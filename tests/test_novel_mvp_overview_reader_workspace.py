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
    from mvp import (
        overview,
        overview_card_workspace,
        overview_reader_workspace,
        overview_workspace,
    )
    from mvp.workspace import WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:m9-reader-alice"
BOB = "auth:m9-reader-bob"
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
        "source": "M9_READER_WORKSPACE_SYNTHETIC_FIXTURE",
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
    handle = WorkspaceRouter(runtime).create_project(principal, "M9 阅读项目")
    handle.commit("op-reader-facts", {"facts": _facts()}, {"facts": 0})
    handle.commit(
        "op-reader-index",
        {"chapter_index": [_revision_ref("c01"), _revision_ref("c02")]},
        {"chapter_index": 0},
    )
    return runtime, handle


def _provider_result(fact_ids: list[str]) -> dict:
    return {
        "synopsis": "作者可以直接阅读的离线单章概览。",
        "beats": [
            {
                "text": "本章事实按原顺序呈现。",
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
        "2026-08-19 22:00:00",
        lambda request: _provider_result(
            [fact["id"] for fact in request["facts"]]
        ),
    )


def _save_c01(workspace) -> dict:
    result = _result(workspace, "c01")
    overview_card_workspace.save_overview_card(
        workspace,
        "op-reader-save-c01",
        result,
        0,
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


def test_current_saved_card_is_one_click_readable_after_process_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, workspace = _workspace(tmp_path)
    saved = _save_c01(workspace)
    before = _inventory(runtime)
    monkeypatch.setattr(
        workspace,
        "commit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("reader 不得写工作区")
        ),
    )

    view = overview_reader_workspace.read_saved_overview_card_view(
        workspace,
        "c01",
    )

    assert view["freshness"] == "CURRENT"
    assert view["stale_reasons"] == []
    assert view["facts_snapshot"] == saved["facts_snapshot"]
    assert view["chapter_index_snapshot"] == saved["chapter_index_snapshot"]
    assert view["markdown"].startswith("# 当前概览（CURRENT）\n")
    assert saved["m9"]["synopsis"] in view["markdown"]
    assert "甲拿起钥匙。" in view["markdown"]
    mutated = copy.deepcopy(view)
    mutated["markdown"] = "调用方改动"
    assert overview_reader_workspace.read_saved_overview_card_view(
        workspace,
        "c01",
    )["markdown"] == view["markdown"]
    assert _inventory(runtime) == before

    script = """
import json
import sys
from mvp import overview_reader_workspace
from mvp.workspace import WorkspaceRouter
handle = WorkspaceRouter(sys.argv[1]).open_project(sys.argv[2], sys.argv[3])
result = overview_reader_workspace.read_saved_overview_card_view(handle, 'c01')
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


@pytest.mark.parametrize("drift", ["facts", "index"])
def test_stale_saved_card_remains_readable_but_is_marked_historical(
    tmp_path: Path,
    drift: str,
) -> None:
    _, workspace = _workspace(tmp_path)
    _save_c01(workspace)
    if drift == "facts":
        changed_facts = _facts()
        changed_facts.append(_fact("f004", "c01", "甲拿起钥匙。"))
        workspace.commit("op-reader-facts-v2", {"facts": changed_facts}, {"facts": 1})
        expected_reasons = ["FACTS_SNAPSHOT_CHANGED"]
    else:
        workspace.commit(
            "op-reader-index-v2",
            {
                "chapter_index": [
                    _revision_ref("c01", revision_no=3),
                    _revision_ref("c02"),
                ]
            },
            {"chapter_index": 1},
        )
        expected_reasons = [
            "CHAPTER_INDEX_SNAPSHOT_CHANGED",
            "CHAPTER_REVISION_CHANGED",
        ]

    view = overview_reader_workspace.read_saved_overview_card_view(
        workspace,
        "c01",
    )

    assert view["freshness"] == "STALE"
    assert view["stale_reasons"] == expected_reasons
    assert view["markdown"].startswith("# ⚠️ 历史概览（已过期）\n")
    assert "这张卡只供查看历史，不是当前概览" in view["markdown"]
    assert "CURRENT" not in view["markdown"]
    for reason in expected_reasons:
        assert f"`{reason}`" in view["markdown"]


@pytest.mark.parametrize("changed_key", ["overview_cards", "facts", "chapter_index"])
def test_read_rejects_overview_or_source_change_between_list_and_card(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_key: str,
) -> None:
    _, workspace = _workspace(tmp_path)
    _save_c01(workspace)
    entry = workspace.read(changed_key)
    real_read = overview_card_workspace.read_overview_card
    changed = False

    def read_then_change(handle, chapter_id):
        nonlocal changed
        loaded = real_read(handle, chapter_id)
        if not changed:
            changed = True
            workspace.commit(
                f"op-reader-race-{changed_key}",
                {changed_key: entry["payload"]},
                {changed_key: entry["version"]},
            )
        return loaded

    monkeypatch.setattr(
        overview_card_workspace,
        "read_overview_card",
        read_then_change,
    )

    with pytest.raises(
        overview_reader_workspace.OverviewReaderWorkspaceError,
        match="SAVED_CARD_VIEW_CHANGED_DURING_READ",
    ):
        overview_reader_workspace.read_saved_overview_card_view(workspace, "c01")


def test_missing_chapter_returns_stable_empty_without_writes(tmp_path: Path) -> None:
    runtime, workspace = _workspace(tmp_path)
    _save_c01(workspace)
    before = _inventory(runtime)

    result = overview_reader_workspace.read_saved_overview_card_view(
        workspace,
        "c99",
    )

    assert result is None
    assert _inventory(runtime) == before


def test_bad_store_path_and_cross_author_binding_fail_closed(tmp_path: Path) -> None:
    caller_path = tmp_path / "caller-path"
    with pytest.raises(
        overview_reader_workspace.OverviewReaderWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        overview_reader_workspace.read_saved_overview_card_view(  # type: ignore[arg-type]
            caller_path,
            "c01",
        )
    assert not caller_path.exists()

    _, corrupt = _workspace(tmp_path / "corrupt", ALICE)
    corrupt.commit(
        "op-reader-corrupt-store",
        {"overview_cards": {"bad": True}},
        {"overview_cards": 0},
    )
    with pytest.raises(
        overview_reader_workspace.OverviewReaderWorkspaceError,
        match="SAVED_CARD_INVENTORY_REJECTED",
    ):
        overview_reader_workspace.read_saved_overview_card_view(corrupt, "c01")

    _, alice = _workspace(tmp_path / "alice", ALICE)
    alice_result = _result(alice, "c01")
    _, bob = _workspace(tmp_path / "bob", BOB)
    bob.commit(
        "op-reader-cross-author-store",
        {
            "overview_cards": {
                "store_version": overview_card_workspace.STORE_VERSION,
                "chapters": {"c01": alice_result},
            }
        },
        {"overview_cards": 0},
    )
    with pytest.raises(
        overview_reader_workspace.OverviewReaderWorkspaceError,
        match="SAVED_CARD_INVENTORY_REJECTED",
    ):
        overview_reader_workspace.read_saved_overview_card_view(bob, "c01")
