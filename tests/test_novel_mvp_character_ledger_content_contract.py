from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = (
    ROOT / "novel-mvp/contracts/validate_character_ledger_content.py"
)
FIXTURE_PATH = (
    ROOT / "novel-mvp/contracts/CHARACTER_LEDGER_CONTENT.fixtures.jsonl"
)
CONTRACT_PATH = ROOT / "novel-mvp/contracts/CHARACTER_LEDGER_CONTENT.md"

SPEC = importlib.util.spec_from_file_location(
    "validate_character_ledger_content",
    VALIDATOR_PATH,
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures(FIXTURE_PATH)


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=[case["case_id"] for case in CASES],
)
def test_frozen_character_contract_fixtures(case: dict) -> None:
    actual = MODULE.validate_fixture_case(case)
    if case["valid"]:
        assert actual is None
    else:
        assert actual is not None
        assert actual.startswith(case["expected_error"])


def valid_state_record() -> dict:
    record = copy.deepcopy(next(case["document"] for case in CASES if case["case_id"] == "CL-001"))
    record["state_timeline"] = [
        {
            "ch_ref": "CH-0001",
            "state_key": "injury:left_arm",
            "value": "fractured",
            "story_time": {
                "start": {
                    "chapter_revision_ref": {
                        "chapter_id": "c12",
                        "revision_no": 1,
                        "revision_text_sha256": "a" * 64,
                    },
                    "story_order": 120,
                },
                "end": {
                    "chapter_revision_ref": {
                        "chapter_id": "c18",
                        "revision_no": 1,
                        "revision_text_sha256": "b" * 64,
                    },
                    "story_order": 180,
                },
            },
            "evidence_refs": ["f023"],
        },
        {
            "ch_ref": "CH-0001",
            "state_key": "injury:left_arm",
            "value": "healed",
            "story_time": {
                "start": {
                    "chapter_revision_ref": {
                        "chapter_id": "c18",
                        "revision_no": 1,
                        "revision_text_sha256": "b" * 64,
                    },
                    "story_order": 180,
                },
                "end": None,
            },
            "evidence_refs": ["f031"],
        },
    ]
    return record


def as_of(order: int, chapter_id: str) -> dict:
    return {
        "chapter_revision_ref": {
            "chapter_id": chapter_id,
            "revision_no": 1,
            "revision_text_sha256": "c" * 64,
        },
        "story_order": order,
    }


def test_as_of_before_first_record_returns_not_recorded() -> None:
    result = MODULE.query_state_as_of(
        valid_state_record(),
        state_key="injury:left_arm",
        as_of=as_of(100, "c10"),
    )
    assert result == {
        "status": "NOT_RECORDED",
        "state_key": "injury:left_arm",
        "value": None,
    }


def test_as_of_does_not_use_latest_state_for_history() -> None:
    result = MODULE.query_state_as_of(
        valid_state_record(),
        state_key="injury:left_arm",
        as_of=as_of(150, "c15"),
    )
    assert result["status"] == "RECORDED"
    assert result["value"] == "fractured"
    assert result["value"] != "healed"


def test_as_of_after_transition_returns_new_state() -> None:
    result = MODULE.query_state_as_of(
        valid_state_record(),
        state_key="injury:left_arm",
        as_of=as_of(200, "c20"),
    )
    assert result["status"] == "RECORDED"
    assert result["value"] == "healed"


def test_missing_story_order_does_not_guess_chapter_order() -> None:
    target = {
        "chapter_revision_ref": {
            "chapter_id": "c15",
            "revision_no": 1,
            "revision_text_sha256": "c" * 64,
        }
    }
    result = MODULE.query_state_as_of(
        valid_state_record(),
        state_key="injury:left_arm",
        as_of=target,
    )
    assert result == {
        "status": "STORY_TIME_NOT_COMPARABLE",
        "state_key": "injury:left_arm",
        "value": None,
    }


def test_destiny_ref_requires_official_prefix() -> None:
    record = copy.deepcopy(
        next(case["document"] for case in CASES if case["case_id"] == "CL-002")
    )
    assert record["destiny_ref"] == "DESTINY-0001"
    MODULE.validate_record(record)
    record["destiny_ref"] = "DESTINY-DOES-NOT-EXIST"
    with pytest.raises(MODULE.ContractError, match="DESTINY_REF_PREFIX_INVALID"):
        MODULE.validate_record(record)
    record["destiny_ref"] = "DY-0001"
    with pytest.raises(MODULE.ContractError, match="DESTINY_REF_PREFIX_INVALID"):
        MODULE.validate_record(record)


def test_destiny_ref_existence_closes_in_l5() -> None:
    record = copy.deepcopy(
        next(case["document"] for case in CASES if case["case_id"] == "CL-002")
    )
    directory = frozenset({"DESTINY-0001", "DESTINY-0002"})
    MODULE.validate_record(record, destiny_ids=directory)
    record["destiny_ref"] = "DESTINY-0099"
    with pytest.raises(MODULE.ContractError, match="DESTINY_REF_NOT_FOUND"):
        MODULE.validate_record(record, destiny_ids=directory)
    record["destiny_ref"] = None
    MODULE.validate_record(record, destiny_ids=directory)


def test_death_and_resurrection_remain_two_attested_timepoints() -> None:
    record = copy.deepcopy(
        next(case["document"] for case in CASES if case["case_id"] == "CL-006")
    )
    MODULE.validate_record(record)
    alive_rows = [
        item for item in record["state_timeline"] if item["state_key"] == "alive"
    ]
    assert [item["value"] for item in alive_rows] == ["dead", "alive"]
    assert all(
        "AUTHOR_ATTESTATION" in item["evidence_refs"] for item in alive_rows
    )
    assert (
        alive_rows[0]["story_time"]["start"]
        != alive_rows[1]["story_time"]["start"]
    )


def test_contract_keeps_knowledge_edge_fields_open() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "知情边" in contract
    assert "只留位" in contract
    invalid = copy.deepcopy(
        next(case["document"] for case in CASES if case["case_id"] == "CL-001")
    )
    invalid["knowledge_edges"] = []
    error = MODULE.validate_fixture_case(
        {"case_id": "INLINE", "valid": False, "document": invalid}
    )
    assert error is not None
    assert error.startswith("SCHEMA_INVALID")


def test_validator_is_read_only() -> None:
    tracked = [VALIDATOR_PATH, FIXTURE_PATH, CONTRACT_PATH]
    before = {path: path.read_bytes() for path in tracked}
    MODULE.run_fixtures(FIXTURE_PATH)
    after = {path: path.read_bytes() for path in tracked}
    assert before == after
