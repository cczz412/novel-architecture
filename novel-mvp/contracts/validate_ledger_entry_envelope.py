"""Validate versioned LEDGER_ENTRY_ENVELOPE entries and author edits."""

from __future__ import annotations

import argparse
from datetime import datetime
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker


CONTRACTS_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = CONTRACTS_DIR / "LEDGER_ENTRY_ENVELOPE.schema.json"
V1_SCHEMA_PATH = CONTRACTS_DIR / "LEDGER_ENTRY_ENVELOPE.v1.schema.json"
FIXTURE_PATH = CONTRACTS_DIR / "LEDGER_ENTRY_ENVELOPE.fixtures.jsonl"

CONTRACT_NAME = "LEDGER_ENTRY_ENVELOPE"
CONTRACT_VERSION_V1 = "ledger-entry-envelope-v1"
CONTRACT_VERSION_V2 = "ledger-entry-envelope-v2"
CONTRACT_VERSION = CONTRACT_VERSION_V2
ENTRY_KINDS = frozenset({"DEFINITION", "STATE", "CHANGE"})
SOURCE_IDENTITIES = frozenset(
    {"author_declared", "draft_inferred", "model_suggested", "pack_prefilled"}
)
CONFIRM_STATUSES = frozenset({"candidate", "confirmed", "retired"})
TRANSITION_RULES = frozenset({"confirmation_forward_v1"})
CORE_GROUP_SHAPES = {
    "core:identity": {
        "members": frozenset({"core:identity"}),
        "targets": frozenset({"/id", "/created_at"}),
        "mutation": "write_once",
        "transition_rule": None,
        "managed_by": "CONTRACT",
        "write": frozenset({"SYSTEM"}),
    },
    "core:confirmation": {
        "members": frozenset({"core:confirmation"}),
        "targets": frozenset({"/confirm_status"}),
        "mutation": "transition_only",
        "transition_rule": "confirmation_forward_v1",
        "managed_by": "CONTRACT",
        "write": frozenset({"AUTHOR"}),
    },
    "core:revision": {
        "members": frozenset({"core:revision"}),
        "targets": frozenset({"/rev", "/updated_at"}),
        "mutation": "editable",
        "transition_rule": None,
        "managed_by": "CONTRACT",
        "write": frozenset({"SYSTEM"}),
    },
}
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


def _load_schema(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


SCHEMAS = {
    CONTRACT_VERSION_V1: _load_schema(V1_SCHEMA_PATH),
    CONTRACT_VERSION_V2: _load_schema(SCHEMA_PATH),
}


def _schema_path(error: Any) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "$"


def _validate_schema(document: Any, *, contract_version: str) -> None:
    try:
        schema = SCHEMAS[contract_version]
    except KeyError as exc:
        raise ContractError("CONTRACT_VERSION_INVALID") from exc
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(document),
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


def _validate_tag_groups(
    document: dict[str, Any], *, allowed_targets: frozenset[str] | None
) -> None:
    tags = document["tags"]
    tag_groups = document["tag_groups"]
    if len(tags) != len(set(tags)):
        raise ContractError("TAGS_MUST_BE_UNIQUE")
    if any(":" not in tag or tag.split(":", 1)[0] == "" for tag in tags):
        raise ContractError("TAG_NAMESPACE_REQUIRED")
    if tag_groups["rules_version"] != "tag-group-rules-v1":
        raise ContractError("TAG_GROUP_RULES_VERSION_UNKNOWN")
    groups = tag_groups["groups"]
    group_ids = [group["group_id"] for group in groups]
    if len(group_ids) != len(set(group_ids)):
        raise ContractError("TAG_GROUP_ID_DUPLICATE")
    required_core_groups = set(CORE_GROUP_SHAPES)
    if not required_core_groups <= set(group_ids):
        raise ContractError("TAG_GROUP_REQUIRED_CORE_GROUP_MISSING")
    tag_set = set(tags)
    covered_tags: set[str] = set()
    for group in groups:
        members = group["members"]
        if not set(members) <= tag_set:
            raise ContractError("TAG_GROUP_MEMBER_NOT_IN_TAGS")
        covered_tags.update(members)
        targets = group["targets"]
        if allowed_targets is not None:
            unknown = sorted(set(targets) - allowed_targets)
            if unknown:
                raise ContractError(
                    "TAG_GROUP_TARGET_NOT_ALLOWED:" + ",".join(unknown)
                )
        mutation = group["mutation"]
        transition_rule = group["transition_rule"]
        if mutation == "transition_only" and not transition_rule:
            raise ContractError("TRANSITION_RULE_REQUIRED")
        if transition_rule is not None and transition_rule not in TRANSITION_RULES:
            raise ContractError("TRANSITION_RULE_UNKNOWN")
        if mutation != "transition_only" and transition_rule is not None:
            raise ContractError("TRANSITION_RULE_ONLY_FOR_TRANSITION_MUTATION")
        if not group["access"]["read"] or not group["access"]["write"]:
            raise ContractError("TAG_GROUP_ACCESS_MUST_NOT_BE_EMPTY")
        required_shape = CORE_GROUP_SHAPES.get(group["group_id"])
        if group["group_id"].startswith("core:") and required_shape is None:
            raise ContractError("CORE_GROUP_UNKNOWN")
        if required_shape is not None and (
            set(group["members"]) != required_shape["members"]
            or set(group["targets"]) != required_shape["targets"]
            or group["mutation"] != required_shape["mutation"]
            or group["transition_rule"] != required_shape["transition_rule"]
            or group["managed_by"] != required_shape["managed_by"]
            or set(group["access"]["write"]) != required_shape["write"]
        ):
            raise ContractError("CORE_PROTECTION_SHAPE_INVALID")
    if covered_tags != tag_set:
        raise ContractError("TAG_MISSING_REQUIRED_GROUP")


def validate_entry(
    document: Any,
    *,
    entry_kind: str,
    contract_version: str | None = None,
    allowed_targets: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Validate one common envelope in its content-contract context."""

    if contract_version is None:
        contract_version = (
            CONTRACT_VERSION_V2
            if isinstance(document, dict)
            and ("tags" in document or "tag_groups" in document)
            else CONTRACT_VERSION_V1
        )
    if entry_kind not in ENTRY_KINDS:
        raise ContractError("ENTRY_KIND_INVALID")
    _validate_schema(document, contract_version=contract_version)
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
        if not (
            contract_version == CONTRACT_VERSION_V2 and confirm_status == "retired"
        ):
            raise ContractError("PACK_PREFILLED_MUST_REMAIN_CANDIDATE")
    if confirm_status == "confirmed" and not evidence_refs:
        raise ContractError("CONFIRMED_EVIDENCE_REQUIRED")
    if (
        contract_version == CONTRACT_VERSION_V2
        and confirm_status == "confirmed"
        and source_identity != "author_declared"
    ):
        raise ContractError("CONFIRMED_REQUIRES_AUTHOR_DECLARED")

    has_attestation = "AUTHOR_ATTESTATION" in evidence_refs
    if has_attestation and source_identity != "author_declared":
        raise ContractError("AUTHOR_ATTESTATION_REQUIRES_AUTHOR_DECLARED")
    if has_attestation:
        allowed_statuses = (
            {"confirmed", "retired"}
            if contract_version == CONTRACT_VERSION_V2
            else {"confirmed"}
        )
        if confirm_status not in allowed_statuses:
            if contract_version == CONTRACT_VERSION_V1:
                raise ContractError("AUTHOR_ATTESTATION_REQUIRES_CONFIRMED")
            raise ContractError("AUTHOR_ATTESTATION_REQUIRES_CONFIRMED_OR_RETIRED")

    if contract_version == CONTRACT_VERSION_V2:
        _validate_tag_groups(document, allowed_targets=allowed_targets)

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
    contract_version: str,
    content_before: Any,
    content_after: Any,
) -> None:
    """Validate the approved pack-prefilled → author-declared edit transition."""

    version = contract_version
    if not isinstance(version, str) or version not in SCHEMAS:
        raise ContractError("CONTRACT_VERSION_INVALID")
    validate_entry(before, entry_kind="DEFINITION", contract_version=version)
    validate_entry(after, entry_kind="DEFINITION", contract_version=version)
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
    if version == CONTRACT_VERSION_V2:
        validate_confirmation_transition(
            before, after, actor="AUTHOR", contract_version=version,
            business_before=content_before, business_after=content_after,
        )


@lru_cache(maxsize=6)
def _retirement_host_validator(contract_name: str) -> Any:
    hosts = {
        "CHARACTER_LEDGER_CONTENT": "character",
        "LOCATION_LEDGER_CONTENT": "location",
        "ITEM_LEDGER_CONTENT": "item",
        "FACTION_LEDGER_CONTENT": "faction",
        "SYSTEM_LEDGER_CONTENT": "system",
        "WORLD_RULE_LEDGER_CONTENT": "world_rule",
    }
    host = hosts.get(contract_name)
    if host is None:
        raise ContractError("RETIREMENT_FULL_RECORD_REQUIRED")
    path = CONTRACTS_DIR / f"validate_{host}_ledger_content.py"
    spec = importlib.util.spec_from_file_location(f"retirement_host_{host}", path)
    if spec is None or spec.loader is None:
        raise ContractError("RETIREMENT_HOST_VALIDATOR_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _retirement_body(record: Any, entry: dict[str, Any], version: str) -> dict[str, Any]:
    """Validate a complete host record, bind its envelope, then derive its body."""
    if not isinstance(record, dict) or not isinstance(record.get("contract"), str):
        raise ContractError("RETIREMENT_FULL_RECORD_REQUIRED")
    host = _retirement_host_validator(record["contract"])
    record_version = record.get("version")
    if not isinstance(record_version, str) or (
        record_version.endswith("-v2") != (version == CONTRACT_VERSION_V2)
    ):
        raise ContractError("RETIREMENT_RECORD_VERSION_MISMATCH")
    try:
        host.validate_record(record)
    except host.ContractError as exc:
        raise ContractError(f"RETIREMENT_RECORD_INVALID:{exc}") from exc
    if any(record.get(key) != value for key, value in entry.items()):
        raise ContractError("RETIREMENT_RECORD_ENVELOPE_MISMATCH")
    return {key: value for key, value in record.items() if key not in entry}


def validate_confirmation_transition(
    before: Any,
    after: Any,
    *,
    actor: str,
    contract_version: str,
    business_before: Any = None,
    business_after: Any = None,
) -> None:
    """Validate the forward-only confirmation/lifecycle transition."""

    version = contract_version
    if not isinstance(version, str) or version not in SCHEMAS:
        raise ContractError("CONTRACT_VERSION_INVALID")
    if (
        isinstance(before, dict)
        and isinstance(after, dict)
        and before.get("confirm_status") == "confirmed"
        and after.get("confirm_status") == "candidate"
    ):
        raise ContractError("CONFIRMED_CANNOT_RETURN_TO_CANDIDATE")
    validate_entry(before, entry_kind="DEFINITION", contract_version=version)
    validate_entry(after, entry_kind="DEFINITION", contract_version=version)
    assert isinstance(before, dict) and isinstance(after, dict)
    if before["id"] != after["id"]:
        raise ContractError("TRANSITION_ID_MUST_STAY_STABLE")
    if before["rev"] + 1 != after["rev"]:
        raise ContractError("TRANSITION_REV_MUST_INCREMENT")
    if before["created_at"] != after["created_at"]:
        raise ContractError("TRANSITION_CREATED_AT_MUST_STAY_STABLE")
    if version == CONTRACT_VERSION_V2:
        before_groups = {
            group["group_id"]: group for group in before["tag_groups"]["groups"]
        }
        after_groups = {
            group["group_id"]: group for group in after["tag_groups"]["groups"]
        }
        for group_id, group in before_groups.items():
            if group["managed_by"] == "CONTRACT" and (
                after_groups.get(group_id) != group
            ):
                raise ContractError("CONTRACT_GROUP_IMMUTABLE")
    before_updated = _parse_datetime(before["updated_at"], label="BEFORE_UPDATED_AT")
    after_updated = _parse_datetime(after["updated_at"], label="AFTER_UPDATED_AT")
    if after_updated <= before_updated:
        raise ContractError("TRANSITION_UPDATED_AT_MUST_ADVANCE")

    old_status = before["confirm_status"]
    new_status = after["confirm_status"]
    if old_status == "retired" and new_status != "retired":
        raise ContractError("RETIRED_CANNOT_BE_RESTORED")
    if old_status == "confirmed" and new_status == "candidate":
        raise ContractError("CONFIRMED_CANNOT_RETURN_TO_CANDIDATE")
    if old_status == "candidate" and new_status == "confirmed":
        if actor != "AUTHOR":
            raise ContractError("CONFIRMATION_REQUIRES_AUTHOR")
        if after["source_identity"] != "author_declared" or not after["evidence_refs"]:
            raise ContractError("CONFIRMATION_REQUIRES_AUTHOR_EVIDENCE")
        if before["source_identity"] == "pack_prefilled":
            if "AUTHOR_ATTESTATION" not in after["evidence_refs"]:
                raise ContractError("AUTHOR_EDIT_REQUIRES_ATTESTATION")
            if _pack_ref(business_before, label="BEFORE") != _pack_ref(
                business_after, label="AFTER"
            ):
                raise ContractError("PACK_REF_MUST_BE_PRESERVED")
    elif old_status in {"candidate", "confirmed"} and new_status == "retired":
        if actor != "AUTHOR":
            raise ContractError("RETIREMENT_REQUIRES_AUTHOR")
        if "AUTHOR_ATTESTATION" in before["evidence_refs"] and (
            "AUTHOR_ATTESTATION" not in after["evidence_refs"]
        ):
            raise ContractError("RETIREMENT_MUST_PRESERVE_ATTESTATION")
        if "AUTHOR_ATTESTATION" not in before["evidence_refs"] and (
            "AUTHOR_ATTESTATION" in after["evidence_refs"]
        ):
            raise ContractError("RETIREMENT_MUST_NOT_CREATE_ATTESTATION")
        if business_before is None or business_after is None:
            raise ContractError("RETIREMENT_BUSINESS_SNAPSHOTS_REQUIRED")
        before_body = _retirement_body(business_before, before, version)
        after_body = _retirement_body(business_after, after, version)
        if before_body != after_body:
            raise ContractError("RETIREMENT_MUST_NOT_CHANGE_CONTENT")
        lifecycle_fields = {"confirm_status", "rev", "updated_at"}
        if ({key: value for key, value in before.items() if key not in lifecycle_fields}
                != {key: value for key, value in after.items() if key not in lifecycle_fields}):
            raise ContractError("RETIREMENT_MUST_PRESERVE_ENVELOPE")
    elif old_status == "confirmed" and new_status == "confirmed":
        if actor != "AUTHOR":
            raise ContractError("CONFIRMED_EDIT_REQUIRES_AUTHOR")
    elif old_status == "candidate" and new_status == "candidate":
        if (
            after["source_identity"] == "pack_prefilled"
            and before["source_identity"] != "pack_prefilled"
        ):
            raise ContractError("PACK_PROVENANCE_CANNOT_BE_CREATED_BY_TRANSITION")
        if before["source_identity"] == "pack_prefilled":
            if after["source_identity"] != "pack_prefilled":
                raise ContractError("AUTHOR_EDIT_STATUS_MUST_BECOME_CONFIRMED")
            if business_before is None or business_after is None:
                raise ContractError("PACK_CANDIDATE_BUSINESS_SNAPSHOTS_REQUIRED")
            if _pack_ref(business_before, label="BEFORE") != _pack_ref(
                business_after, label="AFTER"
            ):
                raise ContractError("PACK_REF_MUST_BE_PRESERVED")
            if business_before != business_after:
                raise ContractError("PACK_CONTENT_EDIT_REQUIRES_AUTHOR_MIGRATION")
        return
    elif old_status == new_status == "retired":
        raise ContractError("RETIRED_CANNOT_BE_EDITED")
    else:
        raise ContractError("CONFIRMATION_TRANSITION_INVALID")


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
            document = case.get("document")
            version = case.get("contract_version")
            if version is None:
                version = (
                    CONTRACT_VERSION_V2
                    if isinstance(document, dict)
                    and ("tags" in document or "tag_groups" in document)
                    else CONTRACT_VERSION_V1
                )
            validate_entry(
                document,
                entry_kind=case.get("entry_kind"),
                contract_version=version,
            )
        elif kind == "pack_author_edit_transition":
            validate_pack_prefilled_author_edit(
                case.get("before"),
                case.get("after"),
                contract_version=case.get("contract_version", CONTRACT_VERSION_V1),
                content_before=case.get("content_before"),
                content_after=case.get("content_after"),
            )
        elif kind == "confirmation_transition":
            validate_confirmation_transition(
                case.get("before"),
                case.get("after"),
                contract_version=case.get("contract_version", CONTRACT_VERSION_V1),
                actor=case.get("actor"),
                business_before=case.get("business_before"),
                business_after=case.get("business_after"),
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
    versions = {
        case.get("contract_version")
        or (
            CONTRACT_VERSION_V2
            if isinstance(case.get("document"), dict)
            and (
                "tags" in case["document"]
                or "tag_groups" in case["document"]
            )
            else CONTRACT_VERSION_V1
        )
        for case in cases
    }
    summary = {
        "contract": CONTRACT_NAME,
        "version": next(iter(versions)) if len(versions) == 1 else "mixed",
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
