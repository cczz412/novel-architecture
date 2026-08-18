"""计划—书稿六态观察与作者 facts 准入接缝。

模型只产生短命语义候选；本模块负责引用、证据、revision、作者权限与跨文件事务。
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

try:
    from . import factstore, planstore
except ImportError:  # pragma: no cover - 直接运行脚本时使用
    import factstore  # type: ignore[no-redef]
    import planstore  # type: ignore[no-redef]


CANDIDATE_KEYS = {
    "contract",
    "version",
    "reconcile_run_id",
    "chapter_ref",
    "chapter_text_sha256",
    "slot_ref",
    "planning_basis_commit_seq",
    "fact_candidates",
    "items",
}
FACT_CANDIDATE_KEYS = {"candidate_ref", "text", "quote", "seg", "source"}
CANDIDATE_ITEM_KEYS = {
    "item_key",
    "planned_ref",
    "planned_rev",
    "outcome",
    "coverage",
    "variant_note",
    "evidence_quote",
    "fact_candidate_refs",
    "rationale",
}
ADMISSION_ACTION_KEYS = {
    "contract",
    "version",
    "operation_id",
    "actor",
    "reconcile_run_id",
    "candidate_sha256",
    "chapter_ref",
    "chapter_text_sha256",
    "decisions",
}
DECISION_KEYS = {
    "edge_ref",
    "edge_rev",
    "fact_candidate_refs",
    "reconciliation_action",
    "note",
}
OUTCOMES = {"exact", "variant", "unrealized", "contradicted", "unplanned", "ambiguous"}
OBSERVATION_FAULT_POINTS = {
    "after_prepare",
    "after_plan",
    "after_blob",
    "during_history",
    "after_history",
    "before_commit",
    "after_commit",
}
ADMISSION_FAULT_POINTS = OBSERVATION_FAULT_POINTS | {"after_facts"}


class ReconciliationError(planstore.PlanstoreError):
    """对账或 facts 准入在写前拒绝。"""


def _canonical_sha(value: Any) -> str:
    return planstore._sha256_json(value)


def _chapter_by_id(chapters: list[dict[str, Any]], chapter_ref: str) -> dict[str, Any]:
    matches = [item for item in chapters if item.get("id") == chapter_ref]
    if len(matches) != 1 or matches[0].get("kind") != "draft":
        raise ReconciliationError("CURRENT_C1_NOT_FOUND")
    return matches[0]


def _planned_objects(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["id"]: item
        for key in ("events", "hooks", "must_carries")
        for item in plan.get(key, [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def _active_mapping(
    plan: dict[str, Any], *, slot_ref: str, chapter_ref: str
) -> dict[str, Any]:
    matches = [
        item
        for item in plan["slot_mappings"]
        if item.get("slot_ref") == slot_ref
        and item.get("chapter_id") == chapter_ref
        and item.get("mapping_status") == "active"
    ]
    if len(matches) != 1:
        raise ReconciliationError("CURRENT_SLOT_MAPPING_NOT_FOUND")
    return matches[0]


def _covered_pe_refs(plan: dict[str, Any], *, slot_ref: str, chapter_ref: str) -> list[str]:
    slots = [item for item in plan["slots"] if item.get("id") == slot_ref]
    if len(slots) != 1:
        raise ReconciliationError("CURRENT_SLOT_NOT_FOUND")
    parts = [
        item
        for item in slots[0].get("handover_parts", [])
        if item.get("chapter_id") == chapter_ref
    ]
    if len(parts) != 1:
        raise ReconciliationError("CURRENT_HANDOVER_PART_NOT_FOUND")
    refs = parts[0].get("covered_pe_refs")
    if not isinstance(refs, list) or len(refs) != len(set(refs)):
        raise ReconciliationError("HANDOVER_PE_COVERAGE_INVALID")
    return refs


def _committed_story_seqs(root: Path) -> set[int]:
    rows = planstore._commit_rows(root)
    committed_ops = {
        row.get("op")
        for row in rows
        if row.get("phase") == "commit" and row.get("op") is not None
    }
    return {
        row["story_commit_seq"]
        for row in rows
        if row.get("phase") == "prepare"
        and row.get("op") in committed_ops
        and isinstance(row.get("story_commit_seq"), int)
    }


def validate_candidate(
    root: Path,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(candidate, dict) or set(candidate) != CANDIDATE_KEYS:
        raise ReconciliationError("RECONCILIATION_CANDIDATE_SCHEMA_MISMATCH")
    if (
        candidate.get("contract") != "RECONCILIATION_CANDIDATE"
        or candidate.get("version") != "v1"
    ):
        raise ReconciliationError("RECONCILIATION_CANDIDATE_IDENTITY_INVALID")
    planstore._validate_operation_id(candidate.get("reconcile_run_id"))
    if (
        not isinstance(candidate.get("chapter_text_sha256"), str)
        or planstore.SHA256_RE.fullmatch(candidate["chapter_text_sha256"]) is None
    ):
        raise ReconciliationError("CANDIDATE_CHAPTER_SHA_INVALID")
    if not isinstance(candidate.get("planning_basis_commit_seq"), int):
        raise ReconciliationError("CANDIDATE_PLANNING_BASIS_INVALID")

    plan = planstore._read_json(root / "plan.json")
    chapters = planstore._read_json(root / "chapters.json")
    if not isinstance(chapters, list):
        raise ReconciliationError("C1_CHAPTERS_NOT_LIST")
    planstore._validate_plan(plan)
    chapter = _chapter_by_id(chapters, candidate["chapter_ref"])
    chapter_sha = planstore._sha256_bytes(chapter["text"].encode("utf-8"))
    if chapter_sha != candidate["chapter_text_sha256"]:
        raise ReconciliationError("STALE_C1_TEXT")
    _active_mapping(
        plan,
        slot_ref=candidate["slot_ref"],
        chapter_ref=candidate["chapter_ref"],
    )
    committed_seqs = _committed_story_seqs(root)
    if (
        candidate["planning_basis_commit_seq"] == 0
        and committed_seqs
        or candidate["planning_basis_commit_seq"] != 0
        and candidate["planning_basis_commit_seq"] not in committed_seqs
    ):
        raise ReconciliationError("PLANNING_BASIS_NOT_COMMITTED")

    facts = candidate.get("fact_candidates")
    if not isinstance(facts, list) or any(
        not isinstance(item, dict) or set(item) != FACT_CANDIDATE_KEYS for item in facts
    ):
        raise ReconciliationError("C3_CANDIDATE_WRAPPER_INVALID")
    facts_by_ref = {item.get("candidate_ref"): item for item in facts}
    if len(facts_by_ref) != len(facts) or any(not isinstance(ref, str) or not ref for ref in facts_by_ref):
        raise ReconciliationError("C3_CANDIDATE_REF_INVALID")
    for fact in facts:
        if (
            not isinstance(fact.get("text"), str)
            or not fact["text"].strip()
            or not isinstance(fact.get("quote"), str)
            or not fact["quote"]
            or fact["quote"] not in chapter["text"]
            or not isinstance(fact.get("source"), str)
            or not fact["source"]
            or (
                fact.get("seg") is not None
                and (
                    not isinstance(fact["seg"], int)
                    or isinstance(fact["seg"], bool)
                    or fact["seg"] <= 0
                )
            )
        ):
            raise ReconciliationError("C3_CANDIDATE_EVIDENCE_INVALID")

    items = candidate.get("items")
    if not isinstance(items, list) or any(
        not isinstance(item, dict) or set(item) != CANDIDATE_ITEM_KEYS for item in items
    ):
        raise ReconciliationError("RECONCILIATION_ITEM_SCHEMA_MISMATCH")
    item_keys = [item.get("item_key") for item in items]
    if any(not isinstance(key, str) or not key for key in item_keys) or len(item_keys) != len(set(item_keys)):
        raise ReconciliationError("RECONCILIATION_ITEM_KEY_INVALID")
    planned = _planned_objects(plan)
    covered_refs = _covered_pe_refs(
        plan,
        slot_ref=candidate["slot_ref"],
        chapter_ref=candidate["chapter_ref"],
    )
    planned_items = [item for item in items if item.get("planned_ref") is not None]
    planned_refs = [item["planned_ref"] for item in planned_items]
    if sorted(planned_refs) != sorted(covered_refs) or len(planned_refs) != len(set(planned_refs)):
        raise ReconciliationError("RECONCILIATION_PLANNED_COVERAGE_INCOMPLETE")
    for item in items:
        outcome = item.get("outcome")
        if outcome not in OUTCOMES or item.get("coverage") not in {"full", "partial"}:
            raise ReconciliationError("RECONCILIATION_ITEM_ENUM_INVALID")
        planned_ref = item.get("planned_ref")
        if outcome == "unplanned":
            if planned_ref is not None or item.get("planned_rev") is not None:
                raise ReconciliationError("UNPLANNED_ITEM_BINDING_INVALID")
        elif (
            planned_ref not in planned
            or item.get("planned_rev") != planned[planned_ref].get("rev")
        ):
            raise ReconciliationError("STALE_PLANNED_REVISION")
        refs = item.get("fact_candidate_refs")
        if not isinstance(refs, list) or any(ref not in facts_by_ref for ref in refs):
            raise ReconciliationError("RECONCILIATION_C3_REF_INVALID")
        evidence = item.get("evidence_quote")
        if outcome in {"exact", "variant", "contradicted", "unplanned"}:
            if not refs or not isinstance(evidence, str) or not evidence or evidence not in chapter["text"]:
                raise ReconciliationError("RECONCILIATION_EVIDENCE_REQUIRED")
        elif outcome == "unrealized":
            if refs or evidence is not None:
                raise ReconciliationError("UNREALIZED_ITEM_MUST_NOT_HAVE_EVIDENCE")
        elif refs:
            raise ReconciliationError("AMBIGUOUS_ITEM_MUST_NOT_REFERENCE_FACTS")
        if outcome == "variant":
            if not isinstance(item.get("variant_note"), str) or not item["variant_note"].strip():
                raise ReconciliationError("VARIANT_NOTE_REQUIRED")
        elif item.get("variant_note") is not None:
            raise ReconciliationError("VARIANT_NOTE_FORBIDDEN")
        if not isinstance(item.get("rationale"), str):
            raise ReconciliationError("RECONCILIATION_RATIONALE_INVALID")
    return {
        "plan": plan,
        "chapters": chapters,
        "chapter": chapter,
        "facts_by_ref": facts_by_ref,
        "items_by_key": {item["item_key"]: item for item in items},
    }


def _history_row(
    *,
    operation_id: str,
    actor: str,
    action: str,
    before: dict[str, Any],
    after: dict[str, Any],
    changes: dict[str, Any],
    timestamp: str,
    note: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    content_hash, blob = planstore._blob_record(before)
    return (
        {
            "ts": timestamp,
            "op": operation_id,
            "actor": actor,
            "action": action,
            "object_id": after["id"],
            "rev": after["rev"],
            "changes": changes,
            "content_hash": content_hash,
            "note": note,
        },
        blob,
    )


def _replayed_observation_receipt(root: Path, operation_id: str) -> dict[str, Any]:
    edges = [
        edge
        for edge in planstore._read_json(root / "plan.json")["reconciliation_edges"]
        if edge.get("source_run_id") == operation_id
    ]
    if not edges:
        raise ReconciliationError("COMMITTED_OBSERVATION_RECEIPT_UNRESOLVABLE")
    prepare = next(
        row
        for row in planstore._operation_rows(root, operation_id)
        if row.get("phase") == "prepare"
    )
    return {
        "operation_id": operation_id,
        "status": "COMMITTED",
        "edge_refs": [edge["id"] for edge in edges],
        "edge_count": len(edges),
        "facts_writes": 0,
        "new_f_ids": [],
        "stored_actual_fields": 0,
        "actual_support_refs": [],
        "story_commit_seq": prepare["story_commit_seq"],
        "replayed": True,
    }


def record_reconciliation_candidate(
    project_dir: str | Path,
    *,
    candidate: dict[str, Any],
    timestamp: str,
    fault_at: str | None = None,
) -> dict[str, Any]:
    if fault_at is not None and fault_at not in OBSERVATION_FAULT_POINTS:
        raise ReconciliationError("UNKNOWN_OBSERVATION_FAULT_POINT")
    root = Path(project_dir)
    operation_id = planstore._validate_operation_id(candidate.get("reconcile_run_id"))
    request_sha = _canonical_sha(candidate)
    with planstore._exclusive_lock(root):
        planstore._recover_pending_locked(root, timestamp=timestamp)
        status = planstore._operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            if status["request_sha256"] != request_sha:
                raise ReconciliationError("OPERATION_ID_PAYLOAD_CONFLICT")
            return _replayed_observation_receipt(root, operation_id)
        if status["terminal_phase"] == "rolled_back":
            raise ReconciliationError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        if status["state"] == "NEEDS_MANUAL_RECOVERY":
            raise ReconciliationError("OPERATION_NEEDS_MANUAL_RECOVERY")
        context = validate_candidate(root, candidate)
        plan_after = copy.deepcopy(context["plan"])
        existing_active = {
            (edge.get("chapter_ref"), edge.get("planned_ref"))
            for edge in plan_after["reconciliation_edges"]
            if edge.get("edge_status") == "active"
        }
        for item in candidate["items"]:
            if (candidate["chapter_ref"], item["planned_ref"]) in existing_active:
                raise ReconciliationError("ACTIVE_RECONCILIATION_EDGE_ALREADY_EXISTS")
        counter = plan_after["id_counters"].get("RE")
        if not isinstance(counter, int) or counter < 0:
            raise ReconciliationError("RE_COUNTER_INVALID")
        history_rows = []
        blobs = []
        created = []
        for offset, item in enumerate(candidate["items"], start=1):
            edge = {
                "id": f"RE-{counter + offset:04d}",
                "planned_ref": item["planned_ref"],
                "planned_rev": item["planned_rev"],
                "actual_fact_refs": [],
                "actual_fact_basis_sha256": None,
                "chapter_ref": candidate["chapter_ref"],
                "slot_ref": candidate["slot_ref"],
                "chapter_text_sha256": candidate["chapter_text_sha256"],
                "source_run_id": operation_id,
                "source_item_key": item["item_key"],
                "outcome": item["outcome"],
                "coverage": item["coverage"],
                "variant_note": item["variant_note"],
                "author_decision": None,
                "basis_commit_seq": candidate["planning_basis_commit_seq"],
                "decided_by": "auto",
                "edge_status": "active",
                "superseded_by": None,
                "rev": 1,
            }
            row, blob = _history_row(
                operation_id=operation_id,
                actor="auto",
                action="reconcile",
                before={"id": edge["id"], "rev": 0, "state": "absent"},
                after=edge,
                changes={"state": [None, edge]},
                timestamp=timestamp,
                note=f"六态观察候选 {item['item_key']}",
            )
            history_rows.append(row)
            blobs.append(blob)
            plan_after["reconciliation_edges"].append(edge)
            created.append(edge)
        plan_after["id_counters"]["RE"] = counter + len(created)
        planstore._validate_plan(plan_after)
        receipt = {
            "operation_id": operation_id,
            "status": "COMMITTED",
            "edge_refs": [edge["id"] for edge in created],
            "edge_count": len(created),
            "facts_writes": 0,
            "new_f_ids": [],
            "stored_actual_fields": 0,
            "actual_support_refs": [],
        }
        return planstore._commit_generic_transaction_locked(
            root,
            operation_id=operation_id,
            action_name="reconciliation_observe",
            request_sha256=request_sha,
            replacements={"plan.json": planstore._canonical_bytes(plan_after)},
            appends={
                "plan_history.jsonl": b"".join(
                    planstore._canonical_bytes(row) for row in history_rows
                )
            },
            blobs=blobs,
            receipt=receipt,
            timestamp=timestamp,
            fault_at=fault_at,
        )


def _validate_admission_action(action: dict[str, Any], candidate: dict[str, Any]) -> None:
    if not isinstance(action, dict) or set(action) != ADMISSION_ACTION_KEYS:
        raise ReconciliationError("FACT_ADMISSION_ACTION_SCHEMA_MISMATCH")
    if (
        action.get("contract") != "RECONCILIATION_FACT_ADMISSION_ACTION"
        or action.get("version") != "v1"
    ):
        raise ReconciliationError("FACT_ADMISSION_ACTION_IDENTITY_INVALID")
    if action.get("actor") != "author":
        raise ReconciliationError("FACT_ADMISSION_AUTHOR_REQUIRED")
    planstore._validate_operation_id(action.get("operation_id"))
    if action.get("reconcile_run_id") != candidate.get("reconcile_run_id"):
        raise ReconciliationError("FACT_ADMISSION_RUN_MISMATCH")
    if action.get("candidate_sha256") != _canonical_sha(candidate):
        raise ReconciliationError("FACT_ADMISSION_CANDIDATE_SHA_MISMATCH")
    if (
        action.get("chapter_ref") != candidate.get("chapter_ref")
        or action.get("chapter_text_sha256") != candidate.get("chapter_text_sha256")
    ):
        raise ReconciliationError("FACT_ADMISSION_CHAPTER_BINDING_MISMATCH")
    decisions = action.get("decisions")
    if not isinstance(decisions, list) or not decisions or any(
        not isinstance(item, dict) or set(item) != DECISION_KEYS for item in decisions
    ):
        raise ReconciliationError("FACT_ADMISSION_DECISIONS_INVALID")
    edge_refs = [item.get("edge_ref") for item in decisions]
    if len(edge_refs) != len(set(edge_refs)):
        raise ReconciliationError("FACT_ADMISSION_EDGE_DUPLICATE")


def _replayed_admission_receipt(root: Path, operation_id: str) -> dict[str, Any]:
    history = [
        row
        for row in planstore._read_jsonl(root / "plan_history.jsonl")
        if row.get("op") == operation_id and row.get("action") == "fact_admission"
    ]
    if not history:
        raise ReconciliationError("COMMITTED_ADMISSION_RECEIPT_UNRESOLVABLE")
    fact_refs = sorted(
        {
            ref
            for row in history
            for ref in row.get("changes", {}).get("actual_fact_refs", [[], []])[1]
        }
    )
    prepare = next(
        row
        for row in planstore._operation_rows(root, operation_id)
        if row.get("phase") == "prepare"
    )
    return {
        "operation_id": operation_id,
        "status": "COMMITTED",
        "edge_refs": [row["object_id"] for row in history],
        "facts_writes": len(fact_refs),
        "new_f_ids": fact_refs,
        "stored_actual_fields": 0,
        "story_commit_seq": prepare["story_commit_seq"],
        "replayed": True,
    }


def admit_reconciled_facts(
    project_dir: str | Path,
    *,
    action: dict[str, Any],
    candidate: dict[str, Any],
    timestamp: str,
    fault_at: str | None = None,
) -> dict[str, Any]:
    if fault_at is not None and fault_at not in ADMISSION_FAULT_POINTS:
        raise ReconciliationError("UNKNOWN_ADMISSION_FAULT_POINT")
    _validate_admission_action(action, candidate)
    root = Path(project_dir)
    operation_id = action["operation_id"]
    request_sha = _canonical_sha({"action": action, "candidate": candidate})
    with planstore._exclusive_lock(root):
        planstore._recover_pending_locked(root, timestamp=timestamp)
        status = planstore._operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            if status["request_sha256"] != request_sha:
                raise ReconciliationError("OPERATION_ID_PAYLOAD_CONFLICT")
            return _replayed_admission_receipt(root, operation_id)
        if status["terminal_phase"] == "rolled_back":
            raise ReconciliationError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        if status["state"] == "NEEDS_MANUAL_RECOVERY":
            raise ReconciliationError("OPERATION_NEEDS_MANUAL_RECOVERY")
        context = validate_candidate(root, candidate)
        plan_after = copy.deepcopy(context["plan"])
        facts_before = planstore._read_json(root / "facts.json")
        if not isinstance(facts_before, list):
            raise ReconciliationError("C4_FACTS_NOT_LIST")
        current_edges = {edge["id"]: edge for edge in plan_after["reconciliation_edges"]}
        candidate_items = context["items_by_key"]
        facts_by_ref = context["facts_by_ref"]
        selected_refs = []
        decision_contexts = []
        for decision in action["decisions"]:
            edge = current_edges.get(decision.get("edge_ref"))
            if (
                edge is None
                or edge.get("edge_status") != "active"
                or edge.get("source_run_id") != candidate["reconcile_run_id"]
                or edge.get("rev") != decision.get("edge_rev")
            ):
                raise ReconciliationError("STALE_OR_WRONG_RECONCILIATION_EDGE")
            item = candidate_items.get(edge["source_item_key"])
            if (
                item is None
                or item["planned_ref"] != edge["planned_ref"]
                or item["planned_rev"] != edge["planned_rev"]
                or item["outcome"] != edge["outcome"]
                or edge["slot_ref"] != candidate["slot_ref"]
            ):
                raise ReconciliationError("EDGE_CANDIDATE_BINDING_MISMATCH")
            if edge["actual_fact_refs"] or edge["actual_fact_basis_sha256"] is not None:
                raise ReconciliationError("EDGE_ALREADY_HAS_CONFIRMED_FACTS")
            refs = decision.get("fact_candidate_refs")
            if not isinstance(refs, list) or not refs or any(
                ref not in item["fact_candidate_refs"] for ref in refs
            ):
                raise ReconciliationError("FACT_ADMISSION_CANDIDATE_REFS_INVALID")
            if edge["outcome"] == "exact":
                if decision.get("reconciliation_action") is not None:
                    raise ReconciliationError("EXACT_ADMISSION_MUST_NOT_ADD_DISPOSITION")
            elif edge["outcome"] in {"variant", "contradicted", "unplanned"}:
                if decision.get("reconciliation_action") != "accept_as_is":
                    raise ReconciliationError("DIFFERENCE_REQUIRES_ACCEPT_AS_IS")
            else:
                raise ReconciliationError("OUTCOME_HAS_NO_FACT_ADMISSION_PATH")
            if not isinstance(decision.get("note"), str):
                raise ReconciliationError("FACT_ADMISSION_NOTE_INVALID")
            selected_refs.extend(refs)
            decision_contexts.append((decision, edge, refs))
        unique_refs = list(dict.fromkeys(selected_refs))
        new_ids = factstore.allocate_fact_ids(facts_before, len(unique_refs))
        fact_id_by_candidate = dict(zip(unique_refs, new_ids))
        new_facts = []
        for candidate_ref in unique_refs:
            item = facts_by_ref[candidate_ref]
            record = {
                "id": fact_id_by_candidate[candidate_ref],
                "chapter_id": candidate["chapter_ref"],
                "text": item["text"].strip(),
                "quote": item["quote"],
                "status": factstore.STATUS_CONFIRMED,
                "source": item["source"],
                "note": f"作者经计划—书稿对账确认；candidate={candidate_ref}",
                "added_at": timestamp,
                "decided_at": timestamp,
            }
            if item.get("seg") is not None:
                record["seg"] = item["seg"]
            new_facts.append(record)
        facts_after = [*copy.deepcopy(facts_before), *new_facts]
        facts_after_by_id = {item["id"]: item for item in facts_after}
        history_rows = []
        blobs = []
        admitted_edges = []
        for decision, edge, refs in decision_contexts:
            before = copy.deepcopy(edge)
            fact_ids = [fact_id_by_candidate[ref] for ref in refs]
            edge["actual_fact_refs"] = fact_ids
            edge["actual_fact_basis_sha256"] = planstore._fact_basis_sha256(
                [facts_after_by_id[ref] for ref in fact_ids]
            )
            if decision["reconciliation_action"] is not None:
                edge["author_decision"] = {
                    "action": decision["reconciliation_action"],
                    "decided_at": timestamp,
                    "note": decision["note"],
                }
                edge["decided_by"] = "author"
            edge["rev"] += 1
            row, blob = _history_row(
                operation_id=operation_id,
                actor="author",
                action="fact_admission",
                before=before,
                after=edge,
                changes={
                    "actual_fact_refs": [before["actual_fact_refs"], edge["actual_fact_refs"]],
                    "actual_fact_basis_sha256": [
                        before["actual_fact_basis_sha256"],
                        edge["actual_fact_basis_sha256"],
                    ],
                    "author_decision": [before["author_decision"], edge["author_decision"]],
                    "decided_by": [before["decided_by"], edge["decided_by"]],
                },
                timestamp=timestamp,
                note="作者确认 C1 书稿事实进入 M4",
            )
            history_rows.append(row)
            blobs.append(blob)
            admitted_edges.append(edge)
        planstore._validate_plan(plan_after)
        actual_support_refs = [
            edge["id"] for edge in admitted_edges if edge["outcome"] in {"exact", "variant"}
        ]
        receipt = {
            "operation_id": operation_id,
            "status": "COMMITTED",
            "edge_refs": [edge["id"] for edge in admitted_edges],
            "facts_writes": len(new_facts),
            "new_f_ids": new_ids,
            "stored_actual_fields": 0,
            "actual_support_refs": actual_support_refs,
        }
        return factstore.commit_facts_transaction_locked(
            root,
            operation_id=operation_id,
            action_name="reconciliation_fact_admission",
            request_sha256=request_sha,
            facts_after=facts_after,
            plan_after=plan_after,
            history_rows=history_rows,
            blobs=blobs,
            receipt=receipt,
            timestamp=timestamp,
            fault_at=fault_at,
        )


def reconciliation_edge_states(project_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(project_dir)
    with planstore._exclusive_lock(root):
        plan = planstore._read_json(root / "plan.json")
        planstore._validate_plan(plan)
        return reconciliation_edge_states_unlocked(root, plan)


def mark_stale_reconciliation_edges(
    project_dir: str | Path,
    *,
    operation_id: str,
    timestamp: str,
    fault_at: str | None = None,
) -> dict[str, Any]:
    if fault_at is not None and fault_at not in OBSERVATION_FAULT_POINTS:
        raise ReconciliationError("UNKNOWN_STALE_FAULT_POINT")
    operation_id = planstore._validate_operation_id(operation_id)
    root = Path(project_dir)
    request_sha = _canonical_sha({"operation_id": operation_id, "action": "reconciliation_stale"})
    with planstore._exclusive_lock(root):
        planstore._recover_pending_locked(root, timestamp=timestamp)
        status = planstore._operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            if status["request_sha256"] != request_sha:
                raise ReconciliationError("OPERATION_ID_PAYLOAD_CONFLICT")
            history = [
                row
                for row in planstore._read_jsonl(root / "plan_history.jsonl")
                if row.get("op") == operation_id
            ]
            return {
                "operation_id": operation_id,
                "status": "COMMITTED",
                "stale_edge_refs": [row["object_id"] for row in history],
                "facts_writes": 0,
                "stored_actual_fields": 0,
                "replayed": True,
            }
        if status["terminal_phase"] == "rolled_back":
            raise ReconciliationError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        plan = planstore._read_json(root / "plan.json")
        states = {item["edge_ref"]: item for item in reconciliation_edge_states_unlocked(root, plan)}
        plan_after = copy.deepcopy(plan)
        history_rows = []
        blobs = []
        stale_refs = []
        for edge in plan_after["reconciliation_edges"]:
            state = states[edge["id"]]
            if edge["edge_status"] != "active" or not state["stale_reasons"]:
                continue
            before = copy.deepcopy(edge)
            edge["edge_status"] = "stale"
            edge["rev"] += 1
            row, blob = _history_row(
                operation_id=operation_id,
                actor="auto",
                action="reconciliation_stale",
                before=before,
                after=edge,
                changes={"edge_status": ["active", "stale"]},
                timestamp=timestamp,
                note=",".join(state["stale_reasons"]),
            )
            history_rows.append(row)
            blobs.append(blob)
            stale_refs.append(edge["id"])
        if not stale_refs:
            return {
                "operation_id": operation_id,
                "status": "NO_CHANGES",
                "stale_edge_refs": [],
                "facts_writes": 0,
                "stored_actual_fields": 0,
                "replayed": False,
            }
        planstore._validate_plan(plan_after)
        return planstore._commit_generic_transaction_locked(
            root,
            operation_id=operation_id,
            action_name="reconciliation_stale",
            request_sha256=request_sha,
            replacements={"plan.json": planstore._canonical_bytes(plan_after)},
            appends={
                "plan_history.jsonl": b"".join(
                    planstore._canonical_bytes(row) for row in history_rows
                )
            },
            blobs=blobs,
            receipt={
                "operation_id": operation_id,
                "status": "COMMITTED",
                "stale_edge_refs": stale_refs,
                "facts_writes": 0,
                "stored_actual_fields": 0,
            },
            timestamp=timestamp,
            fault_at=fault_at,
        )


def reconciliation_edge_states_unlocked(
    root: Path, plan: dict[str, Any]
) -> list[dict[str, Any]]:
    chapters = planstore._read_json(root / "chapters.json")
    facts = planstore._read_json(root / "facts.json")
    if not isinstance(chapters, list) or not isinstance(facts, list):
        raise ReconciliationError("C1_OR_C4_LEDGER_INVALID")
    chapters_by_id = {item.get("id"): item for item in chapters}
    planned = _planned_objects(plan)
    facts_by_id = {item.get("id"): item for item in facts}
    states = []
    for edge in plan["reconciliation_edges"]:
        reasons = []
        mapping_matches = [
            item
            for item in plan["slot_mappings"]
            if item.get("slot_ref") == edge["slot_ref"]
            and item.get("chapter_id") == edge["chapter_ref"]
            and item.get("mapping_status") == "active"
        ]
        if len(mapping_matches) != 1:
            reasons.append("STALE_SLOT_MAPPING")
        chapter = chapters_by_id.get(edge["chapter_ref"])
        if (
            chapter is None
            or planstore._sha256_bytes(str(chapter.get("text", "")).encode("utf-8"))
            != edge["chapter_text_sha256"]
        ):
            reasons.append("STALE_C1_TEXT")
        if edge["planned_ref"] is not None:
            current = planned.get(edge["planned_ref"])
            if current is None or current.get("rev") != edge["planned_rev"]:
                reasons.append("STALE_PLANNED_REVISION")
        supporting = [facts_by_id.get(ref) for ref in edge["actual_fact_refs"]]
        if edge["actual_fact_refs"] and (
            any(item is None or item.get("status") != factstore.STATUS_CONFIRMED for item in supporting)
            or planstore._fact_basis_sha256(supporting) != edge["actual_fact_basis_sha256"]
        ):
            reasons.append("STALE_FACT_BASIS")
        current = edge["edge_status"] == "active" and not reasons
        actual_support = (
            current
            and edge["outcome"] in {"exact", "variant"}
            and bool(edge["actual_fact_refs"])
        )
        states.append(
            {
                "edge_ref": edge["id"],
                "current": current,
                "stale_reasons": reasons,
                "actual_support": actual_support,
                "support_set": [edge["id"]] if actual_support else [],
            }
        )
    return states


def _load_object(path: str) -> dict[str, Any]:
    value = planstore._read_json(Path(path))
    if not isinstance(value, dict):
        raise ReconciliationError(f"INPUT_NOT_OBJECT:{path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="六态对账观察与作者 facts 准入")
    sub = parser.add_subparsers(dest="command", required=True)

    observe = sub.add_parser("observe")
    observe.add_argument("project_dir")
    observe.add_argument("--candidate", required=True)
    observe.add_argument("--timestamp", required=True)
    observe.add_argument("--fault-at", choices=sorted(OBSERVATION_FAULT_POINTS))

    admit = sub.add_parser("admit")
    admit.add_argument("project_dir")
    admit.add_argument("--candidate", required=True)
    admit.add_argument("--action", required=True)
    admit.add_argument("--timestamp", required=True)
    admit.add_argument("--fault-at", choices=sorted(ADMISSION_FAULT_POINTS))

    states = sub.add_parser("states")
    states.add_argument("project_dir")

    stale = sub.add_parser("mark-stale")
    stale.add_argument("project_dir")
    stale.add_argument("--operation-id", required=True)
    stale.add_argument("--timestamp", required=True)
    stale.add_argument("--fault-at", choices=sorted(OBSERVATION_FAULT_POINTS))

    args = parser.parse_args()
    try:
        if args.command == "observe":
            result = record_reconciliation_candidate(
                args.project_dir,
                candidate=_load_object(args.candidate),
                timestamp=args.timestamp,
                fault_at=args.fault_at,
            )
        elif args.command == "admit":
            result = admit_reconciled_facts(
                args.project_dir,
                action=_load_object(args.action),
                candidate=_load_object(args.candidate),
                timestamp=args.timestamp,
                fault_at=args.fault_at,
            )
        elif args.command == "states":
            result = {"status": "PASS", "edges": reconciliation_edge_states(args.project_dir)}
        else:
            result = mark_stale_reconciliation_edges(
                args.project_dir,
                operation_id=args.operation_id,
                timestamp=args.timestamp,
                fault_at=args.fault_at,
            )
    except planstore.InjectedCrash as exc:
        print(json.dumps({"status": "INJECTED_CRASH", "reason": str(exc)}, ensure_ascii=False))
        return 75
    except (planstore.PlanstoreError, ReconciliationError) as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
