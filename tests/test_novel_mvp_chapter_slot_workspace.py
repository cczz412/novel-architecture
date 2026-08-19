from __future__ import annotations

import copy
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        chapter_slot_snapshot_tool,
        chapter_slot_workspace,
        plan_workspace,
    )
    from mvp.workspace import WorkspaceRouter
finally:
    sys.path.pop(0)


NOW = "2026-08-19 15:00:00"


def _plan(*, slot_ref: str = "S-0001") -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-SLOT-WORKSPACE", "volumes_enabled": False},
        "slot_sequence": [slot_ref],
        "volumes": [],
        "slots": [
            {
                "id": slot_ref,
                "goal": "让主角决定是否赴约",
                "summary": "这是作者安排的未来剧情，不是已经发生的事实",
                "entry_state": "邀请仍未答复",
                "storyline_refs": ["L-0001"],
                "scene_refs": ["SCN-0001"],
                "exit_condition": "主角作出选择",
                "exit_hook": "选择将影响下一章",
                "must_not": ["不得把规划冒充事实"],
                "risks": ["动机可能不足"],
                "target_length": 1200,
                "outline_checkpoint": {
                    "outline_rev": 3,
                    "source_slot_ref": slot_ref,
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
                "slot_ref": slot_ref,
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
                "storyline_ref": "L-0001",
                "text": "主角计划在下一章打开邀请信",
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 5,
            }
        ],
        "storylines": [
            {
                "id": "L-0001",
                "name": "赴约线",
                "alias": None,
                "priority": 1,
                "members": [],
                "line_status": "active",
                "rev": 1,
            }
        ],
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
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _plan_entry(plan: dict, *, version: int = 1, sha256: str | None = None) -> dict:
    return {
        "version": version,
        "sha256": sha256 or hashlib.sha256(_canonical_bytes(plan)).hexdigest(),
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


def _workspace_with_plan(tmp_path: Path, *, principal: str = "auth:alice"):
    runtime_root = tmp_path / principal.replace(":", "-")
    workspace = WorkspaceRouter(runtime_root).create_project(principal, "章槽项目")
    plan_workspace.save_plan(workspace, "op-plan-setup", _plan(), 0)
    return runtime_root, workspace


def test_reads_current_plan_and_calls_existing_snapshot_core_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root, workspace = _workspace_with_plan(tmp_path)
    project_dir = _project_dir(runtime_root, workspace)
    before = _tree_bytes(project_dir)
    original_execute = chapter_slot_snapshot_tool.execute
    captured: list[dict] = []

    def capture(request: dict) -> dict:
        captured.append(copy.deepcopy(request))
        return original_execute(request)

    def forbidden_commit(*args, **kwargs):
        raise AssertionError("只读适配器不得调用 workspace.commit")

    monkeypatch.setattr(chapter_slot_snapshot_tool, "execute", capture)
    monkeypatch.setattr(workspace, "commit", forbidden_commit)

    snapshot = chapter_slot_workspace.execute(workspace, "S-0001")

    assert len(captured) == 1
    current = plan_workspace.read_plan(workspace)
    assert captured[0] == {
        "plan": current["plan"],
        "slot_ref": "S-0001",
        "source_plan_version": current["version"],
        "source_plan_sha256": current["sha256"],
    }
    assert snapshot["contract"] == "CHAPTER_SLOT_SNAPSHOT"
    assert snapshot["version"] == "v1"
    assert snapshot["status"] == "plan"
    assert snapshot["slot_ref"] == "S-0001"
    assert snapshot["source_plan_version"] == current["version"] == 1
    assert snapshot["source_plan_sha256"] == current["sha256"]
    assert snapshot["basis_refs"] == {
        "slot_ref": "S-0001",
        "scene_refs": ["SCN-0001"],
        "event_refs": ["PE-0001"],
        "storyline_refs": ["L-0001"],
    }
    assert not ({"cards", "planning_card_ref", "facts", "actual"} & set(snapshot))
    assert _tree_bytes(project_dir) == before


def test_empty_plan_key_rejects_without_creating_read_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "empty"
    workspace = WorkspaceRouter(runtime_root).create_project("auth:alice", "空项目")
    project_dir = _project_dir(runtime_root, workspace)
    before = _tree_bytes(project_dir)
    monkeypatch.setattr(
        workspace,
        "commit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("只读适配器不得写")
        ),
    )

    with pytest.raises(
        chapter_slot_workspace.ChapterSlotWorkspaceError,
        match="PLAN_SNAPSHOT_NOT_FOUND",
    ):
        chapter_slot_workspace.execute(workspace, "S-0001")

    assert _tree_bytes(project_dir) == before


def test_path_masquerade_and_cross_author_guess_have_no_read_surface(
    tmp_path: Path,
) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project("auth:alice", "同名项目")
    bob = router.create_project("auth:bob", "同名项目")
    plan_workspace.save_plan(alice, "op-alice-plan", _plan(), 0)
    fake_path = tmp_path / "not-a-workspace"

    with pytest.raises(
        chapter_slot_workspace.ChapterSlotWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        chapter_slot_workspace.execute(fake_path, "S-0001")
    with pytest.raises(
        chapter_slot_workspace.ChapterSlotWorkspaceError,
        match="PLAN_SNAPSHOT_NOT_FOUND",
    ):
        chapter_slot_workspace.execute(bob, "S-0001")

    assert not fake_path.exists()
    assert list(inspect.signature(chapter_slot_workspace.execute).parameters) == [
        "workspace",
        "slot_ref",
    ]


@pytest.mark.parametrize(
    "slot_ref",
    ["S-0000", "", " S-0001"],
)
def test_missing_old_or_noncanonical_slot_ref_rejects_before_output(
    tmp_path: Path,
    slot_ref: str,
) -> None:
    _, workspace = _workspace_with_plan(tmp_path)

    with pytest.raises(
        (
            chapter_slot_workspace.ChapterSlotWorkspaceError,
            chapter_slot_snapshot_tool.ChapterSlotSnapshotError,
        )
    ):
        chapter_slot_workspace.execute(workspace, slot_ref)


@pytest.mark.parametrize("damage", ["duplicate_slot", "missing_scene", "missing_pe"])
def test_duplicate_slot_or_dangling_scene_and_pe_reject_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / damage).create_project(
        "auth:alice", "坏引用项目"
    )
    plan = _plan()
    if damage == "duplicate_slot":
        plan["slots"].append(copy.deepcopy(plan["slots"][0]))
    elif damage == "missing_scene":
        plan["slots"][0]["scene_refs"] = ["SCN-9999"]
    else:
        plan["scenes"][0]["pe_refs"] = ["PE-9999"]
    monkeypatch.setattr(plan_workspace, "read_plan", lambda handle: _plan_entry(plan))

    with pytest.raises(
        chapter_slot_snapshot_tool.ChapterSlotSnapshotError,
        match="PLAN_INVALID",
    ):
        chapter_slot_workspace.execute(workspace, "S-0001")


def test_plan_snapshot_sha_or_version_drift_rejects_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "identity").create_project(
        "auth:alice", "身份漂移"
    )
    plan = _plan()
    monkeypatch.setattr(
        plan_workspace,
        "read_plan",
        lambda handle: _plan_entry(plan, sha256="0" * 64),
    )
    with pytest.raises(
        chapter_slot_snapshot_tool.ChapterSlotSnapshotError,
        match="SOURCE_PLAN_SHA_MISMATCH",
    ):
        chapter_slot_workspace.execute(workspace, "S-0001")

    monkeypatch.setattr(
        plan_workspace,
        "read_plan",
        lambda handle: _plan_entry(plan, version=0),
    )
    with pytest.raises(
        chapter_slot_workspace.ChapterSlotWorkspaceError,
        match="PLAN_SNAPSHOT_VERSION_INVALID",
    ):
        chapter_slot_workspace.execute(workspace, "S-0001")


def test_reopened_process_reads_the_same_current_snapshot_without_writes(
    tmp_path: Path,
) -> None:
    runtime_root, workspace = _workspace_with_plan(tmp_path)
    project_dir = _project_dir(runtime_root, workspace)
    before = _tree_bytes(project_dir)
    expected = chapter_slot_workspace.execute(workspace, "S-0001")
    child = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from mvp.chapter_slot_workspace import execute
from mvp.workspace import WorkspaceRouter
workspace = WorkspaceRouter(sys.argv[2]).open_project(sys.argv[3], sys.argv[4])
value = execute(workspace, sys.argv[5])
sys.stdout.buffer.write((json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\\n").encode("utf-8"))
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
            "S-0001",
        ],
        capture_output=True,
        check=True,
    )

    assert reopened.stdout == _canonical_bytes(expected)
    assert _tree_bytes(project_dir) == before
