from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "V02_C11_product_north_star_20260725"
    / "C11_4_5_structure_paper_design"
    / "program"
)
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

import v02_c11_structure_paper_design as design  # noqa: E402


pytestmark = pytest.mark.v02

EXPECTED_RECONCILIATION_STATES = (
    "realized_exact",
    "realized_variant",
    "omitted",
    "contradicted",
    "new_unplanned",
    "deferred",
)
EXPECTED_OWNER_VALUES = (
    "narrator",
    "character_speech",
    "character_thought",
    "document_or_system",
    "unknown",
)
EXPECTED_SCENE_TEXTURE_KINDS = (
    "place",
    "time_or_light",
    "key_visual_object",
    "camera_suggestion",
)
EXPECTED_AFFECT_VALENCES = (
    "positive",
    "negative",
    "neutral",
    "unknown",
)


def test_c11_4_has_exactly_five_strict_draft_2020_12_schemas() -> None:
    schemas = design.build_c11_4_schemas()
    assert list(schemas) == [
        "dual_order",
        "plan_event_store",
        "plan_prose_reconciliation",
        "chapter_contract_bundle",
        "assertion_owner",
    ]
    for schema in schemas.values():
        assert schema["$schema"] == design.DRAFT_2020_12
        Draft202012Validator.check_schema(schema)
        assert schema["additionalProperties"] is False


def test_each_c11_4_schema_accepts_one_valid_and_rejects_one_invalid() -> None:
    valid, invalid = design.build_c11_4_examples()
    assert len(valid) == len(invalid) == 5
    for name, instance in valid.items():
        design.validate_c11_4_instance(name, instance)
        with pytest.raises(design.PaperDesignError):
            design.validate_c11_4_instance(name, invalid[name])


def test_dual_order_is_separate_but_uses_the_same_members() -> None:
    valid, _ = design.build_c11_4_examples()
    instance = valid["dual_order"]
    assert instance["story_order"] != instance["discourse_order"]
    assert set(instance["story_order"]) == set(instance["discourse_order"])
    changed = {**instance, "discourse_order": ["PE-0001"]}
    with pytest.raises(design.PaperDesignError, match="成员漂移"):
        design.validate_c11_4_instance("dual_order", changed)


def test_plan_store_uses_plan_identity_and_history_fact_refs_only() -> None:
    valid, _ = design.build_c11_4_examples()
    instance = valid["plan_event_store"]
    assert all(set(row) == {"plan_event_id"} for row in instance["plan_events"])
    assert all(set(row) == {"fact_ref"} for row in instance["history"])
    assert "fact_id" not in design._walk_keys(instance)
    assert instance["history"] == [{"fact_ref": "PE-0001"}]


def test_plan_store_rejects_duplicate_ids_and_dangling_history_refs() -> None:
    valid, _ = design.build_c11_4_examples()
    instance = valid["plan_event_store"]
    duplicate = {
        **instance,
        "plan_events": [
            {"plan_event_id": "PE-0001"},
            {"plan_event_id": "PE-0001"},
        ],
    }
    dangling = {
        **instance,
        "history": [{"fact_ref": "PE-9999"}],
    }
    with pytest.raises(design.PaperDesignError, match="机械唯一"):
        design.validate_c11_4_instance("plan_event_store", duplicate)
    with pytest.raises(design.PaperDesignError, match="悬空引用"):
        design.validate_c11_4_instance("plan_event_store", dangling)


def test_reconciliation_uses_exact_states_and_strict_sixty_percent_rule() -> None:
    schema = design.build_c11_4_schemas()["plan_prose_reconciliation"]
    assert schema["properties"]["state"]["enum"] == list(EXPECTED_RECONCILIATION_STATES)
    valid, _ = design.build_c11_4_examples()
    instance = valid["plan_prose_reconciliation"]
    design.validate_c11_4_instance(
        "plan_prose_reconciliation",
        instance,
    )
    at_threshold = {
        **instance,
        "new_unplanned_scan_tokens": 60,
        "saving_verdict": "SAVING",
    }
    design.validate_c11_4_instance(
        "plan_prose_reconciliation",
        at_threshold,
    )


def test_contract_bundle_blocks_unapproved_plan_fields_and_truth_writeback() -> None:
    schemas = design.build_c11_4_schemas()
    defs = schemas["chapter_contract_bundle"]["$defs"]
    assert set(defs) == {
        "chapter_fact_graph_v2",
        "chapter_plan_v2",
        "chapter_execution_packet_v1",
        "projection_card_v1",
    }
    valid, _ = design.build_c11_4_examples()
    instance = valid["chapter_contract_bundle"]
    plan = instance["chapter_plan_v2"]
    assert plan["missing_marker"] == "CHAPTER_PLAN_V2_FIELD_NAMES_MISSING"
    assert plan["activation_allowed"] is False
    assert "known_semantic_slots" not in plan
    assert instance["projection_card_v1"]["truth_writeback_allowed"] is False


def test_assertion_owner_keeps_one_five_value_enum_and_no_literalness() -> None:
    valid, _ = design.build_c11_4_examples()
    instance = valid["assertion_owner"]
    assert tuple(instance["candidate_values"]) == EXPECTED_OWNER_VALUES
    assert "document" not in instance["candidate_values"]
    assert "system" not in instance["candidate_values"]
    assert "literalness" not in design._walk_keys(instance)
    assert instance["canonical_field_name_status"] == (
        "ASSERTION_OWNER_CANONICAL_FIELD_NAME_MISSING"
    )


def test_c11_5_schema_is_independent_and_examples_are_three_plus_three() -> None:
    schema = design.build_sidecar_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert schema["properties"]["fact_sentence_writeback_allowed"] == {"const": False}
    assert schema["properties"]["metric_exclusions"]["const"] == [
        "FACT_COVERAGE",
        "UCR",
        "SOP",
        "GATES",
    ]
    scene_enum = schema["properties"]["scene_texture"]["items"]["properties"]["kind"][
        "enum"
    ]
    assert tuple(scene_enum) == EXPECTED_SCENE_TEXTURE_KINDS
    affect_valence = schema["properties"]["affect"]["items"]["properties"]["valence"][
        "enum"
    ]
    assert tuple(affect_valence) == EXPECTED_AFFECT_VALENCES
    valid, invalid = design.build_sidecar_examples()
    assert len(valid) == len(invalid) == 3
    for instance in valid:
        design.validate_sidecar_instance(instance)
    for instance in invalid:
        with pytest.raises(design.PaperDesignError):
            design.validate_sidecar_instance(instance)


def test_sidecar_valid_examples_cover_all_scene_kinds_and_bad_values_reject() -> None:
    valid, _ = design.build_sidecar_examples()
    observed = {
        item["kind"] for instance in valid for item in instance["scene_texture"]
    }
    assert observed == set(EXPECTED_SCENE_TEXTURE_KINDS)
    affect_example = next(instance for instance in valid if instance["affect"])
    bad_valence = json.loads(json.dumps(affect_example, ensure_ascii=False))
    bad_valence["affect"][0]["valence"] = "banana"
    bad_intensity = json.loads(json.dumps(affect_example, ensure_ascii=False))
    bad_intensity["affect"][0]["intensity"] = "extreme"
    with pytest.raises(design.PaperDesignError):
        design.validate_sidecar_instance(bad_valence)
    with pytest.raises(design.PaperDesignError):
        design.validate_sidecar_instance(bad_intensity)


def test_sidecar_spans_replay_exactly_against_c4_frozen_catalogs() -> None:
    valid, _ = design.build_sidecar_examples()
    sources = design._load_source_index()
    for instance in valid:
        for item in [*instance["scene_texture"], *instance["affect"]]:
            quote = sources[item["case_id"]]["entries"][item["anchor_id"]]["quote"]
            assert item["evidence_span"] in quote


def test_question_relation_covers_all_nine_families_without_fake_questions() -> None:
    table = design.build_question_relation_table()
    assert len(table["rows"]) == 9
    assert len({row["question_family"] for row in table["rows"]}) == 9
    assert table["formal_question_count"] == 0
    assert table["formal_answer_count"] == 0
    assert table["formal_score_count"] == 0
    storyboard = next(
        row
        for row in table["rows"]
        if row["question_family"] == "PRODUCT_STORYBOARD_RECONSTRUCTION"
    )
    assert storyboard["candidate_sidecar_surfaces"] == [
        "scene_texture",
        "affect",
    ]
    assert all(row["human_required"] is True for row in table["rows"])


def test_artifacts_total_sixteen_examples_and_are_deterministic(
    tmp_path: Path,
) -> None:
    first = design.build_artifacts()
    second = design.build_artifacts()
    assert first == second
    acceptance = json.loads(first["acceptance_receipt.json"])
    assert acceptance["total_example_count"] == 16
    assert acceptance["model_api_calls"] == 0
    assert acceptance["network_requests"] == 0
    assert acceptance["formal_gold_read"] is False
    output = tmp_path / "bundle"
    design.write_artifacts(output, first)
    manifest = design.verify_artifacts(output)
    assert manifest["file_count"] == len(first) - 1
    assert (output / "README.md").read_text().endswith("来源：Codex\n")


def test_verifier_rejects_unregistered_files(tmp_path: Path) -> None:
    output = tmp_path / "bundle"
    design.write_artifacts(output, design.build_artifacts())
    (output / "unexpected.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(design.PaperDesignError, match="实际文件集合"):
        design.verify_artifacts(output)


def test_verifier_rejects_unregistered_program_files(tmp_path: Path) -> None:
    output = tmp_path / "bundle"
    design.write_artifacts(output, design.build_artifacts())
    (output / "program" / "unregistered.py").write_text(
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )
    with pytest.raises(design.PaperDesignError, match="实际文件集合"):
        design.verify_artifacts(output)


def test_actual_task_root_matches_the_deterministic_delivery() -> None:
    manifest = design.verify_artifacts(design.TASK_ROOT)
    assert manifest["paper_only"] is True
    assert manifest["candidate_status"] == "candidate_silver_not_active"
