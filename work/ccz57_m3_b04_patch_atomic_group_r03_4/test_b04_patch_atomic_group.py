"""Offline acceptance tests for CCZ-57 M3 B-04."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import pytest

import fixtures
from b04_contracts import (
    B04ContractError,
    EXPECTED_CURRENT_MAIN,
    FORBIDDEN_B05_TYPES,
    canonical_bytes,
    record_ref,
    sha256_value,
    validate_construction_gate,
    validate_patch_record,
    validate_protection_record,
)
from b04_store import B04Service, FixtureStore
from patch_preview_projection import PatchPreviewProjector, validate_patch_preview

ROOT = Path(__file__).resolve().parent


def _load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _rehash_record(record: dict[str, Any]) -> dict[str, Any]:
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    return record


def _rehash_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt["receipt_hash"] = sha256_value(
        {key: value for key, value in receipt.items() if key != "receipt_hash"}
    )
    return receipt


def _rehash_group(group: dict[str, Any]) -> dict[str, Any]:
    group["group_payload_hash"] = sha256_value(
        {key: value for key, value in group.items() if key != "group_payload_hash"}
    )
    return group


def _service(
    tmp_path: Path, *, failure_point: str | None = None
) -> tuple[FixtureStore, B04Service]:
    store = FixtureStore(tmp_path / "b04-store", failure_point=failure_point)
    return store, B04Service(store)


def _propose(service: B04Service, route: str, **overrides: Any) -> dict[str, Any]:
    inputs = fixtures.route_inputs(route)
    inputs.update(overrides)
    return service.propose(**inputs)


def _assert_failure_unchanged(
    store: FixtureStore, code: str, action: Callable[[], Any]
) -> B04ContractError:
    files_before = store.file_snapshot()
    objects_before = store.object_snapshot()
    with pytest.raises(B04ContractError) as caught:
        action()
    assert caught.value.code == code
    assert store.file_snapshot() == files_before
    assert store.object_snapshot() == objects_before
    return caught.value


def _records_by_type(store: FixtureStore) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for record in store.read_records():
        result.setdefault(record["record_type"], []).append(record)
    return result


def test_n01_no_source_slice_exact_vector(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    result = _propose(service, "NO_SOURCE_SLICE")
    expected = fixtures.fixed_route("NO_SOURCE_SLICE")
    records = _records_by_type(store)
    assert records["M3_CANDIDATE_PROTECTION_SET"] == [
        fixtures.FIXED["shared_unaffected"]["protection_set_record"]
    ]
    assert records["M3_CAUSAL_HINT_PROPOSAL"] == [
        expected["causal_hint_proposal_record"]
    ]
    assert records["M3_PATCH_PROPOSAL"] == [expected["patch_proposal_record"]]
    assert result["patch_preview"] == expected["patch_preview"]
    assert (
        sha256_value(result["patch_preview"])
        == expected["expected"]["patch_preview"]["projection_sha256"]
    )


def test_n02_single_replace_group(tmp_path: Path) -> None:
    _, service = _service(tmp_path)
    groups = [deepcopy(fixtures.FIXED["shared_unaffected"]["atomic_groups"][0])]
    result = _propose(service, "NO_SOURCE_SLICE", groups=groups, causal_payloads=[])
    assert len(result["patch_preview"]["atomic_group_previews"]) == 1
    assert (
        result["patch_preview"]["atomic_group_previews"][0]["proposed_changes"][0][
            "json_pointer"
        ]
        == "/items/0/text"
    )


def test_n03_single_add_group(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    groups = [deepcopy(fixtures.FIXED["shared_unaffected"]["atomic_groups"][1])]
    result = _propose(service, "NO_SOURCE_SLICE", groups=groups, causal_payloads=[])
    protection = _records_by_type(store)["M3_CANDIDATE_PROTECTION_SET"][0]
    assert len(protection["payload"]["protected_entries"]) == 2
    assert (
        result["patch_preview"]["atomic_group_previews"][0]["proposed_changes"][0][
            "json_pointer"
        ]
        == "/items/-"
    )


def _apply_group(base: dict[str, Any], group: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(base)
    for operation in group["operations"]:
        if operation["operation_kind"] == "REPLACE_FIELD":
            index = int(operation["json_pointer"].split("/")[2])
            value["payload"]["items"][index]["text"] = operation["new_value"]
        else:
            value["payload"]["items"].append(deepcopy(operation["new_item"]))
    return value


def test_n04_groups_are_independently_applicable() -> None:
    groups = fixtures.FIXED["shared_unaffected"]["atomic_groups"]
    first = _apply_group(fixtures.BASE, groups[0])
    second = _apply_group(fixtures.BASE, groups[1])
    both = _apply_group(first, groups[1])
    assert first["payload"]["items"][0]["text"] == "角色甲已经进入北塔。"
    assert len(first["payload"]["items"]) == 2
    assert second["payload"]["items"][0]["text"] == "角色甲进入北塔。"
    assert len(second["payload"]["items"]) == 3
    assert len(both["payload"]["items"]) == 3


def test_n05_protection_set_is_exact_complement(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    _propose(service, "NO_SOURCE_SLICE")
    protection = _records_by_type(store)["M3_CANDIDATE_PROTECTION_SET"][0]
    assert [
        item["json_pointer"] for item in protection["payload"]["protected_entries"]
    ] == ["/items/1/text"]
    assert protection == fixtures.FIXED["shared_unaffected"]["protection_set_record"]


def test_n06_empty_source_slice_never_calls_b03(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    result = _propose(service, "NO_SOURCE_SLICE")
    patch = _records_by_type(store)["M3_PATCH_PROPOSAL"][0]
    assert patch["payload"]["authorized_source_slice_refs"] == []
    for group in result["patch_preview"]["atomic_group_previews"]:
        assert group["evidence_refs"] == patch["payload"]["diagnostic_refs"]
    assert all("b03" not in event["event"].lower() for event in store.events)


def test_n07_b03_r02_source_slice_exact_vector(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    result = _propose(service, "B03_R02_SOURCE_SLICE")
    expected = fixtures.fixed_route("B03_R02_SOURCE_SLICE")
    records = _records_by_type(store)
    assert records["M3_CAUSAL_HINT_PROPOSAL"] == [
        expected["causal_hint_proposal_record"]
    ]
    assert records["M3_PATCH_PROPOSAL"] == [expected["patch_proposal_record"]]
    assert result["patch_preview"] == expected["patch_preview"]


def test_n08_causal_sidecar_is_noncommittable(tmp_path: Path) -> None:
    _, service = _service(tmp_path)
    result = _propose(service, "B03_R02_SOURCE_SLICE")
    assert (
        result["patch_preview"]["noncommittable_sidecar_proposals"][0]["committable"]
        is False
    )
    assert all(
        operation["operation_kind"] != "ADD_CAUSAL_HINT"
        for group in fixtures.FIXED["shared_unaffected"]["atomic_groups"]
        for operation in group["operations"]
    )


def test_n09_replay_is_idempotent_and_routes_do_not_alias(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    first = _propose(service, "NO_SOURCE_SLICE")
    snapshot = store.object_snapshot()
    replay = _propose(service, "NO_SOURCE_SLICE")
    assert replay == first
    assert store.object_snapshot() == snapshot
    source = _propose(service, "B03_R02_SOURCE_SLICE")
    source_snapshot = store.object_snapshot()
    source_replay = _propose(service, "B03_R02_SOURCE_SLICE")
    assert source_replay == source
    assert store.object_snapshot() == source_snapshot
    assert first["patch_proposal_ref"] != source["patch_proposal_ref"]
    assert len(source_snapshot) == 5


def test_n10_projection_is_deterministic_and_contains_no_b05_refs(
    tmp_path: Path,
) -> None:
    store, service = _service(tmp_path)
    for route in ("NO_SOURCE_SLICE", "B03_R02_SOURCE_SLICE"):
        result = _propose(service, route)
        expected_hash = fixtures.fixed_route(route)["expected"]["patch_preview"][
            "projection_sha256"
        ]
        hashes = {sha256_value(result["patch_preview"]) for _ in range(100)}
        assert hashes == {expected_hash}
        serialized = canonical_bytes(result["patch_preview"]).decode("utf-8")
        assert all(record_type not in serialized for record_type in FORBIDDEN_B05_TYPES)


def test_f01_a_admission_drift_fails_closed(tmp_path: Path) -> None:
    store, _ = _service(tmp_path)
    a = _load("A_INTERFACE_ADMISSION_RECEIPT.fixture.json")
    a["payload"]["merge_commit_sha"] = "0" * 64
    _assert_failure_unchanged(
        store,
        "B04_ADMISSION_FAILED",
        lambda: validate_construction_gate(
            a_admission=a,
            b01_receipt=_load("B01_MERGE_READBACK_RECEIPT.fixture.json"),
            b02_receipt=_load("B02_MERGE_READBACK_RECEIPT.fixture.json"),
            current_main_sha=EXPECTED_CURRENT_MAIN,
        ),
    )


def test_f02_b02_draft_or_wrong_head_fails_closed(tmp_path: Path) -> None:
    store, _ = _service(tmp_path)
    b02 = _load("B02_MERGE_READBACK_RECEIPT.fixture.json")
    b02["pr"]["merged"] = False
    _rehash_receipt(b02)
    _assert_failure_unchanged(
        store,
        "B04_B02_NOT_MERGED",
        lambda: validate_construction_gate(
            a_admission=_load("A_INTERFACE_ADMISSION_RECEIPT.fixture.json"),
            b01_receipt=_load("B01_MERGE_READBACK_RECEIPT.fixture.json"),
            b02_receipt=b02,
            current_main_sha=EXPECTED_CURRENT_MAIN,
        ),
    )


def test_f03_b02_tree_or_receipt_drift_fails_closed(tmp_path: Path) -> None:
    store, _ = _service(tmp_path)
    b02 = _load("B02_MERGE_READBACK_RECEIPT.fixture.json")
    b02["merged_b02_artifacts"]["git_tree"] = "0" * 40
    _rehash_receipt(b02)
    _assert_failure_unchanged(
        store,
        "B04_B02_READBACK_FAILED",
        lambda: validate_construction_gate(
            a_admission=_load("A_INTERFACE_ADMISSION_RECEIPT.fixture.json"),
            b01_receipt=_load("B01_MERGE_READBACK_RECEIPT.fixture.json"),
            b02_receipt=b02,
            current_main_sha=EXPECTED_CURRENT_MAIN,
        ),
    )


def test_f04_upstream_diagnostic_drift_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    diagnostic = deepcopy(fixtures.DIAGNOSTIC)
    diagnostic["payload"]["seg"] = 2
    _rehash_record(diagnostic)
    _assert_failure_unchanged(
        store,
        "B04_DIAGNOSTIC_SEG_MISMATCH",
        lambda: _propose(service, "NO_SOURCE_SLICE", diagnostics=[diagnostic]),
    )


def test_f05_immutable_envelope_extra_key_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    base = deepcopy(fixtures.BASE)
    base["extra"] = True
    _assert_failure_unchanged(
        store,
        "B04_IMMUTABLE_SHAPE_INVALID",
        lambda: _propose(service, "NO_SOURCE_SLICE", base=base),
    )


def test_f06_lineage_locator_drift_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    diagnostic = deepcopy(fixtures.DIAGNOSTIC)
    diagnostic["payload"]["target"]["lineage_locator"]["item_hash"] = "0" * 64
    _rehash_record(diagnostic)
    _assert_failure_unchanged(
        store,
        "B04_LINEAGE_LOCATOR_INVALID",
        lambda: _propose(service, "NO_SOURCE_SLICE", diagnostics=[diagnostic]),
    )


def test_f07_disabled_protection_policy_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    policy = deepcopy(fixtures.POLICY)
    policy["payload"]["protect_untouched_fields"] = False
    _rehash_record(policy)
    _assert_failure_unchanged(
        store,
        "B04_PROTECTION_POLICY_INVALID",
        lambda: _propose(service, "NO_SOURCE_SLICE", policy=policy),
    )


def test_f08_protection_complement_drift_fails_closed(tmp_path: Path) -> None:
    store, _ = _service(tmp_path)
    protection = deepcopy(fixtures.FIXED["shared_unaffected"]["protection_set_record"])
    protection["payload"]["protected_entries"] = []
    _rehash_record(protection)
    _assert_failure_unchanged(
        store,
        "B04_PROTECTION_COMPLEMENT_MISMATCH",
        lambda: validate_protection_record(
            protection,
            base=fixtures.BASE,
            policy=fixtures.POLICY,
            groups=fixtures.FIXED["shared_unaffected"]["atomic_groups"],
        ),
    )


def test_f09_patch_target_overlaps_protected_entry(tmp_path: Path) -> None:
    store, _ = _service(tmp_path)
    protection = deepcopy(fixtures.FIXED["shared_unaffected"]["protection_set_record"])
    item0 = deepcopy(protection["payload"]["protected_entries"][0])
    item0["lineage_locator"] = deepcopy(fixtures.LOCATOR_1)
    item0["json_pointer"] = "/items/0/text"
    item0["value_hash"] = sha256_value(fixtures.BASE["payload"]["items"][0]["text"])
    protection["payload"]["protected_entries"].insert(0, item0)
    _rehash_record(protection)
    route = fixtures.fixed_route("NO_SOURCE_SLICE")
    patch = deepcopy(route["patch_proposal_record"])
    patch["payload"]["protection_set_ref"] = record_ref(protection)
    _rehash_record(patch)
    causal = route["causal_hint_proposal_record"]
    _assert_failure_unchanged(
        store,
        "B04_PROTECTED_TARGET_OVERLAP",
        lambda: validate_patch_record(
            patch,
            base=fixtures.BASE,
            diagnostics=[fixtures.DIAGNOSTIC],
            coverages=[fixtures.COVERAGE],
            protection=protection,
            causal_records=[causal],
            source_slice_revision=None,
        ),
    )


def test_f10_patch_payload_shape_drift_fails_closed(tmp_path: Path) -> None:
    store, _ = _service(tmp_path)
    route = fixtures.fixed_route("NO_SOURCE_SLICE")
    patch = deepcopy(route["patch_proposal_record"])
    patch["payload"]["route"] = "FORBIDDEN"
    _rehash_record(patch)
    _assert_failure_unchanged(
        store,
        "B04_PATCH_PAYLOAD_INVALID",
        lambda: validate_patch_record(
            patch,
            base=fixtures.BASE,
            diagnostics=[fixtures.DIAGNOSTIC],
            coverages=[fixtures.COVERAGE],
            protection=fixtures.FIXED["shared_unaffected"]["protection_set_record"],
            causal_records=[route["causal_hint_proposal_record"]],
            source_slice_revision=None,
        ),
    )


def test_f11_unapproved_source_slice_ref_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    ref = deepcopy(fixtures.B03_CATALOG["refs"]["M3_AUTHORIZED_SOURCE_SLICE"])
    ref["record_id"] += "-other"
    _assert_failure_unchanged(
        store,
        "SOURCE_SLICE_RECORD_REF_MISMATCH",
        lambda: _propose(
            service,
            "B03_R02_SOURCE_SLICE",
            source_slice_refs=[ref],
        ),
    )


def test_f12_replace_pointer_drift_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    groups = deepcopy(fixtures.FIXED["shared_unaffected"]["atomic_groups"])
    groups[0]["operations"][0]["json_pointer"] = "/items/0/quote"
    _rehash_group(groups[0])
    _assert_failure_unchanged(
        store,
        "B04_REPLACE_TARGET_INVALID",
        lambda: _propose(service, "NO_SOURCE_SLICE", groups=groups),
    )


def test_f13_add_with_matched_coverage_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    coverage = deepcopy(fixtures.COVERAGE)
    coverage["payload"]["candidate_match"] = "MATCHED"
    _rehash_record(coverage)
    _assert_failure_unchanged(
        store,
        "B04_ADD_COVERAGE_REQUIRED",
        lambda: _propose(service, "NO_SOURCE_SLICE", coverages=[coverage]),
    )


def test_f14_causal_operation_is_forbidden(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    groups = deepcopy(fixtures.FIXED["shared_unaffected"]["atomic_groups"])
    groups[0]["operations"] = [{"operation_kind": "ADD_CAUSAL_HINT"}]
    _rehash_group(groups[0])
    _assert_failure_unchanged(
        store,
        "FORBIDDEN_COMMITTABLE_OPERATION",
        lambda: _propose(service, "NO_SOURCE_SLICE", groups=groups),
    )


def test_f15_duplicate_operation_across_groups_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    groups = deepcopy(fixtures.FIXED["shared_unaffected"]["atomic_groups"])
    groups[1]["operations"] = [deepcopy(groups[0]["operations"][0])]
    _rehash_group(groups[1])
    _assert_failure_unchanged(
        store,
        "B04_OPERATION_DUPLICATE",
        lambda: _propose(service, "NO_SOURCE_SLICE", groups=groups),
    )


def test_f16_group_hash_drift_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    groups = deepcopy(fixtures.FIXED["shared_unaffected"]["atomic_groups"])
    groups[0]["group_payload_hash"] = "0" * 64
    _assert_failure_unchanged(
        store,
        "B04_ATOMIC_GROUP_HASH_MISMATCH",
        lambda: _propose(service, "NO_SOURCE_SLICE", groups=groups),
    )


def test_f17_cross_group_target_overlap_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    groups = deepcopy(fixtures.FIXED["shared_unaffected"]["atomic_groups"])
    duplicate_target = deepcopy(groups[0]["operations"][0])
    duplicate_target["new_value"] = "角色甲已抵达北塔。"
    groups[1]["operations"] = [duplicate_target]
    _rehash_group(groups[1])
    _assert_failure_unchanged(
        store,
        "B04_CROSS_GROUP_TARGET_OVERLAP",
        lambda: _propose(service, "NO_SOURCE_SLICE", groups=groups),
    )


def test_f18_cross_group_dependency_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    groups = deepcopy(fixtures.FIXED["shared_unaffected"]["atomic_groups"])
    dependent = deepcopy(groups[0]["operations"][0])
    dependent["target"]["lineage_id"] = "lin_fact_003"
    groups[0]["operations"] = [dependent]
    _rehash_group(groups[0])
    _assert_failure_unchanged(
        store,
        "B04_CROSS_GROUP_DEPENDENCY",
        lambda: _propose(service, "NO_SOURCE_SLICE", groups=groups),
    )


def test_f19_committable_causal_proposal_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    payload = deepcopy(
        fixtures.fixed_route("NO_SOURCE_SLICE")["causal_hint_proposal_record"][
            "payload"
        ]
    )
    payload["noncommittable"] = False
    _assert_failure_unchanged(
        store,
        "B04_CAUSAL_MUST_BE_NONCOMMITTABLE",
        lambda: _propose(service, "NO_SOURCE_SLICE", causal_payloads=[payload]),
    )


def test_f20_b05_output_in_preview_fails_closed(tmp_path: Path) -> None:
    store, _ = _service(tmp_path)
    preview = deepcopy(fixtures.fixed_route("NO_SOURCE_SLICE")["patch_preview"])
    preview["route"] = "ROUTE_TO_B06"
    _assert_failure_unchanged(
        store,
        "B04_PREVIEW_SHAPE_INVALID",
        lambda: validate_patch_preview(preview),
    )


def test_f21_patch_preview_cannot_be_persisted(tmp_path: Path) -> None:
    store, _ = _service(tmp_path)
    preview = fixtures.fixed_route("NO_SOURCE_SLICE")["patch_preview"]
    _assert_failure_unchanged(
        store,
        "B04_PREVIEW_PERSISTENCE_FORBIDDEN",
        lambda: PatchPreviewProjector.persist(preview),
    )


def test_f22_identity_conflict_and_crashes_leave_visible_store_unchanged(
    tmp_path: Path,
) -> None:
    store, service = _service(tmp_path)
    _propose(service, "NO_SOURCE_SLICE")
    existing = _records_by_type(store)["M3_CAUSAL_HINT_PROPOSAL"][0]
    conflict = deepcopy(existing)
    conflict["payload"]["hint_kind"] = "DRIFT"
    _rehash_record(conflict)
    _assert_failure_unchanged(
        store,
        "B04_IMMUTABLE_IDENTITY_COLLISION",
        lambda: store._commit_bundle([conflict]),
    )
    for point in (
        "after_protection_staging",
        "after_causal_staging",
        "after_patch_staging",
        "before_final_graph_check",
        "before_atomic_publish",
    ):
        crash_store, crash_service = _service(tmp_path / point, failure_point=point)
        _assert_failure_unchanged(
            crash_store,
            "B04_SIMULATED_TRANSACTION_FAILURE",
            lambda crash_service=crash_service: _propose(
                crash_service, "NO_SOURCE_SLICE"
            ),
        )


def test_f23_write_set_escape_fails_closed(tmp_path: Path) -> None:
    repository_root = ROOT.parents[1]
    with pytest.raises(B04ContractError) as caught:
        FixtureStore(repository_root / "work" / "not-b04")
    assert caught.value.code == "B04_WRITE_SET_ESCAPE"


def test_f24_forbidden_runtime_event_is_counted() -> None:
    from self_check import RuntimeEventLedger

    ledger = RuntimeEventLedger(allowed_write_roots=[ROOT])
    with pytest.raises(B04ContractError) as caught:
        ledger.audit("socket.connect", ("example.invalid", 443))
    assert caught.value.code == "B04_RUNTIME_EVENT_FORBIDDEN"
    assert ledger.summary()["socket_events"] == 1


def test_f25_stale_source_slice_ref_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    stale = fixtures.NEGATIVE_SOURCE_SLICE["fixtures"]["F-25"]["input_ref"]
    _assert_failure_unchanged(
        store,
        "STALE_SOURCE_SLICE_REF",
        lambda: _propose(
            service,
            "B03_R02_SOURCE_SLICE",
            source_slice_refs=[deepcopy(stale)],
        ),
    )


def test_f26_hash_only_source_slice_splice_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    ref = fixtures.NEGATIVE_SOURCE_SLICE["fixtures"]["F-26"]["input_ref"]
    _assert_failure_unchanged(
        store,
        "SOURCE_SLICE_RECORD_REF_MISMATCH",
        lambda: _propose(
            service,
            "B03_R02_SOURCE_SLICE",
            source_slice_refs=[deepcopy(ref)],
        ),
    )


@pytest.mark.parametrize("field", fixtures.F27_FIELDS)
def test_f27_each_source_slice_ref_field_drift_fails_closed(
    tmp_path: Path, field: str
) -> None:
    store, service = _service(tmp_path)
    ref = deepcopy(fixtures.NEGATIVE_SOURCE_SLICE["base_exact_ref"])
    ref[field] = fixtures.NEGATIVE_SOURCE_SLICE["fixtures"]["F-27"]["mutations"][field]
    _assert_failure_unchanged(
        store,
        "SOURCE_SLICE_RECORD_REF_MISMATCH",
        lambda: _propose(
            service,
            "B03_R02_SOURCE_SLICE",
            source_slice_refs=[ref],
        ),
    )


def test_f28_source_slice_revision_drift_fails_closed(tmp_path: Path) -> None:
    store, service = _service(tmp_path)
    revision = deepcopy(fixtures.REVISION)
    revision["revision_no"] = 3
    _assert_failure_unchanged(
        store,
        "SOURCE_SLICE_REVISION_MISMATCH",
        lambda: _propose(
            service,
            "B03_R02_SOURCE_SLICE",
            source_slice_revision=revision,
        ),
    )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"attempt_b03_writer": True}, "B03_WRITER_CALL_FORBIDDEN"),
        (
            {"attempt_source_content_read": True},
            "SOURCE_SLICE_CONTENT_READ_FORBIDDEN",
        ),
    ],
)
def test_f29_projector_cannot_call_b03_or_read_source_content(
    tmp_path: Path, kwargs: dict[str, bool], expected: str
) -> None:
    store, service = _service(tmp_path)
    _propose(service, "B03_R02_SOURCE_SLICE")
    records = _records_by_type(store)
    _assert_failure_unchanged(
        store,
        expected,
        lambda: PatchPreviewProjector.project(
            base=fixtures.BASE,
            protection=records["M3_CANDIDATE_PROTECTION_SET"][0],
            patch=records["M3_PATCH_PROPOSAL"][0],
            causal_records=records["M3_CAUSAL_HINT_PROPOSAL"],
            **kwargs,
        ),
    )


def test_fixture_definition_and_execution_counts() -> None:
    assert len(fixtures.NORMAL_FIXTURE_DEFINITIONS) == 10
    assert len(fixtures.FAILURE_FIXTURE_DEFINITIONS) == 29
    assert len(fixtures.FAILURE_EXECUTION_IDS) == 38
