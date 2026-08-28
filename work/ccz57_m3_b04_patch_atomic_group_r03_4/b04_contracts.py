"""CCZ-57 M3 B-04 immutable patch-proposal contracts.

This module is fixture-only.  It has no model, network, subprocess, dynamic
import, or real-novel access path.
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
DOCUMENT_IDENTITY = "CCZ57-M3-B04-R02-CANDIDATE"
IMMUTABLE_CONTRACT = "M3_IMMUTABLE_RECORD"
RECORD_REF_CONTRACT = "M3_RECORD_REF"
LINEAGE_LOCATOR_CONTRACT = "M3_LINEAGE_LOCATOR"
SOURCE_MODULE = "M3"
FIXTURE_ACCESS = "POLICY_FIXTURE_READ_ONLY"
RUN_ACCESS = "RUN_INTERNAL_READ_ONLY"
RETENTION_CLASS = "CORE_IMMUTABLE_AUDIT"
WRITE_SET_PREFIX = "work/ccz57_m3_b04_patch_atomic_group_r03_4/"

EXPECTED_CURRENT_MAIN = "2307831d7b62eb57992d3be368a3a635ebb8b7b7"
EXPECTED_A_MERGE_SHA = "019df751641533c7de4d56aa38f50747fb564036"
EXPECTED_B01_MERGE_SHA = "905346f56cd51259c15a9517ead1517227c1719a"
EXPECTED_B02_REVIEWED_HEAD = "5e43484859aba53c594023e93ee5fa43291b057a"
EXPECTED_B02_MERGE_SHA = EXPECTED_CURRENT_MAIN
EXPECTED_B02_TREE = "1a8d5100602dfdbeb5f8bfe811b7377172a62c42"
EXPECTED_B02_RECEIPT_HASH = (
    "e19e8b40d529fa62ae0f6f43bb5ad10fcaa1ddc1211fe711f5290c91c44993c4"
)
EXPECTED_B02_RECEIPT_FILE_SHA256 = (
    "8244b608b412c2dbb4f31c5ea4a926a4c9cd4cff47fda87786dd79efb2adbdb2"
)
EXPECTED_B03_CATALOG_HASH = (
    "955bad28eb36ec70eb827b400640e00c5825041042e0d879960101d992761b93"
)
EXPECTED_SOURCE_SLICE_REF = {
    "contract": "M3_RECORD_REF",
    "contract_version": CONTRACT_VERSION,
    "record_type": "M3_AUTHORIZED_SOURCE_SLICE",
    "record_id": "srs:93232f086794dd8c60982f938952f8d5556601bc0e644b1729ba584534dc293a",
    "record_version": 1,
    "record_contract_version": CONTRACT_VERSION,
    "record_hash": "9f276749fd199c87da4e227d38f05b6572b9c5f7e6f2811f647ebe1f2a2a9929",
    "access": FIXTURE_ACCESS,
    "source_module": SOURCE_MODULE,
}
STALE_SOURCE_SLICE_HASH = (
    "1afdc3c1167b7f5bc11981915d55c4e19eda67154deee7870486fe7cb15825e2"
)

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
LOCATOR_KEYS = {
    "contract",
    "contract_version",
    "candidate_version_ref",
    "lineage_id",
    "json_pointer",
    "item_hash",
    "locator_hash",
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
    "value_hash",
    "reason",
}
PATCH_PAYLOAD_KEYS = {
    "base_candidate_version_ref",
    "diagnostic_refs",
    "authorized_source_slice_refs",
    "protection_set_ref",
    "chapter_revision_ref",
    "atomic_groups",
    "sidecar_proposal_refs",
}
CAUSAL_PAYLOAD_KEYS = {
    "from_lineage_locator",
    "to_lineage_locator",
    "evidence_refs",
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
    "json_pointer",
    "expected_old_value_hash",
    "new_value",
}
ADD_KEYS = {"operation_kind", "target_collection_pointer", "new_item"}
NEW_ITEM_KEYS = {"lineage_id", "text"}


class B04ContractError(ValueError):
    """Stable, machine-readable B-04 contract failure."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def fail(code: str, detail: str = "") -> None:
    raise B04ContractError(code, detail)


def normalize(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        fail("B04_CANONICAL_VALUE_INVALID", "floating-point values are forbidden")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                fail("B04_CANONICAL_KEY_INVALID", "object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in result:
                fail("B04_CANONICAL_DUPLICATE_KEY", normalized_key)
            result[normalized_key] = normalize(item)
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
    if set(value) != expected:
        fail(
            code,
            f"missing={sorted(expected - set(value))}; extra={sorted(set(value) - expected)}",
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


def _same(left: Any, right: Any) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def validate_lineage_locator(locator: Any, *, base: dict[str, Any]) -> dict[str, Any]:
    exact_keys(locator, LOCATOR_KEYS, "B04_LINEAGE_LOCATOR_SHAPE_INVALID")
    if locator["contract"] != LINEAGE_LOCATOR_CONTRACT:
        fail("B04_LINEAGE_LOCATOR_INVALID", "contract")
    if locator["contract_version"] != CONTRACT_VERSION:
        fail("B04_LINEAGE_LOCATOR_INVALID", "contract_version")
    validate_record_ref(
        locator["candidate_version_ref"], expected_type="M3_CANDIDATE_VERSION"
    )
    if not _same(locator["candidate_version_ref"], record_ref(base)):
        fail("B04_LINEAGE_LOCATOR_INVALID", "candidate_version_ref")
    match = re.fullmatch(r"/items/(\d+)", str(locator["json_pointer"]))
    if match is None:
        fail("B04_LINEAGE_LOCATOR_INVALID", "json_pointer")
    index = int(match.group(1))
    items = base.get("payload", {}).get("items", [])
    if index >= len(items):
        fail("B04_LINEAGE_LOCATOR_INVALID", "item index")
    item = items[index]
    if locator["lineage_id"] != item.get("lineage_id"):
        fail("B04_LINEAGE_LOCATOR_INVALID", "lineage_id")
    if locator["item_hash"] != item.get("item_hash"):
        fail("B04_LINEAGE_LOCATOR_INVALID", "item_hash")
    preimage = {key: value for key, value in locator.items() if key != "locator_hash"}
    if sha256_value(preimage) != locator["locator_hash"]:
        fail("B04_LINEAGE_LOCATOR_INVALID", "locator_hash")
    return item


def validate_upstream_base(base: dict[str, Any]) -> None:
    validate_record(base)
    if base["record_type"] != "M3_CANDIDATE_VERSION":
        fail("B04_BASE_INVALID", "record_type")
    payload = base.get("payload")
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        fail("B04_BASE_INVALID", "items")
    validate_chapter_revision(payload.get("chapter_revision_ref"))
    if not is_non_bool_int(payload.get("seg")):
        fail("B04_BASE_INVALID", "seg")


def validate_external_record(record: dict[str, Any], *, expected_type: str) -> None:
    validate_record(record)
    if record["record_type"] != expected_type:
        fail("B04_UPSTREAM_OBJECT_INVALID", expected_type)


def validate_source_slice_refs(
    refs: Any, *, source_slice_revision: dict[str, Any] | None, revision: dict[str, Any]
) -> None:
    if not isinstance(refs, list):
        fail("B04_SOURCE_SLICE_REFS_INVALID", "array required")
    if refs == []:
        if source_slice_revision is not None:
            fail("B04_SOURCE_SLICE_REFS_INVALID", "unexpected metadata")
        return
    if len(refs) != 1:
        fail("B04_SOURCE_SLICE_REFS_INVALID", "exactly one ref")
    ref = refs[0]
    if isinstance(ref, dict) and ref.get("record_hash") == STALE_SOURCE_SLICE_HASH:
        fail("STALE_SOURCE_SLICE_REF")
    if not _same(ref, EXPECTED_SOURCE_SLICE_REF):
        fail("SOURCE_SLICE_RECORD_REF_MISMATCH")
    validate_record_ref(ref, expected_type="M3_AUTHORIZED_SOURCE_SLICE")
    if source_slice_revision is None or not _same(source_slice_revision, revision):
        fail("SOURCE_SLICE_REVISION_MISMATCH")


def operation_write_target(operation: dict[str, Any]) -> str:
    if operation.get("operation_kind") == "REPLACE_FIELD":
        return operation.get("json_pointer", "")
    if operation.get("operation_kind") == "ADD_CANDIDATE_ITEM":
        return "/items/-"
    if operation.get("operation_kind") == "ADD_CAUSAL_HINT":
        fail("FORBIDDEN_COMMITTABLE_OPERATION")
    fail("B04_OPERATION_KIND_INVALID", str(operation.get("operation_kind")))


def _pointer_overlap(left: str, right: str) -> bool:
    normalized_left = left.rstrip("/")
    normalized_right = right.rstrip("/")
    return (
        normalized_left == normalized_right
        or normalized_left.startswith(normalized_right + "/")
        or normalized_right.startswith(normalized_left + "/")
    )


def validate_operation(
    operation: Any,
    *,
    base: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    coverages: list[dict[str, Any]],
) -> None:
    if not isinstance(operation, dict):
        fail("B04_OPERATION_SHAPE_INVALID", "object required")
    kind = operation.get("operation_kind")
    if kind == "ADD_CAUSAL_HINT":
        fail("FORBIDDEN_COMMITTABLE_OPERATION")
    if kind == "REPLACE_FIELD":
        exact_keys(operation, REPLACE_KEYS, "B04_REPLACE_SHAPE_INVALID")
        item = validate_lineage_locator(operation["target"], base=base)
        expected_pointer = operation["target"]["json_pointer"] + "/text"
        if operation["json_pointer"] != expected_pointer:
            fail("B04_REPLACE_TARGET_INVALID", "json_pointer")
        old_value = item.get("text")
        if operation["expected_old_value_hash"] != sha256_value(old_value):
            fail("B04_REPLACE_OLD_HASH_MISMATCH")
        new_value = operation["new_value"]
        if (
            not isinstance(new_value, str)
            or not new_value
            or new_value != normalize(new_value)
        ):
            fail("B04_REPLACE_NEW_VALUE_INVALID")
        if canonical_bytes(new_value) == canonical_bytes(old_value):
            fail("B04_REPLACE_NO_OP")
        target = operation["target"]
        if not any(
            _same(diag["payload"].get("target", {}).get("lineage_locator"), target)
            for diag in diagnostics
        ):
            fail("B04_REPLACE_DIAGNOSTIC_REQUIRED")
        return
    if kind == "ADD_CANDIDATE_ITEM":
        exact_keys(operation, ADD_KEYS, "B04_ADD_SHAPE_INVALID")
        exact_keys(operation["new_item"], NEW_ITEM_KEYS, "B04_ADD_ITEM_SHAPE_INVALID")
        if operation["target_collection_pointer"] != "/items":
            fail("B04_ADD_TARGET_INVALID")
        new_item = operation["new_item"]
        if not isinstance(new_item["lineage_id"], str) or not new_item["lineage_id"]:
            fail("B04_ADD_ITEM_INVALID", "lineage_id")
        if not isinstance(new_item["text"], str) or not new_item["text"]:
            fail("B04_ADD_ITEM_INVALID", "text")
        if new_item["text"] != normalize(new_item["text"]):
            fail("B04_ADD_ITEM_INVALID", "NFC")
        base_lineages = {item.get("lineage_id") for item in base["payload"]["items"]}
        if new_item["lineage_id"] in base_lineages:
            fail("B04_ADD_LINEAGE_DUPLICATE")
        if not any(
            coverage["payload"].get("candidate_match") in {"MISSING", "PARTIAL"}
            for coverage in coverages
        ):
            fail("B04_ADD_COVERAGE_REQUIRED")
        return
    fail("B04_OPERATION_KIND_INVALID", str(kind))


def validate_atomic_groups(
    groups: Any,
    *,
    base: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    coverages: list[dict[str, Any]],
) -> None:
    if not isinstance(groups, list) or not groups:
        fail("B04_ATOMIC_GROUPS_INVALID", "non-empty array required")
    added_by_group: dict[int, set[str]] = {}
    for index, group in enumerate(groups):
        if not isinstance(group, dict) or not isinstance(group.get("operations"), list):
            continue
        added_by_group[index] = {
            str(operation.get("new_item", {}).get("lineage_id"))
            for operation in group["operations"]
            if isinstance(operation, dict)
            and operation.get("operation_kind") == "ADD_CANDIDATE_ITEM"
        }
    for owner, added in added_by_group.items():
        for index, group in enumerate(groups):
            if index == owner or not isinstance(group, dict):
                continue
            for operation in group.get("operations", []):
                if not isinstance(operation, dict):
                    continue
                target_lineage = operation.get("target", {}).get("lineage_id")
                if target_lineage in added:
                    fail("B04_CROSS_GROUP_DEPENDENCY", str(target_lineage))

    group_ids: set[str] = set()
    operation_fingerprints: set[str] = set()
    writes_by_group: list[list[str]] = []
    added_lineages: set[str] = set()
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
        for operation in operations:
            validate_operation(
                operation, base=base, diagnostics=diagnostics, coverages=coverages
            )
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
    canonical_groups = canonical_bytes(groups)
    for lineage in added_lineages:
        marker = f'"lineage_id":"{lineage}"'.encode("utf-8")
        if canonical_groups.count(marker) > 1:
            fail("B04_CROSS_GROUP_DEPENDENCY", lineage)


def expected_protected_entries(
    *, base: dict[str, Any], groups: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    replace_paths = {
        operation["json_pointer"]
        for group in groups
        for operation in group["operations"]
        if operation["operation_kind"] == "REPLACE_FIELD"
    }
    locators = {
        entry["json_pointer"]: entry
        for entry in base["payload"].get("lineage_index", [])
    }
    result: list[dict[str, Any]] = []
    for index, item in enumerate(base["payload"]["items"]):
        text_path = f"/items/{index}/text"
        if text_path in replace_paths:
            continue
        index_entry = locators.get(f"/items/{index}")
        if index_entry is None:
            fail("B04_BASE_LINEAGE_INDEX_INVALID", text_path)
        locator = {
            "contract": LINEAGE_LOCATOR_CONTRACT,
            "contract_version": CONTRACT_VERSION,
            "candidate_version_ref": record_ref(base),
            "lineage_id": item["lineage_id"],
            "json_pointer": f"/items/{index}",
            "item_hash": item["item_hash"],
            "locator_hash": "",
        }
        locator["locator_hash"] = sha256_value(
            {key: value for key, value in locator.items() if key != "locator_hash"}
        )
        result.append(
            {
                "lineage_locator": locator,
                "json_pointer": text_path,
                "value_hash": sha256_value(item["text"]),
                "reason": "UNTOUCHED_ACCEPTED_CORRECT_ITEM",
            }
        )
    return result


def validate_protection_record(
    record: dict[str, Any],
    *,
    base: dict[str, Any],
    policy: dict[str, Any],
    groups: list[dict[str, Any]],
) -> None:
    validate_record(record)
    if record["record_type"] != "M3_CANDIDATE_PROTECTION_SET":
        fail("B04_PROTECTION_SET_INVALID", "record_type")
    payload = record["payload"]
    exact_keys(payload, PROTECTION_PAYLOAD_KEYS, "B04_PROTECTION_PAYLOAD_INVALID")
    validate_external_record(policy, expected_type="M3_PROTECTION_POLICY")
    policy_payload = policy["payload"]
    exact_keys(
        policy_payload,
        {"policy_revision", "protect_untouched_fields", "protect_accepted_lineage"},
        "B04_PROTECTION_POLICY_INVALID",
    )
    if (
        policy_payload["protect_untouched_fields"] is not True
        or policy_payload["protect_accepted_lineage"] is not True
    ):
        fail("B04_PROTECTION_POLICY_INVALID", "disabled")
    if not _same(payload["base_candidate_version_ref"], record_ref(base)):
        fail("B04_PROTECTION_SET_INVALID", "base")
    if not _same(payload["protection_policy_ref"], record_ref(policy)):
        fail("B04_PROTECTION_SET_INVALID", "policy")
    if not _same(
        payload["chapter_revision_ref"], base["payload"]["chapter_revision_ref"]
    ):
        fail("B04_PROTECTION_SET_INVALID", "revision")
    expected = expected_protected_entries(base=base, groups=groups)
    if not _same(payload["protected_entries"], expected):
        fail("B04_PROTECTION_COMPLEMENT_MISMATCH")
    for entry in payload["protected_entries"]:
        exact_keys(entry, PROTECTED_ENTRY_KEYS, "B04_PROTECTED_ENTRY_INVALID")
        validate_lineage_locator(entry["lineage_locator"], base=base)


def validate_upstream_inputs(
    *,
    base: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    coverages: list[dict[str, Any]],
) -> None:
    validate_upstream_base(base)
    revision = base["payload"]["chapter_revision_ref"]
    seg = base["payload"]["seg"]
    if not diagnostics:
        fail("B04_DIAGNOSTIC_REQUIRED")
    for diagnostic in diagnostics:
        validate_external_record(diagnostic, expected_type="M3_DIAGNOSTIC")
        payload = diagnostic["payload"]
        if not _same(payload.get("base_candidate_version_ref"), record_ref(base)):
            fail("B04_DIAGNOSTIC_BASE_MISMATCH")
        if not _same(payload.get("chapter_revision_ref"), revision):
            fail("B04_DIAGNOSTIC_REVISION_MISMATCH")
        if payload.get("seg") != seg:
            fail("B04_DIAGNOSTIC_SEG_MISMATCH")
        validate_lineage_locator(
            payload.get("target", {}).get("lineage_locator"), base=base
        )
    for coverage in coverages:
        validate_external_record(coverage, expected_type="M3_COVERAGE_OBSERVATION")
        payload = coverage["payload"]
        if not _same(payload.get("base_candidate_version_ref"), record_ref(base)):
            fail("B04_COVERAGE_BASE_MISMATCH")
        if not _same(payload.get("chapter_revision_ref"), revision):
            fail("B04_COVERAGE_REVISION_MISMATCH")
        if payload.get("seg") != seg:
            fail("B04_COVERAGE_SEG_MISMATCH")
        if payload.get("candidate_match") not in {"MATCHED", "MISSING", "PARTIAL"}:
            fail("B04_COVERAGE_VALUE_INVALID")


def validate_causal_record(
    record: dict[str, Any],
    *,
    base: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    source_slice_refs: list[dict[str, Any]],
) -> None:
    validate_record(record)
    if record["record_type"] != "M3_CAUSAL_HINT_PROPOSAL":
        fail("B04_CAUSAL_INVALID", "record_type")
    payload = record["payload"]
    exact_keys(payload, CAUSAL_PAYLOAD_KEYS, "B04_CAUSAL_PAYLOAD_INVALID")
    validate_lineage_locator(payload["from_lineage_locator"], base=base)
    validate_lineage_locator(payload["to_lineage_locator"], base=base)
    if payload["noncommittable"] is not True:
        fail("B04_CAUSAL_MUST_BE_NONCOMMITTABLE")
    if not isinstance(payload["hint_kind"], str) or not payload["hint_kind"]:
        fail("B04_CAUSAL_INVALID", "hint_kind")
    if (
        not is_non_bool_int(payload["expiry_request_seconds"])
        or payload["expiry_request_seconds"] <= 0
    ):
        fail("B04_CAUSAL_INVALID", "expiry")
    if not _same(
        payload["chapter_revision_ref"], base["payload"]["chapter_revision_ref"]
    ):
        fail("B04_CAUSAL_REVISION_MISMATCH")
    diagnostic_refs = [record_ref(item) for item in diagnostics]
    if not payload["diagnostic_refs"] or any(
        not any(_same(ref, allowed) for allowed in diagnostic_refs)
        for ref in payload["diagnostic_refs"]
    ):
        fail("B04_CAUSAL_DIAGNOSTIC_REF_INVALID")
    if any(
        not any(_same(ref, allowed) for allowed in source_slice_refs)
        for ref in payload["evidence_refs"]
    ):
        fail("B04_CAUSAL_EVIDENCE_REF_INVALID")


def validate_patch_record(
    record: dict[str, Any],
    *,
    base: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    coverages: list[dict[str, Any]],
    protection: dict[str, Any],
    causal_records: list[dict[str, Any]],
    source_slice_revision: dict[str, Any] | None,
) -> None:
    validate_record(record)
    if record["record_type"] != "M3_PATCH_PROPOSAL":
        fail("B04_PATCH_INVALID", "record_type")
    payload = record["payload"]
    exact_keys(payload, PATCH_PAYLOAD_KEYS, "B04_PATCH_PAYLOAD_INVALID")
    if not _same(payload["base_candidate_version_ref"], record_ref(base)):
        fail("B04_PATCH_BASE_MISMATCH")
    if not _same(
        payload["chapter_revision_ref"], base["payload"]["chapter_revision_ref"]
    ):
        fail("B04_PATCH_REVISION_MISMATCH")
    allowed_diagnostics = [record_ref(item) for item in diagnostics]
    if not payload["diagnostic_refs"] or any(
        not any(_same(ref, allowed) for allowed in allowed_diagnostics)
        for ref in payload["diagnostic_refs"]
    ):
        fail("B04_PATCH_DIAGNOSTIC_REF_INVALID")
    validate_source_slice_refs(
        payload["authorized_source_slice_refs"],
        source_slice_revision=source_slice_revision,
        revision=base["payload"]["chapter_revision_ref"],
    )
    if not _same(payload["protection_set_ref"], record_ref(protection)):
        fail("B04_PATCH_PROTECTION_REF_INVALID")
    validate_atomic_groups(
        payload["atomic_groups"],
        base=base,
        diagnostics=diagnostics,
        coverages=coverages,
    )
    protected_paths = [
        entry["json_pointer"] for entry in protection["payload"]["protected_entries"]
    ]
    for group in payload["atomic_groups"]:
        for operation in group["operations"]:
            target = operation_write_target(operation)
            if any(
                _pointer_overlap(target, protected) for protected in protected_paths
            ):
                fail("B04_PROTECTED_TARGET_OVERLAP")
    causal_by_ref = {canonical_bytes(record_ref(item)): item for item in causal_records}
    if len(payload["sidecar_proposal_refs"]) != len(
        {canonical_bytes(ref) for ref in payload["sidecar_proposal_refs"]}
    ):
        fail("B04_SIDECAR_REF_DUPLICATE")
    for ref in payload["sidecar_proposal_refs"]:
        validate_record_ref(ref, expected_type="M3_CAUSAL_HINT_PROPOSAL")
        causal = causal_by_ref.get(canonical_bytes(ref))
        if causal is None:
            fail("B04_SIDECAR_REF_INVALID")
        validate_causal_record(
            causal,
            base=base,
            diagnostics=diagnostics,
            source_slice_refs=payload["authorized_source_slice_refs"],
        )


def validate_output_record(record: dict[str, Any]) -> None:
    validate_record(record)
    if record["record_type"] not in OUTPUT_TYPES:
        fail("B04_OUTPUT_TYPE_INVALID", str(record["record_type"]))


def validate_construction_gate(
    *,
    a_admission: dict[str, Any],
    b01_receipt: dict[str, Any],
    b02_receipt: dict[str, Any],
    current_main_sha: str,
) -> None:
    """Validate the three construction receipts without turning them into products."""

    try:
        validate_record(a_admission)
    except B04ContractError as error:
        fail("B04_ADMISSION_FAILED", error.code)
    if a_admission["record_type"] != "M3_A_INTERFACE_ADMISSION_RECEIPT":
        fail("B04_ADMISSION_FAILED", "A receipt type")
    if a_admission["payload"].get("merge_commit_sha") != EXPECTED_A_MERGE_SHA:
        fail("B04_ADMISSION_FAILED", "A merge")
    if a_admission["payload"].get("admission_result") != "PASS":
        fail("B04_ADMISSION_FAILED", "A result")

    b01_preimage = {
        key: value for key, value in b01_receipt.items() if key != "receipt_hash"
    }
    if sha256_value(b01_preimage) != b01_receipt.get("receipt_hash"):
        fail("B04_ADMISSION_FAILED", "B-01 receipt hash")
    if b01_receipt.get("pr", {}).get("merge_commit") != EXPECTED_B01_MERGE_SHA:
        fail("B04_ADMISSION_FAILED", "B-01 merge")
    if b01_receipt.get("pr", {}).get("merged") is not True:
        fail("B04_ADMISSION_FAILED", "B-01 merged")

    b02_preimage = {
        key: value for key, value in b02_receipt.items() if key != "receipt_hash"
    }
    if sha256_value(b02_preimage) != b02_receipt.get("receipt_hash"):
        fail("B04_B02_READBACK_FAILED", "receipt hash")
    pr = b02_receipt.get("pr", {})
    readback = b02_receipt.get("current_main_readback", {})
    artifacts = b02_receipt.get("merged_b02_artifacts", {})
    if pr.get("merged") is not True or pr.get("merge_commit") != EXPECTED_B02_MERGE_SHA:
        fail("B04_B02_NOT_MERGED")
    if pr.get("head_at_merge") != EXPECTED_B02_REVIEWED_HEAD:
        fail("B04_B02_NOT_MERGED", "head drift")
    if current_main_sha != EXPECTED_CURRENT_MAIN:
        fail("B04_B02_READBACK_FAILED", "current main")
    if (
        readback.get("sha") != current_main_sha
        or readback.get("merge_commit_reachable_from_current_main") is not True
    ):
        fail("B04_B02_READBACK_FAILED", "reachability")
    if artifacts.get("git_tree") != EXPECTED_B02_TREE:
        fail("B04_B02_READBACK_FAILED", "tree")


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
