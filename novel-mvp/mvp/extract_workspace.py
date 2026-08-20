"""把 AuthorWorkspace 当前 C2 交给 M3，并原子保存 C3 v1 候选。

本适配器只接受已绑定的能力句柄和冻结离线响应映射。它不接路径或身份字符串，
不调用模型，也不把候选晋升为 C4 或写进 ``facts``。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from mvp import extract_tool, segment_workspace
from mvp.workspace import AuthorWorkspace


FACT_CANDIDATES_KEY = "fact_candidates"
STATE_KEYS = {"items", "source_identity", "responses_identity"}
SOURCE_KEYS = {"segments", "chapter_index"}
IDENTITY_KEYS = {"version", "sha256"}
RESPONSES_IDENTITY_KEYS = {"kind", "sha256", "item_keys"}
RESPONSES_KIND = "LOCAL_FILESYSTEM_ONLY_FROZEN_RESPONSES"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
STATE_LOGICAL_KEYS = {
    "SEGMENTS": "segments",
    "CHAPTER_INDEX": "chapter_index",
    "FACT_CANDIDATES": FACT_CANDIDATES_KEY,
}


class ExtractWorkspaceError(ValueError):
    """M3 工作区来源、冻结响应或候选批次不合法。"""


class FactCandidatesStaleError(ExtractWorkspaceError):
    """已保存或运行中的 C3 不再对应当前 C2／章节水位。"""


def _validate_workspace(workspace: object) -> AuthorWorkspace:
    if not isinstance(workspace, AuthorWorkspace):
        raise ExtractWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return workspace


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ExtractWorkspaceError("VALUE_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def _validate_state_entry(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "logical_key",
        "version",
        "sha256",
        "payload",
    }:
        raise ExtractWorkspaceError(f"{label}_STATE_INVALID")
    if value.get("logical_key") != STATE_LOGICAL_KEYS[label]:
        raise ExtractWorkspaceError(f"{label}_STATE_INVALID")
    version = value.get("version")
    sha256 = value.get("sha256")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
        or not isinstance(sha256, str)
        or SHA256_RE.fullmatch(sha256) is None
    ):
        raise ExtractWorkspaceError(f"{label}_STATE_INVALID")
    if hashlib.sha256(_canonical_bytes(value.get("payload"))).hexdigest() != sha256:
        raise ExtractWorkspaceError(f"{label}_STATE_SHA_MISMATCH")
    return value


def _identity(value: dict[str, Any]) -> dict[str, Any]:
    return {"version": value["version"], "sha256": value["sha256"]}


def _source_identity(
    segments_state: dict[str, Any],
    index_state: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        "segments": _identity(segments_state),
        "chapter_index": _identity(index_state),
    }


def _read_stable_source(
    workspace: AuthorWorkspace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    segments_before = workspace.read("segments")
    index_before = workspace.read("chapter_index")
    if segments_before is None or index_before is None:
        raise ExtractWorkspaceError("M3_SOURCE_STATE_MISSING")
    segments_before = _validate_state_entry(segments_before, "SEGMENTS")
    index_before = _validate_state_entry(index_before, "CHAPTER_INDEX")

    try:
        current_segments = segment_workspace.read_current_segments(workspace)
    except (
        segment_workspace.SegmentWorkspaceError,
        segment_workspace.SegmentWorkspaceStaleError,
    ) as exc:
        raise ExtractWorkspaceError(f"M3_SOURCE_STATE_INVALID:{exc}") from exc

    segments_after = workspace.read("segments")
    index_after = workspace.read("chapter_index")
    if segments_after is None or index_after is None:
        raise ExtractWorkspaceError("M3_SOURCE_STATE_CHANGED_DURING_READ")
    segments_after = _validate_state_entry(segments_after, "SEGMENTS")
    index_after = _validate_state_entry(index_after, "CHAPTER_INDEX")
    before_identity = _source_identity(segments_before, index_before)
    after_identity = _source_identity(segments_after, index_after)
    if before_identity != after_identity:
        raise ExtractWorkspaceError("M3_SOURCE_STATE_CHANGED_DURING_READ")
    if current_segments != segments_after["payload"]:
        raise ExtractWorkspaceError("M3_SEGMENTS_PAYLOAD_DRIFT")

    items = current_segments.get("items")
    refs = index_after.get("payload")
    request = {
        "items": copy.deepcopy(items),
        "current_chapter_revision_refs": copy.deepcopy(refs),
    }
    try:
        extract_tool._validate_request(request)
    except (extract_tool.ExtractToolError, RuntimeError) as exc:
        raise ExtractWorkspaceError(f"M3_SOURCE_STATE_INVALID:{exc}") from exc
    return request["items"], request["current_chapter_revision_refs"], after_identity


def _responses_identity(responses: object) -> dict[str, Any]:
    if not isinstance(responses, dict):
        raise ExtractWorkspaceError("RESPONSES_MAPPING_NOT_OBJECT")
    if any(not isinstance(key, str) or not key for key in responses):
        raise ExtractWorkspaceError("RESPONSES_MAPPING_KEY_INVALID")
    payload = _canonical_bytes(responses)
    return {
        "kind": RESPONSES_KIND,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "item_keys": sorted(responses),
    }


def _require_exact_response_keys(
    responses_identity: dict[str, Any],
    source_items: list[dict[str, Any]],
    *,
    error_code: str,
) -> None:
    source_keys = sorted(extract_tool.item_key(item) for item in source_items)
    if responses_identity["item_keys"] != source_keys:
        raise ExtractWorkspaceError(error_code)


def _validate_identity(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != IDENTITY_KEYS:
        raise ExtractWorkspaceError(f"{label}_IDENTITY_INVALID")
    version = value.get("version")
    sha256 = value.get("sha256")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
        or not isinstance(sha256, str)
        or SHA256_RE.fullmatch(sha256) is None
    ):
        raise ExtractWorkspaceError(f"{label}_IDENTITY_INVALID")
    return copy.deepcopy(value)


def _validated_source_identity(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != SOURCE_KEYS:
        raise ExtractWorkspaceError("FACT_CANDIDATES_SOURCE_IDENTITY_INVALID")
    return {
        label: _validate_identity(value[label], label.upper())
        for label in sorted(SOURCE_KEYS)
    }


def _validated_responses_identity(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RESPONSES_IDENTITY_KEYS:
        raise ExtractWorkspaceError("FACT_CANDIDATES_RESPONSES_IDENTITY_INVALID")
    if value.get("kind") != RESPONSES_KIND:
        raise ExtractWorkspaceError("FACT_CANDIDATES_RESPONSES_IDENTITY_INVALID")
    sha256 = value.get("sha256")
    item_keys = value.get("item_keys")
    if (
        not isinstance(sha256, str)
        or SHA256_RE.fullmatch(sha256) is None
        or not isinstance(item_keys, list)
        or any(not isinstance(key, str) or not key for key in item_keys)
        or item_keys != sorted(set(item_keys))
    ):
        raise ExtractWorkspaceError("FACT_CANDIDATES_RESPONSES_IDENTITY_INVALID")
    return copy.deepcopy(value)


def _validate_candidate_items(
    candidates: Any,
    source_items: list[dict[str, Any]],
    current_refs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(candidates, list):
        raise ExtractWorkspaceError("FACT_CANDIDATES_ITEMS_INVALID")
    try:
        extract_tool._validate_request(
            {
                "items": copy.deepcopy(source_items),
                "current_chapter_revision_refs": copy.deepcopy(current_refs),
            }
        )
    except (extract_tool.ExtractToolError, RuntimeError) as exc:
        raise ExtractWorkspaceError("FACT_CANDIDATES_SOURCE_INVALID") from exc
    source_by_key = {
        extract_tool.item_key(item): item
        for item in source_items
    }
    validated: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise ExtractWorkspaceError(f"FACT_CANDIDATE_INVALID:{index}")
        key = extract_tool.item_key(candidate)
        source_item = source_by_key.get(key)
        if source_item is None:
            raise ExtractWorkspaceError(f"FACT_CANDIDATE_SOURCE_NOT_FOUND:{index}")
        try:
            extract_tool._validate_c3_candidate(
                candidate,
                source_item=source_item,
                key=key,
            )
        except extract_tool.ExtractToolError as exc:
            raise ExtractWorkspaceError(f"FACT_CANDIDATE_INVALID:{index}:{exc}") from exc
        validated.append(copy.deepcopy(candidate))
    return validated


def _validated_stored_payload(
    value: Any,
    source_items: list[dict[str, Any]],
    current_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != STATE_KEYS:
        raise ExtractWorkspaceError("FACT_CANDIDATES_STATE_INVALID")
    responses_identity = _validated_responses_identity(value["responses_identity"])
    _require_exact_response_keys(
        responses_identity,
        source_items,
        error_code="FACT_CANDIDATES_RESPONSES_EXACT_BATCH_INVALID",
    )
    return {
        "items": _validate_candidate_items(
            value["items"], source_items, current_refs
        ),
        "source_identity": _validated_source_identity(value["source_identity"]),
        "responses_identity": responses_identity,
    }


def persist_current_fact_candidates(
    workspace: AuthorWorkspace,
    operation_id: str,
    responses: Mapping[str, Any],
    expected_fact_candidates_version: Any,
) -> dict[str, Any]:
    """离线抽取当前 C2，并在来源未变化时一次提交 C3 候选。"""
    workspace = _validate_workspace(workspace)
    responses_identity = _responses_identity(responses)
    source_items, current_refs, source_identity = _read_stable_source(workspace)
    _require_exact_response_keys(
        responses_identity,
        source_items,
        error_code="RESPONSES_EXACT_BATCH_INVALID",
    )
    try:
        result = extract_tool.execute(
            {
                "items": copy.deepcopy(source_items),
                "current_chapter_revision_refs": copy.deepcopy(current_refs),
            },
            extract_tool.offline_response_provider(responses),
        )
        candidates = _validate_candidate_items(
            result.get("items"), source_items, current_refs
        )
    except (extract_tool.ExtractToolError, RuntimeError) as exc:
        raise ExtractWorkspaceError(f"M3_EXTRACTION_REJECTED:{exc}") from exc

    try:
        _, _, latest_identity = _read_stable_source(workspace)
    except ExtractWorkspaceError as exc:
        raise FactCandidatesStaleError(
            "FACT_CANDIDATES_SOURCE_CHANGED_DURING_RUN"
        ) from exc
    if latest_identity != source_identity:
        raise FactCandidatesStaleError("FACT_CANDIDATES_SOURCE_CHANGED_DURING_RUN")

    payload = {
        "items": candidates,
        "source_identity": source_identity,
        "responses_identity": responses_identity,
    }
    return workspace.commit(
        operation_id,
        {FACT_CANDIDATES_KEY: payload},
        {FACT_CANDIDATES_KEY: expected_fact_candidates_version},
    )


def read_current_fact_candidates(workspace: AuthorWorkspace) -> dict[str, Any]:
    """只在 C2 与 chapter index 来源仍 current 时读回 C3 v1。"""
    workspace = _validate_workspace(workspace)
    state = workspace.read(FACT_CANDIDATES_KEY)
    if state is None:
        raise ExtractWorkspaceError("FACT_CANDIDATES_STATE_MISSING")
    state = _validate_state_entry(state, "FACT_CANDIDATES")
    try:
        source_items, current_refs, current_identity = _read_stable_source(workspace)
    except ExtractWorkspaceError as exc:
        raise FactCandidatesStaleError("FACT_CANDIDATES_STALE") from exc
    payload = _validated_stored_payload(
        state["payload"], source_items, current_refs
    )
    if payload["source_identity"] != current_identity:
        raise FactCandidatesStaleError("FACT_CANDIDATES_STALE")
    return payload
