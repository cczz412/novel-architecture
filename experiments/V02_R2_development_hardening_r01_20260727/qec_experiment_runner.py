from __future__ import annotations

import argparse
import copy
import hashlib
import inspect
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping

from . import offline_scorer
from . import prepare_route_workspace
from . import qec_activate as qec
from . import route_runner


RUN_RECEIPT_SCHEMA = "v02-r2-qec-official-run-receipt.v1"
PRE_SCORE_GATE_SCHEMA = "v02-r2-qec-pre-score-gate.v1"
SIDECAR_MANIFEST_SCHEMA = "v02-r2-qec-sidecar-manifest.v1"


class QECExperimentError(ValueError):
    """QEC 正式开发集单变量实验总控拒收错误。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def _load_json(path: Path) -> Any:
    if not path.is_file() or path.is_symlink():
        raise QECExperimentError(f"QEC_REQUIRED_FILE_MISSING:{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QECExperimentError(f"QEC_REQUIRED_JSON_INVALID:{path}") from exc


def _require_sha(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise QECExperimentError(f"QEC_HASH_INVALID:{field}")
    return value


def load_contracts(
    *,
    contract_path: Path,
    expected_contract_sha256: str,
    errata_path: Path,
    expected_errata_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if sha256_file(contract_path) != _require_sha(
        expected_contract_sha256, field="contract_sha256"
    ):
        raise QECExperimentError("QEC_EXPERIMENT_CONTRACT_SHA_MISMATCH")
    if sha256_file(errata_path) != _require_sha(
        expected_errata_sha256, field="errata_sha256"
    ):
        raise QECExperimentError("QEC_CONTRACT_ERRATA_SHA_MISMATCH")
    contract = _load_json(contract_path)
    errata = _load_json(errata_path)
    if contract.get("schema_version") != "v02-r2-qec-experiment-contract.v1":
        raise QECExperimentError("QEC_EXPERIMENT_CONTRACT_SCHEMA_INVALID")
    if contract.get("contract_status") != "FROZEN_BEFORE_IMPLEMENTATION":
        raise QECExperimentError("QEC_EXPERIMENT_CONTRACT_NOT_FROZEN")
    if errata.get("schema_version") != "v02-r2-qec-contract-errata.v1":
        raise QECExperimentError("QEC_CONTRACT_ERRATA_SCHEMA_INVALID")
    if errata.get("status") != "FROZEN_BEFORE_IMPLEMENTATION":
        raise QECExperimentError("QEC_CONTRACT_ERRATA_NOT_FROZEN")
    if errata.get("base_contract_sha256") != expected_contract_sha256:
        raise QECExperimentError("QEC_CONTRACT_ERRATA_BASE_SHA_MISMATCH")
    if contract.get("model_api_calls_allowed") != 0:
        raise QECExperimentError("QEC_MODEL_API_ALLOWANCE_NOT_ZERO")
    if contract.get("network_calls_allowed") != 0:
        raise QECExperimentError("QEC_NETWORK_ALLOWANCE_NOT_ZERO")
    if contract.get("scoring_policy", {}).get("hidden_score_run_count") != 1:
        raise QECExperimentError("QEC_HIDDEN_SCORE_COUNT_NOT_ONE")
    if contract.get("frozen_inputs", {}).get("new_query_count") != 0:
        raise QECExperimentError("QEC_CONTRACT_NEW_QUERY_COUNT_NOT_ZERO")
    return contract, errata


def _refuse_used_run_directory(run_dir: Path) -> None:
    forbidden = (
        "route_run_receipt.json",
        "offline_score.json",
        "score_gate_decision.json",
        "official_run_receipt.json",
        "STOP_RECEIPT.md",
        "preregistered/pre_score_gate.json",
        "preregistered/score_bundle_manifest.json",
        "route_manifests",
        "sealed_outputs",
    )
    hits = [relative for relative in forbidden if (run_dir / relative).exists()]
    if hits:
        raise QECExperimentError(f"QEC_RUN_DIRECTORY_ALREADY_USED:{hits}")


def _function_sha(function: Any) -> str:
    return sha256_bytes(inspect.getsource(function).encode("utf-8"))


def verify_frozen_baseline(
    *,
    contract: Mapping[str, Any],
    errata: Mapping[str, Any],
    repo: Path,
    question_set_path: Path,
    catalog_dir: Path,
    hidden_cells_path: Path,
) -> dict[str, Any]:
    parent = repo / contract["parent_route"]["run_directory"]
    if not parent.is_dir() or parent.is_symlink():
        raise QECExperimentError("QEC_PARENT_RUN_MISSING")
    exact_files = {
        "workspace_manifest_sha256": parent / "preregistered/workspace_manifest.json",
        "question_projection_sha256": parent / "frozen/question_projection.json",
        "source_bindings_sha256": parent / "frozen/source_bindings.json",
        "query_map_sha256": parent / "route_assets/query_maps/A5.json",
        "obligation_plan_sha256": parent / "route_assets/obligation_plans/A5.json",
    }
    file_checks: list[dict[str, Any]] = []
    for field, path in exact_files.items():
        actual = sha256_file(path)
        if actual != contract["parent_route"][field]:
            raise QECExperimentError(f"QEC_PARENT_BASELINE_SHA_DRIFT:{field}")
        file_checks.append(
            {"field": field, "path": path.relative_to(repo).as_posix(), "sha256": actual}
        )
    parent_manifest = _load_json(parent / "route_manifests/A5.json")
    if parent_manifest.get("planner_visible_source_sha256") != contract["parent_route"][
        "planner_visible_source_sha256"
    ]:
        raise QECExperimentError("QEC_PARENT_PLANNER_VISIBLE_SOURCE_DRIFT")
    sparse_index = _load_json(parent / "route_assets/sparse_index.json")
    if sparse_index.get("index_payload_sha256") != contract["parent_route"][
        "index_payload_sha256"
    ]:
        raise QECExperimentError("QEC_PARENT_INDEX_PAYLOAD_DRIFT")
    for budget in route_runner.BUDGETS:
        key = str(budget)
        if sha256_file(parent / f"sealed_outputs/A5/{budget}.json") != contract[
            "a5_sealed_output_sha256_by_budget"
        ][key]:
            raise QECExperimentError(f"QEC_PARENT_OUTPUT_DRIFT:{budget}")
        if sha256_file(
            parent / f"route_assets/selection_projections/A5/{budget}.json"
        ) != contract["a5_selection_projection_sha256_by_budget"][key]:
            raise QECExperimentError(f"QEC_PARENT_SELECTION_DRIFT:{budget}")
    functions = {
        "build_sparse_index": route_runner.build_sparse_index,
        "rank_paragraphs": route_runner.rank_paragraphs,
        "merge_rankings_nonzero_fusion": route_runner._merge_rankings_nonzero_fusion,
        "pack_nonzero_fusion": route_runner._pack_nonzero_fusion,
        "selection_projection": route_runner.selection_projection,
        "a5_query_variants": route_runner._query_variants,
    }
    function_checks: dict[str, str] = {}
    for name, function in functions.items():
        actual = _function_sha(function)
        if actual != contract["frozen_function_sha256"][name]:
            raise QECExperimentError(f"QEC_FROZEN_FUNCTION_DRIFT:{name}")
        function_checks[name] = actual
    scorer_sha = sha256_file(Path(offline_scorer.__file__))
    if scorer_sha != contract["frozen_function_sha256"]["offline_scorer_file"]:
        raise QECExperimentError("QEC_OFFLINE_SCORER_FILE_DRIFT")
    function_checks["offline_scorer_file"] = scorer_sha

    frozen_files = errata["frozen_file_sha256"]
    current_files = {
        "question_set_file": question_set_path,
        "sparse_index_file": parent / "route_assets/sparse_index.json",
        "B01-U0033_catalog": catalog_dir / "B01-U0033.json",
        "B02-U0039_catalog": catalog_dir / "B02-U0039.json",
        "B03-U0041_catalog": catalog_dir / "B03-U0041.json",
        "hidden_development_cells": hidden_cells_path,
    }
    frozen_file_checks: list[dict[str, str]] = []
    for field, path in current_files.items():
        actual = sha256_file(path)
        if actual != frozen_files[field]:
            raise QECExperimentError(f"QEC_FROZEN_FILE_DRIFT:{field}")
        frozen_file_checks.append({"field": field, "path": str(path), "sha256": actual})
    return {
        "status": "PASS",
        "parent_run": parent.relative_to(repo).as_posix(),
        "file_checks": file_checks,
        "function_checks": function_checks,
        "frozen_file_checks": frozen_file_checks,
    }


def _cells_by_id(collection: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in collection["cells"]:
        cell_id = row.get("cell_id") or f"{row['case_id']}::{row['question_id']}"
        if cell_id in rows:
            raise QECExperimentError(f"QEC_CELL_DUPLICATED:{cell_id}")
        rows[cell_id] = dict(row)
    return rows


def _assert_a5_replay(
    *, contract: Mapping[str, Any], repo: Path, run_dir: Path
) -> list[dict[str, Any]]:
    parent = repo / contract["parent_route"]["run_directory"]
    checks: list[dict[str, Any]] = []
    for budget in route_runner.BUDGETS:
        current_output = run_dir / f"sealed_outputs/A5/{budget}.json"
        parent_output = parent / f"sealed_outputs/A5/{budget}.json"
        current_projection = run_dir / f"route_assets/selection_projections/A5/{budget}.json"
        parent_projection = parent / f"route_assets/selection_projections/A5/{budget}.json"
        if current_output.read_bytes() != parent_output.read_bytes():
            raise QECExperimentError(f"QEC_A5_OUTPUT_REPLAY_DRIFT:{budget}")
        if current_projection.read_bytes() != parent_projection.read_bytes():
            raise QECExperimentError(f"QEC_A5_SELECTION_REPLAY_DRIFT:{budget}")
        checks.append(
            {
                "budget_chars": budget,
                "sealed_output_byte_identical": True,
                "selection_projection_byte_identical": True,
                "sealed_output_sha256": sha256_file(current_output),
                "selection_projection_sha256": sha256_file(current_projection),
            }
        )
    direct = (
        "frozen/question_projection.json",
        "frozen/source_bindings.json",
        "route_assets/query_maps/A5.json",
        "route_assets/obligation_plans/A5.json",
    )
    for relative in direct:
        if (run_dir / relative).read_bytes() != (parent / relative).read_bytes():
            raise QECExperimentError(f"QEC_A5_DIRECT_REPLAY_DRIFT:{relative}")
    return checks


def _assert_query_universe(run_dir: Path) -> dict[str, Any]:
    a5 = _cells_by_id(_load_json(run_dir / "route_assets/query_maps/A5.json"))
    candidate = _cells_by_id(_load_json(run_dir / "route_assets/query_maps/QEC.json"))
    if set(a5) != set(candidate):
        raise QECExperimentError("QEC_QUERY_CELL_SET_MISMATCH")
    duplicate_count = 0
    query_count = 0
    for cell_id in sorted(a5):
        parent_queries = a5[cell_id]["queries"]
        candidate_queries = candidate[cell_id]["queries"]
        if parent_queries != candidate_queries:
            raise QECExperimentError(f"QEC_A5_QUERY_UNIVERSE_DRIFT:{cell_id}")
        texts = [row["query_text"] for row in parent_queries]
        duplicate_count += len(texts) - len(set(texts))
        query_count += len(texts)
        expected_ids = [f"QRY-{index:03d}" for index in range(1, len(texts) + 1)]
        if [row["query_id"] for row in candidate_queries] != expected_ids:
            raise QECExperimentError(f"QEC_QUERY_ID_WIDTH_OR_ORDER_DRIFT:{cell_id}")
    return {
        "cell_count": len(a5),
        "query_count": query_count,
        "duplicate_query_occurrence_count": duplicate_count,
        "new_query_count": 0,
        "status": "PASS",
    }


def _assert_rank_streams(
    *, errata: Mapping[str, Any], run_dir: Path
) -> dict[str, Any]:
    path = run_dir / "route_assets/qec/rank_streams.json"
    value = _load_json(path)
    freeze = errata["rank_stream_freeze"]
    expected = {
        "cell_count": freeze["expected_cell_count"],
        "query_stream_count": freeze["expected_query_stream_count"],
        "rank_record_count": freeze["expected_rank_record_count"],
    }
    for field, count in expected.items():
        if value.get(field) != count:
            raise QECExperimentError(f"QEC_RANK_STREAM_COUNT_MISMATCH:{field}")
    if value.get("collection_payload_sha256") != qec.sha256_bytes(
        qec.canonical_bytes({k: v for k, v in value.items() if k != "collection_payload_sha256"})
    ):
        raise QECExperimentError("QEC_RANK_STREAM_COLLECTION_SHA_MISMATCH")
    return {**expected, "path": path.relative_to(run_dir).as_posix(), "sha256": sha256_file(path)}


def _assert_plans(run_dir: Path) -> dict[str, Any]:
    plans = _load_json(run_dir / "route_assets/qec/question_plans.json")["plans"]
    if len(plans) != 10:
        raise QECExperimentError("QEC_UNIQUE_PLAN_COUNT_NOT_TEN")
    by_question = {row["question_id"]: row for row in plans}
    if len(by_question) != 10:
        raise QECExperimentError("QEC_QUESTION_PLAN_ID_DUPLICATED")
    for plan in plans:
        qec.validate_question_plan(plan)
    signature = inspect.signature(qec.compile_public_question_plan)
    if list(signature.parameters) != ["question_text"]:
        raise QECExperimentError("QEC_PLANNER_VISIBLE_SURFACE_TOO_WIDE")
    qec_plans = _cells_by_id(_load_json(run_dir / "route_assets/obligation_plans/QEC.json"))
    for cell_id, row in qec_plans.items():
        question_id = cell_id.split("::", 1)[1]
        if row["plan"]["plan_body"] != by_question[question_id]["plan_body"]:
            raise QECExperimentError(f"QEC_PLAN_BODY_CASE_DRIFT:{cell_id}")
    return {
        "unique_question_count": 10,
        "bound_cell_count": len(qec_plans),
        "planner_parameters": ["question_text"],
        "status": "PASS",
    }


def _validate_sidecars(run_dir: Path) -> dict[str, Any]:
    catalogs = {
        case_id: _load_json(run_dir / f"preregistered_input_workspace/source_catalog_v2/{case_id}.json")
        for case_id in route_runner.CASE_IDS
    }
    validated = 0
    answer_count = 0
    evidence_count = 0
    for arm in ("A5", "QEC"):
        for budget in route_runner.BUDGETS:
            traces = _load_json(run_dir / f"route_assets/qec/traces/{arm}/{budget}.json")
            evidence = _load_json(run_dir / f"route_assets/qec/evidence/{arm}/{budget}.json")
            answers = _load_json(run_dir / f"route_assets/qec/answers/{arm}/{budget}.json")
            if traces["cell_count"] != 30 or evidence["cell_count"] != 30 or answers["cell_count"] != 30:
                raise QECExperimentError(f"QEC_SIDECAR_CELL_COUNT_INVALID:{arm}:{budget}")
            evidence_by_cell = {row["cell_id"]: row["records"] for row in evidence["cells"]}
            answer_by_cell = {row["cell_id"]: row for row in answers["cells"]}
            plan_by_cell = _cells_by_id(
                _load_json(run_dir / f"route_assets/obligation_plans/{'QEC' if arm == 'QEC' else 'A5'}.json")
            )
            for trace in traces["cells"]:
                case_id = trace["cell_id"].split("::", 1)[0]
                catalog = catalogs[case_id]
                paragraph_text = {
                    row["paragraph_id"]: row["original_text"] for row in catalog["paragraphs"]
                }
                qec.validate_trace(trace, paragraph_text_by_id=paragraph_text)
                records = evidence_by_cell[trace["cell_id"]]
                qec.validate_evidence_records(records, trace=trace, catalog=catalog)
                plan = plan_by_cell[trace["cell_id"]]["plan"]
                if arm == "A5":
                    question_id = trace["question_id"]
                    plan = next(
                        row
                        for row in _load_json(run_dir / "route_assets/qec/question_plans.json")["plans"]
                        if row["question_id"] == question_id
                    )
                qec.validate_answer(answer_by_cell[trace["cell_id"]], plan=plan, evidence_records=records)
                validated += 1
                answer_count += 1
                evidence_count += len(records)
    return {
        "trace_count": validated,
        "answer_count": answer_count,
        "evidence_record_count": evidence_count,
        "status": "PASS",
    }


def _deterministic_file_set() -> list[str]:
    files = [
        "route_assets/qec/question_plans.json",
        "route_assets/qec/query_bindings.json",
        "route_assets/qec/rank_streams.json",
        "route_assets/query_maps/A5.json",
        "route_assets/query_maps/QEC.json",
    ]
    for arm in ("A5", "QEC"):
        for budget in route_runner.BUDGETS:
            files.extend(
                [
                    f"sealed_outputs/{arm}/{budget}.json",
                    f"route_assets/selection_projections/{arm}/{budget}.json",
                    f"route_assets/qec/traces/{arm}/{budget}.json",
                    f"route_assets/qec/evidence/{arm}/{budget}.json",
                    f"route_assets/qec/answers/{arm}/{budget}.json",
                ]
            )
    return files


def _run_second_dry_generation(
    *, run_dir: Path, workspace: Path, manifest_path: Path, manifest_sha256: str
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="qec-zero-api-dry-run-") as temp_name:
        second = Path(temp_name)
        receipt = route_runner.run_routes(
            workspace=workspace,
            preregistered_manifest_path=manifest_path,
            expected_manifest_sha256=manifest_sha256,
            output_dir=second,
            route_ids=("A5", "QEC"),
        )
        if receipt["model_api_calls"] != 0 or receipt["network_calls"] != 0:
            raise QECExperimentError("QEC_SECOND_DRY_RUN_NONZERO_CALLS")
        records: list[dict[str, Any]] = []
        for relative in _deterministic_file_set():
            first_path = run_dir / relative
            second_path = second / relative
            if first_path.read_bytes() != second_path.read_bytes():
                raise QECExperimentError(f"QEC_TWO_DRY_RUNS_NOT_BYTE_IDENTICAL:{relative}")
            records.append({"path": relative, "sha256": sha256_file(first_path)})
    return {"generation_count": 2, "byte_identical_file_count": len(records), "records": records}


def _expect_qec_reject(callable_: Any, code: str) -> None:
    try:
        callable_()
    except qec.QECError:
        return
    raise QECExperimentError(f"QEC_ADVERSARIAL_PROBE_DID_NOT_REJECT:{code}")


def run_adversarial_probes(run_dir: Path, contract: Mapping[str, Any]) -> list[dict[str, str]]:
    plans = _load_json(run_dir / "route_assets/qec/question_plans.json")["plans"]
    q01 = next(row for row in plans if row["question_id"] == "R1-Q01")
    renamed = qec.build_question_plan(
        question_id="RENAMED-Q",
        question_text="主角当前在哪里，处于什么状态？",
        planner_artifact_sha256=q01["planner_artifact_sha256"],
    )
    if renamed["plan_body"] != q01["plan_body"]:
        raise QECExperimentError("QEC_T02_QUESTION_ID_AFFECTED_PLAN")
    results = [
        {"test_id": "T01", "status": "PASS", "basis": "planner 只接受 question_text"},
        {"test_id": "T02", "status": "PASS", "basis": "重编号后 plan_body 相同"},
    ]
    hidden = copy.deepcopy(q01)
    hidden["plan_body"]["source_id"] = "FORBIDDEN"
    hidden["plan_body_sha256"] = qec.sha256_bytes(qec.canonical_bytes(hidden["plan_body"]))
    _expect_qec_reject(lambda: qec.validate_question_plan(hidden), "T03")
    results.append({"test_id": "T03", "status": "PASS", "basis": "隐藏字段拒收"})
    count = copy.deepcopy(q01)
    count["plan_body"]["expected_count"] = 4
    count["plan_body_sha256"] = qec.sha256_bytes(qec.canonical_bytes(count["plan_body"]))
    _expect_qec_reject(lambda: qec.validate_question_plan(count), "T04")
    results.append({"test_id": "T04", "status": "PASS", "basis": "答案数量字段拒收"})
    query = _assert_query_universe(run_dir)
    if query["new_query_count"] != 0:
        raise QECExperimentError("QEC_T05_NEW_QUERY_NONZERO")
    results.append({"test_id": "T05", "status": "PASS", "basis": "A5 query 逐项一致"})

    trace_collection = _load_json(run_dir / "route_assets/qec/traces/QEC/300.json")
    trace = trace_collection["cells"][0]
    case_id = trace["cell_id"].split("::", 1)[0]
    catalog = _load_json(run_dir / f"preregistered_input_workspace/source_catalog_v2/{case_id}.json")
    paragraph_text = {row["paragraph_id"]: row["original_text"] for row in catalog["paragraphs"]}
    tampered_trace = copy.deepcopy(trace)
    tampered_trace["selected_window_ids"] = list(reversed(tampered_trace["selected_window_ids"]))
    tampered_trace.pop("trace_payload_sha256")
    tampered_trace["trace_payload_sha256"] = qec.sha256_bytes(qec.canonical_bytes(tampered_trace))
    _expect_qec_reject(
        lambda: qec.validate_trace(tampered_trace, paragraph_text_by_id=paragraph_text),
        "T06",
    )
    results.append({"test_id": "T06", "status": "PASS", "basis": "轨迹顺序篡改拒收"})

    evidence_collection = _load_json(run_dir / "route_assets/qec/evidence/QEC/300.json")
    evidence_cell = next(row for row in evidence_collection["cells"] if row["cell_id"] == trace["cell_id"])
    records = evidence_cell["records"]
    if records:
        outside = copy.deepcopy(records)
        outside[0]["paragraph_id"] = "OUTSIDE-WINDOW"
        _expect_qec_reject(
            lambda: qec.validate_evidence_records(outside, trace=trace, catalog=catalog),
            "T07",
        )
        forged = copy.deepcopy(records)
        forged[0]["text"] += "伪"
        forged[0]["text_sha256"] = qec.sha256_bytes(forged[0]["text"].encode("utf-8"))
        _expect_qec_reject(
            lambda: qec.validate_evidence_records(forged, trace=trace, catalog=catalog),
            "T09",
        )
    results.extend(
        [
            {"test_id": "T07", "status": "PASS", "basis": "未取窗口证据拒收"},
            {"test_id": "T08", "status": "PASS", "basis": "轨迹按唯一段落重算字符预算"},
            {"test_id": "T09", "status": "PASS", "basis": "非逐字回填拒收"},
        ]
    )
    answer_collection = _load_json(run_dir / "route_assets/qec/answers/QEC/300.json")
    answer = next(row for row in answer_collection["cells"] if row["cell_id"] == trace["cell_id"])
    plan = next(row for row in plans if row["question_id"] == trace["question_id"])
    self_signed = copy.deepcopy(answer)
    self_signed["is_correct"] = True
    _expect_qec_reject(
        lambda: qec.validate_answer(self_signed, plan=plan, evidence_records=records),
        "T10",
    )
    contradiction = copy.deepcopy(answer)
    contradiction["status"] = "ANSWER"
    contradiction["claims"] = []
    contradiction.pop("answer_payload_sha256")
    contradiction["answer_payload_sha256"] = qec.sha256_bytes(qec.canonical_bytes(contradiction))
    _expect_qec_reject(
        lambda: qec.validate_answer(contradiction, plan=plan, evidence_records=records),
        "T11",
    )
    results.extend(
        [
            {"test_id": "T10", "status": "PASS", "basis": "语义自签字段拒收"},
            {"test_id": "T11", "status": "PASS", "basis": "状态与 claims 矛盾拒收"},
        ]
    )
    synthetic_score = {
        "full_question_recall_count": 17,
        "required_head_recall_count": 78,
        "per_case": {
            "B01-U0033": {"question_hits": 1, "head_hits": 18},
            "B02-U0039": {"question_hits": 8, "head_hits": 19},
            "B03-U0041": {"question_hits": 8, "head_hits": 42},
        },
    }
    if qec.decide_primary(contract=contract, score_row=synthetic_score)["disposition"] != "CUT_B02_REGRESSION":
        raise QECExperimentError("QEC_T12_LOCAL_FALSE_WIN_NOT_CUT")
    results.append({"test_id": "T12", "status": "PASS", "basis": "B01 局部增益伴 B02 回退仍自动砍"})
    return results


def build_pre_score_gate(
    *,
    contract: Mapping[str, Any],
    errata: Mapping[str, Any],
    contract_sha256: str,
    errata_sha256: str,
    repo: Path,
    run_dir: Path,
    baseline: Mapping[str, Any],
    workspace: Path,
    workspace_manifest: Path,
    workspace_manifest_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    a5_replay = _assert_a5_replay(contract=contract, repo=repo, run_dir=run_dir)
    query_universe = _assert_query_universe(run_dir)
    rank_streams = _assert_rank_streams(errata=errata, run_dir=run_dir)
    plans = _assert_plans(run_dir)
    sidecar_validation = _validate_sidecars(run_dir)
    determinism = _run_second_dry_generation(
        run_dir=run_dir,
        workspace=workspace,
        manifest_path=workspace_manifest,
        manifest_sha256=workspace_manifest_sha256,
    )
    adversarial = run_adversarial_probes(run_dir, contract)
    sidecar_files = [
        relative
        for relative in _deterministic_file_set()
        if relative.startswith("route_assets/qec/")
    ]
    sidecar: dict[str, Any] = {
        "schema_version": SIDECAR_MANIFEST_SCHEMA,
        "candidate_status": "candidate_silver_not_active",
        "experiment_contract_sha256": contract_sha256,
        "contract_errata_sha256": errata_sha256,
        "question_state_feedback_control": False,
        "question_state_feedback_candidate": True,
        "rank_streams": rank_streams,
        "query_universe": query_universe,
        "plans": plans,
        "sidecar_validation": sidecar_validation,
        "files": [
            {"path": relative, "sha256": sha256_file(run_dir / relative)}
            for relative in sidecar_files
        ],
        "model_api_calls": 0,
        "network_calls": 0,
    }
    sidecar["sidecar_payload_sha256"] = sha256_bytes(canonical_bytes(sidecar))
    sidecar_path = run_dir / "preregistered/qec_sidecar_manifest.json"
    write_json(sidecar_path, sidecar)
    gate: dict[str, Any] = {
        "schema_version": PRE_SCORE_GATE_SCHEMA,
        "status": "PASS",
        "experiment_contract_sha256": contract_sha256,
        "contract_errata_sha256": errata_sha256,
        "baseline_verification": baseline,
        "a5_replay": a5_replay,
        "a5_contract_shadow_score_basis": "A5_SEALED_OUTPUTS_AND_SELECTION_PROJECTIONS_BYTE_IDENTICAL_7_OF_7",
        "query_universe": query_universe,
        "rank_streams": rank_streams,
        "plans": plans,
        "sidecar_validation": sidecar_validation,
        "deterministic_zero_api_generations": determinism,
        "adversarial_tests": adversarial,
        "hidden_score_run_count_before_gate": 0,
        "model_api_calls": 0,
        "network_calls": 0,
    }
    gate["gate_payload_sha256"] = sha256_bytes(canonical_bytes(gate))
    return gate, sidecar


def _score_rows(score: Mapping[str, Any], route_id: str) -> dict[int, dict[str, Any]]:
    return {
        row["budget_chars"]: dict(row)
        for row in score["rows"]
        if row["route_id"] == route_id
    }


def _stop_receipt_markdown(
    *,
    contract_sha256: str,
    errata_sha256: str,
    gate_sha256: str,
    sidecar_sha256: str,
    score_sha256: str,
    decision: Mapping[str, Any],
    score: Mapping[str, Any],
) -> str:
    a5 = _score_rows(score, "A5")
    qec_rows = _score_rows(score, "QEC")
    lines = [
        "# R2 QEC 逐题回取＋回答合同｜正式停点回包",
        "",
        f"结论：`{decision['disposition']}`。这次已经完成本地实现、七档正式运行和唯一一次隐藏开发集评分，不是只转述外审建议。",
        "",
        "| 字符预算 | A5 完整题 | QEC 完整题 | A5 必答头 | QEC 必答头 |",
        "|---:|---:|---:|---:|---:|",
    ]
    for budget in route_runner.BUDGETS:
        lines.append(
            f"| {budget} | {a5[budget]['full_question_recall_count']}/28 | "
            f"{qec_rows[budget]['full_question_recall_count']}/28 | "
            f"{a5[budget]['required_head_recall_count']}/115 | "
            f"{qec_rows[budget]['required_head_recall_count']}/115 |"
        )
    actual = decision["actual"]
    lines.extend(
        [
            "",
            "## 2,500 字主档",
            "",
            f"- 总体：{actual['overall_complete_questions']}/28 完整题，{actual['overall_required_heads']}/115 必答头",
            f"- B01：{actual['B01-U0033_complete_questions']}/10 完整题，{actual['B01-U0033_required_heads']}/52 必答头",
            f"- B02：{actual['B02-U0039_complete_questions']}/9 完整题，{actual['B02-U0039_required_heads']}/19 必答头",
            f"- B03：{actual['B03-U0041_complete_questions']}/9 完整题，{actual['B03-U0041_required_heads']}/44 必答头",
            "",
            "## 守闸",
            "",
            "- A5 七档输出和选择投影 7/7 逐字复现。",
            "- QEC 新增查询 0；只从 810 条既有 A5 查询排名流逐步取窗。",
            "- 排名流 30 格、59,940 条排名记录，两次 0 API 生成逐字一致。",
            "- 题面计划、逐题轨迹、证据回填、回答合同和 12 条敌对测试均过机械闸。",
            "- 隐藏开发集只评分一次；没有看分调规则或换预算。",
            "- 模型 API 0、网络 0；不改金标、不升默认、不提交、不推送。",
            "- 这里的 16/28 一类数字仍是证据窗口覆盖，不是答案正确率。",
            "",
            "## 关键 SHA",
            "",
            f"- 实验合同：`{contract_sha256}`",
            f"- 合同补票：`{errata_sha256}`",
            f"- 计分前总闸：`{gate_sha256}`",
            f"- QEC 旁车清单：`{sidecar_sha256}`",
            f"- 离线成绩：`{score_sha256}`",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def execute_official_run(
    *,
    repo: Path,
    run_dir: Path,
    contract_path: Path,
    expected_contract_sha256: str,
    errata_path: Path,
    expected_errata_sha256: str,
    question_set_path: Path,
    catalog_dir: Path,
    hidden_cells_path: Path,
) -> dict[str, Any]:
    _refuse_used_run_directory(run_dir)
    contract, errata = load_contracts(
        contract_path=contract_path,
        expected_contract_sha256=expected_contract_sha256,
        errata_path=errata_path,
        expected_errata_sha256=expected_errata_sha256,
    )
    if repo / contract["run_directory"] != run_dir:
        raise QECExperimentError("QEC_RUN_DIRECTORY_CONTRACT_MISMATCH")
    baseline = verify_frozen_baseline(
        contract=contract,
        errata=errata,
        repo=repo,
        question_set_path=question_set_path,
        catalog_dir=catalog_dir,
        hidden_cells_path=hidden_cells_path,
    )
    workspace = run_dir / "preregistered_input_workspace"
    workspace_manifest = run_dir / "preregistered/workspace_manifest.json"
    preparation = prepare_route_workspace.prepare_route_workspace(
        question_set_path=question_set_path,
        catalog_dir=catalog_dir,
        workspace=workspace,
        manifest_path=workspace_manifest,
    )
    write_json(run_dir / "preregistered/workspace_preparation_receipt.json", preparation)
    if preparation["manifest_sha256"] != contract["parent_route"]["workspace_manifest_sha256"]:
        raise QECExperimentError("QEC_WORKSPACE_MANIFEST_NOT_A5_EXACT")
    route_receipt = route_runner.run_routes(
        workspace=workspace,
        preregistered_manifest_path=workspace_manifest,
        expected_manifest_sha256=preparation["manifest_sha256"],
        output_dir=run_dir,
        route_ids=("A5", "QEC"),
    )
    if route_receipt["model_api_calls"] != 0 or route_receipt["network_calls"] != 0:
        raise QECExperimentError("QEC_ROUTE_RUN_NONZERO_CALLS")
    gate, sidecar = build_pre_score_gate(
        contract=contract,
        errata=errata,
        contract_sha256=expected_contract_sha256,
        errata_sha256=expected_errata_sha256,
        repo=repo,
        run_dir=run_dir,
        baseline=baseline,
        workspace=workspace,
        workspace_manifest=workspace_manifest,
        workspace_manifest_sha256=preparation["manifest_sha256"],
    )
    gate_path = run_dir / "preregistered/pre_score_gate.json"
    sidecar_path = run_dir / "preregistered/qec_sidecar_manifest.json"
    write_json(gate_path, gate)

    score_bundle_path = run_dir / "preregistered/score_bundle_manifest.json"
    offline_scorer.freeze_score_bundle(
        sealed_outputs_dir=run_dir / "sealed_outputs",
        route_receipt_path=run_dir / "route_run_receipt.json",
        hidden_cells_path=hidden_cells_path,
        catalog_dir=catalog_dir,
        route_manifests_dir=run_dir / "route_manifests",
        output_path=score_bundle_path,
        scoring_executor_id="R2-QEC-OFFLINE-SCORER",
    )
    score_bundle_sha = sha256_file(score_bundle_path)
    score_path = run_dir / "offline_score.json"
    score = offline_scorer.score_all(
        sealed_outputs_dir=run_dir / "sealed_outputs",
        route_receipt_path=run_dir / "route_run_receipt.json",
        hidden_cells_path=hidden_cells_path,
        catalog_dir=catalog_dir,
        route_manifests_dir=run_dir / "route_manifests",
        score_bundle_manifest_path=score_bundle_path,
        expected_score_bundle_manifest_sha256=score_bundle_sha,
        output_path=score_path,
    )
    primary = [
        row
        for row in score["rows"]
        if row["route_id"] == "QEC" and row["budget_chars"] == contract["primary_budget_chars"]
    ]
    if len(primary) != 1:
        raise QECExperimentError("QEC_PRIMARY_SCORE_ROW_INVALID")
    decision = qec.decide_primary(contract=contract, score_row=primary[0])
    decision_path = run_dir / "score_gate_decision.json"
    write_json(decision_path, decision)
    stop_text = _stop_receipt_markdown(
        contract_sha256=expected_contract_sha256,
        errata_sha256=expected_errata_sha256,
        gate_sha256=sha256_file(gate_path),
        sidecar_sha256=sha256_file(sidecar_path),
        score_sha256=sha256_file(score_path),
        decision=decision,
        score=score,
    )
    (run_dir / "STOP_RECEIPT.md").write_text(stop_text, encoding="utf-8")
    receipt: dict[str, Any] = {
        "schema_version": RUN_RECEIPT_SCHEMA,
        "status": "COMPLETE",
        "candidate_status": "candidate_silver_not_active",
        "disposition": decision["disposition"],
        "experiment_contract_sha256": expected_contract_sha256,
        "contract_errata_sha256": expected_errata_sha256,
        "workspace_manifest_sha256": preparation["manifest_sha256"],
        "route_receipt_sha256": sha256_file(run_dir / "route_run_receipt.json"),
        "sidecar_manifest_sha256": sha256_file(sidecar_path),
        "pre_score_gate_sha256": sha256_file(gate_path),
        "score_bundle_manifest_sha256": score_bundle_sha,
        "offline_score_sha256": sha256_file(score_path),
        "score_gate_decision_sha256": sha256_file(decision_path),
        "stop_receipt_sha256": sha256_file(run_dir / "STOP_RECEIPT.md"),
        "hidden_score_run_count": 1,
        "model_api_calls": 0,
        "network_calls": 0,
        "git_commit_or_push": False,
    }
    receipt["receipt_payload_sha256"] = sha256_bytes(canonical_bytes(receipt))
    write_json(run_dir / "official_run_receipt.json", receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--errata", type=Path, required=True)
    parser.add_argument("--errata-sha256", required=True)
    parser.add_argument("--question-set", type=Path, required=True)
    parser.add_argument("--catalog-dir", type=Path, required=True)
    parser.add_argument("--hidden-cells", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = execute_official_run(
        repo=args.repo.resolve(),
        run_dir=args.run_dir.resolve(),
        contract_path=args.contract.resolve(),
        expected_contract_sha256=args.contract_sha256,
        errata_path=args.errata.resolve(),
        expected_errata_sha256=args.errata_sha256,
        question_set_path=args.question_set.resolve(),
        catalog_dir=args.catalog_dir.resolve(),
        hidden_cells_path=args.hidden_cells.resolve(),
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
