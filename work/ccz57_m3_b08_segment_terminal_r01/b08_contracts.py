"""B-08 immutable segment-terminal record and derived-view contracts."""

from __future__ import annotations

import hashlib
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    CANDIDATE_SCHEMA_ID,
    SOURCE_GENERATION_RECORD_TYPE,
    validate_chapter_revision_ref,
)
from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    CONTRACT_VERSION,
    IMMUTABLE_CONTRACT,
    RETENTION_CLASS,
    RUN_ACCESS,
    SOURCE_MODULE,
    canonical_bytes,
    record_ref,
    sha256_value,
    validate_immutable_record,
    validate_record_ref,
)
from work.ccz57_m3_b06_commit_core_r01.b06_contracts import (  # noqa: E402
    MERGE_RECEIPT_TYPE,
    validate_merge_receipt,
)
from work.ccz57_m3_b07_local_recovery_stop_r01.b07_contracts import (  # noqa: E402
    validate_current_run_state,
)

TERMINAL_RECEIPT_TYPE = "M3_SEGMENT_CANDIDATE_TERMINAL_RECEIPT"
EXACT_CURRENT_VIEW_TYPE = "M3_EXACT_CURRENT_SEGMENT_TERMINAL_VIEW"
ADAPTER_READY_VIEW_TYPE = "M3_ADAPTER_READY_SEGMENT_VIEW"
TERMINAL_COMPONENT_KIND = TERMINAL_RECEIPT_TYPE
TERMINAL_ARTIFACT_KIND = "B08_SEGMENT_TERMINAL_RECORD"
WRITE_SET_PREFIX = "work/ccz57_m3_b08_segment_terminal_r01/"

PRODUCT_RESULTS = {
    "CANDIDATES_READY",
    "NO_CHANGE",
    "LEGAL_ZERO",
    "NOT_APPLICABLE",
    "INSUFFICIENT_EVIDENCE",
    "EXTRACTION_FAILED",
}
TERMINAL_DELIVERIES = {"COMPLETE", "EMPTY_VALID", "PARTIAL", "BLOCKED"}
CANDIDATE_ORIGINS = {"ROOT", "B06_CHILD"}
CURRENTNESS_STATES = {
    "CURRENT",
    "RUN_NOT_PUBLISHED",
    "RUN_STATUS_INCOMPATIBLE",
    "SUPERSEDED_RUN_GENERATION",
    "SUPERSEDED_RUN_EPOCH",
    "SOURCE_REVISION_STALE",
    "SEGMENT_SCOPE_STALE",
    "POINTER_STALE",
    "CANDIDATE_STALE",
    "AUTHORITY_DRIFT",
}

AUTHORITY_SNAPSHOT_KEYS = {
    "run_state",
    "segment_binding",
    "pointer_binding",
    "classification_binding",
    "b06_merge_receipt_or_null",
}
SEGMENT_BINDING_KEYS = {
    "chapter_revision_ref",
    "seg",
    "segment_scope_hash",
    "segment_index_ref",
    "source_generation_ref",
    "candidate_schema_id",
}
POINTER_BINDING_KEYS = {
    "logical_pointer_key",
    "generation",
    "current_candidate_version_ref",
    "candidate_origin",
}
CLASSIFICATION_BINDING_KEYS = {
    "classification_policy_ref",
    "classification_policy_hash",
    "product_result",
    "terminal_delivery",
    "reason_code",
    "candidate_count",
    "expected_unit_count",
    "covered_unit_count",
    "missing_unit_count",
    "coverage_complete",
}
RUN_BINDING_KEYS = {
    "project_scope_id",
    "logical_run_key",
    "run_id",
    "logical_run_generation",
    "run_epoch",
    "finalized_from_state_revision",
    "finalized_from_state_hash",
}
TERMINAL_PAYLOAD_KEYS = {
    "terminalization_key",
    "operation_id",
    "operation_request_hash",
    "run_binding",
    "segment_binding",
    "pointer_binding",
    "classification_binding",
    "b06_merge_receipt_ref_or_null",
    "authority_snapshot_hash",
    "created_at",
}
EXACT_CURRENT_VIEW_KEYS = {
    "view_type",
    "terminal_record_ref",
    "currentness",
    "reason_code",
    "product_result",
    "terminal_delivery",
    "run_id",
    "logical_run_generation",
    "run_epoch",
    "current_state_hash",
    "view_hash",
}
ADAPTER_READY_VIEW_KEYS = {
    "view_type",
    "terminal_record_ref",
    "ready",
    "reason_code",
    "product_result",
    "terminal_delivery",
    "candidate_version_ref_or_null",
    "view_hash",
}


class B08ContractError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def fail(code: str, detail: str = "") -> None:
    raise B08ContractError(code, detail)


def _exact_keys(value: Any, expected: set[str], code: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        fail(code)


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_ref(value: Any, *, expected_type: str, code: str) -> None:
    try:
        validate_record_ref(value, expected_type=expected_type)
    except ValueError as error:
        fail(code, str(error))


def validate_segment_binding(binding: Any) -> None:
    _exact_keys(binding, SEGMENT_BINDING_KEYS, "B08_SEGMENT_BINDING_INVALID")
    try:
        validate_chapter_revision_ref(binding["chapter_revision_ref"])
    except ValueError as error:
        fail("B08_SEGMENT_BINDING_INVALID", str(error))
    _validate_ref(
        binding["segment_index_ref"],
        expected_type="M3_SEGMENT_INDEX_SNAPSHOT",
        code="B08_SEGMENT_BINDING_INVALID",
    )
    _validate_ref(
        binding["source_generation_ref"],
        expected_type=SOURCE_GENERATION_RECORD_TYPE,
        code="B08_SEGMENT_BINDING_INVALID",
    )
    if (
        not _positive_int(binding["seg"])
        or not _sha(binding["segment_scope_hash"])
        or binding["candidate_schema_id"] != CANDIDATE_SCHEMA_ID
    ):
        fail("B08_SEGMENT_BINDING_INVALID")


def validate_pointer_binding(binding: Any) -> None:
    _exact_keys(binding, POINTER_BINDING_KEYS, "B08_POINTER_BINDING_INVALID")
    _validate_ref(
        binding["current_candidate_version_ref"],
        expected_type="M3_CANDIDATE_VERSION",
        code="B08_POINTER_BINDING_INVALID",
    )
    if (
        not isinstance(binding["logical_pointer_key"], str)
        or not binding["logical_pointer_key"]
        or not _positive_int(binding["generation"])
        or binding["candidate_origin"] not in CANDIDATE_ORIGINS
    ):
        fail("B08_POINTER_BINDING_INVALID")


def validate_classification_binding(binding: Any) -> None:
    _exact_keys(
        binding,
        CLASSIFICATION_BINDING_KEYS,
        "B08_CLASSIFICATION_BINDING_INVALID",
    )
    _validate_ref(
        binding["classification_policy_ref"],
        expected_type="M3_SEGMENT_TERMINAL_CLASSIFICATION_POLICY",
        code="B08_CLASSIFICATION_BINDING_INVALID",
    )
    if (
        not _sha(binding["classification_policy_hash"])
        or binding["product_result"] not in PRODUCT_RESULTS
        or binding["terminal_delivery"] not in TERMINAL_DELIVERIES
        or not isinstance(binding["reason_code"], str)
        or re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", binding["reason_code"]) is None
        or not _non_negative_int(binding["candidate_count"])
        or not _non_negative_int(binding["expected_unit_count"])
        or not _non_negative_int(binding["covered_unit_count"])
        or not _non_negative_int(binding["missing_unit_count"])
        or not isinstance(binding["coverage_complete"], bool)
        or binding["covered_unit_count"] + binding["missing_unit_count"]
        != binding["expected_unit_count"]
    ):
        fail("B08_CLASSIFICATION_BINDING_INVALID")

    result = binding["product_result"]
    delivery = binding["terminal_delivery"]
    count = binding["candidate_count"]
    coverage_complete = binding["coverage_complete"]
    if (delivery in {"COMPLETE", "EMPTY_VALID"}) != coverage_complete:
        fail("B08_RESULT_DELIVERY_CONFLICT")
    if coverage_complete != (binding["missing_unit_count"] == 0):
        fail("B08_COVERAGE_CONFLICT")
    if result == "CANDIDATES_READY" and (count < 1 or delivery != "COMPLETE"):
        fail("B08_RESULT_DELIVERY_CONFLICT")
    if result == "NO_CHANGE" and delivery != "COMPLETE":
        fail("B08_RESULT_DELIVERY_CONFLICT")
    if result in {"LEGAL_ZERO", "NOT_APPLICABLE"} and (
        count != 0 or delivery != "EMPTY_VALID"
    ):
        fail("B08_RESULT_DELIVERY_CONFLICT")
    if result == "INSUFFICIENT_EVIDENCE" and delivery not in {"PARTIAL", "BLOCKED"}:
        fail("B08_RESULT_DELIVERY_CONFLICT")
    if result == "EXTRACTION_FAILED" and delivery != "BLOCKED":
        fail("B08_RESULT_DELIVERY_CONFLICT")


def validate_authority_snapshot(snapshot: Any, *, for_publish: bool) -> None:
    _exact_keys(snapshot, AUTHORITY_SNAPSHOT_KEYS, "B08_AUTHORITY_SHAPE_INVALID")
    try:
        validate_current_run_state(snapshot["run_state"])
    except ValueError as error:
        fail("B08_RUN_AUTHORITY_INVALID", str(error))
    validate_segment_binding(snapshot["segment_binding"])
    validate_pointer_binding(snapshot["pointer_binding"])
    validate_classification_binding(snapshot["classification_binding"])

    state = snapshot["run_state"]
    segment = snapshot["segment_binding"]
    pointer = snapshot["pointer_binding"]
    state_authority = state["authority_snapshot"]
    if for_publish and (
        state_authority["chapter_revision_ref"] != segment["chapter_revision_ref"]
        or state_authority["segment_scope_hash"] != segment["segment_scope_hash"]
        or state_authority["candidate_pointer_key"] != pointer["logical_pointer_key"]
        or state_authority["observed_pointer_generation"] != pointer["generation"]
        or canonical_bytes(state_authority["observed_candidate_version_ref"])
        != canonical_bytes(pointer["current_candidate_version_ref"])
    ):
        fail("B08_AUTHORITY_BINDING_DRIFT")
    if for_publish and (
        state["status"] != "ACTIVE"
        or state["phase"] != "FINALIZING"
        or state["pending_local_action"] is not None
    ):
        fail("B08_RUN_NOT_FINALIZING")

    merge_receipt = snapshot["b06_merge_receipt_or_null"]
    if pointer["candidate_origin"] == "ROOT":
        if merge_receipt is not None:
            fail("B08_B06_BINDING_UNEXPECTED")
    else:
        if merge_receipt is None:
            fail("B08_B06_BINDING_REQUIRED")
        try:
            validate_merge_receipt(merge_receipt)
        except ValueError as error:
            fail("B08_B06_BINDING_INVALID", str(error))
        payload = merge_receipt["payload"]
        if (
            canonical_bytes(payload["child_candidate_version_ref"])
            != canonical_bytes(pointer["current_candidate_version_ref"])
            or payload["pointer_logical_key"] != pointer["logical_pointer_key"]
            or payload["pointer_generation_after"] != pointer["generation"]
        ):
            fail("B08_B06_BINDING_INVALID")


def _terminalization_key_from_bindings(
    run: dict[str, Any], segment: dict[str, Any]
) -> str:
    return sha256_value(
        {
            "project_scope_id": run["project_scope_id"],
            "logical_run_key": run["logical_run_key"],
            "run_id": run["run_id"],
            "logical_run_generation": run["logical_run_generation"],
            "run_epoch": run["run_epoch"],
            "chapter_revision_ref": segment["chapter_revision_ref"],
            "seg": segment["seg"],
            "segment_scope_hash": segment["segment_scope_hash"],
        }
    )


def terminalization_key(snapshot: dict[str, Any]) -> str:
    validate_authority_snapshot(snapshot, for_publish=False)
    state = snapshot["run_state"]
    run = {
        "project_scope_id": state["project_scope_id"],
        "logical_run_key": state["logical_run_key"],
        "run_id": state["run_id"],
        "logical_run_generation": state["logical_run_generation"],
        "run_epoch": state["run_epoch"],
    }
    return _terminalization_key_from_bindings(run, snapshot["segment_binding"])


def build_terminal_record(
    *,
    snapshot: dict[str, Any],
    operation_id: str,
    operation_request_hash: str,
    created_at: str,
) -> dict[str, Any]:
    validate_authority_snapshot(snapshot, for_publish=True)
    if (
        not isinstance(operation_id, str)
        or not operation_id
        or not _sha(operation_request_hash)
    ):
        fail("B08_OPERATION_INVALID")
    state = snapshot["run_state"]
    key = terminalization_key(snapshot)
    merge_receipt = snapshot["b06_merge_receipt_or_null"]
    payload = {
        "terminalization_key": key,
        "operation_id": operation_id,
        "operation_request_hash": operation_request_hash,
        "run_binding": {
            "project_scope_id": state["project_scope_id"],
            "logical_run_key": state["logical_run_key"],
            "run_id": state["run_id"],
            "logical_run_generation": state["logical_run_generation"],
            "run_epoch": state["run_epoch"],
            "finalized_from_state_revision": state["state_revision"],
            "finalized_from_state_hash": state["state_hash"],
        },
        "segment_binding": deepcopy(snapshot["segment_binding"]),
        "pointer_binding": deepcopy(snapshot["pointer_binding"]),
        "classification_binding": deepcopy(snapshot["classification_binding"]),
        "b06_merge_receipt_ref_or_null": (
            None if merge_receipt is None else record_ref(merge_receipt)
        ),
        "authority_snapshot_hash": sha256_value(snapshot),
        "created_at": created_at,
    }
    record = {
        "contract": IMMUTABLE_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "record_type": TERMINAL_RECEIPT_TYPE,
        "record_id": f"segment-terminal:{key}",
        "record_version": 1,
        "record_contract_version": CONTRACT_VERSION,
        "record_hash": "",
        "source_module": SOURCE_MODULE,
        "access": RUN_ACCESS,
        "retention_class": RETENTION_CLASS,
        "created_at": created_at,
        "payload": payload,
    }
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    validate_terminal_record(record)
    return record


def validate_terminal_record(record: Any) -> None:
    try:
        validate_immutable_record(record, expected_type=TERMINAL_RECEIPT_TYPE)
    except ValueError as error:
        fail("B08_TERMINAL_RECORD_INVALID", str(error))
    payload = record["payload"]
    _exact_keys(payload, TERMINAL_PAYLOAD_KEYS, "B08_TERMINAL_PAYLOAD_INVALID")
    _exact_keys(payload["run_binding"], RUN_BINDING_KEYS, "B08_RUN_BINDING_INVALID")
    run = payload["run_binding"]
    if (
        any(
            not isinstance(run[key], str) or not run[key]
            for key in ("project_scope_id", "logical_run_key", "run_id")
        )
        or not _positive_int(run["logical_run_generation"])
        or not _non_negative_int(run["run_epoch"])
        or not _positive_int(run["finalized_from_state_revision"])
        or not _sha(run["finalized_from_state_hash"])
        or not _sha(payload["terminalization_key"])
        or not isinstance(payload["operation_id"], str)
        or not payload["operation_id"]
        or not _sha(payload["operation_request_hash"])
        or not _sha(payload["authority_snapshot_hash"])
        or payload["created_at"] != record["created_at"]
        or record["record_id"]
        != f"segment-terminal:{payload['terminalization_key']}"
    ):
        fail("B08_TERMINAL_PAYLOAD_INVALID")
    validate_segment_binding(payload["segment_binding"])
    validate_pointer_binding(payload["pointer_binding"])
    validate_classification_binding(payload["classification_binding"])
    if payload["terminalization_key"] != _terminalization_key_from_bindings(
        run, payload["segment_binding"]
    ):
        fail("B08_TERMINALIZATION_KEY_INVALID")
    merge_ref = payload["b06_merge_receipt_ref_or_null"]
    origin = payload["pointer_binding"]["candidate_origin"]
    if origin == "ROOT" and merge_ref is not None:
        fail("B08_B06_BINDING_UNEXPECTED")
    if origin == "B06_CHILD":
        if merge_ref is None:
            fail("B08_B06_BINDING_REQUIRED")
        _validate_ref(
            merge_ref,
            expected_type=MERGE_RECEIPT_TYPE,
            code="B08_B06_BINDING_INVALID",
        )
    if len(canonical_bytes(record)) > 32768:
        fail("B08_TERMINAL_RECORD_TOO_LARGE")


def terminal_record_ref(record: dict[str, Any]) -> dict[str, Any]:
    validate_terminal_record(record)
    return record_ref(record)


def terminal_component_observation(record: dict[str, Any]) -> dict[str, Any]:
    validate_terminal_record(record)
    artifact_sha = hashlib.sha256(canonical_bytes(record)).hexdigest()
    return {
        "component_kind": TERMINAL_COMPONENT_KIND,
        "component_artifact_ref": {
            "artifact_kind": TERMINAL_ARTIFACT_KIND,
            "workspace_relative_locator": (
                f"{WRITE_SET_PREFIX}records/{record['record_hash']}.json"
            ),
            "artifact_sha256": artifact_sha,
        },
    }


def validate_exact_current_view(view: Any) -> None:
    _exact_keys(view, EXACT_CURRENT_VIEW_KEYS, "B08_EXACT_VIEW_INVALID")
    _validate_ref(
        view["terminal_record_ref"],
        expected_type=TERMINAL_RECEIPT_TYPE,
        code="B08_EXACT_VIEW_INVALID",
    )
    if (
        view["view_type"] != EXACT_CURRENT_VIEW_TYPE
        or view["currentness"] not in CURRENTNESS_STATES
        or view["product_result"] not in PRODUCT_RESULTS
        or view["terminal_delivery"] not in TERMINAL_DELIVERIES
        or not isinstance(view["reason_code"], str)
        or not view["reason_code"]
        or not isinstance(view["run_id"], str)
        or not view["run_id"]
        or not _positive_int(view["logical_run_generation"])
        or not _non_negative_int(view["run_epoch"])
        or not _sha(view["current_state_hash"])
        or view["view_hash"]
        != sha256_value({key: value for key, value in view.items() if key != "view_hash"})
    ):
        fail("B08_EXACT_VIEW_INVALID")


def validate_adapter_ready_view(view: Any) -> None:
    _exact_keys(view, ADAPTER_READY_VIEW_KEYS, "B08_ADAPTER_VIEW_INVALID")
    _validate_ref(
        view["terminal_record_ref"],
        expected_type=TERMINAL_RECEIPT_TYPE,
        code="B08_ADAPTER_VIEW_INVALID",
    )
    candidate_ref = view["candidate_version_ref_or_null"]
    if candidate_ref is not None:
        _validate_ref(
            candidate_ref,
            expected_type="M3_CANDIDATE_VERSION",
            code="B08_ADAPTER_VIEW_INVALID",
        )
    if (
        view["view_type"] != ADAPTER_READY_VIEW_TYPE
        or not isinstance(view["ready"], bool)
        or not isinstance(view["reason_code"], str)
        or not view["reason_code"]
        or view["product_result"] not in PRODUCT_RESULTS
        or view["terminal_delivery"] not in TERMINAL_DELIVERIES
        or view["view_hash"]
        != sha256_value({key: value for key, value in view.items() if key != "view_hash"})
        or (view["ready"] and candidate_ref is None)
    ):
        fail("B08_ADAPTER_VIEW_INVALID")


def guard_runtime_event(event: str) -> None:
    forbidden = {
        "model_api",
        "network",
        "real_novel_read",
        "text_slice_read",
        "candidate_version_write",
        "pointer_write",
        "merge_receipt_write",
        "formal_fact_write",
        "ledger_truth_write",
        "b07_state_write",
        "derived_view_write",
        "subprocess",
    }
    if event in forbidden:
        fail("B08_FORBIDDEN_RUNTIME_EVENT", event)
