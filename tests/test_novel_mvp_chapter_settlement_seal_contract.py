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
MODULE_PATH = CONTRACTS / "validate_chapter_settlement_seal.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "chapter_settlement_seal", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_module()


def _cases() -> list[dict]:
    return validator.load_fixtures()


def _case(case_id: str) -> dict:
    return next(row for row in _cases() if row["case_id"] == case_id)


def _document(case_id: str) -> dict:
    return validator.materialize_fixture_case(_case(case_id))["document"]


def test_schema_and_fixture_inventory_are_frozen() -> None:
    assert validator.SCHEMA["title"] == "CHAPTER_SETTLEMENT_SEAL v1"
    cases = _cases()
    assert len(cases) == 18
    assert len({row["case_id"] for row in cases}) == len(cases)
    assert validator.validate_all_fixtures() == {
        validator.STRUCTURAL_VALID: 4,
        validator.STRUCTURAL_VALID_OWNER_UNRESOLVED: 4,
        validator.STRUCTURAL_INVALID: 10,
    }


@pytest.mark.parametrize("case", _cases(), ids=lambda row: row["case_id"])
def test_each_fixture_has_the_declared_result(case: dict) -> None:
    assert validator.validate_fixture_case(case) == case["expected_result"]


def test_short_lived_closeout_action_is_not_a_settlement() -> None:
    document = _document("CSS-VALID-01")
    action = document["closeout_input"]
    with pytest.raises(validator.ContractError, match="^SCHEMA_INVALID"):
        validator.validate_settlement(action)


def test_route_and_manuscript_boundaries_are_independent() -> None:
    no_prose = _document("CSS-VALID-03")
    assert no_prose["closeout_input"]["route"] == "no_prose"
    assert no_prose["manuscript"] == {
        "disposition": "NO_PROSE",
        "chapter_revision_ref": None,
        "handover_receipt_ref": None,
        "written_progress_delta": 0,
        "provenance_seal_refs": [],
    }

    invalid = copy.deepcopy(no_prose)
    invalid["manuscript"] = _document("CSS-VALID-01")["manuscript"]
    invalid = validator.seal_document(invalid)
    with pytest.raises(
        validator.ContractError,
        match="NO_PROSE_MANUSCRIPT_EFFECT_FORBIDDEN",
    ):
        validator.validate_settlement(invalid)

    skipped = _document("CSS-VALID-02")
    assert skipped["closeout_input"]["check_result_ref"] is None
    assert skipped["manuscript"]["disposition"] == "NOT_ADOPTED"


def test_ten_ledgers_are_complete_ordered_and_do_not_add_an_owner() -> None:
    document = _document("CSS-VALID-01")
    assert tuple(row["ledger_name"] for row in document["ledger_coverage"]) == (
        "chapter",
        "fact",
        "character",
        "location",
        "item",
        "faction",
        "system",
        "world_rule",
        "longline",
        "planning",
    )
    assert all(
        row["result"] == "CONFIRMED_NO_CHANGE"
        for row in document["ledger_coverage"]
    )
    assert all(row["owner_contract"] for row in document["ledger_coverage"])


def test_committed_change_requires_a_same_ledger_owner_commit_seal() -> None:
    document = _document("CSS-VALID-01")
    row = next(
        item for item in document["ledger_coverage"]
        if item["ledger_name"] == "character"
    )
    row.update(
        {
            "result": "COMMITTED_CHANGE",
            "before_snapshot_sha256": "1" * 64,
            "after_snapshot_sha256": "2" * 64,
        }
    )
    document = validator.seal_document(document)
    with pytest.raises(
        validator.ContractError,
        match="COMMITTED_CHANGE_OWNER_RECEIPT_REQUIRED:character",
    ):
        validator.validate_settlement(document)


def test_owner_unresolved_cannot_be_reported_as_sealed() -> None:
    document = _document("CSS-UNRESOLVED-01")
    assert (
        validator.validate_settlement(document)
        == validator.STRUCTURAL_VALID_OWNER_UNRESOLVED
    )
    assert document["claim_kind"] == "OWNER_UNRESOLVED_CANDIDATE"

    changed = copy.deepcopy(document)
    changed["claim_kind"] = "OWNER_RESOLVED_SEALED"
    changed = validator.seal_document(changed)
    with pytest.raises(
        validator.ContractError,
        match="OWNER_UNRESOLVED_CANNOT_CLAIM_SEALED",
    ):
        validator.validate_settlement(changed)


def test_settlement_sha_is_stable_and_any_business_change_gets_a_new_id() -> None:
    document = _document("CSS-VALID-01")
    assert validator.validate_settlement(document) == validator.STRUCTURAL_VALID
    assert validator.seal_document(document) == document

    changed = copy.deepcopy(document)
    changed["outcome"]["actual_completion"][0]["summary"] += " 新结果。"
    changed = validator.seal_document(changed)
    assert changed["settlement_sha256"] != document["settlement_sha256"]
    assert validator.validate_settlement(changed) == validator.STRUCTURAL_VALID


def test_every_embedded_provenance_seal_is_used_and_revalidated() -> None:
    document = _document("CSS-VALID-01")
    dangling = copy.deepcopy(document)
    extra = copy.deepcopy(dangling["provenance_seals"][0])
    extra["subject_ref"]["role"] = "unused-synthetic-seal"
    extra = validator.tps.seal_document(extra)
    assert validator.tps.validate_seal(extra) == validator.tps.STRUCTURAL_VALID
    dangling["provenance_seals"].append(extra)
    dangling = validator.seal_document(dangling)
    with pytest.raises(validator.ContractError, match="PROVENANCE_SEAL_UNUSED"):
        validator.validate_settlement(dangling)


def test_contract_text_keeps_runtime_and_truth_boundaries_explicit() -> None:
    text = (CONTRACTS / "CHAPTER_SETTLEMENT_SEAL.md").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "CONTRACT_ONLY__OWNER_RESOLUTION_AND_SETTLEMENT_RUNTIME_NOT_AUTHORIZED",
        "chapter_close_effect=none",
        "OWNER_UNRESOLVED_CANDIDATE",
        "不新增 `slot_status=closed`",
        "离线 validator",
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
        validator.STRUCTURAL_INVALID: 10,
        validator.STRUCTURAL_VALID: 4,
        validator.STRUCTURAL_VALID_OWNER_UNRESOLVED: 4,
    }
    assert result["owner_resolution_performed"] is False
    assert result["network_calls"] == 0
    assert result["model_calls"] == 0
