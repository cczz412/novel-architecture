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
    from mvp import overview, overview_card_workspace, overview_workspace
    from mvp.workspace import (
        OperationConflictError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


ALICE = "auth:m9-card-alice"
BOB = "auth:m9-card-bob"
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
        "source": "M9_CARD_WORKSPACE_SYNTHETIC_FIXTURE",
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


def _provider_result(fact_ids: list[str], *, note: str = "current") -> dict:
    return {
        "synopsis": f"目标章事实被投影为一张概览：{note}",
        "beats": [
            {
                "text": "目标章事件顺序清晰。",
                "fact_refs": list(fact_ids),
                "visual_hint": "目标章事实卡。",
            }
        ],
        "orphan_refs": [],
        "visual_hint": "离线概览。",
    }


def _workspace(tmp_path: Path, principal: str = ALICE):
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime = tmp_path / principal.replace(":", "-")
    handle = WorkspaceRouter(runtime).create_project(principal, "M9 概览卡项目")
    handle.commit("op-seed-facts", {"facts": _facts()}, {"facts": 0})
    handle.commit(
        "op-seed-index",
        {"chapter_index": [_revision_ref("c01"), _revision_ref("c02")]},
        {"chapter_index": 0},
    )
    return runtime, handle


def _result(
    workspace,
    chapter_id: str,
    *,
    note: str = "current",
    generated_at: str = "2026-08-19 21:00:00",
) -> dict:
    def provider(request: dict) -> dict:
        return _provider_result(
            [fact["id"] for fact in request["facts"]],
            note=note,
        )

    return overview_workspace.execute(
        workspace,
        chapter_id,
        generated_at,
        provider,
    )


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


def _save_two_current(workspace) -> tuple[dict, dict]:
    first = _result(workspace, "c01")
    second = _result(workspace, "c02")
    overview_card_workspace.save_overview_card(workspace, "op-save-c01", first, 0)
    overview_card_workspace.save_overview_card(workspace, "op-save-c02", second, 1)
    return first, second


def test_inventory_lists_two_current_cards_in_stable_order_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, workspace = _workspace(tmp_path)
    first, second = _save_two_current(workspace)
    before = _inventory(runtime)
    monkeypatch.setattr(
        workspace,
        "commit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("inventory 不得写工作区")
        ),
    )

    inventory = overview_card_workspace.list_overview_cards(workspace)

    assert [item["chapter_id"] for item in inventory["cards"]] == ["c01", "c02"]
    assert [item["freshness"] for item in inventory["cards"]] == [
        "CURRENT",
        "CURRENT",
    ]
    assert all(item["stale_reasons"] == [] for item in inventory["cards"])
    assert inventory["watermarks"]["overview_cards"]["version"] == 2
    assert len(inventory["watermarks"]["overview_cards"]["sha256"]) == 64
    for item, saved in zip(inventory["cards"], (first, second), strict=True):
        assert item["overview_cards_version"] == 2
        assert (
            item["overview_cards_sha256"]
            == inventory["watermarks"]["overview_cards"]["sha256"]
        )
        assert item["chapter_revision_ref"] == saved["m9"]["chapter_revision_ref"]
        assert item["facts_snapshot"] == saved["facts_snapshot"]
        assert item["chapter_index_snapshot"] == saved["chapter_index_snapshot"]
        assert item["synopsis"] == saved["m9"]["synopsis"]
    inventory["cards"][0]["synopsis"] = "调用方改动"
    assert overview_card_workspace.list_overview_cards(workspace)["cards"][0][
        "synopsis"
    ] == first["m9"]["synopsis"]
    assert _inventory(runtime) == before


@pytest.mark.parametrize("drift", ["facts", "index"])
def test_global_source_advance_marks_both_old_cards_stale(
    tmp_path: Path,
    drift: str,
) -> None:
    _, workspace = _workspace(tmp_path)
    _save_two_current(workspace)
    if drift == "facts":
        changed_facts = _facts()
        changed_facts.append(_fact("f004", "c01", "甲拿起钥匙。"))
        workspace.commit("op-inventory-facts-v2", {"facts": changed_facts}, {"facts": 1})
    else:
        workspace.commit(
            "op-inventory-index-v2",
            {
                "chapter_index": [
                    _revision_ref("c01", revision_no=3),
                    _revision_ref("c02"),
                ]
            },
            {"chapter_index": 1},
        )

    cards = overview_card_workspace.list_overview_cards(workspace)["cards"]
    by_chapter = {item["chapter_id"]: item for item in cards}

    assert by_chapter["c01"]["freshness"] == "STALE"
    assert by_chapter["c02"]["freshness"] == "STALE"
    if drift == "facts":
        assert by_chapter["c01"]["stale_reasons"] == ["FACTS_SNAPSHOT_CHANGED"]
        assert by_chapter["c02"]["stale_reasons"] == ["FACTS_SNAPSHOT_CHANGED"]
    else:
        assert by_chapter["c01"]["stale_reasons"] == [
            "CHAPTER_INDEX_SNAPSHOT_CHANGED",
            "CHAPTER_REVISION_CHANGED",
        ]
        assert by_chapter["c02"]["stale_reasons"] == [
            "CHAPTER_INDEX_SNAPSHOT_CHANGED"
        ]


def test_new_global_snapshot_card_is_current_while_unrefreshed_old_card_is_stale(
    tmp_path: Path,
) -> None:
    _, workspace = _workspace(tmp_path)
    first, _ = _save_two_current(workspace)
    changed_facts = _facts()
    changed_facts.append(_fact("f004", "c01", "甲拿起钥匙。"))
    workspace.commit("op-facts-v2", {"facts": changed_facts}, {"facts": 1})
    refreshed_second = _result(
        workspace,
        "c02",
        note="new-global-snapshot",
        generated_at="2026-08-19 21:03:00",
    )
    overview_card_workspace.save_overview_card(
        workspace,
        "op-refresh-c02",
        refreshed_second,
        2,
    )

    cards = overview_card_workspace.list_overview_cards(workspace)["cards"]
    by_chapter = {item["chapter_id"]: item for item in cards}

    assert by_chapter["c01"]["freshness"] == "STALE"
    assert by_chapter["c01"]["stale_reasons"] == ["FACTS_SNAPSHOT_CHANGED"]
    assert by_chapter["c01"]["facts_snapshot"] == first["facts_snapshot"]
    assert by_chapter["c02"]["freshness"] == "CURRENT"
    assert by_chapter["c02"]["stale_reasons"] == []
    assert by_chapter["c02"]["facts_snapshot"] == refreshed_second["facts_snapshot"]


def test_empty_inventory_is_stable_and_does_not_create_state(tmp_path: Path) -> None:
    runtime = tmp_path / "empty-runtime"
    workspace = WorkspaceRouter(runtime).create_project(ALICE, "空概览项目")
    before = _inventory(runtime)

    inventory = overview_card_workspace.list_overview_cards(workspace)

    assert inventory == {
        "watermarks": {
            "overview_cards": {"version": 0, "sha256": None},
            "facts": {"version": 0, "sha256": None},
            "chapter_index": {"version": 0, "sha256": None},
        },
        "cards": [],
    }
    assert _inventory(runtime) == before


@pytest.mark.parametrize("changed_key", ["overview_cards", "facts", "chapter_index"])
def test_inventory_rejects_any_watermark_change_during_listing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_key: str,
) -> None:
    _, workspace = _workspace(tmp_path)
    _save_two_current(workspace)
    entry = workspace.read(changed_key)
    real_inspect = overview_workspace.inspect_freshness
    changed = False

    def inspect_then_change(handle, saved_result):
        nonlocal changed
        result = real_inspect(handle, saved_result)
        if not changed:
            changed = True
            workspace.commit(
                f"op-inventory-change-{changed_key}",
                {changed_key: entry["payload"]},
                {changed_key: entry["version"]},
            )
        return result

    monkeypatch.setattr(
        overview_workspace,
        "inspect_freshness",
        inspect_then_change,
    )

    with pytest.raises(
        overview_card_workspace.OverviewCardWorkspaceError,
        match=f"INVENTORY_WATERMARK_CHANGED:{changed_key}",
    ):
        overview_card_workspace.list_overview_cards(workspace)


def test_inventory_bad_store_binding_path_and_freshness_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caller_path = tmp_path / "caller-path"
    with pytest.raises(
        overview_card_workspace.OverviewCardWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        overview_card_workspace.list_overview_cards(  # type: ignore[arg-type]
            caller_path
        )
    assert not caller_path.exists()

    _, corrupt = _workspace(tmp_path / "corrupt", ALICE)
    corrupt.commit(
        "op-corrupt-inventory-store",
        {"overview_cards": {"bad": True}},
        {"overview_cards": 0},
    )
    with pytest.raises(
        overview_card_workspace.OverviewCardWorkspaceError,
        match="OVERVIEW_CARD_STORE_INVALID",
    ):
        overview_card_workspace.list_overview_cards(corrupt)

    _, alice = _workspace(tmp_path / "alice", ALICE)
    alice_result = _result(alice, "c01")
    _, bob = _workspace(tmp_path / "bob", BOB)
    bob.commit(
        "op-cross-author-inventory-store",
        {
            "overview_cards": {
                "store_version": overview_card_workspace.STORE_VERSION,
                "chapters": {"c01": alice_result},
            }
        },
        {"overview_cards": 0},
    )
    with pytest.raises(
        overview_card_workspace.OverviewCardWorkspaceError,
        match="OVERVIEW_RESULT_WORKSPACE_MISMATCH",
    ):
        overview_card_workspace.list_overview_cards(bob)

    _, bad_freshness = _workspace(tmp_path / "freshness", ALICE)
    _save_two_current(bad_freshness)
    monkeypatch.setattr(
        overview_workspace,
        "inspect_freshness",
        lambda *args, **kwargs: {
            "freshness": "CURRENT",
            "stale_reasons": ["IMPOSSIBLE_REASON"],
        },
    )
    with pytest.raises(
        overview_card_workspace.OverviewCardWorkspaceError,
        match="INVENTORY_FRESHNESS_RESULT_INVALID",
    ):
        overview_card_workspace.list_overview_cards(bad_freshness)


def test_inventory_is_byte_stable_after_process_restart(tmp_path: Path) -> None:
    runtime, workspace = _workspace(tmp_path)
    _save_two_current(workspace)
    expected = overview_card_workspace.list_overview_cards(workspace)
    script = """
import json
import sys
from mvp import overview_card_workspace
from mvp.workspace import WorkspaceRouter
handle = WorkspaceRouter(sys.argv[1]).open_project(sys.argv[2], sys.argv[3])
result = overview_card_workspace.list_overview_cards(handle)
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
        text=False,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr.decode()
    assert completed.stdout == _canonical(expected) + b"\n"


def test_save_restart_read_is_byte_equivalent_current_and_deep_copied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, workspace = _workspace(tmp_path)
    result = _result(workspace, "c01")
    commit_calls = 0
    real_commit = workspace.commit

    def counted_commit(*args, **kwargs):
        nonlocal commit_calls
        commit_calls += 1
        return real_commit(*args, **kwargs)

    monkeypatch.setattr(workspace, "commit", counted_commit)
    monkeypatch.setattr(
        overview_workspace,
        "execute",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("保存概览卡不得重新生成或调用 provider")
        ),
    )
    receipt = overview_card_workspace.save_overview_card(
        workspace,
        "op-save-c01",
        result,
        0,
    )
    loaded = overview_card_workspace.read_overview_card(workspace, "c01")

    assert commit_calls == 1
    assert receipt["versions"] == {"overview_cards": 1}
    assert loaded["version"] == 1
    assert len(loaded["sha256"]) == 64
    assert _canonical(loaded["overview_result"]) == _canonical(result)
    loaded["overview_result"]["m9"]["synopsis"] = "调用方改动"
    assert overview_card_workspace.read_overview_card(workspace, "c01")[
        "overview_result"
    ] == result

    script = """
import json
import sys
from mvp import overview_card_workspace, overview_workspace
from mvp.workspace import WorkspaceRouter
handle = WorkspaceRouter(sys.argv[1]).open_project(sys.argv[2], sys.argv[3])
loaded = overview_card_workspace.read_overview_card(handle, 'c01')
freshness = overview_workspace.inspect_freshness(handle, loaded['overview_result'])
print(json.dumps({'loaded': loaded, 'freshness': freshness}, ensure_ascii=False, sort_keys=True))
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
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    reopened = json.loads(completed.stdout)
    assert _canonical(reopened["loaded"]["overview_result"]) == _canonical(result)
    assert reopened["freshness"]["freshness"] == "CURRENT"
    assert reopened["freshness"]["stale_reasons"] == []


def test_same_operation_is_idempotent_and_conflicts_do_not_overwrite(
    tmp_path: Path,
) -> None:
    _, workspace = _workspace(tmp_path)
    original = _result(workspace, "c01")
    first = overview_card_workspace.save_overview_card(
        workspace, "op-idempotent", original, 0
    )
    replay = overview_card_workspace.save_overview_card(
        workspace, "op-idempotent", original, 0
    )
    changed = _result(
        workspace,
        "c01",
        note="changed",
        generated_at="2026-08-19 21:01:00",
    )

    assert first["generation_id"] == replay["generation_id"]
    assert replay["replayed"] is True
    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        overview_card_workspace.save_overview_card(
            workspace, "op-idempotent", changed, 0
        )
    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        overview_card_workspace.save_overview_card(
            workspace, "op-stale-version", changed, 0
        )
    assert overview_card_workspace.read_overview_card(workspace, "c01")[
        "overview_result"
    ] == original


@pytest.mark.parametrize("drift", ["facts", "index", "both"])
def test_stale_card_is_rejected_before_overview_card_write(
    tmp_path: Path,
    drift: str,
) -> None:
    runtime, workspace = _workspace(tmp_path)
    result = _result(workspace, "c01")
    if drift in {"facts", "both"}:
        changed_facts = _facts()
        changed_facts.append(_fact("f004", "c01", "甲拿起钥匙。"))
        workspace.commit(
            "op-facts-drift",
            {"facts": changed_facts},
            {"facts": 1},
        )
    if drift in {"index", "both"}:
        workspace.commit(
            "op-index-drift",
            {
                "chapter_index": [
                    _revision_ref("c01", revision_no=3),
                    _revision_ref("c02"),
                ]
            },
            {"chapter_index": 1},
        )
    before = _inventory(runtime)

    with pytest.raises(
        overview_card_workspace.OverviewCardWorkspaceError,
        match="OVERVIEW_RESULT_NOT_CURRENT",
    ):
        overview_card_workspace.save_overview_card(
            workspace,
            f"op-save-stale-{drift}",
            result,
            0,
        )

    assert workspace.read("overview_cards") is None
    assert _inventory(runtime) == before


def test_saved_card_can_be_read_as_stale_without_automatic_overwrite(
    tmp_path: Path,
) -> None:
    _, workspace = _workspace(tmp_path)
    result = _result(workspace, "c01")
    overview_card_workspace.save_overview_card(workspace, "op-save", result, 0)
    changed_facts = _facts()
    changed_facts.append(_fact("f004", "c01", "甲拿起钥匙。"))
    workspace.commit("op-facts-drift", {"facts": changed_facts}, {"facts": 1})

    loaded = overview_card_workspace.read_overview_card(workspace, "c01")
    freshness = overview_workspace.inspect_freshness(
        workspace,
        loaded["overview_result"],
    )

    assert freshness["freshness"] == "STALE"
    assert freshness["stale_reasons"] == ["FACTS_SNAPSHOT_CHANGED"]
    assert loaded["version"] == 1
    assert loaded["overview_result"] == result
    assert workspace.read("overview_cards")["version"] == 1


def test_bad_cross_author_path_duplicate_and_corrupt_store_fail_closed(
    tmp_path: Path,
) -> None:
    _, alice = _workspace(tmp_path / "alice", ALICE)
    result = _result(alice, "c01")
    bad = copy.deepcopy(result)
    bad.pop("workspace_binding")
    with pytest.raises(
        overview_card_workspace.OverviewCardWorkspaceError,
        match="OVERVIEW_RESULT_INVALID",
    ):
        overview_card_workspace.save_overview_card(alice, "op-bad", bad, 0)

    inconsistent = copy.deepcopy(result)
    inconsistent["m9"]["chapter_ref"] = "c02"
    with pytest.raises(
        overview_card_workspace.OverviewCardWorkspaceError,
        match="OVERVIEW_RESULT_INVALID",
    ):
        overview_card_workspace.save_overview_card(
            alice, "op-inconsistent", inconsistent, 0
        )

    _, bob = _workspace(tmp_path / "bob", BOB)
    with pytest.raises(
        overview_card_workspace.OverviewCardWorkspaceError,
        match="OVERVIEW_RESULT_WORKSPACE_MISMATCH",
    ):
        overview_card_workspace.save_overview_card(bob, "op-cross-author", result, 0)

    caller_path = tmp_path / "caller-path"
    with pytest.raises(
        overview_card_workspace.OverviewCardWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        overview_card_workspace.save_overview_card(  # type: ignore[arg-type]
            caller_path,
            "op-path",
            result,
            0,
        )
    assert not caller_path.exists()

    _, duplicate_store = _workspace(tmp_path / "duplicate", ALICE)
    duplicate_result = _result(duplicate_store, "c01")
    duplicate_store.commit(
        "op-duplicate-store",
        {
            "overview_cards": {
                "store_version": overview_card_workspace.STORE_VERSION,
                "chapters": {
                    "c01": duplicate_result,
                    "c02": duplicate_result,
                },
            }
        },
        {"overview_cards": 0},
    )
    with pytest.raises(
        overview_card_workspace.OverviewCardWorkspaceError,
        match="OVERVIEW_CARD_CHAPTER_IDENTITY_DUPLICATE",
    ):
        overview_card_workspace.read_overview_card(duplicate_store, "c01")

    _, corrupt_store = _workspace(tmp_path / "corrupt", ALICE)
    corrupt_store.commit(
        "op-corrupt-store",
        {"overview_cards": {"bad": True}},
        {"overview_cards": 0},
    )
    with pytest.raises(
        overview_card_workspace.OverviewCardWorkspaceError,
        match="OVERVIEW_CARD_STORE_INVALID",
    ):
        overview_card_workspace.read_overview_card(corrupt_store, "c01")


def test_updating_one_chapter_preserves_the_other_chapter(tmp_path: Path) -> None:
    _, workspace = _workspace(tmp_path)
    first = _result(workspace, "c01")
    second = _result(workspace, "c02")
    overview_card_workspace.save_overview_card(workspace, "op-save-c01", first, 0)
    overview_card_workspace.save_overview_card(workspace, "op-save-c02", second, 1)
    second_before = overview_card_workspace.read_overview_card(
        workspace, "c02"
    )["overview_result"]

    first_updated = _result(
        workspace,
        "c01",
        note="updated",
        generated_at="2026-08-19 21:02:00",
    )
    receipt = overview_card_workspace.save_overview_card(
        workspace,
        "op-update-c01",
        first_updated,
        2,
    )

    assert receipt["versions"] == {"overview_cards": 3}
    assert overview_card_workspace.read_overview_card(workspace, "c01")[
        "overview_result"
    ] == first_updated
    assert overview_card_workspace.read_overview_card(workspace, "c02")[
        "overview_result"
    ] == second_before
