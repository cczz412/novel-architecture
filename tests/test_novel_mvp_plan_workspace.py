from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import plan_workspace, planstore
    from mvp.workspace import (
        InjectedWorkspaceCrash,
        OperationConflictError,
        ProjectNotFoundError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


NOW = "2026-08-19 10:00:00"


def _plan() -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-SYNTHETIC", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "goal": "让主角决定是否赴约",
                "summary": "这是作者的未来规划，不是已发生事实",
                "entry_state": "邀请仍未答复",
                "storyline_refs": [],
                "scene_refs": ["SCN-0001"],
                "exit_condition": "主角作出选择",
                "exit_hook": "选择会影响下一章",
                "must_not": ["不得把规划冒充事实"],
                "risks": [],
                "target_length": 1200,
                "outline_checkpoint": {
                    "outline_rev": 3,
                    "source_slot_ref": "S-0001",
                    "source_commit_seq": 8,
                },
                "slot_status": "planned",
                "handover_parts": [],
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 2,
            }
        ],
        "scenes": [
            {
                "id": "SCN-0001",
                "slot_ref": "S-0001",
                "goal": "收到邀请",
                "summary": "主角看见邀请信",
                "pe_refs": ["PE-0001"],
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 4,
            }
        ],
        "events": [
            {
                "id": "PE-0001",
                "scene_ref": "SCN-0001",
                "text": "主角计划在下一章打开邀请信",
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 5,
            }
        ],
        "storylines": [],
        "hooks": [],
        "widgets": [],
        "pins": [],
        "must_carries": [],
        "option_records": [],
        "slot_mappings": [],
        "reconciliation_edges": [],
        "stop_points": {},
        "id_counters": {"MAP": 0, "RE": 0},
    }


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _project_dir(runtime_root: Path, workspace) -> Path:
    return (
        runtime_root
        / "authors"
        / workspace.author_id
        / "projects"
        / workspace.project_id
    )


def test_empty_project_read_returns_none_without_creating_read_state(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project("auth:alice", "空项目")
    project_dir = _project_dir(runtime_root, workspace)
    before = sorted(path.relative_to(project_dir) for path in project_dir.rglob("*"))

    assert plan_workspace.read_plan(workspace) is None

    after = sorted(path.relative_to(project_dir) for path in project_dir.rglob("*"))
    assert after == before


def test_save_and_new_process_open_project_read_byte_equivalent_plan(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project("auth:alice", "计划项目")
    plan = _plan()

    receipt = plan_workspace.save_plan(workspace, "op-plan-001", plan, 0)

    assert receipt["status"] == "COMMITTED"
    assert receipt["versions"] == {"plan": 1}
    child = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from mvp.plan_workspace import read_plan
from mvp.workspace import WorkspaceRouter
workspace = WorkspaceRouter(sys.argv[2]).open_project(sys.argv[3], sys.argv[4])
value = read_plan(workspace)
sys.stdout.buffer.write(json.dumps(value[\"plan\"], ensure_ascii=False, sort_keys=True, separators=(\",\", \":\")).encode(\"utf-8\"))
"""
    reopened = subprocess.run(
        [
            sys.executable,
            "-c",
            child,
            str(PRODUCT_ROOT),
            str(runtime_root),
            "auth:alice",
            workspace.project_id,
        ],
        capture_output=True,
        check=True,
    )

    assert reopened.stdout == _canonical_bytes(plan)
    loaded = plan_workspace.read_plan(workspace)
    assert loaded["plan"]["slots"][0]["outline_checkpoint"]["outline_rev"] == 3
    assert loaded["plan"]["slots"][0]["rev"] == 2
    assert loaded["plan"]["events"][0]["rev"] == 5
    assert loaded["plan"]["slots"][0]["truth_bearing"] == "primary"
    assert not ({"facts", "actual", "actuality"} & set(loaded["plan"]))


def test_bad_plan_has_zero_visible_write(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "auth:alice", "坏对象"
    )
    bad = _plan()
    bad["actuality"] = "happened"

    with pytest.raises(planstore.PlanstoreError, match="PLAN_MUST_NOT_CONTAIN_TRUTH_FIELDS"):
        plan_workspace.save_plan(workspace, "op-bad-plan", bad, 0)

    assert plan_workspace.read_plan(workspace) is None


def test_same_operation_is_idempotent_and_different_request_conflicts(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "auth:alice", "幂等项目"
    )
    plan = _plan()

    first = plan_workspace.save_plan(workspace, "op-idempotent", plan, 0)
    replay = plan_workspace.save_plan(workspace, "op-idempotent", plan, 0)

    assert first["generation_id"] == replay["generation_id"]
    assert replay["replayed"] is True
    assert plan_workspace.read_plan(workspace)["version"] == 1

    changed = copy.deepcopy(plan)
    changed["slots"][0]["summary"] = "另一份仍合法的规划"
    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        plan_workspace.save_plan(workspace, "op-idempotent", changed, 0)
    assert plan_workspace.read_plan(workspace)["plan"] == plan


def test_version_conflict_keeps_previous_plan_visible(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "auth:alice", "版本项目"
    )
    original = _plan()
    plan_workspace.save_plan(workspace, "op-version-1", original, 0)
    changed = copy.deepcopy(original)
    changed["slots"][0]["rev"] = 3
    changed["slots"][0]["summary"] = "并发写入候选"

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        plan_workspace.save_plan(workspace, "op-version-stale", changed, 0)

    loaded = plan_workspace.read_plan(workspace)
    assert loaded["version"] == 1
    assert loaded["plan"] == original


@pytest.mark.parametrize(
    ("fault_point", "recovery_status", "visible"),
    [
        ("after_prepare", "ROLLED_BACK", False),
        ("after_pointer_swap", "COMMIT_COMPLETED", True),
    ],
)
def test_crash_recovery_exposes_whole_plan_or_no_plan(
    tmp_path: Path,
    fault_point: str,
    recovery_status: str,
    visible: bool,
) -> None:
    runtime_root = tmp_path / fault_point
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project("auth:alice", "恢复项目")
    plan = _plan()

    def crash(point: str) -> None:
        if point == fault_point:
            raise InjectedWorkspaceCrash(point)

    router._set_failure_hook_for_testing(crash)
    with pytest.raises(InjectedWorkspaceCrash, match=fault_point):
        plan_workspace.save_plan(workspace, f"op-{fault_point}", plan, 0)
    router._set_failure_hook_for_testing(None)

    recovery = workspace.recover()
    assert recovery["status"] == recovery_status
    restarted = WorkspaceRouter(runtime_root).open_project(
        "auth:alice", workspace.project_id
    )
    loaded = plan_workspace.read_plan(restarted)
    assert (loaded is not None) is visible
    if visible:
        assert loaded["plan"] == plan


def test_cross_author_guess_matches_missing_project_and_has_no_search_surface(
    tmp_path: Path,
) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project("auth:alice", "同名项目")
    bob = router.create_project("auth:bob", "同名项目")
    plan_workspace.save_plan(alice, "op-alice-plan", _plan(), 0)

    assert plan_workspace.read_plan(bob) is None
    with pytest.raises(ProjectNotFoundError) as guessed:
        router.open_project("auth:bob", alice.project_id)
    with pytest.raises(ProjectNotFoundError) as absent:
        router.open_project("auth:bob", "p_" + "f" * 32)

    assert guessed.value.code == absent.value.code == "PROJECT_NOT_FOUND"
    assert not hasattr(alice, "open_path")
    assert not hasattr(alice, "glob")
    assert not hasattr(router, "search_projects")
