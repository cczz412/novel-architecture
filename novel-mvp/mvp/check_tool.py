"""M7 零 API、LOCAL_FILESYSTEM_ONLY 的健康报告文件工具。

核心 ``execute(request, finding_provider)`` 只吃内存对象。provider 是唯一
MODEL_PROVIDER_SWAP_POINT；本模块只提供冻结离线映射实现，不调用模型。
输出沿用现行 C6 v1 顶层形状，``scan.excluded_counts`` 只是本地工具遥测，
不冻结新的正式 C6 字段。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Protocol

from jsonschema import Draft202012Validator


TRANSPORT_SCOPE = "LOCAL_FILESYSTEM_ONLY"
MODEL_PROVIDER_SWAP_POINT = "finding_provider"
COORDINATE_BASIS = "CHAPTER_REVISION_TEXT_UNICODE_CODEPOINT_0_BASED_HALF_OPEN"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FACT_ID_RE = re.compile(r"^f[0-9]{3,}$")
CONFLICT_ID_RE = re.compile(r"^h[0-9]{3,}$")
INSUFFICIENT_ID_RE = re.compile(r"^n[0-9]{3,}$")
REVISION_REF_KEYS = {"chapter_id", "revision_no", "revision_text_sha256"}
ANCHOR_REF_KEYS = {
    "chapter_id",
    "revision_no",
    "revision_text_sha256",
    "coordinate_basis",
    "start",
    "end",
    "slice_sha256",
}
C4_REQUIRED_KEYS = {
    "contract",
    "version",
    "id",
    "chapter_id",
    "text",
    "quote",
    "status",
    "source",
    "note",
    "added_at",
    "chapter_revision_ref",
    "anchor_ref",
    "anchor_state",
    "recheck",
}
C4_ALLOWED_KEYS = C4_REQUIRED_KEYS | {"seg", "decided_at"}
KINDS = ("naming", "timeline", "setting", "event")
SCOPE_KINDS = {"entity", "timeline", "leftover"}
PROVIDER_FINDING_KEYS = {
    "fact_ids",
    "kind",
    "verdict",
    "severity",
    "hard",
    "confidence",
    "note",
}
EXCLUDED_COUNT_KEYS = (
    "invalid_c4_v1",
    "rejected",
    "needs_recheck",
    "current_revision_missing",
    "stale_revision",
    "unverified_evidence",
    "invalid_evidence",
    "duplicate_dropped",
)
C6_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "C11_CHAPTER_REVISION_LEDGER.schema.json"
)
C6_REPORT_KEYS = {
    "contract",
    "version",
    "project",
    "generated_at",
    "model",
    "chapter_revision_refs",
    "source_revision_state",
    "scan",
    "conflicts",
    "insufficient",
    "alias_hints",
    "integrity",
    "summary",
}
SCAN_KEYS = {
    "facts_total",
    "confirmed",
    "extracted",
    "rejected_excluded",
    "duplicate_dropped",
    "api_calls",
    "failed_calls",
    "clean_groups",
    "total_tokens",
    "seconds",
    "groups",
    "excluded_counts",
}
GROUP_KEYS = {"name", "kind", "facts", "status", "findings"}
FINDING_KEYS = {
    "issue_id",
    "kind",
    "layer",
    "fact_ids",
    "note",
    "next_step",
    "evidence",
    "found_by",
    "confidence",
    "hard",
}
EVIDENCE_KEYS = {
    "fact_id",
    "chapter_id",
    "seg",
    "status",
    "text",
    "quote",
    "chapter_revision_ref",
    "anchor_ref",
}
ALIAS_HINT_KEYS = {
    "hint_id",
    "names",
    "fact_ids_a",
    "fact_ids_b",
    "note",
}
INTEGRITY_KEYS = {"duplicate_ids", "note", "next_step"}
DUPLICATE_KEYS = {"problem", "id", "kept", "dropped"}
LOCATION_KEYS = {"chapter_id", "seg", "text"}
SUMMARY_KEYS = {
    "red",
    "yellow",
    "by_layer",
    "by_kind",
    "insufficient",
    "alias_hints",
    "duplicate_ids",
}


class CheckToolError(ValueError):
    """输入、冻结 provider 或整批 finding 不满足现行判法。"""


class FindingProvider(Protocol):
    provider_id: str
    model_calls: int

    def find(self, batch: dict[str, Any]) -> dict[str, Any]: ...


class FrozenFindingProvider:
    """从只读离线对象返回一份冻结 finding response。"""

    def __init__(self, frozen: dict[str, Any]):
        if not isinstance(frozen, dict) or set(frozen) != {
            "provider_id",
            "model_calls",
            "response",
        }:
            raise CheckToolError(
                "冻结 responses 只允许 provider_id、model_calls、response"
            )
        if not isinstance(frozen["provider_id"], str) or not frozen[
            "provider_id"
        ].strip():
            raise CheckToolError("provider_id 必须是非空字符串")
        if frozen["model_calls"] != 0:
            raise CheckToolError("本票只接受 model_calls=0 的冻结响应")
        if not isinstance(frozen["response"], dict):
            raise CheckToolError("response 必须是对象")
        self.provider_id = frozen["provider_id"]
        self.model_calls = 0
        self._response = copy.deepcopy(frozen["response"])

    def find(self, batch: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(batch, dict):
            raise CheckToolError("provider batch 必须是对象")
        return copy.deepcopy(self._response)


def _is_int(value: object, *, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _valid_revision_ref(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == REVISION_REF_KEYS
        and isinstance(value.get("chapter_id"), str)
        and bool(value["chapter_id"])
        and _is_int(value.get("revision_no"), minimum=1)
        and _valid_sha256(value.get("revision_text_sha256"))
    )


def _current_revision_index(raw_refs: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_refs, list):
        raise CheckToolError("current_revision_refs 必须是列表")
    result: dict[str, dict[str, Any]] = {}
    for index, ref in enumerate(raw_refs):
        if not _valid_revision_ref(ref):
            raise CheckToolError(
                f"current_revision_refs[{index}] 不是合法 revision ref"
            )
        chapter_id = ref["chapter_id"]
        if chapter_id in result:
            raise CheckToolError(f"current revision 重复：{chapter_id}")
        result[chapter_id] = copy.deepcopy(ref)
    return result


def _c4_identity_valid(fact: object) -> bool:
    return (
        isinstance(fact, dict)
        and C4_REQUIRED_KEYS <= set(fact) <= C4_ALLOWED_KEYS
        and fact.get("contract") == "C4_FACT_QUERY"
        and fact.get("version") == "v1"
        and isinstance(fact.get("id"), str)
        and FACT_ID_RE.fullmatch(fact["id"]) is not None
        and isinstance(fact.get("chapter_id"), str)
        and bool(fact["chapter_id"])
        and isinstance(fact.get("text"), str)
        and bool(fact["text"])
        and isinstance(fact.get("quote"), str)
        and isinstance(fact.get("source"), str)
        and bool(fact["source"])
    )


def _anchor_valid(fact: dict[str, Any]) -> bool:
    revision_ref = fact.get("chapter_revision_ref")
    anchor = fact.get("anchor_ref")
    quote = fact.get("quote")
    if (
        fact.get("anchor_state") != "VERIFIED"
        or fact.get("recheck") is not None
        or not _valid_revision_ref(revision_ref)
        or not isinstance(anchor, dict)
        or set(anchor) != ANCHOR_REF_KEYS
        or not isinstance(quote, str)
        or not quote
    ):
        return False
    if any(anchor.get(key) != revision_ref[key] for key in REVISION_REF_KEYS):
        return False
    start, end = anchor.get("start"), anchor.get("end")
    if (
        anchor.get("coordinate_basis") != COORDINATE_BASIS
        or not _is_int(start, minimum=0)
        or not _is_int(end, minimum=1)
        or start >= end
        or end - start != len(quote)
        or not _valid_sha256(anchor.get("slice_sha256"))
    ):
        return False
    return anchor["slice_sha256"] == hashlib.sha256(quote.encode("utf-8")).hexdigest()


def _loc(fact: dict[str, Any]) -> dict[str, Any]:
    return {
        "chapter_id": fact["chapter_id"],
        "seg": fact.get("seg"),
        "text": fact["text"][:40],
    }


def _eligible_facts(
    raw_facts: object,
    current_refs: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, Any]]]:
    if not isinstance(raw_facts, list):
        raise CheckToolError("facts 必须是 C4 v1 对象列表")
    counts = {key: 0 for key in EXCLUDED_COUNT_KEYS}
    eligible_before_dedupe: list[dict[str, Any]] = []
    for fact in raw_facts:
        if not _c4_identity_valid(fact):
            counts["invalid_c4_v1"] += 1
            continue
        status = fact["status"]
        if status == "rejected":
            counts["rejected"] += 1
            continue
        if status == "needs_recheck":
            counts["needs_recheck"] += 1
            continue
        if status not in {"confirmed", "extracted"}:
            counts["invalid_c4_v1"] += 1
            continue
        revision_ref = fact["chapter_revision_ref"]
        if (
            not _valid_revision_ref(revision_ref)
            or revision_ref["chapter_id"] != fact["chapter_id"]
        ):
            counts["invalid_c4_v1"] += 1
            continue
        current_ref = current_refs.get(fact["chapter_id"])
        if current_ref is None:
            counts["current_revision_missing"] += 1
            continue
        if revision_ref != current_ref:
            counts["stale_revision"] += 1
            continue
        if fact["anchor_state"] != "VERIFIED":
            counts["unverified_evidence"] += 1
            continue
        if not _anchor_valid(fact):
            counts["invalid_evidence"] += 1
            continue
        eligible_before_dedupe.append(copy.deepcopy(fact))

    kept_by_id: dict[str, dict[str, Any]] = {}
    dropped_by_id: dict[str, list[dict[str, Any]]] = {}
    for fact in eligible_before_dedupe:
        fact_id = fact["id"]
        if fact_id in kept_by_id:
            dropped_by_id.setdefault(fact_id, []).append(fact)
        else:
            kept_by_id[fact_id] = fact
    duplicate_records = [
        {
            "problem": "duplicate_id",
            "id": fact_id,
            "kept": _loc(kept_by_id[fact_id]),
            "dropped": [_loc(fact) for fact in dropped],
        }
        for fact_id, dropped in dropped_by_id.items()
    ]
    counts["duplicate_dropped"] = sum(
        len(record["dropped"]) for record in duplicate_records
    )
    return list(kept_by_id.values()), counts, duplicate_records


def _validate_check_config(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != {
        "scope_name",
        "scope_kind",
        "kinds",
    }:
        raise CheckToolError(
            "check_config 只允许 scope_name、scope_kind、kinds"
        )
    if not isinstance(raw["scope_name"], str) or not raw["scope_name"].strip():
        raise CheckToolError("scope_name 必须是非空字符串")
    if raw["scope_kind"] not in SCOPE_KINDS:
        raise CheckToolError("scope_kind 必须是 entity/timeline/leftover")
    kinds = raw["kinds"]
    if (
        not isinstance(kinds, list)
        or not kinds
        or any(not isinstance(kind, str) or kind not in KINDS for kind in kinds)
        or len(kinds) != len(set(kinds))
    ):
        raise CheckToolError("kinds 必须是无重复的现行检查类型列表")
    return copy.deepcopy(raw)


def _expected_severity(
    finding: dict[str, Any],
    *,
    layer: str | None = None,
) -> str | None:
    if finding["verdict"] == "insufficient":
        return None
    if finding["kind"] == "timeline":
        return "yellow"
    if layer is not None and layer != "confirmed":
        return "yellow"
    if finding["hard"] and finding["confidence"] == "high":
        return "red"
    return "yellow"


def _provider_findings(
    response: object,
    *,
    known_fact_ids: set[str],
    allowed_kinds: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(response, dict) or set(response) != {"findings"}:
        raise CheckToolError("provider response 只允许 findings")
    raw_findings = response["findings"]
    if not isinstance(raw_findings, list):
        raise CheckToolError("provider findings 必须是列表")
    validated: list[dict[str, Any]] = []
    seen_sets: set[frozenset[str]] = set()
    for index, finding in enumerate(raw_findings):
        label = f"findings[{index}]"
        if not isinstance(finding, dict) or set(finding) != PROVIDER_FINDING_KEYS:
            raise CheckToolError(f"{label} 字段缺失或多出字段")
        fact_ids = finding["fact_ids"]
        if (
            not isinstance(fact_ids, list)
            or len(fact_ids) < 2
            or any(not isinstance(fact_id, str) for fact_id in fact_ids)
            or len(fact_ids) != len(set(fact_ids))
        ):
            raise CheckToolError(f"{label}.fact_ids 必须含至少两个唯一事实号")
        unknown = sorted(set(fact_ids) - known_fact_ids)
        if unknown:
            raise CheckToolError(f"{label} 引用未知 fact：{', '.join(unknown)}")
        if finding["kind"] not in allowed_kinds:
            raise CheckToolError(f"{label}.kind 不在显式检查范围")
        if finding["verdict"] not in {"conflict", "insufficient"}:
            raise CheckToolError(f"{label}.verdict 非法")
        if not isinstance(finding["hard"], bool):
            raise CheckToolError(f"{label}.hard 必须是布尔值")
        if finding["confidence"] not in {"high", "low"}:
            raise CheckToolError(f"{label}.confidence 非法")
        if (
            not isinstance(finding["note"], str)
            or not finding["note"].strip()
            or len(finding["note"]) > 300
        ):
            raise CheckToolError(f"{label}.note 必须是 1–300 字符")
        if finding["verdict"] == "insufficient" and finding["hard"]:
            raise CheckToolError(f"{label} 材料不足不能标 hard")
        if finding["verdict"] == "conflict":
            if finding["severity"] not in {"red", "yellow"}:
                raise CheckToolError(f"{label}.severity 非法")
        elif finding["severity"] is not None:
            raise CheckToolError(f"{label} 材料不足时 severity 必须为空")
        fact_set = frozenset(fact_ids)
        if fact_set in seen_sets:
            raise CheckToolError(f"{label} 重复报告同一组事实")
        seen_sets.add(fact_set)
        validated.append(copy.deepcopy(finding))
    return validated


def _evidence(fact_ids: list[str], by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "fact_id": fact_id,
            "chapter_id": by_id[fact_id]["chapter_id"],
            "seg": by_id[fact_id].get("seg"),
            "status": by_id[fact_id]["status"],
            "text": by_id[fact_id]["text"],
            "quote": by_id[fact_id]["quote"],
            "chapter_revision_ref": copy.deepcopy(
                by_id[fact_id]["chapter_revision_ref"]
            ),
            "anchor_ref": copy.deepcopy(by_id[fact_id]["anchor_ref"]),
        }
        for fact_id in fact_ids
    ]


def _layer_from_statuses(statuses: set[str]) -> str:
    if statuses == {"confirmed"}:
        return "confirmed"
    if "confirmed" in statuses:
        return "mixed"
    return "candidate"


def _layer(fact_ids: list[str], by_id: dict[str, dict[str, Any]]) -> str:
    return _layer_from_statuses(
        {by_id[fact_id]["status"] for fact_id in fact_ids}
    )


def _next_step(layer: str, verdict: str) -> str:
    if verdict == "insufficient":
        return "材料不足：导入后续章节或回对应章·段人工核对后再判，不当矛盾处理"
    if layer == "confirmed":
        return "真值层矛盾：回对应章·段复核原文；确属笔误就在审查台改写或驳回其中一方"
    if layer == "mixed":
        return "候选与已确认真值抵触：先回原文核对该候选，确认前不要采纳"
    return "双方都还是候选：先在审查台（confirm）核对真伪；都被确认时才升级为真值矛盾"


def execute(
    request: dict[str, Any],
    finding_provider: FindingProvider,
) -> dict[str, Any]:
    """用显式 C4 快照和冻结 finding provider 生成 C6 v1 报告对象。"""

    if not isinstance(request, dict):
        raise CheckToolError("request 必须是对象")
    if set(request) != {
        "project",
        "generated_at",
        "facts",
        "current_revision_refs",
        "check_config",
    }:
        raise CheckToolError(
            "request 只允许 project、generated_at、facts、current_revision_refs、check_config"
        )
    project = request["project"]
    generated_at = request["generated_at"]
    if not isinstance(project, str) or not project.strip():
        raise CheckToolError("project 必须是非空显示名")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise CheckToolError("generated_at 必须显式提供")
    config = _validate_check_config(request["check_config"])
    current_refs = _current_revision_index(request["current_revision_refs"])
    facts, excluded_counts, duplicate_records = _eligible_facts(
        request["facts"], current_refs
    )
    provider_id = getattr(finding_provider, "provider_id", None)
    model_calls = getattr(finding_provider, "model_calls", None)
    find = getattr(finding_provider, "find", None)
    if not isinstance(provider_id, str) or not provider_id.strip() or not callable(find):
        raise CheckToolError("finding_provider 身份或 find(batch) 缺失")
    if model_calls != 0:
        raise CheckToolError("本票只允许 model_calls=0")
    batch = {
        "scope": copy.deepcopy(config),
        "facts": copy.deepcopy(facts),
    }
    response = find(batch)
    raw_findings = _provider_findings(
        response,
        known_fact_ids={fact["id"] for fact in facts},
        allowed_kinds=set(config["kinds"]),
    )
    by_id = {fact["id"]: fact for fact in facts}
    conflicts: list[dict[str, Any]] = []
    insufficient: list[dict[str, Any]] = []
    for finding in raw_findings:
        layer = _layer(finding["fact_ids"], by_id)
        record = {
            "kind": finding["kind"],
            "layer": layer,
            "fact_ids": finding["fact_ids"],
            "note": finding["note"],
            "next_step": _next_step(layer, finding["verdict"]),
            "evidence": _evidence(finding["fact_ids"], by_id),
            "found_by": [config["scope_name"]],
            "confidence": finding["confidence"],
            "hard": finding["hard"],
        }
        if finding["verdict"] == "conflict":
            record["severity"] = _expected_severity(finding, layer=layer)
            conflicts.append(record)
        else:
            insufficient.append(record)
    conflicts.sort(key=lambda item: (0 if item["severity"] == "red" else 1, item["fact_ids"]))
    insufficient.sort(key=lambda item: item["fact_ids"])
    for index, record in enumerate(conflicts, 1):
        record["issue_id"] = f"h{index:03d}"
    for index, record in enumerate(insufficient, 1):
        record["issue_id"] = f"n{index:03d}"
    revision_refs = sorted(
        {
            (
                fact["chapter_revision_ref"]["chapter_id"],
                fact["chapter_revision_ref"]["revision_no"],
                fact["chapter_revision_ref"]["revision_text_sha256"],
            )
            for fact in facts
        }
    )
    report_revision_refs = [
        {
            "chapter_id": chapter_id,
            "revision_no": revision_no,
            "revision_text_sha256": revision_sha,
        }
        for chapter_id, revision_no, revision_sha in revision_refs
    ]
    confirmed_count = sum(1 for fact in facts if fact["status"] == "confirmed")
    extracted_count = sum(1 for fact in facts if fact["status"] == "extracted")
    return {
        "contract": "C6_HEALTH_REPORT",
        "version": "v1",
        "project": project,
        "generated_at": generated_at,
        "model": provider_id,
        "chapter_revision_refs": report_revision_refs,
        "source_revision_state": "CURRENT",
        "scan": {
            "facts_total": len(facts),
            "confirmed": confirmed_count,
            "extracted": extracted_count,
            "rejected_excluded": excluded_counts["rejected"],
            "duplicate_dropped": excluded_counts["duplicate_dropped"],
            "api_calls": 0,
            "failed_calls": 0,
            "clean_groups": 1 if not raw_findings else 0,
            "total_tokens": 0,
            "seconds": 0.0,
            "groups": [
                {
                    "name": config["scope_name"],
                    "kind": config["scope_kind"],
                    "facts": len(facts),
                    "status": "ok",
                    "findings": len(raw_findings),
                }
            ],
            "excluded_counts": excluded_counts,
        },
        "conflicts": conflicts,
        "insufficient": insufficient,
        "alias_hints": [],
        "integrity": {
            "duplicate_ids": duplicate_records,
            "note": (
                "同一事实号对应多条当前事实——入账事故，不是小说矛盾；体检只认首次出现"
                if duplicate_records
                else ""
            ),
            "next_step": (
                "回 M4 修账（重编号或重抽）后重跑体检才算数"
                if duplicate_records
                else ""
            ),
        },
        "summary": {
            "red": sum(1 for record in conflicts if record["severity"] == "red"),
            "yellow": sum(
                1 for record in conflicts if record["severity"] == "yellow"
            ),
            "by_layer": {
                layer: sum(1 for record in conflicts if record["layer"] == layer)
                for layer in ("confirmed", "mixed", "candidate")
            },
            "by_kind": {
                kind: sum(1 for record in conflicts if record["kind"] == kind)
                for kind in KINDS
            },
            "insufficient": len(insufficient),
            "alias_hints": 0,
            "duplicate_ids": len(duplicate_records),
        },
    }


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_string_list(
    value: object,
    *,
    label: str,
    minimum: int = 0,
) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) < minimum
        or any(not _nonempty_string(item) for item in value)
        or len(value) != len(set(value))
    ):
        raise CheckToolError(f"{label} 必须是无重复的非空字符串列表")
    return value


def _validate_location(value: object, *, label: str) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != LOCATION_KEYS
        or not _nonempty_string(value.get("chapter_id"))
        or (
            value.get("seg") is not None
            and not _nonnegative_int(value.get("seg"))
        )
        or not isinstance(value.get("text"), str)
    ):
        raise CheckToolError(f"{label} 不是合法定位")


def _validate_evidence(
    value: object,
    *,
    label: str,
    revision_by_chapter: dict[str, dict[str, Any]],
) -> str:
    if (
        not isinstance(value, dict)
        or set(value) != EVIDENCE_KEYS
        or not isinstance(value.get("fact_id"), str)
        or FACT_ID_RE.fullmatch(value["fact_id"]) is None
        or not _nonempty_string(value.get("chapter_id"))
        or value.get("status") not in {"confirmed", "extracted"}
        or not _nonempty_string(value.get("text"))
        or not _nonempty_string(value.get("quote"))
        or (
            value.get("seg") is not None
            and not _nonnegative_int(value.get("seg"))
        )
        or not _valid_revision_ref(value.get("chapter_revision_ref"))
    ):
        raise CheckToolError(f"{label} 不是合法 C6 evidence")
    revision_ref = value["chapter_revision_ref"]
    if (
        revision_ref["chapter_id"] != value["chapter_id"]
        or revision_by_chapter.get(value["chapter_id"]) != revision_ref
    ):
        raise CheckToolError(f"{label} 的 revision 来源不在报告水位中")
    anchor = value.get("anchor_ref")
    quote = value["quote"]
    if (
        not isinstance(anchor, dict)
        or set(anchor) != ANCHOR_REF_KEYS
        or any(anchor.get(key) != revision_ref[key] for key in REVISION_REF_KEYS)
        or anchor.get("coordinate_basis") != COORDINATE_BASIS
        or not _is_int(anchor.get("start"), minimum=0)
        or not _is_int(anchor.get("end"), minimum=1)
        or anchor["start"] >= anchor["end"]
        or anchor["end"] - anchor["start"] != len(quote)
        or not _valid_sha256(anchor.get("slice_sha256"))
        or anchor["slice_sha256"]
        != hashlib.sha256(quote.encode("utf-8")).hexdigest()
    ):
        raise CheckToolError(f"{label} 的 anchor/quote 不一致")
    return value["fact_id"]


def _validate_finding(
    value: object,
    *,
    label: str,
    conflict: bool,
    revision_by_chapter: dict[str, dict[str, Any]],
) -> tuple[str, frozenset[str], str]:
    expected_keys = FINDING_KEYS | ({"severity"} if conflict else set())
    if (
        not isinstance(value, dict)
        or set(value) != expected_keys
        or not _nonempty_string(value.get("issue_id"))
        or not _nonempty_string(value.get("kind"))
        or value.get("layer") not in {"confirmed", "mixed", "candidate"}
        or not _nonempty_string(value.get("note"))
        or not _nonempty_string(value.get("next_step"))
        or value.get("confidence") not in {"high", "low"}
        or not isinstance(value.get("hard"), bool)
    ):
        raise CheckToolError(f"{label} 不是合法 C6 finding")
    issue_id_re = CONFLICT_ID_RE if conflict else INSUFFICIENT_ID_RE
    if issue_id_re.fullmatch(value["issue_id"]) is None:
        raise CheckToolError(f"{label}.issue_id 非法")
    fact_ids = _validate_string_list(
        value.get("fact_ids"),
        label=f"{label}.fact_ids",
        minimum=2,
    )
    if any(FACT_ID_RE.fullmatch(fact_id) is None for fact_id in fact_ids):
        raise CheckToolError(f"{label}.fact_ids 含坏事实号")
    _validate_string_list(
        value.get("found_by"),
        label=f"{label}.found_by",
        minimum=1,
    )
    evidence = value.get("evidence")
    if not isinstance(evidence, list):
        raise CheckToolError(f"{label}.evidence 必须是列表")
    evidence_ids = [
        _validate_evidence(
            row,
            label=f"{label}.evidence[{index}]",
            revision_by_chapter=revision_by_chapter,
        )
        for index, row in enumerate(evidence)
    ]
    if evidence_ids != fact_ids:
        raise CheckToolError(f"{label} 的 fact_ids 与 evidence 引用不一致")
    expected_layer = _layer_from_statuses(
        {str(row["status"]) for row in evidence}
    )
    if value["layer"] != expected_layer:
        raise CheckToolError(f"{label}.layer 与 evidence 状态不一致")
    if conflict:
        severity = value.get("severity")
        if severity not in {"red", "yellow"}:
            raise CheckToolError(f"{label}.severity 非法")
        if value["layer"] != "confirmed" or value["kind"] in KINDS:
            expected = _expected_severity(
                {
                    "verdict": "conflict",
                    "kind": value["kind"],
                    "hard": value["hard"],
                    "confidence": value["confidence"],
                },
                layer=value["layer"],
            )
            if severity != expected:
                raise CheckToolError(f"{label}.severity 与现行判法不一致")
    else:
        severity = "未提供（材料不足）"
        if value["hard"]:
            raise CheckToolError(f"{label} 材料不足不能标 hard")
    return value["issue_id"], frozenset(fact_ids), str(severity)


def _validate_alias_hints(value: object) -> None:
    if not isinstance(value, list):
        raise CheckToolError("alias_hints 必须是列表")
    seen_ids: set[str] = set()
    for index, hint in enumerate(value):
        label = f"alias_hints[{index}]"
        if (
            not isinstance(hint, dict)
            or set(hint) != ALIAS_HINT_KEYS
            or not _nonempty_string(hint.get("hint_id"))
            or not _nonempty_string(hint.get("note"))
        ):
            raise CheckToolError(f"{label} 非法")
        _validate_string_list(hint.get("names"), label=f"{label}.names", minimum=2)
        for key in ("fact_ids_a", "fact_ids_b"):
            fact_ids = _validate_string_list(
                hint.get(key),
                label=f"{label}.{key}",
                minimum=1,
            )
            if any(FACT_ID_RE.fullmatch(fact_id) is None for fact_id in fact_ids):
                raise CheckToolError(f"{label}.{key} 含坏事实号")
        if hint["hint_id"] in seen_ids:
            raise CheckToolError("alias_hints 含重复提示号")
        seen_ids.add(hint["hint_id"])


def _validate_integrity(value: object) -> int:
    if (
        not isinstance(value, dict)
        or set(value) != INTEGRITY_KEYS
        or not isinstance(value.get("note"), str)
        or not isinstance(value.get("next_step"), str)
        or not isinstance(value.get("duplicate_ids"), list)
    ):
        raise CheckToolError("integrity 非法")
    seen_ids: set[str] = set()
    for index, record in enumerate(value["duplicate_ids"]):
        label = f"integrity.duplicate_ids[{index}]"
        if (
            not isinstance(record, dict)
            or set(record) != DUPLICATE_KEYS
            or record.get("problem") != "duplicate_id"
            or not isinstance(record.get("id"), str)
            or FACT_ID_RE.fullmatch(record["id"]) is None
            or not isinstance(record.get("dropped"), list)
            or not record["dropped"]
        ):
            raise CheckToolError(f"{label} 非法")
        _validate_location(record.get("kept"), label=f"{label}.kept")
        for dropped_index, location in enumerate(record["dropped"]):
            _validate_location(
                location,
                label=f"{label}.dropped[{dropped_index}]",
            )
        if record["id"] in seen_ids:
            raise CheckToolError("integrity 含重复事实号记录")
        seen_ids.add(record["id"])
    return len(value["duplicate_ids"])


def _validate_scan(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != SCAN_KEYS:
        raise CheckToolError("scan 字段漂移")
    count_keys = SCAN_KEYS - {"seconds", "groups", "excluded_counts"}
    if any(not _nonnegative_int(value.get(key)) for key in count_keys):
        raise CheckToolError("scan 计数字段非法")
    if (
        not isinstance(value.get("seconds"), (int, float))
        or isinstance(value["seconds"], bool)
        or value["seconds"] < 0
        or value["facts_total"] != value["confirmed"] + value["extracted"]
    ):
        raise CheckToolError("scan 水位非法")
    if (
        value["api_calls"] != 0
        or value["failed_calls"] != 0
        or value["total_tokens"] != 0
    ):
        raise CheckToolError("当前 M7 人读入口只接受零调用报告")
    groups = value.get("groups")
    if not isinstance(groups, list):
        raise CheckToolError("scan.groups 必须是列表")
    for index, group in enumerate(groups):
        if (
            not isinstance(group, dict)
            or set(group) != GROUP_KEYS
            or not _nonempty_string(group.get("name"))
            or group.get("kind") not in SCOPE_KINDS
            or group.get("status") not in {"ok", "failed", "skipped_budget"}
            or not _nonnegative_int(group.get("facts"))
            or not _nonnegative_int(group.get("findings"))
        ):
            raise CheckToolError(f"scan.groups[{index}] 非法")
    excluded = value.get("excluded_counts")
    if (
        not isinstance(excluded, dict)
        or set(excluded) != set(EXCLUDED_COUNT_KEYS)
        or any(not _nonnegative_int(excluded.get(key)) for key in EXCLUDED_COUNT_KEYS)
        or value["rejected_excluded"] != excluded["rejected"]
        or value["duplicate_dropped"] != excluded["duplicate_dropped"]
    ):
        raise CheckToolError("scan.excluded_counts 非法")
    return value


def _validate_summary(
    value: object,
    *,
    conflicts: list[dict[str, Any]],
    insufficient: list[dict[str, Any]],
    alias_count: int,
    duplicate_count: int,
) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != SUMMARY_KEYS
        or any(
            not _nonnegative_int(value.get(key))
            for key in (
                "red",
                "yellow",
                "insufficient",
                "alias_hints",
                "duplicate_ids",
            )
        )
        or not isinstance(value.get("by_layer"), dict)
        or not isinstance(value.get("by_kind"), dict)
        or set(value["by_layer"]) != {"confirmed", "mixed", "candidate"}
        or any(not _nonnegative_int(count) for count in value["by_layer"].values())
        or any(
            not _nonempty_string(kind) or not _nonnegative_int(count)
            for kind, count in value["by_kind"].items()
        )
    ):
        raise CheckToolError("summary 非法")
    expected_by_kind = {
        kind: sum(1 for finding in conflicts if finding["kind"] == kind)
        for kind in set(KINDS) | {finding["kind"] for finding in conflicts}
    }
    if (
        value["red"] != sum(1 for row in conflicts if row["severity"] == "red")
        or value["yellow"]
        != sum(1 for row in conflicts if row["severity"] == "yellow")
        or value["by_layer"]
        != {
            layer: sum(1 for row in conflicts if row["layer"] == layer)
            for layer in ("confirmed", "mixed", "candidate")
        }
        or value["by_kind"] != expected_by_kind
        or value["insufficient"] != len(insufficient)
        or value["alias_hints"] != alias_count
        or value["duplicate_ids"] != duplicate_count
    ):
        raise CheckToolError("summary 与 finding 台账不一致")


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    """用现行 C6 schema 与 M7 引用规则严格校验，不调用 provider。"""

    if not isinstance(report, dict):
        raise CheckToolError("report 必须是对象")
    try:
        schema = json.loads(C6_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckToolError("C6_SCHEMA_UNAVAILABLE") from exc
    errors = sorted(
        Draft202012Validator(schema).iter_errors(report),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise CheckToolError(f"C6_SCHEMA_INVALID:{errors[0].json_path}")
    if set(report) != C6_REPORT_KEYS:
        raise CheckToolError("C6_REPORT_FIELDS_INVALID")
    if any(
        not _nonempty_string(report.get(key))
        for key in ("project", "generated_at", "model")
    ):
        raise CheckToolError("C6_REPORT_SOURCE_IDENTITY_INVALID")
    revision_refs = report["chapter_revision_refs"]
    revision_by_chapter: dict[str, dict[str, Any]] = {}
    for index, ref in enumerate(revision_refs):
        if not _valid_revision_ref(ref):
            raise CheckToolError(f"chapter_revision_refs[{index}] 非法")
        if ref["chapter_id"] in revision_by_chapter:
            raise CheckToolError("chapter_revision_refs 含重复章")
        revision_by_chapter[ref["chapter_id"]] = ref
    scan = _validate_scan(report["scan"])
    conflicts = report["conflicts"]
    insufficient = report["insufficient"]
    seen_issue_ids: set[str] = set()
    seen_fact_sets: set[frozenset[str]] = set()
    for list_name, rows, conflict in (
        ("conflicts", conflicts, True),
        ("insufficient", insufficient, False),
    ):
        for index, row in enumerate(rows):
            issue_id, fact_set, _ = _validate_finding(
                row,
                label=f"{list_name}[{index}]",
                conflict=conflict,
                revision_by_chapter=revision_by_chapter,
            )
            if issue_id in seen_issue_ids or fact_set in seen_fact_sets:
                raise CheckToolError("C6 finding 重复")
            seen_issue_ids.add(issue_id)
            seen_fact_sets.add(fact_set)
    _validate_alias_hints(report["alias_hints"])
    duplicate_count = _validate_integrity(report["integrity"])
    _validate_summary(
        report["summary"],
        conflicts=conflicts,
        insufficient=insufficient,
        alias_count=len(report["alias_hints"]),
        duplicate_count=duplicate_count,
    )
    if sum(group["findings"] for group in scan["groups"]) != (
        len(conflicts) + len(insufficient)
    ):
        raise CheckToolError("scan.groups.findings 与 finding 台账不一致")
    return copy.deepcopy(report)


def _render_evidence(row: dict[str, Any]) -> list[str]:
    anchor = row["anchor_ref"]
    revision = row["chapter_revision_ref"]
    return [
        f"  - 事实 {row['fact_id']}（{row['status']}）",
        f"    引文：{row['quote']}",
        (
            f"    锚点：{row['chapter_id']} / revision "
            f"{revision['revision_no']} / [{anchor['start']}, {anchor['end']})"
        ),
        f"    revision SHA：{revision['revision_text_sha256']}",
        f"    quote SHA：{anchor['slice_sha256']}",
    ]


def render_report(report: dict[str, Any]) -> str:
    """把已有 C6 v1 对象稳定排版成人读文本，不运行或重跑 provider。"""

    value = validate_report(report)
    scan = value["scan"]
    lines = [
        "# 小说体检报告",
        "",
        f"报告身份：{value['contract']} {value['version']}",
        f"项目：{value['project']}",
        f"生成时间：{value['generated_at']}",
        (
            f"Provider：{value['model']}（原报告记录 API 调用 "
            f"{scan['api_calls']} 次；本次渲染未调用 provider）"
        ),
        f"来源状态：{value['source_revision_state']}",
        "",
        "## 覆盖范围与来源水位",
        "",
        (
            f"事实水位：纳入 {scan['facts_total']} 条；已确认 "
            f"{scan['confirmed']} 条；候选 {scan['extracted']} 条。"
        ),
        f"检查分组：{len(scan['groups'])} 组。",
    ]
    if value["chapter_revision_refs"]:
        lines.append("来源 revisions：")
        for ref in value["chapter_revision_refs"]:
            lines.append(
                f"- {ref['chapter_id']} / revision {ref['revision_no']} / "
                f"SHA {ref['revision_text_sha256']}"
            )
    else:
        lines.append("来源 revisions：本报告未记录任何 revision。")

    lines.extend(["", "## Findings", ""])
    finding_count = len(value["conflicts"]) + len(value["insufficient"])
    if finding_count == 0:
        lines.append("本次未返回 finding；这不能证明没有问题。")
    for bucket, rows in (
        ("矛盾", value["conflicts"]),
        ("材料不足", value["insufficient"]),
    ):
        for row in rows:
            severity = row.get("severity", "未提供（材料不足）")
            lines.extend(
                [
                    f"### {row['issue_id']} · {bucket}",
                    "",
                    f"- 严重度：{severity}",
                    f"- 类别：{row['kind']}",
                    f"- 事实层：{row['layer']}",
                    f"- 说明：{row['note']}",
                    f"- 事实号：{', '.join(row['fact_ids'])}",
                    "- 证据：",
                ]
            )
            for evidence in row["evidence"]:
                lines.extend(_render_evidence(evidence))
            lines.extend(
                [
                    "- 判读边界：以上类别按原报告展示，没有给出整体结论。",
                    "",
                ]
            )

    lines.extend(["## 排除、弃权与未知项", ""])
    for key in EXCLUDED_COUNT_KEYS:
        lines.append(f"- {key}：{scan['excluded_counts'][key]}")
    lines.extend(
        [
            f"- 材料不足 findings：{len(value['insufficient'])}",
            f"- 别名提示：{len(value['alias_hints'])}",
            f"- 账本重复事实号：{len(value['integrity']['duplicate_ids'])}",
            "",
            "这些项目只按原报告列出；未进入 finding 的内容不等于已经完成检查。",
            "",
        ]
    )
    return "\n".join(lines)


def _read_json_object(path_text: str | None, *, label: str) -> dict[str, Any]:
    if path_text in {None, "-"}:
        raw = sys.stdin.read()
    else:
        raw = Path(path_text).read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CheckToolError(f"{label} 不是合法 JSON：{exc.msg}") from exc
    if not isinstance(value, dict):
        raise CheckToolError(f"{label} 顶层必须是对象")
    return value


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    payload = _json_bytes(value)
    if not path.parent.is_dir():
        raise CheckToolError(f"输出目录不存在：{path.parent}")
    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _atomic_write_text(path: Path, value: str) -> None:
    payload = value.encode("utf-8")
    if not path.parent.is_dir():
        raise CheckToolError(f"输出目录不存在：{path.parent}")
    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _write_result(path_text: str | None, result: dict[str, Any]) -> None:
    if path_text in {None, "-"}:
        sys.stdout.buffer.write(_json_bytes(result))
        sys.stdout.buffer.flush()
        return
    _atomic_write_json(Path(path_text), result)


def _write_rendered(path_text: str | None, result: str) -> None:
    if path_text in {None, "-"}:
        sys.stdout.buffer.write(result.encode("utf-8"))
        sys.stdout.buffer.flush()
        return
    _atomic_write_text(Path(path_text), result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="M7 LOCAL_FILESYSTEM_ONLY frozen-response health report tool"
    )
    parser.add_argument("--input", help="本地 request JSON；省略或 - 时读 stdin")
    parser.add_argument("--responses", help="本地冻结 responses JSON")
    parser.add_argument("--output", help="本地 report JSON；省略或 - 时写 stdout")
    parser.add_argument(
        "--render",
        action="store_true",
        help="把 --input 中已有的 C6 v1 报告渲染为人读文本",
    )
    args = parser.parse_args(argv)
    try:
        if args.render:
            if args.responses is not None:
                raise CheckToolError("render 不接受 responses，也不调用 provider")
            report = _read_json_object(args.input, label="report")
            _write_rendered(args.output, render_report(report))
        else:
            if args.responses is None:
                raise CheckToolError("默认 JSON 模式必须提供 --responses")
            request = _read_json_object(args.input, label="input")
            frozen = _read_json_object(args.responses, label="responses")
            provider = FrozenFindingProvider(frozen)
            result = execute(request, provider)
            _write_result(args.output, result)
    except (CheckToolError, OSError) as exc:
        print(f"check_tool error: {exc}", file=sys.stderr)
        return 2
    return 0


__all__ = [
    "CheckToolError",
    "FindingProvider",
    "FrozenFindingProvider",
    "execute",
    "render_report",
    "validate_report",
]


if __name__ == "__main__":
    raise SystemExit(main())
