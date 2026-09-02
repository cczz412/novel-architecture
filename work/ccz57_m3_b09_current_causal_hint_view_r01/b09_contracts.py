"""Contracts for the non-persistent B-09 current causal-hint view."""

from __future__ import annotations

import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    B01ContractError,
    CONTRACT_VERSION as B01_CONTRACT_VERSION,
    EVIDENCE_LOCATOR_CONTRACT,
    FIXTURE_ACCESS as B01_FIXTURE_ACCESS,
    LINEAGE_LOCATOR_CONTRACT,
    SOURCE_MODULE as B01_SOURCE_MODULE,
    validate_chapter_revision_ref as b01_validate_chapter_revision_ref,
    validate_lineage_locator as b01_validate_lineage_locator,
    validate_record_ref as b01_validate_record_ref,
)
from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    canonical_bytes,
    sha256_value,
    validate_record_ref,
)

CONTRACT_VERSION = "b09-r01"
VIEW_TYPE = "DERIVED_RECOMPUTABLE"
PURPOSE = "CCZ142_READ_ONLY_FEEDBACK"

STATUSES = {"AVAILABLE", "EMPTY", "CLOSED", "ERROR"}
REASONS_BY_STATUS = {
    "AVAILABLE": {"CURRENT_HINTS_AVAILABLE"},
    "EMPTY": {
        "NO_ROUTE_TO_B09",
        "NO_SAFE_CURRENT_HINT",
        "POST_COMMIT_NOT_PROVABLY_UNCHANGED",
    },
    "CLOSED": {
        "RUN_STOPPED",
        "REQUEST_RUN_IDENTITY_STALE",
        "REQUEST_SCOPE_STALE",
        "EXACT_CURRENT_SEGMENT_TERMINAL",
    },
    "ERROR": {
        "AUTHORITY_READER_UNAVAILABLE",
        "AUTHORITY_REFERENCE_CONFLICT",
        "AUTHORITY_HASH_MISMATCH",
        "AUTHORITY_DRIFT",
        "AUTHORITY_STATE_INCOHERENT",
    },
}
PHASES = {"PRE_COMMIT_CURRENT", "POST_COMMIT_EXACT_CHILD", "NOT_APPLICABLE"}

REQUEST_KEYS = {
    "project_scope_id",
    "run_id",
    "expected_logical_run_generation",
    "expected_run_epoch",
    "segment_scope_hash",
    "purpose",
}
SCOPE_KEYS = {
    "project_scope_id",
    "logical_run_key",
    "run_id",
    "logical_run_generation",
    "run_epoch",
    "segment_scope_hash",
    "chapter_revision_ref",
    "seg",
    "pointer_logical_key",
    "pointer_generation",
    "current_candidate_version_ref",
    "authority_fingerprint_hash",
    "phase",
}
HINT_KEYS = {
    "ordinal",
    "causal_hint_proposal_ref",
    "route_receipt_ref",
    "lifecycle_head_ref",
    "mapping_proof_hash",
    "supporting_route_unit_ids",
    "hint_kind",
    "current_from_lineage_locator",
    "current_to_lineage_locator",
    "current_evidence_locators",
    "diagnostic_refs",
    "coverage_observation_refs",
    "authorized_source_slice_refs",
    "advisory_only",
    "committable",
    "author_visible",
    "cross_run_reusable",
    "exportable",
}
VIEW_KEYS = {
    "view_type",
    "contract_version",
    "status",
    "reason_code",
    "scope",
    "hints",
    "view_hash",
}
FORBIDDEN_OUTPUT_KEYS = {
    "record_id",
    "record_version",
    "created_at",
    "expires_at",
    "retention_class",
    "manifest_ref",
    "lifecycle_sequence",
    "store_key",
    "formal_causal_edge_ref",
}
LINEAGE_LOCATOR_KEYS = {
    "contract",
    "contract_version",
    "candidate_version_ref",
    "lineage_id",
    "json_pointer",
    "item_hash",
    "locator_hash",
}
EVIDENCE_LOCATOR_KEYS = {
    "contract",
    "contract_version",
    "candidate_version_ref",
    "lineage_id",
    "evidence_json_pointer",
    "evidence_sha256",
    "binding_hash",
    "locator_hash",
}


class B09ContractError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


class B09AuthorityError(RuntimeError):
    """A closed error vocabulary that can safely become an ERROR view."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        if reason_code not in REASONS_BY_STATUS["ERROR"]:
            raise B09ContractError("B09_AUTHORITY_ERROR_REASON_INVALID", reason_code)
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)


def fail(code: str, detail: str = "") -> None:
    raise B09ContractError(code, detail)


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _exact_keys(value: Any, expected: set[str], code: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        fail(code)


def stable_unique(values: Iterable[Any]) -> list[Any]:
    """Deep-copy, de-duplicate, and order values using the current canonical bytes."""

    unique: dict[bytes, Any] = {}
    for value in values:
        unique[canonical_bytes(value)] = deepcopy(value)
    return [unique[key] for key in sorted(unique)]


def validate_request(request: Any) -> None:
    _exact_keys(request, REQUEST_KEYS, "B09_REQUEST_SHAPE_INVALID")
    if (
        not isinstance(request["project_scope_id"], str)
        or not request["project_scope_id"]
        or not isinstance(request["run_id"], str)
        or not request["run_id"]
        or not _positive_int(request["expected_logical_run_generation"])
        or not _non_negative_int(request["expected_run_epoch"])
        or not _sha(request["segment_scope_hash"])
        or request["purpose"] != PURPOSE
    ):
        fail("B09_REQUEST_VALUE_INVALID")


def null_scope() -> dict[str, Any]:
    scope = {key: None for key in SCOPE_KEYS}
    scope["phase"] = "NOT_APPLICABLE"
    return scope


def scope_from_authority(
    authority_snapshot: dict[str, Any], *, phase: str
) -> dict[str, Any]:
    if phase not in PHASES:
        fail("B09_PHASE_INVALID")
    state = authority_snapshot["run_state"]
    pointer = authority_snapshot["current_pointer"]
    state_authority = state["authority_snapshot"]
    return {
        "project_scope_id": state["project_scope_id"],
        "logical_run_key": state["logical_run_key"],
        "run_id": state["run_id"],
        "logical_run_generation": state["logical_run_generation"],
        "run_epoch": state["run_epoch"],
        "segment_scope_hash": state_authority["segment_scope_hash"],
        "chapter_revision_ref": deepcopy(state_authority["chapter_revision_ref"]),
        "seg": pointer["seg"],
        "pointer_logical_key": pointer["logical_pointer_key"],
        "pointer_generation": pointer["generation"],
        "current_candidate_version_ref": deepcopy(
            pointer["current_candidate_version_ref"]
        ),
        "authority_fingerprint_hash": sha256_value(
            authority_snapshot["authority_fingerprint"]
        ),
        "phase": phase,
    }


def build_view(
    *,
    status: str,
    reason_code: str,
    scope: dict[str, Any],
    hints: list[dict[str, Any]],
) -> dict[str, Any]:
    view = {
        "view_type": VIEW_TYPE,
        "contract_version": CONTRACT_VERSION,
        "status": status,
        "reason_code": reason_code,
        "scope": deepcopy(scope),
        "hints": deepcopy(hints),
        "view_hash": "",
    }
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )
    validate_view(view)
    return view


def build_error_view(reason_code: str) -> dict[str, Any]:
    return build_view(
        status="ERROR",
        reason_code=reason_code,
        scope=null_scope(),
        hints=[],
    )


def _validate_ref(value: Any, expected_type: str, code: str) -> None:
    try:
        validate_record_ref(value, expected_type=expected_type)
    except ValueError as error:
        fail(code, str(error))


def _validate_canonical_unique(values: Any, code: str) -> None:
    if not isinstance(values, list) or values != stable_unique(values):
        fail(code)


def _validate_lineage_locator(value: Any) -> None:
    _exact_keys(value, LINEAGE_LOCATOR_KEYS, "B09_HINT_LINEAGE_LOCATOR_INVALID")
    try:
        b01_validate_lineage_locator(value)
    except (B01ContractError, TypeError, ValueError) as error:
        fail("B09_HINT_LINEAGE_LOCATOR_INVALID", str(error))
    if (
        value["contract"] != LINEAGE_LOCATOR_CONTRACT
        or value["contract_version"] != B01_CONTRACT_VERSION
        or not isinstance(value["lineage_id"], str)
        or re.fullmatch(r"lin_[0-9a-f]{64}", value["lineage_id"]) is None
        or not isinstance(value["json_pointer"], str)
        or re.fullmatch(r"/items/(0|[1-9][0-9]*)", value["json_pointer"]) is None
        or not _sha(value["item_hash"])
        or not _sha(value["locator_hash"])
    ):
        fail("B09_HINT_LINEAGE_LOCATOR_INVALID")


def _validate_evidence_locator(value: Any) -> None:
    _exact_keys(value, EVIDENCE_LOCATOR_KEYS, "B09_HINT_EVIDENCE_LOCATOR_INVALID")
    if (
        value["contract"] != EVIDENCE_LOCATOR_CONTRACT
        or value["contract_version"] != B01_CONTRACT_VERSION
        or not isinstance(value["lineage_id"], str)
        or re.fullmatch(r"lin_[0-9a-f]{64}", value["lineage_id"]) is None
        or not isinstance(value["evidence_json_pointer"], str)
        or re.fullmatch(
            r"/items/(0|[1-9][0-9]*)/evidence",
            value["evidence_json_pointer"],
        )
        is None
        or not _sha(value["evidence_sha256"])
        or not _sha(value["binding_hash"])
        or not _sha(value["locator_hash"])
    ):
        fail("B09_HINT_EVIDENCE_LOCATOR_INVALID")
    try:
        b01_validate_record_ref(
            value["candidate_version_ref"],
            code="B09_HINT_EVIDENCE_LOCATOR_INVALID",
            expected_type="M3_CANDIDATE_VERSION",
            expected_access=B01_FIXTURE_ACCESS,
            expected_source_module=B01_SOURCE_MODULE,
            expected_contract_version=B01_CONTRACT_VERSION,
        )
    except (B01ContractError, TypeError, ValueError) as error:
        fail("B09_HINT_EVIDENCE_LOCATOR_INVALID", str(error))
    if value["locator_hash"] != sha256_value(
        {key: item for key, item in value.items() if key != "locator_hash"}
    ):
        fail("B09_HINT_EVIDENCE_LOCATOR_INVALID", "locator hash")


def _validate_populated_scope(scope: dict[str, Any]) -> None:
    if (
        any(
            not isinstance(scope[key], str) or not scope[key]
            for key in (
                "project_scope_id",
                "logical_run_key",
                "run_id",
                "pointer_logical_key",
            )
        )
        or not _sha(scope["segment_scope_hash"])
        or not _sha(scope["authority_fingerprint_hash"])
        or not _positive_int(scope["logical_run_generation"])
        or not _non_negative_int(scope["run_epoch"])
        or not _positive_int(scope["seg"])
        or not _positive_int(scope["pointer_generation"])
    ):
        fail("B09_SCOPE_VALUE_INVALID")
    try:
        b01_validate_chapter_revision_ref(scope["chapter_revision_ref"])
    except (B01ContractError, TypeError, ValueError) as error:
        fail("B09_SCOPE_CHAPTER_REVISION_INVALID", str(error))
    try:
        b01_validate_record_ref(
            scope["current_candidate_version_ref"],
            code="B09_SCOPE_CANDIDATE_REF_INVALID",
            expected_type="M3_CANDIDATE_VERSION",
            expected_access=B01_FIXTURE_ACCESS,
            expected_source_module=B01_SOURCE_MODULE,
            expected_contract_version=B01_CONTRACT_VERSION,
        )
    except (B01ContractError, TypeError, ValueError) as error:
        fail("B09_SCOPE_CANDIDATE_REF_INVALID", str(error))


def validate_view(view: Any) -> None:
    _exact_keys(view, VIEW_KEYS, "B09_VIEW_SHAPE_INVALID")
    if (
        view["view_type"] != VIEW_TYPE
        or view["contract_version"] != CONTRACT_VERSION
        or view["status"] not in STATUSES
        or view["reason_code"] not in REASONS_BY_STATUS.get(view["status"], set())
        or not _sha(view["view_hash"])
    ):
        fail("B09_VIEW_VALUE_INVALID")
    _exact_keys(view["scope"], SCOPE_KEYS, "B09_SCOPE_SHAPE_INVALID")
    scope = view["scope"]
    if scope["phase"] not in PHASES:
        fail("B09_PHASE_INVALID")
    if view["status"] == "AVAILABLE":
        if (
            scope["phase"]
            not in {
                "PRE_COMMIT_CURRENT",
                "POST_COMMIT_EXACT_CHILD",
            }
            or not view["hints"]
        ):
            fail("B09_AVAILABLE_INVARIANT_INVALID")
    elif scope["phase"] != "NOT_APPLICABLE" or view["hints"]:
        fail("B09_NONAVAILABLE_INVARIANT_INVALID")
    if view["status"] != "ERROR" and any(
        scope[key] is None for key in SCOPE_KEYS if key != "phase"
    ):
        fail("B09_SCOPE_CURRENT_AUTHORITY_REQUIRED")
    if view["status"] == "ERROR" and any(
        value is not None for key, value in scope.items() if key != "phase"
    ):
        # ERROR views produced from a fully verified snapshot may carry current scope,
        # but a partial mixture is forbidden.  Callers either provide all or none.
        if any(scope[key] is None for key in SCOPE_KEYS if key != "phase"):
            fail("B09_ERROR_SCOPE_PARTIAL")
    if all(scope[key] is not None for key in SCOPE_KEYS if key != "phase"):
        _validate_populated_scope(scope)

    if not isinstance(view["hints"], list):
        fail("B09_HINTS_INVALID")
    exact_keys: list[dict[str, Any]] = []
    for expected_ordinal, hint in enumerate(view["hints"], start=1):
        _exact_keys(hint, HINT_KEYS, "B09_HINT_SHAPE_INVALID")
        if (
            hint["ordinal"] != expected_ordinal
            or not _sha(hint["mapping_proof_hash"])
            or not isinstance(hint["hint_kind"], str)
            or not hint["hint_kind"]
            or hint["advisory_only"] is not True
            or hint["committable"] is not False
            or hint["author_visible"] is not False
            or hint["cross_run_reusable"] is not False
            or hint["exportable"] is not False
        ):
            fail("B09_HINT_VALUE_INVALID")
        _validate_ref(
            hint["causal_hint_proposal_ref"],
            "M3_CAUSAL_HINT_PROPOSAL",
            "B09_HINT_REF_INVALID",
        )
        _validate_ref(
            hint["route_receipt_ref"],
            "M3_PATCH_ROUTE_RECEIPT",
            "B09_HINT_REF_INVALID",
        )
        _validate_ref(
            hint["lifecycle_head_ref"],
            "M3_PATCH_LIFECYCLE_RECEIPT",
            "B09_HINT_REF_INVALID",
        )
        for key in (
            "supporting_route_unit_ids",
            "current_evidence_locators",
            "diagnostic_refs",
            "coverage_observation_refs",
            "authorized_source_slice_refs",
        ):
            _validate_canonical_unique(hint[key], "B09_HINT_ORDER_INVALID")
        if not hint["supporting_route_unit_ids"] or any(
            not isinstance(item, str) or not item
            for item in hint["supporting_route_unit_ids"]
        ):
            fail("B09_HINT_SUPPORT_INVALID")
        for locator in (
            hint["current_from_lineage_locator"],
            hint["current_to_lineage_locator"],
        ):
            _validate_lineage_locator(locator)
            if (
                locator["candidate_version_ref"]
                != scope["current_candidate_version_ref"]
            ):
                fail("B09_HINT_LINEAGE_LOCATOR_INVALID", "candidate ref")
        for locator in hint["current_evidence_locators"]:
            _validate_evidence_locator(locator)
            if (
                locator["candidate_version_ref"]
                != scope["current_candidate_version_ref"]
            ):
                fail("B09_HINT_EVIDENCE_LOCATOR_INVALID", "candidate ref")
        for key, expected_type in (
            ("diagnostic_refs", "M3_DIAGNOSTIC"),
            ("coverage_observation_refs", "M3_COVERAGE_OBSERVATION"),
            ("authorized_source_slice_refs", "M3_AUTHORIZED_SOURCE_SLICE"),
        ):
            for ref in hint[key]:
                _validate_ref(ref, expected_type, "B09_HINT_REF_INVALID")
        exact_keys.append(
            {
                "causal_hint_proposal_ref": hint["causal_hint_proposal_ref"],
                "route_receipt_ref": hint["route_receipt_ref"],
                "mapping_proof_hash": hint["mapping_proof_hash"],
            }
        )
    if exact_keys != sorted(exact_keys, key=canonical_bytes):
        fail("B09_HINT_ORDER_INVALID")
    # Record refs necessarily carry record_id/record_version.  The prohibition
    # applies to B-09-owned top-level fields, whose exact-key contracts above
    # prevent persistent identity or lifecycle metadata from being added.
    if FORBIDDEN_OUTPUT_KEYS & (set(view) | set(scope)):
        fail("B09_FORBIDDEN_OUTPUT_FIELD")
    if any(FORBIDDEN_OUTPUT_KEYS & set(hint) for hint in view["hints"]):
        fail("B09_FORBIDDEN_OUTPUT_FIELD")
    if view["view_hash"] != sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    ):
        fail("B09_VIEW_HASH_INVALID")
