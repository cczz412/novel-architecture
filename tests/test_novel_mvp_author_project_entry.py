from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp.author_project_entry import AuthorProjectEntry
    from mvp.workspace import AuthorWorkspace, ProjectNotFoundError, WorkspaceRouter
finally:
    sys.path.pop(0)


def test_entry_lists_two_projects_and_opens_the_selected_one(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    fixture_router = WorkspaceRouter(runtime_root)
    first = fixture_router.create_project("auth:alice", "第一本")
    second = fixture_router.create_project("auth:alice", "第二本")
    second.commit(
        "op-save-private-state",
        {"state": {"private_text": "不会出现在项目列表"}},
        {"state": 0},
    )

    entry = AuthorProjectEntry(runtime_root)
    projects = entry.list("auth:alice")

    assert [row["project_id"] for row in projects] == sorted(
        [first.project_id, second.project_id]
    )
    assert {row["display_name"] for row in projects} == {"第一本", "第二本"}
    assert all(
        set(row) == {"project_id", "display_name", "created_at"} for row in projects
    )
    public_payload = json.dumps(projects, ensure_ascii=False)
    assert "private_text" not in public_payload
    assert str(runtime_root) not in public_payload

    opened = entry.open("auth:alice", second.project_id)

    assert isinstance(opened, AuthorWorkspace)
    assert opened.project_id == second.project_id
    assert opened.author_id == second.author_id
    assert opened.read("state")["payload"] == {"private_text": "不会出现在项目列表"}
    assert not hasattr(opened, "_backend")
    assert not hasattr(entry, "create_project")
    assert not hasattr(entry, "runtime_root")


def test_entry_missing_reads_do_not_create_runtime_directories(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    entry = AuthorProjectEntry(runtime_root)

    assert entry.list("auth:alice") == []
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        entry.open("auth:alice", "p_" + "0" * 32)

    assert not runtime_root.exists()


def test_entry_hides_other_authors_project_like_a_missing_project(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    fixture_router = WorkspaceRouter(runtime_root)
    alice = fixture_router.create_project("auth:alice", "同名项目")
    bob = fixture_router.create_project("auth:bob", "同名项目")
    entry = AuthorProjectEntry(runtime_root)

    assert [row["project_id"] for row in entry.list("auth:alice")] == [alice.project_id]
    with pytest.raises(ProjectNotFoundError) as other_author:
        entry.open("auth:alice", bob.project_id)
    with pytest.raises(ProjectNotFoundError) as missing:
        entry.open("auth:alice", "p_" + "f" * 32)
    with pytest.raises(ProjectNotFoundError) as path_escape:
        entry.open("auth:alice", "../project")

    assert (
        other_author.value.code
        == missing.value.code
        == path_escape.value.code
        == "PROJECT_NOT_FOUND"
    )
