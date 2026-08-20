"""当前 plan → 章事实稿短命供料候选的只读工作区适配器。

本模块只整理已经进入当前规划账、且有正式选择记录证明已消化的计划事件，
以及章槽快照中原本存在的写法字段。输出不是 C11、不是事实，也没有任何
工作区或账本写入口。
"""

from __future__ import annotations

import copy
import re
from typing import Any, NoReturn

from . import chapter_slot_snapshot_tool, chapter_slot_workspace, plan_workspace
from .workspace import AuthorWorkspace


IDENTITY = "SUPPLY_CANDIDATE"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
RESULT_FIELDS = {
    "identity",
    "not_c11",
    "not_fact",
    "author_handover",
    "writes",
    "source_plan_version",
    "source_plan_sha256",
    "generation_watermark",
    "slot_ref",
    "slot_rev",
    "outline_checkpoint",
    "future_event_materials",
    "writing_note_sources",
    "longline_context",
}
GENERATION_WATERMARK_FIELDS = {
    "source_plan_version",
    "source_plan_sha256",
    "slot_rev",
    "outline_source_commit_seq",
}
OUTLINE_CHECKPOINT_FIELDS = {
    "outline_rev",
    "source_slot_ref",
    "source_commit_seq",
}
EVENT_REQUIRED_FIELDS = {"id", "rev", "scene_ref", "text"}
CHAPTER_REQUIRED_NOTE_FIELDS = {"slot_ref", "slot_rev", "goal", "summary"}
SCENE_REQUIRED_NOTE_FIELDS = {"id", "rev", "goal", "summary"}
STORYLINE_FIELDS = {
    "id",
    "rev",
    "name",
    "alias",
    "priority",
    "members",
    "line_status",
}
PLAN_ENTRY_KEYS = frozenset({"version", "sha256", "plan"})
EVENT_OPTIONAL_FIELDS = (
    "storyline_ref",
    "purpose",
    "story_time_hint",
    "origin_ref",
    "repair_ref",
    "deviation_note",
    "defer_count",
)
SCENE_OPTIONAL_NOTE_FIELDS = (
    "location",
    "characters",
    "pov",
    "mood_in",
    "mood_out",
    "visual_hint",
    "dialogue_hints",
    "resistance",
    "turn",
    "spoiler_notes",
    "word_estimate",
)
CHAPTER_OPTIONAL_NOTE_FIELDS = (
    "entry_state",
    "exit_condition",
    "exit_hook",
    "must_not",
    "risks",
)


class ChapterFactSupplyWorkspaceError(RuntimeError):
    """当前规划不足以安全形成只读章事实稿供料候选。"""


def _fail(code: str, detail: str = "") -> NoReturn:
    raise ChapterFactSupplyWorkspaceError(
        f"{code}:{detail}" if detail else code
    )


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _plan_entry(value: Any, phase: str) -> dict[str, Any]:
    if value is None:
        _fail("PLAN_SNAPSHOT_NOT_FOUND", phase)
    if not isinstance(value, dict) or set(value) != PLAN_ENTRY_KEYS:
        _fail("PLAN_SNAPSHOT_IDENTITY_INVALID", phase)
    version = value.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        _fail("PLAN_SNAPSHOT_VERSION_INVALID", phase)
    sha256 = value.get("sha256")
    if not isinstance(sha256, str) or SHA256_RE.fullmatch(sha256) is None:
        _fail("PLAN_SNAPSHOT_SHA_INVALID", phase)
    if not isinstance(value.get("plan"), dict):
        _fail("PLAN_SNAPSHOT_OBJECT_REQUIRED", phase)
    return value


def _identity(value: dict[str, Any]) -> tuple[int, str]:
    return value["version"], value["sha256"]


def _index_unique(rows: Any, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        _fail("PLAN_COLLECTION_INVALID", label)
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail("PLAN_OBJECT_INVALID", f"{label}[{index}]")
        object_id = row.get("id")
        if not isinstance(object_id, str) or not object_id:
            _fail("PLAN_OBJECT_ID_INVALID", f"{label}[{index}]")
        if object_id in result:
            _fail("PLAN_OBJECT_ID_DUPLICATE", f"{label}:{object_id}")
        result[object_id] = row
    return result


def _nonempty_strings(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        _fail("REFERENCE_LIST_INVALID", field)
    if len(value) != len(set(value)):
        _fail("REFERENCE_LIST_DUPLICATE", field)
    return value


def _selection_proves_landed_event(
    event: dict[str, Any],
    option_records: dict[str, dict[str, Any]],
    slot_ref: str,
) -> bool:
    event_ref = event["id"]
    digest_status = event.get("digest_status")
    if digest_status in {"pending", "voided"}:
        return False
    if digest_status != "digested":
        _fail("EVENT_DIGEST_STATUS_INVALID", event_ref)

    digest_ref = event.get("digest_ref")
    if not isinstance(digest_ref, str) or not digest_ref:
        _fail("DIGESTED_EVENT_RECORD_REF_INVALID", event_ref)
    record = option_records.get(digest_ref)
    if record is None:
        _fail("DIGESTED_EVENT_RECORD_NOT_FOUND", event_ref)
    if record.get("slot_ref") != slot_ref:
        _fail("DIGESTED_EVENT_RECORD_SLOT_MISMATCH", event_ref)
    if record.get("group_status") != "active":
        _fail("DIGESTED_EVENT_RECORD_NOT_ACTIVE", event_ref)
    if record.get("decided_by") not in {"author", "auto"}:
        _fail("DIGESTED_EVENT_ACTOR_INVALID", event_ref)

    chosen_key = record.get("chosen_key")
    recommended_key = record.get("recommended_key")
    if not isinstance(chosen_key, str) or not chosen_key:
        _fail("DIGESTED_EVENT_CHOICE_MISSING", event_ref)
    if not isinstance(recommended_key, str) or not recommended_key:
        _fail("DIGESTED_EVENT_RECOMMENDATION_INVALID", event_ref)
    options = record.get("options")
    if not isinstance(options, list) or not options:
        _fail("DIGESTED_EVENT_OPTIONS_INVALID", event_ref)
    option_keys = []
    for index, option in enumerate(options):
        if not isinstance(option, dict):
            _fail("DIGESTED_EVENT_OPTION_INVALID", f"{event_ref}:{index}")
        key = option.get("key")
        if not isinstance(key, str) or not key:
            _fail("DIGESTED_EVENT_OPTION_KEY_INVALID", f"{event_ref}:{index}")
        option_keys.append(key)
    if len(option_keys) != len(set(option_keys)):
        _fail("DIGESTED_EVENT_OPTION_KEY_DUPLICATE", event_ref)
    if chosen_key not in option_keys or recommended_key not in option_keys:
        _fail("DIGESTED_EVENT_OPTION_REF_NOT_FOUND", event_ref)

    digest_applied = _nonempty_strings(
        record.get("digest_applied"), f"option_record[{digest_ref}].digest_applied"
    )
    if event_ref not in digest_applied:
        _fail("DIGESTED_EVENT_NOT_IN_RECORD", event_ref)
    return True


def _has_material(value: Any) -> bool:
    return value not in {None, ""} if not isinstance(value, list) else bool(value)


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail("SUPPLY_RESULT_INTEGER_INVALID", field)
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("SUPPLY_RESULT_INTEGER_INVALID", field)
    return value


def _string(value: Any, field: str, *, nonempty: bool = False) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        _fail("SUPPLY_RESULT_STRING_INVALID", field)
    return value


def _string_list(value: Any, field: str, *, unique: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _fail("SUPPLY_RESULT_STRING_LIST_INVALID", field)
    if unique and (
        any(not item for item in value) or len(value) != len(set(value))
    ):
        _fail("SUPPLY_RESULT_STRING_LIST_INVALID", field)
    return list(value)


def _present_string(value: Any, field: str) -> str:
    text = _string(value, field, nonempty=True)
    if not _has_material(text):
        _fail("SUPPLY_RESULT_EMPTY_OPTIONAL_FIELD", field)
    return text


def _validate_generation_watermark(
    value: Any,
    *,
    source_plan_version: int,
    source_plan_sha256: str,
    slot_rev: int,
    outline_source_commit_seq: int,
) -> dict[str, Any]:
    expected = {
        "source_plan_version": source_plan_version,
        "source_plan_sha256": source_plan_sha256,
        "slot_rev": slot_rev,
        "outline_source_commit_seq": outline_source_commit_seq,
    }
    if not isinstance(value, dict) or set(value) != GENERATION_WATERMARK_FIELDS:
        _fail("SUPPLY_RESULT_GENERATION_WATERMARK_INVALID")
    if value != expected:
        _fail("SUPPLY_RESULT_GENERATION_WATERMARK_MISMATCH")
    return copy.deepcopy(value)


def _validate_outline_checkpoint(value: Any, slot_ref: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != OUTLINE_CHECKPOINT_FIELDS:
        _fail("SUPPLY_RESULT_OUTLINE_CHECKPOINT_INVALID")
    _positive_int(value.get("outline_rev"), "outline_checkpoint.outline_rev")
    if value.get("source_slot_ref") != slot_ref:
        _fail("SUPPLY_RESULT_OUTLINE_SLOT_MISMATCH")
    _nonnegative_int(
        value.get("source_commit_seq"),
        "outline_checkpoint.source_commit_seq",
    )
    return copy.deepcopy(value)


def _validate_future_events(
    value: Any,
    *,
    scene_ids: set[str],
    storyline_ids: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _fail("SUPPLY_RESULT_FUTURE_EVENTS_INVALID")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    allowed = EVENT_REQUIRED_FIELDS | set(EVENT_OPTIONAL_FIELDS)
    for index, row in enumerate(value):
        if (
            not isinstance(row, dict)
            or not EVENT_REQUIRED_FIELDS.issubset(row)
            or not set(row).issubset(allowed)
        ):
            _fail("SUPPLY_RESULT_FUTURE_EVENT_INVALID", str(index))
        event_id = _string(row.get("id"), f"future_event[{index}].id", nonempty=True)
        if event_id in seen:
            _fail("SUPPLY_RESULT_FUTURE_EVENT_DUPLICATE", event_id)
        seen.add(event_id)
        _positive_int(row.get("rev"), f"future_event[{event_id}].rev")
        scene_ref = _string(
            row.get("scene_ref"),
            f"future_event[{event_id}].scene_ref",
            nonempty=True,
        )
        if scene_ref not in scene_ids:
            _fail("SUPPLY_RESULT_EVENT_SCENE_NOT_FOUND", event_id)
        _string(row.get("text"), f"future_event[{event_id}].text")
        for field in {
            "storyline_ref",
            "story_time_hint",
            "origin_ref",
            "repair_ref",
            "deviation_note",
        } & set(row):
            _present_string(row[field], f"future_event[{event_id}].{field}")
        if "storyline_ref" in row and row["storyline_ref"] not in storyline_ids:
            _fail("SUPPLY_RESULT_EVENT_STORYLINE_NOT_FOUND", event_id)
        if "purpose" in row and row["purpose"] not in {
            "setup",
            "advance",
            "reveal",
            "payoff",
            "repair",
        }:
            _fail("SUPPLY_RESULT_EVENT_PURPOSE_INVALID", event_id)
        if "defer_count" in row:
            _nonnegative_int(
                row["defer_count"], f"future_event[{event_id}].defer_count"
            )
        result.append(copy.deepcopy(row))
    return result


def _validate_chapter_note(value: Any, slot_ref: str, slot_rev: int) -> dict[str, Any]:
    allowed = CHAPTER_REQUIRED_NOTE_FIELDS | set(CHAPTER_OPTIONAL_NOTE_FIELDS)
    if (
        not isinstance(value, dict)
        or not CHAPTER_REQUIRED_NOTE_FIELDS.issubset(value)
        or not set(value).issubset(allowed)
        or value.get("slot_ref") != slot_ref
        or value.get("slot_rev") != slot_rev
    ):
        _fail("SUPPLY_RESULT_CHAPTER_NOTE_INVALID")
    _string(value.get("goal"), "writing_note_sources.chapter.goal")
    _string(value.get("summary"), "writing_note_sources.chapter.summary")
    for field in {"entry_state", "exit_condition", "exit_hook"} & set(value):
        _present_string(value[field], f"writing_note_sources.chapter.{field}")
    for field in {"must_not", "risks"} & set(value):
        rows = _string_list(value[field], f"writing_note_sources.chapter.{field}")
        if not rows:
            _fail("SUPPLY_RESULT_EMPTY_OPTIONAL_FIELD", field)
    return copy.deepcopy(value)


def _validate_scene_notes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _fail("SUPPLY_RESULT_SCENE_NOTES_INVALID")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    allowed = SCENE_REQUIRED_NOTE_FIELDS | set(SCENE_OPTIONAL_NOTE_FIELDS)
    for index, row in enumerate(value):
        if (
            not isinstance(row, dict)
            or not SCENE_REQUIRED_NOTE_FIELDS.issubset(row)
            or not set(row).issubset(allowed)
        ):
            _fail("SUPPLY_RESULT_SCENE_NOTE_INVALID", str(index))
        scene_id = _string(row.get("id"), f"scene_note[{index}].id", nonempty=True)
        if scene_id in seen:
            _fail("SUPPLY_RESULT_SCENE_NOTE_DUPLICATE", scene_id)
        seen.add(scene_id)
        _positive_int(row.get("rev"), f"scene_note[{scene_id}].rev")
        _string(row.get("goal"), f"scene_note[{scene_id}].goal")
        _string(row.get("summary"), f"scene_note[{scene_id}].summary")
        for field in {
            "location",
            "pov",
            "mood_in",
            "mood_out",
            "visual_hint",
            "resistance",
            "turn",
        } & set(row):
            _present_string(row[field], f"scene_note[{scene_id}].{field}")
        for field in {"characters", "dialogue_hints", "spoiler_notes"} & set(row):
            rows = _string_list(
                row[field],
                f"scene_note[{scene_id}].{field}",
                unique=field == "characters",
            )
            if not rows:
                _fail("SUPPLY_RESULT_EMPTY_OPTIONAL_FIELD", field)
        if "word_estimate" in row:
            _nonnegative_int(
                row["word_estimate"], f"scene_note[{scene_id}].word_estimate"
            )
        result.append(copy.deepcopy(row))
    return result


def _validate_storylines(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _fail("SUPPLY_RESULT_LONGLINE_CONTEXT_INVALID")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(value):
        if not isinstance(row, dict) or set(row) != STORYLINE_FIELDS:
            _fail("SUPPLY_RESULT_STORYLINE_INVALID", str(index))
        storyline_id = _string(
            row.get("id"), f"storyline[{index}].id", nonempty=True
        )
        if storyline_id in seen:
            _fail("SUPPLY_RESULT_STORYLINE_DUPLICATE", storyline_id)
        seen.add(storyline_id)
        _positive_int(row.get("rev"), f"storyline[{storyline_id}].rev")
        _string(row.get("name"), f"storyline[{storyline_id}].name")
        if row.get("alias") is not None:
            _string(row["alias"], f"storyline[{storyline_id}].alias")
        if isinstance(row.get("priority"), bool) or not isinstance(
            row.get("priority"), int
        ):
            _fail("SUPPLY_RESULT_INTEGER_INVALID", f"storyline[{storyline_id}].priority")
        _string_list(
            row.get("members"),
            f"storyline[{storyline_id}].members",
            unique=True,
        )
        if row.get("line_status") not in {
            "active",
            "paused",
            "converged",
            "merged",
        }:
            _fail("SUPPLY_RESULT_STORYLINE_STATUS_INVALID", storyline_id)
        result.append(copy.deepcopy(row))
    return result


def validate_result(value: object) -> dict[str, Any]:
    """严格校验现役短命供料结果，不重新读取规划账或补写字段。"""

    if not isinstance(value, dict) or set(value) != RESULT_FIELDS:
        _fail("SUPPLY_RESULT_FIELDS_INVALID")
    result = copy.deepcopy(value)
    if (
        result["identity"] != IDENTITY
        or result["not_c11"] is not True
        or result["not_fact"] is not True
        or result["author_handover"] is not False
        or result["writes"] != "none"
    ):
        _fail("SUPPLY_RESULT_IDENTITY_INVALID")
    source_version = _positive_int(
        result["source_plan_version"], "source_plan_version"
    )
    source_sha = result["source_plan_sha256"]
    if not isinstance(source_sha, str) or SHA256_RE.fullmatch(source_sha) is None:
        _fail("SUPPLY_RESULT_SOURCE_SHA_INVALID")
    slot_ref = _string(result["slot_ref"], "slot_ref", nonempty=True)
    slot_rev = _positive_int(result["slot_rev"], "slot_rev")
    checkpoint = _validate_outline_checkpoint(result["outline_checkpoint"], slot_ref)
    result["generation_watermark"] = _validate_generation_watermark(
        result["generation_watermark"],
        source_plan_version=source_version,
        source_plan_sha256=source_sha,
        slot_rev=slot_rev,
        outline_source_commit_seq=checkpoint["source_commit_seq"],
    )
    notes = result["writing_note_sources"]
    if not isinstance(notes, dict) or set(notes) != {"chapter", "scenes"}:
        _fail("SUPPLY_RESULT_WRITING_NOTES_INVALID")
    chapter = _validate_chapter_note(notes["chapter"], slot_ref, slot_rev)
    scenes = _validate_scene_notes(notes["scenes"])
    storylines = _validate_storylines(result["longline_context"])
    result["future_event_materials"] = _validate_future_events(
        result["future_event_materials"],
        scene_ids={scene["id"] for scene in scenes},
        storyline_ids={storyline["id"] for storyline in storylines},
    )
    result["writing_note_sources"] = {"chapter": chapter, "scenes": scenes}
    result["longline_context"] = storylines
    return result


def _copy_existing_fields(
    source: dict[str, Any], fields: tuple[str, ...]
) -> dict[str, Any]:
    return {
        field: copy.deepcopy(source[field])
        for field in fields
        if field in source and _has_material(source[field])
    }


def _future_event_materials(
    snapshot: dict[str, Any], plan: dict[str, Any]
) -> list[dict[str, Any]]:
    plan_events = _index_unique(plan.get("events"), "events")
    option_records = _index_unique(plan.get("option_records"), "option_records")
    result: list[dict[str, Any]] = []
    for event_slice in snapshot["events"]:
        event_ref = event_slice["id"]
        plan_event = plan_events.get(event_ref)
        if plan_event is None:
            _fail("SNAPSHOT_EVENT_NOT_IN_CURRENT_PLAN", event_ref)
        if any(plan_event.get(key) != value for key, value in event_slice.items()):
            _fail("SNAPSHOT_EVENT_IDENTITY_DRIFT", event_ref)
        if not _selection_proves_landed_event(
            plan_event, option_records, snapshot["slot_ref"]
        ):
            continue
        material = {
            "id": event_slice["id"],
            "rev": event_slice["rev"],
            "scene_ref": event_slice["scene_ref"],
            "text": event_slice["text"],
        }
        material.update(_copy_existing_fields(event_slice, EVENT_OPTIONAL_FIELDS))
        result.append(material)
    return result


def _writing_note_sources(snapshot: dict[str, Any]) -> dict[str, Any]:
    chapter = {
        "slot_ref": snapshot["slot_ref"],
        "slot_rev": snapshot["slot_rev"],
        "goal": snapshot["goal"],
        "summary": snapshot["summary"],
    }
    chapter.update(_copy_existing_fields(snapshot, CHAPTER_OPTIONAL_NOTE_FIELDS))

    scenes: list[dict[str, Any]] = []
    for scene in snapshot["scenes"]:
        note = {
            "id": scene["id"],
            "rev": scene["rev"],
            "goal": scene["goal"],
            "summary": scene["summary"],
        }
        note.update(_copy_existing_fields(scene, SCENE_OPTIONAL_NOTE_FIELDS))
        scenes.append(note)
    return {"chapter": chapter, "scenes": scenes}


def execute(workspace: AuthorWorkspace, slot_ref: str) -> dict[str, Any]:
    """读取稳定 current plan，返回短命规划供料候选；全程零写。"""
    handle = _require_workspace(workspace)
    before = _plan_entry(plan_workspace.read_plan(handle), "before")
    try:
        snapshot = chapter_slot_workspace.execute(handle, slot_ref)
    except (
        chapter_slot_workspace.ChapterSlotWorkspaceError,
        chapter_slot_snapshot_tool.ChapterSlotSnapshotError,
    ) as exc:
        _fail("CHAPTER_SLOT_SNAPSHOT_REJECTED", str(exc))
    after = _plan_entry(plan_workspace.read_plan(handle), "after")

    source_identity = (
        snapshot.get("source_plan_version"),
        snapshot.get("source_plan_sha256"),
    )
    if _identity(before) != source_identity or _identity(after) != source_identity:
        _fail("PLAN_SOURCE_CHANGED_DURING_RESOLUTION")
    checkpoint = snapshot.get("outline_checkpoint")
    if checkpoint is None:
        _fail("OUTLINE_CHECKPOINT_REQUIRED_FOR_SUPPLY")

    result = {
        "identity": IDENTITY,
        "not_c11": True,
        "not_fact": True,
        "author_handover": False,
        "writes": "none",
        "source_plan_version": snapshot["source_plan_version"],
        "source_plan_sha256": snapshot["source_plan_sha256"],
        "generation_watermark": copy.deepcopy(snapshot["generation_watermark"]),
        "slot_ref": snapshot["slot_ref"],
        "slot_rev": snapshot["slot_rev"],
        "outline_checkpoint": copy.deepcopy(checkpoint),
        "future_event_materials": _future_event_materials(
            snapshot, before["plan"]
        ),
        "writing_note_sources": _writing_note_sources(snapshot),
        "longline_context": copy.deepcopy(snapshot["storylines"]),
    }
    return validate_result(result)


__all__ = [
    "ChapterFactSupplyWorkspaceError",
    "execute",
    "validate_result",
]
