"""CCZ-57 M3 B-03 r03.5 bound-evidence read contracts.

The product entry is a candidate subject plus its already-sealed evidence
binding.  Caller-supplied ranges and size limits are deliberately absent.
This module has no model, network, subprocess, or real-novel path.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    B01ContractError,
    CANDIDATE_SCHEMA_ID as B01_SCHEMA_ID,
    CONTRACT_VERSION as B01_CONTRACT_VERSION,
    record_ref as b01_record_ref,
    validate_candidate_version as b01_validate_candidate_version,
    validate_evidence_locator as b01_validate_evidence_locator,
    validate_lineage_locator as b01_validate_lineage_locator,
)
from work.ccz57_m3_b02_diagnostic_coverage_r03_5.b02_contracts import (  # noqa: E402
    B02ContractError,
    build_source_evidence_binding as b02_build_source_evidence_binding,
    validate_upstream_context as b02_validate_upstream_context,
)

CONTRACT_VERSION = "r03.5-candidate"
LEGACY_CONTRACT_VERSION = "r03.3-candidate"
CANDIDATE_SCHEMA_ID = "novel-fact-extraction-v2.1"
IMMUTABLE_CONTRACT = "M3_IMMUTABLE_RECORD"
RECORD_REF_CONTRACT = "M3_RECORD_REF"
SOURCE_MODULE = "M3"
FIXTURE_ACCESS = "POLICY_FIXTURE_READ_ONLY"
CORE_RETENTION = "CORE_IMMUTABLE_AUDIT"
SLICE_RETENTION = "RUNTIME_SIDECAR_EXPIRING"
WRITE_SET_PREFIX = "work/ccz57_m3_b03_bound_evidence_read_r03_5/"

if CONTRACT_VERSION != B01_CONTRACT_VERSION or CANDIDATE_SCHEMA_ID != B01_SCHEMA_ID:
    raise RuntimeError("B-01/B-03 r03.5 identity drift")

OUTPUT_TYPES = {
    "M3_SOURCE_READ_REQUEST",
    "M3_SOURCE_READ_CONSENT",
    "M3_SOURCE_READ_CONSENT_LIFECYCLE_RECEIPT",
    "M3_SOURCE_READ_AUTHORIZATION",
    "M3_SOURCE_READ_AUTHORIZATION_LIFECYCLE_RECEIPT",
    "M3_AUTHORIZED_SOURCE_SLICE",
    "M3_SOURCE_SLICE_RETENTION_RECEIPT",
}
WRITER_MAP = {
    "M3_SOURCE_READ_REQUEST": "SourceReadRequestWriter",
    "M3_SOURCE_READ_CONSENT": "SourceReadConsentWriter",
    "M3_SOURCE_READ_CONSENT_LIFECYCLE_RECEIPT": "SourceReadConsentLifecycleWriter",
    "M3_SOURCE_READ_AUTHORIZATION": "SourceReadAuthorizationWriter",
    "M3_SOURCE_READ_AUTHORIZATION_LIFECYCLE_RECEIPT": "SourceReadAuthorizationLifecycleWriter",
    "M3_AUTHORIZED_SOURCE_SLICE": "RestrictedSourceReader",
    "M3_SOURCE_SLICE_RETENTION_RECEIPT": "RestrictedSourceRetentionController",
}
PROJECTOR_NAME = "SourceReadAuthorizationStateProjector"
_WRITER_TOKENS = {record_type: object() for record_type in WRITER_MAP}

ENVELOPE_KEYS = {
    "contract",
    "contract_version",
    "record_type",
    "record_id",
    "record_version",
    "record_contract_version",
    "record_hash",
    "source_module",
    "access",
    "retention_class",
    "created_at",
    "payload",
}
RECORD_REF_KEYS = {
    "contract",
    "contract_version",
    "record_type",
    "record_id",
    "record_version",
    "record_contract_version",
    "record_hash",
    "access",
    "source_module",
}
CHAPTER_REVISION_KEYS = {"chapter_id", "revision_no", "revision_text_sha256"}
EVIDENCE_BINDING_KEYS = {
    "chapter_revision_ref",
    "evidence_sha256",
    "sentence_count",
    "match_locations",
    "binding_hash",
}
PRODUCT_INPUT_KEYS = {"subject", "evidence_binding", "purpose"}
CANDIDATE_SUBJECT_KEYS = {
    "kind",
    "candidate_version_ref",
    "lineage_locator",
    "evidence_locator",
    "item_hash",
    "source_revision_ref",
    "source_generation_ref",
}
REQUEST_PAYLOAD_KEYS = {
    "subject",
    "evidence_binding",
    "purpose",
    "candidate_schema_id",
    "b02_context_hash",
}
CONSENT_PAYLOAD_KEYS = {
    "request_ref",
    "policy_ref",
    "actor_identity",
    "authorization_mode",
    "purpose",
    "request_scope_hash",
    "issued_at",
    "expires_at",
    "consent_sequence",
}
AUTHORIZATION_PAYLOAD_KEYS = {
    "request_ref",
    "policy_ref",
    "source_read_consent_ref",
    "authorization_mode",
    "purpose",
    "subject_binding_hash",
    "evidence_binding_hash",
    "evidence_sha256",
    "source_revision_ref",
    "source_generation_ref",
    "b02_context_hash",
    "issued_at",
    "expires_at",
    "authorization_sequence",
    "retention_class",
}
LIFECYCLE_PAYLOAD_KEYS = {
    "parent_ref",
    "lifecycle_sequence",
    "event",
    "effective_at",
    "reason_code",
    "replacement_ref",
}
SLICE_PAYLOAD_KEYS = {
    "request_ref",
    "authorization_ref",
    "source_read_consent_ref",
    "authorization_lifecycle_refs",
    "consent_lifecycle_refs",
    "trusted_time_ref",
    "trusted_evaluation_time",
    "projected_authorization_state",
    "projected_consent_state",
    "subject",
    "evidence_binding",
    "source_revision_ref",
    "source_generation_ref",
    "b02_context_hash",
    "content",
    "content_sha256",
    "content_utf8_bytes",
    "expires_at",
    "content_access_state",
}
RETENTION_PAYLOAD_KEYS = {
    "authorized_source_slice_ref",
    "lifecycle_sequence",
    "event",
    "effective_at",
    "trusted_time_ref",
    "trusted_evaluation_time",
    "content_bytes_retained",
    "retained_metadata_fields",
}
TOMBSTONE_KEYS = {
    "authorized_source_slice_ref",
    "evidence_binding_hash",
    "evidence_sha256",
    "content_bytes_retained",
    "storage_state",
}
TOMBSTONE_FIELDS = sorted(TOMBSTONE_KEYS, key=lambda item: item.encode("utf-8"))
POLICY_PAYLOAD_KEYS = {
    "allowed_subject_types",
    "authorization_modes",
    "adjacent_prose_access",
    "plaintext_retention",
    "revocation_effect",
    "expiry_effect",
}
TRUSTED_TIME_PAYLOAD_KEYS = {
    "time_source_id",
    "trusted_evaluation_time",
    "monotonic_sequence",
    "clock_mode",
}
LEGACY_CALLER_FIELDS = {
    "range",
    "requested_range",
    "authorized_range",
    "start",
    "end",
    "max_chars",
    "max_characters",
}
TERMINAL_EVENTS = {"REVOKED", "SUPERSEDED", "EXPIRED"}
ACTIVE_STATE = "ACTIVE"


class B03ContractError(ValueError):
    """Stable machine-readable B-03 failure."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def fail(code: str, detail: str = "") -> None:
    raise B03ContractError(code, detail)


_SOURCE_BOUND_STRING_KEYS = {"evidence", "responsibility_text", "content"}


def normalize(value: Any, *, preserve_string_value: bool = False) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        fail("B03_CANONICAL_VALUE_INVALID", "floating-point values are forbidden")
    if isinstance(value, str):
        return value if preserve_string_value else unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [
            normalize(item, preserve_string_value=preserve_string_value)
            for item in value
        ]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                fail("B03_CANONICAL_KEY_INVALID")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                fail("B03_CANONICAL_DUPLICATE_KEY", normalized_key)
            normalized[normalized_key] = normalize(
                item,
                preserve_string_value=(
                    preserve_string_value or normalized_key in _SOURCE_BOUND_STRING_KEYS
                ),
            )
        return {
            key: normalized[key]
            for key in sorted(normalized, key=lambda item: item.encode("utf-8"))
        }
    fail("B03_CANONICAL_VALUE_INVALID", type(value).__name__)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        normalize(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def exact_keys(value: Any, expected: set[str], code: str) -> None:
    if not isinstance(value, dict):
        fail(code, "object required")
    if set(value) != expected:
        extra = set(value) - expected
        if extra & LEGACY_CALLER_FIELDS:
            fail(
                "B03_CALLER_RANGE_FORBIDDEN",
                ",".join(sorted(extra & LEGACY_CALLER_FIELDS)),
            )
        fail(code, f"missing={sorted(expected - set(value))}; extra={sorted(extra)}")


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_utc(value: Any, code: str) -> datetime:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is None
    ):
        fail(code, "UTC timestamp required")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as error:
        fail(code, str(error))


def validate_chapter_revision_ref(ref: dict[str, Any], code: str) -> None:
    exact_keys(ref, CHAPTER_REVISION_KEYS, code)
    if not isinstance(ref["chapter_id"], str) or not ref["chapter_id"]:
        fail(code, "chapter id")
    if not is_int(ref["revision_no"]) or ref["revision_no"] < 1:
        fail(code, "revision number")
    if not is_sha256(ref["revision_text_sha256"]):
        fail(code, "revision hash")


def build_record(
    *,
    record_type: str,
    payload: dict[str, Any],
    created_at: str,
    writer_token: object,
    access: str = FIXTURE_ACCESS,
    retention_class: str = CORE_RETENTION,
) -> dict[str, Any]:
    if _WRITER_TOKENS.get(record_type) is not writer_token:
        fail("B03_WRITER_SCOPE_ESCAPE", record_type)
    parse_utc(created_at, "B03_OBJECT_INVALID")
    prefix = {
        "M3_SOURCE_READ_REQUEST": "srr",
        "M3_SOURCE_READ_CONSENT": "src",
        "M3_SOURCE_READ_CONSENT_LIFECYCLE_RECEIPT": "srcl",
        "M3_SOURCE_READ_AUTHORIZATION": "sra",
        "M3_SOURCE_READ_AUTHORIZATION_LIFECYCLE_RECEIPT": "sral",
        "M3_AUTHORIZED_SOURCE_SLICE": "srs",
        "M3_SOURCE_SLICE_RETENTION_RECEIPT": "srrt",
    }[record_type]
    normalized_payload = normalize(deepcopy(payload))
    record = {
        "contract": IMMUTABLE_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "record_type": record_type,
        "record_id": f"{prefix}:{sha256_value(normalized_payload)}",
        "record_version": 1,
        "record_contract_version": CONTRACT_VERSION,
        "record_hash": "",
        "source_module": SOURCE_MODULE,
        "access": access,
        "retention_class": retention_class,
        "created_at": created_at,
        "payload": normalized_payload,
    }
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    validate_record(record)
    return record


def make_input_record(
    *, record_type: str, record_id: str, payload: dict[str, Any], created_at: str
) -> dict[str, Any]:
    if record_type in OUTPUT_TYPES:
        fail("B03_WRITER_SCOPE_ESCAPE", record_type)
    record = {
        "contract": IMMUTABLE_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "record_type": record_type,
        "record_id": record_id,
        "record_version": 1,
        "record_contract_version": CONTRACT_VERSION,
        "record_hash": "",
        "source_module": "B03_READ_ONLY_INPUT",
        "access": FIXTURE_ACCESS,
        "retention_class": CORE_RETENTION,
        "created_at": created_at,
        "payload": normalize(deepcopy(payload)),
    }
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    validate_record(record)
    return record


def validate_record(record: dict[str, Any]) -> None:
    exact_keys(record, ENVELOPE_KEYS, "B03_IMMUTABLE_ENVELOPE_INVALID")
    if record["contract"] != IMMUTABLE_CONTRACT:
        fail("B03_IMMUTABLE_ENVELOPE_INVALID", "contract")
    if (
        record["contract_version"] != CONTRACT_VERSION
        or record["record_contract_version"] != CONTRACT_VERSION
    ):
        fail("B03_CROSS_VERSION_FORBIDDEN")
    if not is_int(record["record_version"]) or record["record_version"] < 1:
        fail("B03_IMMUTABLE_ENVELOPE_INVALID", "version")
    if not isinstance(record["payload"], dict) or not is_sha256(record["record_hash"]):
        fail("B03_IMMUTABLE_ENVELOPE_INVALID", "payload or hash")
    parse_utc(record["created_at"], "B03_IMMUTABLE_ENVELOPE_INVALID")
    expected = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    if record["record_hash"] != expected:
        fail("B03_RECORD_HASH_MISMATCH", record["record_id"])


def record_ref(record: dict[str, Any]) -> dict[str, Any]:
    validate_record(record)
    return {
        "contract": RECORD_REF_CONTRACT,
        "contract_version": record["contract_version"],
        "record_type": record["record_type"],
        "record_id": record["record_id"],
        "record_version": record["record_version"],
        "record_contract_version": record["record_contract_version"],
        "record_hash": record["record_hash"],
        "access": record["access"],
        "source_module": record["source_module"],
    }


def validate_record_ref(
    ref: dict[str, Any],
    *,
    records: list[dict[str, Any]] | None = None,
    expected_type: str | None = None,
    code: str = "B03_REFERENCE_INTEGRITY_FAILED",
) -> None:
    exact_keys(ref, RECORD_REF_KEYS, code)
    if ref["contract"] != RECORD_REF_CONTRACT:
        fail(code, "contract")
    if (
        ref["contract_version"] != CONTRACT_VERSION
        or ref["record_contract_version"] != CONTRACT_VERSION
    ):
        fail("B03_CROSS_VERSION_FORBIDDEN")
    if expected_type is not None and ref["record_type"] != expected_type:
        fail(code, "record type")
    if not is_sha256(ref["record_hash"]):
        fail(code, "hash")
    if (
        records is not None
        and len([item for item in records if record_ref(item) == ref]) != 1
    ):
        fail(code, "reference does not resolve uniquely")


def admit_candidate_context(**upstream: Any) -> dict[str, Any]:
    try:
        return b02_validate_upstream_context(**upstream)
    except B02ContractError as error:
        fail("B03_B02_CONTEXT_INVALID", f"{error.code}:{error.detail}")


def context_hash(context: dict[str, Any]) -> str:
    return sha256_value(context)


def _candidate_item(context: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any]:
    candidate = context["candidate_version"]
    if subject["candidate_version_ref"].get("contract_version") != CONTRACT_VERSION:
        fail("B03_CROSS_VERSION_FORBIDDEN")
    if subject["candidate_version_ref"] != b01_record_ref(candidate):
        fail("B03_CANDIDATE_VERSION_DRIFT")
    validation_records = [*context["reference_records"], context["segment_index"]]
    try:
        b01_validate_candidate_version(
            candidate, allow_child=True, reference_records=validation_records
        )
        b01_validate_lineage_locator(
            subject["lineage_locator"],
            candidate_version=candidate,
            reference_records=validation_records,
        )
        b01_validate_evidence_locator(
            subject["evidence_locator"],
            candidate_version=candidate,
            reference_records=validation_records,
        )
    except B01ContractError as error:
        fail("B03_LOCATOR_DRIFT", f"{error.code}:{error.detail}")
    lineage = subject["lineage_locator"]
    evidence_locator = subject["evidence_locator"]
    if (
        lineage["candidate_version_ref"] != subject["candidate_version_ref"]
        or evidence_locator["candidate_version_ref"] != subject["candidate_version_ref"]
        or lineage["lineage_id"] != evidence_locator["lineage_id"]
    ):
        fail("B03_LOCATOR_DRIFT", "locator pair")
    pointer = re.fullmatch(r"/items/(0|[1-9][0-9]*)", lineage["json_pointer"])
    if pointer is None:
        fail("B03_LOCATOR_DRIFT", "item pointer")
    index = int(pointer.group(1))
    items = candidate["payload"]["items"]
    if index >= len(items):
        fail("B03_LOCATOR_DRIFT", "item out of range")
    item = items[index]
    if (
        item["lineage_id"] != lineage["lineage_id"]
        or item["item_hash"] != lineage["item_hash"]
        or subject["item_hash"] != item["item_hash"]
    ):
        fail("B03_ITEM_HASH_DRIFT")
    return item


def resolve_bound_candidate_input(
    product_input: dict[str, Any], *, context: dict[str, Any]
) -> dict[str, Any]:
    exact_keys(product_input, PRODUCT_INPUT_KEYS, "B03_PRODUCT_INPUT_INVALID")
    subject = product_input["subject"]
    if not isinstance(subject, dict):
        fail("B03_SUBJECT_INVALID")
    if set(subject) & LEGACY_CALLER_FIELDS:
        fail("B03_CALLER_RANGE_FORBIDDEN")
    if subject.get("kind") == "FORMAL_LEDGER_ITEM":
        fail("B03_FORMAL_LEDGER_ADAPTER_REQUIRED")
    exact_keys(subject, CANDIDATE_SUBJECT_KEYS, "B03_SUBJECT_INVALID")
    if subject["kind"] != "CANDIDATE_FACT":
        fail("B03_SUBJECT_INVALID", "kind")
    evidence_binding = product_input["evidence_binding"]
    if evidence_binding is None:
        fail("B03_EVIDENCE_REQUIRED")
    exact_keys(evidence_binding, EVIDENCE_BINDING_KEYS, "B03_EVIDENCE_BINDING_DRIFT")
    item = _candidate_item(context, subject)
    candidate = context["candidate_version"]
    expected_revision = candidate["payload"]["chapter_revision_ref"]
    expected_generation = candidate["payload"]["extraction_input_binding"][
        "accepted_source_generation_ref"
    ]
    if subject["source_revision_ref"] != expected_revision:
        fail("B03_SOURCE_REVISION_DRIFT")
    if subject["source_generation_ref"] != expected_generation:
        fail("B03_SOURCE_GENERATION_DRIFT")
    if evidence_binding != item["evidence_binding"]:
        fail("B03_EVIDENCE_BINDING_DRIFT")
    if evidence_binding["chapter_revision_ref"] != expected_revision:
        fail("B03_SOURCE_REVISION_DRIFT")
    if (
        evidence_binding["evidence_sha256"]
        != hashlib.sha256(item["evidence"].encode("utf-8")).hexdigest()
    ):
        fail("B03_EVIDENCE_BINDING_DRIFT", "evidence hash")
    if subject["evidence_locator"]["binding_hash"] != evidence_binding["binding_hash"]:
        fail("B03_EVIDENCE_BINDING_DRIFT", "locator binding")
    if (
        subject["evidence_locator"]["evidence_sha256"]
        != evidence_binding["evidence_sha256"]
    ):
        fail("B03_EVIDENCE_BINDING_DRIFT", "locator evidence hash")
    try:
        b02_binding = b02_build_source_evidence_binding(
            item["evidence"], context=context
        )
    except B02ContractError as error:
        fail("B03_B02_CONTEXT_DRIFT", f"{error.code}:{error.detail}")
    for key in (
        "chapter_revision_ref",
        "evidence_sha256",
        "sentence_count",
        "match_locations",
    ):
        if b02_binding[key] != evidence_binding[key]:
            fail("B03_B02_CONTEXT_DRIFT", key)
    purpose = product_input["purpose"]
    if (
        not isinstance(purpose, str)
        or re.fullmatch(r"[A-Z][A-Z0-9_]*", purpose) is None
    ):
        fail("B03_PRODUCT_INPUT_INVALID", "purpose")
    return {
        "subject": deepcopy(subject),
        "evidence_binding": deepcopy(evidence_binding),
        "purpose": purpose,
        "candidate_schema_id": CANDIDATE_SCHEMA_ID,
        "b02_context_hash": context_hash(context),
        "item": deepcopy(item),
    }


def validate_policy_record(record: dict[str, Any]) -> None:
    validate_record(record)
    if record["record_type"] != "M3_BOUND_EVIDENCE_READ_POLICY":
        fail("B03_POLICY_INVALID", "record type")
    payload = record["payload"]
    exact_keys(payload, POLICY_PAYLOAD_KEYS, "B03_POLICY_INVALID")
    forbidden = set(payload) & LEGACY_CALLER_FIELDS
    if forbidden:
        fail("B03_POLICY_LIMIT_FORBIDDEN", ",".join(sorted(forbidden)))
    if (
        payload["allowed_subject_types"] != ["CANDIDATE_FACT", "FORMAL_LEDGER_ITEM"]
        or payload["authorization_modes"] != ["POLICY_FIXTURE_ONLY"]
        or payload["adjacent_prose_access"] != "DENY"
        or payload["plaintext_retention"] != "SHORT_TERM_EXPIRING"
        or payload["revocation_effect"] != "IMMEDIATE_DENY_AND_PURGE"
        or payload["expiry_effect"] != "DENY_AND_PURGE_AT_OR_AFTER_EXPIRY"
    ):
        fail("B03_POLICY_INVALID", "policy value")


def validate_trusted_time_record(record: dict[str, Any]) -> None:
    validate_record(record)
    if record["record_type"] != "M3_TRUSTED_TIME_RECEIPT":
        fail("B03_TRUSTED_TIME_INVALID", "record type")
    exact_keys(record["payload"], TRUSTED_TIME_PAYLOAD_KEYS, "B03_TRUSTED_TIME_INVALID")
    payload = record["payload"]
    if not isinstance(payload["time_source_id"], str) or not payload["time_source_id"]:
        fail("B03_TRUSTED_TIME_INVALID", "source")
    if not is_int(payload["monotonic_sequence"]) or payload["monotonic_sequence"] < 1:
        fail("B03_TRUSTED_TIME_INVALID", "sequence")
    parse_utc(payload["trusted_evaluation_time"], "B03_TRUSTED_TIME_INVALID")
    if payload["clock_mode"] != "DETERMINISTIC_FIXTURE":
        fail("B03_TRUSTED_TIME_INVALID", "clock mode")


def current_trusted_time_head(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        fail("B03_TRUSTED_TIME_REQUIRED")
    for record in records:
        validate_trusted_time_record(record)
    source_ids = {record["payload"]["time_source_id"] for record in records}
    if len(source_ids) != 1:
        fail("B03_TRUSTED_TIME_CHAIN_INVALID", "source drift")
    by_sequence: dict[int, dict[str, Any]] = {}
    for record in records:
        sequence = record["payload"]["monotonic_sequence"]
        prior = by_sequence.get(sequence)
        if prior is not None and canonical_bytes(prior) != canonical_bytes(record):
            fail("B03_TRUSTED_TIME_HEAD_AMBIGUOUS")
        by_sequence[sequence] = record
    if sorted(by_sequence) != list(range(1, max(by_sequence) + 1)):
        fail("B03_TRUSTED_TIME_CHAIN_INVALID", "sequence gap")
    previous: datetime | None = None
    for sequence in sorted(by_sequence):
        current = parse_utc(
            by_sequence[sequence]["payload"]["trusted_evaluation_time"],
            "B03_TRUSTED_TIME_INVALID",
        )
        if previous is not None and current <= previous:
            fail("B03_TRUSTED_TIME_SEQUENCE_TIME_REGRESSION")
        previous = current
    return deepcopy(by_sequence[max(by_sequence)])


def require_current_trusted_time(
    supplied_ref: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    head = current_trusted_time_head(records)
    if supplied_ref != record_ref(head):
        fail("B03_TRUSTED_TIME_STALE")
    return head


def validate_request_record(
    record: dict[str, Any], *, context: dict[str, Any]
) -> dict[str, Any]:
    validate_record(record)
    if record["record_type"] != "M3_SOURCE_READ_REQUEST":
        fail("B03_REQUEST_INVALID", "record type")
    exact_keys(record["payload"], REQUEST_PAYLOAD_KEYS, "B03_REQUEST_INVALID")
    payload = record["payload"]
    resolved = resolve_bound_candidate_input(
        {
            "subject": payload["subject"],
            "evidence_binding": payload["evidence_binding"],
            "purpose": payload["purpose"],
        },
        context=context,
    )
    if payload["candidate_schema_id"] != CANDIDATE_SCHEMA_ID:
        fail("B03_CROSS_VERSION_FORBIDDEN")
    if payload["b02_context_hash"] != context_hash(context):
        fail("B03_B02_CONTEXT_DRIFT")
    return resolved


def _resolve_ref(
    ref: dict[str, Any], records: list[dict[str, Any]], expected_type: str, code: str
) -> dict[str, Any]:
    validate_record_ref(ref, records=records, expected_type=expected_type, code=code)
    return next(item for item in records if record_ref(item) == ref)


def validate_consent_record(
    record: dict[str, Any], *, records: list[dict[str, Any]], context: dict[str, Any]
) -> None:
    validate_record(record)
    if record["record_type"] != "M3_SOURCE_READ_CONSENT":
        fail("B03_CONSENT_INVALID", "record type")
    payload = record["payload"]
    exact_keys(payload, CONSENT_PAYLOAD_KEYS, "B03_CONSENT_INVALID")
    request = _resolve_ref(
        payload["request_ref"], records, "M3_SOURCE_READ_REQUEST", "B03_CONSENT_INVALID"
    )
    policy = _resolve_ref(
        payload["policy_ref"],
        records,
        "M3_BOUND_EVIDENCE_READ_POLICY",
        "B03_POLICY_INVALID",
    )
    validate_request_record(request, context=context)
    validate_policy_record(policy)
    if sha256_value(request["payload"]) != payload["request_scope_hash"]:
        fail("B03_REQUEST_SCOPE_HASH_MISMATCH")
    if (
        not isinstance(payload["actor_identity"], str)
        or not payload["actor_identity"]
        or payload["authorization_mode"] != "POLICY_FIXTURE_ONLY"
        or payload["authorization_mode"] not in policy["payload"]["authorization_modes"]
        or payload["purpose"] != request["payload"]["purpose"]
        or payload["consent_sequence"] != 0
        or parse_utc(payload["issued_at"], "B03_CONSENT_INVALID")
        >= parse_utc(payload["expires_at"], "B03_CONSENT_INVALID")
    ):
        fail("B03_CONSENT_INVALID", "payload")


def validate_authorization_record(
    record: dict[str, Any],
    *,
    all_records: list[dict[str, Any]],
    context: dict[str, Any],
) -> None:
    validate_record(record)
    if record["record_type"] != "M3_SOURCE_READ_AUTHORIZATION":
        fail("B03_AUTHORIZATION_INVALID", "record type")
    payload = record["payload"]
    exact_keys(payload, AUTHORIZATION_PAYLOAD_KEYS, "B03_AUTHORIZATION_INVALID")
    request = _resolve_ref(
        payload["request_ref"],
        all_records,
        "M3_SOURCE_READ_REQUEST",
        "B03_REQUEST_INVALID",
    )
    consent = _resolve_ref(
        payload["source_read_consent_ref"],
        all_records,
        "M3_SOURCE_READ_CONSENT",
        "B03_CONSENT_INVALID",
    )
    policy = _resolve_ref(
        payload["policy_ref"],
        all_records,
        "M3_BOUND_EVIDENCE_READ_POLICY",
        "B03_POLICY_INVALID",
    )
    resolved = validate_request_record(request, context=context)
    validate_consent_record(consent, records=all_records, context=context)
    validate_policy_record(policy)
    request_payload = request["payload"]
    if consent["payload"]["request_scope_hash"] != sha256_value(request_payload):
        fail("B03_REQUEST_SCOPE_HASH_MISMATCH")
    if (
        consent["payload"]["request_ref"] != payload["request_ref"]
        or consent["payload"]["policy_ref"] != payload["policy_ref"]
        or consent["payload"]["purpose"] != request_payload["purpose"]
        or consent["payload"]["authorization_mode"] != payload["authorization_mode"]
        or payload["authorization_mode"] != "POLICY_FIXTURE_ONLY"
        or payload["purpose"] != request_payload["purpose"]
        or payload["subject_binding_hash"] != sha256_value(request_payload["subject"])
        or payload["evidence_binding_hash"]
        != request_payload["evidence_binding"]["binding_hash"]
        or payload["evidence_sha256"]
        != request_payload["evidence_binding"]["evidence_sha256"]
        or payload["source_revision_ref"]
        != request_payload["subject"]["source_revision_ref"]
        or payload["source_generation_ref"]
        != request_payload["subject"]["source_generation_ref"]
        or payload["b02_context_hash"] != request_payload["b02_context_hash"]
        or payload["authorization_sequence"] != 0
        or payload["retention_class"] != SLICE_RETENTION
    ):
        fail("B03_AUTHORIZATION_BINDING_DRIFT")
    if (
        resolved["item"]["evidence_binding"]["binding_hash"]
        != payload["evidence_binding_hash"]
    ):
        fail("B03_EVIDENCE_BINDING_DRIFT")
    issued = parse_utc(payload["issued_at"], "B03_AUTHORIZATION_INVALID")
    expires = parse_utc(payload["expires_at"], "B03_AUTHORIZATION_INVALID")
    consent_issued = parse_utc(consent["payload"]["issued_at"], "B03_CONSENT_INVALID")
    consent_expires = parse_utc(consent["payload"]["expires_at"], "B03_CONSENT_INVALID")
    if issued < consent_issued or expires > consent_expires or issued >= expires:
        fail("B03_AUTHORIZATION_INVALID", "time window")


def validate_lifecycle_record(
    record: dict[str, Any], *, all_records: list[dict[str, Any]]
) -> None:
    validate_record(record)
    mapping = {
        "M3_SOURCE_READ_CONSENT_LIFECYCLE_RECEIPT": "M3_SOURCE_READ_CONSENT",
        "M3_SOURCE_READ_AUTHORIZATION_LIFECYCLE_RECEIPT": "M3_SOURCE_READ_AUTHORIZATION",
    }
    if record["record_type"] not in mapping:
        fail("B03_LIFECYCLE_INVALID", "record type")
    payload = record["payload"]
    exact_keys(payload, LIFECYCLE_PAYLOAD_KEYS, "B03_LIFECYCLE_INVALID")
    parent = _resolve_ref(
        payload["parent_ref"],
        all_records,
        mapping[record["record_type"]],
        "B03_LIFECYCLE_INVALID",
    )
    if (
        not is_int(payload["lifecycle_sequence"])
        or payload["lifecycle_sequence"] < 1
        or payload["event"] not in TERMINAL_EVENTS
        or not isinstance(payload["reason_code"], str)
        or re.fullmatch(r"[A-Z][A-Z0-9_]*", payload["reason_code"]) is None
    ):
        fail("B03_LIFECYCLE_INVALID", "payload")
    if parse_utc(payload["effective_at"], "B03_LIFECYCLE_INVALID") < parse_utc(
        parent["created_at"], "B03_LIFECYCLE_INVALID"
    ):
        fail("B03_LIFECYCLE_ORDER_CONFLICT")
    replacement = payload["replacement_ref"]
    if payload["event"] == "SUPERSEDED":
        if replacement is None or replacement == payload["parent_ref"]:
            fail("B03_LIFECYCLE_REPLACEMENT_INVALID")
        _resolve_ref(
            replacement,
            all_records,
            mapping[record["record_type"]],
            "B03_LIFECYCLE_REPLACEMENT_INVALID",
        )
    elif replacement is not None:
        fail("B03_LIFECYCLE_REPLACEMENT_INVALID")


def validate_lifecycle_streams(records: list[dict[str, Any]]) -> None:
    for lifecycle_type in (
        "M3_SOURCE_READ_CONSENT_LIFECYCLE_RECEIPT",
        "M3_SOURCE_READ_AUTHORIZATION_LIFECYCLE_RECEIPT",
    ):
        grouped: dict[bytes, list[dict[str, Any]]] = {}
        for record in records:
            if record["record_type"] != lifecycle_type:
                continue
            validate_lifecycle_record(record, all_records=records)
            grouped.setdefault(
                canonical_bytes(record["payload"]["parent_ref"]), []
            ).append(record)
        for stream in grouped.values():
            ordered = sorted(
                stream, key=lambda item: item["payload"]["lifecycle_sequence"]
            )
            sequences = [item["payload"]["lifecycle_sequence"] for item in ordered]
            if len(sequences) != len(set(sequences)) or sequences != sorted(sequences):
                fail("B03_LIFECYCLE_SEQUENCE_CONFLICT")
            times = [
                parse_utc(item["payload"]["effective_at"], "B03_LIFECYCLE_INVALID")
                for item in ordered
            ]
            if times != sorted(times) or len(times) != len(set(times)):
                fail("B03_LIFECYCLE_TIME_CONFLICT")
            if len(ordered) > 1:
                fail("B03_LIFECYCLE_TERMINAL")


def projected_state(
    original: dict[str, Any], lifecycle: list[dict[str, Any]], trusted_time: str
) -> str:
    now = parse_utc(trusted_time, "B03_TRUSTED_TIME_INVALID")
    for receipt in sorted(
        lifecycle, key=lambda item: item["payload"]["lifecycle_sequence"]
    ):
        if (
            parse_utc(receipt["payload"]["effective_at"], "B03_LIFECYCLE_INVALID")
            <= now
        ):
            return receipt["payload"]["event"]
    payload = original["payload"]
    if now >= parse_utc(payload["expires_at"], "B03_AUTHORIZATION_INVALID"):
        return "EXPIRED"
    if now < parse_utc(payload["issued_at"], "B03_AUTHORIZATION_INVALID"):
        return "NOT_YET_ACTIVE"
    return ACTIVE_STATE


def validate_slice_record(
    record: dict[str, Any],
    *,
    all_records: list[dict[str, Any]],
    context: dict[str, Any],
) -> None:
    validate_record(record)
    if record["record_type"] != "M3_AUTHORIZED_SOURCE_SLICE":
        fail("B03_SLICE_INVALID", "record type")
    payload = record["payload"]
    exact_keys(payload, SLICE_PAYLOAD_KEYS, "B03_SLICE_INVALID")
    request = _resolve_ref(
        payload["request_ref"],
        all_records,
        "M3_SOURCE_READ_REQUEST",
        "B03_SLICE_INVALID",
    )
    authorization = _resolve_ref(
        payload["authorization_ref"],
        all_records,
        "M3_SOURCE_READ_AUTHORIZATION",
        "B03_SLICE_INVALID",
    )
    consent = _resolve_ref(
        payload["source_read_consent_ref"],
        all_records,
        "M3_SOURCE_READ_CONSENT",
        "B03_SLICE_INVALID",
    )
    resolved = validate_request_record(request, context=context)
    validate_authorization_record(
        authorization, all_records=all_records, context=context
    )
    validate_consent_record(consent, records=all_records, context=context)
    if (
        authorization["payload"]["request_ref"] != payload["request_ref"]
        or authorization["payload"]["source_read_consent_ref"]
        != payload["source_read_consent_ref"]
        or consent["payload"]["request_ref"] != payload["request_ref"]
        or consent["payload"]["policy_ref"] != authorization["payload"]["policy_ref"]
    ):
        fail("B03_AUTHORIZATION_BINDING_DRIFT")
    content = resolved["item"]["evidence"]
    if (
        payload["subject"] != request["payload"]["subject"]
        or payload["evidence_binding"] != request["payload"]["evidence_binding"]
        or payload["source_revision_ref"]
        != request["payload"]["subject"]["source_revision_ref"]
        or payload["source_generation_ref"]
        != request["payload"]["subject"]["source_generation_ref"]
        or payload["b02_context_hash"] != request["payload"]["b02_context_hash"]
        or payload["content"] != content
        or payload["content_sha256"]
        != hashlib.sha256(content.encode("utf-8")).hexdigest()
        or payload["content_utf8_bytes"] != len(content.encode("utf-8"))
        or payload["content_access_state"] != "READABLE_UNTIL_EXPIRY"
        or payload["expires_at"] != authorization["payload"]["expires_at"]
    ):
        fail("B03_SLICE_INTEGRITY_MISMATCH")
    if (
        payload["projected_authorization_state"] != ACTIVE_STATE
        or payload["projected_consent_state"] != ACTIVE_STATE
    ):
        fail("B03_SLICE_INVALID", "inactive projection")


def validate_tombstone(tombstone: dict[str, Any]) -> None:
    exact_keys(tombstone, TOMBSTONE_KEYS, "B03_TOMBSTONE_FIELD_VIOLATION")
    validate_record_ref(
        tombstone["authorized_source_slice_ref"],
        expected_type="M3_AUTHORIZED_SOURCE_SLICE",
        code="B03_TOMBSTONE_REF_MISMATCH",
    )
    if (
        not is_sha256(tombstone["evidence_binding_hash"])
        or not is_sha256(tombstone["evidence_sha256"])
        or tombstone["content_bytes_retained"] is not False
        or tombstone["storage_state"] != "TOMBSTONED_CONTENT_UNAVAILABLE"
    ):
        fail("B03_TOMBSTONE_INVALID")


def validate_retention_record(
    record: dict[str, Any], *, tombstone: dict[str, Any]
) -> None:
    validate_record(record)
    if record["record_type"] != "M3_SOURCE_SLICE_RETENTION_RECEIPT":
        fail("B03_RETENTION_INVALID", "record type")
    payload = record["payload"]
    exact_keys(payload, RETENTION_PAYLOAD_KEYS, "B03_RETENTION_INVALID")
    validate_tombstone(tombstone)
    if (
        payload["authorized_source_slice_ref"]
        != tombstone["authorized_source_slice_ref"]
        or payload["lifecycle_sequence"] != 1
        or payload["event"] not in {"UNREADABLE", "DELETED"}
        or payload["content_bytes_retained"] is not False
        or payload["retained_metadata_fields"] != TOMBSTONE_FIELDS
    ):
        fail("B03_RETENTION_INVALID", "payload")


def reseal_record(record: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(record)
    result["record_hash"] = sha256_value(
        {key: value for key, value in result.items() if key != "record_hash"}
    )
    return result


def guard_write_path(repository_relative_path: str) -> None:
    if not repository_relative_path.startswith(WRITE_SET_PREFIX):
        fail("B03_WRITE_SET_VIOLATION", repository_relative_path)


FORBIDDEN_RUNTIME_EVENTS = {
    "network",
    "socket",
    "http",
    "dns",
    "model_api",
    "subprocess",
    "fork",
    "exec",
    "dynamic_import",
    "credential_read",
    "real_novel_read",
    "patch_write",
    "candidate_version_write",
    "pointer_write",
    "formal_ledger_guess",
}


def guard_runtime_event(event: str) -> None:
    if event in FORBIDDEN_RUNTIME_EVENTS:
        fail("B03_RUNTIME_EVENT_FORBIDDEN", event)


def build_output_record(
    *,
    record_type: str,
    payload: dict[str, Any],
    created_at: str,
    retention_class: str = CORE_RETENTION,
) -> dict[str, Any]:
    """Seal one of the seven B-03 outputs through its fixed writer slot.

    The token remains private to this contract module.  Callers select a
    record type, never a generic writer or a mutable output class.
    """

    if record_type not in OUTPUT_TYPES:
        fail("B03_WRITER_SCOPE_ESCAPE", record_type)
    return build_record(
        record_type=record_type,
        payload=payload,
        created_at=created_at,
        writer_token=_WRITER_TOKENS[record_type],
        retention_class=retention_class,
    )
