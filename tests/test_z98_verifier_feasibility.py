from __future__ import annotations

import json
from pathlib import Path

from experiments.Z98_independent_verifier_freeze_20260724 import pipeline
from experiments.Z98_independent_verifier_freeze_20260724.feasibility import (
    build_feasibility_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_budget_override_and_identity_limitation_are_both_explicit(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = _load(bundle / "mappings/verifier_mapping.json")
    templates = {
        row["verifier_template_path"]: _load(
            bundle / row["verifier_template_path"]
        )
        for row in mapping["mappings"]
    }
    receipt = build_feasibility_receipt(
        repo_root=REPO_ROOT,
        templates=templates,
    )
    assert receipt["status"] == (
        "PASS_WITH_RUNTIME_BUDGET_GATE_AND_DECLARED_"
        "CARDINALITY_LIMITATION"
    )
    assert receipt["hard_stop_reasons"] == []
    budget = receipt["budget_audit"]
    assert budget["template_count"] == 17
    assert budget["candidate_result_inserted"] is False
    assert budget["projected_input_over_total_cap_count"] == 17
    assert budget["all_templates_projected_over_total_cap"] is True
    assert all(
        row["empirical_prompt_projection_min"]
        > row["verification_total_token_cap"]
        for row in budget["templates"]
    )
    legacy = budget["legacy_pre_registered_per_request_caps"]
    assert legacy["status"] == (
        "SUPERSEDED_AS_SEND_BLOCKER_BY_CZ_DIRECT_ALLOWANCE"
    )
    allowance = budget["cz_direct_round_allowance"]
    assert allowance["total_token_cap"] == 500_000
    assert (
        allowance["static_before_candidate_two_lane_token_projection"]
        < 500_000
    )
    assert (
        allowance["static_before_candidate_two_lane_cost_micro_cny"]
        < 10_000_000
    )
    assert allowance["static_projection_within_token_cap"] is True
    assert allowance["static_projection_within_cost_cap"] is True
    assert allowance["full_round_completion_guaranteed"] is False
    assert allowance["runtime_dynamic_request_gate_required"] is True
    blindness = receipt["identity_blindness_audit"]
    assert blindness["single_item_counts"] == [1]
    assert blindness["batch_item_counts"] == [4, 5]
    assert blindness["structural_identity_inferable"] is True
    assert blindness["blocking"] is False
    assert receipt["model_api_calls"] == 0
    assert receipt["network_attempts"] == 0


def test_qwen_family_calibration_sources_are_sha_pinned(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    mapping = _load(bundle / "mappings/verifier_mapping.json")
    templates = {
        row["verifier_template_path"]: _load(
            bundle / row["verifier_template_path"]
        )
        for row in mapping["mappings"]
    }
    receipt = build_feasibility_receipt(
        repo_root=REPO_ROOT,
        templates=templates,
    )
    sources = receipt["calibration"]["sources"]
    assert [row["prompt_tokens"] for row in sources] == [11395, 11391]
    assert [row["message_chars"] for row in sources] == [23202, 23202]
    assert all(len(row["request_sha256"]) == 64 for row in sources)
    assert all(len(row["usage_sha256"]) == 64 for row in sources)
