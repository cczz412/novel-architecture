from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "novel-mvp/contracts/validate_plan_milestone_content.py"
SPEC = importlib.util.spec_from_file_location("validate_plan_milestone_content", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures()


def test_plan_milestone_fixture_matrix() -> None:
    for case in CASES:
        MODULE.validate_fixture_case(case)


def test_plan_milestone_fixture_counts() -> None:
    assert MODULE.validate_all_fixtures() == {"cases": 8, "valid": 2, "invalid": 6}


def test_milestone_fields_cover_review_items_12_13_14() -> None:
    contract = (ROOT / "novel-mvp/contracts/PLAN_MILESTONE_CONTENT.md").read_text(
        encoding="utf-8"
    )
    assert "storyline_refs" in contract
    assert "milestone_refs" in contract
    assert "construction_order" in contract
    assert "8240167c" in contract
    assert "fulfillment_fact_ref" in contract
