"""CCZ-57 M3 B-04 r03.5 immutable full-item Patch contracts.

This module is fixture-only. It has no model, network, subprocess, dynamic
import, or real-novel access path. B-04 proposes complete candidate-item
changes; it never applies a Patch or creates a child CandidateVersion.
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
    ALLOWED_STATUSES,
    B01ContractError,
    CANDIDATE_SCHEMA_ID as B01_CANDIDATE_SCHEMA_ID,
    CONTRACT_VERSION as B01_CONTRACT_VERSION,
    record_ref as b01_record_ref,
    sentence_count,
    validate_candidate_version as b01_validate_candidate_version,
    validate_evidence_locator as b01_validate_evidence_locator,
    validate_lineage_locator as b01_validate_lineage_locator,
)
from work.ccz57_m3_b02_diagnostic_coverage_r03_5.b02_contracts import (  # noqa: E402
    B02ContractError,
    CANDIDATE_SCHEMA_ID as B02_CANDIDATE_SCHEMA_ID,
    CONTRACT_VERSION as B02_CONTRACT_VERSION,
    validate_coverage_record as b02_validate_coverage_record,
    validate_diagnostic_record as b02_validate_diagnostic_record,
    validate_lifecycle_record as b02_validate_lifecycle_record,
)
from work.ccz57_m3_b03_bound_evidence_read_r03_5.b03_contracts import (  # noqa: E402
    B03ContractError,
    SLICE_PAYLOAD_KEYS as B03_SLICE_PAYLOAD_KEYS,
    record_ref as b03_record_ref,
    validate_record as b03_validate_record,
)

CONTRACT_VERSION = "r03.5-candidate"
CANDIDATE_SCHEMA_ID = "novel-fact-extraction-v2.1"
DOCUMENT_IDENTITY = "CCZ57-M3-B04-R03.5-CANDIDATE"
IMMUTABLE_CONTRACT = "M3_IMMUTABLE_RECORD"
RECORD_REF_CONTRACT = "M3_RECORD_REF"
LINEAGE_LOCATOR_CONTRACT = "M3_LINEAGE_LOCATOR"
EVIDENCE_LOCATOR_CONTRACT = "M3_EVIDENCE_LOCATOR"
SOURCE_MODULE = "M3"
FIXTURE_ACCESS = "POLICY_FIXTURE_READ_ONLY"
RUN_ACCESS = "RUN_INTERNAL_READ_ONLY"
RETENTION_CLASS = "CORE_IMMUTABLE_AUDIT"
WRITE_SET_PREFIX = "work/ccz57_m3_b04_patch_atomic_group_r03_5/"
LEGACY_WRITE_SET_PREFIX = "work/ccz57_m3_b04_patch_atomic_group_r03_4/"

EXPECTED_CURRENT_MAIN = "410596b559ac308f136f82ea2985e34202b2964b"
EXPECTED_B01_MERGE_SHA = "bab092f4914c41e410599a588f55788ae5ff7b7c"
EXPECTED_B02_MERGE_SHA = "6c126a85b97444092955e90be88952617805cf17"
EXPECTED_B03_MERGE_SHA = EXPECTED_CURRENT_MAIN

if (
    CONTRACT_VERSION != B01_CONTRACT_VERSION
    or CONTRACT_VERSION != B02_CONTRACT_VERSION
    or CANDIDATE_SCHEMA_ID != B01_CANDIDATE_SCHEMA_ID
    or CANDIDATE_SCHEMA_ID != B02_CANDIDATE_SCHEMA_ID
):
    raise RuntimeError("B-01/B-02/B-04 r03.5 identity drift")

OUTPUT_TYPES = {
    "M3_CANDIDATE_PROTECTION_SET",
    "M3_PATCH_PROPOSAL",
    "M3_CAUSAL_HINT_PROPOSAL",
}
WRITER_MAP = {
    "M3_CANDIDATE_PROTECTION_SET": "ProtectionSetBuilder",
    "M3_PATCH_PROPOSAL": "PatchRecorder",
    "M3_CAUSAL_HINT_PROPOSAL": "CausalHintProposalRecorder",
}
PROJECTOR_MAP = {"PatchPreview": "PatchPreviewProjector"}
_WRITER_TOKENS = {record_type: object() for record_type in WRITER_MAP}
ALLOWED_ACCESS = {FIXTURE_ACCESS, RUN_ACCESS}
FORBIDDEN_B05_TYPES = {
    "M3_PATCH_VALIDATION_RECEIPT",
    "M3_PATCH_ELIGIBILITY_RECEIPT",
    "M3_PATCH_DECISION",
    "M3_PATCH_LIFECYCLE_RECEIPT",
    "M3_FORMAL_FACT",
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
PROTECTION_PAYLOAD_KEYS = {
    "base_candidate_version_ref",
    "protection_policy_ref",
    "chapter_revision_ref",
    "protected_entries",
}
PROTECTED_ENTRY_KEYS = {
    "lineage_locator",
    "json_pointer",
    "protected_item_hash",
    "reason",
}
PATCH_PAYLOAD_KEYS = {
    "base_candidate_version_ref",
    "candidate_schema_id",
    "diagnostic_refs",
    "coverage_observation_refs",
    "authorized_source_slice_refs",
    "protection_set_ref",
    "chapter_revision_ref",
    "atomic_groups",
    "sidecar_proposal_refs",
}
CAUSAL_PAYLOAD_KEYS = {
    "from_lineage_locator",
    "to_lineage_locator",
    "evidence_locators",
    "coverage_observation_refs",
    "authorized_source_slice_refs",
    "diagnostic_refs",
    "hint_kind",
    "expiry_request_seconds",
    "noncommittable",
    "chapter_revision_ref",
}
GROUP_KEYS = {"atomic_group_id", "purpose", "operations", "group_payload_hash"}
REPLACE_KEYS = {
    "operation_kind",
    "target",
    "expected_old_item_hash",
    "new_item",
    "supporting_diagnostic_refs",
    "supporting_coverage_refs",
}
ADD_KEYS = {
    "operation_kind",
    "target_collection_pointer",
    "new_item",
    "supporting_coverage_refs",
}
NEW_ITEM_REQUIRED_KEYS = {
    "lineage_id",
    "fact",
    "status",
    "evidence",
    "evidence_binding",
}
EVIDENCE_BINDING_KEYS = {
    "chapter_revision_ref",
    "evidence_sha256",
    "sentence_count",
    "match_locations",
    "binding_hash",
}
SOURCE_EVIDENCE_BINDING_KEYS = EVIDENCE_BINDING_KEYS | {"evidence"}


class B04ContractError(ValueError):
    """Stable, machine-readable B-04 contract failure."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def fail(code: str, detail: str = "") -> None:
    raise B04ContractError(code, detail)


_SOURCE_BOUND_STRING_KEYS = {"evidence", "responsibility_text"}


def normalize(value: Any, *, preserve_string_value: bool = False) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        fail("B04_CANONICAL_VALUE_INVALID", "floating-point values are forbidden")
    if isinstance(value, str):
        return value if preserve_string_value else unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [
            normalize(item, preserve_string_value=preserve_string_value)
            for item in value
        ]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                fail("B04_CANONICAL_KEY_INVALID", "object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in result:
                fail("B04_CANONICAL_DUPLICATE_KEY", normalized_key)
            result[normalized_key] = normalize(
                item,
                preserve_string_value=(
                    preserve_string_value or normalized_key in _SOURCE_BOUND_STRING_KEYS
                ),
            )
        return {
            key: result[key]
            for key in sorted(result, key=lambda item: item.encode("utf-8"))
        }
    fail("B04_CANONICAL_VALUE_INVALID", type(value).__name__)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        normalize(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def exact_keys(value: Any, expected: set[str], code: str) -> None:
    if not isinstance(value, dict):
        fail(code, "object required")
    actual = set(value)
    if actual != expected:
        fail(
            code,
            f"missing={sorted(expected - actual)}; extra={sorted(actual - expected)}",
        )


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def is_non_bool_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_utc(value: Any, code: str) -> datetime:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is None
    ):
        fail(code, "UTC RFC3339 timestamp required")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as error:
        fail(code, str(error))


def _same(left: Any, right: Any) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def validate_chapter_revision(value: Any) -> None:
    exact_keys(value, CHAPTER_REVISION_KEYS, "B04_REVISION_SHAPE_INVALID")
    if not isinstance(value["chapter_id"], str) or not value["chapter_id"]:
        fail("B04_REVISION_INVALID", "chapter_id")
    if not is_non_bool_int(value["revision_no"]) or value["revision_no"] < 1:
        fail("B04_REVISION_INVALID", "revision_no")
    if not is_sha256(value["revision_text_sha256"]):
        fail("B04_REVISION_INVALID", "revision_text_sha256")


def validate_record_ref(value: Any, *, expected_type: str | None = None) -> None:
    exact_keys(value, RECORD_REF_KEYS, "B04_RECORD_REF_SHAPE_INVALID")
    if value["contract"] != RECORD_REF_CONTRACT:
        fail("B04_RECORD_REF_INVALID", "contract")
    if value["contract_version"] != CONTRACT_VERSION:
        fail("B04_RECORD_REF_INVALID", "contract_version")
    if value["record_contract_version"] != CONTRACT_VERSION:
        fail("B04_RECORD_REF_INVALID", "record_contract_version")
    if expected_type is not None and value["record_type"] != expected_type:
        fail("B04_RECORD_REF_TYPE_INVALID", str(value["record_type"]))
    if not isinstance(value["record_id"], str) or not value["record_id"]:
        fail("B04_RECORD_REF_INVALID", "record_id")
    if not is_non_bool_int(value["record_version"]) or value["record_version"] < 1:
        fail("B04_RECORD_REF_INVALID", "record_version")
    if not is_sha256(value["record_hash"]):
        fail("B04_RECORD_REF_INVALID", "record_hash")
    if value["access"] not in ALLOWED_ACCESS:
        fail("B04_RECORD_REF_INVALID", "access")
    if not isinstance(value["source_module"], str) or not value["source_module"]:
        fail("B04_RECORD_REF_INVALID", "source_module")


def _stable_refs(
    refs: Any, *, expected_type: str, code: str, allow_empty: bool = True
) -> list[dict[str, Any]]:
    if not isinstance(refs, list) or (not allow_empty and not refs):
        fail(code, "stable reference list required")
    for ref in refs:
        validate_record_ref(ref, expected_type=expected_type)
    stable = sorted(deepcopy(refs), key=canonical_bytes)
    if refs != stable or len({canonical_bytes(ref) for ref in refs}) != len(refs):
        fail(code, "unique canonical order required")
    return stable


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
        fail("B04_WRITER_SCOPE_ESCAPE", record_type)
    if not isinstance(record_id, str) or not record_id:
        fail("B04_OBJECT_INVALID", "record_id")
    parse_utc(created_at, "B04_OBJECT_INVALID")
    if access not in ALLOWED_ACCESS:
        fail("B04_OBJECT_INVALID", "access")
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
    preimage = {key: value for key, value in record.items() if key != "record_hash"}
    record["record_hash"] = sha256_value(preimage)
    return record


def validate_record(record: Any) -> None:
    exact_keys(record, ENVELOPE_KEYS, "B04_IMMUTABLE_SHAPE_INVALID")
    if record["contract"] != IMMUTABLE_CONTRACT:
        fail("B04_IMMUTABLE_INVALID", "contract")
    if record["contract_version"] != CONTRACT_VERSION:
        fail("B04_IMMUTABLE_INVALID", "contract_version")
    if record["record_contract_version"] != CONTRACT_VERSION:
        fail("B04_IMMUTABLE_INVALID", "record_contract_version")
    if not is_non_bool_int(record["record_version"]) or record["record_version"] < 1:
        fail("B04_IMMUTABLE_INVALID", "record_version")
    if not is_sha256(record["record_hash"]):
        fail("B04_IMMUTABLE_INVALID", "record_hash")
    if record["access"] not in ALLOWED_ACCESS:
        fail("B04_IMMUTABLE_INVALID", "access")
    if record["retention_class"] != RETENTION_CLASS:
        fail("B04_IMMUTABLE_INVALID", "retention_class")
    parse_utc(record["created_at"], "B04_IMMUTABLE_INVALID")
    preimage = {key: value for key, value in record.items() if key != "record_hash"}
    if sha256_value(preimage) != record["record_hash"]:
        fail("B04_RECORD_HASH_MISMATCH", str(record["record_id"]))


def validate_external_record(record: dict[str, Any], *, expected_type: str) -> None:
    validate_record(record)
    if record["record_type"] != expected_type:
        fail("B04_UPSTREAM_OBJECT_INVALID", expected_type)


def _b01_failure(error: B01ContractError, detail: str) -> None:
    fail("B04_B01_INPUT_INVALID", f"{detail}:{error.code}")


def _b02_failure(error: B02ContractError, detail: str) -> None:
    fail("B04_B02_INPUT_INVALID", f"{detail}:{error.code}")


def _b03_failure(error: B03ContractError, detail: str) -> None:
    fail("B04_B03_INPUT_INVALID", f"{detail}:{error.code}")


def _candidate_validation_records(context: dict[str, Any]) -> list[dict[str, Any]]:
    return [*context["reference_records"], context["segment_index"]]


def validate_upstream_context(context: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "reference_records",
        "segment_index",
        "candidate_version",
        "lineage_locators",
        "evidence_locators",
        "segment_inputs",
    }
    exact_keys(context, expected, "B04_UPSTREAM_CONTEXT_INVALID")
    base = context["candidate_version"]
    try:
        b01_validate_candidate_version(
            base,
            allow_child=True,
            reference_records=_candidate_validation_records(context),
        )
        for locator in context["lineage_locators"]:
            b01_validate_lineage_locator(
                locator,
                candidate_version=base,
                reference_records=_candidate_validation_records(context),
            )
        for locator in context["evidence_locators"]:
            b01_validate_evidence_locator(
                locator,
                candidate_version=base,
                reference_records=_candidate_validation_records(context),
            )
    except B01ContractError as error:
        _b01_failure(error, "context")
    if base["payload"]["candidate_schema_id"] != CANDIDATE_SCHEMA_ID:
        fail("B04_CANDIDATE_SCHEMA_MISMATCH")
    return base


def validate_lineage_locator(
    locator: dict[str, Any], *, context: dict[str, Any]
) -> dict[str, Any]:
    base = context["candidate_version"]
    try:
        b01_validate_lineage_locator(
            locator,
            candidate_version=base,
            reference_records=_candidate_validation_records(context),
        )
    except B01ContractError as error:
        _b01_failure(error, "lineage locator")
    matches = [
        item
        for item in base["payload"]["items"]
        if item["lineage_id"] == locator["lineage_id"]
    ]
    if len(matches) != 1:
        fail("B04_LINEAGE_LOCATOR_INVALID", "target")
    return matches[0]


def validate_evidence_locator(
    locator: dict[str, Any], *, context: dict[str, Any]
) -> None:
    try:
        b01_validate_evidence_locator(
            locator,
            candidate_version=context["candidate_version"],
            reference_records=_candidate_validation_records(context),
        )
    except B01ContractError as error:
        _b01_failure(error, "evidence locator")


def validate_upstream_inputs(
    *,
    context: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    coverages: list[dict[str, Any]],
    lifecycle_receipts: list[dict[str, Any]],
    upstream_records: list[dict[str, Any]],
) -> None:
    base = validate_upstream_context(context)
    if not isinstance(diagnostics, list) or not isinstance(coverages, list):
        fail("B04_UPSTREAM_COLLECTION_INVALID")
    if not diagnostics and not coverages:
        fail("B04_PATCH_EVIDENCE_REQUIRED")
    all_records = upstream_records
    authoritative_by_ref = {
        canonical_bytes(record_ref(record)): record for record in all_records
    }
    for selected in [*diagnostics, *coverages]:
        authoritative = authoritative_by_ref.get(canonical_bytes(record_ref(selected)))
        if authoritative is None or canonical_bytes(authoritative) != canonical_bytes(
            selected
        ):
            fail("B04_B02_CURRENT_STATE_MISMATCH")
    authoritative_lifecycle = sorted(
        [
            record
            for record in all_records
            if record["record_type"] == "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT"
        ],
        key=lambda record: canonical_bytes(record_ref(record)),
    )
    if (
        sorted(
            lifecycle_receipts, key=lambda record: canonical_bytes(record_ref(record))
        )
        != authoritative_lifecycle
    ):
        fail("B04_B02_CURRENT_STATE_MISMATCH", "lifecycle snapshot")
    for diagnostic in diagnostics:
        try:
            b02_validate_diagnostic_record(
                diagnostic, context=context, records=all_records
            )
        except B02ContractError as error:
            _b02_failure(error, "diagnostic")
        if diagnostic["payload"]["base_candidate_version_ref"] != b01_record_ref(base):
            fail("B04_DIAGNOSTIC_BASE_MISMATCH")
    for coverage in coverages:
        try:
            b02_validate_coverage_record(coverage, context=context, records=all_records)
        except B02ContractError as error:
            _b02_failure(error, "coverage")
        if coverage["payload"]["base_candidate_version_ref"] != b01_record_ref(base):
            fail("B04_COVERAGE_BASE_MISMATCH")
    for lifecycle in lifecycle_receipts:
        try:
            b02_validate_lifecycle_record(lifecycle, records=all_records)
        except B02ContractError as error:
            _b02_failure(error, "lifecycle")


def _binding_from_coverage(coverage: dict[str, Any]) -> dict[str, Any]:
    source = coverage["payload"]["source_evidence_binding"]
    exact_keys(source, SOURCE_EVIDENCE_BINDING_KEYS, "B04_COVERAGE_BINDING_INVALID")
    without_hash = {
        "chapter_revision_ref": deepcopy(source["chapter_revision_ref"]),
        "evidence_sha256": source["evidence_sha256"],
        "sentence_count": source["sentence_count"],
        "match_locations": deepcopy(source["match_locations"]),
    }
    return {**without_hash, "binding_hash": sha256_value(without_hash)}


def validate_new_item(
    item: Any, *, context: dict[str, Any], code: str = "B04_NEW_ITEM_INVALID"
) -> None:
    if not isinstance(item, dict):
        fail(code, "object required")
    expected = set(NEW_ITEM_REQUIRED_KEYS)
    if "speaker" in item:
        expected.add("speaker")
    exact_keys(item, expected, code)
    if not isinstance(item["lineage_id"], str) or not item["lineage_id"].startswith(
        "lin_"
    ):
        fail(code, "lineage_id")
    if not isinstance(item["fact"], str) or not item["fact"]:
        fail(code, "fact")
    if item["status"] not in ALLOWED_STATUSES:
        fail(code, "status")
    if not isinstance(item["evidence"], str) or not item["evidence"]:
        fail(code, "evidence")
    if "speaker" in item and (
        not isinstance(item["speaker"], str) or not item["speaker"]
    ):
        fail(code, "speaker")
    if normalize(item) != item:
        fail(code, "NFC")
    binding = item["evidence_binding"]
    exact_keys(binding, EVIDENCE_BINDING_KEYS, "B04_EVIDENCE_BINDING_INVALID")
    revision = context["candidate_version"]["payload"]["chapter_revision_ref"]
    if binding["chapter_revision_ref"] != revision:
        fail("B04_EVIDENCE_BINDING_INVALID", "chapter revision")
    if (
        binding["evidence_sha256"]
        != hashlib.sha256(item["evidence"].encode("utf-8")).hexdigest()
    ):
        fail("B04_EVIDENCE_BINDING_INVALID", "evidence hash")
    count = sentence_count(item["evidence"])
    if binding["sentence_count"] != count or count not in {1, 2}:
        fail("B04_EVIDENCE_BINDING_INVALID", "sentence count")
    locations = binding["match_locations"]
    if not isinstance(locations, list) or not locations:
        fail("B04_EVIDENCE_BINDING_INVALID", "match locations")
    stable_locations = sorted(
        locations,
        key=lambda location: (
            location.get("seg"),
            location.get("start_byte"),
            location.get("end_byte"),
        ),
    )
    if locations != stable_locations or len(
        {canonical_bytes(location) for location in locations}
    ) != len(locations):
        fail("B04_EVIDENCE_BINDING_INVALID", "location order")
    seg = context["candidate_version"]["payload"]["seg"]
    selected = context["segment_index"]["payload"]["segments"][seg - 1]
    for location in locations:
        exact_keys(
            location,
            {"seg", "start_byte", "end_byte"},
            "B04_EVIDENCE_BINDING_INVALID",
        )
        if (
            location["seg"] != seg
            or not is_non_bool_int(location["start_byte"])
            or not is_non_bool_int(location["end_byte"])
            or location["start_byte"] < selected["start_byte"]
            or location["end_byte"] > selected["end_byte"]
            or location["start_byte"] >= location["end_byte"]
        ):
            fail("B04_EVIDENCE_BINDING_INVALID", "location range")
    binding_preimage = {
        key: value for key, value in binding.items() if key != "binding_hash"
    }
    if binding["binding_hash"] != sha256_value(binding_preimage):
        fail("B04_EVIDENCE_BINDING_INVALID", "binding hash")


def _ref_key(ref: dict[str, Any]) -> bytes:
    return canonical_bytes(ref)


def _records_by_ref(records: list[dict[str, Any]]) -> dict[bytes, dict[str, Any]]:
    return {_ref_key(record_ref(record)): record for record in records}


def _validate_ref_subset(
    refs: list[dict[str, Any]],
    *,
    allowed: dict[bytes, dict[str, Any]],
    expected_type: str,
    code: str,
    allow_empty: bool,
) -> list[dict[str, Any]]:
    _stable_refs(refs, expected_type=expected_type, code=code, allow_empty=allow_empty)
    for ref in refs:
        if _ref_key(ref) not in allowed:
            fail(code, "reference is not a top-level input")
    return refs


def _coverage_supports_item(coverage: dict[str, Any], item: dict[str, Any]) -> bool:
    source = coverage["payload"]["source_evidence_binding"]
    return (
        source["evidence"] == item["evidence"]
        and _binding_from_coverage(coverage) == item["evidence_binding"]
    )


def proposed_add_lineage_id(
    *,
    base_candidate_version_ref: dict[str, Any],
    supporting_coverage_refs: list[dict[str, Any]],
    atomic_group_id: str,
    group_operation_ordinal: int,
    item: dict[str, Any],
) -> str:
    seed = {
        "base_candidate_version_ref": deepcopy(base_candidate_version_ref),
        "supporting_coverage_refs": deepcopy(supporting_coverage_refs),
        "atomic_group_id": atomic_group_id,
        "group_operation_ordinal": group_operation_ordinal,
        "fact": item["fact"],
        "status": item["status"],
        "evidence": item["evidence"],
        "evidence_binding_hash": item["evidence_binding"]["binding_hash"],
    }
    if "speaker" in item:
        seed["speaker_if_present"] = item["speaker"]
    return f"lin_{sha256_value(seed)}"


def operation_write_target(operation: dict[str, Any]) -> str:
    kind = operation.get("operation_kind")
    if kind == "REPLACE_CANDIDATE_ITEM":
        return str(operation.get("target", {}).get("json_pointer", ""))
    if kind == "ADD_CANDIDATE_ITEM":
        return f"/items/@{operation.get('new_item', {}).get('lineage_id', '')}"
    if kind in {"REPLACE_FIELD", "ADD_CAUSAL_HINT"}:
        fail("B04_LEGACY_OR_COMMITTABLE_OPERATION_FORBIDDEN", str(kind))
    fail("B04_OPERATION_KIND_INVALID", str(kind))


def _pointer_overlap(left: str, right: str) -> bool:
    normalized_left = left.rstrip("/")
    normalized_right = right.rstrip("/")
    return (
        normalized_left == normalized_right
        or normalized_left.startswith(normalized_right + "/")
        or normalized_right.startswith(normalized_left + "/")
    )


def _old_item_without_hash(item: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in item.items() if key != "item_hash"}


def validate_operation(
    operation: Any,
    *,
    context: dict[str, Any],
    diagnostic_by_ref: dict[bytes, dict[str, Any]],
    coverage_by_ref: dict[bytes, dict[str, Any]],
    terminal_diagnostic_refs: set[bytes],
    atomic_group_id: str,
    group_operation_ordinal: int,
) -> tuple[set[bytes], set[bytes]]:
    if not isinstance(operation, dict):
        fail("B04_OPERATION_SHAPE_INVALID", "object required")
    kind = operation.get("operation_kind")
    if kind in {"REPLACE_FIELD", "ADD_CAUSAL_HINT"}:
        fail("B04_LEGACY_OR_COMMITTABLE_OPERATION_FORBIDDEN", str(kind))
    if kind == "REPLACE_CANDIDATE_ITEM":
        exact_keys(operation, REPLACE_KEYS, "B04_REPLACE_SHAPE_INVALID")
        old_item = validate_lineage_locator(operation["target"], context=context)
        if operation["expected_old_item_hash"] != old_item["item_hash"]:
            fail("B04_REPLACE_OLD_ITEM_HASH_MISMATCH")
        new_item = operation["new_item"]
        validate_new_item(new_item, context=context)
        if new_item["lineage_id"] != operation["target"]["lineage_id"]:
            fail("B04_REPLACE_LINEAGE_MISMATCH")
        if _same(new_item, _old_item_without_hash(old_item)):
            fail("B04_REPLACE_NO_OP")
        diagnostic_refs = _validate_ref_subset(
            operation["supporting_diagnostic_refs"],
            allowed=diagnostic_by_ref,
            expected_type="M3_DIAGNOSTIC",
            code="B04_REPLACE_DIAGNOSTIC_INVALID",
            allow_empty=False,
        )
        for ref in diagnostic_refs:
            key = _ref_key(ref)
            diagnostic = diagnostic_by_ref[key]
            if key in terminal_diagnostic_refs:
                fail("B04_REPLACE_DIAGNOSTIC_NOT_OPEN")
            target = diagnostic["payload"]["target"]["lineage_locator"]
            if target != operation["target"]:
                fail("B04_REPLACE_DIAGNOSTIC_TARGET_MISMATCH")
        coverage_refs = _validate_ref_subset(
            operation["supporting_coverage_refs"],
            allowed=coverage_by_ref,
            expected_type="M3_COVERAGE_OBSERVATION",
            code="B04_REPLACE_COVERAGE_INVALID",
            allow_empty=True,
        )
        evidence_changed = (
            new_item["evidence"] != old_item["evidence"]
            or new_item["evidence_binding"] != old_item["evidence_binding"]
        )
        if evidence_changed and not coverage_refs:
            fail("B04_REPLACE_COVERAGE_REQUIRED")
        for ref in coverage_refs:
            coverage = coverage_by_ref[_ref_key(ref)]
            if coverage["payload"]["candidate_match"] not in {"MISSING", "PARTIAL"}:
                fail("B04_REPLACE_COVERAGE_MATCH_INVALID")
            if not _coverage_supports_item(coverage, new_item):
                fail("B04_REPLACE_COVERAGE_BINDING_MISMATCH")
        return (
            {_ref_key(ref) for ref in diagnostic_refs},
            {_ref_key(ref) for ref in coverage_refs},
        )
    if kind == "ADD_CANDIDATE_ITEM":
        exact_keys(operation, ADD_KEYS, "B04_ADD_SHAPE_INVALID")
        if operation["target_collection_pointer"] != "/items":
            fail("B04_ADD_TARGET_INVALID")
        new_item = operation["new_item"]
        validate_new_item(new_item, context=context)
        base_lineages = {
            item["lineage_id"]
            for item in context["candidate_version"]["payload"]["items"]
        }
        if new_item["lineage_id"] in base_lineages:
            fail("B04_ADD_LINEAGE_DUPLICATE")
        coverage_refs = _validate_ref_subset(
            operation["supporting_coverage_refs"],
            allowed=coverage_by_ref,
            expected_type="M3_COVERAGE_OBSERVATION",
            code="B04_ADD_COVERAGE_INVALID",
            allow_empty=False,
        )
        for ref in coverage_refs:
            coverage = coverage_by_ref[_ref_key(ref)]
            if coverage["payload"]["candidate_match"] not in {"MISSING", "PARTIAL"}:
                fail("B04_ADD_COVERAGE_MATCH_INVALID")
            if not _coverage_supports_item(coverage, new_item):
                fail("B04_ADD_COVERAGE_BINDING_MISMATCH")
        expected_lineage = proposed_add_lineage_id(
            base_candidate_version_ref=b01_record_ref(context["candidate_version"]),
            supporting_coverage_refs=coverage_refs,
            atomic_group_id=atomic_group_id,
            group_operation_ordinal=group_operation_ordinal,
            item=new_item,
        )
        if new_item["lineage_id"] != expected_lineage:
            fail("B04_ADD_LINEAGE_ID_MISMATCH")
        return set(), {_ref_key(ref) for ref in coverage_refs}
    fail("B04_OPERATION_KIND_INVALID", str(kind))


def validate_atomic_groups(
    groups: Any,
    *,
    context: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    coverages: list[dict[str, Any]],
    lifecycle_receipts: list[dict[str, Any]],
) -> tuple[set[bytes], set[bytes]]:
    if not isinstance(groups, list) or not groups:
        fail("B04_ATOMIC_GROUPS_INVALID", "non-empty array required")
    diagnostic_by_ref = _records_by_ref(diagnostics)
    coverage_by_ref = _records_by_ref(coverages)
    terminal_diagnostic_refs = {
        _ref_key(item["payload"]["diagnostic_ref"])
        for item in lifecycle_receipts
        if item.get("record_type") == "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT"
    }
    group_ids: set[str] = set()
    operation_fingerprints: set[str] = set()
    writes_by_group: list[list[str]] = []
    added_lineages: set[str] = set()
    used_diagnostics: set[bytes] = set()
    used_coverages: set[bytes] = set()
    for group in groups:
        exact_keys(group, GROUP_KEYS, "B04_ATOMIC_GROUP_SHAPE_INVALID")
        group_id = group["atomic_group_id"]
        if not isinstance(group_id, str) or not group_id or group_id in group_ids:
            fail("B04_ATOMIC_GROUP_ID_INVALID", str(group_id))
        group_ids.add(group_id)
        if not isinstance(group["purpose"], str) or not group["purpose"]:
            fail("B04_ATOMIC_GROUP_PURPOSE_INVALID")
        operations = group["operations"]
        if not isinstance(operations, list) or not operations:
            fail("B04_ATOMIC_GROUP_EMPTY")
        group_preimage = {
            key: value for key, value in group.items() if key != "group_payload_hash"
        }
        if sha256_value(group_preimage) != group["group_payload_hash"]:
            fail("B04_ATOMIC_GROUP_HASH_MISMATCH", group_id)
        group_writes: list[str] = []
        for group_operation_ordinal, operation in enumerate(operations):
            diagnostic_keys, coverage_keys = validate_operation(
                operation,
                context=context,
                diagnostic_by_ref=diagnostic_by_ref,
                coverage_by_ref=coverage_by_ref,
                terminal_diagnostic_refs=terminal_diagnostic_refs,
                atomic_group_id=group_id,
                group_operation_ordinal=group_operation_ordinal,
            )
            used_diagnostics.update(diagnostic_keys)
            used_coverages.update(coverage_keys)
            fingerprint = sha256_value(operation)
            if fingerprint in operation_fingerprints:
                fail("B04_OPERATION_DUPLICATE")
            operation_fingerprints.add(fingerprint)
            target = operation_write_target(operation)
            if any(_pointer_overlap(target, prior) for prior in group_writes):
                fail("B04_GROUP_TARGET_OVERLAP")
            group_writes.append(target)
            if operation["operation_kind"] == "ADD_CANDIDATE_ITEM":
                lineage = operation["new_item"]["lineage_id"]
                if lineage in added_lineages:
                    fail("B04_ADD_LINEAGE_DUPLICATE")
                added_lineages.add(lineage)
        writes_by_group.append(group_writes)
    for left_index, left in enumerate(writes_by_group):
        for right in writes_by_group[left_index + 1 :]:
            if any(_pointer_overlap(a, b) for a in left for b in right):
                fail("B04_CROSS_GROUP_TARGET_OVERLAP")
    return used_diagnostics, used_coverages


def expected_protected_entries(
    *, context: dict[str, Any], groups: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    base = context["candidate_version"]
    replace_paths = {
        operation["target"]["json_pointer"]
        for group in groups
        for operation in group["operations"]
        if operation["operation_kind"] == "REPLACE_CANDIDATE_ITEM"
    }
    locator_by_path = {
        locator["json_pointer"]: locator for locator in context["lineage_locators"]
    }
    result: list[dict[str, Any]] = []
    for index, item in enumerate(base["payload"]["items"]):
        item_path = f"/items/{index}"
        if item_path in replace_paths:
            continue
        locator = locator_by_path.get(item_path)
        if locator is None:
            fail("B04_BASE_LINEAGE_INDEX_INVALID", item_path)
        result.append(
            {
                "lineage_locator": deepcopy(locator),
                "json_pointer": item_path,
                "protected_item_hash": item["item_hash"],
                "reason": "UNTOUCHED_BY_THIS_PATCH_PROTECTED",
            }
        )
    return result


def validate_protection_record(
    record: dict[str, Any],
    *,
    context: dict[str, Any],
    policy: dict[str, Any],
    groups: list[dict[str, Any]],
) -> None:
    base = context["candidate_version"]
    validate_output_record(record)
    if record["record_type"] != "M3_CANDIDATE_PROTECTION_SET":
        fail("B04_PROTECTION_SET_INVALID", "record_type")
    payload = record["payload"]
    exact_keys(payload, PROTECTION_PAYLOAD_KEYS, "B04_PROTECTION_PAYLOAD_INVALID")
    validate_external_record(policy, expected_type="M3_PROTECTION_POLICY")
    exact_keys(
        policy["payload"],
        {"policy_revision", "protect_untouched_items", "protect_accepted_lineage"},
        "B04_PROTECTION_POLICY_INVALID",
    )
    if (
        policy["payload"]["protect_untouched_items"] is not True
        or policy["payload"]["protect_accepted_lineage"] is not True
    ):
        fail("B04_PROTECTION_POLICY_INVALID", "disabled")
    if payload["base_candidate_version_ref"] != b01_record_ref(base):
        fail("B04_PROTECTION_SET_INVALID", "base")
    if payload["protection_policy_ref"] != record_ref(policy):
        fail("B04_PROTECTION_SET_INVALID", "policy")
    if payload["chapter_revision_ref"] != base["payload"]["chapter_revision_ref"]:
        fail("B04_PROTECTION_SET_INVALID", "revision")
    expected = expected_protected_entries(context=context, groups=groups)
    if payload["protected_entries"] != expected:
        fail("B04_PROTECTION_COMPLEMENT_MISMATCH")
    for entry in payload["protected_entries"]:
        exact_keys(entry, PROTECTED_ENTRY_KEYS, "B04_PROTECTED_ENTRY_INVALID")
        item = validate_lineage_locator(entry["lineage_locator"], context=context)
        if (
            entry["json_pointer"] != entry["lineage_locator"]["json_pointer"]
            or entry["protected_item_hash"] != item["item_hash"]
        ):
            fail("B04_PROTECTED_ENTRY_INVALID", "target")


def validate_source_slice_records(
    records: list[dict[str, Any]],
    *,
    context: dict[str, Any],
    groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        fail("B04_SOURCE_SLICE_INPUT_INVALID", "record list required")
    try:
        refs = sorted(
            [b03_record_ref(record) for record in records], key=canonical_bytes
        )
    except B03ContractError as error:
        _b03_failure(error, "source slice ref")
    _stable_refs(
        refs,
        expected_type="M3_AUTHORIZED_SOURCE_SLICE",
        code="B04_SOURCE_SLICE_REFS_INVALID",
        allow_empty=True,
    )
    if not records:
        return refs
    operations = [
        operation for group in groups for operation in group.get("operations", [])
    ]
    if len(operations) != 1 or operations[0].get("operation_kind") != (
        "REPLACE_CANDIDATE_ITEM"
    ):
        fail("B04_SOURCE_SLICE_SCOPE_INVALID", "one replacement required")
    operation = operations[0]
    old_item = validate_lineage_locator(operation["target"], context=context)
    if (
        operation["new_item"]["evidence"] != old_item["evidence"]
        or operation["new_item"]["evidence_binding"] != old_item["evidence_binding"]
    ):
        fail("B04_SOURCE_SLICE_SCOPE_INVALID", "old evidence only")
    if len(records) != 1:
        fail("B04_SOURCE_SLICE_SCOPE_INVALID", "one exact recheck record required")
    record = records[0]
    try:
        b03_validate_record(record)
    except B03ContractError as error:
        _b03_failure(error, "source slice")
    if record["record_type"] != "M3_AUTHORIZED_SOURCE_SLICE":
        fail("B04_SOURCE_SLICE_INPUT_INVALID", "record type")
    exact_keys(
        record["payload"],
        B03_SLICE_PAYLOAD_KEYS,
        "B04_SOURCE_SLICE_INPUT_INVALID",
    )
    payload = record["payload"]
    subject = payload["subject"]
    if (
        subject["candidate_version_ref"]
        != b01_record_ref(context["candidate_version"])
        or subject["lineage_locator"] != operation["target"]
        or subject["evidence_locator"]["lineage_id"] != old_item["lineage_id"]
        or subject["item_hash"] != old_item["item_hash"]
        or payload["evidence_binding"] != old_item["evidence_binding"]
    ):
        fail("B04_SOURCE_SLICE_SCOPE_INVALID", "subject or evidence drift")
    return refs


def validate_causal_record(
    record: dict[str, Any],
    *,
    context: dict[str, Any],
    diagnostic_refs: list[dict[str, Any]],
    coverage_refs: list[dict[str, Any]],
    source_slice_refs: list[dict[str, Any]],
) -> None:
    validate_output_record(record)
    if record["record_type"] != "M3_CAUSAL_HINT_PROPOSAL":
        fail("B04_CAUSAL_INVALID", "record_type")
    payload = record["payload"]
    exact_keys(payload, CAUSAL_PAYLOAD_KEYS, "B04_CAUSAL_PAYLOAD_INVALID")
    validate_lineage_locator(payload["from_lineage_locator"], context=context)
    validate_lineage_locator(payload["to_lineage_locator"], context=context)
    if payload["noncommittable"] is not True:
        fail("B04_CAUSAL_MUST_BE_NONCOMMITTABLE")
    if not isinstance(payload["hint_kind"], str) or not payload["hint_kind"]:
        fail("B04_CAUSAL_INVALID", "hint_kind")
    if (
        not is_non_bool_int(payload["expiry_request_seconds"])
        or payload["expiry_request_seconds"] <= 0
    ):
        fail("B04_CAUSAL_INVALID", "expiry")
    if (
        payload["chapter_revision_ref"]
        != context["candidate_version"]["payload"]["chapter_revision_ref"]
    ):
        fail("B04_CAUSAL_REVISION_MISMATCH")
    _validate_ref_subset(
        payload["diagnostic_refs"],
        allowed={_ref_key(ref): {} for ref in diagnostic_refs},
        expected_type="M3_DIAGNOSTIC",
        code="B04_CAUSAL_DIAGNOSTIC_REF_INVALID",
        allow_empty=True,
    )
    _validate_ref_subset(
        payload["coverage_observation_refs"],
        allowed={_ref_key(ref): {} for ref in coverage_refs},
        expected_type="M3_COVERAGE_OBSERVATION",
        code="B04_CAUSAL_COVERAGE_REF_INVALID",
        allow_empty=True,
    )
    _validate_ref_subset(
        payload["authorized_source_slice_refs"],
        allowed={_ref_key(ref): {} for ref in source_slice_refs},
        expected_type="M3_AUTHORIZED_SOURCE_SLICE",
        code="B04_CAUSAL_SOURCE_SLICE_REF_INVALID",
        allow_empty=True,
    )
    if not payload["diagnostic_refs"] and not payload["coverage_observation_refs"]:
        fail("B04_CAUSAL_SUPPORT_REQUIRED")
    evidence_locators = payload["evidence_locators"]
    if not isinstance(evidence_locators, list) or not evidence_locators:
        fail("B04_CAUSAL_EVIDENCE_LOCATOR_INVALID", "non-empty list required")
    if evidence_locators != sorted(evidence_locators, key=canonical_bytes) or len(
        {canonical_bytes(locator) for locator in evidence_locators}
    ) != len(evidence_locators):
        fail("B04_CAUSAL_EVIDENCE_LOCATOR_INVALID", "unique canonical order required")
    for locator in payload["evidence_locators"]:
        validate_evidence_locator(locator, context=context)


def validate_patch_record(
    record: dict[str, Any],
    *,
    context: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    coverages: list[dict[str, Any]],
    lifecycle_receipts: list[dict[str, Any]],
    source_slice_records: list[dict[str, Any]],
    protection: dict[str, Any],
    causal_records: list[dict[str, Any]],
) -> None:
    base = context["candidate_version"]
    validate_output_record(record)
    if record["record_type"] != "M3_PATCH_PROPOSAL":
        fail("B04_PATCH_INVALID", "record_type")
    payload = record["payload"]
    exact_keys(payload, PATCH_PAYLOAD_KEYS, "B04_PATCH_PAYLOAD_INVALID")
    if payload["base_candidate_version_ref"] != b01_record_ref(base):
        fail("B04_PATCH_BASE_MISMATCH")
    if payload["candidate_schema_id"] != CANDIDATE_SCHEMA_ID:
        fail("B04_CANDIDATE_SCHEMA_MISMATCH")
    if payload["chapter_revision_ref"] != base["payload"]["chapter_revision_ref"]:
        fail("B04_PATCH_REVISION_MISMATCH")
    diagnostic_refs = [record_ref(item) for item in diagnostics]
    coverage_refs = [record_ref(item) for item in coverages]
    _stable_refs(
        payload["diagnostic_refs"],
        expected_type="M3_DIAGNOSTIC",
        code="B04_PATCH_DIAGNOSTIC_REF_INVALID",
        allow_empty=True,
    )
    _stable_refs(
        payload["coverage_observation_refs"],
        expected_type="M3_COVERAGE_OBSERVATION",
        code="B04_PATCH_COVERAGE_REF_INVALID",
        allow_empty=True,
    )
    if payload["diagnostic_refs"] != diagnostic_refs:
        fail("B04_PATCH_DIAGNOSTIC_REF_INVALID", "top-level refs")
    if payload["coverage_observation_refs"] != coverage_refs:
        fail("B04_PATCH_COVERAGE_REF_INVALID", "top-level refs")
    if not diagnostic_refs and not coverage_refs:
        fail("B04_PATCH_EVIDENCE_REQUIRED")
    source_slice_refs = validate_source_slice_records(
        source_slice_records,
        context=context,
        groups=payload["atomic_groups"],
    )
    if payload["authorized_source_slice_refs"] != source_slice_refs:
        fail("B04_SOURCE_SLICE_REFS_INVALID", "top-level refs")
    if payload["protection_set_ref"] != record_ref(protection):
        fail("B04_PATCH_PROTECTION_REF_INVALID")
    used_diagnostics, used_coverages = validate_atomic_groups(
        payload["atomic_groups"],
        context=context,
        diagnostics=diagnostics,
        coverages=coverages,
        lifecycle_receipts=lifecycle_receipts,
    )
    if used_diagnostics != {_ref_key(ref) for ref in diagnostic_refs}:
        fail("B04_UNUSED_OR_MISSING_DIAGNOSTIC_REF")
    if used_coverages != {_ref_key(ref) for ref in coverage_refs}:
        fail("B04_UNUSED_OR_MISSING_COVERAGE_REF")
    protected_paths = {
        entry["json_pointer"] for entry in protection["payload"]["protected_entries"]
    }
    for group in payload["atomic_groups"]:
        for operation in group["operations"]:
            target = operation_write_target(operation)
            if any(
                _pointer_overlap(target, protected) for protected in protected_paths
            ):
                fail("B04_PROTECTED_TARGET_OVERLAP")
    causal_by_ref = _records_by_ref(causal_records)
    _stable_refs(
        payload["sidecar_proposal_refs"],
        expected_type="M3_CAUSAL_HINT_PROPOSAL",
        code="B04_SIDECAR_REF_INVALID",
        allow_empty=True,
    )
    if set(causal_by_ref) != {
        _ref_key(ref) for ref in payload["sidecar_proposal_refs"]
    }:
        fail("B04_SIDECAR_REF_INVALID", "top-level refs")
    for ref in payload["sidecar_proposal_refs"]:
        validate_causal_record(
            causal_by_ref[_ref_key(ref)],
            context=context,
            diagnostic_refs=diagnostic_refs,
            coverage_refs=coverage_refs,
            source_slice_refs=payload["authorized_source_slice_refs"],
        )


def validate_output_record(record: dict[str, Any]) -> None:
    validate_record(record)
    if record["record_type"] not in OUTPUT_TYPES:
        fail("B04_OUTPUT_TYPE_INVALID", str(record["record_type"]))


def validate_construction_gate(
    *, current_main_sha: str, b01_merge_sha: str, b02_merge_sha: str
) -> None:
    if current_main_sha != EXPECTED_CURRENT_MAIN:
        fail("B04_CURRENT_MAIN_DRIFT", current_main_sha)
    if b01_merge_sha != EXPECTED_B01_MERGE_SHA:
        fail("B04_B01_MERGE_DRIFT", b01_merge_sha)
    if b02_merge_sha != EXPECTED_B02_MERGE_SHA:
        fail("B04_B02_MERGE_DRIFT", b02_merge_sha)


def reference_cycle_count(records: list[dict[str, Any]]) -> int:
    identities = {
        (record["record_type"], record["record_id"], record["record_version"]): record
        for record in records
    }
    graph: dict[tuple[str, str, int], set[tuple[str, str, int]]] = {
        key: set() for key in identities
    }

    def visit(value: Any, owner: tuple[str, str, int]) -> None:
        if isinstance(value, dict):
            if set(value) == RECORD_REF_KEYS:
                target = (
                    value["record_type"],
                    value["record_id"],
                    value["record_version"],
                )
                if target in identities:
                    graph[owner].add(target)
            for nested in value.values():
                visit(nested, owner)
        elif isinstance(value, list):
            for nested in value:
                visit(nested, owner)

    for identity, record in identities.items():
        visit(record["payload"], identity)
    visiting: set[tuple[str, str, int]] = set()
    visited: set[tuple[str, str, int]] = set()
    cycles = 0

    def walk(node: tuple[str, str, int]) -> None:
        nonlocal cycles
        if node in visiting:
            cycles += 1
            return
        if node in visited:
            return
        visiting.add(node)
        for target in graph[node]:
            walk(target)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        walk(node)
    return cycles


def guard_write_path(repository_relative_path: str) -> None:
    if not repository_relative_path.startswith(WRITE_SET_PREFIX):
        fail("B04_WRITE_SET_ESCAPE", repository_relative_path)


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
    "patch_apply",
    "candidate_version_write",
    "formal_fact_write",
}


def guard_runtime_event(event: str) -> None:
    if event in FORBIDDEN_RUNTIME_EVENTS:
        fail("B04_FORBIDDEN_RUNTIME_EVENT", event)
