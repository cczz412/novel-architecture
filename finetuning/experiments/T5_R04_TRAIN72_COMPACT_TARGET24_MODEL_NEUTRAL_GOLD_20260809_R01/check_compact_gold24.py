from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PARENT_DIR = ROOT / (
    "finetuning/experiments/"
    "T5_R04_TRAIN72_SUPPLEMENT24_MODEL_NEUTRAL_GOLD_20260809_R02"
)
PARENT_SOURCE = PARENT_DIR / "SOURCE_INDEX_24.jsonl"
PARENT_GOLD = PARENT_DIR / "MODEL_NEUTRAL_GOLD_24.jsonl"
SOURCE_INDEX = HERE / "SOURCE_INDEX_24.jsonl"
GOLD = HERE / "MODEL_NEUTRAL_GOLD_24.jsonl"

EXPECTED_PARENT_SOURCE_SHA = (
    "21c8c29ba1551129219b0f7ca46fc35093e1f0f66592553012d171a94e71dae6"
)
EXPECTED_PARENT_GOLD_SHA = (
    "35f028ee1c198ec5a0651a158ee7312dfb6e5eb072c806f4055bb2d91d759353"
)
STATUSES = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}

# case_id, 密度档, 父 case_id, 父 Txx 起点, 父 Txx 终点, 审收后事实数
SPECS = [
    ("CT72-L01", "LOW_0_TO_3", "TR72-S18", 9, 14, 0),
    ("CT72-L02", "LOW_0_TO_3", "TR72-M13", 8, 12, 0),
    ("CT72-L03", "LOW_0_TO_3", "SUP16-A-01", 1, 5, 0),
    ("CT72-L04", "LOW_0_TO_3", "SUP16-A-03", 10, 14, 0),
    ("CT72-L05", "LOW_0_TO_3", "SUP16-A-02", 13, 16, 0),
    ("CT72-L06", "LOW_0_TO_3", "TR72-M15", 8, 12, 1),
    ("CT72-L07", "LOW_0_TO_3", "SUP16-C-02", 16, 20, 1),
    ("CT72-L08", "LOW_0_TO_3", "TR72-M14", 12, 16, 2),
    ("CT72-L09", "LOW_0_TO_3", "TR72-M18", 17, 22, 2),
    ("CT72-L10", "LOW_0_TO_3", "TR72-M17", 13, 17, 3),
    ("CT72-L11", "LOW_0_TO_3", "SUP16-C-01", 7, 11, 3),
    ("CT72-L12", "LOW_0_TO_3", "SUP16-C-03", 19, 22, 3),
    ("CT72-M01", "MEDIUM_4_TO_6", "TR72-M12", 18, 22, 4),
    ("CT72-M02", "MEDIUM_4_TO_6", "TR72-M16", 14, 19, 4),
    ("CT72-M03", "MEDIUM_4_TO_6", "SUP16-B-01", 9, 13, 4),
    ("CT72-M04", "MEDIUM_4_TO_6", "SUP16-B-02", 11, 14, 4),
    ("CT72-M05", "MEDIUM_4_TO_6", "SUP16-D-01", 20, 24, 4),
    ("CT72-M06", "MEDIUM_4_TO_6", "SUP16-D-02", 13, 16, 4),
    ("CT72-M07", "MEDIUM_4_TO_6", "SUP16-D-03", 13, 17, 4),
    ("CT72-M08", "MEDIUM_4_TO_6", "SUP16-E-01", 17, 21, 4),
    ("CT72-M09", "MEDIUM_4_TO_6", "SUP16-E-03", 1, 4, 4),
    ("CT72-M10", "MEDIUM_4_TO_6", "SUP16-F-02", 11, 14, 4),
    ("CT72-M11", "MEDIUM_4_TO_6", "SUP16-F-01", 14, 18, 5),
    ("CT72-M12", "MEDIUM_4_TO_6", "SUP16-E-02", 17, 21, 6),
]
SOURCE_SPECS = [spec[:5] for spec in SPECS]

OVERLAP_INDEXES = [
    ROOT
    / "finetuning/experiments/T5_R04_TRAIN36_GOLD_CANDIDATE_20260809_R01/TRAIN36_SOURCE_INDEX.jsonl",
    ROOT
    / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/S6_SOURCE_INDEX.jsonl",
    ROOT
    / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/M6_SOURCE_INDEX.jsonl",
    ROOT
    / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/L6_SOURCE_INDEX.jsonl",
    ROOT
    / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01/REAL24_SOURCE_INDEX.jsonl",
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
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )
    path.write_text(text, encoding="utf-8")


def check_parent_bindings() -> None:
    if file_sha256(PARENT_SOURCE) != EXPECTED_PARENT_SOURCE_SHA:
        raise ValueError("R02 父来源索引 SHA 漂移")
    if file_sha256(PARENT_GOLD) != EXPECTED_PARENT_GOLD_SHA:
        raise ValueError("R02 父 Gold SHA 漂移")


def build_source_index() -> list[dict[str, Any]]:
    check_parent_bindings()
    parent_rows = {row["case_id"]: row for row in read_jsonl(PARENT_SOURCE)}
    rows: list[dict[str, Any]] = []
    for row_index, (case_id, band, parent_case, first, last) in enumerate(
        SOURCE_SPECS, 1
    ):
        parent = parent_rows[parent_case]
        units = parent["target_units"][first - 1 : last]
        if [unit["id"] for unit in units] != [
            f"T{number:02d}" for number in range(first, last + 1)
        ]:
            raise ValueError(f"{case_id} 父 Txx 范围不连续")
        first_offset = units[0]["start"]
        last_offset = units[-1]["end"]
        target = "".join(unit["text"] for unit in units)
        source_path = ROOT / parent["source_path"]
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        target_start = parent["target_start"] + first_offset
        target_end = parent["target_start"] + last_offset
        if source_text[target_start:target_end] != target:
            raise ValueError(f"{case_id} 绝对坐标不能重建小负责区")
        local_units = []
        for local_index, unit in enumerate(units, 1):
            unit_text = unit["text"]
            local_units.append(
                {
                    "id": f"T{local_index:02d}",
                    "parent_unit_id": unit["id"],
                    "start": unit["start"] - first_offset,
                    "end": unit["end"] - first_offset,
                    "text": unit_text,
                    "text_sha256": sha256_bytes(unit_text.encode("utf-8")),
                }
            )
        rows.append(
            {
                "schema_version": "train72-compact-target24-source-index/1.0",
                "dataset_status": "CANDIDATE_NOT_YET_APPROVED",
                "row_index": row_index,
                "case_id": case_id,
                "density_band": band,
                "parent_case_id": parent_case,
                "parent_txx_start": f"T{first:02d}",
                "parent_txx_end": f"T{last:02d}",
                "parent_target_sha256": parent["target_sha256"],
                "source_id": parent["source_id"],
                "source_path": parent["source_path"],
                "source_chapter_sha256": parent["source_chapter_sha256"],
                "coordinate_space": "unicode_codepoint_0_based_half_open",
                "target_start": target_start,
                "target_end": target_end,
                "target_sha256": sha256_bytes(target.encode("utf-8")),
                "target_units": local_units,
                "project_original": True,
                "training_authorized": False,
            }
        )
    return rows


def validate_source_index(rows: list[dict[str, Any]]) -> None:
    expected_ids = [spec[0] for spec in SPECS]
    if len(rows) != 24 or [row["case_id"] for row in rows] != expected_ids:
        raise ValueError("小负责区索引不是冻结的24题顺序")
    if len({row["case_id"] for row in rows}) != 24:
        raise ValueError("case_id 重复")
    if len({row["target_sha256"] for row in rows}) != 24:
        raise ValueError("目标段 SHA 重复")
    if rows != build_source_index():
        raise ValueError("小负责区索引不是父 Txx 的机械派生结果")
    for row in rows:
        source_path = ROOT / row["source_path"]
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        if sha256_bytes(source_bytes) != row["source_chapter_sha256"]:
            raise ValueError(f"{row['case_id']} 原章 SHA 漂移")
        target = source_text[row["target_start"] : row["target_end"]]
        if sha256_bytes(target.encode("utf-8")) != row["target_sha256"]:
            raise ValueError(f"{row['case_id']} 小负责区 SHA 漂移")
        if "".join(unit["text"] for unit in row["target_units"]) != target:
            raise ValueError(f"{row['case_id']} 局部 Txx 无法逐字重建")


def validate_no_overlap(rows: list[dict[str, Any]]) -> dict[str, int]:
    within = 0
    for index, row in enumerate(rows):
        for other in rows[index + 1 :]:
            if row["source_path"] != other["source_path"]:
                continue
            if max(row["target_start"], other["target_start"]) < min(
                row["target_end"], other["target_end"]
            ):
                within += 1
    if within:
        raise ValueError(f"24个小负责区内部重叠：{within}")

    prior: list[dict[str, Any]] = []
    for path in OVERLAP_INDEXES:
        prior.extend(read_jsonl(path))
    prior_overlaps = 0
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
                prior_overlaps += 1
    if prior_overlaps:
        raise ValueError(f"与 TRAIN36/S6/M6/L6/REAL24 重叠：{prior_overlaps}")
    return {"within_compact24_overlaps": within, "prior_target_overlaps": prior_overlaps}


def validate_gold(
    source_rows: list[dict[str, Any]], gold_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(gold_rows) != 24:
        raise ValueError(f"Gold 题数不是24：{len(gold_rows)}")
    if [row["case_id"] for row in gold_rows] != [row["case_id"] for row in source_rows]:
        raise ValueError("Gold 顺序与来源索引不一致")
    fact_total = 0
    counts: list[int] = []
    for source, row, spec in zip(source_rows, gold_rows, SPECS, strict=True):
        if row.get("dataset_status") != "CANDIDATE_NOT_YET_APPROVED":
            raise ValueError(f"{row['case_id']} 候选状态错误")
        if row.get("common_answer_entity_policy") != "TARGET_VISIBLE_SURFACE_ONLY":
            raise ValueError(f"{row['case_id']} 实体政策错误")
        if row.get("exhaustive_within_target_candidate") is not True:
            raise ValueError(f"{row['case_id']} 穷尽候选字段错误")
        facts = row.get("facts")
        if not isinstance(facts, list):
            raise ValueError(f"{row['case_id']} facts 不是数组")
        if row.get("expected_fact_count") != len(facts) or len(facts) != spec[5]:
            raise ValueError(f"{row['case_id']} 事实数不是审收冻结值")
        counts.append(len(facts))
        fact_total += len(facts)
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
                raise ValueError(f"{row['case_id']} 状态非法")
            if fact["speaker"] is not None and not isinstance(fact["speaker"], str):
                raise ValueError(f"{row['case_id']} speaker 类型非法")
            evidence = fact["evidence_ids"]
            if not isinstance(evidence, list) or not evidence:
                raise ValueError(f"{row['case_id']} evidence_ids 非法")
            try:
                positions = [unit_ids.index(item) for item in evidence]
            except ValueError as exc:
                raise ValueError(f"{row['case_id']} evidence 越出小负责区") from exc
            if positions != list(range(positions[0], positions[-1] + 1)):
                raise ValueError(f"{row['case_id']} evidence 不连续或乱序")
        expected_fact_ids = {
            f"{row['case_id']}-F{index:03d}" for index in range(1, len(facts) + 1)
        }
        if fact_ids != expected_fact_ids:
            raise ValueError(f"{row['case_id']} fact_id 不连续")

    low_counts = counts[:12]
    medium_counts = counts[12:]
    if any(count < 0 or count > 3 for count in low_counts):
        raise ValueError(f"低档越出0–3：{low_counts}")
    if any(count < 4 or count > 6 for count in medium_counts):
        raise ValueError(f"中档越出4–6：{medium_counts}")
    return {
        "cases": len(gold_rows),
        "facts": fact_total,
        "empty_cases": sum(count == 0 for count in counts),
        "low_counts": low_counts,
        "medium_counts": medium_counts,
    }


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

    check_parent_bindings()
    source_rows = read_jsonl(SOURCE_INDEX)
    validate_source_index(source_rows)
    overlaps = validate_no_overlap(source_rows)
    gold_stats = validate_gold(source_rows, read_jsonl(GOLD))
    print(json.dumps({"status": "PASS", **overlaps, **gold_stats}, ensure_ascii=False))


if __name__ == "__main__":
    main()
