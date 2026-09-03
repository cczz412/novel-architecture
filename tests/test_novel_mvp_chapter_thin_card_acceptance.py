from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "novel-mvp" / "contracts"
MODULE_PATH = CONTRACTS / "validate_chapter_thin_card_acceptance.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "chapter_thin_card_acceptance",
        MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_module()


def _fixtures() -> list[dict]:
    return validator.load_fixtures()


def _fixture(case_id: str) -> dict:
    return next(row for row in _fixtures() if row["case_id"] == case_id)


def test_schema_and_fixture_inventory_are_frozen() -> None:
    assert validator.SCHEMA["title"] == (
        "CHAPTER_THIN_CARD_ACCEPTANCE contract family v1"
    )
    assert [row["$ref"] for row in validator.SCHEMA["oneOf"]] == [
        "#/$defs/acceptance_case",
        "#/$defs/suite_receipt",
    ]
    fixtures = _fixtures()
    assert len(fixtures) == 24
    assert len({row["case_id"] for row in fixtures}) == 24
    assert [row["scenario_id"] for row in fixtures[:12]] == list(validator.SCENARIO_IDS)
    assert [row["scenario_id"] for row in fixtures[12:]] == list(validator.SCENARIO_IDS)
    assert validator.validate_all_fixtures() == {
        validator.ACCEPTANCE_PASS: 12,
        validator.ACCEPTANCE_REJECTED: 12,
    }


@pytest.mark.parametrize("recipe", _fixtures(), ids=lambda row: row["case_id"])
def test_each_fixture_has_the_declared_result(recipe: dict) -> None:
    assert validator.validate_fixture_case(recipe) == recipe["expected_result"]


@pytest.mark.parametrize(
    "recipe",
    [row for row in _fixtures() if row["expected_result"] == "ACCEPTANCE_REJECTED"],
    ids=lambda row: row["case_id"],
)
def test_each_negative_variant_hits_its_declared_error(recipe: dict) -> None:
    assert (
        validator.fixture_error_code(recipe)
        == validator.EXPECTED_ERROR_CODES[recipe["mutation"]]
    )


@pytest.mark.parametrize("scenario_id", validator.SCENARIO_IDS)
def test_each_scenario_runs_its_field_level_assertions(scenario_id: str) -> None:
    observed = validator.SCENARIO_RUNNERS[scenario_id]()
    assert observed == validator.SCENARIOS[scenario_id]["assertion_ids"]
    assert len(observed) >= 2
    assert len(observed) == len(set(observed))


def test_a04_preserves_one_task_no_match_without_a_fake_fact() -> None:
    bundle = validator._thin_bundle("CTC-VALID-08")
    task = bundle["task_bundle"]["task"]
    payload = bundle["artifact"]["compiled_payload"]

    assert task["selected_fact_refs"] == []
    assert not any(
        row["need_id"].startswith("NEED-FACT-") for row in task["c9_source_needs"]
    )
    task_results = [
        row
        for row in payload["version_manifest"]
        if row["binding_kind"] == "TASK_SOURCE_RESULT"
    ]
    no_match = [row for row in payload["source_results"] if row["state"] == "NO_MATCH"]
    fake_owner = [
        row
        for row in payload["version_manifest"]
        if row["material_role"] == "FACT_EXPRESSION"
        and row["binding_kind"] == "OWNER_PROOF"
    ]
    assert len(task_results) == 1
    assert len(no_match) == 1
    assert no_match[0]["reason_code"] == "NO_MATCHING_ENTRIES"
    assert fake_owner == []


def test_a05_keeps_untracked_distinct_and_does_not_invent_a_version() -> None:
    bundle = validator._custom_bundle(
        outcome_status="NOT_ATTEMPTED",
        outcome_reason="UNTRACKED",
        artifact_kind="ADMISSION",
    )
    card = bundle["thin_card"]
    rows = [
        row
        for row in card["compiled_payload"]["source_results"]
        if row["state"] == "UNTRACKED"
    ]
    assert rows == [
        {
            "result_id": rows[0]["result_id"],
            "material_role": rows[0]["material_role"],
            "state": "UNTRACKED",
            "reason_code": "UNTRACKED",
            "identity_disclosure": {"mode": "NOT_AVAILABLE"},
        }
    ]
    assert bundle["artifact"]["status"] == "ADMITTED_WITH_GAPS"


def test_a06_unauthorized_twins_have_the_same_visible_failure() -> None:
    left = validator._custom_bundle(
        outcome_status="REJECTED",
        outcome_reason="UNAUTHORIZED",
    )["artifact"]
    right = validator._custom_bundle(
        outcome_status="REJECTED",
        outcome_reason="UNAUTHORIZED",
    )["artifact"]
    assert left == right
    assert left["contract"] == "CHAPTER_THIN_CARD_BUILD_FAILURE"
    assert left["reason_code"] == "UNAUTHORIZED"
    visible = validator.canonical_bytes(left)
    for secret in (b"HIDDEN-BOX", b"secret_count", b"hidden_sha256"):
        assert secret not in visible


def test_a07_delegation_does_not_expand_scope_or_source_needs() -> None:
    author = validator._thin_bundle("CTC-VALID-01")
    delegated = validator._custom_bundle(task_base="delegated")
    fields = (
        "selected_storyline_ref",
        "transition_intent",
        "viewpoint_character_ref",
        "appearance_character_refs",
        "slot_ref",
        "slot_rev",
    )
    for field in fields:
        assert (
            author["task_bundle"]["task"]["scope_projection"][field]
            == (delegated["task_bundle"]["task"]["scope_projection"][field])
        )
    assert [row["need_id"] for row in author["c9_request"]["source_needs"]] == [
        row["need_id"] for row in delegated["c9_request"]["source_needs"]
    ]


def test_a08_keeps_reader_items_and_thin_card_utf8_bytes_separate() -> None:
    case = validator.materialize_acceptance_case(_fixture("A08"))
    assert case["expected"]["reader_limit"] == {
        "max_business_items": 100,
        "unit": "BUSINESS_ITEMS",
    }
    assert case["expected"]["thin_card_limit"] == {
        "max_payload_bytes": 262144,
        "unit": "CANONICAL_JSON_UTF8_BYTES",
    }
    bundle = validator._thin_bundle("CTC-VALID-11")
    card = bundle["artifact"]
    assert card["size_receipt"]["normalized_utf8_bytes"] == len(
        validator.canonical_bytes(card["compiled_payload"])
    )
    assert all(
        row["obligation_tier"] != "HARD"
        for row in card["compiled_payload"]["on_demand_layer"]
    )


def test_a10_stale_admission_cannot_mutate_the_old_card() -> None:
    bundle = validator._thin_bundle("CTC-VALID-14")
    before = validator.canonical_bytes(bundle["thin_card"])
    admission = bundle["artifact"]
    assert admission["status"] == "STOPPED"
    assert admission["reason_codes"] == ["SOURCE_ADVANCED"]
    assert admission["recompile_required"] is True
    assert validator.canonical_bytes(bundle["thin_card"]) == before


def test_a11_success_and_failure_objects_are_mutually_exclusive() -> None:
    for case_id in ("CTC-VALID-16", "CTC-VALID-17", "CTC-VALID-18"):
        failure = validator._thin_bundle(case_id)["artifact"]
        assert failure["contract"] == "CHAPTER_THIN_CARD_BUILD_FAILURE"
        assert failure["status"] == "STOPPED"
        assert "thin_card_id" not in failure
        assert "compiled_payload" not in failure


def test_a12_test_only_rowset_roundtrip_preserves_types_and_array_order() -> None:
    value = {
        "none": None,
        "boolean": True,
        "integer": 3,
        "number": 1.5,
        "string": "合成文本",
        "array": ["A", 2, False],
        "object": {"state": "NO_MATCH"},
    }
    rows = validator.flatten_logical_rowset(value)
    assert validator.restore_logical_rowset(rows) == value
    assert {row["value_type"] for row in rows} >= {
        "NULL",
        "BOOLEAN",
        "INTEGER",
        "NUMBER",
        "STRING",
        "ARRAY",
        "OBJECT",
    }
    assert [
        row["array_index"]
        for row in rows
        if row["path"] in {"/array/0", "/array/1", "/array/2"}
    ] == [0, 1, 2]


def test_suite_receipt_is_canonical_and_reports_zero_external_calls() -> None:
    receipt = validator.build_suite_receipt()
    assert validator.validate_suite_receipt(receipt) == validator.ACCEPTANCE_PASS
    assert receipt["status"] == "PASS"
    assert receipt["scenario_ids"] == list(validator.SCENARIO_IDS)
    assert len(receipt["case_results"]) == 12
    assert len(receipt["negative_variant_results"]) == 12
    assert receipt["call_counts"] == validator.ZERO_CALL_COUNTS
    unhashed = copy.deepcopy(receipt)
    observed = unhashed.pop("receipt_sha256")
    assert observed == validator.sha256_json(unhashed)


def test_validator_does_not_import_runtime_network_model_or_database_clients() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(
        {
            "requests",
            "httpx",
            "socket",
            "sqlite3",
            "sqlalchemy",
            "psycopg",
            "openai",
        }
    )


def test_contract_text_keeps_test_only_and_runtime_boundaries_explicit() -> None:
    text = (CONTRACTS / "CHAPTER_THIN_CARD_ACCEPTANCE.md").read_text(encoding="utf-8")
    for phrase in (
        "CANDIDATE_LOGICAL_ROWSET__TEST_ONLY",
        "100 条",
        "262144 UTF-8 bytes",
        "不是数据库 Schema",
        "不接真实 reader",
        "不接真实 C9",
        "不证明真实小说取件准确率",
        "来源：Codex",
    ):
        assert phrase in text


def test_validator_cli_emits_the_suite_summary() -> None:
    completed = subprocess.run(
        [sys.executable, str(MODULE_PATH)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["status"] == "PASS"
    assert payload["scenario_ids"] == list(validator.SCENARIO_IDS)
    assert payload["counts"] == {
        validator.ACCEPTANCE_PASS: 12,
        validator.ACCEPTANCE_REJECTED: 12,
    }
    assert payload["call_counts"] == validator.ZERO_CALL_COUNTS
