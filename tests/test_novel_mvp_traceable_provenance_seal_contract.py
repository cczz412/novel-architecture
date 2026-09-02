from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "novel-mvp" / "contracts"
MODULE_PATH = CONTRACTS / "validate_traceable_provenance_seal.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("traceable_provenance_seal", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_module()


def _cases() -> list[dict]:
    return validator.load_fixtures()


def _case(case_id: str) -> dict:
    return next(row for row in _cases() if row["case_id"] == case_id)


def test_schema_and_fixture_inventory_are_frozen() -> None:
    assert validator.SCHEMA["title"] == "TRACEABLE_PROVENANCE_SEAL v1"
    cases = _cases()
    assert len(cases) == 37
    assert len({row["case_id"] for row in cases}) == len(cases)
    assert validator.validate_all_fixtures() == {
        validator.STRUCTURAL_VALID: 8,
        validator.STRUCTURAL_VALID_OWNER_UNRESOLVED: 8,
        validator.STRUCTURAL_INVALID: 21,
    }


@pytest.mark.parametrize("case", _cases(), ids=lambda row: row["case_id"])
def test_each_fixture_has_the_declared_result(case: dict) -> None:
    assert validator.validate_fixture_case(case) == case["expected_result"]


def test_seal_sha_is_stable_and_any_binding_change_requires_a_new_id() -> None:
    document = copy.deepcopy(_case("TPS-VALID-01")["document"])
    assert validator.validate_seal(document) == validator.STRUCTURAL_VALID
    assert validator.seal_document(document) == document

    changed = copy.deepcopy(document)
    changed["subject_ref"]["role"] = "changed-subject-role"
    with pytest.raises(validator.ContractError, match="SEAL_SHA256_MISMATCH"):
        validator.validate_seal(changed)
    assert validator.seal_document(changed)["seal_sha256"] != document["seal_sha256"]


def test_scope_is_rejected_before_owner_wrapper_details() -> None:
    case = copy.deepcopy(_case("TPS-INVALID-01"))
    case["document"]["direct_basis_refs"][0]["ref"]["stable_id"] = "BROKEN"
    with pytest.raises(validator.ContractError, match="^TRUTH_SCOPE_MISMATCH$"):
        validator.validate_seal(case["document"])


def test_pinned_historical_subject_remains_structurally_valid() -> None:
    document = _case("TPS-VALID-07")["document"]
    assert document["subject_ref"]["binding_mode"] == "recorded_pin"
    assert document["subject_ref"]["retired_notice"] is True
    assert validator.validate_seal(document) == validator.STRUCTURAL_VALID


def test_owner_unresolved_is_not_reported_as_owner_committed() -> None:
    document = _case("TPS-UNRESOLVED-01")["document"]
    assert document["subject_ref"]["stable_id"] is None
    assert (
        validator.validate_seal(document)
        == validator.STRUCTURAL_VALID_OWNER_UNRESOLVED
    )


def test_no_change_cannot_form_a_new_owner_commit_seal() -> None:
    document = _case("TPS-INVALID-09")["document"]
    with pytest.raises(validator.ContractError, match="OWNER_COMMIT_RECEIPT_NOT_COMMITTED"):
        validator.validate_seal(document)


def test_contract_and_fixtures_do_not_copy_protected_content() -> None:
    forbidden = validator.FORBIDDEN_CONTENT_KEYS
    for case in (
        row
        for row in _cases()
        if row["expected_result"] != validator.STRUCTURAL_INVALID
    ):
        stack = [case["document"]]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                assert forbidden.isdisjoint(value)
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)


def test_contract_text_keeps_runtime_and_truth_boundaries_explicit() -> None:
    text = (CONTRACTS / "TRACEABLE_PROVENANCE_SEAL.md").read_text(encoding="utf-8")
    for phrase in (
        "CONTRACT_ONLY__OWNER_RESOLUTION_AND_RUNTIME_NOT_AUTHORIZED",
        "STRUCTURAL_VALID_OWNER_UNRESOLVED",
        "OWNER_RESOLUTION_AND_AUTHORITY_VERIFICATION",
        "工作稿交棒不能产生或证明 facts、ledger、actual、对账或 closeout",
        "长线账是规划账的读取投影",
        "expected_fact_sha256",
    ):
        assert phrase in text


def test_cli_reports_separate_counts_and_zero_external_calls() -> None:
    completed = subprocess.run(
        [sys.executable, str(MODULE_PATH)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "PASS"
    assert result["counts"] == {
        validator.STRUCTURAL_VALID: 8,
        validator.STRUCTURAL_VALID_OWNER_UNRESOLVED: 8,
        validator.STRUCTURAL_INVALID: 21,
    }
    assert result["owner_resolution_performed"] is False
    assert result["network_calls"] == 0
    assert result["model_calls"] == 0
