from __future__ import annotations

import copy
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
        chapter_slot_snapshot_tool,
        chapter_slot_workspace,
        m10_scene_slice_adapter,
        plan_workspace,
        scene_export,
        scene_export_workspace,
    )
    from mvp.workspace import ProjectNotFoundError, WorkspaceRouter
finally:
    sys.path.pop(0)


NOW = "2026-08-19 14:00:00"


def _plan() -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-M10-WORKSPACE", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "goal": "让两人决定共同送信",
                "summary": "两场合成规划",
                "entry_state": "双方互不信任",
                "storyline_refs": [],
                "scene_refs": ["SCN-001", "SCN-002"],
                "exit_condition": "双方形成临时同盟",
                "exit_hook": "寄件人仍未知",
                "must_not": ["不得提前揭晓寄件人"],
                "risks": [],
                "outline_checkpoint": {
                    "outline_rev": 2,
                    "source_slot_ref": "S-0001",
                    "source_commit_seq": 9,
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
                "id": "SCN-001",
                "slot_ref": "S-0001",
                "goal": "完成密封信交接",
                "summary": "许岚在纸灯巷把密封信交给林照",
                "pe_refs": ["PE-001"],
                "characters": ["CH-001", "CH-002"],
                "mood_in": "戒备",
                "mood_out": "暂时信任",
                "visual_hint": "纸灯倒影被雨滴打碎",
                "dialogue_hints": ["密封信必须在天亮前送达"],
                "resistance": "双方都不肯说明来源",
                "turn": "许岚交出密封信",
                "pov": "CH-001",
                "spoiler_notes": ["不得展示信内页"],
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 2,
            },
            {
                "id": "SCN-002",
                "slot_ref": "S-0001",
                "goal": "决定共同前往旧码头",
                "summary": "两人在旧码头确认下一步路线",
                "pe_refs": ["PE-002"],
                "characters": ["CH-001", "CH-002"],
                "mood_in": "暂时信任",
                "mood_out": "形成同盟",
                "visual_hint": "雾中木栈桥只露出近处栏杆",
                "dialogue_hints": ["码头铁门会在午夜关闭"],
                "resistance": "路线可能已经暴露",
                "turn": "两人决定改走水路",
                "pov": "CH-002",
                "spoiler_notes": ["不得展示跟踪者身份"],
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 1,
            },
        ],
        "events": [
            {
                "id": "PE-001",
                "scene_ref": "SCN-001",
                "text": "许岚计划把密封信交给林照",
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 3,
            },
            {
                "id": "PE-002",
                "scene_ref": "SCN-002",
                "text": "两人计划从旧码头改走水路",
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
    def anchor(anchor_id: str, kind: str, entity_ref: str, name: str) -> dict:
        return {
            "anchor_id": anchor_id,
            "kind": kind,
            "entity_ref": entity_ref,
            "name": name,
            "aliases": [],
            "look": f"{name}的合成外观",
            "voice_hint": "克制" if kind == "character" else "",
            "status": "confirmed",
            "source_refs": [f"SYN-{anchor_id}"],
            "revision": 1,
        }

    return [
        anchor("AN-CHAR-001", "character", "CH-001", "林照"),
        anchor("AN-CHAR-002", "character", "CH-002", "许岚"),
        anchor("AN-LOC-001", "location", "LOC-001", "纸灯巷"),
        anchor("AN-LOC-002", "location", "LOC-002", "旧码头"),
    ]


def _supplements() -> tuple[dict, list[dict], list[dict]]:
    context = {
        "project": "_workspace_scene_export",
        "generated_at": "2026-08-19 14:30:00",
        "model": "stub",
        "book_title": "雨夜送信",
        "plan_id": "PLAN-WORKSPACE-r1",
        "basis_note": "workspace-current-plan",
        "chapter_hint": 1,
        "chapter_title": "雨夜送信",
    }
    scenes = [
        {
            "scene_ref": "SCN-001",
            "location_anchor_ref": "AN-LOC-001",
            "time": "雨夜",
            "character_presence": {
                "CH-001": "站在铁门内侧",
                "CH-002": "从巷口跑来",
            },
            "writing_guidance": ["只表现交接动作"],
        },
        {
            "scene_ref": "SCN-002",
            "location_anchor_ref": "AN-LOC-002",
            "time": "午夜前",
            "character_presence": {
                "CH-001": "检查木船",
                "CH-002": "观察铁门方向",
            },
            "writing_guidance": ["不展示跟踪者正脸"],
        },
    ]
    events = [
        {
            "event_ref": "PE-001",
            "visual": "许岚把密封信递向林照",
            "shot_hint": "中景，手部特写",
            "dialogue_bindings": [
                {
                    "id": "D-001",
                    "info": "密封信必须在天亮前送达",
                    "speaker_ref": "CH-002",
                    "tone": "急促但压低声音",
                }
            ],
        },
        {
            "event_ref": "PE-002",
            "visual": "两人在雾中把木船推离栈桥",
            "shot_hint": "远景转中景",
            "dialogue_bindings": [
                {
                    "id": "D-002",
                    "info": "码头铁门会在午夜关闭",
                    "speaker_ref": "CH-001",
                    "tone": "低声提醒",
                }
            ],
        },
    ]
    return context, scenes, events


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


def _workspace_with_plan(tmp_path: Path, principal: str = "auth:alice"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime_root = tmp_path / principal.replace(":", "-")
    workspace = WorkspaceRouter(runtime_root).create_project(principal, "场景导出项目")
    plan_workspace.save_plan(workspace, "op-plan-setup", _plan(), 0)
    return runtime_root, workspace


def _execute(workspace, *, anchors=None, context=None, scenes=None, events=None):
    default_context, default_scenes, default_events = _supplements()
    return scene_export_workspace.execute(
        workspace,
        "S-0001",
        _anchors() if anchors is None else anchors,
        default_context if context is None else context,
        default_scenes if scenes is None else scenes,
        default_events if events is None else events,
    )


def _inspect(workspace, saved, *, anchors=None, scenes=None, events=None):
    _, default_scenes, default_events = _supplements()
    return scene_export_workspace.inspect_freshness(
        workspace,
        saved,
        _anchors() if anchors is None else anchors,
        default_scenes if scenes is None else scenes,
        default_events if events is None else events,
    )


def _update_plan(workspace, operation_id: str, mutate) -> dict:
    current = plan_workspace.read_plan(workspace)
    changed = copy.deepcopy(current["plan"])
    mutate(changed)
    plan_workspace.save_plan(
        workspace,
        operation_id,
        changed,
        current["version"],
    )
    return changed


def _freshness_by_scene(result: dict) -> dict[str, dict]:
    return {row["scene_id"]: row for row in result["scenes"]}


def test_current_workspace_plan_exports_two_scene_c8_with_watermark(
    tmp_path: Path,
) -> None:
    runtime_root, workspace = _workspace_with_plan(tmp_path)
    project_dir = _project_dir(runtime_root, workspace)
    current_before = plan_workspace.read_plan(workspace)
    tree_before = _tree_bytes(project_dir)
    external = tmp_path / "existing-output.json"
    external.write_bytes(b'{"keep":"outside"}\n')

    result = _execute(workspace)

    scene_export.validate_c8_prototype(result)
    assert result["contract"] == "C8_SCENE_CARD_PROTOTYPE"
    assert result["range"] == {
        "chapters": [1],
        "scene_ids": ["SCN-001", "SCN-002"],
    }
    assert result["workspace_basis"]["source_plan_version"] == current_before[
        "version"
    ]
    assert result["workspace_basis"]["source_plan_sha256"] == current_before[
        "sha256"
    ]
    assert result["workspace_basis"]["slot_ref"] == "S-0001"
    assert result["workspace_basis"]["slot_rev"] == 3
    assert result["workspace_binding"]["scene_ids"] == ["SCN-001", "SCN-002"]
    assert [
        row["scene_id"] for row in result["workspace_binding"]["scenes"]
    ] == ["SCN-001", "SCN-002"]
    assert "summary" not in json.dumps(
        result["workspace_binding"], ensure_ascii=False
    )
    assert plan_workspace.read_plan(workspace) == current_before
    assert _tree_bytes(project_dir) == tree_before
    assert external.read_bytes() == b'{"keep":"outside"}\n'


def test_same_input_and_restarted_workspace_are_stable(tmp_path: Path) -> None:
    runtime_root, workspace = _workspace_with_plan(tmp_path)
    first = _execute(workspace)
    second = _execute(workspace)
    restarted = WorkspaceRouter(runtime_root).open_project(
        "auth:alice", workspace.project_id
    )
    third = _execute(restarted)

    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second, ensure_ascii=False, sort_keys=True
    )
    assert third == first


@pytest.mark.parametrize(
    ("damage", "error_type", "message"),
    [
        ("missing_location", m10_scene_slice_adapter.M10SceneSliceAdapterError, "LOCATION_ANCHOR_MISSING"),
        ("missing_presence", m10_scene_slice_adapter.M10SceneSliceAdapterError, "CHARACTER_PRESENCE_INCOMPLETE"),
        ("missing_event", m10_scene_slice_adapter.M10SceneSliceAdapterError, "EVENT_BINDINGS_INCOMPLETE"),
    ],
)
def test_missing_explicit_material_fails_closed(
    tmp_path: Path, damage: str, error_type: type[Exception], message: str
) -> None:
    _, workspace = _workspace_with_plan(tmp_path)
    context, scenes, events = _supplements()
    if damage == "missing_location":
        scenes[0]["location_anchor_ref"] = "AN-LOC-999"
    elif damage == "missing_presence":
        scenes[0]["character_presence"].pop("CH-002")
    else:
        events.pop()

    with pytest.raises(error_type, match=message):
        _execute(workspace, context=context, scenes=scenes, events=events)


def test_old_slot_and_path_masquerade_fail_closed(tmp_path: Path) -> None:
    _, workspace = _workspace_with_plan(tmp_path)
    context, scenes, events = _supplements()

    with pytest.raises(
        chapter_slot_snapshot_tool.ChapterSlotSnapshotError,
        match="SLOT_NOT_FOUND",
    ):
        scene_export_workspace.execute(
            workspace,
            "S-9999",
            _anchors(),
            context,
            scenes,
            events,
        )
    with pytest.raises(
        scene_export_workspace.SceneExportWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        scene_export_workspace.execute(
            tmp_path,
            "S-0001",
            _anchors(),
            context,
            scenes,
            events,
        )
    assert not hasattr(scene_export_workspace, "open_path")
    assert list(inspect.signature(scene_export_workspace.execute).parameters) == [
        "workspace",
        "slot_ref",
        "anchors",
        "export_context",
        "scene_bindings",
        "event_bindings",
    ]


def test_cross_author_project_guess_matches_missing_and_cannot_export(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    alice = router.create_project("auth:alice", "同名项目")
    bob = router.create_project("auth:bob", "同名项目")
    plan_workspace.save_plan(alice, "op-alice-plan", _plan(), 0)

    with pytest.raises(ProjectNotFoundError) as guessed:
        router.open_project("auth:bob", alice.project_id)
    with pytest.raises(ProjectNotFoundError) as absent:
        router.open_project("auth:bob", "p_" + "f" * 32)
    assert guessed.value.code == absent.value.code == "PROJECT_NOT_FOUND"
    with pytest.raises(
        chapter_slot_workspace.ChapterSlotWorkspaceError,
        match="PLAN_SNAPSHOT_NOT_FOUND",
    ):
        _execute(bob)


def test_unchanged_saved_scenes_are_current_and_inspection_never_writes(
    tmp_path: Path,
) -> None:
    runtime_root, workspace = _workspace_with_plan(tmp_path)
    saved = _execute(workspace)
    project_dir = _project_dir(runtime_root, workspace)
    before = _tree_bytes(project_dir)

    freshness = _inspect(workspace, saved)

    assert freshness["plan_snapshot_changed"] is False
    assert freshness["new_scene_ids"] == []
    assert freshness["removed_scene_ids"] == []
    assert freshness["scenes"] == [
        {"scene_id": "SCN-001", "status": "CURRENT", "reasons": []},
        {"scene_id": "SCN-002", "status": "CURRENT", "reasons": []},
    ]
    assert _tree_bytes(project_dir) == before
    assert list(
        inspect.signature(scene_export_workspace.inspect_freshness).parameters
    ) == [
        "workspace",
        "saved_scene_result",
        "anchors",
        "scene_bindings",
        "event_bindings",
    ]


def test_only_changed_scene_becomes_stale(tmp_path: Path) -> None:
    _, workspace = _workspace_with_plan(tmp_path)
    saved = _execute(workspace)

    def change_scene_one(plan: dict) -> None:
        plan["scenes"][0]["summary"] = "第一场计划摘要已经修改"
        plan["scenes"][0]["rev"] += 1

    _update_plan(workspace, "op-scene-one-change", change_scene_one)
    freshness = _inspect(workspace, saved)
    by_scene = _freshness_by_scene(freshness)

    assert freshness["plan_snapshot_changed"] is True
    assert by_scene["SCN-001"]["status"] == "STALE"
    assert by_scene["SCN-001"]["reasons"] == [
        "SCENE_REV_CHANGED",
        "SCENE_CONTENT_CHANGED",
    ]
    assert by_scene["SCN-002"] == {
        "scene_id": "SCN-002",
        "status": "CURRENT",
        "reasons": [],
    }


def test_unrelated_plan_change_does_not_stale_any_scene(tmp_path: Path) -> None:
    _, workspace = _workspace_with_plan(tmp_path)
    saved = _execute(workspace)

    _update_plan(
        workspace,
        "op-unrelated-book-note",
        lambda plan: plan["book"].update(note="与两场导出无关的规划备注"),
    )
    freshness = _inspect(workspace, saved)

    assert freshness["plan_snapshot_changed"] is True
    assert [row["status"] for row in freshness["scenes"]] == [
        "CURRENT",
        "CURRENT",
    ]
    assert all(row["reasons"] == [] for row in freshness["scenes"])


def test_new_and_removed_scenes_are_reported_separately(tmp_path: Path) -> None:
    _, add_workspace = _workspace_with_plan(tmp_path / "add")
    saved_before_add = _execute(add_workspace)

    def add_scene(plan: dict) -> None:
        scene = copy.deepcopy(plan["scenes"][1])
        scene.update(
            id="SCN-003",
            pe_refs=["PE-003"],
            summary="新增第三场",
            dialogue_hints=["新增场的信息点"],
            rev=1,
        )
        event = copy.deepcopy(plan["events"][1])
        event.update(
            id="PE-003",
            scene_ref="SCN-003",
            text="新增第三场计划事件",
            rev=1,
        )
        plan["slots"][0]["scene_refs"].append("SCN-003")
        plan["slots"][0]["rev"] += 1
        plan["scenes"].append(scene)
        plan["events"].append(event)

    _update_plan(add_workspace, "op-add-scene", add_scene)
    added = _inspect(add_workspace, saved_before_add)
    assert added["new_scene_ids"] == ["SCN-003"]
    assert added["removed_scene_ids"] == []
    assert _freshness_by_scene(added)["SCN-003"] == {
        "scene_id": "SCN-003",
        "status": "NEW",
        "reasons": ["SCENE_ADDED"],
    }

    _, remove_workspace = _workspace_with_plan(tmp_path / "remove")
    saved_before_remove = _execute(remove_workspace)

    def remove_scene(plan: dict) -> None:
        plan["slots"][0]["scene_refs"] = ["SCN-001"]
        plan["slots"][0]["rev"] += 1
        plan["scenes"] = [plan["scenes"][0]]
        plan["events"] = [plan["events"][0]]

    _update_plan(remove_workspace, "op-remove-scene", remove_scene)
    removed = _inspect(remove_workspace, saved_before_remove)
    assert removed["new_scene_ids"] == []
    assert removed["removed_scene_ids"] == ["SCN-002"]
    assert _freshness_by_scene(removed)["SCN-002"] == {
        "scene_id": "SCN-002",
        "status": "STALE",
        "reasons": ["SCENE_REMOVED"],
    }


def test_anchor_drift_only_stales_scenes_using_that_anchor(tmp_path: Path) -> None:
    _, workspace = _workspace_with_plan(tmp_path)
    saved = _execute(workspace)
    anchors = _anchors()
    location_one = next(
        anchor for anchor in anchors if anchor["anchor_id"] == "AN-LOC-001"
    )
    location_one["look"] = "纸灯巷的外观已经修改"
    location_one["revision"] = 2

    freshness = _inspect(workspace, saved, anchors=anchors)
    by_scene = _freshness_by_scene(freshness)

    assert by_scene["SCN-001"]["status"] == "STALE"
    assert by_scene["SCN-001"]["reasons"] == [
        "ANCHOR_CHANGED:AN-LOC-001"
    ]
    assert by_scene["SCN-002"]["status"] == "CURRENT"


@pytest.mark.parametrize(
    ("change_scene_binding", "change_event_binding", "expected_reason"),
    [
        (True, False, "SCENE_BINDING_CHANGED"),
        (False, True, "EVENT_BINDING_CHANGED:PE-001"),
    ],
)
def test_binding_drift_only_stales_its_scene(
    tmp_path: Path,
    change_scene_binding: bool,
    change_event_binding: bool,
    expected_reason: str,
) -> None:
    _, workspace = _workspace_with_plan(tmp_path)
    saved = _execute(workspace)
    _, scenes, events = _supplements()
    if change_scene_binding:
        scenes[0]["time"] = "雨夜稍晚"
    if change_event_binding:
        events[0]["visual"] = "密封信交接画面已调整"

    freshness = _inspect(workspace, saved, scenes=scenes, events=events)
    by_scene = _freshness_by_scene(freshness)

    assert by_scene["SCN-001"] == {
        "scene_id": "SCN-001",
        "status": "STALE",
        "reasons": [expected_reason],
    }
    assert by_scene["SCN-002"]["status"] == "CURRENT"


def test_bad_saved_result_duplicate_inputs_and_missing_anchor_fail_closed(
    tmp_path: Path,
) -> None:
    _, workspace = _workspace_with_plan(tmp_path)
    saved = _execute(workspace)

    missing_binding = copy.deepcopy(saved)
    missing_binding.pop("workspace_binding")
    with pytest.raises(
        scene_export_workspace.SceneExportWorkspaceError,
        match="SAVED_WORKSPACE_BINDING_INVALID",
    ):
        _inspect(workspace, missing_binding)

    duplicate_saved = copy.deepcopy(saved)
    duplicate_saved["workspace_binding"]["scenes"].append(
        copy.deepcopy(duplicate_saved["workspace_binding"]["scenes"][0])
    )
    with pytest.raises(
        scene_export_workspace.SceneExportWorkspaceError,
        match="SAVED_SCENE_DUPLICATE",
    ):
        _inspect(workspace, duplicate_saved)

    _, duplicate_scenes, events = _supplements()
    duplicate_scenes.append(copy.deepcopy(duplicate_scenes[0]))
    with pytest.raises(
        scene_export_workspace.SceneExportWorkspaceError,
        match="SCENE_BINDING_DUPLICATE",
    ):
        _inspect(workspace, saved, scenes=duplicate_scenes, events=events)

    anchors = [
        anchor for anchor in _anchors() if anchor["anchor_id"] != "AN-LOC-001"
    ]
    with pytest.raises(
        scene_export_workspace.SceneExportWorkspaceError,
        match="LOCATION_ANCHOR_MISSING",
    ):
        _inspect(workspace, saved, anchors=anchors)


def test_old_slot_cross_author_path_and_restart_are_closed_and_stable(
    tmp_path: Path,
) -> None:
    runtime_root, workspace = _workspace_with_plan(tmp_path / "restart")
    saved = _execute(workspace)
    first = _inspect(workspace, saved)
    restarted = WorkspaceRouter(runtime_root).open_project(
        "auth:alice", workspace.project_id
    )
    assert _inspect(restarted, saved) == first

    def replace_slot(plan: dict) -> None:
        plan["slot_sequence"] = ["S-0002"]
        plan["slots"][0]["id"] = "S-0002"
        plan["slots"][0]["outline_checkpoint"]["source_slot_ref"] = "S-0002"
        for scene in plan["scenes"]:
            scene["slot_ref"] = "S-0002"

    _update_plan(workspace, "op-replace-slot", replace_slot)
    with pytest.raises(
        chapter_slot_snapshot_tool.ChapterSlotSnapshotError,
        match="SLOT_NOT_FOUND",
    ):
        _inspect(workspace, saved)

    router = WorkspaceRouter(tmp_path / "cross-author")
    bob = router.create_project("auth:bob", "另一作者")
    with pytest.raises(
        scene_export_workspace.SceneExportWorkspaceError,
        match="SAVED_WORKSPACE_BINDING_MISMATCH",
    ):
        _inspect(bob, saved)
    _, scenes, events = _supplements()
    with pytest.raises(
        scene_export_workspace.SceneExportWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        scene_export_workspace.inspect_freshness(
            tmp_path,
            saved,
            _anchors(),
            scenes,
            events,
        )
