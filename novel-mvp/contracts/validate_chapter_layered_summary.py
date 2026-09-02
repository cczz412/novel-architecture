"""Validate CHAPTER_LAYERED_SUMMARY v1 structural traceability."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "CHAPTER_LAYERED_SUMMARY.schema.json"
FIXTURE_PATH = DIR / "CHAPTER_LAYERED_SUMMARY.fixtures.jsonl"
SETTLEMENT_VALIDATOR_PATH = DIR / "validate_chapter_settlement_seal.py"

STRUCTURAL_VALID = "STRUCTURAL_VALID"
STRUCTURAL_VALID_OWNER_UNRESOLVED = "STRUCTURAL_VALID_OWNER_UNRESOLVED"
STRUCTURAL_INVALID = "STRUCTURAL_INVALID"

FORBIDDEN_CONTENT_KEYS = {
    "body",
    "chapter_text",
    "database_table",
    "file_path",
    "path",
    "physical_path",
    "quote",
    "sql",
    "table_name",
    "text",
}
RECIPE_KEYS = {"base", "case_id", "expected_result", "mutation"}


class ContractError(ValueError):
    """A layered-summary structural invariant failed."""


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"MODULE_LOAD_FAILED:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


settlement = _load_module(
    SETTLEMENT_VALIDATOR_PATH, "chapter_layered_summary_settlement"
)


def _load_schema() -> dict[str, Any]:
    value = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


SCHEMA = _load_schema()
VALIDATOR = Draft202012Validator(SCHEMA)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def summary_sha256(document: dict[str, Any]) -> str:
    payload = copy.deepcopy(document)
    payload.pop("summary_sha256", None)
    return sha256_json(payload)


def seal_document(document: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    result["summary_sha256"] = summary_sha256(result)
    return result


def policy_sha256(policy: dict[str, Any]) -> str:
    payload = copy.deepcopy(policy)
    payload.pop("policy_sha256", None)
    return sha256_json(payload)


def _schema_path(error: Any) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "$"


def _validate_schema(document: Any) -> None:
    errors = sorted(
        VALIDATOR.iter_errors(document),
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
                raise ContractError(
                    f"PROTECTED_CONTENT_KEY_FORBIDDEN:{path}.{key}"
                )
            _walk_forbidden_content(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_forbidden_content(item, f"{path}[{index}]")


def _unique_map(
    values: list[dict[str, Any]], key: str, label: str
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in values:
        identity = value.get(key)
        if not isinstance(identity, str) or not identity or identity in result:
            raise ContractError(f"{label}_IDENTITY_INVALID_OR_DUPLICATE")
        result[identity] = value
    return result


def _validate_policy(document: dict[str, Any]) -> None:
    policy = document["policy"]
    if policy["grouping_basis"] != document["scope"]["grouping_basis"]:
        raise ContractError("POLICY_SCOPE_GROUPING_MISMATCH")
    if policy["policy_sha256"] != policy_sha256(policy):
        raise ContractError("POLICY_SHA256_MISMATCH")


def _expected_unresolved_items(
    leaves: list[dict[str, Any]],
    settlement_map: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for leaf in leaves:
        source = settlement_map[leaf["settlement_sha256"]]
        rows.extend(
            {
                "item_id": item["item_id"],
                "settlement_sha256": leaf["settlement_sha256"],
            }
            for item in source["unresolved_story_items"]
        )
    return rows


def _validate_summary(
    document: dict[str, Any],
    settlement_map: dict[str, dict[str, Any]],
    summary_map: dict[str, dict[str, Any]],
    stack: set[str],
) -> str:
    _validate_schema(document)
    _walk_forbidden_content(document)
    _validate_policy(document)
    identity = document["summary_sha256"]
    if identity in stack:
        raise ContractError("SUMMARY_INPUT_CYCLE")
    active_stack = {*stack, identity}

    inputs = document["inputs"]
    if [row["order"] for row in inputs] != list(range(1, len(inputs) + 1)):
        raise ContractError("INPUT_ORDER_INVALID")
    input_keys = [(row["input_kind"], row["input_sha256"]) for row in inputs]
    if len(input_keys) != len(set(input_keys)):
        raise ContractError("INPUT_REF_DUPLICATE")
    if document["summary_kind"] == "PHASE" and any(
        row["input_kind"] != "CHAPTER_SETTLEMENT_SEAL" for row in inputs
    ):
        raise ContractError("PHASE_INPUT_MUST_BE_SETTLEMENT")

    expected_leaves: list[dict[str, Any]] = []
    owner_unresolved = False
    for input_ref in inputs:
        source_sha = input_ref["input_sha256"]
        if input_ref["input_kind"] == "CHAPTER_SETTLEMENT_SEAL":
            source = settlement_map.get(source_sha)
            if source is None:
                raise ContractError("SETTLEMENT_INPUT_NOT_FOUND")
            try:
                result = settlement.validate_settlement(source)
            except settlement.ContractError as exc:
                raise ContractError(f"SETTLEMENT_INPUT_INVALID:{exc}") from exc
            if source["truth_scope_ref"] != document["truth_scope_ref"]:
                raise ContractError("TRUTH_SCOPE_MISMATCH")
            if input_ref["input_claim_kind"] != source["claim_kind"]:
                raise ContractError("SETTLEMENT_INPUT_CLAIM_MISMATCH")
            owner_unresolved |= (
                result == settlement.STRUCTURAL_VALID_OWNER_UNRESOLVED
            )
            expected_leaves.append(
                {
                    "slot_ref": source["slot_ref"],
                    "settlement_sha256": source_sha,
                    "settlement_claim_kind": source["claim_kind"],
                    "order": 0,
                }
            )
        else:
            source = summary_map.get(source_sha)
            if source is None:
                raise ContractError("SUMMARY_INPUT_NOT_FOUND")
            result = _validate_summary(
                source,
                settlement_map,
                summary_map,
                active_stack,
            )
            if source["truth_scope_ref"] != document["truth_scope_ref"]:
                raise ContractError("TRUTH_SCOPE_MISMATCH")
            if input_ref["input_claim_kind"] != source["claim_kind"]:
                raise ContractError("SUMMARY_INPUT_CLAIM_MISMATCH")
            owner_unresolved |= result == STRUCTURAL_VALID_OWNER_UNRESOLVED
            expected_leaves.extend(
                {**copy.deepcopy(leaf), "order": 0}
                for leaf in source["leaf_settlement_refs"]
            )

    leaf_ids = [row["settlement_sha256"] for row in expected_leaves]
    if len(leaf_ids) != len(set(leaf_ids)):
        raise ContractError("LEAF_SETTLEMENT_DUPLICATE_ACROSS_INPUTS")
    for order, leaf in enumerate(expected_leaves, start=1):
        leaf["order"] = order
    if document["leaf_settlement_refs"] != expected_leaves:
        raise ContractError("LEAF_SETTLEMENT_MANIFEST_MISMATCH")

    expected_claim = (
        "OWNER_UNRESOLVED_PROJECTION"
        if owner_unresolved
        else "RESOLVED_PROJECTION"
    )
    if document["claim_kind"] != expected_claim:
        raise ContractError("SUMMARY_OWNER_RESOLUTION_PROPAGATION_MISMATCH")

    section_ids = [row["section_id"] for row in document["sections"]]
    if len(section_ids) != len(set(section_ids)):
        raise ContractError("SECTION_ID_DUPLICATE")
    leaf_set = set(leaf_ids)
    covered: set[str] = set()
    for section in document["sections"]:
        refs = section["source_leaf_settlement_refs"]
        unknown = set(refs) - leaf_set
        if unknown:
            raise ContractError("SECTION_SOURCE_LEAF_UNKNOWN")
        covered.update(refs)
    if covered != leaf_set:
        raise ContractError("SECTION_LEAF_COVERAGE_INCOMPLETE")

    expected_unresolved = _expected_unresolved_items(
        expected_leaves, settlement_map
    )
    if document["unresolved_item_refs"] != expected_unresolved:
        raise ContractError("UNRESOLVED_STORY_ITEM_COVERAGE_MISMATCH")

    coverage = document["coverage"]
    expected_coverage = {
        "input_count": len(inputs),
        "leaf_count": len(expected_leaves),
        "covered_leaf_count": len(covered),
        "unresolved_item_count": len(expected_unresolved),
        "coverage_ratio": 1.0,
    }
    if coverage != expected_coverage:
        raise ContractError("SUMMARY_COVERAGE_MISMATCH")
    if document["summary_sha256"] != summary_sha256(document):
        raise ContractError("SUMMARY_SHA256_MISMATCH")
    return (
        STRUCTURAL_VALID_OWNER_UNRESOLVED
        if owner_unresolved
        else STRUCTURAL_VALID
    )


def validate_summary(
    document: Any,
    settlement_documents: list[dict[str, Any]],
    summary_documents: list[dict[str, Any]] | None = None,
) -> str:
    """Validate one projection with exact in-memory sources and no external IO."""

    if not isinstance(document, dict):
        raise ContractError("SUMMARY_DOCUMENT_NOT_OBJECT")
    settlement_map = _unique_map(
        settlement_documents,
        "settlement_sha256",
        "SETTLEMENT_SOURCE",
    )
    summary_map = _unique_map(
        summary_documents or [],
        "summary_sha256",
        "SUMMARY_SOURCE",
    )
    return _validate_summary(document, settlement_map, summary_map, set())


def _variant_settlement(
    source: dict[str, Any], index: int
) -> dict[str, Any]:
    value = copy.deepcopy(source)
    slot_ref = f"S-{index:04d}"
    value["slot_ref"] = slot_ref
    value["settled_at"] = f"2026-09-{index:02d}T03:00:00+08:00"
    action = value["closeout_input"]
    action["operation_id"] = f"op-closeout-variant-{index}"
    action["slot_ref"] = slot_ref
    if action["work_ref"] is not None:
        action["work_ref"] = f"{slot_ref}@work"
    action["action_sha256"] = settlement.closeout_action_sha256(action)
    value["planning"]["chapter_slot_snapshot_sha256"] = sha256_json(
        {"slot": slot_ref, "rev": index}
    )
    value["planning"]["source_plan_version"] = index + 10
    value["planning"]["source_plan_sha256"] = sha256_json(
        {"plan": index + 10}
    )
    value["planning"]["adopted_path_refs"][0][
        "object_ref"
    ] = f"work-card:WC-{index:04d}"
    value["unresolved_story_items"][0]["item_id"] = f"USI-{index:04d}"
    return settlement.seal_document(value)


def _policy(grouping_basis: str, version: str = "v1") -> dict[str, Any]:
    value = {
        "policy_id": "chapter-layering-policy",
        "policy_version": version,
        "grouping_basis": grouping_basis,
    }
    value["policy_sha256"] = policy_sha256(value)
    return value


def _unresolved_item_refs(
    leaves: list[dict[str, Any]], settlements: list[dict[str, Any]]
) -> list[dict[str, str]]:
    source_map = {
        row["settlement_sha256"]: row for row in settlements
    }
    return _expected_unresolved_items(leaves, source_map)


def _summary_document(
    *,
    summary_kind: str,
    grouping_basis: str,
    scope_ref: str,
    inputs: list[dict[str, Any]],
    leaves: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
    owner_unresolved: bool,
    policy_version: str = "v1",
) -> dict[str, Any]:
    leaf_ids = [row["settlement_sha256"] for row in leaves]
    unresolved_refs = _unresolved_item_refs(leaves, settlements)
    document = {
        "contract": "CHAPTER_LAYERED_SUMMARY",
        "version": "v1",
        "truth_scope_ref": copy.deepcopy(settlements[0]["truth_scope_ref"]),
        "claim_kind": (
            "OWNER_UNRESOLVED_PROJECTION"
            if owner_unresolved
            else "RESOLVED_PROJECTION"
        ),
        "summary_kind": summary_kind,
        "projection_only": True,
        "writes_truth": False,
        "scope": {
            "grouping_basis": grouping_basis,
            "scope_ref": scope_ref,
            "ordered": True,
        },
        "policy": _policy(grouping_basis, policy_version),
        "inputs": inputs,
        "leaf_settlement_refs": leaves,
        "sections": [
            {
                "section_id": "SEC-0001",
                "section_kind": "SYNOPSIS",
                "summary": "合成阶段摘要只压缩已封存输入。",
                "source_leaf_settlement_refs": leaf_ids,
            },
            {
                "section_id": "SEC-0002",
                "section_kind": "UNRESOLVED",
                "summary": "合成未决项完整保留，仍可回到原章。",
                "source_leaf_settlement_refs": leaf_ids,
            },
        ],
        "unresolved_item_refs": unresolved_refs,
        "coverage": {
            "input_count": len(inputs),
            "leaf_count": len(leaves),
            "covered_leaf_count": len(leaves),
            "unresolved_item_count": len(unresolved_refs),
            "coverage_ratio": 1.0,
        },
        "generated_by": {
            "kind": "DETERMINISTIC_ASSEMBLER",
            "name": "synthetic-fixture-builder",
            "version": "v1",
        },
        "generated_at": "2026-09-03T04:00:00+08:00",
    }
    return seal_document(document)


def _phase_bundle(*, unresolved: bool) -> dict[str, Any]:
    first = _variant_settlement(
        settlement.build_base_document("resolved_full"), 1
    )
    second_base = "unresolved_fact" if unresolved else "resolved_skip"
    second = _variant_settlement(
        settlement.build_base_document(second_base), 2
    )
    settlements = [first, second]
    inputs = [
        {
            "input_kind": "CHAPTER_SETTLEMENT_SEAL",
            "input_sha256": row["settlement_sha256"],
            "input_claim_kind": row["claim_kind"],
            "order": index,
        }
        for index, row in enumerate(settlements, start=1)
    ]
    leaves = [
        {
            "slot_ref": row["slot_ref"],
            "settlement_sha256": row["settlement_sha256"],
            "settlement_claim_kind": row["claim_kind"],
            "order": index,
        }
        for index, row in enumerate(settlements, start=1)
    ]
    return {
        "document": _summary_document(
            summary_kind="PHASE",
            grouping_basis="STORY_PHASE",
            scope_ref="phase:PH-0001",
            inputs=inputs,
            leaves=leaves,
            settlements=settlements,
            owner_unresolved=unresolved,
        ),
        "settlements": settlements,
        "summaries": [],
    }


def _long_range_bundle(*, unresolved: bool) -> dict[str, Any]:
    child = _phase_bundle(unresolved=unresolved)
    third = _variant_settlement(
        settlement.build_base_document("resolved_no_prose"), 3
    )
    settlements = [*child["settlements"], third]
    child_document = child["document"]
    inputs = [
        {
            "input_kind": "CHAPTER_LAYERED_SUMMARY",
            "input_sha256": child_document["summary_sha256"],
            "input_claim_kind": child_document["claim_kind"],
            "order": 1,
        },
        {
            "input_kind": "CHAPTER_SETTLEMENT_SEAL",
            "input_sha256": third["settlement_sha256"],
            "input_claim_kind": third["claim_kind"],
            "order": 2,
        },
    ]
    leaves = [
        {
            **copy.deepcopy(row),
            "order": index,
        }
        for index, row in enumerate(
            [
                *child_document["leaf_settlement_refs"],
                {
                    "slot_ref": third["slot_ref"],
                    "settlement_sha256": third["settlement_sha256"],
                    "settlement_claim_kind": third["claim_kind"],
                    "order": 0,
                },
            ],
            start=1,
        )
    ]
    return {
        "document": _summary_document(
            summary_kind="LONG_RANGE",
            grouping_basis="STORYLINE_SCOPE",
            scope_ref="storyline:L-0001",
            inputs=inputs,
            leaves=leaves,
            settlements=settlements,
            owner_unresolved=unresolved,
        ),
        "settlements": settlements,
        "summaries": [child_document],
    }


def _retarget_bundle(
    bundle: dict[str, Any], grouping_basis: str, scope_ref: str
) -> dict[str, Any]:
    result = copy.deepcopy(bundle)
    result["document"]["scope"] = {
        "grouping_basis": grouping_basis,
        "scope_ref": scope_ref,
        "ordered": True,
    }
    result["document"]["policy"] = _policy(grouping_basis)
    result["document"] = seal_document(result["document"])
    return result


def build_base_bundle(base: str) -> dict[str, Any]:
    if base == "valid_phase":
        return _phase_bundle(unresolved=False)
    if base == "valid_long_range":
        return _long_range_bundle(unresolved=False)
    if base == "valid_author_pinned":
        return _retarget_bundle(
            _phase_bundle(unresolved=False),
            "AUTHOR_PINNED_SET",
            "author-pinned:APS-0001",
        )
    if base == "valid_policy_v2":
        bundle = _phase_bundle(unresolved=False)
        bundle["document"]["policy"] = _policy("STORY_PHASE", "v2")
        bundle["document"] = seal_document(bundle["document"])
        return bundle
    if base == "unresolved_phase":
        return _phase_bundle(unresolved=True)
    if base == "unresolved_long_range":
        return _long_range_bundle(unresolved=True)
    if base == "unresolved_author_pinned":
        return _retarget_bundle(
            _phase_bundle(unresolved=True),
            "AUTHOR_PINNED_SET",
            "author-pinned:APS-0002",
        )
    raise ContractError(f"FIXTURE_BASE_UNKNOWN:{base}")


def _apply_mutation(bundle: dict[str, Any], mutation: str) -> dict[str, Any]:
    value = copy.deepcopy(bundle)
    document = value["document"]
    if mutation == "none":
        return value
    if mutation == "writes_truth":
        document["writes_truth"] = True
    elif mutation == "missing_leaf":
        document["leaf_settlement_refs"].pop()
    elif mutation == "duplicate_leaf":
        duplicate = copy.deepcopy(document["leaf_settlement_refs"][0])
        duplicate["order"] = len(document["leaf_settlement_refs"]) + 1
        document["leaf_settlement_refs"].append(duplicate)
    elif mutation == "input_order_gap":
        document["inputs"][-1]["order"] += 1
    elif mutation == "section_without_source":
        document["sections"][0]["source_leaf_settlement_refs"] = []
    elif mutation == "unresolved_item_dropped":
        document["unresolved_item_refs"].pop()
        document["coverage"]["unresolved_item_count"] -= 1
    elif mutation == "scope_mismatch":
        document["truth_scope_ref"]["project_id"] = "PROJECT-OTHER"
    elif mutation == "unresolved_claims_resolved":
        document["claim_kind"] = "RESOLVED_PROJECTION"
    elif mutation == "policy_changed_reused_summary_sha":
        document["policy"] = _policy(
            document["policy"]["grouping_basis"], "v99"
        )
        return value
    else:
        raise ContractError(f"FIXTURE_MUTATION_UNKNOWN:{mutation}")
    value["document"] = seal_document(document)
    return value


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    rows = []
    for line_no, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict) or set(value) != RECIPE_KEYS:
            raise ContractError(f"FIXTURE_RECIPE_INVALID:{line_no}")
        rows.append(value)
    return rows


def materialize_fixture_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        **copy.deepcopy(case),
        **_apply_mutation(build_base_bundle(case["base"]), case["mutation"]),
    }


def validate_fixture_case(case: dict[str, Any]) -> str:
    materialized = materialize_fixture_case(case)
    try:
        return validate_summary(
            materialized["document"],
            materialized["settlements"],
            materialized["summaries"],
        )
    except (ContractError, KeyError, TypeError, ValueError):
        return STRUCTURAL_INVALID


def validate_all_fixtures(path: Path = FIXTURE_PATH) -> dict[str, int]:
    counts = {
        STRUCTURAL_VALID: 0,
        STRUCTURAL_VALID_OWNER_UNRESOLVED: 0,
        STRUCTURAL_INVALID: 0,
    }
    for case in load_fixtures(path):
        actual = validate_fixture_case(case)
        if actual != case["expected_result"]:
            raise ContractError(
                f"FIXTURE_EXPECTATION_MISMATCH:{case['case_id']}:"
                f"{case['expected_result']}:{actual}"
            )
        counts[actual] += 1
    return counts


def main() -> int:
    counts = validate_all_fixtures()
    print(
        json.dumps(
            {
                "contract": "CHAPTER_LAYERED_SUMMARY",
                "version": "v1",
                "status": "PASS",
                "counts": counts,
                "owner_resolution_performed": False,
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
