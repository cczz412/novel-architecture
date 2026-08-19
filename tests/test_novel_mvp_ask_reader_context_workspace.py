from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        ask_reader_context_workspace,
        ask_reader_scope_workspace,
        ask_tool,
    )
    from mvp.workspace import ProjectNotFoundError, WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:m6-reader-context-alice"
BOB = "auth:m6-reader-context-bob"
VISIBLE_QUOTE = "顾遥在第四章收起银戒指"
FUTURE_QUOTE = "第六章揭晓银戒指里藏着王室密令"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _chapter_text(chapter_id: str) -> str:
    if chapter_id == "c04":
        return f"门外雨声渐密。{VISIBLE_QUOTE}，没有解释来历。"
    if chapter_id == "c06":
        return f"所有人到齐后，{FUTURE_QUOTE}。"
    return f"{chapter_id} 只记录不涉及银戒指谜底的日常行程。"


def _ref(chapter_id: str, *, revision_no: int = 1, text: str | None = None) -> dict:
    chapter_text = _chapter_text(chapter_id) if text is None else text
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": _sha(chapter_text),
    }


def _chapter(chapter_id: str) -> dict:
    text = _chapter_text(chapter_id)
    return {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": chapter_id,
        "title": f"第{int(chapter_id[1:])}章",
        "kind": "draft",
        "text": text,
        "added_at": "2026-08-19 23:00:00",
        "chapter_revision_ref": _ref(chapter_id),
    }


def _fact(
    fact_id: str,
    chapter_id: str,
    quote: str,
    *,
    ref: dict | None = None,
    bad_anchor: bool = False,
) -> dict:
    chapter_text = _chapter_text(chapter_id)
    selected_ref = copy.deepcopy(ref or _ref(chapter_id))
    start = chapter_text.index(quote)
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": chapter_id,
        "text": f"{quote}。",
        "quote": quote,
        "status": "confirmed",
        "source": "M6_READER_CONTEXT_SYNTHETIC",
        "note": "",
        "added_at": "2026-08-19 23:01:00",
        "seg": 1,
        "decided_at": "2026-08-19 23:02:00",
        "chapter_revision_ref": selected_ref,
        "anchor_ref": {
            **copy.deepcopy(selected_ref),
            "coordinate_basis": ask_tool.COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": "0" * 64 if bad_anchor else _sha(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


def _chapters() -> list[dict]:
    return [_chapter(f"c{number:02d}") for number in range(1, 7)]


def _refs() -> list[dict]:
    return [copy.deepcopy(chapter["chapter_revision_ref"]) for chapter in _chapters()]


def _facts() -> list[dict]:
    return [
        _fact("f004", "c04", VISIBLE_QUOTE),
        _fact("f006", "c06", FUTURE_QUOTE),
    ]


def _commit_all(
    workspace,
    *,
    facts: list[dict] | None = None,
    chapters: list[dict] | None = None,
    refs: list[dict] | None = None,
) -> dict:
    return workspace.commit(
        "op-reader-context-base",
        {
            "facts": _facts() if facts is None else facts,
            "chapter_index": _refs() if refs is None else refs,
            "chapters": _chapters() if chapters is None else chapters,
        },
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


def _all_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _all_strings(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _all_strings(item)]
    return []


def test_as_of_fifth_expands_fourth_evidence_without_sixth_chapter_leak(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project(ALICE, "读者防剧透上下文")
    receipt = _commit_all(workspace)
    restarted = WorkspaceRouter(runtime_root).open_project(ALICE, workspace.project_id)
    before = _inventory(runtime_root)

    result = ask_reader_context_workspace.execute(
        restarted,
        "银戒指",
        "c05",
        5,
        6,
    )

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
    assert result["visible_chapter_revision_refs"] == _refs()[:5]
    assert all(
        set(ref) == {"chapter_id", "revision_no", "revision_text_sha256"}
        for ref in result["visible_chapter_revision_refs"]
    )
    assert [item["fact_id"] for item in result["m6"]["matches"]] == ["f004"]
    assert [item["fact_id"] for item in result["m6"]["evidence"]] == ["f004"]
    assert result["m6"]["reader_scope"] == {
        "mode": "AS_OF_CHAPTER",
        "as_of_chapter_id": "c05",
        "visible_chapter_count": 5,
        "future_chapter_count": 1,
        "blocked_fact_count": 1,
    }
    context = result["m6"]["evidence"][0]["context"]
    highlighted = context["text"][
        context["highlight_start"] : context["highlight_end"]
    ]
    assert highlighted == VISIBLE_QUOTE
    assert context["window_start"] < _chapter_text("c04").index(VISIBLE_QUOTE)
    assert context["window_end"] > context["window_start"] + context["highlight_end"]
    strings = _all_strings(result)
    assert "f006" not in strings
    assert "c06" not in strings
    assert FUTURE_QUOTE not in strings
    assert _inventory(runtime_root) == before
    json.loads(json.dumps(result, ensure_ascii=False))


def test_empty_match_returns_stable_empty_context(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "空命中")
    _commit_all(workspace)
    before = _inventory(runtime_root)

    result = ask_reader_context_workspace.execute(
        workspace,
        "不存在的线索",
        "c05",
        4,
        4,
    )

    assert result["m6"]["matches"] == []
    assert result["m6"]["evidence"] == []
    assert result["m6"]["reader_scope"]["blocked_fact_count"] == 1
    assert _inventory(runtime_root) == before


@pytest.mark.parametrize("fault", ["missing_chapters", "stale_fact", "bad_anchor"])
def test_missing_prose_revision_drift_or_bad_anchor_fails_closed(
    tmp_path: Path,
    fault: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / fault).create_project(ALICE, fault)
    if fault == "missing_chapters":
        workspace.commit(
            "op-missing-chapters",
            {"facts": _facts(), "chapter_index": _refs()},
            {"facts": 0, "chapter_index": 0},
        )
    elif fault == "stale_fact":
        stale_text = _chapter_text("c04") + "旧版"
        stale_ref = _ref("c04", revision_no=2, text=stale_text)
        _commit_all(
            workspace,
            facts=[_fact("f004", "c04", VISIBLE_QUOTE, ref=stale_ref)],
        )
    else:
        _commit_all(
            workspace,
            facts=[_fact("f004", "c04", VISIBLE_QUOTE, bad_anchor=True)],
        )

    with pytest.raises(
        ask_reader_context_workspace.AskReaderContextWorkspaceError
    ):
        ask_reader_context_workspace.execute(workspace, "银戒指", "c05", 4, 4)


def test_injected_future_evidence_is_rejected_before_context_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "future-injection").create_project(
        ALICE,
        "未来证据注入",
    )
    _commit_all(workspace)
    real_execute = ask_reader_scope_workspace.execute

    def inject_future(handle, query: str, as_of_chapter_id: str) -> dict:
        result = real_execute(handle, query, as_of_chapter_id)
        full = ask_tool.execute(
            {
                "query": query,
                "facts": _facts(),
                "current_revision_refs": _refs(),
            }
        )
        result["m6"]["matches"].append(copy.deepcopy(full["matches"][1]))
        result["m6"]["evidence"].append(copy.deepcopy(full["evidence"][1]))
        return result

    monkeypatch.setattr(ask_reader_scope_workspace, "execute", inject_future)

    with pytest.raises(
        ask_reader_context_workspace.AskReaderContextWorkspaceError,
        match="CONTEXT_EXPANSION_REJECTED",
    ):
        ask_reader_context_workspace.execute(workspace, "银戒指", "c05", 4, 4)


@pytest.mark.parametrize("logical_key", ["facts", "chapter_index", "chapters"])
def test_any_source_watermark_change_discards_combined_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    logical_key: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / logical_key).create_project(ALICE, "来源竞态")
    _commit_all(workspace)
    real_execute = ask_reader_scope_workspace.execute

    def execute_and_change_source(handle, query: str, as_of_chapter_id: str) -> dict:
        result = real_execute(handle, query, as_of_chapter_id)
        changed = copy.deepcopy(handle.read(logical_key)["payload"])
        if logical_key == "facts":
            changed[0]["note"] = "组合期间更新"
        handle.commit(
            f"op-reader-context-race-{logical_key}",
            {logical_key: changed},
            {logical_key: 1},
        )
        return result

    monkeypatch.setattr(
        ask_reader_scope_workspace,
        "execute",
        execute_and_change_source,
    )

    with pytest.raises(ask_reader_context_workspace.AskReaderContextWorkspaceError):
        ask_reader_context_workspace.execute(workspace, "银戒指", "c05", 4, 4)


def test_path_and_cross_author_guess_are_rejected(tmp_path: Path) -> None:
    caller_path = tmp_path / "caller-project"
    with pytest.raises(
        ask_reader_context_workspace.AskReaderContextWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        ask_reader_context_workspace.execute(  # type: ignore[arg-type]
            caller_path,
            "银戒指",
            "c05",
            4,
            4,
        )
    assert not caller_path.exists()

    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project(ALICE, "同名项目")
    _commit_all(alice)
    bob = router.create_project(BOB, "同名项目")
    _commit_all(bob, facts=[])

    result = ask_reader_context_workspace.execute(
        bob,
        f"{alice.project_id} 银戒指",
        "c05",
        4,
        4,
    )
    assert result["m6"]["matches"] == []
    assert result["m6"]["evidence"] == []
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project(BOB, alice.project_id)


def test_public_signature_exposes_no_path_or_identity_parameters() -> None:
    assert list(
        inspect.signature(ask_reader_context_workspace.execute).parameters
    ) == [
        "workspace",
        "query",
        "as_of_chapter_id",
        "before_chars",
        "after_chars",
    ]
