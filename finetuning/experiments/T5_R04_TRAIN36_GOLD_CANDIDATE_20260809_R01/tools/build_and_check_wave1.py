from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1]
OLD_ROOT = REPO / "finetuning/experiments/T5_R04_NOVELLIKE_STYLE_CALIBRATION_10BOOKS_20260809_R01"
NEW_ROOT = REPO / "finetuning/experiments/T5_R04_NOVELLIKE_TRAIN36_EXTENSION_20260809_R01"
OLD_LIST = OLD_ROOT / "TRAIN24_SEGMENT_CANDIDATES.md"
NEW_LIST = NEW_ROOT / "TRAIN12_EXTENSION_CANDIDATES.md"
SOURCE_INDEX = OUT / "TRAIN36_SOURCE_INDEX.jsonl"
TXX_MAP = OUT / "TRAIN36_TXX_MAP.jsonl"
GOLD = OUT / "GOLD_DRAFT_WAVE1_E01_E04.jsonl"
DIAGNOSTIC = OUT / "ENTITY_RESOLUTION_DIAGNOSTIC_WAVE1.jsonl"
REVIEW = OUT / "GOLD_DRAFT_WAVE1_REVIEW.md"
ATOMIZER_SOURCE = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/inspection/T5_R04_SYNTHETIC_MICRO24_R01/tools/build_micro24.py"
P4_OUTPUT_SCHEMA = REPO / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"

STATUS_ONTOLOGY = {
    "已发生",
    "正在发生",
    "计划",
    "承诺",
    "条件",
    "推测",
    "误信",
    "否定",
}
INTERVAL_RE = re.compile(r"`?\[(\d+), (\d+)\)`?")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    body = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    path.write_text(body, encoding="utf-8")


def jsonl_row_sha256(row: dict[str, Any]) -> str:
    body = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    return sha256_text(body)


def parse_candidates(path: Path, source_root: Path, source_group: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| TR-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        match = INTERVAL_RE.fullmatch(cells[3])
        if match is None or cells[0] in seen:
            continue
        seen.add(cells[0])
        source_path = source_root / cells[2].strip("`")
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        start, end = int(match.group(1)), int(match.group(2))
        if not 0 <= start < end <= len(source_text):
            raise AssertionError(f"invalid target interval: {cells[0]}")
        target = source_text[start:end]
        rows.append(
            {
                "case_id": cells[0],
                "story_id": cells[1].split()[0],
                "source_group": source_group,
                "source_file": source_path.relative_to(REPO).as_posix(),
                "source_sha256": sha256_bytes(source_bytes),
                "target_start": start,
                "target_end": end,
                "target_text": target,
                "target_sha256": sha256_text(target),
            }
        )
    return rows


def split_units(text: str, max_chars: int = 40) -> list[dict[str, Any]]:
    """Demo-compatible copy of the frozen MICRO24 split_units behavior."""
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
        units.append({"start": start, "end": end, "text": text[start:end]})
        start = end
    return units


def label_units(units: list[dict[str, Any]], prefix: str = "T") -> list[dict[str, Any]]:
    labeled: list[dict[str, Any]] = []
    for index, unit in enumerate(units, 1):
        row = dict(unit)
        row["id"] = f"{prefix}{index:02d}"
        row["text_sha256"] = sha256_text(row["text"])
        labeled.append(row)
    return labeled


def build_indexes() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = parse_candidates(OLD_LIST, OLD_ROOT, "FROZEN_TRAIN24")
    candidates += parse_candidates(NEW_LIST, NEW_ROOT, "WAVE1_EXTENSION12")
    if len(candidates) != 36 or len({row["case_id"] for row in candidates}) != 36:
        raise AssertionError("TRAIN36 denominator is not 36 unique cases")
    e01_target = next(row["target_text"] for row in candidates if row["case_id"] == "TR-E01-01")
    if "游客名单上登记着四十一人" not in e01_target:
        raise AssertionError("E01 registered-count wording is missing")
    if "候车厅里还有四十一名游客" in e01_target:
        raise AssertionError("E01 ambiguous final-count wording remains")
    e01_source = next(row for row in candidates if row["case_id"] == "TR-E01-01")["source_file"]
    e01_full_text = (REPO / e01_source).read_text(encoding="utf-8")
    if e01_full_text.count("留站十八人") != 1 or e01_full_text.count("山顶的十八人") != 1:
        raise AssertionError("E01 final 24-down / 18-station count is not closed")
    if "留站十七人" in e01_full_text or "山顶的十七人" in e01_full_text:
        raise AssertionError("E01 stale 17-person count remains")

    source_rows: list[dict[str, Any]] = []
    txx_rows: list[dict[str, Any]] = []
    for row in candidates:
        units = label_units(split_units(row["target_text"], max_chars=40))
        if not units or len(units) > 99:
            raise AssertionError(f"invalid Txx count: {row['case_id']}")
        if "".join(unit["text"] for unit in units) != row["target_text"]:
            raise AssertionError(f"Txx reconstruction failed: {row['case_id']}")
        source_rows.append(
            {
                "schema_version": "train36-source-index/1.0",
                "dataset_status": "CANDIDATE_NOT_YET_APPROVED",
                "case_id": row["case_id"],
                "story_id": row["story_id"],
                "source_group": row["source_group"],
                "source_file": row["source_file"],
                "source_sha256": row["source_sha256"],
                "target_coordinate_space": "source_unicode_codepoint_0_based_half_open",
                "target_start": row["target_start"],
                "target_end": row["target_end"],
                "target_sha256": row["target_sha256"],
                "project_original": True,
                "confirm24_included": False,
            }
        )
        txx_rows.append(
            {
                "schema_version": "train36-txx-map/1.0",
                "dataset_status": "CANDIDATE_NOT_YET_APPROVED",
                "case_id": row["case_id"],
                "target_sha256": row["target_sha256"],
                "atomizer": {
                    "id": "MICRO_ATOMIZER_R01_PUNCT_AWARE_MAX40_DEMO_COMPAT",
                    "max_chars": 40,
                    "warning": "仅用于 TRAIN36 Demo 兼容切句，不冒充生产 C2_UNIT R02。",
                    "source_implementation": "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/inspection/T5_R04_SYNTHETIC_MICRO24_R01/tools/build_micro24.py#split_units,label_units",
                    "source_implementation_sha256": sha256_bytes(ATOMIZER_SOURCE.read_bytes()),
                },
                "target_units": units,
            }
        )

    write_jsonl(SOURCE_INDEX, source_rows)
    write_jsonl(TXX_MAP, txx_rows)
    return source_rows, txx_rows


def build_review(gold_rows: list[dict[str, Any]], txx_rows: list[dict[str, Any]]) -> None:
    unit_index = {row["case_id"]: row["target_units"] for row in txx_rows}
    lines = [
        "# TRAIN36 Wave1 Gold 草稿审阅版",
        "",
        "当前身份：**CANDIDATE_NOT_YET_APPROVED**。这只是 E01—E04 共 12 题的首轮草稿，不是正式 gold，也不授权训练。",
        "",
        "Txx 使用 MICRO24 的 40 字 Demo 兼容切句；它不属于生产 C2_UNIT R02。共同答案只使用目标段可见称呼，隐藏姓名另见实体还原诊断旁证。",
        "",
        f"未来输出结构绑定 P4.1 C0 Schema（SHA-256：`{sha256_bytes(P4_OUTPUT_SCHEMA.read_bytes())}`）。本草稿沿用 canonical 的 `fact_sentence` 字段；未来 renderer 才机械映射为 assistant 的 `fact`，本轮不渲染训练行。",
        "",
        "审查指令提到的“第一次偏离两次以上就终止”不在当前 E04-03 源文或目标段中，本草稿没有凭空新增这条事实。",
        "",
        "未来渲染整章 A／B／C 输入时，必须剔除 Markdown 文末的“来源：Codex”；它是材料署名，不是小说正文。本轮不删除源文中的署名。",
        "",
    ]
    for row in gold_rows:
        lines += [f"## {row['case_id']}", "", "目标 Txx：", ""]
        for unit in unit_index[row["case_id"]]:
            visible = unit["text"].replace("\n", "↵")
            lines.append(f"- `{unit['id']}` {visible}")
        lines += ["", "草稿事实：", ""]
        for fact in row["facts"]:
            speaker = "null" if fact["speaker"] is None else fact["speaker"]
            evidence = "、".join(fact["evidence_ids"])
            lines.append(
                f"- `{fact['fact_id']}` {fact['fact_sentence']}（状态：{fact['status']}；说话人：{speaker}；证据：{evidence}）"
            )
        lines.append("")
    lines += ["来源：Codex", ""]
    REVIEW.write_text("\n".join(lines), encoding="utf-8")


def refresh_diagnostics(
    source_rows: list[dict[str, Any]], txx_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    source_index = {row["case_id"]: row for row in source_rows}
    txx_index = {row["case_id"]: row for row in txx_rows}
    diagnostics = read_jsonl(DIAGNOSTIC)
    for row in diagnostics:
        case_id = row["case_id"]
        source_row = source_index[case_id]
        txx_row = txx_index[case_id]
        row["schema_version"] = "train36-entity-resolution-diagnostic/1.1"
        row["source_sha256"] = source_row["source_sha256"]
        row["target_sha256"] = source_row["target_sha256"]
        row["txx_map_entry_sha256"] = jsonl_row_sha256(txx_row)
    write_jsonl(DIAGNOSTIC, diagnostics)
    return diagnostics


def check_gold(source_rows: list[dict[str, Any]], txx_rows: list[dict[str, Any]]) -> None:
    if not GOLD.exists():
        print("gold draft not present yet; indexes built")
        return
    gold_rows = read_jsonl(GOLD)
    expected = [f"TR-E{story:02d}-{segment:02d}" for story in range(1, 5) for segment in range(1, 4)]
    if [row["case_id"] for row in gold_rows] != expected:
        raise AssertionError("Wave1 must contain E01-E04 in fixed 12-case order")
    unit_index = {row["case_id"]: row["target_units"] for row in txx_rows}
    hidden_names = {
        "TR-E01-03": "沈澜",
        "TR-E02-03": "周穗",
        "TR-E03-03": "赵海生",
        "TR-E04-01": "韩杉",
    }
    fact_ids: set[str] = set()
    for row in gold_rows:
        if row.get("dataset_status") != "CANDIDATE_NOT_YET_APPROVED":
            raise AssertionError(f"bad candidate status: {row['case_id']}")
        units = unit_index[row["case_id"]]
        valid_ids = [unit["id"] for unit in units]
        for fact in row.get("facts", []):
            if fact.get("fact_id") in fact_ids:
                raise AssertionError(f"duplicate fact id: {fact.get('fact_id')}")
            fact_ids.add(fact.get("fact_id"))
            if not isinstance(fact.get("fact_sentence"), str) or not fact["fact_sentence"].strip():
                raise AssertionError(f"empty fact: {row['case_id']}")
            if fact.get("status") not in STATUS_ONTOLOGY:
                raise AssertionError(f"bad status: {row['case_id']}")
            if fact.get("speaker") is not None and not isinstance(fact["speaker"], str):
                raise AssertionError(f"bad speaker: {row['case_id']}")
            hidden_name = hidden_names.get(row["case_id"])
            if hidden_name and (hidden_name in fact["fact_sentence"] or hidden_name == fact.get("speaker")):
                raise AssertionError(f"hidden name leaked into common gold: {row['case_id']}")
            evidence_ids = fact.get("evidence_ids")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise AssertionError(f"empty evidence: {row['case_id']}")
            positions = [valid_ids.index(evidence_id) for evidence_id in evidence_ids]
            if positions != list(range(positions[0], positions[-1] + 1)):
                raise AssertionError(f"non-contiguous evidence: {row['case_id']}")
        if row.get("expected_fact_count") != len(row.get("facts", [])):
            raise AssertionError(f"fact count drift: {row['case_id']}")

    diagnostics = read_jsonl(DIAGNOSTIC)
    expected_diagnostics = {"TR-E01-03", "TR-E02-03", "TR-E03-03", "TR-E04-01"}
    if {row["case_id"] for row in diagnostics} != expected_diagnostics or len(diagnostics) != 4:
        raise AssertionError("entity diagnostic denominator must be the fixed four cases")
    source_index = {row["case_id"]: row for row in source_rows}
    txx_index = {row["case_id"]: row for row in txx_rows}
    for row in diagnostics:
        source_row = source_index[row["case_id"]]
        txx_row = txx_index[row["case_id"]]
        if row.get("source_sha256") != source_row["source_sha256"]:
            raise AssertionError(f"diagnostic source SHA drift: {row['case_id']}")
        if row.get("target_sha256") != source_row["target_sha256"]:
            raise AssertionError(f"diagnostic target SHA drift: {row['case_id']}")
        if row.get("txx_map_entry_sha256") != jsonl_row_sha256(txx_row):
            raise AssertionError(f"diagnostic Txx SHA drift: {row['case_id']}")
        anchor = row["remote_anchor"]
        source = REPO / anchor["source_file"]
        source_text = source.read_bytes().decode("utf-8", errors="strict")
        actual = source_text[anchor["start"] : anchor["end"]]
        if actual != anchor["text"] or sha256_text(actual) != anchor["text_sha256"]:
            raise AssertionError(f"entity anchor mismatch: {row['case_id']}")

    build_review(gold_rows, txx_rows)


def main() -> None:
    source_rows, txx_rows = build_indexes()
    refresh_diagnostics(source_rows, txx_rows)
    check_gold(source_rows, txx_rows)
    print(f"source_index={len(source_rows)}")
    print(f"txx_map={len(txx_rows)}")
    print("reconstruction=36/36")


if __name__ == "__main__":
    main()
