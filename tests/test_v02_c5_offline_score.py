from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c5_offline_score as c5  # noqa: E402


pytestmark = pytest.mark.v02


def test_c5_current_materials_are_missing_not_zero_or_fail(tmp_path: Path) -> None:
    result = c5.write_or_verify(tmp_path / "c5")
    receipt = json.loads(
        (tmp_path / "c5/offline_score_receipt.json").read_text(encoding="utf-8")
    )

    assert result["status"] == c5.CONCLUSION_MISSING
    assert receipt["selected_conclusion"] == c5.CONCLUSION_MISSING
    assert receipt["selected_conclusion"] != c5.CONCLUSION_FAIL
    assert receipt["aggregate"]["ANCHOR_PARTIAL"] == "MISSING_INPUT"
    assert receipt["quality_result_registered"] is False
    assert receipt["mechanical_facts_only"]["c5_scoring_model_calls"] == 0


def test_c5_locks_denominators_and_gate_thresholds(tmp_path: Path) -> None:
    c5.write_or_verify(tmp_path / "c5")
    material = json.loads(
        (tmp_path / "c5/material_sufficiency.json").read_text(encoding="utf-8")
    )

    assert material["denominators_by_case"] == {
        "B01-U0033": 25,
        "B02-U0039": 8,
        "B03-U0041": 16,
    }
    assert material["formal_denominator"] == 49
    criteria = material["gate_contract"]["criteria"]
    assert criteria["relative_reduction_threshold"] == 0.5
    assert criteria["declining_chapter_threshold"] == 2
    assert criteria["sop_threshold"] == 0.98
    assert criteria["no_regression_layers"] == [
        "FCR",
        "QCR_full",
        "ASR_full",
        "UCR",
    ]


def test_c5_records_control_requests_as_not_sent(tmp_path: Path) -> None:
    c5.write_or_verify(tmp_path / "c5")
    material = json.loads(
        (tmp_path / "c5/material_sufficiency.json").read_text(encoding="utf-8")
    )
    control = material["control_evidence"]

    assert control["control_product_kind"] == "REQUESTS_ONLY"
    assert control["control_output_exists"] is False
    assert control["control_semantic_score_exists"] is False
    assert [row["execution_status"] for row in control["requests"]] == [
        "FROZEN_NOT_SENT",
        "FROZEN_NOT_SENT",
        "FROZEN_NOT_SENT",
    ]
    assert all(
        row["request_identity_sha256"] != row["request_file_sha256"]
        for row in control["requests"]
    )


def test_c5_never_emits_gold_text_or_paths(tmp_path: Path) -> None:
    c5.write_or_verify(tmp_path / "c5")
    combined = b"\n".join(
        path.read_bytes()
        for path in sorted((tmp_path / "c5").glob("*.json"))
    )

    assert b"layered_items" not in combined
    assert b"source_quote" not in combined
    assert b"formal_gold/B0" not in combined
    assert b"/Users/a1234/" not in combined
    assert b'"formal_gold_text_emitted": false' in combined


def test_c5_double_run_is_byte_identical_and_tamper_is_rejected(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "c5"
    first = c5.write_or_verify(output_dir)
    before = {
        path.name: path.read_bytes() for path in sorted(output_dir.glob("*.json"))
    }
    second = c5.write_or_verify(output_dir)
    after = {
        path.name: path.read_bytes() for path in sorted(output_dir.glob("*.json"))
    }
    assert first == second
    assert before == after

    (output_dir / "offline_score_receipt.json").write_text(
        "{}\n", encoding="utf-8"
    )
    with pytest.raises(c5.C5ScoreError, match="漂移"):
        c5.write_or_verify(output_dir)


def test_c5_missing_input_never_invokes_numeric_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("缺材料时不准调用旧数值闸")

    monkeypatch.setattr(c5.prep, "evaluate_gate", forbidden)
    c5.write_or_verify(tmp_path / "c5")
    material = json.loads(
        (tmp_path / "c5/material_sufficiency.json").read_text(encoding="utf-8")
    )
    assert material["evaluate_gate_invoked"] is False
