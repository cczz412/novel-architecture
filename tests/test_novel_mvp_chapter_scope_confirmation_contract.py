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
MODULE_PATH = CONTRACTS / "validate_chapter_scope_confirmation.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "chapter_scope_confirmation", MODULE_PATH
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


def _document(case_id: str) -> dict:
    return validator.materialize_fixture_case(_case(case_id))["document"]


def test_schema_and_fixture_inventory_are_frozen() -> None:
    assert validator.SCHEMA["title"] == "CHAPTER_SCOPE_CONFIRMATION v1"
    cases = _cases()
    assert len(cases) == 36
    assert len({row["case_id"] for row in cases}) == len(cases)
    assert validator.validate_all_fixtures() == {
        validator.STRUCTURAL_VALID: 11,
        validator.STRUCTURAL_INVALID: 25,
    }


@pytest.mark.parametrize("case", _cases(), ids=lambda row: row["case_id"])
def test_each_fixture_has_the_declared_result(case: dict) -> None:
    assert validator.validate_fixture_case(case) == case["expected_result"]


def test_all_four_transition_intents_are_real_confirmed_examples() -> None:
    case_ids = (
        "CSC-VALID-01",
        "CSC-VALID-02",
        "CSC-VALID-03",
        "CSC-VALID-04",
    )
    actual = {
        _document(case_id)["selection"]["transition_intent"]
        for case_id in case_ids
    }
    assert actual == set(validator.TRANSITION_INTENTS)


def test_only_confirmed_current_shape_exposes_ccz139_handoff() -> None:
    confirmed = _document("CSC-VALID-01")
    handoff = confirmed["ccz139_handoff"]
    assert handoff == validator._handoff_for(confirmed)
    assert handoff["target"] == "CCZ-139"

    for case_id in (
        "CSC-VALID-07",
        "CSC-VALID-08",
        "CSC-VALID-09",
        "CSC-VALID-10",
        "CSC-VALID-11",
    ):
        assert _document(case_id)["ccz139_handoff"] is None


def test_selection_is_a_projection_of_current_candidates() -> None:
    document = _document("CSC-VALID-02")
    selection = document["selection"]
    assert selection["selected_storyline_ref"] == "LINE-0002"
    assert selection["viewpoint_character_ref"] == "CHAR-0002"
    assert selection["viewpoint_character_ref"] in selection[
        "appearance_character_refs"
    ]
    assert selection["selected_basis_refs"] == [
        "BASIS-LINE-0002",
        "BASIS-CHAR-0002",
        "BASIS-CHAR-0003",
    ]


def test_delegated_confirmation_is_bounded_by_trusted_snapshot_summary() -> None:
    document = _document("CSC-VALID-05")
    confirmation = document["confirmation"]
    permission = confirmation["permission_snapshot_ref"]
    assert confirmation["mode"] == "DELEGATED_CONFIRMED"
    assert confirmation["actor_id"] == permission["delegate_actor_id"]
    assert set(validator._selected_refs(document["selection"])).issubset(
        permission["allowed_scope_refs"]
    )

    narrowed = copy.deepcopy(document)
    narrowed["confirmation"]["permission_snapshot_ref"][
        "allowed_scope_refs"
    ] = [document["selection"]["selected_storyline_ref"]]
    narrowed = validator.seal_document(narrowed)
    with pytest.raises(
        validator.ContractError,
        match="PERMISSION_SELECTION_SCOPE_NOT_COVERED",
    ):
        validator.validate_scope_confirmation(narrowed)


def test_new_selection_and_old_history_are_two_distinct_objects() -> None:
    new = _document("CSC-VALID-06")
    old = _document("CSC-VALID-08")
    assert new["scope_id"] == "SCOPE-0002"
    assert new["supersedes_scope_id"] == old["scope_id"]
    assert old["superseded_by_scope_id"] == new["scope_id"]
    assert new["status"] == "CONFIRMED"
    assert old["status"] == "SUPERSEDED"
    assert old["selection"] is not None
    assert old["confirmation"] is not None
    assert old["ccz139_handoff"] is None


def test_unauthorized_stop_does_not_leak_candidate_inventory() -> None:
    document = _document("CSC-VALID-11")
    assert document["status"] == "STOPPED"
    assert document["reason_code"] == "UNAUTHORIZED"
    assert document["candidate_basis"] == {
        "storyline_candidates": [],
        "character_candidates": [],
    }
    assert document["selection"] is None
    assert document["confirmation"] is None


def test_scope_hash_is_stable_and_covers_business_fields() -> None:
    document = _document("CSC-VALID-01")
    assert validator.seal_document(document) == document
    changed = copy.deepcopy(document)
    changed["task_ref"]["object_revision"] += 1
    changed = validator.seal_document(changed)
    assert changed["scope_basis_sha256"] != document["scope_basis_sha256"]
    assert changed["ccz139_handoff"]["scope_basis_sha256"] == changed[
        "scope_basis_sha256"
    ]


def test_schema_and_fixture_files_are_parseable() -> None:
    schema = json.loads(
        (CONTRACTS / "CHAPTER_SCOPE_CONFIRMATION.schema.json").read_text(
            encoding="utf-8"
        )
    )
    fixtures = [
        json.loads(line)
        for line in (
            CONTRACTS / "CHAPTER_SCOPE_CONFIRMATION.fixtures.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert schema["$schema"].endswith("2020-12/schema")
    assert len(fixtures) == 36


def test_contract_text_keeps_ownership_and_runtime_boundaries_explicit() -> None:
    text = (CONTRACTS / "CHAPTER_SCOPE_CONFIRMATION.md").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "CONTRACT_ONLY__NO_RUNTIME_OR_UI_AUTHORIZED",
        "不创建故事线、人物、章槽、权限快照或 Focus",
        "不能自行读取 current",
        "不定义 CCZ-139 的事实筛选",
        "不能冒充运行时权限通过",
    ):
        assert phrase in text


def test_cli_reports_zero_external_calls() -> None:
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
        "contract": "CHAPTER_SCOPE_CONFIRMATION",
        "current_owner_resolution_performed": False,
        "model_calls": 0,
        "network_calls": 0,
        "permission_evaluation_performed": False,
        "status": "PASS",
        "version": "v1",
        "counts": {
            validator.STRUCTURAL_INVALID: 25,
            validator.STRUCTURAL_VALID: 11,
        },
    }
