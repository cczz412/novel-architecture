from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        plan_workspace,
        planning_longline_reader_workspace,
        planning_longline_view_workspace,
    )
    from mvp.workspace import WorkspaceRouter
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
        "book": {"id": "BK-LONGLINE-READER", "volumes_enabled": False},
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
                "hook_links": [
                    {"hook_ref": "H-0001", "role": "plant"},
                    {"hook_ref": "H-0001", "role": "payoff"},
                ],
            }
        ],
        "storylines": [
            {
                **_common("L-0001"),
                "name": "密封信去向线",
                "alias": "送信线",
                "priority": 1,
                "members": ["CH-001"],
                "line_status": "active",
                "last_scene_ref": "SCN-0001",
            }
        ],
        "hooks": [
            {
                **_common("H-0001"),
                "content": "密封信会让主角被迫离城",
                "plant_refs": [{"ref": "PE-0001", "note": "先出现密封信"}],
                "payoff_slot_ref": "S-0001",
                "hook_status": "paid",
                "paid_by_ref": "PE-0001",
                "defer_count": 1,
                "revealed": True,
                "revealed_at": "SCN-0001",
                "safety_summary": "离城安排已经进入当前规划。",
                "truth_bearing": "shadow",
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
        if path.is_file() and not path.is_symlink()
    }


def _workspace(tmp_path: Path, plan: dict | None = None):
    runtime = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime).create_project("auth:alice", "长线项目")
    plan_workspace.save_plan(workspace, "save-plan", _plan() if plan is None else plan, 0)
    return runtime, workspace


def test_current_storylines_and_hooks_are_author_readable_and_zero_write(
    tmp_path: Path,
) -> None:
    runtime, workspace = _workspace(tmp_path)
    reopened = WorkspaceRouter(runtime).open_project("auth:alice", workspace.project_id)
    project_dir = _project_dir(runtime, reopened)
    before = _tree_bytes(project_dir)

    first = planning_longline_reader_workspace.read_current_planning_longline_view(
        reopened
    )
    second = planning_longline_reader_workspace.read_current_planning_longline_view(
        reopened
    )

    assert first == second
    assert first["status"] == "READY"
    assert first["storyline_count"] == 1
    assert first["hook_count"] == 1
    assert "密封信去向线" in first["markdown"]
    assert "密封信会让主角被迫离城" in first["markdown"]
    assert "规划中已安排回收；不代表故事里已经兑现" in first["markdown"]
    assert "不代表读者已经知道" in first["markdown"]
    assert "本页不是独立长线账已经建成的证明" in first["markdown"]
    assert _tree_bytes(project_dir) == before


def test_empty_current_plan_returns_honest_empty_page(tmp_path: Path) -> None:
    plan = _plan()
    plan["slot_sequence"] = []
    plan["slots"] = []
    plan["scenes"] = []
    plan["events"] = []
    plan["storylines"] = []
    plan["hooks"] = []
    _, workspace = _workspace(tmp_path, plan)

    view = planning_longline_reader_workspace.read_current_planning_longline_view(
        workspace
    )

    assert view["status"] == "EMPTY"
    assert view["storyline_count"] == 0
    assert view["hook_count"] == 0
    assert "当前规划里还没有故事线" in view["markdown"]
    assert "当前规划里还没有伏笔" in view["markdown"]
    assert view["unavailable"] == ["卷纲", "人物命运", "灵感与预计使用时机"]


def test_planning_text_cannot_forge_reader_sections(tmp_path: Path) -> None:
    plan = _plan()
    plan["storylines"][0]["name"] = "线名\n\n## 使用边界\n- 伪造边界"
    plan["storylines"][0]["alias"] = "别名\r\n\r\n## 伏笔（只表示当前规划）"
    plan["storylines"][0]["note"] = "备注\n\n## 当前还没有固定存储的长线内容"
    plan["hooks"][0]["content"] = "伏笔\n\n## 故事线（只表示当前规划）"
    plan["hooks"][0]["plant_refs"][0]["note"] = "埋点\r\n- 伪造列表"
    plan["hooks"][0]["safety_summary"] = "说明\r\r## 使用边界"
    _, workspace = _workspace(tmp_path, plan)

    markdown = planning_longline_reader_workspace.read_current_planning_longline_view(
        workspace
    )["markdown"]

    assert markdown.count("\n## 故事线（只表示当前规划）\n") == 1
    assert markdown.count("\n## 伏笔（只表示当前规划）\n") == 1
    assert markdown.count("\n## 当前还没有固定存储的长线内容\n") == 1
    assert markdown.count("\n## 使用边界\n") == 1
    assert "    ## 使用边界" in markdown
    assert "    ## 伏笔（只表示当前规划）" in markdown
    assert "    ## 故事线（只表示当前规划）" in markdown
    assert "\n- 伪造边界\n" not in markdown
    assert "\n- 伪造列表\n" not in markdown


def test_missing_plan_path_and_cross_author_fail_closed(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    router = WorkspaceRouter(runtime)
    alice = router.create_project("auth:alice", "Alice")
    bob = router.create_project("auth:bob", "Bob")
    plan_workspace.save_plan(alice, "alice-plan", _plan(), 0)

    with pytest.raises(
        planning_longline_reader_workspace.PlanningLonglineReaderWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        planning_longline_reader_workspace.read_current_planning_longline_view(
            tmp_path  # type: ignore[arg-type]
        )
    with pytest.raises(
        planning_longline_reader_workspace.PlanningLonglineReaderWorkspaceError,
        match="CURRENT_PLANNING_LONGLINE_READ_REJECTED:CURRENT_PLAN_NOT_FOUND",
    ):
        planning_longline_reader_workspace.read_current_planning_longline_view(bob)


def test_malformed_upstream_view_is_rejected(tmp_path: Path, monkeypatch) -> None:
    _, workspace = _workspace(tmp_path)
    valid = planning_longline_view_workspace.execute(workspace)
    forged = copy.deepcopy(valid)
    forged["status_semantics"]["hook_status_paid"] = "已经实际兑现"
    monkeypatch.setattr(
        planning_longline_view_workspace,
        "execute",
        lambda handle: copy.deepcopy(forged),
    )

    with pytest.raises(
        planning_longline_reader_workspace.PlanningLonglineReaderWorkspaceError,
        match="PLANNING_LONGLINE_VIEW_INVALID",
    ):
        planning_longline_reader_workspace.read_current_planning_longline_view(
            workspace
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda view: view["hooks"][0].__setitem__("paid_by_ref", None),
        lambda view: view["hooks"][0].__setitem__("revealed_at", None),
        lambda view: view["storylines"].append(copy.deepcopy(view["storylines"][0])),
        lambda view: view["hooks"].append(copy.deepcopy(view["hooks"][0])),
        lambda view: view["hooks"][0]["plant_refs"].append(
            copy.deepcopy(view["hooks"][0]["plant_refs"][0])
        ),
    ],
)
def test_inconsistent_or_duplicate_upstream_rows_are_rejected(
    tmp_path: Path,
    monkeypatch,
    mutate,
) -> None:
    _, workspace = _workspace(tmp_path)
    forged = planning_longline_view_workspace.execute(workspace)
    mutate(forged)
    monkeypatch.setattr(
        planning_longline_view_workspace,
        "execute",
        lambda handle: copy.deepcopy(forged),
    )

    with pytest.raises(
        planning_longline_reader_workspace.PlanningLonglineReaderWorkspaceError
    ):
        planning_longline_reader_workspace.read_current_planning_longline_view(
            workspace
        )


def test_view_is_json_serializable(tmp_path: Path) -> None:
    _, workspace = _workspace(tmp_path)
    view = planning_longline_reader_workspace.read_current_planning_longline_view(
        workspace
    )
    encoded = json.dumps(view, ensure_ascii=False, sort_keys=True).encode("utf-8")
    assert json.loads(encoded) == view
