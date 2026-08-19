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
        fact_tool,
        fact_workspace,
        factstore,
        review_workspace,
    )
    from mvp.workspace import (
        ProjectNotFoundError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


PRINCIPAL = "auth:review-author"
TEXT = "甲拿起钥匙。乙离开。"
QUOTE = "甲拿起钥匙。"
DECIDED_AT = "2026-08-19 16:00:00"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _revision_ref(*, revision_no: int = 1) -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": revision_no,
        "revision_text_sha256": _sha256(TEXT),
    }


def _snapshot() -> list[dict]:
    revision_ref = _revision_ref()
    return fact_tool.execute(
        {
            "chapter": {
                "contract": "C1_CHAPTER_DOC",
                "version": "v1",
                "id": "c01",
                "title": "第一章",
                "kind": "draft",
                "text": TEXT,
                "added_at": "2026-08-19 15:00:00",
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
                },
                {
                    "contract": "C3_FACT_CANDIDATE",
                    "version": "v1",
                    "chapter_revision_ref": revision_ref,
                    "text": "乙离开。",
                    "quote": "乙离开。",
                    "seg": 1,
                },
            ],
            "source": "M5_WORKSPACE_FIXTURE",
            "added_at": "2026-08-19 15:01:00",
        }
    )["facts"]


def _setup(tmp_path: Path):
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project(PRINCIPAL, "M5 合成项目")
    snapshot = _snapshot()
    fact_workspace.save_snapshot(
        workspace,
        operation_id="op-seed-facts",
        snapshot=snapshot,
        expected_version=0,
    )
    return runtime_root, router, workspace, snapshot


def _explicit_action(
    fact: dict,
    decision: str,
    operation_id: str,
    *,
    revision_ref: dict | None = None,
) -> dict:
    return {
        "action": factstore.build_review_action(
            fact,
            decision=decision,
            operation_id=operation_id,
        ),
        "chapter_revision_ref": copy.deepcopy(
            fact["chapter_revision_ref"] if revision_ref is None else revision_ref
        ),
        "decided_at": DECIDED_AT,
    }


def _ask(facts: list[dict]) -> dict:
    return ask_tool.execute(
        {
            "query": "钥匙",
            "facts": facts,
            "current_revision_refs": [_revision_ref()],
        }
    )


def _batch_actions(snapshot: list[dict]) -> list[dict]:
    return [
        _explicit_action(snapshot[0], "confirm", "op-batch-confirm-f001"),
        _explicit_action(snapshot[1], "reject", "op-batch-reject-f002"),
    ]


def _subprocess_read(runtime_root: Path, project_id: str) -> dict:
    script = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from mvp.workspace import WorkspaceRouter
current = WorkspaceRouter(sys.argv[2]).open_project(sys.argv[3], sys.argv[4]).read(\"facts\")
print(json.dumps(current, ensure_ascii=False, sort_keys=True, separators=(\",\", \":\")))
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


def test_confirm_reads_current_commits_once_and_m6_returns_evidence(
    tmp_path: Path,
) -> None:
    _, _, workspace, snapshot = _setup(tmp_path)
    before = copy.deepcopy(snapshot[0])
    action = _explicit_action(before, "confirm", "op-workspace-confirm")

    result = review_workspace.apply_review(
        workspace,
        operation_id="op-workspace-confirm",
        review_action=action,
        expected_facts_version=1,
    )

    assert result["facts_version"] == 2 and result["replayed"] is False
    assert result["facts"][0]["status"] == "confirmed"
    assert [row["fact_id"] for row in _ask(result["facts"])["matches"]] == [
        "f001"
    ]
    for key in ("quote", "source", "anchor_ref", "chapter_revision_ref"):
        assert result["facts"][0][key] == before[key]
    assert workspace.read("facts")["payload"] == result["facts"]


def test_reject_is_saved_but_remains_excluded_from_m6(tmp_path: Path) -> None:
    _, _, workspace, snapshot = _setup(tmp_path)
    action = _explicit_action(snapshot[0], "reject", "op-workspace-reject")

    result = review_workspace.apply_review(
        workspace,
        operation_id="op-workspace-reject",
        review_action=action,
        expected_facts_version=1,
    )

    assert result["facts"][0]["status"] == "rejected"
    query = _ask(result["facts"])
    assert query["matches"] == []
    assert query["excluded_counts"]["rejected"] == 1


def test_same_operation_and_request_replays_without_second_version(tmp_path: Path) -> None:
    _, _, workspace, snapshot = _setup(tmp_path)
    action = _explicit_action(snapshot[0], "confirm", "op-workspace-repeat")

    first = review_workspace.apply_review(
        workspace,
        operation_id="op-workspace-repeat",
        review_action=action,
        expected_facts_version=1,
    )
    replay = review_workspace.apply_review(
        workspace,
        operation_id="op-workspace-repeat",
        review_action=action,
        expected_facts_version=1,
    )

    assert first["facts_version"] == replay["facts_version"] == 2
    assert replay["replayed"] is True
    assert workspace.read("facts")["version"] == 2


def test_same_operation_different_action_is_rejected_without_visible_write(
    tmp_path: Path,
) -> None:
    _, _, workspace, snapshot = _setup(tmp_path)
    operation_id = "op-workspace-conflict"
    confirm = _explicit_action(snapshot[0], "confirm", operation_id)
    review_workspace.apply_review(
        workspace,
        operation_id=operation_id,
        review_action=confirm,
        expected_facts_version=1,
    )
    before = copy.deepcopy(workspace.read("facts"))
    reject = _explicit_action(snapshot[0], "reject", operation_id)

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        review_workspace.apply_review(
            workspace,
            operation_id=operation_id,
            review_action=reject,
            expected_facts_version=1,
        )
    assert workspace.read("facts") == before


def test_version_fact_and_revision_staleness_have_zero_visible_write(
    tmp_path: Path,
) -> None:
    _, _, workspace, snapshot = _setup(tmp_path)
    before = copy.deepcopy(workspace.read("facts"))
    action = _explicit_action(snapshot[0], "confirm", "op-stale-fact")
    action["action"]["expected_status"] = "confirmed"
    with pytest.raises(factstore.FactstoreError, match="STALE_FACT_REVISION"):
        review_workspace.apply_review(
            workspace,
            operation_id="op-stale-fact",
            review_action=action,
            expected_facts_version=1,
        )

    wrong_ref = _explicit_action(
        snapshot[0],
        "confirm",
        "op-stale-ref",
        revision_ref=_revision_ref(revision_no=2),
    )
    with pytest.raises(
        review_workspace.ReviewWorkspaceError,
        match="STALE_CHAPTER_REVISION_REF",
    ):
        review_workspace.apply_review(
            workspace,
            operation_id="op-stale-ref",
            review_action=wrong_ref,
            expected_facts_version=1,
        )

    new_action = _explicit_action(snapshot[0], "confirm", "op-stale-version")
    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        review_workspace.apply_review(
            workspace,
            operation_id="op-stale-version",
            review_action=new_action,
            expected_facts_version=2,
        )
    assert workspace.read("facts") == before


def test_empty_or_bad_snapshot_is_rejected_without_adapter_write(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(PRINCIPAL, "空项目")
    workspace.commit("op-empty-seed", {"facts": []}, {"facts": 0})
    placeholder = _snapshot()[0]
    action = _explicit_action(placeholder, "confirm", "op-empty-review")
    with pytest.raises(
        review_workspace.ReviewWorkspaceError,
        match="FACTS_SNAPSHOT_EMPTY",
    ):
        review_workspace.apply_review(
            workspace,
            operation_id="op-empty-review",
            review_action=action,
            expected_facts_version=1,
        )
    assert workspace.read("facts")["version"] == 1

    bad = _snapshot()
    bad[0]["anchor_ref"]["slice_sha256"] = "0" * 64
    bad_workspace = WorkspaceRouter(tmp_path / "bad-runtime").create_project(
        PRINCIPAL, "坏批次"
    )
    bad_workspace.commit("op-bad-seed", {"facts": bad}, {"facts": 0})
    bad_action = _explicit_action(bad[0], "confirm", "op-bad-review")
    with pytest.raises(
        factstore.FactstoreError,
        match="C4_ANCHOR_QUOTE_SHA_MISMATCH",
    ):
        review_workspace.apply_review(
            bad_workspace,
            operation_id="op-bad-review",
            review_action=bad_action,
            expected_facts_version=1,
        )
    assert bad_workspace.read("facts")["version"] == 1


def test_new_process_reopens_and_reads_same_committed_result(tmp_path: Path) -> None:
    runtime_root, _, workspace, snapshot = _setup(tmp_path)
    action = _explicit_action(snapshot[0], "confirm", "op-restart-review")
    result = review_workspace.apply_review(
        workspace,
        operation_id="op-restart-review",
        review_action=action,
        expected_facts_version=1,
    )

    reopened = _subprocess_read(runtime_root, workspace.project_id)
    assert reopened["payload"] == result["facts"]
    assert reopened["version"] == 2


def test_cross_author_guess_and_path_handle_are_rejected(tmp_path: Path) -> None:
    _, router, alice, snapshot = _setup(tmp_path)
    action = _explicit_action(snapshot[0], "confirm", "op-auth-boundary")
    bob = router.create_project("auth:other", "同名项目")

    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("auth:other", alice.project_id)
    assert bob.read("facts") is None

    caller_path = tmp_path / "caller-path"
    with pytest.raises(
        review_workspace.ReviewWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        review_workspace.apply_review(  # type: ignore[arg-type]
            caller_path,
            operation_id="op-path-reject",
            review_action=action,
            expected_facts_version=1,
        )
    assert not caller_path.exists()


def test_batch_confirm_reject_commits_once_preserves_order_and_adds_one_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, workspace, snapshot = _setup(tmp_path)
    current = workspace.read("facts")
    actions = _batch_actions(snapshot)
    commit_calls: list[tuple] = []
    real_commit = workspace.commit

    def recording_commit(*args, **kwargs):
        commit_calls.append((args, kwargs))
        return real_commit(*args, **kwargs)

    monkeypatch.setattr(workspace, "commit", recording_commit)
    result = review_workspace.apply_review_batch(
        workspace,
        operation_id="op-workspace-batch-01",
        review_actions=actions,
        expected_facts_version=current["version"],
        expected_facts_sha256=current["sha256"],
    )

    assert len(commit_calls) == 1
    assert result["facts_version"] == 2
    assert [fact["status"] for fact in result["facts"]] == [
        "confirmed",
        "rejected",
    ]
    assert [receipt["operation_id"] for receipt in result["receipts"]] == [
        "op-batch-confirm-f001",
        "op-batch-reject-f002",
    ]
    assert [receipt["before_snapshot_version"] for receipt in result["receipts"]] == [
        1,
        2,
    ]
    assert result["input_count"] == result["applied_count"] == 2
    assert result["replayed"] is False
    assert workspace.read("facts")["version"] == 2


@pytest.mark.parametrize(
    ("bad_kind", "reason"),
    [
        ("fact-sha", "STALE_FACT_REVISION"),
        ("revision", "REVIEW_BATCH_CROSS_REVISION_SCOPE"),
    ],
)
def test_bad_second_action_keeps_first_action_out_of_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_kind: str,
    reason: str,
) -> None:
    _, _, workspace, snapshot = _setup(tmp_path)
    current = workspace.read("facts")
    before = copy.deepcopy(current)
    actions = _batch_actions(snapshot)
    if bad_kind == "fact-sha":
        actions[1]["action"]["expected_fact_sha256"] = "0" * 64
    else:
        actions[1]["chapter_revision_ref"]["revision_no"] = 2
    commit_calls = 0

    def forbidden_commit(*_args, **_kwargs):
        nonlocal commit_calls
        commit_calls += 1
        raise AssertionError("坏批次不得提交")

    monkeypatch.setattr(workspace, "commit", forbidden_commit)
    with pytest.raises(factstore.FactstoreError, match=reason):
        review_workspace.apply_review_batch(
            workspace,
            operation_id=f"op-bad-second-{bad_kind}",
            review_actions=actions,
            expected_facts_version=current["version"],
            expected_facts_sha256=current["sha256"],
        )

    assert commit_calls == 0
    assert workspace.read("facts") == before


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda actions: actions.clear(),
            "REVIEW_WORKSPACE_BATCH_ITEMS_REQUIRED",
        ),
        (
            lambda actions: actions.append(
                {
                    **copy.deepcopy(actions[0]),
                    "action": {
                        **copy.deepcopy(actions[0]["action"]),
                        "operation_id": "op-duplicate-fact-other-action",
                    },
                }
            ),
            "REVIEW_BATCH_FACT_REF_DUPLICATE",
        ),
        (
            lambda actions: actions[1]["action"].update(
                operation_id=actions[0]["action"]["operation_id"]
            ),
            "REVIEW_BATCH_OPERATION_ID_DUPLICATE",
        ),
        (
            lambda actions: actions[0].update(extra="forbidden"),
            "REVIEW_WORKSPACE_BATCH_ITEM_SHAPE_INVALID:0",
        ),
    ],
    ids=["empty", "duplicate-fact", "duplicate-action", "bad-shape"],
)
def test_batch_shape_errors_have_zero_workspace_write(
    tmp_path: Path,
    mutate,
    reason: str,
) -> None:
    _, _, workspace, snapshot = _setup(tmp_path)
    current = workspace.read("facts")
    before = copy.deepcopy(current)
    actions = _batch_actions(snapshot)
    mutate(actions)

    with pytest.raises(factstore.FactstoreError, match=reason):
        review_workspace.apply_review_batch(
            workspace,
            operation_id="op-batch-shape-error",
            review_actions=actions,
            expected_facts_version=current["version"],
            expected_facts_sha256=current["sha256"],
        )

    assert workspace.read("facts") == before


def test_exact_batch_replay_does_not_add_version_and_preserves_receipt_order(
    tmp_path: Path,
) -> None:
    _, _, workspace, snapshot = _setup(tmp_path)
    current = workspace.read("facts")
    actions = _batch_actions(snapshot)
    kwargs = {
        "operation_id": "op-workspace-batch-replay",
        "review_actions": actions,
        "expected_facts_version": current["version"],
        "expected_facts_sha256": current["sha256"],
    }

    first = review_workspace.apply_review_batch(workspace, **kwargs)
    replay = review_workspace.apply_review_batch(workspace, **kwargs)

    assert first["facts_version"] == replay["facts_version"] == 2
    assert first["applied_count"] == 2
    assert replay["applied_count"] == 0 and replay["replayed"] is True
    assert [receipt["fact_ref"] for receipt in replay["receipts"]] == [
        "f001",
        "f002",
    ]
    assert workspace.read("facts")["version"] == 2


def test_same_batch_operation_changed_content_is_rejected_without_write(
    tmp_path: Path,
) -> None:
    _, _, workspace, snapshot = _setup(tmp_path)
    current = workspace.read("facts")
    actions = _batch_actions(snapshot)
    review_workspace.apply_review_batch(
        workspace,
        operation_id="op-workspace-batch-conflict",
        review_actions=actions,
        expected_facts_version=current["version"],
        expected_facts_sha256=current["sha256"],
    )
    before = copy.deepcopy(workspace.read("facts"))
    changed = copy.deepcopy(actions)
    changed[1]["action"]["decision"] = "confirm"

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        review_workspace.apply_review_batch(
            workspace,
            operation_id="op-workspace-batch-conflict",
            review_actions=changed,
            expected_facts_version=current["version"],
            expected_facts_sha256=current["sha256"],
        )

    assert workspace.read("facts") == before


@pytest.mark.parametrize(
    ("expected_version_delta", "sha", "reason"),
    [
        (1, "current", "VERSION_CONFLICT"),
        (0, "wrong", "SHA_CONFLICT"),
    ],
)
def test_batch_expected_version_or_sha_conflict_has_zero_write(
    tmp_path: Path,
    expected_version_delta: int,
    sha: str,
    reason: str,
) -> None:
    _, _, workspace, snapshot = _setup(tmp_path)
    current = workspace.read("facts")
    before = copy.deepcopy(current)

    with pytest.raises(VersionConflictError, match=reason):
        review_workspace.apply_review_batch(
            workspace,
            operation_id=f"op-batch-{reason.lower()}",
            review_actions=_batch_actions(snapshot),
            expected_facts_version=current["version"] + expected_version_delta,
            expected_facts_sha256=(
                current["sha256"] if sha == "current" else "0" * 64
            ),
        )

    assert workspace.read("facts") == before


def test_batch_restart_reads_byte_equivalent_final_facts(tmp_path: Path) -> None:
    runtime_root, _, workspace, snapshot = _setup(tmp_path)
    current = workspace.read("facts")
    result = review_workspace.apply_review_batch(
        workspace,
        operation_id="op-batch-restart",
        review_actions=_batch_actions(snapshot),
        expected_facts_version=current["version"],
        expected_facts_sha256=current["sha256"],
    )

    reopened = _subprocess_read(runtime_root, workspace.project_id)

    assert _canonical_bytes(reopened["payload"]) == _canonical_bytes(result["facts"])
    assert reopened["version"] == result["facts_version"] == 2


def test_batch_cross_author_and_path_handle_are_rejected(tmp_path: Path) -> None:
    _, router, alice, snapshot = _setup(tmp_path)
    current = alice.read("facts")
    bob = router.create_project("auth:other-batch", "同名项目")
    actions = _batch_actions(snapshot)

    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("auth:other-batch", alice.project_id)
    with pytest.raises(review_workspace.ReviewWorkspaceError, match="FACTS_SNAPSHOT_MISSING"):
        review_workspace.apply_review_batch(
            bob,
            operation_id="op-bob-batch",
            review_actions=actions,
            expected_facts_version=current["version"],
            expected_facts_sha256=current["sha256"],
        )
    caller_path = tmp_path / "batch-caller-path"
    with pytest.raises(
        review_workspace.ReviewWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        review_workspace.apply_review_batch(  # type: ignore[arg-type]
            caller_path,
            operation_id="op-path-batch",
            review_actions=actions,
            expected_facts_version=current["version"],
            expected_facts_sha256=current["sha256"],
        )
    assert not caller_path.exists()
