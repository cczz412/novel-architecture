#!/usr/bin/env python3
"""第64道件A：为冻结样本补齐本地正文上下文，不自动判语义。"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/Z64_三窗回包语义抽查与差距表_20260720"
FROZEN = REPORT / "抽样方案与冻结名单.json"
EVIDENCE_FILE = (
    ROOT
    / "TEMP/z61_chatgpt_pro_three_window_returns_20260720/raw/诡秘之主_第01-50章_逐章证据条目.md"
)
CHAPTER_DIR = ROOT / "TEMP/X批材料包_20260716/books/X01_诡秘之主/chapters"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize(value: str) -> str:
    return re.sub(r"[\s　]+", "", value).replace("·", ".")


def semantic_chars(value: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", value)


def bigrams(value: str) -> set[str]:
    value = semantic_chars(value)
    return {value[index : index + 2] for index in range(max(0, len(value) - 1))}


def similarity(query: str, candidate: str) -> float:
    query_clean = semantic_chars(query)
    candidate_clean = semantic_chars(candidate)
    if not query_clean or not candidate_clean:
        return 0.0
    qgrams, cgrams = bigrams(query_clean), bigrams(candidate_clean)
    union = qgrams | cgrams
    jaccard = len(qgrams & cgrams) / len(union) if union else 0.0
    seq = difflib.SequenceMatcher(None, query_clean, candidate_clean).ratio()
    return round(0.65 * jaccard + 0.35 * seq, 6)


def load_chapters() -> dict[int, dict[str, Any]]:
    chapters: dict[int, dict[str, Any]] = {}
    for chapter in range(1, 51):
        matches = sorted(CHAPTER_DIR.glob(f"{chapter:04d}_第{chapter}章_*.txt"))
        if len(matches) != 1:
            raise ValueError(f"第{chapter}章正文文件数量不是1：{matches}")
        path = matches[0]
        text = path.read_text(encoding="utf-8")
        paragraphs = [
            {"line": line_no, "text": line.strip()}
            for line_no, line in enumerate(text.splitlines(), start=1)
            if line.strip()
        ]
        chapters[chapter] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha256_file(path),
            "text": text,
            "normalized": normalize(text),
            "paragraphs": paragraphs,
        }
    return chapters


def load_evidence_map() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    pattern = re.compile(r"^- \*\*(E-(\d{2})-\d{2,3})\*\*\s+(.*)$")
    for line_no, line in enumerate(EVIDENCE_FILE.read_text(encoding="utf-8").splitlines(), start=1):
        match = pattern.match(line)
        if not match:
            continue
        eid, chapter, statement = match.groups()
        result[eid] = {
            "id": eid,
            "chapter": int(chapter),
            "statement": statement,
            "source_line": line_no,
        }
    if len(result) != 1761:
        raise ValueError(f"证据索引不是1761条：{len(result)}")
    return result


def top_contexts(
    query: str, chapter_numbers: list[int], chapters: dict[int, dict[str, Any]], limit: int = 3
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for chapter in chapter_numbers:
        for paragraph in chapters[chapter]["paragraphs"]:
            score = similarity(query, paragraph["text"])
            if score <= 0:
                continue
            candidates.append(
                {
                    "chapter": chapter,
                    "line": paragraph["line"],
                    "score": score,
                    "text": paragraph["text"],
                }
            )
    candidates.sort(key=lambda row: (-row["score"], row["chapter"], row["line"]))
    return candidates[:limit]


def exact_locations(
    quote: str, chapter_numbers: list[int], chapters: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    needle = normalize(quote.strip("“”\"'：:。！？；，, "))
    if not needle:
        return []
    locations: list[dict[str, Any]] = []
    for chapter in chapter_numbers:
        if needle not in chapters[chapter]["normalized"]:
            continue
        matching_lines = [
            paragraph["line"]
            for paragraph in chapters[chapter]["paragraphs"]
            if needle in normalize(paragraph["text"])
        ]
        locations.append({"chapter": chapter, "lines": matching_lines})
    return locations


def statement_claim(statement: str) -> str:
    return re.sub(r"（来源：.*?）\s*$", "", statement).strip()


def quoted_fragments(text: str) -> list[str]:
    fragments = re.findall(r"[“\"]([^”\"\n]{4,})[”\"]", text)
    seen: set[str] = set()
    result: list[str] = []
    for fragment in fragments:
        fragment = fragment.strip()
        if fragment and fragment not in seen:
            result.append(fragment)
            seen.add(fragment)
    return result


def cited_chapters(text: str) -> list[int]:
    chapters: set[int] = set()
    for match in re.finditer(r"第(\d+)(?:[—～~-](\d+))?章", text):
        start, end = int(match.group(1)), match.group(2)
        if end:
            chapters.update(range(start, int(end) + 1))
        else:
            chapters.add(start)
    return sorted(chapter for chapter in chapters if 1 <= chapter <= 50)


def build_event_row(row: dict[str, Any], chapters: dict[int, dict[str, Any]]) -> dict[str, Any]:
    chapter = int(row["chapter"])
    quote = str(row.get("source_quote") or "")
    semantic_keys = (
        "story_line",
        "delta",
        "direct_cause",
        "future_use",
        "trigger_condition",
        "trigger_action",
        "reader_expectation",
        "payoff_test",
        "condition",
        "consequence",
        "scope_exception",
    )
    query = " ".join(str(row.get(key) or "") for key in (*semantic_keys, "source_quote"))
    return {
        "review_id": f"{row['population']}:{row['id']}",
        "population": row["population"],
        "source_id": row["id"],
        "chapter": chapter,
        "record_type": row["type"],
        "claim": {
            key: row.get(key)
            for key in (*semantic_keys, "status", "type_state", "assertion", "related_ids")
            if key in row
        },
        "citation": quote,
        "citation_exact_locations": exact_locations(quote, [chapter], chapters),
        "context_candidates": top_contexts(query, [chapter], chapters),
        "questions": {
            "citation_semantic_support": None,
            "type_delta_cause_correct": None,
            "verdict_note": None,
        },
    }


def build_evidence_row(row: dict[str, Any], chapters: dict[int, dict[str, Any]]) -> dict[str, Any]:
    chapter = int(row["chapter"])
    claim = statement_claim(row["statement"])
    return {
        "review_id": f"{row['population']}:{row['id']}",
        "population": row["population"],
        "source_id": row["id"],
        "chapter": chapter,
        "record_type": "逐章事实证据",
        "claim": claim,
        "citation": f"第{chapter}章正文",
        "citation_exact_locations": [],
        "context_candidates": top_contexts(claim, [chapter], chapters),
        "questions": {
            "citation_semantic_support": None,
            "type_delta_cause_correct": "not_applicable",
            "verdict_note": None,
        },
    }


def build_package_row(
    row: dict[str, Any],
    chapters: dict[int, dict[str, Any]],
    evidence_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    eids = row.get("evidence_ids", [])
    evidence_refs: list[dict[str, Any]] = []
    chapter_numbers: set[int] = set()
    for eid in eids:
        evidence = dict(evidence_map[eid])
        evidence["claim"] = statement_claim(evidence["statement"])
        evidence["context_candidates"] = top_contexts(
            evidence["claim"], [evidence["chapter"]], chapters, limit=2
        )
        evidence_refs.append(evidence)
        chapter_numbers.add(int(evidence["chapter"]))
    chapter_numbers.update(cited_chapters(row["text"]))
    if row.get("chapter"):
        chapter_numbers.add(int(row["chapter"]))
    if not chapter_numbers:
        chapter_numbers.update(range(1, 51))
    quotes: list[dict[str, Any]] = []
    for quote in quoted_fragments(row["text"]):
        locations = exact_locations(quote, sorted(chapter_numbers), chapters)
        if not locations and len(chapter_numbers) < 50:
            locations = exact_locations(quote, list(range(1, 51)), chapters)
        quotes.append({"quote": quote, "exact_locations": locations})
    return {
        "review_id": row["unit_id"],
        "population": "两步法新增包" if row["package"] == "two_step" else "一步直出新增包",
        "source_id": row["unit_id"],
        "category": row["category"],
        "sampling_band": row["sampling_band"],
        "chapter": row.get("chapter"),
        "title": row["title"],
        "claim": row["text"],
        "evidence_ids": eids,
        "evidence_refs": evidence_refs,
        "embedded_quotes": quotes,
        "context_candidates": top_contexts(
            row["text"], sorted(chapter_numbers), chapters, limit=4
        ),
        "questions": {
            "citation_semantic_support": None,
            "type_delta_cause_correct": None,
            "verdict_note": None,
        },
    }


def build_payload() -> dict[str, Any]:
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    chapters = load_chapters()
    evidence_map = load_evidence_map()
    rows: list[dict[str, Any]] = []
    for population, samples in frozen["samples"].items():
        for sample in samples:
            if "type" in sample:
                rows.append(build_event_row(sample, chapters))
            elif population == "50章窗3逐章证据":
                rows.append(build_evidence_row(sample, chapters))
            else:
                rows.append(build_package_row(sample, chapters, evidence_map))
    exact_summary = defaultdict(lambda: {"rows": 0, "with_exact_quote": 0, "without_exact_quote": 0})
    for row in rows:
        bucket = exact_summary[row["population"]]
        bucket["rows"] += 1
        if "citation_exact_locations" in row:
            checked = bool(row["citation"])
            exact = bool(row["citation_exact_locations"])
        else:
            embedded = row.get("embedded_quotes", [])
            checked = bool(embedded)
            exact = checked and all(item["exact_locations"] for item in embedded)
        if checked and exact:
            bucket["with_exact_quote"] += 1
        elif checked:
            bucket["without_exact_quote"] += 1
    return {
        "task": "第64道件A语义复核工作底稿",
        "created_at": "2026-07-20",
        "model_api_calls": 0,
        "automatic_judgment": "none",
        "frozen_sample_path": str(FROZEN.relative_to(ROOT)),
        "frozen_sample_sha256": sha256_file(FROZEN),
        "chapter_window": {"start": 1, "end": 50, "count": 50},
        "chapter_files_sha256": {
            str(chapter): chapters[chapter]["sha256"] for chapter in range(1, 51)
        },
        "row_count": len(rows),
        "mechanical_quote_summary": dict(exact_summary),
        "rows": rows,
    }


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# 第64道件A｜语义复核工作底稿",
        "",
        "机器只负责把正文与引用搬到同一行，不替人判对错。所有判词填写在 JSON 同名行的 `questions` 中。",
        "",
        f"- 抽查主单元：{payload['row_count']}",
        "- 正文窗口：X01 第1—50章",
        "- 模型 API 调用：0",
        "",
        "## 机械短引定位概览",
        "",
        "| 材料 | 样本 | 带短引且全部可原样定位 | 带短引但至少一处未原样定位 |",
        "|---|---:|---:|---:|",
    ]
    for name, item in payload["mechanical_quote_summary"].items():
        lines.append(
            f"| {name} | {item['rows']} | {item['with_exact_quote']} | {item['without_exact_quote']} |"
        )
    lines.extend(["", "来源：Codex", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=REPORT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = build_payload()
    if args.check:
        print(json.dumps({"row_count": payload["row_count"], "summary": payload["mechanical_quote_summary"]}, ensure_ascii=False, sort_keys=True))
        return 0
    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / "语义复核工作底稿.json"
    md_path = args.out / "语义复核工作底稿.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_md(payload), encoding="utf-8")
    print(f"JSON={json_path}")
    print(f"JSON_SHA256={sha256_file(json_path)}")
    print(f"MD={md_path}")
    print(f"MD_SHA256={sha256_file(md_path)}")
    print(json.dumps(payload["mechanical_quote_summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
