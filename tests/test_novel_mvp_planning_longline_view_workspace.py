from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        plan_workspace,
        planning_longline_view_workspace,
    )
    from mvp.workspace import ProjectNotFoundError, WorkspaceRouter
finally:
    sys.path.pop(0)


NOW = "2026-08-20 15:00:00"


def _common(object_id: str) -> dict:
    return {
        "id": object_id,
        "source_identity": "author_declared",
        "created_at": NOW,
        "updated_at": NOW,
        "rev": 1,
        "note": "",
    }


def _plan() -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-WORKSPACE", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "scene_refs": ["SCN-0001"],
                "storyline_refs": ["L-0001"],
            }
        ],
        "scenes": [
            {"id": "SCN-0001", "slot_ref": "S-0001", "pe_refs": ["PE-0001"]}
        ],
        "events": [
            {
                "id": "PE-0001",
                "scene_ref": "SCN-0001",
                "storyline_ref": "L-0001",
                "hook_links": [{"hook_ref": "H-0001", "role": "payoff"}],
            }
        ],
        "storylines": [
            {
                **_common("L-0001"),
                "name": "送信线",
                "alias": None,
                "priority": 1,
                "members": ["CH-001"],
                "line_status": "active",
                "last_scene_ref": "SCN-0001",
            }
        ],
        "hooks": [
            {
                **_common("H-0001"),
                "content": "主角已经安排在后续拒绝密封信",
                "plant_refs": [{"ref": "PE-0001", "note": "信件已经进入计划"}],
                "payoff_slot_ref": "S-0001",
                "hook_status": "paid",
                "paid_by_ref": "PE-0001",
                "defer_count": 0,
                "revealed": True,
                "revealed_at": "SCN-0001",
                "safety_summary": "拒信已经安排，但尚未实际写成。",
                "truth_bearing": "primary",
            }
        ],
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
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _entry(plan: dict, version: int) -> dict:
    return {
        "version": version,
        "sha256": hashlib.sha256(_canonical_bytes(plan)).hexdigest(),
        "plan": copy.deepcopy(plan),
    }


def _project_dir(runtime_root: Path, workspace) -> Path:
    return (
        runtime_root
        / "authors"
        / workspace.author_id
        / "projects"
        / workspace.project_id
    )


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_bound_workspace_double_reads_current_plan_and_never_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project("auth:alice", "长线项目")
    plan_workspace.save_plan(workspace, "op-plan", _plan(), 0)
    project_dir = _project_dir(runtime_root, workspace)
    before = _tree_bytes(project_dir)
    real_read = plan_workspace.read_plan
    calls = 0

    def counted_read(handle):
        nonlocal calls
        calls += 1
        return real_read(handle)

    monkeypatch.setattr(plan_workspace, "read_plan", counted_read)
    monkeypatch.setattr(
        workspace,
        "commit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("长线视图不得写工作区")
        ),
    )

    result = planning_longline_view_workspace.execute(workspace)

    assert calls == 2
    assert result["source_plan_version"] == 1
    assert result["storylines"][0]["id"] == "L-0001"
    assert result["hooks"][0]["hook_status"] == "paid"
    assert _tree_bytes(project_dir) == before


def test_source_change_between_reads_rejects_and_keeps_workspace_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "race"
    workspace = WorkspaceRouter(runtime_root).create_project("auth:alice", "竞态项目")
    project_dir = _project_dir(runtime_root, workspace)
    before = _tree_bytes(project_dir)
    first = _plan()
    second = _plan()
    second["storylines"][0]["name"] = "读取期间已经改名"
    entries = [_entry(first, 1), _entry(second, 2)]

    monkeypatch.setattr(
        plan_workspace,
        "read_plan",
        lambda handle: copy.deepcopy(entries.pop(0)),
    )
    monkeypatch.setattr(
        workspace,
        "commit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("来源变化时不得写工作区")
        ),
    )

    with pytest.raises(
        planning_longline_view_workspace.PlanningLonglineViewWorkspaceError,
        match="PLAN_SOURCE_CHANGED_DURING_READ",
    ):
        planning_longline_view_workspace.execute(workspace)

    assert entries == []
    assert _tree_bytes(project_dir) == before


def test_missing_bad_plan_path_and_cross_author_guess_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "isolation"
    router = WorkspaceRouter(runtime_root)
    alice = router.create_project("auth:alice", "Alice 长线")
    bob = router.create_project("auth:bob", "Bob 长线")
    plan_workspace.save_plan(alice, "op-alice", _plan(), 0)
    fake_path = tmp_path / "not-a-workspace"

    with pytest.raises(
        planning_longline_view_workspace.PlanningLonglineViewWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        planning_longline_view_workspace.execute(fake_path)
    with pytest.raises(
        planning_longline_view_workspace.PlanningLonglineViewWorkspaceError,
        match="CURRENT_PLAN_NOT_FOUND",
    ):
        planning_longline_view_workspace.execute(bob)
    with pytest.raises(ProjectNotFoundError):
        router.open_project("auth:bob", alice.project_id)
    assert not fake_path.exists()

    bad = _plan()
    bad["volumes"] = [{"id": "VOL-0001"}]
    monkeypatch.setattr(
        plan_workspace,
        "read_plan",
        lambda handle: _entry(bad, 1),
    )
    with pytest.raises(
        planning_longline_view_workspace.PlanningLonglineViewWorkspaceError,
        match="CURRENT_PLAN_REJECTED:first:VOLUMES_NOT_SUPPORTED",
    ):
        planning_longline_view_workspace.execute(alice)


def test_new_process_reopen_returns_same_bytes_without_workspace_change(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "restart"
    workspace = WorkspaceRouter(runtime_root).create_project("auth:alice", "重启项目")
    plan_workspace.save_plan(workspace, "op-plan", _plan(), 0)
    project_dir = _project_dir(runtime_root, workspace)
    before = _tree_bytes(project_dir)
    expected = planning_longline_view_workspace.execute(workspace)
    child = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from mvp.planning_longline_view_workspace import execute
from mvp.workspace import WorkspaceRouter
workspace = WorkspaceRouter(sys.argv[2]).open_project(sys.argv[3], sys.argv[4])
value = execute(workspace)
sys.stdout.buffer.write((json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(\",\", \":\")) + \"\\n\").encode(\"utf-8\"))
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

    assert reopened.stdout == _canonical_bytes(expected)
    assert _tree_bytes(project_dir) == before
