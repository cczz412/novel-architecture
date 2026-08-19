"""M5 作者审查动作到 AuthorWorkspace facts 的原子适配器。

只接已绑定 AuthorWorkspace 能力句柄；不接路径、作者 ID、项目 ID，
不调用 legacy writer，也不做 reconcile。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from . import factstore, review_tool
from .workspace import AuthorWorkspace, VersionConflictError


LOGICAL_KEY = "facts"
REVIEW_ACTION_KEYS = {"action", "chapter_revision_ref", "decided_at"}
CHAPTER_REVISION_REF_KEYS = {
    "chapter_id",
    "revision_no",
    "revision_text_sha256",
}
BATCH_OPERATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


class ReviewWorkspaceError(factstore.FactstoreError):
    """workspace 审查适配输入或当前快照不满足执行前提。"""


def _require_workspace(value: Any) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        raise ReviewWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _internal_operation_id(operation_id: str, review_action: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        _canonical_bytes(
            {"operation_id": operation_id, "review_action": review_action}
        )
    ).hexdigest()
    return f"m5-review-{digest}"


def _internal_batch_operation_id(
    operation_id: str,
    review_actions: list[dict[str, Any]],
    expected_facts_version: int,
    expected_facts_sha256: str,
) -> str:
    digest = hashlib.sha256(
        _canonical_bytes(
            {
                "operation_id": operation_id,
                "review_actions": review_actions,
                "expected_facts_version": expected_facts_version,
                "expected_facts_sha256": expected_facts_sha256,
            }
        )
    ).hexdigest()
    return f"m5-review-batch-{digest}"


def _validate_explicit_review_action(
    operation_id: str,
    value: Any,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REVIEW_ACTION_KEYS:
        raise ReviewWorkspaceError("REVIEW_WORKSPACE_ACTION_SCHEMA_MISMATCH")
    action = review_tool.validate_review_action(value["action"])
    if action["operation_id"] != operation_id:
        raise ReviewWorkspaceError("REVIEW_OPERATION_ID_MISMATCH")
    decided_at = value["decided_at"]
    if not isinstance(decided_at, str) or not decided_at.strip():
        raise ReviewWorkspaceError("FACT_REVIEW_DECIDED_AT_INVALID")
    revision_ref = value["chapter_revision_ref"]
    if not isinstance(revision_ref, dict):
        raise ReviewWorkspaceError("REVIEW_CHAPTER_REVISION_REF_INVALID")
    return {
        "action": action,
        "chapter_revision_ref": copy.deepcopy(revision_ref),
        "decided_at": decided_at,
    }


def _target_fact(facts: list[dict[str, Any]], action: dict[str, Any]) -> dict[str, Any]:
    matches = [fact for fact in facts if fact["id"] == action["fact_ref"]]
    if len(matches) != 1:
        raise ReviewWorkspaceError("FACT_REVIEW_TARGET_NOT_FOUND")
    return matches[0]


def _validate_batch_review_actions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ReviewWorkspaceError("REVIEW_WORKSPACE_BATCH_ITEMS_REQUIRED")
    validated: list[dict[str, Any]] = []
    seen_fact_refs: set[str] = set()
    seen_operation_ids: set[str] = set()
    batch_revision_ref: dict[str, Any] | None = None
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != REVIEW_ACTION_KEYS:
            raise ReviewWorkspaceError(
                f"REVIEW_WORKSPACE_BATCH_ITEM_SHAPE_INVALID:{index}"
            )
        action = review_tool.validate_review_action(item["action"])
        fact_ref = action["fact_ref"]
        action_operation_id = action["operation_id"]
        if fact_ref in seen_fact_refs:
            raise ReviewWorkspaceError("REVIEW_BATCH_FACT_REF_DUPLICATE")
        if action_operation_id in seen_operation_ids:
            raise ReviewWorkspaceError("REVIEW_BATCH_OPERATION_ID_DUPLICATE")
        decided_at = item["decided_at"]
        if not isinstance(decided_at, str) or not decided_at.strip():
            raise ReviewWorkspaceError("FACT_REVIEW_DECIDED_AT_INVALID")
        revision_ref = item["chapter_revision_ref"]
        if (
            not isinstance(revision_ref, dict)
            or set(revision_ref) != CHAPTER_REVISION_REF_KEYS
            or not isinstance(revision_ref.get("chapter_id"), str)
            or not revision_ref["chapter_id"]
            or not isinstance(revision_ref.get("revision_no"), int)
            or isinstance(revision_ref["revision_no"], bool)
            or revision_ref["revision_no"] < 1
            or not isinstance(revision_ref.get("revision_text_sha256"), str)
            or review_tool.SHA256_RE.fullmatch(
                revision_ref["revision_text_sha256"]
            )
            is None
        ):
            raise ReviewWorkspaceError(
                f"REVIEW_CHAPTER_REVISION_REF_INVALID:{index}"
            )
        if batch_revision_ref is None:
            batch_revision_ref = copy.deepcopy(revision_ref)
        elif revision_ref != batch_revision_ref:
            raise ReviewWorkspaceError("REVIEW_BATCH_CROSS_REVISION_SCOPE")
        seen_fact_refs.add(fact_ref)
        seen_operation_ids.add(action_operation_id)
        validated.append(
            {
                "action": action,
                "chapter_revision_ref": copy.deepcopy(revision_ref),
                "decided_at": decided_at,
            }
        )
    return validated


def apply_review(
    workspace: AuthorWorkspace,
    *,
    operation_id: str,
    review_action: dict[str, Any],
    expected_facts_version: int,
) -> dict[str, Any]:
    """读取 current facts，执行显式作者动作，并用一次 workspace.commit 写回。"""
    workspace = _require_workspace(workspace)
    explicit = _validate_explicit_review_action(operation_id, review_action)
    if (
        not isinstance(expected_facts_version, int)
        or isinstance(expected_facts_version, bool)
        or expected_facts_version <= 0
    ):
        raise ReviewWorkspaceError("FACTS_EXPECTED_VERSION_INVALID")
    current = workspace.read(LOGICAL_KEY)
    if current is None:
        raise ReviewWorkspaceError("FACTS_SNAPSHOT_MISSING")
    facts = factstore.validate_c4_v1_snapshot(current["payload"])
    if not facts:
        raise ReviewWorkspaceError("FACTS_SNAPSHOT_EMPTY")
    target = _target_fact(facts, explicit["action"])
    if target["chapter_revision_ref"] != explicit["chapter_revision_ref"]:
        raise ReviewWorkspaceError("STALE_CHAPTER_REVISION_REF")

    internal_operation_id = _internal_operation_id(operation_id, explicit)
    if current["version"] == expected_facts_version:
        review_result = review_tool.execute(
            {
                "snapshot_version": current["version"],
                "expected_snapshot_version": expected_facts_version,
                "expected_snapshot_sha256": current["sha256"],
                "facts": facts,
                "chapter_revision_ref": explicit["chapter_revision_ref"],
                "action": explicit["action"],
                "decided_at": explicit["decided_at"],
            }
        )
        facts_after = review_result["facts"]
        review_receipt = review_result["receipt"]
    elif current["version"] == expected_facts_version + 1:
        # 精确重复时，当前 payload 就是第一次 commit 的 mutation；交给 workspace 回放。
        facts_after = facts
        review_receipt = {
            "status": "REPLAY_CANDIDATE",
            "operation_id": operation_id,
            "fact_ref": explicit["action"]["fact_ref"],
            "decision": explicit["action"]["decision"],
        }
    else:
        raise VersionConflictError("VERSION_CONFLICT")

    storage_receipt = workspace.commit(
        internal_operation_id,
        {LOGICAL_KEY: facts_after},
        {LOGICAL_KEY: expected_facts_version},
    )
    return {
        "status": storage_receipt["status"],
        "operation_id": operation_id,
        "facts_version": storage_receipt["versions"][LOGICAL_KEY],
        "facts_sha256": storage_receipt["payload_sha256"][LOGICAL_KEY],
        "facts": copy.deepcopy(facts_after),
        "review_receipt": copy.deepcopy(review_receipt),
        "replayed": storage_receipt["replayed"],
    }


def apply_review_batch(
    workspace: AuthorWorkspace,
    *,
    operation_id: str,
    review_actions: list[dict[str, Any]],
    expected_facts_version: int,
    expected_facts_sha256: str,
) -> dict[str, Any]:
    """整批内存计算完成后，只用一次 workspace.commit 替换 facts。"""

    workspace = _require_workspace(workspace)
    if (
        not isinstance(operation_id, str)
        or BATCH_OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        raise ReviewWorkspaceError("REVIEW_BATCH_OPERATION_ID_INVALID")
    explicit_actions = _validate_batch_review_actions(review_actions)
    if (
        not isinstance(expected_facts_version, int)
        or isinstance(expected_facts_version, bool)
        or expected_facts_version <= 0
    ):
        raise ReviewWorkspaceError("FACTS_EXPECTED_VERSION_INVALID")
    if (
        not isinstance(expected_facts_sha256, str)
        or review_tool.SHA256_RE.fullmatch(expected_facts_sha256) is None
    ):
        raise ReviewWorkspaceError("FACTS_EXPECTED_SHA256_INVALID")
    current = workspace.read(LOGICAL_KEY)
    if current is None:
        raise ReviewWorkspaceError("FACTS_SNAPSHOT_MISSING")
    facts = factstore.validate_c4_v1_snapshot(current["payload"])
    if not facts:
        raise ReviewWorkspaceError("FACTS_SNAPSHOT_EMPTY")
    internal_operation_id = _internal_batch_operation_id(
        operation_id,
        explicit_actions,
        expected_facts_version,
        expected_facts_sha256,
    )
    if current["version"] == expected_facts_version:
        if current["sha256"] != expected_facts_sha256:
            raise VersionConflictError("SHA_CONFLICT")
        batch_result = review_tool.execute_batch(
            {
                "snapshot_version": current["version"],
                "snapshot_sha256": current["sha256"],
                "facts": facts,
                "items": explicit_actions,
            }
        )
        facts_after = batch_result["facts"]
        receipts = batch_result["receipts"]
        applied_count = batch_result["applied_count"]
    elif current["version"] == expected_facts_version + 1:
        # 精确重放由 workspace 已持久化 receipt 判定；不对已变更事实重放动作。
        facts_after = facts
        receipts = [
            {
                "status": "REPLAY_CANDIDATE",
                "operation_id": item["action"]["operation_id"],
                "fact_ref": item["action"]["fact_ref"],
                "decision": item["action"]["decision"],
            }
            for item in explicit_actions
        ]
        applied_count = 0
    else:
        raise VersionConflictError("VERSION_CONFLICT")

    storage_receipt = workspace.commit(
        internal_operation_id,
        {LOGICAL_KEY: facts_after},
        {
            LOGICAL_KEY: {
                "version": expected_facts_version,
                "sha256": expected_facts_sha256,
            }
        },
    )
    return {
        "status": storage_receipt["status"],
        "operation_id": operation_id,
        "facts_version": storage_receipt["versions"][LOGICAL_KEY],
        "facts_sha256": storage_receipt["payload_sha256"][LOGICAL_KEY],
        "facts": copy.deepcopy(facts_after),
        "receipts": copy.deepcopy(receipts),
        "input_count": len(explicit_actions),
        "applied_count": applied_count,
        "replayed": storage_receipt["replayed"],
    }
