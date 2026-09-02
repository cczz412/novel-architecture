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
MODULE_PATH = CONTRACTS / "validate_chapter_layered_summary.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "chapter_layered_summary", MODULE_PATH
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


def _materialized(case_id: str) -> dict:
    return validator.materialize_fixture_case(_case(case_id))


def test_schema_and_fixture_inventory_are_frozen() -> None:
    assert validator.SCHEMA["title"] == "CHAPTER_LAYERED_SUMMARY v1"
    cases = _cases()
    assert len(cases) == 16
    assert len({row["case_id"] for row in cases}) == len(cases)
    assert validator.validate_all_fixtures() == {
        validator.STRUCTURAL_VALID: 4,
        validator.STRUCTURAL_VALID_OWNER_UNRESOLVED: 3,
        validator.STRUCTURAL_INVALID: 9,
    }


@pytest.mark.parametrize("case", _cases(), ids=lambda row: row["case_id"])
def test_each_fixture_has_the_declared_result(case: dict) -> None:
    assert validator.validate_fixture_case(case) == case["expected_result"]


def test_phase_reads_settlements_and_long_range_may_read_phase_summary() -> None:
    phase = _materialized("CLS-VALID-01")
    assert phase["document"]["summary_kind"] == "PHASE"
    assert all(
        row["input_kind"] == "CHAPTER_SETTLEMENT_SEAL"
        for row in phase["document"]["inputs"]
    )

    long_range = _materialized("CLS-VALID-02")
    assert long_range["document"]["summary_kind"] == "LONG_RANGE"
    assert long_range["document"]["inputs"][0]["input_kind"] == (
        "CHAPTER_LAYERED_SUMMARY"
    )
    assert len(long_range["document"]["leaf_settlement_refs"]) == 3


def test_policy_change_creates_a_new_summary_without_changing_sources() -> None:
    bundle = _materialized("CLS-VALID-01")
    document = bundle["document"]
    changed = copy.deepcopy(document)
    changed["policy"]["policy_version"] = "v2"
    changed["policy"]["policy_sha256"] = validator.policy_sha256(
        changed["policy"]
    )
    changed = validator.seal_document(changed)

    assert changed["summary_sha256"] != document["summary_sha256"]
    assert (
        validator.validate_summary(
            changed,
            bundle["settlements"],
            bundle["summaries"],
        )
        == validator.STRUCTURAL_VALID
    )


def test_every_leaf_and_unresolved_story_item_survives_compression() -> None:
    bundle = _materialized("CLS-VALID-02")
    document = bundle["document"]
    leaf_ids = {
        row["settlement_sha256"]
        for row in document["leaf_settlement_refs"]
    }
    covered = {
        ref
        for section in document["sections"]
        for ref in section["source_leaf_settlement_refs"]
    }
    assert covered == leaf_ids
    assert document["coverage"]["coverage_ratio"] == 1.0
    assert len(document["unresolved_item_refs"]) == len(leaf_ids)


def test_owner_unresolved_propagates_through_long_range_summary() -> None:
    bundle = _materialized("CLS-UNRESOLVED-02")
    document = bundle["document"]
    assert (
        validator.validate_summary(
            document,
            bundle["settlements"],
            bundle["summaries"],
        )
        == validator.STRUCTURAL_VALID_OWNER_UNRESOLVED
    )
    assert document["claim_kind"] == "OWNER_UNRESOLVED_PROJECTION"
    assert document["inputs"][0]["input_claim_kind"] == (
        "OWNER_UNRESOLVED_PROJECTION"
    )


def test_schema_has_no_fixed_chapter_count_or_truth_write_switch() -> None:
    encoded = json.dumps(validator.SCHEMA, ensure_ascii=False)
    assert "chapter_count" not in encoded
    assert validator.SCHEMA["properties"]["projection_only"] == {"const": True}
    assert validator.SCHEMA["properties"]["writes_truth"] == {"const": False}


def test_contract_text_keeps_projection_and_semantic_limits_explicit() -> None:
    text = (CONTRACTS / "CHAPTER_LAYERED_SUMMARY.md").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "CONTRACT_ONLY__SUMMARY_GENERATION_AND_PERSISTENCE_NOT_AUTHORIZED",
        "上一章默认读取完整",
        "projection_only=true",
        "不能判断自由文字是否语义忠实",
        "OWNER_UNRESOLVED_PROJECTION",
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
        validator.STRUCTURAL_INVALID: 9,
        validator.STRUCTURAL_VALID: 4,
        validator.STRUCTURAL_VALID_OWNER_UNRESOLVED: 3,
    }
    assert result["owner_resolution_performed"] is False
    assert result["network_calls"] == 0
    assert result["model_calls"] == 0
