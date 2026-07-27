from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from experiments.extraction_redesign_v02_overnight_20260725.V02_R1_scope_preregistration_20260726 import (
    v02_r1_scope_preregistration as r1,
)


def test_author_question_set_is_ten_full_frozen_questions() -> None:
    value = r1.author_question_set()
    assert value["question_count_per_chapter"] == 10
    assert value["scored_cell_total"] == 30
    assert len(value["questions"]) == 10
    assert len({row["question_id"] for row in value["questions"]}) == 10
    assert all(row["question_text"].endswith("？") for row in value["questions"])
    assert value["model_visible"] is False


def test_decision_rule_freezes_both_reductions_at_thirty_percent() -> None:
    gate = r1.decision_rule()["gates"]["material_reduction"]
    assert gate["fact_count_reduction_minimum"] == 0.30
    assert gate["material_output_token_reduction_minimum"] == 0.30
    assert "reasoning_tokens" in gate["material_output_tokens_definition"]


def test_arm_a_binds_current_contract_and_b_only_changes_scope_contract() -> None:
    arm_a = r1.arm_contract("A")
    arm_b = r1.arm_contract("B")
    assert (
        arm_a["shared_input_envelope"]
        == arm_b["shared_input_envelope"]
    )
    assert arm_a["scope"] != arm_b["scope"]
    assert arm_a["hot_type_enum"] == arm_b["hot_type_enum"]
    assert arm_a["permitted_delta_from_current"] == []
    assert arm_b["permitted_delta_from_current"] == [
        "MODEL_VISIBLE_SCOPE_RULES",
        "OUTPUT_SCHEMA_FROM_Z_EVENT_V1_TO_V02_R1_HOT_MATERIAL_V1",
    ]
    baseline = arm_a["current_contract_baseline_identity"]
    assert baseline["source_request_file_sha256"] == r1.sha256_file(
        r1.C6_BASELINE_REQUEST
    )
    assert "# Z00l 中性事件提取 Prompt v1.0" in (
        arm_a["model_visible_contract"]
    )
    assert arm_a["model_writes_verbatim_quote"] is False
    assert arm_b["model_writes_verbatim_quote"] is False


def test_b_schema_is_strict_and_a_keeps_z_event_v1() -> None:
    schema_a = r1.arm_a_output_schema()
    event = schema_a["properties"]["events"]["items"]
    assert schema_a["properties"]["schema_version"]["const"] == "z-event-v1"
    assert event["additionalProperties"] is False
    assert "event" in event["required"]
    schema_b = r1.arm_b_output_schema()
    fact = schema_b["properties"]["facts"]["items"]
    assert fact["additionalProperties"] is False
    assert "quote" not in fact["properties"]
    assert "source_ids" in fact["required"]


def test_each_case_is_split_into_two_covering_nonoverlapping_chunks() -> None:
    for case_id in r1.CASE_IDS:
        plan = r1.experiment_chunk_plan(case_id)
        catalog = r1.read_json(
            r1.REPO_ROOT / plan["source_catalog_path"]
        )
        first, second = plan["chunks"]
        assert first["primary_range"]["char_start"] == 0
        assert (
            first["primary_range"]["char_end_exclusive"]
            == second["primary_range"]["char_start"]
        )
        assert (
            second["primary_range"]["char_end_exclusive"]
            == len(catalog["source_text"])
        )
        known_ids = {row["sentence_id"] for row in catalog["sentences"]}
        assert set(first["visible_source_ids"]) <= known_ids
        assert set(second["visible_source_ids"]) <= known_ids
        assert plan["general_s1_calibration_changed"] is False


def test_preregistration_is_twelve_calls_zero_retry_and_not_executable() -> None:
    value = r1.preregistration()
    assert value["call_budget"] == {
        "A": 6,
        "B": 6,
        "total": 12,
        "retry": 0,
    }
    assert len(value["call_matrix"]) == 12
    assert sum(row["arm"] == "A" for row in value["call_matrix"]) == 6
    assert sum(row["arm"] == "B" for row in value["call_matrix"]) == 6
    assert value["network_authorization"]["execute_allowed"] is False
    assert value["model"]["provider"] == "sensenova"
    assert value["model"]["model"] == "deepseek-v4-flash"


def test_experiment_hard_stop_list_is_exactly_six_conditions() -> None:
    value = r1.preregistration()
    assert tuple(value["experiment_hard_stop_reasons"]) == (
        r1.EXPERIMENT_HARD_STOP_REASONS
    )
    assert value["quality_failure_policy"] == "NEGATIVE_SCORE_CONTINUE_BATCH"


def test_samples_contain_no_gold_path_or_secret_material() -> None:
    raw = json.dumps(
        {
            "A": r1.contract_sample("A"),
            "B": r1.contract_sample("B"),
        },
        ensure_ascii=False,
    )
    assert "config/gold" not in raw
    assert "API_KEY" not in raw
    assert "正式金标" not in raw


def test_artifacts_are_deterministic_and_zero_network() -> None:
    first = r1.build_artifacts()
    second = r1.build_artifacts()
    assert first == second
    manifest = json.loads(first["manifest.json"])
    assert manifest["model_api_calls"] == 0
    assert manifest["network_requests"] == 0
    assert manifest["git_commit_or_push"] is False


def test_cli_writes_same_tree_without_network() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "out"
        report_dir = Path(tmp) / "report"
        result = subprocess.run(
            [
                sys.executable,
                str(Path(r1.__file__).resolve()),
                "--output-dir",
                str(output_dir),
                "--report-dir",
                str(report_dir),
            ],
            cwd=r1.REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        receipt = json.loads(result.stdout)
        assert receipt["model_api_calls"] == 0
        assert receipt["network_requests"] == 0
        assert receipt["execute_allowed"] is False
        assert (output_dir / "preregistration.json").exists()
        assert (report_dir / "R1_范围实验预注册停点回包.md").exists()
