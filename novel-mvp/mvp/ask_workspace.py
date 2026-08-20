"""AuthorWorkspace 到现役 M6 ``ask_tool`` 的只读适配层。

调用方只能交入已绑定作者与项目的 ``AuthorWorkspace`` 句柄。本模块
不认路径、作者 ID 或项目 ID，也不写任何 workspace 逻辑键。
"""

from __future__ import annotations

import copy
from typing import Any

from . import ask_tool
from .workspace import AuthorWorkspace


FACTS_LOGICAL_KEY = "facts"
CHAPTER_INDEX_LOGICAL_KEY = "chapter_index"


class AskWorkspaceError(ask_tool.AskToolError):
    """M6 工作区适配器拒绝了非句柄或损坏的读取结果。"""


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        raise AskWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
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
        raise AskWorkspaceError(f"{logical_key.upper()}_WORKSPACE_ENTRY_INVALID")
    return {
        "version": entry["version"],
        "sha256": entry["sha256"],
        "payload": copy.deepcopy(entry["payload"]),
    }


def _current_revision_refs(
    chapter_index: list[Any],
    facts: list[Any],
) -> list[dict[str, Any]]:
    if not chapter_index:
        if facts:
            raise AskWorkspaceError("CHAPTER_INDEX_REQUIRED_FOR_NONEMPTY_FACTS")
        return []
    indexed: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    for index, raw_ref in enumerate(chapter_index, start=1):
        if not ask_tool._valid_revision_ref(raw_ref):
            raise AskWorkspaceError(f"CHAPTER_INDEX_REVISION_REF_INVALID:{index}")
        chapter_id = raw_ref["chapter_id"]
        if chapter_id in indexed:
            raise AskWorkspaceError(f"CHAPTER_INDEX_REVISION_REF_DUPLICATE:{chapter_id}")
        clean = copy.deepcopy(raw_ref)
        indexed[chapter_id] = clean
        ordered.append(clean)

    for index, fact in enumerate(facts, start=1):
        if not isinstance(fact, dict):
            continue
        chapter_id = fact.get("chapter_id")
        if not isinstance(chapter_id, str) or not chapter_id:
            continue
        if chapter_id not in indexed:
            raise AskWorkspaceError(f"FACT_CHAPTER_NOT_IN_CURRENT_INDEX:{index}:{chapter_id}")
    return ordered


def _read_query_source(workspace: AuthorWorkspace) -> dict[str, Any]:
    facts_snapshot = _read_list_snapshot(workspace, FACTS_LOGICAL_KEY)
    chapter_index_snapshot = _read_list_snapshot(
        workspace, CHAPTER_INDEX_LOGICAL_KEY
    )
    current_revision_refs = _current_revision_refs(
        chapter_index_snapshot["payload"],
        facts_snapshot["payload"],
    )
    return {
        "facts": facts_snapshot,
        "chapter_index": chapter_index_snapshot,
        "current_revision_refs": current_revision_refs,
    }


def _source_watermark(source: dict[str, Any]) -> tuple[tuple[Any, Any], tuple[Any, Any]]:
    return (
        (source["facts"]["version"], source["facts"]["sha256"]),
        (
            source["chapter_index"]["version"],
            source["chapter_index"]["sha256"],
        ),
    )


def execute(workspace: AuthorWorkspace, query: str) -> dict[str, Any]:
    """从同一句柄读 facts 和 current chapter index，再调 M6 对象核心。"""
    handle = _require_workspace(workspace)
    first_source = _read_query_source(handle)
    try:
        query_source = _read_query_source(handle)
    except AskWorkspaceError as exc:
        raise AskWorkspaceError("M6_SOURCE_CHANGED_BEFORE_QUERY") from exc
    if _source_watermark(first_source) != _source_watermark(query_source):
        raise AskWorkspaceError("M6_SOURCE_CHANGED_BEFORE_QUERY")

    m6_result = ask_tool.execute(
        {
            "query": query,
            "facts": query_source["facts"]["payload"],
            "current_revision_refs": query_source["current_revision_refs"],
        }
    )
    try:
        after_source = _read_query_source(handle)
    except AskWorkspaceError as exc:
        raise AskWorkspaceError("M6_SOURCE_CHANGED_DURING_QUERY") from exc
    if _source_watermark(after_source) != _source_watermark(query_source):
        raise AskWorkspaceError("M6_SOURCE_CHANGED_DURING_QUERY")

    return {
        "facts_snapshot": {
            "version": query_source["facts"]["version"],
            "sha256": query_source["facts"]["sha256"],
        },
        "chapter_index_snapshot": {
            "version": query_source["chapter_index"]["version"],
            "sha256": query_source["chapter_index"]["sha256"],
        },
        "m6": m6_result,
    }


__all__ = ["AskWorkspaceError", "execute"]
