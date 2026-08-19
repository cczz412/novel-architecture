"""把 AuthorWorkspace 中当前 C1 交给 M2，并持久化可查 stale 的 C2。

本适配器不接路径或身份字符串，不改变 C1/C2 字段，也不创建通用编排层。
来源章节在切段后发生变化时，旧 C2 只能以 STALE 拒绝，不能冒充 current。
"""

from __future__ import annotations

import copy
from typing import Any

from mvp import chapter_workspace, segment_tool
from mvp.workspace import AuthorWorkspace


SEGMENT_STATE_KEYS = {"items", "receipt", "options", "source_identity"}
SOURCE_KEYS = {"chapters", "chapter_index"}
SOURCE_IDENTITY_KEYS = {"version", "sha256"}


class SegmentWorkspaceError(ValueError):
    """M2 工作区入口、来源或持久化结果不合法。"""


class SegmentWorkspaceStaleError(SegmentWorkspaceError):
    """已保存的 C2 不再对应工作区当前 C1。"""


def _validate_workspace(workspace: object) -> AuthorWorkspace:
    if not isinstance(workspace, AuthorWorkspace):
        raise SegmentWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return workspace


def _read_source_states(
    workspace: AuthorWorkspace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    chapters_state = workspace.read("chapters")
    index_state = workspace.read("chapter_index")
    if chapters_state is None or index_state is None:
        raise SegmentWorkspaceError("M2_SOURCE_STATE_MISSING")
    if chapters_state["version"] != index_state["version"]:
        raise SegmentWorkspaceError("M2_SOURCE_STATE_VERSION_DIVERGED")
    return chapters_state, index_state


def _source_identity(
    chapters_state: dict[str, Any],
    index_state: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        "chapters": {
            "version": chapters_state["version"],
            "sha256": chapters_state["sha256"],
        },
        "chapter_index": {
            "version": index_state["version"],
            "sha256": index_state["sha256"],
        },
    }


def _validated_source_snapshot(
    workspace: AuthorWorkspace,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    chapters_state, index_state = _read_source_states(workspace)
    try:
        chapters, _ = chapter_workspace._validated_batch(
            chapters_state["payload"],
            index_state["payload"],
        )
    except chapter_workspace.ChapterWorkspaceError as exc:
        raise SegmentWorkspaceError(f"M2_SOURCE_STATE_INVALID:{exc}") from exc
    return chapters, _source_identity(chapters_state, index_state)


def persist_current_segments(
    workspace: AuthorWorkspace,
    operation_id: str,
    seg_min_chars: int,
    seg_max_chars: int,
    halo_chars: int,
    expected_segments_version: Any,
) -> dict[str, Any]:
    """读取当前 C1，调用现役 M2，并一次提交 segments。"""
    workspace = _validate_workspace(workspace)
    chapters, source_identity = _validated_source_snapshot(workspace)
    options = {
        "seg_min_chars": seg_min_chars,
        "seg_max_chars": seg_max_chars,
        "halo_chars": halo_chars,
    }
    try:
        result = segment_tool.execute({"items": chapters, "options": options})
    except segment_tool.SegmentToolError as exc:
        raise SegmentWorkspaceError(f"M2_SEGMENTATION_REJECTED:{exc}") from exc

    try:
        _, latest_identity = _validated_source_snapshot(workspace)
    except SegmentWorkspaceError as exc:
        raise SegmentWorkspaceStaleError("SEGMENTS_SOURCE_CHANGED_DURING_RUN") from exc
    if latest_identity != source_identity:
        raise SegmentWorkspaceStaleError("SEGMENTS_SOURCE_CHANGED_DURING_RUN")

    payload = {
        "items": result["items"],
        "receipt": result["receipt"],
        "options": options,
        "source_identity": source_identity,
    }
    return workspace.commit(
        operation_id,
        {"segments": payload},
        {"segments": expected_segments_version},
    )


def _validated_stored_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != SEGMENT_STATE_KEYS:
        raise SegmentWorkspaceError("SEGMENTS_STATE_INVALID")
    identity = payload["source_identity"]
    if not isinstance(identity, dict) or set(identity) != SOURCE_KEYS:
        raise SegmentWorkspaceError("SEGMENTS_STATE_INVALID")
    for value in identity.values():
        if not isinstance(value, dict) or set(value) != SOURCE_IDENTITY_KEYS:
            raise SegmentWorkspaceError("SEGMENTS_STATE_INVALID")
    return copy.deepcopy(payload)


def read_current_segments(workspace: AuthorWorkspace) -> dict[str, Any]:
    """只在来源 C1 身份仍为 current 时读回已保存 C2。"""
    workspace = _validate_workspace(workspace)
    segments_state = workspace.read("segments")
    if segments_state is None:
        raise SegmentWorkspaceError("SEGMENTS_STATE_MISSING")
    payload = _validated_stored_payload(segments_state["payload"])

    try:
        chapters_state, index_state = _read_source_states(workspace)
    except SegmentWorkspaceError as exc:
        raise SegmentWorkspaceStaleError("SEGMENTS_STALE") from exc
    current_identity = _source_identity(chapters_state, index_state)
    if current_identity != payload["source_identity"]:
        raise SegmentWorkspaceStaleError("SEGMENTS_STALE")

    try:
        chapters, _ = chapter_workspace._validated_batch(
            chapters_state["payload"],
            index_state["payload"],
        )
        expected = segment_tool.execute(
            {"items": chapters, "options": payload["options"]}
        )
    except (chapter_workspace.ChapterWorkspaceError, segment_tool.SegmentToolError) as exc:
        raise SegmentWorkspaceError("SEGMENTS_STATE_INVALID") from exc
    if payload["items"] != expected["items"] or payload["receipt"] != expected["receipt"]:
        raise SegmentWorkspaceError("SEGMENTS_STATE_INVALID")
    return payload
