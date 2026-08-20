"""从 AuthorWorkspace 打开当前章的 M5 待审候选会话。

本模块只读 ``facts`` 与 ``chapter_index``，不持久化 session、不创建新状态、
不替作者确认。返回的完整 C4 候选可由调用方显式构造 M5 动作后交给
``review_workspace.apply_review_batch``。
"""

from __future__ import annotations

import copy
from typing import Any

from . import factstore, review_workspace
from .workspace import AuthorWorkspace, SHA256_RE


FACTS_LOGICAL_KEY = "facts"
CHAPTER_INDEX_LOGICAL_KEY = "chapter_index"
REVISION_REF_KEYS = {
    "chapter_id",
    "revision_no",
    "revision_text_sha256",
}


class ReviewQueueWorkspaceError(review_workspace.ReviewWorkspaceError):
    """工作区待审会话缺少 current 身份或收到非能力句柄。"""


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        raise ReviewQueueWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _clean_chapter_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "/" in value
        or "\\" in value
        or value in {".", ".."}
    ):
        raise ReviewQueueWorkspaceError("CHAPTER_ID_INVALID")
    return value


def _read_list_snapshot(
    workspace: AuthorWorkspace,
    logical_key: str,
    *,
    allow_missing: bool,
) -> dict[str, Any]:
    entry = workspace.read(logical_key)
    if entry is None:
        if allow_missing:
            return {"version": 0, "sha256": None, "payload": []}
        raise ReviewQueueWorkspaceError(f"{logical_key.upper()}_SNAPSHOT_MISSING")
    if (
        not isinstance(entry, dict)
        or entry.get("logical_key") != logical_key
        or not isinstance(entry.get("version"), int)
        or isinstance(entry.get("version"), bool)
        or entry["version"] < 1
        or not isinstance(entry.get("sha256"), str)
        or SHA256_RE.fullmatch(entry["sha256"]) is None
        or not isinstance(entry.get("payload"), list)
    ):
        raise ReviewQueueWorkspaceError(
            f"{logical_key.upper()}_WORKSPACE_ENTRY_INVALID"
        )
    return {
        "version": entry["version"],
        "sha256": entry["sha256"],
        "payload": copy.deepcopy(entry["payload"]),
    }


def _revision_index(value: list[Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for index, ref in enumerate(value):
        if (
            not isinstance(ref, dict)
            or set(ref) != REVISION_REF_KEYS
            or not isinstance(ref.get("chapter_id"), str)
            or not ref["chapter_id"]
            or not isinstance(ref.get("revision_no"), int)
            or isinstance(ref["revision_no"], bool)
            or ref["revision_no"] < 1
            or not isinstance(ref.get("revision_text_sha256"), str)
            or SHA256_RE.fullmatch(ref["revision_text_sha256"]) is None
        ):
            raise ReviewQueueWorkspaceError(
                f"CHAPTER_INDEX_REF_INVALID:{index}"
            )
        chapter_id = ref["chapter_id"]
        if chapter_id in indexed:
            raise ReviewQueueWorkspaceError(
                f"CHAPTER_INDEX_REF_DUPLICATE:{chapter_id}"
            )
        indexed[chapter_id] = copy.deepcopy(ref)
    return indexed


def _validated_current_review_source(
    facts_snapshot: dict[str, Any],
    chapter_index_snapshot: dict[str, Any],
    chapter_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    refs_by_chapter = _revision_index(chapter_index_snapshot["payload"])
    current_ref = refs_by_chapter.get(chapter_id)
    if current_ref is None:
        raise ReviewQueueWorkspaceError(
            f"CHAPTER_CURRENT_REVISION_NOT_FOUND:{chapter_id}"
        )
    facts = factstore.validate_c4_v1_snapshot(facts_snapshot["payload"])
    fact_chapters = {fact["chapter_id"] for fact in facts}
    missing_chapters = sorted(fact_chapters - set(refs_by_chapter))
    if missing_chapters:
        raise ReviewQueueWorkspaceError(
            f"FACT_CHAPTER_NOT_IN_INDEX:{','.join(missing_chapters)}"
        )
    return facts, current_ref


def _is_pending_candidate(
    fact: dict[str, Any],
    chapter_id: str,
    current_ref: dict[str, Any],
) -> bool:
    return (
        fact["chapter_id"] == chapter_id
        and fact["chapter_revision_ref"] == current_ref
        and fact["status"] == "extracted"
        and fact["anchor_state"] == "VERIFIED"
        and fact["recheck"] is None
    )


def _snapshot_watermark(snapshot: dict[str, Any]) -> tuple[int, str | None]:
    return snapshot["version"], snapshot["sha256"]


def _read_stable_page_source(
    workspace: AuthorWorkspace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    first_facts = _read_list_snapshot(
        workspace,
        FACTS_LOGICAL_KEY,
        allow_missing=True,
    )
    first_index = _read_list_snapshot(
        workspace,
        CHAPTER_INDEX_LOGICAL_KEY,
        allow_missing=False,
    )
    second_facts = _read_list_snapshot(
        workspace,
        FACTS_LOGICAL_KEY,
        allow_missing=True,
    )
    second_index = _read_list_snapshot(
        workspace,
        CHAPTER_INDEX_LOGICAL_KEY,
        allow_missing=False,
    )
    if (
        _snapshot_watermark(first_facts) != _snapshot_watermark(second_facts)
        or _snapshot_watermark(first_index) != _snapshot_watermark(second_index)
    ):
        raise ReviewQueueWorkspaceError("REVIEW_SOURCE_SNAPSHOT_CHANGED")
    return second_facts, second_index


def open_chapter_review_session(
    workspace: AuthorWorkspace,
    chapter_id: str,
) -> dict[str, Any]:
    """列出当前章 current revision 上可由作者明确审查的 extracted C4。"""

    handle = _require_workspace(workspace)
    clean_chapter_id = _clean_chapter_id(chapter_id)
    facts_snapshot = _read_list_snapshot(
        handle,
        FACTS_LOGICAL_KEY,
        allow_missing=True,
    )
    chapter_index_snapshot = _read_list_snapshot(
        handle,
        CHAPTER_INDEX_LOGICAL_KEY,
        allow_missing=False,
    )
    facts, current_ref = _validated_current_review_source(
        facts_snapshot,
        chapter_index_snapshot,
        clean_chapter_id,
    )
    candidates = [
        copy.deepcopy(fact)
        for fact in facts
        if _is_pending_candidate(fact, clean_chapter_id, current_ref)
    ]
    return {
        "chapter_id": clean_chapter_id,
        "chapter_revision_ref": copy.deepcopy(current_ref),
        "facts_snapshot": {
            "version": facts_snapshot["version"],
            "sha256": facts_snapshot["sha256"],
        },
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def read_chapter_review_page(
    workspace: AuthorWorkspace,
    chapter_id: str,
    page_size: int,
    after_fact_ref: str | None,
) -> dict[str, Any]:
    """按事实账原顺序读取当前章下一页待审项，不保存 UI 游标。"""

    handle = _require_workspace(workspace)
    clean_chapter_id = _clean_chapter_id(chapter_id)
    if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size < 1:
        raise ReviewQueueWorkspaceError("PAGE_SIZE_INVALID")
    if after_fact_ref is not None and (
        not isinstance(after_fact_ref, str)
        or not after_fact_ref
        or after_fact_ref != after_fact_ref.strip()
    ):
        raise ReviewQueueWorkspaceError("AFTER_FACT_REF_INVALID")

    facts_snapshot, chapter_index_snapshot = _read_stable_page_source(handle)
    facts, current_ref = _validated_current_review_source(
        facts_snapshot,
        chapter_index_snapshot,
        clean_chapter_id,
    )
    cursor_index = -1
    if after_fact_ref is not None:
        cursor_index = next(
            (
                index
                for index, fact in enumerate(facts)
                if fact["id"] == after_fact_ref
            ),
            -1,
        )
        if cursor_index < 0:
            raise ReviewQueueWorkspaceError(
                f"AFTER_FACT_REF_NOT_FOUND:{after_fact_ref}"
            )
        cursor_fact = facts[cursor_index]
        if cursor_fact["chapter_id"] != clean_chapter_id:
            raise ReviewQueueWorkspaceError(
                f"AFTER_FACT_REF_CHAPTER_MISMATCH:{after_fact_ref}"
            )
        if cursor_fact["chapter_revision_ref"] != current_ref:
            raise ReviewQueueWorkspaceError(
                f"AFTER_FACT_REF_REVISION_MISMATCH:{after_fact_ref}"
            )

    remaining = [
        copy.deepcopy(fact)
        for fact in facts[cursor_index + 1:]
        if _is_pending_candidate(fact, clean_chapter_id, current_ref)
    ]
    items = remaining[:page_size]
    return {
        "chapter_id": clean_chapter_id,
        "chapter_revision_ref": copy.deepcopy(current_ref),
        "facts_snapshot": {
            "version": facts_snapshot["version"],
            "sha256": facts_snapshot["sha256"],
        },
        "items": items,
        "has_more": len(remaining) > len(items),
        "next_after_fact_ref": (
            items[-1]["id"] if items else after_fact_ref
        ),
    }


__all__ = [
    "ReviewQueueWorkspaceError",
    "open_chapter_review_session",
    "read_chapter_review_page",
]
