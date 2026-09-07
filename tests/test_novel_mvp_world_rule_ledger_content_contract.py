from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
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


@pytest.mark.parametrize("target", ["/rule_text", "/exceptions"])
def test_v2_rejects_separately_masked_rule_condition(target: str) -> None:
    record = deepcopy(next(case["document"] for case in CASES
                           if case["document"]["version"] == MODULE.VERSION_V2
                           and case["expect"] == "PASS"))
    record["tags"].append("author:secret")
    record["tag_groups"]["groups"].append({
        "group_id": "author:secret", "members": ["author:secret"],
        "targets": [target], "mutation": "editable", "transition_rule": None,
        "access": {"read": ["AUTHOR"], "write": ["AUTHOR"]},
        "mask_for": ["model_context"], "managed_by": "AUTHOR",
    })
    with pytest.raises(MODULE.ContractError, match="WORLD_RULE_REQUIRED_FIELDS_MUST_SHARE_GROUP"):
        MODULE.validate_record(record)


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_world_rule_ledger_fixture_matrix(case: dict) -> None:
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
    assert (
        "world-rule-ledger-content-v1" in schema["title"]
        and "world-rule-ledger-content-v2" in schema["title"]
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


@pytest.mark.parametrize("source", ["draft_inferred", "model_suggested"])
def test_v2_non_author_rule_cannot_enter_red_light_path(source):
    record = deepcopy(next(case["document"] for case in CASES
                           if case["document"]["version"] == MODULE.VERSION_V2
                           and case["expect"] == "PASS"))
    record.update(source_identity=source, confirm_status="confirmed",
                  evidence_refs=["f001"], hardness="hard")
    with pytest.raises(MODULE.ContractError, match="CONFIRMED_REQUIRES_AUTHOR_DECLARED"):
        MODULE.m7_red_light_eligibility(record)
