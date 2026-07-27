from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C12_8_anchor_catalog_load_diagnosis_20260725/program"
)
if str(PROGRAM_DIR) not in sys.path:
    sys.path.insert(0, str(PROGRAM_DIR))

import v02_c12_8_anchor_catalog_load_diagnosis as diagnosis  # noqa: E402


pytestmark = pytest.mark.v02


def _document(artifacts: dict[str, bytes], name: str) -> dict:
    return json.loads(artifacts[name].decode("utf-8"))


def _calls() -> dict[str, dict]:
    ledger = _document(
        diagnosis.build_artifacts(), "historical_call_ledger.json"
    )
    return {row["call_id"]: row for row in ledger["calls"]}


def test_eleven_historical_calls_rebuild_exactly() -> None:
    ledger = _document(
        diagnosis.build_artifacts(), "historical_call_ledger.json"
    )

    assert ledger["call_total"] == 11
    assert {row["case_id"] for row in ledger["calls"]} == {
        "B01-U0033",
        "B02-U0039",
        "B03-U0041",
    }
    assert ledger["model_api_calls"] == ledger["network_requests"] == 0
    assert ledger["quality_result_registered"] is False


def test_input_load_and_output_anchor_count_are_not_conflated() -> None:
    calls = _calls()

    assert calls["C4-B01"]["catalog_entry_count"] == 419
    assert calls["C4-B02"]["catalog_entry_count"] == 113
    assert calls["C4-B03"]["catalog_entry_count"] == 137
    assert calls["C4-B01"]["selected_anchor_reference_count"] == 52
    assert calls["C4-B02"]["selected_anchor_reference_count"] == 25
    assert calls["C4-B03"]["selected_anchor_reference_count"] == 12
    assert all(row["selection_k"] == "K_MISSING" for row in calls.values())
    assert all(
        row["selected_anchor_is_output_metric_not_input_k"] is True
        for row in calls.values()
    )


def test_b01_shorthand_is_split_into_c4_and_c5_rows() -> None:
    artifacts = diagnosis.build_artifacts()
    errata = _document(artifacts, "notion_shorthand_errata.json")
    rows = errata["mixed_b01_shorthand"]["correct_rows"]

    assert [
        (
            row["call_id"],
            row["prompt_tokens"],
            row["selected_anchor_reference_count"],
            row["claim_span_violation_count"],
        )
        for row in rows
    ] == [
        ("C4-B01", 23636, 52, 0),
        ("C5-B01", 23636, 37, 10),
    ]
    assert rows[0]["request_sha256"] == rows[1]["request_sha256"]
    assert errata["old_line_rewritten"] is False


def test_same_contract_replays_keep_both_hypotheses_open() -> None:
    diagnosis_doc = _document(
        diagnosis.build_artifacts(), "dual_hypothesis_diagnosis.json"
    )
    hypotheses = {
        row["hypothesis_id"]: row for row in diagnosis_doc["hypotheses"]
    }

    assert set(hypotheses) == {
        "H1_PROBABILISTIC_INSTABILITY",
        "H2_ANCHOR_CATALOG_LOAD_CLIFF",
    }
    assert {row["status"] for row in hypotheses.values()} == {
        "OPEN_NOT_ADJUDICATED"
    }
    assert diagnosis_doc["curve_fitted"] is False
    assert diagnosis_doc["threshold_declared"] is False
    assert diagnosis_doc["hypothesis_ranked"] is False
    assert diagnosis_doc["c6_4_risk_statement_kept"] is True
    assert "两种解释都仍然可能" in diagnosis_doc["required_conclusion"]


def test_same_request_replay_is_pass_pass_pass_fail_not_a_curve() -> None:
    diagnosis_doc = _document(
        diagnosis.build_artifacts(), "dual_hypothesis_diagnosis.json"
    )
    rows = {
        row["case_id"]: row for row in diagnosis_doc["same_contract_replays"]
    }

    assert all(row["same_request_sha256"] for row in rows.values())
    assert rows["B01-U0033"]["main_result"][
        "claim_span_violation_count"
    ] == 0
    assert rows["B01-U0033"]["repeat_result"][
        "claim_span_violation_count"
    ] == 10
    assert rows["B02-U0039"]["main_result"][
        "claim_span_violation_count"
    ] == 0
    assert rows["B02-U0039"]["repeat_result"][
        "claim_span_violation_count"
    ] == 0
    assert rows["B03-U0041"]["main_result"][
        "claim_span_violation_count"
    ] == 0
    assert rows["B03-U0041"]["repeat_result"][
        "claim_span_violation_count"
    ] == 0


def test_rejected_and_different_contract_rows_keep_metric_boundaries() -> None:
    calls = _calls()

    assert calls["C2-B02"]["claim_span_metric_status"] == (
        "DIAGNOSTIC_ONLY_FROM_REJECTED_FULL_JSON"
    )
    assert calls["C2-B02"]["rejected_response_used_as_quality_result"] is False
    assert calls["C3-B02"]["selected_anchor_reference_count"] is None
    assert calls["C3-B02"]["claim_span_violation_count"] is None
    assert calls["C3-B02"]["claim_span_metric_status"] == (
        "MISSING_TRUNCATED_RESPONSE_NO_SALVAGE"
    )
    for call_id in ("C6-B01", "C6-B02", "C6-B03"):
        assert calls[call_id]["claim_span_violation_count"] is None
        assert calls[call_id]["claim_span_metric_status"] == (
            "NOT_APPLICABLE_DIFFERENT_CONTRACT"
        )


def test_reasoning_share_uses_completion_tokens_as_denominator() -> None:
    calls = _calls()
    row = calls["C4-B02"]

    assert row["reasoning_share_of_completion"] == pytest.approx(
        14696 / 16472
    )
    assert row["reasoning_share_percent_display"] == "89.2181%"


def test_future_experiment_changes_only_k_and_is_not_authorized() -> None:
    shape = _document(
        diagnosis.build_artifacts(),
        "minimum_future_experiment_shape.json",
    )

    assert shape["status"] == "DESIGN_ONLY_NOT_AUTHORIZED_NOT_EXECUTED"
    assert shape["only_changed_variable"] == "input candidate anchor count K"
    assert shape["candidate_sets_nested"] is True
    assert shape["correct_required_anchors_present_at_every_level"] is True
    assert shape["repeated_calls_per_level"] == "CZ_APPROVAL_MISSING"
    assert shape["budget"] == "CZ_APPROVAL_MISSING"
    assert shape["report_raw_results_without_curve_fit"] is True
    assert shape["declare_safe_threshold"] is False
    assert shape["execute_now"] is False


def test_outputs_contain_metrics_and_provenance_but_no_model_payloads() -> None:
    artifacts = diagnosis.build_artifacts()
    forbidden_keys = {"messages", "content", "events", "quote", "chapter_body"}

    for name, raw in artifacts.items():
        if not name.endswith(".json"):
            continue
        document = json.loads(raw)

        def walk(value):
            if isinstance(value, dict):
                assert not (set(value) & forbidden_keys)
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(document)


def test_write_check_is_byte_stable_and_rejects_extra_file(
    tmp_path: Path,
) -> None:
    output = tmp_path / "artifacts"
    first = diagnosis.write_or_verify(output, write=True)
    before = {
        path.name: diagnosis.sha256_file(path)
        for path in output.iterdir()
        if path.is_file()
    }
    second = diagnosis.write_or_verify(output, write=False)
    after = {
        path.name: diagnosis.sha256_file(path)
        for path in output.iterdir()
        if path.is_file()
    }

    assert first == second
    assert before == after
    (output / "smuggled.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(diagnosis.C128Error, match="文件集合不闭合"):
        diagnosis.write_or_verify(output, write=False)


def test_frozen_source_sha_drift_is_rejected(tmp_path: Path) -> None:
    copied = tmp_path / "attempt.jsonl"
    source = diagnosis.CALL_SPECS[0]["attempt_path"]
    shutil.copy2(source, copied)
    copied.write_bytes(copied.read_bytes() + b" ")

    with pytest.raises(diagnosis.C128Error, match="冻结真源 SHA 漂移"):
        diagnosis._verify_source(
            copied,
            diagnosis.CALL_SPECS[0]["attempt_sha256"],
        )


def test_protected_run_and_c13_roots_cannot_be_outputs() -> None:
    with pytest.raises(diagnosis.C128Error, match="输出路径落入冻结根"):
        diagnosis.write_or_verify(diagnosis.C4_RUN / "new-output", write=False)
    with pytest.raises(diagnosis.C128Error, match="输出路径落入冻结根"):
        diagnosis.write_or_verify(
            diagnosis.V02_ROOT
            / "V02_C13_downstream_consumer_20260725/new-output",
            write=False,
        )
