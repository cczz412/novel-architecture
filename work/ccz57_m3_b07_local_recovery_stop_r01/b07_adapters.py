"""Zero-network adapters at the B-07 boundaries."""

from __future__ import annotations

import hashlib
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    record_ref,
    sha256_value,
)

from b07_contracts import fail, validate_component_observation  # noqa: E402

SavedResultReader = Callable[[str], bytes]

SAVED_ARTIFACT_KEYS = {
    "component_kind",
    "artifact_kind",
    "workspace_relative_locator",
    "artifact_sha256",
}


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


def verify_saved_artifact(
    envelope: dict[str, Any], *, reader: SavedResultReader
) -> dict[str, Any]:
    if not isinstance(envelope, dict) or set(envelope) != SAVED_ARTIFACT_KEYS:
        fail("B07_CCZ142_OBSERVATION_SHAPE_INVALID")
    if any(
        not isinstance(envelope[key], str) or not envelope[key]
        for key in (
            "component_kind",
            "artifact_kind",
            "workspace_relative_locator",
        )
    ) or not _sha(envelope["artifact_sha256"]):
        fail("B07_CCZ142_OBSERVATION_VALUE_INVALID")
    observation = {
        "component_kind": envelope["component_kind"],
        "component_artifact_ref": {
            "artifact_kind": envelope["artifact_kind"],
            "workspace_relative_locator": envelope["workspace_relative_locator"],
            "artifact_sha256": envelope["artifact_sha256"],
        },
    }
    validate_component_observation(observation)
    try:
        raw = reader(envelope["workspace_relative_locator"])
    except Exception as error:
        fail("B07_CCZ142_SAVED_RESULT_UNAVAILABLE", str(error))
    if (
        not isinstance(raw, bytes)
        or not raw
        or hashlib.sha256(raw).hexdigest() != envelope["artifact_sha256"]
    ):
        fail("B07_CCZ142_SAVED_RESULT_HASH_MISMATCH")
    return observation


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
