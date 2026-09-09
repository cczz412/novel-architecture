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
    entry_text = "governance/CURRENT_STATE.json\ngovernance/current_pointers.json\n"
    for rel in ("AGENTS.md", "README.md"):
        (root / rel).write_text(entry_text, encoding="utf-8")
    for rel in ("governance/INDEX.md", "governance/START_HERE.md"):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("entry\n", encoding="utf-8")
    history_stub = root / "history/root_current_snapshot_20260720.md"
    history_stub.parent.mkdir(parents=True, exist_ok=True)
    history_stub.write_text("history\n", encoding="utf-8")
    (root / "current.md").write_text(
        "governance/INDEX.md\n"
        "governance/CURRENT_STATE.json\n"
        "governance/current_pointers.json\n"
        "governance/START_HERE.md\n"
        "history/root_current_snapshot_20260720.md\n",
        encoding="utf-8",
    )

    design = {
        "inventory": {
            "document_count": 2,
            "status_counts": {"CURRENT": 1, "HISTORICAL": 1, "SUPERSEDED": 0, "WAITING_REWRITE": 0},
        }
    }
    dump(root / "novel-mvp/design/design_registry.json", design)
    (root / "novel-mvp/design/INDEX.md").write_text("design\n", encoding="utf-8")
    (root / "finetuning").mkdir(parents=True, exist_ok=True)
    dump(root / "finetuning/CURRENT.json", {"status": "abandoned"})

    for rel in MODULE.DRIFT_CHECKERS:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("# checker\n", encoding="utf-8")
    dump(
        root / "governance/tool_registry.json",
        {"tools": [{"path": rel} for rel in MODULE.DRIFT_CHECKERS]},
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
            "schema_version": MODULE.POINTER_SCHEMA,
            "invariants": list(MODULE.EXPECTED_INVARIANTS),
            "pointers": [
                {
                    "pointer_id": "repository_current",
                    "status": "ACTIVE_CURRENT",
                    "version": "governance-current-state-v2",
                    "path": "governance/CURRENT_STATE.json",
                },
                {
                    "pointer_id": "current_freshness_checker",
                    "status": "ACTIVE_CURRENT",
                    "version": "v1",
                    "path": "tools/check_current_freshness.py",
                    "registry_status": "REGISTERED",
                    "suite_entry": "tools/check_drift.py",
                },
                {
                    "pointer_id": "design_registry",
                    "status": "ACTIVE_CURRENT",
                    "version": "R01",
                    "path": "novel-mvp/design/design_registry.json",
                    "index_path": "novel-mvp/design/INDEX.md",
                    "document_count": 2,
                    "status_counts": design["inventory"]["status_counts"],
                    "checker_path": "tools/check_design_currentness.py",
                    "checker_registry_status": "REGISTERED",
                    "suite_entry": "tools/check_drift.py",
                },
                {
                    "pointer_id": "future_candidate",
                    "status": "PLANNED",
                    "path": "future/not-yet-present.json",
                },
            ],
        },
    )


def pointers(root: Path) -> dict:
    return json.loads((root / "governance/current_pointers.json").read_text(encoding="utf-8"))


def test_clean_fixture_passes_with_only_planned_warning(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert any(item["code"] == "PLANNED_PATH_NOT_MATERIALIZED" for item in report["warnings"])


def test_checker_is_read_only(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    before = {path.relative_to(tmp_path).as_posix(): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    MODULE.build_report(tmp_path)
    after = {path.relative_to(tmp_path).as_posix(): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert before == after


def test_registered_content_routing_accepts_partial_migration(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    value = pointers(tmp_path)
    value["invariants"][-1] = (
        "已核对的长期决定、原话和产品规格按 Notion 逐项主存登记读取，"
        "未迁项仍回原 Linear 主存；活动任务与未决问题现场读取 Linear；"
        "工程能力只认 GitHub main 上的正式合同、测试和已合并代码。"
    )
    dump(tmp_path / "governance/current_pointers.json", value)
    assert MODULE.build_report(tmp_path)["status"] == "PASS"


def test_old_linear_only_content_routing_is_rejected(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    value = pointers(tmp_path)
    value["invariants"][-1] = (
        "产品需求、模块边界和 CZ 拍板现场读取 Linear；"
        "工程能力只认 GitHub main 上的正式合同、测试和已合并代码。"
    )
    dump(tmp_path / "governance/current_pointers.json", value)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert {item["code"] for item in report["errors"]} == {"INVARIANT_SET_DRIFT"}


def test_live_repository_current_freshness_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    report = MODULE.build_report(root)
    assert report["schema_version"] == "current-freshness-report-v1"
    assert report["status"] == "PASS"
    assert report["errors"] == []


def test_retired_background_pointer_cannot_return(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    value = pointers(tmp_path)
    value["pointers"].append(
        {
            "pointer_id": "product_background",
            "status": "HISTORICAL_REFERENCE",
            "path": "history/old-product-background.md",
        }
    )
    (tmp_path / "history/old-product-background.md").write_text("old\n", encoding="utf-8")
    dump(tmp_path / "governance/current_pointers.json", value)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "RETIRED_BACKGROUND_POINTER_PRESENT" in {item["code"] for item in report["errors"]}


def test_duplicate_pointer_id_is_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    value = pointers(tmp_path)
    value["pointers"].append(dict(value["pointers"][0]))
    dump(tmp_path / "governance/current_pointers.json", value)
    report = MODULE.build_report(tmp_path)
    assert "POINTER_ID_DUPLICATE" in {item["code"] for item in report["errors"]}


def test_pointer_schema_mismatch_is_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    value = pointers(tmp_path)
    value["schema_version"] = "wrong"
    dump(tmp_path / "governance/current_pointers.json", value)
    report = MODULE.build_report(tmp_path)
    assert "POINTER_SCHEMA" in {item["code"] for item in report["errors"]}


def test_invariant_set_drift_is_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    value = pointers(tmp_path)
    value["invariants"] = value["invariants"][:-1]
    dump(tmp_path / "governance/current_pointers.json", value)
    report = MODULE.build_report(tmp_path)
    assert "INVARIANT_SET_DRIFT" in {item["code"] for item in report["errors"]}


def test_unknown_active_current_cannot_escape_validation(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    target = tmp_path / "unknown/current.json"
    dump(target, {})
    value = pointers(tmp_path)
    value["pointers"].append(
        {"pointer_id": "unknown_current", "status": "ACTIVE_CURRENT", "version": "v1", "path": "unknown/current.json"}
    )
    dump(tmp_path / "governance/current_pointers.json", value)
    report = MODULE.build_report(tmp_path)
    assert "ACTIVE_CURRENT_UNVALIDATED" in {item["code"] for item in report["errors"]}


def test_design_registry_declared_count_mismatch_is_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    value = pointers(tmp_path)
    design = next(row for row in value["pointers"] if row["pointer_id"] == "design_registry")
    design["document_count"] = 3
    dump(tmp_path / "governance/current_pointers.json", value)
    report = MODULE.build_report(tmp_path)
    assert "DESIGN_REGISTRY_COUNT_MISMATCH" in {item["code"] for item in report["errors"]}


def git(root: Path, *args: str) -> str:
    return run_git(*args, cwd=root, check=True, text=True).stdout.strip()


def init_git_with_origin_main(root: Path) -> str:
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "freshness@example.invalid")
    git(root, "config", "user.name", "Freshness Tests")
    git(root, "add", ".")
    git(root, "commit", "-qm", "seed")
    sha = git(root, "rev-parse", "HEAD")
    git(root, "update-ref", "refs/remotes/origin/main", sha)
    return sha


def write_main_snapshot(root: Path, commit: str, kind: str | None) -> None:
    state = json.loads((root / "governance/CURRENT_STATE.json").read_text(encoding="utf-8"))
    row: dict[str, str] = {"identity": "main", "commit": commit}
    if kind is not None:
        row["kind"] = kind
    state["refresh_metadata"] = {"source_snapshot": [row]}
    dump(root / "governance/CURRENT_STATE.json", state)


def advance_origin_main(root: Path) -> str:
    (root / "extra.txt").write_text("extra\n", encoding="utf-8")
    git(root, "add", "extra.txt")
    git(root, "commit", "-qm", "advance")
    sha = git(root, "rev-parse", "HEAD")
    git(root, "update-ref", "refs/remotes/origin/main", sha)
    return sha


def test_gitless_fixture_skips_head_check(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    report = MODULE.build_report(tmp_path)
    assert report["summary"]["git_head"] is None
    assert report["summary"]["recorded_main_sha"] is None


def test_unlabelled_main_sha_cannot_pass(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    sha = init_git_with_origin_main(tmp_path)
    write_main_snapshot(tmp_path, sha, kind=None)
    report = MODULE.build_report(tmp_path)
    assert "MAIN_SHA_CLAIMED_AS_LIVE_HEAD" in {item["code"] for item in report["errors"]}


def test_refresh_base_matching_origin_main_passes(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    sha = init_git_with_origin_main(tmp_path)
    write_main_snapshot(tmp_path, sha, kind="refresh_base")
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "PASS"
    assert report["summary"]["git_head"] == sha


def test_refresh_base_behind_origin_main_is_warning(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    base = init_git_with_origin_main(tmp_path)
    write_main_snapshot(tmp_path, base, kind="refresh_base")
    head = advance_origin_main(tmp_path)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "PASS"
    assert report["summary"]["git_head"] == head
    assert any(item["code"] == "MAIN_SHA_BEHIND_HEAD" for item in report["warnings"])


def test_refresh_base_unrelated_sha_is_error(tmp_path: Path) -> None:
    seed_repo(tmp_path)
    init_git_with_origin_main(tmp_path)
    write_main_snapshot(tmp_path, "a" * 40, kind="refresh_base")
    report = MODULE.build_report(tmp_path)
    assert "MAIN_SHA_NOT_ANCESTOR_OF_HEAD" in {item["code"] for item in report["errors"]}
