from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "novel-mvp/contracts"
MODULE_PATH = CONTRACT_DIR / "validate_knowledge_edge.py"
CONTRACT_PATH = CONTRACT_DIR / "KNOWLEDGE_EDGE.md"
SCHEMA_PATH = CONTRACT_DIR / "KNOWLEDGE_EDGE.schema.json"
CHARACTER_CONTRACT_PATH = CONTRACT_DIR / "CHARACTER_LEDGER_CONTENT.md"
CHARACTER_SCHEMA_PATH = CONTRACT_DIR / "CHARACTER_LEDGER_CONTENT.schema.json"
SPEC = importlib.util.spec_from_file_location("validate_knowledge_edge", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures()


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_knowledge_edge_fixture_matrix(case: dict) -> None:
    MODULE.validate_fixture_case(case)


def test_fixture_counts_are_frozen() -> None:
    assert MODULE.validate_all_fixtures() == {
        "cases": 29,
        "valid": 11,
        "invalid": 18,
    }


def test_seven_business_fields_are_exact_and_fact_ref_is_stable() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    edge = schema["$defs"]["edge"]
    business_fields = {
        "observer_ref",
        "epistemic_state",
        "fact_ref",
        "belief_content",
        "story_time_interval",
        "evidence_refs",
        "version_status",
    }
    assert business_fields <= set(edge["required"])
    assert edge["properties"]["observer_ref"]["pattern"] == "^CH-[0-9]+$"
    assert edge["properties"]["fact_ref"]["pattern"] == "^f[0-9]{3,}$"
    assert edge["properties"]["permission_namespace"]["const"] == (
        "knowledge-edge.v1"
    )


def test_false_belief_requires_bounded_inline_text() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    belief = schema["$defs"]["edge"]["properties"]["belief_content"]
    text_shape = next(shape for shape in belief["oneOf"] if shape["type"] == "string")
    assert text_shape["minLength"] == 1
    assert text_shape["maxLength"] == 500
    invalid_null = next(case for case in CASES if case["case_id"] == "KE-INVALID-01")
    with pytest.raises(MODULE.ContractError, match="SCHEMA_INVALID"):
        MODULE.validate_document(invalid_null["document"])


def test_no_record_means_untracked_not_explicitly_does_not_know() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "无记录不是第五种知情状态" in contract
    assert "不得改写成 `explicitly_does_not_know`" in contract
    assert "EMPTY + NO_MATCHING_ENTRIES" in contract


def test_knowledge_edges_stay_out_of_character_ledger_body() -> None:
    contract = CHARACTER_CONTRACT_PATH.read_text(encoding="utf-8")
    character_schema = json.loads(CHARACTER_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert "[KNOWLEDGE_EDGE.md](KNOWLEDGE_EDGE.md)" in contract
    assert "不住人物账本体" in contract
    assert "knowledge_edges" not in character_schema["properties"]
    assert character_schema["additionalProperties"] is False


def test_only_author_can_confirm_modify_or_retire() -> None:
    invalid = next(case for case in CASES if case["case_id"] == "KE-INVALID-07")
    with pytest.raises(MODULE.ContractError, match="AUTHOR_REQUIRED_FOR_FORMAL_ACTION"):
        MODULE.validate_document(invalid["document"])
    valid = next(case for case in CASES if case["case_id"] == "KE-VALID-04")
    action = MODULE.validate_document(valid["document"])
    assert action["writer_namespace"] == MODULE.WRITER_NAMESPACE
    assert action["requested_by"] == "AUTHOR"


def test_revision_chain_requires_base_revision_and_stable_identity() -> None:
    base_conflict = next(case for case in CASES if case["case_id"] == "KE-INVALID-13")
    with pytest.raises(MODULE.ContractError, match="BASE_REVISION_CONFLICT"):
        MODULE.validate_revision_transition(
            base_conflict["previous"],
            base_conflict["current"],
            base_conflict["action"],
        )
    identity_change = next(case for case in CASES if case["case_id"] == "KE-INVALID-14")
    with pytest.raises(MODULE.ContractError, match="STABLE_EDGE_IDENTITY_CHANGED"):
        MODULE.validate_revision_transition(
            identity_change["previous"],
            identity_change["current"],
            identity_change["action"],
        )


def test_current_and_historical_are_pointer_roles_not_mutable_revision_fields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    status = schema["$defs"]["version_status"]
    assert set(status["required"]) == {"confirmation", "lifecycle"}
    assert "revision_role" not in status["properties"]
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "current／historical 不写进不可变 revision" in contract
    assert "旧记录本身一个字不改" in contract


def test_permissions_are_full_task_scoped_or_closed() -> None:
    author = next(case for case in CASES if case["case_id"] == "KE-VALID-05")
    task = next(case for case in CASES if case["case_id"] == "KE-VALID-06")
    reader = next(case for case in CASES if case["case_id"] == "KE-VALID-07")
    assert MODULE.validate_document(author["document"])["access"] == "FULL_PROJECT"
    assert MODULE.validate_document(task["document"])["access"] == "TASK_SLICE"
    assert MODULE.validate_document(reader["document"])["access"] == "CLOSED"


def test_transaction_reuse_does_not_merge_fact_and_cognitive_state() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    for anchor in (
        "允许复用现有事务协调器",
        "知情边是独立对象",
        "认知状态不能写进事实状态",
        "事实确认不能自动确认知情边",
    ):
        assert anchor in contract


def test_contract_only_validator_does_not_import_runtime() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    validator = MODULE_PATH.read_text(encoding="utf-8")
    assert "CONTRACT_ONLY__WRITER_AND_READ_RUNTIME_NOT_AUTHORIZED" in contract
    assert "from mvp" not in validator
    assert "novel-mvp/mvp" not in validator
