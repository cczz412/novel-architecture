#!/usr/bin/env python3
"""Read-only validator for the reviewed-candidate capability traceability table."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_ROW_FIELDS = {
    "requirement_id",
    "requirement_level",
    "requirement_text",
    "journey_stage",
    "primary_owner",
    "shared_owners",
    "capability_type",
    "truth_write_level",
    "source_authority",
    "maturity",
    "review_identity",
}
CAPABILITY_TYPES = {
    "SEMANTIC",
    "MECHANICAL",
    "TRANSPORT",
    "PERSISTENCE",
    "SECURITY",
    "HUMAN_DECISION",
    "RENDERING",
    "OBSERVABILITY",
}
TRUTH_LEVELS = {
    "READ_ONLY",
    "PROJECTION_ONLY",
    "CANDIDATE_WRITE",
    "AUTHOR_CONFIRMED_WRITE",
    "SYSTEM_STATE_WRITE",
}
MATURITY = {
    "REQUIREMENT_ONLY",
    "TEST_DESIGNED",
    "FIXTURE_READY",
    "MECHANICAL_RUNNABLE",
    "SEMANTIC_RUNNABLE",
    "PARTIALLY_IMPLEMENTED",
    "INDEPENDENT_TOOL",
    "AUTHOR_USABLE",
    "MAIN_LOOP_INTEGRATED",
    "BLOCKED",
}
REQUIREMENT_LEVELS = {
    "NORTH_STAR",
    "CORE_CAPABILITY",
    "ATOMIC_EXPECTATION",
    "ACCEPTANCE_CASE",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def issue(level: str, code: str, requirement_id: str | None, message: str) -> dict[str, Any]:
    value: dict[str, Any] = {"level": level, "code": code, "message": message}
    if requirement_id is not None:
        value["requirement_id"] = requirement_id
    return value


def build_report(
    root: Path,
    traceability: dict[str, Any] | None = None,
    pointer_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    trace_path = root / "governance/capability_traceability.json"
    r03_path = root / "references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json"
    pointer_path = root / "references/atomic-expectations/TEST_DESIGN_CURRENT.json"

    if traceability is None:
        if not trace_path.is_file():
            return {
                "schema_version": "traceability-check-report-v1",
                "status": "FAIL",
                "errors": [issue("ERROR", "TRACEABILITY_MISSING", None, str(trace_path))],
                "warnings": [],
            }
        traceability = load_json(trace_path)

    if traceability.get("schema_version") != "capability-traceability-candidate-r01":
        errors.append(issue("ERROR", "SCHEMA_VERSION", None, "unexpected traceability schema_version"))
    if traceability.get("authority") != "ADVISORY_ONLY_NO_PRODUCT_OR_EXECUTION_AUTHORITY":
        errors.append(issue("ERROR", "AUTHORITY", None, "traceability authority changed"))
    if traceability.get("review_status") != "CANDIDATE_REVIEWED":
        errors.append(issue("ERROR", "REVIEW_STATUS", None, "review_status must be CANDIDATE_REVIEWED"))

    rows = traceability.get("requirements")
    if not isinstance(rows, list):
        errors.append(issue("ERROR", "ROWS_TYPE", None, "requirements must be a list"))
        rows = []
    if len(rows) != 142:
        errors.append(issue("ERROR", "ROW_COUNT", None, f"expected 142 rows, found {len(rows)}"))

    ids: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(issue("ERROR", "ROW_SCHEMA", None, f"row {index} is not an object"))
            continue
        req_id = row.get("requirement_id")
        if not isinstance(req_id, str) or not req_id:
            errors.append(issue("ERROR", "REQUIREMENT_ID", None, f"row {index} lacks requirement_id"))
            req_id = None
        else:
            ids.append(req_id)
        missing = sorted(REQUIRED_ROW_FIELDS - set(row))
        if missing:
            errors.append(issue("ERROR", "MISSING_FIELDS", req_id, f"missing {missing}"))
            continue
        if not isinstance(row.get("primary_owner"), str) or not row["primary_owner"]:
            errors.append(issue("ERROR", "OWNER_FIELD", req_id, "primary_owner must be a non-empty string; UNASSIGNED is legal"))
        if row.get("requirement_level") not in REQUIREMENT_LEVELS:
            errors.append(issue("ERROR", "REQUIREMENT_LEVEL", req_id, str(row.get("requirement_level"))))
        capability = row.get("capability_type")
        if not isinstance(capability, list) or not capability or any(item not in CAPABILITY_TYPES for item in capability):
            errors.append(issue("ERROR", "CAPABILITY_TYPE", req_id, str(capability)))
        if row.get("truth_write_level") not in TRUTH_LEVELS:
            errors.append(issue("ERROR", "TRUTH_WRITE_LEVEL", req_id, str(row.get("truth_write_level"))))
        if row.get("maturity") not in MATURITY:
            errors.append(issue("ERROR", "MATURITY", req_id, str(row.get("maturity"))))
        if row.get("review_identity") != "CANDIDATE_REVIEWED":
            errors.append(issue("ERROR", "ROW_REVIEW_IDENTITY", req_id, str(row.get("review_identity"))))
        authorities = row.get("source_authority")
        if not isinstance(authorities, list) or not authorities or any(not isinstance(item, str) or not item for item in authorities):
            errors.append(issue("ERROR", "SOURCE_AUTHORITY", req_id, str(authorities)))

        if row.get("primary_owner") == "UNASSIGNED":
            warnings.append(issue("WARNING", "REQUIREMENT_UNASSIGNED", req_id, "owner remains explicitly unassigned"))
        implementation_refs = row.get("implementation_refs", [])
        mapping_evidence = row.get("implementation_mapping_evidence")
        if implementation_refs and (not mapping_evidence or "PENDING_CZ_SOURCE" in authorities):
            warnings.append(issue("WARNING", "IMPLEMENTATION_WITHOUT_SOURCE", req_id, "implementation references lack a non-pending mapping source"))
        test_refs = row.get("test_refs", [])
        test_status = row.get("test_design_status")
        if not test_refs or not test_status:
            warnings.append(issue("WARNING", "TEST_WITHOUT_SOURCE", req_id, "test design or source reference is missing"))
        if row.get("local_evidence_status") == "LOCAL_EVIDENCE_PENDING":
            warnings.append(issue("WARNING", "LOCAL_EVIDENCE_PENDING", req_id, "local journey evidence card is intentionally deferred"))
        if "PENDING_CZ_SOURCE" in authorities:
            warnings.append(issue("WARNING", "PENDING_CZ_SOURCE", req_id, "upstream product source remains pending"))

    duplicates = sorted({req_id for req_id in ids if ids.count(req_id) > 1})
    if duplicates:
        errors.append(issue("ERROR", "DUPLICATE_IDS", None, str(duplicates)))

    if r03_path.is_file():
        r03 = load_json(r03_path)
        r03_rows = r03.get("records", [])
        r03_by_id = {row.get("预期ID"): row for row in r03_rows if isinstance(row, dict)}
        if set(ids) != set(r03_by_id):
            errors.append(issue("ERROR", "R03_ID_SET", None, "traceability IDs differ from R03"))
        for row in rows:
            if not isinstance(row, dict):
                continue
            req_id = row.get("requirement_id")
            if req_id in r03_by_id and row.get("requirement_text") != r03_by_id[req_id].get("长期需求"):
                errors.append(issue("ERROR", "REQUIREMENT_TEXT_CHANGED", req_id, "traceability text differs from R03"))
    else:
        errors.append(issue("ERROR", "R03_MISSING", None, str(r03_path)))

    if pointer_override is not None:
        pointer = pointer_override
    elif not pointer_path.is_file():
        errors.append(issue("ERROR", "TEST_POINTER_MISSING", None, str(pointer_path)))
        pointer = None
    else:
        pointer = load_json(pointer_path)
    if pointer is not None:
        coverage = pointer.get("coverage", {})
        if coverage.get("requirements_total") != 142 or coverage.get("small_tests_total") != 852:
            errors.append(issue("ERROR", "TEST_POINTER_COVERAGE", None, str(coverage)))
        suites = pointer.get("suites", [])
        if len(suites) != 2:
            errors.append(issue("ERROR", "TEST_SUITE_COUNT", None, "current test registry must contain legacy base plus R03 addendum"))
        if pointer.get("schema_version") != "atomic-test-design-current-registry-v2":
            errors.append(issue("ERROR", "TEST_DESIGN_SCHEMA", None, str(pointer.get("schema_version"))))
        if pointer.get("identity") != "ATOMIC_TEST_DESIGN_R03_COMPOSITE_CURRENT":
            errors.append(issue("ERROR", "TEST_DESIGN_IDENTITY", None, str(pointer.get("identity"))))
        suite_root = pointer_path.parent
        for suite in suites:
            if not isinstance(suite, dict):
                errors.append(issue("ERROR", "TEST_SUITE_SCHEMA", None, "suite is not an object"))
                continue
            suite_id = suite.get("suite_id") if isinstance(suite.get("suite_id"), str) else None
            for field, sha_field in (
                ("entry", None),
                ("design", "design_sha256"),
                ("validation_receipt", "validation_receipt_sha256"),
                ("manifest", "manifest_sha256"),
            ):
                rel = suite.get(field)
                if not rel:
                    continue
                if not isinstance(rel, str):
                    errors.append(issue("ERROR", "TEST_DESIGN_FILE_FIELD", suite_id, f"{field} must be a path"))
                    continue
                file_path = suite_root / rel
                if not file_path.is_file():
                    errors.append(issue("ERROR", "TEST_DESIGN_FILE_MISSING", suite_id, str(rel)))
                    continue
                expected = suite.get(sha_field) if sha_field else None
                if isinstance(expected, str) and expected:
                    digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
                    if digest != expected:
                        errors.append(issue("ERROR", "TEST_DESIGN_SHA_DRIFT", suite_id, f"{field} sha256 drifted"))

    for row in rows:
        if not isinstance(row, dict):
            continue
        req_id = row.get("requirement_id") if isinstance(row.get("requirement_id"), str) else None
        for key, code in (
            ("implementation_refs", "IMPLEMENTATION_REF_MISSING"),
            ("test_refs", "TEST_REF_MISSING"),
        ):
            for ref in row.get(key) or []:
                if not isinstance(ref, str) or not ref.strip():
                    continue
                rel = ref.split("#", 1)[0].strip()
                if not rel or rel.endswith("/"):
                    continue
                if "/" not in rel and not rel.endswith((".py", ".md", ".json")):
                    continue
                if not (root / rel).exists():
                    errors.append(issue("ERROR", code, req_id, rel))

    warning_counts: dict[str, int] = {}
    for item in warnings:
        warning_counts[item["code"]] = warning_counts.get(item["code"], 0) + 1
    status = "PASS" if not errors else "FAIL"
    return {
        "schema_version": "traceability-check-report-v1",
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "row_count": len(rows),
            "unique_id_count": len(set(ids)),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "warning_counts": dict(sorted(warning_counts.items())),
            "unassigned_count": sum(isinstance(row, dict) and row.get("primary_owner") == "UNASSIGNED" for row in rows),
        },
    }


def render_summary(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Capability traceability check",
        "",
        f"- status: `{report.get('status')}`",
        f"- rows: `{summary.get('row_count', 0)}`",
        f"- unique IDs: `{summary.get('unique_id_count', 0)}`",
        f"- errors: `{summary.get('error_count', len(report.get('errors', [])))}`",
        f"- warnings: `{summary.get('warning_count', len(report.get('warnings', [])))}`",
        f"- UNASSIGNED: `{summary.get('unassigned_count', 0)}`",
        f"- warning classes: `{json.dumps(summary.get('warning_counts', {}), ensure_ascii=False, sort_keys=True)}`",
    ]
    if report.get("errors"):
        lines.extend(["", "## Errors"])
        for item in report["errors"]:
            lines.append(f"- `{item['code']}` `{item.get('requirement_id', '-')}` {item['message']}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--format", choices=("summary", "json", "both"), default="summary")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.root)
    summary = render_summary(report)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(summary, encoding="utf-8")
    if args.format in {"json", "both"}:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.format in {"summary", "both"}:
        print(summary, end="")
    if args.check:
        print(
            f"{'PASS_TRACEABILITY' if report['status'] == 'PASS' else 'FAIL_TRACEABILITY'} "
            f"errors={len(report.get('errors', []))} warnings={len(report.get('warnings', []))}"
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
