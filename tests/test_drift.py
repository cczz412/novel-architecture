from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "check_drift.py"
SPEC = importlib.util.spec_from_file_location("check_drift", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_live_root_five_checker_suite_has_no_errors() -> None:
    report = MODULE.build_report(ROOT)
    assert report["schema_version"] == "drift-check-report-v1"
    assert report["summary"]["checker_count"] == 5
    assert set(report["checks"]) == {
        "current_freshness",
        "design_currentness",
        "traceability",
        "tracked_temp",
        "review_identity",
    }
    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert report["summary"]["failing_checkers"] == []
