from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from experiments.V02_R2_development_hardening_r01_20260727 import (
    qec_activate as qec,
    qec_experiment_runner,
    route_runner,
)


REPO = Path(__file__).resolve().parents[1]
PARENT = REPO / "runs/V02_R2_A8_event_graph_planner_ab_r01_20260727"
QEC_RUN = REPO / "runs/V02_R2_QEC_activate_ab_r01_20260727"
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
CONTRACT_SHA256 = "3ddeee4d8c7954d564642565396648c1b6e95b429ab5e58012389507c305f0e2"
ERRATA_SHA256 = "4cca82a0d1e3976509c9c4adc105895622034966dbd2ebeae079db16fc39940c"


@pytest.fixture(scope="module")
def qec_route_output(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("qec-route")
    receipt = route_runner.run_routes(
        workspace=PARENT / "preregistered_input_workspace",
        preregistered_manifest_path=PARENT / "preregistered/workspace_manifest.json",
        expected_manifest_sha256=(
            "06d57b3603f213093d25afa4eb8f5ce866843e658f2457148fc4c52e5718c0d2"
        ),
        output_dir=output,
        route_ids=("A5", "QEC"),
    )
    assert receipt["model_api_calls"] == 0
    assert receipt["network_calls"] == 0
    return output


def _plans() -> list[dict]:
    questions = json.loads(QUESTION_SET.read_text(encoding="utf-8"))["questions"]
    planner_sha = hashlib.sha256(Path(qec.__file__).read_bytes()).hexdigest()
    return [
        qec.build_question_plan(
            question_id=row["question_id"],
            question_text=row["question_text"],
            planner_artifact_sha256=planner_sha,
        )
        for row in questions
    ]


def test_t01_t02_public_plan_is_case_blind_and_id_independent() -> None:
    assert list(inspect.signature(qec.compile_public_question_plan).parameters) == [
        "question_text"
    ]
    text = "主角当前在哪里，处于什么状态？"
    planner_sha = "a" * 64
    first = qec.build_question_plan(
        question_id="R1-Q01", question_text=text, planner_artifact_sha256=planner_sha
    )
    renamed = qec.build_question_plan(
        question_id="RENAMED", question_text=text, planner_artifact_sha256=planner_sha
    )
    assert first["plan_body"] == renamed["plan_body"]
    assert first["plan_body_sha256"] == renamed["plan_body_sha256"]
    assert first["plan_body"]["fixed_conjuncts"] == ["LOCATION", "CURRENT_STATE"]


def test_t03_t04_plan_rejects_hidden_fields_and_answer_counts() -> None:
    plan = _plans()[0]
    hidden = copy.deepcopy(plan)
    hidden["plan_body"]["source_id"] = "FORBIDDEN"
    hidden["plan_body_sha256"] = qec.sha256_bytes(
        qec.canonical_bytes(hidden["plan_body"])
    )
    with pytest.raises(qec.QECError, match="QEC_FORBIDDEN_PLAN_KEY"):
        qec.validate_question_plan(hidden)
    counted = copy.deepcopy(plan)
    counted["plan_body"]["expected_count"] = 4
    counted["plan_body_sha256"] = qec.sha256_bytes(
        qec.canonical_bytes(counted["plan_body"])
    )
    with pytest.raises(qec.QECError):
        qec.validate_question_plan(counted)


def test_all_ten_public_question_kinds_compile_once() -> None:
    plans = _plans()
    assert len(plans) == 10
    assert len({row["plan_body"]["question_kind"] for row in plans}) == 10
    assert all(
        row["plan_body"]["count_policy"] == "NO_EXPECTED_ANSWER_COUNT"
        for row in plans
    )
    assert all(
        row["plan_body"]["completeness_policy"] == "NOT_SELF_CERTIFIED"
        for row in plans
    )


def test_t05_query_universe_keeps_order_text_and_duplicates(
    qec_route_output: Path,
) -> None:
    result = qec_experiment_runner._assert_query_universe(qec_route_output)
    assert result["cell_count"] == 30
    assert result["query_count"] == 810
    assert result["new_query_count"] == 0
    assert result["duplicate_query_occurrence_count"] > 0
    first = json.loads(
        (qec_route_output / "route_assets/query_maps/QEC.json").read_text(
            encoding="utf-8"
        )
    )["cells"][0]
    assert [row["query_id"] for row in first["queries"]] == [
        f"QRY-{index:03d}" for index in range(1, len(first["queries"]) + 1)
    ]


def test_rank_stream_freeze_has_expected_complete_counts_and_hash(
    qec_route_output: Path,
) -> None:
    errata = json.loads(
        (QEC_RUN / "preregistered/qec_contract_errata.json").read_text(
            encoding="utf-8"
        )
    )
    result = qec_experiment_runner._assert_rank_streams(
        errata=errata, run_dir=qec_route_output
    )
    assert result["cell_count"] == 30
    assert result["query_stream_count"] == 810
    assert result["rank_record_count"] == 59940


def test_qec_route_preserves_a5_and_emits_all_seven_budgets(
    qec_route_output: Path,
) -> None:
    for budget in route_runner.BUDGETS:
        assert (qec_route_output / f"sealed_outputs/A5/{budget}.json").read_bytes() == (
            PARENT / f"sealed_outputs/A5/{budget}.json"
        ).read_bytes()
        assert (
            qec_route_output
            / f"route_assets/selection_projections/A5/{budget}.json"
        ).read_bytes() == (
            PARENT / f"route_assets/selection_projections/A5/{budget}.json"
        ).read_bytes()
        candidate = json.loads(
            (qec_route_output / f"sealed_outputs/QEC/{budget}.json").read_text(
                encoding="utf-8"
            )
        )
        assert len(candidate["cells"]) == 30
        assert all(row["candidate_chars"] <= budget for row in candidate["cells"])
    manifest = json.loads(
        (qec_route_output / "route_manifests/QEC.json").read_text(encoding="utf-8")
    )
    assert manifest["parent_route_id"] == "A5"
    assert manifest["single_change"] == (
        "QUESTION_STATE_FEEDBACK_ON_FROZEN_A5_QUERY_RANK_STREAMS_ONLY"
    )


def test_t06_t07_t08_trace_replays_and_rejects_tamper(
    qec_route_output: Path,
) -> None:
    collection = json.loads(
        (qec_route_output / "route_assets/qec/traces/QEC/600.json").read_text(
            encoding="utf-8"
        )
    )
    trace = collection["cells"][0]
    case_id = trace["cell_id"].split("::", 1)[0]
    catalog = json.loads((CATALOG_DIR / f"{case_id}.json").read_text(encoding="utf-8"))
    paragraph_text = {
        row["paragraph_id"]: row["original_text"] for row in catalog["paragraphs"]
    }
    qec.validate_trace(trace, paragraph_text_by_id=paragraph_text)
    assert trace["candidate_source_chars"] <= trace["budget_chars"]
    tampered = copy.deepcopy(trace)
    tampered["selected_window_ids"] = list(reversed(tampered["selected_window_ids"]))
    tampered.pop("trace_payload_sha256")
    tampered["trace_payload_sha256"] = qec.sha256_bytes(qec.canonical_bytes(tampered))
    with pytest.raises(qec.QECError, match="QEC_TRACE_SELECTED_REPLAY_MISMATCH"):
        qec.validate_trace(tampered, paragraph_text_by_id=paragraph_text)


def test_t09_t10_t11_evidence_and_answer_contract_reject_false_tickets(
    qec_route_output: Path,
) -> None:
    traces = json.loads(
        (qec_route_output / "route_assets/qec/traces/QEC/900.json").read_text(
            encoding="utf-8"
        )
    )["cells"]
    evidence_cells = json.loads(
        (qec_route_output / "route_assets/qec/evidence/QEC/900.json").read_text(
            encoding="utf-8"
        )
    )["cells"]
    answers = json.loads(
        (qec_route_output / "route_assets/qec/answers/QEC/900.json").read_text(
            encoding="utf-8"
        )
    )["cells"]
    evidence_by_cell = {row["cell_id"]: row["records"] for row in evidence_cells}
    chosen = next(trace for trace in traces if evidence_by_cell[trace["cell_id"]])
    records = evidence_by_cell[chosen["cell_id"]]
    case_id = chosen["cell_id"].split("::", 1)[0]
    catalog = json.loads((CATALOG_DIR / f"{case_id}.json").read_text(encoding="utf-8"))
    qec.validate_evidence_records(records, trace=chosen, catalog=catalog)
    forged = copy.deepcopy(records)
    forged[0]["text"] += "伪"
    forged[0]["text_sha256"] = qec.sha256_bytes(forged[0]["text"].encode())
    with pytest.raises(qec.QECError, match="QEC_EVIDENCE_PROGRAM_BACKFILL_MISMATCH"):
        qec.validate_evidence_records(forged, trace=chosen, catalog=catalog)
    plan = next(row for row in _plans() if row["question_id"] == chosen["question_id"])
    answer = next(row for row in answers if row["cell_id"] == chosen["cell_id"])
    qec.validate_answer(answer, plan=plan, evidence_records=records)
    self_signed = copy.deepcopy(answer)
    self_signed["is_correct"] = True
    with pytest.raises(qec.QECError, match="QEC_ANSWER_FIELDS_OR_SCHEMA_INVALID"):
        qec.validate_answer(self_signed, plan=plan, evidence_records=records)


def test_t12_primary_decision_cuts_local_false_win() -> None:
    contract = json.loads(
        (QEC_RUN / "preregistered/qec_experiment_contract.json").read_text(
            encoding="utf-8"
        )
    )
    synthetic = {
        "full_question_recall_count": 17,
        "required_head_recall_count": 78,
        "per_case": {
            "B01-U0033": {"question_hits": 1, "head_hits": 18},
            "B02-U0039": {"question_hits": 8, "head_hits": 19},
            "B03-U0041": {"question_hits": 8, "head_hits": 42},
        },
    }
    decision = qec.decide_primary(contract=contract, score_row=synthetic)
    assert decision["disposition"] == "CUT_B02_REGRESSION"
    assert decision["register_candidate"] is False


def test_frozen_a5_functions_and_contracts_are_still_exact() -> None:
    contract, errata = qec_experiment_runner.load_contracts(
        contract_path=QEC_RUN / "preregistered/qec_experiment_contract.json",
        expected_contract_sha256=CONTRACT_SHA256,
        errata_path=QEC_RUN / "preregistered/qec_contract_errata.json",
        expected_errata_sha256=ERRATA_SHA256,
    )
    functions = {
        "build_sparse_index": route_runner.build_sparse_index,
        "rank_paragraphs": route_runner.rank_paragraphs,
        "merge_rankings_nonzero_fusion": route_runner._merge_rankings_nonzero_fusion,
        "pack_nonzero_fusion": route_runner._pack_nonzero_fusion,
        "selection_projection": route_runner.selection_projection,
        "a5_query_variants": route_runner._query_variants,
    }
    for name, function in functions.items():
        assert hashlib.sha256(inspect.getsource(function).encode()).hexdigest() == (
            contract["frozen_function_sha256"][name]
        )
    assert errata["rank_stream_freeze"]["required_generation_runs"] == 2


def test_baseline_verification_passes_without_opening_hidden_semantics() -> None:
    contract, errata = qec_experiment_runner.load_contracts(
        contract_path=QEC_RUN / "preregistered/qec_experiment_contract.json",
        expected_contract_sha256=CONTRACT_SHA256,
        errata_path=QEC_RUN / "preregistered/qec_contract_errata.json",
        expected_errata_sha256=ERRATA_SHA256,
    )
    result = qec_experiment_runner.verify_frozen_baseline(
        contract=contract,
        errata=errata,
        repo=REPO,
        question_set_path=QUESTION_SET,
        catalog_dir=CATALOG_DIR,
        hidden_cells_path=HIDDEN_CELLS,
    )
    assert result["status"] == "PASS"
    assert result["function_checks"]["rank_paragraphs"] == (
        contract["frozen_function_sha256"]["rank_paragraphs"]
    )
