from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from isolation import run_git

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "check_current_freshness.py"
SPEC = importlib.util.spec_from_file_location("check_current_freshness", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def seed_repo(root: Path) -> None:
    product = (
        "references/shared-context/"
        "NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/"
        "00_READ_ME_FIRST.md"
    )
    superseded = (
        "references/shared-context/"
        "NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/"
        "00_READ_ME_FIRST.md"
    )
    atomic_entry = (
        "references/atomic-expectations/"
        "ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/00_READ_ME_FIRST.md"
    )
    text = "\n".join(
        [
            "governance/CURRENT_STATE.json",
            "governance/current_pointers.json",
            product,
            "codex/module-runtime-foundation-20260819-r01",
            "cc793c4719fb6470946c70e744f463147989547b",
        ]
    )
    for rel in ("AGENTS.md", "README.md"):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (root / product).parent.mkdir(parents=True, exist_ok=True)
    (root / product).write_text("R14", encoding="utf-8")
    (root / superseded).parent.mkdir(parents=True, exist_ok=True)
    (root / superseded).write_text("R13", encoding="utf-8")
    (root / atomic_entry).parent.mkdir(parents=True, exist_ok=True)
    (root / atomic_entry).write_text("R03", encoding="utf-8")
    dump(
        root / "references/atomic-expectations/CURRENT.json",
        {
            "current_version": "R03",
            "entry_path": "ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/00_READ_ME_FIRST.md",
        },
    )
    (root / "governance").mkdir(parents=True, exist_ok=True)
    (root / "governance/INDEX.md").write_text("index", encoding="utf-8")
    (root / "history").mkdir(parents=True, exist_ok=True)
    (root / "history/root_current_snapshot_20260720.md").write_text("old", encoding="utf-8")
    (root / "current.md").write_text(
        "governance/INDEX.md\n"
        "governance/CURRENT_STATE.json\n"
        "governance/current_pointers.json\n"
        "governance/START_HERE.md\n"
        "history/root_current_snapshot_20260720.md\n",
        encoding="utf-8",
    )
    dump(
        root / "governance/CURRENT_STATE.json",
        {
            "schema_version": "governance-current-state-v2",
            "current_execution": {
                "task": {"task_id": "CLEAN-BASELINE-M1-M11-INTEGRATION-20260821"},
                "candidate": {
                    "branch": "codex/module-runtime-foundation-20260819-r01",
                    "tip": "cc793c4719fb6470946c70e744f463147989547b",
                },
            },
            "historical_context": {"moved_to": "governance/CURRENT_STATE_HISTORY.json"},
        },
    )
    dump(root / "governance/CURRENT_STATE_HISTORY.json", {"historical_context": {"accepted_steps": []}})
    dump(
        root / "governance/current_pointers.json",
        {
            "schema_version": "governance-current-pointers-v1",
            "invariants": list(MODULE.EXPECTED_INVARIANTS),
            "pointers": [
                {
                    "pointer_id": "repository_current",
                    "status": "ACTIVE_CURRENT",
                    "version": "governance-current-state-v2",
                    "path": "governance/CURRENT_STATE.json",
                },
                {
                    "pointer_id": "product_background",
                    "status": "ACTIVE_CURRENT",
                    "version": "R14",
                    "path": product,
                    "supersedes": {
                        "version": "R13",
                        "path": superseded,
                        "status": "SUPERSEDED_HISTORICAL",
                    },
                },
                {
                    "pointer_id": "atomic_expectations",
                    "status": "ACTIVE_CURRENT",
                    "version": "R03",
                    "path": "references/atomic-expectations/CURRENT.json",
                    "entry_path": atomic_entry,
                    "record_count": 142,
                },
                {
                    "pointer_id": "design_registry",
                    "status": "PLANNED",
                    "path": "novel-mvp/design/design_registry.json",
                },
            ],
        },
    )
    dump(root / "governance/tool_registry.json", {"tools": [{"path": "tools/check_current_freshness.py"}]})


def test_clean_fixture_passes_with_only_planned_warning(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "PASS"
    assert report["summary"]["error_count"] == 0
    assert any(item["code"] == "PLANNED_PATH_NOT_MATERIALIZED" for item in report["warnings"])


def test_product_pointer_mismatch_fails(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    pointers = json.loads((tmp_path / "governance/current_pointers.json").read_text(encoding="utf-8"))
    pointers["pointers"][1]["path"] = "references/shared-context/missing/00_READ_ME_FIRST.md"
    dump(tmp_path / "governance/current_pointers.json", pointers)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    codes = {item["code"] for item in report["errors"]}
    assert "PRODUCT_BACKGROUND_MISSING" in codes


def test_checker_is_read_only_without_output_paths(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    MODULE.build_report(tmp_path)
    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert before == after


def test_live_repository_current_freshness_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    report = MODULE.build_report(root)
    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert report["schema_version"] == "current-freshness-report-v1"


def test_duplicate_pointer_id_is_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    pointers = json.loads((tmp_path / "governance/current_pointers.json").read_text(encoding="utf-8"))
    pointers["pointers"].append(dict(pointers["pointers"][0]))
    dump(tmp_path / "governance/current_pointers.json", pointers)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "POINTER_ID_DUPLICATE" in {item["code"] for item in report["errors"]}


def test_pointer_schema_mismatch_is_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    pointers = json.loads((tmp_path / "governance/current_pointers.json").read_text(encoding="utf-8"))
    pointers["schema_version"] = "wrong"
    dump(tmp_path / "governance/current_pointers.json", pointers)
    report = MODULE.build_report(tmp_path)
    assert "POINTER_SCHEMA" in {item["code"] for item in report["errors"]}


def _pointers(root: Path) -> dict:
    return json.loads((root / "governance/current_pointers.json").read_text(encoding="utf-8"))


def test_second_active_product_background_different_pointer_id_is_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    pointers = _pointers(tmp_path)
    product = next(row for row in pointers["pointers"] if row["pointer_id"] == "product_background")
    extra = dict(product)
    extra["pointer_id"] = "product_background_alias"
    pointers["pointers"].append(extra)
    dump(tmp_path / "governance/current_pointers.json", pointers)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "ROLE_CURRENT_NOT_UNIQUE" in {item["code"] for item in report["errors"]}


def test_atomic_expectations_count_mismatch_is_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    pointers = _pointers(tmp_path)
    atomic = next(row for row in pointers["pointers"] if row["pointer_id"] == "atomic_expectations")
    atomic["record_count"] = 141
    dump(tmp_path / "governance/current_pointers.json", pointers)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "ATOMIC_EXPECTATIONS_COUNT" in {item["code"] for item in report["errors"]}


def test_legacy_127_suite_claiming_full_r03_is_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    dump(
        tmp_path / "references/atomic-expectations/TEST_DESIGN_CURRENT.json",
        {
            "coverage": {
                "requirements_total": 142,
                "small_tests_total": 852,
                "legacy_requirements": 127,
                "r03_addendum_requirements": 15,
            }
        },
    )
    pointers = _pointers(tmp_path)
    pointers["pointers"].append(
        {
            "pointer_id": "atomic_test_design",
            "status": "ACTIVE_CURRENT",
            "path": "references/atomic-expectations/TEST_DESIGN_CURRENT.json",
            "covered_expectations": 142,
            "designed_test_cases": 852,
        }
    )
    dump(tmp_path / "governance/current_pointers.json", pointers)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "TEST_DESIGN_MASQUERADE" in {item["code"] for item in report["errors"]}


def test_design_registry_declared_count_mismatch_is_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    dump(
        tmp_path / "novel-mvp/design/design_registry.json",
        {
            "inventory": {
                "document_count": 58,
                "status_counts": {"CURRENT": 20, "HISTORICAL": 5, "SUPERSEDED": 26, "WAITING_REWRITE": 7},
            }
        },
    )
    pointers = _pointers(tmp_path)
    planned = next(row for row in pointers["pointers"] if row["pointer_id"] == "design_registry")
    planned["status"] = "ACTIVE_CURRENT"
    planned["document_count"] = 57
    planned["status_counts"] = {"CURRENT": 19, "HISTORICAL": 5, "SUPERSEDED": 26, "WAITING_REWRITE": 7}
    dump(tmp_path / "governance/current_pointers.json", pointers)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "DESIGN_REGISTRY_COUNT_MISMATCH" in {item["code"] for item in report["errors"]}


def test_invariant_set_drift_is_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    pointers = _pointers(tmp_path)
    pointers["invariants"] = list(MODULE.EXPECTED_INVARIANTS[:-1])
    dump(tmp_path / "governance/current_pointers.json", pointers)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "INVARIANT_SET_DRIFT" in {item["code"] for item in report["errors"]}


def test_unknown_active_current_row_cannot_escape_validation(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    extra = tmp_path / "references/unknown-current.md"
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_text("unknown\n", encoding="utf-8")
    pointers = _pointers(tmp_path)
    pointers["pointers"].append(
        {
            "pointer_id": "unknown_current",
            "status": "ACTIVE_CURRENT",
            "version": "v1",
            "path": "references/unknown-current.md",
        }
    )
    dump(tmp_path / "governance/current_pointers.json", pointers)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "ACTIVE_CURRENT_UNVALIDATED" in {item["code"] for item in report["errors"]}


def _git(root: Path, *args: str) -> str:
    return run_git(*args, cwd=root, check=True, text=True).stdout.strip()


def _init_git_with_origin_main(root: Path) -> str:
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "freshness@example.invalid")
    _git(root, "config", "user.name", "Freshness Tests")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "seed")
    sha = _git(root, "rev-parse", "HEAD")
    _git(root, "update-ref", "refs/remotes/origin/main", sha)
    return sha


def _write_main_snapshot(root: Path, commit: str, kind: str | None) -> None:
    state = json.loads((root / "governance/CURRENT_STATE.json").read_text(encoding="utf-8"))
    row: dict = {"identity": "main", "commit": commit}
    if kind is not None:
        row["kind"] = kind
    state["refresh_metadata"] = {"source_snapshot": [row]}
    dump(root / "governance/CURRENT_STATE.json", state)


def _advance_origin_main(root: Path) -> str:
    extra = root / "extra.txt"
    extra.write_text("extra\n", encoding="utf-8")
    _git(root, "add", "extra.txt")
    _git(root, "commit", "-qm", "advance")
    sha = _git(root, "rev-parse", "HEAD")
    _git(root, "update-ref", "refs/remotes/origin/main", sha)
    return sha


def test_gitless_fixture_still_skips_head_check(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "PASS"
    assert report["summary"]["git_head"] is None
    assert report["summary"]["recorded_main_sha"] is None


def test_unlabeled_live_head_sha_cannot_pass(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    sha = _init_git_with_origin_main(tmp_path)
    _write_main_snapshot(tmp_path, sha, kind=None)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "MAIN_SHA_CLAIMED_AS_LIVE_HEAD" in {item["code"] for item in report["errors"]}


def test_refresh_base_matching_origin_main_passes(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    sha = _init_git_with_origin_main(tmp_path)
    _write_main_snapshot(tmp_path, sha, kind="refresh_base")
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert report["summary"]["git_head"] == sha
    assert report["summary"]["recorded_main_sha"] == sha
    assert report["summary"]["recorded_main_kind"] == "refresh_base"


def test_refresh_base_behind_origin_main_is_warning_not_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    base = _init_git_with_origin_main(tmp_path)
    _write_main_snapshot(tmp_path, base, kind="refresh_base")
    head = _advance_origin_main(tmp_path)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert report["summary"]["git_head"] == head
    assert report["summary"]["recorded_main_sha"] == base
    assert any(item["code"] == "MAIN_SHA_BEHIND_HEAD" for item in report["warnings"])


def test_refresh_base_unrelated_sha_is_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    _init_git_with_origin_main(tmp_path)
    foreign = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    _write_main_snapshot(tmp_path, foreign, kind="refresh_base")
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "MAIN_SHA_NOT_ANCESTOR_OF_HEAD" in {item["code"] for item in report["errors"]}
