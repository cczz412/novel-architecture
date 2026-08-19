from __future__ import annotations

import copy
import hashlib
import inspect
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import chapter_slot_snapshot_tool, planstore, work_draft_workspace
    from mvp.workspace import (
        AuthorWorkspace,
        OperationConflictError,
        ProjectNotFoundError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


def _action(
    operation_id: str = "op-work-save-r1",
    *,
    expected_rev: int = 0,
    slot_ref: str = "S-0001",
    source_outline_ref: str = "S-0001@outline-r2",
    entry_mode: str = "typed",
    text: str = "窗外的雨突然停了。\n\n“你听见了吗？”",
) -> dict:
    return {
        "operation_id": operation_id,
        "slot_ref": slot_ref,
        "source_outline_ref": source_outline_ref,
        "expected_rev": expected_rev,
        "entry_mode": entry_mode,
        "author_text": text,
    }


def _handover_action(
    *,
    work_rev: int = 2,
    work_ref: str = "S-0001@work",
    slot_ref: str = "S-0001",
    source_outline_ref: str = "S-0001@outline-r2",
) -> dict:
    return {
        "contract": "WORK_DRAFT_HANDOVER_ACTION",
        "version": "v1",
        "operation_id": "op-handover-work-r2",
        "actor": "author",
        "intent": "adopt_as_manuscript",
        "work_ref": work_ref,
        "work_rev": work_rev,
        "slot_ref": slot_ref,
        "source_outline_ref": source_outline_ref,
        "target_contract": "C1_CHAPTER_DOC",
        "target_planstore_result": "handover_parts",
    }


def _skip_check_action(
    *,
    work_rev: int = 2,
    work_ref: str = "S-0001@work",
    slot_ref: str = "S-0001",
) -> dict:
    return {
        "contract": "WRITING_DESK_CLOSEOUT_ACTION",
        "version": "v1",
        "operation_id": "op-closeout-skip-r2",
        "actor": "author",
        "slot_ref": slot_ref,
        "route": "skip_check",
        "work_ref": work_ref,
        "work_rev": work_rev,
        "check_result_ref": None,
    }


def _no_prose_action(*, slot_ref: str = "S-0001") -> dict:
    return {
        "contract": "WRITING_DESK_CLOSEOUT_ACTION",
        "version": "v1",
        "operation_id": "op-closeout-no-prose",
        "actor": "author",
        "slot_ref": slot_ref,
        "route": "no_prose",
        "work_ref": None,
        "work_rev": None,
        "check_result_ref": None,
    }


def _plan(*, slot_ref: str = "S-0001") -> dict:
    now = "2026-08-19 15:00:00"
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-NO-PROSE", "volumes_enabled": False},
        "slot_sequence": [slot_ref],
        "volumes": [],
        "slots": [
            {
                "id": slot_ref,
                "goal": "让主角决定是否赴约",
                "summary": "这是作者安排的未来剧情",
                "entry_state": "邀请仍未答复",
                "storyline_refs": [],
                "scene_refs": ["SCN-0001"],
                "exit_condition": "主角作出选择",
                "exit_hook": "选择将影响后续",
                "must_not": ["不得把规划冒充事实"],
                "risks": [],
                "target_length": 1200,
                "outline_checkpoint": {
                    "outline_rev": 3,
                    "source_slot_ref": slot_ref,
                    "source_commit_seq": 8,
                },
                "slot_status": "planned",
                "handover_parts": [],
                "truth_bearing": "primary",
                "updated_at": now,
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
                "updated_at": now,
                "rev": 4,
            }
        ],
        "events": [
            {
                "id": "PE-0001",
                "scene_ref": "SCN-0001",
                "text": "主角计划打开邀请信",
                "truth_bearing": "primary",
                "updated_at": now,
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


def _workspace_with_plan(runtime_root: Path, *, principal: str = "alice"):
    workspace = WorkspaceRouter(runtime_root).create_project(principal, "章槽项目")
    workspace.commit("op-plan-setup", {"plan": _plan()}, {"plan": 0})
    return workspace


def _save_r2(workspace: AuthorWorkspace) -> None:
    work_draft_workspace.save_current_work_draft(workspace, _action())
    work_draft_workspace.save_current_work_draft(
        workspace,
        _action(
            "op-work-save-r2",
            expected_rev=1,
            entry_mode="edited",
            text="第二版作者原文。\n换行保留。",
        ),
    )


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _other_visible_state(workspace: AuthorWorkspace) -> dict[str, object]:
    return {
        key: workspace.read(key)
        for key in ("plan", "chapters", "chapter_index", "facts")
    }


def _persisted_draft(
    *,
    work_rev: int = 1,
    entry_mode: str = "typed",
    text: str = "原文",
) -> dict:
    return {
        "contract": "WRITING_DESK_WORK_DRAFT",
        "version": "v1",
        "work_ref": "S-0001@work",
        "slot_ref": "S-0001",
        "source_outline_ref": "S-0001@outline-r2",
        "work_rev": work_rev,
        "state": "working",
        "entry_mode": entry_mode,
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "last_operation_id": "op-seed",
    }


def test_first_save_edit_restart_and_exact_text_round_trip(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project("alice", "作者项目")
    text_r1 = "  雨落在窗台。\r\n\r\n“别动——”\n她说。  "

    first = work_draft_workspace.save_current_work_draft(
        workspace,
        _action(text=text_r1),
    )
    assert first["replayed"] is False
    assert first["draft_workspace"]["version"] == 1
    assert first["current_work_draft"] == {
        "contract": "WRITING_DESK_WORK_DRAFT",
        "version": "v1",
        "work_ref": "S-0001@work",
        "slot_ref": "S-0001",
        "source_outline_ref": "S-0001@outline-r2",
        "work_rev": 1,
        "state": "working",
        "entry_mode": "typed",
        "text": text_r1,
        "text_sha256": hashlib.sha256(text_r1.encode("utf-8")).hexdigest(),
        "last_operation_id": "op-work-save-r1",
    }

    text_r2 = text_r1 + "\n门外又响了一声。"
    second = work_draft_workspace.save_current_work_draft(
        workspace,
        _action(
            "op-work-save-r2",
            expected_rev=1,
            entry_mode="edited",
            text=text_r2,
        ),
    )
    restarted = WorkspaceRouter(runtime_root).open_project(
        "alice", workspace.project_id
    )
    restored = work_draft_workspace.read_current_work_draft(restarted)

    assert second["draft_workspace"]["version"] == 2
    assert second["current_work_draft"]["work_rev"] == 2
    assert restored == {
        "status": "READY",
        "draft_workspace": copy.deepcopy(second["draft_workspace"]),
        "current_work_draft": copy.deepcopy(second["current_work_draft"]),
    }
    assert restored["current_work_draft"]["text"] == text_r2


def test_idempotent_replay_and_operation_conflict_do_not_advance_revision(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "alice", "项目"
    )
    action = _action()

    first = work_draft_workspace.save_current_work_draft(workspace, action)
    replay = work_draft_workspace.save_current_work_draft(workspace, action)

    assert replay["replayed"] is True
    assert replay["operation_receipt"] == first["operation_receipt"]
    assert workspace.read("draft")["version"] == 1
    assert replay["current_work_draft"]["work_rev"] == 1

    changed = {**action, "author_text": "同一动作号的另一份文本"}
    before = copy.deepcopy(workspace.read("draft"))
    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        work_draft_workspace.save_current_work_draft(workspace, changed)
    assert workspace.read("draft") == before


def test_stale_revision_and_different_slot_fail_without_overwrite(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "alice", "项目"
    )
    work_draft_workspace.save_current_work_draft(workspace, _action())
    before = copy.deepcopy(workspace.read("draft"))

    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="STALE_WORK_REVISION",
    ):
        work_draft_workspace.save_current_work_draft(
            workspace,
            _action("op-stale", expected_rev=0, text="过期编辑"),
        )
    assert workspace.read("draft") == before

    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="CURRENT_WORK_DRAFT_SLOT_CONFLICT",
    ):
        work_draft_workspace.save_current_work_draft(
            workspace,
            _action(
                "op-other-slot",
                expected_rev=1,
                slot_ref="S-0002",
                source_outline_ref="S-0002@outline-r1",
            ),
        )
    assert workspace.read("draft") == before


@pytest.mark.parametrize(
    ("change", "expected_error"),
    [
        ({"entry_mode": "generated"}, "WORK_DRAFT_ENTRY_MODE_INVALID"),
        ({"expected_rev": -1}, "EXPECTED_WORK_REV_INVALID"),
        ({"slot_ref": " S-0001"}, "WORK_DRAFT_SLOT_REF_INVALID"),
        ({"author_text": 123}, "WORK_DRAFT_TEXT_INVALID"),
    ],
)
def test_invalid_save_action_fails_before_write(
    tmp_path: Path,
    change: dict,
    expected_error: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / expected_error).create_project(
        "alice", "项目"
    )
    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match=expected_error,
    ):
        work_draft_workspace.save_current_work_draft(
            workspace,
            {**_action(), **change},
        )
    assert workspace.read("draft") is None


@pytest.mark.parametrize(
    ("corruption", "expected_error"),
    [
        ({"text_sha256": "0" * 64}, "WORK_DRAFT_TEXT_SHA_MISMATCH"),
        ({"entry_mode": "generated"}, "WORK_DRAFT_ENTRY_MODE_INVALID"),
        ({"work_ref": "S-9999@work"}, "WORK_DRAFT_REF_INVALID"),
        ({"work_rev": 2}, "WORK_DRAFT_REVISION_INVALID"),
        ({"unexpected": True}, "WORK_DRAFT_WORKSPACE_ENTRY_INVALID"),
    ],
)
def test_corrupt_persisted_draft_is_rejected(
    tmp_path: Path,
    corruption: dict,
    expected_error: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / expected_error).create_project(
        "alice", "项目"
    )
    workspace.commit(
        "op-corrupt",
        {"draft": {**_persisted_draft(), **corruption}},
        {"draft": 0},
    )

    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match=expected_error,
    ):
        work_draft_workspace.read_current_work_draft(workspace)


def test_only_draft_changes_and_empty_read_is_read_only(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "alice", "项目"
    )
    before_empty = _other_visible_state(workspace)
    assert work_draft_workspace.read_current_work_draft(workspace) == {
        "status": "EMPTY",
        "draft_workspace": None,
        "current_work_draft": None,
    }
    assert _other_visible_state(workspace) == before_empty

    work_draft_workspace.save_current_work_draft(workspace, _action())
    assert _other_visible_state(workspace) == before_empty
    before_failure = copy.deepcopy(workspace.read("draft"))
    with pytest.raises(work_draft_workspace.WorkDraftWorkspaceError):
        work_draft_workspace.save_current_work_draft(
            workspace,
            _action("op-invalid", expected_rev=1, entry_mode="ai"),
        )
    assert workspace.read("draft") == before_failure
    assert _other_visible_state(workspace) == before_empty


def test_bound_handle_only_and_cross_author_isolation(tmp_path: Path) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project("alice", "同名项目")
    bob = router.create_project("bob", "同名项目")
    work_draft_workspace.save_current_work_draft(bob, _action())

    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("alice", bob.project_id)
    assert work_draft_workspace.read_current_work_draft(alice)["status"] == "EMPTY"
    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        work_draft_workspace.read_current_work_draft(tmp_path)  # type: ignore[arg-type]

    assert list(
        inspect.signature(work_draft_workspace.save_current_work_draft).parameters
    ) == ["workspace", "action"]
    assert list(
        inspect.signature(work_draft_workspace.read_current_work_draft).parameters
    ) == ["workspace"]


def test_matching_current_r2_prepares_read_only_handover_bundle(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project("alice", "项目")
    _save_r2(workspace)
    action = _handover_action()
    before = _tree_bytes(runtime_root)

    bundle = work_draft_workspace.prepare_explicit_handover(workspace, action)

    assert bundle["status"] == "PREFLIGHT_READY"
    assert bundle["handover_action"] == action
    assert bundle["draft_workspace"] == {
        "version": 2,
        "sha256": workspace.read("draft")["sha256"],
    }
    assert bundle["current_work_draft"]["work_rev"] == 2
    assert bundle["current_work_draft"]["text"] == "第二版作者原文。\n换行保留。"
    assert _tree_bytes(runtime_root) == before
    assert _other_visible_state(workspace) == {
        "plan": None,
        "chapters": None,
        "chapter_index": None,
        "facts": None,
    }


@pytest.mark.parametrize(
    ("change", "expected_error"),
    [
        ({"work_rev": 1}, "STALE_WORK_REVISION"),
        ({"work_ref": "S-9999@work"}, "WORK_DRAFT_HANDOVER_REF_MISMATCH"),
        ({"slot_ref": "S-9999"}, "WORK_DRAFT_HANDOVER_REF_MISMATCH"),
        (
            {"source_outline_ref": "S-0001@outline-r1"},
            "WORK_DRAFT_HANDOVER_REF_MISMATCH",
        ),
        ({"actor": "provider"}, "WORK_DRAFT_HANDOVER_ACTOR_INVALID"),
        ({"intent": "save_only"}, "WORK_DRAFT_HANDOVER_INTENT_INVALID"),
        ({"target_contract": "C11"}, "WORK_DRAFT_HANDOVER_TARGET_INVALID"),
        (
            {"target_planstore_result": "closed"},
            "WORK_DRAFT_HANDOVER_PLAN_RESULT_INVALID",
        ),
    ],
)
def test_handover_mismatch_or_invalid_author_intent_fails_without_write(
    tmp_path: Path,
    change: dict,
    expected_error: str,
) -> None:
    runtime_root = tmp_path / expected_error
    workspace = WorkspaceRouter(runtime_root).create_project("alice", "项目")
    _save_r2(workspace)
    before = _tree_bytes(runtime_root)

    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match=expected_error,
    ):
        work_draft_workspace.prepare_explicit_handover(
            workspace,
            {**_handover_action(), **change},
        )
    assert _tree_bytes(runtime_root) == before


def test_handover_detects_draft_change_between_reads_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project("alice", "项目")
    _save_r2(workspace)
    stable_entry = workspace.read("draft")
    changed_entry = copy.deepcopy(stable_entry)
    changed_entry["version"] = 3
    changed_entry["sha256"] = "1" * 64
    changed_entry["payload"]["work_rev"] = 3
    reads = iter([stable_entry, changed_entry])
    before = _tree_bytes(runtime_root)
    monkeypatch.setattr(workspace, "read", lambda logical_key: next(reads))

    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="WORK_DRAFT_CHANGED_DURING_HANDOVER_READ",
    ):
        work_draft_workspace.prepare_explicit_handover(
            workspace,
            _handover_action(),
        )
    assert _tree_bytes(runtime_root) == before


def test_handover_bundle_is_deep_copy_and_restart_is_byte_equivalent(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project("alice", "项目")
    _save_r2(workspace)
    action = _handover_action()

    first = work_draft_workspace.prepare_explicit_handover(workspace, action)
    first_bytes = _canonical_bytes(first)
    first["handover_action"]["actor"] = "provider"
    first["current_work_draft"]["text"] = "篡改"
    first["draft_workspace"]["sha256"] = "0" * 64

    restarted = WorkspaceRouter(runtime_root).open_project(
        "alice", workspace.project_id
    )
    second = work_draft_workspace.prepare_explicit_handover(restarted, action)
    assert _canonical_bytes(second) == first_bytes


def test_handover_requires_bound_workspace_current_draft_and_valid_storage(
    tmp_path: Path,
) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project("alice", "项目")
    bob = router.create_project("bob", "项目")
    _save_r2(bob)

    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="CURRENT_WORK_DRAFT_REQUIRED",
    ):
        work_draft_workspace.prepare_explicit_handover(
            alice,
            _handover_action(),
        )
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("alice", bob.project_id)
    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        work_draft_workspace.prepare_explicit_handover(  # type: ignore[arg-type]
            tmp_path,
            _handover_action(),
        )

    corrupt = router.create_project("alice", "损坏项目")
    corrupt.commit(
        "op-corrupt-handover",
        {"draft": {**_persisted_draft(work_rev=1), "text_sha256": "0" * 64}},
        {"draft": 0},
    )
    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="WORK_DRAFT_TEXT_SHA_MISMATCH",
    ):
        work_draft_workspace.prepare_explicit_handover(
            corrupt,
            _handover_action(work_rev=1),
        )

    assert list(
        inspect.signature(work_draft_workspace.prepare_explicit_handover).parameters
    ) == ["workspace", "action"]


def test_current_r2_prepares_read_only_skip_check_closeout(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project("alice", "项目")
    _save_r2(workspace)
    action = _skip_check_action()
    before = _tree_bytes(runtime_root)

    result = work_draft_workspace.prepare_skip_check_closeout(workspace, action)

    assert result == {
        "status": "PREFLIGHT_READY",
        "closeout_action": action,
        "draft_workspace": {
            "version": 2,
            "sha256": workspace.read("draft")["sha256"],
        },
        "result": "skipped_by_author",
        "handover_effect": "none",
        "chapter_close_effect": "none",
        "truth_effect": "none",
    }
    assert not set(result) & {"passed", "clean", "checked", "chapter_closed"}
    assert _tree_bytes(runtime_root) == before
    assert _other_visible_state(workspace) == {
        "plan": None,
        "chapters": None,
        "chapter_index": None,
        "facts": None,
    }


@pytest.mark.parametrize(
    ("mutate", "expected_error"),
    [
        (lambda value: value.update(work_rev=1), "STALE_WORK_REVISION"),
        (
            lambda value: value.update(work_ref="S-9999@work"),
            "WORK_DRAFT_CLOSEOUT_REF_MISMATCH",
        ),
        (
            lambda value: value.update(slot_ref="S-9999"),
            "WORK_DRAFT_CLOSEOUT_REF_MISMATCH",
        ),
        (
            lambda value: value.update(actor="provider"),
            "WRITING_DESK_CLOSEOUT_ACTOR_INVALID",
        ),
        (lambda value: value.update(route="full_check"), "SKIP_CHECK_ROUTE_REQUIRED"),
        (
            lambda value: value.update(check_result_ref="check-r2"),
            "SKIP_CHECK_MUST_NOT_REFERENCE_RESULT",
        ),
        (
            lambda value: value.pop("work_ref"),
            "WRITING_DESK_CLOSEOUT_ACTION_INVALID",
        ),
        (
            lambda value: value.update(extra=True),
            "WRITING_DESK_CLOSEOUT_ACTION_INVALID",
        ),
    ],
)
def test_skip_check_action_or_current_mismatch_fails_without_write(
    tmp_path: Path,
    mutate,
    expected_error: str,
) -> None:
    runtime_root = tmp_path / expected_error
    workspace = WorkspaceRouter(runtime_root).create_project("alice", "项目")
    _save_r2(workspace)
    action = _skip_check_action()
    mutate(action)
    before = _tree_bytes(runtime_root)

    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match=expected_error,
    ):
        work_draft_workspace.prepare_skip_check_closeout(workspace, action)
    assert _tree_bytes(runtime_root) == before


def test_skip_check_discards_draft_changed_between_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project("alice", "项目")
    _save_r2(workspace)
    stable_entry = workspace.read("draft")
    changed_entry = copy.deepcopy(stable_entry)
    changed_entry["version"] = 3
    changed_entry["sha256"] = "1" * 64
    changed_entry["payload"]["work_rev"] = 3
    reads = iter([stable_entry, changed_entry])
    before = _tree_bytes(runtime_root)
    monkeypatch.setattr(workspace, "read", lambda logical_key: next(reads))

    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="WORK_DRAFT_CHANGED_DURING_CLOSEOUT_READ",
    ):
        work_draft_workspace.prepare_skip_check_closeout(
            workspace,
            _skip_check_action(),
        )
    assert _tree_bytes(runtime_root) == before


def test_skip_check_result_is_deep_copy_and_restart_is_byte_equivalent(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project("alice", "项目")
    _save_r2(workspace)
    action = _skip_check_action()

    first = work_draft_workspace.prepare_skip_check_closeout(workspace, action)
    first_bytes = _canonical_bytes(first)
    first["closeout_action"]["actor"] = "provider"
    first["draft_workspace"]["sha256"] = "0" * 64

    restarted = WorkspaceRouter(runtime_root).open_project(
        "alice", workspace.project_id
    )
    second = work_draft_workspace.prepare_skip_check_closeout(restarted, action)
    assert _canonical_bytes(second) == first_bytes


def test_skip_check_requires_bound_workspace_current_draft_and_valid_storage(
    tmp_path: Path,
) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project("alice", "项目")
    bob = router.create_project("bob", "项目")
    _save_r2(bob)

    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="CURRENT_WORK_DRAFT_REQUIRED",
    ):
        work_draft_workspace.prepare_skip_check_closeout(
            alice,
            _skip_check_action(),
        )
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("alice", bob.project_id)
    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        work_draft_workspace.prepare_skip_check_closeout(  # type: ignore[arg-type]
            tmp_path,
            _skip_check_action(),
        )

    corrupt = router.create_project("alice", "损坏项目")
    corrupt.commit(
        "op-corrupt-closeout",
        {"draft": {**_persisted_draft(work_rev=1), "text_sha256": "0" * 64}},
        {"draft": 0},
    )
    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="WORK_DRAFT_TEXT_SHA_MISMATCH",
    ):
        work_draft_workspace.prepare_skip_check_closeout(
            corrupt,
            _skip_check_action(work_rev=1),
        )

    assert list(
        inspect.signature(
            work_draft_workspace.prepare_skip_check_closeout
        ).parameters
    ) == ["workspace", "action"]


def test_no_prose_current_slot_and_empty_draft_prepare_read_only_result(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = _workspace_with_plan(runtime_root)
    action = _no_prose_action()
    before = _tree_bytes(runtime_root)

    result = work_draft_workspace.prepare_no_prose_closeout(workspace, action)

    assert result == {
        "status": "PREFLIGHT_READY",
        "closeout_action": action,
        "chapter_slot_source": {
            "slot_ref": "S-0001",
            "source_plan_version": 1,
            "source_plan_sha256": workspace.read("plan")["sha256"],
            "generation_watermark": {
                "source_plan_version": 1,
                "source_plan_sha256": workspace.read("plan")["sha256"],
                "slot_rev": 2,
                "outline_source_commit_seq": 8,
            },
        },
        "result": "not_applicable_no_manuscript",
        "handover_effect": "none",
        "chapter_close_effect": "none",
        "truth_effect": "none",
    }
    assert workspace.read("draft") is None
    assert _tree_bytes(runtime_root) == before
    assert _other_visible_state(workspace) == {
        "plan": workspace.read("plan"),
        "chapters": None,
        "chapter_index": None,
        "facts": None,
    }


@pytest.mark.parametrize(
    ("mutate", "expected_error"),
    [
        (lambda value: value.update(route="skip_check"), "NO_PROSE_ROUTE_REQUIRED"),
        (
            lambda value: value.update(work_ref="S-0001@work"),
            "NO_PROSE_MUST_NOT_REFERENCE_WORK",
        ),
        (
            lambda value: value.update(work_rev=1),
            "NO_PROSE_MUST_NOT_REFERENCE_WORK",
        ),
        (
            lambda value: value.update(check_result_ref="check-r1"),
            "NO_PROSE_MUST_NOT_REFERENCE_RESULT",
        ),
        (
            lambda value: value.update(actor="provider"),
            "WRITING_DESK_CLOSEOUT_ACTOR_INVALID",
        ),
    ],
)
def test_no_prose_invalid_action_fails_without_write(
    tmp_path: Path,
    mutate,
    expected_error: str,
) -> None:
    runtime_root = tmp_path / expected_error
    workspace = _workspace_with_plan(runtime_root)
    action = _no_prose_action()
    mutate(action)
    before = _tree_bytes(runtime_root)

    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match=expected_error,
    ):
        work_draft_workspace.prepare_no_prose_closeout(workspace, action)
    assert _tree_bytes(runtime_root) == before


def test_no_prose_rejects_any_existing_current_work_draft(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = _workspace_with_plan(runtime_root)
    work_draft_workspace.save_current_work_draft(
        workspace,
        _action(
            slot_ref="S-9999",
            source_outline_ref="S-9999@outline-r1",
        ),
    )
    before = _tree_bytes(runtime_root)

    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="NO_PROSE_REQUIRES_EMPTY_WORK_DRAFT",
    ):
        work_draft_workspace.prepare_no_prose_closeout(
            workspace,
            _no_prose_action(),
        )
    assert _tree_bytes(runtime_root) == before


def test_no_prose_rejects_missing_slot_and_corrupt_plan(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = _workspace_with_plan(runtime_root)
    before = _tree_bytes(runtime_root)
    with pytest.raises(
        chapter_slot_snapshot_tool.ChapterSlotSnapshotError,
        match="SLOT_NOT_FOUND",
    ):
        work_draft_workspace.prepare_no_prose_closeout(
            workspace,
            _no_prose_action(slot_ref="S-9999"),
        )
    assert _tree_bytes(runtime_root) == before

    bad_root = tmp_path / "bad-plan"
    bad_workspace = WorkspaceRouter(bad_root).create_project("alice", "坏计划")
    bad_workspace.commit(
        "op-bad-plan",
        {"plan": {"schema": "broken"}},
        {"plan": 0},
    )
    bad_before = _tree_bytes(bad_root)
    with pytest.raises(planstore.PlanstoreError):
        work_draft_workspace.prepare_no_prose_closeout(
            bad_workspace,
            _no_prose_action(),
        )
    assert _tree_bytes(bad_root) == bad_before


def test_no_prose_discards_slot_or_draft_changed_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = _workspace_with_plan(runtime_root)
    original_execute = work_draft_workspace.chapter_slot_workspace.execute
    stable_snapshot = original_execute(workspace, "S-0001")
    changed_snapshot = copy.deepcopy(stable_snapshot)
    changed_snapshot["slot_rev"] = 3
    changed_snapshot["generation_watermark"]["slot_rev"] = 3
    snapshots = iter([stable_snapshot, changed_snapshot])
    monkeypatch.setattr(
        work_draft_workspace.chapter_slot_workspace,
        "execute",
        lambda handle, slot_ref: next(snapshots),
    )
    before = _tree_bytes(runtime_root)
    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="CHAPTER_SLOT_CHANGED_DURING_CLOSEOUT_READ",
    ):
        work_draft_workspace.prepare_no_prose_closeout(
            workspace,
            _no_prose_action(),
        )
    assert _tree_bytes(runtime_root) == before

    monkeypatch.setattr(
        work_draft_workspace.chapter_slot_workspace,
        "execute",
        lambda handle, slot_ref: copy.deepcopy(stable_snapshot),
    )
    original_read = workspace.read
    draft = _persisted_draft()
    reads = iter([None, {"logical_key": "draft", "version": 1, "sha256": "1" * 64, "payload": draft}])

    def changed_draft_read(logical_key: str):
        if logical_key == "draft":
            return next(reads)
        return original_read(logical_key)

    monkeypatch.setattr(workspace, "read", changed_draft_read)
    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="WORK_DRAFT_CHANGED_DURING_CLOSEOUT_READ",
    ):
        work_draft_workspace.prepare_no_prose_closeout(
            workspace,
            _no_prose_action(),
        )
    assert _tree_bytes(runtime_root) == before


def test_no_prose_result_is_deep_copy_restart_stable_and_author_bound(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    alice = router.create_project("alice", "章槽项目")
    alice.commit("op-plan", {"plan": _plan()}, {"plan": 0})
    bob = router.create_project("bob", "章槽项目")
    bob.commit("op-bob-plan", {"plan": _plan()}, {"plan": 0})
    action = _no_prose_action()

    first = work_draft_workspace.prepare_no_prose_closeout(alice, action)
    expected_bytes = _canonical_bytes(first)
    first["closeout_action"]["actor"] = "provider"
    first["chapter_slot_source"]["generation_watermark"]["slot_rev"] = 999
    restarted = WorkspaceRouter(runtime_root).open_project(
        "alice", alice.project_id
    )
    second = work_draft_workspace.prepare_no_prose_closeout(restarted, action)
    assert _canonical_bytes(second) == expected_bytes

    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("alice", bob.project_id)
    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        work_draft_workspace.prepare_no_prose_closeout(  # type: ignore[arg-type]
            tmp_path,
            action,
        )
    assert list(
        inspect.signature(work_draft_workspace.prepare_no_prose_closeout).parameters
    ) == ["workspace", "action"]
