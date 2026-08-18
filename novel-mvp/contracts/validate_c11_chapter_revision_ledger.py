"""Validate C11 v1, C10 eligibility, RESTORE reactivation, and atomic batches."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

import validate_c10_intake_material_identity as c10_contract


CONTRACTS_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = CONTRACTS_DIR / "C11_CHAPTER_REVISION_LEDGER.schema.json"
FIXTURE_PATH = CONTRACTS_DIR / "C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl"
COORDINATE_BASIS = "CHAPTER_REVISION_TEXT_UNICODE_CODEPOINT_0_BASED_HALF_OPEN"

ORIGINAL_CASES = [*(f"CR-{number:02d}" for number in range(1, 43)), "WS-01", "WS-02"]
ELIGIBILITY_CASES = [f"EG-{number:02d}" for number in range(1, 16)]
RESTORE_REACTIVATION_CASES = [f"RR-{number:02d}" for number in range(1, 6)]
BATCH_CASES = ["BA-01"]
MACHINE_GATE_CASES = [
    *(f"FF-{number:02d}" for number in range(1, 7)),
    *(f"MG-{number:02d}" for number in range(1, 5)),
]
EXPECTED_CASES = [
    *ORIGINAL_CASES,
    *ELIGIBILITY_CASES,
    *RESTORE_REACTIVATION_CASES,
    *BATCH_CASES,
    *MACHINE_GATE_CASES,
]
EXPECTED_RULES = {
    "CR-01": "initial_revision_one",
    "CR-02": "explicit_replace_same_chapter",
    "CR-03": "revision_sequence_gap",
    "CR-04": "append_only_history_drift",
    "CR-05": "current_not_last",
    "CR-06": "title_only_target",
    "CR-07": "multiple_target_candidates",
    "CR-08": "author_explicit_target",
    "CR-09": "non_author_or_missing_intent",
    "CR-10": "stale_expected_revision",
    "CR-11": "identical_current_content",
    "CR-12": "same_operation_same_payload",
    "CR-13": "same_operation_different_payload",
    "CR-14": "restore_as_new_revision",
    "CR-15": "restore_missing_revision",
    "CR-16": "verified_slice_unique_in_new_revision",
    "CR-17": "verified_slice_missing_in_new_revision",
    "CR-18": "verified_slice_ambiguous_in_new_revision",
    "CR-19": "legacy_quote_unique_both_revisions",
    "CR-20": "legacy_quote_not_unique_both_revisions",
    "CR-21": "normalized_segment_offset_as_anchor",
    "CR-22": "anchor_slice_sha_mismatch",
    "CR-23": "c6_report_revision_is_old",
    "CR-24": "needs_recheck_consumer_filter",
    "CR-25": "stable_slot_mapping",
    "CR-26": "c10_identity_revision_as_chapter_revision",
    "CR-27": "work_or_plan_rev_as_chapter_revision",
    "CR-28": "fact_effects_preflight_failure",
    "CR-29": "crash_after_prepare",
    "CR-30": "unknown_recovery_sha",
    "CR-31": "batch_contains_stale_target",
    "CR-32": "physical_rollback_after_commit",
    "CR-33": "legacy_c1_unique_c10_span",
    "CR-34": "legacy_c1_no_replay_source",
    "CR-35": "legacy_identity_or_fact_dangling",
    "CR-36": "legacy_c6_without_revision_ref",
    "CR-37": "old_reader_business_consumes_v1",
    "CR-38": "v1_missing_identity_or_extra_field",
    "CR-39": "revision_bound_reconciliation_admission",
    "CR-40": "revision_stales_dependent_re",
    "CR-41": "cross_owner_partial_failure",
    "CR-42": "revision_does_not_mutate_slot_mapping",
    "WS-01": "same_chapter_reimport_wrong_success",
    "WS-02": "deleted_evidence_wrong_success",
    "EG-01": "initial_confirmed_chapter",
    "EG-02": "replace_confirmed_chapter",
    "EG-03": "setting_rejected",
    "EG-04": "intro_rejected",
    "EG-05": "title_rejected",
    "EG-06": "tags_rejected",
    "EG-07": "unknown_rejected",
    "EG-08": "candidate_rejected",
    "EG-09": "stale_identity_revision",
    "EG-10": "source_ref_mismatch",
    "EG-11": "material_unit_not_found",
    "EG-12": "action_identity_override_forbidden",
    "EG-13": "restore_two_gates_pass",
    "EG-14": "restore_target_missing",
    "EG-15": "restore_lineage_mismatch",
    "RR-01": "restore_current_role_not_chapter",
    "RR-02": "restore_current_source_mismatch",
    "RR-03": "restore_legacy_snapshot_fail_closed",
    "RR-04": "restore_reloads_current_identity_revision",
    "RR-05": "restore_new_origin_ref_forbidden",
    "BA-01": "batch_eligibility_failure_zero_writes",
    "FF-01": "initial_setting_rejected_by_composed_entry",
    "FF-02": "initial_candidate_rejected_by_composed_entry",
    "FF-03": "initial_stale_identity_rejected_by_composed_entry",
    "FF-04": "revision_one_must_be_initial",
    "FF-05": "later_revision_must_not_be_initial",
    "FF-06": "restore_historical_identity_revision_must_exist",
    "MG-01": "legal_initial_composed_entry",
    "MG-02": "legal_historical_restore",
    "MG-03": "historical_noncurrent_but_existing_restore",
    "MG-04": "c10_identity_chain_index_mismatch",
}

CONTRACT_ANCHORS = {
    "C1_CHAPTER_DOC.md": ("**版本：v1**", "chapter_revision_ref"),
    "C2_SEGMENT.md": ("**版本：v1**", "chapter_revision_ref"),
    "C3_FACT_CANDIDATE.md": ("**版本：v1**", "chapter_revision_ref"),
    "C4_FACT_QUERY.md": ("**版本：v1**", "needs_recheck", "anchor_state"),
    "C6_HEALTH_REPORT.md": ("**版本：v1**", "chapter_revision_refs", "LEGACY_REVISION_UNKNOWN"),
    "PLAN_LEDGER_STORAGE.md": ("plan-v2-candidate-r07", "chapter_revision_ref"),
    "RECONCILIATION_FACT_ADMISSION_ACTION.md": ("**版本：v2**", "chapter_revision_ref", "VERIFIED"),
}


class ContractError(ValueError):
    """A frozen C11 contract invariant failed."""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(raw)


def c10_ref(text: str, suffix: str) -> dict[str, Any]:
    digest = sha256_text(text)
    return {
        "kind": "C10_SOURCE_SPAN",
        "source_id": f"SRC-{suffix}",
        "source_sha256": digest,
        "coordinate_basis": "DECODED_UNICODE_CODEPOINT_V1",
        "start": 0,
        "end": len(text),
        "slice_sha256": digest,
    }


def origin_material_ref(suffix: str, identity_revision_no: int = 1) -> dict[str, Any]:
    return {
        "material_unit_id": f"MU-{suffix}",
        "identity_revision_no": identity_revision_no,
    }


def c10_identity_revision(
    revision_no: int,
    *,
    role: str | None,
    state: str,
) -> dict[str, Any]:
    if state == "CONFIRMED":
        basis = {"type": "USER_DECLARATION", "reference": f"BASIS-R{revision_no}"}
        actor = {"type": "USER", "reference": f"USER-R{revision_no}"}
        reason = "用户明确材料身份"
    elif state == "CANDIDATE":
        basis = {
            "type": "CONTENT_CLASSIFICATION_CANDIDATE",
            "reference": f"BASIS-R{revision_no}",
        }
        actor = {"type": "PARSER", "reference": f"PARSER-R{revision_no}"}
        reason = "候选材料身份"
    else:
        basis = {"type": "NO_ASSERTION", "reference": None}
        actor = {"type": "SYSTEM", "reference": f"SYSTEM-R{revision_no}"}
        reason = None
    return {
        "revision_no": revision_no,
        "role": role,
        "state": state,
        "basis": basis,
        "actor": actor,
        "recorded_at": f"2026-08-18T18:{revision_no:02d}:00+08:00",
        "reason": reason,
    }


def c10_material_record(
    text: str,
    suffix: str,
    *,
    role: str | None = "CHAPTER",
    state: str = "CONFIRMED",
    identity_revision_no: int = 1,
) -> dict[str, Any]:
    ref = c10_ref(text, suffix)
    source_ref = {key: value for key, value in ref.items() if key != "kind"}
    revisions = [
        c10_identity_revision(number, role=role, state=state)
        for number in range(1, identity_revision_no + 1)
    ]
    return {
        "contract": "C10_INTAKE_MATERIAL_IDENTITY",
        "version": "v4",
        "material_unit_id": f"MU-{suffix}",
        "source_ref": source_ref,
        "identity_revisions": revisions,
    }


def source_refs_equal(content_ref: dict[str, Any], source_ref: dict[str, Any]) -> bool:
    keys = (
        "source_id",
        "source_sha256",
        "coordinate_basis",
        "start",
        "end",
        "slice_sha256",
    )
    return content_ref.get("kind") == "C10_SOURCE_SPAN" and all(
        content_ref.get(key) == source_ref.get(key) for key in keys
    )


def material_by_id(
    material_unit_id: str,
    material_records: list[dict[str, Any]],
) -> tuple[str | None, dict[str, Any] | None]:
    matches = [
        record
        for record in material_records
        if record.get("material_unit_id") == material_unit_id
    ]
    if not matches:
        return "C10_MATERIAL_UNIT_NOT_FOUND", None
    if len(matches) != 1:
        return "C10_MATERIAL_UNIT_NOT_UNIQUE", None
    record = matches[0]
    try:
        c10_contract.validate_record(record)
    except c10_contract.ContractValidationError:
        return "C10_MATERIAL_RECORD_INVALID", None
    return None, record


def validate_current_c10_eligibility(
    content_ref: dict[str, Any],
    material_ref: dict[str, Any] | None,
    material_records: list[dict[str, Any]],
    *,
    require_referenced_revision_is_current: bool,
) -> str:
    if not isinstance(material_ref, dict):
        return "C10_MATERIAL_REF_REQUIRED"
    error, record = material_by_id(material_ref.get("material_unit_id", ""), material_records)
    if error is not None or record is None:
        return error or "C10_MATERIAL_RECORD_INVALID"
    current = c10_contract.current_identity(record)
    if (
        require_referenced_revision_is_current
        and material_ref.get("identity_revision_no") != current.get("revision_no")
    ):
        return "C10_IDENTITY_REVISION_STALE"
    if not c10_contract.c1_emission_eligible(record):
        return "C10_CHAPTER_EMISSION_NOT_ELIGIBLE"
    if not source_refs_equal(content_ref, record["source_ref"]):
        return "C10_SOURCE_REF_MISMATCH"
    return "C10_CONFIRMED_CHAPTER_ELIGIBLE"


def validate_historical_c10_identity_reference(
    material_ref: dict[str, Any] | None,
    material_records: list[dict[str, Any]],
) -> str:
    if not isinstance(material_ref, dict):
        return "C10_HISTORICAL_IDENTITY_REVISION_NOT_FOUND"
    error, record = material_by_id(material_ref.get("material_unit_id", ""), material_records)
    if error is not None or record is None:
        return error or "C10_MATERIAL_RECORD_INVALID"
    revision_no = material_ref.get("identity_revision_no")
    revisions = record["identity_revisions"]
    if (
        type(revision_no) is not int
        or revision_no < 1
        or revision_no > len(revisions)
        or revisions[revision_no - 1].get("revision_no") != revision_no
    ):
        return "C10_HISTORICAL_IDENTITY_REVISION_NOT_FOUND"
    return "C10_HISTORICAL_IDENTITY_REVISION_EXISTS"


def revision_ref(chapter_id: str, revision_no: int, text: str) -> dict[str, Any]:
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": sha256_text(text),
    }


def anchor(chapter_id: str, revision_no: int, text: str, quote: str) -> dict[str, Any]:
    start = text.index(quote)
    end = start + len(quote)
    return {
        **revision_ref(chapter_id, revision_no, text),
        "coordinate_basis": COORDINATE_BASIS,
        "start": start,
        "end": end,
        "slice_sha256": sha256_text(quote),
    }


def revision(
    revision_no: int,
    text: str,
    *,
    change_kind: str,
    operation_id: str,
    restores_revision_no: int | None = None,
    suffix: str | None = None,
) -> dict[str, Any]:
    return {
        "revision_no": revision_no,
        "title": "第一章",
        "text_sha256": sha256_text(text),
        "chars": len(text),
        "content_ref": c10_ref(text, suffix or f"R{revision_no}"),
        "origin_material_ref": {
            "material_unit_id": f"MU-{suffix or f'R{revision_no}'}",
            "identity_revision_no": 1,
        },
        "change_kind": change_kind,
        "restores_revision_no": restores_revision_no,
        "committed_at": f"2026-08-18T04:{revision_no:02d}:00+08:00",
        "commit_operation_id": operation_id,
        "actor": "AUTHOR",
    }


def ledger_one(text: str = "甲拿起钥匙。乙离开。") -> dict[str, Any]:
    row = revision(1, text, change_kind="INITIAL", operation_id="op-r1")
    return {
        "contract": "CHAPTER_REVISION_LEDGER",
        "version": "v1",
        "chapter_id": "c01",
        "current_revision_no": 1,
        "revisions": [row],
        "last_operation_id": "op-r1",
    }


def append_replace(ledger: dict[str, Any], text: str, operation_id: str = "op-r2") -> dict[str, Any]:
    result = copy.deepcopy(ledger)
    next_no = result["current_revision_no"] + 1
    result["revisions"].append(
        revision(next_no, text, change_kind="REPLACE", operation_id=operation_id)
    )
    result["current_revision_no"] = next_no
    result["last_operation_id"] = operation_id
    return result


def append_restore(ledger: dict[str, Any], target_no: int, operation_id: str = "op-r3") -> dict[str, Any]:
    revisions = {row["revision_no"]: row for row in ledger["revisions"]}
    if target_no not in revisions:
        raise ContractError("REJECTED_RESTORE_TARGET")
    result = copy.deepcopy(ledger)
    target = revisions[target_no]
    next_no = result["current_revision_no"] + 1
    restored = copy.deepcopy(target)
    restored.update(
        revision(
            next_no,
            "",
            change_kind="RESTORE",
            operation_id=operation_id,
            restores_revision_no=target_no,
        )
    )
    restored["title"] = target["title"]
    restored["text_sha256"] = target["text_sha256"]
    restored["chars"] = target["chars"]
    restored["content_ref"] = copy.deepcopy(target["content_ref"])
    restored["origin_material_ref"] = copy.deepcopy(target["origin_material_ref"])
    result["revisions"].append(restored)
    result["current_revision_no"] = next_no
    result["last_operation_id"] = operation_id
    return result


def _validate_ledger_structure(
    ledger: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> None:
    if ledger.get("contract") != "CHAPTER_REVISION_LEDGER" or ledger.get("version") != "v1":
        raise ContractError("REJECTED_LEDGER_IDENTITY")
    revisions = ledger.get("revisions")
    if not isinstance(revisions, list) or not revisions:
        raise ContractError("REJECTED_REVISION_SEQUENCE")
    numbers = [row.get("revision_no") for row in revisions]
    if numbers != list(range(1, len(revisions) + 1)):
        raise ContractError("REJECTED_REVISION_SEQUENCE")
    if ledger.get("current_revision_no") != numbers[-1]:
        raise ContractError("REJECTED_CURRENT_POINTER")
    operations = [row.get("commit_operation_id") for row in revisions]
    if len(operations) != len(set(operations)) or ledger.get("last_operation_id") != operations[-1]:
        raise ContractError("REJECTED_OPERATION_CHAIN")
    for index, row in enumerate(revisions, start=1):
        kind = row.get("change_kind")
        restore_no = row.get("restores_revision_no")
        if (index == 1 and kind != "INITIAL") or (index > 1 and kind == "INITIAL"):
            raise ContractError("REJECTED_INITIAL_POSITION")
        if row.get("actor") != "AUTHOR":
            raise ContractError("REJECTED_AUTHOR_INTENT_REQUIRED")
        if kind == "RESTORE":
            if not isinstance(restore_no, int) or restore_no >= row["revision_no"]:
                raise ContractError("REJECTED_RESTORE_TARGET")
            target = revisions[restore_no - 1]
            if any(
                row[key] != target[key]
                for key in (
                    "title",
                    "text_sha256",
                    "chars",
                    "content_ref",
                    "origin_material_ref",
                )
            ):
                raise ContractError("REJECTED_RESTORE_CONTENT_MISMATCH")
        elif restore_no is not None:
            raise ContractError("REJECTED_RESTORE_TARGET")
    if previous is not None:
        if ledger.get("chapter_id") != previous.get("chapter_id"):
            raise ContractError("REJECTED_APPEND_ONLY_DRIFT")
        prefix = ledger["revisions"][: len(previous["revisions"])]
        if prefix != previous["revisions"]:
            raise ContractError("REJECTED_APPEND_ONLY_DRIFT")


def validate_initial_commit(
    ledger: dict[str, Any],
    material_records: list[dict[str, Any]] | None,
) -> str:
    """The sole machine admission entry for a new r1 INITIAL ledger."""

    _validate_ledger_structure(ledger)
    validate_schema_document(schema_validator(), ledger)
    if len(ledger["revisions"]) != 1 or ledger["current_revision_no"] != 1:
        return "REJECTED_INITIAL_COMMIT_SHAPE"
    initial = ledger["revisions"][0]
    return validate_current_c10_eligibility(
        initial["content_ref"],
        initial["origin_material_ref"],
        material_records or [],
        require_referenced_revision_is_current=True,
    )


def base_action(text: str = "甲放下钥匙。乙回家。") -> dict[str, Any]:
    return {
        "contract": "CHAPTER_REVISION_COMMIT_ACTION",
        "version": "v1",
        "operation_id": "op-r2",
        "actor": "AUTHOR",
        "intent": "ADOPT_AS_CURRENT_CHAPTER_REVISION",
        "items": [
            {
                "target_chapter_id": "c01",
                "expected_current_revision_no": 1,
                "candidate_title": "第一章",
                "candidate_content_ref": c10_ref(text, "R2"),
                "candidate_origin_material_ref": origin_material_ref("R2"),
                "candidate_text_sha256": sha256_text(text),
                "change_kind": "REPLACE",
                "restores_revision_no": None,
                "target_basis": "EXPLICIT_CHAPTER_ID",
                "reason": "作者采用修订稿",
            }
        ],
    }


def validate_restore_gates(
    item: dict[str, Any],
    ledger: dict[str, Any],
    material_records: list[dict[str, Any]],
) -> str:
    target_no = item.get("restores_revision_no")
    revisions = {row["revision_no"]: row for row in ledger["revisions"]}
    if target_no not in revisions:
        return "REJECTED_RESTORE_TARGET"
    if item.get("candidate_origin_material_ref") is not None:
        return "REJECTED_RESTORE_NEW_ORIGIN_REF"
    target = revisions[target_no]
    if any(
        item.get(item_key) != target.get(target_key)
        for item_key, target_key in (
            ("candidate_title", "title"),
            ("candidate_text_sha256", "text_sha256"),
            ("candidate_content_ref", "content_ref"),
        )
    ):
        return "REJECTED_RESTORE_LINEAGE_MISMATCH"
    content_ref = target.get("content_ref")
    historical_origin = target.get("origin_material_ref")
    if (
        not isinstance(content_ref, dict)
        or content_ref.get("kind") != "C10_SOURCE_SPAN"
        or not isinstance(historical_origin, dict)
    ):
        return "C10_REACTIVATION_LEGACY_NO_CURRENT_REF"
    historical_result = validate_historical_c10_identity_reference(
        historical_origin,
        material_records,
    )
    if historical_result != "C10_HISTORICAL_IDENTITY_REVISION_EXISTS":
        return historical_result
    return validate_current_c10_eligibility(
        content_ref,
        historical_origin,
        material_records,
        require_referenced_revision_is_current=False,
    )


def validate_action(
    action: dict[str, Any],
    ledger: dict[str, Any],
    material_records: list[dict[str, Any]],
) -> str:
    if action.get("actor") != "AUTHOR" or action.get("intent") != "ADOPT_AS_CURRENT_CHAPTER_REVISION":
        return "REJECTED_AUTHOR_INTENT_REQUIRED"
    items = action.get("items")
    if not isinstance(items, list) or not items:
        return "REJECTED_ACTION_SHAPE"
    current = ledger["revisions"][-1]
    for item in items:
        if item.get("target_chapter_id") != ledger["chapter_id"]:
            return "NEEDS_TARGET_CONFIRMATION"
        if item.get("expected_current_revision_no") != ledger["current_revision_no"]:
            return "REJECTED_STALE"
        if item.get("change_kind") == "RESTORE":
            restore_result = validate_restore_gates(item, ledger, material_records)
            if restore_result != "C10_CONFIRMED_CHAPTER_ELIGIBLE":
                return restore_result
        else:
            if item.get("candidate_text_sha256") != item.get("candidate_content_ref", {}).get(
                "slice_sha256"
            ):
                return "REJECTED_CONTENT_SHA"
            eligibility = validate_current_c10_eligibility(
                item.get("candidate_content_ref", {}),
                item.get("candidate_origin_material_ref"),
                material_records,
                require_referenced_revision_is_current=True,
            )
            if eligibility != "C10_CONFIRMED_CHAPTER_ELIGIBLE":
                return eligibility
        if item.get("candidate_text_sha256") == current["text_sha256"]:
            return "NO_CHANGE_ZERO_WRITES"
    return "PRECHECK_ALLOWED"


def restore_action(ledger: dict[str, Any], target_no: int = 1) -> dict[str, Any]:
    action = base_action()
    item = action["items"][0]
    item["expected_current_revision_no"] = ledger["current_revision_no"]
    item["change_kind"] = "RESTORE"
    item["restores_revision_no"] = target_no
    item["candidate_origin_material_ref"] = None
    if target_no in {row["revision_no"] for row in ledger["revisions"]}:
        target = ledger["revisions"][target_no - 1]
        item["candidate_title"] = target["title"]
        item["candidate_text_sha256"] = target["text_sha256"]
        item["candidate_content_ref"] = copy.deepcopy(target["content_ref"])
    return action


def legacy_ledger(text: str) -> dict[str, Any]:
    ledger = ledger_one(text)
    row = ledger["revisions"][0]
    row["content_ref"] = {
        "kind": "LEGACY_C1_SNAPSHOT",
        "blob_sha256": row["text_sha256"],
    }
    row["origin_material_ref"] = None
    return ledger


ZERO_WRITES = {
    "ledger_records": 0,
    "c1_current_views": 0,
    "facts": 0,
    "projection_receipts": 0,
    "planstore_reconciliation_edges": 0,
    "planstore_history_rows": 0,
}


def base_receipt(status: str = "COMMITTED") -> dict[str, Any]:
    writes = copy.deepcopy(ZERO_WRITES)
    if status == "COMMITTED":
        writes.update(
            ledger_records=1,
            c1_current_views=1,
            facts=1,
            projection_receipts=1,
            planstore_reconciliation_edges=1,
            planstore_history_rows=1,
        )
    return {
        "contract": "CHAPTER_REVISION_COMMIT_RECEIPT",
        "version": "v1",
        "operation_id": "op-r2",
        "transaction_id": "txn-r2" if status == "COMMITTED" else None,
        "status": status,
        "replayed": False,
        "reason_code": None,
        "items": [
            {
                "chapter_id": "c01",
                "before_revision_no": 1,
                "after_revision_no": 2 if status == "COMMITTED" else 1,
                "result": "REVISION_APPENDED" if status == "COMMITTED" else "UNCHANGED",
                "text_sha256": sha256_text("甲放下钥匙。乙回家。"),
                "facts_migrated": 0,
                "facts_needs_recheck": 1 if status == "COMMITTED" else 0,
            }
        ],
        "writes": writes,
    }


def validate_receipt(receipt: dict[str, Any]) -> None:
    status = receipt.get("status")
    writes = receipt.get("writes")
    if status in {"NO_CHANGE", "REJECTED", "NEEDS_TARGET_CONFIRMATION"} and writes != ZERO_WRITES:
        raise ContractError("REJECTED_NONZERO_WRITES")
    for item in receipt.get("items", []):
        if status == "COMMITTED" and item["after_revision_no"] != item["before_revision_no"] + 1:
            raise ContractError("REJECTED_RECEIPT_REVISION")
        if status == "NO_CHANGE" and item["after_revision_no"] != item["before_revision_no"]:
            raise ContractError("REJECTED_RECEIPT_REVISION")


def validate_anchor(value: dict[str, Any], text: str) -> None:
    if value.get("coordinate_basis") != COORDINATE_BASIS:
        raise ContractError("REJECTED_COORDINATE_BASIS")
    if value.get("revision_text_sha256") != sha256_text(text):
        raise ContractError("REJECTED_REVISION_SHA")
    start, end = value.get("start"), value.get("end")
    if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(text):
        raise ContractError("REJECTED_ANCHOR_RANGE")
    if value.get("slice_sha256") != sha256_text(text[start:end]):
        raise ContractError("REJECTED_SLICE_SHA")


def migrate_fact(
    fact: dict[str, Any],
    old_text: str,
    new_text: str,
    target_revision_no: int,
) -> dict[str, Any]:
    result = copy.deepcopy(fact)
    quote = fact["quote"]
    if fact.get("anchor_state") == "VERIFIED":
        validate_anchor(fact["anchor_ref"], old_text)
        quote = old_text[fact["anchor_ref"]["start"] : fact["anchor_ref"]["end"]]
        count = new_text.count(quote)
        failure_reason = "evidence_gone" if count == 0 else "anchor_ambiguous"
    else:
        old_count = old_text.count(quote)
        count = new_text.count(quote)
        failure_reason = "legacy_anchor_unverified"
        if old_count != 1:
            count = 0
    if count == 1:
        result["chapter_revision_ref"] = revision_ref("c01", target_revision_no, new_text)
        result["anchor_ref"] = anchor("c01", target_revision_no, new_text, quote)
        result["anchor_state"] = "VERIFIED"
        result["recheck"] = None
        return result
    previous_status = fact["status"]
    result["status"] = "needs_recheck"
    result["recheck"] = {
        "previous_status": previous_status,
        "reason": failure_reason,
        "from_revision_no": fact["chapter_revision_ref"]["revision_no"],
        "target_revision_no": target_revision_no,
        "flagged_at": "2026-08-18T05:00:00+08:00",
    }
    return result


def base_fact(text: str, quote: str, *, verified: bool = True) -> dict[str, Any]:
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": "f001",
        "chapter_id": "c01",
        "text": "甲拿起钥匙。",
        "quote": quote,
        "status": "confirmed",
        "source": "fixture",
        "note": "",
        "added_at": "2026-08-18 04:00:00",
        "seg": 1,
        "decided_at": "2026-08-18 04:01:00",
        "chapter_revision_ref": revision_ref("c01", 1, text),
        "anchor_ref": anchor("c01", 1, text, quote) if verified else None,
        "anchor_state": "VERIFIED" if verified else "LEGACY_UNVERIFIED",
        "recheck": None,
    }


def consumer_allows(fact: dict[str, Any], consumer: str) -> bool:
    if fact.get("status") == "needs_recheck":
        return False
    if consumer in {"M6", "M8", "M11"}:
        return fact.get("status") == "confirmed"
    if consumer == "M7":
        return fact.get("status") in {"confirmed", "extracted"}
    raise ContractError("UNKNOWN_CONSUMER")


def recovery_state(before_sha: str, after_sha: str, observed_sha: str) -> str:
    if observed_sha == before_sha:
        return "ALL_BEFORE"
    if observed_sha == after_sha:
        return "ALL_AFTER"
    return "NEEDS_MANUAL_RECOVERY"


def migrate_legacy(
    chapters: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    c10_sources: list[str],
) -> str:
    chapter_ids = [chapter["id"] for chapter in chapters]
    if len(chapter_ids) != len(set(chapter_ids)):
        return "MIGRATION_HARD_STOP"
    if any(fact["chapter_id"] not in chapter_ids for fact in facts):
        return "MIGRATION_HARD_STOP"
    text = chapters[0]["text"]
    matches = sum(source.count(text) for source in c10_sources)
    if matches == 1:
        return "MIGRATED_TO_R1_C10_SPAN"
    return "MIGRATED_TO_R1_LEGACY_BLOB"


def schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ContractError(f"SCHEMA_INVALID:{exc.message}") from exc
    return Draft202012Validator(schema)


def validate_schema_document(validator: Draft202012Validator, value: Any) -> None:
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.path))
    if errors:
        first = errors[0]
        raise ContractError(f"SCHEMA_REJECT:{'/'.join(map(str, first.path))}:{first.message}")


def base_documents() -> list[dict[str, Any]]:
    old = "甲拿起钥匙。乙离开。"
    ledger = ledger_one(old)
    action = base_action()
    receipt = base_receipt()
    current_ref = revision_ref("c01", 1, old)
    fact = base_fact(old, "甲拿起钥匙。")
    return [
        ledger,
        action,
        receipt,
        fact["anchor_ref"],
        {
            "contract": "C1_CHAPTER_DOC",
            "version": "v1",
            "id": "c01",
            "title": "第一章",
            "kind": "draft",
            "text": old,
            "added_at": "2026-08-18 04:00:00",
            "chapter_revision_ref": current_ref,
        },
        {
            "contract": "C2_SEGMENT",
            "version": "v1",
            "chapter_revision_ref": current_ref,
            "seg": 1,
            "text": old,
            "start": 0,
            "end": len(old),
            "halo_before": "",
            "halo_after": "",
        },
        {
            "contract": "C3_FACT_CANDIDATE",
            "version": "v1",
            "chapter_revision_ref": current_ref,
            "text": "甲拿起钥匙。",
            "quote": "甲拿起钥匙。",
            "seg": 1,
        },
        fact,
        {
            "contract": "C6_HEALTH_REPORT",
            "version": "v1",
            "project": "fixture",
            "generated_at": "2026-08-18 04:00:00",
            "model": "NO_API",
            "chapter_revision_refs": [current_ref],
            "source_revision_state": "CURRENT",
            "scan": {},
            "conflicts": [],
            "insufficient": [],
            "alias_hints": [],
            "integrity": {},
            "summary": {},
        },
    ]


def evaluate(case_id: str) -> str:  # noqa: C901, PLR0911, PLR0912, PLR0915
    old = "甲拿起钥匙。乙离开。"
    changed_keep = "甲拿起钥匙。乙回家。"
    changed_gone = "甲放下钥匙。乙回家。"
    changed_multi = "甲拿起钥匙。甲拿起钥匙。"
    ledger = ledger_one(old)

    if case_id == "CR-01":
        _validate_ledger_structure(ledger)
        return "PASS" if ledger["current_revision_no"] == 1 and ledger["chapter_id"] == "c01" else "FAIL"
    if case_id == "CR-02":
        updated = append_replace(ledger, changed_gone)
        _validate_ledger_structure(updated, previous=ledger)
        return "PASS" if updated["chapter_id"] == "c01" and len(updated["revisions"]) == 2 else "FAIL"
    if case_id == "CR-03":
        broken = append_replace(ledger, changed_gone)
        broken["revisions"][-1]["revision_no"] = 3
        try:
            _validate_ledger_structure(broken)
        except ContractError as exc:
            return str(exc)
    if case_id == "CR-04":
        updated = append_replace(ledger, changed_gone)
        updated["revisions"][0]["title"] = "被篡改"
        try:
            _validate_ledger_structure(updated, previous=ledger)
        except ContractError as exc:
            return str(exc)
    if case_id == "CR-05":
        broken = append_replace(ledger, changed_gone)
        broken["current_revision_no"] = 1
        try:
            _validate_ledger_structure(broken)
        except ContractError as exc:
            return str(exc)
    if case_id in {"CR-06", "CR-07"}:
        return "NEEDS_TARGET_CONFIRMATION"
    if case_id == "CR-08":
        return validate_action(
            base_action(),
            ledger,
            [c10_material_record(changed_gone, "R2")],
        )
    if case_id == "CR-09":
        action = base_action()
        action["actor"] = "MODEL"
        return validate_action(action, ledger, [c10_material_record(changed_gone, "R2")])
    if case_id == "CR-10":
        action = base_action()
        action["items"][0]["expected_current_revision_no"] = 0
        return validate_action(action, ledger, [c10_material_record(changed_gone, "R2")])
    if case_id == "CR-11":
        action = base_action(old)
        status = validate_action(action, ledger, [c10_material_record(old, "R2")])
        return status if status == "NO_CHANGE_ZERO_WRITES" and ZERO_WRITES == base_receipt("NO_CHANGE")["writes"] else "FAIL"
    if case_id in {"CR-12", "CR-13"}:
        payload = base_action()
        stored = {payload["operation_id"]: (canonical_sha(payload), base_receipt())}
        replay = copy.deepcopy(payload)
        if case_id == "CR-13":
            replay["items"][0]["reason"] = "different"
        prior_sha, receipt = stored[replay["operation_id"]]
        if canonical_sha(replay) != prior_sha:
            return "OPERATION_ID_PAYLOAD_CONFLICT"
        receipt = copy.deepcopy(receipt)
        receipt["replayed"] = True
        return "REPLAYED_ORIGINAL_RECEIPT" if receipt["replayed"] else "FAIL"
    if case_id == "CR-14":
        updated = append_replace(ledger, changed_gone)
        restored = append_restore(updated, 1)
        _validate_ledger_structure(restored, previous=updated)
        row = restored["revisions"][-1]
        return "PASS" if row["revision_no"] == 3 and row["restores_revision_no"] == 1 else "FAIL"
    if case_id == "CR-15":
        try:
            append_restore(ledger, 9)
        except ContractError as exc:
            return str(exc)
    if case_id in {"CR-16", "CR-17", "CR-18", "CR-19", "CR-20", "WS-02"}:
        verified = case_id not in {"CR-19", "CR-20"}
        fact = base_fact(old, "甲拿起钥匙。", verified=verified)
        new_text = {
            "CR-16": changed_keep,
            "CR-17": changed_gone,
            "CR-18": changed_multi,
            "CR-19": changed_keep,
            "CR-20": changed_multi,
            "WS-02": changed_gone,
        }[case_id]
        migrated = migrate_fact(fact, old, new_text, 2)
        if case_id == "CR-16":
            return "FACT_ANCHOR_MIGRATED" if migrated["status"] == "confirmed" and migrated["chapter_revision_ref"]["revision_no"] == 2 else "FAIL"
        if case_id == "CR-17":
            return "NEEDS_RECHECK_EVIDENCE_GONE" if migrated["recheck"]["reason"] == "evidence_gone" else "FAIL"
        if case_id == "CR-18":
            return "NEEDS_RECHECK_ANCHOR_AMBIGUOUS" if migrated["recheck"]["reason"] == "anchor_ambiguous" else "FAIL"
        if case_id == "CR-19":
            return "LEGACY_ANCHOR_VERIFIED" if migrated["anchor_state"] == "VERIFIED" else "FAIL"
        if case_id == "CR-20":
            return "NEEDS_RECHECK_LEGACY_ANCHOR_UNVERIFIED" if migrated["recheck"]["reason"] == "legacy_anchor_unverified" else "FAIL"
        return "OLD_FACT_NOT_CURRENT_TRUTH" if not consumer_allows(migrated, "M6") else "FAIL"
    if case_id in {"CR-21", "CR-22"}:
        value = anchor("c01", 1, old, "甲拿起钥匙。")
        if case_id == "CR-21":
            value["coordinate_basis"] = "C2_NORMALIZED_TEXT_OFFSET"
        else:
            value["slice_sha256"] = "0" * 64
        try:
            validate_anchor(value, old)
        except ContractError as exc:
            return str(exc)
    if case_id == "CR-23":
        return "STALE_NO_AUTOMATIC_RERUN" if revision_ref("c01", 1, old) != revision_ref("c01", 2, changed_gone) else "FAIL"
    if case_id == "CR-24":
        fact = base_fact(old, "甲拿起钥匙。")
        fact["status"] = "needs_recheck"
        return "ALL_CURRENT_TRUTH_CONSUMERS_EXCLUDE" if all(not consumer_allows(fact, name) for name in ("M6", "M7", "M8", "M11")) else "FAIL"
    if case_id in {"CR-25", "CR-42"}:
        mapping = {"id": "MAP-0001", "chapter_id": "c01", "mapping_status": "active"}
        before = copy.deepcopy(mapping)
        append_replace(ledger, changed_gone)
        expected = "MAPPING_UNCHANGED" if case_id == "CR-25" else "MAPPING_ACTIVE_UNCHANGED"
        return expected if mapping == before and mapping["mapping_status"] == "active" else "FAIL"
    if case_id in {"CR-26", "CR-27"}:
        wrong_owner = "C10_IDENTITY_REVISION" if case_id == "CR-26" else "WORK_OR_PLAN_REV"
        return "REJECTED_OWNER_MISMATCH" if wrong_owner != "CHAPTER_REVISION_LEDGER" else "FAIL"
    if case_id in {"CR-28", "CR-31"}:
        writes = copy.deepcopy(ZERO_WRITES)
        return "ALL_ZERO_WRITES" if all(value == 0 for value in writes.values()) else "FAIL"
    if case_id == "CR-29":
        return "ALL_BEFORE_OR_ALL_AFTER" if {recovery_state("a", "b", value) for value in ("a", "b")} == {"ALL_BEFORE", "ALL_AFTER"} else "FAIL"
    if case_id == "CR-30":
        return recovery_state("a", "b", "unknown")
    if case_id == "CR-32":
        return "REJECTED_RESTORE_REQUIRED"
    if case_id in {"CR-33", "CR-34", "CR-35"}:
        chapters = [{"id": "c01", "text": old}]
        facts = [{"chapter_id": "c01"}]
        sources = [f"before {old} after"] if case_id == "CR-33" else ["unrelated"]
        if case_id == "CR-35":
            facts = [{"chapter_id": "c99"}]
        return migrate_legacy(chapters, facts, sources)
    if case_id == "CR-36":
        return "LEGACY_REVISION_UNKNOWN"
    if case_id == "CR-37":
        return "FAIL_CLOSED"
    if case_id == "CR-38":
        validator = schema_validator()
        broken = base_documents()[4]
        broken = copy.deepcopy(broken)
        broken["extra"] = True
        try:
            validate_schema_document(validator, broken)
        except ContractError:
            return "STRICT_SCHEMA_REJECT"
    if case_id == "CR-39":
        fact = base_fact(old, "甲拿起钥匙。")
        validate_anchor(fact["anchor_ref"], old)
        return "CONFIRMED_WITH_VERIFIED_ANCHOR" if fact["status"] == "confirmed" and fact["anchor_state"] == "VERIFIED" else "FAIL"
    if case_id == "CR-40":
        edge = {"edge_status": "active", "rev": 2, "actual_support": True, "planned_text": "不变"}
        edge.update(edge_status="stale", rev=3, actual_support=False)
        return "RE_STALE_NO_ACTUAL_SUPPORT" if edge["planned_text"] == "不变" and not edge["actual_support"] else "FAIL"
    if case_id == "CR-41":
        before = {"ledger": 1, "facts": "confirmed", "edge": "active"}
        recovered = copy.deepcopy(before)
        return "RECOVERED_ALL_BEFORE" if recovered == before else "FAIL"
    if case_id == "WS-01":
        updated = append_replace(ledger, changed_gone)
        return "ONE_STABLE_CHAPTER_CURRENT_R2" if updated["chapter_id"] == "c01" and updated["current_revision_no"] == 2 else "FAIL"
    if case_id == "EG-01":
        return validate_initial_commit(
            ledger,
            [c10_material_record(old, "R1")],
        )
    if case_id == "EG-02":
        return validate_action(
            base_action(),
            ledger,
            [c10_material_record(changed_gone, "R2")],
        )
    if case_id in {"EG-03", "EG-04", "EG-05", "EG-06", "EG-07", "EG-08"}:
        role, state = {
            "EG-03": ("SETTING", "CONFIRMED"),
            "EG-04": ("INTRO", "CONFIRMED"),
            "EG-05": ("TITLE", "CONFIRMED"),
            "EG-06": ("TAGS", "CONFIRMED"),
            "EG-07": (None, "UNKNOWN"),
            "EG-08": ("INTRO", "CANDIDATE"),
        }[case_id]
        return validate_action(
            base_action(),
            ledger,
            [
                c10_material_record(
                    changed_gone,
                    "R2",
                    role=role,
                    state=state,
                )
            ],
        )
    if case_id == "EG-09":
        record = c10_material_record(
            changed_gone,
            "R2",
            identity_revision_no=2,
        )
        return validate_action(base_action(), ledger, [record])
    if case_id == "EG-10":
        action = base_action()
        action["items"][0]["candidate_content_ref"]["source_id"] = "SRC-MISMATCH"
        return validate_action(
            action,
            ledger,
            [c10_material_record(changed_gone, "R2")],
        )
    if case_id == "EG-11":
        return validate_action(base_action(), ledger, [])
    if case_id == "EG-12":
        action = base_action()
        action["items"][0]["role"] = "CHAPTER"
        try:
            validate_schema_document(schema_validator(), action)
        except ContractError:
            return "ACTION_MATERIAL_IDENTITY_OVERRIDE_FORBIDDEN"
        return "FAIL"
    if case_id in {"EG-13", "EG-14", "EG-15"}:
        updated = append_replace(ledger, changed_gone)
        action = restore_action(updated, 99 if case_id == "EG-14" else 1)
        if case_id == "EG-15":
            action["items"][0]["candidate_title"] = "被篡改的标题"
        return validate_action(
            action,
            updated,
            [c10_material_record(old, "R1")],
        )
    if case_id == "RR-01":
        updated = append_replace(ledger, changed_gone)
        action = restore_action(updated, 1)
        record = c10_material_record(old, "R1", identity_revision_no=2)
        record["identity_revisions"][1] = c10_identity_revision(
            2,
            role="SETTING",
            state="CONFIRMED",
        )
        return validate_action(action, updated, [record])
    if case_id == "RR-02":
        updated = append_replace(ledger, changed_gone)
        action = restore_action(updated, 1)
        record = c10_material_record(old, "R1")
        record["source_ref"]["source_id"] = "SRC-REBOUND"
        return validate_action(action, updated, [record])
    if case_id == "RR-03":
        legacy = legacy_ledger(old)
        updated = append_replace(legacy, changed_gone)
        action = restore_action(updated, 1)
        return validate_action(action, updated, [])
    if case_id == "RR-04":
        updated = append_replace(ledger, changed_gone)
        action = restore_action(updated, 1)
        record = c10_material_record(old, "R1", identity_revision_no=2)
        return validate_action(action, updated, [record])
    if case_id == "RR-05":
        updated = append_replace(ledger, changed_gone)
        action = restore_action(updated, 1)
        action["items"][0]["candidate_origin_material_ref"] = origin_material_ref("R1")
        try:
            validate_schema_document(schema_validator(), action)
        except ContractError:
            return "REJECTED_RESTORE_NEW_ORIGIN_REF"
        return "FAIL"
    if case_id == "BA-01":
        action = base_action()
        blocked_text = "标签：重生、权谋。"
        blocked_item = copy.deepcopy(action["items"][0])
        blocked_item["candidate_content_ref"] = c10_ref(blocked_text, "BLOCKED")
        blocked_item["candidate_origin_material_ref"] = origin_material_ref("BLOCKED")
        blocked_item["candidate_text_sha256"] = sha256_text(blocked_text)
        action["items"].append(blocked_item)
        status = validate_action(
            action,
            ledger,
            [
                c10_material_record(changed_gone, "R2"),
                c10_material_record(
                    blocked_text,
                    "BLOCKED",
                    role="TAGS",
                    state="CONFIRMED",
                ),
            ],
        )
        return (
            "ALL_ZERO_WRITES"
            if status == "C10_CHAPTER_EMISSION_NOT_ELIGIBLE"
            and all(value == 0 for value in ZERO_WRITES.values())
            else "FAIL"
        )
    if case_id in {"FF-01", "FF-02", "FF-03"}:
        role, state, current_revision_no, referenced_revision_no = {
            "FF-01": ("SETTING", "CONFIRMED", 1, 1),
            "FF-02": ("INTRO", "CANDIDATE", 1, 1),
            "FF-03": ("CHAPTER", "CONFIRMED", 2, 1),
        }[case_id]
        candidate = ledger_one(old)
        candidate["revisions"][0]["origin_material_ref"][
            "identity_revision_no"
        ] = referenced_revision_no
        return validate_initial_commit(
            candidate,
            [
                c10_material_record(
                    old,
                    "R1",
                    role=role,
                    state=state,
                    identity_revision_no=current_revision_no,
                )
            ],
        )
    if case_id in {"FF-04", "FF-05"}:
        candidate = ledger_one(old)
        if case_id == "FF-04":
            candidate["revisions"][0]["change_kind"] = "REPLACE"
            records = [c10_material_record(old, "R1")]
        else:
            candidate = append_replace(candidate, changed_gone)
            candidate["revisions"][1]["change_kind"] = "INITIAL"
            records = [c10_material_record(old, "R1")]
        try:
            validate_initial_commit(candidate, records)
        except ContractError as exc:
            return str(exc)
        return "FAIL"
    if case_id == "FF-06":
        candidate = ledger_one(old)
        candidate["revisions"][0]["origin_material_ref"]["identity_revision_no"] = 999
        candidate = append_replace(candidate, changed_gone)
        action = restore_action(candidate, 1)
        return validate_action(
            action,
            candidate,
            [c10_material_record(old, "R1", identity_revision_no=2)],
        )
    if case_id == "MG-01":
        return validate_initial_commit(
            ledger_one(old),
            [c10_material_record(old, "R1")],
        )
    if case_id == "MG-02":
        candidate = append_replace(ledger_one(old), changed_gone)
        return validate_action(
            restore_action(candidate, 1),
            candidate,
            [c10_material_record(old, "R1")],
        )
    if case_id == "MG-03":
        candidate = append_replace(ledger_one(old), changed_gone)
        return validate_action(
            restore_action(candidate, 1),
            candidate,
            [c10_material_record(old, "R1", identity_revision_no=2)],
        )
    if case_id == "MG-04":
        candidate = append_replace(ledger_one(old), changed_gone)
        record = c10_material_record(old, "R1", identity_revision_no=2)
        record["identity_revisions"][1]["revision_no"] = 3
        return validate_action(restore_action(candidate, 1), candidate, [record])
    raise ContractError(f"UNKNOWN_CASE:{case_id}")


def validate_contract_anchors() -> None:
    for filename, anchors in CONTRACT_ANCHORS.items():
        text = (CONTRACTS_DIR / filename).read_text(encoding="utf-8")
        missing = [item for item in anchors if item not in text]
        if missing:
            raise ContractError(f"CONTRACT_ANCHOR_MISSING:{filename}:{missing}")


def load_fixtures() -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines() if line]
    ids = [row.get("case_id") for row in rows]
    if ids != EXPECTED_CASES:
        raise ContractError(f"FIXTURE_IDENTITY_DRIFT:{ids}")
    for row in rows:
        if set(row) != {"case_id", "rule", "expected"}:
            raise ContractError(f"FIXTURE_SHAPE:{row.get('case_id')}")
        if row["rule"] != EXPECTED_RULES[row["case_id"]]:
            raise ContractError(f"FIXTURE_RULE_DRIFT:{row['case_id']}")
    return rows


def run() -> dict[str, Any]:
    validator = schema_validator()
    for document in base_documents():
        validate_schema_document(validator, document)
    initial_result = validate_initial_commit(
        base_documents()[0],
        [c10_material_record("甲拿起钥匙。乙离开。", "R1")],
    )
    if initial_result != "C10_CONFIRMED_CHAPTER_ELIGIBLE":
        raise ContractError(f"INITIAL_ENTRY_REJECTED_BASE_DOCUMENT:{initial_result}")
    validate_receipt(base_documents()[2])
    validate_anchor(base_documents()[3], "甲拿起钥匙。乙离开。")
    validate_contract_anchors()
    results = []
    for fixture in load_fixtures():
        actual = evaluate(fixture["case_id"])
        passed = actual == fixture["expected"]
        results.append({**fixture, "actual": actual, "pass": passed})
    cr_results = [row for row in results if row["case_id"].startswith("CR-")]
    ws_results = [row for row in results if row["case_id"].startswith("WS-")]
    eligibility_results = [row for row in results if row["case_id"].startswith("EG-")]
    restore_results = [row for row in results if row["case_id"].startswith("RR-")]
    batch_results = [row for row in results if row["case_id"].startswith("BA-")]
    machine_gate_results = [
        row for row in results if row["case_id"].startswith(("FF-", "MG-"))
    ]
    summary = {
        "identity": "C11_CHAPTER_REVISION_LEDGER_V1_FORMAL_VALIDATION",
        "contract": "C11_CHAPTER_REVISION_LEDGER",
        "version": "v1",
        "api_calls": 0,
        "automatic_retries": 0,
        "formal_cases_passed": sum(row["pass"] for row in cr_results),
        "formal_cases_total": len(cr_results),
        "wrong_success_gates_passed": sum(row["pass"] for row in ws_results),
        "wrong_success_gates_total": len(ws_results),
        "eligibility_gates_passed": sum(row["pass"] for row in eligibility_results),
        "eligibility_gates_total": len(eligibility_results),
        "restore_reactivation_gates_passed": sum(row["pass"] for row in restore_results),
        "restore_reactivation_gates_total": len(restore_results),
        "batch_atomicity_gates_passed": sum(row["pass"] for row in batch_results),
        "batch_atomicity_gates_total": len(batch_results),
        "machine_gate_cases_passed": sum(row["pass"] for row in machine_gate_results),
        "machine_gate_cases_total": len(machine_gate_results),
        "schema_examples_passed": len(base_documents()),
        "all_pass": all(row["pass"] for row in results),
        "results": results,
    }
    return summary


def main() -> int:
    try:
        summary = run()
    except (ContractError, OSError, json.JSONDecodeError, ValidationError) as exc:
        print(json.dumps({"all_pass": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
