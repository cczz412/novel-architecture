"""AuthorWorkspace 中当前章事实稿交棒请求的作者只读页。

这里只组合现役 ``prepare_pending_handover_consumption``。它不分配章节号或
revision，不写 C11、章节账、事实账、规划账，也不把待处理请求说成交棒成功。
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, NoReturn

from . import (
    chapter_fact_draft_tool,
    chapter_fact_handover_tool,
    chapter_fact_handover_workspace,
)
from .workspace import OPERATION_ID_RE, SHA256_RE, AuthorWorkspace


VIEW_IDENTITY = {
    "name": "AUTHOR_WORKSPACE_CURRENT_CHAPTER_FACT_HANDOVER_VIEW",
    "version": "v1",
    "projection_only": True,
}
PREFLIGHT_KEYS = {
    "status",
    "operation_id",
    "request",
    "requests_snapshot",
    "current_plan_snapshot",
    "effects",
}
REQUEST_KEYS = {
    "operation_id",
    "request_sha256",
    "workspace_binding",
    "chapter_fact_draft",
    "handover_action",
}
WORKSPACE_BINDING_KEYS = {"author_id", "project_id"}
ZERO_EFFECTS = {
    "c11": "none",
    "chapter_ledger": "none",
    "facts": "none",
    "plan": "none",
}


class ChapterFactHandoverReaderWorkspaceError(RuntimeError):
    """待处理请求不能组成稳定、可信的作者页面。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise ChapterFactHandoverReaderWorkspaceError(code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _canonical_bytes(value: object) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ChapterFactHandoverReaderWorkspaceError(
            "VIEW_VALUE_NOT_CANONICAL_JSON"
        ) from exc
    return (text + "\n").encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _snapshot(value: object, *, label: str) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "sha256"}
        or isinstance(value.get("version"), bool)
        or not isinstance(value.get("version"), int)
        or value["version"] < 1
        or not isinstance(value.get("sha256"), str)
        or SHA256_RE.fullmatch(value["sha256"]) is None
    ):
        _fail(f"{label}_SNAPSHOT_INVALID")
    return {"version": value["version"], "sha256": value["sha256"]}


def _validated_request(
    workspace: AuthorWorkspace,
    operation_id: str,
    value: object,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    if (
        not isinstance(value, dict)
        or set(value) != REQUEST_KEYS
        or value.get("operation_id") != operation_id
        or not isinstance(value.get("workspace_binding"), dict)
        or set(value["workspace_binding"]) != WORKSPACE_BINDING_KEYS
        or value["workspace_binding"]
        != {
            "author_id": workspace.author_id,
            "project_id": workspace.project_id,
        }
    ):
        _fail("PENDING_HANDOVER_REQUEST_INVALID")
    try:
        draft = chapter_fact_draft_tool.validate_result(
            value["chapter_fact_draft"]
        )
        action = chapter_fact_handover_tool.validate_result(
            value["handover_action"]
        )
    except (
        chapter_fact_draft_tool.ChapterFactDraftToolError,
        chapter_fact_handover_tool.ChapterFactHandoverToolError,
    ) as exc:
        raise ChapterFactHandoverReaderWorkspaceError(
            "PENDING_HANDOVER_OBJECT_INVALID"
        ) from exc
    source = action["source_prototype"]
    if (
        action["operation_id"] != operation_id
        or source["identity"] != draft["identity"]
        or source["operation_id"] != draft["operation_id"]
        or source["prototype_sha256"] != draft["prototype_sha256"]
        or action["slot"] != draft["slot"]
        or action["planning_source"] != draft["planning_source"]
    ):
        _fail("PENDING_HANDOVER_OBJECT_MISMATCH")
    request_core = {
        "operation_id": operation_id,
        "workspace_binding": copy.deepcopy(value["workspace_binding"]),
        "chapter_fact_draft": draft,
        "handover_action": action,
    }
    request_sha = value.get("request_sha256")
    if (
        not isinstance(request_sha, str)
        or SHA256_RE.fullmatch(request_sha) is None
        or _sha256(request_core) != request_sha
    ):
        _fail("PENDING_HANDOVER_REQUEST_SHA_MISMATCH")
    return draft, action, request_sha


def _validated_preflight(
    workspace: AuthorWorkspace,
    operation_id: str,
    value: object,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], str]:
    if (
        not isinstance(value, dict)
        or set(value) != PREFLIGHT_KEYS
        or value.get("status")
        != chapter_fact_handover_workspace.PREFLIGHT_STATUS
        or value.get("operation_id") != operation_id
        or value.get("effects") != ZERO_EFFECTS
    ):
        _fail("PENDING_HANDOVER_PREFLIGHT_INVALID")
    draft, action, request_sha = _validated_request(
        workspace,
        operation_id,
        value["request"],
    )
    requests_snapshot = _snapshot(value["requests_snapshot"], label="REQUESTS")
    current_plan_snapshot = _snapshot(
        value["current_plan_snapshot"],
        label="CURRENT_PLAN",
    )
    planning = draft["planning_source"]
    if current_plan_snapshot != {
        "version": planning["source_plan_version"],
        "sha256": planning["source_plan_sha256"],
    }:
        _fail("PENDING_HANDOVER_CURRENT_PLAN_IDENTITY_MISMATCH")
    return (
        draft,
        action,
        requests_snapshot,
        current_plan_snapshot,
        request_sha,
    )


def _indented_block(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(f"    {line}" for line in normalized.split("\n"))


def _labeled_block(lines: list[str], label: str, value: str) -> None:
    lines.extend([f"- {label}：", "", _indented_block(value)])


def _render_markdown(
    operation_id: str,
    draft: dict[str, Any],
    action: dict[str, Any],
    requests_snapshot: dict[str, Any],
    current_plan_snapshot: dict[str, Any],
    request_sha: str,
) -> str:
    slot = draft["slot"]
    planning = draft["planning_source"]
    lines = [
        "# 当前章事实稿交棒请求｜仍待正式接收",
        "",
        "> 这份请求仍绑定当前规划，但尚未写入章节账或事实账。",
        "> 本页只复核作者已经提交的内容，不代表交棒完成，也不会开放下一章。",
        "",
        "## 作者确认标题",
        "",
        _indented_block(action["author_confirmed_title"]),
        "",
        "## 有序事实句与写法批注",
    ]
    for index, entry in enumerate(draft["entries"], start=1):
        lines.extend(["", f"### {index}. 事实句", "", _indented_block(entry["fact_text"])])
        lines.extend(["", "**写法批注**", ""])
        if entry["writing_note"]:
            lines.append(_indented_block(entry["writing_note"]))
        else:
            lines.append("    （无）")
    lines.extend(["", "## 当前绑定", ""])
    _labeled_block(lines, "交棒请求操作号", operation_id)
    _labeled_block(lines, "章槽", slot["slot_ref"])
    lines.extend(["", f"- 章槽修订：`{slot['slot_rev']}`"])
    _labeled_block(lines, "章纲来源", slot["source_outline_ref"])
    lines.extend(
        [
            "",
            f"- 当前规划版本：`{current_plan_snapshot['version']}`",
            f"- 当前规划 SHA256：`{current_plan_snapshot['sha256']}`",
            f"- 章事实稿来源规划版本：`{planning['source_plan_version']}`",
            f"- 章事实稿来源规划 SHA256：`{planning['source_plan_sha256']}`",
            f"- 规划提交水位：`{planning['source_commit_seq']}`",
            f"- 待处理区版本：`{requests_snapshot['version']}`",
            f"- 待处理区 SHA256：`{requests_snapshot['sha256']}`",
            f"- 章事实稿原型 SHA256：`{draft['prototype_sha256']}`",
            f"- 交棒动作 SHA256：`{action['action_sha256']}`",
            f"- 完整请求 SHA256：`{request_sha}`",
            "",
            "## 当前结果",
            "",
            "- 状态：仍待正式接收",
            "- C11 写入：0",
            "- 章节账写入：0",
            "- 事实账写入：0",
            "- 规划账写入：0",
            "- 章节号分配：0",
            "- 章节版本号分配：0",
            "",
        ]
    )
    return "\n".join(lines)


def read_current_pending_handover_view(
    workspace: AuthorWorkspace,
    operation_id: str,
) -> dict[str, Any]:
    """读出仍绑定当前规划的待处理章事实稿请求，不产生任何写入。"""
    handle = _require_workspace(workspace)
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        _fail("HANDOVER_OPERATION_ID_INVALID")
    try:
        preflight = chapter_fact_handover_workspace.prepare_pending_handover_consumption(
            handle,
            operation_id,
        )
    except chapter_fact_handover_workspace.ChapterFactHandoverWorkspaceError as exc:
        raise ChapterFactHandoverReaderWorkspaceError(
            f"PENDING_HANDOVER_PREFLIGHT_REJECTED:{exc.code}"
        ) from exc
    (
        draft,
        action,
        requests_snapshot,
        current_plan_snapshot,
        request_sha,
    ) = _validated_preflight(handle, operation_id, preflight)
    return {
        "status": chapter_fact_handover_workspace.PREFLIGHT_STATUS,
        "encoding": "UTF-8",
        "view_identity": copy.deepcopy(VIEW_IDENTITY),
        "operation_id": operation_id,
        "requests_snapshot": requests_snapshot,
        "current_plan_snapshot": current_plan_snapshot,
        "request_sha256": request_sha,
        "draft_identity": {
            "identity": draft["identity"],
            "operation_id": draft["operation_id"],
            "prototype_sha256": draft["prototype_sha256"],
            "entry_count": len(draft["entries"]),
        },
        "action_identity": {
            "identity": action["identity"],
            "operation_id": action["operation_id"],
            "action_sha256": action["action_sha256"],
        },
        "markdown": _render_markdown(
            operation_id,
            draft,
            action,
            requests_snapshot,
            current_plan_snapshot,
            request_sha,
        ),
    }


__all__ = [
    "ChapterFactHandoverReaderWorkspaceError",
    "read_current_pending_handover_view",
]
