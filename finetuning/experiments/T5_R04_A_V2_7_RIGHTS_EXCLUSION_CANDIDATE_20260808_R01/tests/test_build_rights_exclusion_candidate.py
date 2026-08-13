from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/build_rights_exclusion_candidate.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("rights_exclusion_builder", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_decisions_are_stable_and_exact_rejections() -> None:
    tool = load_tool()
    first = tool.build_decision_rows()
    second = tool.build_decision_rows()
    assert tool.canonical_jsonl_bytes(first) == tool.canonical_jsonl_bytes(second)
    assert len(first) == 74
    assert len({row["group_id"] for row in first}) == 74
    assert sum(row["row_count"] for row in first) == 314
    assert sum(row["fact_count"] for row in first) == 2783
    assert {row["cz_decision"] for row in first} == {"REJECT_FOR_TRAINING"}
    assert {row["decision_scope"] for row in first} == {"INTERNAL_MODEL_TRAINING"}
    assert {row["allowed_use"] for row in first} == {"FORBIDDEN"}
    assert all(row["cz_note"] == tool.NOTE for row in first)
    for row in first:
        for key in (
            "authority_document_path",
            "authority_document_sha256",
            "rights_holder",
            "validity",
            "author_id",
            "author_name",
            "source_sha256",
            "row_scope",
            "authority_snapshot_path",
            "authority_snapshot_sha256",
        ):
            assert row[key] is None


def test_existing_candidate_is_reject_only_and_not_trainable() -> None:
    tool = load_tool()
    binding = tool.check()
    assert binding["status"] == "CANDIDATE_PENDING_CZ_CONFIRMATION"
    assert binding["frozen_denominator"] == {"groups": 74, "rows": 314, "facts": 2783}
    assert binding["two_run_stability"]["decision_bytes_identical"] is True
    assert binding["two_run_stability"]["candidate_bytes_identical"] is True
    assert binding["rights_boundary"] == {
        "original_source_status": "RIGHTS_UNKNOWN",
        "project_use_decision": "REJECT_FOR_TRAINING",
        "legal_rights_determination": False,
        "training_eligible": False,
        "production_promoted": False,
        "cz_confirmation_required": True,
    }
