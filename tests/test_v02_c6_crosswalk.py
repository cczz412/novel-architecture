from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c6_crosswalk as c6  # noqa: E402


def _built() -> dict[str, object]:
    return {
        name: json.loads(raw.decode("utf-8"))
        for name, raw in c6.build_crosswalk().items()
    }


def test_c6_crosswalk_is_deterministic_and_zero_call() -> None:
    first = c6.build_crosswalk()
    second = c6.build_crosswalk()
    assert first == second
    manifest = json.loads(first["artifact_manifest.json"])
    assert manifest["model_api_calls"] == 0
    assert manifest["network_requests"] == 0


def test_c6_crosswalk_counts_and_gate_are_hard_stopped() -> None:
    built = _built()
    crosswalk = built["mechanical_crosswalk_partial.json"]
    assert crosswalk["counts"] == {
        "candidate_event_total": 37,
        "candidate_obligation_total": 49,
        "formal_gold_atom_total": 49,
        "event_unique_route_total": 13,
        "obligation_unique_route_total": 11,
        "pending_gold_atom_total_event_graph": 36,
    }
    assert crosswalk["formal_mapping_frozen"] is False
    assert crosswalk["c5_scoring_allowed"] is False
    assert crosswalk["mechanical_route_is_not_semantic_verdict"] is True
    gate = built["mapping_gate.json"]
    assert gate["status"] == "HARD_STOP_PENDING_CZ_MAPPING_VERDICTS"
    assert gate["c5_rescore_allowed"] is False
    assert gate["ling_l1_allowed_before_c6_closure"] is False


def test_c6_human_queue_has_required_choices_without_gold_text() -> None:
    built = _built()
    queue = built["human_verdict_queue.json"]
    assert queue["row_total"] == 36
    for row in queue["rows"]:
        assert row["atom_id"]
        assert row["candidate_file_sha256"]
        assert row["formal_gold_sha256"]
        assert row["mechanical_failure_reason"] in {
            c6.ROUTE_AMBIGUOUS,
            c6.ROUTE_NONE,
        }
        assert row["choices"][-1]["choice_id"] == "NO_CORRESPONDENCE"
        assert "claim" not in row
        assert "quote" not in row
    serialized = json.dumps(queue, ensure_ascii=False)
    assert '"gold_claim":' not in serialized
    assert '"quote":' not in serialized


def test_c6_mechanical_routes_use_only_position_and_frozen_identity() -> None:
    crosswalk = _built()["mechanical_crosswalk_partial.json"]
    algorithm = crosswalk["algorithm"]
    assert algorithm["minimum_exact_overlap_nonspace_characters"] == 6
    assert algorithm["unique_rule"] == "candidate_degree==1 AND gold_degree==1"
    assert algorithm["forbidden_matching_methods"] == [
        "text_similarity",
        "person_name",
        "ordinal_guess",
        "llm_judgment",
        "greedy_merge",
    ]
    assert all(
        row["mechanical_route_is_not_semantic_verdict"] is True
        for row in crosswalk["frozen_event_unique_routes"]
    )
    assert all(
        row["mechanical_route_is_not_semantic_verdict"] is True
        for row in crosswalk["frozen_obligation_unique_routes"]
    )
