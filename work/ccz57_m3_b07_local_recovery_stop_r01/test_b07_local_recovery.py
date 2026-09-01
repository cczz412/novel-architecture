"""Focused B-07 state, stop, recovery, B-06 fence, and boundary tests."""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from b07_adapters import (
    accept_saved_observation,
    assert_author_payload_safe,
)
from b07_contracts import (
    B07ContractError,
    project_author_status,
    stop_receipt_ref,
    validate_current_run_state,
    validate_debug_record,
    validate_resume_plan,
    validate_stop_receipt,
)
from b07_store import B07RunStore
from work.ccz57_m3_b07_local_recovery_stop_r01.fixtures import (
    B07FixtureEnvironment,
    build_environment,
    generic_ref,
)

ROOT = Path(__file__).resolve().parent


def _stop(
    env: B07FixtureEnvironment,
    state: dict[str, Any],
    *,
    operation_id: str = "stop-1",
    reason: str = "AUTHOR_ABORTED",
) -> dict[str, Any]:
    return env.b07.stop(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        operation_id=operation_id,
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        stop_reason_code=reason,
        stop_class="LOCAL_CONTROL",
        stop_source="FIXTURE",
        authority_reader=env.authority,
    )


def test_schema_shares_b06_database_and_has_three_persistent_types(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "schema")
    names = env.b07.schema_objects()

    assert {
        "candidate_versions",
        "current_pointers",
        "merge_receipts",
        "b07_current_run_states",
        "b07_stop_receipts",
        "b07_internal_debug_records",
        "b07_run_command_dedupe",
    } <= set(names)
    assert not {
        "checkpoints",
        "commit_intents",
        "provider_checkpoints",
        "resume_plans",
        "failed_commit_receipts",
    } & set(names)


def test_b07_refuses_a_second_sqlite_transaction_domain(tmp_path: Path) -> None:
    store = B07RunStore(tmp_path / "missing-b06", clock=lambda: "2026-09-01T03:00:00Z")
    with pytest.raises(B07ContractError, match="B07_B06_TRANSACTION_DOMAIN_MISSING"):
        store.initialize_schema()


def test_open_creates_one_active_current_state_and_resume_is_derived(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "open")
    state = env.open()
    plan = env.b07.derive_resume_plan(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        authority_reader=env.authority,
    )

    validate_current_run_state(state)
    validate_resume_plan(plan)
    assert state["status"] == "ACTIVE"
    assert state["run_epoch"] == 0
    assert plan["disposition"] == "CONTINUE_SAME_RUN"
    assert "resume_plans" not in env.b07.schema_objects()
    assert env.b07.visible_counts()["b07_current_run_states"] == 1


def test_open_replay_is_idempotent_and_changed_input_conflicts(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "open-replay")
    first = env.open()
    replay = env.open()
    assert replay == first

    with pytest.raises(B07ContractError, match="B07_IDEMPOTENCY_CONFLICT"):
        env.b07.open_run(
            project_scope_id=env.project_scope_id,
            logical_run_key=env.logical_run_key,
            run_id=env.run_id,
            run_kind="DIFFERENT_KIND",
            operation_id="open-1",
            authority_reader=env.authority,
        )
    assert env.b07.visible_counts()["b07_current_run_states"] == 1


def test_saved_ccz142_observation_reads_local_bytes_and_copies_no_payload(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "saved-observation")
    raw = env.saved_result_bytes()
    saved_ref = env.b06.route_receipt_ref
    envelope = {
        "project_scope_id": env.project_scope_id,
        "run_id": env.run_id,
        "expected_run_epoch": 0,
        "expected_state_revision": 1,
        "observation_id": "observation-1",
        "observation_kind": "COMPONENT_RESULT",
        "component_kind": "CCZ142_REPAIR_COMPONENT",
        "component_contract_version": "fixture-v1",
        "saved_result_locator": "local:fixture-result",
        "saved_result_sha256": hashlib.sha256(raw).hexdigest(),
        "saved_result_ref": saved_ref,
        "result_class": "SUCCESS",
        "next_phase_hint": "CHECKING",
        "error_fingerprint": None,
        "experiment_context_hash": None,
    }

    observation = accept_saved_observation(
        envelope,
        reader=lambda locator: raw if locator == "local:fixture-result" else b"",
    )

    assert observation == {
        "component_kind": "CCZ142_REPAIR_COMPONENT",
        "component_receipt_ref": saved_ref,
        "component_result_hash": hashlib.sha256(raw).hexdigest(),
    }
    assert "payload" not in observation


def test_saved_observation_rejects_hash_drift(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "saved-drift")
    raw = env.saved_result_bytes()
    envelope = {
        "project_scope_id": env.project_scope_id,
        "run_id": env.run_id,
        "expected_run_epoch": 0,
        "expected_state_revision": 1,
        "observation_id": "observation-1",
        "observation_kind": "COMPONENT_RESULT",
        "component_kind": "CCZ142_REPAIR_COMPONENT",
        "component_contract_version": "fixture-v1",
        "saved_result_locator": "local:fixture-result",
        "saved_result_sha256": "0" * 64,
        "saved_result_ref": generic_ref("M3_COMPONENT_RECEIPT", "ccz142:saved:1"),
        "result_class": "SUCCESS",
        "next_phase_hint": "CHECKING",
        "error_fingerprint": None,
        "experiment_context_hash": None,
    }
    with pytest.raises(B07ContractError, match="B07_CCZ142_SAVED_RESULT_HASH_MISMATCH"):
        accept_saved_observation(envelope, reader=lambda _locator: raw)


def test_saved_observation_rejects_caller_supplied_ref_mismatch(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "saved-ref-mismatch")
    raw = env.saved_result_bytes()
    envelope = {
        "project_scope_id": env.project_scope_id,
        "run_id": env.run_id,
        "expected_run_epoch": 0,
        "expected_state_revision": 1,
        "observation_id": "observation-1",
        "observation_kind": "COMPONENT_RESULT",
        "component_kind": "CCZ142_REPAIR_COMPONENT",
        "component_contract_version": "fixture-v1",
        "saved_result_locator": "local:fixture-result",
        "saved_result_sha256": hashlib.sha256(raw).hexdigest(),
        "saved_result_ref": generic_ref("M3_COMPONENT_RECEIPT", "wrong-ref"),
        "result_class": "SUCCESS",
        "next_phase_hint": "CHECKING",
        "error_fingerprint": None,
        "experiment_context_hash": None,
    }
    with pytest.raises(B07ContractError, match="B07_CCZ142_SAVED_RESULT_REF_MISMATCH"):
        accept_saved_observation(envelope, reader=lambda _locator: raw)


def test_oversized_run_state_is_rejected_before_persistence(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "oversized-state")
    env.authority.snapshot["budget_state_ref"] = generic_ref(
        "M3_BUDGET_STATE", "x" * 9000
    )
    with pytest.raises(B07ContractError, match="B07_RUN_STATE_VALUE_INVALID"):
        env.open()
    assert env.b07.visible_counts()["b07_current_run_states"] == 0


def test_stop_receipt_and_stopped_state_are_one_atomic_effect(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "stop")
    state = env.open()
    receipt = _stop(env, state)
    stopped = env.b07.read_state(env.project_scope_id, env.run_id)

    validate_stop_receipt(receipt)
    assert stopped["status"] == "STOPPED"
    assert stopped["stop_receipt_ref"] == stop_receipt_ref(receipt)
    assert env.b07.visible_counts() == {
        "b07_current_run_states": 1,
        "b07_internal_debug_records": 0,
        "b07_stop_receipts": 1,
    }


@pytest.mark.parametrize(
    "failure_point",
    ["after_stop_receipt_insert", "after_stopped_state_update", "before_stop_commit"],
)
def test_stop_failure_injection_rolls_back_receipt_and_state(
    tmp_path: Path, failure_point: str
) -> None:
    env = build_environment(tmp_path / failure_point)
    state = env.open()
    env.b07.failure_point = failure_point

    with pytest.raises(B07ContractError, match="B07_SIMULATED_TRANSACTION_FAILURE"):
        _stop(env, state)

    current = env.b07.read_state(env.project_scope_id, env.run_id)
    assert current == state
    assert env.b07.visible_counts()["b07_stop_receipts"] == 0


def test_stop_replay_returns_same_receipt_and_changed_reason_conflicts(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "stop-replay")
    state = env.open()
    first = _stop(env, state)
    replay = _stop(env, state)
    assert replay == first

    with pytest.raises(B07ContractError, match="B07_IDEMPOTENCY_CONFLICT"):
        _stop(env, state, reason="RETRY_LIMIT")
    assert env.b07.visible_counts()["b07_stop_receipts"] == 1


def test_resume_increments_epoch_and_old_epoch_writes_zero(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "resume")
    state = env.open()
    waiting = env.b07.advance(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        operation_id="wait-1",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        target_status="WAITING_LOCAL",
        target_phase="CHECKING",
        wait_kind="LOCAL_COMPONENT",
        authority_reader=env.authority,
    )
    resumed = env.b07.resume(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        operation_id="resume-1",
        expected_run_epoch=waiting["run_epoch"],
        expected_state_revision=waiting["state_revision"],
        authority_reader=env.authority,
    )
    assert resumed["run_epoch"] == waiting["run_epoch"] + 1
    assert resumed["state_revision"] == waiting["state_revision"] + 1

    with pytest.raises(B07ContractError, match="B07_STALE_RUN_FENCE"):
        env.b07.advance(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            operation_id="old-epoch-write",
            expected_run_epoch=waiting["run_epoch"],
            expected_state_revision=waiting["state_revision"],
            target_status="ACTIVE",
            target_phase="CHECKING",
            wait_kind=None,
            authority_reader=env.authority,
        )
    assert env.b07.read_state(env.project_scope_id, env.run_id) == resumed


def test_stopped_run_cannot_resume_and_reopen_creates_new_generation(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "reopen")
    state = env.open()
    _stop(env, state)
    old = env.b07.read_state(env.project_scope_id, env.run_id)

    with pytest.raises(B07ContractError, match="B07_RESUME_NOT_ALLOWED"):
        env.b07.resume(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            operation_id="resume-stopped",
            expected_run_epoch=old["run_epoch"],
            expected_state_revision=old["state_revision"],
            authority_reader=env.authority,
        )

    reopened = env.b07.reopen(
        project_scope_id=env.project_scope_id,
        source_run_id=env.run_id,
        new_run_id="run-b07-fixture-reopen",
        operation_id="reopen-1",
        authority_reader=env.authority,
    )
    assert reopened["logical_run_generation"] == 2
    assert reopened["run_id"] != old["run_id"]
    assert env.b07.read_state(env.project_scope_id, env.run_id) == old


def test_b06_ack_lost_is_reconciled_as_committed_without_second_publish(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "b06-ack-lost")
    state = env.open()
    pending, fence = env.prepare_b06(state)
    committed = env.commit_b06(run_fence=fence)
    env.authority.sync_pointer(committed["current_pointer"])

    reconciled = env.b07.reconcile_b06(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        operation_id="reconcile-1",
        expected_run_epoch=pending["run_epoch"],
        expected_state_revision=pending["state_revision"],
        authority_reader=env.authority,
    )
    replay = env.commit_b06(run_fence=fence)

    assert reconciled["status"] == "ACTIVE"
    assert reconciled["pending_local_action"] is None
    assert replay["reused_existing_commit"] is True
    assert env.b06.store.visible_counts()["merge_receipts"] == 1


def test_stop_before_b06_publish_denies_old_run_with_zero_b06_writes(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "stop-before-b06")
    state = env.open()
    pending, fence = env.prepare_b06(state)
    _stop(env, pending, operation_id="stop-before-publish")

    with pytest.raises(B07ContractError, match="B07_B06_FENCE_STALE"):
        env.commit_b06(run_fence=fence)
    assert env.b06.store.visible_counts() == {
        "candidate_versions": 1,
        "current_pointers": 1,
        "merge_receipts": 0,
    }


def test_b06_commit_can_win_then_existing_operation_replays_after_stop(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "b06-before-stop")
    state = env.open()
    pending, fence = env.prepare_b06(state)
    first = env.commit_b06(run_fence=fence)
    env.authority.sync_pointer(first["current_pointer"])
    _stop(env, pending, operation_id="stop-after-publish")

    replay = env.commit_b06(run_fence=fence)
    assert replay["reused_existing_commit"] is True
    assert replay["merge_receipt_ref"] == first["merge_receipt_ref"]


def test_no_b06_publication_reconciles_to_exactly_one_stop(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "b06-not-published")
    state = env.open()
    pending, _fence = env.prepare_b06(state)

    stopped = env.b07.reconcile_b06(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        operation_id="reconcile-no-publish",
        expected_run_epoch=pending["run_epoch"],
        expected_state_revision=pending["state_revision"],
        authority_reader=env.authority,
    )
    receipt = env.b07.read_stop_receipt(env.project_scope_id, env.run_id)
    assert stopped["status"] == "STOPPED"
    assert receipt["payload"]["stop_reason_code"] == "B06_NOT_PUBLISHED"
    assert env.b07.visible_counts()["b07_stop_receipts"] == 1


def test_competing_pointer_reconciles_to_conflict_stop(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "b06-conflict")
    state = env.open()
    pending, _fence = env.prepare_b06(state)
    pointer = env.b06.store.read_pointer(env.b06.live_pointer["logical_pointer_key"])
    pointer["generation"] += 1
    with sqlite3.connect(env.b06.store._database_path) as connection:  # noqa: SLF001
        connection.execute(
            "UPDATE current_pointers SET pointer_json = ? WHERE logical_pointer_key = ?",
            (
                json.dumps(
                    pointer, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8"),
                pointer["logical_pointer_key"],
            ),
        )
    env.authority.sync_pointer(pointer)

    stopped = env.b07.reconcile_b06(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        operation_id="reconcile-conflict",
        expected_run_epoch=pending["run_epoch"],
        expected_state_revision=pending["state_revision"],
        authority_reader=env.authority,
    )
    receipt = env.b07.read_stop_receipt(env.project_scope_id, env.run_id)
    assert stopped["status"] == "STOPPED"
    assert receipt["payload"]["stop_reason_code"] == "B06_POINTER_CONFLICT"


def test_debug_is_best_effort_and_author_payload_rejects_internal_fields(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "debug")
    state = env.open()
    receipt = _stop(env, state)
    debug_payload = env.debug_payload()
    debug_payload["stop_receipt_ref"] = stop_receipt_ref(receipt)
    debug = env.b07.append_debug(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        payload=debug_payload,
    )
    validate_debug_record(debug)
    author_payload = project_author_status(
        env.b07.read_state(env.project_scope_id, env.run_id)
    )
    assert_author_payload_safe(author_payload)

    with pytest.raises(B07ContractError, match="B07_AUTHOR_PAYLOAD_INTERNAL_FIELD"):
        assert_author_payload_safe({"status": "stopped", "debug": {"token": 1}})


def test_debug_failure_does_not_roll_back_prior_stop(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "debug-failure")
    state = env.open()
    _stop(env, state)
    env.b07.failure_point = "debug_before_commit"

    with pytest.raises(B07ContractError, match="B07_SIMULATED_TRANSACTION_FAILURE"):
        env.b07.append_debug(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            payload=env.debug_payload(),
        )
    assert env.b07.read_state(env.project_scope_id, env.run_id)["status"] == "STOPPED"
    assert env.b07.visible_counts()["b07_stop_receipts"] == 1
    assert env.b07.visible_counts()["b07_internal_debug_records"] == 0


def test_debug_retention_over_thirty_days_is_rejected(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "debug-retention")
    env.open()
    payload = env.debug_payload()
    payload["retention_expires_at"] = "2026-10-08T03:00:00Z"

    with pytest.raises(B07ContractError, match="B07_DEBUG_RETENTION_INVALID"):
        env.b07.append_debug(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            payload=payload,
        )
    assert env.b07.visible_counts()["b07_internal_debug_records"] == 0


def test_two_concurrent_stops_have_one_visible_winner(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "concurrent-stop")
    state = env.open()

    def run(operation_id: str) -> str:
        try:
            _stop(env, state, operation_id=operation_id)
        except B07ContractError as error:
            return error.code
        return "STOPPED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run, ["stop-a", "stop-b"]))
    assert results.count("STOPPED") == 1
    assert len(results) == 2
    assert env.b07.visible_counts()["b07_stop_receipts"] == 1


def test_database_reopen_reads_same_state_and_stop(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "database-reopen")
    state = env.open()
    receipt = _stop(env, state)
    reopened = B07RunStore(env.b06.store.root, clock=env.clock)
    reopened.initialize_schema()

    assert reopened.read_state(env.project_scope_id, env.run_id)["status"] == "STOPPED"
    assert reopened.read_stop_receipt(env.project_scope_id, env.run_id) == receipt


def test_b07_imports_have_no_model_network_or_subprocess_execution() -> None:
    forbidden_modules = {
        "requests",
        "httpx",
        "openai",
        "anthropic",
        "socket",
        "subprocess",
    }
    for name in ("b07_contracts.py", "b07_store.py", "b07_adapters.py"):
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
