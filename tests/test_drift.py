from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

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


def test_child_exception_is_structured_without_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "CHECKERS", (("broken", "broken", "build_report"),))

    def fail_load(_name: str) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(MODULE, "_load", fail_load)
    report = MODULE.build_report(ROOT)
    assert report["status"] == "FAIL"
    assert report["summary"]["failing_checkers"] == ["broken"]
    assert report["errors"][0]["code"] == "CHECKER_EXCEPTION"
    assert "Traceback" not in MODULE.render_summary(report)


def test_child_error_cannot_hide_behind_pass_status(monkeypatch: pytest.MonkeyPatch) -> None:
    child = {
        "status": "PASS",
        "errors": [{"level": "ERROR", "code": "HIDDEN", "message": "must fail"}],
        "warnings": [],
    }
    module = SimpleNamespace(build_report=lambda _root: child)
    monkeypatch.setattr(MODULE, "CHECKERS", (("inconsistent", "inconsistent", "build_report"),))
    monkeypatch.setattr(MODULE, "_load", lambda _name: module)
    report = MODULE.build_report(ROOT)
    assert report["status"] == "FAIL"
    assert report["summary"]["failing_checkers"] == ["inconsistent"]
    assert report["errors"][0]["code"] == "HIDDEN"


@pytest.mark.parametrize("output_format", ["json", "both"])
def test_json_stdout_is_one_document_with_check_status_on_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    output_format: str,
) -> None:
    monkeypatch.setattr(sys, "argv", ["check_drift.py", "--format", output_format, "--check"])
    assert MODULE.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "PASS"
    assert "PASS_DRIFT" in captured.err
    if output_format == "both":
        assert "# Drift check suite" in captured.err
