from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1]
SOURCE_INDEX = OUT / "TRAIN36_SOURCE_INDEX.jsonl"
TXX_MAP = OUT / "TRAIN36_TXX_MAP.jsonl"
GOLD = OUT / "GOLD_DRAFT_WAVE2_T01_T05.jsonl"
DIAGNOSTIC = OUT / "ENTITY_RESOLUTION_DIAGNOSTIC_WAVE2.jsonl"
REVIEW = OUT / "GOLD_DRAFT_WAVE2_REVIEW.md"

EXPECTED_CASES = [
    "TR-T01-01",
    "TR-T01-02",
    "TR-T01-03",
    "TR-T02-01",
    "TR-T02-02",
    "TR-T03-01",
    "TR-T03-02",
    "TR-T04-01",
    "TR-T04-02",
    "TR-T05-01",
    "TR-T05-02",
    "TR-T05-03",
]
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
HIDDEN_NAMES = {
    "TR-T01-02": {"罗伊", "方禾"},
    "TR-T04-02": {"罗锦"},
}
VISIBLE_NAME_ANCHORS = {
    "唐越",
    "老冯",
    "罗伊",
    "方禾",
    "罗澄",
    "陈寿",
    "桑禾",
    "梁九",
    "顾拙",
    "周诚",
    "邵晴",
    "祁南",
    "许葵",
    "周成海",
    "罗锦",
    "小陶",
    "老魏",
    "闻岫",
    "孟照",
    "宁芷",
    "闻川",
    "季迟",
}
CONTEXTUAL_NAME_ANCHOR_EXCEPTIONS = {
    # T06 是唐越连续核问的原话；终审要求最小证据只保留 T06，
    # 动作主体由同题紧邻上下文确定，不把 T05 重新并入证据。
    ("TR-T01-02", "TR-T01-02-F06", "唐越"),
    # T22 中“我姐”由紧邻 T21 锚定为罗伊；终审只校准事实句，
    # 未要求扩张现有最小证据范围。
    ("TR-T01-03", "TR-T01-03-F18", "罗伊"),
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def jsonl_row_sha256(row: dict[str, Any]) -> str:
    body = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    return sha256_text(body)


def check_and_build() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_rows = read_jsonl(SOURCE_INDEX)
    txx_rows = read_jsonl(TXX_MAP)
    if len(source_rows) != 36 or len({row["case_id"] for row in source_rows}) != 36:
        raise AssertionError("TRAIN36 source index denominator drift")
    if len(txx_rows) != 36 or len({row["case_id"] for row in txx_rows}) != 36:
        raise AssertionError("TRAIN36 Txx denominator drift")
    source_index = {row["case_id"]: row for row in source_rows}
    txx_index = {row["case_id"]: row for row in txx_rows}
    if any(case_id not in source_index or case_id not in txx_index for case_id in EXPECTED_CASES):
        raise AssertionError("Wave2 case missing from frozen TRAIN36 indexes")
    for case_id in EXPECTED_CASES:
        source_row = source_index[case_id]
        txx_row = txx_index[case_id]
        source_bytes = (REPO / source_row["source_file"]).read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        target_text = source_text[source_row["target_start"] : source_row["target_end"]]
        if sha256_bytes(source_bytes) != source_row["source_sha256"]:
            raise AssertionError(f"source SHA drift: {case_id}")
        if sha256_text(target_text) != source_row["target_sha256"]:
            raise AssertionError(f"target slice drift: {case_id}")
        if "".join(unit["text"] for unit in txx_row["target_units"]) != target_text:
            raise AssertionError(f"Txx reconstruction drift: {case_id}")
        if source_row["target_sha256"] != txx_row["target_sha256"]:
            raise AssertionError(f"target SHA drift: {case_id}")

    gold_rows = read_jsonl(GOLD)
    if [row["case_id"] for row in gold_rows] != EXPECTED_CASES:
        raise AssertionError("Wave2 must contain the fixed 12 cases in order")
    if len({row["case_id"] for row in gold_rows}) != 12:
        raise AssertionError("Wave2 case IDs are not unique")

    fact_ids: set[str] = set()
    for row in gold_rows:
        case_id = row["case_id"]
        if row.get("dataset_status") != "CANDIDATE_NOT_YET_APPROVED":
            raise AssertionError(f"bad candidate status: {case_id}")
        units = txx_index[case_id]["target_units"]
        valid_ids = [unit["id"] for unit in units]
        for fact in row.get("facts", []):
            fact_id = fact.get("fact_id")
            if fact_id in fact_ids:
                raise AssertionError(f"duplicate fact ID: {fact_id}")
            fact_ids.add(fact_id)
            if not isinstance(fact.get("fact_sentence"), str) or not fact["fact_sentence"].strip():
                raise AssertionError(f"empty fact: {fact_id}")
            if fact.get("status") not in STATUS_ONTOLOGY:
                raise AssertionError(f"bad status: {fact_id}")
            if fact.get("speaker") is not None and not isinstance(fact["speaker"], str):
                raise AssertionError(f"bad speaker: {fact_id}")
            evidence_ids = fact.get("evidence_ids")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise AssertionError(f"empty evidence: {fact_id}")
            try:
                positions = [valid_ids.index(evidence_id) for evidence_id in evidence_ids]
            except ValueError as exc:
                raise AssertionError(f"foreign evidence ID: {fact_id}") from exc
            if positions != list(range(positions[0], positions[-1] + 1)):
                raise AssertionError(f"non-contiguous evidence: {fact_id}")
            evidence_text = "".join(units[position]["text"] for position in positions)
            # 对话轮的 speaker 由同题上下文确定；这里只阻止 fact_sentence 本身
            # 使用证据片段里看不到的姓名。
            claimed_text = fact["fact_sentence"]
            for name in VISIBLE_NAME_ANCHORS:
                exception_key = (case_id, fact_id, name)
                if (
                    name in claimed_text
                    and name not in evidence_text
                    and exception_key not in CONTEXTUAL_NAME_ANCHOR_EXCEPTIONS
                ):
                    raise AssertionError(f"name lacks visible evidence anchor: {fact_id}: {name}")
            for hidden_name in HIDDEN_NAMES.get(case_id, set()):
                if hidden_name in fact["fact_sentence"] or hidden_name == fact.get("speaker"):
                    raise AssertionError(f"hidden name leaked: {fact_id}")
        if row.get("expected_fact_count") != len(row.get("facts", [])):
            raise AssertionError(f"fact count drift: {case_id}")

    facts_by_case = {row["case_id"]: row["facts"] for row in gold_rows}
    all_fact_text = "\n".join(
        fact["fact_sentence"] for facts in facts_by_case.values() for fact in facts
    )
    for stale_phrase in ("手续次日再补", "过度浇水", "不再是药圃的无名弟子"):
        if stale_phrase in all_fact_text:
            raise AssertionError(f"reviewed-out wording remains: {stale_phrase}")
    if any(fact["status"] == "误信" for fact in facts_by_case["TR-T02-01"]):
        raise AssertionError("TR-T02-01 must not mark Liang Jiu's uncorrected suspicion as misbelief")
    required_facts = {
        "TR-T01-01": "身份证照片中的姑娘与面前女人五官基本对得上",
        "TR-T01-03": "半小时前拍摄的玄关照片显示门链当时没有扣上",
        "TR-T03-02": "防火门上的纯机械计数器已经三十年没有更换",
        "TR-T04-02": "手续今天补",
        "TR-T05-03": "旧案归戒律堂管辖，不归药圃",
    }
    for case_id, snippet in required_facts.items():
        if not any(snippet in fact["fact_sentence"] for fact in facts_by_case[case_id]):
            raise AssertionError(f"review-required fact missing: {case_id}: {snippet}")

    diagnostics = read_jsonl(DIAGNOSTIC)
    if [row["case_id"] for row in diagnostics] != ["TR-T01-02", "TR-T04-02"]:
        raise AssertionError("Wave2 entity diagnostics must be the fixed two cases")
    for row in diagnostics:
        case_id = row["case_id"]
        source_row = source_index[case_id]
        txx_row = txx_index[case_id]
        if row.get("source_sha256") != source_row["source_sha256"]:
            raise AssertionError(f"diagnostic source SHA drift: {case_id}")
        if row.get("target_sha256") != source_row["target_sha256"]:
            raise AssertionError(f"diagnostic target SHA drift: {case_id}")
        if row.get("txx_map_entry_sha256") != jsonl_row_sha256(txx_row):
            raise AssertionError(f"diagnostic Txx SHA drift: {case_id}")
        anchor = row["remote_anchor"]
        source_text = (REPO / anchor["source_file"]).read_bytes().decode("utf-8", errors="strict")
        actual = source_text[anchor["start"] : anchor["end"]]
        if actual != anchor["text"] or sha256_text(actual) != anchor["text_sha256"]:
            raise AssertionError(f"diagnostic anchor mismatch: {case_id}")

    build_review(gold_rows, txx_index)
    return gold_rows, diagnostics


def build_review(gold_rows: list[dict[str, Any]], txx_index: dict[str, dict[str, Any]]) -> None:
    lines = [
        "# TRAIN36 Wave2 Gold 草稿审阅版",
        "",
        "当前身份：**CANDIDATE_NOT_YET_APPROVED**。本文仅覆盖 T01—T05 的 12 题，不是正式 gold，也不授权训练。",
        "",
        "Txx 继续复用 TRAIN36 冻结映射。共同 gold 只使用目标段内可见称呼；T01-02 与 T04-02 的整章姓名还原另见诊断旁证。",
        "",
    ]
    for row in gold_rows:
        lines.extend([f"## {row['case_id']}", "", "目标 Txx：", ""])
        for unit in txx_index[row["case_id"]]["target_units"]:
            visible = unit["text"].replace("\n", "↵")
            lines.append(f"- `{unit['id']}` {visible}")
        lines.extend(["", "草稿事实：", ""])
        for fact in row["facts"]:
            speaker = "null" if fact["speaker"] is None else fact["speaker"]
            evidence = "、".join(fact["evidence_ids"])
            lines.append(
                f"- `{fact['fact_id']}` {fact['fact_sentence']}"
                f"（状态：{fact['status']}；说话人：{speaker}；证据：{evidence}）"
            )
        lines.append("")
    lines.extend(["来源：Codex", ""])
    REVIEW.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    gold_rows, diagnostics = check_and_build()
    print(f"wave2_cases={len(gold_rows)}")
    print(f"wave2_facts={sum(len(row['facts']) for row in gold_rows)}")
    print(f"entity_diagnostics={len(diagnostics)}")


if __name__ == "__main__":
    main()
