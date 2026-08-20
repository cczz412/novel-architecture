from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        ask_tool,
        chapter_workspace,
        extract_tool,
        extract_workspace,
        fact_tool,
        fact_workspace,
        factstore,
        segment_workspace,
    )
    from mvp.workspace import (
        OperationConflictError,
        ProjectNotFoundError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


PRINCIPAL = "auth:fixture-author"
TEXT = "甲拿起钥匙。乙离开。"
QUOTE = "甲拿起钥匙。"
SECOND_TEXT = "丁点灯。丁又把灯吹灭。"
UPDATED_TEXT = "甲把钥匙交给乙。乙离开。"
SEGMENT_OPTIONS = {
    "seg_min_chars": 80,
    "seg_max_chars": 120,
    "halo_chars": 20,
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_ref() -> dict:
    return _revision_ref_for("c01", TEXT)


def _revision_ref_for(
    chapter_id: str,
    text: str,
    revision_no: int = 1,
) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": _sha256(text),
    }


def _fact_tool_request() -> dict:
    revision_ref = _revision_ref()
    return {
        "chapter": {
            "contract": "C1_CHAPTER_DOC",
            "version": "v1",
            "id": "c01",
            "title": "第一章",
            "kind": "draft",
            "text": TEXT,
            "added_at": "2026-08-19 14:00:00",
            "chapter_revision_ref": revision_ref,
        },
        "segments": [
            {
                "contract": "C2_SEGMENT",
                "version": "v1",
                "chapter_revision_ref": revision_ref,
                "seg": 1,
                "text": TEXT,
                "start": 0,
                "end": len(TEXT),
                "halo_before": "",
                "halo_after": "",
            }
        ],
        "candidates": [
            {
                "contract": "C3_FACT_CANDIDATE",
                "version": "v1",
                "chapter_revision_ref": revision_ref,
                "text": "甲拿起钥匙。",
                "quote": QUOTE,
                "seg": 1,
            }
        ],
        "source": "M4_STANDALONE_FIXTURE",
        "added_at": "2026-08-19 14:01:00",
    }


def _snapshot() -> list[dict]:
    return fact_tool.execute(_fact_tool_request())["facts"]


def _fact_for_chapter(
    fact_id: str,
    chapter_id: str,
    revision_text: str,
    quote: str,
    *,
    revision_no: int = 1,
) -> dict:
    fact = copy.deepcopy(_snapshot()[0])
    revision_ref = _revision_ref_for(chapter_id, revision_text, revision_no)
    start = revision_text.index(quote)
    fact.update(
        id=fact_id,
        chapter_id=chapter_id,
        text=quote,
        quote=quote,
        chapter_revision_ref=revision_ref,
        anchor_ref={
            **revision_ref,
            "coordinate_basis": factstore.ANCHOR_COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": _sha256(quote),
        },
    )
    return fact


def _canonical_bytes(value) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _open_workspace(tmp_path: Path):
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project(PRINCIPAL, "M4 合成项目")
    return runtime_root, router, workspace


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


def _commit_fact_view_sources(
    workspace,
    facts: list[dict],
    revision_refs: list[dict],
) -> dict:
    facts = factstore.validate_c4_v1_snapshot(facts)
    return workspace.commit(
        "op-current-fact-view-sources",
        {"facts": facts, "chapter_index": revision_refs},
        {"facts": 0, "chapter_index": 0},
    )


def _current_chapters() -> list[dict]:
    return [
        _fact_tool_request()["chapter"],
        {
            "contract": "C1_CHAPTER_DOC",
            "version": "v1",
            "id": "c02",
            "title": "第二章",
            "kind": "draft",
            "text": SECOND_TEXT,
            "added_at": "2026-08-19 14:00:00",
            "chapter_revision_ref": {
                "chapter_id": "c02",
                "revision_no": 1,
                "revision_text_sha256": _sha256(SECOND_TEXT),
            },
        },
    ]


def _prepare_current_c1_c2_c3(workspace) -> dict:
    chapters = _current_chapters()
    chapter_workspace.persist_c1_current_views(
        workspace,
        "op-current-c1",
        chapters,
        [copy.deepcopy(item["chapter_revision_ref"]) for item in chapters],
        {"chapters": 0, "chapter_index": 0},
    )
    segment_workspace.persist_current_segments(
        workspace,
        "op-current-c2",
        SEGMENT_OPTIONS["seg_min_chars"],
        SEGMENT_OPTIONS["seg_max_chars"],
        SEGMENT_OPTIONS["halo_chars"],
        0,
    )
    responses = {}
    for item in segment_workspace.read_current_segments(workspace)["items"]:
        chapter_id = item["chapter_revision_ref"]["chapter_id"]
        if chapter_id == "c01":
            fact_text, quote = "甲拿起钥匙。", QUOTE
        else:
            fact_text, quote = "丁点亮了灯。", "丁点灯"
        responses[extract_tool.item_key(item)] = {
            "data": {"facts": [{"text": fact_text, "quote": quote}]},
            "usage": {},
            "model": "FROZEN_OFFLINE_RESPONSE",
        }
    extract_workspace.persist_current_fact_candidates(
        workspace,
        "op-current-c3",
        responses,
        0,
    )
    return responses


def _subprocess_read(runtime_root: Path, project_id: str) -> dict:
    script = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from mvp.fact_workspace import read_snapshot
from mvp.workspace import WorkspaceRouter
workspace = WorkspaceRouter(sys.argv[2]).open_project(sys.argv[3], sys.argv[4])
print(json.dumps(read_snapshot(workspace), ensure_ascii=False, sort_keys=True, separators=(\",\", \":\")))
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(PRODUCT_ROOT),
            str(runtime_root),
            PRINCIPAL,
            project_id,
        ],
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def _subprocess_read_current(runtime_root: Path, project_id: str) -> dict:
    script = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from mvp.fact_workspace import read_current_snapshot
from mvp.workspace import WorkspaceRouter
workspace = WorkspaceRouter(sys.argv[2]).open_project(sys.argv[3], sys.argv[4])
print(json.dumps(read_current_snapshot(workspace), ensure_ascii=False, sort_keys=True, separators=(\",\", \":\")))
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(PRODUCT_ROOT),
            str(runtime_root),
            PRINCIPAL,
            project_id,
        ],
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_save_restart_read_and_m6_excludes_extracted_snapshot(tmp_path: Path) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    snapshot = _snapshot()

    receipt = fact_workspace.save_snapshot(
        workspace,
        operation_id="op-facts-save-01",
        snapshot=snapshot,
        expected_version=0,
    )
    restarted = _subprocess_read(runtime_root, workspace.project_id)

    assert set(receipt) == {
        "status",
        "operation_id",
        "version",
        "sha256",
        "generation_id",
        "replayed",
    }
    assert receipt["status"] == "COMMITTED" and receipt["version"] == 1
    assert _canonical_bytes(restarted["facts"]) == _canonical_bytes(snapshot)
    assert restarted["version"] == 1 and restarted["sha256"] == receipt["sha256"]
    result = ask_tool.execute(
        {
            "query": "钥匙",
            "facts": restarted["facts"],
            "current_revision_refs": [_revision_ref()],
        }
    )
    assert result["matches"] == []
    assert result["excluded_counts"]["extracted"] == 1


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda snapshot: snapshot[0]["anchor_ref"].update(
                slice_sha256="0" * 64
            ),
            "C4_ANCHOR_QUOTE_SHA_MISMATCH",
        ),
        (
            lambda snapshot: snapshot[0]["chapter_revision_ref"].update(
                revision_no=2
            ),
            "C4_ANCHOR_REVISION_REF_MISMATCH",
        ),
    ],
)
def test_bad_anchor_or_revision_ref_rejects_batch_and_preserves_current(
    tmp_path: Path,
    mutate,
    reason: str,
) -> None:
    _, _, workspace = _open_workspace(tmp_path)
    original = _snapshot()
    fact_workspace.save_snapshot(
        workspace,
        operation_id="op-facts-base",
        snapshot=original,
        expected_version=0,
    )
    broken = copy.deepcopy(original)
    mutate(broken)

    with pytest.raises(factstore.FactstoreError, match=reason):
        fact_workspace.save_snapshot(
            workspace,
            operation_id="op-facts-broken",
            snapshot=broken,
            expected_version=1,
        )

    current = fact_workspace.read_snapshot(workspace)
    assert current["version"] == 1
    assert current["facts"] == original


def test_same_operation_is_idempotent_and_payload_change_conflicts(tmp_path: Path) -> None:
    _, _, workspace = _open_workspace(tmp_path)
    snapshot = _snapshot()
    first = fact_workspace.save_snapshot(
        workspace,
        operation_id="op-facts-idempotent",
        snapshot=snapshot,
        expected_version=0,
    )
    replay = fact_workspace.save_snapshot(
        workspace,
        operation_id="op-facts-idempotent",
        snapshot=snapshot,
        expected_version=0,
    )
    changed = copy.deepcopy(snapshot)
    changed[0]["note"] = "同一 operation 不得换载荷"

    assert replay["generation_id"] == first["generation_id"]
    assert replay["replayed"] is True
    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        fact_workspace.save_snapshot(
            workspace,
            operation_id="op-facts-idempotent",
            snapshot=changed,
            expected_version=0,
        )
    assert fact_workspace.read_snapshot(workspace)["facts"] == snapshot


def test_version_conflict_has_zero_visible_write(tmp_path: Path) -> None:
    _, _, workspace = _open_workspace(tmp_path)
    snapshot = _snapshot()
    fact_workspace.save_snapshot(
        workspace,
        operation_id="op-facts-v1",
        snapshot=snapshot,
        expected_version=0,
    )
    changed = copy.deepcopy(snapshot)
    changed[0]["note"] = "这次应该被版本门挡住"

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        fact_workspace.save_snapshot(
            workspace,
            operation_id="op-facts-stale-version",
            snapshot=changed,
            expected_version=0,
        )

    current = fact_workspace.read_snapshot(workspace)
    assert current["version"] == 1 and current["facts"] == snapshot


def test_existing_statuses_are_preserved_without_author_action(tmp_path: Path) -> None:
    _, _, workspace = _open_workspace(tmp_path)
    extracted = _snapshot()[0]
    confirmed = copy.deepcopy(extracted)
    confirmed.update(
        id="f002",
        status="confirmed",
        decided_at="2026-08-19 14:02:00",
    )
    snapshot = [extracted, confirmed]

    fact_workspace.save_snapshot(
        workspace,
        operation_id="op-facts-preserve-status",
        snapshot=snapshot,
        expected_version=0,
    )

    reread = fact_workspace.read_snapshot(workspace)["facts"]
    assert [fact["status"] for fact in reread] == ["extracted", "confirmed"]
    assert reread == snapshot


def test_cross_author_project_guess_cannot_reach_saved_facts(tmp_path: Path) -> None:
    _, router, alice = _open_workspace(tmp_path)
    snapshot = _snapshot()
    fact_workspace.save_snapshot(
        alice,
        operation_id="op-alice-facts",
        snapshot=snapshot,
        expected_version=0,
    )
    bob = router.create_project("auth:other-author", "同名项目")

    assert fact_workspace.read_snapshot(bob) == {
        "version": 0,
        "sha256": None,
        "facts": [],
    }
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("auth:other-author", alice.project_id)
    assert fact_workspace.read_snapshot(alice)["facts"] == snapshot


def test_adapter_rejects_path_handle_without_creating_caller_directory(
    tmp_path: Path,
) -> None:
    caller_path = tmp_path / "caller-controlled"

    with pytest.raises(
        fact_workspace.FactWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        fact_workspace.save_snapshot(  # type: ignore[arg-type]
            caller_path,
            operation_id="op-path-forbidden",
            snapshot=_snapshot(),
            expected_version=0,
        )

    assert not caller_path.exists()


def test_materializes_two_current_chapters_as_one_extracted_snapshot_and_restarts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    _prepare_current_c1_c2_c3(workspace)
    real_execute = fact_tool.execute
    calls: list[dict] = []

    def capture(request: dict) -> dict:
        calls.append(copy.deepcopy(request))
        return real_execute(request)

    monkeypatch.setattr(fact_tool, "execute", capture)
    receipt = fact_workspace.materialize_current_extracted_snapshot(
        workspace,
        operation_id="op-materialize-current",
        source="M4_CURRENT_WORKSPACE",
        added_at="2026-08-19 16:30:00",
    )
    current = fact_workspace.read_snapshot(workspace)
    restarted = _subprocess_read(runtime_root, workspace.project_id)

    assert receipt["status"] == "COMMITTED" and receipt["version"] == 1
    assert len(calls) == 2
    assert calls[0]["existing_c4"] == []
    assert [fact["id"] for fact in calls[1]["existing_c4"]] == ["f001"]
    assert [fact["id"] for fact in current["facts"]] == ["f001", "f002"]
    assert [fact["status"] for fact in current["facts"]] == [
        "extracted",
        "extracted",
    ]
    assert [fact["chapter_id"] for fact in current["facts"]] == ["c01", "c02"]
    assert all(fact["source"] == "M4_CURRENT_WORKSPACE" for fact in current["facts"])
    assert all(fact["anchor_state"] == "VERIFIED" for fact in current["facts"])
    for fact in current["facts"]:
        assert fact["chapter_revision_ref"] == {
            key: fact["anchor_ref"][key]
            for key in (
                "chapter_id",
                "revision_no",
                "revision_text_sha256",
            )
        }
        assert fact["anchor_ref"]["slice_sha256"] == _sha256(fact["quote"])
        assert fact["anchor_ref"]["end"] - fact["anchor_ref"]["start"] == len(
            fact["quote"]
        )
    assert _canonical_bytes(restarted["facts"]) == _canonical_bytes(current["facts"])
    assert restarted["version"] == 1 and restarted["sha256"] == receipt["sha256"]


def test_second_chapter_bad_candidate_rejects_without_half_snapshot(
    tmp_path: Path,
) -> None:
    _, _, workspace = _open_workspace(tmp_path)
    _prepare_current_c1_c2_c3(workspace)
    candidates_state = workspace.read("fact_candidates")
    broken = copy.deepcopy(candidates_state["payload"])
    broken["items"][1]["quote"] = "丁"
    workspace.commit(
        "op-bad-second-candidate",
        {"fact_candidates": broken},
        {"fact_candidates": candidates_state["version"]},
    )

    with pytest.raises(
        fact_workspace.FactWorkspaceError,
        match="M4_MATERIALIZATION_REJECTED",
    ):
        fact_workspace.materialize_current_extracted_snapshot(
            workspace,
            operation_id="op-no-half-facts",
            source="M4_CURRENT_WORKSPACE",
            added_at="2026-08-19 16:31:00",
        )

    assert fact_workspace.read_snapshot(workspace) == {
        "version": 0,
        "sha256": None,
        "facts": [],
    }


def test_source_change_during_materialization_has_zero_facts_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, workspace = _open_workspace(tmp_path)
    _prepare_current_c1_c2_c3(workspace)
    real_execute = fact_tool.execute
    call_count = 0

    def execute_and_advance_segments(request: dict) -> dict:
        nonlocal call_count
        result = real_execute(request)
        call_count += 1
        if call_count == 1:
            segments_state = workspace.read("segments")
            workspace.commit(
                "op-segments-changed-during-m4",
                {"segments": segments_state["payload"]},
                {"segments": segments_state["version"]},
            )
        return result

    monkeypatch.setattr(fact_tool, "execute", execute_and_advance_segments)

    with pytest.raises(
        fact_workspace.FactWorkspaceSourceChangedError,
        match="M4_SOURCE_CHANGED_DURING_RUN",
    ):
        fact_workspace.materialize_current_extracted_snapshot(
            workspace,
            operation_id="op-m4-race",
            source="M4_CURRENT_WORKSPACE",
            added_at="2026-08-19 16:32:00",
        )

    assert fact_workspace.read_snapshot(workspace)["version"] == 0


def test_existing_facts_version_conflict_never_replaces_prior_batch(
    tmp_path: Path,
) -> None:
    _, _, workspace = _open_workspace(tmp_path)
    _prepare_current_c1_c2_c3(workspace)
    prior = _snapshot()
    fact_workspace.save_snapshot(
        workspace,
        operation_id="op-prior-facts",
        snapshot=prior,
        expected_version=0,
    )

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        fact_workspace.materialize_current_extracted_snapshot(
            workspace,
            operation_id="op-m4-existing-facts",
            source="M4_CURRENT_WORKSPACE",
            added_at="2026-08-19 16:33:00",
        )

    assert fact_workspace.read_snapshot(workspace)["facts"] == prior


def test_materialize_operation_is_idempotent_and_changed_payload_conflicts(
    tmp_path: Path,
) -> None:
    _, _, workspace = _open_workspace(tmp_path)
    _prepare_current_c1_c2_c3(workspace)
    first = fact_workspace.materialize_current_extracted_snapshot(
        workspace,
        operation_id="op-m4-idempotent",
        source="M4_CURRENT_WORKSPACE",
        added_at="2026-08-19 16:34:00",
    )
    replay = fact_workspace.materialize_current_extracted_snapshot(
        workspace,
        operation_id="op-m4-idempotent",
        source="M4_CURRENT_WORKSPACE",
        added_at="2026-08-19 16:34:00",
    )
    before = fact_workspace.read_snapshot(workspace)

    assert replay["replayed"] is True
    assert replay["generation_id"] == first["generation_id"]
    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        fact_workspace.materialize_current_extracted_snapshot(
            workspace,
            operation_id="op-m4-idempotent",
            source="M4_CURRENT_WORKSPACE",
            added_at="2026-08-19 16:34:01",
        )

    assert fact_workspace.read_snapshot(workspace) == before


def test_missing_or_stale_upstream_and_wrong_handle_reject_before_facts(
    tmp_path: Path,
) -> None:
    _, router, alice = _open_workspace(tmp_path)
    bob = router.create_project("auth:other-author", "同名项目")
    _prepare_current_c1_c2_c3(bob)
    index_state = bob.read("chapter_index")
    bob.commit(
        "op-stale-index",
        {"chapter_index": index_state["payload"]},
        {"chapter_index": index_state["version"]},
    )
    caller_path = tmp_path / "not-workspace"

    with pytest.raises(
        fact_workspace.FactWorkspaceError,
        match="M4_SOURCE_STATE_MISSING",
    ):
        fact_workspace.materialize_current_extracted_snapshot(
            alice,
            operation_id="op-missing-upstream",
            source="M4_CURRENT_WORKSPACE",
            added_at="2026-08-19 16:35:00",
        )
    with pytest.raises(
        fact_workspace.FactWorkspaceError,
        match="M4_CURRENT_SOURCE_INVALID",
    ):
        fact_workspace.materialize_current_extracted_snapshot(
            bob,
            operation_id="op-stale-upstream",
            source="M4_CURRENT_WORKSPACE",
            added_at="2026-08-19 16:35:00",
        )
    with pytest.raises(
        fact_workspace.FactWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        fact_workspace.materialize_current_extracted_snapshot(
            caller_path,
            operation_id="op-path",
            source="M4_CURRENT_WORKSPACE",
            added_at="2026-08-19 16:35:00",
        )
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project(PRINCIPAL, bob.project_id)

    assert fact_workspace.read_snapshot(alice)["version"] == 0
    assert fact_workspace.read_snapshot(bob)["version"] == 0
    assert not caller_path.exists()


def test_read_current_snapshot_returns_two_current_chapters_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    facts = [
        _fact_for_chapter("f001", "c01", TEXT, QUOTE),
        _fact_for_chapter("f002", "c02", SECOND_TEXT, "丁点灯。"),
    ]
    refs = [
        _revision_ref_for("c01", TEXT),
        _revision_ref_for("c02", SECOND_TEXT),
    ]
    receipt = _commit_fact_view_sources(workspace, facts, refs)
    before = _inventory(runtime_root)
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
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("current 事实视图不得写 workspace")
        ),
    )

    result = fact_workspace.read_current_snapshot(workspace)

    assert read_calls == ["facts", "chapter_index"] * 3
    assert [fact["id"] for fact in result["facts"]] == ["f001", "f002"]
    assert result["facts"] == facts
    assert result["stale_fact_ids"] == []
    assert result["facts_snapshot"] == {
        "version": receipt["versions"]["facts"],
        "sha256": receipt["payload_sha256"]["facts"],
    }
    assert result["chapter_index_snapshot"] == {
        "version": receipt["versions"]["chapter_index"],
        "sha256": receipt["payload_sha256"]["chapter_index"],
    }
    result["facts"][0]["text"] = "调用方修改返回值"
    assert fact_workspace.read_current_snapshot(workspace)["facts"] == facts
    assert _inventory(runtime_root) == before


def test_read_current_snapshot_excludes_only_advanced_chapter_and_keeps_history(
    tmp_path: Path,
) -> None:
    _, _, workspace = _open_workspace(tmp_path)
    facts = [
        _fact_for_chapter("f001", "c01", TEXT, QUOTE),
        _fact_for_chapter("f002", "c02", SECOND_TEXT, "丁点灯。"),
    ]
    refs = [
        _revision_ref_for("c01", TEXT),
        _revision_ref_for("c02", SECOND_TEXT),
    ]
    _commit_fact_view_sources(workspace, facts, refs)
    index_state = workspace.read("chapter_index")
    workspace.commit(
        "op-advance-only-c01",
        {
            "chapter_index": [
                _revision_ref_for("c01", UPDATED_TEXT, revision_no=2),
                refs[1],
            ]
        },
        {"chapter_index": index_state["version"]},
    )

    current = fact_workspace.read_current_snapshot(workspace)
    historical = fact_workspace.read_snapshot(workspace)

    assert [fact["id"] for fact in current["facts"]] == ["f002"]
    assert current["stale_fact_ids"] == ["f001"]
    assert current["facts_snapshot"]["version"] == 1
    assert current["chapter_index_snapshot"]["version"] == 2
    assert historical["facts"] == facts


def test_empty_facts_with_legal_current_index_returns_stable_empty_view(
    tmp_path: Path,
) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    receipt = workspace.commit(
        "op-current-index-only",
        {"chapter_index": [_revision_ref_for("c01", TEXT)]},
        {"chapter_index": 0},
    )
    before = _inventory(runtime_root)

    result = fact_workspace.read_current_snapshot(workspace)

    assert result == {
        "facts": [],
        "stale_fact_ids": [],
        "facts_snapshot": {"version": 0, "sha256": None},
        "chapter_index_snapshot": {
            "version": 1,
            "sha256": receipt["payload_sha256"]["chapter_index"],
        },
    }
    assert _inventory(runtime_root) == before


@pytest.mark.parametrize("fault", ["missing", "bad_shape", "duplicate"])
def test_missing_bad_or_duplicate_current_index_rejects_without_writes(
    tmp_path: Path,
    fault: str,
) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    fact = _fact_for_chapter("f001", "c01", TEXT, QUOTE)
    changes = {"facts": [fact]}
    expected = {"facts": 0}
    if fault == "bad_shape":
        changes["chapter_index"] = [{"chapter_id": "c01", "revision_no": 1}]
        expected["chapter_index"] = 0
    elif fault == "duplicate":
        ref = _revision_ref_for("c01", TEXT)
        changes["chapter_index"] = [ref, copy.deepcopy(ref)]
        expected["chapter_index"] = 0
    workspace.commit(f"op-current-index-{fault}", changes, expected)
    before = _inventory(runtime_root)

    with pytest.raises(
        fact_workspace.FactWorkspaceError,
        match="M4_CURRENT_CHAPTER_INDEX",
    ):
        fact_workspace.read_current_snapshot(workspace)

    assert _inventory(runtime_root) == before


@pytest.mark.parametrize("fault", ["unknown_chapter", "bad_revision_ref"])
def test_unknown_chapter_or_invalid_fact_revision_rejects_whole_view(
    tmp_path: Path,
    fault: str,
) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    if fault == "unknown_chapter":
        fact = _fact_for_chapter("f003", "c03", "丙关上门。", "丙关上门。")
        error = "M4_CURRENT_FACT_CHAPTER_UNKNOWN"
    else:
        fact = _fact_for_chapter("f001", "c01", TEXT, QUOTE)
        fact["chapter_revision_ref"]["revision_no"] = 0
        fact["anchor_ref"]["revision_no"] = 0
        error = "M4_CURRENT_FACTS_INVALID"
    workspace.commit(
        f"op-current-fact-{fault}",
        {
            "facts": [fact],
            "chapter_index": [_revision_ref_for("c01", TEXT)],
        },
        {"facts": 0, "chapter_index": 0},
    )
    before = _inventory(runtime_root)

    with pytest.raises(fact_workspace.FactWorkspaceError, match=error):
        fact_workspace.read_current_snapshot(workspace)

    assert _inventory(runtime_root) == before


@pytest.mark.parametrize(
    ("changed_key", "change_after_read"),
    [
        ("facts", 2),
        ("chapter_index", 2),
        ("facts", 4),
        ("chapter_index", 4),
    ],
)
def test_source_change_during_current_view_read_rejects_without_overwriting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_key: str,
    change_after_read: int,
) -> None:
    _, _, workspace = _open_workspace(tmp_path)
    fact = _fact_for_chapter("f001", "c01", TEXT, QUOTE)
    _commit_fact_view_sources(
        workspace,
        [fact],
        [_revision_ref_for("c01", TEXT)],
    )
    real_read = workspace.read
    read_count = 0

    def racing_read(logical_key: str):
        nonlocal read_count
        value = real_read(logical_key)
        read_count += 1
        if read_count == change_after_read:
            changed_state = real_read(changed_key)
            workspace.commit(
                f"op-current-fact-view-race-{changed_key}-{change_after_read}",
                {changed_key: changed_state["payload"]},
                {changed_key: changed_state["version"]},
            )
        return value

    monkeypatch.setattr(workspace, "read", racing_read)

    with pytest.raises(
        fact_workspace.FactWorkspaceSourceChangedError,
        match="M4_CURRENT_FACT_VIEW_SOURCE_CHANGED_DURING_READ",
    ):
        fact_workspace.read_current_snapshot(workspace)

    assert real_read(changed_key)["version"] == 2
    unchanged_key = "chapter_index" if changed_key == "facts" else "facts"
    assert real_read(unchanged_key)["version"] == 1


def test_current_view_restart_is_byte_stable_and_workspace_binding_is_enforced(
    tmp_path: Path,
) -> None:
    runtime_root, router, alice = _open_workspace(tmp_path)
    facts = [
        _fact_for_chapter("f001", "c01", TEXT, QUOTE),
        _fact_for_chapter("f002", "c02", SECOND_TEXT, "丁点灯。"),
    ]
    refs = [
        _revision_ref_for("c01", TEXT),
        _revision_ref_for("c02", SECOND_TEXT),
    ]
    _commit_fact_view_sources(alice, facts, refs)
    current = fact_workspace.read_current_snapshot(alice)
    restarted = _subprocess_read_current(runtime_root, alice.project_id)
    bob = router.create_project("auth:other-author", "同名项目")
    bob.commit(
        "op-bob-empty-index",
        {"chapter_index": [_revision_ref_for("c01", TEXT)]},
        {"chapter_index": 0},
    )
    caller_path = tmp_path / "caller-current-view"

    assert _canonical_bytes(restarted) == _canonical_bytes(current)
    assert fact_workspace.read_current_snapshot(bob)["facts"] == []
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("auth:other-author", alice.project_id)
    with pytest.raises(
        fact_workspace.FactWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        fact_workspace.read_current_snapshot(caller_path)  # type: ignore[arg-type]
    assert not caller_path.exists()
