"""章事实稿交棒请求的 AuthorWorkspace 待处理区。

这里保存完整、已经机械校验过的章事实稿 prototype 与作者交棒动作 prototype。
它只说明“请求已经安全留存，尚未应用”；不分配章节或 revision，不写 C10、
C11、C1、事实账或规划账，也不产生 current 指针。
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, NoReturn

from . import (
    chapter_fact_draft_tool,
    chapter_fact_handover_tool,
    chapter_slot_snapshot_tool,
    plan_workspace,
    planstore,
)
from .workspace import (
    OPERATION_ID_RE,
    AuthorWorkspace,
    OperationConflictError,
    VersionConflictError,
)


LOGICAL_KEY = "chapter_fact_handover_requests"
STORE_SCHEMA = "chapter-fact-handover-request-store-v1"
PREFLIGHT_STATUS = "CURRENT_NOT_APPLIED"
STORE_KEYS = {"schema_version", "requests"}
REQUEST_KEYS = {
    "operation_id",
    "request_sha256",
    "workspace_binding",
    "chapter_fact_draft",
    "handover_action",
}
WORKSPACE_BINDING_KEYS = {"author_id", "project_id"}
WORKSPACE_ENTRY_KEYS = {"logical_key", "version", "sha256", "payload"}


class ChapterFactHandoverWorkspaceError(RuntimeError):
    """待处理请求不满足作者工作区、来源水位或对象完整性边界。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise ChapterFactHandoverWorkspaceError(code)


def _workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ChapterFactHandoverWorkspaceError(
            "VALUE_NOT_CANONICAL_JSON"
        ) from exc
    return (text + "\n").encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _binding(workspace: AuthorWorkspace) -> dict[str, str]:
    return {
        "author_id": workspace.author_id,
        "project_id": workspace.project_id,
    }


def _validated_pair(
    chapter_fact_draft: object,
    handover_action: object,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        draft = chapter_fact_draft_tool.validate_result(chapter_fact_draft)
    except chapter_fact_draft_tool.ChapterFactDraftToolError as exc:
        raise ChapterFactHandoverWorkspaceError(
            f"CHAPTER_FACT_DRAFT_INVALID:{exc.code}"
        ) from exc
    try:
        action = chapter_fact_handover_tool.validate_result(handover_action)
    except chapter_fact_handover_tool.ChapterFactHandoverToolError as exc:
        raise ChapterFactHandoverWorkspaceError(
            f"CHAPTER_FACT_HANDOVER_ACTION_INVALID:{exc.code}"
        ) from exc

    source = action["source_prototype"]
    if (
        source["identity"] != draft["identity"]
        or source["operation_id"] != draft["operation_id"]
        or source["prototype_sha256"] != draft["prototype_sha256"]
        or action["slot"] != draft["slot"]
        or action["planning_source"] != draft["planning_source"]
    ):
        _fail("HANDOVER_ACTION_DRAFT_MISMATCH")
    return draft, action


def _request_record(
    workspace: AuthorWorkspace,
    chapter_fact_draft: object,
    handover_action: object,
) -> dict[str, Any]:
    draft, action = _validated_pair(chapter_fact_draft, handover_action)
    request_core = {
        "operation_id": action["operation_id"],
        "workspace_binding": _binding(workspace),
        "chapter_fact_draft": draft,
        "handover_action": action,
    }
    return {
        **request_core,
        "request_sha256": _sha256(request_core),
    }


def _validated_request(
    workspace: AuthorWorkspace,
    operation_id: object,
    value: object,
) -> dict[str, Any]:
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
        or not isinstance(value, dict)
        or set(value) != REQUEST_KEYS
        or value.get("operation_id") != operation_id
        or not isinstance(value.get("workspace_binding"), dict)
        or set(value["workspace_binding"]) != WORKSPACE_BINDING_KEYS
        or value["workspace_binding"] != _binding(workspace)
    ):
        _fail("SAVED_HANDOVER_REQUEST_INVALID")
    draft, action = _validated_pair(
        value["chapter_fact_draft"],
        value["handover_action"],
    )
    if action["operation_id"] != operation_id:
        _fail("SAVED_HANDOVER_REQUEST_OPERATION_MISMATCH")
    core = {
        "operation_id": operation_id,
        "workspace_binding": copy.deepcopy(value["workspace_binding"]),
        "chapter_fact_draft": draft,
        "handover_action": action,
    }
    if value.get("request_sha256") != _sha256(core):
        _fail("SAVED_HANDOVER_REQUEST_SHA_MISMATCH")
    return {**core, "request_sha256": value["request_sha256"]}


def _empty_store() -> dict[str, Any]:
    return {"schema_version": STORE_SCHEMA, "requests": {}}


def _validated_store(
    workspace: AuthorWorkspace,
    value: object,
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != STORE_KEYS
        or value.get("schema_version") != STORE_SCHEMA
        or not isinstance(value.get("requests"), dict)
    ):
        _fail("HANDOVER_REQUEST_STORE_INVALID")
    requests: dict[str, dict[str, Any]] = {}
    for operation_id, request in value["requests"].items():
        requests[operation_id] = _validated_request(
            workspace,
            operation_id,
            request,
        )
    return {"schema_version": STORE_SCHEMA, "requests": requests}


def _state(workspace: AuthorWorkspace) -> dict[str, Any]:
    entry = workspace.read(LOGICAL_KEY)
    if entry is None:
        return {
            "logical_key": LOGICAL_KEY,
            "version": 0,
            "sha256": None,
            "payload": _empty_store(),
        }
    if (
        not isinstance(entry, dict)
        or set(entry) != WORKSPACE_ENTRY_KEYS
        or entry.get("logical_key") != LOGICAL_KEY
        or isinstance(entry.get("version"), bool)
        or not isinstance(entry.get("version"), int)
        or entry["version"] < 1
        or not isinstance(entry.get("sha256"), str)
    ):
        _fail("HANDOVER_REQUEST_WORKSPACE_STATE_INVALID")
    store = _validated_store(workspace, entry.get("payload"))
    if _sha256(store) != entry["sha256"]:
        _fail("HANDOVER_REQUEST_WORKSPACE_SHA_MISMATCH")
    return {**entry, "payload": store}


def _current_plan_watermark(
    workspace: AuthorWorkspace,
    draft: dict[str, Any],
) -> dict[str, Any]:
    try:
        current = plan_workspace.read_plan(workspace)
    except (
        plan_workspace.PlanWorkspaceError,
        planstore.PlanstoreError,
        ValueError,
        TypeError,
        KeyError,
    ) as exc:
        raise ChapterFactHandoverWorkspaceError("CURRENT_PLAN_INVALID") from exc
    if current is None:
        _fail("CURRENT_PLAN_REQUIRED")
    planning = draft["planning_source"]
    if (
        current["version"] != planning["source_plan_version"]
        or current["sha256"] != planning["source_plan_sha256"]
    ):
        _fail("CHAPTER_FACT_DRAFT_PLAN_NOT_CURRENT")
    try:
        snapshot = chapter_slot_snapshot_tool.execute(
            {
                "plan": current["plan"],
                "slot_ref": draft["slot"]["slot_ref"],
                "source_plan_version": current["version"],
                "source_plan_sha256": current["sha256"],
            }
        )
    except chapter_slot_snapshot_tool.ChapterSlotSnapshotError as exc:
        raise ChapterFactHandoverWorkspaceError(
            "CURRENT_CHAPTER_SLOT_SNAPSHOT_INVALID"
        ) from exc
    if (
        _sha256(snapshot) != planning["chapter_slot_snapshot_sha256"]
        or snapshot.get("slot_rev") != draft["slot"]["slot_rev"]
        or snapshot.get("outline_checkpoint", {}).get("source_commit_seq")
        != planning["source_commit_seq"]
    ):
        _fail("CHAPTER_FACT_DRAFT_SLOT_NOT_CURRENT")
    return {"version": current["version"], "sha256": current["sha256"]}


def _result(
    state: dict[str, Any],
    operation_id: str,
    *,
    replayed: bool,
) -> dict[str, Any]:
    request = state["payload"]["requests"].get(operation_id)
    if request is None:
        _fail("SAVED_HANDOVER_REQUEST_NOT_FOUND_AFTER_COMMIT")
    return {
        "status": chapter_fact_handover_tool.STATUS,
        "replayed": replayed,
        "operation_id": operation_id,
        "requests_snapshot": {
            "version": state["version"],
            "sha256": state["sha256"],
        },
        "request": copy.deepcopy(request),
    }


def save_pending_handover_request(
    workspace: AuthorWorkspace,
    chapter_fact_draft: dict[str, Any],
    handover_action: dict[str, Any],
    expected_requests_version: int,
) -> dict[str, Any]:
    """追加一条作者交棒请求；提交后仍是未应用状态。"""
    handle = _workspace(workspace)
    if (
        isinstance(expected_requests_version, bool)
        or not isinstance(expected_requests_version, int)
        or expected_requests_version < 0
    ):
        _fail("EXPECTED_REQUESTS_VERSION_INVALID")
    candidate = _request_record(handle, chapter_fact_draft, handover_action)
    operation_id = candidate["operation_id"]
    before = _state(handle)
    existing = before["payload"]["requests"].get(operation_id)
    if existing is not None:
        if existing["request_sha256"] != candidate["request_sha256"]:
            raise OperationConflictError(
                "OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST"
            )
        return _result(before, operation_id, replayed=True)
    if expected_requests_version != before["version"]:
        raise VersionConflictError("VERSION_CONFLICT")
    first_plan = _current_plan_watermark(
        handle,
        candidate["chapter_fact_draft"],
    )

    store = copy.deepcopy(before["payload"])
    store["requests"][operation_id] = candidate
    store = _validated_store(handle, store)
    second_plan = _current_plan_watermark(
        handle,
        store["requests"][operation_id]["chapter_fact_draft"],
    )
    if second_plan != first_plan:
        _fail("CURRENT_PLAN_CHANGED_BEFORE_COMMIT")
    handle.commit_guarded(
        operation_id,
        {LOGICAL_KEY: store},
        {
            LOGICAL_KEY: {
                "version": before["version"],
                "sha256": before["sha256"],
            }
        },
        {"plan": first_plan},
    )
    after = _state(handle)
    if after["version"] != before["version"] + 1:
        _fail("HANDOVER_REQUEST_COMMIT_VERSION_MISMATCH")
    return _result(after, operation_id, replayed=False)


def read_pending_handover_request(
    workspace: AuthorWorkspace,
    operation_id: str,
) -> dict[str, Any] | None:
    """按交棒操作号读回完整请求；不创建目录，也不应用请求。"""
    handle = _workspace(workspace)
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        _fail("HANDOVER_OPERATION_ID_INVALID")
    state = _state(handle)
    if operation_id not in state["payload"]["requests"]:
        return None
    return _result(state, operation_id, replayed=False)


def prepare_pending_handover_consumption(
    workspace: AuthorWorkspace,
    operation_id: str,
) -> dict[str, Any]:
    """复核一条待处理请求仍绑定当前规划；只读，不应用交棒。"""
    handle = _workspace(workspace)
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        _fail("HANDOVER_OPERATION_ID_INVALID")

    first = _state(handle)
    first_request = first["payload"]["requests"].get(operation_id)
    if first_request is None:
        _fail("PENDING_HANDOVER_REQUEST_NOT_FOUND")
    first_plan = _current_plan_watermark(
        handle,
        first_request["chapter_fact_draft"],
    )

    second = _state(handle)
    if (
        second["version"] != first["version"]
        or second["sha256"] != first["sha256"]
    ):
        _fail("HANDOVER_REQUEST_STORE_CHANGED_DURING_PREFLIGHT")
    second_request = second["payload"]["requests"].get(operation_id)
    if (
        second_request is None
        or second_request["request_sha256"] != first_request["request_sha256"]
    ):
        _fail("HANDOVER_REQUEST_CHANGED_DURING_PREFLIGHT")
    try:
        second_plan = _current_plan_watermark(
            handle,
            second_request["chapter_fact_draft"],
        )
    except ChapterFactHandoverWorkspaceError as exc:
        raise ChapterFactHandoverWorkspaceError(
            "CURRENT_PLAN_CHANGED_DURING_PREFLIGHT"
        ) from exc
    if second_plan != first_plan:
        _fail("CURRENT_PLAN_CHANGED_DURING_PREFLIGHT")

    return {
        "status": PREFLIGHT_STATUS,
        "operation_id": operation_id,
        "request": copy.deepcopy(second_request),
        "requests_snapshot": {
            "version": second["version"],
            "sha256": second["sha256"],
        },
        "current_plan_snapshot": copy.deepcopy(second_plan),
        "effects": {
            "c11": "none",
            "chapter_ledger": "none",
            "facts": "none",
            "plan": "none",
        },
    }


__all__ = [
    "ChapterFactHandoverWorkspaceError",
    "prepare_pending_handover_consumption",
    "read_pending_handover_request",
    "save_pending_handover_request",
]
