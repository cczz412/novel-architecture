"""模块 6：中性事件提取合同与程序清点。

本模块不发 API 请求。它负责构造与 Z00n 相同的请求消息、严格验收模型 JSON、
从实际 ``events`` 生成程序清点账，并把冻结证据 ID 确定性展开成短引。
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from .errors import ZBatchError
from .evidence_catalog import nonspace_chars
from .prompt_render_pin import load_pinned_text, prompt_sha256, sha256_bytes, render_prompt


EVENT_SCHEMA_VERSION = "z-event-v1"
AUDIT_SCHEMA_VERSION = "z-program-event-audit-v1"
ROOT_KEYS = {"schema_version", "chapter", "events"}
EVENT_KEYS = {"event_id", "event", "anchors"}
ANCHOR_KEYS = {"anchor_id"}
EVENT_ID_PATTERN = re.compile(r"^EV-C(?P<chapter>\d{4})-(?P<serial>\d{2})$")
CLASSIFICATION_LABELS = (
    "A类",
    "B类",
    "C类",
    "D类",
    "跨章因果",
    "故事内触发器",
    "读者承诺",
    "世界规则",
)
SYSTEM_MESSAGE = "你只做证据约束的中性事件摘取，不做类型判断。只输出合法 JSON。"


def build_messages(
    *,
    prompt_path: Path,
    expected_prompt_sha256: str,
    chapter: int,
    chapter_filename: str,
    catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    """渲染可交给运输层的完整 messages，并返回所有确定性指纹。"""
    template = load_pinned_text(prompt_path, expected_prompt_sha256)
    catalog_json = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    user_prompt = render_prompt(
        template,
        {
            "CHAPTER_NUMBER": str(chapter),
            "CHAPTER_PADDED": f"{chapter:04d}",
            "CHAPTER_FILENAME": chapter_filename,
            "EVIDENCE_CATALOG_JSON": catalog_json,
        },
    )
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": user_prompt},
        ],
        "template_sha256": expected_prompt_sha256,
        "prompt_sha256": prompt_sha256(user_prompt),
        "catalog_sha256": sha256_bytes(catalog_json.encode("utf-8")),
    }


def audit_event_envelope(
    data: Any,
    chapter: int,
    catalog: list[dict[str, Any]],
) -> tuple[list[str], dict[str, Any]]:
    """从模型实际交出的 events 生成严格清点账；不声称语义无遗漏。"""
    reasons: list[str] = []
    catalog_ids = {
        str(row.get("anchor_id"))
        for row in catalog
        if isinstance(row, dict) and isinstance(row.get("anchor_id"), str)
    }
    observed_event_ids: list[str] = []
    used_anchor_ids: list[str] = []
    missing_anchor_ids: list[str] = []
    duplicate_anchor_events: list[str] = []
    events_with_anchors = 0
    events_without_anchors = 0
    invalid_event_id_count = 0

    if not isinstance(data, dict):
        reasons.append("回包不是对象")
        events: Any = []
    else:
        if set(data) != ROOT_KEYS:
            reasons.append("事件外壳字段不等于固定合同")
        if data.get("schema_version") != EVENT_SCHEMA_VERSION:
            reasons.append("事件schema错误")
        if data.get("chapter") != chapter:
            reasons.append("章号错误")
        events = data.get("events")
        if not isinstance(events, list):
            reasons.append("events不是数组")
            events = []

    expected_ids = [f"EV-C{chapter:04d}-{index:02d}" for index in range(1, len(events) + 1)]
    for index, event in enumerate(events, 1):
        expected_id = expected_ids[index - 1]
        if not isinstance(event, dict):
            reasons.append("事件不是对象")
            invalid_event_id_count += 1
            events_without_anchors += 1
            continue
        if set(event) != EVENT_KEYS:
            reasons.append(f"{expected_id}字段越出中性事件合同")

        event_id = event.get("event_id")
        if isinstance(event_id, str):
            observed_event_ids.append(event_id)
        match = EVENT_ID_PATTERN.fullmatch(event_id) if isinstance(event_id, str) else None
        if match is None:
            reasons.append(f"{expected_id}事件ID非法")
            invalid_event_id_count += 1
        else:
            if int(match.group("chapter")) != chapter:
                reasons.append(f"{event_id}事件ID章号错误")
            if event_id != expected_id:
                reasons.append(f"{event_id}事件ID不连续")

        summary = event.get("event")
        if not isinstance(summary, str) or not 6 <= nonspace_chars(summary) <= 100:
            reasons.append(f"{expected_id}事件摘要长度非法")
        elif any(label in summary for label in CLASSIFICATION_LABELS):
            reasons.append(f"{expected_id}夹带分类标签")

        anchors = event.get("anchors")
        if not isinstance(anchors, list) or not anchors:
            reasons.append(f"{expected_id}无冻结证据ID")
            events_without_anchors += 1
            continue
        events_with_anchors += 1
        event_anchor_ids: list[str] = []
        for anchor in anchors:
            if not isinstance(anchor, dict) or set(anchor) != ANCHOR_KEYS:
                reasons.append(f"{expected_id}证据字段越出合同")
                continue
            anchor_id = anchor.get("anchor_id")
            if not isinstance(anchor_id, str):
                reasons.append(f"{expected_id}证据目录ID不存在")
                continue
            event_anchor_ids.append(anchor_id)
            used_anchor_ids.append(anchor_id)
            if anchor_id not in catalog_ids:
                reasons.append(f"{expected_id}证据目录ID不存在")
                missing_anchor_ids.append(anchor_id)
        if len(event_anchor_ids) != len(set(event_anchor_ids)):
            reasons.append(f"{expected_id}证据目录ID重复")
            duplicate_anchor_events.append(str(event_id or expected_id))

    if len(observed_event_ids) != len(set(observed_event_ids)):
        reasons.append("事件ID重复")
    if observed_event_ids != expected_ids:
        reasons.append("事件ID集合或顺序不连续")

    unique_reasons = sorted(set(reasons))
    audit = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "chapter": chapter,
        "status": "pass" if not unique_reasons else "fail",
        "event_count": len(events),
        "event_ids": observed_event_ids,
        "event_ids_contiguous": observed_event_ids == expected_ids and invalid_event_id_count == 0,
        "invalid_event_id_count": invalid_event_id_count,
        "events_with_anchors": events_with_anchors,
        "events_without_anchors": events_without_anchors,
        "anchor_reference_count": len(used_anchor_ids),
        "catalog_anchor_count": len(catalog_ids),
        "used_anchor_ids": list(dict.fromkeys(used_anchor_ids)),
        "missing_catalog_anchor_ids": sorted(set(missing_anchor_ids)),
        "duplicate_anchor_event_ids": sorted(set(duplicate_anchor_events)),
        "reasons": unique_reasons,
        "scope_note": "只清点模型实际输出并核对冻结证据ID；不声称语义无遗漏。",
    }
    return unique_reasons, audit


def materialize_events(
    data: dict[str, Any],
    catalog: list[dict[str, Any]],
    chapter: int,
) -> dict[str, Any]:
    """把事件引用的冻结 ID 确定性展开成章号与连续短引。"""
    catalog_map = {
        str(row.get("anchor_id")): str(row.get("quote"))
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


def process_model_data(
    data: Any,
    *,
    chapter: int,
    catalog: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """严格验收后返回展开事件与程序账；失败即中止，不做修补。"""
    reasons, audit = audit_event_envelope(data, chapter, catalog)
    if reasons:
        raise ZBatchError(f"第 {chapter} 章中性事件回包无效：{reasons}；不做二次生成")
    assert isinstance(data, dict)
    return materialize_events(data, catalog, chapter), audit
