"""CCZ-57 M3 B-02 r03.5 immutable Diagnostic/Coverage contracts.

The module is fixture-only. It has no model, network, subprocess,
dynamic-import, real-novel, Patch, or CandidateVersion write path.
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
    CANDIDATE_SCHEMA_ID as B01_CANDIDATE_SCHEMA_ID,
    CONTRACT_VERSION as B01_CONTRACT_VERSION,
    sentence_count,
    validate_candidate_version as b01_validate_candidate_version,
    validate_evidence_locator as b01_validate_evidence_locator,
    validate_lineage_locator as b01_validate_lineage_locator,
    validate_segment_index_snapshot as b01_validate_segment_index,
)

CONTRACT_VERSION = "r03.5-candidate"
LEGACY_CONTRACT_VERSION = "r03.3-candidate"
CANDIDATE_SCHEMA_ID = "novel-fact-extraction-v2.1"
DOCUMENT_IDENTITY = "CCZ57-M3-B02-R03.5-CANDIDATE"
IMMUTABLE_CONTRACT = "M3_IMMUTABLE_RECORD"
RECORD_REF_CONTRACT = "M3_RECORD_REF"
SOURCE_MODULE = "M3"
FIXTURE_ACCESS = "POLICY_FIXTURE_READ_ONLY"
RUN_ACCESS = "RUN_INTERNAL_READ_ONLY"
RETENTION_CLASS = "CORE_IMMUTABLE_AUDIT"
WRITE_SET_PREFIX = "work/ccz57_m3_b02_diagnostic_coverage_r03_5/"

if (
    CONTRACT_VERSION != B01_CONTRACT_VERSION
    or CANDIDATE_SCHEMA_ID != B01_CANDIDATE_SCHEMA_ID
):
    raise RuntimeError("B-01/B-02 r03.5 identity drift")

OUTPUT_TYPES = {
    "M3_DIAGNOSTIC_RECORDER_IDENTITY",
    "M3_DIAGNOSTIC",
    "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT",
    "M3_COVERAGE_OBSERVATION",
}
WRITER_MAP = {
    "M3_DIAGNOSTIC_RECORDER_IDENTITY": "DiagnosticRecorderIdentityRegistry",
    "M3_DIAGNOSTIC": "DiagnosticRecorder",
    "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT": "DiagnosticLifecycleWriter",
    "M3_COVERAGE_OBSERVATION": "CoverageRecorder",
}
_WRITER_TOKENS = {record_type: object() for record_type in WRITER_MAP}
TERMINAL_EVENTS = {"SUPERSEDED_BY_PATCH_REVIEW", "CLOSED"}
COVERAGE_MATCHES = {"MATCHED", "MISSING", "PARTIAL"}
ALLOWED_ACCESS = {FIXTURE_ACCESS, RUN_ACCESS}

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
IDENTITY_PAYLOAD_KEYS = {"writer", "writer_version"}
DIAGNOSTIC_PAYLOAD_KEYS = {
    "base_candidate_version_ref",
    "candidate_schema_id",
    "chapter_revision_ref",
    "seg",
    "axis",
    "severity",
    "target",
    "fingerprint",
    "writer_identity_ref",
}
LIFECYCLE_PAYLOAD_KEYS = {
    "diagnostic_ref",
    "lifecycle_sequence",
    "event",
    "effective_at",
    "reason_code",
    "resolution_ref",
}
COVERAGE_PAYLOAD_KEYS = {
    "base_candidate_version_ref",
    "candidate_schema_id",
    "chapter_revision_ref",
    "seg",
    "source_observation_id",
    "source_evidence_binding",
    "axis",
    "candidate_match",
    "matched_candidate_bindings",
    "observer_ref",
}
SOURCE_EVIDENCE_BINDING_KEYS = {
    "chapter_revision_ref",
    "evidence",
    "evidence_sha256",
    "sentence_count",
    "match_locations",
    "binding_hash",
}
MATCHED_BINDING_KEYS = {"lineage_locator", "evidence_locator"}


class B02ContractError(ValueError):
    """Stable, machine-readable B-02 contract failure."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def fail(code: str, detail: str = "") -> None:
    raise B02ContractError(code, detail)


# Source bytes must survive canonical JSON without NFC rewriting. Other strings
# still use NFC. `responsibility_text` is sealed input needed to validate source.
_SOURCE_BOUND_STRING_KEYS = {"evidence", "responsibility_text"}


def normalize(value: Any, *, preserve_string_value: bool = False) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        fail("B02_CANONICAL_VALUE_INVALID", "floating-point values are forbidden")
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
                fail("B02_CANONICAL_KEY_INVALID", "object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                fail("B02_CANONICAL_DUPLICATE_KEY", normalized_key)
            normalized[normalized_key] = normalize(
                item,
                preserve_string_value=(
                    preserve_string_value
                    or normalized_key in _SOURCE_BOUND_STRING_KEYS
                ),
            )
        return {
            key: normalized[key]
            for key in sorted(normalized, key=lambda item: item.encode("utf-8"))
        }
    fail("B02_CANONICAL_VALUE_INVALID", type(value).__name__)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        normalize(value),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def exact_keys(value: dict[str, Any], expected: set[str], code: str) -> None:
    if not isinstance(value, dict):
        fail(code, "object required")
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        fail(code, f"missing={missing}; extra={extra}")


def is_non_bool_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def parse_utc(value: Any, code: str) -> datetime:
    if not isinstance(value, str) or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value
    ) is None:
        fail(code, "UTC RFC 3339 timestamp required")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as error:
        fail(code, str(error))


def build_record(
    *,
    record_type: str,
    record_id: str,
    payload: dict[str, Any],
    created_at: str,
    access: str,
    writer_token: object,
) -> dict[str, Any]:
    if _WRITER_TOKENS.get(record_type) is not writer_token:
        fail("B02_WRITER_SCOPE_ESCAPE", record_type)
    if not isinstance(record_id, str) or not record_id:
        fail("B02_OBJECT_INVALID", "record id")
    parse_utc(created_at, "B02_OBJECT_INVALID")
    if access not in ALLOWED_ACCESS:
        fail("B02_OBJECT_INVALID", "access")
    record = {
        "contract": IMMUTABLE_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "record_type": record_type,
        "record_id": record_id,
        "record_version": 1,
        "record_contract_version": CONTRACT_VERSION,
        "record_hash": "",
        "source_module": SOURCE_MODULE,
        "access": access,
        "retention_class": RETENTION_CLASS,
        "created_at": created_at,
        "payload": normalize(deepcopy(payload)),
    }
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    validate_record(record)
    return record


def validate_record(record: dict[str, Any]) -> None:
    exact_keys(record, ENVELOPE_KEYS, "B02_IMMUTABLE_ENVELOPE_INVALID")
    if record["contract"] != IMMUTABLE_CONTRACT:
        fail("B02_IMMUTABLE_ENVELOPE_INVALID", "contract")
    if (
        record["contract_version"] != CONTRACT_VERSION
        or record["record_contract_version"] != CONTRACT_VERSION
    ):
        fail("B02_UPSTREAM_CONTRACT_DRIFT", "contract version")
    if not is_non_bool_int(record["record_version"]) or record["record_version"] < 1:
        fail("B02_IMMUTABLE_ENVELOPE_INVALID", "record version")
    for key in (
        "record_type",
        "record_id",
        "source_module",
        "access",
        "retention_class",
        "created_at",
    ):
        if not isinstance(record[key], str) or not record[key]:
            fail("B02_IMMUTABLE_ENVELOPE_INVALID", key)
    parse_utc(record["created_at"], "B02_IMMUTABLE_ENVELOPE_INVALID")
    if not isinstance(record["payload"], dict) or not is_sha256(record["record_hash"]):
        fail("B02_IMMUTABLE_ENVELOPE_INVALID", "payload or record hash")
    if record != normalize(record):
        fail("B02_CANONICAL_VALUE_INVALID", "non-source field is not NFC")
    expected_hash = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    if record["record_hash"] != expected_hash:
        fail("B02_RECORD_HASH_MISMATCH", record["record_id"])


def validate_b02_output_record(record: dict[str, Any]) -> None:
    validate_record(record)
    if record["record_type"] not in OUTPUT_TYPES:
        fail("B02_OUTPUT_ENVELOPE_INVALID", "record type")
    if record["record_version"] != 1:
        fail("B02_OUTPUT_ENVELOPE_INVALID", "record version")
    if record["source_module"] != SOURCE_MODULE:
        fail("B02_OUTPUT_ENVELOPE_INVALID", "source module")
    if record["access"] not in ALLOWED_ACCESS:
        fail("B02_OUTPUT_ENVELOPE_INVALID", "access")
    if record["retention_class"] != RETENTION_CLASS:
        fail("B02_OUTPUT_ENVELOPE_INVALID", "retention class")


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
    code: str = "B02_REFERENCE_INTEGRITY_FAILED",
    records: list[dict[str, Any]] | None = None,
    expected_type: str | None = None,
    allowed_access: set[str] | None = None,
    expected_source_module: str | None = None,
) -> None:
    exact_keys(ref, RECORD_REF_KEYS, code)
    if ref["contract"] != RECORD_REF_CONTRACT:
        fail(code, "contract")
    if (
        ref["contract_version"] != CONTRACT_VERSION
        or ref["record_contract_version"] != CONTRACT_VERSION
    ):
        fail("B02_UPSTREAM_CONTRACT_DRIFT", "RecordRef contract version")
    if not is_non_bool_int(ref["record_version"]) or ref["record_version"] < 1:
        fail(code, "record version")
    if not is_sha256(ref["record_hash"]):
        fail(code, "record hash")
    if expected_type is not None and ref["record_type"] != expected_type:
        fail(code, "record type")
    if allowed_access is not None and ref["access"] not in allowed_access:
        fail(code, "access")
    if expected_source_module is not None and ref["source_module"] != expected_source_module:
        fail(code, "source module")
    if records is not None:
        matches = [record for record in records if record_ref(record) == ref]
        if len(matches) != 1:
            fail(code, "reference does not resolve uniquely")


def validate_chapter_revision_ref(ref: dict[str, Any]) -> None:
    exact_keys(ref, CHAPTER_REVISION_KEYS, "B02_SCOPE_MISMATCH")
    if not isinstance(ref["chapter_id"], str) or not ref["chapter_id"]:
        fail("B02_SCOPE_MISMATCH", "chapter id")
    if not is_non_bool_int(ref["revision_no"]) or ref["revision_no"] < 1:
        fail("B02_SCOPE_MISMATCH", "revision number")
    if not is_sha256(ref["revision_text_sha256"]):
        fail("B02_SCOPE_MISMATCH", "revision hash")


def _b01_failure(error: B01ContractError, detail: str) -> None:
    fail("B02_UPSTREAM_CONTEXT_INVALID", f"{detail}:{error.code}:{error.detail}")


def _validate_segment_sources(
    segment_index: dict[str, Any], segment_inputs: list[dict[str, Any]]
) -> bytes:
    indexed = segment_index["payload"]["segments"]
    if not isinstance(segment_inputs, list) or len(segment_inputs) != len(indexed):
        fail("B02_SOURCE_EVIDENCE_INVALID", "segment source count")
    chunks: list[bytes] = []
    for expected_seg, (source, index_entry) in enumerate(
        zip(segment_inputs, indexed, strict=True), start=1
    ):
        allowed = {"seg", "start_byte", "end_byte", "responsibility_text"}
        if "responsibility_text_sha256" in source:
            allowed.add("responsibility_text_sha256")
        exact_keys(source, allowed, "B02_SOURCE_EVIDENCE_INVALID")
        text = source.get("responsibility_text")
        if not isinstance(text, str):
            fail("B02_SOURCE_EVIDENCE_INVALID", "responsibility text")
        text_bytes = text.encode("utf-8")
        text_hash = hashlib.sha256(text_bytes).hexdigest()
        expected_entry = {
            "seg": expected_seg,
            "start_byte": source.get("start_byte"),
            "end_byte": source.get("end_byte"),
            "responsibility_text_sha256": text_hash,
        }
        if (
            source.get("seg") != expected_seg
            or not is_non_bool_int(source.get("start_byte"))
            or not is_non_bool_int(source.get("end_byte"))
            or source["end_byte"] - source["start_byte"] != len(text_bytes)
            or source.get("responsibility_text_sha256", text_hash) != text_hash
            or index_entry != expected_entry
        ):
            fail("B02_SOURCE_EVIDENCE_INVALID", "segment bytes")
        chunks.append(text_bytes)
    chapter_bytes = b"".join(chunks)
    chapter_ref = segment_index["payload"]["chapter_revision_ref"]
    if (
        len(chapter_bytes) != segment_index["payload"]["chapter_length_bytes"]
        or hashlib.sha256(chapter_bytes).hexdigest()
        != chapter_ref["revision_text_sha256"]
    ):
        fail("B02_SOURCE_EVIDENCE_INVALID", "chapter bytes")
    return chapter_bytes


def validate_upstream_context(
    *,
    reference_records: list[dict[str, Any]],
    segment_index: dict[str, Any],
    candidate_version: dict[str, Any],
    lineage_locators: list[dict[str, Any]],
    evidence_locators: list[dict[str, Any]],
    segment_inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(reference_records, list):
        fail("B02_UPSTREAM_CONTEXT_INVALID", "reference records")
    validation_records = [*deepcopy(reference_records), deepcopy(segment_index)]
    try:
        b01_validate_segment_index(segment_index)
        b01_validate_candidate_version(
            candidate_version,
            allow_child=True,
            reference_records=validation_records,
        )
    except B01ContractError as error:
        _b01_failure(error, "candidate")
    if (
        candidate_version["contract_version"] != CONTRACT_VERSION
        or candidate_version["record_contract_version"] != CONTRACT_VERSION
        or candidate_version["payload"]["candidate_schema_id"] != CANDIDATE_SCHEMA_ID
        or candidate_version["payload"]["segment_index_ref"] != record_ref(segment_index)
        or candidate_version["payload"]["chapter_revision_ref"]
        != segment_index["payload"]["chapter_revision_ref"]
    ):
        fail("B02_SCOPE_MISMATCH", "CandidateVersion identity")
    chapter_bytes = _validate_segment_sources(segment_index, segment_inputs)
    if not lineage_locators or not evidence_locators:
        fail("B02_LOCATOR_SET_INVALID", "empty admitted locator set")
    admitted_lineage: dict[str, dict[str, Any]] = {}
    admitted_evidence: dict[str, dict[str, Any]] = {}
    for locator in lineage_locators:
        try:
            b01_validate_lineage_locator(
                locator,
                candidate_version=candidate_version,
                reference_records=validation_records,
            )
        except B01ContractError as error:
            _b01_failure(error, "LineageLocator")
        if locator["lineage_id"] in admitted_lineage:
            fail("B02_LOCATOR_SET_INVALID", "duplicate LineageLocator")
        admitted_lineage[locator["lineage_id"]] = deepcopy(locator)
    for locator in evidence_locators:
        try:
            b01_validate_evidence_locator(
                locator,
                candidate_version=candidate_version,
                reference_records=validation_records,
            )
        except B01ContractError as error:
            _b01_failure(error, "EvidenceLocator")
        if locator["lineage_id"] in admitted_evidence:
            fail("B02_LOCATOR_SET_INVALID", "duplicate EvidenceLocator")
        admitted_evidence[locator["lineage_id"]] = deepcopy(locator)
    if set(admitted_lineage) != set(admitted_evidence):
        fail("B02_LOCATOR_SET_INVALID", "Lineage/Evidence locator set mismatch")
    return {
        "reference_records": deepcopy(reference_records),
        "segment_index": deepcopy(segment_index),
        "candidate_version": deepcopy(candidate_version),
        "lineage_locators": [
            admitted_lineage[key]
            for key in sorted(admitted_lineage, key=lambda item: item.encode("utf-8"))
        ],
        "evidence_locators": [
            admitted_evidence[key]
            for key in sorted(admitted_evidence, key=lambda item: item.encode("utf-8"))
        ],
        "segment_inputs": deepcopy(segment_inputs),
        "chapter_bytes_sha256": hashlib.sha256(chapter_bytes).hexdigest(),
    }


def validate_scope(
    payload: dict[str, Any],
    context: dict[str, Any],
    *,
    code: str = "B02_SCOPE_MISMATCH",
) -> None:
    candidate = context["candidate_version"]
    segment = context["segment_index"]
    if payload["base_candidate_version_ref"] != record_ref(candidate):
        fail(code, "candidate ref")
    if payload["candidate_schema_id"] != CANDIDATE_SCHEMA_ID:
        fail(code, "candidate schema")
    validate_chapter_revision_ref(payload["chapter_revision_ref"])
    if (
        payload["chapter_revision_ref"] != candidate["payload"]["chapter_revision_ref"]
        or payload["chapter_revision_ref"] != segment["payload"]["chapter_revision_ref"]
        or payload["seg"] != candidate["payload"]["seg"]
    ):
        fail(code, "revision or segment")


def _expected_source_locations(
    evidence: str, *, context: dict[str, Any]
) -> list[dict[str, int]]:
    chapter_bytes = _validate_segment_sources(
        context["segment_index"], context["segment_inputs"]
    )
    seg = context["candidate_version"]["payload"]["seg"]
    selected = context["segment_index"]["payload"]["segments"][seg - 1]
    evidence_bytes = evidence.encode("utf-8")
    locations: list[dict[str, int]] = []
    offset = 0
    while evidence_bytes and offset <= len(chapter_bytes) - len(evidence_bytes):
        start = chapter_bytes.find(evidence_bytes, offset)
        if start < 0:
            break
        end = start + len(evidence_bytes)
        if selected["start_byte"] <= start and end <= selected["end_byte"]:
            locations.append({"seg": seg, "start_byte": start, "end_byte": end})
        offset = start + 1
    return locations


def build_source_evidence_binding(
    evidence: str, *, context: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(evidence, str) or not evidence:
        fail("B02_SOURCE_EVIDENCE_INVALID", "evidence required")
    count = sentence_count(evidence)
    if count not in {1, 2}:
        fail("B02_SOURCE_EVIDENCE_INVALID", f"sentence_count={count}")
    locations = _expected_source_locations(evidence, context=context)
    if not locations:
        fail("B02_SOURCE_EVIDENCE_NOT_IN_EXACT_CHAPTER")
    without_hash = {
        "chapter_revision_ref": deepcopy(
            context["candidate_version"]["payload"]["chapter_revision_ref"]
        ),
        "evidence": evidence,
        "evidence_sha256": hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
        "sentence_count": count,
        "match_locations": locations,
    }
    return {**without_hash, "binding_hash": sha256_value(without_hash)}


def validate_source_evidence_binding(
    binding: dict[str, Any], *, context: dict[str, Any]
) -> None:
    exact_keys(
        binding,
        SOURCE_EVIDENCE_BINDING_KEYS,
        "B02_SOURCE_EVIDENCE_INVALID",
    )
    evidence = binding["evidence"]
    if not isinstance(evidence, str) or not evidence:
        fail("B02_SOURCE_EVIDENCE_INVALID", "evidence required")
    expected = build_source_evidence_binding(evidence, context=context)
    if binding != expected:
        fail("B02_SOURCE_EVIDENCE_INVALID", "binding does not match exact bytes")


def _validate_locator_pair(
    pair: dict[str, Any], *, context: dict[str, Any]
) -> None:
    exact_keys(pair, MATCHED_BINDING_KEYS, "B02_MATCHED_BINDING_INVALID")
    lineage = pair["lineage_locator"]
    evidence = pair["evidence_locator"]
    if not isinstance(lineage, dict) or not isinstance(evidence, dict):
        fail("B02_MATCHED_BINDING_INVALID", "both locators are required")
    candidate = context["candidate_version"]
    validation_records = [*context["reference_records"], context["segment_index"]]
    try:
        b01_validate_lineage_locator(
            lineage,
            candidate_version=candidate,
            reference_records=validation_records,
        )
        b01_validate_evidence_locator(
            evidence,
            candidate_version=candidate,
            reference_records=validation_records,
        )
    except B01ContractError as error:
        _b01_failure(error, "matched locator")
    if (
        lineage["candidate_version_ref"] != evidence["candidate_version_ref"]
        or lineage["candidate_version_ref"] != record_ref(candidate)
        or lineage["lineage_id"] != evidence["lineage_id"]
    ):
        fail("B02_MATCHED_BINDING_INVALID", "locator pair identity")
    admitted_pairs = {
        (
            item["lineage_id"],
            item["locator_hash"],
            next(
                evidence_item["locator_hash"]
                for evidence_item in context["evidence_locators"]
                if evidence_item["lineage_id"] == item["lineage_id"]
            ),
        )
        for item in context["lineage_locators"]
    }
    identity = (
        lineage["lineage_id"],
        lineage["locator_hash"],
        evidence["locator_hash"],
    )
    if identity not in admitted_pairs:
        fail("B02_MATCHED_BINDING_INVALID", "locator pair not admitted")


def validate_matched_candidate_bindings(
    bindings: list[dict[str, Any]],
    *,
    candidate_match: str,
    context: dict[str, Any],
) -> None:
    if not isinstance(bindings, list):
        fail("B02_MATCHED_BINDING_INVALID", "list required")
    if candidate_match == "MISSING":
        if bindings:
            fail("B02_MISSING_MATCHED_REFS_FORBIDDEN")
        return
    if not bindings:
        fail("B02_MATCHED_BINDING_REQUIRED", candidate_match)
    stable = sorted(
        bindings,
        key=lambda pair: (
            pair.get("lineage_locator", {}).get("locator_hash", ""),
            pair.get("evidence_locator", {}).get("locator_hash", ""),
        ),
    )
    if bindings != stable or len({canonical_bytes(pair) for pair in bindings}) != len(
        bindings
    ):
        fail("B02_MATCHED_BINDING_INVALID", "unique canonical order required")
    for pair in bindings:
        _validate_locator_pair(pair, context=context)


def validate_identity_record(record: dict[str, Any]) -> None:
    validate_b02_output_record(record)
    if record["record_type"] != "M3_DIAGNOSTIC_RECORDER_IDENTITY":
        fail("B02_WRITER_IDENTITY_INVALID", "record type")
    exact_keys(record["payload"], IDENTITY_PAYLOAD_KEYS, "B02_WRITER_IDENTITY_INVALID")
    if (
        record["payload"]["writer"] != "DiagnosticRecorder"
        or not isinstance(record["payload"]["writer_version"], str)
        or not record["payload"]["writer_version"]
        or record["payload"]["writer_version"] == DOCUMENT_IDENTITY
    ):
        fail("B02_WRITER_IDENTITY_INVALID", "payload")


def validate_diagnostic_record(
    record: dict[str, Any], *, context: dict[str, Any], records: list[dict[str, Any]]
) -> None:
    validate_b02_output_record(record)
    if record["record_type"] != "M3_DIAGNOSTIC":
        fail("B02_DIAGNOSTIC_INVALID", "record type")
    payload = record["payload"]
    exact_keys(payload, DIAGNOSTIC_PAYLOAD_KEYS, "B02_DIAGNOSTIC_INVALID")
    validate_scope(payload, context)
    if not isinstance(payload["axis"], str) or not payload["axis"]:
        fail("B02_DIAGNOSTIC_INVALID", "axis")
    if not isinstance(payload["severity"], str) or not payload["severity"]:
        fail("B02_DIAGNOSTIC_INVALID", "severity")
    if not is_sha256(payload["fingerprint"]):
        fail("B02_DIAGNOSTIC_INVALID", "fingerprint")
    target = payload["target"]
    exact_keys(
        target,
        {"kind", "lineage_locator", "evidence_locator"},
        "B02_DIAGNOSTIC_INVALID",
    )
    if target["kind"] != "CANDIDATE_ITEM_EVIDENCE":
        fail("B02_DIAGNOSTIC_INVALID", "target kind")
    _validate_locator_pair(
        {
            "lineage_locator": target["lineage_locator"],
            "evidence_locator": target["evidence_locator"],
        },
        context=context,
    )
    validate_record_ref(
        payload["writer_identity_ref"],
        code="B02_WRITER_IDENTITY_INVALID",
        records=records,
        expected_type="M3_DIAGNOSTIC_RECORDER_IDENTITY",
        allowed_access=ALLOWED_ACCESS,
        expected_source_module=SOURCE_MODULE,
    )


def validate_lifecycle_record(
    record: dict[str, Any], *, records: list[dict[str, Any]]
) -> None:
    validate_b02_output_record(record)
    if record["record_type"] != "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT":
        fail("B02_LIFECYCLE_INVALID", "record type")
    payload = record["payload"]
    exact_keys(payload, LIFECYCLE_PAYLOAD_KEYS, "B02_LIFECYCLE_INVALID")
    validate_record_ref(
        payload["diagnostic_ref"],
        code="B02_LIFECYCLE_INVALID",
        records=records,
        expected_type="M3_DIAGNOSTIC",
        allowed_access=ALLOWED_ACCESS,
        expected_source_module=SOURCE_MODULE,
    )
    if not is_non_bool_int(payload["lifecycle_sequence"]) or payload[
        "lifecycle_sequence"
    ] < 1:
        fail("B02_LIFECYCLE_INVALID", "sequence")
    if payload["event"] not in TERMINAL_EVENTS:
        fail("B02_LIFECYCLE_INVALID", "event")
    parse_utc(payload["effective_at"], "B02_LIFECYCLE_INVALID")
    if not isinstance(payload["reason_code"], str) or re.fullmatch(
        r"[A-Z][A-Z0-9_]*", payload["reason_code"]
    ) is None:
        fail("B02_LIFECYCLE_INVALID", "reason code")
    if payload["resolution_ref"] is not None:
        fail("B02_LIFECYCLE_INVALID", "resolution ref must be null")


def validate_coverage_record(
    record: dict[str, Any], *, context: dict[str, Any], records: list[dict[str, Any]]
) -> None:
    validate_b02_output_record(record)
    if record["record_type"] != "M3_COVERAGE_OBSERVATION":
        fail("B02_COVERAGE_INVALID", "record type")
    payload = record["payload"]
    exact_keys(payload, COVERAGE_PAYLOAD_KEYS, "B02_COVERAGE_INVALID")
    validate_scope(payload, context)
    if not isinstance(payload["source_observation_id"], str) or not payload[
        "source_observation_id"
    ]:
        fail("B02_COVERAGE_INVALID", "source observation id")
    if not isinstance(payload["axis"], str) or not payload["axis"]:
        fail("B02_COVERAGE_INVALID", "axis")
    if payload["candidate_match"] not in COVERAGE_MATCHES:
        fail("B02_COVERAGE_MATCH_INVALID")
    validate_source_evidence_binding(
        payload["source_evidence_binding"], context=context
    )
    validate_matched_candidate_bindings(
        payload["matched_candidate_bindings"],
        candidate_match=payload["candidate_match"],
        context=context,
    )
    validate_record_ref(
        payload["observer_ref"],
        code="B02_WRITER_IDENTITY_INVALID",
        records=records,
        expected_type="M3_DIAGNOSTIC_RECORDER_IDENTITY",
        allowed_access=ALLOWED_ACCESS,
        expected_source_module=SOURCE_MODULE,
    )


def guard_write_path(repository_relative_path: str) -> None:
    if not repository_relative_path.startswith(WRITE_SET_PREFIX):
        fail("B02_WRITE_SET_ESCAPE", repository_relative_path)


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
    "dynamic_eval",
    "credential_read",
    "real_novel_read",
    "patch_write",
    "candidate_version_write",
    "pointer_write",
}


def guard_runtime_event(event: str) -> None:
    if event in FORBIDDEN_RUNTIME_EVENTS:
        if event in {"patch_write", "candidate_version_write", "pointer_write"}:
            fail("B02_CANDIDATE_WRITE_FORBIDDEN", event)
        fail("B02_RUNTIME_EVENT_FORBIDDEN", event)
