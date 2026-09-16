"""B-06 minimal commit receipt and mutable pointer validation."""

from __future__ import annotations

import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    CANDIDATE_SCHEMA_ID,
    CONTRACT_VERSION,
    CandidateAuthorityProfile,
    authority_profile_for_pointer,
    LIVE_POINTER_KEYS,
    SOURCE_MODULE,
    pointer_logical_key,
    require_authority_profile,
    validate_candidate_version,
)
from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    IMMUTABLE_CONTRACT,
    RETENTION_CLASS,
    canonical_bytes,
    record_ref,
    sha256_value,
    validate_record_ref,
)

MERGE_RECEIPT_TYPE = "M3_CANDIDATE_MERGE_RECEIPT"
RECEIPT_ACCESS = "RUN_INTERNAL_READ_ONLY"
RECEIPT_KEYS = {
    "operation_id",
    "request_hash",
    "route_receipt_ref",
    "validation_receipt_ref",
    "route_unit_id",
    "atomic_group_bindings",
    "patch_proposal_ref",
    "protection_set_ref",
    "base_candidate_version_ref",
    "child_candidate_version_ref",
    "pointer_logical_key",
    "pointer_generation_before",
    "pointer_generation_after",
    "pointer_binding_hash_before",
    "pointer_binding_hash_after",
    "canonical_apply_result_hash",
    "committed_at",
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


class B06ContractError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def fail(code: str, detail: str = "") -> None:
    raise B06ContractError(code, detail)


def _exact_keys(value: Any, expected: set[str], code: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        fail(code)


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_mutable_pointer(
    pointer: dict[str, Any],
    *,
    candidate: dict[str, Any],
    reference_records: list[dict[str, Any]],
    authority_profile: CandidateAuthorityProfile | None = None,
) -> None:
    _exact_keys(pointer, LIVE_POINTER_KEYS, "B06_POINTER_SHAPE_INVALID")
    try:
        profile = (
            authority_profile_for_pointer(pointer)
            if authority_profile is None
            else require_authority_profile(authority_profile)
        )
    except ValueError as error:
        fail("B06_POINTER_SCOPE_INVALID", str(error))
    if (
        pointer["pointer_namespace"] != profile.pointer_namespace
        or pointer["candidate_schema_id"] != CANDIDATE_SCHEMA_ID
        or not isinstance(pointer["generation"], int)
        or isinstance(pointer["generation"], bool)
        or pointer["generation"] < 1
    ):
        fail("B06_POINTER_SCOPE_INVALID")
    try:
        validate_candidate_version(
            candidate,
            allow_child=candidate["payload"]["parent_candidate_version_ref"]
            is not None,
            reference_records=reference_records,
            authority_profile=profile,
        )
    except (KeyError, ValueError) as error:
        fail("B06_POINTER_CANDIDATE_INVALID", str(error))
    payload = candidate["payload"]
    if (
        canonical_bytes(pointer["current_candidate_version_ref"])
        != canonical_bytes(record_ref(candidate))
        or pointer["chapter_revision_ref"] != payload["chapter_revision_ref"]
        or pointer["seg"] != payload["seg"]
        or pointer["input_binding_hash"]
        != payload["extraction_input_binding"]["input_binding_hash"]
        or not isinstance(pointer["project_scope_id"], str)
        or not pointer["project_scope_id"]
        or not isinstance(pointer["author_workspace_logical_key"], str)
        or not pointer["author_workspace_logical_key"]
        or not isinstance(pointer["logical_pointer_key"], str)
        or not pointer["logical_pointer_key"]
        or pointer["logical_pointer_key"]
        != pointer_logical_key(
            pointer["chapter_revision_ref"],
            pointer["seg"],
            pointer["input_binding_hash"],
            project_scope_id=pointer["project_scope_id"],
            authority_profile=profile,
        )
    ):
        fail("B06_POINTER_SCOPE_INVALID")


def build_merge_receipt(*, payload: dict[str, Any], created_at: str) -> dict[str, Any]:
    record_id = f"merge-receipt:{sha256_value(payload)}"
    record = {
        "contract": IMMUTABLE_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "record_type": MERGE_RECEIPT_TYPE,
        "record_id": record_id,
        "record_version": 1,
        "record_contract_version": CONTRACT_VERSION,
        "record_hash": "",
        "source_module": SOURCE_MODULE,
        "access": RECEIPT_ACCESS,
        "retention_class": RETENTION_CLASS,
        "created_at": created_at,
        "payload": deepcopy(payload),
    }
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    validate_merge_receipt(record)
    return record


def validate_merge_receipt(record: dict[str, Any]) -> None:
    _exact_keys(record, ENVELOPE_KEYS, "B06_RECEIPT_ENVELOPE_INVALID")
    if (
        record["contract"] != IMMUTABLE_CONTRACT
        or record["contract_version"] != CONTRACT_VERSION
        or record["record_type"] != MERGE_RECEIPT_TYPE
        or record["record_version"] != 1
        or record["record_contract_version"] != CONTRACT_VERSION
        or record["source_module"] != SOURCE_MODULE
        or record["access"] != RECEIPT_ACCESS
        or record["retention_class"] != RETENTION_CLASS
        or not isinstance(record["created_at"], str)
        or not record["created_at"]
        or record["record_hash"]
        != sha256_value(
            {key: value for key, value in record.items() if key != "record_hash"}
        )
    ):
        fail("B06_RECEIPT_ENVELOPE_INVALID")
    payload = record["payload"]
    _exact_keys(payload, RECEIPT_KEYS, "B06_RECEIPT_PAYLOAD_INVALID")
    for key in (
        "request_hash",
        "pointer_binding_hash_before",
        "pointer_binding_hash_after",
        "canonical_apply_result_hash",
    ):
        if not _sha(payload[key]):
            fail("B06_RECEIPT_HASH_INVALID", key)
    if (
        not isinstance(payload["operation_id"], str)
        or not payload["operation_id"]
        or not isinstance(payload["route_unit_id"], str)
        or not payload["route_unit_id"]
        or not isinstance(payload["pointer_logical_key"], str)
        or not payload["pointer_logical_key"]
        or not isinstance(payload["pointer_generation_before"], int)
        or isinstance(payload["pointer_generation_before"], bool)
        or payload["pointer_generation_before"] < 1
        or not isinstance(payload["pointer_generation_after"], int)
        or isinstance(payload["pointer_generation_after"], bool)
        or payload["pointer_generation_after"]
        != payload["pointer_generation_before"] + 1
        or payload["committed_at"] != record["created_at"]
        or record["record_id"] != f"merge-receipt:{sha256_value(payload)}"
        or canonical_bytes(payload["base_candidate_version_ref"])
        == canonical_bytes(payload["child_candidate_version_ref"])
        or payload["pointer_binding_hash_before"]
        == payload["pointer_binding_hash_after"]
    ):
        fail("B06_RECEIPT_PAYLOAD_INVALID")
    refs = {
        "route_receipt_ref": "M3_PATCH_ROUTE_RECEIPT",
        "validation_receipt_ref": "M3_PATCH_VALIDATION_RECEIPT",
        "patch_proposal_ref": "M3_PATCH_PROPOSAL",
        "protection_set_ref": "M3_CANDIDATE_PROTECTION_SET",
        "base_candidate_version_ref": "M3_CANDIDATE_VERSION",
        "child_candidate_version_ref": "M3_CANDIDATE_VERSION",
    }
    try:
        for key, expected_type in refs.items():
            validate_record_ref(payload[key], expected_type=expected_type)
    except ValueError as error:
        fail("B06_RECEIPT_REF_INVALID", str(error))
    bindings = payload["atomic_group_bindings"]
    if (
        not isinstance(bindings, list)
        or not bindings
        or bindings != sorted(bindings, key=canonical_bytes)
        or len({canonical_bytes(item) for item in bindings}) != len(bindings)
    ):
        fail("B06_RECEIPT_GROUP_BINDING_INVALID")
    for binding in bindings:
        if (
            not isinstance(binding, dict)
            or set(binding) != {"atomic_group_id", "group_payload_hash"}
            or not isinstance(binding["atomic_group_id"], str)
            or not binding["atomic_group_id"]
            or not _sha(binding["group_payload_hash"])
        ):
            fail("B06_RECEIPT_GROUP_BINDING_INVALID")
