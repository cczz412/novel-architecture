#!/usr/bin/env python3
"""第64道件B/C：机械核算本地链、20/50窗和两种七类包的密度。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import z64_freeze_samples as freeze


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/Z64_三窗回包语义抽查与差距表_20260720"
RAW = ROOT / "TEMP/z61_chatgpt_pro_three_window_returns_20260720/raw"
LOCAL122 = ROOT / "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/02_verify/valid_records.json"
GOLD = ROOT / "reports/Z56_金标双轨分层与全链体检_20260719/第3章结构层金标v1.1.json"
Z57_SCORE = ROOT / "reports/Z57_稳定语义身份解耦与全链后半_20260719/第3章当章层诚实成绩单.json"
AUDIT_A = REPORT / "件A_分层样本逐条语义复核.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def file_metrics(path: Path) -> dict[str, Any]:
    text = read_text(path)
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "characters": len(text),
        "non_whitespace_characters": len(re.sub(r"\s+", "", text)),
        "heading_count": len(re.findall(r"^#{1,6}\s+", text, flags=re.M)),
        "table_row_count": len(re.findall(r"^\|.*\|\s*$", text, flags=re.M)),
    }


def event_chapter(record: dict[str, Any]) -> int:
    if "_source_chapter" in record:
        return int(record["_source_chapter"])
    value = str(record.get("章节位置", ""))
    match = re.search(r"第0*(\d+)章", value)
    if not match:
        raise ValueError(f"事件缺章号：{record.get('id')}")
    return int(match.group(1))


def record_stats(records: list[dict[str, Any]], chapter_end: int) -> dict[str, Any]:
    records = [row for row in records if 1 <= event_chapter(row) <= chapter_end]
    by_type = Counter(str(row["type"]) for row in records)
    by_chapter = Counter(event_chapter(row) for row in records)
    per_chapter = [by_chapter[chapter] for chapter in range(1, chapter_end + 1)]
    anchor_counts: list[int] = []
    for row in records:
        anchors = row.get("anchors", [])
        anchor_counts.append(len(anchors))
    return {
        "chapters": chapter_end,
        "records": len(records),
        "records_by_type": {key: by_type[key] for key in "ABCD"},
        "records_per_chapter": {
            "mean": round(statistics.mean(per_chapter), 4),
            "median": round(statistics.median(per_chapter), 4),
            "min": min(per_chapter),
            "max": max(per_chapter),
            "values": {str(chapter): by_chapter[chapter] for chapter in range(1, chapter_end + 1)},
        },
        "anchor_count": sum(anchor_counts),
        "anchors_per_record_mean": round(statistics.mean(anchor_counts), 4),
    }


def load_event20() -> list[dict[str, Any]]:
    text = read_text(RAW / "novel_ch01-20_events_and_setting_cards.md")
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.S)
    if not match:
        raise ValueError("20章事件文件缺JSON块")
    return json.loads(match.group(1))["records"]


def evidence_stats() -> dict[str, Any]:
    rows = freeze.load_evidence50()
    by_chapter = Counter(int(row["chapter"]) for row in rows)
    per_chapter = [by_chapter[chapter] for chapter in range(1, 51)]
    return {
        "records": len(rows),
        "unique_ids": len({row["id"] for row in rows}),
        "chapters": 50,
        "records_per_chapter": {
            "mean": round(statistics.mean(per_chapter), 4),
            "median": round(statistics.median(per_chapter), 4),
            "min": min(per_chapter),
            "max": max(per_chapter),
            "values": {str(chapter): by_chapter[chapter] for chapter in range(1, 51)},
        },
    }


def package_category_metrics(package: str) -> dict[str, Any]:
    units = freeze.load_package_units(package)
    categories: dict[str, Any] = {}
    for category, rows in units.items():
        evidence_refs = sum(len(row["evidence_ids"]) for row in rows)
        categories[category] = {
            "primary_units": len(rows),
            "field_claims": sum(int(row["field_claim_count"]) for row in rows),
            "evidence_id_references": evidence_refs,
            "units_with_evidence_ids": sum(bool(row["evidence_ids"]) for row in rows),
        }
    base = freeze.TWO_STEP if package == "two_step" else freeze.ONE_STEP
    files: dict[str, Any] = {}
    for category, filename in freeze.CATEGORY_FILES.items():
        if category == "逻辑句":
            filename = "06_逻辑句_因果用.md" if package == "two_step" else "06_逻辑句_因果兑现.md"
        assert filename is not None
        files[category] = file_metrics(base / filename)
    return {
        "package": package,
        "categories": categories,
        "totals": {
            "primary_units": sum(item["primary_units"] for item in categories.values()),
            "field_claims": sum(item["field_claims"] for item in categories.values()),
            "evidence_id_references": sum(item["evidence_id_references"] for item in categories.values()),
            "bytes": sum(item["bytes"] for item in files.values()),
            "non_whitespace_characters": sum(item["non_whitespace_characters"] for item in files.values()),
        },
        "files": files,
    }


def gold_items() -> list[dict[str, Any]]:
    data = json.loads(read_text(GOLD))
    result: list[dict[str, Any]] = []
    for item in data["layered_items"]:
        part = next(part for part in item["parts"] if part["layer"] == "当章可知")
        result.append({"gold_id": item["item_id"], "claim": part["claim"]})
    return result


def main_payload() -> dict[str, Any]:
    local = json.loads(read_text(LOCAL122))["records"]
    event50 = json.loads(read_text(freeze.EVENT50))["records"]
    event20 = load_event20()
    z57 = json.loads(read_text(Z57_SCORE))
    audit_a = json.loads(read_text(AUDIT_A))
    two = package_category_metrics("two_step")
    one = package_category_metrics("one_step")

    expected_cloud = {
        "two_step": {
            "世界观设定": 143,
            "人物档案": 72,
            "地点档案": 99,
            "人物关系": 59,
            "每章大纲": 50,
            "逻辑句": 94,
            "每章写法": 50,
        },
        "one_step": {
            "世界观设定": 60,
            "人物档案": 55,
            "地点档案": 70,
            "人物关系": 45,
            "每章大纲": 50,
            "逻辑句": 56,
            "每章写法": 50,
        },
    }
    measured_primary = {
        package: {
            category: data[package]["categories"][category]["primary_units"]
            for category in expected_cloud[package]
        }
        for package in ("two_step", "one_step")
        for data in [{"two_step": two, "one_step": one}]
    }
    if measured_primary != expected_cloud:
        raise ValueError(
            "云端初判数量未通过本地复核："
            + json.dumps(
                {"measured": measured_primary, "expected": expected_cloud},
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    return {
        "task": "第64道件B/C机械母数",
        "created_at": "2026-07-20",
        "model_api_calls": 0,
        "event_sets": {
            "local_current_122": record_stats(local, 20),
            "return_20_window": record_stats(event20, 20),
            "return_50_window_full": record_stats(event50, 50),
            "return_50_window_first20": record_stats(event50, 20),
        },
        "evidence_50_window": evidence_stats(),
        "document_windows": {
            "deep_analysis_20": file_metrics(RAW / "第1-20章深度拆解.md"),
            "deep_analysis_50": file_metrics(RAW / "第1-50章深度拆解.md"),
            "events_20": file_metrics(RAW / "novel_ch01-20_events_and_setting_cards.md"),
            "events_50_json": file_metrics(freeze.EVENT50),
            "evidence_50": file_metrics(freeze.EVIDENCE50),
            "thought_trace_evidence50": file_metrics(RAW / "50小说证据抽取任务思考过程.md"),
            "thought_trace_events50": file_metrics(RAW / "50小说事件记录与设定思考过程.md"),
            "thought_trace_deep50": file_metrics(RAW / "50小说拆解分析请求思考过程.md"),
        },
        "package_comparison": {"two_step": two, "one_step": one},
        "cloud_count_verification": {
            "expected": expected_cloud,
            "measured": measured_primary,
            "verdict": "pass",
        },
        "gold_chapter3": {
            "items": gold_items(),
            "sha256": sha256_file(GOLD),
        },
        "local_z57_baseline": {
            "strict_complete_extraction": z57["summary"]["strict_complete_extraction"],
            "strict_total": z57["summary"]["on_chapter_gold_total"],
            "shadow_recalled": z57["summary"]["shadow_recalled"],
            "sha256": sha256_file(Z57_SCORE),
        },
        "semantic_sample_summary": audit_a["summary"],
        "protected_sources": {
            "local_current_122": {"path": str(LOCAL122.relative_to(ROOT)), "sha256": sha256_file(LOCAL122)},
            "gold_v1_1": {"path": str(GOLD.relative_to(ROOT)), "sha256": sha256_file(GOLD)},
            "z57_score": {"path": str(Z57_SCORE.relative_to(ROOT)), "sha256": sha256_file(Z57_SCORE)},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=REPORT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = main_payload()
    if args.check:
        print(
            json.dumps(
                {
                    "event_sets": payload["event_sets"],
                    "cloud_count_verification": payload["cloud_count_verification"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "件B_C_机械母数.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"JSON={path}")
    print(f"JSON_SHA256={sha256_file(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
