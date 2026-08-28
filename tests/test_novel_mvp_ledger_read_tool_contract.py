from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "novel-mvp/contracts"
MODULE_PATH = CONTRACT_DIR / "validate_ledger_read_tool_contract.py"
CONTRACT_PATH = CONTRACT_DIR / "LEDGER_READ_TOOL_CONTRACT.md"
SCHEMA_PATH = CONTRACT_DIR / "LEDGER_READ_TOOL_CONTRACT.schema.json"
SPEC = importlib.util.spec_from_file_location(
    "validate_ledger_read_tool_contract",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures()


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_ledger_read_tool_fixture_matrix(case: dict) -> None:
    MODULE.validate_fixture_case(case)


def test_fixture_counts_are_frozen() -> None:
    assert MODULE.validate_all_fixtures() == {
        "cases": 27,
        "valid": 11,
        "invalid": 16,
    }


def test_ten_ledger_order_and_eight_read_profiles_are_exact() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert tuple(schema["$defs"]["ledger_name"]["enum"]) == MODULE.TEN_LEDGER_NAMES
    assert schema["$defs"]["read_profile"]["enum"] == list(
        MODULE.READ_PROFILE_BY_LEDGER.values()
    )
    assert "长线账" not in MODULE.READ_PROFILE_BY_LEDGER
    assert "规划账" not in MODULE.READ_PROFILE_BY_LEDGER


def test_character_historical_selector_excludes_current_definition() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    sections = schema["$defs"]["selector_character"]["properties"]["sections"]
    assert sections["items"]["enum"] == [
        "aliases_with_story_time",
        "state_timeline",
        "relationships_with_story_time",
    ]
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    for field in ("`profile`", "`role_tag`", "`destiny_ref`"):
        assert field in contract
    assert "完整当前人物定义不进入历史 `as-of`" in contract


def test_chapter_empty_scope_is_not_registered_empty() -> None:
    valid = next(case for case in CASES if case["case_id"] == "LR-VALID-08")
    assert MODULE.validate_document(valid["document"])["reason_code"] == (
        "NO_MATCHING_ENTRIES"
    )
    invalid = next(case for case in CASES if case["case_id"] == "LR-INVALID-09")
    with pytest.raises(MODULE.ContractError, match="CHAPTER_EMPTY_SEMANTICS_INVALID"):
        MODULE.validate_document(invalid["document"])


def test_masked_directory_state_cannot_leak_content_or_watermark() -> None:
    valid = next(case for case in CASES if case["case_id"] == "LR-VALID-06")
    snapshot = MODULE.validate_document(valid["document"])
    masked = [item for item in snapshot["ledgers"] if item["visibility"] == "MASKED"]
    assert masked
    assert all(item["content_status"] == "UNKNOWN" for item in masked)
    assert all(item["source_watermark"] is None for item in masked)


def test_unauthorized_response_cannot_bind_sources_or_snapshot() -> None:
    case = next(item for item in CASES if item["case_id"] == "LR-INVALID-16")
    with pytest.raises(MODULE.ContractError, match="UNAUTHORIZED_EXISTENCE_LEAK"):
        MODULE.validate_document(case["document"])


def test_basis_hash_is_logical_and_storage_generation_independent() -> None:
    case = next(item for item in CASES if item["case_id"] == "LR-VALID-11")
    left = copy.deepcopy(case["left"])
    right = copy.deepcopy(case["right"])
    assert left["receipt"]["storage_generation"] != right["receipt"][
        "storage_generation"
    ]
    assert MODULE.basis_sha256(left) == MODULE.basis_sha256(right)
    assert MODULE.basis_sha256(left) == left["receipt"]["basis_sha256"]
    MODULE.validate_storage_equivalence(left, right)


def test_storage_equivalence_rejects_changed_business_data() -> None:
    case = next(item for item in CASES if item["case_id"] == "LR-INVALID-12")
    with pytest.raises(
        MODULE.ContractError,
        match="STORAGE_LOGICAL_EQUIVALENCE_FAILED",
    ):
        MODULE.validate_storage_equivalence(case["left"], case["right"])


def test_box_and_knowledge_interfaces_remain_closed() -> None:
    box = next(item for item in CASES if item["case_id"] == "LR-VALID-09")
    knowledge = next(item for item in CASES if item["case_id"] == "LR-VALID-10")
    assert MODULE.validate_document(box["document"])["reason_code"] == (
        "PROJECTION_NOT_AVAILABLE"
    )
    assert MODULE.validate_document(knowledge["document"])["reason_code"] == (
        "FORMAL_CONTRACT_NOT_AVAILABLE"
    )


def test_limits_are_versioned_and_silent_truncation_is_impossible() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    limits = schema["$defs"]["limits"]["properties"]
    assert limits["policy_version"]["const"] == "limit-policy-v1"
    assert limits["business_items"]["maximum"] == 100
    assert limits["response_bytes"]["maximum"] == 262144
    assert limits["truncated"]["const"] is False
    refs = schema["$defs"]["selector_entries_current"]["properties"]["refs"]
    assert refs["maxItems"] == 50


def test_contract_only_validator_does_not_import_runtime() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    validator = MODULE_PATH.read_text(encoding="utf-8")
    assert "CONTRACT_ONLY__RUNTIME_NOT_AUTHORIZED" in contract
    assert "novel-mvp/mvp" not in validator
    assert "from mvp" not in validator
