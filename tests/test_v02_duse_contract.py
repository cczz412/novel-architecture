from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_duse_contract as dc  # noqa: E402


pytestmark = pytest.mark.v02


def _built() -> dict[str, object]:
    return {
        name: (
            raw.decode("utf-8")
            if name.endswith(".md")
            else json.loads(raw.decode("utf-8"))
        )
        for name, raw in dc.build_artifacts().items()
    }


def test_a_and_b_contracts_are_separate() -> None:
    built = _built()
    metric = built["contracts/metric_contract.v1.json"]
    assert set(metric["scorecards"]) == {"D-USE-A", "D-USE-B"}
    assert metric["combined_total_accuracy_forbidden"] is True
    assert metric["formal_score_requires_question_and_answer_freeze_tickets"] is True
    assert metric["scorecards"]["D-USE-A"]["x10_x11_metrics"] == list(dc.NEW_METRICS)


def test_closed_query_has_exact_five_fields() -> None:
    schema = dc.closed_query_schema()
    assert set(schema["properties"]) == {
        "query_type",
        "entity_id",
        "state_slot",
        "as_of_chapter",
        "epistemic_owner",
    }
    assert schema["additionalProperties"] is False


def test_seven_case_kinds_are_blank_and_human_required() -> None:
    built = _built()
    bank = built["templates/question_bank.blank.json"]
    assert len(bank["rows"]) == 7
    assert {row["case_kind"] for row in bank["rows"]} == set(dc.CASE_KINDS)
    assert all(
        row["question_text"] == dc.HUMAN_REQUIRED
        and row["expected_status"] is None
        and row["expected_fact_ids"] == []
        and row["review_status"] == "HUMAN_REQUIRED"
        and row["derived_from_model_output"] is False
        for row in bank["rows"]
    )
    assert bank["formal_question_count"] == 0
    assert bank["formal_answer_count"] == 0


def test_blank_bank_is_blocked_before_freeze() -> None:
    preflight = _built()["preflight/question_freeze_preflight.json"]
    assert preflight["status"] == "HARD_STOP_HUMAN_REQUIRED"
    assert preflight["question_set_frozen"] is False
    assert preflight["seven_case_kinds_complete"] is True
    assert preflight["formal_question_count"] == 0
    assert preflight["model_api_calls"] == 0
    assert preflight["model_output_read_for_question_writing"] is False
    block = _built()["preflight/human_required_block_receipt.json"]
    assert block["required_missing_freeze_tickets"] == [
        dc.QUESTION_FREEZE_FILENAME,
        dc.ANSWER_FREEZE_FILENAME,
    ]


def test_existing_explicit_freeze_causes_hard_stop(tmp_path: Path) -> None:
    marker = tmp_path / "question_freeze_receipt.json"
    marker.write_text(
        json.dumps({"status": "QUESTION_SET_FROZEN"}),
        encoding="utf-8",
    )
    with pytest.raises(dc.ExistingQuestionFreezeError):
        dc.write_artifacts(tmp_path)
    assert list(tmp_path.iterdir()) == [marker]


def test_nonfreeze_design_files_do_not_false_positive(tmp_path: Path) -> None:
    (tmp_path / "design.json").write_text(
        json.dumps({"status": "HUMAN_REQUIRED"}),
        encoding="utf-8",
    )
    manifest = dc.write_artifacts(tmp_path)
    receipt = dc.verify_artifacts(tmp_path)
    assert manifest["status"] == "HUMAN_REQUIRED_NOT_FROZEN"
    assert receipt["status"] == "PASS_HUMAN_REQUIRED_BLOCK_ACTIVE"


def test_future_canary_is_mechanical_and_contains_no_novel_answer() -> None:
    canary = _built()["canary/future_n_plus_one_contract.json"]
    assert canary["status"] == "MECHANICAL_FIXTURE_ONLY_NOT_FORMAL_QUESTION"
    assert canary["novel_text_included"] is False
    assert canary["expected_semantic_answer_included"] is False


def test_outputs_do_not_contain_absolute_path_or_formal_answer() -> None:
    raw = b"\n".join(dc.build_artifacts().values())
    assert b"/Users/a1234/" not in raw
    assert b'"formal_scores_emitted": true' not in raw
    assert b'"question_set_frozen": true' not in raw
    assert b'"derived_from_model_output": true' not in raw


def _built_c11() -> dict[str, object]:
    return {
        name: (
            raw.decode("utf-8")
            if name.endswith(".md")
            else json.loads(raw.decode("utf-8"))
        )
        for name, raw in dc.build_c11_question_expansion_artifacts().items()
    }


def test_c11_question_family_is_independent_dimension() -> None:
    built = _built_c11()
    catalog = built["catalog/question_family_catalog.json"]
    assert catalog["dimension_name"] == "question_family"
    assert catalog["independent_from"] == ["query_type", "case_kind"]
    assert catalog["research_family_count"] == 6
    assert catalog["product_family_count"] == 3
    assert len(catalog["rows"]) == 9
    assert {row["question_family"] for row in catalog["rows"]} == set(
        dc.QUESTION_FAMILIES
    )
    assert catalog["executable_query_types_unchanged"] == list(dc.QUERY_TYPES)
    assert catalog["case_kinds_unchanged"] == list(dc.CASE_KINDS)


def test_c11_nine_family_templates_remain_human_required() -> None:
    built = _built_c11()
    bank = built["templates/question_family.blank.json"]
    assert len(bank["rows"]) == 9
    assert all(
        row["question_text"] == dc.HUMAN_REQUIRED
        and row["executable_query_type"] is None
        and row["case_kind"] is None
        and row["expected_answer"] is None
        and row["review_status"] == "HUMAN_REQUIRED"
        and row["formal_question"] is False
        and row["formal_answer"] is False
        and row["scoreable"] is False
        for row in bank["rows"]
    )
    assert bank["formal_question_count"] == 0
    assert bank["formal_answer_count"] == 0
    assert bank["formal_score_count"] == 0


def test_c11_missing_bucket_arithmetic_does_not_invent_old_names() -> None:
    built = _built_c11()
    expansion = built["catalog/missing_field_bucket_expansion.json"]
    assert expansion["legacy_bucket_total"] == 7
    assert expansion["legacy_bucket_catalog_status"] == ("LEGACY_NAMES_MISSING")
    assert expansion["legacy_bucket_refs"] == []
    assert expansion["named_additions"] == [
        "SCENE_VISUAL_MISSING",
        "EMOTION_INTENSITY_MISSING",
    ]
    assert expansion["resulting_bucket_total"] == 9
    assert 7 + len(expansion["named_additions"]) == 9
    raw = b"\n".join(dc.build_c11_question_expansion_artifacts().values())
    assert b"LEGACY_BUCKET_01" not in raw
    assert b"LEGACY_BUCKET_07" not in raw


def test_c11_missing_bucket_instance_matches_the_published_schema() -> None:
    built = _built_c11()
    schema = built["contracts/missing_field_bucket_registry.v1.schema.json"]
    expansion = built["catalog/missing_field_bucket_expansion.json"]
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(expansion)
    assert expansion["formal_diagnostic_row_count"] == 0
    assert expansion["formal_score_count"] == 0


def test_c11_expansion_writes_only_blocked_candidate_artifacts(
    tmp_path: Path,
) -> None:
    first = dc.write_c11_question_expansion_artifacts(tmp_path)
    receipt = dc.verify_c11_question_expansion_artifacts(tmp_path)
    second_manifest_sha = dc.sha256_file(tmp_path / "artifact_manifest.json")
    dc.write_c11_question_expansion_artifacts(tmp_path)
    assert dc.sha256_file(tmp_path / "artifact_manifest.json") == (second_manifest_sha)
    assert first["formal_question_count"] == 0
    assert first["formal_answer_count"] == 0
    assert first["formal_score_count"] == 0
    assert receipt["status"] == "PASS_HUMAN_REQUIRED_BLOCK_ACTIVE"
    assert receipt["formal_question_freeze_allowed"] is False
    assert receipt["formal_duse_execution_allowed"] is False
    assert receipt["formal_scores_emitted"] is False


def test_c11_expansion_rejects_unregistered_artifact(tmp_path: Path) -> None:
    dc.write_c11_question_expansion_artifacts(tmp_path)
    (tmp_path / "forged_formal_score.json").write_text(
        json.dumps({"status": "FORGED_FORMAL_SCORE"}),
        encoding="utf-8",
    )
    with pytest.raises(dc.DUseContractError, match="工件清单不闭合"):
        dc.verify_c11_question_expansion_artifacts(tmp_path)


def test_c11_expansion_rejects_manifest_inventory_drift(
    tmp_path: Path,
) -> None:
    dc.write_c11_question_expansion_artifacts(tmp_path)
    manifest_path = tmp_path / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_count_without_manifest"] += 1
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(dc.DUseContractError, match="工件数量漂移"):
        dc.verify_c11_question_expansion_artifacts(tmp_path)


def test_c11_expansion_rejects_forged_score_even_if_manifest_is_resigned(
    tmp_path: Path,
) -> None:
    dc.write_c11_question_expansion_artifacts(tmp_path)
    forged = tmp_path / "formal_score.json"
    forged.write_text('{"formal_score": 1}\n', encoding="utf-8")
    manifest_path = tmp_path / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["inventory"].append(
        {
            "path": "formal_score.json",
            "sha256": dc.sha256_file(forged),
            "bytes": forged.stat().st_size,
        }
    )
    manifest["artifact_count_without_manifest"] = len(manifest["inventory"])
    manifest["inventory_sha256"] = dc.sha256_bytes(
        dc.canonical_json_bytes(manifest["inventory"])
    )
    manifest_path.write_bytes(dc.canonical_json_bytes(manifest))
    with pytest.raises(dc.DUseContractError, match="固定工件清单"):
        dc.verify_c11_question_expansion_artifacts(tmp_path)


def test_c11_attribution_binds_page_identity_without_invented_content_sha() -> None:
    built = _built_c11()
    receipt = built["attribution_receipt.json"]
    source = receipt["notion_work_order"]
    assert source["page_id"] == "eb8821e57b67472db9f220b46110dcfd"
    assert source["url"].endswith(source["page_id"])
    assert source["content_sha256"] is None
    assert source["content_sha256_status"] == "NOT_AVAILABLE_NOT_INVENTED"
    excerpt_path = "authority_excerpt.json"
    assert receipt["authority_excerpt_path"] == excerpt_path
    assert receipt["authority_excerpt_sha256"] == dc.sha256_bytes(
        dc.build_c11_question_expansion_artifacts()[excerpt_path]
    )
    excerpt = built[excerpt_path]
    assert excerpt["excerpt_scope"] == "C11.2"
    assert excerpt["notion_full_page_content_sha256"] is None


def test_c11_actual_delivery_matches_generator_fixed_inventory() -> None:
    receipt = dc.verify_c11_question_expansion_artifacts(dc.DEFAULT_C11_OUTPUT_DIR)
    assert receipt["formal_scores_emitted"] is False
    assert receipt["artifact_count"] == (
        len(dc.C11_QUESTION_EXPANSION_RELATIVE_PATHS) + 1
    )
