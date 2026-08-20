from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import intent_router
finally:
    sys.path.pop(0)


ENTITIES = ["林照", "许岚", "周伯"]


def _route(text: str) -> dict:
    return intent_router.route_author_intent(text, known_entities=ENTITIES)


def test_next_chapter_has_highest_priority_and_links_relationship_only() -> None:
    result = _route("下一章让林照和许岚在渡口重逢。")

    assert result["primary_home"] == "chapter_plan"
    assert result["link_targets"] == ["relationship_arc"]
    assert result["time_horizon"] == "next_chapter_or_scene"
    assert result["entity_scope"] == {
        "kind": "chapter",
        "entities": ["林照", "许岚"],
    }


def test_current_volume_goal_routes_to_volume_outline() -> None:
    result = _route("本卷末要让林照拿到通行凭证。")

    assert result["primary_home"] == "volume_outline"
    assert result["time_horizon"] == "current_volume"
    assert result["confidence"] >= 0.9


def test_unscheduled_final_death_routes_to_character_arc() -> None:
    result = _route("周伯最后一定会死，但具体时间未定。")

    assert result["primary_home"] == "character_arc"
    assert result["commitment"] == "committed"
    assert result["time_horizon"] == "long_term_unscheduled"
    assert result["entity_scope"] == {
        "kind": "character",
        "entities": ["周伯"],
    }


def test_future_relationship_in_current_volume_links_without_copying_intent() -> None:
    intent = "林照和许岚未来会结盟，而且本卷内发生，先不定具体章节。"

    result = _route(intent)

    assert result["primary_home"] == "relationship_arc"
    assert result["link_targets"] == ["volume_outline"]
    assert result["time_horizon"] == "current_volume"
    assert intent not in str(result["link_targets"])


def test_uncommitted_unanchored_idea_routes_to_open_hook() -> None:
    result = _route("先记个灵感：也许周伯以后能有一条自己的支线。")

    assert result["primary_home"] == "open_hook"
    assert result["commitment"] == "idea"
    assert result["time_horizon"] == "unanchored"


def test_low_confidence_returns_at_most_two_candidates_and_one_question() -> None:
    result = _route("林照以后会有变化。")

    assert result["confidence"] < 0.5
    assert result["candidate_homes"] == ["character_arc", "open_hook"]
    assert result["clarification_question"] == (
        "这是人物长期走向，还是先作为未承诺灵感保存？"
    )
    assert result["clarification_question"].count("？") == 1


def test_route_is_advice_only_and_never_exposes_a_write_action() -> None:
    result = _route("下一章让林照去渡口。")

    assert result["advice_only"] is True
    assert result["writes"] == []
    assert set(result["candidate_homes"]).issubset(intent_router.HOMES)


def test_empty_intent_is_rejected() -> None:
    with pytest.raises(intent_router.IntentRoutingError) as exc_info:
        _route("  ")

    assert exc_info.value.code == "EMPTY_AUTHOR_INTENT"
