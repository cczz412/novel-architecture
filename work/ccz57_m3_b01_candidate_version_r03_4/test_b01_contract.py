"""Targeted B-01 contract tests. All inputs are synthetic and offline."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path

import pytest

from b01_contract import (
    B01ContractError,
    B01Service,
    CandidatePointerSnapshotWriter,
    CandidateVersionStore,
    FixtureStore,
    SegmentIndexSnapshotWriter,
    VersionDiffProjector,
    canonical_bytes,
    make_read_only_child_fixture,
    make_fixture_input_record,
    record_ref,
    sha256_value,
    state_counts,
    state_file_hash,
    validate_admission,
    validate_lineage_locator,
    validate_pointer_snapshot,
    validate_record_ref,
    verify_state,
)
from self_check import (
    RuntimeAuditGuard,
    run_restart_process_probe,
    static_audit,
    writer_audit,
)
from fixtures import (
    FAILURE_SCENARIOS,
    NORMAL_SCENARIOS,
    b01_fixed_vectors,
    base_request,
    canonical_fixture_vector,
    inherited_fixed_vectors,
    interface_manifest_record,
    reference_records,
    review_receipt_record,
    run_failure_scenario,
    run_normal_scenario,
    valid_admission,
)


@pytest.mark.parametrize(
    "scenario_name",
    sorted(name for name in NORMAL_SCENARIOS if name != "N08_RESTART_READBACK"),
)
def test_normal_fixture_family(scenario_name: str, tmp_path: Path) -> None:
    result = run_normal_scenario(scenario_name, tmp_path / scenario_name)
    assert result


@pytest.mark.parametrize("scenario_name", sorted(FAILURE_SCENARIOS))
def test_failure_fixture_family_is_fail_closed(
    scenario_name: str, tmp_path: Path
) -> None:
    codes = run_failure_scenario(scenario_name, tmp_path / scenario_name)
    assert codes
    assert all(code.startswith("B01_") for code in codes)


@pytest.mark.parametrize(
    "crash_point",
    [
        "before_staging",
        "after_records_staged_before_pointer_cas",
        "after_pointer_staged_before_commit",
    ],
)
def test_precommit_crash_leaves_zero_visible_state(
    crash_point: str, tmp_path: Path
) -> None:
    root = tmp_path / crash_point
    request = base_request()
    request["crash_point"] = crash_point
    with pytest.raises(B01ContractError, match="B01_SIMULATED_CRASH"):
        B01Service(FixtureStore(root)).initialize_root_baseline(**request)
    assert state_counts(root / "state.json") == (0, 0, 0)
    assert state_file_hash(root / "state.json") is None


def test_n08_restart_readback_uses_distinct_python_processes(tmp_path: Path) -> None:
    evidence = run_restart_process_probe(tmp_path / "after-commit")
    prepare = evidence["prepare"]
    readback = evidence["readback"]
    assert evidence["harness_process_calls"] == 2
    assert prepare["pid"] != readback["pid"]
    assert prepare["state_file_hash"] == readback["state_file_hash"]
    assert prepare["result_hash"] == readback["result_hash"]
    assert readback["generation"] == 1
    assert all(
        not receipt["runtime_event_evidence"]["forbidden_events"]
        for receipt in (prepare, readback)
    )


def test_fixture_store_contains_only_contract_outputs(tmp_path: Path) -> None:
    root = tmp_path / "outputs"
    run_normal_scenario("N01_NONEMPTY_BASELINE", root)
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert {record["record_type"] for record in state["records"].values()} == {
        "M3_SEGMENT_INDEX_SNAPSHOT",
        "M3_CANDIDATE_VERSION",
        "M3_CANDIDATE_POINTER_SNAPSHOT",
    }
    assert len(state["pointers"]) == 1


def test_unique_writer_and_projector_surface_is_fixed() -> None:
    assert [
        SegmentIndexSnapshotWriter.__name__,
        CandidateVersionStore.__name__,
        CandidatePointerSnapshotWriter.__name__,
        VersionDiffProjector.__name__,
    ] == [
        "SegmentIndexSnapshotWriter",
        "CandidateVersionStore",
        "CandidatePointerSnapshotWriter",
        "VersionDiffProjector",
    ]


def test_canonical_json_is_nfc_compact_and_stable() -> None:
    vector = canonical_fixture_vector()
    assert bytes.fromhex(vector["canonical_utf8_hex"]) == canonical_bytes(
        {"z": "é", "a": [3, True, None, "synthetic"]}
    )
    assert len(vector["sha256"]) == 64


def test_only_fixture_pointer_namespace_can_be_written(tmp_path: Path) -> None:
    request = base_request()
    request["pointer_namespace"] = "PRODUCT"
    with pytest.raises(B01ContractError, match="B01_POINTER_SCOPE_MISMATCH"):
        B01Service(FixtureStore(tmp_path)).initialize_root_baseline(**request)
    assert state_counts(tmp_path / "state.json") == (0, 0, 0)


def test_runtime_event_evidence_contains_no_forbidden_event(tmp_path: Path) -> None:
    store = FixtureStore(tmp_path)
    B01Service(store).initialize_root_baseline(**base_request())
    assert set(store.events) <= {
        "fixture_storage_read",
        "fixture_storage_atomic_replace",
    }


def test_global_a_records_match_exact_generated_receipts() -> None:
    assert valid_admission()["record_hash"] == (
        "91257566a8c4fc662b5735ce1a1abebd905bf148b23ad594dfcf21b8410c65af"
    )
    assert review_receipt_record()["record_hash"] == (
        "7878b111cbc71b2f67710254015ecc327946190294f0a82e9ffb7dd9b0b6d75c"
    )
    assert interface_manifest_record()["record_hash"] == (
        "80751b702a335e1b733e975ac3905512ac54ec9f8f47922e2f975564542aeaa7"
    )


def test_admission_rejects_reissued_later_main_receipt() -> None:
    admission = valid_admission()
    admission["payload"]["current_main_sha"] = "a" * 40
    admission["record_hash"] = sha256_value(
        {key: value for key, value in admission.items() if key != "record_hash"}
    )
    with pytest.raises(B01ContractError, match="B01_A_ADMISSION_REQUIRED"):
        validate_admission(admission, reference_records=reference_records())


def test_admission_rejects_reissued_identity_with_same_claims() -> None:
    admission = valid_admission()
    admission["record_id"] = "replacement-admission"
    admission["created_at"] = "2026-08-28T05:00:00Z"
    admission["record_hash"] = sha256_value(
        {key: value for key, value in admission.items() if key != "record_hash"}
    )
    with pytest.raises(B01ContractError, match="B01_A_ADMISSION_REQUIRED"):
        validate_admission(admission, reference_records=reference_records())


def test_admission_rejects_wrong_repository_even_with_valid_hash() -> None:
    admission = valid_admission()
    admission["payload"]["repository"] = "wrong/repository"
    admission["record_hash"] = sha256_value(
        {key: value for key, value in admission.items() if key != "record_hash"}
    )
    with pytest.raises(B01ContractError, match="B01_A_ADMISSION_REQUIRED"):
        validate_admission(admission, reference_records=reference_records())


def test_record_ref_uses_contract_shape_and_resolves_original() -> None:
    record = interface_manifest_record()
    ref = record_ref(record)
    assert ref["contract"] == "M3_RECORD_REF"
    validate_record_ref(ref, records=[record], expected_type="A_INTERFACE_MANIFEST")
    forged = deepcopy(ref)
    forged["record_id"] = "missing"
    with pytest.raises(B01ContractError, match="B01_RECORD_REF_INVALID"):
        validate_record_ref(forged, records=[record])


def test_segment_output_uses_contract_start_end_and_rejects_boolean(
    tmp_path: Path,
) -> None:
    run_normal_scenario("N01_NONEMPTY_BASELINE", tmp_path / "valid")
    state = json.loads((tmp_path / "valid" / "state.json").read_text(encoding="utf-8"))
    segment = next(
        record
        for record in state["records"].values()
        if record["record_type"] == "M3_SEGMENT_INDEX_SNAPSHOT"
    )
    assert set(segment["payload"]["chapter_revision_ref"]) == {
        "chapter_id",
        "revision_no",
        "revision_text_sha256",
    }
    assert set(segment["payload"]["segments"][0]) == {
        "seg",
        "start",
        "end",
        "responsibility_text_sha256",
    }
    request = base_request()
    request["segment_inputs"][0]["start"] = False
    with pytest.raises(B01ContractError, match="B01_SEGMENT_INDEX_INVALID"):
        B01Service(FixtureStore(tmp_path / "boolean")).initialize_root_baseline(
            **request
        )


def test_quote_must_be_inside_selected_responsibility_text(tmp_path: Path) -> None:
    request = base_request(raw_items=[{"text": "fact", "quote": "outside quote"}])
    with pytest.raises(B01ContractError, match="B01_CANDIDATE_VERSION_INVALID"):
        B01Service(FixtureStore(tmp_path)).initialize_root_baseline(**request)
    assert state_counts(tmp_path / "state.json") == (0, 0, 0)


def test_nfc_input_commits_without_post_commit_false_failure(tmp_path: Path) -> None:
    request = base_request(
        raw_items=[{"text": "e\u0301", "quote": "synthetic quote one"}]
    )
    B01Service(FixtureStore(tmp_path)).initialize_root_baseline(**request)
    assert state_counts(tmp_path / "state.json") == (3, 1, 1)
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    candidate = next(
        record
        for record in state["records"].values()
        if record["record_type"] == "M3_CANDIDATE_VERSION"
    )
    assert candidate["payload"]["items"][0]["text"] == "é"


def test_segment_identity_collision_never_overwrites_first_record(
    tmp_path: Path,
) -> None:
    B01Service(FixtureStore(tmp_path)).initialize_root_baseline(**base_request())
    before = (tmp_path / "state.json").read_bytes()
    changed = base_request()
    changed["operation_id"] = "fixture-operation-002"
    changed["author_workspace_logical_key"] = "different-workspace"
    with pytest.raises(B01ContractError, match="B01_SEGMENT_INDEX_IDENTITY_COLLISION"):
        B01Service(FixtureStore(tmp_path)).initialize_root_baseline(**changed)
    assert (tmp_path / "state.json").read_bytes() == before


def test_segment_payload_idempotency_ignores_created_at(tmp_path: Path) -> None:
    first = B01Service(FixtureStore(tmp_path)).initialize_root_baseline(
        **base_request()
    )
    second_request = base_request(raw_items=[])
    second_request["seg"] = 2
    second_request["operation_id"] = "fixture-operation-002"
    second_request["created_at"] = "2026-08-28T12:01:00Z"
    second = B01Service(FixtureStore(tmp_path)).initialize_root_baseline(
        **second_request
    )
    assert first["segment_index_snapshot_ref"] == second[
        "segment_index_snapshot_ref"
    ]
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    segment_records = [
        record
        for record in state["records"].values()
        if record["record_type"] == "M3_SEGMENT_INDEX_SNAPSHOT"
    ]
    assert len(segment_records) == 1
    assert segment_records[0]["created_at"] == "2026-08-28T12:00:00Z"
    assert state_counts(tmp_path / "state.json") == (5, 2, 2)


def test_operation_replay_ignores_new_created_at_and_keeps_state_bytes(
    tmp_path: Path,
) -> None:
    service = B01Service(FixtureStore(tmp_path))
    first = service.initialize_root_baseline(**base_request())
    before = (tmp_path / "state.json").read_bytes()
    replay = base_request()
    replay["created_at"] = "2026-08-28T12:01:00Z"
    second = service.initialize_root_baseline(**replay)
    assert second == first
    assert (tmp_path / "state.json").read_bytes() == before
    assert state_counts(tmp_path / "state.json") == (3, 1, 1)


def test_corrupt_operation_replay_fails_reference_integrity(tmp_path: Path) -> None:
    B01Service(FixtureStore(tmp_path)).initialize_root_baseline(**base_request())
    state_path = tmp_path / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["records"] = {}
    state_path.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(B01ContractError, match="B01_REFERENCE_INTEGRITY_FAILED"):
        B01Service(FixtureStore(tmp_path)).initialize_root_baseline(**base_request())


def test_live_pointer_keeps_full_scope_and_generation(tmp_path: Path) -> None:
    B01Service(FixtureStore(tmp_path)).initialize_root_baseline(**base_request())
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    pointer = next(iter(state["pointers"].values()))
    assert set(pointer) == {
        "project_scope_id",
        "author_workspace_logical_key",
        "logical_pointer_key",
        "pointer_namespace",
        "chapter_revision_ref",
        "seg",
        "generation",
        "current_candidate_version_ref",
    }
    assert pointer["generation"] == 1
    verify_state(state, reference_records=reference_records())


def test_pointer_initialization_rejects_read_only_child_fixture(
    tmp_path: Path,
) -> None:
    run_normal_scenario("N01_NONEMPTY_BASELINE", tmp_path)
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    parent = next(
        record
        for record in state["records"].values()
        if record["record_type"] == "M3_CANDIDATE_VERSION"
    )
    child = make_read_only_child_fixture(
        parent,
        [
            {"text": "child one", "quote": "synthetic quote one"},
            {"text": "child two", "quote": "synthetic quote two"},
        ],
        reference_records=reference_records(),
    )
    request = base_request()
    pointer = CandidatePointerSnapshotWriter.build(
        project_scope_id=request["project_scope_id"],
        author_workspace_logical_key=request["author_workspace_logical_key"],
        chapter_revision_ref=request["chapter_revision_ref"],
        seg=request["seg"],
        candidate_ref=record_ref(child),
        operation_id="child-pointer-attempt",
        created_at=request["created_at"],
    )
    with pytest.raises(B01ContractError, match="B01_POINTER_SCOPE_MISMATCH"):
        validate_pointer_snapshot(
            pointer,
            records=[*reference_records(), parent, child],
        )


def test_candidate_idempotency_is_scoped_to_author_workspace() -> None:
    request = base_request()

    def build(workspace: str) -> dict[str, object]:
        return CandidateVersionStore.build_root(
            chapter_revision_ref=request["chapter_revision_ref"],
            seg=request["seg"],
            author_workspace_logical_key=workspace,
            origin_attempt_refs=request["origin_attempt_refs"],
            reference_records=request["reference_records"],
            responsibility_text=request["segment_inputs"][0][
                "responsibility_text"
            ],
            raw_items=request["raw_items"],
            created_at=request["created_at"],
        )

    state = FixtureStore.empty_state()
    first = build("workspace-one")
    second = build("workspace-two")
    first_ref = CandidateVersionStore.stage_root(
        state,
        first,
        author_workspace_logical_key="workspace-one",
        reference_records=reference_records(),
    )
    second_ref = CandidateVersionStore.stage_root(
        state,
        second,
        author_workspace_logical_key="workspace-two",
        reference_records=reference_records(),
    )
    assert first_ref != second_ref
    assert len(state["records"]) == 2


def test_lineage_locator_must_resolve_exact_candidate_item(tmp_path: Path) -> None:
    run_normal_scenario("N01_NONEMPTY_BASELINE", tmp_path)
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    candidate = next(
        record
        for record in state["records"].values()
        if record["record_type"] == "M3_CANDIDATE_VERSION"
    )
    locator = CandidateVersionStore.lineage_locator(
        candidate,
        candidate["payload"]["items"][0]["lineage_id"],
        reference_records=reference_records(),
    )
    locator["json_pointer"] = "/items/999"
    locator["locator_hash"] = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    with pytest.raises(B01ContractError, match="B01_LINEAGE_INDEX_INVALID"):
        validate_lineage_locator(locator, candidate_version=candidate)


def test_lineage_locator_rejects_rehashed_out_of_range_candidate(
    tmp_path: Path,
) -> None:
    run_normal_scenario("N01_NONEMPTY_BASELINE", tmp_path)
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    candidate = deepcopy(
        next(
            record
            for record in state["records"].values()
            if record["record_type"] == "M3_CANDIDATE_VERSION"
        )
    )
    candidate["payload"]["lineage_index"][0]["json_pointer"] = "/items/99"
    candidate["payload"]["version_payload_hash"] = sha256_value(
        {
            key: value
            for key, value in candidate["payload"].items()
            if key != "version_payload_hash"
        }
    )
    candidate["record_hash"] = sha256_value(
        {key: value for key, value in candidate.items() if key != "record_hash"}
    )
    first_item = candidate["payload"]["items"][0]
    locator = {
        "contract": "M3_LINEAGE_LOCATOR",
        "contract_version": "r03.3-candidate",
        "candidate_version_ref": record_ref(candidate),
        "lineage_id": first_item["lineage_id"],
        "json_pointer": "/items/99",
        "item_hash": first_item["item_hash"],
        "locator_hash": "",
    }
    locator["locator_hash"] = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    with pytest.raises(B01ContractError, match="B01_LINEAGE_INDEX_INVALID"):
        validate_lineage_locator(locator, candidate_version=candidate)


def test_version_diff_rejects_child_that_replaces_existing_lineage(
    tmp_path: Path,
) -> None:
    run_normal_scenario("N01_NONEMPTY_BASELINE", tmp_path)
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    parent = next(
        record
        for record in state["records"].values()
        if record["record_type"] == "M3_CANDIDATE_VERSION"
    )
    child = make_read_only_child_fixture(
        parent,
        [
            {"text": "child one", "quote": "synthetic quote one"},
            {"text": "child two", "quote": "synthetic quote two"},
        ],
        reference_records=reference_records(),
    )
    replacement_lineage = f"lin_{'f' * 64}"
    first_item = child["payload"]["items"][0]
    first_item["lineage_id"] = replacement_lineage
    item_preimage = {
        "lineage_id": replacement_lineage,
        "text": first_item["text"],
        "quote_if_present": first_item["quote"],
    }
    first_item["item_hash"] = sha256_value(item_preimage)
    child["payload"]["lineage_index"][0] = {
        "lineage_id": replacement_lineage,
        "json_pointer": "/items/0",
        "item_hash": first_item["item_hash"],
    }
    child["payload"]["version_payload_hash"] = sha256_value(
        {
            key: value
            for key, value in child["payload"].items()
            if key != "version_payload_hash"
        }
    )
    child["record_hash"] = sha256_value(
        {key: value for key, value in child.items() if key != "record_hash"}
    )
    with pytest.raises(B01ContractError, match="B01_VERSION_DIFF_INVALID"):
        VersionDiffProjector.project(
            parent,
            child,
            reference_records=reference_records(),
        )


def test_inherited_and_b01_fixed_vectors_are_frozen(tmp_path: Path) -> None:
    inherited = inherited_fixed_vectors()
    own = b01_fixed_vectors(tmp_path)
    assert all(vector["actual"] == vector["expected"] for vector in inherited.values())
    assert all(vector["actual"] == vector["expected"] for vector in own.values())


@pytest.mark.parametrize("value", [1.0, float("nan"), float("inf")])
def test_canonical_rejects_all_float_forms(value: float) -> None:
    with pytest.raises(B01ContractError, match="B01_CANONICAL_VALUE_INVALID"):
        canonical_bytes({"value": value})


def test_canonical_rejects_nfc_duplicate_keys() -> None:
    with pytest.raises(B01ContractError, match="B01_CANONICAL_DUPLICATE_KEY"):
        canonical_bytes({"é": 1, "e\u0301": 2})


def test_atomic_replace_failure_cleans_pending_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FixtureStore(tmp_path)

    def fail_replace(_source: os.PathLike[str], _target: os.PathLike[str]) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr("b01_contract.os.replace", fail_replace)
    with pytest.raises(B01ContractError, match="B01_TRANSACTION_WRITE_FAILED"):
        store.commit(FixtureStore.empty_state())
    assert not (tmp_path / ".state.json.pending").exists()
    assert not (tmp_path / "state.json").exists()


def test_fixture_store_rejects_repository_path_outside_unique_write_set() -> None:
    outside = Path(__file__).resolve().parents[2] / "work" / "another-ticket"
    with pytest.raises(B01ContractError, match="B01_WRITE_SET_ESCAPE"):
        FixtureStore(outside)


def test_fixture_input_helper_cannot_construct_b01_output() -> None:
    with pytest.raises(B01ContractError, match="B01_SCOPE_ESCAPE"):
        make_fixture_input_record(
            record_type="M3_CANDIDATE_VERSION",
            record_id="forbidden",
            record_version=1,
            payload={},
            created_at="2026-08-28T12:00:00Z",
        )


def test_runtime_audit_guard_rejects_network_event_without_opening_socket() -> None:
    guard = RuntimeAuditGuard()
    with pytest.raises(B01ContractError, match="B01_NETWORK_OR_PROCESS_EVENT"):
        guard.audit("socket.connect", ())
    assert guard.forbidden_events == ["socket.connect"]


def test_runtime_audit_guard_rejects_real_novel_path_without_reading_it() -> None:
    guard = RuntimeAuditGuard()
    with pytest.raises(B01ContractError, match="B01_SCOPE_ESCAPE"):
        guard.audit("open", ("/synthetic/local/trial_seven_books/book.txt", "r", 0))
    assert len(guard.real_novel_events) == 1


def test_static_and_unique_writer_audits_are_computed() -> None:
    audit = static_audit()
    assert all(value == 0 for value in audit["totals"].values())
    assert all(item["sha256"] for item in audit["files"])
    writers = writer_audit()
    assert writers["unique_writer_conflicts"] == 0
    assert writers["persisting_writer_classes"] == [
        "CandidatePointerSnapshotWriter",
        "CandidateVersionStore",
        "SegmentIndexSnapshotWriter",
    ]
