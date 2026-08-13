from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1]
SOURCE_INDEX = OUT / "TRAIN36_SOURCE_INDEX.jsonl"
TXX_MAP = OUT / "TRAIN36_TXX_MAP.jsonl"
GOLD = OUT / "GOLD_DRAFT_WAVE3_C01_C05.jsonl"
DIAGNOSTIC = OUT / "ENTITY_RESOLUTION_DIAGNOSTIC_WAVE3.jsonl"
REVIEW = OUT / "GOLD_DRAFT_WAVE3_REVIEW.md"

EXPECTED_CASES = [
    "TR-C01-01",
    "TR-C01-02",
    "TR-C02-01",
    "TR-C02-02",
    "TR-C03-01",
    "TR-C03-02",
    "TR-C04-01",
    "TR-C04-02",
    "TR-C04-03",
    "TR-C05-01",
    "TR-C05-02",
    "TR-C05-03",
]
STATUS_ONTOLOGY = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}
HIDDEN_NAMES = {"TR-C02-02": {"彭勇"}, "TR-C05-02": {"柳娘"}}
ENTITY_NAMES_AND_ROLES = {
    "叶迎",
    "桂婶",
    "田叔",
    "小满",
    "石头",
    "任青",
    "赵师傅",
    "彭勇",
    "物业主管",
    "维修公司",
    "那名十楼住户",
    "赵一航",
    "陈叔",
    "沈礼",
    "许栀",
    "高燃",
    "乔曼",
    "梁穗",
    "梁川",
    "梁守诚",
    "阿梅",
    "梅琴",
    "陆青梧",
    "佟掌柜",
    "柳娘",
    "黄老板",
    "胡嫂",
    "莫巡检",
}

# 终审定点修复的最小回归表；不锁定每题事实数。
EXPECTED_CORRECTIONS = [
    ("TR-C01-01", "清早六点，南塘村晒谷场上摆着一双红布鞋。", "正在发生", None, ["T01"]),
    ("TR-C01-01", "红布鞋摆在晒谷场改造投票当天。", "已发生", None, ["T10"]),
    ("TR-C01-02", "石头称小满每天坐在老樟树旁看他们打球。", "正在发生", "石头", ["T06"]),
    (
        "TR-C01-02",
        "石头转述小满称棚子建起后她会找不到家。",
        "条件",
        "石头（转述自小满）",
        ["T06", "T07"],
    ),
    ("TR-C02-01", "城市西边的森林火灾已经持续七天。", "正在发生", None, ["T08"]),
    ("TR-C02-01", "当天风向已经改变。", "已发生", None, ["T08"]),
    ("TR-C02-01", "任青是社区卫生站的医生。", "正在发生", None, ["T10"]),
    (
        "TR-C02-01",
        "门边黑点落到塑料袋上后没有散开，并长出细小绒毛。",
        "已发生",
        None,
        ["T22", "T23"],
    ),
    ("TR-C02-02", "任青提出病人、老人和孩子单列。", "计划", "任青", ["T22"]),
    (
        "TR-C03-01",
        "许栀是嘉原二中的队长，也是高二三班班长。",
        "正在发生",
        None,
        ["T08"],
    ),
    ("TR-C03-01", "许栀的能力是让一小片地面暂时失去摩擦。", "正在发生", None, ["T08"]),
    ("TR-C03-01", "沈礼确认自己能记住每个动作回声。", "正在发生", "沈礼", ["T27"]),
    ("TR-C04-02", "梁守诚认为子女把阿梅当作贼来防备。", "推测", "梁守诚", ["T01"]),
    ("TR-C04-02", "阿梅说自己的母亲也曾中风。", "已发生", "阿梅", ["T06", "T07"]),
    (
        "TR-C04-02",
        "阿梅说自己在母亲接受照护的第一个月每天查看监控。",
        "已发生",
        "阿梅",
        ["T07"],
    ),
    (
        "TR-C04-02",
        "阿梅把新钥匙放到茶几上后，梁守诚当场沉下了脸。",
        "已发生",
        None,
        ["T11", "T12"],
    ),
    ("TR-C04-02", "卫生间门口地砖边缘有一道新的磕痕。", "已发生", None, ["T14"]),
    (
        "TR-C04-02",
        "梁穗和梁川都无法每天夜里守在父亲床边。",
        "否定",
        None,
        ["T18", "T19"],
    ),
    (
        "TR-C04-03",
        "梁守诚提出，关于照顾他的人选，他有一票决定权。",
        "条件",
        "梁守诚",
        ["T11", "T12"],
    ),
    ("TR-C04-03", "梁穗正在把夜间情况分成三档写入照护约定。", "正在发生", None, ["T17"]),
    ("TR-C05-01", "已有商旅把银子夹进文书后获准放行。", "已发生", None, ["T18"]),
    ("TR-C05-01", "也有商旅不肯，货箱被掀开、货物散落一地。", "已发生", None, ["T18"]),
    ("TR-C05-02", "妇人说明箱内装有丈夫骨灰和婆母交给她的婚书。", "已发生", "妇人", ["T06"]),
    ("TR-C05-02", "黄老板决定留下等待。", "已发生", None, ["T16", "T17"]),
    ("TR-C05-02", "胡嫂也决定留下等待。", "已发生", None, ["T18"]),
    ("TR-C05-02", "陆青梧认为选择更快道路的人不欠自己。", "已发生", "陆青梧", ["T22"]),
    (
        "TR-C05-03",
        "莫巡检已经到达关口，并核看了妇人的路引和婚书封皮。",
        "已发生",
        None,
        ["T01"],
    ),
    ("TR-C05-03", "陆青梧提出不打开箱口，先对箱子称重。", "计划", "陆青梧", ["T03"]),
    ("TR-C05-03", "陆青梧承诺自己若算错重量，就留下三箱茶抵罚。", "承诺", "陆青梧", ["T07"]),
    ("TR-C05-03", "两名守门婆子已经隔着布帘摸验箱体。", "已发生", None, ["T11"]),
    ("TR-C05-03", "漆皮箱上的关印没有被风吹开。", "否定", None, ["T22"]),
]
FORBIDDEN_OLD_WORDING = {
    "清早六点，南塘村晒谷场上出现了一双红布鞋。",
    "任青提出病人、老人和孩子单独优先。",
    "也有商旅因拒绝塞银而被开箱，货物散落一地。",
    "妇人箱上的关印仍未打开。",
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
    actual_cases = [
        row["case_id"]
        for row in source_rows
        if row["case_id"].startswith(("TR-C01-", "TR-C02-", "TR-C03-", "TR-C04-", "TR-C05-"))
    ]
    if actual_cases != EXPECTED_CASES:
        raise AssertionError(f"Wave3 source case set/order drift: {actual_cases}")
    if any(case_id not in txx_index for case_id in EXPECTED_CASES):
        raise AssertionError("Wave3 case missing from frozen Txx map")

    target_texts: dict[str, str] = {}
    for case_id in EXPECTED_CASES:
        source_row = source_index[case_id]
        txx_row = txx_index[case_id]
        source_bytes = (REPO / source_row["source_file"]).read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        target_text = source_text[source_row["target_start"] : source_row["target_end"]]
        target_texts[case_id] = target_text
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
        raise AssertionError("Wave3 must contain the fixed 12 cases in order")
    if len({row["case_id"] for row in gold_rows}) != 12:
        raise AssertionError("Wave3 case IDs are not unique")

    all_fact_ids: set[str] = set()
    fact_index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in gold_rows:
        case_id = row["case_id"]
        if row.get("dataset_status") != "CANDIDATE_NOT_YET_APPROVED":
            raise AssertionError(f"bad candidate status: {case_id}")
        if "expected_fact_count" in row:
            raise AssertionError(f"Wave3 must not pre-register a fact count: {case_id}")
        units = txx_index[case_id]["target_units"]
        valid_ids = [unit["id"] for unit in units]
        target_text = target_texts[case_id]
        for fact in row.get("facts", []):
            fact_id = fact.get("fact_id")
            if not isinstance(fact_id, str) or not fact_id.startswith(case_id + "-F"):
                raise AssertionError(f"bad fact ID: {fact_id}")
            if fact_id in all_fact_ids:
                raise AssertionError(f"duplicate fact ID: {fact_id}")
            all_fact_ids.add(fact_id)
            sentence = fact.get("fact_sentence")
            if not isinstance(sentence, str) or not sentence.strip():
                raise AssertionError(f"empty fact: {fact_id}")
            if (case_id, sentence) in fact_index:
                raise AssertionError(f"duplicate fact sentence: {case_id}: {sentence}")
            fact_index[(case_id, sentence)] = fact
            if fact.get("status") not in STATUS_ONTOLOGY:
                raise AssertionError(f"bad status: {fact_id}")
            if fact.get("speaker") is not None and not isinstance(fact["speaker"], str):
                raise AssertionError(f"bad speaker: {fact_id}")
            evidence_ids = fact.get("evidence_ids")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise AssertionError(f"empty evidence: {fact_id}")
            if len(evidence_ids) != len(set(evidence_ids)):
                raise AssertionError(f"duplicate evidence: {fact_id}")
            try:
                positions = [valid_ids.index(evidence_id) for evidence_id in evidence_ids]
            except ValueError as exc:
                raise AssertionError(f"foreign evidence ID: {fact_id}") from exc
            if positions != sorted(positions):
                raise AssertionError(f"evidence order drift: {fact_id}")
            if positions != list(range(positions[0], positions[-1] + 1)):
                raise AssertionError(f"non-contiguous evidence: {fact_id}")
            for hidden_name in HIDDEN_NAMES.get(case_id, set()):
                if hidden_name in sentence or hidden_name == fact.get("speaker"):
                    raise AssertionError(f"hidden name leaked: {fact_id}")
            claimed = sentence + "\n" + (fact.get("speaker") or "")
            for name in ENTITY_NAMES_AND_ROLES:
                if name in claimed and name not in target_text:
                    raise AssertionError(f"name/role lacks target anchor: {fact_id}: {name}")

    for case_id, sentence, status, speaker, evidence_ids in EXPECTED_CORRECTIONS:
        fact = fact_index.get((case_id, sentence))
        if fact is None:
            raise AssertionError(f"missing terminal-review correction: {case_id}: {sentence}")
        if (fact["status"], fact["speaker"], fact["evidence_ids"]) != (status, speaker, evidence_ids):
            raise AssertionError(f"terminal-review correction drift: {case_id}: {sentence}")
    if FORBIDDEN_OLD_WORDING & {sentence for _, sentence in fact_index}:
        raise AssertionError("superseded Wave3 wording remains")

    diagnostics = read_jsonl(DIAGNOSTIC)
    if [row["case_id"] for row in diagnostics] != ["TR-C02-02", "TR-C05-02"]:
        raise AssertionError("Wave3 entity diagnostics must be the fixed two cases")
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
        "# TRAIN36 Wave3 Gold 草稿审阅版",
        "",
        "当前身份：**CANDIDATE_NOT_YET_APPROVED**。本文只覆盖 C01—C05 的 12 题，不是正式 gold，也不授权训练。",
        "",
        "共同 gold 只使用目标段可见姓名或角色称呼；C02-02 与 C05-02 的整章姓名还原另见诊断旁证。",
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
    print(f"wave3_cases={len(gold_rows)}")
    print(f"wave3_facts={sum(len(row['facts']) for row in gold_rows)}")
    print(f"entity_diagnostics={len(diagnostics)}")


if __name__ == "__main__":
    main()
