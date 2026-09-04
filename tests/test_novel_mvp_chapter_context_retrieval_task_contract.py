from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "novel-mvp" / "contracts"
MODULE_PATH = CONTRACTS / "validate_chapter_context_retrieval_task.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "chapter_context_retrieval_task", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_module()


def _cases() -> list[dict]:
    return validator.load_fixtures()


def _case(case_id: str) -> dict:
    return next(row for row in _cases() if row["case_id"] == case_id)


def _bundle(case_id: str) -> dict:
    return validator.materialize_fixture_case(_case(case_id))


def _task(case_id: str) -> dict:
    return _bundle(case_id)["task"]


def test_schema_and_fixture_inventory_are_frozen() -> None:
    assert validator.SCHEMA["title"] == "CHAPTER_CONTEXT_RETRIEVAL_TASK v1"
    cases = _cases()
    assert len(cases) == 57
    assert len({row["case_id"] for row in cases}) == len(cases)
    assert validator.validate_all_fixtures() == {
        validator.STRUCTURAL_VALID: 14,
        validator.STRUCTURAL_INVALID: 43,
    }


@pytest.mark.parametrize("case", _cases(), ids=lambda row: row["case_id"])
def test_each_fixture_has_the_declared_result(case: dict) -> None:
    assert validator.validate_fixture_case(case) == case["expected_result"]


@pytest.mark.parametrize(
    "case",
    [row for row in _cases() if row["expected_result"] == validator.STRUCTURAL_INVALID],
    ids=lambda row: row["case_id"],
)
def test_each_invalid_fixture_hits_its_intended_guard(case: dict) -> None:
    assert validator.fixture_error_code(case) == validator.EXPECTED_ERROR_CODES[
        case["mutation"]
    ]


def test_scope_confirmation_is_the_only_story_scope_input() -> None:
    bundle = _bundle("CRT-VALID-02")
    task = bundle["task"]
    scope = bundle["scope_confirmation"]
    assert task["scope_confirmation_ref"] == {
        "contract": "CHAPTER_SCOPE_CONFIRMATION",
        "version": "v1",
        "scope_id": scope["scope_id"],
        "scope_basis_sha256": scope["scope_basis_sha256"],
    }
    assert task["scope_projection"] == scope["ccz139_handoff"]
    for forbidden_duplicate in (
        "selected_storyline_ref",
        "transition_intent",
        "viewpoint_character_ref",
        "appearance_character_refs",
    ):
        assert forbidden_duplicate not in task


def test_all_four_transition_intents_come_from_ccz137_projection() -> None:
    case_ids = (
        "CRT-VALID-01",
        "CRT-VALID-02",
        "CRT-VALID-03",
        "CRT-VALID-04",
    )
    transitions = {
        _task(case_id)["scope_projection"]["transition_intent"]
        for case_id in case_ids
    }
    assert transitions == {
        "CONTINUE_CURRENT",
        "SWITCH_HARD_CUT",
        "SWITCH_SUSTAINED_BRANCH",
        "SWITCH_MAINLINE_BRIDGE",
    }


def test_previous_handoff_is_an_exact_resolved_settlement_projection() -> None:
    bundle = _bundle("CRT-VALID-01")
    task = bundle["task"]
    settlement = bundle["settlements"][0]
    previous = task["previous_chapter_handoff"]
    assert settlement["claim_kind"] == "OWNER_RESOLVED_SEALED"
    assert previous == validator._previous_projection(
        settlement, previous["c9_need_id"]
    )
    assert len(previous["ledger_coverage"]) == 10
    assert previous["unresolved_story_item_refs"] == ["USI-0001"]


def test_predecessor_binding_seals_current_and_previous_chapter_identity() -> None:
    bundle = _bundle("CRT-VALID-01")
    task = bundle["task"]
    scope = bundle["scope_confirmation"]["ccz139_handoff"]
    settlement = bundle["settlements"][0]
    binding = bundle["predecessor_binding"]
    assert task["predecessor_binding_ref"] == {
        "contract": "CHAPTER_PREDECESSOR_BINDING",
        "version": "v1",
        "binding_id": binding["binding_id"],
        "binding_basis_sha256": binding["binding_basis_sha256"],
    }
    assert binding["current_slot_ref"] == scope["slot_ref"]
    assert binding["current_slot_rev"] == scope["slot_rev"]
    assert binding["source_plan_sha256"] == scope["source_plan_sha256"]
    assert binding["previous_slot_ref"] == settlement["slot_ref"]
    assert binding["previous_settlement_sha256"] == settlement["settlement_sha256"]


def test_first_chapter_and_non_confirmed_scope_stop_are_distinct() -> None:
    first = _task("CRT-VALID-05")
    stopped = _task("CRT-VALID-14")
    first_bundle = _bundle("CRT-VALID-05")
    assert first_bundle["predecessor_binding"]["chapter_position"] == "FIRST_CHAPTER"
    assert first["previous_chapter_handoff"] is None
    assert first["status"] == "READY_FOR_THIN_CARD"
    assert stopped["status"] == "STOPPED"
    assert stopped["reason_code"] == "SCOPE_NOT_CONFIRMED"
    assert stopped["scope_projection"] is None
    assert stopped["c9_source_needs"] == []


def test_selected_fact_is_only_a_ref_to_an_opened_ok_response() -> None:
    bundle = _bundle("CRT-VALID-07")
    task = bundle["task"]
    response = bundle["ledger_responses"][0]
    fact = task["selected_fact_refs"][0]
    source_entry = response["receipt"]["source_manifest"][0]
    assert response["status"] == "OK"
    assert response["limits"]["truncated"] is False
    assert fact["fact_ref"] == response["data"]["entries"][0]["id"]
    assert fact["fact_revision"] == source_entry["revision"]
    assert fact["fact_sha256"] == source_entry["logical_content_sha256"]
    assert set(fact["selection_basis_refs"]) == {
        task["scope_confirmation_ref"]["scope_id"],
        response["request_id"],
    }
    assert "text" not in fact
    assert "quote" not in fact


def test_legal_empty_does_not_invent_a_fact_or_claim_failure() -> None:
    bundle = _bundle("CRT-VALID-06")
    task = bundle["task"]
    response = bundle["ledger_responses"][0]
    assert (response["status"], response["reason_code"]) == (
        "EMPTY",
        "NO_MATCHING_ENTRIES",
    )
    assert task["selected_fact_refs"] == []
    assert task["status"] == "READY_FOR_THIN_CARD"


def test_optional_capability_gap_is_visible_but_not_blocking() -> None:
    task = _task("CRT-VALID-08")
    box = next(row for row in task["box_directory"] if row["box_id"] == "BOX-CHARACTER")
    assert task["status"] == "READY_WITH_GAPS"
    assert task["reason_code"] == "OPTIONAL_SOURCES_UNAVAILABLE"
    assert task["read_coverage"]["complete_for_required"] is True
    assert box["availability"] == "CAPABILITY_UNAVAILABLE"
    assert box["obligation_tier"] == "SHOULD"
    assert box["logical_open_ref"] is None
    assert box["c9_need_ids"] == []


def test_hard_capability_gap_stops_without_executable_material() -> None:
    bundle = _bundle("CRT-VALID-13")
    task = bundle["task"]
    assert bundle["predecessor_binding"]["chapter_position"] == "CONTINUING_CHAPTER"
    assert task["previous_chapter_handoff"] is not None
    assert task["previous_chapter_handoff"]["c9_need_id"] is None
    assert task["status"] == "STOPPED"
    assert task["reason_code"] == "REQUIRED_SOURCE_UNAVAILABLE"
    assert task["read_coverage"]["complete_for_required"] is False
    assert task["read_coverage"]["missing_required_box_ids"] == [
        "BOX-CHARACTER"
    ]
    assert task["selected_fact_refs"] == []
    assert task["c9_source_needs"] == []
    assert task["box_directory"][0]["source_id"] is None
    assert task["box_directory"][0]["logical_open_ref"] is None


def test_directory_only_box_contains_an_entry_not_material() -> None:
    task = _task("CRT-VALID-09")
    box = task["box_directory"][0]
    assert box["availability"] == "DIRECTORY_ONLY"
    assert box["logical_open_ref"] == "SUMMARY-PHASE-0001"
    assert box["c9_need_ids"] == ["NEED-BOX-OLDER"]
    for forbidden in ("content", "material_text", "body", "chapter_text"):
        assert forbidden not in box


def test_three_level_evidence_chain_never_escalates_obligation() -> None:
    task = _task("CRT-VALID-10")
    need_map = {row["need_id"]: row for row in task["c9_source_needs"]}
    fact = need_map["NEED-FACT-f0001"]
    formation = need_map["NEED-FORMATION"]
    original = need_map["NEED-ORIGINAL"]
    assert [
        fact["evidence_layer"],
        formation["evidence_layer"],
        original["evidence_layer"],
    ] == ["LEDGER_OBJECT", "FORMATION_BASIS", "ORIGINAL_EVIDENCE"]
    assert formation["parent_need_id"] == fact["need_id"]
    assert original["parent_need_id"] == formation["need_id"]
    assert [
        fact["obligation_tier"],
        formation["obligation_tier"],
        original["obligation_tier"],
    ] == ["HARD", "SHOULD", "MAY"]


def test_every_task_material_maps_to_exactly_one_c9_need() -> None:
    task = _task("CRT-VALID-12")
    expected = {
        task["previous_chapter_handoff"]["c9_need_id"]
    } - {None}
    expected.update(row["c9_need_id"] for row in task["selected_fact_refs"])
    for box in task["box_directory"]:
        expected.update(box["c9_need_ids"])
    actual = {row["need_id"] for row in task["c9_source_needs"]}
    assert actual == expected
    assert len(actual) == len(task["c9_source_needs"])


def test_author_and_delegated_confirmation_keep_the_same_task_scope_shape() -> None:
    author = _task("CRT-VALID-01")["scope_projection"]
    delegated = _task("CRT-VALID-11")["scope_projection"]
    for key in (
        "selected_storyline_ref",
        "transition_intent",
        "viewpoint_character_ref",
        "appearance_character_refs",
        "slot_ref",
        "slot_rev",
    ):
        assert delegated[key] == author[key]


def test_task_hash_is_stable_and_covers_business_fields() -> None:
    task = _task("CRT-VALID-01")
    assert validator.seal_task(task) == task
    changed = copy.deepcopy(task)
    changed["selected_fact_refs"][0]["fact_summary"] = "另一条合成任务摘要。"
    changed = validator.seal_task(changed)
    assert changed["task_basis_sha256"] != task["task_basis_sha256"]


def test_schema_and_fixture_files_are_parseable() -> None:
    schema = json.loads(
        (CONTRACTS / "CHAPTER_CONTEXT_RETRIEVAL_TASK.schema.json").read_text(
            encoding="utf-8"
        )
    )
    fixtures = [
        json.loads(line)
        for line in (
            CONTRACTS / "CHAPTER_CONTEXT_RETRIEVAL_TASK.fixtures.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert schema["$schema"].endswith("2020-12/schema")
    assert len(fixtures) == 57


def test_contract_text_keeps_ownership_and_runtime_boundaries_explicit() -> None:
    text = (CONTRACTS / "CHAPTER_CONTEXT_RETRIEVAL_TASK.md").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "CONTRACT_ONLY__NO_SEARCH_READER_C9_OR_UI_AUTHORIZED",
        "不重做 CCZ-137",
        "不是第二份事实账",
        "不创建物理 BOX",
        "不创建完整 `C9_RETRIEVAL_REQUEST`",
        "不能证明自然语言相关性真的选得好",
    ):
        assert phrase in text


def test_cli_reports_zero_external_or_runtime_work() -> None:
    completed = subprocess.run(
        [sys.executable, str(MODULE_PATH)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    assert result == {
        "contract": "CHAPTER_CONTEXT_RETRIEVAL_TASK",
        "version": "v1",
        "status": "PASS",
        "counts": {
            validator.STRUCTURAL_VALID: 14,
            validator.STRUCTURAL_INVALID: 43,
        },
        "current_owner_resolution_performed": False,
        "semantic_search_performed": False,
        "c9_execution_performed": False,
        "workspace_reads": 0,
        "network_calls": 0,
        "model_calls": 0,
    }
