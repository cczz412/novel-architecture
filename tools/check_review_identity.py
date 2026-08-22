#!/usr/bin/env python3
"""Read-only PR identity checker for future pull requests.

Historical merged PRs are out of scope. Default mode only verifies the
repository template. Pass --pr-body to check one future PR body.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

TEMPLATE_REL = ".github/PULL_REQUEST_TEMPLATE.md"
FIELD_MARKERS = (
    "review_identity:base_sha",
    "review_identity:head_sha",
    "review_identity:requirement_ids",
    "review_identity:contract_delta",
    "review_identity:exact_tests",
    "review_identity:semantic_change",
    "review_identity:rollback",
)
REQUIREMENT_ROLES = ("承接", "部分贡献", "依赖", "明确排除")
PLACEHOLDERS = {
    "",
    "_待填_",
    "TBD",
    "tbd",
    "—",
    "-",
    "TODO",
}


def _issue(level: str, code: str, message: str, path: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"level": level, "code": code, "message": message}
    if path is not None:
        item["path"] = path
    return item


def _marker(field: str) -> str:
    return f"<!-- {field} -->"


def _section_after(text: str, field: str) -> str:
    token = _marker(field)
    if token not in text:
        return ""
    rest = text.split(token, 1)[1]
    next_hits = [rest.find(_marker(other)) for other in FIELD_MARKERS if _marker(other) in rest]
    next_hits = [index for index in next_hits if index >= 0]
    if next_hits:
        rest = rest[: min(next_hits)]
    return rest


def _filled(text: str) -> bool:
    role_only = re.compile(r"^(承接|部分贡献|依赖|明确排除)[：:]?\s*$")
    heading_only = re.compile(r"^是否改产品语义[：:]?\s*(是\s*/\s*否)?\s*$")
    bold_heading = re.compile(r"^\*\*([^*]+)\*\*[：:]\s*(.*)$")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("<!--"):
            continue
        line = re.sub(r"^[-*]\s+", "", line).strip()
        matched = bold_heading.match(line)
        if matched:
            line = matched.group(2).strip()
        if not line or line in PLACEHOLDERS:
            continue
        if role_only.fullmatch(line) or heading_only.fullmatch(line):
            continue
        return True
    return False


def _check_document(text: str, path: str, *, require_values: bool) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[dict[str, Any]] = []
    present: list[str] = []
    for field in FIELD_MARKERS:
        if _marker(field) not in text:
            errors.append(_issue("ERROR", "REVIEW_IDENTITY_FIELD_MISSING", f"missing {field}", path))
            continue
        present.append(field)
        if require_values and not _filled(_section_after(text, field)):
            errors.append(
                _issue(
                    "ERROR",
                    "REVIEW_IDENTITY_FIELD_EMPTY",
                    f"{field} is present but empty",
                    path,
                )
            )
    missing_roles = [role for role in REQUIREMENT_ROLES if role not in text]
    if missing_roles:
        errors.append(
            _issue(
                "ERROR",
                "REQUIREMENT_ROLE_MISSING",
                "requirement IDs must distinguish 承接 / 部分贡献 / 依赖 / 明确排除",
                path,
            )
        )
    return errors, present


def build_report(root: Path, pr_body: str | None = None, pr_body_path: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    template_path = root / TEMPLATE_REL
    if not template_path.is_file():
        errors.append(_issue("ERROR", "PR_TEMPLATE_MISSING", "future PR template is missing", TEMPLATE_REL))
        template_text = ""
    else:
        template_text = template_path.read_text(encoding="utf-8")
        template_errors, _present = _check_document(template_text, TEMPLATE_REL, require_values=False)
        errors.extend(template_errors)

    body_rel = pr_body_path
    if pr_body is None and body_rel:
        body_file = root / body_rel if not Path(body_rel).is_absolute() else Path(body_rel)
        if body_file.is_file():
            pr_body = body_file.read_text(encoding="utf-8")
        else:
            errors.append(_issue("ERROR", "PR_BODY_MISSING", "requested PR body file is missing", body_rel))
            pr_body = ""

    if pr_body is not None:
        source = body_rel or "<pr-body>"
        body_errors, _present = _check_document(pr_body, source, require_values=True)
        errors.extend(body_errors)

    status = "PASS" if not errors else "FAIL"
    return {
        "schema_version": "review-identity-check-report-v1",
        "root": str(root),
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "template_present": template_path.is_file(),
            "pr_body_supplied": pr_body is not None,
            "historical_prs_scanned": False,
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
    }


def render_summary(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Review identity check",
        "",
        f"- status: `{report.get('status')}`",
        f"- template present: `{summary.get('template_present')}`",
        f"- PR body supplied: `{summary.get('pr_body_supplied')}`",
        f"- historical PRs scanned: `{summary.get('historical_prs_scanned')}`",
        f"- errors: `{summary.get('error_count', len(report.get('errors', [])))}`",
        f"- warnings: `{summary.get('warning_count', len(report.get('warnings', [])))}`",
    ]
    if report.get("errors"):
        lines.extend(["", "## Errors"])
        for item in report["errors"]:
            lines.append(f"- `{item['code']}` {item['message']} ({item.get('path', '-')})")
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        for item in report["warnings"]:
            lines.append(f"- `{item['code']}` {item['message']} ({item.get('path', '-')})")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pr-body", type=Path, help="optional future PR body to check; historical PRs are never fetched")
    parser.add_argument("--format", choices=("summary", "json", "both"), default="summary")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pr_body = args.pr_body.read_text(encoding="utf-8") if args.pr_body else None
    report = build_report(
        args.root,
        pr_body=pr_body,
        pr_body_path=str(args.pr_body) if args.pr_body else None,
    )
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
            f"{'PASS_REVIEW_IDENTITY' if report['status'] == 'PASS' else 'FAIL_REVIEW_IDENTITY'} "
            f"errors={len(report.get('errors', []))} warnings={len(report.get('warnings', []))}"
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
