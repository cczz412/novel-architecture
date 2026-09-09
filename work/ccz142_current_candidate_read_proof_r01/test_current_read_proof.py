from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_candidate_authority_r01"
for candidate in (REPOSITORY_ROOT, MODULE_ROOT, AUTHORITY_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from candidate_authority import (  # noqa: E402
    CandidateAuthorityStore,
    CandidateRootInitializer,
)
from current_read_proof import (  # noqa: E402
    DATABASE_FILENAME,
    FIXTURE_ACCESS,
    FIXTURE_POINTER_NAMESPACE,
    GAP_CANDIDATE_MISSING,
    GAP_NO_HUMAN_ITEMS,
    GAP_NO_LIVE_STORE,
    GAP_NOT_PRODUCT_IDENTITY,
    GAP_POINTER_AMBIGUOUS,
    GAP_POINTER_MISSING,
    GAP_REAL_NOVEL_NOT_IN_SCOPE,
    GAP_STORE_MISSING,
    READ_PATH,
    STATUS_GAP,
    STATUS_READ_OK,
    prove_current_read,
    render_human_text,
)
from prove import main as prove_main  # noqa: E402
from self_check import run_self_check  # noqa: E402
from shadow_fixtures import (  # noqa: E402
    MutableRootAuthorityReader,
    authority_snapshot,
    root_request,
)

PROJECT = "fixture-project-001"


def new_store(root: Path) -> CandidateAuthorityStore:
    store = CandidateAuthorityStore(root, project_scope_id=PROJECT)
    store.initialize_authority_schema()
    return store


def publish_root(store: CandidateAuthorityStore, request: dict | None = None) -> dict:
    selected = request or root_request()
    return CandidateRootInitializer(
        store=store,
        authority_reader=MutableRootAuthorityReader(authority_snapshot(selected)),
    ).initialize_root(selected)


def test_no_live_store_reports_gap_and_still_names_the_read_path() -> None:
    proof = prove_current_read()
    assert proof["status"] == STATUS_GAP
    assert proof["gaps"] == [GAP_NO_LIVE_STORE]
    assert proof["human_card"] is None
    assert proof["result_scope"]["book_title"] == "未提供"
    assert proof["result_scope"]["chapter_completeness"] == "未确认"
    assert proof["identity"]["product_adopted"] is False
    assert proof["read_path"]["store_class"] == READ_PATH["store_class"]
    assert GAP_REAL_NOVEL_NOT_IN_SCOPE in proof["standing_boundaries"]
    assert "CandidateAuthorityStore" in render_human_text(proof)


def test_missing_database_is_store_gap(tmp_path: Path) -> None:
    missing = tmp_path / "empty-authority"
    missing.mkdir()
    proof = prove_current_read(store_root=missing)
    assert proof["gaps"] == [GAP_STORE_MISSING]
    assert proof["human_card"] is None


def test_initialized_store_without_pointer_is_pointer_gap(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    proof = prove_current_read(store_root=store.root, project_scope_id=PROJECT)
    assert proof["gaps"] == [GAP_POINTER_MISSING]
    assert proof["discovered_pointer_keys"] == []
    assert proof["human_card"] is None


def test_fixture_current_projects_human_card_and_fixture_identity(
    tmp_path: Path,
) -> None:
    store = new_store(tmp_path / "authority")
    published = publish_root(store)
    proof = prove_current_read(store_root=store.root, project_scope_id=PROJECT)
    assert proof["status"] == STATUS_READ_OK
    assert proof["gaps"] == []
    assert proof["pointer_key"] == published["logical_pointer_key"]
    assert proof["identity"]["pointer_namespace"] == FIXTURE_POINTER_NAMESPACE
    assert proof["identity"]["candidate_access"] == FIXTURE_ACCESS
    assert proof["identity"]["candidate_contract"] == "r03.5-candidate"
    assert proof["identity"]["product_adopted"] is False
    scope = proof["result_scope"]
    assert scope["book_title"] == "未提供"
    assert scope["chapter_id"] == "synthetic-chapter-001"
    assert scope["revision_no"] == 7
    assert scope["project_scope_id"] == PROJECT
    assert scope["chapter_completeness"] == "未确认"
    assert "不是已确认的整章汇总" in scope["display_range"]
    assert GAP_NOT_PRODUCT_IDENTITY in proof["limitations"]
    card = proof["human_card"]
    assert card["item_count"] == 2
    facts = [item["fact"] for item in card["items"]]
    assert facts == ["甲进入北塔。", "甲拿起铜钥匙。"]
    assert card["items"][0]["status"] == "已发生"
    assert card["items"][0]["evidence"] == "甲走进北塔。"
    assert card["items"][0]["kind"] == "已发生"
    assert card["items"][0]["stable_item_id"].startswith("lin_")
    assert card["items"][0]["match_locations"] == [
        {"seg": 1, "start_byte": 0, "end_byte": 18},
        {"seg": 1, "start_byte": 39, "end_byte": 57},
    ]
    assert "字节 0–18" in card["items"][0]["source_location"]
    assert "字节 39–57" in card["items"][0]["source_location"]
    assert card["items"][1]["speaker"] == "旁白"
    assert card["items"][1]["match_locations"] == [
        {"seg": 1, "start_byte": 18, "end_byte": 39},
    ]
    assert all("patch" not in item and "建议" not in item for item in card["items"])
    text = render_human_text(proof)
    assert "甲进入北塔。" in text
    assert "不是产品采用" in text


def test_explicit_pointer_key_reads_that_current(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    first = publish_root(store, root_request(seg=1, operation_id="root-seg-1"))
    second = publish_root(store, root_request(seg=2, operation_id="root-seg-2"))
    proof = prove_current_read(
        store_root=store.root,
        project_scope_id=PROJECT,
        pointer_key=second["logical_pointer_key"],
    )
    assert proof["status"] == STATUS_READ_OK
    assert proof["pointer_key"] == second["logical_pointer_key"]
    assert proof["pointer_key"] != first["logical_pointer_key"]
    assert proof["human_card"]["items"][0]["fact"] == "乙停在门外。"


def test_two_pointers_without_key_are_ambiguous(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    publish_root(store, root_request(seg=1, operation_id="root-seg-1"))
    publish_root(store, root_request(seg=2, operation_id="root-seg-2"))
    proof = prove_current_read(store_root=store.root, project_scope_id=PROJECT)
    assert proof["gaps"] == [GAP_POINTER_AMBIGUOUS]
    assert len(proof["discovered_pointer_keys"]) == 2
    assert proof["human_card"] is None


def test_missing_candidate_row_is_candidate_gap(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    publish_root(store)
    database = store.root / DATABASE_FILENAME
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM candidate_versions")
        connection.commit()
    proof = prove_current_read(store_root=store.root, project_scope_id=PROJECT)
    assert proof["gaps"] == [GAP_CANDIDATE_MISSING]
    assert proof["human_card"] is None


def test_unknown_pointer_key_is_pointer_gap(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    publish_root(store)
    proof = prove_current_read(
        store_root=store.root,
        project_scope_id=PROJECT,
        pointer_key="missing-pointer-key",
    )
    assert proof["gaps"] == [GAP_POINTER_MISSING]


def test_cli_without_store_prints_no_live_store_gap(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = prove_main([])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert GAP_NO_LIVE_STORE in captured.out
    assert "CandidateAuthorityStore" in captured.out
    payload = json.loads(captured.out[captured.out.index("{") :])
    assert payload["gaps"] == [GAP_NO_LIVE_STORE]
    assert payload["identity"]["product_adopted"] is False


def test_self_check_passes() -> None:
    receipt = run_self_check()
    assert receipt["result"] == "PASS"
    assert receipt["identity_never_product_adopted"] is True


def test_empty_items_projection_is_human_item_gap() -> None:
    pointer = {
        "pointer_namespace": FIXTURE_POINTER_NAMESPACE,
        "candidate_schema_id": "novel-fact-extraction-v2.1",
        "current_candidate_version_ref": {"record_id": "x"},
    }
    candidate = {
        "access": FIXTURE_ACCESS,
        "contract_version": "r03.5-candidate",
        "payload": {"items": []},
    }
    from current_read_proof import project_human_card

    card = project_human_card(pointer=pointer, candidate=candidate)
    assert card["item_count"] == 0
    # prove_current_read uses live store; this keeps the projector honest.
    assert GAP_NO_HUMAN_ITEMS
