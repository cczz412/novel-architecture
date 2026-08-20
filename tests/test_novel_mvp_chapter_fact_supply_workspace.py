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
    from mvp import chapter_fact_supply_workspace, plan_workspace
    from mvp.workspace import WorkspaceRouter
finally:
    sys.path.pop(0)


NOW = "2026-08-20 10:00:00"


def _option_record(
    record_id: str,
    *,
    event_ref: str,
    slot_ref: str = "S-0001",
    group_status: str = "active",
) -> dict:
    return {
        "id": record_id,
        "slot_ref": slot_ref,
        "question": "本章采用哪条已经落位的规划？",
        "options": [
            {
                "key": "A",
                "summary": "已选方向",
                "why_fit": "符合当前规划",
                "changes": "推进当前计划事件",
                "risks": "动机需要写清",
                "digest_refs": [event_ref],
            },
            {
                "key": "B",
                "summary": "未选择候选绝不能进入供料",
                "why_fit": "只是候选",
                "changes": "未落账 C7 变化绝不能进入供料",
                "risks": "C7 主推荐绝不能进入供料",
                "digest_refs": [],
            },
        ],
        "chosen_key": "A" if group_status == "active" else None,
        "decided_by": "author",
        "decided_at": NOW,
        "digest_applied": [event_ref] if group_status == "active" else [],
        "variant_note": None,
        "card_ref": "AC-0001",
        "recommended_key": "B",
        "group_status": group_status,
        "source_identity": "author_declared",
        "created_at": NOW,
        "updated_at": NOW,
        "rev": 1,
        "note": "冲突问句与写作指导不得进入供料",
    }


def _event(
    event_ref: str,
    *,
    scene_ref: str,
    storyline_ref: str,
    text: str,
    digest_status: str,
    digest_ref: str | None,
    rev: int,
) -> dict:
    return {
        "id": event_ref,
        "text": text,
        "scene_ref": scene_ref,
        "storyline_ref": storyline_ref,
        "purpose": "advance",
        "hook_links": [],
        "story_time_hint": "雨夜",
        "digest_status": digest_status,
        "digest_ref": digest_ref,
        "origin_ref": "AC-0001",
        "repair_ref": None,
        "deviation_note": None,
        "defer_count": 0,
        "truth_bearing": "primary",
        "prose_status": "unwritten",
        "prose_basis": None,
        "impact": "normal",
        "source_identity": "author_declared",
        "created_at": NOW,
        "updated_at": NOW,
        "rev": rev,
        "note": "",
    }


def _plan() -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-FACT-SUPPLY", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "goal": "让林照在下一章完成送信决定",
                "summary": "两场依次完成接信与决定",
                "entry_state": "双方互不信任",
                "storyline_refs": ["L-0001", "L-0002"],
                "scene_refs": ["SCN-0001", "SCN-0002"],
                "exit_condition": "林照明确接受送信",
                "exit_hook": "寄件人身份仍未知",
                "must_not": ["不得提前揭晓寄件人"],
                "risks": ["动机可能不足"],
                "target_length": 1800,
                "outline_checkpoint": {
                    "outline_rev": 2,
                    "source_slot_ref": "S-0001",
                    "source_commit_seq": 8,
                },
                "slot_status": "planned",
                "handover_parts": [],
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 3,
            }
        ],
        "scenes": [
            {
                "id": "SCN-0001",
                "slot_ref": "S-0001",
                "goal": "完成密封信交接",
                "summary": "许岚在雨巷交信",
                "location": "纸灯巷口",
                "characters": ["CH-0001", "CH-0002"],
                "pe_refs": ["PE-0001", "PE-0002"],
                "mood_in": "戒备",
                "mood_out": "试探",
                "visual_hint": "雨水打碎纸灯倒影",
                "dialogue_hints": ["只透露天亮前必须送达"],
                "resistance": "双方不肯说明来源",
                "turn": "许岚交出密封信",
                "pov": "CH-0001",
                "spoiler_notes": ["不得展示信内页"],
                "word_estimate": 900,
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 4,
            },
            {
                "id": "SCN-0002",
                "slot_ref": "S-0001",
                "goal": "作出送信决定",
                "summary": "林照确认共同送信",
                "location": "旧茶摊",
                "characters": ["CH-0001"],
                "pe_refs": ["PE-0003", "PE-0004"],
                "mood_in": "犹豫",
                "mood_out": "坚定",
                "visual_hint": None,
                "dialogue_hints": [],
                "resistance": "时间紧迫",
                "turn": "林照收起密封信",
                "pov": "CH-0001",
                "spoiler_notes": ["不得确认幕后人"],
                "word_estimate": 900,
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 5,
            },
        ],
        "events": [
            _event(
                "PE-0001",
                scene_ref="SCN-0001",
                storyline_ref="L-0001",
                text="许岚计划把密封信交给林照",
                digest_status="digested",
                digest_ref="OPT-0001",
                rev=7,
            ),
            _event(
                "PE-0002",
                scene_ref="SCN-0001",
                storyline_ref="L-0001",
                text="pending 候选事件绝不能进入供料",
                digest_status="pending",
                digest_ref=None,
                rev=1,
            ),
            _event(
                "PE-0003",
                scene_ref="SCN-0002",
                storyline_ref="L-0002",
                text="林照计划接受共同送信",
                digest_status="digested",
                digest_ref="OPT-0002",
                rev=8,
            ),
            _event(
                "PE-0004",
                scene_ref="SCN-0002",
                storyline_ref="L-0002",
                text="被驳回事件绝不能进入供料",
                digest_status="voided",
                digest_ref="OPT-VOID",
                rev=2,
            ),
        ],
        "storylines": [
            {
                "id": "L-0001",
                "name": "密封信去向",
                "alias": "送信线",
                "priority": 1,
                "members": ["CH-0001", "CH-0002"],
                "line_status": "active",
                "rev": 2,
            },
            {
                "id": "L-0002",
                "name": "寄件人身份",
                "alias": None,
                "priority": 2,
                "members": ["CH-0001"],
                "line_status": "paused",
                "rev": 3,
            },
        ],
        "hooks": [],
        "widgets": [],
        "pins": [],
        "must_carries": [],
        "option_records": [
            _option_record("OPT-0001", event_ref="PE-0001"),
            _option_record("OPT-0002", event_ref="PE-0003"),
            _option_record(
                "OPT-VOID", event_ref="PE-0004", group_status="discarded"
            ),
        ],
        "slot_mappings": [],
        "reconciliation_edges": [],
        "stop_points": {
            "P3": {"blocked_reason": "被停点挡住的候选绝不能进入供料"}
        },
        "id_counters": {"MAP": 0, "RE": 0},
    }


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _plan_entry(plan: dict, *, version: int = 1) -> dict:
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


def _workspace_with_plan(tmp_path: Path, *, principal: str = "auth:alice"):
    runtime_root = tmp_path / principal.replace(":", "-")
    workspace = WorkspaceRouter(runtime_root).create_project(principal, "供料项目")
    plan_workspace.save_plan(workspace, "op-plan-setup", _plan(), 0)
    return runtime_root, workspace


def test_stable_current_plan_emits_only_landed_materials_in_plan_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root, workspace = _workspace_with_plan(tmp_path)
    project_dir = _project_dir(runtime_root, workspace)
    before_tree = _tree_bytes(project_dir)
    before_plan = plan_workspace.read_plan(workspace)
    monkeypatch.setattr(
        workspace,
        "commit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("只读供料器不得写工作区")
        ),
    )

    result = chapter_fact_supply_workspace.execute(workspace, "S-0001")

    assert result["identity"] == "SUPPLY_CANDIDATE"
    assert result["not_c11"] is True
    assert result["not_fact"] is True
    assert result["author_handover"] is False
    assert result["writes"] == "none"
    assert result["outline_checkpoint"] == {
        "outline_rev": 2,
        "source_slot_ref": "S-0001",
        "source_commit_seq": 8,
    }
    assert [item["id"] for item in result["future_event_materials"]] == [
        "PE-0001",
        "PE-0003",
    ]
    assert [item["text"] for item in result["future_event_materials"]] == [
        "许岚计划把密封信交给林照",
        "林照计划接受共同送信",
    ]
    assert [item["id"] for item in result["writing_note_sources"]["scenes"]] == [
        "SCN-0001",
        "SCN-0002",
    ]
    assert result["writing_note_sources"]["chapter"]["must_not"] == [
        "不得提前揭晓寄件人"
    ]
    assert result["writing_note_sources"]["scenes"][0]["dialogue_hints"] == [
        "只透露天亮前必须送达"
    ]
    assert "visual_hint" not in result["writing_note_sources"]["scenes"][1]
    assert [item["id"] for item in result["longline_context"]] == [
        "L-0001",
        "L-0002",
    ]
    assert plan_workspace.read_plan(workspace) == before_plan
    assert _tree_bytes(project_dir) == before_tree


def test_c7_unselected_pending_blocked_and_discarded_content_never_appears(
    tmp_path: Path,
) -> None:
    _, workspace = _workspace_with_plan(tmp_path)

    result = chapter_fact_supply_workspace.execute(workspace, "S-0001")
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True)

    assert "未选择候选绝不能进入供料" not in rendered
    assert "未落账 C7 变化绝不能进入供料" not in rendered
    assert "C7 主推荐绝不能进入供料" not in rendered
    assert "冲突问句与写作指导不得进入供料" not in rendered
    assert "pending 候选事件绝不能进入供料" not in rendered
    assert "被停点挡住的候选绝不能进入供料" not in rendered
    assert "被驳回事件绝不能进入供料" not in rendered
    assert list(inspect.signature(chapter_fact_supply_workspace.execute).parameters) == [
        "workspace",
        "slot_ref",
    ]


def test_plan_source_change_during_resolution_rejects_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "race"
    workspace = WorkspaceRouter(runtime_root).create_project("auth:alice", "竞态项目")
    project_dir = _project_dir(runtime_root, workspace)
    before_tree = _tree_bytes(project_dir)
    original = _plan()
    changed = _plan()
    changed["slots"][0]["summary"] = "运行中已经变化"
    entries = [
        _plan_entry(original, version=1),
        _plan_entry(original, version=1),
        _plan_entry(changed, version=2),
    ]

    def changing_read(handle):
        return copy.deepcopy(entries.pop(0))

    monkeypatch.setattr(plan_workspace, "read_plan", changing_read)
    monkeypatch.setattr(
        workspace,
        "commit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("来源变化时不得写")
        ),
    )

    with pytest.raises(
        chapter_fact_supply_workspace.ChapterFactSupplyWorkspaceError,
        match="PLAN_SOURCE_CHANGED_DURING_RESOLUTION",
    ):
        chapter_fact_supply_workspace.execute(workspace, "S-0001")

    assert entries == []
    assert _tree_bytes(project_dir) == before_tree


def test_missing_or_bad_slot_bad_plan_path_and_cross_author_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root, alice = _workspace_with_plan(tmp_path, principal="auth:alice")
    bob = WorkspaceRouter(runtime_root).create_project("auth:bob", "同名供料项目")
    fake_path = tmp_path / "not-a-workspace"

    with pytest.raises(
        chapter_fact_supply_workspace.ChapterFactSupplyWorkspaceError,
        match="CHAPTER_SLOT_SNAPSHOT_REJECTED",
    ):
        chapter_fact_supply_workspace.execute(alice, "S-9999")
    with pytest.raises(
        chapter_fact_supply_workspace.ChapterFactSupplyWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        chapter_fact_supply_workspace.execute(fake_path, "S-0001")
    with pytest.raises(
        chapter_fact_supply_workspace.ChapterFactSupplyWorkspaceError,
        match="PLAN_SNAPSHOT_NOT_FOUND",
    ):
        chapter_fact_supply_workspace.execute(bob, "S-0001")
    assert not fake_path.exists()

    bad = _plan()
    bad["scenes"][0]["pe_refs"] = ["PE-9999"]
    monkeypatch.setattr(
        plan_workspace,
        "read_plan",
        lambda handle: _plan_entry(bad),
    )
    with pytest.raises(
        chapter_fact_supply_workspace.ChapterFactSupplyWorkspaceError,
        match="CHAPTER_SLOT_SNAPSHOT_REJECTED",
    ):
        chapter_fact_supply_workspace.execute(alice, "S-0001")


def test_missing_outline_checkpoint_and_invalid_landed_record_reject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = WorkspaceRouter(tmp_path / "invalid").create_project(
        "auth:alice", "不完整供料"
    )
    no_outline = _plan()
    no_outline["slots"][0]["outline_checkpoint"] = None
    entries = [_plan_entry(no_outline) for _ in range(3)]
    monkeypatch.setattr(
        plan_workspace,
        "read_plan",
        lambda handle: copy.deepcopy(entries.pop(0)),
    )
    with pytest.raises(
        chapter_fact_supply_workspace.ChapterFactSupplyWorkspaceError,
        match="OUTLINE_CHECKPOINT_REQUIRED_FOR_SUPPLY",
    ):
        chapter_fact_supply_workspace.execute(workspace, "S-0001")

    broken = _plan()
    broken["option_records"][0]["group_status"] = "discarded"
    entries = [_plan_entry(broken) for _ in range(3)]
    monkeypatch.setattr(
        plan_workspace,
        "read_plan",
        lambda handle: copy.deepcopy(entries.pop(0)),
    )
    with pytest.raises(
        chapter_fact_supply_workspace.ChapterFactSupplyWorkspaceError,
        match="DIGESTED_EVENT_RECORD_NOT_ACTIVE:PE-0001",
    ):
        chapter_fact_supply_workspace.execute(workspace, "S-0001")


def test_reopened_process_returns_byte_stable_supply_without_writes(
    tmp_path: Path,
) -> None:
    runtime_root, workspace = _workspace_with_plan(tmp_path)
    project_dir = _project_dir(runtime_root, workspace)
    before = _tree_bytes(project_dir)
    expected = chapter_fact_supply_workspace.execute(workspace, "S-0001")
    child = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from mvp.chapter_fact_supply_workspace import execute
from mvp.workspace import WorkspaceRouter
workspace = WorkspaceRouter(sys.argv[2]).open_project(sys.argv[3], sys.argv[4])
value = execute(workspace, sys.argv[5])
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
            "S-0001",
        ],
        capture_output=True,
        check=True,
    )

    assert reopened.stdout == _canonical_bytes(expected)
    assert _tree_bytes(project_dir) == before


def test_public_validator_is_strict_and_returns_a_deep_copy(tmp_path: Path) -> None:
    _, workspace = _workspace_with_plan(tmp_path)
    result = chapter_fact_supply_workspace.execute(workspace, "S-0001")

    validated = chapter_fact_supply_workspace.validate_result(result)
    assert validated == result
    validated["future_event_materials"][0]["text"] = "调用方修改副本"
    assert result["future_event_materials"][0]["text"] == "许岚计划把密封信交给林照"

    bad_watermark = copy.deepcopy(result)
    bad_watermark["generation_watermark"]["slot_rev"] += 1
    with pytest.raises(
        chapter_fact_supply_workspace.ChapterFactSupplyWorkspaceError,
        match="SUPPLY_RESULT_GENERATION_WATERMARK_MISMATCH",
    ):
        chapter_fact_supply_workspace.validate_result(bad_watermark)

    bad_event = copy.deepcopy(result)
    bad_event["future_event_materials"][0]["scene_ref"] = "SCN-MISSING"
    with pytest.raises(
        chapter_fact_supply_workspace.ChapterFactSupplyWorkspaceError,
        match="SUPPLY_RESULT_EVENT_SCENE_NOT_FOUND",
    ):
        chapter_fact_supply_workspace.validate_result(bad_event)
