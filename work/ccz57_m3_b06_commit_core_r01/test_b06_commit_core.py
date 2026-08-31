"""Focused B-06 atomicity, replay, concurrency, and boundary checks."""

from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

import pytest

from b06_contracts import B06ContractError, validate_merge_receipt
from b06_store import B06CommitStore
from work.ccz57_m3_b06_commit_core_r01.fixtures import (
    COMMITTED_AT,
    build_environment,
)

ROOT = Path(__file__).resolve().parent


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
