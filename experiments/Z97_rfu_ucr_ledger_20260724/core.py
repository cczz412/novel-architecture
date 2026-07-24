"""RFU、候选主张、冻结判词与 UCR 五层的纯内存合同。

本模块不读写文件、不访问网络、不调用模型。语义判断只能由外部冻结
``MatchVerdict`` 注入；本模块只做合同校验、确定性匹配和机械计分。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any


class Z97ContractError(ValueError):
    """第97道候选合同不成立。"""


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_NAMESPACED_ANCHOR_RE = re.compile(r"^ch\d{4}:E\d{4}$")
_QUALIFIER_TYPES = frozenset(
    {
        "time",
        "frequency",
        "condition",
        "source",
        "attribution",
        "modality",
        "purpose",
        "quantity",
        "location",
        "scope",
    }
)
_ACTUALITY_VALUES = frozenset(
    {
        "occurred",
        "reported",
        "believed",
        "planned",
        "hypothetical",
        "unresolved",
    }
)
_HEAD_MATCH_VALUES = frozenset({"yes", "partial", "no", "contradiction"})
_QUALIFIER_RESULT_VALUES = frozenset(
    {"present", "missing", "contradicted", "unclear"}
)
_ANCHOR_RESULT_VALUES = frozenset(
    {"supported", "partial", "unsupported", "wrong_anchor"}
)
_ATOMICITY_VALUES = frozenset(
    {"atomic", "mechanically_splittable", "merged_unaddressable"}
)
_REASON_CODES = frozenset(
    {
        "SUBJECT_SCOPE_NARROWED",
        "SUBJECT_SCOPE_EXPANDED",
        "PREDICATE_SCOPE_NARROWED",
        "PREDICATE_SCOPE_EXPANDED",
        "OBJECT_SCOPE_NARROWED",
        "OBJECT_SCOPE_EXPANDED",
        "POLARITY_CHANGED",
        "ACTUALITY_STRENGTHENED",
        "ATTRIBUTION_CHANGED",
        "MISSING_QUALIFIER_TIME",
        "MISSING_QUALIFIER_FREQUENCY",
        "MISSING_QUALIFIER_CONDITION",
        "MISSING_QUALIFIER_SOURCE",
        "MISSING_QUALIFIER_ATTRIBUTION",
        "MISSING_QUALIFIER_MODALITY",
        "MISSING_QUALIFIER_PURPOSE",
        "MISSING_QUALIFIER_QUANTITY",
        "MISSING_QUALIFIER_LOCATION",
        "MISSING_QUALIFIER_SCOPE",
        "ANCHOR_PARTIAL",
        "ANCHOR_WRONG",
        "ENDPOINT_SPAN_PATTERN",
        "MULTI_FACT_MERGE",
        "EXTRA_UNSUPPORTED_CLAIM",
    }
)
MATCH_VERDICT_FIELDS = frozenset(
    {
        "schema_version",
        "rfu_id",
        "claim_id",
        "head_match",
        "reason_codes",
        "qualifier_results",
        "anchor_component_results",
        "atomicity",
        "confidence",
        "judge_id",
        "judge_config_sha256",
        "candidate_arm",
        "human_review_required",
        "frozen_reason",
        "adjudication_source_sha256",
    }
)
JUDGE_ELIGIBILITY_FIELDS = frozenset(
    {
        "schema_version",
        "candidate_provider",
        "candidate_family",
        "candidate_checkpoint",
        "candidate_training_lineage",
        "judge_kind",
        "judge_provider",
        "judge_family",
        "judge_checkpoint",
        "judge_training_lineage",
        "same_family",
        "same_checkpoint",
        "judge_trained_on_scored_outputs",
        "candidate_identity_visible",
        "historical_scores_visible",
        "repair_logs_visible",
        "eligible",
        "main_judge",
        "reasons",
    }
)


def stable_json_bytes(value: Any) -> bytes:
    """把 JSON 兼容值编码为可复验的 UTF-8 字节。"""

    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    """返回字节内容的小写 SHA-256。"""

    if not isinstance(data, bytes):
        raise Z97ContractError("sha256_bytes 只接受 bytes")
    return hashlib.sha256(data).hexdigest()


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Z97ContractError(f"{label} 必须是对象")
    return value


def _require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise Z97ContractError(f"{label} 必须是非空字符串")
    return value


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise Z97ContractError(f"{label} 必须是非空字符串组成的数组")
    return list(value)


def _require_sha256(value: Any, label: str) -> str:
    text = _require_nonempty_string(value, label)
    if not _SHA256_RE.fullmatch(text):
        raise Z97ContractError(f"{label} 不是小写 SHA-256")
    return text


def _reject_extra_fields(
    row: Mapping[str, Any],
    allowed: set[str] | frozenset[str],
    label: str,
) -> None:
    extra = set(row) - set(allowed)
    if extra:
        raise Z97ContractError(f"{label} 含 schema 未声明字段：{sorted(extra)}")


def _require_namespaced_anchors(value: Any, label: str) -> list[str]:
    anchors = _require_string_list(value, label)
    if any(not _NAMESPACED_ANCHOR_RE.fullmatch(anchor) for anchor in anchors):
        raise Z97ContractError(f"{label} 必须使用 chNNNN:ENNNN 身份")
    if len(anchors) != len(set(anchors)):
        raise Z97ContractError(f"{label} 含重复锚")
    return anchors


def _validate_fact_head(value: Any, label: str) -> None:
    row = _require_mapping(value, label)
    allowed = {
        "subject_entity_ids",
        "predicate",
        "object_entity_ids",
        "result",
        "polarity",
        "actuality",
    }
    for key in allowed:
        if key not in row:
            raise Z97ContractError(f"{label} 缺字段 {key}")
    _reject_extra_fields(row, allowed, label)
    _require_string_list(row["subject_entity_ids"], f"{label}.subject_entity_ids")
    _require_nonempty_string(row["predicate"], f"{label}.predicate")
    _require_string_list(row["object_entity_ids"], f"{label}.object_entity_ids")
    if not isinstance(row["result"], str):
        raise Z97ContractError(f"{label}.result 必须是字符串")
    if row["polarity"] not in {"positive", "negative"}:
        raise Z97ContractError(f"{label}.polarity 非法")
    if row["actuality"] not in _ACTUALITY_VALUES:
        raise Z97ContractError(f"{label}.actuality 非法")


def _validate_qualifier_definition(value: Any, label: str) -> None:
    row = _require_mapping(value, label)
    _reject_extra_fields(
        row,
        {
            "qualifier_id",
            "type",
            "normalized_value",
            "why_required",
            "support_anchor_ids",
        },
        label,
    )
    qualifier_id = _require_nonempty_string(row.get("qualifier_id"), f"{label}.id")
    if row.get("type") not in _QUALIFIER_TYPES:
        raise Z97ContractError(f"{label} {qualifier_id} 的 type 非法")
    _require_nonempty_string(
        row.get("normalized_value"),
        f"{label} {qualifier_id}.normalized_value",
    )
    _require_nonempty_string(
        row.get("why_required"),
        f"{label} {qualifier_id}.why_required",
    )
    _require_namespaced_anchors(
        row.get("support_anchor_ids"),
        f"{label} {qualifier_id}.support_anchor_ids",
    )


def validate_rfu(value: Any) -> dict[str, Any]:
    """校验并复制一个参考事实单元。"""

    row = _require_mapping(value, "RFU")
    required = (
        "schema_version",
        "reference_version",
        "chapter_id",
        "rfu_id",
        "source_order",
        "fact_head",
        "required_qualifiers",
        "optional_details",
        "minimal_support_sets",
        "pathology_tags",
        "criticality",
        "weight",
        "provenance",
    )
    for key in required:
        if key not in row:
            raise Z97ContractError(f"RFU 缺字段 {key}")
    if row["schema_version"] != "rfu-v1":
        raise Z97ContractError("RFU schema_version 必须是 rfu-v1")
    for key in ("reference_version", "chapter_id", "rfu_id"):
        _require_nonempty_string(row[key], f"RFU.{key}")
    if (
        not isinstance(row["source_order"], int)
        or isinstance(row["source_order"], bool)
        or row["source_order"] < 1
    ):
        raise Z97ContractError("RFU.source_order 必须是正整数")
    _validate_fact_head(row["fact_head"], "RFU.fact_head")

    qualifiers = row["required_qualifiers"]
    if not isinstance(qualifiers, list):
        raise Z97ContractError("RFU.required_qualifiers 必须是数组")
    qualifier_ids: list[str] = []
    for index, qualifier in enumerate(qualifiers):
        _validate_qualifier_definition(
            qualifier,
            f"RFU.required_qualifiers[{index}]",
        )
        qualifier_ids.append(str(qualifier["qualifier_id"]))
    if len(qualifier_ids) != len(set(qualifier_ids)):
        raise Z97ContractError("RFU.required_qualifiers 的 qualifier_id 重复")

    if not isinstance(row["optional_details"], list):
        raise Z97ContractError("RFU.optional_details 必须是数组")
    support_sets = row["minimal_support_sets"]
    if not isinstance(support_sets, list):
        raise Z97ContractError("RFU.minimal_support_sets 必须是数组")
    support_set_ids: list[str] = []
    for index, support_set in enumerate(support_sets):
        support = _require_mapping(
            support_set,
            f"RFU.minimal_support_sets[{index}]",
        )
        support_set_ids.append(
            _require_nonempty_string(
                support.get("support_set_id"),
                f"RFU.minimal_support_sets[{index}].support_set_id",
            )
        )
        _require_namespaced_anchors(
            support.get("anchor_ids"),
            f"RFU.minimal_support_sets[{index}].anchor_ids",
        )
        if support.get("minimality") not in {"adjudicated", "not_adjudicated"}:
            raise Z97ContractError("RFU support_set minimality 非法")
    if len(support_set_ids) != len(set(support_set_ids)):
        raise Z97ContractError("RFU minimal_support_sets 身份重复")

    _require_string_list(row["pathology_tags"], "RFU.pathology_tags")
    if row["criticality"] not in {"normal", "critical"}:
        raise Z97ContractError("RFU.criticality 非法")
    weight = row["weight"]
    if (
        isinstance(weight, bool)
        or not isinstance(weight, (int, float))
        or not math.isfinite(float(weight))
        or float(weight) <= 0
    ):
        raise Z97ContractError("RFU.weight 必须是正有限数")

    provenance = _require_mapping(row["provenance"], "RFU.provenance")
    if provenance.get("origin") not in {
        "human_gold",
        "dual_judge_consensus",
        "single_judge_provisional",
    }:
        raise Z97ContractError("RFU.provenance.origin 非法")
    _require_string_list(provenance.get("annotators"), "RFU.provenance.annotators")
    _require_nonempty_string(
        provenance.get("adjudicator"),
        "RFU.provenance.adjudicator",
    )
    _require_sha256(provenance.get("source_sha256"), "RFU.provenance.source_sha256")
    _require_sha256(
        provenance.get("anchor_catalog_sha256"),
        "RFU.provenance.anchor_catalog_sha256",
    )
    return deepcopy(dict(row))


def _validate_candidate_qualifier(value: Any, label: str) -> None:
    row = _require_mapping(value, label)
    _require_nonempty_string(row.get("qualifier_id"), f"{label}.qualifier_id")
    if row.get("type") not in _QUALIFIER_TYPES:
        raise Z97ContractError(f"{label}.type 非法")
    _require_nonempty_string(
        row.get("normalized_value"),
        f"{label}.normalized_value",
    )


def validate_candidate_claim(value: Any) -> dict[str, Any]:
    """校验并复制一个候选主张。"""

    row = _require_mapping(value, "CandidateClaim")
    required = (
        "schema_version",
        "chapter_id",
        "event_id",
        "claim_id",
        "clause_index",
        "event_text",
        "fact_head",
        "qualifiers",
        "claim_components",
        "listed_anchor_ids",
        "is_addressable",
        "atomic_clause_count",
        "parse_origin",
        "candidate_output_sha256",
    )
    for key in required:
        if key not in row:
            raise Z97ContractError(f"CandidateClaim 缺字段 {key}")
    if row["schema_version"] != "candidate-claim-v1":
        raise Z97ContractError(
            "CandidateClaim schema_version 必须是 candidate-claim-v1"
        )
    for key in ("chapter_id", "event_id", "claim_id", "event_text", "parse_origin"):
        _require_nonempty_string(row[key], f"CandidateClaim.{key}")
    if (
        not isinstance(row["clause_index"], int)
        or isinstance(row["clause_index"], bool)
        or row["clause_index"] < 0
    ):
        raise Z97ContractError("CandidateClaim.clause_index 必须是非负整数")
    if (
        not isinstance(row["atomic_clause_count"], int)
        or isinstance(row["atomic_clause_count"], bool)
        or row["atomic_clause_count"] < 1
    ):
        raise Z97ContractError("CandidateClaim.atomic_clause_count 必须是正整数")
    if not isinstance(row["is_addressable"], bool):
        raise Z97ContractError("CandidateClaim.is_addressable 必须是布尔值")
    _validate_fact_head(row["fact_head"], "CandidateClaim.fact_head")
    qualifiers = row["qualifiers"]
    if not isinstance(qualifiers, list):
        raise Z97ContractError("CandidateClaim.qualifiers 必须是数组")
    for index, qualifier in enumerate(qualifiers):
        _validate_candidate_qualifier(
            qualifier,
            f"CandidateClaim.qualifiers[{index}]",
        )
    components = row["claim_components"]
    if not isinstance(components, list) or not components:
        raise Z97ContractError("CandidateClaim.claim_components 必须是非空数组")
    component_ids: list[str] = []
    for index, component in enumerate(components):
        component_row = _require_mapping(
            component,
            f"CandidateClaim.claim_components[{index}]",
        )
        component_ids.append(
            _require_nonempty_string(
                component_row.get("component_id"),
                f"CandidateClaim.claim_components[{index}].component_id",
            )
        )
        _reject_extra_fields(
            component_row,
            {"component_id", "text", "anchor_ids"},
            f"CandidateClaim.claim_components[{index}]",
        )
        _require_nonempty_string(
            component_row.get("text"),
            f"CandidateClaim.claim_components[{index}].text",
        )
        _require_namespaced_anchors(
            component_row.get("anchor_ids"),
            f"CandidateClaim.claim_components[{index}].anchor_ids",
        )
    if len(component_ids) != len(set(component_ids)):
        raise Z97ContractError("CandidateClaim component_id 重复")
    _require_namespaced_anchors(
        row["listed_anchor_ids"],
        "CandidateClaim.listed_anchor_ids",
    )
    _require_sha256(
        row["candidate_output_sha256"],
        "CandidateClaim.candidate_output_sha256",
    )
    if "source_event_ids" in row:
        _require_string_list(
            row["source_event_ids"],
            "CandidateClaim.source_event_ids",
        )
    return deepcopy(dict(row))


def validate_match_verdict(value: Any) -> dict[str, Any]:
    """校验并复制一个冻结语义判词。"""

    row = _require_mapping(value, "MatchVerdict")
    for key in MATCH_VERDICT_FIELDS:
        if key not in row:
            raise Z97ContractError(f"MatchVerdict 缺字段 {key}")
    extra_fields = set(row) - MATCH_VERDICT_FIELDS
    if extra_fields:
        raise Z97ContractError(
            f"MatchVerdict 含 schema 未声明字段：{sorted(extra_fields)}"
        )
    if row["schema_version"] != "match-verdict-v1":
        raise Z97ContractError(
            "MatchVerdict schema_version 必须是 match-verdict-v1"
        )
    for key in ("rfu_id", "claim_id", "judge_id", "candidate_arm", "frozen_reason"):
        _require_nonempty_string(row[key], f"MatchVerdict.{key}")
    if row["head_match"] not in _HEAD_MATCH_VALUES:
        raise Z97ContractError("MatchVerdict.head_match 非法")
    reason_codes = _require_string_list(
        row["reason_codes"],
        "MatchVerdict.reason_codes",
    )
    if any(code not in _REASON_CODES for code in reason_codes):
        raise Z97ContractError("MatchVerdict.reason_codes 含未知代码")
    if len(reason_codes) != len(set(reason_codes)):
        raise Z97ContractError("MatchVerdict.reason_codes 重复")

    qualifier_results = row["qualifier_results"]
    if not isinstance(qualifier_results, list):
        raise Z97ContractError("MatchVerdict.qualifier_results 必须是数组")
    qualifier_ids: list[str] = []
    for index, result in enumerate(qualifier_results):
        result_row = _require_mapping(
            result,
            f"MatchVerdict.qualifier_results[{index}]",
        )
        qualifier_ids.append(
            _require_nonempty_string(
                result_row.get("qualifier_id"),
                f"MatchVerdict.qualifier_results[{index}].qualifier_id",
            )
        )
        _reject_extra_fields(
            result_row,
            {"qualifier_id", "status"},
            f"MatchVerdict.qualifier_results[{index}]",
        )
        if result_row.get("status") not in _QUALIFIER_RESULT_VALUES:
            raise Z97ContractError("MatchVerdict qualifier status 非法")
    if len(qualifier_ids) != len(set(qualifier_ids)):
        raise Z97ContractError("MatchVerdict qualifier_id 重复")

    anchor_results = row["anchor_component_results"]
    if not isinstance(anchor_results, list) or not anchor_results:
        raise Z97ContractError(
            "MatchVerdict.anchor_component_results 必须是非空数组"
        )
    component_ids: list[str] = []
    for index, result in enumerate(anchor_results):
        result_row = _require_mapping(
            result,
            f"MatchVerdict.anchor_component_results[{index}]",
        )
        component_ids.append(
            _require_nonempty_string(
                result_row.get("component_id"),
                f"MatchVerdict.anchor_component_results[{index}].component_id",
            )
        )
        _reject_extra_fields(
            result_row,
            {"component_id", "status"},
            f"MatchVerdict.anchor_component_results[{index}]",
        )
        if result_row.get("status") not in _ANCHOR_RESULT_VALUES:
            raise Z97ContractError("MatchVerdict anchor status 非法")
    if len(component_ids) != len(set(component_ids)):
        raise Z97ContractError("MatchVerdict component_id 重复")
    if row["atomicity"] not in _ATOMICITY_VALUES:
        raise Z97ContractError("MatchVerdict.atomicity 非法")
    confidence = row["confidence"]
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(float(confidence))
        or not 0 <= float(confidence) <= 1
    ):
        raise Z97ContractError("MatchVerdict.confidence 必须在 0 到 1")
    _require_sha256(
        row["judge_config_sha256"],
        "MatchVerdict.judge_config_sha256",
    )
    _require_sha256(
        row["adjudication_source_sha256"],
        "MatchVerdict.adjudication_source_sha256",
    )
    if not isinstance(row["human_review_required"], bool):
        raise Z97ContractError("MatchVerdict.human_review_required 必须是布尔值")
    return deepcopy(dict(row))


def validate_judge_eligibility(value: Any) -> dict[str, Any]:
    """校验裁判独立性资格表。"""

    row = _require_mapping(value, "judge_eligibility")
    for key in JUDGE_ELIGIBILITY_FIELDS:
        if key not in row:
            raise Z97ContractError(f"judge_eligibility 缺字段 {key}")
    extra_fields = set(row) - JUDGE_ELIGIBILITY_FIELDS
    if extra_fields:
        raise Z97ContractError(
            f"judge_eligibility 含 schema 未声明字段：{sorted(extra_fields)}"
        )
    if row["schema_version"] != "judge-eligibility-v1":
        raise Z97ContractError(
            "judge_eligibility schema_version 必须是 judge-eligibility-v1"
        )
    for key in (
        "candidate_provider",
        "candidate_family",
        "candidate_checkpoint",
        "candidate_training_lineage",
        "judge_kind",
        "judge_provider",
        "judge_family",
        "judge_checkpoint",
        "judge_training_lineage",
        "main_judge",
    ):
        _require_nonempty_string(row[key], f"judge_eligibility.{key}")
    for key in (
        "same_family",
        "same_checkpoint",
        "judge_trained_on_scored_outputs",
        "candidate_identity_visible",
        "historical_scores_visible",
        "repair_logs_visible",
        "eligible",
    ):
        if not isinstance(row[key], bool):
            raise Z97ContractError(f"judge_eligibility.{key} 必须是布尔值")
    _require_string_list(row["reasons"], "judge_eligibility.reasons")
    if row["eligible"]:
        disqualifying = (
            row["same_family"],
            row["same_checkpoint"],
            row["judge_trained_on_scored_outputs"],
            row["candidate_identity_visible"],
            row["historical_scores_visible"],
            row["repair_logs_visible"],
        )
        if any(disqualifying):
            raise Z97ContractError("裁判存在已声明污染却被标为 eligible")
    return deepcopy(dict(row))


def compute_edge_weight(value: Any) -> int:
    """按可复算附录的固定公式计算一条匹配边权。"""

    verdict = validate_match_verdict(value)
    if verdict["head_match"] == "contradiction":
        return -1000
    if verdict["head_match"] == "no":
        return -100
    present = sum(
        result["status"] == "present"
        for result in verdict["qualifier_results"]
    )
    missing = sum(
        result["status"] in {"missing", "contradicted", "unclear"}
        for result in verdict["qualifier_results"]
    )
    supported = sum(
        result["status"] == "supported"
        for result in verdict["anchor_component_results"]
    )
    unsupported = sum(
        result["status"] in {"partial", "unsupported", "wrong_anchor"}
        for result in verdict["anchor_component_results"]
    )
    return 100 + 10 * present + 5 * supported - 20 * missing - 30 * unsupported


def _hungarian_min_cost(costs: list[list[int]]) -> list[int]:
    """返回每行选中的列；要求列数不少于行数。"""

    row_count = len(costs)
    if row_count == 0:
        return []
    column_count = len(costs[0])
    if column_count < row_count or any(
        len(row) != column_count for row in costs
    ):
        raise Z97ContractError("匹配矩阵必须为列数不少于行数的矩形")
    infinity = 10**18
    u = [0] * (row_count + 1)
    v = [0] * (column_count + 1)
    p = [0] * (column_count + 1)
    way = [0] * (column_count + 1)
    for row_index in range(1, row_count + 1):
        p[0] = row_index
        minimum = [infinity] * (column_count + 1)
        used = [False] * (column_count + 1)
        column0 = 0
        while True:
            used[column0] = True
            current_row = p[column0]
            delta = infinity
            column1 = 0
            for column in range(1, column_count + 1):
                if used[column]:
                    continue
                current = (
                    costs[current_row - 1][column - 1]
                    - u[current_row]
                    - v[column]
                )
                if current < minimum[column]:
                    minimum[column] = current
                    way[column] = column0
                if minimum[column] < delta:
                    delta = minimum[column]
                    column1 = column
            for column in range(column_count + 1):
                if used[column]:
                    u[p[column]] += delta
                    v[column] -= delta
                else:
                    minimum[column] -= delta
            column0 = column1
            if p[column0] == 0:
                break
        while True:
            column1 = way[column0]
            p[column0] = p[column1]
            column0 = column1
            if column0 == 0:
                break
    assignment = [-1] * row_count
    for column in range(1, column_count + 1):
        if p[column] != 0:
            assignment[p[column] - 1] = column - 1
    return assignment


def select_max_weight_matches(
    rfus: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    verdicts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """做确定性一对一最大权匹配，负权边不会替代未匹配。"""

    validated_rfus = sorted(
        (validate_rfu(row) for row in rfus),
        key=lambda row: row["rfu_id"],
    )
    validated_claims = sorted(
        (validate_candidate_claim(row) for row in claims),
        key=lambda row: row["claim_id"],
    )
    validated_verdicts = sorted(
        (validate_match_verdict(row) for row in verdicts),
        key=lambda row: (row["rfu_id"], row["claim_id"]),
    )
    rfu_ids = [row["rfu_id"] for row in validated_rfus]
    claim_ids = [row["claim_id"] for row in validated_claims]
    if len(rfu_ids) != len(set(rfu_ids)):
        raise Z97ContractError("RFU 身份重复")
    if len(claim_ids) != len(set(claim_ids)):
        raise Z97ContractError("CandidateClaim 身份重复")
    known_rfus = set(rfu_ids)
    known_claims = set(claim_ids)
    by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for verdict in validated_verdicts:
        pair = (verdict["rfu_id"], verdict["claim_id"])
        if verdict["rfu_id"] not in known_rfus:
            raise Z97ContractError(f"判词引用未知 RFU：{verdict['rfu_id']}")
        if verdict["claim_id"] not in known_claims:
            raise Z97ContractError(f"判词引用未知主张：{verdict['claim_id']}")
        if pair in by_pair:
            raise Z97ContractError(f"同一 RFU/主张有多条判词：{pair}")
        by_pair[pair] = verdict

    if not rfu_ids:
        return []
    maximum_weight = max(
        [0, *(compute_edge_weight(verdict) for verdict in validated_verdicts)]
    )
    missing_weight = -1_000_000
    actual_column_count = len(claim_ids)
    costs: list[list[int]] = []
    for rfu_id in rfu_ids:
        weights = [
            compute_edge_weight(by_pair[(rfu_id, claim_id)])
            if (rfu_id, claim_id) in by_pair
            else missing_weight
            for claim_id in claim_ids
        ]
        weights.extend([0] * len(rfu_ids))
        costs.append([maximum_weight - weight for weight in weights])
    assignment = _hungarian_min_cost(costs)

    selected: list[dict[str, Any]] = []
    for row_index, column_index in enumerate(assignment):
        if column_index < 0 or column_index >= actual_column_count:
            continue
        pair = (rfu_ids[row_index], claim_ids[column_index])
        verdict = by_pair.get(pair)
        if verdict is None:
            continue
        weight = compute_edge_weight(verdict)
        if weight <= 0:
            continue
        selected.append(
            {
                "rfu_id": pair[0],
                "claim_id": pair[1],
                "edge_weight": weight,
                "verdict": verdict,
            }
        )
    return sorted(selected, key=lambda row: (row["rfu_id"], row["claim_id"]))


def _ratio(numerator: float, denominator: float) -> dict[str, Any]:
    value = None if denominator == 0 else numerator / denominator
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": value,
    }


def _qualifier_full(rfu: Mapping[str, Any], verdict: Mapping[str, Any]) -> bool:
    required = [row["qualifier_id"] for row in rfu["required_qualifiers"]]
    if not required:
        return True
    status_by_id = {
        row["qualifier_id"]: row["status"]
        for row in verdict["qualifier_results"]
    }
    return all(status_by_id.get(qualifier_id) == "present" for qualifier_id in required)


def _anchor_full(verdict: Mapping[str, Any]) -> bool:
    results = verdict["anchor_component_results"]
    return bool(results) and all(row["status"] == "supported" for row in results)


def compute_score_ticket(
    rfus: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    verdicts: Sequence[Mapping[str, Any]],
    *,
    judge_eligibility: Mapping[str, Any],
    candidate_universe_complete: bool,
    legacy_metrics_read_only: Mapping[str, Any] | None = None,
    ticket_id: str = "RFU-SCORE-TICKET",
) -> dict[str, Any]:
    """计算五层新读数；不会生成、补写或改判任何语义判词。"""

    validated_rfus = [validate_rfu(row) for row in rfus]
    validated_claims = [validate_candidate_claim(row) for row in claims]
    validated_verdicts = [validate_match_verdict(row) for row in verdicts]
    eligibility = validate_judge_eligibility(judge_eligibility)
    if not isinstance(candidate_universe_complete, bool):
        raise Z97ContractError("candidate_universe_complete 必须是布尔值")
    legacy_before = (
        sha256_bytes(stable_json_bytes(legacy_metrics_read_only))
        if legacy_metrics_read_only is not None
        else None
    )
    rfu_by_id = {row["rfu_id"]: row for row in validated_rfus}
    claim_by_id = {row["claim_id"]: row for row in validated_claims}
    if len(rfu_by_id) != len(validated_rfus):
        raise Z97ContractError("RFU 身份重复")
    if len(claim_by_id) != len(validated_claims):
        raise Z97ContractError("CandidateClaim 身份重复")
    for verdict in validated_verdicts:
        rfu = rfu_by_id.get(verdict["rfu_id"])
        claim = claim_by_id.get(verdict["claim_id"])
        if rfu is None or claim is None:
            raise Z97ContractError("MatchVerdict 引用未知 RFU 或主张")
        expected_qualifiers = {
            row["qualifier_id"] for row in rfu["required_qualifiers"]
        }
        actual_qualifiers = {
            row["qualifier_id"] for row in verdict["qualifier_results"]
        }
        if actual_qualifiers != expected_qualifiers:
            raise Z97ContractError("判词限定结果没有完整对齐 RFU 限定清单")
        expected_components = {
            row["component_id"] for row in claim["claim_components"]
        }
        actual_components = {
            row["component_id"] for row in verdict["anchor_component_results"]
        }
        if actual_components != expected_components:
            raise Z97ContractError("判词锚结果没有完整对齐候选主张部件")

    selected = select_max_weight_matches(
        validated_rfus,
        validated_claims,
        validated_verdicts,
    )
    selected_by_rfu = {row["rfu_id"]: row for row in selected}
    selected_by_claim = {row["claim_id"]: row for row in selected}

    head_covered = 0
    qualifier_complete = 0
    anchor_complete = 0
    usable_weight = 0.0
    total_weight = sum(float(row["weight"]) for row in validated_rfus)
    per_rfu: list[dict[str, Any]] = []
    for rfu in validated_rfus:
        match = selected_by_rfu.get(rfu["rfu_id"])
        verdict = match["verdict"] if match else None
        head_ok = bool(verdict and verdict["head_match"] == "yes")
        qualifier_ok = bool(verdict and head_ok and _qualifier_full(rfu, verdict))
        anchor_ok = bool(verdict and _anchor_full(verdict))
        atomicity_ok = bool(
            verdict
            and verdict["atomicity"] in {"atomic", "mechanically_splittable"}
        )
        usable = head_ok and qualifier_ok and anchor_ok and atomicity_ok
        head_covered += int(head_ok)
        qualifier_complete += int(qualifier_ok)
        anchor_complete += int(anchor_ok)
        if usable:
            usable_weight += float(rfu["weight"])
        per_rfu.append(
            {
                "rfu_id": rfu["rfu_id"],
                "selected_claim_id": match["claim_id"] if match else None,
                "edge_weight": match["edge_weight"] if match else None,
                "head_covered": head_ok,
                "required_qualifiers_complete": qualifier_ok,
                "anchor_support_complete": anchor_ok,
                "atomicity_acceptable": atomicity_ok,
                "is_usable": usable,
            }
        )

    fully_supported_claims = 0
    for claim in validated_claims:
        match = selected_by_claim.get(claim["claim_id"])
        if match and _anchor_full(match["verdict"]):
            fully_supported_claims += 1
    fcr = _ratio(head_covered, len(validated_rfus))
    qcr = _ratio(qualifier_complete, head_covered)
    asr = _ratio(anchor_complete, len(selected))
    ucr = _ratio(usable_weight, total_weight)
    sop = _ratio(fully_supported_claims, len(validated_claims))
    sop_threshold_met = bool(
        candidate_universe_complete
        and sop["value"] is not None
        and sop["value"] >= 0.98
    )
    five_layer_values_present = all(
        metric["value"] is not None for metric in (fcr, qcr, asr, ucr, sop)
    )
    formal_score_eligible = bool(
        eligibility["eligible"]
        and candidate_universe_complete
        and five_layer_values_present
    )

    legacy_copy = (
        deepcopy(dict(legacy_metrics_read_only))
        if legacy_metrics_read_only is not None
        else None
    )
    legacy_after = (
        sha256_bytes(stable_json_bytes(legacy_copy))
        if legacy_copy is not None
        else None
    )
    if legacy_before != legacy_after:
        raise AssertionError("旧成绩只读副本发生漂移")
    return {
        "schema_version": "ucr-score-ticket-v1",
        "ticket_id": ticket_id,
        "status": (
            "candidate_metrics_complete_not_released"
            if five_layer_values_present
            else "candidate_metrics_incomplete"
        ),
        "metric_contract": {
            "parallel_no_offset": True,
            "zero_required_qualifiers_count_as_qcr_pass": True,
            "sop_release_threshold": 0.98,
            "strict_legacy_metrics_read_only": True,
            "mrp_72_release_gate_required": True,
            "mrp_72_release_gate_passed": False,
        },
        "metrics": {
            "FCR": fcr,
            "QCR_full": qcr,
            "ASR_full": asr,
            "UCR": ucr,
            "SOP": {
                **sop,
                "candidate_universe_complete": candidate_universe_complete,
                "threshold_met": sop_threshold_met,
            },
        },
        "formal_score_eligible": formal_score_eligible,
        "eligibility": eligibility,
        "selected_matches": [
            {
                "rfu_id": row["rfu_id"],
                "claim_id": row["claim_id"],
                "edge_weight": row["edge_weight"],
            }
            for row in selected
        ],
        "per_rfu": per_rfu,
        "unmatched_rfu_ids": [
            rfu["rfu_id"]
            for rfu in validated_rfus
            if rfu["rfu_id"] not in selected_by_rfu
        ],
        "unmatched_claim_ids": [
            claim["claim_id"]
            for claim in validated_claims
            if claim["claim_id"] not in selected_by_claim
        ],
        "legacy_metrics_read_only": legacy_copy,
        "legacy_metrics_sha256_before": legacy_before,
        "legacy_metrics_sha256_after": legacy_after,
    }


def evaluate_canary_suite(value: Any) -> dict[str, Any]:
    """逐案计算八个冻结反例，并核对预写读数和原因码。"""

    suite = _require_mapping(value, "canary_suite")
    if suite.get("schema_version") != "rfu-canary-suite-v1":
        raise Z97ContractError(
            "canary_suite schema_version 必须是 rfu-canary-suite-v1"
        )
    cases = suite.get("cases")
    if not isinstance(cases, list) or len(cases) != 8:
        raise Z97ContractError("canary_suite 必须恰好含八案")
    seen: set[str] = set()
    receipts: list[dict[str, Any]] = []
    for case in cases:
        case_row = _require_mapping(case, "canary_case")
        case_id = _require_nonempty_string(case_row.get("case_id"), "canary.case_id")
        if case_id in seen:
            raise Z97ContractError(f"CANARY 身份重复：{case_id}")
        seen.add(case_id)
        rfus = case_row.get("rfus")
        claims = case_row.get("claims")
        verdicts = case_row.get("verdicts")
        if not all(isinstance(rows, list) for rows in (rfus, claims, verdicts)):
            raise Z97ContractError(f"{case_id} 三类输入必须是数组")
        eligibility = case_row.get("judge_eligibility")
        ticket = compute_score_ticket(
            rfus,
            claims,
            verdicts,
            judge_eligibility=eligibility,
            candidate_universe_complete=True,
            ticket_id=f"{case_id}-TICKET",
        )
        expected = _require_mapping(case_row.get("expected"), f"{case_id}.expected")
        expected_metrics = _require_mapping(
            expected.get("metrics"),
            f"{case_id}.expected.metrics",
        )
        metric_pass = all(
            ticket["metrics"][metric_name]["value"] == expected_value
            for metric_name, expected_value in expected_metrics.items()
        )
        expected_codes = set(
            _require_string_list(
                expected.get("reason_codes"),
                f"{case_id}.expected.reason_codes",
            )
        )
        actual_codes = {
            code for verdict in verdicts for code in verdict["reason_codes"]
        }
        reason_pass = expected_codes <= actual_codes
        if not metric_pass or not reason_pass:
            raise Z97ContractError(f"{case_id} 未命中预写结果")
        receipts.append(
            {
                "case_id": case_id,
                "status": "PASS",
                "metrics": {
                    name: ticket["metrics"][name]["value"]
                    for name in ("FCR", "QCR_full", "ASR_full", "UCR", "SOP")
                },
                "reason_codes": sorted(actual_codes),
            }
        )
    return {
        "schema_version": "rfu-canary-receipt-v1",
        "status": "PASS",
        "case_count": len(receipts),
        "cases": receipts,
    }
