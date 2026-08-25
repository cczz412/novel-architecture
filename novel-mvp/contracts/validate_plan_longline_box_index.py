"""Validate PLAN_LONGLINE_BOX_INDEX longline-box-index-v1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "PLAN_LONGLINE_BOX_INDEX.schema.json"
FIXTURE_PATH = DIR / "PLAN_LONGLINE_BOX_INDEX.fixtures.jsonl"
CONTRACT = "PLAN_LONGLINE_BOX_INDEX"
VERSION = "longline-box-index-v1"


class ContractError(ValueError):
    """A PLAN_LONGLINE_BOX_INDEX invariant failed."""


SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def _schema_path(error: Any) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "$"


def validate_record(document: Any) -> dict[str, Any]:
    errors = sorted(
        VALIDATOR.iter_errors(document),
        key=lambda item: (list(item.absolute_path), item.message),
    )
    if errors:
        first = errors[0]
        raise ContractError(f"SCHEMA_INVALID:{_schema_path(first)}:{first.validator}")
    assert isinstance(document, dict)
    if document["contract"] != CONTRACT or document["version"] != VERSION:
        raise ContractError("CONTRACT_IDENTITY_INVALID")
    if document["title"] != document["title"].strip():
        raise ContractError("TITLE_MUST_BE_TRIMMED")
    if document["status_light"] != document["compiled_status"]:
        raise ContractError("STATUS_LIGHT_MUST_MATCH_COMPILED")
    return document


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = [row.get("case_id") for row in rows]
    if len(ids) != len(set(ids)):
        raise ContractError("FIXTURE_CASE_ID_DUPLICATE")
    return rows


def validate_fixture_case(case: dict[str, Any]) -> str | None:
    try:
        validate_record(case["document"])
    except ContractError as exc:
        error = str(exc)
        if case.get("valid") is True:
            raise ContractError(f"FIXTURE_EXPECTED_VALID:{case['case_id']}:{error}") from exc
        expected = case.get("expected_error")
        if not expected or not error.startswith(expected):
            raise ContractError(
                f"FIXTURE_ERROR_MISMATCH:{case['case_id']}:expected={expected}:actual={error}"
            ) from exc
        return error
    if case.get("valid") is False:
        raise ContractError(f"FIXTURE_EXPECTED_FAILURE_BUT_PASSED:{case['case_id']}")
    return None


def run_fixtures(path: Path = FIXTURE_PATH) -> tuple[int, int]:
    rows = load_fixtures(path)
    invalid = sum(validate_fixture_case(case) is not None for case in rows)
    return len(rows) - invalid, invalid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", action="store_true")
    args = parser.parse_args()
    if not args.fixtures:
        print("Use --fixtures to validate the frozen fixture pack.")
        return 0
    valid_count, invalid_count = run_fixtures()
    print(
        "PASS_PLAN_LONGLINE_BOX_INDEX "
        f"cases={valid_count + invalid_count} valid={valid_count} invalid={invalid_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
