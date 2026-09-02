"""Focused B-09 authority, phase, determinism, and boundary tests."""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import sqlite3
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
    B05ContractError,
    canonical_bytes,
    record_ref,
    sha256_value,
    validate_output_record,
)
from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    record_ref as b01_record_ref,
)
from work.ccz57_m3_b05_patch_route_r03_5.fixtures import (  # noqa: E402
    REOPENED_AT,
    build_environment as build_b05_environment,
    external_record,
)
from patch_route_projection import PatchAggregateProjector  # noqa: E402
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
from work.ccz57_m3_b07_local_recovery_stop_r01.b07_contracts import (  # noqa: E402
    state_hash_value,
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

from b09_authority_reader import (  # noqa: E402
    CurrentCausalHintAuthorityReader,
    _decode_state_row,
    _decode_terminal_row,
    _require_causal_proposal_closure,
    _require_route_validation_binding,
)
from b09_contracts import (  # noqa: E402
    B09AuthorityError,
    B09ContractError,
    validate_request,
    validate_view,
)
from current_causal_hint_view import (  # noqa: E402
    _resolve_evidence,
    project_current_causal_hints,
    read_current_causal_hints,
)


def test_package_imports_share_b09_exception_identity() -> None:
    package_root = "work.ccz57_m3_b09_current_causal_hint_view_r01"
    b05_contracts = importlib.import_module("b05_contracts")
    b08_contracts = importlib.import_module("b08_contracts")
    contracts = importlib.import_module(f"{package_root}.b09_contracts")
    authority_reader = importlib.import_module(f"{package_root}.b09_authority_reader")
    causal_hint_view = importlib.import_module(
        f"{package_root}.current_causal_hint_view"
    )

    assert authority_reader.B09ContractError is contracts.B09ContractError
    assert authority_reader.B09AuthorityError is contracts.B09AuthorityError
    assert causal_hint_view.B09ContractError is contracts.B09ContractError
    assert causal_hint_view.B09AuthorityError is contracts.B09AuthorityError
    assert authority_reader.B05ContractError is b05_contracts.B05ContractError
    assert causal_hint_view.B05ContractError is b05_contracts.B05ContractError
    assert authority_reader.B08ContractError is b08_contracts.B08ContractError

    with pytest.raises(contracts.B09AuthorityError, match="AUTHORITY_HASH_MISMATCH"):
        authority_reader.CurrentCausalHintAuthorityReader._b05_projection([{}])
    mapped = causal_hint_view._guard_error(
        b05_contracts.B05ContractError("B05_DOWNSTREAM_GUARD_POLICY_STALE")
    )
    assert mapped.reason_code == "AUTHORITY_DRIFT"

    def reject_b08_current(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise b08_contracts.B08ContractError("B08_AUTHORITY_SNAPSHOT_INVALID")

    reader = authority_reader.CurrentCausalHintAuthorityReader(
        b05_store=None,
        shared_database_path=Path("."),
        freshness_reader=lambda: {},
        immutable_reader=lambda _ref: {},
        b08_authority_reader=SimpleNamespace(read_current=reject_b08_current),
    )
    terminal = {
        "payload": {
            "run_binding": {
                "project_scope_id": "project:test",
                "logical_run_key": "run:test",
            }
        }
    }
    with pytest.raises(contracts.B09AuthorityError, match="AUTHORITY_STATE_INCOHERENT"):
        reader._b08_currentness(None, terminal)


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
        except B05ContractError:
            try:
                key = canonical_bytes(b01_record_ref(record))
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
    route_mode: str | None = None,
    b05_options: dict[str, Any] | None = None,
) -> SimpleNamespace:
    mode = "causal"
    if safe_postcommit:
        mode = "order-add" if multi_support else "add"
    if route_mode is not None:
        mode = route_mode
    b05 = build_b05_environment(
        root / "b05",
        mode=mode,
        **({} if b05_options is None else b05_options),
    )
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
    route_units = route["payload"]["route_units"]
    assert route_units
    route_unit_id = (allow_entries or route_units)[0]["route_unit_id"]

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
    ("hint_key", "expected_type"),
    [
        ("causal_hint_proposal_ref", "M3_CAUSAL_HINT_PROPOSAL"),
        ("route_receipt_ref", "M3_PATCH_ROUTE_RECEIPT"),
        ("lifecycle_head_ref", "M3_PATCH_LIFECYCLE_RECEIPT"),
        ("diagnostic_refs", "M3_DIAGNOSTIC"),
        ("coverage_observation_refs", "M3_COVERAGE_OBSERVATION"),
        ("authorized_source_slice_refs", "M3_AUTHORIZED_SOURCE_SLICE"),
    ],
)
@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("record_version", True),
        ("source_module", "NOT_M3"),
        ("access", []),
    ],
)
def test_view_rejects_rehashed_invalid_top_level_record_identity(
    tmp_path: Path,
    hint_key: str,
    expected_type: str,
    field: str,
    bad_value: Any,
) -> None:
    world = _build_world(tmp_path / f"{hint_key}-{field}")
    view = read_current_causal_hints(world.make_reader(), world.request)
    hint = view["hints"][0]
    if hint_key.endswith("_refs"):
        ref = deepcopy(hint["causal_hint_proposal_ref"])
        ref["record_type"] = expected_type
        hint[hint_key] = [ref]
    else:
        ref = hint[hint_key]
    ref[field] = bad_value
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )

    with pytest.raises(B09ContractError, match="B09_HINT_REF_INVALID"):
        validate_view(view)


@pytest.mark.parametrize(
    ("target", "bad_value", "error_code"),
    [
        ("status", [], "B09_VIEW_VALUE_INVALID"),
        ("reason_code", {}, "B09_VIEW_VALUE_INVALID"),
        ("phase", [], "B09_PHASE_INVALID"),
    ],
)
def test_view_rejects_unhashable_discriminators_through_contract(
    tmp_path: Path,
    target: str,
    bad_value: Any,
    error_code: str,
) -> None:
    world = _build_world(tmp_path / target)
    view = read_current_causal_hints(world.make_reader(), world.request)
    if target == "phase":
        view["scope"]["phase"] = bad_value
    else:
        view[target] = bad_value
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )

    with pytest.raises(B09ContractError, match=error_code):
        validate_view(view)


@pytest.mark.parametrize(
    "missing_support",
    ["evidence", "diagnostic_and_coverage"],
)
def test_view_rejects_stripped_mandatory_causal_support(
    tmp_path: Path,
    missing_support: str,
) -> None:
    world = _build_world(tmp_path / missing_support)
    view = read_current_causal_hints(world.make_reader(), world.request)
    hint = view["hints"][0]
    if missing_support == "evidence":
        hint["current_evidence_locators"] = []
    else:
        hint["diagnostic_refs"] = []
        hint["coverage_observation_refs"] = []
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )

    with pytest.raises(B09ContractError, match="B09_HINT_SUPPORT_INVALID"):
        validate_view(view)


def test_view_rejects_boolean_ordinal(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "boolean-ordinal")
    view = read_current_causal_hints(world.make_reader(), world.request)
    view["hints"][0]["ordinal"] = True
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )

    with pytest.raises(B09ContractError, match="B09_HINT_VALUE_INVALID"):
        validate_view(view)


def test_view_rejects_malformed_supporting_route_unit_id(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "malformed-route-unit")
    view = read_current_causal_hints(world.make_reader(), world.request)
    view["hints"][0]["supporting_route_unit_ids"] = ["invalid"]
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )

    with pytest.raises(B09ContractError, match="B09_HINT_SUPPORT_INVALID"):
        validate_view(view)


def test_view_rejects_noncanonical_list_value_through_contract(
    tmp_path: Path,
) -> None:
    world = _build_world(tmp_path / "noncanonical-list-value")
    view = read_current_causal_hints(world.make_reader(), world.request)
    view["hints"][0]["supporting_route_unit_ids"] = [1.5]

    with pytest.raises(B09ContractError, match="B09_HINT_ORDER_INVALID"):
        validate_view(view)


def test_view_rejects_duplicate_causal_proposal_identity(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "duplicate-proposal", hint_count=2)
    view = read_current_causal_hints(world.make_reader(), world.request)
    view["hints"][1]["causal_hint_proposal_ref"] = deepcopy(
        view["hints"][0]["causal_hint_proposal_ref"]
    )
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )

    with pytest.raises(B09ContractError, match="B09_HINT_ORDER_INVALID"):
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
    ("field", "bad_value"),
    [
        ("pointer_namespace", "PRODUCT"),
        ("candidate_schema_id", "wrong-schema"),
        ("author_workspace_logical_key", ""),
        ("input_binding_hash", "0" * 64),
    ],
)
def test_reader_rejects_corrupt_complete_live_pointer(
    tmp_path: Path,
    field: str,
    bad_value: str,
) -> None:
    world = _build_world(tmp_path / field)
    pointer_key = world.live_pointer["logical_pointer_key"]
    with sqlite3.connect(world.b06_store._database_path) as connection:
        row = connection.execute(
            "SELECT pointer_json FROM current_pointers WHERE logical_pointer_key = ?",
            (pointer_key,),
        ).fetchone()
        assert row is not None
        pointer = json.loads(bytes(row[0]).decode("utf-8"))
        pointer[field] = bad_value
        connection.execute(
            "UPDATE current_pointers SET pointer_json = ? "
            "WHERE logical_pointer_key = ?",
            (canonical_bytes(pointer), pointer_key),
        )

    view = read_current_causal_hints(world.make_reader(), world.request)
    assert view["status"] == "ERROR"
    assert view["reason_code"] == "AUTHORITY_STATE_INCOHERENT"


def test_reader_rejects_coherently_rehashed_candidate_access_policy(
    tmp_path: Path,
) -> None:
    world = _build_world(tmp_path / "candidate-access-policy")
    pointer_key = world.live_pointer["logical_pointer_key"]
    old_ref = world.live_pointer["current_candidate_version_ref"]
    old_ref_hash = sha256_value(old_ref)
    with sqlite3.connect(world.b06_store._database_path) as connection:
        candidate_row = connection.execute(
            "SELECT record_json FROM candidate_versions WHERE ref_hash = ?",
            (old_ref_hash,),
        ).fetchone()
        pointer_row = connection.execute(
            "SELECT pointer_json FROM current_pointers WHERE logical_pointer_key = ?",
            (pointer_key,),
        ).fetchone()
        assert candidate_row is not None
        assert pointer_row is not None
        candidate = json.loads(bytes(candidate_row[0]).decode("utf-8"))
        pointer = json.loads(bytes(pointer_row[0]).decode("utf-8"))
        candidate["access"] = "RUN_INTERNAL_READ_ONLY"
        candidate["record_hash"] = sha256_value(
            {key: value for key, value in candidate.items() if key != "record_hash"}
        )
        new_ref = record_ref(candidate)
        pointer["current_candidate_version_ref"] = new_ref
        connection.execute(
            "UPDATE candidate_versions SET ref_hash = ?, record_json = ? "
            "WHERE ref_hash = ?",
            (sha256_value(new_ref), canonical_bytes(candidate), old_ref_hash),
        )
        connection.execute(
            "UPDATE current_pointers SET pointer_json = ? "
            "WHERE logical_pointer_key = ?",
            (canonical_bytes(pointer), pointer_key),
        )

    view = read_current_causal_hints(world.make_reader(), world.request)
    assert view["status"] == "ERROR"
    assert view["reason_code"] == "AUTHORITY_REFERENCE_CONFLICT"


def test_reader_rejects_coherently_rehashed_invalid_candidate_payload(
    tmp_path: Path,
) -> None:
    world = _build_world(tmp_path / "candidate-lineage-index", bind_route=False)
    pointer_key = world.live_pointer["logical_pointer_key"]
    old_ref = world.live_pointer["current_candidate_version_ref"]
    old_ref_hash = sha256_value(old_ref)
    with sqlite3.connect(world.b06_store._database_path) as connection:
        candidate_row = connection.execute(
            "SELECT record_json FROM candidate_versions WHERE ref_hash = ?",
            (old_ref_hash,),
        ).fetchone()
        pointer_row = connection.execute(
            "SELECT pointer_json FROM current_pointers WHERE logical_pointer_key = ?",
            (pointer_key,),
        ).fetchone()
        state_row = connection.execute(
            "SELECT state_json FROM b07_current_run_states "
            "WHERE project_scope_id = ? AND run_id = ?",
            (world.project_scope_id, world.run_id),
        ).fetchone()
        assert candidate_row is not None
        assert pointer_row is not None
        assert state_row is not None
        candidate = json.loads(bytes(candidate_row[0]).decode("utf-8"))
        pointer = json.loads(bytes(pointer_row[0]).decode("utf-8"))
        state = json.loads(bytes(state_row[0]).decode("utf-8"))
        candidate["payload"]["lineage_index"][0]["json_pointer"] = "/items/1"
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
        new_ref = record_ref(candidate)
        pointer["current_candidate_version_ref"] = new_ref
        state["authority_snapshot"]["observed_candidate_version_ref"] = deepcopy(
            new_ref
        )
        state["state_hash"] = state_hash_value(state)
        connection.execute(
            "UPDATE candidate_versions SET ref_hash = ?, record_json = ? "
            "WHERE ref_hash = ?",
            (sha256_value(new_ref), canonical_bytes(candidate), old_ref_hash),
        )
        connection.execute(
            "UPDATE current_pointers SET pointer_json = ? "
            "WHERE logical_pointer_key = ?",
            (canonical_bytes(pointer), pointer_key),
        )
        connection.execute(
            "UPDATE b07_current_run_states SET state_json = ? "
            "WHERE project_scope_id = ? AND run_id = ?",
            (canonical_bytes(state), world.project_scope_id, world.run_id),
        )

    view = read_current_causal_hints(world.make_reader(), world.request)
    assert view["status"] == "ERROR"
    assert view["reason_code"] == "AUTHORITY_HASH_MISMATCH"


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


@pytest.mark.parametrize(
    "freshness_key",
    [
        "b02_scope_snapshot_hash",
        "active_policy_selection_hash",
        "non_content_gate_snapshot_hash",
    ],
)
def test_nonrouted_causal_hint_rejects_stale_route_freshness(
    tmp_path: Path,
    freshness_key: str,
) -> None:
    world = _build_world(
        tmp_path / freshness_key,
        route_mode="causal",
        b05_options={"semantic_unknown_groups": ["replace-a"]},
    )
    assert all(
        entry["route"] != "ROUTE_TO_B09"
        for entry in world.route["payload"]["causal_hint_routes"]
    )
    world.freshness.snapshot[freshness_key] = sha256_value(
        {"stale_route_freshness": freshness_key}
    )

    view = read_current_causal_hints(world.make_reader(), world.request)
    assert (view["status"], view["reason_code"]) == (
        "ERROR",
        "AUTHORITY_DRIFT",
    )


def test_superseded_route_returns_empty(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "superseded-route")
    before = PatchAggregateProjector.project(world.b05.store.read_records())
    prior_route = before["series"][0]["active_route_receipt_ref"]
    prior_head = before["series"][0]["lifecycle_head_ref"]

    new_payload = deepcopy(world.b05.patch["payload"])
    group = new_payload["atomic_groups"][0]
    group["purpose"] = "b09-superseded-route-fixture"
    group["group_payload_hash"] = sha256_value(
        {key: value for key, value in group.items() if key != "group_payload_hash"}
    )
    new_patch = external_record(
        "M3_PATCH_PROPOSAL", new_payload, created_at=REOPENED_AT
    )
    world.b05.patch = new_patch
    reopened = world.b05.evaluate(
        "b09-supersede-route",
        created_at=REOPENED_AT,
        prior_active_route_receipt_ref_or_null=prior_route,
        prior_lifecycle_head_ref_or_null=prior_head,
        material_delta_refs=[record_ref(new_patch)],
    )
    after = PatchAggregateProjector.project(world.b05.store.read_records())
    assert reopened["route_receipt_ref"] != prior_route
    assert after["series"][0]["active_route_receipt_ref"] == reopened[
        "route_receipt_ref"
    ]

    view = read_current_causal_hints(world.make_reader(), world.request)
    assert view["status"] == "EMPTY"
    assert view["reason_code"] == "NO_ROUTE_TO_B09"
    assert view["scope"]["phase"] == "NOT_APPLICABLE"
    assert view["hints"] == []


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


@pytest.mark.parametrize("ref_key", ["route_receipt_ref", "lifecycle_head_ref"])
def test_multi_hint_view_rejects_mixed_authority_heads(
    tmp_path: Path,
    ref_key: str,
) -> None:
    world = _build_world(tmp_path / ref_key, hint_count=2)
    view = read_current_causal_hints(world.make_reader(), world.request)
    view["hints"][1][ref_key]["record_id"] += ":other-head"
    view["hints"] = sorted(
        view["hints"],
        key=lambda hint: canonical_bytes(
            {
                "causal_hint_proposal_ref": hint["causal_hint_proposal_ref"],
                "route_receipt_ref": hint["route_receipt_ref"],
                "mapping_proof_hash": hint["mapping_proof_hash"],
            }
        ),
    )
    for ordinal, hint in enumerate(view["hints"], start=1):
        hint["ordinal"] = ordinal
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )

    with pytest.raises(B09ContractError, match="B09_HINT_AUTHORITY_HEAD_MISMATCH"):
        validate_view(view)


def test_reader_detects_pre_post_authority_drift(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "drift")
    world.freshness.drift_on_read = world.freshness.read_count + 2
    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "ERROR",
        "AUTHORITY_DRIFT",
    )
    assert all(value is None for key, value in view["scope"].items() if key != "phase")


def test_reader_fingerprints_merge_receipt_across_two_passes(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "merge-receipt-drift", safe_postcommit=True)
    _commit(world)
    read_count = 0

    def freshness_with_merge_drift() -> dict[str, str]:
        nonlocal read_count
        read_count += 1
        if read_count == 2:
            with sqlite3.connect(world.b06_store._database_path) as connection:
                row = connection.execute(
                    "SELECT operation_id, receipt_json FROM merge_receipts "
                    "WHERE project_scope_id = ?",
                    (world.project_scope_id,),
                ).fetchone()
                assert row is not None
                receipt = json.loads(bytes(row[1]).decode("utf-8"))
                receipt["created_at"] = "2026-09-01T09:00:01Z"
                receipt["payload"]["committed_at"] = receipt["created_at"]
                receipt["record_id"] = (
                    f"merge-receipt:{sha256_value(receipt['payload'])}"
                )
                receipt["record_hash"] = sha256_value(
                    {
                        key: value
                        for key, value in receipt.items()
                        if key != "record_hash"
                    }
                )
                connection.execute(
                    "UPDATE merge_receipts SET receipt_json = ? "
                    "WHERE project_scope_id = ? AND operation_id = ?",
                    (canonical_bytes(receipt), world.project_scope_id, row[0]),
                )
        return world.freshness()

    reader = world.make_reader()
    reader._freshness_reader = freshness_with_merge_drift
    view = read_current_causal_hints(reader, world.request)

    assert (view["status"], view["reason_code"]) == (
        "ERROR",
        "AUTHORITY_DRIFT",
    )


@pytest.mark.parametrize("column", ["operation_id", "request_hash"])
def test_merge_receipt_mirrored_columns_must_match_payload(
    tmp_path: Path,
    column: str,
) -> None:
    world = _build_world(tmp_path / f"merge-receipt-{column}", safe_postcommit=True)
    _commit(world)
    with sqlite3.connect(world.b06_store._database_path) as connection:
        connection.execute(
            f"UPDATE merge_receipts SET {column} = ? WHERE project_scope_id = ?",
            (f"tampered-{column}", world.project_scope_id),
        )

    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "ERROR",
        "AUTHORITY_STATE_INCOHERENT",
    )


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


@pytest.mark.parametrize(
    "reason_code",
    ["AUTHORITY_READER_UNAVAILABLE", "AUTHORITY_HASH_MISMATCH", "AUTHORITY_DRIFT"],
)
def test_candidate_dependency_reader_preserves_b09_authority_error(
    tmp_path: Path,
    reason_code: str,
) -> None:
    world = _build_world(tmp_path / reason_code.lower())
    candidate = world.b05.b01_reader.read_scope()["candidate_version_record"]
    target_ref = candidate["payload"]["segment_index_ref"]

    def unavailable_reader(ref: dict[str, Any]) -> dict[str, Any]:
        if canonical_bytes(ref) == canonical_bytes(target_ref):
            raise B09AuthorityError(reason_code, "candidate dependency")
        return world.read_immutable(ref)

    view = read_current_causal_hints(
        world.make_reader(immutable_override=unavailable_reader), world.request
    )

    assert (view["status"], view["reason_code"]) == ("ERROR", reason_code)


@pytest.mark.parametrize(
    "field",
    [
        "patch_proposal_ref",
        "protection_set_ref",
        "base_candidate_version_ref",
        "candidate_schema_id",
        "chapter_revision_ref",
        "seg",
        "segment_index_ref",
        "live_pointer_binding_hash",
        "b02_scope_snapshot_hash",
        "non_content_gate_snapshot_hash",
    ],
)
def test_route_header_must_match_selected_validation_input(
    tmp_path: Path,
    field: str,
) -> None:
    world = _build_world(tmp_path / f"route-pvr-{field}")
    route = deepcopy(world.route)
    validation = world.b05.store.record_by_ref(
        route["payload"]["validation_receipt_ref"]
    )
    value = route["payload"]["binding_header"][field]
    if isinstance(value, dict):
        value = deepcopy(value)
        first_key = next(iter(value))
        value[first_key] = f"{value[first_key]}:other"
    elif isinstance(value, int):
        value += 1
    else:
        value = "f" * 64 if len(value) == 64 else f"{value}:other"
    route["payload"]["binding_header"][field] = value
    route["payload"]["binding_header_hash"] = sha256_value(
        route["payload"]["binding_header"]
    )
    route["record_id"] = f"patch-route:{sha256_value(route['payload'])}"
    route["record_hash"] = sha256_value(
        {key: value for key, value in route.items() if key != "record_hash"}
    )
    validate_output_record(route)

    with pytest.raises(B09AuthorityError, match="AUTHORITY_REFERENCE_CONFLICT"):
        _require_route_validation_binding(route, validation)


@pytest.mark.parametrize(
    "field",
    [
        "evaluation_key",
        "evaluation_input_hash",
        "validator_identity_ref",
        "validation_policy_ref",
        "active_policy_selection_ref",
        "active_policy_selection_hash",
    ],
)
def test_route_metadata_must_match_selected_validation_receipt(
    tmp_path: Path,
    field: str,
) -> None:
    world = _build_world(tmp_path / f"route-pvr-metadata-{field}")
    route = deepcopy(world.route)
    validation = world.b05.store.record_by_ref(
        route["payload"]["validation_receipt_ref"]
    )
    value = route["payload"][field]
    if isinstance(value, dict):
        value = deepcopy(value)
        first_key = next(iter(value))
        value[first_key] = f"{value[first_key]}:other"
    else:
        value = "f" * 64 if len(value) == 64 else f"{value}:other"
    route["payload"][field] = value
    route["record_id"] = f"patch-route:{sha256_value(route['payload'])}"
    route["record_hash"] = sha256_value(
        {key: value for key, value in route.items() if key != "record_hash"}
    )
    validate_output_record(route)

    with pytest.raises(B09AuthorityError, match="AUTHORITY_REFERENCE_CONFLICT"):
        _require_route_validation_binding(route, validation)


@pytest.mark.parametrize(
    "missing_from",
    ["route", "validation_input", "validation_mapping", "patch"],
)
def test_routed_proposals_must_share_one_validation_closure(
    tmp_path: Path,
    missing_from: str,
) -> None:
    world = _build_world(tmp_path / f"proposal-closure-{missing_from}")
    route = deepcopy(world.route)
    validation = world.b05.store.record_by_ref(
        route["payload"]["validation_receipt_ref"]
    )
    patch = deepcopy(world.b05.patch)
    if missing_from == "route":
        route["payload"]["causal_hint_routes"] = []
    elif missing_from == "validation_input":
        validation["payload"]["input_binding"]["causal_hint_proposal_refs"] = []
    elif missing_from == "validation_mapping":
        validation["payload"]["causal_support_mappings"] = []
    else:
        patch["payload"]["sidecar_proposal_refs"] = []

    with pytest.raises(B09AuthorityError, match="AUTHORITY_REFERENCE_CONFLICT"):
        _require_causal_proposal_closure(route, validation, patch)


@pytest.mark.parametrize("identity_field", ["project_scope_id", "run_id"])
def test_requested_run_row_must_match_its_database_key(
    tmp_path: Path,
    identity_field: str,
) -> None:
    world = _build_world(tmp_path / f"run-row-{identity_field}")
    with sqlite3.connect(world.b06_store._database_path) as connection:
        row = connection.execute(
            "SELECT state_json FROM b07_current_run_states "
            "WHERE project_scope_id = ? AND run_id = ?",
            (world.project_scope_id, world.run_id),
        ).fetchone()
        assert row is not None
        state = json.loads(bytes(row[0]).decode("utf-8"))
        state[identity_field] = f"{state[identity_field]}:other"
        state["state_hash"] = state_hash_value(state)
        connection.execute(
            "UPDATE b07_current_run_states SET state_json = ? "
            "WHERE project_scope_id = ? AND run_id = ?",
            (canonical_bytes(state), world.project_scope_id, world.run_id),
        )

    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "ERROR",
        "AUTHORITY_STATE_INCOHERENT",
    )


@pytest.mark.parametrize(
    ("column", "bad_value"),
    [
        ("logical_run_generation", 2),
        ("run_epoch", 1),
        ("state_revision", 2),
        ("status", "SUCCEEDED"),
    ],
)
def test_current_run_payload_must_match_all_selected_row_columns(
    tmp_path: Path,
    column: str,
    bad_value: Any,
) -> None:
    world = _build_world(tmp_path / f"current-run-row-{column}")
    with sqlite3.connect(world.b06_store._database_path) as connection:
        connection.execute(
            f"UPDATE b07_current_run_states SET {column} = ? "
            "WHERE project_scope_id = ? AND run_id = ?",
            (bad_value, world.project_scope_id, world.run_id),
        )

    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "ERROR",
        "AUTHORITY_STATE_INCOHERENT",
    )


def test_state_row_stop_receipt_id_must_match_payload(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "state-row-stop-receipt")
    state = _state(world)
    row = (
        state["project_scope_id"],
        state["run_id"],
        state["logical_run_key"],
        state["logical_run_generation"],
        state["run_epoch"],
        state["state_revision"],
        state["status"],
        "stop-receipt:other",
        canonical_bytes(state),
    )

    with pytest.raises(B09AuthorityError, match="AUTHORITY_STATE_INCOHERENT"):
        _decode_state_row(row, detail="test run state bytes")


@pytest.mark.parametrize("column_index", range(10))
def test_terminal_row_mirrored_columns_must_match_record(
    tmp_path: Path,
    column_index: int,
) -> None:
    world = _build_world(tmp_path / f"terminal-row-{column_index}")
    state = _enter_finalizing(world)
    world.b08_store.publish(
        project_scope_id=world.project_scope_id,
        run_id=world.run_id,
        operation_id="terminal-row-b09",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
    )
    with sqlite3.connect(world.b06_store._database_path) as connection:
        row = list(
            connection.execute(
                "SELECT terminalization_key, project_scope_id, logical_run_key, "
                "run_id, logical_run_generation, run_epoch, operation_id, "
                "call_request_hash, record_id, record_hash, record_json "
                "FROM b08_segment_terminal_receipts"
            ).fetchone()
        )
    if isinstance(row[column_index], int):
        row[column_index] += 1
    else:
        row[column_index] = (
            "f" * 64
            if len(row[column_index]) == 64
            else f"{row[column_index]}:other"
        )

    with pytest.raises(B09AuthorityError, match="AUTHORITY_STATE_INCOHERENT"):
        _decode_terminal_row(tuple(row))


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        (
            "chapter_revision_ref",
            {
                "chapter_id": "other-chapter",
                "revision_no": 1,
                "revision_text_sha256": "f" * 64,
            },
        ),
        (
            "base_candidate_version_ref",
            {
                "contract": "M3_RECORD_REF",
                "contract_version": "r03.5-candidate",
                "record_type": "M3_CANDIDATE_VERSION",
                "record_id": "cv:other",
                "record_version": 1,
                "record_contract_version": "r03.5-candidate",
                "record_hash": "f" * 64,
                "access": "POLICY_FIXTURE_READ_ONLY",
                "source_module": "M3",
            },
        ),
    ],
)
def test_reader_applies_complete_b04_patch_contract(
    tmp_path: Path,
    field: str,
    bad_value: Any,
) -> None:
    world = _build_world(tmp_path / f"patch-contract-{field}")
    snapshot = world.make_reader().read(world.request)
    invalid_patch = deepcopy(world.b05.patch)
    invalid_patch["payload"][field] = bad_value
    _rehash_external(invalid_patch, "patch-proposal")
    invalid_patch_ref = record_ref(invalid_patch)
    collected = deepcopy(snapshot)
    for key in (
        "request",
        "b05_records",
        "causal_hint_proposals",
        "current_segment_index",
    ):
        collected.pop(key)
    collected["validation_receipt"]["payload"]["input_binding"][
        "patch_proposal_ref"
    ] = invalid_patch_ref

    def reissued_reader(ref: dict[str, Any]) -> dict[str, Any]:
        if canonical_bytes(ref) == canonical_bytes(invalid_patch_ref):
            return deepcopy(invalid_patch)
        return world.read_immutable(ref)

    reader = world.make_reader(immutable_override=reissued_reader)
    with pytest.raises(B09AuthorityError, match="AUTHORITY_HASH_MISMATCH"):
        reader._attach_immutables(collected)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("noncommittable", False),
        ("expiry_request_seconds", 0),
        (
            "chapter_revision_ref",
            {
                "chapter_id": "other-chapter",
                "revision_no": 1,
                "revision_text_sha256": "f" * 64,
            },
        ),
    ],
)
def test_reader_applies_complete_b04_causal_contract(
    tmp_path: Path,
    field: str,
    bad_value: Any,
) -> None:
    world = _build_world(tmp_path / field)
    snapshot = world.make_reader().read(world.request)
    invalid_proposal = deepcopy(snapshot["causal_hint_proposals"][0])
    invalid_proposal["payload"][field] = bad_value
    _rehash_external(invalid_proposal, "causal-hint-proposal")
    invalid_ref = record_ref(invalid_proposal)
    invalid_patch = deepcopy(world.b05.patch)
    invalid_patch["payload"]["sidecar_proposal_refs"] = [invalid_ref]
    _rehash_external(invalid_patch, "patch-proposal")
    invalid_patch_ref = record_ref(invalid_patch)
    collected = deepcopy(snapshot)
    for key in (
        "request",
        "b05_records",
        "causal_hint_proposals",
        "current_segment_index",
    ):
        collected.pop(key)
    collected["active_route"]["payload"]["causal_hint_routes"][0][
        "causal_hint_proposal_ref"
    ] = invalid_ref
    collected["validation_receipt"]["payload"]["input_binding"][
        "causal_hint_proposal_refs"
    ] = [invalid_ref]
    collected["validation_receipt"]["payload"]["input_binding"][
        "patch_proposal_ref"
    ] = invalid_patch_ref
    collected["validation_receipt"]["payload"]["causal_support_mappings"][0][
        "causal_hint_proposal_ref"
    ] = invalid_ref

    def reissued_reader(ref: dict[str, Any]) -> dict[str, Any]:
        if canonical_bytes(ref) == canonical_bytes(invalid_ref):
            return deepcopy(invalid_proposal)
        if canonical_bytes(ref) == canonical_bytes(invalid_patch_ref):
            return deepcopy(invalid_patch)
        return world.read_immutable(ref)

    reader = world.make_reader(immutable_override=reissued_reader)
    with pytest.raises(B09AuthorityError, match="AUTHORITY_HASH_MISMATCH"):
        reader._attach_immutables(collected)


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


@pytest.mark.parametrize(
    "mismatch_kind",
    ["validation_receipt_ref", "patch_proposal_ref", "protection_set_ref"],
)
def test_postcommit_merge_receipt_must_match_selected_validation_closure(
    tmp_path: Path,
    mismatch_kind: str,
) -> None:
    world = _build_world(
        tmp_path / f"postcommit-merge-closure-{mismatch_kind}",
        safe_postcommit=True,
    )
    _commit(world)
    snapshot = world.make_reader().read(world.request)
    merge_receipt = snapshot["merge_receipt_or_null"]
    mismatched_ref = deepcopy(merge_receipt["payload"][mismatch_kind])
    mismatched_ref["record_id"] = f"{mismatched_ref['record_id']}:other"
    mismatched_ref["record_hash"] = sha256_value(mismatched_ref)
    merge_receipt["payload"][mismatch_kind] = mismatched_ref
    merge_receipt["record_hash"] = sha256_value(
        {
            key: value
            for key, value in merge_receipt.items()
            if key != "record_hash"
        }
    )

    view = project_current_causal_hints(snapshot)

    assert (view["status"], view["reason_code"]) == (
        "EMPTY",
        "POST_COMMIT_NOT_PROVABLY_UNCHANGED",
    )


@pytest.mark.parametrize(
    "mismatch_kind", ["atomic_group_bindings", "canonical_apply_result_hash"]
)
def test_postcommit_merge_receipt_must_match_selected_apply_proof(
    tmp_path: Path,
    mismatch_kind: str,
) -> None:
    world = _build_world(
        tmp_path / f"postcommit-merge-proof-{mismatch_kind}",
        safe_postcommit=True,
    )
    _commit(world)
    snapshot = world.make_reader().read(world.request)
    merge_receipt = snapshot["merge_receipt_or_null"]
    if mismatch_kind == "atomic_group_bindings":
        merge_receipt["payload"][mismatch_kind][0]["group_payload_hash"] = "f" * 64
    else:
        merge_receipt["payload"][mismatch_kind] = "f" * 64
    merge_receipt["record_id"] = (
        f"merge-receipt:{sha256_value(merge_receipt['payload'])}"
    )
    merge_receipt["record_hash"] = sha256_value(
        {
            key: value
            for key, value in merge_receipt.items()
            if key != "record_hash"
        }
    )

    view = project_current_causal_hints(snapshot)

    assert (view["status"], view["reason_code"]) == (
        "EMPTY",
        "POST_COMMIT_NOT_PROVABLY_UNCHANGED",
    )


@pytest.mark.parametrize("mismatch_kind", ["extra", "different"])
def test_postcommit_view_rejects_route_unit_mismatch(
    tmp_path: Path,
    mismatch_kind: str,
) -> None:
    world = _build_world(
        tmp_path / f"postcommit-route-unit-{mismatch_kind}",
        safe_postcommit=True,
        hint_count=2,
    )
    _commit(world)
    view = read_current_causal_hints(world.make_reader(), world.request)
    other_route_unit_id = "route-unit:" + "f" * 64
    if other_route_unit_id == view["hints"][0]["supporting_route_unit_ids"][0]:
        other_route_unit_id = "route-unit:" + "e" * 64
    if mismatch_kind == "extra":
        view["hints"][0]["supporting_route_unit_ids"] = sorted(
            [
                *view["hints"][0]["supporting_route_unit_ids"],
                other_route_unit_id,
            ],
            key=canonical_bytes,
        )
    else:
        view["hints"][1]["supporting_route_unit_ids"] = [other_route_unit_id]
    view["view_hash"] = sha256_value(
        {key: value for key, value in view.items() if key != "view_hash"}
    )

    with pytest.raises(B09ContractError, match="B09_HINT_SUPPORT_INVALID"):
        validate_view(view)


def test_postcommit_endpoint_change_returns_empty(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "postcommit-endpoint-change")
    _commit(world)
    view = read_current_causal_hints(world.make_reader(), world.request)

    assert (view["status"], view["reason_code"]) == (
        "EMPTY",
        "POST_COMMIT_NOT_PROVABLY_UNCHANGED",
    )


def test_postcommit_deleted_endpoint_lineage_returns_empty(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "postcommit-deleted-endpoint", safe_postcommit=True)
    _commit(world)
    snapshot = world.make_reader().read(world.request)
    lineage_id = snapshot["causal_hint_proposals"][0]["payload"][
        "from_lineage_locator"
    ]["lineage_id"]
    snapshot["current_candidate"]["payload"]["items"] = [
        item
        for item in snapshot["current_candidate"]["payload"]["items"]
        if item["lineage_id"] != lineage_id
    ]

    view = project_current_causal_hints(snapshot)

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


def test_postcommit_deleted_evidence_lineage_is_unsafe(tmp_path: Path) -> None:
    world = _build_world(tmp_path / "postcommit-deleted-evidence", safe_postcommit=True)
    _commit(world)
    snapshot = world.make_reader().read(world.request)
    original = snapshot["causal_hint_proposals"][0]["payload"]["evidence_locators"][0]
    changed = deepcopy(snapshot["current_candidate"])
    changed["payload"]["items"] = [
        item
        for item in changed["payload"]["items"]
        if item["lineage_id"] != original["lineage_id"]
    ]

    with pytest.raises(ValueError, match="evidence lineage unavailable"):
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
