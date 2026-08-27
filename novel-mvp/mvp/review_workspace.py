"""M5 作者审查动作到 AuthorWorkspace facts 的原子适配器。

只接已绑定 AuthorWorkspace 能力句柄；不接路径、作者 ID、项目 ID，
不调用 legacy writer，也不做 reconcile。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from . import fact_workspace, factstore, review_tool
from .workspace import (
    AuthorWorkspace,
    OperationConflictError,
    VersionConflictError,
)


LOGICAL_KEY = "facts"
REVIEW_RUNS_KEY = "fact_review_runs"
REVIEW_RUNS_SCHEMA = "s2-author-review-ledger-v1"
S2_GUARD_KEYS = (
    "fact_candidates",
    "fact_candidate_runs",
    "fact_materialization_runs",
    "segments",
    "chapter_index",
)
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


def _internal_author_review_operation_id(operation_id: str) -> str:
    digest = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()
    return f"s2-author-review-{digest}"


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _empty_review_runs() -> dict[str, Any]:
    return {
        "schema": REVIEW_RUNS_SCHEMA,
        "authorizations": [],
        "saves": [],
    }


def _ledger_invalid() -> None:
    raise ReviewWorkspaceError("AUTHOR_REVIEW_LEDGER_INVALID")


def _facts_identity(value: object) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "sha256"}
        or not isinstance(value.get("version"), int)
        or isinstance(value.get("version"), bool)
        or value["version"] < 1
        or not isinstance(value.get("sha256"), str)
        or review_tool.SHA256_RE.fullmatch(value["sha256"]) is None
    ):
        _ledger_invalid()
    return copy.deepcopy(value)


def _request_ref_projection(value: object) -> object:
    keys = (
        "record_type",
        "record_id",
        "record_version",
        "record_hash",
        "access",
        "source_module",
    )
    if not isinstance(value, Mapping):
        return copy.deepcopy(value)
    return {
        key: copy.deepcopy(value[key]) if key in value else {"missing": key}
        for key in keys
    }


def _stored_fact_candidates_ref(value: object) -> dict[str, Any]:
    try:
        normalized = (
            fact_workspace.extract_workspace._require_fact_candidates_foreign_ref(
                value
            )
        )
    except (fact_workspace.extract_workspace.ExtractWorkspaceError, TypeError):
        _ledger_invalid()
    if value != normalized:
        _ledger_invalid()
    return normalized


def _materialization_ledger(workspace: AuthorWorkspace) -> dict[str, Any]:
    state = workspace.read("fact_materialization_runs")
    if state is None:
        raise ReviewWorkspaceError("AUTHOR_REVIEW_MATERIALIZATION_MISSING")
    try:
        return fact_workspace._validated_materialization_ledger(state["payload"])
    except (fact_workspace.FactWorkspaceError, KeyError, TypeError) as exc:
        raise ReviewWorkspaceError("AUTHOR_REVIEW_MATERIALIZATION_INVALID") from exc


def _validate_review_runs_payload(
    workspace: AuthorWorkspace, payload: object
) -> dict[str, Any]:
    try:
        if (
            not isinstance(payload, dict)
            or set(payload) != {"schema", "authorizations", "saves"}
            or payload.get("schema") != REVIEW_RUNS_SCHEMA
            or not isinstance(payload.get("authorizations"), list)
            or not isinstance(payload.get("saves"), list)
            or len(payload["authorizations"]) != len(payload["saves"])
        ):
            _ledger_invalid()
        materialization = _materialization_ledger(workspace)
        m4_by_operation = {
            row["operation_id"]: row for row in materialization["operations"]
        }
        previous_saves: dict[str, dict[str, Any]] = {}
        seen_operation_ids: set[str] = set()
        authorizations: list[dict[str, Any]] = []
        saves: list[dict[str, Any]] = []
        for authorization, save in zip(
            payload["authorizations"], payload["saves"], strict=True
        ):
            if (
                not isinstance(authorization, dict)
                or set(authorization)
                != {
                    "operation_id",
                    "request_sha256",
                    "actor",
                    "fact_candidates_ref",
                    "facts_before",
                    "chapter_batch_evidence",
                    "lineage_anchor",
                    "actions",
                }
                or not isinstance(save, dict)
                or set(save)
                != {
                    "operation_id",
                    "authorization_sha256",
                    "facts_before",
                    "facts_after",
                    "facts_after_payload",
                    "results",
                }
            ):
                _ledger_invalid()
            operation_id = authorization["operation_id"]
            if (
                not isinstance(operation_id, str)
                or BATCH_OPERATION_ID_RE.fullmatch(operation_id) is None
                or operation_id in seen_operation_ids
                or save["operation_id"] != operation_id
                or authorization["actor"] != "author"
            ):
                _ledger_invalid()
            seen_operation_ids.add(operation_id)
            ref = _stored_fact_candidates_ref(
                authorization["fact_candidates_ref"]
            )
            facts_before = _facts_identity(authorization["facts_before"])
            facts_after = _facts_identity(save["facts_after"])
            facts_after_payload = factstore.validate_c4_v1_snapshot(
                save["facts_after_payload"]
            )
            if (
                _facts_identity(save["facts_before"]) != facts_before
                or facts_after["version"] != facts_before["version"] + 1
                or _sha256(facts_after_payload) != facts_after["sha256"]
            ):
                _ledger_invalid()
            facts_after_by_ref = {
                fact["id"]: fact for fact in facts_after_payload
            }

            evidence = authorization["chapter_batch_evidence"]
            if (
                not isinstance(evidence, dict)
                or set(evidence)
                != {
                    "scope",
                    "materialization_operation_id",
                    "target_chapter_ids",
                    "fact_candidates",
                }
                or evidence["scope"] != "CHAPTER_BATCH_ONLY"
                or not isinstance(evidence["target_chapter_ids"], list)
                or not evidence["target_chapter_ids"]
                or any(
                    not isinstance(chapter_id, str) or not chapter_id
                    for chapter_id in evidence["target_chapter_ids"]
                )
                or len(evidence["target_chapter_ids"])
                != len(set(evidence["target_chapter_ids"]))
            ):
                _ledger_invalid()
            evidence_identity = _facts_identity(evidence["fact_candidates"])
            if evidence_identity != {
                "version": ref["record_version"],
                "sha256": ref["record_hash"],
            }:
                _ledger_invalid()
            evidence_m4 = m4_by_operation.get(
                evidence["materialization_operation_id"]
            )
            if (
                evidence_m4 is None
                or not set(evidence["target_chapter_ids"]).issubset(
                    set(evidence_m4["added_chapter_ids"])
                )
                or evidence_m4["source_identity"].get("fact_candidates")
                != evidence_identity
            ):
                _ledger_invalid()

            anchor = authorization["lineage_anchor"]
            if (
                not isinstance(anchor, dict)
                or set(anchor) != {"kind", "operation_id", "facts_identity"}
                or _facts_identity(anchor["facts_identity"]) != facts_before
            ):
                _ledger_invalid()
            if anchor["kind"] == "M4_FACTS_SNAPSHOT":
                anchor_m4 = m4_by_operation.get(anchor["operation_id"])
                if anchor_m4 is None or anchor_m4["facts_snapshot"] != facts_before:
                    _ledger_invalid()
            elif anchor["kind"] == "S2_SAVE":
                anchor_save = previous_saves.get(anchor["operation_id"])
                if anchor_save is None or anchor_save["facts_after"] != facts_before:
                    _ledger_invalid()
            else:
                _ledger_invalid()

            if not isinstance(authorization["actions"], list):
                _ledger_invalid()
            explicit_actions = []
            for action_record in authorization["actions"]:
                if (
                    not isinstance(action_record, dict)
                    or set(action_record)
                    != {
                        "operation_id",
                        "kind",
                        "fact_ref",
                        "decided_at",
                        "chapter_revision_ref",
                        "action_sha256",
                        "action",
                    }
                ):
                    _ledger_invalid()
                action = review_tool.validate_review_action(
                    action_record["action"]
                )
                if (
                    action_record["operation_id"] != action["operation_id"]
                    or action_record["fact_ref"] != action["fact_ref"]
                    or action_record["action_sha256"] != _sha256(action)
                ):
                    _ledger_invalid()
                explicit_actions.append(
                    {
                        "action": action,
                        "chapter_revision_ref": copy.deepcopy(
                            action_record["chapter_revision_ref"]
                        ),
                        "decided_at": action_record["decided_at"],
                    }
                )
            validated_actions = _validate_batch_review_actions(explicit_actions)
            if validated_actions != explicit_actions:
                _ledger_invalid()

            if (
                not isinstance(save["results"], list)
                or len(save["results"]) != len(authorization["actions"])
            ):
                _ledger_invalid()
            for action_record, result in zip(
                authorization["actions"], save["results"], strict=True
            ):
                if (
                    not isinstance(result, dict)
                    or set(result)
                    != {
                        "operation_id",
                        "kind",
                        "fact_ref",
                        "before_status",
                        "after_status",
                        "before_fact_sha256",
                        "after_fact_sha256",
                    }
                    or result["operation_id"] != action_record["operation_id"]
                    or result["fact_ref"] != action_record["fact_ref"]
                    or result["kind"] != action_record["kind"]
                    or result["before_status"] not in factstore.FACT_STATUSES
                    or result["after_status"] not in factstore.FACT_STATUSES
                    or result["before_fact_sha256"]
                    != action_record["action"]["expected_fact_sha256"]
                    or review_tool.SHA256_RE.fullmatch(
                        result["after_fact_sha256"]
                    )
                    is None
                ):
                    _ledger_invalid()
                persisted_fact_after = facts_after_by_ref.get(result["fact_ref"])
                if (
                    persisted_fact_after is None
                    or persisted_fact_after["status"] != result["after_status"]
                    or factstore.fact_sha256(persisted_fact_after)
                    != result["after_fact_sha256"]
                ):
                    _ledger_invalid()
                expected_kind = _audit_kind(
                    action_record["action"],
                    {"status": result["before_status"]},
                )
                decision = action_record["action"]["decision"]
                expected_after = (
                    factstore.STATUS_CONFIRMED
                    if decision in {"confirm", "edit_and_confirm"}
                    else factstore.STATUS_REJECTED
                    if decision == "reject"
                    else result["before_status"]
                )
                if (
                    action_record["kind"] != expected_kind
                    or action_record["action"]["expected_status"]
                    != result["before_status"]
                    or result["after_status"] != expected_after
                ):
                    _ledger_invalid()

            expected_request_sha = _review_request_sha256(
                operation_id=operation_id,
                actor="author",
                review_actions=explicit_actions,
                fact_candidates_ref=ref,
                expected_facts_version=facts_before["version"],
                expected_facts_sha256=facts_before["sha256"],
            )
            if (
                authorization["request_sha256"] != expected_request_sha
                or save["authorization_sha256"] != _sha256(authorization)
            ):
                _ledger_invalid()
            authorization_copy = copy.deepcopy(authorization)
            save_copy = copy.deepcopy(save)
            authorizations.append(authorization_copy)
            saves.append(save_copy)
            previous_saves[operation_id] = save_copy
        return {
            "schema": REVIEW_RUNS_SCHEMA,
            "authorizations": authorizations,
            "saves": saves,
        }
    except ReviewWorkspaceError as exc:
        if str(exc) == "AUTHOR_REVIEW_LEDGER_INVALID":
            raise
        raise ReviewWorkspaceError("AUTHOR_REVIEW_LEDGER_INVALID") from exc
    except (KeyError, TypeError, ValueError, factstore.FactstoreError) as exc:
        raise ReviewWorkspaceError("AUTHOR_REVIEW_LEDGER_INVALID") from exc


def _read_review_runs_state(workspace: AuthorWorkspace) -> dict[str, Any]:
    state = workspace.read(REVIEW_RUNS_KEY)
    if state is None:
        return {
            "version": 0,
            "sha256": None,
            "payload": _empty_review_runs(),
        }
    payload = _validate_review_runs_payload(workspace, state.get("payload"))
    return {
        "version": state["version"],
        "sha256": state["sha256"],
        "payload": payload,
    }


def _review_request_sha256(
    *,
    operation_id: str,
    actor: str,
    review_actions: list[dict[str, Any]],
    fact_candidates_ref: object,
    expected_facts_version: int,
    expected_facts_sha256: str,
) -> str:
    return _sha256(
        {
            "operation_id": operation_id,
            "actor": actor,
            "review_actions": review_actions,
            "fact_candidates_ref": _request_ref_projection(fact_candidates_ref),
            "expected_facts_version": expected_facts_version,
            "expected_facts_sha256": expected_facts_sha256,
        }
    )


def _existing_author_review(
    state: dict[str, Any], operation_id: str, request_sha256: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    authorizations = [
        row
        for row in state["payload"]["authorizations"]
        if row["operation_id"] == operation_id
    ]
    saves = [
        row
        for row in state["payload"]["saves"]
        if row["operation_id"] == operation_id
    ]
    if not authorizations and not saves:
        return None
    if len(authorizations) != 1 or len(saves) != 1:
        raise ReviewWorkspaceError("AUTHOR_REVIEW_LEDGER_INVALID")
    if authorizations[0].get("request_sha256") != request_sha256:
        raise OperationConflictError("OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST")
    if saves[0].get("authorization_sha256") != _sha256(authorizations[0]):
        raise ReviewWorkspaceError("AUTHOR_REVIEW_LEDGER_INVALID")
    return copy.deepcopy(authorizations[0]), copy.deepcopy(saves[0])


def _state_guard(workspace: AuthorWorkspace, logical_key: str) -> dict[str, Any]:
    state = workspace.read(logical_key)
    if state is None:
        raise ReviewWorkspaceError(f"AUTHOR_REVIEW_SOURCE_MISSING:{logical_key}")
    return {"version": state["version"], "sha256": state["sha256"]}


def _source_watermark(workspace: AuthorWorkspace) -> dict[str, Any]:
    watermark: dict[str, Any] = {}
    for logical_key in S2_GUARD_KEYS:
        state = workspace.read(logical_key)
        watermark[logical_key] = (
            None
            if state is None
            else {"version": state["version"], "sha256": state["sha256"]}
        )
    return watermark


def _chapter_batch_evidence(
    workspace: AuthorWorkspace,
    *,
    target_chapter_ids: set[str],
    fact_candidates_ref: dict[str, Any],
) -> dict[str, Any]:
    """只证明目标章节位于该 M4 批次，不证明候选与 f-ID 逐条对应。"""

    ledger = _materialization_ledger(workspace)
    matching = [
        operation
        for operation in ledger["operations"]
        if target_chapter_ids.issubset(set(operation["added_chapter_ids"]))
    ]
    if len(matching) != 1:
        raise ReviewWorkspaceError("AUTHOR_REVIEW_C4_BATCH_BINDING_MISSING")
    operation = matching[0]
    candidate_identity = operation["source_identity"].get("fact_candidates")
    expected_identity = {
        "version": fact_candidates_ref["record_version"],
        "sha256": fact_candidates_ref["record_hash"],
    }
    if candidate_identity != expected_identity:
        raise ReviewWorkspaceError("AUTHOR_REVIEW_C4_C3_BATCH_MISMATCH")
    return {
        "scope": "CHAPTER_BATCH_ONLY",
        "materialization_operation_id": operation["operation_id"],
        "target_chapter_ids": sorted(target_chapter_ids),
        "fact_candidates": expected_identity,
    }


def _lineage_anchor(
    workspace: AuthorWorkspace,
    current_identity: dict[str, Any],
    review_runs_state: dict[str, Any],
) -> dict[str, Any]:
    materialization = _materialization_ledger(workspace)
    if materialization["operations"]:
        latest_m4 = materialization["operations"][-1]
        if latest_m4["facts_snapshot"] == current_identity:
            return {
                "kind": "M4_FACTS_SNAPSHOT",
                "operation_id": latest_m4["operation_id"],
                "facts_identity": copy.deepcopy(current_identity),
            }
    saves = review_runs_state["payload"]["saves"]
    if saves and saves[-1]["facts_after"] == current_identity:
        return {
            "kind": "S2_SAVE",
            "operation_id": saves[-1]["operation_id"],
            "facts_identity": copy.deepcopy(current_identity),
        }
    raise ReviewWorkspaceError("AUTHOR_REVIEW_FACTS_LINEAGE_UNTRUSTED")


def _audit_kind(action: dict[str, Any], fact_before: dict[str, Any]) -> str:
    decision = action["decision"]
    if decision in {"confirm", "edit_and_confirm"}:
        return "confirm"
    if decision == "reject" and fact_before["status"] == factstore.STATUS_CONFIRMED:
        return "revoke"
    return decision


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


def apply_author_review_actions(
    workspace: AuthorWorkspace,
    *,
    operation_id: str,
    actor: str,
    review_actions: list[dict[str, Any]],
    fact_candidates_ref: object,
    expected_facts_version: int,
    expected_facts_sha256: str,
) -> dict[str, Any]:
    """S2：按显式 f-ID 清单执行作者动作，并原子保存两类审计记录。

    这里只证明目标章节来自指定 C3 批次，并证明整份 facts 沿 M4/S2 连续演进；
    不建立、也不声称存在单条 C3 候选到 f-ID 的映射。
    """

    workspace = _require_workspace(workspace)
    if (
        not isinstance(operation_id, str)
        or BATCH_OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        raise ReviewWorkspaceError("AUTHOR_REVIEW_OPERATION_ID_INVALID")
    if actor != "author":
        raise ReviewWorkspaceError("AUTHOR_REVIEW_ACTOR_MUST_BE_AUTHOR")
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

    request_sha = _review_request_sha256(
        operation_id=operation_id,
        actor=actor,
        review_actions=explicit_actions,
        fact_candidates_ref=fact_candidates_ref,
        expected_facts_version=expected_facts_version,
        expected_facts_sha256=expected_facts_sha256,
    )
    review_runs_state = _read_review_runs_state(workspace)
    existing = _existing_author_review(
        review_runs_state, operation_id, request_sha
    )
    if existing is not None:
        authorization_record, save_record = existing
        # 重放不是永久通行证：同请求冲突先判完，再重新通过当前 S1 与章节批次证据。
        replay_source_before = _source_watermark(workspace)
        fact_workspace.read_fact_candidates_by_ref(
            workspace, fact_candidates_ref
        )
        replay_evidence = _chapter_batch_evidence(
            workspace,
            target_chapter_ids=set(
                authorization_record["chapter_batch_evidence"][
                    "target_chapter_ids"
                ]
            ),
            fact_candidates_ref=authorization_record["fact_candidates_ref"],
        )
        if replay_evidence != authorization_record["chapter_batch_evidence"]:
            raise ReviewWorkspaceError("AUTHOR_REVIEW_LEDGER_INVALID")
        replay_facts = workspace.read(LOGICAL_KEY)
        if replay_facts is None:
            raise ReviewWorkspaceError("FACTS_SNAPSHOT_MISSING")
        factstore.validate_c4_v1_snapshot(replay_facts["payload"])
        _lineage_anchor(
            workspace,
            {
                "version": replay_facts["version"],
                "sha256": replay_facts["sha256"],
            },
            review_runs_state,
        )
        if _source_watermark(workspace) != replay_source_before:
            raise ReviewWorkspaceError("AUTHOR_REVIEW_SOURCE_CHANGED_DURING_READ")
        return {
            "status": "COMMITTED",
            "operation_id": operation_id,
            "facts_version": save_record["facts_after"]["version"],
            "facts_sha256": save_record["facts_after"]["sha256"],
            "authorization_record": authorization_record,
            "save_record": save_record,
            "results": copy.deepcopy(save_record["results"]),
            "replayed": True,
        }

    # 六字段规则只由 S1 的公开读入口解释；S2 不复制、放宽或改名。
    source_before = _source_watermark(workspace)
    candidates_payload = fact_workspace.read_fact_candidates_by_ref(
        workspace, fact_candidates_ref
    )
    normalized_ref = _request_ref_projection(fact_candidates_ref)
    if not isinstance(normalized_ref, dict):  # S1 已拒绝；只为类型收窄。
        raise ReviewWorkspaceError("AUTHOR_REVIEW_FACT_CANDIDATES_REF_INVALID")

    current = workspace.read(LOGICAL_KEY)
    if current is None:
        raise ReviewWorkspaceError("FACTS_SNAPSHOT_MISSING")
    facts = factstore.validate_c4_v1_snapshot(current["payload"])
    if not facts:
        raise ReviewWorkspaceError("FACTS_SNAPSHOT_EMPTY")
    if current["version"] != expected_facts_version:
        raise VersionConflictError("VERSION_CONFLICT")
    if current["sha256"] != expected_facts_sha256:
        raise VersionConflictError("SHA_CONFLICT")

    facts_by_ref = {fact["id"]: fact for fact in facts}
    target_facts = [
        facts_by_ref[action["action"]["fact_ref"]]
        for action in explicit_actions
        if action["action"]["fact_ref"] in facts_by_ref
    ]
    if len(target_facts) != len(explicit_actions):
        raise ReviewWorkspaceError("FACT_REVIEW_TARGET_NOT_FOUND")
    chapter_evidence = _chapter_batch_evidence(
        workspace,
        target_chapter_ids={fact["chapter_id"] for fact in target_facts},
        fact_candidates_ref=normalized_ref,
    )
    facts_before_identity = {
        "version": current["version"],
        "sha256": current["sha256"],
    }
    lineage_anchor = _lineage_anchor(
        workspace, facts_before_identity, review_runs_state
    )

    batch_result = review_tool.execute_batch(
        {
            "snapshot_version": current["version"],
            "snapshot_sha256": current["sha256"],
            "facts": facts,
            "items": explicit_actions,
        }
    )
    facts_after = batch_result["facts"]
    actions_audit = []
    results = []
    for explicit, receipt in zip(
        explicit_actions, batch_result["receipts"], strict=True
    ):
        action = explicit["action"]
        fact_before = facts_by_ref[action["fact_ref"]]
        kind = _audit_kind(action, fact_before)
        actions_audit.append(
            {
                "operation_id": action["operation_id"],
                "kind": kind,
                "fact_ref": action["fact_ref"],
                "decided_at": explicit["decided_at"],
                "chapter_revision_ref": copy.deepcopy(
                    explicit["chapter_revision_ref"]
                ),
                "action_sha256": _sha256(action),
                "action": copy.deepcopy(action),
            }
        )
        results.append(
            {
                "operation_id": action["operation_id"],
                "kind": kind,
                "fact_ref": action["fact_ref"],
                "before_status": receipt["before_status"],
                "after_status": receipt["after_status"],
                "before_fact_sha256": receipt["before_fact_sha256"],
                "after_fact_sha256": receipt["after_fact_sha256"],
            }
        )

    facts_after_identity = {
        "version": current["version"] + 1,
        "sha256": _sha256(facts_after),
    }
    authorization_record = {
        "operation_id": operation_id,
        "request_sha256": request_sha,
        "actor": actor,
        "fact_candidates_ref": normalized_ref,
        "facts_before": facts_before_identity,
        "chapter_batch_evidence": chapter_evidence,
        "lineage_anchor": lineage_anchor,
        "actions": actions_audit,
    }
    save_record = {
        "operation_id": operation_id,
        "authorization_sha256": _sha256(authorization_record),
        "facts_before": facts_before_identity,
        "facts_after": facts_after_identity,
        "facts_after_payload": copy.deepcopy(facts_after),
        "results": results,
    }
    ledger_after = copy.deepcopy(review_runs_state["payload"])
    ledger_after["authorizations"].append(authorization_record)
    ledger_after["saves"].append(save_record)
    guards = {key: _state_guard(workspace, key) for key in S2_GUARD_KEYS}
    if guards != source_before:
        raise ReviewWorkspaceError("AUTHOR_REVIEW_SOURCE_CHANGED_DURING_READ")
    if guards["fact_candidates"] != {
        "version": normalized_ref["record_version"],
        "sha256": normalized_ref["record_hash"],
    }:
        raise ReviewWorkspaceError("AUTHOR_REVIEW_C3_CHANGED_DURING_READ")
    source_identity = candidates_payload["source_identity"]
    for key in ("segments", "chapter_index"):
        if guards[key] != source_identity[key]:
            raise ReviewWorkspaceError(
                "AUTHOR_REVIEW_C3_SOURCE_CHANGED_DURING_READ"
            )
    committed = workspace.commit_guarded(
        _internal_author_review_operation_id(operation_id),
        {LOGICAL_KEY: facts_after, REVIEW_RUNS_KEY: ledger_after},
        {
            LOGICAL_KEY: facts_before_identity,
            REVIEW_RUNS_KEY: {
                "version": review_runs_state["version"],
                "sha256": review_runs_state["sha256"],
            },
        },
        guards,
    )
    return {
        "status": committed["status"],
        "operation_id": operation_id,
        "facts_version": committed["versions"][LOGICAL_KEY],
        "facts_sha256": committed["payload_sha256"][LOGICAL_KEY],
        "authorization_record": copy.deepcopy(authorization_record),
        "save_record": copy.deepcopy(save_record),
        "results": copy.deepcopy(results),
        "replayed": committed["replayed"],
    }


def read_author_review_records(workspace: AuthorWorkspace) -> dict[str, Any]:
    """公开只读返回作者授权记录与对应保存结果，不修改任何工作区状态。"""

    workspace = _require_workspace(workspace)
    state = _read_review_runs_state(workspace)
    return {
        "version": state["version"],
        "sha256": state["sha256"],
        "authorizations": copy.deepcopy(state["payload"]["authorizations"]),
        "saves": copy.deepcopy(state["payload"]["saves"]),
    }
