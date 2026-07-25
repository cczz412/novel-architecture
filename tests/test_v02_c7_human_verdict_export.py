from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c7_human_verdict_export as c7  # noqa: E402


pytestmark = pytest.mark.v02


def _built() -> dict[str, bytes]:
    return c7.build_artifacts()


def test_c7_export_is_deterministic_and_zero_call() -> None:
    first = _built()
    second = _built()
    assert first == second
    manifest = json.loads(first["artifact_manifest.json"])
    assert manifest["model_api_calls"] == 0
    assert manifest["network_requests"] == 0


def test_c7_export_has_all_36_blank_rows_in_frozen_order() -> None:
    document = json.loads(_built()["notion_human_verdict_rows.json"])
    assert document["row_total"] == 36
    assert document["case_counts"] == {
        "B01-U0033": 22,
        "B02-U0039": 4,
        "B03-U0041": 10,
    }
    rows = document["rows"]
    assert [row["row_id"] for row in rows] == [
        f"C7-{index:03d}" for index in range(1, 37)
    ]
    assert len({row["atom_id"] for row in rows}) == 36
    assert all(row["cz_verdict"] == "" for row in rows)
    assert all(
        row["choices"][-1]["choice_id"] == c7.NO_CORRESPONDENCE
        for row in rows
    )
    assert document["mapping_freeze_allowed"] is False
    assert document["c5_rescore_allowed"] is False
    assert document["status"] == "WAITING_FOR_CZ_28_VERDICTS_C75_8_AUTO"
    assert document["cz_pending_total"] == 28
    assert document["cz_pending_case_counts"] == {
        "B01-U0033": 14,
        "B02-U0039": 4,
        "B03-U0041": 10,
    }
    assert document["c7_5_mechanical_resolution_total"] == 8


def test_c7_5_resolves_exactly_the_eight_single_candidate_rows() -> None:
    document = json.loads(_built()["notion_human_verdict_rows.json"])
    resolved = [
        row for row in document["rows"] if row["mechanical_resolution"]
    ]
    assert [row["sequence"] for row in resolved] == [
        16,
        21,
        22,
        26,
        27,
        34,
        35,
        36,
    ]
    assert all(row["resolution_source"] == "C7.5" for row in resolved)
    assert all(
        row["mechanical_failure_reason"] == "AMBIGUOUS_ROUTE"
        and len(row["candidate_event_ids"]) == 1
        and row["mechanical_resolution"]
        == f"MAP_TO::{row['candidate_event_ids'][0]}"
        for row in resolved
    )
    pending = [
        row for row in document["rows"] if row["work_status"] == "WAITING_CZ"
    ]
    assert len(pending) == 28
    assert sum(
        row["mechanical_failure_reason"] == "NO_POSITION_ROUTE"
        for row in pending
    ) == 26
    assert [
        row["sequence"]
        for row in pending
        if row["mechanical_failure_reason"] == "AMBIGUOUS_ROUTE"
    ] == [3, 15]


def test_c7_5_cardinality_policy_requires_both_arm_merge_degree() -> None:
    policy = json.loads(
        _built()["c7_5_mapping_cardinality_policy.json"]
    )
    assert policy["multiple_gold_atoms_may_map_to_same_event"] is True
    assert policy["event_occupancy_rule"] == "NO_EXCLUSIVE_OCCUPANCY"
    assert policy["applies_equally_to_arms"] == ["control", "treatment"]
    assert policy["arm_event_counts_for_front_screen"] == {
        "control": 129,
        "treatment": 37,
    }
    assert policy["scoring_atom_set_size"] == 49
    assert policy["same_scoring_atom_set_required_for_both_arms"] is True
    assert policy["same_counter_version_required_for_both_arms"] is True
    assert policy["required_metrics_per_arm"] == [
        "produced_parent_event_total",
        "mapped_atom_total",
        "unmapped_atom_total",
        "coverage_rate",
        "mapped_parent_event_total",
        "mapped_event_degree_histogram",
        "one_to_one_mapped_event_count",
        "many_to_one_mapped_event_count",
        "maximum_atoms_per_mapped_event",
        "by_case_breakdown",
        "event_loads",
    ]
    assert "atom_count_equals_len_atom_ids" in policy["hard_invariants"]
    assert (
        "histogram_weighted_sum_equals_mapped_atom_total"
        in policy["hard_invariants"]
    )
    assert (
        "both_arms_share_scoring_atom_set_and_counter_version"
        in policy["hard_invariants"]
    )
    assert policy["auto_resolution_total"] == 8
    assert policy["cz_pending_total"] == 28
    assert policy["mapping_freeze_allowed"] is False
    assert policy["c5_rescore_allowed"] is False


def test_c7_notion_export_contains_no_gold_text_or_direction_hint() -> None:
    built = _built()
    serialized = (
        built["notion_human_verdict_table.md"]
        + built["notion_human_verdict_rows.json"]
    ).decode("utf-8")
    for forbidden in (
        '"gold_claim"',
        '"quote"',
        '"similarity"',
        '"recommended_choice"',
        '"model_advice"',
    ):
        assert forbidden not in serialized
    audit = json.loads(built["leakage_and_completeness_ticket.json"])
    assert audit["status"] == "PASS"
    assert audit["row_total"] == 36
    assert audit["unique_atom_id_total"] == 36
    assert audit["cz_verdict_blank_total"] == 36
    assert audit["display_result_blank_total"] == 28
    assert audit["c7_5_mechanical_resolution_total"] == 8
    assert audit["cz_pending_total"] == 28
    assert audit["no_correspondence_option_total"] == 36
    assert audit["choice_count_distribution"] == {
        "2": 8,
        "3": 2,
        "11": 10,
        "14": 3,
        "15": 13,
    }
    assert audit["formal_gold_files_read"] == 0
    assert audit["gold_claim_source_field_hit_total"] == 0
    assert audit["gold_quote_source_field_hit_total"] == 0
    assert audit["direction_hint_field_hit_total"] == 0


def test_c7_candidate_lookup_is_objective_and_sha_bound() -> None:
    document = json.loads(_built()["notion_human_verdict_rows.json"])
    for case_id, candidates in document["candidate_catalogs"].items():
        assert case_id in c7.CASE_ORDER
        assert candidates
        for candidate in candidates:
            assert candidate["event_id"]
            assert candidate["event_text"]
            assert candidate["event_text_sha256"] == c7.sha256_bytes(
                candidate["event_text"].encode("utf-8")
            )
            assert candidate["anchor_ids"]
            assert candidate["anchor_ranges"]
            assert [row["anchor_id"] for row in candidate["anchor_ranges"]] == (
                candidate["anchor_ids"]
            )
