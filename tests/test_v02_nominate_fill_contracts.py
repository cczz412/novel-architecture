from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_nominate_fill_contracts as nf  # noqa: E402


def test_both_valid_examples_pass_and_unknown_fields_fail() -> None:
    schemas = {
        "nomination": nf.nomination_schema(),
        "fill": nf.fill_schema(),
    }
    valid = nf.valid_examples(schemas)
    invalid = nf.invalid_examples(valid)

    for name in schemas:
        nf.validate_instance(valid[name], schemas[name])
        with pytest.raises(nf.NominateFillError, match="unknown fields"):
            nf.validate_instance(invalid[name], schemas[name])
    nf.validate_nomination_fill_pair(valid["nomination"], valid["fill"])


@pytest.mark.parametrize(
    "case_name",
    [
        "unknown_nomination_id",
        "drifted_fact_head",
        "forged_dedup_key",
        "minimal_anchor_mismatch",
        "reversed_source_span",
        "wrong_nomination_artifact_sha",
    ],
)
def test_cross_contract_negative_cases_are_rejected(case_name: str) -> None:
    schemas = {
        "nomination": nf.nomination_schema(),
        "fill": nf.fill_schema(),
    }
    valid = nf.valid_examples(schemas)
    pair = nf.cross_contract_negative_examples(valid)[case_name]

    with pytest.raises(nf.NominateFillError):
        nf.validate_nomination_fill_pair(pair["nomination"], pair["fill"])


def test_nomination_stage_cannot_carry_anchor_or_score_fields() -> None:
    schema = nf.nomination_schema()
    valid = nf.valid_examples({"nomination": schema, "fill": nf.fill_schema()})[
        "nomination"
    ]

    assert "minimal_anchor_ids" not in json.dumps(schema, ensure_ascii=False)
    assert "self_score" not in json.dumps(schema, ensure_ascii=False)
    valid["nominations"][0]["minimal_anchor_ids"] = ["E0001"]
    with pytest.raises(nf.NominateFillError):
        nf.validate_instance(valid, schema)


def test_exact_duplicate_is_flagged_but_never_auto_merged() -> None:
    schemas = {
        "nomination": nf.nomination_schema(),
        "fill": nf.fill_schema(),
    }
    row = nf.valid_examples(schemas)["nomination"]["nominations"][0]
    second = json.loads(json.dumps(row, ensure_ascii=False))
    second["nomination_id"] = "NH-C0001-B001-002"

    decisions = nf.dedup_decisions([row, second])

    assert len(decisions) == 1
    assert decisions[0]["decision"] == "EXACT_DUPLICATE_REVIEW_REQUIRED"
    assert decisions[0]["automatic_merge"] is False


def test_dedup_key_preserves_actuality_and_ledger_boundary() -> None:
    schemas = {
        "nomination": nf.nomination_schema(),
        "fill": nf.fill_schema(),
    }
    row = nf.valid_examples(schemas)["nomination"]["nominations"][0]
    changed = json.loads(json.dumps(row, ensure_ascii=False))
    changed["fact_head"]["actuality"] = "planned"

    assert nf.dedup_key(row) != nf.dedup_key(changed)


@pytest.mark.parametrize(
    ("observed", "budget", "expected"),
    [
        (12, "BUDGET_MISSING", "BUDGET_MISSING_HOLD"),
        (32, 32, "PASS"),
        (50, 32, "OVERFLOW_OBSERVE_NO_TRUNCATION"),
        (65, 32, "GRANULARITY_ANOMALY_REVIEW"),
        (20, 32, "UNDERFILL_OBSERVE_NO_PADDING"),
    ],
)
def test_density_guard_never_pads_or_truncates(
    observed: int,
    budget: int | str,
    expected: str,
) -> None:
    result = nf.density_guard(observed_count=observed, budget=budget)

    assert result["status"] == expected
    assert result["automatic_padding"] is False
    assert result["automatic_truncation"] is False
    assert result["semantic_merge"] is False


def test_build_is_deterministic_and_candidate_only(tmp_path: Path) -> None:
    first = nf.build_artifacts()
    second = nf.build_artifacts()

    assert first == second
    nf.write_artifacts(tmp_path, first)
    receipt = nf.verify_artifacts(tmp_path, second)
    manifest = json.loads((tmp_path / "artifact_manifest.json").read_text())
    assert receipt["status"] == "pass"
    assert manifest["status"] == "candidate_silver_not_active"
    assert manifest["model_api_calls"] == 0
    assert manifest["active_pipeline_changed"] is False
