from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "novel-mvp/contracts/validate_plan_inspiration_content.py"
CONTRACT_PATH = ROOT / "novel-mvp/contracts/PLAN_INSPIRATION_CONTENT.md"
SPEC = importlib.util.spec_from_file_location(
    "validate_plan_inspiration_content",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures()


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_plan_inspiration_fixture_matrix(case: dict) -> None:
    MODULE.validate_fixture_case(case)


def test_fixture_counts_are_frozen() -> None:
    assert MODULE.validate_all_fixtures() == {
        "cases": 20,
        "valid": 8,
        "invalid": 12,
    }


def test_one_inspiration_placed_three_times_is_legal() -> None:
    record = next(
        case["document"] for case in CASES if case["case_id"] == "INS-VALID-02"
    )
    validated = MODULE.validate_record(copy.deepcopy(record))
    assert len(validated["placements"]) == 3
    refs = {item["placement_ref"] for item in validated["placements"]}
    assert len(refs) == 3


def test_duplicate_placement_ref_fails() -> None:
    record = copy.deepcopy(
        next(case["document"] for case in CASES if case["case_id"] == "INS-VALID-02")
    )
    record["placements"].append(dict(record["placements"][0]))
    error = MODULE.validate_fixture_case(
        {
            "case_id": "INLINE",
            "fixture_kind": "record",
            "expect": "FAIL",
            "expected_error_prefix": "PLACEMENT_REF_DUPLICATE",
            "document": record,
        }
    )
    assert error is not None


def test_zero_format_threshold_one_liner_is_enough() -> None:
    record = copy.deepcopy(
        next(case["document"] for case in CASES if case["case_id"] == "INS-VALID-01")
    )
    record["content"] = "灯。"
    MODULE.validate_record(record)


def test_contract_forbids_digestion_fields() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "多实例" in contract
    assert "ADD-030" in contract
    record = copy.deepcopy(
        next(case["document"] for case in CASES if case["case_id"] == "INS-VALID-01")
    )
    record["digest_status"] = "digested"
    error = MODULE.validate_fixture_case(
        {
            "case_id": "INLINE",
            "fixture_kind": "record",
            "expect": "FAIL",
            "expected_error_prefix": "SCHEMA_INVALID",
            "document": record,
        }
    )
    assert error is not None
