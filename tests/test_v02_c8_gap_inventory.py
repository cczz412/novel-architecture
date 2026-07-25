from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c8_gap_inventory as gap  # noqa: E402


pytestmark = pytest.mark.v02


def _built() -> dict[str, object]:
    return {
        name: (
            json.loads(raw.decode("utf-8"))
            if name.endswith(".json")
            else raw.decode("utf-8")
        )
        for name, raw in gap.build_artifacts().items()
    }


def test_two_p0_conflicts_are_explicitly_blocked() -> None:
    inventory = _built()["gap_inventory.json"]
    assert inventory["status"] == "BLOCKED"
    conflicts = inventory["blocking_conflicts"]
    assert [row["status"] for row in conflicts] == ["BLOCKED", "BLOCKED"]
    assert [row["conflict_id"] for row in conflicts] == [
        "C8-P0-CARDINALITY-CONTRACT",
        "C8-P0-DENOMINATOR-CONTRACT",
    ]
    assert inventory["score_calculation_invoked"] is False
    assert inventory["quality_result_registered"] is False


def test_all_six_semantic_rows_stay_blocked_without_values() -> None:
    inventory = _built()["gap_inventory.json"]
    rows = inventory["gaps"]
    assert [row["layer"] for row in rows] == [
        "ANCHOR_PARTIAL",
        "FCR",
        "QCR_full",
        "ASR_full",
        "UCR",
        "SOP",
    ]
    assert all(row["status"] == "BLOCKED" for row in rows)
    assert inventory["semantic_values_emitted"] is False
    assert inventory["mechanical_routes_counted_as_semantic_hits"] is False
    assert inventory["missing_values_filled_with_zero"] is False
    assert "value" not in json.dumps(rows, ensure_ascii=False)


def test_gap_scale_is_honest_about_minimum_and_unknown_exact_counts() -> None:
    inventory = _built()["gap_inventory.json"]
    scale = inventory["estimated_scale_summary"]
    assert scale["rfu_truth_rows"] == 49
    assert scale["atom_arm_outcome_rows_minimum"] == 98
    assert scale["parent_event_rows_minimum"] == 166
    assert scale["claim_component_and_verdict_rows_exact"] is None
    by_layer = {row["layer"]: row for row in inventory["gaps"]}
    assert by_layer["ANCHOR_PARTIAL"]["estimated_rows"][
        "minimum_atom_arm_outcomes"
    ] == 98
    assert by_layer["ASR_full"]["estimated_rows"][
        "exact_anchor_component_verdict_rows"
    ] is None
    assert by_layer["SOP"]["estimated_rows"]["exact_candidate_claim_rows"] is None


def test_first_screen_never_uses_event_count_as_control_coverage() -> None:
    readiness = _built()["first_screen_readiness.json"]
    assert readiness["status"] == "BLOCKED"
    slots = {row["slot"]: row for row in readiness["slots"]}
    assert slots[1]["value"] == {"control": 129, "treatment": 37}
    assert slots[2]["value"]["treatment"] == {
        "mapped_atom_total": 25,
        "coverage_rate": 25 / 49,
    }
    if slots[2]["status"] != "READY":
        assert slots[2]["value"]["control"] is None
    assert slots[2]["mechanical_route_is_not_semantic_coverage"] is True
    assert readiness["semantic_five_layer_values"] is None
    assert readiness["missing_values_are_not_zero"] is True


def test_n10_n11_stay_blocked_but_bias_audit_is_ready() -> None:
    readiness = _built()["first_screen_readiness.json"]
    slots = {row["slot"]: row for row in readiness["slots"]}
    assert slots[5]["status"] in {"MISSING", "BLOCKED"}
    assert slots[6]["status"] in {"MISSING", "BLOCKED"}
    assert slots[8]["status"] == "READY"
    assert slots[8]["value"] == {
        "matched_total": 6,
        "comparable_total": 6,
        "fraction": "6/6",
        "rate": 1.0,
        "below_5_of_6_risk": False,
    }
    assert slots[6]["diagnostic"]["five_layer_floor_values"] is None
    assert readiness["all_nine_slots_ready"] is False


def test_readme_starts_blocked_and_has_source() -> None:
    readme = _built()["README.md"]
    assert readme.startswith("# BLOCKED：两项 P0 合同冲突未解")
    assert "机械路由冒充语义命中" in readme
    assert readme.endswith("来源：Codex\n")


def test_frozen_input_sha_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        gap.EXPECTED_INPUT_SHAS,
        "c1_offline_score_template",
        "0" * 64,
    )
    with pytest.raises(gap.C8GapInventoryError, match="SHA 漂移"):
        gap.build_artifacts()


def test_double_build_and_write_are_byte_identical(tmp_path: Path) -> None:
    assert gap.build_artifacts() == gap.build_artifacts()
    output = tmp_path / "gap"
    first = gap.write_or_verify(output)
    before = {
        path.name: path.read_bytes() for path in sorted(output.iterdir())
    }
    second = gap.write_or_verify(output)
    after = {
        path.name: path.read_bytes() for path in sorted(output.iterdir())
    }
    assert first == second
    assert before == after
