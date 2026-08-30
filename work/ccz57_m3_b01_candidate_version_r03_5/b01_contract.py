"""CCZ-57 M3 B-01 r03.5 offline candidate-version contract.

This module intentionally has no model, network, subprocess, or dynamic-import path.
It operates only on synthetic fixture data and a caller-provided fixture directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, ClassVar

CONTRACT_VERSION = "r03.5-candidate"
LEGACY_CONTRACT_VERSION = "r03.3-candidate"
CANDIDATE_SCHEMA_ID = "novel-fact-extraction-v2.1"
CCZ142_EXTRACTION_SOURCE_LANE = "CCZ142_TEXT_EXTRACTION_CANDIDATES"
CCZ142_EXTRACTION_SOURCE_MODULE = "CCZ-142"
CCZ142_EXTRACTION_HANDOFF_CONTRACT = "CCZ142_B01_EXTRACTION_HANDOFF_V1_CANDIDATE"
IMMUTABLE_CONTRACT = "M3_IMMUTABLE_RECORD"
RECORD_REF_CONTRACT = "M3_RECORD_REF"
LINEAGE_LOCATOR_CONTRACT = "M3_LINEAGE_LOCATOR"
EVIDENCE_LOCATOR_CONTRACT = "M3_EVIDENCE_LOCATOR"
SOURCE_MODULE = "M3"
FIXTURE_ACCESS = "POLICY_FIXTURE_READ_ONLY"
IMMUTABLE_RETENTION = "CORE_IMMUTABLE_AUDIT"
FIXTURE_POINTER_NAMESPACE = "FIXTURE_ONLY"
WRITE_SET_PREFIX = "work/ccz57_m3_b01_candidate_version_r03_5/"
COORDINATE_UNIT = "UTF8_BYTE"
SOURCE_GENERATION_RECORD_TYPE = "M1_ACCEPTED_SOURCE_GENERATION"
WRITING_MATERIAL_RECORD_TYPE = "M1_WRITING_MATERIAL"
REQUIRED_MATERIAL_KINDS = {"GENRE", "CORE_CHARACTER"}
OPTIONAL_MATERIAL_KINDS = {"PLATFORM", "SYNOPSIS", "PLAN"}
ALLOWED_MATERIAL_KINDS = REQUIRED_MATERIAL_KINDS | OPTIONAL_MATERIAL_KINDS
ALLOWED_STATUSES = {
    "已发生",
    "正在发生",
    "计划",
    "承诺",
    "条件",
    "推测",
    "误信",
    "否定",
}
SENTENCE_END_RE = re.compile(r"[。？！]+")
SENTENCE_WRAPPERS = " \t\r\n\"'“”‘’（）()《》〈〉【】[]「」『』"
FORBIDDEN_RUNTIME_EVENTS = {
    "network",
    "model_api",
    "subprocess",
    "dynamic_import",
    "credential_read",
    "real_novel_read",
    "product_pointer_write",
}

CCZ142_HANDOFF_KEYS = {
    "source_lane",
    "source_module",
    "source_contract_version",
    "candidate_schema_id",
    "project_scope_id",
    "author_workspace_logical_key",
    "chapter_revision_ref",
    "accepted_source_generation_ref",
    "writing_material_refs",
    "source_module_identity",
    "segment_inputs",
    "seg",
    "origin_attempt_refs",
    "raw_items",
}

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
LIVE_POINTER_KEYS = {
    "project_scope_id",
    "author_workspace_logical_key",
    "logical_pointer_key",
    "pointer_namespace",
    "candidate_schema_id",
    "input_binding_hash",
    "chapter_revision_ref",
    "seg",
    "generation",
    "current_candidate_version_ref",
}
ADMISSION_PAYLOAD_KEYS = {
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
EXPECTED_REVIEWED_HEAD = "9eafdac71f412be3f7b8ad5fd81ffc84c3de3a26"
EXPECTED_A_MERGE_COMMIT = "019df751641533c7de4d56aa38f50747fb564036"
EXPECTED_A_INTERFACE_PAYLOAD_HASH = (
    "50c5c74c67678565693dd86c27dab20319a0d107bb9d196b21d23643843ca860"
)
EXPECTED_A_ADMISSION_ID = "a_admission_pr186_019df751_20260828"
EXPECTED_A_ADMISSION_HASH = (
    "91257566a8c4fc662b5735ce1a1abebd905bf148b23ad594dfcf21b8410c65af"
)
EXPECTED_A_ADMISSION_CREATED_AT = "2026-08-28T03:26:14Z"
_SEGMENT_WRITER_TOKEN = object()
_CANDIDATE_WRITER_TOKEN = object()
_POINTER_WRITER_TOKEN = object()
_B_OUTPUT_WRITER_TOKENS = {
    "M3_SEGMENT_INDEX_SNAPSHOT": _SEGMENT_WRITER_TOKEN,
    "M3_CANDIDATE_VERSION": _CANDIDATE_WRITER_TOKEN,
    "M3_CANDIDATE_POINTER_SNAPSHOT": _POINTER_WRITER_TOKEN,
}


class B01ContractError(ValueError):
    """Stable, machine-readable failure for the B-01 boundary."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _fail(code: str, detail: str = "") -> None:
    raise B01ContractError(code, detail)


_SOURCE_BOUND_STRING_KEYS = {"evidence"}


def _normalize(value: Any, *, preserve_string_value: bool = False) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        _fail("B01_CANONICAL_VALUE_INVALID", "floating-point values are forbidden")
    if isinstance(value, str):
        return value if preserve_string_value else unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [
            _normalize(item, preserve_string_value=preserve_string_value)
            for item in value
        ]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                _fail("B01_CANONICAL_KEY_INVALID", "object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                _fail("B01_CANONICAL_DUPLICATE_KEY", normalized_key)
            normalized[normalized_key] = _normalize(
                item,
                preserve_string_value=(
                    preserve_string_value or normalized_key in _SOURCE_BOUND_STRING_KEYS
                ),
            )
        return {
            key: normalized[key]
            for key in sorted(normalized, key=lambda item: item.encode("utf-8"))
        }
    _fail("B01_CANONICAL_VALUE_INVALID", type(value).__name__)


def canonical_bytes(value: Any) -> bytes:
    normalized = _normalize(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _new_extraction_admission_channel() -> tuple[
    Callable[[dict[str, Any]], object],
    Callable[[object], dict[str, Any]],
]:
    """Create one service-local seal/open channel without an importable token."""

    class _ExtractionAdmission:
        __slots__ = ()

    sealed: dict[object, tuple[bytes, str]] = {}

    def seal(payload: dict[str, Any]) -> object:
        payload_bytes = canonical_bytes(payload)
        capability = _ExtractionAdmission()
        sealed[capability] = (
            payload_bytes,
            hashlib.sha256(payload_bytes).hexdigest(),
        )
        return capability

    def open_admission(capability: object) -> dict[str, Any]:
        if type(capability) is not _ExtractionAdmission or capability not in sealed:
            _fail("B01_EXTRACTION_ADMISSION_REQUIRED")
        payload_bytes, expected_hash = sealed[capability]
        if hashlib.sha256(payload_bytes).hexdigest() != expected_hash:
            _fail("B01_EXTRACTION_ADMISSION_DRIFT")
        reopened = json.loads(payload_bytes)
        if canonical_bytes(reopened) != payload_bytes:
            _fail("B01_EXTRACTION_ADMISSION_DRIFT")
        return reopened

    return seal, open_admission


def _exact_keys(value: dict[str, Any], expected: set[str], code: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        _fail(code, f"missing={missing}; extra={extra}")


def _is_non_bool_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _make_record(
    *,
    record_type: str,
    record_id: str,
    record_version: int,
    payload: dict[str, Any],
    created_at: str,
    source_module: str = SOURCE_MODULE,
    access: str = FIXTURE_ACCESS,
    retention_class: str = IMMUTABLE_RETENTION,
    writer_token: object | None = None,
    contract_version: str = CONTRACT_VERSION,
) -> dict[str, Any]:
    expected_token = _B_OUTPUT_WRITER_TOKENS.get(record_type)
    if expected_token is not None and writer_token is not expected_token:
        _fail("B01_SCOPE_ESCAPE", f"{record_type} must use its unique writer")
    record = {
        "contract": IMMUTABLE_CONTRACT,
        "contract_version": contract_version,
        "record_type": record_type,
        "record_id": record_id,
        "record_version": record_version,
        "record_contract_version": contract_version,
        "record_hash": "",
        "source_module": source_module,
        "access": access,
        "retention_class": retention_class,
        "created_at": created_at,
        "payload": _normalize(deepcopy(payload)),
    }
    preimage = {key: value for key, value in record.items() if key != "record_hash"}
    record["record_hash"] = sha256_value(preimage)
    return record


def make_fixture_input_record(**kwargs: Any) -> dict[str, Any]:
    """Create read-only synthetic upstream evidence, never a B-01 output."""
    if kwargs.get("record_type") in _B_OUTPUT_WRITER_TOKENS:
        _fail("B01_SCOPE_ESCAPE", "B-01 output requested through fixture input helper")
    return _make_record(**kwargs)


def validate_record(record: dict[str, Any]) -> None:
    _exact_keys(record, ENVELOPE_KEYS, "B01_IMMUTABLE_ENVELOPE_INVALID")
    if record["contract"] != IMMUTABLE_CONTRACT:
        _fail("B01_IMMUTABLE_ENVELOPE_INVALID", "contract")
    if (
        record["contract_version"] not in {CONTRACT_VERSION, LEGACY_CONTRACT_VERSION}
        or record["record_contract_version"] != record["contract_version"]
    ):
        _fail("B01_IMMUTABLE_ENVELOPE_INVALID", "contract version")
    if not _is_non_bool_int(record["record_version"]) or record["record_version"] < 1:
        _fail("B01_IMMUTABLE_ENVELOPE_INVALID", "record version")
    if not all(
        isinstance(record[key], str) and record[key]
        for key in (
            "record_type",
            "record_id",
            "source_module",
            "access",
            "retention_class",
            "created_at",
        )
    ):
        _fail("B01_IMMUTABLE_ENVELOPE_INVALID", "string field")
    if not isinstance(record["payload"], dict) or not _is_sha256(record["record_hash"]):
        _fail("B01_IMMUTABLE_ENVELOPE_INVALID", "payload or hash")
    preimage = {key: value for key, value in record.items() if key != "record_hash"}
    if record["record_hash"] != sha256_value(preimage):
        _fail("B01_RECORD_HASH_MISMATCH", record.get("record_id", ""))


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
    code: str = "B01_RECORD_REF_INVALID",
    records: list[dict[str, Any]] | None = None,
    expected_type: str | None = None,
    expected_access: str | None = None,
    expected_source_module: str | None = None,
    expected_contract_version: str | None = None,
) -> None:
    _exact_keys(ref, RECORD_REF_KEYS, code)
    if ref["contract"] != RECORD_REF_CONTRACT:
        _fail(code, "contract")
    if (
        ref["contract_version"] not in {CONTRACT_VERSION, LEGACY_CONTRACT_VERSION}
        or ref["record_contract_version"] != ref["contract_version"]
    ):
        _fail(code, "contract version")
    if (
        expected_contract_version is not None
        and ref["contract_version"] != expected_contract_version
    ):
        _fail(code, "unexpected contract version")
    if not _is_non_bool_int(ref["record_version"]) or ref["record_version"] < 1:
        _fail(code, "record version")
    if not _is_sha256(ref["record_hash"]):
        _fail(code, "record hash")
    if expected_type is not None and ref["record_type"] != expected_type:
        _fail(code, "record type")
    if expected_access is not None and ref["access"] != expected_access:
        _fail(code, "access")
    if (
        expected_source_module is not None
        and ref["source_module"] != expected_source_module
    ):
        _fail(code, "source module")
    if records is not None:
        matches = [record for record in records if record_ref(record) == ref]
        if len(matches) != 1:
            _fail(code, "reference does not resolve uniquely")


def validate_admission(
    admission: dict[str, Any], *, reference_records: list[dict[str, Any]]
) -> None:
    if not admission:
        _fail("B01_A_ADMISSION_REQUIRED")
    try:
        validate_record(admission)
    except B01ContractError as error:
        _fail("B01_A_ADMISSION_REQUIRED", error.code)
    if admission["record_type"] != "M3_A_INTERFACE_ADMISSION_RECEIPT":
        _fail("B01_A_ADMISSION_REQUIRED", "record type")
    if admission["contract_version"] != LEGACY_CONTRACT_VERSION:
        _fail("B01_A_ADMISSION_REQUIRED", "legacy admission contract version")
    if (
        admission["source_module"] != "M3_B_ADMISSION"
        or admission["access"] != "RUN_INTERNAL_READ_ONLY"
    ):
        _fail("B01_A_ADMISSION_REQUIRED", "record policy")
    payload = admission["payload"]
    _exact_keys(payload, ADMISSION_PAYLOAD_KEYS, "B01_A_ADMISSION_REQUIRED")
    if (
        payload["repository"] != "cczz412/novel-architecture"
        or payload["issue_number"] != 176
        or payload["pr_number"] != 186
    ):
        _fail("B01_A_ADMISSION_REQUIRED", "repository, issue, or PR")
    if (
        payload["admission_result"] != "PASS"
        or payload["b_code_start_authorized"] is not True
        or payload["admission_mode"] != "MERGED_CURRENT_MAIN_EXACT_HEAD"
    ):
        _fail("B01_A_ADMISSION_REQUIRED", "admission result")
    if payload["reviewed_pr_head_sha"] != payload["pr_head_sha_at_merge"]:
        _fail("B01_A_ADMISSION_HEAD_MISMATCH")
    if payload["reviewed_pr_head_sha"] != EXPECTED_REVIEWED_HEAD:
        _fail("B01_A_ADMISSION_HEAD_MISMATCH", "unexpected reviewed head")
    if payload["reviewed_head_equals_merge_head"] is not True:
        _fail("B01_A_ADMISSION_HEAD_MISMATCH", "equality receipt")
    if payload["merge_commit_sha"] != EXPECTED_A_MERGE_COMMIT or not re.fullmatch(
        r"[0-9a-f]{40}", payload["current_main_sha"]
    ):
        _fail("B01_A_ADMISSION_READBACK_INVALID")
    if (
        payload["merge_commit_reachable_from_current_main"] is not True
        or payload["current_main_readback_passed"] is not True
    ):
        _fail("B01_A_ADMISSION_READBACK_INVALID")
    validate_record_ref(
        payload["review_receipt_ref"],
        code="B01_A_ADMISSION_REQUIRED",
        records=reference_records,
        expected_type="A_EXACT_HEAD_REVIEW_RECEIPT",
        expected_contract_version=LEGACY_CONTRACT_VERSION,
    )
    reviews = [
        record
        for record in reference_records
        if record_ref(record) == payload["review_receipt_ref"]
    ]
    if (
        len(reviews) != 1
        or reviews[0]["payload"].get("review_result") != "PASS"
        or reviews[0]["payload"].get("head_sha") != EXPECTED_REVIEWED_HEAD
        or reviews[0]["payload"].get("pr_number") != 186
    ):
        _fail("B01_A_ADMISSION_REQUIRED", "review receipt")
    validate_record_ref(
        payload["a_interface_manifest_ref"],
        code="B01_A_INTERFACE_DRIFT",
        records=reference_records,
        expected_type="A_INTERFACE_MANIFEST",
        expected_contract_version=LEGACY_CONTRACT_VERSION,
    )
    manifests = [
        record
        for record in reference_records
        if record_ref(record) == payload["a_interface_manifest_ref"]
    ]
    if (
        len(manifests) != 1
        or sha256_value(manifests[0]["payload"])
        != payload["a_interface_manifest_sha256"]
    ):
        _fail("B01_A_INTERFACE_DRIFT")
    if (
        manifests[0]["payload"].get("repository") != "cczz412/novel-architecture"
        or manifests[0]["payload"].get("issue_number") != 176
        or manifests[0]["payload"].get("manifest_mode")
        != "MERGED_CURRENT_MAIN_READBACK"
    ):
        _fail("B01_A_INTERFACE_DRIFT", "manifest payload")
    if payload["a_interface_manifest_sha256"] != EXPECTED_A_INTERFACE_PAYLOAD_HASH:
        _fail("B01_A_INTERFACE_DRIFT", "unexpected manifest hash")
    if (
        admission["record_id"] != EXPECTED_A_ADMISSION_ID
        or admission["record_version"] != 1
        or admission["record_hash"] != EXPECTED_A_ADMISSION_HASH
        or admission["created_at"] != EXPECTED_A_ADMISSION_CREATED_AT
    ):
        _fail("B01_A_ADMISSION_REQUIRED", "admission original")


def validate_chapter_revision_ref(ref: dict[str, Any]) -> None:
    _exact_keys(ref, CHAPTER_REVISION_KEYS, "B01_SEGMENT_SOURCE_MISMATCH")
    if not isinstance(ref["chapter_id"], str) or not ref["chapter_id"]:
        _fail("B01_SEGMENT_SOURCE_MISMATCH", "chapter id")
    if not _is_non_bool_int(ref["revision_no"]) or ref["revision_no"] < 1:
        _fail("B01_SEGMENT_SOURCE_MISMATCH", "revision number")
    if not _is_sha256(ref["revision_text_sha256"]):
        _fail("B01_SEGMENT_SOURCE_MISMATCH", "revision text hash")


def sentence_count(text: str) -> int:
    """Reuse the approved v2.1 Chinese sentence-boundary rule."""

    return sum(
        bool(part.strip(SENTENCE_WRAPPERS)) for part in SENTENCE_END_RE.split(text)
    )


def _resolved_record(
    ref: dict[str, Any],
    *,
    records: list[dict[str, Any]],
    expected_type: str,
    code: str,
    expected_contract_version: str = CONTRACT_VERSION,
) -> dict[str, Any]:
    validate_record_ref(
        ref,
        code=code,
        records=records,
        expected_type=expected_type,
        expected_access=FIXTURE_ACCESS,
        expected_source_module="M1_READ_ONLY_ADAPTER",
        expected_contract_version=expected_contract_version,
    )
    matches = [record for record in records if record_ref(record) == ref]
    if len(matches) != 1:
        _fail(code, "reference does not resolve uniquely")
    return matches[0]


def validate_source_generation_record(record: dict[str, Any]) -> None:
    validate_record(record)
    if (
        record["contract_version"] != CONTRACT_VERSION
        or record["record_type"] != SOURCE_GENERATION_RECORD_TYPE
        or record["source_module"] != "M1_READ_ONLY_ADAPTER"
        or record["access"] != FIXTURE_ACCESS
    ):
        _fail("B01_SOURCE_GENERATION_INVALID", "record identity")
    payload = record["payload"]
    _exact_keys(
        payload,
        {
            "workspace_generation_schema",
            "chapter_admission_identity",
            "workspace_generation_id",
            "manifest_sha256",
            "chapter_revision_ref",
        },
        "B01_SOURCE_GENERATION_INVALID",
    )
    if (
        payload["workspace_generation_schema"] != "author-workspace-generation-v1"
        or payload["chapter_admission_identity"]
        != "AUTHOR_WORKSPACE_INITIAL_CHAPTER_ADMISSION_R01"
        or not isinstance(payload["workspace_generation_id"], str)
        or re.fullmatch(r"g_[0-9a-f]{64}", payload["workspace_generation_id"]) is None
        or not _is_sha256(payload["manifest_sha256"])
    ):
        _fail("B01_SOURCE_GENERATION_INVALID", "upstream contract")
    validate_chapter_revision_ref(payload["chapter_revision_ref"])


def validate_writing_material_record(
    record: dict[str, Any], *, reference_records: list[dict[str, Any]]
) -> None:
    validate_record(record)
    if (
        record["contract_version"] != CONTRACT_VERSION
        or record["record_type"] != WRITING_MATERIAL_RECORD_TYPE
        or record["source_module"] != "M1_READ_ONLY_ADAPTER"
        or record["access"] != FIXTURE_ACCESS
    ):
        _fail("B01_WRITING_MATERIAL_INVALID", "record identity")
    payload = record["payload"]
    _exact_keys(
        payload,
        {
            "material_kind",
            "accepted_source_generation_ref",
            "material_contract",
            "material_version",
            "material_sha256",
        },
        "B01_WRITING_MATERIAL_INVALID",
    )
    if (
        payload["material_kind"] not in ALLOWED_MATERIAL_KINDS
        or not isinstance(payload["material_contract"], str)
        or not payload["material_contract"]
        or not isinstance(payload["material_version"], str)
        or not payload["material_version"]
        or not _is_sha256(payload["material_sha256"])
    ):
        _fail("B01_WRITING_MATERIAL_INVALID", "payload")
    source_generation = _resolved_record(
        payload["accepted_source_generation_ref"],
        records=reference_records,
        expected_type=SOURCE_GENERATION_RECORD_TYPE,
        code="B01_SOURCE_GENERATION_INVALID",
    )
    validate_source_generation_record(source_generation)


def build_extraction_input_binding(
    *,
    accepted_source_generation_ref: dict[str, Any],
    chapter_revision_ref: dict[str, Any],
    writing_material_refs: list[dict[str, Any]],
    reference_records: list[dict[str, Any]],
) -> dict[str, Any]:
    source_generation = _resolved_record(
        accepted_source_generation_ref,
        records=reference_records,
        expected_type=SOURCE_GENERATION_RECORD_TYPE,
        code="B01_SOURCE_GENERATION_INVALID",
    )
    validate_source_generation_record(source_generation)
    validate_chapter_revision_ref(chapter_revision_ref)
    if source_generation["payload"]["chapter_revision_ref"] != chapter_revision_ref:
        _fail("B01_SOURCE_GENERATION_MISMATCH", "chapter revision")
    if not isinstance(writing_material_refs, list) or not writing_material_refs:
        _fail("B01_WRITING_MATERIAL_INVALID", "materials required")
    normalized: list[dict[str, Any]] = []
    seen_refs: set[bytes] = set()
    kinds: set[str] = set()
    for item in writing_material_refs:
        if not isinstance(item, dict):
            _fail("B01_WRITING_MATERIAL_INVALID", "material binding")
        _exact_keys(
            item,
            {"material_kind", "material_ref"},
            "B01_WRITING_MATERIAL_INVALID",
        )
        material = _resolved_record(
            item["material_ref"],
            records=reference_records,
            expected_type=WRITING_MATERIAL_RECORD_TYPE,
            code="B01_WRITING_MATERIAL_INVALID",
        )
        validate_writing_material_record(material, reference_records=reference_records)
        if (
            item["material_kind"] != material["payload"]["material_kind"]
            or material["payload"]["accepted_source_generation_ref"]
            != accepted_source_generation_ref
        ):
            _fail("B01_SOURCE_GENERATION_MISMATCH", "material generation")
        ref_bytes = canonical_bytes(item["material_ref"])
        if ref_bytes in seen_refs:
            _fail("B01_WRITING_MATERIAL_INVALID", "duplicate material ref")
        seen_refs.add(ref_bytes)
        kinds.add(item["material_kind"])
        normalized.append(deepcopy(item))
    if not REQUIRED_MATERIAL_KINDS.issubset(kinds):
        _fail("B01_WRITING_MATERIAL_INVALID", "required material kind missing")
    normalized.sort(
        key=lambda item: (
            item["material_kind"].encode("utf-8"),
            canonical_bytes(item["material_ref"]),
        )
    )
    if writing_material_refs != normalized:
        _fail("B01_WRITING_MATERIAL_INVALID", "materials not canonically sorted")
    binding_without_hash = {
        "accepted_source_generation_ref": deepcopy(accepted_source_generation_ref),
        "chapter_revision_ref": deepcopy(chapter_revision_ref),
        "writing_material_refs": normalized,
    }
    return {
        **binding_without_hash,
        "input_binding_hash": sha256_value(binding_without_hash),
    }


def validate_extraction_input_binding(
    binding: dict[str, Any], *, reference_records: list[dict[str, Any]]
) -> None:
    _exact_keys(
        binding,
        {
            "accepted_source_generation_ref",
            "chapter_revision_ref",
            "writing_material_refs",
            "input_binding_hash",
        },
        "B01_INPUT_BINDING_INVALID",
    )
    rebuilt = build_extraction_input_binding(
        accepted_source_generation_ref=binding["accepted_source_generation_ref"],
        chapter_revision_ref=binding["chapter_revision_ref"],
        writing_material_refs=binding["writing_material_refs"],
        reference_records=reference_records,
    )
    if rebuilt != binding:
        _fail("B01_INPUT_BINDING_INVALID", "binding hash")


def stable_segment_index_id(
    project_scope_id: str,
    chapter_id: str,
    revision_no: int,
    revision_text_sha256: str,
    source_generation_hash: str,
) -> str:
    return (
        f"segidx:{project_scope_id}:{chapter_id}:r{revision_no}:"
        f"{revision_text_sha256[:12]}:{source_generation_hash[:12]}"
    )


def _segment_id(ref: dict[str, Any]) -> tuple[str, int]:
    return str(ref["chapter_id"]), int(ref["revision_no"])


def _build_segment_index_snapshot(
    *,
    project_scope_id: str,
    author_workspace_logical_key: str,
    chapter_revision_ref: dict[str, Any],
    accepted_source_generation_ref: dict[str, Any],
    reference_records: list[dict[str, Any]],
    source_module_identity: str,
    segment_inputs: list[dict[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    validate_chapter_revision_ref(chapter_revision_ref)
    source_generation = _resolved_record(
        accepted_source_generation_ref,
        records=reference_records,
        expected_type=SOURCE_GENERATION_RECORD_TYPE,
        code="B01_SOURCE_GENERATION_INVALID",
    )
    validate_source_generation_record(source_generation)
    if source_generation["payload"]["chapter_revision_ref"] != chapter_revision_ref:
        _fail("B01_SOURCE_GENERATION_MISMATCH", "segment chapter revision")
    if not segment_inputs:
        _fail("B01_SEGMENT_INDEX_INVALID", "segments must not be empty")
    chapter_id, revision_no = _segment_id(chapter_revision_ref)
    segments: list[dict[str, Any]] = []
    previous_end = 0
    for expected_seg, source in enumerate(segment_inputs, start=1):
        if source.get("seg") != expected_seg:
            _fail("B01_SEGMENT_INDEX_INVALID", "segment numbering")
        if set(source) not in (
            {"seg", "start_byte", "end_byte", "responsibility_text"},
            {
                "seg",
                "start_byte",
                "end_byte",
                "responsibility_text",
                "responsibility_text_sha256",
            },
        ):
            _fail("B01_SEGMENT_INDEX_INVALID", "segment input fields")
        start = source.get("start_byte")
        end = source.get("end_byte")
        text = source.get("responsibility_text")
        if (
            not _is_non_bool_int(start)
            or not _is_non_bool_int(end)
            or not isinstance(text, str)
            or start < 0
            or start >= end
            or start != previous_end
            or end - start != len(text.encode("utf-8"))
        ):
            _fail("B01_SEGMENT_INDEX_INVALID", "segment range")
        expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        supplied_hash = source.get("responsibility_text_sha256", expected_hash)
        if supplied_hash != expected_hash:
            _fail("B01_SEGMENT_TEXT_HASH_MISMATCH")
        segments.append(
            {
                "seg": expected_seg,
                "start_byte": start,
                "end_byte": end,
                "responsibility_text_sha256": expected_hash,
            }
        )
        previous_end = end
    reconstructed_revision = "".join(
        source["responsibility_text"] for source in segment_inputs
    )
    if (
        hashlib.sha256(reconstructed_revision.encode("utf-8")).hexdigest()
        != chapter_revision_ref["revision_text_sha256"]
    ):
        _fail("B01_SEGMENT_SOURCE_MISMATCH", "revision text hash")
    stable_id = stable_segment_index_id(
        project_scope_id,
        chapter_id,
        revision_no,
        chapter_revision_ref["revision_text_sha256"],
        accepted_source_generation_ref["record_hash"],
    )
    chapter_length_bytes = len(reconstructed_revision.encode("utf-8"))
    payload = {
        "project_scope_id": project_scope_id,
        "author_workspace_logical_key": author_workspace_logical_key,
        "source_module_identity": source_module_identity,
        "accepted_source_generation_ref": deepcopy(accepted_source_generation_ref),
        "chapter_revision_ref": deepcopy(chapter_revision_ref),
        "coordinate_unit": COORDINATE_UNIT,
        "chapter_length_bytes": chapter_length_bytes,
        "coverage_denominator_bytes": chapter_length_bytes,
        "stable_segment_index_id": stable_id,
        "segments": segments,
    }
    return _make_record(
        record_type="M3_SEGMENT_INDEX_SNAPSHOT",
        record_id=stable_id,
        record_version=1,
        payload=payload,
        created_at=created_at,
        writer_token=_SEGMENT_WRITER_TOKEN,
    )


def validate_segment_index_snapshot(record: dict[str, Any]) -> None:
    validate_record(record)
    if record["record_type"] != "M3_SEGMENT_INDEX_SNAPSHOT":
        _fail("B01_SEGMENT_INDEX_INVALID", "record type")
    if record["source_module"] != SOURCE_MODULE or record["access"] != FIXTURE_ACCESS:
        _fail("B01_SEGMENT_INDEX_INVALID", "record policy")
    payload = record["payload"]
    expected = {
        "project_scope_id",
        "author_workspace_logical_key",
        "source_module_identity",
        "accepted_source_generation_ref",
        "chapter_revision_ref",
        "coordinate_unit",
        "chapter_length_bytes",
        "coverage_denominator_bytes",
        "stable_segment_index_id",
        "segments",
    }
    _exact_keys(payload, expected, "B01_SEGMENT_INDEX_INVALID")
    validate_chapter_revision_ref(payload["chapter_revision_ref"])
    validate_record_ref(
        payload["accepted_source_generation_ref"],
        code="B01_SOURCE_GENERATION_INVALID",
        expected_type=SOURCE_GENERATION_RECORD_TYPE,
        expected_access=FIXTURE_ACCESS,
        expected_source_module="M1_READ_ONLY_ADAPTER",
        expected_contract_version=CONTRACT_VERSION,
    )
    if payload["source_module_identity"] not in {
        "M2_READ_ONLY_ADAPTER",
        "C2_READ_ONLY_ADAPTER",
        "B01_SYNTHETIC_FIXTURE",
    }:
        _fail("B01_SEGMENT_SOURCE_MISMATCH")
    chapter_id, revision_no = _segment_id(payload["chapter_revision_ref"])
    expected_stable_id = stable_segment_index_id(
        payload["project_scope_id"],
        chapter_id,
        revision_no,
        payload["chapter_revision_ref"]["revision_text_sha256"],
        payload["accepted_source_generation_ref"]["record_hash"],
    )
    if (
        payload["stable_segment_index_id"] != record["record_id"]
        or record["record_id"] != expected_stable_id
    ):
        _fail("B01_SEGMENT_INDEX_INVALID", "stable id")
    if not payload["segments"]:
        _fail("B01_SEGMENT_INDEX_INVALID", "empty")
    if (
        payload["coordinate_unit"] != COORDINATE_UNIT
        or not _is_non_bool_int(payload["chapter_length_bytes"])
        or payload["chapter_length_bytes"] < 1
        or payload["coverage_denominator_bytes"] != payload["chapter_length_bytes"]
    ):
        _fail("B01_SEGMENT_INDEX_INVALID", "coverage denominator")
    previous_end = 0
    for expected_seg, segment in enumerate(payload["segments"], start=1):
        _exact_keys(
            segment,
            {
                "seg",
                "start_byte",
                "end_byte",
                "responsibility_text_sha256",
            },
            "B01_SEGMENT_INDEX_INVALID",
        )
        if segment["seg"] != expected_seg:
            _fail("B01_SEGMENT_INDEX_INVALID", "numbering")
        if (
            not _is_non_bool_int(segment["start_byte"])
            or not _is_non_bool_int(segment["end_byte"])
            or segment["start_byte"] != previous_end
            or segment["start_byte"] >= segment["end_byte"]
        ):
            _fail("B01_SEGMENT_INDEX_INVALID", "range")
        if not _is_sha256(segment["responsibility_text_sha256"]):
            _fail("B01_SEGMENT_TEXT_HASH_MISMATCH")
        previous_end = segment["end_byte"]
    if previous_end != payload["chapter_length_bytes"]:
        _fail("B01_SEGMENT_INDEX_INVALID", "coverage incomplete")


def _validate_attempt_refs(
    refs: list[dict[str, Any]],
    *,
    reference_records: list[dict[str, Any]] | None,
) -> None:
    if not refs:
        _fail("B01_ATTEMPT_REF_INVALID", "root baseline requires evidence")
    for ref in refs:
        validate_record_ref(
            ref,
            code="B01_ATTEMPT_REF_INVALID",
            records=reference_records,
            expected_type="A_RAW_ATTEMPT_RECEIPT",
            expected_access=FIXTURE_ACCESS,
            expected_source_module="A_STAGE_FIXTURE",
            expected_contract_version=LEGACY_CONTRACT_VERSION,
        )


def _stored_item(
    extraction_input_binding: dict[str, Any],
    chapter_revision_ref: dict[str, Any],
    seg: int,
    ordinal: int,
    raw: dict[str, Any],
    segment_index_record: dict[str, Any],
    segment_inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    allowed = {"fact", "status", "evidence"}
    if "speaker" in raw:
        allowed.add("speaker")
    if set(raw) != allowed:
        _fail("B01_CANDIDATE_VERSION_INVALID", "raw item fields")
    if not isinstance(raw.get("fact"), str) or not raw["fact"]:
        _fail("B01_CANDIDATE_VERSION_INVALID", "fact")
    if raw.get("status") not in ALLOWED_STATUSES:
        _fail("B01_CANDIDATE_VERSION_INVALID", "status")
    evidence = raw.get("evidence")
    if not isinstance(evidence, str) or not evidence:
        _fail("B01_EVIDENCE_INVALID", "evidence required")
    if "speaker" in raw and (not isinstance(raw["speaker"], str) or not raw["speaker"]):
        _fail("B01_CANDIDATE_VERSION_INVALID", "speaker")
    count = sentence_count(evidence)
    if count not in {1, 2}:
        _fail("B01_EVIDENCE_SENTENCE_LIMIT", str(count))
    evidence_bytes = evidence.encode("utf-8")
    locations = _expected_evidence_locations(
        evidence,
        seg=seg,
        segment_index_record=segment_index_record,
        segment_inputs=segment_inputs,
    )
    if not locations:
        _fail("B01_EVIDENCE_NOT_IN_EXACT_CHAPTER")
    binding_without_hash = {
        "chapter_revision_ref": deepcopy(chapter_revision_ref),
        "evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
        "sentence_count": count,
        "match_locations": locations,
    }
    evidence_binding = {
        **binding_without_hash,
        "binding_hash": sha256_value(binding_without_hash),
    }
    seed = {
        "chapter_revision_ref": chapter_revision_ref,
        "input_binding_hash": extraction_input_binding["input_binding_hash"],
        "seg": seg,
        "ordinal": ordinal,
        "fact": raw["fact"],
        "status": raw["status"],
        "evidence": evidence,
        "evidence_binding_hash": evidence_binding["binding_hash"],
    }
    if "speaker" in raw:
        seed["speaker_if_present"] = raw["speaker"]
    lineage_id = f"lin_{sha256_value(seed)}"
    item = {
        "lineage_id": lineage_id,
        "fact": raw["fact"],
        "status": raw["status"],
        "evidence": evidence,
    }
    item_preimage: dict[str, Any] = deepcopy(item)
    if "speaker" in raw:
        item["speaker"] = raw["speaker"]
        item_preimage["speaker"] = raw["speaker"]
    item["evidence_binding"] = evidence_binding
    item_preimage["evidence_binding"] = evidence_binding
    item["item_hash"] = sha256_value(item_preimage)
    return item


def _exact_segment_source_bytes(
    segment_index_record: dict[str, Any],
    segment_inputs: list[dict[str, Any]],
) -> bytes:
    """Rebuild the exact chapter bytes and bind them to the persisted index."""
    validate_segment_index_snapshot(segment_index_record)
    indexed_segments = segment_index_record["payload"]["segments"]
    if len(segment_inputs) != len(indexed_segments):
        _fail("B01_SEGMENT_SOURCE_MISMATCH", "segment count")
    chunks: list[bytes] = []
    for expected_seg, (source, indexed) in enumerate(
        zip(segment_inputs, indexed_segments), start=1
    ):
        if set(source) not in (
            {"seg", "start_byte", "end_byte", "responsibility_text"},
            {
                "seg",
                "start_byte",
                "end_byte",
                "responsibility_text",
                "responsibility_text_sha256",
            },
        ):
            _fail("B01_SEGMENT_INDEX_INVALID", "segment input fields")
        text = source.get("responsibility_text")
        if not isinstance(text, str):
            _fail("B01_SEGMENT_INDEX_INVALID", "responsibility text")
        text_bytes = text.encode("utf-8")
        expected_hash = hashlib.sha256(text_bytes).hexdigest()
        expected_indexed = {
            "seg": expected_seg,
            "start_byte": source.get("start_byte"),
            "end_byte": source.get("end_byte"),
            "responsibility_text_sha256": expected_hash,
        }
        if (
            source.get("seg") != expected_seg
            or not _is_non_bool_int(source.get("start_byte"))
            or not _is_non_bool_int(source.get("end_byte"))
            or source["end_byte"] - source["start_byte"] != len(text_bytes)
            or source.get("responsibility_text_sha256", expected_hash) != expected_hash
            or indexed != expected_indexed
        ):
            _fail("B01_SEGMENT_SOURCE_MISMATCH", "segment bytes")
        chunks.append(text_bytes)
    full_chapter = b"".join(chunks)
    payload = segment_index_record["payload"]
    if (
        len(full_chapter) != payload["chapter_length_bytes"]
        or hashlib.sha256(full_chapter).hexdigest()
        != payload["chapter_revision_ref"]["revision_text_sha256"]
    ):
        _fail("B01_SEGMENT_SOURCE_MISMATCH", "chapter bytes")
    return full_chapter


def _expected_evidence_locations(
    evidence: str,
    *,
    seg: int,
    segment_index_record: dict[str, Any],
    segment_inputs: list[dict[str, Any]],
) -> list[dict[str, int]]:
    full_chapter = _exact_segment_source_bytes(
        segment_index_record,
        segment_inputs,
    )
    segments = segment_index_record["payload"]["segments"]
    if not _is_non_bool_int(seg) or seg < 1 or seg > len(segments):
        _fail("B01_SEGMENT_INDEX_INVALID", "selected segment")
    selected_segment = segments[seg - 1]
    evidence_bytes = evidence.encode("utf-8")
    locations: list[dict[str, int]] = []
    offset = 0
    while offset <= len(full_chapter) - len(evidence_bytes):
        start = full_chapter.find(evidence_bytes, offset)
        if start < 0:
            break
        end = start + len(evidence_bytes)
        if (
            selected_segment["start_byte"] <= start
            and end <= selected_segment["end_byte"]
        ):
            locations.append({"seg": seg, "start_byte": start, "end_byte": end})
        offset = start + 1
    return locations


def _build_root_candidate_version(
    *,
    chapter_revision_ref: dict[str, Any],
    seg: int,
    author_workspace_logical_key: str,
    extraction_input_binding: dict[str, Any],
    segment_index_record: dict[str, Any],
    origin_attempt_refs: list[dict[str, Any]],
    reference_records: list[dict[str, Any]],
    segment_inputs: list[dict[str, Any]],
    raw_items: list[dict[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    validate_chapter_revision_ref(chapter_revision_ref)
    if not _is_non_bool_int(seg) or seg < 1:
        _fail("B01_CANDIDATE_VERSION_INVALID", "segment")
    _validate_attempt_refs(origin_attempt_refs, reference_records=reference_records)
    validate_extraction_input_binding(
        extraction_input_binding, reference_records=reference_records
    )
    validate_segment_index_snapshot(segment_index_record)
    if (
        extraction_input_binding["chapter_revision_ref"] != chapter_revision_ref
        or segment_index_record["payload"]["chapter_revision_ref"]
        != chapter_revision_ref
        or segment_index_record["payload"]["accepted_source_generation_ref"]
        != extraction_input_binding["accepted_source_generation_ref"]
    ):
        _fail("B01_INPUT_BINDING_INVALID", "segment binding")
    items = [
        _stored_item(
            extraction_input_binding,
            chapter_revision_ref,
            seg,
            ordinal,
            raw,
            segment_index_record,
            segment_inputs,
        )
        for ordinal, raw in enumerate(raw_items)
    ]
    lineage_ids = [item["lineage_id"] for item in items]
    if len(lineage_ids) != len(set(lineage_ids)):
        _fail("B01_DUPLICATE_LINEAGE_ID")
    lineage_index = [
        {
            "lineage_id": item["lineage_id"],
            "json_pointer": f"/items/{index}",
            "item_hash": item["item_hash"],
        }
        for index, item in enumerate(items)
    ]
    payload_without_hash = {
        "candidate_schema_id": CANDIDATE_SCHEMA_ID,
        "extraction_input_binding": deepcopy(extraction_input_binding),
        "segment_index_ref": record_ref(segment_index_record),
        "chapter_revision_ref": deepcopy(chapter_revision_ref),
        "seg": seg,
        "parent_candidate_version_ref": None,
        "origin_attempt_refs": deepcopy(origin_attempt_refs),
        "origin_commit_intent_ref": None,
        "items": items,
        "lineage_index": lineage_index,
    }
    payload = {
        **payload_without_hash,
        "version_payload_hash": sha256_value(payload_without_hash),
    }
    record_id = (
        f"cv:{sha256_value(author_workspace_logical_key)[:12]}:"
        f"{payload['version_payload_hash'][:32]}"
    )
    return _make_record(
        record_type="M3_CANDIDATE_VERSION",
        record_id=record_id,
        record_version=1,
        payload=payload,
        created_at=created_at,
        writer_token=_CANDIDATE_WRITER_TOKEN,
    )


def validate_candidate_version(
    record: dict[str, Any],
    *,
    allow_child: bool = False,
    reference_records: list[dict[str, Any]] | None = None,
) -> None:
    validate_record(record)
    if (
        record["contract_version"] != CONTRACT_VERSION
        or record["record_type"] != "M3_CANDIDATE_VERSION"
    ):
        _fail("B01_CANDIDATE_VERSION_INVALID", "record type")
    if record["source_module"] != SOURCE_MODULE or record["access"] != FIXTURE_ACCESS:
        _fail("B01_CANDIDATE_VERSION_INVALID", "record policy")
    payload = record["payload"]
    expected = {
        "candidate_schema_id",
        "extraction_input_binding",
        "segment_index_ref",
        "chapter_revision_ref",
        "seg",
        "parent_candidate_version_ref",
        "origin_attempt_refs",
        "origin_commit_intent_ref",
        "items",
        "lineage_index",
        "version_payload_hash",
    }
    _exact_keys(payload, expected, "B01_CANDIDATE_VERSION_INVALID")
    if payload["candidate_schema_id"] != CANDIDATE_SCHEMA_ID:
        _fail("B01_CANDIDATE_SCHEMA_MISMATCH")
    validate_chapter_revision_ref(payload["chapter_revision_ref"])
    if reference_records is None:
        _fail("B01_REFERENCE_INTEGRITY_FAILED", "reference records required")
    validate_extraction_input_binding(
        payload["extraction_input_binding"], reference_records=reference_records
    )
    if (
        payload["extraction_input_binding"]["chapter_revision_ref"]
        != payload["chapter_revision_ref"]
    ):
        _fail("B01_INPUT_BINDING_INVALID", "candidate revision")
    validate_record_ref(
        payload["segment_index_ref"],
        code="B01_SEGMENT_INDEX_INVALID",
        records=reference_records,
        expected_type="M3_SEGMENT_INDEX_SNAPSHOT",
        expected_access=FIXTURE_ACCESS,
        expected_source_module=SOURCE_MODULE,
        expected_contract_version=CONTRACT_VERSION,
    )
    segment_records = [
        item
        for item in reference_records
        if record_ref(item) == payload["segment_index_ref"]
    ]
    if len(segment_records) != 1:
        _fail("B01_SEGMENT_INDEX_INVALID", "segment reference")
    segment_record = segment_records[0]
    validate_segment_index_snapshot(segment_record)
    if (
        segment_record["payload"]["chapter_revision_ref"]
        != payload["chapter_revision_ref"]
        or segment_record["payload"]["accepted_source_generation_ref"]
        != payload["extraction_input_binding"]["accepted_source_generation_ref"]
    ):
        _fail("B01_INPUT_BINDING_INVALID", "segment source generation")
    if (
        not _is_non_bool_int(payload["seg"])
        or payload["seg"] < 1
        or payload["seg"] > len(segment_record["payload"]["segments"])
    ):
        _fail("B01_CANDIDATE_VERSION_INVALID", "segment")
    is_child = payload["parent_candidate_version_ref"] is not None
    if is_child and not allow_child:
        _fail("B01_CHILD_CREATION_OUT_OF_SCOPE")
    if not is_child and record["record_version"] != 1:
        _fail("B01_CANDIDATE_VERSION_INVALID", "root record version")
    if is_child:
        if record["record_version"] < 2:
            _fail("B01_CANDIDATE_VERSION_INVALID", "child record version")
        validate_record_ref(
            payload["parent_candidate_version_ref"],
            code="B01_CANDIDATE_VERSION_INVALID",
            expected_type="M3_CANDIDATE_VERSION",
            expected_access=FIXTURE_ACCESS,
            expected_source_module=SOURCE_MODULE,
            expected_contract_version=CONTRACT_VERSION,
        )
    elif payload["origin_commit_intent_ref"] is not None:
        _fail("B01_CHILD_CREATION_OUT_OF_SCOPE")
    _validate_attempt_refs(
        payload["origin_attempt_refs"],
        reference_records=reference_records,
    )
    if not isinstance(payload["items"], list) or not isinstance(
        payload["lineage_index"], list
    ):
        _fail("B01_CANDIDATE_VERSION_INVALID", "items")
    seen: set[str] = set()
    if len(payload["items"]) != len(payload["lineage_index"]):
        _fail(
            "B01_EMPTY_BASELINE_INVALID"
            if not payload["items"]
            else "B01_LINEAGE_INDEX_INVALID"
        )
    for index, (item, locator) in enumerate(
        zip(payload["items"], payload["lineage_index"])
    ):
        allowed_item_keys = {
            "lineage_id",
            "fact",
            "status",
            "evidence",
            "evidence_binding",
            "item_hash",
        }
        if "speaker" in item:
            allowed_item_keys.add("speaker")
        _exact_keys(item, allowed_item_keys, "B01_CANDIDATE_VERSION_INVALID")
        if not isinstance(item["fact"], str) or not item["fact"]:
            _fail("B01_CANDIDATE_VERSION_INVALID", "fact")
        if item["status"] not in ALLOWED_STATUSES:
            _fail("B01_CANDIDATE_VERSION_INVALID", "status")
        if not isinstance(item["evidence"], str) or not item["evidence"]:
            _fail("B01_EVIDENCE_INVALID")
        if "speaker" in item and (
            not isinstance(item["speaker"], str) or not item["speaker"]
        ):
            _fail("B01_CANDIDATE_VERSION_INVALID", "speaker")
        if not isinstance(item["lineage_id"], str) or not item["lineage_id"].startswith(
            "lin_"
        ):
            _fail("B01_LINEAGE_INDEX_INVALID", "lineage id")
        if not _is_sha256(item["item_hash"]):
            _fail("B01_ITEM_HASH_MISMATCH", "item hash shape")
        if item["lineage_id"] in seen:
            _fail("B01_DUPLICATE_LINEAGE_ID")
        seen.add(item["lineage_id"])
        if not is_child:
            lineage_seed = {
                "chapter_revision_ref": payload["chapter_revision_ref"],
                "input_binding_hash": payload["extraction_input_binding"][
                    "input_binding_hash"
                ],
                "seg": payload["seg"],
                "ordinal": index,
                "fact": item["fact"],
                "status": item["status"],
                "evidence": item["evidence"],
                "evidence_binding_hash": item["evidence_binding"]["binding_hash"],
            }
            if "speaker" in item:
                lineage_seed["speaker_if_present"] = item["speaker"]
            if item["lineage_id"] != f"lin_{sha256_value(lineage_seed)}":
                _fail("B01_LINEAGE_INDEX_INVALID", "lineage seed")
        binding = item["evidence_binding"]
        _exact_keys(
            binding,
            {
                "chapter_revision_ref",
                "evidence_sha256",
                "sentence_count",
                "match_locations",
                "binding_hash",
            },
            "B01_EVIDENCE_BINDING_INVALID",
        )
        count = sentence_count(item["evidence"])
        if (
            binding["chapter_revision_ref"] != payload["chapter_revision_ref"]
            or binding["evidence_sha256"]
            != hashlib.sha256(item["evidence"].encode("utf-8")).hexdigest()
            or binding["sentence_count"] != count
            or count not in {1, 2}
            or not isinstance(binding["match_locations"], list)
            or not binding["match_locations"]
        ):
            _fail("B01_EVIDENCE_BINDING_INVALID", "binding payload")
        locations = binding["match_locations"]
        if locations != sorted(
            locations,
            key=lambda location: (
                location.get("seg"),
                location.get("start_byte"),
                location.get("end_byte"),
            ),
        ) or len({canonical_bytes(location) for location in locations}) != len(
            locations
        ):
            _fail("B01_EVIDENCE_BINDING_INVALID", "location order")
        selected_segment = segment_record["payload"]["segments"][payload["seg"] - 1]
        for location in locations:
            _exact_keys(
                location,
                {"seg", "start_byte", "end_byte"},
                "B01_EVIDENCE_BINDING_INVALID",
            )
            if (
                location["seg"] != payload["seg"]
                or not _is_non_bool_int(location["start_byte"])
                or not _is_non_bool_int(location["end_byte"])
                or location["start_byte"] < selected_segment["start_byte"]
                or location["end_byte"] > selected_segment["end_byte"]
                or location["start_byte"] >= location["end_byte"]
            ):
                _fail("B01_EVIDENCE_BINDING_INVALID", "location range")
        binding_preimage = {
            key: value for key, value in binding.items() if key != "binding_hash"
        }
        if binding["binding_hash"] != sha256_value(binding_preimage):
            _fail("B01_EVIDENCE_BINDING_INVALID", "binding hash")
        item_preimage = {
            key: value for key, value in item.items() if key != "item_hash"
        }
        if item["item_hash"] != sha256_value(item_preimage):
            _fail("B01_ITEM_HASH_MISMATCH")
        expected_locator = {
            "lineage_id": item["lineage_id"],
            "json_pointer": f"/items/{index}",
            "item_hash": item["item_hash"],
        }
        if locator != expected_locator:
            _fail("B01_LINEAGE_INDEX_INVALID")
    payload_preimage = {
        key: value for key, value in payload.items() if key != "version_payload_hash"
    }
    if payload["version_payload_hash"] != sha256_value(payload_preimage):
        _fail("B01_CANDIDATE_VERSION_INVALID", "version payload hash")


def pointer_logical_key(
    chapter_revision_ref: dict[str, Any], seg: int, input_binding_hash: str
) -> str:
    chapter_id, revision_no = _segment_id(chapter_revision_ref)
    return (
        f"fixture:m3_candidate.current/{CANDIDATE_SCHEMA_ID}/"
        f"{chapter_id}/r{revision_no}/seg{seg}/{input_binding_hash}"
    )


def build_live_pointer(
    *,
    project_scope_id: str,
    author_workspace_logical_key: str,
    chapter_revision_ref: dict[str, Any],
    seg: int,
    input_binding_hash: str,
    candidate_ref: dict[str, Any],
) -> dict[str, Any]:
    validate_chapter_revision_ref(chapter_revision_ref)
    validate_record_ref(
        candidate_ref,
        expected_type="M3_CANDIDATE_VERSION",
        expected_access=FIXTURE_ACCESS,
        expected_source_module=SOURCE_MODULE,
        expected_contract_version=CONTRACT_VERSION,
    )
    if not _is_sha256(input_binding_hash):
        _fail("B01_POINTER_SCOPE_MISMATCH", "input binding hash")
    if not _is_non_bool_int(seg) or seg < 1:
        _fail("B01_POINTER_SCOPE_MISMATCH", "segment")
    return {
        "project_scope_id": project_scope_id,
        "author_workspace_logical_key": author_workspace_logical_key,
        "logical_pointer_key": pointer_logical_key(
            chapter_revision_ref, seg, input_binding_hash
        ),
        "pointer_namespace": FIXTURE_POINTER_NAMESPACE,
        "candidate_schema_id": CANDIDATE_SCHEMA_ID,
        "input_binding_hash": input_binding_hash,
        "chapter_revision_ref": deepcopy(chapter_revision_ref),
        "seg": seg,
        "generation": 1,
        "current_candidate_version_ref": deepcopy(candidate_ref),
    }


def _build_pointer_snapshot(
    *,
    project_scope_id: str,
    author_workspace_logical_key: str,
    chapter_revision_ref: dict[str, Any],
    seg: int,
    input_binding_hash: str,
    candidate_ref: dict[str, Any],
    operation_id: str,
    created_at: str,
) -> dict[str, Any]:
    validate_chapter_revision_ref(chapter_revision_ref)
    live_pointer = build_live_pointer(
        project_scope_id=project_scope_id,
        author_workspace_logical_key=author_workspace_logical_key,
        chapter_revision_ref=chapter_revision_ref,
        seg=seg,
        input_binding_hash=input_binding_hash,
        candidate_ref=candidate_ref,
    )
    payload_without_hash = {
        **live_pointer,
        "snapshot_kind": "BASELINE_VERSIONED",
        "snapshot_operation_id": operation_id,
    }
    payload = {
        **payload_without_hash,
        "snapshot_request_hash": sha256_value(payload_without_hash),
    }
    record_id = f"pointer-snapshot:{sha256_value(payload_without_hash)[:32]}"
    return _make_record(
        record_type="M3_CANDIDATE_POINTER_SNAPSHOT",
        record_id=record_id,
        record_version=1,
        payload=payload,
        created_at=created_at,
        writer_token=_POINTER_WRITER_TOKEN,
    )


def _validate_pointer_root_candidate(
    candidate: dict[str, Any],
    *,
    author_workspace_logical_key: str,
    reference_records: list[dict[str, Any]],
    code: str,
) -> None:
    validate_candidate_version(
        candidate,
        allow_child=True,
        reference_records=reference_records,
    )
    payload = candidate["payload"]
    if (
        candidate["record_version"] != 1
        or payload["parent_candidate_version_ref"] is not None
        or payload["origin_commit_intent_ref"] is not None
    ):
        _fail(code, "pointer target is not a root baseline")
    expected_record_id = (
        f"cv:{sha256_value(author_workspace_logical_key)[:12]}:"
        f"{payload['version_payload_hash'][:32]}"
    )
    if candidate["record_id"] != expected_record_id:
        _fail(code, "candidate workspace")


def validate_pointer_snapshot(
    record: dict[str, Any], *, records: list[dict[str, Any]] | None = None
) -> None:
    validate_record(record)
    if record["record_type"] != "M3_CANDIDATE_POINTER_SNAPSHOT":
        _fail("B01_POINTER_SCOPE_MISMATCH", "record type")
    if record["source_module"] != SOURCE_MODULE or record["access"] != FIXTURE_ACCESS:
        _fail("B01_POINTER_SCOPE_MISMATCH", "record policy")
    payload = record["payload"]
    expected = {
        "project_scope_id",
        "author_workspace_logical_key",
        "logical_pointer_key",
        "pointer_namespace",
        "candidate_schema_id",
        "input_binding_hash",
        "chapter_revision_ref",
        "seg",
        "generation",
        "current_candidate_version_ref",
        "snapshot_kind",
        "snapshot_operation_id",
        "snapshot_request_hash",
    }
    _exact_keys(payload, expected, "B01_POINTER_SCOPE_MISMATCH")
    if payload["pointer_namespace"] != FIXTURE_POINTER_NAMESPACE:
        _fail("B01_POINTER_SCOPE_MISMATCH")
    validate_chapter_revision_ref(payload["chapter_revision_ref"])
    validate_record_ref(
        payload["current_candidate_version_ref"],
        code="B01_POINTER_SCOPE_MISMATCH",
        records=records,
        expected_type="M3_CANDIDATE_VERSION",
        expected_access=FIXTURE_ACCESS,
        expected_source_module=SOURCE_MODULE,
        expected_contract_version=CONTRACT_VERSION,
    )
    if records is not None:
        candidates = [
            candidate
            for candidate in records
            if record_ref(candidate) == payload["current_candidate_version_ref"]
        ]
        if len(candidates) != 1:
            _fail("B01_POINTER_SCOPE_MISMATCH", "candidate resolution")
        _validate_pointer_root_candidate(
            candidates[0],
            author_workspace_logical_key=payload["author_workspace_logical_key"],
            reference_records=records,
            code="B01_POINTER_SCOPE_MISMATCH",
        )
        if (
            candidates[0]["payload"]["chapter_revision_ref"]
            != payload["chapter_revision_ref"]
            or candidates[0]["payload"]["seg"] != payload["seg"]
            or candidates[0]["payload"]["candidate_schema_id"]
            != payload["candidate_schema_id"]
            or candidates[0]["payload"]["extraction_input_binding"][
                "input_binding_hash"
            ]
            != payload["input_binding_hash"]
        ):
            _fail("B01_POINTER_SCOPE_MISMATCH", "candidate scope")
    if payload["generation"] != 1 or payload["snapshot_kind"] != "BASELINE_VERSIONED":
        _fail("B01_POINTER_SCOPE_MISMATCH", "initialization")
    if payload["candidate_schema_id"] != CANDIDATE_SCHEMA_ID or payload[
        "logical_pointer_key"
    ] != pointer_logical_key(
        payload["chapter_revision_ref"],
        payload["seg"],
        payload["input_binding_hash"],
    ):
        _fail("B01_POINTER_SCOPE_MISMATCH", "logical key")
    if not _is_non_bool_int(payload["seg"]) or payload["seg"] < 1:
        _fail("B01_POINTER_SCOPE_MISMATCH", "segment")
    preimage = {
        key: value for key, value in payload.items() if key != "snapshot_request_hash"
    }
    if payload["snapshot_request_hash"] != sha256_value(preimage):
        _fail("B01_POINTER_SCOPE_MISMATCH", "request hash")


def _make_lineage_locator(
    candidate_version: dict[str, Any],
    lineage_id: str,
    *,
    reference_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validate_candidate_version(
        candidate_version,
        allow_child=True,
        reference_records=reference_records,
    )
    candidate_ref = record_ref(candidate_version)
    matches = [
        entry
        for entry in candidate_version["payload"]["lineage_index"]
        if entry["lineage_id"] == lineage_id
    ]
    if len(matches) != 1:
        _fail("B01_LINEAGE_INDEX_INVALID", "lineage not found")
    entry = matches[0]
    locator = {
        "contract": LINEAGE_LOCATOR_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "candidate_version_ref": candidate_ref,
        "lineage_id": entry["lineage_id"],
        "json_pointer": entry["json_pointer"],
        "item_hash": entry["item_hash"],
        "locator_hash": "",
    }
    locator["locator_hash"] = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    return locator


def validate_lineage_locator(
    locator: dict[str, Any],
    *,
    candidate_version: dict[str, Any] | None = None,
    reference_records: list[dict[str, Any]] | None = None,
) -> None:
    expected = {
        "contract",
        "contract_version",
        "candidate_version_ref",
        "lineage_id",
        "json_pointer",
        "item_hash",
        "locator_hash",
    }
    _exact_keys(locator, expected, "B01_LINEAGE_INDEX_INVALID")
    if locator["contract"] != LINEAGE_LOCATOR_CONTRACT:
        _fail("B01_LINEAGE_INDEX_INVALID", "locator contract")
    if locator["contract_version"] != CONTRACT_VERSION:
        _fail("B01_LINEAGE_INDEX_INVALID", "locator contract version")
    validate_record_ref(
        locator["candidate_version_ref"],
        records=[candidate_version] if candidate_version is not None else None,
        expected_type="M3_CANDIDATE_VERSION",
        expected_access=FIXTURE_ACCESS,
        expected_source_module=SOURCE_MODULE,
        expected_contract_version=CONTRACT_VERSION,
    )
    preimage = {key: value for key, value in locator.items() if key != "locator_hash"}
    if locator["locator_hash"] != sha256_value(preimage):
        _fail("B01_LINEAGE_INDEX_INVALID", "locator hash")
    if candidate_version is not None:
        if reference_records is None:
            _fail("B01_REFERENCE_INTEGRITY_FAILED", "reference records required")
        validate_candidate_version(
            candidate_version,
            allow_child=True,
            reference_records=reference_records,
        )
        matches = [
            entry
            for entry in candidate_version["payload"]["lineage_index"]
            if entry["lineage_id"] == locator["lineage_id"]
        ]
        if len(matches) != 1 or matches[0] != {
            "lineage_id": locator["lineage_id"],
            "json_pointer": locator["json_pointer"],
            "item_hash": locator["item_hash"],
        }:
            _fail("B01_LINEAGE_INDEX_INVALID", "locator target")
        pointer_match = re.fullmatch(r"/items/(0|[1-9][0-9]*)", locator["json_pointer"])
        if pointer_match is None:
            _fail("B01_LINEAGE_INDEX_INVALID", "locator JSON pointer")
        item_index = int(pointer_match.group(1))
        items = candidate_version["payload"]["items"]
        if item_index >= len(items):
            _fail("B01_LINEAGE_INDEX_INVALID", "locator target out of range")
        target = items[item_index]
        if (
            target["lineage_id"] != locator["lineage_id"]
            or target["item_hash"] != locator["item_hash"]
        ):
            _fail("B01_LINEAGE_INDEX_INVALID", "locator item")


def _make_evidence_locator(
    candidate_version: dict[str, Any],
    lineage_id: str,
    *,
    reference_records: list[dict[str, Any]],
) -> dict[str, Any]:
    validate_candidate_version(
        candidate_version,
        allow_child=True,
        reference_records=reference_records,
    )
    matches = [
        (index, item)
        for index, item in enumerate(candidate_version["payload"]["items"])
        if item["lineage_id"] == lineage_id
    ]
    if len(matches) != 1:
        _fail("B01_EVIDENCE_LOCATOR_INVALID", "lineage")
    index, item = matches[0]
    locator = {
        "contract": EVIDENCE_LOCATOR_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "candidate_version_ref": record_ref(candidate_version),
        "lineage_id": lineage_id,
        "evidence_json_pointer": f"/items/{index}/evidence",
        "evidence_sha256": item["evidence_binding"]["evidence_sha256"],
        "binding_hash": item["evidence_binding"]["binding_hash"],
        "locator_hash": "",
    }
    locator["locator_hash"] = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    return locator


def validate_evidence_locator(
    locator: dict[str, Any],
    *,
    candidate_version: dict[str, Any],
    reference_records: list[dict[str, Any]],
) -> None:
    _exact_keys(
        locator,
        {
            "contract",
            "contract_version",
            "candidate_version_ref",
            "lineage_id",
            "evidence_json_pointer",
            "evidence_sha256",
            "binding_hash",
            "locator_hash",
        },
        "B01_EVIDENCE_LOCATOR_INVALID",
    )
    if (
        locator["contract"] != EVIDENCE_LOCATOR_CONTRACT
        or locator["contract_version"] != CONTRACT_VERSION
    ):
        _fail("B01_EVIDENCE_LOCATOR_INVALID", "contract")
    validate_candidate_version(
        candidate_version,
        allow_child=True,
        reference_records=reference_records,
    )
    validate_record_ref(
        locator["candidate_version_ref"],
        code="B01_EVIDENCE_LOCATOR_INVALID",
        records=[candidate_version],
        expected_type="M3_CANDIDATE_VERSION",
        expected_access=FIXTURE_ACCESS,
        expected_source_module=SOURCE_MODULE,
        expected_contract_version=CONTRACT_VERSION,
    )
    matches = [
        (index, item)
        for index, item in enumerate(candidate_version["payload"]["items"])
        if item["lineage_id"] == locator["lineage_id"]
    ]
    if len(matches) != 1:
        _fail("B01_EVIDENCE_LOCATOR_INVALID", "lineage")
    index, item = matches[0]
    if (
        locator["evidence_json_pointer"] != f"/items/{index}/evidence"
        or locator["evidence_sha256"] != item["evidence_binding"]["evidence_sha256"]
        or locator["binding_hash"] != item["evidence_binding"]["binding_hash"]
    ):
        _fail("B01_EVIDENCE_LOCATOR_INVALID", "target")
    preimage = {key: value for key, value in locator.items() if key != "locator_hash"}
    if locator["locator_hash"] != sha256_value(preimage):
        _fail("B01_EVIDENCE_LOCATOR_INVALID", "locator hash")


def make_legacy_read_only_candidate_fixture(
    *,
    chapter_revision_ref: dict[str, Any],
    seg: int,
    origin_attempt_refs: list[dict[str, Any]],
    raw_items: list[dict[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    """Build an r03.3 fixture for compatibility reads; never stage it."""

    validate_chapter_revision_ref(chapter_revision_ref)
    items: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_items):
        allowed = {"text"}
        if "quote" in raw:
            allowed.add("quote")
        if set(raw) != allowed or not isinstance(raw["text"], str) or not raw["text"]:
            _fail("B01_LEGACY_RECORD_INVALID", "item")
        lineage_seed = {
            "chapter_revision_ref": chapter_revision_ref,
            "seg": seg,
            "ordinal": index,
            "text": raw["text"],
            "quote_if_present": raw.get("quote"),
        }
        item: dict[str, Any] = {
            "lineage_id": f"lin_{sha256_value(lineage_seed)}",
            "text": raw["text"],
        }
        item_preimage = deepcopy(item)
        if "quote" in raw:
            item["quote"] = raw["quote"]
            item_preimage["quote_if_present"] = raw["quote"]
        item["item_hash"] = sha256_value(item_preimage)
        items.append(item)
    lineage_index = [
        {
            "lineage_id": item["lineage_id"],
            "json_pointer": f"/items/{index}",
            "item_hash": item["item_hash"],
        }
        for index, item in enumerate(items)
    ]
    payload_without_hash = {
        "chapter_revision_ref": deepcopy(chapter_revision_ref),
        "seg": seg,
        "parent_candidate_version_ref": None,
        "origin_attempt_refs": deepcopy(origin_attempt_refs),
        "origin_commit_intent_ref": None,
        "items": items,
        "lineage_index": lineage_index,
    }
    payload = {
        **payload_without_hash,
        "version_payload_hash": sha256_value(payload_without_hash),
    }
    return _make_record(
        record_type="M3_CANDIDATE_VERSION",
        record_id=f"legacy-cv:{payload['version_payload_hash'][:32]}",
        record_version=1,
        payload=payload,
        created_at=created_at,
        writer_token=_CANDIDATE_WRITER_TOKEN,
        contract_version=LEGACY_CONTRACT_VERSION,
    )


def read_legacy_candidate_version(record: dict[str, Any]) -> dict[str, Any]:
    """Return a marked read-only summary without inventing v2.1 evidence."""

    validate_record(record)
    if (
        record["contract_version"] != LEGACY_CONTRACT_VERSION
        or record["record_type"] != "M3_CANDIDATE_VERSION"
    ):
        _fail("B01_LEGACY_RECORD_INVALID", "identity")
    payload = record["payload"]
    _exact_keys(
        payload,
        {
            "chapter_revision_ref",
            "seg",
            "parent_candidate_version_ref",
            "origin_attempt_refs",
            "origin_commit_intent_ref",
            "items",
            "lineage_index",
            "version_payload_hash",
        },
        "B01_LEGACY_RECORD_INVALID",
    )
    for item in payload["items"]:
        allowed = {"lineage_id", "text", "item_hash"}
        if "quote" in item:
            allowed.add("quote")
        _exact_keys(item, allowed, "B01_LEGACY_RECORD_INVALID")
        if "evidence" in item or "status" in item or "speaker" in item:
            _fail("B01_LEGACY_RECORD_INVALID", "v2.1 field in legacy item")
    payload_preimage = {
        key: value for key, value in payload.items() if key != "version_payload_hash"
    }
    if payload["version_payload_hash"] != sha256_value(payload_preimage):
        _fail("B01_LEGACY_RECORD_INVALID", "payload hash")
    return {
        "mode": "LEGACY_READ_ONLY",
        "candidate_version_ref": record_ref(record),
        "items": deepcopy(payload["items"]),
        "quote_status": "HISTORICAL_UNVERIFIED_HINT",
        "evidence_locator_available": False,
    }


def _project_version_diff(
    parent: dict[str, Any],
    child: dict[str, Any],
    *,
    persist: bool = False,
    reference_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if persist:
        _fail("B01_DERIVED_VIEW_PERSIST_FORBIDDEN")
    try:
        validate_candidate_version(
            parent, allow_child=True, reference_records=reference_records
        )
        validate_candidate_version(
            child, allow_child=True, reference_records=reference_records
        )
    except B01ContractError as error:
        _fail("B01_VERSION_DIFF_INVALID", error.code)
    parent_ref = record_ref(parent)
    if child["payload"]["parent_candidate_version_ref"] != parent_ref:
        _fail("B01_VERSION_DIFF_INVALID", "parent reference")
    if (
        child["payload"]["chapter_revision_ref"]
        != parent["payload"]["chapter_revision_ref"]
        or child["payload"]["seg"] != parent["payload"]["seg"]
        or child["payload"]["candidate_schema_id"]
        != parent["payload"]["candidate_schema_id"]
        or child["payload"]["extraction_input_binding"]
        != parent["payload"]["extraction_input_binding"]
        or child["payload"]["segment_index_ref"]
        != parent["payload"]["segment_index_ref"]
    ):
        _fail("B01_VERSION_DIFF_INVALID", "scope")
    parent_items = parent["payload"]["items"]
    child_items = child["payload"]["items"]
    if len(child_items) > len(parent_items):
        _fail("B01_VERSION_DIFF_INVALID", "child added lineage")
    for index, child_item in enumerate(child_items):
        if child_item["lineage_id"] != parent_items[index]["lineage_id"]:
            _fail("B01_VERSION_DIFF_INVALID", "child changed lineage")
    changed: list[str] = []
    for index in range(max(len(parent_items), len(child_items))):
        if index >= len(parent_items) or index >= len(child_items):
            changed.append(f"/items/{index}")
            continue
        parent_item = parent_items[index]
        child_item = child_items[index]
        for field in ("fact", "status", "evidence", "speaker", "evidence_binding"):
            if parent_item.get(field) != child_item.get(field):
                changed.append(f"/items/{index}/{field}")
    return {
        "view_type": "DERIVED_RECOMPUTABLE",
        "parent_candidate_version_ref": parent_ref,
        "child_candidate_version_ref": record_ref(child),
        "changed_json_pointers": sorted(
            set(changed), key=lambda item: item.encode("utf-8")
        ),
        "excluded_sidecar_proposal_refs": [],
    }


def make_read_only_child_fixture(
    parent: dict[str, Any],
    raw_items: list[dict[str, Any]],
    *,
    reference_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a synthetic child for structural diff fixtures; never publish it."""
    validate_candidate_version(parent, reference_records=reference_records)
    payload = parent["payload"]
    items: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_items):
        if index >= len(payload["items"]):
            _fail("B01_CHILD_CREATION_OUT_OF_SCOPE", "new child item fixture")
        allowed = {"fact", "status", "evidence"}
        if "speaker" in raw:
            allowed.add("speaker")
        if set(raw) != allowed:
            _fail("B01_VERSION_DIFF_INVALID", "child item fields")
        parent_item = payload["items"][index]
        if raw["evidence"] != parent_item["evidence"]:
            _fail("B01_VERSION_DIFF_INVALID", "child evidence requires B-06")
        item = {
            "lineage_id": parent_item["lineage_id"],
            "fact": raw["fact"],
            "status": raw["status"],
            "evidence": raw["evidence"],
        }
        if "speaker" in raw:
            item["speaker"] = raw["speaker"]
        item["evidence_binding"] = deepcopy(parent_item["evidence_binding"])
        item_preimage: dict[str, Any] = deepcopy(item)
        item["item_hash"] = sha256_value(item_preimage)
        items.append(item)
    lineage_index = [
        {
            "lineage_id": item["lineage_id"],
            "json_pointer": f"/items/{index}",
            "item_hash": item["item_hash"],
        }
        for index, item in enumerate(items)
    ]
    child_payload_without_hash = {
        "candidate_schema_id": payload["candidate_schema_id"],
        "extraction_input_binding": deepcopy(payload["extraction_input_binding"]),
        "segment_index_ref": deepcopy(payload["segment_index_ref"]),
        "chapter_revision_ref": deepcopy(payload["chapter_revision_ref"]),
        "seg": payload["seg"],
        "parent_candidate_version_ref": record_ref(parent),
        "origin_attempt_refs": deepcopy(payload["origin_attempt_refs"]),
        "origin_commit_intent_ref": None,
        "items": items,
        "lineage_index": lineage_index,
    }
    child_payload = {
        **child_payload_without_hash,
        "version_payload_hash": sha256_value(child_payload_without_hash),
    }
    return _make_record(
        record_type="M3_CANDIDATE_VERSION",
        record_id=f"{parent['record_id']}:synthetic-child",
        record_version=2,
        payload=child_payload,
        created_at=parent["created_at"],
        writer_token=_CANDIDATE_WRITER_TOKEN,
    )


def _record_storage_key(record: dict[str, Any]) -> str:
    return f"{record['record_type']}:{record['record_id']}:{record['record_version']}"


class FixtureStore:
    """Atomic JSON fixture store. The caller controls and isolates its directory."""

    MUTATION_EVENTS: ClassVar[set[str]] = {
        "fixture_storage_commit_attempt",
        "fixture_storage_mkdir_attempt",
        "fixture_storage_pending_write_attempt",
        "fixture_storage_atomic_replace_attempt",
        "fixture_storage_cleanup_attempt",
    }
    AUDIT_EVENTS: ClassVar[list[tuple[str, str]]] = []

    def __init__(self, root: Path) -> None:
        resolved = root.resolve(strict=False)
        module_root = Path(__file__).resolve().parent
        repository_root = module_root.parents[1]
        temporary_root = Path(tempfile.gettempdir()).resolve()
        inside_repository = (
            resolved == repository_root or repository_root in resolved.parents
        )
        inside_write_set = resolved == module_root or module_root in resolved.parents
        inside_test_temp = (
            resolved == temporary_root or temporary_root in resolved.parents
        )
        if (inside_repository and not inside_write_set) or (
            not inside_repository and not inside_test_temp
        ):
            _fail("B01_WRITE_SET_ESCAPE", str(root))
        self.root = root
        self.state_path = root / "state.json"
        self.events: list[str] = []

    def _audit(self, event: str) -> None:
        self.events.append(event)
        self.AUDIT_EVENTS.append((str(self.root.resolve(strict=False)), event))

    @classmethod
    def audit_marker(cls) -> int:
        return len(cls.AUDIT_EVENTS)

    @classmethod
    def mutation_events_since(cls, marker: int, root: Path | None = None) -> list[str]:
        resolved_root = None if root is None else str(root.resolve(strict=False))
        return [
            event
            for event_root, event in cls.AUDIT_EVENTS[marker:]
            if (resolved_root is None or event_root == resolved_root)
            and event in cls.MUTATION_EVENTS
        ]

    @staticmethod
    def empty_state() -> dict[str, Any]:
        return {"records": {}, "pointers": {}, "operations": {}}

    def read(self) -> dict[str, Any]:
        self._audit("fixture_storage_read")
        if not self.state_path.exists():
            return self.empty_state()
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def commit(self, state: dict[str, Any]) -> None:
        self._audit("fixture_storage_commit_attempt")
        self._audit("fixture_storage_mkdir_attempt")
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.root / ".state.json.pending"
        payload = json.dumps(
            _normalize(state),
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        try:
            self._audit("fixture_storage_pending_write_attempt")
            temporary.write_text(payload, encoding="utf-8")
            self._audit("fixture_storage_atomic_replace_attempt")
            os.replace(temporary, self.state_path)
        except OSError as error:
            self._audit("fixture_storage_cleanup_attempt")
            temporary.unlink(missing_ok=True)
            _fail("B01_TRANSACTION_WRITE_FAILED", str(error))
        self._audit("fixture_storage_atomic_replace")


def _stage_immutable_record(
    state: dict[str, Any],
    record: dict[str, Any],
    *,
    collision_code: str,
) -> dict[str, Any]:
    validate_record(record)
    key = _record_storage_key(record)
    existing = state["records"].get(key)
    if existing is None:
        state["records"][key] = deepcopy(record)
        return record_ref(record)
    if canonical_bytes(existing) != canonical_bytes(record):
        _fail(collision_code, key)
    return record_ref(existing)


def validate_live_pointer(
    pointer: dict[str, Any], *, records: list[dict[str, Any]]
) -> None:
    _exact_keys(pointer, LIVE_POINTER_KEYS, "B01_POINTER_SCOPE_MISMATCH")
    if pointer["pointer_namespace"] != FIXTURE_POINTER_NAMESPACE:
        _fail("B01_POINTER_SCOPE_MISMATCH", "namespace")
    validate_chapter_revision_ref(pointer["chapter_revision_ref"])
    if not _is_non_bool_int(pointer["seg"]) or pointer["seg"] < 1:
        _fail("B01_POINTER_SCOPE_MISMATCH", "segment")
    if pointer["generation"] != 1:
        _fail("B01_POINTER_SCOPE_MISMATCH", "generation")
    if pointer["candidate_schema_id"] != CANDIDATE_SCHEMA_ID or pointer[
        "logical_pointer_key"
    ] != pointer_logical_key(
        pointer["chapter_revision_ref"],
        pointer["seg"],
        pointer["input_binding_hash"],
    ):
        _fail("B01_POINTER_SCOPE_MISMATCH", "logical key")
    validate_record_ref(
        pointer["current_candidate_version_ref"],
        code="B01_REFERENCE_INTEGRITY_FAILED",
        records=records,
        expected_type="M3_CANDIDATE_VERSION",
        expected_access=FIXTURE_ACCESS,
        expected_source_module=SOURCE_MODULE,
        expected_contract_version=CONTRACT_VERSION,
    )
    candidates = [
        record
        for record in records
        if record_ref(record) == pointer["current_candidate_version_ref"]
    ]
    if len(candidates) != 1:
        _fail("B01_REFERENCE_INTEGRITY_FAILED", "pointer candidate")
    _validate_pointer_root_candidate(
        candidates[0],
        author_workspace_logical_key=pointer["author_workspace_logical_key"],
        reference_records=records,
        code="B01_POINTER_SCOPE_MISMATCH",
    )
    candidate_payload = candidates[0]["payload"]
    if (
        candidate_payload["chapter_revision_ref"] != pointer["chapter_revision_ref"]
        or candidate_payload["seg"] != pointer["seg"]
        or candidate_payload["candidate_schema_id"] != pointer["candidate_schema_id"]
        or candidate_payload["extraction_input_binding"]["input_binding_hash"]
        != pointer["input_binding_hash"]
    ):
        _fail("B01_POINTER_SCOPE_MISMATCH", "candidate scope")


class SegmentIndexSnapshotWriter:
    @staticmethod
    def build(**kwargs: Any) -> dict[str, Any]:
        return _build_segment_index_snapshot(**kwargs)

    @staticmethod
    def stage(state: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
        validate_segment_index_snapshot(record)
        key = _record_storage_key(record)
        existing = state["records"].get(key)
        if existing is None:
            return _stage_immutable_record(
                state,
                record,
                collision_code="B01_SEGMENT_INDEX_IDENTITY_COLLISION",
            )
        validate_segment_index_snapshot(existing)
        if canonical_bytes(existing["payload"]) != canonical_bytes(record["payload"]):
            _fail("B01_SEGMENT_INDEX_IDENTITY_COLLISION", key)
        return record_ref(existing)


class CandidateVersionStore:
    @staticmethod
    def build_root(**kwargs: Any) -> dict[str, Any]:
        return _build_root_candidate_version(**kwargs)

    @staticmethod
    def stage_root(
        state: dict[str, Any],
        record: dict[str, Any],
        *,
        author_workspace_logical_key: str,
        reference_records: list[dict[str, Any]],
        segment_inputs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        validate_candidate_version(
            record,
            reference_records=reference_records,
        )
        segment_records = [
            item
            for item in reference_records
            if record_ref(item) == record["payload"]["segment_index_ref"]
        ]
        if len(segment_records) != 1:
            _fail("B01_SEGMENT_INDEX_INVALID", "segment reference")
        segment_record = segment_records[0]
        _exact_segment_source_bytes(segment_record, segment_inputs)
        for item in record["payload"]["items"]:
            expected_locations = _expected_evidence_locations(
                item["evidence"],
                seg=record["payload"]["seg"],
                segment_index_record=segment_record,
                segment_inputs=segment_inputs,
            )
            if item["evidence_binding"]["match_locations"] != expected_locations:
                _fail("B01_EVIDENCE_BINDING_INVALID", "exact source locations")
        payload_hash = record["payload"]["version_payload_hash"]
        expected_record_id = (
            f"cv:{sha256_value(author_workspace_logical_key)[:12]}:{payload_hash[:32]}"
        )
        if record["record_id"] != expected_record_id:
            _fail("B01_CANDIDATE_VERSION_INVALID", "candidate workspace")
        existing_payload_matches = [
            existing
            for existing in state["records"].values()
            if existing["record_type"] == "M3_CANDIDATE_VERSION"
            and existing["record_id"] == expected_record_id
            and existing["payload"]["version_payload_hash"] == payload_hash
        ]
        for existing in existing_payload_matches:
            if canonical_bytes(existing["payload"]) != canonical_bytes(
                record["payload"]
            ):
                _fail("B01_VERSION_HASH_COLLISION")
            return record_ref(existing)
        return _stage_immutable_record(
            state,
            record,
            collision_code="B01_CANDIDATE_VERSION_IDENTITY_COLLISION",
        )

    @staticmethod
    def lineage_locator(
        candidate_version: dict[str, Any],
        lineage_id: str,
        *,
        reference_records: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return _make_lineage_locator(
            candidate_version,
            lineage_id,
            reference_records=reference_records,
        )

    @staticmethod
    def evidence_locator(
        candidate_version: dict[str, Any],
        lineage_id: str,
        *,
        reference_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return _make_evidence_locator(
            candidate_version,
            lineage_id,
            reference_records=reference_records,
        )


class CandidatePointerSnapshotWriter:
    @staticmethod
    def build(**kwargs: Any) -> dict[str, Any]:
        return _build_pointer_snapshot(**kwargs)

    @staticmethod
    def stage_initialization(
        state: dict[str, Any],
        *,
        pointer_record: dict[str, Any],
        live_pointer: dict[str, Any],
        all_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        validate_pointer_snapshot(pointer_record, records=all_records)
        validate_live_pointer(live_pointer, records=all_records)
        pointer_key = live_pointer["logical_pointer_key"]
        if pointer_key in state["pointers"]:
            _fail("B01_POINTER_ALREADY_INITIALIZED")
        snapshot_ref = _stage_immutable_record(
            state,
            pointer_record,
            collision_code="B01_POINTER_SNAPSHOT_IDENTITY_COLLISION",
        )
        state["pointers"][pointer_key] = deepcopy(live_pointer)
        return snapshot_ref


class VersionDiffProjector:
    @staticmethod
    def project(
        parent: dict[str, Any],
        child: dict[str, Any],
        *,
        persist: bool = False,
        reference_records: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return _project_version_diff(
            parent,
            child,
            persist=persist,
            reference_records=reference_records,
        )


def verify_state(
    state: dict[str, Any], *, reference_records: list[dict[str, Any]]
) -> None:
    _exact_keys(
        state, {"records", "pointers", "operations"}, "B01_REFERENCE_INTEGRITY_FAILED"
    )
    records = list(state["records"].values())
    all_records = [*reference_records, *records]
    for record in records:
        validate_record(record)
        if record["record_type"] == "M3_SEGMENT_INDEX_SNAPSHOT":
            validate_segment_index_snapshot(record)
            validate_record_ref(
                record["payload"]["accepted_source_generation_ref"],
                code="B01_SOURCE_GENERATION_INVALID",
                records=all_records,
                expected_type=SOURCE_GENERATION_RECORD_TYPE,
                expected_access=FIXTURE_ACCESS,
                expected_source_module="M1_READ_ONLY_ADAPTER",
                expected_contract_version=CONTRACT_VERSION,
            )
        elif record["record_type"] == "M3_CANDIDATE_VERSION":
            validate_candidate_version(
                record,
                allow_child=False,
                reference_records=all_records,
            )
        elif record["record_type"] == "M3_CANDIDATE_POINTER_SNAPSHOT":
            validate_pointer_snapshot(record, records=all_records)
        else:
            _fail("B01_REFERENCE_INTEGRITY_FAILED", "unexpected persisted record")
    for pointer_key, pointer in state["pointers"].items():
        validate_live_pointer(pointer, records=all_records)
        if pointer["logical_pointer_key"] != pointer_key:
            _fail("B01_POINTER_SCOPE_MISMATCH", "pointer map key")
        snapshots = [
            record
            for record in records
            if record["record_type"] == "M3_CANDIDATE_POINTER_SNAPSHOT"
            and record["payload"]["logical_pointer_key"] == pointer_key
        ]
        if len(snapshots) != 1:
            _fail("B01_REFERENCE_INTEGRITY_FAILED", "pointer snapshot cardinality")
        snapshot_pointer = {
            key: snapshots[0]["payload"][key] for key in LIVE_POINTER_KEYS
        }
        if canonical_bytes(snapshot_pointer) != canonical_bytes(pointer):
            _fail("B01_POINTER_SCOPE_MISMATCH", "snapshot/live pointer drift")
    for operation in state["operations"].values():
        _exact_keys(
            operation, {"request_hash", "result"}, "B01_REFERENCE_INTEGRITY_FAILED"
        )
        if not _is_sha256(operation["request_hash"]):
            _fail("B01_REFERENCE_INTEGRITY_FAILED", "operation hash")
        for key, value in operation["result"].items():
            if key.endswith("_ref"):
                validate_record_ref(
                    value,
                    code="B01_REFERENCE_INTEGRITY_FAILED",
                    records=all_records,
                )


def _build_ccz142_extraction_handoff_payload(
    *,
    source_lane: str,
    source_module: str,
    source_contract_version: str,
    project_scope_id: str,
    author_workspace_logical_key: str,
    chapter_revision_ref: dict[str, Any],
    accepted_source_generation_ref: dict[str, Any],
    writing_material_refs: list[dict[str, Any]],
    source_module_identity: str,
    segment_inputs: list[dict[str, Any]],
    seg: int,
    origin_attempt_refs: list[dict[str, Any]],
    raw_items: list[dict[str, Any]],
) -> dict[str, Any]:
    if (
        source_lane != CCZ142_EXTRACTION_SOURCE_LANE
        or source_module != CCZ142_EXTRACTION_SOURCE_MODULE
        or source_contract_version != CCZ142_EXTRACTION_HANDOFF_CONTRACT
    ):
        _fail("B01_EXTRACTION_SOURCE_INVALID")
    validate_chapter_revision_ref(chapter_revision_ref)
    if not isinstance(project_scope_id, str) or not project_scope_id:
        _fail("B01_EXTRACTION_SOURCE_INVALID", "project scope")
    if (
        not isinstance(author_workspace_logical_key, str)
        or not author_workspace_logical_key
    ):
        _fail("B01_EXTRACTION_SOURCE_INVALID", "workspace scope")
    if not _is_non_bool_int(seg) or seg < 1:
        _fail("B01_EXTRACTION_SOURCE_INVALID", "segment")
    if not isinstance(raw_items, list) or not all(
        isinstance(item, dict) for item in raw_items
    ):
        _fail("B01_EXTRACTION_SOURCE_INVALID", "candidate items")
    if not isinstance(segment_inputs, list) or not isinstance(
        origin_attempt_refs, list
    ):
        _fail("B01_EXTRACTION_SOURCE_INVALID", "handoff references")
    payload = {
        "source_lane": source_lane,
        "source_module": source_module,
        "source_contract_version": source_contract_version,
        "candidate_schema_id": CANDIDATE_SCHEMA_ID,
        "project_scope_id": project_scope_id,
        "author_workspace_logical_key": author_workspace_logical_key,
        "chapter_revision_ref": deepcopy(chapter_revision_ref),
        "accepted_source_generation_ref": deepcopy(accepted_source_generation_ref),
        "writing_material_refs": deepcopy(writing_material_refs),
        "source_module_identity": source_module_identity,
        "segment_inputs": deepcopy(segment_inputs),
        "seg": seg,
        "origin_attempt_refs": deepcopy(origin_attempt_refs),
        "raw_items": deepcopy(raw_items),
    }
    _exact_keys(payload, CCZ142_HANDOFF_KEYS, "B01_EXTRACTION_SOURCE_INVALID")
    return payload


class B01Service:
    __slots__ = ("store", "__open_extraction_admission")

    def __init__(self, _store: FixtureStore) -> None:
        _fail("B01_RUNTIME_COMPOSITION_REQUIRED")

    def _load_admitted_raw_items(
        self,
        extraction_admission: object,
        *,
        project_scope_id: str,
        author_workspace_logical_key: str,
        chapter_revision_ref: dict[str, Any],
        accepted_source_generation_ref: dict[str, Any],
        writing_material_refs: list[dict[str, Any]],
        source_module_identity: str,
        segment_inputs: list[dict[str, Any]],
        seg: int,
        origin_attempt_refs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        handoff = self.__open_extraction_admission(extraction_admission)
        _exact_keys(
            handoff,
            CCZ142_HANDOFF_KEYS,
            "B01_EXTRACTION_ADMISSION_DRIFT",
        )
        expected_binding = {
            "source_lane": CCZ142_EXTRACTION_SOURCE_LANE,
            "source_module": CCZ142_EXTRACTION_SOURCE_MODULE,
            "source_contract_version": CCZ142_EXTRACTION_HANDOFF_CONTRACT,
            "candidate_schema_id": CANDIDATE_SCHEMA_ID,
            "project_scope_id": project_scope_id,
            "author_workspace_logical_key": author_workspace_logical_key,
            "chapter_revision_ref": chapter_revision_ref,
            "accepted_source_generation_ref": accepted_source_generation_ref,
            "writing_material_refs": writing_material_refs,
            "source_module_identity": source_module_identity,
            "segment_inputs": segment_inputs,
            "seg": seg,
            "origin_attempt_refs": origin_attempt_refs,
        }
        actual_binding = {
            key: value for key, value in handoff.items() if key != "raw_items"
        }
        if canonical_bytes(actual_binding) != canonical_bytes(expected_binding):
            _fail("B01_EXTRACTION_ADMISSION_MISMATCH")
        raw_items = handoff["raw_items"]
        if not isinstance(raw_items, list) or not all(
            isinstance(item, dict) for item in raw_items
        ):
            _fail("B01_EXTRACTION_ADMISSION_DRIFT", "candidate items")
        return deepcopy(raw_items)

    def initialize_root_baseline(
        self,
        *,
        admission: dict[str, Any],
        reference_records: list[dict[str, Any]],
        project_scope_id: str,
        author_workspace_logical_key: str,
        chapter_revision_ref: dict[str, Any],
        accepted_source_generation_ref: dict[str, Any],
        writing_material_refs: list[dict[str, Any]],
        source_module_identity: str,
        segment_inputs: list[dict[str, Any]],
        seg: int,
        origin_attempt_refs: list[dict[str, Any]],
        extraction_admission: object | None = None,
        operation_id: str,
        created_at: str,
        pointer_namespace: str = FIXTURE_POINTER_NAMESPACE,
        crash_point: str | None = None,
        **unexpected_inputs: Any,
    ) -> dict[str, Any]:
        if unexpected_inputs:
            if "raw_items" in unexpected_inputs:
                _fail("B01_EXTRACTION_ADMISSION_REQUIRED", "raw_items")
            _fail(
                "B01_CANDIDATE_VERSION_INVALID",
                f"unexpected inputs: {sorted(unexpected_inputs)}",
            )
        validate_admission(admission, reference_records=reference_records)
        raw_items = self._load_admitted_raw_items(
            extraction_admission,
            project_scope_id=project_scope_id,
            author_workspace_logical_key=author_workspace_logical_key,
            chapter_revision_ref=chapter_revision_ref,
            accepted_source_generation_ref=accepted_source_generation_ref,
            writing_material_refs=writing_material_refs,
            source_module_identity=source_module_identity,
            segment_inputs=segment_inputs,
            seg=seg,
            origin_attempt_refs=origin_attempt_refs,
        )
        if pointer_namespace != FIXTURE_POINTER_NAMESPACE:
            _fail("B01_POINTER_SCOPE_MISMATCH")
        if crash_point == "before_staging":
            _fail("B01_SIMULATED_CRASH", crash_point)
        extraction_input_binding = build_extraction_input_binding(
            accepted_source_generation_ref=accepted_source_generation_ref,
            chapter_revision_ref=chapter_revision_ref,
            writing_material_refs=writing_material_refs,
            reference_records=reference_records,
        )
        segment_record = SegmentIndexSnapshotWriter.build(
            project_scope_id=project_scope_id,
            author_workspace_logical_key=author_workspace_logical_key,
            chapter_revision_ref=chapter_revision_ref,
            accepted_source_generation_ref=accepted_source_generation_ref,
            reference_records=reference_records,
            source_module_identity=source_module_identity,
            segment_inputs=segment_inputs,
            created_at=created_at,
        )
        validate_segment_index_snapshot(segment_record)
        if seg > len(segment_record["payload"]["segments"]):
            _fail("B01_SEGMENT_INDEX_INVALID", "selected segment")
        state = self.store.read()
        verify_state(state, reference_records=reference_records)
        staged = deepcopy(state)
        segment_ref = SegmentIndexSnapshotWriter.stage(staged, segment_record)
        normalized_segments = [
            record
            for record in staged["records"].values()
            if record_ref(record) == segment_ref
        ]
        if len(normalized_segments) != 1:
            _fail("B01_SEGMENT_INDEX_INVALID", "normalized segment record")
        normalized_segment_record = normalized_segments[0]
        candidate_record = CandidateVersionStore.build_root(
            chapter_revision_ref=chapter_revision_ref,
            seg=seg,
            author_workspace_logical_key=author_workspace_logical_key,
            extraction_input_binding=extraction_input_binding,
            segment_index_record=normalized_segment_record,
            origin_attempt_refs=origin_attempt_refs,
            reference_records=reference_records,
            segment_inputs=segment_inputs,
            raw_items=raw_items,
            created_at=created_at,
        )
        validate_candidate_version(
            candidate_record,
            reference_records=[normalized_segment_record, *reference_records],
        )
        candidate_ref = CandidateVersionStore.stage_root(
            staged,
            candidate_record,
            author_workspace_logical_key=author_workspace_logical_key,
            reference_records=[*reference_records, *staged["records"].values()],
            segment_inputs=segment_inputs,
        )
        pointer_record = CandidatePointerSnapshotWriter.build(
            project_scope_id=project_scope_id,
            author_workspace_logical_key=author_workspace_logical_key,
            chapter_revision_ref=chapter_revision_ref,
            seg=seg,
            input_binding_hash=extraction_input_binding["input_binding_hash"],
            candidate_ref=candidate_ref,
            operation_id=operation_id,
            created_at=created_at,
        )
        all_staged_records = [*reference_records, *staged["records"].values()]
        validate_pointer_snapshot(pointer_record, records=all_staged_records)
        request_hash = pointer_record["payload"]["snapshot_request_hash"]
        pointer_key = pointer_record["payload"]["logical_pointer_key"]
        prior_operation = state["operations"].get(operation_id)
        if prior_operation is not None:
            if prior_operation["request_hash"] != request_hash:
                _fail("B01_OPERATION_CONFLICT")
            prior_result = prior_operation["result"]
            _exact_keys(
                prior_result,
                {
                    "segment_index_snapshot_ref",
                    "candidate_version_ref",
                    "candidate_pointer_snapshot_ref",
                    "logical_pointer_key",
                },
                "B01_REFERENCE_INTEGRITY_FAILED",
            )
            if (
                prior_result["segment_index_snapshot_ref"] != segment_ref
                or prior_result["candidate_version_ref"] != candidate_ref
                or prior_result["logical_pointer_key"] != pointer_key
            ):
                _fail("B01_REFERENCE_INTEGRITY_FAILED", "operation replay result")
            prior_snapshot_ref = prior_result["candidate_pointer_snapshot_ref"]
            validate_record_ref(
                prior_snapshot_ref,
                code="B01_REFERENCE_INTEGRITY_FAILED",
                records=list(state["records"].values()),
                expected_type="M3_CANDIDATE_POINTER_SNAPSHOT",
                expected_access=FIXTURE_ACCESS,
                expected_source_module=SOURCE_MODULE,
                expected_contract_version=CONTRACT_VERSION,
            )
            prior_snapshots = [
                existing
                for existing in state["records"].values()
                if record_ref(existing) == prior_snapshot_ref
            ]
            if len(prior_snapshots) != 1:
                _fail("B01_REFERENCE_INTEGRITY_FAILED", "operation snapshot")
            prior_payload = prior_snapshots[0]["payload"]
            if (
                prior_payload["snapshot_request_hash"] != request_hash
                or prior_payload["snapshot_operation_id"] != operation_id
                or prior_payload["logical_pointer_key"] != pointer_key
                or prior_payload["current_candidate_version_ref"] != candidate_ref
            ):
                _fail("B01_REFERENCE_INTEGRITY_FAILED", "operation snapshot drift")
            if staged != state:
                _fail("B01_REFERENCE_INTEGRITY_FAILED", "operation replay state")
            return deepcopy(prior_result)
        if pointer_key in state["pointers"]:
            _fail("B01_POINTER_ALREADY_INITIALIZED")
        live_pointer = build_live_pointer(
            project_scope_id=project_scope_id,
            author_workspace_logical_key=author_workspace_logical_key,
            chapter_revision_ref=chapter_revision_ref,
            seg=seg,
            input_binding_hash=extraction_input_binding["input_binding_hash"],
            candidate_ref=candidate_ref,
        )
        snapshot_ref = CandidatePointerSnapshotWriter.stage_initialization(
            staged,
            pointer_record=pointer_record,
            live_pointer=live_pointer,
            all_records=[*reference_records, *staged["records"].values()],
        )
        result = {
            "segment_index_snapshot_ref": segment_ref,
            "candidate_version_ref": candidate_ref,
            "candidate_pointer_snapshot_ref": snapshot_ref,
            "logical_pointer_key": pointer_key,
        }
        staged["operations"][operation_id] = {
            "request_hash": request_hash,
            "result": result,
        }
        if crash_point in {
            "after_records_staged_before_pointer_cas",
            "after_pointer_staged_before_commit",
        }:
            _fail("B01_SIMULATED_CRASH", crash_point)
        self.store.commit(staged)
        if crash_point == "after_commit_before_readback":
            _fail("B01_SIMULATED_CRASH_AFTER_COMMIT", crash_point)
        reopened = self.store.read()
        verify_state(reopened, reference_records=reference_records)
        if canonical_bytes(reopened) != canonical_bytes(staged):
            _fail("B01_TRANSACTION_READBACK_INVALID")
        return result


def _compose_ccz142_b01_runtime(
    store: FixtureStore,
) -> tuple[B01Service, Callable[..., object]]:
    """Split source-signing authority from the ordinary B-01 service surface."""

    seal, open_admission = _new_extraction_admission_channel()
    service = object.__new__(B01Service)
    service.store = store
    service._B01Service__open_extraction_admission = open_admission

    def admit_from_trusted_adapter(**kwargs: Any) -> object:
        return seal(_build_ccz142_extraction_handoff_payload(**kwargs))

    return service, admit_from_trusted_adapter


def state_file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state_counts(path: Path) -> tuple[int, int, int]:
    if not path.exists():
        return (0, 0, 0)
    state = json.loads(path.read_text(encoding="utf-8"))
    return (len(state["records"]), len(state["pointers"]), len(state["operations"]))


def guard_write_path(repository_relative_path: str) -> None:
    if not repository_relative_path.startswith(WRITE_SET_PREFIX):
        _fail("B01_WRITE_SET_ESCAPE", repository_relative_path)


def guard_runtime_event(event: str) -> None:
    if event in FORBIDDEN_RUNTIME_EVENTS:
        _fail("B01_NETWORK_OR_PROCESS_EVENT", event)
