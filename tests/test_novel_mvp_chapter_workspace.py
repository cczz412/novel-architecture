from __future__ import annotations

import copy
import hashlib
import inspect
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import chapter_workspace, segment_tool
    from mvp.workspace import (
        OperationConflictError,
        ProjectNotFoundError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


def _revision_ref(chapter_id: str, text: str, revision_no: int = 1) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def _chapter(
    chapter_id: str = "c01",
    *,
    title: str = "第一章 雨夜",
    text: str | None = None,
    revision_no: int = 1,
) -> dict:
    if text is None:
        text = "沈砚推开院门。" * 110 + "\n\n" + "铜铃忽然响了。" * 110
    return {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": chapter_id,
        "title": title,
        "kind": "draft",
        "text": text,
        "added_at": "2026-08-19 12:00:00",
        "chapter_revision_ref": _revision_ref(chapter_id, text, revision_no),
    }


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def test_persist_restart_readback_and_m2_consumes_c1_v1_objects(
    tmp_path: Path,
) -> None:
    chapters = [_chapter()]
    refs = [copy.deepcopy(chapters[0]["chapter_revision_ref"])]
    runtime_root = tmp_path / "workspace-runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(
        "principal-a", "作者项目"
    )

    receipt = chapter_workspace.persist_c1_current_views(
        workspace,
        "op-c1-save-01",
        chapters,
        refs,
        {"chapters": 0, "chapter_index": 0},
    )
    restarted = WorkspaceRouter(runtime_root).open_project(
        "principal-a", workspace.project_id
    )
    restored = chapter_workspace.read_c1_current_views(restarted)
    c2 = segment_tool.execute(
        {
            "items": restored,
            "options": {
                "seg_min_chars": 620,
                "seg_max_chars": 923,
                "halo_chars": 180,
            },
        }
    )

    assert receipt["status"] == "COMMITTED" and receipt["replayed"] is False
    assert receipt["versions"] == {"chapter_index": 1, "chapters": 1}
    assert _canonical_bytes(restored) == _canonical_bytes(chapters)
    assert c2["items"]
    assert all(item["contract"] == "C2_SEGMENT" for item in c2["items"])
    assert all(item["version"] == "v1" for item in c2["items"])
    assert all(item["chapter_revision_ref"] == refs[0] for item in c2["items"])


@pytest.mark.parametrize("invalid_kind", ["bad_sha", "bad_ref", "duplicate_id"])
def test_invalid_batch_is_rejected_before_any_visible_write(
    tmp_path: Path,
    invalid_kind: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / invalid_kind).create_project(
        "principal-a", "项目"
    )
    chapters = [_chapter()]
    refs = [copy.deepcopy(chapters[0]["chapter_revision_ref"])]
    if invalid_kind == "bad_sha":
        invalid_chapter = _chapter("c02", title="第二章 清晨")
        invalid_ref = copy.deepcopy(invalid_chapter["chapter_revision_ref"])
        invalid_chapter["chapter_revision_ref"]["revision_text_sha256"] = "0" * 64
        invalid_ref["revision_text_sha256"] = "0" * 64
        chapters.append(invalid_chapter)
        refs.append(invalid_ref)
    elif invalid_kind == "bad_ref":
        refs[0]["revision_no"] = 2
    else:
        chapters.append(copy.deepcopy(chapters[0]))
        refs.append(copy.deepcopy(refs[0]))

    with pytest.raises(chapter_workspace.ChapterWorkspaceError):
        chapter_workspace.persist_c1_current_views(
            workspace,
            f"op-{invalid_kind}",
            chapters,
            refs,
            {"chapters": 0, "chapter_index": 0},
        )

    assert workspace.read("chapters") is None
    assert workspace.read("chapter_index") is None


def test_operation_idempotency_and_different_request_conflict(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    chapters = [_chapter()]
    refs = [copy.deepcopy(chapters[0]["chapter_revision_ref"])]
    expected = {"chapters": 0, "chapter_index": 0}

    first = chapter_workspace.persist_c1_current_views(
        workspace, "op-idem", chapters, refs, expected
    )
    replay = chapter_workspace.persist_c1_current_views(
        workspace, "op-idem", chapters, refs, expected
    )
    assert replay["replayed"] is True
    assert replay["generation_id"] == first["generation_id"]

    changed = [_chapter(text="沈砚没有回头。" * 100, revision_no=2)]
    changed_refs = [copy.deepcopy(changed[0]["chapter_revision_ref"])]
    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        chapter_workspace.persist_c1_current_views(
            workspace,
            "op-idem",
            changed,
            changed_refs,
            expected,
        )


def test_version_conflict_and_invalid_update_do_not_overwrite_visible_state(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    chapters = [_chapter()]
    refs = [copy.deepcopy(chapters[0]["chapter_revision_ref"])]
    chapter_workspace.persist_c1_current_views(
        workspace,
        "op-base",
        chapters,
        refs,
        {"chapters": 0, "chapter_index": 0},
    )
    before_chapters = workspace.read("chapters")
    before_index = workspace.read("chapter_index")
    updated = [_chapter(text="第二版正文。" * 120, revision_no=2)]
    updated_refs = [copy.deepcopy(updated[0]["chapter_revision_ref"])]

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        chapter_workspace.persist_c1_current_views(
            workspace,
            "op-stale",
            updated,
            updated_refs,
            {"chapters": 0, "chapter_index": 0},
        )
    assert workspace.read("chapters") == before_chapters
    assert workspace.read("chapter_index") == before_index

    invalid_refs = copy.deepcopy(updated_refs)
    invalid_refs[0]["revision_no"] = 999
    with pytest.raises(
        chapter_workspace.ChapterWorkspaceError,
        match="C1_CURRENT_REVISION_REF_MISMATCH",
    ):
        chapter_workspace.persist_c1_current_views(
            workspace,
            "op-invalid",
            updated,
            invalid_refs,
            {"chapters": 1, "chapter_index": 1},
        )
    assert workspace.read("chapters") == before_chapters
    assert workspace.read("chapter_index") == before_index


def test_author_scope_stays_opaque_and_core_signatures_have_no_identity_or_path(
    tmp_path: Path,
) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project("principal-a", "同名项目")
    bob = router.create_project("principal-b", "同名项目")
    chapters = [_chapter()]
    refs = [copy.deepcopy(chapters[0]["chapter_revision_ref"])]
    chapter_workspace.persist_c1_current_views(
        bob,
        "op-bob",
        chapters,
        refs,
        {"chapters": 0, "chapter_index": 0},
    )

    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("principal-a", bob.project_id)
    assert alice.read("chapters") is None
    assert list(
        inspect.signature(chapter_workspace.persist_c1_current_views).parameters
    ) == [
        "workspace",
        "operation_id",
        "current_views",
        "current_revision_refs",
        "expected_versions",
    ]
    assert list(
        inspect.signature(chapter_workspace.read_c1_current_views).parameters
    ) == ["workspace"]
