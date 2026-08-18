"""M4/M5 事实变更的唯一事务入口。

本模块不判断事实真假。它只把作者已经明确的确认／驳回／改写动作，
以及既有 facts 准入结果，交给 planstore 的跨文件事务协调器提交。
"""

from __future__ import annotations

import copy
import re
import uuid
from pathlib import Path
from typing import Any

try:
    from . import planstore
except ImportError:  # pragma: no cover - 直接运行脚本时使用
    import planstore  # type: ignore[no-redef]


STATUS_EXTRACTED = "extracted"
STATUS_CONFIRMED = "confirmed"
STATUS_REJECTED = "rejected"
FACT_STATUSES = {STATUS_EXTRACTED, STATUS_CONFIRMED, STATUS_REJECTED}
ACTION_KEYS = {
    "contract",
    "version",
    "operation_id",
    "actor",
    "fact_ref",
    "expected_status",
    "expected_fact_sha256",
    "decision",
    "replacement_text",
    "note",
}
DECISIONS = {"confirm", "reject", "edit", "edit_and_confirm"}
FAULT_POINTS = {
    "after_prepare",
    "after_facts",
    "after_plan",
    "after_blob",
    "during_history",
    "after_history",
    "before_commit",
    "after_commit",
}
FACT_ID_RE = re.compile(r"f(\d+)$")


class FactstoreError(planstore.PlanstoreError):
    """事实动作在写前或恢复时被拒绝。"""


def allocate_fact_ids(facts: list[dict[str, Any]], count: int) -> list[str]:
    """从现有最大 f 号顺延，逐个查重。"""
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise FactstoreError("FACT_ID_COUNT_INVALID")
    used = {
        item.get("id")
        for item in facts
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    numbers = [
        int(match.group(1))
        for item in facts
        if isinstance(item, dict)
        for match in [FACT_ID_RE.fullmatch(str(item.get("id") or ""))]
        if match is not None
    ]
    next_number = max(numbers, default=0) + 1
    result: list[str] = []
    while len(result) < count:
        fact_ref = f"f{next_number:03d}"
        if fact_ref not in used:
            result.append(fact_ref)
            used.add(fact_ref)
        next_number += 1
    return result


def fact_sha256(fact: dict[str, Any]) -> str:
    return planstore._sha256_json(fact)


def new_operation_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _validate_facts(facts: Any) -> list[dict[str, Any]]:
    if not isinstance(facts, list) or any(not isinstance(item, dict) for item in facts):
        raise FactstoreError("C4_FACTS_NOT_LIST")
    refs = [item.get("id") for item in facts]
    if any(not isinstance(ref, str) or FACT_ID_RE.fullmatch(ref) is None for ref in refs):
        raise FactstoreError("C4_FACT_ID_INVALID")
    if len(refs) != len(set(refs)):
        raise FactstoreError("C4_FACT_ID_DUPLICATE")
    if any(item.get("status") not in FACT_STATUSES for item in facts):
        raise FactstoreError("C4_FACT_STATUS_INVALID")
    return facts


def _validate_review_action(action: Any) -> None:
    if not isinstance(action, dict) or set(action) != ACTION_KEYS:
        raise FactstoreError("FACT_REVIEW_ACTION_SCHEMA_MISMATCH")
    if action.get("contract") != "FACT_REVIEW_ACTION" or action.get("version") != "v1":
        raise FactstoreError("FACT_REVIEW_ACTION_IDENTITY_INVALID")
    if action.get("actor") != "author":
        raise FactstoreError("FACT_REVIEW_AUTHOR_REQUIRED")
    planstore._validate_operation_id(action.get("operation_id"))
    if not isinstance(action.get("fact_ref"), str) or FACT_ID_RE.fullmatch(action["fact_ref"]) is None:
        raise FactstoreError("FACT_REVIEW_FACT_REF_INVALID")
    if action.get("expected_status") not in FACT_STATUSES:
        raise FactstoreError("FACT_REVIEW_EXPECTED_STATUS_INVALID")
    if (
        not isinstance(action.get("expected_fact_sha256"), str)
        or planstore.SHA256_RE.fullmatch(action["expected_fact_sha256"]) is None
    ):
        raise FactstoreError("FACT_REVIEW_EXPECTED_SHA_INVALID")
    decision = action.get("decision")
    if decision not in DECISIONS:
        raise FactstoreError("FACT_REVIEW_DECISION_INVALID")
    if not isinstance(action.get("note"), str):
        raise FactstoreError("FACT_REVIEW_NOTE_INVALID")
    replacement = action.get("replacement_text")
    if decision in {"edit", "edit_and_confirm"}:
        if not isinstance(replacement, str) or not replacement.strip():
            raise FactstoreError("FACT_REVIEW_REPLACEMENT_REQUIRED")
    elif replacement is not None:
        raise FactstoreError("FACT_REVIEW_REPLACEMENT_FORBIDDEN")


def build_review_action(
    fact: dict[str, Any],
    *,
    decision: str,
    note: str = "",
    replacement_text: str | None = None,
    operation_id: str | None = None,
) -> dict[str, Any]:
    """供旧调用面构造与当前记录精确绑定的作者动作。"""
    action = {
        "contract": "FACT_REVIEW_ACTION",
        "version": "v1",
        "operation_id": operation_id or new_operation_id("op-m5-review"),
        "actor": "author",
        "fact_ref": fact.get("id"),
        "expected_status": fact.get("status"),
        "expected_fact_sha256": fact_sha256(fact),
        "decision": decision,
        "replacement_text": replacement_text,
        "note": note,
    }
    _validate_review_action(action)
    return action


def _history_row(
    *,
    operation_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
    timestamp: str,
    note: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    content_hash, blob = planstore._blob_record(before)
    return (
        {
            "ts": timestamp,
            "op": operation_id,
            "actor": "author",
            "action": "fact_basis_stale",
            "object_id": after["id"],
            "rev": after["rev"],
            "changes": {"edge_status": [before["edge_status"], after["edge_status"]]},
            "content_hash": content_hash,
            "note": note,
        },
        blob,
    )


def commit_facts_transaction_locked(
    root: Path,
    *,
    operation_id: str,
    action_name: str,
    request_sha256: str,
    facts_after: list[dict[str, Any]],
    plan_after: dict[str, Any] | None,
    history_rows: list[dict[str, Any]],
    blobs: list[dict[str, Any]],
    receipt: dict[str, Any],
    timestamp: str,
    fault_at: str | None = None,
    extra_replacements: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    """已经持有 `.planstore.lock` 时，唯一允许替换 facts.json 的底层入口。"""
    _validate_facts(facts_after)
    replacements = {
        "facts.json": planstore._canonical_bytes(facts_after),
        **(extra_replacements or {}),
    }
    if plan_after is not None:
        planstore._validate_plan(plan_after)
        replacements["plan.json"] = planstore._canonical_bytes(plan_after)
    appends = {}
    if history_rows:
        appends["plan_history.jsonl"] = b"".join(
            planstore._canonical_bytes(row) for row in history_rows
        )
    return planstore._commit_generic_transaction_locked(
        root,
        operation_id=operation_id,
        action_name=action_name,
        request_sha256=request_sha256,
        replacements=replacements,
        appends=appends,
        blobs=blobs,
        receipt=receipt,
        timestamp=timestamp,
        fault_at=fault_at,
    )


def _replayed_receipt(root: Path, operation_id: str) -> dict[str, Any]:
    prepare = next(
        (
            row
            for row in planstore._operation_rows(root, operation_id)
            if row.get("phase") == "prepare"
        ),
        None,
    )
    if prepare is None or not isinstance(prepare.get("receipt"), dict):
        raise FactstoreError("COMMITTED_FACT_REVIEW_RECEIPT_UNRESOLVABLE")
    return {**copy.deepcopy(prepare["receipt"]), "story_commit_seq": prepare["story_commit_seq"], "replayed": True}


def add_fact_candidates(
    project_dir: str | Path,
    *,
    chapter_id: str,
    items: list[dict[str, Any]],
    source: str,
    timestamp: str,
    operation_id: str | None = None,
) -> dict[str, Any]:
    """C3 候选仍只进 extracted，但与 M5 共用文件锁和恢复事务。"""
    if not isinstance(items, list) or not isinstance(source, str):
        raise FactstoreError("FACT_CANDIDATE_INPUT_INVALID")
    root = Path(project_dir)
    operation_id = operation_id or new_operation_id("op-m4-candidates")
    planstore._validate_operation_id(operation_id)
    valid = [
        item
        for item in items
        if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip()
    ]
    request_sha = planstore._sha256_json(
        {
            "chapter_id": chapter_id,
            "items": valid,
            "source": source,
            "timestamp": timestamp,
        }
    )
    with planstore._exclusive_lock(root):
        planstore._recover_pending_locked(root, timestamp=timestamp)
        status = planstore._operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            if status["request_sha256"] != request_sha:
                raise FactstoreError("OPERATION_ID_PAYLOAD_CONFLICT")
            return _replayed_receipt(root, operation_id)
        if status["terminal_phase"] == "rolled_back":
            raise FactstoreError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        if status["state"] == "NEEDS_MANUAL_RECOVERY":
            raise FactstoreError("OPERATION_NEEDS_MANUAL_RECOVERY")
        chapters = planstore._read_json(root / "chapters.json")
        if not isinstance(chapters, list) or chapter_id not in {
            item.get("id") for item in chapters if isinstance(item, dict)
        }:
            raise FactstoreError("FACT_CANDIDATE_CHAPTER_NOT_FOUND")
        facts_before = _validate_facts(planstore._read_json(root / "facts.json"))
        new_ids = allocate_fact_ids(facts_before, len(valid))
        new_records = []
        for item, fact_ref in zip(valid, new_ids):
            record = {
                "id": fact_ref,
                "chapter_id": chapter_id,
                "text": item["text"].strip(),
                "quote": str(item.get("quote") or "").strip(),
                "status": STATUS_EXTRACTED,
                "source": source,
                "note": "",
                "added_at": timestamp,
            }
            if item.get("seg"):
                record["seg"] = item["seg"]
            new_records.append(record)
        facts_after = [*copy.deepcopy(facts_before), *new_records]
        receipt = {
            "operation_id": operation_id,
            "status": "COMMITTED",
            "chapter_id": chapter_id,
            "candidate_count": len(new_records),
            "new_f_ids": new_ids,
            "confirmed_writes": 0,
            "actual_changes": 0,
        }
        return commit_facts_transaction_locked(
            root,
            operation_id=operation_id,
            action_name="fact_candidates_add",
            request_sha256=request_sha,
            facts_after=facts_after,
            plan_after=None,
            history_rows=[],
            blobs=[],
            receipt=receipt,
            timestamp=timestamp,
        )


def _contains_reference(value: Any, refs: set[str]) -> bool:
    if isinstance(value, dict):
        return any(_contains_reference(item, refs) for item in value.values())
    if isinstance(value, list):
        return any(_contains_reference(item, refs) for item in value)
    return isinstance(value, str) and value in refs


def repair_duplicate_fact_ids(
    project_dir: str | Path,
    *,
    timestamp: str,
    operation_id: str | None = None,
) -> dict[str, Any]:
    """旧坏账修号也走事务；被规划账引用的重复号因归属不明而失败关闭。"""
    root = Path(project_dir)
    operation_id = operation_id or new_operation_id("op-m4-repair-ids")
    planstore._validate_operation_id(operation_id)
    with planstore._exclusive_lock(root):
        planstore._recover_pending_locked(root, timestamp=timestamp)
        status = planstore._operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            return _replayed_receipt(root, operation_id)
        if status["terminal_phase"] == "rolled_back":
            raise FactstoreError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        if status["state"] == "NEEDS_MANUAL_RECOVERY":
            raise FactstoreError("OPERATION_NEEDS_MANUAL_RECOVERY")
        raw = planstore._read_json(root / "facts.json")
        if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
            raise FactstoreError("C4_FACTS_NOT_LIST")
        seen: set[str] = set()
        latecomers = []
        for item in raw:
            fact_ref = item.get("id")
            if not isinstance(fact_ref, str) or FACT_ID_RE.fullmatch(fact_ref) is None:
                raise FactstoreError("C4_FACT_ID_INVALID")
            if item.get("status") not in FACT_STATUSES:
                raise FactstoreError("C4_FACT_STATUS_INVALID")
            if fact_ref in seen:
                latecomers.append(item)
            else:
                seen.add(fact_ref)
        if not latecomers:
            return {"total": len(raw), "remap": [], "status": "NO_CHANGES"}
        duplicate_refs = {item["id"] for item in latecomers}
        if (root / "plan.json").exists():
            plan = planstore._read_json(root / "plan.json")
            planstore._validate_plan(plan)
            if _contains_reference(plan, duplicate_refs):
                raise FactstoreError("DUPLICATE_FACT_REF_REFERENCED_REPAIR_AMBIGUOUS")
        facts_after = copy.deepcopy(raw)
        new_ids = allocate_fact_ids(facts_after, len(latecomers))
        remap = []
        late_indexes = []
        seen.clear()
        for index, item in enumerate(facts_after):
            if item["id"] in seen:
                late_indexes.append(index)
            else:
                seen.add(item["id"])
        for index, new_id in zip(late_indexes, new_ids):
            item = facts_after[index]
            remap.append(
                {
                    "old": item["id"],
                    "new": new_id,
                    "chapter_id": item.get("chapter_id"),
                    "seg": item.get("seg"),
                    "text": str(item.get("text", ""))[:40],
                }
            )
            item["id_remapped_from"] = item["id"]
            item["id"] = new_id
        report = {"repaired_at": timestamp, "total": len(facts_after), "remap": remap}
        request_sha = planstore._sha256_json(
            {"operation_id": operation_id, "duplicate_refs": sorted(duplicate_refs)}
        )
        return commit_facts_transaction_locked(
            root,
            operation_id=operation_id,
            action_name="fact_id_repair",
            request_sha256=request_sha,
            facts_after=facts_after,
            plan_after=None,
            history_rows=[],
            blobs=[],
            receipt={**report, "operation_id": operation_id, "status": "COMMITTED"},
            timestamp=timestamp,
            extra_replacements={"repair_ids_report.json": planstore._canonical_bytes(report)},
        )


def review_fact(
    project_dir: str | Path,
    *,
    action: dict[str, Any],
    timestamp: str,
    fault_at: str | None = None,
) -> dict[str, Any]:
    """确认、驳回、改判或改写一个现有 C4 条目。"""
    if fault_at is not None and fault_at not in FAULT_POINTS:
        raise FactstoreError("UNKNOWN_FACT_REVIEW_FAULT_POINT")
    _validate_review_action(action)
    root = Path(project_dir)
    operation_id = action["operation_id"]
    request_sha = planstore._sha256_json(action)
    with planstore._exclusive_lock(root):
        planstore._recover_pending_locked(root, timestamp=timestamp)
        status = planstore._operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            if status["request_sha256"] != request_sha:
                raise FactstoreError("OPERATION_ID_PAYLOAD_CONFLICT")
            return _replayed_receipt(root, operation_id)
        if status["terminal_phase"] == "rolled_back":
            raise FactstoreError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        if status["state"] == "NEEDS_MANUAL_RECOVERY":
            raise FactstoreError("OPERATION_NEEDS_MANUAL_RECOVERY")

        facts_before = _validate_facts(planstore._read_json(root / "facts.json"))
        matches = [item for item in facts_before if item["id"] == action["fact_ref"]]
        if len(matches) != 1:
            raise FactstoreError("FACT_REVIEW_TARGET_NOT_FOUND")
        fact_before = matches[0]
        if (
            fact_before["status"] != action["expected_status"]
            or fact_sha256(fact_before) != action["expected_fact_sha256"]
        ):
            raise FactstoreError("STALE_FACT_REVISION")

        facts_after = copy.deepcopy(facts_before)
        fact_after = next(item for item in facts_after if item["id"] == action["fact_ref"])
        before_status = fact_after["status"]
        before_sha = fact_sha256(fact_after)
        decision = action["decision"]
        if decision == "confirm":
            fact_after["status"] = STATUS_CONFIRMED
        elif decision == "reject":
            fact_after["status"] = STATUS_REJECTED
        elif decision in {"edit", "edit_and_confirm"}:
            old_text = str(fact_after.get("text", ""))
            fact_after["text"] = action["replacement_text"].strip()
            fact_after["note"] = action["note"] or f"原文候选：{old_text}"
            if decision == "edit_and_confirm":
                fact_after["status"] = STATUS_CONFIRMED
        if action["note"] and decision not in {"edit", "edit_and_confirm"}:
            fact_after["note"] = action["note"]
        if decision in {"confirm", "reject", "edit_and_confirm"}:
            fact_after["decided_at"] = timestamp

        plan_after = None
        history_rows: list[dict[str, Any]] = []
        blobs: list[dict[str, Any]] = []
        stale_edge_refs: list[str] = []
        plan_path = root / "plan.json"
        if plan_path.exists():
            plan_after = copy.deepcopy(planstore._read_json(plan_path))
            planstore._validate_plan(plan_after)
            for edge in plan_after["reconciliation_edges"]:
                if edge["edge_status"] != "active" or action["fact_ref"] not in edge["actual_fact_refs"]:
                    continue
                edge_before = copy.deepcopy(edge)
                edge["edge_status"] = "stale"
                edge["rev"] += 1
                row, blob = _history_row(
                    operation_id=operation_id,
                    before=edge_before,
                    after=edge,
                    timestamp=timestamp,
                    note="M5 事实状态或文本改变，旧 actual support 失效",
                )
                history_rows.append(row)
                blobs.append(blob)
                stale_edge_refs.append(edge["id"])

        receipt = {
            "operation_id": operation_id,
            "status": "COMMITTED",
            "fact_ref": action["fact_ref"],
            "decision": decision,
            "before_status": before_status,
            "after_status": fact_after["status"],
            "before_fact_sha256": before_sha,
            "after_fact_sha256": fact_sha256(fact_after),
            "stale_edge_refs": stale_edge_refs,
            "facts_writes": 1,
            "plan_writes": 1 if stale_edge_refs else 0,
            "actual_support_invalidated": len(stale_edge_refs),
            "stored_actual_fields": 0,
        }
        return commit_facts_transaction_locked(
            root,
            operation_id=operation_id,
            action_name="fact_review",
            request_sha256=request_sha,
            facts_after=facts_after,
            plan_after=plan_after if stale_edge_refs else None,
            history_rows=history_rows,
            blobs=blobs,
            receipt=receipt,
            timestamp=timestamp,
            fault_at=fault_at,
        )
