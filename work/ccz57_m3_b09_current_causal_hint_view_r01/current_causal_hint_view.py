"""Pure projection of a verified B-09 authority snapshot."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B05_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b05_patch_route_r03_5"
for candidate in (REPOSITORY_ROOT, MODULE_ROOT, B05_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    B05ContractError,
    canonical_bytes,
    record_ref,
    sha256_value,
)
from patch_route_projection import B09AdmissionGuard  # noqa: E402

from b09_contracts import (  # noqa: E402
    B09AuthorityError,
    B09ContractError,
    build_error_view,
    build_view,
    scope_from_authority,
    stable_unique,
)


class _PostCommitUnsafe(ValueError):
    pass


def _ref_equal(left: Any, right: Any) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def _view_from_snapshot(
    snapshot: dict[str, Any],
    *,
    status: str,
    reason_code: str,
    phase: str = "NOT_APPLICABLE",
    hints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return build_view(
        status=status,
        reason_code=reason_code,
        scope=scope_from_authority(snapshot, phase=phase),
        hints=[] if hints is None else hints,
    )


def _error_from_snapshot(snapshot: dict[str, Any], reason_code: str) -> dict[str, Any]:
    return _view_from_snapshot(
        snapshot,
        status="ERROR",
        reason_code=reason_code,
    )


def _proposal_for_ref(snapshot: dict[str, Any], ref: dict[str, Any]) -> dict[str, Any]:
    matches = [
        item
        for item in snapshot["causal_hint_proposals"]
        if _ref_equal(record_ref(item), ref)
    ]
    if len(matches) != 1:
        raise B09AuthorityError(
            "AUTHORITY_REFERENCE_CONFLICT", "proposal not uniquely resolved"
        )
    return matches[0]


def _mapping_for_ref(
    validation_receipt: dict[str, Any], ref: dict[str, Any]
) -> dict[str, Any]:
    matches = [
        item
        for item in validation_receipt["payload"]["causal_support_mappings"]
        if _ref_equal(item["causal_hint_proposal_ref"], ref)
    ]
    if len(matches) != 1:
        raise B09AuthorityError(
            "AUTHORITY_REFERENCE_CONFLICT", "mapping not uniquely resolved"
        )
    mapping = matches[0]
    expected_hash = sha256_value(
        {key: value for key, value in mapping.items() if key != "mapping_proof_hash"}
    )
    if mapping["mapping_proof_hash"] != expected_hash:
        raise B09AuthorityError("AUTHORITY_HASH_MISMATCH", "mapping proof hash")
    return mapping


def _lineage_locator(
    candidate: dict[str, Any], lineage_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    matches = [
        (index, item)
        for index, item in enumerate(candidate["payload"]["items"])
        if item.get("lineage_id") == lineage_id
    ]
    if len(matches) != 1:
        raise B09AuthorityError("AUTHORITY_REFERENCE_CONFLICT", "lineage is not unique")
    index, item = matches[0]
    locator = {
        "contract": "M3_LINEAGE_LOCATOR",
        "contract_version": candidate["contract_version"],
        "candidate_version_ref": record_ref(candidate),
        "lineage_id": lineage_id,
        "json_pointer": f"/items/{index}",
        "item_hash": item["item_hash"],
        "locator_hash": "",
    }
    locator["locator_hash"] = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    return locator, item


def _evidence_locator(
    candidate: dict[str, Any], lineage_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    matches = [
        (index, item)
        for index, item in enumerate(candidate["payload"]["items"])
        if item.get("lineage_id") == lineage_id
    ]
    if len(matches) != 1:
        raise B09AuthorityError(
            "AUTHORITY_REFERENCE_CONFLICT", "evidence lineage is not unique"
        )
    index, item = matches[0]
    binding = item.get("evidence_binding")
    if not isinstance(binding, dict) or not {
        "evidence_sha256",
        "binding_hash",
    } <= set(binding):
        raise B09AuthorityError("AUTHORITY_STATE_INCOHERENT", "evidence binding")
    locator = {
        "contract": "M3_EVIDENCE_LOCATOR",
        "contract_version": candidate["contract_version"],
        "candidate_version_ref": record_ref(candidate),
        "lineage_id": lineage_id,
        "evidence_json_pointer": f"/items/{index}/evidence",
        "evidence_sha256": binding["evidence_sha256"],
        "binding_hash": binding["binding_hash"],
        "locator_hash": "",
    }
    locator["locator_hash"] = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    return locator, item


def _resolve_lineage(
    *,
    original: dict[str, Any],
    base_candidate: dict[str, Any],
    current_candidate: dict[str, Any],
    post_commit: bool,
) -> dict[str, Any]:
    required = {
        "contract",
        "contract_version",
        "candidate_version_ref",
        "lineage_id",
        "json_pointer",
        "item_hash",
        "locator_hash",
    }
    if not isinstance(original, dict) or set(original) != required:
        raise B09AuthorityError("AUTHORITY_REFERENCE_CONFLICT", "lineage locator shape")
    base_locator, _ = _lineage_locator(base_candidate, original["lineage_id"])
    if not _ref_equal(base_locator, original):
        raise B09AuthorityError(
            "AUTHORITY_REFERENCE_CONFLICT", "proposal lineage is not exact base"
        )
    try:
        current_locator, _ = _lineage_locator(
            current_candidate, original["lineage_id"]
        )
    except B09AuthorityError as error:
        if post_commit:
            raise _PostCommitUnsafe("endpoint lineage unavailable") from error
        raise
    if post_commit and current_locator["item_hash"] != original["item_hash"]:
        raise _PostCommitUnsafe("endpoint item hash changed")
    if not post_commit and not _ref_equal(current_locator, original):
        raise B09AuthorityError(
            "AUTHORITY_REFERENCE_CONFLICT", "pre-commit lineage drift"
        )
    return current_locator


def _resolve_evidence(
    *,
    original: dict[str, Any],
    base_candidate: dict[str, Any],
    current_candidate: dict[str, Any],
    post_commit: bool,
) -> dict[str, Any]:
    required = {
        "contract",
        "contract_version",
        "candidate_version_ref",
        "lineage_id",
        "evidence_json_pointer",
        "evidence_sha256",
        "binding_hash",
        "locator_hash",
    }
    if not isinstance(original, dict) or set(original) != required:
        raise B09AuthorityError(
            "AUTHORITY_REFERENCE_CONFLICT", "evidence locator shape"
        )
    base_locator, _ = _evidence_locator(base_candidate, original["lineage_id"])
    if not _ref_equal(base_locator, original):
        raise B09AuthorityError(
            "AUTHORITY_REFERENCE_CONFLICT", "proposal evidence is not exact base"
        )
    try:
        current_locator, _ = _evidence_locator(
            current_candidate, original["lineage_id"]
        )
    except B09AuthorityError as error:
        if post_commit:
            raise _PostCommitUnsafe("evidence lineage unavailable") from error
        raise
    if post_commit and (
        current_locator["evidence_sha256"] != original["evidence_sha256"]
        or current_locator["binding_hash"] != original["binding_hash"]
    ):
        raise _PostCommitUnsafe("evidence binding changed")
    if not post_commit and not _ref_equal(current_locator, original):
        raise B09AuthorityError(
            "AUTHORITY_REFERENCE_CONFLICT", "pre-commit evidence drift"
        )
    return current_locator


def _support_set(
    proposal: dict[str, Any], mapping: dict[str, Any]
) -> tuple[list[Any], list[Any], list[Any]]:
    payload = proposal["payload"]
    diagnostic_refs = stable_unique(payload.get("diagnostic_refs", []))
    coverage_refs = stable_unique(payload.get("coverage_observation_refs", []))
    source_refs = stable_unique(payload.get("authorized_source_slice_refs", []))
    proposal_support = stable_unique([*diagnostic_refs, *coverage_refs, *source_refs])
    mapping_support = stable_unique(
        entry["support_ref"] for entry in mapping["support_ref_ownership"]
    )
    if canonical_bytes(proposal_support) != canonical_bytes(mapping_support):
        raise B09AuthorityError(
            "AUTHORITY_REFERENCE_CONFLICT", "proposal/mapping support set"
        )
    return diagnostic_refs, coverage_refs, source_refs


def _guard_error(error: B05ContractError) -> B09AuthorityError:
    if any(
        token in error.code
        for token in ("POINTER_STALE", "SCOPE_STALE", "POLICY_STALE", "GATE_STALE")
    ):
        return B09AuthorityError("AUTHORITY_DRIFT", error.code)
    if "HASH" in error.code or "INVALID" in error.code:
        return B09AuthorityError("AUTHORITY_HASH_MISMATCH", error.code)
    return B09AuthorityError("AUTHORITY_REFERENCE_CONFLICT", error.code)


def _phase(snapshot: dict[str, Any]) -> tuple[str, str]:
    route = snapshot["active_route"]
    validation = snapshot["validation_receipt"]
    pointer = snapshot["current_pointer"]
    current_candidate = snapshot["current_candidate"]
    merge_receipt = snapshot["merge_receipt_or_null"]
    base_ref = validation["payload"]["input_binding"]["base_candidate_version_ref"]
    current_ref = pointer["current_candidate_version_ref"]
    route_bound_hash = route["payload"]["binding_header"]["live_pointer_binding_hash"]
    current_hash = sha256_value(pointer)
    if _ref_equal(current_ref, base_ref) and current_hash == route_bound_hash:
        return "PRE_COMMIT_CURRENT", current_hash
    if merge_receipt is None:
        raise _PostCommitUnsafe("exact merge receipt absent")
    receipt = merge_receipt["payload"]
    if (
        not _ref_equal(
            current_candidate["payload"]["parent_candidate_version_ref"], base_ref
        )
        or not _ref_equal(receipt["base_candidate_version_ref"], base_ref)
        or not _ref_equal(receipt["child_candidate_version_ref"], current_ref)
        or receipt["pointer_logical_key"] != pointer["logical_pointer_key"]
        or receipt["pointer_binding_hash_before"] != route_bound_hash
        or receipt["pointer_binding_hash_after"] != current_hash
        or receipt["pointer_generation_after"] != pointer["generation"]
        or receipt["pointer_generation_before"] + 1 != pointer["generation"]
        or not _ref_equal(receipt["route_receipt_ref"], record_ref(route))
    ):
        raise _PostCommitUnsafe("pointer is not the exact committed child")
    return "POST_COMMIT_EXACT_CHILD", route_bound_hash


def _hint(
    snapshot: dict[str, Any],
    *,
    entry: dict[str, Any],
    phase: str,
    route_bound_pointer_hash: str,
) -> dict[str, Any]:
    route = snapshot["active_route"]
    validation = snapshot["validation_receipt"]
    proposal_ref = entry["causal_hint_proposal_ref"]
    proposal = _proposal_for_ref(snapshot, proposal_ref)
    mapping = _mapping_for_ref(validation, proposal_ref)
    if (
        mapping["mapping_status"] != "COMPLETE"
        or mapping["mapping_proof_hash"] != entry["mapping_proof_hash"]
        or mapping["supporting_route_unit_ids"] != entry["supporting_route_unit_ids"]
    ):
        raise B09AuthorityError("AUTHORITY_REFERENCE_CONFLICT", "route/mapping binding")
    try:
        B09AdmissionGuard.require_route(
            snapshot["b05_records"],
            route_receipt_ref=record_ref(route),
            causal_hint_proposal_ref=proposal_ref,
            mapping_proof_hash=entry["mapping_proof_hash"],
            live_pointer_binding_hash=route_bound_pointer_hash,
            b02_scope_snapshot_hash=snapshot["freshness"]["b02_scope_snapshot_hash"],
            active_policy_selection_hash=snapshot["freshness"][
                "active_policy_selection_hash"
            ],
            non_content_gate_snapshot_hash=snapshot["freshness"][
                "non_content_gate_snapshot_hash"
            ],
        )
    except B05ContractError as error:
        raise _guard_error(error) from error

    post_commit = phase == "POST_COMMIT_EXACT_CHILD"
    supporting_units = stable_unique(entry["supporting_route_unit_ids"])
    if post_commit:
        receipt = snapshot["merge_receipt_or_null"]["payload"]
        if (
            len(supporting_units) != 1
            or receipt["route_unit_id"] != supporting_units[0]
        ):
            raise _PostCommitUnsafe("not one exact supporting route unit")
    payload = proposal["payload"]
    from_locator = _resolve_lineage(
        original=payload["from_lineage_locator"],
        base_candidate=snapshot["base_candidate"],
        current_candidate=snapshot["current_candidate"],
        post_commit=post_commit,
    )
    to_locator = _resolve_lineage(
        original=payload["to_lineage_locator"],
        base_candidate=snapshot["base_candidate"],
        current_candidate=snapshot["current_candidate"],
        post_commit=post_commit,
    )
    evidence = stable_unique(
        _resolve_evidence(
            original=locator,
            base_candidate=snapshot["base_candidate"],
            current_candidate=snapshot["current_candidate"],
            post_commit=post_commit,
        )
        for locator in payload["evidence_locators"]
    )
    diagnostic_refs, coverage_refs, source_refs = _support_set(proposal, mapping)
    return {
        "ordinal": 0,
        "causal_hint_proposal_ref": deepcopy(proposal_ref),
        "route_receipt_ref": record_ref(route),
        "lifecycle_head_ref": deepcopy(snapshot["lifecycle_head_ref"]),
        "mapping_proof_hash": entry["mapping_proof_hash"],
        "supporting_route_unit_ids": supporting_units,
        "hint_kind": payload["hint_kind"],
        "current_from_lineage_locator": from_locator,
        "current_to_lineage_locator": to_locator,
        "current_evidence_locators": evidence,
        "diagnostic_refs": diagnostic_refs,
        "coverage_observation_refs": coverage_refs,
        "authorized_source_slice_refs": source_refs,
        "advisory_only": True,
        "committable": False,
        "author_visible": False,
        "cross_run_reusable": False,
        "exportable": False,
    }


def project_current_causal_hints(
    authority_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Purely derive one view; no cache, writer, model, or network side effect."""

    try:
        request = authority_snapshot["request"]
        state = authority_snapshot["run_state"]
        state_authority = state["authority_snapshot"]
        pointer = authority_snapshot["current_pointer"]
        if (
            request["run_id"] != state["run_id"]
            or request["expected_logical_run_generation"]
            != state["logical_run_generation"]
            or request["expected_run_epoch"] != state["run_epoch"]
        ):
            return _view_from_snapshot(
                authority_snapshot,
                status="CLOSED",
                reason_code="REQUEST_RUN_IDENTITY_STALE",
            )
        if request["segment_scope_hash"] != state_authority["segment_scope_hash"]:
            return _view_from_snapshot(
                authority_snapshot,
                status="CLOSED",
                reason_code="REQUEST_SCOPE_STALE",
            )
        if authority_snapshot["exact_current_terminal_ref_or_null"] is not None:
            return _view_from_snapshot(
                authority_snapshot,
                status="CLOSED",
                reason_code="EXACT_CURRENT_SEGMENT_TERMINAL",
            )
        if state["status"] == "STOPPED":
            return _view_from_snapshot(
                authority_snapshot,
                status="CLOSED",
                reason_code="RUN_STOPPED",
            )
        if (
            state["status"] not in {"NEW", "ACTIVE", "WAITING_LOCAL"}
            or not state_authority["budget_allows_continue"]
            or not state_authority["permission_active"]
            or pointer["chapter_revision_ref"]
            != state_authority["chapter_revision_ref"]
            or pointer["seg"]
            != authority_snapshot["current_candidate"]["payload"]["seg"]
        ):
            return _error_from_snapshot(
                authority_snapshot, "AUTHORITY_STATE_INCOHERENT"
            )
        route = authority_snapshot["active_route"]
        if route is None:
            return _view_from_snapshot(
                authority_snapshot,
                status="EMPTY",
                reason_code="NO_ROUTE_TO_B09",
            )
        entries = [
            entry
            for entry in route["payload"]["causal_hint_routes"]
            if entry["route"] == "ROUTE_TO_B09"
        ]
        if not entries:
            return _view_from_snapshot(
                authority_snapshot,
                status="EMPTY",
                reason_code="NO_ROUTE_TO_B09",
            )
        try:
            phase, route_bound_pointer_hash = _phase(authority_snapshot)
            hints = [
                _hint(
                    authority_snapshot,
                    entry=entry,
                    phase=phase,
                    route_bound_pointer_hash=route_bound_pointer_hash,
                )
                for entry in entries
            ]
        except _PostCommitUnsafe:
            return _view_from_snapshot(
                authority_snapshot,
                status="EMPTY",
                reason_code="POST_COMMIT_NOT_PROVABLY_UNCHANGED",
            )
        exact_key = lambda hint: canonical_bytes(  # noqa: E731
            {
                "causal_hint_proposal_ref": hint["causal_hint_proposal_ref"],
                "route_receipt_ref": hint["route_receipt_ref"],
                "mapping_proof_hash": hint["mapping_proof_hash"],
            }
        )
        hints = sorted(hints, key=exact_key)
        for ordinal, hint in enumerate(hints, start=1):
            hint["ordinal"] = ordinal
        if not hints:
            return _view_from_snapshot(
                authority_snapshot,
                status="EMPTY",
                reason_code="NO_SAFE_CURRENT_HINT",
            )
        return _view_from_snapshot(
            authority_snapshot,
            status="AVAILABLE",
            reason_code="CURRENT_HINTS_AVAILABLE",
            phase=phase,
            hints=hints,
        )
    except B09AuthorityError as error:
        return _error_from_snapshot(authority_snapshot, error.reason_code)
    except (B09ContractError, KeyError, TypeError, ValueError):
        return _error_from_snapshot(authority_snapshot, "AUTHORITY_STATE_INCOHERENT")


def read_current_causal_hints(reader: Any, request: dict[str, Any]) -> dict[str, Any]:
    """Read current authority once and turn only closed reader errors into ERROR."""

    try:
        snapshot = reader.read(request)
    except B09AuthorityError as error:
        return build_error_view(error.reason_code)
    return project_current_causal_hints(snapshot)
