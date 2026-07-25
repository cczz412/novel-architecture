from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c7_consensus_workspace as c77  # noqa: E402


pytestmark = pytest.mark.v02


def _built() -> dict[str, bytes]:
    return c77.build_artifacts()


def test_c7_6_7_build_is_deterministic_and_zero_call() -> None:
    first = _built()
    second = _built()
    assert first == second
    manifest = json.loads(first["artifact_manifest.json"])
    assert manifest["model_api_calls"] == 0
    assert manifest["network_requests"] == 0
    assert manifest["mapping_freeze_allowed"] is False
    assert manifest["c5_rescore_allowed"] is False


def test_c7_6_resolves_exactly_two_rows_after_overlap_check() -> None:
    receipt = json.loads(_built()["c7_6_one_to_many_resolution.json"])
    assert receipt["resolution_total"] == 2
    assert receipt["cz_or_ai_pending_total_after_c76"] == 26
    assert [row["sequence"] for row in receipt["resolutions"]] == [3, 15]
    assert receipt["resolutions"][0]["resolved_candidate_event_ids"] == [
        "EV-C0039-05",
        "EV-C0039-06",
    ]
    assert receipt["resolutions"][1]["resolved_candidate_event_ids"] == [
        "EV-C0033-06",
        "EV-C0033-11",
    ]
    assert all(
        row["split_degree"] == 2
        and row["position_overlap_verified"] is True
        and row["overlap_receipts"]
        for row in receipt["resolutions"]
    )


def test_c7_6_split_degree_is_symmetric_and_auditable() -> None:
    policy = json.loads(_built()["c7_6_split_degree_policy.json"])
    assert policy["one_atom_may_map_to_multiple_events"] is True
    assert policy["predecessor_policy"]["retained_rule"] == (
        "multiple_gold_atoms_may_map_to_same_event"
    )
    assert policy["predecessor_policy"]["superseded_hard_invariant"] == (
        "each_atom_maps_to_exactly_one_event_or_no_correspondence"
    )
    assert policy["precedence_rule"] == (
        "C7.6 controls atom-to-event cardinality; "
        "C7.5 continues to control event-to-atom merge degree"
    )
    assert policy["applies_equally_to_arms"] == ["control", "treatment"]
    assert policy["required_metrics_per_arm"] == [
        "mapped_atom_total",
        "unmapped_atom_total",
        "atom_split_degree_histogram",
        "one_event_atom_count",
        "multi_event_atom_count",
        "maximum_events_per_atom",
        "by_case_breakdown",
        "atom_loads",
    ]
    assert "merge_degree" in policy["front_screen_must_show"]
    assert "split_degree" in policy["front_screen_must_show"]
    assert (
        "each_atom_maps_to_one_or_more_unique_events_or_no_correspondence"
        in policy["hard_invariants"]
    )


def test_c7_7_has_26_single_atom_isolation_packets() -> None:
    built = _built()
    manifest = json.loads(built["c7_7_packet_manifest.json"])
    assert manifest["packet_total"] == 26
    assert [row["sequence"] for row in manifest["packets"]] == list(
        c77.C77_EXPECTED_SEQUENCES
    )
    seen_atom_ids: set[str] = set()
    for row in manifest["packets"]:
        packet = json.loads(built[row["packet_path"]])
        assert packet["packet_id"] == row["packet_id"]
        assert packet["atom_id"] == row["atom_id"]
        assert packet["scoring_atom_text"]
        assert packet["atom_id"] not in seen_atom_ids
        seen_atom_ids.add(packet["atom_id"])
        assert list(
            key for key in packet if key == "scoring_atom_text"
        ) == ["scoring_atom_text"]
        assert packet["choices"][-1] == {
            "choice_id": "NO_CORRESPONDENCE",
            "candidate_event_text": None,
        }
        allowed = packet["output_contract"]["selected_choice_ids"][
            "allowed_values"
        ]
        assert allowed == [choice["choice_id"] for choice in packet["choices"]]
        assert packet["output_contract"][
            "no_correspondence_is_exclusive"
        ] is True
        assert packet["adjudication_identity"] == "working_verdict_not_gold"


def test_c7_7_packets_do_not_emit_whole_gold_or_evidence_quotes() -> None:
    built = _built()
    packet_text = "\n".join(
        raw.decode("utf-8")
        for name, raw in built.items()
        if name.startswith("packets/")
    )
    for forbidden in (
        "source_evidence",
        "claim_components",
        "formal_gold",
        "cache_file_path",
        "full_txt_path",
        "review_status",
        "other_model_vote",
        "recommended_choice",
        "API_KEY",
    ):
        assert forbidden not in packet_text
    ticket = json.loads(built["c7_7_leakage_ticket.json"])
    assert ticket == {
        "api_key_hits": 0,
        "formal_gold_paths_in_packets": 0,
        "gold_evidence_quote_fields": 0,
        "model_api_calls": 0,
        "network_requests": 0,
        "other_model_vote_visible_total": 0,
        "other_scoring_atom_texts_per_packet": 0,
        "packet_total": 26,
        "prefilled_vote_total": 0,
        "schema_version": "v02-c7-7-consensus-leakage-ticket.v1",
        "single_scoring_atom_text_per_packet": True,
        "status": "PASS",
    }


def test_c7_7_contract_requires_independent_unanimous_votes() -> None:
    contract = json.loads(_built()["c7_7_consensus_contract.json"])
    assert contract["minimum_independent_model_windows"] == 2
    assert contract["back_to_back_required"] is True
    assert contract["unanimity_required"] is True
    assert contract["only_option_ids_allowed"] is True
    assert contract["multiple_choice_ids_allowed_under_c7_6"] is True
    assert contract["disagreements_route_to"] == "CZ"
    assert contract["mapping_freeze_allowed"] is False
    assert contract["c5_rescore_allowed"] is False
    forbidden = " ".join(contract["forbidden_voters"])
    assert "V4 Flash" in forbidden
    assert "Ling-3.0-flash" in forbidden
