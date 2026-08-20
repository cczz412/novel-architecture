#!/usr/bin/env python3
"""Read-only current-surface freshness checker.

This checker does not choose product semantics and does not auto-fix files. It only
verifies that the repository exposes one machine current, one pointer registry, a
small root compatibility stub, and aligned human entry points.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = (
    "current.md",
    "history/root_current_snapshot_20260720.md",
    "governance/INDEX.md",
    "governance/CURRENT_STATE.json",
    "governance/CURRENT_STATE_HISTORY.json",
    "governance/current_pointers.json",
    "governance/progress/current-progress.md",
    "AGENTS.md",
    "README.md",
    "governance/tool_registry.json",
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _issue(level: str, code: str, message: str, path: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"level": level, "code": code, "message": message}
    if path is not None:
        item["path"] = path
    return item


def build_report(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    for rel in REQUIRED_FILES:
        exists = (root / rel).is_file()
        checks.append({"check": "required_file", "path": rel, "passed": exists})
        if not exists:
            errors.append(_issue("ERROR", "MISSING_REQUIRED_FILE", "required current surface is missing", rel))

    if errors:
        return {
            "schema_version": "current-freshness-report-v1",
            "root": str(root),
            "status": "FAIL",
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
        }

    current = load_json(root / "governance/CURRENT_STATE.json")
    history = load_json(root / "governance/CURRENT_STATE_HISTORY.json")
    pointers = load_json(root / "governance/current_pointers.json")
    registry = load_json(root / "governance/tool_registry.json")
    stub = (root / "current.md").read_text(encoding="utf-8")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    progress = (root / "governance/progress/current-progress.md").read_text(encoding="utf-8")

    if current.get("schema_version") != "governance-current-state-v2":
        errors.append(_issue("ERROR", "CURRENT_SCHEMA", "CURRENT_STATE schema must remain v2", "governance/CURRENT_STATE.json"))

    historical_pointer = current.get("historical_context")
    if not isinstance(historical_pointer, dict) or historical_pointer.get("moved_to") != "governance/CURRENT_STATE_HISTORY.json":
        errors.append(_issue("ERROR", "HISTORY_NOT_SEPARATED", "CURRENT_STATE must point to the separated history snapshot", "governance/CURRENT_STATE.json"))
    forbidden_legacy = {"accepted_steps", "archived_run_states", "issue_ledger", "legacy_mainline"}
    if isinstance(historical_pointer, dict) and forbidden_legacy.intersection(historical_pointer):
        errors.append(_issue("ERROR", "LEGACY_CONTEXT_STILL_ACTIVE", "large historical ledgers remain inside active current", "governance/CURRENT_STATE.json"))
    if "historical_context" not in history:
        errors.append(_issue("ERROR", "HISTORY_SNAPSHOT_INCOMPLETE", "history snapshot does not contain historical_context", "governance/CURRENT_STATE_HISTORY.json"))

    required_stub_links = {
        "governance/INDEX.md",
        "governance/CURRENT_STATE.json",
        "governance/current_pointers.json",
        "governance/progress/current-progress.md",
        "history/root_current_snapshot_20260720.md",
    }
    for rel in sorted(required_stub_links):
        if rel not in stub:
            errors.append(_issue("ERROR", "ROOT_STUB_LINK_MISSING", f"root current stub does not link {rel}", "current.md"))

    pointer_rows = pointers.get("pointers")
    if not isinstance(pointer_rows, list):
        errors.append(_issue("ERROR", "POINTER_ROWS_INVALID", "pointers must be a list", "governance/current_pointers.json"))
        pointer_rows = []
    ids = [row.get("pointer_id") for row in pointer_rows if isinstance(row, dict)]
    if len(ids) != len(set(ids)):
        errors.append(_issue("ERROR", "POINTER_ID_DUPLICATE", "pointer_id values must be unique", "governance/current_pointers.json"))

    by_id = {row.get("pointer_id"): row for row in pointer_rows if isinstance(row, dict)}
    for pointer_id in ("repository_current", "product_background"):
        row = by_id.get(pointer_id)
        if not row or row.get("status") != "ACTIVE_CURRENT":
            errors.append(_issue("ERROR", "ACTIVE_POINTER_MISSING", f"{pointer_id} must have one ACTIVE_CURRENT row", "governance/current_pointers.json"))

    current_path = by_id.get("repository_current", {}).get("path")
    if current_path != "governance/CURRENT_STATE.json":
        errors.append(_issue("ERROR", "REPOSITORY_CURRENT_PATH", "repository_current must point to CURRENT_STATE.json", "governance/current_pointers.json"))

    product_row = by_id.get("product_background", {})
    product_path = product_row.get("path")
    product_version = product_row.get("version")
    if not isinstance(product_path, str) or not (root / product_path).is_file():
        errors.append(_issue("ERROR", "PRODUCT_BACKGROUND_MISSING", "active product background path is missing", str(product_path)))
    elif not product_path.endswith("/00_READ_ME_FIRST.md"):
        errors.append(_issue("ERROR", "PRODUCT_BACKGROUND_ENTRY", "active product background must point to 00_READ_ME_FIRST.md", product_path))
    elif isinstance(product_version, str) and f"_{product_version}/00_READ_ME_FIRST.md" not in product_path:
        errors.append(_issue("ERROR", "PRODUCT_BACKGROUND_VERSION", "product background version and path disagree", product_path))

    semantic_requirements = [
        "governance/CURRENT_STATE.json",
        "governance/current_pointers.json",
    ]
    if isinstance(product_path, str):
        semantic_requirements.append(product_path)
    for label, content, entry_path in (
        ("AGENTS", agents, "AGENTS.md"),
        ("README", readme, "README.md"),
    ):
        for required in semantic_requirements:
            if required not in content:
                errors.append(_issue("ERROR", "ENTRYPOINT_MISMATCH", f"{label} does not name {required}", entry_path))

    for required in ("governance/CURRENT_STATE.json", "governance/current_pointers.json"):
        if required not in progress:
            errors.append(_issue("ERROR", "ENTRYPOINT_MISMATCH", f"progress does not name {required}", "governance/progress/current-progress.md"))

    current_blob = json.dumps(current, ensure_ascii=False, sort_keys=True)
    for expected in (
        "CLEAN-BASELINE-M1-M11-INTEGRATION-20260821",
        "codex/module-runtime-foundation-20260819-r01",
        "cc793c4719fb6470946c70e744f463147989547b",
    ):
        if expected not in current_blob:
            errors.append(_issue("ERROR", "CURRENT_IDENTITY_MISSING", f"CURRENT_STATE does not contain {expected}", "governance/CURRENT_STATE.json"))
        if expected not in progress and expected != "CLEAN-BASELINE-M1-M11-INTEGRATION-20260821":
            errors.append(_issue("ERROR", "PROGRESS_IDENTITY_MISSING", f"progress does not contain {expected}", "governance/progress/current-progress.md"))

    tools = registry.get("tools", [])
    if not any(isinstance(row, dict) and row.get("path") == "tools/check_current_freshness.py" for row in tools):
        warnings.append(
            _issue(
                "WARNING",
                "CHECKER_REGISTRY_ENTRY_PENDING",
                "freshness checker is usable and routed from README/current pointers, but the monolithic tool registry entry is deferred to the drift-check consolidation ticket",
                "governance/tool_registry.json",
            )
        )

    for row in pointer_rows:
        if not isinstance(row, dict):
            continue
        path = row.get("path")
        status = row.get("status")
        if isinstance(path, str) and not (root / path).exists():
            if status in {"PLANNED", "PENDING_WORK_ORDER", "CANDIDATE_BRANCH"}:
                warnings.append(_issue("WARNING", "PLANNED_PATH_NOT_MATERIALIZED", "planned or candidate pointer is not present on main yet", path))
            else:
                errors.append(_issue("ERROR", "ACTIVE_POINTER_TARGET_MISSING", "active pointer target is missing", path))

    status = "PASS" if not errors else "FAIL"
    return {
        "schema_version": "current-freshness-report-v1",
        "root": str(root),
        "status": status,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "error_count": len(errors),
            "warning_count": len(warnings),
            "pointer_count": len(pointer_rows),
        },
    }


def render_summary(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Current freshness check",
        "",
        f"- status: `{report.get('status')}`",
        f"- errors: `{summary.get('error_count', len(report.get('errors', [])))}`",
        f"- warnings: `{summary.get('warning_count', len(report.get('warnings', [])))}`",
        f"- pointers: `{summary.get('pointer_count', 0)}`",
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
            f"{'PASS_CURRENT_FRESHNESS' if report['status'] == 'PASS' else 'FAIL_CURRENT_FRESHNESS'} "
            f"errors={len(report.get('errors', []))} warnings={len(report.get('warnings', []))}"
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
