"""把已提交 C1 v1 交给 AuthorWorkspace 中的 current plan。

本模块只消费 chapter admission 的 pending 记录和现成 chapter_id。它不会读取
工作稿全文来造章，不会分配 C1/C11 身份，也不会写 facts、actual 或关章状态。
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from typing import Any, NoReturn

from mvp import chapter_initial_admission_workspace as admission_workspace
from mvp import plan_workspace, planstore
from mvp.workspace import OPERATION_ID_RE, AuthorWorkspace


IDENTITY = "AUTHOR_WORKSPACE_COMMITTED_CHAPTER_HANDOVER_R01"


class ChapterHandoverWorkspaceError(ValueError):
    """已提交章节还不能安全写入 current plan。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise ChapterHandoverWorkspaceError(code)


def _workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _sha256(value: object) -> str:
    try:
        raw = (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ChapterHandoverWorkspaceError("VALUE_NOT_CANONICAL_JSON") from exc
    return hashlib.sha256(raw).hexdigest()


def _operation_id(value: object, *, code: str) -> str:
    if not isinstance(value, str) or OPERATION_ID_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _handed_at(value: object) -> tuple[str, str]:
    try:
        return admission_workspace._committed_at(value)
    except admission_workspace.ChapterInitialAdmissionError as exc:
        raise ChapterHandoverWorkspaceError("HANDED_AT_INVALID") from exc


def _request_sha(
    admission_operation_id: str,
    plan_operation_id: str,
    handed_at: str,
) -> str:
    return _sha256(
        {
            "admission_operation_id": admission_operation_id,
            "plan_operation_id": plan_operation_id,
            "handed_at": handed_at,
        }
    )


def _apply_existing_chapter(
    plan_before: dict[str, Any],
    admission: Mapping[str, Any],
    current_chapter_ids: set[str],
    *,
    plan_timestamp: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    plan = copy.deepcopy(plan_before)
    try:
        planstore._validate_plan(plan)
    except (planstore.PlanstoreError, ValueError, TypeError, KeyError) as exc:
        raise ChapterHandoverWorkspaceError("PLAN_CURRENT_INVALID") from exc
    slot_ref = admission["slot_ref"]
    chapter_id = admission["chapter_id"]
    if chapter_id not in current_chapter_ids:
        _fail("CURRENT_C1_CHAPTER_NOT_FOUND")
    if any(
        mapping.get("chapter_id") is not None
        and mapping.get("chapter_id") not in current_chapter_ids
        for mapping in plan["slot_mappings"]
    ):
        _fail("PLAN_MAPPING_CHAPTER_NOT_CURRENT")
    slot_matches = [slot for slot in plan["slots"] if slot.get("id") == slot_ref]
    if len(slot_matches) != 1:
        _fail("PLAN_SLOT_NOT_FOUND")
    slot = slot_matches[0]
    if slot.get("slot_status") == "handed_over":
        _fail("SLOT_ALREADY_HANDED_OVER")
    checkpoint = slot.get("outline_checkpoint")
    if not isinstance(checkpoint, dict) or not isinstance(
        checkpoint.get("outline_rev"), int
    ):
        _fail("OUTLINE_CHECKPOINT_MISSING")
    current_outline = f"{slot_ref}@outline-r{checkpoint['outline_rev']}"
    if admission["source_outline_ref"] != current_outline:
        _fail("OUTLINE_NOT_CURRENT")
    if any(
        mapping.get("mapping_status") == "active"
        and (
            mapping.get("slot_ref") == slot_ref
            or mapping.get("chapter_id") == chapter_id
        )
        for mapping in plan["slot_mappings"]
    ):
        _fail("SLOT_OR_CHAPTER_ALREADY_MAPPED")
    if slot_ref not in plan["slot_sequence"]:
        _fail("SLOT_SEQUENCE_NOT_FOUND")

    scene_refs = list(slot.get("scene_refs", []))
    scenes = [scene for scene in plan["scenes"] if scene.get("id") in scene_refs]
    if len(scenes) != len(scene_refs):
        _fail("COVERED_SCENE_REF_NOT_FOUND")
    scenes_by_id = {scene["id"]: scene for scene in scenes}
    event_refs = [
        event_ref
        for scene_ref in scene_refs
        for event_ref in scenes_by_id[scene_ref].get("pe_refs", [])
    ]
    events = [event for event in plan["events"] if event.get("id") in event_refs]
    if len(events) != len(event_refs):
        _fail("COVERED_PE_REF_NOT_FOUND")

    counter = plan["id_counters"].get("MAP")
    if not isinstance(counter, int) or isinstance(counter, bool) or counter < 0:
        _fail("MAP_COUNTER_INVALID")
    mapping_id = f"MAP-{counter + 1:04d}"
    mapping = {
        "id": mapping_id,
        "slot_ref": slot_ref,
        "chapter_id": chapter_id,
        "expected_chapter_no": plan["slot_sequence"].index(slot_ref) + 1,
        "mapping_kind": "as_written",
        "reason": "",
        "decided_by": "author",
        "mapping_status": "active",
        "superseded_by": None,
    }
    handover_part = {
        "part_no": len(slot.get("handover_parts", [])) + 1,
        "chapter_id": chapter_id,
        "covered_scene_refs": scene_refs,
        "covered_pe_refs": event_refs,
        "handed_at": plan_timestamp,
        "decided_by": "author",
    }
    slot["handover_parts"] = [*slot.get("handover_parts", []), handover_part]
    slot["slot_status"] = "handed_over"
    slot["truth_bearing"] = "handed_over"
    slot["rev"] += 1
    if "updated_at" in slot:
        slot["updated_at"] = plan_timestamp
    for item in [*scenes, *events]:
        item["truth_bearing"] = "handed_over"
        item["rev"] += 1
        if "updated_at" in item:
            item["updated_at"] = plan_timestamp
    plan["slot_mappings"].append(mapping)
    plan["id_counters"]["MAP"] = counter + 1
    try:
        planstore._validate_plan(plan)
    except (planstore.PlanstoreError, ValueError, TypeError, KeyError) as exc:
        raise ChapterHandoverWorkspaceError("PLAN_AFTER_HANDOVER_INVALID") from exc
    return plan, mapping, handover_part


def _validate_completed_plan(
    plan: dict[str, Any],
    admission: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    marker = admission.get("plan_handover")
    if not isinstance(marker, dict):
        _fail("COMPLETED_PLAN_HANDOVER_MARKER_MISSING")
    mapping_matches = [
        item
        for item in plan.get("slot_mappings", [])
        if item.get("id") == marker["mapping_id"]
        and item.get("slot_ref") == admission["slot_ref"]
        and item.get("chapter_id") == admission["chapter_id"]
    ]
    slot_matches = [
        slot
        for slot in plan.get("slots", [])
        if slot.get("id") == admission["slot_ref"]
    ]
    if len(mapping_matches) != 1 or len(slot_matches) != 1:
        _fail("COMPLETED_PLAN_HANDOVER_NOT_RESOLVABLE")
    part_matches = [
        part
        for part in slot_matches[0].get("handover_parts", [])
        if part.get("part_no") == marker["handover_part_no"]
        and part.get("chapter_id") == admission["chapter_id"]
    ]
    if len(part_matches) != 1:
        _fail("COMPLETED_PLAN_HANDOVER_NOT_RESOLVABLE")
    return copy.deepcopy(mapping_matches[0]), copy.deepcopy(part_matches[0])


def _result(
    admission: Mapping[str, Any],
    mapping: Mapping[str, Any],
    handover_part: Mapping[str, Any],
    *,
    replayed: bool,
) -> dict[str, Any]:
    marker = admission["plan_handover"]
    return {
        "identity": IDENTITY,
        "status": "HANDOVER_COMPLETE",
        "replayed": replayed,
        "admission_operation_id": admission["operation_id"],
        "plan_operation_id": marker["operation_id"],
        "chapter_revision_ref": {
            "chapter_id": admission["chapter_id"],
            "revision_no": admission["revision_no"],
            "revision_text_sha256": admission["revision_text_sha256"],
        },
        "mapping": copy.deepcopy(dict(mapping)),
        "handover_part": copy.deepcopy(dict(handover_part)),
        "plan_commit": copy.deepcopy(marker),
        "chapter_write": 0,
        "c10_write": 0,
        "c11_write": 0,
        "facts_write": 0,
    }


def complete_pending_handover(
    workspace: AuthorWorkspace,
    admission_operation_id: str,
    plan_operation_id: str,
    handed_at: str,
) -> dict[str, Any]:
    """消费一条 pending admission，把既有章号写入计划账并标完成。"""
    handle = _workspace(workspace)
    admission_operation_id = _operation_id(
        admission_operation_id,
        code="ADMISSION_OPERATION_ID_INVALID",
    )
    plan_operation_id = _operation_id(
        plan_operation_id,
        code="PLAN_OPERATION_ID_INVALID",
    )
    if plan_operation_id == admission_operation_id:
        _fail("PLAN_OPERATION_ID_MUST_BE_DISTINCT")
    handed_at, plan_timestamp = _handed_at(handed_at)
    request_sha = _request_sha(
        admission_operation_id,
        plan_operation_id,
        handed_at,
    )
    handle.recover()
    bundle = admission_workspace._read_bundle(handle)
    admission = bundle["payloads"][admission_workspace.OPERATIONS_KEY][
        "operations"
    ].get(admission_operation_id)
    if admission is None:
        _fail("CHAPTER_ADMISSION_OPERATION_NOT_FOUND")

    plan_entry = plan_workspace.read_plan(handle)
    if plan_entry is None:
        _fail("CURRENT_PLAN_REQUIRED")
    if admission["stage"] == "HANDOVER_COMPLETE":
        marker = admission["plan_handover"]
        if (
            marker["operation_id"] != plan_operation_id
            or marker["request_sha256"] != request_sha
            or marker["handed_at"] != handed_at
        ):
            _fail("PLAN_HANDOVER_ALREADY_COMPLETED_WITH_DIFFERENT_REQUEST")
        mapping, handover_part = _validate_completed_plan(
            plan_entry["plan"], admission
        )
        return _result(
            admission,
            mapping,
            handover_part,
            replayed=True,
        )
    if admission["stage"] != "AW_COMMITTED_PLANSTORE_PENDING":
        _fail("CHAPTER_ADMISSION_STAGE_INVALID")

    plan_after, mapping, handover_part = _apply_existing_chapter(
        plan_entry["plan"],
        admission,
        {
            chapter["id"]
            for chapter in bundle["payloads"][admission_workspace.CHAPTERS_KEY]
        },
        plan_timestamp=plan_timestamp,
    )
    operation_store = copy.deepcopy(
        bundle["payloads"][admission_workspace.OPERATIONS_KEY]
    )
    operation_after = copy.deepcopy(admission)
    operation_after["stage"] = "HANDOVER_COMPLETE"
    operation_after["plan_handover"] = {
        "operation_id": plan_operation_id,
        "request_sha256": request_sha,
        "plan_version": plan_entry["version"] + 1,
        "plan_sha256": _sha256(plan_after),
        "mapping_id": mapping["id"],
        "handover_part_no": handover_part["part_no"],
        "handed_at": handed_at,
    }
    operation_store["operations"][admission_operation_id] = operation_after
    admission_workspace._validated_admission(
        operation_after, admission_operation_id
    )

    expected = {
        "plan": {
            "version": plan_entry["version"],
            "sha256": plan_entry["sha256"],
        },
        admission_workspace.OPERATIONS_KEY: bundle["watermarks"][
            admission_workspace.OPERATIONS_KEY
        ],
    }
    guards = {
        key: watermark
        for key, watermark in bundle["watermarks"].items()
        if key != admission_workspace.OPERATIONS_KEY
    }
    handle.commit_guarded(
        plan_operation_id,
        {
            "plan": plan_after,
            admission_workspace.OPERATIONS_KEY: operation_store,
        },
        expected,
        guards,
    )
    after_bundle = admission_workspace._read_bundle(handle)
    saved = after_bundle["payloads"][admission_workspace.OPERATIONS_KEY][
        "operations"
    ][admission_operation_id]
    after_plan = plan_workspace.read_plan(handle)
    if (
        after_plan is None
        or after_plan["version"] != saved["plan_handover"]["plan_version"]
        or after_plan["sha256"] != saved["plan_handover"]["plan_sha256"]
    ):
        _fail("PLAN_HANDOVER_COMMIT_WATERMARK_MISMATCH")
    saved_mapping, saved_part = _validate_completed_plan(after_plan["plan"], saved)
    return _result(saved, saved_mapping, saved_part, replayed=False)


__all__ = [
    "ChapterHandoverWorkspaceError",
    "complete_pending_handover",
]
