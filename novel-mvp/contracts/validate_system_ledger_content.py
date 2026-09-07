"""Validate SYSTEM_LEDGER_CONTENT system-ledger-content-v1."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "SYSTEM_LEDGER_CONTENT.schema.json"
FIXTURE_PATH = DIR / "SYSTEM_LEDGER_CONTENT.fixtures.jsonl"
COMMON_PATH = DIR / "ledger_content_contract_common.py"


def _load_common() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_system_ledger_content_common",
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
CONTRACT = "SYSTEM_LEDGER_CONTENT"
VERSION = "system-ledger-content-v1"
VERSION_V2 = "system-ledger-content-v2"
VERSIONS = (VERSION, VERSION_V2)
PREFIX = "SY-"


def validate_record(document: Any) -> dict[str, Any]:
    record = COMMON.validate_root(
        document,
        schema=SCHEMA,
        contract=CONTRACT,
        version=VERSIONS,
        prefix=PREFIX,
    )
    if record["source_identity"] == "pack_prefilled" and record["pack_ref"] is None:
        raise ContractError("PACK_PREFILLED_PACK_REF_REQUIRED")
    for index, relation in enumerate(record["relations"]):
        if relation["target_ref"] == record["id"]:
            raise ContractError(
                f"SYSTEM_RELATION_SELF_REFERENCE_FORBIDDEN:{index}"
            )
    return record


def validate_pack_prefilled_transition(before: Any, after: Any) -> None:
    before_record = validate_record(before)
    after_record = validate_record(after)
    try:
        COMMON.ENVELOPE.validate_pack_prefilled_author_edit(
            COMMON.envelope(before_record),
            COMMON.envelope(after_record),
            content_before={"pack_ref": before_record["pack_ref"]},
            content_after={"pack_ref": after_record["pack_ref"]},
        )
    except COMMON.ENVELOPE.ContractError as exc:
        raise ContractError(f"PACK_TRANSITION_INVALID:{exc}") from exc


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    return COMMON.load_fixtures(path)


def validate_fixture_case(case: dict[str, Any]) -> str | None:
    try:
        if case["fixture_kind"] == "record":
            validate_record(case["document"])
        elif case["fixture_kind"] == "pack_transition":
            validate_pack_prefilled_transition(case["before"], case["after"])
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
            "PASS_SYSTEM_LEDGER_CONTENT "
            f"cases={counts['cases']} valid={counts['valid']} "
            f"invalid={counts['invalid']}"
        )
        return 0
    if args.input is None:
        parser.error("--input or --fixtures is required")
    validate_record(json.loads(args.input.read_text(encoding="utf-8")))
    print("PASS_SYSTEM_LEDGER_CONTENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
