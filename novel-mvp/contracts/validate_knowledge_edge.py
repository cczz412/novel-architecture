"""Validate versioned KNOWLEDGE_EDGE v1/v2 contract documents."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "KNOWLEDGE_EDGE.schema.json"
FIXTURE_PATH = DIR / "KNOWLEDGE_EDGE.fixtures.jsonl"
VERSION_V1 = "knowledge-edge-v1"
VERSION_V2 = "knowledge-edge-v2"
# Backward-compatible aliases. New code should use the explicit version suffixes.
VERSION = VERSION_V1
PERMISSION_NAMESPACE_V1 = "knowledge-edge.v1"
PERMISSION_NAMESPACE_V2 = "knowledge-edge.v2"
WRITER_NAMESPACE_V1 = "trusted.knowledge_edge.writer.v1"
WRITER_NAMESPACE_V2 = "trusted.knowledge_edge.writer.v2"
PERMISSION_NAMESPACE = PERMISSION_NAMESPACE_V1
WRITER_NAMESPACE = WRITER_NAMESPACE_V1
VERSION_POLICIES = {
    VERSION_V1: {
        "permission_namespace": PERMISSION_NAMESPACE_V1,
        "writer_namespace": WRITER_NAMESPACE_V1,
    },
    VERSION_V2: {
        "permission_namespace": PERMISSION_NAMESPACE_V2,
        "writer_namespace": WRITER_NAMESPACE_V2,
    },
}
TASK_PRINCIPALS = {"MAIN_AI", "POV_CHECKER", "CHAPTER_CARD"}
CLOSED_PRINCIPALS = {"READER", "PLUGIN"}


class ContractError(ValueError):
    """A knowledge edge contract invariant failed."""


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


def _parse_datetime(value: str, label: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractError(f"{label}_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f"{label}_TIMEZONE_REQUIRED")
    return parsed


def _chapter_ref(anchor: dict[str, Any]) -> dict[str, Any]:
    return anchor["chapter_revision_ref"]


def _validate_story_interval(interval: dict[str, Any]) -> None:
    start = interval["start"]
    end = interval["end"]
    if end is None:
        return
    start_order = start.get("story_order")
    end_order = end.get("story_order")
    if start_order is not None and end_order is not None:
        if end_order <= start_order:
            raise ContractError("STORY_INTERVAL_END_NOT_AFTER_START")
        return
    if _chapter_ref(start) == _chapter_ref(end):
        raise ContractError("STORY_INTERVAL_END_EQUALS_START")


def _validate_edge(document: dict[str, Any]) -> dict[str, Any]:
    created = _parse_datetime(document["created_at"], "CREATED_AT")
    updated = _parse_datetime(document["updated_at"], "UPDATED_AT")
    if updated < created:
        raise ContractError("UPDATED_AT_BEFORE_CREATED_AT")
    rev = document["rev"]
    previous = document["previous_rev"]
    if rev == 1 and previous is not None:
        raise ContractError("FIRST_REVISION_PREVIOUS_REV_FORBIDDEN")
    if rev > 1 and previous != rev - 1:
        raise ContractError("PREVIOUS_REV_NOT_CONTIGUOUS")
    _validate_story_interval(document["story_time_interval"])
    if "AUTHOR_ATTESTATION" in document["evidence_refs"] and (
        document["source_identity"] != "author_declared"
        or document["version_status"]["confirmation"] != "author_confirmed"
    ):
        raise ContractError("AUTHOR_ATTESTATION_REQUIRES_AUTHOR_CONFIRMED")
    return document


def _validate_write_action(document: dict[str, Any]) -> dict[str, Any]:
    operation = document["operation"]
    edge_id = document["edge_id"]
    base_rev = document["base_rev"]
    requested_by = document["requested_by"]
    if operation == "PROPOSE_CANDIDATE":
        if edge_id is not None or base_rev is not None:
            raise ContractError("PROPOSE_CANDIDATE_MUST_NOT_PREASSIGN_EDGE")
        return document
    if requested_by != "AUTHOR":
        raise ContractError("AUTHOR_REQUIRED_FOR_FORMAL_ACTION")
    if edge_id is None or base_rev is None:
        raise ContractError("FORMAL_ACTION_TARGET_AND_BASE_REQUIRED")
    return document


def _validate_read_grant(document: dict[str, Any]) -> dict[str, Any]:
    principal = document["principal_kind"]
    access = document["access"]
    observer_refs = document["observer_refs"]
    fact_refs = document["fact_refs"]
    as_of = document["as_of"]
    if principal == "AUTHOR":
        if access != "FULL_PROJECT" or observer_refs or fact_refs or as_of is not None:
            raise ContractError("AUTHOR_GRANT_SHAPE_INVALID")
        return document
    if principal in TASK_PRINCIPALS:
        if (
            access != "TASK_SLICE"
            or not observer_refs
            or not fact_refs
            or as_of is None
        ):
            raise ContractError("TASK_GRANT_MUST_BE_MINIMALLY_SCOPED")
        return document
    if principal in CLOSED_PRINCIPALS:
        if access != "CLOSED" or observer_refs or fact_refs or as_of is not None:
            raise ContractError("CLOSED_GRANT_SHAPE_INVALID")
        return document
    raise ContractError("PRINCIPAL_KIND_INVALID")


def validate_document(document: Any) -> dict[str, Any]:
    _validate_schema(document)
    assert isinstance(document, dict)
    version = document["version"]
    if version not in VERSION_POLICIES:
        raise ContractError("CONTRACT_VERSION_INVALID")
    contract = document["contract"]
    if contract == "KNOWLEDGE_EDGE":
        if document["permission_namespace"] != VERSION_POLICIES[version][
            "permission_namespace"
        ]:
            raise ContractError("PERMISSION_NAMESPACE_VERSION_MISMATCH")
        return _validate_edge(document)
    if contract == "KNOWLEDGE_EDGE_WRITE_ACTION":
        if document["writer_namespace"] != VERSION_POLICIES[version][
            "writer_namespace"
        ]:
            raise ContractError("WRITER_NAMESPACE_VERSION_MISMATCH")
        return _validate_write_action(document)
    if contract == "KNOWLEDGE_EDGE_READ_GRANT":
        if document["permission_namespace"] != VERSION_POLICIES[version][
            "permission_namespace"
        ]:
            raise ContractError("PERMISSION_NAMESPACE_VERSION_MISMATCH")
        return _validate_read_grant(document)
    raise ContractError("CONTRACT_IDENTITY_INVALID")


def validate_document_for_reader(document: Any, reader_version: str) -> dict[str, Any]:
    if not isinstance(reader_version, str) or reader_version not in VERSION_POLICIES:
        raise ContractError("READER_VERSION_INVALID")
    if not isinstance(document, dict) or document.get("contract") != "KNOWLEDGE_EDGE":
        raise ContractError("READER_DOCUMENT_TYPE_INVALID")
    document_version = document.get("version")
    if (
        not isinstance(document_version, str)
        or document_version not in VERSION_POLICIES
        or (reader_version == VERSION_V1 and document_version != VERSION_V1)
    ):
        raise ContractError("READER_VERSION_UNSUPPORTED")
    return validate_document(document)


def validate_edge_grant_for_reader(
    edge: Any,
    grant: Any,
    reader_version: str,
) -> None:
    if not isinstance(grant, dict) or grant.get("contract") != (
        "KNOWLEDGE_EDGE_READ_GRANT"
    ):
        raise ContractError("READ_GRANT_DOCUMENT_TYPE_INVALID")
    authorization = validate_document(grant)
    if authorization["access"] == "CLOSED":
        raise ContractError("UNAUTHORIZED")
    if (
        not isinstance(edge, dict)
        or edge.get("author_id") != authorization["author_id"]
        or edge.get("project_id") != authorization["project_id"]
    ):
        raise ContractError("UNAUTHORIZED")
    if edge.get("version") != authorization["version"]:
        raise ContractError("READ_GRANT_VERSION_MISMATCH")
    if authorization["access"] == "TASK_SLICE" and (
        edge.get("observer_ref") not in authorization["observer_refs"]
        or edge.get("fact_ref") not in authorization["fact_refs"]
    ):
        raise ContractError("READ_GRANT_SCOPE_MISMATCH")

    if authorization["access"] == "TASK_SLICE":
        _prevalidate_task_edge_eligibility(edge, authorization["as_of"])
    record = validate_document_for_reader(edge, reader_version)
    if authorization["access"] == "TASK_SLICE":
        _validate_task_edge_as_of(record, authorization["as_of"])


def _prevalidate_task_edge_eligibility(
    record: dict[str, Any],
    as_of: dict[str, Any],
) -> None:
    try:
        _validate_task_edge_as_of(record, as_of)
    except ContractError:
        raise
    except (AttributeError, KeyError, TypeError):
        return


def _validate_task_edge_as_of(
    record: dict[str, Any],
    as_of: dict[str, Any],
) -> None:
    if record["version_status"] != {
        "confirmation": "author_confirmed",
        "lifecycle": "active",
    }:
        raise ContractError("TASK_GRANT_REQUIRES_ACTIVE_AUTHOR_CONFIRMED_EDGE")

    interval = record["story_time_interval"]
    start = interval["start"]
    end = interval["end"]
    start_order = start.get("story_order")
    as_of_order = as_of.get("story_order")
    end_order = None if end is None else end.get("story_order")
    start_is_comparable = start_order is not None and as_of_order is not None
    end_is_comparable = (
        end is not None and end_order is not None and as_of_order is not None
    )
    as_of_ref = _chapter_ref(as_of)
    if start_is_comparable:
        if as_of_order < start_order:
            raise ContractError("READ_GRANT_AS_OF_BEFORE_EDGE_START")
        lower_bound_satisfied = True
    else:
        lower_bound_satisfied = as_of_ref == _chapter_ref(start)

    if end is None:
        upper_bound_satisfied = True
    elif end_is_comparable:
        if as_of_order >= end_order:
            raise ContractError("READ_GRANT_AS_OF_OUTSIDE_EDGE_INTERVAL")
        upper_bound_satisfied = True
    else:
        if as_of_ref == _chapter_ref(end):
            raise ContractError("READ_GRANT_AS_OF_OUTSIDE_EDGE_INTERVAL")
        upper_bound_satisfied = as_of_ref == _chapter_ref(start)

    if lower_bound_satisfied and upper_bound_satisfied:
        return
    raise ContractError("READ_GRANT_AS_OF_UNDETERMINED")


def _story_order_bounds(
    interval: dict[str, Any],
) -> tuple[int, int | None] | None:
    start_order = interval["start"].get("story_order")
    end = interval["end"]
    end_order = None if end is None else end.get("story_order")
    if start_order is None or (end is not None and end_order is None):
        return None
    return start_order, end_order


def _same_revision_ref_without_order_conflict(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    same_ref = _chapter_ref(left) == _chapter_ref(right)
    left_order = left.get("story_order")
    right_order = right.get("story_order")
    if (
        same_ref
        and left_order is not None
        and right_order is not None
        and left_order != right_order
    ):
        raise ContractError("STORY_INTERVAL_OVERLAP_UNDETERMINED")
    return same_ref


def _end_proves_non_overlap(
    end: dict[str, Any] | None,
    start: dict[str, Any],
) -> bool | None:
    if end is None:
        return None
    same_ref = _same_revision_ref_without_order_conflict(end, start)
    end_order = end.get("story_order")
    start_order = start.get("story_order")
    if end_order is not None and start_order is not None:
        return end_order <= start_order
    if same_ref:
        return True
    return None


def _story_intervals_overlap(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    left_start = left["start"]
    left_end = left["end"]
    right_start = right["start"]
    right_end = right["end"]
    if _end_proves_non_overlap(left_end, right_start) is True:
        return False
    if _end_proves_non_overlap(right_end, left_start) is True:
        return False

    left_bounds = _story_order_bounds(left)
    right_bounds = _story_order_bounds(right)
    if left_bounds is not None and right_bounds is not None:
        return True

    if _same_revision_ref_without_order_conflict(left_start, right_start):
        return True
    raise ContractError("STORY_INTERVAL_OVERLAP_UNDETERMINED")


def _same_logical_slot(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(
        left[field] == right[field]
        for field in ("author_id", "project_id", "observer_ref", "fact_ref")
    )


def _validate_new_candidate_against_existing(
    record: dict[str, Any],
    existing_edges: Any,
) -> None:
    if not isinstance(existing_edges, list):
        raise ContractError("EXISTING_EDGE_SET_INVALID")
    for existing_document in existing_edges:
        existing = validate_document(existing_document)
        if existing["contract"] != "KNOWLEDGE_EDGE":
            raise ContractError("EXISTING_EDGE_DOCUMENT_TYPE_INVALID")
        if existing["id"] == record["id"]:
            raise ContractError("KNOWLEDGE_EDGE_ID_REUSE_FORBIDDEN")
        if not _same_logical_slot(record, existing):
            continue
        if not _story_intervals_overlap(
            record["story_time_interval"],
            existing["story_time_interval"],
        ):
            continue
        if record["version"] != existing["version"]:
            raise ContractError("CROSS_VERSION_RECREATE_FORBIDDEN")
        raise ContractError("KNOWLEDGE_EDGE_SLOT_CONFLICT")


def validate_new_candidate(
    edge: Any,
    action: Any,
    existing_edges: Any | None = None,
) -> None:
    record = validate_document(edge)
    request = validate_document(action)
    if record["contract"] != "KNOWLEDGE_EDGE" or request["contract"] != (
        "KNOWLEDGE_EDGE_WRITE_ACTION"
    ):
        raise ContractError("NEW_CANDIDATE_DOCUMENTS_INVALID")
    if request["operation"] != "PROPOSE_CANDIDATE":
        raise ContractError("NEW_CANDIDATE_ACTION_REQUIRED")
    if record["version"] != request["version"]:
        raise ContractError("NEW_CANDIDATE_VERSION_MISMATCH")
    if (
        record["author_id"] != request["author_id"]
        or record["project_id"] != request["project_id"]
    ):
        raise ContractError("NEW_CANDIDATE_PROJECT_BINDING_MISMATCH")
    status = record["version_status"]
    if record["rev"] != 1 or record["previous_rev"] is not None or status != {
        "confirmation": "candidate",
        "lifecycle": "active",
    }:
        raise ContractError("NEW_CANDIDATE_VERSION_STATUS_INVALID")
    expected_source = (
        "model_suggested"
        if request["requested_by"] == "MODEL"
        else "author_declared"
    )
    if record["source_identity"] != expected_source:
        raise ContractError("NEW_CANDIDATE_SOURCE_IDENTITY_INVALID")
    if existing_edges is None:
        raise ContractError("EXISTING_EDGE_SET_REQUIRED")
    _validate_new_candidate_against_existing(record, existing_edges)


def _stable_identity(document: dict[str, Any]) -> tuple[str, ...]:
    return (
        document["id"],
        document["author_id"],
        document["project_id"],
        document["permission_namespace"],
        document["source_identity"],
        document["created_at"],
        document["observer_ref"],
        document["fact_ref"],
    )


def validate_revision_transition(previous: Any, current: Any, action: Any) -> None:
    old = validate_document(previous)
    new = validate_document(current)
    request = validate_document(action)
    if old["contract"] != "KNOWLEDGE_EDGE" or new["contract"] != "KNOWLEDGE_EDGE":
        raise ContractError("TRANSITION_REQUIRES_EDGES")
    if request["contract"] != "KNOWLEDGE_EDGE_WRITE_ACTION":
        raise ContractError("TRANSITION_REQUIRES_ACTION")
    if len({old["version"], new["version"], request["version"]}) != 1:
        raise ContractError("CROSS_VERSION_REVISION_FORBIDDEN")
    if request["operation"] == "PROPOSE_CANDIDATE":
        raise ContractError("PROPOSE_CANDIDATE_IS_NOT_REVISION_TRANSITION")
    if request["edge_id"] != old["id"] or request["edge_id"] != new["id"]:
        raise ContractError("ACTION_EDGE_ID_MISMATCH")
    if (
        request["author_id"] != old["author_id"]
        or request["project_id"] != old["project_id"]
    ):
        raise ContractError("ACTION_PROJECT_BINDING_MISMATCH")
    if request["base_rev"] != old["rev"]:
        raise ContractError("BASE_REVISION_CONFLICT")
    if new["rev"] != old["rev"] + 1 or new["previous_rev"] != old["rev"]:
        raise ContractError("REVISION_CHAIN_INVALID")
    if _stable_identity(old) != _stable_identity(new):
        raise ContractError("STABLE_EDGE_IDENTITY_CHANGED")
    if _parse_datetime(new["updated_at"], "UPDATED_AT") <= _parse_datetime(
        old["updated_at"], "PREVIOUS_UPDATED_AT"
    ):
        raise ContractError("UPDATED_AT_MUST_ADVANCE")
    old_status = old["version_status"]
    new_status = new["version_status"]
    if old_status["lifecycle"] == "retired":
        raise ContractError("RETIRED_EDGE_CANNOT_TRANSITION")
    operation = request["operation"]
    if operation == "CONFIRM":
        if old_status["confirmation"] != "candidate" or new_status != {
            "confirmation": "author_confirmed",
            "lifecycle": "active",
        }:
            raise ContractError("CONFIRM_TRANSITION_INVALID")
    elif operation == "MODIFY":
        if old_status["confirmation"] != "author_confirmed" or new_status != {
            "confirmation": "author_confirmed",
            "lifecycle": "active",
        }:
            raise ContractError("MODIFY_TRANSITION_INVALID")
    elif operation == "RETIRE":
        if new_status != {
            "confirmation": old_status["confirmation"],
            "lifecycle": "retired",
        }:
            raise ContractError("RETIRE_TRANSITION_INVALID")
    else:
        raise ContractError("TRANSITION_OPERATION_INVALID")


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
        kind = case["fixture_kind"]
        if kind == "document":
            validate_document(case["document"])
        elif kind == "new_candidate":
            validate_new_candidate(
                case["edge"],
                case["action"],
                case.get("existing_edges"),
            )
        elif kind == "transition":
            validate_revision_transition(
                case["previous"],
                case["current"],
                case["action"],
            )
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
            "PASS_KNOWLEDGE_EDGE "
            f"cases={counts['cases']} valid={counts['valid']} "
            f"invalid={counts['invalid']}"
        )
        return 0
    if args.input is None:
        parser.error("--input or --fixtures is required")
    validate_document(json.loads(args.input.read_text(encoding="utf-8")))
    print("PASS_KNOWLEDGE_EDGE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
