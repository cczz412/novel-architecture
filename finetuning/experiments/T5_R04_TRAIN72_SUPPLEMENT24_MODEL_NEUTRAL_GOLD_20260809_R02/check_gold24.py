from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

OLD_CANDIDATES = ROOT / (
    "finetuning/experiments/"
    "T5_R04_TRAIN72_SUPPLEMENT24_SEGMENT_CANDIDATES_20260809_R01/"
    "SUPPLEMENT24_SEGMENT_CANDIDATES.jsonl"
)
NEW_CANDIDATES = ROOT / (
    "finetuning/experiments/"
    "T5_R04_TRAIN72_SUPPLEMENT16_ORIGINAL_SOURCE_CANDIDATES_20260809_R01/"
    "GENERATED_CANDIDATE_POOL.jsonl"
)
SOURCE_INDEX = HERE / "SOURCE_INDEX_24.jsonl"
GOLD = HERE / "MODEL_NEUTRAL_GOLD_24.jsonl"

EXPECTED_OLD_SHA = "13d98fa578f61ce099b255c04e9ed13ea0dba20e3a3f565c9132e51ee3c813aa"
EXPECTED_NEW_SHA = "f7db1f4e2f73d77b47c61353a43cf6e4a115ba5b6e1382cc58e5b1567c6c703b"
OLD_IDS = [
    "TR72-S18",
    "TR72-M12",
    "TR72-M13",
    "TR72-M14",
    "TR72-M15",
    "TR72-M16",
    "TR72-M17",
    "TR72-M18",
]
STATUSES = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}
EXPECTED_FACT_COUNTS = {
    "TR72-S18": 4,
    "TR72-M12": 10,
    "TR72-M13": 8,
    "TR72-M14": 10,
    "TR72-M15": 8,
    "TR72-M16": 9,
    "TR72-M17": 12,
    "TR72-M18": 13,
    "SUP16-A-01": 7,
    "SUP16-A-02": 10,
    "SUP16-A-03": 2,
    "SUP16-B-01": 4,
    "SUP16-B-02": 13,
    "SUP16-C-01": 18,
    "SUP16-C-02": 4,
    "SUP16-C-03": 4,
    "SUP16-D-01": 9,
    "SUP16-D-02": 14,
    "SUP16-D-03": 10,
    "SUP16-E-01": 5,
    "SUP16-E-02": 6,
    "SUP16-E-03": 16,
    "SUP16-F-01": 10,
    "SUP16-F-02": 24,
}

OVERLAP_INDEXES = [
    ROOT / "finetuning/experiments/T5_R04_TRAIN36_GOLD_CANDIDATE_20260809_R01/TRAIN36_SOURCE_INDEX.jsonl",
    ROOT / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/S6_SOURCE_INDEX.jsonl",
    ROOT / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/M6_SOURCE_INDEX.jsonl",
    ROOT / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/L6_SOURCE_INDEX.jsonl",
    ROOT / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01/REAL24_SOURCE_INDEX.jsonl",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} 不是 JSON 对象")
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
    )
    path.write_text(text, encoding="utf-8")


def split_units(text: str, max_chars: int = 40) -> list[dict[str, Any]]:
    """现役 Demo 兼容切句：只看目标文本和标点，不读取 Gold。"""
    if not text:
        return []
    strong = set("。！？!?；;\n")
    medium = set("，,：:、")
    units: list[dict[str, Any]] = []
    start = 0
    while start < len(text):
        hard_end = min(start + max_chars, len(text))
        end = hard_end
        if hard_end < len(text):
            min_cut = start + max(12, max_chars // 2)
            strong_pos = [i + 1 for i in range(min_cut, hard_end) if text[i] in strong]
            medium_pos = [i + 1 for i in range(min_cut, hard_end) if text[i] in medium]
            if strong_pos:
                end = strong_pos[-1]
            elif medium_pos:
                end = medium_pos[-1]
        if end <= start:
            end = min(start + max_chars, len(text))
        unit_text = text[start:end]
        units.append(
            {
                "id": f"T{len(units) + 1:02d}",
                "start": start,
                "end": end,
                "text": unit_text,
                "text_sha256": sha256_bytes(unit_text.encode("utf-8")),
            }
        )
        start = end
    return units


def frozen_candidates() -> list[dict[str, Any]]:
    if file_sha256(OLD_CANDIDATES) != EXPECTED_OLD_SHA:
        raise ValueError("旧8候选清单 SHA 漂移")
    if file_sha256(NEW_CANDIDATES) != EXPECTED_NEW_SHA:
        raise ValueError("新16候选池 SHA 漂移")

    old_rows = read_jsonl(OLD_CANDIDATES)
    if [row["case_id"] for row in old_rows] != OLD_IDS:
        raise ValueError("旧8 case_id 或顺序漂移")
    new_rows = [
        row
        for row in read_jsonl(NEW_CANDIDATES)
        if row.get("selection_status") == "SELECTED_FOR_SUPPLEMENT16"
    ]
    if len(new_rows) != 16:
        raise ValueError(f"新候选入选数不是16：{len(new_rows)}")
    return old_rows + new_rows


def build_source_index() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for position, candidate in enumerate(frozen_candidates(), 1):
        case_id = candidate.get("case_id") or candidate["candidate_id"]
        source_path = candidate["source_path"]
        source_file = ROOT / source_path
        source_bytes = source_file.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        source_sha = sha256_bytes(source_bytes)
        if source_sha != candidate["source_chapter_sha256"]:
            raise ValueError(f"{case_id} 原章 SHA 不符")
        start = candidate["char_start"]
        end = candidate["char_end"]
        if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(source_text)):
            raise ValueError(f"{case_id} 坐标越界")
        target = source_text[start:end]
        target_sha = sha256_bytes(target.encode("utf-8"))
        if target_sha != candidate["segment_sha256"]:
            raise ValueError(f"{case_id} 目标 SHA 不符")
        rows.append(
            {
                "schema_version": "train72-supplement24-source-index/1.0",
                "dataset_status": "CANDIDATE_NOT_YET_APPROVED",
                "row_index": position,
                "case_id": case_id,
                "source_id": candidate["source_id"],
                "source_path": source_path,
                "source_chapter_sha256": source_sha,
                "coordinate_space": "unicode_codepoint_0_based_half_open",
                "target_start": start,
                "target_end": end,
                "target_sha256": target_sha,
                "target_units": split_units(target),
                "project_original": True,
                "training_authorized": False,
            }
        )
    return rows


def validate_source_index(rows: list[dict[str, Any]]) -> None:
    expected_candidates = frozen_candidates()
    expected_ids = [row.get("case_id") or row["candidate_id"] for row in expected_candidates]
    if len(rows) != 24 or [row["case_id"] for row in rows] != expected_ids:
        raise ValueError("来源索引不是冻结的24题顺序")
    if len({row["case_id"] for row in rows}) != 24:
        raise ValueError("来源索引 case_id 重复")
    if len({row["target_sha256"] for row in rows}) != 24:
        raise ValueError("来源索引目标 SHA 重复")

    for row in rows:
        source_path = ROOT / row["source_path"]
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        if sha256_bytes(source_bytes) != row["source_chapter_sha256"]:
            raise ValueError(f"{row['case_id']} 原章 SHA 漂移")
        target = source_text[row["target_start"] : row["target_end"]]
        if sha256_bytes(target.encode("utf-8")) != row["target_sha256"]:
            raise ValueError(f"{row['case_id']} 目标 SHA 漂移")
        units = row["target_units"]
        if units != split_units(target):
            raise ValueError(f"{row['case_id']} Txx 不是事实无关机械切分结果")
        if "".join(unit["text"] for unit in units) != target:
            raise ValueError(f"{row['case_id']} Txx 无法逐字重建目标段")


def validate_no_overlap(rows: list[dict[str, Any]]) -> int:
    prior: list[dict[str, Any]] = []
    for path in OVERLAP_INDEXES:
        prior.extend(read_jsonl(path))

    overlaps = 0
    for row in rows:
        for old in prior:
            old_path = old.get("source_path") or old.get("source_file")
            old_start = old.get("target_start", old.get("char_start"))
            old_end = old.get("target_end", old.get("char_end"))
            old_sha = old.get("target_sha256", old.get("segment_sha256"))
            same_sha = old_sha == row["target_sha256"]
            same_path_overlap = (
                old_path == row["source_path"]
                and isinstance(old_start, int)
                and isinstance(old_end, int)
                and max(old_start, row["target_start"]) < min(old_end, row["target_end"])
            )
            if same_sha or same_path_overlap:
                overlaps += 1
    if overlaps:
        raise ValueError(f"与既有训练/L6/REAL24目标重叠：{overlaps}")
    return overlaps


def validate_gold(source_rows: list[dict[str, Any]], gold_rows: list[dict[str, Any]]) -> dict[str, int]:
    if len(gold_rows) != 24:
        raise ValueError(f"Gold 题数不是24：{len(gold_rows)}")
    if [row["case_id"] for row in gold_rows] != [row["case_id"] for row in source_rows]:
        raise ValueError("Gold case_id 或顺序与来源索引不一致")
    source_by_id = {row["case_id"]: row for row in source_rows}
    fact_total = 0
    empty_cases = 0
    for row in gold_rows:
        if row.get("dataset_status") != "CANDIDATE_NOT_YET_APPROVED":
            raise ValueError(f"{row['case_id']} 候选状态错误")
        if row.get("common_answer_entity_policy") != "TARGET_VISIBLE_SURFACE_ONLY":
            raise ValueError(f"{row['case_id']} 实体政策错误")
        if row.get("exhaustive_within_target_candidate") is not True:
            raise ValueError(f"{row['case_id']} 穷尽候选字段错误")
        facts = row.get("facts")
        if not isinstance(facts, list):
            raise ValueError(f"{row['case_id']} facts 不是数组")
        if row.get("expected_fact_count") != len(facts):
            raise ValueError(f"{row['case_id']} expected_fact_count 不是 len(facts)")
        if len(facts) != EXPECTED_FACT_COUNTS[row["case_id"]]:
            raise ValueError(f"{row['case_id']} 事实数不是R02冻结值")
        if not facts:
            empty_cases += 1
        fact_total += len(facts)
        source = source_by_id[row["case_id"]]
        unit_ids = [unit["id"] for unit in source["target_units"]]
        fact_ids: set[str] = set()
        for fact in facts:
            required = {"fact_id", "fact_sentence", "status", "speaker", "evidence_ids"}
            if set(fact) != required:
                raise ValueError(f"{row['case_id']} 事实字段不精确")
            if fact["fact_id"] in fact_ids:
                raise ValueError(f"{row['case_id']} fact_id 重复")
            fact_ids.add(fact["fact_id"])
            if not isinstance(fact["fact_sentence"], str) or not fact["fact_sentence"].strip():
                raise ValueError(f"{row['case_id']} 事实句为空")
            if fact["status"] not in STATUSES:
                raise ValueError(f"{row['case_id']} 非法状态")
            if fact["speaker"] is not None and not isinstance(fact["speaker"], str):
                raise ValueError(f"{row['case_id']} speaker 类型错误")
            evidence = fact["evidence_ids"]
            if not isinstance(evidence, list) or not evidence:
                raise ValueError(f"{row['case_id']} evidence_ids 为空或非数组")
            try:
                positions = [unit_ids.index(item) for item in evidence]
            except ValueError as exc:
                raise ValueError(f"{row['case_id']} evidence 不在本题 Txx") from exc
            if positions != list(range(positions[0], positions[-1] + 1)):
                raise ValueError(f"{row['case_id']} evidence 不连续或乱序")
        expected_fact_ids = {
            f"{row['case_id']}-F{index:03d}" for index in range(1, len(facts) + 1)
        }
        if fact_ids != expected_fact_ids:
            raise ValueError(f"{row['case_id']} fact_id 不是顺序编号")
    if fact_total != 230:
        raise ValueError(f"R02 事实总数不是230：{fact_total}")
    return {"cases": len(gold_rows), "facts": fact_total, "empty_cases": empty_cases}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build-source-index", "validate"))
    args = parser.parse_args()

    if args.command == "build-source-index":
        rows = build_source_index()
        write_jsonl(SOURCE_INDEX, rows)
        validate_source_index(rows)
        print(json.dumps({"status": "PASS", "source_cases": len(rows)}, ensure_ascii=False))
        return

    source_rows = read_jsonl(SOURCE_INDEX)
    validate_source_index(source_rows)
    overlaps = validate_no_overlap(source_rows)
    gold_stats = validate_gold(source_rows, read_jsonl(GOLD))
    print(json.dumps({"status": "PASS", "overlaps": overlaps, **gold_stats}, ensure_ascii=False))


if __name__ == "__main__":
    main()
