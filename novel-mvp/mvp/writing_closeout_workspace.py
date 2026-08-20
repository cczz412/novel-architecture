"""把 full_check 收工动作核成只读预检包。

调用方只能交已绑定的 AuthorWorkspace 和精确 9 字段
WRITING_DESK_CLOSEOUT_ACTION v1。本模块按当前工作稿、当前章槽和
已保存 T14 结果重编检测包并逐字段核对；它不保存收工、不关章、
不交棒，也不调用 provider／模型。
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any, NoReturn

from . import (
    chapter_slot_snapshot_tool,
    chapter_slot_workspace,
    work_draft_workspace,
    writing_check_package_tool,
    writing_check_result_tool,
    writing_check_result_workspace,
)
from .workspace import OPERATION_ID_RE, AuthorWorkspace


ACTION_KEYS = work_draft_workspace.CLOSEOUT_ACTION_KEYS
FORBIDDEN_OUTPUT_TOKENS = {
    "pass",
    "clean",
    "all_clear",
    "checked",
    "chapter_closed",
}


class WritingCloseoutWorkspaceError(ValueError):
    """full_check 预检拒绝了非句柄、过期结果或读取过程中的变化。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise WritingCloseoutWorkspaceError(code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _canonical_reference(value: object, code: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        _fail(code)
    return value


def _wrap(exc: BaseException) -> NoReturn:
    code = getattr(exc, "code", None)
    if not isinstance(code, str) or not code:
        code = str(exc)
    raise WritingCloseoutWorkspaceError(code) from exc


def _validated_full_check_action(action: object) -> dict[str, Any]:
    if not isinstance(action, Mapping) or set(action) != ACTION_KEYS:
        _fail("WRITING_DESK_CLOSEOUT_ACTION_INVALID")
    operation_id = action["operation_id"]
    work_rev = action["work_rev"]
    if action["contract"] != "WRITING_DESK_CLOSEOUT_ACTION":
        _fail("WRITING_DESK_CLOSEOUT_CONTRACT_INVALID")
    if action["version"] != "v1":
        _fail("WRITING_DESK_CLOSEOUT_VERSION_INVALID")
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        _fail("OPERATION_ID_INVALID")
    if action["actor"] != "author":
        _fail("WRITING_DESK_CLOSEOUT_ACTOR_INVALID")
    if action["route"] != "full_check":
        _fail("FULL_CHECK_ROUTE_REQUIRED")
    if (
        not isinstance(work_rev, int)
        or isinstance(work_rev, bool)
        or work_rev < 1
    ):
        _fail("WRITING_DESK_CLOSEOUT_REVISION_INVALID")
    check_result_ref = action["check_result_ref"]
    if not isinstance(check_result_ref, str) or not check_result_ref:
        _fail("FULL_CHECK_RESULT_REF_REQUIRED")
    normalized = copy.deepcopy(dict(action))
    normalized["work_ref"] = _canonical_reference(
        action["work_ref"], "WRITING_DESK_CLOSEOUT_WORK_REF_INVALID"
    )
    normalized["slot_ref"] = _canonical_reference(
        action["slot_ref"], "WRITING_DESK_CLOSEOUT_SLOT_REF_INVALID"
    )
    normalized["check_result_ref"] = _canonical_reference(
        check_result_ref, "FULL_CHECK_RESULT_REF_REQUIRED"
    )
    return normalized


def _resolve_result(
    workspace: AuthorWorkspace, check_result_ref: str
) -> dict[str, Any]:
    try:
        return writing_check_result_workspace.resolve_writing_check_result(
            workspace, check_result_ref
        )
    except writing_check_result_workspace.WritingCheckResultWorkspaceError as exc:
        _wrap(exc)


def _read_current_draft(workspace: AuthorWorkspace) -> dict[str, Any]:
    try:
        current = work_draft_workspace.read_current_work_draft(workspace)
    except work_draft_workspace.WorkDraftWorkspaceError as exc:
        _wrap(exc)
    if current["status"] != "READY" or current["current_work_draft"] is None:
        _fail("CURRENT_WORK_DRAFT_REQUIRED")
    return current


def _read_current_slot(workspace: AuthorWorkspace, slot_ref: str) -> dict[str, Any]:
    try:
        return chapter_slot_workspace.execute(workspace, slot_ref)
    except (
        chapter_slot_workspace.ChapterSlotWorkspaceError,
        chapter_slot_snapshot_tool.ChapterSlotSnapshotError,
    ) as exc:
        _wrap(exc)


def _double_read_draft(workspace: AuthorWorkspace) -> dict[str, Any]:
    first = _read_current_draft(workspace)
    second = _read_current_draft(workspace)
    if first != second:
        _fail("WORK_DRAFT_CHANGED_DURING_PREFLIGHT_READ")
    return second


def _double_read_slot(workspace: AuthorWorkspace, slot_ref: str) -> dict[str, Any]:
    first = _read_current_slot(workspace, slot_ref)
    second = _read_current_slot(workspace, slot_ref)
    if first != second:
        _fail("CHAPTER_SLOT_CHANGED_DURING_PREFLIGHT_READ")
    return second


def _align_current(
    action: dict[str, Any],
    draft: dict[str, Any],
    slot: dict[str, Any],
    stored: dict[str, Any],
) -> None:
    if action["work_rev"] != draft["work_rev"]:
        _fail("STALE_WORK_REVISION")
    if (
        action["work_ref"] != draft["work_ref"]
        or action["slot_ref"] != draft["slot_ref"]
    ):
        _fail("WORK_DRAFT_CLOSEOUT_REF_MISMATCH")
    result = stored["result"]
    if action["check_result_ref"] != result["check_result_ref"]:
        _fail("STALE_CHECK_RESULT")
    if (
        result["slot_ref"] != draft["slot_ref"]
        or result["work_ref"] != draft["work_ref"]
        or result["work_rev"] != draft["work_rev"]
        or result["work_text_sha256"] != draft["text_sha256"]
        or result["source_outline_ref"] != draft["source_outline_ref"]
        or result["slot_ref"] != slot["slot_ref"]
        or result["status"] != "completed"
    ):
        _fail("STALE_CHECK_RESULT")


def _rebuild_formal_result(
    draft: dict[str, Any],
    slot: dict[str, Any],
    stored: dict[str, Any],
) -> dict[str, Any]:
    try:
        package = writing_check_package_tool.execute(
            {
                "work_draft": copy.deepcopy(draft),
                "chapter_slot_snapshot": copy.deepcopy(slot),
                "check_operation_id": stored["result"]["operation_id"],
            }
        )
        rebuilt = writing_check_result_tool.execute(
            {
                "input_package": package,
                "provider_response": {
                    "judgments": copy.deepcopy(stored["result"]["judgments"]),
                },
            }
        )
    except (
        writing_check_package_tool.WritingCheckPackageError,
        writing_check_result_tool.WritingCheckResultError,
    ) as exc:
        _wrap(exc)
    if rebuilt != stored["result"]:
        _fail("STALE_CHECK_RESULT")
    return rebuilt


def _assert_output_is_preflight(payload: dict[str, Any]) -> None:
    if FORBIDDEN_OUTPUT_TOKENS & set(payload):
        _fail("PREFLIGHT_OUTPUT_FORBIDDEN")
    result = payload.get("result")
    if not isinstance(result, str) or result in FORBIDDEN_OUTPUT_TOKENS:
        _fail("PREFLIGHT_OUTPUT_FORBIDDEN")


def prepare_full_check_preflight(
    workspace: AuthorWorkspace,
    action: Mapping[str, Any],
) -> dict[str, Any]:
    """核验 full_check 引用的 T14 结果仍对应当前稿与当前槽；全程只读。"""

    handle = _require_workspace(workspace)
    normalized = _validated_full_check_action(action)

    stored = _resolve_result(handle, normalized["check_result_ref"])
    current_draft = _double_read_draft(handle)
    draft = current_draft["current_work_draft"]
    if normalized["work_rev"] != draft["work_rev"]:
        _fail("STALE_WORK_REVISION")
    if (
        normalized["work_ref"] != draft["work_ref"]
        or normalized["slot_ref"] != draft["slot_ref"]
    ):
        _fail("WORK_DRAFT_CLOSEOUT_REF_MISMATCH")
    slot = _double_read_slot(handle, draft["slot_ref"])
    _align_current(normalized, draft, slot, stored)
    _rebuild_formal_result(draft, slot, stored)

    stored_again = _resolve_result(handle, normalized["check_result_ref"])
    draft_again = _read_current_draft(handle)
    slot_again = _read_current_slot(handle, draft["slot_ref"])
    if stored_again != stored:
        _fail("CHECK_RESULT_OWNER_CHANGED_DURING_PREFLIGHT_READ")
    if draft_again != current_draft:
        _fail("WORK_DRAFT_CHANGED_DURING_PREFLIGHT_READ")
    if slot_again != slot:
        _fail("CHAPTER_SLOT_CHANGED_DURING_PREFLIGHT_READ")

    payload = {
        "status": "PREFLIGHT_READY",
        "closeout_action": copy.deepcopy(normalized),
        "check_result_source": {
            "check_result_ref": stored["result"]["check_result_ref"],
            "result_sha256": stored["result_sha256"],
            "version": stored["version"],
            "sha256": stored["sha256"],
        },
        "result": "completed_result_referenced",
        "handover_effect": "none",
        "chapter_close_effect": "none",
        "truth_effect": "none",
    }
    _assert_output_is_preflight(payload)
    return payload


__all__ = [
    "WritingCloseoutWorkspaceError",
    "prepare_full_check_preflight",
]
