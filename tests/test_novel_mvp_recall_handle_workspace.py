from __future__ import annotations

import copy
import inspect
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import packer_tool, packer_workspace, recall_handle_workspace
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


def _material(handle: str) -> dict:
    return {
        "id": "MAY-01",
        "estimated_tokens": 20,
        "actuality_class": "CURRENT_FACT_OR_STATE",
        "obligation_tier": "MAY",
        "selection_rank": 1,
        "task_relation": "与当前合成任务相关",
        "recall_disposition": "RETRIEVABLE",
        "recall_handle": handle,
        "unresolved_reason": None,
    }


def _request(handle: str) -> dict:
    material = _material(handle)
    return {
        "task_id": "M11-RECALL-SYNTHETIC",
        "task_actuality_scope": "CURRENT_TRUTH_REQUIRED",
        "budget_tokens": 10,
        "token_estimator": {
            "identity": packer_tool.ESTIMATOR_IDENTITY,
            "estimates": {material["id"]: material["estimated_tokens"]},
        },
        "candidate_materials": [material],
    }


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


def test_packer_requires_current_handle_and_author_text_hides_it(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "M11"
    )
    binding = _binding(workspace, _source(workspace))
    recall_handle_workspace.register_bindings(
        workspace,
        operation_id="op-register",
        bindings=[binding],
        expected_registry_version=0,
    )
    request = _request(binding["handle"])

    result = packer_workspace.execute(workspace, request)
    assert result == packer_tool.execute(copy.deepcopy(request))
    assert packer_workspace.resolve_for_machine(workspace, binding["handle"]) == binding
    author_text = packer_tool.render_author_safe(result)
    assert binding["handle"] not in author_text
    assert "MAY-01" not in author_text
    assert "已阻断 1 条" in author_text

    with pytest.raises(
        packer_workspace.PackerWorkspaceError,
        match="M11_RECALL_HANDLE_NOT_FOUND",
    ):
        packer_workspace.execute(workspace, _request(MISSING_HANDLE))


def test_source_change_during_pack_rejects_without_rewriting_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    registry_before = workspace.read("recall_handles")
    real_execute = packer_tool.execute

    def execute_and_advance(request: dict) -> dict:
        result = real_execute(request)
        current = workspace.read("state")
        workspace.commit(
            "op-state-race",
            {"state": current["payload"]},
            {"state": current["version"]},
        )
        return result

    monkeypatch.setattr(packer_tool, "execute", execute_and_advance)
    with pytest.raises(
        packer_workspace.PackerWorkspaceError,
        match="M11_RECALL_HANDLE_STALE",
    ):
        packer_workspace.execute(workspace, _request(binding["handle"]))
    assert workspace.read("recall_handles") == registry_before


def test_public_entrypoints_require_bound_workspace_not_paths(tmp_path: Path) -> None:
    with pytest.raises(
        recall_handle_workspace.RecallHandleWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        recall_handle_workspace.resolve_handle(
            Path("/tmp/not-a-workspace"), MISSING_HANDLE
        )
    with pytest.raises(
        packer_workspace.PackerWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        packer_workspace.execute(
            Path("/tmp/not-a-workspace"), _request(MISSING_HANDLE)
        )
    assert list(inspect.signature(packer_workspace.execute).parameters) == [
        "workspace",
        "request",
    ]
