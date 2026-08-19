from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
TOOL_PATH = PRODUCT_ROOT / "mvp/m10_scene_slice_adapter.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import m10_scene_slice_adapter as adapter
    from mvp import scene_export_tool
finally:
    sys.path.pop(0)


def _snapshot() -> dict:
    sha = "a" * 64
    return {
        "contract": "CHAPTER_SLOT_SNAPSHOT",
        "version": "v1",
        "status": "plan",
        "source_plan_version": 7,
        "source_plan_sha256": sha,
        "generation_watermark": {
            "source_plan_version": 7,
            "source_plan_sha256": sha,
            "slot_rev": 3,
            "outline_source_commit_seq": 9,
        },
        "basis_refs": {
            "slot_ref": "S-0001",
            "scene_refs": ["SCN-001", "SCN-002"],
            "event_refs": ["PE-001", "PE-002"],
            "storyline_refs": [],
        },
        "slot_ref": "S-0001",
        "slot_rev": 3,
        "goal": "让两人决定共同送信",
        "summary": "一章两场的合成规划",
        "entry_state": "双方互不信任",
        "exit_condition": "双方形成临时同盟",
        "exit_hook": "寄件人仍未知",
        "storyline_refs": [],
        "scene_refs": ["SCN-001", "SCN-002"],
        "must_not": ["不得提前揭晓寄件人"],
        "risks": [],
        "outline_checkpoint": {
            "outline_rev": 2,
            "source_slot_ref": "S-0001",
            "source_commit_seq": 9,
        },
        "scenes": [
            {
                "id": "SCN-001",
                "rev": 2,
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
            },
            {
                "id": "SCN-002",
                "rev": 1,
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
            },
        ],
        "events": [
            {
                "id": "PE-001",
                "rev": 3,
                "scene_ref": "SCN-001",
                "text": "许岚计划把密封信交给林照",
            },
            {
                "id": "PE-002",
                "rev": 1,
                "scene_ref": "SCN-002",
                "text": "两人计划从旧码头改走水路",
            },
        ],
        "storylines": [],
    }


def _anchors() -> list[dict]:
    return [
        {
            "anchor_id": "AN-CHAR-001",
            "kind": "character",
            "entity_ref": "CH-001",
            "name": "林照",
            "aliases": [],
            "look": "深蓝雨衣，旧皮手套",
            "voice_hint": "克制",
            "status": "confirmed",
            "source_refs": ["SET-SYN-01"],
            "revision": 1,
        },
        {
            "anchor_id": "AN-CHAR-002",
            "kind": "character",
            "entity_ref": "CH-002",
            "name": "许岚",
            "aliases": [],
            "look": "灰色风衣，牛皮纸袋",
            "voice_hint": "语速快",
            "status": "confirmed",
            "source_refs": ["SET-SYN-02"],
            "revision": 1,
        },
        {
            "anchor_id": "AN-LOC-001",
            "kind": "location",
            "entity_ref": "LOC-001",
            "name": "纸灯巷",
            "aliases": [],
            "look": "雨夜青石巷，纸灯映在积水里",
            "voice_hint": "",
            "status": "confirmed",
            "source_refs": ["SET-SYN-03"],
            "revision": 1,
        },
        {
            "anchor_id": "AN-LOC-002",
            "kind": "location",
            "entity_ref": "LOC-002",
            "name": "旧码头",
            "aliases": [],
            "look": "雾中木栈桥，铁门半掩",
            "voice_hint": "",
            "status": "confirmed",
            "source_refs": ["SET-SYN-04"],
            "revision": 1,
        },
    ]


def _request() -> dict:
    return {
        "chapter_slot_snapshot": _snapshot(),
        "anchors": _anchors(),
        "export_context": {
            "project": "_synthetic_adapter",
            "generated_at": "2026-08-19 13:00:00",
            "model": "stub",
            "book_title": "雨夜送信",
            "plan_id": "PLAN-SYN-r7",
            "basis_note": "CHAPTER_SLOT_SNAPSHOT:S-0001:r3",
            "chapter_hint": 1,
            "chapter_title": "雨夜送信",
        },
        "scene_bindings": [
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
        ],
        "event_bindings": [
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
        ],
    }


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        capture_output=True,
        check=False,
    )


def test_two_scene_snapshot_enters_existing_m10_and_produces_c8() -> None:
    request = _request()
    before = copy.deepcopy(request)

    m10_request = adapter.execute(request)
    c8 = scene_export_tool.execute(m10_request)

    assert request == before
    assert m10_request["source"]["scene_export_slice"] == "m10-scene-slice-r1"
    assert m10_request["source"]["contract"] == "C7_PLOT_LAYER v1"
    assert c8["contract"] == "C8_SCENE_CARD_PROTOTYPE"
    assert c8["range"] == {
        "chapters": [1],
        "scene_ids": ["SCN-001", "SCN-002"],
    }


def test_order_source_fields_and_anchor_refs_do_not_drift() -> None:
    output = adapter.execute(_request())["source"]
    snapshot = _snapshot()

    assert [scene["id"] for scene in output["scenes"]] == snapshot["scene_refs"]
    assert [event["id"] for event in output["planned_events"]] == [
        "PE-001",
        "PE-002",
    ]
    assert output["scenes"][0]["goal"] == snapshot["scenes"][0]["goal"]
    assert output["scenes"][0]["summary"] == snapshot["scenes"][0]["summary"]
    assert output["planned_events"][0]["action"] == snapshot["events"][0]["text"]
    assert output["scenes"][0]["characters"] == ["CH-001", "CH-002"]
    assert output["scenes"][0]["location_ref"] == "AN-LOC-001"


def test_same_input_is_byte_stable() -> None:
    first = adapter.execute(_request())
    second = adapter.execute(copy.deepcopy(_request()))

    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second, ensure_ascii=False, sort_keys=True
    )


@pytest.mark.parametrize(
    ("mutate", "error_code"),
    [
        (
            lambda request: request["anchors"].pop(1),
            "CHARACTER_ANCHOR_MISSING",
        ),
        (
            lambda request: request["anchors"].append(
                {
                    **copy.deepcopy(request["anchors"][0]),
                    "anchor_id": "AN-CHAR-009",
                }
            ),
            "DUPLICATE_ANCHOR_ENTITY",
        ),
        (
            lambda request: request["scene_bindings"][0][
                "character_presence"
            ].pop("CH-002"),
            "CHARACTER_PRESENCE_INCOMPLETE",
        ),
        (
            lambda request: request["event_bindings"][0].update(
                dialogue_bindings=[]
            ),
            "DIALOGUE_BINDING_INCOMPLETE",
        ),
        (
            lambda request: request["scene_bindings"][0].update(
                location_anchor_ref="AN-LOC-999"
            ),
            "LOCATION_ANCHOR_MISSING",
        ),
        (
            lambda request: request["event_bindings"].pop(),
            "EVENT_BINDINGS_INCOMPLETE",
        ),
    ],
)
def test_missing_or_ambiguous_explicit_bindings_reject_whole_batch(
    mutate, error_code: str
) -> None:
    request = _request()
    mutate(request)

    with pytest.raises(adapter.M10SceneSliceAdapterError) as exc_info:
        adapter.execute(request)

    assert exc_info.value.code == error_code


def test_formal_c7_cannot_masquerade_as_chapter_slot_snapshot() -> None:
    request = _request()
    request["chapter_slot_snapshot"] = {
        "contract": "C7_PLOT_LAYER v1",
        "cards": [],
        "conflicts": [],
    }

    with pytest.raises(adapter.M10SceneSliceAdapterError) as exc_info:
        adapter.execute(request)

    assert exc_info.value.code == "CHAPTER_SLOT_SNAPSHOT_REQUIRED"


def test_cli_atomic_output_is_directly_consumable(tmp_path: Path) -> None:
    input_path = tmp_path / "adapter-request.json"
    output_path = tmp_path / "m10-request.json"
    input_path.write_text(json.dumps(_request(), ensure_ascii=False), encoding="utf-8")

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 0, completed.stderr.decode()
    persisted = json.loads(output_path.read_bytes())
    assert persisted == adapter.execute(_request())
    assert scene_export_tool.execute(persisted)["contract"] == "C8_SCENE_CARD_PROTOTYPE"


def test_failed_cli_does_not_overwrite_existing_output(tmp_path: Path) -> None:
    request = _request()
    request["scene_bindings"][0]["character_presence"].pop("CH-002")
    input_path = tmp_path / "bad-request.json"
    output_path = tmp_path / "existing.json"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    before = b'{"keep":"old"}\n'
    output_path.write_bytes(before)

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 2
    assert b"CHARACTER_PRESENCE_INCOMPLETE" in completed.stderr
    assert output_path.read_bytes() == before
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []
