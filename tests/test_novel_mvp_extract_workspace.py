from __future__ import annotations

import copy
import hashlib
import inspect
import json
import subprocess
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
        extract_tool,
        extract_workspace,
        segment_workspace,
    )
    from mvp.workspace import (
        InvalidLogicalKeyError,
        OperationConflictError,
        ProjectNotFoundError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


OPTIONS = {"seg_min_chars": 80, "seg_max_chars": 120, "halo_chars": 20}


def _revision_ref(chapter_id: str, text: str, revision_no: int = 1) -> dict:
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def _chapter(chapter_id: str, text: str, revision_no: int = 1) -> dict:
    return {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": chapter_id,
        "title": f"第{chapter_id[1:]}章",
        "kind": "draft",
        "text": text,
        "added_at": "2026-08-19 16:00:00",
        "chapter_revision_ref": _revision_ref(chapter_id, text, revision_no),
    }


def _chapters() -> list[dict]:
    return [
        _chapter("c01", "林乔把钥匙放进木匣。"),
        _chapter("c02", "周宁沿着雨巷追查送信人。" * 20),
    ]


def _save_chapters(workspace, chapters: list[dict], operation_id: str = "op-c1"):
    return chapter_workspace.persist_c1_current_views(
        workspace,
        operation_id,
        chapters,
        [copy.deepcopy(item["chapter_revision_ref"]) for item in chapters],
        {"chapters": 0, "chapter_index": 0},
    )


def _save_segments(workspace, operation_id: str = "op-m2", expected: int = 0):
    return segment_workspace.persist_current_segments(
        workspace,
        operation_id,
        OPTIONS["seg_min_chars"],
        OPTIONS["seg_max_chars"],
        OPTIONS["halo_chars"],
        expected,
    )


def _setup_sources(workspace) -> None:
    _save_chapters(workspace, _chapters())
    _save_segments(workspace)


def _responses(workspace) -> dict:
    result = {}
    for item in segment_workspace.read_current_segments(workspace)["items"]:
        chapter_id = item["chapter_revision_ref"]["chapter_id"]
        quote = "林乔把钥匙放进木匣" if chapter_id == "c01" else "周宁沿着雨巷追查送信人"
        result[extract_tool.item_key(item)] = {
            "data": {
                "facts": [
                    {
                        "text": f"{chapter_id} 中发生了一项可回原文核对的事件。",
                        "quote": quote,
                    }
                ]
            },
            "usage": {},
            "model": "FROZEN_OFFLINE_RESPONSE",
        }
    return result


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _persist(workspace, operation_id: str, responses: object, expected: int):
    return extract_workspace.persist_current_fact_candidates(
        workspace,
        operation_id,
        responses,
        expected,
    )


def test_multichapter_offline_candidates_persist_restart_and_never_call_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project(
        "principal-a", "M3 项目"
    )
    _setup_sources(workspace)
    responses = _responses(workspace)
    monkeypatch.setattr(
        extract.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("离线 M3 不得调用模型")
        ),
    )

    receipt = _persist(workspace, "op-m3", responses, 0)
    stored = workspace.read("fact_candidates")["payload"]
    reopened = WorkspaceRouter(runtime_root).open_project(
        "principal-a", workspace.project_id
    )
    restored = extract_workspace.read_current_fact_candidates(reopened)

    assert receipt["status"] == "COMMITTED"
    assert receipt["versions"] == {"fact_candidates": 1}
    assert _canonical_bytes(restored) == _canonical_bytes(stored)
    assert len(restored["items"]) == 2
    assert {
        item["chapter_revision_ref"]["chapter_id"] for item in restored["items"]
    } == {"c01", "c02"}
    assert all(item["contract"] == "C3_FACT_CANDIDATE" for item in restored["items"])
    assert restored["source_identity"] == {
        "segments": {
            "version": workspace.read("segments")["version"],
            "sha256": workspace.read("segments")["sha256"],
        },
        "chapter_index": {
            "version": workspace.read("chapter_index")["version"],
            "sha256": workspace.read("chapter_index")["sha256"],
        },
    }
    assert restored["responses_identity"]["kind"] == (
        "LOCAL_FILESYSTEM_ONLY_FROZEN_RESPONSES"
    )
    assert restored["responses_identity"]["item_keys"] == sorted(responses)
    assert workspace.read("facts") is None
    assert workspace.read("state") is None
    assert workspace.read("module_state") is None


@pytest.mark.parametrize("failure", ["missing", "bad_field", "bad_quote", "not_object"])
def test_bad_or_missing_frozen_response_rejects_whole_batch(
    tmp_path: Path,
    failure: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / failure).create_project(
        "principal-a", "坏响应"
    )
    _setup_sources(workspace)
    responses: object = _responses(workspace)
    if failure == "not_object":
        responses = []
    else:
        responses = copy.deepcopy(responses)
        second_key = sorted(responses)[1]
        if failure == "missing":
            responses.pop(second_key)
        elif failure == "bad_field":
            responses[second_key]["unexpected"] = True
        else:
            responses[second_key]["data"]["facts"][0]["quote"] = "原文里不存在"

    with pytest.raises(extract_workspace.ExtractWorkspaceError):
        _persist(workspace, "op-bad-m3", responses, 0)

    assert workspace.read("fact_candidates") is None


@pytest.mark.parametrize(
    "mismatch",
    ["missing", "old_revision_extra", "unknown_chapter_extra"],
)
def test_frozen_response_keys_must_exactly_match_current_c2_before_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / mismatch).create_project(
        "principal-a", "冻结响应精确批次"
    )
    _setup_sources(workspace)
    current_responses = _responses(workspace)
    _persist(workspace, "op-initial-c3", current_responses, 0)
    before = workspace.read("fact_candidates")
    mismatched = copy.deepcopy(current_responses)
    first_key = sorted(mismatched)[0]
    if mismatch == "missing":
        mismatched.pop(first_key)
    elif mismatch == "old_revision_extra":
        mismatched[first_key.replace(":r1:", ":r99:")] = copy.deepcopy(
            mismatched[first_key]
        )
    else:
        mismatched["c99:r1:s1"] = copy.deepcopy(mismatched[first_key])

    monkeypatch.setattr(
        extract_tool,
        "execute",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("键集合不精确时不得进入 provider 批次")
        ),
    )

    with pytest.raises(
        extract_workspace.ExtractWorkspaceError,
        match="RESPONSES_EXACT_BATCH_INVALID",
    ):
        _persist(workspace, f"op-{mismatch}", mismatched, 1)

    assert workspace.read("fact_candidates") == before


def test_exact_response_keys_allow_every_item_to_return_zero_candidates(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "empty-candidates").create_project(
        "principal-a", "空候选合法批次"
    )
    _setup_sources(workspace)
    responses = _responses(workspace)
    for response in responses.values():
        response["data"]["facts"] = []

    receipt = _persist(workspace, "op-empty-candidates", responses, 0)
    restored = extract_workspace.read_current_fact_candidates(workspace)

    assert receipt["status"] == "COMMITTED"
    assert restored["items"] == []
    assert restored["responses_identity"]["item_keys"] == sorted(responses)


def test_tampered_stored_response_identity_must_still_match_current_c2(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "identity-tamper").create_project(
        "principal-a", "冻结身份防漂移"
    )
    _setup_sources(workspace)
    _persist(workspace, "op-valid-c3", _responses(workspace), 0)
    state = workspace.read("fact_candidates")
    tampered = copy.deepcopy(state["payload"])
    tampered["responses_identity"]["item_keys"].append("c99:r1:s1")
    tampered["responses_identity"]["item_keys"].sort()
    workspace.commit(
        "op-tamper-response-identity",
        {"fact_candidates": tampered},
        {"fact_candidates": state["version"]},
    )

    with pytest.raises(
        extract_workspace.ExtractWorkspaceError,
        match="FACT_CANDIDATES_RESPONSES_EXACT_BATCH_INVALID",
    ):
        extract_workspace.read_current_fact_candidates(workspace)


@pytest.mark.parametrize("damage", ["old_revision", "duplicate_c2"])
def test_old_revision_or_duplicate_c2_rejects_before_candidate_write(
    tmp_path: Path,
    damage: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / damage).create_project(
        "principal-a", "坏 C2"
    )
    _setup_sources(workspace)
    responses = _responses(workspace)
    segments = copy.deepcopy(workspace.read("segments")["payload"])
    if damage == "old_revision":
        segments["items"][0]["chapter_revision_ref"]["revision_no"] = 99
    else:
        segments["items"].append(copy.deepcopy(segments["items"][0]))
    workspace.commit(
        "op-corrupt-segments",
        {"segments": segments},
        {"segments": 1},
    )

    with pytest.raises(
        extract_workspace.ExtractWorkspaceError,
        match="M3_SOURCE_STATE_INVALID",
    ):
        _persist(workspace, "op-m3-corrupt", responses, 0)

    assert workspace.read("fact_candidates") is None


@pytest.mark.parametrize("source_key", ["segments", "chapter_index"])
def test_upstream_version_change_marks_saved_candidates_stale(
    tmp_path: Path,
    source_key: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / source_key).create_project(
        "principal-a", "改版项目"
    )
    _setup_sources(workspace)
    _persist(workspace, "op-m3", _responses(workspace), 0)
    before = workspace.read("fact_candidates")
    source_state = workspace.read(source_key)
    workspace.commit(
        f"op-{source_key}-v2",
        {source_key: source_state["payload"]},
        {source_key: source_state["version"]},
    )

    with pytest.raises(
        extract_workspace.FactCandidatesStaleError,
        match="FACT_CANDIDATES_STALE",
    ):
        extract_workspace.read_current_fact_candidates(workspace)

    assert workspace.read("fact_candidates") == before


def test_source_change_during_extraction_rejects_before_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "race").create_project(
        "principal-a", "并发项目"
    )
    _setup_sources(workspace)
    responses = _responses(workspace)
    real_execute = extract_tool.execute

    def execute_and_advance_segments(request: dict, provider) -> dict:
        result = real_execute(request, provider)
        state = workspace.read("segments")
        workspace.commit(
            "op-segments-race",
            {"segments": state["payload"]},
            {"segments": state["version"]},
        )
        return result

    monkeypatch.setattr(extract_tool, "execute", execute_and_advance_segments)

    with pytest.raises(
        extract_workspace.FactCandidatesStaleError,
        match="FACT_CANDIDATES_SOURCE_CHANGED_DURING_RUN",
    ):
        _persist(workspace, "op-m3-race", responses, 0)

    assert workspace.read("fact_candidates") is None


def test_idempotency_operation_conflict_and_version_conflict_keep_old_c3(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "versions").create_project(
        "principal-a", "版本项目"
    )
    _setup_sources(workspace)
    responses = _responses(workspace)
    first = _persist(workspace, "op-idem", responses, 0)
    replay = _persist(workspace, "op-idem", responses, 0)
    before = workspace.read("fact_candidates")

    assert replay["replayed"] is True
    assert replay["generation_id"] == first["generation_id"]
    changed = copy.deepcopy(responses)
    changed[sorted(changed)[0]]["model"] = "OTHER_FROZEN_IDENTITY"
    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        _persist(workspace, "op-idem", changed, 0)
    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        _persist(workspace, "op-stale-version", responses, 0)

    assert workspace.read("fact_candidates") == before


def test_failed_rerun_and_tampered_candidate_never_hide_prior_state(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "preserve").create_project(
        "principal-a", "保留旧候选"
    )
    _setup_sources(workspace)
    responses = _responses(workspace)
    _persist(workspace, "op-m3", responses, 0)
    before = workspace.read("fact_candidates")
    bad = copy.deepcopy(responses)
    bad[sorted(bad)[1]]["data"]["facts"][0]["quote"] = "坏引用"

    with pytest.raises(extract_workspace.ExtractWorkspaceError):
        _persist(workspace, "op-m3-bad", bad, 1)
    assert workspace.read("fact_candidates") == before

    tampered = copy.deepcopy(before["payload"])
    tampered["items"][0]["quote"] = "不在责任段中的引用"
    workspace.commit(
        "op-tamper-c3",
        {"fact_candidates": tampered},
        {"fact_candidates": 1},
    )
    with pytest.raises(
        extract_workspace.ExtractWorkspaceError,
        match="FACT_CANDIDATE_INVALID",
    ):
        extract_workspace.read_current_fact_candidates(workspace)


def test_new_process_reads_byte_equivalent_candidates(tmp_path: Path) -> None:
    runtime_root = tmp_path / "restart"
    workspace = WorkspaceRouter(runtime_root).create_project(
        "principal-a", "重启项目"
    )
    _setup_sources(workspace)
    _persist(workspace, "op-m3", _responses(workspace), 0)
    expected = extract_workspace.read_current_fact_candidates(workspace)
    child = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from mvp.extract_workspace import read_current_fact_candidates
from mvp.workspace import WorkspaceRouter
workspace = WorkspaceRouter(sys.argv[2]).open_project(sys.argv[3], sys.argv[4])
value = read_current_fact_candidates(workspace)
sys.stdout.buffer.write((json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\\n").encode("utf-8"))
"""

    reopened = subprocess.run(
        [
            sys.executable,
            "-c",
            child,
            str(PRODUCT_ROOT),
            str(runtime_root),
            "principal-a",
            workspace.project_id,
        ],
        capture_output=True,
        check=True,
    )

    assert reopened.stdout == _canonical_bytes(expected)


def test_author_scope_signatures_and_unknown_key_guard_remain(
    tmp_path: Path,
) -> None:
    router = WorkspaceRouter(tmp_path / "scope")
    alice = router.create_project("principal-a", "同名项目")
    bob = router.create_project("principal-b", "同名项目")
    _setup_sources(bob)
    _persist(bob, "op-bob-m3", _responses(bob), 0)
    fake_path = tmp_path / "fake-workspace"

    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("principal-a", bob.project_id)
    with pytest.raises(
        extract_workspace.ExtractWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        extract_workspace.read_current_fact_candidates(fake_path)
    with pytest.raises(InvalidLogicalKeyError, match="LOGICAL_KEY_NOT_ALLOWED"):
        alice.read("fact_candidate")

    assert alice.read("fact_candidates") is None
    assert not fake_path.exists()
    assert list(
        inspect.signature(
            extract_workspace.persist_current_fact_candidates
        ).parameters
    ) == [
        "workspace",
        "operation_id",
        "responses",
        "expected_fact_candidates_version",
    ]
    assert list(
        inspect.signature(extract_workspace.read_current_fact_candidates).parameters
    ) == ["workspace"]
