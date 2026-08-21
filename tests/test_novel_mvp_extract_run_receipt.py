# PR-E1 临时收窄版：原版冻结在 cc793c4 的同一路径。
# PR-E2 带入 fact_workspace 的 M4 入账修改后，必须用 cc793c4 原版
# 逐字节还原本文件。
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        chapter_workspace,
        extract,
        extract_run_receipt,
        extract_tool,
        extract_workspace,
        segment_workspace,
    )
    from mvp.workspace import VersionConflictError, WorkspaceRouter
finally:
    sys.path.pop(0)


OPTIONS = {"seg_min_chars": 80, "seg_max_chars": 120, "halo_chars": 20}


def _revision_ref(chapter_id: str, text: str) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": 1,
        "revision_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def _chapters() -> list[dict]:
    rows = [
        ("c01", "林乔把钥匙放进木匣。"),
        ("c02", "周宁沿着雨巷追查送信人。" * 20),
    ]
    return [
        {
            "contract": "C1_CHAPTER_DOC",
            "version": "v1",
            "id": chapter_id,
            "title": f"第{chapter_id[1:]}章",
            "kind": "draft",
            "text": text,
            "added_at": "2026-08-20 00:00:00",
            "chapter_revision_ref": _revision_ref(chapter_id, text),
        }
        for chapter_id, text in rows
    ]


def _setup(workspace) -> None:
    chapters = _chapters()
    chapter_workspace.persist_c1_current_views(
        workspace,
        "op-c1",
        chapters,
        [copy.deepcopy(row["chapter_revision_ref"]) for row in chapters],
        {"chapters": 0, "chapter_index": 0},
    )
    segment_workspace.persist_current_segments(
        workspace,
        "op-c2",
        OPTIONS["seg_min_chars"],
        OPTIONS["seg_max_chars"],
        OPTIONS["halo_chars"],
        0,
    )


def _responses(workspace) -> dict:
    responses = {}
    for item in segment_workspace.read_current_segments(workspace)["items"]:
        chapter_id = item["chapter_revision_ref"]["chapter_id"]
        quote = (
            "林乔把钥匙放进木匣"
            if chapter_id == "c01"
            else "周宁沿着雨巷追查送信人"
        )
        responses[extract_tool.item_key(item)] = {
            "data": {
                "facts": [
                    {
                        "text": f"{chapter_id} 中发生了一项合成事件。",
                        "quote": quote,
                    }
                ]
            },
            "usage": {},
            "model": "FROZEN_OFFLINE_RESPONSE",
        }
    return responses


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def test_complete_receipt_binds_current_c3_and_survives_restart(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project("principal-a", "M3")
    _setup(workspace)
    responses = _responses(workspace)

    receipt = extract_workspace.persist_current_fact_candidates(
        workspace, "op-complete", responses, 0
    )
    current = extract_workspace.read_current_complete_fact_candidates(workspace)
    run_view = extract_workspace.read_fact_candidate_run_receipts(workspace)
    reopened = WorkspaceRouter(runtime_root).open_project(
        "principal-a", workspace.project_id
    )

    assert receipt["versions"] == {"fact_candidates": 1}
    assert run_view["version"] == 1
    assert len(run_view["runs"]) == 1
    run = run_view["runs"][0]
    assert run["completion_state"] == "COMPLETE"
    assert run["attempt_count"] == 1
    assert run["unprocessed_item_keys"] == []
    assert run["candidate_snapshot"] == {
        "version": workspace.read("fact_candidates")["version"],
        "sha256": workspace.read("fact_candidates")["sha256"],
    }
    assert _canonical_bytes(
        extract_workspace.read_current_complete_fact_candidates(reopened)
    ) == _canonical_bytes(current)
    assert _canonical_bytes(
        extract_workspace.read_fact_candidate_run_receipts(reopened)
    ) == _canonical_bytes(run_view)


def test_failed_run_receipt_never_overwrites_last_complete_c3(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "M3"
    )
    _setup(workspace)
    extract_workspace.persist_current_fact_candidates(
        workspace, "op-complete", _responses(workspace), 0
    )
    before = workspace.read("fact_candidates")
    item_keys = [
        extract_tool.item_key(item)
        for item in segment_workspace.read_current_segments(workspace)["items"]
    ]
    raw = b'{"content":"{\\"facts\\":["}'
    failure = extract.TruncatedOutput(
        "truncated",
        finish_reason="length",
        raw_response_sha256=hashlib.sha256(raw).hexdigest(),
        raw_response_bytes=len(raw),
    )

    extract_workspace.persist_failed_fact_candidate_run(
        workspace,
        operation_id="op-failed",
        provider_ref="arkcli:NO_API_SYNTHETIC",
        failure=failure,
        failed_item_key=item_keys[1],
        completed_item_keys=[item_keys[0]],
        accepted_candidate_count=1,
        expected_run_receipts_version=1,
    )
    run_view = extract_workspace.read_fact_candidate_run_receipts(workspace)

    assert workspace.read("fact_candidates") == before
    assert [row["completion_state"] for row in run_view["runs"]] == [
        "COMPLETE",
        "INCOMPLETE_TRUNCATED",
    ]
    failed = run_view["runs"][1]
    assert failed["completed_item_keys"] == [item_keys[0]]
    assert failed["unprocessed_item_keys"] == item_keys[1:]
    assert failed["candidate_snapshot"] is None
    assert failed["attempt_count"] == 1
    assert extract_workspace.read_current_complete_fact_candidates(workspace) == before[
        "payload"
    ]


def test_complete_operation_replays_after_later_run_receipt(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "M3"
    )
    _setup(workspace)
    responses = _responses(workspace)
    first = extract_workspace.persist_current_fact_candidates(
        workspace, "op-complete", responses, 0
    )
    item_keys = [
        extract_tool.item_key(item)
        for item in segment_workspace.read_current_segments(workspace)["items"]
    ]
    extract_workspace.persist_failed_fact_candidate_run(
        workspace,
        operation_id="op-timeout-after-complete",
        provider_ref="arkcli:NO_API_SYNTHETIC",
        failure=extract.ExtractCallFailure(
            "timeout",
            completion_state="FAILED_TIMEOUT",
            code="ARKCLI_TIMEOUT",
        ),
        failed_item_key=item_keys[0],
        completed_item_keys=[],
        accepted_candidate_count=0,
        expected_run_receipts_version=1,
    )

    replay = extract_workspace.persist_current_fact_candidates(
        workspace, "op-complete", copy.deepcopy(responses), 0
    )

    assert replay["replayed"] is True
    assert replay["generation_id"] == first["generation_id"]
    assert [
        row["completion_state"]
        for row in extract_workspace.read_fact_candidate_run_receipts(workspace)[
            "runs"
        ]
    ] == ["COMPLETE", "FAILED_TIMEOUT"]


def test_bad_failure_partition_writes_nothing(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "M3"
    )
    _setup(workspace)
    item_keys = [
        extract_tool.item_key(item)
        for item in segment_workspace.read_current_segments(workspace)["items"]
    ]
    failure = extract.ExtractCallFailure(
        "timeout",
        completion_state="FAILED_TIMEOUT",
        code="ARKCLI_TIMEOUT",
    )

    with pytest.raises(
        extract_workspace.ExtractWorkspaceError,
        match="M3_FAILURE_RECEIPT_INVALID",
    ):
        extract_workspace.persist_failed_fact_candidate_run(
            workspace,
            operation_id="op-bad-partition",
            provider_ref="arkcli:NO_API_SYNTHETIC",
            failure=failure,
            failed_item_key=item_keys[0],
            completed_item_keys=[item_keys[1]],
            accepted_candidate_count=1,
            expected_run_receipts_version=0,
        )

    assert workspace.read("fact_candidate_runs") is None
    assert workspace.read("fact_candidates") is None


def test_stale_failure_receipt_version_writes_nothing(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "M3"
    )
    _setup(workspace)
    extract_workspace.persist_failed_fact_candidate_run(
        workspace,
        operation_id="op-timeout-1",
        provider_ref="arkcli:NO_API_SYNTHETIC",
        failure=extract.ExtractCallFailure(
            "timeout",
            completion_state="FAILED_TIMEOUT",
            code="ARKCLI_TIMEOUT",
        ),
        failed_item_key=None,
        completed_item_keys=[],
        accepted_candidate_count=0,
        expected_run_receipts_version=0,
    )
    before = workspace.read("fact_candidate_runs")

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        extract_workspace.persist_failed_fact_candidate_run(
            workspace,
            operation_id="op-timeout-stale",
            provider_ref="arkcli:NO_API_SYNTHETIC",
            failure=extract.ExtractCallFailure(
                "timeout",
                completion_state="FAILED_TIMEOUT",
                code="ARKCLI_TIMEOUT",
            ),
            failed_item_key=None,
            completed_item_keys=[],
            accepted_candidate_count=0,
            expected_run_receipts_version=0,
        )

    assert workspace.read("fact_candidate_runs") == before


def test_source_change_marks_complete_receipt_and_c3_stale(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "M3"
    )
    _setup(workspace)
    extract_workspace.persist_current_fact_candidates(
        workspace, "op-complete", _responses(workspace), 0
    )
    before = workspace.read("fact_candidates")
    segments = workspace.read("segments")
    workspace.commit(
        "op-segments-v2",
        {"segments": segments["payload"]},
        {"segments": segments["version"]},
    )

    with pytest.raises(
        extract_workspace.FactCandidatesStaleError,
        match="FACT_CANDIDATES_STALE",
    ):
        extract_workspace.read_current_complete_fact_candidates(workspace)

    assert workspace.read("fact_candidates") == before


def test_failure_receipt_accepts_all_declared_transport_states() -> None:
    source_identity = {
        "segments": {"version": 1, "sha256": "1" * 64},
        "chapter_index": {"version": 1, "sha256": "2" * 64},
    }
    item_keys = ["c01:r1:s1"]
    for state in sorted(extract_run_receipt.FAILURE_STATES):
        raw_required = state in {"INCOMPLETE_TRUNCATED", "FAILED_RAW_RESPONSE"}
        failure = {
            "code": state,
            "failed_item_key": item_keys[0],
            "finish_reason": "length" if state == "INCOMPLETE_TRUNCATED" else None,
            "raw_response_sha256": "3" * 64 if raw_required else None,
            "raw_response_bytes": 10 if raw_required else None,
        }
        receipt = extract_run_receipt.build_failure_receipt(
            operation_id=f"op-{state.lower()}",
            completion_state=state,
            provider_ref="synthetic-provider",
            source_identity=source_identity,
            expected_item_keys=item_keys,
            completed_item_keys=[],
            accepted_candidate_count=0,
            failure=failure,
            ledger_parent_version=0,
        )
        assert receipt["completion_state"] == state
        assert receipt["attempt_count"] == 1
        assert receipt["candidate_snapshot"] is None
