from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
C12_1_PROGRAM = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C12_1_cardinality_score_and_c5_rescore_20260725/program"
)
C12_2_PROGRAM = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C12_2_mutation_kill_rate_20260725/program"
)
for path in (TOOLS, C12_1_PROGRAM, C12_2_PROGRAM):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import v02_anchor_first_experiment as anchor  # noqa: E402
import v02_c12_1_cardinality_score_adapter as adapter  # noqa: E402
import v02_c12_2_mutation_kill_rate as harness  # noqa: E402
import v02_c7_consensus_tally as tally  # noqa: E402
from experiments.Z97_rfu_ucr_ledger_20260724.fixtures import (  # noqa: E402
    build_canary_suite,
)


pytestmark = pytest.mark.v02


def _valid_anchor_response(case: Any, catalog: dict[str, Any]) -> dict[str, Any]:
    anchor_id = catalog["entries"][0]["anchor_id"]
    return {
        "schema_version": anchor.CONTRACT_VERSION,
        "chapter": case.unit,
        "events": [
            {
                "event_id": f"EV-C{case.unit:04d}-01",
                "event": "人物明确做出一项安排",
                "minimal_anchor_ids": [anchor_id],
                "support_obligations": [
                    {
                        "claim_span": "做出一项安排",
                        "anchor_ids": [anchor_id],
                        "combination": "all_required",
                    }
                ],
            }
        ],
    }


def test_required_mutation_catalog_has_exact_seven_targets() -> None:
    specs = harness.mutation_specs()
    assert [row.mutant_id for row in specs] == [
        "M01_FAKE_SECOND_MODEL_FAMILY",
        "M02_BYPASS_SEAL_BEFORE_VOTE",
        "M03_MECHANICAL_ROUTE_AS_SEMANTIC_HIT",
        "M04_EXACT_PASTEBACK_TO_SUBSTRING",
        "M05_NOT_FOUND_TO_UNKNOWN",
        "M06_MANIFEST_SMUGGLING",
        "M07_FORCE_LAYER_DENOMINATOR_49",
    ]
    assert len({row.source_path for row in specs}) == 6
    assert all((ROOT / row.source_path).is_file() for row in specs)


def test_anchor_reverse_lookup_requires_full_exact_slice() -> None:
    source = anchor.load_case_source(anchor.CASES[0])
    catalog = anchor.generate_anchor_catalog(
        case_id=source["case"].case_id,
        chapter=source["case"].unit,
        text=source["body"],
    )
    response = _valid_anchor_response(source["case"], catalog)
    weakened = copy.deepcopy(catalog)
    weakened["entries"][0]["quote"] = weakened["entries"][0]["quote"][:-1]

    result = anchor.validate_closed_anchor_alignment(
        response,
        catalog=weakened,
        source_text=source["body"],
    )

    assert result["status"] == "fail"
    assert result["source_reverse_lookup_verified"] is False
    assert any(
        "anchor_reverse_lookup_failed" in error
        for error in result["errors"]
    )


def test_all_five_layer_denominators_remain_dynamic() -> None:
    base = copy.deepcopy(
        next(
            row
            for row in build_canary_suite()["cases"]
            if row["case_id"] == "CANARY-M-01"
        )
    )
    ticket = adapter.compute_many_to_many_score_ticket(
        base["rfus"],
        base["claims"],
        base["verdicts"],
        judge_eligibility=base["judge_eligibility"],
        candidate_universe_complete=True,
    )

    assert ticket["metrics"]["FCR"]["denominator"] == len(base["rfus"])
    assert (
        ticket["metrics"]["QCR_full"]["denominator"]
        == ticket["metrics"]["FCR"]["numerator"]
    )
    assert (
        ticket["metrics"]["ASR_full"]["denominator"]
        == ticket["cardinality"]["selected_edge_total"]
    )
    assert ticket["metrics"]["UCR"]["denominator"] == sum(
        float(row["weight"]) for row in base["rfus"]
    )
    assert ticket["metrics"]["SOP"]["denominator"] == len(base["claims"])
    assert ticket["denominator_contract"] == {
        "FCR": "VALIDATED_RFU_TOTAL",
        "QCR_full": "HEAD_COVERED_UNIQUE_RFU_TOTAL",
        "ASR_full": "SELECTED_POSITIVE_EDGE_TOTAL",
        "UCR": "VALIDATED_RFU_WEIGHT_TOTAL",
        "SOP": "VALIDATED_CANDIDATE_CLAIM_TOTAL",
    }


@pytest.mark.xfail(
    strict=True,
    reason="等待不可伪造的平台署名或外部信任根",
)
def test_forged_second_window_receipt_requires_external_trust_root(
    tmp_path: Path,
) -> None:
    vote_dir = (
        ROOT
        / "experiments/extraction_redesign_v02_overnight_20260725"
        / "V02_C7_6_7_ai_consensus_workspace/votes"
    )
    first_path = vote_dir / "terra_independent_window_1.json"
    notion_path = vote_dir / "notion_independent_window_2.json"
    if not first_path.is_file() or not notion_path.is_file():
        pytest.skip("伪造第二窗口测试的输入前置未满足：本机独立窗口 vote JSON 不在当前工作树")
    first = json.loads(first_path.read_text(encoding="utf-8"))
    notion = json.loads(notion_path.read_text(encoding="utf-8"))
    forged = copy.deepcopy(first)
    forged["voter_id"] = "forged_independent_window_2"
    forged["model_family"] = "notion_platform_assistant"
    forged["independence_receipt"] = notion["independence_receipt"]
    forged_path = tmp_path / "forged_vote.json"
    forged_path.write_text(
        json.dumps(forged, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(tally.C7TallyError):
        tally.tally_votes([first_path, forged_path])
