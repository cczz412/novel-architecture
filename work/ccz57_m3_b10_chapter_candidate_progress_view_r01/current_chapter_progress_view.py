"""Pure derivation and author-safe projection for B-10."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import sha256_value

if __package__:
    from .b10_contracts import (
        AUTHOR_VIEW_KEYS,
        INTERNAL_VIEW_TYPE,
        B10AuthorityError,
        B10ContractError,
        validate_author_view,
        validate_internal_view,
        validate_request,
        validate_segment_set_closure,
    )
else:
    from b10_contracts import (
        AUTHOR_VIEW_KEYS,
        INTERNAL_VIEW_TYPE,
        B10AuthorityError,
        B10ContractError,
        validate_author_view,
        validate_internal_view,
        validate_request,
        validate_segment_set_closure,
    )


def _processing_state(statuses: list[str]) -> str:
    completed = {"COMPLETE", "EMPTY_VALID"}
    if all(status in completed for status in statuses):
        return "COMPLETE"
    if all(status == "NOT_TRACKED_YET" for status in statuses):
        return "NOT_TRACKED"
    if any(
        status in {"RUNNING", "TERMINALIZING", "NOT_TRACKED_YET"}
        for status in statuses
    ):
        return "IN_PROGRESS"
    if any(status in {"BLOCKED", "STALE"} for status in statuses):
        return "BLOCKED"
    if any(status == "PARTIAL" for status in statuses):
        return "PARTIAL"
    return "WAITING"


def _author_action(segments: list[dict[str, Any]], state: str) -> tuple[bool, str]:
    candidates: set[str] = set()
    for segment in segments:
        status = segment["segment_status"]
        run = segment["run_state_or_null"]
        upstream = None if run is None else run["author_action_kind"]
        if upstream in {"WAIT", "REVIEW_INPUT", "RESTART", "REFRESH"}:
            candidates.add(upstream)
        if status == "STALE":
            candidates.add("REFRESH")
        elif status == "PARTIAL":
            candidates.add("REVIEW_INPUT")
        elif status == "BLOCKED" and upstream is None:
            candidates.add("REVIEW_INPUT")
    for action in ("WAIT", "REFRESH", "REVIEW_INPUT", "RESTART"):
        if action in candidates:
            return action != "WAIT", action
    if state == "COMPLETE":
        return False, "NONE"
    return False, "WAIT"


def _counts(segments: list[dict[str, Any]]) -> dict[str, int]:
    statuses = [segment["segment_status"] for segment in segments]
    return {
        "total_segments": len(segments),
        "completed_segments": sum(
            status in {"COMPLETE", "EMPTY_VALID"} for status in statuses
        ),
        "empty_valid_segments": statuses.count("EMPTY_VALID"),
        "running_segments": statuses.count("RUNNING"),
        "waiting_segments": statuses.count("WAITING"),
        "attention_segments": sum(
            status in {"TERMINALIZING", "PARTIAL", "BLOCKED", "STALE"}
            for status in statuses
        ),
    }


def build_ready_view(
    request: dict[str, Any], snapshot: dict[str, Any]
) -> dict[str, Any]:
    validate_request(request)
    expected = snapshot["expected_segment_keys"]
    segments = sorted(
        deepcopy(snapshot["segment_results"]),
        key=lambda item: item["exact_segment_key"]["seg"],
    )
    resolved = [segment["exact_segment_key"] for segment in segments]
    validate_segment_set_closure(expected, resolved)
    statuses = [segment["segment_status"] for segment in segments]
    state = _processing_state(statuses)
    counts = _counts(segments)
    has_blockers = any(
        status in {"TERMINALIZING", "PARTIAL", "BLOCKED", "STALE"}
        for status in statuses
    )
    action_required, action_kind = _author_action(segments, state)
    view = {
        "view_type": INTERNAL_VIEW_TYPE,
        "availability": "READY",
        "request": deepcopy(request),
        "candidate_processing_state": state,
        "counts": counts,
        "segments": segments,
        "has_blockers": has_blockers,
        "author_action_required": action_required,
        "author_action_kind": action_kind,
        "complete_claim_allowed": state == "COMPLETE",
        "authority_fingerprint": deepcopy(snapshot["authority_fingerprint"]),
        "reason_code": "CURRENT_AUTHORITY_RESOLVED",
        "view_hash": "",
    }
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )
    validate_internal_view(view)
    return view


def build_unavailable_view(
    request: dict[str, Any], *, reason_code: str
) -> dict[str, Any]:
    validate_request(request)
    view = {
        "view_type": INTERNAL_VIEW_TYPE,
        "availability": "UNAVAILABLE",
        "request": deepcopy(request),
        "candidate_processing_state": None,
        "counts": None,
        "segments": [],
        "has_blockers": False,
        "author_action_required": False,
        "author_action_kind": "NONE",
        "complete_claim_allowed": False,
        "authority_fingerprint": None,
        "reason_code": reason_code,
        "view_hash": "",
    }
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )
    validate_internal_view(view)
    return view


def read_current_chapter_progress(
    authority_reader: Any, request: dict[str, Any]
) -> dict[str, Any]:
    validate_request(request)
    try:
        return build_ready_view(request, authority_reader.read(request))
    except B10AuthorityError as error:
        return build_unavailable_view(request, reason_code=error.reason_code)
    except B10ContractError:
        raise
    except Exception:
        return build_unavailable_view(
            request, reason_code="AUTHORITY_READER_UNAVAILABLE"
        )


def project_author_progress(view: dict[str, Any]) -> dict[str, Any]:
    validate_internal_view(view)
    counts = view["counts"]
    projected = {
        "availability": view["availability"],
        "candidate_processing_state": view["candidate_processing_state"],
        "total_segments": None if counts is None else counts["total_segments"],
        "completed_segments": (
            None if counts is None else counts["completed_segments"]
        ),
        "empty_valid_segments": (
            None if counts is None else counts["empty_valid_segments"]
        ),
        "running_segments": None if counts is None else counts["running_segments"],
        "waiting_segments": None if counts is None else counts["waiting_segments"],
        "attention_segments": (
            None if counts is None else counts["attention_segments"]
        ),
        "has_blockers": view["has_blockers"],
        "author_action_required": view["author_action_required"],
        "author_action_kind": view["author_action_kind"],
        "message_key": (
            "M3_CANDIDATE_PROGRESS_UNAVAILABLE"
            if view["availability"] == "UNAVAILABLE"
            else f"M3_CANDIDATE_PROGRESS_{view['candidate_processing_state']}"
        ),
    }
    if set(projected) != AUTHOR_VIEW_KEYS:
        raise B10ContractError("B10_AUTHOR_VIEW_INVALID")
    validate_author_view(projected)
    return projected
