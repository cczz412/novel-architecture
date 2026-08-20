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
    from mvp import (
        chapter_slot_workspace,
        plan_workspace,
        work_draft_workspace,
        writing_check_package_tool,
        writing_check_result_tool,
        writing_check_result_workspace,
        writing_closeout_workspace,
    )
    from mvp.workspace import ProjectNotFoundError, WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:t14-closeout-alice"
BOB = "auth:t14-closeout-bob"
NOW = "2026-08-19 15:00:00"
PE_TEXT = "主角计划在下一章打开邀请信"
MUST_NOT = "不得把规划冒充事实"
TEXT = f"{PE_TEXT}。她没有立即答复。窗外传来一声雷。"


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _plan(*, slot_ref: str = "S-0001", pe_text: str = PE_TEXT) -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-FULL-CHECK-PREFLIGHT", "volumes_enabled": False},
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
                "must_not": [MUST_NOT],
                "risks": ["动机可能不足"],
                "target_length": 1200,
                "outline_checkpoint": {
                    "outline_rev": 2,
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


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _workspace(tmp_path: Path, principal: str = ALICE):
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime = tmp_path / principal.replace(":", "-")
    handle = WorkspaceRouter(runtime).create_project(principal, "T14 预检项目")
    return runtime, handle


def _save_draft(workspace, *, text: str = TEXT, expected_rev: int, operation_id: str):
    return work_draft_workspace.save_current_work_draft(
        workspace,
        {
            "operation_id": operation_id,
            "slot_ref": "S-0001",
            "source_outline_ref": "S-0001@outline-r2",
            "expected_rev": expected_rev,
            "entry_mode": "edited" if expected_rev else "typed",
            "author_text": text,
        },
    )


def _judgments(package: dict) -> list[dict]:
    refs = package["scope"]["requirement_refs"]
    return [
        {
            "category": "covered",
            "requirement_ref": refs[0],
            "evidence_quote": f"{PE_TEXT}。",
            "explanation": "原文写出了拆信前的计划。",
        },
        {
            "category": "missing",
            "requirement_ref": refs[1],
            "evidence_quote": None,
            "explanation": "禁令没有被正文触碰。",
        },
        {
            "category": "unplanned",
            "requirement_ref": None,
            "evidence_quote": "窗外传来一声雷。",
            "explanation": "这个细节不在已冻结 requirement 中。",
        },
    ]


def _seed(tmp_path: Path, *, principal: str = ALICE):
    runtime, workspace = _workspace(tmp_path, principal)
    plan_workspace.save_plan(workspace, "op-plan-setup", _plan(), 0)
    _save_draft(workspace, expected_rev=0, operation_id="op-work-save-r1")
    _save_draft(workspace, expected_rev=1, operation_id="op-work-save-r2")
    draft = work_draft_workspace.read_current_work_draft(workspace)[
        "current_work_draft"
    ]
    slot = chapter_slot_workspace.execute(workspace, "S-0001")
    package = writing_check_package_tool.execute(
        {
            "work_draft": draft,
            "chapter_slot_snapshot": slot,
            "check_operation_id": "op-t14-check-r2",
        }
    )
    result = writing_check_result_tool.execute(
        {
            "input_package": package,
            "provider_response": {"judgments": _judgments(package)},
        }
    )
    receipt = writing_check_result_workspace.save_writing_check_result(
        workspace,
        result["operation_id"],
        package,
        result,
        0,
        None,
    )
    action = {
        "contract": "WRITING_DESK_CLOSEOUT_ACTION",
        "version": "v1",
        "operation_id": "op-closeout-full-r2",
        "actor": "author",
        "slot_ref": "S-0001",
        "route": "full_check",
        "work_ref": "S-0001@work",
        "work_rev": 2,
        "check_result_ref": result["check_result_ref"],
    }
    return runtime, workspace, action, package, result, receipt


def test_full_check_preflight_ready_allows_mismatch_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, workspace, action, _, result, receipt = _seed(tmp_path)
    before = _tree_bytes(runtime)
    package_calls: list[dict] = []
    result_calls: list[dict] = []
    original_package = writing_check_package_tool.execute
    original_result = writing_check_result_tool.execute

    def capture_package(request: dict) -> dict:
        package_calls.append(copy.deepcopy(request))
        return original_package(request)

    def capture_result(request: dict) -> dict:
        result_calls.append(copy.deepcopy(request))
        return original_result(request)

    monkeypatch.setattr(writing_check_package_tool, "execute", capture_package)
    monkeypatch.setattr(writing_check_result_tool, "execute", capture_result)

    payload = writing_closeout_workspace.prepare_full_check_preflight(
        workspace, action
    )

    assert payload == {
        "status": "PREFLIGHT_READY",
        "closeout_action": action,
        "check_result_source": {
            "check_result_ref": result["check_result_ref"],
            "result_sha256": _sha(result),
            "version": 1,
            "sha256": receipt["payload_sha256"]["writing_check_results"],
        },
        "result": "completed_result_referenced",
        "handover_effect": "none",
        "chapter_close_effect": "none",
        "truth_effect": "none",
    }
    assert payload["handover_effect"] == "none"
    assert "pass" not in str(payload).lower()
    assert not (
        {"pass", "clean", "all_clear", "checked", "chapter_closed"} & set(payload)
    )
    assert any(
        row["category"] == "missing" for row in result["judgments"]
    )
    assert any(
        row["category"] == "unplanned" for row in result["judgments"]
    )
    assert len(package_calls) == 1
    assert len(result_calls) == 1
    assert result_calls[0]["provider_response"]["judgments"] == result["judgments"]
    assert _tree_bytes(runtime) == before
    assert workspace.read("facts") is None
    assert workspace.read("chapters") is None


def test_operation_id_may_contain_pass_or_checked_substring(tmp_path: Path) -> None:
    runtime, workspace, action, *_ = _seed(tmp_path)
    action["operation_id"] = "pass-checked-1"
    before = _tree_bytes(runtime)

    payload = writing_closeout_workspace.prepare_full_check_preflight(
        workspace, action
    )

    assert payload["status"] == "PREFLIGHT_READY"
    assert payload["result"] == "completed_result_referenced"
    assert payload["closeout_action"]["operation_id"] == "pass-checked-1"
    assert _tree_bytes(runtime) == before


def test_draft_one_character_change_is_stale_and_writes_nothing(tmp_path: Path) -> None:
    runtime, workspace, action, *_ = _seed(tmp_path)
    _save_draft(
        workspace,
        text=TEXT + "。",
        expected_rev=2,
        operation_id="op-work-save-r3",
    )
    before = _tree_bytes(runtime)

    with pytest.raises(
        writing_closeout_workspace.WritingCloseoutWorkspaceError,
        match="STALE_WORK_REVISION",
    ):
        writing_closeout_workspace.prepare_full_check_preflight(workspace, action)
    assert _tree_bytes(runtime) == before

    action["work_rev"] = 3
    with pytest.raises(
        writing_closeout_workspace.WritingCloseoutWorkspaceError,
        match="STALE_CHECK_RESULT",
    ):
        writing_closeout_workspace.prepare_full_check_preflight(workspace, action)
    assert _tree_bytes(runtime) == before


def test_plan_pe_change_is_stale_and_writes_nothing(tmp_path: Path) -> None:
    runtime, workspace, action, *_ = _seed(tmp_path)
    changed = _plan(pe_text="主角改口决定立刻赴约")
    plan_workspace.save_plan(workspace, "op-plan-pe-change", changed, 1)
    before = _tree_bytes(runtime)

    with pytest.raises(
        writing_closeout_workspace.WritingCloseoutWorkspaceError,
        match="STALE_CHECK_RESULT",
    ):
        writing_closeout_workspace.prepare_full_check_preflight(workspace, action)
    assert _tree_bytes(runtime) == before


@pytest.mark.parametrize(
    ("mutate", "expected_error"),
    [
        (lambda value: value.update(route="skip_check"), "FULL_CHECK_ROUTE_REQUIRED"),
        (
            lambda value: value.update(check_result_ref=None),
            "FULL_CHECK_RESULT_REF_REQUIRED",
        ),
        (
            lambda value: value.update(check_result_ref="missing-ref"),
            "CHECK_RESULT_REF_NOT_FOUND",
        ),
        (lambda value: value.update(work_rev=1), "STALE_WORK_REVISION"),
        (
            lambda value: value.update(slot_ref="S-9999"),
            "WORK_DRAFT_CLOSEOUT_REF_MISMATCH",
        ),
        (
            lambda value: value.update(actor="provider"),
            "WRITING_DESK_CLOSEOUT_ACTOR_INVALID",
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
def test_bad_action_or_missing_ref_writes_nothing(
    tmp_path: Path, mutate, expected_error: str
) -> None:
    runtime, workspace, action, *_ = _seed(tmp_path)
    mutate(action)
    before = _tree_bytes(runtime)
    with pytest.raises(
        writing_closeout_workspace.WritingCloseoutWorkspaceError,
        match=expected_error,
    ):
        writing_closeout_workspace.prepare_full_check_preflight(workspace, action)
    assert _tree_bytes(runtime) == before


def test_discards_when_draft_changes_between_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, workspace, action, *_ = _seed(tmp_path)
    stable = work_draft_workspace.read_current_work_draft(workspace)
    changed = copy.deepcopy(stable)
    changed["draft_workspace"]["version"] = 9
    changed["current_work_draft"]["work_rev"] = 9
    reads = iter([stable, changed])
    monkeypatch.setattr(
        work_draft_workspace,
        "read_current_work_draft",
        lambda _workspace: next(reads),
    )
    before = _tree_bytes(runtime)

    with pytest.raises(
        writing_closeout_workspace.WritingCloseoutWorkspaceError,
        match="WORK_DRAFT_CHANGED_DURING_PREFLIGHT_READ",
    ):
        writing_closeout_workspace.prepare_full_check_preflight(workspace, action)
    assert _tree_bytes(runtime) == before


def test_discards_when_slot_changes_between_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, workspace, action, *_ = _seed(tmp_path)
    stable = chapter_slot_workspace.execute(workspace, "S-0001")
    changed = copy.deepcopy(stable)
    changed["source_plan_sha256"] = "1" * 64
    reads = iter([stable, changed])
    monkeypatch.setattr(
        chapter_slot_workspace,
        "execute",
        lambda _workspace, _slot_ref: next(reads),
    )
    before = _tree_bytes(runtime)

    with pytest.raises(
        writing_closeout_workspace.WritingCloseoutWorkspaceError,
        match="CHAPTER_SLOT_CHANGED_DURING_PREFLIGHT_READ",
    ):
        writing_closeout_workspace.prepare_full_check_preflight(workspace, action)
    assert _tree_bytes(runtime) == before


def test_discards_when_owner_changes_before_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, workspace, action, *_ = _seed(tmp_path)
    original = writing_check_result_workspace.resolve_writing_check_result
    calls = {"n": 0}

    def flipped(handle, check_result_ref: str) -> dict:
        loaded = original(handle, check_result_ref)
        calls["n"] += 1
        if calls["n"] == 1:
            return loaded
        changed = copy.deepcopy(loaded)
        changed["version"] = loaded["version"] + 1
        changed["sha256"] = "2" * 64
        return changed

    monkeypatch.setattr(
        writing_check_result_workspace,
        "resolve_writing_check_result",
        flipped,
    )
    before = _tree_bytes(runtime)

    with pytest.raises(
        writing_closeout_workspace.WritingCloseoutWorkspaceError,
        match="CHECK_RESULT_OWNER_CHANGED_DURING_PREFLIGHT_READ",
    ):
        writing_closeout_workspace.prepare_full_check_preflight(workspace, action)
    assert _tree_bytes(runtime) == before


def test_restart_is_byte_equivalent_and_output_is_deep_copy(tmp_path: Path) -> None:
    runtime, workspace, action, *_ = _seed(tmp_path)
    first = writing_closeout_workspace.prepare_full_check_preflight(workspace, action)
    first_bytes = _canonical_bytes(first)
    first["closeout_action"]["actor"] = "provider"
    first["check_result_source"]["sha256"] = "0" * 64

    restarted = WorkspaceRouter(runtime).open_project(ALICE, workspace.project_id)
    second = writing_closeout_workspace.prepare_full_check_preflight(
        restarted, action
    )
    assert _canonical_bytes(second) == first_bytes


def test_alice_cannot_use_bob_result_and_path_is_rejected(tmp_path: Path) -> None:
    alice_runtime, alice = _workspace(tmp_path, principal=ALICE)
    _, bob, bob_action, *_rest = _seed(tmp_path, principal=BOB)
    alice_action = copy.deepcopy(bob_action)

    with pytest.raises(
        writing_closeout_workspace.WritingCloseoutWorkspaceError,
        match="CHECK_RESULT_REF_NOT_FOUND",
    ):
        writing_closeout_workspace.prepare_full_check_preflight(alice, bob_action)
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        WorkspaceRouter(alice_runtime).open_project(ALICE, bob.project_id)
    with pytest.raises(
        writing_closeout_workspace.WritingCloseoutWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        writing_closeout_workspace.prepare_full_check_preflight(  # type: ignore[arg-type]
            tmp_path, alice_action
        )
    assert list(
        inspect.signature(
            writing_closeout_workspace.prepare_full_check_preflight
        ).parameters
    ) == ["workspace", "action"]


def test_corrupt_results_store_fails_closed(tmp_path: Path) -> None:
    runtime, workspace, action, *_ = _seed(tmp_path)
    workspace.commit(
        "op-corrupt-results",
        {"writing_check_results": {"schema": "broken", "results": {}}},
        {"writing_check_results": 1},
    )
    before = _tree_bytes(runtime)
    with pytest.raises(
        writing_closeout_workspace.WritingCloseoutWorkspaceError,
        match="RESULTS_STORE_INVALID",
    ):
        writing_closeout_workspace.prepare_full_check_preflight(workspace, action)
    assert _tree_bytes(runtime) == before
