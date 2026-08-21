"""Validate LEDGER_ENTRY_ENVELOPE v1 entries and pack-prefilled author edits."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker


CONTRACTS_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = CONTRACTS_DIR / "LEDGER_ENTRY_ENVELOPE.schema.json"
FIXTURE_PATH = CONTRACTS_DIR / "LEDGER_ENTRY_ENVELOPE.fixtures.jsonl"

CONTRACT_NAME = "LEDGER_ENTRY_ENVELOPE"
CONTRACT_VERSION = "ledger-entry-envelope-v1"
ENTRY_KINDS = frozenset({"DEFINITION", "STATE", "CHANGE"})
SOURCE_IDENTITIES = frozenset(
    {"author_declared", "draft_inferred", "model_suggested", "pack_prefilled"}
)
CONFIRM_STATUSES = frozenset({"candidate", "confirmed", "retired"})
ID_PREFIXES = {
    "人物账": "CH-",
    "地点账": "LOC-",
    "物品账": "IT-",
    "势力账": "FA-",
    "体系账": "SY-",
    "世界规则账": "RU-",
}
SYSTEM_TIME_KEYS = frozenset(
    {
        "created_at",
        "updated_at",
        "recorded_at",
        "committed_at",
        "system_time",
        "timestamp",
    }
)


class ContractError(ValueError):
    """A frozen common-envelope invariant failed."""


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


def _parse_datetime(value: str, *, label: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:  # schema format checker normally catches this first
        raise ContractError(f"{label}_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f"{label}_TIMEZONE_REQUIRED")
    return parsed


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _walk_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_keys(nested)


def validate_entry(document: Any, *, entry_kind: str) -> dict[str, Any]:
    """Validate one common envelope in its content-contract context."""

    if entry_kind not in ENTRY_KINDS:
        raise ContractError("ENTRY_KIND_INVALID")
    _validate_schema(document)
    assert isinstance(document, dict)

    created_at = _parse_datetime(document["created_at"], label="CREATED_AT")
    updated_at = _parse_datetime(document["updated_at"], label="UPDATED_AT")
    if updated_at < created_at:
        raise ContractError("UPDATED_AT_BEFORE_CREATED_AT")

    story_time = document["story_time"]
    if entry_kind == "DEFINITION" and story_time is not None:
        raise ContractError("STORY_TIME_FORBIDDEN_FOR_DEFINITION")
    if isinstance(story_time, dict):
        forbidden = sorted(set(_walk_keys(story_time)) & SYSTEM_TIME_KEYS)
        if forbidden:
            raise ContractError(
                "SYSTEM_TIME_CANNOT_STAND_IN_FOR_STORY_TIME:"
                + ",".join(forbidden)
            )

    source_identity = document["source_identity"]
    confirm_status = document["confirm_status"]
    evidence_refs = document["evidence_refs"]

    if source_identity == "pack_prefilled" and confirm_status != "candidate":
        raise ContractError("PACK_PREFILLED_MUST_REMAIN_CANDIDATE")
    if confirm_status == "confirmed" and not evidence_refs:
        raise ContractError("CONFIRMED_EVIDENCE_REQUIRED")

    has_attestation = "AUTHOR_ATTESTATION" in evidence_refs
    if has_attestation and source_identity != "author_declared":
        raise ContractError("AUTHOR_ATTESTATION_REQUIRES_AUTHOR_DECLARED")
    if has_attestation and confirm_status != "confirmed":
        raise ContractError("AUTHOR_ATTESTATION_REQUIRES_CONFIRMED")

    return document


def _pack_ref(content: Any, *, label: str) -> str:
    if not isinstance(content, dict):
        raise ContractError(f"{label}_CONTENT_NOT_OBJECT")
    value = content.get("pack_ref")
    if not isinstance(value, str) or not value or value != value.strip():
        raise ContractError(f"{label}_PACK_REF_REQUIRED")
    return value


def validate_pack_prefilled_author_edit(
    before: Any,
    after: Any,
    *,
    content_before: Any,
    content_after: Any,
) -> None:
    """Validate the approved pack-prefilled → author-declared edit transition."""

    validate_entry(before, entry_kind="DEFINITION")
    validate_entry(after, entry_kind="DEFINITION")
    assert isinstance(before, dict)
    assert isinstance(after, dict)

    if before["source_identity"] != "pack_prefilled":
        raise ContractError("AUTHOR_EDIT_BEFORE_MUST_BE_PACK_PREFILLED")
    if before["confirm_status"] != "candidate":
        raise ContractError("AUTHOR_EDIT_BEFORE_MUST_BE_CANDIDATE")
    if after["id"] != before["id"]:
        raise ContractError("AUTHOR_EDIT_ID_MUST_STAY_STABLE")
    if after["source_identity"] != "author_declared":
        raise ContractError("AUTHOR_EDIT_SOURCE_MUST_BECOME_AUTHOR_DECLARED")
    if after["confirm_status"] != "confirmed":
        raise ContractError("AUTHOR_EDIT_STATUS_MUST_BECOME_CONFIRMED")
    if "AUTHOR_ATTESTATION" not in after["evidence_refs"]:
        raise ContractError("AUTHOR_EDIT_REQUIRES_ATTESTATION")
    if after["rev"] != before["rev"] + 1:
        raise ContractError("AUTHOR_EDIT_REV_MUST_INCREMENT")
    if after["created_at"] != before["created_at"]:
        raise ContractError("AUTHOR_EDIT_CREATED_AT_MUST_STAY_STABLE")

    before_updated = _parse_datetime(before["updated_at"], label="BEFORE_UPDATED_AT")
    after_updated = _parse_datetime(after["updated_at"], label="AFTER_UPDATED_AT")
    if after_updated <= before_updated:
        raise ContractError("AUTHOR_EDIT_UPDATED_AT_MUST_ADVANCE")

    if _pack_ref(content_before, label="BEFORE") != _pack_ref(
        content_after, label="AFTER"
    ):
        raise ContractError("PACK_REF_MUST_BE_PRESERVED")


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContractError(f"FIXTURE_JSON_INVALID:{line_no}") from exc
        if not isinstance(value, dict):
            raise ContractError(f"FIXTURE_NOT_OBJECT:{line_no}")
        rows.append(value)
    ids = [row.get("case_id") for row in rows]
    if any(not isinstance(case_id, str) or not case_id for case_id in ids):
        raise ContractError("FIXTURE_CASE_ID_INVALID")
    if len(ids) != len(set(ids)):
        raise ContractError("FIXTURE_CASE_ID_DUPLICATE")
    return rows


def validate_fixture_case(case: dict[str, Any]) -> str | None:
    kind = case.get("fixture_kind")
    try:
        if kind == "entry":
            validate_entry(case.get("document"), entry_kind=case.get("entry_kind"))
        elif kind == "pack_author_edit_transition":
            validate_pack_prefilled_author_edit(
                case.get("before"),
                case.get("after"),
                content_before=case.get("content_before"),
                content_after=case.get("content_after"),
            )
        else:
            raise ContractError("FIXTURE_KIND_INVALID")
    except ContractError as exc:
        return str(exc)
    return None


def validate_fixture_suite(path: Path = FIXTURE_PATH) -> dict[str, Any]:
    cases = load_fixtures(path)
    mismatches: list[dict[str, Any]] = []
    for case in cases:
        error = validate_fixture_case(case)
        valid = bool(case.get("valid"))
        expected_error = case.get("expected_error")
        if valid:
            matches = error is None
        else:
            matches = (
                isinstance(expected_error, str)
                and error is not None
                and error.startswith(expected_error)
            )
        if not matches:
            mismatches.append(
                {
                    "case_id": case.get("case_id"),
                    "declared_valid": valid,
                    "expected_error": expected_error,
                    "actual_error": error,
                }
            )
    summary = {
        "contract": CONTRACT_NAME,
        "version": CONTRACT_VERSION,
        "status": "PASS" if not mismatches else "FAIL",
        "case_count": len(cases),
        "valid_case_count": sum(bool(case.get("valid")) for case in cases),
        "invalid_case_count": sum(not bool(case.get("valid")) for case in cases),
        "mismatches": mismatches,
    }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        type=Path,
        nargs="?",
        const=FIXTURE_PATH,
        help="Validate the fixture suite; defaults to the formal JSONL file.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture_path = args.fixtures or FIXTURE_PATH
    summary = validate_fixture_suite(fixture_path)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            f"{summary['status']}_LEDGER_ENTRY_ENVELOPE "
            f"cases={summary['case_count']} "
            f"valid={summary['valid_case_count']} "
            f"invalid={summary['invalid_case_count']}"
        )
        if summary["mismatches"]:
            print(json.dumps(summary["mismatches"], ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
