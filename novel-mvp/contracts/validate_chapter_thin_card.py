#!/usr/bin/env python3
"""Validate the CCZ-140 chapter thin-card contract family v1."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, NoReturn

from jsonschema import Draft202012Validator


DIR = Path(__file__).resolve().parent
PRODUCT_ROOT = DIR.parent
SCHEMA_PATH = DIR / "CHAPTER_THIN_CARD.schema.json"
FIXTURE_PATH = DIR / "CHAPTER_THIN_CARD.fixtures.jsonl"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import unified_retrieval_core as c9_core
finally:
    sys.path.pop(0)


STRUCTURAL_VALID = "STRUCTURAL_VALID"
STRUCTURAL_INVALID = "STRUCTURAL_INVALID"
MAX_PAYLOAD_BYTES = 262_144
FIXED_TIME = "2026-09-03T00:00:00Z"
DEFAULT_STORAGE_GENERATION = "STORAGE-GENERATION-0001"
TASK_FACT_NO_MATCH_EMPTY_SCOPE = (
    "current_confirmed_facts_for_selected_chapter_revision"
)
RECIPE_KEYS = {"artifact", "base", "case_id", "expected_result", "mutation"}
REQUIRED_MATERIAL_ROLES = {
    "SOURCE_TEXT",
    "FACT_EXPRESSION",
    "FORMAL_LEDGER_STATE",
    "CHAPTER_TARGET",
    "DERIVED_ARTIFACT",
}
ADMISSION_CHECK_KINDS = {
    "THIN_CARD_INTEGRITY",
    "SCOPE_CURRENT",
    "PERMISSION_CURRENT",
    "FOCUS_CURRENT",
    "RETRIEVAL_TASK_CURRENT",
    "C9_RUN_CURRENT",
    "SOURCE_VERSION_CURRENT",
    "STORAGE_GENERATION_CURRENT",
    "CONTRACT_SUPPORT_CURRENT",
}
BUILD_POLICY = {
    "compiler_version": "chapter-thin-card-compiler-v1",
    "summary_policy_version": "chapter-thin-card-summary-v1",
    "normalization_policy_version": "chapter-thin-card-canonical-json-utf8-v1",
    "byte_limit_policy_version": "chapter-thin-card-byte-limit-v1",
    "max_payload_bytes": MAX_PAYLOAD_BYTES,
}
EXPECTED_COUNTS = {STRUCTURAL_VALID: 18, STRUCTURAL_INVALID: 50}
EXPECTED_ERROR_CODES = {
    "admission_card_ref": "ADMISSION_CARD_REF_MISMATCH",
    "admission_hash": "ADMISSION_RECEIPT_SHA256_MISMATCH",
    "admission_duplicate_check_kind": "ADMISSION_CHECK_KIND_SET_INVALID",
    "admission_current_proof_shape": "ADMISSION_CURRENT_PROOF_SCHEMA_INVALID",
    "admission_mask_leak": "ADMISSION_MASK_LEAK",
    "admission_match_fingerprint": "ADMISSION_MATCH_FINGERPRINT_MISMATCH",
    "admission_missing_check": "SCHEMA_INVALID",
    "admission_wrong_expected_fingerprint": "ADMISSION_EXPECTED_FINGERPRINT_MISMATCH",
    "admission_status": "ADMISSION_STATUS_MISMATCH",
    "byte_count": "PAYLOAD_BYTE_COUNT_MISMATCH",
    "c9_run_ref": "C9_RUN_REF_MISMATCH",
    "c9_scope_mismatch": "C9_SCOPE_MISMATCH",
    "card_hash": "THIN_CARD_SHA256_MISMATCH",
    "character_view_collapsed": "CHARACTER_VIEW_IDENTITY_COLLAPSED",
    "demotion_order": "DEMOTION_ORDER_INVALID",
    "duplicate_version_ref": "VERSION_REF_DUPLICATE",
    "failure_has_card_id": "SCHEMA_INVALID",
    "failure_hash": "BUILD_FAILURE_SHA256_MISMATCH",
    "failure_status": "SCHEMA_INVALID",
    "hard_byte_demotion": "HARD_DEMOTION_FORBIDDEN",
    "input_hash": "INPUT_BASIS_SHA256_MISMATCH",
    "missing_hard_resident": "HARD_LOADED_NOT_RESIDENT",
    "on_demand_content_leak": "SCHEMA_INVALID",
    "on_demand_missing_handle": "SCHEMA_INVALID",
    "on_demand_unknown_need": "ON_DEMAND_SOURCE_INVALID",
    "payload_hash": "COMPILED_PAYLOAD_SHA256_MISMATCH",
    "plan_snapshot_mismatch": "PLAN_SNAPSHOT_MISMATCH",
    "plugin_field": "SCHEMA_INVALID",
    "previous_snapshot_mismatch": "PREVIOUS_SNAPSHOT_MISMATCH",
    "resident_material_changed": "RESIDENT_ITEM_MISMATCH",
    "resident_obligation_changed": "RESIDENT_ITEM_MISMATCH",
    "resident_unknown_need": "RESIDENT_NOT_C9_LOADED",
    "resident_why_changed": "RESIDENT_ITEM_MISMATCH",
    "retrieval_task_ref": "RETRIEVAL_TASK_REF_MISMATCH",
    "scope_projection_mismatch": "SCOPE_PROJECTION_MISMATCH",
    "source_result_unknown_version": "SOURCE_RESULT_VERSION_UNKNOWN",
    "storage_generation_mixed": "STORAGE_GENERATION_MIXED",
    "success_when_c9_stopped": "SUCCESS_CARD_FOR_FAILED_BUILD",
    "success_when_unsupported": "SUCCESS_CARD_FOR_FAILED_BUILD",
    "task_c9_needs_mismatch": "TASK_C9_SOURCE_NEEDS_MISMATCH",
    "task_no_match_source_result_missing": "TASK_NO_MATCH_SOURCE_RESULT_REQUIRED",
    "task_no_match_source_result_mismatch": "TASK_NO_MATCH_SOURCE_RESULT_MISMATCH",
    "task_no_match_version_binding_mismatch": (
        "TASK_NO_MATCH_VERSION_BINDING_MISMATCH"
    ),
    "thin_card_current_field": "SCHEMA_INVALID",
    "unauthorized_disclosed": "SOURCE_RESULT_DISCLOSURE_INVALID",
    "uncommitted_as_committed": "SCHEMA_INVALID",
    "unknown_field": "SCHEMA_INVALID",
    "untracked_disclosed": "SOURCE_RESULT_DISCLOSURE_INVALID",
    "version_manifest_mismatch": "VERSION_MANIFEST_MISMATCH",
    "wrong_contract": "SCHEMA_INVALID",
}


class ThinCardError(ValueError):
    """A thin-card family invariant failed."""


def _fail(code: str) -> NoReturn:
    raise ThinCardError(code)


def _load_module(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, DIR / filename)
    if spec is None or spec.loader is None:
        raise ThinCardError(f"UPSTREAM_VALIDATOR_UNAVAILABLE:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


task_validator = _load_module(
    "validate_chapter_context_retrieval_task.py",
    "ccz140_task_validator",
)
c9_fixture_validator = _load_module(
    "validate_c9_unified_retrieval_run.py",
    "ccz140_c9_fixture_validator",
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ThinCardError(f"JSON_OBJECT_REQUIRED:{path.name}")
    return value


SCHEMA = _load_json(SCHEMA_PATH)
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA)
ADMISSION_CHECK_SCHEMA = {
    "$schema": SCHEMA["$schema"],
    "$ref": "#/$defs/admission_check",
    "$defs": SCHEMA["$defs"],
}
Draft202012Validator.check_schema(ADMISSION_CHECK_SCHEMA)
ADMISSION_CHECK_VALIDATOR = Draft202012Validator(ADMISSION_CHECK_SCHEMA)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _schema_path(error: Any) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "$"


def _validate_schema(value: Any) -> None:
    errors = sorted(
        VALIDATOR.iter_errors(value),
        key=lambda item: (list(item.absolute_path), item.message),
    )
    if errors:
        first = errors[0]
        raise ThinCardError(
            f"SCHEMA_INVALID:{_schema_path(first)}:{first.validator}"
        )


def _unique_map(
    rows: list[dict[str, Any]], key: str, code: str
) -> dict[str, dict[str, Any]]:
    values = [row[key] for row in rows]
    if len(values) != len(set(values)):
        _fail(code)
    return {row[key]: row for row in rows}


def _workpoint(task: dict[str, Any]) -> str:
    scope = task["scope_projection"]
    return f"chapter:{scope['slot_ref']}@{scope['slot_rev']}"


def _c9_scope(task: dict[str, Any]) -> dict[str, Any]:
    scope = task["scope_projection"]
    truth = task["truth_scope_ref"]
    return {
        "author_id": truth["principal_author_id"],
        "project_id": truth["project_id"],
        "task_id": task["retrieval_task_id"],
        "consumer_id": "CHAPTER-THIN-CARD-COMPILER",
        "workpoint_ref": _workpoint(task),
        "story_scope_ref": scope["selected_storyline_ref"],
        "sandbox_ref": None,
        "upstream_card_ref": task["retrieval_task_id"],
    }


def _make_c9_request(
    task: dict[str, Any],
    *,
    scenario: str,
    scope_override: dict[str, Any] | None = None,
    needs_override: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    needs = copy.deepcopy(needs_override or task["c9_source_needs"])
    hard_tokens = sum(
        row["estimated_tokens"]
        for row in needs
        if row["obligation_tier"] == "HARD"
    )
    all_tokens = sum(row["estimated_tokens"] for row in needs)
    budget = hard_tokens if scenario == "c9_omitted" else max(all_tokens + 32, 1)
    actuality_scope = (
        "FUTURE_MATERIAL_EXPLICITLY_IN_SCOPE"
        if any(row["actuality_class"] == "FUTURE_PLAN_OR_PROJECTION" for row in needs)
        else "CURRENT_TRUTH_REQUIRED"
    )
    request = {
        "contract": "C9_RETRIEVAL_REQUEST",
        "version": c9_core.VERSION,
        "scope": copy.deepcopy(scope_override or _c9_scope(task)),
        "basis_mode": "current_at_start",
        "task_actuality_scope": actuality_scope,
        "budget": {
            "limit_tokens": budget,
            "estimator_ref": "chapter-thin-card-fixture-estimator-v1",
        },
        "gap_policy": {
            "policy_ref": "chapter-thin-card-fixture-gap-policy-v1",
            "missing_required_behavior": "WARN_AND_CONTINUE",
        },
        "source_needs": needs,
    }
    return c9_core.seal_request(request)


def _make_c9_outcomes(
    request: dict[str, Any], scenario: str
) -> list[dict[str, Any]]:
    outcomes = [
        c9_fixture_validator._outcome(
            need,
            basis_mode=request["basis_mode"],
        )
        for need in request["source_needs"]
    ]
    fact_index = next(
        (
            index
            for index, need in enumerate(request["source_needs"])
            if need["need_id"].startswith("NEED-FACT-")
        ),
        None,
    )
    optional_index = next(
        (
            index
            for index, need in enumerate(request["source_needs"])
            if need["obligation_tier"] in {"SHOULD", "MAY"}
        ),
        None,
    )
    if scenario in {"legal_empty", "no_match"} and fact_index is not None:
        reason = (
            "VALID_EMPTY_OBJECT"
            if scenario == "legal_empty"
            else "NO_MATCHING_ENTRIES"
        )
        outcomes[fact_index] = c9_fixture_validator._outcome(
            request["source_needs"][fact_index],
            basis_mode=request["basis_mode"],
            status="EMPTY",
            reason_code=reason,
        )
    elif scenario == "directory_only" and optional_index is not None:
        outcomes[optional_index] = c9_fixture_validator._outcome(
            request["source_needs"][optional_index],
            basis_mode=request["basis_mode"],
            status="NOT_ATTEMPTED",
        )
    elif scenario == "byte_demotion" and optional_index is not None:
        outcomes[optional_index] = c9_fixture_validator._outcome(
            request["source_needs"][optional_index],
            basis_mode=request["basis_mode"],
            material_text="可选材料" * 70_000,
        )
    elif scenario == "damaged_failure" and fact_index is not None:
        outcomes[fact_index] = c9_fixture_validator._outcome(
            request["source_needs"][fact_index],
            basis_mode=request["basis_mode"],
            status="ERROR",
            reason_code="SOURCE_CORRUPTED",
        )
    elif scenario == "hard_missing_failure" and fact_index is not None:
        outcomes[fact_index] = c9_fixture_validator._outcome(
            request["source_needs"][fact_index],
            basis_mode=request["basis_mode"],
            status="NOT_ATTEMPTED",
        )
    return outcomes


def _compile_c9(
    task: dict[str, Any],
    scenario: str,
    *,
    scope_override: dict[str, Any] | None = None,
    needs_override: list[dict[str, Any]] | None = None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    request = _make_c9_request(
        task,
        scenario=scenario,
        scope_override=scope_override,
        needs_override=needs_override,
    )
    plan = c9_core.prepare_plan(request)
    outcomes = _make_c9_outcomes(request, scenario)
    registry = c9_fixture_validator._registry()
    result = c9_core.compile_result(request, plan, outcomes, registry)
    return request, plan, result, outcomes, registry


def _c9_run_ref(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract": result["contract"],
        "version": result["version"],
        "request_sha256": result["request_sha256"],
        "plan_sha256": result["plan_sha256"],
        "package_sha256": result["material_package"]["package_sha256"],
        "receipt_sha256": result["short_receipt"]["receipt_sha256"],
        "trace_log_sha256": result["trace_log"]["trace_log_sha256"],
        "run_sha256": result["run_sha256"],
    }


def _task_ref(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract": task["contract"],
        "version": task["version"],
        "retrieval_task_id": task["retrieval_task_id"],
        "task_basis_sha256": task["task_basis_sha256"],
    }


def _all_c9_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    package = result["material_package"]
    return package["loaded"] + package["omitted"] + package["outstanding"]


def _material_role(need: dict[str, Any]) -> str:
    if need["evidence_layer"] == "ORIGINAL_EVIDENCE":
        return "SOURCE_TEXT"
    if need["source_contract"] == "LEDGER_READ_TOOL_CONTRACT":
        return "FACT_EXPRESSION"
    if need["source_contract"] == "CHAPTER_SETTLEMENT_SEAL":
        return "FORMAL_LEDGER_STATE"
    if need["source_contract"] == "CHAPTER_LAYERED_SUMMARY":
        return "DERIVED_ARTIFACT"
    return "FACT_EXPRESSION"


def _role_actuality(role: str) -> str:
    return {
        "SOURCE_TEXT": "OUTER_EVIDENCE",
        "FACT_EXPRESSION": "FACT_EXPRESSION",
        "FORMAL_LEDGER_STATE": "COMMITTED_TRUTH",
        "CHAPTER_TARGET": "PLANNED_TARGET",
        "DERIVED_ARTIFACT": "DERIVED_ARTIFACT",
    }[role]


def _owner_version(
    version_ref: str,
    role: str,
    *,
    actuality: str | None = None,
    storage_generation: str = DEFAULT_STORAGE_GENERATION,
) -> dict[str, Any]:
    object_ref = f"OWNER-OBJECT-{version_ref}"
    revision_ref = f"REVISION-{version_ref}"
    return {
        "version_ref": version_ref,
        "material_role": role,
        "binding_kind": "OWNER_PROOF",
        "binding_ref": f"OWNER-RECEIPT-{version_ref}",
        "source_contract": {
            "SOURCE_TEXT": "LEDGER_READ_TOOL_CONTRACT",
            "FACT_EXPRESSION": "LEDGER_READ_TOOL_CONTRACT",
            "FORMAL_LEDGER_STATE": "LEDGER_READ_TOOL_CONTRACT",
            "CHAPTER_TARGET": "CHAPTER_SCOPE_CONFIRMATION",
            "DERIVED_ARTIFACT": "CHAPTER_LAYERED_SUMMARY",
        }[role],
        "source_contract_version": {
            "SOURCE_TEXT": "ledger-read-tool-contract-v1",
            "FACT_EXPRESSION": "ledger-read-tool-contract-v1",
            "FORMAL_LEDGER_STATE": "ledger-read-tool-contract-v1",
            "CHAPTER_TARGET": "v1",
            "DERIVED_ARTIFACT": "v1",
        }[role],
        "object_ref": object_ref,
        "revision_ref": revision_ref,
        "content_sha256": sha256_json({"object_ref": object_ref, "revision": revision_ref}),
        "basis_mode": "current_at_start",
        "basis_sha256": sha256_json({"basis": version_ref}),
        "storage_generation": storage_generation,
        "actuality_class": actuality or _role_actuality(role),
    }


def _task_no_match_evidence(
    task_bundle: dict[str, Any],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    task = task_bundle["task"]
    response_map = {
        row["request_id"]: row for row in task_bundle["ledger_responses"]
    }
    evidence: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for source in task["source_manifest"]:
        if not (
            source["source_contract"] == "LEDGER_READ_TOOL_CONTRACT"
            and source["access_state"] == "OPENED_EMPTY"
            and source["source_status"] == "EMPTY"
            and source["reason_code"] == "NO_MATCHING_ENTRIES"
        ):
            continue
        response = response_map.get(source["object_ref"])
        if response is None or not (
            response["contract"] == "LEDGER_READ_RESPONSE"
            and response["version"] == source["source_contract_version"]
            and response["request_id"] == source["object_ref"]
            and response["tool"] == "get_chapter_evidence_slice"
            and response["status"] == source["source_status"]
            and response["reason_code"] == source["reason_code"]
            and response["basis_mode"] == source["basis_mode"]
            and response["receipt"]["tool_contract_version"]
            == source["source_contract_version"]
            and response["receipt"]["basis_sha256"] == source["basis_sha256"]
            and sha256_json(response) == source["source_document_sha256"]
            and response["data"] is None
            and response["empty_scope"] == TASK_FACT_NO_MATCH_EMPTY_SCOPE
            and response["limits"]["business_items"] == 0
            and response["limits"]["truncated"] is False
        ):
            _fail("TASK_NO_MATCH_VERSION_BINDING_MISMATCH")
        evidence.append((source, response))
    return sorted(evidence, key=lambda pair: pair[0]["source_id"])


def _task_no_match_generation(
    evidence: list[tuple[dict[str, Any], dict[str, Any]]],
) -> str:
    generations = {
        response["receipt"]["storage_generation"] for _, response in evidence
    }
    if len(generations) > 1:
        _fail("TASK_SOURCE_RESULT_GENERATION_MIXED")
    return next(iter(generations), DEFAULT_STORAGE_GENERATION)


def _task_no_match_version(
    source: dict[str, Any],
    response: dict[str, Any],
    storage_generation: str,
) -> dict[str, Any]:
    document_sha256 = source["source_document_sha256"]
    return {
        "version_ref": (
            f"VERSION-TASK-SOURCE:{source['source_id']}@{document_sha256}"
        ),
        "material_role": "FACT_EXPRESSION",
        "binding_kind": "TASK_SOURCE_RESULT",
        "binding_ref": source["source_id"],
        "source_contract": source["source_contract"],
        "source_contract_version": source["source_contract_version"],
        "object_ref": response["request_id"],
        "revision_ref": (
            f"READ-RESULT:{response['request_id']}@{document_sha256}"
        ),
        "content_sha256": document_sha256,
        "basis_mode": source["basis_mode"],
        "basis_sha256": source["basis_sha256"],
        "storage_generation": storage_generation,
        "actuality_class": "FACT_EXPRESSION",
    }


def _version_proofs(
    task_bundle: dict[str, Any],
    request: dict[str, Any],
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    task_no_match_evidence = _task_no_match_evidence(task_bundle)
    storage_generation = _task_no_match_generation(task_no_match_evidence)
    need_map = {row["need_id"]: row for row in request["source_needs"]}
    proofs: list[dict[str, Any]] = []
    for item in _all_c9_items(result):
        validation = item.get("source_validation")
        binding = validation.get("source_binding") if validation else None
        if binding is None:
            continue
        need = need_map[item["need_id"]]
        role = _material_role(need)
        proofs.append(
            {
                "version_ref": f"VERSION-{need['need_id']}",
                "material_role": role,
                "binding_kind": "C9_NEED",
                "binding_ref": need["need_id"],
                "source_contract": validation["source_contract"],
                "source_contract_version": validation["source_contract_version"],
                "object_ref": binding["canonical_object_ref"],
                "revision_ref": binding["source_revision_ref"],
                "content_sha256": binding["source_object_sha256"],
                "basis_mode": binding["basis_mode"],
                "basis_sha256": binding["basis_sha256"],
                "storage_generation": storage_generation,
                "actuality_class": _role_actuality(role),
            }
        )

    proofs.extend(
        _task_no_match_version(source, response, storage_generation)
        for source, response in task_no_match_evidence
    )
    proofs.extend(
        [
            _owner_version(
                "VERSION-CHAR-CURRENT",
                "FORMAL_LEDGER_STATE",
                storage_generation=storage_generation,
            ),
            _owner_version(
                "VERSION-CHAR-STORY",
                "FORMAL_LEDGER_STATE",
                storage_generation=storage_generation,
            ),
            _owner_version(
                "VERSION-CHAPTER-TARGET",
                "CHAPTER_TARGET",
                storage_generation=storage_generation,
            ),
            _owner_version(
                "VERSION-WORKSPACE-DELTA",
                "CHAPTER_TARGET",
                actuality="UNCOMMITTED_WORKSPACE",
                storage_generation=storage_generation,
            ),
        ]
    )
    role_fallbacks = {
        "SOURCE_TEXT": "VERSION-SOURCE-TEXT",
        "FACT_EXPRESSION": "VERSION-FACT-EXPRESSION",
        "FORMAL_LEDGER_STATE": "VERSION-FORMAL-LEDGER",
        "CHAPTER_TARGET": "VERSION-CHAPTER-TARGET-FALLBACK",
        "DERIVED_ARTIFACT": "VERSION-DERIVED-ARTIFACT",
    }
    existing_roles = {row["material_role"] for row in proofs}
    for role in sorted(REQUIRED_MATERIAL_ROLES - existing_roles):
        proofs.append(
            _owner_version(
                role_fallbacks[role],
                role,
                storage_generation=storage_generation,
            )
        )
    return sorted(proofs, key=lambda row: row["version_ref"])


def _raw_outcome_map(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["need_id"]: row for row in bundle["c9_outcomes"]}


def _source_state(outcome: dict[str, Any]) -> tuple[str, str]:
    status = outcome["source_status"]
    reason = outcome["reason_code"]
    if status == "OK":
        return "PRESENT", "CONTENT_AVAILABLE"
    if status == "EMPTY" and reason == "NO_MATCHING_ENTRIES":
        return "NO_MATCH", reason
    if status == "EMPTY":
        return "EMPTY", reason or "VALID_EMPTY_OBJECT"
    if reason == "UNTRACKED":
        return "UNTRACKED", reason
    if reason == "UNSUPPORTED_VERSION":
        return "UNSUPPORTED_VERSION", reason
    if status == "NOT_ATTEMPTED":
        return "UNAVAILABLE", reason or "OWNER_RUNTIME_NOT_AVAILABLE"
    if reason == "UNAUTHORIZED":
        return "UNAUTHORIZED", reason
    if reason in {"SOURCE_CORRUPTED", "SHA_MISMATCH", "INTERNAL_ERROR"}:
        return "DAMAGED", reason
    if status in {"ERROR", "REJECTED"}:
        return "DAMAGED", reason or "SOURCE_DAMAGED"
    return "UNAVAILABLE", reason or status


def _source_results(
    task_bundle: dict[str, Any],
    request: dict[str, Any],
    outcomes: list[dict[str, Any]],
    proofs: list[dict[str, Any]],
    *,
    task_has_optional_gap: bool,
) -> list[dict[str, Any]]:
    proof_by_need = {
        row["binding_ref"]: row
        for row in proofs
        if row["binding_kind"] == "C9_NEED"
    }
    outcome_map = {row["need_id"]: row for row in outcomes}
    result_rows: list[dict[str, Any]] = []
    seen_versions: set[str] = set()
    need_map = {row["need_id"]: row for row in request["source_needs"]}
    for need_id, need in need_map.items():
        proof = proof_by_need.get(need_id)
        state, reason = _source_state(outcome_map[need_id])
        if proof is None:
            result_id = f"RESULT-{need_id}"
            disclosure = (
                {"mode": "MASKED"}
                if state == "UNAUTHORIZED"
                else {"mode": "NOT_AVAILABLE"}
            )
        else:
            version_ref = proof["version_ref"]
            seen_versions.add(version_ref)
            result_id = f"RESULT-{version_ref}"
            disclosure = (
                {"mode": "MASKED"}
                if state == "UNAUTHORIZED"
                else {"mode": "DISCLOSED", "version_ref": version_ref}
            )
        result_rows.append(
            {
                "result_id": result_id,
                "material_role": _material_role(need),
                "state": state,
                "reason_code": reason,
                "identity_disclosure": disclosure,
            }
        )
    task_proof_by_source = {
        row["binding_ref"]: row
        for row in proofs
        if row["binding_kind"] == "TASK_SOURCE_RESULT"
    }
    for source, _ in _task_no_match_evidence(task_bundle):
        proof = task_proof_by_source.get(source["source_id"])
        if proof is None:
            _fail("TASK_NO_MATCH_VERSION_BINDING_MISMATCH")
        version_ref = proof["version_ref"]
        seen_versions.add(version_ref)
        result_rows.append(
            {
                "result_id": f"RESULT-{version_ref}",
                "material_role": "FACT_EXPRESSION",
                "state": "NO_MATCH",
                "reason_code": "NO_MATCHING_ENTRIES",
                "identity_disclosure": {
                    "mode": "DISCLOSED",
                    "version_ref": version_ref,
                },
            }
        )
    for proof in proofs:
        if proof["version_ref"] in seen_versions:
            continue
        result_rows.append(
            {
                "result_id": f"RESULT-{proof['version_ref']}",
                "material_role": proof["material_role"],
                "state": "PRESENT",
                "reason_code": "CONTENT_AVAILABLE",
                "identity_disclosure": {
                    "mode": "DISCLOSED",
                    "version_ref": proof["version_ref"],
                },
            }
        )
    if task_has_optional_gap:
        result_rows.append(
            {
                "result_id": "RESULT-OPTIONAL-GAP",
                "material_role": "FORMAL_LEDGER_STATE",
                "state": "UNAVAILABLE",
                "reason_code": "OPTIONAL_SOURCES_UNAVAILABLE",
                "identity_disclosure": {"mode": "NOT_AVAILABLE"},
            }
        )
    return sorted(result_rows, key=lambda row: row["result_id"])


def _proof_for_need(
    proofs: list[dict[str, Any]], need_id: str
) -> dict[str, Any]:
    proof = next(
        (
            row
            for row in proofs
            if row["binding_kind"] == "C9_NEED" and row["binding_ref"] == need_id
        ),
        None,
    )
    if proof is None:
        _fail(f"C9_NEED_VERSION_PROOF_REQUIRED:{need_id}")
    return proof


def _source_result_ref_for_need(
    source_results: list[dict[str, Any]],
    proofs: list[dict[str, Any]],
    need_id: str,
) -> str:
    proof = next(
        (
            row
            for row in proofs
            if row["binding_kind"] == "C9_NEED" and row["binding_ref"] == need_id
        ),
        None,
    )
    result_id = (
        f"RESULT-{proof['version_ref']}" if proof else f"RESULT-{need_id}"
    )
    if not any(row["result_id"] == result_id for row in source_results):
        _fail(f"SOURCE_RESULT_REQUIRED:{need_id}")
    return result_id


def _relation_refs(task: dict[str, Any], need_id: str) -> list[str]:
    previous = task["previous_chapter_handoff"]
    if previous and previous["c9_need_id"] == need_id:
        return copy.deepcopy(previous["handoff_scope_refs"])
    for fact in task["selected_fact_refs"]:
        if fact["c9_need_id"] == need_id:
            return copy.deepcopy(fact["relation_scope_refs"])
    for box in task["box_directory"]:
        if need_id in box["c9_need_ids"]:
            return copy.deepcopy(box["relation_scope_refs"])
    return [task["scope_projection"]["selected_storyline_ref"]]


def _display_summary(
    task: dict[str, Any], item: dict[str, Any]
) -> tuple[str, str]:
    need_id = item["need_id"]
    for fact in task["selected_fact_refs"]:
        if fact["c9_need_id"] == need_id:
            return fact["fact_summary"], "TASK_FACT_SUMMARY"
    previous = task["previous_chapter_handoff"]
    if previous and previous["c9_need_id"] == need_id:
        return previous["handoff_summary"], "PREVIOUS_HANDOFF_SUMMARY"
    return item["why_loaded"], "C9_WHY_LOADED"


def _recall(item: dict[str, Any]) -> dict[str, Any]:
    if item["recall_disposition"] == "RETRIEVABLE":
        return {
            "disposition": "RETRIEVABLE",
            "handle": item["recall_handle"],
        }
    return {"disposition": "NOT_RETRIEVABLE"}


def _resident_item(
    task: dict[str, Any],
    item: dict[str, Any],
    proofs: list[dict[str, Any]],
    source_results: list[dict[str, Any]],
) -> dict[str, Any]:
    proof = _proof_for_need(proofs, item["need_id"])
    summary, summary_source = _display_summary(task, item)
    return {
        "need_id": item["need_id"],
        "object_ref": item["object_ref"],
        "evidence_layer": item["evidence_layer"],
        "parent_need_id": item["parent_need_id"],
        "obligation_tier": item["obligation_tier"],
        "material_text": item["material_text"],
        "material_sha256": item["material_sha256"],
        "why_loaded": item["why_loaded"],
        "source_version_ref": proof["version_ref"],
        "source_result_ref": _source_result_ref_for_need(
            source_results,
            proofs,
            item["need_id"],
        ),
        "relation_scope_refs": _relation_refs(task, item["need_id"]),
        "display_summary": summary,
        "display_summary_source": summary_source,
        "consumer_use_tags": [
            "AUTHOR_UI",
            "PRODUCT_MODULE",
            "INTERNAL_AUDIT",
        ],
        "recall": _recall(item),
    }


def _box_for_need(task: dict[str, Any], need_id: str) -> str | None:
    for box in task["box_directory"]:
        if need_id in box["c9_need_ids"]:
            return box["box_id"]
    return None


def _on_demand_item(
    task: dict[str, Any],
    item: dict[str, Any],
    source_results: list[dict[str, Any]],
    proofs: list[dict[str, Any]],
    *,
    reason_code: str,
) -> dict[str, Any]:
    return {
        "entry_id": f"ON-DEMAND-{item['need_id']}",
        "need_id": item["need_id"],
        "box_id": _box_for_need(task, item["need_id"]),
        "object_ref": item["object_ref"],
        "evidence_layer": item["evidence_layer"],
        "parent_need_id": item["parent_need_id"],
        "obligation_tier": item["obligation_tier"],
        "reason_code": reason_code,
        "recall_handle": item["recall_handle"],
        "relation_scope_refs": _relation_refs(task, item["need_id"]),
        "source_result_ref": _source_result_ref_for_need(
            source_results,
            proofs,
            item["need_id"],
        ),
    }


def _previous_snapshot(task: dict[str, Any]) -> dict[str, Any] | None:
    previous = task["previous_chapter_handoff"]
    if previous is None:
        return None
    return {
        "source_slot_ref": previous["source_slot_ref"],
        "settlement_sha256": previous["settlement_sha256"],
        "handoff_summary": previous["handoff_summary"],
        "actuality_class": "COMMITTED_TRUTH",
    }


def _gap_summary(
    task: dict[str, Any],
    result: dict[str, Any],
    source_results: list[dict[str, Any]],
) -> dict[str, Any]:
    optional: list[str] = []
    if task["status"] == "READY_WITH_GAPS" and task["reason_code"]:
        optional.append(task["reason_code"])
    package = result["material_package"]
    for item in package["omitted"]:
        if item["obligation_tier"] in {"SHOULD", "MAY"}:
            optional.append(item["reason"])
    for item in package["outstanding"]:
        if not item["fatal"] and item["obligation_tier"] in {"SHOULD", "MAY"}:
            optional.append(item["reason_code"])
    return {
        "hard_gap_codes": [],
        "optional_gap_codes": sorted(set(optional)),
        "masked_access": any(
            row["state"] == "UNAUTHORIZED" for row in source_results
        ),
    }


def _input_basis(
    task: dict[str, Any],
    result: dict[str, Any],
    proofs: list[dict[str, Any]],
) -> str:
    return sha256_json(
        {
            "retrieval_task_ref": _task_ref(task),
            "c9_run_ref": _c9_run_ref(result),
            "version_manifest": proofs,
            "build_policy": BUILD_POLICY,
        }
    )


def _build_failure(
    task: dict[str, Any],
    result: dict[str, Any],
    proofs: list[dict[str, Any]],
    *,
    stage: str,
    reason_code: str,
) -> dict[str, Any]:
    retry, recompile = {
        "UNSUPPORTED_VERSION": ("RECOMPILE_AFTER_RULE_SUPPORT", True),
        "SOURCE_DAMAGED": ("RETRY_AFTER_SOURCE_CHANGE", True),
        "SOURCE_CORRUPTED": ("RETRY_AFTER_SOURCE_CHANGE", True),
        "REQUIRED_SOURCE_UNAVAILABLE": ("RETRY_AFTER_SOURCE_CHANGE", True),
        "REQUIRED_SOURCE_UNTRACKED": ("RETRY_AFTER_SOURCE_CHANGE", True),
        "REQUIRED_RESIDENT_CONTENT_TOO_LARGE": ("REDUCE_REQUIRED_INPUT", True),
    }.get(reason_code, ("NOT_RETRYABLE_WITH_CURRENT_SCOPE", False))
    failure = {
        "contract": "CHAPTER_THIN_CARD_BUILD_FAILURE",
        "version": "v1",
        "build_failure_id": "THIN-CARD-BUILD-FAILURE-0001",
        "truth_scope_ref": copy.deepcopy(task["truth_scope_ref"]),
        "workpoint_ref": _workpoint(task),
        "status": "STOPPED",
        "failure_stage": stage,
        "reason_code": reason_code,
        "identity_disclosure": {
            "mode": "DISCLOSED",
            "version_ref": task["retrieval_task_id"],
        },
        "retry_disposition": retry,
        "recompile_required": recompile,
        "input_basis_sha256": _input_basis(task, result, proofs),
    }
    failure["build_failure_sha256"] = sha256_json(failure)
    return failure


def _build_card_or_failure(bundle: dict[str, Any]) -> dict[str, Any]:
    task = bundle["task_bundle"]["task"]
    result = bundle["c9_result"]
    proofs = copy.deepcopy(bundle["version_proofs"])
    scenario = bundle["scenario"]

    if task["status"] == "STOPPED":
        return _build_failure(
            task,
            result,
            proofs,
            stage="TASK",
            reason_code=task["reason_code"] or "TASK_STOPPED",
        )
    if result["status"] == "STOPPED":
        reasons = [
            row["reason_code"]
            for row in result["material_package"]["outstanding"]
            if row["reason_code"]
        ]
        return _build_failure(
            task,
            result,
            proofs,
            stage="C9",
            reason_code=reasons[0] if reasons else "C9_STOPPED",
        )
    if scenario == "unsupported_failure":
        return _build_failure(
            task,
            result,
            proofs,
            stage="SOURCE",
            reason_code="UNSUPPORTED_VERSION",
        )

    source_results = _source_results(
        bundle["task_bundle"],
        bundle["c9_request"],
        bundle["c9_outcomes"],
        proofs,
        task_has_optional_gap=task["status"] == "READY_WITH_GAPS",
    )
    outcomes_by_need = _raw_outcome_map(bundle)
    for need in bundle["c9_request"]["source_needs"]:
        if need["obligation_tier"] != "HARD":
            continue
        state, _ = _source_state(outcomes_by_need[need["need_id"]])
        if state in {"PRESENT", "EMPTY", "NO_MATCH"}:
            continue
        reason_code = {
            "UNTRACKED": "REQUIRED_SOURCE_UNTRACKED",
            "UNAVAILABLE": "REQUIRED_SOURCE_UNAVAILABLE",
            "UNAUTHORIZED": "UNAUTHORIZED",
            "UNSUPPORTED_VERSION": "UNSUPPORTED_VERSION",
            "DAMAGED": "SOURCE_DAMAGED",
        }[state]
        return _build_failure(
            task,
            result,
            proofs,
            stage="SOURCE",
            reason_code=reason_code,
        )
    resident = [
        _resident_item(task, item, proofs, source_results)
        for item in result["material_package"]["loaded"]
    ]
    on_demand: list[dict[str, Any]] = []
    for item in (
        result["material_package"]["omitted"]
        + result["material_package"]["outstanding"]
    ):
        if (
            item["obligation_tier"] not in {"SHOULD", "MAY"}
            or item["recall_disposition"] != "RETRIEVABLE"
            or not item["recall_handle"]
        ):
            continue
        if item.get("fatal", False):
            continue
        reason = item.get("reason") or item.get("reason_code") or "NOT_RESIDENT"
        on_demand.append(
            _on_demand_item(
                task,
                item,
                source_results,
                proofs,
                reason_code=reason,
            )
        )

    scope = task["scope_projection"]
    payload = {
        "character_views": [
            {
                "character_ref": scope["viewpoint_character_ref"],
                "character_current_definition": {
                    "source_version_ref": "VERSION-CHAR-CURRENT",
                    "time_anchor_ref": "TIME-BUILD-CURRENT",
                },
                "character_story_time_slice": {
                    "source_version_ref": "VERSION-CHAR-STORY",
                    "time_anchor_ref": f"TIME-{scope['slot_ref']}",
                },
            }
        ],
        "current_chapter_plan_snapshot": {
            "slot_ref": scope["slot_ref"],
            "slot_rev": scope["slot_rev"],
            "source_plan_version": scope["source_plan_version"],
            "source_plan_sha256": scope["source_plan_sha256"],
            "actuality_class": "PLANNED_TARGET",
        },
        "previous_chapter_committed_snapshot": _previous_snapshot(task),
        "uncommitted_workspace_delta_refs": [
            {
                "object_ref": "WORKSPACE-DELTA-0001",
                "source_version_ref": "VERSION-WORKSPACE-DELTA",
                "actuality_class": "UNCOMMITTED_WORKSPACE",
            }
        ],
        "version_manifest": proofs,
        "source_results": source_results,
        "resident_layer": resident,
        "on_demand_layer": on_demand,
        "gap_summary": _gap_summary(task, result, source_results),
    }

    demotions: list[dict[str, Any]] = []
    for tier in ("MAY", "SHOULD"):
        for item in list(reversed(payload["resident_layer"])):
            if len(canonical_bytes(payload)) <= MAX_PAYLOAD_BYTES:
                break
            if item["obligation_tier"] != tier:
                continue
            recall = item["recall"]
            if recall["disposition"] != "RETRIEVABLE":
                continue
            payload["resident_layer"].remove(item)
            payload["on_demand_layer"].append(
                {
                    "entry_id": f"ON-DEMAND-{item['need_id']}",
                    "need_id": item["need_id"],
                    "box_id": _box_for_need(task, item["need_id"]),
                    "object_ref": item["object_ref"],
                    "evidence_layer": item["evidence_layer"],
                    "parent_need_id": item["parent_need_id"],
                    "obligation_tier": item["obligation_tier"],
                    "reason_code": "THIN_CARD_BYTE_LIMIT",
                    "recall_handle": recall["handle"],
                    "relation_scope_refs": item["relation_scope_refs"],
                    "source_result_ref": item["source_result_ref"],
                }
            )
            demotions.append(
                {
                    "need_id": item["need_id"],
                    "from_layer": "RESIDENT",
                    "to_layer": "ON_DEMAND",
                    "reason_code": "THIN_CARD_BYTE_LIMIT",
                }
            )
    payload_bytes = len(canonical_bytes(payload))
    if payload_bytes > MAX_PAYLOAD_BYTES:
        return _build_failure(
            task,
            result,
            proofs,
            stage="SIZE",
            reason_code="REQUIRED_RESIDENT_CONTENT_TOO_LARGE",
        )

    card = {
        "contract": "CHAPTER_THIN_CARD",
        "version": "v1",
        "thin_card_id": "THIN-CARD-0001",
        "truth_scope_ref": copy.deepcopy(task["truth_scope_ref"]),
        "workpoint_ref": _workpoint(task),
        "compiled_at": FIXED_TIME,
        "retrieval_task_ref": _task_ref(task),
        "c9_run_ref": _c9_run_ref(result),
        "scope_projection": copy.deepcopy(scope),
        "build_policy": copy.deepcopy(BUILD_POLICY),
        "compiled_payload": payload,
        "input_basis_sha256": _input_basis(task, result, proofs),
        "compiled_payload_sha256": sha256_json(payload),
        "size_receipt": {
            "normalized_utf8_bytes": payload_bytes,
            "max_payload_bytes": MAX_PAYLOAD_BYTES,
            "demotions": demotions,
        },
    }
    card["thin_card_sha256"] = sha256_json(card)
    return card


def _disclosed_check(
    check_id: str,
    check_kind: str,
    subject_ref: str,
    fingerprint: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "check_kind": check_kind,
        "observed_state": "MATCH",
        "disclosure": {
            "mode": "DISCLOSED",
            "subject_ref": subject_ref,
            "expected_sha256": fingerprint,
            "observed_sha256": fingerprint,
        },
    }


def _current_proofs(card: dict[str, Any], scenario: str) -> list[dict[str, Any]]:
    payload = card["compiled_payload"]
    scope = card["scope_projection"]
    generations = sorted(
        {row["storage_generation"] for row in payload["version_manifest"]}
    )
    checks = [
        _disclosed_check(
            "CHECK-01-CARD",
            "THIN_CARD_INTEGRITY",
            card["thin_card_id"],
            card["thin_card_sha256"],
        ),
        _disclosed_check(
            "CHECK-02-SCOPE",
            "SCOPE_CURRENT",
            scope["scope_id"],
            scope["scope_basis_sha256"],
        ),
        _disclosed_check(
            "CHECK-03-PERMISSION",
            "PERMISSION_CURRENT",
            "PERMISSION-SNAPSHOT-0001",
            scope["permission_snapshot_sha256"],
        ),
        _disclosed_check(
            "CHECK-04-FOCUS",
            "FOCUS_CURRENT",
            "FOCUS-SNAPSHOT-0001",
            scope["effective_focus_sha256"],
        ),
        _disclosed_check(
            "CHECK-05-TASK",
            "RETRIEVAL_TASK_CURRENT",
            card["retrieval_task_ref"]["retrieval_task_id"],
            card["retrieval_task_ref"]["task_basis_sha256"],
        ),
        _disclosed_check(
            "CHECK-06-C9",
            "C9_RUN_CURRENT",
            "C9-RUN-0001",
            card["c9_run_ref"]["run_sha256"],
        ),
        _disclosed_check(
            "CHECK-07-SOURCES",
            "SOURCE_VERSION_CURRENT",
            "SOURCE-VERSION-MANIFEST-0001",
            sha256_json(payload["version_manifest"]),
        ),
        _disclosed_check(
            "CHECK-08-STORAGE",
            "STORAGE_GENERATION_CURRENT",
            generations[0],
            sha256_json(generations),
        ),
        _disclosed_check(
            "CHECK-09-CONTRACTS",
            "CONTRACT_SUPPORT_CURRENT",
            "THIN-CARD-CONTRACT-SUPPORT-0001",
            sha256_json(card["build_policy"]),
        ),
    ]
    if scenario == "admission_stale":
        checks[6]["observed_state"] = "ADVANCED"
        checks[6]["disclosure"]["observed_sha256"] = sha256_json(
            {"advanced": True}
        )
    elif scenario == "admission_revoked":
        checks[2]["observed_state"] = "REVOKED"
        checks[2]["disclosure"] = {"mode": "MASKED"}
    return checks


def _expected_admission_fingerprints(
    card: dict[str, Any],
) -> dict[str, tuple[str, str]]:
    payload = card["compiled_payload"]
    scope = card["scope_projection"]
    generations = sorted(
        {row["storage_generation"] for row in payload["version_manifest"]}
    )
    return {
        "THIN_CARD_INTEGRITY": (
            card["thin_card_id"],
            card["thin_card_sha256"],
        ),
        "SCOPE_CURRENT": (scope["scope_id"], scope["scope_basis_sha256"]),
        "PERMISSION_CURRENT": (
            "PERMISSION-SNAPSHOT-0001",
            scope["permission_snapshot_sha256"],
        ),
        "FOCUS_CURRENT": (
            "FOCUS-SNAPSHOT-0001",
            scope["effective_focus_sha256"],
        ),
        "RETRIEVAL_TASK_CURRENT": (
            card["retrieval_task_ref"]["retrieval_task_id"],
            card["retrieval_task_ref"]["task_basis_sha256"],
        ),
        "C9_RUN_CURRENT": ("C9-RUN-0001", card["c9_run_ref"]["run_sha256"]),
        "SOURCE_VERSION_CURRENT": (
            "SOURCE-VERSION-MANIFEST-0001",
            sha256_json(payload["version_manifest"]),
        ),
        "STORAGE_GENERATION_CURRENT": (
            generations[0],
            sha256_json(generations),
        ),
        "CONTRACT_SUPPORT_CURRENT": (
            "THIN-CARD-CONTRACT-SUPPORT-0001",
            sha256_json(card["build_policy"]),
        ),
    }


def _validate_current_proofs(
    card: dict[str, Any], checks: list[dict[str, Any]]
) -> None:
    for index, check in enumerate(checks):
        errors = sorted(
            ADMISSION_CHECK_VALIDATOR.iter_errors(check),
            key=lambda item: (list(item.absolute_path), item.message),
        )
        if errors:
            first = errors[0]
            raise ThinCardError(
                "ADMISSION_CURRENT_PROOF_SCHEMA_INVALID:"
                f"{index}:{_schema_path(first)}:{first.validator}"
            )
    kinds = [row["check_kind"] for row in checks]
    if len(kinds) != len(ADMISSION_CHECK_KINDS) or set(kinds) != (
        ADMISSION_CHECK_KINDS
    ):
        _fail("ADMISSION_CHECK_KIND_SET_INVALID")
    expected = _expected_admission_fingerprints(card)
    for check in checks:
        state = check["observed_state"]
        disclosure = check["disclosure"]
        mode = disclosure["mode"]
        if state in {"REVOKED", "UNAUTHORIZED"}:
            if mode != "MASKED":
                _fail("ADMISSION_MASK_LEAK")
            continue
        if state == "UNAVAILABLE":
            if mode != "NOT_AVAILABLE":
                _fail("ADMISSION_UNAVAILABLE_DISCLOSURE_INVALID")
            continue
        if mode != "DISCLOSED":
            _fail("ADMISSION_DISCLOSURE_REQUIRED")
        subject_ref, expected_sha = expected[check["check_kind"]]
        if (
            disclosure["subject_ref"] != subject_ref
            or disclosure["expected_sha256"] != expected_sha
        ):
            _fail("ADMISSION_EXPECTED_FINGERPRINT_MISMATCH")
        if state == "MATCH" and disclosure["observed_sha256"] != expected_sha:
            _fail("ADMISSION_MATCH_FINGERPRINT_MISMATCH")
        if state == "ADVANCED" and disclosure["observed_sha256"] == expected_sha:
            _fail("ADMISSION_ADVANCED_FINGERPRINT_MISMATCH")


def _admission_reason(state: str) -> str:
    return {
        "ADVANCED": "SOURCE_ADVANCED",
        "REVOKED": "PERMISSION_REVOKED",
        "EXPIRED": "FOCUS_EXPIRED",
        "UNAVAILABLE": "CURRENT_CHECK_UNAVAILABLE",
        "UNAUTHORIZED": "UNAUTHORIZED",
        "UNSUPPORTED": "UNSUPPORTED_VERSION",
        "DAMAGED": "SOURCE_DAMAGED",
    }[state]


def _build_admission(
    card: dict[str, Any], checks: list[dict[str, Any]]
) -> dict[str, Any]:
    failing_states = [
        row["observed_state"] for row in checks if row["observed_state"] != "MATCH"
    ]
    reasons = [_admission_reason(state) for state in failing_states]
    if failing_states:
        status = "STOPPED"
    elif card["compiled_payload"]["gap_summary"]["optional_gap_codes"]:
        status = "ADMITTED_WITH_GAPS"
        reasons = ["OPTIONAL_GAPS_PRESENT"]
    else:
        status = "ADMITTED"
    receipt = {
        "contract": "CHAPTER_THIN_CARD_ADMISSION_RECEIPT",
        "version": "v1",
        "admission_receipt_id": "THIN-CARD-ADMISSION-0001",
        "thin_card_ref": {
            "thin_card_id": card["thin_card_id"],
            "thin_card_sha256": card["thin_card_sha256"],
        },
        "checked_at": FIXED_TIME,
        "consumer_id": "CONSUMER-WORK-CARD-0001",
        "checks": copy.deepcopy(checks),
        "status": status,
        "reason_codes": reasons,
        "recompile_required": any(
            state in {"ADVANCED", "UNSUPPORTED", "DAMAGED"}
            for state in failing_states
        ),
    }
    receipt["admission_receipt_sha256"] = sha256_json(receipt)
    return receipt


def _task_base_for_scenario(scenario: str) -> str:
    return {
        "hard_cut": "hard_cut",
        "sustained_branch": "sustained_branch",
        "mainline_bridge": "mainline_bridge",
        "first_chapter": "first_chapter",
        "optional_gap": "optional_gap",
        "no_match": "previous_empty",
        "directory_only": "summary_directory",
        "admission_gap": "optional_gap",
    }.get(scenario, "continue")


def _base_bundle(scenario: str, artifact_kind: str) -> dict[str, Any]:
    task_bundle = task_validator.build_base_bundle(_task_base_for_scenario(scenario))
    task = task_bundle["task"]
    request, plan, result, outcomes, registry = _compile_c9(task, scenario)
    bundle: dict[str, Any] = {
        "scenario": scenario,
        "artifact_kind": artifact_kind,
        "task_bundle": task_bundle,
        "c9_request": request,
        "c9_plan": plan,
        "c9_result": result,
        "c9_outcomes": outcomes,
        "c9_registry": registry,
    }
    bundle["version_proofs"] = _version_proofs(task_bundle, request, result)
    base_artifact = _build_card_or_failure(bundle)
    if artifact_kind == "CARD":
        bundle["artifact"] = base_artifact
    elif artifact_kind == "FAILURE":
        bundle["artifact"] = base_artifact
    elif artifact_kind == "ADMISSION":
        if base_artifact["contract"] != "CHAPTER_THIN_CARD":
            _fail("ADMISSION_REQUIRES_SUCCESS_CARD")
        checks = _current_proofs(base_artifact, scenario)
        bundle["thin_card"] = base_artifact
        bundle["current_proofs"] = checks
        bundle["artifact"] = _build_admission(base_artifact, checks)
    else:
        _fail(f"FIXTURE_ARTIFACT_KIND_INVALID:{artifact_kind}")
    return bundle


def _validate_task_and_c9(bundle: dict[str, Any]) -> None:
    try:
        task_validator.validate_task_bundle(bundle["task_bundle"])
    except Exception as exc:
        raise ThinCardError(f"UPSTREAM_TASK_INVALID:{exc}") from exc
    try:
        c9_core.validate_result(
            bundle["c9_result"],
            bundle["c9_request"],
            bundle["c9_plan"],
            bundle["c9_outcomes"],
            bundle["c9_registry"],
        )
    except Exception as exc:
        raise ThinCardError(f"UPSTREAM_C9_INVALID:{exc}") from exc

    task = bundle["task_bundle"]["task"]
    request = bundle["c9_request"]
    if request["source_needs"] != task["c9_source_needs"]:
        _fail("TASK_C9_SOURCE_NEEDS_MISMATCH")
    if request["scope"] != _c9_scope(task):
        _fail("C9_SCOPE_MISMATCH")
    evidence = _task_no_match_evidence(bundle["task_bundle"])
    storage_generation = _task_no_match_generation(evidence)
    expected_task_proofs = sorted(
        (
            _task_no_match_version(source, response, storage_generation)
            for source, response in evidence
        ),
        key=lambda row: row["version_ref"],
    )
    observed_task_proofs = sorted(
        (
            row
            for row in bundle["version_proofs"]
            if row["binding_kind"] == "TASK_SOURCE_RESULT"
        ),
        key=lambda row: row["version_ref"],
    )
    if observed_task_proofs != expected_task_proofs:
        _fail("TASK_NO_MATCH_VERSION_BINDING_MISMATCH")


def _validate_task_no_match_projection(
    task_bundle: dict[str, Any], payload: dict[str, Any]
) -> None:
    evidence = _task_no_match_evidence(task_bundle)
    storage_generation = _task_no_match_generation(evidence)
    expected_proofs = [
        _task_no_match_version(source, response, storage_generation)
        for source, response in evidence
    ]
    observed_proofs = [
        row
        for row in payload["version_manifest"]
        if row["binding_kind"] == "TASK_SOURCE_RESULT"
    ]
    if sorted(observed_proofs, key=lambda row: row["version_ref"]) != sorted(
        expected_proofs, key=lambda row: row["version_ref"]
    ):
        _fail("TASK_NO_MATCH_VERSION_BINDING_MISMATCH")

    result_map = {
        row["result_id"]: row for row in payload["source_results"]
    }
    for proof in expected_proofs:
        result_id = f"RESULT-{proof['version_ref']}"
        observed = result_map.get(result_id)
        if observed is None:
            _fail("TASK_NO_MATCH_SOURCE_RESULT_REQUIRED")
        expected = {
            "result_id": result_id,
            "material_role": "FACT_EXPRESSION",
            "state": "NO_MATCH",
            "reason_code": "NO_MATCHING_ENTRIES",
            "identity_disclosure": {
                "mode": "DISCLOSED",
                "version_ref": proof["version_ref"],
            },
        }
        if observed != expected:
            _fail("TASK_NO_MATCH_SOURCE_RESULT_MISMATCH")


def _validate_source_disclosures(
    source_results: list[dict[str, Any]],
    version_map: dict[str, dict[str, Any]],
) -> None:
    for result in source_results:
        state = result["state"]
        disclosure = result["identity_disclosure"]
        mode = disclosure["mode"]
        if state in {"PRESENT", "EMPTY", "NO_MATCH"} and mode != "DISCLOSED":
            _fail("SOURCE_RESULT_DISCLOSURE_INVALID")
        if state in {"UNTRACKED", "UNAVAILABLE"} and mode != "NOT_AVAILABLE":
            _fail("SOURCE_RESULT_DISCLOSURE_INVALID")
        if state == "UNAUTHORIZED" and mode != "MASKED":
            _fail("SOURCE_RESULT_DISCLOSURE_INVALID")
        if mode == "DISCLOSED" and disclosure["version_ref"] not in version_map:
            _fail("SOURCE_RESULT_VERSION_UNKNOWN")


def _validate_card(
    card: dict[str, Any], expected: dict[str, Any], bundle: dict[str, Any]
) -> str:
    task = bundle["task_bundle"]["task"]
    result = bundle["c9_result"]
    payload = card["compiled_payload"]
    expected_payload = expected["compiled_payload"]

    if card["retrieval_task_ref"] != _task_ref(task):
        _fail("RETRIEVAL_TASK_REF_MISMATCH")
    if card["c9_run_ref"] != _c9_run_ref(result):
        _fail("C9_RUN_REF_MISMATCH")
    if card["scope_projection"] != task["scope_projection"]:
        _fail("SCOPE_PROJECTION_MISMATCH")
    if card["truth_scope_ref"] != task["truth_scope_ref"]:
        _fail("TRUTH_SCOPE_MISMATCH")
    if card["workpoint_ref"] != _workpoint(task):
        _fail("WORKPOINT_MISMATCH")
    if card["build_policy"] != BUILD_POLICY:
        _fail("BUILD_POLICY_MISMATCH")

    version_map = _unique_map(
        payload["version_manifest"],
        "version_ref",
        "VERSION_REF_DUPLICATE",
    )
    _validate_task_no_match_projection(bundle["task_bundle"], payload)
    if {row["material_role"] for row in payload["version_manifest"]} != (
        REQUIRED_MATERIAL_ROLES
    ):
        _fail("VERSION_ROLE_COVERAGE_MISMATCH")
    generations = {
        row["storage_generation"] for row in payload["version_manifest"]
    }
    if len(generations) != 1:
        _fail("STORAGE_GENERATION_MIXED")
    if payload["version_manifest"] != expected_payload["version_manifest"]:
        _fail("VERSION_MANIFEST_MISMATCH")

    _unique_map(
        payload["source_results"],
        "result_id",
        "SOURCE_RESULT_ID_DUPLICATE",
    )
    _validate_source_disclosures(payload["source_results"], version_map)
    if payload["source_results"] != expected_payload["source_results"]:
        _fail("SOURCE_RESULTS_MISMATCH")

    for view in payload["character_views"]:
        current = view["character_current_definition"]
        story = view["character_story_time_slice"]
        if (
            current["source_version_ref"] == story["source_version_ref"]
            or current["time_anchor_ref"] == story["time_anchor_ref"]
        ):
            _fail("CHARACTER_VIEW_IDENTITY_COLLAPSED")
        if (
            current["source_version_ref"] not in version_map
            or story["source_version_ref"] not in version_map
        ):
            _fail("CHARACTER_VIEW_VERSION_UNKNOWN")
    if payload["character_views"] != expected_payload["character_views"]:
        _fail("CHARACTER_VIEWS_MISMATCH")
    if payload["current_chapter_plan_snapshot"] != expected_payload[
        "current_chapter_plan_snapshot"
    ]:
        _fail("PLAN_SNAPSHOT_MISMATCH")
    if payload["previous_chapter_committed_snapshot"] != expected_payload[
        "previous_chapter_committed_snapshot"
    ]:
        _fail("PREVIOUS_SNAPSHOT_MISMATCH")
    if payload["uncommitted_workspace_delta_refs"] != expected_payload[
        "uncommitted_workspace_delta_refs"
    ]:
        _fail("WORKSPACE_DELTA_MISMATCH")

    if any(
        row["reason_code"] == "THIN_CARD_BYTE_LIMIT"
        and row["obligation_tier"] == "HARD"
        for row in payload["on_demand_layer"]
    ) or any(
        row["need_id"]
        in {
            item["need_id"]
            for item in expected_payload["resident_layer"]
            if item["obligation_tier"] == "HARD"
        }
        for row in card["size_receipt"]["demotions"]
    ):
        _fail("HARD_DEMOTION_FORBIDDEN")

    loaded_map = {
        row["need_id"]: row for row in result["material_package"]["loaded"]
    }
    resident_map = _unique_map(
        payload["resident_layer"],
        "need_id",
        "RESIDENT_NEED_DUPLICATE",
    )
    for need_id, item in resident_map.items():
        if need_id not in loaded_map:
            _fail("RESIDENT_NOT_C9_LOADED")
        expected_item = next(
            row for row in expected_payload["resident_layer"] if row["need_id"] == need_id
        )
        if item != expected_item:
            _fail("RESIDENT_ITEM_MISMATCH")
    expected_hard = {
        row["need_id"]
        for row in expected_payload["resident_layer"]
        if row["obligation_tier"] == "HARD"
    }
    if not expected_hard.issubset(resident_map):
        _fail("HARD_LOADED_NOT_RESIDENT")
    if payload["resident_layer"] != expected_payload["resident_layer"]:
        _fail("RESIDENT_ORDER_MISMATCH")

    valid_on_demand_ids = {
        row["need_id"] for row in expected_payload["on_demand_layer"]
    }
    _unique_map(
        payload["on_demand_layer"],
        "entry_id",
        "ON_DEMAND_ENTRY_DUPLICATE",
    )
    for item in payload["on_demand_layer"]:
        if item["reason_code"] == "THIN_CARD_BYTE_LIMIT" and (
            item["obligation_tier"] == "HARD"
        ):
            _fail("HARD_DEMOTION_FORBIDDEN")
        if item["need_id"] not in valid_on_demand_ids:
            _fail("ON_DEMAND_SOURCE_INVALID")
    if payload["on_demand_layer"] != expected_payload["on_demand_layer"]:
        _fail("ON_DEMAND_LAYER_MISMATCH")
    if payload["gap_summary"] != expected_payload["gap_summary"]:
        _fail("GAP_SUMMARY_MISMATCH")

    if card["size_receipt"]["demotions"] != expected["size_receipt"]["demotions"]:
        _fail("DEMOTION_ORDER_INVALID")
    actual_bytes = len(canonical_bytes(payload))
    if card["size_receipt"]["normalized_utf8_bytes"] != actual_bytes:
        _fail("PAYLOAD_BYTE_COUNT_MISMATCH")
    if actual_bytes > MAX_PAYLOAD_BYTES:
        _fail("REQUIRED_RESIDENT_CONTENT_TOO_LARGE")
    if card["input_basis_sha256"] != _input_basis(
        task,
        result,
        bundle["version_proofs"],
    ):
        _fail("INPUT_BASIS_SHA256_MISMATCH")
    if card["compiled_payload_sha256"] != sha256_json(payload):
        _fail("COMPILED_PAYLOAD_SHA256_MISMATCH")
    unhashed = copy.deepcopy(card)
    observed_sha = unhashed.pop("thin_card_sha256")
    if observed_sha != sha256_json(unhashed):
        _fail("THIN_CARD_SHA256_MISMATCH")
    if card != expected:
        _fail("THIN_CARD_NOT_CANONICAL")
    return STRUCTURAL_VALID


def _validate_admission_disclosures(checks: list[dict[str, Any]]) -> None:
    for check in checks:
        if check["observed_state"] in {"REVOKED", "UNAUTHORIZED"} and (
            check["disclosure"]["mode"] != "MASKED"
        ):
            _fail("ADMISSION_MASK_LEAK")


def _validate_admission(
    receipt: dict[str, Any], expected: dict[str, Any], card: dict[str, Any]
) -> str:
    if receipt["thin_card_ref"] != {
        "thin_card_id": card["thin_card_id"],
        "thin_card_sha256": card["thin_card_sha256"],
    }:
        _fail("ADMISSION_CARD_REF_MISMATCH")
    _unique_map(receipt["checks"], "check_id", "ADMISSION_CHECK_ID_DUPLICATE")
    _validate_current_proofs(card, receipt["checks"])
    _validate_admission_disclosures(receipt["checks"])
    if receipt["checks"] != expected["checks"]:
        _fail("ADMISSION_CHECK_MISMATCH")
    if (
        receipt["status"] != expected["status"]
        or receipt["reason_codes"] != expected["reason_codes"]
        or receipt["recompile_required"] != expected["recompile_required"]
    ):
        _fail("ADMISSION_STATUS_MISMATCH")
    unhashed = copy.deepcopy(receipt)
    observed_sha = unhashed.pop("admission_receipt_sha256")
    if observed_sha != sha256_json(unhashed):
        _fail("ADMISSION_RECEIPT_SHA256_MISMATCH")
    if receipt != expected:
        _fail("ADMISSION_RECEIPT_NOT_CANONICAL")
    return STRUCTURAL_VALID


def _validate_failure(
    failure: dict[str, Any], expected: dict[str, Any]
) -> str:
    for field in (
        "truth_scope_ref",
        "workpoint_ref",
        "failure_stage",
        "reason_code",
        "identity_disclosure",
        "retry_disposition",
        "recompile_required",
        "input_basis_sha256",
    ):
        if failure[field] != expected[field]:
            _fail("BUILD_FAILURE_MISMATCH")
    unhashed = copy.deepcopy(failure)
    observed_sha = unhashed.pop("build_failure_sha256")
    if observed_sha != sha256_json(unhashed):
        _fail("BUILD_FAILURE_SHA256_MISMATCH")
    if failure != expected:
        _fail("BUILD_FAILURE_NOT_CANONICAL")
    return STRUCTURAL_VALID


def validate_bundle(bundle: Any) -> str:
    if not isinstance(bundle, dict):
        _fail("BUNDLE_OBJECT_REQUIRED")
    required = {
        "scenario",
        "artifact_kind",
        "task_bundle",
        "c9_request",
        "c9_plan",
        "c9_result",
        "c9_outcomes",
        "c9_registry",
        "version_proofs",
        "artifact",
    }
    if not required.issubset(bundle):
        _fail("BUNDLE_FIELDS_MISSING")
    _validate_task_and_c9(bundle)
    artifact = bundle["artifact"]
    _validate_schema(artifact)
    expected = _build_card_or_failure(bundle)
    kind = artifact["contract"]

    if kind == "CHAPTER_THIN_CARD":
        if expected["contract"] != "CHAPTER_THIN_CARD":
            _fail("SUCCESS_CARD_FOR_FAILED_BUILD")
        return _validate_card(artifact, expected, bundle)
    if kind == "CHAPTER_THIN_CARD_BUILD_FAILURE":
        if expected["contract"] != "CHAPTER_THIN_CARD_BUILD_FAILURE":
            _fail("BUILD_FAILURE_WITHOUT_BUILD_FAILURE")
        return _validate_failure(artifact, expected)
    if kind == "CHAPTER_THIN_CARD_ADMISSION_RECEIPT":
        card = bundle.get("thin_card")
        checks = bundle.get("current_proofs")
        if not isinstance(card, dict) or not isinstance(checks, list):
            _fail("ADMISSION_INPUTS_REQUIRED")
        _validate_schema(card)
        expected_card = _build_card_or_failure(bundle)
        if expected_card["contract"] != "CHAPTER_THIN_CARD":
            _fail("ADMISSION_REQUIRES_SUCCESS_CARD")
        _validate_card(card, expected_card, bundle)
        _validate_current_proofs(card, checks)
        expected_receipt = _build_admission(card, checks)
        return _validate_admission(artifact, expected_receipt, card)
    _fail("ARTIFACT_CONTRACT_INVALID")


def _rebuild_c9(
    bundle: dict[str, Any],
    *,
    scope: dict[str, Any] | None = None,
    needs: list[dict[str, Any]] | None = None,
) -> None:
    task = bundle["task_bundle"]["task"]
    request, plan, result, outcomes, registry = _compile_c9(
        task,
        "continue",
        scope_override=scope,
        needs_override=needs,
    )
    bundle["c9_request"] = request
    bundle["c9_plan"] = plan
    bundle["c9_result"] = result
    bundle["c9_outcomes"] = outcomes
    bundle["c9_registry"] = registry


def _sample_on_demand(card: dict[str, Any]) -> dict[str, Any]:
    layer = card["compiled_payload"]["on_demand_layer"]
    if not layer:
        _fail("FIXTURE_ON_DEMAND_SAMPLE_REQUIRED")
    return layer[0]


def apply_mutation(bundle: dict[str, Any], mutation: str) -> dict[str, Any]:
    if mutation == "none":
        return bundle
    artifact = bundle["artifact"]
    if mutation == "unknown_field":
        artifact["unexpected"] = True
    elif mutation == "wrong_contract":
        artifact["contract"] = "CHAPTER_THIN_CARD_V2"
    elif mutation == "scope_projection_mismatch":
        artifact["scope_projection"]["selected_storyline_ref"] = "LINE-9999"
    elif mutation == "retrieval_task_ref":
        artifact["retrieval_task_ref"]["retrieval_task_id"] = "RETRIEVAL-TASK-9999"
    elif mutation == "c9_run_ref":
        artifact["c9_run_ref"]["run_sha256"] = "0" * 64
    elif mutation == "task_c9_needs_mismatch":
        needs = copy.deepcopy(bundle["c9_request"]["source_needs"])
        extra = copy.deepcopy(needs[-1])
        extra.update(
            {
                "need_id": "NEED-EXTRA",
                "object_ref": "SUMMARY-EXTRA-0001",
                "selection_rank": 99,
                "task_relation": "额外合成需要",
            }
        )
        needs.append(extra)
        _rebuild_c9(bundle, needs=needs)
    elif mutation == "c9_scope_mismatch":
        scope = copy.deepcopy(bundle["c9_request"]["scope"])
        scope["story_scope_ref"] = "LINE-9999"
        _rebuild_c9(bundle, scope=scope)
    elif mutation == "resident_unknown_need":
        artifact["compiled_payload"]["resident_layer"][0]["need_id"] = "NEED-UNKNOWN"
    elif mutation == "resident_material_changed":
        artifact["compiled_payload"]["resident_layer"][0]["material_text"] = "被改写的材料"
    elif mutation == "resident_why_changed":
        artifact["compiled_payload"]["resident_layer"][0]["why_loaded"] = "伪造理由"
    elif mutation == "resident_obligation_changed":
        artifact["compiled_payload"]["resident_layer"][0]["obligation_tier"] = "MAY"
    elif mutation == "missing_hard_resident":
        residents = artifact["compiled_payload"]["resident_layer"]
        residents[:] = [row for row in residents if row["obligation_tier"] != "HARD"]
    elif mutation == "on_demand_unknown_need":
        payload = artifact["compiled_payload"]
        sample = copy.deepcopy(payload["resident_layer"][-1])
        payload["on_demand_layer"].append(
            {
                "entry_id": "ON-DEMAND-UNKNOWN",
                "need_id": "NEED-UNKNOWN",
                "box_id": None,
                "object_ref": sample["object_ref"],
                "evidence_layer": sample["evidence_layer"],
                "parent_need_id": sample["parent_need_id"],
                "obligation_tier": "SHOULD",
                "reason_code": "NOT_RESIDENT",
                "recall_handle": "recall:NEED-UNKNOWN",
                "relation_scope_refs": sample["relation_scope_refs"],
                "source_result_ref": sample["source_result_ref"],
            }
        )
    elif mutation == "on_demand_missing_handle":
        _sample_on_demand(artifact)["recall_handle"] = ""
    elif mutation == "on_demand_content_leak":
        _sample_on_demand(artifact)["material_text"] = "不应出现"
    elif mutation == "hard_byte_demotion":
        payload = artifact["compiled_payload"]
        hard = next(row for row in payload["resident_layer"] if row["obligation_tier"] == "HARD")
        payload["resident_layer"].remove(hard)
        payload["on_demand_layer"].append(
            {
                "entry_id": f"ON-DEMAND-{hard['need_id']}",
                "need_id": hard["need_id"],
                "box_id": None,
                "object_ref": hard["object_ref"],
                "evidence_layer": hard["evidence_layer"],
                "parent_need_id": hard["parent_need_id"],
                "obligation_tier": "HARD",
                "reason_code": "THIN_CARD_BYTE_LIMIT",
                "recall_handle": hard["recall"]["handle"],
                "relation_scope_refs": hard["relation_scope_refs"],
                "source_result_ref": hard["source_result_ref"],
            }
        )
        artifact["size_receipt"]["demotions"].append(
            {
                "need_id": hard["need_id"],
                "from_layer": "RESIDENT",
                "to_layer": "ON_DEMAND",
                "reason_code": "THIN_CARD_BYTE_LIMIT",
            }
        )
    elif mutation == "demotion_order":
        artifact["size_receipt"]["demotions"].append(
            {
                "need_id": "NEED-BOX-OLDER",
                "from_layer": "RESIDENT",
                "to_layer": "ON_DEMAND",
                "reason_code": "THIN_CARD_BYTE_LIMIT",
            }
        )
    elif mutation == "duplicate_version_ref":
        versions = artifact["compiled_payload"]["version_manifest"]
        versions.append(copy.deepcopy(versions[0]))
    elif mutation == "version_manifest_mismatch":
        artifact["compiled_payload"]["version_manifest"][0]["revision_ref"] = "REVISION-9999"
    elif mutation == "character_view_collapsed":
        view = artifact["compiled_payload"]["character_views"][0]
        view["character_story_time_slice"] = copy.deepcopy(
            view["character_current_definition"]
        )
    elif mutation == "plan_snapshot_mismatch":
        artifact["compiled_payload"]["current_chapter_plan_snapshot"]["slot_rev"] += 1
    elif mutation == "previous_snapshot_mismatch":
        artifact["compiled_payload"]["previous_chapter_committed_snapshot"][
            "settlement_sha256"
        ] = "0" * 64
    elif mutation == "uncommitted_as_committed":
        artifact["compiled_payload"]["uncommitted_workspace_delta_refs"][0][
            "actuality_class"
        ] = "COMMITTED_TRUTH"
    elif mutation == "untracked_disclosed":
        result = artifact["compiled_payload"]["source_results"][0]
        result["state"] = "UNTRACKED"
    elif mutation == "unauthorized_disclosed":
        result = artifact["compiled_payload"]["source_results"][0]
        result["state"] = "UNAUTHORIZED"
    elif mutation == "source_result_unknown_version":
        result = next(
            row
            for row in artifact["compiled_payload"]["source_results"]
            if row["identity_disclosure"]["mode"] == "DISCLOSED"
        )
        result["identity_disclosure"]["version_ref"] = "VERSION-UNKNOWN"
    elif mutation == "storage_generation_mixed":
        artifact["compiled_payload"]["version_manifest"][0][
            "storage_generation"
        ] = "STORAGE-GENERATION-9999"
    elif mutation == "task_no_match_source_result_missing":
        payload = artifact["compiled_payload"]
        proof = next(
            row
            for row in payload["version_manifest"]
            if row["binding_kind"] == "TASK_SOURCE_RESULT"
        )
        result_id = f"RESULT-{proof['version_ref']}"
        payload["source_results"] = [
            row for row in payload["source_results"] if row["result_id"] != result_id
        ]
    elif mutation == "task_no_match_source_result_mismatch":
        payload = artifact["compiled_payload"]
        proof = next(
            row
            for row in payload["version_manifest"]
            if row["binding_kind"] == "TASK_SOURCE_RESULT"
        )
        result_id = f"RESULT-{proof['version_ref']}"
        result = next(
            row for row in payload["source_results"] if row["result_id"] == result_id
        )
        result["state"] = "EMPTY"
        result["reason_code"] = "VALID_EMPTY_OBJECT"
    elif mutation == "task_no_match_version_binding_mismatch":
        proof = next(
            row
            for row in artifact["compiled_payload"]["version_manifest"]
            if row["binding_kind"] == "TASK_SOURCE_RESULT"
        )
        proof["binding_kind"] = "OWNER_PROOF"
    elif mutation == "input_hash":
        artifact["input_basis_sha256"] = "0" * 64
    elif mutation == "payload_hash":
        artifact["compiled_payload_sha256"] = "0" * 64
    elif mutation == "card_hash":
        artifact["thin_card_sha256"] = "0" * 64
    elif mutation == "byte_count":
        artifact["size_receipt"]["normalized_utf8_bytes"] += 1
    elif mutation == "admission_card_ref":
        artifact["thin_card_ref"]["thin_card_id"] = "THIN-CARD-9999"
    elif mutation == "admission_status":
        artifact["status"] = "ADMITTED"
        artifact["reason_codes"] = []
        artifact["recompile_required"] = False
    elif mutation == "admission_mask_leak":
        check = next(row for row in artifact["checks"] if row["observed_state"] == "REVOKED")
        check["disclosure"] = {
            "mode": "DISCLOSED",
            "subject_ref": "HIDDEN-PERMISSION",
            "expected_sha256": "1" * 64,
            "observed_sha256": "2" * 64,
        }
    elif mutation == "admission_hash":
        artifact["admission_receipt_sha256"] = "0" * 64
    elif mutation == "admission_missing_check":
        checks = bundle["current_proofs"]
        checks.pop()
        bundle["artifact"] = _build_admission(bundle["thin_card"], checks)
    elif mutation == "admission_duplicate_check_kind":
        checks = bundle["current_proofs"]
        checks[-1]["check_kind"] = checks[0]["check_kind"]
        bundle["artifact"] = _build_admission(bundle["thin_card"], checks)
    elif mutation == "admission_wrong_expected_fingerprint":
        checks = bundle["current_proofs"]
        disclosure = checks[6]["disclosure"]
        disclosure["expected_sha256"] = "0" * 64
        disclosure["observed_sha256"] = "0" * 64
        bundle["artifact"] = _build_admission(bundle["thin_card"], checks)
    elif mutation == "admission_match_fingerprint":
        checks = bundle["current_proofs"]
        checks[6]["disclosure"]["observed_sha256"] = "0" * 64
        bundle["artifact"] = _build_admission(bundle["thin_card"], checks)
    elif mutation == "admission_current_proof_shape":
        bundle["current_proofs"][0]["disclosure"].pop("mode")
    elif mutation == "failure_has_card_id":
        artifact["thin_card_id"] = "THIN-CARD-0001"
    elif mutation == "failure_hash":
        artifact["build_failure_sha256"] = "0" * 64
    elif mutation == "failure_status":
        artifact["status"] = "READY"
    elif mutation in {"success_when_unsupported", "success_when_c9_stopped"}:
        replacement = _base_bundle("continue", "CARD")["artifact"]
        bundle["artifact"] = replacement
    elif mutation == "thin_card_current_field":
        artifact["current_status"] = "CURRENT"
    elif mutation == "plugin_field":
        artifact["compiled_payload"]["plugin_payload"] = {"vendor": "synthetic"}
    else:
        _fail(f"FIXTURE_MUTATION_UNKNOWN:{mutation}")
    return bundle


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if any(not isinstance(row, dict) or set(row) != RECIPE_KEYS for row in rows):
        _fail("FIXTURE_FIELDS_INVALID")
    ids = [row["case_id"] for row in rows]
    if len(ids) != len(set(ids)):
        _fail("FIXTURE_CASE_ID_DUPLICATE")
    return rows


def materialize_fixture_case(case: dict[str, Any]) -> dict[str, Any]:
    bundle = _base_bundle(case["base"], case["artifact"])
    return apply_mutation(bundle, case["mutation"])


def fixture_error_code(case: dict[str, Any]) -> str | None:
    try:
        validate_bundle(materialize_fixture_case(case))
    except ThinCardError as exc:
        return str(exc).split(":", maxsplit=1)[0]
    return None


def validate_fixture_case(case: dict[str, Any]) -> str:
    try:
        result = validate_bundle(materialize_fixture_case(case))
    except ThinCardError:
        result = STRUCTURAL_INVALID
    if result != case["expected_result"]:
        _fail(f"FIXTURE_EXPECTATION_MISMATCH:{case['case_id']}:{result}")
    return result


def validate_all_fixtures(path: Path = FIXTURE_PATH) -> dict[str, int]:
    counts = {STRUCTURAL_VALID: 0, STRUCTURAL_INVALID: 0}
    for case in load_fixtures(path):
        counts[validate_fixture_case(case)] += 1
    if counts != EXPECTED_COUNTS:
        _fail(f"FIXTURE_COUNTS_MISMATCH:{counts}")
    return counts


def main() -> int:
    counts = validate_all_fixtures()
    print(
        json.dumps(
            {
                "contract_family": "CHAPTER_THIN_CARD",
                "version": "v1",
                "status": "PASS",
                "counts": counts,
                "synthetic_c9_compilation_performed": True,
                "real_reader_calls": 0,
                "real_c9_calls": 0,
                "workspace_reads": 0,
                "network_calls": 0,
                "model_calls": 0,
                "database_writes": 0,
                "ui_actions": 0,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
