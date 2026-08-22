"""Validate PLAN_INSPIRATION_CONTENT inspiration-plan-content-v1."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "PLAN_INSPIRATION_CONTENT.schema.json"
FIXTURE_PATH = DIR / "PLAN_INSPIRATION_CONTENT.fixtures.jsonl"
COMMON_PATH = DIR / "plan_longline_contract_common.py"


def _load_common() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_plan_inspiration_content_common",
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
CONTRACT = "PLAN_INSPIRATION_CONTENT"
VERSION = "inspiration-plan-content-v1"
PREFIX = "INS-"


def validate_record(document: Any) -> dict[str, Any]:
    record = COMMON.validate_plan_root(
        document,
        schema=SCHEMA,
        contract=CONTRACT,
        version=VERSION,
        prefix=PREFIX,
    )
    seen: set[str] = set()
    for placement in record["placements"]:
        ref = placement["placement_ref"]
        if ref in seen:
            raise ContractError(f"PLACEMENT_REF_DUPLICATE:{ref}")
        seen.add(ref)
    COMMON.validate_expected_at(record["expected_at"])
    return record


def expected_at_alarm_policy(document: Any) -> dict[str, str]:
    record = validate_record(document)
    return COMMON.expected_at_alarm_policy(record["expected_at"])


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    return COMMON.load_fixtures(path)


_HANDLERS = {
    "record": lambda case: validate_record(case["document"]),
    "alarm_policy": lambda case: expected_at_alarm_policy(case["document"]),
}


def validate_fixture_case(case: dict[str, Any]) -> str | None:
    return COMMON.validate_fixture_case(case, _HANDLERS)


def validate_all_fixtures(path: Path = FIXTURE_PATH) -> dict[str, int]:
    return COMMON.validate_all_fixtures(path, _HANDLERS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true")
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    if args.fixtures:
        counts = validate_all_fixtures()
        print(
            "PASS_PLAN_INSPIRATION_CONTENT "
            f"cases={counts['cases']} valid={counts['valid']} "
            f"invalid={counts['invalid']}"
        )
        return 0
    if args.input is None:
        parser.error("--input or --fixtures is required")
    validate_record(json.loads(args.input.read_text(encoding="utf-8")))
    print("PASS_PLAN_INSPIRATION_CONTENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
