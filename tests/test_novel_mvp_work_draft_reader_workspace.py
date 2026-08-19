from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import work_draft_reader_workspace, work_draft_workspace
    from mvp.workspace import ProjectNotFoundError, WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:draft-reader-alice"
BOB = "auth:draft-reader-bob"
TEXT_R1 = "第一版作者原文。\n这一行会在第二版消失。"
TEXT_R2 = "  第二版作者原文。\r\n\r\n“换行必须逐字保留。”\n结尾两个空格。  "


def _action(
    operation_id: str,
    *,
    expected_rev: int,
    text: str,
    entry_mode: str,
) -> dict:
    return {
        "operation_id": operation_id,
        "slot_ref": "S-0001",
        "source_outline_ref": "S-0001@outline-r2",
        "expected_rev": expected_rev,
        "entry_mode": entry_mode,
        "author_text": text,
    }


def _save_r1_r2(workspace) -> None:
    work_draft_workspace.save_current_work_draft(
        workspace,
        _action(
            "op-reader-save-r1",
            expected_rev=0,
            text=TEXT_R1,
            entry_mode="typed",
        ),
    )
    work_draft_workspace.save_current_work_draft(
        workspace,
        _action(
            "op-reader-save-r2",
            expected_rev=1,
            text=TEXT_R2,
            entry_mode="edited",
        ),
    )


def _inventory(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def test_r1_to_r2_view_shows_only_current_exact_text_and_restarts_identically(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project(ALICE, "当前工作稿阅读")
    _save_r1_r2(workspace)
    before = _inventory(runtime_root)

    result = work_draft_reader_workspace.read_current_draft_view(workspace)

    assert result["status"] == "READY"
    assert result["encoding"] == "UTF-8"
    assert result["view_identity"] == {
        "name": "AUTHOR_WORKSPACE_CURRENT_DRAFT_VIEW",
        "version": "v1",
        "projection_only": True,
    }
    assert result["draft_workspace"]["version"] == 2
    assert result["draft_identity"] == {
        "contract": "WRITING_DESK_WORK_DRAFT",
        "version": "v1",
        "state": "working",
        "slot_ref": "S-0001",
        "source_outline_ref": "S-0001@outline-r2",
        "work_ref": "S-0001@work",
        "work_rev": 2,
        "entry_mode": "edited",
        "text_sha256": hashlib.sha256(TEXT_R2.encode("utf-8")).hexdigest(),
    }
    assert result["author_text"] == TEXT_R2
    assert TEXT_R2 in result["text"]
    assert TEXT_R2 in result["markdown"]
    assert TEXT_R1 not in result["text"]
    assert "这是可编辑工作稿，不是C1章节、未冻结、未交棒、未进入事实真值" in (
        result["text"]
    )
    assert _inventory(runtime_root) == before

    script = """
import json, sys
sys.path.insert(0, sys.argv[4])
from mvp import work_draft_reader_workspace
from mvp.workspace import WorkspaceRouter
workspace = WorkspaceRouter(sys.argv[1]).open_project(sys.argv[2], sys.argv[3])
print(json.dumps(work_draft_reader_workspace.read_current_draft_view(workspace), ensure_ascii=False, sort_keys=True, separators=(',', ':')))
"""
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(runtime_root),
            ALICE,
            workspace.project_id,
            str(PRODUCT_ROOT),
        ],
        check=False,
        capture_output=True,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert _canonical(json.loads(completed.stdout)) == _canonical(result)


def test_empty_view_is_stable_and_workspace_is_unchanged(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "空工作稿")
    before = _inventory(runtime_root)

    first = work_draft_reader_workspace.read_current_draft_view(workspace)
    second = work_draft_reader_workspace.read_current_draft_view(workspace)

    assert first == second
    assert first["status"] == "EMPTY"
    assert first["draft_workspace"] is None
    assert first["draft_identity"] is None
    assert first["author_text"] is None
    assert "本次未生成、编辑或保存正文" in first["text"]
    assert _inventory(runtime_root) == before


def test_change_between_two_reads_fails_closed_without_reader_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "竞态工作稿")
    work_draft_workspace.save_current_work_draft(
        workspace,
        _action(
            "op-reader-race-r1",
            expected_rev=0,
            text=TEXT_R1,
            entry_mode="typed",
        ),
    )
    real_read = work_draft_workspace.read_current_work_draft
    calls = 0
    inventory_after_external: dict[str, bytes] | None = None

    def racing_read(handle):
        nonlocal calls, inventory_after_external
        calls += 1
        value = real_read(handle)
        if calls == 1:
            current = workspace.read("draft")
            payload = current["payload"]
            payload.update(
                {
                    "work_rev": 2,
                    "entry_mode": "edited",
                    "text": TEXT_R2,
                    "text_sha256": hashlib.sha256(
                        TEXT_R2.encode("utf-8")
                    ).hexdigest(),
                    "last_operation_id": "op-reader-race-r2",
                }
            )
            workspace.commit(
                "op-reader-race-r2",
                {"draft": payload},
                {"draft": current["version"]},
            )
            inventory_after_external = _inventory(runtime_root)
        return value

    monkeypatch.setattr(work_draft_workspace, "read_current_work_draft", racing_read)

    with pytest.raises(
        work_draft_reader_workspace.WorkDraftReaderWorkspaceError,
        match="WORK_DRAFT_CHANGED_DURING_VIEW_READ",
    ):
        work_draft_reader_workspace.read_current_draft_view(workspace)

    assert calls == 2
    assert _inventory(runtime_root) == inventory_after_external


def test_bad_draft_path_and_cross_author_guess_are_rejected_without_writes(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    corrupt = router.create_project(ALICE, "损坏工作稿")
    corrupt.commit(
        "op-reader-corrupt-draft",
        {"draft": {"bad": True}},
        {"draft": 0},
    )
    before_corrupt = _inventory(runtime_root)
    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="WORK_DRAFT_WORKSPACE_ENTRY_INVALID",
    ):
        work_draft_reader_workspace.read_current_draft_view(corrupt)
    assert _inventory(runtime_root) == before_corrupt

    alice = router.create_project(ALICE, "Alice 工作稿")
    _save_r1_r2(alice)
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project(BOB, alice.project_id)

    caller_path = tmp_path / "caller-path"
    with pytest.raises(
        work_draft_reader_workspace.WorkDraftReaderWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        work_draft_reader_workspace.read_current_draft_view(  # type: ignore[arg-type]
            caller_path
        )
    assert not caller_path.exists()


def test_return_value_mutation_cannot_change_saved_current_draft(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "深拷贝工作稿")
    _save_r1_r2(workspace)
    before = _inventory(runtime_root)

    result = work_draft_reader_workspace.read_current_draft_view(workspace)
    result["draft_workspace"]["version"] = 999
    result["draft_identity"]["work_rev"] = 999
    result["view_identity"]["name"] = "CALLER_CHANGED"
    result["author_text"] = "调用方改写"
    result["text"] = "调用方改写"
    result["markdown"] = "调用方改写"
    stored = work_draft_workspace.read_current_work_draft(workspace)

    assert stored["draft_workspace"]["version"] == 2
    assert stored["current_work_draft"]["work_rev"] == 2
    assert stored["current_work_draft"]["text"] == TEXT_R2
    assert _inventory(runtime_root) == before
