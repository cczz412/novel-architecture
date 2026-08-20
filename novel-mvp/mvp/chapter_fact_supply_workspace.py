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

    return {
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

