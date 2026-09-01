"""B-07 local run-state, stop, debug, and derived-resume contracts."""

from __future__ import annotations

import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

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
from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    validate_chapter_revision_ref,
)

CURRENT_RUN_STATE_TYPE = "M3_CURRENT_RUN_STATE"
STOP_RECEIPT_TYPE = "M3_RUN_STOP_RECEIPT"
DEBUG_RECORD_TYPE = "M3_RUN_INTERNAL_DEBUG_RECORD"
RESUME_PLAN_TYPE = "M3_DERIVED_RESUME_PLAN"
ACCESS_MAINTAINER_INTERNAL = "MAINTAINER_INTERNAL"

RUN_STATUSES = {
    "NEW",
    "ACTIVE",
    "WAITING_LOCAL",
    "B06_OUTCOME_PENDING",
    "SUCCEEDED",
    "STOPPED",
}
NONTERMINAL_STATUSES = RUN_STATUSES - {"SUCCEEDED", "STOPPED"}
WAIT_KINDS = {None, "LOCAL_COMPONENT", "AUTHOR_ACTION", "LOCAL_BACKOFF"}
RUN_PHASES = {
    "EXTRACTING",
    "CHECKING",
    "REPAIRING",
    "COMMITTING",
    "FINALIZING",
    "DONE",
}
STOP_REASONS = {
    "BUDGET_EXHAUSTED",
    "PERMISSION_INACTIVE",
    "INPUT_REVISION_DRIFT",
    "ROUTE_STOP",
    "B06_NOT_PUBLISHED",
    "B06_POINTER_CONFLICT",
    "UNRECOVERABLE_COMPONENT_FAILURE",
    "LOCAL_STORAGE_INTEGRITY_FAILURE",
    "LOCAL_AUTHORITY_MISSING",
    "NO_PROGRESS_LIMIT",
    "RETRY_LIMIT",
    "AUTHOR_ABORTED",
}
RESUME_DISPOSITIONS = {
    "CONTINUE_SAME_RUN",
    "RECONCILE_B06_THEN_CONTINUE",
    "REOPEN_NEW_RUN",
    "DO_NOT_RESUME",
    "MAINTENANCE_REQUIRED",
}
B06_OUTCOMES = {
    "COMMITTED",
    "NOT_PUBLISHED",
    "CONFLICT",
    "NOT_APPLICABLE",
    "INTEGRITY_FAILURE",
}

AUTHORITY_SNAPSHOT_KEYS = {
    "chapter_revision_ref",
    "segment_scope_hash",
    "candidate_pointer_key",
    "observed_pointer_generation",
    "observed_candidate_version_ref",
    "budget_state_ref",
    "budget_state_hash",
    "budget_revision",
    "budget_allows_continue",
    "permission_state_ref",
    "permission_state_hash",
    "permission_revision",
    "permission_active",
    "route_decision_ref",
    "route_decision_hash",
}
PENDING_B06_KEYS = {
    "kind",
    "operation_id",
    "request_hash",
    "expected_pointer_key",
    "expected_pointer_generation",
    "expected_candidate_version_ref",
}
OBSERVATION_KEYS = {
    "component_kind",
    "component_receipt_ref",
    "component_result_hash",
}
CURRENT_RUN_STATE_KEYS = {
    "schema_version",
    "record_type",
    "project_scope_id",
    "logical_run_key",
    "run_id",
    "logical_run_generation",
    "run_kind",
    "run_epoch",
    "state_revision",
    "state_hash",
    "status",
    "phase",
    "wait_kind",
    "authority_snapshot",
    "last_component_observation",
    "pending_local_action",
    "reopened_from_stop_receipt_ref",
    "stop_receipt_ref",
    "created_at",
    "updated_at",
}
STOP_PAYLOAD_KEYS = {
    "project_scope_id",
    "logical_run_key",
    "run_id",
    "logical_run_generation",
    "run_epoch",
    "stopped_from_state_revision",
    "stop_operation_id",
    "stop_request_hash",
    "stop_reason_code",
    "stop_class",
    "stop_source",
    "authority_snapshot",
    "last_durable_phase",
    "last_component_observation",
    "pending_local_action",
    "retainable_candidate_version_ref",
    "resume_disposition",
    "terminalization_required",
    "created_at",
}
DEBUG_PAYLOAD_KEYS = {
    "project_scope_id",
    "run_id",
    "run_epoch",
    "state_revision",
    "event_kind",
    "component_kind",
    "source_receipt_ref",
    "source_receipt_hash",
    "stop_receipt_ref",
    "internal_error_code",
    "error_category",
    "error_fingerprint",
    "request_hash",
    "response_hash",
    "prompt_hash",
    "stack_fingerprint",
    "token_counts",
    "cost_microunits",
    "currency",
    "latency_ms",
    "retry_count",
    "tool_call_count",
    "provider_route_hash",
    "model_profile_hash",
    "created_at",
    "retention_expires_at",
    "access_class",
    "debug_payload_bytes",
}
RESUME_PLAN_KEYS = {
    "view_type",
    "run_id",
    "source_run_epoch",
    "source_state_revision",
    "source_state_hash",
    "authority_snapshot_hash",
    "b06_outcome",
    "disposition",
    "next_phase",
    "preconditions",
    "plan_hash",
}


class B07ContractError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def fail(code: str, detail: str = "") -> None:
    raise B07ContractError(code, detail)


def _exact_keys(value: Any, expected: set[str], code: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        fail(code)


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _validate_ref_or_none(value: Any, *, code: str) -> None:
    if value is None:
        return
    try:
        validate_record_ref(value)
    except ValueError as error:
        fail(code, str(error))


def validate_authority_snapshot(snapshot: Any) -> None:
    _exact_keys(snapshot, AUTHORITY_SNAPSHOT_KEYS, "B07_AUTHORITY_SHAPE_INVALID")
    try:
        validate_chapter_revision_ref(snapshot["chapter_revision_ref"])
    except ValueError as error:
        fail("B07_AUTHORITY_REF_INVALID", str(error))
    for key in (
        "observed_candidate_version_ref",
        "budget_state_ref",
        "permission_state_ref",
    ):
        _validate_ref_or_none(snapshot[key], code="B07_AUTHORITY_REF_INVALID")
        if snapshot[key] is None:
            fail("B07_AUTHORITY_REF_INVALID", key)
    _validate_ref_or_none(
        snapshot["route_decision_ref"], code="B07_AUTHORITY_REF_INVALID"
    )
    if (
        not _sha(snapshot["segment_scope_hash"])
        or not isinstance(snapshot["candidate_pointer_key"], str)
        or not snapshot["candidate_pointer_key"]
        or not _positive_int(snapshot["observed_pointer_generation"])
        or not _sha(snapshot["budget_state_hash"])
        or not _non_negative_int(snapshot["budget_revision"])
        or not isinstance(snapshot["budget_allows_continue"], bool)
        or not _sha(snapshot["permission_state_hash"])
        or not _non_negative_int(snapshot["permission_revision"])
        or not isinstance(snapshot["permission_active"], bool)
        or (snapshot["route_decision_ref"] is None)
        != (snapshot["route_decision_hash"] is None)
        or (
            snapshot["route_decision_hash"] is not None
            and not _sha(snapshot["route_decision_hash"])
        )
    ):
        fail("B07_AUTHORITY_VALUE_INVALID")


def validate_pending_local_action(value: Any) -> None:
    _exact_keys(value, PENDING_B06_KEYS, "B07_PENDING_ACTION_INVALID")
    if (
        value["kind"] != "B06_PUBLISH"
        or any(
            not isinstance(value[key], str) or not value[key]
            for key in ("operation_id", "expected_pointer_key")
        )
        or not _sha(value["request_hash"])
        or not _positive_int(value["expected_pointer_generation"])
    ):
        fail("B07_PENDING_ACTION_INVALID")
    _validate_ref_or_none(
        value["expected_candidate_version_ref"], code="B07_PENDING_ACTION_INVALID"
    )
    if value["expected_candidate_version_ref"] is None:
        fail("B07_PENDING_ACTION_INVALID")


def validate_component_observation(value: Any) -> None:
    _exact_keys(value, OBSERVATION_KEYS, "B07_OBSERVATION_INVALID")
    if not isinstance(value["component_kind"], str) or not value["component_kind"]:
        fail("B07_OBSERVATION_INVALID")
    _validate_ref_or_none(
        value["component_receipt_ref"], code="B07_OBSERVATION_INVALID"
    )
    if value["component_receipt_ref"] is None or not _sha(
        value["component_result_hash"]
    ):
        fail("B07_OBSERVATION_INVALID")


def state_hash_value(state: dict[str, Any]) -> str:
    return sha256_value(
        {
            key: value
            for key, value in state.items()
            if key not in {"state_hash", "created_at", "updated_at"}
        }
    )


def validate_current_run_state(state: Any) -> None:
    _exact_keys(state, CURRENT_RUN_STATE_KEYS, "B07_RUN_STATE_SHAPE_INVALID")
    if (
        state["schema_version"] != CONTRACT_VERSION
        or state["record_type"] != CURRENT_RUN_STATE_TYPE
        or any(
            not isinstance(state[key], str) or not state[key]
            for key in (
                "project_scope_id",
                "logical_run_key",
                "run_id",
                "run_kind",
                "created_at",
                "updated_at",
            )
        )
        or not _positive_int(state["logical_run_generation"])
        or not _non_negative_int(state["run_epoch"])
        or not _positive_int(state["state_revision"])
        or state["status"] not in RUN_STATUSES
        or state["phase"] not in RUN_PHASES
        or state["wait_kind"] not in WAIT_KINDS
        or state["state_hash"] != state_hash_value(state)
        or len(canonical_bytes(state)) > 8192
    ):
        fail("B07_RUN_STATE_VALUE_INVALID")
    validate_authority_snapshot(state["authority_snapshot"])
    if state["last_component_observation"] is not None:
        validate_component_observation(state["last_component_observation"])
    if state["pending_local_action"] is not None:
        validate_pending_local_action(state["pending_local_action"])
    _validate_ref_or_none(
        state["reopened_from_stop_receipt_ref"], code="B07_RUN_STATE_REF_INVALID"
    )
    _validate_ref_or_none(state["stop_receipt_ref"], code="B07_RUN_STATE_REF_INVALID")
    if (
        (state["status"] == "B06_OUTCOME_PENDING")
        != (state["pending_local_action"] is not None)
        or (state["status"] == "STOPPED") != (state["stop_receipt_ref"] is not None)
        or (state["status"] == "WAITING_LOCAL" and state["wait_kind"] is None)
        or (state["status"] != "WAITING_LOCAL" and state["wait_kind"] is not None)
        or (state["status"] in {"SUCCEEDED", "STOPPED"} and state["phase"] != "DONE")
    ):
        fail("B07_RUN_STATE_INVARIANT_INVALID")


def build_current_run_state(
    *,
    project_scope_id: str,
    logical_run_key: str,
    run_id: str,
    logical_run_generation: int,
    run_kind: str,
    authority_snapshot: dict[str, Any],
    created_at: str,
    reopened_from_stop_receipt_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = {
        "schema_version": CONTRACT_VERSION,
        "record_type": CURRENT_RUN_STATE_TYPE,
        "project_scope_id": project_scope_id,
        "logical_run_key": logical_run_key,
        "run_id": run_id,
        "logical_run_generation": logical_run_generation,
        "run_kind": run_kind,
        "run_epoch": 0,
        "state_revision": 1,
        "state_hash": "",
        "status": "ACTIVE",
        "phase": "EXTRACTING",
        "wait_kind": None,
        "authority_snapshot": deepcopy(authority_snapshot),
        "last_component_observation": None,
        "pending_local_action": None,
        "reopened_from_stop_receipt_ref": deepcopy(reopened_from_stop_receipt_ref),
        "stop_receipt_ref": None,
        "created_at": created_at,
        "updated_at": created_at,
    }
    state["state_hash"] = state_hash_value(state)
    validate_current_run_state(state)
    return state


def rehash_state(state: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(state)
    updated["state_hash"] = state_hash_value(updated)
    validate_current_run_state(updated)
    return updated


def _build_immutable_record(
    *, record_type: str, record_id: str, payload: dict[str, Any], created_at: str
) -> dict[str, Any]:
    record = {
        "contract": IMMUTABLE_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "record_type": record_type,
        "record_id": record_id,
        "record_version": 1,
        "record_contract_version": CONTRACT_VERSION,
        "record_hash": "",
        "source_module": SOURCE_MODULE,
        "access": RUN_ACCESS,
        "retention_class": RETENTION_CLASS,
        "created_at": created_at,
        "payload": deepcopy(payload),
    }
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    validate_immutable_record(record)
    return record


def build_stop_receipt(*, payload: dict[str, Any], created_at: str) -> dict[str, Any]:
    record = _build_immutable_record(
        record_type=STOP_RECEIPT_TYPE,
        record_id=f"run-stop:{sha256_value(payload)}",
        payload=payload,
        created_at=created_at,
    )
    validate_stop_receipt(record)
    return record


def validate_stop_receipt(record: Any) -> None:
    try:
        validate_immutable_record(record, expected_type=STOP_RECEIPT_TYPE)
    except ValueError as error:
        fail("B07_STOP_RECEIPT_INVALID", str(error))
    payload = record["payload"]
    _exact_keys(payload, STOP_PAYLOAD_KEYS, "B07_STOP_PAYLOAD_INVALID")
    if (
        any(
            not isinstance(payload[key], str) or not payload[key]
            for key in (
                "project_scope_id",
                "logical_run_key",
                "run_id",
                "stop_operation_id",
                "stop_class",
                "stop_source",
                "created_at",
            )
        )
        or not _positive_int(payload["logical_run_generation"])
        or not _non_negative_int(payload["run_epoch"])
        or not _positive_int(payload["stopped_from_state_revision"])
        or not _sha(payload["stop_request_hash"])
        or payload["stop_reason_code"] not in STOP_REASONS
        or payload["last_durable_phase"] not in RUN_PHASES
        or payload["resume_disposition"] not in RESUME_DISPOSITIONS
        or payload["terminalization_required"] is not True
        or payload["created_at"] != record["created_at"]
        or record["record_id"] != f"run-stop:{sha256_value(payload)}"
        or len(canonical_bytes(record)) > 8192
    ):
        fail("B07_STOP_PAYLOAD_INVALID")
    validate_authority_snapshot(payload["authority_snapshot"])
    if payload["last_component_observation"] is not None:
        validate_component_observation(payload["last_component_observation"])
    if payload["pending_local_action"] is not None:
        validate_pending_local_action(payload["pending_local_action"])
    _validate_ref_or_none(
        payload["retainable_candidate_version_ref"],
        code="B07_STOP_PAYLOAD_INVALID",
    )


def build_debug_record(*, payload: dict[str, Any], created_at: str) -> dict[str, Any]:
    record = _build_immutable_record(
        record_type=DEBUG_RECORD_TYPE,
        record_id=f"run-debug:{sha256_value(payload)}",
        payload=payload,
        created_at=created_at,
    )
    validate_debug_record(record)
    return record


def validate_debug_record(record: Any) -> None:
    try:
        validate_immutable_record(record, expected_type=DEBUG_RECORD_TYPE)
    except ValueError as error:
        fail("B07_DEBUG_RECORD_INVALID", str(error))
    payload = record["payload"]
    _exact_keys(payload, DEBUG_PAYLOAD_KEYS, "B07_DEBUG_PAYLOAD_INVALID")
    for value in payload.values():
        _reject_raw_debug_value(value)
    if (
        any(
            not isinstance(payload[key], str) or not payload[key]
            for key in (
                "project_scope_id",
                "run_id",
                "event_kind",
                "error_category",
                "created_at",
                "retention_expires_at",
            )
        )
        or not _non_negative_int(payload["run_epoch"])
        or not _positive_int(payload["state_revision"])
        or payload["access_class"] != ACCESS_MAINTAINER_INTERNAL
        or not _non_negative_int(payload["debug_payload_bytes"])
        or payload["debug_payload_bytes"] > 4096
        or payload["created_at"] != record["created_at"]
        or any(
            value is not None and not _sha(value)
            for value in (
                payload["source_receipt_hash"],
                payload["error_fingerprint"],
                payload["request_hash"],
                payload["response_hash"],
                payload["prompt_hash"],
                payload["stack_fingerprint"],
                payload["provider_route_hash"],
                payload["model_profile_hash"],
            )
        )
    ):
        fail("B07_DEBUG_PAYLOAD_INVALID")
    for key in ("source_receipt_ref", "stop_receipt_ref"):
        _validate_ref_or_none(payload[key], code="B07_DEBUG_PAYLOAD_INVALID")
    for key in (
        "cost_microunits",
        "latency_ms",
        "retry_count",
        "tool_call_count",
    ):
        if payload[key] is not None and not _non_negative_int(payload[key]):
            fail("B07_DEBUG_PAYLOAD_INVALID", key)
    if payload["token_counts"] is not None:
        if not isinstance(payload["token_counts"], dict) or any(
            not _non_negative_int(value) for value in payload["token_counts"].values()
        ):
            fail("B07_DEBUG_PAYLOAD_INVALID", "token_counts")
    expected_payload_bytes = len(
        canonical_bytes(
            {
                key: value
                for key, value in payload.items()
                if key != "debug_payload_bytes"
            }
        )
    )
    if payload["debug_payload_bytes"] != expected_payload_bytes:
        fail("B07_DEBUG_PAYLOAD_BYTES_INVALID")
    try:
        created = datetime.strptime(
            payload["created_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        expires = datetime.strptime(
            payload["retention_expires_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
    except ValueError as error:
        fail("B07_DEBUG_RETENTION_INVALID", str(error))
    retention_seconds = (expires - created).total_seconds()
    if retention_seconds <= 0 or retention_seconds > 30 * 24 * 60 * 60:
        fail("B07_DEBUG_RETENTION_INVALID")
    if (payload["source_receipt_ref"] is None) != (
        payload["source_receipt_hash"] is None
    ):
        fail("B07_DEBUG_SOURCE_BINDING_INVALID")
    if len(canonical_bytes(record)) > 4096:
        fail("B07_DEBUG_RECORD_TOO_LARGE")


def _reject_raw_debug_value(value: Any) -> None:
    if isinstance(value, dict):
        forbidden = {
            "prompt",
            "raw_prompt",
            "raw_request",
            "raw_response",
            "novel_text",
            "stack",
            "trace",
            "absolute_path",
            "session_id",
        }
        if set(value) & forbidden:
            fail("B07_DEBUG_RAW_FIELD_FORBIDDEN")
        for nested in value.values():
            _reject_raw_debug_value(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_raw_debug_value(nested)


def build_resume_plan(
    *,
    state: dict[str, Any],
    authority_snapshot: dict[str, Any],
    b06_outcome: str,
    disposition: str,
    next_phase: str,
    preconditions: list[str],
) -> dict[str, Any]:
    validate_current_run_state(state)
    validate_authority_snapshot(authority_snapshot)
    plan = {
        "view_type": "DERIVED_RECOMPUTABLE",
        "run_id": state["run_id"],
        "source_run_epoch": state["run_epoch"],
        "source_state_revision": state["state_revision"],
        "source_state_hash": state["state_hash"],
        "authority_snapshot_hash": sha256_value(authority_snapshot),
        "b06_outcome": b06_outcome,
        "disposition": disposition,
        "next_phase": next_phase,
        "preconditions": sorted(set(preconditions)),
        "plan_hash": "",
    }
    plan["plan_hash"] = sha256_value(
        {key: value for key, value in plan.items() if key != "plan_hash"}
    )
    validate_resume_plan(plan)
    return plan


def validate_resume_plan(plan: Any) -> None:
    _exact_keys(plan, RESUME_PLAN_KEYS, "B07_RESUME_PLAN_INVALID")
    if (
        plan["view_type"] != "DERIVED_RECOMPUTABLE"
        or not isinstance(plan["run_id"], str)
        or not plan["run_id"]
        or not _non_negative_int(plan["source_run_epoch"])
        or not _positive_int(plan["source_state_revision"])
        or not _sha(plan["source_state_hash"])
        or not _sha(plan["authority_snapshot_hash"])
        or plan["b06_outcome"] not in B06_OUTCOMES
        or plan["disposition"] not in RESUME_DISPOSITIONS
        or plan["next_phase"] not in RUN_PHASES
        or not isinstance(plan["preconditions"], list)
        or any(not isinstance(item, str) or not item for item in plan["preconditions"])
        or plan["preconditions"] != sorted(set(plan["preconditions"]))
        or plan["plan_hash"]
        != sha256_value(
            {key: value for key, value in plan.items() if key != "plan_hash"}
        )
    ):
        fail("B07_RESUME_PLAN_INVALID")


def stop_receipt_ref(record: dict[str, Any]) -> dict[str, Any]:
    validate_stop_receipt(record)
    return record_ref(record)


def debug_record_ref(record: dict[str, Any]) -> dict[str, Any]:
    validate_debug_record(record)
    return record_ref(record)


def project_author_status(state: dict[str, Any]) -> dict[str, Any]:
    validate_current_run_state(state)
    status_class = {
        "NEW": "RUNNING",
        "ACTIVE": "RUNNING",
        "WAITING_LOCAL": "WAITING",
        "B06_OUTCOME_PENDING": "RUNNING",
        "SUCCEEDED": "CONTROL_SUCCEEDED",
        "STOPPED": "STOPPED",
    }[state["status"]]
    action_kind = "NONE"
    if state["status"] == "STOPPED":
        action_kind = "RESTART"
    elif state["wait_kind"] == "AUTHOR_ACTION":
        action_kind = "REVIEW_INPUT"
    return {
        "run_status_class": status_class,
        "phase_class": ("FINALIZING" if state["phase"] == "DONE" else state["phase"]),
        "author_action_required": action_kind != "NONE",
        "author_action_kind": action_kind,
        "terminalization_pending": state["status"] == "STOPPED",
    }
