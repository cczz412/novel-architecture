"""Focused B-09 authority, phase, determinism, and boundary tests."""

from __future__ import annotations

import ast
import inspect
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[1]
B05_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b05_patch_route_r03_5"
B06_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b06_commit_core_r01"
B07_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b07_local_recovery_stop_r01"
B08_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b08_segment_terminal_r01"
for candidate in (REPOSITORY_ROOT, B05_ROOT, B06_ROOT, B07_ROOT, B08_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    canonical_bytes,
    record_ref,
    sha256_value,
)
from work.ccz57_m3_b05_patch_route_r03_5.fixtures import (  # noqa: E402
    build_environment as build_b05_environment,
    external_record,
)
from work.ccz57_m3_b06_commit_core_r01.b06_store import (  # noqa: E402
    B06CommitService,
    B06CommitStore,
)
from work.ccz57_m3_b06_commit_core_r01.fixtures import (  # noqa: E402
    FreshnessReader,
)
from work.ccz57_m3_b07_local_recovery_stop_r01.b07_adapters import (  # noqa: E402
    derive_b06_request_hash,
)
from work.ccz57_m3_b07_local_recovery_stop_r01.b07_store import (  # noqa: E402
    B07RunStore,
)
from work.ccz57_m3_b07_local_recovery_stop_r01.fixtures import (  # noqa: E402
    AuthorityFixture,
    FixtureClock as B07FixtureClock,
)
from work.ccz57_m3_b08_segment_terminal_r01.b08_store import (  # noqa: E402
    B08SegmentTerminalStore,
)
from work.ccz57_m3_b08_segment_terminal_r01.fixtures import (  # noqa: E402
    B08AuthorityFixture,
    FixtureClock as B08FixtureClock,
)

from b09_authority_reader import CurrentCausalHintAuthorityReader  # noqa: E402
from b09_contracts import (  # noqa: E402
    B09ContractError,
    validate_request,
    validate_view,
)
from current_causal_hint_view import (  # noqa: E402
    _resolve_evidence,
    project_current_causal_hints,
    read_current_causal_hints,
)


def _rehash_external(record: dict[str, Any], prefix: str) -> None:
    record["record_id"] = f"{prefix}:{sha256_value(record['payload'])}"
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )


def _prepare_causals(b05: Any, *, safe_postcommit: bool, hint_count: int) -> None:
    if b05.causals:
        first_payload = deepcopy(b05.causals[0]["payload"])
    else:
        b01 = b05.b01_reader.read_scope()
        context = b01["upstream_context"]
        first_payload = {
            "from_lineage_locator": deepcopy(context["lineage_locators"][0]),
            "to_lineage_locator": deepcopy(context["lineage_locators"][1]),
            "evidence_locators": sorted(
                deepcopy(context["evidence_locators"]), key=canonical_bytes
            ),
            "coverage_observation_refs": [record_ref(b05.records["coverage"])],
            "authorized_source_slice_refs": [],
            "diagnostic_refs": [],
            "hint_kind": "DIRECT_POSSIBLE_CAUSE",
            "expiry_request_seconds": 3600,
            "noncommittable": True,
            "chapter_revision_ref": deepcopy(
                context["candidate_version"]["payload"]["chapter_revision_ref"]
            ),
        }
    causals = [external_record("M3_CAUSAL_HINT_PROPOSAL", first_payload)]
    if hint_count == 2:
        second_payload = deepcopy(first_payload)
        second_payload["hint_kind"] = "SECOND_OPINION_POSSIBLE_CAUSE"
        causals.append(external_record("M3_CAUSAL_HINT_PROPOSAL", second_payload))
    b05.causals = sorted(causals, key=lambda item: canonical_bytes(record_ref(item)))
    b05.patch = deepcopy(b05.patch)
    b05.patch["payload"]["sidecar_proposal_refs"] = sorted(
        [record_ref(item) for item in b05.causals], key=canonical_bytes
    )
    _rehash_external(b05.patch, "patch-proposal")


def _immutable_reader(records: list[dict[str, Any]]) -> Any:
    indexed: dict[bytes, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        try:
            key = canonical_bytes(record_ref(record))
        except ValueError:
            continue
        prior = indexed.get(key)
        if prior is not None and canonical_bytes(prior) != canonical_bytes(record):
            raise AssertionError("fixture immutable identity collision")
        indexed[key] = deepcopy(record)

    def read(ref: dict[str, Any]) -> dict[str, Any]:
        return deepcopy(indexed[canonical_bytes(ref)])

    read.indexed = indexed  # type: ignore[attr-defined]
    return read


def _build_world(
    root: Path,
    *,
    safe_postcommit: bool = False,
    hint_count: int = 1,
    bind_route: bool = True,
    multi_support: bool = False,
    valid_route_hash: bool = True,
) -> SimpleNamespace:
    mode = "causal"
    if safe_postcommit:
        mode = "order-add" if multi_support else "add"
    b05 = build_b05_environment(root / "b05", mode=mode)
    _prepare_causals(
        b05,
        safe_postcommit=safe_postcommit,
        hint_count=hint_count,
    )
    result = b05.evaluate("b05-route-operation")
    route = b05.store.record_by_ref(result["route_receipt_ref"])
    allow_entries = [
        item
        for item in route["payload"]["route_units"]
        if item["route"] == "ALLOW_FOR_B06"
    ]
    assert allow_entries
    route_unit_id = allow_entries[0]["route_unit_id"]

    b01_snapshot = b05.b01_reader.read_scope()
    base_candidate = b01_snapshot["candidate_version_record"]
    live_pointer = b01_snapshot["live_pointer_binding"]
    reference_records = b01_snapshot["candidate_reference_records"]
    freshness = FreshnessReader(
        {
            "b02_scope_snapshot_hash": route["payload"]["binding_header"][
                "b02_scope_snapshot_hash"
            ],
            "active_policy_selection_hash": route["payload"][
                "active_policy_selection_hash"
            ],
            "non_content_gate_snapshot_hash": route["payload"]["binding_header"][
                "non_content_gate_snapshot_hash"
            ],
        }
    )
    b06_store = B06CommitStore(root / "shared")
    b06_store.initialize(
        base_candidate=base_candidate,
        live_pointer=live_pointer,
        reference_records=reference_records,
    )
    b06_stub = SimpleNamespace(store=b06_store, live_pointer=live_pointer)
    authority = AuthorityFixture(b06_stub)
    if bind_route:
        authority.snapshot["route_decision_ref"] = record_ref(route)
        authority.snapshot["route_decision_hash"] = (
            route["record_hash"] if valid_route_hash else "0" * 64
        )

    b07 = B07RunStore(b06_store.root, clock=B07FixtureClock())
    b07.initialize_schema()
    b06_service = B06CommitService(
        store=b06_store,
        b05_store=b05.store,
        freshness_reader=freshness,
        run_fence_reader=b07.run_fence_reader,
        reference_records=reference_records,
    )
    project_scope_id = live_pointer["project_scope_id"]
    logical_run_key = "logical-run:b09-fixture"
    run_id = "run-b09-fixture"
    state = b07.open_run(
        project_scope_id=project_scope_id,
        logical_run_key=logical_run_key,
        run_id=run_id,
        run_kind="FACT_EXTRACTION_REPAIR",
        operation_id="open-b09",
        authority_reader=authority,
    )

    b08_authority = B08AuthorityFixture()
    b08_store = B08SegmentTerminalStore(
        b06_store.root,
        clock=B08FixtureClock(),
        authority_reader=b08_authority,
    )
    b08_store.initialize_schema()

    immutable_records = [
        *reference_records,
        b05.patch,
        b05.protection,
        *b05.causals,
        *[record for record in b05.records.values() if isinstance(record, dict)],
    ]
    read_immutable = _immutable_reader(immutable_records)

    def make_reader(
        *,
        immutable_override: Any = None,
    ) -> CurrentCausalHintAuthorityReader:
        return CurrentCausalHintAuthorityReader(
            b05_store=b05.store,
            shared_database_path=b06_store._database_path,
            freshness_reader=freshness,
            immutable_reader=(
                read_immutable if immutable_override is None else immutable_override
            ),
            b08_authority_reader=b08_authority,
        )

    request = {
        "project_scope_id": project_scope_id,
        "run_id": run_id,
        "expected_logical_run_generation": state["logical_run_generation"],
        "expected_run_epoch": state["run_epoch"],
        "segment_scope_hash": state["authority_snapshot"]["segment_scope_hash"],
        "purpose": "CCZ142_READ_ONLY_FEEDBACK",
    }
    return SimpleNamespace(
        root=root,
        b05=b05,
        route=route,
        route_unit_id=route_unit_id,
        b06_store=b06_store,
        b06_service=b06_service,
        live_pointer=live_pointer,
        freshness=freshness,
        reference_records=reference_records,
        b07=b07,
        authority=authority,
        b08_store=b08_store,
        b08_authority=b08_authority,
        project_scope_id=project_scope_id,
        logical_run_key=logical_run_key,
        run_id=run_id,
        request=request,
        read_immutable=read_immutable,
        make_reader=make_reader,
    )


def _state(world: SimpleNamespace) -> dict[str, Any]:
    return world.b07.read_state(world.project_scope_id, world.run_id)


def _commit(world: SimpleNamespace) -> dict[str, Any]:
    state = _state(world)
    operation_id = "b06-operation-b09"
    committed_at = "2026-09-01T09:00:00Z"
    run_fence = {
        "project_scope_id": world.project_scope_id,
        "run_id": world.run_id,
        "expected_run_epoch": state["run_epoch"],
        "expected_state_revision": state["state_revision"] + 1,
    }
    request_hash = derive_b06_request_hash(
        project_scope_id=world.project_scope_id,
        logical_pointer_key=world.live_pointer["logical_pointer_key"],
        operation_id=operation_id,
        route_receipt_ref=record_ref(world.route),
        route_unit_id=world.route_unit_id,
        patch_proposal=world.b05.patch,
        protection_set=world.b05.protection,
        committed_at=committed_at,
        run_fence=run_fence,
    )
    pointer = world.b06_store.read_pointer(world.live_pointer["logical_pointer_key"])
    pending = {
        "kind": "B06_PUBLISH",
        "operation_id": operation_id,
        "request_hash": request_hash,
        "expected_pointer_key": pointer["logical_pointer_key"],
        "expected_pointer_generation": pointer["generation"],
        "expected_candidate_version_ref": deepcopy(
            pointer["current_candidate_version_ref"]
        ),
    }
    prepared = world.b07.advance(
        project_scope_id=world.project_scope_id,
        run_id=world.run_id,
        operation_id="prepare-b06-b09",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        target_status="B06_OUTCOME_PENDING",
        target_phase="COMMITTING",
        wait_kind=None,
        authority_reader=world.authority,
        pending_local_action=pending,
    )
    result = world.b06_service.commit(
        project_scope_id=world.project_scope_id,
        logical_pointer_key=world.live_pointer["logical_pointer_key"],
        operation_id=operation_id,
        route_receipt_ref=record_ref(world.route),
        route_unit_id=world.route_unit_id,
        patch_proposal=deepcopy(world.b05.patch),
        protection_set=deepcopy(world.b05.protection),
        committed_at=committed_at,
        run_fence=run_fence,
    )
    pointer_after = world.b06_store.read_pointer(
        world.live_pointer["logical_pointer_key"]
    )
    world.authority.sync_pointer(pointer_after)
    world.b07.reconcile_b06(
        project_scope_id=world.project_scope_id,
        run_id=world.run_id,
        operation_id="reconcile-b06-b09",
        expected_run_epoch=prepared["run_epoch"],
        expected_state_revision=prepared["state_revision"],
        authority_reader=world.authority,
        committed_status="ACTIVE",
        committed_phase="FINALIZING",
    )
    return result


def _enter_finalizing(world: SimpleNamespace) -> dict[str, Any]:
    state = _state(world)
    if state["phase"] == "FINALIZING":
        return state
    return world.b07.advance(
        project_scope_id=world.project_scope_id,
        run_id=world.run_id,
        operation_id="enter-finalizing-b09",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        target_status="ACTIVE",
        target_phase="FINALIZING",
        wait_kind=None,
        authority_reader=world.authority,
    )


def test_request_contract_rejects_caller_owned_authority() -> None:
    request = {
        "project_scope_id": "project",
        "run_id": "run",
        "expected_logical_run_generation": 1,
        "expected_run_epoch": 0,
        "segment_scope_hash": "1" * 64,
        "purpose": "CCZ142_READ_ONLY_FEEDBACK",
    }
    validate_request(request)
    request["route_receipt_ref"] = {}
    with pytest.raises(B09ContractError, match="B09_REQUEST_SHAPE_INVALID"):
        validate_request(request)


def test_precommit_current_is_available_and_nonpersistent(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "precommit")
    view = read_current_causal_hints(world.make_reader(), world.request)

    validate_view(view)
    assert view["status"] == "AVAILABLE"
    assert view["scope"]["phase"] == "PRE_COMMIT_CURRENT"
    assert len(view["hints"]) == 1
    assert view["hints"][0]["advisory_only"] is True
    assert view["hints"][0]["committable"] is False
    assert view["hints"][0]["author_visible"] is False
    assert view["hints"][0]["cross_run_reusable"] is False
    assert view["hints"][0]["exportable"] is False


@pytest.mark.parametrize(
    ("locator_key", "pointer_key", "bad_pointer", "error_code"),
    [
        (
            "current_from_lineage_locator",
            "json_pointer",
            "/items/00",
            "B09_HINT_LINEAGE_LOCATOR_INVALID",
        ),
        (
            "current_evidence_locators",
            "evidence_json_pointer",
            "/items/0",
            "B09_HINT_EVIDENCE_LOCATOR_INVALID",
        ),
    ],
)
def test_view_rejects_rehashed_malformed_nested_locators(
    tmp_path: Path,
    locator_key: str,
    pointer_key: str,
    bad_pointer: str,
    error_code: str,
) -> None:
    world = _build_world(tmp_path / pointer_key)
    view = read_current_causal_hints(world.make_reader(), world.request)
    hint = view["hints"][0]
    locator = hint[locator_key]
    if isinstance(locator, list):
        locator = locator[0]
    locator[pointer_key] = bad_pointer
    locator["locator_hash"] = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )

    with pytest.raises(B09ContractError, match=error_code):
        validate_view(view)


@pytest.mark.parametrize(
    ("scope_key", "bad_value"),
    [
        ("project_scope_id", 7),
        ("logical_run_key", ""),
        ("run_id", []),
        ("segment_scope_hash", "not-a-hash"),
        ("pointer_logical_key", ""),
    ],
)
def test_view_rejects_rehashed_invalid_authority_scope_values(
    tmp_path: Path,
    scope_key: str,
    bad_value: Any,
) -> None:
    world = _build_world(tmp_path / scope_key)
    view = read_current_causal_hints(world.make_reader(), world.request)
    view["scope"][scope_key] = bad_value
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )

    with pytest.raises(B09ContractError, match="B09_SCOPE"):
        validate_view(view)


@pytest.mark.parametrize(
    "scope_key", ["chapter_revision_ref", "current_candidate_version_ref"]
)
def test_view_rejects_rehashed_invalid_authority_scope_refs(
    tmp_path: Path,
    scope_key: str,
) -> None:
    world = _build_world(tmp_path / scope_key)
    view = read_current_causal_hints(world.make_reader(), world.request)
    view["scope"][scope_key] = {}
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )

    with pytest.raises(B09ContractError, match="B09_SCOPE"):
        validate_view(view)


def test_no_b07_route_is_a_normal_empty_view(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "no-route", bind_route=False)
    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "EMPTY",
        "NO_ROUTE_TO_B09",
    )
    assert view["scope"]["phase"] == "NOT_APPLICABLE"


def test_multiple_hints_have_deterministic_order_ordinals_and_hash(
    tmp_path: Path,
) -> None:
    world = _build_world(tmp_path / "deterministic", hint_count=2)
    first = read_current_causal_hints(world.make_reader(), world.request)
    second = read_current_causal_hints(world.make_reader(), world.request)

    assert first == second
    assert [item["ordinal"] for item in first["hints"]] == [1, 2]
    keys = [
        canonical_bytes(
            {
                "causal_hint_proposal_ref": item["causal_hint_proposal_ref"],
                "route_receipt_ref": item["route_receipt_ref"],
                "mapping_proof_hash": item["mapping_proof_hash"],
            }
        )
        for item in first["hints"]
    ]
    assert keys == sorted(keys)


def test_reader_detects_pre_post_authority_drift(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "drift")
    world.freshness.drift_on_read = world.freshness.read_count + 2
    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "ERROR",
        "AUTHORITY_DRIFT",
    )
    assert all(value is None for key, value in view["scope"].items() if key != "phase")


def test_exact_immutable_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "bad-proposal")
    target_ref = record_ref(world.b05.causals[0])

    def tampered_reader(ref: dict[str, Any]) -> dict[str, Any]:
        record = world.read_immutable(ref)
        if canonical_bytes(ref) == canonical_bytes(target_ref):
            record["payload"]["hint_kind"] = "TAMPERED_WITHOUT_REHASH"
        return record

    view = read_current_causal_hints(
        world.make_reader(immutable_override=tampered_reader), world.request
    )
    assert (view["status"], view["reason_code"]) == (
        "ERROR",
        "AUTHORITY_HASH_MISMATCH",
    )


def test_b07_route_hash_must_equal_exact_route_record_hash(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "bad-route-hash", valid_route_hash=False)
    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "ERROR",
        "AUTHORITY_HASH_MISMATCH",
    )


def test_old_epoch_and_generation_requests_close_without_reusing_hint(
    tmp_path: Path,
) -> None:
    world = _build_world(tmp_path / "stale-request")
    stale_epoch = deepcopy(world.request)
    stale_epoch["expected_run_epoch"] += 1
    stale_generation = deepcopy(world.request)
    stale_generation["expected_logical_run_generation"] += 1

    for request in (stale_epoch, stale_generation):
        view = read_current_causal_hints(world.make_reader(), request)
        assert (view["status"], view["reason_code"]) == (
            "CLOSED",
            "REQUEST_RUN_IDENTITY_STALE",
        )


def test_request_scope_stale_closes(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "scope-stale")
    request = deepcopy(world.request)
    request["segment_scope_hash"] = sha256_value({"different": "segment"})
    view = read_current_causal_hints(world.make_reader(), request)

    assert (view["status"], view["reason_code"]) == (
        "CLOSED",
        "REQUEST_SCOPE_STALE",
    )


def test_stop_closes_without_persisting_a_b09_lifecycle(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "stop")
    state = _state(world)
    world.b07.stop(
        project_scope_id=world.project_scope_id,
        run_id=world.run_id,
        operation_id="stop-b09",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        stop_reason_code="AUTHOR_ABORTED",
        stop_class="LOCAL_CONTROL",
        stop_source="B09_TEST",
        authority_reader=world.authority,
    )
    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "CLOSED",
        "RUN_STOPPED",
    )


def test_exact_current_terminal_closes(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "terminal")
    state = _enter_finalizing(world)
    result = world.b08_store.publish(
        project_scope_id=world.project_scope_id,
        run_id=world.run_id,
        operation_id="terminal-b09",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
    )
    state = _state(world)
    world.b07.advance(
        project_scope_id=world.project_scope_id,
        run_id=world.run_id,
        operation_id="bind-terminal-b09",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        target_status="SUCCEEDED",
        target_phase="FINALIZING",
        wait_kind=None,
        authority_reader=world.authority,
        component_observation=result["component_observation"],
    )
    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "CLOSED",
        "EXACT_CURRENT_SEGMENT_TERMINAL",
    )


def test_bound_terminal_with_b08_classification_drift_is_error(
    tmp_path: Path,
) -> None:
    world = _build_world(tmp_path / "terminal-classification-drift")
    state = _enter_finalizing(world)
    result = world.b08_store.publish(
        project_scope_id=world.project_scope_id,
        run_id=world.run_id,
        operation_id="terminal-classification-drift-b09",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
    )
    state = _state(world)
    world.b07.advance(
        project_scope_id=world.project_scope_id,
        run_id=world.run_id,
        operation_id="bind-terminal-classification-drift-b09",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        target_status="SUCCEEDED",
        target_phase="FINALIZING",
        wait_kind=None,
        authority_reader=world.authority,
        component_observation=result["component_observation"],
    )
    world.b08_authority.classification["classification_policy_hash"] = sha256_value(
        {"policy": "b08-fixture", "version": 2}
    )

    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "ERROR",
        "AUTHORITY_STATE_INCOHERENT",
    )


def test_b07_b08_terminal_conflict_is_error(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "terminal-conflict")
    state = _enter_finalizing(world)
    world.b08_store.publish(
        project_scope_id=world.project_scope_id,
        run_id=world.run_id,
        operation_id="terminal-conflict-b09",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
    )
    state = _state(world)
    world.b07.advance(
        project_scope_id=world.project_scope_id,
        run_id=world.run_id,
        operation_id="succeed-without-terminal-binding",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        target_status="SUCCEEDED",
        target_phase="FINALIZING",
        wait_kind=None,
        authority_reader=world.authority,
    )
    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "ERROR",
        "AUTHORITY_STATE_INCOHERENT",
    )


def test_old_epoch_unbound_terminal_does_not_close_resumed_run(
    tmp_path: Path,
) -> None:
    world = _build_world(tmp_path / "resume-terminal")
    state = _enter_finalizing(world)
    world.b08_store.publish(
        project_scope_id=world.project_scope_id,
        run_id=world.run_id,
        operation_id="old-terminal-b09",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
    )
    resumed = world.b07.resume(
        project_scope_id=world.project_scope_id,
        run_id=world.run_id,
        operation_id="resume-b09",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        authority_reader=world.authority,
    )
    request = deepcopy(world.request)
    request["expected_run_epoch"] = resumed["run_epoch"]
    view = read_current_causal_hints(world.make_reader(), request)

    assert view["status"] == "AVAILABLE"
    assert view["scope"]["run_epoch"] == resumed["run_epoch"]


def test_postcommit_exact_child_narrow_positive(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "postcommit-positive", safe_postcommit=True)
    _commit(world)
    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["scope"]["phase"]) == (
        "AVAILABLE",
        "POST_COMMIT_EXACT_CHILD",
    )
    assert len(view["hints"][0]["supporting_route_unit_ids"]) == 1


def test_postcommit_endpoint_change_returns_empty(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "postcommit-endpoint-change")
    _commit(world)
    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "EMPTY",
        "POST_COMMIT_NOT_PROVABLY_UNCHANGED",
    )


def test_postcommit_evidence_binding_change_is_rejected(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "evidence-change", safe_postcommit=True)
    _commit(world)
    snapshot = world.make_reader().read(world.request)
    original = snapshot["causal_hint_proposals"][0]["payload"]["evidence_locators"][0]
    changed = deepcopy(snapshot["current_candidate"])
    item = next(
        item
        for item in changed["payload"]["items"]
        if item["lineage_id"] == original["lineage_id"]
    )
    item["evidence_binding"]["evidence_sha256"] = "f" * 64
    changed["record_hash"] = sha256_value(
        {key: value for key, value in changed.items() if key != "record_hash"}
    )

    with pytest.raises(ValueError, match="evidence binding changed"):
        _resolve_evidence(
            original=original,
            base_candidate=snapshot["base_candidate"],
            current_candidate=changed,
            post_commit=True,
        )


def test_postcommit_multiple_supporting_units_return_empty(tmp_path: Path) -> None:
    world = _build_world(
        tmp_path / "multi-support",
        safe_postcommit=True,
        multi_support=True,
    )
    assert (
        len(
            world.route["payload"]["causal_hint_routes"][0]["supporting_route_unit_ids"]
        )
        == 2
    )
    _commit(world)
    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "EMPTY",
        "POST_COMMIT_NOT_PROVABLY_UNCHANGED",
    )


def test_postcommit_recommit_and_rollback_are_not_reused(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "postcommit-pointer", safe_postcommit=True)
    _commit(world)
    snapshot = world.make_reader().read(world.request)

    recommit = deepcopy(snapshot)
    recommit["current_pointer"]["generation"] += 1
    recommit["run_state"]["authority_snapshot"]["observed_pointer_generation"] += 1
    recommit["authority_fingerprint"]["pointer_generation"] += 1
    recommit["authority_fingerprint"]["pointer_binding_hash"] = sha256_value(
        recommit["current_pointer"]
    )
    assert project_current_causal_hints(recommit)["reason_code"] == (
        "POST_COMMIT_NOT_PROVABLY_UNCHANGED"
    )

    rollback = deepcopy(snapshot)
    rollback["current_pointer"]["generation"] += 2
    rollback["current_pointer"]["current_candidate_version_ref"] = record_ref(
        rollback["base_candidate"]
    )
    rollback["current_candidate"] = deepcopy(rollback["base_candidate"])
    rollback["run_state"]["authority_snapshot"]["observed_pointer_generation"] = (
        rollback["current_pointer"]["generation"]
    )
    rollback["run_state"]["authority_snapshot"]["observed_candidate_version_ref"] = (
        deepcopy(rollback["current_pointer"]["current_candidate_version_ref"])
    )
    rollback["authority_fingerprint"]["pointer_generation"] = rollback[
        "current_pointer"
    ]["generation"]
    rollback["authority_fingerprint"]["pointer_binding_hash"] = sha256_value(
        rollback["current_pointer"]
    )
    assert project_current_causal_hints(rollback)["reason_code"] == (
        "POST_COMMIT_NOT_PROVABLY_UNCHANGED"
    )


def test_authority_reader_constructor_owns_all_non_request_inputs() -> None:
    assert set(
        inspect.signature(CurrentCausalHintAuthorityReader.__init__).parameters
    ) == {
        "self",
        "b05_store",
        "shared_database_path",
        "freshness_reader",
        "immutable_reader",
        "b08_authority_reader",
    }
    assert set(inspect.signature(CurrentCausalHintAuthorityReader.read).parameters) == {
        "self",
        "request",
    }


def test_static_boundaries_have_no_b09_writer_schema_model_network_or_b10_edge() -> (
    None
):
    implementation = [
        ROOT / "b09_contracts.py",
        ROOT / "b09_authority_reader.py",
        ROOT / "current_causal_hint_view.py",
    ]
    forbidden_import_roots = {
        "requests",
        "httpx",
        "urllib",
        "socket",
        "subprocess",
        "openai",
        "anthropic",
    }
    for path in implementation:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        class_names = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        }
        assert not forbidden_import_roots & imported
        assert not {name for name in class_names if name.endswith(("Store", "Writer"))}
        assert "CREATE TABLE" not in source.upper()
        assert "INSERT INTO" not in source.upper()
        assert "UPDATE " not in source.upper()
        assert "DELETE FROM" not in source.upper()

    b10_files = list((REPOSITORY_ROOT / "work").glob("*b10*/*.py"))
    assert all(
        "ccz57_m3_b09" not in path.read_text(encoding="utf-8")
        and "current_causal_hint" not in path.read_text(encoding="utf-8")
        for path in b10_files
    )
    assert {path.name for path in ROOT.iterdir() if path.is_file()} == {
        "README.md",
        "b09_contracts.py",
        "b09_authority_reader.py",
        "current_causal_hint_view.py",
        "test_current_causal_hint_view.py",
        "self_check.py",
    }
