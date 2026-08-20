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
    from mvp import scene_export
finally:
    sys.path.pop(0)


def _fixture() -> dict:
    """Synthetic novel-planning example; it contains no novel corpus text."""

    return {
        "contract": "C7_PLOT_LAYER v1",
        "scene_export_slice": "m10-scene-slice-r1",
        "project": "_scene_export_synthetic",
        "generated_at": "2026-08-19 09:00:00",
        "model": "stub",
        "book_title": "纸灯巷",
        "plan_id": "PLAN-S001-r2",
        "basis_note": "plan-ledger@synthetic-02",
        "anchors": [
            {
                "anchor_id": "AN-CHAR-001",
                "kind": "character",
                "entity_ref": "CH-001",
                "name": "林照",
                "aliases": [],
                "look": "短发青年，深蓝雨衣，右手戴旧皮手套",
                "voice_hint": "年轻男声，克制",
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
                "look": "长发束起，灰色风衣，怀抱牛皮纸文件袋",
                "voice_hint": "女声，语速快",
                "status": "confirmed",
                "source_refs": ["SET-SYN-02"],
                "revision": 1,
            },
            {
                "anchor_id": "AN-LOC-001",
                "kind": "location",
                "entity_ref": "LOC-001",
                "name": "纸灯巷口",
                "aliases": [],
                "look": "雨夜青石巷，纸灯映在积水里，远处铁门半掩",
                "voice_hint": "",
                "status": "confirmed",
                "source_refs": ["SET-SYN-03"],
                "revision": 1,
            },
        ],
        "scenes": [
            {
                "id": "SCN-001",
                "chapter_hint": 1,
                "chapter_title": "雨巷来信",
                "scene_order": 1,
                "scene_count": 1,
                "goal": "让两人确认文件袋必须在天亮前送达",
                "summary": "林照在雨巷接到许岚送来的密封文件袋",
                "location_ref": "AN-LOC-001",
                "time": "雨夜",
                "visual_hint": "纸灯倒影被脚步踩碎，文件袋始终保持密封",
                "characters": ["CH-001", "CH-002"],
                "character_presence": {
                    "CH-001": "站在铁门内侧，雨衣滴水",
                    "CH-002": "从巷口跑来，护住文件袋",
                },
                "mood_in": "戒备",
                "mood_out": "形成临时同盟",
                "turn": "许岚把密封文件袋交到林照手中",
                "pov": "CH-001",
                "resistance": "两人都不愿先说明各自掌握的来源",
                "writing_guidance": ["只拍交接动作，不补文件内容"],
                "spoiler_guard": [
                    {
                        "audience_state": "known_at_scene",
                        "instruction": "画面不得展示文件袋内页或寄件人身份",
                    }
                ],
                "dialogue_hints": [
                    {
                        "id": "D-001",
                        "kind": "information_point",
                        "speaker_ref": "CH-002",
                        "info": "强调文件袋必须在天亮前送达",
                        "tone": "急促但压低声音",
                    }
                ],
                "pe_refs": ["PE-001"],
            }
        ],
        "planned_events": [
            {
                "id": "PE-001",
                "scene_ref": "SCN-001",
                "action": "许岚把密封文件袋交给林照",
                "visual": "中景：灰色风衣女子把文件袋递向蓝色雨衣青年",
                "dialogue_hint_refs": ["D-001"],
                "shot_hint": "中景，手部特写收尾",
            }
        ],
    }


def _all_keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key
            for child in value.values()
            for key in _all_keys(child)
        }
    if isinstance(value, list):
        return {key for child in value for key in _all_keys(child)}
    return set()


def test_exports_usable_c8_prototype_from_valid_c7_fixture() -> None:
    result = scene_export.export_scene_cards(_fixture())

    scene_export.validate_c8_prototype(result)
    assert result["contract"] == "C8_SCENE_CARD_PROTOTYPE"
    assert result["version"] == "v0-prototype-r1"
    assert result["range"] == {"chapters": [1], "scene_ids": ["SCN-001"]}
    assert result["ai_label"]["contains_ai_generated_content"] is False
    card = result["cards"][0]
    assert card["cast"] == [
        {"anchor_ref": "AN-CHAR-001", "presence": "站在铁门内侧，雨衣滴水"},
        {"anchor_ref": "AN-CHAR-002", "presence": "从巷口跑来，护住文件袋"},
    ]
    assert "短发青年，深蓝雨衣" in card["scene_prompt"]
    assert "长发束起，灰色风衣" in card["scene_prompt"]
    assert card["dialogue_sheet"] == [
        {
            "speaker": "许岚",
            "info": "强调文件袋必须在天亮前送达",
            "tone": "急促但压低声音",
        }
    ]
    assert card["dont_show"] == ["禁止：画面不得展示文件袋内页或寄件人身份"]
    assert {"line", "quote", "verbatim", "future_reveal"}.isdisjoint(
        _all_keys(result)
    )


def test_rejects_scene_character_without_visual_anchor() -> None:
    fixture = _fixture()
    fixture["anchors"] = [
        anchor for anchor in fixture["anchors"] if anchor["entity_ref"] != "CH-002"
    ]

    with pytest.raises(scene_export.SceneExportError) as exc_info:
        scene_export.export_scene_cards(fixture)

    assert exc_info.value.code == "MISSING_CHARACTER_ANCHOR"


def test_rejects_structured_future_spoiler() -> None:
    fixture = _fixture()
    fixture["scenes"][0]["spoiler_guard"][0]["audience_state"] = "future_reveal"

    with pytest.raises(scene_export.SceneExportError) as exc_info:
        scene_export.export_scene_cards(fixture)

    assert exc_info.value.code == "FUTURE_SPOILER_FORBIDDEN"


def test_rejects_verbatim_dialogue_instead_of_information_point() -> None:
    fixture = _fixture()
    fixture["scenes"][0]["dialogue_hints"][0] = {
        "id": "D-001",
        "kind": "verbatim_line",
        "speaker_ref": "CH-002",
        "line": "天亮前，一定要送到。",
        "tone": "急促",
    }

    with pytest.raises(scene_export.SceneExportError) as exc_info:
        scene_export.export_scene_cards(fixture)

    assert exc_info.value.code == "DIALOGUE_PROSE_FORBIDDEN"


def test_repeated_exports_are_byte_for_byte_deterministic() -> None:
    fixture = _fixture()

    first = scene_export.dumps_scene_cards(fixture)
    second = scene_export.dumps_scene_cards(copy.deepcopy(fixture))

    assert first == second
    assert json.loads(first)["export_id"].startswith("EXP-")


def test_renders_short_user_visible_scene_card_demo() -> None:
    result = scene_export.export_scene_cards(_fixture())

    demo = scene_export.render_scene_card(result)

    assert demo.startswith("【纸灯巷 · 第1章「雨巷来信」 · 场1/1】")
    assert "林照：短发青年，深蓝雨衣" in demo
    assert "许岚→强调文件袋必须在天亮前送达（急促但压低声音）" in demo
    assert "禁止：画面不得展示文件袋内页或寄件人身份" in demo
