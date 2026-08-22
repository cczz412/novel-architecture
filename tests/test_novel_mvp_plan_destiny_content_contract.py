from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "novel-mvp/contracts/validate_plan_destiny_content.py"
CONTRACT_PATH = ROOT / "novel-mvp/contracts/PLAN_DESTINY_CONTENT.md"
SCHEMA_PATH = ROOT / "novel-mvp/contracts/PLAN_DESTINY_CONTENT.schema.json"
SPEC = importlib.util.spec_from_file_location(
    "validate_plan_destiny_content",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures()


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_plan_destiny_fixture_matrix(case: dict) -> None:
    MODULE.validate_fixture_case(case)


def test_fixture_counts_are_frozen() -> None:
    assert MODULE.validate_all_fixtures() == {
        "cases": 20,
        "valid": 8,
        "invalid": 12,
    }


def test_destiny_prefix_is_official() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["id"]["pattern"] == "^DESTINY-[0-9]+$"
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "官方前缀" in contract
    assert "DESTINY-0001" in contract


def test_expected_at_three_anchor_kinds() -> None:
    kinds = {
        case["document"]["expected_at"]["kind"]
        for case in CASES
        if case["expect"] == "PASS" and case["document"]["expected_at"]
    }
    assert kinds == {"slot_anchor", "story_time_anchor", "fuzzy_anchor"}


def test_fuzzy_anchor_is_remind_only() -> None:
    record = copy.deepcopy(
        next(case["document"] for case in CASES if case["case_id"] == "DES-VALID-05")
    )
    assert MODULE.expected_at_alarm_policy(record) == {"policy": "REMIND_ONLY"}


def test_story_anchor_reuses_frozen_l2_tokens() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    anchor = schema["$defs"]["story_anchor"]
    assert anchor["required"] == ["chapter_revision_ref"]
    assert set(anchor["properties"]) == {"chapter_revision_ref", "story_order"}
    ref = schema["$defs"]["chapter_revision_ref"]
    assert set(ref["required"]) == {
        "chapter_id",
        "revision_no",
        "revision_text_sha256",
    }
    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    assert "story_sequence" not in schema_text


def test_legacy_story_anchor_keys_fail() -> None:
    record = copy.deepcopy(
        next(case["document"] for case in CASES if case["case_id"] == "DES-VALID-03")
    )
    record["expected_at"]["anchor"]["story_sequence"] = 3
    error = MODULE.validate_fixture_case(
        {
            "case_id": "INLINE",
            "fixture_kind": "record",
            "expect": "FAIL",
            "expected_error": "LEGACY_STORY_ANCHOR_KEY_FORBIDDEN:story_sequence",
            "document": record,
        }
    )
    assert error is not None
