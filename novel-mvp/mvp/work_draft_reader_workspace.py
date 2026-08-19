"""AuthorWorkspace 当前工作稿的一键只读视图。

本模块只组合现役 ``read_current_work_draft``。它不保存、不编辑、不交棒，
也不把 current 工作稿升级成 C1、冻结书稿或事实真值。
"""

from __future__ import annotations

import copy
from typing import Any, NoReturn

from . import work_draft_workspace
from .workspace import AuthorWorkspace


VIEW_IDENTITY = {
    "name": "AUTHOR_WORKSPACE_CURRENT_DRAFT_VIEW",
    "version": "v1",
    "projection_only": True,
}
READ_RESULT_KEYS = {"status", "draft_workspace", "current_work_draft"}
WARNING = "这是可编辑工作稿，不是C1章节、未冻结、未交棒、未进入事实真值。"


class WorkDraftReaderWorkspaceError(RuntimeError):
    """双读不稳定，或现役工作稿读回结果形状不一致。"""


def _fail(code: str) -> NoReturn:
    raise WorkDraftReaderWorkspaceError(code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _validated_result(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != READ_RESULT_KEYS:
        _fail("WORK_DRAFT_READ_RESULT_INVALID")
    status = value.get("status")
    if status == "EMPTY":
        if value["draft_workspace"] is not None or value["current_work_draft"] is not None:
            _fail("WORK_DRAFT_EMPTY_RESULT_INVALID")
        return copy.deepcopy(value)
    if (
        status != "READY"
        or not isinstance(value.get("draft_workspace"), dict)
        or set(value["draft_workspace"]) != {"version", "sha256"}
        or not isinstance(value.get("current_work_draft"), dict)
    ):
        _fail("WORK_DRAFT_READY_RESULT_INVALID")
    return copy.deepcopy(value)


def _empty_view() -> dict[str, Any]:
    text = (
        "【暂无当前工作稿】\n"
        "状态：EMPTY\n"
        "没有可显示的 current 工作稿；本次未生成、编辑或保存正文。\n"
    )
    markdown = (
        "# 暂无当前工作稿\n\n"
        "状态：`EMPTY`\n\n"
        "没有可显示的 current 工作稿；本次未生成、编辑或保存正文。\n"
    )
    return {
        "status": "EMPTY",
        "encoding": "UTF-8",
        "view_identity": copy.deepcopy(VIEW_IDENTITY),
        "draft_workspace": None,
        "draft_identity": None,
        "author_text": None,
        "markdown": markdown,
        "text": text,
    }


def _markdown_fence(text: str) -> str:
    fence = "```"
    while fence in text:
        fence += "`"
    return fence


def _draft_identity(draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract": draft["contract"],
        "version": draft["version"],
        "state": draft["state"],
        "slot_ref": draft["slot_ref"],
        "source_outline_ref": draft["source_outline_ref"],
        "work_ref": draft["work_ref"],
        "work_rev": draft["work_rev"],
        "entry_mode": draft["entry_mode"],
        "text_sha256": draft["text_sha256"],
    }


def _render_text(draft: dict[str, Any]) -> str:
    return (
        "【当前可编辑工作稿】\n"
        f"⚠️ {WARNING}\n"
        f"章槽：{draft['slot_ref']}\n"
        f"来源大纲：{draft['source_outline_ref']}\n"
        f"工作稿：{draft['work_ref']} / revision {draft['work_rev']}\n"
        f"录入方式：{draft['entry_mode']}\n"
        f"正文 SHA：{draft['text_sha256']}\n"
        "\n【作者原文开始】\n"
        f"{draft['text']}"
        "\n【作者原文结束】\n"
    )


def _render_markdown(draft: dict[str, Any]) -> str:
    fence = _markdown_fence(draft["text"])
    return (
        "# 当前可编辑工作稿\n\n"
        f"> ⚠️ {WARNING}\n\n"
        f"- 章槽：`{draft['slot_ref']}`\n"
        f"- 来源大纲：`{draft['source_outline_ref']}`\n"
        f"- 工作稿：`{draft['work_ref']}` / revision `{draft['work_rev']}`\n"
        f"- 录入方式：`{draft['entry_mode']}`\n"
        f"- 正文 SHA：`{draft['text_sha256']}`\n\n"
        "## 作者原文\n\n"
        f"{fence}\n{draft['text']}\n{fence}\n"
    )


def read_current_draft_view(workspace: AuthorWorkspace) -> dict[str, Any]:
    """连续读两次 current 工作稿，只展示第二份稳定副本。"""

    handle = _require_workspace(workspace)
    first = _validated_result(
        work_draft_workspace.read_current_work_draft(handle)
    )
    second = _validated_result(
        work_draft_workspace.read_current_work_draft(handle)
    )
    if first != second:
        _fail("WORK_DRAFT_CHANGED_DURING_VIEW_READ")
    if second["status"] == "EMPTY":
        return _empty_view()
    draft_workspace = copy.deepcopy(second["draft_workspace"])
    draft = copy.deepcopy(second["current_work_draft"])
    return {
        "status": "READY",
        "encoding": "UTF-8",
        "view_identity": copy.deepcopy(VIEW_IDENTITY),
        "draft_workspace": draft_workspace,
        "draft_identity": _draft_identity(draft),
        "author_text": draft["text"],
        "markdown": _render_markdown(draft),
        "text": _render_text(draft),
    }


__all__ = ["WorkDraftReaderWorkspaceError", "read_current_draft_view"]
