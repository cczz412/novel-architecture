from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.Z96_anchor_layer_evidence_closure_20260724.anchor_evidence_candidate import (
    Z96CandidateError,
    aligned_anchor_rows,
    build_evidence_closure_packet,
    build_lightweight_chapter_map,
    catalog_entries,
    derive_minimal_anchor_sets,
    endpoint_span_pattern,
    evaluate_anchor_set,
    evaluate_fixture_replay,
    render_reverse_check,
    topology_candidate_ids,
)
from experiments.Z96_anchor_layer_evidence_closure_20260724.generate_replay import build


def _fixture() -> tuple[str, list[dict[str, object]], list[dict[str, object]]]:
    text = "甲先说明条件。乙据此采取行动。事情最终成功。远处另有一条来源。"
    entries: list[dict[str, object]] = [
        {"anchor_id": "E0001", "chapter": 0, "quote": "甲先说明条件。"},
        {"anchor_id": "E0002", "chapter": 0, "quote": "乙据此采取行动。"},
        {"anchor_id": "E0003", "chapter": 0, "quote": "事情最终成功。"},
        {"anchor_id": "E0004", "chapter": 0, "quote": "远处另有一条来源。"},
    ]
    return text, entries, aligned_anchor_rows(text, entries)


def test_canary_a01_half_sentence_is_rejected() -> None:
    _, _, aligned = _fixture()
    result = evaluate_fixture_replay(
        case_id="CANARY-A-01",
        aligned=aligned,
        selected_anchor_ids=["E0001"],
        necessary_anchor_ids=["E0001", "E0002"],
    )
    assert result["input_gate"]["ASR_full"] is False
    assert result["input_gate"]["decision"] == "REJECT"


def test_canary_a02_endpoint_only_is_hard_rejected() -> None:
    _, _, aligned = _fixture()
    result = evaluate_fixture_replay(
        case_id="CANARY-A-02",
        aligned=aligned,
        selected_anchor_ids=["E0001", "E0003"],
        necessary_anchor_ids=["E0001", "E0002", "E0003"],
    )
    assert result["endpoint_span_pattern"] is True
    assert result["input_gate"]["ASR_full"] is False
    assert result["input_gate"]["decision"] == "REJECT"


def test_endpoint_uses_source_order_not_anchor_id_range() -> None:
    _, _, aligned = _fixture()
    assert endpoint_span_pattern(
        aligned=aligned,
        selected_anchor_ids=["E0001", "E0003"],
        necessary_anchor_ids=["E0001", "E0002", "E0003"],
    )
    assert not endpoint_span_pattern(
        aligned=aligned,
        selected_anchor_ids=["E0001", "E0002"],
        necessary_anchor_ids=["E0001", "E0002"],
    )


def test_noncontiguous_span_seed_does_not_fill_long_gap() -> None:
    text = "".join(f"第{index}段。" for index in range(1, 13))
    entries = [
        {
            "anchor_id": f"E{index:04d}",
            "chapter": 0,
            "quote": f"第{index}段。",
        }
        for index in range(1, 13)
    ]
    aligned = aligned_anchor_rows(text, entries)
    result = topology_candidate_ids(aligned, ["E0001", "E0012"], max_hops=2)
    assert result == ["E0001", "E0002", "E0003", "E0010", "E0011", "E0012"]


def test_minimal_complete_anchor_set_is_deterministic() -> None:
    claims = [
        {"claim_id": "C1", "sufficient_support_groups": [["E0001"], ["E0002"]]},
        {"claim_id": "C2", "sufficient_support_groups": [["E0002", "E0003"]]},
    ]
    result = derive_minimal_anchor_sets(claims, ["E0001", "E0002", "E0003"])
    assert result["minimum_size"] == 2
    assert result["primary"] == ["E0002", "E0003"]
    assert evaluate_anchor_set(claims, result["primary"])["ASR_full"]


def test_render_reverse_check_rejects_added_claim() -> None:
    result = render_reverse_check(["C1"], ["C1", "C2"])
    assert result["decision"] == "REJECT"
    assert result["new_claim_ids"] == ["C2"]


def test_closure_keeps_fixture_truth_outside_model_visible() -> None:
    text, entries, aligned = _fixture()
    chapter_map = build_lightweight_chapter_map(text, aligned)
    packet = build_evidence_closure_packet(
        case_id="CASE-01",
        event_text="甲说明条件后乙行动。",
        chapter_map=chapter_map,
        aligned=aligned,
        seed_anchor_ids=["E0001", "E0003"],
        necessary_anchor_ids_for_fixture=["E0001", "E0002", "E0003"],
    )
    visible = json.dumps(packet["model_visible"], ensure_ascii=False)
    assert "necessary_anchor_ids" not in visible
    assert packet["offline_evaluation"]["necessary_span_recall"] == 1.0


def test_closure_allows_one_enumerated_controlled_expansion() -> None:
    text, _, aligned = _fixture()
    chapter_map = build_lightweight_chapter_map(text, aligned)
    packet = build_evidence_closure_packet(
        case_id="CASE-EXPAND",
        event_text="甲说明条件，远处另有来源。",
        chapter_map=chapter_map,
        aligned=aligned,
        seed_anchor_ids=["E0001"],
        controlled_expansion_reason="SOURCE_SPAN_OUTSIDE_INITIAL_CLOSURE",
        controlled_expansion_seed_anchor_ids=["E0004"],
    )
    assert packet["metrics"]["controlled_expansion_count"] == 1
    assert {
        row["anchor_id"] for row in packet["model_visible"]["evidence_spans"]
    } == {"E0001", "E0002", "E0003", "E0004"}


def test_catalog_shape_is_validated() -> None:
    with pytest.raises(Z96CandidateError):
        catalog_entries({"entries": [{"anchor_id": "BAD", "quote": "文字"}]})


def test_full_generator_is_zero_call_and_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "z96"
    build(output)
    summary = json.loads((output / "09_validation_summary.json").read_text(encoding="utf-8"))
    closure = json.loads((output / "07_evidence_closure_ledger.json").read_text(encoding="utf-8"))
    x04 = json.loads((output / "03_x04_85_disposition_ledger.json").read_text(encoding="utf-8"))
    assert summary["status"] == "PASS"
    assert summary["usage"]["model_api_network_attempts"] == 0
    assert closure["metrics"]["necessary_span_recall"] == 1.0
    assert closure["metrics"]["input_token_proxy_median"] <= 2500
    assert closure["metrics"]["input_token_proxy_p95_nearest_rank"] <= 4000
    assert x04["summary"]["rows"] == 85
    assert x04["summary"]["unresolved"] == 0
    with pytest.raises(Z96CandidateError):
        build(output)
