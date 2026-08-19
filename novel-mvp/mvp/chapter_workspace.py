"""把合法 C1 v1 current view 原子保存到 AuthorWorkspace。

本适配器只物化已经由上游确认的 current view；它不创建 C11 revision、不猜测
current revision，也不接路径、作者 ID 或项目 ID。M2 可通过纯对象读取入口取得 C1。
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from typing import Any

from mvp import store
from mvp.workspace import AuthorWorkspace


VISIBLE_KEYS = {"chapters", "chapter_index"}
REVISION_REF_KEYS = {
    "chapter_id",
    "revision_no",
    "revision_text_sha256",
}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class ChapterWorkspaceError(ValueError):
    """C1 current view 尚未满足工作区保存或读取条件。"""


def _validate_workspace(workspace: object) -> AuthorWorkspace:
    if not isinstance(workspace, AuthorWorkspace):
        raise ChapterWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return workspace


def _validated_revision_refs(
    current_revision_refs: object,
) -> dict[str, dict[str, Any]]:
    if not isinstance(current_revision_refs, list):
        raise ChapterWorkspaceError("CURRENT_REVISION_REFS_MUST_BE_LIST")
    indexed: dict[str, dict[str, Any]] = {}
    for index, ref in enumerate(current_revision_refs):
        if not isinstance(ref, dict) or set(ref) != REVISION_REF_KEYS:
            raise ChapterWorkspaceError(f"CURRENT_REVISION_REF_INVALID:{index}")
        chapter_id = ref["chapter_id"]
        revision_no = ref["revision_no"]
        text_sha = ref["revision_text_sha256"]
        if (
            not isinstance(chapter_id, str)
            or not chapter_id
            or isinstance(revision_no, bool)
            or not isinstance(revision_no, int)
            or revision_no < 1
            or not isinstance(text_sha, str)
            or SHA256_RE.fullmatch(text_sha) is None
        ):
            raise ChapterWorkspaceError(f"CURRENT_REVISION_REF_INVALID:{index}")
        if chapter_id in indexed:
            raise ChapterWorkspaceError("CURRENT_REVISION_REF_DUPLICATE_CHAPTER_ID")
        indexed[chapter_id] = copy.deepcopy(ref)
    return indexed


def _validated_batch(
    current_views: object,
    current_revision_refs: object,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(current_views, list) or not current_views:
        raise ChapterWorkspaceError("C1_CURRENT_VIEW_BATCH_REQUIRED")
    refs_by_chapter = _validated_revision_refs(current_revision_refs)
    chapters: list[dict[str, Any]] = []
    chapter_ids: set[str] = set()
    ordered_refs: list[dict[str, Any]] = []
    for index, chapter in enumerate(current_views):
        if not isinstance(chapter, dict):
            raise ChapterWorkspaceError(f"C1_CURRENT_VIEW_INVALID:{index}")
        try:
            store._validate_c1_v1_current_view(chapter)
        except (KeyError, TypeError, ValueError) as exc:
            raise ChapterWorkspaceError(
                f"C1_CURRENT_VIEW_INVALID:{index}:{exc}"
            ) from exc
        chapter_id = chapter["id"]
        if chapter_id in chapter_ids:
            raise ChapterWorkspaceError("C1_CURRENT_VIEW_DUPLICATE_CHAPTER_ID")
        chapter_ids.add(chapter_id)
        current_ref = refs_by_chapter.get(chapter_id)
        if current_ref is None or chapter["chapter_revision_ref"] != current_ref:
            raise ChapterWorkspaceError("C1_CURRENT_REVISION_REF_MISMATCH")
        chapters.append(copy.deepcopy(chapter))
        ordered_refs.append(copy.deepcopy(current_ref))

    if chapter_ids != set(refs_by_chapter):
        raise ChapterWorkspaceError("C1_CURRENT_REVISION_REF_SET_MISMATCH")
    try:
        json.dumps(
            {"chapters": chapters, "chapter_index": ordered_refs},
            ensure_ascii=False,
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ChapterWorkspaceError("C1_CURRENT_VIEW_NOT_JSON_SERIALIZABLE") from exc
    return chapters, ordered_refs


def persist_c1_current_views(
    workspace: AuthorWorkspace,
    operation_id: str,
    current_views: list[dict[str, Any]],
    current_revision_refs: list[dict[str, Any]],
    expected_versions: Mapping[str, Any],
) -> dict[str, Any]:
    """一次原子提交 C1 current views 与同批 current revision refs。"""
    workspace = _validate_workspace(workspace)
    if not isinstance(expected_versions, Mapping) or set(expected_versions) != VISIBLE_KEYS:
        raise ChapterWorkspaceError("C1_EXPECTED_VERSION_KEYS_MISMATCH")
    chapters, chapter_index = _validated_batch(
        current_views,
        current_revision_refs,
    )
    return workspace.commit(
        operation_id,
        {"chapters": chapters, "chapter_index": chapter_index},
        expected_versions,
    )


def read_c1_current_views(workspace: AuthorWorkspace) -> list[dict[str, Any]]:
    """从工作区读回并复核同一原子版本的 C1 current view 批次。"""
    workspace = _validate_workspace(workspace)
    chapters_state = workspace.read("chapters")
    index_state = workspace.read("chapter_index")
    if chapters_state is None or index_state is None:
        raise ChapterWorkspaceError("C1_WORKSPACE_STATE_MISSING")
    if chapters_state["version"] != index_state["version"]:
        raise ChapterWorkspaceError("C1_WORKSPACE_STATE_VERSION_DIVERGED")
    chapters, _ = _validated_batch(
        chapters_state["payload"],
        index_state["payload"],
    )
    return chapters
