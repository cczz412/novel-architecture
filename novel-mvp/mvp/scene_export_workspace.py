"""AuthorWorkspace 当前 plan → M10 C8 原型与逐场新鲜度的只读入口。"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, NoReturn

from . import (
    chapter_slot_workspace,
    m10_scene_slice_adapter,
    scene_export,
    scene_export_tool,
)
from .workspace import AUTHOR_ID_RE, PROJECT_ID_RE, AuthorWorkspace


BINDING_VERSION = "m10-scene-workspace-binding-v1"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
WORKSPACE_BINDING_KEYS = {
    "binding_version",
    "author_id",
    "project_id",
    "slot_ref",
    "source_plan_version",
    "source_plan_sha256",
    "scene_ids",
    "scenes",
}
SCENE_DEPENDENCY_KEYS = {
    "scene_id",
    "card_id",
    "slot_ref",
    "scene_rev",
    "scene_sha256",
    "scene_order",
    "scene_count",
    "scene_binding_sha256",
    "event_refs",
    "events",
    "anchors",
}
EVENT_DEPENDENCY_KEYS = {
    "event_id",
    "event_rev",
    "event_sha256",
    "binding_sha256",
}
ANCHOR_DEPENDENCY_KEYS = {
    "anchor_id",
    "entity_ref",
    "kind",
    "revision",
    "anchor_sha256",
}


class SceneExportWorkspaceError(RuntimeError):
    """工作区句柄、保存结果或逐场依赖身份不合法。"""


def _fail(code: str, detail: str = "") -> NoReturn:
    raise SceneExportWorkspaceError(f"{code}:{detail}" if detail else code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _canonical_sha(value: Any) -> str:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SceneExportWorkspaceError("DEPENDENCY_NOT_JSON_SERIALIZABLE") from exc
    return hashlib.sha256(payload).hexdigest()


def _clean_text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        _fail(code)
    return value


def _positive_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail(code)
    return value


def _clean_text_list(value: object, code: str) -> list[str]:
    if (
        not isinstance(value, list)
        or any(
            not isinstance(item, str)
            or not item
            or item != item.strip()
            for item in value
        )
    ):
        _fail(code)
    return list(value)


def _index_rows(rows: object, ref_key: str, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        _fail(f"{label}_ARRAY_REQUIRED")
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail(f"{label}_ITEM_INVALID", str(index))
        ref = _clean_text(row.get(ref_key), f"{label}_REF_INVALID")
        if ref in result:
            _fail(f"{label}_DUPLICATE", ref)
        result[ref] = row
    return result


def _anchor_indexes(
    anchors: object,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id = _index_rows(anchors, "anchor_id", "ANCHOR")
    by_character: dict[str, dict[str, Any]] = {}
    seen_entities: set[str] = set()
    for anchor_id, anchor in by_id.items():
        entity_ref = _clean_text(anchor.get("entity_ref"), "ANCHOR_ENTITY_INVALID")
        kind = anchor.get("kind")
        if kind not in {"character", "location"}:
            _fail("ANCHOR_KIND_INVALID", anchor_id)
        if entity_ref in seen_entities:
            _fail("ANCHOR_ENTITY_DUPLICATE", entity_ref)
        seen_entities.add(entity_ref)
        if kind == "character":
            by_character[entity_ref] = anchor
    return by_id, by_character


def _scene_dependencies(
    snapshot: dict[str, Any],
    anchors: object,
    scene_bindings: object,
    event_bindings: object,
    scene_ids: list[str],
) -> list[dict[str, Any]]:
    anchor_by_id, character_by_entity = _anchor_indexes(anchors)
    scene_binding_by_ref = _index_rows(
        scene_bindings, "scene_ref", "SCENE_BINDING"
    )
    event_binding_by_ref = _index_rows(
        event_bindings, "event_ref", "EVENT_BINDING"
    )
    scene_by_id = _index_rows(snapshot.get("scenes"), "id", "SNAPSHOT_SCENE")
    event_by_id = _index_rows(snapshot.get("events"), "id", "SNAPSHOT_EVENT")
    current_scene_refs = snapshot.get("scene_refs")
    if not isinstance(current_scene_refs, list) or len(current_scene_refs) != len(
        set(current_scene_refs)
    ):
        _fail("SNAPSHOT_SCENE_REFS_INVALID")

    dependencies: list[dict[str, Any]] = []
    seen_dialogue_ids: set[str] = set()
    for scene_id in scene_ids:
        scene = scene_by_id.get(scene_id)
        if scene is None:
            _fail("SNAPSHOT_SCENE_MISSING", scene_id)
        binding = scene_binding_by_ref.get(scene_id)
        if binding is None:
            _fail("SCENE_BINDING_MISSING", scene_id)
        if set(binding) != m10_scene_slice_adapter.SCENE_BINDING_KEYS:
            _fail("SCENE_BINDING_FIELDS_INVALID", scene_id)

        location_anchor_ref = binding.get("location_anchor_ref")
        location_anchor = anchor_by_id.get(str(location_anchor_ref))
        if location_anchor is None or location_anchor.get("kind") != "location":
            _fail("LOCATION_ANCHOR_MISSING", str(location_anchor_ref))
        characters = scene.get("characters")
        if (
            not isinstance(characters, list)
            or not characters
            or any(not isinstance(ref, str) or not ref for ref in characters)
            or len(characters) != len(set(characters))
        ):
            _fail("SCENE_CHARACTERS_INVALID", scene_id)
        used_anchors = [location_anchor]
        for character_ref in characters:
            anchor = character_by_entity.get(character_ref)
            if anchor is None:
                _fail("CHARACTER_ANCHOR_MISSING", character_ref)
            used_anchors.append(anchor)
        presence = binding.get("character_presence")
        if not isinstance(presence, dict) or set(presence) != set(characters):
            _fail("CHARACTER_PRESENCE_INCOMPLETE", scene_id)
        for description in presence.values():
            _clean_text(description, "CHARACTER_PRESENCE_INVALID")
        _clean_text(binding.get("time"), "SCENE_TIME_INVALID")
        _clean_text_list(
            binding.get("writing_guidance"), "WRITING_GUIDANCE_INVALID"
        )

        event_refs = scene.get("pe_refs")
        if (
            not isinstance(event_refs, list)
            or any(not isinstance(ref, str) or not ref for ref in event_refs)
            or len(event_refs) != len(set(event_refs))
        ):
            _fail("SCENE_EVENT_REFS_INVALID", scene_id)
        event_dependencies: list[dict[str, Any]] = []
        bound_dialogue_info: list[str] = []
        for event_ref in event_refs:
            event = event_by_id.get(event_ref)
            if event is None or event.get("scene_ref") != scene_id:
                _fail("SNAPSHOT_EVENT_MISSING_OR_MISMATCH", event_ref)
            event_binding = event_binding_by_ref.get(event_ref)
            if event_binding is None:
                _fail("EVENT_BINDING_MISSING", event_ref)
            if set(event_binding) != m10_scene_slice_adapter.EVENT_BINDING_KEYS:
                _fail("EVENT_BINDING_FIELDS_INVALID", event_ref)
            _clean_text(event_binding.get("visual"), "EVENT_VISUAL_INVALID")
            _clean_text(event_binding.get("shot_hint"), "EVENT_SHOT_HINT_INVALID")
            dialogue_rows = event_binding.get("dialogue_bindings")
            if not isinstance(dialogue_rows, list):
                _fail("DIALOGUE_BINDINGS_INVALID", event_ref)
            for dialogue in dialogue_rows:
                if (
                    not isinstance(dialogue, dict)
                    or set(dialogue)
                    != m10_scene_slice_adapter.DIALOGUE_BINDING_KEYS
                ):
                    _fail("DIALOGUE_BINDING_FIELDS_INVALID", event_ref)
                dialogue_id = _clean_text(
                    dialogue.get("id"), "DIALOGUE_BINDING_ID_INVALID"
                )
                if dialogue_id in seen_dialogue_ids:
                    _fail("DIALOGUE_BINDING_ID_DUPLICATE", dialogue_id)
                seen_dialogue_ids.add(dialogue_id)
                speaker_ref = _clean_text(
                    dialogue.get("speaker_ref"),
                    "DIALOGUE_BINDING_SPEAKER_INVALID",
                )
                if speaker_ref not in characters:
                    _fail("DIALOGUE_SPEAKER_NOT_IN_SCENE", dialogue_id)
                bound_dialogue_info.append(
                    _clean_text(dialogue.get("info"), "DIALOGUE_INFO_INVALID")
                )
                _clean_text(dialogue.get("tone"), "DIALOGUE_TONE_INVALID")
            event_dependencies.append(
                {
                    "event_id": event_ref,
                    "event_rev": _positive_int(
                        event.get("rev"), "EVENT_REV_INVALID"
                    ),
                    "event_sha256": _canonical_sha(event),
                    "binding_sha256": _canonical_sha(event_binding),
                }
            )
        snapshot_dialogue = _clean_text_list(
            scene.get("dialogue_hints", []), "SNAPSHOT_DIALOGUE_HINTS_INVALID"
        )
        if len(snapshot_dialogue) != len(set(snapshot_dialogue)):
            _fail("SNAPSHOT_DIALOGUE_HINT_DUPLICATE", scene_id)
        if bound_dialogue_info != snapshot_dialogue:
            _fail("DIALOGUE_BINDING_INCOMPLETE", scene_id)

        anchor_dependencies = [
            {
                "anchor_id": _clean_text(
                    anchor.get("anchor_id"), "ANCHOR_ID_INVALID"
                ),
                "entity_ref": _clean_text(
                    anchor.get("entity_ref"), "ANCHOR_ENTITY_INVALID"
                ),
                "kind": anchor["kind"],
                "revision": _positive_int(
                    anchor.get("revision"), "ANCHOR_REVISION_INVALID"
                ),
                "anchor_sha256": _canonical_sha(anchor),
            }
            for anchor in sorted(used_anchors, key=lambda item: item["anchor_id"])
        ]
        scene_order = current_scene_refs.index(scene_id) + 1
        dependencies.append(
            {
                "scene_id": scene_id,
                "card_id": f"SC-{scene_id}",
                "slot_ref": snapshot["slot_ref"],
                "scene_rev": _positive_int(
                    scene.get("rev"), "SCENE_REV_INVALID"
                ),
                "scene_sha256": _canonical_sha(scene),
                "scene_order": scene_order,
                "scene_count": len(current_scene_refs),
                "scene_binding_sha256": _canonical_sha(binding),
                "event_refs": list(event_refs),
                "events": event_dependencies,
                "anchors": anchor_dependencies,
            }
        )
    return dependencies


def _workspace_binding(
    workspace: AuthorWorkspace,
    snapshot: dict[str, Any],
    anchors: object,
    scene_bindings: object,
    event_bindings: object,
) -> dict[str, Any]:
    scene_ids = list(snapshot["scene_refs"])
    return {
        "binding_version": BINDING_VERSION,
        "author_id": workspace.author_id,
        "project_id": workspace.project_id,
        "slot_ref": snapshot["slot_ref"],
        "source_plan_version": snapshot["source_plan_version"],
        "source_plan_sha256": snapshot["source_plan_sha256"],
        "scene_ids": scene_ids,
        "scenes": _scene_dependencies(
            snapshot,
            anchors,
            scene_bindings,
            event_bindings,
            scene_ids,
        ),
    }


def _validate_dependency_sha(value: object, code: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _saved_binding(saved_result: object) -> dict[str, Any]:
    if not isinstance(saved_result, dict):
        _fail("SAVED_RESULT_INVALID")
    try:
        scene_export.validate_c8_prototype(saved_result)
    except (KeyError, TypeError, scene_export.SceneExportError) as exc:
        raise SceneExportWorkspaceError("SAVED_C8_PROTOTYPE_INVALID") from exc
    binding = saved_result.get("workspace_binding")
    if not isinstance(binding, dict) or set(binding) != WORKSPACE_BINDING_KEYS:
        _fail("SAVED_WORKSPACE_BINDING_INVALID")
    if (
        binding.get("binding_version") != BINDING_VERSION
        or not isinstance(binding.get("author_id"), str)
        or AUTHOR_ID_RE.fullmatch(binding["author_id"]) is None
        or not isinstance(binding.get("project_id"), str)
        or PROJECT_ID_RE.fullmatch(binding["project_id"]) is None
    ):
        _fail("SAVED_WORKSPACE_BINDING_INVALID")
    _clean_text(binding.get("slot_ref"), "SAVED_SLOT_REF_INVALID")
    _positive_int(binding.get("source_plan_version"), "SAVED_PLAN_VERSION_INVALID")
    _validate_dependency_sha(
        binding.get("source_plan_sha256"), "SAVED_PLAN_SHA_INVALID"
    )
    scene_ids = binding.get("scene_ids")
    if (
        not isinstance(scene_ids, list)
        or any(not isinstance(scene_id, str) or not scene_id for scene_id in scene_ids)
        or len(scene_ids) != len(set(scene_ids))
    ):
        _fail("SAVED_SCENE_IDS_INVALID")
    scene_by_id = _index_rows(binding.get("scenes"), "scene_id", "SAVED_SCENE")
    if list(scene_by_id) != scene_ids:
        _fail("SAVED_SCENE_ORDER_INVALID")
    card_by_scene: dict[str, str] = {}
    for card in saved_result.get("cards", []):
        if not isinstance(card, dict) or not isinstance(card.get("source"), dict):
            _fail("SAVED_CARD_SCENE_BINDING_INVALID")
        scene_id = card["source"].get("scene_id")
        card_id = card.get("card_id")
        if (
            not isinstance(scene_id, str)
            or not scene_id
            or not isinstance(card_id, str)
            or not card_id
            or scene_id in card_by_scene
        ):
            _fail("SAVED_CARD_SCENE_BINDING_INVALID")
        card_by_scene[scene_id] = card_id
    if set(card_by_scene) != set(scene_ids):
        _fail("SAVED_CARD_SCENE_BINDING_INVALID")
    for scene_id, dependency in scene_by_id.items():
        if set(dependency) != SCENE_DEPENDENCY_KEYS:
            _fail("SAVED_SCENE_DEPENDENCY_INVALID", scene_id)
        if (
            dependency.get("card_id") != card_by_scene[scene_id]
            or dependency.get("slot_ref") != binding["slot_ref"]
        ):
            _fail("SAVED_SCENE_DEPENDENCY_INVALID", scene_id)
        _positive_int(dependency.get("scene_rev"), "SAVED_SCENE_REV_INVALID")
        _positive_int(dependency.get("scene_order"), "SAVED_SCENE_ORDER_INVALID")
        _positive_int(dependency.get("scene_count"), "SAVED_SCENE_COUNT_INVALID")
        _validate_dependency_sha(
            dependency.get("scene_sha256"), "SAVED_SCENE_SHA_INVALID"
        )
        _validate_dependency_sha(
            dependency.get("scene_binding_sha256"),
            "SAVED_SCENE_BINDING_SHA_INVALID",
        )
        event_by_id = _index_rows(
            dependency.get("events"), "event_id", "SAVED_EVENT"
        )
        if list(event_by_id) != dependency.get("event_refs"):
            _fail("SAVED_EVENT_ORDER_INVALID", scene_id)
        for event in event_by_id.values():
            if set(event) != EVENT_DEPENDENCY_KEYS:
                _fail("SAVED_EVENT_DEPENDENCY_INVALID")
            _positive_int(event.get("event_rev"), "SAVED_EVENT_REV_INVALID")
            _validate_dependency_sha(
                event.get("event_sha256"), "SAVED_EVENT_SHA_INVALID"
            )
            _validate_dependency_sha(
                event.get("binding_sha256"), "SAVED_EVENT_BINDING_SHA_INVALID"
            )
        anchor_by_id = _index_rows(
            dependency.get("anchors"), "anchor_id", "SAVED_ANCHOR"
        )
        for anchor in anchor_by_id.values():
            if set(anchor) != ANCHOR_DEPENDENCY_KEYS:
                _fail("SAVED_ANCHOR_DEPENDENCY_INVALID")
            _positive_int(anchor.get("revision"), "SAVED_ANCHOR_REV_INVALID")
            _validate_dependency_sha(
                anchor.get("anchor_sha256"), "SAVED_ANCHOR_SHA_INVALID"
            )

    basis = saved_result.get("workspace_basis")
    if (
        not isinstance(basis, dict)
        or basis.get("source_plan_version") != binding["source_plan_version"]
        or basis.get("source_plan_sha256") != binding["source_plan_sha256"]
        or basis.get("slot_ref") != binding["slot_ref"]
    ):
        _fail("SAVED_WORKSPACE_BASIS_MISMATCH")
    return copy.deepcopy(binding)


def _dependency_reasons(
    saved: dict[str, Any], current: dict[str, Any]
) -> list[str]:
    reasons: list[str] = []
    if saved["scene_rev"] != current["scene_rev"]:
        reasons.append("SCENE_REV_CHANGED")
    if saved["scene_sha256"] != current["scene_sha256"]:
        reasons.append("SCENE_CONTENT_CHANGED")
    if (
        saved["scene_order"] != current["scene_order"]
        or saved["scene_count"] != current["scene_count"]
    ):
        reasons.append("SCENE_POSITION_CHANGED")
    if saved["scene_binding_sha256"] != current["scene_binding_sha256"]:
        reasons.append("SCENE_BINDING_CHANGED")
    if saved["event_refs"] != current["event_refs"]:
        reasons.append("EVENT_SET_CHANGED")
    else:
        current_events = {event["event_id"]: event for event in current["events"]}
        for saved_event in saved["events"]:
            event_id = saved_event["event_id"]
            current_event = current_events[event_id]
            if (
                saved_event["event_rev"] != current_event["event_rev"]
                or saved_event["event_sha256"] != current_event["event_sha256"]
            ):
                reasons.append(f"EVENT_CHANGED:{event_id}")
            if saved_event["binding_sha256"] != current_event["binding_sha256"]:
                reasons.append(f"EVENT_BINDING_CHANGED:{event_id}")
    saved_anchors = {anchor["anchor_id"]: anchor for anchor in saved["anchors"]}
    current_anchors = {anchor["anchor_id"]: anchor for anchor in current["anchors"]}
    if list(saved_anchors) != list(current_anchors):
        reasons.append("ANCHOR_SET_CHANGED")
    for anchor_id in sorted(set(saved_anchors) & set(current_anchors)):
        if saved_anchors[anchor_id] != current_anchors[anchor_id]:
            reasons.append(f"ANCHOR_CHANGED:{anchor_id}")
    return reasons


def execute(
    workspace: AuthorWorkspace,
    slot_ref: str,
    anchors: list[dict[str, Any]],
    export_context: dict[str, Any],
    scene_bindings: list[dict[str, Any]],
    event_bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    """只读当前 plan，显式补料后返回带逐场依赖绑定的 C8 原型。"""
    handle = _require_workspace(workspace)
    snapshot = chapter_slot_workspace.execute(handle, slot_ref)
    m10_request = m10_scene_slice_adapter.execute(
        {
            "chapter_slot_snapshot": snapshot,
            "anchors": anchors,
            "export_context": export_context,
            "scene_bindings": scene_bindings,
            "event_bindings": event_bindings,
        }
    )
    prototype = scene_export_tool.execute(m10_request)
    if (
        prototype.get("contract") != scene_export.PROTOTYPE_CONTRACT
        or prototype.get("version") != scene_export.PROTOTYPE_VERSION
    ):
        _fail("C8_PROTOTYPE_IDENTITY_DRIFT")
    return {
        **copy.deepcopy(prototype),
        "workspace_basis": {
            "snapshot_contract": snapshot["contract"],
            "snapshot_version": snapshot["version"],
            "source_plan_version": snapshot["source_plan_version"],
            "source_plan_sha256": snapshot["source_plan_sha256"],
            "slot_ref": snapshot["slot_ref"],
            "slot_rev": snapshot["slot_rev"],
            "generation_watermark": copy.deepcopy(
                snapshot["generation_watermark"]
            ),
        },
        "workspace_binding": _workspace_binding(
            handle,
            snapshot,
            anchors,
            scene_bindings,
            event_bindings,
        ),
    }


def inspect_freshness(
    workspace: AuthorWorkspace,
    saved_scene_result: dict[str, Any],
    anchors: list[dict[str, Any]],
    scene_bindings: list[dict[str, Any]],
    event_bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    """逐场比较已保存 C8 原型的真实依赖，不用整份 plan SHA 一刀切。"""
    handle = _require_workspace(workspace)
    saved_binding = _saved_binding(saved_scene_result)
    if (
        saved_binding["author_id"] != handle.author_id
        or saved_binding["project_id"] != handle.project_id
    ):
        _fail("SAVED_WORKSPACE_BINDING_MISMATCH")

    snapshot = chapter_slot_workspace.execute(handle, saved_binding["slot_ref"])
    current_scene_ids = list(snapshot["scene_refs"])
    saved_scene_ids = list(saved_binding["scene_ids"])
    new_scene_ids = [
        scene_id for scene_id in current_scene_ids if scene_id not in saved_scene_ids
    ]
    removed_scene_ids = [
        scene_id for scene_id in saved_scene_ids if scene_id not in current_scene_ids
    ]
    comparable_ids = [
        scene_id for scene_id in current_scene_ids if scene_id in saved_scene_ids
    ]
    current_dependencies = _scene_dependencies(
        snapshot,
        anchors,
        scene_bindings,
        event_bindings,
        comparable_ids,
    )
    saved_by_id = {
        dependency["scene_id"]: dependency
        for dependency in saved_binding["scenes"]
    }
    current_by_id = {
        dependency["scene_id"]: dependency
        for dependency in current_dependencies
    }

    scene_results: list[dict[str, Any]] = []
    for scene_id in current_scene_ids:
        if scene_id in new_scene_ids:
            scene_results.append(
                {"scene_id": scene_id, "status": "NEW", "reasons": ["SCENE_ADDED"]}
            )
            continue
        reasons = _dependency_reasons(saved_by_id[scene_id], current_by_id[scene_id])
        scene_results.append(
            {
                "scene_id": scene_id,
                "status": "STALE" if reasons else "CURRENT",
                "reasons": reasons,
            }
        )
    scene_results.extend(
        {
            "scene_id": scene_id,
            "status": "STALE",
            "reasons": ["SCENE_REMOVED"],
        }
        for scene_id in removed_scene_ids
    )
    return {
        "slot_ref": saved_binding["slot_ref"],
        "plan_snapshot_changed": (
            saved_binding["source_plan_version"] != snapshot["source_plan_version"]
            or saved_binding["source_plan_sha256"]
            != snapshot["source_plan_sha256"]
        ),
        "saved_plan_snapshot": {
            "version": saved_binding["source_plan_version"],
            "sha256": saved_binding["source_plan_sha256"],
        },
        "current_plan_snapshot": {
            "version": snapshot["source_plan_version"],
            "sha256": snapshot["source_plan_sha256"],
        },
        "scenes": scene_results,
        "new_scene_ids": new_scene_ids,
        "removed_scene_ids": removed_scene_ids,
    }


__all__ = [
    "SceneExportWorkspaceError",
    "execute",
    "inspect_freshness",
]
