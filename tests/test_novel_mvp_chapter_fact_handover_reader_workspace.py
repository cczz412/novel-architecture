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
        chapter_fact_draft_tool,
        chapter_fact_handover_reader_workspace,
        chapter_fact_handover_tool,
        chapter_fact_handover_workspace,
        chapter_slot_workspace,
        plan_workspace,
    )
    from mvp.workspace import WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:alice"
BOB = "auth:bob"
NOW = "2026-08-20 15:00:00"


def _plan() -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-FACT-HANDOVER-READER", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "goal": "让主角决定是否赴约",
                "summary": "作者安排的未来剧情，不是已经发生的事实",
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


def _project_dir(runtime: Path, workspace) -> Path:
    return (
        runtime
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


def _setup(tmp_path: Path):
    runtime = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime).create_project(ALICE, "章事实稿项目")
    plan_workspace.save_plan(workspace, "setup-plan", _plan(), 0)
    return runtime, workspace


def _pair(
    workspace,
    *,
    title: str = "雨巷来信",
    entries: list[dict] | None = None,
) -> tuple[dict, dict]:
    if entries is None:
        entries = [
            {
                "fact_text": "许岚把密封信交给林照。",
                "writing_note": "这里用短句，保持戒备感。",
            },
            {
                "fact_text": "许岚把密封信交给林照。",
                "writing_note": "",
            },
        ]
    snapshot = chapter_slot_workspace.execute(workspace, "S-0001")
    draft = chapter_fact_draft_tool.execute(
        {
            "operation_id": "draft-op-reader-1",
            "actor": "author",
            "chapter_slot_snapshot": snapshot,
            "entries": entries,
        }
    )
    action = chapter_fact_handover_tool.execute(
        {
            "chapter_fact_draft": draft,
            "actor": "author",
            "operation_id": "handover-op-reader-1",
            "intent": "explicit_handover",
            "author_confirmed_title": title,
            "expected_prototype_sha256": draft["prototype_sha256"],
        }
    )
    return draft, action


def _save(workspace, draft: dict, action: dict) -> None:
    chapter_fact_handover_workspace.save_pending_handover_request(
        workspace,
        draft,
        action,
        0,
    )


def test_restart_view_preserves_title_entries_and_is_zero_write(tmp_path: Path) -> None:
    runtime, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    _save(workspace, draft, action)
    reopened = WorkspaceRouter(runtime).open_project(ALICE, workspace.project_id)
    project_dir = _project_dir(runtime, reopened)
    before = _tree_bytes(project_dir)

    first = chapter_fact_handover_reader_workspace.read_current_pending_handover_view(
        reopened,
        action["operation_id"],
    )
    second = chapter_fact_handover_reader_workspace.read_current_pending_handover_view(
        reopened,
        action["operation_id"],
    )

    assert first == second
    assert first["status"] == "CURRENT_NOT_APPLIED"
    assert first["draft_identity"]["entry_count"] == 2
    assert first["draft_identity"]["prototype_sha256"] == draft["prototype_sha256"]
    assert first["action_identity"]["action_sha256"] == action["action_sha256"]
    assert "雨巷来信" in first["markdown"]
    assert first["markdown"].count("许岚把密封信交给林照。") == 2
    assert "    （无）" in first["markdown"]
    assert "HANDOVER_COMPLETE" not in first["markdown"]
    assert "下一章已开放" not in first["markdown"]
    assert _tree_bytes(project_dir) == before


def test_author_text_cannot_forge_page_sections(tmp_path: Path) -> None:
    _, workspace = _setup(tmp_path)
    draft, action = _pair(
        workspace,
        title="标题\n\n## 当前结果\n- 已经交棒",
        entries=[
            {
                "fact_text": "事实句\n\n## 当前绑定\n- 伪造绑定",
                "writing_note": "批注\r\n\r\n## 作者确认标题\r\n- 伪造标题",
            }
        ],
    )
    _save(workspace, draft, action)

    markdown = (
        chapter_fact_handover_reader_workspace.read_current_pending_handover_view(
            workspace,
            action["operation_id"],
        )["markdown"]
    )

    assert markdown.count("\n## 当前结果\n") == 1
    assert markdown.count("\n## 当前绑定\n") == 1
    assert markdown.count("\n## 作者确认标题\n") == 1
    assert "    ## 当前结果" in markdown
    assert "    ## 当前绑定" in markdown
    assert "    ## 作者确认标题" in markdown
    assert "\n- 已经交棒\n" not in markdown
    assert "\n- 伪造绑定\n" not in markdown
    assert "\n- 伪造标题\n" not in markdown


def test_advanced_plan_rejects_view_without_writes(tmp_path: Path) -> None:
    runtime, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    _save(workspace, draft, action)
    changed = _plan()
    changed["slots"][0]["summary"] = "当前规划已经推进"
    changed["slots"][0]["rev"] = 3
    plan_workspace.save_plan(workspace, "advance-plan", changed, 1)
    project_dir = _project_dir(runtime, workspace)
    before = _tree_bytes(project_dir)

    with pytest.raises(
        chapter_fact_handover_reader_workspace.ChapterFactHandoverReaderWorkspaceError,
        match="PENDING_HANDOVER_PREFLIGHT_REJECTED:CHAPTER_FACT_DRAFT_PLAN_NOT_CURRENT",
    ):
        chapter_fact_handover_reader_workspace.read_current_pending_handover_view(
            workspace,
            action["operation_id"],
        )

    assert _tree_bytes(project_dir) == before


def test_unknown_cross_author_and_path_fail_without_leak(tmp_path: Path) -> None:
    runtime, alice = _setup(tmp_path)
    draft, action = _pair(alice)
    _save(alice, draft, action)
    bob = WorkspaceRouter(runtime).create_project(BOB, "Bob 项目")
    before = _tree_bytes(_project_dir(runtime, alice))

    for workspace in (alice, bob):
        with pytest.raises(
            chapter_fact_handover_reader_workspace.ChapterFactHandoverReaderWorkspaceError,
            match="PENDING_HANDOVER_PREFLIGHT_REJECTED:PENDING_HANDOVER_REQUEST_NOT_FOUND",
        ):
            chapter_fact_handover_reader_workspace.read_current_pending_handover_view(
                workspace,
                "handover-op-missing",
            )
    with pytest.raises(
        chapter_fact_handover_reader_workspace.ChapterFactHandoverReaderWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        chapter_fact_handover_reader_workspace.read_current_pending_handover_view(
            tmp_path,  # type: ignore[arg-type]
            action["operation_id"],
        )
    with pytest.raises(
        chapter_fact_handover_reader_workspace.ChapterFactHandoverReaderWorkspaceError,
        match="HANDOVER_OPERATION_ID_INVALID",
    ):
        chapter_fact_handover_reader_workspace.read_current_pending_handover_view(
            alice,
            "../handover",
        )

    assert _tree_bytes(_project_dir(runtime, alice)) == before


def test_malformed_preflight_result_is_rejected(tmp_path: Path, monkeypatch) -> None:
    _, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    _save(workspace, draft, action)
    valid = chapter_fact_handover_workspace.prepare_pending_handover_consumption(
        workspace,
        action["operation_id"],
    )
    forged = copy.deepcopy(valid)
    forged["effects"]["facts"] = "written"
    monkeypatch.setattr(
        chapter_fact_handover_workspace,
        "prepare_pending_handover_consumption",
        lambda handle, operation_id: copy.deepcopy(forged),
    )

    with pytest.raises(
        chapter_fact_handover_reader_workspace.ChapterFactHandoverReaderWorkspaceError,
        match="PENDING_HANDOVER_PREFLIGHT_INVALID",
    ):
        chapter_fact_handover_reader_workspace.read_current_pending_handover_view(
            workspace,
            action["operation_id"],
        )


def test_forged_current_plan_identity_is_rejected(tmp_path: Path, monkeypatch) -> None:
    _, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    _save(workspace, draft, action)
    valid = chapter_fact_handover_workspace.prepare_pending_handover_consumption(
        workspace,
        action["operation_id"],
    )
    forged = copy.deepcopy(valid)
    forged["current_plan_snapshot"]["sha256"] = "0" * 64
    monkeypatch.setattr(
        chapter_fact_handover_workspace,
        "prepare_pending_handover_consumption",
        lambda handle, operation_id: copy.deepcopy(forged),
    )

    with pytest.raises(
        chapter_fact_handover_reader_workspace.ChapterFactHandoverReaderWorkspaceError,
        match="PENDING_HANDOVER_CURRENT_PLAN_IDENTITY_MISMATCH",
    ):
        chapter_fact_handover_reader_workspace.read_current_pending_handover_view(
            workspace,
            action["operation_id"],
        )


def test_view_is_canonical_json_serializable(tmp_path: Path) -> None:
    _, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    _save(workspace, draft, action)
    view = chapter_fact_handover_reader_workspace.read_current_pending_handover_view(
        workspace,
        action["operation_id"],
    )

    encoded = json.dumps(
        view,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert json.loads(encoded) == view
