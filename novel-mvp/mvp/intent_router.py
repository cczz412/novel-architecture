"""M8 zero-model router for placing an author's future-story intent.

The result is advice only.  It never writes planstore, character cards, volume
outlines, relationship arcs, or hook storage.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, NoReturn


HOMES = (
    "chapter_plan",
    "volume_outline",
    "character_arc",
    "relationship_arc",
    "open_hook",
)

CHAPTER_CUES = (
    "下一章",
    "下章",
    "下一回",
    "下一场",
    "这场",
    "具体场景",
    "本章这一场",
)
VOLUME_CUES = ("本卷末", "本卷内", "这一卷", "本卷目标", "卷末", "本卷")
FUTURE_CUES = ("未来", "以后", "将来", "最后", "最终", "结局", "迟早")
RELATIONSHIP_CUES = (
    "相遇",
    "重逢",
    "再见面",
    "关系",
    "结盟",
    "联手",
    "反目",
    "决裂",
    "和好",
    "成婚",
    "成亲",
    "相爱",
    "爱上",
    "成为朋友",
    "成为敌人",
)
PAIR_CUES = ("两人", "二人", "她们", "他们", "双方", "彼此")
CHARACTER_FATE_CUES = (
    "会死",
    "死亡",
    "牺牲",
    "命运",
    "结局",
    "最终成为",
    "最后成为",
    "最后一定",
)
IDEA_CUES = (
    "灵感",
    "先记",
    "记个",
    "有个念头",
    "也许",
    "或许",
    "可能",
    "暂时没想好",
    "以后再说",
    "先放着",
)
UNSCHEDULED_CUES = (
    "时间未定",
    "时候未定",
    "哪一卷还没定",
    "哪章还没定",
    "不知道什么时候",
    "具体时间以后再定",
    "先不定具体章节",
)
HARD_COMMITMENT_CUES = ("一定", "必须", "确定", "肯定", "注定")
ACTION_COMMITMENT_CUES = ("要让", "让", "安排", "要在", "要把", "要攒", "要去")


class IntentRoutingError(ValueError):
    """The intent or context cannot be routed safely."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _fail(code: str, detail: str = "") -> NoReturn:
    raise IntentRoutingError(code, detail)


def _contains(text: str, cues: tuple[str, ...]) -> bool:
    return any(cue in text for cue in cues)


def _known_entities(values: Iterable[str]) -> list[str]:
    entities = []
    seen = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            _fail("INVALID_KNOWN_ENTITY")
        entity = value.strip()
        if entity not in seen:
            seen.add(entity)
            entities.append(entity)
    return entities


def _mentioned_entities(intent: str, known_entities: list[str]) -> list[str]:
    return [
        entity
        for entity in sorted(known_entities, key=lambda item: (-len(item), item))
        if entity in intent
    ]


def _commitment(intent: str, *, explicit_time: bool) -> str:
    if _contains(intent, HARD_COMMITMENT_CUES):
        return "committed"
    if _contains(intent, IDEA_CUES):
        return "idea"
    if explicit_time and _contains(intent, ACTION_COMMITMENT_CUES):
        return "committed"
    return "provisional"


def _entity_scope(primary_home: str, entities: list[str]) -> dict[str, Any]:
    kind = {
        "chapter_plan": "chapter",
        "volume_outline": "volume",
        "character_arc": "character",
        "relationship_arc": "relationship",
        "open_hook": "open",
    }[primary_home]
    return {"kind": kind, "entities": entities}


def route_author_intent(
    intent: str,
    *,
    known_entities: Iterable[str] = (),
) -> dict[str, Any]:
    """Return one primary placement recommendation without mutating any store."""

    if not isinstance(intent, str) or not intent.strip():
        _fail("EMPTY_AUTHOR_INTENT")
    text = " ".join(intent.split())
    entities = _mentioned_entities(text, _known_entities(known_entities))

    has_chapter = _contains(text, CHAPTER_CUES)
    has_volume = _contains(text, VOLUME_CUES)
    has_future = _contains(text, FUTURE_CUES)
    has_relationship = _contains(text, RELATIONSHIP_CUES)
    has_pair = len(entities) >= 2 or _contains(text, PAIR_CUES)
    has_character_fate = _contains(text, CHARACTER_FATE_CUES)
    has_idea = _contains(text, IDEA_CUES)
    unscheduled = _contains(text, UNSCHEDULED_CUES)

    link_targets: list[str] = []
    clarification_question: str | None = None

    if has_chapter:
        primary_home = "chapter_plan"
        time_horizon = "next_chapter_or_scene"
        confidence = 0.98
        if has_relationship and has_pair:
            link_targets.append("relationship_arc")
        elif has_character_fate and entities:
            link_targets.append("character_arc")
        if has_volume:
            link_targets.append("volume_outline")
        candidate_homes = [primary_home]
    elif has_relationship and (has_pair or entities):
        primary_home = "relationship_arc"
        time_horizon = "current_volume" if has_volume else "future_unscheduled"
        confidence = 0.95 if has_pair else 0.62
        if has_volume:
            link_targets.append("volume_outline")
        candidate_homes = [primary_home]
        if not has_pair:
            candidate_homes.append("open_hook")
            clarification_question = "这条关系变化涉及哪两个人？"
    elif has_volume:
        primary_home = "volume_outline"
        time_horizon = "current_volume"
        confidence = 0.96
        if has_character_fate and entities:
            link_targets.append("character_arc")
        candidate_homes = [primary_home]
    elif has_character_fate and (entities or has_future):
        primary_home = "character_arc"
        time_horizon = "long_term_unscheduled" if unscheduled or not has_volume else "current_volume"
        confidence = 0.93 if entities else 0.68
        candidate_homes = [primary_home]
        if not entities:
            candidate_homes.append("open_hook")
            clarification_question = "这条长期命运属于哪个人物？"
    elif has_idea and not has_chapter and not has_volume:
        primary_home = "open_hook"
        time_horizon = "unanchored"
        confidence = 0.9
        candidate_homes = [primary_home]
    elif has_future and len(entities) == 1:
        primary_home = "character_arc"
        time_horizon = "future_unscheduled"
        confidence = 0.48
        candidate_homes = ["character_arc", "open_hook"]
        clarification_question = "这是人物长期走向，还是先作为未承诺灵感保存？"
    else:
        primary_home = "open_hook"
        time_horizon = "unanchored"
        confidence = 0.42
        candidate_homes = ["open_hook", "chapter_plan"]
        clarification_question = "这条想法有明确章节位置，还是先作为灵感保存？"

    commitment = _commitment(
        text,
        explicit_time=has_chapter or has_volume or unscheduled,
    )
    if primary_home == "open_hook" and time_horizon == "unanchored" and commitment == "provisional":
        commitment = "idea"

    unique_links = [
        home
        for index, home in enumerate(link_targets)
        if home != primary_home and home not in link_targets[:index]
    ]
    if len(candidate_homes) > 2:
        _fail("TOO_MANY_CANDIDATE_HOMES")
    if clarification_question and clarification_question.count("？") > 1:
        _fail("TOO_MANY_CLARIFICATION_QUESTIONS")

    return {
        "primary_home": primary_home,
        "link_targets": unique_links,
        "commitment": commitment,
        "time_horizon": time_horizon,
        "entity_scope": _entity_scope(primary_home, entities),
        "confidence": confidence,
        "clarification_question": clarification_question,
        "candidate_homes": candidate_homes,
        "advice_only": True,
        "writes": [],
    }
