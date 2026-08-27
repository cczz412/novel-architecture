from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        chapter_workspace,
        extract_tool,
        extract_workspace,
        fact_workspace,
        factstore,
        review_workspace,
        segment_workspace,
    )
    from mvp.workspace import (
        InjectedWorkspaceCrash,
        OperationConflictError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


TEXT = "甲拿起钥匙。乙离开。"
SEGMENT_OPTIONS = {
    "seg_min_chars": 80,
    "seg_max_chars": 120,
    "halo_chars": 20,
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_ref() -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": 1,
        "revision_text_sha256": _sha256(TEXT),
    }


def _setup(tmp_path: Path):
    router = WorkspaceRouter(tmp_path / "runtime")
    workspace = router.create_project("auth:s2-author", "S2 合成项目")
    chapter = {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": "c01",
        "title": "第一章",
        "kind": "draft",
        "text": TEXT,
        "added_at": "2026-08-28 09:00:00",
        "chapter_revision_ref": _revision_ref(),
    }
    chapter_workspace.persist_c1_current_views(
        workspace,
        "op-s2-c1",
        [chapter],
        [_revision_ref()],
        {"chapters": 0, "chapter_index": 0},
    )
    segment_workspace.persist_current_segments(
        workspace,
        "op-s2-c2",
        SEGMENT_OPTIONS["seg_min_chars"],
        SEGMENT_OPTIONS["seg_max_chars"],
        SEGMENT_OPTIONS["halo_chars"],
        0,
    )
    item = segment_workspace.read_current_segments(workspace)["items"][0]
    responses = {
        extract_tool.item_key(item): {
            "data": {
                "facts": [
                    {"text": "甲拿起钥匙。", "quote": "甲拿起钥匙。"},
                    {"text": "乙离开。", "quote": "乙离开。"},
                ]
            },
            "usage": {},
            "model": "FROZEN_OFFLINE_RESPONSE",
        }
    }
    extract_workspace.persist_current_fact_candidates(
        workspace,
        "op-s2-c3",
        responses,
        0,
    )
    ref = fact_workspace.current_fact_candidates_ref(workspace)
    fact_workspace.materialize_current_extracted_snapshot(
        workspace,
        operation_id="op-s2-c4",
        source="M4_CURRENT_WORKSPACE",
        added_at="2026-08-28 09:01:00",
    )
    return router, workspace, ref


def _action(fact: dict, decision: str, operation_id: str) -> dict:
    return {
        "action": factstore.build_review_action(
            fact,
            decision=decision,
            operation_id=operation_id,
        ),
        "chapter_revision_ref": copy.deepcopy(fact["chapter_revision_ref"]),
        "decided_at": "2026-08-28 09:02:00",
    }


def _call(workspace, ref, actions, operation_id="op-s2-author-review"):
    facts = workspace.read("facts")
    return review_workspace.apply_author_review_actions(
        workspace,
        operation_id=operation_id,
        actor="author",
        review_actions=actions,
        fact_candidates_ref=ref,
        expected_facts_version=facts["version"],
        expected_facts_sha256=facts["sha256"],
    )


def _before(workspace) -> tuple[dict | None, dict | None]:
    return copy.deepcopy(workspace.read("facts")), copy.deepcopy(
        workspace.read("fact_review_runs")
    )


def _assert_unchanged(workspace, before) -> None:
    assert workspace.read("facts") == before[0]
    assert workspace.read("fact_review_runs") == before[1]


def test_single_confirm_writes_separate_authorization_and_save_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, workspace, ref = _setup(tmp_path)
    fact = workspace.read("facts")["payload"][0]

    def forbidden(*_args, **_kwargs):
        raise AssertionError("S2 不得调用 legacy review_fact")

    reconciliation_before = copy.deepcopy(workspace.read("reconciliation"))
    monkeypatch.setattr(factstore, "review_fact", forbidden)
    result = _call(workspace, ref, [_action(fact, "confirm", "op-confirm-f001")])
    records = review_workspace.read_author_review_records(workspace)

    assert result["facts_version"] == 2
    assert workspace.read("facts")["payload"][0]["status"] == "confirmed"
    assert len(records["authorizations"]) == len(records["saves"]) == 1
    authorization = records["authorizations"][0]
    save = records["saves"][0]
    assert authorization["actor"] == "author"
    assert authorization["fact_candidates_ref"] == ref
    assert authorization["actions"][0]["operation_id"] == "op-confirm-f001"
    assert authorization["actions"][0]["kind"] == "confirm"
    assert authorization["actions"][0]["fact_ref"] == "f001"
    assert authorization["actions"][0]["decided_at"] == "2026-08-28 09:02:00"
    assert authorization["actions"][0]["chapter_revision_ref"] == _revision_ref()
    assert authorization["actions"][0]["action"] == _action(
        fact, "confirm", "op-confirm-f001"
    )["action"]
    assert len(authorization["actions"][0]["action_sha256"]) == 64
    assert authorization["chapter_batch_evidence"] == {
        "scope": "CHAPTER_BATCH_ONLY",
        "materialization_operation_id": "op-s2-c4",
        "target_chapter_ids": ["c01"],
        "fact_candidates": {
            "version": ref["record_version"],
            "sha256": ref["record_hash"],
        },
    }
    assert "c3_fact_ref" not in authorization["chapter_batch_evidence"]
    assert authorization["lineage_anchor"] == {
        "kind": "M4_FACTS_SNAPSHOT",
        "operation_id": "op-s2-c4",
        "facts_identity": authorization["facts_before"],
    }
    assert save["facts_before"] == authorization["facts_before"]
    assert save["facts_after"] == {
        "version": 2,
        "sha256": result["facts_sha256"],
    }
    assert save["facts_after_payload"] == workspace.read("facts")["payload"]
    assert workspace.read("reconciliation") == reconciliation_before


def test_explicit_batch_is_one_facts_version_and_preserves_item_results(
    tmp_path: Path,
) -> None:
    _, workspace, ref = _setup(tmp_path)
    facts = workspace.read("facts")["payload"]
    result = _call(
        workspace,
        ref,
        [
            _action(facts[0], "confirm", "op-confirm-f001"),
            _action(facts[1], "reject", "op-reject-f002"),
        ],
        "op-s2-explicit-batch",
    )

    assert result["facts_version"] == 2
    assert [row["kind"] for row in result["results"]] == ["confirm", "reject"]
    assert [fact["status"] for fact in workspace.read("facts")["payload"]] == [
        "confirmed",
        "rejected",
    ]


def test_cross_chapter_batch_remains_rejected(tmp_path: Path) -> None:
    _, workspace, ref = _setup(tmp_path)
    facts = workspace.read("facts")["payload"]
    actions = [
        _action(facts[0], "confirm", "op-cross-f001"),
        _action(facts[1], "reject", "op-cross-f002"),
    ]
    actions[1]["chapter_revision_ref"] = {
        **actions[1]["chapter_revision_ref"],
        "chapter_id": "c02",
    }
    before = _before(workspace)

    with pytest.raises(
        review_workspace.ReviewWorkspaceError,
        match="REVIEW_BATCH_CROSS_REVISION_SCOPE",
    ):
        _call(workspace, ref, actions, "op-s2-cross-chapter")

    _assert_unchanged(workspace, before)


def test_confirmed_to_reject_is_audited_as_revoke(tmp_path: Path) -> None:
    _, workspace, ref = _setup(tmp_path)
    fact = workspace.read("facts")["payload"][0]
    _call(
        workspace,
        ref,
        [_action(fact, "confirm", "op-confirm-before-revoke")],
        "op-s2-confirm-before-revoke",
    )
    confirmed = workspace.read("facts")["payload"][0]
    result = _call(
        workspace,
        ref,
        [_action(confirmed, "reject", "op-revoke-f001")],
        "op-s2-revoke",
    )

    assert result["results"][0]["kind"] == "revoke"
    records = review_workspace.read_author_review_records(workspace)
    assert records["authorizations"][1]["actions"][0]["kind"] == "revoke"
    assert records["saves"][1]["results"][0]["kind"] == "revoke"


@pytest.mark.parametrize(
    ("bad_actions", "actor", "reason"),
    [
        ({"scope": "全部通过"}, "author", "REVIEW_WORKSPACE_BATCH_ITEMS_REQUIRED"),
        ("全部通过", "author", "REVIEW_WORKSPACE_BATCH_ITEMS_REQUIRED"),
        ([], "author", "REVIEW_WORKSPACE_BATCH_ITEMS_REQUIRED"),
        (None, "assistant", "AUTHOR_REVIEW_ACTOR_MUST_BE_AUTHOR"),
    ],
)
def test_unscoped_or_non_author_request_is_zero_write(
    tmp_path: Path,
    bad_actions,
    actor: str,
    reason: str,
) -> None:
    _, workspace, ref = _setup(tmp_path)
    before = _before(workspace)
    facts = workspace.read("facts")

    with pytest.raises((review_workspace.ReviewWorkspaceError, factstore.FactstoreError), match=reason):
        review_workspace.apply_author_review_actions(
            workspace,
            operation_id="op-s2-bad-scope",
            actor=actor,
            review_actions=bad_actions,
            fact_candidates_ref=ref,
            expected_facts_version=facts["version"],
            expected_facts_sha256=facts["sha256"],
        )

    _assert_unchanged(workspace, before)


def test_duplicate_target_is_zero_write(tmp_path: Path) -> None:
    _, workspace, ref = _setup(tmp_path)
    fact = workspace.read("facts")["payload"][0]
    actions = [
        _action(fact, "confirm", "op-dup-a"),
        _action(fact, "reject", "op-dup-b"),
    ]
    before = _before(workspace)

    with pytest.raises(
        review_workspace.ReviewWorkspaceError,
        match="REVIEW_BATCH_FACT_REF_DUPLICATE",
    ):
        _call(workspace, ref, actions, "op-s2-duplicate")

    _assert_unchanged(workspace, before)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda ref: ref.update(record_hash="0" * 64),
        lambda ref: ref.update(record_version=ref["record_version"] + 1),
        lambda ref: ref.update(access="WRITE"),
        lambda ref: ref.pop("source_module"),
    ],
    ids=["hash", "version", "write-access", "missing-field"],
)
def test_bad_s1_ref_is_zero_write(tmp_path: Path, mutate) -> None:
    _, workspace, ref = _setup(tmp_path)
    bad = copy.deepcopy(ref)
    mutate(bad)
    fact = workspace.read("facts")["payload"][0]
    before = _before(workspace)

    with pytest.raises(fact_workspace.FactWorkspaceError, match="M4_FACT_CANDIDATES_REF_REJECTED"):
        _call(workspace, bad, [_action(fact, "confirm", "op-bad-ref")])

    _assert_unchanged(workspace, before)


def test_stale_c3_source_is_zero_write(tmp_path: Path) -> None:
    _, workspace, ref = _setup(tmp_path)
    segments = workspace.read("segments")
    workspace.commit(
        "op-source-forward",
        {"segments": segments["payload"]},
        {"segments": segments["version"]},
    )
    fact = workspace.read("facts")["payload"][0]
    before = _before(workspace)

    with pytest.raises(fact_workspace.FactWorkspaceError, match="FACT_CANDIDATES_STALE"):
        _call(workspace, ref, [_action(fact, "confirm", "op-stale-source")])

    _assert_unchanged(workspace, before)


def test_missing_complete_receipt_is_zero_write(tmp_path: Path) -> None:
    _, workspace, ref = _setup(tmp_path)
    runs = workspace.read("fact_candidate_runs")
    broken = copy.deepcopy(runs["payload"])
    broken["runs"] = []
    workspace.commit(
        "op-remove-complete-receipt",
        {"fact_candidate_runs": broken},
        {"fact_candidate_runs": runs["version"]},
    )
    fact = workspace.read("facts")["payload"][0]
    before = _before(workspace)

    with pytest.raises(fact_workspace.FactWorkspaceError, match="COMPLETE_RECEIPT_MISSING"):
        _call(workspace, ref, [_action(fact, "confirm", "op-missing-complete")])

    _assert_unchanged(workspace, before)


def test_uncommitted_s1_ref_is_zero_write(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "empty").create_project(
        "auth:s2-author", "空项目"
    )
    synthetic = {
        "record_type": "C3_FACT_CANDIDATE_SNAPSHOT",
        "record_id": "fact_candidates",
        "record_version": 1,
        "record_hash": "a" * 64,
        "access": "READ_ONLY",
        "source_module": "novel-mvp/M3",
    }
    action = {
        "action": {
            "contract": "FACT_REVIEW_ACTION",
            "version": "v1",
            "operation_id": "op-uncommitted-f001",
            "actor": "author",
            "fact_ref": "f001",
            "expected_status": "extracted",
            "expected_fact_sha256": "b" * 64,
            "decision": "confirm",
            "replacement_text": None,
            "note": "",
        },
        "chapter_revision_ref": _revision_ref(),
        "decided_at": "2026-08-28 09:02:00",
    }

    with pytest.raises(fact_workspace.FactWorkspaceError, match="FACT_CANDIDATES_STATE_MISSING"):
        review_workspace.apply_author_review_actions(
            workspace,
            operation_id="op-uncommitted",
            actor="author",
            review_actions=[action],
            fact_candidates_ref=synthetic,
            expected_facts_version=1,
            expected_facts_sha256="a" * 64,
        )

    assert workspace.read("facts") is None
    assert workspace.read("fact_review_runs") is None


def test_exact_replay_adds_no_version_or_records(tmp_path: Path) -> None:
    _, workspace, ref = _setup(tmp_path)
    fact = workspace.read("facts")["payload"][0]
    actions = [_action(fact, "confirm", "op-replay-f001")]
    facts_before = workspace.read("facts")
    kwargs = {
        "operation_id": "op-s2-replay",
        "actor": "author",
        "review_actions": actions,
        "fact_candidates_ref": ref,
        "expected_facts_version": facts_before["version"],
        "expected_facts_sha256": facts_before["sha256"],
    }
    first = review_workspace.apply_author_review_actions(workspace, **kwargs)
    replay = review_workspace.apply_author_review_actions(workspace, **kwargs)
    records = review_workspace.read_author_review_records(workspace)

    assert replay["replayed"] is True
    assert replay["facts_version"] == first["facts_version"]
    assert workspace.read("facts")["version"] == 2
    assert records["version"] == 1
    assert len(records["authorizations"]) == len(records["saves"]) == 1


@pytest.mark.parametrize("invalidate", ["segments", "complete"])
def test_exact_replay_rechecks_s1_and_rejects_invalid_current_gate(
    tmp_path: Path,
    invalidate: str,
) -> None:
    _, workspace, ref = _setup(tmp_path)
    fact = workspace.read("facts")["payload"][0]
    facts_before = workspace.read("facts")
    kwargs = {
        "operation_id": "op-s2-replay-current-gate",
        "actor": "author",
        "review_actions": [_action(fact, "confirm", "op-replay-current-f001")],
        "fact_candidates_ref": ref,
        "expected_facts_version": facts_before["version"],
        "expected_facts_sha256": facts_before["sha256"],
    }
    review_workspace.apply_author_review_actions(workspace, **kwargs)
    if invalidate == "segments":
        state = workspace.read("segments")
        workspace.commit(
            "op-replay-segments-forward",
            {"segments": state["payload"]},
            {"segments": state["version"]},
        )
    else:
        state = workspace.read("fact_candidate_runs")
        payload = copy.deepcopy(state["payload"])
        payload["runs"] = []
        workspace.commit(
            "op-replay-complete-invalid",
            {"fact_candidate_runs": payload},
            {"fact_candidate_runs": state["version"]},
        )
    before_replay = _before(workspace)

    with pytest.raises(
        fact_workspace.FactWorkspaceError,
        match=(
            "FACT_CANDIDATES_STALE"
            if invalidate == "segments"
            else "COMPLETE_RECEIPT_MISSING"
        ),
    ):
        review_workspace.apply_author_review_actions(workspace, **kwargs)

    _assert_unchanged(workspace, before_replay)


def test_exact_replay_rejects_facts_written_outside_verified_lineage(
    tmp_path: Path,
) -> None:
    _, workspace, ref = _setup(tmp_path)
    fact = workspace.read("facts")["payload"][0]
    facts_before = workspace.read("facts")
    kwargs = {
        "operation_id": "op-s2-replay-lineage",
        "actor": "author",
        "review_actions": [_action(fact, "confirm", "op-replay-lineage-f001")],
        "fact_candidates_ref": ref,
        "expected_facts_version": facts_before["version"],
        "expected_facts_sha256": facts_before["sha256"],
    }
    first = review_workspace.apply_author_review_actions(workspace, **kwargs)
    current = workspace.read("facts")
    bypassed = copy.deepcopy(current["payload"])
    bypassed[0]["note"] = "旁路 v3"
    fact_workspace.save_snapshot(
        workspace,
        operation_id="op-replay-lineage-bypass-v3",
        snapshot=bypassed,
        expected_version=current["version"],
    )
    before_replay = _before(workspace)

    with pytest.raises(
        review_workspace.ReviewWorkspaceError,
        match="AUTHOR_REVIEW_FACTS_LINEAGE_UNTRUSTED",
    ):
        review_workspace.apply_author_review_actions(workspace, **kwargs)

    assert first["facts_version"] == 2
    assert workspace.read("facts")["version"] == 3
    _assert_unchanged(workspace, before_replay)


def test_older_receipt_replays_after_a_later_verified_s2_save(
    tmp_path: Path,
) -> None:
    _, workspace, ref = _setup(tmp_path)
    facts = workspace.read("facts")["payload"]
    initial = workspace.read("facts")
    first_kwargs = {
        "operation_id": "op-s2-chain-first",
        "actor": "author",
        "review_actions": [_action(facts[0], "confirm", "op-chain-first-f001")],
        "fact_candidates_ref": ref,
        "expected_facts_version": initial["version"],
        "expected_facts_sha256": initial["sha256"],
    }
    first = review_workspace.apply_author_review_actions(
        workspace, **first_kwargs
    )
    second_fact = workspace.read("facts")["payload"][1]
    _call(
        workspace,
        ref,
        [_action(second_fact, "reject", "op-chain-second-f002")],
        "op-s2-chain-second",
    )
    before_replay = _before(workspace)

    replay = review_workspace.apply_author_review_actions(
        workspace, **first_kwargs
    )

    assert replay["replayed"] is True
    assert replay["facts_version"] == first["facts_version"] == 2
    assert workspace.read("facts")["version"] == 3
    _assert_unchanged(workspace, before_replay)


@pytest.mark.parametrize("change", ["action", "ref", "target"])
def test_same_operation_changed_request_is_rejected_zero_write(
    tmp_path: Path,
    change: str,
) -> None:
    _, workspace, ref = _setup(tmp_path)
    facts = workspace.read("facts")["payload"]
    fact = facts[0]
    original = [_action(fact, "confirm", "op-conflict-f001")]
    facts_before = workspace.read("facts")
    review_workspace.apply_author_review_actions(
        workspace,
        operation_id="op-s2-conflict",
        actor="author",
        review_actions=original,
        fact_candidates_ref=ref,
        expected_facts_version=facts_before["version"],
        expected_facts_sha256=facts_before["sha256"],
    )
    before = _before(workspace)
    changed = copy.deepcopy(original)
    changed_ref = copy.deepcopy(ref)
    if change == "action":
        changed[0]["action"]["note"] = "changed"
    elif change == "ref":
        changed_ref["record_hash"] = "0" * 64
    else:
        changed = [_action(facts[1], "confirm", "op-conflict-f002")]

    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        review_workspace.apply_author_review_actions(
            workspace,
            operation_id="op-s2-conflict",
            actor="author",
            review_actions=changed,
            fact_candidates_ref=changed_ref,
            expected_facts_version=facts_before["version"],
            expected_facts_sha256=facts_before["sha256"],
        )

    _assert_unchanged(workspace, before)


@pytest.mark.parametrize(
    "logical_key",
    [
        "fact_candidates",
        "fact_candidate_runs",
        "fact_materialization_runs",
        "segments",
        "chapter_index",
    ],
)
def test_guard_rejects_source_change_between_read_and_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    logical_key: str,
) -> None:
    _, workspace, ref = _setup(tmp_path)
    fact = workspace.read("facts")["payload"][0]
    before = _before(workspace)
    real_commit_guarded = workspace.commit_guarded

    def drift_then_commit(*args, **kwargs):
        state = workspace.read(logical_key)
        workspace.commit(
            f"op-s2-guard-drift-{logical_key}",
            {logical_key: state["payload"]},
            {logical_key: state["version"]},
        )
        return real_commit_guarded(*args, **kwargs)

    monkeypatch.setattr(workspace, "commit_guarded", drift_then_commit)
    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        _call(
            workspace,
            ref,
            [_action(fact, "confirm", "op-guard-f001")],
            "op-s2-guard",
        )

    _assert_unchanged(workspace, before)


@pytest.mark.parametrize("bypass", ["replace", "insert"])
def test_public_save_snapshot_breaks_whole_facts_lineage(
    tmp_path: Path,
    bypass: str,
) -> None:
    _, workspace, ref = _setup(tmp_path)
    current = workspace.read("facts")
    bypassed = copy.deepcopy(current["payload"])
    if bypass == "replace":
        bypassed[0]["status"] = "confirmed"
        bypassed[0]["decided_at"] = "2026-08-28 09:03:00"
    else:
        inserted = copy.deepcopy(bypassed[-1])
        inserted["id"] = "f003"
        bypassed.append(inserted)
    fact_workspace.save_snapshot(
        workspace,
        operation_id=f"op-public-bypass-{bypass}",
        snapshot=bypassed,
        expected_version=current["version"],
    )
    fact = workspace.read("facts")["payload"][0]
    before = _before(workspace)

    with pytest.raises(
        review_workspace.ReviewWorkspaceError,
        match="AUTHOR_REVIEW_FACTS_LINEAGE_UNTRUSTED",
    ):
        _call(
            workspace,
            ref,
            [_action(fact, "reject", f"op-bypass-{bypass}-f001")],
            f"op-s2-bypass-{bypass}",
        )

    _assert_unchanged(workspace, before)


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda payload: payload["authorizations"][0]["facts_before"].update(
            version=0
        ),
        lambda payload: payload["saves"][0]["facts_after"].update(
            sha256="0" * 64
        ),
        lambda payload: payload["saves"][0]["results"][0].update(
            after_fact_sha256="0" * 64
        ),
        lambda payload: payload["saves"][0]["facts_after_payload"][0].update(
            text="内容被旁路改动"
        ),
        lambda payload: payload["saves"][0].update(
            authorization_sha256="0" * 64
        ),
        lambda payload: payload["authorizations"][0]["actions"][0].update(
            action_sha256="0" * 64
        ),
        lambda payload: payload["authorizations"][0]["lineage_anchor"].update(
            operation_id="op-disconnected"
        ),
    ],
    ids=[
        "version",
        "facts-after-valid-looking-hash",
        "result-valid-looking-hash",
        "payload-content",
        "authorization-hash",
        "action-hash",
        "lineage",
    ],
)
def test_corrupt_review_ledger_is_rejected_with_stable_error(
    tmp_path: Path,
    corrupt,
) -> None:
    _, workspace, ref = _setup(tmp_path)
    fact = workspace.read("facts")["payload"][0]
    _call(workspace, ref, [_action(fact, "confirm", "op-ledger-f001")])
    state = workspace.read("fact_review_runs")
    payload = copy.deepcopy(state["payload"])
    corrupt(payload)
    workspace.commit(
        "op-corrupt-s2-ledger",
        {"fact_review_runs": payload},
        {"fact_review_runs": state["version"]},
    )

    with pytest.raises(
        review_workspace.ReviewWorkspaceError,
        match="^AUTHOR_REVIEW_LEDGER_INVALID$",
    ):
        review_workspace.read_author_review_records(workspace)


def test_injected_failure_before_pointer_swap_keeps_facts_and_records_atomic(
    tmp_path: Path,
) -> None:
    router, workspace, ref = _setup(tmp_path)
    fact = workspace.read("facts")["payload"][0]
    before = _before(workspace)

    def fail_after_prepare(point: str) -> None:
        if point == "after_prepare":
            raise InjectedWorkspaceCrash(point)

    router._set_failure_hook_for_testing(fail_after_prepare)
    with pytest.raises(InjectedWorkspaceCrash, match="after_prepare"):
        _call(
            workspace,
            ref,
            [_action(fact, "confirm", "op-atomic-f001")],
            "op-s2-atomic",
        )
    router._set_failure_hook_for_testing(None)
    router._backend.recover(workspace.author_id, workspace.project_id)

    _assert_unchanged(workspace, before)
