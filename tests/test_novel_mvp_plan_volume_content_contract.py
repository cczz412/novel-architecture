from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "novel-mvp/contracts/validate_plan_volume_content.py"
CONTRACT_PATH = ROOT / "novel-mvp/contracts/PLAN_VOLUME_CONTENT.md"
SCHEMA_PATH = ROOT / "novel-mvp/contracts/PLAN_VOLUME_CONTENT.schema.json"
SPEC = importlib.util.spec_from_file_location(
    "validate_plan_volume_content",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures()


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_plan_volume_fixture_matrix(case: dict) -> None:
    MODULE.validate_fixture_case(case)


def test_fixture_counts_are_frozen() -> None:
    assert MODULE.validate_all_fixtures() == {
        "cases": 20,
        "valid": 8,
        "invalid": 12,
    }


def test_storage_r03_seven_fields_are_frozen() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["title"] == "PLAN_VOLUME_CONTENT volume-plan-content-v1"
    seven = [
        "order",
        "title",
        "goal",
        "main_conflict",
        "entry_state",
        "exit_state",
        "summary",
    ]
    for field in seven:
        assert field in schema["required"]
        assert field in schema["properties"]
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    for anchor in (
        "VOLUMES_NOT_SUPPORTED",
        "id_counters.VOL",
        "禁止改名、禁止删",
        "volumes_enabled=true` 的写路径挂后续 runtime 票",
    ):
        assert anchor in contract


def test_volume_prefix_is_vol() -> None:
    record = copy.deepcopy(
        next(case["document"] for case in CASES if case["case_id"] == "VOL-VALID-01")
    )
    assert record["id"].startswith("VOL-")
    MODULE.validate_record(record)
    record["id"] = "V-0001"
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


def test_nullable_trio_and_empty_summary_are_legal() -> None:
    record = next(
        case["document"] for case in CASES if case["case_id"] == "VOL-VALID-03"
    )
    validated = MODULE.validate_record(copy.deepcopy(record))
    assert validated["main_conflict"] is None
    assert validated["entry_state"] is None
    assert validated["exit_state"] is None
    assert validated["summary"] == ""


def test_pack_prefilled_is_not_a_volume_source() -> None:
    record = copy.deepcopy(
        next(case["document"] for case in CASES if case["case_id"] == "VOL-VALID-01")
    )
    record["source_identity"] = "pack_prefilled"
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
