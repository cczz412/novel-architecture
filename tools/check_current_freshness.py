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
    "产品共同背景现行只认 R14；R13 留 Git 作 SUPERSEDED_HISTORICAL。",
    "原子需求现行只认 R03／142 条唯一 ID；R02 留 Git 作 SUPERSEDED_HISTORICAL。",
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
    pointer = _posix(row.get("current_pointer"))
    if pointer is None:
        errors.append(
            _issue(
                "ERROR",
                "EXTERNAL_REPORT_POINTER_MISSING",
                "external_report_background must declare current_pointer",
                "governance/current_pointers.json",
            )
        )
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
    if path == CURRENT_STATE_REL or pointer_id == "repository_current":
        return
    if path.endswith("/00_READ_ME_FIRST.md") and "/shared-context/" in path:
        _validate_product_background_row(root, row, errors)
        return
    if path == ATOMIC_CURRENT_REL or pointer_id == "atomic_expectations":
        _validate_atomic_expectations_row(root, row, errors)
        return
    if path == TEST_DESIGN_REL or pointer_id == "atomic_test_design":
        _validate_test_design_row(root, row, errors)
        return
    if path == DESIGN_REGISTRY_REL or pointer_id == "design_registry":
        _validate_design_registry_row(root, row, errors)
        return
    if pointer_id == "external_report_background":
        _validate_external_report_row(root, row, errors)


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
