#!/usr/bin/env python3
"""Validate CHAPTER_CONTEXT_RETRIEVAL_TASK v1 structural boundaries."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator


DIR = Path(__file__).resolve().parent
PRODUCT_ROOT = DIR.parent
SCHEMA_PATH = DIR / "CHAPTER_CONTEXT_RETRIEVAL_TASK.schema.json"
FIXTURE_PATH = DIR / "CHAPTER_CONTEXT_RETRIEVAL_TASK.fixtures.jsonl"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import unified_retrieval_core as c9_core
finally:
    sys.path.pop(0)

STRUCTURAL_VALID = "STRUCTURAL_VALID"
STRUCTURAL_INVALID = "STRUCTURAL_INVALID"
RECIPE_KEYS = {"base", "case_id", "expected_result", "mutation"}

SOURCE_VERSIONS = dict(c9_core.SOURCE_CONTRACT_VERSIONS)
MANIFEST_SOURCE_VERSIONS = {
    "CHAPTER_SCOPE_CONFIRMATION": "v1",
    "CHAPTER_PREDECESSOR_BINDING": "v1",
    "CHAPTER_SETTLEMENT_SEAL": "v1",
    "CHAPTER_LAYERED_SUMMARY": "v1",
    "LEDGER_READ_TOOL_CONTRACT": "ledger-read-tool-contract-v1",
    "TRACEABLE_PROVENANCE_SEAL": "v1",
}
OPENED_STATES = {
    "OPENED_OK",
    "OPENED_EMPTY",
    "OPENED_REJECTED",
    "OPENED_ERROR",
}
ACCESS_TO_STATUS = {
    "OPENED_OK": "OK",
    "OPENED_EMPTY": "EMPTY",
    "OPENED_REJECTED": "REJECTED",
    "OPENED_ERROR": "ERROR",
}
OBLIGATION_RANK = {"HARD": 0, "SHOULD": 1, "MAY": 2}
FORBIDDEN_CONTENT_KEYS = {
    "body",
    "chapter_text",
    "database_table",
    "file_path",
    "material_text",
    "path",
    "sql",
    "storage_path",
    "table_name",
    "token_budget",
}
EXPECTED_ERROR_CODES = {
    "scope_non_confirmed": "NON_CONFIRMED_SCOPE_MUST_STOP",
    "scope_projection_mismatch": "SCOPE_PROJECTION_MISMATCH",
    "second_scope_field": "SCHEMA_INVALID",
    "settlement_scope_mismatch": "TRUTH_SCOPE_MISMATCH",
    "settlement_owner_unresolved": "PREVIOUS_SETTLEMENT_OWNER_UNRESOLVED",
    "continuing_without_settlement": "CONTINUING_CHAPTER_PREVIOUS_HANDOFF_REQUIRED",
    "fact_not_in_response": "FACT_NOT_IN_OPENED_RESPONSE",
    "fact_revision_mismatch": "FACT_REVISION_MISMATCH",
    "fact_from_empty": "FACT_SOURCE_MUST_BE_OPENED_OK",
    "current_advanced_ready": "FAILED_SOURCE_MUST_STOP",
    "result_too_large_ready": "FAILED_SOURCE_MUST_STOP",
    "truncated_response": "TRUNCATED_LEDGER_RESPONSE_FORBIDDEN",
    "unavailable_marked_empty": "UNOPENED_SOURCE_CANNOT_CLAIM_CONTENT",
    "physical_box": "SCHEMA_INVALID",
    "unauthorized_box_leak": "SCHEMA_INVALID",
    "directory_only_content": "SCHEMA_INVALID",
    "c9_wrong_version": "C9_SOURCE_CONTRACT_VERSION_MISMATCH",
    "c9_mapping_missing": "TASK_MATERIAL_TO_C9_NEED_MAPPING_MISMATCH",
    "orphan_child_need": "C9_PARENT_NEED_NOT_FOUND",
    "child_obligation_escalation": "C9_CHILD_OBLIGATION_ESCALATION",
    "natural_language_path": "SCHEMA_INVALID",
    "unknown_field": "SCHEMA_INVALID",
    "duplicate_source_id": "SOURCE_ID_DUPLICATE",
    "stale_task_hash": "TASK_BASIS_SHA256_MISMATCH",
    "full_c9_budget": "SCHEMA_INVALID",
    "coverage_partition_mismatch": "READ_COVERAGE_PARTITION_MISMATCH",
    "optional_gap_as_ready": "READY_STATUS_SHAPE_INVALID",
    "manifest_authorization_outside": "SOURCE_AUTHORIZATION_OUTSIDE_CONFIRMED_SCOPE",
    "non_confirmed_box_leak": "NON_CONFIRMED_SCOPE_STOP_MUST_BE_EMPTY",
    "opened_summary_without_evidence": "OPENED_SUMMARY_SOURCE_NOT_PROVIDED",
    "box_source_contract_mismatch": "BOX_C9_NEED_SOURCE_CONTRACT_MISMATCH",
    "source_version_mismatch": "SOURCE_MANIFEST_CONTRACT_VERSION_MISMATCH",
    "provenance_original_layer": "C9_NEED_ORDER_INVALID",
    "fact_missing_chapter_revision": "FACT_CHAPTER_REVISION_REQUIRED",
    "fact_basis_mismatch": "FACT_SELECTION_BASIS_REFS_MISMATCH",
    "predecessor_current_slot_mismatch": "PREDECESSOR_BINDING_CURRENT_SLOT_MISMATCH",
    "predecessor_settlement_mismatch": "PREDECESSOR_SETTLEMENT_MISMATCH",
    "predecessor_first_with_previous": "FIRST_CHAPTER_PREVIOUS_HANDOFF_FORBIDDEN",
    "previous_obligation_downgrade": "PREVIOUS_HANDOFF_C9_NEED_MISMATCH",
    "box_obligation_downgrade": "BOX_C9_NEED_OBLIGATION_MISMATCH",
    "duplicate_selected_fact": "FACT_REF_DUPLICATE",
    "stopped_box_entry_leak": "STOPPED_BOX_CANNOT_EXPOSE_RETRIEVAL_ENTRY",
    "stopped_source_entry_leak": "STOPPED_SOURCE_CANNOT_EXPOSE_RETRIEVAL_ENTRY",
}


class ContractError(ValueError):
    """A chapter context retrieval task invariant failed."""


def _load_module(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, DIR / filename)
    if spec is None or spec.loader is None:
        raise ContractError(f"UPSTREAM_VALIDATOR_UNAVAILABLE:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scope_validator = _load_module(
    "validate_chapter_scope_confirmation.py", "ccz139_scope_validator"
)
settlement_validator = _load_module(
    "validate_chapter_settlement_seal.py", "ccz139_settlement_validator"
)
summary_validator = _load_module(
    "validate_chapter_layered_summary.py", "ccz139_summary_validator"
)
ledger_validator = _load_module(
    "validate_ledger_read_tool_contract.py", "ccz139_ledger_validator"
)
provenance_validator = _load_module(
    "validate_traceable_provenance_seal.py", "ccz139_provenance_validator"
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError(f"JSON_OBJECT_REQUIRED:{path.name}")
    return value


SCHEMA = _load_json(SCHEMA_PATH)
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA)

C9_SCHEMA = _load_json(DIR / "C9_UNIFIED_RETRIEVAL_RUN.schema.json")
C9_NEED_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$ref": "#/$defs/source_need",
    "$defs": C9_SCHEMA["$defs"],
}
Draft202012Validator.check_schema(C9_NEED_SCHEMA)
C9_NEED_VALIDATOR = Draft202012Validator(C9_NEED_SCHEMA)
PREDECESSOR_BINDING_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$ref": "#/$defs/chapter_predecessor_binding",
    "$defs": SCHEMA["$defs"],
}
Draft202012Validator.check_schema(PREDECESSOR_BINDING_SCHEMA)
PREDECESSOR_BINDING_VALIDATOR = Draft202012Validator(PREDECESSOR_BINDING_SCHEMA)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def task_basis_sha256(task: dict[str, Any]) -> str:
    payload = copy.deepcopy(task)
    payload.pop("task_basis_sha256", None)
    return sha256_json(payload)


def predecessor_binding_basis_sha256(binding: dict[str, Any]) -> str:
    payload = copy.deepcopy(binding)
    payload.pop("binding_basis_sha256", None)
    return sha256_json(payload)


def seal_predecessor_binding(binding: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(binding)
    result["binding_basis_sha256"] = predecessor_binding_basis_sha256(result)
    return result


def seal_task(task: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(task)
    result["task_basis_sha256"] = task_basis_sha256(result)
    return result


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
        raise ContractError(
            f"SCHEMA_INVALID:{_schema_path(first)}:{first.validator}"
        )


def _walk_forbidden_content(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_CONTENT_KEYS:
                raise ContractError(f"PROTECTED_CONTENT_KEY_FORBIDDEN:{path}.{key}")
            _walk_forbidden_content(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_forbidden_content(item, f"{path}[{index}]")


def _unique_map(rows: list[dict[str, Any]], key: str, label: str) -> dict[str, Any]:
    values = [row[key] for row in rows]
    if len(values) != len(set(values)):
        raise ContractError(f"{label}_DUPLICATE")
    return {row[key]: row for row in rows}


def _validate_manifest_shape(task: dict[str, Any]) -> dict[str, dict[str, Any]]:
    manifest = task["source_manifest"]
    if manifest != sorted(manifest, key=lambda row: row["source_id"]):
        raise ContractError("SOURCE_MANIFEST_NOT_STABLY_SORTED")
    source_map = _unique_map(manifest, "source_id", "SOURCE_ID")
    for row in manifest:
        if row["source_contract_version"] != MANIFEST_SOURCE_VERSIONS[
            row["source_contract"]
        ]:
            raise ContractError("SOURCE_MANIFEST_CONTRACT_VERSION_MISMATCH")
        state = row["access_state"]
        if state in OPENED_STATES:
            if row["source_document_sha256"] is None:
                raise ContractError("OPENED_SOURCE_DOCUMENT_SHA_REQUIRED")
            if row["source_contract"] == "LEDGER_READ_TOOL_CONTRACT":
                if row["source_status"] != ACCESS_TO_STATUS[state]:
                    raise ContractError("LEDGER_SOURCE_STATUS_MISMATCH")
                if row["basis_mode"] is None or row["basis_sha256"] is None:
                    raise ContractError("LEDGER_SOURCE_BASIS_REQUIRED")
            elif state != "OPENED_OK" or row["source_status"] != "VALIDATED":
                raise ContractError("OBJECT_SOURCE_MUST_BE_VALIDATED")
            if state == "OPENED_OK" and row["reason_code"] is not None:
                raise ContractError("OPENED_OK_REASON_FORBIDDEN")
            if state != "OPENED_OK" and row["reason_code"] is None:
                raise ContractError("NON_OK_SOURCE_REASON_REQUIRED")
        else:
            if (
                row["source_status"] is not None
                or row["basis_mode"] is not None
                or row["basis_sha256"] is not None
                or row["source_document_sha256"] is not None
            ):
                raise ContractError("UNOPENED_SOURCE_CANNOT_CLAIM_CONTENT")
            if state == "CAPABILITY_UNAVAILABLE" and row["reason_code"] is None:
                raise ContractError("UNAVAILABLE_SOURCE_REASON_REQUIRED")
            if state in {"DIRECTORY_ONLY", "NOT_READ"} and row["reason_code"] is not None:
                raise ContractError("UNREAD_SOURCE_REASON_FORBIDDEN")
    return source_map


def _validate_scope(
    task: dict[str, Any],
    scope_confirmation: dict[str, Any],
    source_map: dict[str, dict[str, Any]],
) -> set[str]:
    result = scope_validator.validate_scope_confirmation(scope_confirmation)
    if result != scope_validator.STRUCTURAL_VALID:
        raise ContractError("SCOPE_CONFIRMATION_STRUCTURALLY_INVALID")
    scope_sources = [
        row
        for row in source_map.values()
        if row["source_contract"] == "CHAPTER_SCOPE_CONFIRMATION"
    ]
    if len(scope_sources) != 1:
        raise ContractError("UNIQUE_SCOPE_SOURCE_REQUIRED")
    source = scope_sources[0]
    expected_ref = {
        "contract": "CHAPTER_SCOPE_CONFIRMATION",
        "version": "v1",
        "scope_id": scope_confirmation["scope_id"],
        "scope_basis_sha256": scope_confirmation["scope_basis_sha256"],
    }
    if task["scope_confirmation_ref"] != expected_ref:
        raise ContractError("SCOPE_CONFIRMATION_REF_MISMATCH")
    if source["object_ref"] != scope_confirmation["scope_id"]:
        raise ContractError("SCOPE_MANIFEST_OBJECT_REF_MISMATCH")
    if source["source_document_sha256"] != scope_confirmation["scope_basis_sha256"]:
        raise ContractError("SCOPE_MANIFEST_SHA256_MISMATCH")
    if source["access_state"] != "OPENED_OK":
        raise ContractError("SCOPE_SOURCE_MUST_BE_OPENED")
    if task["truth_scope_ref"] != scope_confirmation["truth_scope_ref"]:
        raise ContractError("TASK_TRUTH_SCOPE_MISMATCH")

    if scope_confirmation["status"] == "CONFIRMED":
        if task["scope_projection"] != scope_confirmation["ccz139_handoff"]:
            raise ContractError("SCOPE_PROJECTION_MISMATCH")
    else:
        if (
            task["status"] != "STOPPED"
            or task["reason_code"] != "SCOPE_NOT_CONFIRMED"
            or task["scope_projection"] is not None
        ):
            raise ContractError("NON_CONFIRMED_SCOPE_MUST_STOP")
        return {scope_confirmation["task_ref"]["object_ref"]}

    projection = task["scope_projection"]
    return {
        projection["selected_storyline_ref"],
        projection["viewpoint_character_ref"],
        *projection["appearance_character_refs"],
        scope_confirmation["task_ref"]["object_ref"],
    }


def _validate_predecessor_binding(
    task: dict[str, Any],
    binding: dict[str, Any] | None,
    source_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if binding is None:
        raise ContractError("PREDECESSOR_BINDING_REQUIRED")
    errors = sorted(
        PREDECESSOR_BINDING_VALIDATOR.iter_errors(binding),
        key=lambda item: (list(item.absolute_path), item.message),
    )
    if errors:
        raise ContractError(
            f"PREDECESSOR_BINDING_SCHEMA_INVALID:{_schema_path(errors[0])}"
        )
    if binding["binding_basis_sha256"] != predecessor_binding_basis_sha256(binding):
        raise ContractError("PREDECESSOR_BINDING_SHA256_MISMATCH")
    expected_ref = {
        "contract": "CHAPTER_PREDECESSOR_BINDING",
        "version": "v1",
        "binding_id": binding["binding_id"],
        "binding_basis_sha256": binding["binding_basis_sha256"],
    }
    if task["predecessor_binding_ref"] != expected_ref:
        raise ContractError("PREDECESSOR_BINDING_REF_MISMATCH")
    projection = task["scope_projection"]
    if binding["truth_scope_ref"] != task["truth_scope_ref"]:
        raise ContractError("PREDECESSOR_BINDING_TRUTH_SCOPE_MISMATCH")
    if (
        binding["source_plan_version"] != projection["source_plan_version"]
        or binding["source_plan_sha256"] != projection["source_plan_sha256"]
        or binding["current_slot_ref"] != projection["slot_ref"]
        or binding["current_slot_rev"] != projection["slot_rev"]
    ):
        raise ContractError("PREDECESSOR_BINDING_CURRENT_SLOT_MISMATCH")
    sources = [
        row
        for row in source_map.values()
        if row["source_contract"] == "CHAPTER_PREDECESSOR_BINDING"
    ]
    if len(sources) != 1:
        raise ContractError("UNIQUE_PREDECESSOR_BINDING_SOURCE_REQUIRED")
    source = sources[0]
    if (
        source["access_state"] != "OPENED_OK"
        or source["object_ref"] != binding["binding_id"]
        or source["source_document_sha256"] != binding["binding_basis_sha256"]
    ):
        raise ContractError("PREDECESSOR_BINDING_MANIFEST_MISMATCH")
    if binding["chapter_position"] == "FIRST_CHAPTER":
        if (
            binding["previous_slot_ref"] is not None
            or binding["previous_settlement_sha256"] is not None
        ):
            raise ContractError("FIRST_CHAPTER_PREDECESSOR_FORBIDDEN")
    elif (
        binding["previous_slot_ref"] is None
        or binding["previous_settlement_sha256"] is None
    ):
        raise ContractError("CONTINUING_CHAPTER_PREDECESSOR_REQUIRED")
    return binding


def _previous_projection(
    settlement: dict[str, Any], c9_need_id: str | None
) -> dict[str, Any]:
    outcome = settlement["outcome"]
    handoff = settlement["next_chapter_handoff"]
    return {
        "source_contract": "CHAPTER_SETTLEMENT_SEAL",
        "source_contract_version": "v1",
        "source_slot_ref": settlement["slot_ref"],
        "settlement_sha256": settlement["settlement_sha256"],
        "target_disposition": outcome["target_disposition"],
        "actual_completion_statement_refs": [
            row["statement_id"] for row in outcome["actual_completion"]
        ],
        "key_plot_statement_refs": [
            row["statement_id"] for row in outcome["key_plot_skeleton"]
        ],
        "important_state_statement_refs": [
            row["statement_id"] for row in outcome["important_state_changes"]
        ],
        "unresolved_story_item_refs": [
            row["item_id"] for row in settlement["unresolved_story_items"]
        ],
        "handoff_mode": handoff["mode"],
        "handoff_scope_refs": handoff["scope_refs"],
        "handoff_summary": handoff["summary"],
        "provenance_seal_refs": handoff["provenance_seal_refs"],
        "ledger_coverage": [
            {"ledger_name": row["ledger_name"], "result": row["result"]}
            for row in settlement["ledger_coverage"]
        ],
        "c9_need_id": c9_need_id,
    }


def _validate_settlements(
    task: dict[str, Any],
    predecessor_binding: dict[str, Any],
    settlements: list[dict[str, Any]],
    source_map: dict[str, dict[str, Any]],
) -> set[str]:
    settlement_map: dict[str, dict[str, Any]] = {}
    for settlement in settlements:
        result = settlement_validator.validate_settlement(settlement)
        if result not in {
            settlement_validator.STRUCTURAL_VALID,
            settlement_validator.STRUCTURAL_VALID_OWNER_UNRESOLVED,
        }:
            raise ContractError("SETTLEMENT_RESULT_INVALID")
        sha = settlement["settlement_sha256"]
        if sha in settlement_map:
            raise ContractError("SETTLEMENT_SHA_DUPLICATE")
        settlement_map[sha] = settlement

    previous = task["previous_chapter_handoff"]
    opened_sources = [
        row
        for row in source_map.values()
        if row["source_contract"] == "CHAPTER_SETTLEMENT_SEAL"
        and row["access_state"] == "OPENED_OK"
    ]
    if predecessor_binding["chapter_position"] == "FIRST_CHAPTER":
        if previous is not None or opened_sources:
            raise ContractError("FIRST_CHAPTER_PREVIOUS_HANDOFF_FORBIDDEN")
        return set()
    if previous is None:
        raise ContractError("CONTINUING_CHAPTER_PREVIOUS_HANDOFF_REQUIRED")
    if len(opened_sources) != 1:
        raise ContractError("CONTINUING_CHAPTER_SETTLEMENT_SOURCE_REQUIRED")
    settlement = settlement_map.get(previous["settlement_sha256"])
    if settlement is None:
        raise ContractError("PREVIOUS_SETTLEMENT_NOT_PROVIDED")
    if settlement["claim_kind"] != "OWNER_RESOLVED_SEALED":
        raise ContractError("PREVIOUS_SETTLEMENT_OWNER_UNRESOLVED")
    if settlement["truth_scope_ref"] != task["truth_scope_ref"]:
        raise ContractError("PREVIOUS_SETTLEMENT_SCOPE_MISMATCH")
    if (
        settlement["slot_ref"] != predecessor_binding["previous_slot_ref"]
        or settlement["settlement_sha256"]
        != predecessor_binding["previous_settlement_sha256"]
    ):
        raise ContractError("PREDECESSOR_SETTLEMENT_MISMATCH")
    expected = _previous_projection(settlement, previous["c9_need_id"])
    if previous != expected:
        raise ContractError("PREVIOUS_HANDOFF_PROJECTION_MISMATCH")
    source = opened_sources[0]
    if (
        source["object_ref"] != f"settlement:{settlement['settlement_sha256']}"
        or source["source_document_sha256"] != settlement["settlement_sha256"]
    ):
        raise ContractError("PREVIOUS_SETTLEMENT_MANIFEST_MISMATCH")
    return {
        *previous["actual_completion_statement_refs"],
        *previous["key_plot_statement_refs"],
        *previous["important_state_statement_refs"],
        *previous["unresolved_story_item_refs"],
        *previous["handoff_scope_refs"],
    }


def _ledger_entry_maps(response: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    data = response["data"] or {}
    entries: list[dict[str, Any]] = []
    if isinstance(data, dict):
        entries.extend(data.get("entries", []))
        entries.extend(data.get("confirmed_facts", []))
    entry_map = {row["id"]: row for row in entries if isinstance(row, dict) and "id" in row}
    source_rows = response["receipt"]["source_manifest"]
    source_entry_map = {
        row["stable_id"]: row
        for row in source_rows
        if row.get("logical_ledger_name") == "事实账"
    }
    return entry_map, source_entry_map


def _validate_ledger_sources(
    task: dict[str, Any],
    responses: list[dict[str, Any]],
    source_map: dict[str, dict[str, Any]],
    allowed_relation_refs: set[str],
) -> None:
    response_map: dict[str, dict[str, Any]] = {}
    for response in responses:
        if response.get("limits", {}).get("truncated") is True:
            raise ContractError("TRUNCATED_LEDGER_RESPONSE_FORBIDDEN")
        ledger_validator.validate_document(response)
        request_id = response["request_id"]
        if request_id in response_map:
            raise ContractError("LEDGER_RESPONSE_ID_DUPLICATE")
        response_map[request_id] = response

    for source in source_map.values():
        if source["source_contract"] != "LEDGER_READ_TOOL_CONTRACT":
            continue
        if source["access_state"] not in OPENED_STATES:
            continue
        response = response_map.get(source["object_ref"])
        if response is None:
            raise ContractError("OPENED_LEDGER_RESPONSE_NOT_PROVIDED")
        if source["source_status"] != response["status"]:
            raise ContractError("LEDGER_MANIFEST_STATUS_MISMATCH")
        if source["reason_code"] != response["reason_code"]:
            raise ContractError("LEDGER_MANIFEST_REASON_MISMATCH")
        if source["basis_mode"] != response["basis_mode"]:
            raise ContractError("LEDGER_MANIFEST_BASIS_MODE_MISMATCH")
        if source["basis_sha256"] != response["receipt"]["basis_sha256"]:
            raise ContractError("LEDGER_MANIFEST_BASIS_SHA_MISMATCH")
        if source["source_document_sha256"] != sha256_json(response):
            raise ContractError("LEDGER_MANIFEST_DOCUMENT_SHA_MISMATCH")
        if (
            response["receipt"]["author_id"]
            != task["truth_scope_ref"]["principal_author_id"]
            or response["receipt"]["project_id"]
            != task["truth_scope_ref"]["project_id"]
        ):
            raise ContractError("LEDGER_RESPONSE_SCOPE_MISMATCH")
    _unique_map(task["selected_fact_refs"], "fact_ref", "FACT_REF")
    for fact in task["selected_fact_refs"]:
        source = source_map.get(fact["read_source_id"])
        if source is None or source["source_contract"] != "LEDGER_READ_TOOL_CONTRACT":
            raise ContractError("FACT_READ_SOURCE_INVALID")
        if source["access_state"] != "OPENED_OK":
            raise ContractError("FACT_SOURCE_MUST_BE_OPENED_OK")
        response = response_map.get(fact["source_response_ref"])
        if response is None or source["object_ref"] != response["request_id"]:
            raise ContractError("FACT_RESPONSE_REF_MISMATCH")
        entry_map, source_entry_map = _ledger_entry_maps(response)
        entry = entry_map.get(fact["fact_ref"])
        source_entry = source_entry_map.get(fact["fact_ref"])
        if entry is None or source_entry is None:
            raise ContractError("FACT_NOT_IN_OPENED_RESPONSE")
        if source_entry["revision"] != fact["fact_revision"]:
            raise ContractError("FACT_REVISION_MISMATCH")
        if source_entry["logical_content_sha256"] != fact["fact_sha256"]:
            raise ContractError("FACT_SHA256_MISMATCH")
        chapter_ref = entry.get("chapter_revision_ref")
        if chapter_ref is None:
            raise ContractError("FACT_CHAPTER_REVISION_REQUIRED")
        if (
            chapter_ref["chapter_id"] != fact["chapter_slot_ref"]
            or chapter_ref["revision_no"] != fact["chapter_revision"]
        ):
            raise ContractError("FACT_CHAPTER_REVISION_MISMATCH")
        expected_basis_refs = {
            task["scope_confirmation_ref"]["scope_id"],
            fact["source_response_ref"],
        }
        if set(fact["selection_basis_refs"]) != expected_basis_refs:
            raise ContractError("FACT_SELECTION_BASIS_REFS_MISMATCH")
        if not set(fact["relation_scope_refs"]).issubset(allowed_relation_refs):
            raise ContractError("FACT_RELATION_OUTSIDE_CONFIRMED_SCOPE")


def _validate_opened_object_sources(
    source_map: dict[str, dict[str, Any]],
    summary_bundles: list[dict[str, Any]],
    provenance_seals: list[dict[str, Any]],
    truth_scope_ref: dict[str, Any],
) -> None:
    summary_map: dict[str, dict[str, Any]] = {}
    for bundle in summary_bundles:
        if set(bundle) not in ({"document", "settlements"}, {"document", "settlements", "summaries"}):
            raise ContractError("SUMMARY_VALIDATION_BUNDLE_SHAPE_INVALID")
        document = bundle["document"]
        result = summary_validator.validate_summary(
            document,
            bundle["settlements"],
            bundle.get("summaries", []),
        )
        if result not in {
            summary_validator.STRUCTURAL_VALID,
            summary_validator.STRUCTURAL_VALID_OWNER_UNRESOLVED,
        }:
            raise ContractError("SUMMARY_RESULT_INVALID")
        sha = document["summary_sha256"]
        if sha in summary_map:
            raise ContractError("SUMMARY_SHA_DUPLICATE")
        summary_map[sha] = document

    seal_map: dict[str, dict[str, Any]] = {}
    for seal in provenance_seals:
        result = provenance_validator.validate_seal(seal)
        if result not in {
            provenance_validator.STRUCTURAL_VALID,
            provenance_validator.STRUCTURAL_VALID_OWNER_UNRESOLVED,
        }:
            raise ContractError("PROVENANCE_RESULT_INVALID")
        sha = seal["seal_sha256"]
        if sha in seal_map:
            raise ContractError("PROVENANCE_SHA_DUPLICATE")
        seal_map[sha] = seal

    for source in source_map.values():
        if source["access_state"] not in OPENED_STATES:
            continue
        contract = source["source_contract"]
        if contract == "CHAPTER_LAYERED_SUMMARY":
            sha = source["source_document_sha256"]
            if sha not in summary_map or source["object_ref"] != f"summary:{sha}":
                raise ContractError("OPENED_SUMMARY_SOURCE_NOT_PROVIDED")
            if summary_map[sha]["truth_scope_ref"] != truth_scope_ref:
                raise ContractError("OPENED_SUMMARY_SCOPE_MISMATCH")
        elif contract == "TRACEABLE_PROVENANCE_SEAL":
            sha = source["source_document_sha256"]
            if sha not in seal_map or source["object_ref"] != f"provenance:{sha}":
                raise ContractError("OPENED_PROVENANCE_SOURCE_NOT_PROVIDED")
            if seal_map[sha]["truth_scope_ref"] != truth_scope_ref:
                raise ContractError("OPENED_PROVENANCE_SCOPE_MISMATCH")


def _validate_manifest_authorization(
    source_map: dict[str, dict[str, Any]], allowed_refs: set[str]
) -> None:
    for source in source_map.values():
        if not set(source["authorized_scope_refs"]).issubset(allowed_refs):
            raise ContractError("SOURCE_AUTHORIZATION_OUTSIDE_CONFIRMED_SCOPE")


def _validate_box_directory(
    task: dict[str, Any], source_map: dict[str, dict[str, Any]], allowed_refs: set[str]
) -> None:
    boxes = task["box_directory"]
    _unique_map(boxes, "box_id", "BOX_ID")
    for box in boxes:
        if not set(box["relation_scope_refs"]).issubset(allowed_refs):
            raise ContractError("BOX_RELATION_OUTSIDE_CONFIRMED_SCOPE")
        availability = box["availability"]
        source_id = box["source_id"]
        source = source_map.get(source_id) if source_id is not None else None
        if task["status"] == "STOPPED":
            if (
                source_id is not None
                or box["logical_open_ref"] is not None
                or box["c9_need_ids"]
                or availability not in {"CAPABILITY_UNAVAILABLE", "MASKED"}
                or box["reason_code"] is None
            ):
                raise ContractError("STOPPED_BOX_CANNOT_EXPOSE_RETRIEVAL_ENTRY")
            continue
        expected_state = {
            "OPENED": OPENED_STATES,
            "DIRECTORY_ONLY": {"DIRECTORY_ONLY"},
            "NOT_READ": {"NOT_READ"},
            "CAPABILITY_UNAVAILABLE": {"CAPABILITY_UNAVAILABLE"},
        }
        if availability == "MASKED":
            if (
                source_id is not None
                or box["logical_open_ref"] is not None
                or box["c9_need_ids"]
                or box["reason_code"] != "UNAUTHORIZED"
            ):
                raise ContractError("MASKED_BOX_EXISTENCE_LEAK")
            continue
        if source is None or source["access_state"] not in expected_state[availability]:
            raise ContractError("BOX_SOURCE_ACCESS_STATE_MISMATCH")
        if availability in {"CAPABILITY_UNAVAILABLE"}:
            if box["logical_open_ref"] is not None or box["reason_code"] is None:
                raise ContractError("UNAVAILABLE_BOX_SHAPE_INVALID")
        else:
            if box["logical_open_ref"] is None or box["reason_code"] is not None:
                raise ContractError("AVAILABLE_BOX_DIRECTORY_SHAPE_INVALID")


def _validate_source_coverage(task: dict[str, Any]) -> None:
    coverage = task["read_coverage"]
    expected = {
        "opened_source_ids": sorted(
            row["source_id"]
            for row in task["source_manifest"]
            if row["access_state"] in OPENED_STATES
        ),
        "directory_only_source_ids": sorted(
            row["source_id"]
            for row in task["source_manifest"]
            if row["access_state"] == "DIRECTORY_ONLY"
        ),
        "not_read_source_ids": sorted(
            row["source_id"]
            for row in task["source_manifest"]
            if row["access_state"] == "NOT_READ"
        ),
        "unavailable_source_ids": sorted(
            row["source_id"]
            for row in task["source_manifest"]
            if row["access_state"] == "CAPABILITY_UNAVAILABLE"
        ),
    }
    for key, value in expected.items():
        if coverage[key] != value:
            raise ContractError(f"READ_COVERAGE_PARTITION_MISMATCH:{key}")
    if coverage["selected_fact_count"] != len(task["selected_fact_refs"]):
        raise ContractError("SELECTED_FACT_COUNT_MISMATCH")
    missing_hard = sorted(
        box["box_id"]
        for box in task["box_directory"]
        if box["obligation_tier"] == "HARD"
        and box["availability"] in {"CAPABILITY_UNAVAILABLE", "MASKED"}
    )
    if coverage["missing_required_box_ids"] != missing_hard:
        raise ContractError("MISSING_REQUIRED_BOXES_MISMATCH")
    expected_complete = not missing_hard and task["scope_projection"] is not None
    if coverage["complete_for_required"] != expected_complete:
        raise ContractError("REQUIRED_COVERAGE_FLAG_MISMATCH")


def _validate_need_shape(need: dict[str, Any]) -> None:
    errors = sorted(
        C9_NEED_VALIDATOR.iter_errors(need),
        key=lambda item: (list(item.absolute_path), item.message),
    )
    if errors:
        raise ContractError(f"C9_SOURCE_NEED_INVALID:{_schema_path(errors[0])}")


def _validate_c9_needs(
    task: dict[str, Any], source_map: dict[str, dict[str, Any]]
) -> None:
    needs = task["c9_source_needs"]
    need_map = _unique_map(needs, "need_id", "C9_NEED_ID")
    for index, need in enumerate(needs):
        _validate_need_shape(need)
        if need["source_contract_version"] != SOURCE_VERSIONS[need["source_contract"]]:
            raise ContractError("C9_SOURCE_CONTRACT_VERSION_MISMATCH")
        parent_id = need["parent_need_id"]
        if parent_id is None:
            if need["evidence_layer"] != "LEDGER_OBJECT":
                raise ContractError("ROOT_NEED_MUST_BE_LEDGER_OBJECT")
            if need["trigger_provenance"] is not None:
                raise ContractError("ROOT_NEED_TRIGGER_PROVENANCE_FORBIDDEN")
            continue
        parent = need_map.get(parent_id)
        if parent is None:
            raise ContractError("C9_PARENT_NEED_NOT_FOUND")
        expected_parent_layer = {
            "FORMATION_BASIS": "LEDGER_OBJECT",
            "ORIGINAL_EVIDENCE": "FORMATION_BASIS",
        }.get(need["evidence_layer"])
        if expected_parent_layer is None or parent["evidence_layer"] != expected_parent_layer:
            raise ContractError("C9_EVIDENCE_LAYER_CHAIN_INVALID")
        if OBLIGATION_RANK[need["obligation_tier"]] < OBLIGATION_RANK[parent["obligation_tier"]]:
            raise ContractError("C9_CHILD_OBLIGATION_ESCALATION")
        provenance = need["trigger_provenance"]
        if (
            provenance is None
            or provenance["parent_need_id"] != parent_id
            or provenance["decision_code"] != need["expansion_trigger"]
        ):
            raise ContractError("C9_TRIGGER_PROVENANCE_MISMATCH")

    try:
        c9_core._validate_need_order({"source_needs": needs})
    except c9_core.C9RetrievalError as error:
        raise ContractError(f"C9_NEED_ORDER_INVALID:{error}") from error

    expected_ids: list[str] = []
    previous = task["previous_chapter_handoff"]
    if previous is not None and previous["c9_need_id"] is not None:
        expected_ids.append(previous["c9_need_id"])
    expected_ids.extend(row["c9_need_id"] for row in task["selected_fact_refs"])
    for box in task["box_directory"]:
        expected_ids.extend(box["c9_need_ids"])
    if len(expected_ids) != len(set(expected_ids)):
        raise ContractError("TASK_MATERIAL_NEED_ID_DUPLICATE")
    if set(expected_ids) != set(need_map):
        raise ContractError("TASK_MATERIAL_TO_C9_NEED_MAPPING_MISMATCH")

    for fact in task["selected_fact_refs"]:
        need = need_map[fact["c9_need_id"]]
        if (
            need["source_contract"] != "LEDGER_READ_TOOL_CONTRACT"
            or need["object_ref"] != fact["fact_ref"]
            or need["obligation_tier"] != fact["obligation_tier"]
        ):
            raise ContractError("FACT_C9_NEED_PROJECTION_MISMATCH")
    if previous is not None and previous["c9_need_id"] is not None:
        need = need_map[previous["c9_need_id"]]
        if (
            need["source_contract"] != "CHAPTER_SETTLEMENT_SEAL"
            or need["object_ref"] != f"settlement:{previous['settlement_sha256']}"
            or need["obligation_tier"] != "HARD"
        ):
            raise ContractError("PREVIOUS_HANDOFF_C9_NEED_MISMATCH")
    elif previous is not None and task["status"] != "STOPPED":
        raise ContractError("PREVIOUS_HANDOFF_C9_NEED_REQUIRED")
    box_map = {row["box_id"]: row for row in task["box_directory"]}
    for box in box_map.values():
        for need_id in box["c9_need_ids"]:
            need = need_map[need_id]
            if box["logical_open_ref"] != need["object_ref"]:
                raise ContractError("BOX_C9_NEED_OBJECT_REF_MISMATCH")
            if box["obligation_tier"] != need["obligation_tier"]:
                raise ContractError("BOX_C9_NEED_OBLIGATION_MISMATCH")
            source = source_map.get(box["source_id"])
            if source is None or source["source_contract"] != need["source_contract"]:
                raise ContractError("BOX_C9_NEED_SOURCE_CONTRACT_MISMATCH")


def _validate_status(task: dict[str, Any]) -> None:
    status = task["status"]
    reason = task["reason_code"]
    coverage = task["read_coverage"]
    unavailable_optional = any(
        box["availability"] in {"CAPABILITY_UNAVAILABLE", "MASKED"}
        and box["obligation_tier"] != "HARD"
        for box in task["box_directory"]
    )
    if status == "READY_FOR_THIN_CARD":
        if reason is not None or not coverage["complete_for_required"] or unavailable_optional:
            raise ContractError("READY_STATUS_SHAPE_INVALID")
    elif status == "READY_WITH_GAPS":
        if (
            reason != "OPTIONAL_SOURCES_UNAVAILABLE"
            or not coverage["complete_for_required"]
            or not unavailable_optional
        ):
            raise ContractError("READY_WITH_GAPS_SHAPE_INVALID")
    else:
        if reason is None or reason == "OPTIONAL_SOURCES_UNAVAILABLE":
            raise ContractError("STOPPED_REASON_INVALID")
        if task["selected_fact_refs"] or task["c9_source_needs"]:
            raise ContractError("STOPPED_TASK_CANNOT_EXPOSE_EXECUTABLE_MATERIAL")
        if any(
            row["access_state"] in {"DIRECTORY_ONLY", "NOT_READ"}
            for row in task["source_manifest"]
        ):
            raise ContractError("STOPPED_SOURCE_CANNOT_EXPOSE_RETRIEVAL_ENTRY")
        if reason not in {"SCOPE_NOT_CONFIRMED", "SCOPE_MISMATCH"} and coverage["complete_for_required"]:
            raise ContractError("STOPPED_TASK_REQUIRED_GAP_MISSING")

    blocking_sources = [
        row
        for row in task["source_manifest"]
        if row["access_state"] in {"OPENED_REJECTED", "OPENED_ERROR"}
    ]
    if blocking_sources:
        if status != "STOPPED":
            raise ContractError("FAILED_SOURCE_MUST_STOP")
        source_reasons = {row["reason_code"] for row in blocking_sources}
        if reason not in source_reasons:
            raise ContractError("STOPPED_REASON_DOES_NOT_MATCH_SOURCE")


def validate_task_bundle(bundle: Any) -> str:
    """Validate one task and its explicit evidence objects without I/O."""

    if not isinstance(bundle, dict) or set(bundle) != {
        "task",
        "scope_confirmation",
        "predecessor_binding",
        "settlements",
        "summaries",
        "ledger_responses",
        "provenance_seals",
    }:
        raise ContractError("VALIDATION_BUNDLE_SHAPE_INVALID")
    task = bundle["task"]
    _validate_schema(task)
    _walk_forbidden_content(task)
    source_map = _validate_manifest_shape(task)
    allowed_refs = _validate_scope(task, bundle["scope_confirmation"], source_map)
    if task["scope_projection"] is None:
        if (
            task["predecessor_binding_ref"] is not None
            or bundle["predecessor_binding"] is not None
            or task["previous_chapter_handoff"] is not None
            or task["selected_fact_refs"]
            or task["box_directory"]
            or task["c9_source_needs"]
            or len(task["source_manifest"]) != 1
            or bundle["settlements"]
            or bundle["summaries"]
            or bundle["ledger_responses"]
            or bundle["provenance_seals"]
        ):
            raise ContractError("NON_CONFIRMED_SCOPE_STOP_MUST_BE_EMPTY")
        _validate_manifest_authorization(source_map, allowed_refs)
        _validate_source_coverage(task)
        _validate_status(task)
        if task["task_basis_sha256"] != task_basis_sha256(task):
            raise ContractError("TASK_BASIS_SHA256_MISMATCH")
        return STRUCTURAL_VALID

    predecessor_binding = _validate_predecessor_binding(
        task, bundle["predecessor_binding"], source_map
    )
    allowed_refs.update(
        _validate_settlements(
            task, predecessor_binding, bundle["settlements"], source_map
        )
    )
    _validate_manifest_authorization(source_map, allowed_refs)
    _validate_opened_object_sources(
        source_map,
        bundle["summaries"],
        bundle["provenance_seals"],
        task["truth_scope_ref"],
    )
    _validate_ledger_sources(
        task, bundle["ledger_responses"], source_map, allowed_refs
    )
    _validate_box_directory(task, source_map, allowed_refs)
    _validate_source_coverage(task)
    _validate_c9_needs(task, source_map)
    _validate_status(task)
    if task["task_basis_sha256"] != task_basis_sha256(task):
        raise ContractError("TASK_BASIS_SHA256_MISMATCH")
    return STRUCTURAL_VALID


def _source_manifest_row(
    source_id: str,
    source_contract: str,
    object_ref: str,
    access_state: str,
    *,
    source_status: str | None = None,
    reason_code: str | None = None,
    basis_mode: str | None = None,
    basis_sha256: str | None = None,
    document_sha256: str | None = None,
    authorized_scope_refs: list[str] | None = None,
) -> dict[str, Any]:
    versions = {
        "CHAPTER_SCOPE_CONFIRMATION": "v1",
        "CHAPTER_PREDECESSOR_BINDING": "v1",
        "CHAPTER_SETTLEMENT_SEAL": "v1",
        "CHAPTER_LAYERED_SUMMARY": "v1",
        "LEDGER_READ_TOOL_CONTRACT": "ledger-read-tool-contract-v1",
        "TRACEABLE_PROVENANCE_SEAL": "v1",
    }
    return {
        "source_id": source_id,
        "source_contract": source_contract,
        "source_contract_version": versions[source_contract],
        "object_ref": object_ref,
        "access_state": access_state,
        "source_status": source_status,
        "reason_code": reason_code,
        "basis_mode": basis_mode,
        "basis_sha256": basis_sha256,
        "source_document_sha256": document_sha256,
        "authorized_scope_refs": authorized_scope_refs or [],
    }


def _need(
    need_id: str,
    object_ref: str,
    source_contract: str,
    *,
    obligation: str = "HARD",
    layer: str = "LEDGER_OBJECT",
    parent: str | None = None,
    trigger: str = "INITIAL",
    rank: int | None = None,
) -> dict[str, Any]:
    provenance = None
    if parent is not None:
        decision = {"need_id": need_id, "parent_need_id": parent, "trigger": trigger}
        provenance = {
            "decision_contract": "CHAPTER_CONTEXT_RETRIEVAL_TASK",
            "decision_contract_version": "v1",
            "decision_object_ref": f"decision:{need_id}",
            "decision_object_sha256": sha256_json(decision),
            "producer_component_id": "CCZ139_CONTRACT_FIXTURE_BUILDER",
            "decision_code": trigger,
            "parent_need_id": parent,
        }
    return {
        "need_id": need_id,
        "evidence_layer": layer,
        "parent_need_id": parent,
        "source_contract": source_contract,
        "source_contract_version": SOURCE_VERSIONS[source_contract],
        "object_ref": object_ref,
        "actuality_class": "CURRENT_FACT_OR_STATE",
        "obligation_tier": obligation,
        "selection_rank": rank,
        "task_relation": f"合成任务需要 {need_id}",
        "estimated_tokens": 24,
        "recall_disposition": "RETRIEVABLE",
        "recall_handle": f"recall:{need_id}",
        "expansion_trigger": trigger,
        "trigger_provenance": provenance,
    }


def _scope_document(transition: str, *, delegated: bool = False) -> dict[str, Any]:
    return scope_validator._confirmed_document(
        transition,
        delegated=delegated,
        second_storyline=transition != "CONTINUE_CURRENT",
    )


def _fact_response() -> dict[str, Any]:
    fact = {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": "f0001",
        "chapter_id": "c01",
        "text": "合成事实，不进入任务单。",
        "quote": "",
        "status": "confirmed",
        "source": "CCZ139_SYNTHETIC",
        "note": "",
        "added_at": "2026-09-03 10:01:00",
        "chapter_revision_ref": {
            "chapter_id": "c01",
            "revision_no": 1,
            "revision_text_sha256": "d" * 64,
        },
        "anchor_ref": None,
        "anchor_state": "LEGACY_UNVERIFIED",
        "recheck": None,
    }
    source = {
        "source_kind": "ledger_entry",
        "source_contract": "C4_FACT_QUERY",
        "source_contract_version": "v1",
        "logical_ledger_name": "事实账",
        "object_type": "fact_record",
        "stable_id": "f0001",
        "revision": "workspace-facts-v1",
        "logical_content_sha256": sha256_json(fact),
        "role": "requested_entry",
        "binding_mode": "resolved_at_read",
        "retired_notice": False,
        "compiler_version": None,
        "input_basis_sha256": None,
    }
    response = {
        "contract": "LEDGER_READ_RESPONSE",
        "version": "ledger-read-tool-contract-v1",
        "status": "OK",
        "reason_code": None,
        "message": "已读取 1 条合成事实。",
        "request_id": "REQ-FACT-0001",
        "tool": "get_ledger_entries_by_ref",
        "basis_mode": "current_at_start",
        "data": {"entries": [fact]},
        "empty_scope": None,
        "receipt": {
            "author_id": "AUTHOR-0001",
            "project_id": "PROJECT-0001",
            "permission_policy_version": "permission-policy-v1",
            "tool_contract_version": "ledger-read-tool-contract-v1",
            "storage_generation": "json-v1",
            "capability_snapshot_id": "CAP-0001",
            "source_manifest": [source],
            "basis_sha256": "0" * 64,
        },
        "limits": {
            "policy_version": "limit-policy-v1",
            "business_items": 1,
            "response_bytes": 1024,
            "truncated": False,
        },
    }
    response["receipt"]["basis_sha256"] = ledger_validator.basis_sha256(response)
    return response


def _empty_chapter_response() -> dict[str, Any]:
    response = copy.deepcopy(
        next(
            row["document"]
            for row in ledger_validator.load_fixtures()
            if row["case_id"] == "LR-VALID-08"
        )
    )
    response["receipt"]["author_id"] = "AUTHOR-0001"
    response["receipt"]["project_id"] = "PROJECT-0001"
    response["receipt"]["basis_sha256"] = ledger_validator.basis_sha256(response)
    return response


def _box(
    box_id: str,
    kind: str,
    source_id: str | None,
    relation_ref: str,
    availability: str,
    obligation: str,
    logical_open_ref: str | None,
    need_ids: list[str],
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "box_id": box_id,
        "box_kind": kind,
        "source_id": source_id,
        "relation_scope_refs": [relation_ref],
        "expected_material_kinds": [kind],
        "availability": availability,
        "reason_code": reason,
        "obligation_tier": obligation,
        "logical_open_ref": logical_open_ref,
        "c9_need_ids": need_ids,
    }


def _coverage(task: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(
        box["box_id"]
        for box in task["box_directory"]
        if box["obligation_tier"] == "HARD"
        and box["availability"] in {"CAPABILITY_UNAVAILABLE", "MASKED"}
    )
    return {
        "opened_source_ids": sorted(
            row["source_id"]
            for row in task["source_manifest"]
            if row["access_state"] in OPENED_STATES
        ),
        "directory_only_source_ids": sorted(
            row["source_id"]
            for row in task["source_manifest"]
            if row["access_state"] == "DIRECTORY_ONLY"
        ),
        "not_read_source_ids": sorted(
            row["source_id"]
            for row in task["source_manifest"]
            if row["access_state"] == "NOT_READ"
        ),
        "unavailable_source_ids": sorted(
            row["source_id"]
            for row in task["source_manifest"]
            if row["access_state"] == "CAPABILITY_UNAVAILABLE"
        ),
        "selected_fact_count": len(task["selected_fact_refs"]),
        "complete_for_required": not missing,
        "missing_required_box_ids": missing,
    }


def _predecessor_binding(
    scope: dict[str, Any], settlement: dict[str, Any] | None
) -> dict[str, Any]:
    projection = scope["ccz139_handoff"]
    return seal_predecessor_binding(
        {
            "contract": "CHAPTER_PREDECESSOR_BINDING",
            "version": "v1",
            "binding_id": "PREDECESSOR-BINDING-0001",
            "truth_scope_ref": copy.deepcopy(scope["truth_scope_ref"]),
            "source_plan_version": projection["source_plan_version"],
            "source_plan_sha256": projection["source_plan_sha256"],
            "current_slot_ref": projection["slot_ref"],
            "current_slot_rev": projection["slot_rev"],
            "chapter_position": (
                "FIRST_CHAPTER" if settlement is None else "CONTINUING_CHAPTER"
            ),
            "previous_slot_ref": None if settlement is None else settlement["slot_ref"],
            "previous_settlement_sha256": (
                None if settlement is None else settlement["settlement_sha256"]
            ),
            "binding_basis_sha256": "0" * 64,
        }
    )


def _base_bundle(
    *,
    transition: str = "CONTINUE_CURRENT",
    first_chapter: bool = False,
    delegated: bool = False,
    empty_response: bool = False,
    optional_gap: bool = False,
    hard_gap: bool = False,
    three_layers: bool = False,
) -> dict[str, Any]:
    scope = _scope_document(transition, delegated=delegated)
    settlement = settlement_validator.build_base_document("resolved_full")
    response = _empty_chapter_response() if empty_response else _fact_response()
    projection = scope["ccz139_handoff"]
    relation_ref = projection["selected_storyline_ref"]
    predecessor_binding = _predecessor_binding(
        scope, None if first_chapter else settlement
    )

    manifest = [
        _source_manifest_row(
            "SOURCE-SCOPE",
            "CHAPTER_SCOPE_CONFIRMATION",
            scope["scope_id"],
            "OPENED_OK",
            source_status="VALIDATED",
            document_sha256=scope["scope_basis_sha256"],
            authorized_scope_refs=[relation_ref],
        ),
        _source_manifest_row(
            "SOURCE-PREDECESSOR",
            "CHAPTER_PREDECESSOR_BINDING",
            predecessor_binding["binding_id"],
            "OPENED_OK",
            source_status="VALIDATED",
            document_sha256=predecessor_binding["binding_basis_sha256"],
            authorized_scope_refs=[relation_ref],
        ),
        _source_manifest_row(
            "SOURCE-OLDER-SUMMARY",
            "CHAPTER_LAYERED_SUMMARY",
            "SUMMARY-PHASE-0001",
            "DIRECTORY_ONLY",
            authorized_scope_refs=[relation_ref],
        ),
    ]
    needs: list[dict[str, Any]] = []
    previous = None
    settlements: list[dict[str, Any]] = []
    if not first_chapter:
        manifest.append(
            _source_manifest_row(
                "SOURCE-SETTLEMENT",
                "CHAPTER_SETTLEMENT_SEAL",
                f"settlement:{settlement['settlement_sha256']}",
                "OPENED_OK",
                source_status="VALIDATED",
                document_sha256=settlement["settlement_sha256"],
                authorized_scope_refs=[relation_ref],
            )
        )
        previous = _previous_projection(
            settlement, None if hard_gap else "NEED-PREVIOUS"
        )
        settlements = [settlement]
        if not hard_gap:
            needs.append(
                _need(
                    "NEED-PREVIOUS",
                    f"settlement:{settlement['settlement_sha256']}",
                    "CHAPTER_SETTLEMENT_SEAL",
                    rank=None,
                )
            )

    facts: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    if not hard_gap:
        state = {
            "OK": "OPENED_OK",
            "EMPTY": "OPENED_EMPTY",
            "REJECTED": "OPENED_REJECTED",
            "ERROR": "OPENED_ERROR",
        }[response["status"]]
        manifest.append(
            _source_manifest_row(
                "SOURCE-FACT-READ",
                "LEDGER_READ_TOOL_CONTRACT",
                response["request_id"],
                state,
                source_status=response["status"],
                reason_code=response["reason_code"],
                basis_mode=response["basis_mode"],
                basis_sha256=response["receipt"]["basis_sha256"],
                document_sha256=sha256_json(response),
                authorized_scope_refs=[relation_ref],
            )
        )
        responses = [response]
        if response["status"] == "OK":
            source_entry = response["receipt"]["source_manifest"][0]
            fact = response["data"]["entries"][0]
            facts = [
                {
                    "fact_ref": fact["id"],
                    "ledger_name": "事实账",
                    "read_source_id": "SOURCE-FACT-READ",
                    "source_response_ref": response["request_id"],
                    "fact_revision": source_entry["revision"],
                    "fact_sha256": source_entry["logical_content_sha256"],
                    "chapter_slot_ref": fact["chapter_revision_ref"]["chapter_id"],
                    "chapter_revision": fact["chapter_revision_ref"]["revision_no"],
                    "relation_scope_refs": [relation_ref],
                    "selection_basis_refs": [scope["scope_id"], response["request_id"]],
                    "fact_summary": "合成事实与当前任务范围直接相关。",
                    "obligation_tier": "HARD",
                    "c9_need_id": "NEED-FACT-f0001",
                }
            ]
            needs.append(
                _need(
                    "NEED-FACT-f0001",
                    "f0001",
                    "LEDGER_READ_TOOL_CONTRACT",
                    rank=None,
                )
            )

    boxes = [
        _box(
            "BOX-OLDER-SUMMARY",
            "OLDER_CHAPTER_SUMMARY",
            "SOURCE-OLDER-SUMMARY",
            relation_ref,
            "DIRECTORY_ONLY",
            "SHOULD",
            "SUMMARY-PHASE-0001",
            ["NEED-BOX-OLDER"],
        )
    ]
    if not hard_gap:
        needs.append(
            _need(
                "NEED-BOX-OLDER",
                "SUMMARY-PHASE-0001",
                "CHAPTER_LAYERED_SUMMARY",
                obligation="SHOULD",
                rank=len(needs),
            )
        )

    if optional_gap:
        manifest.append(
            _source_manifest_row(
                "SOURCE-CHARACTER",
                "LEDGER_READ_TOOL_CONTRACT",
                "CAPABILITY-CHARACTER-STATE",
                "CAPABILITY_UNAVAILABLE",
                reason_code="CAPABILITY_UNAVAILABLE",
                authorized_scope_refs=[projection["viewpoint_character_ref"]],
            )
        )
        boxes.append(
            _box(
                "BOX-CHARACTER",
                "CHARACTER_STATE",
                "SOURCE-CHARACTER",
                projection["viewpoint_character_ref"],
                "CAPABILITY_UNAVAILABLE",
                "HARD" if hard_gap else "SHOULD",
                None,
                [],
                "CAPABILITY_UNAVAILABLE",
            )
        )
    elif hard_gap:
        boxes.append(
            _box(
                "BOX-CHARACTER",
                "CHARACTER_STATE",
                None,
                projection["viewpoint_character_ref"],
                "CAPABILITY_UNAVAILABLE",
                "HARD",
                None,
                [],
                "CAPABILITY_UNAVAILABLE",
            )
        )

    if three_layers:
        manifest.extend(
            [
                _source_manifest_row(
                    "SOURCE-FORMATION",
                    "TRACEABLE_PROVENANCE_SEAL",
                    "SEAL-FORMATION-0001",
                    "DIRECTORY_ONLY",
                    authorized_scope_refs=[relation_ref],
                ),
                _source_manifest_row(
                    "SOURCE-ORIGINAL",
                    "LEDGER_READ_TOOL_CONTRACT",
                    "ORIGINAL-EVIDENCE-0001",
                    "DIRECTORY_ONLY",
                    authorized_scope_refs=[relation_ref],
                ),
            ]
        )
        manifest = sorted(manifest, key=lambda row: row["source_id"])
        formation_need = _need(
            "NEED-FORMATION",
            "SEAL-FORMATION-0001",
            "TRACEABLE_PROVENANCE_SEAL",
            obligation="SHOULD",
            layer="FORMATION_BASIS",
            parent="NEED-FACT-f0001",
            trigger="AUDIT_REQUIRED",
            rank=len(needs),
        )
        original_need = _need(
            "NEED-ORIGINAL",
            "ORIGINAL-EVIDENCE-0001",
            "LEDGER_READ_TOOL_CONTRACT",
            obligation="MAY",
            layer="ORIGINAL_EVIDENCE",
            parent="NEED-FORMATION",
            trigger="DOWNSTREAM_REQUESTED_MORE",
            rank=len(needs) + 1,
        )
        needs.extend([formation_need, original_need])
        boxes.extend(
            [
                _box(
                    "BOX-FORMATION",
                    "FORMATION_BASIS",
                    "SOURCE-FORMATION",
                    relation_ref,
                    "DIRECTORY_ONLY",
                    "SHOULD",
                    "SEAL-FORMATION-0001",
                    ["NEED-FORMATION"],
                ),
                _box(
                    "BOX-ORIGINAL",
                    "ORIGINAL_EVIDENCE",
                    "SOURCE-ORIGINAL",
                    relation_ref,
                    "DIRECTORY_ONLY",
                    "MAY",
                    "ORIGINAL-EVIDENCE-0001",
                    ["NEED-ORIGINAL"],
                ),
            ]
        )

    status = "READY_FOR_THIN_CARD"
    reason = None
    if optional_gap:
        status = "READY_WITH_GAPS"
        reason = "OPTIONAL_SOURCES_UNAVAILABLE"
    if hard_gap:
        status = "STOPPED"
        reason = "REQUIRED_SOURCE_UNAVAILABLE"
        facts = []
        needs = []
        manifest = [
            row
            for row in manifest
            if row["source_id"]
            in {"SOURCE-SCOPE", "SOURCE-PREDECESSOR", "SOURCE-SETTLEMENT"}
        ]
        boxes = [row for row in boxes if row["box_id"] == "BOX-CHARACTER"]

    task = {
        "contract": "CHAPTER_CONTEXT_RETRIEVAL_TASK",
        "version": "v1",
        "retrieval_task_id": "RETRIEVAL-TASK-0001",
        "truth_scope_ref": copy.deepcopy(scope["truth_scope_ref"]),
        "predecessor_binding_ref": {
            "contract": "CHAPTER_PREDECESSOR_BINDING",
            "version": "v1",
            "binding_id": predecessor_binding["binding_id"],
            "binding_basis_sha256": predecessor_binding["binding_basis_sha256"],
        },
        "status": status,
        "reason_code": reason,
        "scope_confirmation_ref": {
            "contract": "CHAPTER_SCOPE_CONFIRMATION",
            "version": "v1",
            "scope_id": scope["scope_id"],
            "scope_basis_sha256": scope["scope_basis_sha256"],
        },
        "scope_projection": copy.deepcopy(projection),
        "previous_chapter_handoff": previous,
        "source_manifest": sorted(manifest, key=lambda row: row["source_id"]),
        "selected_fact_refs": facts,
        "box_directory": boxes,
        "c9_source_needs": needs,
        "read_coverage": {},
        "task_basis_sha256": "0" * 64,
    }
    task["read_coverage"] = _coverage(task)
    return {
        "task": seal_task(task),
        "scope_confirmation": scope,
        "predecessor_binding": predecessor_binding,
        "settlements": settlements,
        "summaries": [],
        "ledger_responses": responses,
        "provenance_seals": [],
    }


def _non_confirmed_scope_bundle() -> dict[str, Any]:
    scope = scope_validator._awaiting_document()
    task = {
        "contract": "CHAPTER_CONTEXT_RETRIEVAL_TASK",
        "version": "v1",
        "retrieval_task_id": "RETRIEVAL-TASK-STOPPED-SCOPE",
        "truth_scope_ref": copy.deepcopy(scope["truth_scope_ref"]),
        "predecessor_binding_ref": None,
        "status": "STOPPED",
        "reason_code": "SCOPE_NOT_CONFIRMED",
        "scope_confirmation_ref": {
            "contract": "CHAPTER_SCOPE_CONFIRMATION",
            "version": "v1",
            "scope_id": scope["scope_id"],
            "scope_basis_sha256": scope["scope_basis_sha256"],
        },
        "scope_projection": None,
        "previous_chapter_handoff": None,
        "source_manifest": [
            _source_manifest_row(
                "SOURCE-SCOPE",
                "CHAPTER_SCOPE_CONFIRMATION",
                scope["scope_id"],
                "OPENED_OK",
                source_status="VALIDATED",
                document_sha256=scope["scope_basis_sha256"],
            )
        ],
        "selected_fact_refs": [],
        "box_directory": [],
        "c9_source_needs": [],
        "read_coverage": {},
        "task_basis_sha256": "0" * 64,
    }
    task["read_coverage"] = _coverage(task)
    task["read_coverage"]["complete_for_required"] = False
    return {
        "task": seal_task(task),
        "scope_confirmation": scope,
        "predecessor_binding": None,
        "settlements": [],
        "summaries": [],
        "ledger_responses": [],
        "provenance_seals": [],
    }


def build_base_bundle(base: str) -> dict[str, Any]:
    builders = {
        "continue": lambda: _base_bundle(),
        "hard_cut": lambda: _base_bundle(transition="SWITCH_HARD_CUT"),
        "sustained_branch": lambda: _base_bundle(transition="SWITCH_SUSTAINED_BRANCH"),
        "mainline_bridge": lambda: _base_bundle(transition="SWITCH_MAINLINE_BRIDGE"),
        "first_chapter": lambda: _base_bundle(first_chapter=True),
        "previous_empty": lambda: _base_bundle(empty_response=True),
        "current_fact": lambda: _base_bundle(),
        "optional_gap": lambda: _base_bundle(optional_gap=True),
        "summary_directory": lambda: _base_bundle(),
        "three_layers": lambda: _base_bundle(three_layers=True),
        "delegated": lambda: _base_bundle(delegated=True),
        "exact_mapping": lambda: _base_bundle(),
        "stopped_required": lambda: _base_bundle(hard_gap=True),
        "stopped_scope": _non_confirmed_scope_bundle,
    }
    try:
        return builders[base]()
    except KeyError as error:
        raise ContractError(f"FIXTURE_BASE_UNKNOWN:{base}") from error


def _recalculate_manifest_for_response(bundle: dict[str, Any]) -> None:
    response = bundle["ledger_responses"][0]
    response["receipt"]["basis_sha256"] = ledger_validator.basis_sha256(response)
    source = next(
        row
        for row in bundle["task"]["source_manifest"]
        if row["source_id"] == "SOURCE-FACT-READ"
    )
    source["object_ref"] = response["request_id"]
    source.update(
        {
            "access_state": {
                "OK": "OPENED_OK",
                "EMPTY": "OPENED_EMPTY",
                "REJECTED": "OPENED_REJECTED",
                "ERROR": "OPENED_ERROR",
            }[response["status"]],
            "source_status": response["status"],
            "reason_code": response["reason_code"],
            "basis_mode": response["basis_mode"],
            "basis_sha256": response["receipt"]["basis_sha256"],
            "source_document_sha256": sha256_json(response),
        }
    )
    bundle["task"]["read_coverage"] = _coverage(bundle["task"])


def _recalculate_predecessor_binding(bundle: dict[str, Any]) -> None:
    binding = seal_predecessor_binding(bundle["predecessor_binding"])
    bundle["predecessor_binding"] = binding
    bundle["task"]["predecessor_binding_ref"] = {
        "contract": "CHAPTER_PREDECESSOR_BINDING",
        "version": "v1",
        "binding_id": binding["binding_id"],
        "binding_basis_sha256": binding["binding_basis_sha256"],
    }
    source = next(
        row
        for row in bundle["task"]["source_manifest"]
        if row["source_id"] == "SOURCE-PREDECESSOR"
    )
    source["object_ref"] = binding["binding_id"]
    source["source_document_sha256"] = binding["binding_basis_sha256"]


def apply_mutation(bundle: dict[str, Any], mutation: str) -> dict[str, Any]:
    if mutation == "none":
        return bundle
    task = bundle["task"]
    if mutation == "scope_non_confirmed":
        source = scope_validator._awaiting_document()
        source["scope_id"] = bundle["scope_confirmation"]["scope_id"]
        source = scope_validator.seal_document(source)
        bundle["scope_confirmation"] = source
        task["scope_confirmation_ref"]["scope_basis_sha256"] = source[
            "scope_basis_sha256"
        ]
        scope_source = next(
            row
            for row in task["source_manifest"]
            if row["source_id"] == "SOURCE-SCOPE"
        )
        scope_source["source_document_sha256"] = source["scope_basis_sha256"]
    elif mutation == "scope_projection_mismatch":
        task["scope_projection"]["selected_storyline_ref"] = "LINE-9999"
    elif mutation == "second_scope_field":
        task["selected_storyline_ref"] = "LINE-0001"
    elif mutation == "settlement_scope_mismatch":
        bundle["settlements"][0]["truth_scope_ref"]["project_id"] = "PROJECT-0002"
        bundle["settlements"][0] = settlement_validator.seal_document(bundle["settlements"][0])
    elif mutation == "settlement_owner_unresolved":
        settlement = settlement_validator.build_base_document("unresolved_fact")
        bundle["settlements"][0] = settlement
        previous = _previous_projection(
            settlement, task["previous_chapter_handoff"]["c9_need_id"]
        )
        task["previous_chapter_handoff"] = previous
        source = next(
            row
            for row in task["source_manifest"]
            if row["source_id"] == "SOURCE-SETTLEMENT"
        )
        source["object_ref"] = f"settlement:{settlement['settlement_sha256']}"
        source["source_document_sha256"] = settlement["settlement_sha256"]
    elif mutation == "continuing_without_settlement":
        bundle["settlements"] = []
        task["previous_chapter_handoff"] = None
    elif mutation == "fact_not_in_response":
        task["selected_fact_refs"][0]["fact_ref"] = "f9999"
    elif mutation == "fact_revision_mismatch":
        task["selected_fact_refs"][0]["fact_revision"] = "workspace-facts-v9"
    elif mutation == "fact_from_empty":
        bundle["ledger_responses"][0] = _empty_chapter_response()
        _recalculate_manifest_for_response(bundle)
    elif mutation in {"current_advanced_ready", "result_too_large_ready"}:
        response = bundle["ledger_responses"][0]
        response.update(
            {
                "status": "REJECTED",
                "reason_code": "CURRENT_ADVANCED" if mutation.startswith("current") else "RESULT_TOO_LARGE",
                "data": None,
                "empty_scope": None,
            }
        )
        response["receipt"]["source_manifest"] = []
        response["limits"]["business_items"] = 0
        fact_need_id = task["selected_fact_refs"][0]["c9_need_id"]
        task["selected_fact_refs"] = []
        task["c9_source_needs"] = [
            row for row in task["c9_source_needs"] if row["need_id"] != fact_need_id
        ]
        _recalculate_manifest_for_response(bundle)
    elif mutation == "truncated_response":
        bundle["ledger_responses"][0]["limits"]["truncated"] = True
        _recalculate_manifest_for_response(bundle)
    elif mutation == "unavailable_marked_empty":
        task["source_manifest"].append(
            _source_manifest_row(
                "SOURCE-FAKE-EMPTY",
                "LEDGER_READ_TOOL_CONTRACT",
                "CAPABILITY-FAKE",
                "CAPABILITY_UNAVAILABLE",
                source_status="EMPTY",
                reason_code="REGISTERED_EMPTY",
            )
        )
        task["source_manifest"] = sorted(task["source_manifest"], key=lambda row: row["source_id"])
    elif mutation == "physical_box":
        task["box_directory"][0]["storage_path"] = "/tmp/box"
    elif mutation == "unauthorized_box_leak":
        task["box_directory"][0]["title"] = "隐藏盒子"
    elif mutation == "directory_only_content":
        task["box_directory"][0]["material_text"] = "不该出现的内容"
    elif mutation == "c9_wrong_version":
        task["c9_source_needs"][0]["source_contract_version"] = "v999"
    elif mutation == "c9_mapping_missing":
        fact_need = task["selected_fact_refs"][0]["c9_need_id"]
        task["c9_source_needs"] = [
            row for row in task["c9_source_needs"] if row["need_id"] != fact_need
        ]
    elif mutation == "orphan_child_need":
        child = _need(
            "NEED-ORPHAN",
            "SEAL-ORPHAN",
            "TRACEABLE_PROVENANCE_SEAL",
            obligation="SHOULD",
            layer="FORMATION_BASIS",
            parent="NEED-MISSING",
            trigger="AUDIT_REQUIRED",
            rank=len(task["c9_source_needs"]),
        )
        task["c9_source_needs"].append(child)
        task["box_directory"][0]["c9_need_ids"].append(child["need_id"])
    elif mutation == "child_obligation_escalation":
        parent = task["c9_source_needs"][0]
        parent["obligation_tier"] = "MAY"
        child = _need(
            "NEED-ESCALATED",
            "SEAL-ESCALATED",
            "TRACEABLE_PROVENANCE_SEAL",
            obligation="HARD",
            layer="FORMATION_BASIS",
            parent=parent["need_id"],
            trigger="AUDIT_REQUIRED",
            rank=len(task["c9_source_needs"]),
        )
        task["c9_source_needs"].append(child)
        task["box_directory"][0]["logical_open_ref"] = child["object_ref"]
        task["box_directory"][0]["c9_need_ids"].append(child["need_id"])
    elif mutation == "natural_language_path":
        task["source_manifest"][0]["file_path"] = "/tmp/source.json"
    elif mutation == "unknown_field":
        task["runtime_status"] = "READY"
    elif mutation == "duplicate_source_id":
        task["source_manifest"].append(copy.deepcopy(task["source_manifest"][0]))
        task["source_manifest"] = sorted(
            task["source_manifest"], key=lambda row: row["source_id"]
        )
    elif mutation == "stale_task_hash":
        task["retrieval_task_id"] = "RETRIEVAL-TASK-CHANGED"
        return bundle
    elif mutation == "full_c9_budget":
        task["budget"] = {"limit_tokens": 9999}
    elif mutation == "coverage_partition_mismatch":
        task["read_coverage"]["opened_source_ids"] = []
    elif mutation == "optional_gap_as_ready":
        task["status"] = "READY_FOR_THIN_CARD"
        task["reason_code"] = None
    elif mutation == "manifest_authorization_outside":
        task["source_manifest"][0]["authorized_scope_refs"] = ["LINE-9999"]
    elif mutation == "non_confirmed_box_leak":
        task["box_directory"] = [
            _box(
                "BOX-LEAKED",
                "CHARACTER_STATE",
                None,
                "TASK-0001",
                "MASKED",
                "SHOULD",
                None,
                [],
                "UNAUTHORIZED",
            )
        ]
    elif mutation == "opened_summary_without_evidence":
        source = next(
            row
            for row in task["source_manifest"]
            if row["source_id"] == "SOURCE-OLDER-SUMMARY"
        )
        source.update(
            {
                "object_ref": "summary:" + "a" * 64,
                "access_state": "OPENED_OK",
                "source_status": "VALIDATED",
                "source_document_sha256": "a" * 64,
            }
        )
        task["box_directory"][0]["availability"] = "OPENED"
        task["box_directory"][0]["logical_open_ref"] = source["object_ref"]
        task["c9_source_needs"][-1]["object_ref"] = source["object_ref"]
        task["read_coverage"] = _coverage(task)
    elif mutation == "box_source_contract_mismatch":
        task["source_manifest"].append(
            _source_manifest_row(
                "SOURCE-BOX-WRONG",
                "LEDGER_READ_TOOL_CONTRACT",
                "CAPABILITY-WRONG-BOX",
                "DIRECTORY_ONLY",
                authorized_scope_refs=[
                    task["scope_projection"]["selected_storyline_ref"]
                ],
            )
        )
        task["source_manifest"] = sorted(
            task["source_manifest"], key=lambda row: row["source_id"]
        )
        task["box_directory"][0]["source_id"] = "SOURCE-BOX-WRONG"
        task["read_coverage"] = _coverage(task)
    elif mutation == "source_version_mismatch":
        task["source_manifest"][0]["source_contract_version"] = "v999"
    elif mutation == "provenance_original_layer":
        need = next(
            row
            for row in task["c9_source_needs"]
            if row["need_id"] == "NEED-ORIGINAL"
        )
        need["source_contract"] = "TRACEABLE_PROVENANCE_SEAL"
        need["source_contract_version"] = SOURCE_VERSIONS[
            "TRACEABLE_PROVENANCE_SEAL"
        ]
        source = next(
            row
            for row in task["source_manifest"]
            if row["source_id"] == "SOURCE-ORIGINAL"
        )
        source["source_contract"] = "TRACEABLE_PROVENANCE_SEAL"
        source["source_contract_version"] = "v1"
    elif mutation == "fact_missing_chapter_revision":
        response = bundle["ledger_responses"][0]
        fact = response["data"]["entries"][0]
        fact.pop("chapter_revision_ref")
        source = response["receipt"]["source_manifest"][0]
        source["logical_content_sha256"] = sha256_json(fact)
        task["selected_fact_refs"][0]["fact_sha256"] = source[
            "logical_content_sha256"
        ]
        _recalculate_manifest_for_response(bundle)
    elif mutation == "fact_basis_mismatch":
        task["selected_fact_refs"][0]["selection_basis_refs"] = [
            task["scope_confirmation_ref"]["scope_id"],
            "REQ-UNREAD-9999",
        ]
    elif mutation == "predecessor_current_slot_mismatch":
        bundle["predecessor_binding"]["current_slot_ref"] = "SLOT-9999"
        _recalculate_predecessor_binding(bundle)
    elif mutation == "predecessor_settlement_mismatch":
        bundle["predecessor_binding"]["previous_slot_ref"] = "S-9999"
        _recalculate_predecessor_binding(bundle)
    elif mutation == "predecessor_first_with_previous":
        binding = bundle["predecessor_binding"]
        binding["chapter_position"] = "FIRST_CHAPTER"
        binding["previous_slot_ref"] = None
        binding["previous_settlement_sha256"] = None
        _recalculate_predecessor_binding(bundle)
    elif mutation == "previous_obligation_downgrade":
        need = next(
            row
            for row in task["c9_source_needs"]
            if row["need_id"] == "NEED-PREVIOUS"
        )
        need["obligation_tier"] = "MAY"
        need["selection_rank"] = 0
        next(
            row
            for row in task["c9_source_needs"]
            if row["need_id"] == "NEED-BOX-OLDER"
        )["selection_rank"] = 1
    elif mutation == "box_obligation_downgrade":
        need = next(
            row
            for row in task["c9_source_needs"]
            if row["need_id"] == "NEED-BOX-OLDER"
        )
        need["obligation_tier"] = "MAY"
        need["selection_rank"] = 0
    elif mutation == "duplicate_selected_fact":
        duplicate = copy.deepcopy(task["selected_fact_refs"][0])
        duplicate["c9_need_id"] = "NEED-FACT-f0001-DUPLICATE"
        task["selected_fact_refs"].append(duplicate)
        task["c9_source_needs"].append(
            _need(
                duplicate["c9_need_id"],
                duplicate["fact_ref"],
                "LEDGER_READ_TOOL_CONTRACT",
                rank=None,
            )
        )
    elif mutation == "stopped_box_entry_leak":
        task["box_directory"][0]["logical_open_ref"] = "CHARACTER-STATE-0001"
    elif mutation == "stopped_source_entry_leak":
        task["source_manifest"].append(
            _source_manifest_row(
                "SOURCE-LEAKED-DIRECTORY",
                "CHAPTER_LAYERED_SUMMARY",
                "SUMMARY-LEAKED-0001",
                "DIRECTORY_ONLY",
                authorized_scope_refs=[
                    task["scope_projection"]["selected_storyline_ref"]
                ],
            )
        )
        task["source_manifest"] = sorted(
            task["source_manifest"], key=lambda row: row["source_id"]
        )
        task["read_coverage"] = _coverage(task)
    else:
        raise ContractError(f"FIXTURE_MUTATION_UNKNOWN:{mutation}")
    task["task_basis_sha256"] = task_basis_sha256(task)
    return bundle


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for row in rows:
        if set(row) != RECIPE_KEYS:
            raise ContractError("FIXTURE_RECIPE_KEYS_INVALID")
    return rows


def materialize_fixture_case(case: dict[str, Any]) -> dict[str, Any]:
    return apply_mutation(build_base_bundle(case["base"]), case["mutation"])


def fixture_error_code(case: dict[str, Any]) -> str | None:
    try:
        validate_task_bundle(materialize_fixture_case(case))
    except (ContractError, KeyError, TypeError, ValueError, AssertionError) as error:
        return str(error).split(":", 1)[0]
    return None


def validate_fixture_case(case: dict[str, Any]) -> str:
    if fixture_error_code(case) is not None:
        return STRUCTURAL_INVALID
    return STRUCTURAL_VALID


def validate_all_fixtures(path: Path = FIXTURE_PATH) -> dict[str, int]:
    counts = {STRUCTURAL_VALID: 0, STRUCTURAL_INVALID: 0}
    for case in load_fixtures(path):
        result = validate_fixture_case(case)
        if result != case["expected_result"]:
            raise ContractError(
                f"FIXTURE_EXPECTATION_MISMATCH:{case['case_id']}:{result}"
            )
        if result == STRUCTURAL_INVALID:
            expected_error = EXPECTED_ERROR_CODES.get(case["mutation"])
            actual_error = fixture_error_code(case)
            if actual_error != expected_error:
                raise ContractError(
                    "FIXTURE_ERROR_CODE_MISMATCH:"
                    f"{case['case_id']}:{expected_error}:{actual_error}"
                )
        counts[result] += 1
    return counts


def main() -> int:
    counts = validate_all_fixtures()
    print(
        json.dumps(
            {
                "contract": "CHAPTER_CONTEXT_RETRIEVAL_TASK",
                "version": "v1",
                "status": "PASS",
                "counts": counts,
                "current_owner_resolution_performed": False,
                "semantic_search_performed": False,
                "c9_execution_performed": False,
                "workspace_reads": 0,
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
