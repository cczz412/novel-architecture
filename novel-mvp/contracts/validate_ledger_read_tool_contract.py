"""Validate LEDGER_READ_TOOL_CONTRACT ledger-read-tool-contract-v1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "LEDGER_READ_TOOL_CONTRACT.schema.json"
FIXTURE_PATH = DIR / "LEDGER_READ_TOOL_CONTRACT.fixtures.jsonl"
VERSION = "ledger-read-tool-contract-v1"
LIMIT_POLICY_VERSION = "limit-policy-v1"
TEN_LEDGER_NAMES = (
    "章节账",
    "事实账",
    "人物账",
    "地点账",
    "物品账",
    "势力账",
    "体系账",
    "世界规则账",
    "长线账",
    "规划账",
)
READ_PROFILE_BY_LEDGER = {
    "章节账": "chapter_metadata",
    "事实账": "fact_record",
    "人物账": "character_definition",
    "地点账": "location_definition",
    "物品账": "item_definition",
    "势力账": "faction_definition",
    "体系账": "system_definition",
    "世界规则账": "world_rule_definition",
}
REF_PATTERN_BY_LEDGER = {
    "章节账": re.compile(r"^c[0-9]{2,}$"),
    "事实账": re.compile(r"^f[0-9]{3,}$"),
    "人物账": re.compile(r"^CH-[0-9]+$"),
    "地点账": re.compile(r"^LOC-[0-9]+$"),
    "物品账": re.compile(r"^IT-[0-9]+$"),
    "势力账": re.compile(r"^FA-[0-9]+$"),
    "体系账": re.compile(r"^SY-[0-9]+$"),
    "世界规则账": re.compile(r"^RU-[0-9]+$"),
}
EMPTY_REASONS = {
    "REGISTERED_EMPTY",
    "NO_MATCHING_ENTRIES",
    "NOT_RECORDED",
}
REJECTED_REASONS = {
    "UNAUTHORIZED",
    "INVALID_SELECTOR",
    "INVALID_PIN_SET",
    "CURRENT_ADVANCED",
    "ENTRY_NOT_FOUND",
    "REVISION_NOT_FOUND",
    "SHA_MISMATCH",
    "CAPABILITY_UNAVAILABLE",
    "READ_PROFILE_NOT_FROZEN",
    "SOURCE_VERSION_UNSUPPORTED",
    "STORY_TIME_NOT_COMPARABLE",
    "PROJECTION_NOT_AVAILABLE",
    "FORMAL_CONTRACT_NOT_AVAILABLE",
    "RESULT_TOO_LARGE",
}
ERROR_REASONS = {
    "DIRECTORY_NOT_INITIALIZED",
    "SOURCE_CORRUPTED",
    "INTERNAL_ERROR",
}


class ContractError(ValueError):
    """A ledger read tool contract invariant failed."""


def _load_schema() -> dict[str, Any]:
    value = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


SCHEMA = _load_schema()
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


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
        raise ContractError(f"SCHEMA_INVALID:{_schema_path(first)}:{first.validator}")


def canonical_json(value: Any) -> str:
    """Return the contract's UTF-8 canonical JSON text."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _source_sort_key(item: dict[str, Any]) -> tuple[str, ...]:
    revision = item["revision"]
    revision_key = (
        f"integer:{revision:020d}"
        if isinstance(revision, int) and not isinstance(revision, bool)
        else f"string:{revision}"
    )
    return (
        item["source_kind"],
        item["logical_ledger_name"] or "",
        item["stable_id"],
        revision_key,
        item["role"],
        item["source_contract"],
        item["source_contract_version"],
        item["logical_content_sha256"],
    )


def validate_source_manifest(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ContractError("SOURCE_MANIFEST_INVALID")
    manifest = value
    if manifest != sorted(manifest, key=_source_sort_key):
        raise ContractError("SOURCE_MANIFEST_NOT_STABLY_SORTED")
    keys = [_source_sort_key(item) for item in manifest]
    if len(keys) != len(set(keys)):
        raise ContractError("SOURCE_MANIFEST_ITEM_DUPLICATE")
    for index, item in enumerate(manifest):
        kind = item["source_kind"]
        compiler = item["compiler_version"]
        input_basis = item["input_basis_sha256"]
        ledger = item["logical_ledger_name"]
        if kind == "projection":
            if compiler is None or input_basis is None:
                raise ContractError(f"PROJECTION_BINDING_INCOMPLETE:{index}")
        elif compiler is not None or input_basis is not None:
            raise ContractError(f"NON_PROJECTION_COMPILER_FIELDS_FORBIDDEN:{index}")
        if kind == "directory_capability_snapshot" and ledger is not None:
            raise ContractError(f"DIRECTORY_SOURCE_LEDGER_MUST_BE_NULL:{index}")
        if kind != "directory_capability_snapshot" and ledger is None:
            raise ContractError(f"SOURCE_LEDGER_REQUIRED:{index}")
        if kind == "chapter_revision" and ledger != "章节账":
            raise ContractError(f"CHAPTER_SOURCE_LEDGER_INVALID:{index}")
    return manifest


def basis_object(response: dict[str, Any]) -> dict[str, Any]:
    receipt = response["receipt"]
    return {
        "author_id": receipt["author_id"],
        "project_id": receipt["project_id"],
        "permission_policy_version": receipt["permission_policy_version"],
        "tool_contract_version": receipt["tool_contract_version"],
        "basis_mode": response["basis_mode"],
        "tool": response["tool"],
        "source_manifest": receipt["source_manifest"],
    }


def basis_sha256(response: dict[str, Any]) -> str:
    payload = canonical_json(basis_object(response)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_request(document: dict[str, Any]) -> dict[str, Any]:
    tool = document["tool"]
    mode = document["basis"]["mode"]
    selector = document["selector"]
    keys = set(selector)
    if mode == "pinned_manifest":
        validate_source_manifest(document["basis"]["source_manifest"])

    if tool == "get_ledger_directory":
        if mode != "current_at_start" or keys:
            raise ContractError("DIRECTORY_CURRENT_ONLY")
        return document

    if tool == "get_chapter_evidence_slice":
        expected = (
            {"chapter_id", "include_chapter_text"}
            if mode == "current_at_start"
            else {"chapter_revision_ref", "include_chapter_text"}
        )
        if keys != expected:
            raise ContractError("CHAPTER_SELECTOR_BASIS_MISMATCH")
        return document

    if tool == "get_character_state_as_of":
        if keys != {"character_ref", "as_of", "sections", "state_keys"}:
            raise ContractError("CHARACTER_SELECTOR_INVALID")
        return document

    if tool == "get_ledger_entries_by_ref":
        expected = (
            {"ledger_name", "read_profile", "refs"}
            if mode == "current_at_start"
            else {"ledger_name", "read_profile", "recall_codes"}
        )
        if keys != expected:
            raise ContractError("ENTRY_SELECTOR_BASIS_MISMATCH")
        ledger_name = selector["ledger_name"]
        profile = selector["read_profile"]
        if READ_PROFILE_BY_LEDGER.get(ledger_name) != profile:
            raise ContractError("READ_PROFILE_LEDGER_MISMATCH")
        pattern = REF_PATTERN_BY_LEDGER[ledger_name]
        if mode == "current_at_start":
            if any(pattern.fullmatch(ref) is None for ref in selector["refs"]):
                raise ContractError("STABLE_REF_INVALID")
        else:
            if any(
                code["ledger_name"] != ledger_name
                for code in selector["recall_codes"]
            ):
                raise ContractError("RECALL_CODE_LEDGER_MISMATCH")
            if any(
                pattern.fullmatch(code["entry_id"]) is None
                for code in selector["recall_codes"]
            ):
                raise ContractError("RECALL_CODE_ENTRY_ID_INVALID")
        return document

    if tool == "get_longline_box_status":
        if mode != "current_at_start" or keys != {"box_ref"}:
            raise ContractError("BOX_CURRENT_ONLY")
        return document

    if tool == "get_character_knowledge_edges_as_of":
        if keys != {"observer_ref", "as_of", "fact_refs"}:
            raise ContractError("KNOWLEDGE_SELECTOR_INVALID")
        return document

    raise ContractError("TOOL_INVALID")


def _validate_response(document: dict[str, Any]) -> dict[str, Any]:
    status = document["status"]
    reason = document["reason_code"]
    data = document["data"]
    empty_scope = document["empty_scope"]
    limits = document["limits"]
    manifest = validate_source_manifest(document["receipt"]["source_manifest"])

    if document["basis_mode"] == "pinned_manifest" and not manifest:
        raise ContractError("PINNED_RESPONSE_SOURCE_MANIFEST_REQUIRED")
    if status == "OK":
        if reason is not None or data is None or empty_scope is not None:
            raise ContractError("OK_RESPONSE_SHAPE_INVALID")
        if isinstance(data, (dict, list)) and not data:
            raise ContractError("OK_RESPONSE_DATA_EMPTY")
        if limits["business_items"] < 1:
            raise ContractError("OK_RESPONSE_ITEM_COUNT_INVALID")
    elif status == "EMPTY":
        if reason not in EMPTY_REASONS or data is not None or empty_scope is None:
            raise ContractError("EMPTY_RESPONSE_SHAPE_INVALID")
        if limits["business_items"] != 0:
            raise ContractError("EMPTY_RESPONSE_ITEM_COUNT_INVALID")
    elif status == "REJECTED":
        if reason not in REJECTED_REASONS or data is not None or empty_scope is not None:
            raise ContractError("REJECTED_RESPONSE_SHAPE_INVALID")
        if limits["business_items"] != 0:
            raise ContractError("REJECTED_RESPONSE_ITEM_COUNT_INVALID")
    elif status == "ERROR":
        if reason not in ERROR_REASONS or data is not None or empty_scope is not None:
            raise ContractError("ERROR_RESPONSE_SHAPE_INVALID")
        if limits["business_items"] != 0:
            raise ContractError("ERROR_RESPONSE_ITEM_COUNT_INVALID")
    else:
        raise ContractError("STATUS_INVALID")

    if reason == "UNAUTHORIZED" and (
        manifest or document["receipt"]["capability_snapshot_id"] is not None
    ):
        raise ContractError("UNAUTHORIZED_EXISTENCE_LEAK")

    if document["tool"] == "get_longline_box_status" and (
        status != "REJECTED" or reason != "PROJECTION_NOT_AVAILABLE"
    ):
        raise ContractError("BOX_INTERFACE_MUST_REMAIN_CLOSED")
    if document["tool"] == "get_character_knowledge_edges_as_of" and (
        status != "REJECTED" or reason != "FORMAL_CONTRACT_NOT_AVAILABLE"
    ):
        raise ContractError("KNOWLEDGE_INTERFACE_MUST_REMAIN_CLOSED")
    if document["tool"] == "get_chapter_evidence_slice" and status == "EMPTY":
        if reason != "NO_MATCHING_ENTRIES" or empty_scope != (
            "current_confirmed_facts_for_selected_chapter_revision"
        ):
            raise ContractError("CHAPTER_EMPTY_SEMANTICS_INVALID")
    if document["tool"] == "get_character_state_as_of" and status == "EMPTY":
        if reason != "NOT_RECORDED":
            raise ContractError("CHARACTER_EMPTY_SEMANTICS_INVALID")
    if document["receipt"]["basis_sha256"] != basis_sha256(document):
        raise ContractError("BASIS_SHA256_MISMATCH")
    return document


def _validate_capability_snapshot(document: dict[str, Any]) -> dict[str, Any]:
    names = tuple(item["ledger_name"] for item in document["ledgers"])
    if names != TEN_LEDGER_NAMES:
        raise ContractError("CAPABILITY_LEDGER_ORDER_INVALID")
    for index, item in enumerate(document["ledgers"]):
        if item["visibility"] == "MASKED" and (
            item["content_status"] != "UNKNOWN"
            or item["source_watermark"] is not None
        ):
            raise ContractError(f"MASKED_LEDGER_STATE_LEAK:{index}")
    return document


def validate_document(document: Any) -> dict[str, Any]:
    _validate_schema(document)
    assert isinstance(document, dict)
    contract = document["contract"]
    if document["version"] != VERSION:
        raise ContractError("CONTRACT_VERSION_INVALID")
    if contract == "LEDGER_READ_REQUEST":
        return _validate_request(document)
    if contract == "LEDGER_READ_RESPONSE":
        return _validate_response(document)
    if contract == "LEDGER_CAPABILITY_SNAPSHOT":
        return _validate_capability_snapshot(document)
    raise ContractError("CONTRACT_IDENTITY_INVALID")


def _logical_response_view(document: dict[str, Any]) -> dict[str, Any]:
    receipt = document["receipt"]
    limits = document["limits"]
    return {
        "status": document["status"],
        "reason_code": document["reason_code"],
        "tool": document["tool"],
        "basis_mode": document["basis_mode"],
        "data": document["data"],
        "empty_scope": document["empty_scope"],
        "receipt": {
            "author_id": receipt["author_id"],
            "project_id": receipt["project_id"],
            "permission_policy_version": receipt["permission_policy_version"],
            "tool_contract_version": receipt["tool_contract_version"],
            "source_manifest": receipt["source_manifest"],
            "basis_sha256": receipt["basis_sha256"],
        },
        "limits": {
            "policy_version": limits["policy_version"],
            "business_items": limits["business_items"],
            "truncated": limits["truncated"],
        },
    }


def validate_storage_equivalence(left: Any, right: Any) -> None:
    left_record = validate_document(left)
    right_record = validate_document(right)
    if left_record["contract"] != "LEDGER_READ_RESPONSE" or right_record[
        "contract"
    ] != "LEDGER_READ_RESPONSE":
        raise ContractError("EQUIVALENCE_REQUIRES_RESPONSES")
    if _logical_response_view(left_record) != _logical_response_view(right_record):
        raise ContractError("STORAGE_LOGICAL_EQUIVALENCE_FAILED")


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = [row.get("case_id") for row in rows]
    if len(ids) != len(set(ids)):
        raise ContractError("FIXTURE_CASE_ID_DUPLICATE")
    return rows


def validate_fixture_case(case: dict[str, Any]) -> str | None:
    try:
        if case["fixture_kind"] == "document":
            validate_document(case["document"])
        elif case["fixture_kind"] == "equivalence":
            validate_storage_equivalence(case["left"], case["right"])
        else:
            raise ContractError("FIXTURE_KIND_INVALID")
    except ContractError as exc:
        error = str(exc)
        if case.get("valid") is True:
            raise ContractError(
                f"FIXTURE_EXPECTED_VALID:{case['case_id']}:{error}"
            ) from exc
        expected = case.get("expected_error")
        if not expected or not error.startswith(expected):
            raise ContractError(
                f"FIXTURE_ERROR_MISMATCH:{case['case_id']}:"
                f"expected={expected}:actual={error}"
            ) from exc
        return error
    if case.get("valid") is False:
        raise ContractError(f"FIXTURE_EXPECTED_FAILURE_BUT_PASSED:{case['case_id']}")
    return None


def validate_all_fixtures(path: Path = FIXTURE_PATH) -> dict[str, int]:
    rows = load_fixtures(path)
    invalid = sum(validate_fixture_case(case) is not None for case in rows)
    return {"cases": len(rows), "valid": len(rows) - invalid, "invalid": invalid}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", action="store_true")
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    if args.fixtures:
        counts = validate_all_fixtures()
        print(
            "PASS_LEDGER_READ_TOOL_CONTRACT "
            f"cases={counts['cases']} valid={counts['valid']} "
            f"invalid={counts['invalid']}"
        )
        return 0
    if args.input is None:
        parser.error("--input or --fixtures is required")
    validate_document(json.loads(args.input.read_text(encoding="utf-8")))
    print("PASS_LEDGER_READ_TOOL_CONTRACT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
