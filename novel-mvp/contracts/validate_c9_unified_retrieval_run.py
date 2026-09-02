#!/usr/bin/env python3
"""校验 C9 统一取件合同的 24 个纯合成夹具。"""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


DIR = Path(__file__).resolve().parent
PRODUCT_ROOT = DIR.parent
FIXTURE_PATH = DIR / "C9_UNIFIED_RETRIEVAL_RUN.fixtures.jsonl"
SCHEMA_PATH = DIR / "C9_UNIFIED_RETRIEVAL_RUN.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA)
SCHEMA_VALIDATOR = Draft202012Validator(SCHEMA)

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import unified_retrieval_core as core
finally:
    sys.path.pop(0)


EXPECTED_COUNTS = {
    "READY": 6,
    "READY_WITH_GAPS": 3,
    "STOPPED": 3,
    "STRUCTURAL_INVALID": 12,
}
FIXTURE_FIELDS = {"case_id", "scenario", "expected_result"}


class FixtureError(ValueError):
    """夹具自身不符合冻结预期。"""


def _validate_schema_instance(value: Any) -> None:
    errors = sorted(
        SCHEMA_VALIDATOR.iter_errors(value),
        key=lambda item: (list(item.absolute_path), item.message),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].absolute_path) or "$"
        raise FixtureError(f"SCHEMA_INSTANCE_INVALID:{path}")


def _scope() -> dict[str, Any]:
    return {
        "author_id": "AUTHOR-0001",
        "project_id": "PROJECT-0001",
        "task_id": "TASK-C9-0001",
        "consumer_id": "CONSUMER-SYNTHETIC",
        "workpoint_ref": "chapter:c12@3",
        "story_scope_ref": "story-phase:phase-02",
        "sandbox_ref": "sandbox:chapter-c13",
        "upstream_card_ref": "card:synthetic-01",
    }


def _need(
    need_id: str,
    *,
    layer: str = "LEDGER_OBJECT",
    parent: str | None = None,
    source_contract: str = "LEDGER_READ_TOOL_CONTRACT",
    obligation: str = "HARD",
    rank: int | None = None,
    tokens: int = 20,
    actuality: str = "CURRENT_FACT_OR_STATE",
    trigger: str = "INITIAL",
) -> dict[str, Any]:
    return {
        "need_id": need_id,
        "evidence_layer": layer,
        "parent_need_id": parent,
        "source_contract": source_contract,
        "source_contract_version": core.SOURCE_CONTRACT_VERSIONS[source_contract],
        "object_ref": f"synthetic://{need_id}",
        "actuality_class": actuality,
        "obligation_tier": obligation,
        "selection_rank": rank,
        "task_relation": f"合成任务需要 {need_id}",
        "estimated_tokens": tokens,
        "recall_disposition": "RETRIEVABLE",
        "recall_handle": f"synthetic-recall://{need_id}",
        "expansion_trigger": trigger,
    }


def _request(
    needs: list[dict[str, Any]],
    *,
    basis_mode: str = "current_at_start",
    budget: int = 200,
    gap_behavior: str = "WARN_AND_CONTINUE",
) -> dict[str, Any]:
    return core.seal_request(
        {
            "contract": "C9_RETRIEVAL_REQUEST",
            "version": core.VERSION,
            "scope": _scope(),
            "basis_mode": basis_mode,
            "task_actuality_scope": "CURRENT_TRUTH_REQUIRED",
            "budget": {
                "limit_tokens": budget,
                "estimator_ref": "synthetic-estimator-v1",
            },
            "gap_policy": {
                "policy_ref": "synthetic-gap-policy-v1",
                "missing_required_behavior": gap_behavior,
            },
            "source_needs": copy.deepcopy(needs),
        }
    )


def _source_document(
    need: Mapping[str, Any],
    *,
    basis_mode: str,
    status: str,
    reason_code: str | None,
    validation_result: str,
    project_id: str = "PROJECT-0001",
) -> dict[str, Any]:
    source_contract = need["source_contract"]
    if source_contract == "LEDGER_READ_TOOL_CONTRACT":
        basis_sha256 = core.sha256_json(
            {
                "need_id": need["need_id"],
                "basis_mode": basis_mode,
                "project_id": project_id,
            }
        )
        return {
            "contract": "LEDGER_READ_RESPONSE",
            "version": core.SOURCE_CONTRACT_VERSIONS[source_contract],
            "status": status,
            "reason_code": reason_code,
            "basis_mode": basis_mode,
            "request_id": f"READ-{need['need_id']}",
            "receipt": {
                "author_id": "AUTHOR-0001",
                "project_id": project_id,
                "basis_sha256": basis_sha256,
            },
            "synthetic_validation": validation_result,
        }
    return {
        "contract": core.SOURCE_DOCUMENT_CONTRACTS[source_contract],
        "version": core.SOURCE_CONTRACT_VERSIONS[source_contract],
        "truth_scope_ref": {
            "principal_author_id": "AUTHOR-0001",
            "project_id": project_id,
        },
        "synthetic_validation": validation_result,
    }


def _outcome(
    need: Mapping[str, Any],
    *,
    basis_mode: str,
    status: str = "OK",
    reason_code: str | None = None,
    validation_result: str = "STRUCTURAL_VALID",
    project_id: str = "PROJECT-0001",
    material_text: str | None = None,
) -> dict[str, Any]:
    if status == "NOT_ATTEMPTED":
        return {
            "need_id": need["need_id"],
            "source_status": status,
            "reason_code": reason_code or "OWNER_RUNTIME_NOT_AVAILABLE",
            "source_document": None,
            "material_text": None,
            "validator_id": None,
        }
    return {
        "need_id": need["need_id"],
        "source_status": status,
        "reason_code": reason_code,
        "source_document": _source_document(
            need,
            basis_mode=basis_mode,
            status=status,
            reason_code=reason_code,
            validation_result=validation_result,
            project_id=project_id,
        ),
        "material_text": (
            material_text
            if material_text is not None
            else (f"{need['need_id']} 的合成材料" if status == "OK" else None)
        ),
        "validator_id": f"synthetic-validator:{need['source_contract']}:v1",
    }


def _synthetic_ledger_validator(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("synthetic_validation") != (
        "STRUCTURAL_VALID"
    ):
        raise FixtureError("SYNTHETIC_LEDGER_SOURCE_INVALID")
    return copy.deepcopy(document)


def _synthetic_object_validator(document: Any) -> str:
    if not isinstance(document, dict):
        raise FixtureError("SYNTHETIC_SOURCE_NOT_OBJECT")
    result = document.get("synthetic_validation")
    if result not in {
        "STRUCTURAL_VALID",
        "STRUCTURAL_VALID_OWNER_UNRESOLVED",
    }:
        raise FixtureError("SYNTHETIC_SOURCE_INVALID")
    return result


def _registry() -> dict[str, Callable[[Any], Any]]:
    return {
        "LEDGER_READ_TOOL_CONTRACT": _synthetic_ledger_validator,
        "TRACEABLE_PROVENANCE_SEAL": _synthetic_object_validator,
        "CHAPTER_SETTLEMENT_SEAL": _synthetic_object_validator,
        "CHAPTER_LAYERED_SUMMARY": _synthetic_object_validator,
    }


def _standard_chain() -> list[dict[str, Any]]:
    return [
        _need(
            "NEED-LEDGER",
            source_contract="CHAPTER_SETTLEMENT_SEAL",
        ),
        _need(
            "NEED-FORMATION",
            layer="FORMATION_BASIS",
            parent="NEED-LEDGER",
            source_contract="TRACEABLE_PROVENANCE_SEAL",
            obligation="SHOULD",
            rank=1,
            trigger="CONFLICT_DETECTED",
        ),
        _need(
            "NEED-ORIGINAL",
            layer="ORIGINAL_EVIDENCE",
            parent="NEED-FORMATION",
            obligation="MAY",
            rank=2,
            trigger="AUDIT_REQUIRED",
        ),
    ]


def _build_run(
    scenario: str,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Callable[[Any], Any]],
]:
    basis_mode = "current_at_start"
    budget = 200
    gap_behavior = "WARN_AND_CONTINUE"

    if scenario in {"ready_formation", "ready_original_audit"}:
        needs = _standard_chain()
        if scenario == "ready_formation":
            needs = needs[:2]
    elif scenario == "ready_settlement_summary":
        needs = [
            _need("NEED-SETTLEMENT", source_contract="CHAPTER_SETTLEMENT_SEAL"),
            _need(
                "NEED-SUMMARY",
                source_contract="CHAPTER_LAYERED_SUMMARY",
                obligation="SHOULD",
                rank=1,
            ),
        ]
    elif scenario == "ready_budgeted_reference":
        needs = [
            _need("NEED-HARD", tokens=30),
            _need("NEED-SHOULD", obligation="SHOULD", rank=1, tokens=30),
        ]
        budget = 30
    elif scenario == "ready_pinned":
        needs = [_need("NEED-PINNED")]
        basis_mode = "pinned_manifest"
    elif scenario in {
        "gap_empty_warn",
        "gap_owner_unavailable",
        "gap_assumption_allowed",
        "stop_missing_block",
        "stop_current_advanced",
    }:
        needs = [_need("NEED-PRESENT"), _need("NEED-MISSING")]
        if scenario == "gap_assumption_allowed":
            gap_behavior = "AUTO_CONTINUE"
        if scenario == "stop_missing_block":
            gap_behavior = "BLOCK"
    elif scenario == "stop_hard_budget":
        needs = [_need("NEED-HARD-A", tokens=40), _need("NEED-HARD-B", tokens=40)]
        budget = 60
    else:
        needs = [_need("NEED-LEDGER-ONLY")]

    request = _request(
        needs,
        basis_mode=basis_mode,
        budget=budget,
        gap_behavior=gap_behavior,
    )
    outcomes = [
        _outcome(need, basis_mode=basis_mode)
        for need in needs
    ]

    if scenario in {"gap_empty_warn", "gap_assumption_allowed", "stop_missing_block"}:
        outcomes[1] = _outcome(
            needs[1],
            basis_mode=basis_mode,
            status="EMPTY",
            reason_code="NO_MATCHING_ENTRIES",
        )
    elif scenario == "gap_owner_unavailable":
        outcomes[1] = _outcome(
            needs[1],
            basis_mode=basis_mode,
            status="NOT_ATTEMPTED",
        )
    elif scenario == "stop_current_advanced":
        outcomes[1] = _outcome(
            needs[1],
            basis_mode=basis_mode,
            status="REJECTED",
            reason_code="CURRENT_ADVANCED",
        )
    return request, outcomes, _registry()


def _reseal(value: dict[str, Any], field: str) -> None:
    value.pop(field, None)
    value[field] = core.sha256_json(value)


def _mutated_result(scenario: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    request, outcomes, registry = _build_run("ready_ledger")
    plan = core.prepare_plan(request)
    result = core.compile_result(request, plan, outcomes, registry)
    package = result["material_package"]

    if scenario == "invalid_overlap":
        loaded = package["loaded"][0]
        package["omitted"].append(
            {
                "need_id": loaded["need_id"],
                "object_ref": loaded["object_ref"],
                "reason": "BUDGET_OPTIONAL_DEFERRED",
                "source_validation": copy.deepcopy(loaded["source_validation"]),
                "recall_disposition": loaded["recall_disposition"],
                "recall_handle": loaded["recall_handle"],
            }
        )
        _reseal(package, "package_sha256")
    elif scenario == "invalid_unaccounted":
        package["loaded"] = []
        _reseal(package, "package_sha256")
    elif scenario == "invalid_why_loaded":
        package["loaded"][0]["why_loaded"] = "伪造的装入理由"
        result["trace_log"]["events"][0]["why_loaded"] = "伪造的装入理由"
        _reseal(package, "package_sha256")
        _reseal(result["trace_log"], "trace_log_sha256")
    elif scenario == "invalid_receipt":
        result["short_receipt"]["required_satisfied"] = 0
        _reseal(result["short_receipt"], "receipt_sha256")
    elif scenario == "invalid_replay":
        result["replay_status"] = "REPLAYABLE_PINNED"
    elif scenario == "invalid_run_sha":
        result["run_sha256"] = "0" * 64
        return request, plan, result
    else:
        raise FixtureError(f"UNKNOWN_RESULT_MUTATION:{scenario}")
    _reseal(result, "run_sha256")
    return request, plan, result


def _expect_invalid(scenario: str) -> None:
    if scenario.startswith("invalid_") and scenario in {
        "invalid_overlap",
        "invalid_unaccounted",
        "invalid_why_loaded",
        "invalid_receipt",
        "invalid_replay",
        "invalid_run_sha",
    }:
        request, plan, result = _mutated_result(scenario)
        core.validate_result(result, request, plan)
        return

    request, outcomes, registry = _build_run("ready_ledger")
    safety_stop = scenario in {
        "invalid_cross_scope",
        "invalid_unauthorized_leak",
        "invalid_corrupted_source",
    }
    if scenario == "invalid_cross_scope":
        need = request["source_needs"][0]
        outcomes[0] = _outcome(
            need,
            basis_mode=request["basis_mode"],
            project_id="PROJECT-OTHER",
        )
    elif scenario == "invalid_duplicate_need":
        request["source_needs"].append(copy.deepcopy(request["source_needs"][0]))
        request = core.seal_request(request)
    elif scenario == "invalid_disconnected_layer":
        need = request["source_needs"][0]
        need["evidence_layer"] = "FORMATION_BASIS"
        need["parent_need_id"] = "NEED-NOT-PRESENT"
        need["source_contract"] = "TRACEABLE_PROVENANCE_SEAL"
        need["source_contract_version"] = "v1"
        need["expansion_trigger"] = "AUDIT_REQUIRED"
        request = core.seal_request(request)
    elif scenario == "invalid_unverified_source":
        registry.pop("LEDGER_READ_TOOL_CONTRACT")
    elif scenario == "invalid_unauthorized_leak":
        need = request["source_needs"][0]
        outcomes[0] = _outcome(
            need,
            basis_mode=request["basis_mode"],
            status="REJECTED",
            reason_code="UNAUTHORIZED",
            material_text="不应泄露的内容",
        )
    elif scenario == "invalid_corrupted_source":
        outcomes[0]["source_document"]["contract"] = "UNAUTHORIZED_BLOB"
    else:
        raise FixtureError(f"UNKNOWN_INVALID_SCENARIO:{scenario}")
    plan = core.prepare_plan(request)
    result = core.compile_result(request, plan, outcomes, registry)
    if safety_stop:
        if result["status"] != "STOPPED":
            raise FixtureError(f"SAFETY_CASE_DID_NOT_STOP:{scenario}")
        result["status"] = "READY"
        _reseal(result, "run_sha256")
        core.validate_result(result, request, plan)


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not isinstance(row, dict) or set(row) != FIXTURE_FIELDS:
            raise FixtureError(f"FIXTURE_FIELDS_INVALID:{line_no}")
        if row["expected_result"] not in EXPECTED_COUNTS:
            raise FixtureError(f"FIXTURE_EXPECTATION_INVALID:{line_no}")
        rows.append(row)
    case_ids = [row["case_id"] for row in rows]
    if len(case_ids) != len(set(case_ids)):
        raise FixtureError("FIXTURE_CASE_ID_DUPLICATE")
    return rows


def validate_fixture_case(case: Mapping[str, str]) -> str:
    expected = case["expected_result"]
    try:
        if expected == "STRUCTURAL_INVALID":
            _expect_invalid(case["scenario"])
            raise FixtureError(f"FIXTURE_EXPECTED_INVALID:{case['case_id']}")
        request, outcomes, registry = _build_run(case["scenario"])
        _validate_schema_instance(request)
        plan = core.prepare_plan(request)
        _validate_schema_instance(plan)
        result = core.compile_result(request, plan, outcomes, registry)
        _validate_schema_instance(result)
        actual = result["status"]
    except core.C9RetrievalError:
        if expected == "STRUCTURAL_INVALID":
            return "STRUCTURAL_INVALID"
        raise
    if actual != expected:
        raise FixtureError(
            f"FIXTURE_RESULT_MISMATCH:{case['case_id']}:{expected}:{actual}"
        )
    return actual


def validate_all_fixtures(path: Path = FIXTURE_PATH) -> dict[str, int]:
    counts = {key: 0 for key in EXPECTED_COUNTS}
    for case in load_fixtures(path):
        counts[validate_fixture_case(case)] += 1
    if counts != EXPECTED_COUNTS:
        raise FixtureError(f"FIXTURE_COUNTS_MISMATCH:{counts}")
    return counts


def main() -> int:
    counts = validate_all_fixtures()
    print(
        json.dumps(
            {
                "contract": "C9_UNIFIED_RETRIEVAL_RUN",
                "version": core.VERSION,
                "status": "PASS",
                "counts": counts,
                "owner_readers_invoked": 0,
                "workspace_writes": 0,
                "network_calls": 0,
                "model_calls": 0,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
