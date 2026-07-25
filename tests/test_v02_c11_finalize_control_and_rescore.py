from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C11_product_north_star_20260725"
    / "program/v02_c11_finalize_control_and_rescore.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "v02_c11_finalize_control_and_rescore",
        MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.v02
def test_c11_1_freezes_terminal_row_and_preserves_historical_c9(tmp_path):
    module = _load_module()
    historical_before = hashlib.sha256(module.C9_MANIFEST.read_bytes()).hexdigest()
    result = module.write_or_verify(
        tmp_path / "control_mapping",
        tmp_path / "c11",
    )
    mapping = _read(tmp_path / "control_mapping/final_control_mapping.json")
    freeze_receipt = _read(tmp_path / "control_mapping/mapping_freeze_receipt.json")
    rows = {row["atom_id"]: row for row in mapping["rows"]}
    terminal = rows["Z74B-B01-U0033-A09"]

    assert result["status"] == module.CONCLUSION_MISSING
    assert mapping["row_total"] == 49
    assert len(rows) == 49
    assert mapping["source_counts"] == {
        "AI_CONSENSUS": 20,
        "CZ_MANUAL": 1,
        "MECHANICAL_C6_UNIQUE_ROUTE": 17,
        "MECHANICAL_C7_5_SINGLE_CANDIDATE": 11,
    }
    assert terminal["mapping_source"] == "CZ_MANUAL"
    assert terminal["candidate_event_ids"] == ["EV-C0033-43"]
    assert terminal["source_detail"]["cz_row_rejudged"] is False
    assert terminal["source_detail"]["mechanically_derived"] is True
    assert terminal["source_detail"]["revocable"] is True
    assert mapping["conditional_invalidation"] == (module.X04_CONDITIONAL_INVALIDATION)
    assert freeze_receipt["conditional_invalidation"] == (
        module.X04_CONDITIONAL_INVALIDATION
    )
    assert (
        mapping["conditional_invalidation"][
            "current_artifact_remains_unconditional_truth"
        ]
        is False
    )
    assert (
        hashlib.sha256(module.C9_MANIFEST.read_bytes()).hexdigest() == historical_before
    )


@pytest.mark.v02
def test_c11_1_emits_three_reporting_views_without_quality_verdict(tmp_path):
    module = _load_module()
    module.write_or_verify(tmp_path / "control", tmp_path / "c11")
    control_metrics = _read(tmp_path / "control/control_cardinality_metrics.json")
    control_views = _read(tmp_path / "c11/control_coverage_reporting_views.json")
    treatment_views = _read(tmp_path / "c11/treatment_coverage_reporting_views.json")
    first_screen = _read(tmp_path / "c11/first_screen_metrics.json")
    sufficiency = _read(tmp_path / "c11/material_sufficiency.json")
    receipt = _read(tmp_path / "c11/c5_rescore_receipt.json")

    assert control_metrics["mapped_atom_total"] == 40
    assert control_metrics["coverage_rate"] == 40 / 49
    assert control_metrics["atom_split_degree_histogram"] == {"1": 34, "2": 6}
    assert control_metrics["mapped_event_degree_histogram"] == {"1": 30, "2": 8}
    assert control_views["views"]["micro_average"]["fraction"] == "40/49"
    assert control_views["views"]["macro_average"]["display_percent"] == "82.8%"
    assert (
        control_views["views"]["per_chapter_and_range"]["minimum_display_percent"]
        == "56.2%"
    )
    assert treatment_views["views"]["micro_average"]["fraction"] == "25/49"
    assert treatment_views["views"]["macro_average"]["display_percent"] == "52.8%"
    assert first_screen["parent_event_counts"]["control"] == 129
    assert first_screen["parent_event_counts"]["treatment"] == 37
    assert first_screen["causal_attribution_allowed"] is False
    assert first_screen["winner_declaration_allowed"] is False
    assert first_screen["standalone_25_of_49_allowed"] is False
    assert sufficiency["selected_conclusion"] == module.CONCLUSION_MISSING
    assert sufficiency["c8_p0_items_fixed"] is False
    assert receipt["quality_result_registered"] is False
    assert receipt["experiment_a_single_variable_claim_allowed"] is False


@pytest.mark.v02
def test_c11_1_is_deterministic_and_rejects_output_drift(tmp_path):
    module = _load_module()
    control = tmp_path / "control"
    c11 = tmp_path / "c11"
    first = module.write_or_verify(control, c11)
    second = module.write_or_verify(control, c11)
    assert first == second

    target = control / "final_control_mapping.json"
    target.write_text("{}\n", encoding="utf-8")
    with pytest.raises(module.C11FinalizeError, match="既有输出字节漂移"):
        module.write_or_verify(control, c11)
