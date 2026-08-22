from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "check_review_identity.py"
SPEC = importlib.util.spec_from_file_location("check_review_identity", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")


def test_live_template_covers_six_fields() -> None:
    report = MODULE.build_report(ROOT)
    assert report["status"] == "PASS"
    assert report["summary"]["historical_prs_scanned"] is False
    codes = {item["code"] for item in report["errors"]}
    assert "REVIEW_IDENTITY_FIELD_MISSING" not in codes


def test_missing_template_field_is_error(tmp_path: Path) -> None:
    (tmp_path / ".github").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".github/PULL_REQUEST_TEMPLATE.md").write_text("# empty\n", encoding="utf-8")
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "REVIEW_IDENTITY_FIELD_MISSING" in {item["code"] for item in report["errors"]}


def test_future_pr_body_missing_rollback_is_error(tmp_path: Path) -> None:
    (tmp_path / ".github").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".github/PULL_REQUEST_TEMPLATE.md").write_text(TEMPLATE, encoding="utf-8")
    body = TEMPLATE.replace("<!-- review_identity:rollback -->", "")
    report = MODULE.build_report(tmp_path, pr_body=body, pr_body_path="pr.md")
    assert report["status"] == "FAIL"
    assert "REVIEW_IDENTITY_FIELD_MISSING" in {item["code"] for item in report["errors"]}


def _filled_pr_body() -> str:
    return """<!-- review_identity:base_sha -->
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


def test_future_pr_body_with_empty_rollback_is_error(tmp_path: Path) -> None:
    (tmp_path / ".github").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".github/PULL_REQUEST_TEMPLATE.md").write_text(TEMPLATE, encoding="utf-8")
    report = MODULE.build_report(tmp_path, pr_body=_filled_pr_body(), pr_body_path="pr.md")
    assert report["status"] == "FAIL"
    assert "REVIEW_IDENTITY_FIELD_EMPTY" in {item["code"] for item in report["errors"]}
