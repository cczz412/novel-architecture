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
    from mvp import chapter_workspace, segment, segment_tool, segment_workspace
    from mvp.workspace import (
        InvalidLogicalKeyError,
        OperationConflictError,
        ProjectNotFoundError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


OPTIONS = {"seg_min_chars": 80, "seg_max_chars": 120, "halo_chars": 20}


def _revision_ref(chapter_id: str, text: str, revision_no: int = 1) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def _chapter(
    chapter_id: str,
    text: str,
    *,
    revision_no: int = 1,
) -> dict:
    return {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": chapter_id,
        "title": f"第{chapter_id[1:]}章",
        "kind": "draft",
        "text": text,
        "added_at": "2026-08-19 14:00:00",
        "chapter_revision_ref": _revision_ref(chapter_id, text, revision_no),
    }


def _chapters() -> list[dict]:
    return [
        _chapter("c01", "短章也必须保留。"),
        _chapter("c02", "这是一个不可拆的长自然段。" * 30),
    ]


def _save_chapters(workspace, chapters: list[dict], *, operation_id: str = "op-c1"):
    return chapter_workspace.persist_c1_current_views(
        workspace,
        operation_id,
        chapters,
        [copy.deepcopy(item["chapter_revision_ref"]) for item in chapters],
        {"chapters": 0, "chapter_index": 0},
    )


def _persist_segments(workspace, operation_id: str, expected_version: int):
    return segment_workspace.persist_current_segments(
        workspace,
        operation_id,
        OPTIONS["seg_min_chars"],
        OPTIONS["seg_max_chars"],
        OPTIONS["halo_chars"],
        expected_version,
    )


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def test_multichapter_persist_restart_and_source_identity(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(
        "principal-a", "作者项目"
    )
    chapters = _chapters()
    _save_chapters(workspace, chapters)

    receipt = _persist_segments(workspace, "op-m2", 0)
    stored = workspace.read("segments")["payload"]
    restarted = WorkspaceRouter(runtime_root).open_project(
        "principal-a", workspace.project_id
    )
    restored = segment_workspace.read_current_segments(restarted)

    assert receipt["status"] == "COMMITTED" and receipt["versions"] == {"segments": 1}
    assert _canonical_bytes(restored) == _canonical_bytes(stored)
    assert restored["receipt"]["input_count"] == 2
    assert [
        row["chapter_revision_ref"]["chapter_id"]
        for row in restored["receipt"]["chapter_receipts"]
    ] == ["c01", "c02"]
    assert _canonical_bytes(restored["receipt"]["chapter_receipts"]) == _canonical_bytes(
        stored["receipt"]["chapter_receipts"]
    )
    assert len(restored["items"]) == 2
    assert {item["chapter_revision_ref"]["chapter_id"] for item in restored["items"]} == {
        "c01",
        "c02",
    }
    assert len(restored["items"][1]["text"]) > OPTIONS["seg_max_chars"]
    assert restored["source_identity"] == {
        "chapters": {
            "version": workspace.read("chapters")["version"],
            "sha256": workspace.read("chapters")["sha256"],
        },
        "chapter_index": {
            "version": workspace.read("chapter_index")["version"],
            "sha256": workspace.read("chapter_index")["sha256"],
        },
    }


@pytest.mark.parametrize("corruption", ["bad_sha", "ref_drift", "empty_batch"])
def test_bad_source_rejects_whole_batch_without_segments(
    tmp_path: Path,
    corruption: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    chapters = _chapters()
    refs = [copy.deepcopy(item["chapter_revision_ref"]) for item in chapters]
    if corruption == "bad_sha":
        chapters[1]["chapter_revision_ref"]["revision_text_sha256"] = "0" * 64
        refs[1]["revision_text_sha256"] = "0" * 64
    elif corruption == "ref_drift":
        refs[1]["revision_no"] = 999
    else:
        chapters = []
        refs = []
    workspace.commit(
        "op-corrupt-source",
        {"chapters": chapters, "chapter_index": refs},
        {"chapters": 0, "chapter_index": 0},
    )

    with pytest.raises(
        segment_workspace.SegmentWorkspaceError,
        match="M2_SOURCE_STATE_INVALID",
    ):
        _persist_segments(workspace, "op-m2-bad", 0)
    assert workspace.read("segments") is None


def test_missing_source_and_bad_options_never_create_segments(
    tmp_path: Path,
) -> None:
    missing = WorkspaceRouter(tmp_path / "missing").create_project(
        "principal-a", "项目"
    )
    with pytest.raises(
        segment_workspace.SegmentWorkspaceError,
        match="M2_SOURCE_STATE_MISSING",
    ):
        _persist_segments(missing, "op-missing", 0)
    assert missing.read("segments") is None

    bad_options = WorkspaceRouter(tmp_path / "bad-options").create_project(
        "principal-a", "项目"
    )
    _save_chapters(bad_options, _chapters())
    with pytest.raises(
        segment_workspace.SegmentWorkspaceError,
        match="M2_SEGMENTATION_REJECTED",
    ):
        segment_workspace.persist_current_segments(
            bad_options,
            "op-bad-options",
            0,
            100,
            20,
            0,
        )
    assert bad_options.read("segments") is None


def test_upstream_revision_makes_saved_segments_stale(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    _save_chapters(workspace, _chapters())
    _persist_segments(workspace, "op-m2", 0)
    before_segments = workspace.read("segments")
    updated = [
        _chapter("c01", "短章第二版。", revision_no=2),
        _chapter("c02", "这是一个不可拆的长自然段。" * 30),
    ]
    chapter_workspace.persist_c1_current_views(
        workspace,
        "op-c1-v2",
        updated,
        [copy.deepcopy(item["chapter_revision_ref"]) for item in updated],
        {"chapters": 1, "chapter_index": 1},
    )

    with pytest.raises(
        segment_workspace.SegmentWorkspaceStaleError,
        match="SEGMENTS_STALE",
    ):
        segment_workspace.read_current_segments(workspace)
    assert workspace.read("segments") == before_segments


def test_source_change_during_segmentation_is_rejected_before_commit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    chapters = _chapters()
    _save_chapters(workspace, chapters)
    real_execute = segment_tool.execute

    def execute_and_change_source(request: dict) -> dict:
        result = real_execute(request)
        updated = [
            _chapter("c01", "并发第二版。", revision_no=2),
            copy.deepcopy(chapters[1]),
        ]
        chapter_workspace.persist_c1_current_views(
            workspace,
            "op-concurrent-c1",
            updated,
            [copy.deepcopy(item["chapter_revision_ref"]) for item in updated],
            {"chapters": 1, "chapter_index": 1},
        )
        return result

    monkeypatch.setattr(segment_tool, "execute", execute_and_change_source)
    with pytest.raises(
        segment_workspace.SegmentWorkspaceStaleError,
        match="SEGMENTS_SOURCE_CHANGED_DURING_RUN",
    ):
        _persist_segments(workspace, "op-race", 0)
    assert workspace.read("segments") is None


def test_idempotency_operation_conflict_and_version_conflict_do_not_overwrite(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    _save_chapters(workspace, _chapters())
    first = _persist_segments(workspace, "op-idem", 0)
    replay = _persist_segments(workspace, "op-idem", 0)
    assert replay["replayed"] is True
    assert replay["generation_id"] == first["generation_id"]
    before = workspace.read("segments")

    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        segment_workspace.persist_current_segments(
            workspace,
            "op-idem",
            90,
            140,
            25,
            0,
        )
    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        _persist_segments(workspace, "op-stale-version", 0)
    with pytest.raises(
        segment_workspace.SegmentWorkspaceError,
        match="M2_SEGMENTATION_REJECTED",
    ):
        segment_workspace.persist_current_segments(
            workspace,
            "op-invalid-options",
            0,
            100,
            20,
            1,
        )
    assert workspace.read("segments") == before


def test_author_scope_signatures_and_unknown_key_guard_remain(
    tmp_path: Path,
) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project("principal-a", "同名项目")
    bob = router.create_project("principal-b", "同名项目")
    _save_chapters(bob, _chapters())
    _persist_segments(bob, "op-bob-m2", 0)

    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("principal-a", bob.project_id)
    assert alice.read("segments") is None
    with pytest.raises(InvalidLogicalKeyError, match="LOGICAL_KEY_NOT_ALLOWED"):
        alice.read("segmentz")
    assert list(
        inspect.signature(segment_workspace.persist_current_segments).parameters
    ) == [
        "workspace",
        "operation_id",
        "seg_min_chars",
        "seg_max_chars",
        "halo_chars",
        "expected_segments_version",
    ]
    assert list(inspect.signature(segment_workspace.read_current_segments).parameters) == [
        "workspace"
    ]


def test_second_chapter_coverage_failure_never_persists_first_chapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    _save_chapters(workspace, _chapters())
    real_segment_chapter = segment.segment_chapter

    def corrupt_second(chapter: dict, lo: int, hi: int, halo: int) -> list[dict]:
        rows = real_segment_chapter(chapter, lo, hi, halo)
        if chapter["id"] == "c02":
            rows[0]["start"] += 1
            rows[0]["end"] += 1
        return rows

    monkeypatch.setattr(segment, "segment_chapter", corrupt_second)
    with pytest.raises(
        segment_workspace.SegmentWorkspaceError,
        match="M2_SEGMENTATION_REJECTED:CHAPTER_COVERAGE_INVALID:c02",
    ):
        _persist_segments(workspace, "op-second-bad", 0)
    assert workspace.read("segments") is None
