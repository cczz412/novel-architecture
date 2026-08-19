"""AuthorWorkspace 到 M6 查询＋引文上下文的只读交接层。

本模块只认已绑定作者与项目的 ``AuthorWorkspace`` 句柄。它不保存查询
结果，不新增逻辑键，不重定义 M6 检索或窗口语义。
"""

from __future__ import annotations

import copy
from typing import Any

from . import ask_context_tool, ask_tool, ask_workspace, chapter_workspace, factstore
from .workspace import AuthorWorkspace


LOGICAL_KEYS = ("facts", "chapter_index", "chapters")


class AskContextWorkspaceError(ask_context_tool.AskContextError):
    """三份工作区快照不同源、不闭合或读途变化时拒绝。"""


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        raise AskContextWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _read_list_snapshot(workspace: AuthorWorkspace, logical_key: str) -> dict[str, Any]:
    entry = workspace.read(logical_key)
    if entry is None:
        return {"version": 0, "sha256": None, "payload": []}
    if (
        not isinstance(entry, dict)
        or entry.get("logical_key") != logical_key
        or not isinstance(entry.get("version"), int)
        or isinstance(entry.get("version"), bool)
        or entry["version"] < 1
        or not isinstance(entry.get("sha256"), str)
        or ask_tool.SHA256_RE.fullmatch(entry["sha256"]) is None
        or not isinstance(entry.get("payload"), list)
    ):
        raise AskContextWorkspaceError(f"{logical_key.upper()}_WORKSPACE_ENTRY_INVALID")
    return {
        "version": entry["version"],
        "sha256": entry["sha256"],
        "payload": copy.deepcopy(entry["payload"]),
    }


def _read_three(workspace: AuthorWorkspace) -> dict[str, dict[str, Any]]:
    return {key: _read_list_snapshot(workspace, key) for key in LOGICAL_KEYS}


def _watermark(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {"version": snapshot["version"], "sha256": snapshot["sha256"]}


def _validate_closed_snapshots(snapshots: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    raw_facts = snapshots["facts"]["payload"]
    raw_index = snapshots["chapter_index"]["payload"]
    raw_chapters = snapshots["chapters"]["payload"]
    try:
        facts = factstore.validate_c4_v1_snapshot(raw_facts)
    except factstore.FactstoreError as exc:
        raise AskContextWorkspaceError(f"FACTS_SNAPSHOT_INVALID:{exc}") from exc

    if not raw_chapters and not raw_index:
        if facts:
            raise AskContextWorkspaceError("FACTS_PRESENT_WITHOUT_CURRENT_CHAPTERS")
        return []
    try:
        chapters, current_refs = chapter_workspace._validated_batch(
            raw_chapters,
            raw_index,
        )
    except chapter_workspace.ChapterWorkspaceError as exc:
        raise AskContextWorkspaceError(f"CHAPTER_SNAPSHOTS_INVALID:{exc}") from exc
    if snapshots["chapters"]["version"] != snapshots["chapter_index"]["version"]:
        raise AskContextWorkspaceError("CHAPTERS_AND_INDEX_VERSION_DIVERGED")

    chapters_by_id = {chapter["id"]: chapter for chapter in chapters}
    refs_by_id = {ref["chapter_id"]: ref for ref in current_refs}
    for fact in facts:
        chapter_id = fact["chapter_id"]
        chapter = chapters_by_id.get(chapter_id)
        current_ref = refs_by_id.get(chapter_id)
        if chapter is None or current_ref is None:
            raise AskContextWorkspaceError(f"FACT_CHAPTER_MISSING:{fact['id']}:{chapter_id}")
        if fact["chapter_revision_ref"] != current_ref:
            raise AskContextWorkspaceError(f"FACT_NOT_CURRENT_REVISION:{fact['id']}")
        if fact["anchor_state"] != "VERIFIED":
            continue
        anchor = fact["anchor_ref"]
        start, end = anchor["start"], anchor["end"]
        if end > len(chapter["text"]) or chapter["text"][start:end] != fact["quote"]:
            raise AskContextWorkspaceError(f"FACT_ANCHOR_NOT_IN_CURRENT_TEXT:{fact['id']}")
    return chapters


def _same_watermarks(
    left: dict[str, dict[str, Any]],
    right: dict[str, dict[str, Any]],
) -> bool:
    return all(_watermark(left[key]) == _watermark(right[key]) for key in LOGICAL_KEYS)


def execute(
    workspace: AuthorWorkspace,
    query: str,
    before_chars: int,
    after_chars: int,
) -> dict[str, Any]:
    """同一句柄下串起当前事实查询与机械引文上下文。"""
    handle = _require_workspace(workspace)
    before = _read_three(handle)
    chapters = _validate_closed_snapshots(before)

    query_result = ask_workspace.execute(handle, query)
    if (
        query_result["facts_snapshot"] != _watermark(before["facts"])
        or query_result["chapter_index_snapshot"] != _watermark(before["chapter_index"])
    ):
        raise AskContextWorkspaceError("WORKSPACE_SNAPSHOT_CHANGED_DURING_QUERY")
    enriched = ask_context_tool.execute(
        {
            "m6_result": query_result["m6"],
            "current_chapters": chapters,
            "before_chars": before_chars,
            "after_chars": after_chars,
        }
    )

    after = _read_three(handle)
    _validate_closed_snapshots(after)
    if not _same_watermarks(before, after):
        raise AskContextWorkspaceError("WORKSPACE_SNAPSHOT_CHANGED_DURING_CONTEXT_EXPANSION")
    return {
        "facts_snapshot": _watermark(before["facts"]),
        "chapter_index_snapshot": _watermark(before["chapter_index"]),
        "chapters_snapshot": _watermark(before["chapters"]),
        "m6": enriched,
    }


__all__ = ["AskContextWorkspaceError", "execute"]
