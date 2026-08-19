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
    from mvp import ask_reader_scope_workspace, ask_tool
    from mvp.workspace import ProjectNotFoundError, WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:m6-reader-alice"
BOB = "auth:m6-reader-bob"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ref(chapter_id: str, revision_no: int = 1) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": _sha(f"{chapter_id}-revision-{revision_no}"),
    }


def _fact(
    fact_id: str,
    chapter_id: str,
    text: str,
    quote: str,
    *,
    ref: dict | None = None,
    bad_anchor: bool = False,
) -> dict:
    selected_ref = copy.deepcopy(ref or _ref(chapter_id))
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": chapter_id,
        "text": text,
        "quote": quote,
        "status": "confirmed",
        "source": "M6_READER_WORKSPACE_SYNTHETIC_FIXTURE",
        "note": "",
        "added_at": "2026-08-19 22:00:00",
        "seg": 1,
        "decided_at": "2026-08-19 22:01:00",
        "chapter_revision_ref": selected_ref,
        "anchor_ref": {
            **selected_ref,
            "coordinate_basis": ask_tool.COORDINATE_BASIS,
            "start": 0,
            "end": len(quote),
            "slice_sha256": "0" * 64 if bad_anchor else _sha(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


C05_REF = _ref("c05")
C20_REF = _ref("c20")
C99_REF = _ref("c99")
MISDIRECTION = _fact(
    "f005",
    "c05",
    "众人都误以为管家是凶手。",
    "众人都误以为管家是凶手",
    ref=C05_REF,
)
REVEAL = _fact(
    "f020",
    "c20",
    "真正的凶手是苏晚。",
    "真正的凶手是苏晚",
    ref=C20_REF,
)


def _commit(workspace, facts: list[dict], refs: list[dict]) -> dict:
    return workspace.commit(
        "op-reader-scope-base",
        {"facts": facts, "chapter_index": refs},
        {"facts": 0, "chapter_index": 0},
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


def _all_string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for row in value for item in _all_string_values(row)]
    if isinstance(value, dict):
        return [item for row in value.values() for item in _all_string_values(row)]
    return []


def test_restart_as_of_middle_chapter_hides_future_and_returns_two_watermarks(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project(ALICE, "读者截点")
    receipt = _commit(workspace, [MISDIRECTION, REVEAL], [C05_REF, C20_REF])
    restarted = WorkspaceRouter(runtime_root).open_project(ALICE, workspace.project_id)
    before = _inventory(runtime_root)

    result = ask_reader_scope_workspace.execute(restarted, "凶手", "c05")

    assert result["facts_snapshot"] == {
        "version": 1,
        "sha256": receipt["payload_sha256"]["facts"],
    }
    assert result["chapter_index_snapshot"] == {
        "version": 1,
        "sha256": receipt["payload_sha256"]["chapter_index"],
    }
    assert [row["fact_id"] for row in result["m6"]["matches"]] == ["f005"]
    assert [row["fact_id"] for row in result["m6"]["evidence"]] == ["f005"]
    assert result["m6"]["reader_scope"]["blocked_fact_count"] == 1
    strings = _all_string_values(result)
    assert "f020" not in strings
    assert "c20" not in strings
    assert "真正的凶手是苏晚" not in strings
    assert _inventory(runtime_root) == before
    json.loads(json.dumps(result, ensure_ascii=False))


def test_non_contiguous_ids_follow_workspace_index_order(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(ALICE, "非连续顺序")
    _commit(workspace, [MISDIRECTION, REVEAL], [C20_REF, C05_REF, C99_REF])

    result = ask_reader_scope_workspace.execute(workspace, "凶手", "c20")

    assert [row["fact_id"] for row in result["m6"]["matches"]] == ["f020"]
    assert result["m6"]["reader_scope"] == {
        "mode": "AS_OF_CHAPTER",
        "as_of_chapter_id": "c20",
        "visible_chapter_count": 1,
        "future_chapter_count": 2,
        "blocked_fact_count": 1,
    }


def test_existing_index_with_empty_facts_returns_stable_empty_result(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "空事实")
    receipt = _commit(workspace, [], [C05_REF, C20_REF])
    before = _inventory(runtime_root)

    result = ask_reader_scope_workspace.execute(workspace, "凶手", "c05")

    assert result["facts_snapshot"] == {
        "version": 1,
        "sha256": receipt["payload_sha256"]["facts"],
    }
    assert result["m6"]["matches"] == []
    assert result["m6"]["evidence"] == []
    assert result["m6"]["reader_scope"]["future_chapter_count"] == 1
    assert result["m6"]["reader_scope"]["blocked_fact_count"] == 0
    assert _inventory(runtime_root) == before


@pytest.mark.parametrize(
    ("fault", "message"),
    [
        ("missing_index", "CHAPTER_INDEX_REQUIRED"),
        ("missing_cutoff", "as_of_chapter_id"),
        ("duplicate_index", "WORKSPACE_SNAPSHOT_INVALID"),
        ("fact_chapter_absent", "FACT_CHAPTER_NOT_IN_CURRENT_INDEX"),
        ("stale_fact", "FACT_NOT_CURRENT_REVISION"),
        ("bad_fact", "WORKSPACE_SNAPSHOT_INVALID"),
    ],
)
def test_missing_or_inconsistent_workspace_snapshots_fail_closed(
    tmp_path: Path,
    fault: str,
    message: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / fault).create_project(ALICE, fault)
    cutoff = "c05"
    if fault == "missing_index":
        workspace.commit("op-facts-only", {"facts": []}, {"facts": 0})
    elif fault == "missing_cutoff":
        _commit(workspace, [], [C05_REF])
        cutoff = "c20"
    elif fault == "duplicate_index":
        _commit(workspace, [], [C05_REF, copy.deepcopy(C05_REF)])
    elif fault == "fact_chapter_absent":
        _commit(
            workspace,
            [_fact("f099", "c99", "远处传来钟声。", "远处传来钟声")],
            [C05_REF],
        )
    elif fault == "stale_fact":
        stale_ref = _ref("c05", 1)
        current_ref = _ref("c05", 2)
        _commit(
            workspace,
            [_fact("f005", "c05", "旧线索仍在。", "旧线索仍在", ref=stale_ref)],
            [current_ref],
        )
    else:
        _commit(
            workspace,
            [
                _fact(
                    "f005",
                    "c05",
                    "众人都误以为管家是凶手。",
                    "众人都误以为管家是凶手",
                    ref=C05_REF,
                    bad_anchor=True,
                )
            ],
            [C05_REF],
        )

    with pytest.raises(
        ask_reader_scope_workspace.ReaderScopeWorkspaceError,
        match=message,
    ):
        ask_reader_scope_workspace.execute(workspace, "凶手", cutoff)


def test_snapshot_change_during_query_discards_whole_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(ALICE, "读途变化")
    _commit(workspace, [MISDIRECTION, REVEAL], [C05_REF, C20_REF])
    real_read = workspace.read
    reads = 0

    def changing_read(logical_key: str):
        nonlocal reads
        reads += 1
        if reads == 3:
            changed = copy.deepcopy(MISDIRECTION)
            changed["note"] = "查询过程中发生并发更新"
            workspace.commit(
                "op-reader-mid-query-change",
                {"facts": [changed, REVEAL]},
                {"facts": 1},
            )
        return real_read(logical_key)

    monkeypatch.setattr(workspace, "read", changing_read)

    with pytest.raises(
        ask_reader_scope_workspace.ReaderScopeWorkspaceError,
        match="WORKSPACE_SNAPSHOT_CHANGED_DURING_QUERY",
    ):
        ask_reader_scope_workspace.execute(workspace, "凶手", "c05")


def test_path_and_cross_author_guess_cannot_select_another_workspace(
    tmp_path: Path,
) -> None:
    caller_path = tmp_path / "caller-controlled-project"
    with pytest.raises(
        ask_reader_scope_workspace.ReaderScopeWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        ask_reader_scope_workspace.execute(  # type: ignore[arg-type]
            caller_path,
            "凶手",
            "c05",
        )
    assert not caller_path.exists()

    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project(ALICE, "同名项目")
    _commit(alice, [MISDIRECTION, REVEAL], [C05_REF, C20_REF])
    bob = router.create_project(BOB, "同名项目")
    _commit(bob, [], [C05_REF])

    result = ask_reader_scope_workspace.execute(
        bob,
        f"{alice.project_id} 凶手",
        "c05",
    )
    assert result["m6"]["matches"] == []
    assert result["m6"]["evidence"] == []
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project(BOB, alice.project_id)


def test_public_signature_exposes_no_path_identity_or_revision_order() -> None:
    assert list(inspect.signature(ask_reader_scope_workspace.execute).parameters) == [
        "workspace",
        "query",
        "as_of_chapter_id",
    ]
