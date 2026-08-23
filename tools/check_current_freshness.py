#!/usr/bin/env python3
"""Read-only current-surface freshness checker.

This checker does not choose product semantics and does not auto-fix files. It only
verifies that the repository exposes one machine current, one pointer registry, a
small root compatibility stub, and aligned human entry points. In a Git checkout it
also compares the recorded main refresh_base SHA with origin/main (falling back to
HEAD) so a live HEAD written as the current signpost cannot PASS.
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
    "governance/CURRENT_STATE.json",
    "governance/CURRENT_STATE_HISTORY.json",
    "governance/current_pointers.json",
    "governance/progress/current-progress.md",
    "AGENTS.md",
    "README.md",
    "governance/tool_registry.json",
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
    "tools/check_traceability.py",
    "tools/check_tracked_temp.py",
    "tools/check_review_identity.py",
    "tools/check_drift.py",
)
EXPECTED_INVARIANTS = (
    "repository_current、product_background 与 atomic_expectations 各自只有一个 ACTIVE_CURRENT。",
    "产品共同背景现行只认 R14；R13 及更早印刷版已退出本 Git，本机备份，身份仍记为 SUPERSEDED_HISTORICAL。",
    "原子需求现行只认 R03／142 条唯一 ID；R02 及更早已退出本 Git，本机备份，身份仍记为 SUPERSEDED_HISTORICAL。",
    "六例设计 CURRENT 的组合覆盖是 142 条／852 例（旧 127×6 加 R03 新增 15×6）；旧 127 套不得单独冒充全 R03。组合覆盖仍是设计，不是执行证明。",
    "候选分支、PLANNED 和 PENDING_WORK_ORDER 不得冒充 main current。",
    "本表不保存运行分数，不替代正式合同、结果票或 CZ 拍板。",
    "设计默认路由只能指向 design_registry 中的 CURRENT；其他状态一律不得指导施工。",
)
ROLE_CURRENT_PATHS = {
    "repository_current": "governance/CURRENT_STATE.json",
    "product_background_suffix": "/00_READ_ME_FIRST.md",
    "product_background_marker": "/shared-context/",
    "atomic_expectations": "references/atomic-expectations/CURRENT.json",
}
SCORE_KEYS = ("score", "pass_rate", "kill_rate")
MASQUERADE_STATUSES = {"CANDIDATE_BRANCH", "PLANNED", "PENDING_WORK_ORDER"}
CURRENT_STATE_REL = "governance/CURRENT_STATE.json"
ATOMIC_CURRENT_REL = "references/atomic-expectations/CURRENT.json"
TEST_DESIGN_REL = "references/atomic-expectations/TEST_DESIGN_CURRENT.json"
DESIGN_REGISTRY_REL = "novel-mvp/design/design_registry.json"
HUMAN_HANDOFF_REL = "governance/progress/current-progress.md"
CURRENT_FRESHNESS_CHECKER_REL = "tools/check_current_freshness.py"
DRIFT_SUITE_REL = "tools/check_drift.py"
EXTERNAL_REPORT_BACKGROUND_REL = "references/external-knowledge-base/README.md"
EXTERNAL_REPORT_CURRENT_REL = "references/external-knowledge-base/CURRENT.json"
ACTIVE_CURRENT_POINTER_IDS = frozenset(
    {
        "repository_current",
        "human_handoff",
        "current_freshness_checker",
        "product_background",
        "external_report_background",
        "atomic_expectations",
        "atomic_test_design",
        "design_registry",
    }
)
REFRESH_BASE_KIND = "refresh_base"
REFRESH_BASE_MARKERS = ("本页复核到", "刷新时的 base")
MAIN_SHA_RE = re.compile(r"`([0-9a-f]{40})`")
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


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _role_family(path: str) -> str | None:
    posix = Path(path).as_posix()
    if posix == ROLE_CURRENT_PATHS["repository_current"]:
        return "repository_current"
    if posix == ROLE_CURRENT_PATHS["atomic_expectations"]:
        return "atomic_expectations"
    if posix.endswith(ROLE_CURRENT_PATHS["product_background_suffix"]) and (
        ROLE_CURRENT_PATHS["product_background_marker"] in posix
    ):
        return "product_background"
    return None


def _check_role_uniqueness(pointer_rows: list[Any], errors: list[dict[str, Any]]) -> None:
    counts = {
        "repository_current": 0,
        "product_background": 0,
        "atomic_expectations": 0,
    }
    for row in pointer_rows:
        if not isinstance(row, dict) or row.get("status") != "ACTIVE_CURRENT":
            continue
        path = _posix(row.get("path"))
        if path is None:
            continue
        family = _role_family(path)
        if family is not None:
            counts[family] += 1
    for family, count in counts.items():
        if count != 1:
            errors.append(
                _issue(
                    "ERROR",
                    "ROLE_CURRENT_NOT_UNIQUE",
                    f"{family} must have exactly one ACTIVE_CURRENT path, found {count}",
                    "governance/current_pointers.json",
                )
            )


def _check_score_keys(row: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    hits = [key for key in SCORE_KEYS if key in row]
    if hits:
        errors.append(
            _issue(
                "ERROR",
                "POINTER_SCORE_FORBIDDEN",
                f"{row.get('pointer_id', 'pointer')} stores runtime score keys {hits}",
                "governance/current_pointers.json",
            )
        )


def _check_candidate_masquerade(row: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    if row.get("status") not in MASQUERADE_STATUSES:
        return
    path = _posix(row.get("path"))
    if path is None:
        return
    if _role_family(path) is not None:
        errors.append(
            _issue(
                "ERROR",
                "CANDIDATE_MASQUERADES_CURRENT",
                f"{row.get('pointer_id', 'pointer')} uses a current-role path with status {row.get('status')}",
                path,
            )
        )


def _validate_product_background_row(
    root: Path,
    row: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    path = _posix(row.get("path"))
    if row.get("version") != "R14" or path is None or "_R14/" not in path:
        errors.append(
            _issue(
                "ERROR",
                "PRODUCT_BACKGROUND_NOT_R14",
                "active product background must be the R14 package",
                path or "governance/current_pointers.json",
            )
        )
    supersedes = row.get("supersedes")
    if not isinstance(supersedes, dict) or supersedes.get("status") != "SUPERSEDED_HISTORICAL":
        errors.append(
            _issue(
                "ERROR",
                "PRODUCT_BACKGROUND_R13_NOT_SUPERSEDED",
                "R13 may only remain as SUPERSEDED_HISTORICAL under product_background.supersedes",
                "governance/current_pointers.json",
            )
        )
        return
    if supersedes.get("version") != "R13":
        errors.append(
            _issue(
                "ERROR",
                "PRODUCT_BACKGROUND_R13_NOT_SUPERSEDED",
                "superseded product background version must be R13",
                "governance/current_pointers.json",
            )
        )
    superseded_path = _posix(supersedes.get("path"))
    retention = supersedes.get("retention")
    if retention == "local_backup_not_in_this_git":
        if superseded_path is not None and "R13" not in superseded_path:
            errors.append(
                _issue(
                    "ERROR",
                    "PRODUCT_BACKGROUND_R13_NOT_SUPERSEDED",
                    "superseded product background path must remain the R13 package",
                    "governance/current_pointers.json",
                )
            )
        return
    if superseded_path is None or "R13" not in superseded_path:
        errors.append(
            _issue(
                "ERROR",
                "PRODUCT_BACKGROUND_R13_NOT_SUPERSEDED",
                "superseded product background path must remain the R13 package",
                "governance/current_pointers.json",
            )
        )
    elif not (root / superseded_path).is_file():
        errors.append(
            _issue(
                "ERROR",
                "ACTIVE_POINTER_TARGET_MISSING",
                "superseded R13 entry is missing",
                superseded_path,
            )
        )


def _validate_atomic_expectations_row(
    root: Path,
    row: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    path = _posix(row.get("path"))
    if path is None:
        return
    target = root / path
    if not target.is_file():
        return
    try:
        document = load_json(target)
    except (OSError, json.JSONDecodeError):
        errors.append(_issue("ERROR", "ATOMIC_EXPECTATIONS_INVALID", "atomic CURRENT.json is not readable JSON", path))
        return
    if document.get("current_version") != "R03":
        errors.append(
            _issue(
                "ERROR",
                "ATOMIC_EXPECTATIONS_VERSION",
                "atomic_expectations current_version must be R03",
                path,
            )
        )
    if row.get("version") != "R03" or row.get("record_count") != 142:
        errors.append(
            _issue(
                "ERROR",
                "ATOMIC_EXPECTATIONS_COUNT",
                "atomic_expectations pointer must declare R03 and record_count 142",
                "governance/current_pointers.json",
            )
        )
    entry = _posix(row.get("entry_path")) or _posix(document.get("entry_path"))
    if entry is None:
        errors.append(
            _issue(
                "ERROR",
                "ATOMIC_EXPECTATIONS_ENTRY_MISSING",
                "atomic_expectations entry_path is missing",
                "governance/current_pointers.json",
            )
        )
        return
    entry_path = Path(entry)
    if not entry_path.is_absolute():
        if path == ATOMIC_CURRENT_REL:
            entry_path = root / "references/atomic-expectations" / entry
        else:
            entry_path = root / entry
        if not entry_path.is_file():
            entry_path = root / entry
    if not entry_path.is_file():
        errors.append(
            _issue(
                "ERROR",
                "ATOMIC_EXPECTATIONS_ENTRY_MISSING",
                "atomic_expectations entry_path is missing",
                entry,
            )
        )


def _validate_test_design_row(
    root: Path,
    row: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    path = _posix(row.get("path"))
    if path is None:
        return
    if path != TEST_DESIGN_REL or row.get("version") != "R03_COMPOSITE_127_PLUS_15":
        errors.append(
            _issue(
                "ERROR",
                "TEST_DESIGN_POINTER_IDENTITY",
                "atomic_test_design must bind the R03 composite TEST_DESIGN_CURRENT registry",
                "governance/current_pointers.json",
            )
        )
    target = root / path
    if not target.is_file():
        return
    try:
        document = load_json(target)
    except (OSError, json.JSONDecodeError):
        errors.append(_issue("ERROR", "TEST_DESIGN_INVALID", "TEST_DESIGN_CURRENT.json is not readable JSON", path))
        return
    coverage = document.get("coverage")
    if not isinstance(coverage, dict):
        errors.append(_issue("ERROR", "TEST_DESIGN_INVALID", "TEST_DESIGN_CURRENT coverage is missing", path))
        return
    declared_requirements = row.get("covered_expectations")
    declared_tests = row.get("designed_test_cases")
    if declared_requirements != coverage.get("requirements_total") or declared_tests != coverage.get(
        "small_tests_total"
    ):
        errors.append(
            _issue(
                "ERROR",
                "TEST_DESIGN_COUNT_MISMATCH",
                "atomic_test_design pointer counts must match TEST_DESIGN_CURRENT coverage",
                "governance/current_pointers.json",
            )
        )
    legacy = row.get("legacy_suite")
    addendum = row.get("r03_addendum")
    split_ok = (
        isinstance(legacy, dict)
        and isinstance(addendum, dict)
        and _is_plain_int(legacy.get("requirements"))
        and _is_plain_int(legacy.get("small_tests"))
        and _is_plain_int(addendum.get("requirements"))
        and _is_plain_int(addendum.get("small_tests"))
        and legacy.get("requirements") + addendum.get("requirements") == coverage.get("requirements_total")
        and legacy.get("small_tests") + addendum.get("small_tests") == coverage.get("small_tests_total")
        and legacy.get("requirements") == coverage.get("legacy_requirements")
        and addendum.get("requirements") == coverage.get("r03_addendum_requirements")
    )
    if not split_ok:
        errors.append(
            _issue(
                "ERROR",
                "TEST_DESIGN_MASQUERADE",
                "old 127-suite counts may not claim full R03 coverage without split identity fields",
                "governance/current_pointers.json",
            )
        )


def _validate_design_registry_row(
    root: Path,
    row: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    path = _posix(row.get("path"))
    if path is None:
        return
    if (
        path != DESIGN_REGISTRY_REL
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
                "design_registry ACTIVE_CURRENT identity or checker binding drifted",
                "governance/current_pointers.json",
            )
        )
    target = root / path
    if not target.is_file():
        return
    try:
        document = load_json(target)
    except (OSError, json.JSONDecodeError):
        errors.append(_issue("ERROR", "DESIGN_REGISTRY_INVALID", "design_registry.json is not readable JSON", path))
        return
    inventory = document.get("inventory")
    if not isinstance(inventory, dict):
        errors.append(_issue("ERROR", "DESIGN_REGISTRY_INVALID", "design_registry inventory is missing", path))
        return
    declared_counts = row.get("status_counts")
    if row.get("document_count") != inventory.get("document_count") or declared_counts != inventory.get(
        "status_counts"
    ):
        errors.append(
            _issue(
                "ERROR",
                "DESIGN_REGISTRY_COUNT_MISMATCH",
                "design_registry pointer inventory copy is stale",
                "governance/current_pointers.json",
            )
        )


def _validate_external_report_row(
    root: Path,
    row: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    path = _posix(row.get("path"))
    pointer = _posix(row.get("current_pointer"))
    if path != EXTERNAL_REPORT_BACKGROUND_REL or pointer != EXTERNAL_REPORT_CURRENT_REL:
        errors.append(
            _issue(
                "ERROR",
                "EXTERNAL_REPORT_POINTER_IDENTITY",
                "external_report_background must bind its registered README and CURRENT.json",
                "governance/current_pointers.json",
            )
        )
    if pointer is None:
        return
    target = root / pointer
    if not target.is_file():
        errors.append(
            _issue(
                "ERROR",
                "ACTIVE_POINTER_TARGET_MISSING",
                "external report CURRENT.json is missing",
                pointer,
            )
        )
        return
    try:
        document = load_json(target)
    except (OSError, json.JSONDecodeError):
        errors.append(_issue("ERROR", "EXTERNAL_REPORT_INVALID", "external report CURRENT.json is not readable JSON", pointer))
        return
    if document.get("current_version") != "R01" or row.get("version") != "R01":
        errors.append(
            _issue(
                "ERROR",
                "EXTERNAL_REPORT_VERSION",
                "external_report_background current_version must be R01",
                pointer,
            )
        )


def _validate_active_current_row(
    root: Path,
    row: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    path = _posix(row.get("path"))
    if path is None:
        return
    pointer_id = row.get("pointer_id")
    if pointer_id not in ACTIVE_CURRENT_POINTER_IDS:
        errors.append(
            _issue(
                "ERROR",
                "ACTIVE_CURRENT_UNVALIDATED",
                f"ACTIVE_CURRENT row {pointer_id!r} has no explicit validator",
                "governance/current_pointers.json",
            )
        )
        return
    version = row.get("version")
    if not isinstance(version, str) or not version.strip():
        errors.append(
            _issue(
                "ERROR",
                "ACTIVE_CURRENT_VERSION_MISSING",
                f"ACTIVE_CURRENT row {pointer_id} must declare a non-empty version",
                "governance/current_pointers.json",
            )
        )

    if pointer_id == "repository_current":
        if path != CURRENT_STATE_REL or version != "governance-current-state-v2":
            errors.append(
                _issue(
                    "ERROR",
                    "REPOSITORY_CURRENT_IDENTITY",
                    "repository_current must bind CURRENT_STATE.json at governance-current-state-v2",
                    "governance/current_pointers.json",
                )
            )
        return
    if pointer_id == "human_handoff":
        if path != HUMAN_HANDOFF_REL:
            errors.append(
                _issue(
                    "ERROR",
                    "HUMAN_HANDOFF_IDENTITY",
                    f"human_handoff must point to {HUMAN_HANDOFF_REL}",
                    "governance/current_pointers.json",
                )
            )
        return
    if pointer_id == "current_freshness_checker":
        if (
            path != CURRENT_FRESHNESS_CHECKER_REL
            or version != "v1"
            or row.get("registry_status") != "REGISTERED"
            or row.get("suite_entry") != DRIFT_SUITE_REL
            or not (root / DRIFT_SUITE_REL).is_file()
        ):
            errors.append(
                _issue(
                    "ERROR",
                    "CURRENT_CHECKER_IDENTITY",
                    "current_freshness_checker must stay registered at v1 and bind the drift-suite entry",
                    "governance/current_pointers.json",
                )
            )
        return
    if pointer_id == "product_background":
        _validate_product_background_row(root, row, errors)
        return
    if pointer_id == "atomic_expectations":
        _validate_atomic_expectations_row(root, row, errors)
        return
    if pointer_id == "atomic_test_design":
        _validate_test_design_row(root, row, errors)
        return
    if pointer_id == "design_registry":
        _validate_design_registry_row(root, row, errors)
        return
    if pointer_id == "external_report_background":
        _validate_external_report_row(root, row, errors)


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
    if GIT_SHA_RE.fullmatch(sha):
        return sha
    return None


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
    for row in snapshots:
        if isinstance(row, dict) and row.get("identity") == "main":
            return row
    return None


def _sha_on_main_line(text: str) -> str | None:
    for line in text.splitlines():
        if "main" not in line.lower() and "`main`" not in line:
            continue
        if not any(token in line for token in ("基准", "刷新时的 base", "本页复核到")):
            continue
        match = MAIN_SHA_RE.search(line)
        if match:
            return match.group(1)
    return None


def _has_refresh_base_markers(text: str) -> bool:
    return any(marker in text for marker in REFRESH_BASE_MARKERS)


def _check_recorded_main_against_git(
    root: Path,
    current: dict[str, Any],
    progress: str,
    index_text: str,
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
        errors.append(
            _issue(
                "ERROR",
                "GIT_HEAD_UNREADABLE",
                "git repository exists but origin/main and HEAD could not be read",
                "governance/CURRENT_STATE.json",
            )
        )
        return summary

    if recorded is None:
        errors.append(
            _issue(
                "ERROR",
                "MISSING_MAIN_SNAPSHOT",
                "CURRENT_STATE refresh_metadata.source_snapshot is missing a 40-char identity=main commit",
                "governance/CURRENT_STATE.json",
            )
        )
        return summary

    progress_sha = _sha_on_main_line(progress)
    if progress_sha is None:
        errors.append(
            _issue(
                "ERROR",
                "PROGRESS_MAIN_SHA_MISSING",
                "progress page has no 40-char main refresh-base SHA",
                "governance/progress/current-progress.md",
            )
        )
    elif progress_sha != recorded:
        errors.append(
            _issue(
                "ERROR",
                "MAIN_SHA_SIGNPOST_MISMATCH",
                "progress main SHA does not match CURRENT_STATE identity=main commit",
                "governance/progress/current-progress.md",
            )
        )

    index_sha = _sha_on_main_line(index_text)
    if index_sha is not None and index_sha != recorded:
        errors.append(
            _issue(
                "ERROR",
                "INDEX_MAIN_SHA_MISMATCH",
                "INDEX.md main SHA does not match CURRENT_STATE identity=main commit",
                "governance/INDEX.md",
            )
        )

    labeled = kind == REFRESH_BASE_KIND and _has_refresh_base_markers(progress)
    if not labeled:
        errors.append(
            _issue(
                "ERROR",
                "MAIN_SHA_CLAIMED_AS_LIVE_HEAD",
                "main SHA must be recorded as refresh_base / 本页复核到; writing a live HEAD that expires on the next merge cannot PASS",
                "governance/CURRENT_STATE.json",
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
                f"refresh_base {recorded} is behind {git_ref} {git_head}; runtime HEAD is reported here, not in the signpost SHA",
                "governance/CURRENT_STATE.json",
            )
        )
        return summary
    errors.append(
        _issue(
            "ERROR",
            "MAIN_SHA_NOT_ANCESTOR_OF_HEAD",
            f"refresh_base {recorded} is not an ancestor of {git_ref} {git_head}",
            "governance/CURRENT_STATE.json",
        )
    )
    return summary


def _execute_invariants(
    root: Path,
    pointers: dict[str, Any],
    pointer_rows: list[Any],
    errors: list[dict[str, Any]],
) -> None:
    declared = pointers.get("invariants")
    if not isinstance(declared, list) or [item for item in declared if isinstance(item, str)] != list(
        EXPECTED_INVARIANTS
    ):
        errors.append(
            _issue(
                "ERROR",
                "INVARIANT_SET_DRIFT",
                "current_pointers invariants[] no longer match the frozen checker set",
                "governance/current_pointers.json",
            )
        )
        return
    _check_role_uniqueness(pointer_rows, errors)
    for row in pointer_rows:
        if not isinstance(row, dict):
            continue
        _check_score_keys(row, errors)
        _check_candidate_masquerade(row, errors)
        if row.get("status") == "ACTIVE_CURRENT":
            _validate_active_current_row(root, row, errors)


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

    if pointers.get("schema_version") != POINTER_SCHEMA:
        errors.append(
            _issue(
                "ERROR",
                "POINTER_SCHEMA",
                f"current_pointers schema_version must be {POINTER_SCHEMA}",
                "governance/current_pointers.json",
            )
        )
    pointer_rows = pointers.get("pointers")
    if not isinstance(pointer_rows, list):
        errors.append(_issue("ERROR", "POINTER_ROWS_INVALID", "pointers must be a list", "governance/current_pointers.json"))
        pointer_rows = []
    ids = [row.get("pointer_id") for row in pointer_rows if isinstance(row, dict)]
    if len(ids) != len(set(ids)):
        errors.append(_issue("ERROR", "POINTER_ID_DUPLICATE", "pointer_id values must be unique", "governance/current_pointers.json"))
    for position, row in enumerate(pointer_rows):
        if not isinstance(row, dict):
            errors.append(
                _issue(
                    "ERROR",
                    "POINTER_ROW_SCHEMA",
                    f"pointer row {position} is not an object",
                    "governance/current_pointers.json",
                )
            )
            continue
        missing = [field for field in REQUIRED_POINTER_FIELDS if not isinstance(row.get(field), str) or not str(row.get(field)).strip()]
        if missing:
            errors.append(
                _issue(
                    "ERROR",
                    "POINTER_ROW_MISSING_FIELDS",
                    f"{row.get('pointer_id', f'row {position}')} missing {missing}",
                    "governance/current_pointers.json",
                )
            )
        status = row.get("status")
        if isinstance(status, str) and status not in POINTER_STATUSES:
            errors.append(
                _issue(
                    "ERROR",
                    "POINTER_STATUS_ENUM",
                    f"{row.get('pointer_id', f'row {position}')} has invalid status {status!r}",
                    "governance/current_pointers.json",
                )
            )

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
    registered_paths = {row.get("path") for row in tools if isinstance(row, dict)}
    for rel in DRIFT_CHECKERS:
        if (root / rel).is_file() and rel not in registered_paths:
            errors.append(
                _issue(
                    "ERROR",
                    "CHECKER_REGISTRY_MISSING",
                    f"{rel} exists but is not registered in tool_registry",
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

    _execute_invariants(root, pointers, pointer_rows, errors)
    index_text = (root / "governance/INDEX.md").read_text(encoding="utf-8")
    git_summary = _check_recorded_main_against_git(
        root,
        current,
        progress,
        index_text,
        errors,
        warnings,
    )

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
