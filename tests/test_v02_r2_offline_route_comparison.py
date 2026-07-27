from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

import pytest

from experiments.V02_R2_development_hardening_r01_20260727 import (
    offline_scorer,
    prepare_route_workspace,
    r2_dev_hardening,
    route_runner,
)


REPO = Path(__file__).resolve().parents[1]
QUESTION_SET = (
    REPO
    / "experiments/extraction_redesign_v02_overnight_20260725/"
    "V02_R1_scope_preregistration_20260726/author_question_set.json"
)
CATALOG_DIR = (
    REPO
    / "runs/V02_R2_question_driven_retrieval_p0_r04_20260726/"
    "model_workspace/source_catalog_v2"
)
HIDDEN_CELLS = (
    REPO
    / "runs/V02_R2_question_driven_retrieval_p0_r04_20260726/"
    "scoring_lockbox/question_gold_dev_v2.json"
)


def _freeze_and_score(run_dir: Path) -> dict:
    score_bundle_path = run_dir / "preregistered/score_bundle_manifest.json"
    offline_scorer.freeze_score_bundle(
        sealed_outputs_dir=run_dir / "sealed_outputs",
        route_receipt_path=run_dir / "route_run_receipt.json",
        hidden_cells_path=HIDDEN_CELLS,
        catalog_dir=CATALOG_DIR,
        route_manifests_dir=run_dir / "route_manifests",
        output_path=score_bundle_path,
        scoring_executor_id="TEST-OFFLINE-SCORER",
    )
    return offline_scorer.score_all(
        sealed_outputs_dir=run_dir / "sealed_outputs",
        route_receipt_path=run_dir / "route_run_receipt.json",
        hidden_cells_path=HIDDEN_CELLS,
        catalog_dir=CATALOG_DIR,
        route_manifests_dir=run_dir / "route_manifests",
        score_bundle_manifest_path=score_bundle_path,
        expected_score_bundle_manifest_sha256=offline_scorer.sha256_file(
            score_bundle_path
        ),
        output_path=run_dir / "offline_score.json",
    )


def test_route_runner_does_not_import_gold_capable_modules() -> None:
    source = inspect.getsource(route_runner)
    assert "v02_r2_p0" not in source
    assert "v02_r1_route_comparison" not in source
    assert "v02_r1_route_runner" not in source


def test_route_runner_rejects_hidden_input_path(tmp_path: Path) -> None:
    hidden_path = tmp_path / "scoring_lockbox" / "questions.json"
    hidden_path.parent.mkdir()
    hidden_path.write_text("{}", encoding="utf-8")
    try:
        route_runner._load_questions(hidden_path)
    except route_runner.RouteRunnerError as exc:
        assert "FORBIDDEN_ROUTE_INPUT_PATH" in str(exc)
    else:
        raise AssertionError("隐藏输入路径未被拒绝")


def test_route_workspace_rejects_symlink_to_hidden_material(tmp_path: Path) -> None:
    hidden = tmp_path / "scoring_lockbox" / "question_set.json"
    hidden.parent.mkdir()
    hidden.write_bytes(QUESTION_SET.read_bytes())
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "question_set.json").symlink_to(hidden)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "v02-r2-route-workspace-manifest.v1",
                "issuer_type": "LOCAL_PREREGISTERED_CANDIDATE",
                "sealed_before_run": True,
                "files": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        r2_dev_hardening.R2HardeningError,
        match="SYMLINK_FORBIDDEN",
    ):
        route_runner.run_routes(
            workspace=workspace,
            preregistered_manifest_path=manifest,
            expected_manifest_sha256=route_runner.sha256_file(manifest),
            output_dir=tmp_path / "out",
        )


def test_program_plan_and_cue_lexicon_are_generic() -> None:
    plan = route_runner.plan_question("谁仍不知道什么，或误信了什么？")
    assert len(plan) >= 2
    assert all(row["request_head_id"].startswith("RH-") for row in plan)
    serialized = json.dumps(
        {
            "generic": route_runner.GENERIC_CUE_LEXICON,
            "bridge": route_runner.OBSERVABLE_NARRATIVE_BRIDGE,
        },
        ensure_ascii=False,
    )
    for forbidden in ("明兰", "路明非", "周明瑞", "B01-", "B02-", "B03-"):
        assert forbidden not in serialized


def test_a5_only_adds_generic_observable_bridge_terms() -> None:
    question = "本章发生了哪些会影响后续的状态变化？"
    plan = route_runner.plan_question(question)
    a4h = route_runner._query_variants(
        route_id="A4h",
        question_text=question,
        plan=plan,
        aliases=[],
        case_id="B01-U0033",
    )
    a5 = route_runner._query_variants(
        route_id="A5",
        question_text=question,
        plan=plan,
        aliases=[],
        case_id="B01-U0033",
    )
    assert a5[: len(a4h)] == a4h
    assert set(a5) - set(a4h) == set(
        route_runner._observable_bridge_terms(question)
    ) - set(a4h)
    assert "开始" in a5
    assert "收走" in a5


def test_a6_uses_exactly_the_same_queries_as_a5() -> None:
    question = "本章发生了哪些会影响后续的状态变化？"
    plan = route_runner.plan_question(question)
    kwargs = {
        "question_text": question,
        "plan": plan,
        "aliases": [],
        "case_id": "B01-U0033",
    }
    assert route_runner._query_variants(route_id="A6", **kwargs) == (
        route_runner._query_variants(route_id="A5", **kwargs)
    )


def test_selection_projection_keeps_only_selection_identity() -> None:
    projection = route_runner.selection_projection(
        [
            {
                "cell_id": "B01-U0033::R1-Q01",
                "selected_windows": [
                    {
                        "paragraph_id": "B01-U0033-P0001",
                        "rank": 1,
                        "selection_reason": "ACTUAL_QUERY_MATCH",
                        "score": 99.0,
                        "char_count": 12,
                    }
                ],
            }
        ]
    )
    assert set(projection) == {
        "schema_version",
        "cells",
        "projection_payload_sha256",
    }
    assert projection["cells"][0]["selected_windows"] == [
        {
            "paragraph_id": "B01-U0033-P0001",
            "rank": 1,
            "selection_reason": "ACTUAL_QUERY_MATCH",
        }
    ]


def test_planner_visible_source_projection_drops_catalog_side_fields() -> None:
    catalog = json.loads(
        (CATALOG_DIR / "B01-U0033.json").read_text(encoding="utf-8")
    )
    projected = route_runner._planner_visible_source_projection(catalog)
    serialized = json.dumps(projected, ensure_ascii=False)
    assert set(projected) == {
        "schema_version",
        "source_id",
        "source_body_sha256",
        "source_text",
        "paragraphs",
        "sentences",
        "projection_payload_sha256",
    }
    for forbidden in (
        "answer_source_id_contract",
        "accepted_legacy_source_ids",
        "legacy_sentence_ids_with_content_overlap",
        "run_id",
    ):
        assert forbidden not in serialized


def test_a7_ontology_and_planner_are_generic_and_open_world() -> None:
    question = {
        "question_id": "TEST-Q",
        "question_text": "本章新增了哪些目标、计划、承诺或威胁？",
    }
    plan = route_runner.plan_fact_obligations(question)
    serialized = json.dumps(
        {
            "ontology": route_runner.FACT_OBLIGATION_ONTOLOGY,
            "plan": plan,
        },
        ensure_ascii=False,
    )
    assert plan["planner_kind"] == "PROGRAM_ONTOLOGY_GROUNDED"
    assert plan["cardinality_policy"] == "UNKNOWN_OPEN_WORLD"
    assert plan["completeness_claim"] == "NOT_SELF_CERTIFIED"
    assert "expected_answer_count" not in serialized
    for forbidden in (
        "明兰",
        "路明非",
        "周明瑞",
        "B01-",
        "B02-",
        "B03-",
        "required_heads",
        "source_id_groups",
        "human_verdict",
    ):
        assert forbidden not in serialized


def test_a7_candidate_frames_bind_exact_source_spans() -> None:
    catalog = json.loads(
        (CATALOG_DIR / "B01-U0033.json").read_text(encoding="utf-8")
    )
    source = route_runner._planner_visible_source_projection(catalog)
    question = {
        "question_id": "TEST-Q",
        "question_text": "本章新增了哪些目标、计划、承诺或威胁？",
    }
    plan = route_runner.plan_fact_obligations(question)
    frames = route_runner.extract_candidate_frames(
        obligation_plan=plan,
        planner_source=source,
    )
    assert frames
    for frame in frames:
        surface = source["source_text"][
            frame["char_start"] : frame["char_end_exclusive"]
        ]
        assert route_runner.sha256_bytes(surface.encode("utf-8")) == frame[
            "surface_sha256"
        ]
        assert frame["status"] == "CANDIDATE_NOT_ANSWER"
    query_map = route_runner.build_a7_query_map(
        case_id=source["source_id"],
        question_id=question["question_id"],
        planner_source=source,
        frames=frames,
    )
    assert query_map["queries"]
    for query in query_map["queries"]:
        assert {row["kind"] for row in query["origins"]} == {
            "SOURCE_EXACT_SPAN"
        }


def test_a6_reserves_real_match_per_request_head_then_global_fills() -> None:
    rows = [
        {
            "paragraph_id": "P-global",
            "merged_score": 10.0,
            "query_hit_count": 2,
            "char_count": 60,
            "matched_query_ids": ["QRY-03", "QRY-04"],
            "matched_grams": ["全局"],
        },
        {
            "paragraph_id": "P-head-1",
            "merged_score": 8.0,
            "query_hit_count": 1,
            "char_count": 60,
            "matched_query_ids": ["QRY-01"],
            "matched_grams": ["甲头"],
        },
        {
            "paragraph_id": "P-head-2",
            "merged_score": 7.0,
            "query_hit_count": 1,
            "char_count": 60,
            "matched_query_ids": ["QRY-02"],
            "matched_grams": ["乙头"],
        },
    ]
    request_heads = [
        [
            {
                "paragraph_id": "P-head-1",
                "char_count": 60,
                "matched_grams": ["甲头"],
            },
            {
                "paragraph_id": "P-global",
                "char_count": 60,
                "matched_grams": [],
            },
        ],
        [
            {
                "paragraph_id": "P-head-2",
                "char_count": 60,
                "matched_grams": ["乙头"],
            },
            {
                "paragraph_id": "P-global",
                "char_count": 60,
                "matched_grams": [],
            },
        ],
    ]
    selected = route_runner._pack_request_head_minimum_then_global_fill(
        rows,
        request_head_rankings=request_heads,
        budget=120,
    )
    by_id = {row["paragraph_id"]: row for row in selected}
    assert set(by_id) == {"P-head-1", "P-head-2"}
    assert by_id["P-head-1"]["request_head_ids"] == ["RH-01"]
    assert by_id["P-head-2"]["request_head_ids"] == ["RH-02"]
    assert sum(row["char_count"] for row in selected) == 120


def test_a6_packer_has_no_hidden_or_case_specific_branch() -> None:
    source = inspect.getsource(
        route_runner._pack_request_head_minimum_then_global_fill
    )
    for forbidden in ("B01", "B02", "B03", "gold", "lockbox", "question_id"):
        assert forbidden not in source


def test_a5_manifest_binds_single_change_and_stays_zero_api(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    manifest = tmp_path / "manifest.json"
    prep = prepare_route_workspace.prepare_route_workspace(
        question_set_path=QUESTION_SET,
        catalog_dir=CATALOG_DIR,
        workspace=workspace,
        manifest_path=manifest,
    )
    run_dir = tmp_path / "a5"
    receipt = route_runner.run_routes(
        workspace=workspace,
        preregistered_manifest_path=manifest,
        expected_manifest_sha256=prep["manifest_sha256"],
        output_dir=run_dir,
        route_ids=("A4h", "A5"),
    )
    assert receipt["model_api_calls"] == 0
    assert receipt["network_calls"] == 0
    assert receipt["sealed_output_count"] == 14
    route_manifest = json.loads(
        (run_dir / "route_manifests/A5.json").read_text(encoding="utf-8")
    )
    assert route_manifest["parent_route_id"] == "A4h"
    assert route_manifest["single_change"] == (
        "OBSERVABLE_NARRATIVE_BRIDGE_ONLY_ON_A4H"
    )
    score = _freeze_and_score(run_dir)
    assert len(score["rows"]) == 14


def test_a6_manifest_binds_packing_only_and_stays_zero_api(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    manifest = tmp_path / "manifest.json"
    prep = prepare_route_workspace.prepare_route_workspace(
        question_set_path=QUESTION_SET,
        catalog_dir=CATALOG_DIR,
        workspace=workspace,
        manifest_path=manifest,
    )
    run_dir = tmp_path / "a6"
    receipt = route_runner.run_routes(
        workspace=workspace,
        preregistered_manifest_path=manifest,
        expected_manifest_sha256=prep["manifest_sha256"],
        output_dir=run_dir,
        route_ids=("A5", "A6"),
    )
    assert receipt["model_api_calls"] == 0
    assert receipt["network_calls"] == 0
    assert receipt["sealed_output_count"] == 14
    route_manifest = json.loads(
        (run_dir / "route_manifests/A6.json").read_text(encoding="utf-8")
    )
    assert route_manifest["parent_route_id"] == "A5"
    assert route_manifest["single_change"] == (
        "REQUEST_HEAD_MINIMUM_WINDOW_BEFORE_A5_GLOBAL_FILL_ONLY"
    )
    score = _freeze_and_score(run_dir)
    assert len(score["rows"]) == 14


def test_a7_manifest_binds_planner_only_and_stays_zero_api(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    manifest = tmp_path / "manifest.json"
    prep = prepare_route_workspace.prepare_route_workspace(
        question_set_path=QUESTION_SET,
        catalog_dir=CATALOG_DIR,
        workspace=workspace,
        manifest_path=manifest,
    )
    run_dir = tmp_path / "a7"
    receipt = route_runner.run_routes(
        workspace=workspace,
        preregistered_manifest_path=manifest,
        expected_manifest_sha256=prep["manifest_sha256"],
        output_dir=run_dir,
        route_ids=("A5", "A7"),
    )
    assert receipt["model_api_calls"] == 0
    assert receipt["network_calls"] == 0
    assert receipt["sealed_output_count"] == 14
    route_manifest = json.loads(
        (run_dir / "route_manifests/A7.json").read_text(encoding="utf-8")
    )
    assert route_manifest["parent_route_id"] == "A5"
    assert route_manifest["single_change"] == (
        "PROGRAM_ONTOLOGY_GROUNDED_OBLIGATION_PLANNER_ONLY"
    )
    assert route_manifest["hidden_root_mounted"] is False
    frames = json.loads(
        (
            run_dir / "route_assets/source_candidate_frames_v1/A7.json"
        ).read_text(encoding="utf-8")
    )
    assert any(cell["frames"] for cell in frames["cells"])
    score = _freeze_and_score(run_dir)
    assert len(score["rows"]) == 14


def test_a3_independent_head_quotas_merge_duplicates_once() -> None:
    rankings = [
        [
            {
                "paragraph_id": "P-left",
                "score": 10.0,
                "char_count": 60,
                "original_text": "甲" * 60,
            },
            {
                "paragraph_id": "P-shared",
                "score": 9.0,
                "char_count": 40,
                "original_text": "乙" * 40,
            },
        ],
        [
            {
                "paragraph_id": "P-right",
                "score": 10.0,
                "char_count": 60,
                "original_text": "丙" * 60,
            },
            {
                "paragraph_id": "P-shared",
                "score": 9.0,
                "char_count": 40,
                "original_text": "乙" * 40,
            },
        ],
    ]
    selected = route_runner._pack_independent_head_quotas(rankings, budget=200)
    by_id = {row["paragraph_id"]: row for row in selected}
    assert set(by_id) == {"P-left", "P-right", "P-shared"}
    assert sum(row["char_count"] for row in selected) == 160
    assert by_id["P-left"]["request_head_ids"] == ["RH-01"]
    assert by_id["P-right"]["request_head_ids"] == ["RH-02"]
    assert by_id["P-shared"]["request_head_ids"] == ["RH-01", "RH-02"]


def test_a3_has_no_case_or_hidden_reference_branch() -> None:
    source = inspect.getsource(route_runner._pack_independent_head_quotas)
    for forbidden in (
        "B01",
        "B02",
        "B03",
        "gold",
        "lockbox",
        "question_id",
    ):
        assert forbidden not in source


def test_route_run_and_isolated_score_are_reproducible(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_workspace = tmp_path / "first-workspace"
    first_manifest = tmp_path / "first-manifest.json"
    first_prep = prepare_route_workspace.prepare_route_workspace(
        question_set_path=QUESTION_SET,
        catalog_dir=CATALOG_DIR,
        workspace=first_workspace,
        manifest_path=first_manifest,
    )
    second_workspace = tmp_path / "second-workspace"
    second_manifest = tmp_path / "second-manifest.json"
    second_prep = prepare_route_workspace.prepare_route_workspace(
        question_set_path=QUESTION_SET,
        catalog_dir=CATALOG_DIR,
        workspace=second_workspace,
        manifest_path=second_manifest,
    )
    first_receipt = route_runner.run_routes(
        workspace=first_workspace,
        preregistered_manifest_path=first_manifest,
        expected_manifest_sha256=first_prep["manifest_sha256"],
        output_dir=first,
    )
    second_receipt = route_runner.run_routes(
        workspace=second_workspace,
        preregistered_manifest_path=second_manifest,
        expected_manifest_sha256=second_prep["manifest_sha256"],
        output_dir=second,
    )
    assert first_receipt["model_api_calls"] == 0
    assert first_receipt["sealed_output_count"] == 42
    assert first_receipt["receipt_payload_sha256"] == second_receipt[
        "receipt_payload_sha256"
    ]
    for path in sorted((first / "sealed_outputs").glob("*/*.json")):
        counterpart = second / path.relative_to(first)
        assert path.read_bytes() == counterpart.read_bytes()
    for path in sorted((first / "sealed_outputs/A3").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for cell in payload["cells"]:
            represented = {
                head_id
                for window in cell["selected_windows"]
                for head_id in window["request_head_ids"]
            }
            expected = {
                head["request_head_id"] for head in cell["request_heads"]
            }
            assert represented == expected
            assert cell["candidate_chars"] <= payload["budget_chars"]

    score = _freeze_and_score(first)
    assert score["model_api_calls"] == 0
    assert len(score["rows"]) == 42
    assert score["formal_quality_score"] is False
    assert score["next_model_stage_allowed"] is False

    tampered = first / "sealed_outputs/A0/300.json"
    tampered.write_text("{}\n", encoding="utf-8")
    try:
        offline_scorer.score_all(
            sealed_outputs_dir=first / "sealed_outputs",
            route_receipt_path=first / "route_run_receipt.json",
            hidden_cells_path=HIDDEN_CELLS,
            catalog_dir=CATALOG_DIR,
            route_manifests_dir=first / "route_manifests",
            score_bundle_manifest_path=(
                first / "preregistered/score_bundle_manifest.json"
            ),
            expected_score_bundle_manifest_sha256=offline_scorer.sha256_file(
                first / "preregistered/score_bundle_manifest.json"
            ),
            output_path=first / "tampered-score.json",
        )
    except offline_scorer.OfflineScorerError as exc:
        assert "SEALED_OUTPUT_SHA_MISMATCH" in str(exc)
    else:
        raise AssertionError("被替换的封存输出未被拒绝")


def test_a4h_only_counts_nonempty_query_hits_and_is_scoreable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    manifest = tmp_path / "manifest.json"
    prep = prepare_route_workspace.prepare_route_workspace(
        question_set_path=QUESTION_SET,
        catalog_dir=CATALOG_DIR,
        workspace=workspace,
        manifest_path=manifest,
    )
    run_dir = tmp_path / "a4h"
    receipt = route_runner.run_routes(
        workspace=workspace,
        preregistered_manifest_path=manifest,
        expected_manifest_sha256=prep["manifest_sha256"],
        output_dir=run_dir,
        route_ids=("A4h",),
    )
    assert receipt["sealed_output_count"] == 7
    question_projection = json.loads(
        (run_dir / "frozen/question_projection.json").read_text(encoding="utf-8")
    )
    assert all(set(row) == {"question_id", "question_text"} for row in question_projection)
    for output_path in sorted((run_dir / "sealed_outputs/A4h").glob("*.json")):
        output = json.loads(output_path.read_text(encoding="utf-8"))
        for cell in output["cells"]:
            seen_fallback = False
            actual_count = 0
            fallback_count = 0
            for window in cell["selected_windows"]:
                if window["selection_reason"] == "UNMATCHED_FALLBACK":
                    seen_fallback = True
                    fallback_count += 1
                    assert window["matched_grams"] == []
                    assert window["matched_query_ids"] == []
                else:
                    assert not seen_fallback
                    actual_count += 1
                    assert window["selection_reason"] == "ACTUAL_QUERY_MATCH"
                    assert window["matched_grams"]
                    assert window["matched_query_ids"]
            assert cell["actual_match_window_count"] == actual_count
            assert cell["fallback_window_count"] == fallback_count
            assert cell["actual_match_chars"] + cell["fallback_chars"] == cell[
                "candidate_chars"
            ]
    route_manifest = json.loads(
        (run_dir / "route_manifests/A4h.json").read_text(encoding="utf-8")
    )
    assert route_manifest["parent_route_id"] == "A4"
    assert route_manifest["single_change"] == (
        "NONZERO_QUERY_HIT_ACCOUNTING_AND_FALLBACK_ORDER_ONLY"
    )
    score = _freeze_and_score(run_dir)
    assert len(score["rows"]) == 7
    assert all(row["route_id"] == "A4h" for row in score["rows"])


def test_scorer_recomputes_chars_and_case_binding(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    manifest = tmp_path / "manifest.json"
    prep = prepare_route_workspace.prepare_route_workspace(
        question_set_path=QUESTION_SET,
        catalog_dir=CATALOG_DIR,
        workspace=workspace,
        manifest_path=manifest,
    )
    run_dir = tmp_path / "run"
    route_runner.run_routes(
        workspace=workspace,
        preregistered_manifest_path=manifest,
        expected_manifest_sha256=prep["manifest_sha256"],
        output_dir=run_dir,
        route_ids=("A4h",),
    )
    output = json.loads(
        (run_dir / "sealed_outputs/A4h/2500.json").read_text(encoding="utf-8")
    )
    hidden = json.loads(HIDDEN_CELLS.read_text(encoding="utf-8"))["cells"]
    catalogs = offline_scorer._load_catalogs(CATALOG_DIR)
    expected_index_sha256 = output["index_payload_sha256"]

    bad_chars = copy.deepcopy(output)
    bad_chars["cells"][0]["candidate_chars"] += 1
    bad_chars["output_payload_sha256"] = offline_scorer.sha256_bytes(
        offline_scorer.canonical_bytes(
            {key: value for key, value in bad_chars.items() if key != "output_payload_sha256"}
        )
    )
    with pytest.raises(
        offline_scorer.OfflineScorerError,
        match="ROUTE_OUTPUT_CANDIDATE_CHARS_MISMATCH",
    ):
        offline_scorer.score_route_output(
            route_output=bad_chars,
            hidden_cells=hidden,
            catalogs=catalogs,
            expected_index_payload_sha256=expected_index_sha256,
        )

    cross_case = copy.deepcopy(output)
    foreign_paragraph = catalogs[1]["paragraphs"][0]
    cross_case["cells"][0]["selected_windows"][0]["paragraph_id"] = foreign_paragraph[
        "paragraph_id"
    ]
    cross_case["cells"][0]["selected_windows"][0]["char_count"] = len(
        foreign_paragraph["original_text"]
    )
    cross_case["output_payload_sha256"] = offline_scorer.sha256_bytes(
        offline_scorer.canonical_bytes(
            {key: value for key, value in cross_case.items() if key != "output_payload_sha256"}
        )
    )
    with pytest.raises(
        offline_scorer.OfflineScorerError,
        match="ROUTE_OUTPUT_PARAGRAPH_CROSS_CASE",
    ):
        offline_scorer.score_route_output(
            route_output=cross_case,
            hidden_cells=hidden,
            catalogs=catalogs,
            expected_index_payload_sha256=expected_index_sha256,
        )

    wrong_index = copy.deepcopy(output)
    wrong_index["index_payload_sha256"] = "f" * 64
    wrong_index["output_payload_sha256"] = offline_scorer.sha256_bytes(
        offline_scorer.canonical_bytes(
            {key: value for key, value in wrong_index.items() if key != "output_payload_sha256"}
        )
    )
    with pytest.raises(
        offline_scorer.OfflineScorerError,
        match="ROUTE_OUTPUT_INDEX_PAYLOAD_MISMATCH",
    ):
        offline_scorer.score_route_output(
            route_output=wrong_index,
            hidden_cells=hidden,
            catalogs=catalogs,
            expected_index_payload_sha256=expected_index_sha256,
        )


def test_score_freeze_rejects_route_manifest_budget_drift(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace_manifest = tmp_path / "workspace-manifest.json"
    prep = prepare_route_workspace.prepare_route_workspace(
        question_set_path=QUESTION_SET,
        catalog_dir=CATALOG_DIR,
        workspace=workspace,
        manifest_path=workspace_manifest,
    )
    run_dir = tmp_path / "run"
    route_runner.run_routes(
        workspace=workspace,
        preregistered_manifest_path=workspace_manifest,
        expected_manifest_sha256=prep["manifest_sha256"],
        output_dir=run_dir,
        route_ids=("A4h",),
    )
    route_manifest_path = run_dir / "route_manifests/A4h.json"
    route_manifest = json.loads(route_manifest_path.read_text(encoding="utf-8"))
    route_manifest["budgets"] = [*route_runner.BUDGETS[:-1], 2600]
    route_manifest["manifest_payload_sha256"] = route_runner.sha256_bytes(
        route_runner.canonical_bytes(
            {
                key: value
                for key, value in route_manifest.items()
                if key != "manifest_payload_sha256"
            }
        )
    )
    route_runner.write_json(route_manifest_path, route_manifest)
    receipt_path = run_dir / "route_run_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["route_manifests"][0]["sha256"] = route_runner.sha256_file(
        route_manifest_path
    )
    receipt["receipt_payload_sha256"] = route_runner.sha256_bytes(
        route_runner.canonical_bytes(
            {
                key: value
                for key, value in receipt.items()
                if key != "receipt_payload_sha256"
            }
        )
    )
    route_runner.write_json(receipt_path, receipt)
    with pytest.raises(
        offline_scorer.OfflineScorerError,
        match="ROUTE_MANIFEST_BUDGET_CONTRACT_MISMATCH",
    ):
        offline_scorer.freeze_score_bundle(
            sealed_outputs_dir=run_dir / "sealed_outputs",
            route_receipt_path=receipt_path,
            hidden_cells_path=HIDDEN_CELLS,
            catalog_dir=CATALOG_DIR,
            route_manifests_dir=run_dir / "route_manifests",
            output_path=run_dir / "score_bundle.json",
            scoring_executor_id="TEST-OFFLINE-SCORER",
        )


def test_score_freeze_rebuilds_sparse_index_from_catalogs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace_manifest = tmp_path / "workspace-manifest.json"
    prep = prepare_route_workspace.prepare_route_workspace(
        question_set_path=QUESTION_SET,
        catalog_dir=CATALOG_DIR,
        workspace=workspace,
        manifest_path=workspace_manifest,
    )
    run_dir = tmp_path / "run"
    route_runner.run_routes(
        workspace=workspace,
        preregistered_manifest_path=workspace_manifest,
        expected_manifest_sha256=prep["manifest_sha256"],
        output_dir=run_dir,
        route_ids=("A4h",),
    )
    index_path = run_dir / "route_assets/sparse_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["documents"][0]["char_count"] += 1
    index["index_payload_sha256"] = route_runner.sha256_bytes(
        route_runner.canonical_bytes(
            {
                key: value
                for key, value in index.items()
                if key != "index_payload_sha256"
            }
        )
    )
    route_runner.write_json(index_path, index)
    with pytest.raises(
        offline_scorer.OfflineScorerError,
        match="SPARSE_INDEX_REBUILD_MISMATCH",
    ):
        offline_scorer.freeze_score_bundle(
            sealed_outputs_dir=run_dir / "sealed_outputs",
            route_receipt_path=run_dir / "route_run_receipt.json",
            hidden_cells_path=HIDDEN_CELLS,
            catalog_dir=CATALOG_DIR,
            route_manifests_dir=run_dir / "route_manifests",
            output_path=run_dir / "score_bundle.json",
            scoring_executor_id="TEST-OFFLINE-SCORER",
        )


def test_offline_scorer_requires_all_source_groups() -> None:
    source_map = {"S1": "P1", "S2": "P2"}
    assert not offline_scorer._head_complete(
        retrieved_paragraphs={"P1"},
        source_id_groups=[["S1"], ["S2"]],
        source_paragraph_map=source_map,
    )
    assert offline_scorer._head_complete(
        retrieved_paragraphs={"P1", "P2"},
        source_id_groups=[["S1"], ["S2"]],
        source_paragraph_map=source_map,
    )
