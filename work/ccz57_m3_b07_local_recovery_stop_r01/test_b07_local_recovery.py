"""Focused B-07 state, stop, recovery, B-06 fence, and boundary tests."""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from b07_adapters import (
    assert_author_payload_safe,
    verify_saved_artifact,
)
from b07_contracts import (
    TERMINAL_ARTIFACT_KIND,
    TERMINAL_COMPONENT_KIND,
    B07ContractError,
    project_author_status,
    record_ref,
    sha256_value,
    stop_receipt_ref,
    validate_current_run_state,
    validate_debug_record,
    validate_resume_plan,
    validate_stop_receipt,
    validate_stop_receipt_for_state,
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


def _terminal_ready(
    env: B07FixtureEnvironment,
    state: dict[str, Any],
    *,
    marker: str,
) -> dict[str, Any]:
    return env.bind_terminal_observation(
        state,
        operation_id=f"bind-{marker}",
        marker=marker,
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
    envelope = {
        "component_kind": "CCZ142_REPAIR_COMPONENT",
        "artifact_kind": "component_output",
        "workspace_relative_locator": "TEMP/fixture-result.json",
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
    }

    observation = verify_saved_artifact(
        envelope,
        reader=lambda locator: raw if locator == "TEMP/fixture-result.json" else b"",
    )

    assert observation == {
        "component_kind": "CCZ142_REPAIR_COMPONENT",
        "component_artifact_ref": {
            "artifact_kind": "component_output",
            "workspace_relative_locator": "TEMP/fixture-result.json",
            "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        },
    }
    assert "payload" not in observation


def test_saved_observation_rejects_hash_drift(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "saved-drift")
    raw = env.saved_result_bytes()
    envelope = {
        "component_kind": "CCZ142_REPAIR_COMPONENT",
        "artifact_kind": "component_output",
        "workspace_relative_locator": "TEMP/fixture-result.json",
        "artifact_sha256": "0" * 64,
    }
    with pytest.raises(B07ContractError, match="B07_CCZ142_SAVED_RESULT_HASH_MISMATCH"):
        verify_saved_artifact(envelope, reader=lambda _locator: raw)


def test_saved_observation_rejects_non_relative_or_unused_caller_fields(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "saved-ref-mismatch")
    raw = env.saved_result_bytes()
    base = {
        "component_kind": "CCZ142_REPAIR_COMPONENT",
        "artifact_kind": "component_output",
        "workspace_relative_locator": "TEMP/fixture-result.json",
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
    }
    for locator in ("/tmp/result.json", "TEMP/../result.json"):
        envelope = dict(base, workspace_relative_locator=locator)
        with pytest.raises(B07ContractError, match="B07_OBSERVATION_INVALID"):
            verify_saved_artifact(envelope, reader=lambda _locator: raw)
    with pytest.raises(B07ContractError, match="B07_CCZ142_OBSERVATION_SHAPE_INVALID"):
        verify_saved_artifact(
            dict(base, result_class="SUCCESS"), reader=lambda _locator: raw
        )


def test_oversized_run_state_is_rejected_before_persistence(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "oversized-state")
    env.authority.snapshot["budget_state_ref"] = generic_ref(
        "M3_BUDGET_STATE", "x" * 9000
    )
    with pytest.raises(B07ContractError, match="B07_RUN_STATE_VALUE_INVALID"):
        env.open()
    assert env.b07.visible_counts()["b07_current_run_states"] == 0


@pytest.mark.parametrize("target_status", ["SUCCEEDED", "STOPPED"])
def test_direct_terminal_transition_without_b08_observation_is_atomic_rejection(
    tmp_path: Path, target_status: str
) -> None:
    env = build_environment(tmp_path / f"direct-{target_status.lower()}")
    opened = env.open()
    finalizing = env.b07.advance(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        operation_id="enter-finalizing-without-b08",
        expected_run_epoch=opened["run_epoch"],
        expected_state_revision=opened["state_revision"],
        target_status="ACTIVE",
        target_phase="FINALIZING",
        wait_kind=None,
        authority_reader=env.authority,
    )
    counts = env.b07.visible_counts()

    with pytest.raises(B07ContractError, match="B07_TERMINAL_OBSERVATION_REQUIRED"):
        if target_status == "SUCCEEDED":
            env.b07.advance(
                project_scope_id=env.project_scope_id,
                run_id=env.run_id,
                operation_id="direct-success",
                expected_run_epoch=finalizing["run_epoch"],
                expected_state_revision=finalizing["state_revision"],
                target_status="SUCCEEDED",
                target_phase="FINALIZING",
                wait_kind=None,
                authority_reader=env.authority,
            )
        else:
            _stop(env, finalizing, operation_id="direct-stop")

    assert env.b07.read_state(env.project_scope_id, env.run_id) == finalizing
    assert env.b07.visible_counts() == counts


@pytest.mark.parametrize(
    ("case", "error_code"),
    [
        ("NO_RECORD", "B07_TERMINAL_OBSERVATION_NOT_FOUND"),
        ("WRONG_HASH", "B07_TERMINAL_OBSERVATION_MISMATCH"),
        ("WRONG_LOCATOR", "B07_TERMINAL_OBSERVATION_NOT_FOUND"),
        ("WRONG_RUN_SCOPE", "B07_TERMINAL_OBSERVATION_SCOPE_MISMATCH"),
    ],
)
def test_terminal_transition_requires_exact_b08_record(
    tmp_path: Path, case: str, error_code: str
) -> None:
    env = build_environment(tmp_path / case.lower())
    opened = env.open()
    finalizing = env.b07.advance(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        operation_id="enter-finalizing-for-exact-b08",
        expected_run_epoch=opened["run_epoch"],
        expected_state_revision=opened["state_revision"],
        target_status="ACTIVE",
        target_phase="FINALIZING",
        wait_kind=None,
        authority_reader=env.authority,
    )
    if case == "NO_RECORD":
        observation = {
            "component_kind": TERMINAL_COMPONENT_KIND,
            "component_artifact_ref": {
                "artifact_kind": TERMINAL_ARTIFACT_KIND,
                "workspace_relative_locator": (
                    "work/ccz57_m3_b08_segment_terminal_r01/records/"
                    f"{sha256_value({'missing': case})}.json"
                ),
                "artifact_sha256": sha256_value({"missing_bytes": case}),
            },
        }
    elif case == "WRONG_RUN_SCOPE":
        other = env.b07.open_run(
            project_scope_id=env.project_scope_id,
            logical_run_key="logical-run:wrong-scope",
            run_id="run-b07-wrong-scope",
            run_kind="FACT_EXTRACTION_REPAIR",
            operation_id="open-wrong-scope",
            authority_reader=env.authority,
        )
        other = env.b07.advance(
            project_scope_id=env.project_scope_id,
            run_id=other["run_id"],
            operation_id="finalizing-wrong-scope",
            expected_run_epoch=other["run_epoch"],
            expected_state_revision=other["state_revision"],
            target_status="ACTIVE",
            target_phase="FINALIZING",
            wait_kind=None,
            authority_reader=env.authority,
        )
        observation = env.publish_terminal(
            other, marker="wrong-scope", delivery="COMPLETE"
        )["component_observation"]
    else:
        observation = deepcopy(
            env.publish_terminal(
                finalizing, marker=case.lower(), delivery="COMPLETE"
            )["component_observation"]
        )
        if case == "WRONG_HASH":
            observation["component_artifact_ref"]["artifact_sha256"] = sha256_value(
                {"wrong": "artifact hash"}
            )
        else:
            observation["component_artifact_ref"][
                "workspace_relative_locator"
            ] = (
                "work/ccz57_m3_b08_segment_terminal_r01/records/"
                f"{'0' * 64}.json"
            )

    with pytest.raises(B07ContractError, match=error_code):
        env.b07.advance(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            operation_id=f"reject-{case.lower()}",
            expected_run_epoch=finalizing["run_epoch"],
            expected_state_revision=finalizing["state_revision"],
            target_status="SUCCEEDED",
            target_phase="FINALIZING",
            wait_kind=None,
            authority_reader=env.authority,
            component_observation=observation,
        )
    assert env.b07.read_state(env.project_scope_id, env.run_id) == finalizing


def test_stop_receipt_and_stopped_state_are_one_atomic_effect(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "stop")
    state = _terminal_ready(env, env.open(), marker="stop")
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


def test_stop_rejects_authority_drift_after_terminal_binding(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "stop-authority-drift")
    ready = _terminal_ready(env, env.open(), marker="stop-authority-drift")
    env.authority.snapshot["budget_revision"] += 1
    env.authority.snapshot["budget_state_hash"] = sha256_value(
        {"budget_revision": env.authority.snapshot["budget_revision"]}
    )

    with pytest.raises(B07ContractError, match="B07_AUTHORITY_DRIFT"):
        _stop(env, ready, operation_id="stop-after-authority-drift")

    assert env.b07.read_state(env.project_scope_id, env.run_id) == ready
    assert env.b07.visible_counts()["b07_stop_receipts"] == 0


@pytest.mark.parametrize(
    "failure_point",
    ["after_stop_receipt_insert", "after_stopped_state_update", "before_stop_commit"],
)
def test_stop_failure_injection_rolls_back_receipt_and_state(
    tmp_path: Path, failure_point: str
) -> None:
    env = build_environment(tmp_path / failure_point)
    state = _terminal_ready(env, env.open(), marker=failure_point)
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
    state = _terminal_ready(env, env.open(), marker="stop-replay")
    first = _stop(env, state)
    replay = _stop(env, state)
    assert replay == first

    with pytest.raises(B07ContractError, match="B07_IDEMPOTENCY_CONFLICT"):
        _stop(env, state, reason="RETRY_LIMIT")
    assert env.b07.visible_counts()["b07_stop_receipts"] == 1


@pytest.mark.parametrize(
    ("reason", "disposition", "action_kind", "action_required"),
    [
        ("AUTHOR_ABORTED", "REOPEN_NEW_RUN", "RESTART", True),
        ("ROUTE_STOP", "DO_NOT_RESUME", "WAIT", False),
        (
            "LOCAL_STORAGE_INTEGRITY_FAILURE",
            "MAINTENANCE_REQUIRED",
            "WAIT",
            False,
        ),
    ],
)
def test_stop_receipt_controls_resume_plan_and_author_action(
    tmp_path: Path,
    reason: str,
    disposition: str,
    action_kind: str,
    action_required: bool,
) -> None:
    env = build_environment(tmp_path / reason.lower())
    ready = _terminal_ready(env, env.open(), marker=reason.lower())
    receipt = _stop(env, ready, reason=reason)
    stopped = env.b07.read_state(env.project_scope_id, env.run_id)
    plan = env.b07.derive_resume_plan(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        authority_reader=env.authority,
    )
    author = project_author_status(stopped, stop_receipt=receipt)

    assert receipt["payload"]["resume_disposition"] == disposition
    assert plan["disposition"] == disposition
    assert author["author_action_kind"] == action_kind
    assert author["author_action_required"] is action_required
    assert author["terminalization_pending"] is False


def test_missing_stop_receipt_fails_resume_plan_closed(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "missing-stop-receipt")
    ready = _terminal_ready(env, env.open(), marker="missing-stop-receipt")
    _stop(env, ready)
    with sqlite3.connect(env.b06.store._database_path) as connection:  # noqa: SLF001
        connection.execute("DELETE FROM b07_stop_receipts")
        connection.commit()

    with pytest.raises(B07ContractError, match="B07_STOP_RECEIPT_NOT_FOUND"):
        env.b07.derive_resume_plan(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            authority_reader=env.authority,
        )


def test_tampered_stop_receipt_fails_resume_plan_closed(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "tampered-stop-receipt")
    ready = _terminal_ready(env, env.open(), marker="tampered-stop-receipt")
    _stop(env, ready)
    with sqlite3.connect(env.b06.store._database_path) as connection:  # noqa: SLF001
        raw = connection.execute(
            "SELECT receipt_json FROM b07_stop_receipts"
        ).fetchone()[0]
        receipt = json.loads(bytes(raw).decode("utf-8"))
        receipt["payload"]["resume_disposition"] = "DO_NOT_RESUME"
        connection.execute(
            "UPDATE b07_stop_receipts SET receipt_json = ?",
            (json.dumps(receipt, sort_keys=True).encode("utf-8"),),
        )
        connection.commit()

    with pytest.raises(B07ContractError, match="B07_STOP_RECEIPT_INVALID"):
        env.b07.derive_resume_plan(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            authority_reader=env.authority,
        )


def test_stop_receipt_scope_mismatch_fails_closed(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "scope-stop-receipt")
    ready = _terminal_ready(env, env.open(), marker="scope-stop-receipt")
    receipt = _stop(env, ready)
    stopped = env.b07.read_state(env.project_scope_id, env.run_id)
    wrong = json.loads(json.dumps(receipt))
    wrong["payload"]["logical_run_key"] = "logical-run:wrong"
    wrong["record_id"] = f"run-stop:{sha256_value(wrong['payload'])}"
    wrong["record_hash"] = sha256_value(
        {key: value for key, value in wrong.items() if key != "record_hash"}
    )
    validate_stop_receipt(wrong)

    with pytest.raises(B07ContractError, match="B07_STOP_RECEIPT_SCOPE_MISMATCH"):
        validate_stop_receipt_for_state(stopped, wrong)
    assert record_ref(wrong) != stopped["stop_receipt_ref"]


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
    state = _terminal_ready(env, env.open(), marker="reopen")
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


def test_stop_before_b06_publish_is_rejected_without_a_half_terminal(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "stop-before-b06")
    state = env.open()
    pending, fence = env.prepare_b06(state)
    with pytest.raises(B07ContractError, match="B07_TERMINAL_SEQUENCE_INVALID"):
        _stop(env, pending, operation_id="stop-before-publish")

    committed = env.commit_b06(run_fence=fence)
    assert committed["reused_existing_commit"] is False
    assert env.b06.store.visible_counts() == {
        "candidate_versions": 2,
        "current_pointers": 1,
        "merge_receipts": 1,
    }
    assert env.b07.visible_counts()["b07_stop_receipts"] == 0


def test_b06_commit_can_win_then_existing_operation_replays_after_stop(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "b06-before-stop")
    state = env.open()
    pending, fence = env.prepare_b06(state)
    first = env.commit_b06(run_fence=fence)
    env.authority.sync_pointer(first["current_pointer"])
    reconciled = env.b07.reconcile_b06(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        operation_id="reconcile-before-stop",
        expected_run_epoch=pending["run_epoch"],
        expected_state_revision=pending["state_revision"],
        authority_reader=env.authority,
    )
    ready = _terminal_ready(env, reconciled, marker="stop-after-publish")
    _stop(env, ready, operation_id="stop-after-publish")

    replay = env.commit_b06(run_fence=fence)
    assert replay["reused_existing_commit"] is True
    assert replay["merge_receipt_ref"] == first["merge_receipt_ref"]


def test_no_b06_publication_cannot_invent_a_forced_stop(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "b06-not-published")
    state = env.open()
    pending, _fence = env.prepare_b06(state)

    with pytest.raises(B07ContractError, match="B07_TERMINAL_SEQUENCE_INVALID"):
        env.b07.reconcile_b06(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            operation_id="reconcile-no-publish",
            expected_run_epoch=pending["run_epoch"],
            expected_state_revision=pending["state_revision"],
            authority_reader=env.authority,
        )
    assert env.b07.read_state(env.project_scope_id, env.run_id) == pending
    assert env.b07.visible_counts()["b07_stop_receipts"] == 0


def test_competing_pointer_cannot_invent_a_forced_stop(tmp_path: Path) -> None:
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

    with pytest.raises(B07ContractError, match="B07_TERMINAL_SEQUENCE_INVALID"):
        env.b07.reconcile_b06(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            operation_id="reconcile-conflict",
            expected_run_epoch=pending["run_epoch"],
            expected_state_revision=pending["state_revision"],
            authority_reader=env.authority,
        )
    assert env.b07.read_state(env.project_scope_id, env.run_id) == pending
    assert env.b07.visible_counts()["b07_stop_receipts"] == 0


def test_debug_is_best_effort_and_author_payload_rejects_internal_fields(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "debug")
    state = _terminal_ready(env, env.open(), marker="debug")
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
        env.b07.read_state(env.project_scope_id, env.run_id),
        stop_receipt=receipt,
    )
    assert_author_payload_safe(author_payload)

    with pytest.raises(B07ContractError, match="B07_AUTHOR_PAYLOAD_INTERNAL_FIELD"):
        assert_author_payload_safe({"status": "stopped", "debug": {"token": 1}})


def test_debug_failure_does_not_roll_back_prior_stop(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "debug-failure")
    state = _terminal_ready(env, env.open(), marker="debug-failure")
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
    state = _terminal_ready(env, env.open(), marker="concurrent-stop")

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
    state = _terminal_ready(env, env.open(), marker="database-reopen")
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
