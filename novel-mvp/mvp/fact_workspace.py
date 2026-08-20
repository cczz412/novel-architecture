"""C4 v1 快照到 AuthorWorkspace 的最小持久化适配器。

只使用 AuthorWorkspace 的逻辑键 ``facts``；不接路径、作者 ID、项目 ID，
不调用 legacy facts.json writer，也不做 M5 作者确认。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from . import (
    chapter_workspace,
    extract_workspace,
    fact_tool,
    factstore,
    segment_workspace,
)
from .workspace import AuthorWorkspace


LOGICAL_KEY = "facts"
UPSTREAM_KEYS = ("chapters", "chapter_index", "segments", "fact_candidates")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class FactWorkspaceError(factstore.FactstoreError):
    """适配器输入不是受绑定 workspace 能力或合法版本时拒绝。"""


class FactWorkspaceSourceChangedError(FactWorkspaceError):
    """M4 运行期间的来源水位已经变化。"""


def _require_workspace(value: Any) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        raise FactWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise FactWorkspaceError("M4_SOURCE_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def _validated_state_entry(value: Any, logical_key: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "logical_key",
        "version",
        "sha256",
        "payload",
    }:
        raise FactWorkspaceError(f"M4_SOURCE_STATE_INVALID:{logical_key}")
    version = value.get("version")
    sha256 = value.get("sha256")
    if (
        value.get("logical_key") != logical_key
        or isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
        or not isinstance(sha256, str)
        or SHA256_RE.fullmatch(sha256) is None
        or hashlib.sha256(_canonical_bytes(value.get("payload"))).hexdigest()
        != sha256
    ):
        raise FactWorkspaceError(f"M4_SOURCE_STATE_INVALID:{logical_key}")
    return value


def _source_identity(states: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "version": states[key]["version"],
            "sha256": states[key]["sha256"],
        }
        for key in UPSTREAM_KEYS
    }


def _read_upstream_states(
    workspace: AuthorWorkspace,
) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for key in UPSTREAM_KEYS:
        state = workspace.read(key)
        if state is None:
            raise FactWorkspaceError(f"M4_SOURCE_STATE_MISSING:{key}")
        states[key] = _validated_state_entry(state, key)
    return states


def _read_current_upstream(
    workspace: AuthorWorkspace,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    states_before = _read_upstream_states(workspace)
    try:
        chapters = chapter_workspace.read_c1_current_views(workspace)
        segments_payload = segment_workspace.read_current_segments(workspace)
        candidates_payload = extract_workspace.read_current_fact_candidates(workspace)
    except (
        chapter_workspace.ChapterWorkspaceError,
        segment_workspace.SegmentWorkspaceError,
        extract_workspace.ExtractWorkspaceError,
    ) as exc:
        raise FactWorkspaceError(f"M4_CURRENT_SOURCE_INVALID:{exc}") from exc

    states_after = _read_upstream_states(workspace)
    before_identity = _source_identity(states_before)
    after_identity = _source_identity(states_after)
    if before_identity != after_identity:
        raise FactWorkspaceSourceChangedError(
            "M4_CURRENT_SOURCE_CHANGED_DURING_READ"
        )
    if (
        chapters != states_after["chapters"]["payload"]
        or segments_payload != states_after["segments"]["payload"]
        or candidates_payload != states_after["fact_candidates"]["payload"]
    ):
        raise FactWorkspaceError("M4_CURRENT_SOURCE_PAYLOAD_DRIFT")

    current_refs = states_after["chapter_index"]["payload"]
    try:
        checked_chapters, checked_refs = chapter_workspace._validated_batch(
            chapters,
            current_refs,
        )
    except chapter_workspace.ChapterWorkspaceError as exc:
        raise FactWorkspaceError(f"M4_CURRENT_SOURCE_INVALID:{exc}") from exc
    if checked_chapters != chapters or checked_refs != current_refs:
        raise FactWorkspaceError("M4_CURRENT_SOURCE_PAYLOAD_DRIFT")
    return (
        copy.deepcopy(chapters),
        copy.deepcopy(segments_payload["items"]),
        copy.deepcopy(candidates_payload["items"]),
        after_identity,
    )


def save_snapshot(
    workspace: AuthorWorkspace,
    *,
    operation_id: str,
    snapshot: list[dict[str, Any]],
    expected_version: int,
) -> dict[str, Any]:
    """校验整批 C4 v1 后，通过 workspace.commit 原子替换逻辑键 facts。"""
    workspace = _require_workspace(workspace)
    if (
        not isinstance(expected_version, int)
        or isinstance(expected_version, bool)
        or expected_version < 0
    ):
        raise FactWorkspaceError("FACTS_EXPECTED_VERSION_INVALID")
    facts = factstore.validate_c4_v1_snapshot(snapshot)
    receipt = workspace.commit(
        operation_id,
        {LOGICAL_KEY: facts},
        {LOGICAL_KEY: expected_version},
    )
    return {
        "status": receipt["status"],
        "operation_id": receipt["operation_id"],
        "version": receipt["versions"][LOGICAL_KEY],
        "sha256": receipt["payload_sha256"][LOGICAL_KEY],
        "generation_id": receipt["generation_id"],
        "replayed": receipt["replayed"],
    }


def read_snapshot(workspace: AuthorWorkspace) -> dict[str, Any]:
    """读取并重新校验当前 facts；缺失时返回空的 version 0 视图。"""
    workspace = _require_workspace(workspace)
    current = workspace.read(LOGICAL_KEY)
    if current is None:
        return {"version": 0, "sha256": None, "facts": []}
    facts = factstore.validate_c4_v1_snapshot(current["payload"])
    return {
        "version": current["version"],
        "sha256": current["sha256"],
        "facts": copy.deepcopy(facts),
    }


def _read_current_fact_view_source(
    workspace: AuthorWorkspace,
) -> dict[str, Any]:
    facts_state = workspace.read(LOGICAL_KEY)
    if facts_state is None:
        facts_snapshot = {"version": 0, "sha256": None, "payload": []}
    else:
        facts_snapshot = _validated_state_entry(facts_state, LOGICAL_KEY)

    index_state = workspace.read("chapter_index")
    if index_state is None:
        raise FactWorkspaceError("M4_CURRENT_CHAPTER_INDEX_MISSING")
    index_snapshot = _validated_state_entry(index_state, "chapter_index")

    try:
        facts = factstore.validate_c4_v1_snapshot(facts_snapshot["payload"])
    except factstore.FactstoreError as exc:
        raise FactWorkspaceError(f"M4_CURRENT_FACTS_INVALID:{exc}") from exc
    try:
        refs_by_chapter = chapter_workspace._validated_revision_refs(
            index_snapshot["payload"]
        )
    except chapter_workspace.ChapterWorkspaceError as exc:
        raise FactWorkspaceError(
            f"M4_CURRENT_CHAPTER_INDEX_INVALID:{exc}"
        ) from exc

    current_facts: list[dict[str, Any]] = []
    stale_fact_ids: list[str] = []
    for fact in facts:
        chapter_id = fact["chapter_id"]
        current_ref = refs_by_chapter.get(chapter_id)
        if current_ref is None:
            raise FactWorkspaceError(
                f"M4_CURRENT_FACT_CHAPTER_UNKNOWN:{fact['id']}:{chapter_id}"
            )
        if fact["chapter_revision_ref"] == current_ref:
            current_facts.append(copy.deepcopy(fact))
        else:
            stale_fact_ids.append(fact["id"])

    return {
        "facts": current_facts,
        "stale_fact_ids": stale_fact_ids,
        "facts_snapshot": {
            "version": facts_snapshot["version"],
            "sha256": facts_snapshot["sha256"],
        },
        "chapter_index_snapshot": {
            "version": index_snapshot["version"],
            "sha256": index_snapshot["sha256"],
        },
    }


def _current_fact_view_watermark(
    view: dict[str, Any],
) -> tuple[tuple[Any, Any], tuple[Any, Any]]:
    return (
        (
            view["facts_snapshot"]["version"],
            view["facts_snapshot"]["sha256"],
        ),
        (
            view["chapter_index_snapshot"]["version"],
            view["chapter_index_snapshot"]["sha256"],
        ),
    )


def read_current_snapshot(workspace: AuthorWorkspace) -> dict[str, Any]:
    """只返回仍绑定 chapter_index current revision 的 C4 事实。"""
    workspace = _require_workspace(workspace)
    first_view = _read_current_fact_view_source(workspace)
    try:
        current_view = _read_current_fact_view_source(workspace)
    except FactWorkspaceError as exc:
        raise FactWorkspaceSourceChangedError(
            "M4_CURRENT_FACT_VIEW_SOURCE_CHANGED_DURING_READ"
        ) from exc
    current_watermark = _current_fact_view_watermark(current_view)
    if _current_fact_view_watermark(first_view) != current_watermark:
        raise FactWorkspaceSourceChangedError(
            "M4_CURRENT_FACT_VIEW_SOURCE_CHANGED_DURING_READ"
        )

    try:
        after_view = _read_current_fact_view_source(workspace)
    except FactWorkspaceError as exc:
        raise FactWorkspaceSourceChangedError(
            "M4_CURRENT_FACT_VIEW_SOURCE_CHANGED_DURING_READ"
        ) from exc
    if _current_fact_view_watermark(after_view) != current_watermark:
        raise FactWorkspaceSourceChangedError(
            "M4_CURRENT_FACT_VIEW_SOURCE_CHANGED_DURING_READ"
        )
    return copy.deepcopy(current_view)


def _revision_key(value: Any) -> str:
    if not isinstance(value, dict):
        raise FactWorkspaceError("M4_REVISION_REF_INVALID")
    return _canonical_bytes(value).decode("utf-8")


def materialize_current_extracted_snapshot(
    workspace: AuthorWorkspace,
    *,
    operation_id: str,
    source: str,
    added_at: str,
) -> dict[str, Any]:
    """把工作区 current C1＋C2＋C3 整批物化为一个 C4 EXTRACTED 快照。"""
    workspace = _require_workspace(workspace)
    chapters, segments, candidates, source_identity = _read_current_upstream(
        workspace
    )

    chapter_keys = [_revision_key(chapter["chapter_revision_ref"]) for chapter in chapters]
    if len(chapter_keys) != len(set(chapter_keys)):
        raise FactWorkspaceError("M4_CHAPTER_REVISION_REF_DUPLICATE")
    segments_by_revision: dict[str, list[dict[str, Any]]] = {
        key: [] for key in chapter_keys
    }
    candidates_by_revision: dict[str, list[dict[str, Any]]] = {
        key: [] for key in chapter_keys
    }
    for segment in segments:
        key = _revision_key(segment.get("chapter_revision_ref"))
        if key not in segments_by_revision:
            raise FactWorkspaceError("M4_SEGMENT_CURRENT_CHAPTER_NOT_FOUND")
        segments_by_revision[key].append(segment)
    for candidate in candidates:
        key = _revision_key(candidate.get("chapter_revision_ref"))
        if key not in candidates_by_revision:
            raise FactWorkspaceError("M4_CANDIDATE_CURRENT_CHAPTER_NOT_FOUND")
        candidates_by_revision[key].append(candidate)
    if any(not segments_by_revision[key] for key in chapter_keys):
        raise FactWorkspaceError("M4_CHAPTER_SEGMENTS_MISSING")

    snapshot: list[dict[str, Any]] = []
    try:
        for chapter, key in zip(chapters, chapter_keys, strict=True):
            result = fact_tool.execute(
                {
                    "chapter": chapter,
                    "segments": segments_by_revision[key],
                    "candidates": candidates_by_revision[key],
                    "existing_c4": snapshot,
                    "source": source,
                    "added_at": added_at,
                }
            )
            snapshot = result["facts"]
    except (factstore.FactstoreError, KeyError, TypeError) as exc:
        raise FactWorkspaceError(f"M4_MATERIALIZATION_REJECTED:{exc}") from exc

    snapshot = factstore.validate_c4_v1_snapshot(snapshot)
    if any(fact["status"] != factstore.STATUS_EXTRACTED for fact in snapshot):
        raise FactWorkspaceError("M4_MATERIALIZATION_STATUS_NOT_EXTRACTED")

    try:
        _, _, _, latest_identity = _read_current_upstream(workspace)
    except FactWorkspaceError as exc:
        raise FactWorkspaceSourceChangedError(
            "M4_SOURCE_CHANGED_DURING_RUN"
        ) from exc
    if latest_identity != source_identity:
        raise FactWorkspaceSourceChangedError("M4_SOURCE_CHANGED_DURING_RUN")

    return save_snapshot(
        workspace,
        operation_id=operation_id,
        snapshot=snapshot,
        expected_version=0,
    )
