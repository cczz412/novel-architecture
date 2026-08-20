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
    from mvp import scene_state_interval_resolver as resolver
finally:
    sys.path.pop(0)


def _candidate(
    *,
    entity_ref: str,
    anchor: str,
    start: int | None,
    end: int | None,
    summary: str,
    source_ref: str = "SRC-001",
    source_revision: int = 1,
) -> dict:
    return {
        "entity_ref": entity_ref,
        "state_anchor_ref": anchor,
        "effective_interval": {"start": start, "end": end},
        "source_ref": source_ref,
        "source_revision": source_revision,
        "state_summary": summary,
    }


def _request(
    *,
    scene_start: object = 2,
    scene_end: object = 3,
    character_refs: list[str] | None = None,
    candidates: list[dict] | None = None,
    scene_plan_revision: object = 4,
) -> dict:
    return {
        "scene_ref": "SCN-001",
        "scene_plan_ref": "PLAN-001",
        "scene_plan_revision": scene_plan_revision,
        "scene_story_interval": {"start": scene_start, "end": scene_end},
        "character_refs": list(
            character_refs if character_refs is not None else ["CH-001"]
        ),
        "state_candidates": list(
            candidates
            if candidates is not None
            else [
                _candidate(
                    entity_ref="CH-001",
                    anchor="ST-UNINJURED",
                    start=1,
                    end=3,
                    summary="左臂未受伤",
                ),
                _candidate(
                    entity_ref="CH-001",
                    anchor="ST-BANDAGE",
                    start=3,
                    end=None,
                    summary="左臂缠着新绷带",
                ),
            ]
        ),
    }


def _expected_sha(request: dict) -> str:
    candidates = [
        resolver._candidate(row, index)
        for index, row in enumerate(request["state_candidates"])
    ]
    return resolver._sha256(
        resolver._canonical_request(
            scene_ref=request["scene_ref"],
            scene_plan_ref=request["scene_plan_ref"],
            scene_plan_revision=request["scene_plan_revision"],
            scene_story_interval=request["scene_story_interval"],
            character_refs=request["character_refs"],
            candidates=candidates,
        )
    )


def _dump(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def test_scene_before_injury_selects_uninjured_stage_not_bandage() -> None:
    request = _request()
    before = copy.deepcopy(request)

    result = resolver.execute(request)

    assert request == before
    assert [row["state_anchor_ref"] for row in result["selected_states"]] == [
        "ST-UNINJURED"
    ]
    assert result["selected_states"][0]["state_summary"] == "左臂未受伤"
    assert result["character_match_stats"] == [
        {"entity_ref": "CH-001", "candidate_count": 2, "match_count": 1}
    ]
    assert "绷带" not in json.dumps(result, ensure_ascii=False)
    assert result["canonical_input_sha256"] == _expected_sha(request)


def test_scene_after_injury_selects_open_ended_bandage_stage() -> None:
    request = _request(scene_start=3, scene_end=4)

    result = resolver.execute(request)

    assert result["selected_states"][0]["state_anchor_ref"] == "ST-BANDAGE"
    assert result["selected_states"][0]["state_summary"] == "左臂缠着新绷带"
    assert result["selected_states"][0]["effective_interval"] == {
        "start": 3,
        "end": None,
    }
    assert result["canonical_input_sha256"] == _expected_sha(request)


def test_open_start_state_interval_can_unique_match() -> None:
    request = _request(
        scene_start=1,
        scene_end=2,
        candidates=[
            _candidate(
                entity_ref="CH-001",
                anchor="ST-UNINJURED",
                start=None,
                end=3,
                summary="左臂未受伤",
            ),
            _candidate(
                entity_ref="CH-001",
                anchor="ST-BANDAGE",
                start=3,
                end=None,
                summary="左臂缠着新绷带",
            ),
        ],
    )

    result = resolver.execute(request)

    assert result["selected_states"][0]["effective_interval"] == {
        "start": None,
        "end": 3,
    }
    assert "绷带" not in json.dumps(result, ensure_ascii=False)


def test_arbitrarily_large_integer_ordinals_do_not_lose_boundary_precision() -> None:
    boundary = 10**400
    request = _request(
        scene_start=boundary,
        scene_end=boundary + 1,
        candidates=[
            _candidate(
                entity_ref="CH-001",
                anchor="ST-BEFORE",
                start=boundary,
                end=boundary + 1,
                summary="仍处于前一阶段",
            ),
            _candidate(
                entity_ref="CH-001",
                anchor="ST-AFTER",
                start=boundary + 1,
                end=None,
                summary="进入后一阶段",
            ),
        ],
    )

    result = resolver.execute(request)

    assert result["selected_states"][0]["state_anchor_ref"] == "ST-BEFORE"
    assert result["selected_states"][0]["effective_interval"]["end"] == boundary + 1


@pytest.mark.parametrize(
    ("payload", "error_code"),
    [
        (
            _request(
                candidates=[
                    _candidate(
                        entity_ref="CH-001",
                        anchor="ST-UNINJURED",
                        start=1,
                        end=4,
                        summary="左臂未受伤",
                    ),
                    _candidate(
                        entity_ref="CH-001",
                        anchor="ST-BANDAGE",
                        start=3,
                        end=None,
                        summary="左臂缠着新绷带",
                    ),
                ]
            ),
            "STATE_INTERVAL_CONFLICT",
        ),
        (
            _request(scene_start=2, scene_end=4),
            "AMBIGUOUS_STAGE_MATCH",
        ),
        (
            _request(scene_start=0, scene_end=1),
            "NO_STAGE_MATCH",
        ),
        (
            _request(character_refs=["CH-001", "CH-002"]),
            "CHARACTER_REF_MISSING",
        ),
        (
            _request(
                candidates=_request()["state_candidates"]
                + [
                    _candidate(
                        entity_ref="CH-002",
                        anchor="ST-OTHER",
                        start=1,
                        end=3,
                        summary="旁观",
                    )
                ]
            ),
            "EXTRA_CHARACTER_REF",
        ),
        (
            _request(character_refs=["CH-001", "CH-001"]),
            "DUPLICATE_REFERENCE",
        ),
        (
            _request(
                candidates=[
                    _candidate(
                        entity_ref="CH-001",
                        anchor="ST-UNINJURED",
                        start=1,
                        end=3,
                        summary="左臂未受伤",
                    ),
                    _candidate(
                        entity_ref="CH-001",
                        anchor="ST-UNINJURED",
                        start=3,
                        end=None,
                        summary="左臂缠着新绷带",
                    ),
                ]
            ),
            "DUPLICATE_REFERENCE",
        ),
        (_request(scene_plan_revision=True), "REVISION_INVALID"),
        (
            _request(
                candidates=[
                    _candidate(
                        entity_ref="CH-001",
                        anchor="ST-UNINJURED",
                        start=1,
                        end=3,
                        summary="左臂未受伤",
                        source_revision=0,
                    )
                ]
            ),
            "REVISION_INVALID",
        ),
        (_request(scene_start="受伤前", scene_end=3), "STORY_TIME_UNRESOLVED"),
        (
            _request(
                candidates=[
                    _candidate(
                        entity_ref="CH-001",
                        anchor="ST-UNINJURED",
                        start="受伤前",
                        end=3,
                        summary="左臂未受伤",
                    )
                ]
            ),
            "STORY_TIME_UNRESOLVED",
        ),
        (
            _request(
                candidates=[
                    _candidate(
                        entity_ref="CH-001",
                        anchor="ST-EMPTY",
                        start=1,
                        end=3,
                        summary="   ",
                    )
                ]
            ),
            "TEXT_REQUIRED",
        ),
        (
            _request(
                candidates=[
                    _candidate(
                        entity_ref="CH-001",
                        anchor="ST-CURRENT",
                        start=None,
                        end=None,
                        summary="当前外观",
                    )
                ]
            ),
            "STORY_TIME_UNRESOLVED",
        ),
        (_request(scene_start=True, scene_end=3), "STORY_TIME_UNRESOLVED"),
        (_request(scene_start=2, scene_end=True), "STORY_TIME_UNRESOLVED"),
        (_request(scene_start=None, scene_end=3), "STORY_TIME_UNRESOLVED"),
        (
            {
                **_request(),
                "scene_story_interval": {"start": 2},
            },
            "STORY_TIME_UNRESOLVED",
        ),
        (
            _request(
                candidates=[
                    _candidate(
                        entity_ref="CH-001",
                        anchor="ST-UNINJURED",
                        start=False,
                        end=3,
                        summary="左臂未受伤",
                    )
                ]
            ),
            "STORY_TIME_UNRESOLVED",
        ),
    ],
)
def test_conflict_gap_identity_and_unresolved_time_all_hard_stop(
    payload: dict, error_code: str
) -> None:
    before = copy.deepcopy(payload)

    with pytest.raises(resolver.SceneStateIntervalResolverError) as exc_info:
        resolver.execute(payload)

    assert payload == before
    assert exc_info.value.code == error_code


def test_one_character_match_does_not_rescue_another_zero_match() -> None:
    request = _request(
        character_refs=["CH-001", "CH-002"],
        candidates=[
            _candidate(
                entity_ref="CH-001",
                anchor="ST-UNINJURED",
                start=1,
                end=3,
                summary="左臂未受伤",
            ),
            _candidate(
                entity_ref="CH-002",
                anchor="ST-LATER",
                start=8,
                end=None,
                summary="尚未出场",
            ),
        ],
    )

    with pytest.raises(resolver.SceneStateIntervalResolverError) as exc_info:
        resolver.execute(request)

    assert exc_info.value.code == "NO_STAGE_MATCH"
    assert "CH-002" in str(exc_info.value)


def test_candidate_order_does_not_change_canonical_output() -> None:
    first = _request(
        character_refs=["CH-001", "CH-002"],
        candidates=[
            _candidate(
                entity_ref="CH-002",
                anchor="ST-B",
                start=1,
                end=None,
                summary="在场",
            ),
            _candidate(
                entity_ref="CH-001",
                anchor="ST-BANDAGE",
                start=3,
                end=None,
                summary="左臂缠着新绷带",
            ),
            _candidate(
                entity_ref="CH-001",
                anchor="ST-UNINJURED",
                start=1,
                end=3,
                summary="左臂未受伤",
            ),
        ],
    )
    second = copy.deepcopy(first)
    second["state_candidates"] = list(reversed(first["state_candidates"]))

    left = resolver.execute(first)
    right = resolver.execute(second)

    assert _dump(left) == _dump(right)
    assert left["canonical_input_sha256"] == right["canonical_input_sha256"]
    assert left["canonical_input_sha256"] == _expected_sha(first)
    assert [row["entity_ref"] for row in left["selected_states"]] == [
        "CH-001",
        "CH-002",
    ]
    assert "绷带" not in json.dumps(left, ensure_ascii=False)


def test_same_input_output_bytes_are_stable_and_request_is_not_mutated() -> None:
    request = _request()
    before = copy.deepcopy(request)

    first = resolver.execute(request)
    second = resolver.execute(request)

    assert request == before
    assert _dump(first) == _dump(second)
    assert first == json.loads(_dump(first))
