from __future__ import annotations

import ast
import threading
from copy import deepcopy
from pathlib import Path

import pytest

import b05_store as b05_store_module

from acceptance_spec import FAILURE_FIXTURES, NORMAL_FIXTURES, RUNTIME_COUNTERS
from authoritative_readers import UnavailableReader
from b05_contracts import (
    B05ContractError,
    canonical_bytes,
    guard_runtime_event,
    guard_write_path,
    record_ref,
    sha256_value,
    validate_output_record,
)
from fixtures import CREATED_AT, REOPENED_AT, build_environment, external_record
from patch_route_projection import (
    B06AdmissionGuard,
    B09AdmissionGuard,
    PatchAggregateProjector,
)

ROOT = Path(__file__).resolve().parent


def _rehash(record: dict) -> None:
    prefixes = {
        "M3_CANDIDATE_PROTECTION_SET": "protection-set",
        "M3_PATCH_PROPOSAL": "patch-proposal",
        "M3_CAUSAL_HINT_PROPOSAL": "causal-hint-proposal",
        "M3_VALIDATOR_IDENTITY_RECEIPT": "validator-identity",
        "M3_PATCH_VALIDATION_RECEIPT": "patch-validation",
        "M3_PATCH_ROUTE_RECEIPT": "patch-route",
        "M3_PATCH_LIFECYCLE_RECEIPT": "patch-route-lifecycle",
    }
    if record["record_type"] in prefixes:
        record["record_id"] = (
            f"{prefixes[record['record_type']]}:{sha256_value(record['payload'])}"
        )
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )


def _replace_active_policy(env, mutate_payload) -> None:
    mutate_payload(env.policy_reader.validation_policy["payload"])
    _rehash(env.policy_reader.validation_policy)
    env.policy_reader.active_selection = external_record(
        "M3_ACTIVE_POLICY_SELECTION",
        {
            "selected_validation_policy_ref": record_ref(
                env.policy_reader.validation_policy
            )
        },
    )


def _route_record(env) -> dict:
    return next(
        item
        for item in env.store.read_records()
        if item["record_type"] == "M3_PATCH_ROUTE_RECEIPT"
    )


def _pvr_record(env) -> dict:
    return next(
        item
        for item in env.store.read_records()
        if item["record_type"] == "M3_PATCH_VALIDATION_RECEIPT"
    )


def _forged_initial_route_records(env, mutate) -> tuple[list[dict], dict]:
    records = env.store.read_records()
    original_route = next(
        item for item in records if item["record_type"] == "M3_PATCH_ROUTE_RECEIPT"
    )
    route = deepcopy(original_route)
    mutate(route)
    _rehash(route)
    old_ref = record_ref(original_route)
    new_ref = record_ref(route)
    forged = []
    for record in records:
        if record["record_type"] == "M3_PATCH_ROUTE_RECEIPT":
            forged.append(route)
            continue
        if record["record_type"] != "M3_PATCH_LIFECYCLE_RECEIPT":
            forged.append(record)
            continue
        lifecycle = deepcopy(record)
        for key in (
            "subject_route_receipt_ref",
            "replacement_route_receipt_ref_or_null",
            "prior_route_receipt_ref_or_null",
        ):
            if lifecycle["payload"][key] == old_ref:
                lifecycle["payload"][key] = new_ref
        _rehash(lifecycle)
        forged.append(lifecycle)
    return forged, route


def _forged_pvr_route_records(env, mutate_pvr, synchronize_route):
    records = env.store.read_records()
    original_pvr = next(
        item for item in records if item["record_type"] == "M3_PATCH_VALIDATION_RECEIPT"
    )
    original_route = next(
        item for item in records if item["record_type"] == "M3_PATCH_ROUTE_RECEIPT"
    )
    pvr = deepcopy(original_pvr)
    mutate_pvr(pvr)
    _rehash(pvr)
    route = deepcopy(original_route)
    route["payload"]["validation_receipt_ref"] = record_ref(pvr)
    synchronize_route(route, pvr)
    _rehash(route)
    old_route_ref = record_ref(original_route)
    new_route_ref = record_ref(route)
    forged = []
    for record in records:
        if record["record_type"] == "M3_PATCH_VALIDATION_RECEIPT":
            forged.append(pvr)
            continue
        if record["record_type"] == "M3_PATCH_ROUTE_RECEIPT":
            forged.append(route)
            continue
        if record["record_type"] != "M3_PATCH_LIFECYCLE_RECEIPT":
            forged.append(record)
            continue
        lifecycle = deepcopy(record)
        for key in (
            "subject_route_receipt_ref",
            "replacement_route_receipt_ref_or_null",
            "prior_route_receipt_ref_or_null",
        ):
            if lifecycle["payload"][key] == old_route_ref:
                lifecycle["payload"][key] = new_route_ref
        _rehash(lifecycle)
        forged.append(lifecycle)
    return forged, pvr, route


def test_frozen_fixture_catalog_is_exact_10_22() -> None:
    assert len(NORMAL_FIXTURES) == 10
    assert len(FAILURE_FIXTURES) == 22
    assert not (set(NORMAL_FIXTURES) & set(FAILURE_FIXTURES))
    assert all(value == 0 for value in RUNTIME_COUNTERS.values())


@pytest.mark.parametrize(
    ("fixture_id", "mode", "kwargs", "expected"),
    [
        ("N01_REPLACE_ALLOWED", "replace", {}, ["ALLOW_FOR_B06"]),
        ("N02_ADD_ALLOWED", "add", {}, ["ALLOW_FOR_B06"]),
        (
            "N03_INDEPENDENT_MIXED_ROUTES_WITH_EFFECTIVE_PROTECTION",
            "two-replace",
            {"semantic_unknown_groups": ["replace-b"]},
            ["ALLOW_FOR_B06", "EXPAND_CHECK"],
        ),
        ("N04_DEPENDENT_GROUPS_SINGLE_ROUTE_UNIT", "dependent", {}, ["ALLOW_FOR_B06"]),
        (
            "N05_EXPAND_CHECK_MINIMAL_TARGET",
            "replace",
            {"semantic_unknown_groups": ["replace-a"]},
            ["EXPAND_CHECK"],
        ),
        (
            "N06_DEFER_EXACT_DECLARED_NON_CONTENT_GATE",
            "replace",
            {"closed_gate": True},
            ["DEFER"],
        ),
        (
            "N07_TRUSTED_STALE_OR_UNSAFE_PROPOSAL_REJECTED",
            "replace",
            {"stale_pointer": True},
            ["REJECT"],
        ),
    ],
)
def test_n01_to_n07_routes(
    tmp_path: Path, fixture_id: str, mode: str, kwargs: dict, expected: list[str]
) -> None:
    assert fixture_id in NORMAL_FIXTURES
    env = build_environment(tmp_path / fixture_id, mode=mode, **kwargs)
    result = env.evaluate()
    assert sorted(item["route"] for item in result["route_units"]) == sorted(expected)
    assert result["reused_existing_bundle"] is False
    assert (
        len(
            [
                item
                for item in env.store.read_records()
                if item["record_type"] != "M3_VALIDATOR_IDENTITY_RECEIPT"
            ]
        )
        == 3
    )
    if fixture_id == "N01_REPLACE_ALLOWED":
        pvr = _pvr_record(env)
        route = _route_record(env)
        assert pvr["payload"]["evaluation_key"] == (
            f"b05-evaluation:{pvr['payload']['evaluation_input_hash']}"
        )
        assert route["payload"]["route_series_id"] == (
            f"route-series:{sha256_value({'initial_patch_proposal_ref': record_ref(env.patch)})}"
        )
    if fixture_id == "N03_INDEPENDENT_MIXED_ROUTES_WITH_EFFECTIVE_PROTECTION":
        pvr = _pvr_record(env)
        allow_id = next(
            item["route_unit_id"]
            for item in result["route_units"]
            if item["route"] == "ALLOW_FOR_B06"
        )
        proof = next(
            item
            for item in pvr["payload"]["route_unit_proofs"]
            if item["route_unit_id"] == allow_id
        )
        protected_lineages = {
            item["lineage_locator"]["lineage_id"]
            for item in proof["effective_protection_proof"]
        }
        assert env.records["candidate"]["payload"]["items"][1][
            "lineage_id"
        ] in protected_lineages
        dependency = pvr["payload"]["dependency_proof"]
        assert dependency["dependency_edges"] == []
        assert dependency["unknown_dependency_tokens"] == []
        assert len(dependency["route_unit_partition"]) == 2
        assert proof["exchange_order_checks"]
        assert all(item["byte_identical"] for item in proof["exchange_order_checks"])


def test_n08_causal_route_to_b09(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "n08", mode="causal")
    result = env.evaluate()
    assert [item["route"] for item in result["causal_hint_routes"]] == ["ROUTE_TO_B09"]
    assert all(
        item["record_type"] not in {"M3_CAUSAL_SIDECAR", "M3_CAUSAL_SIDECAR_MANIFEST"}
        for item in env.store.read_records()
    )


def test_add_sort_keeps_protected_base_item_positions(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "add-position", mode="add")
    result = env.evaluate()
    assert result["route_units"][0]["route"] == "ALLOW_FOR_B06"
    applied, errors = b05_store_module._apply_groups(
        env.b01_reader.candidate_version["payload"],
        env.patch["payload"]["atomic_groups"],
        canonical_add_sort=True,
    )
    assert errors == []
    base_lineages = [
        item["lineage_id"]
        for item in env.b01_reader.candidate_version["payload"]["items"]
    ]
    added_lineage = env.patch["payload"]["atomic_groups"][0]["operations"][0][
        "new_item"
    ]["lineage_id"]
    assert [item["lineage_id"] for item in applied["items"]] == [
        *base_lineages,
        added_lineage,
    ]


def test_n09_idempotent_and_content_dedup_replay(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "n09")
    first = env.evaluate("creator-operation")
    snapshot = env.store.visible_snapshot()
    same_operation = env.evaluate(
        "creator-operation", created_at="2026-08-30T08:01:00Z"
    )
    different_operation = env.evaluate(
        "different-operation", created_at="2026-08-30T08:02:00Z"
    )
    assert same_operation["route_receipt_ref"] == first["route_receipt_ref"]
    assert different_operation["route_receipt_ref"] == first["route_receipt_ref"]
    assert same_operation["reused_existing_bundle"] is True
    assert different_operation["reused_existing_bundle"] is True
    assert env.store.visible_snapshot() == snapshot


def test_sqlite_bundle_survives_store_restart(tmp_path: Path) -> None:
    root = tmp_path / "sqlite-restart"
    env = build_environment(root)
    env.evaluate()
    expected = env.store.read_records()
    restarted = b05_store_module.B05RouteStore(root)
    assert restarted.read_records() == expected


def test_n10_atomic_supersede_and_reopen(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "n10", closed_gate=True)
    initial = env.evaluate("initial-operation")
    assert initial["route_units"][0]["route"] == "DEFER"
    projection = PatchAggregateProjector.project(env.store.read_records())
    prior_route = projection["series"][0]["active_route_receipt_ref"]
    prior_head = projection["series"][0]["lifecycle_head_ref"]
    new_gate_state = external_record(
        "M3_NON_CONTENT_GATE_STATE",
        {
            "gate_ref": record_ref(env.records["gate"]),
            "state_sequence": 2,
            "current_state": "OPEN",
        },
        created_at=REOPENED_AT,
    )
    env.policy_reader.gate_bindings[0]["gate_state_ref"] = record_ref(new_gate_state)
    env.policy_reader.gate_bindings[0]["current_state"] = "OPEN"
    env.policy_reader.gate_records = [env.records["gate"], new_gate_state]
    before_invalid = env.store.visible_snapshot()
    with pytest.raises(
        B05ContractError, match="B05_REOPEN_MATERIAL_DELTA_NOT_AUTHORITATIVE"
    ):
        env.evaluate(
            "invalid-pointer-only-reopen",
            created_at=REOPENED_AT,
            prior_active_route_receipt_ref_or_null=prior_route,
            prior_lifecycle_head_ref_or_null=prior_head,
            material_delta_refs=[record_ref(env.records["pointer_snapshot"])],
        )
    assert env.store.visible_snapshot() == before_invalid
    reopened = env.evaluate(
        "reopen-operation",
        created_at=REOPENED_AT,
        prior_active_route_receipt_ref_or_null=prior_route,
        prior_lifecycle_head_ref_or_null=prior_head,
        material_delta_refs=[record_ref(new_gate_state)],
    )
    assert reopened["route_units"][0]["route"] == "ALLOW_FOR_B06"
    after = PatchAggregateProjector.project(env.store.read_records())
    assert after["series"][0]["active_route_generation"] == 2
    lifecycle_events = [
        item["payload"]["event"]
        for item in env.store.read_records()
        if item["record_type"] == "M3_PATCH_LIFECYCLE_RECEIPT"
    ]
    assert sorted(lifecycle_events) == [
        "REOPENED_WITH_NEW_MATERIAL",
        "ROUTES_FROZEN",
        "SUPERSEDED",
    ]
    replay = env.evaluate(
        "reopen-operation",
        created_at="2026-08-30T08:06:00Z",
        prior_active_route_receipt_ref_or_null=prior_route,
        prior_lifecycle_head_ref_or_null=prior_head,
        material_delta_refs=[record_ref(new_gate_state)],
    )
    assert replay["route_receipt_ref"] == reopened["route_receipt_ref"]
    assert replay["reused_existing_bundle"] is True


def test_n10_new_patch_with_exact_prior_link_inherits_series(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "n10-new-patch")
    initial = env.evaluate("initial")
    projection = PatchAggregateProjector.project(env.store.read_records())
    prior_route = projection["series"][0]["active_route_receipt_ref"]
    prior_head = projection["series"][0]["lifecycle_head_ref"]
    new_payload = deepcopy(env.patch["payload"])
    new_payload["atomic_groups"][0]["purpose"] = "fixture-new-material"
    group = new_payload["atomic_groups"][0]
    group["group_payload_hash"] = sha256_value(
        {key: value for key, value in group.items() if key != "group_payload_hash"}
    )
    new_patch = external_record(
        "M3_PATCH_PROPOSAL", new_payload, created_at=REOPENED_AT
    )
    env.patch = new_patch
    reopened = env.evaluate(
        "new-patch-reopen",
        created_at=REOPENED_AT,
        prior_active_route_receipt_ref_or_null=prior_route,
        prior_lifecycle_head_ref_or_null=prior_head,
        material_delta_refs=[record_ref(new_patch)],
    )
    assert initial["route_receipt_ref"] != reopened["route_receipt_ref"]
    current = PatchAggregateProjector.project(env.store.read_records())["series"][0]
    assert current["active_route_generation"] == 2


def test_f01_bad_original_aborts_without_route_output(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f01")
    before = env.store.visible_snapshot()
    env.patch["record_hash"] = "0" * 64
    with pytest.raises(B05ContractError, match="B05_IMMUTABLE_HASH_MISMATCH"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_f01_source_bound_evidence_preserves_original_unicode_bytes() -> None:
    decomposed = "e\u0301"
    encoded = canonical_bytes(
        {
            "evidence": decomposed,
            "fact": decomposed,
            "speaker": decomposed,
            "status": decomposed,
        }
    )
    assert encoded.count(decomposed.encode("utf-8")) == 4
    assert "é".encode("utf-8") not in encoded


def test_f02_pointer_drift_between_reads_aborts(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f02")
    before = env.store.visible_snapshot()

    def drift(read_count: int) -> None:
        if read_count == 2:
            env.b01_reader.live_pointer_binding["generation"] += 1

    env.b01_reader.set_read_hook(drift)
    with pytest.raises(B05ContractError, match="B05_AUTHORITATIVE_SNAPSHOT_DRIFT"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_f03_b02_lifecycle_drift_between_reads_aborts(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f03")
    before = env.store.visible_snapshot()

    def drift(read_count: int) -> None:
        if read_count == 2:
            env.b02_reader.records.append(
                external_record(
                    "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT",
                    {
                        "diagnostic_ref": record_ref(env.records["diagnostic"]),
                        "lifecycle_sequence": 1,
                        "event": "CLOSED",
                        "effective_at": CREATED_AT,
                        "reason_code": "DRIFT",
                        "resolution_ref": None,
                    },
                )
            )

    env.b02_reader.set_read_hook(drift)
    with pytest.raises(B05ContractError, match="B05_AUTHORITATIVE_SNAPSHOT_DRIFT"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candidate_schema_id", "forged-schema"),
        (
            "chapter_revision_ref",
            {
                "chapter_id": "fixture-chapter",
                "revision_no": 2,
                "revision_text_sha256": "2" * 64,
            },
        ),
        ("seg", "seg-forged"),
    ],
)
def test_b02_coverage_scope_fields_cannot_drift(
    tmp_path: Path, field: str, value
) -> None:
    env = build_environment(tmp_path / field, mode="add")
    coverage = next(
        item
        for item in env.b02_reader.records
        if item["record_type"] == "M3_COVERAGE_OBSERVATION"
    )
    coverage["payload"][field] = value
    _rehash(coverage)
    new_ref = record_ref(coverage)
    env.patch["payload"]["coverage_observation_refs"] = [new_ref]
    group = env.patch["payload"]["atomic_groups"][0]
    group["operations"][0]["supporting_coverage_refs"] = [new_ref]
    group["group_payload_hash"] = sha256_value(
        {key: item for key, item in group.items() if key != "group_payload_hash"}
    )
    _rehash(env.patch)
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_B02_COVERAGE_SCOPE_INVALID"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_f04_policy_selection_drift_aborts(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f04")
    before = env.store.visible_snapshot()

    def drift(read_count: int) -> None:
        if read_count == 2:
            env.policy_reader.validation_policy["payload"]["drift"] = True
            _rehash(env.policy_reader.validation_policy)

    env.policy_reader.set_read_hook(drift)
    with pytest.raises(B05ContractError, match="B05_AUTHORITATIVE_SNAPSHOT_DRIFT"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_f05_same_operation_different_input_aborts(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f05")
    env.evaluate("same-operation")
    before = env.store.visible_snapshot()
    env.policy_reader.validation_policy["payload"]["semantic_unknown_group_ids"] = [
        "replace-a"
    ]
    _rehash(env.policy_reader.validation_policy)
    env.policy_reader.active_selection = external_record(
        "M3_ACTIVE_POLICY_SELECTION",
        {
            "selected_validation_policy_ref": record_ref(
                env.policy_reader.validation_policy
            )
        },
    )
    with pytest.raises(B05ContractError, match="B05_OPERATION_ID_INPUT_CONFLICT"):
        env.evaluate("same-operation")
    assert env.store.visible_snapshot() == before


def test_f05_operation_id_is_scoped_by_project(tmp_path: Path) -> None:
    shared_root = tmp_path / "f05-scoped"
    first = build_environment(shared_root)
    first.evaluate("same-operation")
    second = build_environment(shared_root)
    second.b01_reader.live_pointer_binding["project_scope_id"] = "fixture-project-2"
    second.b01_reader.live_pointer_binding["logical_pointer_key"] = "fixture-pointer-2"
    second.patch["payload"]["atomic_groups"][0]["purpose"] = "second-project"
    group = second.patch["payload"]["atomic_groups"][0]
    group["group_payload_hash"] = sha256_value(
        {key: value for key, value in group.items() if key != "group_payload_hash"}
    )
    _rehash(second.patch)
    result = second.evaluate("same-operation")
    assert result["reused_existing_bundle"] is False


def test_f05_same_input_different_derived_proof_is_nondeterminism(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = build_environment(tmp_path / "f05-nondeterminism", mode="two-replace")
    first = env.evaluate("creator")
    original = b05_store_module._known_edges

    def changed_edges(groups, policy_payload):
        edges = original(groups, policy_payload)
        return [
            *edges,
            {
                "left_atomic_group_id": "replace-a",
                "right_atomic_group_id": "replace-b",
                "edge_type": "OPERATION_RESULT_DEPENDENCY",
                "evidence_tokens": [
                    {
                        "type": "STABLE_CHECK_CODE",
                        "value": "B05_CHECK_FORCED_NONDETERMINISM",
                    }
                ],
            },
        ]

    monkeypatch.setattr(b05_store_module, "_known_edges", changed_edges)
    with pytest.raises(B05ContractError, match="B05_NONDETERMINISTIC_RESULT"):
        env.evaluate("second-operation")
    assert env.store.route_bundle_for_input(first["evaluation_input_hash"]) is not None


def test_f06_concurrent_identical_bundle_has_one_active_route(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f06")
    barrier = threading.Barrier(2)

    def synchronize_first_reads(read_count: int) -> None:
        if read_count <= 2:
            barrier.wait(timeout=5)

    env.b01_reader.set_read_hook(synchronize_first_reads)
    results = []
    errors = []

    def run(operation: str) -> None:
        try:
            results.append(env.evaluate(operation))
        except Exception as error:  # pragma: no cover - asserted below
            errors.append(error)

    threads = [
        threading.Thread(target=run, args=(f"op-{index}",)) for index in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not errors
    assert len(results) == 2
    assert len({canonical_bytes(item["route_receipt_ref"]) for item in results}) == 1
    projection = PatchAggregateProjector.project(env.store.read_records())
    assert len(projection["series"]) == 1


def test_f06_concurrent_conflicting_bundles_only_one_commits(tmp_path: Path) -> None:
    shared_root = tmp_path / "f06-conflict"
    allow_env = build_environment(shared_root)
    expand_env = build_environment(shared_root, semantic_unknown_groups=["replace-a"])
    barrier = threading.Barrier(2)

    def wait_first(read_count: int) -> None:
        if read_count == 1:
            barrier.wait(timeout=5)

    allow_env.b01_reader.set_read_hook(wait_first)
    expand_env.b01_reader.set_read_hook(wait_first)
    results = []
    errors = []

    def run(env, operation: str) -> None:
        try:
            results.append(env.evaluate(operation))
        except Exception as error:  # pragma: no cover - asserted below
            errors.append(error)

    threads = [
        threading.Thread(target=run, args=(allow_env, "allow-operation")),
        threading.Thread(target=run, args=(expand_env, "expand-operation")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], B05ContractError)
    assert errors[0].code == "B05_PRIOR_ROUTE_STATE_DRIFT"
    projection = PatchAggregateProjector.project(allow_env.store.read_records())
    assert len(projection["series"]) == 1


def test_f07_reader_unavailable_aborts_without_output(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f07")
    before = env.store.visible_snapshot()
    env.service.b02_reader = UnavailableReader()  # type: ignore[assignment]
    with pytest.raises(B05ContractError, match="B05_AUTHORITATIVE_READER_UNAVAILABLE"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_f07_validator_identity_must_match_exact_reader_version(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f07-identity")
    before = env.store.visible_snapshot()
    env.b01_reader.reader_version = "drifted-reader-version"
    with pytest.raises(B05ContractError, match="B05_VALIDATOR_READER_IDENTITY_DRIFT"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_f07_b02_terminal_time_order_fails_closed(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f07-time")
    diagnostic_ref = record_ref(env.records["diagnostic"])
    env.b02_reader.records.extend(
        [
            external_record(
                "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT",
                {
                    "diagnostic_ref": diagnostic_ref,
                    "lifecycle_sequence": 1,
                    "event": "CLOSED",
                    "effective_at": "2026-08-30T08:02:00Z",
                    "reason_code": "CLOSED",
                    "resolution_ref": None,
                },
            ),
            external_record(
                "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT",
                {
                    "diagnostic_ref": diagnostic_ref,
                    "lifecycle_sequence": 2,
                    "event": "OBSERVED",
                    "effective_at": "2026-08-30T08:03:00Z",
                    "reason_code": "AFTER_TERMINAL",
                    "resolution_ref": None,
                },
            ),
        ]
    )
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_B02_LIFECYCLE_INVALID"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_f08_partial_allow_cannot_drop_other_unit_protection(tmp_path: Path) -> None:
    env = build_environment(
        tmp_path / "f08",
        mode="two-replace",
        semantic_unknown_groups=["replace-b"],
    )
    env.evaluate()
    pvr = _pvr_record(env)
    route = _route_record(env)
    allow = next(
        item
        for item in route["payload"]["route_units"]
        if item["route"] == "ALLOW_FOR_B06"
    )
    proof = next(
        item
        for item in pvr["payload"]["route_unit_proofs"]
        if item["route_unit_id"] == allow["route_unit_id"]
    )
    assert env.records["candidate"]["payload"]["items"][1]["lineage_id"] in {
        item["lineage_locator"]["lineage_id"]
        for item in proof["effective_protection_proof"]
    }


def test_b04_protection_set_must_equal_exact_base_complement(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "protection-forgery")
    entry = deepcopy(env.protection["payload"]["protected_entries"][0])
    locator = entry["lineage_locator"]
    locator["lineage_id"] = "lin-ghost"
    locator["json_pointer"] = "/items/99"
    locator["item_hash"] = "3" * 64
    locator["locator_hash"] = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    entry["json_pointer"] = "/items/99"
    entry["protected_item_hash"] = "3" * 64
    env.protection["payload"]["protected_entries"] = [entry]
    _rehash(env.protection)
    env.patch["payload"]["protection_set_ref"] = record_ref(env.protection)
    _rehash(env.patch)
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_B04_CLOSURE_INVALID"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_f09_dependent_groups_have_no_partial_route(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f09", mode="dependent")
    result = env.evaluate()
    assert len(result["route_units"]) == 1
    assert len(result["route_units"][0]["atomic_group_bindings"]) == 2


def test_f10_unknown_dependency_expands_not_allows(tmp_path: Path) -> None:
    env = build_environment(
        tmp_path / "f10",
        mode="mixed",
        unknown_tokens=[
            {
                "reason_code": "DEPENDENCY_ENDPOINT_UNKNOWN",
                "bounded_atomic_group_ids": [],
                "supporting_refs": [],
            }
        ],
    )
    result = env.evaluate()
    assert [item["route"] for item in result["route_units"]] == ["EXPAND_CHECK"]


def test_f11_duplicate_group_aborts_before_publish(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f11")
    before = env.store.visible_snapshot()
    env.patch["payload"]["atomic_groups"].append(
        deepcopy(env.patch["payload"]["atomic_groups"][0])
    )
    _rehash(env.patch)
    with pytest.raises(B05ContractError, match="B05_B04_CLOSURE_INVALID"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_f12_order_sensitive_add_units_merge_without_frozen_sort(
    tmp_path: Path,
) -> None:
    env = build_environment(
        tmp_path / "f12", mode="order-add", canonical_add_sort_frozen=False
    )
    result = env.evaluate()
    assert len(result["route_units"]) == 1
    assert len(result["route_units"][0]["atomic_group_bindings"]) == 2


def test_f13_object_responsibilities_are_not_duplicated(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f13")
    env.evaluate()
    pvr = _pvr_record(env)
    route = _route_record(env)
    lifecycle = next(
        item
        for item in env.store.read_records()
        if item["record_type"] == "M3_PATCH_LIFECYCLE_RECEIPT"
    )
    assert "route" not in pvr["payload"]
    assert "route_units" not in lifecycle["payload"]
    assert "logical_read_set" not in route["payload"]["route_units"][0]


@pytest.mark.parametrize(
    "failure_point",
    [
        "after_stage_1",
        "after_stage_2",
        "after_stage_3",
        "before_atomic_publish",
        "after_sqlite_insert",
    ],
)
def test_f14_atomic_bundle_failure_has_no_partial_visibility(
    tmp_path: Path, failure_point: str
) -> None:
    env = build_environment(tmp_path / failure_point)
    before = env.store.visible_snapshot()
    env.store.failure_point = failure_point
    with pytest.raises(B05ContractError, match="B05_SIMULATED_TRANSACTION_FAILURE"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_f14_pvr_cannot_be_published_without_route_and_lifecycle(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "f14-members")
    env.evaluate()
    pvr = _pvr_record(env)
    before = env.store.visible_snapshot()
    with env.store.serialization():
        with pytest.raises(
            B05ContractError, match="B05_ROUTE_BUNDLE_MEMBER_SET_INVALID"
        ):
            env.store._publish_locked([pvr], publisher_token=object())
    assert env.store.visible_snapshot() == before


def test_f14_direct_store_call_cannot_bypass_unique_publisher(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f14-scope")
    env.evaluate()
    bundle = [
        item
        for item in env.store.read_records()
        if item["record_type"] != "M3_VALIDATOR_IDENTITY_RECEIPT"
    ]
    before = env.store.visible_snapshot()
    with env.store.serialization():
        with pytest.raises(B05ContractError, match="B05_PUBLISHER_SCOPE_ESCAPE"):
            env.store._publish_locked(bundle, publisher_token=object())
    assert env.store.visible_snapshot() == before


def test_f15_no_visible_stage_and_runtime_write_guards(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f15")
    before = env.store.visible_snapshot()
    writes_before = env.store.write_attempt_count()
    env.store.failure_point = "before_atomic_publish"
    with pytest.raises(B05ContractError):
        env.evaluate()
    assert env.store.visible_snapshot() == before
    assert not list(tmp_path.rglob(".b05-private-stage-*"))
    assert env.store.write_attempt_count() == writes_before
    env.store.assert_no_write_attempts_since(writes_before)
    env.store.physical_write_attempts.append(
        {"event": "forbidden_write_then_delete_probe"}
    )
    with pytest.raises(B05ContractError, match="B05_ZERO_WRITE_PROOF_FAILED"):
        env.store.assert_no_write_attempts_since(writes_before)
    guard_write_path("work/ccz57_m3_b05_patch_route_r03_5/fixture.json")
    with pytest.raises(B05ContractError, match="B05_WRITE_SET_ESCAPE"):
        guard_write_path("work/ccz57_m3_b06/fixture.json")


def test_f16_no_model_network_text_or_b03_runtime_path() -> None:
    forbidden_modules = {"requests", "httpx", "openai", "anthropic", "subprocess"}
    for name in (
        "b05_contracts.py",
        "b05_store.py",
        "authoritative_readers.py",
        "patch_route_projection.py",
    ):
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert not (imports & forbidden_modules)
        assert "ccz57_m3_b03" not in (ROOT / name).read_text(encoding="utf-8")
    for event in (
        "model_api",
        "network",
        "real_novel_read",
        "text_slice_read",
        "new_fact_generation",
        "patch_mutation",
        "candidate_version_write",
        "pointer_write",
        "b09_sidecar_write",
    ):
        with pytest.raises(B05ContractError, match="B05_FORBIDDEN_RUNTIME_EVENT"):
            guard_runtime_event(event)


def test_f17_expand_target_contains_no_text_prompt_or_new_fact(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f17", semantic_unknown_groups=["replace-a"])
    result = env.evaluate()
    target = result["route_units"][0]["expand_check_target_or_null"]
    assert set(target) == {
        "return_module",
        "patch_proposal_ref",
        "route_unit_id",
        "atomic_group_bindings",
        "chapter_revision_ref",
        "segment_index_ref",
        "seg_targets",
        "diagnostic_refs",
        "coverage_observation_refs",
        "authorized_source_slice_refs",
        "causal_hint_proposal_refs",
        "question_codes",
    }
    assert not ({"prompt", "novel_text", "new_fact", "new_item"} & set(target))


def test_f18_non_exact_causal_support_aborts(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f18", mode="two-replace")
    opaque_source_ref = record_ref(
        external_record("M3_AUTHORIZED_SOURCE_SLICE", {"opaque_fixture": True})
    )
    causal = external_record(
        "M3_CAUSAL_HINT_PROPOSAL",
        {
            "from_lineage_locator": {"lineage_id": "lin-a"},
            "to_lineage_locator": {"lineage_id": "lin-b"},
            "evidence_locators": [],
            "coverage_observation_refs": [],
            "authorized_source_slice_refs": [opaque_source_ref],
            "diagnostic_refs": [],
            "hint_kind": "DIRECT_POSSIBLE_CAUSE",
            "expiry_request_seconds": 3600,
            "noncommittable": True,
            "chapter_revision_ref": deepcopy(
                env.patch["payload"]["chapter_revision_ref"]
            ),
        },
    )
    env.causals = [causal]
    env.patch["payload"]["authorized_source_slice_refs"] = [opaque_source_ref]
    env.patch["payload"]["sidecar_proposal_refs"] = [record_ref(causal)]
    _rehash(env.patch)
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_B04_CLOSURE_INVALID"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_causal_locator_must_resolve_exact_base_before_b09(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "causal-locator", mode="causal")
    locator = env.causals[0]["payload"]["from_lineage_locator"]
    locator["lineage_id"] = "lin-ghost"
    locator["json_pointer"] = "/items/99"
    locator["item_hash"] = "4" * 64
    locator["locator_hash"] = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    _rehash(env.causals[0])
    env.patch["payload"]["sidecar_proposal_refs"] = [record_ref(env.causals[0])]
    _rehash(env.patch)
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_B04_CLOSURE_INVALID"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_f19_b09_denied_route_writes_nothing(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f19", mode="causal", stale_pointer=True)
    result = env.evaluate()
    route = _route_record(env)
    before = env.store.visible_snapshot()
    causal_entry = result["causal_hint_routes"][0]
    with pytest.raises(B05ContractError, match="B05_B09_ROUTE_DENIED"):
        B09AdmissionGuard.require_route(
            env.store.read_records(),
            route_receipt_ref=record_ref(route),
            causal_hint_proposal_ref=causal_entry["causal_hint_proposal_ref"],
            mapping_proof_hash=causal_entry["mapping_proof_hash"],
            live_pointer_binding_hash=route["payload"]["binding_header"][
                "live_pointer_binding_hash"
            ],
            b02_scope_snapshot_hash=route["payload"]["binding_header"][
                "b02_scope_snapshot_hash"
            ],
            active_policy_selection_hash=route["payload"][
                "active_policy_selection_hash"
            ],
            non_content_gate_snapshot_hash=route["payload"]["binding_header"][
                "non_content_gate_snapshot_hash"
            ],
        )
    assert env.store.visible_snapshot() == before


def test_f20_b06_stale_route_writes_nothing(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f20")
    result = env.evaluate()
    route = _route_record(env)
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_DOWNSTREAM_POINTER_STALE"):
        B06AdmissionGuard.require_allow(
            env.store.read_records(),
            route_receipt_ref=record_ref(route),
            route_unit_id=result["route_units"][0]["route_unit_id"],
            base_candidate_version_record=env.b01_reader.candidate_version,
            live_pointer_binding_hash="0" * 64,
            b02_scope_snapshot_hash=route["payload"]["binding_header"][
                "b02_scope_snapshot_hash"
            ],
            active_policy_selection_hash=route["payload"][
                "active_policy_selection_hash"
            ],
            non_content_gate_snapshot_hash=route["payload"]["binding_header"][
                "non_content_gate_snapshot_hash"
            ],
        )
    assert env.store.visible_snapshot() == before


def test_b06_rechecks_exact_pvr_unit_proof(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "b06-proof")
    env.evaluate()

    def mutate(route: dict) -> None:
        route["payload"]["route_units"][0]["unit_proof_hash"] = "5" * 64

    records, route = _forged_initial_route_records(env, mutate)
    binding = route["payload"]["binding_header"]
    with pytest.raises(B05ContractError, match="B05_B06_UNIT_PROOF_MISMATCH"):
        B06AdmissionGuard.require_allow(
            records,
            route_receipt_ref=record_ref(route),
            route_unit_id=route["payload"]["route_units"][0]["route_unit_id"],
            base_candidate_version_record=env.b01_reader.candidate_version,
            live_pointer_binding_hash=binding["live_pointer_binding_hash"],
            b02_scope_snapshot_hash=binding["b02_scope_snapshot_hash"],
            active_policy_selection_hash=route["payload"][
                "active_policy_selection_hash"
            ],
            non_content_gate_snapshot_hash=binding["non_content_gate_snapshot_hash"],
        )


def test_b06_recomputes_effective_protection_from_exact_base(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "b06-effective-protection")
    env.evaluate()

    def mutate_pvr(pvr: dict) -> None:
        proof = pvr["payload"]["route_unit_proofs"][0]
        proof["effective_protection_proof"] = []
        proof["unit_proof_hash"] = sha256_value(
            {key: value for key, value in proof.items() if key != "unit_proof_hash"}
        )

    def synchronize_route(route: dict, pvr: dict) -> None:
        route["payload"]["route_units"][0]["unit_proof_hash"] = pvr["payload"][
            "route_unit_proofs"
        ][0]["unit_proof_hash"]

    records, _, route = _forged_pvr_route_records(env, mutate_pvr, synchronize_route)
    binding = route["payload"]["binding_header"]
    with pytest.raises(B05ContractError, match="B05_B06_EFFECTIVE_PROTECTION_INVALID"):
        B06AdmissionGuard.require_allow(
            records,
            route_receipt_ref=record_ref(route),
            route_unit_id=route["payload"]["route_units"][0]["route_unit_id"],
            base_candidate_version_record=env.b01_reader.candidate_version,
            live_pointer_binding_hash=binding["live_pointer_binding_hash"],
            b02_scope_snapshot_hash=binding["b02_scope_snapshot_hash"],
            active_policy_selection_hash=route["payload"][
                "active_policy_selection_hash"
            ],
            non_content_gate_snapshot_hash=binding["non_content_gate_snapshot_hash"],
        )


def test_b09_rechecks_exact_pvr_mapping_proof(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "b09-proof", mode="causal")
    env.evaluate()

    def mutate(route: dict) -> None:
        route["payload"]["causal_hint_routes"][0]["mapping_proof_hash"] = "6" * 64

    records, route = _forged_initial_route_records(env, mutate)
    binding = route["payload"]["binding_header"]
    causal = route["payload"]["causal_hint_routes"][0]
    with pytest.raises(B05ContractError, match="B05_B09_MAPPING_PROOF_MISMATCH"):
        B09AdmissionGuard.require_route(
            records,
            route_receipt_ref=record_ref(route),
            causal_hint_proposal_ref=causal["causal_hint_proposal_ref"],
            mapping_proof_hash=causal["mapping_proof_hash"],
            live_pointer_binding_hash=binding["live_pointer_binding_hash"],
            b02_scope_snapshot_hash=binding["b02_scope_snapshot_hash"],
            active_policy_selection_hash=route["payload"][
                "active_policy_selection_hash"
            ],
            non_content_gate_snapshot_hash=binding["non_content_gate_snapshot_hash"],
        )


def test_b09_rechecks_supporting_units_against_allow_routes(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "b09-support-units", mode="causal")
    env.evaluate()

    def mutate_pvr(pvr: dict) -> None:
        mapping = pvr["payload"]["causal_support_mappings"][0]
        mapping["supporting_route_unit_ids"] = ["route-unit:ghost"]
        mapping["mapping_proof_hash"] = sha256_value(
            {
                key: value
                for key, value in mapping.items()
                if key != "mapping_proof_hash"
            }
        )

    def synchronize_route(route: dict, pvr: dict) -> None:
        mapping = pvr["payload"]["causal_support_mappings"][0]
        entry = route["payload"]["causal_hint_routes"][0]
        entry["mapping_proof_hash"] = mapping["mapping_proof_hash"]
        entry["supporting_route_unit_ids"] = mapping["supporting_route_unit_ids"]

    records, _, route = _forged_pvr_route_records(env, mutate_pvr, synchronize_route)
    binding = route["payload"]["binding_header"]
    causal = route["payload"]["causal_hint_routes"][0]
    with pytest.raises(B05ContractError, match="B05_B09_SUPPORTING_ROUTE_MISMATCH"):
        B09AdmissionGuard.require_route(
            records,
            route_receipt_ref=record_ref(route),
            causal_hint_proposal_ref=causal["causal_hint_proposal_ref"],
            mapping_proof_hash=causal["mapping_proof_hash"],
            live_pointer_binding_hash=binding["live_pointer_binding_hash"],
            b02_scope_snapshot_hash=binding["b02_scope_snapshot_hash"],
            active_policy_selection_hash=route["payload"][
                "active_policy_selection_hash"
            ],
            non_content_gate_snapshot_hash=binding["non_content_gate_snapshot_hash"],
        )


def test_f21_invalid_defer_cases_do_not_become_defer(tmp_path: Path) -> None:
    outage = build_environment(tmp_path / "f21-outage")
    before = outage.store.visible_snapshot()
    outage.service.b01_reader = UnavailableReader()  # type: ignore[assignment]
    with pytest.raises(B05ContractError):
        outage.evaluate()
    assert outage.store.visible_snapshot() == before
    no_declared_human_gate = build_environment(tmp_path / "f21-no-gate")
    assert (
        no_declared_human_gate.evaluate()["route_units"][0]["route"] == "ALLOW_FOR_B06"
    )
    semantic = build_environment(
        tmp_path / "f21-semantic", semantic_unknown_groups=["replace-a"]
    )
    assert semantic.evaluate()["route_units"][0]["route"] == "EXPAND_CHECK"


def test_f22_projection_fails_closed_on_two_active_routes(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f22")
    env.evaluate()
    records = env.store.read_records()
    route = deepcopy(_route_record(env))
    route["record_id"] = f"{route['record_id']}-forged-active"
    route["payload"]["route_generation"] = 2
    _rehash(route)
    validate_output_record(route)
    with pytest.raises(B05ContractError, match="B05_PROJECTION_ACTIVE_ROUTE_AMBIGUOUS"):
        PatchAggregateProjector.project([*records, route])


def test_f22_projection_rejects_swapped_reopen_sequence(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "f22-sequence", closed_gate=True)
    env.evaluate("initial")
    projection = PatchAggregateProjector.project(env.store.read_records())
    prior_route = projection["series"][0]["active_route_receipt_ref"]
    prior_head = projection["series"][0]["lifecycle_head_ref"]
    gate_state = external_record(
        "M3_NON_CONTENT_GATE_STATE",
        {
            "gate_ref": record_ref(env.records["gate"]),
            "state_sequence": 2,
            "current_state": "OPEN",
        },
        created_at=REOPENED_AT,
    )
    env.policy_reader.gate_bindings[0]["gate_state_ref"] = record_ref(gate_state)
    env.policy_reader.gate_bindings[0]["current_state"] = "OPEN"
    env.policy_reader.gate_records = [env.records["gate"], gate_state]
    env.evaluate(
        "reopen",
        created_at=REOPENED_AT,
        prior_active_route_receipt_ref_or_null=prior_route,
        prior_lifecycle_head_ref_or_null=prior_head,
        material_delta_refs=[record_ref(gate_state)],
    )
    mutated = deepcopy(env.store.read_records())
    pair = [
        item
        for item in mutated
        if item["record_type"] == "M3_PATCH_LIFECYCLE_RECEIPT"
        and item["payload"]["event"] in {"SUPERSEDED", "REOPENED_WITH_NEW_MATERIAL"}
    ]
    assert len(pair) == 2
    (
        pair[0]["payload"]["lifecycle_sequence"],
        pair[1]["payload"]["lifecycle_sequence"],
    ) = (
        pair[1]["payload"]["lifecycle_sequence"],
        pair[0]["payload"]["lifecycle_sequence"],
    )
    for item in pair:
        _rehash(item)
        validate_output_record(item)
    with pytest.raises(B05ContractError, match="B05_PROJECTION_REOPEN_CHAIN_INVALID"):
        PatchAggregateProjector.project(mutated)


def test_modify_m01_exact_b01_child_is_accepted(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "m01-child", candidate_child=True)
    assert env.records["candidate"]["record_version"] == 2
    result = env.evaluate()
    assert [item["route"] for item in result["route_units"]] == ["ALLOW_FOR_B06"]


def test_modify_m02_trial_rebuilds_full_candidate_payload(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "m02-trial")
    payload, local_errors = b05_store_module._apply_groups(
        env.records["candidate"]["payload"],
        env.patch["payload"]["atomic_groups"],
        canonical_add_sort=True,
    )
    trial, exact_errors = b05_store_module._build_and_validate_trial_candidate(
        env.records["candidate"],
        payload,
        reference_records=env.b01_reader.read_scope()["candidate_reference_records"],
    )
    assert local_errors == []
    assert exact_errors == []
    assert trial["record_version"] == 2
    assert trial["payload"]["parent_candidate_version_ref"] == record_ref(
        env.records["candidate"]
    )
    assert trial["payload"]["lineage_index"] == [
        {
            "lineage_id": item["lineage_id"],
            "json_pointer": f"/items/{index}",
            "item_hash": item["item_hash"],
        }
        for index, item in enumerate(trial["payload"]["items"])
    ]


def test_modify_m03_unknown_b02_lifecycle_event_aborts(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "m03-lifecycle")
    env.b02_reader.records.append(
        external_record(
            "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT",
            {
                "diagnostic_ref": record_ref(env.records["diagnostic"]),
                "lifecycle_sequence": 1,
                "event": "OBSERVED",
                "effective_at": CREATED_AT,
                "reason_code": "UNKNOWN_EVENT",
                "resolution_ref": None,
            },
        )
    )
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_B02_LIFECYCLE_INVALID"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_modify_m04_undeclared_gate_cannot_defer(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "m04-gate")
    gate = env.records["gate"]
    state = external_record(
        "M3_NON_CONTENT_GATE_STATE",
        {
            "gate_ref": record_ref(gate),
            "state_sequence": 1,
            "current_state": "CLOSED",
        },
    )
    env.policy_reader.gate_records = [gate, state]
    env.policy_reader.gate_bindings = [
        {
            "gate_ref": record_ref(gate),
            "gate_state_ref": record_ref(state),
            "current_state": "CLOSED",
            "applicable_patch_proposal_ref": record_ref(env.patch),
            "applicable_atomic_group_bindings_or_route_unit_ids": [
                {
                    "atomic_group_id": env.patch["payload"]["atomic_groups"][0][
                        "atomic_group_id"
                    ],
                    "group_payload_hash": env.patch["payload"]["atomic_groups"][0][
                        "group_payload_hash"
                    ],
                }
            ],
            "reader_identity": env.policy_reader.reader_identity,
            "reader_version": env.policy_reader.reader_version,
        }
    ]
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_GATE_NOT_DECLARED"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_modify_m04_declared_gate_requires_exact_binding_closure(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "m04-declared-unbound", closed_gate=True)
    env.policy_reader.gate_bindings = []
    before = env.store.visible_snapshot()
    with pytest.raises(
        B05ContractError, match="B05_GATE_DECLARATION_CLOSURE_INVALID"
    ):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_modify_m04_gate_binding_must_use_current_state(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "m04-current-state", closed_gate=True)
    current_state = external_record(
        "M3_NON_CONTENT_GATE_STATE",
        {
            "gate_ref": record_ref(env.records["gate"]),
            "state_sequence": 2,
            "current_state": "OPEN",
        },
        created_at=REOPENED_AT,
    )
    env.policy_reader.gate_records.append(current_state)
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_GATE_STATE_NOT_CURRENT"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_modify_m04_gate_state_head_must_be_unambiguous(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "m04-state-ambiguous", closed_gate=True)
    conflicting_state = external_record(
        "M3_NON_CONTENT_GATE_STATE",
        {
            "gate_ref": record_ref(env.records["gate"]),
            "state_sequence": 1,
            "current_state": "OPEN",
        },
        created_at=REOPENED_AT,
    )
    env.policy_reader.gate_records.append(conflicting_state)
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_GATE_STATE_AMBIGUOUS"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_modify_m04_gate_group_binding_requires_exact_hash(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "m04-group-hash", closed_gate=True)
    target = env.policy_reader.gate_bindings[0][
        "applicable_atomic_group_bindings_or_route_unit_ids"
    ][0]
    target["group_payload_hash"] = "0" * 64
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_GATE_APPLICABILITY_INVALID"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_modify_m04_gate_route_unit_target_must_exist(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "m04-route-unit", closed_gate=True)
    env.policy_reader.gate_bindings[0][
        "applicable_atomic_group_bindings_or_route_unit_ids"
    ] = ["route-unit:not-present"]
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_GATE_APPLICABILITY_INVALID"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_modify_m04_gate_bindings_must_cover_each_declared_gate_once(
    tmp_path: Path,
) -> None:
    env = build_environment(
        tmp_path / "m04-binding-bijection", mode="two-replace", closed_gate=True
    )
    second_gate = external_record(
        "M3_NON_CONTENT_GATE",
        {"gate_kind": "SECOND_CONTROL", "gate_scope": "PATCH_ROUTE_UNIT"},
    )
    second_state = external_record(
        "M3_NON_CONTENT_GATE_STATE",
        {
            "gate_ref": record_ref(second_gate),
            "state_sequence": 1,
            "current_state": "CLOSED",
        },
    )
    declarations = env.policy_reader.validation_policy["payload"][
        "declared_non_content_gates"
    ]
    declarations.append(
        {"gate_ref": record_ref(second_gate), "gate_kind": "SECOND_CONTROL"}
    )
    env.policy_reader.validation_policy["payload"]["declared_non_content_gates"] = (
        sorted(declarations, key=canonical_bytes)
    )
    _rehash(env.policy_reader.validation_policy)
    env.policy_reader.active_selection = external_record(
        "M3_ACTIVE_POLICY_SELECTION",
        {
            "selected_validation_policy_ref": record_ref(
                env.policy_reader.validation_policy
            )
        },
    )
    duplicate_binding = deepcopy(env.policy_reader.gate_bindings[0])
    second_group = env.patch["payload"]["atomic_groups"][1]
    duplicate_binding["applicable_atomic_group_bindings_or_route_unit_ids"] = [
        {
            "atomic_group_id": second_group["atomic_group_id"],
            "group_payload_hash": second_group["group_payload_hash"],
        }
    ]
    env.policy_reader.gate_bindings.append(duplicate_binding)
    env.policy_reader.gate_records.extend([second_gate, second_state])
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_GATE_BINDING_DUPLICATE"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_modify_m05_forged_b04_target_ref_aborts(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "m05-target")
    target = env.patch["payload"]["atomic_groups"][0]["operations"][0]["target"]
    forged_ref = deepcopy(target["candidate_version_ref"])
    forged_ref["record_id"] = f"{forged_ref['record_id']}:forged"
    forged_ref["record_hash"] = sha256_value(forged_ref)
    target["candidate_version_ref"] = forged_ref
    target["locator_hash"] = sha256_value(
        {key: value for key, value in target.items() if key != "locator_hash"}
    )
    group = env.patch["payload"]["atomic_groups"][0]
    group["group_payload_hash"] = sha256_value(
        {key: value for key, value in group.items() if key != "group_payload_hash"}
    )
    _rehash(env.patch)
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_B04_CLOSURE_INVALID"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_modify_m05_opaque_source_patch_still_requires_exact_schema(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "m05-source-schema", mode="causal")
    opaque_source_ref = record_ref(
        external_record("M3_AUTHORIZED_SOURCE_SLICE", {"opaque_fixture": True})
    )
    env.patch["payload"]["authorized_source_slice_refs"] = [opaque_source_ref]
    env.causals[0]["payload"]["authorized_source_slice_refs"] = [opaque_source_ref]
    _rehash(env.causals[0])
    env.patch["payload"]["sidecar_proposal_refs"] = [record_ref(env.causals[0])]
    env.patch["payload"]["candidate_schema_id"] = "WRONG-SCHEMA"
    _rehash(env.patch)
    before = env.store.visible_snapshot()
    with pytest.raises(
        B05ContractError,
        match="B05_B04_CLOSURE_INVALID.*B04_CANDIDATE_SCHEMA_MISMATCH",
    ):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_modify_m06_source_slice_relation_never_routes_b09(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "m06-source", mode="two-replace")
    opaque_source_ref = record_ref(
        external_record("M3_AUTHORIZED_SOURCE_SLICE", {"opaque_fixture": True})
    )
    env.patch["payload"]["authorized_source_slice_refs"] = [opaque_source_ref]
    _rehash(env.patch)
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_B04_SOURCE_SLICE_SCOPE_INVALID"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_modify_m06_patch_and_causal_source_refs_must_be_byte_equal(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "m06-source-byte-equality", mode="causal")
    opaque_source_ref = record_ref(
        external_record("M3_AUTHORIZED_SOURCE_SLICE", {"opaque_fixture": True})
    )
    env.patch["payload"]["authorized_source_slice_refs"] = [opaque_source_ref]
    _rehash(env.patch)
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_B04_CAUSAL_SOURCE_SCOPE_INVALID"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_modify_m06_exact_source_slice_relation_can_route_b09(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "m06-source-exact", mode="causal")
    opaque_source_ref = record_ref(
        external_record("M3_AUTHORIZED_SOURCE_SLICE", {"opaque_fixture": True})
    )
    env.patch["payload"]["authorized_source_slice_refs"] = [opaque_source_ref]
    env.causals[0]["payload"]["authorized_source_slice_refs"] = [opaque_source_ref]
    _rehash(env.causals[0])
    env.patch["payload"]["sidecar_proposal_refs"] = [record_ref(env.causals[0])]
    _rehash(env.patch)
    result = env.evaluate()
    assert [item["route"] for item in result["causal_hint_routes"]] == [
        "ROUTE_TO_B09"
    ]


def test_r03_gate_applicability_accepts_one_canonical_target_set(
    tmp_path: Path,
) -> None:
    env = build_environment(
        tmp_path / "r03-gate-canonical", mode="two-replace", closed_gate=True
    )
    bindings = sorted(
        [
            {
                "atomic_group_id": group["atomic_group_id"],
                "group_payload_hash": group["group_payload_hash"],
            }
            for group in env.patch["payload"]["atomic_groups"]
        ],
        key=canonical_bytes,
    )
    env.policy_reader.gate_bindings[0][
        "applicable_atomic_group_bindings_or_route_unit_ids"
    ] = bindings
    result = env.evaluate()
    assert [item["route"] for item in result["route_units"]] == ["DEFER", "DEFER"]


def test_r03_gate_applicability_accepts_one_exact_route_unit_target(
    tmp_path: Path,
) -> None:
    env = build_environment(
        tmp_path / "r03-gate-route-unit", mode="two-replace", closed_gate=True
    )
    first_group = env.patch["payload"]["atomic_groups"][0]
    first_binding = {
        "atomic_group_id": first_group["atomic_group_id"],
        "group_payload_hash": first_group["group_payload_hash"],
    }
    route_unit_id = f"route-unit:{sha256_value({'patch_proposal_ref': record_ref(env.patch), 'atomic_group_bindings': [first_binding]})}"
    env.policy_reader.gate_bindings[0][
        "applicable_atomic_group_bindings_or_route_unit_ids"
    ] = [route_unit_id]
    result = env.evaluate()
    assert sorted(item["route"] for item in result["route_units"]) == [
        "ALLOW_FOR_B06",
        "DEFER",
    ]


@pytest.mark.parametrize(
    "variant",
    ["reversed_exact_groups", "duplicate_exact_group", "duplicate_route_unit"],
)
def test_r03_gate_applicability_requires_canonical_sorted_unique_targets(
    tmp_path: Path, variant: str
) -> None:
    env = build_environment(
        tmp_path / f"r03-gate-{variant}", mode="two-replace", closed_gate=True
    )
    bindings = sorted(
        [
            {
                "atomic_group_id": group["atomic_group_id"],
                "group_payload_hash": group["group_payload_hash"],
            }
            for group in env.patch["payload"]["atomic_groups"]
        ],
        key=canonical_bytes,
    )
    if variant == "reversed_exact_groups":
        targets = list(reversed(bindings))
    elif variant == "duplicate_exact_group":
        targets = [bindings[0], deepcopy(bindings[0]), bindings[1]]
    else:
        route_unit_id = f"route-unit:{sha256_value({'patch_proposal_ref': record_ref(env.patch), 'atomic_group_bindings': [bindings[0]]})}"
        targets = [route_unit_id, route_unit_id]
    env.policy_reader.gate_bindings[0][
        "applicable_atomic_group_bindings_or_route_unit_ids"
    ] = targets
    before = env.store.visible_snapshot()
    with pytest.raises(B05ContractError, match="B05_GATE_APPLICABILITY_INVALID"):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_r03_gate_replay_rejects_representation_only_reordering(
    tmp_path: Path,
) -> None:
    env = build_environment(
        tmp_path / "r03-gate-replay", mode="two-replace", closed_gate=True
    )
    bindings = sorted(
        [
            {
                "atomic_group_id": group["atomic_group_id"],
                "group_payload_hash": group["group_payload_hash"],
            }
            for group in env.patch["payload"]["atomic_groups"]
        ],
        key=canonical_bytes,
    )
    env.policy_reader.gate_bindings[0][
        "applicable_atomic_group_bindings_or_route_unit_ids"
    ] = bindings
    env.evaluate("canonical-first")
    before = env.store.visible_snapshot()
    env.policy_reader.gate_bindings[0][
        "applicable_atomic_group_bindings_or_route_unit_ids"
    ] = list(reversed(bindings))
    with pytest.raises(B05ContractError, match="B05_GATE_APPLICABILITY_INVALID"):
        env.evaluate("representation-only-replay")
    assert env.store.visible_snapshot() == before


@pytest.mark.parametrize(
    "variant",
    [
        "invalid_edge_type",
        "nonstring_edge_type",
        "free_text_evidence",
        "nonstring_evidence_type",
        "reversed_endpoints",
        "self_loop",
        "ghost_adjacent_group",
        "nonstring_unknown_reason",
    ],
)
def test_r03_validation_policy_rejects_dependency_semantic_bypasses(
    tmp_path: Path, variant: str
) -> None:
    env = build_environment(tmp_path / f"r03-policy-{variant}", mode="two-replace")
    edge = {
        "left_atomic_group_id": "replace-a",
        "right_atomic_group_id": "replace-b",
        "edge_type": "OPERATION_RESULT_DEPENDENCY",
        "evidence_tokens": [
            {
                "type": "STABLE_CHECK_CODE",
                "value": "B05_CHECK_R03_DECLARED_DEPENDENCY",
            }
        ],
    }

    def mutate(payload: dict) -> None:
        if variant == "invalid_edge_type":
            edge["edge_type"] = "FREE_TEXT"
        elif variant == "nonstring_edge_type":
            edge["edge_type"] = []
        elif variant == "free_text_evidence":
            edge["evidence_tokens"] = ["free text"]
        elif variant == "nonstring_evidence_type":
            edge["evidence_tokens"] = [{"type": [], "value": "invalid"}]
        elif variant == "reversed_endpoints":
            edge["left_atomic_group_id"] = "replace-b"
            edge["right_atomic_group_id"] = "replace-a"
        elif variant == "self_loop":
            edge["right_atomic_group_id"] = "replace-a"
        elif variant == "ghost_adjacent_group":
            payload["adjacent_check_group_ids"] = ["ghost"]
            return
        else:
            payload["unknown_dependency_tokens"] = [
                {
                    "reason_code": [],
                    "bounded_atomic_group_ids": [],
                    "supporting_refs": [],
                }
            ]
            return
        payload["declared_dependency_edges"] = [edge]

    _replace_active_policy(env, mutate)
    before = env.store.visible_snapshot()
    with pytest.raises(
        B05ContractError,
        match="B05_(POLICY_DEPENDENCY_EDGE|POLICY_GROUP_SET|UNKNOWN_DEPENDENCY)_INVALID",
    ):
        env.evaluate()
    assert env.store.visible_snapshot() == before


@pytest.mark.parametrize(
    "variant",
    [
        "duplicate_edges",
        "duplicate_evidence_tokens",
        "reversed_evidence_tokens",
        "reversed_semantic_groups",
        "duplicate_adjacent_groups",
        "reversed_unknown_bounds",
    ],
)
def test_r03_validation_policy_nested_collections_are_canonical(
    tmp_path: Path, variant: str
) -> None:
    env = build_environment(tmp_path / f"r03-policy-order-{variant}", mode="two-replace")
    tokens = sorted(
        [
            {"type": "STABLE_CHECK_CODE", "value": "B05_CHECK_R03_A"},
            {"type": "STABLE_CHECK_CODE", "value": "B05_CHECK_R03_B"},
        ],
        key=canonical_bytes,
    )
    edge = {
        "left_atomic_group_id": "replace-a",
        "right_atomic_group_id": "replace-b",
        "edge_type": "OPERATION_RESULT_DEPENDENCY",
        "evidence_tokens": [tokens[0]],
    }

    def mutate(payload: dict) -> None:
        if variant == "duplicate_edges":
            payload["declared_dependency_edges"] = [edge, deepcopy(edge)]
        elif variant == "duplicate_evidence_tokens":
            edge["evidence_tokens"] = [tokens[0], deepcopy(tokens[0])]
            payload["declared_dependency_edges"] = [edge]
        elif variant == "reversed_evidence_tokens":
            edge["evidence_tokens"] = list(reversed(tokens))
            payload["declared_dependency_edges"] = [edge]
        elif variant == "reversed_semantic_groups":
            payload["semantic_unknown_group_ids"] = ["replace-b", "replace-a"]
        elif variant == "duplicate_adjacent_groups":
            payload["adjacent_check_group_ids"] = ["replace-a", "replace-a"]
        else:
            payload["unknown_dependency_tokens"] = [
                {
                    "reason_code": "DEPENDENCY_ENDPOINT_UNKNOWN",
                    "bounded_atomic_group_ids": ["replace-b", "replace-a"],
                    "supporting_refs": [],
                }
            ]

    _replace_active_policy(env, mutate)
    before = env.store.visible_snapshot()
    with pytest.raises(
        B05ContractError,
        match="B05_(POLICY_DEPENDENCY_EDGE|POLICY_GROUP_SET|UNKNOWN_DEPENDENCY)_INVALID",
    ):
        env.evaluate()
    assert env.store.visible_snapshot() == before


def test_r03_all_contract_dependency_edge_types_remain_accepted(
    tmp_path: Path,
) -> None:
    edge_types = {
        "WRITE_WRITE_OVERLAP",
        "WRITE_READ_OVERLAP",
        "TARGET_OR_LINEAGE_DEPENDENCY",
        "SHARED_SUPPORT_AFFECTS_VALIDATION",
        "OPERATION_RESULT_DEPENDENCY",
        "PROTECTION_INTERACTION",
        "NON_COMMUTATIVE_APPLICATION",
    }
    for edge_type in sorted(edge_types):
        env = build_environment(
            tmp_path / f"r03-edge-positive-{edge_type}", mode="two-replace"
        )

        def mutate(payload: dict, selected_edge_type: str = edge_type) -> None:
            payload["declared_dependency_edges"] = [
                {
                    "left_atomic_group_id": "replace-a",
                    "right_atomic_group_id": "replace-b",
                    "edge_type": selected_edge_type,
                    "evidence_tokens": [
                        {
                            "type": "STABLE_CHECK_CODE",
                            "value": "B05_CHECK_R03_VALID_EDGE",
                        }
                    ],
                }
            ]

        _replace_active_policy(env, mutate)
        result = env.evaluate()
        assert [item["route"] for item in result["route_units"]] == [
            "ALLOW_FOR_B06"
        ]


def test_r03_all_typed_dependency_evidence_tokens_remain_accepted(
    tmp_path: Path,
) -> None:
    token_types = {
        "EXACT_RECORD_REF",
        "LINEAGE_LOCATOR",
        "EVIDENCE_LOCATOR",
        "JSON_POINTER",
        "OPERATION_FINGERPRINT",
        "STABLE_CHECK_CODE",
    }
    for token_type in sorted(token_types):
        env = build_environment(
            tmp_path / f"r03-token-positive-{token_type}", mode="two-replace"
        )
        operation = env.patch["payload"]["atomic_groups"][0]["operations"][0]
        values = {
            "EXACT_RECORD_REF": record_ref(env.records["diagnostic"]),
            "LINEAGE_LOCATOR": deepcopy(env.b01_reader.lineage_locators[0]),
            "EVIDENCE_LOCATOR": deepcopy(env.b01_reader.evidence_locators[0]),
            "JSON_POINTER": "/items/0",
            "OPERATION_FINGERPRINT": sha256_value(operation),
            "STABLE_CHECK_CODE": "B05_CHECK_R03_VALID_TOKEN",
        }

        def mutate(payload: dict, selected_token_type: str = token_type) -> None:
            payload["declared_dependency_edges"] = [
                {
                    "left_atomic_group_id": "replace-a",
                    "right_atomic_group_id": "replace-b",
                    "edge_type": "OPERATION_RESULT_DEPENDENCY",
                    "evidence_tokens": [
                        {
                            "type": selected_token_type,
                            "value": values[selected_token_type],
                        }
                    ],
                }
            ]

        _replace_active_policy(env, mutate)
        result = env.evaluate()
        assert [item["route"] for item in result["route_units"]] == [
            "ALLOW_FOR_B06"
        ]


def test_r03_pvr_defense_rejects_noncanonical_gate_targets(tmp_path: Path) -> None:
    env = build_environment(
        tmp_path / "r03-pvr-gate-defense", mode="two-replace", closed_gate=True
    )
    bindings = sorted(
        [
            {
                "atomic_group_id": group["atomic_group_id"],
                "group_payload_hash": group["group_payload_hash"],
            }
            for group in env.patch["payload"]["atomic_groups"]
        ],
        key=canonical_bytes,
    )
    env.policy_reader.gate_bindings[0][
        "applicable_atomic_group_bindings_or_route_unit_ids"
    ] = bindings
    env.evaluate()
    pvr = deepcopy(_pvr_record(env))
    pvr_binding = pvr["payload"]["input_binding"]
    pvr_binding["non_content_gate_bindings"][0][
        "applicable_atomic_group_bindings_or_route_unit_ids"
    ] = list(reversed(bindings))
    pvr_binding["non_content_gate_snapshot_hash"] = sha256_value(
        pvr_binding["non_content_gate_bindings"]
    )
    _rehash(pvr)
    with pytest.raises(B05ContractError, match="B05_GATE_APPLICABILITY_INVALID"):
        validate_output_record(pvr)


def test_r03_pvr_defense_rejects_invalid_dependency_edge(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "r03-pvr-edge-defense", mode="two-replace")
    env.evaluate()
    pvr = deepcopy(_pvr_record(env))
    dependency = pvr["payload"]["dependency_proof"]
    dependency["dependency_edges"] = [
        {
            "left_atomic_group_id": "replace-a",
            "right_atomic_group_id": "replace-b",
            "edge_type": "FREE_TEXT",
            "evidence_tokens": [
                {
                    "type": "STABLE_CHECK_CODE",
                    "value": "B05_CHECK_R03_FORGED_EDGE",
                }
            ],
        }
    ]
    dependency["partition_hash"] = sha256_value(
        {
            "group_catalog": dependency["group_catalog"],
            "dependency_edges": dependency["dependency_edges"],
            "unknown_dependency_tokens": dependency["unknown_dependency_tokens"],
            "route_unit_partition": dependency["route_unit_partition"],
        }
    )
    _rehash(pvr)
    with pytest.raises(B05ContractError, match="B05_DEPENDENCY_EDGE_INVALID"):
        validate_output_record(pvr)


def test_r03_pvr_defense_recomputes_route_unit_identity(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "r03-pvr-route-unit-id", mode="two-replace")
    env.evaluate()
    pvr = deepcopy(_pvr_record(env))
    dependency = pvr["payload"]["dependency_proof"]
    dependency["route_unit_partition"][0]["route_unit_id"] = f"route-unit:{'f' * 64}"
    dependency["route_unit_partition"] = sorted(
        dependency["route_unit_partition"], key=canonical_bytes
    )
    dependency["partition_hash"] = sha256_value(
        {
            "group_catalog": dependency["group_catalog"],
            "dependency_edges": dependency["dependency_edges"],
            "unknown_dependency_tokens": dependency["unknown_dependency_tokens"],
            "route_unit_partition": dependency["route_unit_partition"],
        }
    )
    _rehash(pvr)
    with pytest.raises(
        B05ContractError, match="B05_ROUTE_UNIT_PARTITION_INVALID"
    ):
        validate_output_record(pvr)


@pytest.mark.parametrize(
    "variant", ["known_edge_split", "unbounded_unknown_split", "nonstring_group_id"]
)
def test_r03_pvr_defense_recomputes_dependency_components(
    tmp_path: Path, variant: str
) -> None:
    env = build_environment(tmp_path / f"r03-pvr-components-{variant}", mode="two-replace")
    env.evaluate()
    pvr = deepcopy(_pvr_record(env))
    dependency = pvr["payload"]["dependency_proof"]
    if variant == "known_edge_split":
        dependency["dependency_edges"] = [
            {
                "left_atomic_group_id": "replace-a",
                "right_atomic_group_id": "replace-b",
                "edge_type": "OPERATION_RESULT_DEPENDENCY",
                "evidence_tokens": [
                    {
                        "type": "STABLE_CHECK_CODE",
                        "value": "B05_CHECK_R03_FORGED_COMPONENT",
                    }
                ],
            }
        ]
    elif variant == "unbounded_unknown_split":
        preimage = {
            "reason_code": "DEPENDENCY_ENDPOINT_UNKNOWN",
            "bounded_atomic_group_ids": [],
            "supporting_refs": [],
        }
        dependency["unknown_dependency_tokens"] = [
            {
                "token_id": f"unknown-dependency:{sha256_value(preimage)}",
                **preimage,
            }
        ]
    else:
        dependency["route_unit_partition"][0]["atomic_group_bindings"][0][
            "atomic_group_id"
        ] = []
        dependency["route_unit_partition"] = sorted(
            dependency["route_unit_partition"], key=canonical_bytes
        )
    dependency["partition_hash"] = sha256_value(
        {
            "group_catalog": dependency["group_catalog"],
            "dependency_edges": dependency["dependency_edges"],
            "unknown_dependency_tokens": dependency["unknown_dependency_tokens"],
            "route_unit_partition": dependency["route_unit_partition"],
        }
    )
    _rehash(pvr)
    with pytest.raises(
        B05ContractError, match="B05_ROUTE_UNIT_PARTITION_INVALID"
    ):
        validate_output_record(pvr)


def test_modify_m07_self_check_vectors_use_semantic_snapshot() -> None:
    from self_check import fixed_vectors

    first = fixed_vectors()
    second = fixed_vectors()
    assert first == second
    assert all("semantic_snapshot_hash" in vector for vector in first)
    assert all("visible_snapshot_hash" not in vector for vector in first)
