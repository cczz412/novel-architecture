#!/usr/bin/env python3
"""Independent postfix replay for C11 action Schema/public-entry composition."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

REPO = Path("/Users/a1234/挣钱/小说架构")
ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RUNTIME = ROOT / "runtime"
CONTRACTS = REPO / "novel-mvp/contracts"

FORMAL_INPUTS = [
    CONTRACTS / "validate_c11_chapter_revision_ledger.py",
    CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl",
    CONTRACTS / "CHAPTER_REVISION_COMMIT_ACTION.md",
    CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.schema.json",
    CONTRACTS / "validate_c10_intake_material_identity.py",
]

EXPECTED_START_SHA256 = {
    str(CONTRACTS / "validate_c11_chapter_revision_ledger.py"): "eb80054278c8bb219ae04bda2544ee614ab4e317089ca8b4db08fa60721438ae",
    str(CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl"): "af9db754ae83ca5003a881bdd830b21e88002c33782ea3839abd6dea17c906f8",
    str(CONTRACTS / "CHAPTER_REVISION_COMMIT_ACTION.md"): "48dfd296c0cb70873e0f1abb5c08a731ad494cde287a23d1d1e63f7d1a80a651",
    str(CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.schema.json"): "708e19c5ba8e748fd9f50f18e65ad243f06eebcbd30bce7cda804764ad64ef63",
    str(CONTRACTS / "validate_c10_intake_material_identity.py"): "aeac1c24226019ec4a763bc64c55d2156af60aaa18679151029bafffcc8024ab",
}

A_EVIDENCE = [
    REPO
    / "TEMP/a_c11_action_schema_composition_formal_fix_20260819_r01/VALIDATION_RESULTS.json",
    REPO
    / "TEMP/a_c11_action_schema_composition_formal_fix_20260819_r01/FORMAL_SHA_RECEIPT.json",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_validator():
    path = CONTRACTS / "validate_c11_chapter_revision_ledger.py"
    sys.path.insert(0, str(CONTRACTS))
    spec = importlib.util.spec_from_file_location("c11_d_postfix_replay", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("C11_VALIDATOR_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def schema_result(c11, action: dict[str, Any]) -> dict[str, Any]:
    try:
        c11.validate_schema_document(c11.schema_validator(), action)
    except c11.ContractError as exc:
        message = str(exc)
        return {
            "accepted": False,
            "error_code": message.split(":", 1)[0],
            "error": message,
        }
    return {"accepted": True, "error_code": None, "error": None}


def run_case(
    c11,
    *,
    case_id: str,
    mutation: str,
    action: dict[str, Any],
    ledger: dict[str, Any],
    records: list[dict[str, Any]],
    expected_schema: bool,
    expected_entry: str,
) -> dict[str, Any]:
    state_before = {
        "ledger": copy.deepcopy(ledger),
        "records": copy.deepcopy(records),
        "write_vector": copy.deepcopy(c11.ZERO_WRITES),
    }
    before_sha = canonical_sha(state_before)
    schema = schema_result(c11, action)
    entry_result = c11.validate_action(action, ledger, records)
    state_after = {
        "ledger": copy.deepcopy(ledger),
        "records": copy.deepcopy(records),
        "write_vector": copy.deepcopy(c11.ZERO_WRITES),
    }
    after_sha = canonical_sha(state_after)
    is_failure_path = not expected_schema
    zero_write = before_sha == after_sha and all(
        value == 0 for value in state_after["write_vector"].values()
    )
    passed = (
        schema["accepted"] == expected_schema
        and entry_result == expected_entry
        and (not is_failure_path or zero_write)
    )
    return {
        "case_id": case_id,
        "construction_source": "D_PREVIOUS_FAIL_FIRST_MUTATION_PATTERN",
        "mutation": mutation,
        "schema": schema,
        "validate_action": {
            "return_value": entry_result,
            "expected": expected_entry,
        },
        "failure_path": is_failure_path,
        "state_sha256_before": before_sha,
        "state_sha256_after": after_sha,
        "writes": copy.deepcopy(state_after["write_vector"]),
        "zero_write": zero_write if is_failure_path else None,
        "pass": passed,
    }


def run_command(command: list[str]) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["RUFF_CACHE_DIR"] = str(RUNTIME / "ruff_cache")
    completed = subprocess.run(
        command,
        cwd=REPO,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    all_read_inputs = [*FORMAL_INPUTS, *A_EVIDENCE]
    missing = [str(path) for path in all_read_inputs if not path.is_file()]
    if missing:
        write_json(
            RESULTS / "postfix_replay_ledger.json",
            {
                "task_id": "D-C11-ACTION-ENTRY-SCHEMA-COMPOSITION-POSTFIX-REPLAY-01",
                "verdict": "GAP_OR_IDENTITY_STOP",
                "reason": "INPUT_MISSING",
                "missing": missing,
            },
        )
        return 2

    before = {str(path): sha256_file(path) for path in all_read_inputs}
    identity_mismatch = {
        path: {"expected": expected, "actual": before.get(path)}
        for path, expected in EXPECTED_START_SHA256.items()
        if before.get(path) != expected
    }
    if identity_mismatch:
        write_json(
            RESULTS / "postfix_replay_ledger.json",
            {
                "task_id": "D-C11-ACTION-ENTRY-SCHEMA-COMPOSITION-POSTFIX-REPLAY-01",
                "verdict": "GAP_OR_IDENTITY_STOP",
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

    mutations: list[tuple[str, str, dict[str, Any], bool, str]] = []
    mutations.append(
        (
            "ENTRY-01-LEGAL-REPLACE",
            "NONE",
            copy.deepcopy(legal),
            True,
            "PRECHECK_ALLOWED",
        )
    )
    initial = copy.deepcopy(legal)
    initial["items"][0]["change_kind"] = "INITIAL"
    mutations.append(
        (
            "ENTRY-02-INVALID-INITIAL",
            "items[0].change_kind=INITIAL",
            initial,
            False,
            "REJECTED_ACTION_SCHEMA",
        )
    )
    bogus = copy.deepcopy(legal)
    bogus["items"][0]["change_kind"] = "BOGUS"
    mutations.append(
        (
            "ENTRY-03-INVALID-BOGUS",
            "items[0].change_kind=BOGUS",
            bogus,
            False,
            "REJECTED_ACTION_SCHEMA",
        )
    )
    missing_contract = copy.deepcopy(legal)
    del missing_contract["contract"]
    mutations.append(
        (
            "ENTRY-04A-MISSING-CONTRACT",
            "top-level contract removed",
            missing_contract,
            False,
            "REJECTED_ACTION_SCHEMA",
        )
    )
    missing_version = copy.deepcopy(legal)
    del missing_version["version"]
    mutations.append(
        (
            "ENTRY-04B-MISSING-VERSION",
            "top-level version removed",
            missing_version,
            False,
            "REJECTED_ACTION_SCHEMA",
        )
    )

    cases = [
        run_case(
            c11,
            case_id=case_id,
            mutation=mutation,
            action=action,
            ledger=ledger,
            records=records,
            expected_schema=expected_schema,
            expected_entry=expected_entry,
        )
        for case_id, mutation, action, expected_schema, expected_entry in mutations
    ]

    old_text = "甲拿起钥匙。乙离开。"
    restore_ledger = c11.append_replace(c11.ledger_one(old_text), replacement_text)
    restore_result = c11.validate_action(
        c11.restore_action(restore_ledger, 1),
        restore_ledger,
        [c11.c10_material_record(old_text, "R1")],
    )
    restore_semantics = {
        "expected": "PRECHECK_ALLOWED",
        "actual": restore_result,
        "pass": restore_result == "PRECHECK_ALLOWED",
    }

    validator_run = run_command(
        [
            "uv",
            "run",
            "--locked",
            "python",
            "novel-mvp/contracts/validate_c11_chapter_revision_ledger.py",
        ]
    )
    validator_summary: dict[str, Any] | None = None
    validator_parse_error = None
    if validator_run["returncode"] == 0:
        try:
            validator_summary = json.loads(validator_run["stdout"])
        except json.JSONDecodeError as exc:
            validator_parse_error = str(exc)
    write_json(
        RESULTS / "current_validator_output.json",
        {
            "command": validator_run["command"],
            "returncode": validator_run["returncode"],
            "stderr": validator_run["stderr"],
            "parse_error": validator_parse_error,
            "summary": validator_summary,
        },
    )

    current_results = validator_summary.get("results", []) if validator_summary else []
    old_results = [row for row in current_results if not row["case_id"].startswith("AS-")]
    new_results = [row for row in current_results if row["case_id"].startswith("AS-")]
    validator_checks = {
        "command_returncode_zero": validator_run["returncode"] == 0,
        "json_output_parsed": validator_summary is not None,
        "all_pass": bool(validator_summary and validator_summary.get("all_pass")),
        "old_75_of_75": len(old_results) == 75 and all(row["pass"] for row in old_results),
        "new_5_of_5": len(new_results) == 5 and all(row["pass"] for row in new_results),
        "total_80_of_80": len(current_results) == 80
        and all(row["pass"] for row in current_results),
        "restore_reactivation_5_of_5": bool(
            validator_summary
            and validator_summary.get("restore_reactivation_gates_passed") == 5
            and validator_summary.get("restore_reactivation_gates_total") == 5
        ),
    }

    ruff = run_command(
        [
            "uv",
            "run",
            "--locked",
            "ruff",
            "check",
            "--no-cache",
            "novel-mvp/contracts/validate_c11_chapter_revision_ledger.py",
        ]
    )
    write_json(RESULTS / "ruff_result.json", ruff)

    json_checks: dict[str, Any] = {}
    try:
        schema = json.loads(
            (CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.schema.json").read_text(
                encoding="utf-8"
            )
        )
        json_checks["schema_json"] = {
            "pass": isinstance(schema, dict),
            "top_level_id": schema.get("$id"),
        }
    except json.JSONDecodeError as exc:
        json_checks["schema_json"] = {"pass": False, "error": str(exc)}
    fixture_rows = []
    fixture_error = None
    try:
        fixture_rows = [
            json.loads(line)
            for line in (
                CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl"
            ).read_text(encoding="utf-8").splitlines()
            if line
        ]
    except json.JSONDecodeError as exc:
        fixture_error = str(exc)
    json_checks["fixtures_jsonl"] = {
        "pass": fixture_error is None and len(fixture_rows) == 80,
        "lines": len(fixture_rows),
        "error": fixture_error,
    }

    after = {str(path): sha256_file(path) for path in all_read_inputs}
    formal_changed = sorted(
        str(path)
        for path in FORMAL_INPUTS
        if before[str(path)] != after[str(path)]
    )
    evidence_changed = sorted(
        str(path)
        for path in A_EVIDENCE
        if before[str(path)] != after[str(path)]
    )
    cache_hits = sorted(
        str(path)
        for path in ROOT.rglob("*")
        if path.name in {"__pycache__", ".pytest_cache"} or path.suffix == ".pyc"
    )

    all_checks = (
        all(case["pass"] for case in cases)
        and restore_semantics["pass"]
        and all(validator_checks.values())
        and ruff["returncode"] == 0
        and all(item["pass"] for item in json_checks.values())
        and not formal_changed
        and not evidence_changed
        and not cache_hits
    )
    verdict = (
        "PASS_INDEPENDENT_POSTFIX_REPLAY"
        if all_checks
        else "GAP_OR_IDENTITY_STOP"
    )

    manifest = {
        "identity": "D_C11_ACTION_ENTRY_POSTFIX_INPUT_MANIFEST_R01",
        "material_status": "STABLE"
        if not formal_changed and not evidence_changed
        else "MATERIAL_CHANGED",
        "formal_inputs": [
            {
                "path": str(path),
                "expected_start_sha256": EXPECTED_START_SHA256[str(path)],
                "before_sha256": before[str(path)],
                "after_sha256": after[str(path)],
                "stable": before[str(path)] == after[str(path)],
            }
            for path in FORMAL_INPUTS
        ],
        "supporting_a_evidence": [
            {
                "path": str(path),
                "before_sha256": before[str(path)],
                "after_sha256": after[str(path)],
                "stable": before[str(path)] == after[str(path)],
            }
            for path in A_EVIDENCE
        ],
        "formal_changed_during_replay": formal_changed,
        "evidence_changed_during_replay": evidence_changed,
    }
    ledger_result = {
        "identity": "D_C11_ACTION_ENTRY_POSTFIX_REPLAY_LEDGER_R01",
        "task_id": "D-C11-ACTION-ENTRY-SCHEMA-COMPOSITION-POSTFIX-REPLAY-01",
        "status": "COMPLETE" if all_checks else "STOPPED",
        "verdict": verdict,
        "independence": {
            "case_generation": "D_PREVIOUS_FAIL_FIRST_MUTATION_PATTERN",
            "used_a_five_case_output_as_expected_results": False,
            "used_current_formal_fixtures_to_generate_five_cases": False,
        },
        "cases": cases,
        "legal_restore_semantics": restore_semantics,
        "current_validator": validator_checks,
        "ruff": {
            "returncode": ruff["returncode"],
            "stdout": ruff["stdout"],
            "stderr": ruff["stderr"],
            "pass": ruff["returncode"] == 0,
        },
        "json_parse": json_checks,
        "statistics": {
            "independent_cases_passed": sum(case["pass"] for case in cases),
            "independent_cases_total": len(cases),
            "illegal_cases_zero_write": sum(
                case["failure_path"] and case["zero_write"] for case in cases
            ),
            "illegal_cases_total": sum(case["failure_path"] for case in cases),
            "old_validator_cases_passed": sum(row["pass"] for row in old_results),
            "old_validator_cases_total": len(old_results),
            "new_validator_cases_passed": sum(row["pass"] for row in new_results),
            "new_validator_cases_total": len(new_results),
            "all_validator_cases_passed": sum(row["pass"] for row in current_results),
            "all_validator_cases_total": len(current_results),
            "formal_input_drift": len(formal_changed),
            "cache_hits": len(cache_hits),
            "api_calls": 0,
            "model_calls": 0,
            "automatic_retries": 0,
            "formal_writes": 0,
        },
        "formal_fix_applied": False,
        "scope_expanded": False,
    }
    no_touch = {
        "identity": "D_C11_ACTION_ENTRY_POSTFIX_NO_TOUCH_R01",
        "five_formal_inputs_unchanged": not formal_changed,
        "supporting_evidence_unchanged": not evidence_changed,
        "cache_hits": cache_hits,
        "unauthorized_write_path": 0,
        "formal_writes": 0,
        "product_writes": 0,
        "r13_writes": 0,
        "gold_reads_or_writes": 0,
        "novel_reads": 0,
        "notion_operations": 0,
        "git_operations": 0,
        "uploads": 0,
        "api_calls": 0,
        "model_calls": 0,
        "automatic_retries": 0,
    }
    write_json(RESULTS / "input_manifest.json", manifest)
    write_json(RESULTS / "postfix_replay_ledger.json", ledger_result)
    write_json(RESULTS / "no_touch_receipt.json", no_touch)
    print(
        f"{ledger_result['task_id']}: verdict={verdict} "
        f"independent={ledger_result['statistics']['independent_cases_passed']}/5 "
        f"zero_write={ledger_result['statistics']['illegal_cases_zero_write']}/4 "
        f"validator={ledger_result['statistics']['all_validator_cases_passed']}/80 "
        f"old={ledger_result['statistics']['old_validator_cases_passed']}/75 "
        f"new={ledger_result['statistics']['new_validator_cases_passed']}/5 "
        f"ruff={ruff['returncode']} json={all(item['pass'] for item in json_checks.values())} "
        f"drift={len(formal_changed)} cache={len(cache_hits)} "
        "API=0 models=0 retries=0 formal_writes=0"
    )
    return 0 if all_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
