"""Zero-network adapters at the B-07 boundaries."""

from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    canonical_bytes,
    record_ref,
    sha256_value,
    validate_record_ref,
)

from b07_contracts import fail  # noqa: E402

SavedResultReader = Callable[[str], bytes]

SAVED_OBSERVATION_KEYS = {
    "project_scope_id",
    "run_id",
    "expected_run_epoch",
    "expected_state_revision",
    "observation_id",
    "observation_kind",
    "component_kind",
    "component_contract_version",
    "saved_result_locator",
    "saved_result_sha256",
    "saved_result_ref",
    "result_class",
    "next_phase_hint",
    "error_fingerprint",
    "experiment_context_hash",
}
OBSERVATION_KINDS = {
    "COMPONENT_RESULT",
    "BUDGET_STOP",
    "RETRY_STOP",
    "NO_PROGRESS_STOP",
    "TRANSIENT_SIGNAL",
}
RESULT_CLASSES = {"SUCCESS", "WAIT", "RETRYABLE_FAILURE", "STOP_RECOMMENDED"}


def derive_b06_request_hash(
    *,
    project_scope_id: str,
    logical_pointer_key: str,
    operation_id: str,
    route_receipt_ref: dict[str, Any],
    route_unit_id: str,
    patch_proposal: dict[str, Any],
    protection_set: dict[str, Any],
    committed_at: str,
    run_fence: dict[str, Any],
) -> str:
    """Mirror B-06's public request preimage at the orchestration seam."""

    return sha256_value(
        {
            "project_scope_id": project_scope_id,
            "logical_pointer_key": logical_pointer_key,
            "operation_id": operation_id,
            "route_receipt_ref": deepcopy(route_receipt_ref),
            "route_unit_id": route_unit_id,
            "patch_proposal_ref": record_ref(patch_proposal),
            "protection_set_ref": record_ref(protection_set),
            "committed_at": committed_at,
            "run_fence": deepcopy(run_fence),
        }
    )


def accept_saved_observation(
    envelope: dict[str, Any], *, reader: SavedResultReader
) -> dict[str, Any]:
    if not isinstance(envelope, dict) or set(envelope) != SAVED_OBSERVATION_KEYS:
        fail("B07_CCZ142_OBSERVATION_SHAPE_INVALID")
    if (
        any(
            not isinstance(envelope[key], str) or not envelope[key]
            for key in (
                "project_scope_id",
                "run_id",
                "observation_id",
                "component_kind",
                "component_contract_version",
                "saved_result_locator",
            )
        )
        or any(
            not isinstance(envelope[key], int)
            or isinstance(envelope[key], bool)
            or envelope[key] < 0
            for key in ("expected_run_epoch", "expected_state_revision")
        )
        or envelope["observation_kind"] not in OBSERVATION_KINDS
        or envelope["result_class"] not in RESULT_CLASSES
        or not _sha(envelope["saved_result_sha256"])
        or (
            envelope["error_fingerprint"] is not None
            and not _sha(envelope["error_fingerprint"])
        )
        or (
            envelope["experiment_context_hash"] is not None
            and not _sha(envelope["experiment_context_hash"])
        )
    ):
        fail("B07_CCZ142_OBSERVATION_VALUE_INVALID")
    try:
        validate_record_ref(envelope["saved_result_ref"])
        raw = reader(envelope["saved_result_locator"])
    except Exception as error:
        fail("B07_CCZ142_SAVED_RESULT_UNAVAILABLE", str(error))
    if (
        not isinstance(raw, bytes)
        or hashlib.sha256(raw).hexdigest() != envelope["saved_result_sha256"]
    ):
        fail("B07_CCZ142_SAVED_RESULT_HASH_MISMATCH")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        fail("B07_CCZ142_SAVED_RESULT_INVALID", str(error))
    if not isinstance(parsed, dict):
        fail("B07_CCZ142_SAVED_RESULT_INVALID")
    try:
        actual_ref = record_ref(parsed)
    except ValueError as error:
        fail("B07_CCZ142_SAVED_RESULT_INVALID", str(error))
    if canonical_bytes(actual_ref) != canonical_bytes(envelope["saved_result_ref"]):
        fail("B07_CCZ142_SAVED_RESULT_REF_MISMATCH")
    return {
        "component_kind": envelope["component_kind"],
        "component_receipt_ref": deepcopy(envelope["saved_result_ref"]),
        "component_result_hash": envelope["saved_result_sha256"],
    }


def assert_author_payload_safe(payload: Any) -> None:
    """Reject internal/debug fields recursively before an author-facing write."""

    forbidden_exact = {
        "record_id",
        "record_hash",
        "internal_error_code",
        "stop_reason_code",
        "error_fingerprint",
        "prompt",
        "raw_prompt",
        "raw_request",
        "raw_response",
        "request_hash",
        "response_hash",
        "prompt_hash",
        "retry_count",
        "tool_call_count",
        "absolute_path",
        "experiment_context_hash",
    }
    forbidden_prefixes = (
        "token",
        "cost",
        "fee",
        "latency",
        "provider",
        "session",
        "stack",
        "trace",
    )
    if isinstance(payload, dict):
        for key, value in payload.items():
            if (
                not isinstance(key, str)
                or key in forbidden_exact
                or key.startswith(forbidden_prefixes)
                or key in {"debug", "internal_debug"}
            ):
                fail("B07_AUTHOR_PAYLOAD_INTERNAL_FIELD")
            assert_author_payload_safe(value)
    elif isinstance(payload, list):
        for value in payload:
            assert_author_payload_safe(value)


def _sha(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
