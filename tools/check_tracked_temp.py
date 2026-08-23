#!/usr/bin/env python3
"""Read-only scanner for tracked TEMP / runs / reports / outbox paths.

Uses NUL-safe `git ls-files -z`. It does not grep file bodies for the letters TEMP.
A path is a TEMP hit only when a path component is exactly `TEMP`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

FREEZE_MANIFEST_NAMES = frozenset(
    {
        "MANIFEST.json",
        "FROZEN_MANIFEST.json",
        "freeze_manifest.json",
    }
)
WARNING_ROOTS = ("runs", "reports", "outbox")


def _issue(level: str, code: str, message: str, path: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"level": level, "code": code, "message": message}
    if path is not None:
        item["path"] = path
    return item


def _git_ls_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git ls-files failed with exit {result.returncode}: {detail}")
    payload = result.stdout.split(b"\0")
    paths: list[str] = []
    for raw in payload:
        if not raw:
            continue
        paths.append(raw.decode("utf-8", errors="strict"))
    return paths


def _tracked_list_problem(paths: object) -> str | None:
    if not isinstance(paths, list):
        return "git ls-files result is not a list"
    if not paths:
        return "git ls-files returned an empty tracked-path list"
    if any(not isinstance(path, str) or not path for path in paths):
        return "git ls-files returned a non-string or empty path"
    if len(paths) != len(set(paths)):
        return "git ls-files returned duplicate paths"
    for path in paths:
        pure = PurePosixPath(path)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            return f"git ls-files returned an unsafe path: {path!r}"
    return None


def _is_git_repo(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _has_temp_component(posix: str) -> bool:
    return "TEMP" in Path(posix).parts


def _is_freeze_manifest(posix: str) -> bool:
    path = Path(posix)
    return path.name in FREEZE_MANIFEST_NAMES and "TEMP" in path.parts


def _covered_by_freeze(posix: str, tracked: set[str]) -> bool:
    parts = Path(posix).parts
    if "TEMP" not in parts:
        return False
    temp_index = parts.index("TEMP")
    for length in range(len(parts) - 1, temp_index, -1):
        directory = Path(*parts[:length]).as_posix()
        for name in FREEZE_MANIFEST_NAMES:
            if f"{directory}/{name}" in tracked:
                return True
    return False


def build_report(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    try:
        is_git_repo = _is_git_repo(root)
    except OSError as exc:
        errors.append(_issue("ERROR", "GIT_PROBE_FAILED", f"cannot run Git repository probe: {exc}", str(root)))
        is_git_repo = False
    if not is_git_repo:
        if not errors:
            errors.append(
                _issue(
                    "ERROR",
                    "NOT_A_GIT_REPO",
                    "tracked-temp check requires a Git work tree",
                    str(root),
                )
            )
        return {
            "schema_version": "tracked-temp-check-report-v1",
            "root": str(root),
            "status": "FAIL",
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "tracked_count": 0,
                "temp_error_count": 0,
                "lane_warning_count": 0,
                "error_count": len(errors),
                "warning_count": 0,
            },
        }

    try:
        tracked_paths = _git_ls_files(root)
    except (OSError, RuntimeError, UnicodeDecodeError) as exc:
        errors.append(_issue("ERROR", "GIT_LS_FILES_FAILED", str(exc), str(root)))
        tracked_paths = []
    if not errors and (problem := _tracked_list_problem(tracked_paths)) is not None:
        errors.append(_issue("ERROR", "TRACKED_LIST_INVALID", problem, str(root)))
    if errors:
        return {
            "schema_version": "tracked-temp-check-report-v1",
            "root": str(root),
            "status": "FAIL",
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "tracked_count": len(tracked_paths),
                "temp_error_count": 0,
                "lane_warning_count": 0,
                "error_count": len(errors),
                "warning_count": 0,
            },
        }
    tracked = set(tracked_paths)
    temp_hits: list[str] = []
    lane_hits: list[str] = []
    for posix in tracked_paths:
        parts = Path(posix).parts
        if _has_temp_component(posix):
            if _is_freeze_manifest(posix) or _covered_by_freeze(posix, tracked):
                continue
            temp_hits.append(posix)
            errors.append(
                _issue(
                    "ERROR",
                    "TRACKED_TEMP_WITHOUT_FREEZE_MANIFEST",
                    "tracked path has a TEMP component but no freeze manifest",
                    posix,
                )
            )
        elif parts and parts[0] in WARNING_ROOTS:
            lane_hits.append(posix)
            warnings.append(
                _issue(
                    "WARNING",
                    "TRACKED_RUNTIME_LANE",
                    f"tracked file sits under {parts[0]}/; first cycle stays WARNING",
                    posix,
                )
            )

    status = "PASS" if not errors else "FAIL"
    return {
        "schema_version": "tracked-temp-check-report-v1",
        "root": str(root),
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "tracked_count": len(tracked_paths),
            "temp_error_count": len(temp_hits),
            "lane_warning_count": len(lane_hits),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
    }


def render_summary(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Tracked TEMP check",
        "",
        f"- status: `{report.get('status')}`",
        f"- tracked files: `{summary.get('tracked_count', 0)}`",
        f"- TEMP errors: `{summary.get('temp_error_count', 0)}`",
        f"- runs/reports/outbox warnings: `{summary.get('lane_warning_count', 0)}`",
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
            f"{'PASS_TRACKED_TEMP' if report['status'] == 'PASS' else 'FAIL_TRACKED_TEMP'} "
            f"errors={len(report.get('errors', []))} warnings={len(report.get('warnings', []))}"
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
