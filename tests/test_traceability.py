from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "check_traceability.py"
SPEC = importlib.util.spec_from_file_location("check_traceability", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ROOT = Path(__file__).resolve().parents[1]
TRACE = json.loads((ROOT / "governance/capability_traceability.json").read_text(encoding="utf-8"))


def error_codes(report: dict) -> set[str]:
    return {item["code"] for item in report["errors"]}


def test_repo_traceability_has_zero_errors() -> None:
    report = MODULE.build_report(ROOT)
    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert report["summary"]["row_count"] == 142
    assert report["summary"]["unique_id_count"] == 142


def test_duplicate_id_is_error() -> None:
    value = copy.deepcopy(TRACE)
    value["requirements"][1]["requirement_id"] = value["requirements"][0]["requirement_id"]
    report = MODULE.build_report(ROOT, value)
    assert "DUPLICATE_IDS" in error_codes(report)


def test_wrong_row_count_is_error() -> None:
    value = copy.deepcopy(TRACE)
    value["requirements"].pop()
    report = MODULE.build_report(ROOT, value)
    assert "ROW_COUNT" in error_codes(report)


def test_missing_owner_field_is_error() -> None:
    value = copy.deepcopy(TRACE)
    value["requirements"][0].pop("primary_owner")
    report = MODULE.build_report(ROOT, value)
    assert "MISSING_FIELDS" in error_codes(report)


def test_schema_enum_mismatch_is_error() -> None:
    value = copy.deepcopy(TRACE)
    value["requirements"][0]["capability_type"] = ["NOT_A_CAPABILITY_TYPE"]
    report = MODULE.build_report(ROOT, value)
    assert "CAPABILITY_TYPE" in error_codes(report)


def test_checker_is_read_only() -> None:
    tracked = [
        ROOT / "governance/capability_traceability.json",
        ROOT / "references/atomic-expectations/TEST_DESIGN_CURRENT.json",
        ROOT / "references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json",
    ]
    before = {path: path.read_bytes() for path in tracked}
    MODULE.build_report(ROOT)
    after = {path: path.read_bytes() for path in tracked}
    assert before == after


def test_missing_implementation_ref_is_error() -> None:
    value = copy.deepcopy(TRACE)
    value["requirements"][0]["implementation_refs"] = ["does-not-exist/missing.py"]
    report = MODULE.build_report(ROOT, value)
    assert "IMPLEMENTATION_REF_MISSING" in error_codes(report)


def test_missing_test_ref_is_error() -> None:
    value = copy.deepcopy(TRACE)
    value["requirements"][0]["test_refs"] = ["does-not-exist/missing-test.py"]
    report = MODULE.build_report(ROOT, value)
    assert "TEST_REF_MISSING" in error_codes(report)


def test_maturity_without_evidence_is_error() -> None:
    value = copy.deepcopy(TRACE)
    value["requirements"][0].pop("maturity_evidence")
    report = MODULE.build_report(ROOT, value)
    assert "MATURITY_EVIDENCE" in error_codes(report)


def test_test_design_sha_drift_is_error() -> None:
    pointer = json.loads(
        (ROOT / "references/atomic-expectations/TEST_DESIGN_CURRENT.json").read_text(encoding="utf-8")
    )
    pointer["suites"][0]["design_sha256"] = "0" * 64
    report = MODULE.build_report(ROOT, copy.deepcopy(TRACE), pointer)
    assert "TEST_DESIGN_SHA_DRIFT" in error_codes(report)
