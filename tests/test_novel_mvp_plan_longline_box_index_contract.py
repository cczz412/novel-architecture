from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "novel-mvp/contracts/validate_plan_longline_box_index.py"
SPEC = importlib.util.spec_from_file_location(
    "validate_plan_longline_box_index", MODULE_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASES = MODULE.load_fixtures()


def test_longline_box_fixture_matrix() -> None:
    for case in CASES:
        MODULE.validate_fixture_case(case)


def test_longline_box_fixture_counts() -> None:
    valid, invalid = MODULE.run_fixtures()
    assert valid == 2
    assert invalid == 3


def test_box_index_is_four_fields_and_compiled_light() -> None:
    contract = (ROOT / "novel-mvp/contracts/PLAN_LONGLINE_BOX_INDEX.md").read_text(
        encoding="utf-8"
    )
    assert "读取面五纪律" in contract
    assert "四样封顶" in contract
    assert "按任务声明" in contract
    assert "8240167c" in contract
