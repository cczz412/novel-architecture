"""把作者当前工作稿保存到已绑定的 AuthorWorkspace。

这个适配器只管一份 current 工作稿的保存、递增和读回。它不验证
planstore 中的章槽，也不触发交棒、收工、C1 或事实写入。
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping
from typing import Any

from mvp import chapter_slot_workspace
from mvp.workspace import (
    OPERATION_ID_RE,
    SHA256_RE,
    AuthorWorkspace,
    VersionConflictError,
)


ACTION_KEYS = {
    "operation_id",
    "slot_ref",
    "source_outline_ref",
    "expected_rev",
    "entry_mode",
    "author_text",
}
DRAFT_KEYS = {
    "contract",
    "version",
    "work_ref",
    "slot_ref",
    "source_outline_ref",
    "work_rev",
    "state",
    "entry_mode",
    "text",
    "text_sha256",
    "last_operation_id",
}
ENTRY_MODES = {"typed", "pasted", "edited"}
HANDOVER_ACTION_KEYS = {
    "contract",
    "version",
    "operation_id",
    "actor",
    "intent",
    "work_ref",
    "work_rev",
    "slot_ref",
    "source_outline_ref",
    "target_contract",
    "target_planstore_result",
}
CLOSEOUT_ACTION_KEYS = {
    "contract",
    "version",
    "operation_id",
    "actor",
    "slot_ref",
    "route",
    "work_ref",
    "work_rev",
    "check_result_ref",
}


class WorkDraftWorkspaceError(ValueError):
    """工作稿未满足保存或读回条件。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _validated_workspace(workspace: object) -> AuthorWorkspace:
    if not isinstance(workspace, AuthorWorkspace):
        raise WorkDraftWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return workspace


def _canonical_reference(value: object, code: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise WorkDraftWorkspaceError(code)
    return value


def _text_sha256(text: str) -> str:
    try:
        raw = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise WorkDraftWorkspaceError("WORK_DRAFT_TEXT_NOT_UTF8") from exc
    return hashlib.sha256(raw).hexdigest()


def _validated_action(action: object) -> dict[str, Any]:
    if not isinstance(action, Mapping) or set(action) != ACTION_KEYS:
        raise WorkDraftWorkspaceError("WORK_DRAFT_SAVE_ACTION_INVALID")
    operation_id = action["operation_id"]
    expected_rev = action["expected_rev"]
    entry_mode = action["entry_mode"]
    author_text = action["author_text"]
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        raise WorkDraftWorkspaceError("OPERATION_ID_INVALID")
    if (
        not isinstance(expected_rev, int)
        or isinstance(expected_rev, bool)
        or expected_rev < 0
    ):
        raise WorkDraftWorkspaceError("EXPECTED_WORK_REV_INVALID")
    if not isinstance(entry_mode, str) or entry_mode not in ENTRY_MODES:
        raise WorkDraftWorkspaceError("WORK_DRAFT_ENTRY_MODE_INVALID")
    # v1 合同没有禁止空文本，这里只验类型，不自造产品语义。
    if not isinstance(author_text, str):
        raise WorkDraftWorkspaceError("WORK_DRAFT_TEXT_INVALID")
    _text_sha256(author_text)
    return {
        "operation_id": operation_id,
        "slot_ref": _canonical_reference(
            action["slot_ref"], "WORK_DRAFT_SLOT_REF_INVALID"
        ),
        "source_outline_ref": _canonical_reference(
            action["source_outline_ref"],
            "WORK_DRAFT_SOURCE_OUTLINE_REF_INVALID",
        ),
        "expected_rev": expected_rev,
        "entry_mode": entry_mode,
        "author_text": author_text,
    }


def _validated_handover_action(action: object) -> dict[str, Any]:
    if not isinstance(action, Mapping) or set(action) != HANDOVER_ACTION_KEYS:
        raise WorkDraftWorkspaceError("WORK_DRAFT_HANDOVER_ACTION_INVALID")
    operation_id = action["operation_id"]
    work_rev = action["work_rev"]
    if action["contract"] != "WORK_DRAFT_HANDOVER_ACTION":
        raise WorkDraftWorkspaceError("WORK_DRAFT_HANDOVER_CONTRACT_INVALID")
    if action["version"] != "v1":
        raise WorkDraftWorkspaceError("WORK_DRAFT_HANDOVER_VERSION_INVALID")
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        raise WorkDraftWorkspaceError("OPERATION_ID_INVALID")
    if action["actor"] != "author":
        raise WorkDraftWorkspaceError("WORK_DRAFT_HANDOVER_ACTOR_INVALID")
    if action["intent"] != "adopt_as_manuscript":
        raise WorkDraftWorkspaceError("WORK_DRAFT_HANDOVER_INTENT_INVALID")
    if (
        not isinstance(work_rev, int)
        or isinstance(work_rev, bool)
        or work_rev < 1
    ):
        raise WorkDraftWorkspaceError("WORK_DRAFT_HANDOVER_REVISION_INVALID")
    if action["target_contract"] != "C1_CHAPTER_DOC":
        raise WorkDraftWorkspaceError("WORK_DRAFT_HANDOVER_TARGET_INVALID")
    if action["target_planstore_result"] != "handover_parts":
        raise WorkDraftWorkspaceError("WORK_DRAFT_HANDOVER_PLAN_RESULT_INVALID")
    normalized = copy.deepcopy(dict(action))
    normalized["work_ref"] = _canonical_reference(
        action["work_ref"], "WORK_DRAFT_HANDOVER_WORK_REF_INVALID"
    )
    normalized["slot_ref"] = _canonical_reference(
        action["slot_ref"], "WORK_DRAFT_HANDOVER_SLOT_REF_INVALID"
    )
    normalized["source_outline_ref"] = _canonical_reference(
        action["source_outline_ref"],
        "WORK_DRAFT_HANDOVER_SOURCE_OUTLINE_REF_INVALID",
    )
    return normalized


def _validated_skip_check_action(action: object) -> dict[str, Any]:
    if not isinstance(action, Mapping) or set(action) != CLOSEOUT_ACTION_KEYS:
        raise WorkDraftWorkspaceError("WRITING_DESK_CLOSEOUT_ACTION_INVALID")
    operation_id = action["operation_id"]
    work_rev = action["work_rev"]
    if action["contract"] != "WRITING_DESK_CLOSEOUT_ACTION":
        raise WorkDraftWorkspaceError("WRITING_DESK_CLOSEOUT_CONTRACT_INVALID")
    if action["version"] != "v1":
        raise WorkDraftWorkspaceError("WRITING_DESK_CLOSEOUT_VERSION_INVALID")
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        raise WorkDraftWorkspaceError("OPERATION_ID_INVALID")
    if action["actor"] != "author":
        raise WorkDraftWorkspaceError("WRITING_DESK_CLOSEOUT_ACTOR_INVALID")
    if action["route"] != "skip_check":
        raise WorkDraftWorkspaceError("SKIP_CHECK_ROUTE_REQUIRED")
    if (
        not isinstance(work_rev, int)
        or isinstance(work_rev, bool)
        or work_rev < 1
    ):
        raise WorkDraftWorkspaceError("WRITING_DESK_CLOSEOUT_REVISION_INVALID")
    if action["check_result_ref"] is not None:
        raise WorkDraftWorkspaceError("SKIP_CHECK_MUST_NOT_REFERENCE_RESULT")
    normalized = copy.deepcopy(dict(action))
    normalized["work_ref"] = _canonical_reference(
        action["work_ref"], "WRITING_DESK_CLOSEOUT_WORK_REF_INVALID"
    )
    normalized["slot_ref"] = _canonical_reference(
        action["slot_ref"], "WRITING_DESK_CLOSEOUT_SLOT_REF_INVALID"
    )
    return normalized


def _validated_no_prose_action(action: object) -> dict[str, Any]:
    if not isinstance(action, Mapping) or set(action) != CLOSEOUT_ACTION_KEYS:
        raise WorkDraftWorkspaceError("WRITING_DESK_CLOSEOUT_ACTION_INVALID")
    operation_id = action["operation_id"]
    if action["contract"] != "WRITING_DESK_CLOSEOUT_ACTION":
        raise WorkDraftWorkspaceError("WRITING_DESK_CLOSEOUT_CONTRACT_INVALID")
    if action["version"] != "v1":
        raise WorkDraftWorkspaceError("WRITING_DESK_CLOSEOUT_VERSION_INVALID")
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        raise WorkDraftWorkspaceError("OPERATION_ID_INVALID")
    if action["actor"] != "author":
        raise WorkDraftWorkspaceError("WRITING_DESK_CLOSEOUT_ACTOR_INVALID")
    if action["route"] != "no_prose":
        raise WorkDraftWorkspaceError("NO_PROSE_ROUTE_REQUIRED")
    if action["work_ref"] is not None or action["work_rev"] is not None:
        raise WorkDraftWorkspaceError("NO_PROSE_MUST_NOT_REFERENCE_WORK")
    if action["check_result_ref"] is not None:
        raise WorkDraftWorkspaceError("NO_PROSE_MUST_NOT_REFERENCE_RESULT")
    normalized = copy.deepcopy(dict(action))
    normalized["slot_ref"] = _canonical_reference(
        action["slot_ref"], "WRITING_DESK_CLOSEOUT_SLOT_REF_INVALID"
    )
    return normalized


def _validated_entry(entry: object) -> dict[str, Any]:
    if not isinstance(entry, Mapping) or set(entry) != {
        "logical_key",
        "version",
        "sha256",
        "payload",
    }:
        raise WorkDraftWorkspaceError("WORK_DRAFT_WORKSPACE_ENTRY_INVALID")
    version = entry["version"]
    workspace_sha = entry["sha256"]
    payload = entry["payload"]
    if (
        entry["logical_key"] != "draft"
        or not isinstance(version, int)
        or isinstance(version, bool)
        or version < 1
        or not isinstance(workspace_sha, str)
        or SHA256_RE.fullmatch(workspace_sha) is None
        or not isinstance(payload, Mapping)
        or set(payload) != DRAFT_KEYS
    ):
        raise WorkDraftWorkspaceError("WORK_DRAFT_WORKSPACE_ENTRY_INVALID")

    slot_ref = _canonical_reference(
        payload["slot_ref"], "WORK_DRAFT_SLOT_REF_INVALID"
    )
    source_outline_ref = _canonical_reference(
        payload["source_outline_ref"],
        "WORK_DRAFT_SOURCE_OUTLINE_REF_INVALID",
    )
    work_rev = payload["work_rev"]
    entry_mode = payload["entry_mode"]
    text = payload["text"]
    last_operation_id = payload["last_operation_id"]
    if payload["contract"] != "WRITING_DESK_WORK_DRAFT":
        raise WorkDraftWorkspaceError("WORK_DRAFT_CONTRACT_INVALID")
    if payload["version"] != "v1":
        raise WorkDraftWorkspaceError("WORK_DRAFT_VERSION_INVALID")
    if payload["work_ref"] != f"{slot_ref}@work":
        raise WorkDraftWorkspaceError("WORK_DRAFT_REF_INVALID")
    if (
        not isinstance(work_rev, int)
        or isinstance(work_rev, bool)
        or work_rev < 1
        or work_rev != version
    ):
        raise WorkDraftWorkspaceError("WORK_DRAFT_REVISION_INVALID")
    if payload["state"] != "working":
        raise WorkDraftWorkspaceError("WORK_DRAFT_STATE_INVALID")
    if not isinstance(entry_mode, str) or entry_mode not in ENTRY_MODES:
        raise WorkDraftWorkspaceError("WORK_DRAFT_ENTRY_MODE_INVALID")
    if not isinstance(text, str):
        raise WorkDraftWorkspaceError("WORK_DRAFT_TEXT_INVALID")
    if payload["text_sha256"] != _text_sha256(text):
        raise WorkDraftWorkspaceError("WORK_DRAFT_TEXT_SHA_MISMATCH")
    if (
        not isinstance(last_operation_id, str)
        or OPERATION_ID_RE.fullmatch(last_operation_id) is None
    ):
        raise WorkDraftWorkspaceError("WORK_DRAFT_LAST_OPERATION_ID_INVALID")
    # source_outline_ref 在这个适配器中仅保真；它是否仍为 current
    # 属于 planstore/hand-over 的合同边界，本票不越权判断。
    _ = source_outline_ref
    return {
        "draft_workspace": {
            "version": version,
            "sha256": workspace_sha,
        },
        "current_work_draft": copy.deepcopy(dict(payload)),
    }


def read_current_work_draft(workspace: AuthorWorkspace) -> dict[str, Any]:
    """读回 current 工作稿，并对完整字段、派生身份和文本 SHA 做复验。"""
    workspace = _validated_workspace(workspace)
    entry = workspace.read("draft")
    if entry is None:
        return {
            "status": "EMPTY",
            "draft_workspace": None,
            "current_work_draft": None,
        }
    validated = _validated_entry(entry)
    return {"status": "READY", **validated}


def prepare_explicit_handover(
    workspace: AuthorWorkspace,
    action: Mapping[str, Any],
) -> dict[str, Any]:
    """生成只读交棒前置包；不创建 C1，也不写 planstore。"""
    workspace = _validated_workspace(workspace)
    normalized_action = _validated_handover_action(action)

    first_entry = workspace.read("draft")
    second_entry = workspace.read("draft")
    if first_entry != second_entry:
        raise WorkDraftWorkspaceError("WORK_DRAFT_CHANGED_DURING_HANDOVER_READ")
    if second_entry is None:
        raise WorkDraftWorkspaceError("CURRENT_WORK_DRAFT_REQUIRED")
    current = _validated_entry(second_entry)
    draft = current["current_work_draft"]

    if normalized_action["work_rev"] != draft["work_rev"]:
        raise WorkDraftWorkspaceError("STALE_WORK_REVISION")
    if any(
        normalized_action[field] != draft[field]
        for field in (
            "work_ref",
            "slot_ref",
            "source_outline_ref",
        )
    ):
        raise WorkDraftWorkspaceError("WORK_DRAFT_HANDOVER_REF_MISMATCH")

    return {
        "status": "PREFLIGHT_READY",
        "handover_action": copy.deepcopy(normalized_action),
        "current_work_draft": copy.deepcopy(draft),
        "draft_workspace": copy.deepcopy(current["draft_workspace"]),
    }


def prepare_skip_check_closeout(
    workspace: AuthorWorkspace,
    action: Mapping[str, Any],
) -> dict[str, Any]:
    """准备作者显式 skip_check 收工；只读且不产生 PASS。"""
    workspace = _validated_workspace(workspace)
    normalized_action = _validated_skip_check_action(action)

    first_entry = workspace.read("draft")
    second_entry = workspace.read("draft")
    if first_entry != second_entry:
        raise WorkDraftWorkspaceError("WORK_DRAFT_CHANGED_DURING_CLOSEOUT_READ")
    if second_entry is None:
        raise WorkDraftWorkspaceError("CURRENT_WORK_DRAFT_REQUIRED")
    current = _validated_entry(second_entry)
    draft = current["current_work_draft"]

    if normalized_action["work_rev"] != draft["work_rev"]:
        raise WorkDraftWorkspaceError("STALE_WORK_REVISION")
    if (
        normalized_action["work_ref"] != draft["work_ref"]
        or normalized_action["slot_ref"] != draft["slot_ref"]
    ):
        raise WorkDraftWorkspaceError("WORK_DRAFT_CLOSEOUT_REF_MISMATCH")

    return {
        "status": "PREFLIGHT_READY",
        "closeout_action": copy.deepcopy(normalized_action),
        "draft_workspace": copy.deepcopy(current["draft_workspace"]),
        "result": "skipped_by_author",
        "handover_effect": "none",
        "chapter_close_effect": "none",
        "truth_effect": "none",
    }


def prepare_no_prose_closeout(
    workspace: AuthorWorkspace,
    action: Mapping[str, Any],
) -> dict[str, Any]:
    """准备无工作稿的 no_prose 收工；不保存进度或改章状态。"""
    workspace = _validated_workspace(workspace)
    normalized_action = _validated_no_prose_action(action)

    draft_before = workspace.read("draft")
    if draft_before is not None:
        raise WorkDraftWorkspaceError("NO_PROSE_REQUIRES_EMPTY_WORK_DRAFT")
    first_snapshot = chapter_slot_workspace.execute(
        workspace, normalized_action["slot_ref"]
    )
    second_snapshot = chapter_slot_workspace.execute(
        workspace, normalized_action["slot_ref"]
    )
    draft_after = workspace.read("draft")
    if draft_before != draft_after:
        raise WorkDraftWorkspaceError("WORK_DRAFT_CHANGED_DURING_CLOSEOUT_READ")
    if first_snapshot != second_snapshot:
        raise WorkDraftWorkspaceError("CHAPTER_SLOT_CHANGED_DURING_CLOSEOUT_READ")

    return {
        "status": "PREFLIGHT_READY",
        "closeout_action": copy.deepcopy(normalized_action),
        "chapter_slot_source": {
            "slot_ref": second_snapshot["slot_ref"],
            "source_plan_version": second_snapshot["source_plan_version"],
            "source_plan_sha256": second_snapshot["source_plan_sha256"],
            "generation_watermark": copy.deepcopy(
                second_snapshot["generation_watermark"]
            ),
        },
        "result": "not_applicable_no_manuscript",
        "handover_effect": "none",
        "chapter_close_effect": "none",
        "truth_effect": "none",
    }


def save_current_work_draft(
    workspace: AuthorWorkspace,
    action: Mapping[str, Any],
) -> dict[str, Any]:
    """按合同动作保存唯一 current 工作稿。"""
    workspace = _validated_workspace(workspace)
    normalized = _validated_action(action)
    existing = read_current_work_draft(workspace)
    if (
        existing["current_work_draft"] is not None
        and existing["current_work_draft"]["slot_ref"] != normalized["slot_ref"]
    ):
        raise WorkDraftWorkspaceError("CURRENT_WORK_DRAFT_SLOT_CONFLICT")

    new_revision = normalized["expected_rev"] + 1
    text = normalized["author_text"]
    draft = {
        "contract": "WRITING_DESK_WORK_DRAFT",
        "version": "v1",
        "work_ref": f"{normalized['slot_ref']}@work",
        "slot_ref": normalized["slot_ref"],
        "source_outline_ref": normalized["source_outline_ref"],
        "work_rev": new_revision,
        "state": "working",
        "entry_mode": normalized["entry_mode"],
        "text": text,
        "text_sha256": _text_sha256(text),
        "last_operation_id": normalized["operation_id"],
    }
    try:
        receipt = workspace.commit(
            normalized["operation_id"],
            {"draft": draft},
            {"draft": normalized["expected_rev"]},
        )
    except VersionConflictError as exc:
        raise WorkDraftWorkspaceError("STALE_WORK_REVISION") from exc

    current = read_current_work_draft(workspace)
    return {
        "status": receipt["status"],
        "replayed": receipt["replayed"],
        "operation_receipt": {
            "operation_id": receipt["operation_id"],
            "generation_id": receipt["generation_id"],
            "draft_workspace_version": receipt["versions"]["draft"],
            "draft_workspace_sha256": receipt["payload_sha256"]["draft"],
        },
        "draft_workspace": current["draft_workspace"],
        "current_work_draft": current["current_work_draft"],
    }
