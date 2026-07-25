from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c7_rescore_c5 as rescore  # noqa: E402


pytestmark = pytest.mark.v02


def _built() -> dict[str, object]:
    return {
        name: json.loads(raw.decode("utf-8"))
        for name, raw in rescore.build_artifacts().items()
    }


def test_rescore_stays_materials_insufficient_not_fail() -> None:
    built = _built()
    receipt = built["c5_rescore_receipt.json"]
    sufficiency = built["material_sufficiency.json"]
    assert receipt["selected_conclusion"] == rescore.CONCLUSION_MISSING
    assert receipt["quality_result_registered"] is False
    assert receipt["evaluate_gate_invoked"] is False
    assert sufficiency["control_mapping_frozen"] is False
    assert sufficiency["treatment_mapping_frozen"] is True
    assert sufficiency["symmetric_49_atom_coverage_available"] is False


def test_first_screen_has_exact_available_metrics_and_missing_control() -> None:
    first = _built()["first_screen_metrics.json"]
    assert first["arm_event_counts"] == {
        "control": 129,
        "treatment": 37,
    }
    assert first["coverage"]["control"]["status"] == (
        rescore.CONTROL_MAPPING_MISSING
    )
    assert first["coverage"]["control"]["coverage_rate"] is None
    assert first["coverage"]["treatment"]["mapped_atom_total"] == 25
    assert first["coverage"]["treatment"]["coverage_rate"] == 25 / 49
    assert first["merge_degree"]["treatment"]["histogram"] == {
        "1": 16,
        "2": 3,
        "3": 2,
    }
    assert first["split_degree"]["treatment"]["histogram"] == {
        "1": 22,
        "2": 3,
    }
    assert first["produced_event_count_not_used_as_coverage"] is True
    assert first["coverage_guard"]["triggered"] is None


def test_control_readiness_uses_same_counter_but_is_not_semantic_mapping() -> None:
    readiness = _built()["control_mapping_readiness.json"]
    assert readiness["same_position_counter_as_treatment_c6"] is True
    assert readiness["mechanical_unique_route_total"] == 17
    assert readiness["semantic_verdict_pending_total"] == 32
    assert readiness["gold_atom_route_status_counts"] == {
        "AMBIGUOUS_ROUTE": 24,
        "MECHANICAL_UNIQUE_ROUTE": 17,
        "NO_POSITION_ROUTE": 8,
    }
    assert readiness["mechanical_route_is_not_semantic_verdict"] is True
    assert readiness["control_mapping_frozen"] is False


def test_gate_is_not_called_with_missing_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("材料不足时不应调用数值过闸器")

    monkeypatch.setattr(rescore.prep, "evaluate_gate", forbidden)
    assert (
        json.loads(
            rescore.build_artifacts()["c5_rescore_receipt.json"].decode(
                "utf-8"
            )
        )["evaluate_gate_invoked"]
        is False
    )


def test_frozen_source_sample_sha_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        rescore.EXPECTED_SAMPLE_SHAS["control"]["B02-U0039"],
        "candidate",
        "0" * 64,
    )
    with pytest.raises(rescore.C5RescoreError, match="SHA 漂移"):
        rescore.build_artifacts()


def test_outputs_do_not_emit_gold_text_or_absolute_paths() -> None:
    combined = b"\n".join(rescore.build_artifacts().values())
    assert b'"claim"' not in combined
    assert b'"quote"' not in combined
    assert b"/Users/a1234/" not in combined
    assert b'"formal_gold_text_emitted": false' in combined


def test_double_build_and_write_are_byte_identical(tmp_path: Path) -> None:
    assert rescore.build_artifacts() == rescore.build_artifacts()
    output = tmp_path / "rescore"
    first = rescore.write_or_verify(output)
    before = {
        path.name: path.read_bytes() for path in sorted(output.glob("*.json"))
    }
    second = rescore.write_or_verify(output)
    after = {
        path.name: path.read_bytes() for path in sorted(output.glob("*.json"))
    }
    assert first == second
    assert before == after
