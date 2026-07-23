#!/usr/bin/env python3
"""Z00l 分类收权单变量适配器。

不修改 ``tools/zbatch.py``。本文件只把原来的提取阶段拆成两段：

1. SenseNova ``deepseek-v4-flash`` 只交中性事件和冻结证据 ID；
2. 本地主控按独立规则文件分类，再复用 zbatch 的记录核锚器验收。

分类阶段不调用模型。所有未分类、丢弃、重叠命中和重复组都显式留账。
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import zbatch  # noqa: E402


EVENT_ID_PATTERN = re.compile(r"^EV-C(?P<chapter>\d{4})-(?P<serial>\d{2})$")
EVENT_SCHEMA_VERSION = "z-event-v1"
DECISION_SCHEMA_VERSION = "z-main-control-classification-v1"
EXPECTED_STAGES = ["event_extract", "classify", "verify"]
EXPECTED_MODEL = "deepseek-v4-flash"
EXPECTED_TEMPERATURE = 0.2
EXPECTED_CHAPTER_RANGE = (6, 10)
EXPECTED_CHAPTERS = 5
EXPECTED_ITEM = "X01"
EXPECTED_BATCH = "Z00l"
DEFAULT_PROMPT_SHA256 = "b5f30ab1e3e9cae7870db6bf2a951448d391981c0cfb257bd577686bd0a2c6b9"

ROOT_KEYS = {"schema_version", "chapter", "coverage_audit", "events"}
EVENT_KEYS = {"event_id", "event", "anchors"}
ANCHOR_KEYS = {"anchor_id"}
COVERAGE_KEYS = {"status", "event_ids", "reason"}
CLASSIFICATION_LABELS = ("A类", "B类", "C类", "D类", "跨章因果", "故事内触发器", "读者承诺", "世界规则")
DECISION_KEYS = {
    "event_id",
    "disposition",
    "matched_types",
    "primary_type",
    "rule_ids",
    "basis",
    "assertion",
    "fields",
    "related_event_ids",
    "duplicate_group",
    "conflict_reason",
}
DISPOSITIONS = {"classified", "unclassified", "discarded"}
TYPE_STATE = {"A": "", "B": "待", "C": "未兑现", "D": "有效"}


def event_envelope_reasons(
    data: Any,
    chapter: int,
    catalog: list[dict[str, Any]],
) -> list[str]:
    """严格验收弱模型中性事件外壳，不修补、不二次生成。"""
    if not isinstance(data, dict):
        return ["回包不是对象"]

    reasons: list[str] = []
    if set(data) != ROOT_KEYS:
        reasons.append("事件外壳字段不等于固定合同")
    if data.get("schema_version") != EVENT_SCHEMA_VERSION:
        reasons.append("事件schema错误")
    if data.get("chapter") != chapter:
        reasons.append("章号错误")

    catalog_ids = {
        str(row.get("anchor_id"))
        for row in catalog
        if isinstance(row, dict) and isinstance(row.get("anchor_id"), str)
    }
    events = data.get("events")
    if not isinstance(events, list):
        return sorted(set(reasons + ["events不是数组"]))

    emitted_ids: list[str] = []
    expected_ids: list[str] = []
    for index, event in enumerate(events, 1):
        expected_id = f"EV-C{chapter:04d}-{index:02d}"
        expected_ids.append(expected_id)
        if not isinstance(event, dict):
            reasons.append("事件不是对象")
            continue
        if set(event) != EVENT_KEYS:
            reasons.append(f"{expected_id}字段越出中性事件合同")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not EVENT_ID_PATTERN.fullmatch(event_id):
            reasons.append(f"{expected_id}事件ID非法")
        else:
            emitted_ids.append(event_id)
            match = EVENT_ID_PATTERN.fullmatch(event_id)
            assert match is not None
            if int(match.group("chapter")) != chapter:
                reasons.append(f"{event_id}事件ID章号错误")
            if event_id != expected_id:
                reasons.append(f"{event_id}事件ID不连续")

        summary = event.get("event")
        if not isinstance(summary, str) or not 8 <= zbatch.nonspace_chars(summary) <= 100:
            reasons.append(f"{expected_id}事件摘要长度非法")
        elif any(label in summary for label in CLASSIFICATION_LABELS):
            reasons.append(f"{expected_id}夹带分类标签")

        anchors = event.get("anchors")
        if not isinstance(anchors, list) or not anchors:
            reasons.append(f"{expected_id}无冻结证据ID")
            continue
        anchor_ids: list[str] = []
        for anchor in anchors:
            if not isinstance(anchor, dict) or set(anchor) != ANCHOR_KEYS:
                reasons.append(f"{expected_id}证据字段越出合同")
                continue
            anchor_id = anchor.get("anchor_id")
            if not isinstance(anchor_id, str) or anchor_id not in catalog_ids:
                reasons.append(f"{expected_id}证据目录ID不存在")
            else:
                anchor_ids.append(anchor_id)
        if len(anchor_ids) != len(set(anchor_ids)):
            reasons.append(f"{expected_id}证据目录ID重复")

    if len(emitted_ids) != len(set(emitted_ids)):
        reasons.append("事件ID重复")
    if emitted_ids != expected_ids:
        reasons.append("事件ID集合或顺序不连续")

    audit = data.get("coverage_audit")
    if not isinstance(audit, dict):
        reasons.append("缺事件覆盖清点")
    else:
        if set(audit) != COVERAGE_KEYS:
            reasons.append("事件覆盖清点字段错误")
        status = audit.get("status")
        if status not in {"emitted", "none"}:
            reasons.append("事件覆盖状态非法")
        audit_ids = audit.get("event_ids")
        if not isinstance(audit_ids, list) or any(not isinstance(value, str) for value in audit_ids):
            reasons.append("事件覆盖ID非法")
            audit_ids = []
        if audit_ids != emitted_ids:
            reasons.append("事件覆盖ID与输出不一致")
        if emitted_ids and status != "emitted":
            reasons.append("有事件却未标emitted")
        if not emitted_ids and status != "none":
            reasons.append("无事件却未标none")
        reason = audit.get("reason")
        if not isinstance(reason, str) or zbatch.nonspace_chars(reason) < 12:
            reasons.append("事件覆盖理由过短")

    return sorted(set(reasons))


def materialize_event_anchors(
    data: dict[str, Any],
    catalog: list[dict[str, Any]],
    chapter: int,
) -> dict[str, Any]:
    """把弱模型选择的冻结 ID 确定性展开为章号＋10～25字原文短引。"""
    catalog_map = {
        str(row["anchor_id"]): str(row["quote"])
        for row in catalog
        if isinstance(row, dict) and row.get("anchor_id") and row.get("quote")
    }
    result = copy.deepcopy(data)
    for event in result.get("events") or []:
        event["anchors"] = [
            {
                "chapter": chapter,
                "anchor_id": str(anchor["anchor_id"]),
                "quote": catalog_map[str(anchor["anchor_id"])],
            }
            for anchor in event.get("anchors") or []
        ]
    return result


def z00l_preflight(config_path: Path, *, require_key: bool = False) -> dict[str, Any]:
    """在原 zbatch 零调用预演上追加 Z00l 单变量护栏。"""
    result = zbatch.preflight(config_path, require_key=require_key)
    batch, provider = zbatch.load_configs(config_path)
    checks = list(result.get("checks") or [])

    zbatch.add_check(checks, "z00l_batch", batch.get("batch_id") == EXPECTED_BATCH, batch.get("batch_id"))
    zbatch.add_check(checks, "z00l_item", batch.get("item_id") == EXPECTED_ITEM, batch.get("item_id"))
    zbatch.add_check(
        checks,
        "z00l_chapter_range",
        (batch.get("chapter_start"), batch.get("chapter_end"), batch.get("expected_chapters"))
        == (*EXPECTED_CHAPTER_RANGE, EXPECTED_CHAPTERS),
        [batch.get("chapter_start"), batch.get("chapter_end"), batch.get("expected_chapters")],
    )
    zbatch.add_check(checks, "z00l_stages", batch.get("stages") == EXPECTED_STAGES, batch.get("stages"))
    zbatch.add_check(checks, "z00l_model", provider.get("model") == EXPECTED_MODEL, provider.get("model"))
    zbatch.add_check(
        checks,
        "z00l_temperature",
        float(provider.get("temperature", -1)) == EXPECTED_TEMPERATURE,
        provider.get("temperature"),
    )
    prompts = batch.get("prompts") if isinstance(batch.get("prompts"), dict) else {}
    zbatch.add_check(
        checks,
        "z00l_prompt_keys",
        set(prompts) == {"event_extract", "classifier_rules"},
        sorted(prompts),
    )
    default_prompt = zbatch.root_path("work/zbatch_prompts/extract_v1.3.md")
    zbatch.add_check(
        checks,
        "default_extract_unchanged",
        default_prompt.is_file() and zbatch.sha256_file(default_prompt) == DEFAULT_PROMPT_SHA256,
        zbatch.sha256_file(default_prompt) if default_prompt.is_file() else "missing",
    )
    run_id = str(batch.get("run_id") or "")
    outbox_path = zbatch.OUTBOX_DIR / run_id
    zbatch.add_check(checks, "z00l_outbox_absent", not outbox_path.exists(), zbatch.rel(outbox_path))

    result["checks"] = checks
    result["preflight"] = "pass" if all(item.get("ok") for item in checks) else "fail"
    result["model_calls"] = 0
    result["z00l_contract"] = {
        "variable": "分类与主类型归属权从弱模型转移到主控规则；事件提取合同同步改为中性事件合同",
        "classification_model_calls": 0,
        "runner_unchanged": True,
    }
    return result


def _event_prompt(batch: dict[str, Any]) -> str:
    path = zbatch.root_path(str((batch.get("prompts") or {}).get("event_extract") or ""))
    if not path.is_file():
        raise zbatch.ZBatchError("缺 Z00l 中性事件提取 Prompt")
    return path.read_text(encoding="utf-8")


def extract_events(config_path: Path) -> dict[str, Any]:
    pre = z00l_preflight(config_path, require_key=True)
    if pre.get("preflight") != "pass":
        raise zbatch.ZBatchError("Z00l 预演未通过，拒绝创建 API 运行")

    batch, provider = zbatch.load_configs(config_path)
    ctx = zbatch.initialize_run(batch, provider, pre, resume=False)
    chapters = zbatch.load_chapters(
        zbatch.root_path(batch["book_dir"]),
        int(batch["chapter_start"]),
        int(batch["chapter_end"]),
    )
    template = _event_prompt(batch)
    metrics: dict[str, Any] = {
        "chapters_completed": 0,
        "chapters_expected": len(chapters),
        "events_by_chapter": {},
        "empty_chapters": [],
        "classification_fields_found": 0,
    }
    zbatch.update_run_manifest(ctx, status="running")
    try:
        for number, chapter in chapters.items():
            catalog = zbatch.build_evidence_catalog(number, chapter["text"])
            coverage = zbatch.evidence_catalog_coverage(chapter["text"], catalog)
            if not catalog or coverage != 1.0:
                raise zbatch.ZBatchError(f"第 {number} 章冻结证据目录不完整")
            catalog_path = ctx.run_dir / "01_event_extract" / "evidence_catalogs" / f"ch{number:04d}.json"
            zbatch.write_json(catalog_path, {"chapter": number, "coverage": coverage, "entries": catalog})
            catalog_json = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
            prompt = zbatch.replace_prompt(template, {
                "CHAPTER_NUMBER": str(number),
                "CHAPTER_PADDED": f"{number:04d}",
                "CHAPTER_FILENAME": chapter["filename"],
                "CHAPTER_TEXT": chapter["text"],
                "EVIDENCE_CATALOG_JSON": catalog_json,
            })
            prompt_sha = zbatch.sha256_bytes(prompt.encode("utf-8"))
            input_sha = zbatch.sha256_bytes(
                (chapter["sha256"] + "\n" + zbatch.sha256_bytes(catalog_json.encode("utf-8"))).encode("utf-8")
            )
            data = ctx.call_json(
                stage="extract",
                case_id=f"ch{number:04d}",
                messages=[
                    {
                        "role": "system",
                        "content": "你只做证据约束的中性事件摘取，不做类型判断。只输出合法 JSON。",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            reasons = event_envelope_reasons(data, number, catalog)
            if reasons:
                raise zbatch.ZBatchError(f"第 {number} 章中性事件回包无效：{reasons}；不做二次生成")
            materialized = materialize_event_anchors(data, catalog, number)
            output_path = ctx.run_dir / "01_event_extract" / "parsed" / f"ch{number:04d}.json"
            zbatch.write_api_artifact(
                ctx,
                stage="extract",
                case_id=f"ch{number:04d}",
                output_path=output_path,
                data=materialized,
                input_sha256=input_sha,
                prompt_sha256=prompt_sha,
            )
            count = len(materialized.get("events") or [])
            metrics["events_by_chapter"][str(number)] = count
            if count == 0:
                metrics["empty_chapters"].append(number)
            metrics["chapters_completed"] += 1

        metrics["event_total"] = sum(metrics["events_by_chapter"].values())
        metrics["empty_chapter_count"] = len(metrics["empty_chapters"])
        metrics["model_calls"] = ctx.calls_made
        metrics["model"] = provider.get("model")
        metrics["temperature"] = provider.get("temperature")
        zbatch.write_json(ctx.run_dir / "01_event_extract" / "metrics.json", metrics)
        zbatch.update_run_manifest(ctx, status="awaiting_main_control", stage="event_extract")
    except Exception as exc:
        zbatch.update_run_manifest(ctx, status="failed", error=f"{type(exc).__name__}: {exc}")
        raise

    return {
        "run_id": batch.get("run_id"),
        "run_dir": zbatch.rel(ctx.run_dir),
        "calls_made": ctx.calls_made,
        "results": {"event_extract": metrics},
    }


def load_events(run_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    event_map: dict[str, dict[str, Any]] = {}
    by_chapter: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted((run_dir / "01_event_extract" / "parsed").glob("ch[0-9][0-9][0-9][0-9].json")):
        data = zbatch.read_json(path)
        chapter = data.get("chapter")
        if not isinstance(chapter, int):
            raise zbatch.ZBatchError(f"中性事件工件章号非法：{path}")
        for event in data.get("events") or []:
            event_id = event.get("event_id") if isinstance(event, dict) else None
            if not isinstance(event_id, str) or event_id in event_map:
                raise zbatch.ZBatchError(f"中性事件 ID 重复或非法：{event_id}")
            event_map[event_id] = event
            by_chapter[chapter].append(event)
    return event_map, dict(by_chapter)


def decision_reasons(
    data: Any,
    *,
    run_id: str,
    rules_sha256: str,
    event_ids: set[str],
) -> list[str]:
    """验收主控分类决定；所有事件必须一条不漏地显式处置。"""
    if not isinstance(data, dict):
        return ["分类决定不是对象"]
    reasons: list[str] = []
    if data.get("schema_version") != DECISION_SCHEMA_VERSION:
        reasons.append("分类决定schema错误")
    if data.get("run_id") != run_id:
        reasons.append("分类决定run_id错误")
    if data.get("rules_sha256") != rules_sha256:
        reasons.append("分类规则SHA不一致")
    decisions = data.get("decisions")
    if not isinstance(decisions, list):
        return sorted(set(reasons + ["decisions不是数组"]))

    seen: list[str] = []
    dispositions: dict[str, str] = {}
    for index, decision in enumerate(decisions, 1):
        label = f"决定{index}"
        if not isinstance(decision, dict):
            reasons.append(f"{label}不是对象")
            continue
        if set(decision) != DECISION_KEYS:
            reasons.append(f"{label}字段不等于固定合同")
        event_id = decision.get("event_id")
        if not isinstance(event_id, str) or event_id not in event_ids:
            reasons.append(f"{label}事件ID不存在")
            continue
        seen.append(event_id)
        disposition = decision.get("disposition")
        dispositions[event_id] = str(disposition)
        if disposition not in DISPOSITIONS:
            reasons.append(f"{event_id}处置状态非法")
        matched = decision.get("matched_types")
        if not isinstance(matched, list) or any(value not in "ABCD" for value in matched):
            reasons.append(f"{event_id}命中类型非法")
            matched = []
        if len(matched) != len(set(matched)):
            reasons.append(f"{event_id}命中类型重复")
        primary = decision.get("primary_type")
        rule_ids = decision.get("rule_ids")
        if not isinstance(rule_ids, list) or not rule_ids or any(not isinstance(value, str) for value in rule_ids):
            reasons.append(f"{event_id}缺规则编号")
        basis = decision.get("basis")
        if not isinstance(basis, str) or zbatch.nonspace_chars(basis) < 8:
            reasons.append(f"{event_id}分类依据过短")
        fields = decision.get("fields")
        related = decision.get("related_event_ids")
        duplicate_group = decision.get("duplicate_group")
        conflict_reason = decision.get("conflict_reason")
        if not isinstance(related, list) or any(not isinstance(value, str) for value in related):
            reasons.append(f"{event_id}关联事件ID非法")
            related = []
        if event_id in related:
            reasons.append(f"{event_id}关联事件自指")
        if duplicate_group is not None and (not isinstance(duplicate_group, str) or not duplicate_group.strip()):
            reasons.append(f"{event_id}重复组非法")
        if not isinstance(conflict_reason, str):
            reasons.append(f"{event_id}冲突说明不是字符串")
            conflict_reason = ""

        if disposition == "classified":
            if primary not in "ABCD" or primary not in matched:
                reasons.append(f"{event_id}主类型未包含在命中类型")
            required = set(zbatch.TYPE_REQUIRED_FIELDS.get(str(primary), ()))
            if not isinstance(fields, dict) or set(fields) != required:
                reasons.append(f"{event_id}分类字段与主类型不一致")
            elif any(not isinstance(value, str) or not value.strip() for value in fields.values()):
                reasons.append(f"{event_id}分类字段为空")
            if decision.get("assertion") not in zbatch.ALLOWED_ASSERTION:
                reasons.append(f"{event_id}事实等级非法")
            if not matched:
                reasons.append(f"{event_id}分类后无命中类型")
        else:
            if primary is not None or matched:
                reasons.append(f"{event_id}未分类或丢弃却带类型")
            if decision.get("assertion") is not None:
                reasons.append(f"{event_id}未分类或丢弃却带事实等级")
            if fields != {} or related:
                reasons.append(f"{event_id}未分类或丢弃却带记录字段")

        if (len(matched) > 1 or duplicate_group is not None) and zbatch.nonspace_chars(conflict_reason) < 8:
            reasons.append(f"{event_id}重叠或重复未写冲突说明")

    if len(seen) != len(set(seen)):
        reasons.append("分类决定事件ID重复")
    if set(seen) != event_ids:
        missing = sorted(event_ids - set(seen))
        extra = sorted(set(seen) - event_ids)
        reasons.append(f"分类决定未一对一覆盖事件：missing={missing},extra={extra}")

    classified_ids = {event_id for event_id, disposition in dispositions.items() if disposition == "classified"}
    for decision in decisions:
        if not isinstance(decision, dict) or decision.get("disposition") != "classified":
            continue
        event_id = str(decision.get("event_id"))
        for related_id in decision.get("related_event_ids") or []:
            if related_id not in classified_ids:
                reasons.append(f"{event_id}关联未成记录的事件")
            elif related_id.split("-")[1] != event_id.split("-")[1]:
                reasons.append(f"{event_id}关联跨章事件")

    return sorted(set(reasons))


def _coverage_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for kind in "ABCD":
        ids = [record["id"] for record in records if record["type"] == kind]
        result[kind] = {
            "status": "emitted" if ids else "none",
            "record_ids": ids,
            "reason": f"主控按独立规则逐事件裁定；{kind}类共{len(ids)}条，未命中者均在处置账显式登记。",
        }
    return result


def classify_and_verify(config_path: Path, decisions_path: Path) -> dict[str, Any]:
    pre = z00l_preflight(config_path, require_key=False)
    if pre.get("preflight") != "pass":
        raise zbatch.ZBatchError("Z00l 分类前预演未通过")
    batch, provider = zbatch.load_configs(config_path)
    run_dir = zbatch.RUNS_DIR / str(batch.get("run_id"))
    if not run_dir.is_dir():
        raise zbatch.ZBatchError("找不到 Z00l 中性事件运行")
    manifest = zbatch.read_json(run_dir / "run_manifest.json")
    if "event_extract" not in set(manifest.get("stages_completed") or []):
        raise zbatch.ZBatchError("中性事件阶段未完成")
    ctx = zbatch.initialize_run(batch, provider, pre, resume=True)
    zbatch.verify_provenance_snapshot(run_dir)

    rules_path = zbatch.root_path(str((batch.get("prompts") or {}).get("classifier_rules") or ""))
    rules_sha = zbatch.sha256_file(rules_path)
    decisions_path = zbatch.root_path(decisions_path)
    decisions_data = zbatch.read_json(decisions_path)
    event_map, events_by_chapter = load_events(run_dir)
    reasons = decision_reasons(
        decisions_data,
        run_id=str(batch.get("run_id")),
        rules_sha256=rules_sha,
        event_ids=set(event_map),
    )
    if reasons:
        raise zbatch.ZBatchError(f"主控分类决定无效：{reasons}")

    decisions = decisions_data["decisions"]
    decision_map = {decision["event_id"]: decision for decision in decisions}
    counters: Counter[tuple[int, str]] = Counter()
    record_id_map: dict[str, str] = {}
    for chapter in sorted(events_by_chapter):
        for event in events_by_chapter[chapter]:
            decision = decision_map[event["event_id"]]
            if decision["disposition"] != "classified":
                continue
            kind = decision["primary_type"]
            counters[(chapter, kind)] += 1
            record_id_map[event["event_id"]] = f"{kind}-C{chapter:04d}-{counters[(chapter, kind)]:02d}"

    chapters = zbatch.load_chapters(
        zbatch.root_path(batch["book_dir"]),
        int(batch["chapter_start"]),
        int(batch["chapter_end"]),
    )
    all_records: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    resolved_decisions: list[dict[str, Any]] = []
    raw_anchor_refs: dict[tuple[int, str], list[str]] = defaultdict(list)

    for chapter in sorted(events_by_chapter):
        chapter_records: list[dict[str, Any]] = []
        catalog_data = zbatch.read_json(
            run_dir / "01_event_extract" / "evidence_catalogs" / f"ch{chapter:04d}.json"
        )
        catalog_map = {
            str(row["anchor_id"]): str(row["quote"])
            for row in catalog_data.get("entries") or []
            if isinstance(row, dict) and row.get("anchor_id") and row.get("quote")
        }
        for event in events_by_chapter[chapter]:
            event_id = event["event_id"]
            decision = copy.deepcopy(decision_map[event_id])
            decision["record_id"] = record_id_map.get(event_id)
            resolved_decisions.append(decision)
            for anchor in event.get("anchors") or []:
                raw_anchor_refs[(chapter, str(anchor.get("anchor_id")))].append(event_id)
            if decision["disposition"] != "classified":
                continue
            kind = decision["primary_type"]
            record = {
                "id": record_id_map[event_id],
                "type": kind,
                **copy.deepcopy(decision["fields"]),
                "status": "开",
                "type_state": TYPE_STATE[kind],
                "assertion": decision["assertion"],
                "related_ids": [record_id_map[value] for value in decision["related_event_ids"]],
                "anchors": copy.deepcopy(event["anchors"]),
                "_source_event_id": event_id,
                "_classification_rule_ids": copy.deepcopy(decision["rule_ids"]),
            }
            record_for_validation = {key: value for key, value in record.items() if not key.startswith("_")}
            record_reasons, anchor_checks = zbatch.validate_record(
                record_for_validation,
                chapters,
                expected_chapter=chapter,
                evidence_catalog=catalog_map,
            )
            validation_rows.append({
                "source_chapter": chapter,
                "source_event_id": event_id,
                "record": record,
                "valid": not record_reasons,
                "reasons": record_reasons,
                "anchor_checks": anchor_checks,
            })
            chapter_records.append(record)
            all_records.append(record)

        envelope = {
            "schema_version": "z-candidate-v1",
            "chapter": chapter,
            "decision_markers": [
                f"分类权由主控规则执行；弱模型仅交中性事件。规则SHA={rules_sha}"
            ],
            "coverage_audit": _coverage_audit(chapter_records),
            "records": chapter_records,
        }
        envelope_reasons = zbatch.validate_candidate_envelope(envelope, chapter)
        if envelope_reasons:
            raise zbatch.ZBatchError(f"第 {chapter} 章分类后兼容外壳无效：{envelope_reasons}")
        zbatch.write_json(run_dir / "02_classify" / "parsed" / f"ch{chapter:04d}.json", envelope)

    invalid_rows = [row for row in validation_rows if not row["valid"]]
    valid_records = [row["record"] for row in validation_rows if row["valid"]]
    ids = [record["id"] for record in valid_records]
    if len(ids) != len(set(ids)):
        raise zbatch.ZBatchError("分类后记录ID重复")

    duplicate_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    matched_type_conflicts: list[dict[str, Any]] = []
    for decision in resolved_decisions:
        if len(decision["matched_types"]) > 1:
            matched_type_conflicts.append(decision)
        group = decision.get("duplicate_group")
        if group:
            duplicate_groups[str(group)].append(decision)
    duplicate_rows = []
    cross_type_duplicate_groups = 0
    for group, rows in sorted(duplicate_groups.items()):
        types = sorted({str(row.get("primary_type")) for row in rows if row.get("primary_type")})
        row = {
            "duplicate_group": group,
            "event_ids": [row["event_id"] for row in rows],
            "primary_types": types,
            "cross_type": len(types) > 1,
        }
        duplicate_rows.append(row)
        if row["cross_type"]:
            cross_type_duplicate_groups += 1

    shared_event_anchors = [
        {
            "chapter": chapter,
            "anchor_id": anchor_id,
            "event_ids": event_ids,
            "primary_types": sorted({
                str(decision_map[event_id].get("primary_type"))
                for event_id in event_ids
                if decision_map[event_id].get("primary_type")
            }),
        }
        for (chapter, anchor_id), event_ids in sorted(raw_anchor_refs.items())
        if len(set(event_ids)) > 1
    ]
    overlap = zbatch.cross_type_anchor_overlap(valid_records)
    dispositions = Counter(decision["disposition"] for decision in resolved_decisions)
    type_total = Counter(record["type"] for record in valid_records)
    metrics = {
        "event_total": len(event_map),
        "classified_total": dispositions["classified"],
        "unclassified_total": dispositions["unclassified"],
        "discarded_total": dispositions["discarded"],
        "candidate_total": len(validation_rows),
        "valid_total": len(valid_records),
        "invalid_total": len(invalid_rows),
        "anchor_valid_rate": round(len(valid_records) / len(validation_rows), 6) if validation_rows else 0.0,
        "by_type": {kind: type_total[kind] for kind in "ABCD"},
        "classification_model_calls": 0,
        "matched_type_conflict_count": len(matched_type_conflicts),
        "declared_duplicate_group_count": len(duplicate_rows),
        "cross_type_semantic_duplicate_groups": cross_type_duplicate_groups,
        "raw_shared_anchor_groups": len(shared_event_anchors),
        "emitted_cross_type_shared_anchor_count": overlap["shared_anchor_count"],
        "emitted_cross_type_pair_count": overlap["cross_type_pair_count"],
        "rules_sha256": rules_sha,
        "decisions_sha256": zbatch.sha256_file(decisions_path),
        "model_calls_total": ctx.calls_made,
    }

    zbatch.write_json(run_dir / "02_classify" / "classification_decisions_resolved.json", {
        "schema_version": DECISION_SCHEMA_VERSION,
        "run_id": batch.get("run_id"),
        "rules_sha256": rules_sha,
        "source_path": zbatch.rel(decisions_path),
        "source_sha256": zbatch.sha256_file(decisions_path),
        "decisions": resolved_decisions,
    })
    zbatch.write_json(run_dir / "02_classify" / "classification_conflicts.json", {
        "matched_type_conflicts": matched_type_conflicts,
        "declared_duplicate_groups": duplicate_rows,
        "raw_shared_anchor_groups": shared_event_anchors,
        "emitted_cross_type_anchor_overlap": overlap,
        "gate_note": "跨类型重复闸须结合本账人审；不得只因每事件单主类型而自动判过。",
    })
    zbatch.write_json(run_dir / "02_classify" / "metrics.json", metrics)
    zbatch.write_json(run_dir / "03_verify" / "validation_rows.json", validation_rows)
    zbatch.write_json(run_dir / "03_verify" / "valid_records.json", {"records": valid_records})
    zbatch.write_json(run_dir / "03_verify" / "invalid_records.json", {"rows": invalid_rows})
    zbatch.write_json(run_dir / "03_verify" / "metrics.json", metrics)
    zbatch.write_text(
        run_dir / "03_verify" / "程序核锚报告.md",
        "# Z00l 程序核锚报告\n\n"
        f"- 中性事件：{len(event_map)} 条\n"
        f"- 主控成记录：{len(validation_rows)} 条\n"
        f"- 过锚：{len(valid_records)} 条\n"
        f"- 未分类：{dispositions['unclassified']} 条\n"
        f"- 丢弃：{dispositions['discarded']} 条\n"
        f"- 分类阶段模型调用：0\n"
        f"- A/B/C/D：{type_total['A']}/{type_total['B']}/{type_total['C']}/{type_total['D']}\n"
        f"- 声明的跨类型语义重复组：{cross_type_duplicate_groups}\n"
        "\n来源：Codex\n",
    )
    if invalid_rows:
        zbatch.update_run_manifest(ctx, status="failed", error="主控分类后核锚失败")
        raise zbatch.ZBatchError(f"主控分类后有 {len(invalid_rows)} 条未过核锚")
    zbatch.update_run_manifest(ctx, status="running", stage="classify")
    zbatch.update_run_manifest(ctx, status="completed", stage="verify")
    return {
        "run_id": batch.get("run_id"),
        "run_dir": zbatch.rel(run_dir),
        "calls_made": ctx.calls_made,
        "results": {"classify": metrics, "verify": metrics},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Z00l 分类收权单变量适配器")
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight", help="零调用预演")
    pre.add_argument("--config", required=True)
    extract = sub.add_parser("extract", help="只让弱模型抽中性事件")
    extract.add_argument("--config", required=True)
    classify = sub.add_parser("classify", help="主控零调用分类并核锚")
    classify.add_argument("--config", required=True)
    classify.add_argument("--decisions", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config_path = zbatch.root_path(args.config)
        if args.command == "preflight":
            result = z00l_preflight(config_path, require_key=False)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("preflight") == "pass" else 2
        if args.command == "extract":
            result = extract_events(config_path)
        elif args.command == "classify":
            result = classify_and_verify(config_path, Path(args.decisions))
        else:  # pragma: no cover
            raise zbatch.ZBatchError(f"未知命令：{args.command}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except zbatch.ZBatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

