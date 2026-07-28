from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from experiments.V02_R2_development_hardening_r01_20260727 import (
    qec_psr_experiment_runner as runner,
    qec_psr_sidecar as psr,
)


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "runs/V02_R2_M1_02_final_semantic_r01_20260727"
CONTRACT_PATH = RUN_DIR / "preregistered/qec_psr_experiment_contract.json"
CONTRACT_SHA256 = "1e95e26a2307be6957d2e910cee1be023cafd62bbe76615f8a73fcbdc405b4f9"


@pytest.fixture(scope="module")
def prepared() -> tuple[dict, dict, dict]:
    contract = runner.load_contract(
        contract_path=CONTRACT_PATH,
        expected_contract_sha256=CONTRACT_SHA256,
    )
    baseline, paths = runner.verify_frozen_public_baseline(
        repo=REPO, contract=contract
    )
    gate, artifacts = runner.build_pre_score_artifacts(
        repo=REPO,
        contract=contract,
        baseline=baseline,
        paths=paths,
    )
    return contract, gate, artifacts


def test_contract_is_frozen_before_candidate_and_rule_copy_is_exact() -> None:
    contract = runner.load_contract(
        contract_path=CONTRACT_PATH,
        expected_contract_sha256=CONTRACT_SHA256,
    )
    assert contract["contract_status"] == "FROZEN_BEFORE_CANDIDATE_IMPLEMENTATION"
    assert (
        contract["primary_score_decision_order"]
        == contract["scoring_policy"]["ordered_stop_rules"]
    )
    assert contract["model_api_calls_allowed"] == 0
    assert contract["network_calls_allowed"] == 0


def test_prepare_interface_cannot_receive_hidden_development_file() -> None:
    parameters = inspect.signature(runner.prepare_run).parameters
    assert "hidden_cells_path" not in parameters
    assert "hidden_cells" not in parameters


def test_two_public_generations_are_identical_and_match_reference(
    prepared: tuple[dict, dict, dict],
) -> None:
    _, gate, artifacts = prepared
    assert gate["status"] == "PASS"
    assert gate["candidate_generation"]["generation_count"] == 2
    assert gate["candidate_generation"]["byte_identical"] is True
    assert gate["independent_reference_check"]["projection_byte_identical"] is True
    assert artifacts["protection_trace"]["eligible_cell_count"] == 3
    assert artifacts["protection_trace"]["protected_plan_unit_record_count"] == 6


def test_noneligible_and_frozen_non_regression_cases_stay_exact(
    prepared: tuple[dict, dict, dict],
) -> None:
    contract, gate, artifacts = prepared
    assert gate["independent_reference_check"][
        "non_regression_cell_count_equal_control"
    ] == contract["reference_freeze"]["expected_non_regression_cell_count"]
    reference = json.loads(
        (
            RUN_DIR / "preregistered/qec_psr_reference_eligibility.json"
        ).read_text(encoding="utf-8")
    )
    controls = json.loads(
        (
            REPO
            / contract["control_route"]["run_directory"]
            / "route_assets/selection_projections/QEC/2500.json"
        ).read_text(encoding="utf-8")
    )
    control_by_id = {row["cell_id"]: row for row in controls["cells"]}
    candidate_by_id = {
        row["cell_id"]: row
        for row in artifacts["selection_projection"]["cells"]
    }
    for row in reference["cells"]:
        if not row["eligible"]:
            assert candidate_by_id[row["cell_id"]] == control_by_id[row["cell_id"]]


def test_candidate_stays_within_budget_and_residual_fill_is_maximal(
    prepared: tuple[dict, dict, dict],
) -> None:
    contract, gate, artifacts = prepared
    assert gate["public_output_check"]["all_cells_within_budget"] is True
    assert gate["residual_fill_maximal"] is True
    assert all(
        cell["candidate_chars"] <= contract["primary_budget_chars"]
        for cell in artifacts["sealed_output"]["cells"]
    )
    assert all(
        row["residual_fit_remaining_count"] == 0
        for row in artifacts["protection_trace"]["cells"]
    )


def test_production_sources_contain_no_frozen_business_identifier(
    prepared: tuple[dict, dict, dict],
) -> None:
    _, gate, _ = prepared
    result = gate["candidate_program"]["business_id_literal_scan"]
    assert result["status"] == "PASS"
    assert result["hit_count"] == 0


def test_pre_score_gate_records_zero_hidden_score_api_and_network(
    prepared: tuple[dict, dict, dict],
) -> None:
    _, gate, _ = prepared
    assert gate["hidden_development_file_opened"] is False
    assert gate["terminal_question_or_gold_opened"] is False
    assert gate["scorer_imported_before_gate"] is False
    assert gate["scorer_calls_before_gate"] == 0
    assert gate["model_api_calls"] == 0
    assert gate["network_calls"] == 0


def test_sidecar_has_no_filesystem_or_scoring_parameter() -> None:
    parameters = inspect.signature(psr.build_candidate).parameters
    assert "repo" not in parameters
    assert "run_dir" not in parameters
    assert "hidden_cells" not in parameters
    assert "score" not in parameters
