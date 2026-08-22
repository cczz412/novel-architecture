"""plan-v2 writer：r07 规划记录、handover 与跨文件事务恢复／幂等。

业务语义分别由 handover 与 reconciliation 接缝校验；本模块不做模型抽取、暗稿或关章。
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


ACTION_KEYS = {
    "contract",
    "version",
    "operation_id",
    "actor",
    "intent",
    "work_ref",
    "work_rev",
    "slot_ref",
    "source_outline_ref",
    "target_contract",
    "target_planstore_result",
}
WORK_KEYS = {
    "contract",
    "version",
    "work_ref",
    "slot_ref",
    "source_outline_ref",
    "work_rev",
    "state",
    "entry_mode",
    "text",
    "text_sha256",
    "last_operation_id",
}
MAP_KEYS = {
    "id",
    "slot_ref",
    "chapter_id",
    "expected_chapter_no",
    "mapping_kind",
    "reason",
    "decided_by",
    "mapping_status",
    "superseded_by",
}
RECONCILIATION_EDGE_KEYS = {
    "id",
    "planned_ref",
    "planned_rev",
    "actual_fact_refs",
    "actual_fact_basis_sha256",
    "chapter_ref",
    "slot_ref",
    "chapter_text_sha256",
    "source_run_id",
    "source_item_key",
    "outcome",
    "coverage",
    "variant_note",
    "author_decision",
    "basis_commit_seq",
    "decided_by",
    "edge_status",
    "superseded_by",
    "rev",
}
RECONCILIATION_EDGE_R07_KEYS = RECONCILIATION_EDGE_KEYS | {"chapter_revision_ref"}
CHAPTER_REVISION_REF_KEYS = {
    "chapter_id",
    "revision_no",
    "revision_text_sha256",
}
R07_PLANNING_RECORD_INPUT_KEYS = {
    "planned_ref",
    "planned_rev",
    "chapter_ref",
    "slot_ref",
    "source_item_key",
    "outcome",
    "coverage",
    "variant_note",
    "author_decision",
    "decided_by",
}
FORBIDDEN_TRUTH_KEYS = {"facts", "F-", "actual", "actuality", "dark_draft", "chapter_close"}
OPERATION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
C1_RE = re.compile(r"c(\d+)$")
MAP_RE = re.compile(r"MAP-(\d{4,})$")
RECONCILIATION_EDGE_RE = re.compile(r"RE-(\d{4,})$")
SHA256_RE = re.compile(r"[0-9a-f]{64}$")
MAPPING_KINDS_WITH_SLOT = {"as_written", "split", "merge"}
MAPPING_KINDS_WITHOUT_SLOT = {"inserted", "non_narrative"}
FAULT_POINTS = {
    "after_prepare",
    "after_chapters",
    "after_blob",
    "during_history",
    "after_history",
    "after_plan",
    "before_commit",
    "after_commit",
}
R07_PLANNING_FAULT_POINTS = FAULT_POINTS - {"after_chapters"}


class PlanstoreError(RuntimeError):
    """正式 writer 在写入前或恢复时拒绝继续。"""


class InjectedCrash(RuntimeError):
    """只供故障注入测试使用；调用方必须模拟进程重启后恢复。"""


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _fact_basis_sha256(records: list[dict[str, Any]]) -> str:
    return _sha256_json(sorted(records, key=lambda item: str(item.get("id"))))


def _validate_chapter_revision_ref(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != CHAPTER_REVISION_REF_KEYS:
        raise PlanstoreError("CHAPTER_REVISION_REF_SHAPE_INVALID")
    chapter_id = value.get("chapter_id")
    revision_no = value.get("revision_no")
    revision_sha = value.get("revision_text_sha256")
    if not isinstance(chapter_id, str) or C1_RE.fullmatch(chapter_id) is None:
        raise PlanstoreError("CHAPTER_REVISION_REF_CHAPTER_INVALID")
    if (
        not isinstance(revision_no, int)
        or isinstance(revision_no, bool)
        or revision_no <= 0
    ):
        raise PlanstoreError("CHAPTER_REVISION_REF_NUMBER_INVALID")
    if not isinstance(revision_sha, str) or SHA256_RE.fullmatch(revision_sha) is None:
        raise PlanstoreError("CHAPTER_REVISION_REF_SHA_INVALID")
    return value


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlanstoreError(f"REQUIRED_FILE_MISSING:{path.name}") from exc
    except json.JSONDecodeError as exc:
        raise PlanstoreError(f"INVALID_JSON:{path.name}:{exc.lineno}") from exc


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_bytes().splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PlanstoreError(f"INVALID_JSONL:{path.name}:{line_no}") from exc
        if not isinstance(value, dict):
            raise PlanstoreError(f"JSONL_ROW_NOT_OBJECT:{path.name}:{line_no}")
        rows.append(value)
    return rows


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temp.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    _fsync_directory(path.parent)


def _write_json_atomic(path: Path, value: Any) -> None:
    _write_bytes_atomic(path, _canonical_bytes(value))


def _append_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    _append_bytes(path, _canonical_bytes(value))


def _file_bytes(path: Path) -> bytes:
    return path.read_bytes() if path.exists() else b""


def _truncate_file(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.truncate(size)
        handle.flush()
        os.fsync(handle.fileno())


def _journal_path(root: Path, operation_id: str) -> Path:
    digest = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()
    return root / ".planstore_txn" / f"{digest}.json"


@contextmanager
def _exclusive_lock(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".planstore.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _validate_operation_id(operation_id: Any) -> str:
    if not isinstance(operation_id, str) or OPERATION_RE.fullmatch(operation_id) is None:
        raise PlanstoreError("OPERATION_ID_INVALID")
    return operation_id


def _commit_rows(root: Path) -> list[dict[str, Any]]:
    return _read_jsonl(root / "commit_log.jsonl")


def _operation_rows(root: Path, operation_id: str) -> list[dict[str, Any]]:
    return [row for row in _commit_rows(root) if row.get("op") == operation_id]


def _phase_state(rows: list[dict[str, Any]]) -> str:
    phases = [row.get("phase") for row in rows]
    if phases.count("commit") > 1 or phases.count("prepare") > 1 or phases.count("rolled_back") > 1:
        return "NEEDS_MANUAL_RECOVERY"
    if "commit" in phases and "rolled_back" in phases:
        return "NEEDS_MANUAL_RECOVERY"
    if "commit" in phases:
        return "COMMITTED"
    if "rolled_back" in phases:
        return "NOT_HAPPENED"
    if "prepare" in phases:
        return "PENDING_RECOVERY"
    return "NOT_HAPPENED"


def _operation_status_unlocked(root: Path, operation_id: str) -> dict[str, Any]:
    operation_id = _validate_operation_id(operation_id)
    rows = _operation_rows(root, operation_id)
    state = _phase_state(rows)
    prepare = next((row for row in rows if row.get("phase") == "prepare"), None)
    journal_path = _journal_path(root, operation_id)
    if state == "PENDING_RECOVERY":
        if not journal_path.exists():
            state = "NEEDS_MANUAL_RECOVERY"
        else:
            try:
                journal = _read_json(journal_path)
                if journal.get("version") == 2:
                    recognizable = _generic_journal_is_recognizable(root, journal)
                else:
                    plan_sha = _sha256_bytes(_file_bytes(root / "plan.json"))
                    chapters_sha = _sha256_bytes(_file_bytes(root / "chapters.json"))
                    allowed_plan = {
                        journal["before"]["plan_sha256"],
                        journal["after"]["plan_sha256"],
                    }
                    allowed_chapters = {
                        journal["before"]["chapters_sha256"],
                        journal["after"]["chapters_sha256"],
                    }
                    recognizable = (
                        plan_sha in allowed_plan
                        and chapters_sha in allowed_chapters
                        and _history_append_is_recognizable(
                            root / "plan_history.jsonl", journal
                        )
                    )
                if not recognizable:
                    state = "NEEDS_MANUAL_RECOVERY"
            except (KeyError, TypeError, PlanstoreError):
                state = "NEEDS_MANUAL_RECOVERY"
    return {
        "operation_id": operation_id,
        "state": state,
        "terminal_phase": (
            "commit" if state == "COMMITTED" else "rolled_back" if rows and state == "NOT_HAPPENED" else None
        ),
        "request_sha256": None if prepare is None else prepare.get("request_sha256"),
        "story_commit_seq": None if prepare is None else prepare.get("story_commit_seq"),
        "journal_present": journal_path.exists(),
    }


def operation_status(project_dir: str | Path, operation_id: str) -> dict[str, Any]:
    root = Path(project_dir)
    with _exclusive_lock(root):
        return _operation_status_unlocked(root, operation_id)


def _next_story_commit_seq(root: Path) -> int:
    values = [
        row.get("story_commit_seq")
        for row in _commit_rows(root)
        if row.get("phase") == "prepare" and isinstance(row.get("story_commit_seq"), int)
    ]
    return max(values, default=0) + 1


def _validate_action_and_work(action: Any, current_work: Any) -> None:
    if not isinstance(action, dict) or set(action) != ACTION_KEYS:
        if isinstance(action, dict) and set(action) & FORBIDDEN_TRUTH_KEYS:
            raise PlanstoreError("HANDOVER_TRUTH_MUTATION_FORBIDDEN")
        raise PlanstoreError("HANDOVER_ACTION_SCHEMA_MISMATCH")
    if not isinstance(current_work, dict) or set(current_work) != WORK_KEYS:
        raise PlanstoreError("WORK_DRAFT_SCHEMA_MISMATCH")
    if action.get("contract") != "WORK_DRAFT_HANDOVER_ACTION" or action.get("version") != "v1":
        raise PlanstoreError("HANDOVER_ACTION_IDENTITY_INVALID")
    if action.get("actor") != "author" or action.get("intent") != "adopt_as_manuscript":
        raise PlanstoreError("AUTHOR_EXPLICIT_INTENT_REQUIRED")
    if action.get("target_contract") != "C1_CHAPTER_DOC":
        raise PlanstoreError("C1_TARGET_INVALID")
    if action.get("target_planstore_result") != "handover_parts":
        raise PlanstoreError("PLANSTORE_TARGET_INVALID")
    if current_work.get("contract") != "WRITING_DESK_WORK_DRAFT" or current_work.get("version") != "v1":
        raise PlanstoreError("WORK_DRAFT_IDENTITY_INVALID")
    if current_work.get("state") != "working":
        raise PlanstoreError("WORK_DRAFT_NOT_WORKING")
    if current_work.get("text_sha256") != _sha256_bytes(str(current_work.get("text", "")).encode("utf-8")):
        raise PlanstoreError("WORK_TEXT_SHA_MISMATCH")
    if action.get("work_ref") != current_work.get("work_ref"):
        raise PlanstoreError("WORK_REF_MISMATCH")
    if action.get("work_rev") != current_work.get("work_rev"):
        raise PlanstoreError("STALE_WORK_REVISION")
    if action.get("slot_ref") != current_work.get("slot_ref"):
        raise PlanstoreError("SLOT_REF_MISMATCH")
    if action.get("source_outline_ref") != current_work.get("source_outline_ref"):
        raise PlanstoreError("SOURCE_OUTLINE_REF_MISMATCH")
    _validate_operation_id(action.get("operation_id"))


def _validate_plan(plan: Any) -> None:
    if not isinstance(plan, dict) or plan.get("schema") != "plan-v2" or plan.get("ledger") != "plan":
        raise PlanstoreError("PLAN_V2_REQUIRED")
    arrays = {
        "slots",
        "scenes",
        "events",
        "slot_mappings",
        "reconciliation_edges",
    }
    if any(not isinstance(plan.get(key), list) for key in arrays):
        raise PlanstoreError("PLAN_REQUIRED_ARRAY_MISSING")
    if not isinstance(plan.get("slot_sequence"), list) or not isinstance(plan.get("id_counters"), dict):
        raise PlanstoreError("PLAN_ID_OR_SEQUENCE_MISSING")
    if set(plan) & {"facts", "F-", "actual", "actuality"}:
        raise PlanstoreError("PLAN_MUST_NOT_CONTAIN_TRUTH_FIELDS")
    slot_ids = [item.get("id") for item in plan["slots"]]
    scene_ids = {item.get("id") for item in plan["scenes"]}
    event_ids = {item.get("id") for item in plan["events"]}
    if len(slot_ids) != len(set(slot_ids)) or any(ref not in slot_ids for ref in plan["slot_sequence"]):
        raise PlanstoreError("PLAN_SLOT_IDENTITY_INVALID")
    mapping_ids = [item.get("id") for item in plan["slot_mappings"]]
    if len(mapping_ids) != len(set(mapping_ids)):
        raise PlanstoreError("MAPPING_ID_DUPLICATE")
    mappings_by_id = {item.get("id"): item for item in plan["slot_mappings"]}
    for item in plan["slot_mappings"]:
        if (
            set(item) != MAP_KEYS
            or not isinstance(item.get("id"), str)
            or MAP_RE.fullmatch(item["id"]) is None
        ):
            raise PlanstoreError("MAPPING_SHAPE_INVALID")
        mapping_kind = item.get("mapping_kind")
        slot_ref = item.get("slot_ref")
        if mapping_kind in MAPPING_KINDS_WITH_SLOT:
            if not isinstance(slot_ref, str) or slot_ref not in slot_ids:
                raise PlanstoreError("MAPPING_SLOT_REF_INVALID")
        elif mapping_kind in MAPPING_KINDS_WITHOUT_SLOT:
            if slot_ref is not None:
                raise PlanstoreError("MAPPING_SLOT_REF_MUST_BE_NULL")
        else:
            raise PlanstoreError("MAPPING_KIND_INVALID")
        chapter_id = item.get("chapter_id")
        if chapter_id is not None and (
            not isinstance(chapter_id, str) or C1_RE.fullmatch(chapter_id) is None
        ):
            raise PlanstoreError("MAPPING_CHAPTER_ID_INVALID")
        expected_chapter_no = item.get("expected_chapter_no")
        if expected_chapter_no is not None and (
            not isinstance(expected_chapter_no, int)
            or isinstance(expected_chapter_no, bool)
            or expected_chapter_no <= 0
        ):
            raise PlanstoreError("MAPPING_EXPECTED_CHAPTER_NO_INVALID")
        if chapter_id is None and expected_chapter_no is None:
            raise PlanstoreError("MAPPING_PREADJUSTMENT_CHAPTER_NO_REQUIRED")
        if not isinstance(item.get("reason"), str):
            raise PlanstoreError("MAPPING_REASON_INVALID")
        if item.get("decided_by") not in {"author", "auto"}:
            raise PlanstoreError("MAPPING_DECIDED_BY_INVALID")
        if item.get("mapping_status") == "active":
            if item.get("superseded_by") is not None:
                raise PlanstoreError("ACTIVE_MAPPING_HAS_SUPERSEDED_BY")
        elif item.get("mapping_status") == "superseded":
            if item.get("superseded_by") not in mapping_ids or item.get("superseded_by") == item.get("id"):
                raise PlanstoreError("SUPERSEDED_BY_INVALID")
            replacement = mappings_by_id[item["superseded_by"]]
            if replacement.get("mapping_status") != "active":
                raise PlanstoreError("SUPERSEDED_BY_NOT_ACTIVE")
        else:
            raise PlanstoreError("MAPPING_STATUS_INVALID")
    map_numbers = [
        int(match.group(1))
        for mapping_id in mapping_ids
        for match in [MAP_RE.fullmatch(str(mapping_id))]
        if match is not None
    ]
    map_counter = plan["id_counters"].get("MAP")
    if not isinstance(map_counter, int) or map_counter < 0 or map_counter != max(map_numbers, default=0):
        raise PlanstoreError("MAP_COUNTER_DRIFT")
    for slot in plan["slots"]:
        if any(ref not in scene_ids for ref in slot.get("scene_refs", [])):
            raise PlanstoreError("SLOT_SCENE_REF_INVALID")
    for scene in plan["scenes"]:
        if scene.get("slot_ref") not in slot_ids or any(ref not in event_ids for ref in scene.get("pe_refs", [])):
            raise PlanstoreError("SCENE_REFERENCE_INVALID")

    edge_ids = [item.get("id") for item in plan["reconciliation_edges"]]
    if len(edge_ids) != len(set(edge_ids)):
        raise PlanstoreError("RECONCILIATION_EDGE_ID_DUPLICATE")
    source_keys = [
        (item.get("source_run_id"), item.get("source_item_key"))
        for item in plan["reconciliation_edges"]
    ]
    if len(source_keys) != len(set(source_keys)):
        raise PlanstoreError("RECONCILIATION_SOURCE_IDENTITY_DUPLICATE")
    edges_by_id = {item.get("id"): item for item in plan["reconciliation_edges"]}
    for edge in plan["reconciliation_edges"]:
        if (
            frozenset(edge)
            not in {
                frozenset(RECONCILIATION_EDGE_KEYS),
                frozenset(RECONCILIATION_EDGE_R07_KEYS),
            }
            or not isinstance(edge.get("id"), str)
            or RECONCILIATION_EDGE_RE.fullmatch(edge["id"]) is None
        ):
            raise PlanstoreError("RECONCILIATION_EDGE_SHAPE_INVALID")
        planned_ref = edge.get("planned_ref")
        planned_rev = edge.get("planned_rev")
        if edge.get("outcome") == "unplanned":
            if planned_ref is not None or planned_rev is not None:
                raise PlanstoreError("UNPLANNED_EDGE_BINDING_INVALID")
        elif (
            not isinstance(planned_ref, str)
            or not planned_ref
            or not isinstance(planned_rev, int)
            or isinstance(planned_rev, bool)
            or planned_rev <= 0
        ):
            raise PlanstoreError("RECONCILIATION_PLANNED_BINDING_INVALID")
        fact_refs = edge.get("actual_fact_refs")
        fact_basis = edge.get("actual_fact_basis_sha256")
        if not isinstance(fact_refs, list) or any(not isinstance(ref, str) for ref in fact_refs):
            raise PlanstoreError("RECONCILIATION_FACT_REFS_INVALID")
        if len(fact_refs) != len(set(fact_refs)):
            raise PlanstoreError("RECONCILIATION_FACT_REF_DUPLICATE")
        if fact_refs:
            if not isinstance(fact_basis, str) or SHA256_RE.fullmatch(fact_basis) is None:
                raise PlanstoreError("RECONCILIATION_FACT_BASIS_REQUIRED")
        elif fact_basis is not None:
            raise PlanstoreError("EMPTY_RECONCILIATION_FACT_BASIS_MUST_BE_NULL")
        if not isinstance(edge.get("chapter_ref"), str) or C1_RE.fullmatch(edge["chapter_ref"]) is None:
            raise PlanstoreError("RECONCILIATION_CHAPTER_REF_INVALID")
        if "chapter_revision_ref" in edge:
            revision_ref = _validate_chapter_revision_ref(edge["chapter_revision_ref"])
            if revision_ref["chapter_id"] != edge["chapter_ref"]:
                raise PlanstoreError("RECONCILIATION_CHAPTER_REVISION_REF_MISMATCH")
            if revision_ref["revision_text_sha256"] != edge.get("chapter_text_sha256"):
                raise PlanstoreError("RECONCILIATION_CHAPTER_REVISION_SHA_MISMATCH")
        if not isinstance(edge.get("slot_ref"), str) or not edge["slot_ref"]:
            raise PlanstoreError("RECONCILIATION_SLOT_REF_INVALID")
        if (
            not isinstance(edge.get("chapter_text_sha256"), str)
            or SHA256_RE.fullmatch(edge["chapter_text_sha256"]) is None
        ):
            raise PlanstoreError("RECONCILIATION_CHAPTER_SHA_INVALID")
        if (
            not isinstance(edge.get("source_run_id"), str)
            or OPERATION_RE.fullmatch(edge["source_run_id"]) is None
            or not isinstance(edge.get("source_item_key"), str)
            or not edge["source_item_key"]
        ):
            raise PlanstoreError("RECONCILIATION_SOURCE_IDENTITY_INVALID")
        if edge.get("outcome") not in {
            "exact",
            "variant",
            "unrealized",
            "contradicted",
            "unplanned",
            "ambiguous",
        }:
            raise PlanstoreError("RECONCILIATION_OUTCOME_INVALID")
        if edge.get("coverage") not in {"full", "partial"}:
            raise PlanstoreError("RECONCILIATION_COVERAGE_INVALID")
        if edge.get("outcome") == "variant":
            if not isinstance(edge.get("variant_note"), str) or not edge["variant_note"].strip():
                raise PlanstoreError("RECONCILIATION_VARIANT_NOTE_REQUIRED")
        elif edge.get("variant_note") is not None:
            raise PlanstoreError("RECONCILIATION_VARIANT_NOTE_FORBIDDEN")
        author_decision = edge.get("author_decision")
        if author_decision is not None:
            if (
                not isinstance(author_decision, dict)
                or set(author_decision) != {"action", "decided_at", "note"}
                or author_decision.get("action")
                not in {"accept_as_is", "defer", "void_plan", "rewrite_draft"}
                or not isinstance(author_decision.get("decided_at"), str)
                or not isinstance(author_decision.get("note"), str)
            ):
                raise PlanstoreError("RECONCILIATION_AUTHOR_DECISION_INVALID")
            if edge.get("decided_by") != "author":
                raise PlanstoreError("RECONCILIATION_AUTHOR_DECISION_SOURCE_INVALID")
        elif edge.get("decided_by") not in {"auto", "author"}:
            raise PlanstoreError("RECONCILIATION_DECIDED_BY_INVALID")
        if not isinstance(edge.get("basis_commit_seq"), int) or edge["basis_commit_seq"] < 0:
            raise PlanstoreError("RECONCILIATION_BASIS_COMMIT_INVALID")
        if edge.get("edge_status") == "active":
            if edge.get("superseded_by") is not None:
                raise PlanstoreError("ACTIVE_EDGE_HAS_SUPERSEDED_BY")
        elif edge.get("edge_status") == "superseded":
            replacement_id = edge.get("superseded_by")
            if replacement_id not in edge_ids or replacement_id == edge.get("id"):
                raise PlanstoreError("RECONCILIATION_SUPERSEDED_BY_INVALID")
            if edges_by_id[replacement_id].get("edge_status") != "active":
                raise PlanstoreError("RECONCILIATION_SUPERSEDED_BY_NOT_ACTIVE")
        elif edge.get("edge_status") == "stale":
            if edge.get("superseded_by") is not None:
                raise PlanstoreError("STALE_EDGE_HAS_SUPERSEDED_BY")
        else:
            raise PlanstoreError("RECONCILIATION_EDGE_STATUS_INVALID")
        if not isinstance(edge.get("rev"), int) or isinstance(edge.get("rev"), bool) or edge["rev"] <= 0:
            raise PlanstoreError("RECONCILIATION_EDGE_REV_INVALID")
    edge_numbers = [
        int(match.group(1))
        for edge_id in edge_ids
        for match in [RECONCILIATION_EDGE_RE.fullmatch(str(edge_id))]
        if match is not None
    ]
    edge_counter = plan["id_counters"].get("RE")
    if not isinstance(edge_counter, int) or edge_counter < 0 or edge_counter != max(edge_numbers, default=0):
        raise PlanstoreError("RECONCILIATION_EDGE_COUNTER_DRIFT")


def _next_c1_id(chapters: list[dict[str, Any]]) -> str:
    numbers = [
        int(match.group(1))
        for item in chapters
        for match in [C1_RE.fullmatch(str(item.get("id", "")))]
        if match is not None
    ]
    candidate = max(numbers, default=0) + 1
    used = {item.get("id") for item in chapters}
    while f"c{candidate:02d}" in used:
        candidate += 1
    return f"c{candidate:02d}"


def _blob_record(value: Any) -> tuple[str, dict[str, Any]]:
    digest = _sha256_json(value)
    return f"sha256:{digest}", {"digest": digest, "value": copy.deepcopy(value)}


def _history_row(
    *,
    operation_id: str,
    object_before: dict[str, Any],
    object_after: dict[str, Any],
    changes: dict[str, Any],
    timestamp: str,
    note: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    content_hash, blob = _blob_record(object_before)
    return (
        {
            "ts": timestamp,
            "op": operation_id,
            "actor": "author",
            "action": "handover",
            "object_id": object_after["id"],
            "rev": object_after["rev"],
            "changes": changes,
            "content_hash": content_hash,
            "note": note,
        },
        blob,
    )


def _build_transaction(
    root: Path,
    action: dict[str, Any],
    current_work: dict[str, Any],
    *,
    title: str,
    timestamp: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_action_and_work(action, current_work)
    if not isinstance(title, str) or not title:
        raise PlanstoreError("C1_TITLE_INVALID")
    plan_path = root / "plan.json"
    chapters_path = root / "chapters.json"
    history_path = root / "plan_history.jsonl"
    plan_before_bytes = _file_bytes(plan_path)
    chapters_before_bytes = _file_bytes(chapters_path)
    if not plan_before_bytes or not chapters_before_bytes:
        raise PlanstoreError("PLAN_OR_CHAPTERS_FILE_MISSING")
    plan_before = _read_json(plan_path)
    chapters_before = _read_json(chapters_path)
    if not isinstance(chapters_before, list):
        raise PlanstoreError("C1_CHAPTERS_NOT_LIST")
    _read_jsonl(history_path)
    _validate_plan(plan_before)
    chapter_ids = [item.get("id") for item in chapters_before]
    if len(chapter_ids) != len(set(chapter_ids)) or any(C1_RE.fullmatch(str(value)) is None for value in chapter_ids):
        raise PlanstoreError("C1_IDENTITY_INVALID")
    for mapping in plan_before["slot_mappings"]:
        if mapping.get("chapter_id") is not None and mapping.get("chapter_id") not in chapter_ids:
            raise PlanstoreError("MAPPING_CHAPTER_REF_NOT_FOUND")
    slot_matches = [item for item in plan_before["slots"] if item.get("id") == action["slot_ref"]]
    if len(slot_matches) != 1:
        raise PlanstoreError("PLAN_SLOT_NOT_FOUND")
    slot_before = slot_matches[0]
    if slot_before.get("slot_status") == "handed_over":
        raise PlanstoreError("SLOT_ALREADY_HANDED_OVER")
    checkpoint = slot_before.get("outline_checkpoint")
    if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("outline_rev"), int):
        raise PlanstoreError("OUTLINE_CHECKPOINT_MISSING")
    current_outline = f"{slot_before['id']}@outline-r{checkpoint['outline_rev']}"
    if action["source_outline_ref"] != current_outline:
        raise PlanstoreError("OUTLINE_NOT_CURRENT")

    chapter_id = _next_c1_id(chapters_before)
    chapter = {
        "id": chapter_id,
        "title": title,
        "kind": "draft",
        "text": current_work["text"],
        "added_at": timestamp,
    }
    chapters_after = [*copy.deepcopy(chapters_before), chapter]
    plan_after = copy.deepcopy(plan_before)
    slot_after = next(item for item in plan_after["slots"] if item["id"] == action["slot_ref"])
    scene_refs = list(slot_after.get("scene_refs", []))
    scenes_after = [item for item in plan_after["scenes"] if item.get("id") in scene_refs]
    if len(scenes_after) != len(scene_refs):
        raise PlanstoreError("COVERED_SCENE_REF_NOT_FOUND")
    scenes_by_id = {item["id"]: item for item in scenes_after}
    pe_refs = [pe for scene_ref in scene_refs for pe in scenes_by_id[scene_ref].get("pe_refs", [])]
    events_after = [item for item in plan_after["events"] if item.get("id") in pe_refs]
    if len(events_after) != len(pe_refs):
        raise PlanstoreError("COVERED_PE_REF_NOT_FOUND")

    counter = plan_after["id_counters"].get("MAP")
    if not isinstance(counter, int) or counter < 0:
        raise PlanstoreError("MAP_COUNTER_INVALID")
    mapping_id = f"MAP-{counter + 1:04d}"
    if mapping_id in {item.get("id") for item in plan_after["slot_mappings"]}:
        raise PlanstoreError("MAPPING_ID_DUPLICATE")
    mapping = {
        "id": mapping_id,
        "slot_ref": action["slot_ref"],
        "chapter_id": chapter_id,
        "expected_chapter_no": plan_after["slot_sequence"].index(action["slot_ref"]) + 1,
        "mapping_kind": "as_written",
        "reason": "",
        "decided_by": "author",
        "mapping_status": "active",
        "superseded_by": None,
    }
    if set(mapping) != MAP_KEYS or MAP_RE.fullmatch(mapping_id) is None:
        raise PlanstoreError("MAPPING_SHAPE_INVALID")
    handover_part = {
        "part_no": len(slot_after.get("handover_parts", [])) + 1,
        "chapter_id": chapter_id,
        "covered_scene_refs": scene_refs,
        "covered_pe_refs": pe_refs,
        "handed_at": timestamp,
        "decided_by": "author",
    }

    history_rows: list[dict[str, Any]] = []
    blobs: list[dict[str, Any]] = []
    old_handover_parts = copy.deepcopy(slot_after.get("handover_parts", []))
    old_slot_status = slot_after.get("slot_status")
    old_slot_truth = slot_after.get("truth_bearing")
    slot_after["handover_parts"] = [*old_handover_parts, handover_part]
    slot_after["slot_status"] = "handed_over"
    slot_after["truth_bearing"] = "handed_over"
    slot_after["rev"] += 1
    if "updated_at" in slot_after:
        slot_after["updated_at"] = timestamp
    row, blob = _history_row(
        operation_id=action["operation_id"],
        object_before=slot_before,
        object_after=slot_after,
        changes={
            "handover_parts": [old_handover_parts, slot_after["handover_parts"]],
            "slot_status": [old_slot_status, slot_after["slot_status"]],
            "truth_bearing": [old_slot_truth, slot_after["truth_bearing"]],
            "slot_mapping": [None, mapping],
        },
        timestamp=timestamp,
        note="作者显式以当前工作稿为准",
    )
    history_rows.append(row)
    blobs.append(blob)

    plan_before_scenes = {item["id"]: item for item in plan_before["scenes"]}
    for scene_after in scenes_after:
        scene_before = plan_before_scenes[scene_after["id"]]
        old_truth = scene_after.get("truth_bearing")
        scene_after["truth_bearing"] = "handed_over"
        scene_after["rev"] += 1
        if "updated_at" in scene_after:
            scene_after["updated_at"] = timestamp
        row, blob = _history_row(
            operation_id=action["operation_id"],
            object_before=scene_before,
            object_after=scene_after,
            changes={"truth_bearing": [old_truth, "handed_over"]},
            timestamp=timestamp,
            note="交棒覆盖场",
        )
        history_rows.append(row)
        blobs.append(blob)

    plan_before_events = {item["id"]: item for item in plan_before["events"]}
    for event_after in events_after:
        event_before = plan_before_events[event_after["id"]]
        old_truth = event_after.get("truth_bearing")
        event_after["truth_bearing"] = "handed_over"
        event_after["rev"] += 1
        if "updated_at" in event_after:
            event_after["updated_at"] = timestamp
        row, blob = _history_row(
            operation_id=action["operation_id"],
            object_before=event_before,
            object_after=event_after,
            changes={"truth_bearing": [old_truth, "handed_over"]},
            timestamp=timestamp,
            note="交棒覆盖计划事件",
        )
        history_rows.append(row)
        blobs.append(blob)

    plan_after["slot_mappings"].append(mapping)
    plan_after["id_counters"]["MAP"] = counter + 1
    _validate_plan(plan_after)

    history_before = _file_bytes(history_path)
    history_append = b"".join(_canonical_bytes(row) for row in history_rows)
    request_payload = {
        "action": action,
        "current_work": current_work,
        "title": title,
    }
    request_sha = _sha256_json(request_payload)
    story_seq = _next_story_commit_seq(root)
    receipt = {
        "operation_id": action["operation_id"],
        "status": "COMMITTED",
        "chapter_id": chapter_id,
        "slot_ref": action["slot_ref"],
        "handover_part": handover_part,
        "mapping": mapping,
        "slot_status": "handed_over",
        "story_commit_seq": story_seq,
        "facts_writes": 0,
        "new_f_ids": 0,
        "actual_changes": 0,
    }
    plan_after_bytes = _canonical_bytes(plan_after)
    chapters_after_bytes = _canonical_bytes(chapters_after)
    journal = {
        "version": 1,
        "operation_id": action["operation_id"],
        "request_sha256": request_sha,
        "story_commit_seq": story_seq,
        "before": {
            "plan_bytes": plan_before_bytes.decode("utf-8"),
            "plan_sha256": _sha256_bytes(plan_before_bytes),
            "chapters_bytes": chapters_before_bytes.decode("utf-8"),
            "chapters_sha256": _sha256_bytes(chapters_before_bytes),
            "history_size": len(history_before),
        },
        "after": {
            "plan_bytes": plan_after_bytes.decode("utf-8"),
            "plan_sha256": _sha256_bytes(plan_after_bytes),
            "chapters_bytes": chapters_after_bytes.decode("utf-8"),
            "chapters_sha256": _sha256_bytes(chapters_after_bytes),
            "history_append": history_append.decode("utf-8"),
            "history_append_sha256": _sha256_bytes(history_append),
        },
        "blobs": blobs,
        "receipt": receipt,
        "timestamp": timestamp,
    }
    prepare = {
        "op": action["operation_id"],
        "phase": "prepare",
        "story_commit_seq": story_seq,
        "request_sha256": request_sha,
        "files": [
            {
                "path": "chapters.json",
                "expected_sha256": journal["before"]["chapters_sha256"],
                "target_sha256": journal["after"]["chapters_sha256"],
            },
            {
                "path": "plan.json",
                "expected_sha256": journal["before"]["plan_sha256"],
                "target_sha256": journal["after"]["plan_sha256"],
            },
            {
                "path": "plan_history.jsonl",
                "append": True,
                "expected_size": journal["before"]["history_size"],
                "append_sha256": journal["after"]["history_append_sha256"],
            },
            *[
                {
                    "path": f"blobs/{item['digest'][:2]}/{item['digest']}.json",
                    "content_addressed": True,
                    "target_sha256": item["digest"],
                }
                for item in blobs
            ],
        ],
        "action": "handover",
        "ts": timestamp,
    }
    return journal, prepare


def _maybe_crash(fault_at: str | None, point: str) -> None:
    if fault_at == point:
        raise InjectedCrash(f"INJECTED_CRASH:{point}")


def _blob_path(root: Path, digest: str) -> Path:
    return root / "blobs" / digest[:2] / f"{digest}.json"


def _write_blobs(root: Path, blobs: list[dict[str, Any]]) -> None:
    for item in blobs:
        digest = item["digest"]
        path = _blob_path(root, digest)
        payload = _canonical_bytes(item["value"])
        if _sha256_bytes(payload) != digest:
            raise PlanstoreError("BLOB_DIGEST_MISMATCH")
        if path.exists():
            if _sha256_bytes(path.read_bytes()) != digest:
                raise PlanstoreError("EXISTING_BLOB_CORRUPT")
            continue
        _write_bytes_atomic(path, payload)


def _history_has_append(history_path: Path, journal: dict[str, Any]) -> bool:
    before_size = journal["before"]["history_size"]
    expected = journal["after"]["history_append"].encode("utf-8")
    payload = _file_bytes(history_path)
    return len(payload) == before_size + len(expected) and payload[before_size:] == expected


def _history_append_is_recognizable(history_path: Path, journal: dict[str, Any]) -> bool:
    before_size = journal["before"]["history_size"]
    expected = journal["after"]["history_append"].encode("utf-8")
    payload = _file_bytes(history_path)
    if len(payload) < before_size or len(payload) > before_size + len(expected):
        return False
    return expected.startswith(payload[before_size:])


def _generic_journal_is_recognizable(root: Path, journal: dict[str, Any]) -> bool:
    try:
        for item in journal["replacements"]:
            current = _sha256_bytes(_file_bytes(root / item["path"]))
            if current not in {item["before_sha256"], item["target_sha256"]}:
                return False
        for item in journal["appends"]:
            payload = _file_bytes(root / item["path"])
            before_size = item["before_size"]
            expected = item["append_bytes"].encode("utf-8")
            if len(payload) < before_size or len(payload) > before_size + len(expected):
                return False
            if not expected.startswith(payload[before_size:]):
                return False
        for item in journal["blobs"]:
            path = _blob_path(root, item["digest"])
            if path.exists() and _sha256_bytes(path.read_bytes()) != item["digest"]:
                return False
    except (KeyError, TypeError):
        return False
    return True


def _generic_journal_all_written(root: Path, journal: dict[str, Any]) -> bool:
    return (
        all(
            _sha256_bytes(_file_bytes(root / item["path"])) == item["target_sha256"]
            for item in journal["replacements"]
        )
        and all(
            len(_file_bytes(root / item["path"]))
            == item["before_size"] + len(item["append_bytes"].encode("utf-8"))
            and _file_bytes(root / item["path"])[item["before_size"] :]
            == item["append_bytes"].encode("utf-8")
            for item in journal["appends"]
        )
        and _all_blobs_present(root, journal)
    )


def _rollback_generic_journal(root: Path, journal: dict[str, Any]) -> None:
    for item in journal["replacements"]:
        _write_bytes_atomic(root / item["path"], item["before_bytes"].encode("utf-8"))
    for item in journal["appends"]:
        _truncate_file(root / item["path"], item["before_size"])
    _remove_unreferenced_operation_blobs(root, journal)


def _commit_generic_transaction_locked(
    root: Path,
    *,
    operation_id: str,
    action_name: str,
    request_sha256: str,
    replacements: dict[str, bytes],
    appends: dict[str, bytes],
    blobs: list[dict[str, Any]],
    receipt: dict[str, Any],
    timestamp: str,
    fault_at: str | None = None,
) -> dict[str, Any]:
    story_seq = _next_story_commit_seq(root)
    replacement_rows = []
    for relative_path, after_bytes in replacements.items():
        before_bytes = _file_bytes(root / relative_path)
        replacement_rows.append(
            {
                "path": relative_path,
                "before_bytes": before_bytes.decode("utf-8"),
                "before_sha256": _sha256_bytes(before_bytes),
                "target_bytes": after_bytes.decode("utf-8"),
                "target_sha256": _sha256_bytes(after_bytes),
            }
        )
    append_rows = []
    for relative_path, append_bytes in appends.items():
        append_rows.append(
            {
                "path": relative_path,
                "before_size": len(_file_bytes(root / relative_path)),
                "append_bytes": append_bytes.decode("utf-8"),
                "append_sha256": _sha256_bytes(append_bytes),
            }
        )
    journal = {
        "version": 2,
        "operation_id": operation_id,
        "action": action_name,
        "request_sha256": request_sha256,
        "story_commit_seq": story_seq,
        "replacements": replacement_rows,
        "appends": append_rows,
        "blobs": copy.deepcopy(blobs),
        "receipt": {**copy.deepcopy(receipt), "story_commit_seq": story_seq},
        "timestamp": timestamp,
    }
    prepare = {
        "op": operation_id,
        "phase": "prepare",
        "story_commit_seq": story_seq,
        "request_sha256": request_sha256,
        "receipt": copy.deepcopy(receipt),
        "files": [
            *[
                {
                    "path": item["path"],
                    "expected_sha256": item["before_sha256"],
                    "target_sha256": item["target_sha256"],
                }
                for item in replacement_rows
            ],
            *[
                {
                    "path": item["path"],
                    "append": True,
                    "expected_size": item["before_size"],
                    "append_sha256": item["append_sha256"],
                }
                for item in append_rows
            ],
            *[
                {
                    "path": f"blobs/{item['digest'][:2]}/{item['digest']}.json",
                    "content_addressed": True,
                    "target_sha256": item["digest"],
                }
                for item in blobs
            ],
        ],
        "action": action_name,
        "ts": timestamp,
    }
    journal_path = _journal_path(root, operation_id)
    _write_json_atomic(journal_path, journal)
    _append_jsonl(root / "commit_log.jsonl", prepare)
    _maybe_crash(fault_at, "after_prepare")

    for item in replacement_rows:
        _write_bytes_atomic(root / item["path"], item["target_bytes"].encode("utf-8"))
        stem = Path(item["path"]).stem
        _maybe_crash(fault_at, f"after_{stem}")

    _write_blobs(root, blobs)
    _maybe_crash(fault_at, "after_blob")

    for item in append_rows:
        append_bytes = item["append_bytes"].encode("utf-8")
        if fault_at == "during_history" and item["path"] == "plan_history.jsonl":
            _append_bytes(root / item["path"], append_bytes[: max(1, len(append_bytes) // 2)])
            raise InjectedCrash("INJECTED_CRASH:during_history")
        _append_bytes(root / item["path"], append_bytes)
    _maybe_crash(fault_at, "after_history")
    _maybe_crash(fault_at, "before_commit")
    _append_jsonl(
        root / "commit_log.jsonl",
        {"op": operation_id, "phase": "commit", "ts": timestamp},
    )
    _maybe_crash(fault_at, "after_commit")
    _cleanup_journal(journal_path)
    result = copy.deepcopy(journal["receipt"])
    result["replayed"] = False
    return result


def _all_blobs_present(root: Path, journal: dict[str, Any]) -> bool:
    return all(
        _blob_path(root, item["digest"]).exists()
        and _sha256_bytes(_blob_path(root, item["digest"]).read_bytes()) == item["digest"]
        for item in journal["blobs"]
    )


def _remove_unreferenced_operation_blobs(root: Path, journal: dict[str, Any]) -> None:
    referenced = {
        str(row.get("content_hash", "")).removeprefix("sha256:")
        for row in _read_jsonl(root / "plan_history.jsonl")
        if str(row.get("content_hash", "")).startswith("sha256:")
    }
    for item in journal["blobs"]:
        digest = item["digest"]
        if digest in referenced:
            continue
        path = _blob_path(root, digest)
        if path.exists():
            path.unlink()


def _cleanup_journal(path: Path) -> None:
    if path.exists():
        path.unlink()
        _fsync_directory(path.parent)


def _committed_receipt(root: Path, operation_id: str) -> dict[str, Any]:
    prepare = next(
        (row for row in _operation_rows(root, operation_id) if row.get("phase") == "prepare"),
        None,
    )
    history = [row for row in _read_jsonl(root / "plan_history.jsonl") if row.get("op") == operation_id]
    slot_rows = [row for row in history if "slot_mapping" in row.get("changes", {})]
    if prepare is None or len(slot_rows) != 1:
        raise PlanstoreError("COMMITTED_OPERATION_RECEIPT_UNRESOLVABLE")
    changes = slot_rows[0]["changes"]
    mapping = changes["slot_mapping"][1]
    parts = changes["handover_parts"][1]
    if not parts:
        raise PlanstoreError("COMMITTED_HANDOVER_PART_MISSING")
    plan = _read_json(root / "plan.json")
    chapters = _read_json(root / "chapters.json")
    if mapping["id"] not in {item.get("id") for item in plan.get("slot_mappings", [])}:
        raise PlanstoreError("COMMITTED_MAPPING_NOT_IN_PLAN")
    slots = [item for item in plan.get("slots", []) if item.get("id") == mapping["slot_ref"]]
    if len(slots) != 1 or parts[-1] not in slots[0].get("handover_parts", []):
        raise PlanstoreError("COMMITTED_HANDOVER_PART_NOT_IN_PLAN")
    if mapping["chapter_id"] not in {item.get("id") for item in chapters}:
        raise PlanstoreError("COMMITTED_C1_NOT_FOUND")
    return {
        "operation_id": operation_id,
        "status": "COMMITTED",
        "chapter_id": mapping["chapter_id"],
        "slot_ref": mapping["slot_ref"],
        "handover_part": parts[-1],
        "mapping": mapping,
        "slot_status": changes["slot_status"][1],
        "story_commit_seq": prepare["story_commit_seq"],
        "facts_writes": 0,
        "new_f_ids": 0,
        "actual_changes": 0,
        "replayed": True,
    }


def _recover_pending_locked(root: Path, *, timestamp: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    rows = _commit_rows(root)
    operations = sorted({str(row.get("op")) for row in rows if row.get("op") is not None})
    for operation_id in operations:
        op_rows = [row for row in rows if row.get("op") == operation_id]
        state = _phase_state(op_rows)
        journal_path = _journal_path(root, operation_id)
        if state == "COMMITTED":
            _cleanup_journal(journal_path)
            continue
        if state == "NEEDS_MANUAL_RECOVERY":
            raise PlanstoreError(f"NEEDS_MANUAL_RECOVERY:{operation_id}:COMMIT_LOG_CONFLICT")
        if state != "PENDING_RECOVERY":
            continue
        if not journal_path.exists():
            raise PlanstoreError(f"NEEDS_MANUAL_RECOVERY:{operation_id}:JOURNAL_MISSING")
        journal = _read_json(journal_path)
        if journal.get("operation_id") != operation_id:
            raise PlanstoreError(f"NEEDS_MANUAL_RECOVERY:{operation_id}:JOURNAL_ID_MISMATCH")
        if journal.get("version") == 2:
            if not _generic_journal_is_recognizable(root, journal):
                raise PlanstoreError(
                    f"NEEDS_MANUAL_RECOVERY:{operation_id}:UNRECOGNIZED_GENERIC_TRANSACTION"
                )
            if _generic_journal_all_written(root, journal):
                _append_jsonl(
                    root / "commit_log.jsonl",
                    {"op": operation_id, "phase": "commit", "ts": timestamp},
                )
                _cleanup_journal(journal_path)
                results.append({"operation_id": operation_id, "result": "COMMITTED"})
                continue
            _rollback_generic_journal(root, journal)
            _append_jsonl(
                root / "commit_log.jsonl",
                {"op": operation_id, "phase": "rolled_back", "ts": timestamp},
            )
            _cleanup_journal(journal_path)
            results.append({"operation_id": operation_id, "result": "ROLLED_BACK"})
            continue
        plan_bytes = _file_bytes(root / "plan.json")
        chapters_bytes = _file_bytes(root / "chapters.json")
        plan_sha = _sha256_bytes(plan_bytes)
        chapters_sha = _sha256_bytes(chapters_bytes)
        allowed_plan = {journal["before"]["plan_sha256"], journal["after"]["plan_sha256"]}
        allowed_chapters = {
            journal["before"]["chapters_sha256"],
            journal["after"]["chapters_sha256"],
        }
        if plan_sha not in allowed_plan or chapters_sha not in allowed_chapters:
            raise PlanstoreError(f"NEEDS_MANUAL_RECOVERY:{operation_id}:UNRECOGNIZED_FILE_HASH")
        if not _history_append_is_recognizable(root / "plan_history.jsonl", journal):
            raise PlanstoreError(f"NEEDS_MANUAL_RECOVERY:{operation_id}:UNRECOGNIZED_HISTORY_APPEND")
        history_before_size = journal["before"]["history_size"]
        all_written = (
            plan_sha == journal["after"]["plan_sha256"]
            and chapters_sha == journal["after"]["chapters_sha256"]
            and _history_has_append(root / "plan_history.jsonl", journal)
            and _all_blobs_present(root, journal)
        )
        if all_written:
            _append_jsonl(
                root / "commit_log.jsonl",
                {"op": operation_id, "phase": "commit", "ts": timestamp},
            )
            _cleanup_journal(journal_path)
            results.append({"operation_id": operation_id, "result": "COMMITTED"})
            continue
        _write_bytes_atomic(root / "plan.json", journal["before"]["plan_bytes"].encode("utf-8"))
        _write_bytes_atomic(
            root / "chapters.json", journal["before"]["chapters_bytes"].encode("utf-8")
        )
        _truncate_file(root / "plan_history.jsonl", history_before_size)
        _remove_unreferenced_operation_blobs(root, journal)
        _append_jsonl(
            root / "commit_log.jsonl",
            {"op": operation_id, "phase": "rolled_back", "ts": timestamp},
        )
        _cleanup_journal(journal_path)
        results.append({"operation_id": operation_id, "result": "ROLLED_BACK"})
    return results


def recover(project_dir: str | Path, *, timestamp: str) -> list[dict[str, Any]]:
    root = Path(project_dir)
    with _exclusive_lock(root):
        return _recover_pending_locked(root, timestamp=timestamp)


def _latest_committed_story_seq(root: Path) -> int:
    committed_operations = {
        row.get("op")
        for row in _commit_rows(root)
        if row.get("phase") == "commit" and row.get("op") is not None
    }
    return max(
        (
            row["story_commit_seq"]
            for row in _commit_rows(root)
            if row.get("phase") == "prepare"
            and row.get("op") in committed_operations
            and isinstance(row.get("story_commit_seq"), int)
        ),
        default=0,
    )


def _planning_record_identity(plan: dict[str, Any]) -> str:
    edges = plan["reconciliation_edges"]
    if edges and all("chapter_revision_ref" in edge for edge in edges):
        return "plan-v2-r07"
    if any("chapter_revision_ref" in edge for edge in edges):
        return "plan-v2-r06-r07-mixed-legacy-read-only"
    return "plan-v2-r06-legacy-read-only"


def _validate_r07_planning_record_input(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != R07_PLANNING_RECORD_INPUT_KEYS:
        raise PlanstoreError("R07_PLANNING_RECORD_INPUT_SCHEMA_MISMATCH")
    if not isinstance(value.get("source_item_key"), str) or not value["source_item_key"]:
        raise PlanstoreError("RECONCILIATION_SOURCE_IDENTITY_INVALID")
    return value


def _r07_material_fields(edge: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(edge[key])
        for key in R07_PLANNING_RECORD_INPUT_KEYS
    } | {"chapter_revision_ref": copy.deepcopy(edge["chapter_revision_ref"])}


def _replayed_r07_planning_receipt(root: Path, operation_id: str) -> dict[str, Any]:
    edges = [
        edge
        for edge in _read_json(root / "plan.json")["reconciliation_edges"]
        if edge.get("source_run_id") == operation_id
        and "chapter_revision_ref" in edge
    ]
    if len(edges) != 1:
        raise PlanstoreError("COMMITTED_R07_PLANNING_RECEIPT_UNRESOLVABLE")
    prepare = next(
        (
            row
            for row in _operation_rows(root, operation_id)
            if row.get("phase") == "prepare"
        ),
        None,
    )
    if prepare is None:
        raise PlanstoreError("COMMITTED_R07_PLANNING_RECEIPT_UNRESOLVABLE")
    edge = edges[0]
    return {
        "operation_id": operation_id,
        "status": "COMMITTED",
        "record_version": "r07",
        "record_ref": edge["id"],
        "chapter_revision_ref": copy.deepcopy(edge["chapter_revision_ref"]),
        "story_commit_seq": prepare["story_commit_seq"],
        "facts_writes": 0,
        "new_f_ids": 0,
        "actual_changes": 0,
        "replayed": True,
    }


def read_planning_records(project_dir: str | Path) -> dict[str, Any]:
    """读取 plan-v2；只有所有现存 RE 都带 revision ref 时才声明 r07。"""
    root = Path(project_dir)
    with _exclusive_lock(root):
        unsettled = [
            operation_id
            for operation_id in {
                str(row.get("op"))
                for row in _commit_rows(root)
                if row.get("op") is not None
            }
            if _operation_status_unlocked(root, operation_id)["state"]
            in {"PENDING_RECOVERY", "NEEDS_MANUAL_RECOVERY"}
        ]
        if unsettled:
            raise PlanstoreError(f"STORAGE_RECOVERY_REQUIRED:{sorted(unsettled)}")
        plan = _read_json(root / "plan.json")
        _validate_plan(plan)
        identity = _planning_record_identity(plan)
        return {
            "schema": "plan-v2",
            "record_identity": identity,
            "revision_aware": identity == "plan-v2-r07",
            "read_only_compatibility": identity != "plan-v2-r07",
            "records": copy.deepcopy(plan["reconciliation_edges"]),
        }


def write_revision_aware_planning_record(
    project_dir: str | Path,
    *,
    operation_id: str,
    planning_record: dict[str, Any],
    chapter_revision_ref: dict[str, Any],
    current_chapter_revision_ref: dict[str, Any],
    timestamp: str,
    fault_at: str | None = None,
) -> dict[str, Any]:
    """把一条带显式 C11 revision ref 的最小 r07 RE 写进现有 planstore。"""
    root = Path(project_dir)
    operation_id = _validate_operation_id(operation_id)
    planning_record = _validate_r07_planning_record_input(planning_record)
    chapter_revision_ref = _validate_chapter_revision_ref(chapter_revision_ref)
    current_chapter_revision_ref = _validate_chapter_revision_ref(
        current_chapter_revision_ref
    )
    if chapter_revision_ref != current_chapter_revision_ref:
        raise PlanstoreError("STALE_CHAPTER_REVISION_REF")
    if not isinstance(timestamp, str) or not timestamp:
        raise PlanstoreError("R07_PLANNING_TIMESTAMP_INVALID")
    if fault_at is not None and fault_at not in R07_PLANNING_FAULT_POINTS:
        raise PlanstoreError("UNKNOWN_R07_PLANNING_FAULT_POINT")

    request_sha = _sha256_json(
        {
            "operation_id": operation_id,
            "planning_record": planning_record,
            "chapter_revision_ref": chapter_revision_ref,
            "current_chapter_revision_ref": current_chapter_revision_ref,
        }
    )
    with _exclusive_lock(root):
        _recover_pending_locked(root, timestamp=timestamp)
        status = _operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            if status["request_sha256"] != request_sha:
                raise PlanstoreError("OPERATION_ID_PAYLOAD_CONFLICT")
            return _replayed_r07_planning_receipt(root, operation_id)
        if status["terminal_phase"] == "rolled_back":
            raise PlanstoreError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        if status["state"] == "NEEDS_MANUAL_RECOVERY":
            raise PlanstoreError("OPERATION_NEEDS_MANUAL_RECOVERY")

        plan_before = _read_json(root / "plan.json")
        _validate_plan(plan_before)
        legacy_edges = [
            edge["id"]
            for edge in plan_before["reconciliation_edges"]
            if "chapter_revision_ref" not in edge
        ]
        if legacy_edges:
            raise PlanstoreError(
                f"LEGACY_R06_RE_MIGRATION_REQUIRED:{','.join(legacy_edges)}"
            )
        if planning_record["chapter_ref"] != chapter_revision_ref["chapter_id"]:
            raise PlanstoreError("RECONCILIATION_CHAPTER_REVISION_REF_MISMATCH")
        mapping_matches = [
            item
            for item in plan_before["slot_mappings"]
            if item.get("slot_ref") == planning_record["slot_ref"]
            and item.get("chapter_id") == planning_record["chapter_ref"]
            and item.get("mapping_status") == "active"
        ]
        if len(mapping_matches) != 1:
            raise PlanstoreError("CURRENT_SLOT_MAPPING_NOT_FOUND")
        planned_objects = {
            item["id"]: item
            for key in ("events", "hooks", "must_carries")
            for item in plan_before.get(key, [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        planned_ref = planning_record["planned_ref"]
        if planned_ref is not None:
            current_planned = planned_objects.get(planned_ref)
            if current_planned is None:
                raise PlanstoreError("CURRENT_PLANNING_OBJECT_NOT_FOUND")
            if current_planned.get("rev") != planning_record["planned_rev"]:
                raise PlanstoreError("STALE_PLANNED_REVISION")

        material = copy.deepcopy(planning_record) | {
            "chapter_revision_ref": copy.deepcopy(chapter_revision_ref)
        }
        for edge in plan_before["reconciliation_edges"]:
            if edge.get("edge_status") == "active" and _r07_material_fields(edge) == material:
                return {
                    "operation_id": operation_id,
                    "status": "NO_CHANGE",
                    "record_version": "r07",
                    "record_ref": edge["id"],
                    "chapter_revision_ref": copy.deepcopy(chapter_revision_ref),
                    "story_commit_seq": _latest_committed_story_seq(root),
                    "facts_writes": 0,
                    "new_f_ids": 0,
                    "actual_changes": 0,
                    "replayed": False,
                }
        active_same_binding = [
            edge["id"]
            for edge in plan_before["reconciliation_edges"]
            if edge.get("edge_status") == "active"
            and edge.get("chapter_ref") == planning_record["chapter_ref"]
            and edge.get("planned_ref") == planning_record["planned_ref"]
        ]
        if active_same_binding:
            raise PlanstoreError(
                f"ACTIVE_RECONCILIATION_EDGE_ALREADY_EXISTS:{','.join(active_same_binding)}"
            )

        counter = plan_before["id_counters"].get("RE")
        if not isinstance(counter, int) or counter < 0:
            raise PlanstoreError("RE_COUNTER_INVALID")
        edge = {
            "id": f"RE-{counter + 1:04d}",
            "planned_ref": planning_record["planned_ref"],
            "planned_rev": planning_record["planned_rev"],
            "actual_fact_refs": [],
            "actual_fact_basis_sha256": None,
            "chapter_ref": planning_record["chapter_ref"],
            "chapter_revision_ref": copy.deepcopy(chapter_revision_ref),
            "slot_ref": planning_record["slot_ref"],
            "chapter_text_sha256": chapter_revision_ref["revision_text_sha256"],
            "source_run_id": operation_id,
            "source_item_key": planning_record["source_item_key"],
            "outcome": planning_record["outcome"],
            "coverage": planning_record["coverage"],
            "variant_note": planning_record["variant_note"],
            "author_decision": copy.deepcopy(planning_record["author_decision"]),
            "basis_commit_seq": _latest_committed_story_seq(root),
            "decided_by": planning_record["decided_by"],
            "edge_status": "active",
            "superseded_by": None,
            "rev": 1,
        }
        plan_after = copy.deepcopy(plan_before)
        plan_after["reconciliation_edges"].append(edge)
        plan_after["id_counters"]["RE"] = counter + 1
        _validate_plan(plan_after)

        before = {"id": edge["id"], "rev": 0, "state": "absent"}
        content_hash, blob = _blob_record(before)
        history_row = {
            "ts": timestamp,
            "op": operation_id,
            "actor": planning_record["decided_by"],
            "action": "planning_record_r07",
            "object_id": edge["id"],
            "rev": 1,
            "changes": {"state": [None, copy.deepcopy(edge)]},
            "content_hash": content_hash,
            "note": "显式章节修订依据的规划对账记录",
        }
        return _commit_generic_transaction_locked(
            root,
            operation_id=operation_id,
            action_name="planning_record_r07",
            request_sha256=request_sha,
            replacements={"plan.json": _canonical_bytes(plan_after)},
            appends={"plan_history.jsonl": _canonical_bytes(history_row)},
            blobs=[blob],
            receipt={
                "operation_id": operation_id,
                "status": "COMMITTED",
                "record_version": "r07",
                "record_ref": edge["id"],
                "chapter_revision_ref": copy.deepcopy(chapter_revision_ref),
                "facts_writes": 0,
                "new_f_ids": 0,
                "actual_changes": 0,
            },
            timestamp=timestamp,
            fault_at=fault_at,
        )


def accept_work_draft_handover(
    project_dir: str | Path,
    *,
    action: dict[str, Any],
    current_work: dict[str, Any],
    title: str,
    timestamp: str,
    fault_at: str | None = None,
) -> dict[str, Any]:
    root = Path(project_dir)
    if fault_at is not None and fault_at not in FAULT_POINTS:
        raise PlanstoreError("UNKNOWN_FAULT_POINT")
    _validate_action_and_work(action, current_work)
    operation_id = action["operation_id"]
    request_sha = _sha256_json({"action": action, "current_work": current_work, "title": title})
    with _exclusive_lock(root):
        _recover_pending_locked(root, timestamp=timestamp)
        status = _operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            if status["request_sha256"] != request_sha:
                raise PlanstoreError("OPERATION_ID_PAYLOAD_CONFLICT")
            return _committed_receipt(root, operation_id)
        if status["terminal_phase"] == "rolled_back":
            raise PlanstoreError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        if status["state"] == "NEEDS_MANUAL_RECOVERY":
            raise PlanstoreError("OPERATION_NEEDS_MANUAL_RECOVERY")

        journal, prepare = _build_transaction(
            root,
            action,
            current_work,
            title=title,
            timestamp=timestamp,
        )
        journal_path = _journal_path(root, operation_id)
        _write_json_atomic(journal_path, journal)
        _append_jsonl(root / "commit_log.jsonl", prepare)
        _maybe_crash(fault_at, "after_prepare")

        _write_bytes_atomic(root / "chapters.json", journal["after"]["chapters_bytes"].encode("utf-8"))
        _maybe_crash(fault_at, "after_chapters")

        _write_blobs(root, journal["blobs"])
        _maybe_crash(fault_at, "after_blob")

        history_append = journal["after"]["history_append"].encode("utf-8")
        if fault_at == "during_history":
            _append_bytes(root / "plan_history.jsonl", history_append[: max(1, len(history_append) // 2)])
            raise InjectedCrash("INJECTED_CRASH:during_history")
        _append_bytes(root / "plan_history.jsonl", history_append)
        _maybe_crash(fault_at, "after_history")

        _write_bytes_atomic(root / "plan.json", journal["after"]["plan_bytes"].encode("utf-8"))
        _maybe_crash(fault_at, "after_plan")
        _maybe_crash(fault_at, "before_commit")

        _append_jsonl(
            root / "commit_log.jsonl",
            {"op": operation_id, "phase": "commit", "ts": timestamp},
        )
        _maybe_crash(fault_at, "after_commit")
        _cleanup_journal(journal_path)
        receipt = copy.deepcopy(journal["receipt"])
        receipt["replayed"] = False
        return receipt


def verify_storage(project_dir: str | Path) -> dict[str, Any]:
    root = Path(project_dir)
    with _exclusive_lock(root):
        plan_bytes = _file_bytes(root / "plan.json")
        chapters_bytes = _file_bytes(root / "chapters.json")
        history_bytes = _file_bytes(root / "plan_history.jsonl")
        plan = _read_json(root / "plan.json")
        chapters = _read_json(root / "chapters.json")
        raw_facts = _read_json(root / "facts.json") if (root / "facts.json").exists() else []
        _validate_plan(plan)
        if not isinstance(chapters, list):
            raise PlanstoreError("C1_CHAPTERS_NOT_LIST")
        if not isinstance(raw_facts, list):
            if plan["reconciliation_edges"]:
                raise PlanstoreError("C4_FACTS_NOT_LIST")
            facts: list[dict[str, Any]] = []
        else:
            facts = raw_facts
        chapter_ids = [item.get("id") for item in chapters]
        if len(chapter_ids) != len(set(chapter_ids)):
            raise PlanstoreError("C1_ID_DUPLICATE")
        history = _read_jsonl(root / "plan_history.jsonl")
        commit_rows = _commit_rows(root)
        operation_ids = {row.get("op") for row in commit_rows if row.get("op") is not None}
        states = {
            op: _phase_state([row for row in commit_rows if row.get("op") == op])
            for op in operation_ids
        }
        pending = sorted(op for op, state in states.items() if state == "PENDING_RECOVERY")
        manual = sorted(op for op, state in states.items() if state == "NEEDS_MANUAL_RECOVERY")
        if pending or manual:
            raise PlanstoreError(f"STORAGE_NOT_SETTLED:pending={pending}:manual={manual}")
        blob_errors = []
        for row in history:
            ref = str(row.get("content_hash", ""))
            if not ref.startswith("sha256:"):
                blob_errors.append(f"{row.get('op')}:{row.get('object_id')}:NO_BLOB_REF")
                continue
            digest = ref.removeprefix("sha256:")
            path = _blob_path(root, digest)
            if not path.exists() or _sha256_bytes(path.read_bytes()) != digest:
                blob_errors.append(f"{row.get('op')}:{row.get('object_id')}:BLOB_INVALID")
        if blob_errors:
            raise PlanstoreError(f"HISTORY_BLOB_MISMATCH:{blob_errors}")
        committed = sorted(op for op, state in states.items() if state == "COMMITTED")
        committed_prepares: list[dict[str, Any]] = []
        for op in committed:
            prepare = next(
                row
                for row in commit_rows
                if row.get("op") == op and row.get("phase") == "prepare"
            )
            committed_prepares.append(prepare)
            if prepare.get("action") not in {
                "handover",
                "planning_record_r07",
                "reconciliation_observe",
                "reconciliation_fact_admission",
                "reconciliation_stale",
                "fact_review",
                "setting_ledger_write",
            }:
                continue
            op_history = [row for row in history if row.get("op") == op]
            if prepare.get("action") != "fact_review" and not op_history:
                raise PlanstoreError(f"COMMITTED_OPERATION_HISTORY_MISSING:{op}")
            files = prepare.get("files")
            if not isinstance(files, list):
                raise PlanstoreError(f"COMMIT_FILE_MANIFEST_INVALID:{op}")
            history_entries = [row for row in files if row.get("path") == "plan_history.jsonl"]
            if len(history_entries) != (1 if op_history else 0):
                raise PlanstoreError(f"HISTORY_MANIFEST_MISSING:{op}")
            if not op_history:
                continue
            history_entry = history_entries[0]
            history_payload = b"".join(_canonical_bytes(row) for row in op_history)
            if _sha256_bytes(history_payload) != history_entry.get("append_sha256"):
                raise PlanstoreError(f"HISTORY_APPEND_MANIFEST_MISMATCH:{op}")
            expected_size = history_entry.get("expected_size")
            if (
                not isinstance(expected_size, int)
                or expected_size < 0
                or history_bytes[expected_size : expected_size + len(history_payload)]
                != history_payload
            ):
                raise PlanstoreError(f"HISTORY_APPEND_POSITION_MISMATCH:{op}")
            blob_targets = {
                row.get("target_sha256")
                for row in files
                if row.get("content_addressed") is True
            }
            history_targets = {
                str(row.get("content_hash", "")).removeprefix("sha256:")
                for row in op_history
            }
            if blob_targets != history_targets:
                raise PlanstoreError(f"BLOB_MANIFEST_HISTORY_MISMATCH:{op}")
            for row in op_history:
                digest = str(row["content_hash"]).removeprefix("sha256:")
                blob_value = _read_json(_blob_path(root, digest))
                if (
                    not isinstance(blob_value, dict)
                    or blob_value.get("id") != row.get("object_id")
                    or not isinstance(blob_value.get("rev"), int)
                    or blob_value["rev"] + 1 != row.get("rev")
                ):
                    raise PlanstoreError(f"HISTORY_BLOB_IDENTITY_MISMATCH:{op}:{row.get('object_id')}")
            if prepare.get("action") == "handover":
                _committed_receipt(root, str(op))

        current_files = {
            "plan.json": plan_bytes,
            "chapters.json": chapters_bytes,
        }
        if (root / "facts.json").exists():
            current_files["facts.json"] = _file_bytes(root / "facts.json")
        for prepare in committed_prepares:
            for file_entry in prepare.get("files") or []:
                path_name = file_entry.get("path")
                if (
                    isinstance(path_name, str)
                    and file_entry.get("append") is not True
                    and file_entry.get("content_addressed") is not True
                    and path_name not in current_files
                    and (root / path_name).exists()
                ):
                    current_files[path_name] = _file_bytes(root / path_name)
        for path_name, current_bytes in current_files.items():
            candidates = [
                (prepare.get("story_commit_seq"), file_entry)
                for prepare in committed_prepares
                if isinstance(prepare.get("story_commit_seq"), int)
                for file_entry in prepare.get("files", [])
                if file_entry.get("path") == path_name
                and isinstance(file_entry.get("target_sha256"), str)
            ]
            if candidates:
                _, latest = max(candidates, key=lambda item: item[0])
                if _sha256_bytes(current_bytes) != latest["target_sha256"]:
                    label = path_name.removesuffix(".json").upper()
                    raise PlanstoreError(f"FINAL_{label}_COMMIT_HASH_MISMATCH")
        facts_by_id = {item.get("id"): item for item in facts if isinstance(item, dict)}
        chapters_by_id = {
            item.get("id"): item for item in chapters if isinstance(item, dict)
        }
        stale_edges = []
        for edge in plan["reconciliation_edges"]:
            if edge["edge_status"] != "active" or not edge["actual_fact_refs"]:
                continue
            supporting = [facts_by_id.get(ref) for ref in edge["actual_fact_refs"]]
            chapter = chapters_by_id.get(edge["chapter_ref"])
            revision_stale = (
                "chapter_revision_ref" in edge
                and (
                    chapter is None
                    or chapter.get("chapter_revision_ref")
                    != edge["chapter_revision_ref"]
                )
            )
            if (
                revision_stale
                or (
                    "chapter_revision_ref" not in edge
                    and isinstance(chapter, dict)
                    and chapter.get("contract") == "C1_CHAPTER_DOC"
                    and chapter.get("version") == "v1"
                )
                or any(
                    item is None or item.get("status") != "confirmed"
                    for item in supporting
                )
                or _fact_basis_sha256(supporting) != edge["actual_fact_basis_sha256"]
            ):
                stale_edges.append(edge["id"])
        return {
            "status": "PASS",
            "committed_operations": committed,
            "rolled_back_operations": sorted(op for op, state in states.items() if state == "NOT_HAPPENED"),
            "chapter_count": len(chapters),
            "handover_part_count": sum(len(slot.get("handover_parts", [])) for slot in plan["slots"]),
            "mapping_count": len(plan["slot_mappings"]),
            "reconciliation_edge_count": len(plan["reconciliation_edges"]),
            "stale_reconciliation_edges": stale_edges,
            "history_row_count": len(history),
            "blob_ref_count": len(history),
            "fact_count": len(facts),
            "confirmed_fact_count": sum(
                item.get("status") == "confirmed" for item in facts if isinstance(item, dict)
            ),
            "stored_actual_fields": 0,
        }


def _load_object(path: str) -> dict[str, Any]:
    value = _read_json(Path(path))
    if not isinstance(value, dict):
        raise PlanstoreError(f"INPUT_NOT_OBJECT:{path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="plan-v2 规划记录、工作稿交棒与恢复工具")
    sub = parser.add_subparsers(dest="command", required=True)

    planning_write = sub.add_parser("planning-write-r07")
    planning_write.add_argument("project_dir")
    planning_write.add_argument("--operation-id", required=True)
    planning_write.add_argument("--record", required=True)
    planning_write.add_argument("--chapter-revision-ref", required=True)
    planning_write.add_argument("--current-chapter-revision-ref", required=True)
    planning_write.add_argument("--timestamp", required=True)
    planning_write.add_argument("--fault-at", choices=sorted(R07_PLANNING_FAULT_POINTS))

    planning_read = sub.add_parser("planning-read")
    planning_read.add_argument("project_dir")

    handover = sub.add_parser("handover")
    handover.add_argument("project_dir")
    handover.add_argument("--action", required=True)
    handover.add_argument("--work", required=True)
    handover.add_argument("--title", required=True)
    handover.add_argument("--timestamp", required=True)
    handover.add_argument("--fault-at", choices=sorted(FAULT_POINTS))

    recovery = sub.add_parser("recover")
    recovery.add_argument("project_dir")
    recovery.add_argument("--timestamp", required=True)

    status = sub.add_parser("status")
    status.add_argument("project_dir")
    status.add_argument("operation_id")

    verify = sub.add_parser("verify")
    verify.add_argument("project_dir")

    args = parser.parse_args()
    try:
        if args.command == "planning-write-r07":
            result = write_revision_aware_planning_record(
                args.project_dir,
                operation_id=args.operation_id,
                planning_record=_load_object(args.record),
                chapter_revision_ref=_load_object(args.chapter_revision_ref),
                current_chapter_revision_ref=_load_object(
                    args.current_chapter_revision_ref
                ),
                timestamp=args.timestamp,
                fault_at=args.fault_at,
            )
        elif args.command == "planning-read":
            result = read_planning_records(args.project_dir)
        elif args.command == "handover":
            result = accept_work_draft_handover(
                args.project_dir,
                action=_load_object(args.action),
                current_work=_load_object(args.work),
                title=args.title,
                timestamp=args.timestamp,
                fault_at=args.fault_at,
            )
        elif args.command == "recover":
            result = {"status": "PASS", "operations": recover(args.project_dir, timestamp=args.timestamp)}
        elif args.command == "status":
            result = operation_status(args.project_dir, args.operation_id)
        else:
            result = verify_storage(args.project_dir)
    except InjectedCrash as exc:
        print(json.dumps({"status": "INJECTED_CRASH", "reason": str(exc)}, ensure_ascii=False))
        return 75
    except PlanstoreError as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
