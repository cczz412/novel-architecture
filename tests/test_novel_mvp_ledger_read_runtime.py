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
    from mvp import ledger_directory_workspace, ledger_read_runtime
    from mvp.workspace import WorkspaceRouter
finally:
    sys.path.pop(0)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chapter(chapter_id: str, text: str | None = None) -> dict:
    body = text or f"{chapter_id} 的正文。"
    return {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": chapter_id,
        "title": f"第{int(chapter_id[1:])}章",
        "kind": "draft",
        "text": body,
        "added_at": "2026-09-03 10:00:00",
        "chapter_revision_ref": {
            "chapter_id": chapter_id,
            "revision_no": 1,
            "revision_text_sha256": _sha(body),
        },
    }


def _fact(fact_id: str, chapter: dict, *, status: str = "confirmed") -> dict:
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": chapter["id"],
        "text": f"事实 {fact_id}",
        "quote": "",
        "status": status,
        "source": "CCZ170_SYNTHETIC",
        "note": "",
        "added_at": "2026-09-03 10:01:00",
        "chapter_revision_ref": copy.deepcopy(chapter["chapter_revision_ref"]),
        "anchor_ref": None,
        "anchor_state": "LEGACY_UNVERIFIED",
        "recheck": None,
    }


def _seed_workspace(
    tmp_path: Path,
    *,
    chapter_count: int = 2,
    facts_per_chapter: int = 1,
    chapter_text: str | None = None,
):
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "auth:alice", "项目"
    )
    ledger_directory_workspace.initialize_directory(workspace, "op-directory")
    chapters = [
        _chapter(f"c{index:02d}", chapter_text if index == 1 else None)
        for index in range(1, chapter_count + 1)
    ]
    facts = []
    fact_number = 1
    for chapter in chapters:
        for _ in range(facts_per_chapter):
            facts.append(_fact(f"f{fact_number:03d}", chapter))
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
        "caller_id": "ccz170-test",
        "permission_profile": "AUTHOR_PROJECT_INTERNAL",
        "permission_policy_version": "permission-policy-v1",
    }


def _request(session, request_id: str, tool: str, selector: dict) -> dict:
    return {
        "contract": "LEDGER_READ_REQUEST",
        "version": ledger_read_runtime.VERSION,
        "execution_context": {
            "request_id": request_id,
            "caller_id": session.execution_context["caller_id"],
            "author_id": session.author_id,
            "project_id": session.project_id,
            "permission_profile": session.execution_context["permission_profile"],
            "permission_policy_version": session.execution_context[
                "permission_policy_version"
            ],
        },
        "tool": tool,
        "basis": {"mode": "current_at_start"},
        "selector": copy.deepcopy(selector),
    }


def test_directory_and_chapter_fact_slice_are_real_current_reads(
    tmp_path: Path,
) -> None:
    workspace, chapters, facts = _seed_workspace(tmp_path)
    session = ledger_read_runtime.open_current_reader_session(workspace, _trusted())

    directory = ledger_read_runtime.execute_read(
        session,
        _request(session, "REQ-DIR", "get_ledger_directory", {}),
    )
    chapter = ledger_read_runtime.execute_read(
        session,
        _request(
            session,
            "REQ-CH",
            "get_chapter_evidence_slice",
            {"chapter_id": "c01", "include_chapter_text": False},
        ),
    )

    ledgers = directory["data"]["capability_snapshot"]["ledgers"]
    assert [row["ledger_name"] for row in ledgers] == [
        "章节账",
        "事实账",
        "人物账",
        "地点账",
        "物品账",
        "势力账",
        "体系账",
        "世界规则账",
        "长线账",
        "规划账",
    ]
    assert [row["runtime_status"] for row in ledgers[:2]] == [
        "AVAILABLE",
        "AVAILABLE",
    ]
    assert all(row["runtime_status"] == "UNAVAILABLE" for row in ledgers[2:])
    assert chapter["status"] == "OK"
    assert chapter["data"]["chapter"]["id"] == chapters[0]["id"]
    assert "text" not in chapter["data"]["chapter"]
    assert chapter["data"]["confirmed_facts"] == [facts[0]]
    assert chapter["limits"]["business_items"] == 2
    assert chapter["limits"]["truncated"] is False
    ledger_read_runtime.validate_ledger_read_document(directory)
    ledger_read_runtime.validate_ledger_read_document(chapter)


def test_entry_reads_preserve_request_order_and_bad_ref_returns_no_content(
    tmp_path: Path,
) -> None:
    workspace, _, facts = _seed_workspace(tmp_path, chapter_count=3)
    session = ledger_read_runtime.open_current_reader_session(workspace, _trusted())
    requested = [facts[2]["id"], facts[0]["id"]]
    response = ledger_read_runtime.execute_read(
        session,
        _request(
            session,
            "REQ-FACTS",
            "get_ledger_entries_by_ref",
            {"ledger_name": "事实账", "read_profile": "fact_record", "refs": requested},
        ),
    )
    missing = ledger_read_runtime.execute_read(
        session,
        _request(
            session,
            "REQ-MISSING",
            "get_ledger_entries_by_ref",
            {
                "ledger_name": "事实账",
                "read_profile": "fact_record",
                "refs": [facts[0]["id"], "f999"],
            },
        ),
    )

    assert [row["id"] for row in response["data"]["entries"]] == requested
    assert response["status"] == "OK"
    assert missing["status"] == "REJECTED"
    assert missing["reason_code"] == "ENTRY_NOT_FOUND"
    assert missing["data"] is None
    assert missing["receipt"]["source_manifest"] == []


def test_empty_unavailable_closed_and_uninitialized_are_distinct(
    tmp_path: Path,
) -> None:
    workspace, chapters, _ = _seed_workspace(tmp_path, facts_per_chapter=0)
    session = ledger_read_runtime.open_current_reader_session(workspace, _trusted())
    empty = ledger_read_runtime.execute_read(
        session,
        _request(
            session,
            "REQ-EMPTY",
            "get_chapter_evidence_slice",
            {"chapter_id": chapters[0]["id"], "include_chapter_text": True},
        ),
    )
    unavailable = ledger_read_runtime.execute_read(
        session,
        _request(
            session,
            "REQ-LOC",
            "get_ledger_entries_by_ref",
            {
                "ledger_name": "地点账",
                "read_profile": "location_definition",
                "refs": ["LOC-0001"],
            },
        ),
    )
    box = ledger_read_runtime.execute_read(
        session,
        _request(
            session,
            "REQ-BOX",
            "get_longline_box_status",
            {"box_ref": "BOX-0001"},
        ),
    )
    knowledge = ledger_read_runtime.execute_read(
        session,
        _request(
            session,
            "REQ-KE",
            "get_character_knowledge_edges_as_of",
            {
                "observer_ref": "CH-0001",
                "as_of": {"chapter_revision_ref": chapters[0]["chapter_revision_ref"]},
                "fact_refs": [],
            },
        ),
    )
    character = ledger_read_runtime.execute_read(
        session,
        _request(
            session,
            "REQ-CHAR",
            "get_character_state_as_of",
            {
                "character_ref": "CH-0001",
                "as_of": {"chapter_revision_ref": chapters[0]["chapter_revision_ref"]},
                "sections": ["state_timeline"],
                "state_keys": [],
            },
        ),
    )
    blank = WorkspaceRouter(tmp_path / "blank").create_project("auth:alice", "空项目")
    blank_session = ledger_read_runtime.open_current_reader_session(blank, _trusted())
    uninitialized = ledger_read_runtime.execute_read(
        blank_session,
        _request(blank_session, "REQ-BLANK", "get_ledger_directory", {}),
    )

    assert (empty["status"], empty["reason_code"]) == (
        "EMPTY",
        "NO_MATCHING_ENTRIES",
    )
    assert empty["data"] is None
    assert (unavailable["status"], unavailable["reason_code"]) == (
        "REJECTED",
        "CAPABILITY_UNAVAILABLE",
    )
    assert box["reason_code"] == "PROJECTION_NOT_AVAILABLE"
    assert knowledge["reason_code"] == "FORMAL_CONTRACT_NOT_AVAILABLE"
    assert character["reason_code"] == "CAPABILITY_UNAVAILABLE"
    assert (uninitialized["status"], uninitialized["reason_code"]) == (
        "ERROR",
        "DIRECTORY_NOT_INITIALIZED",
    )


def test_unauthorized_and_current_advanced_responses_do_not_leak_content(
    tmp_path: Path,
) -> None:
    workspace, _, facts = _seed_workspace(tmp_path)
    session = ledger_read_runtime.open_current_reader_session(workspace, _trusted())
    request = _request(
        session,
        "REQ-AUTH",
        "get_ledger_entries_by_ref",
        {
            "ledger_name": "事实账",
            "read_profile": "fact_record",
            "refs": [facts[0]["id"]],
        },
    )
    request["execution_context"]["author_id"] = "AUTHOR-FORGED"
    denied = ledger_read_runtime.execute_read(session, request)

    workspace.commit("op-advance", {"state": {"advanced": True}}, {"state": 0})
    advanced_request = _request(
        session,
        "REQ-ADVANCED",
        "get_ledger_entries_by_ref",
        {
            "ledger_name": "事实账",
            "read_profile": "fact_record",
            "refs": [facts[0]["id"]],
        },
    )
    advanced = ledger_read_runtime.execute_read(session, advanced_request)

    assert (denied["status"], denied["reason_code"]) == (
        "REJECTED",
        "UNAUTHORIZED",
    )
    assert denied["data"] is None
    assert denied["receipt"]["source_manifest"] == []
    assert denied["receipt"]["capability_snapshot_id"] is None
    assert workspace.author_id not in json.dumps(denied, ensure_ascii=False)
    assert (advanced["status"], advanced["reason_code"]) == (
        "REJECTED",
        "CURRENT_ADVANCED",
    )
    assert advanced["data"] is None


def test_limits_are_all_or_nothing_and_source_corruption_is_an_error(
    tmp_path: Path,
) -> None:
    huge_text = "甲" * (ledger_read_runtime.MAX_RESPONSE_BYTES + 1024)
    workspace, _, _ = _seed_workspace(tmp_path, chapter_text=huge_text)
    session = ledger_read_runtime.open_current_reader_session(workspace, _trusted())
    too_large = ledger_read_runtime.execute_read(
        session,
        _request(
            session,
            "REQ-LARGE",
            "get_chapter_evidence_slice",
            {"chapter_id": "c01", "include_chapter_text": True},
        ),
    )

    damaged = WorkspaceRouter(tmp_path / "damaged").create_project(
        "auth:alice", "坏来源"
    )
    ledger_directory_workspace.initialize_directory(damaged, "op-directory")
    damaged.commit(
        "op-invalid-content",
        {"chapters": [{"id": "c01"}], "chapter_index": [], "facts": []},
        {"chapters": 0, "chapter_index": 0, "facts": 0},
    )
    damaged_session = ledger_read_runtime.open_current_reader_session(
        damaged, _trusted()
    )
    corrupted = ledger_read_runtime.execute_read(
        damaged_session,
        _request(damaged_session, "REQ-CORRUPT", "get_ledger_directory", {}),
    )

    assert (too_large["status"], too_large["reason_code"]) == (
        "REJECTED",
        "RESULT_TOO_LARGE",
    )
    assert too_large["data"] is None
    assert (
        too_large["limits"]["response_bytes"] <= ledger_read_runtime.MAX_RESPONSE_BYTES
    )
    assert (corrupted["status"], corrupted["reason_code"]) == (
        "ERROR",
        "SOURCE_CORRUPTED",
    )


@pytest.mark.parametrize(
    ("fact_count", "expected_status", "expected_reason"),
    [(99, "OK", None), (100, "REJECTED", "RESULT_TOO_LARGE")],
)
def test_chapter_slice_enforces_the_100_business_item_boundary(
    tmp_path: Path,
    fact_count: int,
    expected_status: str,
    expected_reason: str | None,
) -> None:
    workspace, _, _ = _seed_workspace(
        tmp_path,
        chapter_count=1,
        facts_per_chapter=fact_count,
    )
    session = ledger_read_runtime.open_current_reader_session(workspace, _trusted())
    response = ledger_read_runtime.execute_read(
        session,
        _request(
            session,
            f"REQ-ITEMS-{fact_count}",
            "get_chapter_evidence_slice",
            {"chapter_id": "c01", "include_chapter_text": False},
        ),
    )

    assert (response["status"], response["reason_code"]) == (
        expected_status,
        expected_reason,
    )
    if fact_count == 99:
        assert response["limits"]["business_items"] == 100
    else:
        assert response["data"] is None
        assert response["limits"]["business_items"] == 0


def test_pinned_requests_are_rejected_without_reusing_current(tmp_path: Path) -> None:
    workspace, _, facts = _seed_workspace(tmp_path, chapter_count=1)
    session = ledger_read_runtime.open_current_reader_session(workspace, _trusted())
    current = ledger_read_runtime.execute_read(
        session,
        _request(
            session,
            "REQ-CURRENT",
            "get_ledger_entries_by_ref",
            {
                "ledger_name": "事实账",
                "read_profile": "fact_record",
                "refs": [facts[0]["id"]],
            },
        ),
    )
    source = current["receipt"]["source_manifest"][0]
    pinned = _request(
        session,
        "REQ-PINNED",
        "get_ledger_entries_by_ref",
        {
            "ledger_name": "事实账",
            "read_profile": "fact_record",
            "recall_codes": [
                {
                    "contract": "LEDGER_RECALL_CODE",
                    "version": "ledger-recall-code-v1",
                    "ledger_name": "事实账",
                    "entry_id": facts[0]["id"],
                    "rev": 1,
                    "sha": source["logical_content_sha256"],
                    "expires_at": None,
                }
            ],
        },
    )
    pinned["basis"] = {
        "mode": "pinned_manifest",
        "source_manifest": [source],
    }
    response = ledger_read_runtime.execute_read(session, pinned)

    assert (response["status"], response["reason_code"]) == (
        "REJECTED",
        "INVALID_PIN_SET",
    )
    assert response["data"] is None


@pytest.mark.parametrize("count", [1, 50])
def test_fact_ref_limit_accepts_the_frozen_boundary(tmp_path: Path, count: int) -> None:
    workspace, _, facts = _seed_workspace(
        tmp_path,
        chapter_count=1,
        facts_per_chapter=50,
    )
    session = ledger_read_runtime.open_current_reader_session(workspace, _trusted())
    refs = [fact["id"] for fact in facts[:count]]
    response = ledger_read_runtime.execute_read(
        session,
        _request(
            session,
            f"REQ-LIMIT-{count}",
            "get_ledger_entries_by_ref",
            {"ledger_name": "事实账", "read_profile": "fact_record", "refs": refs},
        ),
    )

    assert response["status"] == "OK"
    assert response["limits"]["business_items"] == count
    assert response["limits"]["truncated"] is False
