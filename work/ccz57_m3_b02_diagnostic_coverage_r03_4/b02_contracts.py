"""CCZ-57 M3 B-02 immutable diagnostic and coverage contracts.

This module is fixture-only.  It contains no model, network, subprocess,
dynamic-import, or real-novel access path.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

CONTRACT_VERSION = "r03.3-candidate"
DOCUMENT_IDENTITY = "CCZ57-M3-B02-R02-CANDIDATE"
IMMUTABLE_CONTRACT = "M3_IMMUTABLE_RECORD"
RECORD_REF_CONTRACT = "M3_RECORD_REF"
LINEAGE_LOCATOR_CONTRACT = "M3_LINEAGE_LOCATOR"
SOURCE_MODULE = "M3"
FIXTURE_ACCESS = "POLICY_FIXTURE_READ_ONLY"
RUN_ACCESS = "RUN_INTERNAL_READ_ONLY"
RETENTION_CLASS = "CORE_IMMUTABLE_AUDIT"
WRITE_SET_PREFIX = "work/ccz57_m3_b02_diagnostic_coverage_r03_4/"

EXPECTED_A_REVIEWED_HEAD = "9eafdac71f412be3f7b8ad5fd81ffc84c3de3a26"
EXPECTED_A_MERGE_SHA = "019df751641533c7de4d56aa38f50747fb564036"
EXPECTED_A_ADMISSION_HASH = (
    "91257566a8c4fc662b5735ce1a1abebd905bf148b23ad594dfcf21b8410c65af"
)
EXPECTED_A_ADMISSION_FILE_SHA256 = (
    "5d326296d2028f87772f1f24836b4885bfe395909a7e74aa331870d5023aa7c0"
)
EXPECTED_B01_REVIEWED_HEAD = "24a89a4a705138308f2db5a9f94dc09e74bb4c28"
EXPECTED_B01_MERGE_SHA = "905346f56cd51259c15a9517ead1517227c1719a"
EXPECTED_B01_RECEIPT_FILE_SHA256 = (
    "98ab63f1b8ff34844ba346839cb7471aeb784d400282f12c3d4fb686a5183138"
)
EXPECTED_B01_RECEIPT_HASH = (
    "81544ef084908480acd3466bbd167f577cdd700de7e70967e782204fc67974a6"
)
EXPECTED_B01_SEGMENT_RECORD_ID = (
    "segidx:fixture-project-001:synthetic-chapter-001:r7:7032bdcb88ad"
)
EXPECTED_B01_SEGMENT_RECORD_HASH = (
    "a8e993d61ec35d849a580d3179e56e8104807f13241f3845f78d86b6c7170d6b"
)
EXPECTED_B01_CANDIDATE_RECORD_ID = (
    "cv:2a17b0a756cd:4436d087de901f60aa12d8d212cbd33d"
)
EXPECTED_B01_CANDIDATE_RECORD_HASH = (
    "09e4a6f59c35d7a9694976e6fb5bf3f41690dd322deb2f57aa7e9969a9c187cf"
)
EXPECTED_B01_LINEAGE_LOCATOR_HASH = (
    "5827eec5c9e33ff5243277d10272287ba6e33764a3b4e893829ac7100154701c"
)
EXPECTED_B01_ORIGIN_ATTEMPT_RECORD_ID = "attempt_fixture_001"
EXPECTED_B01_ORIGIN_ATTEMPT_RECORD_HASH = (
    "fef276f8a06b1aa052b57a12092f4db39a9597752f258003ac979f115f972b3b"
)

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
LOCATOR_KEYS = {
    "contract",
    "contract_version",
    "candidate_version_ref",
    "lineage_id",
    "json_pointer",
    "item_hash",
    "locator_hash",
}
IDENTITY_PAYLOAD_KEYS = {"writer", "writer_version"}
DIAGNOSTIC_PAYLOAD_KEYS = {
    "base_candidate_version_ref",
    "chapter_revision_ref",
    "seg",
    "axis",
    "severity",
    "target",
    "evidence_refs",
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
    "chapter_revision_ref",
    "seg",
    "source_observation_id",
    "source_span_hash",
    "axis",
    "candidate_match",
    "observer_ref",
}


class B02ContractError(ValueError):
    """Stable, machine-readable B-02 contract failure."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def fail(code: str, detail: str = "") -> None:
    raise B02ContractError(code, detail)


def normalize(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        fail("B02_CANONICAL_VALUE_INVALID", "floating-point values are forbidden")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                fail("B02_CANONICAL_KEY_INVALID", "object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                fail("B02_CANONICAL_DUPLICATE_KEY", normalized_key)
            normalized[normalized_key] = normalize(item)
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
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as error:
        fail(code, str(error))
    return parsed


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
    if record["record_type"] not in OUTPUT_TYPES and not isinstance(
        record["record_type"], str
    ):
        fail("B02_IMMUTABLE_ENVELOPE_INVALID", "record type")
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
    expected_hash = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    if record["record_hash"] != expected_hash:
        fail("B02_RECORD_HASH_MISMATCH", record["record_id"])


def validate_b02_output_record(record: dict[str, Any]) -> None:
    """Require the exact B-02 immutable envelope, not a generic upstream one."""
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


def validate_segment_index(record: dict[str, Any]) -> None:
    validate_record(record)
    if record["record_type"] != "M3_SEGMENT_INDEX_SNAPSHOT":
        fail("B02_B01_RECORD_REF_DRIFT", "segment type")
    payload = record["payload"]
    expected = {
        "project_scope_id",
        "author_workspace_logical_key",
        "source_module_identity",
        "chapter_revision_ref",
        "stable_segment_index_id",
        "segments",
    }
    exact_keys(payload, expected, "B02_B01_RECORD_REF_DRIFT")
    validate_chapter_revision_ref(payload["chapter_revision_ref"])
    if not isinstance(payload["segments"], list) or not payload["segments"]:
        fail("B02_B01_RECORD_REF_DRIFT", "segments")
    prior_end = 0
    for expected_seg, segment in enumerate(payload["segments"], start=1):
        exact_keys(
            segment,
            {"seg", "start", "end", "responsibility_text_sha256"},
            "B02_B01_RECORD_REF_DRIFT",
        )
        if (
            segment["seg"] != expected_seg
            or not is_non_bool_int(segment["start"])
            or not is_non_bool_int(segment["end"])
            or segment["start"] != prior_end
            or segment["end"] <= segment["start"]
            or not is_sha256(segment["responsibility_text_sha256"])
        ):
            fail("B02_B01_RECORD_REF_DRIFT", "segment")
        prior_end = segment["end"]


def validate_candidate_version(record: dict[str, Any]) -> None:
    validate_record(record)
    if record["record_type"] != "M3_CANDIDATE_VERSION":
        fail("B02_B01_RECORD_REF_DRIFT", "candidate type")
    payload = record["payload"]
    expected = {
        "chapter_revision_ref",
        "seg",
        "parent_candidate_version_ref",
        "origin_attempt_refs",
        "origin_commit_intent_ref",
        "items",
        "lineage_index",
        "version_payload_hash",
    }
    exact_keys(payload, expected, "B02_B01_RECORD_REF_DRIFT")
    validate_chapter_revision_ref(payload["chapter_revision_ref"])
    if not is_non_bool_int(payload["seg"]) or payload["seg"] < 1:
        fail("B02_B01_RECORD_REF_DRIFT", "candidate segment")
    if not isinstance(payload["origin_attempt_refs"], list) or not payload[
        "origin_attempt_refs"
    ]:
        fail("B02_B01_RECORD_REF_DRIFT", "origin attempts")
    for ref in payload["origin_attempt_refs"]:
        validate_record_ref(ref, code="B02_B01_RECORD_REF_DRIFT")
    if not isinstance(payload["items"], list) or not isinstance(
        payload["lineage_index"], list
    ):
        fail("B02_B01_RECORD_REF_DRIFT", "items or lineage index")
    if len(payload["items"]) != len(payload["lineage_index"]):
        fail("B02_B01_RECORD_REF_DRIFT", "lineage cardinality")
    for index, (item, lineage) in enumerate(
        zip(payload["items"], payload["lineage_index"], strict=True)
    ):
        exact_keys(item, {"lineage_id", "text", "quote", "item_hash"}, "B02_B01_RECORD_REF_DRIFT")
        exact_keys(
            lineage,
            {"lineage_id", "json_pointer", "item_hash"},
            "B02_B01_RECORD_REF_DRIFT",
        )
        if (
            lineage["lineage_id"] != item["lineage_id"]
            or lineage["json_pointer"] != f"/items/{index}"
            or lineage["item_hash"] != item["item_hash"]
            or not is_sha256(item["item_hash"])
        ):
            fail("B02_B01_RECORD_REF_DRIFT", "lineage index")
    payload_without_hash = {
        key: value for key, value in payload.items() if key != "version_payload_hash"
    }
    if payload["version_payload_hash"] != sha256_value(payload_without_hash):
        fail("B02_B01_RECORD_REF_DRIFT", "version payload hash")


def validate_lineage_locator(
    locator: dict[str, Any], candidate: dict[str, Any]
) -> None:
    exact_keys(locator, LOCATOR_KEYS, "B02_LINEAGE_LOCATOR_INVALID")
    if (
        locator["contract"] != LINEAGE_LOCATOR_CONTRACT
        or locator["contract_version"] != CONTRACT_VERSION
    ):
        fail("B02_LINEAGE_LOCATOR_INVALID", "contract")
    if locator["candidate_version_ref"] != record_ref(candidate):
        fail("B02_LINEAGE_LOCATOR_INVALID", "candidate ref")
    if not is_sha256(locator["item_hash"]) or not is_sha256(locator["locator_hash"]):
        fail("B02_LINEAGE_LOCATOR_INVALID", "hash")
    matches = [
        entry
        for entry in candidate["payload"]["lineage_index"]
        if entry["lineage_id"] == locator["lineage_id"]
        and entry["json_pointer"] == locator["json_pointer"]
        and entry["item_hash"] == locator["item_hash"]
    ]
    if len(matches) != 1:
        fail("B02_LINEAGE_LOCATOR_INVALID", "locator does not resolve uniquely")
    try:
        index = int(locator["json_pointer"].removeprefix("/items/"))
        item = candidate["payload"]["items"][index]
    except (ValueError, IndexError):
        fail("B02_LINEAGE_LOCATOR_INVALID", "path")
    if item["lineage_id"] != locator["lineage_id"] or item["item_hash"] != locator[
        "item_hash"
    ]:
        fail("B02_LINEAGE_LOCATOR_INVALID", "item")
    expected_hash = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    if locator["locator_hash"] != expected_hash:
        fail("B02_LINEAGE_LOCATOR_INVALID", "locator hash")


def _resolved(ref: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [record for record in records if record_ref(record) == ref]
    if len(matches) != 1:
        fail("B02_REFERENCE_INTEGRITY_FAILED", "reference does not resolve uniquely")
    return matches[0]


def validate_a_admission(
    admission: dict[str, Any] | None, reference_records: list[dict[str, Any]]
) -> None:
    if not admission:
        fail("B02_A_ADMISSION_REQUIRED")
    validate_record(admission)
    if (
        admission["record_type"] != "M3_A_INTERFACE_ADMISSION_RECEIPT"
        or admission["record_hash"] != EXPECTED_A_ADMISSION_HASH
        or admission["record_version"] != 1
        or admission["access"] != RUN_ACCESS
        or admission["source_module"] != "M3_B_ADMISSION"
    ):
        fail("B02_A_ADMISSION_DRIFT")
    payload = admission["payload"]
    required = {
        "repository",
        "issue_number",
        "pr_number",
        "review_receipt_ref",
        "reviewed_pr_head_sha",
        "pr_head_sha_at_merge",
        "reviewed_head_equals_merge_head",
        "merge_commit_sha",
        "current_main_sha",
        "merge_commit_reachable_from_current_main",
        "a_interface_manifest_ref",
        "a_interface_manifest_sha256",
        "current_main_readback_passed",
        "pr_gate_observation",
        "admission_mode",
        "admission_result",
        "b_code_start_authorized",
    }
    exact_keys(payload, required, "B02_A_ADMISSION_DRIFT")
    if (
        payload["repository"] != "cczz412/novel-architecture"
        or payload["issue_number"] != 176
        or payload["pr_number"] != 186
        or payload["reviewed_pr_head_sha"] != EXPECTED_A_REVIEWED_HEAD
        or payload["pr_head_sha_at_merge"] != EXPECTED_A_REVIEWED_HEAD
        or payload["reviewed_head_equals_merge_head"] is not True
        or payload["merge_commit_sha"] != EXPECTED_A_MERGE_SHA
        or payload["merge_commit_reachable_from_current_main"] is not True
        or payload["current_main_readback_passed"] is not True
        or payload["admission_result"] != "PASS"
        or payload["b_code_start_authorized"] is not True
    ):
        fail("B02_A_ADMISSION_DRIFT")
    validate_record_ref(
        payload["review_receipt_ref"],
        code="B02_A_ADMISSION_DRIFT",
        records=reference_records,
        expected_type="A_EXACT_HEAD_REVIEW_RECEIPT",
    )
    validate_record_ref(
        payload["a_interface_manifest_ref"],
        code="B02_A_ADMISSION_DRIFT",
        records=reference_records,
        expected_type="A_INTERFACE_MANIFEST",
    )


MERGE_RECEIPT_KEYS = {
    "receipt_scope",
    "repository",
    "pr_number",
    "reviewed_head",
    "merge_commit",
    "current_main",
    "merge_commit_reachable_from_current_main",
    "file_sha256",
    "receipt_hash",
    "segment_index_ref",
    "candidate_version_ref",
    "allowed_lineage_locator_hashes",
    "allowed_origin_attempt_refs",
}


def _expected_b01_ref(
    *, record_type: str, record_id: str, record_hash: str, source_module: str = SOURCE_MODULE
) -> dict[str, Any]:
    return {
        "contract": RECORD_REF_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "record_type": record_type,
        "record_id": record_id,
        "record_version": 1,
        "record_contract_version": CONTRACT_VERSION,
        "record_hash": record_hash,
        "access": FIXTURE_ACCESS,
        "source_module": source_module,
    }


def _parse_receipt_bytes(
    raw: bytes | None,
    *,
    expected_file_sha256: str,
    missing_code: str,
    drift_code: str,
) -> dict[str, Any]:
    if raw is None:
        fail(missing_code)
    if not isinstance(raw, bytes):
        fail(drift_code, "raw bytes required")
    if hashlib.sha256(raw).hexdigest() != expected_file_sha256:
        fail(drift_code, "file sha256")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(drift_code, str(error))
    if not isinstance(parsed, dict):
        fail(drift_code, "JSON object required")
    return parsed


def _minimal_b01_receipt(raw_receipt: dict[str, Any]) -> dict[str, Any]:
    expected_receipt_hash = sha256_value(
        {key: value for key, value in raw_receipt.items() if key != "receipt_hash"}
    )
    if (
        raw_receipt.get("receipt_hash_algorithm")
        != "sha256(canonical_json(receipt_without_receipt_hash))"
        or raw_receipt.get("receipt_hash") != expected_receipt_hash
        or expected_receipt_hash != EXPECTED_B01_RECEIPT_HASH
    ):
        fail("B02_B01_MERGE_REQUIRED", "receipt hash")
    try:
        pr = raw_receipt["pr"]
        current_main = raw_receipt["current_main_readback"]
        fixture_inputs = raw_receipt["b02_admissible_fixture_inputs"]
        locators = fixture_inputs["allowed_lineage_locators"]
    except (KeyError, TypeError) as error:
        fail("B02_B01_MERGE_REQUIRED", f"receipt shape: {error}")
    return {
        "receipt_scope": raw_receipt.get("receipt_scope"),
        "repository": raw_receipt.get("repository"),
        "pr_number": pr.get("number"),
        "reviewed_head": pr.get("reviewed_head"),
        "merge_commit": pr.get("merge_commit"),
        "current_main": current_main.get("sha"),
        "merge_commit_reachable_from_current_main": current_main.get(
            "merge_commit_reachable_from_current_main"
        ),
        "file_sha256": EXPECTED_B01_RECEIPT_FILE_SHA256,
        "receipt_hash": raw_receipt.get("receipt_hash"),
        "segment_index_ref": fixture_inputs.get("segment_index_ref"),
        "candidate_version_ref": fixture_inputs.get("candidate_version_ref"),
        "allowed_lineage_locator_hashes": sorted(
            locator.get("locator_hash") for locator in locators
        ),
        "allowed_origin_attempt_refs": fixture_inputs.get("origin_attempt_refs"),
    }


def validate_upstream_context(
    *,
    admission_bytes: bytes | None,
    merge_receipt_bytes: bytes | None,
    reference_records: list[dict[str, Any]],
    lineage_locators: list[dict[str, Any]],
) -> dict[str, Any]:
    admission = _parse_receipt_bytes(
        admission_bytes,
        expected_file_sha256=EXPECTED_A_ADMISSION_FILE_SHA256,
        missing_code="B02_A_ADMISSION_REQUIRED",
        drift_code="B02_A_ADMISSION_DRIFT",
    )
    validate_a_admission(admission, reference_records)
    raw_merge_receipt = _parse_receipt_bytes(
        merge_receipt_bytes,
        expected_file_sha256=EXPECTED_B01_RECEIPT_FILE_SHA256,
        missing_code="B02_B01_MERGE_REQUIRED",
        drift_code="B02_B01_MERGE_REQUIRED",
    )
    merge_receipt = _minimal_b01_receipt(raw_merge_receipt)
    exact_keys(merge_receipt, MERGE_RECEIPT_KEYS, "B02_B01_MERGE_REQUIRED")
    if (
        merge_receipt["receipt_scope"]
        != "CONSTRUCTION_EVIDENCE_ONLY_NOT_M3_PRODUCT_RECORD"
        or merge_receipt["repository"] != "cczz412/novel-architecture"
        or merge_receipt["pr_number"] != 190
        or merge_receipt["reviewed_head"] != EXPECTED_B01_REVIEWED_HEAD
        or merge_receipt["merge_commit"] != EXPECTED_B01_MERGE_SHA
        or merge_receipt["file_sha256"] != EXPECTED_B01_RECEIPT_FILE_SHA256
        or merge_receipt["receipt_hash"] != EXPECTED_B01_RECEIPT_HASH
    ):
        fail("B02_B01_MERGE_REQUIRED", "receipt identity")
    if (
        merge_receipt["current_main"] != EXPECTED_B01_MERGE_SHA
        or merge_receipt["merge_commit_reachable_from_current_main"] is not True
    ):
        fail("B02_B01_MAIN_UNREACHABLE")
    segment_ref = merge_receipt["segment_index_ref"]
    candidate_ref = merge_receipt["candidate_version_ref"]
    expected_segment_ref = _expected_b01_ref(
        record_type="M3_SEGMENT_INDEX_SNAPSHOT",
        record_id=EXPECTED_B01_SEGMENT_RECORD_ID,
        record_hash=EXPECTED_B01_SEGMENT_RECORD_HASH,
    )
    expected_candidate_ref = _expected_b01_ref(
        record_type="M3_CANDIDATE_VERSION",
        record_id=EXPECTED_B01_CANDIDATE_RECORD_ID,
        record_hash=EXPECTED_B01_CANDIDATE_RECORD_HASH,
    )
    if segment_ref != expected_segment_ref or candidate_ref != expected_candidate_ref:
        fail("B02_B01_RECORD_REF_DRIFT", "merged B-01 fixture identity")
    validate_record_ref(
        segment_ref,
        code="B02_B01_RECORD_REF_DRIFT",
        records=reference_records,
        expected_type="M3_SEGMENT_INDEX_SNAPSHOT",
        allowed_access={FIXTURE_ACCESS},
        expected_source_module=SOURCE_MODULE,
    )
    validate_record_ref(
        candidate_ref,
        code="B02_B01_RECORD_REF_DRIFT",
        records=reference_records,
        expected_type="M3_CANDIDATE_VERSION",
        allowed_access={FIXTURE_ACCESS},
        expected_source_module=SOURCE_MODULE,
    )
    segment = _resolved(segment_ref, reference_records)
    candidate = _resolved(candidate_ref, reference_records)
    validate_segment_index(segment)
    validate_candidate_version(candidate)
    if segment["payload"]["chapter_revision_ref"] != candidate["payload"][
        "chapter_revision_ref"
    ]:
        fail("B02_SCOPE_MISMATCH", "revision")
    seg = candidate["payload"]["seg"]
    if not any(item["seg"] == seg for item in segment["payload"]["segments"]):
        fail("B02_SCOPE_MISMATCH", "segment")
    if not lineage_locators:
        fail("B02_LINEAGE_LOCATOR_INVALID", "empty set")
    for locator in lineage_locators:
        validate_lineage_locator(locator, candidate)
    locator_hashes = sorted(locator["locator_hash"] for locator in lineage_locators)
    if (
        locator_hashes != [EXPECTED_B01_LINEAGE_LOCATOR_HASH]
        or locator_hashes != sorted(merge_receipt["allowed_lineage_locator_hashes"])
    ):
        fail("B02_LINEAGE_LOCATOR_INVALID", "allowed set")
    origin_refs = candidate["payload"]["origin_attempt_refs"]
    expected_origin_refs = [
        _expected_b01_ref(
            record_type="A_RAW_ATTEMPT_RECEIPT",
            record_id=EXPECTED_B01_ORIGIN_ATTEMPT_RECORD_ID,
            record_hash=EXPECTED_B01_ORIGIN_ATTEMPT_RECORD_HASH,
            source_module="A_STAGE_FIXTURE",
        )
    ]
    if canonical_bytes(origin_refs) != canonical_bytes(
        merge_receipt["allowed_origin_attempt_refs"]
    ) or canonical_bytes(origin_refs) != canonical_bytes(expected_origin_refs):
        fail("B02_EVIDENCE_OUT_OF_SCOPE", "allowed origin attempts")
    return {
        "admission": deepcopy(admission),
        "merge_receipt": deepcopy(merge_receipt),
        "segment_index": deepcopy(segment),
        "candidate_version": deepcopy(candidate),
        "lineage_locators": deepcopy(lineage_locators),
        "origin_attempt_refs": deepcopy(origin_refs),
    }


def validate_scope(
    payload: dict[str, Any], context: dict[str, Any], *, code: str = "B02_SCOPE_MISMATCH"
) -> None:
    candidate = context["candidate_version"]
    segment = context["segment_index"]
    if payload["base_candidate_version_ref"] != record_ref(candidate):
        fail(code, "candidate ref")
    validate_chapter_revision_ref(payload["chapter_revision_ref"])
    if (
        payload["chapter_revision_ref"] != candidate["payload"]["chapter_revision_ref"]
        or payload["chapter_revision_ref"] != segment["payload"]["chapter_revision_ref"]
        or payload["seg"] != candidate["payload"]["seg"]
        or not any(
            entry["seg"] == payload["seg"] for entry in segment["payload"]["segments"]
        )
    ):
        fail(code, "revision or segment")


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
    exact_keys(target, {"kind", "lineage_locator"}, "B02_DIAGNOSTIC_INVALID")
    if target["kind"] != "LINEAGE":
        fail("B02_DIAGNOSTIC_INVALID", "target kind")
    candidate = context["candidate_version"]
    validate_lineage_locator(target["lineage_locator"], candidate)
    allowed_hashes = {
        locator["locator_hash"] for locator in context["lineage_locators"]
    }
    if target["lineage_locator"]["locator_hash"] not in allowed_hashes:
        fail("B02_LINEAGE_LOCATOR_INVALID", "not admitted")
    if not isinstance(payload["evidence_refs"], list) or not payload["evidence_refs"]:
        fail("B02_EVIDENCE_OUT_OF_SCOPE", "empty")
    stable_evidence = sorted(
        payload["evidence_refs"],
        key=lambda ref: (
            ref.get("record_type", ""),
            ref.get("record_id", ""),
            ref.get("record_version", 0),
            ref.get("record_hash", ""),
        ),
    )
    if payload["evidence_refs"] != stable_evidence or len(
        {canonical_bytes(ref) for ref in payload["evidence_refs"]}
    ) != len(payload["evidence_refs"]):
        fail("B02_EVIDENCE_OUT_OF_SCOPE", "evidence must be unique and sorted")
    allowed_evidence = {
        canonical_bytes(ref) for ref in context["origin_attempt_refs"]
    }
    for ref in payload["evidence_refs"]:
        validate_record_ref(ref, code="B02_EVIDENCE_OUT_OF_SCOPE")
        if canonical_bytes(ref) not in allowed_evidence:
            fail("B02_EVIDENCE_OUT_OF_SCOPE")
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
    if not is_sha256(payload["source_span_hash"]):
        fail("B02_COVERAGE_INVALID", "source span hash")
    if not isinstance(payload["axis"], str) or not payload["axis"]:
        fail("B02_COVERAGE_INVALID", "axis")
    if payload["candidate_match"] not in COVERAGE_MATCHES:
        fail("B02_COVERAGE_MATCH_INVALID")
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
    "real_novel_read",
    "candidate_version_write",
    "pointer_write",
}


def guard_runtime_event(event: str) -> None:
    if event in FORBIDDEN_RUNTIME_EVENTS:
        if event in {"candidate_version_write", "pointer_write"}:
            fail("B02_CANDIDATE_WRITE_FORBIDDEN", event)
        fail("B02_RUNTIME_EVENT_FORBIDDEN", event)
