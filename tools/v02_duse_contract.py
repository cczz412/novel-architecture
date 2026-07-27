#!/usr/bin/env python3
"""V02 D-USE X10/X11：冻结前合同与人工题面空白模板。

本工具只建立查询对象、自然语言解析输入、三态返回、人工答案模板和
题面冻结前预检。它没有模型客户端，不读取小说正文或抽取产物，也不会
生成正式题面、预期答案或 D-USE 成绩。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_DUSE_X10_X11_20260725"
)
DEFAULT_C11_OUTPUT_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C11_product_north_star_20260725"
    / "C11_2_duse_question_expansion"
)
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
HUMAN_REQUIRED = "__HUMAN_REQUIRED__"

QUERY_TYPES = (
    "CHARACTER_STATE_AT_CHAPTER_END",
    "EPISTEMIC_KNOWLEDGE_AT_CHAPTER",
    "GOAL_LIFECYCLE",
    "FIRST_APPEARANCE",
    "LONG_RANGE_CONSISTENCY",
)
CASE_KINDS = (
    "UNIQUE_ANSWER",
    "MULTIPLE_LEGAL_ANSWERS",
    "EXPLICIT_NO_ANSWER",
    "MATERIAL_INSUFFICIENT_UNKNOWN",
    "AS_OF_CHAPTER_CUTOFF",
    "UPDATED_STATE_HISTORY_ONLY",
    "FUTURE_CANARY_N_PLUS_1",
)
QUESTION_FAMILIES = (
    "RESEARCH_RECENT_RESOURCE_DECREASE",
    "RESEARCH_ANTAGONIST_KNOWLEDGE",
    "RESEARCH_UNRESOLVED_THREAD_DUE_WITHIN_TWO_CHAPTERS",
    "RESEARCH_RULE_PRIOR_OCCURRENCES",
    "RESEARCH_UNFULFILLED_READER_PROMISES",
    "RESEARCH_DECISION_INFORMATION_SUFFICIENCY",
    "PRODUCT_STORYBOARD_RECONSTRUCTION",
    "PRODUCT_CHARACTER_DECISION_KNOWLEDGE_SET",
    "PRODUCT_PLAN_FULFILLMENT",
)
RESEARCH_QUESTION_FAMILIES = QUESTION_FAMILIES[:6]
PRODUCT_QUESTION_FAMILIES = QUESTION_FAMILIES[6:]
NEW_MISSING_FIELD_BUCKETS = (
    "SCENE_VISUAL_MISSING",
    "EMOTION_INTENSITY_MISSING",
)
LEGACY_MISSING_FIELD_BUCKET_TOTAL = 7
RESULTING_MISSING_FIELD_BUCKET_TOTAL = LEGACY_MISSING_FIELD_BUCKET_TOTAL + len(
    NEW_MISSING_FIELD_BUCKETS
)
RETURN_STATUSES = ("FOUND", "NOT_FOUND", "UNKNOWN")
NEW_METRICS = (
    "future_information_leak_rate",
    "empty_answer_false_positive_rate",
    "stale_state_false_return_rate",
    "found_trace_completeness_rate",
)
QUESTION_FREEZE_STATUS = "QUESTION_SET_FROZEN"
ANSWER_FREEZE_STATUS = "HUMAN_ANSWERS_FROZEN"
QUESTION_FREEZE_FILENAME = "question_set.freeze.json"
ANSWER_FREEZE_FILENAME = "human_answers.freeze.json"
ORIGINAL_METRICS = (
    "retrieval_rate",
    "answer_correctness_rate",
    "verbatim_source_verification_rate",
)
FREEZE_MARKER_NAMES = (
    "question_set.freeze.json",
    "question_freeze_receipt.json",
    "prompt_freeze_receipt.json",
)
C11_WORK_ORDER_PAGE_ID = "eb8821e57b67472db9f220b46110dcfd"
C11_WORK_ORDER_PAGE_URL = (
    "https://app.notion.com/p/"
    "v0-2-0API-A-CZ-Codex-_20260725-eb8821e57b67472db9f220b46110dcfd"
)
C11_AUTHORITY_READBACK_AT = "2026-07-25T10:46:11.303Z"
C11_2_AUTHORITY_EXCERPT = """### C11.2 D-USE 题面扩题（❌ 仍不写答案、仍 HUMAN_REQUIRED、❌ 仍只准看章节原文）
<callout icon="⏳">
\t**时间窗硬约束**：题面一旦出 SHA 冻结就不准改，故本条必须在冻结**之前**完成，与 C10.3 一次性并入。
</callout>
- **并入研究包六类查询题型**（只拿来定**题型**，❌ 不得拿来定答案）：主角最近一次资源减少在何时／反派目前知道到哪一步／两章内必须收的线／这条世界规则之前在哪些事件里生效／仍未兑现的读者承诺／某章某角色做决定时有没有足够信息。
- **新增三类产品题型（由产品北极星页第五节推出）**：① **分镜可重建题**——给定第 N 章，能否只凭底账重建出场景与镜头（现阶段预期大量失败，**失败本身就是画面／情绪层缺失的量化证据**）；② **角色降智题**——第 N 章某角色做决定时，系统能否报出该角色**当时已知的信息集合**（直接对应归属层与 X14）；③ **计划兑现题**——前文放下的铺垫到后章是否被标为已兑现／未兑现／被推翻。
- **缺字段归因表由七桶扩为九桶**：新增⑧ **画面／场景信息缺失**、⑨ **情绪／强度信息缺失**。其余七桶与记数规则照 §9.1-E.4 不变。
- ❌ 不得因为新增题型而放宽「出题只准看章节原文」；❌ 不得由任何模型代写题目或答案（D-USE 回包已自行守住此线，继续保持）。"""
C11_QUESTION_EXPANSION_RELATIVE_PATHS = (
    "README.md",
    "attribution_receipt.json",
    "authority_excerpt.json",
    "catalog/missing_field_bucket_expansion.json",
    "catalog/question_family_catalog.json",
    "contracts/missing_field_bucket_registry.v1.schema.json",
    "contracts/missing_field_diagnostic_row.v1.schema.json",
    "contracts/question_family_candidate.v1.schema.json",
    "preflight/human_required_block_receipt.json",
    "preflight/question_expansion_preflight.json",
    "templates/question_family.blank.json",
)


class DUseContractError(RuntimeError):
    """D-USE 合同或冻结前置不满足。"""


class ExistingQuestionFreezeError(DUseContractError):
    """已存在冻结题面，不允许原位改写。"""


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def strict_object(
    properties: Mapping[str, Any],
    *,
    required: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": dict(properties),
        "required": list(required or properties),
    }


def string(*, minimum: int = 1) -> dict[str, Any]:
    return {"type": "string", "minLength": minimum}


def closed_query_schema() -> dict[str, Any]:
    """D-USE-A 的唯一封闭查询对象。"""

    return {
        "$schema": DRAFT_2020_12,
        "$id": "https://local.invalid/v02/duse/closed_query.v1.schema.json",
        "title": "D-USE-A 封闭查询对象",
        **strict_object(
            {
                "query_type": {
                    "type": "string",
                    "enum": list(QUERY_TYPES),
                },
                "entity_id": string(),
                "state_slot": string(),
                "as_of_chapter": {"type": "integer", "minimum": 1},
                "epistemic_owner": string(),
            }
        ),
        "x_boundary": (
            "D-USE-A 直接读取本对象，只测数据层与查询器；不得混入自然语言"
            "解析结果的准确率。"
        ),
    }


def natural_language_query_schema() -> dict[str, Any]:
    """D-USE-B 的自然语言输入与解析目标。"""

    return {
        "$schema": DRAFT_2020_12,
        "$id": ("https://local.invalid/v02/duse/natural_language_query.v1.schema.json"),
        "title": "D-USE-B 自然语言解析输入",
        **strict_object(
            {
                "case_id": string(),
                "question_text": string(),
                "human_authored": {"type": "boolean", "const": True},
                "expected_closed_query": closed_query_schema(),
                "review_status": {
                    "type": "string",
                    "const": "HUMAN_VERIFIED",
                },
            }
        ),
        "x_boundary": (
            "D-USE-B 只测自然语言到封闭查询对象的解析；不得与 D-USE-A"
            "查询正确率合并成一个总准确率。"
        ),
    }


def evidence_schema() -> dict[str, Any]:
    return strict_object(
        {
            "fact_id": string(),
            "source_block_id": string(),
            "claim_span": string(),
            "source_span_sha256": string(),
            "chapter": {"type": "integer", "minimum": 1},
            "verbatim_verified": {"type": "boolean"},
        }
    )


def query_result_schema() -> dict[str, Any]:
    schema = {
        "$schema": DRAFT_2020_12,
        "$id": "https://local.invalid/v02/duse/query_result.v1.schema.json",
        "title": "D-USE 查询三态返回",
        **strict_object(
            {
                "status": {
                    "type": "string",
                    "enum": list(RETURN_STATUSES),
                },
                "query": closed_query_schema(),
                "fact_ids": {
                    "type": "array",
                    "uniqueItems": True,
                    "items": string(),
                },
                "evidence": {
                    "type": "array",
                    "items": evidence_schema(),
                },
                "future_fact_ids_suppressed": {
                    "type": "array",
                    "uniqueItems": True,
                    "items": string(),
                },
                "reason_code": {
                    "type": "string",
                    "enum": [
                        "MATCH_FOUND",
                        "COMPLETE_SCOPE_NO_MATCH",
                        "MATERIAL_SCOPE_INCOMPLETE",
                        "STATE_GAP_AFTER_EXPIRED_FACT",
                    ],
                },
            }
        ),
        "x_status_rule": (
            "没有查到不得自动解释为不存在：材料完整且确认无匹配才是 "
            "NOT_FOUND；材料不全或状态链断档必须返回 UNKNOWN。"
        ),
    }
    schema["allOf"] = [
        {
            "if": {
                "properties": {"status": {"const": "FOUND"}},
                "required": ["status"],
            },
            "then": {
                "properties": {
                    "fact_ids": {"minItems": 1},
                    "evidence": {"minItems": 1},
                    "reason_code": {"const": "MATCH_FOUND"},
                }
            },
            "else": {
                "properties": {
                    "fact_ids": {"maxItems": 0},
                    "evidence": {"maxItems": 0},
                }
            },
        }
    ]
    schema["x_fact_evidence_binding"] = (
        "程序闸须验证 fact_ids 非空且唯一，并与 evidence.fact_id 一一唯一、"
        "集合完全相等；JSON Schema 不能表达的跨数组约束不得省略。"
    )
    return schema


def human_answer_template_schema() -> dict[str, Any]:
    return {
        "$schema": DRAFT_2020_12,
        "$id": ("https://local.invalid/v02/duse/human_answer_template.v1.schema.json"),
        "title": "D-USE 人工题面与预期答案模板",
        **strict_object(
            {
                "case_id": string(),
                "case_kind": {
                    "type": "string",
                    "enum": list(CASE_KINDS),
                },
                "question_text": string(),
                "closed_query": closed_query_schema(),
                "expected_status": {
                    "oneOf": [
                        {"type": "null"},
                        {
                            "type": "string",
                            "enum": list(RETURN_STATUSES),
                        },
                    ]
                },
                "expected_fact_ids": {
                    "type": "array",
                    "uniqueItems": True,
                    "items": string(),
                },
                "expected_evidence_spans": {
                    "type": "array",
                    "items": string(),
                },
                "source_read_by_human": {"type": "boolean"},
                "derived_from_model_output": {
                    "type": "boolean",
                    "const": False,
                },
                "review_status": {
                    "type": "string",
                    "enum": ["HUMAN_REQUIRED", "HUMAN_VERIFIED"],
                },
            }
        ),
        "x_oracle_boundary": (
            "当前没有 X06 oracle。首版预期答案只能由本地人员肉眼对照"
            "章节原文填写；不得由模型生成，也不得从被测抽取产物反推。"
        ),
    }


def question_family_candidate_schema() -> dict[str, Any]:
    """C11.2 冻结前题族工位；题族不冒充可执行查询或案例类型。"""

    return {
        "$schema": DRAFT_2020_12,
        "$id": (
            "https://local.invalid/v02/duse/question_family_candidate.v1.schema.json"
        ),
        "title": "C11.2 D-USE 题族候选工位",
        **strict_object(
            {
                "family_id": string(),
                "family_group": {
                    "type": "string",
                    "enum": ["RESEARCH", "PRODUCT"],
                },
                "question_family": {
                    "type": "string",
                    "enum": list(QUESTION_FAMILIES),
                },
                "question_text": {
                    "type": "string",
                    "const": HUMAN_REQUIRED,
                },
                "executable_query_type": {"type": "null"},
                "case_kind": {"type": "null"},
                "expected_answer": {"type": "null"},
                "human_authored": {"type": "boolean", "const": False},
                "review_status": {
                    "type": "string",
                    "const": "HUMAN_REQUIRED",
                },
                "formal_question": {"type": "boolean", "const": False},
                "formal_answer": {"type": "boolean", "const": False},
                "scoreable": {"type": "boolean", "const": False},
            }
        ),
        "x_dimension_boundary": (
            "question_family 是冻结前出题维度，不是 query_type，也不是 "
            "case_kind。人工写题、选定既有 query_type 与 case_kind、冻结"
            "题面和答案之前，不得执行或计分。"
        ),
    }


def missing_field_bucket_registry_schema() -> dict[str, Any]:
    """只登记可证实的 7+2 扩容，不编造旧七桶名称。"""

    return {
        "$schema": DRAFT_2020_12,
        "$id": (
            "https://local.invalid/v02/duse/"
            "missing_field_bucket_registry.v1.schema.json"
        ),
        "title": "C11.2 缺字段桶扩容登记",
        **strict_object(
            {
                "schema_version": {
                    "type": "string",
                    "const": "v02-duse-missing-field-buckets.c11.2.v1",
                },
                "status": {
                    "type": "string",
                    "const": "HUMAN_REQUIRED",
                },
                "legacy_bucket_total": {
                    "type": "integer",
                    "const": LEGACY_MISSING_FIELD_BUCKET_TOTAL,
                },
                "legacy_bucket_catalog_status": {
                    "type": "string",
                    "const": "LEGACY_NAMES_MISSING",
                },
                "legacy_bucket_refs": {
                    "type": "array",
                    "maxItems": 0,
                },
                "named_additions": {
                    "type": "array",
                    "uniqueItems": True,
                    "minItems": len(NEW_MISSING_FIELD_BUCKETS),
                    "maxItems": len(NEW_MISSING_FIELD_BUCKETS),
                    "items": {
                        "type": "string",
                        "enum": list(NEW_MISSING_FIELD_BUCKETS),
                    },
                },
                "resulting_bucket_total": {
                    "type": "integer",
                    "const": RESULTING_MISSING_FIELD_BUCKET_TOTAL,
                },
                "formal_diagnostic_freeze_allowed": {
                    "type": "boolean",
                    "const": False,
                },
                "formal_diagnostic_row_count": {
                    "type": "integer",
                    "const": 0,
                },
                "formal_score_count": {
                    "type": "integer",
                    "const": 0,
                },
            }
        ),
        "x_missing_catalog_boundary": (
            "仓内没有旧七桶权威目录，只能核对旧总数 7 与新增两桶。"
            "不得生成占位旧桶名；旧桶正式引用须等待外部目录核准。"
        ),
    }


def missing_field_diagnostic_row_schema() -> dict[str, Any]:
    """未来诊断行的候选 schema；当前旧桶目录缺失，不能冻结正式行。"""

    bucket_reference = {
        "oneOf": [
            strict_object(
                {
                    "reference_kind": {
                        "type": "string",
                        "const": "NAMED_C11_CANDIDATE",
                    },
                    "bucket_name": {
                        "type": "string",
                        "enum": list(NEW_MISSING_FIELD_BUCKETS),
                    },
                    "external_bucket_ref": {"type": "null"},
                }
            ),
            strict_object(
                {
                    "reference_kind": {
                        "type": "string",
                        "const": "OPAQUE_EXTERNAL_LEGACY",
                    },
                    "bucket_name": {"type": "null"},
                    "external_bucket_ref": string(),
                }
            ),
        ]
    }
    return {
        "$schema": DRAFT_2020_12,
        "$id": (
            "https://local.invalid/v02/duse/missing_field_diagnostic_row.v1.schema.json"
        ),
        "title": "C11.2 缺字段诊断行候选",
        **strict_object(
            {
                "case_id": string(),
                "bucket_reference": bucket_reference,
                "diagnostic_reason": string(),
                "review_status": {
                    "type": "string",
                    "const": "HUMAN_REQUIRED",
                },
                "formal_diagnostic": {"type": "boolean", "const": False},
            }
        ),
        "x_execution_boundary": (
            "新增两桶只具候选名；旧桶只准用外部目录给出的不透明引用。"
            "旧目录未核准时，整张诊断表不得冻结或进入正式读数。"
        ),
    }


def question_freeze_ticket_schema() -> dict[str, Any]:
    return {
        "$schema": DRAFT_2020_12,
        "$id": ("https://local.invalid/v02/duse/question_freeze_ticket.v1.schema.json"),
        "title": "D-USE 题库冻结票",
        **strict_object(
            {
                "schema_version": {
                    "type": "string",
                    "const": "v02-duse-question-freeze-ticket.v1",
                },
                "status": {
                    "type": "string",
                    "const": QUESTION_FREEZE_STATUS,
                },
                "question_bank_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "case_ids_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "question_count": {"type": "integer", "minimum": 1},
                "source_read_by_human": {"type": "boolean", "const": True},
                "derived_from_model_output": {
                    "type": "boolean",
                    "const": False,
                },
            }
        ),
        "x_boundary": (
            "正式计分必须从冻结目录读取本票，并把 SHA 与实际题库重新计算"
            "核对；调用方口头声明或布尔字段不能替代。"
        ),
    }


def human_answer_freeze_ticket_schema() -> dict[str, Any]:
    return {
        "$schema": DRAFT_2020_12,
        "$id": (
            "https://local.invalid/v02/duse/human_answer_freeze_ticket.v1.schema.json"
        ),
        "title": "D-USE 人工答案冻结票",
        **strict_object(
            {
                "schema_version": {
                    "type": "string",
                    "const": "v02-duse-human-answer-freeze-ticket.v1",
                },
                "status": {
                    "type": "string",
                    "const": ANSWER_FREEZE_STATUS,
                },
                "question_bank_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "human_answer_bank_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "case_ids_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "answer_count": {"type": "integer", "minimum": 1},
                "reviewed_by_human": {"type": "boolean", "const": True},
                "derived_from_model_output": {
                    "type": "boolean",
                    "const": False,
                },
            }
        ),
        "x_boundary": (
            "答案票必须与同一题库 SHA、案例集合 SHA 和实际人工答案文件"
            "SHA 绑定；当前空白模板不得生成本票。"
        ),
    }


def metric_contract() -> dict[str, Any]:
    return {
        "schema_version": "v02-duse-metrics.v1",
        "scorecards": {
            "D-USE-A": {
                "purpose": "只测封闭查询对象的数据层与查询器",
                "original_metrics": list(ORIGINAL_METRICS),
                "x10_x11_metrics": list(NEW_METRICS),
            },
            "D-USE-B": {
                "purpose": "只测自然语言问句到封闭查询对象的解析器",
                "metrics": [
                    "closed_query_exact_match_rate",
                    "parse_reject_rate",
                ],
            },
        },
        "combined_total_accuracy_forbidden": True,
        "x10_x11_metrics_must_be_reported_separately": True,
        "formal_score_requires_question_and_answer_freeze_tickets": True,
        "freeze_ticket_filenames": [
            QUESTION_FREEZE_FILENAME,
            ANSWER_FREEZE_FILENAME,
        ],
        "formal_scores_emitted": False,
    }


def blank_human_templates() -> dict[str, Any]:
    """只产七类空白人工工位，不产生正式题面或答案。"""

    rows: list[dict[str, Any]] = []
    for ordinal, case_kind in enumerate(CASE_KINDS, 1):
        rows.append(
            {
                "case_id": f"DUSE-HUMAN-{ordinal:02d}",
                "case_kind": case_kind,
                "question_text": HUMAN_REQUIRED,
                "closed_query": {
                    "query_type": HUMAN_REQUIRED,
                    "entity_id": HUMAN_REQUIRED,
                    "state_slot": HUMAN_REQUIRED,
                    "as_of_chapter": 1,
                    "epistemic_owner": HUMAN_REQUIRED,
                },
                "expected_status": None,
                "expected_fact_ids": [],
                "expected_evidence_spans": [],
                "source_read_by_human": False,
                "derived_from_model_output": False,
                "review_status": "HUMAN_REQUIRED",
            }
        )
    return {
        "schema_version": "v02-duse-human-question-bank.blank.v1",
        "status": "HUMAN_REQUIRED",
        "question_set_frozen": False,
        "formal_question_count": 0,
        "formal_answer_count": 0,
        "rows": rows,
    }


def question_family_catalog() -> dict[str, Any]:
    """C11.2 批准的九个出题方向；不含人工题面与答案。"""

    descriptions = {
        "RESEARCH_RECENT_RESOURCE_DECREASE": (
            "查询人物或组织最近一次资源减少及其时间边界"
        ),
        "RESEARCH_ANTAGONIST_KNOWLEDGE": ("查询对手在指定章节截止点已经知道什么"),
        "RESEARCH_UNRESOLVED_THREAD_DUE_WITHIN_TWO_CHAPTERS": (
            "查询两章内到期但尚未解决的线索或事项"
        ),
        "RESEARCH_RULE_PRIOR_OCCURRENCES": ("查询某条规则此前出现过的章节与证据"),
        "RESEARCH_UNFULFILLED_READER_PROMISES": (
            "查询文本已向读者许下但尚未兑现的承诺"
        ),
        "RESEARCH_DECISION_INFORMATION_SUFFICIENCY": (
            "查询人物作出决定时掌握的信息是否足够"
        ),
        "PRODUCT_STORYBOARD_RECONSTRUCTION": ("查询能否从结构数据还原分镜所需场景要素"),
        "PRODUCT_CHARACTER_DECISION_KNOWLEDGE_SET": (
            "查询人物作决定时的知识集合，用于检查降智"
        ),
        "PRODUCT_PLAN_FULFILLMENT": ("查询计划事项后来是否兑现、变体实现或延后"),
    }
    rows = [
        {
            "question_family": family,
            "family_group": (
                "RESEARCH" if family in RESEARCH_QUESTION_FAMILIES else "PRODUCT"
            ),
            "design_brief": descriptions[family],
            "question_text": HUMAN_REQUIRED,
            "executable_query_type": None,
            "case_kind": None,
            "formal_question": False,
            "formal_answer": False,
            "scoreable": False,
        }
        for family in QUESTION_FAMILIES
    ]
    return {
        "schema_version": "v02-duse-question-family-catalog.c11.2.v1",
        "status": "HUMAN_REQUIRED",
        "dimension_name": "question_family",
        "independent_from": ["query_type", "case_kind"],
        "executable_query_types_unchanged": list(QUERY_TYPES),
        "case_kinds_unchanged": list(CASE_KINDS),
        "research_family_count": len(RESEARCH_QUESTION_FAMILIES),
        "product_family_count": len(PRODUCT_QUESTION_FAMILIES),
        "rows": rows,
        "formal_question_count": 0,
        "formal_answer_count": 0,
        "formal_score_count": 0,
    }


def blank_question_family_templates() -> dict[str, Any]:
    """九个题族各留空白工位，不让设计说明冒充正式题面。"""

    rows = []
    for ordinal, family in enumerate(QUESTION_FAMILIES, 1):
        rows.append(
            {
                "family_id": f"DUSE-C11-FAMILY-{ordinal:02d}",
                "family_group": (
                    "RESEARCH" if family in RESEARCH_QUESTION_FAMILIES else "PRODUCT"
                ),
                "question_family": family,
                "question_text": HUMAN_REQUIRED,
                "executable_query_type": None,
                "case_kind": None,
                "expected_answer": None,
                "human_authored": False,
                "review_status": "HUMAN_REQUIRED",
                "formal_question": False,
                "formal_answer": False,
                "scoreable": False,
            }
        )
    return {
        "schema_version": "v02-duse-question-family-bank.blank.c11.2.v1",
        "status": "HUMAN_REQUIRED",
        "rows": rows,
        "formal_question_count": 0,
        "formal_answer_count": 0,
        "formal_score_count": 0,
    }


def missing_field_bucket_expansion() -> dict[str, Any]:
    return {
        "schema_version": "v02-duse-missing-field-buckets.c11.2.v1",
        "status": "HUMAN_REQUIRED",
        "legacy_bucket_total": LEGACY_MISSING_FIELD_BUCKET_TOTAL,
        "legacy_bucket_catalog_status": "LEGACY_NAMES_MISSING",
        "legacy_bucket_refs": [],
        "named_additions": list(NEW_MISSING_FIELD_BUCKETS),
        "resulting_bucket_total": RESULTING_MISSING_FIELD_BUCKET_TOTAL,
        "formal_diagnostic_freeze_allowed": False,
        "formal_diagnostic_row_count": 0,
        "formal_score_count": 0,
    }


def future_canary_contract() -> dict[str, Any]:
    return {
        "schema_version": "v02-duse-future-canary-contract.v1",
        "status": "MECHANICAL_FIXTURE_ONLY_NOT_FORMAL_QUESTION",
        "rule": (
            "查询 as_of_chapter=N 时，任何 chapter=N+1 的 fact_id 都不得"
            "进入 FOUND 返回；命中即计未来信息泄露。"
        ),
        "fixture_identifiers_only": {
            "query_case_kind": "FUTURE_CANARY_N_PLUS_1",
            "current_fact_id": "FACT-TEST-N",
            "future_canary_fact_id": "FACT-TEST-N-PLUS-1-CANARY",
        },
        "novel_text_included": False,
        "expected_semantic_answer_included": False,
    }


def _is_freeze_payload(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    if payload.get("frozen") is True or payload.get("question_set_frozen") is True:
        return True
    return str(payload.get("status", "")).upper() in {
        "FROZEN",
        "QUESTION_SET_FROZEN",
        "PROMPT_FROZEN",
    }


def find_existing_freezes(root: Path) -> list[dict[str, str]]:
    """只识别明确冻结票，不把设计合同误判成题面冻结。"""

    if not root.exists():
        return []
    found: list[dict[str, str]] = []
    for name in FREEZE_MARKER_NAMES:
        for path in sorted(root.rglob(name)):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if _is_freeze_payload(payload):
                found.append(
                    {
                        "path": display_path(path),
                        "sha256": sha256_file(path),
                    }
                )
    return found


def assert_question_set_not_frozen(root: Path) -> list[dict[str, str]]:
    found = find_existing_freezes(root)
    if found:
        paths = ", ".join(row["path"] for row in found)
        raise ExistingQuestionFreezeError(
            f"D-USE 题面已经冻结，禁止原位补 X10/X11：{paths}"
        )
    return found


def question_freeze_preflight(
    templates: Mapping[str, Any],
    *,
    existing_freezes: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    rows = templates.get("rows")
    if not isinstance(rows, list):
        raise DUseContractError("人工模板 rows 缺失")
    case_kinds = [row.get("case_kind") for row in rows]
    placeholders_only = all(
        row.get("question_text") == HUMAN_REQUIRED
        and row.get("expected_status") is None
        and row.get("expected_fact_ids") == []
        and row.get("expected_evidence_spans") == []
        and row.get("review_status") == "HUMAN_REQUIRED"
        and row.get("derived_from_model_output") is False
        for row in rows
        if isinstance(row, Mapping)
    )
    all_seven_present = (
        len(rows) == len(CASE_KINDS)
        and set(case_kinds) == set(CASE_KINDS)
        and len(case_kinds) == len(set(case_kinds))
    )
    frozen = bool(existing_freezes)
    ready = (
        all_seven_present
        and not frozen
        and all(
            row.get("review_status") == "HUMAN_VERIFIED"
            for row in rows
            if isinstance(row, Mapping)
        )
    )
    return {
        "schema_version": "v02-duse-question-freeze-preflight.v1",
        "status": ("READY_TO_FREEZE" if ready else "HARD_STOP_HUMAN_REQUIRED"),
        "existing_question_freeze_detected": frozen,
        "existing_freezes": list(existing_freezes),
        "seven_case_kinds_complete": all_seven_present,
        "blank_template_contains_no_fabricated_answers": placeholders_only,
        "d_use_a_b_scorecards_separate": True,
        "tri_state_contract_present": True,
        "four_x10_x11_metrics_separate": True,
        "future_n_plus_1_canary_present": True,
        "formal_question_count": 0,
        "formal_answer_count": 0,
        "question_set_frozen": False,
        "model_api_calls": 0,
        "novel_text_read_by_program": False,
        "model_output_read_for_question_writing": False,
        "next_action": (
            "本地人员只看章节原文，逐条填写题面、封闭查询对象和预期答案；"
            "完成复核前不得出 SHA 冻结，不得执行正式 D-USE 成绩。"
        ),
    }


def build_artifacts(
    *,
    existing_freezes: Sequence[Mapping[str, str]] = (),
) -> dict[str, bytes]:
    templates = blank_human_templates()
    preflight = question_freeze_preflight(
        templates,
        existing_freezes=existing_freezes,
    )
    human_block = {
        "schema_version": "v02-duse-human-required-block.v1",
        "status": "HUMAN_REQUIRED",
        "blocking": True,
        "formal_question_freeze_allowed": False,
        "formal_duse_execution_allowed": False,
        "formal_score_allowed": False,
        "required_missing_freeze_tickets": [
            QUESTION_FREEZE_FILENAME,
            ANSWER_FREEZE_FILENAME,
        ],
        "reason": (
            "七类工位只有空白模板；题面与预期答案必须由本地人员肉眼"
            "对照原文填写，模型与抽取产物均不得代写。"
        ),
    }
    readme = """# D-USE X10／X11 冻结前工程件

✅ 本件把 D-USE 拆成两张分开的成绩单：

- D-USE-A 直接输入封闭查询对象，只测数据层与查询器。
- D-USE-B 把人工写好的自然语言问句解析为同一查询对象，只测解析器。

七类题型已经各留一个空白人工工位，但没有生成任何正式问题或预期答案。
当前预检状态固定为 `HUMAN_REQUIRED`，所以题面不能冻结，也不能执行正式
D-USE 成绩。

三态返回固定为 `FOUND／NOT_FOUND／UNKNOWN`。没有查到时，只有材料范围
确认完整才可返回 `NOT_FOUND`；材料不足必须返回 `UNKNOWN`。

新增四项读数单独报：未来信息泄露率、空答案误报率、旧状态误返率、
`FOUND` 的 fact_id 与逐字证据完整率。它们不与原三项合成总分。

N+1 金丝雀只是机械测试身份，不含小说语义、正式题面或预期答案。

来源：Codex
"""
    values: dict[str, Any] = {
        "contracts/closed_query.v1.schema.json": closed_query_schema(),
        (
            "contracts/natural_language_query.v1.schema.json"
        ): natural_language_query_schema(),
        "contracts/query_result.v1.schema.json": query_result_schema(),
        (
            "contracts/human_answer_template.v1.schema.json"
        ): human_answer_template_schema(),
        (
            "contracts/question_freeze_ticket.v1.schema.json"
        ): question_freeze_ticket_schema(),
        (
            "contracts/human_answer_freeze_ticket.v1.schema.json"
        ): human_answer_freeze_ticket_schema(),
        "contracts/metric_contract.v1.json": metric_contract(),
        "templates/question_bank.blank.json": templates,
        "preflight/question_freeze_preflight.json": preflight,
        "preflight/human_required_block_receipt.json": human_block,
        "canary/future_n_plus_one_contract.json": future_canary_contract(),
        "attribution_receipt.json": {
            "schema_version": "v02-duse-attribution-receipt.v1",
            "ownership": "V02_NEW_AREA",
            "read_surfaces": [
                "Notion 施工令 C10.3／§9.1-E",
                "governance/CURRENT_STATE.json（只读校准）",
            ],
            "write_surfaces": [
                "tools/v02_duse_contract.py",
                "tools/v02_duse_query.py",
                "tests/test_v02_duse_contract.py",
                "tests/test_v02_duse_query.py",
                (
                    "experiments/extraction_redesign_v02_overnight_20260725/"
                    "V02_DUSE_X10_X11_20260725/"
                ),
            ],
            "legacy_written": False,
            "model_api_calls": 0,
            "network_requests": 0,
            "novel_body_read_count": 0,
            "formal_gold_read_count": 0,
            "formal_scores_emitted": False,
        },
    }
    artifacts = {path: canonical_json_bytes(value) for path, value in values.items()}
    artifacts["README.md"] = readme.encode("utf-8")
    return artifacts


def write_artifacts(output_dir: Path) -> dict[str, Any]:
    existing = assert_question_set_not_frozen(output_dir)
    artifacts = build_artifacts(existing_freezes=existing)
    for relative, raw in artifacts.items():
        path = output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    inventory = [
        {
            "path": relative,
            "sha256": sha256_bytes(raw),
            "bytes": len(raw),
        }
        for relative, raw in sorted(artifacts.items())
    ]
    manifest = {
        "schema_version": "v02-duse-x10-x11-manifest.v1",
        "status": "HUMAN_REQUIRED_NOT_FROZEN",
        "artifact_count_without_manifest": len(inventory),
        "inventory": inventory,
        "inventory_sha256": sha256_bytes(canonical_json_bytes(inventory)),
        "d_use_a_b_scorecards_separate": True,
        "seven_case_kinds_complete": True,
        "return_statuses": list(RETURN_STATUSES),
        "x10_x11_metrics": list(NEW_METRICS),
        "formal_question_count": 0,
        "formal_answer_count": 0,
        "formal_scores_emitted": False,
        "model_api_calls": 0,
        "active_pipeline_changed": False,
    }
    (output_dir / "artifact_manifest.json").write_bytes(canonical_json_bytes(manifest))
    return manifest


def verify_artifacts(output_dir: Path) -> dict[str, Any]:
    manifest_path = output_dir / "artifact_manifest.json"
    if not manifest_path.is_file():
        raise DUseContractError("artifact_manifest.json 不存在")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in manifest["inventory"]:
        path = output_dir / row["path"]
        if not path.is_file() or sha256_file(path) != row["sha256"]:
            raise DUseContractError(f"工件漂移：{row['path']}")
    preflight = json.loads(
        (output_dir / "preflight/question_freeze_preflight.json").read_text(
            encoding="utf-8"
        )
    )
    if preflight["status"] != "HARD_STOP_HUMAN_REQUIRED":
        raise DUseContractError("空白人工题库不得通过冻结前预检")
    return {
        "status": "PASS_HUMAN_REQUIRED_BLOCK_ACTIVE",
        "manifest_sha256": sha256_file(manifest_path),
        "artifact_count": len(manifest["inventory"]) + 1,
        "formal_question_freeze_allowed": False,
        "formal_duse_execution_allowed": False,
    }


def build_c11_question_expansion_artifacts() -> dict[str, bytes]:
    """C11.2 独立增量件；不重写 C10.3/D-USE 历史输出。"""

    catalog = question_family_catalog()
    templates = blank_question_family_templates()
    bucket_expansion = missing_field_bucket_expansion()
    preflight = {
        "schema_version": "v02-duse-question-expansion-preflight.c11.2.v1",
        "status": "HARD_STOP_HUMAN_REQUIRED",
        "question_family_dimension_added": True,
        "research_question_family_count": len(RESEARCH_QUESTION_FAMILIES),
        "product_question_family_count": len(PRODUCT_QUESTION_FAMILIES),
        "executable_query_type_count": len(QUERY_TYPES),
        "executable_query_types_unchanged": True,
        "case_kind_count": len(CASE_KINDS),
        "case_kinds_unchanged": True,
        "legacy_missing_field_bucket_total": (LEGACY_MISSING_FIELD_BUCKET_TOTAL),
        "legacy_bucket_catalog_status": "LEGACY_NAMES_MISSING",
        "invented_legacy_bucket_name_count": 0,
        "new_named_missing_field_bucket_count": len(NEW_MISSING_FIELD_BUCKETS),
        "resulting_missing_field_bucket_total": (RESULTING_MISSING_FIELD_BUCKET_TOTAL),
        "formal_question_count": 0,
        "formal_answer_count": 0,
        "formal_score_count": 0,
        "formal_question_freeze_allowed": False,
        "formal_diagnostic_freeze_allowed": False,
        "formal_duse_execution_allowed": False,
        "model_api_calls": 0,
        "network_requests": 0,
        "reason": (
            "九个 question_family 只是出题方向；题面、既有 query_type、"
            "case_kind 和答案均未由本地人员填写。旧七桶权威目录也未入仓。"
        ),
    }
    block = {
        "schema_version": "v02-duse-c11.2-human-required-block.v1",
        "status": "HUMAN_REQUIRED",
        "blocking": True,
        "formal_question_freeze_allowed": False,
        "formal_diagnostic_freeze_allowed": False,
        "formal_duse_execution_allowed": False,
        "formal_score_allowed": False,
        "missing_inputs": [
            "HUMAN_AUTHORED_QUESTION_TEXT",
            "HUMAN_SELECTED_EXECUTABLE_QUERY_TYPE",
            "HUMAN_SELECTED_CASE_KIND",
            "HUMAN_VERIFIED_EXPECTED_ANSWER",
            "VERIFIED_LEGACY_MISSING_FIELD_BUCKET_CATALOG",
        ],
    }
    readme = """# C11.2 D-USE 题族扩展候选

✅ 本件给冻结前题面新增九个独立方向：六个研究题族、三个产品题族。
它们只是“以后该问什么”的出题维度，不替换现有五种可执行查询，也不替换
七种案例类型。

九个工位仍全部是人工待填状态。正式题目、答案和分数都是 0；本件不能
假装执行 D-USE，也不能签发题库冻结票。

缺字段桶只做可证实的 7＋2＝9 扩容登记。仓内没有旧七桶的权威目录，
因此不编造七个语义名；只具名新增的“场景／视觉缺失”和“情绪／强度缺失”。
旧桶以后只能引用经核准的外部目录身份。

来源：Codex
"""
    authority_excerpt = {
        "schema_version": "v02-duse-c11.2-authority-excerpt.v1",
        "page_id": C11_WORK_ORDER_PAGE_ID,
        "page_url": C11_WORK_ORDER_PAGE_URL,
        "connector_readback_at": C11_AUTHORITY_READBACK_AT,
        "excerpt_scope": "C11.2",
        "excerpt_text": C11_2_AUTHORITY_EXCERPT,
        "notion_full_page_content_sha256": None,
        "notion_full_page_content_sha256_status": ("NOT_AVAILABLE_NOT_INVENTED"),
    }
    authority_excerpt_raw = canonical_json_bytes(authority_excerpt)
    values: dict[str, Any] = {
        (
            "contracts/question_family_candidate.v1.schema.json"
        ): question_family_candidate_schema(),
        (
            "contracts/missing_field_bucket_registry.v1.schema.json"
        ): missing_field_bucket_registry_schema(),
        (
            "contracts/missing_field_diagnostic_row.v1.schema.json"
        ): missing_field_diagnostic_row_schema(),
        "catalog/question_family_catalog.json": catalog,
        "catalog/missing_field_bucket_expansion.json": bucket_expansion,
        "templates/question_family.blank.json": templates,
        "preflight/question_expansion_preflight.json": preflight,
        "preflight/human_required_block_receipt.json": block,
        "authority_excerpt.json": authority_excerpt,
        "attribution_receipt.json": {
            "schema_version": "v02-duse-c11.2-attribution-receipt.v1",
            "ownership": "V02_NEW_AREA",
            "notion_work_order": {
                "page_id": C11_WORK_ORDER_PAGE_ID,
                "url": C11_WORK_ORDER_PAGE_URL,
                "content_sha256": None,
                "content_sha256_status": "NOT_AVAILABLE_NOT_INVENTED",
            },
            "authority_excerpt_path": "authority_excerpt.json",
            "authority_excerpt_sha256": sha256_bytes(authority_excerpt_raw),
            "read_surfaces": [
                "Notion 施工令 C11.2",
                (
                    "experiments/extraction_redesign_v02_overnight_20260725/"
                    "V02_DUSE_X10_X11_20260725/（只读）"
                ),
            ],
            "write_surfaces": [
                "tools/v02_duse_contract.py",
                "tools/v02_duse_query.py",
                "tests/test_v02_duse_contract.py",
                "tests/test_v02_duse_query.py",
                (
                    "experiments/extraction_redesign_v02_overnight_20260725/"
                    "V02_C11_product_north_star_20260725/"
                    "C11_2_duse_question_expansion/"
                ),
            ],
            "historical_duse_output_rewritten": False,
            "model_api_calls": 0,
            "network_requests": 0,
            "formal_question_count": 0,
            "formal_answer_count": 0,
            "formal_score_count": 0,
        },
    }
    artifacts = {path: canonical_json_bytes(value) for path, value in values.items()}
    artifacts["README.md"] = readme.encode("utf-8")
    if set(artifacts) != set(C11_QUESTION_EXPANSION_RELATIVE_PATHS):
        raise DUseContractError("C11.2 生成器固定工件清单漂移")
    schema_keys = set(missing_field_bucket_registry_schema()["properties"])
    if set(bucket_expansion) != schema_keys:
        raise DUseContractError("C11.2 缺字段桶实例与发布 schema 字段不一致")
    return artifacts


def write_c11_question_expansion_artifacts(
    output_dir: Path,
) -> dict[str, Any]:
    existing = assert_question_set_not_frozen(output_dir)
    if existing:
        raise ExistingQuestionFreezeError("C11.2 目录已有题面冻结")
    artifacts = build_c11_question_expansion_artifacts()
    for relative, raw in artifacts.items():
        path = output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    inventory = [
        {
            "path": relative,
            "sha256": sha256_bytes(raw),
            "bytes": len(raw),
        }
        for relative, raw in sorted(artifacts.items())
    ]
    manifest = {
        "schema_version": "v02-duse-c11.2-manifest.v1",
        "status": "HUMAN_REQUIRED_NOT_FROZEN",
        "artifact_count_without_manifest": len(inventory),
        "inventory": inventory,
        "inventory_sha256": sha256_bytes(canonical_json_bytes(inventory)),
        "question_family_count": len(QUESTION_FAMILIES),
        "research_question_family_count": len(RESEARCH_QUESTION_FAMILIES),
        "product_question_family_count": len(PRODUCT_QUESTION_FAMILIES),
        "executable_query_type_count": len(QUERY_TYPES),
        "case_kind_count": len(CASE_KINDS),
        "missing_field_bucket_arithmetic": {
            "legacy_total": LEGACY_MISSING_FIELD_BUCKET_TOTAL,
            "named_additions": len(NEW_MISSING_FIELD_BUCKETS),
            "resulting_total": RESULTING_MISSING_FIELD_BUCKET_TOTAL,
        },
        "formal_question_count": 0,
        "formal_answer_count": 0,
        "formal_score_count": 0,
        "model_api_calls": 0,
        "active_pipeline_changed": False,
    }
    (output_dir / "artifact_manifest.json").write_bytes(canonical_json_bytes(manifest))
    return manifest


def verify_c11_question_expansion_artifacts(
    output_dir: Path,
) -> dict[str, Any]:
    manifest_path = output_dir / "artifact_manifest.json"
    if not manifest_path.is_file():
        raise DUseContractError("C11.2 artifact_manifest.json 不存在")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inventory = manifest.get("inventory")
    if not isinstance(inventory, list):
        raise DUseContractError("C11.2 manifest inventory 必须是数组")
    if manifest.get("artifact_count_without_manifest") != len(inventory):
        raise DUseContractError("C11.2 manifest 工件数量漂移")
    if manifest.get("inventory_sha256") != sha256_bytes(
        canonical_json_bytes(inventory)
    ):
        raise DUseContractError("C11.2 manifest inventory 摘要漂移")
    inventory_paths = [row.get("path") for row in inventory]
    if len(inventory_paths) != len(set(inventory_paths)) or set(inventory_paths) != set(
        C11_QUESTION_EXPANSION_RELATIVE_PATHS
    ):
        raise DUseContractError("C11.2 manifest 不等于生成器固定工件清单")
    expected_paths = set(C11_QUESTION_EXPANSION_RELATIVE_PATHS)
    actual_paths = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file() and path != manifest_path
    }
    unexpected_paths = actual_paths - expected_paths
    missing_paths = expected_paths - actual_paths
    if unexpected_paths or missing_paths:
        raise DUseContractError(
            "C11.2 工件清单不闭合："
            f"unexpected={sorted(unexpected_paths)} "
            f"missing={sorted(missing_paths)}"
        )
    for row in inventory:
        path = output_dir / row["path"]
        if not path.is_file() or sha256_file(path) != row["sha256"]:
            raise DUseContractError(f"C11.2 工件漂移：{row['path']}")
    preflight = json.loads(
        (output_dir / "preflight/question_expansion_preflight.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        preflight["status"] != "HARD_STOP_HUMAN_REQUIRED"
        or preflight["formal_question_count"] != 0
        or preflight["formal_answer_count"] != 0
        or preflight["formal_score_count"] != 0
        or preflight["invented_legacy_bucket_name_count"] != 0
        or (
            preflight["legacy_missing_field_bucket_total"]
            + preflight["new_named_missing_field_bucket_count"]
        )
        != preflight["resulting_missing_field_bucket_total"]
    ):
        raise DUseContractError("C11.2 冻结前边界或 7+2=9 账漂移")
    catalog = json.loads(
        (output_dir / "catalog/question_family_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    if catalog["executable_query_types_unchanged"] != list(QUERY_TYPES) or catalog[
        "case_kinds_unchanged"
    ] != list(CASE_KINDS):
        raise DUseContractError("C11.2 不得替换 query_type 或 case_kind")
    bucket_expansion = json.loads(
        (output_dir / "catalog/missing_field_bucket_expansion.json").read_text(
            encoding="utf-8"
        )
    )
    if set(bucket_expansion) != set(
        missing_field_bucket_registry_schema()["properties"]
    ):
        raise DUseContractError("C11.2 缺字段桶实例与发布 schema 字段不一致")
    if (
        bucket_expansion["formal_diagnostic_row_count"] != 0
        or bucket_expansion["formal_score_count"] != 0
    ):
        raise DUseContractError("C11.2 正式诊断或分数字段必须保持为 0")
    return {
        "status": "PASS_HUMAN_REQUIRED_BLOCK_ACTIVE",
        "manifest_sha256": sha256_file(manifest_path),
        "artifact_count": len(inventory) + 1,
        "question_family_count": len(QUESTION_FAMILIES),
        "missing_field_bucket_total": RESULTING_MISSING_FIELD_BUCKET_TOTAL,
        "formal_question_freeze_allowed": False,
        "formal_duse_execution_allowed": False,
        "formal_scores_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--c11-question-expansion", action="store_true")
    args = parser.parse_args()
    if args.c11_question_expansion and args.output_dir == DEFAULT_OUTPUT_DIR:
        output_dir = DEFAULT_C11_OUTPUT_DIR.resolve()
    else:
        output_dir = args.output_dir.resolve()
    if args.c11_question_expansion:
        if not args.verify_only:
            write_c11_question_expansion_artifacts(output_dir)
        receipt = verify_c11_question_expansion_artifacts(output_dir)
    else:
        if not args.verify_only:
            write_artifacts(output_dir)
        receipt = verify_artifacts(output_dir)
    print(
        json.dumps(
            receipt,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
