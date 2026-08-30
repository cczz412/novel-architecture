"""Frozen B-05 r03.5 fixture catalog and write profiles."""

from __future__ import annotations

from typing import Any


NORMAL_FIXTURES: dict[str, dict[str, str]] = {
    "N01_REPLACE_ALLOWED": {
        "disposition": "PUBLISH_INITIAL_ROUTE_BUNDLE",
        "write_profile": "INITIAL_ROUTE_BUNDLE",
    },
    "N02_ADD_ALLOWED": {
        "disposition": "PUBLISH_INITIAL_ROUTE_BUNDLE",
        "write_profile": "INITIAL_ROUTE_BUNDLE",
    },
    "N03_INDEPENDENT_MIXED_ROUTES_WITH_EFFECTIVE_PROTECTION": {
        "disposition": "PUBLISH_INITIAL_ROUTE_BUNDLE",
        "write_profile": "INITIAL_ROUTE_BUNDLE",
    },
    "N04_DEPENDENT_GROUPS_SINGLE_ROUTE_UNIT": {
        "disposition": "PUBLISH_INITIAL_ROUTE_BUNDLE",
        "write_profile": "INITIAL_ROUTE_BUNDLE",
    },
    "N05_EXPAND_CHECK_MINIMAL_TARGET": {
        "disposition": "PUBLISH_INITIAL_ROUTE_BUNDLE_WITH_EXPAND_CHECK",
        "write_profile": "INITIAL_ROUTE_BUNDLE",
    },
    "N06_DEFER_EXACT_DECLARED_NON_CONTENT_GATE": {
        "disposition": "PUBLISH_INITIAL_ROUTE_BUNDLE_WITH_DEFER",
        "write_profile": "INITIAL_ROUTE_BUNDLE",
    },
    "N07_TRUSTED_STALE_OR_UNSAFE_PROPOSAL_REJECTED": {
        "disposition": "PUBLISH_INITIAL_ROUTE_BUNDLE_WITH_REJECT",
        "write_profile": "INITIAL_ROUTE_BUNDLE",
    },
    "N08_CAUSAL_ROUTE_TO_B09_ALL_SUPPORT_UNITS_ALLOWED": {
        "disposition": "PUBLISH_INITIAL_ROUTE_BUNDLE_WITH_CAUSAL_ROUTE_TO_B09",
        "write_profile": "INITIAL_ROUTE_BUNDLE",
    },
    "N09_IDEMPOTENT_AND_CONTENT_DEDUP_REPLAY": {
        "disposition": "RETURN_EXISTING_BUNDLE",
        "write_profile": "REUSE_EXISTING_BUNDLE",
    },
    "N10_ATOMIC_SUPERSEDE_AND_REOPEN_WITH_NEW_MATERIAL": {
        "disposition": "PUBLISH_ATOMIC_REOPEN_BUNDLE",
        "write_profile": "REOPEN_ROUTE_BUNDLE",
    },
}


FAILURE_FIXTURES: dict[str, dict[str, Any]] = {
    "F01_DIRECTLY_READABLE_REF_UNRESOLVABLE_OR_HASH_MISMATCHED_ABORTS": {
        "disposition": "ABORT_NO_OUTPUT",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F02_POINTER_DRIFT_BETWEEN_READS_ABORTS": {
        "disposition": "ABORT_NO_OUTPUT",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F03_B02_LIFECYCLE_OR_SCOPE_DRIFT_BETWEEN_READS_ABORTS": {
        "disposition": "ABORT_NO_OUTPUT",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F04_POLICY_OR_DECLARED_GATE_SELECTION_DRIFT_ABORTS": {
        "disposition": "ABORT_NO_OUTPUT",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F05_SAME_OPERATION_ID_DIFFERENT_INPUT_HASH_ABORTS": {
        "disposition": "ABORT_OR_REUSE_PER_SUBCASE",
        "subcases": {
            "SAME_OPERATION_DIFFERENT_INPUT": "ABORT_NO_OUTPUT",
            "SAME_AUTHORITATIVE_INPUT_DIFFERENT_DETERMINISTIC_RESULT_VIEW": (
                "ABORT_NO_OUTPUT"
            ),
            "DIFFERENT_OPERATION_SAME_INPUT_ONLY_CREATOR_OPERATION_ID_DIFFERS": (
                "REUSE_EXISTING_BUNDLE"
            ),
        },
    },
    "F06_CONCURRENT_CONFLICTING_BUNDLE_CANNOT_CREATE_TWO_ACTIVE_ROUTES": {
        "disposition": "ONE_COMMIT_OTHER_ABORTS_OR_REUSES",
        "subcases": {
            "IDENTICAL_INPUT_CONCURRENT_WINNER": "INITIAL_ROUTE_BUNDLE",
            "IDENTICAL_INPUT_CONCURRENT_LOSER": "REUSE_EXISTING_BUNDLE",
            "CONFLICTING_INPUT_CONCURRENT_WINNER": "INITIAL_ROUTE_BUNDLE",
            "CONFLICTING_INPUT_CONCURRENT_LOSER": "ABORT_NO_OUTPUT",
        },
    },
    "F07_B01_OR_B02_READER_UNAVAILABLE_INCOMPLETE_OR_AMBIGUOUS_ABORTS": {
        "disposition": "ABORT_NO_OUTPUT",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F08_PARTIAL_ALLOW_WITHOUT_EFFECTIVE_PROTECTION_OF_OTHER_UNIT_TARGET_CANNOT_BE_PUBLISHED": {
        "disposition": "INVALID_ROUTE_CANDIDATE_NOT_PUBLISHED",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F09_DEPENDENT_GROUP_PARTIAL_ALLOW_CANNOT_BE_PUBLISHED": {
        "disposition": "INVALID_ROUTE_CANDIDATE_NOT_PUBLISHED",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F10_UNKNOWN_DEPENDENCY_CANNOT_BE_ALLOWED": {
        "disposition": "PUBLISH_EXPAND_CHECK_NOT_ALLOW",
        "write_profile": "INITIAL_ROUTE_BUNDLE",
    },
    "F11_GROUP_MISSING_DUPLICATED_OR_ASSIGNED_TO_MULTIPLE_UNITS_CANNOT_BE_PUBLISHED": {
        "disposition": "INVALID_PARTITION_CANDIDATE_NOT_PUBLISHED",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F12_ORDER_SENSITIVE_ADD_UNITS_CANNOT_BE_SPLIT_WITHOUT_FROZEN_CANONICAL_SORT": {
        "disposition": "PUBLISH_INITIAL_ROUTE_BUNDLE_WITH_SINGLE_ALLOW_UNIT",
        "write_profile": "INITIAL_ROUTE_BUNDLE",
    },
    "F13_PVR_ROUTE_OR_LIFECYCLE_DUPLICATES_ANOTHER_OBJECTS_CONCLUSION": {
        "disposition": "INVALID_OBJECT_CANDIDATE_NOT_PUBLISHED",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F14_PVR_ROUTE_AND_LIFECYCLE_PUBLISHED_SEPARATELY": {
        "disposition": "ATOMIC_COMMIT_ABORTS_WITH_NO_PARTIAL_VISIBILITY",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F15_ABORT_PATH_HAS_VISIBLE_TEMP_WRITE_WRITE_THEN_DELETE_OR_OUT_OF_SET_WRITE": {
        "disposition": "ACCEPTANCE_FAILS_ZERO_WRITE_PROOF",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F16_B05_READS_TEXT_CALLS_MODEL_MUTATES_PATCH_WRITES_CANDIDATE_OR_POINTER": {
        "disposition": "ACCEPTANCE_FAILS_FORBIDDEN_RUNTIME_EVENT",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F17_EXPAND_CHECK_COMPLETED_INSIDE_B05_OR_CARRIES_TEXT_PROMPT_NEW_FACT": {
        "disposition": "INVALID_EXPAND_ROUTE_CANDIDATE_NOT_PUBLISHED",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F18_CAUSAL_SUPPORT_MAPPING_INCOMPLETE_OR_AMBIGUOUS_CANNOT_ROUTE_TO_B09": {
        "disposition": "NON_EXACT_B04_CLOSURE_ABORTS_NO_OUTPUT",
        "write_profile": "ABORT_NO_OUTPUT",
    },
    "F19_NON_ROUTE_TO_B09_CAUSAL_ENTRY_WRITES_SIDECAR_MANIFEST_OR_LIFECYCLE": {
        "disposition": "DENY_B09_WRITES",
        "write_profile": "B09_DENIED_EXISTING_B05_UNCHANGED",
    },
    "F20_B06_USES_NON_ACTIVE_OR_STALE_ROUTE_WITHOUT_FRESHNESS_REVALIDATION": {
        "disposition": "DENY_B06_WRITES",
        "write_profile": "B06_DENIED_EXISTING_B05_UNCHANGED",
    },
    "F21_DEFER_USED_FOR_READER_OUTAGE_UNDECLARED_HUMAN_GATE_OR_SEMANTIC_UNCERTAINTY": {
        "disposition": "CASE_MATRIX_NO_INVALID_DEFER",
        "subcases": {
            "AUTHORITATIVE_READER_OUTAGE": "ABORT_NO_OUTPUT",
            "UNDECLARED_HUMAN_GATE": "INITIAL_ROUTE_BUNDLE",
            "SEMANTIC_UNCERTAINTY": "INITIAL_ROUTE_BUNDLE",
        },
    },
    "F22_ROUTE_RECEIPT_MUTATED_OR_LIFECYCLE_PRODUCES_TWO_ACTIVE_ROUTES": {
        "disposition": "PROJECTION_AND_DOWNSTREAM_FAIL_CLOSED",
        "write_profile": "PROJECTION_FAILS_CLOSED",
    },
}


WRITE_PROFILES: dict[str, dict[str, int]] = {
    "INITIAL_ROUTE_BUNDLE": {
        "validator_identity": 0,
        "patch_validation": 1,
        "patch_route": 1,
        "patch_lifecycle": 1,
        "candidate_version": 0,
        "pointer": 0,
        "b09_sidecar": 0,
        "visible_temporary_or_out_of_set": 0,
    },
    "REOPEN_ROUTE_BUNDLE": {
        "validator_identity": 0,
        "patch_validation": 1,
        "patch_route": 1,
        "patch_lifecycle": 2,
        "candidate_version": 0,
        "pointer": 0,
        "b09_sidecar": 0,
        "visible_temporary_or_out_of_set": 0,
    },
    "ABORT_NO_OUTPUT": {
        "validator_identity": 0,
        "patch_validation": 0,
        "patch_route": 0,
        "patch_lifecycle": 0,
        "candidate_version": 0,
        "pointer": 0,
        "b09_sidecar": 0,
        "visible_temporary_or_out_of_set": 0,
    },
}


RUNTIME_COUNTERS: dict[str, int] = {
    "real_model_api_calls": 0,
    "network_calls": 0,
    "real_novel_reads": 0,
    "text_slice_reads": 0,
    "new_fact_generations": 0,
    "patch_mutations": 0,
    "candidate_version_writes": 0,
    "pointer_writes": 0,
    "formal_fact_writes": 0,
    "ledger_truth_writes": 0,
    "b09_sidecar_writes": 0,
}


def validate_fixture_catalog() -> None:
    """Fail when the frozen 10/22 catalog loses identity or write profiles."""

    if len(NORMAL_FIXTURES) != 10 or len(FAILURE_FIXTURES) != 22:
        raise ValueError("B05_FIXTURE_COUNT_DRIFT")
    identifiers = [*NORMAL_FIXTURES, *FAILURE_FIXTURES]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("B05_FIXTURE_ID_DUPLICATE")
    for fixture in [*NORMAL_FIXTURES.values(), *FAILURE_FIXTURES.values()]:
        if not fixture.get("disposition"):
            raise ValueError("B05_FIXTURE_DISPOSITION_MISSING")
        profile = fixture.get("write_profile")
        subcases = fixture.get("subcases")
        if profile is None and not isinstance(subcases, dict):
            raise ValueError("B05_FIXTURE_WRITE_PROFILE_MISSING")
        if profile in {
            "INITIAL_ROUTE_BUNDLE",
            "REOPEN_ROUTE_BUNDLE",
            "ABORT_NO_OUTPUT",
        }:
            if profile not in WRITE_PROFILES:
                raise ValueError("B05_FIXTURE_WRITE_PROFILE_UNKNOWN")


validate_fixture_catalog()
