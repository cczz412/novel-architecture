from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


QUESTION_PLAN_SCHEMA = "r2-question-plan.v2"
QUERY_BINDING_SCHEMA = "r2-a5-query-facet-binding.v1"
RANK_STREAM_SCHEMA = "r2-a5-rank-stream.v1"
RANK_STREAM_COLLECTION_SCHEMA = "r2-a5-rank-stream-collection.v1"
TRACE_SCHEMA = "r2-question-retrieval-trace.v1"
EVIDENCE_SCHEMA = "v02-r2-evidence-record.v1"
ANSWER_SCHEMA = "v02-r2-answer-with-sources.v2"

ACTION_FIELDS = {
    "step_id",
    "obligation_or_facet_id",
    "operation",
    "query_id",
    "cursor_before",
    "cursor_after",
    "paragraph_id",
    "paragraph_sha256",
    "incremental_candidate_chars",
    "evidence_ids",
    "reason_code",
}
ACTION_OPERATIONS = {
    "FETCH_NEXT",
    "SKIP_DUPLICATE",
    "SKIP_NO_FIT",
    "ADMIT_EVIDENCE",
    "REJECT_SHAPE",
    "REUSE_EVIDENCE",
    "STOP",
}
ANSWER_STATUSES = {"ANSWER", "PARTIAL", "ABSTAIN"}
UNMET_REASONS = {
    "NO_NONZERO_A5_WINDOW",
    "RANK_STREAM_EXHAUSTED",
    "BUDGET_EXHAUSTED",
    "REQUIRED_ROLE_MISSING",
    "COREFERENCE_UNRESOLVED",
    "QUALIFIER_UNRESOLVED",
    "MULTI_SPAN_JOIN_MISS",
    "NO_ADMISSIBLE_EVIDENCE_OBSERVED",
}
FORBIDDEN_PLAN_KEYS = {
    "case_id",
    "source_id",
    "query_text",
    "answer_text",
    "required_heads",
    "source_id_groups",
    "head_ids",
    "answerability",
    "expected_count",
    "answer_count",
    "human_verdict",
    "is_correct",
    "supports",
    "complete",
    "confidence",
    "score",
}


class QECError(ValueError):
    """QEC 公开题面逐题回取实验拒收错误。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_sha(value: Mapping[str, Any], field: str) -> str:
    payload = dict(value)
    payload.pop(field, None)
    return sha256_bytes(canonical_bytes(payload))


QUESTION_GRAMMAR: tuple[dict[str, Any], ...] = (
    {
        "triggers": ("在哪里", "什么状态"),
        "question_kind": "LOCATION_AND_CURRENT_STATE",
        "quantifier": "SINGLE_SUBJECT_MULTI_FACET",
        "fixed_conjuncts": ("LOCATION", "CURRENT_STATE"),
        "search_facets": (),
        "record_required_roles": ("PRIMARY_SUBJECT_ROLE", "VALUE"),
        "qualifiers": ("PRIMARY_SUBJECT_REFERENCE", "CURRENT_CHAPTER_SCOPE"),
    },
    {
        "triggers": ("影响后续", "状态变化"),
        "question_kind": "STATE_CHANGE_SET",
        "quantifier": "OPEN_SET",
        "fixed_conjuncts": (),
        "search_facets": ("STATE_CHANGE",),
        "record_required_roles": ("CHANGE_HOLDER", "CHANGE_DESCRIPTION"),
        "qualifiers": ("FUTURE_RELEVANCE", "REALIZATION_STATUS"),
    },
    {
        "triggers": ("新知道",),
        "question_kind": "KNOWLEDGE_GAIN_SET",
        "quantifier": "OPEN_SET",
        "fixed_conjuncts": (),
        "search_facets": ("KNOWLEDGE_GAIN",),
        "record_required_roles": ("EXPERIENCER", "CONTENT"),
        "qualifiers": ("NOVELTY", "TIME_SCOPE", "ATTRIBUTION"),
    },
    {
        "triggers": ("仍不知道", "误信"),
        "question_kind": "IGNORANCE_OR_MISBELIEF_SET",
        "quantifier": "OPEN_SET",
        "fixed_conjuncts": (),
        "search_facets": ("IGNORANCE", "MISBELIEF"),
        "record_required_roles": ("EXPERIENCER", "CONTENT", "EPISTEMIC_MODE"),
        "qualifiers": ("PERSISTENCE", "WORLD_FACT_SEPARATION"),
    },
    {
        "triggers": ("目标", "计划", "承诺", "威胁"),
        "question_kind": "INTENT_SET",
        "quantifier": "OPEN_SET",
        "fixed_conjuncts": (),
        "search_facets": ("GOAL", "PLAN", "PROMISE", "THREAT"),
        "record_required_roles": ("ACTOR", "CONTENT", "INTENT_TYPE"),
        "qualifiers": ("POLARITY", "MODALITY", "ATTRIBUTION"),
    },
    {
        "triggers": ("关系", "身份", "归属"),
        "question_kind": "RELATION_IDENTITY_OWNERSHIP_CHANGE_SET",
        "quantifier": "OPEN_SET",
        "fixed_conjuncts": (),
        "search_facets": ("RELATION_CHANGE", "IDENTITY_CHANGE", "OWNERSHIP_CHANGE"),
        "record_required_roles": ("PARTICIPANT_OR_ITEM", "CHANGE_TYPE", "FROM_OR_TO"),
        "qualifiers": ("CHANGE_DIRECTION", "PARTICIPANT_IDENTITY"),
    },
    {
        "triggers": ("资源", "物品", "位置", "能力", "转移"),
        "question_kind": "RESOURCE_TRANSFER_OR_CHANGE_SET",
        "quantifier": "OPEN_SET",
        "fixed_conjuncts": (),
        "search_facets": ("RESOURCE", "ITEM", "LOCATION_CHANGE", "CAPABILITY_CHANGE"),
        "record_required_roles": ("THING_OR_CAPACITY", "CHANGE_OR_TRANSFER", "FROM_OR_TO"),
        "qualifiers": ("HOLDER", "LOCATION", "TRANSFER_DIRECTION"),
    },
    {
        "triggers": ("未决事项", "风险", "伏笔"),
        "question_kind": "UNRESOLVED_SET",
        "quantifier": "OPEN_SET",
        "fixed_conjuncts": (),
        "search_facets": ("UNRESOLVED_ISSUE", "RISK", "FORESHADOWING"),
        "record_required_roles": ("ISSUE", "OPEN_OR_RISK_BASIS"),
        "qualifiers": ("NEXT_CHAPTER_RELEVANCE", "RESOLUTION_STATUS"),
    },
    {
        "triggers": ("因果触发",),
        "question_kind": "CAUSE_RESULT_SET",
        "quantifier": "OPEN_SET",
        "fixed_conjuncts": (),
        "search_facets": ("CAUSE_RESULT",),
        "record_required_roles": ("CAUSE", "RESULT", "DIRECTION"),
        "qualifiers": ("CAUSAL_NOT_TEMPORAL", "DIRECTION_PRESERVED"),
    },
    {
        "triggers": ("相信", "猜测", "听说", "世界事实"),
        "question_kind": "EPISTEMIC_CLAIM_SET",
        "quantifier": "OPEN_SET",
        "fixed_conjuncts": (),
        "search_facets": ("BELIEF", "GUESS", "HEARSAY"),
        "record_required_roles": ("HOLDER_OR_SPEAKER", "CONTENT", "EPISTEMIC_MODE"),
        "qualifiers": ("NARRATOR_CONFIRMATION", "FACT_STATUS_NOT_UPGRADED"),
    },
)


UNIT_MARKERS: dict[str, tuple[str, ...]] = {
    "LOCATION": (
        "回到", "来到", "走进", "离开", "住在", "留在", "坐在", "站在", "躺在",
        "搬到", "赶到", "进了", "到了", "去了",
    ),
    "CURRENT_STATE": (
        "受伤", "清醒", "昏迷", "死亡", "活着", "病了", "好了", "醒来", "睡着",
        "困住", "留下", "离开", "失去", "得到",
    ),
    "STATE_CHANGE": (
        "开始", "变成", "改为", "不再", "已经", "终于", "恢复", "失去", "得到",
        "离开", "进入", "留下", "赶走", "收走", "送给", "卖掉", "搬去",
    ),
    "KNOWLEDGE_GAIN": (
        "知道", "得知", "发现", "明白", "听见", "看见", "承认", "坦白", "告诉",
    ),
    "IGNORANCE": ("不知道", "不知", "尚未", "仍不", "隐瞒", "瞒着", "秘密"),
    "MISBELIEF": ("误信", "误以为", "以为", "错信", "被骗", "骗过"),
    "GOAL": ("目标", "想要", "要去", "为了", "必须"),
    "PLAN": ("计划", "准备", "决定", "打算", "安排", "吩咐", "命令"),
    "PROMISE": ("承诺", "答应", "保证", "约定", "发誓"),
    "THREAT": ("威胁", "警告", "否则", "休想", "不许"),
    "RELATION_CHANGE": ("关系", "成为", "结交", "决裂", "和好", "认亲", "婚"),
    "IDENTITY_CHANGE": ("身份", "认出", "认作", "改名", "称为", "原来是"),
    "OWNERSHIP_CHANGE": ("属于", "主人", "归", "送给", "给了", "收下", "带走"),
    "RESOURCE": ("资源", "钱", "粮", "人手", "兵", "势力", "名额"),
    "ITEM": ("物品", "东西", "信", "书", "剑", "药", "钥匙", "拿走", "交给", "送给"),
    "LOCATION_CHANGE": ("位置", "移动", "离开", "来到", "搬到", "赶到", "带走", "送到"),
    "CAPABILITY_CHANGE": ("能力", "学会", "会了", "失去", "恢复", "提升", "不能"),
    "UNRESOLVED_ISSUE": ("未决", "还没", "尚未", "仍然", "继续", "等待", "下落", "不知"),
    "RISK": ("风险", "危险", "担心", "恐怕", "威胁", "危机"),
    "FORESHADOWING": ("伏笔", "秘密", "疑问", "线索", "以后", "将来", "隐藏"),
    "CAUSE_RESULT": ("因为", "所以", "因此", "导致", "于是", "结果", "只因", "以致", "才会"),
    "BELIEF": ("相信", "认为", "以为", "觉得"),
    "GUESS": ("猜测", "猜想", "怀疑", "可能", "似乎"),
    "HEARSAY": ("听说", "据说", "传闻", "听闻", "有人说"),
}


def compile_public_question_plan(question_text: str) -> dict[str, Any]:
    """只看一条公开题面；接口故意没有 case、正文或分数字段。"""
    if not isinstance(question_text, str) or not question_text.strip():
        raise QECError("QEC_QUESTION_TEXT_REQUIRED")
    matches = [
        spec
        for spec in QUESTION_GRAMMAR
        if all(trigger in question_text for trigger in spec["triggers"])
    ]
    if len(matches) != 1:
        raise QECError(f"QEC_PUBLIC_GRAMMAR_MATCH_INVALID:{len(matches)}")
    spec = matches[0]
    body = {
        "question_kind": spec["question_kind"],
        "quantifier": spec["quantifier"],
        "fixed_conjuncts": list(spec["fixed_conjuncts"]),
        "search_facets": list(spec["search_facets"]),
        "record_required_roles": list(spec["record_required_roles"]),
        "qualifiers_to_preserve": list(spec["qualifiers"]),
        "count_policy": "NO_EXPECTED_ANSWER_COUNT",
        "completeness_policy": "NOT_SELF_CERTIFIED",
    }
    _validate_plan_body(body)
    return body


def build_question_plan(
    *, question_id: str, question_text: str, planner_artifact_sha256: str
) -> dict[str, Any]:
    body = compile_public_question_plan(question_text)
    plan = {
        "schema_version": QUESTION_PLAN_SCHEMA,
        "question_id": question_id,
        "question_text_sha256": sha256_bytes(question_text.encode("utf-8")),
        "planner_kind": "DETERMINISTIC_PUBLIC_QUESTION_GRAMMAR",
        "planner_artifact_sha256": planner_artifact_sha256,
        "plan_body": body,
        "plan_body_sha256": sha256_bytes(canonical_bytes(body)),
    }
    validate_question_plan(plan)
    return plan


def _validate_plan_body(body: Mapping[str, Any]) -> None:
    expected = {
        "question_kind",
        "quantifier",
        "fixed_conjuncts",
        "search_facets",
        "record_required_roles",
        "qualifiers_to_preserve",
        "count_policy",
        "completeness_policy",
    }
    if set(body) != expected:
        raise QECError("QEC_PLAN_BODY_FIELDS_INVALID")
    if body["quantifier"] not in {"SINGLE_SUBJECT_MULTI_FACET", "OPEN_SET"}:
        raise QECError("QEC_PLAN_QUANTIFIER_INVALID")
    if body["count_policy"] != "NO_EXPECTED_ANSWER_COUNT":
        raise QECError("QEC_PLAN_COUNT_POLICY_INVALID")
    if body["completeness_policy"] != "NOT_SELF_CERTIFIED":
        raise QECError("QEC_PLAN_COMPLETENESS_POLICY_INVALID")
    for field in (
        "fixed_conjuncts",
        "search_facets",
        "record_required_roles",
        "qualifiers_to_preserve",
    ):
        value = body[field]
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item for item in value
        ):
            raise QECError(f"QEC_PLAN_LIST_INVALID:{field}")
        if len(value) != len(set(value)):
            raise QECError(f"QEC_PLAN_LIST_DUPLICATED:{field}")
    if body["quantifier"] == "SINGLE_SUBJECT_MULTI_FACET":
        if body["fixed_conjuncts"] != ["LOCATION", "CURRENT_STATE"]:
            raise QECError("QEC_FIXED_CONJUNCTS_INVALID")
        if body["search_facets"]:
            raise QECError("QEC_FIXED_PLAN_SEARCH_FACETS_NOT_EMPTY")
    elif body["fixed_conjuncts"]:
        raise QECError("QEC_OPEN_SET_FIXED_CONJUNCTS_NOT_EMPTY")


def validate_question_plan(plan: Mapping[str, Any]) -> None:
    expected = {
        "schema_version",
        "question_id",
        "question_text_sha256",
        "planner_kind",
        "planner_artifact_sha256",
        "plan_body",
        "plan_body_sha256",
    }
    if set(plan) != expected:
        raise QECError("QEC_QUESTION_PLAN_FIELDS_INVALID")
    if plan["schema_version"] != QUESTION_PLAN_SCHEMA:
        raise QECError("QEC_QUESTION_PLAN_SCHEMA_INVALID")
    if plan["planner_kind"] != "DETERMINISTIC_PUBLIC_QUESTION_GRAMMAR":
        raise QECError("QEC_PLANNER_KIND_INVALID")
    body = plan["plan_body"]
    if not isinstance(body, Mapping):
        raise QECError("QEC_PLAN_BODY_NOT_OBJECT")
    _reject_forbidden_plan_keys(body)
    _validate_plan_body(body)
    if plan["plan_body_sha256"] != sha256_bytes(canonical_bytes(body)):
        raise QECError("QEC_PLAN_BODY_SHA_MISMATCH")


def _reject_forbidden_plan_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_PLAN_KEYS or lowered.startswith("gold"):
                raise QECError(f"QEC_FORBIDDEN_PLAN_KEY:{key}")
            if lowered.startswith("adjudicator") or lowered.startswith("score"):
                raise QECError(f"QEC_FORBIDDEN_PLAN_KEY:{key}")
            _reject_forbidden_plan_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_plan_keys(child)


def plan_units(plan: Mapping[str, Any]) -> list[str]:
    body = plan["plan_body"]
    return [*body["fixed_conjuncts"], *body["search_facets"]]


def bind_a5_queries_to_units(
    *, plan: Mapping[str, Any], query_map: Mapping[str, Any]
) -> dict[str, Any]:
    validate_question_plan(plan)
    queries = query_map.get("queries")
    if not isinstance(queries, list) or not queries:
        raise QECError("QEC_A5_QUERY_MAP_EMPTY")
    units = plan_units(plan)
    bindings: list[dict[str, Any]] = []
    for query in queries:
        if set(query) != {"query_id", "query_text", "origin_kind"}:
            raise QECError("QEC_A5_QUERY_FIELDS_INVALID")
        text = query["query_text"]
        matched = [
            unit
            for unit in units
            if any(marker in text or text in marker for marker in UNIT_MARKERS[unit])
        ]
        if not matched:
            matched = [
                unit
                for unit in units
                if any(token in text for token in unit.lower().split("_"))
            ]
        if not matched:
            matched = list(units)
        bindings.append(
            {
                "query_id": query["query_id"],
                "query_text_sha256": sha256_bytes(text.encode("utf-8")),
                "bound_obligation_or_facet_ids": matched,
            }
        )
    result = {
        "schema_version": QUERY_BINDING_SCHEMA,
        "cell_id": f"{query_map['case_id']}::{query_map['question_id']}",
        "question_id": query_map["question_id"],
        "plan_body_sha256": plan["plan_body_sha256"],
        "a5_query_count": len(queries),
        "duplicate_queries_preserved": len({row["query_text"] for row in queries})
        != len(queries),
        "query_bindings": bindings,
    }
    result["binding_payload_sha256"] = sha256_bytes(canonical_bytes(result))
    return result


def build_rank_stream_cell(
    *,
    case_id: str,
    question_id: str,
    query_map: Mapping[str, Any],
    rankings: Sequence[Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    queries = query_map["queries"]
    if len(queries) != len(rankings):
        raise QECError("QEC_RANK_STREAM_QUERY_COUNT_MISMATCH")
    streams: list[dict[str, Any]] = []
    for query, ranking in zip(queries, rankings, strict=True):
        records = []
        for rank, row in enumerate(ranking, start=1):
            records.append(
                {
                    "rank": rank,
                    "paragraph_id": row["paragraph_id"],
                    "score": round(float(row["score"]), 8),
                    "matched_grams": list(row["matched_grams"]),
                    "char_count": int(row["char_count"]),
                    "paragraph_sha256": sha256_bytes(
                        row["original_text"].encode("utf-8")
                    ),
                }
            )
        stream = {
            "schema_version": RANK_STREAM_SCHEMA,
            "query_id": query["query_id"],
            "query_text_sha256": sha256_bytes(query["query_text"].encode("utf-8")),
            "record_count": len(records),
            "records": records,
        }
        stream["stream_payload_sha256"] = sha256_bytes(canonical_bytes(stream))
        streams.append(stream)
    cell = {
        "cell_id": f"{case_id}::{question_id}",
        "case_id": case_id,
        "question_id": question_id,
        "query_stream_count": len(streams),
        "rank_record_count": sum(row["record_count"] for row in streams),
        "streams": streams,
    }
    cell["cell_payload_sha256"] = sha256_bytes(canonical_bytes(cell))
    return cell


def build_rank_stream_collection(cells: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ordered = sorted((dict(cell) for cell in cells), key=lambda row: row["cell_id"])
    result = {
        "schema_version": RANK_STREAM_COLLECTION_SCHEMA,
        "cell_count": len(ordered),
        "query_stream_count": sum(row["query_stream_count"] for row in ordered),
        "rank_record_count": sum(row["rank_record_count"] for row in ordered),
        "cells": ordered,
    }
    result["collection_payload_sha256"] = sha256_bytes(canonical_bytes(result))
    return result


def _shape_ready_units(text: str, units: Sequence[str]) -> list[str]:
    ready: list[str] = []
    for unit in units:
        markers = UNIT_MARKERS[unit]
        hits = [marker for marker in markers if marker in text]
        if not hits:
            continue
        if unit == "CAUSE_RESULT":
            if not any(
                text.find(marker) > 0 and text.find(marker) + len(marker) < len(text) - 1
                for marker in hits
            ):
                continue
        if len(text.strip()) < 6:
            continue
        ready.append(unit)
    return ready


def _output_window(row: Mapping[str, Any], *, rank: int) -> dict[str, Any]:
    query_ids = []
    for query_id in row.get("matched_query_ids", []):
        try:
            query_ids.append(f"QRY-{int(str(query_id).rsplit('-', 1)[1]):03d}")
        except (ValueError, IndexError):
            raise QECError(f"QEC_MERGED_QUERY_ID_INVALID:{query_id}")
    actual = int(row.get("query_hit_count", 0)) > 0
    return {
        "paragraph_id": row["paragraph_id"],
        "rank": rank,
        "score": round(float(row["merged_score"]), 8),
        "char_count": int(row["char_count"]),
        "selection_reason": (
            "ACTUAL_QUERY_MATCH" if actual else "UNMATCHED_FALLBACK"
        ),
        "matched_query_ids": query_ids,
        "matched_grams": list(row.get("matched_grams", [])),
    }


def _evidence_id(paragraph_id: str, unit: str) -> str:
    suffix = sha256_bytes(f"{paragraph_id}\0{unit}".encode("utf-8"))[:16]
    return f"EV-{suffix}"


def execute_question_state(
    *,
    plan: Mapping[str, Any],
    query_binding: Mapping[str, Any],
    rank_stream_cell: Mapping[str, Any],
    merged_rows: Sequence[Mapping[str, Any]],
    paragraph_text_by_id: Mapping[str, str],
    budget_chars: int,
    a5_query_map_sha256: str,
    rank_stream_manifest_sha256: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_question_plan(plan)
    if budget_chars <= 0:
        raise QECError("QEC_BUDGET_INVALID")
    if query_binding["cell_id"] != rank_stream_cell["cell_id"]:
        raise QECError("QEC_BINDING_RANK_CELL_MISMATCH")
    stream_by_id = {
        row["query_id"]: row for row in rank_stream_cell["streams"]
    }
    binding_by_unit: dict[str, list[str]] = {unit: [] for unit in plan_units(plan)}
    for row in query_binding["query_bindings"]:
        if row["query_id"] not in stream_by_id:
            raise QECError("QEC_BINDING_QUERY_NOT_IN_RANK_STREAM")
        for unit in row["bound_obligation_or_facet_ids"]:
            if unit not in binding_by_unit:
                raise QECError(f"QEC_BINDING_UNIT_UNKNOWN:{unit}")
            binding_by_unit[unit].append(row["query_id"])
    if any(not query_ids for query_ids in binding_by_unit.values()):
        raise QECError("QEC_UNIT_WITHOUT_A5_QUERY")

    merged_by_id = {row["paragraph_id"]: row for row in merged_rows}
    merged_rank = {
        row["paragraph_id"]: rank for rank, row in enumerate(merged_rows, start=1)
    }
    cursors = {query_id: 0 for query_id in stream_by_id}
    unit_rotors = {unit: 0 for unit in binding_by_unit}
    selected_ids: list[str] = []
    selected_set: set[str] = set()
    evidence_units: dict[str, set[str]] = {}
    first_fetch_step: dict[str, str] = {}
    actions: list[dict[str, Any]] = []
    used_chars = 0
    step_counter = 0

    def add_action(
        *,
        unit: str,
        operation: str,
        query_id: str | None,
        cursor_before: int | None,
        cursor_after: int | None,
        paragraph_id: str | None,
        incremental_chars: int,
        evidence_ids: Sequence[str] = (),
        reason_code: str,
    ) -> str:
        nonlocal step_counter
        step_counter += 1
        step_id = f"STEP-{step_counter:04d}"
        paragraph_sha = None
        if paragraph_id is not None:
            paragraph_sha = sha256_bytes(
                paragraph_text_by_id[paragraph_id].encode("utf-8")
            )
        action = {
            "step_id": step_id,
            "obligation_or_facet_id": unit,
            "operation": operation,
            "query_id": query_id,
            "cursor_before": cursor_before,
            "cursor_after": cursor_after,
            "paragraph_id": paragraph_id,
            "paragraph_sha256": paragraph_sha,
            "incremental_candidate_chars": incremental_chars,
            "evidence_ids": list(evidence_ids),
            "reason_code": reason_code,
        }
        if set(action) != ACTION_FIELDS or operation not in ACTION_OPERATIONS:
            raise QECError("QEC_INTERNAL_ACTION_INVALID")
        actions.append(action)
        return step_id

    def admit_from_paragraph(paragraph_id: str, *, trigger_unit: str) -> int:
        text = paragraph_text_by_id[paragraph_id]
        matched_units = _shape_ready_units(text, plan_units(plan))
        new_count = 0
        if not matched_units:
            add_action(
                unit=trigger_unit,
                operation="REJECT_SHAPE",
                query_id=None,
                cursor_before=None,
                cursor_after=None,
                paragraph_id=paragraph_id,
                incremental_chars=0,
                reason_code="REQUIRED_ROLE_MISSING",
            )
            return 0
        for unit in matched_units:
            seen = evidence_units.setdefault(paragraph_id, set())
            evidence_id = _evidence_id(paragraph_id, unit)
            if unit in seen:
                add_action(
                    unit=unit,
                    operation="REUSE_EVIDENCE",
                    query_id=None,
                    cursor_before=None,
                    cursor_after=None,
                    paragraph_id=paragraph_id,
                    incremental_chars=0,
                    evidence_ids=[evidence_id],
                    reason_code="ALREADY_ADMITTED_FROM_FETCHED_WINDOW",
                )
                continue
            seen.add(unit)
            new_count += 1
            add_action(
                unit=unit,
                operation="ADMIT_EVIDENCE",
                query_id=None,
                cursor_before=None,
                cursor_after=None,
                paragraph_id=paragraph_id,
                incremental_chars=0,
                evidence_ids=[evidence_id],
                reason_code="MECHANICAL_SHAPE_READY",
            )
        return new_count

    def fetch_for_unit(unit: str) -> int:
        nonlocal used_chars
        query_ids = binding_by_unit[unit]
        attempts = 0
        while attempts < len(query_ids):
            rotor = unit_rotors[unit] % len(query_ids)
            query_id = query_ids[rotor]
            unit_rotors[unit] += 1
            attempts += 1
            stream = stream_by_id[query_id]
            cursor = cursors[query_id]
            records = stream["records"]
            while cursor < len(records):
                row = records[cursor]
                if not row["matched_grams"] or float(row["score"]) <= 0:
                    cursors[query_id] = len(records)
                    break
                before = cursor
                cursor += 1
                cursors[query_id] = cursor
                paragraph_id = row["paragraph_id"]
                if paragraph_id in selected_set:
                    add_action(
                        unit=unit,
                        operation="SKIP_DUPLICATE",
                        query_id=query_id,
                        cursor_before=before,
                        cursor_after=cursor,
                        paragraph_id=paragraph_id,
                        incremental_chars=0,
                        reason_code="PARAGRAPH_ALREADY_FETCHED",
                    )
                    return admit_from_paragraph(paragraph_id, trigger_unit=unit)
                char_count = int(row["char_count"])
                if used_chars + char_count > budget_chars:
                    add_action(
                        unit=unit,
                        operation="SKIP_NO_FIT",
                        query_id=query_id,
                        cursor_before=before,
                        cursor_after=cursor,
                        paragraph_id=paragraph_id,
                        incremental_chars=0,
                        reason_code="REMAINING_BUDGET_TOO_SMALL",
                    )
                    continue
                if paragraph_id not in merged_by_id:
                    raise QECError(f"QEC_RANK_PARAGRAPH_NOT_IN_A5_FUSION:{paragraph_id}")
                selected_set.add(paragraph_id)
                selected_ids.append(paragraph_id)
                used_chars += char_count
                fetch_step = add_action(
                    unit=unit,
                    operation="FETCH_NEXT",
                    query_id=query_id,
                    cursor_before=before,
                    cursor_after=cursor,
                    paragraph_id=paragraph_id,
                    incremental_chars=char_count,
                    reason_code="QUESTION_STATE_NEXT_BOUND_A5_STREAM",
                )
                first_fetch_step[paragraph_id] = fetch_step
                return admit_from_paragraph(paragraph_id, trigger_unit=unit)
        return 0

    fixed = list(plan["plan_body"]["fixed_conjuncts"])
    open_facets = list(plan["plan_body"]["search_facets"])
    termination_reason = "RANK_STREAM_EXHAUSTED"
    for _round in range(1, 257):
        ready = {unit for units in evidence_units.values() for unit in units}
        scheduled = [unit for unit in fixed if unit not in ready]
        scheduled.extend(open_facets)
        if not scheduled:
            termination_reason = "FIXED_CONJUNCTS_READY"
            break
        round_new = sum(fetch_for_unit(unit) for unit in scheduled)
        if used_chars >= budget_chars or not any(
            int(row["char_count"]) <= budget_chars - used_chars
            for row in merged_rows
            if row["paragraph_id"] not in selected_set
        ):
            termination_reason = "BUDGET_EXHAUSTED"
            break
        if round_new == 0:
            termination_reason = "ZERO_NEW_EVIDENCE_ROUND"
            break
        if all(cursors[query_id] >= len(stream_by_id[query_id]["records"]) for query_id in cursors):
            termination_reason = "RANK_STREAM_EXHAUSTED"
            break
    else:
        raise QECError("QEC_STATE_ROUND_LIMIT_EXCEEDED")

    residual_cursor = 0
    for residual_cursor, row in enumerate(merged_rows, start=1):
        paragraph_id = row["paragraph_id"]
        if paragraph_id in selected_set:
            continue
        char_count = int(row["char_count"])
        if used_chars + char_count > budget_chars:
            continue
        selected_set.add(paragraph_id)
        selected_ids.append(paragraph_id)
        used_chars += char_count
        fetch_step = add_action(
            unit="RESIDUAL_A5_GLOBAL_FILL",
            operation="FETCH_NEXT",
            query_id=None,
            cursor_before=residual_cursor - 1,
            cursor_after=residual_cursor,
            paragraph_id=paragraph_id,
            incremental_chars=char_count,
            reason_code="A5_GLOBAL_RESIDUAL_FILL",
        )
        first_fetch_step[paragraph_id] = fetch_step
        admit_from_paragraph(paragraph_id, trigger_unit="RESIDUAL_A5_GLOBAL_FILL")

    selected = [
        _output_window(merged_by_id[paragraph_id], rank=merged_rank[paragraph_id])
        for paragraph_id in selected_ids
    ]
    add_action(
        unit="EXECUTION",
        operation="STOP",
        query_id=None,
        cursor_before=None,
        cursor_after=None,
        paragraph_id=None,
        incremental_chars=0,
        reason_code=termination_reason,
    )
    trace: dict[str, Any] = {
        "schema_version": TRACE_SCHEMA,
        "cell_id": query_binding["cell_id"],
        "question_id": plan["question_id"],
        "question_state_feedback_enabled": True,
        "plan_body_sha256": plan["plan_body_sha256"],
        "a5_query_map_sha256": a5_query_map_sha256,
        "rank_stream_manifest_sha256": rank_stream_manifest_sha256,
        "budget_chars": budget_chars,
        "actions": actions,
        "selected_window_ids": selected_ids,
        "candidate_source_chars": used_chars,
        "termination_reason": termination_reason,
    }
    trace["trace_payload_sha256"] = sha256_bytes(canonical_bytes(trace))
    validate_trace(trace, paragraph_text_by_id=paragraph_text_by_id)
    return selected, trace


def build_shadow_trace(
    *,
    plan: Mapping[str, Any],
    cell_id: str,
    selected_windows: Sequence[Mapping[str, Any]],
    paragraph_text_by_id: Mapping[str, str],
    budget_chars: int,
    a5_query_map_sha256: str,
    rank_stream_manifest_sha256: str,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    evidence_seen: set[tuple[str, str]] = set()
    used = 0
    for index, window in enumerate(selected_windows, start=1):
        paragraph_id = window["paragraph_id"]
        text = paragraph_text_by_id[paragraph_id]
        used += int(window["char_count"])
        fetch_step = f"STEP-{len(actions) + 1:04d}"
        actions.append(
            {
                "step_id": fetch_step,
                "obligation_or_facet_id": "A5_GLOBAL_SHADOW",
                "operation": "FETCH_NEXT",
                "query_id": None,
                "cursor_before": index - 1,
                "cursor_after": index,
                "paragraph_id": paragraph_id,
                "paragraph_sha256": sha256_bytes(text.encode("utf-8")),
                "incremental_candidate_chars": int(window["char_count"]),
                "evidence_ids": [],
                "reason_code": "A5_EXISTING_GLOBAL_SELECTION_OBSERVED_ONLY",
            }
        )
        matched = _shape_ready_units(text, plan_units(plan))
        if not matched:
            actions.append(
                {
                    "step_id": f"STEP-{len(actions) + 1:04d}",
                    "obligation_or_facet_id": "A5_GLOBAL_SHADOW",
                    "operation": "REJECT_SHAPE",
                    "query_id": None,
                    "cursor_before": None,
                    "cursor_after": None,
                    "paragraph_id": paragraph_id,
                    "paragraph_sha256": sha256_bytes(text.encode("utf-8")),
                    "incremental_candidate_chars": 0,
                    "evidence_ids": [],
                    "reason_code": "REQUIRED_ROLE_MISSING",
                }
            )
        for unit in matched:
            key = (paragraph_id, unit)
            if key in evidence_seen:
                continue
            evidence_seen.add(key)
            actions.append(
                {
                    "step_id": f"STEP-{len(actions) + 1:04d}",
                    "obligation_or_facet_id": unit,
                    "operation": "ADMIT_EVIDENCE",
                    "query_id": None,
                    "cursor_before": None,
                    "cursor_after": None,
                    "paragraph_id": paragraph_id,
                    "paragraph_sha256": sha256_bytes(text.encode("utf-8")),
                    "incremental_candidate_chars": 0,
                    "evidence_ids": [_evidence_id(paragraph_id, unit)],
                    "reason_code": "MECHANICAL_SHAPE_READY",
                }
            )
    actions.append(
        {
            "step_id": f"STEP-{len(actions) + 1:04d}",
            "obligation_or_facet_id": "EXECUTION",
            "operation": "STOP",
            "query_id": None,
            "cursor_before": None,
            "cursor_after": None,
            "paragraph_id": None,
            "paragraph_sha256": None,
            "incremental_candidate_chars": 0,
            "evidence_ids": [],
            "reason_code": "A5_SHADOW_OBSERVATION_COMPLETE",
        }
    )
    trace: dict[str, Any] = {
        "schema_version": TRACE_SCHEMA,
        "cell_id": cell_id,
        "question_id": plan["question_id"],
        "question_state_feedback_enabled": False,
        "plan_body_sha256": plan["plan_body_sha256"],
        "a5_query_map_sha256": a5_query_map_sha256,
        "rank_stream_manifest_sha256": rank_stream_manifest_sha256,
        "budget_chars": budget_chars,
        "actions": actions,
        "selected_window_ids": [row["paragraph_id"] for row in selected_windows],
        "candidate_source_chars": used,
        "termination_reason": "A5_SHADOW_OBSERVATION_COMPLETE",
    }
    trace["trace_payload_sha256"] = sha256_bytes(canonical_bytes(trace))
    validate_trace(trace, paragraph_text_by_id=paragraph_text_by_id)
    return trace


def validate_trace(
    trace: Mapping[str, Any], *, paragraph_text_by_id: Mapping[str, str]
) -> None:
    expected = {
        "schema_version",
        "cell_id",
        "question_id",
        "question_state_feedback_enabled",
        "plan_body_sha256",
        "a5_query_map_sha256",
        "rank_stream_manifest_sha256",
        "budget_chars",
        "actions",
        "selected_window_ids",
        "candidate_source_chars",
        "termination_reason",
        "trace_payload_sha256",
    }
    if set(trace) != expected or trace["schema_version"] != TRACE_SCHEMA:
        raise QECError("QEC_TRACE_FIELDS_OR_SCHEMA_INVALID")
    if trace["trace_payload_sha256"] != _payload_sha(trace, "trace_payload_sha256"):
        raise QECError("QEC_TRACE_SHA_MISMATCH")
    actions = trace["actions"]
    if not isinstance(actions, list) or not actions:
        raise QECError("QEC_TRACE_ACTIONS_EMPTY")
    fetched: list[str] = []
    fetched_set: set[str] = set()
    chars = 0
    for index, action in enumerate(actions, start=1):
        if set(action) != ACTION_FIELDS:
            raise QECError(f"QEC_TRACE_ACTION_FIELDS_INVALID:{index}")
        if action["step_id"] != f"STEP-{index:04d}":
            raise QECError(f"QEC_TRACE_STEP_ORDER_INVALID:{index}")
        if action["operation"] not in ACTION_OPERATIONS:
            raise QECError(f"QEC_TRACE_OPERATION_INVALID:{index}")
        paragraph_id = action["paragraph_id"]
        if paragraph_id is not None:
            if paragraph_id not in paragraph_text_by_id:
                raise QECError(f"QEC_TRACE_PARAGRAPH_UNKNOWN:{paragraph_id}")
            if action["paragraph_sha256"] != sha256_bytes(
                paragraph_text_by_id[paragraph_id].encode("utf-8")
            ):
                raise QECError(f"QEC_TRACE_PARAGRAPH_SHA_MISMATCH:{paragraph_id}")
        elif action["paragraph_sha256"] is not None:
            raise QECError("QEC_TRACE_NULL_PARAGRAPH_WITH_SHA")
        increment = action["incremental_candidate_chars"]
        if not isinstance(increment, int) or isinstance(increment, bool) or increment < 0:
            raise QECError("QEC_TRACE_INCREMENT_INVALID")
        if action["operation"] == "FETCH_NEXT" and increment > 0:
            if paragraph_id in fetched_set:
                raise QECError("QEC_TRACE_FETCH_DUPLICATE_CHARGED")
            fetched_set.add(paragraph_id)
            fetched.append(paragraph_id)
            chars += increment
        elif increment != 0:
            raise QECError("QEC_TRACE_NON_FETCH_CHARGED")
        if action["operation"] in {"ADMIT_EVIDENCE", "REUSE_EVIDENCE"}:
            if paragraph_id not in fetched_set or not action["evidence_ids"]:
                raise QECError("QEC_TRACE_EVIDENCE_OUTSIDE_FETCHED_WINDOW")
    if fetched != trace["selected_window_ids"]:
        raise QECError("QEC_TRACE_SELECTED_REPLAY_MISMATCH")
    if chars != trace["candidate_source_chars"] or chars > trace["budget_chars"]:
        raise QECError("QEC_TRACE_BUDGET_REPLAY_MISMATCH")
    if actions[-1]["operation"] != "STOP":
        raise QECError("QEC_TRACE_FINAL_STOP_MISSING")


def _catalog_sentence_index(
    catalog: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for sentence in catalog["sentences"]:
        result.setdefault(sentence["paragraph_id"], []).append(dict(sentence))
    return result


def backfill_evidence_and_answer(
    *,
    plan: Mapping[str, Any],
    trace: Mapping[str, Any],
    catalog: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paragraph_sentences = _catalog_sentence_index(catalog)
    evidence: dict[str, dict[str, Any]] = {}
    first_fetch_step: dict[str, str] = {}
    for action in trace["actions"]:
        paragraph_id = action["paragraph_id"]
        if action["operation"] == "FETCH_NEXT" and paragraph_id is not None:
            first_fetch_step.setdefault(paragraph_id, action["step_id"])
        if action["operation"] not in {"ADMIT_EVIDENCE", "REUSE_EVIDENCE"}:
            continue
        unit = action["obligation_or_facet_id"]
        sentences = paragraph_sentences.get(paragraph_id, [])
        if not sentences:
            raise QECError(f"QEC_EVIDENCE_PARAGRAPH_WITHOUT_SENTENCE:{paragraph_id}")
        matching = [
            row
            for row in sentences
            if any(marker in row["original_text"] for marker in UNIT_MARKERS[unit])
        ]
        sentence = (matching or sentences)[0]
        evidence_id = _evidence_id(paragraph_id, unit)
        if action["evidence_ids"] != [evidence_id]:
            raise QECError("QEC_EVIDENCE_ID_BINDING_MISMATCH")
        text = sentence["original_text"]
        record = {
            "schema_version": EVIDENCE_SCHEMA,
            "evidence_id": evidence_id,
            "obligation_or_facet_id": unit,
            "case_id": catalog["source_id"],
            "source_id": sentence["sentence_id"],
            "canonical_sentence_id": sentence["sentence_id"],
            "paragraph_id": paragraph_id,
            "char_start": sentence["char_start"],
            "char_end_exclusive": sentence["char_end_exclusive"],
            "text": text,
            "text_sha256": sha256_bytes(text.encode("utf-8")),
            "retrieval_step_id": first_fetch_step[paragraph_id],
            "program_backfill_pass": True,
            "semantic_support_status": "UNJUDGED",
        }
        previous = evidence.setdefault(evidence_id, record)
        if previous != record:
            raise QECError("QEC_EVIDENCE_ID_COLLISION")
    records = sorted(evidence.values(), key=lambda row: row["evidence_id"])
    claims: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        claims.append(
            {
                "claim_id": f"CL-{index:03d}",
                "obligation_ids": [record["obligation_or_facet_id"]],
                "statement": record["text"],
                "statement_mode": "EXTRACTIVE_VERBATIM",
                "source_ids": [record["source_id"]],
                "evidence_ids": [record["evidence_id"]],
                "qualifiers": {
                    "polarity": "UNSPECIFIED",
                    "modality": "UNSPECIFIED",
                    "attribution": "UNSPECIFIED",
                    "causal_direction": (
                        "PRESERVED_FROM_EXPLICIT_CONNECTOR"
                        if record["obligation_or_facet_id"] == "CAUSE_RESULT"
                        else "NOT_APPLICABLE"
                    ),
                },
            }
        )
    ready = {record["obligation_or_facet_id"] for record in records}
    fixed_missing = [
        unit for unit in plan["plan_body"]["fixed_conjuncts"] if unit not in ready
    ]
    all_units = plan_units(plan)
    unseen = [unit for unit in all_units if unit not in ready]
    unmet = [
        {
            "obligation_or_facet_id": unit,
            "reason": (
                "BUDGET_EXHAUSTED"
                if trace["termination_reason"] == "BUDGET_EXHAUSTED"
                else "NO_ADMISSIBLE_EVIDENCE_OBSERVED"
            ),
        }
        for unit in unseen
    ]
    if not claims:
        status = "ABSTAIN"
        material_status = "NO_ADMISSIBLE_EVIDENCE_IN_BOUNDED_SEARCH"
        abstention_reason = (
            unmet[0]["reason"] if unmet else "NO_ADMISSIBLE_EVIDENCE_OBSERVED"
        )
    elif fixed_missing:
        status = "PARTIAL"
        material_status = "INSUFFICIENT_FOR_FIXED_CONJUNCTS"
        abstention_reason = None
    else:
        status = "ANSWER"
        material_status = "SUFFICIENT_FOR_STRUCTURAL_ANSWER"
        abstention_reason = None
    answer: dict[str, Any] = {
        "schema_version": ANSWER_SCHEMA,
        "cell_id": trace["cell_id"],
        "question_id": plan["question_id"],
        "plan_body_sha256": plan["plan_body_sha256"],
        "trace_payload_sha256": trace["trace_payload_sha256"],
        "status": status,
        "status_basis": "MECHANICAL_STRUCTURE_ONLY",
        "material_status": material_status,
        "claims": claims,
        "unmet_obligations": unmet,
        "abstention_reason": abstention_reason,
        "completeness_claim": "NOT_SELF_CERTIFIED",
        "semantic_correctness_claim": "UNJUDGED",
    }
    answer["answer_payload_sha256"] = sha256_bytes(canonical_bytes(answer))
    validate_evidence_records(records, trace=trace, catalog=catalog)
    validate_answer(answer, plan=plan, evidence_records=records)
    return records, answer


def validate_evidence_records(
    records: Sequence[Mapping[str, Any]],
    *,
    trace: Mapping[str, Any],
    catalog: Mapping[str, Any],
) -> None:
    sentences = {row["sentence_id"]: row for row in catalog["sentences"]}
    fetched = set(trace["selected_window_ids"])
    ids: set[str] = set()
    for record in records:
        expected = {
            "schema_version",
            "evidence_id",
            "obligation_or_facet_id",
            "case_id",
            "source_id",
            "canonical_sentence_id",
            "paragraph_id",
            "char_start",
            "char_end_exclusive",
            "text",
            "text_sha256",
            "retrieval_step_id",
            "program_backfill_pass",
            "semantic_support_status",
        }
        if set(record) != expected or record["schema_version"] != EVIDENCE_SCHEMA:
            raise QECError("QEC_EVIDENCE_FIELDS_OR_SCHEMA_INVALID")
        if record["evidence_id"] in ids:
            raise QECError("QEC_EVIDENCE_ID_DUPLICATED")
        ids.add(record["evidence_id"])
        if record["paragraph_id"] not in fetched:
            raise QECError("QEC_EVIDENCE_OUTSIDE_FETCHED_WINDOW")
        sentence = sentences.get(record["canonical_sentence_id"])
        if sentence is None or sentence["paragraph_id"] != record["paragraph_id"]:
            raise QECError("QEC_EVIDENCE_SENTENCE_BINDING_INVALID")
        for field in ("char_start", "char_end_exclusive", "original_text"):
            record_field = "text" if field == "original_text" else field
            if record[record_field] != sentence[field]:
                raise QECError("QEC_EVIDENCE_PROGRAM_BACKFILL_MISMATCH")
        if record["text_sha256"] != sha256_bytes(record["text"].encode("utf-8")):
            raise QECError("QEC_EVIDENCE_TEXT_SHA_MISMATCH")
        if record["program_backfill_pass"] is not True:
            raise QECError("QEC_EVIDENCE_BACKFILL_NOT_PASS")
        if record["semantic_support_status"] != "UNJUDGED":
            raise QECError("QEC_EVIDENCE_SEMANTIC_SELF_SIGN")


def validate_answer(
    answer: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    evidence_records: Sequence[Mapping[str, Any]],
) -> None:
    expected = {
        "schema_version",
        "cell_id",
        "question_id",
        "plan_body_sha256",
        "trace_payload_sha256",
        "status",
        "status_basis",
        "material_status",
        "claims",
        "unmet_obligations",
        "abstention_reason",
        "completeness_claim",
        "semantic_correctness_claim",
        "answer_payload_sha256",
    }
    if set(answer) != expected or answer["schema_version"] != ANSWER_SCHEMA:
        raise QECError("QEC_ANSWER_FIELDS_OR_SCHEMA_INVALID")
    if answer["answer_payload_sha256"] != _payload_sha(answer, "answer_payload_sha256"):
        raise QECError("QEC_ANSWER_SHA_MISMATCH")
    if answer["status"] not in ANSWER_STATUSES:
        raise QECError("QEC_ANSWER_STATUS_INVALID")
    if answer["completeness_claim"] != "NOT_SELF_CERTIFIED":
        raise QECError("QEC_ANSWER_COMPLETENESS_SELF_SIGN")
    if answer["semantic_correctness_claim"] != "UNJUDGED":
        raise QECError("QEC_ANSWER_SEMANTIC_SELF_SIGN")
    evidence_by_id = {row["evidence_id"]: row for row in evidence_records}
    for claim in answer["claims"]:
        expected_claim = {
            "claim_id",
            "obligation_ids",
            "statement",
            "statement_mode",
            "source_ids",
            "evidence_ids",
            "qualifiers",
        }
        if set(claim) != expected_claim or claim["statement_mode"] != "EXTRACTIVE_VERBATIM":
            raise QECError("QEC_ANSWER_CLAIM_INVALID")
        if len(claim["evidence_ids"]) != 1:
            raise QECError("QEC_ANSWER_CLAIM_EVIDENCE_COUNT_INVALID")
        evidence = evidence_by_id.get(claim["evidence_ids"][0])
        if evidence is None or claim["statement"] != evidence["text"]:
            raise QECError("QEC_ANSWER_STATEMENT_NOT_VERBATIM")
        if claim["source_ids"] != [evidence["source_id"]]:
            raise QECError("QEC_ANSWER_SOURCE_BINDING_INVALID")
        if claim["obligation_ids"] != [evidence["obligation_or_facet_id"]]:
            raise QECError("QEC_ANSWER_OBLIGATION_BINDING_INVALID")
    for unmet in answer["unmet_obligations"]:
        if set(unmet) != {"obligation_or_facet_id", "reason"}:
            raise QECError("QEC_ANSWER_UNMET_FIELDS_INVALID")
        if unmet["reason"] not in UNMET_REASONS:
            raise QECError("QEC_ANSWER_UNMET_REASON_INVALID")
    fixed = set(plan["plan_body"]["fixed_conjuncts"])
    claimed = {
        unit for claim in answer["claims"] for unit in claim["obligation_ids"]
    }
    if answer["status"] == "ANSWER" and (not answer["claims"] or fixed - claimed):
        raise QECError("QEC_ANSWER_STATUS_CONTRADICTS_FIXED_CONJUNCTS")
    if answer["status"] == "PARTIAL":
        if not answer["claims"] or not answer["unmet_obligations"]:
            raise QECError("QEC_PARTIAL_STATUS_INVALID")
    if answer["status"] == "ABSTAIN":
        if answer["claims"] or not answer["unmet_obligations"] or not answer["abstention_reason"]:
            raise QECError("QEC_ABSTAIN_STATUS_INVALID")


def decide_primary(
    *, contract: Mapping[str, Any], score_row: Mapping[str, Any]
) -> dict[str, Any]:
    actual = {
        "overall_complete_questions": score_row["full_question_recall_count"],
        "overall_required_heads": score_row["required_head_recall_count"],
        "B01-U0033_complete_questions": score_row["per_case"]["B01-U0033"]["question_hits"],
        "B01-U0033_required_heads": score_row["per_case"]["B01-U0033"]["head_hits"],
        "B02-U0039_complete_questions": score_row["per_case"]["B02-U0039"]["question_hits"],
        "B02-U0039_required_heads": score_row["per_case"]["B02-U0039"]["head_hits"],
        "B03-U0041_complete_questions": score_row["per_case"]["B03-U0041"]["question_hits"],
        "B03-U0041_required_heads": score_row["per_case"]["B03-U0041"]["head_hits"],
    }
    checks: list[dict[str, Any]] = []
    disposition = "REGISTER_MECHANICAL_CANDIDATE_ONLY"
    for rule in contract["primary_score_decision_order"]:
        passed = actual[rule["metric"]] >= rule["minimum"]
        checks.append({**rule, "actual": actual[rule["metric"]], "passed": passed})
        if not passed:
            disposition = rule["failure"]
            break
    result = {
        "schema_version": "v02-r2-qec-score-gate-decision.v1",
        "candidate_status": "candidate_silver_not_active",
        "primary_budget_chars": contract["primary_budget_chars"],
        "actual": actual,
        "ordered_checks": checks,
        "disposition": disposition,
        "register_candidate": disposition == "REGISTER_MECHANICAL_CANDIDATE_ONLY",
        "quality_boundary": "只测开发集冻结证据窗口覆盖，不等于答案正确率或 R2 终验成绩。",
        "model_api_calls": 0,
        "network_calls": 0,
    }
    result["decision_payload_sha256"] = sha256_bytes(canonical_bytes(result))
    return result
