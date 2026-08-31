"""B-05 r03.5 immutable records and pure route builders.

This module owns only B-05 output envelopes.  Direct-upstream originals are
validated by their bounded reader adapters; SourceSlice bytes stay opaque.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

CONTRACT_VERSION = "r03.5-candidate"
CANDIDATE_SCHEMA_ID = "novel-fact-extraction-v2.1"
DOCUMENT_IDENTITY = "CCZ57-M3-B05-R03.5-CANDIDATE"
IMMUTABLE_CONTRACT = "M3_IMMUTABLE_RECORD"
RECORD_REF_CONTRACT = "M3_RECORD_REF"
SOURCE_MODULE = "M3"
FIXTURE_ACCESS = "POLICY_FIXTURE_READ_ONLY"
RUN_ACCESS = "RUN_INTERNAL_READ_ONLY"
RETENTION_CLASS = "CORE_IMMUTABLE_AUDIT"
WRITE_SET_PREFIX = "work/ccz57_m3_b05_patch_route_r03_5/"

OUTPUT_TYPES = {
    "M3_VALIDATOR_IDENTITY_RECEIPT",
    "M3_PATCH_VALIDATION_RECEIPT",
    "M3_PATCH_ROUTE_RECEIPT",
    "M3_PATCH_LIFECYCLE_RECEIPT",
}
WRITER_MAP = {
    "M3_VALIDATOR_IDENTITY_RECEIPT": "ValidatorIdentityRegistry",
    "M3_PATCH_VALIDATION_RECEIPT": "B05RouteBundlePublisher",
    "M3_PATCH_ROUTE_RECEIPT": "B05RouteBundlePublisher",
    "M3_PATCH_LIFECYCLE_RECEIPT": "B05RouteBundlePublisher",
}
BUILDER_MAP = {
    "M3_PATCH_VALIDATION_RECEIPT": "PatchValidator",
    "M3_PATCH_ROUTE_RECEIPT": "PatchRouteDecider",
    "M3_PATCH_LIFECYCLE_RECEIPT": "PatchLifecycleBuilder",
}
PROJECTOR_MAP = {"PatchRouteAggregateProjection": "PatchAggregateProjector"}

ENVELOPE_KEYS = {
    "contract",
    "contract_version",
    "record_type",
    "record_id",
    "record_version",
    "record_contract_version",
    "record_hash",
    "source_module",
    "access",
    "retention_class",
    "created_at",
    "payload",
}
RECORD_REF_KEYS = {
    "contract",
    "contract_version",
    "record_type",
    "record_id",
    "record_version",
    "record_contract_version",
    "record_hash",
    "access",
    "source_module",
}
PAYLOAD_KEYS = {
    "M3_VALIDATOR_IDENTITY_RECEIPT": {
        "validator_name",
        "validator_version",
        "implementation_identity",
        "supported_contract_version",
        "supported_candidate_schema_ids",
        "supported_policy_contract",
        "supported_policy_versions",
        "runtime_capabilities",
    },
    "M3_PATCH_VALIDATION_RECEIPT": {
        "evaluation_key",
        "operation_id",
        "evaluation_input_hash",
        "validator_identity_ref",
        "validation_policy_ref",
        "active_policy_selection_ref",
        "active_policy_selection_hash",
        "input_binding",
        "dependency_proof",
        "route_unit_proofs",
        "causal_support_mappings",
        "runtime_counters",
    },
    "M3_PATCH_ROUTE_RECEIPT": {
        "evaluation_key",
        "evaluation_input_hash",
        "route_series_id",
        "route_generation",
        "validator_identity_ref",
        "validation_policy_ref",
        "active_policy_selection_ref",
        "active_policy_selection_hash",
        "validation_receipt_ref",
        "binding_header",
        "binding_header_hash",
        "route_units",
        "causal_hint_routes",
    },
    "M3_PATCH_LIFECYCLE_RECEIPT": {
        "route_series_id",
        "lifecycle_sequence",
        "subject_route_receipt_ref",
        "event",
        "effective_at",
        "reason_code",
        "prior_route_receipt_ref_or_null",
        "replacement_route_receipt_ref_or_null",
        "material_delta_refs",
        "evaluation_key",
    },
}
INPUT_BINDING_KEYS = {
    "patch_proposal_ref",
    "protection_set_ref",
    "causal_hint_proposal_refs",
    "base_candidate_version_ref",
    "base_version_payload_hash",
    "candidate_schema_id",
    "chapter_revision_ref",
    "seg",
    "segment_index_ref",
    "candidate_pointer_snapshot_ref_or_null",
    "live_pointer_binding",
    "live_pointer_binding_hash",
    "b02_scope_binding",
    "b02_scope_snapshot_hash",
    "non_content_gate_bindings",
    "non_content_gate_snapshot_hash",
    "prior_active_route_receipt_ref_or_null",
    "prior_lifecycle_head_ref_or_null",
}
DEPENDENCY_PROOF_KEYS = {
    "group_catalog",
    "dependency_edges",
    "unknown_dependency_tokens",
    "route_unit_partition",
    "partition_hash",
}
ROUTE_UNIT_PROOF_KEYS = {
    "route_unit_id",
    "atomic_group_bindings",
    "logical_read_set",
    "logical_write_set",
    "lineage_set",
    "support_refs",
    "validation_context_refs",
    "effective_protection_proof",
    "canonical_apply_result_hash",
    "exchange_order_checks",
    "candidate_structure_check_results",
    "check_results",
    "unit_proof_hash",
}
ROUTE_ENTRY_KEYS = {
    "route_unit_id",
    "atomic_group_bindings",
    "unit_proof_hash",
    "route",
    "reason_codes",
    "expand_check_target_or_null",
    "defer_gate_refs",
}
BINDING_HEADER_KEYS = {
    "patch_proposal_ref",
    "protection_set_ref",
    "base_candidate_version_ref",
    "candidate_schema_id",
    "chapter_revision_ref",
    "seg",
    "segment_index_ref",
    "live_pointer_binding_hash",
    "b02_scope_snapshot_hash",
    "non_content_gate_snapshot_hash",
}
CAUSAL_ROUTE_ENTRY_KEYS = {
    "causal_hint_proposal_ref",
    "mapping_proof_hash",
    "supporting_route_unit_ids",
    "route",
    "reason_codes",
    "expand_check_target_or_null",
}
ROUTES = {"ALLOW_FOR_B06", "REJECT", "DEFER", "EXPAND_CHECK"}
CAUSAL_ROUTES = {"ROUTE_TO_B09", "REJECT", "DEFER", "EXPAND_CHECK"}
LIFECYCLE_EVENTS = {
    "ROUTES_FROZEN",
    "SUPERSEDED",
    "REOPENED_WITH_NEW_MATERIAL",
}
RUNTIME_COUNTER_KEYS = {
    "real_model_api_calls",
    "network_calls",
    "real_novel_reads",
    "text_slice_reads",
    "new_fact_generations",
    "patch_mutations",
    "candidate_version_writes",
    "pointer_writes",
    "formal_fact_writes",
    "ledger_truth_writes",
    "b09_sidecar_writes",
}
FORBIDDEN_PVR_KEYS = {
    "route",
    "route_outcome",
    "ALLOW_FOR_B06",
    "REJECT",
    "DEFER",
    "EXPAND_CHECK",
    "ROUTE_TO_B09",
}
REASON_CODES = {
    "ALLOW_FOR_B06": {"MECHANICAL_PROOF_COMPLETE"},
    "REJECT": {
        "BASE_NOT_CURRENT",
        "SELECTED_DIAGNOSTIC_TERMINAL",
        "CONTRACT_REFERENCE_OR_SCOPE_INVALID",
        "PATCH_SCOPE_EXCEEDED",
        "ROUTE_UNIT_TARGET_CONFLICT",
        "EXPECTED_OLD_ITEM_HASH_MISMATCH",
        "PROTECTION_REGRESSION",
        "CANDIDATE_STRUCTURE_INVALID",
        "FORBIDDEN_B05_RESPONSIBILITY_REQUESTED",
    },
    "EXPAND_CHECK": {
        "DEPENDENCY_ENDPOINT_UNKNOWN",
        "SEMANTIC_IMPACT_UNKNOWN",
        "EVIDENCE_SUPPORT_AMBIGUOUS",
        "CAUSAL_SUPPORT_MAPPING_AMBIGUOUS",
        "ADJACENT_SEGMENT_CHECK_REQUIRED",
    },
    "DEFER": {"DECLARED_NON_CONTENT_GATE_CLOSED"},
}

DEPENDENCY_EDGE_TYPES = {
    "WRITE_WRITE_OVERLAP",
    "WRITE_READ_OVERLAP",
    "TARGET_OR_LINEAGE_DEPENDENCY",
    "SHARED_SUPPORT_AFFECTS_VALIDATION",
    "OPERATION_RESULT_DEPENDENCY",
    "PROTECTION_INTERACTION",
    "NON_COMMUTATIVE_APPLICATION",
}
DEPENDENCY_EVIDENCE_TOKEN_TYPES = {
    "EXACT_RECORD_REF",
    "LINEAGE_LOCATOR",
    "EVIDENCE_LOCATOR",
    "JSON_POINTER",
    "OPERATION_FINGERPRINT",
    "STABLE_CHECK_CODE",
}
UNKNOWN_DEPENDENCY_REASON_CODES = {
    "DEPENDENCY_ENDPOINT_UNKNOWN",
    "SEMANTIC_IMPACT_UNKNOWN",
    "EVIDENCE_SUPPORT_AMBIGUOUS",
    "ADJACENT_SEGMENT_CHECK_REQUIRED",
}

_WRITER_TOKENS = {record_type: object() for record_type in OUTPUT_TYPES}


class B05ContractError(ValueError):
    """Stable machine-readable failure used by the offline shell."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def fail(code: str, detail: str = "") -> None:
    raise B05ContractError(code, detail)


def guard_write_path(relative_path: str) -> None:
    if not isinstance(relative_path, str) or not relative_path.startswith(
        WRITE_SET_PREFIX
    ):
        fail("B05_WRITE_SET_ESCAPE", str(relative_path))


def guard_runtime_event(event: str) -> None:
    forbidden = {
        "model_api",
        "network",
        "real_novel_read",
        "text_slice_read",
        "new_fact_generation",
        "patch_mutation",
        "candidate_version_write",
        "pointer_write",
        "formal_fact_write",
        "ledger_truth_write",
        "b09_sidecar_write",
        "subprocess",
    }
    if event in forbidden:
        fail("B05_FORBIDDEN_RUNTIME_EVENT", event)


_SOURCE_BOUND_STRING_KEYS = {
    "content",
    "evidence",
    "fact",
    "responsibility_text",
    "speaker",
    "status",
}


def normalize(value: Any, *, preserve_string_value: bool = False) -> Any:
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        fail("B05_CANONICAL_VALUE_INVALID", "floating-point values are forbidden")
    if isinstance(value, str):
        return value if preserve_string_value else unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [
            normalize(item, preserve_string_value=preserve_string_value)
            for item in value
        ]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                fail("B05_CANONICAL_KEY_INVALID")
            key = unicodedata.normalize("NFC", key)
            if key in result:
                fail("B05_CANONICAL_DUPLICATE_KEY", key)
            result[key] = normalize(
                item,
                preserve_string_value=(
                    preserve_string_value or key in _SOURCE_BOUND_STRING_KEYS
                ),
            )
        return {key: result[key] for key in sorted(result, key=lambda x: x.encode())}
    fail("B05_CANONICAL_VALUE_INVALID", type(value).__name__)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        normalize(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def exact_keys(value: Any, expected: set[str], code: str) -> None:
    if not isinstance(value, dict):
        fail(code, "object required")
    actual = set(value)
    if actual != expected:
        fail(
            code,
            f"missing={sorted(expected - actual)}; extra={sorted(actual - expected)}",
        )


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _parse_utc(value: Any, code: str = "B05_TIMESTAMP_INVALID") -> None:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is None
    ):
        fail(code)
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        fail(code, str(error))


def validate_record_ref(value: Any, *, expected_type: str | None = None) -> None:
    exact_keys(value, RECORD_REF_KEYS, "B05_RECORD_REF_SHAPE_INVALID")
    if value["contract"] != RECORD_REF_CONTRACT:
        fail("B05_RECORD_REF_INVALID", "contract")
    if value["contract_version"] != CONTRACT_VERSION:
        fail("B05_RECORD_REF_INVALID", "contract_version")
    if value["record_contract_version"] != CONTRACT_VERSION:
        fail("B05_RECORD_REF_INVALID", "record_contract_version")
    if expected_type is not None and value["record_type"] != expected_type:
        fail("B05_RECORD_REF_TYPE_INVALID", str(value["record_type"]))
    if not isinstance(value["record_id"], str) or not value["record_id"]:
        fail("B05_RECORD_REF_INVALID", "record_id")
    if not isinstance(value["record_version"], int) or value["record_version"] < 1:
        fail("B05_RECORD_REF_INVALID", "record_version")
    if not _is_sha(value["record_hash"]):
        fail("B05_RECORD_REF_INVALID", "record_hash")
    if value["access"] not in {FIXTURE_ACCESS, RUN_ACCESS}:
        fail("B05_RECORD_REF_INVALID", "access")
    if not isinstance(value["source_module"], str) or not value["source_module"]:
        fail("B05_RECORD_REF_INVALID", "source_module")


def validate_immutable_record(record: Any, *, expected_type: str | None = None) -> None:
    exact_keys(record, ENVELOPE_KEYS, "B05_IMMUTABLE_SHAPE_INVALID")
    if record["contract"] != IMMUTABLE_CONTRACT:
        fail("B05_IMMUTABLE_INVALID", "contract")
    if record["contract_version"] != CONTRACT_VERSION:
        fail("B05_IMMUTABLE_INVALID", "contract_version")
    if record["record_contract_version"] != CONTRACT_VERSION:
        fail("B05_IMMUTABLE_INVALID", "record_contract_version")
    if expected_type is not None and record["record_type"] != expected_type:
        fail("B05_IMMUTABLE_TYPE_INVALID", str(record["record_type"]))
    if not isinstance(record["record_id"], str) or not record["record_id"]:
        fail("B05_IMMUTABLE_INVALID", "record_id")
    if (
        not isinstance(record["record_version"], int)
        or isinstance(record["record_version"], bool)
        or record["record_version"] < 1
    ):
        fail("B05_IMMUTABLE_INVALID", "record_version")
    if record["source_module"] != SOURCE_MODULE:
        fail("B05_IMMUTABLE_INVALID", "source_module")
    if record["access"] not in {FIXTURE_ACCESS, RUN_ACCESS}:
        fail("B05_IMMUTABLE_INVALID", "access")
    if record["retention_class"] != RETENTION_CLASS:
        fail("B05_IMMUTABLE_INVALID", "retention_class")
    _parse_utc(record["created_at"])
    expected_hash = sha256_value(
        {k: v for k, v in record.items() if k != "record_hash"}
    )
    if record["record_hash"] != expected_hash:
        fail("B05_IMMUTABLE_HASH_MISMATCH", record["record_id"])


def record_ref(record: dict[str, Any]) -> dict[str, Any]:
    validate_immutable_record(record)
    return {
        "contract": RECORD_REF_CONTRACT,
        "contract_version": record["contract_version"],
        "record_type": record["record_type"],
        "record_id": record["record_id"],
        "record_version": record["record_version"],
        "record_contract_version": record["record_contract_version"],
        "record_hash": record["record_hash"],
        "access": record["access"],
        "source_module": record["source_module"],
    }


def build_record(
    *,
    record_type: str,
    record_id: str,
    payload: dict[str, Any],
    created_at: str,
    writer_token: object,
    access: str = FIXTURE_ACCESS,
) -> dict[str, Any]:
    if _WRITER_TOKENS.get(record_type) is not writer_token:
        fail("B05_WRITER_SCOPE_ESCAPE", record_type)
    _parse_utc(created_at)
    record = {
        "contract": IMMUTABLE_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "record_type": record_type,
        "record_id": record_id,
        "record_version": 1,
        "record_contract_version": CONTRACT_VERSION,
        "record_hash": "",
        "source_module": SOURCE_MODULE,
        "access": access,
        "retention_class": RETENTION_CLASS,
        "created_at": created_at,
        "payload": normalize(deepcopy(payload)),
    }
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    validate_output_record(record)
    return record


def _walk_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            found.add(key)
            found.update(_walk_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_walk_keys(item))
    return found


def _walk_strings(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str):
        found.add(value)
    elif isinstance(value, dict):
        for child in value.values():
            found.update(_walk_strings(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_walk_strings(child))
    return found


def validate_output_record(record: Any) -> None:
    validate_immutable_record(record)
    if record["record_version"] != 1:
        fail("B05_OUTPUT_VERSION_INVALID")
    record_type = record["record_type"]
    if record_type not in OUTPUT_TYPES:
        fail("B05_OUTPUT_TYPE_INVALID", str(record_type))
    exact_keys(
        record["payload"], PAYLOAD_KEYS[record_type], "B05_PAYLOAD_SHAPE_INVALID"
    )
    payload = record["payload"]
    prefixes = {
        "M3_VALIDATOR_IDENTITY_RECEIPT": "validator-identity",
        "M3_PATCH_VALIDATION_RECEIPT": "patch-validation",
        "M3_PATCH_ROUTE_RECEIPT": "patch-route",
        "M3_PATCH_LIFECYCLE_RECEIPT": "patch-route-lifecycle",
    }
    if record["record_id"] != f"{prefixes[record_type]}:{sha256_value(payload)}":
        fail("B05_PAYLOAD_ADDRESSED_IDENTITY_INVALID")
    if record_type == "M3_VALIDATOR_IDENTITY_RECEIPT":
        capabilities = payload["runtime_capabilities"]
        exact_keys(
            capabilities,
            {
                "model_api",
                "network",
                "real_novel_read",
                "text_slice_read",
                "candidate_content_generation",
            },
            "B05_VALIDATOR_CAPABILITY_SHAPE_INVALID",
        )
        if any(capabilities.values()):
            fail("B05_VALIDATOR_CAPABILITY_INVALID")
    elif record_type == "M3_PATCH_VALIDATION_RECEIPT":
        _validate_pvr_payload(payload)
        if (_walk_keys(payload) | _walk_strings(payload)) & FORBIDDEN_PVR_KEYS:
            fail("B05_PVR_ROUTE_CONCLUSION_FORBIDDEN")
        exact_keys(
            payload["runtime_counters"], RUNTIME_COUNTER_KEYS, "B05_COUNTERS_INVALID"
        )
        if any(payload["runtime_counters"].values()):
            fail("B05_RUNTIME_COUNTER_NONZERO")
    elif record_type == "M3_PATCH_ROUTE_RECEIPT":
        exact_keys(
            payload["binding_header"],
            BINDING_HEADER_KEYS,
            "B05_BINDING_HEADER_INVALID",
        )
        if payload["binding_header_hash"] != sha256_value(payload["binding_header"]):
            fail("B05_BINDING_HEADER_HASH_MISMATCH")
        validate_record_ref(
            payload["validation_receipt_ref"],
            expected_type="M3_PATCH_VALIDATION_RECEIPT",
        )
        for entry in payload["route_units"]:
            exact_keys(entry, ROUTE_ENTRY_KEYS, "B05_ROUTE_ENTRY_INVALID")
            if entry["route"] not in ROUTES:
                fail("B05_ROUTE_INVALID")
            _validate_route_companions(entry)
        for entry in payload["causal_hint_routes"]:
            exact_keys(entry, CAUSAL_ROUTE_ENTRY_KEYS, "B05_CAUSAL_ROUTE_ENTRY_INVALID")
            if entry["route"] not in CAUSAL_ROUTES:
                fail("B05_CAUSAL_ROUTE_INVALID")
            _validate_causal_companions(entry)
    else:
        if payload["event"] not in LIFECYCLE_EVENTS:
            fail("B05_LIFECYCLE_EVENT_INVALID")
        _parse_utc(payload["effective_at"])
        if _walk_keys(payload) & {"route", "route_units", "causal_hint_routes"}:
            fail("B05_LIFECYCLE_ROUTE_COPY_FORBIDDEN")
        validate_record_ref(
            payload["subject_route_receipt_ref"],
            expected_type="M3_PATCH_ROUTE_RECEIPT",
        )
        for key in (
            "prior_route_receipt_ref_or_null",
            "replacement_route_receipt_ref_or_null",
        ):
            if payload[key] is not None:
                validate_record_ref(
                    payload[key], expected_type="M3_PATCH_ROUTE_RECEIPT"
                )
        for ref in payload["material_delta_refs"]:
            validate_record_ref(ref)
        _validate_lifecycle_companions(payload)


def _validate_route_companions(entry: dict[str, Any]) -> None:
    route = entry["route"]
    reasons = entry["reason_codes"]
    expand = entry["expand_check_target_or_null"]
    gates = entry["defer_gate_refs"]
    if not isinstance(reasons, list) or reasons != sorted(set(reasons)):
        fail("B05_ROUTE_REASON_INVALID")
    if not set(reasons) <= REASON_CODES[route]:
        fail("B05_ROUTE_REASON_INVALID")
    if route == "ALLOW_FOR_B06" and (
        reasons != ["MECHANICAL_PROOF_COMPLETE"] or expand is not None or gates
    ):
        fail("B05_ALLOW_COMPANION_INVALID")
    if route == "REJECT" and (not reasons or expand is not None or gates):
        fail("B05_REJECT_COMPANION_INVALID")
    if route == "EXPAND_CHECK" and (not reasons or expand is None or gates):
        fail("B05_EXPAND_COMPANION_INVALID")
    if route == "DEFER" and (
        reasons != ["DECLARED_NON_CONTENT_GATE_CLOSED"]
        or expand is not None
        or not gates
    ):
        fail("B05_DEFER_COMPANION_INVALID")


def _require_canonical_collection(values: Any, code: str) -> list[Any]:
    if not isinstance(values, list):
        fail(code, "list required")
    try:
        canonical = stable_sorted(values)
    except B05ContractError as error:
        fail(code, error.code)
    if values != canonical:
        fail(code, "canonical order required")
    return values


def validate_gate_applicability_targets(
    targets: Any,
    *,
    exact_group_binding_keys: set[bytes] | None = None,
    route_unit_ids: set[str] | None = None,
) -> None:
    if not isinstance(targets, list) or not targets:
        fail("B05_GATE_APPLICABILITY_INVALID")
    _require_canonical_collection(targets, "B05_GATE_APPLICABILITY_INVALID")
    for target in targets:
        if isinstance(target, str):
            if re.fullmatch(r"route-unit:[0-9a-f]{64}", target) is None:
                fail("B05_GATE_APPLICABILITY_INVALID")
            if route_unit_ids is not None and target not in route_unit_ids:
                fail("B05_GATE_APPLICABILITY_INVALID")
            continue
        exact_keys(
            target,
            {"atomic_group_id", "group_payload_hash"},
            "B05_GATE_APPLICABILITY_INVALID",
        )
        if (
            not isinstance(target["atomic_group_id"], str)
            or not target["atomic_group_id"]
            or not _is_sha(target["group_payload_hash"])
        ):
            fail("B05_GATE_APPLICABILITY_INVALID")
        if (
            exact_group_binding_keys is not None
            and canonical_bytes(target) not in exact_group_binding_keys
        ):
            fail("B05_GATE_APPLICABILITY_INVALID")


def _validate_dependency_evidence_token(token: Any, code: str) -> None:
    exact_keys(token, {"type", "value"}, code)
    token_type = token["type"]
    value = token["value"]
    if (
        not isinstance(token_type, str)
        or token_type not in DEPENDENCY_EVIDENCE_TOKEN_TYPES
    ):
        fail(code, "unsupported evidence token type")
    try:
        if token_type == "EXACT_RECORD_REF":
            validate_record_ref(value)
        elif token_type == "LINEAGE_LOCATOR":
            exact_keys(
                value,
                {
                    "contract",
                    "contract_version",
                    "candidate_version_ref",
                    "lineage_id",
                    "json_pointer",
                    "item_hash",
                    "locator_hash",
                },
                code,
            )
            if (
                value["contract"] != "M3_LINEAGE_LOCATOR"
                or value["contract_version"] != CONTRACT_VERSION
                or not isinstance(value["lineage_id"], str)
                or not value["lineage_id"]
                or not isinstance(value["json_pointer"], str)
                or re.fullmatch(r"/items/(0|[1-9][0-9]*)", value["json_pointer"])
                is None
                or not _is_sha(value["item_hash"])
            ):
                fail(code, "invalid lineage locator")
            validate_record_ref(
                value["candidate_version_ref"],
                expected_type="M3_CANDIDATE_VERSION",
            )
            if value["locator_hash"] != sha256_value(
                {key: item for key, item in value.items() if key != "locator_hash"}
            ):
                fail(code, "lineage locator hash")
        elif token_type == "EVIDENCE_LOCATOR":
            exact_keys(
                value,
                {
                    "contract",
                    "contract_version",
                    "candidate_version_ref",
                    "lineage_id",
                    "evidence_json_pointer",
                    "evidence_sha256",
                    "binding_hash",
                    "locator_hash",
                },
                code,
            )
            if (
                value["contract"] != "M3_EVIDENCE_LOCATOR"
                or value["contract_version"] != CONTRACT_VERSION
                or not isinstance(value["lineage_id"], str)
                or not value["lineage_id"]
                or not isinstance(value["evidence_json_pointer"], str)
                or re.fullmatch(
                    r"/items/(0|[1-9][0-9]*)/evidence",
                    value["evidence_json_pointer"],
                )
                is None
                or not _is_sha(value["evidence_sha256"])
                or not _is_sha(value["binding_hash"])
            ):
                fail(code, "invalid evidence locator")
            validate_record_ref(
                value["candidate_version_ref"],
                expected_type="M3_CANDIDATE_VERSION",
            )
            if value["locator_hash"] != sha256_value(
                {key: item for key, item in value.items() if key != "locator_hash"}
            ):
                fail(code, "evidence locator hash")
        elif token_type == "JSON_POINTER":
            if (
                not isinstance(value, str)
                or not value.startswith("/")
                or re.search(r"~(?:[^01]|$)", value) is not None
            ):
                fail(code, "invalid JSON pointer")
        elif token_type == "OPERATION_FINGERPRINT":
            if not _is_sha(value):
                fail(code, "invalid operation fingerprint")
        elif (
            not isinstance(value, str)
            or re.fullmatch(r"B05_CHECK_[A-Z0-9_]+", value) is None
        ):
            fail(code, "invalid stable check code")
    except B05ContractError as error:
        if error.code == code:
            raise
        fail(code, error.code)


def _validate_dependency_edge(
    edge: Any,
    *,
    valid_group_ids: set[str],
    code: str,
) -> None:
    exact_keys(
        edge,
        {
            "left_atomic_group_id",
            "right_atomic_group_id",
            "edge_type",
            "evidence_tokens",
        },
        code,
    )
    left = edge["left_atomic_group_id"]
    right = edge["right_atomic_group_id"]
    if (
        not isinstance(left, str)
        or not isinstance(right, str)
        or left not in valid_group_ids
        or right not in valid_group_ids
        or left == right
        or canonical_bytes(left) >= canonical_bytes(right)
        or not isinstance(edge["edge_type"], str)
        or edge["edge_type"] not in DEPENDENCY_EDGE_TYPES
    ):
        fail(code, "invalid dependency edge semantics")
    tokens = _require_canonical_collection(edge["evidence_tokens"], code)
    for token in tokens:
        _validate_dependency_evidence_token(token, code)


def _validate_unknown_dependency_token(
    token: Any,
    *,
    valid_group_ids: set[str],
    normalized: bool,
    code: str,
) -> None:
    expected = {
        "reason_code",
        "bounded_atomic_group_ids",
        "supporting_refs",
    }
    if normalized:
        expected.add("token_id")
    exact_keys(token, expected, code)
    reason = token["reason_code"]
    if not isinstance(reason, str) or reason not in UNKNOWN_DEPENDENCY_REASON_CODES:
        fail(code, "invalid reason code")
    bounded = _require_canonical_collection(token["bounded_atomic_group_ids"], code)
    if any(
        not isinstance(group_id, str) or group_id not in valid_group_ids
        for group_id in bounded
    ):
        fail(code, "invalid bounded group")
    supporting_refs = _require_canonical_collection(token["supporting_refs"], code)
    for supporting_ref in supporting_refs:
        try:
            validate_record_ref(supporting_ref)
        except B05ContractError as error:
            fail(code, error.code)
    if normalized:
        preimage = {
            "reason_code": reason,
            "bounded_atomic_group_ids": bounded,
            "supporting_refs": supporting_refs,
        }
        if token["token_id"] != f"unknown-dependency:{sha256_value(preimage)}":
            fail(code, "token identity mismatch")


def validate_validation_policy_semantics(
    *,
    policy_payload: Any,
    atomic_group_bindings: Any,
) -> None:
    group_bindings = _require_canonical_collection(
        atomic_group_bindings, "B05_GATE_GROUP_CATALOG_INVALID"
    )
    group_ids: list[str] = []
    for binding in group_bindings:
        exact_keys(
            binding,
            {"atomic_group_id", "group_payload_hash"},
            "B05_GATE_GROUP_CATALOG_INVALID",
        )
        if (
            not isinstance(binding["atomic_group_id"], str)
            or not binding["atomic_group_id"]
            or not _is_sha(binding["group_payload_hash"])
        ):
            fail("B05_GATE_GROUP_CATALOG_INVALID")
        group_ids.append(binding["atomic_group_id"])
    if len(group_ids) != len(set(group_ids)):
        fail("B05_GATE_GROUP_CATALOG_INVALID")
    valid_group_ids = set(group_ids)
    if (
        not isinstance(policy_payload, dict)
        or not isinstance(policy_payload.get("policy_version"), str)
        or not policy_payload["policy_version"]
        or not isinstance(policy_payload.get("canonical_add_sort_frozen"), bool)
    ):
        fail("B05_VALIDATION_POLICY_SHAPE_INVALID")
    for field in ("semantic_unknown_group_ids", "adjacent_check_group_ids"):
        values = _require_canonical_collection(
            policy_payload.get(field), "B05_POLICY_GROUP_SET_INVALID"
        )
        if any(
            not isinstance(group_id, str) or group_id not in valid_group_ids
            for group_id in values
        ):
            fail("B05_POLICY_GROUP_SET_INVALID", field)
    edges = _require_canonical_collection(
        policy_payload.get("declared_dependency_edges"),
        "B05_POLICY_DEPENDENCY_EDGE_INVALID",
    )
    for edge in edges:
        _validate_dependency_edge(
            edge,
            valid_group_ids=valid_group_ids,
            code="B05_POLICY_DEPENDENCY_EDGE_INVALID",
        )
    unknown = _require_canonical_collection(
        policy_payload.get("unknown_dependency_tokens"),
        "B05_UNKNOWN_DEPENDENCY_INVALID",
    )
    for token in unknown:
        _validate_unknown_dependency_token(
            token,
            valid_group_ids=valid_group_ids,
            normalized=False,
            code="B05_UNKNOWN_DEPENDENCY_INVALID",
        )


def _expected_route_unit_partition(
    *,
    patch_proposal_ref: dict[str, Any],
    group_bindings_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    unknown_tokens: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    group_ids = set(group_bindings_by_id)
    adjacency = {group_id: set() for group_id in group_ids}
    for edge in edges:
        left = edge["left_atomic_group_id"]
        right = edge["right_atomic_group_id"]
        adjacency[left].add(right)
        adjacency[right].add(left)
    all_group_ids = sorted(group_ids, key=canonical_bytes)
    for token in unknown_tokens:
        bounded = token["bounded_atomic_group_ids"] or all_group_ids
        for left in bounded:
            for right in bounded:
                if left != right:
                    adjacency[left].add(right)
    components: list[set[str]] = []
    remaining = set(group_ids)
    while remaining:
        stack = [min(remaining, key=canonical_bytes)]
        component: set[str] = set()
        while stack:
            group_id = stack.pop()
            if group_id in component:
                continue
            component.add(group_id)
            stack.extend(adjacency[group_id] - component)
        remaining -= component
        components.append(component)
    partition = []
    for component in components:
        bindings = stable_sorted(
            [group_bindings_by_id[group_id] for group_id in component]
        )
        partition.append(
            {
                "route_unit_id": f"route-unit:{sha256_value({'patch_proposal_ref': patch_proposal_ref, 'atomic_group_bindings': bindings})}",
                "atomic_group_bindings": bindings,
            }
        )
    return stable_sorted(partition)


def _validate_pvr_payload(payload: dict[str, Any]) -> None:
    for key, expected_type in (
        ("validator_identity_ref", "M3_VALIDATOR_IDENTITY_RECEIPT"),
        ("validation_policy_ref", None),
        ("active_policy_selection_ref", None),
    ):
        validate_record_ref(payload[key], expected_type=expected_type)
    binding = payload["input_binding"]
    exact_keys(binding, INPUT_BINDING_KEYS, "B05_INPUT_BINDING_INVALID")
    for key, expected_type in (
        ("patch_proposal_ref", "M3_PATCH_PROPOSAL"),
        ("protection_set_ref", "M3_CANDIDATE_PROTECTION_SET"),
        ("base_candidate_version_ref", "M3_CANDIDATE_VERSION"),
        ("segment_index_ref", "M3_SEGMENT_INDEX_SNAPSHOT"),
    ):
        validate_record_ref(binding[key], expected_type=expected_type)
    for ref in binding["causal_hint_proposal_refs"]:
        validate_record_ref(ref, expected_type="M3_CAUSAL_HINT_PROPOSAL")
    if binding["candidate_pointer_snapshot_ref_or_null"] is not None:
        validate_record_ref(
            binding["candidate_pointer_snapshot_ref_or_null"],
            expected_type="M3_CANDIDATE_POINTER_SNAPSHOT",
        )
    for key, expected_type in (
        ("prior_active_route_receipt_ref_or_null", "M3_PATCH_ROUTE_RECEIPT"),
        ("prior_lifecycle_head_ref_or_null", "M3_PATCH_LIFECYCLE_RECEIPT"),
    ):
        if binding[key] is not None:
            validate_record_ref(binding[key], expected_type=expected_type)
    if (binding["prior_active_route_receipt_ref_or_null"] is None) != (
        binding["prior_lifecycle_head_ref_or_null"] is None
    ):
        fail("B05_REOPEN_BINDING_INCOMPLETE")
    if binding["candidate_schema_id"] != CANDIDATE_SCHEMA_ID:
        fail("B05_INPUT_SCHEMA_INVALID")
    if binding["live_pointer_binding_hash"] != sha256_value(
        binding["live_pointer_binding"]
    ):
        fail("B05_LIVE_POINTER_BINDING_HASH_MISMATCH")
    b02 = binding["b02_scope_binding"]
    exact_keys(
        b02,
        {
            "reader_identity",
            "reader_version",
            "base_candidate_version_ref",
            "diagnostic_state_bindings",
            "coverage_observation_refs",
            "scope_snapshot_hash",
        },
        "B05_B02_SCOPE_BINDING_INVALID",
    )
    if binding["b02_scope_snapshot_hash"] != b02["scope_snapshot_hash"]:
        fail("B05_B02_SCOPE_HASH_MISMATCH")
    if binding["non_content_gate_snapshot_hash"] != sha256_value(
        binding["non_content_gate_bindings"]
    ):
        fail("B05_GATE_SNAPSHOT_HASH_MISMATCH")
    gate_bindings = _require_canonical_collection(
        binding["non_content_gate_bindings"], "B05_GATE_BINDING_SHAPE_INVALID"
    )
    for gate_binding in gate_bindings:
        exact_keys(
            gate_binding,
            {
                "gate_ref",
                "gate_state_ref",
                "current_state",
                "applicable_patch_proposal_ref",
                "applicable_atomic_group_bindings_or_route_unit_ids",
                "reader_identity",
                "reader_version",
            },
            "B05_GATE_BINDING_SHAPE_INVALID",
        )
        validate_gate_applicability_targets(
            gate_binding["applicable_atomic_group_bindings_or_route_unit_ids"]
        )
    dependency = payload["dependency_proof"]
    exact_keys(dependency, DEPENDENCY_PROOF_KEYS, "B05_DEPENDENCY_PROOF_INVALID")
    expected_partition_hash = sha256_value(
        {
            "group_catalog": dependency["group_catalog"],
            "dependency_edges": dependency["dependency_edges"],
            "unknown_dependency_tokens": dependency["unknown_dependency_tokens"],
            "route_unit_partition": dependency["route_unit_partition"],
        }
    )
    if dependency["partition_hash"] != expected_partition_hash:
        fail("B05_PARTITION_HASH_MISMATCH")
    group_catalog = _require_canonical_collection(
        dependency["group_catalog"], "B05_GROUP_CATALOG_INVALID"
    )
    group_bindings_by_id: dict[str, dict[str, Any]] = {}
    for group in group_catalog:
        exact_keys(
            group,
            {
                "atomic_group_id",
                "group_payload_hash",
                "operation_count",
                "operation_fingerprints",
            },
            "B05_GROUP_CATALOG_INVALID",
        )
        group_id = group["atomic_group_id"]
        fingerprints = group["operation_fingerprints"]
        if (
            not isinstance(group_id, str)
            or not group_id
            or group_id in group_bindings_by_id
            or not _is_sha(group["group_payload_hash"])
            or not isinstance(group["operation_count"], int)
            or isinstance(group["operation_count"], bool)
            or group["operation_count"] < 1
            or not isinstance(fingerprints, list)
            or len(fingerprints) != group["operation_count"]
            or any(not _is_sha(item) for item in fingerprints)
        ):
            fail("B05_GROUP_CATALOG_INVALID")
        group_bindings_by_id[group_id] = {
            "atomic_group_id": group_id,
            "group_payload_hash": group["group_payload_hash"],
        }
    valid_group_ids = set(group_bindings_by_id)
    edges = _require_canonical_collection(
        dependency["dependency_edges"], "B05_DEPENDENCY_EDGE_INVALID"
    )
    for edge in edges:
        _validate_dependency_edge(
            edge,
            valid_group_ids=valid_group_ids,
            code="B05_DEPENDENCY_EDGE_INVALID",
        )
    unknown_tokens = _require_canonical_collection(
        dependency["unknown_dependency_tokens"],
        "B05_UNKNOWN_DEPENDENCY_INVALID",
    )
    for token in unknown_tokens:
        _validate_unknown_dependency_token(
            token,
            valid_group_ids=valid_group_ids,
            normalized=True,
            code="B05_UNKNOWN_DEPENDENCY_INVALID",
        )
    partition = _require_canonical_collection(
        dependency["route_unit_partition"], "B05_ROUTE_UNIT_PARTITION_INVALID"
    )
    route_unit_ids: set[str] = set()
    partitioned_group_ids: list[str] = []
    for unit in partition:
        exact_keys(
            unit,
            {"route_unit_id", "atomic_group_bindings"},
            "B05_ROUTE_UNIT_PARTITION_INVALID",
        )
        route_unit_id = unit["route_unit_id"]
        if (
            not isinstance(route_unit_id, str)
            or re.fullmatch(r"route-unit:[0-9a-f]{64}", route_unit_id) is None
            or route_unit_id in route_unit_ids
        ):
            fail("B05_ROUTE_UNIT_PARTITION_INVALID")
        route_unit_ids.add(route_unit_id)
        unit_bindings = _require_canonical_collection(
            unit["atomic_group_bindings"], "B05_ROUTE_UNIT_PARTITION_INVALID"
        )
        if not unit_bindings:
            fail("B05_ROUTE_UNIT_PARTITION_INVALID")
        for group_binding in unit_bindings:
            exact_keys(
                group_binding,
                {"atomic_group_id", "group_payload_hash"},
                "B05_ROUTE_UNIT_PARTITION_INVALID",
            )
            group_id = group_binding["atomic_group_id"]
            if (
                not isinstance(group_id, str)
                or group_bindings_by_id.get(group_id) != group_binding
            ):
                fail("B05_ROUTE_UNIT_PARTITION_INVALID")
            partitioned_group_ids.append(group_id)
    if sorted(partitioned_group_ids, key=canonical_bytes) != sorted(
        valid_group_ids, key=canonical_bytes
    ):
        fail("B05_ROUTE_UNIT_PARTITION_INVALID")
    if partition != _expected_route_unit_partition(
        patch_proposal_ref=binding["patch_proposal_ref"],
        group_bindings_by_id=group_bindings_by_id,
        edges=edges,
        unknown_tokens=unknown_tokens,
    ):
        fail("B05_ROUTE_UNIT_PARTITION_INVALID")
    exact_group_binding_keys = {
        canonical_bytes(binding_value)
        for binding_value in group_bindings_by_id.values()
    }
    for gate_binding in gate_bindings:
        validate_gate_applicability_targets(
            gate_binding["applicable_atomic_group_bindings_or_route_unit_ids"],
            exact_group_binding_keys=exact_group_binding_keys,
            route_unit_ids=route_unit_ids,
        )
    for proof in payload["route_unit_proofs"]:
        exact_keys(proof, ROUTE_UNIT_PROOF_KEYS, "B05_ROUTE_UNIT_PROOF_INVALID")
        expected_hash = sha256_value(
            {key: value for key, value in proof.items() if key != "unit_proof_hash"}
        )
        if proof["unit_proof_hash"] != expected_hash:
            fail("B05_UNIT_PROOF_HASH_MISMATCH")
        for collection in (
            proof["candidate_structure_check_results"],
            proof["check_results"],
        ):
            for check in collection:
                exact_keys(
                    check,
                    {"check_code", "status", "subject_bindings", "evidence_hashes"},
                    "B05_CHECK_RESULT_INVALID",
                )
                if not str(check["check_code"]).startswith("B05_CHECK_") or check[
                    "status"
                ] not in {"PASS", "FAIL", "UNKNOWN"}:
                    fail("B05_CHECK_RESULT_INVALID")
    for mapping in payload["causal_support_mappings"]:
        exact_keys(
            mapping,
            {
                "causal_hint_proposal_ref",
                "locator_resolution",
                "support_ref_ownership",
                "affected_group_ownership",
                "supporting_atomic_group_ids",
                "supporting_route_unit_ids",
                "mapping_status",
                "mapping_proof_hash",
            },
            "B05_CAUSAL_MAPPING_INVALID",
        )
        validate_record_ref(
            mapping["causal_hint_proposal_ref"],
            expected_type="M3_CAUSAL_HINT_PROPOSAL",
        )
        if mapping["mapping_status"] not in {"COMPLETE", "EXPAND_REQUIRED"}:
            fail("B05_CAUSAL_MAPPING_INVALID")
        if mapping["mapping_proof_hash"] != sha256_value(
            {
                key: value
                for key, value in mapping.items()
                if key != "mapping_proof_hash"
            }
        ):
            fail("B05_CAUSAL_MAPPING_HASH_MISMATCH")


def _validate_causal_companions(entry: dict[str, Any]) -> None:
    route = entry["route"]
    reasons = entry["reason_codes"]
    expand = entry["expand_check_target_or_null"]
    expected = {
        "ROUTE_TO_B09": {"ALL_SUPPORTING_ROUTE_UNITS_ALLOWED"},
        "REJECT": {"SUPPORTING_ROUTE_UNIT_REJECTED"},
        "DEFER": {"SUPPORTING_ROUTE_UNIT_DEFERRED"},
        "EXPAND_CHECK": {
            "CAUSAL_SUPPORT_MAPPING_AMBIGUOUS",
            "SUPPORTING_ROUTE_UNIT_EXPAND_CHECK",
        },
    }
    if not isinstance(reasons, list) or reasons != sorted(set(reasons)):
        fail("B05_CAUSAL_REASON_INVALID")
    if not reasons or not set(reasons) <= expected[route]:
        fail("B05_CAUSAL_REASON_INVALID")
    if route != "EXPAND_CHECK" and expand is not None:
        fail("B05_CAUSAL_EXPAND_TARGET_INVALID")
    if route == "EXPAND_CHECK":
        ambiguous = "CAUSAL_SUPPORT_MAPPING_AMBIGUOUS" in reasons
        if ambiguous != (expand is not None):
            fail("B05_CAUSAL_EXPAND_TARGET_INVALID")


def _validate_lifecycle_companions(payload: dict[str, Any]) -> None:
    event = payload["event"]
    if (
        not isinstance(payload["lifecycle_sequence"], int)
        or payload["lifecycle_sequence"] < 1
    ):
        fail("B05_LIFECYCLE_SEQUENCE_INVALID")
    if event == "ROUTES_FROZEN" and (
        payload["lifecycle_sequence"] != 1
        or payload["reason_code"] != "INITIAL_ROUTE_BUNDLE_COMMITTED"
        or payload["prior_route_receipt_ref_or_null"] is not None
        or payload["replacement_route_receipt_ref_or_null"] is not None
        or payload["material_delta_refs"]
    ):
        fail("B05_LIFECYCLE_FROZEN_INVALID")
    if event == "SUPERSEDED" and (
        payload["reason_code"] != "SUPERSEDED_BY_NEW_ROUTE_RECEIPT"
        or payload["prior_route_receipt_ref_or_null"] is not None
        or payload["replacement_route_receipt_ref_or_null"] is None
        or payload["material_delta_refs"]
    ):
        fail("B05_LIFECYCLE_SUPERSEDED_INVALID")
    if event == "REOPENED_WITH_NEW_MATERIAL" and (
        payload["reason_code"] != "REEVALUATED_WITH_MATERIAL_DELTA"
        or payload["prior_route_receipt_ref_or_null"] is None
        or payload["replacement_route_receipt_ref_or_null"] is not None
        or not payload["material_delta_refs"]
    ):
        fail("B05_LIFECYCLE_REOPEN_INVALID")


def stable_sorted(values: list[Any]) -> list[Any]:
    ordered = sorted(deepcopy(values), key=canonical_bytes)
    if len({canonical_bytes(item) for item in ordered}) != len(ordered):
        fail("B05_CANONICAL_DUPLICATE")
    return ordered


class ValidatorIdentityBuilder:
    @staticmethod
    def build(*, payload: dict[str, Any], created_at: str) -> dict[str, Any]:
        exact_keys(
            payload,
            PAYLOAD_KEYS["M3_VALIDATOR_IDENTITY_RECEIPT"],
            "B05_VALIDATOR_IDENTITY_INVALID",
        )
        payload_hash = sha256_value(payload)
        return build_record(
            record_type="M3_VALIDATOR_IDENTITY_RECEIPT",
            record_id=f"validator-identity:{payload_hash}",
            payload=payload,
            created_at=created_at,
            writer_token=_WRITER_TOKENS["M3_VALIDATOR_IDENTITY_RECEIPT"],
        )


class PatchValidator:
    """Pure builder for the proof-only validation receipt."""

    @staticmethod
    def build(*, payload: dict[str, Any], created_at: str) -> dict[str, Any]:
        exact_keys(
            payload,
            PAYLOAD_KEYS["M3_PATCH_VALIDATION_RECEIPT"],
            "B05_PVR_PAYLOAD_INVALID",
        )
        record_id = f"patch-validation:{sha256_value(payload)}"
        return build_record(
            record_type="M3_PATCH_VALIDATION_RECEIPT",
            record_id=record_id,
            payload=payload,
            created_at=created_at,
            writer_token=_WRITER_TOKENS["M3_PATCH_VALIDATION_RECEIPT"],
        )


class PatchRouteDecider:
    """Pure builder for the final-route-only receipt."""

    @staticmethod
    def build(*, payload: dict[str, Any], created_at: str) -> dict[str, Any]:
        exact_keys(
            payload, PAYLOAD_KEYS["M3_PATCH_ROUTE_RECEIPT"], "B05_ROUTE_PAYLOAD_INVALID"
        )
        record_id = f"patch-route:{sha256_value(payload)}"
        return build_record(
            record_type="M3_PATCH_ROUTE_RECEIPT",
            record_id=record_id,
            payload=payload,
            created_at=created_at,
            writer_token=_WRITER_TOKENS["M3_PATCH_ROUTE_RECEIPT"],
        )


class PatchLifecycleBuilder:
    @staticmethod
    def build(*, payload: dict[str, Any], created_at: str) -> dict[str, Any]:
        exact_keys(
            payload,
            PAYLOAD_KEYS["M3_PATCH_LIFECYCLE_RECEIPT"],
            "B05_LIFECYCLE_PAYLOAD_INVALID",
        )
        record_id = f"patch-route-lifecycle:{sha256_value(payload)}"
        return build_record(
            record_type="M3_PATCH_LIFECYCLE_RECEIPT",
            record_id=record_id,
            payload=payload,
            created_at=created_at,
            writer_token=_WRITER_TOKENS["M3_PATCH_LIFECYCLE_RECEIPT"],
        )


def deterministic_result_view(
    pvr: dict[str, Any], route: dict[str, Any], lifecycles: list[dict[str, Any]]
) -> dict[str, Any]:
    """Remove creator operation and clocks before nondeterminism comparison."""

    pvr_payload = deepcopy(pvr["payload"])
    pvr_payload.pop("operation_id", None)
    lifecycle_payloads = []
    for item in lifecycles:
        payload = deepcopy(item["payload"])
        payload.pop("effective_at", None)
        lifecycle_payloads.append(payload)
    return {
        "pvr_payload_without_operation_id": pvr_payload,
        "route_payload": deepcopy(route["payload"]),
        "lifecycle_payloads_without_clock": stable_sorted(lifecycle_payloads),
    }


def reference_cycle_count(records: list[dict[str, Any]]) -> int:
    ids = {item["record_id"] for item in records}
    edges: dict[str, set[str]] = {item: set() for item in ids}

    def visit(value: Any, owner: str) -> None:
        if isinstance(value, dict):
            if set(value) == RECORD_REF_KEYS and value.get("record_id") in ids:
                edges[owner].add(value["record_id"])
            for child in value.values():
                visit(child, owner)
        elif isinstance(value, list):
            for child in value:
                visit(child, owner)

    for record in records:
        visit(record["payload"], record["record_id"])
    visiting: set[str] = set()
    visited: set[str] = set()

    def cyclic(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        result = any(cyclic(target) for target in edges[node])
        visiting.remove(node)
        visited.add(node)
        return result

    return sum(1 for node in ids if cyclic(node))
