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

from mvp import extract, extract_run_receipt, extract_tool, segment_workspace
from mvp.workspace import (
    AuthorWorkspace,
    OperationConflictError,
    VersionConflictError,
)


FACT_CANDIDATE_RUNS_KEY = "fact_candidate_runs"
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
    "FACT_CANDIDATE_RUNS": FACT_CANDIDATE_RUNS_KEY,
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


def _expected_version_number(value: Any, *, code: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        version = value
    elif isinstance(value, Mapping):
        version = value.get("version")
    else:
        version = None
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        raise ExtractWorkspaceError(code)
    return version


def _read_run_ledger_state(workspace: AuthorWorkspace) -> dict[str, Any]:
    state = workspace.read(FACT_CANDIDATE_RUNS_KEY)
    if state is None:
        return {
            "logical_key": FACT_CANDIDATE_RUNS_KEY,
            "version": 0,
            "sha256": None,
            "payload": extract_run_receipt.empty_ledger(),
        }
    state = _validate_state_entry(state, "FACT_CANDIDATE_RUNS")
    try:
        ledger = extract_run_receipt.validate_ledger(state["payload"])
    except extract_run_receipt.ExtractRunReceiptError as exc:
        raise ExtractWorkspaceError(
            f"FACT_CANDIDATE_RUN_LEDGER_INVALID:{exc}"
        ) from exc
    return {**state, "payload": ledger}


def _existing_run(
    ledger: dict[str, Any], operation_id: str
) -> dict[str, Any] | None:
    for receipt in ledger["runs"]:
        if receipt["operation_id"] == operation_id:
            return receipt
    return None


def _ledger_with_receipt(
    ledger: dict[str, Any], receipt: dict[str, Any]
) -> dict[str, Any]:
    existing_index = next(
        (
            index
            for index, row in enumerate(ledger["runs"])
            if row["operation_id"] == receipt["operation_id"]
        ),
        None,
    )
    if existing_index is not None:
        existing = ledger["runs"][existing_index]
        if existing != receipt:
            raise OperationConflictError(
                "OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST"
            )
        # 重建该 operation 当时提交的 append-only ledger，使 AuthorWorkspace
        # 即使在后续运行已经追加后，也能按原 request SHA 幂等重放。
        return extract_run_receipt.validate_ledger(
            {
                "schema_version": extract_run_receipt.LEDGER_SCHEMA_VERSION,
                "runs": copy.deepcopy(ledger["runs"][: existing_index + 1]),
            }
        )
    result = copy.deepcopy(ledger)
    result["runs"].append(copy.deepcopy(receipt))
    return extract_run_receipt.validate_ledger(result)


def _visible_fact_candidate_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """保持旧公开回执只暴露 fact_candidates 的版本映射。"""
    result = copy.deepcopy(receipt)
    result["versions"] = {
        FACT_CANDIDATES_KEY: receipt["versions"][FACT_CANDIDATES_KEY]
    }
    result["payload_sha256"] = {
        FACT_CANDIDATES_KEY: receipt["payload_sha256"][FACT_CANDIDATES_KEY]
    }
    return result


def persist_current_fact_candidates(
    workspace: AuthorWorkspace,
    operation_id: str,
    responses: Mapping[str, Any],
    expected_fact_candidates_version: Any,
) -> dict[str, Any]:
    """离线完整抽取当前 C2，并原子提交 C3 与 ``COMPLETE`` 运行回执。"""
    workspace = _validate_workspace(workspace)
    candidate_parent_version = _expected_version_number(
        expected_fact_candidates_version,
        code="FACT_CANDIDATES_EXPECTED_VERSION_INVALID",
    )
    responses_identity = _responses_identity(responses)
    source_items, current_refs, source_identity = _read_stable_source(workspace)
    item_keys = [extract_tool.item_key(item) for item in source_items]
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
    ledger_state = _read_run_ledger_state(workspace)
    existing = _existing_run(ledger_state["payload"], operation_id)
    ledger_parent_version = (
        ledger_state["version"]
        if existing is None
        else existing["ledger_parent_version"]
    )
    run_receipt = extract_run_receipt.build_complete_receipt(
        operation_id=operation_id,
        provider_ref=f"FROZEN_RESPONSES:{responses_identity['sha256']}",
        source_identity=source_identity,
        expected_item_keys=item_keys,
        accepted_candidate_count=len(candidates),
        responses_identity=responses_identity,
        candidate_snapshot={
            "version": candidate_parent_version + 1,
            "sha256": extract_run_receipt.payload_sha256(payload),
        },
        ledger_parent_version=ledger_parent_version,
        candidate_parent_version=candidate_parent_version,
    )
    ledger = _ledger_with_receipt(ledger_state["payload"], run_receipt)
    committed = workspace.commit(
        operation_id,
        {
            FACT_CANDIDATE_RUNS_KEY: ledger,
            FACT_CANDIDATES_KEY: payload,
        },
        {
            FACT_CANDIDATE_RUNS_KEY: ledger_parent_version,
            FACT_CANDIDATES_KEY: expected_fact_candidates_version,
        },
    )
    return _visible_fact_candidate_receipt(committed)


def persist_failed_fact_candidate_run(
    workspace: AuthorWorkspace,
    *,
    operation_id: str,
    provider_ref: str,
    failure: extract.ExtractCallFailure,
    failed_item_key: str | None,
    completed_item_keys: list[str],
    accepted_candidate_count: int,
    expected_run_receipts_version: Any,
) -> dict[str, Any]:
    """保存一次失败／截断回执；不写或替换 current C3。"""
    workspace = _validate_workspace(workspace)
    if not isinstance(failure, extract.ExtractCallFailure):
        raise ExtractWorkspaceError("M3_STRUCTURED_FAILURE_REQUIRED")
    ledger_parent_version = _expected_version_number(
        expected_run_receipts_version,
        code="FACT_CANDIDATE_RUNS_EXPECTED_VERSION_INVALID",
    )
    source_items, _, source_identity = _read_stable_source(workspace)
    item_keys = [extract_tool.item_key(item) for item in source_items]
    ledger_state = _read_run_ledger_state(workspace)
    existing = _existing_run(ledger_state["payload"], operation_id)
    if existing is not None:
        ledger_parent_version = existing["ledger_parent_version"]
    elif ledger_parent_version != ledger_state["version"]:
        raise VersionConflictError("VERSION_CONFLICT")
    try:
        run_receipt = extract_run_receipt.build_failure_receipt(
            operation_id=operation_id,
            completion_state=failure.completion_state,
            provider_ref=provider_ref,
            source_identity=source_identity,
            expected_item_keys=item_keys,
            completed_item_keys=completed_item_keys,
            accepted_candidate_count=accepted_candidate_count,
            failure=failure.receipt_failure(failed_item_key=failed_item_key),
            ledger_parent_version=ledger_parent_version,
        )
    except extract_run_receipt.ExtractRunReceiptError as exc:
        raise ExtractWorkspaceError(
            f"M3_FAILURE_RECEIPT_INVALID:{exc}"
        ) from exc
    ledger = _ledger_with_receipt(ledger_state["payload"], run_receipt)

    try:
        _, _, latest_identity = _read_stable_source(workspace)
    except ExtractWorkspaceError as exc:
        raise FactCandidatesStaleError(
            "FACT_CANDIDATE_RUN_SOURCE_CHANGED_DURING_RECORD"
        ) from exc
    if latest_identity != source_identity:
        raise FactCandidatesStaleError(
            "FACT_CANDIDATE_RUN_SOURCE_CHANGED_DURING_RECORD"
        )
    return workspace.commit(
        operation_id,
        {FACT_CANDIDATE_RUNS_KEY: ledger},
        {FACT_CANDIDATE_RUNS_KEY: ledger_parent_version},
    )


def read_fact_candidate_run_receipts(
    workspace: AuthorWorkspace,
) -> dict[str, Any]:
    """读取当前运行回执账；原始回包正文不在此账中。"""
    workspace = _validate_workspace(workspace)
    state = _read_run_ledger_state(workspace)
    return {
        "version": state["version"],
        "sha256": state["sha256"],
        "runs": copy.deepcopy(state["payload"]["runs"]),
    }


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


def read_current_complete_fact_candidates(
    workspace: AuthorWorkspace,
) -> dict[str, Any]:
    """只返回被 current ``COMPLETE`` 回执精确绑定的 C3。"""
    workspace = _validate_workspace(workspace)
    candidates_before = workspace.read(FACT_CANDIDATES_KEY)
    runs_before = workspace.read(FACT_CANDIDATE_RUNS_KEY)
    if candidates_before is None:
        raise ExtractWorkspaceError("FACT_CANDIDATES_STATE_MISSING")
    if runs_before is None:
        raise ExtractWorkspaceError("FACT_CANDIDATES_COMPLETE_RECEIPT_MISSING")
    candidates_before = _validate_state_entry(candidates_before, "FACT_CANDIDATES")
    runs_before = _validate_state_entry(runs_before, "FACT_CANDIDATE_RUNS")
    payload = read_current_fact_candidates(workspace)
    try:
        ledger = extract_run_receipt.validate_ledger(runs_before["payload"])
    except extract_run_receipt.ExtractRunReceiptError as exc:
        raise ExtractWorkspaceError(
            f"FACT_CANDIDATE_RUN_LEDGER_INVALID:{exc}"
        ) from exc

    candidates_after = workspace.read(FACT_CANDIDATES_KEY)
    runs_after = workspace.read(FACT_CANDIDATE_RUNS_KEY)
    if candidates_after is None or runs_after is None:
        raise FactCandidatesStaleError("FACT_CANDIDATES_COMPLETE_GATE_CHANGED")
    candidates_after = _validate_state_entry(candidates_after, "FACT_CANDIDATES")
    runs_after = _validate_state_entry(runs_after, "FACT_CANDIDATE_RUNS")
    before_watermark = (
        candidates_before["version"],
        candidates_before["sha256"],
        runs_before["version"],
        runs_before["sha256"],
    )
    after_watermark = (
        candidates_after["version"],
        candidates_after["sha256"],
        runs_after["version"],
        runs_after["sha256"],
    )
    if before_watermark != after_watermark:
        raise FactCandidatesStaleError("FACT_CANDIDATES_COMPLETE_GATE_CHANGED")

    matching = [
        receipt
        for receipt in ledger["runs"]
        if receipt["completion_state"] == extract_run_receipt.COMPLETE
        and receipt["candidate_snapshot"]
        == {
            "version": candidates_after["version"],
            "sha256": candidates_after["sha256"],
        }
        and receipt["source_identity"] == payload["source_identity"]
        and receipt["responses_identity"] == payload["responses_identity"]
    ]
    if len(matching) != 1:
        raise ExtractWorkspaceError("FACT_CANDIDATES_COMPLETE_RECEIPT_MISSING")
    return payload
