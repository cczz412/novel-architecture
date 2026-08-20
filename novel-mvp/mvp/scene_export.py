"""M10 zero-model scene-card exporter.

The exporter consumes the normalized scene slice anticipated by the M10 design
and emits a deterministic C8 prototype.  It does not freeze a C8 contract and
does not adapt the current question-oriented C7 runtime; that compatibility
adapter is a later seam.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from typing import Any, NoReturn


SOURCE_CONTRACT = "C7_PLOT_LAYER v1"
SOURCE_SLICE = "m10-scene-slice-r1"
PROTOTYPE_CONTRACT = "C8_SCENE_CARD_PROTOTYPE"
PROTOTYPE_VERSION = "v0-prototype-r1"


class SceneExportError(ValueError):
    """The source slice cannot be exported without inventing or leaking data."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _fail(code: str, detail: str = "") -> NoReturn:
    raise SceneExportError(code, detail)


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("INVALID_SHAPE", f"{path} must be an object")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("INVALID_SHAPE", f"{path} must be a list")
    return value


def _text(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        _fail("INVALID_SHAPE", f"{path} must be a string")
    result = value.strip()
    if not allow_empty and not result:
        _fail("INVALID_SHAPE", f"{path} must not be empty")
    return result


def _integer(value: Any, path: str, *, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        _fail("INVALID_SHAPE", f"{path} must be an integer >= {minimum}")
    return value


def _only_fields(value: Mapping[str, Any], allowed: set[str], path: str) -> None:
    extras = sorted(set(value) - allowed)
    if extras:
        _fail("UNKNOWN_FIELDS", f"{path}: {extras}")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_sha(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_anchor(raw: Any, index: int) -> dict[str, Any]:
    anchor = _mapping(raw, f"anchors[{index}]")
    allowed = {
        "anchor_id",
        "kind",
        "entity_ref",
        "name",
        "aliases",
        "look",
        "voice_hint",
        "status",
        "source_refs",
        "revision",
    }
    _only_fields(anchor, allowed, f"anchors[{index}]")
    kind = _text(anchor.get("kind"), f"anchors[{index}].kind")
    if kind not in {"character", "location"}:
        _fail("INVALID_ANCHOR_KIND", kind)
    status = _text(anchor.get("status"), f"anchors[{index}].status")
    if status not in {"draft", "confirmed"}:
        _fail("INVALID_ANCHOR_STATUS", status)
    aliases = [
        _text(item, f"anchors[{index}].aliases[{alias_index}]")
        for alias_index, item in enumerate(
            _list(anchor.get("aliases"), f"anchors[{index}].aliases")
        )
    ]
    source_refs = [
        _text(item, f"anchors[{index}].source_refs[{source_index}]")
        for source_index, item in enumerate(
            _list(anchor.get("source_refs"), f"anchors[{index}].source_refs")
        )
    ]
    return {
        "anchor_id": _text(anchor.get("anchor_id"), f"anchors[{index}].anchor_id"),
        "kind": kind,
        "entity_ref": _text(anchor.get("entity_ref"), f"anchors[{index}].entity_ref"),
        "name": _text(anchor.get("name"), f"anchors[{index}].name"),
        "aliases": aliases,
        "look": _text(anchor.get("look"), f"anchors[{index}].look"),
        "voice_hint": _text(
            anchor.get("voice_hint", ""),
            f"anchors[{index}].voice_hint",
            allow_empty=True,
        ),
        "status": status,
        "source_refs": source_refs,
        "revision": _integer(anchor.get("revision"), f"anchors[{index}].revision"),
    }


def _anchor_indexes(
    anchors: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    characters: dict[str, dict[str, Any]] = {}
    for anchor in anchors:
        anchor_id = anchor["anchor_id"]
        entity_ref = anchor["entity_ref"]
        if anchor_id in by_id:
            _fail("DUPLICATE_ANCHOR_ID", anchor_id)
        by_id[anchor_id] = anchor
        if anchor["kind"] == "character":
            if entity_ref in characters:
                _fail("DUPLICATE_CHARACTER_ANCHOR", entity_ref)
            characters[entity_ref] = anchor
    return by_id, characters


def _dialogue_hints(
    raw_hints: Any,
    scene_id: str,
    character_anchors: Mapping[str, dict[str, Any]],
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    rows: list[dict[str, str]] = []
    by_id: dict[str, dict[str, str]] = {}
    for index, raw in enumerate(_list(raw_hints, f"scenes[{scene_id}].dialogue_hints")):
        hint = _mapping(raw, f"scenes[{scene_id}].dialogue_hints[{index}]")
        prose_fields = sorted(set(hint) & {"line", "quote", "verbatim", "dialogue_text"})
        if prose_fields or hint.get("kind") != "information_point":
            _fail(
                "DIALOGUE_PROSE_FORBIDDEN",
                f"scene={scene_id}, index={index}, fields={prose_fields}",
            )
        _only_fields(
            hint,
            {"id", "kind", "speaker_ref", "info", "tone"},
            f"scenes[{scene_id}].dialogue_hints[{index}]",
        )
        hint_id = _text(hint.get("id"), f"dialogue_hints[{index}].id")
        if hint_id in by_id:
            _fail("DUPLICATE_DIALOGUE_HINT", hint_id)
        speaker_ref = _text(
            hint.get("speaker_ref"), f"dialogue_hints[{index}].speaker_ref"
        )
        anchor = character_anchors.get(speaker_ref)
        if anchor is None:
            _fail("MISSING_CHARACTER_ANCHOR", speaker_ref)
        row = {
            "id": hint_id,
            "speaker_ref": speaker_ref,
            "speaker": anchor["name"],
            "info": _text(hint.get("info"), f"dialogue_hints[{index}].info"),
            "tone": _text(hint.get("tone"), f"dialogue_hints[{index}].tone"),
        }
        rows.append(row)
        by_id[hint_id] = row
    return rows, by_id


def _spoiler_guards(raw_guards: Any, scene_id: str) -> list[str]:
    result: list[str] = []
    for index, raw in enumerate(_list(raw_guards, f"scenes[{scene_id}].spoiler_guard")):
        guard = _mapping(raw, f"scenes[{scene_id}].spoiler_guard[{index}]")
        _only_fields(
            guard,
            {"audience_state", "instruction"},
            f"scenes[{scene_id}].spoiler_guard[{index}]",
        )
        audience_state = _text(
            guard.get("audience_state"),
            f"scenes[{scene_id}].spoiler_guard[{index}].audience_state",
        )
        if audience_state != "known_at_scene":
            _fail(
                "FUTURE_SPOILER_FORBIDDEN",
                f"scene={scene_id}, audience_state={audience_state}",
            )
        instruction = _text(
            guard.get("instruction"),
            f"scenes[{scene_id}].spoiler_guard[{index}].instruction",
        )
        result.append(f"禁止：{instruction}")
    return result


def _normalize_event(raw: Any, index: int) -> dict[str, Any]:
    event = _mapping(raw, f"planned_events[{index}]")
    _only_fields(
        event,
        {"id", "scene_ref", "action", "visual", "dialogue_hint_refs", "shot_hint"},
        f"planned_events[{index}]",
    )
    return {
        "id": _text(event.get("id"), f"planned_events[{index}].id"),
        "scene_ref": _text(event.get("scene_ref"), f"planned_events[{index}].scene_ref"),
        "action": _text(event.get("action"), f"planned_events[{index}].action"),
        "visual": _text(event.get("visual"), f"planned_events[{index}].visual"),
        "dialogue_hint_refs": [
            _text(item, f"planned_events[{index}].dialogue_hint_refs[{ref_index}]")
            for ref_index, item in enumerate(
                _list(
                    event.get("dialogue_hint_refs"),
                    f"planned_events[{index}].dialogue_hint_refs",
                )
            )
        ],
        "shot_hint": _text(event.get("shot_hint"), f"planned_events[{index}].shot_hint"),
    }


def _shot_dialogue(
    hint_refs: list[str], dialogue_by_id: Mapping[str, dict[str, str]], event_id: str
) -> str | None:
    rows = []
    for hint_ref in hint_refs:
        hint = dialogue_by_id.get(hint_ref)
        if hint is None:
            _fail("DIALOGUE_HINT_NOT_FOUND", f"event={event_id}, hint={hint_ref}")
        rows.append(f"{hint['speaker']}→{hint['info']}（语气：{hint['tone']}）")
    return "；".join(rows) if rows else None


def _export_scene(
    raw: Any,
    *,
    anchor_by_id: Mapping[str, dict[str, Any]],
    character_anchors: Mapping[str, dict[str, Any]],
    event_by_id: Mapping[str, dict[str, Any]],
    source: Mapping[str, str],
) -> dict[str, Any]:
    scene = _mapping(raw, "scenes[]")
    allowed = {
        "id",
        "chapter_hint",
        "chapter_title",
        "scene_order",
        "scene_count",
        "goal",
        "summary",
        "location_ref",
        "time",
        "visual_hint",
        "characters",
        "character_presence",
        "mood_in",
        "mood_out",
        "turn",
        "pov",
        "resistance",
        "writing_guidance",
        "spoiler_guard",
        "dialogue_hints",
        "pe_refs",
    }
    _only_fields(scene, allowed, "scenes[]")
    scene_id = _text(scene.get("id"), "scenes[].id")
    character_refs = [
        _text(item, f"scenes[{scene_id}].characters[{index}]")
        for index, item in enumerate(
            _list(scene.get("characters"), f"scenes[{scene_id}].characters")
        )
    ]
    if not character_refs:
        _fail("MISSING_CHARACTER_ANCHOR", f"scene={scene_id}: no characters")
    presence = _mapping(
        scene.get("character_presence"), f"scenes[{scene_id}].character_presence"
    )
    cast = []
    for character_ref in character_refs:
        anchor = character_anchors.get(character_ref)
        if anchor is None:
            _fail("MISSING_CHARACTER_ANCHOR", character_ref)
        cast.append(
            {
                "anchor_ref": anchor["anchor_id"],
                "presence": _text(
                    presence.get(character_ref),
                    f"scenes[{scene_id}].character_presence[{character_ref}]",
                ),
            }
        )
    unknown_presence = sorted(set(presence) - set(character_refs))
    if unknown_presence:
        _fail("UNKNOWN_CHARACTER_PRESENCE", str(unknown_presence))

    location_ref = _text(scene.get("location_ref"), f"scenes[{scene_id}].location_ref")
    location_anchor = anchor_by_id.get(location_ref)
    if location_anchor is None or location_anchor["kind"] != "location":
        _fail("MISSING_LOCATION_ANCHOR", location_ref)

    pov = scene.get("pov")
    if pov is not None:
        pov = _text(pov, f"scenes[{scene_id}].pov")
        if pov not in character_anchors:
            _fail("MISSING_CHARACTER_ANCHOR", pov)

    dialogue_rows, dialogue_by_id = _dialogue_hints(
        scene.get("dialogue_hints"), scene_id, character_anchors
    )
    dont_show = _spoiler_guards(scene.get("spoiler_guard"), scene_id)
    pe_refs = [
        _text(item, f"scenes[{scene_id}].pe_refs[{index}]")
        for index, item in enumerate(_list(scene.get("pe_refs"), f"scenes[{scene_id}].pe_refs"))
    ]
    shots = [
        {
            "shot_no": 1,
            "beat_ref": None,
            "action": f"开场环境镜：{_text(scene.get('visual_hint'), f'scenes[{scene_id}].visual_hint')}",
            "visual": location_anchor["look"],
            "dialogue": None,
            "shot_hint": "全景",
            "duration_hint_s": 3,
        }
    ]
    for pe_ref in pe_refs:
        event = event_by_id.get(pe_ref)
        if event is None or event["scene_ref"] != scene_id:
            _fail("PLANNED_EVENT_NOT_FOUND", f"scene={scene_id}, event={pe_ref}")
        dialogue = _shot_dialogue(event["dialogue_hint_refs"], dialogue_by_id, pe_ref)
        shots.append(
            {
                "shot_no": len(shots) + 1,
                "beat_ref": pe_ref,
                "action": event["action"],
                "visual": event["visual"],
                "dialogue": dialogue,
                "shot_hint": event["shot_hint"],
                "duration_hint_s": 5 if dialogue else 3,
            }
        )

    turn = _text(scene.get("turn"), f"scenes[{scene_id}].turn")
    character_looks = "；".join(
        f"{character_anchors[ref]['name']}：{character_anchors[ref]['look']}"
        for ref in character_refs
    )
    mood_in = _text(scene.get("mood_in"), f"scenes[{scene_id}].mood_in")
    mood_out = _text(scene.get("mood_out"), f"scenes[{scene_id}].mood_out")
    guidance = [
        _text(item, f"scenes[{scene_id}].writing_guidance[{index}]")
        for index, item in enumerate(
            _list(
                scene.get("writing_guidance"),
                f"scenes[{scene_id}].writing_guidance",
            )
        )
    ]
    return {
        "card_id": f"SC-{scene_id}",
        "chapter_hint": _integer(
            scene.get("chapter_hint"), f"scenes[{scene_id}].chapter_hint"
        ),
        "chapter_title": _text(
            scene.get("chapter_title"), f"scenes[{scene_id}].chapter_title"
        ),
        "scene_order": _integer(
            scene.get("scene_order"), f"scenes[{scene_id}].scene_order"
        ),
        "scene_count": _integer(
            scene.get("scene_count"), f"scenes[{scene_id}].scene_count"
        ),
        "source": {**source, "scene_id": scene_id},
        "logline": _text(scene.get("summary"), f"scenes[{scene_id}].summary"),
        "setting": {
            "location_ref": location_ref,
            "time": _text(scene.get("time"), f"scenes[{scene_id}].time"),
            "tone": f"{mood_in}→{mood_out}",
        },
        "cast": cast,
        "mood_arc": f"{mood_in}→{mood_out}",
        "key_frame": turn,
        "scene_prompt": "；".join(
            [
                location_anchor["look"],
                _text(scene.get("time"), f"scenes[{scene_id}].time"),
                _text(scene.get("visual_hint"), f"scenes[{scene_id}].visual_hint"),
                character_looks,
                f"氛围：{mood_in}→{mood_out}",
                f"关键动作：{turn}",
            ]
        ),
        "shots": shots,
        "dialogue_sheet": [
            {"speaker": row["speaker"], "info": row["info"], "tone": row["tone"]}
            for row in dialogue_rows
        ],
        "dont_show": dont_show,
        "director_notes": {
            "pov": character_anchors[pov]["name"] if pov else None,
            "goal": _text(scene.get("goal"), f"scenes[{scene_id}].goal"),
            "resistance": _text(
                scene.get("resistance"), f"scenes[{scene_id}].resistance"
            ),
            "turn": turn,
            "guidance": guidance,
        },
        "frame_refs": [],
    }


def validate_c8_prototype(value: Mapping[str, Any]) -> None:
    """Validate the exporter-owned prototype surface, not a formal C8 contract."""

    output = _mapping(value, "output")
    if output.get("contract") != PROTOTYPE_CONTRACT:
        _fail("INVALID_OUTPUT_CONTRACT")
    if output.get("version") != PROTOTYPE_VERSION:
        _fail("INVALID_OUTPUT_VERSION")
    export_id = _text(output.get("export_id"), "output.export_id")
    if not export_id.startswith("EXP-") or len(export_id) != 20:
        _fail("INVALID_EXPORT_ID")
    anchor_root = _mapping(output.get("anchors"), "output.anchors")
    known_anchors = {
        anchor["anchor_id"]
        for group in ("characters", "locations")
        for anchor in _list(anchor_root.get(group), f"output.anchors.{group}")
    }
    cards = _list(output.get("cards"), "output.cards")
    if not cards:
        _fail("INVALID_OUTPUT_CARDS")
    for card_index, raw_card in enumerate(cards):
        card = _mapping(raw_card, f"output.cards[{card_index}]")
        for cast_index, raw_cast in enumerate(
            _list(card.get("cast"), f"output.cards[{card_index}].cast")
        ):
            cast = _mapping(raw_cast, f"output.cards[{card_index}].cast[{cast_index}]")
            if cast.get("anchor_ref") not in known_anchors:
                _fail("OUTPUT_ANCHOR_REF_MISSING", str(cast.get("anchor_ref")))
        for dialogue_index, raw_dialogue in enumerate(
            _list(
                card.get("dialogue_sheet"),
                f"output.cards[{card_index}].dialogue_sheet",
            )
        ):
            dialogue = _mapping(
                raw_dialogue,
                f"output.cards[{card_index}].dialogue_sheet[{dialogue_index}]",
            )
            _only_fields(
                dialogue,
                {"speaker", "info", "tone"},
                f"output.cards[{card_index}].dialogue_sheet[{dialogue_index}]",
            )
            for field in ("speaker", "info", "tone"):
                _text(dialogue.get(field), f"dialogue_sheet[{dialogue_index}].{field}")


def export_scene_cards(c7_fixture: Mapping[str, Any]) -> dict[str, Any]:
    """Export one normalized C7 scene slice as deterministic C8 prototype JSON."""

    source = _mapping(c7_fixture, "c7_fixture")
    required = {
        "contract",
        "scene_export_slice",
        "project",
        "generated_at",
        "model",
        "book_title",
        "plan_id",
        "basis_note",
        "anchors",
        "scenes",
        "planned_events",
    }
    _only_fields(source, required, "c7_fixture")
    missing = sorted(required - set(source))
    if missing:
        _fail("MISSING_SOURCE_FIELDS", str(missing))
    if source.get("contract") != SOURCE_CONTRACT:
        _fail("INVALID_SOURCE_CONTRACT")
    if source.get("scene_export_slice") != SOURCE_SLICE:
        _fail("INVALID_SOURCE_SLICE")

    anchors = [
        _normalize_anchor(item, index)
        for index, item in enumerate(_list(source.get("anchors"), "anchors"))
    ]
    anchor_by_id, character_anchors = _anchor_indexes(anchors)
    events = [
        _normalize_event(item, index)
        for index, item in enumerate(
            _list(source.get("planned_events"), "planned_events")
        )
    ]
    event_by_id: dict[str, dict[str, Any]] = {}
    for event in events:
        if event["id"] in event_by_id:
            _fail("DUPLICATE_PLANNED_EVENT", event["id"])
        event_by_id[event["id"]] = event

    source_note = {
        "plan_id": _text(source.get("plan_id"), "plan_id"),
        "basis_note": _text(source.get("basis_note"), "basis_note"),
    }
    cards = [
        _export_scene(
            scene,
            anchor_by_id=anchor_by_id,
            character_anchors=character_anchors,
            event_by_id=event_by_id,
            source=source_note,
        )
        for scene in _list(source.get("scenes"), "scenes")
    ]
    if not cards:
        _fail("MISSING_SCENES")
    cards.sort(key=lambda card: (card["chapter_hint"], card["scene_order"], card["card_id"]))
    source_sha = _canonical_sha(source)
    output = {
        "contract": PROTOTYPE_CONTRACT,
        "version": PROTOTYPE_VERSION,
        "export_id": f"EXP-{source_sha[:16]}",
        "exported_at": _text(source.get("generated_at"), "generated_at"),
        "book_title": _text(source.get("book_title"), "book_title"),
        "range": {
            "chapters": sorted({card["chapter_hint"] for card in cards}),
            "scene_ids": [card["source"]["scene_id"] for card in cards],
        },
        "source_note": [source_note],
        "source_sha256": source_sha,
        "ai_label": {
            "contains_ai_generated_content": source.get("model") != "stub",
            "note": "M10 零模型确定性投影；内容身份继承 C7 来源",
        },
        "anchors": {
            "characters": sorted(
                (copy.deepcopy(item) for item in anchors if item["kind"] == "character"),
                key=lambda item: item["anchor_id"],
            ),
            "locations": sorted(
                (copy.deepcopy(item) for item in anchors if item["kind"] == "location"),
                key=lambda item: item["anchor_id"],
            ),
        },
        "cards": cards,
    }
    validate_c8_prototype(output)
    return output


def dumps_scene_cards(c7_fixture: Mapping[str, Any]) -> str:
    """Return stable UTF-8 JSON text for file or clipboard export."""

    return _canonical_json(export_scene_cards(c7_fixture)) + "\n"


def render_scene_card(c8_prototype: Mapping[str, Any], card_index: int = 0) -> str:
    """Render one exported card as a short, self-contained author-facing block."""

    validate_c8_prototype(c8_prototype)
    cards = _list(c8_prototype.get("cards"), "output.cards")
    if not 0 <= card_index < len(cards):
        _fail("CARD_INDEX_OUT_OF_RANGE", str(card_index))
    card = _mapping(cards[card_index], f"output.cards[{card_index}]")
    anchor_root = _mapping(c8_prototype.get("anchors"), "output.anchors")
    anchors = {
        anchor["anchor_id"]: anchor
        for group in ("characters", "locations")
        for anchor in _list(anchor_root.get(group), f"output.anchors.{group}")
    }
    setting = _mapping(card.get("setting"), "card.setting")
    location = anchors[setting["location_ref"]]
    lines = [
        (
            f"【{c8_prototype['book_title']} · 第{card['chapter_hint']}章"
            f"「{card['chapter_title']}」 · 场{card['scene_order']}/{card['scene_count']}】"
        ),
        f"一句话：{card['logline']}",
        f"情绪：{card['mood_arc']}",
        f"场景：{location['name']}——{location['look']}；{setting['time']}",
        "人物：",
    ]
    for cast in _list(card.get("cast"), "card.cast"):
        anchor = anchors[cast["anchor_ref"]]
        lines.append(f"- {anchor['name']}：{anchor['look']}｜本场：{cast['presence']}")
    lines.extend(["整场提示词：", str(card["scene_prompt"]), "台词信息点："])
    dialogue_sheet = _list(card.get("dialogue_sheet"), "card.dialogue_sheet")
    lines.extend(
        f"- {row['speaker']}→{row['info']}（{row['tone']}）"
        for row in dialogue_sheet
    )
    lines.append("别拍出来：")
    lines.extend(f"- {item}" for item in _list(card.get("dont_show"), "card.dont_show"))
    return "\n".join(lines) + "\n"
