from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Mapping

from . import event_graph_planner
from . import offline_scorer
from . import prepare_route_workspace
from . import route_runner


RUN_RECEIPT_SCHEMA = "v02-r2-a8-official-run-receipt.v1"
SIDE_CAR_SCHEMA = "v02-r2-a8-sidecar-manifest.v1"
PRE_SCORE_GATE_SCHEMA = "v02-r2-a8-pre-score-gate.v1"
DECISION_SCHEMA = "v02-r2-a8-score-gate-decision.v1"


class A8ExperimentError(ValueError):
    """A8 正式实验总控拒收错误。"""


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
        raise A8ExperimentError(f"A8_REQUIRED_FILE_MISSING:{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise A8ExperimentError(f"A8_REQUIRED_JSON_INVALID:{path}") from exc


def _require_sha(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise A8ExperimentError(f"A8_HASH_INVALID:{field}")
    return value


def load_experiment_contract(
    path: Path, *, expected_sha256: str
) -> dict[str, Any]:
    _require_sha(expected_sha256, field="experiment_contract_sha256")
    if sha256_file(path) != expected_sha256:
        raise A8ExperimentError("A8_EXPERIMENT_CONTRACT_SHA_MISMATCH")
    value = _load_json(path)
    if not isinstance(value, dict):
        raise A8ExperimentError("A8_EXPERIMENT_CONTRACT_NOT_OBJECT")
    if value.get("schema_version") != "v02-r2-a8-experiment-contract.v1":
        raise A8ExperimentError("A8_EXPERIMENT_CONTRACT_SCHEMA_INVALID")
    if value.get("contract_status") != "FROZEN_BEFORE_IMPLEMENTATION":
        raise A8ExperimentError("A8_EXPERIMENT_CONTRACT_NOT_FROZEN")
    if value.get("model_api_calls_allowed") != 0:
        raise A8ExperimentError("A8_EXPERIMENT_MODEL_API_NOT_ZERO")
    if value.get("network_calls_allowed") != 0:
        raise A8ExperimentError("A8_EXPERIMENT_NETWORK_NOT_ZERO")
    if value.get("scoring_policy", {}).get("hidden_score_run_count") != 1:
        raise A8ExperimentError("A8_HIDDEN_SCORE_COUNT_NOT_ONE")
    return value


def _refuse_used_run_directory(run_dir: Path) -> None:
    forbidden = (
        "route_run_receipt.json",
        "offline_score.json",
        "score_gate_decision.json",
        "preregistered/pre_score_gate.json",
        "preregistered/score_bundle_manifest.json",
        "route_manifests",
        "sealed_outputs",
    )
    hits = [relative for relative in forbidden if (run_dir / relative).exists()]
    if hits:
        raise A8ExperimentError(f"A8_RUN_DIRECTORY_ALREADY_USED:{hits}")


def _function_sha(function: Any) -> str:
    return sha256_bytes(inspect.getsource(function).encode("utf-8"))


def verify_frozen_baseline(
    *, contract: Mapping[str, Any], repo: Path
) -> dict[str, Any]:
    parent = repo / contract["parent_route"]["run_directory"]
    if not parent.is_dir() or parent.is_symlink():
        raise A8ExperimentError("A8_PARENT_RUN_MISSING")

    exact_files = {
        "workspace_manifest_sha256": parent / "preregistered/workspace_manifest.json",
        "question_projection_sha256": parent / "frozen/question_projection.json",
        "source_bindings_sha256": parent / "frozen/source_bindings.json",
        "query_map_sha256": parent / "route_assets/query_maps/A5.json",
        "obligation_plan_sha256": parent / "route_assets/obligation_plans/A5.json",
    }
    file_checks: list[dict[str, Any]] = []
    for field, path in exact_files.items():
        expected = _require_sha(
            contract["parent_route"][field], field=f"parent_route.{field}"
        )
        actual = sha256_file(path)
        if actual != expected:
            raise A8ExperimentError(f"A8_PARENT_BASELINE_SHA_DRIFT:{field}")
        file_checks.append(
            {
                "field": field,
                "path": path.relative_to(repo).as_posix(),
                "sha256": actual,
            }
        )

    parent_manifest = _load_json(parent / "route_manifests/A5.json")
    if (
        parent_manifest.get("planner_visible_source_sha256")
        != contract["parent_route"]["planner_visible_source_sha256"]
    ):
        raise A8ExperimentError("A8_PARENT_PLANNER_VISIBLE_SOURCE_DRIFT")
    sparse_index = _load_json(parent / "route_assets/sparse_index.json")
    if (
        sparse_index.get("index_payload_sha256")
        != contract["parent_route"]["index_payload_sha256"]
    ):
        raise A8ExperimentError("A8_PARENT_INDEX_PAYLOAD_DRIFT")

    budget_checks: list[dict[str, Any]] = []
    for budget in route_runner.BUDGETS:
        key = str(budget)
        output_path = parent / f"sealed_outputs/A5/{budget}.json"
        projection_path = (
            parent / f"route_assets/selection_projections/A5/{budget}.json"
        )
        output_sha = sha256_file(output_path)
        projection_sha = sha256_file(projection_path)
        if output_sha != contract["a5_sealed_output_sha256_by_budget"][key]:
            raise A8ExperimentError(f"A8_PARENT_OUTPUT_DRIFT:{budget}")
        if (
            projection_sha
            != contract["a5_selection_projection_sha256_by_budget"][key]
        ):
            raise A8ExperimentError(f"A8_PARENT_SELECTION_DRIFT:{budget}")
        budget_checks.append(
            {
                "budget_chars": budget,
                "output_sha256": output_sha,
                "selection_projection_sha256": projection_sha,
            }
        )

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
            raise A8ExperimentError(f"A8_FROZEN_FUNCTION_DRIFT:{name}")
        function_checks[name] = actual
    scorer_sha = sha256_file(Path(offline_scorer.__file__))
    if scorer_sha != contract["frozen_function_sha256"]["offline_scorer_file"]:
        raise A8ExperimentError("A8_OFFLINE_SCORER_FILE_DRIFT")
    function_checks["offline_scorer_file"] = scorer_sha

    environment_checks: dict[str, str] = {}
    for relative, expected in contract["environment_sha256"].items():
        actual = sha256_file(repo / relative)
        if actual != expected:
            raise A8ExperimentError(f"A8_ENVIRONMENT_DRIFT:{relative}")
        environment_checks[relative] = actual

    return {
        "parent_run": parent.relative_to(repo).as_posix(),
        "file_checks": file_checks,
        "budget_checks": budget_checks,
        "function_checks": function_checks,
        "environment_checks": environment_checks,
        "status": "PASS",
    }


def _rows_by_cell(collection: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in collection["cells"]:
        cell_id = f"{row['case_id']}::{row['question_id']}"
        if cell_id in rows:
            raise A8ExperimentError(f"A8_QUERY_CELL_DUPLICATED:{cell_id}")
        rows[cell_id] = dict(row)
    return rows


def _output_cells(path: Path) -> dict[str, dict[str, Any]]:
    value = _load_json(path)
    return {row["cell_id"]: row for row in value["cells"]}


def build_pre_score_gate(
    *,
    contract: Mapping[str, Any],
    contract_sha256: str,
    repo: Path,
    run_dir: Path,
    baseline_verification: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    parent = repo / contract["parent_route"]["run_directory"]
    output_replay: list[dict[str, Any]] = []
    selection_replay: list[dict[str, Any]] = []
    for budget in route_runner.BUDGETS:
        current_output = run_dir / f"sealed_outputs/A5/{budget}.json"
        parent_output = parent / f"sealed_outputs/A5/{budget}.json"
        current_projection = (
            run_dir / f"route_assets/selection_projections/A5/{budget}.json"
        )
        parent_projection = (
            parent / f"route_assets/selection_projections/A5/{budget}.json"
        )
        if current_output.read_bytes() != parent_output.read_bytes():
            raise A8ExperimentError(f"A8_A5_OUTPUT_REPLAY_DRIFT:{budget}")
        if current_projection.read_bytes() != parent_projection.read_bytes():
            raise A8ExperimentError(f"A8_A5_SELECTION_REPLAY_DRIFT:{budget}")
        output_replay.append(
            {
                "budget_chars": budget,
                "byte_identical": True,
                "sha256": sha256_file(current_output),
            }
        )
        selection_replay.append(
            {
                "budget_chars": budget,
                "byte_identical": True,
                "sha256": sha256_file(current_projection),
            }
        )

    direct_replay = (
        (run_dir / "frozen/question_projection.json", parent / "frozen/question_projection.json"),
        (run_dir / "frozen/source_bindings.json", parent / "frozen/source_bindings.json"),
        (run_dir / "route_assets/query_maps/A5.json", parent / "route_assets/query_maps/A5.json"),
        (
            run_dir / "route_assets/obligation_plans/A5.json",
            parent / "route_assets/obligation_plans/A5.json",
        ),
    )
    for current, old in direct_replay:
        if current.read_bytes() != old.read_bytes():
            raise A8ExperimentError(f"A8_A5_DIRECT_REPLAY_DRIFT:{current.name}")

    event_contract_path = repo / contract["event_graph_contract"]["path"]
    event_contract = event_graph_planner.load_contract(
        event_contract_path,
        expected_sha256=contract["event_graph_contract"]["sha256"],
    )
    graph_records: list[dict[str, Any]] = []
    for case_id in route_runner.CASE_IDS:
        source_path = run_dir / f"frozen/planner_visible_source_v1/{case_id}.json"
        graph_path = run_dir / f"route_assets/event_graphs/A8/{case_id}.json"
        source = _load_json(source_path)
        current = _load_json(graph_path)
        rebuilt_first = event_graph_planner.build_event_graph(source, event_contract)
        rebuilt_second = event_graph_planner.build_event_graph(source, event_contract)
        if canonical_bytes(rebuilt_first) != canonical_bytes(rebuilt_second):
            raise A8ExperimentError(f"A8_GRAPH_NONDETERMINISTIC:{case_id}")
        if canonical_bytes(current) != canonical_bytes(rebuilt_first):
            raise A8ExperimentError(f"A8_GRAPH_REBUILD_MISMATCH:{case_id}")
        event_graph_planner.validate_event_graph(
            current,
            planner_source=source,
            contract=event_contract,
        )
        graph_records.append(
            {
                "case_id": case_id,
                "path": graph_path.relative_to(run_dir).as_posix(),
                "sha256": sha256_file(graph_path),
                "node_count": len(current["nodes"]),
                "edge_count": len(current["edges"]),
            }
        )

    a5_query_collection = _load_json(run_dir / "route_assets/query_maps/A5.json")
    a8_query_collection = _load_json(run_dir / "route_assets/query_maps/A8.json")
    a5_queries = _rows_by_cell(a5_query_collection)
    a8_queries = _rows_by_cell(a8_query_collection)
    if set(a5_queries) != set(a8_queries):
        raise A8ExperimentError("A8_QUERY_CELL_SET_MISMATCH")
    prefix_checks: list[dict[str, Any]] = []
    zero_trigger_cells: list[str] = []
    event_query_total = 0
    for cell_id in sorted(a5_queries):
        parent_texts = [row["query_text"] for row in a5_queries[cell_id]["queries"]]
        candidate = a8_queries[cell_id]
        prefix_count = candidate["a5_prefix_count"]
        candidate_texts = [row["query_text"] for row in candidate["queries"]]
        if prefix_count != len(parent_texts):
            raise A8ExperimentError(f"A8_PREFIX_COUNT_DRIFT:{cell_id}")
        if candidate_texts[:prefix_count] != parent_texts:
            raise A8ExperimentError(f"A8_PREFIX_TEXT_DRIFT:{cell_id}")
        if candidate["event_query_count"] == 0:
            if candidate_texts != parent_texts:
                raise A8ExperimentError(f"A8_ZERO_TRIGGER_QUERY_DRIFT:{cell_id}")
            zero_trigger_cells.append(cell_id)
        event_query_total += candidate["event_query_count"]
        prefix_checks.append(
            {
                "cell_id": cell_id,
                "a5_prefix_count": prefix_count,
                "event_query_count": candidate["event_query_count"],
                "status": "PASS",
            }
        )

    zero_fallback_checks: list[dict[str, Any]] = []
    for budget in route_runner.BUDGETS:
        a5_cells = _output_cells(run_dir / f"sealed_outputs/A5/{budget}.json")
        a8_cells = _output_cells(run_dir / f"sealed_outputs/A8/{budget}.json")
        for cell_id in zero_trigger_cells:
            if canonical_bytes(a5_cells[cell_id]) != canonical_bytes(a8_cells[cell_id]):
                raise A8ExperimentError(
                    f"A8_ZERO_TRIGGER_OUTPUT_NOT_A5:{budget}:{cell_id}"
                )
        zero_fallback_checks.append(
            {
                "budget_chars": budget,
                "zero_trigger_cell_count": len(zero_trigger_cells),
                "byte_identical": True,
            }
        )

    trigger_path = run_dir / "route_assets/event_triggers/A8.json"
    trigger_collection = _load_json(trigger_path)
    if len(trigger_collection["cells"]) != len(a8_queries):
        raise A8ExperimentError("A8_TRIGGER_CELL_COUNT_MISMATCH")

    sidecar: dict[str, Any] = {
        "schema_version": SIDE_CAR_SCHEMA,
        "candidate_status": "candidate_silver_not_active",
        "experiment_contract_sha256": contract_sha256,
        "event_graph_contract_sha256": contract["event_graph_contract"]["sha256"],
        "event_graph_records": graph_records,
        "event_graph_collection": {
            "path": "route_assets/event_graphs/A8_collection.json",
            "sha256": sha256_file(
                run_dir / "route_assets/event_graphs/A8_collection.json"
            ),
        },
        "event_trigger_collection": {
            "path": trigger_path.relative_to(run_dir).as_posix(),
            "sha256": sha256_file(trigger_path),
            "cell_count": len(trigger_collection["cells"]),
        },
        "a8_query_map": {
            "path": "route_assets/query_maps/A8.json",
            "sha256": sha256_file(run_dir / "route_assets/query_maps/A8.json"),
            "cell_count": len(a8_queries),
            "event_query_total": event_query_total,
            "zero_trigger_cell_count": len(zero_trigger_cells),
        },
        "prefix_checks": prefix_checks,
        "zero_trigger_fallback_checks": zero_fallback_checks,
        "runner_sha256": sha256_file(Path(__file__)),
        "model_api_calls": 0,
        "network_calls": 0,
    }
    sidecar["sidecar_payload_sha256"] = sha256_bytes(canonical_bytes(sidecar))
    sidecar_path = run_dir / "preregistered/a8_sidecar_manifest.json"
    write_json(sidecar_path, sidecar)

    gate: dict[str, Any] = {
        "schema_version": PRE_SCORE_GATE_SCHEMA,
        "status": "PASS",
        "experiment_contract_sha256": contract_sha256,
        "baseline_verification": baseline_verification,
        "a5_output_replay": output_replay,
        "a5_selection_projection_replay": selection_replay,
        "a5_direct_replay_count": len(direct_replay),
        "event_graph_deterministic_count": len(graph_records),
        "query_prefix_pass_count": len(prefix_checks),
        "zero_trigger_cell_count": len(zero_trigger_cells),
        "sidecar_manifest_sha256": sha256_file(sidecar_path),
        "hidden_score_run_count_before_gate": 0,
        "model_api_calls": 0,
        "network_calls": 0,
    }
    gate["gate_payload_sha256"] = sha256_bytes(canonical_bytes(gate))
    return gate, sidecar


def evaluate_primary_decision(
    *, contract: Mapping[str, Any], score: Mapping[str, Any]
) -> dict[str, Any]:
    primary_budget = contract["primary_budget_chars"]
    rows = [
        row
        for row in score["rows"]
        if row["route_id"] == "A8" and row["budget_chars"] == primary_budget
    ]
    if len(rows) != 1:
        raise A8ExperimentError("A8_PRIMARY_SCORE_ROW_INVALID")
    row = rows[0]
    actual = {
        "overall_complete_questions": row["full_question_recall_count"],
        "overall_required_heads": row["required_head_recall_count"],
        "B01-U0033_complete_questions": row["per_case"]["B01-U0033"][
            "question_hits"
        ],
        "B01-U0033_required_heads": row["per_case"]["B01-U0033"]["head_hits"],
        "B02-U0039_complete_questions": row["per_case"]["B02-U0039"][
            "question_hits"
        ],
        "B02-U0039_required_heads": row["per_case"]["B02-U0039"]["head_hits"],
        "B03-U0041_complete_questions": row["per_case"]["B03-U0041"][
            "question_hits"
        ],
        "B03-U0041_required_heads": row["per_case"]["B03-U0041"]["head_hits"],
    }
    hard_cut_map = {
        "overall_complete_questions_min": "overall_complete_questions",
        "overall_required_heads_min": "overall_required_heads",
        "B01-U0033_required_heads_min": "B01-U0033_required_heads",
        "B02-U0039_complete_questions_min": "B02-U0039_complete_questions",
        "B02-U0039_required_heads_min": "B02-U0039_required_heads",
        "B03-U0041_complete_questions_min": "B03-U0041_complete_questions",
        "B03-U0041_required_heads_min": "B03-U0041_required_heads",
    }
    hard_cut_checks = {
        field: actual[metric] >= minimum
        for field, minimum in contract["primary_score_hard_cut_at_2500"].items()
        for metric in [hard_cut_map[field]]
    }
    hard_cut_pass = all(hard_cut_checks.values())
    a10_eligible = (
        hard_cut_pass
        and actual["B01-U0033_complete_questions"]
        >= contract["a10_eligible_only_if"]["B01-U0033_complete_questions_min"]
    )
    candidate_map = {
        "overall_complete_questions_min": "overall_complete_questions",
        "overall_required_heads_min": "overall_required_heads",
        "B01-U0033_complete_questions_min": "B01-U0033_complete_questions",
        "B01-U0033_required_heads_min": "B01-U0033_required_heads",
        "B02-U0039_complete_questions_min": "B02-U0039_complete_questions",
        "B02-U0039_required_heads_min": "B02-U0039_required_heads",
        "B03-U0041_complete_questions_min": "B03-U0041_complete_questions",
        "B03-U0041_required_heads_min": "B03-U0041_required_heads",
    }
    candidate_checks = {
        field: actual[metric] >= minimum
        for field, minimum in contract["register_candidate_only_if"].items()
        for metric in [candidate_map[field]]
    }
    register_candidate = all(candidate_checks.values())
    if not hard_cut_pass:
        disposition = "CUT_PRIMARY_REGRESSION"
    elif not a10_eligible:
        disposition = "CUT_NO_B01_COMPLETE_QUESTION_GAIN"
    elif register_candidate:
        disposition = "CANDIDATE_SILVER_A10_ELIGIBLE"
    else:
        disposition = "A10_ELIGIBLE_NOT_REGISTERED_CANDIDATE"
    decision: dict[str, Any] = {
        "schema_version": DECISION_SCHEMA,
        "candidate_status": "candidate_silver_not_active",
        "primary_budget_chars": primary_budget,
        "actual": actual,
        "hard_cut_checks": hard_cut_checks,
        "hard_cut_pass": hard_cut_pass,
        "a10_eligible": a10_eligible,
        "candidate_checks": candidate_checks,
        "register_candidate": register_candidate,
        "disposition": disposition,
        "quality_boundary": (
            "只测开发集冻结窗口覆盖，不等于答案正确率或 R2 正式终验成绩。"
        ),
        "model_api_calls": 0,
        "network_calls": 0,
    }
    decision["decision_payload_sha256"] = sha256_bytes(
        canonical_bytes(decision)
    )
    return decision


def _score_rows_by_budget(score: Mapping[str, Any], route_id: str) -> list[dict[str, Any]]:
    return sorted(
        [dict(row) for row in score["rows"] if row["route_id"] == route_id],
        key=lambda row: row["budget_chars"],
    )


def _stop_receipt_markdown(
    *,
    contract_sha256: str,
    sidecar_sha256: str,
    pre_score_gate_sha256: str,
    score_sha256: str,
    decision: Mapping[str, Any],
    score: Mapping[str, Any],
) -> str:
    a5_rows = {row["budget_chars"]: row for row in _score_rows_by_budget(score, "A5")}
    a8_rows = {row["budget_chars"]: row for row in _score_rows_by_budget(score, "A8")}
    lines = [
        "# R2 A8 事件图规划器｜正式停点回包",
        "",
        f"结论：`{decision['disposition']}`。本轮只登记开发集机械覆盖，不冒充答案正确率。",
        "",
        "## 七档同卷读数",
        "",
        "| 字符预算 | A5 完整题 | A8 完整题 | A5 必答头 | A8 必答头 |",
        "|---:|---:|---:|---:|---:|",
    ]
    for budget in route_runner.BUDGETS:
        lines.append(
            "| {budget} | {a5q}/28 | {a8q}/28 | {a5h}/115 | {a8h}/115 |".format(
                budget=budget,
                a5q=a5_rows[budget]["full_question_recall_count"],
                a8q=a8_rows[budget]["full_question_recall_count"],
                a5h=a5_rows[budget]["required_head_recall_count"],
                a8h=a8_rows[budget]["required_head_recall_count"],
            )
        )
    lines.extend(
        [
            "",
            "## 2,500 字主档",
            "",
            f"- 总体完整题：{decision['actual']['overall_complete_questions']}/28",
            f"- 总体必答头：{decision['actual']['overall_required_heads']}/115",
            f"- B01：{decision['actual']['B01-U0033_complete_questions']}/10 完整题，{decision['actual']['B01-U0033_required_heads']}/52 必答头",
            f"- B02：{decision['actual']['B02-U0039_complete_questions']}/9 完整题，{decision['actual']['B02-U0039_required_heads']}/19 必答头",
            f"- B03：{decision['actual']['B03-U0041_complete_questions']}/9 完整题，{decision['actual']['B03-U0041_required_heads']}/44 必答头",
            f"- A10 资格：{str(decision['a10_eligible']).lower()}",
            f"- 候选登记：{str(decision['register_candidate']).lower()}",
            "",
            "## 守闸与边界",
            "",
            "- A5 七档输出 7/7 与选择投影 7/7 逐字复现。",
            "- A8 只在 A5 查询列表末尾追加题目触发的原文关系查询。",
            "- 事件图逐来源只建一次，不读题目，不做实体合并、传递闭包或 A7 资产复用。",
            "- 隐藏评分只执行一次；没有按分数选预算、调规则或重跑。",
            "- 模型 API 0、网络 0；不改现役、不升默认、不推送。",
            "- 旧 17 项失败只保留“既有挂账、未独立证明时间归因”的保守口径。",
            "",
            "## 关键 SHA",
            "",
            f"- 实验合同：`{contract_sha256}`",
            f"- A8 旁车清单：`{sidecar_sha256}`",
            f"- 计分前总闸：`{pre_score_gate_sha256}`",
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
    experiment_contract_path: Path,
    expected_experiment_contract_sha256: str,
    question_set_path: Path,
    catalog_dir: Path,
    hidden_cells_path: Path,
) -> dict[str, Any]:
    _refuse_used_run_directory(run_dir)
    contract = load_experiment_contract(
        experiment_contract_path,
        expected_sha256=expected_experiment_contract_sha256,
    )
    if repo / contract["run_directory"] != run_dir:
        raise A8ExperimentError("A8_RUN_DIRECTORY_CONTRACT_MISMATCH")
    baseline = verify_frozen_baseline(contract=contract, repo=repo)

    workspace = run_dir / "preregistered_input_workspace"
    workspace_manifest = run_dir / "preregistered/workspace_manifest.json"
    preparation_receipt = prepare_route_workspace.prepare_route_workspace(
        question_set_path=question_set_path,
        catalog_dir=catalog_dir,
        workspace=workspace,
        manifest_path=workspace_manifest,
    )
    write_json(
        run_dir / "preregistered/workspace_preparation_receipt.json",
        preparation_receipt,
    )
    if preparation_receipt["manifest_sha256"] != contract["parent_route"][
        "workspace_manifest_sha256"
    ]:
        raise A8ExperimentError("A8_WORKSPACE_MANIFEST_NOT_A5_EXACT")

    route_receipt = route_runner.run_routes(
        workspace=workspace,
        preregistered_manifest_path=workspace_manifest,
        expected_manifest_sha256=preparation_receipt["manifest_sha256"],
        output_dir=run_dir,
        route_ids=("A5", "A8"),
        a8_event_graph_contract_path=(
            repo / contract["event_graph_contract"]["path"]
        ),
        expected_a8_event_graph_contract_sha256=(
            contract["event_graph_contract"]["sha256"]
        ),
    )
    if route_receipt["model_api_calls"] != 0 or route_receipt["network_calls"] != 0:
        raise A8ExperimentError("A8_ROUTE_RUN_NONZERO_CALLS")

    gate, sidecar = build_pre_score_gate(
        contract=contract,
        contract_sha256=expected_experiment_contract_sha256,
        repo=repo,
        run_dir=run_dir,
        baseline_verification=baseline,
    )
    gate_path = run_dir / "preregistered/pre_score_gate.json"
    write_json(gate_path, gate)
    sidecar_path = run_dir / "preregistered/a8_sidecar_manifest.json"

    score_bundle_path = run_dir / "preregistered/score_bundle_manifest.json"
    offline_scorer.freeze_score_bundle(
        sealed_outputs_dir=run_dir / "sealed_outputs",
        route_receipt_path=run_dir / "route_run_receipt.json",
        hidden_cells_path=hidden_cells_path,
        catalog_dir=catalog_dir,
        route_manifests_dir=run_dir / "route_manifests",
        output_path=score_bundle_path,
        scoring_executor_id="R2-A8-OFFLINE-SCORER",
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
    decision = evaluate_primary_decision(contract=contract, score=score)
    decision_path = run_dir / "score_gate_decision.json"
    write_json(decision_path, decision)

    stop_text = _stop_receipt_markdown(
        contract_sha256=expected_experiment_contract_sha256,
        sidecar_sha256=sha256_file(sidecar_path),
        pre_score_gate_sha256=sha256_file(gate_path),
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
        "experiment_contract_sha256": expected_experiment_contract_sha256,
        "workspace_manifest_sha256": preparation_receipt["manifest_sha256"],
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
    parser.add_argument("--experiment-contract", type=Path, required=True)
    parser.add_argument("--experiment-contract-sha256", required=True)
    parser.add_argument("--question-set", type=Path, required=True)
    parser.add_argument("--catalog-dir", type=Path, required=True)
    parser.add_argument("--hidden-cells", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = execute_official_run(
        repo=args.repo.resolve(),
        run_dir=args.run_dir.resolve(),
        experiment_contract_path=args.experiment_contract.resolve(),
        expected_experiment_contract_sha256=args.experiment_contract_sha256,
        question_set_path=args.question_set.resolve(),
        catalog_dir=args.catalog_dir.resolve(),
        hidden_cells_path=args.hidden_cells.resolve(),
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
