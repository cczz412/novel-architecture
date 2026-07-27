from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C12_3_reliability_qualification_20260725/program"
)
if str(PROGRAM_DIR) not in sys.path:
    sys.path.insert(0, str(PROGRAM_DIR))

import v02_c12_3_reliability_qualification as reliability  # noqa: E402


pytestmark = pytest.mark.v02


def _synthetic_attempt(
    *,
    logical_id: str,
    attempt: int,
    status: int,
    request_sha: str = "a" * 64,
) -> dict[str, Any]:
    return {
        "logical_request_id": logical_id,
        "attempt": attempt,
        "http_status": status,
        "request_artifact_sha256": request_sha,
        "raw_response_sha256": "b" * 64 if status == 200 else None,
        "usage": (
            {"total_tokens": 100}
            if status == 200
            else {"status": "unknown"}
        ),
    }


def test_real_primary_cohort_exposes_hard_stop_censoring_bias() -> None:
    artifacts = reliability.build_artifacts()
    table = json.loads(
        artifacts["reliability_qualification_table.json"].decode("utf-8")
    )

    assert table["attempts_started"] == 6
    assert table["mechanical_accepts"] == 5
    assert table["mechanical_rejects"] == 1
    assert table["attempt_level_known_mechanical_acceptance_rate"] == {
        "numerator": 5,
        "denominator": 6,
        "value": 5 / 6,
    }
    assert table["condition_level_apparent_acceptance_rate"] == {
        "numerator": 3,
        "denominator": 3,
        "value": 1.0,
    }
    assert table["hard_stop_censoring_bias_percentage_points"] == pytest.approx(
        100 / 6
    )


def test_b01_stop_but_mechanical_reject_stays_in_attempt_denominator() -> None:
    artifacts = reliability.build_artifacts()
    table = json.loads(
        artifacts["reliability_qualification_table.json"].decode("utf-8")
    )
    b01 = next(row for row in table["per_case"] if row["case_id"] == "B01-U0033")

    assert b01["attempts_started"] == 2
    assert b01["mechanical_accepts"] == 1
    assert b01["mechanical_rejects"] == 1
    assert b01["retained_samples"] == 1
    assert b01["attempt_level_known_mechanical_acceptance_rate"]["value"] == 0.5
    assert b01["condition_level_apparent_acceptance_rate"]["value"] == 1.0
    assert b01["hard_stop_censoring_bias_percentage_points"] == 50.0


def test_429_retries_do_not_expand_scientific_attempt_denominator() -> None:
    rows = [
        _synthetic_attempt(logical_id="L1", attempt=1, status=429),
        _synthetic_attempt(logical_id="L1", attempt=2, status=429),
        _synthetic_attempt(logical_id="L1", attempt=3, status=200),
    ]

    collapsed = reliability.collapse_network_attempts(rows)

    assert collapsed["scientific_attempt_started"] is True
    assert collapsed["network_attempt_count"] == 3
    assert collapsed["retry_count"] == 2
    assert collapsed["http_429_count"] == 2
    assert collapsed["logical_request_id"] == "L1"


def test_frozen_plan_without_call_ledger_is_not_a_started_attempt() -> None:
    collapsed = reliability.collapse_network_attempts([])

    assert collapsed["scientific_attempt_started"] is False
    assert collapsed["network_attempt_count"] == 0


def test_stale_c5_plan_cannot_override_three_real_call_ledgers() -> None:
    artifacts = reliability.build_artifacts()
    binding = json.loads(
        artifacts["source_binding_receipt.json"].decode("utf-8")
    )
    ledger = json.loads(artifacts["attempt_ledger.json"].decode("utf-8"))
    c5_rows = [
        row
        for row in ledger["rows"]
        if row["run_id"] == "V02_实验A锚先行倒装_C5稳定性_r04_20260725"
    ]

    assert binding["c5_plan_stale_status"] == "FROZEN_NOT_SENT"
    assert binding["actual_c5_call_ledgers_take_precedence"] is True
    assert len(c5_rows) == 3
    assert all(row["network_attempt_count"] == 1 for row in c5_rows)


@pytest.mark.parametrize(
    ("finish_reason", "mechanical_state", "expected"),
    [
        ("stop", "PASS", "PASS"),
        ("stop", "REJECT_MECHANICAL_CONTRACT", "REJECT"),
        ("length", "UNVERIFIED", "REJECT"),
        (None, "UNVERIFIED", "UNVERIFIED"),
    ],
)
def test_transport_and_mechanical_states_are_not_conflated(
    finish_reason: str | None,
    mechanical_state: str,
    expected: str,
) -> None:
    assert (
        reliability.mechanical_outcome(
            finish_reason=finish_reason,
            mechanical_state=mechanical_state,
        )
        == expected
    )


def test_c2_c3_and_c6_do_not_enter_primary_reliability_rate() -> None:
    artifacts = reliability.build_artifacts()
    ledger = json.loads(artifacts["attempt_ledger.json"].decode("utf-8"))
    table = json.loads(
        artifacts["reliability_qualification_table.json"].decode("utf-8")
    )

    assert len(ledger["rows"]) == 11
    assert table["attempts_started"] == 6
    assert {
        row["comparability"]
        for row in ledger["rows"]
        if row["cohort_id"] != reliability.PRIMARY_COHORT
    } == {
        "NONCOMPARABLE_PROMPT_CONTRACT",
        "NONCOMPARABLE_OUTPUT_LIMIT",
        "NONCOMPARABLE_DIFFERENT_ARM_AND_CONTRACT",
    }


def test_quality_materials_gap_does_not_change_mechanical_outcome() -> None:
    artifacts = reliability.build_artifacts()
    ledger = json.loads(artifacts["attempt_ledger.json"].decode("utf-8"))
    primary = [
        row
        for row in ledger["rows"]
        if row["cohort_id"] == reliability.PRIMARY_COHORT
    ]

    assert all(
        row["quality_scoreability_state"] == reliability.QUALITY_BOUNDARY
        for row in primary
    )
    assert sum(row["attempt_mechanical_outcome"] == "PASS" for row in primary) == 5
    assert all(row["quality_result_registered"] is False for row in primary)


def test_real_historical_inventory_keeps_all_eleven_attempts() -> None:
    artifacts = reliability.build_artifacts()
    history = json.loads(
        artifacts["historical_context_inventory.json"].decode("utf-8")
    )

    assert history["actual_chapter_level_attempts"] == 11
    assert history["network_attempts"] == 11
    assert history["http_200_attempts"] == 11
    assert history["finish_reason_stop"] == 10
    assert history["finish_reason_length"] == 1
    assert history["mechanical_accepts"] == 8
    assert history["mechanical_rejects"] == 3
    assert history["planned_not_started_count"] == 4
    assert history["total_usage_tokens"] == 271008


def test_write_check_is_byte_stable_and_rejects_extra_file(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output"
    report_dir = tmp_path / "report"
    first = reliability.write_or_verify(
        output_dir,
        report_dir,
        write=True,
    )
    second = reliability.write_or_verify(
        output_dir,
        report_dir,
        write=False,
    )

    assert first == second
    (output_dir / "smuggled.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(reliability.C12ReliabilityError, match="输出集合不闭合"):
        reliability.write_or_verify(
            output_dir,
            report_dir,
            write=False,
        )
