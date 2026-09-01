"""Focused B-06 atomicity, replay, concurrency, and boundary checks."""

from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from b06_contracts import B06ContractError, validate_merge_receipt
from b06_store import (
    B06CommitService,
    B06CommitStore,
    B06TransactionReadView,
    RunFenceReader,
)
from work.ccz57_m3_b06_commit_core_r01.fixtures import (
    B06FixtureEnvironment,
    COMMITTED_AT,
    build_environment,
)

ROOT = Path(__file__).resolve().parent


def _run_fence(env: B06FixtureEnvironment, *, revision: int = 7) -> dict[str, Any]:
    return {
        "project_scope_id": env.live_pointer["project_scope_id"],
        "run_id": "run-b07-fixture",
        "expected_run_epoch": 2,
        "expected_state_revision": revision,
    }


def _install_run_state(
    env: B06FixtureEnvironment, *, status: str = "B06_OUTCOME_PENDING"
) -> None:
    with sqlite3.connect(env.store._database_path) as connection:  # noqa: SLF001
        connection.execute(
            "CREATE TABLE b07_current_run_states ("
            "project_scope_id TEXT NOT NULL, run_id TEXT PRIMARY KEY, "
            "run_epoch INTEGER NOT NULL, state_revision INTEGER NOT NULL, "
            "status TEXT NOT NULL, pending_operation_id TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO b07_current_run_states VALUES (?, ?, ?, ?, ?, ?)",
            (
                env.live_pointer["project_scope_id"],
                "run-b07-fixture",
                2,
                7,
                status,
                "b06-operation-1",
            ),
        )


def _trusted_run_fence_reader(seen: list[dict[str, Any]]) -> RunFenceReader:
    def reader(view: B06TransactionReadView, context: dict[str, Any]) -> None:
        fence = context["run_fence"]
        row = view.fetchone(
            "SELECT project_scope_id, run_epoch, state_revision, status, "
            "pending_operation_id FROM b07_current_run_states WHERE run_id = ?",
            (fence["run_id"],),
        )
        if row != (
            fence["project_scope_id"],
            fence["expected_run_epoch"],
            fence["expected_state_revision"],
            "B06_OUTCOME_PENDING",
            context["operation_id"],
        ):
            raise B06ContractError("B06_RUN_FENCE_STALE")
        seen.append(deepcopy(context))

    return reader


def _enable_run_fence(env: B06FixtureEnvironment, reader: RunFenceReader) -> None:
    env.service = B06CommitService(
        store=env.store,
        b05_store=env.b05.store,
        freshness_reader=env.freshness_reader,
        run_fence_reader=reader,
        reference_records=env.reference_records,
    )


def test_allowed_replace_commits_child_pointer_and_receipt(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "replace")
    result = env.commit()

    child = env.store.read_candidate(result["child_candidate_version_ref"])
    receipt = env.store.read_receipts()[0]
    validate_merge_receipt(receipt)
    assert (
        child["payload"]["parent_candidate_version_ref"]
        == receipt["payload"]["base_candidate_version_ref"]
    )
    assert result["current_pointer"]["generation"] == 2
    assert (
        result["current_pointer"]["current_candidate_version_ref"]
        == result["child_candidate_version_ref"]
    )
    assert env.store.visible_counts() == {
        "candidate_versions": 2,
        "current_pointers": 1,
        "merge_receipts": 1,
    }


def test_allowed_add_uses_same_kernel_and_exact_trial_hash(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "add", mode="add")
    result = env.commit()
    child = env.store.read_candidate(result["child_candidate_version_ref"])
    receipt = env.store.read_receipts()[0]
    route = env.b05.store.record_by_ref(env.route_receipt_ref)
    pvr = env.b05.store.record_by_ref(route["payload"]["validation_receipt_ref"])
    proof = next(
        item
        for item in pvr["payload"]["route_unit_proofs"]
        if item["route_unit_id"] == env.route_unit_id
    )

    assert (
        len(child["payload"]["items"])
        == len(env.base_candidate["payload"]["items"]) + 1
    )
    assert (
        receipt["payload"]["canonical_apply_result_hash"]
        == proof["canonical_apply_result_hash"]
    )


def test_same_operation_replays_without_second_write(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "replay")
    first = env.commit()
    before = env.store.write_attempt_count()
    replay = env.commit()

    assert replay["merge_receipt_ref"] == first["merge_receipt_ref"]
    assert replay["reused_existing_commit"] is True
    assert env.store.write_attempt_count() == before
    assert env.store.visible_counts()["merge_receipts"] == 1


def test_same_operation_with_different_input_is_rejected(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "operation-conflict")
    env.commit()
    with pytest.raises(B06ContractError, match="B06_OPERATION_ID_INPUT_CONFLICT"):
        env.commit(committed_at="2026-08-31T23:00:01Z")


def test_run_fence_reads_inside_publish_transaction(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "run-fence-pass")
    _install_run_state(env)
    seen: list[dict[str, Any]] = []
    _enable_run_fence(env, _trusted_run_fence_reader(seen))

    result = env.commit(run_fence=_run_fence(env))

    assert len(seen) == 1
    assert seen[0]["operation_id"] == "b06-operation-1"
    assert seen[0]["request_hash"] == result["request_hash"]
    assert env.store.visible_counts()["merge_receipts"] == 1


def test_stopped_run_fence_rejects_new_publish_with_zero_writes(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "run-fence-stop")
    _install_run_state(env, status="STOPPED")
    _enable_run_fence(env, _trusted_run_fence_reader([]))
    before_pointer = env.store.read_pointer(env.live_pointer["logical_pointer_key"])

    with pytest.raises(B06ContractError, match="B06_RUN_FENCE_STALE"):
        env.commit(run_fence=_run_fence(env))

    assert (
        env.store.read_pointer(env.live_pointer["logical_pointer_key"])
        == before_pointer
    )
    assert env.store.visible_counts() == {
        "candidate_versions": 1,
        "current_pointers": 1,
        "merge_receipts": 0,
    }
    assert env.store.write_attempt_count() == 0


def test_existing_operation_replay_skips_fence_after_stop(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "run-fence-replay")
    _install_run_state(env)
    seen: list[dict[str, Any]] = []
    _enable_run_fence(env, _trusted_run_fence_reader(seen))
    first = env.commit(run_fence=_run_fence(env))
    with sqlite3.connect(env.store._database_path) as connection:  # noqa: SLF001
        connection.execute(
            "UPDATE b07_current_run_states SET status = 'STOPPED', state_revision = 8"
        )

    replay = env.commit(run_fence=_run_fence(env))

    assert replay["merge_receipt_ref"] == first["merge_receipt_ref"]
    assert replay["reused_existing_commit"] is True
    assert len(seen) == 1


def test_run_fence_read_view_rejects_write_query(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "run-fence-read-only")

    def write_reader(view: B06TransactionReadView, _context: dict[str, Any]) -> None:
        view.fetchone("UPDATE current_pointers SET project_scope_id = 'tampered'")

    _enable_run_fence(env, write_reader)
    with pytest.raises(B06ContractError, match="B06_RUN_FENCE_QUERY_NOT_READ_ONLY"):
        env.commit(run_fence=_run_fence(env))
    assert env.store.visible_counts()["merge_receipts"] == 0


def test_same_operation_cannot_swap_run_fence_identity(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "run-fence-identity")
    _install_run_state(env)
    _enable_run_fence(env, _trusted_run_fence_reader([]))
    env.commit(run_fence=_run_fence(env))

    with pytest.raises(B06ContractError, match="B06_OPERATION_ID_INPUT_CONFLICT"):
        env.commit(run_fence=_run_fence(env, revision=8))


def test_run_fence_reader_and_assertion_must_be_installed_together(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "run-fence-configuration")
    with pytest.raises(B06ContractError, match="B06_RUN_FENCE_CONFIGURATION_INVALID"):
        env.commit(run_fence=_run_fence(env))

    _enable_run_fence(env, _trusted_run_fence_reader([]))
    with pytest.raises(B06ContractError, match="B06_RUN_FENCE_CONFIGURATION_INVALID"):
        env.commit()


def test_reopen_reads_same_pointer_child_and_receipt(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "reopen")
    first = env.commit()
    env.reopen()

    assert (
        env.store.read_pointer(env.live_pointer["logical_pointer_key"])
        == first["current_pointer"]
    )
    assert env.store.read_candidate(first["child_candidate_version_ref"])
    assert len(env.store.read_receipts()) == 1


@pytest.mark.parametrize(
    "failure_point",
    [
        "after_child_insert",
        "after_pointer_cas",
        "after_receipt_insert",
        "before_commit",
    ],
)
def test_failure_injection_rolls_back_all_three(
    tmp_path: Path, failure_point: str
) -> None:
    env = build_environment(tmp_path / failure_point, failure_point=failure_point)
    before_pointer = env.store.read_pointer(env.live_pointer["logical_pointer_key"])
    with pytest.raises(B06ContractError, match="B06_SIMULATED_TRANSACTION_FAILURE"):
        env.commit()

    assert (
        env.store.read_pointer(env.live_pointer["logical_pointer_key"])
        == before_pointer
    )
    assert env.store.visible_counts() == {
        "candidate_versions": 1,
        "current_pointers": 1,
        "merge_receipts": 0,
    }
    assert env.store.write_attempt_count() == 0


def test_old_route_cannot_commit_again_after_pointer_moves(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "stale-route")
    env.commit("winner")
    with pytest.raises(B06ContractError, match="B06_ROUTE_INPUT_BINDING_MISMATCH"):
        env.commit("loser", committed_at="2026-08-31T23:00:01Z")
    assert env.store.visible_counts()["merge_receipts"] == 1


@pytest.mark.parametrize(
    ("b05_kwargs", "expected"),
    [
        ({"closed_gate": True}, "B05_B06_ROUTE_DENIED"),
        ({"semantic_unknown_groups": ["replace-a"]}, "B05_B06_ROUTE_DENIED"),
    ],
)
def test_non_allow_routes_never_write(
    tmp_path: Path, b05_kwargs: dict, expected: str
) -> None:
    env = build_environment(tmp_path / expected, b05_kwargs=b05_kwargs)
    with pytest.raises(B06ContractError, match=expected):
        env.commit()
    assert env.store.visible_counts()["merge_receipts"] == 0


def test_tampered_patch_and_protection_fail_before_write(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "tampered")
    patch = deepcopy(env.b05.patch)
    patch["payload"]["atomic_groups"][0]["purpose"] = "tampered"
    with pytest.raises(B06ContractError, match="B06_PATCH_CLOSURE_INVALID"):
        env.commit(patch_proposal=patch)
    assert env.store.write_attempt_count() == 0


def test_direct_store_call_cannot_bypass_unique_committer(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "publisher-scope")
    with pytest.raises(B06ContractError, match="B06_PUBLISHER_SCOPE_ESCAPE"):
        env.store.commit_atomic(
            project_scope_id=env.live_pointer["project_scope_id"],
            logical_pointer_key=env.live_pointer["logical_pointer_key"],
            operation_id="bypass",
            request_hash="0" * 64,
            builder=lambda pointer, candidate: (candidate, pointer, {}),
        )
    assert env.store.write_attempt_count() == 0


def test_authority_drift_between_reads_rolls_back(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "authority-drift")
    env.freshness_reader.drift_on_read = 2
    with pytest.raises(B06ContractError, match="B06_AUTHORITY_SNAPSHOT_DRIFT"):
        env.commit()
    assert env.store.visible_counts()["merge_receipts"] == 0


def test_two_concurrent_operations_only_one_can_move_pointer(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "concurrent")

    def run(operation_id: str) -> str:
        try:
            env.commit(operation_id, committed_at=COMMITTED_AT)
        except B06ContractError as error:
            return error.code
        return "COMMITTED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(run, ["concurrent-a", "concurrent-b"]))
    assert results.count("COMMITTED") == 1
    assert results.count("B06_ROUTE_INPUT_BINDING_MISMATCH") == 1
    assert env.store.visible_counts()["merge_receipts"] == 1


def test_schema_has_no_commit_intent_or_pointer_snapshot_table(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "schema")
    names = env.store.schema_objects()
    assert "commit_intents" not in names
    assert "pointer_snapshots" not in names
    assert names == [
        "candidate_versions",
        "current_pointers",
        "merge_receipts",
        "metadata",
    ]


def test_b06_has_no_model_network_or_subprocess_imports() -> None:
    forbidden_modules = {"requests", "httpx", "openai", "anthropic", "subprocess"}
    for name in ("b06_contracts.py", "b06_store.py"):
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


def test_sqlite_contains_no_partial_rows_after_database_reopen(tmp_path: Path) -> None:
    env = build_environment(
        tmp_path / "sqlite-reopen", failure_point="after_pointer_cas"
    )
    with pytest.raises(B06ContractError):
        env.commit()
    reopened = B06CommitStore(env.root / "b06")
    assert reopened.visible_counts()["merge_receipts"] == 0
    with sqlite3.connect(reopened._database_path) as connection:  # noqa: SLF001
        assert (
            connection.execute("SELECT COUNT(*) FROM candidate_versions").fetchone()[0]
            == 1
        )
