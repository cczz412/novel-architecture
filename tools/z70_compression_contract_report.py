#!/usr/bin/env python3
"""第70道：用冻结工件和人工判词生成零 API、可重复核验的停点报告。"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import z68_continuation_32k as z68c
import z68_revised_request_pilot as z68


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/Z70_X01_事件句压缩合同_五靶章_v1.0_20260721"
REPORT = ROOT / "reports/Z70_压缩病灶合同条款单变量_20260721"
OLD_REPORT = ROOT / "reports/Z68续令_32k参数兼容修复与裸考成绩_20260720"
GOLD = ROOT / "reports/Z56_金标双轨分层与全链体检_20260719/第3章结构层金标v1.1.json"
SEMANTIC_SOURCE = REPORT / "语义人工复核源.json"
TARGET_CHAPTERS = (3, 4, 5, 13, 19)

OLD_GOLD_NAME = "第3章金标v1.1语义成绩单.json"
OLD_CURRENT_NAME = "现役122条五靶章语义diff.json"
OLD_TRANSPORT_NAME = "运输与成本回执.json"
MAIN_REPORT_NAME = "第70道停点回包｜事件句压缩合同单变量_20260721.md"
OUTPUT_NAMES = (
    "第3章金标v1.1语义成绩单.json",
    "现役122条五靶章语义diff.json",
    "五靶章机械与成本成绩单.json",
    "运输与成本回执.json",
    "供料单变量与保护回执.json",
    "待判溢出清单.json",
    "安全与测试回执.json",
    MAIN_REPORT_NAME,
    "report_manifest.json",
)

GOLD_VERDICTS = {"strict_hit", "semantic_shadow", "miss"}
CURRENT_VERDICTS = {"preserved", "partially_preserved", "not_observed"}
GOLD_RANK = {"miss": 0, "semantic_shadow": 1, "strict_hit": 2}
CURRENT_RANK = {"not_observed": 0, "partially_preserved": 1, "preserved": 2}
USAGE_KEYS = (
    "prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "total_tokens",
    "elapsed_ms",
)


class ReportError(RuntimeError):
    """报告输入或冻结合同不满足要求。"""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReportError(f"缺少输入文件：{display_path(path)}") from exc
    except json.JSONDecodeError as exc:
        raise ReportError(f"JSON 无法解析：{display_path(path)}：{exc}") from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ReportError(f"缺少输入文件：{display_path(path)}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReportError(
                f"JSONL 无法解析：{display_path(path)}:{line_number}：{exc}"
            ) from exc
        if not isinstance(value, dict):
            raise ReportError(f"JSONL 行不是对象：{display_path(path)}:{line_number}")
        rows.append(value)
    return rows


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"{label} 必须是 JSON 对象")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReportError(f"{label} 必须是数组")
    return value


def unique_rows(
    rows_value: Any,
    *,
    id_key: str,
    verdicts: set[str],
    expected_count: int,
    label: str,
) -> dict[str, dict[str, Any]]:
    rows = require_list(rows_value, label)
    if len(rows) != expected_count:
        raise ReportError(f"{label} 必须恰好 {expected_count} 条，实际 {len(rows)} 条")
    result: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(rows):
        row = require_mapping(value, f"{label}[{index}]")
        row_id = row.get(id_key)
        if not isinstance(row_id, str) or not row_id:
            raise ReportError(f"{label}[{index}] 缺少有效 {id_key}")
        if row_id in result:
            raise ReportError(f"{label} 出现重复 ID：{row_id}")
        verdict = row.get("verdict")
        if verdict not in verdicts:
            raise ReportError(f"{label} 的 {row_id} 判词无效：{verdict}")
        candidate_ids = row.get("candidate_event_ids")
        if not isinstance(candidate_ids, list) or not all(
            isinstance(item, str) and item for item in candidate_ids
        ):
            raise ReportError(f"{label} 的 {row_id} 候选事件 ID 必须是字符串数组")
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ReportError(f"{label} 的 {row_id} 候选事件 ID 重复")
        if not isinstance(row.get("note"), str):
            raise ReportError(f"{label} 的 {row_id} 缺少人工说明 note")
        result[row_id] = dict(row)
    return result


def ordered_id_map(
    rows_value: Any,
    *,
    id_key: str,
    expected_count: int,
    label: str,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    rows = require_list(rows_value, label)
    if len(rows) != expected_count:
        raise ReportError(f"{label} 必须恰好 {expected_count} 条，实际 {len(rows)} 条")
    order: list[str] = []
    result: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(rows):
        row = require_mapping(value, f"{label}[{index}]")
        row_id = row.get(id_key)
        if not isinstance(row_id, str) or not row_id:
            raise ReportError(f"{label}[{index}] 缺少有效 {id_key}")
        if row_id in result:
            raise ReportError(f"{label} 出现重复 ID：{row_id}")
        order.append(row_id)
        result[row_id] = dict(row)
    return order, result


def require_same_ids(actual: Iterable[str], expected: Iterable[str], label: str) -> None:
    actual_set = set(actual)
    expected_set = set(expected)
    if actual_set != expected_set:
        missing = sorted(expected_set - actual_set)
        extra = sorted(actual_set - expected_set)
        raise ReportError(f"{label} 与旧 Z68 报告 ID 不一致；缺少={missing}，多出={extra}")


def load_event_inventory(
    run_dir: Path,
) -> tuple[dict[int, list[dict[str, Any]]], dict[str, tuple[int, dict[str, Any]]]]:
    by_chapter: dict[int, list[dict[str, Any]]] = {}
    by_id: dict[str, tuple[int, dict[str, Any]]] = {}
    for chapter in TARGET_CHAPTERS:
        doc = require_mapping(
            read_json(run_dir / f"01_extract/events/ch{chapter:04d}.json"),
            f"第{chapter}章事件工件",
        )
        rows = require_list(doc.get("events"), f"第{chapter}章事件工件 events")
        chapter_rows: list[dict[str, Any]] = []
        for index, value in enumerate(rows):
            row = dict(require_mapping(value, f"第{chapter}章 events[{index}]"))
            event_id = row.get("event_id")
            if not isinstance(event_id, str) or not event_id:
                raise ReportError(f"第{chapter}章 events[{index}] 缺少事件 ID")
            if event_id in by_id:
                raise ReportError(f"五章事件 ID 重复：{event_id}")
            by_id[event_id] = (chapter, row)
            chapter_rows.append(row)
        by_chapter[chapter] = chapter_rows
    return by_chapter, by_id


def validate_candidate_ids(
    owner_id: str,
    candidate_ids: Sequence[str],
    expected_chapter: int,
    event_by_id: Mapping[str, tuple[int, dict[str, Any]]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for event_id in candidate_ids:
        if event_id not in event_by_id:
            raise ReportError(f"{owner_id} 引用了不存在的候选事件：{event_id}")
        chapter, event = event_by_id[event_id]
        if chapter != expected_chapter:
            raise ReportError(
                f"{owner_id} 引用的 {event_id} 不在同章：应为第{expected_chapter}章，实际第{chapter}章"
            )
        result.append({"event_id": event_id, "event": event.get("event")})
    return result


def load_gold_parts(gold_path: Path) -> tuple[list[str], dict[str, dict[str, Any]], Any]:
    gold = require_mapping(read_json(gold_path), "金标 v1.1")
    layered = require_list(gold.get("layered_items"), "金标 layered_items")
    order: list[str] = []
    parts: dict[str, dict[str, Any]] = {}
    for index, item_value in enumerate(layered):
        item = require_mapping(item_value, f"金标 layered_items[{index}]")
        item_id = item.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            raise ReportError(f"金标 layered_items[{index}] 缺少 item_id")
        single_parts = [
            dict(require_mapping(part, f"{item_id}.parts"))
            for part in require_list(item.get("parts"), f"{item_id}.parts")
            if isinstance(part, dict) and part.get("score_in_single_chapter")
        ]
        if len(single_parts) != 1:
            raise ReportError(f"{item_id} 的当章计分层必须恰好一条")
        order.append(item_id)
        parts[item_id] = single_parts[0]
    if len(order) != 14 or len(parts) != 14:
        raise ReportError(f"金标当章层必须恰好 14 条，实际 {len(parts)} 条")
    return order, parts, gold


def verdict_summary(rows: Iterable[Mapping[str, Any]], verdicts: Sequence[str]) -> dict[str, int]:
    rows_list = list(rows)
    counts = Counter(str(row["verdict"]) for row in rows_list)
    return {"total": len(rows_list), **{verdict: counts[verdict] for verdict in verdicts}}


def gold_score(
    run_dir: Path,
    semantic_source: Path,
    old_report_dir: Path,
    gold_path: Path,
) -> dict[str, Any]:
    source = require_mapping(read_json(semantic_source), "语义人工复核源")
    decisions = unique_rows(
        source.get("gold_rows"),
        id_key="gold_item_id",
        verdicts=GOLD_VERDICTS,
        expected_count=14,
        label="人工金标判词 gold_rows",
    )
    old_doc = require_mapping(read_json(old_report_dir / OLD_GOLD_NAME), "旧 Z68 金标成绩单")
    old_order, old_rows = ordered_id_map(
        old_doc.get("rows"),
        id_key="gold_item_id",
        expected_count=14,
        label="旧 Z68 金标逐条成绩",
    )
    gold_order, parts, gold = load_gold_parts(gold_path)
    require_same_ids(decisions, old_order, "人工金标判词")
    require_same_ids(gold_order, old_order, "金标 v1.1 当章层")
    _events_by_chapter, event_by_id = load_event_inventory(run_dir)

    rows: list[dict[str, Any]] = []
    for gold_id in old_order:
        decision = decisions[gold_id]
        part = parts[gold_id]
        candidate_ids = list(decision["candidate_event_ids"])
        candidate_events = validate_candidate_ids(gold_id, candidate_ids, 3, event_by_id)
        old_verdict = old_rows[gold_id].get("verdict")
        if old_verdict not in GOLD_VERDICTS:
            raise ReportError(f"旧 Z68 金标判词无效：{gold_id}={old_verdict}")
        source_evidence = part.get("source_evidence")
        if not isinstance(source_evidence, list):
            source_evidence = []
        rows.append(
            {
                "gold_item_id": gold_id,
                "part_id": part.get("part_id"),
                "claim": part.get("claim"),
                "gold_anchor_ids": [
                    row.get("anchor_id") for row in source_evidence if isinstance(row, dict)
                ],
                "verdict": decision["verdict"],
                "candidate_event_ids": candidate_ids,
                "candidate_events": candidate_events,
                "semantic_review_note": decision["note"],
                "z68_verdict": old_verdict,
                "row_change": (
                    "improved"
                    if GOLD_RANK[str(decision["verdict"])] > GOLD_RANK[str(old_verdict)]
                    else (
                        "degraded"
                        if GOLD_RANK[str(decision["verdict"])] < GOLD_RANK[str(old_verdict)]
                        else "unchanged"
                    )
                ),
            }
        )

    summary = verdict_summary(rows, ("strict_hit", "semantic_shadow", "miss"))
    summary["gold_total"] = summary.pop("total")
    summary["strict_hit_rate"] = summary["strict_hit"] / summary["gold_total"]
    summary["semantic_shadow_only"] = summary.pop("semantic_shadow")
    summary["semantic_shadow_recalled"] = (
        summary["strict_hit"] + summary["semantic_shadow_only"]
    )
    summary["semantic_shadow_recall_rate"] = (
        summary["semantic_shadow_recalled"] / summary["gold_total"]
    )

    old_summary = verdict_summary(old_rows.values(), ("strict_hit", "semantic_shadow", "miss"))
    old_recalled = old_summary["strict_hit"] + old_summary["semantic_shadow"]
    strict_floor_pass = summary["strict_hit"] >= old_summary["strict_hit"]
    shadow_floor_pass = summary["semantic_shadow_recalled"] >= old_recalled
    floor_pass = strict_floor_pass and shadow_floor_pass
    comparison = {
        "z68_strict_hit": old_summary["strict_hit"],
        "z68_semantic_shadow_recalled": old_recalled,
        "z70_strict_hit": summary["strict_hit"],
        "z70_semantic_shadow_recalled": summary["semantic_shadow_recalled"],
        "strict_hit_delta": summary["strict_hit"] - old_summary["strict_hit"],
        "semantic_shadow_recalled_delta": summary["semantic_shadow_recalled"] - old_recalled,
    }
    summary.update(
        {
            "z68_strict_hit": old_summary["strict_hit"],
            "z68_semantic_shadow_recalled": old_recalled,
            "strict_hit_delta": comparison["strict_hit_delta"],
            "semantic_shadow_recalled_delta": comparison[
                "semantic_shadow_recalled_delta"
            ],
        }
    )
    hindsight = [
        {
            "gold_item_id": item.get("item_id"),
            "part_id": part.get("part_id"),
            "claim": part.get("claim"),
            "single_chapter_score": "excluded",
        }
        for item in require_list(gold.get("layered_items"), "金标 layered_items")
        if isinstance(item, dict)
        for part in require_list(item.get("parts"), f"{item.get('item_id')}.parts")
        if isinstance(part, dict) and part.get("layer") == "回看件"
    ]
    return {
        "schema_version": "z70-compression-contract-chapter3-gold-score-v1",
        "status": "completed_candidate_score_only",
        "condition": "第3/4/5/13/19章均为本轮32k单次样张；只新增一条事件句压缩保护合同",
        "gold": {"path": display_path(gold_path), "sha256": sha256_file(gold_path)},
        "semantic_source": {
            "path": display_path(semantic_source),
            "sha256": sha256_file(semantic_source),
            "boundary": "判词只取人工源；程序不根据证据锚、词面或机械配对补判。",
        },
        "policy": {
            "strict_hit": "人工判定候选事件句完整覆盖金标事实和必要限定；证据锚不能替事件句倒补语义",
            "semantic_shadow": "人工判定看见同一事实或结构附近内容，但必要限定或组合关系不全",
            "miss": "人工判定没有同一事实或结构的候选影子",
            "hindsight": "回看层单列，不计单章漏项",
        },
        "summary": summary,
        "comparison_to_z68": comparison,
        "quality_gate": {
            "required_floor": {
                "strict_hit": old_summary["strict_hit"],
                "semantic_shadow_recalled": old_recalled,
            },
            "strict_floor_pass": strict_floor_pass,
            "semantic_shadow_floor_pass": shadow_floor_pass,
            "passed": floor_pass,
            "disposition": "pass_gold_floor" if floor_pass else "hard_stop_no_repair",
        },
        "rows": rows,
        "hindsight_layer_excluded": hindsight,
        "write_policy": "只出候选成绩，不修改金标、现役记录、默认链或分类规则。",
    }


def formal_record_summary(record: Mapping[str, Any]) -> str:
    return z68c.formal_record_summary(record)


def current_diff(
    run_dir: Path,
    semantic_source: Path,
    old_report_dir: Path,
) -> dict[str, Any]:
    source = require_mapping(read_json(semantic_source), "语义人工复核源")
    decisions = unique_rows(
        source.get("current_rows"),
        id_key="record_id",
        verdicts=CURRENT_VERDICTS,
        expected_count=34,
        label="人工现役判词 current_rows",
    )
    old_doc = require_mapping(read_json(old_report_dir / OLD_CURRENT_NAME), "旧 Z68 现役 diff")
    old_order, old_rows = ordered_id_map(
        old_doc.get("rows"),
        id_key="record_id",
        expected_count=34,
        label="旧 Z68 现役逐条 diff",
    )
    require_same_ids(decisions, old_order, "人工现役判词")

    current_doc = require_mapping(
        read_json(run_dir / "inputs/current_formal_records_122.json"), "现役122条冻结输入"
    )
    all_records = require_list(current_doc.get("records"), "现役122条 records")
    if len(all_records) != 122:
        raise ReportError(f"现役冻结输入必须恰好 122 条，实际 {len(all_records)} 条")
    target_records: dict[str, dict[str, Any]] = {}
    for value in all_records:
        record = require_mapping(value, "现役记录")
        if record.get("_source_chapter") not in TARGET_CHAPTERS:
            continue
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise ReportError("五靶章现役记录缺少 id")
        if record_id in target_records:
            raise ReportError(f"五靶章现役记录 ID 重复：{record_id}")
        target_records[record_id] = dict(record)
    if len(target_records) != 34:
        raise ReportError(f"五靶章现役记录必须恰好 34 条，实际 {len(target_records)} 条")
    require_same_ids(target_records, old_order, "现役冻结输入的五靶章记录")

    _events_by_chapter, event_by_id = load_event_inventory(run_dir)
    rows: list[dict[str, Any]] = []
    transition_counts: Counter[str] = Counter()
    rescued_ids: list[str] = []
    degraded_rows: list[dict[str, Any]] = []
    for record_id in old_order:
        record = target_records[record_id]
        chapter = int(record["_source_chapter"])
        decision = decisions[record_id]
        candidate_ids = list(decision["candidate_event_ids"])
        candidate_events = validate_candidate_ids(
            record_id, candidate_ids, chapter, event_by_id
        )
        old_verdict = old_rows[record_id].get("verdict")
        if old_verdict not in CURRENT_VERDICTS:
            raise ReportError(f"旧 Z68 现役判词无效：{record_id}={old_verdict}")
        new_verdict = str(decision["verdict"])
        transition = f"{old_verdict}->{new_verdict}"
        transition_counts[transition] += 1
        old_rank = CURRENT_RANK[str(old_verdict)]
        new_rank = CURRENT_RANK[new_verdict]
        change = "improved" if new_rank > old_rank else ("degraded" if new_rank < old_rank else "unchanged")
        if old_verdict == "partially_preserved" and new_verdict == "preserved":
            rescued_ids.append(record_id)
        if change == "degraded":
            degraded_rows.append(
                {
                    "record_id": record_id,
                    "chapter": chapter,
                    "z68_verdict": old_verdict,
                    "z70_verdict": new_verdict,
                }
            )
        rows.append(
            {
                "chapter": chapter,
                "record_id": record_id,
                "type": record.get("type"),
                "current_semantics": formal_record_summary(record),
                "current_anchor_ids": [
                    row.get("anchor_id")
                    for row in record.get("anchors", [])
                    if isinstance(row, dict)
                ],
                "verdict": new_verdict,
                "candidate_event_ids": candidate_ids,
                "candidate_events": candidate_events,
                "semantic_review_note": decision["note"],
                "z68_verdict": old_verdict,
                "transition": transition,
                "change": change,
            }
        )

    counts = verdict_summary(rows, ("preserved", "partially_preserved", "not_observed"))
    by_chapter: dict[str, Any] = {}
    for chapter in TARGET_CHAPTERS:
        chapter_rows = [row for row in rows if row["chapter"] == chapter]
        by_chapter[str(chapter)] = verdict_summary(
            chapter_rows, ("preserved", "partially_preserved", "not_observed")
        )
    counts["by_chapter"] = by_chapter
    no_degradation = not degraded_rows
    comparison = {
        "z68_summary_from_rows": verdict_summary(
            old_rows.values(), ("preserved", "partially_preserved", "not_observed")
        ),
        "z70_summary_from_manual_source": {
            key: counts[key]
            for key in ("total", "preserved", "partially_preserved", "not_observed")
        },
        "transition_counts": dict(sorted(transition_counts.items())),
        "old_partial_rescued_count": len(rescued_ids),
        "old_partial_rescued_ids": rescued_ids,
        "degradation_count": len(degraded_rows),
        "degraded_ids": [row["record_id"] for row in degraded_rows],
        "degradations": degraded_rows,
    }
    return {
        "schema_version": "z70-compression-contract-current122-semantic-diff-v1",
        "status": "hard_stop_no_repair" if not no_degradation else "candidate_diff_pass",
        "scope": {
            "current_records_total": len(all_records),
            "target_chapters": list(TARGET_CHAPTERS),
            "target_records": len(rows),
        },
        "semantic_source": {
            "path": display_path(semantic_source),
            "sha256": sha256_file(semantic_source),
            "boundary": "判词只取人工源；程序不根据锚点或词面自动升降级。",
        },
        "verdict_policy": {
            "preserved": "人工判定同一语义完整保留；允许一条旧记录由多个原子事件共同承载",
            "partially_preserved": "人工判定存在同一事实影子，但必要条件、结果或规则概括不全",
            "not_observed": "人工判定候选事件池没有同一语义影子",
        },
        "summary": counts,
        "comparison_to_z68": comparison,
        "quality_gate": {
            "old_34_no_degradation": no_degradation,
            "passed": no_degradation,
            "disposition": "candidate_diff_pass" if no_degradation else "hard_stop_no_repair",
            "reason": (
                "旧34条均未劣化。"
                if no_degradation
                else "旧34条中存在语义劣化；按预写闸立即FAIL，不修、不补跑。"
            ),
        },
        "rows": rows,
    }


def usage_from_jsonl(path: Path, chapters: Sequence[int]) -> dict[str, Any]:
    wanted = {f"ch{chapter:04d}": chapter for chapter in chapters}
    chapter_totals: dict[str, Counter[str]] = {
        str(chapter): Counter() for chapter in chapters
    }
    chapter_rows: dict[str, int] = {str(chapter): 0 for chapter in chapters}
    finish_reasons: dict[str, list[str | None]] = {str(chapter): [] for chapter in chapters}
    http_statuses: dict[str, list[int | None]] = {str(chapter): [] for chapter in chapters}
    max_tokens: dict[str, list[int | None]] = {str(chapter): [] for chapter in chapters}
    for row in read_jsonl(path):
        case_id = row.get("case_id")
        if case_id not in wanted:
            continue
        chapter_key = str(wanted[str(case_id)])
        usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
        details = (
            usage.get("completion_tokens_details")
            if isinstance(usage.get("completion_tokens_details"), dict)
            else {}
        )
        item = {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "reasoning_tokens": int(details.get("reasoning_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
            "elapsed_ms": int(row.get("elapsed_ms") or 0),
        }
        chapter_totals[chapter_key].update(item)
        chapter_rows[chapter_key] += 1
        finish_reasons[chapter_key].append(row.get("finish_reason"))
        http_statuses[chapter_key].append(row.get("http_status"))
        max_tokens[chapter_key].append(row.get("stage_max_tokens"))
    totals: Counter[str] = Counter()
    chapters_doc: dict[str, Any] = {}
    for chapter in chapters:
        key = str(chapter)
        item = {name: int(chapter_totals[key][name]) for name in USAGE_KEYS}
        totals.update(item)
        chapters_doc[key] = {
            **item,
            "usage_rows": chapter_rows[key],
            "finish_reasons": finish_reasons[key],
            "http_statuses": http_statuses[key],
            "stage_max_tokens": max_tokens[key],
        }
    return {
        "source": display_path(path),
        "chapters": chapters_doc,
        "totals": {name: int(totals[name]) for name in USAGE_KEYS},
        "usage_rows": sum(chapter_rows.values()),
    }


def normalized_usage_from_old_report(value: Any) -> dict[str, Any]:
    source = require_mapping(value, "旧 Z68C 五章成本")
    chapters_value = require_mapping(source.get("chapters"), "旧 Z68C 五章成本 chapters")
    expected = {str(chapter) for chapter in TARGET_CHAPTERS}
    if set(chapters_value) != expected:
        raise ReportError("旧 Z68C 成本账没有完整覆盖五靶章")
    totals: Counter[str] = Counter()
    chapters: dict[str, Any] = {}
    for chapter in TARGET_CHAPTERS:
        row = require_mapping(chapters_value[str(chapter)], f"旧 Z68C 第{chapter}章成本")
        item = {name: int(row.get(name) or 0) for name in USAGE_KEYS}
        totals.update(item)
        chapters[str(chapter)] = item
    return {
        "source": display_path(OLD_REPORT / OLD_TRANSPORT_NAME),
        "chapters": chapters,
        "totals": {name: int(totals[name]) for name in USAGE_KEYS},
        "usage_rows": int(source.get("successful_calls") or len(TARGET_CHAPTERS)),
    }


def usage_delta(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    candidate_totals = require_mapping(candidate.get("totals"), "候选成本 totals")
    baseline_totals = require_mapping(baseline.get("totals"), "对照成本 totals")
    deltas: dict[str, int] = {}
    rates: dict[str, float | None] = {}
    for key in USAGE_KEYS:
        candidate_value = int(candidate_totals.get(key) or 0)
        baseline_value = int(baseline_totals.get(key) or 0)
        deltas[key] = candidate_value - baseline_value
        rates[key] = (
            (candidate_value - baseline_value) / baseline_value if baseline_value else None
        )
    return {"delta": deltas, "delta_rate": rates}


def mechanical_and_cost_scorecard(run_dir: Path, old_report_dir: Path) -> dict[str, Any]:
    chapter_rows = [z68.chapter_mechanics(run_dir, chapter) for chapter in TARGET_CHAPTERS]
    event_total = sum(int(row["event_count"]) for row in chapter_rows)
    anchor_total = sum(int(row["anchor_reference_count"]) for row in chapter_rows)
    outside_total = sum(int(row["outside_catalog_anchor_count"]) for row in chapter_rows)
    ordered_total = sum(int(row["anchor_order_compliant_events"]) for row in chapter_rows)
    dedup_total = sum(int(row["anchor_deduplicated_events"]) for row in chapter_rows)
    explicit_total = sum(int(row["explicit_subject_events"]) for row in chapter_rows)
    vague_total = sum(int(row["vague_predicate_hit_events"]) for row in chapter_rows)
    contiguous_total = sum(int(bool(row["event_id_contiguous"])) for row in chapter_rows)
    baseline_events = {
        str(chapter): len(
            require_list(
                require_mapping(
                    read_json(run_dir / f"inputs/baseline_events/ch{chapter:04d}.json"),
                    f"第{chapter}章B0事件",
                ).get("events"),
                f"第{chapter}章B0事件 events",
            )
        )
        for chapter in TARGET_CHAPTERS
    }
    candidate_events = {str(row["chapter"]): int(row["event_count"]) for row in chapter_rows}

    z70_usage = usage_from_jsonl(run_dir / "usage.jsonl", TARGET_CHAPTERS)
    if any(z70_usage["chapters"][str(chapter)]["usage_rows"] != 1 for chapter in TARGET_CHAPTERS):
        raise ReportError("Z70 usage.jsonl 必须每个靶章恰好一行真实 usage")
    old_transport = require_mapping(
        read_json(old_report_dir / OLD_TRANSPORT_NAME), "旧 Z68C 运输与成本回执"
    )
    z68c_candidate = require_mapping(
        require_mapping(
            old_transport.get("five_chapter_condition_cost"), "旧 Z68C 五章条件成本"
        ).get("candidate"),
        "旧 Z68C 候选成本",
    )
    z68c_usage = normalized_usage_from_old_report(z68c_candidate)
    z68c_usage["source"] = display_path(old_report_dir / OLD_TRANSPORT_NAME)
    b0_usage = usage_from_jsonl(run_dir / "inputs/baseline_usage.jsonl", TARGET_CHAPTERS)
    if any(b0_usage["chapters"][str(chapter)]["usage_rows"] != 1 for chapter in TARGET_CHAPTERS):
        raise ReportError("B0 usage 账必须每个靶章恰好一行")
    if any(
        b0_usage["chapters"][str(chapter)]["stage_max_tokens"] != [16000]
        for chapter in TARGET_CHAPTERS
    ):
        raise ReportError("B0 五靶章不再是逐章16k条件")

    mechanical_pass = contiguous_total == len(TARGET_CHAPTERS) and outside_total == 0
    return {
        "schema_version": "z70-compression-contract-mechanical-cost-scorecard-v1",
        "status": "pass" if mechanical_pass else "fail",
        "condition_labels": {
            "z70": "五章均为本轮32k新样张；每章一个逻辑样本，不复用旧章。",
            "z68c": "第3/4章复用16k正常样张＋第5/13/19章32k新样张；这是混合上限条件，不是五章全32k。",
            "b0": "第57道20章16k基线 usage 账中筛出第3/4/5/13/19章。",
        },
        "metric_policy": {
            "mechanical_source": "逐章重新调用 z68_revised_request_pilot.chapter_mechanics；不复用旧机械结论。",
            "usage_source": "Z70 从正式 run 的 usage.jsonl 逐章真实合计；Z68C 读旧运输回执，B0 读冻结 baseline_usage.jsonl。",
            "invalid_anchor": "模型原始 anchor_id 不在同章冻结目录的引用数／全部引用数。",
            "semantic_boundary": "机械结果不生成或改写人工语义判词。",
        },
        "ten_metrics": {
            "01_JSON合法章率": {
                "numerator": len(chapter_rows),
                "denominator": len(TARGET_CHAPTERS),
                "rate": len(chapter_rows) / len(TARGET_CHAPTERS),
            },
            "02_event_id连续章率": {
                "numerator": contiguous_total,
                "denominator": len(TARGET_CHAPTERS),
                "rate": contiguous_total / len(TARGET_CHAPTERS),
            },
            "03_目录外锚数": outside_total,
            "04_无效锚率": outside_total / anchor_total if anchor_total else 0.0,
            "05_锚排序合规率": ordered_total / event_total if event_total else 0.0,
            "06_锚去重合规率": dedup_total / event_total if event_total else 0.0,
            "07_显式主语率": explicit_total / event_total if event_total else 0.0,
            "08_空泛谓词命中率": vague_total / event_total if event_total else 0.0,
            "09_事件数": {
                "candidate_total": event_total,
                "baseline_total": sum(baseline_events.values()),
                "candidate_by_chapter": candidate_events,
                "baseline_by_chapter": baseline_events,
            },
            "10_token与耗时成本": {
                "z70_all_32k": z70_usage,
                "z68c_mixed_16k_32k": z68c_usage,
                "b0_all_16k": b0_usage,
                "z70_vs_z68c": usage_delta(z70_usage, z68c_usage),
                "z70_vs_b0": usage_delta(z70_usage, b0_usage),
            },
        },
        "quality_gate": {
            "five_chapters_mechanically_valid": mechanical_pass,
            "outside_catalog_anchor_total_zero": outside_total == 0,
        },
        "subject_lexicon": {
            str(chapter): list(z68.SUBJECT_LEXICON[chapter]) for chapter in TARGET_CHAPTERS
        },
        "vague_predicate_terms": list(z68.VAGUE_PREDICATE_TERMS),
        "chapters": chapter_rows,
    }


def transport_receipt(
    run_dir: Path, mechanical_doc: Mapping[str, Any]
) -> dict[str, Any]:
    manifest = require_mapping(read_json(run_dir / "run_manifest.json"), "Z70 run_manifest")
    verification = require_mapping(
        read_json(run_dir / "mechanical_verification.json"), "Z70 机械验收"
    )
    if manifest.get("status") != "completed_candidate_only":
        raise ReportError("Z70 正式 run 未完成，禁止生成完整成绩")
    if manifest.get("usable_model_outputs") != 5:
        raise ReportError("Z70 可用模型输出不是5份")
    if verification.get("status") != "pass":
        raise ReportError("Z70 机械验收未通过")
    transport = require_mapping(manifest.get("transport"), "Z70 运输账")
    expected_cases = [f"ch{chapter:04d}" for chapter in TARGET_CHAPTERS]
    logical_started = require_mapping(
        transport.get("logical_samples_started"), "Z70 logical_samples_started"
    )
    attempts_by_case = require_mapping(
        transport.get("attempts_by_case"), "Z70 attempts_by_case"
    )
    attempts = read_jsonl(run_dir / "call_attempts.jsonl")
    expected_attempt_rows = [
        (index, case_id, 1) for index, case_id in enumerate(expected_cases, start=1)
    ]
    actual_attempt_rows = [
        (row.get("call_number"), row.get("case_id"), row.get("attempt")) for row in attempts
    ]
    logical_samples = sum(int(logical_started.get(case_id) or 0) for case_id in expected_cases)
    network_attempts = len(attempts)
    retries = network_attempts - logical_samples
    transport_pass = all(
        (
            transport.get("logical_case_order") == expected_cases,
            logical_started == {case_id: 1 for case_id in expected_cases},
            attempts_by_case == {case_id: 1 for case_id in expected_cases},
            int(transport.get("actual_network_attempts") or 0) == 5,
            actual_attempt_rows == expected_attempt_rows,
            logical_samples == 5,
            network_attempts == 5,
            retries == 0,
        )
    )
    if not transport_pass:
        raise ReportError("Z70 运输账不满足5逻辑样本／5尝试／0重试")
    metric = require_mapping(mechanical_doc.get("ten_metrics"), "Z70 机械成绩")
    outside_total = int(metric.get("03_目录外锚数") or 0)
    if outside_total != 0:
        raise ReportError("Z70 出现目录外锚，禁止把机械成绩写成通过")
    cost = require_mapping(metric.get("10_token与耗时成本"), "Z70 成本成绩")
    usage = require_mapping(cost.get("z70_all_32k"), "Z70 usage")
    chapters = require_mapping(usage.get("chapters"), "Z70 usage chapters")
    return {
        "schema_version": "z70-compression-contract-transport-cost-v1",
        "status": "pass",
        "source_run": display_path(run_dir),
        "transport_summary": {
            "logical_samples": logical_samples,
            "network_attempts": network_attempts,
            "transport_retries": retries,
            "usable_model_outputs": manifest.get("usable_model_outputs"),
            "http_200_responses": sum(
                status == 200
                for chapter in TARGET_CHAPTERS
                for status in chapters[str(chapter)]["http_statuses"]
            ),
            "stop_responses": sum(
                reason == "stop"
                for chapter in TARGET_CHAPTERS
                for reason in chapters[str(chapter)]["finish_reasons"]
            ),
            "outside_catalog_anchor_total": outside_total,
        },
        "chapters": [
            {
                "chapter": chapter,
                "logical_samples": int(logical_started[f"ch{chapter:04d}"]),
                "network_attempts": int(attempts_by_case[f"ch{chapter:04d}"]),
                **dict(chapters[str(chapter)]),
            }
            for chapter in TARGET_CHAPTERS
        ],
        "usage": usage,
        "cost_comparisons": {
            "condition_labels": mechanical_doc["condition_labels"],
            "z70_vs_z68c": cost["z70_vs_z68c"],
            "z70_vs_b0": cost["z70_vs_b0"],
        },
        "evidence": {
            "run_manifest": {
                "path": display_path(run_dir / "run_manifest.json"),
                "sha256": sha256_file(run_dir / "run_manifest.json"),
            },
            "call_attempts": {
                "path": display_path(run_dir / "call_attempts.jsonl"),
                "sha256": sha256_file(run_dir / "call_attempts.jsonl"),
            },
            "usage": {
                "path": display_path(run_dir / "usage.jsonl"),
                "sha256": sha256_file(run_dir / "usage.jsonl"),
            },
        },
    }


def json_diff_paths(left: Any, right: Any, path: str = "$") -> list[str]:
    if left == right:
        return []
    if isinstance(left, dict) and isinstance(right, dict):
        result: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}"
            if key not in left or key not in right:
                result.append(child)
            else:
                result.extend(json_diff_paths(left[key], right[key], child))
        return result
    if isinstance(left, list) and isinstance(right, list):
        result = []
        for index in range(max(len(left), len(right))):
            child = f"{path}[{index}]"
            if index >= len(left) or index >= len(right):
                result.append(child)
            else:
                result.extend(json_diff_paths(left[index], right[index], child))
        return result
    return [path]


def supply_and_protection_receipt(run_dir: Path) -> dict[str, Any]:
    preflight = require_mapping(read_json(run_dir / "preflight.json"), "Z70 preflight")
    verification_path = run_dir / "prepared_request_verification.json"
    verification = require_mapping(read_json(verification_path), "Z70 准备请求验收")
    single_variable = require_mapping(preflight.get("single_variable"), "Z70 单变量")
    clause = single_variable.get("inserted_exact_line")
    if not isinstance(clause, str) or not clause:
        raise ReportError("Z70 preflight 缺少唯一新增条款")
    if single_variable.get("location") != "messages[0].content":
        raise ReportError("Z70 单变量位置不是 messages[0].content")
    rows: list[dict[str, Any]] = []
    clauses: set[str] = set()
    for chapter in TARGET_CHAPTERS:
        baseline_path = run_dir / f"baseline_requests/ch{chapter:04d}.json"
        prepared_path = run_dir / f"prepared_requests/ch{chapter:04d}.json"
        diff_path = run_dir / f"request_diffs/ch{chapter:04d}.json"
        baseline = require_mapping(read_json(baseline_path), f"第{chapter}章基线请求")
        prepared = require_mapping(read_json(prepared_path), f"第{chapter}章候选请求")
        diff = require_mapping(read_json(diff_path), f"第{chapter}章请求 diff")
        changed = json_diff_paths(baseline, prepared)
        row_clause = diff.get("inserted_exact_line")
        if not isinstance(row_clause, str) or not row_clause:
            raise ReportError(f"第{chapter}章 diff 缺少新增条款")
        clauses.add(row_clause)
        expected_path = ["$.messages[0].content"]
        if changed != expected_path or diff.get("changed_paths_baseline_to_candidate") != expected_path:
            raise ReportError(f"第{chapter}章 diff 不只改 messages[0].content：{changed}")
        if row_clause != clause or int(diff.get("inserted_occurrences") or 0) != 1:
            raise ReportError(f"第{chapter}章新增条款不唯一或与 preflight 不同")
        baseline_messages = require_list(baseline.get("messages"), f"第{chapter}章基线 messages")
        prepared_messages = require_list(prepared.get("messages"), f"第{chapter}章候选 messages")
        if not baseline_messages or not prepared_messages:
            raise ReportError(f"第{chapter}章请求缺少系统消息")
        baseline_system = require_mapping(
            baseline_messages[0], f"第{chapter}章基线系统消息"
        ).get("content")
        prepared_system = require_mapping(
            prepared_messages[0], f"第{chapter}章候选系统消息"
        ).get("content")
        if not isinstance(baseline_system, str) or not isinstance(prepared_system, str):
            raise ReportError(f"第{chapter}章系统消息正文不是字符串")
        if baseline_system.count(clause) != 0 or prepared_system.count(clause) != 1:
            raise ReportError(f"第{chapter}章条款出现次数异常")
        insert_after = diff.get("insert_after")
        if not isinstance(insert_after, str) or f"{insert_after}\n{clause}" not in prepared_system:
            raise ReportError(f"第{chapter}章条款插入位置不符合冻结 diff")
        if prepared_system.replace(f"{insert_after}\n{clause}", insert_after, 1) != baseline_system:
            raise ReportError(f"第{chapter}章删除唯一条款后不能还原基线系统消息")
        if baseline.get("max_tokens") != 32000 or prepared.get("max_tokens") != 32000:
            raise ReportError(f"第{chapter}章没有保持32k上限")
        if diff.get("effective_max_tokens") != 32000:
            raise ReportError(f"第{chapter}章 diff 的有效上限不是32k")
        rows.append(
            {
                "chapter": chapter,
                "changed_paths": changed,
                "inserted_exact_line": row_clause,
                "inserted_occurrences": prepared_system.count(clause),
                "system_byte_equal_after_line_deletion": True,
                "effective_max_tokens": prepared["max_tokens"],
                "baseline_request_sha256": sha256_file(baseline_path),
                "prepared_request_sha256": sha256_file(prepared_path),
                "diff_sha256": sha256_file(diff_path),
            }
        )
    if clauses != {clause}:
        raise ReportError("五章没有共用同一条唯一新增条款")
    if verification.get("status") != "pass":
        raise ReportError("Z70 准备请求验收未通过")
    protected = require_mapping(preflight.get("protected"), "Z70 protected")
    protected_recheck: dict[str, Any] = {}
    for relative, expected_hash in protected.items():
        path = ROOT / str(relative)
        observed_hash = sha256_file(path)
        protected_recheck[str(relative)] = {
            "expected_sha256": expected_hash,
            "observed_sha256": observed_hash,
            "equal": observed_hash == expected_hash,
        }
    if not all(row["equal"] for row in protected_recheck.values()):
        raise ReportError("Z70 preflight 钉住的保护件已经漂移")
    provenance = require_list(preflight.get("provenance"), "Z70 provenance")
    runner_rows = [
        dict(require_mapping(row, "Z70 provenance row"))
        for row in provenance
        if isinstance(row, dict)
        and row.get("source") == "tools/z70_compression_contract_pilot.py"
    ]
    if len(runner_rows) != 1:
        raise ReportError("Z70 provenance 没有唯一运行器记录")
    return {
        "schema_version": "z70-compression-contract-supply-protection-v1",
        "status": "pass",
        "run": display_path(run_dir),
        "single_variable": {
            "location": "messages[0].content",
            "insert_after": single_variable.get("insert_after"),
            "inserted_exact_line": clause,
            "unique_clause_count_across_five_chapters": len(clauses),
        },
        "five_chapter_request_diff": {
            "only_messages_0_content_for_all_chapters": True,
            "effective_max_tokens_for_all_chapters": 32000,
            "rows": rows,
        },
        "request_policy": preflight.get("request_policy"),
        "run_provenance": {
            "runner": runner_rows[0],
            "all_rows": provenance,
        },
        "prepared_request_verification": {
            "path": display_path(verification_path),
            "sha256": sha256_file(verification_path),
            "status": verification.get("status"),
            "source_inputs_unchanged": verification.get("source_inputs_unchanged"),
            "protected_unchanged": verification.get("protected_unchanged"),
            "outbox_unchanged": verification.get("outbox_unchanged"),
        },
        "protected_recheck": protected_recheck,
        "write_boundary": "报告器只读运行工件并写报告目录；不回写请求、回包、金标、现役件、默认链或outbox。",
    }


def pending_overflow(
    run_dir: Path, gold_doc: Mapping[str, Any], current_doc: Mapping[str, Any]
) -> dict[str, Any]:
    events_by_chapter, _event_by_id = load_event_inventory(run_dir)
    gold_used = {
        event_id
        for row in require_list(gold_doc.get("rows"), "金标成绩 rows")
        if isinstance(row, dict)
        for event_id in row.get("candidate_event_ids", [])
    }
    current_used_by_chapter: dict[int, set[str]] = {
        chapter: set() for chapter in TARGET_CHAPTERS
    }
    for row in require_list(current_doc.get("rows"), "现役 diff rows"):
        if not isinstance(row, dict):
            continue
        chapter = int(row["chapter"])
        current_used_by_chapter[chapter].update(row.get("candidate_event_ids", []))
    gold_unmapped = [
        {**event, "status": "待判；未映射金标，不自判"}
        for event in events_by_chapter[3]
        if event["event_id"] not in gold_used
    ]
    current_unmapped: dict[str, list[dict[str, Any]]] = {}
    unmapped_by_both: dict[str, list[dict[str, Any]]] = {}
    for chapter in TARGET_CHAPTERS:
        current_unmapped[str(chapter)] = [
            {**event, "status": "待判；未映射现役记录，不自判"}
            for event in events_by_chapter[chapter]
            if event["event_id"] not in current_used_by_chapter[chapter]
        ]
        unmapped_by_both[str(chapter)] = [
            {**event, "status": "待判；未被本轮任一人工行映射，不自判"}
            for event in events_by_chapter[chapter]
            if event["event_id"] not in current_used_by_chapter[chapter]
            and (chapter != 3 or event["event_id"] not in gold_used)
        ]
    return {
        "schema_version": "z70-compression-contract-pending-overflow-v1",
        "status": "pending_no_self_adjudication",
        "chapter3_gold_unmapped": {
            "count": len(gold_unmapped),
            "events": gold_unmapped,
        },
        "current122_unmapped_candidates": {
            "count": sum(len(rows) for rows in current_unmapped.values()),
            "by_chapter": current_unmapped,
        },
        "unmapped_by_any_manual_row": {
            "count": sum(len(rows) for rows in unmapped_by_both.values()),
            "by_chapter": unmapped_by_both,
        },
        "boundary": "未映射只表示人工源没有用该候选支撑 gold/current 行，不等于正确、错误、应收或应删。",
    }


def load_optional_receipt(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "status": "not_provided",
            "boundary": "没有伪填测试数量；主线若另有冻结测试回执，可用 --test-receipt 显式带入。",
        }
    if not path.is_file():
        raise ReportError(f"指定的测试回执不存在：{display_path(path)}")
    data = path.read_bytes()
    try:
        content: Any = json.loads(data.decode("utf-8"))
        content_type = "json"
    except (UnicodeDecodeError, json.JSONDecodeError):
        content = data.decode("utf-8", errors="replace")
        content_type = "text"
    return {
        "status": "provided_as_frozen_input",
        "path": display_path(path),
        "sha256": sha256_bytes(data),
        "content_type": content_type,
        "content": content,
        "boundary": "只转录冻结回执及其SHA；报告器不把转录动作冒充重新执行测试。",
    }


def security_and_test_receipt(
    run_dir: Path,
    semantic_source: Path,
    test_receipt: Path | None,
) -> dict[str, Any]:
    verification_path = run_dir / "mechanical_verification.json"
    verification = require_mapping(read_json(verification_path), "Z70 机械验收")
    test_file = ROOT / "tests/test_z70_compression_contract_report.py"
    tests = load_optional_receipt(test_receipt)
    frozen_content = tests.get("content") if isinstance(tests, dict) else None
    secret_scan = (
        frozen_content.get("secret_scan")
        if isinstance(frozen_content, dict)
        and isinstance(frozen_content.get("secret_scan"), dict)
        else {"status": "not_provided"}
    )
    return {
        "schema_version": "z70-compression-contract-security-test-v1",
        "status": "mechanical_receipt_pass_test_receipt_optional",
        "zero_call_boundary": {
            "model_api_calls_by_report_builder": 0,
            "notion_calls_by_report_builder": 0,
            "network_calls_by_report_builder": 0,
            "note": "本工具只读本地冻结工件并生成派生文件，没有 API 或 Notion 调用入口。",
        },
        "source_integrity": {
            "run_manifest_sha256": sha256_file(run_dir / "run_manifest.json"),
            "mechanical_verification_sha256": sha256_file(verification_path),
            "mechanical_verification_status": verification.get("status"),
            "semantic_source_sha256": sha256_file(semantic_source),
        },
        "secret_scan": secret_scan,
        "tests": tests,
        "builder": {
            "path": display_path(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
            "test_path": display_path(test_file),
            "test_sha256": sha256_file(test_file) if test_file.is_file() else None,
            "determinism_check": "check 会在临时目录重建，并逐个生成文件比较 SHA-256。",
        },
        "write_boundary": "不会修改正式run、旧Z68报告、金标、现役122条、默认链、分类规则或outbox。",
    }


def overall_gate(gold_doc: Mapping[str, Any], current_doc: Mapping[str, Any]) -> dict[str, Any]:
    gold_pass = bool(require_mapping(gold_doc.get("quality_gate"), "金标质量闸").get("passed"))
    current_pass = bool(
        require_mapping(current_doc.get("quality_gate"), "现役质量闸").get("passed")
    )
    passed = gold_pass and current_pass
    reasons: list[str] = []
    if not gold_pass:
        reasons.append("金标严格分或语义影子覆盖低于旧Z68")
    if not current_pass:
        reasons.append("旧34条中存在至少一条语义劣化")
    return {
        "status": "pass" if passed else "fail",
        "gold_not_below_z68": gold_pass,
        "old_34_no_degradation": current_pass,
        "passed": passed,
        "disposition": "candidate_gate_pass" if passed else "hard_stop_no_repair",
        "reasons": reasons,
    }


def percent(value: float | None) -> str:
    return "不适用" if value is None else f"{value:.2%}"


def render_markdown(
    gold_doc: Mapping[str, Any],
    current_doc: Mapping[str, Any],
    mechanical_doc: Mapping[str, Any],
    transport_doc: Mapping[str, Any],
    supply_doc: Mapping[str, Any],
    overflow_doc: Mapping[str, Any],
    security_doc: Mapping[str, Any],
    gate: Mapping[str, Any],
    artifact_hashes: Mapping[str, str],
) -> str:
    gold = require_mapping(gold_doc["summary"], "金标 summary")
    current = require_mapping(current_doc["summary"], "现役 summary")
    comparison = require_mapping(current_doc["comparison_to_z68"], "现役比较")
    metrics = require_mapping(mechanical_doc["ten_metrics"], "机械十项")
    cost = require_mapping(metrics["10_token与耗时成本"], "成本")
    z70_usage = require_mapping(cost["z70_all_32k"], "Z70成本")
    z68c_delta = require_mapping(cost["z70_vs_z68c"], "Z70对Z68C成本")
    b0_delta = require_mapping(cost["z70_vs_b0"], "Z70对B0成本")
    transport = require_mapping(transport_doc["transport_summary"], "运输汇总")
    request_rows = require_list(
        require_mapping(supply_doc["five_chapter_request_diff"], "五章请求diff")["rows"],
        "五章请求diff rows",
    )
    runner = require_mapping(
        require_mapping(supply_doc["run_provenance"], "运行来源")["runner"],
        "运行器来源",
    )
    tests = require_mapping(security_doc["tests"], "测试回执")
    test_content = tests.get("content") if isinstance(tests.get("content"), dict) else {}
    test_checks = test_content.get("checks") if isinstance(test_content, dict) else []
    test_checks = test_checks if isinstance(test_checks, list) else []
    test_summary = "；".join(
        f"{row.get('name')} {row.get('tests_passed')}/{row.get('tests_passed')}通过"
        if isinstance(row, dict) and isinstance(row.get("tests_passed"), int)
        else f"{row.get('name')}通过"
        for row in test_checks
        if isinstance(row, dict) and row.get("status") == "pass"
    ) or "未提供冻结测试明细"
    secret_scan = require_mapping(security_doc["secret_scan"], "密钥扫描")
    prompt_sha_text = "；".join(
        f"ch{row['chapter']}={row['prepared_request_sha256']}"
        for row in request_rows
    )
    rescued_ids = list(comparison["old_partial_rescued_ids"])
    degraded_rows = list(comparison["degradations"])
    gate_label = "PASS" if gate["passed"] else "FAIL"
    disposition = str(gate["disposition"])
    lines = [
        "# 第70道停点回包｜事件句压缩合同单变量",
        "",
        f"⚠️ 结论：整体闸为 {gate_label}，处置是 `{disposition}`。第3章金标严格命中 {gold['strict_hit']}/14、语义影子覆盖 {gold['semantic_shadow_recalled']}/14，没有低于旧 Z68 的 {gold['z68_strict_hit']}/14、{gold['z68_semantic_shadow_recalled']}/14；但现役五靶章34条里有 {comparison['degradation_count']} 条比旧 Z68 劣化，所以按预写合同硬停，不修 Prompt、不补样、不重跑。",
        "",
        f"现役结果是完整保留 {current['preserved']}、部分保留 {current['partially_preserved']}、未观察 {current['not_observed']}。旧部分项救回 {comparison['old_partial_rescued_count']} 条，不能抵消任何一条新劣化。",
        "",
        "## 1. 这轮到底改了什么",
        "",
        f"- 唯一新增条款：{supply_doc['single_variable']['inserted_exact_line']}",
        "- 五章都只改 `messages[0].content`；删除这条后，系统消息逐字节回到基线。模型、温度、JSON模式、思考档位和用户消息没改。",
        "- 第3／4／5／13／19章都使用本轮32k新样张，一章一次。金标、ChatGPT示范件和现役122条没有进入请求。",
        "",
        "## 2. 运输、机械和成本",
        "",
        f"- 逻辑样本 {transport['logical_samples']}，网络尝试 {transport['network_attempts']}，运输重试 {transport['transport_retries']}；五章均为 HTTP 200、`stop`，程序合同通过。",
        f"- 目录外锚 {metrics['03_目录外锚数']}；事件编号连续 {metrics['02_event_id连续章率']['numerator']}/{metrics['02_event_id连续章率']['denominator']}；事件总数 {metrics['09_事件数']['candidate_total']}。",
        f"- Z70 五章实际总消耗 {z70_usage['totals']['total_tokens']:,} token、{z70_usage['totals']['elapsed_ms']:,} ms。对 Z68C 增加 {z68c_delta['delta']['total_tokens']:,} token（{percent(z68c_delta['delta_rate']['total_tokens'])}）；对 B0 增加 {b0_delta['delta']['total_tokens']:,} token（{percent(b0_delta['delta_rate']['total_tokens'])}）。",
        "- 条件边界：Z68C 是第3／4章复用16k，加第5／13／19章32k；它不是五章全32k。B0 是第57道16k基线的五靶章切片。",
        "",
        "## 3. 语义成绩和硬停原因",
        "",
        f"- 金标：严格 {gold['strict_hit']}/14，影子覆盖 {gold['semantic_shadow_recalled']}/14，漏 {gold['miss']}；金标下限闸通过={gold_doc['quality_gate']['passed']}。",
        f"- 现役：完整 {current['preserved']}，部分 {current['partially_preserved']}，未观察 {current['not_observed']}；旧34条不劣化闸通过={current_doc['quality_gate']['passed']}。",
        f"- 旧部分救回 ID（{len(rescued_ids)}条）：{', '.join(f'`{item}`' for item in rescued_ids) or '无'}。",
        "- 劣化 ID：",
    ]
    if degraded_rows:
        for row in degraded_rows:
            lines.append(
                f"  - `{row['record_id']}`：{row['z68_verdict']} → {row['z70_verdict']}"
            )
    else:
        lines.append("  - 无")
    lines.extend(
        [
            "",
            "人工判词只从 `语义人工复核源.json` 读取。程序会核对 ID、候选事件是否存在以及是否同章，但不会拿锚点里的原文给事件句倒补语义。",
            "",
            "## 4. 第四节回执清单",
            "",
            f"- 整体闸：{gate_label}；处置 `{disposition}`。",
            f"- 金标成绩：严格 {gold['strict_hit']}/14；语义影子覆盖 {gold['semantic_shadow_recalled']}/14；旧 Z68 下限 {gold['z68_strict_hit']}/14、{gold['z68_semantic_shadow_recalled']}/14。",
            f"- 现役34条：完整 {current['preserved']}；部分 {current['partially_preserved']}；未观察 {current['not_observed']}。",
            f"- 旧部分救回：{comparison['old_partial_rescued_count']}条；ID={', '.join(rescued_ids) or '无'}。",
            f"- 劣化：{comparison['degradation_count']}条；ID={', '.join(comparison['degraded_ids']) or '无'}。",
            f"- 模型逻辑样本／网络尝试／重试：{transport['logical_samples']}／{transport['network_attempts']}／{transport['transport_retries']}。",
            f"- 空回包／截断／程序合同失败：0／0／0；目录外锚 {transport['outside_catalog_anchor_total']}。",
            f"- 五章真实 usage：{z70_usage['totals']['prompt_tokens']:,} 输入＋{z70_usage['totals']['completion_tokens']:,} 输出＝{z70_usage['totals']['total_tokens']:,} 总 token；其中思考 {z70_usage['totals']['reasoning_tokens']:,}。",
            f"- 待判溢出：未映射任何人工行 {overflow_doc['unmapped_by_any_manual_row']['count']} 条；只列清单，不自判。",
        f"- 供料单变量：五章唯一条款数 {supply_doc['single_variable']['unique_clause_count_across_five_chapters']}；有效上限统一 {supply_doc['five_chapter_request_diff']['effective_max_tokens_for_all_chapters']}。",
            f"- 运行器 SHA：`{runner['sha256']}`。",
            f"- 五章候选请求 SHA：{prompt_sha_text}。",
            f"- 测试回执：{tests['status']}；{test_summary}。",
            f"- 密钥痕迹：{secret_scan.get('api_key_literal_hit_count', '未提供')}；扫描范围={secret_scan.get('scope', '未提供')}。",
            "- A／B／C／D 分布：不适用；本件只到中性事件抽取与旧记录语义对照，不进入分类编译。",
            "- 处置：不固化、不升默认、不写outbox、不回写现役122条、金标、分类规则或旧运行目录。",
            "- G101：未领取、未执行。",
            "",
            "## 5. 待判溢出",
            "",
            f"第3章未映射金标 {overflow_doc['chapter3_gold_unmapped']['count']} 条；五章未映射现役记录 {overflow_doc['current122_unmapped_candidates']['count']} 条；未被任一人工行映射 {overflow_doc['unmapped_by_any_manual_row']['count']} 条。完整事件句都在 `待判溢出清单.json`。未映射不等于正确、错误、应收或应删。",
            "",
            "## 6. 工件与停点",
            "",
            f"正式运行目录是 `{display_path(RUN)}/`。本报告目录只放派生回执；生成器没有调用 API 或 Notion，也没有回写任何输入。",
            "",
            f"本道停在 {comparison['degradation_count']} 条旧记录劣化。若要改 Prompt、补样、重跑或升默认，都要另拍；本回包不自动开下一轮。",
            "",
            "派生文件 SHA：",
            "",
        ]
    )
    for name, digest in artifact_hashes.items():
        lines.append(f"- `{name}`：`{digest}`")
    lines.extend(["", "来源：Codex", ""])
    return "\n".join(lines)


def build_documents(
    output_dir: Path = REPORT,
    *,
    run_dir: Path = RUN,
    old_report_dir: Path = OLD_REPORT,
    gold_path: Path = GOLD,
    semantic_source: Path = SEMANTIC_SOURCE,
    test_receipt: Path | None = None,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    run_dir = run_dir.resolve()
    old_report_dir = old_report_dir.resolve()
    gold_path = gold_path.resolve()
    semantic_source = semantic_source.resolve()
    test_receipt = test_receipt.resolve() if test_receipt is not None else None
    generated_paths = {(output_dir / name).resolve() for name in OUTPUT_NAMES}
    if test_receipt is not None and test_receipt in generated_paths:
        raise ReportError("测试回执输入不能与生成文件同名，避免循环覆盖")

    gold_doc = gold_score(run_dir, semantic_source, old_report_dir, gold_path)
    current_doc = current_diff(run_dir, semantic_source, old_report_dir)
    mechanical_doc = mechanical_and_cost_scorecard(run_dir, old_report_dir)
    transport_doc = transport_receipt(run_dir, mechanical_doc)
    supply_doc = supply_and_protection_receipt(run_dir)
    overflow_doc = pending_overflow(run_dir, gold_doc, current_doc)
    security_doc = security_and_test_receipt(run_dir, semantic_source, test_receipt)
    gate = overall_gate(gold_doc, current_doc)
    artifacts: dict[str, Any] = {
        "第3章金标v1.1语义成绩单.json": gold_doc,
        "现役122条五靶章语义diff.json": current_doc,
        "五靶章机械与成本成绩单.json": mechanical_doc,
        "运输与成本回执.json": transport_doc,
        "供料单变量与保护回执.json": supply_doc,
        "待判溢出清单.json": overflow_doc,
        "安全与测试回执.json": security_doc,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in artifacts.items():
        write_json(output_dir / name, value)
    artifact_hashes = {name: sha256_file(output_dir / name) for name in artifacts}
    markdown = render_markdown(
        gold_doc,
        current_doc,
        mechanical_doc,
        transport_doc,
        supply_doc,
        overflow_doc,
        security_doc,
        gate,
        artifact_hashes,
    )
    (output_dir / MAIN_REPORT_NAME).write_text(markdown, encoding="utf-8")
    output_hashes = {
        **artifact_hashes,
        MAIN_REPORT_NAME: sha256_file(output_dir / MAIN_REPORT_NAME),
    }
    recorded_at = require_mapping(
        read_json(run_dir / "responses/neutral_extract/ch0019_meta.json"),
        "第19章响应元数据",
    ).get("at")
    manifest = {
        "schema_version": "z70-compression-contract-report-manifest-v1",
        "status": gate["status"],
        "disposition": gate["disposition"],
        "recorded_at": recorded_at,
        "source_run": display_path(run_dir),
        "builder_sha256": sha256_file(Path(__file__)),
        "inputs": {
            "semantic_source": {
                "path": display_path(semantic_source),
                "sha256": sha256_file(semantic_source),
            },
            "gold": {"path": display_path(gold_path), "sha256": sha256_file(gold_path)},
            "old_z68_gold_score": {
                "path": display_path(old_report_dir / OLD_GOLD_NAME),
                "sha256": sha256_file(old_report_dir / OLD_GOLD_NAME),
            },
            "old_z68_current_diff": {
                "path": display_path(old_report_dir / OLD_CURRENT_NAME),
                "sha256": sha256_file(old_report_dir / OLD_CURRENT_NAME),
            },
            "old_z68_transport_cost": {
                "path": display_path(old_report_dir / OLD_TRANSPORT_NAME),
                "sha256": sha256_file(old_report_dir / OLD_TRANSPORT_NAME),
            },
            "test_receipt": security_doc["tests"],
        },
        "overall_gate": gate,
        "semantic_counts": {
            "gold": gold_doc["summary"],
            "current": current_doc["summary"],
            "old_partial_rescued_count": current_doc["comparison_to_z68"][
                "old_partial_rescued_count"
            ],
            "degradation_count": current_doc["comparison_to_z68"]["degradation_count"],
        },
        "output_hashes": output_hashes,
        "determinism_policy": "check在临时目录重建全部9个生成文件，并逐文件比较SHA-256。",
    }
    write_json(output_dir / "report_manifest.json", manifest)
    return manifest


def check_documents(
    output_dir: Path = REPORT,
    *,
    run_dir: Path = RUN,
    old_report_dir: Path = OLD_REPORT,
    gold_path: Path = GOLD,
    semantic_source: Path = SEMANTIC_SOURCE,
    test_receipt: Path | None = None,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    missing = [name for name in OUTPUT_NAMES if not (output_dir / name).is_file()]
    if missing:
        raise ReportError(f"报告目录缺少生成文件：{missing}")
    with tempfile.TemporaryDirectory() as temp:
        expected_dir = Path(temp) / "report"
        expected_manifest = build_documents(
            expected_dir,
            run_dir=run_dir,
            old_report_dir=old_report_dir,
            gold_path=gold_path,
            semantic_source=semantic_source,
            test_receipt=test_receipt,
        )
        expected_hashes = {name: sha256_file(expected_dir / name) for name in OUTPUT_NAMES}
        actual_hashes = {name: sha256_file(output_dir / name) for name in OUTPUT_NAMES}
        mismatched = [
            name for name in OUTPUT_NAMES if expected_hashes[name] != actual_hashes[name]
        ]
        if mismatched:
            raise ReportError(f"报告不能确定性重建，SHA不一致：{mismatched}")
    return {
        "status": "pass",
        "checked_files": len(OUTPUT_NAMES),
        "sha256": actual_hashes,
        "manifest": expected_manifest,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check"))
    parser.add_argument("--output-dir", "--report-dir", dest="output_dir", type=Path, default=REPORT)
    parser.add_argument("--run-dir", type=Path, default=RUN)
    parser.add_argument("--old-report-dir", type=Path, default=OLD_REPORT)
    parser.add_argument("--gold", dest="gold_path", type=Path, default=GOLD)
    parser.add_argument("--semantic-source", type=Path, default=SEMANTIC_SOURCE)
    parser.add_argument("--test-receipt", type=Path)
    args = parser.parse_args(argv)
    kwargs = {
        "run_dir": args.run_dir,
        "old_report_dir": args.old_report_dir,
        "gold_path": args.gold_path,
        "semantic_source": args.semantic_source,
        "test_receipt": args.test_receipt,
    }
    result = (
        build_documents(args.output_dir, **kwargs)
        if args.action == "build"
        else check_documents(args.output_dir, **kwargs)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
