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
        chapter_slot_workspace,
        plan_workspace,
        work_draft_workspace,
        writing_check_package_tool,
        writing_check_result_tool,
        writing_check_result_workspace,
        writing_check_unknown_adjudication_workspace,
    )
    from mvp.workspace import VersionConflictError, WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:t14-unknown-alice"
BOB = "auth:t14-unknown-bob"
NOW = "2026-08-20 15:00:00"
PE_TEXT = "林乔拆开邀请信"
MUST_NOT = "不得让林乔当场答应赴约"
TEXT = "林乔拆开邀请信。她没有立即答复。窗外传来一声雷。"


def _plan(*, pe_text: str = PE_TEXT) -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-T14-UNKNOWN", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "goal": "让主角决定是否赴约",
                "summary": "这是未来规划，不是已经发生的事实",
                "entry_state": "邀请仍未答复",
                "storyline_refs": ["L-0001"],
                "scene_refs": ["SCN-0001"],
                "exit_condition": "主角作出选择",
                "exit_hook": "选择影响下一章",
                "must_not": [MUST_NOT],
                "risks": ["动机可能不足"],
                "target_length": 1200,
                "outline_checkpoint": {
                    "outline_rev": 2,
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
                "text": pe_text,
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


def _save_draft(workspace, *, operation_id: str, expected_rev: int, text: str = TEXT):
    return work_draft_workspace.save_current_work_draft(
        workspace,
        {
            "operation_id": operation_id,
            "slot_ref": "S-0001",
            "source_outline_ref": "S-0001@outline-r2",
            "expected_rev": expected_rev,
            "entry_mode": "typed" if expected_rev == 0 else "edited",
            "author_text": text,
        },
    )


def _seed(tmp_path: Path, *, principal: str = ALICE):
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime = tmp_path / principal.replace(":", "-")
    workspace = WorkspaceRouter(runtime).create_project(principal, "T14 unknown 项目")
    plan_workspace.save_plan(workspace, "save-plan", _plan(), 0)
    _save_draft(workspace, operation_id="save-draft-r1", expected_rev=0)
    draft = work_draft_workspace.read_current_work_draft(workspace)[
        "current_work_draft"
    ]
    slot = chapter_slot_workspace.execute(workspace, "S-0001")
    package = writing_check_package_tool.execute(
        {
            "work_draft": draft,
            "chapter_slot_snapshot": slot,
            "check_operation_id": "check-unknown-r1",
        }
    )
    refs = package["scope"]["requirement_refs"]
    judgments = [
        {
            "category": "unknown",
            "requirement_ref": refs[0],
            "evidence_quote": None,
            "explanation": "当前材料不足，无法安全判断是否完整承接。",
        },
        {
            "category": "unknown",
            "requirement_ref": refs[1],
            "evidence_quote": "她没有立即答复。",
            "explanation": "有相关原文，但仍无法确定是否触碰禁令。",
        },
    ]
    result = writing_check_result_tool.execute(
        {
            "input_package": package,
            "provider_response": {"judgments": judgments},
        }
    )
    writing_check_result_workspace.save_writing_check_result(
        workspace,
        result["operation_id"],
        package,
        result,
        0,
        None,
    )
    return runtime, workspace, package, result


def _action(
    result: dict,
    judgment: dict,
    *,
    operation_id: str = "author-adjudicate-unknown-1",
    decision: str = "covered",
) -> dict:
    return {
        "contract": "WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION",
        "version": "v1",
        "operation_id": operation_id,
        "actor": "author",
        "check_result_ref": result["check_result_ref"],
        "finding_ref": writing_check_result_tool.finding_ref(
            result["check_result_ref"], judgment
        ),
        "work_ref": result["work_ref"],
        "work_rev": result["work_rev"],
        "source_outline_ref": result["source_outline_ref"],
        "source_commit_seq": result["source_commit_seq"],
        "decision": decision,
    }


def test_null_quote_unknown_records_self_reported_overlay_and_keeps_parent(
    tmp_path: Path,
) -> None:
    runtime, workspace, _, result = _seed(tmp_path)
    original = copy.deepcopy(result)
    action = _action(result, result["judgments"][0])

    recorded = writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
        workspace,
        action,
    )
    reopened = WorkspaceRouter(runtime).open_project(ALICE, workspace.project_id)
    stored = writing_check_result_workspace.resolve_writing_check_result_entry(
        reopened,
        result["check_result_ref"],
    )

    assert recorded["status"] == "RECORDED"
    assert recorded["replayed"] is False
    assert recorded["evidence_text_kind"] == "unknown_without_quote"
    assert recorded["receipt"] == stored["unknown_overlays"][0]
    assert recorded["receipt"]["basis"] == "self_reported"
    assert recorded["receipt"]["decision"] == "covered"
    assert stored["result"] == original
    assert stored["result"]["judgments"][0]["category"] == "unknown"
    assert recorded["effects"] == {
        "check_result": "unchanged_unknown",
        "work_draft": "none",
        "plan": "none",
        "facts": "none",
        "handover": "none",
    }


def test_unknown_with_quote_records_second_distinct_overlay(tmp_path: Path) -> None:
    _, workspace, _, result = _seed(tmp_path)
    first = _action(result, result["judgments"][0])
    second = _action(
        result,
        result["judgments"][1],
        operation_id="author-adjudicate-unknown-2",
        decision="mismatch",
    )
    writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
        workspace, first
    )

    recorded = writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
        workspace, second
    )
    stored = writing_check_result_workspace.resolve_writing_check_result_entry(
        workspace, result["check_result_ref"]
    )

    assert recorded["evidence_text_kind"] == "unknown_with_quote"
    assert [row["decision"] for row in stored["unknown_overlays"]] == [
        "covered",
        "mismatch",
    ]
    assert stored["result"] == result


def test_exact_replay_is_zero_write_and_changed_payload_conflicts(tmp_path: Path) -> None:
    runtime, workspace, _, result = _seed(tmp_path)
    action = _action(result, result["judgments"][0])
    first = writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
        workspace, action
    )
    before = _tree_bytes(_project_dir(runtime, workspace))

    replay = writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
        workspace, copy.deepcopy(action)
    )
    changed = {**action, "decision": "missing"}

    assert replay["replayed"] is True
    assert replay["receipt"] == first["receipt"]
    assert _tree_bytes(_project_dir(runtime, workspace)) == before
    with pytest.raises(
        writing_check_unknown_adjudication_workspace.WritingCheckUnknownAdjudicationWorkspaceError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_ACTION",
    ):
        writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
            workspace, changed
        )
    assert _tree_bytes(_project_dir(runtime, workspace)) == before


def test_same_finding_cannot_receive_a_second_decision(tmp_path: Path) -> None:
    _, workspace, _, result = _seed(tmp_path)
    first = _action(result, result["judgments"][0])
    second = _action(
        result,
        result["judgments"][0],
        operation_id="author-adjudicate-same-finding-again",
        decision="missing",
    )
    writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
        workspace, first
    )

    with pytest.raises(
        writing_check_unknown_adjudication_workspace.WritingCheckUnknownAdjudicationWorkspaceError,
        match="UNKNOWN_FINDING_ALREADY_ADJUDICATED",
    ):
        writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
            workspace, second
        )


@pytest.mark.parametrize(
    ("damage", "error"),
    [
        ("actor", "UNKNOWN_ADJUDICATION_ACTION_INVALID"),
        ("decision", "UNKNOWN_ADJUDICATION_ACTION_INVALID"),
        ("extra", "UNKNOWN_ADJUDICATION_ACTION_INVALID"),
        ("finding", "UNKNOWN_FINDING_NOT_FOUND"),
        ("work", "UNKNOWN_ADJUDICATION_PARENT_MISMATCH"),
        ("outline", "UNKNOWN_ADJUDICATION_PARENT_MISMATCH"),
    ],
)
def test_bad_action_or_parent_identity_has_zero_write(
    tmp_path: Path,
    damage: str,
    error: str,
) -> None:
    runtime, workspace, _, result = _seed(tmp_path)
    action = _action(result, result["judgments"][0])
    if damage == "actor":
        action["actor"] = "model"
    elif damage == "decision":
        action["decision"] = "unknown"
    elif damage == "extra":
        action["explanation"] = "不允许夹带说明"
    elif damage == "finding":
        action["finding_ref"] = f"{result['check_result_ref']}#finding:{'0' * 12}"
    elif damage == "work":
        action["work_rev"] = 99
    else:
        action["source_outline_ref"] = "S-0001@outline-r99"
    before = _tree_bytes(_project_dir(runtime, workspace))

    with pytest.raises(
        writing_check_unknown_adjudication_workspace.WritingCheckUnknownAdjudicationWorkspaceError,
        match=error,
    ):
        writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
            workspace, action
        )

    assert _tree_bytes(_project_dir(runtime, workspace)) == before


@pytest.mark.parametrize("stale_source", ["draft", "plan"])
def test_stale_work_or_plan_rejects_without_overlay(
    tmp_path: Path,
    stale_source: str,
) -> None:
    runtime, workspace, _, result = _seed(tmp_path)
    action = _action(result, result["judgments"][0])
    if stale_source == "draft":
        _save_draft(
            workspace,
            operation_id="edit-draft-r2",
            expected_rev=1,
            text=f"{TEXT}又补了一句。",
        )
    else:
        changed = _plan(pe_text="林乔决定把信压在桌角")
        plan_workspace.save_plan(workspace, "change-plan", changed, 1)
    before = _tree_bytes(_project_dir(runtime, workspace))

    with pytest.raises(
        writing_check_unknown_adjudication_workspace.WritingCheckUnknownAdjudicationWorkspaceError,
        match="CURRENT_CHECK_RESULT_REJECTED",
    ):
        writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
            workspace, action
        )

    assert _tree_bytes(_project_dir(runtime, workspace)) == before
    stored = writing_check_result_workspace.resolve_writing_check_result_entry(
        workspace, result["check_result_ref"]
    )
    assert stored["unknown_overlays"] == []


def test_guarded_commit_closes_current_source_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace, _, result = _seed(tmp_path)
    action = _action(result, result["judgments"][0])
    original = workspace.commit_guarded

    def race(operation_id, mutations, expected_versions, guard_versions):
        _save_draft(
            workspace,
            operation_id="race-edit-r2",
            expected_rev=1,
            text=f"{TEXT}竞态改动。",
        )
        return original(
            operation_id,
            mutations,
            expected_versions,
            guard_versions,
        )

    monkeypatch.setattr(workspace, "commit_guarded", race)

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
            workspace, action
        )
    stored = writing_check_result_workspace.resolve_writing_check_result_entry(
        workspace, result["check_result_ref"]
    )
    assert stored["unknown_overlays"] == []


def test_path_and_other_author_cannot_read_or_write_overlay(tmp_path: Path) -> None:
    runtime, alice, _, result = _seed(tmp_path / "alice")
    action = _action(result, result["judgments"][0])
    bob = WorkspaceRouter(runtime).create_project(BOB, "Bob 项目")

    with pytest.raises(
        writing_check_unknown_adjudication_workspace.WritingCheckUnknownAdjudicationWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
            tmp_path, action  # type: ignore[arg-type]
        )
    with pytest.raises(
        writing_check_unknown_adjudication_workspace.WritingCheckUnknownAdjudicationWorkspaceError,
        match="CHECK_RESULT_REF_NOT_FOUND",
    ):
        writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
            bob, action
        )
    assert writing_check_result_workspace.resolve_writing_check_result_entry(
        alice, result["check_result_ref"]
    )["unknown_overlays"] == []


def test_corrupt_overlay_is_rejected_on_read(tmp_path: Path) -> None:
    _, workspace, _, result = _seed(tmp_path)
    current = workspace.read("writing_check_results")
    corrupt = copy.deepcopy(current["payload"])
    corrupt["results"][result["check_result_ref"]]["unknown_overlays"] = [
        {"status": "recorded"}
    ]
    workspace.commit(
        "inject-corrupt-overlay",
        {"writing_check_results": corrupt},
        {"writing_check_results": current["version"]},
    )

    with pytest.raises(
        writing_check_result_workspace.WritingCheckResultWorkspaceError,
        match="UNKNOWN_ADJUDICATION_RECEIPT_INVALID",
    ):
        writing_check_result_workspace.resolve_writing_check_result_entry(
            workspace, result["check_result_ref"]
        )


def test_result_and_action_stay_json_serializable(tmp_path: Path) -> None:
    _, workspace, _, result = _seed(tmp_path)
    action = _action(result, result["judgments"][0])
    recorded = writing_check_unknown_adjudication_workspace.record_unknown_adjudication(
        workspace, action
    )
    assert json.loads(json.dumps(recorded, ensure_ascii=False)) == recorded
