from __future__ import annotations

import copy
import hashlib
import inspect
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        chapter_handover_workspace,
        chapter_initial_admission_workspace,
        plan_workspace,
        work_draft_workspace,
    )
    from mvp.workspace import InjectedWorkspaceCrash, VersionConflictError, WorkspaceRouter
finally:
    sys.path.pop(0)


TEXT = "林乔在雨夜拆开那封信。" * 80
ADMITTED_AT = "2026-08-20T03:00:00+08:00"
HANDED_AT = "2026-08-20T03:05:00+08:00"
ADMISSION_ID = "op-handover-aw-admit"
PLAN_OPERATION_ID = "op-handover-plan"


def _plan(*, outline_rev: int = 2) -> dict:
    now = "2026-08-20 02:30:00"
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-HANDOVER", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "goal": "让林乔读信",
                "summary": "雨夜收到来信",
                "entry_state": "信尚未拆开",
                "storyline_refs": [],
                "scene_refs": ["SCN-0001"],
                "exit_condition": "林乔读完信",
                "exit_hook": "信中提到失踪者",
                "must_not": ["不得把规划当事实"],
                "risks": [],
                "target_length": 1600,
                "outline_checkpoint": {
                    "outline_rev": outline_rev,
                    "source_slot_ref": "S-0001",
                    "source_commit_seq": 12,
                },
                "slot_status": "planned",
                "handover_parts": [],
                "truth_bearing": "primary",
                "updated_at": now,
                "rev": 3,
            }
        ],
        "scenes": [
            {
                "id": "SCN-0001",
                "slot_ref": "S-0001",
                "goal": "拆信",
                "summary": "林乔拆开来信",
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
                "text": "林乔计划拆开来信",
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


def _handover_action() -> dict:
    return {
        "contract": "WORK_DRAFT_HANDOVER_ACTION",
        "version": "v2",
        "operation_id": ADMISSION_ID,
        "actor": "author",
        "intent": "adopt_as_manuscript",
        "work_ref": "S-0001@work",
        "work_rev": 1,
        "slot_ref": "S-0001",
        "source_outline_ref": "S-0001@outline-r2",
        "chapter_title": "第一章 雨夜来信",
        "target_contract": "C1_CHAPTER_DOC",
        "target_planstore_result": "handover_parts",
    }


def _setup(tmp_path: Path):
    runtime = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime).create_project("author:alice", "作者项目")
    plan_workspace.save_plan(workspace, "op-plan-seed", _plan(), 0)
    work_draft_workspace.save_current_work_draft(
        workspace,
        {
            "operation_id": "op-work-seed",
            "slot_ref": "S-0001",
            "source_outline_ref": "S-0001@outline-r2",
            "expected_rev": 0,
            "entry_mode": "typed",
            "author_text": TEXT,
        },
    )
    chapter_initial_admission_workspace.commit_initial_work_draft(
        workspace,
        _handover_action(),
        ADMITTED_AT,
    )
    return runtime, workspace


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_pending_chapter_is_mapped_without_creating_a_second_c1(tmp_path: Path) -> None:
    runtime, workspace = _setup(tmp_path)
    chapters_before = copy.deepcopy(workspace.read("chapters"))
    ledger_before = copy.deepcopy(workspace.read("chapter_revisions"))

    result = chapter_handover_workspace.complete_pending_handover(
        workspace,
        ADMISSION_ID,
        PLAN_OPERATION_ID,
        HANDED_AT,
    )

    assert result["status"] == "HANDOVER_COMPLETE"
    assert result["replayed"] is False
    assert result["chapter_revision_ref"]["chapter_id"] == "c01"
    assert result["mapping"] == {
        "id": "MAP-0001",
        "slot_ref": "S-0001",
        "chapter_id": "c01",
        "expected_chapter_no": 1,
        "mapping_kind": "as_written",
        "reason": "",
        "decided_by": "author",
        "mapping_status": "active",
        "superseded_by": None,
    }
    assert result["handover_part"] == {
        "part_no": 1,
        "chapter_id": "c01",
        "covered_scene_refs": ["SCN-0001"],
        "covered_pe_refs": ["PE-0001"],
        "handed_at": "2026-08-20 03:05:00",
        "decided_by": "author",
    }
    assert result["chapter_write"] == 0
    assert workspace.read("chapters") == chapters_before
    assert workspace.read("chapter_revisions") == ledger_before
    assert workspace.read("chapters")["payload"] == [
        chapter_initial_admission_workspace.resolve_initial_admission(
            workspace, ADMISSION_ID
        )["chapter"]
    ]
    plan = plan_workspace.read_plan(workspace)["plan"]
    assert plan["slots"][0]["slot_status"] == "handed_over"
    assert plan["slots"][0]["truth_bearing"] == "handed_over"
    assert plan["scenes"][0]["truth_bearing"] == "handed_over"
    assert plan["events"][0]["truth_bearing"] == "handed_over"
    assert plan["id_counters"]["MAP"] == 1

    reopened = WorkspaceRouter(runtime).open_project(
        "author:alice", workspace.project_id
    )
    resolved = chapter_initial_admission_workspace.resolve_initial_admission(
        reopened, ADMISSION_ID
    )
    assert resolved["status"] == "HANDOVER_COMPLETE"
    assert resolved["planstore_write"] == 1
    assert resolved["plan_handover"]["mapping_id"] == "MAP-0001"
    marker = reopened.read("chapter_admission_operations")["payload"][
        "operations"
    ][ADMISSION_ID]["plan_handover"]
    assert marker["operation_id"] == PLAN_OPERATION_ID
    assert marker["mapping_id"] == "MAP-0001"
    assert marker["plan_version"] == 2


def test_exact_replay_after_restart_is_zero_write(tmp_path: Path) -> None:
    runtime, workspace = _setup(tmp_path)
    first = chapter_handover_workspace.complete_pending_handover(
        workspace, ADMISSION_ID, PLAN_OPERATION_ID, HANDED_AT
    )
    before = _tree_bytes(runtime)
    reopened = WorkspaceRouter(runtime).open_project(
        "author:alice", workspace.project_id
    )

    replay = chapter_handover_workspace.complete_pending_handover(
        reopened, ADMISSION_ID, PLAN_OPERATION_ID, HANDED_AT
    )

    assert replay["replayed"] is True
    assert replay["mapping"] == first["mapping"]
    assert replay["handover_part"] == first["handover_part"]
    assert _tree_bytes(runtime) == before
    with pytest.raises(
        chapter_handover_workspace.ChapterHandoverWorkspaceError,
        match="PLAN_HANDOVER_ALREADY_COMPLETED_WITH_DIFFERENT_REQUEST",
    ):
        chapter_handover_workspace.complete_pending_handover(
            reopened,
            ADMISSION_ID,
            "op-another-plan-handover",
            HANDED_AT,
        )
    assert _tree_bytes(runtime) == before


def test_outline_change_keeps_formal_chapter_and_pending_marker(
    tmp_path: Path,
) -> None:
    _, workspace = _setup(tmp_path)
    plan_workspace.save_plan(workspace, "op-outline-r3", _plan(outline_rev=3), 1)
    chapter_before = copy.deepcopy(workspace.read("chapters"))
    operations_before = copy.deepcopy(
        workspace.read("chapter_admission_operations")
    )

    with pytest.raises(
        chapter_handover_workspace.ChapterHandoverWorkspaceError,
        match="OUTLINE_NOT_CURRENT",
    ):
        chapter_handover_workspace.complete_pending_handover(
            workspace, ADMISSION_ID, PLAN_OPERATION_ID, HANDED_AT
        )

    assert workspace.read("chapters") == chapter_before
    assert workspace.read("chapter_admission_operations") == operations_before
    assert operations_before["payload"]["operations"][ADMISSION_ID]["stage"] == (
        "AW_COMMITTED_PLANSTORE_PENDING"
    )


def test_plan_race_rejects_without_completing_pending_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace = _setup(tmp_path)
    original = workspace.commit_guarded

    def race(operation_id, mutations, expected_versions, guard_versions):
        changed = copy.deepcopy(plan_workspace.read_plan(workspace)["plan"])
        changed["slots"][0]["summary"] = "作者同时修改了当前规划"
        plan_workspace.save_plan(workspace, "op-plan-race", changed, 1)
        return original(
            operation_id,
            mutations,
            expected_versions,
            guard_versions,
        )

    monkeypatch.setattr(workspace, "commit_guarded", race)
    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        chapter_handover_workspace.complete_pending_handover(
            workspace, ADMISSION_ID, PLAN_OPERATION_ID, HANDED_AT
        )

    operation = workspace.read("chapter_admission_operations")["payload"][
        "operations"
    ][ADMISSION_ID]
    assert operation["stage"] == "AW_COMMITTED_PLANSTORE_PENDING"
    assert operation["plan_handover"] is None
    assert workspace.read("chapters")["payload"][0]["id"] == "c01"
    assert workspace.read("plan")["payload"]["slot_mappings"] == []


def test_crash_after_pointer_is_recovered_as_one_complete_handover(
    tmp_path: Path,
) -> None:
    _, workspace = _setup(tmp_path)

    def fail(point: str) -> None:
        if point == "after_pointer_swap":
            raise InjectedWorkspaceCrash(point)

    workspace._backend._failure_hook = fail
    with pytest.raises(InjectedWorkspaceCrash, match="after_pointer_swap"):
        chapter_handover_workspace.complete_pending_handover(
            workspace, ADMISSION_ID, PLAN_OPERATION_ID, HANDED_AT
        )
    assert workspace.read("chapter_admission_operations")["payload"][
        "operations"
    ][ADMISSION_ID]["stage"] == "HANDOVER_COMPLETE"
    assert len(workspace.read("plan")["payload"]["slot_mappings"]) == 1

    workspace._backend._failure_hook = None
    replay = chapter_handover_workspace.complete_pending_handover(
        workspace, ADMISSION_ID, PLAN_OPERATION_ID, HANDED_AT
    )
    assert replay["replayed"] is True
    assert len(workspace.read("plan")["payload"]["slot_mappings"]) == 1
    assert workspace.recover()["status"] == "NO_RECOVERY_NEEDED"


def test_missing_plan_bad_ids_and_path_impostor_fail_closed(tmp_path: Path) -> None:
    no_plan = WorkspaceRouter(tmp_path / "no-plan").create_project(
        "author:alice", "项目"
    )
    work_draft_workspace.save_current_work_draft(
        no_plan,
        {
            "operation_id": "op-work-seed",
            "slot_ref": "S-0001",
            "source_outline_ref": "S-0001@outline-r2",
            "expected_rev": 0,
            "entry_mode": "typed",
            "author_text": TEXT,
        },
    )
    chapter_initial_admission_workspace.commit_initial_work_draft(
        no_plan, _handover_action(), ADMITTED_AT
    )
    with pytest.raises(
        chapter_handover_workspace.ChapterHandoverWorkspaceError,
        match="CURRENT_PLAN_REQUIRED",
    ):
        chapter_handover_workspace.complete_pending_handover(
            no_plan, ADMISSION_ID, PLAN_OPERATION_ID, HANDED_AT
        )
    assert no_plan.read("chapters")["payload"][0]["id"] == "c01"

    with pytest.raises(
        chapter_handover_workspace.ChapterHandoverWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        chapter_handover_workspace.complete_pending_handover(
            Path("/tmp/not-a-workspace"),
            ADMISSION_ID,
            PLAN_OPERATION_ID,
            HANDED_AT,
        )
    assert list(
        inspect.signature(
            chapter_handover_workspace.complete_pending_handover
        ).parameters
    ) == [
        "workspace",
        "admission_operation_id",
        "plan_operation_id",
        "handed_at",
    ]


def test_plan_sha_marker_matches_exact_committed_payload(tmp_path: Path) -> None:
    _, workspace = _setup(tmp_path)
    result = chapter_handover_workspace.complete_pending_handover(
        workspace, ADMISSION_ID, PLAN_OPERATION_ID, HANDED_AT
    )
    plan_entry = workspace.read("plan")
    marker = result["plan_commit"]
    assert marker["plan_version"] == plan_entry["version"]
    assert marker["plan_sha256"] == plan_entry["sha256"]
    assert marker["plan_sha256"] == hashlib.sha256(
        (
            __import__("json").dumps(
                plan_entry["payload"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    ).hexdigest()
