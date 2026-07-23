"""模块 3：模型 JSON 与候选外壳验收；只判，不修。"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from .errors import ZBatchError

RECORD_ID_PATTERN = re.compile(r"^[ABCD]-(?:C\d{4}-\d{2}|\d{4})$")


CandidateContractError = ZBatchError


def parse_json_content(content: str) -> dict[str, Any]:
    """只剥一层常见代码围栏，不修补模型 JSON。"""
    text = (content or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CandidateContractError(f"模型返回不是合法 JSON；不做二次缝补：{exc}") from exc
    if not isinstance(data, dict):
        raise CandidateContractError("模型 JSON 顶层不是对象；不做二次缝补")
    return data


def validate_candidate_coverage_audit(data: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    records = data.get("records")
    if not isinstance(records, list):
        return ["records不是数组"]
    record_ids_by_type: dict[str, list[str]] = {kind: [] for kind in "ABCD"}
    for record in records:
        if not isinstance(record, dict):
            continue
        record_type = record.get("type")
        record_id = record.get("id")
        if record_type in record_ids_by_type and isinstance(record_id, str):
            record_ids_by_type[record_type].append(record_id)
    audit = data.get("coverage_audit")
    if not isinstance(audit, dict):
        return ["缺四类覆盖清点"]
    missing_types = sorted(set("ABCD") - set(audit))
    extra_types = sorted(set(audit) - set("ABCD"))
    if missing_types:
        reasons.append("覆盖清点缺类型")
    if extra_types:
        reasons.append("覆盖清点多余类型")
    for kind in "ABCD":
        item = audit.get(kind)
        if not isinstance(item, dict):
            reasons.append(f"{kind}类覆盖清点不是对象")
            continue
        status = item.get("status")
        audit_ids = item.get("record_ids")
        reason = item.get("reason")
        expected_ids = record_ids_by_type[kind]
        if status not in {"emitted", "none"}:
            reasons.append(f"{kind}类覆盖状态非法")
        if not isinstance(audit_ids, list) or any(not isinstance(value, str) for value in audit_ids):
            reasons.append(f"{kind}类覆盖记录ID非法")
            audit_ids = []
        if len(audit_ids) != len(set(audit_ids)):
            reasons.append(f"{kind}类覆盖记录ID重复")
        if sorted(audit_ids) != sorted(expected_ids):
            reasons.append(f"{kind}类覆盖记录ID与输出不一致")
        if expected_ids and status != "emitted":
            reasons.append(f"{kind}类有输出却未标emitted")
        if not expected_ids and status != "none":
            reasons.append(f"{kind}类无输出却未标none")
        if not isinstance(reason, str) or len(re.sub(r"\s+", "", reason)) < 8:
            reasons.append(f"{kind}类覆盖理由过短")
    return sorted(set(reasons))


def validate_candidate_envelope(data: dict[str, Any], chapter: int) -> list[str]:
    reasons: list[str] = []
    if data.get("schema_version") != "z-candidate-v1":
        reasons.append("schema_version错误")
    if data.get("chapter") != chapter:
        reasons.append("章号错误")
    if not isinstance(data.get("decision_markers"), list):
        reasons.append("decision_markers不是数组")
    records = data.get("records")
    if isinstance(records, list):
        record_ids = {
            record.get("id")
            for record in records
            if isinstance(record, dict) and isinstance(record.get("id"), str)
        }
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("related_ids"), list):
                continue
            if any(
                isinstance(value, str)
                and RECORD_ID_PATTERN.fullmatch(value)
                and value not in record_ids
                for value in record["related_ids"]
            ):
                reasons.append("关联ID不存在于本章候选")
    reasons.extend(validate_candidate_coverage_audit(data))
    return sorted(set(reasons))


def cross_type_anchor_overlap(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_anchor: dict[tuple[int, str], list[dict[str, str]]] = defaultdict(list)
    for record in records:
        if not isinstance(record, dict):
            continue
        record_id = record.get("id")
        record_type = record.get("type")
        if not isinstance(record_id, str) or record_type not in {"A", "B", "C", "D"}:
            continue
        seen: set[tuple[int, str]] = set()
        for anchor in record.get("anchors") or []:
            if not isinstance(anchor, dict):
                continue
            chapter = anchor.get("chapter")
            anchor_id = anchor.get("anchor_id")
            if not isinstance(chapter, int) or not isinstance(anchor_id, str):
                continue
            key = (chapter, anchor_id)
            if key in seen:
                continue
            seen.add(key)
            by_anchor[key].append({"record_id": record_id, "type": record_type})

    rows: list[dict[str, Any]] = []
    pair_count = 0
    for (chapter, anchor_id), refs in sorted(by_anchor.items()):
        cross_pairs = sum(
            1
            for left in range(len(refs))
            for right in range(left + 1, len(refs))
            if refs[left]["type"] != refs[right]["type"]
        )
        if not cross_pairs:
            continue
        pair_count += cross_pairs
        rows.append({
            "chapter": chapter,
            "anchor_id": anchor_id,
            "record_ids": [ref["record_id"] for ref in refs],
            "types": [ref["type"] for ref in refs],
            "cross_type_pair_count": cross_pairs,
        })
    return {
        "shared_anchor_count": len(rows),
        "cross_type_pair_count": pair_count,
        "rows": rows,
        "role": "诊断项；共享锚不自动判废，需判断是否为同一原始事实重写",
    }
