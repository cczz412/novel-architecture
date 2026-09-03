from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "novel-mvp/contracts"
MODULE_PATH = CONTRACT_DIR / "validate_knowledge_edge.py"
CONTRACT_PATH = CONTRACT_DIR / "KNOWLEDGE_EDGE.md"
SCHEMA_PATH = CONTRACT_DIR / "KNOWLEDGE_EDGE.schema.json"
CHARACTER_CONTRACT_PATH = CONTRACT_DIR / "CHARACTER_LEDGER_CONTENT.md"
CHARACTER_SCHEMA_PATH = CONTRACT_DIR / "CHARACTER_LEDGER_CONTENT.schema.json"
SPEC = importlib.util.spec_from_file_location("validate_knowledge_edge", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures()


def _case(case_id: str) -> dict:
    return next(case for case in CASES if case["case_id"] == case_id)


def _confirmed_task_read_pair(edge_case_id: str, grant_case_id: str) -> tuple:
    edge = copy.deepcopy(_case(edge_case_id)["document"])
    edge["version_status"] = {
        "confirmation": "author_confirmed",
        "lifecycle": "active",
    }
    grant = copy.deepcopy(_case(grant_case_id)["document"])
    return edge, grant


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_knowledge_edge_fixture_matrix(case: dict) -> None:
    MODULE.validate_fixture_case(case)


def test_fixture_counts_are_frozen() -> None:
    assert MODULE.validate_all_fixtures() == {
        "cases": 41,
        "valid": 16,
        "invalid": 25,
    }


def test_seven_business_fields_are_exact_and_fact_ref_is_stable() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    edge = schema["$defs"]["edge"]
    business_fields = {
        "observer_ref",
        "epistemic_state",
        "fact_ref",
        "belief_content",
        "story_time_interval",
        "evidence_refs",
        "version_status",
    }
    assert business_fields <= set(edge["required"])
    assert edge["properties"]["observer_ref"]["pattern"] == "^CH-[0-9]+$"
    assert edge["properties"]["fact_ref"]["pattern"] == "^f[0-9]{3,}$"
    assert set(edge["properties"]["permission_namespace"]["enum"]) == {
        "knowledge-edge.v1",
        "knowledge-edge.v2",
    }


def test_v1_fixture_prefix_matches_current_safety_baseline() -> None:
    fixture_path = CONTRACT_DIR / "KNOWLEDGE_EDGE.fixtures.jsonl"
    prefix = b"".join(fixture_path.read_bytes().splitlines(keepends=True)[:29])
    assert hashlib.sha256(prefix).hexdigest() == (
        "8447de3ddde986cb429f981e9a768aa12b1e08dec7d131ec93ba607e487b71d5"
    )


def test_v1_edge_objects_keep_compatibility_baseline() -> None:
    edge_keys = ("document", "edge", "previous", "current")
    edge_objects = [
        case[key]
        for case in CASES[:29]
        for key in edge_keys
        if isinstance(case.get(key), dict)
        and case[key].get("contract") == "KNOWLEDGE_EDGE"
        and case[key].get("version") == MODULE.VERSION_V1
    ]
    payload = json.dumps(
        edge_objects,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert len(edge_objects) == 28
    assert hashlib.sha256(payload).hexdigest() == (
        "b6b4c22321af18c1c2e816fbbf5ddcb647aa5bc8a8aebb1ccd7fb41298cc4e5f"
    )


def test_v2_adds_explicit_non_belief_with_versioned_namespaces() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    edge = schema["$defs"]["edge"]
    assert "explicitly_does_not_believe" in edge["properties"][
        "epistemic_state"
    ]["enum"]
    valid = next(case for case in CASES if case["case_id"] == "KE-V2-VALID-01")
    document = MODULE.validate_document(valid["document"])
    assert document["version"] == MODULE.VERSION_V2
    assert document["permission_namespace"] == "knowledge-edge.v2"
    assert document["belief_content"] is None

    for state in (
        "knows",
        "explicitly_does_not_know",
        "suspects",
        "false_belief",
        "explicitly_does_not_believe",
    ):
        candidate = copy.deepcopy(valid["document"])
        candidate["epistemic_state"] = state
        candidate["belief_content"] = "错误认知" if state == "false_belief" else None
        assert MODULE.validate_document(candidate)["epistemic_state"] == state


def test_explicit_version_constants_keep_v1_legacy_aliases() -> None:
    assert MODULE.VERSION == MODULE.VERSION_V1
    assert MODULE.PERMISSION_NAMESPACE == MODULE.PERMISSION_NAMESPACE_V1
    assert MODULE.WRITER_NAMESPACE == MODULE.WRITER_NAMESPACE_V1
    assert MODULE.PERMISSION_NAMESPACE_V2 == "knowledge-edge.v2"
    assert MODULE.WRITER_NAMESPACE_V2 == "trusted.knowledge_edge.writer.v2"


def test_reader_type_and_version_stop_before_full_schema_validation() -> None:
    v1 = _case("KE-VALID-01")["document"]
    v2 = _case("KE-V2-VALID-01")["document"]
    assert MODULE.validate_document_for_reader(v1, MODULE.VERSION_V1)
    assert MODULE.validate_document_for_reader(v1, MODULE.VERSION_V2)
    assert MODULE.validate_document_for_reader(v2, MODULE.VERSION_V2)

    malformed_v2 = copy.deepcopy(v2)
    malformed_v2["belief_content"] = "不该出现在第五态的文本"
    with pytest.raises(MODULE.ContractError, match="READER_VERSION_UNSUPPORTED"):
        MODULE.validate_document_for_reader(malformed_v2, MODULE.VERSION_V1)

    for non_edge in (
        _case("KE-VALID-04")["document"],
        _case("KE-VALID-06")["document"],
    ):
        with pytest.raises(MODULE.ContractError, match="READER_DOCUMENT_TYPE_INVALID"):
            MODULE.validate_document_for_reader(non_edge, MODULE.VERSION_V2)

    for invalid_reader_version in ("knowledge-edge-v3", [], {}):
        with pytest.raises(MODULE.ContractError, match="READER_VERSION_INVALID"):
            MODULE.validate_document_for_reader(v1, invalid_reader_version)

    for unsupported_document_version in ("knowledge-edge-v3", [], {}):
        malformed_version = copy.deepcopy(v2)
        malformed_version["version"] = unsupported_document_version
        with pytest.raises(MODULE.ContractError, match="READER_VERSION_UNSUPPORTED"):
            MODULE.validate_document_for_reader(
                malformed_version,
                MODULE.VERSION_V2,
            )


def test_reader_grant_must_match_edge_version_and_project() -> None:
    v1_edge, v1_grant = _confirmed_task_read_pair(
        "KE-VALID-01",
        "KE-VALID-06",
    )
    MODULE.validate_edge_grant_for_reader(v1_edge, v1_grant, MODULE.VERSION_V1)
    MODULE.validate_edge_grant_for_reader(v1_edge, v1_grant, MODULE.VERSION_V2)

    v2_edge, v2_grant = _confirmed_task_read_pair(
        "KE-V2-VALID-01",
        "KE-V2-VALID-05",
    )
    MODULE.validate_edge_grant_for_reader(v2_edge, v2_grant, MODULE.VERSION_V2)

    with pytest.raises(MODULE.ContractError, match="READ_GRANT_VERSION_MISMATCH"):
        MODULE.validate_edge_grant_for_reader(v1_edge, v2_grant, MODULE.VERSION_V2)
    with pytest.raises(MODULE.ContractError, match="READ_GRANT_VERSION_MISMATCH"):
        MODULE.validate_edge_grant_for_reader(v2_edge, v1_grant, MODULE.VERSION_V2)

    wrong_project = copy.deepcopy(v1_grant)
    wrong_project["project_id"] = "PROJECT-OTHER"
    with pytest.raises(
        MODULE.ContractError,
        match="UNAUTHORIZED",
    ):
        MODULE.validate_edge_grant_for_reader(
            v1_edge,
            wrong_project,
            MODULE.VERSION_V2,
        )

    wrong_author = copy.deepcopy(v1_grant)
    wrong_author["author_id"] = "AUTHOR-OTHER"
    with pytest.raises(
        MODULE.ContractError,
        match="UNAUTHORIZED",
    ):
        MODULE.validate_edge_grant_for_reader(
            v1_edge,
            wrong_author,
            MODULE.VERSION_V2,
        )


def test_read_grant_is_validated_before_inspecting_edge() -> None:
    malformed_grant = copy.deepcopy(_case("KE-VALID-06")["document"])
    malformed_grant.pop("as_of")
    guessed_edge = {
        "contract": "KNOWLEDGE_EDGE",
        "version": MODULE.VERSION_V2,
    }
    with pytest.raises(MODULE.ContractError, match="SCHEMA_INVALID"):
        MODULE.validate_edge_grant_for_reader(
            guessed_edge,
            malformed_grant,
            MODULE.VERSION_V1,
        )


def test_closed_grant_denies_before_edge_version_or_schema() -> None:
    closed_grant = copy.deepcopy(_case("KE-VALID-07")["document"])
    guessed_edge = {
        "contract": "KNOWLEDGE_EDGE",
        "version": MODULE.VERSION_V2,
    }
    with pytest.raises(MODULE.ContractError, match="^UNAUTHORIZED$"):
        MODULE.validate_edge_grant_for_reader(
            guessed_edge,
            closed_grant,
            MODULE.VERSION_V1,
        )


@pytest.mark.parametrize("mismatch", ["author_id", "project_id"])
def test_cross_identity_grant_denies_before_edge_schema(mismatch: str) -> None:
    edge, grant = _confirmed_task_read_pair(
        "KE-VALID-01",
        "KE-VALID-06",
    )
    edge.pop("evidence_refs")
    grant[mismatch] = f"{mismatch.upper()}-OTHER"
    with pytest.raises(MODULE.ContractError, match="^UNAUTHORIZED$"):
        MODULE.validate_edge_grant_for_reader(
            edge,
            grant,
            MODULE.VERSION_V2,
        )


def test_authorized_grant_keeps_reader_errors_before_edge_schema() -> None:
    unsupported, matching_v2_grant = _confirmed_task_read_pair(
        "KE-V2-VALID-01",
        "KE-V2-VALID-05",
    )
    with pytest.raises(MODULE.ContractError, match="READER_VERSION_UNSUPPORTED"):
        MODULE.validate_edge_grant_for_reader(
            unsupported,
            matching_v2_grant,
            MODULE.VERSION_V1,
        )

    edge, grant = _confirmed_task_read_pair(
        "KE-VALID-01",
        "KE-VALID-06",
    )
    malformed = copy.deepcopy(edge)
    malformed.pop("evidence_refs")
    with pytest.raises(MODULE.ContractError, match="SCHEMA_INVALID"):
        MODULE.validate_edge_grant_for_reader(
            malformed,
            grant,
            MODULE.VERSION_V2,
        )


@pytest.mark.parametrize(
    ("edge_case_id", "grant_case_id"),
    (
        ("KE-VALID-01", "KE-V2-VALID-05"),
        ("KE-V2-VALID-01", "KE-VALID-06"),
    ),
)
def test_grant_version_mismatch_stops_before_edge_schema(
    edge_case_id: str,
    grant_case_id: str,
) -> None:
    edge = copy.deepcopy(_case(edge_case_id)["document"])
    edge.pop("evidence_refs")
    grant = copy.deepcopy(_case(grant_case_id)["document"])
    with pytest.raises(
        MODULE.ContractError,
        match="^READ_GRANT_VERSION_MISMATCH$",
    ):
        MODULE.validate_edge_grant_for_reader(
            edge,
            grant,
            MODULE.VERSION_V2,
        )


@pytest.mark.parametrize("scope_field", ["observer_refs", "fact_refs"])
def test_task_scope_mismatch_stops_before_edge_schema(scope_field: str) -> None:
    edge, grant = _confirmed_task_read_pair(
        "KE-VALID-01",
        "KE-VALID-06",
    )
    grant[scope_field] = ["CH-0099"] if scope_field == "observer_refs" else ["f999"]
    malformed = copy.deepcopy(edge)
    malformed.pop("evidence_refs")
    for candidate in (edge, malformed):
        with pytest.raises(
            MODULE.ContractError,
            match="^READ_GRANT_SCOPE_MISMATCH$",
        ):
            MODULE.validate_edge_grant_for_reader(
                candidate,
                grant,
                MODULE.VERSION_V2,
            )


@pytest.mark.parametrize(
    ("confirmation", "lifecycle"),
    (
        ("candidate", "active"),
        ("author_confirmed", "retired"),
        ("author_confirmed", "active"),
    ),
)
def test_v1_reader_rejects_v2_before_task_eligibility_or_edge_schema(
    confirmation: str,
    lifecycle: str,
) -> None:
    edge, grant = _confirmed_task_read_pair(
        "KE-V2-VALID-01",
        "KE-V2-VALID-05",
    )
    edge["version_status"] = {
        "confirmation": confirmation,
        "lifecycle": lifecycle,
    }
    malformed = copy.deepcopy(edge)
    malformed.pop("evidence_refs")

    for candidate in (edge, malformed):
        with pytest.raises(MODULE.ContractError) as exc_info:
            MODULE.validate_edge_grant_for_reader(
                candidate,
                grant,
                MODULE.VERSION_V1,
            )
        assert str(exc_info.value) == "READER_VERSION_UNSUPPORTED"


@pytest.mark.parametrize(
    ("edge_case_id", "grant_case_id", "reader_version"),
    (
        ("KE-VALID-01", "KE-VALID-06", MODULE.VERSION_V1),
        ("KE-V2-VALID-01", "KE-V2-VALID-05", MODULE.VERSION_V2),
    ),
)
def test_task_read_requires_active_author_confirmed_edge(
    edge_case_id: str,
    grant_case_id: str,
    reader_version: str,
) -> None:
    candidate = copy.deepcopy(_case(edge_case_id)["document"])
    grant = copy.deepcopy(_case(grant_case_id)["document"])
    with pytest.raises(
        MODULE.ContractError,
        match="TASK_GRANT_REQUIRES_ACTIVE_AUTHOR_CONFIRMED_EDGE",
    ):
        MODULE.validate_edge_grant_for_reader(candidate, grant, reader_version)

    retired = copy.deepcopy(candidate)
    retired["version_status"] = {
        "confirmation": "author_confirmed",
        "lifecycle": "retired",
    }
    with pytest.raises(
        MODULE.ContractError,
        match="TASK_GRANT_REQUIRES_ACTIVE_AUTHOR_CONFIRMED_EDGE",
    ):
        MODULE.validate_edge_grant_for_reader(retired, grant, reader_version)


@pytest.mark.parametrize(
    ("edge_case_id", "grant_case_id", "reader_version"),
    (
        ("KE-VALID-01", "KE-VALID-06", MODULE.VERSION_V1),
        ("KE-V2-VALID-01", "KE-V2-VALID-05", MODULE.VERSION_V2),
    ),
)
@pytest.mark.parametrize(
    ("scenario", "expected_error"),
    (
        ("candidate", "TASK_GRANT_REQUIRES_ACTIVE_AUTHOR_CONFIRMED_EDGE"),
        ("retired", "TASK_GRANT_REQUIRES_ACTIVE_AUTHOR_CONFIRMED_EDGE"),
        ("before_start", "READ_GRANT_AS_OF_BEFORE_EDGE_START"),
        ("at_end", "READ_GRANT_AS_OF_OUTSIDE_EDGE_INTERVAL"),
    ),
)
def test_task_eligibility_stops_before_remaining_edge_schema(
    edge_case_id: str,
    grant_case_id: str,
    reader_version: str,
    scenario: str,
    expected_error: str,
) -> None:
    edge, grant = _confirmed_task_read_pair(edge_case_id, grant_case_id)
    start = edge["story_time_interval"]["start"]
    if scenario == "candidate":
        edge["version_status"]["confirmation"] = "candidate"
    elif scenario == "retired":
        edge["version_status"]["lifecycle"] = "retired"
    elif scenario == "before_start":
        grant["as_of"]["story_order"] = start["story_order"] - 1
    else:
        end = copy.deepcopy(start)
        end_ref = end["chapter_revision_ref"]
        end_ref["revision_no"] += 1
        end_ref["revision_text_sha256"] = "d" * 64
        end["story_order"] = start["story_order"] + 10
        edge["story_time_interval"]["end"] = end
        grant["as_of"]["story_order"] = end["story_order"]

    malformed = copy.deepcopy(edge)
    malformed.pop("evidence_refs")
    for candidate in (edge, malformed):
        with pytest.raises(MODULE.ContractError) as exc_info:
            MODULE.validate_edge_grant_for_reader(candidate, grant, reader_version)
        assert str(exc_info.value) == expected_error


@pytest.mark.parametrize(
    ("edge_case_id", "grant_case_id", "reader_version"),
    (
        ("KE-VALID-01", "KE-VALID-06", MODULE.VERSION_V1),
        ("KE-V2-VALID-01", "KE-V2-VALID-05", MODULE.VERSION_V2),
    ),
)
def test_task_read_as_of_must_be_inside_story_interval(
    edge_case_id: str,
    grant_case_id: str,
    reader_version: str,
) -> None:
    edge, grant = _confirmed_task_read_pair(edge_case_id, grant_case_id)
    start_order = edge["story_time_interval"]["start"]["story_order"]

    before_start = copy.deepcopy(grant)
    before_start["as_of"]["story_order"] = start_order - 1
    with pytest.raises(
        MODULE.ContractError,
        match="READ_GRANT_AS_OF_BEFORE_EDGE_START",
    ):
        MODULE.validate_edge_grant_for_reader(
            edge,
            before_start,
            reader_version,
        )

    MODULE.validate_edge_grant_for_reader(edge, grant, reader_version)

    bounded = copy.deepcopy(edge)
    bounded["story_time_interval"]["end"] = copy.deepcopy(
        edge["story_time_interval"]["start"]
    )
    bounded["story_time_interval"]["end"]["story_order"] = start_order + 10

    inside = copy.deepcopy(grant)
    inside["as_of"]["story_order"] = start_order + 5
    MODULE.validate_edge_grant_for_reader(bounded, inside, reader_version)

    for outside_order in (start_order + 10, start_order + 20):
        outside = copy.deepcopy(grant)
        outside["as_of"]["story_order"] = outside_order
        with pytest.raises(
            MODULE.ContractError,
            match="READ_GRANT_AS_OF_OUTSIDE_EDGE_INTERVAL",
        ):
            MODULE.validate_edge_grant_for_reader(
                bounded,
                outside,
                reader_version,
            )

    after_start = copy.deepcopy(grant)
    after_start["as_of"]["story_order"] = start_order + 20
    MODULE.validate_edge_grant_for_reader(edge, after_start, reader_version)


def test_mixed_story_orders_enforce_start_bound_before_ref_fallback() -> None:
    edge, grant = _confirmed_task_read_pair(
        "KE-V2-VALID-01",
        "KE-V2-VALID-05",
    )
    start = edge["story_time_interval"]["start"]
    end = copy.deepcopy(start)
    end.pop("story_order")
    end_ref = end["chapter_revision_ref"]
    end_ref["revision_no"] = 2
    end_ref["revision_text_sha256"] = "d" * 64
    edge["story_time_interval"]["end"] = end

    grant["as_of"]["story_order"] = start["story_order"] - 1
    with pytest.raises(
        MODULE.ContractError,
        match="READ_GRANT_AS_OF_BEFORE_EDGE_START",
    ):
        MODULE.validate_edge_grant_for_reader(edge, grant, MODULE.VERSION_V2)

    grant["as_of"]["story_order"] = start["story_order"]
    MODULE.validate_edge_grant_for_reader(edge, grant, MODULE.VERSION_V2)


def test_mixed_story_orders_enforce_end_bound_before_ref_fallback() -> None:
    edge, grant = _confirmed_task_read_pair(
        "KE-V2-VALID-01",
        "KE-V2-VALID-05",
    )
    start = edge["story_time_interval"]["start"]
    start.pop("story_order")
    end = copy.deepcopy(start)
    end_ref = end["chapter_revision_ref"]
    end_ref["revision_no"] = 2
    end_ref["revision_text_sha256"] = "d" * 64
    end["story_order"] = 130
    edge["story_time_interval"]["end"] = end

    grant["as_of"]["story_order"] = 130
    with pytest.raises(
        MODULE.ContractError,
        match="READ_GRANT_AS_OF_OUTSIDE_EDGE_INTERVAL",
    ):
        MODULE.validate_edge_grant_for_reader(edge, grant, MODULE.VERSION_V2)

    grant["as_of"]["story_order"] = 120
    MODULE.validate_edge_grant_for_reader(edge, grant, MODULE.VERSION_V2)


def test_task_read_as_of_uses_only_exact_revision_refs_without_story_order() -> None:
    edge, grant = _confirmed_task_read_pair(
        "KE-V2-VALID-01",
        "KE-V2-VALID-05",
    )
    edge["story_time_interval"]["start"].pop("story_order")
    grant["as_of"].pop("story_order")
    MODULE.validate_edge_grant_for_reader(edge, grant, MODULE.VERSION_V2)

    end = copy.deepcopy(edge["story_time_interval"]["start"])
    end_ref = end["chapter_revision_ref"]
    end_ref["revision_no"] = 2
    end_ref["revision_text_sha256"] = "d" * 64
    edge["story_time_interval"]["end"] = end

    at_end = copy.deepcopy(grant)
    at_end["as_of"] = copy.deepcopy(end)
    with pytest.raises(
        MODULE.ContractError,
        match="READ_GRANT_AS_OF_OUTSIDE_EDGE_INTERVAL",
    ):
        MODULE.validate_edge_grant_for_reader(edge, at_end, MODULE.VERSION_V2)

    unknown = copy.deepcopy(grant)
    unknown_ref = unknown["as_of"]["chapter_revision_ref"]
    unknown_ref["revision_no"] = 3
    unknown_ref["revision_text_sha256"] = "e" * 64
    with pytest.raises(
        MODULE.ContractError,
        match="READ_GRANT_AS_OF_UNDETERMINED",
    ):
        MODULE.validate_edge_grant_for_reader(edge, unknown, MODULE.VERSION_V2)


@pytest.mark.parametrize("lifecycle", ["active", "retired"])
def test_author_full_project_can_inspect_candidate_and_history(
    lifecycle: str,
) -> None:
    edge = copy.deepcopy(_case("KE-VALID-01")["document"])
    edge["version_status"]["lifecycle"] = lifecycle
    author_grant = copy.deepcopy(_case("KE-VALID-05")["document"])
    MODULE.validate_edge_grant_for_reader(
        edge,
        author_grant,
        MODULE.VERSION_V1,
    )


@pytest.mark.parametrize("case_id", ["KE-VALID-08", "KE-V2-VALID-03"])
def test_all_candidate_versions_require_existing_edge_set(case_id: str) -> None:
    candidate = _case(case_id)
    with pytest.raises(MODULE.ContractError, match="EXISTING_EDGE_SET_REQUIRED"):
        MODULE.validate_new_candidate(candidate["edge"], candidate["action"])


def test_v1_candidate_with_empty_existing_edge_set_is_valid() -> None:
    candidate = _case("KE-VALID-08")
    MODULE.validate_new_candidate(
        candidate["edge"],
        candidate["action"],
        [],
    )


def test_v1_candidate_rejects_overlapping_v2_edge() -> None:
    candidate = copy.deepcopy(_case("KE-VALID-08"))
    existing = copy.deepcopy(candidate["edge"])
    existing["version"] = MODULE.VERSION_V2
    existing["id"] = "KE-0888"
    existing["permission_namespace"] = MODULE.PERMISSION_NAMESPACE_V2
    with pytest.raises(MODULE.ContractError, match="CROSS_VERSION_RECREATE_FORBIDDEN"):
        MODULE.validate_new_candidate(
            candidate["edge"],
            candidate["action"],
            [existing],
        )


def test_copying_v1_edge_to_new_v2_id_cannot_recreate_same_slot() -> None:
    old = _case("KE-VALID-08")["edge"]
    candidate = copy.deepcopy(_case("KE-V2-VALID-03"))
    for field in ("author_id", "project_id", "observer_ref", "fact_ref"):
        candidate["edge"][field] = old[field]
    candidate["edge"]["story_time_interval"] = copy.deepcopy(
        old["story_time_interval"]
    )
    with pytest.raises(MODULE.ContractError, match="CROSS_VERSION_RECREATE_FORBIDDEN"):
        MODULE.validate_new_candidate(
            candidate["edge"],
            candidate["action"],
            [old],
        )


def test_same_version_state_or_id_change_cannot_duplicate_logical_slot() -> None:
    candidate = copy.deepcopy(_case("KE-V2-VALID-03"))
    existing = copy.deepcopy(candidate["edge"])
    existing["id"] = "KE-0999"
    existing["epistemic_state"] = "suspects"
    with pytest.raises(MODULE.ContractError, match="KNOWLEDGE_EDGE_SLOT_CONFLICT"):
        MODULE.validate_new_candidate(
            candidate["edge"],
            candidate["action"],
            [existing],
        )


@pytest.mark.parametrize(
    "reuse_variant",
    ("different_observer", "different_fact", "non_overlapping_interval"),
)
def test_new_candidate_rejects_reused_edge_id_before_slot_filtering(
    reuse_variant: str,
) -> None:
    candidate = copy.deepcopy(_case("KE-V2-VALID-03"))
    existing = copy.deepcopy(candidate["edge"])
    if reuse_variant == "different_observer":
        existing["observer_ref"] = "CH-0099"
    elif reuse_variant == "different_fact":
        existing["fact_ref"] = "f999"
    else:
        existing["story_time_interval"]["start"]["story_order"] = 100
        existing["story_time_interval"]["end"] = copy.deepcopy(
            candidate["edge"]["story_time_interval"]["start"]
        )

    with pytest.raises(
        MODULE.ContractError,
        match="KNOWLEDGE_EDGE_ID_REUSE_FORBIDDEN",
    ):
        MODULE.validate_new_candidate(
            candidate["edge"],
            candidate["action"],
            [existing],
        )


def test_adjacent_non_overlapping_story_intervals_allow_new_v2_slot() -> None:
    candidate = copy.deepcopy(_case("KE-V2-VALID-03"))
    existing = copy.deepcopy(candidate["edge"])
    existing.update(
        {
            "version": MODULE.VERSION_V1,
            "id": "KE-0998",
            "permission_namespace": MODULE.PERMISSION_NAMESPACE_V1,
            "epistemic_state": "suspects",
        }
    )
    existing["story_time_interval"]["start"]["story_order"] = 100
    existing["story_time_interval"]["end"] = copy.deepcopy(
        candidate["edge"]["story_time_interval"]["start"]
    )
    MODULE.validate_new_candidate(
        candidate["edge"],
        candidate["action"],
        [existing],
    )


def test_left_end_order_proves_separation_when_right_end_order_is_missing() -> None:
    candidate = copy.deepcopy(_case("KE-V2-VALID-03"))
    candidate_end = copy.deepcopy(candidate["edge"]["story_time_interval"]["start"])
    candidate_end_ref = candidate_end["chapter_revision_ref"]
    candidate_end_ref["revision_no"] = 2
    candidate_end_ref["revision_text_sha256"] = "d" * 64
    candidate_end["story_order"] = 125
    candidate["edge"]["story_time_interval"]["end"] = candidate_end

    existing = copy.deepcopy(candidate["edge"])
    existing.update(
        {
            "version": MODULE.VERSION_V1,
            "id": "KE-0994",
            "permission_namespace": MODULE.PERMISSION_NAMESPACE_V1,
            "epistemic_state": "suspects",
        }
    )
    existing_start = existing["story_time_interval"]["start"]
    existing_start_ref = existing_start["chapter_revision_ref"]
    existing_start_ref["chapter_id"] = "c13"
    existing_start_ref["revision_text_sha256"] = "e" * 64
    existing_start["story_order"] = 130
    existing_end = copy.deepcopy(existing_start)
    existing_end.pop("story_order")
    existing_end_ref = existing_end["chapter_revision_ref"]
    existing_end_ref["revision_no"] = 2
    existing_end_ref["revision_text_sha256"] = "f" * 64
    existing["story_time_interval"]["end"] = existing_end

    MODULE.validate_new_candidate(
        candidate["edge"],
        candidate["action"],
        [existing],
    )


def test_right_end_order_proves_separation_when_left_end_order_is_missing() -> None:
    candidate = copy.deepcopy(_case("KE-V2-VALID-03"))
    candidate_end = copy.deepcopy(candidate["edge"]["story_time_interval"]["start"])
    candidate_end.pop("story_order")
    candidate_end_ref = candidate_end["chapter_revision_ref"]
    candidate_end_ref["revision_no"] = 2
    candidate_end_ref["revision_text_sha256"] = "d" * 64
    candidate["edge"]["story_time_interval"]["end"] = candidate_end

    existing = copy.deepcopy(candidate["edge"])
    existing.update(
        {
            "version": MODULE.VERSION_V1,
            "id": "KE-0993",
            "permission_namespace": MODULE.PERMISSION_NAMESPACE_V1,
            "epistemic_state": "suspects",
        }
    )
    existing_start = existing["story_time_interval"]["start"]
    existing_start_ref = existing_start["chapter_revision_ref"]
    existing_start_ref["chapter_id"] = "c11"
    existing_start_ref["revision_text_sha256"] = "b" * 64
    existing_start["story_order"] = 100
    existing_end = copy.deepcopy(existing_start)
    existing_end_ref = existing_end["chapter_revision_ref"]
    existing_end_ref["revision_no"] = 2
    existing_end_ref["revision_text_sha256"] = "a" * 64
    existing_end["story_order"] = 115
    existing["story_time_interval"]["end"] = existing_end

    MODULE.validate_new_candidate(
        candidate["edge"],
        candidate["action"],
        [existing],
    )


def test_comparable_story_orders_stop_on_contradictory_exact_boundary() -> None:
    candidate = copy.deepcopy(_case("KE-V2-VALID-03"))
    candidate["edge"]["story_time_interval"]["start"] = {
        "chapter_revision_ref": {
            "chapter_id": "c11",
            "revision_no": 1,
            "revision_text_sha256": "b" * 64,
        },
        "story_order": 100,
    }
    candidate["edge"]["story_time_interval"]["end"] = {
        "chapter_revision_ref": {
            "chapter_id": "c12",
            "revision_no": 1,
            "revision_text_sha256": "c" * 64,
        },
        "story_order": 150,
    }

    existing = copy.deepcopy(candidate["edge"])
    existing.update(
        {
            "version": MODULE.VERSION_V1,
            "id": "KE-0992",
            "permission_namespace": MODULE.PERMISSION_NAMESPACE_V1,
            "epistemic_state": "suspects",
        }
    )
    existing["story_time_interval"] = {
        "start": {
            "chapter_revision_ref": copy.deepcopy(
                candidate["edge"]["story_time_interval"]["end"][
                    "chapter_revision_ref"
                ]
            ),
            "story_order": 120,
        },
        "end": {
            "chapter_revision_ref": {
                "chapter_id": "c13",
                "revision_no": 1,
                "revision_text_sha256": "d" * 64,
            }
        },
    }

    with pytest.raises(
        MODULE.ContractError,
        match="STORY_INTERVAL_OVERLAP_UNDETERMINED",
    ):
        MODULE.validate_new_candidate(
            candidate["edge"],
            candidate["action"],
            [existing],
        )


def test_exact_revision_adjacent_intervals_allow_new_v2_slot() -> None:
    candidate = copy.deepcopy(_case("KE-V2-VALID-03"))
    candidate["edge"]["story_time_interval"]["start"].pop("story_order")
    existing = copy.deepcopy(candidate["edge"])
    existing.update(
        {
            "version": MODULE.VERSION_V1,
            "id": "KE-0996",
            "permission_namespace": MODULE.PERMISSION_NAMESPACE_V1,
            "epistemic_state": "suspects",
        }
    )
    existing_start_ref = existing["story_time_interval"]["start"][
        "chapter_revision_ref"
    ]
    existing_start_ref["chapter_id"] = "c11"
    existing_start_ref["revision_text_sha256"] = "b" * 64
    existing["story_time_interval"]["end"] = copy.deepcopy(
        candidate["edge"]["story_time_interval"]["start"]
    )
    MODULE.validate_new_candidate(
        candidate["edge"],
        candidate["action"],
        [existing],
    )


def test_exact_revision_equal_starts_are_overlapping() -> None:
    candidate = copy.deepcopy(_case("KE-V2-VALID-03"))
    candidate["edge"]["story_time_interval"]["start"].pop("story_order")
    existing = copy.deepcopy(candidate["edge"])
    existing["id"] = "KE-0995"
    with pytest.raises(MODULE.ContractError, match="KNOWLEDGE_EDGE_SLOT_CONFLICT"):
        MODULE.validate_new_candidate(
            candidate["edge"],
            candidate["action"],
            [existing],
        )


def test_unknown_story_overlap_stops_instead_of_assuming_no_conflict() -> None:
    candidate = copy.deepcopy(_case("KE-V2-VALID-03"))
    existing = copy.deepcopy(candidate["edge"])
    existing["id"] = "KE-0997"
    existing["story_time_interval"]["start"].pop("story_order")
    existing_start_ref = existing["story_time_interval"]["start"][
        "chapter_revision_ref"
    ]
    existing_start_ref["chapter_id"] = "c13"
    existing_start_ref["revision_text_sha256"] = "f" * 64
    with pytest.raises(
        MODULE.ContractError,
        match="STORY_INTERVAL_OVERLAP_UNDETERMINED",
    ):
        MODULE.validate_new_candidate(
            candidate["edge"],
            candidate["action"],
            [existing],
        )


def test_new_candidate_and_action_versions_cannot_be_mixed() -> None:
    v2 = copy.deepcopy(_case("KE-V2-VALID-03"))
    v2["action"]["version"] = MODULE.VERSION_V1
    v2["action"]["writer_namespace"] = MODULE.WRITER_NAMESPACE_V1
    with pytest.raises(MODULE.ContractError, match="NEW_CANDIDATE_VERSION_MISMATCH"):
        MODULE.validate_new_candidate(v2["edge"], v2["action"], [])

    v1 = copy.deepcopy(_case("KE-VALID-08"))
    v1["action"]["version"] = MODULE.VERSION_V2
    v1["action"]["writer_namespace"] = MODULE.WRITER_NAMESPACE_V2
    with pytest.raises(MODULE.ContractError, match="NEW_CANDIDATE_VERSION_MISMATCH"):
        MODULE.validate_new_candidate(v1["edge"], v1["action"])


def test_edge_action_and_grant_namespaces_follow_their_versions() -> None:
    documents = (
        _case("KE-VALID-01")["document"],
        _case("KE-VALID-04")["document"],
        _case("KE-VALID-06")["document"],
        _case("KE-V2-VALID-01")["document"],
        _case("KE-V2-VALID-03")["action"],
        _case("KE-V2-VALID-05")["document"],
    )
    for source in documents:
        document = copy.deepcopy(source)
        document["version"] = (
            MODULE.VERSION_V2
            if document["version"] == MODULE.VERSION_V1
            else MODULE.VERSION_V1
        )
        with pytest.raises(MODULE.ContractError, match="SCHEMA_INVALID"):
            MODULE.validate_document(document)


def test_all_normal_revision_operations_reject_both_cross_version_directions() -> None:
    for case_id in ("KE-VALID-09", "KE-VALID-10", "KE-VALID-11"):
        source = _case(case_id)
        for direction in ("v1_to_v2", "v2_to_v1"):
            transition = copy.deepcopy(source)
            if direction == "v1_to_v2":
                transition["current"]["version"] = MODULE.VERSION_V2
                transition["current"][
                    "permission_namespace"
                ] = MODULE.PERMISSION_NAMESPACE_V2
                transition["action"]["version"] = MODULE.VERSION_V2
                transition["action"]["writer_namespace"] = MODULE.WRITER_NAMESPACE_V2
            else:
                transition["previous"]["version"] = MODULE.VERSION_V2
                transition["previous"][
                    "permission_namespace"
                ] = MODULE.PERMISSION_NAMESPACE_V2
            with pytest.raises(
                MODULE.ContractError,
                match="CROSS_VERSION_REVISION_FORBIDDEN",
            ):
                MODULE.validate_revision_transition(
                    transition["previous"],
                    transition["current"],
                    transition["action"],
                )


def test_v2_keeps_confirm_modify_and_retire_revision_paths() -> None:
    for case_id in ("KE-VALID-09", "KE-VALID-10", "KE-VALID-11"):
        transition = copy.deepcopy(_case(case_id))
        for edge_key in ("previous", "current"):
            transition[edge_key]["version"] = MODULE.VERSION_V2
            transition[edge_key][
                "permission_namespace"
            ] = MODULE.PERMISSION_NAMESPACE_V2
        transition["action"]["version"] = MODULE.VERSION_V2
        transition["action"]["writer_namespace"] = MODULE.WRITER_NAMESPACE_V2
        MODULE.validate_revision_transition(
            transition["previous"],
            transition["current"],
            transition["action"],
        )


@pytest.mark.parametrize("operation", ["MODIFY", "RETIRE"])
def test_v2_explicit_non_belief_can_be_modified_or_retired(operation: str) -> None:
    confirmed = copy.deepcopy(_case("KE-V2-VALID-04")["current"])
    current = copy.deepcopy(confirmed)
    current["rev"] = 3
    current["previous_rev"] = 2
    current["updated_at"] = "2026-09-03T11:00:00+08:00"
    if operation == "MODIFY":
        current["evidence_refs"] = ["f109"]
    else:
        current["version_status"]["lifecycle"] = "retired"

    action = copy.deepcopy(_case("KE-V2-VALID-04")["action"])
    action["action_id"] = f"KEA-V2-{operation}-FIFTH-STATE"
    action["operation"] = operation
    action["base_rev"] = 2
    action["idempotency_key"] = f"v2-{operation.lower()}-fifth-state"

    MODULE.validate_revision_transition(confirmed, current, action)


def test_cross_version_revision_is_stopped() -> None:
    case = _case("KE-V2-INVALID-07")
    with pytest.raises(MODULE.ContractError, match="CROSS_VERSION_REVISION_FORBIDDEN"):
        MODULE.validate_revision_transition(
            case["previous"],
            case["current"],
            case["action"],
        )


def test_false_belief_requires_bounded_inline_text() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    belief = schema["$defs"]["edge"]["properties"]["belief_content"]
    text_shape = next(shape for shape in belief["oneOf"] if shape["type"] == "string")
    assert text_shape["minLength"] == 1
    assert text_shape["maxLength"] == 500
    invalid_null = next(case for case in CASES if case["case_id"] == "KE-INVALID-01")
    with pytest.raises(MODULE.ContractError, match="SCHEMA_INVALID"):
        MODULE.validate_document(invalid_null["document"])


def test_no_record_means_untracked_not_explicitly_does_not_know() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "无记录不是第五种知情状态" in contract
    assert "不得改写成 `explicitly_does_not_know`" in contract
    assert "EMPTY + NO_MATCHING_ENTRIES" in contract


def test_knowledge_edges_stay_out_of_character_ledger_body() -> None:
    contract = CHARACTER_CONTRACT_PATH.read_text(encoding="utf-8")
    character_schema = json.loads(CHARACTER_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert "[KNOWLEDGE_EDGE.md](KNOWLEDGE_EDGE.md)" in contract
    assert "不住人物账本体" in contract
    assert "knowledge_edges" not in character_schema["properties"]
    assert character_schema["additionalProperties"] is False


def test_only_author_can_confirm_modify_or_retire() -> None:
    invalid = next(case for case in CASES if case["case_id"] == "KE-INVALID-07")
    with pytest.raises(MODULE.ContractError, match="AUTHOR_REQUIRED_FOR_FORMAL_ACTION"):
        MODULE.validate_document(invalid["document"])
    valid = next(case for case in CASES if case["case_id"] == "KE-VALID-04")
    action = MODULE.validate_document(valid["document"])
    assert action["writer_namespace"] == MODULE.WRITER_NAMESPACE
    assert action["requested_by"] == "AUTHOR"


def test_revision_chain_requires_base_revision_and_stable_identity() -> None:
    base_conflict = next(case for case in CASES if case["case_id"] == "KE-INVALID-13")
    with pytest.raises(MODULE.ContractError, match="BASE_REVISION_CONFLICT"):
        MODULE.validate_revision_transition(
            base_conflict["previous"],
            base_conflict["current"],
            base_conflict["action"],
        )
    identity_change = next(case for case in CASES if case["case_id"] == "KE-INVALID-14")
    with pytest.raises(MODULE.ContractError, match="STABLE_EDGE_IDENTITY_CHANGED"):
        MODULE.validate_revision_transition(
            identity_change["previous"],
            identity_change["current"],
            identity_change["action"],
        )


def test_current_and_historical_are_pointer_roles_not_mutable_revision_fields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    status = schema["$defs"]["version_status"]
    assert set(status["required"]) == {"confirmation", "lifecycle"}
    assert "revision_role" not in status["properties"]
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "current／historical 不写进不可变 revision" in contract
    assert "旧记录本身一个字不改" in contract


def test_permissions_are_full_task_scoped_or_closed() -> None:
    author = next(case for case in CASES if case["case_id"] == "KE-VALID-05")
    task = next(case for case in CASES if case["case_id"] == "KE-VALID-06")
    reader = next(case for case in CASES if case["case_id"] == "KE-VALID-07")
    assert MODULE.validate_document(author["document"])["access"] == "FULL_PROJECT"
    assert MODULE.validate_document(task["document"])["access"] == "TASK_SLICE"
    assert MODULE.validate_document(reader["document"])["access"] == "CLOSED"


def test_transaction_reuse_does_not_merge_fact_and_cognitive_state() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    for anchor in (
        "允许复用现有事务协调器",
        "知情边是独立对象",
        "认知状态不能写进事实状态",
        "事实确认不能自动确认知情边",
    ):
        assert anchor in contract


def test_contract_only_validator_does_not_import_runtime() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    validator = MODULE_PATH.read_text(encoding="utf-8")
    assert "CONTRACT_ONLY__WRITER_AND_READ_RUNTIME_NOT_AUTHORIZED" in contract
    assert "from mvp" not in validator
    assert "novel-mvp/mvp" not in validator
