from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from isolation import run_git

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "check_tracked_temp.py"
SPEC = importlib.util.spec_from_file_location("check_tracked_temp", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ROOT = Path(__file__).resolve().parents[1]


def _git(root: Path, *args: str) -> None:
    run_git(*args, cwd=root, check=True)


def _seed_git(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "wo7@example.com")
    _git(root, "config", "user.name", "wo7")
    (root / "keep.txt").write_text("ok\n", encoding="utf-8")
    _git(root, "add", "keep.txt")
    _git(root, "commit", "-m", "seed")


def test_live_repository_has_no_unfrozen_tracked_temp() -> None:
    report = MODULE.build_report(ROOT)
    assert report["status"] == "PASS"
    assert report["summary"]["temp_error_count"] == 0


def test_tracked_temp_without_freeze_manifest_is_error(tmp_path: Path) -> None:
    _seed_git(tmp_path)
    leaked = tmp_path / "TEMP" / "scratch.txt"
    leaked.parent.mkdir(parents=True, exist_ok=True)
    leaked.write_text("scratch\n", encoding="utf-8")
    _git(tmp_path, "add", "TEMP/scratch.txt")
    _git(tmp_path, "commit", "-m", "leak")
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "TRACKED_TEMP_WITHOUT_FREEZE_MANIFEST" in {item["code"] for item in report["errors"]}


def test_tracked_temp_with_freeze_manifest_passes(tmp_path: Path) -> None:
    _seed_git(tmp_path)
    folder = tmp_path / "TEMP" / "frozen"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "payload.txt").write_text("payload\n", encoding="utf-8")
    (folder / "MANIFEST.json").write_text("{}\n", encoding="utf-8")
    _git(tmp_path, "add", "TEMP/frozen/payload.txt", "TEMP/frozen/MANIFEST.json")
    _git(tmp_path, "commit", "-m", "frozen")
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "PASS"
    assert report["errors"] == []


def test_tracked_runs_is_warning_not_error(tmp_path: Path) -> None:
    _seed_git(tmp_path)
    path = tmp_path / "runs" / "note.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("run\n", encoding="utf-8")
    _git(tmp_path, "add", "runs/note.txt")
    _git(tmp_path, "commit", "-m", "runs")
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "PASS"
    assert "TRACKED_RUNTIME_LANE" in {item["code"] for item in report["warnings"]}


def test_template_filename_is_not_a_temp_hit(tmp_path: Path) -> None:
    _seed_git(tmp_path)
    folder = tmp_path / "intake" / "14_TEMPLATES"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "CHAT_TEMPLATE.md").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "intake/14_TEMPLATES/CHAT_TEMPLATE.md")
    _git(tmp_path, "commit", "-m", "template")
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "PASS"
    assert report["errors"] == []


def test_git_listing_failure_cannot_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_git(tmp_path)

    def fail_listing(_root: Path) -> list[str]:
        raise RuntimeError("simulated git failure")

    monkeypatch.setattr(MODULE, "_git_ls_files", fail_listing)
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "GIT_LS_FILES_FAILED" in {item["code"] for item in report["errors"]}


def test_empty_fake_tracked_list_cannot_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_git(tmp_path)
    monkeypatch.setattr(MODULE, "_git_ls_files", lambda _root: [])
    report = MODULE.build_report(tmp_path)
    assert report["status"] == "FAIL"
    assert "TRACKED_LIST_INVALID" in {item["code"] for item in report["errors"]}
