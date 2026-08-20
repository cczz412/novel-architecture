from __future__ import annotations

import copy
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
    from mvp import factstore, review_queue_workspace, review_workspace
    from mvp.workspace import ProjectNotFoundError, VersionConflictError, WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:review-queue-alice"
BOB = "auth:review-queue-bob"
TEXTS = {
    "c01-r1": "甲捡起旧钥匙。乙仍在门外。",
    "c01-r2": "甲拿起铜钥匙。乙离开房间。丙关上门。",
    "c02-r1": "丁打开窗户。戊走进院子。",
}
DECIDED_AT = "2026-08-19 22:00:00"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _revision_ref(chapter_id: str, revision_no: int) -> dict:
    text = TEXTS[f"{chapter_id}-r{revision_no}"]
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": _sha(text),
    }


def _fact(
    fact_id: str,
    chapter_id: str,
    quote: str,
    *,
    revision_no: int,
    status: str = "extracted",
    anchor_state: str = "VERIFIED",
) -> dict:
    revision_ref = _revision_ref(chapter_id, revision_no)
    chapter_text = TEXTS[f"{chapter_id}-r{revision_no}"]
    start = chapter_text.index(quote)
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": chapter_id,
        "text": quote,
        "quote": quote,
        "status": status,
        "source": "M5_REVIEW_QUEUE_SYNTHETIC_FIXTURE",
        "note": "",
        "added_at": "2026-08-19 21:00:00",
        "seg": 1,
        "chapter_revision_ref": revision_ref,
        "anchor_ref": (
            {
                **revision_ref,
                "coordinate_basis": (
                    "CHAPTER_REVISION_TEXT_UNICODE_CODEPOINT_0_BASED_HALF_OPEN"
                ),
                "start": start,
                "end": start + len(quote),
                "slice_sha256": _sha(quote),
            }
            if anchor_state == "VERIFIED"
            else None
        ),
        "anchor_state": anchor_state,
        "recheck": (
            {
                "previous_status": "extracted",
                "reason": "evidence_gone",
                "from_revision_no": revision_no,
                "target_revision_no": revision_no + 1,
                "flagged_at": "2026-08-19 21:01:00",
            }
            if status == "needs_recheck"
            else None
        ),
    }


def _current_candidates() -> list[dict]:
    return [
        _fact("f001", "c01", "甲拿起铜钥匙。", revision_no=2),
        _fact("f002", "c01", "乙离开房间。", revision_no=2),
    ]


def _many_candidates(count: int) -> list[dict]:
    return [
        _fact(
            f"f{index:03d}",
            "c01",
            "甲拿起铜钥匙。",
            revision_no=2,
        )
        for index in range(1, count + 1)
    ]


def _mixed_facts() -> list[dict]:
    return [
        *_current_candidates(),
        _fact("f003", "c02", "丁打开窗户。", revision_no=1),
        _fact("f004", "c01", "甲捡起旧钥匙。", revision_no=1),
        _fact(
            "f005",
            "c01",
            "丙关上门。",
            revision_no=2,
            status="confirmed",
        ),
        _fact(
            "f006",
            "c01",
            "丙关上门。",
            revision_no=2,
            status="rejected",
        ),
        _fact(
            "f007",
            "c01",
            "丙关上门。",
            revision_no=2,
            status="needs_recheck",
        ),
        _fact(
            "f008",
            "c01",
            "丙关上门。",
            revision_no=2,
            anchor_state="LEGACY_UNVERIFIED",
        ),
    ]


def _index() -> list[dict]:
    return [_revision_ref("c01", 2), _revision_ref("c02", 1)]


def _inventory(root: Path) -> list[tuple[str, bool, bytes | None]]:
    if not root.exists():
        return []
    return [
        (
            str(path.relative_to(root)),
            path.is_dir(),
            None if path.is_dir() else path.read_bytes(),
        )
        for path in sorted(root.rglob("*"))
    ]


def _seed(workspace, *, facts: list[dict], index: list[dict] | None = None) -> dict:
    mutations = {"facts": facts}
    expected = {"facts": 0}
    if index is not None:
        mutations["chapter_index"] = index
        expected["chapter_index"] = 0
    return workspace.commit("op-review-queue-seed", mutations, expected)


def _review_actions(session: dict) -> list[dict]:
    decisions = ["confirm", "reject"]
    return [
        {
            "action": factstore.build_review_action(
                fact,
                decision=decision,
                operation_id=f"op-session-{decision}-{fact['id']}",
            ),
            "chapter_revision_ref": copy.deepcopy(
                session["chapter_revision_ref"]
            ),
            "decided_at": DECIDED_AT,
        }
        for fact, decision in zip(session["candidates"], decisions)
    ]


def _subprocess_read(runtime_root: Path, project_id: str) -> dict:
    script = """
import json, sys
sys.path.insert(0, sys.argv[1])
from mvp.workspace import WorkspaceRouter
value = WorkspaceRouter(sys.argv[2]).open_project(sys.argv[3], sys.argv[4]).read("facts")
print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(PRODUCT_ROOT),
            str(runtime_root),
            ALICE,
            project_id,
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_mixed_facts_only_list_current_verified_extracted_in_original_order(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "混合候选")
    receipt = _seed(workspace, facts=_mixed_facts(), index=_index())
    before = _inventory(runtime_root)

    session = review_queue_workspace.open_chapter_review_session(workspace, "c01")

    assert session["chapter_revision_ref"] == _revision_ref("c01", 2)
    assert session["facts_snapshot"] == {
        "version": receipt["versions"]["facts"],
        "sha256": receipt["payload_sha256"]["facts"],
    }
    assert session["candidate_count"] == 2
    assert [fact["id"] for fact in session["candidates"]] == ["f001", "f002"]
    assert session["candidates"] == _current_candidates()
    assert _inventory(runtime_root) == before


def test_session_candidates_flow_into_atomic_batch_and_restart_readback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "批次审查")
    _seed(workspace, facts=_current_candidates(), index=_index())
    session = review_queue_workspace.open_chapter_review_session(workspace, "c01")
    commit_calls = 0
    real_commit = workspace.commit

    def recording_commit(*args, **kwargs):
        nonlocal commit_calls
        commit_calls += 1
        return real_commit(*args, **kwargs)

    monkeypatch.setattr(workspace, "commit", recording_commit)
    result = review_workspace.apply_review_batch(
        workspace,
        operation_id="op-session-apply-batch",
        review_actions=_review_actions(session),
        expected_facts_version=session["facts_snapshot"]["version"],
        expected_facts_sha256=session["facts_snapshot"]["sha256"],
    )

    assert commit_calls == 1
    assert result["facts_version"] == session["facts_snapshot"]["version"] + 1
    assert [fact["status"] for fact in result["facts"]] == [
        "confirmed",
        "rejected",
    ]
    assert [receipt["fact_ref"] for receipt in result["receipts"]] == [
        "f001",
        "f002",
    ]
    reopened = _subprocess_read(runtime_root, workspace.project_id)
    assert reopened["version"] == result["facts_version"]
    assert reopened["payload"] == result["facts"]


def test_empty_chapter_returns_empty_session_without_workspace_write(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "空章")
    receipt = _seed(workspace, facts=[], index=_index())
    before = _inventory(runtime_root)

    session = review_queue_workspace.open_chapter_review_session(workspace, "c01")

    assert session["candidate_count"] == 0
    assert session["candidates"] == []
    assert session["chapter_revision_ref"] == _revision_ref("c01", 2)
    assert session["facts_snapshot"] == {
        "version": receipt["versions"]["facts"],
        "sha256": receipt["payload_sha256"]["facts"],
    }
    assert _inventory(runtime_root) == before


def test_facts_change_after_open_is_rejected_by_existing_batch_watermark(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        ALICE, "会话过期"
    )
    _seed(workspace, facts=_current_candidates(), index=_index())
    session = review_queue_workspace.open_chapter_review_session(workspace, "c01")
    changed = copy.deepcopy(workspace.read("facts")["payload"])
    changed[0]["note"] = "作者在别处先改了备注"
    workspace.commit(
        "op-concurrent-facts-change",
        {"facts": changed},
        {"facts": session["facts_snapshot"]},
    )
    before = copy.deepcopy(workspace.read("facts"))

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        review_workspace.apply_review_batch(
            workspace,
            operation_id="op-stale-session-batch",
            review_actions=_review_actions(session),
            expected_facts_version=session["facts_snapshot"]["version"],
            expected_facts_sha256=session["facts_snapshot"]["sha256"],
        )

    assert workspace.read("facts") == before


@pytest.mark.parametrize(
    ("index", "reason"),
    [
        (None, "CHAPTER_INDEX_SNAPSHOT_MISSING"),
        ([{"chapter_id": "c01", "revision_no": 2}], "CHAPTER_INDEX_REF_INVALID:0"),
        (
            [_revision_ref("c01", 2), _revision_ref("c01", 2)],
            "CHAPTER_INDEX_REF_DUPLICATE:c01",
        ),
    ],
    ids=["missing", "bad-shape", "duplicate"],
)
def test_bad_chapter_index_fails_closed(
    tmp_path: Path,
    index,
    reason: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / reason.split(":")[0]).create_project(
        ALICE, "坏 index"
    )
    _seed(workspace, facts=_current_candidates(), index=index)
    before = copy.deepcopy(workspace.read("facts"))

    with pytest.raises(
        review_queue_workspace.ReviewQueueWorkspaceError,
        match=reason,
    ):
        review_queue_workspace.open_chapter_review_session(workspace, "c01")
    with pytest.raises(
        review_queue_workspace.ReviewQueueWorkspaceError,
        match=reason,
    ):
        review_queue_workspace.read_chapter_review_page(
            workspace,
            "c01",
            10,
            None,
        )

    assert workspace.read("facts") == before


def test_path_and_cross_author_project_guess_fail_closed(tmp_path: Path) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project(ALICE, "同名项目")
    _seed(alice, facts=_current_candidates(), index=_index())
    bob = router.create_project(BOB, "同名项目")

    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project(BOB, alice.project_id)
    with pytest.raises(
        review_queue_workspace.ReviewQueueWorkspaceError,
        match="CHAPTER_INDEX_SNAPSHOT_MISSING",
    ):
        review_queue_workspace.open_chapter_review_session(bob, "c01")
    caller_path = tmp_path / "caller-project"
    with pytest.raises(
        review_queue_workspace.ReviewQueueWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        review_queue_workspace.open_chapter_review_session(  # type: ignore[arg-type]
            caller_path,
            "c01",
        )
    assert not caller_path.exists()


def test_two_hundred_fifty_candidates_page_without_gap_duplicate_or_write(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "大章分页")
    facts = _many_candidates(250)
    receipt = _seed(workspace, facts=facts, index=_index())
    before = _inventory(runtime_root)
    collected: list[str] = []
    cursor = None
    pages: list[dict] = []

    while True:
        page = review_queue_workspace.read_chapter_review_page(
            workspace,
            "c01",
            37,
            cursor,
        )
        pages.append(page)
        collected.extend(fact["id"] for fact in page["items"])
        if not page["has_more"]:
            break
        cursor = page["next_after_fact_ref"]

    assert collected == [f"f{index:03d}" for index in range(1, 251)]
    assert len(collected) == len(set(collected)) == 250
    assert [len(page["items"]) for page in pages] == [37] * 6 + [28]
    assert all(
        page["facts_snapshot"]
        == {
            "version": receipt["versions"]["facts"],
            "sha256": receipt["payload_sha256"]["facts"],
        }
        for page in pages
    )
    assert all(
        page["chapter_revision_ref"] == _revision_ref("c01", 2)
        for page in pages
    )
    assert _inventory(runtime_root) == before


def test_processed_last_item_remains_a_valid_resume_anchor(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "提交后续看")
    _seed(workspace, facts=_many_candidates(5), index=_index())
    first = review_queue_workspace.read_chapter_review_page(
        workspace,
        "c01",
        2,
        None,
    )
    actions = [
        {
            "action": factstore.build_review_action(
                fact,
                decision=decision,
                operation_id=f"op-page-{decision}-{fact['id']}",
            ),
            "chapter_revision_ref": copy.deepcopy(
                first["chapter_revision_ref"]
            ),
            "decided_at": DECIDED_AT,
        }
        for fact, decision in zip(
            first["items"],
            ["confirm", "reject"],
            strict=True,
        )
    ]
    review_workspace.apply_review_batch(
        workspace,
        operation_id="op-apply-first-page",
        review_actions=actions,
        expected_facts_version=first["facts_snapshot"]["version"],
        expected_facts_sha256=first["facts_snapshot"]["sha256"],
    )
    before_resume = _inventory(runtime_root)

    resumed = review_queue_workspace.read_chapter_review_page(
        workspace,
        "c01",
        2,
        first["next_after_fact_ref"],
    )

    assert first["next_after_fact_ref"] == "f002"
    assert [fact["id"] for fact in resumed["items"]] == ["f003", "f004"]
    assert resumed["next_after_fact_ref"] == "f004"
    assert resumed["has_more"] is True
    assert _inventory(runtime_root) == before_resume


def test_page_tail_and_empty_page_are_stable_and_read_only(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "页尾")
    _seed(workspace, facts=_many_candidates(3), index=_index())
    before = _inventory(runtime_root)

    tail = review_queue_workspace.read_chapter_review_page(
        workspace,
        "c01",
        2,
        "f002",
    )
    empty = review_queue_workspace.read_chapter_review_page(
        workspace,
        "c01",
        2,
        "f003",
    )

    assert [fact["id"] for fact in tail["items"]] == ["f003"]
    assert tail["has_more"] is False
    assert tail["next_after_fact_ref"] == "f003"
    assert empty["items"] == []
    assert empty["has_more"] is False
    assert empty["next_after_fact_ref"] == "f003"
    assert _inventory(runtime_root) == before


@pytest.mark.parametrize("page_size", [0, -1, True, "10"])
def test_invalid_page_size_fails_before_workspace_read(
    tmp_path: Path,
    page_size,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        ALICE, "坏页大小"
    )
    before = _inventory(tmp_path / "runtime")

    with pytest.raises(
        review_queue_workspace.ReviewQueueWorkspaceError,
        match="PAGE_SIZE_INVALID",
    ):
        review_queue_workspace.read_chapter_review_page(
            workspace,
            "c01",
            page_size,
            None,
        )
    assert _inventory(tmp_path / "runtime") == before


@pytest.mark.parametrize(
    ("cursor", "reason"),
    [
        ("f999", "AFTER_FACT_REF_NOT_FOUND:f999"),
        ("f003", "AFTER_FACT_REF_CHAPTER_MISMATCH:f003"),
        ("f004", "AFTER_FACT_REF_REVISION_MISMATCH:f004"),
        (42, "AFTER_FACT_REF_INVALID"),
        (" ", "AFTER_FACT_REF_INVALID"),
    ],
)
def test_bad_cross_chapter_old_revision_or_shape_cursor_fails_without_write(
    tmp_path: Path,
    cursor,
    reason: str,
) -> None:
    runtime_root = tmp_path / reason.split(":")[0]
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "坏游标")
    _seed(workspace, facts=_mixed_facts(), index=_index())
    before = _inventory(runtime_root)

    with pytest.raises(
        review_queue_workspace.ReviewQueueWorkspaceError,
        match=reason,
    ):
        review_queue_workspace.read_chapter_review_page(
            workspace,
            "c01",
            10,
            cursor,
        )
    assert _inventory(runtime_root) == before


def test_page_source_watermark_drift_fails_without_adapter_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "水位变化")
    _seed(workspace, facts=_current_candidates(), index=_index())
    before = _inventory(runtime_root)
    real_read = workspace.read
    facts_reads = 0

    def drifting_read(logical_key: str):
        nonlocal facts_reads
        value = real_read(logical_key)
        if logical_key == "facts":
            facts_reads += 1
            if facts_reads == 2:
                value = copy.deepcopy(value)
                value["version"] += 1
                value["sha256"] = "a" * 64
        return value

    monkeypatch.setattr(workspace, "read", drifting_read)
    with pytest.raises(
        review_queue_workspace.ReviewQueueWorkspaceError,
        match="REVIEW_SOURCE_SNAPSHOT_CHANGED",
    ):
        review_queue_workspace.read_chapter_review_page(
            workspace,
            "c01",
            10,
            None,
        )
    assert _inventory(runtime_root) == before
