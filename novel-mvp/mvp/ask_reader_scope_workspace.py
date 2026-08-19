"""AuthorWorkspace 到 M6 读者截点查询的只读适配层。

调用方只能交入已绑定作者与项目的 ``AuthorWorkspace`` 句柄、
查询词和截点章节。章节顺序只从同一工作区的 chapter_index 读取。
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from . import ask_reader_scope_tool, ask_tool, factstore
from .workspace import AuthorWorkspace


FACTS_LOGICAL_KEY = "facts"
CHAPTER_INDEX_LOGICAL_KEY = "chapter_index"
ENTRY_KEYS = {"logical_key", "version", "sha256", "payload"}


class ReaderScopeWorkspaceError(ask_reader_scope_tool.ReaderScopeError):
    """读者截点的工作区输入损坏或读途变化时拒绝。"""


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        raise ReaderScopeWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _payload_sha256(value: object) -> str:
    try:
        payload = (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReaderScopeWorkspaceError(
            "WORKSPACE_PAYLOAD_NOT_JSON_SERIALIZABLE"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _read_list_snapshot(
    workspace: AuthorWorkspace,
    logical_key: str,
) -> dict[str, Any]:
    entry = workspace.read(logical_key)
    if entry is None:
        return {
            "present": False,
            "version": 0,
            "sha256": None,
            "payload": [],
        }
    if (
        not isinstance(entry, dict)
        or set(entry) != ENTRY_KEYS
        or entry.get("logical_key") != logical_key
        or not isinstance(entry.get("version"), int)
        or isinstance(entry.get("version"), bool)
        or entry["version"] < 1
        or not isinstance(entry.get("sha256"), str)
        or ask_tool.SHA256_RE.fullmatch(entry["sha256"]) is None
        or not isinstance(entry.get("payload"), list)
        or _payload_sha256(entry["payload"]) != entry["sha256"]
    ):
        raise ReaderScopeWorkspaceError(
            f"{logical_key.upper()}_WORKSPACE_ENTRY_INVALID"
        )
    return {
        "present": True,
        "version": entry["version"],
        "sha256": entry["sha256"],
        "payload": copy.deepcopy(entry["payload"]),
    }


def _read_pair(workspace: AuthorWorkspace) -> dict[str, dict[str, Any]]:
    return {
        FACTS_LOGICAL_KEY: _read_list_snapshot(workspace, FACTS_LOGICAL_KEY),
        CHAPTER_INDEX_LOGICAL_KEY: _read_list_snapshot(
            workspace,
            CHAPTER_INDEX_LOGICAL_KEY,
        ),
    }


def _watermark(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {"version": snapshot["version"], "sha256": snapshot["sha256"]}


def _validate_pair(
    snapshots: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    facts_snapshot = snapshots[FACTS_LOGICAL_KEY]
    index_snapshot = snapshots[CHAPTER_INDEX_LOGICAL_KEY]
    if not index_snapshot["present"]:
        raise ReaderScopeWorkspaceError("CHAPTER_INDEX_REQUIRED")

    try:
        facts = factstore.validate_c4_v1_snapshot(facts_snapshot["payload"])
        current_refs = ask_reader_scope_tool._ordered_current_refs(
            index_snapshot["payload"]
        )
    except (factstore.FactstoreError, ask_reader_scope_tool.ReaderScopeError) as exc:
        raise ReaderScopeWorkspaceError(f"WORKSPACE_SNAPSHOT_INVALID:{exc}") from exc

    refs_by_chapter = {ref["chapter_id"]: ref for ref in current_refs}
    for index, fact in enumerate(facts, start=1):
        current_ref = refs_by_chapter.get(fact["chapter_id"])
        if current_ref is None:
            raise ReaderScopeWorkspaceError(
                f"FACT_CHAPTER_NOT_IN_CURRENT_INDEX:{index}"
            )
        if fact["chapter_revision_ref"] != current_ref:
            raise ReaderScopeWorkspaceError(f"FACT_NOT_CURRENT_REVISION:{index}")
    return facts, current_refs


def _same_watermarks(
    left: dict[str, dict[str, Any]],
    right: dict[str, dict[str, Any]],
) -> bool:
    return all(
        _watermark(left[key]) == _watermark(right[key])
        for key in (FACTS_LOGICAL_KEY, CHAPTER_INDEX_LOGICAL_KEY)
    )


def execute(
    workspace: AuthorWorkspace,
    query: str,
    as_of_chapter_id: str,
) -> dict[str, Any]:
    """从同一作者工作区读当前事实与章节顺序，再做截点查询。"""

    handle = _require_workspace(workspace)
    before = _read_pair(handle)
    facts, current_refs = _validate_pair(before)

    try:
        reader_result = ask_reader_scope_tool.execute(
            {
                "query": query,
                "facts": facts,
                "current_revision_refs": current_refs,
                "as_of_chapter_id": as_of_chapter_id,
            }
        )
    except ask_reader_scope_tool.ReaderScopeError as exc:
        raise ReaderScopeWorkspaceError(f"READER_SCOPE_QUERY_REJECTED:{exc}") from exc

    after = _read_pair(handle)
    _validate_pair(after)
    if not _same_watermarks(before, after):
        raise ReaderScopeWorkspaceError("WORKSPACE_SNAPSHOT_CHANGED_DURING_QUERY")

    return {
        "facts_snapshot": _watermark(before[FACTS_LOGICAL_KEY]),
        "chapter_index_snapshot": _watermark(
            before[CHAPTER_INDEX_LOGICAL_KEY]
        ),
        "m6": reader_result,
    }


__all__ = ["ReaderScopeWorkspaceError", "execute"]
