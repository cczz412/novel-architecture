"""Targeted B-01 contract tests. All inputs are synthetic and offline."""

from __future__ import annotations

import inspect
import json
import os
from copy import deepcopy
from pathlib import Path

import pytest

import product_source_adapter
from product_source_adapter import (
    FORBIDDEN_LOGICAL_KEYS,
    SAFE_LOGICAL_KEYS,
    build_author_workspace_source_generation,
)
from mvp import chapter_initial_admission_workspace, work_draft_workspace
from mvp.workspace import WorkspaceRouter

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
    admitted_request,
    b01_fixed_vectors,
    _all_candidate_refs,
    RESPONSIBILITY_TEXT_1,
    RESPONSIBILITY_TEXT_2,
    attempt_record,
    base_request,
    canonical_fixture_vector,
    fixture_runtime,
    inherited_fixed_vectors,
    initialize_request,
    interface_manifest_record,
    material_record,
    reference_records,
    review_receipt_record,
    run_failure_scenario,
    run_normal_scenario,
    source_generation_record,
    valid_admission,
)


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _seed_author_workspace_source(tmp_path: Path):
    runtime = tmp_path / "product-runtime"
    workspace = WorkspaceRouter(runtime).create_project(
        "author:b01-adapter-fixture", "B-01 合成来源"
    )
    text = RESPONSIBILITY_TEXT_1 + RESPONSIBILITY_TEXT_2
    work_draft_workspace.save_current_work_draft(
        workspace,
        {
            "operation_id": "op-b01-work-r1",
            "slot_ref": "S-B01-0001",
            "source_outline_ref": "S-B01-0001@outline-r1",
            "expected_rev": 0,
            "entry_mode": "typed",
            "author_text": text,
        },
    )
    receipt = chapter_initial_admission_workspace.commit_initial_work_draft(
        workspace,
        {
            "contract": "WORK_DRAFT_HANDOVER_ACTION",
            "version": "v2",
            "operation_id": "op-b01-handover-r1",
            "actor": "author",
            "intent": "adopt_as_manuscript",
            "work_ref": "S-B01-0001@work",
            "work_rev": 1,
            "slot_ref": "S-B01-0001",
            "source_outline_ref": "S-B01-0001@outline-r1",
            "chapter_title": "合成章节",
            "target_contract": "C1_CHAPTER_DOC",
            "target_planstore_result": "handover_parts",
        },
        "2026-08-31T12:00:00+08:00",
    )
    return runtime, workspace, receipt


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
    service, admit_extraction = fixture_runtime(FixtureStore(root))
    with pytest.raises(B01ContractError, match="B01_SIMULATED_CRASH"):
        initialize_request(service, admit_extraction, request)
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
    service, admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    with pytest.raises(B01ContractError, match="B01_POINTER_SCOPE_MISMATCH"):
        initialize_request(service, admit_extraction, request)
    assert state_counts(tmp_path / "state.json") == (0, 0, 0)


def test_runtime_event_evidence_contains_no_forbidden_event(tmp_path: Path) -> None:
    store = FixtureStore(tmp_path)
    service, admit_extraction = fixture_runtime(store)
    initialize_request(service, admit_extraction, base_request())
    assert set(store.events) <= {
        "fixture_storage_read",
        "fixture_storage_commit_attempt",
        "fixture_storage_mkdir_attempt",
        "fixture_storage_pending_write_attempt",
        "fixture_storage_atomic_replace_attempt",
        "fixture_storage_atomic_replace",
    }


def test_public_write_entry_has_no_named_raw_items_parameter() -> None:
    parameters = inspect.signature(B01Service.initialize_root_baseline).parameters
    assert "raw_items" not in parameters
    assert "extraction_admission" in parameters
    assert not hasattr(B01Service, "admit_ccz142_extraction_handoff")


def test_public_service_cannot_self_compose_runtime(tmp_path: Path) -> None:
    with pytest.raises(B01ContractError, match="B01_RUNTIME_COMPOSITION_REQUIRED"):
        B01Service(FixtureStore(tmp_path))


def test_public_write_entry_rejects_direct_raw_items_before_write(
    tmp_path: Path,
) -> None:
    service, _admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    with pytest.raises(B01ContractError, match="B01_EXTRACTION_ADMISSION_REQUIRED"):
        service.initialize_root_baseline(**base_request())
    assert state_counts(tmp_path / "state.json") == (0, 0, 0)


@pytest.mark.parametrize(
    "source_lane",
    [
        "CANVAS_PLAN_FACTS",
        "CHAPTER_KERNEL",
        "C3_PREVIEW",
        "GENERIC_JSON",
    ],
)
def test_source_adapter_rejects_non_extraction_lanes(
    source_lane: str, tmp_path: Path
) -> None:
    _service, admit_extraction = fixture_runtime(FixtureStore(tmp_path / source_lane))
    with pytest.raises(B01ContractError, match="B01_EXTRACTION_SOURCE_INVALID"):
        admitted_request(
            admit_extraction,
            base_request(),
            source_lane=source_lane,
        )
    assert state_counts(tmp_path / source_lane / "state.json") == (0, 0, 0)


@pytest.mark.parametrize("material_kind", ["CORE_CHARACTER", "GENRE"])
def test_genre_and_core_character_are_independently_optional(
    material_kind: str, tmp_path: Path
) -> None:
    generation = source_generation_record()
    material = material_record(material_kind, source_generation=generation)
    request = base_request()
    request.update(
        {
            "reference_records": [
                review_receipt_record(),
                interface_manifest_record(),
                attempt_record(),
                generation,
                material,
            ],
            "accepted_source_generation_ref": record_ref(generation),
            "writing_material_refs": [
                {
                    "material_kind": material_kind,
                    "material_ref": record_ref(material),
                }
            ],
        }
    )
    service, admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    result = initialize_request(service, admit_extraction, request)
    assert result["candidate_version_ref"]["record_type"] == "M3_CANDIDATE_VERSION"


def test_product_source_adapter_reads_only_safe_metadata_and_initializes_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, workspace, receipt = _seed_author_workspace_source(tmp_path)
    before = _tree_bytes(runtime)
    read_keys: list[str] = []
    original_read = product_source_adapter._read_workspace_entry

    def observed_read(workspace_handle, logical_key: str):
        read_keys.append(logical_key)
        return original_read(workspace_handle, logical_key)

    monkeypatch.setattr(product_source_adapter, "_read_workspace_entry", observed_read)
    source = build_author_workspace_source_generation(workspace, chapter_id="c01")

    assert _tree_bytes(runtime) == before
    assert set(read_keys) == set(SAFE_LOGICAL_KEYS)
    assert len(read_keys) == 2 * len(SAFE_LOGICAL_KEYS)
    assert set(read_keys).isdisjoint(FORBIDDEN_LOGICAL_KEYS)
    assert source["chapter_revision_ref"] == receipt["chapter_revision_ref"]
    assert source["writing_material_refs"] == []
    assert source["product_writes"] == 0
    assert source["model_api_calls"] == 0
    assert source["real_novel_body_reads"] == 0

    request = base_request()
    request.update(
        {
            "reference_records": [
                review_receipt_record(),
                interface_manifest_record(),
                attempt_record(),
                source["source_generation_record"],
            ],
            "project_scope_id": source["project_scope_id"],
            "author_workspace_logical_key": source["author_workspace_logical_key"],
            "chapter_revision_ref": source["chapter_revision_ref"],
            "accepted_source_generation_ref": source["accepted_source_generation_ref"],
            "writing_material_refs": [],
            "source_module_identity": source["source_module_identity"],
        }
    )
    service, admit_extraction = fixture_runtime(FixtureStore(tmp_path / "b01"))
    result = initialize_request(service, admit_extraction, request)
    assert result["candidate_version_ref"]["record_type"] == "M3_CANDIDATE_VERSION"
    assert _tree_bytes(runtime) == before


def test_product_source_adapter_rejects_double_read_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _runtime, workspace, _receipt = _seed_author_workspace_source(tmp_path)
    original_read = product_source_adapter._read_workspace_entry
    chapter_index_reads = 0

    def drifting_read(workspace_handle, logical_key: str):
        nonlocal chapter_index_reads
        value = original_read(workspace_handle, logical_key)
        if logical_key == "chapter_index":
            chapter_index_reads += 1
            if chapter_index_reads == 2:
                value = deepcopy(value)
                value["version"] += 1
        return value

    monkeypatch.setattr(product_source_adapter, "_read_workspace_entry", drifting_read)
    with pytest.raises(B01ContractError, match="B01_PRODUCT_SOURCE_SNAPSHOT_DRIFT"):
        build_author_workspace_source_generation(workspace, chapter_id="c01")


def test_admission_rejects_plain_forged_copied_and_cross_service_capabilities(
    tmp_path: Path,
) -> None:
    issuing_service, admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    prepared = admitted_request(admit_extraction, base_request())
    valid_capability = prepared["extraction_admission"]
    invalid_capabilities = [
        {},
        type(valid_capability)(),
        deepcopy(valid_capability),
    ]
    for capability in invalid_capabilities:
        attempt = dict(prepared)
        attempt["extraction_admission"] = capability
        with pytest.raises(B01ContractError, match="B01_EXTRACTION_ADMISSION_REQUIRED"):
            issuing_service.initialize_root_baseline(**attempt)

    other_service, _other_admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    with pytest.raises(B01ContractError, match="B01_EXTRACTION_ADMISSION_REQUIRED"):
        other_service.initialize_root_baseline(**prepared)
    assert state_counts(tmp_path / "state.json") == (0, 0, 0)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("project_scope_id", "other-project"),
        ("author_workspace_logical_key", "other-workspace"),
        ("chapter_revision_ref", {}),
        ("accepted_source_generation_ref", {}),
        ("segment_inputs", []),
        ("seg", 2),
        ("writing_material_refs", []),
        ("origin_attempt_refs", []),
        ("source_module_identity", "M2_READ_ONLY_ADAPTER"),
    ],
)
def test_admission_is_bound_to_exact_initialization_request(
    field: str, replacement: object, tmp_path: Path
) -> None:
    service, admit_extraction = fixture_runtime(FixtureStore(tmp_path / field))
    prepared = admitted_request(admit_extraction, base_request())
    prepared[field] = replacement
    with pytest.raises(B01ContractError, match="B01_EXTRACTION_ADMISSION_MISMATCH"):
        service.initialize_root_baseline(**prepared)
    assert state_counts(tmp_path / field / "state.json") == (0, 0, 0)


def test_admission_seals_items_and_allows_same_operation_replay(
    tmp_path: Path,
) -> None:
    service, admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    request = base_request()
    prepared = admitted_request(admit_extraction, request)
    request["raw_items"][0]["fact"] = "凭证签发后修改的内容"
    first = service.initialize_root_baseline(**prepared)
    before = (tmp_path / "state.json").read_bytes()
    replay = dict(prepared)
    replay["created_at"] = "2026-08-28T12:01:00Z"
    second = service.initialize_root_baseline(**replay)
    assert second == first
    assert (tmp_path / "state.json").read_bytes() == before
    assert b"extraction_admission" not in before
    assert b"CCZ142_TEXT_EXTRACTION_CANDIDATES" not in before
    state = json.loads(before)
    candidate = next(
        record
        for record in state["records"].values()
        if record["record_type"] == "M3_CANDIDATE_VERSION"
    )
    assert candidate["payload"]["items"][0]["fact"] == "甲进入北塔。"


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


def test_segment_output_uses_utf8_byte_ranges_and_rejects_boolean(
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
        "start_byte",
        "end_byte",
        "responsibility_text_sha256",
    }
    request = base_request()
    request["segment_inputs"][0]["start_byte"] = False
    service, admit_extraction = fixture_runtime(FixtureStore(tmp_path / "boolean"))
    with pytest.raises(B01ContractError, match="B01_SEGMENT_INDEX_INVALID"):
        initialize_request(service, admit_extraction, request)


def test_evidence_must_be_inside_selected_responsibility_text(tmp_path: Path) -> None:
    request = base_request(
        raw_items=[
            {
                "fact": "fact",
                "status": "已发生",
                "evidence": "outside evidence。",
            }
        ]
    )
    service, admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    with pytest.raises(B01ContractError, match="B01_EVIDENCE_NOT_IN_EXACT_CHAPTER"):
        initialize_request(service, admit_extraction, request)
    assert state_counts(tmp_path / "state.json") == (0, 0, 0)


def test_nfc_input_commits_without_post_commit_false_failure(tmp_path: Path) -> None:
    request = base_request(
        raw_items=[
            {
                "fact": "e\u0301",
                "status": "已发生",
                "evidence": "甲走进北塔。",
            }
        ]
    )
    service, admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    initialize_request(service, admit_extraction, request)
    assert state_counts(tmp_path / "state.json") == (3, 1, 1)
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    candidate = next(
        record
        for record in state["records"].values()
        if record["record_type"] == "M3_CANDIDATE_VERSION"
    )
    assert candidate["payload"]["items"][0]["fact"] == "é"


def test_segment_identity_collision_never_overwrites_first_record(
    tmp_path: Path,
) -> None:
    first_service, first_admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    initialize_request(first_service, first_admit_extraction, base_request())
    before = (tmp_path / "state.json").read_bytes()
    changed = base_request()
    changed["operation_id"] = "fixture-operation-002"
    changed["author_workspace_logical_key"] = "different-workspace"
    second_service, second_admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    with pytest.raises(B01ContractError, match="B01_SEGMENT_INDEX_IDENTITY_COLLISION"):
        initialize_request(second_service, second_admit_extraction, changed)
    assert (tmp_path / "state.json").read_bytes() == before


def test_segment_payload_idempotency_ignores_created_at(tmp_path: Path) -> None:
    first_service, first_admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    first = initialize_request(first_service, first_admit_extraction, base_request())
    second_request = base_request(raw_items=[])
    second_request["seg"] = 2
    second_request["operation_id"] = "fixture-operation-002"
    second_request["created_at"] = "2026-08-28T12:01:00Z"
    second_service, second_admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    second = initialize_request(
        second_service,
        second_admit_extraction,
        second_request,
    )
    assert first["segment_index_snapshot_ref"] == second["segment_index_snapshot_ref"]
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
    service, admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    first = initialize_request(service, admit_extraction, base_request())
    before = (tmp_path / "state.json").read_bytes()
    replay = base_request()
    replay["created_at"] = "2026-08-28T12:01:00Z"
    second = initialize_request(service, admit_extraction, replay)
    assert second == first
    assert (tmp_path / "state.json").read_bytes() == before
    assert state_counts(tmp_path / "state.json") == (3, 1, 1)


def test_corrupt_operation_replay_fails_reference_integrity(tmp_path: Path) -> None:
    first_service, first_admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    initialize_request(first_service, first_admit_extraction, base_request())
    state_path = tmp_path / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["records"] = {}
    state_path.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
    replay_service, replay_admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    with pytest.raises(B01ContractError, match="B01_REFERENCE_INTEGRITY_FAILED"):
        initialize_request(replay_service, replay_admit_extraction, base_request())


def test_live_pointer_keeps_full_scope_and_generation(tmp_path: Path) -> None:
    service, admit_extraction = fixture_runtime(FixtureStore(tmp_path))
    initialize_request(service, admit_extraction, base_request())
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    pointer = next(iter(state["pointers"].values()))
    assert set(pointer) == {
        "project_scope_id",
        "author_workspace_logical_key",
        "logical_pointer_key",
        "pointer_namespace",
        "candidate_schema_id",
        "input_binding_hash",
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
            {
                "fact": "child one",
                "status": "已发生",
                "evidence": "甲走进北塔。",
            },
            {
                "fact": "child two",
                "status": "已发生",
                "evidence": "甲拿起铜钥匙。",
                "speaker": "旁白",
            },
        ],
        reference_records=_all_candidate_refs(tmp_path),
    )
    request = base_request()
    pointer = CandidatePointerSnapshotWriter.build(
        project_scope_id=request["project_scope_id"],
        author_workspace_logical_key=request["author_workspace_logical_key"],
        chapter_revision_ref=request["chapter_revision_ref"],
        seg=request["seg"],
        input_binding_hash=parent["payload"]["extraction_input_binding"][
            "input_binding_hash"
        ],
        candidate_ref=record_ref(child),
        operation_id="child-pointer-attempt",
        created_at=request["created_at"],
    )
    with pytest.raises(B01ContractError, match="B01_POINTER_SCOPE_MISMATCH"):
        validate_pointer_snapshot(
            pointer,
            records=[*_all_candidate_refs(tmp_path), parent, child],
        )


def test_candidate_idempotency_is_scoped_to_author_workspace(tmp_path: Path) -> None:
    first_request = base_request()
    first_request["author_workspace_logical_key"] = "workspace-one"
    second_request = base_request()
    second_request["author_workspace_logical_key"] = "workspace-two"
    first_service, first_admit_extraction = fixture_runtime(
        FixtureStore(tmp_path / "one")
    )
    second_service, second_admit_extraction = fixture_runtime(
        FixtureStore(tmp_path / "two")
    )
    first_ref = initialize_request(
        first_service,
        first_admit_extraction,
        first_request,
    )["candidate_version_ref"]
    second_ref = initialize_request(
        second_service,
        second_admit_extraction,
        second_request,
    )["candidate_version_ref"]
    assert first_ref != second_ref


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
        reference_records=_all_candidate_refs(tmp_path),
    )
    locator["json_pointer"] = "/items/999"
    locator["locator_hash"] = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    with pytest.raises(B01ContractError, match="B01_LINEAGE_INDEX_INVALID"):
        validate_lineage_locator(
            locator,
            candidate_version=candidate,
            reference_records=_all_candidate_refs(tmp_path),
        )


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
        "contract_version": "r03.5-candidate",
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
        validate_lineage_locator(
            locator,
            candidate_version=candidate,
            reference_records=_all_candidate_refs(tmp_path),
        )


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
            {
                "fact": "child one",
                "status": "已发生",
                "evidence": "甲走进北塔。",
            },
            {
                "fact": "child two",
                "status": "已发生",
                "evidence": "甲拿起铜钥匙。",
                "speaker": "旁白",
            },
        ],
        reference_records=_all_candidate_refs(tmp_path),
    )
    replacement_lineage = f"lin_{'f' * 64}"
    first_item = child["payload"]["items"][0]
    first_item["lineage_id"] = replacement_lineage
    item_preimage = {
        "lineage_id": replacement_lineage,
        "fact": first_item["fact"],
        "status": first_item["status"],
        "evidence": first_item["evidence"],
        "evidence_binding": first_item["evidence_binding"],
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
            reference_records=_all_candidate_refs(tmp_path),
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
