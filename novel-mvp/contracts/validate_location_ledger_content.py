"""Validate versioned LOCATION_LEDGER_CONTENT records."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "LOCATION_LEDGER_CONTENT.schema.json"
FIXTURE_PATH = DIR / "LOCATION_LEDGER_CONTENT.fixtures.jsonl"
COMMON_PATH = DIR / "ledger_content_contract_common.py"


def _load_common() -> Any:
    spec = importlib.util.spec_from_file_location("validate_location_ledger_content_common", COMMON_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("COMMON_HELPER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMMON = _load_common()
ContractError = COMMON.ContractError
SCHEMA = COMMON.load_schema(SCHEMA_PATH)
CONTRACT = "LOCATION_LEDGER_CONTENT"
VERSION = "location-ledger-content-v1"
VERSION_V2 = "location-ledger-content-v2"
VERSIONS = (VERSION, VERSION_V2)
PREFIX = "LOC-"

def validate_record(document: Any) -> dict[str, Any]:
    record = COMMON.validate_root(
        document,
        schema=SCHEMA,
        contract=CONTRACT,
        version=VERSIONS,
        prefix=PREFIX,
    )
    COMMON.validate_aliases(record, record["aliases"])
    for index, item in enumerate(record["state_timeline"]):
        if item["loc_ref"] != record["id"]:
            raise ContractError(f"STATE_LOC_REF_MUST_MATCH_ROOT:{index}")
    COMMON.validate_timeline(
        record,
        record["state_timeline"],
        identity=lambda item: (item["loc_ref"], item["state_key"]),
        label="state_timeline",
    )
    return record


def query_state_as_of(
    document: Any,
    *,
    state_key: str,
    as_of: dict[str, Any],
) -> dict[str, Any]:
    record = validate_record(document)
    return COMMON.query_timeline_as_of(
        record["state_timeline"],
        as_of=as_of,
        predicate=lambda item: item["state_key"] == state_key,
        project=lambda item: {
            "state_key": item["state_key"],
            "value": item["value"],
            "evidence_refs": list(item["evidence_refs"]),
            "story_time": item["story_time"],
        },
    )


def run_query_case(case: dict[str, Any]) -> dict[str, Any]:
    if case["fixture_kind"] != "state_query":
        raise ContractError("FIXTURE_KIND_INVALID")
    return query_state_as_of(case["document"], **case["query"])



def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    return COMMON.load_fixtures(path)


def validate_fixture_case(case: dict[str, Any]) -> str | None:
    try:
        if case["fixture_kind"] == "record":
            actual: Any = validate_record(case["document"])
        else:
            actual = run_query_case(case)
    except ContractError as exc:
        error = str(exc)
        if case["expect"] != "FAIL":
            raise
        expected = case.get("expected_error")
        prefix = case.get("expected_error_prefix")
        if expected is not None and error != expected:
            raise ContractError(f"FIXTURE_WRONG_ERROR:{case['case_id']}:{error}") from exc
        if prefix is not None and not error.startswith(prefix):
            raise ContractError(f"FIXTURE_WRONG_ERROR_PREFIX:{case['case_id']}:{error}") from exc
        return error
    if case["expect"] == "FAIL":
        raise ContractError(f"FIXTURE_EXPECTED_FAILURE_BUT_PASSED:{case['case_id']}")
    if case["fixture_kind"] != "record" and actual != case["expected_result"]:
        raise ContractError(f"FIXTURE_QUERY_RESULT_MISMATCH:{case['case_id']}:{actual}")
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
            "PASS_LOCATION_LEDGER_CONTENT "
            f"cases={counts['cases']} valid={counts['valid']} invalid={counts['invalid']}"
        )
        return 0
    if args.input is None:
        parser.error("--input or --fixtures is required")
    validate_record(json.loads(args.input.read_text(encoding="utf-8")))
    print("PASS_LOCATION_LEDGER_CONTENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
