#!/usr/bin/env python3
"""Read-only checker for the repository's current technical entry surface.

Verified long-term decisions and product specifications follow Notion's per-item
storage register; unmigrated items retain their original Linear source. Active tasks
live in Linear; implemented engineering truth lives in GitHub.
This checker validates only repository paths, identities, the dated technical
snapshot, and registered drift tools. It does not compile or validate a repository-wide
product background.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

REQUIRED_FILES = (
    "current.md",
    "history/root_current_snapshot_20260720.md",
    "governance/INDEX.md",
    "governance/START_HERE.md",
    "governance/CURRENT_STATE.json",
    "governance/CURRENT_STATE_HISTORY.json",
    "governance/current_pointers.json",
    "governance/tool_registry.json",
    "AGENTS.md",
    "README.md",
)
POINTER_SCHEMA = "governance-current-pointers-v1"
REQUIRED_POINTER_FIELDS = ("pointer_id", "status", "path")
POINTER_STATUSES = {
    "ACTIVE_CURRENT",
    "HISTORICAL_REFERENCE",
    "CANDIDATE_REVIEWED",
    "CANDIDATE_BRANCH",
    "ACTIVE_DOMAIN_POINTER",
    "PLANNED",
    "PENDING_WORK_ORDER",
    "SUPERSEDED_HISTORICAL",
}
DRIFT_CHECKERS = (
    "tools/check_current_freshness.py",
    "tools/check_design_currentness.py",
    "tools/check_tracked_temp.py",
    "tools/check_review_identity.py",
    "tools/check_drift.py",
)
EXPECTED_INVARIANTS = (
    "repository_current、current_freshness_checker 与 design_registry 各自只有一个登记入口。",
    "候选分支、PLANNED 和 PENDING_WORK_ORDER 不得冒充 main current。",
    "本表不保存运行分数，不替代正式合同、结果票或 CZ 拍板。",
    "本表不保存整体任务进度、领票、依赖、阻塞、PR 或合并状态；这些信息现场读取 Linear 与 GitHub。",
    "设计默认路由只能指向 design_registry 中的 CURRENT；其他状态一律不得指导施工。",
    "已核对的长期决定、原话和产品规格按 Notion 逐项主存登记读取，未迁项仍回原 Linear 主存；活动任务与未决问题现场读取 Linear；工程能力只认 GitHub main 上的正式合同、测试和已合并代码。",
)
REQUIRED_ACTIVE_POINTERS = {
    "repository_current": "governance/CURRENT_STATE.json",
    "current_freshness_checker": "tools/check_current_freshness.py",
    "design_registry": "novel-mvp/design/design_registry.json",
}
RETIRED_BACKGROUND_POINTER_IDS = {
    "product_background",
    "external_report_background",
    "atomic_expectations",
    "atomic_test_design",
}
RESERVED_ACTIVE_PATHS = frozenset(REQUIRED_ACTIVE_POINTERS.values())
SCORE_KEYS = ("score", "pass_rate", "kill_rate")
MASQUERADE_STATUSES = {"CANDIDATE_BRANCH", "PLANNED", "PENDING_WORK_ORDER"}
CURRENT_STATE_REL = "governance/CURRENT_STATE.json"
DESIGN_REGISTRY_REL = "novel-mvp/design/design_registry.json"
DRIFT_SUITE_REL = "tools/check_drift.py"
REFRESH_BASE_KIND = "refresh_base"
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _issue(level: str, code: str, message: str, path: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"level": level, "code": code, "message": message}
    if path is not None:
        item["path"] = path
    return item


def _posix(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value).as_posix()


def _validate_design_registry(
    root: Path,
    row: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    if (
        row.get("path") != DESIGN_REGISTRY_REL
        or row.get("version") != "R01"
        or row.get("index_path") != "novel-mvp/design/INDEX.md"
        or row.get("checker_path") != "tools/check_design_currentness.py"
        or row.get("checker_registry_status") != "REGISTERED"
        or row.get("suite_entry") != DRIFT_SUITE_REL
    ):
        errors.append(
            _issue(
                "ERROR",
                "DESIGN_REGISTRY_POINTER_IDENTITY",
                "design_registry current identity or checker binding drifted",
                "governance/current_pointers.json",
            )
        )
    target = root / DESIGN_REGISTRY_REL
    if not target.is_file():
        return
    try:
        document = load_json(target)
    except (OSError, json.JSONDecodeError):
        errors.append(
            _issue("ERROR", "DESIGN_REGISTRY_INVALID", "design_registry is not readable JSON", DESIGN_REGISTRY_REL)
        )
        return
    inventory = document.get("inventory")
    if not isinstance(inventory, dict):
        errors.append(
            _issue("ERROR", "DESIGN_REGISTRY_INVALID", "design_registry inventory is missing", DESIGN_REGISTRY_REL)
        )
        return
    if row.get("document_count") != inventory.get("document_count") or row.get(
        "status_counts"
    ) != inventory.get("status_counts"):
        errors.append(
            _issue(
                "ERROR",
                "DESIGN_REGISTRY_COUNT_MISMATCH",
                "design_registry pointer inventory copy is stale",
                "governance/current_pointers.json",
            )
        )


def _validate_active_pointer(
    root: Path,
    row: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    pointer_id = row.get("pointer_id")
    expected_path = REQUIRED_ACTIVE_POINTERS.get(pointer_id)
    if expected_path is None:
        errors.append(
            _issue(
                "ERROR",
                "ACTIVE_CURRENT_UNVALIDATED",
                f"ACTIVE_CURRENT row {pointer_id!r} has no explicit validator",
                "governance/current_pointers.json",
            )
        )
        return
    if row.get("path") != expected_path:
        errors.append(
            _issue(
                "ERROR",
                "ACTIVE_CURRENT_PATH",
                f"{pointer_id} must point to {expected_path}",
                "governance/current_pointers.json",
            )
        )
    version = row.get("version")
    if not isinstance(version, str) or not version.strip():
        errors.append(
            _issue(
                "ERROR",
                "ACTIVE_CURRENT_VERSION_MISSING",
                f"{pointer_id} must declare a non-empty version",
                "governance/current_pointers.json",
            )
        )
    if pointer_id == "repository_current" and version != "governance-current-state-v2":
        errors.append(
            _issue(
                "ERROR",
                "REPOSITORY_CURRENT_IDENTITY",
                "repository_current must bind CURRENT_STATE at governance-current-state-v2",
                "governance/current_pointers.json",
            )
        )
    elif pointer_id == "current_freshness_checker":
        if (
            version != "v1"
            or row.get("registry_status") != "REGISTERED"
            or row.get("suite_entry") != DRIFT_SUITE_REL
            or not (root / DRIFT_SUITE_REL).is_file()
        ):
            errors.append(
                _issue(
                    "ERROR",
                    "CURRENT_CHECKER_IDENTITY",
                    "current_freshness_checker must remain registered at v1 and bind the drift suite",
                    "governance/current_pointers.json",
                )
            )
    elif pointer_id == "design_registry":
        _validate_design_registry(root, row, errors)


def _is_git_repo(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _git_rev_parse(root: Path, ref: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", ref],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    sha = result.stdout.strip().lower()
    return sha if GIT_SHA_RE.fullmatch(sha) else None


def _git_is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _compared_git_sha(root: Path) -> tuple[str | None, str | None]:
    for ref in ("origin/main", "HEAD"):
        sha = _git_rev_parse(root, ref)
        if sha is not None:
            return sha, ref
    return None, None


def _main_snapshot(current: dict[str, Any]) -> dict[str, Any] | None:
    refresh = current.get("refresh_metadata")
    if not isinstance(refresh, dict):
        return None
    snapshots = refresh.get("source_snapshot")
    if not isinstance(snapshots, list):
        return None
    return next(
        (row for row in snapshots if isinstance(row, dict) and row.get("identity") == "main"),
        None,
    )


def _check_recorded_main_against_git(
    root: Path,
    current: dict[str, Any],
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    snapshot = _main_snapshot(current)
    recorded = None
    kind = None
    if snapshot is not None:
        kind = snapshot.get("kind")
        commit = snapshot.get("commit")
        if isinstance(commit, str) and GIT_SHA_RE.fullmatch(commit.lower()):
            recorded = commit.lower()
    summary = {
        "git_head": None,
        "git_head_ref": None,
        "recorded_main_sha": recorded,
        "recorded_main_kind": kind if isinstance(kind, str) else None,
    }
    if not _is_git_repo(root):
        return summary
    git_head, git_ref = _compared_git_sha(root)
    summary["git_head"] = git_head
    summary["git_head_ref"] = git_ref
    if git_head is None:
        errors.append(_issue("ERROR", "GIT_HEAD_UNREADABLE", "origin/main and HEAD could not be read", CURRENT_STATE_REL))
        return summary
    if recorded is None:
        errors.append(
            _issue(
                "ERROR",
                "MISSING_MAIN_SNAPSHOT",
                "CURRENT_STATE is missing a 40-character identity=main commit",
                CURRENT_STATE_REL,
            )
        )
        return summary
    if kind != REFRESH_BASE_KIND:
        errors.append(
            _issue(
                "ERROR",
                "MAIN_SHA_CLAIMED_AS_LIVE_HEAD",
                "main SHA must be labelled refresh_base; a live HEAD claim expires on the next merge",
                CURRENT_STATE_REL,
            )
        )
        return summary
    if recorded == git_head:
        return summary
    if _git_is_ancestor(root, recorded, git_head):
        warnings.append(
            _issue(
                "WARNING",
                "MAIN_SHA_BEHIND_HEAD",
                f"refresh_base {recorded} is behind {git_ref} {git_head}",
                CURRENT_STATE_REL,
            )
        )
        return summary
    errors.append(
        _issue(
            "ERROR",
            "MAIN_SHA_NOT_ANCESTOR_OF_HEAD",
            f"refresh_base {recorded} is not an ancestor of {git_ref} {git_head}",
            CURRENT_STATE_REL,
        )
    )
    return summary


def _failed_report(root: Path, checks: list[dict[str, Any]], errors: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "current-freshness-report-v1",
        "root": str(root),
        "status": "FAIL",
        "checks": checks,
        "errors": errors,
        "warnings": [],
        "summary": {"error_count": len(errors), "warning_count": 0, "pointer_count": 0},
    }


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
        return _failed_report(root, checks, errors)

    try:
        current = load_json(root / CURRENT_STATE_REL)
        history = load_json(root / "governance/CURRENT_STATE_HISTORY.json")
        pointers = load_json(root / "governance/current_pointers.json")
        registry = load_json(root / "governance/tool_registry.json")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(_issue("ERROR", "CURRENT_JSON_INVALID", str(exc)))
        return _failed_report(root, checks, errors)

    stub = (root / "current.md").read_text(encoding="utf-8")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")

    if current.get("schema_version") != "governance-current-state-v2":
        errors.append(_issue("ERROR", "CURRENT_SCHEMA", "CURRENT_STATE schema must remain v2", CURRENT_STATE_REL))
    historical_pointer = current.get("historical_context")
    if not isinstance(historical_pointer, dict) or historical_pointer.get("moved_to") != "governance/CURRENT_STATE_HISTORY.json":
        errors.append(_issue("ERROR", "HISTORY_NOT_SEPARATED", "CURRENT_STATE must point to the history snapshot", CURRENT_STATE_REL))
    forbidden_legacy = {"accepted_steps", "archived_run_states", "issue_ledger", "legacy_mainline"}
    if isinstance(historical_pointer, dict) and forbidden_legacy.intersection(historical_pointer):
        errors.append(_issue("ERROR", "LEGACY_CONTEXT_STILL_ACTIVE", "historical ledgers remain inside active current", CURRENT_STATE_REL))
    if "historical_context" not in history:
        errors.append(_issue("ERROR", "HISTORY_SNAPSHOT_INCOMPLETE", "history snapshot lacks historical_context", "governance/CURRENT_STATE_HISTORY.json"))

    for rel in (
        "governance/INDEX.md",
        CURRENT_STATE_REL,
        "governance/current_pointers.json",
        "governance/START_HERE.md",
        "history/root_current_snapshot_20260720.md",
    ):
        if rel not in stub:
            errors.append(_issue("ERROR", "ROOT_STUB_LINK_MISSING", f"root current stub does not link {rel}", "current.md"))
    for label, content, entry_path in (("AGENTS", agents, "AGENTS.md"), ("README", readme, "README.md")):
        for rel in (CURRENT_STATE_REL, "governance/current_pointers.json"):
            if rel not in content:
                errors.append(_issue("ERROR", "ENTRYPOINT_MISMATCH", f"{label} does not name {rel}", entry_path))

    if pointers.get("schema_version") != POINTER_SCHEMA:
        errors.append(_issue("ERROR", "POINTER_SCHEMA", f"schema_version must be {POINTER_SCHEMA}", "governance/current_pointers.json"))
    pointer_rows = pointers.get("pointers")
    if not isinstance(pointer_rows, list):
        errors.append(_issue("ERROR", "POINTER_ROWS_INVALID", "pointers must be a list", "governance/current_pointers.json"))
        pointer_rows = []
    ids = [row.get("pointer_id") for row in pointer_rows if isinstance(row, dict)]
    if len(ids) != len(set(ids)):
        errors.append(_issue("ERROR", "POINTER_ID_DUPLICATE", "pointer_id values must be unique", "governance/current_pointers.json"))

    by_id: dict[str, dict[str, Any]] = {}
    for position, row in enumerate(pointer_rows):
        if not isinstance(row, dict):
            errors.append(_issue("ERROR", "POINTER_ROW_SCHEMA", f"pointer row {position} is not an object", "governance/current_pointers.json"))
            continue
        pointer_id = row.get("pointer_id")
        if isinstance(pointer_id, str):
            by_id[pointer_id] = row
        missing = [field for field in REQUIRED_POINTER_FIELDS if not isinstance(row.get(field), str) or not str(row.get(field)).strip()]
        if missing:
            errors.append(_issue("ERROR", "POINTER_ROW_MISSING_FIELDS", f"row {position} missing {missing}", "governance/current_pointers.json"))
        status = row.get("status")
        if isinstance(status, str) and status not in POINTER_STATUSES:
            errors.append(_issue("ERROR", "POINTER_STATUS_ENUM", f"{pointer_id!r} has invalid status {status!r}", "governance/current_pointers.json"))
        if pointer_id in RETIRED_BACKGROUND_POINTER_IDS:
            errors.append(_issue("ERROR", "RETIRED_BACKGROUND_POINTER_PRESENT", f"retired pointer {pointer_id} returned", "governance/current_pointers.json"))
        score_hits = [key for key in SCORE_KEYS if key in row]
        if score_hits:
            errors.append(_issue("ERROR", "POINTER_SCORE_FORBIDDEN", f"{pointer_id!r} stores runtime score keys {score_hits}", "governance/current_pointers.json"))
        path = _posix(row.get("path"))
        if status in MASQUERADE_STATUSES and path in RESERVED_ACTIVE_PATHS:
            errors.append(_issue("ERROR", "CANDIDATE_MASQUERADES_CURRENT", f"{pointer_id!r} uses a reserved current path", path))
        if path is not None and not (root / path).exists():
            if status in MASQUERADE_STATUSES:
                warnings.append(_issue("WARNING", "PLANNED_PATH_NOT_MATERIALIZED", "planned or candidate pointer is not present yet", path))
            else:
                errors.append(_issue("ERROR", "ACTIVE_POINTER_TARGET_MISSING", "pointer target is missing", path))
        if status == "ACTIVE_CURRENT":
            _validate_active_pointer(root, row, errors)

    for pointer_id, expected_path in REQUIRED_ACTIVE_POINTERS.items():
        row = by_id.get(pointer_id)
        if not row or row.get("status") != "ACTIVE_CURRENT" or row.get("path") != expected_path:
            errors.append(_issue("ERROR", "ACTIVE_POINTER_MISSING", f"{pointer_id} must have one ACTIVE_CURRENT row at {expected_path}", "governance/current_pointers.json"))

    if pointers.get("invariants") != list(EXPECTED_INVARIANTS):
        errors.append(_issue("ERROR", "INVARIANT_SET_DRIFT", "current_pointers invariants no longer match the checker", "governance/current_pointers.json"))

    current_blob = json.dumps(current, ensure_ascii=False, sort_keys=True)
    for expected in (
        "CLEAN-BASELINE-M1-M11-INTEGRATION-20260821",
        "codex/module-runtime-foundation-20260819-r01",
        "cc793c4719fb6470946c70e744f463147989547b",
    ):
        if expected not in current_blob:
            errors.append(_issue("ERROR", "CURRENT_IDENTITY_MISSING", f"CURRENT_STATE does not contain {expected}", CURRENT_STATE_REL))

    tools = registry.get("tools")
    registered_paths = {row.get("path") for row in tools if isinstance(row, dict)} if isinstance(tools, list) else set()
    for rel in DRIFT_CHECKERS:
        if (root / rel).is_file() and rel not in registered_paths:
            errors.append(_issue("ERROR", "CHECKER_REGISTRY_MISSING", f"{rel} exists but is not registered", "governance/tool_registry.json"))

    git_summary = _check_recorded_main_against_git(root, current, errors, warnings)
    return {
        "schema_version": "current-freshness-report-v1",
        "root": str(root),
        "status": "PASS" if not errors else "FAIL",
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "error_count": len(errors),
            "warning_count": len(warnings),
            "pointer_count": len(pointer_rows),
            **git_summary,
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
        f"- git_head_ref: `{summary.get('git_head_ref')}`",
        f"- git_head: `{summary.get('git_head')}`",
        f"- recorded_main_sha: `{summary.get('recorded_main_sha')}`",
        f"- recorded_main_kind: `{summary.get('recorded_main_kind')}`",
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
