from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        chapter_fact_draft_tool,
        chapter_fact_handover_tool,
        chapter_fact_handover_workspace,
        chapter_slot_workspace,
        plan_workspace,
    )
    from mvp.workspace import (
        OperationConflictError,
        ProjectNotFoundError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


ALICE = "auth:alice"
BOB = "auth:bob"
NOW = "2026-08-20 15:00:00"


def _plan() -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-FACT-HANDOVER", "volumes_enabled": False},
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


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _setup(tmp_path: Path, *, principal: str = ALICE):
    runtime = tmp_path / principal.replace(":", "-")
    workspace = WorkspaceRouter(runtime).create_project(principal, "章事实稿项目")
    plan_workspace.save_plan(workspace, "setup-plan", _plan(), 0)
    return runtime, workspace


def _pair(
    workspace,
    *,
    draft_operation_id: str = "draft-op-1",
    handover_operation_id: str = "handover-op-1",
    title: str = "雨巷来信",
    fact_text: str = "许岚把密封信交给林照。",
) -> tuple[dict, dict]:
    snapshot = chapter_slot_workspace.execute(workspace, "S-0001")
    draft = chapter_fact_draft_tool.execute(
        {
            "operation_id": draft_operation_id,
            "actor": "author",
            "chapter_slot_snapshot": snapshot,
            "entries": [
                {
                    "fact_text": fact_text,
                    "writing_note": "这里用短句，保持戒备感。",
                }
            ],
        }
    )
    action = chapter_fact_handover_tool.execute(
        {
            "chapter_fact_draft": draft,
            "actor": "author",
            "operation_id": handover_operation_id,
            "intent": "explicit_handover",
            "author_confirmed_title": title,
            "expected_prototype_sha256": draft["prototype_sha256"],
        }
    )
    return draft, action


def _save(workspace, draft: dict, action: dict, expected: int = 0) -> dict:
    return chapter_fact_handover_workspace.save_pending_handover_request(
        workspace,
        draft,
        action,
        expected,
    )


def test_save_restart_exact_readback_and_no_truth_or_current_side_effect(
    tmp_path: Path,
) -> None:
    runtime, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)

    saved = _save(workspace, draft, action)
    raw = workspace.read("chapter_fact_handover_requests")
    reopened = WorkspaceRouter(runtime).open_project(ALICE, workspace.project_id)
    loaded = chapter_fact_handover_workspace.read_pending_handover_request(
        reopened,
        action["operation_id"],
    )

    assert saved["status"] == "REQUEST_RECORDED_NOT_APPLIED"
    assert saved["replayed"] is False
    assert saved["requests_snapshot"] == {
        "version": raw["version"],
        "sha256": raw["sha256"],
    }
    assert _canonical(loaded["request"]["chapter_fact_draft"]) == _canonical(draft)
    assert _canonical(loaded["request"]["handover_action"]) == _canonical(action)
    assert raw["payload"]["schema_version"] == (
        "chapter-fact-handover-request-store-v1"
    )
    assert set(raw["payload"]["requests"]) == {"handover-op-1"}
    assert "current" not in raw["payload"]
    for forbidden in ("chapter_revisions", "chapters", "facts", "chapter_index"):
        assert workspace.read(forbidden) is None
    assert workspace.read("plan")["version"] == 1


def test_multiple_requests_append_and_old_request_replay_is_zero_write(
    tmp_path: Path,
) -> None:
    runtime, workspace = _setup(tmp_path)
    first = _pair(workspace)
    second = _pair(
        workspace,
        draft_operation_id="draft-op-2",
        handover_operation_id="handover-op-2",
        title="第二份交棒请求",
        fact_text="林照接受了密封信。",
    )
    _save(workspace, *first, expected=0)
    _save(workspace, *second, expected=1)
    changed_plan = _plan()
    changed_plan["slots"][0]["summary"] = "请求保存后规划继续推进"
    changed_plan["slots"][0]["rev"] = 3
    plan_workspace.save_plan(workspace, "advance-after-save", changed_plan, 1)
    before = _tree_bytes(_project_dir(runtime, workspace))

    replay = _save(workspace, *first, expected=0)

    assert replay["replayed"] is True
    assert replay["request"]["operation_id"] == "handover-op-1"
    assert _tree_bytes(_project_dir(runtime, workspace)) == before
    store = workspace.read("chapter_fact_handover_requests")["payload"]
    assert list(store["requests"]) == ["handover-op-1", "handover-op-2"]


def test_same_operation_different_payload_conflicts_without_overwrite(
    tmp_path: Path,
) -> None:
    runtime, workspace = _setup(tmp_path)
    original = _pair(workspace)
    _save(workspace, *original)
    changed = _pair(
        workspace,
        draft_operation_id="draft-op-other",
        handover_operation_id="handover-op-1",
        title="另一个标题",
    )
    before = _tree_bytes(_project_dir(runtime, workspace))

    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        _save(workspace, *changed, expected=1)

    assert _tree_bytes(_project_dir(runtime, workspace)) == before


@pytest.mark.parametrize("expected", [True, -1, 1])
def test_bad_or_stale_expected_version_leaves_request_store_absent(
    tmp_path: Path,
    expected: object,
) -> None:
    runtime, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    before = _tree_bytes(_project_dir(runtime, workspace))
    expected_error = (
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError
        if isinstance(expected, bool) or expected == -1
        else VersionConflictError
    )

    with pytest.raises(expected_error):
        _save(workspace, draft, action, expected=expected)  # type: ignore[arg-type]

    assert _tree_bytes(_project_dir(runtime, workspace)) == before
    assert workspace.read("chapter_fact_handover_requests") is None


def test_valid_but_different_draft_and_action_pair_is_rejected_before_write(
    tmp_path: Path,
) -> None:
    runtime, workspace = _setup(tmp_path)
    draft, _ = _pair(workspace)
    _, action = _pair(
        workspace,
        draft_operation_id="other-draft",
        handover_operation_id="handover-other",
        fact_text="另一份事实稿。",
    )
    before = _tree_bytes(_project_dir(runtime, workspace))

    with pytest.raises(
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError,
        match="HANDOVER_ACTION_DRAFT_MISMATCH",
    ):
        _save(workspace, draft, action)

    assert _tree_bytes(_project_dir(runtime, workspace)) == before


def test_missing_or_advanced_current_plan_rejects_without_request_write(
    tmp_path: Path,
) -> None:
    runtime, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    changed_plan = _plan()
    changed_plan["slots"][0]["summary"] = "规划已经改变"
    changed_plan["slots"][0]["rev"] = 3
    plan_workspace.save_plan(workspace, "advance-plan", changed_plan, 1)
    before = _tree_bytes(_project_dir(runtime, workspace))

    with pytest.raises(
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError,
        match="CHAPTER_FACT_DRAFT_PLAN_NOT_CURRENT",
    ):
        _save(workspace, draft, action)

    assert _tree_bytes(_project_dir(runtime, workspace)) == before
    assert workspace.read("chapter_fact_handover_requests") is None

    empty = WorkspaceRouter(tmp_path / "empty").create_project(ALICE, "空项目")
    with pytest.raises(
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError,
        match="CURRENT_PLAN_REQUIRED",
    ):
        _save(empty, draft, action)
    assert empty.read("chapter_fact_handover_requests") is None


def test_plan_change_before_commit_is_seen_and_request_is_not_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    original_state = chapter_fact_handover_workspace._state
    changed = False

    def change_plan_then_read(handle):
        nonlocal changed
        if not changed:
            changed = True
            next_plan = _plan()
            next_plan["slots"][0]["summary"] = "保存前发生变化"
            next_plan["slots"][0]["rev"] = 3
            plan_workspace.save_plan(handle, "race-plan-before", next_plan, 1)
        return original_state(handle)

    monkeypatch.setattr(
        chapter_fact_handover_workspace,
        "_state",
        change_plan_then_read,
    )

    with pytest.raises(
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError,
        match="CHAPTER_FACT_DRAFT_PLAN_NOT_CURRENT",
    ):
        _save(workspace, draft, action)

    assert workspace.read("chapter_fact_handover_requests") is None


def test_guarded_commit_closes_plan_race_without_partial_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    original_commit = workspace.commit_guarded

    def race(operation_id, mutations, expected_versions, guard_versions):
        changed_plan = _plan()
        changed_plan["slots"][0]["summary"] = "锁内提交前发生变化"
        changed_plan["slots"][0]["rev"] = 3
        plan_workspace.save_plan(workspace, "race-plan-locked", changed_plan, 1)
        return original_commit(
            operation_id,
            mutations,
            expected_versions,
            guard_versions,
        )

    monkeypatch.setattr(workspace, "commit_guarded", race)

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        _save(workspace, draft, action)

    assert workspace.read("chapter_fact_handover_requests") is None
    assert workspace.read("plan")["version"] == 2


def test_corrupt_saved_store_fails_closed_and_is_not_replaced(tmp_path: Path) -> None:
    runtime, workspace = _setup(tmp_path)
    workspace.commit(
        "inject-corrupt-store",
        {
            "chapter_fact_handover_requests": {
                "schema_version": "wrong",
                "requests": {},
            }
        },
        {"chapter_fact_handover_requests": 0},
    )
    draft, action = _pair(workspace)
    before = _tree_bytes(_project_dir(runtime, workspace))

    with pytest.raises(
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError,
        match="HANDOVER_REQUEST_STORE_INVALID",
    ):
        _save(workspace, draft, action, expected=1)

    assert _tree_bytes(_project_dir(runtime, workspace)) == before


def test_path_impersonation_and_cross_author_guess_do_not_leak_request(
    tmp_path: Path,
) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project(ALICE, "同名项目")
    bob = router.create_project(BOB, "同名项目")
    plan_workspace.save_plan(alice, "alice-plan", _plan(), 0)
    draft, action = _pair(alice)
    _save(alice, draft, action)

    with pytest.raises(
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        chapter_fact_handover_workspace.read_pending_handover_request(
            tmp_path, "handover-op-1"  # type: ignore[arg-type]
        )
    assert (
        chapter_fact_handover_workspace.read_pending_handover_request(
            bob, "handover-op-1"
        )
        is None
    )
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project(BOB, alice.project_id)


def test_read_returns_deep_copy_and_invalid_operation_does_not_write(
    tmp_path: Path,
) -> None:
    runtime, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    _save(workspace, draft, action)
    loaded = chapter_fact_handover_workspace.read_pending_handover_request(
        workspace, "handover-op-1"
    )
    loaded["request"]["chapter_fact_draft"]["entries"][0]["fact_text"] = "篡改"
    before = _tree_bytes(_project_dir(runtime, workspace))

    assert chapter_fact_handover_workspace.read_pending_handover_request(
        workspace, "handover-op-1"
    )["request"]["chapter_fact_draft"] == draft
    with pytest.raises(
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError,
        match="HANDOVER_OPERATION_ID_INVALID",
    ):
        chapter_fact_handover_workspace.read_pending_handover_request(
            workspace, "../handover"
        )
    assert _tree_bytes(_project_dir(runtime, workspace)) == before


def test_new_process_read_is_canonical_byte_equivalent(tmp_path: Path) -> None:
    runtime, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    _save(workspace, draft, action)
    expected = chapter_fact_handover_workspace.read_pending_handover_request(
        workspace, "handover-op-1"
    )
    script = """
import json
import sys
from mvp import chapter_fact_handover_workspace
from mvp.workspace import WorkspaceRouter
handle = WorkspaceRouter(sys.argv[1]).open_project(sys.argv[2], sys.argv[3])
result = chapter_fact_handover_workspace.read_pending_handover_request(handle, sys.argv[4])
print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
"""

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(runtime),
            ALICE,
            workspace.project_id,
            "handover-op-1",
        ],
        check=False,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(PRODUCT_ROOT)},
    )

    assert completed.returncode == 0, completed.stderr.decode()
    assert completed.stdout == _canonical(expected)


def test_preflight_after_restart_returns_current_request_without_writes(
    tmp_path: Path,
) -> None:
    runtime, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    _save(workspace, draft, action)
    reopened = WorkspaceRouter(runtime).open_project(ALICE, workspace.project_id)
    project_dir = _project_dir(runtime, reopened)
    before = _tree_bytes(project_dir)

    result = chapter_fact_handover_workspace.prepare_pending_handover_consumption(
        reopened,
        action["operation_id"],
    )

    assert result["status"] == "CURRENT_NOT_APPLIED"
    assert _canonical(result["request"]["chapter_fact_draft"]) == _canonical(draft)
    assert _canonical(result["request"]["handover_action"]) == _canonical(action)
    assert result["requests_snapshot"]["version"] == 1
    assert result["current_plan_snapshot"]["version"] == 1
    assert result["effects"] == {
        "c11": "none",
        "chapter_ledger": "none",
        "facts": "none",
        "plan": "none",
    }
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "HANDOVER_COMPLETE",
        '"chapter_id"',
        '"fact_id"',
        '"revision"',
    ):
        assert forbidden not in rendered
    assert _tree_bytes(project_dir) == before


def test_preflight_rejects_request_after_plan_has_advanced_without_writes(
    tmp_path: Path,
) -> None:
    runtime, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    _save(workspace, draft, action)
    changed = _plan()
    changed["slots"][0]["summary"] = "作者已经推进当前章槽"
    changed["slots"][0]["rev"] = 3
    plan_workspace.save_plan(workspace, "advance-plan", changed, 1)
    before = _tree_bytes(_project_dir(runtime, workspace))

    with pytest.raises(
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError,
        match="CHAPTER_FACT_DRAFT_PLAN_NOT_CURRENT",
    ):
        chapter_fact_handover_workspace.prepare_pending_handover_consumption(
            workspace,
            action["operation_id"],
        )

    assert _tree_bytes(_project_dir(runtime, workspace)) == before


def test_preflight_rejects_request_store_change_between_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, workspace = _setup(tmp_path)
    first_draft, first_action = _pair(workspace)
    _save(workspace, first_draft, first_action)
    first_state = chapter_fact_handover_workspace._state(workspace)
    second_draft, second_action = _pair(
        workspace,
        draft_operation_id="draft-op-2",
        handover_operation_id="handover-op-2",
        title="第二封信",
    )
    _save(workspace, second_draft, second_action, expected=1)
    second_state = chapter_fact_handover_workspace._state(workspace)
    states = [copy.deepcopy(first_state), copy.deepcopy(second_state)]
    before = _tree_bytes(_project_dir(runtime, workspace))

    monkeypatch.setattr(
        chapter_fact_handover_workspace,
        "_state",
        lambda handle: states.pop(0),
    )
    with pytest.raises(
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError,
        match="HANDOVER_REQUEST_STORE_CHANGED_DURING_PREFLIGHT",
    ):
        chapter_fact_handover_workspace.prepare_pending_handover_consumption(
            workspace,
            first_action["operation_id"],
        )

    assert states == []
    assert _tree_bytes(_project_dir(runtime, workspace)) == before


def test_preflight_rejects_plan_change_between_validations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, workspace = _setup(tmp_path)
    draft, action = _pair(workspace)
    _save(workspace, draft, action)
    original = chapter_fact_handover_workspace._current_plan_watermark
    calls = 0

    def change_before_second(handle, current_draft):
        nonlocal calls
        calls += 1
        if calls == 2:
            changed = _plan()
            changed["slots"][0]["summary"] = "预检期间规划变化"
            changed["slots"][0]["rev"] = 3
            plan_workspace.save_plan(handle, "race-plan-preflight", changed, 1)
        return original(handle, current_draft)

    monkeypatch.setattr(
        chapter_fact_handover_workspace,
        "_current_plan_watermark",
        change_before_second,
    )
    with pytest.raises(
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError,
        match="CURRENT_PLAN_CHANGED_DURING_PREFLIGHT",
    ):
        chapter_fact_handover_workspace.prepare_pending_handover_consumption(
            workspace,
            action["operation_id"],
        )

    assert calls == 2
    assert workspace.read("chapter_fact_handover_requests")["version"] == 1
    assert workspace.read("plan")["version"] == 2


def test_preflight_unknown_operation_path_and_cross_author_fail_closed(
    tmp_path: Path,
) -> None:
    runtime, alice = _setup(tmp_path)
    draft, action = _pair(alice)
    _save(alice, draft, action)
    bob = WorkspaceRouter(runtime).create_project(BOB, "Bob 预检")
    before = _tree_bytes(_project_dir(runtime, alice))

    with pytest.raises(
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError,
        match="PENDING_HANDOVER_REQUEST_NOT_FOUND",
    ):
        chapter_fact_handover_workspace.prepare_pending_handover_consumption(
            bob,
            action["operation_id"],
        )
    with pytest.raises(
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError,
        match="PENDING_HANDOVER_REQUEST_NOT_FOUND",
    ):
        chapter_fact_handover_workspace.prepare_pending_handover_consumption(
            alice,
            "handover-op-missing",
        )
    with pytest.raises(
        chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        chapter_fact_handover_workspace.prepare_pending_handover_consumption(
            tmp_path,  # type: ignore[arg-type]
            action["operation_id"],
        )

    assert _tree_bytes(_project_dir(runtime, alice)) == before
