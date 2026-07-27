from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C12_1_cardinality_score_and_c5_rescore_20260725"
    / "program"
)
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

import v02_c12_1_cardinality_score_adapter as adapter  # noqa: E402

from experiments.Z97_rfu_ucr_ledger_20260724.fixtures import (  # noqa: E402
    build_canary_suite,
)


pytestmark = pytest.mark.v02


def _base() -> dict[str, Any]:
    suite = build_canary_suite()
    return copy.deepcopy(
        next(row for row in suite["cases"] if row["case_id"] == "CANARY-M-01")
    )


def _graph(
    rfu_ids: list[str],
    claim_ids: list[str],
    pairs: list[tuple[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    base = _base()
    rfu_template = base["rfus"][0]
    claim_template = base["claims"][0]
    verdict_template = base["verdicts"][0]

    rfus = []
    for index, rfu_id in enumerate(rfu_ids, 1):
        row = copy.deepcopy(rfu_template)
        row["rfu_id"] = rfu_id
        row["source_order"] = index
        rfus.append(row)

    claims = []
    components = {}
    for index, claim_id in enumerate(claim_ids, 1):
        row = copy.deepcopy(claim_template)
        row["claim_id"] = claim_id
        row["event_id"] = f"EVENT-{index}"
        component_id = f"{claim_id}-COMP"
        row["claim_components"][0]["component_id"] = component_id
        components[claim_id] = component_id
        claims.append(row)

    verdicts = []
    for rfu_id, claim_id in pairs:
        row = copy.deepcopy(verdict_template)
        row["rfu_id"] = rfu_id
        row["claim_id"] = claim_id
        row["head_match"] = "yes"
        row["atomicity"] = "atomic"
        row["reason_codes"] = []
        row["anchor_component_results"] = [
            {
                "component_id": components[claim_id],
                "status": "supported",
            }
        ]
        verdicts.append(row)
    return rfus, claims, verdicts


def _ticket(
    rfu_ids: list[str],
    claim_ids: list[str],
    pairs: list[tuple[str, str]],
) -> dict[str, Any]:
    rfus, claims, verdicts = _graph(rfu_ids, claim_ids, pairs)
    eligibility = _base()["judge_eligibility"]
    return adapter.compute_many_to_many_score_ticket(
        rfus,
        claims,
        verdicts,
        judge_eligibility=eligibility,
        candidate_universe_complete=True,
    )


def test_n_to_one_keeps_both_rfu_edges() -> None:
    ticket = _ticket(["R1", "R2"], ["C1"], [("R1", "C1"), ("R2", "C1")])
    assert {
        (row["rfu_id"], row["claim_id"]) for row in ticket["selected_matches"]
    } == {("R1", "C1"), ("R2", "C1")}
    assert ticket["cardinality"]["selected_edge_total"] == 2
    assert ticket["cardinality"]["matched_rfu_total"] == 2
    assert ticket["cardinality"]["matched_claim_total"] == 1
    assert ticket["cardinality"]["maximum_rfus_per_claim"] == 2
    assert ticket["metrics"]["FCR"]["numerator"] == 2
    assert ticket["metrics"]["SOP"]["numerator"] == 1


def test_one_to_n_keeps_both_claim_edges_without_double_counting_rfu() -> None:
    ticket = _ticket(["R1"], ["C1", "C2"], [("R1", "C1"), ("R1", "C2")])
    assert ticket["cardinality"]["selected_edge_total"] == 2
    assert ticket["cardinality"]["matched_rfu_total"] == 1
    assert ticket["cardinality"]["matched_claim_total"] == 2
    assert ticket["cardinality"]["maximum_claims_per_rfu"] == 2
    assert ticket["metrics"]["FCR"] == {
        "numerator": 1,
        "denominator": 1,
        "value": 1,
    }
    assert ticket["metrics"]["UCR"] == {
        "numerator": 1.0,
        "denominator": 1.0,
        "value": 1.0,
    }
    assert ticket["metrics"]["ASR_full"]["denominator"] == 2


def test_many_to_many_cross_keeps_all_edges_and_is_order_stable() -> None:
    pairs = [
        ("R1", "C1"),
        ("R1", "C2"),
        ("R2", "C1"),
        ("R2", "C2"),
    ]
    rfus, claims, verdicts = _graph(["R1", "R2"], ["C1", "C2"], pairs)
    eligibility = _base()["judge_eligibility"]
    first = adapter.compute_many_to_many_score_ticket(
        rfus,
        claims,
        verdicts,
        judge_eligibility=eligibility,
        candidate_universe_complete=True,
    )
    second = adapter.compute_many_to_many_score_ticket(
        list(reversed(rfus)),
        list(reversed(claims)),
        list(reversed(verdicts)),
        judge_eligibility=eligibility,
        candidate_universe_complete=True,
    )
    assert first == second
    assert first["cardinality"] == {
        "selected_edge_total": 4,
        "matched_rfu_total": 2,
        "matched_claim_total": 2,
        "rfu_degree_histogram": {"2": 2},
        "claim_degree_histogram": {"2": 2},
        "maximum_claims_per_rfu": 2,
        "maximum_rfus_per_claim": 2,
    }
    assert len(first["selected_matches"]) == 4


def test_unmatched_claim_is_not_reported_as_matched() -> None:
    ticket = _ticket(["R1"], ["C1", "C2"], [("R1", "C1")])
    assert ticket["cardinality"]["matched_claim_total"] == 1
    assert ticket["cardinality"]["claim_degree_histogram"] == {"1": 1}
    assert ticket["unmatched_claim_ids"] == ["C2"]
    assert ticket["metrics"]["SOP"] == {
        "numerator": 1,
        "denominator": 2,
        "value": 0.5,
        "candidate_universe_complete": True,
        "threshold_met": False,
    }


def test_c12_artifacts_clear_two_engineering_p0_without_faking_scores() -> None:
    built = {
        name: (
            json.loads(raw.decode("utf-8"))
            if name.endswith(".json")
            else raw.decode("utf-8")
        )
        for name, raw in adapter.build_artifacts().items()
    }
    receipt = built["c5_rescore_receipt.json"]
    crosswalk = built["five_layer_denominator_crosswalk.json"]
    assert receipt["cleared_engineering_items"] == [
        "C8-P0-CARDINALITY-CONTRACT",
        "C8-P0-DENOMINATOR-CONTRACT",
    ]
    assert receipt["selected_conclusion"] == adapter.CONCLUSION_MISSING
    assert receipt["evaluate_gate_invoked"] is False
    assert receipt["quality_result_registered"] is False
    assert crosswalk["c1_reference_scoring_atom_total"] == 49
    assert crosswalk["c5_directly_scoreable_layers"] == []
    assert all(row["c5_current_denominator"] is None for row in crosswalk["rows"])
    assert crosswalk["different_denominator_units_may_be_added_or_averaged"] is False


def test_c12_double_build_is_byte_identical_and_emits_no_gold_text() -> None:
    first = adapter.build_artifacts()
    second = adapter.build_artifacts()
    assert first == second
    combined = b"\n".join(first.values())
    assert b"/Users/a1234/" not in combined
    assert b'"claim"' not in combined
    assert b'"quote"' not in combined
    assert b'"model_api_calls": 0' in combined


def test_check_mode_does_not_create_missing_report_directory(tmp_path) -> None:
    output_dir = tmp_path / "output"
    report_dir = tmp_path / "report"
    adapter.write_or_verify(output_dir, report_dir, write=True)
    shutil.rmtree(report_dir)

    with pytest.raises(adapter.C12CardinalityError):
        adapter.write_or_verify(output_dir, report_dir, write=False)

    assert not report_dir.exists()
