from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "novel-mvp" / "contracts"
MODULE_PATH = CONTRACTS / "validate_c9_unified_retrieval_run.py"
SCHEMA_PATH = CONTRACTS / "C9_UNIFIED_RETRIEVAL_RUN.schema.json"
CONTRACT_PATH = CONTRACTS / "C9_UNIFIED_RETRIEVAL_RUN.md"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "validate_c9_unified_retrieval_run",
        MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_module()
CASES = validator.load_fixtures()


def test_schema_and_24_case_inventory_are_frozen() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["title"] == "C9 unified retrieval run c9-unified-retrieval-run-v2"
    assert len(CASES) == 24
    assert len({case["case_id"] for case in CASES}) == 24
    assert validator.validate_all_fixtures() == validator.EXPECTED_COUNTS


@pytest.mark.parametrize("case", CASES, ids=lambda row: row["case_id"])
def test_each_fixture_has_the_declared_result(case: dict[str, str]) -> None:
    assert validator.validate_fixture_case(case) == case["expected_result"]


def test_contract_keeps_runtime_truth_and_hypothesis_boundaries_explicit() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    for phrase in (
        "ZERO_API_CORE_AVAILABLE__OWNER_READERS_AND_PRODUCT_ENTRYPOINTS_NOT_CONNECTED",
        "LEDGER_OBJECT",
        "FORMATION_BASIS",
        "ORIGINAL_EVIDENCE",
        "packer.pack_context()",
        "AUDITABLE_CURRENT_NOT_REPLAYABLE",
        "REPLAYABLE_PINNED",
        "PINNED_REQUEST_NOT_REPLAYABLE",
        "source_binding",
        "trigger_provenance",
        "RESULT_NOT_EXACT_SOURCE_RECOMPILE",
        "核心不生成假设",
        "十本账已真实接线",
    ):
        assert phrase in text


def test_cli_reports_exact_counts_and_zero_external_effects() -> None:
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
    assert result["counts"] == validator.EXPECTED_COUNTS
    assert result["owner_readers_invoked"] == 0
    assert result["workspace_writes"] == 0
    assert result["network_calls"] == 0
    assert result["model_calls"] == 0
