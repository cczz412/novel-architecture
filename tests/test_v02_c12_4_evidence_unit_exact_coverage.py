from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C12_4_evidence_unit_exact_coverage_20260725/program"
)
if str(PROGRAM_DIR) not in sys.path:
    sys.path.insert(0, str(PROGRAM_DIR))

import v02_c12_4_evidence_unit_exact_coverage as coverage  # noqa: E402


pytestmark = pytest.mark.v02


def _document(artifacts: dict[str, bytes], name: str) -> dict:
    return json.loads(artifacts[name].decode("utf-8"))


def test_real_old_queues_reduce_only_zero_and_two_rows() -> None:
    summary = _document(
        coverage.build_artifacts(), "semantic_queue_reduction.json"
    )

    assert summary["arms"]["treatment"]["baseline_semantic_verdict_rows"] == 36
    assert summary["arms"]["treatment"]["strict_mechanical_routes"] == 0
    assert summary["arms"]["treatment"]["remaining_semantic_verdict_rows"] == 36
    assert summary["arms"]["control"]["baseline_semantic_verdict_rows"] == 32
    assert summary["arms"]["control"]["strict_mechanical_routes"] == 2
    assert summary["arms"]["control"]["remaining_semantic_verdict_rows"] == 30
    assert summary["combined"]["remaining_semantic_verdict_rows"] == 66
    assert summary["combined"]["target_met"] is False


def test_two_strict_routes_are_exactly_the_expected_control_rows() -> None:
    summary = _document(
        coverage.build_artifacts(), "semantic_queue_reduction.json"
    )

    assert summary["arms"]["control"]["resolved_rows"] == [
        {
            "case_id": "B01-U0033",
            "atom_id": "Z74B-B01-U0033-A10-R02",
            "selected_event_ids": ["EV-C0033-61"],
            "frozen_mapping_agreement": True,
        },
        {
            "case_id": "B01-U0033",
            "atom_id": "Z74B-B01-U0033-A11-R01",
            "selected_event_ids": ["EV-C0033-50"],
            "frozen_mapping_agreement": True,
        },
    ]


def test_multi_event_set_cover_is_detected_but_forbidden() -> None:
    overlay = _document(
        coverage.build_artifacts(), "mechanical_resolution_overlay.json"
    )
    row = next(
        item
        for item in overlay["treatment_rows"]
        if item["atom_id"] == "Z74B-B02-U0039-A06"
    )

    assert row["decision"] == "SEMANTIC_VERDICT_STILL_REQUIRED"
    assert row["selected_event_ids"] == []
    assert row["multi_event_exact_cover_solutions"] == [
        ["EV-C0039-05", "EV-C0039-06"]
    ]
    assert "MULTI_EVENT_SET_COVER_FORBIDDEN" in row["refusal_codes"]


def test_multiple_full_anchor_candidates_cannot_be_selected_by_best_coverage() -> None:
    overlay = _document(
        coverage.build_artifacts(), "mechanical_resolution_overlay.json"
    )
    row = next(
        item
        for item in overlay["control_rows"]
        if item["atom_id"] == "Z74B-B01-U0033-A09"
    )

    assert set(row["full_anchor_cover_event_ids"]) == {
        "EV-C0033-42",
        "EV-C0033-43",
    }
    assert row["decision"] == "SEMANTIC_VERDICT_STILL_REQUIRED"
    assert "ROW_MULTIPLE_FULL_COVERAGE_CANDIDATES" in row["refusal_codes"]


def test_reverse_lookup_rejects_quote_or_coordinate_drift() -> None:
    body = "甲说：不能走。乙回答：可以。"
    good = {
        "anchor_id": "Q1",
        "quote": "不能走",
        "cache_body_start_char": 3,
        "cache_body_end_char_exclusive": 6,
    }

    assert coverage.reverse_lookup_evidence_unit(
        body=body, row=good, identity="GOOD"
    )["quote_sha256"]
    bad_quote = {**good, "quote": "不能跑"}
    with pytest.raises(
        coverage.C12EvidenceUnitError,
        match="EVIDENCE_REVERSE_LOOKUP_FAILED",
    ):
        coverage.reverse_lookup_evidence_unit(
            body=body, row=bad_quote, identity="BAD_QUOTE"
        )
    bad_coordinate = {
        **good,
        "cache_body_start_char": 4,
        "cache_body_end_char_exclusive": 7,
    }
    with pytest.raises(
        coverage.C12EvidenceUnitError,
        match="EVIDENCE_REVERSE_LOOKUP_FAILED",
    ):
        coverage.reverse_lookup_evidence_unit(
            body=body, row=bad_coordinate, identity="BAD_COORD"
        )


def test_coordinate_relations_use_exact_positions_not_repeated_text() -> None:
    evidence = [{"start": 2, "end": 8}]

    assert coverage.coordinate_relation(
        [{"start": 2, "end": 8}], evidence
    ) == "EXACT"
    assert coverage.coordinate_relation(
        [{"start": 1, "end": 9}], evidence
    ) == "CONTAINS"
    assert coverage.coordinate_relation(
        [{"start": 3, "end": 7}], evidence
    ) == "CONTAINED_BY"
    assert coverage.coordinate_relation(
        [{"start": 7, "end": 10}], evidence
    ) == "PARTIAL"
    assert coverage.coordinate_relation(
        [{"start": 8, "end": 14}], evidence
    ) == "DISJOINT"


def test_mechanical_routes_never_emit_semantic_or_five_layer_scores() -> None:
    artifacts = coverage.build_artifacts()
    overlay = _document(artifacts, "mechanical_resolution_overlay.json")
    audit = _document(artifacts, "frozen_mapping_audit.json")

    for row in overlay["treatment_rows"] + overlay["control_rows"]:
        assert row["mapping_identity"] == "working_route_not_semantic_verdict"
        assert row["semantic_support_verified"] is False
        assert row["quality_score_eligible"] is False
        assert set(row["semantic_fields"].values()) == {None}
    assert audit["treatment"][
        "mechanical_rows_semantic_score_admission_allowed"
    ] is False
    assert audit["control"][
        "mechanical_rows_semantic_score_admission_allowed"
    ] is False
    assert audit["semantic_score_edges_emitted"] == 0


def test_build_is_read_only_for_all_frozen_top_level_inputs() -> None:
    before = {
        path: coverage.sha256_file(path)
        for path in coverage.EXPECTED_FROZEN_SHA256
    }
    coverage.build_artifacts()
    after = {
        path: coverage.sha256_file(path)
        for path in coverage.EXPECTED_FROZEN_SHA256
    }

    assert before == after == coverage.EXPECTED_FROZEN_SHA256


def test_write_check_is_byte_stable_and_rejects_extra_file(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output"
    report_dir = tmp_path / "report"
    first = coverage.write_or_verify(
        output_dir,
        report_dir,
        write=True,
    )
    second = coverage.write_or_verify(
        output_dir,
        report_dir,
        write=False,
    )

    assert first == second
    (output_dir / "smuggled.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        coverage.C12EvidenceUnitError,
        match="输出集合不闭合",
    ):
        coverage.write_or_verify(
            output_dir,
            report_dir,
            write=False,
        )


def test_protected_roots_cannot_be_used_as_output() -> None:
    with pytest.raises(
        coverage.C12EvidenceUnitError,
        match="输出路径落入冻结根",
    ):
        coverage.write_or_verify(
            coverage.C7_DIR,
            coverage.REPORT_DIR,
            write=False,
        )
