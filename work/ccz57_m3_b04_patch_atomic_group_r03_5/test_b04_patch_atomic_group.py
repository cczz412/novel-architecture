from __future__ import annotations

import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from threading import Event
from typing import Any, Callable

import pytest

from b04_contracts import (
    B04ContractError,
    CANDIDATE_SCHEMA_ID,
    EXPECTED_B01_MERGE_SHA,
    EXPECTED_B02_MERGE_SHA,
    EXPECTED_CURRENT_MAIN,
    PROJECTOR_MAP,
    RUN_ACCESS,
    WRITER_MAP,
    canonical_bytes,
    guard_runtime_event,
    guard_write_path,
    record_ref,
    reference_cycle_count,
    sha256_value,
    validate_construction_gate,
    validate_protection_record,
)
from b04_store import B04Service, FixtureStore
from fixtures import (
    FAILURE_FIXTURES,
    NORMAL_FIXTURES,
    bound_recheck_stack,
    build_authoritative_b02_store,
    route_inputs,
)
from patch_preview_projection import PatchPreviewProjector, validate_patch_preview

ROOT = Path(__file__).resolve().parent
LEGACY_ROOT = ROOT.parent / "ccz57_m3_b04_patch_atomic_group_r03_4"
B03_RUNTIME_ROOT = (
    ROOT.parent / "ccz57_m3_b03_bound_evidence_read_r03_5" / ".pytest-runtime-b04"
)
LEGACY_MANIFEST_SHA256 = (
    "5f9e896429ef7b2497c931d0f450d4f0b9689217f8bf07a189c6236aad7f188b"
)


@pytest.fixture(autouse=True)
def clean_b03_runtime() -> Any:
    if B03_RUNTIME_ROOT.exists():
        shutil.rmtree(B03_RUNTIME_ROOT)
    yield
    if B03_RUNTIME_ROOT.exists():
        shutil.rmtree(B03_RUNTIME_ROOT)


def _args(route: str) -> dict[str, Any]:
    args = route_inputs(route)
    args.pop("catalog")
    return args


def _service(
    tmp_path: Path,
    failure_point: str | None = None,
    *,
    b03_service: Any | None = None,
) -> tuple[FixtureStore, B04Service, Any]:
    data = route_inputs("replace_only")["catalog"]
    b02_store, b02_service = build_authoritative_b02_store(tmp_path / "b02-store", data)
    store = FixtureStore(tmp_path / "b04-store", failure_point=failure_point)
    return (
        store,
        B04Service(
            store,
            b02_store=b02_store,
            b03_service=b03_service,
        ),
        b02_service,
    )


def _propose(
    tmp_path: Path, route: str, **overrides: Any
) -> tuple[FixtureStore, dict[str, Any]]:
    store, service, _ = _service(tmp_path)
    args = _args(route)
    args.update(overrides)
    return store, service.propose(**args)


def _records_by_type(store: FixtureStore) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for record in store.read_records():
        result.setdefault(record["record_type"], []).append(record)
    return result


def _rehash_group(group: dict[str, Any]) -> None:
    group["group_payload_hash"] = sha256_value(
        {key: value for key, value in group.items() if key != "group_payload_hash"}
    )


def _rehash_record(record: dict[str, Any]) -> None:
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )


def _assert_failure_unchanged(
    tmp_path: Path,
    route: str,
    mutate: Callable[[dict[str, Any]], None],
    code: str,
) -> None:
    store, service, _ = _service(tmp_path)
    args = _args(route)
    mutate(args)
    before_files = store.file_snapshot()
    before_objects = store.object_snapshot()
    with pytest.raises(B04ContractError) as caught:
        service.propose(**args)
    assert caught.value.code == code
    assert store.file_snapshot() == before_files
    assert store.object_snapshot() == before_objects


def test_n01_diagnostic_only_replacement_is_full_item(tmp_path: Path) -> None:
    store, result = _propose(tmp_path, "replace_only")
    records = _records_by_type(store)
    assert set(records) == {"M3_CANDIDATE_PROTECTION_SET", "M3_PATCH_PROPOSAL"}
    patch = records["M3_PATCH_PROPOSAL"][0]
    operation = patch["payload"]["atomic_groups"][0]["operations"][0]
    assert operation["operation_kind"] == "REPLACE_CANDIDATE_ITEM"
    assert set(operation["new_item"]) == {
        "lineage_id",
        "fact",
        "status",
        "evidence",
        "evidence_binding",
    }
    assert "item_hash" not in operation["new_item"]
    assert patch["payload"]["candidate_schema_id"] == CANDIDATE_SCHEMA_ID
    assert patch["payload"]["coverage_observation_refs"] == []
    validate_patch_preview(result["patch_preview"])


def test_n02_missing_coverage_authorizes_complete_add(tmp_path: Path) -> None:
    store, result = _propose(tmp_path, "add_only")
    patch = _records_by_type(store)["M3_PATCH_PROPOSAL"][0]
    operation = patch["payload"]["atomic_groups"][0]["operations"][0]
    assert operation["operation_kind"] == "ADD_CANDIDATE_ITEM"
    assert operation["target_collection_pointer"] == "/items"
    assert operation["new_item"]["lineage_id"].startswith("lin_")
    assert "item_hash" not in operation["new_item"]
    assert (
        operation["supporting_coverage_refs"]
        == patch["payload"]["coverage_observation_refs"]
    )
    assert result["patch_preview"]["diagnostic_refs"] == []


def test_n03_partial_coverage_authorizes_replacement_evidence(tmp_path: Path) -> None:
    store, _ = _propose(tmp_path, "replace_with_evidence")
    patch = _records_by_type(store)["M3_PATCH_PROPOSAL"][0]
    operation = patch["payload"]["atomic_groups"][0]["operations"][0]
    assert operation["supporting_diagnostic_refs"]
    assert operation["supporting_coverage_refs"]
    assert operation["new_item"]["evidence"] == "甲走进北塔。甲拿起铜钥匙。"


def test_n04_groups_can_be_previewed_independently(tmp_path: Path) -> None:
    store, _ = _propose(tmp_path, "replace_and_add")
    records = _records_by_type(store)
    protection = records["M3_CANDIDATE_PROTECTION_SET"][0]
    patch = records["M3_PATCH_PROPOSAL"][0]
    first = PatchPreviewProjector.project(
        context=route_inputs("replace_and_add")["context"],
        protection=protection,
        patch=patch,
        causal_records=[],
        selected_group_ids={"replace-existing"},
    )
    second = PatchPreviewProjector.project(
        context=route_inputs("replace_and_add")["context"],
        protection=protection,
        patch=patch,
        causal_records=[],
        selected_group_ids={"add-missing"},
    )
    assert [item["atomic_group_id"] for item in first["atomic_group_previews"]] == [
        "replace-existing"
    ]
    assert [item["atomic_group_id"] for item in second["atomic_group_previews"]] == [
        "add-missing"
    ]
    assert first["patch_ref"] == second["patch_ref"]
    assert [
        item["json_pointer"]
        for item in second["atomic_group_previews"][0]["protected_item_summaries"]
    ] == ["/items/0", "/items/1"]
    add_only = route_inputs("add_only")["groups"][0]["operations"][0]
    mixed_add = route_inputs("replace_and_add")["groups"][1]["operations"][0]
    assert add_only["new_item"]["lineage_id"] == mixed_add["new_item"]["lineage_id"]


def test_n05_protection_is_exact_untouched_item_complement(tmp_path: Path) -> None:
    store, _ = _propose(tmp_path, "replace_and_add")
    protection = _records_by_type(store)["M3_CANDIDATE_PROTECTION_SET"][0]
    entries = protection["payload"]["protected_entries"]
    assert len(entries) == 1
    assert entries[0]["json_pointer"] == "/items/1"
    assert (
        entries[0]["protected_item_hash"] == entries[0]["lineage_locator"]["item_hash"]
    )
    assert entries[0]["reason"] == "UNTOUCHED_BY_THIS_PATCH_PROTECTED"


def test_n06_b03_absence_does_not_block_coverage_patch(tmp_path: Path) -> None:
    _, result = _propose(tmp_path, "add_only")
    assert result["patch_preview"]["authorized_source_slice_refs"] == []


def test_n06_exact_b03_recheck_can_only_bind_old_evidence(tmp_path: Path) -> None:
    data = route_inputs("replace_only")["catalog"]
    stack = bound_recheck_stack(tmp_path / "b03-store", data)
    _, service, _ = _service(tmp_path, b03_service=stack["service"])
    args = _args("replace_only")
    args["source_slice_records"] = stack["records"]
    result = service.propose(**args)
    refs = result["patch_preview"]["authorized_source_slice_refs"]
    assert len(refs) == 1
    assert refs[0]["record_type"] == "M3_AUTHORIZED_SOURCE_SLICE"


def test_n07_patch_persists_exact_coverage_provenance(tmp_path: Path) -> None:
    store, result = _propose(tmp_path, "replace_and_add")
    patch = _records_by_type(store)["M3_PATCH_PROPOSAL"][0]
    top_level = patch["payload"]["coverage_observation_refs"]
    operation = patch["payload"]["atomic_groups"][1]["operations"][0]
    assert top_level == operation["supporting_coverage_refs"]
    assert result["patch_preview"]["coverage_observation_refs"] == top_level


def test_n08_causal_sidecar_is_separate_and_noncommittable(tmp_path: Path) -> None:
    store, result = _propose(tmp_path, "causal_sidecar")
    records = _records_by_type(store)
    causal = records["M3_CAUSAL_HINT_PROPOSAL"][0]
    assert causal["payload"]["noncommittable"] is True
    assert causal["payload"]["evidence_locators"]
    assert (
        result["patch_preview"]["noncommittable_sidecar_proposals"][0]["committable"]
        is False
    )
    assert "FACT_CAUSAL_EDGE" not in canonical_bytes(records).decode("utf-8")


def test_n09_replay_is_idempotent(tmp_path: Path) -> None:
    store, service, _ = _service(tmp_path)
    args = _args("replace_and_add")
    first = service.propose(**args)
    first_files = store.file_snapshot()
    second = service.propose(**args)
    assert second == first
    assert store.file_snapshot() == first_files
    assert len(store.read_records()) == 2


def test_n09_later_distinct_patch_reuses_exact_protection_original(
    tmp_path: Path,
) -> None:
    store, service, _ = _service(tmp_path)
    first_args = _args("replace_only")
    second_args = deepcopy(first_args)
    second_args["created_at"] = "2026-08-30T02:10:01Z"
    operation = second_args["groups"][0]["operations"][0]
    operation["new_item"]["fact"] = "甲已经站在北塔内。"
    _rehash_group(second_args["groups"][0])

    first = service.propose(**first_args)
    second = service.propose(**second_args)

    assert second["protection_set_ref"] == first["protection_set_ref"]
    assert second["patch_proposal_ref"] != first["patch_proposal_ref"]
    records = _records_by_type(store)
    assert len(records["M3_CANDIDATE_PROTECTION_SET"]) == 1
    assert len(records["M3_PATCH_PROPOSAL"]) == 2


def test_n09_later_semantic_replay_reuses_all_exact_originals(tmp_path: Path) -> None:
    store, service, _ = _service(tmp_path)
    first_args = _args("replace_only")
    replay_args = deepcopy(first_args)
    replay_args["created_at"] = "2026-08-30T02:10:01Z"

    first = service.propose(**first_args)
    first_files = store.file_snapshot()
    replay = service.propose(**replay_args)

    assert replay == first
    assert store.file_snapshot() == first_files
    assert len(store.read_records()) == 2


def test_n09_same_payload_different_access_fails_before_staging(
    tmp_path: Path,
) -> None:
    store, service, _ = _service(tmp_path)
    service.propose(**_args("replace_only"))
    before_files = store.file_snapshot()
    before_objects = store.object_snapshot()
    conflicting = _args("replace_only")
    conflicting["created_at"] = "2026-08-30T02:10:01Z"
    conflicting["access"] = RUN_ACCESS

    with pytest.raises(B04ContractError) as caught:
        service.propose(**conflicting)

    assert caught.value.code == "B04_IMMUTABLE_IDENTITY_COLLISION"
    assert store.file_snapshot() == before_files
    assert store.object_snapshot() == before_objects


def test_n09_two_store_instances_serialize_same_root_publish(tmp_path: Path) -> None:
    data = route_inputs("replace_only")["catalog"]
    b02_store, _ = build_authoritative_b02_store(tmp_path / "b02-store", data)
    shared_root = tmp_path / "b04-store"
    first_store = FixtureStore(shared_root)
    second_store = FixtureStore(shared_root)
    first_service = B04Service(first_store, b02_store=b02_store)
    second_service = B04Service(second_store, b02_store=b02_store)
    first_args = _args("replace_only")
    second_args = deepcopy(first_args)
    second_args["created_at"] = "2026-08-30T02:10:01Z"

    first_at_publish = Event()
    release_first = Event()
    second_started = Event()

    def hold_first_publish() -> None:
        first_at_publish.set()
        assert release_first.wait(timeout=5)

    def run_second() -> dict[str, Any]:
        second_started.set()
        return second_service.propose(**second_args)

    first_store.before_publish_guard_hook = hold_first_publish
    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(first_service.propose, **first_args)
        assert first_at_publish.wait(timeout=5)
        second_future = executor.submit(run_second)
        try:
            assert second_started.wait(timeout=5)
            assert not second_future.done()
        finally:
            release_first.set()
        first = first_future.result(timeout=5)
        second = second_future.result(timeout=5)

    assert second == first
    assert len(first_store.read_records()) == 2
    assert len(list((shared_root / "transactions").iterdir())) == 1


def test_n10_preview_has_complete_items_and_no_decision_fields(tmp_path: Path) -> None:
    _, result = _propose(tmp_path, "replace_and_add")
    preview = result["patch_preview"]
    encoded = canonical_bytes(preview).decode("utf-8")
    for key in ("fact", "status", "evidence", "speaker_if_present"):
        assert f'"{key}"' in encoded
    for forbidden in (
        "author_decision",
        "accepted_group_ids",
        "child_candidate_version_ref",
        "formal_fact_ref",
    ):
        assert forbidden not in encoded
    assert preview["forbidden_b05_record_types_present"] == []


def test_source_evidence_keeps_original_unicode_bytes() -> None:
    evidence = "甲看见e\u0301。"
    payload = {"ordinary_label": "Cafe\u0301", "evidence": evidence}
    reopened = json.loads(canonical_bytes(payload))
    assert reopened["evidence"] == evidence
    assert reopened["evidence"].encode("utf-8") == evidence.encode("utf-8")
    assert reopened["ordinary_label"] == "Café"


def test_legacy_b04_manifest_is_unchanged() -> None:
    assert hashlib.sha256(
        (LEGACY_ROOT / "MANIFEST.sha256").read_bytes()
    ).hexdigest() == (LEGACY_MANIFEST_SHA256)


def test_construction_gate_is_exact() -> None:
    validate_construction_gate(
        current_main_sha=EXPECTED_CURRENT_MAIN,
        b01_merge_sha=EXPECTED_B01_MERGE_SHA,
        b02_merge_sha=EXPECTED_B02_MERGE_SHA,
    )
    with pytest.raises(B04ContractError, match="B04_CURRENT_MAIN_DRIFT"):
        validate_construction_gate(
            current_main_sha="0" * 40,
            b01_merge_sha=EXPECTED_B01_MERGE_SHA,
            b02_merge_sha=EXPECTED_B02_MERGE_SHA,
        )


def test_f01_legacy_operation_is_rejected(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        operation = args["groups"][0]["operations"][0]
        operation["operation_kind"] = "REPLACE_FIELD"
        _rehash_group(args["groups"][0])

    _assert_failure_unchanged(
        tmp_path,
        "replace_only",
        mutate,
        "B04_LEGACY_OR_COMMITTABLE_OPERATION_FORBIDDEN",
    )


def test_f02_old_item_hash_drift_is_rejected(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        args["groups"][0]["operations"][0]["expected_old_item_hash"] = "0" * 64
        _rehash_group(args["groups"][0])

    _assert_failure_unchanged(
        tmp_path, "replace_only", mutate, "B04_REPLACE_OLD_ITEM_HASH_MISMATCH"
    )


def test_f03_replacement_requires_supporting_diagnostic(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        args["groups"][0]["operations"][0]["supporting_diagnostic_refs"] = []
        _rehash_group(args["groups"][0])

    _assert_failure_unchanged(
        tmp_path, "replace_only", mutate, "B04_REPLACE_DIAGNOSTIC_INVALID"
    )


def test_f04_terminal_diagnostic_is_rejected(tmp_path: Path) -> None:
    store, service, b02_service = _service(tmp_path)
    data = route_inputs("replace_only")["catalog"]
    terminal = data["terminal_lifecycle"]
    payload = terminal["payload"]
    b02_service.append_lifecycle(
        diagnostic_ref=deepcopy(payload["diagnostic_ref"]),
        lifecycle_sequence=payload["lifecycle_sequence"],
        event=payload["event"],
        effective_at=payload["effective_at"],
        reason_code=payload["reason_code"],
        created_at=terminal["created_at"],
    )
    before = store.visible_snapshot()
    with pytest.raises(B04ContractError, match="B04_REPLACE_DIAGNOSTIC_NOT_OPEN"):
        service.propose(**_args("replace_only"))
    assert store.visible_snapshot() == before == []


def test_f05_evidence_change_requires_coverage(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        args["coverages"] = []
        args["groups"][0]["operations"][0]["supporting_coverage_refs"] = []
        _rehash_group(args["groups"][0])

    _assert_failure_unchanged(
        tmp_path, "replace_with_evidence", mutate, "B04_REPLACE_COVERAGE_REQUIRED"
    )


def test_f06_replacement_coverage_must_match_new_evidence(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        operation = args["groups"][0]["operations"][0]
        old = args["context"]["candidate_version"]["payload"]["items"][0]
        operation["new_item"]["evidence"] = old["evidence"]
        operation["new_item"]["evidence_binding"] = deepcopy(old["evidence_binding"])
        _rehash_group(args["groups"][0])

    _assert_failure_unchanged(
        tmp_path,
        "replace_with_evidence",
        mutate,
        "B04_REPLACE_COVERAGE_BINDING_MISMATCH",
    )


def test_f07_add_requires_coverage(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        data = route_inputs("replace_only")["catalog"]
        args["diagnostics"] = [deepcopy(data["diagnostic"])]
        args["coverages"] = []
        args["groups"][0]["operations"][0]["supporting_coverage_refs"] = []
        _rehash_group(args["groups"][0])

    _assert_failure_unchanged(tmp_path, "add_only", mutate, "B04_ADD_COVERAGE_INVALID")


def test_f08_matched_coverage_cannot_authorize_add(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        data = route_inputs("add_only")["catalog"]
        matched = deepcopy(data["matched_coverage"])
        args["coverages"] = [matched]
        args["groups"][0]["operations"][0]["supporting_coverage_refs"] = [
            record_ref(matched)
        ]
        _rehash_group(args["groups"][0])

    _assert_failure_unchanged(
        tmp_path, "add_only", mutate, "B04_ADD_COVERAGE_MATCH_INVALID"
    )


def test_f09_add_evidence_binding_drift_is_rejected(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        operation = args["groups"][0]["operations"][0]
        operation["new_item"]["evidence_binding"]["evidence_sha256"] = "0" * 64
        operation["new_item"]["evidence_binding"]["binding_hash"] = sha256_value(
            {
                key: value
                for key, value in operation["new_item"]["evidence_binding"].items()
                if key != "binding_hash"
            }
        )
        _rehash_group(args["groups"][0])

    _assert_failure_unchanged(
        tmp_path, "add_only", mutate, "B04_EVIDENCE_BINDING_INVALID"
    )


def test_f10_caller_chosen_add_lineage_is_rejected(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        args["groups"][0]["operations"][0]["new_item"]["lineage_id"] = "lin_" + "0" * 64
        _rehash_group(args["groups"][0])

    _assert_failure_unchanged(
        tmp_path, "add_only", mutate, "B04_ADD_LINEAGE_ID_MISMATCH"
    )


@pytest.mark.parametrize("field", ["status", "evidence_binding"])
def test_f11_incomplete_new_item_is_rejected(tmp_path: Path, field: str) -> None:
    def mutate(args: dict[str, Any]) -> None:
        del args["groups"][0]["operations"][0]["new_item"][field]
        _rehash_group(args["groups"][0])

    _assert_failure_unchanged(tmp_path, "add_only", mutate, "B04_NEW_ITEM_INVALID")


def test_f11_item_hash_injection_is_rejected(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        args["groups"][0]["operations"][0]["new_item"]["item_hash"] = "0" * 64
        _rehash_group(args["groups"][0])

    _assert_failure_unchanged(tmp_path, "add_only", mutate, "B04_NEW_ITEM_INVALID")


def test_f12_group_hash_drift_is_rejected(tmp_path: Path) -> None:
    _assert_failure_unchanged(
        tmp_path,
        "replace_only",
        lambda args: args["groups"][0].__setitem__("purpose", "漂移"),
        "B04_ATOMIC_GROUP_HASH_MISMATCH",
    )


def test_f12_duplicate_operation_is_rejected(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        group = args["groups"][0]
        group["operations"].append(deepcopy(group["operations"][0]))
        _rehash_group(group)

    _assert_failure_unchanged(
        tmp_path, "replace_only", mutate, "B04_OPERATION_DUPLICATE"
    )


def test_f13_protection_complement_drift_is_rejected(tmp_path: Path) -> None:
    store, _ = _propose(tmp_path, "replace_and_add")
    records = _records_by_type(store)
    protection = deepcopy(records["M3_CANDIDATE_PROTECTION_SET"][0])
    protection["payload"]["protected_entries"] = []
    _rehash_record(protection)
    args = route_inputs("replace_and_add")
    with pytest.raises(B04ContractError, match="B04_PROTECTION_COMPLEMENT_MISMATCH"):
        validate_protection_record(
            protection,
            context=args["context"],
            policy=args["policy"],
            groups=args["groups"],
        )


def test_f14_unused_top_level_coverage_is_rejected(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        data = route_inputs("replace_only")["catalog"]
        args["coverages"] = [deepcopy(data["missing_coverage"])]

    _assert_failure_unchanged(
        tmp_path, "replace_only", mutate, "B04_UNUSED_OR_MISSING_COVERAGE_REF"
    )


def test_f15_candidate_contract_drift_is_rejected(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        base = args["context"]["candidate_version"]
        base["contract_version"] = "r03.3-candidate"
        base["record_contract_version"] = "r03.3-candidate"
        _rehash_record(base)

    _assert_failure_unchanged(tmp_path, "replace_only", mutate, "B04_B01_INPUT_INVALID")


def test_f16_committable_causal_sidecar_is_rejected(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        args["causal_payloads"][0]["noncommittable"] = False

    _assert_failure_unchanged(
        tmp_path, "causal_sidecar", mutate, "B04_CAUSAL_MUST_BE_NONCOMMITTABLE"
    )


def test_f17_preview_cannot_persist_or_call_other_writers(tmp_path: Path) -> None:
    _, result = _propose(tmp_path, "replace_only")
    with pytest.raises(B04ContractError, match="B04_PREVIEW_PERSISTENCE_FORBIDDEN"):
        PatchPreviewProjector.persist(result["patch_preview"])
    store, _ = _propose(tmp_path / "second", "replace_only")
    records = _records_by_type(store)
    args = route_inputs("replace_only")
    with pytest.raises(B04ContractError, match="B03_WRITER_CALL_FORBIDDEN"):
        PatchPreviewProjector.project(
            context=args["context"],
            protection=records["M3_CANDIDATE_PROTECTION_SET"][0],
            patch=records["M3_PATCH_PROPOSAL"][0],
            causal_records=[],
            attempt_b03_writer=True,
        )
    with pytest.raises(B04ContractError, match="B05_CALL_FORBIDDEN"):
        PatchPreviewProjector.project(
            context=args["context"],
            protection=records["M3_CANDIDATE_PROTECTION_SET"][0],
            patch=records["M3_PATCH_PROPOSAL"][0],
            causal_records=[],
            attempt_b05_call=True,
        )


def test_f17_preview_failure_happens_before_publish(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        args["groups"][0]["purpose"] = "M3_PATCH_DECISION"
        _rehash_group(args["groups"][0])

    _assert_failure_unchanged(
        tmp_path,
        "replace_only",
        mutate,
        "B04_PREVIEW_B05_REFERENCE_FORBIDDEN",
    )


@pytest.mark.parametrize(
    "failure_point",
    [
        "after_protection_staging",
        "after_patch_staging",
        "before_final_graph_check",
        "before_atomic_publish",
    ],
)
def test_f18_transaction_failure_has_zero_visible_records(
    tmp_path: Path, failure_point: str
) -> None:
    store, service, _ = _service(tmp_path, failure_point=failure_point)
    before = store.file_snapshot()
    before_visible = store.visible_snapshot()
    with pytest.raises(B04ContractError, match="B04_SIMULATED_TRANSACTION_FAILURE"):
        service.propose(**_args("replace_only"))
    assert store.file_snapshot() == before == []
    assert store.object_snapshot() == []
    assert store.visible_snapshot() == before_visible == []


def test_f19_write_set_and_runtime_guards() -> None:
    guard_write_path("work/ccz57_m3_b04_patch_atomic_group_r03_5/fixture.json")
    with pytest.raises(B04ContractError, match="B04_WRITE_SET_ESCAPE"):
        guard_write_path("work/ccz57_m3_b04_patch_atomic_group_r03_4/fixture.json")
    for event in (
        "network",
        "model_api",
        "subprocess",
        "real_novel_read",
        "patch_apply",
        "candidate_version_write",
        "formal_fact_write",
    ):
        with pytest.raises(B04ContractError, match="B04_FORBIDDEN_RUNTIME_EVENT"):
            guard_runtime_event(event)


def test_f20_source_slice_does_not_replace_coverage(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        data = route_inputs("replace_with_evidence")["catalog"]
        stack = bound_recheck_stack(tmp_path / "b03-no-coverage", data)
        args["coverages"] = []
        args["source_slice_records"] = stack["records"]
        args["groups"][0]["operations"][0]["supporting_coverage_refs"] = []
        _rehash_group(args["groups"][0])

    _assert_failure_unchanged(
        tmp_path, "replace_with_evidence", mutate, "B04_REPLACE_COVERAGE_REQUIRED"
    )


def test_f20_source_slice_cannot_be_attached_to_add(tmp_path: Path) -> None:
    def mutate(args: dict[str, Any]) -> None:
        data = route_inputs("add_only")["catalog"]
        stack = bound_recheck_stack(tmp_path / "b03-add", data)
        args["source_slice_records"] = stack["records"]

    _assert_failure_unchanged(
        tmp_path, "add_only", mutate, "B04_SOURCE_SLICE_SCOPE_INVALID"
    )


def test_f21_revoked_b03_slice_is_rejected_before_publish(tmp_path: Path) -> None:
    data = route_inputs("replace_only")["catalog"]
    stack = bound_recheck_stack(tmp_path / "b03-revoked", data)
    store, service, _ = _service(tmp_path, b03_service=stack["service"])
    stack["service"].lifecycle(
        stack["consent_ref"],
        event="REVOKED",
        effective_at="2026-08-29T06:02:00Z",
        created_at="2026-08-29T06:02:00Z",
    )
    before = store.visible_snapshot()
    args = _args("replace_only")
    args["source_slice_records"] = stack["records"]
    with pytest.raises(B04ContractError, match="B04_B03_SOURCE_NOT_ACTIVE"):
        service.propose(**args)
    assert store.visible_snapshot() == before == []


def test_f21_b03_revocation_before_linearization_guard_has_zero_writes(
    tmp_path: Path,
) -> None:
    data = route_inputs("replace_only")["catalog"]
    stack = bound_recheck_stack(tmp_path / "b03-late-revocation", data)
    store, service, _ = _service(tmp_path, b03_service=stack["service"])

    def revoke_consent() -> None:
        store.before_publish_guard_hook = None
        stack["service"].lifecycle(
            stack["consent_ref"],
            event="REVOKED",
            effective_at="2026-08-29T06:02:00Z",
            created_at="2026-08-29T06:02:00Z",
        )

    store.before_publish_guard_hook = revoke_consent
    args = _args("replace_only")
    args["source_slice_records"] = stack["records"]
    before = store.visible_snapshot()
    with pytest.raises(B04ContractError, match="B04_B03_SOURCE_NOT_ACTIVE"):
        service.propose(**args)
    assert store.visible_snapshot() == before == []


def test_f21_b03_slice_requires_authoritative_current_reader(tmp_path: Path) -> None:
    data = route_inputs("replace_only")["catalog"]
    stack = bound_recheck_stack(tmp_path / "b03-reader-required", data)
    store, service, _ = _service(tmp_path)
    args = _args("replace_only")
    args["source_slice_records"] = stack["records"]
    before = store.visible_snapshot()
    with pytest.raises(B04ContractError, match="B04_B03_CURRENT_STATE_READER_REQUIRED"):
        service.propose(**args)
    assert store.visible_snapshot() == before == []


def test_f22_b02_change_before_publish_guard_leaves_zero_writes(
    tmp_path: Path,
) -> None:
    store, service, b02_service = _service(tmp_path)
    terminal = route_inputs("replace_only")["catalog"]["terminal_lifecycle"]

    def close_diagnostic() -> None:
        store.before_publish_guard_hook = None
        payload = terminal["payload"]
        b02_service.append_lifecycle(
            diagnostic_ref=deepcopy(payload["diagnostic_ref"]),
            lifecycle_sequence=payload["lifecycle_sequence"],
            event=payload["event"],
            effective_at=payload["effective_at"],
            reason_code=payload["reason_code"],
            created_at=terminal["created_at"],
        )

    store.before_publish_guard_hook = close_diagnostic
    before = store.visible_snapshot()
    with pytest.raises(B04ContractError, match="B04_B02_CURRENT_STATE_CHANGED"):
        service.propose(**_args("replace_only"))
    assert store.visible_snapshot() == before == []


def test_fixed_contract_counts_and_reference_graph(tmp_path: Path) -> None:
    store, _ = _propose(tmp_path, "causal_sidecar")
    assert len(WRITER_MAP) == 3
    assert PROJECTOR_MAP == {"PatchPreview": "PatchPreviewProjector"}
    assert len(NORMAL_FIXTURES) == 10
    assert len(FAILURE_FIXTURES) == 22
    assert reference_cycle_count(store.read_records()) == 0
