from __future__ import annotations

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
    from mvp import ask_tool, ask_workspace
    from mvp.workspace import ProjectNotFoundError, WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:m6-alice"
BOB = "auth:m6-bob"
CURRENT_TEXT = "林乔把铜钥匙交给苏晚。苏晚把钥匙收进黑色文件袋。"
OLD_TEXT = "林乔把旧钥匙放在桌上。"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _revision_ref(*, revision_no: int = 2, text: str = CURRENT_TEXT) -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": revision_no,
        "revision_text_sha256": _sha(text),
    }


def _fact(
    fact_id: str,
    *,
    status: str = "confirmed",
    text: str = "林乔把铜钥匙交给苏晚。",
    quote: str = "把铜钥匙交给苏晚",
    revision_no: int = 2,
    revision_text: str = CURRENT_TEXT,
    bad_anchor: bool = False,
) -> dict:
    revision_ref = _revision_ref(revision_no=revision_no, text=revision_text)
    start = revision_text.index(quote) if quote in revision_text else 0
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": "c01",
        "text": text,
        "quote": quote,
        "status": status,
        "source": "M6_WORKSPACE_SYNTHETIC_FIXTURE",
        "note": "",
        "added_at": "2026-08-19 18:00:00",
        "seg": 1,
        "decided_at": "2026-08-19 18:01:00",
        "chapter_revision_ref": revision_ref,
        "anchor_ref": {
            **revision_ref,
            "coordinate_basis": ask_tool.COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": "0" * 64 if bad_anchor else _sha(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


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


def _commit_snapshots(workspace, facts: list[dict], refs: list[dict] | None = None) -> dict:
    refs = refs if refs is not None else [_revision_ref()]
    return workspace.commit(
        "op-m6-snapshots-01",
        {"facts": facts, "chapter_index": refs},
        {"facts": 0, "chapter_index": 0},
    )


def test_empty_project_returns_stable_empty_result_without_writes(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "空项目")
    before = _inventory(runtime_root)

    result = ask_workspace.execute(workspace, "钥匙")

    assert result == {
        "facts_snapshot": {"version": 0, "sha256": None},
        "chapter_index_snapshot": {"version": 0, "sha256": None},
        "m6": {
            "query": "钥匙",
            "matches": [],
            "evidence": [],
            "excluded_counts": {key: 0 for key in ask_tool.EXCLUDED_COUNT_KEYS},
        },
    }
    assert _inventory(runtime_root) == before


def test_current_confirmed_verified_hits_and_other_states_stay_excluded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(ALICE, "M6 合成项目")
    stale = _fact(
        "f004",
        text="林乔把旧钥匙放在桌上。",
        quote="把旧钥匙放在桌上",
        revision_no=1,
        revision_text=OLD_TEXT,
    )
    receipt = _commit_snapshots(
        workspace,
        [
            _fact("f001"),
            _fact("f002", status="extracted"),
            _fact("f003", status="rejected"),
            stale,
            _fact("f005", bad_anchor=True),
        ],
    )
    before = _inventory(tmp_path / "runtime")
    read_calls: list[str] = []
    real_read = workspace.read
    monkeypatch.setattr(
        workspace,
        "read",
        lambda logical_key: read_calls.append(logical_key) or real_read(logical_key),
    )
    monkeypatch.setattr(
        workspace,
        "commit",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("查询不得写 workspace")),
    )

    result = ask_workspace.execute(workspace, "钥匙 苏晚")

    assert read_calls == ["facts", "chapter_index"] * 3
    assert result["facts_snapshot"] == {
        "version": receipt["versions"]["facts"],
        "sha256": receipt["payload_sha256"]["facts"],
    }
    assert result["chapter_index_snapshot"] == {
        "version": receipt["versions"]["chapter_index"],
        "sha256": receipt["payload_sha256"]["chapter_index"],
    }
    assert [item["fact_id"] for item in result["m6"]["matches"]] == ["f001"]
    assert [item["fact_id"] for item in result["m6"]["evidence"]] == ["f001"]
    excluded = result["m6"]["excluded_counts"]
    assert excluded["extracted"] == 1
    assert excluded["rejected"] == 1
    assert excluded["stale_revision"] == 1
    assert excluded["invalid_evidence"] == 1
    json.loads(json.dumps(result, ensure_ascii=False))
    assert _inventory(tmp_path / "runtime") == before


def test_restart_reads_same_facts_version_sha_and_evidence(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project(ALICE, "可重启项目")
    receipt = _commit_snapshots(workspace, [_fact("f001")])

    restarted = WorkspaceRouter(runtime_root).open_project(ALICE, workspace.project_id)
    result = ask_workspace.execute(restarted, "钥匙 苏晚")

    assert result["facts_snapshot"] == {
        "version": 1,
        "sha256": receipt["payload_sha256"]["facts"],
    }
    assert result["chapter_index_snapshot"] == {
        "version": 1,
        "sha256": receipt["payload_sha256"]["chapter_index"],
    }
    assert result["m6"]["evidence"][0]["anchor_ref"]["slice_sha256"] == _sha(
        "把铜钥匙交给苏晚"
    )


def test_other_author_project_guess_cannot_change_workspace_binding(tmp_path: Path) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project(ALICE, "同名项目")
    _commit_snapshots(alice, [_fact("f001")])
    bob = router.create_project(BOB, "同名项目")

    result = ask_workspace.execute(
        bob,
        f"{alice.project_id} 钥匙",
    )

    assert result["facts_snapshot"] == {"version": 0, "sha256": None}
    assert result["chapter_index_snapshot"] == {"version": 0, "sha256": None}
    assert result["m6"]["matches"] == []
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project(BOB, alice.project_id)


def test_path_cannot_impersonate_workspace_handle(tmp_path: Path) -> None:
    caller_path = tmp_path / "caller-controlled-project"

    with pytest.raises(
        ask_workspace.AskWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        ask_workspace.execute(  # type: ignore[arg-type]
            caller_path,
            "钥匙",
        )

    assert not caller_path.exists()


def test_old_revision_fact_is_excluded_by_workspace_owned_current_index(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(ALICE, "旧版本事实")
    stale = _fact(
        "f001",
        text="林乔把旧钥匙放在桌上。",
        quote="把旧钥匙放在桌上",
        revision_no=1,
        revision_text=OLD_TEXT,
    )
    _commit_snapshots(workspace, [stale], [_revision_ref()])

    result = ask_workspace.execute(workspace, "旧钥匙")

    assert result["m6"]["matches"] == []
    assert result["m6"]["excluded_counts"]["stale_revision"] == 1


def test_nonempty_facts_without_chapter_index_fail_before_m6(tmp_path: Path, monkeypatch) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(ALICE, "缺索引")
    workspace.commit("op-facts-only", {"facts": [_fact("f001")]}, {"facts": 0})
    monkeypatch.setattr(
        ask_tool,
        "execute",
        lambda request: (_ for _ in ()).throw(AssertionError("不得进入 M6")),
    )

    with pytest.raises(
        ask_workspace.AskWorkspaceError,
        match="CHAPTER_INDEX_REQUIRED_FOR_NONEMPTY_FACTS",
    ):
        ask_workspace.execute(workspace, "钥匙")


def test_preread_mixed_watermark_rejects_before_ask_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime-race-before").create_project(
        ALICE, "预读竞态"
    )
    _commit_snapshots(workspace, [_fact("f001")])
    real_read = workspace.read
    read_calls = 0
    ask_calls = 0

    def racing_read(logical_key: str):
        nonlocal read_calls
        read_calls += 1
        result = real_read(logical_key)
        if read_calls == 1:
            facts = real_read("facts")
            chapter_index = real_read("chapter_index")
            workspace.commit(
                "op-m6-preread-race",
                {
                    "facts": facts["payload"],
                    "chapter_index": chapter_index["payload"],
                },
                {
                    "facts": facts["version"],
                    "chapter_index": chapter_index["version"],
                },
            )
        return result

    def forbidden_ask(request: dict) -> dict:
        nonlocal ask_calls
        ask_calls += 1
        raise AssertionError("预读水位不一致时不得调用 ask_tool")

    monkeypatch.setattr(workspace, "read", racing_read)
    monkeypatch.setattr(ask_tool, "execute", forbidden_ask)

    with pytest.raises(
        ask_workspace.AskWorkspaceError,
        match="M6_SOURCE_CHANGED_BEFORE_QUERY",
    ):
        ask_workspace.execute(workspace, "钥匙")

    assert ask_calls == 0
    assert real_read("facts")["version"] == 2
    assert real_read("chapter_index")["version"] == 2


@pytest.mark.parametrize("changed_key", ["facts", "chapter_index"])
def test_source_change_during_query_discards_result_and_preserves_new_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_key: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / f"runtime-race-{changed_key}").create_project(
        ALICE, "查询竞态"
    )
    _commit_snapshots(workspace, [_fact("f001")])
    real_ask = ask_tool.execute
    ask_calls = 0

    def ask_and_advance_source(request: dict) -> dict:
        nonlocal ask_calls
        ask_calls += 1
        result = real_ask(request)
        current = workspace.read(changed_key)
        workspace.commit(
            f"op-m6-during-{changed_key}",
            {changed_key: current["payload"]},
            {changed_key: current["version"]},
        )
        return result

    monkeypatch.setattr(ask_tool, "execute", ask_and_advance_source)

    with pytest.raises(
        ask_workspace.AskWorkspaceError,
        match="M6_SOURCE_CHANGED_DURING_QUERY",
    ):
        ask_workspace.execute(workspace, "钥匙 苏晚")

    assert ask_calls == 1
    assert workspace.read(changed_key)["version"] == 2
    unchanged = "chapter_index" if changed_key == "facts" else "facts"
    assert workspace.read(unchanged)["version"] == 1


@pytest.mark.parametrize("fault", ["bad_shape", "duplicate", "chapter_mismatch"])
def test_bad_or_inconsistent_chapter_index_fails_closed(tmp_path: Path, fault: str) -> None:
    workspace = WorkspaceRouter(tmp_path / fault).create_project(ALICE, fault)
    refs = [_revision_ref()]
    facts = [_fact("f001")]
    if fault == "bad_shape":
        refs[0] = {"chapter_id": "c01", "revision_no": 2}
    elif fault == "duplicate":
        refs.append(dict(refs[0]))
    else:
        refs[0] = {
            "chapter_id": "c02",
            "revision_no": 1,
            "revision_text_sha256": _sha("第二章"),
        }
    _commit_snapshots(workspace, facts, refs)

    with pytest.raises(ask_workspace.AskWorkspaceError):
        ask_workspace.execute(workspace, "钥匙")


def test_public_signature_has_no_revision_refs_identity_or_path() -> None:
    assert list(inspect.signature(ask_workspace.execute).parameters) == ["workspace", "query"]
