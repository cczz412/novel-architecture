from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

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
    identity = report["checks"]["review_identity"]["summary"]
    assert identity["pr_body_supplied"] is False
    assert identity["historical_prs_scanned"] is False


def test_optional_pr_body_empty_rollback_fails_suite() -> None:
    body = """<!-- review_identity:base_sha -->
- **base SHA**：aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

<!-- review_identity:head_sha -->
- **head SHA**：bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb

<!-- review_identity:requirement_ids -->
- **需求 ID**：
  - 承接：WO7
  - 部分贡献：
  - 依赖：
  - 明确排除：工单 6

<!-- review_identity:contract_delta -->
- **合同变化**：无十本账合同改动

<!-- review_identity:exact_tests -->
- **精确测试**：tests/test_drift.py

<!-- review_identity:semantic_change -->
- **是否改产品语义**：否

<!-- review_identity:rollback -->
- **回滚方式**：
"""
    report = MODULE.build_report(ROOT, pr_body=body, pr_body_path="pr.md")
    assert report["status"] == "FAIL"
    assert "review_identity" in report["summary"]["failing_checkers"]
    assert any(
        item["code"] == "REVIEW_IDENTITY_FIELD_EMPTY" and item.get("checker") == "review_identity"
        for item in report["errors"]
    )


def test_parse_args_default_format_is_both(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["check_drift.py"])
    args = MODULE.parse_args()
    assert args.format == "both"
    assert args.pr_body is None
