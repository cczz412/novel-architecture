"""纯对象、显式整数区间的场景人物状态 resolver 原型。

调用方必须自己给出半开整数序位。这里不解析自然语言，不把章号
当成故事时间，也不接入现役场景导出或人物阶段账。
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, NoReturn


REQUEST_KEYS = {
    "scene_ref",
    "scene_plan_ref",
    "scene_plan_revision",
    "scene_story_interval",
    "character_refs",
    "state_candidates",
}
INTERVAL_KEYS = {"start", "end"}
CANDIDATE_KEYS = {
    "entity_ref",
    "state_anchor_ref",
    "effective_interval",
    "source_ref",
    "source_revision",
    "state_summary",
}


class SceneStateIntervalResolverError(ValueError):
    """显式故事时间区间无法唯一落到每个人物的一个阶段。"""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _fail(code: str, detail: str = "") -> NoReturn:
    raise SceneStateIntervalResolverError(code, detail)


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise SceneStateIntervalResolverError("VALUE_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail("TEXT_REQUIRED", field)
    return value


def _revision(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail("REVISION_INVALID", field)
    return value


def _ordinal(value: object, field: str, *, allow_null: bool) -> int | None:
    if value is None:
        if allow_null:
            return None
        _fail("STORY_TIME_UNRESOLVED", field)
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("STORY_TIME_UNRESOLVED", field)
    return value


def _interval(
    raw: object, field: str, *, allow_open: bool
) -> dict[str, int | None]:
    if not isinstance(raw, dict) or set(raw) != INTERVAL_KEYS:
        _fail("STORY_TIME_UNRESOLVED", field)
    start = _ordinal(raw.get("start"), f"{field}.start", allow_null=allow_open)
    end = _ordinal(raw.get("end"), f"{field}.end", allow_null=allow_open)
    if start is None and end is None:
        _fail("STORY_TIME_UNRESOLVED", field)
    if start is not None and end is not None and start >= end:
        _fail("STORY_TIME_UNRESOLVED", field)
    return {"start": start, "end": end}


def _starts_before_end(start: int | None, end: int | None) -> bool:
    if start is None or end is None:
        return True
    return start < end


def _starts_at_or_before(outer: int | None, inner: int | None) -> bool:
    if outer is None:
        return True
    if inner is None:
        return False
    return outer <= inner


def _ends_at_or_after(outer: int | None, inner: int | None) -> bool:
    if outer is None:
        return True
    if inner is None:
        return False
    return outer >= inner


def _overlaps(left: dict[str, int | None], right: dict[str, int | None]) -> bool:
    return _starts_before_end(
        left["start"], right["end"]
    ) and _starts_before_end(right["start"], left["end"])


def _contains(outer: dict[str, int | None], inner: dict[str, int | None]) -> bool:
    return _starts_at_or_before(
        outer["start"], inner["start"]
    ) and _ends_at_or_after(outer["end"], inner["end"])


def _character_refs(raw: object) -> list[str]:
    if not isinstance(raw, list):
        _fail("ARRAY_REQUIRED", "character_refs")
    if not raw:
        _fail("CHARACTER_REFS_EMPTY")
    refs = [_text(item, f"character_refs[{index}]") for index, item in enumerate(raw)]
    if len(refs) != len(set(refs)):
        _fail("DUPLICATE_REFERENCE", "character_refs")
    return refs


def _candidate(raw: object, index: int) -> dict[str, Any]:
    field = f"state_candidates[{index}]"
    if not isinstance(raw, dict) or set(raw) != CANDIDATE_KEYS:
        _fail("FIELDS_INVALID", field)
    return {
        "entity_ref": _text(raw.get("entity_ref"), f"{field}.entity_ref"),
        "state_anchor_ref": _text(
            raw.get("state_anchor_ref"), f"{field}.state_anchor_ref"
        ),
        "effective_interval": _interval(
            raw.get("effective_interval"),
            f"{field}.effective_interval",
            allow_open=True,
        ),
        "source_ref": _text(raw.get("source_ref"), f"{field}.source_ref"),
        "source_revision": _revision(
            raw.get("source_revision"), f"{field}.source_revision"
        ),
        "state_summary": _text(
            raw.get("state_summary"), f"{field}.state_summary"
        ),
    }


def _bound_sort_key(value: int | None) -> tuple[int, int]:
    if value is None:
        return (0, 0)
    return (1, value)


def _canonical_request(
    *,
    scene_ref: str,
    scene_plan_ref: str,
    scene_plan_revision: int,
    scene_story_interval: dict[str, int | None],
    character_refs: list[str],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    rank = {ref: index for index, ref in enumerate(character_refs)}
    ordered = sorted(
        candidates,
        key=lambda row: (
            rank[row["entity_ref"]],
            row["state_anchor_ref"],
            row["source_ref"],
            row["source_revision"],
            _bound_sort_key(row["effective_interval"]["start"]),
            _bound_sort_key(row["effective_interval"]["end"]),
            row["state_summary"],
        ),
    )
    return {
        "scene_ref": scene_ref,
        "scene_plan_ref": scene_plan_ref,
        "scene_plan_revision": scene_plan_revision,
        "scene_story_interval": copy.deepcopy(scene_story_interval),
        "character_refs": list(character_refs),
        "state_candidates": [copy.deepcopy(row) for row in ordered],
    }


def _resolve_character(
    entity_ref: str,
    candidates: list[dict[str, Any]],
    scene_interval: dict[str, int | None],
) -> dict[str, Any]:
    for left_index, left in enumerate(candidates):
        for right in candidates[left_index + 1 :]:
            if _overlaps(left["effective_interval"], right["effective_interval"]):
                _fail("STATE_INTERVAL_CONFLICT", entity_ref)

    overlapping = [
        row
        for row in candidates
        if _overlaps(row["effective_interval"], scene_interval)
    ]
    containing = [
        row
        for row in candidates
        if _contains(row["effective_interval"], scene_interval)
    ]
    if len(overlapping) > 1:
        _fail("AMBIGUOUS_STAGE_MATCH", entity_ref)
    if len(containing) != 1:
        _fail("NO_STAGE_MATCH", entity_ref)
    return containing[0]


def execute(request: dict) -> dict:
    """按显式半开整数区间为每个出场人物选出唯一阶段。"""
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        _fail("REQUEST_FIELDS_INVALID")

    scene_ref = _text(request.get("scene_ref"), "scene_ref")
    scene_plan_ref = _text(request.get("scene_plan_ref"), "scene_plan_ref")
    scene_plan_revision = _revision(
        request.get("scene_plan_revision"), "scene_plan_revision"
    )
    scene_interval = _interval(
        request.get("scene_story_interval"),
        "scene_story_interval",
        allow_open=False,
    )
    character_refs = _character_refs(request.get("character_refs"))
    raw_candidates = request.get("state_candidates")
    if not isinstance(raw_candidates, list):
        _fail("ARRAY_REQUIRED", "state_candidates")

    candidates = [_candidate(row, index) for index, row in enumerate(raw_candidates)]
    allowed = set(character_refs)
    for row in candidates:
        if row["entity_ref"] not in allowed:
            _fail("EXTRA_CHARACTER_REF", row["entity_ref"])

    seen_anchors: set[tuple[str, str]] = set()
    grouped: dict[str, list[dict[str, Any]]] = {ref: [] for ref in character_refs}
    for row in candidates:
        anchor_key = (row["entity_ref"], row["state_anchor_ref"])
        if anchor_key in seen_anchors:
            _fail("DUPLICATE_REFERENCE", ":".join(anchor_key))
        seen_anchors.add(anchor_key)
        grouped[row["entity_ref"]].append(row)

    for entity_ref in character_refs:
        if not grouped[entity_ref]:
            _fail("CHARACTER_REF_MISSING", entity_ref)

    selected_states: list[dict[str, Any]] = []
    character_match_stats: list[dict[str, Any]] = []
    for entity_ref in character_refs:
        rows = grouped[entity_ref]
        selected = _resolve_character(entity_ref, rows, scene_interval)
        selected_states.append(copy.deepcopy(selected))
        character_match_stats.append(
            {
                "entity_ref": entity_ref,
                "candidate_count": len(rows),
                "match_count": 1,
            }
        )

    return {
        "canonical_input_sha256": _sha256(
            _canonical_request(
                scene_ref=scene_ref,
                scene_plan_ref=scene_plan_ref,
                scene_plan_revision=scene_plan_revision,
                scene_story_interval=scene_interval,
                character_refs=character_refs,
                candidates=candidates,
            )
        ),
        "selected_states": selected_states,
        "character_match_stats": character_match_stats,
    }
