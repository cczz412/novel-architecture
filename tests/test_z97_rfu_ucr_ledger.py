from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.Z97_rfu_ucr_ledger_20260724 import pipeline
from experiments.Z97_rfu_ucr_ledger_20260724.core import (
    Z97ContractError,
    compute_edge_weight,
    compute_score_ticket,
    evaluate_canary_suite,
    select_max_weight_matches,
    sha256_bytes,
    stable_json_bytes,
    validate_judge_eligibility,
    validate_rfu,
)
from experiments.Z97_rfu_ucr_ledger_20260724.fixtures import build_canary_suite


def _case(case_id: str) -> dict[str, object]:
    suite = build_canary_suite()
    return copy.deepcopy(
        next(row for row in suite["cases"] if row["case_id"] == case_id)
    )


def test_stable_json_bytes_and_sha_are_deterministic() -> None:
    left = {"乙": 2, "甲": [1, 2]}
    right = {"甲": [1, 2], "乙": 2}
    assert stable_json_bytes(left) == stable_json_bytes(right)
    assert sha256_bytes(stable_json_bytes(left)) == sha256_bytes(
        stable_json_bytes(right)
    )


def test_eight_canaries_all_hit_prewritten_results() -> None:
    receipt = evaluate_canary_suite(build_canary_suite())
    assert receipt["status"] == "PASS"
    assert receipt["case_count"] == 8
    assert [row["case_id"] for row in receipt["cases"]] == [
        "CANARY-Q-01",
        "CANARY-Q-02",
        "CANARY-Q-03",
        "CANARY-A-01",
        "CANARY-A-02",
        "CANARY-M-01",
        "CANARY-F-01",
        "CANARY-F-02",
    ]


def test_zero_required_qualifiers_count_as_qcr_pass() -> None:
    case = _case("CANARY-M-01")
    verdict = case["verdicts"][0]
    verdict["atomicity"] = "atomic"
    verdict["reason_codes"] = []
    ticket = compute_score_ticket(
        case["rfus"],
        case["claims"],
        case["verdicts"],
        judge_eligibility=case["judge_eligibility"],
        candidate_universe_complete=True,
    )
    assert ticket["metrics"]["FCR"]["value"] == 1
    assert ticket["metrics"]["QCR_full"] == {
        "numerator": 1,
        "denominator": 1,
        "value": 1,
    }
    assert ticket["metrics"]["UCR"]["value"] == 1


def test_edge_weight_uses_fixed_formula_and_hard_contradictions() -> None:
    case = _case("CANARY-Q-01")
    verdict = case["verdicts"][0]
    verdict["qualifier_results"] = [
        {"qualifier_id": "Q1", "status": "present"},
        {"qualifier_id": "Q2", "status": "missing"},
    ]
    verdict["anchor_component_results"] = [
        {"component_id": "C1", "status": "supported"},
        {"component_id": "C2", "status": "partial"},
    ]
    assert compute_edge_weight(verdict) == 65
    verdict["head_match"] = "no"
    assert compute_edge_weight(verdict) == -100
    verdict["head_match"] = "contradiction"
    assert compute_edge_weight(verdict) == -1000


def test_max_weight_matching_is_global_not_row_greedy() -> None:
    base = _case("CANARY-M-01")
    rfu1 = base["rfus"][0]
    rfu1["rfu_id"] = "R1"
    rfu2 = copy.deepcopy(rfu1)
    rfu2["rfu_id"] = "R2"
    rfu2["source_order"] = 2
    claim1 = base["claims"][0]
    claim1["claim_id"] = "C1"
    claim1["claim_components"][0]["component_id"] = "C1-COMP"
    claim2 = copy.deepcopy(claim1)
    claim2["claim_id"] = "C2"
    claim2["event_id"] = "C2-EVENT"
    claim2["claim_components"][0]["component_id"] = "C2-COMP"

    def verdict(
        rfu_id: str,
        claim_id: str,
        component_id: str,
        anchor_status: str,
    ) -> dict[str, object]:
        row = copy.deepcopy(base["verdicts"][0])
        row["rfu_id"] = rfu_id
        row["claim_id"] = claim_id
        row["reason_codes"] = []
        row["anchor_component_results"] = [
            {
                "component_id": component_id,
                "status": anchor_status,
            }
        ]
        row["atomicity"] = "atomic"
        return row

    verdicts = [
        verdict("R1", "C1", "C1-COMP", "supported"),
        verdict("R1", "C2", "C2-COMP", "supported"),
        verdict("R2", "C1", "C1-COMP", "supported"),
        verdict("R2", "C2", "C2-COMP", "unsupported"),
    ]
    selected = select_max_weight_matches(
        [rfu1, rfu2],
        [claim1, claim2],
        verdicts,
    )
    assert {
        (row["rfu_id"], row["claim_id"])
        for row in selected
    } == {("R1", "C2"), ("R2", "C1")}
    reversed_selected = select_max_weight_matches(
        [rfu2, rfu1],
        [claim2, claim1],
        list(reversed(verdicts)),
    )
    assert [
        (row["rfu_id"], row["claim_id"])
        for row in reversed_selected
    ] == [
        (row["rfu_id"], row["claim_id"])
        for row in selected
    ]


def test_match_ticket_rejects_incomplete_component_or_qualifier_rows() -> None:
    case = _case("CANARY-Q-01")
    case["verdicts"][0]["qualifier_results"] = []
    with pytest.raises(Z97ContractError, match="限定结果没有完整对齐"):
        compute_score_ticket(
            case["rfus"],
            case["claims"],
            case["verdicts"],
            judge_eligibility=case["judge_eligibility"],
            candidate_universe_complete=True,
        )

    case = _case("CANARY-A-01")
    case["verdicts"][0]["anchor_component_results"][0]["component_id"] = "OTHER"
    with pytest.raises(Z97ContractError, match="锚结果没有完整对齐"):
        compute_score_ticket(
            case["rfus"],
            case["claims"],
            case["verdicts"],
            judge_eligibility=case["judge_eligibility"],
            candidate_universe_complete=True,
        )


def test_judge_pollution_cannot_be_marked_eligible() -> None:
    case = _case("CANARY-A-01")
    eligibility = case["judge_eligibility"]
    eligibility["candidate_identity_visible"] = True
    with pytest.raises(Z97ContractError, match="污染"):
        validate_judge_eligibility(eligibility)


def test_match_verdict_rejects_schema_extra_field() -> None:
    case = _case("CANARY-A-01")
    case["verdicts"][0]["historical_verdict_read_only"] = "strict_hit"
    with pytest.raises(Z97ContractError, match="未声明字段"):
        compute_edge_weight(case["verdicts"][0])


def test_match_verdict_rejects_nested_schema_extra_field() -> None:
    case = _case("CANARY-Q-01")
    case["verdicts"][0]["qualifier_results"][0]["note"] = "not-in-schema"
    with pytest.raises(Z97ContractError, match="未声明字段"):
        compute_edge_weight(case["verdicts"][0])

    case = _case("CANARY-A-01")
    case["verdicts"][0]["anchor_component_results"][0]["quote"] = "not-in-schema"
    with pytest.raises(Z97ContractError, match="未声明字段"):
        compute_edge_weight(case["verdicts"][0])


def test_rfu_rejects_naked_anchor_ids() -> None:
    case = _case("CANARY-Q-01")
    rfu = case["rfus"][0]
    rfu["required_qualifiers"][0]["support_anchor_ids"] = ["E0001"]
    with pytest.raises(Z97ContractError, match="chNNNN:ENNNN"):
        validate_rfu(rfu)


def test_source_reader_rejects_retry03_truncated_raw() -> None:
    reader = pipeline.SourceReader()
    with pytest.raises(pipeline.Z97PipelineError, match="截断响应"):
        reader.json(
            pipeline.RETRY03_REJECTED_RAW,
            zone="J-MATCH",
            answer_derived=False,
        )


def test_bundle_build_is_byte_identical_and_keeps_quality_boundary(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    pipeline.build_bundle(left)
    pipeline.build_bundle(right)
    assert pipeline._tree_manifest(left) == pipeline._tree_manifest(right)

    rfu = json.loads(
        (left / "run/J-REF/rfu_ledger.json").read_text(encoding="utf-8")
    )
    assert rfu["rfu_count"] == 23
    assert rfu["formal_gold_denominator_read_only"] == 23
    assert rfu["qualifier_inventory_status"] == "not_exhaustively_adjudicated"

    retry03 = json.loads(
        (
            left / "run/SCORE/retry03_accounting_only_ticket.json"
        ).read_text(encoding="utf-8")
    )
    assert retry03["candidate_claim_count"] == 58
    assert retry03["match_verdict_count"] == 0
    assert all(value is None for value in retry03["metrics"].values())
    assert retry03["rejected_raw_used"] is False

    z89 = json.loads(
        (left / "run/SCORE/z89_score_ticket.json").read_text(encoding="utf-8")
    )
    assert z89["metrics"]["FCR"] == {
        "numerator": 13,
        "denominator": 23,
        "value": 13 / 23,
    }
    assert z89["metrics"]["UCR"] == {
        "numerator": 10.0,
        "denominator": 23.0,
        "value": 10 / 23,
    }
    assert z89["metrics"]["SOP"]["candidate_universe_complete"] is False
    assert z89["metrics"]["SOP"]["threshold_met"] is False
    assert z89["formal_score_eligible"] is False
    assert (
        z89["legacy_metrics_sha256_before"]
        == z89["legacy_metrics_sha256_after"]
    )

    validation = json.loads(
        (
            left / "run/audit/validation_summary.json"
        ).read_text(encoding="utf-8")
    )
    assert validation["candidate_connected_to_runner"] is False
    assert validation["formal_quality_winner_registered"] is False
    assert validation["mrp_72_release_gate_passed"] is False


def test_z89_qualifier_status_must_be_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(
        pipeline.Z89_QUALIFIER_STATUS["GOLD-C0003-14-N01"],
        "G14-Q-PURPOSE",
    )
    with pytest.raises(pipeline.Z97PipelineError, match="逐项冻结状态"):
        pipeline.build_bundle(tmp_path / "bundle")


def test_contract_files_parse_and_are_registered() -> None:
    rows = pipeline._contract_manifest()
    assert len(rows) == 5
    assert {Path(row["path"]).name for row in rows} == set(
        pipeline.CONTRACT_FILES
    )


def test_execute_refuses_any_unapproved_or_existing_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(pipeline.Z97PipelineError, match="只允许"):
        pipeline.execute_double_run(run_directory="runs/OTHER")

    existing = tmp_path / "exists"
    existing.mkdir()
    monkeypatch.setattr(pipeline, "REPO_ROOT", tmp_path)
    (tmp_path / "runs").mkdir()
    (tmp_path / "reports").mkdir()
    run_name = pipeline.AUTHORIZED_RUN_DIRECTORY.split("/", 1)[1]
    (tmp_path / "runs" / run_name).mkdir()
    with pytest.raises(pipeline.Z97PipelineError, match="已存在"):
        pipeline.execute_double_run()


def test_execute_double_run_verifies_copied_run_and_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline, "REPO_ROOT", tmp_path)
    (tmp_path / "runs").mkdir()
    (tmp_path / "reports").mkdir()

    def synthetic_build(root: Path) -> dict[str, object]:
        (root / "run").mkdir(parents=True)
        (root / "report").mkdir(parents=True)
        pipeline.write_text(root / "run" / "a.txt", "run\n")
        pipeline.write_text(root / "report" / "b.txt", "report\n")
        return {}

    monkeypatch.setattr(pipeline, "build_bundle", synthetic_build)
    receipt = pipeline.execute_double_run()
    assert receipt["status"] == "PASS"
    assert receipt["official_run_copy_sha256"]
    assert receipt["official_report_copy_sha256"]
    assert (
        tmp_path
        / pipeline.AUTHORIZED_RUN_DIRECTORY
        / "a.txt"
    ).read_text(encoding="utf-8") == "run\n"
    assert (
        tmp_path
        / pipeline.AUTHORIZED_REPORT_DIRECTORY
        / "b.txt"
    ).read_text(encoding="utf-8") == "report\n"
