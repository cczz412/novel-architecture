#!/usr/bin/env python3
"""Fail-closed P4 importer for grouped rights decisions.

The importer can only write a derived candidate plus a receipt. Even a fully
verified approval remains in ``CANDIDATE_PENDING_CZ_CONFIRMATION`` and is never
marked training-eligible here.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator, FormatChecker


APPROVE = "APPROVE_FOR_INTERNAL_TRAINING"
REJECT = "REJECT_FOR_TRAINING"
KEEP_UNKNOWN = "KEEP_RIGHTS_UNKNOWN"
UNRESOLVED = "CZ_DECISION_REQUIRED"
INTERNAL_SCOPE = "INTERNAL_MODEL_TRAINING"
CANDIDATE_STATUS = "CANDIDATE_PENDING_CZ_CONFIRMATION"
SHA256_HEX_LENGTH = 64
MODE_DRY_RUN = "DRY_RUN"
MODE_REALTIME = "REALTIME_CANDIDATE"
MODE_REPLAY = "REPLAY_ONLY"
IMPORT_MODES = (MODE_DRY_RUN, MODE_REALTIME, MODE_REPLAY)
SHANGHAI = ZoneInfo("Asia/Shanghai")

REPO = Path("/Users/a1234/挣钱/小说架构")
EXP = REPO / "finetuning/experiments/T5_R04_WIDE_READ_NARROW_WRITE_P4_PREFLIGHT_20260808_R01"
P3_TRACK_A = (
    REPO
    / "finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01"
    / "sealed_inputs_r01/track_a"
)
FROZEN_SOURCE_GROUPS_PATH = P3_TRACK_A / "RIGHTS_SOURCE_GROUPS_314.jsonl"
FROZEN_SOURCE_GROUPS_SHA256 = (
    "08c576787d1d3153d95ed52dd4c5a0462ee7d08f66bca2be21df9fa66171db95"
)
FROZEN_DECISION_TEMPLATE_PATH = P3_TRACK_A / "RIGHTS_DECISION_TEMPLATE.jsonl"
FROZEN_DECISION_TEMPLATE_SHA256 = (
    "e8b870daedf4161f670f5dd73ee67814343115af2966353cfc50cfc0fc15b945"
)
FROZEN_SCHEMA_PATH = EXP / "RIGHTS_DECISION_IMPORT_SCHEMA.json"
FROZEN_SCHEMA_SHA256 = (
    "25b8434b8ae1e396a8b679bb60b2e91abd03c9dfd13745543a804705aafc8b6d"
)
FROZEN_GROUP_COUNT = 74
FROZEN_ROW_COUNT = 314
FROZEN_FACT_COUNT = 2783


class RightsImportError(ValueError):
    """A fail-closed import gate rejected the supplied material."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return the canonical bytes used for per-record identity hashes."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _runtime_clock(
    trusted_now_utc_for_test: datetime | None = None,
) -> tuple[datetime, datetime]:
    now = trusted_now_utc_for_test or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise RightsImportError("RUNTIME_CLOCK_MUST_BE_TIMEZONE_AWARE")
    utc_now = now.astimezone(timezone.utc)
    return utc_now, utc_now.astimezone(SHANGHAI)


def _read_pinned_file(
    path: Path,
    *,
    expected_path: Path,
    expected_sha256: str,
    label: str,
) -> bytes:
    supplied = path.resolve(strict=False)
    pinned = expected_path.resolve(strict=False)
    if supplied != pinned:
        raise RightsImportError(
            f"FROZEN_{label}_PATH_DRIFT: expected={pinned} actual={supplied}"
        )
    try:
        data = path.read_bytes()
    except FileNotFoundError as exc:
        raise RightsImportError(f"FROZEN_{label}_MISSING: {path}") from exc
    actual_sha256 = sha256_bytes(data)
    if actual_sha256 != expected_sha256:
        raise RightsImportError(
            f"FROZEN_{label}_SHA_DRIFT: "
            f"expected={expected_sha256} actual={actual_sha256}"
        )
    return data


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RightsImportError(f"DUPLICATE_JSON_KEY: {key}")
        result[key] = value
    return result


def parse_json_bytes(data: bytes, label: str) -> Any:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RightsImportError(f"UTF8_DECODE_FAIL: {label}: {exc}") from exc
    try:
        return json.loads(text, object_pairs_hook=_object_without_duplicate_keys)
    except RightsImportError:
        raise
    except json.JSONDecodeError as exc:
        raise RightsImportError(f"JSON_PARSE_FAIL: {label}: {exc}") from exc


def read_jsonl_bytes(data: bytes, label: str) -> list[dict[str, Any]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RightsImportError(f"UTF8_DECODE_FAIL: {label}: {exc}") from exc
    lines = text.splitlines()
    if not lines:
        raise RightsImportError(f"EMPTY_JSONL: {label}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            raise RightsImportError(f"BLANK_JSONL_LINE: {label}:{line_number}")
        try:
            row = json.loads(line, object_pairs_hook=_object_without_duplicate_keys)
        except RightsImportError as exc:
            raise RightsImportError(f"{exc}: {label}:{line_number}") from exc
        except json.JSONDecodeError as exc:
            raise RightsImportError(
                f"JSONL_PARSE_FAIL: {label}:{line_number}: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise RightsImportError(f"JSONL_ROW_NOT_OBJECT: {label}:{line_number}")
        rows.append(row)
    return rows


def parse_iso_date(raw: str, label: str) -> date:
    try:
        parsed = date.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise RightsImportError(f"INVALID_DATE: {label}={raw!r}") from exc
    if parsed.isoformat() != raw:
        raise RightsImportError(f"NON_CANONICAL_DATE: {label}={raw!r}")
    return parsed


def _require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RightsImportError(f"MISSING_OR_EMPTY_FIELD: {label}")
    return value


def _require_positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RightsImportError(f"INVALID_POSITIVE_INTEGER: {label}={value!r}")
    return value


def _require_sha256(value: str, label: str) -> None:
    if (
        len(value) != SHA256_HEX_LENGTH
        or value.lower() != value
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise RightsImportError(f"INVALID_SHA256: {label}={value!r}")


def _load_exact_file(path: Path, label: str) -> tuple[Path, bytes]:
    if not path.is_absolute():
        raise RightsImportError(f"EVIDENCE_PATH_NOT_ABSOLUTE: {label}: {path}")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise RightsImportError(f"EVIDENCE_MISSING: {label}: {path}") from exc
    if path != resolved:
        raise RightsImportError(
            f"EVIDENCE_PATH_NOT_REAL: {label}: supplied={path} resolved={resolved}"
        )
    if not resolved.is_file():
        raise RightsImportError(f"EVIDENCE_NOT_REGULAR_FILE: {label}: {path}")
    data = resolved.read_bytes()
    if not data:
        raise RightsImportError(f"EVIDENCE_EMPTY: {label}: {path}")
    return resolved, data


def _validate_source_groups(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_group: dict[str, dict[str, Any]] = {}
    source_ids: set[str] = set()
    global_row_ids: set[str] = set()
    for line_number, row in enumerate(rows, 1):
        group_id = _require_nonempty_string(row.get("group_id"), f"source[{line_number}].group_id")
        if group_id in by_group:
            raise RightsImportError(f"DUPLICATE_SOURCE_GROUP_ID: {group_id}")
        identity = row.get("source_identity")
        coverage = row.get("coverage")
        if not isinstance(identity, dict) or not isinstance(coverage, dict):
            raise RightsImportError(f"SOURCE_GROUP_SHAPE_FAIL: {group_id}")
        for field in (
            "source_id",
            "source_sha256",
            "book_id",
            "book_title",
            "author_id",
            "author_name",
        ):
            _require_nonempty_string(identity.get(field), f"{group_id}.source_identity.{field}")
        _require_sha256(identity["source_sha256"], f"{group_id}.source_identity.source_sha256")
        source_id = identity["source_id"]
        if source_id in source_ids:
            raise RightsImportError(f"DUPLICATE_SOURCE_ID: {source_id}")
        source_ids.add(source_id)

        row_count = _require_positive_int(coverage.get("row_count"), f"{group_id}.row_count")
        _require_positive_int(coverage.get("fact_count"), f"{group_id}.fact_count")
        row_ids = coverage.get("row_ids")
        if (
            not isinstance(row_ids, list)
            or len(row_ids) != row_count
            or len(set(row_ids)) != len(row_ids)
            or any(not isinstance(row_id, str) or not row_id for row_id in row_ids)
        ):
            raise RightsImportError(f"SOURCE_ROW_SCOPE_INVALID: {group_id}")
        repeated_across_groups = sorted(set(row_ids) & global_row_ids)
        if repeated_across_groups:
            raise RightsImportError(
                "SOURCE_ROW_ID_REUSED_ACROSS_GROUPS: "
                f"{group_id}: {','.join(repeated_across_groups)}"
            )
        global_row_ids.update(row_ids)
        if row.get("candidate_decision") != "RIGHTS_UNKNOWN":
            raise RightsImportError(f"SOURCE_RIGHTS_STATE_DRIFT: {group_id}.candidate_decision")
        if row.get("candidate_status") != CANDIDATE_STATUS:
            raise RightsImportError(f"SOURCE_RIGHTS_STATE_DRIFT: {group_id}.candidate_status")
        current_rights = row.get("current_rights")
        if not isinstance(current_rights, dict) or current_rights.get("status") != "RIGHTS_UNKNOWN":
            raise RightsImportError(f"SOURCE_RIGHTS_STATE_DRIFT: {group_id}.current_rights")
        by_group[group_id] = row
    return by_group


def _validate_decision_schema(
    rows: list[dict[str, Any]], schema: dict[str, Any]
) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise RightsImportError(f"IMPORT_SCHEMA_INVALID: {exc}") from exc
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for line_number, row in enumerate(rows, 1):
        errors = sorted(
            validator.iter_errors(row),
            key=lambda error: (list(error.absolute_path), error.message),
        )
        if errors:
            error = errors[0]
            field_path = ".".join(str(part) for part in error.absolute_path) or "<row>"
            raise RightsImportError(
                "DECISION_SCHEMA_FAIL: "
                f"line={line_number} field={field_path} message={error.message}"
            )


def _validate_derived_candidate_bindings(
    candidate: dict[str, Any], schema: dict[str, Any]
) -> None:
    bindings_schema = schema.get("$defs", {}).get("derived_candidate_bindings")
    if not isinstance(bindings_schema, dict):
        raise RightsImportError("DERIVED_CANDIDATE_BINDINGS_SCHEMA_MISSING")
    validator = Draft202012Validator(
        bindings_schema,
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(candidate),
        key=lambda error: (list(error.absolute_path), error.message),
    )
    if errors:
        error = errors[0]
        field_path = ".".join(str(part) for part in error.absolute_path) or "<row>"
        raise RightsImportError(
            "DERIVED_CANDIDATE_BINDING_FAIL: "
            f"group={candidate.get('group_id')} field={field_path} "
            f"message={error.message}"
        )


def _validate_decision_coverage(
    decisions: list[dict[str, Any]], sources: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    by_group: dict[str, dict[str, Any]] = {}
    for row in decisions:
        group_id = row["group_id"]
        if group_id in by_group:
            raise RightsImportError(f"DUPLICATE_DECISION_GROUP_ID: {group_id}")
        if group_id not in sources:
            raise RightsImportError(f"UNKNOWN_DECISION_GROUP_ID: {group_id}")
        by_group[group_id] = row
    missing = sorted(set(sources) - set(by_group))
    if missing:
        raise RightsImportError(f"MISSING_DECISION_GROUP_IDS: {','.join(missing)}")
    return by_group


def _verify_basic_binding(decision: dict[str, Any], source: dict[str, Any]) -> None:
    group_id = source["group_id"]
    identity = source["source_identity"]
    coverage = source["coverage"]
    expected = {
        "group_id": group_id,
        "source_id": identity["source_id"],
        "book_id": identity["book_id"],
        "book_title": identity["book_title"],
        "row_count": coverage["row_count"],
        "fact_count": coverage["fact_count"],
    }
    for field, value in expected.items():
        if decision.get(field) != value:
            raise RightsImportError(
                f"DECISION_SOURCE_BINDING_DRIFT: {group_id}.{field}: "
                f"expected={value!r} actual={decision.get(field)!r}"
            )


def _expected_authority_snapshot(
    decision: dict[str, Any], source: dict[str, Any]
) -> dict[str, Any]:
    identity = source["source_identity"]
    return {
        "schema_version": "t5-r04-p4-rights-authority-snapshot-v1",
        "cz_decision": APPROVE,
        "group_id": source["group_id"],
        "source_id": identity["source_id"],
        "source_sha256": identity["source_sha256"],
        "book_id": identity["book_id"],
        "book_title": identity["book_title"],
        "author_id": identity["author_id"],
        "author_name": identity["author_name"],
        "row_scope": {
            "row_ids": source["coverage"]["row_ids"],
            "row_count": source["coverage"]["row_count"],
            "fact_count": source["coverage"]["fact_count"],
        },
        "rights_holder": decision["rights_holder"],
        "decision_scope": INTERNAL_SCOPE,
        "allowed_use": INTERNAL_SCOPE,
        "validity": decision["validity"],
        "authority_document_path": decision["authority_document_path"],
        "authority_document_sha256": decision["authority_document_sha256"],
    }


def _verify_allow(
    decision: dict[str, Any], source: dict[str, Any], as_of: date
) -> dict[str, Any]:
    group_id = source["group_id"]
    if decision.get("decision_scope") != INTERNAL_SCOPE:
        raise RightsImportError(f"ALLOW_SCOPE_NOT_EXACT: {group_id}")
    if decision.get("allowed_use") != INTERNAL_SCOPE:
        raise RightsImportError(f"ALLOW_USE_NOT_EXACT: {group_id}")
    identity = source["source_identity"]
    coverage = source["coverage"]
    extra_bindings = {
        "author_id": identity["author_id"],
        "author_name": identity["author_name"],
        "source_sha256": identity["source_sha256"],
    }
    for field, expected in extra_bindings.items():
        if decision.get(field) != expected:
            raise RightsImportError(
                f"ALLOW_IDENTITY_DRIFT: {group_id}.{field}: "
                f"expected={expected!r} actual={decision.get(field)!r}"
            )
    expected_scope = {
        "row_ids": coverage["row_ids"],
        "row_count": coverage["row_count"],
        "fact_count": coverage["fact_count"],
    }
    if decision.get("row_scope") != expected_scope:
        raise RightsImportError(f"ALLOW_ROW_SCOPE_DRIFT: {group_id}")
    _require_nonempty_string(decision.get("rights_holder"), f"{group_id}.rights_holder")

    validity = decision["validity"]
    valid_from = parse_iso_date(validity["valid_from"], f"{group_id}.validity.valid_from")
    valid_until = parse_iso_date(validity["valid_until"], f"{group_id}.validity.valid_until")
    if valid_until < valid_from:
        raise RightsImportError(f"ALLOW_VALIDITY_REVERSED: {group_id}")
    if not valid_from <= as_of <= valid_until:
        raise RightsImportError(
            f"ALLOW_NOT_VALID_AS_OF_DATE: {group_id}: as_of={as_of.isoformat()}"
        )

    document_path, document_bytes = _load_exact_file(
        Path(decision["authority_document_path"]),
        f"{group_id}.authority_document",
    )
    document_sha256 = sha256_bytes(document_bytes)
    if document_sha256 != decision["authority_document_sha256"]:
        raise RightsImportError(
            f"AUTHORITY_DOCUMENT_SHA_DRIFT: {group_id}: "
            f"expected={decision['authority_document_sha256']} actual={document_sha256}"
        )

    snapshot_path, snapshot_bytes = _load_exact_file(
        Path(decision["authority_snapshot_path"]),
        f"{group_id}.authority_snapshot",
    )
    snapshot_sha256 = sha256_bytes(snapshot_bytes)
    if snapshot_sha256 != decision["authority_snapshot_sha256"]:
        raise RightsImportError(
            f"AUTHORITY_SNAPSHOT_SHA_DRIFT: {group_id}: "
            f"expected={decision['authority_snapshot_sha256']} actual={snapshot_sha256}"
        )
    snapshot = parse_json_bytes(snapshot_bytes, f"{group_id}.authority_snapshot")
    if not isinstance(snapshot, dict):
        raise RightsImportError(f"AUTHORITY_SNAPSHOT_NOT_OBJECT: {group_id}")
    expected_snapshot = _expected_authority_snapshot(decision, source)
    if snapshot != expected_snapshot:
        raise RightsImportError(f"AUTHORITY_SNAPSHOT_BINDING_DRIFT: {group_id}")

    return {
        "verification_status": "ALLOW_EVIDENCE_MECHANICALLY_VERIFIED",
        "rights_holder": decision["rights_holder"],
        "decision_scope": INTERNAL_SCOPE,
        "allowed_use": INTERNAL_SCOPE,
        "validity": validity,
        "row_scope": expected_scope,
        "authority_document_path": str(document_path),
        "authority_document_sha256": document_sha256,
        "authority_snapshot_path": str(snapshot_path),
        "authority_snapshot_sha256": snapshot_sha256,
    }


def _derived_candidate(
    source: dict[str, Any],
    decision: dict[str, Any],
    allow_verification: dict[str, Any] | None,
    source_groups_authority_snapshot_sha256: str,
    mode: str,
    validation_date: date,
    test_only: bool,
) -> dict[str, Any]:
    requested = decision["cz_decision"]
    if mode == MODE_REPLAY:
        rights_status = "RIGHTS_REPLAY_OBSERVATION_ONLY"
    elif test_only:
        rights_status = "RIGHTS_TEST_ONLY_OBSERVATION"
    elif requested == APPROVE:
        rights_status = "RIGHTS_ALLOW_CANDIDATE"
    elif requested == REJECT:
        rights_status = "RIGHTS_REJECT_CANDIDATE"
    else:
        rights_status = "RIGHTS_UNKNOWN"
    return {
        "schema_version": "t5-r04-p4-rights-derived-candidate-v1",
        "group_id": source["group_id"],
        "source_groups_authority_snapshot_sha256": (
            source_groups_authority_snapshot_sha256
        ),
        "source_group_sha256": sha256_bytes(canonical_json_bytes(source)),
        "decision_row_sha256": sha256_bytes(canonical_json_bytes(decision)),
        "source_identity": source["source_identity"],
        "coverage": source["coverage"],
        "requested_decision": requested,
        "candidate_rights_status": rights_status,
        "candidate_status": (
            "TEST_ONLY_NOT_A_CANDIDATE" if test_only else CANDIDATE_STATUS
        ),
        "allowed_use": (
            None if mode == MODE_REPLAY or test_only else decision["allowed_use"]
        ),
        "validity": decision["validity"],
        "import_mode": mode,
        "validation_date": validation_date.isoformat(),
        "replay_only": mode == MODE_REPLAY,
        "test_only": test_only,
        "allow_verification": allow_verification,
        "cz_confirmation_required": not test_only,
        "training_eligible": False,
        "production_promoted": False,
        "p2_sealed_modified": False,
    }


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(row) + b"\n" for row in rows)


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _import_decisions_core(
    *,
    source_groups_path: Path,
    decisions_path: Path,
    schema_path: Path,
    output_path: Path,
    receipt_path: Path,
    expected_source_groups_sha256: str,
    expected_decisions_sha256: str,
    expected_schema_sha256: str,
    mode: str,
    expected_group_count: int,
    expected_row_count: int,
    expected_fact_count: int,
    replay_as_of_date: str | None = None,
    trusted_now_utc_for_test: datetime | None = None,
    baseline_is_frozen: bool = False,
) -> dict[str, Any]:
    """Validate all inputs, then write candidate-only output and its receipt."""
    if mode not in IMPORT_MODES:
        raise RightsImportError(f"UNKNOWN_IMPORT_MODE: {mode}")
    if trusted_now_utc_for_test is not None and baseline_is_frozen:
        raise RightsImportError("TEST_CLOCK_FORBIDDEN_WITH_FROZEN_BASELINE")
    for value, label in (
        (expected_source_groups_sha256, "expected_source_groups_sha256"),
        (expected_decisions_sha256, "expected_decisions_sha256"),
        (expected_schema_sha256, "expected_schema_sha256"),
    ):
        _require_sha256(value, label)
    run_utc, run_shanghai = _runtime_clock(trusted_now_utc_for_test)
    if mode == MODE_REPLAY:
        if replay_as_of_date is None:
            raise RightsImportError("REPLAY_AS_OF_DATE_REQUIRED")
        validation_date = parse_iso_date(replay_as_of_date, "replay_as_of_date")
        validation_date_source = "EXPLICIT_REPLAY_ONLY_DATE"
    else:
        if replay_as_of_date is not None:
            raise RightsImportError("REPLAY_AS_OF_DATE_FORBIDDEN_OUTSIDE_REPLAY")
        validation_date = run_shanghai.date()
        validation_date_source = "SYSTEM_ASIA_SHANGHAI_CURRENT_DATE"

    source_bytes = source_groups_path.read_bytes()
    decision_bytes = decisions_path.read_bytes()
    schema_bytes = schema_path.read_bytes()
    source_sha256 = sha256_bytes(source_bytes)
    decisions_sha256 = sha256_bytes(decision_bytes)
    schema_sha256 = sha256_bytes(schema_bytes)
    if source_sha256 != expected_source_groups_sha256:
        raise RightsImportError(
            "SOURCE_GROUPS_SHA_DRIFT: "
            f"expected={expected_source_groups_sha256} actual={source_sha256}"
        )
    if decisions_sha256 != expected_decisions_sha256:
        raise RightsImportError(
            "DECISIONS_SHA_DRIFT: "
            f"expected={expected_decisions_sha256} actual={decisions_sha256}"
        )
    if schema_sha256 != expected_schema_sha256:
        raise RightsImportError(
            "IMPORT_SCHEMA_SHA_DRIFT: "
            f"expected={expected_schema_sha256} actual={schema_sha256}"
        )

    source_rows = read_jsonl_bytes(source_bytes, str(source_groups_path))
    decision_rows = read_jsonl_bytes(decision_bytes, str(decisions_path))
    schema = parse_json_bytes(schema_bytes, str(schema_path))
    if not isinstance(schema, dict):
        raise RightsImportError("IMPORT_SCHEMA_NOT_OBJECT")
    sources = _validate_source_groups(source_rows)
    _validate_decision_schema(decision_rows, schema)
    decisions = _validate_decision_coverage(decision_rows, sources)

    group_count = len(sources)
    row_count = sum(source["coverage"]["row_count"] for source in sources.values())
    fact_count = sum(source["coverage"]["fact_count"] for source in sources.values())
    for actual, expected, label in (
        (group_count, expected_group_count, "GROUP_COUNT_DRIFT"),
        (row_count, expected_row_count, "ROW_COUNT_DRIFT"),
        (fact_count, expected_fact_count, "FACT_COUNT_DRIFT"),
    ):
        if actual != expected:
            raise RightsImportError(f"{label}: expected={expected} actual={actual}")

    derived: list[dict[str, Any]] = []
    decision_counts = {
        "allow_candidate": 0,
        "reject_candidate": 0,
        "rights_unknown": 0,
        "unresolved_template": 0,
        "replay_approve_observation": 0,
        "replay_reject_observation": 0,
        "test_only_allow_observation": 0,
        "test_only_reject_observation": 0,
    }
    for source in source_rows:
        group_id = source["group_id"]
        decision = decisions[group_id]
        _verify_basic_binding(decision, source)
        requested = decision["cz_decision"]
        if mode == MODE_DRY_RUN and requested not in (UNRESOLVED, KEEP_UNKNOWN):
            raise RightsImportError(
                f"DRY_RUN_REQUIRES_ALL_RIGHTS_UNKNOWN: {group_id}: {requested}"
            )
        if requested == UNRESOLVED and mode != MODE_DRY_RUN:
            raise RightsImportError(
                f"UNRESOLVED_DECISION_FORBIDDEN_OUTSIDE_DRY_RUN: {group_id}"
            )
        allow_verification = None
        if requested == APPROVE:
            allow_verification = _verify_allow(decision, source, validation_date)
            if mode == MODE_REPLAY:
                allow_verification = {
                    **allow_verification,
                    "verification_status": (
                        "REPLAY_ONLY_EVIDENCE_VERIFIED_NO_AUTHORITY_EFFECT"
                    ),
                    "historical_requested_use": INTERNAL_SCOPE,
                    "allowed_use": None,
                    "authority_effect": "NONE_REPLAY_ONLY",
                }
                decision_counts["replay_approve_observation"] += 1
            elif trusted_now_utc_for_test is not None:
                decision_counts["test_only_allow_observation"] += 1
            else:
                decision_counts["allow_candidate"] += 1
        elif requested == REJECT:
            if not decision["cz_note"].strip():
                raise RightsImportError(f"REJECT_NOTE_EMPTY: {group_id}")
            if mode == MODE_REPLAY:
                decision_counts["replay_reject_observation"] += 1
            elif trusted_now_utc_for_test is not None:
                decision_counts["test_only_reject_observation"] += 1
            else:
                decision_counts["reject_candidate"] += 1
        else:
            decision_counts["rights_unknown"] += 1
            if requested == UNRESOLVED:
                decision_counts["unresolved_template"] += 1
        candidate = _derived_candidate(
            source,
            decision,
            allow_verification,
            source_sha256,
            mode,
            validation_date,
            trusted_now_utc_for_test is not None,
        )
        _validate_derived_candidate_bindings(candidate, schema)
        derived.append(candidate)

    output_bytes = _jsonl_bytes(derived)
    all_unknown_dry_run = (
        mode == MODE_DRY_RUN
        and decision_counts["rights_unknown"] == group_count
        and decision_counts["allow_candidate"] == 0
        and decision_counts["reject_candidate"] == 0
    )
    if mode == MODE_DRY_RUN:
        if not all_unknown_dry_run:
            raise RightsImportError("DRY_RUN_UNKNOWN_ONLY_INVARIANT_FAIL")
        status = (
            "PASS_TEST_ONLY_DRY_RUN_NO_CANDIDATE_EFFECT"
            if trusted_now_utc_for_test is not None
            else "PASS_DRY_RUN_ALL_RIGHTS_UNKNOWN_NO_PROMOTION"
        )
    elif mode == MODE_REPLAY:
        status = (
            "PASS_TEST_ONLY_REPLAY_OBSERVATION_NO_CANDIDATE_EFFECT"
            if trusted_now_utc_for_test is not None
            else "PASS_REPLAY_ONLY_NO_TRAINING_OR_PROMOTION"
        )
    else:
        status = (
            "PASS_TEST_ONLY_NO_CANDIDATE_EFFECT"
            if trusted_now_utc_for_test is not None
            else "PASS_CANDIDATE_IMPORT_NO_PROMOTION"
        )
    receipt = {
        "schema_version": "t5-r04-p4-rights-import-receipt-v1",
        "status": status,
        "mode": mode,
        "validation_date": validation_date.isoformat(),
        "runtime_clock": {
            "utc": run_utc.isoformat(timespec="seconds"),
            "asia_shanghai": run_shanghai.isoformat(timespec="seconds"),
            "validation_date_source": validation_date_source,
            "clock_source": (
                "TEST_ONLY_INJECTED"
                if trusted_now_utc_for_test is not None
                else "SYSTEM_UTC"
            ),
        },
        "baseline_contract": {
            "frozen": baseline_is_frozen,
            "source_groups_sha256": expected_source_groups_sha256,
            "schema_sha256": expected_schema_sha256,
            "source_groups": expected_group_count,
            "rows": expected_row_count,
            "facts": expected_fact_count,
        },
        "preflight_corrections": [
            {
                "id": "P4-RIGHTS-CORR-01",
                "finding": "DRY_RUN_PREVIOUSLY_ACCEPTED_MIXED_DECISIONS",
                "resolution": "DRY_RUN_NOW_REQUIRES_EVERY_GROUP_RIGHTS_UNKNOWN",
            },
            {
                "id": "P4-RIGHTS-CORR-02",
                "finding": "IMPORT_SCHEMA_WAS_NOT_SHA_PINNED",
                "resolution": (
                    "SCHEMA_SHA_PINNED_AND_ALLOW_SCOPE_CHECKED_IN_PROGRAM"
                ),
            },
            {
                "id": "P4-RIGHTS-CORR-03",
                "finding": "CALLER_DATE_COULD_MASK_EXPIRED_REALTIME_AUTHORITY",
                "resolution": (
                    "REALTIME_USES_SYSTEM_ASIA_SHANGHAI_DATE_REPLAY_IS_EXPLICIT"
                ),
            },
            {
                "id": "P4-RIGHTS-CORR-04",
                "finding": "SCHEMA_REGRESSION_ASSERTION_WAS_INSERTED_IN_WRONG_TEST_SCOPE",
                "resolution": (
                    "ASSERTION_MOVED_TO_SCHEMA_TEST_AFTER_1_FAILED_18_PASSED"
                ),
            },
            {
                "id": "P4-RIGHTS-CORR-05",
                "finding": (
                    "REPLAY_ASSERTIONS_LAGGED_OBSERVATION_ONLY_CONTRACT"
                ),
                "resolution": (
                    "UPDATED_AFTER_2_FAILED_17_PASSED_REPLAY_HAS_NO_ALLOW_CANDIDATE"
                ),
            },
            {
                "id": "P4-RIGHTS-CORR-06",
                "finding": "PUBLIC_ENTRYPOINT_ACCEPTED_TEST_CLOCK_INJECTION",
                "resolution": (
                    "TEST_CLOCK_RETAINED_ONLY_IN_PRIVATE_CORE_PUBLIC_USES_SYSTEM_UTC"
                ),
            },
            {
                "id": "P4-RIGHTS-CORR-07",
                "finding": "TEST_CLOCK_COULD_BE_COMBINED_WITH_FROZEN_BASELINE",
                "resolution": (
                    "HARD_STOP_TEST_CLOCK_WITH_FROZEN_BASELINE_BEFORE_ANY_OUTPUT"
                ),
            },
            {
                "id": "P4-RIGHTS-CORR-08",
                "finding": (
                    "TOY_ASSERTIONS_EXPECTED_FORMAL_RIGHTS_STATES_AFTER_TEST_ONLY_LOCK"
                ),
                "resolution": (
                    "UPDATED_AFTER_3_FAILED_17_PASSED_TO_TEST_ONLY_OBSERVATIONS"
                ),
            },
            {
                "id": "P4-RIGHTS-CORR-09",
                "finding": (
                    "REPLAY_TOY_ASSERTED_FORMAL_PASS_AFTER_TEST_ONLY_STATUS_SPLIT"
                ),
                "resolution": (
                    "UPDATED_AFTER_1_FAILED_19_PASSED_TO_TEST_ONLY_REPLAY_STATUS"
                ),
            },
        ],
        "inputs": {
            "source_groups": {
                "path": str(source_groups_path.resolve()),
                "sha256": source_sha256,
                "bytes": len(source_bytes),
                "frozen_baseline": baseline_is_frozen,
            },
            "decisions": {
                "path": str(decisions_path.resolve()),
                "sha256": decisions_sha256,
                "bytes": len(decision_bytes),
                "frozen_template": baseline_is_frozen and mode == MODE_DRY_RUN,
            },
            "schema": {
                "path": str(schema_path.resolve()),
                "sha256": schema_sha256,
                "bytes": len(schema_bytes),
                "frozen_baseline": baseline_is_frozen,
            },
            "importer": {
                "path": str(Path(__file__).resolve()),
                "sha256": sha256_file(Path(__file__).resolve()),
            },
        },
        "coverage": {
            "source_groups": group_count,
            "rows": row_count,
            "facts": fact_count,
            **decision_counts,
        },
        "output": {
            "path": str(output_path.resolve()),
            "sha256": sha256_bytes(output_bytes),
            "bytes": len(output_bytes),
            "candidate_rows": len(derived),
            "required_bindings": {
                "source_groups_authority_snapshot_sha256": source_sha256,
                "source_group_record_sha256_present_per_candidate": True,
                "allowed_use_key_present_per_candidate": True,
                "validity_key_present_per_candidate": True,
            },
        },
        "safety": {
            "all_outputs_candidate_pending_cz_confirmation": (
                trusted_now_utc_for_test is None
            ),
            "test_only": trusted_now_utc_for_test is not None,
            "replay_only": mode == MODE_REPLAY,
            "replay_can_train_or_promote": False,
            "training_eligible_groups": 0,
            "production_promotions": 0,
            "p2_sealed_modified": False,
            "training_runs": 0,
            "model_or_api_calls": 0,
            "notion_writes": 0,
            "git_actions": 0,
        },
    }
    receipt_bytes = _json_bytes(receipt)

    input_paths = {
        source_groups_path.resolve(),
        decisions_path.resolve(),
        schema_path.resolve(),
        Path(__file__).resolve(),
    }
    evidence_paths: set[Path] = set()
    for row in derived:
        verification = row["allow_verification"]
        if verification is None:
            continue
        document_path = Path(verification["authority_document_path"]).resolve()
        snapshot_path = Path(verification["authority_snapshot_path"]).resolve()
        if document_path == snapshot_path:
            raise RightsImportError(
                f"AUTHORITY_DOCUMENT_AND_SNAPSHOT_COLLIDE: {row['group_id']}"
            )
        evidence_paths.update((document_path, snapshot_path))
    if evidence_paths & input_paths:
        aliases = ",".join(str(path) for path in sorted(evidence_paths & input_paths))
        raise RightsImportError(f"EVIDENCE_PATH_ALIASES_IMPORT_CONTROL: {aliases}")
    output_resolved = output_path.resolve()
    receipt_resolved = receipt_path.resolve()
    if output_resolved in input_paths or receipt_resolved in input_paths:
        raise RightsImportError("OUTPUT_PATH_ALIASES_INPUT")
    if output_resolved == receipt_resolved:
        raise RightsImportError("OUTPUT_AND_RECEIPT_PATH_COLLIDE")
    if output_resolved in evidence_paths or receipt_resolved in evidence_paths:
        raise RightsImportError("OUTPUT_PATH_ALIASES_VERIFIED_EVIDENCE")

    _write_bytes(output_path, output_bytes)
    _write_bytes(receipt_path, receipt_bytes)
    return receipt


def import_frozen_decisions(
    *,
    mode: str,
    output_path: Path,
    receipt_path: Path,
    decisions_path: Path | None = None,
    expected_decisions_sha256: str | None = None,
    replay_as_of_date: str | None = None,
) -> dict[str, Any]:
    """Production entrypoint with the P3 baseline and schema pinned in code."""
    _read_pinned_file(
        FROZEN_SOURCE_GROUPS_PATH,
        expected_path=FROZEN_SOURCE_GROUPS_PATH,
        expected_sha256=FROZEN_SOURCE_GROUPS_SHA256,
        label="SOURCE_GROUPS",
    )
    _read_pinned_file(
        FROZEN_SCHEMA_PATH,
        expected_path=FROZEN_SCHEMA_PATH,
        expected_sha256=FROZEN_SCHEMA_SHA256,
        label="IMPORT_SCHEMA",
    )
    if mode == MODE_DRY_RUN:
        if decisions_path is not None or expected_decisions_sha256 is not None:
            raise RightsImportError("DRY_RUN_DECISION_INPUT_OVERRIDE_FORBIDDEN")
        decisions_path = FROZEN_DECISION_TEMPLATE_PATH
        expected_decisions_sha256 = FROZEN_DECISION_TEMPLATE_SHA256
        _read_pinned_file(
            decisions_path,
            expected_path=FROZEN_DECISION_TEMPLATE_PATH,
            expected_sha256=FROZEN_DECISION_TEMPLATE_SHA256,
            label="DECISION_TEMPLATE",
        )
    elif decisions_path is None or expected_decisions_sha256 is None:
        raise RightsImportError("DECISION_PATH_AND_SHA_REQUIRED")

    return _import_decisions_core(
        source_groups_path=FROZEN_SOURCE_GROUPS_PATH,
        decisions_path=decisions_path,
        schema_path=FROZEN_SCHEMA_PATH,
        output_path=output_path,
        receipt_path=receipt_path,
        expected_source_groups_sha256=FROZEN_SOURCE_GROUPS_SHA256,
        expected_decisions_sha256=expected_decisions_sha256,
        expected_schema_sha256=FROZEN_SCHEMA_SHA256,
        mode=mode,
        expected_group_count=FROZEN_GROUP_COUNT,
        expected_row_count=FROZEN_ROW_COUNT,
        expected_fact_count=FROZEN_FACT_COUNT,
        replay_as_of_date=replay_as_of_date,
        baseline_is_frozen=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed import of grouped rights decisions into a candidate-only artifact."
    )
    parser.add_argument("--mode", choices=IMPORT_MODES, required=True)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--expected-decisions-sha256")
    parser.add_argument("--replay-as-of-date")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = import_frozen_decisions(
            mode=args.mode,
            decisions_path=args.decisions,
            output_path=args.output,
            receipt_path=args.receipt,
            expected_decisions_sha256=args.expected_decisions_sha256,
            replay_as_of_date=args.replay_as_of_date,
        )
    except (OSError, RightsImportError) as exc:
        print(f"HARD_STOP_RIGHTS_IMPORT: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
