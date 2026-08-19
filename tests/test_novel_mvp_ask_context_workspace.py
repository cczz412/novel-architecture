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
    from mvp import ask_context_workspace, ask_tool
    from mvp.workspace import ProjectNotFoundError, WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:m6-context-alice"
BOB = "auth:m6-context-bob"
TEXT = "院门外传来脚步声。林乔把铜钥匙交给苏晚。苏晚收起钥匙。"
QUOTE = "林乔把铜钥匙交给苏晚"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _ref(*, revision_no: int = 2, text: str = TEXT) -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": revision_no,
        "revision_text_sha256": _sha(text),
    }


def _chapter(*, revision_no: int = 2, text: str = TEXT) -> dict:
    return {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": "c01",
        "title": "第一章 钥匙",
        "kind": "draft",
        "text": text,
        "added_at": "2026-08-19 21:00:00",
        "chapter_revision_ref": _ref(revision_no=revision_no, text=text),
    }


def _fact(
    *,
    revision_no: int = 2,
    revision_text: str = TEXT,
    bad_anchor: bool = False,
) -> dict:
    ref = _ref(revision_no=revision_no, text=revision_text)
    start = revision_text.index(QUOTE)
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": "f001",
        "chapter_id": "c01",
        "text": "林乔把铜钥匙交给苏晚。",
        "quote": QUOTE,
        "status": "confirmed",
        "source": "M6_CONTEXT_WORKSPACE_SYNTHETIC",
        "note": "",
        "added_at": "2026-08-19 21:01:00",
        "seg": 1,
        "decided_at": "2026-08-19 21:02:00",
        "chapter_revision_ref": ref,
        "anchor_ref": {
            **copy.deepcopy(ref),
            "coordinate_basis": ask_tool.COORDINATE_BASIS,
            "start": start,
            "end": start + len(QUOTE),
            "slice_sha256": "0" * 64 if bad_anchor else _sha(QUOTE),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


def _commit_all(workspace, *, facts=None, chapters=None, refs=None) -> dict:
    facts = [_fact()] if facts is None else facts
    chapters = [_chapter()] if chapters is None else chapters
    refs = [_ref()] if refs is None else refs
    return workspace.commit(
        "op-m6-context-base",
        {"facts": facts, "chapter_index": refs, "chapters": chapters},
        {"facts": 0, "chapter_index": 0, "chapters": 0},
    )


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


def test_restart_returns_exact_context_and_three_source_watermarks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project(ALICE, "M6 上下文")
    receipt = _commit_all(workspace)
    restarted = WorkspaceRouter(runtime_root).open_project(ALICE, workspace.project_id)
    before = _inventory(runtime_root)
    read_calls: list[str] = []
    real_read = restarted.read
    monkeypatch.setattr(
        restarted,
        "read",
        lambda logical_key: read_calls.append(logical_key) or real_read(logical_key),
    )

    result = ask_context_workspace.execute(restarted, "钥匙 苏晚", 4, 5)

    assert read_calls == [
        "facts",
        "chapter_index",
        "chapters",
        "facts",
        "chapter_index",
        "facts",
        "chapter_index",
        "chapters",
    ]
    assert result["facts_snapshot"] == {
        "version": 1,
        "sha256": receipt["payload_sha256"]["facts"],
    }
    assert result["chapter_index_snapshot"] == {
        "version": 1,
        "sha256": receipt["payload_sha256"]["chapter_index"],
    }
    assert result["chapters_snapshot"] == {
        "version": 1,
        "sha256": receipt["payload_sha256"]["chapters"],
    }
    evidence = result["m6"]["evidence"][0]
    context = evidence["context"]
    assert context["text"][context["highlight_start"] : context["highlight_end"]] == QUOTE
    assert evidence["quote"] == QUOTE
    assert _inventory(runtime_root) == before
    json.loads(json.dumps(result, ensure_ascii=False))


def test_empty_project_is_stable_and_has_zero_side_effects(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "空项目")
    before = _inventory(runtime_root)

    result = ask_context_workspace.execute(workspace, "钥匙", 3, 3)

    assert result["facts_snapshot"] == {"version": 0, "sha256": None}
    assert result["chapter_index_snapshot"] == {"version": 0, "sha256": None}
    assert result["chapters_snapshot"] == {"version": 0, "sha256": None}
    assert result["m6"]["matches"] == [] and result["m6"]["evidence"] == []
    assert _inventory(runtime_root) == before


@pytest.mark.parametrize("fault", ["missing_chapters", "different_batch", "chapter_sha"])
def test_missing_or_nonclosed_chapter_snapshots_are_rejected(tmp_path: Path, fault: str) -> None:
    workspace = WorkspaceRouter(tmp_path / fault).create_project(ALICE, fault)
    if fault == "missing_chapters":
        workspace.commit(
            "op-missing-chapters",
            {"facts": [_fact()], "chapter_index": [_ref()]},
            {"facts": 0, "chapter_index": 0},
        )
    else:
        chapters = [_chapter()]
        if fault == "chapter_sha":
            chapters[0]["text"] += "漂移"
        _commit_all(workspace, chapters=chapters)
        if fault == "different_batch":
            workspace.commit(
                "op-index-only-v2",
                {"chapter_index": [_ref()]},
                {"chapter_index": 1},
            )

    with pytest.raises(ask_context_workspace.AskContextWorkspaceError):
        ask_context_workspace.execute(workspace, "钥匙", 3, 3)


@pytest.mark.parametrize("fault", ["old_revision", "bad_anchor"])
def test_old_revision_or_bad_anchor_is_rejected_before_query(tmp_path: Path, fault: str) -> None:
    workspace = WorkspaceRouter(tmp_path / fault).create_project(ALICE, fault)
    if fault == "old_revision":
        old_text = TEXT + "旧版"
        facts = [_fact(revision_no=1, revision_text=old_text)]
    else:
        facts = [_fact(bad_anchor=True)]
    _commit_all(workspace, facts=facts)

    with pytest.raises(ask_context_workspace.AskContextWorkspaceError):
        ask_context_workspace.execute(workspace, "钥匙", 3, 3)


def test_snapshot_change_during_query_rejects_whole_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(ALICE, "并发变更")
    _commit_all(workspace)
    real_read = workspace.read
    reads = 0

    def changing_read(logical_key: str):
        nonlocal reads
        reads += 1
        if reads == 4:
            changed = _fact()
            changed["note"] = "查询过程中并发更新"
            workspace.commit(
                "op-mid-query-change",
                {"facts": [changed]},
                {"facts": 1},
            )
        return real_read(logical_key)

    monkeypatch.setattr(workspace, "read", changing_read)

    with pytest.raises(
        ask_context_workspace.AskContextWorkspaceError,
        match="WORKSPACE_SNAPSHOT_CHANGED_DURING_QUERY",
    ):
        ask_context_workspace.execute(workspace, "钥匙", 3, 3)


def test_path_and_cross_author_project_guess_are_rejected(tmp_path: Path) -> None:
    caller_path = tmp_path / "caller-project"
    with pytest.raises(
        ask_context_workspace.AskContextWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        ask_context_workspace.execute(caller_path, "钥匙", 3, 3)  # type: ignore[arg-type]
    assert not caller_path.exists()

    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project(ALICE, "同名项目")
    _commit_all(alice)
    bob = router.create_project(BOB, "同名项目")
    result = ask_context_workspace.execute(bob, f"{alice.project_id} 钥匙", 3, 3)
    assert result["m6"]["matches"] == []
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project(BOB, alice.project_id)


def test_public_signature_has_no_path_or_identity_parameters() -> None:
    assert list(inspect.signature(ask_context_workspace.execute).parameters) == [
        "workspace",
        "query",
        "before_chars",
        "after_chars",
    ]
