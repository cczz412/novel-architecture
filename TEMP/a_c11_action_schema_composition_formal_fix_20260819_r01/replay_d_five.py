from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[2]
CONTRACTS = REPO / "novel-mvp" / "contracts"
VALIDATOR_PATH = CONTRACTS / "validate_c11_chapter_revision_ledger.py"
FIXTURE_PATH = CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl"
ACTION_PATH = CONTRACTS / "CHAPTER_REVISION_COMMIT_ACTION.md"
SCHEMA_PATH = CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.schema.json"
INPUTS = [VALIDATOR_PATH, FIXTURE_PATH, ACTION_PATH, SCHEMA_PATH]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_validator():
    sys.path.insert(0, str(CONTRACTS))
    try:
        spec = importlib.util.spec_from_file_location("c11_action_replay", VALIDATOR_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError("C11_VALIDATOR_IMPORT_FAILED")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def schema_result(c11, action: dict) -> dict:
    try:
        c11.validate_schema_document(c11.schema_validator(), action)
    except c11.ContractError as exc:
        return {"accepted": False, "error_code": str(exc).split(":", 1)[0]}
    return {"accepted": True, "error_code": None}


def main() -> int:
    before = {str(path): sha256_file(path) for path in INPUTS}
    c11 = load_validator()
    ledger = c11.ledger_one()
    replacement_text = "甲放下钥匙。乙回家。"
    records = [c11.c10_material_record(replacement_text, "R2")]
    legal = c11.base_action(replacement_text)

    candidates = []
    candidates.append(("ENTRY-01-LEGAL-REPLACE", "NONE", copy.deepcopy(legal)))
    initial = copy.deepcopy(legal)
    initial["items"][0]["change_kind"] = "INITIAL"
    candidates.append(("ENTRY-02-INVALID-INITIAL", "items[0].change_kind=INITIAL", initial))
    bogus = copy.deepcopy(legal)
    bogus["items"][0]["change_kind"] = "BOGUS"
    candidates.append(("ENTRY-03-INVALID-BOGUS", "items[0].change_kind=BOGUS", bogus))
    missing_contract = copy.deepcopy(legal)
    del missing_contract["contract"]
    candidates.append(("ENTRY-04A-MISSING-CONTRACT", "top-level contract removed", missing_contract))
    missing_version = copy.deepcopy(legal)
    del missing_version["version"]
    candidates.append(("ENTRY-04B-MISSING-VERSION", "top-level version removed", missing_version))

    cases = []
    for case_id, mutation, action in candidates:
        schema = schema_result(c11, action)
        entry = c11.validate_action(action, ledger, records)
        legal_case = case_id == "ENTRY-01-LEGAL-REPLACE"
        passed = (
            schema["accepted"] and entry == "PRECHECK_ALLOWED"
            if legal_case
            else not schema["accepted"] and entry == "REJECTED_ACTION_SCHEMA"
        )
        cases.append(
            {
                "case_id": case_id,
                "mutation": mutation,
                "schema": schema,
                "validate_action": entry,
                "pass": passed,
                "writes": 0,
            }
        )

    after = {str(path): sha256_file(path) for path in INPUTS}
    output = {
        "identity": "A_C11_D_FIVE_CASE_REPLAY_R01",
        "task_id": "A-C11-ACTION-SCHEMA-COMPOSITION-FORMAL-FIX-01",
        "status": "PASS" if all(case["pass"] for case in cases) else "FAIL",
        "cases": cases,
        "cases_passed": sum(case["pass"] for case in cases),
        "cases_total": len(cases),
        "input_sha_before": before,
        "input_sha_after": after,
        "input_drift": [path for path in before if before[path] != after[path]],
        "failure_path_writes": 0,
        "api_calls": 0,
        "model_calls": 0,
        "automatic_retries": 0,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["status"] == "PASS" and not output["input_drift"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
