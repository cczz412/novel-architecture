"""Contracts for the disposable B-10 chapter candidate progress views."""

from __future__ import annotations

import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
for candidate in (REPOSITORY_ROOT, MODULE_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    validate_chapter_revision_ref,
    validate_record_ref as b01_validate_record_ref,
)
from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    canonical_bytes,
    sha256_value,
    validate_record_ref as b05_validate_record_ref,
)

INTERNAL_VIEW_TYPE = "M3_CURRENT_CHAPTER_CANDIDATE_PROGRESS_VIEW"
AUTHOR_VIEW_TYPE = "M3_AUTHOR_VISIBLE_CHAPTER_CANDIDATE_PROGRESS"
PURPOSE = "AUTHOR_VISIBLE_M3_CANDIDATE_PROGRESS"

AVAILABILITIES = {"READY", "UNAVAILABLE"}
PROCESSING_STATES = {
    "NOT_TRACKED",
    "IN_PROGRESS",
    "WAITING",
    "PARTIAL",
    "BLOCKED",
    "COMPLETE",
}
SEGMENT_STATES = {
    "NOT_TRACKED_YET",
    "RUNNING",
    "WAITING",
    "TERMINALIZING",
    "COMPLETE",
    "EMPTY_VALID",
    "PARTIAL",
    "BLOCKED",
    "STALE",
}
AUTHOR_ACTIONS = {"NONE", "WAIT", "REVIEW_INPUT", "RESTART", "REFRESH"}
NEGATIVE_WITNESSES = {"AUTHORITATIVE_NO_CURRENT_RUN", "TERMINAL_PENDING"}

REQUEST_KEYS = {
    "project_scope_id",
    "chapter_revision_ref",
    "segment_index_ref",
    "purpose",
}
SEGMENT_KEY_KEYS = {
    "project_scope_id",
    "author_workspace_logical_key",
    "chapter_revision_ref",
    "segment_index_ref",
    "seg",
}
SEGMENT_RESULT_KEYS = {
    "exact_segment_key",
    "segment_status",
    "run_state_or_null",
    "terminal_record_ref_or_null",
    "terminal_currentness_or_null",
    "product_result_or_null",
    "terminal_delivery_or_null",
    "authority_witness",
}
COUNT_KEYS = {
    "total_segments",
    "completed_segments",
    "empty_valid_segments",
    "running_segments",
    "waiting_segments",
    "attention_segments",
}
INTERNAL_VIEW_KEYS = {
    "view_type",
    "availability",
    "request",
    "candidate_processing_state",
    "counts",
    "segments",
    "has_blockers",
    "author_action_required",
    "author_action_kind",
    "complete_claim_allowed",
    "authority_fingerprint",
    "reason_code",
    "view_hash",
}
AUTHOR_VIEW_KEYS = {
    "availability",
    "candidate_processing_state",
    *COUNT_KEYS,
    "has_blockers",
    "author_action_required",
    "author_action_kind",
    "message_key",
}


class B10ContractError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


class B10AuthorityError(RuntimeError):
    def __init__(self, reason_code: str, detail: str = "") -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(
            f"{reason_code}: {detail}" if detail else reason_code
        )


def _fail(code: str, detail: str = "") -> None:
    raise B10ContractError(code, detail)


def _exact_keys(value: Any, expected: set[str], code: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        _fail(code)


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_request(request: Any) -> None:
    _exact_keys(request, REQUEST_KEYS, "B10_REQUEST_INVALID")
    try:
        validate_chapter_revision_ref(request["chapter_revision_ref"])
        b01_validate_record_ref(
            request["segment_index_ref"],
            expected_type="M3_SEGMENT_INDEX_SNAPSHOT",
        )
    except ValueError as error:
        _fail("B10_REQUEST_INVALID", str(error))
    if (
        not isinstance(request["project_scope_id"], str)
        or not request["project_scope_id"]
        or request["purpose"] != PURPOSE
    ):
        _fail("B10_REQUEST_INVALID")


def exact_segment_key(
    *,
    project_scope_id: str,
    author_workspace_logical_key: str,
    chapter_revision_ref: dict[str, Any],
    segment_index_ref: dict[str, Any],
    seg: int,
) -> dict[str, Any]:
    value = {
        "project_scope_id": project_scope_id,
        "author_workspace_logical_key": author_workspace_logical_key,
        "chapter_revision_ref": deepcopy(chapter_revision_ref),
        "segment_index_ref": deepcopy(segment_index_ref),
        "seg": seg,
    }
    validate_exact_segment_key(value)
    return value


def validate_exact_segment_key(value: Any) -> None:
    _exact_keys(value, SEGMENT_KEY_KEYS, "B10_SEGMENT_KEY_INVALID")
    try:
        validate_chapter_revision_ref(value["chapter_revision_ref"])
        b01_validate_record_ref(
            value["segment_index_ref"],
            expected_type="M3_SEGMENT_INDEX_SNAPSHOT",
        )
    except ValueError as error:
        _fail("B10_SEGMENT_KEY_INVALID", str(error))
    if (
        not isinstance(value["project_scope_id"], str)
        or not value["project_scope_id"]
        or not isinstance(value["author_workspace_logical_key"], str)
        or not value["author_workspace_logical_key"]
        or not isinstance(value["seg"], int)
        or isinstance(value["seg"], bool)
        or value["seg"] < 1
    ):
        _fail("B10_SEGMENT_KEY_INVALID")


def validate_segment_result(value: Any) -> None:
    _exact_keys(value, SEGMENT_RESULT_KEYS, "B10_SEGMENT_RESULT_INVALID")
    validate_exact_segment_key(value["exact_segment_key"])
    status = value["segment_status"]
    if status not in SEGMENT_STATES:
        _fail("B10_SEGMENT_RESULT_INVALID")
    run = value["run_state_or_null"]
    if run is not None and (
        not isinstance(run, dict)
        or set(run)
        != {
            "logical_run_key",
            "run_id",
            "logical_run_generation",
            "run_epoch",
            "state_revision",
            "state_hash",
            "status",
            "phase",
            "wait_kind",
            "author_action_required",
            "author_action_kind",
        }
        or not _sha(run["state_hash"])
    ):
        _fail("B10_SEGMENT_RESULT_INVALID")
    terminal_ref = value["terminal_record_ref_or_null"]
    if terminal_ref is not None:
        try:
            b05_validate_record_ref(
                terminal_ref,
                expected_type="M3_SEGMENT_CANDIDATE_TERMINAL_RECEIPT",
            )
        except ValueError as error:
            _fail("B10_SEGMENT_RESULT_INVALID", str(error))
    witness = value["authority_witness"]
    if not isinstance(witness, dict) or not isinstance(witness.get("kind"), str):
        _fail("B10_SEGMENT_RESULT_INVALID")
    if witness["kind"] in NEGATIVE_WITNESSES and terminal_ref is not None:
        _fail("B10_SEGMENT_RESULT_INVALID")
    if status == "NOT_TRACKED_YET" and witness["kind"] != "AUTHORITATIVE_NO_CURRENT_RUN":
        _fail("B10_SEGMENT_RESULT_INVALID")
    if status == "TERMINALIZING" and witness["kind"] != "TERMINAL_PENDING":
        _fail("B10_SEGMENT_RESULT_INVALID")


def validate_segment_set_closure(
    expected_segment_keys: list[dict[str, Any]],
    resolved_segment_keys: list[dict[str, Any]],
) -> None:
    for value in (*expected_segment_keys, *resolved_segment_keys):
        validate_exact_segment_key(value)
    expected = [canonical_bytes(value) for value in expected_segment_keys]
    resolved = [canonical_bytes(value) for value in resolved_segment_keys]
    if (
        len(expected) != len(set(expected))
        or len(resolved) != len(set(resolved))
        or set(expected) != set(resolved)
    ):
        _fail("B10_SEGMENT_SET_MISMATCH")


def validate_internal_view(view: Any) -> None:
    _exact_keys(view, INTERNAL_VIEW_KEYS, "B10_INTERNAL_VIEW_INVALID")
    validate_request(view["request"])
    if (
        view["view_type"] != INTERNAL_VIEW_TYPE
        or view["availability"] not in AVAILABILITIES
        or not isinstance(view["has_blockers"], bool)
        or not isinstance(view["author_action_required"], bool)
        or view["author_action_kind"] not in AUTHOR_ACTIONS
        or not isinstance(view["complete_claim_allowed"], bool)
        or not isinstance(view["reason_code"], str)
        or not view["reason_code"]
        or view["view_hash"]
        != sha256_value({key: value for key, value in view.items() if key != "view_hash"})
    ):
        _fail("B10_INTERNAL_VIEW_INVALID")
    if view["availability"] == "UNAVAILABLE":
        if (
            view["candidate_processing_state"] is not None
            or view["counts"] is not None
            or view["segments"] != []
            or view["complete_claim_allowed"]
            or view["authority_fingerprint"] is not None
        ):
            _fail("B10_UNAVAILABLE_LEAK")
        return
    if (
        view["candidate_processing_state"] not in PROCESSING_STATES
        or not isinstance(view["counts"], dict)
        or set(view["counts"]) != COUNT_KEYS
        or any(not _non_negative_int(item) for item in view["counts"].values())
        or not isinstance(view["segments"], list)
        or not view["segments"]
        or not isinstance(view["authority_fingerprint"], dict)
    ):
        _fail("B10_INTERNAL_VIEW_INVALID")
    for segment in view["segments"]:
        validate_segment_result(segment)
    keys = [segment["exact_segment_key"] for segment in view["segments"]]
    if keys != sorted(keys, key=lambda key: key["seg"]) or len(keys) != len(
        {canonical_bytes(key) for key in keys}
    ):
        _fail("B10_INTERNAL_VIEW_INVALID")
    counts = view["counts"]
    if counts["total_segments"] != len(view["segments"]):
        _fail("B10_INTERNAL_VIEW_INVALID")
    complete = view["candidate_processing_state"] == "COMPLETE"
    if view["complete_claim_allowed"] != complete:
        _fail("B10_INTERNAL_VIEW_INVALID")


def validate_author_view(view: Any) -> None:
    _exact_keys(view, AUTHOR_VIEW_KEYS, "B10_AUTHOR_VIEW_INVALID")
    if (
        view["availability"] not in AVAILABILITIES
        or view["candidate_processing_state"] not in PROCESSING_STATES | {None}
        or not isinstance(view["has_blockers"], bool)
        or not isinstance(view["author_action_required"], bool)
        or view["author_action_kind"] not in AUTHOR_ACTIONS
        or not isinstance(view["message_key"], str)
        or not view["message_key"]
    ):
        _fail("B10_AUTHOR_VIEW_INVALID")
    count_values = [view[key] for key in COUNT_KEYS]
    if view["availability"] == "UNAVAILABLE":
        if any(item is not None for item in count_values):
            _fail("B10_AUTHOR_VIEW_INVALID")
    elif any(not _non_negative_int(item) for item in count_values):
        _fail("B10_AUTHOR_VIEW_INVALID")
