from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "novel-mvp/contracts/validate_system_ledger_content.py"
CONTRACT_PATH = ROOT / "novel-mvp/contracts/SYSTEM_LEDGER_CONTENT.md"
SCHEMA_PATH = ROOT / "novel-mvp/contracts/SYSTEM_LEDGER_CONTENT.schema.json"
SPEC = importlib.util.spec_from_file_location(
    "validate_system_ledger_content",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures()


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_system_ledger_fixture_matrix(case: dict) -> None:
    MODULE.validate_fixture_case(case)


def test_fixture_counts_are_frozen() -> None:
    assert MODULE.validate_all_fixtures() == {
        "cases": 22,
        "valid": 9,
        "invalid": 13,
    }


def test_contract_identity_and_fields_are_frozen() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "system-ledger-content-v1" in schema["title"]
    assert "system-ledger-content-v2" in schema["title"]
    for anchor in (
        "category",
        "rank_order",
        "有向关系",
        "pack_ref 原样留痕",
        "关系是定义卡上的有向边，不带故事时间区间",
    ):
        assert anchor in contract


def test_relation_direction_is_not_auto_reversed() -> None:
    case = next(item for item in CASES if item["case_id"] == "SY-VALID-03")
    record = MODULE.validate_record(case["document"])
    assert record["relations"] == [
        {"target_ref": "SY-0002", "kind": "进阶"},
    ]
    assert all(item["target_ref"] != record["id"] for item in record["relations"])


def test_pack_prefilled_transition_preserves_pack_ref() -> None:
    case = next(item for item in CASES if item["case_id"] == "SY-VALID-04")
    MODULE.validate_pack_prefilled_transition(case["before"], case["after"])
    assert case["before"]["pack_ref"] == case["after"]["pack_ref"]


def test_definition_root_story_time_is_null() -> None:
    case = next(item for item in CASES if item["case_id"] == "SY-VALID-01")
    assert MODULE.validate_record(case["document"])["story_time"] is None


def test_relation_schema_has_no_time_fields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    relation = schema["$defs"]["relation"]
    assert set(relation["properties"]) == {"target_ref", "kind"}


def test_open_items_are_not_materialized_as_fields() -> None:
    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "knowledge_edges",
        "reader_projection",
        "new_ledger_request",
        "recall_handle",
    ):
        assert forbidden not in schema_text
