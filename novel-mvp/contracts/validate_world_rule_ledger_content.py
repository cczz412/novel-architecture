"""Validate WORLD_RULE_LEDGER_CONTENT world-rule-ledger-content-v1."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "WORLD_RULE_LEDGER_CONTENT.schema.json"
FIXTURE_PATH = DIR / "WORLD_RULE_LEDGER_CONTENT.fixtures.jsonl"
COMMON_PATH = DIR / "ledger_content_contract_common.py"


def _load_common() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_world_rule_ledger_content_common",
        COMMON_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("COMMON_HELPER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMMON = _load_common()
ContractError = COMMON.ContractError
SCHEMA = COMMON.load_schema(SCHEMA_PATH)
CONTRACT = "WORLD_RULE_LEDGER_CONTENT"
VERSION = "world-rule-ledger-content-v1"
PREFIX = "RU-"


def validate_record(document: Any) -> dict[str, Any]:
    record = COMMON.validate_root(
        document,
        schema=SCHEMA,
        contract=CONTRACT,
        version=VERSION,
        prefix=PREFIX,
    )
    if record["rule_text"] != record["rule_text"].strip():
        raise ContractError("RULE_TEXT_MUST_BE_TRIMMED")
    if "\n" in record["rule_text"] or "\r" in record["rule_text"]:
        raise ContractError("RULE_TEXT_MUST_BE_SINGLE_LINE")
    if any(item != item.strip() for item in record["exceptions"]):
        raise ContractError("EXCEPTION_TEXT_MUST_BE_TRIMMED")
    return record


def m7_red_light_eligibility(document: Any) -> dict[str, Any]:
    record = validate_record(document)
    if record["hardness"] != "hard":
        return {"status": "NOT_ELIGIBLE", "reason": "HARDNESS_NOT_HARD"}
    if record["confirm_status"] != "confirmed":
        return {
            "status": "NOT_ELIGIBLE",
            "reason": "CONFIRM_STATUS_NOT_CONFIRMED",
        }
    return {
        "status": "ELIGIBLE",
        "reason": "HARD_CONFIRMED_MECHANICAL_PREREQUISITE",
    }


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    return COMMON.load_fixtures(path)


def validate_fixture_case(case: dict[str, Any]) -> str | None:
    try:
        if case["fixture_kind"] == "record":
            actual: Any = validate_record(case["document"])
        elif case["fixture_kind"] == "eligibility":
            actual = m7_red_light_eligibility(case["document"])
        else:
            raise ContractError("FIXTURE_KIND_INVALID")
    except ContractError as exc:
        error = str(exc)
        if case["expect"] != "FAIL":
            raise
        expected = case.get("expected_error")
        prefix = case.get("expected_error_prefix")
        if expected is not None and error != expected:
            raise ContractError(
                f"FIXTURE_WRONG_ERROR:{case['case_id']}:{error}"
            ) from exc
        if prefix is not None and not error.startswith(prefix):
            raise ContractError(
                f"FIXTURE_WRONG_ERROR_PREFIX:{case['case_id']}:{error}"
            ) from exc
        return error
    if case["expect"] == "FAIL":
        raise ContractError(
            f"FIXTURE_EXPECTED_FAILURE_BUT_PASSED:{case['case_id']}"
        )
    if case["fixture_kind"] == "eligibility" and actual != case["expected_result"]:
        raise ContractError(
            f"FIXTURE_ELIGIBILITY_MISMATCH:{case['case_id']}:{actual}"
        )
    return None


def validate_all_fixtures(path: Path = FIXTURE_PATH) -> dict[str, int]:
    rows = load_fixtures(path)
    invalid = sum(validate_fixture_case(case) is not None for case in rows)
    return {"cases": len(rows), "valid": len(rows) - invalid, "invalid": invalid}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true")
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    if args.fixtures:
        counts = validate_all_fixtures()
        print(
            "PASS_WORLD_RULE_LEDGER_CONTENT "
            f"cases={counts['cases']} valid={counts['valid']} "
            f"invalid={counts['invalid']}"
        )
        return 0
    if args.input is None:
        parser.error("--input or --fixtures is required")
    validate_record(json.loads(args.input.read_text(encoding="utf-8")))
    print("PASS_WORLD_RULE_LEDGER_CONTENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
