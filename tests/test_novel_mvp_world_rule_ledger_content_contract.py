from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "novel-mvp/contracts/validate_world_rule_ledger_content.py"
CONTRACT_PATH = ROOT / "novel-mvp/contracts/WORLD_RULE_LEDGER_CONTENT.md"
SCHEMA_PATH = ROOT / "novel-mvp/contracts/WORLD_RULE_LEDGER_CONTENT.schema.json"
SPEC = importlib.util.spec_from_file_location(
    "validate_world_rule_ledger_content",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures()


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_world_rule_ledger_fixture_matrix(case: dict) -> None:
    MODULE.validate_fixture_case(case)


def test_fixture_counts_are_frozen() -> None:
    assert MODULE.validate_all_fixtures() == {
        "cases": 20,
        "valid": 8,
        "invalid": 12,
    }


def test_contract_identity_and_fields_are_frozen() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert (
        schema["title"]
        == "WORLD_RULE_LEDGER_CONTENT world-rule-ledger-content-v1"
    )
    for anchor in (
        "rule_text",
        "hardness=hard 且 confirm_status=confirmed",
        "M7 红灯资格",
        "例外做子字段",
        "ADD-043",
    ):
        assert anchor in contract


def test_hard_confirmed_rule_is_eligible() -> None:
    case = next(item for item in CASES if item["case_id"] == "RU-VALID-01")
    assert MODULE.m7_red_light_eligibility(case["document"]) == {
        "status": "ELIGIBLE",
        "reason": "HARD_CONFIRMED_MECHANICAL_PREREQUISITE",
    }


def test_hard_candidate_rule_is_not_eligible() -> None:
    case = next(item for item in CASES if item["case_id"] == "RU-VALID-03")
    assert MODULE.m7_red_light_eligibility(case["document"]) == {
        "status": "NOT_ELIGIBLE",
        "reason": "CONFIRM_STATUS_NOT_CONFIRMED",
    }


def test_advisory_confirmed_rule_is_not_eligible() -> None:
    case = next(item for item in CASES if item["case_id"] == "RU-VALID-02")
    assert MODULE.m7_red_light_eligibility(case["document"]) == {
        "status": "NOT_ELIGIBLE",
        "reason": "HARDNESS_NOT_HARD",
    }


def test_exceptions_remain_string_subfields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    items = schema["properties"]["exceptions"]["items"]
    assert items["type"] == "string"
    assert "oneOf" not in items


def test_open_items_are_not_materialized_as_fields() -> None:
    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "knowledge_edges",
        "reader_projection",
        "new_ledger_request",
        "exception_objects",
        "ability_objects",
        "recall_handle",
    ):
        assert forbidden not in schema_text
