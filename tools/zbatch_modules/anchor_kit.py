"""模块 2：冻结锚物化与逐字核锚。"""

from __future__ import annotations

import copy
import re
from typing import Any

from .evidence_catalog import nonspace_chars
from .errors import ZBatchError


TYPE_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "A": ("story_line", "delta", "direct_cause", "future_use"),
    "B": ("trigger_condition", "trigger_action"),
    "C": ("reader_expectation", "payoff_test"),
    "D": ("condition", "consequence", "scope_exception"),
}
ALLOWED_STATUS = {"开", "收", "废"}
ALLOWED_ASSERTION = {"明", "推", "存疑"}
RECORD_ID_PATTERN = re.compile(r"^[ABCD]-(?:C\d{4}-\d{2}|\d{4})$")


AnchorContractError = ZBatchError


def materialize_anchor_ids(
    data: dict[str, Any],
    catalog: list[dict[str, Any]],
    chapter: int,
) -> dict[str, Any]:
    """把模型选择的目录 ID 确定性展开成章号和原文短引。"""
    result = copy.deepcopy(data)
    catalog_map = {
        str(entry.get("anchor_id")): str(entry.get("quote"))
        for entry in catalog
        if isinstance(entry, dict) and entry.get("anchor_id") and entry.get("quote")
    }
    materialized = 0
    unresolved = 0
    for record in result.get("records") or []:
        if not isinstance(record, dict) or not isinstance(record.get("anchors"), list):
            continue
        for anchor in record["anchors"]:
            if not isinstance(anchor, dict):
                unresolved += 1
                continue
            anchor_id = anchor.get("anchor_id")
            if not isinstance(anchor_id, str) or anchor_id not in catalog_map:
                unresolved += 1
                continue
            anchor.clear()
            anchor.update({
                "chapter": chapter,
                "anchor_id": anchor_id,
                "quote": catalog_map[anchor_id],
            })
            materialized += 1
    result["_anchor_materialization"] = {
        "mode": "frozen_catalog_id_lookup",
        "materialized": materialized,
        "unresolved": unresolved,
    }
    return result


def materialize_anchors_from_sources(
    items: Any,
    source_records: dict[str, dict[str, Any]],
    *,
    source_field: str,
) -> list[Any]:
    """按来源记录 ID 聚合原锚；模型不再负责复制 chapter/quote。"""
    if not isinstance(items, list):
        raise AnchorContractError("待解引用工件不是数组")
    result = copy.deepcopy(items)
    for item in result:
        if not isinstance(item, dict):
            continue
        source_ids = item.get(source_field)
        anchors: list[dict[str, Any]] = []
        unresolved: list[str] = []
        seen: set[tuple[Any, Any, Any]] = set()
        if isinstance(source_ids, list):
            for source_id in source_ids:
                source = source_records.get(str(source_id))
                if source is None:
                    unresolved.append(str(source_id))
                    continue
                for anchor in source.get("anchors") or []:
                    if not isinstance(anchor, dict):
                        continue
                    key = (anchor.get("chapter"), anchor.get("anchor_id"), anchor.get("quote"))
                    if key in seen:
                        continue
                    seen.add(key)
                    anchors.append(copy.deepcopy(anchor))
        item["anchors"] = anchors
        item["_anchor_materialization"] = {
            "mode": f"source_record_lookup:{source_field}",
            "resolved_sources": len(source_ids or []) - len(unresolved) if isinstance(source_ids, list) else 0,
            "unresolved_source_ids": unresolved,
        }
    return result


def validate_anchors(
    anchors: Any,
    chapters: dict[int, dict[str, Any]],
    *,
    expected_chapter: int | None = None,
    evidence_catalog: dict[str, str] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    reasons: list[str] = []
    checks: list[dict[str, Any]] = []
    if not isinstance(anchors, list) or not anchors:
        return ["无锚"], checks
    for index, anchor in enumerate(anchors, 1):
        row: dict[str, Any] = {"index": index, "valid": False}
        if not isinstance(anchor, dict):
            reasons.append("锚不是对象")
            checks.append(row)
            continue
        chapter = anchor.get("chapter")
        quote = anchor.get("quote")
        anchor_id = anchor.get("anchor_id")
        row.update({"chapter": chapter, "quote": quote, "anchor_id": anchor_id})
        if evidence_catalog is not None:
            if not isinstance(anchor_id, str) or anchor_id not in evidence_catalog:
                reasons.append("证据目录ID不存在")
            elif quote != evidence_catalog[anchor_id]:
                reasons.append("证据目录短引不一致")
        if not isinstance(chapter, int) or chapter not in chapters:
            reasons.append("锚章号不存在")
            checks.append(row)
            continue
        if expected_chapter is not None and chapter != expected_chapter:
            reasons.append("越界混账")
        if not isinstance(quote, str) or not quote:
            reasons.append("无锚")
            checks.append(row)
            continue
        count = nonspace_chars(quote)
        row["nonspace_chars"] = count
        row["exact_hit"] = quote in chapters[chapter]["text"]
        if count < 10 or count > 25:
            reasons.append("短引长度越界")
        if not row["exact_hit"]:
            reasons.append("短引不命中")
        row["valid"] = count >= 10 and count <= 25 and row["exact_hit"] and (
            expected_chapter is None or chapter == expected_chapter
        )
        checks.append(row)
    return sorted(set(reasons)), checks


def validate_record(
    record: Any,
    chapters: dict[int, dict[str, Any]],
    *,
    expected_chapter: int | None = None,
    require_sources: bool = False,
    allowed_source_ids: set[str] | None = None,
    evidence_catalog: dict[str, str] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    if not isinstance(record, dict):
        return ["记录不是对象"], []
    reasons: list[str] = []
    record_id = record.get("id")
    record_type = record.get("type")
    if not isinstance(record_id, str) or not record_id.strip():
        reasons.append("缺ID")
    if record_type not in TYPE_REQUIRED_FIELDS:
        reasons.append("类型非法")
    else:
        for field in TYPE_REQUIRED_FIELDS[record_type]:
            if not isinstance(record.get(field), str) or not str(record.get(field)).strip():
                reasons.append(f"缺字段:{field}")
    if record.get("status") not in ALLOWED_STATUS:
        reasons.append("态非法")
    if record.get("assertion") not in ALLOWED_ASSERTION:
        reasons.append("事实等级非法")
    related_ids = record.get("related_ids")
    if not isinstance(related_ids, list):
        reasons.append("关联ID不是数组")
    else:
        if any(not isinstance(value, str) or not RECORD_ID_PATTERN.fullmatch(value) for value in related_ids):
            reasons.append("关联ID格式非法")
        if len(related_ids) != len(set(value for value in related_ids if isinstance(value, str))):
            reasons.append("关联ID重复")
        if isinstance(record_id, str) and record_id in related_ids:
            reasons.append("关联ID自指")

    source_ids = record.get("source_record_ids")
    if require_sources and (not isinstance(source_ids, list) or not source_ids):
        reasons.append("缺来源候选ID")
    if isinstance(source_ids, list) and allowed_source_ids is not None:
        unknown = [value for value in source_ids if value not in allowed_source_ids]
        if unknown:
            reasons.append("来源候选ID不存在")

    anchor_reasons, anchor_checks = validate_anchors(
        record.get("anchors"),
        chapters,
        expected_chapter=expected_chapter,
        evidence_catalog=evidence_catalog,
    )
    reasons.extend(anchor_reasons)
    return sorted(set(reasons)), anchor_checks
