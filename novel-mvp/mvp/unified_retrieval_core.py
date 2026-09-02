"""C9 统一取件的零 API 编排核心。

本模块只处理调用方交来的任务需求和已解析 source outcomes。它不读取文件、
AuthorWorkspace、数据库或网络，也不替任务方案判断故事线和材料相关性。
最终预算筛选只调用现有 ``packer.pack_context``。
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any, NoReturn

from . import packer


VERSION = "c9-unified-retrieval-run-v1"
SOURCE_CONTRACT_VERSIONS = {
    "LEDGER_READ_TOOL_CONTRACT": "ledger-read-tool-contract-v1",
    "TRACEABLE_PROVENANCE_SEAL": "v1",
    "CHAPTER_SETTLEMENT_SEAL": "v1",
    "CHAPTER_LAYERED_SUMMARY": "v1",
}
SOURCE_DOCUMENT_CONTRACTS = {
    "LEDGER_READ_TOOL_CONTRACT": "LEDGER_READ_RESPONSE",
    "TRACEABLE_PROVENANCE_SEAL": "TRACEABLE_PROVENANCE_SEAL",
    "CHAPTER_SETTLEMENT_SEAL": "CHAPTER_SETTLEMENT_SEAL",
    "CHAPTER_LAYERED_SUMMARY": "CHAPTER_LAYERED_SUMMARY",
}
LAYER_PARENT = {
    "LEDGER_OBJECT": None,
    "FORMATION_BASIS": "LEDGER_OBJECT",
    "ORIGINAL_EVIDENCE": "FORMATION_BASIS",
}
FATAL_REASON_CODES = {
    "UNAUTHORIZED",
    "CURRENT_ADVANCED",
    "INVALID_PIN_SET",
    "SOURCE_CORRUPTED",
    "SHA_MISMATCH",
    "INTERNAL_ERROR",
}
SOURCE_OUTCOME_FIELDS = {
    "need_id",
    "source_status",
    "reason_code",
    "source_document",
    "material_text",
    "validator_id",
}
SCOPE_FIELDS = {
    "author_id",
    "project_id",
    "task_id",
    "consumer_id",
    "workpoint_ref",
    "story_scope_ref",
    "sandbox_ref",
    "upstream_card_ref",
}
NEED_FIELDS = {
    "need_id",
    "evidence_layer",
    "parent_need_id",
    "source_contract",
    "source_contract_version",
    "object_ref",
    "actuality_class",
    "obligation_tier",
    "selection_rank",
    "task_relation",
    "estimated_tokens",
    "recall_disposition",
    "recall_handle",
    "expansion_trigger",
}
REQUEST_FIELDS = {
    "contract",
    "version",
    "scope",
    "basis_mode",
    "task_actuality_scope",
    "budget",
    "gap_policy",
    "source_needs",
    "request_sha256",
}
PLAN_FIELDS = {
    "contract",
    "version",
    "scope",
    "basis_mode",
    "request_sha256",
    "steps",
    "plan_sha256",
}
RESULT_FIELDS = {
    "contract",
    "version",
    "scope",
    "basis_mode",
    "request_sha256",
    "plan_sha256",
    "status",
    "replay_status",
    "material_package",
    "short_receipt",
    "trace_log",
    "run_sha256",
}
SOURCE_VALIDATION_FIELDS = {
    "source_contract",
    "source_contract_version",
    "validator_id",
    "validation_result",
    "failure_code",
    "document_sha256",
    "input_mode",
    "read_request_id",
    "basis_sha256",
}


class C9RetrievalError(ValueError):
    """C9 请求、计划、source outcome 或结果违反冻结边界。"""


def _fail(code: str) -> NoReturn:
    raise C9RetrievalError(code)


def canonical_bytes(value: Any) -> bytes:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise C9RetrievalError("VALUE_NOT_JSON_SERIALIZABLE") from exc
    return payload.encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _seal(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    result.pop(field, None)
    result[field] = sha256_json(result)
    return result


def _verify_seal(value: Mapping[str, Any], field: str, code: str) -> None:
    expected = _seal(value, field)[field]
    if value.get(field) != expected:
        _fail(code)


def _object(value: Any, fields: set[str], code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail(code)
    return value


def _string(value: Any, code: str) -> None:
    if not isinstance(value, str) or not value.strip():
        _fail(code)


def _nullable_string(value: Any, code: str) -> None:
    if value is not None:
        _string(value, code)


def _integer(value: Any, minimum: int, code: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        _fail(code)


def _sha(value: Any, code: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(code)


def _scope_shape(value: Any) -> None:
    scope = _object(value, SCOPE_FIELDS, "SCOPE_FIELDS_INVALID")
    for field in SCOPE_FIELDS - {"sandbox_ref", "upstream_card_ref"}:
        _string(scope[field], f"SCOPE_FIELD_INVALID:{field}")
    _nullable_string(scope["sandbox_ref"], "SCOPE_FIELD_INVALID:sandbox_ref")
    _nullable_string(
        scope["upstream_card_ref"],
        "SCOPE_FIELD_INVALID:upstream_card_ref",
    )


def _need_shape(value: Any, *, plan_step: bool = False) -> None:
    fields = NEED_FIELDS | ({"order"} if plan_step else set())
    need = _object(value, fields, "NEED_FIELDS_INVALID")
    if plan_step:
        _integer(need["order"], 1, "PLAN_STEP_ORDER_INVALID")
    _string(need["need_id"], "NEED_ID_INVALID")
    if not need["need_id"].startswith("NEED-"):
        _fail("NEED_ID_INVALID")
    if need["evidence_layer"] not in LAYER_PARENT:
        _fail("NEED_EVIDENCE_LAYER_INVALID")
    _nullable_string(need["parent_need_id"], "NEED_PARENT_INVALID")
    if need["source_contract"] not in SOURCE_CONTRACT_VERSIONS:
        _fail("NEED_SOURCE_CONTRACT_INVALID")
    for field in ("source_contract_version", "object_ref", "task_relation"):
        _string(need[field], f"NEED_FIELD_INVALID:{field}")
    if need["actuality_class"] not in {
        "CURRENT_FACT_OR_STATE",
        "ACTIVE_CONSTRAINT",
        "FUTURE_PLAN_OR_PROJECTION",
    }:
        _fail("NEED_ACTUALITY_INVALID")
    if need["obligation_tier"] not in {"HARD", "SHOULD", "MAY"}:
        _fail("NEED_OBLIGATION_INVALID")
    if need["selection_rank"] is not None:
        _integer(need["selection_rank"], 0, "NEED_SELECTION_RANK_INVALID")
    _integer(need["estimated_tokens"], 0, "NEED_TOKEN_ESTIMATE_INVALID")
    if need["recall_disposition"] not in {
        "RETRIEVABLE",
        "NOT_RETRIEVABLE",
    }:
        _fail("NEED_RECALL_DISPOSITION_INVALID")
    _nullable_string(need["recall_handle"], "NEED_RECALL_HANDLE_INVALID")
    if need["expansion_trigger"] not in {
        "INITIAL",
        "AUDIT_REQUIRED",
        "CONFLICT_DETECTED",
        "SOURCE_STALE",
        "LOW_CONFIDENCE",
        "LEDGER_INSUFFICIENT",
        "DOWNSTREAM_REQUESTED_MORE",
        "HIGH_IMPACT_DECISION",
    }:
        _fail("NEED_EXPANSION_TRIGGER_INVALID")


def _source_validation_shape(value: Any) -> None:
    row = _object(
        value,
        SOURCE_VALIDATION_FIELDS,
        "SOURCE_VALIDATION_FIELDS_INVALID",
    )
    if row["source_contract"] not in SOURCE_CONTRACT_VERSIONS:
        _fail("SOURCE_VALIDATION_CONTRACT_INVALID")
    for field in ("source_contract_version", "validator_id"):
        _string(row[field], f"SOURCE_VALIDATION_FIELD_INVALID:{field}")
    if row["validation_result"] not in {
        "LEDGER_READ_RESPONSE_VALID",
        "STRUCTURAL_VALID",
        "STRUCTURAL_VALID_OWNER_UNRESOLVED",
        "SOURCE_VALIDATION_FAILED",
    }:
        _fail("SOURCE_VALIDATION_RESULT_INVALID")
    _nullable_string(row["failure_code"], "SOURCE_VALIDATION_FAILURE_CODE_INVALID")
    _sha(row["document_sha256"], "SOURCE_DOCUMENT_SHA256_INVALID")
    if row["input_mode"] not in {
        "LEDGER_READ_RESPONSE",
        "CALLER_PROVIDED_VALIDATED_OBJECT",
    }:
        _fail("SOURCE_INPUT_MODE_INVALID")
    _nullable_string(row["read_request_id"], "SOURCE_READ_REQUEST_ID_INVALID")
    if row["basis_sha256"] is not None:
        _sha(row["basis_sha256"], "SOURCE_BASIS_SHA256_INVALID")


def _request_shape(value: Mapping[str, Any]) -> None:
    _object(value, REQUEST_FIELDS, "REQUEST_FIELDS_INVALID")
    if value["version"] != VERSION:
        _fail("REQUEST_VERSION_INVALID")
    _scope_shape(value["scope"])
    if value["basis_mode"] not in {"current_at_start", "pinned_manifest"}:
        _fail("REQUEST_BASIS_MODE_INVALID")
    if value["task_actuality_scope"] not in {
        "CURRENT_TRUTH_REQUIRED",
        "FUTURE_MATERIAL_EXPLICITLY_IN_SCOPE",
    }:
        _fail("REQUEST_ACTUALITY_SCOPE_INVALID")
    budget = _object(
        value["budget"],
        {"limit_tokens", "estimator_ref"},
        "REQUEST_BUDGET_FIELDS_INVALID",
    )
    _integer(budget["limit_tokens"], 1, "REQUEST_BUDGET_INVALID")
    _string(budget["estimator_ref"], "REQUEST_ESTIMATOR_INVALID")
    gap = _object(
        value["gap_policy"],
        {"policy_ref", "missing_required_behavior"},
        "REQUEST_GAP_POLICY_FIELDS_INVALID",
    )
    _string(gap["policy_ref"], "REQUEST_GAP_POLICY_REF_INVALID")
    if gap["missing_required_behavior"] not in {
        "AUTO_CONTINUE",
        "WARN_AND_CONTINUE",
        "BLOCK",
    }:
        _fail("REQUEST_GAP_BEHAVIOR_INVALID")
    if not isinstance(value["source_needs"], list) or not value["source_needs"]:
        _fail("REQUEST_SOURCE_NEEDS_INVALID")
    for need in value["source_needs"]:
        _need_shape(need)
    _sha(value["request_sha256"], "REQUEST_SHA256_INVALID")


def _plan_shape(value: Mapping[str, Any]) -> None:
    _object(value, PLAN_FIELDS, "PLAN_FIELDS_INVALID")
    if value["version"] != VERSION:
        _fail("PLAN_VERSION_INVALID")
    _scope_shape(value["scope"])
    if value["basis_mode"] not in {"current_at_start", "pinned_manifest"}:
        _fail("PLAN_BASIS_MODE_INVALID")
    _sha(value["request_sha256"], "PLAN_REQUEST_SHA256_INVALID")
    if not isinstance(value["steps"], list) or not value["steps"]:
        _fail("PLAN_STEPS_INVALID")
    for step in value["steps"]:
        _need_shape(step, plan_step=True)
    _sha(value["plan_sha256"], "PLAN_SHA256_INVALID")


def _result_shape(value: Mapping[str, Any]) -> None:
    _object(value, RESULT_FIELDS, "RESULT_FIELDS_INVALID")
    if value["version"] != VERSION:
        _fail("RESULT_VERSION_INVALID")
    _scope_shape(value["scope"])
    if value["basis_mode"] not in {"current_at_start", "pinned_manifest"}:
        _fail("RESULT_BASIS_MODE_INVALID")
    for field in ("request_sha256", "plan_sha256", "run_sha256"):
        _sha(value[field], f"RESULT_SHA256_INVALID:{field}")
    if value["status"] not in {"READY", "READY_WITH_GAPS", "STOPPED"}:
        _fail("RESULT_STATUS_INVALID")
    if value["replay_status"] not in {
        "REPLAYABLE_PINNED",
        "AUDITABLE_CURRENT_NOT_REPLAYABLE",
    }:
        _fail("RESULT_REPLAY_STATUS_INVALID")

    package = _object(
        value["material_package"],
        {"loaded", "omitted", "outstanding", "package_sha256"},
        "PACKAGE_FIELDS_INVALID",
    )
    for field in ("loaded", "omitted", "outstanding"):
        if not isinstance(package[field], list):
            _fail(f"PACKAGE_LIST_INVALID:{field}")
    for row in package["loaded"]:
        item = _object(
            row,
            {
                "need_id",
                "object_ref",
                "evidence_layer",
                "material_text",
                "material_sha256",
                "why_loaded",
                "source_validation",
                "recall_disposition",
                "recall_handle",
            },
            "LOADED_FIELDS_INVALID",
        )
        for field in ("need_id", "object_ref", "material_text", "why_loaded"):
            _string(item[field], f"LOADED_FIELD_INVALID:{field}")
        if item["evidence_layer"] not in LAYER_PARENT:
            _fail("LOADED_LAYER_INVALID")
        _sha(item["material_sha256"], "LOADED_MATERIAL_SHA256_INVALID")
        _source_validation_shape(item["source_validation"])
        if item["recall_disposition"] not in {
            "RETRIEVABLE",
            "NOT_RETRIEVABLE",
        }:
            _fail("LOADED_RECALL_DISPOSITION_INVALID")
        _nullable_string(item["recall_handle"], "LOADED_RECALL_HANDLE_INVALID")
    for row in package["omitted"]:
        item = _object(
            row,
            {
                "need_id",
                "object_ref",
                "reason",
                "source_validation",
                "recall_disposition",
                "recall_handle",
            },
            "OMITTED_FIELDS_INVALID",
        )
        for field in ("need_id", "object_ref", "reason"):
            _string(item[field], f"OMITTED_FIELD_INVALID:{field}")
        _source_validation_shape(item["source_validation"])
        if item["recall_disposition"] not in {
            "RETRIEVABLE",
            "NOT_RETRIEVABLE",
        }:
            _fail("OMITTED_RECALL_DISPOSITION_INVALID")
        _nullable_string(item["recall_handle"], "OMITTED_RECALL_HANDLE_INVALID")
    for row in package["outstanding"]:
        item = _object(
            row,
            {
                "need_id",
                "object_ref",
                "obligation_tier",
                "category",
                "reason_code",
                "fatal",
                "source_validation",
            },
            "OUTSTANDING_FIELDS_INVALID",
        )
        for field in ("need_id", "object_ref", "reason_code"):
            _string(item[field], f"OUTSTANDING_FIELD_INVALID:{field}")
        if item["obligation_tier"] not in {"HARD", "SHOULD", "MAY"}:
            _fail("OUTSTANDING_OBLIGATION_INVALID")
        if item["category"] not in {
            "NOT_READ",
            "UNRESOLVED",
            "FAILED",
            "NOT_DELIVERED",
        }:
            _fail("OUTSTANDING_CATEGORY_INVALID")
        if not isinstance(item["fatal"], bool):
            _fail("OUTSTANDING_FATAL_INVALID")
        if item["source_validation"] is not None:
            _source_validation_shape(item["source_validation"])
    _sha(package["package_sha256"], "PACKAGE_SHA256_INVALID")

    trace = _object(
        value["trace_log"],
        {"consumer_id", "events", "trace_log_sha256"},
        "TRACE_FIELDS_INVALID",
    )
    _string(trace["consumer_id"], "TRACE_CONSUMER_INVALID")
    if not isinstance(trace["events"], list) or not trace["events"]:
        _fail("TRACE_EVENTS_INVALID")
    for row in trace["events"]:
        event = _object(
            row,
            {
                "order",
                "need_id",
                "source_status",
                "reason_code",
                "why_loaded",
                "validation_result",
                "final_disposition",
                "expansion_trigger",
            },
            "TRACE_EVENT_FIELDS_INVALID",
        )
        _integer(event["order"], 1, "TRACE_EVENT_ORDER_INVALID")
        _string(event["need_id"], "TRACE_EVENT_NEED_ID_INVALID")
        if event["source_status"] not in {
            "OK",
            "EMPTY",
            "REJECTED",
            "ERROR",
            "NOT_ATTEMPTED",
        }:
            _fail("TRACE_SOURCE_STATUS_INVALID")
        _nullable_string(event["reason_code"], "TRACE_REASON_CODE_INVALID")
        _nullable_string(event["why_loaded"], "TRACE_WHY_LOADED_INVALID")
        if event["validation_result"] is not None and event[
            "validation_result"
        ] not in {
            "LEDGER_READ_RESPONSE_VALID",
            "STRUCTURAL_VALID",
            "STRUCTURAL_VALID_OWNER_UNRESOLVED",
            "SOURCE_VALIDATION_FAILED",
        }:
            _fail("TRACE_VALIDATION_RESULT_INVALID")
        if event["final_disposition"] not in {
            "LOADED",
            "OMITTED",
            "NOT_READ",
            "UNRESOLVED",
            "FAILED",
            "NOT_DELIVERED",
        }:
            _fail("TRACE_DISPOSITION_INVALID")
        if event["expansion_trigger"] not in {
            "INITIAL",
            "AUDIT_REQUIRED",
            "CONFLICT_DETECTED",
            "SOURCE_STALE",
            "LOW_CONFIDENCE",
            "LEDGER_INSUFFICIENT",
            "DOWNSTREAM_REQUESTED_MORE",
            "HIGH_IMPACT_DECISION",
        }:
            _fail("TRACE_EXPANSION_TRIGGER_INVALID")
    _sha(trace["trace_log_sha256"], "TRACE_LOG_SHA256_INVALID")

    receipt = _object(
        value["short_receipt"],
        {
            "status",
            "scope",
            "required_total",
            "required_satisfied",
            "required_missing",
            "loaded_count",
            "omitted_count",
            "outstanding_count",
            "evidence_layers_loaded",
            "important_missing_need_ids",
            "warnings",
            "source_versions_used",
            "package_sha256",
            "trace_log_sha256",
            "receipt_sha256",
        },
        "RECEIPT_FIELDS_INVALID",
    )
    if receipt["status"] not in {"READY", "READY_WITH_GAPS", "STOPPED"}:
        _fail("RECEIPT_STATUS_INVALID")
    _scope_shape(receipt["scope"])
    for field in (
        "required_total",
        "required_satisfied",
        "required_missing",
        "loaded_count",
        "omitted_count",
        "outstanding_count",
    ):
        _integer(receipt[field], 0, f"RECEIPT_COUNT_INVALID:{field}")
    for field in (
        "evidence_layers_loaded",
        "important_missing_need_ids",
        "warnings",
        "source_versions_used",
    ):
        if not isinstance(receipt[field], list):
            _fail(f"RECEIPT_LIST_INVALID:{field}")
    if any(layer not in LAYER_PARENT for layer in receipt["evidence_layers_loaded"]):
        _fail("RECEIPT_EVIDENCE_LAYER_INVALID")
    for field in ("important_missing_need_ids", "warnings"):
        for item in receipt[field]:
            _string(item, f"RECEIPT_LIST_ITEM_INVALID:{field}")
    for item in receipt["source_versions_used"]:
        source = _object(
            item,
            {"source_contract", "source_contract_version"},
            "RECEIPT_SOURCE_VERSION_FIELDS_INVALID",
        )
        if source["source_contract"] not in SOURCE_CONTRACT_VERSIONS:
            _fail("RECEIPT_SOURCE_CONTRACT_INVALID")
        _string(
            source["source_contract_version"],
            "RECEIPT_SOURCE_CONTRACT_VERSION_INVALID",
        )
    for field in ("package_sha256", "trace_log_sha256", "receipt_sha256"):
        _sha(receipt[field], f"RECEIPT_SHA256_INVALID:{field}")


def _validate_schema(value: Any) -> None:
    if not isinstance(value, Mapping):
        _fail("CONTRACT_OBJECT_REQUIRED")
    contract = value.get("contract")
    if contract == "C9_RETRIEVAL_REQUEST":
        _request_shape(value)
    elif contract == "C9_RETRIEVAL_PLAN":
        _plan_shape(value)
    elif contract == "C9_RETRIEVAL_RESULT":
        _result_shape(value)
    else:
        _fail("CONTRACT_IDENTITY_INVALID")


def _need_map(request: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {need["need_id"]: need for need in request["source_needs"]}


def _validate_need_order(request: Mapping[str, Any]) -> None:
    seen: dict[str, dict[str, Any]] = {}
    for index, need in enumerate(request["source_needs"]):
        need_id = need["need_id"]
        if need_id in seen:
            _fail(f"NEED_ID_DUPLICATE:{need_id}")
        source_contract = need["source_contract"]
        expected_version = SOURCE_CONTRACT_VERSIONS.get(source_contract)
        if expected_version is None or need["source_contract_version"] != expected_version:
            _fail(f"SOURCE_CONTRACT_VERSION_UNSUPPORTED:{need_id}")

        layer = need["evidence_layer"]
        parent_id = need["parent_need_id"]
        expected_parent_layer = LAYER_PARENT[layer]
        if expected_parent_layer is None:
            if parent_id is not None:
                _fail(f"LEDGER_NEED_PARENT_FORBIDDEN:{need_id}")
            if need["expansion_trigger"] != "INITIAL":
                _fail(f"LEDGER_NEED_MUST_BE_INITIAL:{need_id}")
        else:
            parent = seen.get(parent_id)
            if parent is None:
                _fail(f"NEED_PARENT_MUST_PRECEDE_CHILD:{need_id}")
            if parent["evidence_layer"] != expected_parent_layer:
                _fail(f"NEED_LAYER_CHAIN_INVALID:{need_id}")
            if need["expansion_trigger"] == "INITIAL":
                _fail(f"DEEP_NEED_TRIGGER_REQUIRED:{need_id}")

        if source_contract == "TRACEABLE_PROVENANCE_SEAL" and layer != "FORMATION_BASIS":
            _fail(f"PROVENANCE_LAYER_INVALID:{need_id}")
        if source_contract in {
            "CHAPTER_SETTLEMENT_SEAL",
            "CHAPTER_LAYERED_SUMMARY",
        } and layer != "LEDGER_OBJECT":
            _fail(f"CHAPTER_PROJECTION_LAYER_INVALID:{need_id}")

        obligation = need["obligation_tier"]
        rank = need["selection_rank"]
        if obligation == "HARD" and rank is not None:
            _fail(f"HARD_SELECTION_RANK_FORBIDDEN:{need_id}")
        if obligation != "HARD" and rank is None:
            _fail(f"OPTIONAL_SELECTION_RANK_REQUIRED:{need_id}")

        recall_disposition = need["recall_disposition"]
        recall_handle = need["recall_handle"]
        if recall_disposition == "RETRIEVABLE" and recall_handle is None:
            _fail(f"RECALL_HANDLE_REQUIRED:{need_id}")
        if recall_disposition == "NOT_RETRIEVABLE" and recall_handle is not None:
            _fail(f"RECALL_HANDLE_FORBIDDEN:{need_id}")
        seen[need_id] = copy.deepcopy(need)


def validate_request(value: Any) -> dict[str, Any]:
    _validate_schema(value)
    if value.get("contract") != "C9_RETRIEVAL_REQUEST":
        _fail("REQUEST_CONTRACT_REQUIRED")
    _verify_seal(value, "request_sha256", "REQUEST_SHA256_MISMATCH")
    _validate_need_order(value)
    return copy.deepcopy(value)


def seal_request(value: Mapping[str, Any]) -> dict[str, Any]:
    return _seal(value, "request_sha256")


def _plan_from_request(request: Mapping[str, Any]) -> dict[str, Any]:
    steps = []
    for order, need in enumerate(request["source_needs"], start=1):
        step = copy.deepcopy(need)
        step["order"] = order
        steps.append(step)
    return {
        "contract": "C9_RETRIEVAL_PLAN",
        "version": VERSION,
        "scope": copy.deepcopy(request["scope"]),
        "basis_mode": request["basis_mode"],
        "request_sha256": request["request_sha256"],
        "steps": steps,
    }


def prepare_plan(request: Mapping[str, Any]) -> dict[str, Any]:
    checked = validate_request(request)
    return _seal(_plan_from_request(checked), "plan_sha256")


def validate_plan(
    value: Any,
    request: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    _validate_schema(value)
    if value.get("contract") != "C9_RETRIEVAL_PLAN":
        _fail("PLAN_CONTRACT_REQUIRED")
    _verify_seal(value, "plan_sha256", "PLAN_SHA256_MISMATCH")
    orders = [step["order"] for step in value["steps"]]
    if orders != list(range(1, len(orders) + 1)):
        _fail("PLAN_STEP_ORDER_INVALID")
    if request is not None:
        checked_request = validate_request(request)
        expected = _seal(_plan_from_request(checked_request), "plan_sha256")
        if value != expected:
            _fail("PLAN_NOT_EXACT_REQUEST_PROJECTION")
    return copy.deepcopy(value)


def _scope_from_source_document(
    source_contract: str,
    document: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    if source_contract == "LEDGER_READ_TOOL_CONTRACT":
        receipt = document.get("receipt")
        if not isinstance(receipt, Mapping):
            return None, None
        return receipt.get("author_id"), receipt.get("project_id")
    scope = document.get("truth_scope_ref")
    if not isinstance(scope, Mapping):
        return None, None
    return scope.get("principal_author_id"), scope.get("project_id")


def _validation_result(
    need: Mapping[str, Any],
    outcome: Mapping[str, Any],
    scope: Mapping[str, Any],
    basis_mode: str,
    validator_registry: Mapping[str, Callable[[Any], Any]],
) -> dict[str, Any] | None:
    status = outcome["source_status"]
    if status == "NOT_ATTEMPTED":
        if (
            outcome["source_document"] is not None
            or outcome["material_text"] is not None
            or outcome["validator_id"] is not None
            or not outcome["reason_code"]
        ):
            _fail(f"NOT_ATTEMPTED_SHAPE_INVALID:{need['need_id']}")
        return None

    document = outcome["source_document"]
    validator_id = outcome["validator_id"]
    if not isinstance(document, Mapping) or not isinstance(validator_id, str):
        _fail(f"SOURCE_DOCUMENT_OR_VALIDATOR_MISSING:{need['need_id']}")
    validator = validator_registry.get(need["source_contract"])
    if validator is None:
        _fail(f"SOURCE_VALIDATOR_NOT_REGISTERED:{need['need_id']}")
    if document.get("contract") != SOURCE_DOCUMENT_CONTRACTS[need["source_contract"]]:
        _fail(f"SOURCE_DOCUMENT_CONTRACT_MISMATCH:{need['need_id']}")
    if document.get("version") != need["source_contract_version"]:
        _fail(f"SOURCE_DOCUMENT_VERSION_MISMATCH:{need['need_id']}")

    try:
        raw_validation = validator(copy.deepcopy(document))
    except Exception as exc:  # validator errors stay behind one stable C9 boundary
        raise C9RetrievalError(
            f"SOURCE_VALIDATION_FAILED:{need['need_id']}:{type(exc).__name__}"
        ) from exc

    source_contract = need["source_contract"]
    if source_contract == "LEDGER_READ_TOOL_CONTRACT":
        if not isinstance(raw_validation, Mapping):
            _fail(f"LEDGER_VALIDATOR_RESULT_INVALID:{need['need_id']}")
        document_status = document.get("status")
        if status != document_status:
            _fail(f"LEDGER_STATUS_MISMATCH:{need['need_id']}")
        if document.get("basis_mode") != basis_mode:
            _fail(f"SOURCE_BASIS_MODE_MISMATCH:{need['need_id']}")
        document_reason = document.get("reason_code")
        if outcome["reason_code"] != document_reason:
            _fail(f"LEDGER_REASON_MISMATCH:{need['need_id']}")
        validation_label = "LEDGER_READ_RESPONSE_VALID"
        input_mode = "LEDGER_READ_RESPONSE"
        read_request_id = document.get("request_id")
        basis_sha256 = document.get("receipt", {}).get("basis_sha256")
    else:
        if status != "OK" or outcome["reason_code"] is not None:
            _fail(f"CONTRACT_OBJECT_STATUS_MUST_BE_OK:{need['need_id']}")
        if raw_validation not in {
            "STRUCTURAL_VALID",
            "STRUCTURAL_VALID_OWNER_UNRESOLVED",
        }:
            _fail(f"CONTRACT_OBJECT_VALIDATION_RESULT_INVALID:{need['need_id']}")
        validation_label = str(raw_validation)
        input_mode = "CALLER_PROVIDED_VALIDATED_OBJECT"
        read_request_id = None
        basis_sha256 = None

    author_id, project_id = _scope_from_source_document(source_contract, document)
    if (author_id, project_id) != (scope["author_id"], scope["project_id"]):
        _fail(f"SOURCE_SCOPE_MISMATCH:{need['need_id']}")

    material_text = outcome["material_text"]
    if status == "OK":
        if not isinstance(material_text, str) or not material_text.strip():
            _fail(f"OK_SOURCE_MATERIAL_REQUIRED:{need['need_id']}")
    elif material_text is not None:
        _fail(f"NON_OK_SOURCE_MATERIAL_FORBIDDEN:{need['need_id']}")

    return {
        "source_contract": source_contract,
        "source_contract_version": need["source_contract_version"],
        "validator_id": validator_id,
        "validation_result": validation_label,
        "failure_code": None,
        "document_sha256": sha256_json(document),
        "input_mode": input_mode,
        "read_request_id": read_request_id,
        "basis_sha256": basis_sha256,
    }


def _failed_source_validation(
    need: Mapping[str, Any],
    outcome: Mapping[str, Any],
    failure_code: str,
) -> dict[str, Any]:
    document = outcome.get("source_document")
    source_contract = need["source_contract"]
    is_ledger = source_contract == "LEDGER_READ_TOOL_CONTRACT"
    receipt = document.get("receipt") if isinstance(document, Mapping) else None
    return {
        "source_contract": source_contract,
        "source_contract_version": need["source_contract_version"],
        "validator_id": outcome["validator_id"],
        "validation_result": "SOURCE_VALIDATION_FAILED",
        "failure_code": failure_code,
        "document_sha256": sha256_json(document),
        "input_mode": (
            "LEDGER_READ_RESPONSE"
            if is_ledger
            else "CALLER_PROVIDED_VALIDATED_OBJECT"
        ),
        "read_request_id": document.get("request_id") if is_ledger else None,
        "basis_sha256": (
            receipt.get("basis_sha256")
            if is_ledger and isinstance(receipt, Mapping)
            else None
        ),
    }


def _validate_outcomes(
    request: Mapping[str, Any],
    plan: Mapping[str, Any],
    source_outcomes: Any,
    validator_registry: Mapping[str, Callable[[Any], Any]],
) -> list[dict[str, Any]]:
    if not isinstance(source_outcomes, list):
        _fail("SOURCE_OUTCOMES_MUST_BE_LIST")
    step_ids = [step["need_id"] for step in plan["steps"]]
    outcome_ids: list[str] = []
    checked: list[dict[str, Any]] = []
    needs = _need_map(request)
    for index, raw in enumerate(source_outcomes):
        if not isinstance(raw, Mapping) or set(raw) != SOURCE_OUTCOME_FIELDS:
            _fail(f"SOURCE_OUTCOME_FIELDS_INVALID:{index}")
        outcome = copy.deepcopy(dict(raw))
        need_id = outcome["need_id"]
        if need_id not in needs:
            _fail(f"SOURCE_OUTCOME_NEED_UNKNOWN:{need_id}")
        if need_id in outcome_ids:
            _fail(f"SOURCE_OUTCOME_DUPLICATE:{need_id}")
        outcome_ids.append(need_id)
        try:
            validation = _validation_result(
                needs[need_id],
                outcome,
                request["scope"],
                request["basis_mode"],
                validator_registry,
            )
        except C9RetrievalError as exc:
            failure_code = str(exc).split(":", maxsplit=1)[0]
            if failure_code in {
                "SOURCE_VALIDATOR_NOT_REGISTERED",
                "SOURCE_DOCUMENT_OR_VALIDATOR_MISSING",
            } or not isinstance(outcome.get("source_document"), Mapping):
                raise
            if failure_code == "SOURCE_SCOPE_MISMATCH":
                reason_code = "UNAUTHORIZED"
            elif outcome.get("reason_code") in FATAL_REASON_CODES:
                reason_code = outcome["reason_code"]
            else:
                reason_code = "SOURCE_CORRUPTED"
            validation = _failed_source_validation(
                needs[need_id],
                outcome,
                failure_code,
            )
            outcome["source_status"] = "ERROR"
            outcome["reason_code"] = reason_code
            outcome["material_text"] = None
        outcome["source_validation"] = validation
        checked.append(outcome)
    if outcome_ids != step_ids:
        _fail("SOURCE_OUTCOMES_NOT_EXACT_PLAN_ORDER")
    return checked


def _outcome_reason(outcome: Mapping[str, Any]) -> str:
    validation = outcome["source_validation"]
    if validation and validation["validation_result"] == "STRUCTURAL_VALID_OWNER_UNRESOLVED":
        return "OWNER_UNRESOLVED"
    return outcome["reason_code"] or outcome["source_status"]


def _outcome_is_usable(outcome: Mapping[str, Any]) -> bool:
    validation = outcome["source_validation"]
    return (
        outcome["source_status"] == "OK"
        and validation is not None
        and validation["validation_result"]
        not in {
            "STRUCTURAL_VALID_OWNER_UNRESOLVED",
            "SOURCE_VALIDATION_FAILED",
        }
    )


def _outcome_is_fatal(outcome: Mapping[str, Any]) -> bool:
    if outcome["source_status"] == "ERROR":
        return True
    return _outcome_reason(outcome) in FATAL_REASON_CODES


def _packer_request(
    request: Mapping[str, Any],
    outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    needs = _need_map(request)
    materials = []
    for outcome in outcomes:
        if not _outcome_is_usable(outcome):
            continue
        need = needs[outcome["need_id"]]
        materials.append(
            {
                "id": need["need_id"],
                "estimated_tokens": need["estimated_tokens"],
                "actuality_class": need["actuality_class"],
                "obligation_tier": need["obligation_tier"],
                "selection_rank": need["selection_rank"],
                "task_relation": need["task_relation"],
                "recall_disposition": need["recall_disposition"],
                "recall_handle": need["recall_handle"],
                "unresolved_reason": None,
            }
        )
    return {
        "task_id": request["scope"]["task_id"],
        "task_actuality_scope": request["task_actuality_scope"],
        "budget_tokens": request["budget"]["limit_tokens"],
        "token_estimator_ref": request["budget"]["estimator_ref"],
        "candidate_materials": materials,
    }


def _source_validation_copy(outcome: Mapping[str, Any]) -> dict[str, Any]:
    validation = outcome["source_validation"]
    if validation is None:
        _fail(f"SOURCE_VALIDATION_REQUIRED:{outcome['need_id']}")
    return copy.deepcopy(validation)


def _build_loaded(
    load_ids: list[str],
    why_loaded: Mapping[str, str],
    request: Mapping[str, Any],
    outcomes_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    needs = _need_map(request)
    loaded = []
    for need_id in load_ids:
        need = needs[need_id]
        outcome = outcomes_by_id[need_id]
        text = outcome["material_text"]
        loaded.append(
            {
                "need_id": need_id,
                "object_ref": need["object_ref"],
                "evidence_layer": need["evidence_layer"],
                "material_text": text,
                "material_sha256": _sha256_text(text),
                "why_loaded": why_loaded[need_id],
                "source_validation": _source_validation_copy(outcome),
                "recall_disposition": need["recall_disposition"],
                "recall_handle": need["recall_handle"],
            }
        )
    return loaded


def _build_omitted(
    rows: list[dict[str, Any]],
    request: Mapping[str, Any],
    outcomes_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    needs = _need_map(request)
    return [
        {
            "need_id": row["id"],
            "object_ref": needs[row["id"]]["object_ref"],
            "reason": row["reason"],
            "source_validation": _source_validation_copy(outcomes_by_id[row["id"]]),
            "recall_disposition": row["recall_disposition"],
            "recall_handle": row["recall_handle"],
        }
        for row in rows
    ]


def _build_outstanding(
    request: Mapping[str, Any],
    outcomes: list[dict[str, Any]],
    *,
    stop_reason: str | None = None,
) -> list[dict[str, Any]]:
    needs = _need_map(request)
    rows = []
    for outcome in outcomes:
        if _outcome_is_usable(outcome) and stop_reason is None:
            continue
        if _outcome_is_usable(outcome):
            category = "NOT_DELIVERED"
            reason = stop_reason
            fatal = True
        else:
            reason = _outcome_reason(outcome)
            fatal = _outcome_is_fatal(outcome)
            if outcome["source_status"] == "NOT_ATTEMPTED":
                category = "NOT_READ"
            elif reason == "OWNER_UNRESOLVED":
                category = "UNRESOLVED"
            else:
                category = "FAILED"
        rows.append(
            {
                "need_id": outcome["need_id"],
                "object_ref": needs[outcome["need_id"]]["object_ref"],
                "obligation_tier": needs[outcome["need_id"]]["obligation_tier"],
                "category": category,
                "reason_code": reason,
                "fatal": fatal,
                "source_validation": copy.deepcopy(outcome["source_validation"]),
            }
        )
    return rows


def _warnings(
    omitted: list[dict[str, Any]],
    outstanding: list[dict[str, Any]],
) -> list[str]:
    warnings = []
    for row in outstanding:
        prefix = "MISSING_REQUIRED" if row["obligation_tier"] == "HARD" else "SOURCE_GAP"
        warnings.append(f"{prefix}:{row['need_id']}:{row['reason_code']}")
    for row in omitted:
        warnings.append(f"OMITTED:{row['need_id']}:{row['reason']}")
    return warnings


def _seal_package(
    loaded: list[dict[str, Any]],
    omitted: list[dict[str, Any]],
    outstanding: list[dict[str, Any]],
) -> dict[str, Any]:
    return _seal(
        {
            "loaded": loaded,
            "omitted": omitted,
            "outstanding": outstanding,
        },
        "package_sha256",
    )


def _build_trace_log(
    request: Mapping[str, Any],
    plan: Mapping[str, Any],
    outcomes: list[dict[str, Any]],
    loaded: list[dict[str, Any]],
    omitted: list[dict[str, Any]],
    outstanding: list[dict[str, Any]],
) -> dict[str, Any]:
    loaded_ids = {row["need_id"] for row in loaded}
    loaded_map = {row["need_id"]: row for row in loaded}
    omitted_map = {row["need_id"]: row for row in omitted}
    outstanding_map = {row["need_id"]: row for row in outstanding}
    outcomes_by_id = {row["need_id"]: row for row in outcomes}
    events = []
    for step in plan["steps"]:
        need_id = step["need_id"]
        outcome = outcomes_by_id[need_id]
        if need_id in loaded_ids:
            disposition = "LOADED"
            reason = None
        elif need_id in omitted_map:
            disposition = "OMITTED"
            reason = omitted_map[need_id]["reason"]
        else:
            disposition = outstanding_map[need_id]["category"]
            reason = outstanding_map[need_id]["reason_code"]
        validation = outcome["source_validation"]
        events.append(
            {
                "order": step["order"],
                "need_id": need_id,
                "source_status": outcome["source_status"],
                "reason_code": reason,
                "why_loaded": (
                    loaded_map[need_id]["why_loaded"]
                    if need_id in loaded_map
                    else None
                ),
                "validation_result": (
                    validation["validation_result"] if validation else None
                ),
                "final_disposition": disposition,
                "expansion_trigger": step["expansion_trigger"],
            }
        )
    return _seal(
        {
            "consumer_id": request["scope"]["consumer_id"],
            "events": events,
        },
        "trace_log_sha256",
    )


def _build_short_receipt(
    status: str,
    request: Mapping[str, Any],
    package: Mapping[str, Any],
    trace_log: Mapping[str, Any],
) -> dict[str, Any]:
    needs = _need_map(request)
    loaded_ids = {row["need_id"] for row in package["loaded"]}
    hard_ids = [
        need["need_id"]
        for need in request["source_needs"]
        if need["obligation_tier"] == "HARD"
    ]
    missing_hard = [need_id for need_id in hard_ids if need_id not in loaded_ids]
    layers = []
    for row in package["loaded"]:
        layer = row["evidence_layer"]
        if layer not in layers:
            layers.append(layer)
    warnings = _warnings(package["omitted"], package["outstanding"])
    source_versions_used = []
    seen_versions: set[tuple[str, str]] = set()
    for row in package["loaded"]:
        validation = row["source_validation"]
        key = (
            validation["source_contract"],
            validation["source_contract_version"],
        )
        if key not in seen_versions:
            seen_versions.add(key)
            source_versions_used.append(
                {
                    "source_contract": key[0],
                    "source_contract_version": key[1],
                }
            )
    receipt = {
        "status": status,
        "scope": copy.deepcopy(request["scope"]),
        "required_total": len(hard_ids),
        "required_satisfied": len(hard_ids) - len(missing_hard),
        "required_missing": len(missing_hard),
        "loaded_count": len(package["loaded"]),
        "omitted_count": len(package["omitted"]),
        "outstanding_count": len(package["outstanding"]),
        "evidence_layers_loaded": layers,
        "important_missing_need_ids": missing_hard,
        "warnings": warnings,
        "source_versions_used": source_versions_used,
        "package_sha256": package["package_sha256"],
        "trace_log_sha256": trace_log["trace_log_sha256"],
    }
    if set(loaded_ids) - set(needs):
        _fail("SHORT_RECEIPT_UNKNOWN_LOADED_NEED")
    return _seal(receipt, "receipt_sha256")


def _result_status(
    request: Mapping[str, Any],
    outcomes: list[dict[str, Any]],
) -> tuple[str, str | None]:
    needs = _need_map(request)
    fatal = next((row for row in outcomes if _outcome_is_fatal(row)), None)
    if fatal is not None:
        return "STOPPED", _outcome_reason(fatal)
    missing_hard = [
        row
        for row in outcomes
        if needs[row["need_id"]]["obligation_tier"] == "HARD"
        and not _outcome_is_usable(row)
    ]
    if missing_hard:
        behavior = request["gap_policy"]["missing_required_behavior"]
        if behavior == "BLOCK":
            return "STOPPED", "MISSING_REQUIRED_BLOCKED"
        return "READY_WITH_GAPS", None
    return "READY", None


def _replay_status(request: Mapping[str, Any]) -> str:
    if request["basis_mode"] == "pinned_manifest":
        return "REPLAYABLE_PINNED"
    return "AUDITABLE_CURRENT_NOT_REPLAYABLE"


def compile_result(
    request: Mapping[str, Any],
    plan: Mapping[str, Any],
    source_outcomes: list[dict[str, Any]],
    validator_registry: Mapping[str, Callable[[Any], Any]],
) -> dict[str, Any]:
    checked_request = validate_request(request)
    checked_plan = validate_plan(plan, checked_request)
    outcomes = _validate_outcomes(
        checked_request,
        checked_plan,
        source_outcomes,
        validator_registry,
    )
    status, stop_reason = _result_status(checked_request, outcomes)
    usable_count = sum(_outcome_is_usable(row) for row in outcomes)
    packer_result: dict[str, Any] | None = None

    if status != "STOPPED" and usable_count == 0:
        status = "STOPPED"
        stop_reason = "NO_USABLE_MATERIALS"
    if status != "STOPPED":
        packer_result = packer.pack_context(_packer_request(checked_request, outcomes))
        if packer_result["decision_state"] != "READY":
            status = "STOPPED"
            errors = packer_result["errors"]
            stop_reason = errors[0]["code"] if errors else packer_result["decision_state"]

    outcomes_by_id = {row["need_id"]: row for row in outcomes}
    if status == "STOPPED":
        loaded: list[dict[str, Any]] = []
        omitted: list[dict[str, Any]] = []
        outstanding = _build_outstanding(
            checked_request,
            outcomes,
            stop_reason=stop_reason or "RUN_STOPPED",
        )
    else:
        assert packer_result is not None
        loaded = _build_loaded(
            packer_result["load_ids"],
            packer_result["why_loaded"],
            checked_request,
            outcomes_by_id,
        )
        omitted = _build_omitted(
            packer_result["omitted"],
            checked_request,
            outcomes_by_id,
        )
        outstanding = _build_outstanding(checked_request, outcomes)

    package = _seal_package(loaded, omitted, outstanding)
    trace_log = _build_trace_log(
        checked_request,
        checked_plan,
        outcomes,
        loaded,
        omitted,
        outstanding,
    )
    short_receipt = _build_short_receipt(
        status,
        checked_request,
        package,
        trace_log,
    )
    result = {
        "contract": "C9_RETRIEVAL_RESULT",
        "version": VERSION,
        "scope": copy.deepcopy(checked_request["scope"]),
        "basis_mode": checked_request["basis_mode"],
        "request_sha256": checked_request["request_sha256"],
        "plan_sha256": checked_plan["plan_sha256"],
        "status": status,
        "replay_status": _replay_status(checked_request),
        "material_package": package,
        "short_receipt": short_receipt,
        "trace_log": trace_log,
    }
    sealed = _seal(result, "run_sha256")
    validate_result(sealed, checked_request, checked_plan)
    return sealed


def _accounting_map(result: Mapping[str, Any]) -> dict[str, tuple[str, Mapping[str, Any]]]:
    package = result["material_package"]
    accounting: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for label in ("loaded", "omitted", "outstanding"):
        for row in package[label]:
            need_id = row["need_id"]
            if need_id in accounting:
                _fail(f"RESULT_NEED_OVERLAP:{need_id}")
            accounting[need_id] = (label, row)
    return accounting


def _packer_request_for_accounted_materials(
    request: Mapping[str, Any],
    accounted_need_ids: set[str],
) -> dict[str, Any]:
    materials = []
    for need in request["source_needs"]:
        if need["need_id"] not in accounted_need_ids:
            continue
        materials.append(
            {
                "id": need["need_id"],
                "estimated_tokens": need["estimated_tokens"],
                "actuality_class": need["actuality_class"],
                "obligation_tier": need["obligation_tier"],
                "selection_rank": need["selection_rank"],
                "task_relation": need["task_relation"],
                "recall_disposition": need["recall_disposition"],
                "recall_handle": need["recall_handle"],
                "unresolved_reason": None,
            }
        )
    return {
        "task_id": request["scope"]["task_id"],
        "task_actuality_scope": request["task_actuality_scope"],
        "budget_tokens": request["budget"]["limit_tokens"],
        "token_estimator_ref": request["budget"]["estimator_ref"],
        "candidate_materials": materials,
    }


def validate_result(
    value: Any,
    request: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_schema(value)
    if value.get("contract") != "C9_RETRIEVAL_RESULT":
        _fail("RESULT_CONTRACT_REQUIRED")
    checked_request = validate_request(request)
    checked_plan = validate_plan(plan, checked_request)
    result = copy.deepcopy(value)
    if (
        result["scope"] != checked_request["scope"]
        or result["basis_mode"] != checked_request["basis_mode"]
        or result["request_sha256"] != checked_request["request_sha256"]
        or result["plan_sha256"] != checked_plan["plan_sha256"]
    ):
        _fail("RESULT_REQUEST_PLAN_BINDING_MISMATCH")
    _verify_seal(
        result["material_package"],
        "package_sha256",
        "PACKAGE_SHA256_MISMATCH",
    )
    _verify_seal(
        result["trace_log"],
        "trace_log_sha256",
        "TRACE_LOG_SHA256_MISMATCH",
    )
    _verify_seal(
        result["short_receipt"],
        "receipt_sha256",
        "RECEIPT_SHA256_MISMATCH",
    )
    _verify_seal(result, "run_sha256", "RUN_SHA256_MISMATCH")

    accounting = _accounting_map(result)
    step_ids = [step["need_id"] for step in checked_plan["steps"]]
    if set(accounting) != set(step_ids):
        _fail("RESULT_NEEDS_NOT_EXACT_PLAN")
    needs = _need_map(checked_request)
    for need_id, (label, row) in accounting.items():
        need = needs[need_id]
        if row["object_ref"] != need["object_ref"]:
            _fail(f"RESULT_OBJECT_REF_MISMATCH:{need_id}")
        if label == "loaded":
            if row["evidence_layer"] != need["evidence_layer"]:
                _fail(f"LOADED_LAYER_MISMATCH:{need_id}")
            if row["material_sha256"] != _sha256_text(row["material_text"]):
                _fail(f"LOADED_MATERIAL_SHA256_MISMATCH:{need_id}")
            if not row["why_loaded"].strip():
                _fail(f"LOADED_WHY_MISSING:{need_id}")
            if (
                row["recall_disposition"] != need["recall_disposition"]
                or row["recall_handle"] != need["recall_handle"]
            ):
                _fail(f"LOADED_RECALL_MISMATCH:{need_id}")
            validation = row["source_validation"]
            if (
                validation["source_contract"] != need["source_contract"]
                or validation["source_contract_version"]
                != need["source_contract_version"]
                or validation["validation_result"]
                in {
                    "STRUCTURAL_VALID_OWNER_UNRESOLVED",
                    "SOURCE_VALIDATION_FAILED",
                }
            ):
                _fail(f"LOADED_SOURCE_VALIDATION_MISMATCH:{need_id}")
        elif label == "omitted":
            validation = row["source_validation"]
            if (
                validation["source_contract"] != need["source_contract"]
                or validation["source_contract_version"]
                != need["source_contract_version"]
                or validation["validation_result"]
                in {
                    "STRUCTURAL_VALID_OWNER_UNRESOLVED",
                    "SOURCE_VALIDATION_FAILED",
                }
            ):
                _fail(f"OMITTED_SOURCE_VALIDATION_MISMATCH:{need_id}")
        elif label == "outstanding":
            if row["obligation_tier"] != need["obligation_tier"]:
                _fail(f"OUTSTANDING_OBLIGATION_MISMATCH:{need_id}")

    package = result["material_package"]
    hard_ids = [
        need["need_id"]
        for need in checked_request["source_needs"]
        if need["obligation_tier"] == "HARD"
    ]
    loaded_ids = {row["need_id"] for row in package["loaded"]}
    missing_hard = [need_id for need_id in hard_ids if need_id not in loaded_ids]
    fatal_outstanding = any(row["fatal"] for row in package["outstanding"])
    status = result["status"]
    if status == "READY" and (missing_hard or fatal_outstanding):
        _fail("READY_STATUS_CONTRADICTS_GAPS")
    if status == "READY_WITH_GAPS" and (not missing_hard or fatal_outstanding):
        _fail("READY_WITH_GAPS_STATUS_CONTRADICTION")
    if status == "STOPPED" and (package["loaded"] or package["omitted"]):
        _fail("STOPPED_RESULT_MUST_NOT_DELIVER_MATERIAL")
    if status != "STOPPED":
        packer_need_ids = {
            row["need_id"] for row in package["loaded"] + package["omitted"]
        }
        expected_pack = packer.pack_context(
            _packer_request_for_accounted_materials(
                checked_request,
                packer_need_ids,
            )
        )
        if expected_pack["decision_state"] != "READY":
            _fail("RESULT_PACKER_DECISION_NOT_READY")
        if [row["need_id"] for row in package["loaded"]] != expected_pack["load_ids"]:
            _fail("RESULT_LOAD_ORDER_NOT_PACKER_OUTPUT")
        expected_omitted = _build_omitted(
            expected_pack["omitted"],
            checked_request,
            {row["need_id"]: {"source_validation": row["source_validation"]} for row in package["omitted"]},
        )
        if package["omitted"] != expected_omitted:
            _fail("RESULT_OMISSIONS_NOT_PACKER_OUTPUT")
        why_loaded = {
            row["need_id"]: row["why_loaded"] for row in package["loaded"]
        }
        if why_loaded != expected_pack["why_loaded"]:
            _fail("RESULT_WHY_LOADED_NOT_PACKER_OUTPUT")

    expected_replay = _replay_status(checked_request)
    if result["replay_status"] != expected_replay:
        _fail("REPLAY_STATUS_MISMATCH")

    trace = result["trace_log"]
    events = trace["events"]
    if trace["consumer_id"] != checked_request["scope"]["consumer_id"]:
        _fail("TRACE_CONSUMER_MISMATCH")
    if [event["need_id"] for event in events] != step_ids:
        _fail("TRACE_EVENTS_NOT_EXACT_PLAN_ORDER")
    for step, event in zip(checked_plan["steps"], events, strict=True):
        label = accounting[event["need_id"]][0]
        if label == "loaded":
            expected_disposition = "LOADED"
        elif label == "omitted":
            expected_disposition = "OMITTED"
        else:
            expected_disposition = accounting[event["need_id"]][1]["category"]
        if (
            event["order"] != step["order"]
            or event["expansion_trigger"] != step["expansion_trigger"]
            or event["final_disposition"] != expected_disposition
            or event["why_loaded"]
            != (
                accounting[event["need_id"]][1]["why_loaded"]
                if label == "loaded"
                else None
            )
        ):
            _fail(f"TRACE_EVENT_MISMATCH:{event['need_id']}")

    receipt = result["short_receipt"]
    expected_receipt = _build_short_receipt(status, checked_request, package, trace)
    if receipt != expected_receipt:
        _fail("SHORT_RECEIPT_NOT_MECHANICAL_PROJECTION")
    return result


__all__ = [
    "C9RetrievalError",
    "VERSION",
    "canonical_bytes",
    "compile_result",
    "prepare_plan",
    "seal_request",
    "sha256_json",
    "validate_plan",
    "validate_request",
    "validate_result",
]
