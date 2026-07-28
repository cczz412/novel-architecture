from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from experiments.V02_R2_development_hardening_r01_20260727 import (
    a8_experiment_runner,
    event_graph_planner,
    prepare_route_workspace,
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
BASELINE_RUN = REPO / "runs/V02_R2_A5_A7_obligation_planner_ab_r01_20260727"
A8_RUN = REPO / "runs/V02_R2_A8_event_graph_planner_ab_r01_20260727"
A8_FROZEN_ENVIRONMENT = (
    REPO / "tests/fixtures/a8_frozen_environment_20260727"
)
CONTRACT_PATH = A8_RUN / "preregistered/event_graph_contract.json"
CONTRACT_SHA256 = "f6b0849d448454cdd8e633a3fd3eb047bf92dd2f306f366b04cfa26697758fab"
EXPERIMENT_CONTRACT_SHA256 = (
    "3913d9d565d43d021aae742b55e7e0ad2602a0174239abfa1a80f5db5f0a3a96"
)


def _contract() -> dict:
    return event_graph_planner.load_contract(
        CONTRACT_PATH,
        expected_sha256=CONTRACT_SHA256,
    )


def _planner_source(case_id: str = "B02-U0039") -> dict:
    catalog = json.loads((CATALOG_DIR / f"{case_id}.json").read_text("utf-8"))
    return route_runner._planner_visible_source_projection(catalog)


def _rehash_graph(graph: dict) -> None:
    graph.pop("graph_payload_sha256", None)
    graph["graph_payload_sha256"] = event_graph_planner.sha256_bytes(
        event_graph_planner.canonical_bytes(graph)
    )


def _synthetic_source(text: str) -> dict:
    source_id = "SYNTHETIC-SOURCE"
    source = {
        "schema_version": "r2-planner-visible-source.v1",
        "source_id": source_id,
        "source_body_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "source_text": text,
        "paragraphs": [
            {
                "paragraph_id": f"{source_id}-P0001",
                "char_start": 0,
                "char_end_exclusive": len(text),
                "original_text": text,
            }
        ],
        "sentences": [
            {
                "sentence_id": f"{source_id}-S0001",
                "paragraph_id": f"{source_id}-P0001",
                "char_start": 0,
                "char_end_exclusive": len(text),
                "original_text": text,
            }
        ],
    }
    source["projection_payload_sha256"] = hashlib.sha256(
        event_graph_planner.canonical_bytes(source)
    ).hexdigest()
    return source


def test_a8_graph_is_question_independent_deterministic_and_exact() -> None:
    source = _planner_source()
    first = event_graph_planner.build_event_graph(source, _contract())
    second = event_graph_planner.build_event_graph(source, _contract())
    assert event_graph_planner.canonical_bytes(first) == (
        event_graph_planner.canonical_bytes(second)
    )
    serialized = json.dumps(first, ensure_ascii=False)
    assert "question_id" not in serialized
    assert "required_heads" not in serialized
    assert "source_id_groups" not in serialized
    assert first["semantic_truth_verified_by_program"] is False
    assert first["nodes"]
    assert first["edges"]
    assert {row["relation"] for row in first["edges"]} <= {
        "ACTOR_OF",
        "EXPERIENCER_OF",
        "CONTENT_OF",
        "CAUSES",
    }


def test_a8_query_map_preserves_a5_prefix_and_zero_trigger_fallback() -> None:
    source = _planner_source()
    contract = _contract()
    graph = event_graph_planner.build_event_graph(source, contract)
    question = {
        "question_id": "TEST-Q",
        "question_text": "本章新增了哪些目标、计划、承诺或威胁？",
    }
    plan = route_runner.plan_question(question["question_text"])
    a5 = route_runner._query_variants(
        route_id="A5",
        question_text=question["question_text"],
        plan=plan,
        aliases=[],
        case_id=source["source_id"],
    )
    trigger = event_graph_planner.compile_event_queries(
        question=question,
        graph=graph,
        contract=contract,
    )
    query_map = event_graph_planner.build_a8_query_map(
        case_id=source["source_id"],
        question_id=question["question_id"],
        a5_queries=a5,
        trigger=trigger,
    )
    assert [row["query_text"] for row in query_map["queries"][: len(a5)]] == a5
    assert all(
        row["origin_kind"] == "A5_FROZEN_PREFIX"
        for row in query_map["queries"][: len(a5)]
    )

    zero_question = {
        "question_id": "TEST-ZERO",
        "question_text": "请概括本章的颜色。",
    }
    zero_trigger = event_graph_planner.compile_event_queries(
        question=zero_question,
        graph=graph,
        contract=contract,
    )
    zero_map = event_graph_planner.build_a8_query_map(
        case_id=source["source_id"],
        question_id=zero_question["question_id"],
        a5_queries=a5,
        trigger=zero_trigger,
    )
    assert zero_map["event_query_count"] == 0
    assert [row["query_text"] for row in zero_map["queries"]] == a5


def test_a8_graph_rejects_unknown_field_and_source_span_tamper() -> None:
    source = _planner_source()
    contract = _contract()
    graph = event_graph_planner.build_event_graph(source, contract)

    unknown = copy.deepcopy(graph)
    unknown["nodes"][0]["harmless_extra"] = "NO"
    _rehash_graph(unknown)
    with pytest.raises(
        event_graph_planner.A8EventGraphError,
        match="A8_GRAPH_NODE_FIELDS_INVALID",
    ):
        event_graph_planner.validate_event_graph(
            unknown,
            planner_source=source,
            contract=contract,
        )

    tampered = copy.deepcopy(graph)
    node = next(row for row in tampered["nodes"] if row["kind"] == "EVENT")
    node["query_span"]["char_start"] += 1
    _rehash_graph(tampered)
    with pytest.raises(
        event_graph_planner.A8EventGraphError,
        match="A8_EVIDENCE_SPAN_REBUILD_MISMATCH",
    ):
        event_graph_planner.validate_event_graph(
            tampered,
            planner_source=source,
            contract=contract,
        )


def test_a8_same_surface_mentions_are_not_canonicalized() -> None:
    source = _synthetic_source("甲决定离开，甲决定留下。")
    graph = event_graph_planner.build_event_graph(source, _contract())
    mentions = [row for row in graph["nodes"] if row["kind"] == "MENTION"]
    exact_name_mentions = [
        row
        for row in mentions
        if row["evidence_spans"][0]["surface_text"] == "甲"
    ]
    assert len(exact_name_mentions) == 2
    assert len({row["node_id"] for row in exact_name_mentions}) == 2
    serialized = json.dumps(graph, ensure_ascii=False)
    assert "canonical_entity_id" not in serialized
    assert "coreference_cluster_id" not in serialized


def test_a8_route_keeps_frozen_a5_outputs_and_stays_zero_api(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    manifest = tmp_path / "workspace_manifest.json"
    prep = prepare_route_workspace.prepare_route_workspace(
        question_set_path=QUESTION_SET,
        catalog_dir=CATALOG_DIR,
        workspace=workspace,
        manifest_path=manifest,
    )
    run_dir = tmp_path / "a8"
    receipt = route_runner.run_routes(
        workspace=workspace,
        preregistered_manifest_path=manifest,
        expected_manifest_sha256=prep["manifest_sha256"],
        output_dir=run_dir,
        route_ids=("A5", "A8"),
        a8_event_graph_contract_path=CONTRACT_PATH,
        expected_a8_event_graph_contract_sha256=CONTRACT_SHA256,
    )
    assert receipt["model_api_calls"] == 0
    assert receipt["network_calls"] == 0
    for budget in route_runner.BUDGETS:
        assert (run_dir / f"sealed_outputs/A5/{budget}.json").read_bytes() == (
            BASELINE_RUN / f"sealed_outputs/A5/{budget}.json"
        ).read_bytes()
        assert (
            run_dir / f"route_assets/selection_projections/A5/{budget}.json"
        ).read_bytes() == (
            BASELINE_RUN
            / f"route_assets/selection_projections/A5/{budget}.json"
        ).read_bytes()
    assert (
        run_dir / "route_assets/event_graphs/A8_collection.json"
    ).is_file()
    assert (run_dir / "route_assets/event_triggers/A8.json").is_file()
    a8_manifest = json.loads(
        (run_dir / "route_manifests/A8.json").read_text(encoding="utf-8")
    )
    assert a8_manifest["parent_route_id"] == "A5"
    assert a8_manifest["single_change"] == (
        "A5_FROZEN_QUERY_PREFIX_PLUS_EXACT_RELATION_QUERY_APPEND_ONLY"
    )


def test_a8_frozen_downstream_function_hashes_stay_unchanged() -> None:
    contract = json.loads(
        (A8_RUN / "preregistered/a8_experiment_contract.json").read_text(
            encoding="utf-8"
        )
    )
    expected = contract["frozen_function_sha256"]
    functions = {
        "build_sparse_index": route_runner.build_sparse_index,
        "rank_paragraphs": route_runner.rank_paragraphs,
        "merge_rankings_nonzero_fusion": (
            route_runner._merge_rankings_nonzero_fusion
        ),
        "pack_nonzero_fusion": route_runner._pack_nonzero_fusion,
        "selection_projection": route_runner.selection_projection,
        "a5_query_variants": route_runner._query_variants,
    }
    for key, function in functions.items():
        actual = hashlib.sha256(inspect.getsource(function).encode()).hexdigest()
        assert actual == expected[key]


def test_a8_official_runner_verifies_frozen_baseline_before_score() -> None:
    contract_path = A8_RUN / "preregistered/a8_experiment_contract.json"
    contract = a8_experiment_runner.load_experiment_contract(
        contract_path,
        expected_sha256=EXPERIMENT_CONTRACT_SHA256,
    )
    receipt = a8_experiment_runner.verify_frozen_baseline(
        contract=contract,
        repo=REPO,
        environment_snapshot_root=A8_FROZEN_ENVIRONMENT,
    )
    assert receipt["status"] == "PASS"
    assert len(receipt["budget_checks"]) == 7
    assert receipt["environment_checks"] == contract["environment_sha256"]
    assert receipt["function_checks"]["offline_scorer_file"] == (
        contract["frozen_function_sha256"]["offline_scorer_file"]
    )


def test_a8_active_verification_rejects_current_environment_migration() -> None:
    contract_path = A8_RUN / "preregistered/a8_experiment_contract.json"
    contract = a8_experiment_runner.load_experiment_contract(
        contract_path,
        expected_sha256=EXPERIMENT_CONTRACT_SHA256,
    )
    with pytest.raises(
        a8_experiment_runner.A8ExperimentError,
        match=r"A8_ENVIRONMENT_DRIFT:\.python-version",
    ):
        a8_experiment_runner.verify_frozen_baseline(
            contract=contract,
            repo=REPO,
        )


def test_a8_primary_decision_requires_b01_complete_question_gain() -> None:
    contract = json.loads(
        (A8_RUN / "preregistered/a8_experiment_contract.json").read_text(
            encoding="utf-8"
        )
    )
    score = {
        "rows": [
            {
                "route_id": "A8",
                "budget_chars": 2500,
                "full_question_recall_count": 16,
                "required_head_recall_count": 78,
                "per_case": {
                    "B01-U0033": {
                        "question_hits": 0,
                        "head_hits": 17,
                    },
                    "B02-U0039": {
                        "question_hits": 9,
                        "head_hits": 19,
                    },
                    "B03-U0041": {
                        "question_hits": 7,
                        "head_hits": 42,
                    },
                },
            }
        ]
    }
    decision = a8_experiment_runner.evaluate_primary_decision(
        contract=contract,
        score=score,
    )
    assert decision["hard_cut_pass"] is True
    assert decision["a10_eligible"] is False
    assert decision["disposition"] == "CUT_NO_B01_COMPLETE_QUESTION_GAIN"
