#!/usr/bin/env python3
"""One-command read-only drift suite.

Runs the four standing checkers and prints a combined JSON / summary / exit code.
Does not rewrite current pointers, requirements, contracts, or product semantics.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

CHECKERS = (
    ("current_freshness", "check_current_freshness", "build_report"),
    ("design_currentness", "check_design_currentness", "build_report"),
    ("tracked_temp", "check_tracked_temp", "build_report"),
    ("review_identity", "check_review_identity", "build_report"),
)
TOOLS_DIR = Path(__file__).resolve().parent


def _load(name: str) -> ModuleType:
    path = TOOLS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _annotate(checker_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        row.setdefault("checker", checker_id)
        annotated.append(row)
    return annotated


def _checker_failure(root: Path, checker_id: str, exc: Exception) -> dict[str, Any]:
    return {
        "schema_version": "drift-child-error-v1",
        "root": str(root),
        "status": "FAIL",
        "errors": [
            {
                "level": "ERROR",
                "code": "CHECKER_EXCEPTION",
                "message": f"{type(exc).__name__}: {exc}",
            }
        ],
        "warnings": [],
        "summary": {"error_count": 1, "warning_count": 0, "checker": checker_id},
    }


def _validated_report(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("checker report must be an object")
    for field in ("errors", "warnings"):
        items = value.get(field) or []
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise TypeError(f"checker report {field} must be a list of objects")
    return value


def build_report(
    root: Path,
    pr_body: str | None = None,
    pr_body_path: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    reports: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    failing: list[str] = []
    for checker_id, module_name, function_name in CHECKERS:
        try:
            module = _load(module_name)
            if checker_id == "review_identity":
                raw_report = getattr(module, function_name)(
                    root,
                    pr_body=pr_body,
                    pr_body_path=pr_body_path,
                )
            else:
                raw_report = getattr(module, function_name)(root)
            report = _validated_report(raw_report)
        except Exception as exc:
            report = _checker_failure(root, checker_id, exc)
        reports[checker_id] = report
        checker_errors = list(report.get("errors") or [])
        errors.extend(_annotate(checker_id, checker_errors))
        warnings.extend(_annotate(checker_id, list(report.get("warnings") or [])))
        if report.get("status") != "PASS" or checker_errors:
            failing.append(checker_id)
    status = "PASS" if not failing else "FAIL"
    return {
        "schema_version": "drift-check-report-v1",
        "root": str(root),
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "checks": reports,
        "summary": {
            "checker_count": len(CHECKERS),
            "failing_checkers": failing,
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
    }


def render_summary(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Drift check suite",
        "",
        f"- status: `{report.get('status')}`",
        f"- checkers: `{summary.get('checker_count', 0)}`",
        f"- failing: `{json.dumps(summary.get('failing_checkers', []), ensure_ascii=False)}`",
        f"- errors: `{summary.get('error_count', len(report.get('errors', [])))}`",
        f"- warnings: `{summary.get('warning_count', len(report.get('warnings', [])))}`",
        "",
        "Checker PASS is not 852 semantic tests and is not a full-repo pytest green.",
    ]
    for checker_id, payload in (report.get("checks") or {}).items():
        lines.append(f"- `{checker_id}`: `{payload.get('status')}`")
    if report.get("errors"):
        lines.extend(["", "## Errors"])
        for item in report["errors"]:
            lines.append(
                f"- `{item.get('checker', '-')}` `{item.get('code', 'UNKNOWN_ERROR')}` "
                f"{item.get('message', 'checker reported an error')} "
                f"({item.get('path') or item.get('requirement_id') or '-'})"
            )
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        for item in report["warnings"][:20]:
            lines.append(
                f"- `{item.get('checker', '-')}` `{item.get('code', 'UNKNOWN_WARNING')}` "
                f"{item.get('message', 'checker reported a warning')} "
                f"({item.get('path') or item.get('requirement_id') or '-'})"
            )
        extra = len(report["warnings"]) - 20
        if extra > 0:
            lines.append(f"- … {extra} more warnings")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--pr-body",
        type=Path,
        help="optional future PR body to check; historical PRs are never fetched",
    )
    parser.add_argument("--format", choices=("summary", "json", "both"), default="both")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pr_body_path = str(args.pr_body) if args.pr_body else None
    report = build_report(args.root, pr_body_path=pr_body_path)
    summary = render_summary(report)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(summary, encoding="utf-8")
    if args.format in {"json", "both"}:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.format == "summary":
        print(summary, end="")
    elif args.format == "both":
        print(summary, end="", file=sys.stderr)
    if args.check:
        print(
            f"{'PASS_DRIFT' if report['status'] == 'PASS' else 'FAIL_DRIFT'} "
            f"errors={len(report.get('errors', []))} warnings={len(report.get('warnings', []))}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
