#!/usr/bin/env python3
"""Fail-first independent review of C11 action Schema/entry composition."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any


os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

REPO = Path("/Users/a1234/挣钱/小说架构")
ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
CONTRACTS = REPO / "novel-mvp/contracts"

INPUTS = [
    CONTRACTS / "CHAPTER_REVISION_COMMIT_ACTION.md",
    CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.schema.json",
    CONTRACTS / "validate_c11_chapter_revision_ledger.py",
    CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl",
    CONTRACTS / "validate_c10_intake_material_identity.py",
    REPO
    / "TEMP/a_c11_initial_restore_machine_gate_formal_fix_20260819_r01/VALIDATION_RESULTS.json",
    REPO
    / "TEMP/a_c11_initial_restore_machine_gate_formal_fix_20260819_r01/FORMAL_SHA_RECEIPT.json",
    REPO
    / "TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/results/narrow_replay_ledger.json",
]

EXPECTED_START_SHA256 = {
    str(CONTRACTS / "CHAPTER_REVISION_COMMIT_ACTION.md"): "48dfd296c0cb70873e0f1abb5c08a731ad494cde287a23d1d1e63f7d1a80a651",
    str(CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.schema.json"): "708e19c5ba8e748fd9f50f18e65ad243f06eebcbd30bce7cda804764ad64ef63",
    str(CONTRACTS / "validate_c11_chapter_revision_ledger.py"): "54861c0ead77cbcc474c7115b1e07d711250368f84fb83cbc90238c230de2411",
    str(CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl"): "5f258aed2a9d739eaf69ef2ff4fce3801446487dd562d9d8e9f0371ad3fd3e00",
    str(CONTRACTS / "validate_c10_intake_material_identity.py"): "aeac1c24226019ec4a763bc64c55d2156af60aaa18679151029bafffcc8024ab",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_validator():
    path = CONTRACTS / "validate_c11_chapter_revision_ledger.py"
    sys.path.insert(0, str(CONTRACTS))
    spec = importlib.util.spec_from_file_location("c11_entry_independent_review", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("C11_VALIDATOR_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def schema_result(c11, value: dict[str, Any]) -> dict[str, Any]:
    try:
        c11.validate_schema_document(c11.schema_validator(), value)
    except c11.ContractError as exc:
        message = str(exc)
        return {
            "accepted": False,
            "error_code": message.split(":", 1)[0],
            "error": message,
        }
    return {"accepted": True, "error_code": None, "error": None}


def run_entry(c11, action, ledger, records) -> dict[str, Any]:
    try:
        value = c11.validate_action(action, ledger, records)
    except Exception as exc:  # preserve the public entry's exact failure identity
        return {
            "returned": False,
            "return_value": None,
            "exception_type": type(exc).__name__,
            "exception": str(exc),
        }
    return {
        "returned": True,
        "return_value": value,
        "exception_type": None,
        "exception": None,
    }


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    missing = [str(path) for path in INPUTS if not path.is_file()]
    if missing:
        write_json(
            RESULTS / "gate_ledger.json",
            {
                "task_id": "D-C11-ACTION-ENTRY-SCHEMA-COMPOSITION-INDEPENDENT-REVIEW-01",
                "verdict": "IDENTITY_OR_SCOPE_STOP",
                "reason": "INPUT_MISSING",
                "missing": missing,
            },
        )
        return 2

    before = {str(path): sha256_file(path) for path in INPUTS}
    identity_mismatch = {
        path: {"expected": expected, "actual": before.get(path)}
        for path, expected in EXPECTED_START_SHA256.items()
        if before.get(path) != expected
    }
    if identity_mismatch:
        write_json(
            RESULTS / "gate_ledger.json",
            {
                "task_id": "D-C11-ACTION-ENTRY-SCHEMA-COMPOSITION-INDEPENDENT-REVIEW-01",
                "verdict": "IDENTITY_OR_SCOPE_STOP",
                "reason": "START_SHA_MISMATCH",
                "identity_mismatch": identity_mismatch,
            },
        )
        return 2

    c11 = load_validator()
    ledger = c11.ledger_one()
    replacement_text = "甲放下钥匙。乙回家。"
    records = [c11.c10_material_record(replacement_text, "R2")]
    legal = c11.base_action(replacement_text)

    cases: list[dict[str, Any]] = []

    legal_schema = schema_result(c11, legal)
    legal_entry = run_entry(c11, legal, ledger, records)
    cases.append(
        {
            "case_id": "ENTRY-01-LEGAL-REPLACE",
            "group": 1,
            "mutation": "NONE",
            "executed": True,
            "schema": legal_schema,
            "validate_action": legal_entry,
            "expected": {
                "schema_accepted": True,
                "validate_action_return": "PRECHECK_ALLOWED",
            },
            "verdict": "PASS"
            if legal_schema["accepted"]
            and legal_entry["return_value"] == "PRECHECK_ALLOWED"
            else "FAIL_LEGAL_ENTRY",
        }
    )

    initial = copy.deepcopy(legal)
    initial["items"][0]["change_kind"] = "INITIAL"
    initial_schema = schema_result(c11, initial)
    initial_entry = run_entry(c11, initial, ledger, records)
    gap_found = (
        not initial_schema["accepted"]
        and initial_entry["return_value"] == "PRECHECK_ALLOWED"
    )
    cases.append(
        {
            "case_id": "ENTRY-02-INVALID-INITIAL",
            "group": 2,
            "mutation": "items[0].change_kind=INITIAL",
            "executed": True,
            "schema": initial_schema,
            "validate_action": initial_entry,
            "expected": {
                "schema_accepted": False,
                "validate_action_must_reject": True,
            },
            "verdict": "CONTRACT_MACHINE_ENTRY_GAP_FOUND"
            if gap_found
            else "PASS_CONSISTENT_REJECTION",
        }
    )

    remaining = [
        ("ENTRY-03-INVALID-BOGUS", 3, "items[0].change_kind=BOGUS"),
        ("ENTRY-04A-MISSING-CONTRACT", 4, "top-level contract removed"),
        ("ENTRY-04B-MISSING-VERSION", 4, "top-level version removed"),
    ]
    if gap_found:
        for case_id, group, mutation in remaining:
            cases.append(
                {
                    "case_id": case_id,
                    "group": group,
                    "mutation": mutation,
                    "executed": False,
                    "schema": None,
                    "validate_action": None,
                    "expected": {
                        "schema_accepted": False,
                        "validate_action_must_reject": True,
                    },
                    "verdict": "NOT_RUN_AFTER_FAIL_FIRST_STOP",
                }
            )
        verdict = "CONTRACT_MACHINE_ENTRY_GAP_FOUND"
    else:
        candidates = []
        bogus = copy.deepcopy(legal)
        bogus["items"][0]["change_kind"] = "BOGUS"
        candidates.append((remaining[0], bogus))
        missing_contract = copy.deepcopy(legal)
        del missing_contract["contract"]
        candidates.append((remaining[1], missing_contract))
        missing_version = copy.deepcopy(legal)
        del missing_version["version"]
        candidates.append((remaining[2], missing_version))
        later_gap = False
        for (case_id, group, mutation), action in candidates:
            check = schema_result(c11, action)
            entry = run_entry(c11, action, ledger, records)
            entry_gap = not check["accepted"] and entry["return_value"] == "PRECHECK_ALLOWED"
            later_gap = later_gap or entry_gap
            cases.append(
                {
                    "case_id": case_id,
                    "group": group,
                    "mutation": mutation,
                    "executed": True,
                    "schema": check,
                    "validate_action": entry,
                    "expected": {
                        "schema_accepted": False,
                        "validate_action_must_reject": True,
                    },
                    "verdict": "CONTRACT_MACHINE_ENTRY_GAP_FOUND"
                    if entry_gap
                    else "PASS_CONSISTENT_REJECTION",
                }
            )
            if entry_gap:
                break
        verdict = (
            "CONTRACT_MACHINE_ENTRY_GAP_FOUND"
            if later_gap
            else "PASS_INDEPENDENT_ENTRY_REVIEW"
        )

    after = {str(path): sha256_file(path) for path in INPUTS}
    changed = sorted(path for path in before if before[path] != after[path])
    if changed:
        verdict = "IDENTITY_OR_SCOPE_STOP"
    cache_hits = sorted(
        str(path)
        for path in ROOT.rglob("*")
        if path.name in {"__pycache__", ".pytest_cache"} or path.suffix == ".pyc"
    )

    manifest = {
        "identity": "D_C11_ACTION_ENTRY_INPUT_MANIFEST_R01",
        "material_status": "STABLE" if not changed else "MATERIAL_CHANGED",
        "inputs": [
            {
                "path": path,
                "before_sha256": before[path],
                "after_sha256": after[path],
                "stable": before[path] == after[path],
            }
            for path in sorted(before)
        ],
        "changed_during_review": changed,
    }
    ledger_result = {
        "identity": "D_C11_ACTION_ENTRY_SCHEMA_COMPOSITION_LEDGER_R01",
        "task_id": "D-C11-ACTION-ENTRY-SCHEMA-COMPOSITION-INDEPENDENT-REVIEW-01",
        "status": "COMPLETE" if verdict != "IDENTITY_OR_SCOPE_STOP" else "STOPPED",
        "verdict": verdict,
        "cases": cases,
        "statistics": {
            "groups_planned": 4,
            "subcases_planned": 5,
            "subcases_executed": sum(case["executed"] for case in cases),
            "subcases_not_run_after_fail_first": sum(
                case["verdict"] == "NOT_RUN_AFTER_FAIL_FIRST_STOP" for case in cases
            ),
            "schema_invalid_entry_precheck_allowed": sum(
                case["executed"]
                and case["schema"] is not None
                and not case["schema"]["accepted"]
                and case["validate_action"]["return_value"] == "PRECHECK_ALLOWED"
                for case in cases
            ),
            "input_drift": len(changed),
            "cache_hits": len(cache_hits),
            "api_calls": 0,
            "model_calls": 0,
            "automatic_retries": 0,
            "formal_writes": 0,
        },
        "minimal_impact": [
            "The formal action Schema rejects INITIAL in items[].change_kind.",
            "The public validate_action entry returns PRECHECK_ALLOWED for that same action.",
            "validate_action does not compose validate_schema_document before semantic branching.",
            "Its current branch treats every non-RESTORE change_kind as the REPLACE path.",
        ]
        if gap_found
        else [],
        "candidate_difference_not_applied": [
            "Validate the complete action with the formal action Schema at the public entry boundary.",
            "Return a stable rejection for Schema-invalid actions before any semantic eligibility check.",
            "After Schema acceptance, branch only on exact REPLACE or RESTORE values.",
        ]
        if gap_found
        else [],
        "formal_fix_applied": False,
        "scope_expanded_to_callers": False,
    }
    no_touch = {
        "identity": "D_C11_ACTION_ENTRY_NO_TOUCH_R01",
        "designated_inputs_unchanged": not changed,
        "changed_inputs": changed,
        "cache_hits": cache_hits,
        "unauthorized_write_path": 0,
        "formal_writes": 0,
        "product_writes": 0,
        "r13_writes": 0,
        "gold_reads_or_writes": 0,
        "novel_reads": 0,
        "notion_operations": 0,
        "git_operations": 0,
        "api_calls": 0,
        "model_calls": 0,
        "automatic_retries": 0,
    }
    write_json(RESULTS / "input_manifest.json", manifest)
    write_json(RESULTS / "gate_ledger.json", ledger_result)
    write_json(RESULTS / "no_touch_receipt.json", no_touch)
    print(
        f"{ledger_result['task_id']}: verdict={verdict} "
        f"executed={ledger_result['statistics']['subcases_executed']}/5 "
        f"fail_first_not_run={ledger_result['statistics']['subcases_not_run_after_fail_first']} "
        f"entry_gaps={ledger_result['statistics']['schema_invalid_entry_precheck_allowed']} "
        f"input_drift={len(changed)} cache={len(cache_hits)} "
        "API=0 models=0 retries=0 formal_writes=0"
    )
    return 0 if verdict != "IDENTITY_OR_SCOPE_STOP" else 2


if __name__ == "__main__":
    raise SystemExit(main())
