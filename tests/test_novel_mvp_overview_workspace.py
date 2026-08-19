from __future__ import annotations

import copy
import hashlib
import inspect
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
    from mvp import overview, overview_tool, overview_workspace
    from mvp.workspace import ProjectNotFoundError, WorkspaceRouter
finally:
    sys.path.pop(0)


ALICE = "auth:m9-workspace-alice"
BOB = "auth:m9-workspace-bob"
GENERATED_AT = "2026-08-19 21:00:00"
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


def _fact(
    fact_id: str,
    chapter_id: str,
    quote: str,
    *,
    status: str = "confirmed",
    bad_anchor: bool = False,
    revision_no: int = 2,
) -> dict:
    revision_ref = _revision_ref(chapter_id, revision_no=revision_no)
    text = TEXTS[chapter_id]
    start = text.index(quote)
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": chapter_id,
        "text": quote,
        "quote": quote,
        "status": status,
        "source": "M9_WORKSPACE_SYNTHETIC_FIXTURE",
        "note": "",
        "added_at": "2026-08-19 20:00:00",
        "seg": 1,
        "chapter_revision_ref": revision_ref,
        "anchor_ref": {
            **revision_ref,
            "coordinate_basis": overview.COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": "0" * 64 if bad_anchor else _sha(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


def _facts() -> list[dict]:
    return [
        _fact("f001", "c01", "甲拿起钥匙。"),
        _fact("f002", "c01", "乙看见了钥匙。", status="confirmed"),
        _fact("f003", "c02", "丙关上窗户。"),
    ]


def _provider_result(fact_ids: list[str]) -> dict:
    return {
        "synopsis": "目标章事实被投影为一张概览。",
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


def _seed(workspace, *, facts: list[dict] | None = None) -> tuple[dict, dict]:
    facts = copy.deepcopy(facts if facts is not None else _facts())
    refs = [_revision_ref("c01"), _revision_ref("c02")]
    facts_receipt = workspace.commit("op-m9-facts", {"facts": facts}, {"facts": 0})
    index_receipt = workspace.commit(
        "op-m9-index-v1",
        {"chapter_index": refs},
        {"chapter_index": 0},
    )
    index_receipt = workspace.commit(
        "op-m9-index-v2",
        {"chapter_index": refs},
        {"chapter_index": 1},
    )
    return facts_receipt, index_receipt


def _offline_provider(facts: list[dict], current_ref: dict) -> overview.OverviewProvider:
    request = {
        "facts": facts,
        "current_revision_ref": current_ref,
        "source_revision": "test-only-provider-key",
        "generated_at": GENERATED_AT,
    }
    key = overview.provider_key_for_request(request)
    return overview_tool.offline_overview_provider(
        {key: _provider_result([fact["id"] for fact in facts])}
    )


def _execute_c01(workspace) -> dict:
    selected = [fact for fact in _facts() if fact["chapter_id"] == "c01"]
    return overview_workspace.execute(
        workspace,
        "c01",
        GENERATED_AT,
        _offline_provider(selected, _revision_ref("c01")),
    )


def test_normal_read_preserves_independent_snapshot_identities_and_never_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "M9 合成项目")
    facts_receipt, index_receipt = _seed(workspace)
    before = _inventory(runtime_root)
    read_calls: list[str] = []
    real_read = workspace.read
    monkeypatch.setattr(
        workspace,
        "read",
        lambda key: read_calls.append(key) or real_read(key),
    )
    monkeypatch.setattr(
        workspace,
        "commit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("M9 工作区适配器不得 commit")
        ),
    )

    selected = [fact for fact in _facts() if fact["chapter_id"] == "c01"]
    frozen_provider = _offline_provider(selected, _revision_ref("c01"))
    provider_calls: list[dict] = []

    def provider(request: dict) -> dict:
        provider_calls.append(copy.deepcopy(request))
        return frozen_provider(request)

    result = overview_workspace.execute(
        workspace,
        "c01",
        GENERATED_AT,
        provider,
    )

    assert read_calls == [
        "facts",
        "chapter_index",
        "facts",
        "chapter_index",
        "facts",
        "chapter_index",
    ]
    assert len(provider_calls) == 1
    assert result["facts_snapshot"] == {
        "version": facts_receipt["versions"]["facts"],
        "sha256": facts_receipt["payload_sha256"]["facts"],
    }
    assert result["chapter_index_snapshot"] == {
        "version": index_receipt["versions"]["chapter_index"],
        "sha256": index_receipt["payload_sha256"]["chapter_index"],
    }
    assert result["workspace_binding"] == {
        "author_id": workspace.author_id,
        "project_id": workspace.project_id,
    }
    assert result["facts_snapshot"]["version"] != result["chapter_index_snapshot"]["version"]
    assert result["m9"]["chapter_ref"] == "c01"
    assert result["m9"]["source_summary"]["fact_count"] == 2
    assert _inventory(runtime_root) == before
    assert list(inspect.signature(overview_workspace.execute).parameters) == [
        "workspace",
        "chapter_id",
        "generated_at",
        "overview_provider",
    ]


def test_source_change_between_pre_reads_rejects_before_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime-pre-race"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "预读竞态")
    _seed(workspace)
    facts = _facts()
    refs = [_revision_ref("c01"), _revision_ref("c02")]
    real_read = workspace.read
    read_count = 0
    inventory_after_external: list[tuple[str, bool, bytes | None]] | None = None
    provider_calls: list[dict] = []

    def racing_read(logical_key: str):
        nonlocal read_count, inventory_after_external
        read_count += 1
        value = real_read(logical_key)
        if read_count == 2:
            workspace.commit(
                "op-m9-external-pre-provider",
                {"facts": facts, "chapter_index": refs},
                {"facts": 1, "chapter_index": 2},
            )
            inventory_after_external = _inventory(runtime_root)
        return value

    def provider(_request: dict) -> dict:
        provider_calls.append(copy.deepcopy(_request))
        return _provider_result(["f001", "f002"])

    monkeypatch.setattr(workspace, "read", racing_read)
    with pytest.raises(
        overview_workspace.OverviewWorkspaceError,
        match="M9_SOURCE_CHANGED_BEFORE_PROVIDER",
    ):
        overview_workspace.execute(
            workspace,
            "c01",
            GENERATED_AT,
            provider,
        )

    assert provider_calls == []
    assert real_read("facts")["version"] == 2
    assert real_read("chapter_index")["version"] == 3
    assert _inventory(runtime_root) == inventory_after_external


@pytest.mark.parametrize("changed_key", ["facts", "chapter_index"])
def test_source_change_during_provider_discards_card_and_keeps_new_state(
    tmp_path: Path,
    changed_key: str,
) -> None:
    runtime_root = tmp_path / f"runtime-provider-{changed_key}"
    workspace = WorkspaceRouter(runtime_root).create_project(
        ALICE, "Provider 竞态"
    )
    _seed(workspace)
    facts = _facts()
    refs = [_revision_ref("c01"), _revision_ref("c02")]
    provider_calls: list[dict] = []
    inventory_after_external = None

    def provider(request: dict) -> dict:
        nonlocal inventory_after_external
        provider_calls.append(copy.deepcopy(request))
        payload = facts if changed_key == "facts" else refs
        expected_version = 1 if changed_key == "facts" else 2
        workspace.commit(
            f"op-m9-provider-change-{changed_key}",
            {changed_key: payload},
            {changed_key: expected_version},
        )
        inventory_after_external = _inventory(runtime_root)
        return _provider_result(["f001", "f002"])

    with pytest.raises(
        overview_workspace.OverviewWorkspaceError,
        match="M9_SOURCE_CHANGED_DURING_PROVIDER",
    ):
        overview_workspace.execute(
            workspace,
            "c01",
            GENERATED_AT,
            provider,
        )

    assert len(provider_calls) == 1
    expected_after = 2 if changed_key == "facts" else 3
    assert workspace.read(changed_key)["version"] == expected_after
    other_key = "chapter_index" if changed_key == "facts" else "facts"
    expected_other = 2 if other_key == "chapter_index" else 1
    assert workspace.read(other_key)["version"] == expected_other
    assert _inventory(runtime_root) == inventory_after_external


def test_unchanged_saved_card_is_current_without_provider_or_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "当前卡项目")
    _seed(workspace)
    saved = _execute_c01(workspace)
    before = _inventory(runtime_root)
    monkeypatch.setattr(
        workspace,
        "commit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("freshness 不得 commit")
        ),
    )
    monkeypatch.setattr(
        overview_tool,
        "execute",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("freshness 不得重新生成或调用 provider")
        ),
    )

    result = overview_workspace.inspect_freshness(workspace, saved)

    assert result["freshness"] == "CURRENT"
    assert result["stale_reasons"] == []
    assert result["saved_basis"] == result["current_basis"]
    assert _inventory(runtime_root) == before
    assert list(inspect.signature(overview_workspace.inspect_freshness).parameters) == [
        "workspace",
        "saved_result",
    ]


@pytest.mark.parametrize(
    ("change_facts", "change_index", "expected_reasons"),
    [
        (True, False, ["FACTS_SNAPSHOT_CHANGED"]),
        (
            False,
            True,
            ["CHAPTER_INDEX_SNAPSHOT_CHANGED", "CHAPTER_REVISION_CHANGED"],
        ),
        (
            True,
            True,
            [
                "FACTS_SNAPSHOT_CHANGED",
                "CHAPTER_INDEX_SNAPSHOT_CHANGED",
                "CHAPTER_REVISION_CHANGED",
            ],
        ),
    ],
)
def test_normal_snapshot_changes_return_stable_stale_with_all_reasons(
    tmp_path: Path,
    change_facts: bool,
    change_index: bool,
    expected_reasons: list[str],
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(ALICE, "换版项目")
    _seed(workspace)
    saved = _execute_c01(workspace)
    if change_facts:
        changed_facts = _facts()
        changed_facts.append(_fact("f004", "c01", "甲拿起钥匙。"))
        workspace.commit(
            "op-m9-facts-v2",
            {"facts": changed_facts},
            {"facts": 1},
        )
    if change_index:
        workspace.commit(
            "op-m9-index-v3",
            {
                "chapter_index": [
                    _revision_ref("c01", revision_no=3),
                    _revision_ref("c02"),
                ]
            },
            {"chapter_index": 2},
        )
    before = _inventory(tmp_path / "runtime")

    result = overview_workspace.inspect_freshness(workspace, saved)

    assert result["freshness"] == "STALE"
    assert result["stale_reasons"] == expected_reasons
    assert _inventory(tmp_path / "runtime") == before


def test_multi_chapter_facts_never_enter_other_chapter_provider(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(ALICE, "多章项目")
    _seed(workspace)
    captured: list[dict] = []

    def provider(request: dict) -> dict:
        captured.append(copy.deepcopy(request))
        return _provider_result(["f001", "f002"])

    result = overview_workspace.execute(workspace, "c01", GENERATED_AT, provider)

    assert [[fact["id"] for fact in call["facts"]] for call in captured] == [
        ["f001", "f002"]
    ]
    assert "f003" not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize(
    ("mutate_index", "mutate_facts", "reason"),
    [
        (
            lambda refs: refs.pop(0),
            lambda facts: None,
            "CURRENT_REVISION_REF_MISSING:c01",
        ),
        (
            lambda refs: refs.append(copy.deepcopy(refs[0])),
            lambda facts: None,
            "CURRENT_REVISION_REF_DUPLICATE:c01",
        ),
        (
            lambda refs: None,
            lambda facts: facts[0].update(
                chapter_revision_ref=_revision_ref("c01", revision_no=1)
            ),
            "FACT_CURRENT_REVISION_REF_MISMATCH:f001",
        ),
    ],
)
def test_current_ref_missing_duplicate_or_mismatch_rejects_before_provider(
    tmp_path: Path,
    mutate_index,
    mutate_facts,
    reason: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / reason.split(":")[0]).create_project(
        ALICE, "坏 current ref"
    )
    facts = _facts()
    refs = [_revision_ref("c01"), _revision_ref("c02")]
    mutate_index(refs)
    mutate_facts(facts)
    workspace.commit("op-facts", {"facts": facts}, {"facts": 0})
    workspace.commit("op-index", {"chapter_index": refs}, {"chapter_index": 0})
    called = False

    def provider(_request: dict) -> dict:
        nonlocal called
        called = True
        return _provider_result(["f001", "f002"])

    with pytest.raises(overview_workspace.OverviewWorkspaceError, match=reason):
        overview_workspace.execute(workspace, "c01", GENERATED_AT, provider)
    assert called is False


def test_bad_anchor_and_bad_provider_remain_closed_by_existing_m9_core(
    tmp_path: Path,
) -> None:
    bad_anchor_workspace = WorkspaceRouter(tmp_path / "bad-anchor").create_project(
        ALICE, "坏锚"
    )
    facts = _facts()
    facts[0] = _fact("f001", "c01", "甲拿起钥匙。", bad_anchor=True)
    _seed(bad_anchor_workspace, facts=facts)
    called = False

    def should_not_run(_request: dict) -> dict:
        nonlocal called
        called = True
        return _provider_result(["f001", "f002"])

    with pytest.raises(overview.OverviewError, match="C4_ANCHOR_QUOTE_INVALID:f001"):
        overview_workspace.execute(
            bad_anchor_workspace,
            "c01",
            GENERATED_AT,
            should_not_run,
        )
    assert called is False

    bad_provider_workspace = WorkspaceRouter(tmp_path / "bad-provider").create_project(
        ALICE, "坏 provider"
    )
    _seed(bad_provider_workspace)
    with pytest.raises(overview.OverviewError, match="UNCOVERED_FACT_REFS:f002"):
        overview_workspace.execute(
            bad_provider_workspace,
            "c01",
            GENERATED_AT,
            lambda _request: {
                "synopsis": "缺一条事实。",
                "beats": [
                    {"text": "只覆盖一条。", "fact_refs": ["f001"], "visual_hint": ""}
                ],
                "orphan_refs": [],
                "visual_hint": "",
            },
        )


def test_empty_keys_and_path_impersonation_do_not_create_workspace_state(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "空项目")
    before = _inventory(runtime_root)

    with pytest.raises(
        overview_workspace.OverviewWorkspaceError,
        match="FACTS_SNAPSHOT_MISSING",
    ):
        overview_workspace.execute(
            workspace,
            "c01",
            GENERATED_AT,
            lambda _request: _provider_result([]),
        )
    assert _inventory(runtime_root) == before

    caller_path = tmp_path / "caller-project"
    with pytest.raises(
        overview_workspace.OverviewWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        overview_workspace.execute(  # type: ignore[arg-type]
            caller_path,
            "c01",
            GENERATED_AT,
            lambda _request: _provider_result([]),
        )
    assert not caller_path.exists()


def test_cross_author_project_guess_cannot_escape_bound_handle(tmp_path: Path) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project(ALICE, "同名项目")
    _seed(alice)
    bob = router.create_project(BOB, "同名项目")

    with pytest.raises(
        overview_workspace.OverviewWorkspaceError,
        match="FACTS_SNAPSHOT_MISSING",
    ):
        overview_workspace.execute(
            bob,
            alice.project_id,
            GENERATED_AT,
            lambda _request: _provider_result([]),
        )
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project(BOB, alice.project_id)


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda saved: saved.pop("workspace_binding"),
            "SAVED_RESULT_SHAPE_INVALID",
        ),
        (
            lambda saved: saved["m9"].update(contract="NOT_M9"),
            "SAVED_M9_PROTOTYPE_IDENTITY_INVALID",
        ),
        (
            lambda saved: saved["m9"]["source_summary"].update(
                source_revision="tampered"
            ),
            "SAVED_M9_BASIS_INCONSISTENT",
        ),
    ],
)
def test_malformed_saved_card_is_rejected(
    tmp_path: Path,
    mutate,
    reason: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / reason).create_project(ALICE, "坏旧卡")
    _seed(workspace)
    saved = _execute_c01(workspace)
    mutate(saved)

    with pytest.raises(overview_workspace.OverviewWorkspaceError, match=reason):
        overview_workspace.inspect_freshness(workspace, saved)


def test_saved_card_binding_rejects_other_author_project_and_path(tmp_path: Path) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project(ALICE, "作者 A 项目")
    _seed(alice)
    saved = _execute_c01(alice)
    bob = router.create_project(BOB, "作者 B 项目")
    _seed(bob)
    other_alice_project = router.create_project(ALICE, "作者 A 另一个项目")
    _seed(other_alice_project)

    for wrong_handle in (bob, other_alice_project):
        with pytest.raises(
            overview_workspace.OverviewWorkspaceError,
            match="SAVED_WORKSPACE_BINDING_MISMATCH",
        ):
            overview_workspace.inspect_freshness(wrong_handle, saved)

    caller_path = tmp_path / "caller-path"
    with pytest.raises(
        overview_workspace.OverviewWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        overview_workspace.inspect_freshness(caller_path, saved)  # type: ignore[arg-type]
    assert not caller_path.exists()


def test_bad_current_facts_or_duplicate_current_ref_is_rejected(tmp_path: Path) -> None:
    bad_facts = WorkspaceRouter(tmp_path / "bad-facts").create_project(ALICE, "坏 facts")
    _seed(bad_facts)
    saved_bad_facts = _execute_c01(bad_facts)
    bad_facts.commit("op-bad-facts", {"facts": [{"bad": True}]}, {"facts": 1})
    with pytest.raises(
        overview_workspace.OverviewWorkspaceError,
        match="CURRENT_FACTS_SNAPSHOT_INVALID",
    ):
        overview_workspace.inspect_freshness(bad_facts, saved_bad_facts)

    duplicate_index = WorkspaceRouter(tmp_path / "duplicate-index").create_project(
        ALICE, "重复 current ref"
    )
    _seed(duplicate_index)
    saved_duplicate_index = _execute_c01(duplicate_index)
    duplicate_index.commit(
        "op-duplicate-index",
        {
            "chapter_index": [
                _revision_ref("c01"),
                _revision_ref("c01"),
                _revision_ref("c02"),
            ]
        },
        {"chapter_index": 2},
    )
    with pytest.raises(
        overview_workspace.OverviewWorkspaceError,
        match="CURRENT_REVISION_REF_DUPLICATE:c01",
    ):
        overview_workspace.inspect_freshness(duplicate_index, saved_duplicate_index)


def test_new_process_reopen_returns_same_snapshot_identities_and_m9_result(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(ALICE, "重启项目")
    _seed(workspace)
    selected = [fact for fact in _facts() if fact["chapter_id"] == "c01"]
    request = {
        "facts": selected,
        "current_revision_ref": _revision_ref("c01"),
        "source_revision": "test-only-provider-key",
        "generated_at": GENERATED_AT,
    }
    responses = {
        overview.provider_key_for_request(request): _provider_result(["f001", "f002"])
    }
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(json.dumps(responses, ensure_ascii=False), encoding="utf-8")
    expected = _execute_c01(workspace)
    script = """
import json
import sys
from mvp import overview_tool, overview_workspace
from mvp.workspace import WorkspaceRouter
responses = json.loads(open(sys.argv[5], encoding='utf-8').read())
handle = WorkspaceRouter(sys.argv[1]).open_project(sys.argv[2], sys.argv[3])
result = overview_workspace.execute(
    handle,
    'c01',
    sys.argv[4],
    overview_tool.offline_overview_provider(responses),
)
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PRODUCT_ROOT)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(runtime_root),
            ALICE,
            workspace.project_id,
            GENERATED_AT,
            str(responses_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == expected

    saved_path = tmp_path / "saved-result.json"
    saved_path.write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
    freshness_script = """
import json
import sys
from mvp import overview_workspace
from mvp.workspace import WorkspaceRouter
saved = json.loads(open(sys.argv[4], encoding='utf-8').read())
handle = WorkspaceRouter(sys.argv[1]).open_project(sys.argv[2], sys.argv[3])
result = overview_workspace.inspect_freshness(handle, saved)
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
"""
    freshness = subprocess.run(
        [
            sys.executable,
            "-c",
            freshness_script,
            str(runtime_root),
            ALICE,
            workspace.project_id,
            str(saved_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert freshness.returncode == 0, freshness.stderr
    freshness_result = json.loads(freshness.stdout)
    assert freshness_result["freshness"] == "CURRENT"
    assert freshness_result["stale_reasons"] == []
    assert freshness_result["saved_basis"] == freshness_result["current_basis"]
