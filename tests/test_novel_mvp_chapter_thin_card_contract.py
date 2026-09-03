from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "novel-mvp" / "contracts"
MODULE_PATH = CONTRACTS / "validate_chapter_thin_card.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("chapter_thin_card", MODULE_PATH)
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


def _card(case_id: str) -> dict:
    artifact = _bundle(case_id)["artifact"]
    assert artifact["contract"] == "CHAPTER_THIN_CARD"
    return artifact


def test_schema_and_fixture_inventory_are_frozen() -> None:
    assert validator.SCHEMA["title"] == "CHAPTER_THIN_CARD contract family v1"
    assert [row["$ref"] for row in validator.SCHEMA["oneOf"]] == [
        "#/$defs/thin_card",
        "#/$defs/admission_receipt",
        "#/$defs/build_failure",
    ]
    cases = _cases()
    assert len(cases) == 65
    assert len({row["case_id"] for row in cases}) == len(cases)
    assert validator.validate_all_fixtures() == {
        validator.STRUCTURAL_VALID: 18,
        validator.STRUCTURAL_INVALID: 47,
    }


@pytest.mark.parametrize("case", _cases(), ids=lambda row: row["case_id"])
def test_each_fixture_has_the_declared_result(case: dict) -> None:
    assert validator.validate_fixture_case(case) == case["expected_result"]


@pytest.mark.parametrize(
    "case",
    [row for row in _cases() if row["expected_result"] == "STRUCTURAL_INVALID"],
    ids=lambda row: row["case_id"],
)
def test_each_invalid_fixture_hits_its_intended_guard(case: dict) -> None:
    assert validator.fixture_error_code(case) == validator.EXPECTED_ERROR_CODES[
        case["mutation"]
    ]


def test_scope_and_source_needs_are_only_projected_from_ccz139_and_c9() -> None:
    bundle = _bundle("CTC-VALID-01")
    task = bundle["task_bundle"]["task"]
    card = bundle["artifact"]
    assert card["scope_projection"] == task["scope_projection"]
    assert bundle["c9_request"]["source_needs"] == task["c9_source_needs"]
    assert card["retrieval_task_ref"] == validator._task_ref(task)
    assert card["c9_run_ref"] == validator._c9_run_ref(bundle["c9_result"])


def test_resident_layer_is_an_exact_projection_of_c9_loaded_material() -> None:
    bundle = _bundle("CTC-VALID-01")
    loaded = {
        row["need_id"]: row
        for row in bundle["c9_result"]["material_package"]["loaded"]
    }
    resident = bundle["artifact"]["compiled_payload"]["resident_layer"]
    assert [row["need_id"] for row in resident] == list(loaded)
    for row in resident:
        source = loaded[row["need_id"]]
        assert row["material_text"] == source["material_text"]
        assert row["material_sha256"] == source["material_sha256"]
        assert row["why_loaded"] == source["why_loaded"]
        assert row["obligation_tier"] == source["obligation_tier"]


@pytest.mark.parametrize("case_id", ["CTC-VALID-09", "CTC-VALID-10"])
def test_on_demand_layer_is_a_recall_directory_without_material(case_id: str) -> None:
    layer = _card(case_id)["compiled_payload"]["on_demand_layer"]
    assert layer
    for row in layer:
        assert "material_text" not in row
        assert "material_sha256" not in row
        assert row["recall_handle"]
        assert row["obligation_tier"] in {"SHOULD", "MAY"}


def test_byte_limit_demotes_optional_material_but_never_hard_material() -> None:
    card = _card("CTC-VALID-11")
    payload = card["compiled_payload"]
    receipt = card["size_receipt"]
    assert receipt["normalized_utf8_bytes"] == len(
        validator.canonical_bytes(payload)
    )
    assert receipt["normalized_utf8_bytes"] <= validator.MAX_PAYLOAD_BYTES
    assert receipt["demotions"] == [
        {
            "need_id": "NEED-BOX-OLDER",
            "from_layer": "RESIDENT",
            "to_layer": "ON_DEMAND",
            "reason_code": "THIN_CARD_BYTE_LIMIT",
        }
    ]
    assert all(
        row["obligation_tier"] == "HARD" for row in payload["resident_layer"]
    )


def test_empty_no_match_and_unavailable_remain_different_source_results() -> None:
    expected = {
        "CTC-VALID-06": ("UNAVAILABLE", "NOT_AVAILABLE"),
        "CTC-VALID-07": ("EMPTY", "DISCLOSED"),
        "CTC-VALID-08": ("NO_MATCH", "DISCLOSED"),
    }
    for case_id, pair in expected.items():
        results = _card(case_id)["compiled_payload"]["source_results"]
        assert pair in {
            (row["state"], row["identity_disclosure"]["mode"])
            for row in results
        }
    assert _card("CTC-VALID-07")["compiled_payload"]["gap_summary"] == {
        "hard_gap_codes": [],
        "optional_gap_codes": [],
        "masked_access": False,
    }
    assert _card("CTC-VALID-08")["compiled_payload"]["gap_summary"] == {
        "hard_gap_codes": [],
        "optional_gap_codes": [],
        "masked_access": False,
    }


def test_character_current_definition_and_story_time_slice_are_separate() -> None:
    view = _card("CTC-VALID-01")["compiled_payload"]["character_views"][0]
    current = view["character_current_definition"]
    story = view["character_story_time_slice"]
    assert current["source_version_ref"] != story["source_version_ref"]
    assert current["time_anchor_ref"] != story["time_anchor_ref"]


def test_plan_previous_commit_and_workspace_delta_keep_distinct_actuality() -> None:
    payload = _card("CTC-VALID-01")["compiled_payload"]
    assert payload["current_chapter_plan_snapshot"]["actuality_class"] == (
        "PLANNED_TARGET"
    )
    assert payload["previous_chapter_committed_snapshot"]["actuality_class"] == (
        "COMMITTED_TRUTH"
    )
    assert {
        row["actuality_class"] for row in payload["uncommitted_workspace_delta_refs"]
    } == {"UNCOMMITTED_WORKSPACE"}
    assert (
        _card("CTC-VALID-05")["compiled_payload"][
            "previous_chapter_committed_snapshot"
        ]
        is None
    )


def test_version_manifest_covers_all_five_material_roles_one_generation() -> None:
    manifest = _card("CTC-VALID-01")["compiled_payload"]["version_manifest"]
    assert {row["material_role"] for row in manifest} == {
        "SOURCE_TEXT",
        "FACT_EXPRESSION",
        "FORMAL_LEDGER_STATE",
        "CHAPTER_TARGET",
        "DERIVED_ARTIFACT",
    }
    assert len({row["storage_generation"] for row in manifest}) == 1


def test_admission_rechecks_currentness_without_rewriting_the_thin_card() -> None:
    admitted = _bundle("CTC-VALID-12")
    stale = _bundle("CTC-VALID-14")
    revoked = _bundle("CTC-VALID-15")
    assert admitted["thin_card"] == stale["thin_card"] == revoked["thin_card"]
    assert admitted["artifact"]["status"] == "ADMITTED"
    assert stale["artifact"]["status"] == "STOPPED"
    assert stale["artifact"]["reason_codes"] == ["SOURCE_ADVANCED"]
    assert stale["artifact"]["recompile_required"] is True
    assert revoked["artifact"]["status"] == "STOPPED"
    assert revoked["artifact"]["reason_codes"] == ["PERMISSION_REVOKED"]
    assert revoked["artifact"]["recompile_required"] is False


def test_admission_requires_nine_unique_checks_with_truthful_fingerprints() -> None:
    receipt = _bundle("CTC-VALID-12")["artifact"]
    assert len(receipt["checks"]) == 9
    assert {row["check_kind"] for row in receipt["checks"]} == (
        validator.ADMISSION_CHECK_KINDS
    )
    for row in receipt["checks"]:
        assert row["observed_state"] == "MATCH"
        assert row["disclosure"]["expected_sha256"] == (
            row["disclosure"]["observed_sha256"]
        )
    assert validator.fixture_error_code(_case("CTC-INVALID-43")) == "SCHEMA_INVALID"
    assert validator.fixture_error_code(_case("CTC-INVALID-44")) == (
        "ADMISSION_CHECK_KIND_SET_INVALID"
    )
    assert validator.fixture_error_code(_case("CTC-INVALID-45")) == (
        "ADMISSION_EXPECTED_FINGERPRINT_MISMATCH"
    )
    assert validator.fixture_error_code(_case("CTC-INVALID-46")) == (
        "ADMISSION_MATCH_FINGERPRINT_MISMATCH"
    )
    assert validator.fixture_error_code(_case("CTC-INVALID-47")) == (
        "ADMISSION_CURRENT_PROOF_SCHEMA_INVALID"
    )


def test_permission_revocation_masks_identity() -> None:
    receipt = _bundle("CTC-VALID-15")["artifact"]
    permission = next(
        row for row in receipt["checks"] if row["check_kind"] == "PERMISSION_CURRENT"
    )
    assert permission["observed_state"] == "REVOKED"
    assert permission["disclosure"] == {"mode": "MASKED"}


def test_build_failures_do_not_masquerade_as_thin_cards() -> None:
    unsupported = _bundle("CTC-VALID-16")["artifact"]
    damaged = _bundle("CTC-VALID-17")["artifact"]
    hard_missing = _bundle("CTC-VALID-18")["artifact"]
    assert unsupported["reason_code"] == "UNSUPPORTED_VERSION"
    assert damaged["reason_code"] == "SOURCE_CORRUPTED"
    assert hard_missing["reason_code"] == "REQUIRED_SOURCE_UNAVAILABLE"
    assert _bundle("CTC-VALID-18")["c9_result"]["status"] == "READY_WITH_GAPS"
    for failure in (unsupported, damaged, hard_missing):
        assert failure["contract"] == "CHAPTER_THIN_CARD_BUILD_FAILURE"
        assert failure["status"] == "STOPPED"
        assert "thin_card_id" not in failure
        assert "compiled_payload" not in failure


def test_hashes_bind_the_canonical_payload_and_whole_card() -> None:
    card = _card("CTC-VALID-01")
    assert card["compiled_payload_sha256"] == validator.sha256_json(
        card["compiled_payload"]
    )
    unhashed = dict(card)
    observed = unhashed.pop("thin_card_sha256")
    assert observed == validator.sha256_json(unhashed)


def test_contract_document_keeps_the_authorized_non_runtime_boundary() -> None:
    text = (CONTRACTS / "CHAPTER_THIN_CARD.md").read_text(encoding="utf-8")
    for phrase in (
        "CONTRACT_ONLY__NO_RUNTIME_READER_C9_PACKER_DATABASE_OR_UI_AUTHORIZED",
        "不重做 CCZ-137 或 CCZ-139",
        "旧卡和旧摘要保持原样",
        "按需项不允许出现 `material_text`",
        "来源：Codex",
    ):
        assert phrase in text


def test_cli_reports_synthetic_only_pass_receipt() -> None:
    completed = subprocess.run(
        [sys.executable, str(MODULE_PATH)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    receipt = json.loads(completed.stdout)
    assert receipt["status"] == "PASS"
    assert receipt["counts"] == {
        validator.STRUCTURAL_VALID: 18,
        validator.STRUCTURAL_INVALID: 47,
    }
    assert receipt["synthetic_c9_compilation_performed"] is True
    assert {
        key: receipt[key]
        for key in (
            "real_reader_calls",
            "real_c9_calls",
            "workspace_reads",
            "network_calls",
            "model_calls",
            "database_writes",
            "ui_actions",
        )
    } == {
        "real_reader_calls": 0,
        "real_c9_calls": 0,
        "workspace_reads": 0,
        "network_calls": 0,
        "model_calls": 0,
        "database_writes": 0,
        "ui_actions": 0,
    }
