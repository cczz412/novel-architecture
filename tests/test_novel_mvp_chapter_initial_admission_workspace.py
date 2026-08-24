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
    from contracts import validate_c11_chapter_revision_ledger as c11_contract
    from contracts.validate_c10_intake_material_identity import validate_record
    from mvp import (
        chapter_initial_admission_workspace,
        chapter_workspace,
        segment_tool,
        work_draft_workspace,
    )
    from mvp.workspace import (
        InjectedWorkspaceCrash,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


TEXT = ("雨落在旧驿站的铜瓦上。" * 70) + "\n\n" + ("林乔拆开那封信。" * 70)
COMMITTED_AT = "2026-08-20T01:30:00+08:00"
STATE_KEYS = {
    "chapter_sources",
    "chapter_materials",
    "chapter_revisions",
    "chapters",
    "chapter_index",
    "chapter_admission_operations",
}


def _save_draft(workspace, *, text: str = TEXT) -> dict:
    return work_draft_workspace.save_current_work_draft(
        workspace,
        {
            "operation_id": "op-work-r1",
            "slot_ref": "S-0001",
            "source_outline_ref": "S-0001@outline-r2",
            "expected_rev": 0,
            "entry_mode": "typed",
            "author_text": text,
        },
    )


def _handover(
    *,
    operation_id: str = "op-handover-initial-01",
    work_rev: int = 1,
    work_ref: str = "S-0001@work",
    slot_ref: str = "S-0001",
    source_outline_ref: str = "S-0001@outline-r2",
    chapter_title: str = "雨夜来信",
) -> dict:
    return {
        "contract": "WORK_DRAFT_HANDOVER_ACTION",
        "version": "v2",
        "operation_id": operation_id,
        "actor": "author",
        "intent": "adopt_as_manuscript",
        "work_ref": work_ref,
        "work_rev": work_rev,
        "slot_ref": slot_ref,
        "source_outline_ref": source_outline_ref,
        "chapter_title": chapter_title,
        "target_contract": "C1_CHAPTER_DOC",
        "target_planstore_result": "handover_parts",
    }


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _seed_next_slot_draft(workspace) -> None:
    text = "第二章作者工作稿。" * 90
    workspace.commit(
        "op-seed-next-slot-draft",
        {
            "draft": {
                "contract": "WRITING_DESK_WORK_DRAFT",
                "version": "v1",
                "work_ref": "S-0002@work",
                "slot_ref": "S-0002",
                "source_outline_ref": "S-0002@outline-r1",
                "work_rev": 2,
                "state": "working",
                "entry_mode": "typed",
                "text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "last_operation_id": "op-seed-next-slot-draft",
            }
        },
        {"draft": 1},
    )


def test_initial_handover_commits_c10_c11_c1_and_restarts_into_m2(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime).create_project("author:alice", "作者项目")
    _save_draft(workspace)

    receipt = chapter_initial_admission_workspace.commit_initial_work_draft(
        workspace,
        _handover(),
        COMMITTED_AT,
    )

    assert receipt["status"] == "AW_COMMITTED_PLANSTORE_PENDING"
    assert receipt["replayed"] is False
    assert receipt["chapter_id"] == "c01"
    assert receipt["planstore_write"] == 0
    assert set(receipt["workspace_state"]) == STATE_KEYS
    assert {row["version"] for row in receipt["workspace_state"].values()} == {1}

    reopened = WorkspaceRouter(runtime).open_project(
        "author:alice", workspace.project_id
    )
    resolved = chapter_initial_admission_workspace.resolve_initial_admission(
        reopened, "op-handover-initial-01"
    )
    material = resolved["material"]
    ledger = resolved["ledger"]
    chapter = resolved["chapter"]
    assert validate_record(copy.deepcopy(material)) == material
    assert (
        c11_contract.validate_initial_commit(ledger, [material])
        == "C10_CONFIRMED_CHAPTER_ELIGIBLE"
    )
    assert ledger["revisions"][0]["title"] == "雨夜来信"
    assert ledger["revisions"][0]["committed_at"] == COMMITTED_AT
    assert chapter == chapter_workspace.read_c1_current_views(reopened)[0]
    assert chapter["text"] == TEXT
    assert chapter["added_at"] == "2026-08-20 01:30:00"

    c2 = segment_tool.execute(
        {
            "items": [chapter],
            "options": {
                "seg_min_chars": 620,
                "seg_max_chars": 923,
                "halo_chars": 180,
            },
        }
    )
    assert c2["items"]
    assert all(
        item["chapter_revision_ref"] == chapter["chapter_revision_ref"]
        for item in c2["items"]
    )


def test_exact_replay_is_read_only_and_changed_request_conflicts(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime).create_project("author:alice", "项目")
    _save_draft(workspace)
    action = _handover()
    first = chapter_initial_admission_workspace.commit_initial_work_draft(
        workspace, action, COMMITTED_AT
    )
    before = _tree_bytes(runtime)

    replay = chapter_initial_admission_workspace.commit_initial_work_draft(
        workspace, action, COMMITTED_AT
    )

    assert replay["replayed"] is True
    assert replay["chapter_revision_ref"] == first["chapter_revision_ref"]
    assert _tree_bytes(runtime) == before
    with pytest.raises(
        chapter_initial_admission_workspace.ChapterInitialAdmissionError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        chapter_initial_admission_workspace.commit_initial_work_draft(
            workspace,
            _handover(chapter_title="另一标题"),
            COMMITTED_AT,
        )
    assert _tree_bytes(runtime) == before


def test_next_valid_slot_gets_c02_without_overwriting_c01(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "author:alice", "项目"
    )
    _save_draft(workspace)
    first = chapter_initial_admission_workspace.commit_initial_work_draft(
        workspace, _handover(), COMMITTED_AT
    )
    first_chapter = copy.deepcopy(workspace.read("chapters")["payload"][0])
    _seed_next_slot_draft(workspace)

    second = chapter_initial_admission_workspace.commit_initial_work_draft(
        workspace,
        _handover(
            operation_id="op-handover-initial-02",
            work_rev=2,
            work_ref="S-0002@work",
            slot_ref="S-0002",
            source_outline_ref="S-0002@outline-r1",
            chapter_title="第二章 潮声",
        ),
        "2026-08-20T02:00:00+08:00",
    )

    assert first["chapter_id"] == "c01"
    assert second["chapter_id"] == "c02"
    chapters = chapter_workspace.read_c1_current_views(workspace)
    assert [chapter["id"] for chapter in chapters] == ["c01", "c02"]
    assert chapters[0] == first_chapter
    assert workspace.read("chapter_revisions")["payload"][
        "next_chapter_number"
    ] == 3


def test_same_slot_new_work_revision_is_not_misclassified_as_new_initial(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime).create_project("author:alice", "项目")
    _save_draft(workspace)
    chapter_initial_admission_workspace.commit_initial_work_draft(
        workspace, _handover(), COMMITTED_AT
    )
    work_draft_workspace.save_current_work_draft(
        workspace,
        {
            "operation_id": "op-work-r2",
            "slot_ref": "S-0001",
            "source_outline_ref": "S-0001@outline-r3",
            "expected_rev": 1,
            "entry_mode": "edited",
            "author_text": TEXT + "\n作者补了一段。",
        },
    )
    before = {
        key: copy.deepcopy(workspace.read(key))
        for key in STATE_KEYS
    }

    with pytest.raises(
        chapter_initial_admission_workspace.ChapterInitialAdmissionError,
        match="SLOT_ALREADY_HAS_INITIAL_CHAPTER",
    ):
        chapter_initial_admission_workspace.commit_initial_work_draft(
            workspace,
            _handover(
                operation_id="op-handover-replace-misroute",
                work_rev=2,
                source_outline_ref="S-0001@outline-r3",
            ),
            "2026-08-20T02:10:00+08:00",
        )
    assert {key: workspace.read(key) for key in STATE_KEYS} == before


def test_stale_or_empty_work_draft_has_zero_admission_writes(tmp_path: Path) -> None:
    stale = WorkspaceRouter(tmp_path / "stale").create_project(
        "author:alice", "项目"
    )
    _save_draft(stale)
    with pytest.raises(
        work_draft_workspace.WorkDraftWorkspaceError,
        match="STALE_WORK_REVISION",
    ):
        chapter_initial_admission_workspace.commit_initial_work_draft(
            stale, _handover(work_rev=2), COMMITTED_AT
        )
    assert all(stale.read(key) is None for key in STATE_KEYS)

    empty = WorkspaceRouter(tmp_path / "empty").create_project(
        "author:alice", "项目"
    )
    _save_draft(empty, text="")
    with pytest.raises(
        chapter_initial_admission_workspace.ChapterInitialAdmissionError,
        match="INITIAL_CHAPTER_TEXT_EMPTY",
    ):
        chapter_initial_admission_workspace.commit_initial_work_draft(
            empty, _handover(), COMMITTED_AT
        )
    assert all(empty.read(key) is None for key in STATE_KEYS)


def test_draft_change_at_commit_guard_rejects_all_admission_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "author:alice", "项目"
    )
    _save_draft(workspace)
    original = workspace.commit_guarded

    def race(operation_id, mutations, expected_versions, guard_versions):
        work_draft_workspace.save_current_work_draft(
            workspace,
            {
                "operation_id": "op-racing-edit",
                "slot_ref": "S-0001",
                "source_outline_ref": "S-0001@outline-r3",
                "expected_rev": 1,
                "entry_mode": "edited",
                "author_text": TEXT + "\n竞态编辑。",
            },
        )
        return original(
            operation_id,
            mutations,
            expected_versions,
            guard_versions,
        )

    monkeypatch.setattr(workspace, "commit_guarded", race)
    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        chapter_initial_admission_workspace.commit_initial_work_draft(
            workspace, _handover(), COMMITTED_AT
        )

    assert all(workspace.read(key) is None for key in STATE_KEYS)
    assert workspace.read("draft")["payload"]["work_rev"] == 2


def test_crash_before_pointer_recovers_with_no_partial_admission(
    tmp_path: Path,
) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    workspace = router.create_project("author:alice", "项目")
    _save_draft(workspace)

    def fail(point: str) -> None:
        if point == "after_prepare":
            raise InjectedWorkspaceCrash(point)

    router._set_failure_hook_for_testing(fail)
    with pytest.raises(InjectedWorkspaceCrash, match="after_prepare"):
        chapter_initial_admission_workspace.commit_initial_work_draft(
            workspace, _handover(), COMMITTED_AT
        )
    assert all(workspace.read(key) is None for key in STATE_KEYS)
    router._set_failure_hook_for_testing(None)
    assert workspace.recover()["status"] == "ROLLED_BACK"
    assert all(workspace.read(key) is None for key in STATE_KEYS)

    retry = chapter_initial_admission_workspace.commit_initial_work_draft(
        workspace, _handover(), COMMITTED_AT
    )
    assert retry["chapter_id"] == "c01"


def test_partial_owner_state_and_path_impostor_fail_closed(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "author:alice", "项目"
    )
    _save_draft(workspace)
    workspace.commit(
        "op-partial-state",
        {
            "chapter_sources": {
                "schema": "chapter-sources-v1",
                "sources": {},
            }
        },
        {"chapter_sources": 0},
    )
    before = copy.deepcopy(workspace.read("chapter_sources"))
    with pytest.raises(
        chapter_initial_admission_workspace.ChapterInitialAdmissionError,
        match="CHAPTER_ADMISSION_STATE_PARTIAL",
    ):
        chapter_initial_admission_workspace.commit_initial_work_draft(
            workspace, _handover(), COMMITTED_AT
        )
    assert workspace.read("chapter_sources") == before

    with pytest.raises(
        chapter_initial_admission_workspace.ChapterInitialAdmissionError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        chapter_initial_admission_workspace.commit_initial_work_draft(
            Path("/tmp/not-a-workspace"), _handover(), COMMITTED_AT
        )
    assert list(
        inspect.signature(
            chapter_initial_admission_workspace.commit_initial_work_draft
        ).parameters
    ) == ["workspace", "handover_action", "committed_at"]


def test_source_bytes_and_c1_are_exactly_the_author_work_text(tmp_path: Path) -> None:
    text = "  开头保留空格。\r\n\r\n结尾也保留。  "
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "author:alice", "项目"
    )
    _save_draft(workspace, text=text)
    chapter_initial_admission_workspace.commit_initial_work_draft(
        workspace, _handover(), COMMITTED_AT
    )

    source = next(
        iter(workspace.read("chapter_sources")["payload"]["sources"].values())
    )
    material = next(
        iter(workspace.read("chapter_materials")["payload"]["records"].values())
    )
    chapter = workspace.read("chapters")["payload"][0]
    assert source["decoded_text"] == chapter["text"] == text
    assert source["normalization"] == "none"
    assert material["source_ref"]["start"] == 0
    assert material["source_ref"]["end"] == len(text)
    assert material["source_ref"]["slice_sha256"] == hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()
    assert json.loads(json.dumps(source, ensure_ascii=False)) == source
