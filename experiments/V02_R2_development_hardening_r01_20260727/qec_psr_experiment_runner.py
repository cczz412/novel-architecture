from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Mapping

from . import qec_activate as qec
from . import qec_psr_sidecar as psr
from . import route_runner


PRE_SCORE_GATE_SCHEMA = "v02-r2-qec-psr-pre-score-gate.v1"
ROUTE_MANIFEST_SCHEMA = "v02-r2-qec-psr-route-manifest.v1"
RUN_RECEIPT_SCHEMA = "v02-r2-qec-psr-route-run-receipt.v1"
SCORE_BUNDLE_SCHEMA = "v02-r2-qec-psr-score-bundle.v1"
SCORE_RECEIPT_SCHEMA = "v02-r2-qec-psr-offline-score.v1"
OFFICIAL_RECEIPT_SCHEMA = "v02-r2-qec-psr-official-run-receipt.v1"


class QECPSRExperimentError(ValueError):
    """QEC-PSR 最后语义臂总控拒收错误。"""


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


def load_json(path: Path) -> Any:
    if not path.is_file() or path.is_symlink():
        raise QECPSRExperimentError(f"QEC_PSR_REQUIRED_FILE_MISSING:{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QECPSRExperimentError(
            f"QEC_PSR_REQUIRED_JSON_INVALID:{path}"
        ) from exc


def _require_sha(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise QECPSRExperimentError(f"QEC_PSR_SHA_INVALID:{field}")
    return value


def _payload_sha(value: Mapping[str, Any], field: str) -> str:
    payload = dict(value)
    payload.pop(field, None)
    return sha256_bytes(canonical_bytes(payload))


def _verify_payload(value: Mapping[str, Any], *, field: str, label: str) -> None:
    actual = _require_sha(value.get(field), field=field)
    if _payload_sha(value, field) != actual:
        raise QECPSRExperimentError(f"QEC_PSR_{label}_PAYLOAD_SHA_MISMATCH")


def _function_sha(function: Any) -> str:
    return sha256_bytes(inspect.getsource(function).encode("utf-8"))


def load_contract(
    *, contract_path: Path, expected_contract_sha256: str
) -> dict[str, Any]:
    expected = _require_sha(
        expected_contract_sha256, field="expected_contract_sha256"
    )
    if sha256_file(contract_path) != expected:
        raise QECPSRExperimentError("QEC_PSR_EXPERIMENT_CONTRACT_SHA_MISMATCH")
    contract = load_json(contract_path)
    if (
        contract.get("schema_version")
        != "v02-r2-qec-psr-experiment-contract.v1"
    ):
        raise QECPSRExperimentError("QEC_PSR_EXPERIMENT_CONTRACT_SCHEMA_INVALID")
    if contract.get("contract_status") != "FROZEN_BEFORE_CANDIDATE_IMPLEMENTATION":
        raise QECPSRExperimentError("QEC_PSR_EXPERIMENT_CONTRACT_NOT_FROZEN")
    _verify_payload(
        contract, field="contract_payload_sha256", label="EXPERIMENT_CONTRACT"
    )
    if contract.get("model_api_calls_allowed") != 0:
        raise QECPSRExperimentError("QEC_PSR_MODEL_API_ALLOWANCE_NOT_ZERO")
    if contract.get("network_calls_allowed") != 0:
        raise QECPSRExperimentError("QEC_PSR_NETWORK_ALLOWANCE_NOT_ZERO")
    if contract.get("new_query_count") != 0:
        raise QECPSRExperimentError("QEC_PSR_NEW_QUERY_COUNT_NOT_ZERO")
    if contract["primary_score_decision_order"] != contract["scoring_policy"][
        "ordered_stop_rules"
    ]:
        raise QECPSRExperimentError("QEC_PSR_DECISION_RULE_COPY_DRIFT")
    return contract


def _verify_authority(
    *,
    contract: Mapping[str, Any],
    authorization_ticket_path: Path,
    truth_snapshot_path: Path,
) -> dict[str, Any]:
    ticket_sha = sha256_file(authorization_ticket_path)
    truth_sha = sha256_file(truth_snapshot_path)
    if ticket_sha != contract["authorization_ticket_sha256"]:
        raise QECPSRExperimentError("QEC_PSR_AUTHORIZATION_TICKET_SHA_DRIFT")
    if truth_sha != contract["authority_snapshot_sha256"]:
        raise QECPSRExperimentError("QEC_PSR_AUTHORITY_SNAPSHOT_SHA_DRIFT")
    ticket = load_json(authorization_ticket_path)
    if ticket.get("task_id") != contract["task_id"]:
        raise QECPSRExperimentError("QEC_PSR_AUTHORIZATION_TASK_MISMATCH")
    if ticket.get("run_id") != contract["run_id"]:
        raise QECPSRExperimentError("QEC_PSR_AUTHORIZATION_RUN_MISMATCH")
    if (
        "m1_02_final_semantic_single_variable"
        not in ticket.get("allowed_actions", [])
    ):
        raise QECPSRExperimentError("QEC_PSR_ACTION_NOT_AUTHORIZED")
    if ticket.get("authority_source_sha256") != truth_sha:
        raise QECPSRExperimentError("QEC_PSR_TICKET_TRUTH_BINDING_DRIFT")
    return {
        "status": "PASS",
        "authorization_ticket_sha256": ticket_sha,
        "authority_snapshot_sha256": truth_sha,
        "allowed_action": "m1_02_final_semantic_single_variable",
    }


def _public_paths(qec_run: Path) -> dict[str, Path]:
    return {
        "question_plans": qec_run / "route_assets/qec/question_plans.json",
        "query_bindings": qec_run / "route_assets/qec/query_bindings.json",
        "rank_streams": qec_run / "route_assets/qec/rank_streams.json",
        "qec_trace_2500": qec_run / "route_assets/qec/traces/QEC/2500.json",
        "qec_selection_projection_2500": (
            qec_run / "route_assets/selection_projections/QEC/2500.json"
        ),
        "qec_sealed_output_2500": qec_run / "sealed_outputs/QEC/2500.json",
    }


def verify_frozen_public_baseline(
    *, repo: Path, contract: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    qec_run = repo / contract["control_route"]["run_directory"]
    if not qec_run.is_dir() or qec_run.is_symlink():
        raise QECPSRExperimentError("QEC_PSR_CONTROL_RUN_MISSING")

    control = contract["control_route"]
    exact_paths = {
        "experiment_contract_sha256": (
            qec_run / "preregistered/qec_experiment_contract.json"
        ),
        "contract_errata_sha256": (
            qec_run / "preregistered/qec_contract_errata.json"
        ),
        "question_plans_sha256": (
            qec_run / "route_assets/qec/question_plans.json"
        ),
        "query_bindings_sha256": (
            qec_run / "route_assets/qec/query_bindings.json"
        ),
        "rank_streams_sha256": qec_run / "route_assets/qec/rank_streams.json",
        "trace_2500_sha256": (
            qec_run / "route_assets/qec/traces/QEC/2500.json"
        ),
        "selection_projection_2500_sha256": (
            qec_run / "route_assets/selection_projections/QEC/2500.json"
        ),
        "sealed_output_2500_sha256": qec_run / "sealed_outputs/QEC/2500.json",
        "sparse_index_file_sha256": qec_run / "route_assets/sparse_index.json",
        "route_manifest_sha256": qec_run / "route_manifests/QEC.json",
        "route_receipt_sha256": qec_run / "route_run_receipt.json",
        "offline_score_sha256": qec_run / "offline_score.json",
        "score_gate_decision_sha256": qec_run / "score_gate_decision.json",
    }
    file_checks: list[dict[str, str]] = []
    for field, path in exact_paths.items():
        actual = sha256_file(path)
        if actual != control[field]:
            raise QECPSRExperimentError(f"QEC_PSR_CONTROL_FILE_DRIFT:{field}")
        file_checks.append(
            {
                "field": field,
                "path": path.relative_to(repo).as_posix(),
                "sha256": actual,
            }
        )

    frozen = contract["frozen_inputs"]
    input_paths = {
        "question_set_file_sha256": (
            qec_run / "preregistered_input_workspace/question_set.json"
        ),
        "workspace_manifest_sha256": (
            qec_run / "preregistered/workspace_manifest.json"
        ),
        "question_projection_sha256": qec_run / "frozen/question_projection.json",
        "source_bindings_sha256": qec_run / "frozen/source_bindings.json",
    }
    input_checks: list[dict[str, str]] = []
    for field, path in input_paths.items():
        actual = sha256_file(path)
        if actual != frozen[field]:
            raise QECPSRExperimentError(f"QEC_PSR_FROZEN_INPUT_DRIFT:{field}")
        input_checks.append(
            {
                "field": field,
                "path": path.relative_to(repo).as_posix(),
                "sha256": actual,
            }
        )
    sparse_index = load_json(qec_run / "route_assets/sparse_index.json")
    if sparse_index.get("index_payload_sha256") != frozen[
        "index_payload_sha256"
    ]:
        raise QECPSRExperimentError("QEC_PSR_INDEX_PAYLOAD_DRIFT")

    catalog_dir = qec_run / "preregistered_input_workspace/source_catalog_v2"
    catalog_paths = sorted(catalog_dir.glob("*.json"))
    if {path.stem for path in catalog_paths} != set(
        frozen["catalog_file_sha256"]
    ):
        raise QECPSRExperimentError("QEC_PSR_CATALOG_SET_DRIFT")
    catalog_checks: list[dict[str, str]] = []
    for path in catalog_paths:
        actual = sha256_file(path)
        if actual != frozen["catalog_file_sha256"][path.stem]:
            raise QECPSRExperimentError(f"QEC_PSR_CATALOG_FILE_DRIFT:{path.stem}")
        catalog_checks.append(
            {
                "source_id": path.stem,
                "path": path.relative_to(repo).as_posix(),
                "sha256": actual,
            }
        )

    program = contract["frozen_program_surface"]
    program_paths = {
        "qec_activate_file_sha256": Path(qec.__file__),
        "qec_experiment_runner_file_sha256": (
            Path(qec.__file__).with_name("qec_experiment_runner.py")
        ),
        "route_runner_file_sha256": Path(route_runner.__file__),
        "offline_scorer_file_sha256": (
            Path(route_runner.__file__).with_name("offline_scorer.py")
        ),
    }
    program_checks: list[dict[str, str]] = []
    for field, path in program_paths.items():
        actual = sha256_file(path)
        if actual != program[field]:
            raise QECPSRExperimentError(f"QEC_PSR_PROGRAM_FILE_DRIFT:{field}")
        program_checks.append({"field": field, "path": str(path), "sha256": actual})
    functions = {
        "a5_query_variants": route_runner._query_variants,
        "build_sparse_index": route_runner.build_sparse_index,
        "rank_paragraphs": route_runner.rank_paragraphs,
        "merge_rankings_nonzero_fusion": (
            route_runner._merge_rankings_nonzero_fusion
        ),
        "pack_nonzero_fusion": route_runner._pack_nonzero_fusion,
        "selection_projection": route_runner.selection_projection,
        "qec_validate_trace": qec.validate_trace,
        "qec_decide_primary": qec.decide_primary,
    }
    function_checks: dict[str, str] = {}
    for name, function in functions.items():
        actual = _function_sha(function)
        if actual != program["function_sha256"][name]:
            raise QECPSRExperimentError(f"QEC_PSR_FUNCTION_DRIFT:{name}")
        function_checks[name] = actual

    reference = contract["reference_freeze"]
    run_dir = repo / contract["run_directory"]
    reference_paths = {
        "builder_sha256": run_dir / "preregistered/qec_psr_reference_builder.py",
        "eligibility_sha256": (
            run_dir / "preregistered/qec_psr_reference_eligibility.json"
        ),
        "projection_sha256": (
            run_dir / "preregistered/qec_psr_reference_projection.json"
        ),
        "determinism_receipt_sha256": (
            run_dir / "preregistered/reference_determinism_receipt.json"
        ),
    }
    reference_checks: list[dict[str, str]] = []
    for field, path in reference_paths.items():
        actual = sha256_file(path)
        if actual != reference[field]:
            raise QECPSRExperimentError(f"QEC_PSR_REFERENCE_DRIFT:{field}")
        reference_checks.append(
            {
                "field": field,
                "path": path.relative_to(repo).as_posix(),
                "sha256": actual,
            }
        )
    return (
        {
            "status": "PASS",
            "control_run": qec_run.relative_to(repo).as_posix(),
            "control_file_checks": file_checks,
            "frozen_input_checks": input_checks,
            "catalog_checks": catalog_checks,
            "program_checks": program_checks,
            "function_checks": function_checks,
            "reference_checks": reference_checks,
            "hidden_development_file_opened": False,
            "scorer_imported": False,
        },
        {
            "qec_run": qec_run,
            "catalog_dir": catalog_dir,
            "public_paths": _public_paths(qec_run),
        },
    )


def _load_public_inputs(paths: Mapping[str, Path]) -> dict[str, Any]:
    return {name: load_json(path) for name, path in paths.items()}


def _source_business_literal_count(
    *, public_inputs: Mapping[str, Any]
) -> dict[str, Any]:
    values: set[str] = set()
    for row in public_inputs["question_plans"]["plans"]:
        values.add(row["question_id"])
    for row in public_inputs["query_bindings"]["cells"]:
        values.add(row["cell_id"])
        values.add(row["cell_id"].split("::", 1)[0])
    source = (
        Path(psr.__file__).read_text(encoding="utf-8")
        + "\n"
        + Path(__file__).read_text(encoding="utf-8")
    )
    hits = sorted(value for value in values if value and value in source)
    if hits:
        raise QECPSRExperimentError(
            f"QEC_PSR_PRODUCTION_BUSINESS_LITERAL_FOUND:{hits}"
        )
    return {
        "status": "PASS",
        "literal_universe_count": len(values),
        "hit_count": 0,
        "scanned_files": [str(Path(psr.__file__)), str(Path(__file__))],
    }


def _validate_output_against_public_catalogs(
    *,
    output: Mapping[str, Any],
    catalog_dir: Path,
    budget_chars: int,
) -> dict[str, Any]:
    _verify_payload(output, field="output_payload_sha256", label="SEALED_OUTPUT")
    paragraphs: dict[str, dict[str, Any]] = {}
    for path in sorted(catalog_dir.glob("*.json")):
        catalog = load_json(path)
        for row in catalog["paragraphs"]:
            paragraphs[row["paragraph_id"]] = {
                "source_id": catalog["source_id"],
                "char_count": len(row["original_text"]),
                "sha256": sha256_bytes(row["original_text"].encode("utf-8")),
            }
    for cell in output["cells"]:
        seen_ids: set[str] = set()
        seen_ranks: set[int] = set()
        used = 0
        for window in cell["selected_windows"]:
            paragraph_id = window["paragraph_id"]
            paragraph = paragraphs.get(paragraph_id)
            if paragraph is None or paragraph["source_id"] != cell["case_id"]:
                raise QECPSRExperimentError(
                    f"QEC_PSR_PUBLIC_PARAGRAPH_BINDING_INVALID:{paragraph_id}"
                )
            if paragraph_id in seen_ids or window["rank"] in seen_ranks:
                raise QECPSRExperimentError(
                    f"QEC_PSR_PUBLIC_SELECTION_DUPLICATED:{cell['cell_id']}"
                )
            if window["char_count"] != paragraph["char_count"]:
                raise QECPSRExperimentError(
                    f"QEC_PSR_PUBLIC_CHAR_COUNT_DRIFT:{paragraph_id}"
                )
            seen_ids.add(paragraph_id)
            seen_ranks.add(window["rank"])
            used += int(window["char_count"])
        if used != cell["candidate_chars"] or used > budget_chars:
            raise QECPSRExperimentError(
                f"QEC_PSR_PUBLIC_BUDGET_INVALID:{cell['cell_id']}"
            )
    return {
        "status": "PASS",
        "cell_count": len(output["cells"]),
        "paragraph_count": len(paragraphs),
        "all_cells_within_budget": True,
    }


def _validate_against_reference(
    *,
    contract: Mapping[str, Any],
    run_dir: Path,
    candidate: Mapping[str, Mapping[str, Any]],
    public_inputs: Mapping[str, Any],
) -> dict[str, Any]:
    reference_projection_path = (
        run_dir / "preregistered/qec_psr_reference_projection.json"
    )
    actual_projection = canonical_bytes(candidate["selection_projection"])
    if actual_projection != reference_projection_path.read_bytes():
        raise QECPSRExperimentError("QEC_PSR_PRODUCTION_REFERENCE_PROJECTION_DRIFT")

    reference = load_json(
        run_dir / "preregistered/qec_psr_reference_eligibility.json"
    )
    actual_by_id = {
        row["cell_id"]: row for row in candidate["protection_trace"]["cells"]
    }
    reference_by_id = {row["cell_id"]: row for row in reference["cells"]}
    if set(actual_by_id) != set(reference_by_id):
        raise QECPSRExperimentError("QEC_PSR_REFERENCE_CELL_SET_DRIFT")
    compare_fields = (
        "candidate_selected_ids",
        "candidate_source_chars",
        "state_selected_count",
        "state_source_chars",
        "protections",
        "added_vs_qec_control",
        "removed_vs_qec_control",
        "eligible",
    )
    for cell_id in sorted(actual_by_id):
        for field in compare_fields:
            if actual_by_id[cell_id][field] != reference_by_id[cell_id][field]:
                raise QECPSRExperimentError(
                    f"QEC_PSR_REFERENCE_FIELD_DRIFT:{cell_id}:{field}"
                )

    controls = {
        row["cell_id"]: row
        for row in public_inputs["qec_selection_projection_2500"]["cells"]
    }
    actual_projection_by_id = {
        row["cell_id"]: row
        for row in candidate["selection_projection"]["cells"]
    }
    noneligible_equal_count = 0
    for cell_id, row in reference_by_id.items():
        if row["eligible"]:
            continue
        if actual_projection_by_id[cell_id] != controls[cell_id]:
            raise QECPSRExperimentError(
                f"QEC_PSR_NONELIGIBLE_CONTROL_DRIFT:{cell_id}"
            )
        noneligible_equal_count += 1
    non_regression_equal_count = 0
    for case_id in contract["reference_freeze"]["non_regression_cases"]:
        for cell_id in sorted(actual_projection_by_id):
            if cell_id.split("::", 1)[0] != case_id:
                continue
            if actual_projection_by_id[cell_id] != controls[cell_id]:
                raise QECPSRExperimentError(
                    f"QEC_PSR_NON_REGRESSION_CASE_DRIFT:{cell_id}"
                )
            non_regression_equal_count += 1
    if non_regression_equal_count != contract["reference_freeze"][
        "expected_non_regression_cell_count"
    ]:
        raise QECPSRExperimentError("QEC_PSR_NON_REGRESSION_CELL_COUNT_DRIFT")
    trace = candidate["protection_trace"]
    if trace["eligible_cell_count"] != contract["reference_freeze"][
        "eligible_cell_count"
    ]:
        raise QECPSRExperimentError("QEC_PSR_ELIGIBLE_CELL_COUNT_DRIFT")
    if trace["protected_plan_unit_record_count"] != contract["reference_freeze"][
        "protected_plan_unit_record_count"
    ]:
        raise QECPSRExperimentError("QEC_PSR_PROTECTION_RECORD_COUNT_DRIFT")
    return {
        "status": "PASS",
        "projection_byte_identical": True,
        "eligible_cell_count": trace["eligible_cell_count"],
        "protected_plan_unit_record_count": trace[
            "protected_plan_unit_record_count"
        ],
        "noneligible_cell_count_equal_control": noneligible_equal_count,
        "non_regression_cell_count_equal_control": non_regression_equal_count,
    }


def build_pre_score_artifacts(
    *,
    repo: Path,
    contract: Mapping[str, Any],
    baseline: Mapping[str, Any],
    paths: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    public_paths = paths["public_paths"]
    public_inputs = _load_public_inputs(public_paths)
    kwargs = {
        "question_plan_collection": public_inputs["question_plans"],
        "query_binding_collection": public_inputs["query_bindings"],
        "rank_stream_collection": public_inputs["rank_streams"],
        "qec_trace_collection": public_inputs["qec_trace_2500"],
        "control_projection": public_inputs[
            "qec_selection_projection_2500"
        ],
        "control_output": public_inputs["qec_sealed_output_2500"],
        "budget_chars": contract["primary_budget_chars"],
    }
    first = psr.build_candidate(**kwargs)
    second = psr.build_candidate(**kwargs)
    determinism: list[dict[str, Any]] = []
    for name in sorted(first):
        first_bytes = canonical_bytes(first[name])
        second_bytes = canonical_bytes(second[name])
        if first_bytes != second_bytes:
            raise QECPSRExperimentError(
                f"QEC_PSR_TWO_GENERATIONS_DRIFT:{name}"
            )
        determinism.append(
            {
                "artifact": name,
                "sha256": sha256_bytes(first_bytes),
                "byte_identical": True,
            }
        )

    run_dir = repo / contract["run_directory"]
    reference_check = _validate_against_reference(
        contract=contract,
        run_dir=run_dir,
        candidate=first,
        public_inputs=public_inputs,
    )
    public_output_check = _validate_output_against_public_catalogs(
        output=first["sealed_output"],
        catalog_dir=paths["catalog_dir"],
        budget_chars=contract["primary_budget_chars"],
    )
    business_literals = _source_business_literal_count(
        public_inputs=public_inputs
    )
    if any(
        row["residual_fit_remaining_count"] != 0
        for row in first["protection_trace"]["cells"]
    ):
        raise QECPSRExperimentError("QEC_PSR_RESIDUAL_FILL_NOT_MAXIMAL")
    gate: dict[str, Any] = {
        "schema_version": PRE_SCORE_GATE_SCHEMA,
        "status": "PASS",
        "route_id": psr.ROUTE_ID,
        "run_id": contract["run_id"],
        "experiment_contract_sha256": sha256_file(
            run_dir / "preregistered/qec_psr_experiment_contract.json"
        ),
        "baseline_verification": baseline,
        "candidate_program": {
            "sidecar_path": Path(psr.__file__).relative_to(repo).as_posix(),
            "sidecar_sha256": sha256_file(Path(psr.__file__)),
            "runner_path": Path(__file__).relative_to(repo).as_posix(),
            "runner_sha256": sha256_file(Path(__file__)),
            "business_id_literal_scan": business_literals,
        },
        "public_construction_input_whitelist": [
            {
                "id": name,
                "path": path.relative_to(repo).as_posix(),
                "sha256": sha256_file(path),
            }
            for name, path in public_paths.items()
        ],
        "candidate_generation": {
            "generation_count": 2,
            "byte_identical": True,
            "artifacts": determinism,
        },
        "independent_reference_check": reference_check,
        "public_output_check": public_output_check,
        "residual_fill_maximal": True,
        "new_query_count": 0,
        "hidden_development_file_opened": False,
        "terminal_question_or_gold_opened": False,
        "scorer_imported_before_gate": False,
        "scorer_calls_before_gate": 0,
        "model_api_calls": 0,
        "network_calls": 0,
        "quality_boundary": (
            "只证明公开冻结选择面按单变量生成且与独立参考逐字一致；"
            "此闸没有读取开发答案，也不构成质量成绩。"
        ),
    }
    gate["gate_payload_sha256"] = _payload_sha(gate, "gate_payload_sha256")
    return gate, first


def _route_manifest(
    *,
    repo: Path,
    contract_sha256: str,
    artifacts: Mapping[str, Mapping[str, Any]],
    artifact_paths: Mapping[str, Path],
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema_version": ROUTE_MANIFEST_SCHEMA,
        "route_id": psr.ROUTE_ID,
        "parent_route_id": psr.CONTROL_ROUTE_ID,
        "candidate_status": "candidate_silver_not_active",
        "primary_budget_chars": artifacts["sealed_output"]["budget_chars"],
        "single_change": "PROTECT_ONE_OUTSIDE_CONTROL_HIT_PER_PUBLIC_PLAN_UNIT",
        "experiment_contract_sha256": contract_sha256,
        "program_sha256": {
            "sidecar": sha256_file(Path(psr.__file__)),
            "runner": sha256_file(Path(__file__)),
        },
        "artifacts": [
            {
                "id": name,
                "path": path.relative_to(repo).as_posix(),
                "sha256": sha256_file(path),
            }
            for name, path in artifact_paths.items()
        ],
        "hidden_root_mounted": False,
        "model_api_calls": 0,
        "network_calls": 0,
    }
    manifest["manifest_payload_sha256"] = _payload_sha(
        manifest, "manifest_payload_sha256"
    )
    return manifest


def prepare_run(
    *,
    repo: Path,
    contract_path: Path,
    expected_contract_sha256: str,
    authorization_ticket_path: Path,
    truth_snapshot_path: Path,
) -> dict[str, Any]:
    contract = load_contract(
        contract_path=contract_path,
        expected_contract_sha256=expected_contract_sha256,
    )
    run_dir = repo / contract["run_directory"]
    if run_dir != contract_path.parents[1]:
        raise QECPSRExperimentError("QEC_PSR_RUN_DIRECTORY_CONTRACT_MISMATCH")
    forbidden = (
        "preregistered/pre_score_gate.json",
        "preregistered/score_bundle_manifest.json",
        "sealed_outputs/QEC-PSR/2500.json",
        "route_assets/selection_projections/QEC-PSR/2500.json",
        "route_assets/qec_psr/protection_trace_2500.json",
        "route_manifests/QEC-PSR.json",
        "route_run_receipt.json",
        "offline_score.json",
        "score_gate_decision.json",
        "official_run_receipt.json",
        "STOP_RECEIPT.md",
    )
    existing = [relative for relative in forbidden if (run_dir / relative).exists()]
    if existing:
        raise QECPSRExperimentError(f"QEC_PSR_RUN_ALREADY_PREPARED:{existing}")

    authority = _verify_authority(
        contract=contract,
        authorization_ticket_path=authorization_ticket_path,
        truth_snapshot_path=truth_snapshot_path,
    )
    baseline, paths = verify_frozen_public_baseline(
        repo=repo, contract=contract
    )
    baseline = {**baseline, "authority": authority}
    gate, artifacts = build_pre_score_artifacts(
        repo=repo, contract=contract, baseline=baseline, paths=paths
    )

    artifact_paths = {
        "sealed_output": run_dir / "sealed_outputs/QEC-PSR/2500.json",
        "selection_projection": (
            run_dir / "route_assets/selection_projections/QEC-PSR/2500.json"
        ),
        "protection_trace": (
            run_dir / "route_assets/qec_psr/protection_trace_2500.json"
        ),
    }
    for name, path in artifact_paths.items():
        write_json(path, artifacts[name])

    manifest = _route_manifest(
        repo=repo,
        contract_sha256=expected_contract_sha256,
        artifacts=artifacts,
        artifact_paths=artifact_paths,
    )
    manifest_path = run_dir / "route_manifests/QEC-PSR.json"
    write_json(manifest_path, manifest)
    receipt: dict[str, Any] = {
        "schema_version": RUN_RECEIPT_SCHEMA,
        "candidate_status": "candidate_silver_not_active",
        "route_count": 1,
        "budget_count": 1,
        "cell_count_per_output": len(artifacts["sealed_output"]["cells"]),
        "outputs": [
            {
                "route_id": psr.ROUTE_ID,
                "budget_chars": contract["primary_budget_chars"],
                "path": artifact_paths["sealed_output"].relative_to(run_dir).as_posix(),
                "sha256": sha256_file(artifact_paths["sealed_output"]),
            }
        ],
        "route_manifests": [
            {
                "route_id": psr.ROUTE_ID,
                "path": manifest_path.relative_to(run_dir).as_posix(),
                "sha256": sha256_file(manifest_path),
            }
        ],
        "scoreable_claim": False,
        "model_api_calls": 0,
        "network_calls": 0,
        "interpretation_boundary": (
            "只封存公开材料生成的单变量候选；计分前总闸通过后才允许"
            "读取一次冻结开发尺。"
        ),
    }
    receipt["receipt_payload_sha256"] = _payload_sha(
        receipt, "receipt_payload_sha256"
    )
    receipt_path = run_dir / "route_run_receipt.json"
    write_json(receipt_path, receipt)

    gate["sealed_candidate_files"] = [
        {
            "id": name,
            "path": path.relative_to(run_dir).as_posix(),
            "sha256": sha256_file(path),
        }
        for name, path in artifact_paths.items()
    ]
    gate["route_manifest_sha256"] = sha256_file(manifest_path)
    gate["route_run_receipt_sha256"] = sha256_file(receipt_path)
    gate["gate_payload_sha256"] = _payload_sha(gate, "gate_payload_sha256")
    gate_path = run_dir / "preregistered/pre_score_gate.json"
    write_json(gate_path, gate)
    return {
        "status": "PASS",
        "stage": "PRE_SCORE_GATE",
        "run_id": contract["run_id"],
        "route_id": psr.ROUTE_ID,
        "experiment_contract_sha256": expected_contract_sha256,
        "pre_score_gate_sha256": sha256_file(gate_path),
        "sealed_output_sha256": sha256_file(artifact_paths["sealed_output"]),
        "selection_projection_sha256": sha256_file(
            artifact_paths["selection_projection"]
        ),
        "protection_trace_sha256": sha256_file(
            artifact_paths["protection_trace"]
        ),
        "hidden_score_run_count": 0,
        "model_api_calls": 0,
        "network_calls": 0,
    }


def _verify_prepared_run(
    *,
    repo: Path,
    run_dir: Path,
    contract: Mapping[str, Any],
    expected_contract_sha256: str,
) -> tuple[dict[str, Any], Path]:
    gate_path = run_dir / "preregistered/pre_score_gate.json"
    gate = load_json(gate_path)
    if gate.get("schema_version") != PRE_SCORE_GATE_SCHEMA:
        raise QECPSRExperimentError("QEC_PSR_PRE_SCORE_GATE_SCHEMA_INVALID")
    if gate.get("status") != "PASS":
        raise QECPSRExperimentError("QEC_PSR_PRE_SCORE_GATE_NOT_PASS")
    _verify_payload(gate, field="gate_payload_sha256", label="PRE_SCORE_GATE")
    if gate.get("experiment_contract_sha256") != expected_contract_sha256:
        raise QECPSRExperimentError("QEC_PSR_PRE_SCORE_GATE_CONTRACT_DRIFT")
    if (
        gate.get("hidden_development_file_opened") is not False
        or gate.get("scorer_calls_before_gate") != 0
        or gate.get("model_api_calls") != 0
        or gate.get("network_calls") != 0
    ):
        raise QECPSRExperimentError("QEC_PSR_PRE_SCORE_GATE_ISOLATION_INVALID")
    for record in gate["sealed_candidate_files"]:
        path = run_dir / record["path"]
        if sha256_file(path) != record["sha256"]:
            raise QECPSRExperimentError(
                f"QEC_PSR_SEALED_CANDIDATE_DRIFT:{record['id']}"
            )
    manifest_path = run_dir / "route_manifests/QEC-PSR.json"
    receipt_path = run_dir / "route_run_receipt.json"
    if sha256_file(manifest_path) != gate["route_manifest_sha256"]:
        raise QECPSRExperimentError("QEC_PSR_ROUTE_MANIFEST_DRIFT")
    if sha256_file(receipt_path) != gate["route_run_receipt_sha256"]:
        raise QECPSRExperimentError("QEC_PSR_ROUTE_RECEIPT_DRIFT")
    if (repo / contract["run_directory"]) != run_dir:
        raise QECPSRExperimentError("QEC_PSR_PREPARED_RUN_DIRECTORY_DRIFT")
    return gate, gate_path


def _load_catalogs_for_score(catalog_dir: Path) -> list[dict[str, Any]]:
    paths = sorted(catalog_dir.glob("*.json"))
    if not paths:
        raise QECPSRExperimentError("QEC_PSR_SCORE_CATALOGS_MISSING")
    return [load_json(path) for path in paths]


def _score_bundle(
    *,
    repo: Path,
    run_dir: Path,
    gate_path: Path,
    hidden_path: Path,
    hidden_sha256: str,
    catalog_dir: Path,
    scorer_path: Path,
) -> dict[str, Any]:
    output_path = run_dir / "sealed_outputs/QEC-PSR/2500.json"
    manifest_path = run_dir / "route_manifests/QEC-PSR.json"
    receipt_path = run_dir / "route_run_receipt.json"
    bundle: dict[str, Any] = {
        "schema_version": SCORE_BUNDLE_SCHEMA,
        "issuer_type": "LOCAL_PREREGISTERED_CANDIDATE",
        "sealed_before_score": True,
        "route_id": psr.ROUTE_ID,
        "candidate_budget_count": 1,
        "candidate_output": {
            "path": output_path.relative_to(repo).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "route_manifest_sha256": sha256_file(manifest_path),
        "route_run_receipt_sha256": sha256_file(receipt_path),
        "pre_score_gate_sha256": sha256_file(gate_path),
        "hidden_cells": {
            "path": hidden_path.relative_to(repo).as_posix(),
            "sha256": hidden_sha256,
        },
        "catalog_bindings": [
            {
                "path": path.relative_to(repo).as_posix(),
                "sha256": sha256_file(path),
            }
            for path in sorted(catalog_dir.glob("*.json"))
        ],
        "scorer_sha256": sha256_file(scorer_path),
        "planned_scorer_call_count": 1,
        "control_score_source": "FROZEN_EXISTING_QEC_SCORE_ONLY",
    }
    bundle["bundle_payload_sha256"] = _payload_sha(
        bundle, "bundle_payload_sha256"
    )
    return bundle


def _stop_receipt_markdown(
    *,
    decision: Mapping[str, Any],
    score: Mapping[str, Any],
    contract_sha256: str,
    gate_sha256: str,
    score_bundle_sha256: str,
    score_sha256: str,
) -> str:
    candidate = score["candidate_score"]
    control = score["control_score_reused"]
    actual = decision["actual"]
    lines = [
        "# 【主线一·M1-02】R2 最后一道语义臂停点",
        "",
        f"✅ 结论：`{decision['disposition']}`。QEC-PSR 已按跑前合同只做一次冻结开发集评分，M1-02 到此关闭，不因分数调参重跑。",
        "",
        f"- 候选：完整题 {candidate['full_question_recall_count']}/28，必答头 {candidate['required_head_recall_count']}/115。",
        f"- 冻结 QEC 对照（复用旧成绩，未重跑）：完整题 {control['full_question_recall_count']}/28，必答头 {control['required_head_recall_count']}/115。",
    ]
    for case_id, row in sorted(candidate["per_case"].items()):
        complete_key = f"{case_id}_complete_questions"
        heads_key = f"{case_id}_required_heads"
        lines.append(
            f"- {case_id}：{actual[complete_key]}/{row['question_total']} 完整题，"
            f"{actual[heads_key]}/{row['head_total']} 必答头。"
        )
    lines.extend(
        [
            "",
            "🔥 边界：这里测的是开发集证据窗口覆盖，不是答案正确率，也不是终验成绩；候选不升默认。",
            "",
            f"- 实验合同 SHA：`{contract_sha256}`",
            f"- 计分前总闸 SHA：`{gate_sha256}`",
            f"- 计分包 SHA：`{score_bundle_sha256}`",
            f"- 离线成绩 SHA：`{score_sha256}`",
            "- 模型 API 0，网络 0；开发集评分调用 1；未重跑、未改判据、未动金标。",
            "",
            "👉 下一步：进入 M1-03。只接受主线三封存题集与封签票；主线一不出题、不改题。封签允许一次终验前，只做封签和运行条件核验。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def score_once(
    *,
    repo: Path,
    contract_path: Path,
    expected_contract_sha256: str,
    authorization_ticket_path: Path,
    truth_snapshot_path: Path,
    hidden_cells_path: Path,
) -> dict[str, Any]:
    contract = load_contract(
        contract_path=contract_path,
        expected_contract_sha256=expected_contract_sha256,
    )
    run_dir = repo / contract["run_directory"]
    score_outputs = (
        "preregistered/score_bundle_manifest.json",
        "offline_score.json",
        "score_gate_decision.json",
        "official_run_receipt.json",
        "STOP_RECEIPT.md",
    )
    existing = [relative for relative in score_outputs if (run_dir / relative).exists()]
    if existing:
        raise QECPSRExperimentError(f"QEC_PSR_SCORE_ALREADY_USED:{existing}")
    _verify_authority(
        contract=contract,
        authorization_ticket_path=authorization_ticket_path,
        truth_snapshot_path=truth_snapshot_path,
    )
    gate, gate_path = _verify_prepared_run(
        repo=repo,
        run_dir=run_dir,
        contract=contract,
        expected_contract_sha256=expected_contract_sha256,
    )

    hidden_bytes = hidden_cells_path.read_bytes()
    hidden_sha = sha256_bytes(hidden_bytes)
    expected_hidden_sha = contract["scoring_policy"][
        "hidden_development_cells_sha256"
    ]
    if hidden_sha != expected_hidden_sha:
        raise QECPSRExperimentError("QEC_PSR_HIDDEN_DEVELOPMENT_SHA_DRIFT")
    try:
        hidden = json.loads(hidden_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QECPSRExperimentError("QEC_PSR_HIDDEN_DEVELOPMENT_JSON_INVALID") from exc

    qec_run = repo / contract["control_route"]["run_directory"]
    catalog_dir = qec_run / "preregistered_input_workspace/source_catalog_v2"
    scorer_path = Path(route_runner.__file__).with_name("offline_scorer.py")
    if sha256_file(scorer_path) != contract["frozen_program_surface"][
        "offline_scorer_file_sha256"
    ]:
        raise QECPSRExperimentError("QEC_PSR_SCORER_SHA_DRIFT")
    bundle = _score_bundle(
        repo=repo,
        run_dir=run_dir,
        gate_path=gate_path,
        hidden_path=hidden_cells_path,
        hidden_sha256=hidden_sha,
        catalog_dir=catalog_dir,
        scorer_path=scorer_path,
    )
    bundle_path = run_dir / "preregistered/score_bundle_manifest.json"
    write_json(bundle_path, bundle)

    from . import offline_scorer

    candidate_output = load_json(
        run_dir / "sealed_outputs/QEC-PSR/2500.json"
    )
    catalogs = _load_catalogs_for_score(catalog_dir)
    scorer_call_count = 0
    scorer_call_count += 1
    candidate_score = offline_scorer.score_route_output(
        route_output=candidate_output,
        hidden_cells=hidden["cells"],
        catalogs=catalogs,
        expected_index_payload_sha256=contract["frozen_inputs"][
            "index_payload_sha256"
        ],
    )
    if scorer_call_count != 1:
        raise QECPSRExperimentError("QEC_PSR_SCORER_CALL_COUNT_NOT_ONE")

    control_score_path = qec_run / "offline_score.json"
    if sha256_file(control_score_path) != contract["control_route"][
        "offline_score_sha256"
    ]:
        raise QECPSRExperimentError("QEC_PSR_CONTROL_SCORE_SHA_DRIFT")
    control_score_collection = load_json(control_score_path)
    control_rows = [
        row
        for row in control_score_collection["rows"]
        if row["route_id"] == psr.CONTROL_ROUTE_ID
        and row["budget_chars"] == contract["primary_budget_chars"]
    ]
    if len(control_rows) != 1:
        raise QECPSRExperimentError("QEC_PSR_CONTROL_SCORE_ROW_NOT_UNIQUE")
    score: dict[str, Any] = {
        "schema_version": SCORE_RECEIPT_SCHEMA,
        "candidate_status": "candidate_silver_not_active",
        "route_id": psr.ROUTE_ID,
        "primary_budget_chars": contract["primary_budget_chars"],
        "candidate_score": candidate_score,
        "control_score_reused": control_rows[0],
        "control_rescored": False,
        "hidden_development_cells_sha256": hidden_sha,
        "score_bundle_sha256": sha256_file(bundle_path),
        "scorer_sha256": sha256_file(scorer_path),
        "hidden_score_run_count": 1,
        "candidate_budget_count_scored": 1,
        "scorer_call_count": scorer_call_count,
        "model_api_calls": 0,
        "network_calls": 0,
        "quality_boundary": (
            "只测冻结窗口覆盖开发集证据组，不等于答案正确率或终验成绩。"
        ),
    }
    score["score_payload_sha256"] = _payload_sha(
        score, "score_payload_sha256"
    )
    score_path = run_dir / "offline_score.json"
    write_json(score_path, score)

    decision = qec.decide_primary(
        contract=contract, score_row=candidate_score
    )
    decision["route_id"] = psr.ROUTE_ID
    decision["control_score_reused"] = True
    decision["hidden_score_run_count"] = 1
    decision.pop("decision_payload_sha256", None)
    decision["decision_payload_sha256"] = _payload_sha(
        decision, "decision_payload_sha256"
    )
    decision_path = run_dir / "score_gate_decision.json"
    write_json(decision_path, decision)

    official: dict[str, Any] = {
        "schema_version": OFFICIAL_RECEIPT_SCHEMA,
        "status": "M1_02_CLOSED",
        "run_id": contract["run_id"],
        "route_id": psr.ROUTE_ID,
        "disposition": decision["disposition"],
        "register_candidate": decision["register_candidate"],
        "experiment_contract_sha256": expected_contract_sha256,
        "pre_score_gate_sha256": sha256_file(gate_path),
        "score_bundle_sha256": sha256_file(bundle_path),
        "offline_score_sha256": sha256_file(score_path),
        "score_gate_decision_sha256": sha256_file(decision_path),
        "hidden_score_run_count": 1,
        "candidate_budget_count_scored": 1,
        "control_rescored": False,
        "rerun_allowed": False,
        "model_api_calls": 0,
        "network_calls": 0,
        "next_stage": "M1_03_VERIFY_MAINLINE_THREE_SEAL",
    }
    official["receipt_payload_sha256"] = _payload_sha(
        official, "receipt_payload_sha256"
    )
    official_path = run_dir / "official_run_receipt.json"
    write_json(official_path, official)
    stop_path = run_dir / "STOP_RECEIPT.md"
    stop_path.write_text(
        _stop_receipt_markdown(
            decision=decision,
            score=score,
            contract_sha256=expected_contract_sha256,
            gate_sha256=sha256_file(gate_path),
            score_bundle_sha256=sha256_file(bundle_path),
            score_sha256=sha256_file(score_path),
        ),
        encoding="utf-8",
    )
    return {
        "status": "M1_02_CLOSED",
        "run_id": contract["run_id"],
        "route_id": psr.ROUTE_ID,
        "disposition": decision["disposition"],
        "candidate_complete_questions": candidate_score[
            "full_question_recall_count"
        ],
        "candidate_required_heads": candidate_score[
            "required_head_recall_count"
        ],
        "hidden_score_run_count": 1,
        "rerun_allowed": False,
        "official_run_receipt_sha256": sha256_file(official_path),
        "stop_receipt_sha256": sha256_file(stop_path),
        "model_api_calls": 0,
        "network_calls": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "score"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--repo", type=Path, required=True)
        sub.add_argument("--contract", type=Path, required=True)
        sub.add_argument("--contract-sha256", required=True)
        sub.add_argument("--authorization-ticket", type=Path, required=True)
        sub.add_argument("--truth-snapshot", type=Path, required=True)
        if command == "score":
            sub.add_argument("--hidden-cells", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    common = {
        "repo": args.repo.resolve(),
        "contract_path": args.contract.resolve(),
        "expected_contract_sha256": args.contract_sha256,
        "authorization_ticket_path": args.authorization_ticket.resolve(),
        "truth_snapshot_path": args.truth_snapshot.resolve(),
    }
    if args.command == "prepare":
        result = prepare_run(**common)
    else:
        result = score_once(
            **common, hidden_cells_path=args.hidden_cells.resolve()
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
