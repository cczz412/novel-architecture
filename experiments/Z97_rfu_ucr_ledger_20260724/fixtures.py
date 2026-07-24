"""第97道冻结映射和八个回归反例。

这些数据只把已有金标、Z89 已完成判词和可复算附录转成机器合同，
不新增小说语义判断。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .core import sha256_bytes


QUALIFIER_OVERLAY: dict[str, list[dict[str, Any]]] = {
    "GOLD-C0003-01-N01": [
        {
            "qualifier_id": "G01-Q-SOURCE",
            "type": "source",
            "normalized_value": "来自克莱恩残留的记忆碎片",
            "why_required": "Z89冻结判词明确把信息来源列为不可省限定",
            "support_anchor_ids": ["ch0003:E0005"],
        }
    ],
    "GOLD-C0003-03-N01": [
        {
            "qualifier_id": "G03-Q-CONDITION",
            "type": "condition",
            "normalized_value": "眼见梅丽莎即将出来",
            "why_required": "Z89冻结判词明确记录此前提被漏",
            "support_anchor_ids": ["ch0003:E0077", "ch0003:E0078"],
        }
    ],
    "GOLD-C0003-11-N02": [
        {
            "qualifier_id": "G11-N02-Q-CONDITION",
            "type": "condition",
            "normalized_value": "掌握理论知识后",
            "why_required": "Z89冻结判词明确记录理论知识限定被漏",
            "support_anchor_ids": ["ch0003:E0097"],
        }
    ],
    "GOLD-C0003-11-N03": [
        {
            "qualifier_id": "G11-N03-Q-TIME",
            "type": "time",
            "normalized_value": "最近",
            "why_required": "可复算附录 CANARY-Q-01 与 Z89冻结判词共同钉住",
            "support_anchor_ids": ["ch0003:E0098"],
        }
    ],
    "GOLD-C0003-12-N01": [
        {
            "qualifier_id": "G12-N01-Q-PURPOSE",
            "type": "purpose",
            "normalized_value": "维持生活",
            "why_required": "Z89冻结判词明确记录该目的被漏",
            "support_anchor_ids": ["ch0003:E0060", "ch0003:E0061"],
        },
        {
            "qualifier_id": "G12-N01-Q-LOCATION",
            "type": "location",
            "normalized_value": "恶劣环境",
            "why_required": "Z89冻结判词明确记录出差环境限定被漏",
            "support_anchor_ids": ["ch0003:E0062"],
        },
    ],
    "GOLD-C0003-12-N03": [
        {
            "qualifier_id": "G12-N03-Q-CONDITION",
            "type": "condition",
            "normalized_value": "平民出身和普通文法学校背景",
            "why_required": "Z89冻结判词明确记录普通文法学校背景被漏",
            "support_anchor_ids": ["ch0003:E0064", "ch0003:E0065"],
        }
    ],
    "GOLD-C0003-13-N01": [
        {
            "qualifier_id": "G13-N01-Q-SCOPE",
            "type": "scope",
            "normalized_value": "劣等茶水",
            "why_required": "Z89冻结判词明确记录茶水性质被压平",
            "support_anchor_ids": [
                "ch0003:E0136",
                "ch0003:E0137",
                "ch0003:E0138",
            ],
        },
        {
            "qualifier_id": "G13-N01-Q-QUANTITY",
            "type": "quantity",
            "normalized_value": "两条黑麦面包",
            "why_required": "Z89冻结判词明确记录数量被漏",
            "support_anchor_ids": ["ch0003:E0138", "ch0003:E0139"],
        },
    ],
    "GOLD-C0003-14-N01": [
        {
            "qualifier_id": "G14-Q-FREQUENCY",
            "type": "frequency",
            "normalized_value": "平时都会提前出门",
            "why_required": "可复算附录 CANARY-Q-02 与 Z89冻结判词共同钉住",
            "support_anchor_ids": ["ch0003:E0158", "ch0003:E0159"],
        },
        {
            "qualifier_id": "G14-Q-PURPOSE",
            "type": "purpose",
            "normalized_value": "为了省车费",
            "why_required": "正式金标主张明示目的",
            "support_anchor_ids": ["ch0003:E0157", "ch0003:E0158"],
        },
        {
            "qualifier_id": "G14-Q-QUANTITY",
            "type": "quantity",
            "normalized_value": "步行约五十分钟",
            "why_required": "正式金标主张明示时长",
            "support_anchor_ids": ["ch0003:E0155", "ch0003:E0156"],
        },
        {
            "qualifier_id": "G14-Q-LOCATION",
            "type": "location",
            "normalized_value": "廷根技术学校",
            "why_required": "正式金标主张明示目的地",
            "support_anchor_ids": ["ch0003:E0155", "ch0003:E0156"],
        },
    ],
}


Z89_REASON_CODES: dict[str, list[str]] = {
    "GOLD-C0003-01-N01": ["ANCHOR_PARTIAL"],
    "GOLD-C0003-02-N01": ["PREDICATE_SCOPE_NARROWED"],
    "GOLD-C0003-03-N01": ["MISSING_QUALIFIER_CONDITION"],
    "GOLD-C0003-04-N01": ["ANCHOR_PARTIAL"],
    "GOLD-C0003-05-N01": [],
    "GOLD-C0003-06-N01": [],
    "GOLD-C0003-07-N01": ["PREDICATE_SCOPE_NARROWED"],
    "GOLD-C0003-08-N01": ["ANCHOR_PARTIAL"],
    "GOLD-C0003-09-N01": [],
    "GOLD-C0003-09-N02": [],
    "GOLD-C0003-09-N03": [],
    "GOLD-C0003-09-N04": [],
    "GOLD-C0003-09-N05": [],
    "GOLD-C0003-10-N01": ["PREDICATE_SCOPE_NARROWED"],
    "GOLD-C0003-10-N02": [],
    "GOLD-C0003-11-N01": [],
    "GOLD-C0003-11-N02": [
        "MISSING_QUALIFIER_CONDITION",
        "MULTI_FACT_MERGE",
    ],
    "GOLD-C0003-11-N03": [
        "MISSING_QUALIFIER_TIME",
        "MULTI_FACT_MERGE",
    ],
    "GOLD-C0003-12-N01": [
        "MISSING_QUALIFIER_PURPOSE",
        "MISSING_QUALIFIER_LOCATION",
    ],
    "GOLD-C0003-12-N02": [],
    "GOLD-C0003-12-N03": ["MISSING_QUALIFIER_CONDITION"],
    "GOLD-C0003-13-N01": [
        "PREDICATE_SCOPE_NARROWED",
        "MISSING_QUALIFIER_QUANTITY",
    ],
    "GOLD-C0003-14-N01": ["MISSING_QUALIFIER_FREQUENCY"],
}


Z89_QUALIFIER_STATUS: dict[str, dict[str, str]] = {
    "GOLD-C0003-01-N01": {
        "G01-Q-SOURCE": "present",
    },
    "GOLD-C0003-03-N01": {
        "G03-Q-CONDITION": "missing",
    },
    "GOLD-C0003-11-N02": {
        "G11-N02-Q-CONDITION": "missing",
    },
    "GOLD-C0003-11-N03": {
        "G11-N03-Q-TIME": "missing",
    },
    "GOLD-C0003-12-N01": {
        "G12-N01-Q-PURPOSE": "missing",
        "G12-N01-Q-LOCATION": "missing",
    },
    "GOLD-C0003-12-N03": {
        "G12-N03-Q-CONDITION": "missing",
    },
    "GOLD-C0003-13-N01": {
        "G13-N01-Q-SCOPE": "missing",
        "G13-N01-Q-QUANTITY": "missing",
    },
    "GOLD-C0003-14-N01": {
        "G14-Q-FREQUENCY": "missing",
        "G14-Q-PURPOSE": "present",
        "G14-Q-QUANTITY": "present",
        "G14-Q-LOCATION": "present",
    },
}


def _synthetic_sha(label: str) -> str:
    return sha256_bytes(label.encode("utf-8"))


def _eligibility() -> dict[str, Any]:
    return {
        "schema_version": "judge-eligibility-v1",
        "candidate_provider": "synthetic",
        "candidate_family": "synthetic-candidate",
        "candidate_checkpoint": "synthetic-candidate-v1",
        "candidate_training_lineage": "none",
        "judge_kind": "frozen_regression_fixture",
        "judge_provider": "local",
        "judge_family": "human-authored-canary",
        "judge_checkpoint": "canary-v1",
        "judge_training_lineage": "none",
        "same_family": False,
        "same_checkpoint": False,
        "judge_trained_on_scored_outputs": False,
        "candidate_identity_visible": False,
        "historical_scores_visible": False,
        "repair_logs_visible": False,
        "eligible": True,
        "main_judge": "frozen_canary_contract",
        "reasons": ["八案只用于回归，不代表小说质量真值"],
    }


def _rfu(
    case_id: str,
    *,
    qualifier: tuple[str, str, str] | None = None,
    actuality: str = "occurred",
) -> dict[str, Any]:
    qualifiers: list[dict[str, Any]] = []
    if qualifier is not None:
        qualifier_id, qualifier_type, normalized_value = qualifier
        qualifiers.append(
            {
                "qualifier_id": qualifier_id,
                "type": qualifier_type,
                "normalized_value": normalized_value,
                "why_required": f"{case_id} 预写反例",
                "support_anchor_ids": ["ch0003:E0001"],
            }
        )
    return {
        "schema_version": "rfu-v1",
        "reference_version": "canary-v1",
        "chapter_id": "ch0003",
        "rfu_id": f"{case_id}-RFU",
        "source_order": 1,
        "fact_head": {
            "subject_entity_ids": ["ENTITY-A"],
            "predicate": f"{case_id} reference fact",
            "object_entity_ids": ["ENTITY-B"],
            "result": "",
            "polarity": "positive",
            "actuality": actuality,
        },
        "required_qualifiers": qualifiers,
        "optional_details": [],
        "minimal_support_sets": [
            {
                "support_set_id": f"{case_id}-SUPPORT-01",
                "anchor_ids": ["ch0003:E0001"],
                "minimality": "adjudicated",
            }
        ],
        "pathology_tags": [case_id],
        "criticality": "normal",
        "weight": 1,
        "provenance": {
            "origin": "dual_judge_consensus",
            "annotators": ["canary-author", "canary-reviewer"],
            "adjudicator": "canary-contract",
            "source_sha256": _synthetic_sha(f"{case_id}:source"),
            "anchor_catalog_sha256": _synthetic_sha(f"{case_id}:catalog"),
        },
    }


def _claim(case_id: str, text: str) -> dict[str, Any]:
    return {
        "schema_version": "candidate-claim-v1",
        "chapter_id": "ch0003",
        "event_id": f"{case_id}-EVENT",
        "claim_id": f"{case_id}-CLAIM",
        "clause_index": 0,
        "event_text": text,
        "fact_head": {
            "subject_entity_ids": ["ENTITY-A"],
            "predicate": text,
            "object_entity_ids": ["ENTITY-B"],
            "result": "",
            "polarity": "positive",
            "actuality": "occurred",
        },
        "qualifiers": [],
        "claim_components": [
            {
                "component_id": f"{case_id}-COMP-01",
                "text": text,
                "anchor_ids": ["ch0003:E0001"],
            }
        ],
        "listed_anchor_ids": ["ch0003:E0001"],
        "is_addressable": True,
        "atomic_clause_count": 1,
        "parse_origin": "frozen_canary",
        "candidate_output_sha256": _synthetic_sha(f"{case_id}:candidate"),
    }


def _verdict(
    case_id: str,
    *,
    head_match: str = "yes",
    reason_codes: list[str],
    qualifier_status: str | None = None,
    anchor_status: str = "supported",
    atomicity: str = "atomic",
) -> dict[str, Any]:
    qualifier_results = []
    if qualifier_status is not None:
        qualifier_results.append(
            {
                "qualifier_id": f"{case_id}-QUALIFIER",
                "status": qualifier_status,
            }
        )
    return {
        "schema_version": "match-verdict-v1",
        "rfu_id": f"{case_id}-RFU",
        "claim_id": f"{case_id}-CLAIM",
        "head_match": head_match,
        "reason_codes": reason_codes,
        "qualifier_results": qualifier_results,
        "anchor_component_results": [
            {
                "component_id": f"{case_id}-COMP-01",
                "status": anchor_status,
            }
        ],
        "atomicity": atomicity,
        "confidence": 1.0,
        "judge_id": "canary-contract",
        "judge_config_sha256": _synthetic_sha("canary-judge-v1"),
        "candidate_arm": "synthetic-canary",
        "human_review_required": False,
        "frozen_reason": f"{case_id} 预写反例",
        "adjudication_source_sha256": _synthetic_sha(f"{case_id}:adjudication"),
    }


def build_canary_suite() -> dict[str, Any]:
    """返回八个可独立复算的冻结反例。"""

    cases: list[dict[str, Any]] = []

    def add(
        case_id: str,
        rfu: dict[str, Any],
        claim: dict[str, Any],
        verdict: dict[str, Any],
        metrics: dict[str, float],
        reason_codes: list[str],
    ) -> None:
        cases.append(
            {
                "case_id": case_id,
                "rfus": [rfu],
                "claims": [claim],
                "verdicts": [verdict],
                "judge_eligibility": _eligibility(),
                "expected": {
                    "metrics": metrics,
                    "reason_codes": reason_codes,
                },
            }
        )

    add(
        "CANARY-Q-01",
        _rfu(
            "CANARY-Q-01",
            qualifier=("CANARY-Q-01-QUALIFIER", "time", "最近"),
        ),
        _claim("CANARY-Q-01", "梅丽莎宣称修好了怀表。"),
        _verdict(
            "CANARY-Q-01",
            reason_codes=["MISSING_QUALIFIER_TIME"],
            qualifier_status="missing",
        ),
        {"FCR": 1.0, "QCR_full": 0.0, "UCR": 0.0},
        ["MISSING_QUALIFIER_TIME"],
    )
    add(
        "CANARY-Q-02",
        _rfu(
            "CANARY-Q-02",
            qualifier=("CANARY-Q-02-QUALIFIER", "frequency", "平时都会"),
        ),
        _claim("CANARY-Q-02", "梅丽莎步行去学校。"),
        _verdict(
            "CANARY-Q-02",
            reason_codes=["MISSING_QUALIFIER_FREQUENCY"],
            qualifier_status="missing",
        ),
        {"FCR": 1.0, "QCR_full": 0.0, "UCR": 0.0},
        ["MISSING_QUALIFIER_FREQUENCY"],
    )
    add(
        "CANARY-Q-03",
        _rfu("CANARY-Q-03", actuality="unresolved"),
        _claim("CANARY-Q-03", "已经确认是他杀。"),
        _verdict(
            "CANARY-Q-03",
            head_match="contradiction",
            reason_codes=["ACTUALITY_STRENGTHENED"],
        ),
        {"FCR": 0.0, "UCR": 0.0, "SOP": 0.0},
        ["ACTUALITY_STRENGTHENED"],
    )
    add(
        "CANARY-A-01",
        _rfu("CANARY-A-01"),
        _claim("CANARY-A-01", "完整主张只挂半句锚。"),
        _verdict(
            "CANARY-A-01",
            reason_codes=["ANCHOR_PARTIAL"],
            anchor_status="partial",
        ),
        {"FCR": 1.0, "ASR_full": 0.0, "UCR": 0.0, "SOP": 0.0},
        ["ANCHOR_PARTIAL"],
    )
    add(
        "CANARY-A-02",
        _rfu("CANARY-A-02"),
        _claim("CANARY-A-02", "长设定句只挂首尾锚。"),
        _verdict(
            "CANARY-A-02",
            reason_codes=["ANCHOR_PARTIAL", "ENDPOINT_SPAN_PATTERN"],
            anchor_status="partial",
        ),
        {"FCR": 1.0, "ASR_full": 0.0, "UCR": 0.0, "SOP": 0.0},
        ["ANCHOR_PARTIAL", "ENDPOINT_SPAN_PATTERN"],
    )
    add(
        "CANARY-M-01",
        _rfu("CANARY-M-01"),
        _claim("CANARY-M-01", "把两个时期的怀表事实压成一条。"),
        _verdict(
            "CANARY-M-01",
            reason_codes=["MULTI_FACT_MERGE"],
            atomicity="merged_unaddressable",
        ),
        {"FCR": 1.0, "ASR_full": 1.0, "UCR": 0.0, "SOP": 1.0},
        ["MULTI_FACT_MERGE"],
    )
    add(
        "CANARY-F-01",
        _rfu("CANARY-F-01", actuality="hypothetical"),
        _claim("CANARY-F-01", "子弹穿过确定导致记忆破碎。"),
        _verdict(
            "CANARY-F-01",
            head_match="contradiction",
            reason_codes=["ACTUALITY_STRENGTHENED"],
        ),
        {"FCR": 0.0, "UCR": 0.0, "SOP": 0.0},
        ["ACTUALITY_STRENGTHENED"],
    )
    add(
        "CANARY-F-02",
        _rfu("CANARY-F-02", actuality="reported"),
        _claim("CANARY-F-02", "候选把别人转述的邀请写成本人承诺。"),
        _verdict(
            "CANARY-F-02",
            head_match="contradiction",
            reason_codes=["ATTRIBUTION_CHANGED"],
        ),
        {"FCR": 0.0, "UCR": 0.0, "SOP": 0.0},
        ["ATTRIBUTION_CHANGED"],
    )
    return {
        "schema_version": "rfu-canary-suite-v1",
        "cases": deepcopy(cases),
    }
