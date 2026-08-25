"""Validate PLAN_MILESTONE_CONTENT milestone-plan-content-v1."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any

DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "PLAN_MILESTONE_CONTENT.schema.json"
FIXTURE_PATH = DIR / "PLAN_MILESTONE_CONTENT.fixtures.jsonl"
COMMON_PATH = DIR / "plan_longline_contract_common.py"


def _load_common() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_plan_milestone_content_common",
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
CONTRACT = "PLAN_MILESTONE_CONTENT"
VERSION = "milestone-plan-content-v1"
PREFIX = "MS-"


def validate_record(
    document: Any,
    *,
    sibling_orders: dict[str, set[int]] | None = None,
) -> dict[str, Any]:
    record = COMMON.validate_plan_root(
        document,
        schema=SCHEMA,
        contract=CONTRACT,
        version=VERSION,
        prefix=PREFIX,
    )
    if record["title"] != record["title"].strip():
        raise ContractError("TITLE_MUST_BE_TRIMMED")
    owner = record["owner_storyline_ref"]
    if owner not in record["storyline_refs"]:
        raise ContractError("OWNER_MUST_BE_IN_STORYLINE_REFS")
    if record["id"] in record["milestone_refs"]:
        raise ContractError("MILESTONE_REFS_SELF_FORBIDDEN")
    if len(record["storyline_refs"]) != len(set(record["storyline_refs"])):
        raise ContractError("STORYLINE_REFS_DUPLICATE")
    if len(record["milestone_refs"]) != len(set(record["milestone_refs"])):
        raise ContractError("MILESTONE_REFS_DUPLICATE")
    for index, edge in enumerate(record["planning_dependency_edges"]):
        if edge["from_ref"] == edge["to_ref"]:
            raise ContractError(f"PLAN_DEP_SELF_LOOP:{index}")
    if sibling_orders is not None:
        seen = sibling_orders.get(owner, set())
        if record["construction_order"] in seen:
            raise ContractError("CONSTRUCTION_ORDER_DUPLICATE")
    return record


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    return COMMON.load_fixtures(path)


_HANDLERS = {
    "record": lambda case: validate_record(
        case["document"],
        sibling_orders=(
            {key: set(value) for key, value in case["sibling_orders"].items()}
            if "sibling_orders" in case
            else None
        ),
    ),
}


def validate_fixture_case(case: dict[str, Any]) -> str | None:
    return COMMON.validate_fixture_case(case, _HANDLERS)


def validate_all_fixtures(path: Path = FIXTURE_PATH) -> dict[str, int]:
    return COMMON.validate_all_fixtures(path, _HANDLERS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true")
    args = parser.parse_args()
    if not args.fixtures:
        print("Use --fixtures to validate the frozen fixture pack.")
        return 0
    counts = validate_all_fixtures()
    print(
        "PASS_PLAN_MILESTONE_CONTENT "
        f"cases={counts['cases']} valid={counts['valid']} invalid={counts['invalid']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
