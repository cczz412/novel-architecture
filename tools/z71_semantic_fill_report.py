#!/usr/bin/env python3
"""第71道：从完整旁路补全 run 和人工判词生成零 API、可重复核验的停点报告。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import z71_semantic_fill_pilot as z71


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/Z71_X01_z70语义补全旁路_五靶章_v1.0_20260721"
REPORT = ROOT / "reports/Z71_z70语义补全旁路_20260721"
Z68_REPORT = ROOT / "reports/Z68续令_32k参数兼容修复与裸考成绩_20260720"
Z70_REPORT = ROOT / "reports/Z70_压缩病灶合同条款单变量_20260721"
B0_GOLD = ROOT / "reports/Z57_稳定语义身份解耦与全链后半_20260719/第3章当章层诚实成绩单.json"
GOLD = ROOT / "reports/Z56_金标双轨分层与全链体检_20260719/第3章结构层金标v1.1.json"
PATCH_NOTE = ROOT / "TEMP/z70_semfill_sandbox_20260721/patch/SEMANTIC_FILL_PATCH.md"
SEMANTIC_SOURCE = REPORT / "语义人工复核源.json"

TARGET_CHAPTERS = (3, 4, 5, 13, 19)
EXPECTED_LOGICAL_BATCHES = 25
Z68_FROZEN_TOTAL_TOKENS = 91342
Z68_GOLD_NAME = "第3章金标v1.1语义成绩单.json"
Z68_CURRENT_NAME = "现役122条五靶章语义diff.json"
Z68_TRANSPORT_NAME = "运输与成本回执.json"
Z70_MANIFEST_NAME = "report_manifest.json"
MAIN_REPORT_NAME = "第71道停点回包｜z70语义补全旁路_20260721.md"
OUTPUT_NAMES = (
    "补全逐条diff与provenance.json",
    "第3章金标v1.1语义成绩单.json",
    "现役34条逐条账.json",
    "旧部分保留救回清单.json",
    "运输与成本回执.json",
    "实现差异回执.json",
    "待判溢出清单.json",
    "安全与测试回执.json",
    MAIN_REPORT_NAME,
    "report_manifest.json",
)

FILL_VERDICTS = {
    "pass",
    "unsupported",
    "lost_original",
    "absorbed_independent",
    "uncertain",
}
GOLD_VERDICTS = {"strict_hit", "semantic_shadow", "miss"}
CURRENT_VERDICTS = {"preserved", "partially_preserved", "not_observed"}
CURRENT_RANK = {"not_observed": 0, "partially_preserved": 1, "preserved": 2}
USAGE_KEYS = (
    "prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "total_tokens",
    "elapsed_ms",
)


class ReportError(RuntimeError):
    """报告输入不完整、集合漂移或冻结合同不满足要求。"""


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


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReportError(f"{label} 必须是非空字符串")
    return value


def require_separate_output(run_dir: Path, output_dir: Path) -> None:
    run = run_dir.resolve()
    output = output_dir.resolve()
    if output == run or run in output.parents or output in run.parents:
        raise ReportError("报告目录必须与正式 run 完全分离，禁止回写或嵌套")


def directory_hashes(path: Path) -> dict[str, str]:
    if not path.is_dir():
        raise ReportError(f"完整 run 目录不存在：{display_path(path)}")
    return {
        item.relative_to(path).as_posix(): sha256_file(item)
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def unique_rows(
    value: Any,
    *,
    id_key: str,
    verdicts: set[str],
    expected_count: int | None,
    label: str,
) -> dict[str, dict[str, Any]]:
    rows = require_list(value, label)
    if expected_count is not None and len(rows) != expected_count:
        raise ReportError(f"{label} 必须恰好 {expected_count} 条，实际 {len(rows)} 条")
    result: dict[str, dict[str, Any]] = {}
    for index, value_row in enumerate(rows):
        row = dict(require_mapping(value_row, f"{label}[{index}]"))
        row_id = require_string(row.get(id_key), f"{label}[{index}].{id_key}")
        if row_id in result:
            raise ReportError(f"{label} 出现重复 ID：{row_id}")
        verdict = row.get("verdict")
        if verdict not in verdicts:
            raise ReportError(f"{label} 的 {row_id} 判词无效：{verdict}")
        if not isinstance(row.get("note"), str):
            raise ReportError(f"{label} 的 {row_id} 缺少人工说明 note")
        result[row_id] = row
    return result


def require_same_ids(actual: Iterable[str], expected: Iterable[str], label: str) -> None:
    actual_set = set(actual)
    expected_set = set(expected)
    if actual_set != expected_set:
        raise ReportError(
            f"{label} 集合不一致；缺少={sorted(expected_set - actual_set)}，"
            f"多出={sorted(actual_set - expected_set)}"
        )


def event_rows(path: Path, label: str) -> list[dict[str, Any]]:
    doc = require_mapping(read_json(path), label)
    rows = require_list(doc.get("events"), f"{label}.events")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, value in enumerate(rows):
        row = dict(require_mapping(value, f"{label}.events[{index}]"))
        event_id = require_string(row.get("event_id"), f"{label}.events[{index}].event_id")
        require_string(row.get("event"), f"{label}.{event_id}.event")
        if event_id in seen:
            raise ReportError(f"{label} 出现重复事件 ID：{event_id}")
        seen.add(event_id)
        result.append(row)
    return result


def evidence_map(path: Path, chapter: int) -> dict[str, str]:
    doc = require_mapping(read_json(path), f"第{chapter}章冻结证据目录")
    entries = require_list(doc.get("entries"), f"第{chapter}章证据目录.entries")
    result: dict[str, str] = {}
    for index, value in enumerate(entries):
        row = require_mapping(value, f"第{chapter}章证据目录[{index}]")
        anchor_id = require_string(row.get("anchor_id"), "证据锚 anchor_id")
        quote = require_string(row.get("quote"), f"{anchor_id}.quote")
        if anchor_id in result:
            raise ReportError(f"第{chapter}章冻结目录重复锚：{anchor_id}")
        result[anchor_id] = quote
    return result


def diff_sidecar_rows(path: Path, chapter: int) -> list[dict[str, Any]]:
    doc = read_json(path)
    if isinstance(doc, list):
        raw_rows = doc
    else:
        mapping = require_mapping(doc, f"第{chapter}章补全 diff")
        raw_rows = None
        for key in ("events", "rows", "event_diffs", "diffs"):
            if isinstance(mapping.get(key), list):
                raw_rows = mapping[key]
                break
        if raw_rows is None:
            raise ReportError(f"第{chapter}章补全 diff 缺少 events")
    return [
        dict(require_mapping(row, f"第{chapter}章补全 diff[{index}]"))
        for index, row in enumerate(raw_rows)
    ]


def collect_fill_inventory(run_dir: Path) -> dict[str, Any]:
    by_chapter: dict[int, list[dict[str, Any]]] = {}
    by_id: dict[str, tuple[int, dict[str, Any]]] = {}
    changed: dict[str, dict[str, Any]] = {}
    outside_rows: list[dict[str, Any]] = []
    quote_mismatches: list[dict[str, Any]] = []
    total_events = 0
    expected_batches = 0

    for chapter in TARGET_CHAPTERS:
        before_path = run_dir / f"inputs/events/ch{chapter:04d}.json"
        after_path = run_dir / f"outputs/events/ch{chapter:04d}.json"
        sidecar_path = run_dir / f"sidecars/event_diffs/ch{chapter:04d}.json"
        catalog_path = run_dir / f"inputs/evidence_catalogs/ch{chapter:04d}.json"
        before_rows = event_rows(before_path, f"第{chapter}章补全前事件")
        after_rows = event_rows(after_path, f"第{chapter}章补全后事件")
        before_ids = [str(row["event_id"]) for row in before_rows]
        after_ids = [str(row["event_id"]) for row in after_rows]
        if before_ids != after_ids:
            raise ReportError(f"第{chapter}章补全前后事件 ID 或顺序变化")
        total_events += len(before_rows)
        expected_batches += math.ceil(len(before_rows) / 3)
        catalog = evidence_map(catalog_path, chapter)
        side_rows = diff_sidecar_rows(sidecar_path, chapter)
        side_by_id: dict[str, dict[str, Any]] = {}
        for index, row in enumerate(side_rows):
            event_id = require_string(
                row.get("event_id"), f"第{chapter}章补全 diff[{index}].event_id"
            )
            if event_id in side_by_id:
                raise ReportError(f"第{chapter}章补全 diff 重复事件：{event_id}")
            side_by_id[event_id] = row
        if not set(side_by_id).issubset(set(before_ids)):
            raise ReportError(f"第{chapter}章补全 diff 引用了不存在的事件")

        chapter_after: list[dict[str, Any]] = []
        for before, after in zip(before_rows, after_rows, strict=True):
            event_id = str(before["event_id"])
            before_locked = {key: value for key, value in before.items() if key != "event"}
            after_locked = {key: value for key, value in after.items() if key != "event"}
            if before_locked != after_locked:
                raise ReportError(f"{event_id} 除事件句外的编号、锚或字段发生变化")
            is_changed = before["event"] != after["event"]
            side = side_by_id.get(event_id)
            if is_changed and side is None:
                raise ReportError(f"{event_id} 实际改写但缺少 diff/provenance 行")
            if side is not None:
                side_changed = side.get("changed")
                if not isinstance(side_changed, bool) or side_changed != is_changed:
                    raise ReportError(f"{event_id} 的 changed 标记与实际事件句不一致")
                if side.get("before") != before["event"] or side.get("after") != after["event"]:
                    raise ReportError(f"{event_id} 的 before/after 与事件工件不一致")
            if is_changed:
                provenance_value = side.get("provenance") if side is not None else None
                provenance = require_list(provenance_value, f"{event_id}.provenance")
                if not provenance:
                    raise ReportError(f"{event_id} 被改写但没有原句锚 provenance")
                normalized_provenance: list[dict[str, Any]] = []
                seen_anchors: set[str] = set()
                for prov_index, value in enumerate(provenance):
                    prov = require_mapping(value, f"{event_id}.provenance[{prov_index}]")
                    anchor_id = require_string(
                        prov.get("anchor_id"), f"{event_id}.provenance[{prov_index}].anchor_id"
                    )
                    quote = require_string(
                        prov.get("quote"), f"{event_id}.provenance[{prov_index}].quote"
                    )
                    if anchor_id in seen_anchors:
                        raise ReportError(f"{event_id} provenance 重复锚：{anchor_id}")
                    seen_anchors.add(anchor_id)
                    in_catalog = anchor_id in catalog
                    quote_equal = in_catalog and catalog[anchor_id] == quote
                    normalized = {
                        "anchor_id": anchor_id,
                        "quote": quote,
                        "batch_id": prov.get("batch_id", side.get("batch_id")),
                        "in_frozen_catalog": in_catalog,
                        "quote_equals_frozen_catalog": quote_equal,
                    }
                    normalized_provenance.append(normalized)
                    if not in_catalog:
                        outside_rows.append(
                            {"chapter": chapter, "event_id": event_id, "anchor_id": anchor_id}
                        )
                    elif not quote_equal:
                        quote_mismatches.append(
                            {"chapter": chapter, "event_id": event_id, "anchor_id": anchor_id}
                        )
                changed[event_id] = {
                    "chapter": chapter,
                    "event_id": event_id,
                    "before": before["event"],
                    "after": after["event"],
                    "provenance": normalized_provenance,
                    "batch_id": side.get("batch_id") if side else None,
                }
            by_id[event_id] = (chapter, after)
            chapter_after.append(after)
        by_chapter[chapter] = chapter_after

    if expected_batches != EXPECTED_LOGICAL_BATCHES:
        raise ReportError(
            f"按每批至多3条计算应为 {EXPECTED_LOGICAL_BATCHES} 个逻辑批，实际 {expected_batches}"
        )
    return {
        "by_chapter": by_chapter,
        "by_id": by_id,
        "changed": changed,
        "outside_rows": outside_rows,
        "quote_mismatches": quote_mismatches,
        "total_events": total_events,
        "expected_batches": expected_batches,
    }


def validate_candidate_ids(
    owner_id: str,
    candidate_ids: Sequence[str],
    chapter: int,
    event_by_id: Mapping[str, tuple[int, dict[str, Any]]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for event_id in candidate_ids:
        if event_id not in event_by_id:
            raise ReportError(f"{owner_id} 引用了不存在的补全后事件：{event_id}")
        actual_chapter, event = event_by_id[event_id]
        if actual_chapter != chapter:
            raise ReportError(f"{owner_id} 引用的 {event_id} 不在第{chapter}章")
        result.append({"event_id": event_id, "event": event.get("event")})
    return result


def candidate_ids(row: Mapping[str, Any], label: str) -> list[str]:
    value = row.get("candidate_event_ids")
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ReportError(f"{label}.candidate_event_ids 必须是字符串数组")
    if len(value) != len(set(value)):
        raise ReportError(f"{label}.candidate_event_ids 出现重复")
    return list(value)


def verdict_summary(rows: Iterable[Mapping[str, Any]], verdicts: Sequence[str]) -> dict[str, int]:
    rows_list = list(rows)
    counts = Counter(str(row["verdict"]) for row in rows_list)
    return {"total": len(rows_list), **{verdict: counts[verdict] for verdict in verdicts}}


def fill_diff_report(
    source: Mapping[str, Any], inventory: Mapping[str, Any]
) -> dict[str, Any]:
    changed = require_mapping(inventory["changed"], "实际 changed 集")
    decisions = unique_rows(
        source.get("fill_rows"),
        id_key="event_id",
        verdicts=FILL_VERDICTS,
        expected_count=None,
        label="人工补全判词 fill_rows",
    )
    require_same_ids(decisions, changed, "fill_rows 与实际 changed 事件")
    rows: list[dict[str, Any]] = []
    for event_id, item_value in changed.items():
        item = require_mapping(item_value, event_id)
        decision = decisions[event_id]
        if decision.get("chapter") != item.get("chapter"):
            raise ReportError(f"fill_rows 的 {event_id} 章号与 run 不一致")
        rows.append(
            {
                **dict(item),
                "verdict": decision["verdict"],
                "semantic_review_note": decision["note"],
            }
        )
    nonpass = [row for row in rows if row["verdict"] != "pass"]
    outside = list(inventory["outside_rows"])
    quote_mismatches = list(inventory["quote_mismatches"])
    passed = not nonpass and not outside and not quote_mismatches
    return {
        "schema_version": "z71-semantic-fill-diff-provenance-v1",
        "status": "candidate_fill_pass" if passed else "hard_stop_no_repair",
        "scope": {
            "source_events": inventory["total_events"],
            "changed_events": len(rows),
            "unchanged_events": int(inventory["total_events"]) - len(rows),
            "target_chapters": list(TARGET_CHAPTERS),
        },
        "verdict_policy": {
            "pass": "人工确认补全句保持原义，新增内容有所挂原句锚支撑，且未吞并独立事实",
            "unsupported": "补入内容没有当章原文与冻结锚语义支撑",
            "lost_original": "改写时丢失原事件已有语义",
            "absorbed_independent": "把另一条独立事实并入本事件句",
            "uncertain": "本地判读不能确认语义保真；按失败处置",
        },
        "summary": {
            **verdict_summary(rows, tuple(sorted(FILL_VERDICTS))),
            "outside_catalog_provenance": len(outside),
            "provenance_quote_mismatches": len(quote_mismatches),
        },
        "quality_gate": {
            "all_changed_rows_semantically_pass": not nonpass,
            "outside_catalog_provenance_zero": not outside,
            "provenance_quotes_match_catalog": not quote_mismatches,
            "passed": passed,
            "disposition": "candidate_fill_pass" if passed else "hard_stop_no_repair",
            "failures": [
                {
                    "chapter": row["chapter"],
                    "event_id": row["event_id"],
                    "verdict": row["verdict"],
                    "reason": row["semantic_review_note"],
                }
                for row in nonpass
            ]
            + [{**row, "verdict": "outside_catalog"} for row in outside]
            + [{**row, "verdict": "quote_mismatch"} for row in quote_mismatches],
        },
        "rows": rows,
        "write_boundary": "只读补全前后工件；不回写 Z68C 样张或 Z71 run。",
    }


def old_rows_by_id(value: Any, id_key: str, count: int, label: str) -> tuple[list[str], dict[str, dict[str, Any]]]:
    rows = require_list(value, label)
    if len(rows) != count:
        raise ReportError(f"{label} 必须恰好 {count} 条")
    order: list[str] = []
    result: dict[str, dict[str, Any]] = {}
    for row_value in rows:
        row = dict(require_mapping(row_value, label))
        row_id = require_string(row.get(id_key), f"{label}.{id_key}")
        if row_id in result:
            raise ReportError(f"{label} 重复 ID：{row_id}")
        order.append(row_id)
        result[row_id] = row
    return order, result


def history_snapshot(z68_report_dir: Path, z70_report_dir: Path, b0_gold_path: Path) -> dict[str, Any]:
    b0_doc = require_mapping(read_json(b0_gold_path), "B0 第57道成绩")
    z68_gold_path = z68_report_dir / Z68_GOLD_NAME
    z68_current_path = z68_report_dir / Z68_CURRENT_NAME
    z70_manifest_path = z70_report_dir / Z70_MANIFEST_NAME
    z68_gold = require_mapping(read_json(z68_gold_path), "Z68C 金标成绩")
    z68_current = require_mapping(read_json(z68_current_path), "Z68C 现役成绩")
    z70_manifest = require_mapping(read_json(z70_manifest_path), "Z70 报告 manifest")
    b0_summary = require_mapping(b0_doc.get("summary"), "B0 summary")
    z68_gold_summary = require_mapping(z68_gold.get("summary"), "Z68C gold summary")
    z68_current_summary = require_mapping(z68_current.get("summary"), "Z68C current summary")
    z70_counts = require_mapping(z70_manifest.get("semantic_counts"), "Z70 semantic_counts")
    z70_gold = require_mapping(z70_counts.get("gold"), "Z70 gold summary")
    z70_current = require_mapping(z70_counts.get("current"), "Z70 current summary")
    expected_current = {"preserved": 17, "partially_preserved": 16, "not_observed": 1}
    if any(int(z68_current_summary.get(key) or 0) != value for key, value in expected_current.items()):
        raise ReportError("Z68C 现役历史基线不再是17完整／16部分／1未观察")
    return {
        "b0": {
            "path": display_path(b0_gold_path),
            "sha256": sha256_file(b0_gold_path),
            "strict_hit": int(b0_summary.get("hit") or 0),
            "semantic_shadow_recalled": int(b0_summary.get("shadow_recalled") or 0),
        },
        "z68c": {
            "gold_path": display_path(z68_gold_path),
            "gold_sha256": sha256_file(z68_gold_path),
            "current_path": display_path(z68_current_path),
            "current_sha256": sha256_file(z68_current_path),
            "strict_hit": int(z68_gold_summary.get("strict_hit") or 0),
            "semantic_shadow_recalled": int(z68_gold_summary.get("semantic_shadow_recalled") or 0),
            "current": expected_current,
        },
        "z70": {
            "path": display_path(z70_manifest_path),
            "sha256": sha256_file(z70_manifest_path),
            "status": z70_manifest.get("status"),
            "strict_hit": int(z70_gold.get("strict_hit") or 0),
            "semantic_shadow_recalled": int(z70_gold.get("semantic_shadow_recalled") or 0),
            "current": {
                key: int(z70_current.get(key) or 0)
                for key in ("preserved", "partially_preserved", "not_observed")
            },
        },
        "boundary": "三组历史成绩只从已落盘报告读取并列展示，不重算、不重跑、不修改。",
    }


def gold_score(
    source: Mapping[str, Any],
    inventory: Mapping[str, Any],
    history: Mapping[str, Any],
    gold_path: Path,
    z68_report_dir: Path,
) -> dict[str, Any]:
    decisions = unique_rows(
        source.get("gold_rows"),
        id_key="gold_item_id",
        verdicts=GOLD_VERDICTS,
        expected_count=14,
        label="人工金标判词 gold_rows",
    )
    old_doc = require_mapping(read_json(z68_report_dir / Z68_GOLD_NAME), "Z68C 金标成绩")
    order, old_rows = old_rows_by_id(old_doc.get("rows"), "gold_item_id", 14, "Z68C 金标 rows")
    require_same_ids(decisions, order, "gold_rows 与 Z68C 金标")
    event_by_id = require_mapping(inventory["by_id"], "补全后事件索引")
    rows: list[dict[str, Any]] = []
    for gold_id in order:
        decision = decisions[gold_id]
        ids = candidate_ids(decision, gold_id)
        rows.append(
            {
                "gold_item_id": gold_id,
                "verdict": decision["verdict"],
                "candidate_event_ids": ids,
                "candidate_events": validate_candidate_ids(gold_id, ids, 3, event_by_id),
                "semantic_review_note": decision["note"],
                "z68c_verdict": old_rows[gold_id].get("verdict"),
            }
        )
    summary = verdict_summary(rows, ("strict_hit", "semantic_shadow", "miss"))
    summary["gold_total"] = summary.pop("total")
    summary["semantic_shadow_only"] = summary.pop("semantic_shadow")
    summary["semantic_shadow_recalled"] = summary["strict_hit"] + summary["semantic_shadow_only"]
    summary["strict_hit_rate"] = summary["strict_hit"] / 14
    summary["semantic_shadow_recall_rate"] = summary["semantic_shadow_recalled"] / 14
    passed = summary["strict_hit"] >= 6 and summary["semantic_shadow_recalled"] >= 13
    return {
        "schema_version": "z71-semantic-fill-chapter3-gold-score-v1",
        "status": "candidate_score_pass" if passed else "hard_stop_no_repair",
        "condition": "Z68C＋z70旁路补全",
        "gold": {"path": display_path(gold_path), "sha256": sha256_file(gold_path)},
        "semantic_boundary": "严格与影子只取人工源；程序不拿 provenance 原句倒补语义。",
        "summary": summary,
        "historical_comparison_read_only": history,
        "quality_gate": {
            "required": {"strict_hit": 6, "semantic_shadow_recalled": 13},
            "strict_floor_pass": summary["strict_hit"] >= 6,
            "shadow_floor_pass": summary["semantic_shadow_recalled"] >= 13,
            "passed": passed,
            "disposition": "candidate_score_pass" if passed else "hard_stop_no_repair",
        },
        "rows": rows,
        "write_policy": "只出候选成绩，不修改金标。",
    }


def current_score(
    source: Mapping[str, Any],
    inventory: Mapping[str, Any],
    history: Mapping[str, Any],
    z68_report_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    decisions = unique_rows(
        source.get("current_rows"),
        id_key="record_id",
        verdicts=CURRENT_VERDICTS,
        expected_count=34,
        label="人工现役判词 current_rows",
    )
    old_doc = require_mapping(read_json(z68_report_dir / Z68_CURRENT_NAME), "Z68C 现役逐条账")
    order, old_rows = old_rows_by_id(old_doc.get("rows"), "record_id", 34, "Z68C 现役 rows")
    require_same_ids(decisions, order, "current_rows 与 Z68C 现役34条")
    event_by_id = require_mapping(inventory["by_id"], "补全后事件索引")
    rows: list[dict[str, Any]] = []
    degraded: list[dict[str, Any]] = []
    rescued: list[str] = []
    partial_rows: list[dict[str, Any]] = []
    for record_id in order:
        old = old_rows[record_id]
        chapter = int(old.get("chapter") or 0)
        if chapter not in TARGET_CHAPTERS:
            raise ReportError(f"Z68C 现役行 {record_id} 章号不在五靶章")
        old_verdict = old.get("verdict")
        if old_verdict not in CURRENT_VERDICTS:
            raise ReportError(f"Z68C 现役行 {record_id} 判词无效")
        decision = decisions[record_id]
        ids = candidate_ids(decision, record_id)
        new_verdict = str(decision["verdict"])
        old_rank = CURRENT_RANK[str(old_verdict)]
        new_rank = CURRENT_RANK[new_verdict]
        change = "improved" if new_rank > old_rank else ("degraded" if new_rank < old_rank else "unchanged")
        row = {
            "chapter": chapter,
            "record_id": record_id,
            "current_semantics": old.get("current_semantics"),
            "z68c_verdict": old_verdict,
            "verdict": new_verdict,
            "change": change,
            "candidate_event_ids": ids,
            "candidate_events": validate_candidate_ids(record_id, ids, chapter, event_by_id),
            "semantic_review_note": decision["note"],
        }
        rows.append(row)
        if change == "degraded":
            degraded.append(
                {
                    "chapter": chapter,
                    "record_id": record_id,
                    "z68c_verdict": old_verdict,
                    "z71_verdict": new_verdict,
                    "reason": decision["note"],
                }
            )
        if old_verdict == "partially_preserved":
            was_rescued = new_verdict == "preserved"
            if was_rescued:
                rescued.append(record_id)
            partial_rows.append(
                {
                    "chapter": chapter,
                    "record_id": record_id,
                    "z68c_verdict": old_verdict,
                    "z71_verdict": new_verdict,
                    "rescued_to_preserved": was_rescued,
                    "candidate_event_ids": ids,
                    "note": decision["note"],
                }
            )
    if len(partial_rows) != 16:
        raise ReportError(f"Z68C 旧部分保留必须恰好16条，实际 {len(partial_rows)}")
    summary = verdict_summary(rows, ("preserved", "partially_preserved", "not_observed"))
    by_chapter = {
        str(chapter): verdict_summary(
            [row for row in rows if row["chapter"] == chapter],
            ("preserved", "partially_preserved", "not_observed"),
        )
        for chapter in TARGET_CHAPTERS
    }
    summary["by_chapter"] = by_chapter
    passed = not degraded
    current_doc = {
        "schema_version": "z71-semantic-fill-current34-score-v1",
        "status": "candidate_diff_pass" if passed else "hard_stop_no_repair",
        "condition": "Z68C＋z70旁路补全",
        "baseline": {"preserved": 17, "partially_preserved": 16, "not_observed": 1},
        "historical_comparison_read_only": history,
        "summary": summary,
        "quality_gate": {
            "old_34_no_degradation": passed,
            "degradation_count": len(degraded),
            "degradations": degraded,
            "passed": passed,
            "disposition": "candidate_diff_pass" if passed else "hard_stop_no_repair",
        },
        "rows": rows,
    }
    rescue_doc = {
        "schema_version": "z71-semantic-fill-old-partial-rescue-v1",
        "status": "completed_candidate_count_only",
        "baseline_partial_count": 16,
        "rescued_count": len(rescued),
        "rescued_ids": rescued,
        "not_rescued_count": 16 - len(rescued),
        "rows": partial_rows,
        "boundary": "救回数不能抵消任一旧记录降级；主闸仍是34条逐条不劣化。",
    }
    return current_doc, rescue_doc


def usage_totals(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    totals: Counter[str] = Counter()
    by_chapter: dict[str, Counter[str]] = {str(chapter): Counter() for chapter in TARGET_CHAPTERS}
    counts: Counter[str] = Counter()
    for index, row in enumerate(rows):
        usage = require_mapping(row.get("usage"), f"usage[{index}].usage")
        details = usage.get("completion_tokens_details")
        details = details if isinstance(details, dict) else {}
        case_id = str(row.get("case_id") or row.get("batch_id") or "")
        chapter = row.get("chapter")
        if not isinstance(chapter, int):
            for candidate in TARGET_CHAPTERS:
                if f"ch{candidate:04d}" in case_id:
                    chapter = candidate
                    break
        if chapter not in TARGET_CHAPTERS:
            raise ReportError(f"usage[{index}] 无法识别五靶章：{case_id}")
        item = {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "reasoning_tokens": int(details.get("reasoning_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
            "elapsed_ms": int(row.get("elapsed_ms") or 0),
        }
        totals.update(item)
        by_chapter[str(chapter)].update(item)
        counts[str(chapter)] += 1
    return {
        "successful_usage_rows": len(rows),
        "totals": {key: int(totals[key]) for key in USAGE_KEYS},
        "chapters": {
            str(chapter): {
                **{key: int(by_chapter[str(chapter)][key]) for key in USAGE_KEYS},
                "successful_usage_rows": counts[str(chapter)],
            }
            for chapter in TARGET_CHAPTERS
        },
    }


def transport_and_cost(run_dir: Path, z68_report_dir: Path, expected_batches: int) -> dict[str, Any]:
    usage = usage_totals(run_dir / "usage.jsonl")
    attempts = read_jsonl(run_dir / "call_attempts.jsonl")
    if usage["successful_usage_rows"] != expected_batches:
        raise ReportError(
            f"Z71 完整 run 应有 {expected_batches} 个成功 usage，实际 {usage['successful_usage_rows']}"
        )
    logical_ids = {
        str(row.get("case_id") or row.get("batch_id") or "")
        for row in attempts
        if row.get("case_id") or row.get("batch_id")
    }
    logical_samples = len(logical_ids)
    if logical_samples != expected_batches:
        raise ReportError(f"Z71 逻辑批应为 {expected_batches}，实际 {logical_samples}")
    network_attempts = len(attempts)
    retries = network_attempts - logical_samples
    if retries < 0:
        raise ReportError("Z71 网络尝试少于逻辑批")
    z68_path = z68_report_dir / Z68_TRANSPORT_NAME
    z68_transport = require_mapping(read_json(z68_path), "Z68C 运输与成本回执")
    five_cost = require_mapping(z68_transport.get("five_chapter_condition_cost"), "Z68C 五章成本")
    z68_candidate = require_mapping(five_cost.get("candidate"), "Z68C 候选成本")
    z68_totals = require_mapping(z68_candidate.get("totals"), "Z68C totals")
    if int(z68_totals.get("total_tokens") or 0) != Z68_FROZEN_TOTAL_TOKENS:
        raise ReportError("Z68C 冻结历史成本不再是91,342 token")
    prepared_paths = sorted((run_dir / "prepared_requests").glob("*.json"))
    if len(prepared_paths) != expected_batches:
        raise ReportError(f"补全提示词候选应有 {expected_batches} 份，实际 {len(prepared_paths)}")
    return {
        "schema_version": "z71-semantic-fill-transport-cost-v1",
        "status": "pass",
        "condition": "Z68C＋z70旁路补全",
        "transport": {
            "expected_logical_batches": EXPECTED_LOGICAL_BATCHES,
            "actual_logical_batches": logical_samples,
            "network_attempts": network_attempts,
            "transport_retries": retries,
            "actual_model_api_calls": network_attempts,
            "single_sample_no_selection_rerun": True,
        },
        "incremental_z71_usage": {
            **usage,
            "source": display_path(run_dir / "usage.jsonl"),
            "source_sha256": sha256_file(run_dir / "usage.jsonl"),
            "billable_this_round_total_tokens": usage["totals"]["total_tokens"],
        },
        "z68c_frozen_history_not_rebilled": {
            "source": display_path(z68_path),
            "source_sha256": sha256_file(z68_path),
            "total_tokens": Z68_FROZEN_TOTAL_TOKENS,
            "rebilled_in_z71": False,
        },
        "prompt_candidates": [
            {"path": display_path(path), "sha256": sha256_file(path)}
            for path in prepared_paths
        ],
        "cost_boundary": "本轮成本只算 Z71 usage；Z68C 91,342 token 仅作冻结底料历史展示，不重复计费。",
    }


def implementation_differences(run_dir: Path, patch_note: Path) -> dict[str, Any]:
    manifest = require_mapping(read_json(run_dir / "run_manifest.json"), "Z71 run_manifest")
    preflight_path = run_dir / "preflight.json"
    preflight = require_mapping(read_json(preflight_path), "Z71 preflight")
    frozen_differences = preflight.get("sandbox_to_formal_differences")
    if not isinstance(frozen_differences, list) or not frozen_differences:
        raise ReportError("Z71 preflight 缺少 sandbox_to_formal_differences")
    batch_rows = require_list(preflight.get("rows"), "Z71 preflight.rows")
    if len(batch_rows) != EXPECTED_LOGICAL_BATCHES:
        raise ReportError(
            f"Z71 preflight 应冻结 {EXPECTED_LOGICAL_BATCHES} 个逐批规格，实际 {len(batch_rows)}"
        )
    explanatory_differences = [
        {
            "item": "施工身份",
            "sandbox_patch": "TEMP 候选补丁，只证明第3章三样本 v2 单点可行。",
            "formal_z71": "Codex 主线独立实现并对五靶章完整 run 验收，不复用沙箱输出。",
        },
        {
            "item": "范围与调度",
            "sandbox_patch": "三样本单点；整章与自动分批未正式验证。",
            "formal_z71": "72条冻结 Z68C 事件按每批至多3条拆成25个逻辑批。",
        },
        {
            "item": "组件边界",
            "sandbox_patch": "TEMP 覆盖样张。",
            "formal_z71": "补全前、补全后、逐条diff、provenance和逐批运输工件分别落盘。",
        },
        {
            "item": "硬锁与失败闸",
            "sandbox_patch": "三样本 v2 的检查比 v1 薄。",
            "formal_z71": "不增删事件、不改ID/顺序/锚；人工逐条审 changed 集，任一非pass硬停。",
        },
        {
            "item": "成绩身份",
            "sandbox_patch": "银标观察件。",
            "formal_z71": "仍是候选银标，只登记条件成绩，不固化、不升默认。",
        },
    ]
    return {
        "schema_version": "z71-semantic-fill-implementation-differences-v1",
        "status": "recorded",
        "patch_source": {
            "path": display_path(patch_note),
            "sha256": sha256_file(patch_note),
        },
        "formal_runner": manifest.get("runner"),
        "preflight": {
            "path": display_path(preflight_path),
            "sha256": sha256_file(preflight_path),
            "sandbox_to_formal_differences": frozen_differences,
            "batch_row_count": len(batch_rows),
        },
        "differences": explanatory_differences,
        "unchanged_contract": "只补既有事件句；当章正文＋冻结目录取材；原文未明示留空；不改抽取端与默认链。",
    }


def pending_overflow(
    inventory: Mapping[str, Any], gold_doc: Mapping[str, Any], current_doc: Mapping[str, Any]
) -> dict[str, Any]:
    by_chapter = require_mapping(inventory["by_chapter"], "补全后逐章事件")
    gold_used = {
        event_id
        for row in require_list(gold_doc.get("rows"), "金标 rows")
        if isinstance(row, dict)
        for event_id in row.get("candidate_event_ids", [])
    }
    current_used: dict[int, set[str]] = {chapter: set() for chapter in TARGET_CHAPTERS}
    for row in require_list(current_doc.get("rows"), "现役 rows"):
        if isinstance(row, dict):
            current_used[int(row["chapter"])].update(row.get("candidate_event_ids", []))
    gold_unmapped = [
        {**row, "status": "待判；未映射金标，不自判"}
        for row in by_chapter[3]
        if row["event_id"] not in gold_used
    ]
    by_target: dict[str, list[dict[str, Any]]] = {}
    by_any: dict[str, list[dict[str, Any]]] = {}
    for chapter in TARGET_CHAPTERS:
        by_target[str(chapter)] = [
            {**row, "status": "待判；未映射现役记录，不自判"}
            for row in by_chapter[chapter]
            if row["event_id"] not in current_used[chapter]
        ]
        by_any[str(chapter)] = [
            {**row, "status": "待判；未被任一人工评分行映射，不自判"}
            for row in by_chapter[chapter]
            if row["event_id"] not in current_used[chapter]
            and (chapter != 3 or row["event_id"] not in gold_used)
        ]
    return {
        "schema_version": "z71-semantic-fill-pending-overflow-v1",
        "status": "pending_no_self_adjudication",
        "chapter3_gold_unmapped": {"count": len(gold_unmapped), "events": gold_unmapped},
        "current34_unmapped": {
            "count": sum(len(rows) for rows in by_target.values()),
            "by_chapter": by_target,
        },
        "unmapped_by_any_manual_row": {
            "count": sum(len(rows) for rows in by_any.values()),
            "by_chapter": by_any,
        },
        "boundary": "未映射只表示没有被本轮人工评分行采用，不等于正确、错误、应收或应删。",
    }


def load_optional_receipt(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "status": "not_provided",
            "boundary": "不伪填测试数量；可用 --test-receipt 显式带入冻结回执。",
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
        "boundary": "只转录冻结回执和SHA，不冒充重新执行测试。",
    }


def security_and_tests(
    run_dir: Path,
    semantic_source: Path,
    runner_verification: Mapping[str, Any],
    run_hashes: Mapping[str, str],
    test_receipt: Path | None,
) -> dict[str, Any]:
    test_file = ROOT / "tests/test_z71_semantic_fill_report.py"
    tests = load_optional_receipt(test_receipt)
    content = tests.get("content") if isinstance(tests, dict) else None
    secret_scan = content.get("secret_scan") if isinstance(content, dict) else None
    return {
        "schema_version": "z71-semantic-fill-security-test-v1",
        "status": "runner_verified_report_test_receipt_optional",
        "zero_call_boundary": {
            "model_api_calls_by_report_builder": 0,
            "network_calls_by_report_builder": 0,
            "notion_calls_by_report_builder": 0,
        },
        "runner_verify": dict(runner_verification),
        "source_run_read_only": {
            "file_count": len(run_hashes),
            "tree_sha256": sha256_bytes(json_bytes(dict(run_hashes))),
            "unchanged_during_build": True,
        },
        "semantic_source": {
            "path": display_path(semantic_source),
            "sha256": sha256_file(semantic_source),
        },
        "secret_scan": secret_scan or {"status": "not_provided"},
        "tests": tests,
        "builder": {
            "path": display_path(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
            "test_path": display_path(test_file),
            "test_sha256": sha256_file(test_file) if test_file.is_file() else None,
            "determinism": "check在临时目录重建全部生成文件并逐SHA比较。",
        },
        "write_boundary": "原run只读；不回写Z68C、默认链、现役122条、金标、分类规则或outbox。",
    }


def overall_gate(
    fill_doc: Mapping[str, Any], gold_doc: Mapping[str, Any], current_doc: Mapping[str, Any]
) -> dict[str, Any]:
    fill_pass = bool(require_mapping(fill_doc.get("quality_gate"), "补全闸").get("passed"))
    gold_pass = bool(require_mapping(gold_doc.get("quality_gate"), "金标闸").get("passed"))
    current_pass = bool(require_mapping(current_doc.get("quality_gate"), "现役闸").get("passed"))
    passed = fill_pass and gold_pass and current_pass
    reasons: list[str] = []
    if not fill_pass:
        reasons.append("至少一条补全语义非pass、目录外provenance或原句锚不一致")
    if not gold_pass:
        reasons.append("第3章严格低于6/14或语义影子覆盖低于13/14")
    if not current_pass:
        reasons.append("现役34条相对Z68C至少一条降级")
    return {
        "status": "pass" if passed else "fail",
        "fill_semantic_and_provenance_gate": fill_pass,
        "gold_floor_gate": gold_pass,
        "old_34_no_degradation_gate": current_pass,
        "passed": passed,
        "disposition": "candidate_gate_pass" if passed else "hard_stop_no_repair",
        "reasons": reasons,
    }


def render_markdown(
    run_dir: Path,
    fill_doc: Mapping[str, Any],
    gold_doc: Mapping[str, Any],
    current_doc: Mapping[str, Any],
    rescue_doc: Mapping[str, Any],
    transport_doc: Mapping[str, Any],
    implementation_doc: Mapping[str, Any],
    overflow_doc: Mapping[str, Any],
    security_doc: Mapping[str, Any],
    gate: Mapping[str, Any],
    hashes: Mapping[str, str],
) -> str:
    fill_summary = require_mapping(fill_doc["summary"], "补全 summary")
    gold = require_mapping(gold_doc["summary"], "金标 summary")
    current = require_mapping(current_doc["summary"], "现役 summary")
    transport = require_mapping(transport_doc["transport"], "运输 summary")
    usage = require_mapping(transport_doc["incremental_z71_usage"], "Z71 usage")
    totals = require_mapping(usage["totals"], "Z71 usage totals")
    fill_failures = require_list(
        require_mapping(fill_doc["quality_gate"], "补全闸")["failures"], "补全失败"
    )
    degradations = require_list(
        require_mapping(current_doc["quality_gate"], "现役闸")["degradations"], "现役降级"
    )
    gate_label = "PASS" if gate["passed"] else "FAIL"
    lines = [
        "# 第71道停点回包｜z70语义补全旁路轮",
        "",
        f"✅ 条件成绩：`Z68C＋z70旁路补全`。整体闸为 {gate_label}，处置是 `{gate['disposition']}`。本轮只把已落盘 Z68C 事件送进独立补全组件，没有重抽五章。",
        "",
        f"补全实际改写 {fill_summary['total']} 条，其中人工通过 {fill_summary['pass']} 条；第3章金标严格 {gold['strict_hit']}/14、语义影子覆盖 {gold['semantic_shadow_recalled']}/14；现役34条是完整 {current['preserved']}、部分 {current['partially_preserved']}、未观察 {current['not_observed']}。",
        "",
        "## 1. 三道验收闸",
        "",
        f"- 补全语义与 provenance：通过={fill_doc['quality_gate']['passed']}；目录外锚 {fill_summary['outside_catalog_provenance']}；原句锚不一致 {fill_summary['provenance_quote_mismatches']}。",
        f"- 金标不跌：通过={gold_doc['quality_gate']['passed']}；门槛是严格≥6、影子覆盖≥13。",
        f"- 旧34条不劣化：通过={current_doc['quality_gate']['passed']}；降级 {current_doc['quality_gate']['degradation_count']} 条。",
        "",
        f"旧16条部分保留救回 {rescue_doc['rescued_count']} 条：{', '.join(rescue_doc['rescued_ids']) or '无'}。救回不能抵消任何一条降级。",
        "",
    ]
    if fill_failures:
        lines.extend(["补全失败明细：", ""])
        for row in fill_failures:
            lines.append(
                f"- 第{row.get('chapter')}章 `{row.get('event_id')}`：{row.get('verdict')}；{row.get('reason', '见逐条账')}"
            )
        lines.append("")
    if degradations:
        lines.extend(["现役降级明细：", ""])
        for row in degradations:
            lines.append(
                f"- 第{row['chapter']}章 `{row['record_id']}`：{row['z68c_verdict']} → {row['z71_verdict']}；{row['reason']}"
            )
        lines.append("")
    lines.extend(
        [
            "## 2. 运输和成本",
            "",
            f"- 预计逻辑批 {transport['expected_logical_batches']}，实际 {transport['actual_logical_batches']}；网络尝试 {transport['network_attempts']}，运输重试 {transport['transport_retries']}。每批至多3条，五章均单次采样，不挑结果。",
            f"- Z71 新增消耗：输入 {totals['prompt_tokens']:,}＋输出 {totals['completion_tokens']:,}＝{totals['total_tokens']:,} token，其中思考 {totals['reasoning_tokens']:,}；耗时 {totals['elapsed_ms']:,} ms。",
            f"- Z68C 冻结底料历史成本 {Z68_FROZEN_TOTAL_TOKENS:,} token，只作条件背景，不在 Z71 重复计费。",
            "",
            "## 3. 与沙箱补丁的实现差异",
            "",
        ]
    )
    for row in implementation_doc["differences"]:
        lines.append(
            f"- {row['item']}：沙箱={row['sandbox_patch']}；正式Z71={row['formal_z71']}"
        )
    lines.extend(
        [
            "",
            "## 4. 第四节回执清单",
            "",
            f"- 整体闸：{gate_label}；处置 `{gate['disposition']}`。",
            "- 条件成绩：`Z68C＋z70旁路补全`；候选银标，不固化、不升默认。",
            "- 抽取段：复用 Z68C 五章样张，二次采样 0，五章重抽 0。",
            f"- 补全调用：预计25逻辑批，实际逻辑批 {transport['actual_logical_batches']}，网络调用 {transport['actual_model_api_calls']}，重试 {transport['transport_retries']}。",
            f"- 补全 changed：{fill_summary['total']}条；pass {fill_summary['pass']}；非pass {fill_summary['total'] - fill_summary['pass']}。",
            f"- 金标：严格 {gold['strict_hit']}/14；影子覆盖 {gold['semantic_shadow_recalled']}/14。",
            f"- 现役34条：完整 {current['preserved']}；部分 {current['partially_preserved']}；未观察 {current['not_observed']}；旧部分救回 {rescue_doc['rescued_count']}。",
            f"- provenance：目录外锚 {fill_summary['outside_catalog_provenance']}；quote不一致 {fill_summary['provenance_quote_mismatches']}。",
            f"- Z71 新增真实 usage：{totals['total_tokens']:,} token；Z68C 历史 {Z68_FROZEN_TOTAL_TOKENS:,} 不重复计费。",
            f"- 待判溢出：未映射任一人工行 {overflow_doc['unmapped_by_any_manual_row']['count']} 条，只列不自判。",
            f"- 报告器模型／网络／Notion调用：{security_doc['zero_call_boundary']['model_api_calls_by_report_builder']}／{security_doc['zero_call_boundary']['network_calls_by_report_builder']}／{security_doc['zero_call_boundary']['notion_calls_by_report_builder']}。",
            "- A／B／C／D：不适用；本道不进入分类编译。",
            "- 保护边界：默认链、现役122条、金标、分类规则、outbox均不动；G101未领取。",
            "",
            "## 5. 工件、待判与停点",
            "",
            f"补全逐条前后句、原句锚和人工判词在 `补全逐条diff与provenance.json`。待判项在 `待判溢出清单.json`，不自判对错。原 run `{display_path(run_dir)}/` 只读，报告器只写独立报告目录。",
            "",
            "派生文件 SHA：",
            "",
        ]
    )
    for name, digest in hashes.items():
        lines.append(f"- `{name}`：`{digest}`")
    lines.extend(["", "来源：Codex", ""])
    return "\n".join(lines)


def build_documents(
    output_dir: Path = REPORT,
    *,
    run_dir: Path = RUN,
    semantic_source: Path = SEMANTIC_SOURCE,
    z68_report_dir: Path = Z68_REPORT,
    z70_report_dir: Path = Z70_REPORT,
    b0_gold_path: Path = B0_GOLD,
    gold_path: Path = GOLD,
    patch_note: Path = PATCH_NOTE,
    test_receipt: Path | None = None,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    run_dir = run_dir.resolve()
    semantic_source = semantic_source.resolve()
    z68_report_dir = z68_report_dir.resolve()
    z70_report_dir = z70_report_dir.resolve()
    b0_gold_path = b0_gold_path.resolve()
    gold_path = gold_path.resolve()
    patch_note = patch_note.resolve()
    test_receipt = test_receipt.resolve() if test_receipt else None
    require_separate_output(run_dir, output_dir)
    generated = {(output_dir / name).resolve() for name in OUTPUT_NAMES}
    if semantic_source in generated or (test_receipt is not None and test_receipt in generated):
        raise ReportError("人工源／测试回执不能与生成文件同名，避免循环覆盖")

    before_hashes = directory_hashes(run_dir)
    verify_result = require_mapping(z71.verify(run_dir), "Z71 runner verify 回执")
    if verify_result.get("status") != "pass":
        raise ReportError(f"Z71 runner verify 未通过：{verify_result}")
    source = require_mapping(read_json(semantic_source), "语义人工复核源")
    inventory = collect_fill_inventory(run_dir)
    history = history_snapshot(z68_report_dir, z70_report_dir, b0_gold_path)
    fill_doc = fill_diff_report(source, inventory)
    gold_doc = gold_score(source, inventory, history, gold_path, z68_report_dir)
    current_doc, rescue_doc = current_score(source, inventory, history, z68_report_dir)
    transport_doc = transport_and_cost(run_dir, z68_report_dir, int(inventory["expected_batches"]))
    implementation_doc = implementation_differences(run_dir, patch_note)
    overflow_doc = pending_overflow(inventory, gold_doc, current_doc)
    after_read_hashes = directory_hashes(run_dir)
    if before_hashes != after_read_hashes:
        raise ReportError("runner verify 或报告读取过程改写了原 run")
    security_doc = security_and_tests(
        run_dir, semantic_source, verify_result, before_hashes, test_receipt
    )
    gate = overall_gate(fill_doc, gold_doc, current_doc)
    artifacts: dict[str, Any] = {
        "补全逐条diff与provenance.json": fill_doc,
        "第3章金标v1.1语义成绩单.json": gold_doc,
        "现役34条逐条账.json": current_doc,
        "旧部分保留救回清单.json": rescue_doc,
        "运输与成本回执.json": transport_doc,
        "实现差异回执.json": implementation_doc,
        "待判溢出清单.json": overflow_doc,
        "安全与测试回执.json": security_doc,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in artifacts.items():
        write_json(output_dir / name, value)
    hashes = {name: sha256_file(output_dir / name) for name in artifacts}
    markdown = render_markdown(
        run_dir,
        fill_doc,
        gold_doc,
        current_doc,
        rescue_doc,
        transport_doc,
        implementation_doc,
        overflow_doc,
        security_doc,
        gate,
        hashes,
    )
    (output_dir / MAIN_REPORT_NAME).write_text(markdown, encoding="utf-8")
    hashes[MAIN_REPORT_NAME] = sha256_file(output_dir / MAIN_REPORT_NAME)
    run_manifest = require_mapping(read_json(run_dir / "run_manifest.json"), "Z71 run_manifest")
    manifest = {
        "schema_version": "z71-semantic-fill-report-manifest-v1",
        "status": gate["status"],
        "disposition": gate["disposition"],
        "condition": "Z68C＋z70旁路补全",
        "recorded_at": run_manifest.get("completed_at") or run_manifest.get("recorded_at"),
        "source_run": display_path(run_dir),
        "source_run_tree_sha256": sha256_bytes(json_bytes(before_hashes)),
        "builder_sha256": sha256_file(Path(__file__)),
        "inputs": {
            "semantic_source": {
                "path": display_path(semantic_source),
                "sha256": sha256_file(semantic_source),
            },
            "gold": {"path": display_path(gold_path), "sha256": sha256_file(gold_path)},
            "history": history,
            "patch_note": implementation_doc["patch_source"],
            "test_receipt": security_doc["tests"],
        },
        "overall_gate": gate,
        "counts": {
            "source_events": inventory["total_events"],
            "changed_events": fill_doc["summary"]["total"],
            "fill_nonpass": fill_doc["summary"]["total"] - fill_doc["summary"]["pass"],
            "gold_strict": gold_doc["summary"]["strict_hit"],
            "gold_shadow_recalled": gold_doc["summary"]["semantic_shadow_recalled"],
            "current_preserved": current_doc["summary"]["preserved"],
            "current_partial": current_doc["summary"]["partially_preserved"],
            "current_not_observed": current_doc["summary"]["not_observed"],
            "old_partial_rescued": rescue_doc["rescued_count"],
            "current_degradations": current_doc["quality_gate"]["degradation_count"],
        },
        "transport": transport_doc["transport"],
        "incremental_total_tokens": transport_doc["incremental_z71_usage"]["totals"]["total_tokens"],
        "output_hashes": hashes,
        "determinism_policy": "check在临时目录重建全部10个生成文件并逐SHA比较。",
        "candidate_boundary": "银标候选；不固化、不升默认、不写outbox。",
    }
    write_json(output_dir / "report_manifest.json", manifest)
    if before_hashes != directory_hashes(run_dir):
        raise ReportError("生成报告期间原 run 发生变化")
    return manifest


def check_documents(
    output_dir: Path = REPORT,
    **kwargs: Any,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    missing = [name for name in OUTPUT_NAMES if not (output_dir / name).is_file()]
    if missing:
        raise ReportError(f"报告目录缺少生成文件：{missing}")
    with tempfile.TemporaryDirectory() as temp:
        expected_dir = Path(temp) / "report"
        expected_manifest = build_documents(expected_dir, **kwargs)
        expected = {name: sha256_file(expected_dir / name) for name in OUTPUT_NAMES}
        actual = {name: sha256_file(output_dir / name) for name in OUTPUT_NAMES}
        mismatched = [name for name in OUTPUT_NAMES if expected[name] != actual[name]]
        if mismatched:
            raise ReportError(f"报告不能确定性重建，SHA不一致：{mismatched}")
    return {
        "status": "pass",
        "checked_files": len(OUTPUT_NAMES),
        "sha256": actual,
        "manifest": expected_manifest,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check"))
    parser.add_argument("--report-dir", "--output-dir", dest="output_dir", type=Path, default=REPORT)
    parser.add_argument("--run-dir", type=Path, default=RUN)
    parser.add_argument("--semantic-source", type=Path, default=SEMANTIC_SOURCE)
    parser.add_argument("--z68-report-dir", type=Path, default=Z68_REPORT)
    parser.add_argument("--z70-report-dir", type=Path, default=Z70_REPORT)
    parser.add_argument("--b0-gold", dest="b0_gold_path", type=Path, default=B0_GOLD)
    parser.add_argument("--gold", dest="gold_path", type=Path, default=GOLD)
    parser.add_argument("--patch-note", type=Path, default=PATCH_NOTE)
    parser.add_argument("--test-receipt", type=Path)
    args = parser.parse_args(argv)
    kwargs = {
        "run_dir": args.run_dir,
        "semantic_source": args.semantic_source,
        "z68_report_dir": args.z68_report_dir,
        "z70_report_dir": args.z70_report_dir,
        "b0_gold_path": args.b0_gold_path,
        "gold_path": args.gold_path,
        "patch_note": args.patch_note,
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
