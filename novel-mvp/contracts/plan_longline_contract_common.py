"""Shared mechanics for L5 plan-ledger long-line content contracts."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

CONTRACTS_DIR = Path(__file__).resolve().parent
LEGACY_KEYS = {"story" + "_sequence", "text" + "_sha256"}
PLAN_SOURCE_IDENTITIES = ("author_declared", "draft_inferred", "model_suggested")
CONFIRM_STATUSES = ("candidate", "confirmed", "retired")
RETIRED_NOTICE_TEXT = "此条已改判／退役"


class ContractError(ValueError):
    """A long-line plan-ledger contract invariant failed."""


def load_schema(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


def _schema_path(error: Any) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "$"


def _walk_keys(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            result.append(str(key))
            result.extend(_walk_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            result.extend(_walk_keys(nested))
    return result


def validate_schema(document: Any, schema: dict[str, Any]) -> None:
    legacy = sorted(set(_walk_keys(document)) & LEGACY_KEYS)
    if legacy:
        raise ContractError("LEGACY_STORY_ANCHOR_KEY_FORBIDDEN:" + ",".join(legacy))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(document),
        key=lambda item: (list(item.absolute_path), item.message),
    )
    if errors:
        first = errors[0]
        raise ContractError(f"SCHEMA_INVALID:{_schema_path(first)}:{first.validator}")


def parse_datetime(value: str, label: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractError(f"{label}_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f"{label}_TIMEZONE_REQUIRED")
    return parsed


def validate_confirm_and_evidence(document: dict[str, Any]) -> None:
    refs = document["evidence_refs"]
    if document["confirm_status"] == "confirmed" and not refs:
        raise ContractError("CONFIRMED_REQUIRES_EVIDENCE")
    if "AUTHOR_ATTESTATION" in refs and (
        document["source_identity"] != "author_declared"
        or document["confirm_status"] != "confirmed"
    ):
        raise ContractError(
            "AUTHOR_ATTESTATION_REQUIRES_AUTHOR_DECLARED_CONFIRMED"
        )


def validate_plan_root(
    document: Any,
    *,
    schema: dict[str, Any],
    contract: str,
    version: str,
    prefix: str,
) -> dict[str, Any]:
    validate_schema(document, schema)
    assert isinstance(document, dict)
    if document["contract"] != contract or document["version"] != version:
        raise ContractError("CONTRACT_IDENTITY_INVALID")
    if not document["id"].startswith(prefix):
        raise ContractError("PLAN_ID_PREFIX_INVALID")
    created = parse_datetime(document["created_at"], "CREATED_AT")
    updated = parse_datetime(document["updated_at"], "UPDATED_AT")
    if updated < created:
        raise ContractError("UPDATED_AT_BEFORE_CREATED_AT")
    validate_confirm_and_evidence(document)
    return document


def validate_expected_at(value: Any) -> None:
    """Cross-field checks beyond schema for the expected_at tagged union."""

    if value is None:
        return
    if value["kind"] == "fuzzy_anchor" and value["scope"] != value["scope"].strip():
        raise ContractError("FUZZY_SCOPE_MUST_BE_TRIMMED")


def expected_at_alarm_policy(value: Any) -> dict[str, str]:
    """Fuzzy anchors remind only; they never raise reconciliation alarms."""

    if value is None:
        return {"policy": "NONE"}
    kind = value["kind"]
    if kind == "slot_anchor":
        return {"policy": "MAPPED_TO_SLOT"}
    if kind == "story_time_anchor":
        return {"policy": "STORY_TIME_COMPARE"}
    if kind == "fuzzy_anchor":
        return {"policy": "REMIND_ONLY"}
    raise ContractError(f"EXPECTED_AT_KIND_UNKNOWN:{kind}")


def load_fixtures(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = [row.get("case_id") for row in rows]
    if any(not isinstance(case_id, str) or not case_id for case_id in ids):
        raise ContractError("FIXTURE_CASE_ID_INVALID")
    if len(ids) != len(set(ids)):
        raise ContractError("FIXTURE_CASE_ID_DUPLICATE")
    return rows


def validate_fixture_case(
    case: dict[str, Any],
    handlers: dict[str, Callable[[dict[str, Any]], Any]],
) -> str | None:
    handler = handlers.get(case["fixture_kind"])
    if handler is None:
        raise ContractError("FIXTURE_KIND_INVALID")
    try:
        actual: Any = handler(case)
    except ContractError as exc:
        error = str(exc)
        if case["expect"] != "FAIL":
            raise
        expected = case.get("expected_error")
        prefix = case.get("expected_error_prefix")
        if expected is not None and error != expected:
            raise ContractError(
                f"FIXTURE_WRONG_ERROR:{case['case_id']}:{error}"
            ) from exc
        if prefix is not None and not error.startswith(prefix):
            raise ContractError(
                f"FIXTURE_WRONG_ERROR_PREFIX:{case['case_id']}:{error}"
            ) from exc
        return error
    if case["expect"] == "FAIL":
        raise ContractError(
            f"FIXTURE_EXPECTED_FAILURE_BUT_PASSED:{case['case_id']}"
        )
    if "expected_result" in case and actual != case["expected_result"]:
        raise ContractError(
            f"FIXTURE_RESULT_MISMATCH:{case['case_id']}:{actual}"
        )
    return None


def validate_all_fixtures(
    path: Path,
    handlers: dict[str, Callable[[dict[str, Any]], Any]],
) -> dict[str, int]:
    rows = load_fixtures(path)
    invalid = sum(
        validate_fixture_case(case, handlers) is not None for case in rows
    )
    return {"cases": len(rows), "valid": len(rows) - invalid, "invalid": invalid}
