from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "novel-mvp/contracts/validate_fact_causal_edge.py"
SPEC = importlib.util.spec_from_file_location("validate_fact_causal_edge", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures()


def test_fact_causal_edge_fixture_matrix() -> None:
    for case in CASES:
        MODULE.validate_fixture_case(case)


def test_fact_causal_edge_fixture_counts() -> None:
    valid, invalid = MODULE.run_fixtures()
    assert valid == 2
    assert invalid == 4


def test_self_loop_and_plan_refs_are_rejected() -> None:
    contract = (ROOT / "novel-mvp/contracts/FACT_CAUSAL_EDGE.md").read_text(encoding="utf-8")
    assert "8240167c" in contract
    assert "5387771600" in contract
    assert "不改 C4" in contract or "不改 C4 必填字段" in contract
