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
    from mvp import (
        overview,
        overview_book_workspace,
        overview_card_workspace,
        overview_reader_workspace,
        overview_workspace,
    )
    from mvp.workspace import WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:m9-book-alice"
BOB = "auth:m9-book-bob"
TEXTS = {
    "c01": "甲拿起钥匙。乙看见了钥匙。",
    "c02": "丙关上窗户。丁离开房间。",
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_ref(chapter_id: str, *, revision_no: int = 2) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": _sha(TEXTS[chapter_id]),
    }


def _fact(fact_id: str, chapter_id: str, quote: str) -> dict:
    revision_ref = _revision_ref(chapter_id)
    start = TEXTS[chapter_id].index(quote)
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": chapter_id,
        "text": quote,
        "quote": quote,
        "status": "extracted",
        "source": "M9_BOOK_WORKSPACE_SYNTHETIC_FIXTURE",
        "note": "",
        "added_at": "2026-08-19 20:00:00",
        "seg": 1,
        "chapter_revision_ref": revision_ref,
        "anchor_ref": {
            **revision_ref,
            "coordinate_basis": overview.COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": _sha(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


def _facts() -> list[dict]:
    return [
        _fact("f001", "c01", "甲拿起钥匙。"),
        _fact("f002", "c01", "乙看见了钥匙。"),
        _fact("f003", "c02", "丙关上窗户。"),
    ]


def _workspace(tmp_path: Path, principal: str = ALICE):
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime = tmp_path / principal.replace(":", "-")
    handle = WorkspaceRouter(runtime).create_project(principal, "M9 全书概览项目")
    handle.commit("op-book-facts", {"facts": _facts()}, {"facts": 0})
    handle.commit(
        "op-book-index",
        {"chapter_index": [_revision_ref("c01"), _revision_ref("c02")]},
        {"chapter_index": 0},
    )
    return runtime, handle


def _provider_result(fact_ids: list[str], chapter_id: str) -> dict:
    return {
        "synopsis": f"{chapter_id} 的作者可读概览。",
        "beats": [
            {
                "text": f"{chapter_id} 的事件点。",
                "fact_refs": list(fact_ids),
                "visual_hint": "",
            }
        ],
        "orphan_refs": [],
        "visual_hint": "",
    }


def _result(workspace, chapter_id: str) -> dict:
    return overview_workspace.execute(
        workspace,
        chapter_id,
        "2026-08-19 22:30:00",
        lambda request: _provider_result(
            [fact["id"] for fact in request["facts"]],
            chapter_id,
        ),
    )


def _save(workspace, chapter_id: str, operation_id: str, expected_version: int) -> dict:
    result = _result(workspace, chapter_id)
    overview_card_workspace.save_overview_card(
        workspace,
        operation_id,
        result,
        expected_version,
    )
    return result


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _inventory(root: Path) -> list[tuple[str, bool, bytes | None]]:
    return [
        (
            str(path.relative_to(root)),
            path.is_dir(),
            None if path.is_dir() else path.read_bytes(),
        )
        for path in sorted(root.rglob("*"))
    ]


def _mixed_snapshot_cards(workspace) -> None:
    _save(workspace, "c01", "op-save-old-c01", 0)
    changed_facts = _facts()
    changed_facts.append(_fact("f004", "c01", "甲拿起钥匙。"))
    workspace.commit("op-book-facts-v2", {"facts": changed_facts}, {"facts": 1})
    _save(workspace, "c02", "op-save-current-c02", 1)


def test_mixed_current_and_stale_cards_follow_inventory_order_and_restart_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, workspace = _workspace(tmp_path)
    _mixed_snapshot_cards(workspace)
    inventory = overview_card_workspace.list_overview_cards(workspace)
    expected_order = [item["chapter_id"] for item in inventory["cards"]]
    before = _inventory(runtime)
    monkeypatch.setattr(
        workspace,
        "commit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("book view 不得写工作区")
        ),
    )

    view = overview_book_workspace.read_saved_overview_book_view(workspace)

    assert expected_order == ["c01", "c02"]
    assert view["status"] == "READY"
    assert view["card_count"] == 2
    assert view["current_count"] == 1
    assert view["stale_count"] == 1
    assert view["workspace_binding"] == {
        "author_id": workspace.author_id,
        "project_id": workspace.project_id,
    }
    assert "# ⚠️ 历史概览（已过期）" in view["markdown"]
    assert "`FACTS_SNAPSHOT_CHANGED`" in view["markdown"]
    assert "# 当前概览（CURRENT）" in view["markdown"]
    assert view["markdown"].index("c01 的作者可读概览") < view["markdown"].index(
        "c02 的作者可读概览"
    )
    assert _inventory(runtime) == before

    script = """
import json
import sys
from mvp import overview_book_workspace
from mvp.workspace import WorkspaceRouter
handle = WorkspaceRouter(sys.argv[1]).open_project(sys.argv[2], sys.argv[3])
result = overview_book_workspace.read_saved_overview_book_view(handle)
print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PRODUCT_ROOT)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(runtime),
            ALICE,
            workspace.project_id,
        ],
        check=False,
        capture_output=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr.decode()
    assert completed.stdout == _canonical(view) + b"\n"


def test_empty_project_returns_stable_empty_document_without_writes(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "empty-runtime"
    workspace = WorkspaceRouter(runtime).create_project(ALICE, "空项目")
    before = _inventory(runtime)

    view = overview_book_workspace.read_saved_overview_book_view(workspace)

    assert view["status"] == "EMPTY"
    assert view["card_count"] == 0
    assert view["current_count"] == 0
    assert view["stale_count"] == 0
    assert "- 状态：EMPTY" in view["markdown"]
    assert "当前没有已保存的 M9 概览卡" in view["markdown"]
    assert _inventory(runtime) == before


@pytest.mark.parametrize("changed_key", ["overview_cards", "facts", "chapter_index"])
def test_mid_read_card_or_source_change_rejects_whole_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_key: str,
) -> None:
    _, workspace = _workspace(tmp_path)
    _save(workspace, "c01", "op-save-c01", 0)
    _save(workspace, "c02", "op-save-c02", 1)
    entry = workspace.read(changed_key)
    real_read = overview_reader_workspace.read_saved_overview_card_view
    changed = False

    def read_then_change(handle, chapter_id):
        nonlocal changed
        view = real_read(handle, chapter_id)
        if not changed:
            changed = True
            workspace.commit(
                f"op-book-race-{changed_key}",
                {changed_key: entry["payload"]},
                {changed_key: entry["version"]},
            )
        return view

    monkeypatch.setattr(
        overview_reader_workspace,
        "read_saved_overview_card_view",
        read_then_change,
    )

    with pytest.raises(
        overview_book_workspace.OverviewBookWorkspaceError,
        match="BOOK_OVERVIEW_SNAPSHOT_MISMATCH|BOOK_OVERVIEW_CHANGED_DURING_READ",
    ):
        overview_book_workspace.read_saved_overview_book_view(workspace)


def test_bad_store_path_and_cross_author_binding_fail_closed(tmp_path: Path) -> None:
    caller_path = tmp_path / "caller-path"
    with pytest.raises(
        overview_book_workspace.OverviewBookWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        overview_book_workspace.read_saved_overview_book_view(  # type: ignore[arg-type]
            caller_path
        )
    assert not caller_path.exists()

    _, corrupt = _workspace(tmp_path / "corrupt", ALICE)
    corrupt.commit(
        "op-book-corrupt-store",
        {"overview_cards": {"bad": True}},
        {"overview_cards": 0},
    )
    with pytest.raises(
        overview_book_workspace.OverviewBookWorkspaceError,
        match="BOOK_OVERVIEW_INVENTORY_REJECTED",
    ):
        overview_book_workspace.read_saved_overview_book_view(corrupt)

    _, alice = _workspace(tmp_path / "alice", ALICE)
    alice_result = _result(alice, "c01")
    _, bob = _workspace(tmp_path / "bob", BOB)
    bob.commit(
        "op-book-cross-author-store",
        {
            "overview_cards": {
                "store_version": overview_card_workspace.STORE_VERSION,
                "chapters": {"c01": alice_result},
            }
        },
        {"overview_cards": 0},
    )
    with pytest.raises(
        overview_book_workspace.OverviewBookWorkspaceError,
        match="BOOK_OVERVIEW_INVENTORY_REJECTED",
    ):
        overview_book_workspace.read_saved_overview_book_view(bob)
