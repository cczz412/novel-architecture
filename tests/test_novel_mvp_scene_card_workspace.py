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
        scene_card_workspace,
        scene_export_workspace,
    )
    from mvp.workspace import (
        OperationConflictError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


NOW = "2026-08-19 18:00:00"


def _slot(slot_ref: str, scene_ref: str, rev: int) -> dict:
    return {
        "id": slot_ref,
        "goal": f"完成{scene_ref}的规划目标",
        "summary": f"{scene_ref}的合成规划",
        "entry_state": "尚未作出决定",
        "storyline_refs": [],
        "scene_refs": [scene_ref],
        "exit_condition": "作出决定",
        "exit_hook": "决定影响后续规划",
        "must_not": ["不得把规划冒充事实"],
        "risks": [],
        "outline_checkpoint": {
            "outline_rev": rev,
            "source_slot_ref": slot_ref,
            "source_commit_seq": rev,
        },
        "slot_status": "planned",
        "handover_parts": [],
        "truth_bearing": "primary",
        "updated_at": NOW,
        "rev": rev,
    }


def _scene(scene_ref: str, slot_ref: str, event_ref: str, character: str) -> dict:
    return {
        "id": scene_ref,
        "slot_ref": slot_ref,
        "goal": f"{character}接到任务",
        "summary": f"{character}在合成地点接到任务",
        "pe_refs": [event_ref],
        "characters": [character],
        "mood_in": "犹豫",
        "mood_out": "决定行动",
        "visual_hint": "雨落在石阶上",
        "dialogue_hints": ["任务必须在天亮前完成"],
        "resistance": "时间不足",
        "turn": f"{character}收下任务",
        "pov": character,
        "spoiler_notes": ["不得展示幕后人物"],
        "truth_bearing": "primary",
        "updated_at": NOW,
        "rev": 1,
    }


def _plan() -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-SCENE-CARD-STORE", "volumes_enabled": False},
        "slot_sequence": ["S-0001", "S-0002"],
        "volumes": [],
        "slots": [
            _slot("S-0001", "SCN-001", 1),
            _slot("S-0002", "SCN-002", 2),
        ],
        "scenes": [
            _scene("SCN-001", "S-0001", "PE-001", "CH-001"),
            _scene("SCN-002", "S-0002", "PE-002", "CH-002"),
        ],
        "events": [
            {
                "id": "PE-001",
                "scene_ref": "SCN-001",
                "text": "林照计划收下任务",
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 1,
            },
            {
                "id": "PE-002",
                "scene_ref": "SCN-002",
                "text": "许岚计划收下任务",
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 1,
            },
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


def _anchors() -> list[dict]:
    return [
        {
            "anchor_id": "AN-CH-001",
            "kind": "character",
            "entity_ref": "CH-001",
            "name": "林照",
            "aliases": [],
            "look": "深色短衣",
            "voice_hint": "克制",
            "status": "confirmed",
            "source_refs": ["SYN-CH-001"],
            "revision": 1,
        },
        {
            "anchor_id": "AN-CH-002",
            "kind": "character",
            "entity_ref": "CH-002",
            "name": "许岚",
            "aliases": [],
            "look": "浅色斗篷",
            "voice_hint": "直接",
            "status": "confirmed",
            "source_refs": ["SYN-CH-002"],
            "revision": 1,
        },
        {
            "anchor_id": "AN-LOC-001",
            "kind": "location",
            "entity_ref": "LOC-001",
            "name": "纸灯巷",
            "aliases": [],
            "look": "雨夜石阶",
            "voice_hint": "",
            "status": "confirmed",
            "source_refs": ["SYN-LOC-001"],
            "revision": 1,
        },
        {
            "anchor_id": "AN-LOC-002",
            "kind": "location",
            "entity_ref": "LOC-002",
            "name": "旧码头",
            "aliases": [],
            "look": "雾中栈桥",
            "voice_hint": "",
            "status": "confirmed",
            "source_refs": ["SYN-LOC-002"],
            "revision": 1,
        },
    ]


def _materials(slot_ref: str, *, note: str = "current") -> tuple[dict, list, list]:
    number = "001" if slot_ref == "S-0001" else "002"
    character = f"CH-{number}"
    context = {
        "project": "_scene_card_store",
        "generated_at": NOW,
        "model": "stub",
        "book_title": "合成任务簿",
        "plan_id": "PLAN-STORE-r1",
        "basis_note": note,
        "chapter_hint": int(number),
        "chapter_title": f"第{int(number)}章",
    }
    scenes = [
        {
            "scene_ref": f"SCN-{number}",
            "location_anchor_ref": f"AN-LOC-{number}",
            "time": "雨夜",
            "character_presence": {character: "站在任务交接处"},
            "writing_guidance": ["只展示任务交接"],
        }
    ]
    events = [
        {
            "event_ref": f"PE-{number}",
            "visual": "人物收下密封任务",
            "shot_hint": "中景转手部特写",
            "dialogue_bindings": [
                {
                    "id": f"D-{number}",
                    "info": "任务必须在天亮前完成",
                    "speaker_ref": character,
                    "tone": "压低声音",
                }
            ],
        }
    ]
    return context, scenes, events


def _workspace(tmp_path: Path, principal: str = "auth:alice"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime = tmp_path / principal.replace(":", "-")
    handle = WorkspaceRouter(runtime).create_project(principal, "场景卡项目")
    plan_workspace.save_plan(handle, "op-plan-setup", _plan(), 0)
    return runtime, handle


def _result(workspace, slot_ref: str, *, note: str = "current") -> dict:
    context, scenes, events = _materials(slot_ref, note=note)
    return scene_export_workspace.execute(
        workspace,
        slot_ref,
        _anchors(),
        context,
        scenes,
        events,
    )


def _save(
    workspace,
    operation_id: str,
    result: dict,
    expected_version: int,
    *,
    anchors=None,
    scenes=None,
    events=None,
):
    slot_ref = result["workspace_binding"]["slot_ref"]
    _, default_scenes, default_events = _materials(slot_ref)
    return scene_card_workspace.save_scene_cards(
        workspace,
        operation_id,
        result,
        expected_version,
        anchors=_anchors() if anchors is None else anchors,
        scene_bindings=default_scenes if scenes is None else scenes,
        event_bindings=default_events if events is None else events,
    )


def _project_tree(runtime: Path, workspace) -> dict[str, bytes]:
    root = runtime / "authors" / workspace.author_id / "projects" / workspace.project_id
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def test_generate_save_restart_read_and_freshness_remain_current(
    tmp_path: Path,
) -> None:
    runtime, workspace = _workspace(tmp_path)
    result = _result(workspace, "S-0001")

    receipt = _save(workspace, "op-save-scene-1", result, 0)
    reopened = WorkspaceRouter(runtime).open_project(
        "auth:alice", workspace.project_id
    )
    loaded = scene_card_workspace.read_scene_cards(reopened, "S-0001")
    _, scenes, events = _materials("S-0001")
    freshness = scene_export_workspace.inspect_freshness(
        reopened,
        loaded["scene_result"],
        _anchors(),
        scenes,
        events,
    )

    assert receipt["versions"] == {"scene_cards": 1}
    assert loaded["version"] == 1
    assert len(loaded["sha256"]) == 64
    assert _canonical(loaded["scene_result"]) == _canonical(result)
    assert [row["status"] for row in freshness["scenes"]] == ["CURRENT"]
    loaded["scene_result"]["book_title"] = "调用方改动"
    assert scene_card_workspace.read_scene_cards(reopened, "S-0001")[
        "scene_result"
    ] == result


def test_same_operation_is_idempotent_and_different_payload_conflicts(
    tmp_path: Path,
) -> None:
    _, workspace = _workspace(tmp_path)
    result = _result(workspace, "S-0001")

    first = _save(workspace, "op-idempotent", result, 0)
    replay = _save(workspace, "op-idempotent", result, 0)
    changed = _result(workspace, "S-0001", note="changed-output-note")

    assert first["generation_id"] == replay["generation_id"]
    assert replay["replayed"] is True
    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        _save(workspace, "op-idempotent", changed, 0)
    assert scene_card_workspace.read_scene_cards(workspace, "S-0001")[
        "scene_result"
    ] == result


def test_version_conflict_does_not_overwrite_saved_result(tmp_path: Path) -> None:
    _, workspace = _workspace(tmp_path)
    original = _result(workspace, "S-0001")
    _save(workspace, "op-version-1", original, 0)
    changed = _result(workspace, "S-0001", note="new-output")

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        _save(workspace, "op-stale-version", changed, 0)

    assert scene_card_workspace.read_scene_cards(workspace, "S-0001")[
        "scene_result"
    ] == original


@pytest.mark.parametrize("drift", ["plan", "anchor", "scene_binding"])
def test_stale_material_is_rejected_before_any_scene_card_write(
    tmp_path: Path,
    drift: str,
) -> None:
    runtime, workspace = _workspace(tmp_path)
    result = _result(workspace, "S-0001")
    anchors = _anchors()
    _, scenes, events = _materials("S-0001")
    if drift == "plan":
        current = plan_workspace.read_plan(workspace)
        changed = copy.deepcopy(current["plan"])
        changed["scenes"][0]["summary"] = "当前规划已经改变"
        changed["scenes"][0]["rev"] += 1
        plan_workspace.save_plan(
            workspace,
            "op-plan-drift",
            changed,
            current["version"],
        )
    elif drift == "anchor":
        anchors[0]["look"] = "人物外观已经改变"
        anchors[0]["revision"] += 1
    else:
        scenes[0]["time"] = "黎明前"
    before = _project_tree(runtime, workspace)

    with pytest.raises(
        scene_card_workspace.SceneCardWorkspaceError,
        match="SCENE_RESULT_NOT_CURRENT",
    ):
        _save(
            workspace,
            "op-stale-result",
            result,
            0,
            anchors=anchors,
            scenes=scenes,
            events=events,
        )

    assert scene_card_workspace.read_scene_cards(workspace, "S-0001") is None
    assert _project_tree(runtime, workspace) == before


def test_bad_cross_author_path_duplicate_and_corrupt_read_fail_closed(
    tmp_path: Path,
) -> None:
    _, alice = _workspace(tmp_path / "alice", "auth:alice")
    result = _result(alice, "S-0001")

    bad = copy.deepcopy(result)
    bad.pop("contract")
    with pytest.raises(
        scene_card_workspace.SceneCardWorkspaceError,
        match="SCENE_RESULT_INVALID",
    ):
        _save(alice, "op-bad", bad, 0)

    duplicate = copy.deepcopy(result)
    duplicate["workspace_binding"]["scenes"].append(
        copy.deepcopy(duplicate["workspace_binding"]["scenes"][0])
    )
    with pytest.raises(
        scene_card_workspace.SceneCardWorkspaceError,
        match="SCENE_RESULT_INVALID",
    ):
        _save(alice, "op-duplicate", duplicate, 0)

    _, bob = _workspace(tmp_path / "bob", "auth:bob")
    with pytest.raises(
        scene_card_workspace.SceneCardWorkspaceError,
        match="SCENE_RESULT_WORKSPACE_MISMATCH",
    ):
        _save(bob, "op-cross-author", result, 0)
    with pytest.raises(
        scene_card_workspace.SceneCardWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        scene_card_workspace.save_scene_cards(
            tmp_path,
            "op-path",
            result,
            0,
            anchors=_anchors(),
            scene_bindings=[],
            event_bindings=[],
        )

    alice.commit(
        "op-corrupt-store",
        {"scene_cards": {"bad": True}},
        {"scene_cards": 0},
    )
    with pytest.raises(
        scene_card_workspace.SceneCardWorkspaceError,
        match="SCENE_CARD_STORE_INVALID",
    ):
        scene_card_workspace.read_scene_cards(alice, "S-0001")


def test_updating_one_slot_preserves_the_other_slot(tmp_path: Path) -> None:
    _, workspace = _workspace(tmp_path)
    first = _result(workspace, "S-0001")
    second = _result(workspace, "S-0002")
    _save(workspace, "op-slot-1", first, 0)
    _save(workspace, "op-slot-2", second, 1)
    second_before = scene_card_workspace.read_scene_cards(
        workspace, "S-0002"
    )["scene_result"]

    first_updated = _result(workspace, "S-0001", note="re-exported")
    receipt = _save(workspace, "op-slot-1-update", first_updated, 2)

    assert receipt["versions"] == {"scene_cards": 3}
    assert scene_card_workspace.read_scene_cards(workspace, "S-0001")[
        "scene_result"
    ] == first_updated
    assert scene_card_workspace.read_scene_cards(workspace, "S-0002")[
        "scene_result"
    ] == second_before
