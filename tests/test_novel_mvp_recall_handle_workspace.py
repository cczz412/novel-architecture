# PR-D 临时收窄版：原版冻结在 cc793c4 的同一路径。
# PR-E4 带入 packer_tool／packer_workspace 后，必须用 cc793c4 原版
# 逐字节还原本文件。
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import recall_handle_workspace
    from mvp.workspace import (
        OperationConflictError,
        ProjectNotFoundError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


MISSING_HANDLE = "rh_00000000000000000000000000000000"


def _source(workspace, *, operation_id: str = "op-source") -> dict:
    workspace.commit(
        operation_id,
        {"state": {"items": [{"id": "state-01", "text": "合成状态"}]}},
        {"state": 0},
    )
    return workspace.read("state")


def _binding(workspace, state: dict, *, object_ref: str = "state-01") -> dict:
    return recall_handle_workspace.build_binding(
        workspace,
        source_owner="state_owner",
        source_ref={
            "logical_key": "state",
            "object_ref": object_ref,
            "version": state["version"],
            "sha256": state["sha256"],
        },
    )


def test_register_resolve_restart_and_idempotent_replay(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime).create_project("principal-a", "M11")
    binding = _binding(workspace, _source(workspace))

    first = recall_handle_workspace.register_bindings(
        workspace,
        operation_id="op-register-handle",
        bindings=[binding],
        expected_registry_version=0,
    )
    replay = recall_handle_workspace.register_bindings(
        workspace,
        operation_id="op-register-handle",
        bindings=[copy.deepcopy(binding)],
        expected_registry_version=0,
    )
    reopened = WorkspaceRouter(runtime).open_project(
        "principal-a", workspace.project_id
    )

    assert first["status"] == "COMMITTED"
    assert replay["replayed"] is True
    assert replay["generation_id"] == first["generation_id"]
    assert recall_handle_workspace.resolve_handle(reopened, binding["handle"]) == binding
    assert recall_handle_workspace.read_registry(reopened)["bindings"] == [binding]
    assert set(recall_handle_workspace.resolve_handle(reopened, binding["handle"])) == {
        "handle",
        "source_owner",
        "source_ref",
    }
    assert "payload" not in recall_handle_workspace.resolve_handle(
        reopened, binding["handle"]
    )


def test_old_registration_replays_after_later_registration(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "M11"
    )
    source = _source(workspace)
    first_binding = _binding(workspace, source)
    first = recall_handle_workspace.register_bindings(
        workspace,
        operation_id="op-register-first",
        bindings=[first_binding],
        expected_registry_version=0,
    )
    second_binding = _binding(workspace, source, object_ref="state-02")
    recall_handle_workspace.register_bindings(
        workspace,
        operation_id="op-register-second",
        bindings=[second_binding],
        expected_registry_version=1,
    )

    replay = recall_handle_workspace.register_bindings(
        workspace,
        operation_id="op-register-first",
        bindings=[copy.deepcopy(first_binding)],
        expected_registry_version=0,
    )

    assert replay["replayed"] is True
    assert replay["generation_id"] == first["generation_id"]
    assert recall_handle_workspace.read_registry(workspace)["bindings"] == sorted(
        [first_binding, second_binding], key=lambda row: row["handle"]
    )


def test_missing_stale_and_cross_author_fail_closed(tmp_path: Path) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project("principal-a", "同名项目")
    bob = router.create_project("principal-b", "同名项目")
    source = _source(alice)
    binding = _binding(alice, source)
    recall_handle_workspace.register_bindings(
        alice,
        operation_id="op-register-alice",
        bindings=[binding],
        expected_registry_version=0,
    )

    with pytest.raises(
        recall_handle_workspace.RecallHandleNotFoundError,
        match="RECALL_HANDLE_NOT_FOUND",
    ):
        recall_handle_workspace.resolve_handle(alice, MISSING_HANDLE)
    with pytest.raises(
        recall_handle_workspace.RecallHandleNotFoundError,
        match="RECALL_HANDLE_NOT_FOUND",
    ):
        recall_handle_workspace.resolve_handle(bob, binding["handle"])
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("principal-b", alice.project_id)

    alice.commit(
        "op-state-v2",
        {"state": source["payload"]},
        {"state": source["version"]},
    )
    with pytest.raises(
        recall_handle_workspace.RecallHandleStaleError,
        match="RECALL_HANDLE_STALE",
    ):
        recall_handle_workspace.resolve_handle(alice, binding["handle"])


def test_failed_rebind_bad_version_and_operation_conflict_are_zero_write(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "M11"
    )
    source = _source(workspace)
    binding = _binding(workspace, source)
    recall_handle_workspace.register_bindings(
        workspace,
        operation_id="op-register",
        bindings=[binding],
        expected_registry_version=0,
    )
    before = workspace.read("recall_handles")

    changed = copy.deepcopy(binding)
    changed["source_ref"]["object_ref"] = "state-02"
    with pytest.raises(
        recall_handle_workspace.RecallHandleWorkspaceError,
        match="RECALL_HANDLE_NOT_MINTED_FOR_SOURCE",
    ):
        recall_handle_workspace.register_bindings(
            workspace,
            operation_id="op-rebind",
            bindings=[changed],
            expected_registry_version=1,
        )
    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        recall_handle_workspace.register_bindings(
            workspace,
            operation_id="op-stale-version",
            bindings=[_binding(workspace, source, object_ref="state-02")],
            expected_registry_version=0,
        )
    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        recall_handle_workspace.register_bindings(
            workspace,
            operation_id="op-register",
            bindings=[_binding(workspace, source, object_ref="state-03")],
            expected_registry_version=0,
        )
    assert workspace.read("recall_handles") == before
