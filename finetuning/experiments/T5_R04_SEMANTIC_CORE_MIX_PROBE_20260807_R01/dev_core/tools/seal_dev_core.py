#!/usr/bin/env python3
"""Seal DEV_CORE semantic gold and zero-training question arms without inference."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


DEV = Path(__file__).resolve().parents[1]
RUN1 = DEV / "r02_run_1"
RUN2 = DEV / "r02_run_2"
OUT = DEV / "sealed_r01"
GOLD = DEV / "CORE_GOLD_CANONICAL_R01.jsonl"
FILES = ["SOURCE_WINDOWS.jsonl", "A_CORE_QUESTIONS.jsonl", "C2_CORE_QUESTIONS.jsonl", "CORE_GOLD_WORKSHEET.jsonl"]


def canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(canon(row) + "\n" for row in rows), encoding="utf-8")


def message(row: dict[str, Any], role: str) -> str:
    return next(item["content"] for item in row["messages"] if item["role"] == role)


def section(text: str, start: str, end: str | None) -> str:
    value = text.split(start, 1)[1]
    if end:
        value = value.split(end, 1)[0]
    return value.strip("\n")


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def strip_local_ids(text: str) -> str:
    if text == "（无）":
        return ""
    markers = list(re.finditer(r"\[(?:B|T)\d{2}\]", text))
    if not markers or markers[0].start() != 0:
        raise SystemExit(f"HARD_STOP malformed local ID block: {text[:80]}")
    parts = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        body = text[marker.end() : end]
        if index + 1 < len(markers) and body.endswith("\n"):
            body = body[:-1]
        parts.append(body)
    return "".join(parts)


def citation_question(row: dict[str, Any]) -> dict[str, Any]:
    system = (
        "你是中文小说核心事实抽取器。B/T 编号只表示原文位置。"
        "只判断编号负责区表达了哪些会影响后续大纲的核心事实，并为每条事实选择最小覆盖的编号。"
        "输出严格 JSON：{\"facts\":[{\"fact_sentence\":\"...\",\"evidence_ids\":[\"T01\"]}]}。"
        "不要输出状态、说话人或解释。编号上文和未编号下文只帮助理解，不能单独贡献答案。"
    )
    return {
        "case_id": row["case_id"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": message(row, "user")}],
    }


def main() -> None:
    two_run = []
    for name in FILES:
        left = RUN1 / name
        right = RUN2 / name
        same = left.read_bytes() == right.read_bytes()
        two_run.append({"file": name, "run_1_sha256": sha(left), "run_2_sha256": sha(right), "byte_identical": same})
    if not all(row["byte_identical"] for row in two_run):
        raise SystemExit("HARD_STOP DEV_CORE two-run mismatch")

    source = read_jsonl(RUN1 / "SOURCE_WINDOWS.jsonl")
    a = read_jsonl(RUN1 / "A_CORE_QUESTIONS.jsonl")
    c2 = read_jsonl(RUN1 / "C2_CORE_QUESTIONS.jsonl")
    gold = read_jsonl(GOLD)
    if not (len(source) == len(a) == len(c2) == len(gold) == 48):
        raise SystemExit("HARD_STOP denominator mismatch")
    ids = [row["case_id"] for row in source]
    if ids != [row["case_id"] for row in a] or ids != [row["case_id"] for row in c2] or ids != [row["case_id"] for row in gold]:
        raise SystemExit("HARD_STOP case order mismatch")

    source_identity_failures = []
    c2_visible_counts = []
    for src, ar, cr in zip(source, a, c2):
        au = message(ar, "user")
        cu = message(cr, "user")
        expected_a = (
            f"【题号】\n{src['case_id']}\n\n【只读上文】\n{src['bridge_text'] or '（无）'}\n\n"
            f"【本段负责区】\n{src['target_text']}\n\n【只读下文】\n{src['following_text'] or '（无）'}"
        )
        a_bridge = section(au, "【只读上文】\n", "\n\n【本段负责区】")
        a_target = section(au, "【本段负责区】\n", "\n\n【只读下文】")
        a_follow = section(au, "【只读下文】\n", None)
        c_bridge = section(cu, "【编号只读上文】\n", "\n\n【编号负责区】")
        c_target = section(cu, "【编号负责区】\n", "\n\n【未编号只读下文】")
        c_follow = section(cu, "【未编号只读下文】\n", None)
        checks = {
            "a_full_exact": au == expected_a,
            "c_bridge": compact(strip_local_ids(c_bridge)) == compact(src["bridge_text"]),
            "c_target": compact(strip_local_ids(c_target)) == compact(src["target_text"]),
            "c_follow": compact(c_follow) == compact(src["following_text"] or "（无）"),
        }
        if not all(checks.values()):
            source_identity_failures.append({"case_id": src["case_id"], "checks": checks})
        c2_visible_counts.append(len(re.findall(r"\[(?:B|T)\d{2}\]", cu)))
    if source_identity_failures:
        raise SystemExit(f"HARD_STOP A/C2 source mismatch: {source_identity_failures[:2]}")

    fact_count = 0
    empty_count = 0
    forbidden = []
    for row in gold:
        if set(row) != {"case_id", "fact_sentences"} or not isinstance(row["fact_sentences"], list):
            raise SystemExit(f"HARD_STOP gold schema: {row.get('case_id')}")
        if not row["fact_sentences"]:
            empty_count += 1
        for fact in row["fact_sentences"]:
            if not isinstance(fact, str) or not fact.strip():
                raise SystemExit(f"HARD_STOP empty fact: {row['case_id']}")
            if re.search(r"\b(?:B|T)\d{2}\b|evidence|speaker|status", fact, re.I):
                forbidden.append({"case_id": row["case_id"], "fact": fact})
            fact_count += 1
    if forbidden:
        raise SystemExit(f"HARD_STOP representation leaked into CORE gold: {forbidden[:2]}")

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "DEV_CORE_SOURCE_WINDOWS.jsonl", source)
    write_jsonl(OUT / "Z00_BASE_A_CORE_QUESTIONS.jsonl", a)
    write_jsonl(OUT / "Z01_BASE_C2_CORE_QUESTIONS.jsonl", c2)
    write_jsonl(OUT / "Z02C_C2_CORE_WITH_CITATION_QUESTIONS.jsonl", [citation_question(row) for row in c2])
    write_jsonl(OUT / "CORE_GOLD.jsonl", gold)
    write_jsonl(OUT / "A_CORE_GOLD.jsonl", gold)
    write_jsonl(OUT / "C2_CORE_GOLD.jsonl", gold)

    receipt = {
        "schema_version": "t5-r04-dev-core-seal-receipt-v1",
        "status": "PASS_DEV_CORE_CONSTRUCTION_READY_FOR_STAGE_TICKET",
        "window_count": 48,
        "author_count": len({row["author"] for row in source}),
        "book_count": len({row["book_id"] for row in source}),
        "chapter_count": len({row["chapter_sha256"] for row in source}),
        "core_fact_count": fact_count,
        "zero_fact_window_count": empty_count,
        "a_c2_same_source_48_of_48": True,
        "a_c2_same_canonical_gold_48_of_48": True,
        "gold_contains_position_ids": False,
        "selection_used_gold": False,
        "selection_used_old_model_outputs": False,
        "representation_specific_question_adjustments": 0,
        "visible_id_count": {
            "mean": sum(c2_visible_counts) / len(c2_visible_counts),
            "min": min(c2_visible_counts),
            "max": max(c2_visible_counts),
        },
        "two_run_selection": two_run,
        "artifacts": {},
        "known_gap": "Z03 cross-unit matched subarms require a separate support-position audit; CORE gold intentionally contains semantics only.",
    }
    for path in sorted(OUT.iterdir()):
        if path.name == "DEV_CORE_SEAL_RECEIPT.json":
            continue
        receipt["artifacts"][path.name] = {"sha256": sha(path), "bytes": path.stat().st_size}
    (OUT / "DEV_CORE_SEAL_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
