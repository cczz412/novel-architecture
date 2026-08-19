"""AuthorWorkspace 到“读者截点查询＋证据上下文”的只读组合入口。

本模块只组合现役 reader-scope 工作区入口和 context 对象核心。未来章节
正文不会交给上下文核心；查询结果不保存，也不产生事实或权限判断。
"""

from __future__ import annotations

import copy
from typing import Any

from . import (
    ask_context_tool,
    ask_context_workspace,
    ask_reader_scope_workspace,
)
from .workspace import AuthorWorkspace


M6_RESULT_KEYS = ("query", "matches", "evidence", "excluded_counts")


class AskReaderContextWorkspaceError(ask_context_tool.AskContextError):
    """读者截点、上下文或三份工作区水位不能闭合时拒绝。"""


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        raise AskReaderContextWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _watermark(snapshot: dict[str, Any]) -> dict[str, Any]:
    return ask_context_workspace._watermark(snapshot)


def _reader_watermarks_match(
    reader_result: dict[str, Any],
    snapshots: dict[str, dict[str, Any]],
) -> bool:
    return (
        reader_result.get("facts_snapshot") == _watermark(snapshots["facts"])
        and reader_result.get("chapter_index_snapshot")
        == _watermark(snapshots["chapter_index"])
    )


def _visible_chapters(
    chapters: list[dict[str, Any]],
    reader_m6: dict[str, Any],
    as_of_chapter_id: str,
) -> list[dict[str, Any]]:
    scope = reader_m6.get("reader_scope")
    if not isinstance(scope, dict):
        raise AskReaderContextWorkspaceError("READER_SCOPE_RESULT_INVALID")
    visible_count = scope.get("visible_chapter_count")
    if (
        not isinstance(visible_count, int)
        or isinstance(visible_count, bool)
        or visible_count < 1
        or visible_count > len(chapters)
        or scope.get("as_of_chapter_id") != as_of_chapter_id
    ):
        raise AskReaderContextWorkspaceError("READER_SCOPE_RESULT_INVALID")
    visible = copy.deepcopy(chapters[:visible_count])
    if not visible or visible[-1].get("id") != as_of_chapter_id:
        raise AskReaderContextWorkspaceError("READER_SCOPE_CHAPTER_PREFIX_MISMATCH")
    return visible


def _visible_revision_refs(
    chapter_index_snapshot: dict[str, Any],
    reader_m6: dict[str, Any],
    as_of_chapter_id: str,
) -> list[dict[str, Any]]:
    scope = reader_m6["reader_scope"]
    visible_count = scope["visible_chapter_count"]
    current_refs = chapter_index_snapshot["payload"]
    visible_refs = copy.deepcopy(current_refs[:visible_count])
    if (
        len(visible_refs) != visible_count
        or not visible_refs
        or visible_refs[-1].get("chapter_id") != as_of_chapter_id
    ):
        raise AskReaderContextWorkspaceError("READER_SCOPE_REVISION_PREFIX_MISMATCH")
    return visible_refs


def execute(
    workspace: AuthorWorkspace,
    query: str,
    as_of_chapter_id: str,
    before_chars: int,
    after_chars: int,
) -> dict[str, Any]:
    """在同一快照上完成防剧透查询与命中证据的机械上下文展开。"""
    handle = _require_workspace(workspace)
    before = ask_context_workspace._read_three(handle)
    try:
        chapters = ask_context_workspace._validate_closed_snapshots(before)
    except ask_context_workspace.AskContextWorkspaceError as exc:
        raise AskReaderContextWorkspaceError(
            f"WORKSPACE_SNAPSHOT_INVALID:{exc}"
        ) from exc

    try:
        reader_result = ask_reader_scope_workspace.execute(
            handle,
            query,
            as_of_chapter_id,
        )
    except ask_reader_scope_workspace.ReaderScopeWorkspaceError as exc:
        raise AskReaderContextWorkspaceError(
            f"READER_SCOPE_QUERY_REJECTED:{exc}"
        ) from exc
    if not _reader_watermarks_match(reader_result, before):
        raise AskReaderContextWorkspaceError(
            "WORKSPACE_SNAPSHOT_CHANGED_DURING_READER_QUERY"
        )

    reader_m6 = reader_result.get("m6")
    if not isinstance(reader_m6, dict):
        raise AskReaderContextWorkspaceError("READER_SCOPE_RESULT_INVALID")
    visible_chapters = _visible_chapters(
        chapters,
        reader_m6,
        as_of_chapter_id,
    )
    visible_revision_refs = _visible_revision_refs(
        before["chapter_index"],
        reader_m6,
        as_of_chapter_id,
    )
    m6_result = {
        key: copy.deepcopy(reader_m6.get(key)) for key in M6_RESULT_KEYS
    }
    try:
        enriched = ask_context_tool.execute(
            {
                "m6_result": m6_result,
                "current_chapters": visible_chapters,
                "before_chars": before_chars,
                "after_chars": after_chars,
            }
        )
    except ask_context_tool.AskContextError as exc:
        raise AskReaderContextWorkspaceError(
            f"CONTEXT_EXPANSION_REJECTED:{exc}"
        ) from exc

    after = ask_context_workspace._read_three(handle)
    try:
        ask_context_workspace._validate_closed_snapshots(after)
    except ask_context_workspace.AskContextWorkspaceError as exc:
        raise AskReaderContextWorkspaceError(
            f"WORKSPACE_SNAPSHOT_INVALID_AFTER_QUERY:{exc}"
        ) from exc
    if not ask_context_workspace._same_watermarks(before, after):
        raise AskReaderContextWorkspaceError(
            "WORKSPACE_SNAPSHOT_CHANGED_DURING_CONTEXT_EXPANSION"
        )

    combined_m6 = copy.deepcopy(reader_m6)
    combined_m6.update(enriched)
    return {
        "facts_snapshot": _watermark(before["facts"]),
        "chapter_index_snapshot": _watermark(before["chapter_index"]),
        "chapters_snapshot": _watermark(before["chapters"]),
        "visible_chapter_revision_refs": visible_revision_refs,
        "m6": combined_m6,
    }


__all__ = ["AskReaderContextWorkspaceError", "execute"]
