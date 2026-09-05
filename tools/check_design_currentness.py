#!/usr/bin/env python3
"""Read-only validator for the design registry and its INDEX route."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

STATUSES = {"CURRENT", "WAITING_REWRITE", "HISTORICAL", "SUPERSEDED"}
DEFAULT_START = "<!-- DESIGN_DEFAULT_ROUTES_START -->"
DEFAULT_END = "<!-- DESIGN_DEFAULT_ROUTES_END -->"
TABLE_START = "<!-- DESIGN_STATUS_TABLE_START -->"
TABLE_END = "<!-- DESIGN_STATUS_TABLE_END -->"
EXCLUDED_MARKDOWN = {"INDEX.md"}
MIGRATION_DOCUMENT_ID = "a77972d8-8be7-4dfa-9d71-b6c7aa6d09ec"
MIGRATION_DOCUMENT_URL = (
    "https://linear.app/ccz/document/"
    "三类仓库背景卡解耦迁移总索引2026-08-30-e14efc91008b"
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def issue(level: str, code: str, message: str, path: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"level": level, "code": code, "message": message}
    if path is not None:
        value["path"] = path
    return value


def between(text: str, start: str, end: str) -> str | None:
    if text.count(start) != 1 or text.count(end) != 1:
        return None
    return text.split(start, 1)[1].split(end, 1)[0]


def linked_paths(section: str) -> list[str]:
    return [
        f"novel-mvp/design/{match}"
        for match in re.findall(r"\]\(([^)]+\.md)\)", section)
    ]


def status_table(section: str) -> dict[str, str]:
    result: dict[str, str] = {}
    pattern = re.compile(r"\]\(([^)]+\.md)\)\s*\|\s*`(CURRENT|WAITING_REWRITE|HISTORICAL|SUPERSEDED)`")
    for filename, status in pattern.findall(section):
        path = f"novel-mvp/design/{filename}"
        if path in result:
            raise ValueError(f"duplicate INDEX status row: {path}")
        result[path] = status
    return result


def build_report(
    root: Path,
    registry_override: dict[str, Any] | None = None,
    index_override: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    design_dir = root / "novel-mvp/design"
    registry_path = design_dir / "design_registry.json"
    index_path = design_dir / "INDEX.md"

    if registry_override is None:
        if not registry_path.is_file():
            return {
                "schema_version": "design-currentness-check-report-v1",
                "status": "FAIL",
                "errors": [issue("ERROR", "REGISTRY_MISSING", "design registry is missing", str(registry_path))],
                "warnings": [],
            }
        registry = load_json(registry_path)
    else:
        registry = registry_override
    index_text = index_path.read_text(encoding="utf-8") if index_override is None else index_override

    if registry.get("schema_version") != "design-currentness-registry-v1":
        errors.append(issue("ERROR", "SCHEMA_VERSION", "unexpected registry schema version"))
    if registry.get("review_status") != "CANDIDATE_REVIEWED":
        errors.append(issue("ERROR", "REVIEW_STATUS", "review_status must be CANDIDATE_REVIEWED"))
    if "product_background" in registry:
        errors.append(issue("ERROR", "RETIRED_PRODUCT_BACKGROUND", "local product_background binding must not return"))
    migration = registry.get("migration_source", {})
    if (
        migration.get("identity") != "LINEAR_FROZEN_MIGRATION_RECEIPT"
        or migration.get("former_source_version") != "R14"
        or migration.get("document_id") != MIGRATION_DOCUMENT_ID
        or migration.get("url") != MIGRATION_DOCUMENT_URL
        or not migration.get("attachment_id")
        or not migration.get("attachment_sha256")
    ):
        errors.append(
            issue(
                "ERROR",
                "MIGRATION_SOURCE_IDENTITY",
                "design registry must bind the frozen Linear migration receipt",
            )
        )

    rows = registry.get("documents")
    if not isinstance(rows, list):
        errors.append(issue("ERROR", "DOCUMENTS_TYPE", "documents must be a list"))
        rows = []

    actual = {
        f"novel-mvp/design/{path.name}"
        for path in design_dir.glob("*.md")
        if path.name not in EXCLUDED_MARKDOWN
    }
    paths: list[str] = []
    by_path: dict[str, dict[str, Any]] = {}
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(issue("ERROR", "ROW_SCHEMA", f"row {position} is not an object"))
            continue
        path = row.get("path")
        if not isinstance(path, str) or not path:
            errors.append(issue("ERROR", "PATH_FIELD", f"row {position} has no path"))
            continue
        paths.append(path)
        by_path[path] = row
        status = row.get("status")
        if status not in STATUSES:
            errors.append(issue("ERROR", "STATUS_ENUM", f"invalid status {status!r}", path))
        relation = row.get("source_relation")
        if not isinstance(relation, dict) or not relation.get("state") or not relation.get("note"):
            errors.append(issue("ERROR", "SOURCE_RELATION", "source_relation must contain state and note", path))
        source_basis = row.get("source_basis")
        if not isinstance(source_basis, list) or MIGRATION_DOCUMENT_URL not in source_basis:
            errors.append(
                issue(
                    "ERROR",
                    "MIGRATION_SOURCE_MISSING",
                    "every design row must retain the frozen migration receipt in source_basis",
                    path,
                )
            )
        if "superseded_by" not in row:
            errors.append(issue("ERROR", "SUPERSEDED_BY_FIELD", "superseded_by field is required", path))
        successor = row.get("superseded_by")
        if status == "SUPERSEDED":
            if not isinstance(successor, dict) or not successor.get("path"):
                errors.append(issue("ERROR", "SUPERSEDED_WITHOUT_SUCCESSOR", "SUPERSEDED requires a successor", path))
            elif successor.get("kind") == "REPOSITORY_PATH" and not (root / successor["path"]).is_file():
                errors.append(issue("ERROR", "SUCCESSOR_MISSING", "repository successor is missing", successor["path"]))
        elif successor is not None:
            errors.append(issue("ERROR", "NON_SUPERSEDED_HAS_SUCCESSOR", "only SUPERSEDED rows may set superseded_by", path))
        if status == "SUPERSEDED" and isinstance(successor, dict) and successor.get("path") == path:
            errors.append(issue("ERROR", "SUCCESSOR_SELF", "successor must not point at the same document", path))
        default_route = row.get("default_route")
        if not isinstance(default_route, bool):
            errors.append(issue("ERROR", "DEFAULT_ROUTE_FIELD", "default_route must be boolean", path))
        elif default_route != (status == "CURRENT"):
            errors.append(issue("ERROR", "DEFAULT_ROUTE_STATUS", "default_route must be true exactly for CURRENT", path))
        file_path = root / path
        if not file_path.is_file():
            errors.append(issue("ERROR", "REGISTERED_FILE_MISSING", "registered design file is missing", path))
        elif row.get("body_sha256") != sha256(file_path):
            errors.append(issue("ERROR", "BODY_SHA_DRIFT", "design body changed without registry refresh", path))

    duplicates = sorted({path for path in paths if paths.count(path) > 1})
    if duplicates:
        errors.append(issue("ERROR", "DUPLICATE_PATHS", str(duplicates)))
    registered = set(paths)
    if registered != actual:
        if missing := sorted(actual - registered):
            errors.append(issue("ERROR", "UNREGISTERED_DESIGN", str(missing)))
        if extra := sorted(registered - actual):
            errors.append(issue("ERROR", "REGISTRY_EXTRA_PATH", str(extra)))

    default_section = between(index_text, DEFAULT_START, DEFAULT_END)
    if default_section is None:
        errors.append(issue("ERROR", "DEFAULT_ROUTE_MARKERS", "INDEX default-route markers are missing or duplicated"))
        default_paths: list[str] = []
    else:
        default_paths = linked_paths(default_section)
        if len(default_paths) != len(set(default_paths)):
            errors.append(issue("ERROR", "DUPLICATE_DEFAULT_ROUTE", "INDEX default route contains duplicate files"))
        for path in default_paths:
            status = by_path.get(path, {}).get("status")
            if status != "CURRENT":
                errors.append(issue("ERROR", "DEFAULT_ROUTE_NON_CURRENT", f"default route points to {status}", path))
        registry_defaults = {path for path, row in by_path.items() if row.get("default_route") is True}
        if set(default_paths) != registry_defaults:
            errors.append(issue("ERROR", "DEFAULT_ROUTE_MISMATCH", f"INDEX={sorted(default_paths)} registry={sorted(registry_defaults)}"))

    table_section = between(index_text, TABLE_START, TABLE_END)
    if table_section is None:
        errors.append(issue("ERROR", "STATUS_TABLE_MARKERS", "INDEX full-table markers are missing or duplicated"))
    else:
        try:
            index_status = status_table(table_section)
        except ValueError as exc:
            errors.append(issue("ERROR", "INDEX_STATUS_DUPLICATE", str(exc)))
            index_status = {}
        registry_status = {path: row.get("status") for path, row in by_path.items()}
        if index_status != registry_status:
            errors.append(issue("ERROR", "INDEX_REGISTRY_STATUS_MISMATCH", "INDEX status table and registry differ"))
        successor_pattern = re.compile(
            r"\]\(([^)]+\.md)\)\s*\|\s*`(CURRENT|WAITING_REWRITE|HISTORICAL|SUPERSEDED)`\s*\|\s*`([^`]+)`"
        )
        index_successors: dict[str, str | None] = {}
        for filename, _status, shown in successor_pattern.findall(table_section):
            index_successors[f"novel-mvp/design/{filename}"] = None if shown in {"—", "-"} else shown
        for path, row in by_path.items():
            successor = row.get("superseded_by")
            expected = successor.get("path") if isinstance(successor, dict) else None
            shown = index_successors.get(path)
            if shown != expected:
                errors.append(
                    issue(
                        "ERROR",
                        "INDEX_SUCCESSOR_MISMATCH",
                        f"INDEX successor {shown!r} != registry {expected!r}",
                        path,
                    )
                )

    status_cell_pattern = re.compile(
        r"\]\(([^)]+\.md)\)\s*\|\s*`(CURRENT|WAITING_REWRITE|HISTORICAL|SUPERSEDED)`"
    )
    for filename, shown in status_cell_pattern.findall(index_text):
        cell_path = f"novel-mvp/design/{filename}"
        cell_row = by_path.get(cell_path)
        if cell_row is not None and cell_row.get("status") != shown:
            errors.append(
                issue(
                    "ERROR",
                    "INDEX_REGISTRY_STATUS_MISMATCH",
                    f"{cell_path} shows `{shown}` in INDEX but registry says {cell_row.get('status')}",
                )
            )

    status_counts = Counter(row.get("status") for row in rows if isinstance(row, dict))
    visited_cycles: set[str] = set()
    for start, row in by_path.items():
        if row.get("status") != "SUPERSEDED":
            continue
        seen: list[str] = []
        current = start
        while current in by_path and by_path[current].get("status") == "SUPERSEDED":
            successor = by_path[current].get("superseded_by")
            nxt = successor.get("path") if isinstance(successor, dict) else None
            if not isinstance(nxt, str) or not nxt:
                break
            if nxt == current:
                break
            if nxt in seen:
                cycle_members = tuple(sorted(set(seen + [current, nxt])))
                marker = "|".join(cycle_members)
                if marker not in visited_cycles:
                    visited_cycles.add(marker)
                    errors.append(
                        issue(
                            "ERROR",
                            "SUCCESSOR_CYCLE",
                            f"successor chain cycles through {list(cycle_members)}",
                            start,
                        )
                    )
                break
            seen.append(current)
            current = nxt

    inventory = registry.get("inventory", {})
    if inventory.get("document_count") != len(rows):
        errors.append(issue("ERROR", "INVENTORY_COUNT", "inventory document_count differs from rows"))
    if inventory.get("status_counts") != dict(sorted(status_counts.items())):
        errors.append(issue("ERROR", "INVENTORY_STATUS_COUNTS", "inventory status_counts differs from rows"))

    pr_c = registry.get("expected_work_order_5_pr_c_changes", {}).get("changes")
    if not isinstance(pr_c, list) or len(pr_c) != 4:
        errors.append(issue("ERROR", "PR_C_EXPECTED_CHANGES", "registry must record four read-only PR-C design surfaces"))

    status = "PASS" if not errors else "FAIL"
    return {
        "schema_version": "design-currentness-check-report-v1",
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "document_count": len(rows),
            "registered_unique_paths": len(set(paths)),
            "default_route_count": len(default_paths),
            "status_counts": dict(sorted(status_counts.items())),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
    }


def render_summary(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Design currentness check",
        "",
        f"- status: `{report.get('status')}`",
        f"- documents: `{summary.get('document_count', 0)}`",
        f"- unique paths: `{summary.get('registered_unique_paths', 0)}`",
        f"- default routes: `{summary.get('default_route_count', 0)}`",
        f"- status counts: `{json.dumps(summary.get('status_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- errors: `{summary.get('error_count', len(report.get('errors', [])))}`",
        f"- warnings: `{summary.get('warning_count', len(report.get('warnings', [])))}`",
    ]
    if report.get("errors"):
        lines.extend(["", "## Errors"])
        for item in report["errors"]:
            lines.append(f"- `{item['code']}` `{item.get('path', '-')}` {item['message']}")
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
            f"{'PASS_DESIGN_CURRENTNESS' if report['status'] == 'PASS' else 'FAIL_DESIGN_CURRENTNESS'} "
            f"errors={len(report.get('errors', []))} warnings={len(report.get('warnings', []))}"
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
