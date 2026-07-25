#!/usr/bin/env python3
"""V02 D-USE X10/X11：封闭查询器与自然语言解析器候选件。

本工具不读仓库小说正文或模型产物。调用方只能显式传入已审查的封闭事实
集合；正式评分必须先有人工核准题面与答案。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from v02_duse_contract import (
    ANSWER_FREEZE_FILENAME,
    ANSWER_FREEZE_STATUS,
    CASE_KINDS,
    HUMAN_REQUIRED,
    NEW_METRICS,
    QUESTION_FREEZE_FILENAME,
    QUESTION_FREEZE_STATUS,
    QUESTION_FAMILIES,
    RESEARCH_QUESTION_FAMILIES,
    NEW_MISSING_FIELD_BUCKETS,
    QUERY_TYPES,
    RETURN_STATUSES,
    DUseContractError,
)


class DUseQueryError(DUseContractError):
    """查询、解析或评分输入不满足 D-USE 合同。"""


_NATURAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "CHARACTER_STATE_AT_CHAPTER_END",
        re.compile(
            r"^截至第(?P<chapter>[1-9][0-9]*)章，"
            r"(?P<entity>[A-Za-z0-9_.:-]+)的"
            r"(?P<slot>[A-Za-z0-9_.:-]+)是什么[？?]$"
        ),
    ),
    (
        "EPISTEMIC_KNOWLEDGE_AT_CHAPTER",
        re.compile(
            r"^截至第(?P<chapter>[1-9][0-9]*)章，"
            r"(?P<owner>[A-Za-z0-9_.:-]+)是否知道"
            r"(?P<entity>[A-Za-z0-9_.:-]+)的"
            r"(?P<slot>[A-Za-z0-9_.:-]+)[？?]$"
        ),
    ),
    (
        "GOAL_LIFECYCLE",
        re.compile(
            r"^截至第(?P<chapter>[1-9][0-9]*)章，"
            r"(?P<entity>[A-Za-z0-9_.:-]+)的目标"
            r"(?P<slot>[A-Za-z0-9_.:-]+)是什么[？?]$"
        ),
    ),
    (
        "FIRST_APPEARANCE",
        re.compile(
            r"^截至第(?P<chapter>[1-9][0-9]*)章，"
            r"(?P<entity>[A-Za-z0-9_.:-]+)的"
            r"(?P<slot>[A-Za-z0-9_.:-]+)首次出现在哪里[？?]$"
        ),
    ),
    (
        "LONG_RANGE_CONSISTENCY",
        re.compile(
            r"^截至第(?P<chapter>[1-9][0-9]*)章，"
            r"(?P<entity>[A-Za-z0-9_.:-]+)的"
            r"(?P<slot>[A-Za-z0-9_.:-]+)是否仍然一致[？?]$"
        ),
    ),
)

_QUERY_KEYS = {
    "query_type",
    "entity_id",
    "state_slot",
    "as_of_chapter",
    "epistemic_owner",
}
_FACT_KEYS = {
    "fact_id",
    "query_type",
    "entity_id",
    "state_slot",
    "epistemic_owner",
    "chapter",
    "valid_from_chapter",
    "valid_until_chapter",
    "source_block_id",
    "claim_span",
    "source_span_sha256",
    "verbatim_verified",
}
_QUESTION_TICKET_KEYS = {
    "schema_version",
    "status",
    "question_bank_sha256",
    "case_ids_sha256",
    "question_count",
    "source_read_by_human",
    "derived_from_model_output",
}
_ANSWER_TICKET_KEYS = {
    "schema_version",
    "status",
    "question_bank_sha256",
    "human_answer_bank_sha256",
    "case_ids_sha256",
    "answer_count",
    "reviewed_by_human",
    "derived_from_model_output",
}
_RESULT_KEYS = {
    "status",
    "query",
    "fact_ids",
    "evidence",
    "future_fact_ids_suppressed",
    "reason_code",
}
_EVIDENCE_KEYS = {
    "fact_id",
    "source_block_id",
    "claim_span",
    "source_span_sha256",
    "chapter",
    "verbatim_verified",
}
_QUESTION_FAMILY_CANDIDATE_KEYS = {
    "family_id",
    "family_group",
    "question_family",
    "question_text",
    "executable_query_type",
    "case_kind",
    "expected_answer",
    "human_authored",
    "review_status",
    "formal_question",
    "formal_answer",
    "scoreable",
}
_MISSING_FIELD_DIAGNOSTIC_ROW_KEYS = {
    "case_id",
    "bucket_reference",
    "diagnostic_reason",
    "review_status",
    "formal_diagnostic",
}
_BUCKET_REFERENCE_KEYS = {
    "reference_kind",
    "bucket_name",
    "external_bucket_ref",
}


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def question_projection(
    cases: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "case_id": case.get("case_id"),
            "case_kind": case.get("case_kind"),
            "question_text": case.get("question_text"),
            "closed_query": case.get("closed_query"),
        }
        for case in cases
    ]


def case_ids_projection(cases: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(case.get("case_id")) for case in cases]


def expected_freeze_bindings(
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "question_bank_sha256": canonical_sha256(question_projection(cases)),
        "human_answer_bank_sha256": canonical_sha256(list(cases)),
        "case_ids_sha256": canonical_sha256(case_ids_projection(cases)),
        "count": len(cases),
    }


def _read_ticket(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise DUseQueryError(f"{label}不存在，禁止正式计分：{path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DUseQueryError(f"{label}不可读，禁止正式计分") from exc
    if not isinstance(value, dict):
        raise DUseQueryError(f"{label}不是 JSON 对象")
    return value


def verify_formal_score_authority(
    cases: Sequence[Mapping[str, Any]],
    *,
    freeze_dir: Path,
) -> dict[str, Any]:
    """从磁盘读取两张冻结票，并把全部身份重新绑定到实际题库。"""

    if not isinstance(freeze_dir, Path):
        raise DUseQueryError("正式计分必须提供冻结票目录 Path")
    question_ticket = _read_ticket(
        freeze_dir / QUESTION_FREEZE_FILENAME,
        label="题库冻结票",
    )
    answer_ticket = _read_ticket(
        freeze_dir / ANSWER_FREEZE_FILENAME,
        label="人工答案冻结票",
    )
    if set(question_ticket) != _QUESTION_TICKET_KEYS:
        raise DUseQueryError("题库冻结票字段漂移")
    if set(answer_ticket) != _ANSWER_TICKET_KEYS:
        raise DUseQueryError("人工答案冻结票字段漂移")
    bindings = expected_freeze_bindings(cases)
    if (
        question_ticket["schema_version"] != "v02-duse-question-freeze-ticket.v1"
        or question_ticket["status"] != QUESTION_FREEZE_STATUS
        or question_ticket["source_read_by_human"] is not True
        or question_ticket["derived_from_model_output"] is not False
        or question_ticket["question_bank_sha256"] != bindings["question_bank_sha256"]
        or question_ticket["case_ids_sha256"] != bindings["case_ids_sha256"]
        or question_ticket["question_count"] != bindings["count"]
    ):
        raise DUseQueryError("题库冻结票状态、SHA 或数量不匹配")
    if (
        answer_ticket["schema_version"] != "v02-duse-human-answer-freeze-ticket.v1"
        or answer_ticket["status"] != ANSWER_FREEZE_STATUS
        or answer_ticket["reviewed_by_human"] is not True
        or answer_ticket["derived_from_model_output"] is not False
        or answer_ticket["question_bank_sha256"] != bindings["question_bank_sha256"]
        or answer_ticket["human_answer_bank_sha256"]
        != bindings["human_answer_bank_sha256"]
        or answer_ticket["case_ids_sha256"] != bindings["case_ids_sha256"]
        or answer_ticket["answer_count"] != bindings["count"]
    ):
        raise DUseQueryError("人工答案冻结票状态、SHA 或数量不匹配")
    return {
        "status": "FORMAL_SCORE_AUTHORITY_VERIFIED",
        "question_ticket_sha256": hashlib.sha256(
            (freeze_dir / QUESTION_FREEZE_FILENAME).read_bytes()
        ).hexdigest(),
        "answer_ticket_sha256": hashlib.sha256(
            (freeze_dir / ANSWER_FREEZE_FILENAME).read_bytes()
        ).hexdigest(),
        **bindings,
    }


def validate_closed_query(query: Mapping[str, Any]) -> dict[str, Any]:
    if set(query) != _QUERY_KEYS:
        raise DUseQueryError("封闭查询对象字段不完整或夹带未知字段")
    if query["query_type"] not in QUERY_TYPES:
        raise DUseQueryError("query_type 不在冻结枚举")
    for key in ("entity_id", "state_slot", "epistemic_owner"):
        if not isinstance(query[key], str) or not query[key].strip():
            raise DUseQueryError(f"{key} 必须是非空字符串")
    chapter = query["as_of_chapter"]
    if isinstance(chapter, bool) or not isinstance(chapter, int) or chapter < 1:
        raise DUseQueryError("as_of_chapter 必须是正整数")
    return dict(query)


def validate_question_family_candidate(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """校验冻结前题族工位，但绝不把它升级成可执行查询。"""

    if set(candidate) != _QUESTION_FAMILY_CANDIDATE_KEYS:
        raise DUseQueryError("题族候选字段不完整或夹带未知字段")
    family = candidate.get("question_family")
    if family not in QUESTION_FAMILIES:
        raise DUseQueryError("question_family 不在 C11.2 冻结枚举")
    expected_group = "RESEARCH" if family in RESEARCH_QUESTION_FAMILIES else "PRODUCT"
    if (
        candidate.get("family_group") != expected_group
        or not isinstance(candidate.get("family_id"), str)
        or not candidate["family_id"]
    ):
        raise DUseQueryError("题族分组或 family_id 非法")
    if (
        candidate.get("question_text") != HUMAN_REQUIRED
        or candidate.get("executable_query_type") is not None
        or candidate.get("case_kind") is not None
        or candidate.get("expected_answer") is not None
        or candidate.get("human_authored") is not False
        or candidate.get("review_status") != "HUMAN_REQUIRED"
        or candidate.get("formal_question") is not False
        or candidate.get("formal_answer") is not False
        or candidate.get("scoreable") is not False
    ):
        raise DUseQueryError(
            "题族工位仍须 HUMAN_REQUIRED，禁止冒充正式题面、答案或分数"
        )
    return dict(candidate)


def execute_question_family_candidate(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """显式拒绝把 question_family 维度当作 query_type 执行。"""

    validate_question_family_candidate(candidate)
    raise DUseQueryError("question_family 只是冻结前出题维度，禁止假执行 D-USE")


def validate_missing_field_diagnostic_candidate(
    row: Mapping[str, Any],
    *,
    legacy_bucket_catalog_status: str,
    verified_legacy_bucket_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """校验候选诊断行；旧目录缺失时不得把不透明引用当正式桶。"""

    if set(row) != _MISSING_FIELD_DIAGNOSTIC_ROW_KEYS:
        raise DUseQueryError("缺字段诊断行字段漂移")
    if (
        not isinstance(row.get("case_id"), str)
        or not row["case_id"]
        or not isinstance(row.get("diagnostic_reason"), str)
        or not row["diagnostic_reason"]
        or row.get("review_status") != "HUMAN_REQUIRED"
        or row.get("formal_diagnostic") is not False
    ):
        raise DUseQueryError("诊断行必须保持 HUMAN_REQUIRED 候选状态")
    reference = row.get("bucket_reference")
    if not isinstance(reference, Mapping) or set(reference) != (_BUCKET_REFERENCE_KEYS):
        raise DUseQueryError("bucket_reference 字段漂移")
    kind = reference.get("reference_kind")
    if kind == "NAMED_C11_CANDIDATE":
        if (
            reference.get("bucket_name") not in NEW_MISSING_FIELD_BUCKETS
            or reference.get("external_bucket_ref") is not None
        ):
            raise DUseQueryError("C11 具名候选桶非法")
    elif kind == "OPAQUE_EXTERNAL_LEGACY":
        external_ref = reference.get("external_bucket_ref")
        if reference.get("bucket_name") is not None:
            raise DUseQueryError("旧桶不得在本地补写语义名称")
        if legacy_bucket_catalog_status != "AVAILABLE_AND_VERIFIED":
            raise DUseQueryError(
                "旧七桶权威目录缺失，诊断行保持 HUMAN_REQUIRED 且不得冻结"
            )
        if (
            not isinstance(external_ref, str)
            or not external_ref
            or external_ref not in verified_legacy_bucket_refs
        ):
            raise DUseQueryError("旧桶引用未绑定已核准外部目录")
    else:
        raise DUseQueryError("缺字段桶引用类型非法")
    return dict(row)


def parse_natural_language_query(question_text: str) -> dict[str, Any]:
    """D-USE-B 的确定性语法；不调用模型、不猜无法解析的问题。"""

    if not isinstance(question_text, str) or not question_text.strip():
        raise DUseQueryError("自然语言问句为空")
    for query_type, pattern in _NATURAL_PATTERNS:
        matched = pattern.fullmatch(question_text.strip())
        if matched is None:
            continue
        groups = matched.groupdict()
        owner = groups.get("owner") or "OBJECTIVE"
        return validate_closed_query(
            {
                "query_type": query_type,
                "entity_id": groups["entity"],
                "state_slot": groups["slot"],
                "as_of_chapter": int(groups["chapter"]),
                "epistemic_owner": owner,
            }
        )
    raise DUseQueryError("问句不满足冻结语法，禁止模型猜写查询对象")


def validate_fact(fact: Mapping[str, Any]) -> dict[str, Any]:
    if set(fact) != _FACT_KEYS:
        raise DUseQueryError("事实行字段不完整或夹带未知字段")
    if fact["query_type"] not in QUERY_TYPES:
        raise DUseQueryError("事实行 query_type 非法")
    for key in (
        "fact_id",
        "entity_id",
        "state_slot",
        "epistemic_owner",
        "source_block_id",
        "claim_span",
        "source_span_sha256",
    ):
        if not isinstance(fact[key], str) or not fact[key]:
            raise DUseQueryError(f"事实行 {key} 必须是非空字符串")
    for key in ("chapter", "valid_from_chapter"):
        value = fact[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise DUseQueryError(f"事实行 {key} 必须是正整数")
    until = fact["valid_until_chapter"]
    if until is not None and (
        isinstance(until, bool)
        or not isinstance(until, int)
        or until < fact["valid_from_chapter"]
    ):
        raise DUseQueryError("valid_until_chapter 非法")
    if not isinstance(fact["verbatim_verified"], bool):
        raise DUseQueryError("verbatim_verified 必须是布尔值")
    return dict(fact)


def _same_scope(fact: Mapping[str, Any], query: Mapping[str, Any]) -> bool:
    return all(
        fact[key] == query[key]
        for key in (
            "query_type",
            "entity_id",
            "state_slot",
            "epistemic_owner",
        )
    )


def _evidence(fact: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "fact_id": fact["fact_id"],
        "source_block_id": fact["source_block_id"],
        "claim_span": fact["claim_span"],
        "source_span_sha256": fact["source_span_sha256"],
        "chapter": fact["chapter"],
        "verbatim_verified": fact["verbatim_verified"],
    }


def execute_closed_query(
    query: Mapping[str, Any],
    facts: Iterable[Mapping[str, Any]],
    *,
    material_complete_through_chapter: int,
) -> dict[str, Any]:
    """D-USE-A 查询；N+1 事实只能进入抑制旁账，不能进入 FOUND。"""

    normalized_query = validate_closed_query(query)
    if (
        isinstance(material_complete_through_chapter, bool)
        or not isinstance(material_complete_through_chapter, int)
        or material_complete_through_chapter < 0
    ):
        raise DUseQueryError("材料完整章界非法")
    normalized_facts = [validate_fact(fact) for fact in facts]
    scoped = [fact for fact in normalized_facts if _same_scope(fact, normalized_query)]
    future = sorted(
        fact["fact_id"]
        for fact in scoped
        if fact["chapter"] > normalized_query["as_of_chapter"]
    )
    eligible = [
        fact for fact in scoped if fact["chapter"] <= normalized_query["as_of_chapter"]
    ]

    if normalized_query["query_type"] == "FIRST_APPEARANCE" and eligible:
        earliest = min(fact["chapter"] for fact in eligible)
        found = [fact for fact in eligible if fact["chapter"] == earliest]
    else:
        found = [
            fact
            for fact in eligible
            if fact["valid_from_chapter"] <= normalized_query["as_of_chapter"]
            and (
                fact["valid_until_chapter"] is None
                or normalized_query["as_of_chapter"] <= fact["valid_until_chapter"]
            )
        ]
        if found:
            latest = max(fact["valid_from_chapter"] for fact in found)
            found = [fact for fact in found if fact["valid_from_chapter"] == latest]

    if found:
        found.sort(key=lambda row: (row["chapter"], row["fact_id"]))
        status = "FOUND"
        reason = "MATCH_FOUND"
    elif eligible and any(
        fact["valid_until_chapter"] is not None
        and fact["valid_until_chapter"] < normalized_query["as_of_chapter"]
        for fact in eligible
    ):
        status = "UNKNOWN"
        reason = "STATE_GAP_AFTER_EXPIRED_FACT"
    elif material_complete_through_chapter >= normalized_query["as_of_chapter"]:
        status = "NOT_FOUND"
        reason = "COMPLETE_SCOPE_NO_MATCH"
    else:
        status = "UNKNOWN"
        reason = "MATERIAL_SCOPE_INCOMPLETE"

    return {
        "status": status,
        "query": normalized_query,
        "fact_ids": [fact["fact_id"] for fact in found],
        "evidence": [_evidence(fact) for fact in found],
        "future_fact_ids_suppressed": future,
        "reason_code": reason,
    }


def execute_natural_language_query(
    question_text: str,
    facts: Iterable[Mapping[str, Any]],
    *,
    material_complete_through_chapter: int,
) -> dict[str, Any]:
    """D-USE-B 只负责解析，再明确调用 D-USE-A。两层仍须分开计分。"""

    parsed = parse_natural_language_query(question_text)
    return {
        "parser_output": parsed,
        "query_result": execute_closed_query(
            parsed,
            facts,
            material_complete_through_chapter=(material_complete_through_chapter),
        ),
        "scorecards_must_remain_separate": True,
    }


def _require_human_verified(case: Mapping[str, Any]) -> None:
    if (
        case.get("review_status") != "HUMAN_VERIFIED"
        or case.get("question_text") in (None, "", HUMAN_REQUIRED)
        or case.get("expected_status") not in RETURN_STATUSES
        or case.get("derived_from_model_output") is not False
        or case.get("source_read_by_human") is not True
    ):
        raise DUseQueryError(
            "存在 HUMAN_REQUIRED 或非人工核准答案，禁止执行正式 D-USE 评分"
        )


def validate_result_against_case(
    case: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """在计分前钉死题目、截止章、事实 ID 与逐条证据的对应关系。"""

    if set(result) != _RESULT_KEYS:
        raise DUseQueryError("查询结果字段不完整或夹带未知字段")
    expected_query = validate_closed_query(case.get("closed_query", {}))
    actual_query = validate_closed_query(result.get("query", {}))
    if actual_query != expected_query:
        raise DUseQueryError("result.query 与 case.closed_query 不逐字一致，禁止计分")
    status = result.get("status")
    if status not in RETURN_STATUSES:
        raise DUseQueryError("查询结果状态非法")
    fact_ids = result.get("fact_ids")
    evidence = result.get("evidence")
    suppressed = result.get("future_fact_ids_suppressed")
    if (
        not isinstance(fact_ids, list)
        or any(not isinstance(value, str) or not value for value in fact_ids)
        or len(fact_ids) != len(set(fact_ids))
    ):
        raise DUseQueryError("fact_ids 必须是无重复的非空字符串列表")
    if not isinstance(evidence, list):
        raise DUseQueryError("evidence 必须是列表")
    if (
        not isinstance(suppressed, list)
        or any(not isinstance(value, str) or not value for value in suppressed)
        or len(suppressed) != len(set(suppressed))
    ):
        raise DUseQueryError("future_fact_ids_suppressed 必须是无重复字符串列表")

    evidence_fact_ids: list[str] = []
    for row in evidence:
        if not isinstance(row, Mapping) or set(row) != _EVIDENCE_KEYS:
            raise DUseQueryError("evidence 行字段不完整或夹带未知字段")
        fact_id = row.get("fact_id")
        chapter = row.get("chapter")
        if not isinstance(fact_id, str) or not fact_id:
            raise DUseQueryError("evidence.fact_id 非法")
        if isinstance(chapter, bool) or not isinstance(chapter, int) or chapter < 1:
            raise DUseQueryError("evidence.chapter 非法")
        for key in ("source_block_id", "claim_span", "source_span_sha256"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise DUseQueryError(f"evidence.{key} 非法")
        if not isinstance(row.get("verbatim_verified"), bool):
            raise DUseQueryError("evidence.verbatim_verified 非法")
        evidence_fact_ids.append(fact_id)
    if len(evidence_fact_ids) != len(set(evidence_fact_ids)):
        raise DUseQueryError("evidence.fact_id 重复")

    if status == "FOUND":
        if not fact_ids:
            raise DUseQueryError("FOUND 必须带非空 fact_ids")
        if set(fact_ids) != set(evidence_fact_ids):
            raise DUseQueryError(
                "FOUND 的 fact_ids 与 evidence.fact_id 必须一一完全相等"
            )
        if result.get("reason_code") != "MATCH_FOUND":
            raise DUseQueryError("FOUND 的 reason_code 必须是 MATCH_FOUND")
    else:
        if fact_ids or evidence:
            raise DUseQueryError("非 FOUND 的 fact_ids 与 evidence 必须都为空")
        allowed_reasons = {
            "NOT_FOUND": {"COMPLETE_SCOPE_NO_MATCH"},
            "UNKNOWN": {
                "MATERIAL_SCOPE_INCOMPLETE",
                "STATE_GAP_AFTER_EXPIRED_FACT",
            },
        }
        if result.get("reason_code") not in allowed_reasons[status]:
            raise DUseQueryError("非 FOUND 的 reason_code 与状态不一致")
    return dict(result)


def score_x10_x11_metrics(
    cases: Sequence[Mapping[str, Any]],
    results: Sequence[Mapping[str, Any]],
    *,
    freeze_dir: Path,
) -> dict[str, Any]:
    """只算 X10/X11 四项分列读数，不合成总分。"""

    if len(cases) != len(results) or not cases:
        raise DUseQueryError("题目与结果必须非空且一一对应")
    for case in cases:
        _require_human_verified(case)
    authority = verify_formal_score_authority(
        cases,
        freeze_dir=freeze_dir,
    )

    future_leaks = 0
    empty_denominator = 0
    empty_false_positives = 0
    stale_denominator = 0
    stale_returns = 0
    found_rows = 0
    complete_found_rows = 0
    per_case: list[dict[str, Any]] = []
    for case, result in zip(cases, results, strict=True):
        validated_result = validate_result_against_case(case, result)
        query = validated_result["query"]
        evidence = validated_result["evidence"]
        fact_ids = validated_result["fact_ids"]
        leaked = any(
            isinstance(row, Mapping)
            and isinstance(row.get("chapter"), int)
            and row["chapter"] > query["as_of_chapter"]
            for row in evidence
        )
        future_leaks += int(leaked)
        if case["expected_status"] == "NOT_FOUND":
            empty_denominator += 1
            empty_false_positives += int(validated_result["status"] == "FOUND")
        if case.get("case_kind") == "UPDATED_STATE_HISTORY_ONLY":
            stale_denominator += 1
            expected = set(case.get("expected_fact_ids", []))
            stale_returns += int(
                validated_result["status"] == "FOUND"
                and not set(fact_ids).issubset(expected)
            )
        row_complete = 0
        if validated_result["status"] == "FOUND":
            found_rows += len(fact_ids)
            evidence_by_fact = {
                row.get("fact_id"): row for row in evidence if isinstance(row, Mapping)
            }
            for fact_id in fact_ids:
                row = evidence_by_fact.get(fact_id)
                if (
                    isinstance(row, Mapping)
                    and row.get("verbatim_verified") is True
                    and isinstance(row.get("claim_span"), str)
                    and bool(row["claim_span"])
                ):
                    complete_found_rows += 1
                    row_complete += 1
        per_case.append(
            {
                "case_id": case["case_id"],
                "future_leak": leaked,
                "found_trace_complete_count": row_complete,
            }
        )

    def rate(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    metrics = {
        "future_information_leak_rate": rate(future_leaks, len(cases)),
        "empty_answer_false_positive_rate": rate(
            empty_false_positives, empty_denominator
        ),
        "stale_state_false_return_rate": rate(stale_returns, stale_denominator),
        "found_trace_completeness_rate": rate(complete_found_rows, found_rows),
    }
    if set(metrics) != set(NEW_METRICS):
        raise DUseQueryError("X10/X11 四项读数漂移")
    return {
        "schema_version": "v02-duse-x10-x11-score.v1",
        "scorecard": "D-USE-A",
        "metrics": metrics,
        "denominators": {
            "all_cases": len(cases),
            "explicit_no_answer_cases": empty_denominator,
            "updated_state_cases": stale_denominator,
            "found_fact_rows": found_rows,
        },
        "per_case": per_case,
        "combined_total_accuracy_emitted": False,
        "formal_score_authority": authority,
    }


def score_parser_exact_match(
    human_verified_items: Sequence[Mapping[str, Any]],
    *,
    freeze_dir: Path,
) -> dict[str, Any]:
    """D-USE-B 独立成绩单；禁止与查询器分数合成。"""

    if not human_verified_items:
        raise DUseQueryError("解析器评分集为空")
    authority = verify_formal_score_authority(
        human_verified_items,
        freeze_dir=freeze_dir,
    )
    matched = 0
    rejected = 0
    for item in human_verified_items:
        _require_human_verified(item)
        expected = validate_closed_query(item["closed_query"])
        try:
            actual = parse_natural_language_query(item["question_text"])
        except DUseQueryError:
            rejected += 1
            continue
        matched += int(actual == expected)
    return {
        "schema_version": "v02-duse-parser-score.v1",
        "scorecard": "D-USE-B",
        "closed_query_exact_match_rate": matched / len(human_verified_items),
        "parse_reject_rate": rejected / len(human_verified_items),
        "combined_with_d_use_a": False,
        "formal_score_authority": authority,
    }


def case_kind_counts(cases: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(case.get("case_kind")) for case in cases)
    return {kind: counts.get(kind, 0) for kind in CASE_KINDS}
