from __future__ import annotations

import copy
import hashlib
import inspect
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        plan_workspace,
        scene_card_workspace,
        scene_export_bundle,
        scene_export_bundle_workspace,
        scene_export_workspace,
    )
    from mvp.workspace import ProjectNotFoundError, WorkspaceRouter
finally:
    sys.path.pop(0)


NOW = "2026-08-19 23:30:00"


def _plan() -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-BUNDLE-WORKSPACE", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "goal": "让林照接到任务",
                "summary": "合成任务交接",
                "entry_state": "尚未接到任务",
                "storyline_refs": [],
                "scene_refs": ["SCN-001"],
                "exit_condition": "林照收下任务",
                "exit_hook": "任务影响后续计划",
                "must_not": ["不得把规划冒充事实"],
                "risks": [],
                "outline_checkpoint": {
                    "outline_rev": 1,
                    "source_slot_ref": "S-0001",
                    "source_commit_seq": 1,
                },
                "slot_status": "planned",
                "handover_parts": [],
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 1,
            }
        ],
        "scenes": [
            {
                "id": "SCN-001",
                "slot_ref": "S-0001",
                "goal": "接到密封任务",
                "summary": "林照在纸灯巷接到任务",
                "pe_refs": ["PE-001"],
                "characters": ["CH-001"],
                "mood_in": "犹豫",
                "mood_out": "决定行动",
                "visual_hint": "雨落在石阶上",
                "dialogue_hints": ["任务必须在天亮前完成"],
                "resistance": "时间不足",
                "turn": "林照收下任务",
                "pov": "CH-001",
                "spoiler_notes": ["不得展示幕后人物"],
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 1,
            }
        ],
        "events": [
            {
                "id": "PE-001",
                "scene_ref": "SCN-001",
                "text": "林照计划收下任务",
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 1,
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
    ]


def _materials() -> tuple[dict, list[dict], list[dict]]:
    context = {
        "project": "_bundle_workspace",
        "generated_at": NOW,
        "model": "stub",
        "book_title": "合成任务簿",
        "plan_id": "PLAN-BUNDLE-WORKSPACE-r1",
        "basis_note": "workspace-current-plan",
        "chapter_hint": 1,
        "chapter_title": "任务交接",
    }
    scenes = [
        {
            "scene_ref": "SCN-001",
            "location_anchor_ref": "AN-LOC-001",
            "time": "雨夜",
            "character_presence": {"CH-001": "站在任务交接处"},
            "writing_guidance": ["只展示任务交接"],
        }
    ]
    events = [
        {
            "event_ref": "PE-001",
            "visual": "林照收下密封任务",
            "shot_hint": "中景转手部特写",
            "dialogue_bindings": [
                {
                    "id": "D-001",
                    "info": "任务必须在天亮前完成",
                    "speaker_ref": "CH-001",
                    "tone": "压低声音",
                }
            ],
        }
    ]
    return context, scenes, events


def _workspace(tmp_path: Path, principal: str = "auth:alice"):
    runtime = tmp_path / principal.replace(":", "-")
    runtime.parent.mkdir(parents=True, exist_ok=True)
    handle = WorkspaceRouter(runtime).create_project(principal, "场景文本包")
    plan_workspace.save_plan(handle, "op-plan-setup", _plan(), 0)
    return runtime, handle


def _generate_and_save(workspace) -> dict:
    context, scenes, events = _materials()
    result = scene_export_workspace.execute(
        workspace,
        "S-0001",
        _anchors(),
        context,
        scenes,
        events,
    )
    scene_card_workspace.save_scene_cards(
        workspace,
        "op-save-scene-cards",
        result,
        0,
        anchors=_anchors(),
        scene_bindings=scenes,
        event_bindings=events,
    )
    return result


def _project_tree(runtime: Path, workspace) -> dict[str, bytes]:
    root = runtime / "authors" / workspace.author_id / "projects" / workspace.project_id
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _execute(workspace, *, anchors=None, scenes=None, events=None):
    _, default_scenes, default_events = _materials()
    return scene_export_bundle_workspace.execute(
        workspace,
        "S-0001",
        _anchors() if anchors is None else anchors,
        default_scenes if scenes is None else scenes,
        default_events if events is None else events,
    )


def test_saved_current_c8_restart_returns_same_zip_as_offline_and_no_writes(
    tmp_path: Path,
) -> None:
    runtime, workspace = _workspace(tmp_path)
    saved_result = _generate_and_save(workspace)
    reopened = WorkspaceRouter(runtime).open_project("auth:alice", workspace.project_id)
    before = _project_tree(runtime, reopened)

    result = _execute(reopened)
    expected = scene_export_bundle.build_bundle(
        saved_result,
        {
            "source_plan_version": saved_result["workspace_basis"][
                "source_plan_version"
            ],
            "source_plan_sha256": saved_result["workspace_basis"][
                "source_plan_sha256"
            ],
        },
    )

    assert result["zip_bytes"] == expected
    assert result["zip_sha256"] == hashlib.sha256(expected).hexdigest()
    assert result["zip_size_bytes"] == len(expected)
    assert result["source_plan"] == {
        "version": saved_result["workspace_basis"]["source_plan_version"],
        "sha256": saved_result["workspace_basis"]["source_plan_sha256"],
    }
    assert result["scene_cards_snapshot"]["version"] == 1
    assert len(result["scene_cards_snapshot"]["sha256"]) == 64
    assert _project_tree(runtime, reopened) == before


def test_public_signature_has_no_path_identity_or_plan_watermark() -> None:
    assert list(
        inspect.signature(scene_export_bundle_workspace.execute).parameters
    ) == [
        "workspace",
        "slot_ref",
        "anchors",
        "scene_bindings",
        "event_bindings",
    ]


def test_missing_slot_returns_none_without_writes(tmp_path: Path) -> None:
    runtime, workspace = _workspace(tmp_path)
    before = _project_tree(runtime, workspace)

    result = scene_export_bundle_workspace.execute(
        workspace,
        "S-0099",
        [],
        [],
        [],
    )

    assert result is None
    assert _project_tree(runtime, workspace) == before


@pytest.mark.parametrize("drift", ["plan", "anchor", "scene", "event"])
def test_plan_anchor_scene_and_event_drift_are_rejected(
    tmp_path: Path,
    drift: str,
) -> None:
    _, workspace = _workspace(tmp_path)
    _generate_and_save(workspace)
    anchors = _anchors()
    _, scenes, events = _materials()
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
    elif drift == "scene":
        scenes[0]["time"] = "黎明前"
    else:
        events[0]["visual"] = "动作画面已经改变"

    with pytest.raises(
        scene_export_bundle_workspace.SceneExportBundleWorkspaceError,
    ):
        _execute(workspace, anchors=anchors, scenes=scenes, events=events)


def test_scene_card_change_during_bundle_discards_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace = _workspace(tmp_path)
    _generate_and_save(workspace)
    real_read = scene_card_workspace.read_scene_cards
    calls = 0

    def changing_read(handle, slot_ref):
        nonlocal calls
        calls += 1
        if calls == 2:
            entry = handle.read("scene_cards")
            handle.commit(
                "op-scene-card-race",
                {"scene_cards": entry["payload"]},
                {"scene_cards": entry["version"]},
            )
        return real_read(handle, slot_ref)

    monkeypatch.setattr(scene_card_workspace, "read_scene_cards", changing_read)

    with pytest.raises(
        scene_export_bundle_workspace.SceneExportBundleWorkspaceError,
        match="SCENE_CARD_SNAPSHOT_CHANGED_DURING_BUNDLE",
    ):
        _execute(workspace)


def test_corrupt_saved_c8_is_rejected_before_bundle(tmp_path: Path) -> None:
    _, workspace = _workspace(tmp_path)
    _generate_and_save(workspace)
    entry = workspace.read("scene_cards")
    corrupted = copy.deepcopy(entry["payload"])
    corrupted["slots"]["S-0001"]["contract"] = "WRONG"
    workspace.commit(
        "op-corrupt-saved-c8",
        {"scene_cards": corrupted},
        {"scene_cards": entry["version"]},
    )

    with pytest.raises(scene_card_workspace.SceneCardWorkspaceError):
        _execute(workspace)


def test_path_and_cross_author_saved_result_fail_closed(tmp_path: Path) -> None:
    caller_path = tmp_path / "caller-project"
    with pytest.raises(
        scene_export_bundle_workspace.SceneExportBundleWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        _execute(caller_path)  # type: ignore[arg-type]
    assert not caller_path.exists()

    _, alice = _workspace(tmp_path / "alice", "auth:alice")
    alice_result = _generate_and_save(alice)
    _, bob = _workspace(tmp_path / "bob", "auth:bob")
    bob.commit(
        "op-inject-cross-author",
        {
            "scene_cards": {
                "store_version": scene_card_workspace.STORE_VERSION,
                "slots": {"S-0001": alice_result},
            }
        },
        {"scene_cards": 0},
    )

    with pytest.raises(scene_card_workspace.SceneCardWorkspaceError):
        _execute(bob)
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        WorkspaceRouter(tmp_path / "bob" / "auth-bob").open_project(
            "auth:bob",
            alice.project_id,
        )
