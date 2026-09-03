from __future__ import annotations

import copy
import hashlib
import inspect
import json
import resource
import sys
import time
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import c9_ledger_read_adapter as adapter
    from mvp import ledger_directory_workspace, unified_retrieval_core as c9
    from mvp import unified_retrieval_composition as composition
    from mvp.workspace import (
        AuthorWorkspace,
        CurrentGenerationSnapshot,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chapter(chapter_id: str) -> dict:
    text = f"{chapter_id} 的合成正文。"
    return {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": chapter_id,
        "title": f"第{int(chapter_id[1:])}章",
        "kind": "draft",
        "text": text,
        "added_at": "2026-09-03 10:00:00",
        "chapter_revision_ref": {
            "chapter_id": chapter_id,
            "revision_no": 1,
            "revision_text_sha256": _sha(text),
        },
    }


def _fact(fact_number: int, chapter: dict) -> dict:
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": f"f{fact_number:03d}",
        "chapter_id": chapter["id"],
        "text": f"合成事实 {fact_number}",
        "quote": "",
        "status": "confirmed",
        "source": "CCZ170_SCALE_SYNTHETIC",
        "note": "",
        "added_at": "2026-09-03 10:01:00",
        "chapter_revision_ref": copy.deepcopy(chapter["chapter_revision_ref"]),
        "anchor_ref": None,
        "anchor_state": "LEGACY_UNVERIFIED",
        "recheck": None,
    }


def _workspace(tmp_path: Path, chapter_count: int, facts_per_chapter: int):
    workspace = WorkspaceRouter(tmp_path / f"runtime-{chapter_count}").create_project(
        "auth:alice", f"合成项目 {chapter_count}"
    )
    ledger_directory_workspace.initialize_directory(workspace, "op-directory")
    chapters = [_chapter(f"c{number:02d}") for number in range(1, chapter_count + 1)]
    facts = []
    fact_number = 1
    for chapter in chapters:
        for _ in range(facts_per_chapter):
            facts.append(_fact(fact_number, chapter))
            fact_number += 1
    workspace.commit(
        "op-content",
        {
            "chapters": chapters,
            "chapter_index": [
                copy.deepcopy(chapter["chapter_revision_ref"]) for chapter in chapters
            ],
            "facts": facts,
        },
        {"chapters": 0, "chapter_index": 0, "facts": 0},
    )
    return workspace, chapters, facts


def _trusted() -> dict[str, str]:
    return {
        "caller_id": "ccz170-composition-test",
        "permission_profile": "AUTHOR_PROJECT_INTERNAL",
        "permission_policy_version": "permission-policy-v1",
    }


def _need(need_id: str, object_ref: str, *, rank: int | None = None) -> dict:
    obligation = "HARD" if rank is None else "SHOULD"
    return {
        "need_id": need_id,
        "evidence_layer": "LEDGER_OBJECT",
        "parent_need_id": None,
        "source_contract": "LEDGER_READ_TOOL_CONTRACT",
        "source_contract_version": "ledger-read-tool-contract-v1",
        "object_ref": object_ref,
        "actuality_class": "CURRENT_FACT_OR_STATE",
        "obligation_tier": obligation,
        "selection_rank": rank,
        "task_relation": f"合成任务需要 {need_id}",
        "estimated_tokens": 8,
        "recall_disposition": "NOT_RETRIEVABLE",
        "recall_handle": None,
        "expansion_trigger": "INITIAL",
        "trigger_provenance": None,
    }


def _request(workspace: AuthorWorkspace, needs: list[dict]) -> dict:
    return c9.seal_request(
        {
            "contract": "C9_RETRIEVAL_REQUEST",
            "version": c9.VERSION,
            "scope": {
                "author_id": workspace.author_id,
                "project_id": workspace.project_id,
                "task_id": "TASK-CCZ170",
                "consumer_id": "CCZ170-TEST",
                "workpoint_ref": "chapter:c-next",
                "story_scope_ref": "story-scope:test",
                "sandbox_ref": None,
                "upstream_card_ref": None,
            },
            "basis_mode": "current_at_start",
            "task_actuality_scope": "CURRENT_TRUTH_REQUIRED",
            "budget": {
                "limit_tokens": 100_000,
                "estimator_ref": "ccz170-synthetic-estimator-v1",
            },
            "gap_policy": {
                "policy_ref": "ccz170-test-gap-policy-v1",
                "missing_required_behavior": "BLOCK",
            },
            "source_needs": copy.deepcopy(needs),
        }
    )


def test_real_reader_adapter_and_c9_form_one_deterministic_run(tmp_path: Path) -> None:
    workspace, _, facts = _workspace(tmp_path, 2, 2)
    needs = [
        _need("NEED-DIRECTORY", adapter.directory_object_ref()),
        _need(
            "NEED-CHAPTER",
            adapter.chapter_evidence_object_ref("c01", include_chapter_text=False),
            rank=1,
        ),
        _need(
            "NEED-FACT",
            adapter.ledger_entries_object_ref("事实账", [facts[-1]["id"]]),
            rank=2,
        ),
    ]
    request = _request(workspace, needs)

    first = composition.run_current_retrieval(workspace, _trusted(), request)
    second = composition.run_current_retrieval(workspace, _trusted(), request)

    assert first == second
    assert first["status"] == "READY"
    assert first["short_receipt"]["loaded_count"] == 3
    assert first["short_receipt"]["required_satisfied"] == 1
    for loaded in first["material_package"]["loaded"]:
        validation = loaded["source_validation"]
        assert validation["validation_result"] == "LEDGER_READ_RESPONSE_VALID"
        assert validation["input_mode"] == "LEDGER_READ_RESPONSE"
        assert (
            validation["source_binding"]["canonical_object_ref"] == loaded["object_ref"]
        )
        assert validation["source_binding"]["pin_proof_status"] == "CURRENT_AT_START"
    assert list(inspect.signature(composition.run_current_retrieval).parameters) == [
        "workspace",
        "trusted_execution_context",
        "c9_request",
    ]
    assert (
        "validator"
        not in inspect.signature(composition.run_current_retrieval).parameters
    )


def test_composition_rejects_forged_scope_and_noncanonical_reference(
    tmp_path: Path,
) -> None:
    workspace, _, facts = _workspace(tmp_path, 1, 1)
    request = _request(
        workspace,
        [
            _need(
                "NEED-FACT",
                adapter.ledger_entries_object_ref("事实账", [facts[0]["id"]]),
            )
        ],
    )
    forged = copy.deepcopy(request)
    forged["scope"]["project_id"] = "PROJECT-FORGED"
    forged = c9.seal_request(forged)
    bad_ref = copy.deepcopy(request)
    bad_ref["source_needs"][0]["object_ref"] = "/tmp/facts.json"
    bad_ref = c9.seal_request(bad_ref)

    with pytest.raises(
        composition.UnifiedRetrievalCompositionError,
        match="COMPOSITION_SCOPE_MISMATCH",
    ):
        composition.run_current_retrieval(workspace, _trusted(), forged)
    with pytest.raises(
        adapter.C9LedgerReadAdapterError, match="LEDGER_OBJECT_REF_INVALID"
    ):
        composition.run_current_retrieval(workspace, _trusted(), bad_ref)


def test_current_advance_after_a_read_stops_the_whole_c9_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, _, facts = _workspace(tmp_path, 1, 2)
    needs = [
        _need(
            "NEED-FACT-1",
            adapter.ledger_entries_object_ref("事实账", [facts[0]["id"]]),
        ),
        _need(
            "NEED-FACT-2",
            adapter.ledger_entries_object_ref("事实账", [facts[1]["id"]]),
            rank=1,
        ),
    ]
    request = _request(workspace, needs)
    real_read_need = adapter.read_need
    calls = 0

    def advancing_read(session, current_request, need):
        nonlocal calls
        result = real_read_need(session, current_request, need)
        calls += 1
        if calls == 1:
            workspace.commit(
                "op-advance-during-read",
                {"state": {"advanced": True}},
                {"state": 0},
            )
        return result

    monkeypatch.setattr(adapter, "read_need", advancing_read)
    result = composition.run_current_retrieval(workspace, _trusted(), request)

    assert result["status"] == "STOPPED"
    assert result["material_package"]["loaded"] == []
    assert {
        row["reason_code"] for row in result["material_package"]["outstanding"]
    } == {"CURRENT_ADVANCED"}
    assert all(row["fatal"] for row in result["material_package"]["outstanding"])


def test_reader_adapter_preserve_empty_and_unavailable_in_c9(tmp_path: Path) -> None:
    workspace, _, _ = _workspace(tmp_path, 1, 0)
    needs = [
        _need(
            "NEED-EMPTY",
            adapter.chapter_evidence_object_ref("c01", include_chapter_text=False),
        ),
        _need(
            "NEED-UNAVAILABLE",
            adapter.ledger_entries_object_ref("地点账", ["LOC-0001"]),
            rank=1,
        ),
    ]
    request = _request(workspace, needs)
    result = composition.run_current_retrieval(workspace, _trusted(), request)

    assert result["status"] == "STOPPED"
    outstanding = {
        row["need_id"]: (row["source_status"], row["reason_code"])
        for row in result["material_package"]["outstanding"]
    }
    assert outstanding == {
        "NEED-EMPTY": ("EMPTY", "NO_MATCHING_ENTRIES"),
        "NEED-UNAVAILABLE": ("REJECTED", "CAPABILITY_UNAVAILABLE"),
    }


def test_reader_error_stays_error_after_c9_composition(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime-empty").create_project(
        "auth:alice", "空项目"
    )
    request = _request(
        workspace,
        [_need("NEED-DIRECTORY", adapter.directory_object_ref())],
    )

    result = composition.run_current_retrieval(workspace, _trusted(), request)

    assert result["status"] == "STOPPED"
    outstanding = result["material_package"]["outstanding"]
    assert len(outstanding) == 1
    assert (outstanding[0]["source_status"], outstanding[0]["reason_code"]) == (
        "ERROR",
        "DIRECTORY_NOT_INITIALIZED",
    )


def test_10_50_100_chapter_shapes_use_one_generation_and_bounded_point_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_opens: Counter[str] = Counter()
    state_reads: Counter[tuple[str, str]] = Counter()
    opened_generations: dict[str, str] = {}
    real_snapshot_open = AuthorWorkspace.read_current_snapshot
    real_snapshot_read = CurrentGenerationSnapshot.read

    def counted_open(self, logical_keys):
        snapshot_opens[self.project_id] += 1
        snapshot = real_snapshot_open(self, logical_keys)
        assert snapshot.generation_id is not None
        opened_generations[self.project_id] = snapshot.generation_id
        return snapshot

    def counted_read(self, logical_key):
        state_reads[(self.generation_id or "empty", logical_key)] += 1
        return real_snapshot_read(self, logical_key)

    monkeypatch.setattr(AuthorWorkspace, "read_current_snapshot", counted_open)
    monkeypatch.setattr(CurrentGenerationSnapshot, "read", counted_read)
    receipts = []
    for chapter_count, need_count in ((10, 1), (50, 10), (100, 50)):
        workspace, _, facts = _workspace(tmp_path, chapter_count, 200)
        selected = [facts[index * 199] for index in range(need_count)]
        needs = [
            _need(
                f"NEED-{index:02d}",
                adapter.ledger_entries_object_ref("事实账", [fact["id"]]),
                rank=index + 1,
            )
            for index, fact in enumerate(selected)
        ]
        request = _request(workspace, needs)
        payload_bytes = len(
            json.dumps(
                {"chapters": chapter_count, "facts": facts},
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        peak_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        started = time.perf_counter()
        result = composition.run_current_retrieval(workspace, _trusted(), request)
        elapsed = time.perf_counter() - started
        peak_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_bytes = peak_after if sys.platform == "darwin" else peak_after * 1024
        peak_before_bytes = (
            peak_before if sys.platform == "darwin" else peak_before * 1024
        )
        generation = opened_generations[workspace.project_id]
        receipts.append(
            {
                "chapters": chapter_count,
                "facts": len(facts),
                "needs": need_count,
                "elapsed_seconds": round(elapsed, 6),
                "peak_bytes": peak_bytes,
                "peak_growth_bytes": max(0, peak_bytes - peak_before_bytes),
                "payload_bytes": payload_bytes,
                "snapshot_opens": snapshot_opens[workspace.project_id],
                "logical_key_reads": {
                    key: state_reads[(generation, key)]
                    for key in (
                        "ledger_directory",
                        "chapters",
                        "chapter_index",
                        "facts",
                    )
                },
            }
        )

        assert result["status"] == "READY"
        assert result["short_receipt"]["loaded_count"] == need_count
        assert all(
            len(json.loads(row["material_text"])["entries"]) == 1
            for row in result["material_package"]["loaded"]
        )
        assert snapshot_opens[workspace.project_id] == 1
        assert all(
            state_reads[(generation, key)] == 1
            for key in receipts[-1]["logical_key_reads"]
        )

    per_fact = [row["payload_bytes"] / row["facts"] for row in receipts]
    assert receipts[-1]["facts"] == 20_000
    assert (
        receipts[0]["payload_bytes"]
        < receipts[1]["payload_bytes"]
        < receipts[2]["payload_bytes"]
    )
    assert max(per_fact) / min(per_fact) < 1.2
    print(
        "CCZ158_SCALE_RECEIPT "
        + json.dumps(receipts, ensure_ascii=False, sort_keys=True)
    )
