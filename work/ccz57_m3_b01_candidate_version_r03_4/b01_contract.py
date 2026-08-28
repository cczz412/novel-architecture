"""CCZ-57 M3 B-01 offline candidate-version contract.

This module intentionally has no model, network, subprocess, or dynamic-import path.
It operates only on synthetic fixture data and a caller-provided fixture directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "r03.3-candidate"
IMMUTABLE_CONTRACT = "M3_IMMUTABLE_RECORD"
LINEAGE_LOCATOR_CONTRACT = "M3_LINEAGE_LOCATOR"
SOURCE_MODULE = "CCZ57-M3-B01"
FIXTURE_POINTER_NAMESPACE = "FIXTURE_ONLY"
WRITE_SET_PREFIX = "work/ccz57_m3_b01_candidate_version_r03_4/"
FORBIDDEN_RUNTIME_EVENTS = {
    "network",
    "model_api",
    "subprocess",
    "dynamic_import",
    "credential_read",
    "real_novel_read",
    "product_pointer_write",
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


class B01ContractError(ValueError):
    """Stable, machine-readable failure for the B-01 boundary."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _fail(code: str, detail: str = "") -> None:
    raise B01ContractError(code, detail)


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        _fail("B01_CANONICAL_VALUE_INVALID", "floating-point values are forbidden")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                _fail("B01_CANONICAL_KEY_INVALID", "object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                _fail("B01_CANONICAL_DUPLICATE_KEY", normalized_key)
            normalized[normalized_key] = _normalize(item)
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


def _exact_keys(value: dict[str, Any], expected: set[str], code: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        _fail(code, f"missing={missing}; extra={extra}")


def make_record(
    *,
    record_type: str,
    record_id: str,
    record_version: int,
    payload: dict[str, Any],
    created_at: str,
    access: str = "INTERNAL",
    retention_class: str = "PROJECT_LIFETIME",
) -> dict[str, Any]:
    record = {
        "contract": IMMUTABLE_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "record_type": record_type,
        "record_id": record_id,
        "record_version": record_version,
        "record_contract_version": CONTRACT_VERSION,
        "record_hash": "",
        "source_module": SOURCE_MODULE,
        "access": access,
        "retention_class": retention_class,
        "created_at": created_at,
        "payload": deepcopy(payload),
    }
    preimage = {key: value for key, value in record.items() if key != "record_hash"}
    record["record_hash"] = sha256_value(preimage)
    return record


def validate_record(record: dict[str, Any]) -> None:
    _exact_keys(record, ENVELOPE_KEYS, "B01_IMMUTABLE_ENVELOPE_INVALID")
    if record["contract"] != IMMUTABLE_CONTRACT:
        _fail("B01_IMMUTABLE_ENVELOPE_INVALID", "contract")
    if (
        record["contract_version"] != CONTRACT_VERSION
        or record["record_contract_version"] != CONTRACT_VERSION
    ):
        _fail("B01_IMMUTABLE_ENVELOPE_INVALID", "contract version")
    if not isinstance(record["record_version"], int) or record["record_version"] < 1:
        _fail("B01_IMMUTABLE_ENVELOPE_INVALID", "record version")
    preimage = {key: value for key, value in record.items() if key != "record_hash"}
    if record["record_hash"] != sha256_value(preimage):
        _fail("B01_RECORD_HASH_MISMATCH", record.get("record_id", ""))


def record_ref(record: dict[str, Any]) -> dict[str, Any]:
    validate_record(record)
    return {key: deepcopy(record[key]) for key in RECORD_REF_KEYS}


def validate_record_ref(
    ref: dict[str, Any], *, code: str = "B01_RECORD_REF_INVALID"
) -> None:
    _exact_keys(ref, RECORD_REF_KEYS, code)
    if ref["contract"] != IMMUTABLE_CONTRACT:
        _fail(code, "contract")
    if (
        ref["contract_version"] != CONTRACT_VERSION
        or ref["record_contract_version"] != CONTRACT_VERSION
    ):
        _fail(code, "contract version")
    if not isinstance(ref["record_version"], int) or ref["record_version"] < 1:
        _fail(code, "record version")
    if not isinstance(ref["record_hash"], str) or len(ref["record_hash"]) != 64:
        _fail(code, "record hash")


def validate_admission(admission: dict[str, Any]) -> None:
    if not admission:
        _fail("B01_A_ADMISSION_REQUIRED")
    required = {
        "receipt_type",
        "reviewed_head_sha",
        "merge_time_head_sha",
        "merge_commit_sha",
        "current_main_sha",
        "main_contains_merge",
        "readback_ok",
        "interface_manifest_hash",
        "expected_interface_manifest_hash",
    }
    if not required.issubset(admission):
        _fail("B01_A_ADMISSION_REQUIRED", "receipt fields missing")
    if admission["receipt_type"] != "A_INTERFACE_ADMISSION_RECEIPT":
        _fail("B01_A_ADMISSION_REQUIRED", "receipt type")
    if admission["reviewed_head_sha"] != admission["merge_time_head_sha"]:
        _fail("B01_A_ADMISSION_HEAD_MISMATCH")
    if not admission["main_contains_merge"] or not admission["readback_ok"]:
        _fail("B01_A_ADMISSION_READBACK_INVALID")
    if admission["current_main_sha"] != admission["merge_commit_sha"]:
        _fail("B01_A_ADMISSION_READBACK_INVALID", "current main")
    if (
        admission["interface_manifest_hash"]
        != admission["expected_interface_manifest_hash"]
    ):
        _fail("B01_A_INTERFACE_DRIFT")


def validate_chapter_revision_ref(ref: dict[str, Any]) -> None:
    validate_record_ref(ref, code="B01_SEGMENT_SOURCE_MISMATCH")
    if ref["record_type"] != "CHAPTER_REVISION":
        _fail("B01_SEGMENT_SOURCE_MISMATCH", "record type")


def stable_segment_index_id(
    project_scope_id: str,
    chapter_id: str,
    revision_no: int,
    revision_text_sha256: str,
) -> str:
    return (
        f"segidx:{project_scope_id}:{chapter_id}:r{revision_no}:"
        f"{revision_text_sha256[:12]}"
    )


def _segment_id(ref: dict[str, Any]) -> tuple[str, int]:
    return str(ref["record_id"]), int(ref["record_version"])


def build_segment_index_snapshot(
    *,
    project_scope_id: str,
    author_workspace_logical_key: str,
    chapter_revision_ref: dict[str, Any],
    revision_text_sha256: str,
    segment_inputs: list[dict[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    validate_chapter_revision_ref(chapter_revision_ref)
    if not segment_inputs:
        _fail("B01_SEGMENT_INDEX_INVALID", "segments must not be empty")
    chapter_id, revision_no = _segment_id(chapter_revision_ref)
    segments: list[dict[str, Any]] = []
    previous_end = 0
    for expected_seg, source in enumerate(segment_inputs, start=1):
        if source.get("seg") != expected_seg:
            _fail("B01_SEGMENT_INDEX_INVALID", "segment numbering")
        start = source.get("start_offset")
        end = source.get("end_offset")
        text = source.get("responsibility_text")
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or not isinstance(text, str)
            or start < 0
            or start >= end
            or start != previous_end
        ):
            _fail("B01_SEGMENT_INDEX_INVALID", "segment range")
        expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        supplied_hash = source.get("responsibility_text_sha256", expected_hash)
        if supplied_hash != expected_hash:
            _fail("B01_SEGMENT_TEXT_HASH_MISMATCH")
        segments.append(
            {
                "seg": expected_seg,
                "start_offset": start,
                "end_offset": end,
                "responsibility_text_sha256": expected_hash,
            }
        )
        previous_end = end
    stable_id = stable_segment_index_id(
        project_scope_id,
        chapter_id,
        revision_no,
        revision_text_sha256,
    )
    payload = {
        "project_scope_id": project_scope_id,
        "author_workspace_logical_key": author_workspace_logical_key,
        "source_module_identity": SOURCE_MODULE,
        "chapter_revision_ref": deepcopy(chapter_revision_ref),
        "stable_segment_index_id": stable_id,
        "segments": segments,
    }
    return make_record(
        record_type="M3_SEGMENT_INDEX_SNAPSHOT",
        record_id=stable_id,
        record_version=1,
        payload=payload,
        created_at=created_at,
    )


def validate_segment_index_snapshot(record: dict[str, Any]) -> None:
    validate_record(record)
    if record["record_type"] != "M3_SEGMENT_INDEX_SNAPSHOT":
        _fail("B01_SEGMENT_INDEX_INVALID", "record type")
    payload = record["payload"]
    expected = {
        "project_scope_id",
        "author_workspace_logical_key",
        "source_module_identity",
        "chapter_revision_ref",
        "stable_segment_index_id",
        "segments",
    }
    _exact_keys(payload, expected, "B01_SEGMENT_INDEX_INVALID")
    validate_chapter_revision_ref(payload["chapter_revision_ref"])
    if payload["source_module_identity"] != SOURCE_MODULE:
        _fail("B01_SEGMENT_SOURCE_MISMATCH")
    if payload["stable_segment_index_id"] != record["record_id"]:
        _fail("B01_SEGMENT_INDEX_INVALID", "stable id")
    if not payload["segments"]:
        _fail("B01_SEGMENT_INDEX_INVALID", "empty")
    previous_end = 0
    for expected_seg, segment in enumerate(payload["segments"], start=1):
        _exact_keys(
            segment,
            {"seg", "start_offset", "end_offset", "responsibility_text_sha256"},
            "B01_SEGMENT_INDEX_INVALID",
        )
        if segment["seg"] != expected_seg:
            _fail("B01_SEGMENT_INDEX_INVALID", "numbering")
        if (
            segment["start_offset"] != previous_end
            or segment["start_offset"] >= segment["end_offset"]
        ):
            _fail("B01_SEGMENT_INDEX_INVALID", "range")
        if len(segment["responsibility_text_sha256"]) != 64:
            _fail("B01_SEGMENT_TEXT_HASH_MISMATCH")
        previous_end = segment["end_offset"]


def _validate_attempt_refs(refs: list[dict[str, Any]]) -> None:
    if not refs:
        _fail("B01_ATTEMPT_REF_INVALID", "root baseline requires evidence")
    for ref in refs:
        validate_record_ref(ref, code="B01_ATTEMPT_REF_INVALID")
        if ref["record_type"] != "RAW_ATTEMPT_RECEIPT":
            _fail("B01_ATTEMPT_REF_INVALID", "record type")


def _stored_item(
    chapter_revision_ref: dict[str, Any], seg: int, ordinal: int, raw: dict[str, Any]
) -> dict[str, Any]:
    if set(raw) not in ({"text"}, {"text", "quote"}):
        _fail("B01_CANDIDATE_VERSION_INVALID", "raw item fields")
    if not isinstance(raw.get("text"), str) or not raw["text"]:
        _fail("B01_CANDIDATE_VERSION_INVALID", "item text")
    seed = {
        "chapter_revision_ref": chapter_revision_ref,
        "seg": seg,
        "ordinal": ordinal,
        "text": raw["text"],
        "quote_if_present": raw.get("quote"),
    }
    lineage_id = f"lin_{sha256_value(seed)}"
    item = {"lineage_id": lineage_id, "text": raw["text"]}
    item_preimage: dict[str, Any] = {"lineage_id": lineage_id, "text": raw["text"]}
    if "quote" in raw:
        if not isinstance(raw["quote"], str):
            _fail("B01_CANDIDATE_VERSION_INVALID", "quote")
        item["quote"] = raw["quote"]
        item_preimage["quote_if_present"] = raw["quote"]
    item["item_hash"] = sha256_value(item_preimage)
    return item


def build_root_candidate_version(
    *,
    chapter_revision_ref: dict[str, Any],
    seg: int,
    origin_attempt_refs: list[dict[str, Any]],
    raw_items: list[dict[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    validate_chapter_revision_ref(chapter_revision_ref)
    if not isinstance(seg, int) or seg < 1:
        _fail("B01_CANDIDATE_VERSION_INVALID", "segment")
    _validate_attempt_refs(origin_attempt_refs)
    items = [
        _stored_item(chapter_revision_ref, seg, ordinal, raw)
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
    chapter_id, revision_no = _segment_id(chapter_revision_ref)
    record_id = f"candidate:{chapter_id}:r{revision_no}:seg{seg}:v1"
    return make_record(
        record_type="M3_CANDIDATE_VERSION",
        record_id=record_id,
        record_version=1,
        payload=payload,
        created_at=created_at,
    )


def validate_candidate_version(
    record: dict[str, Any], *, allow_child: bool = False
) -> None:
    validate_record(record)
    if record["record_type"] != "M3_CANDIDATE_VERSION":
        _fail("B01_CANDIDATE_VERSION_INVALID", "record type")
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
    _exact_keys(payload, expected, "B01_CANDIDATE_VERSION_INVALID")
    validate_chapter_revision_ref(payload["chapter_revision_ref"])
    if not isinstance(payload["seg"], int) or payload["seg"] < 1:
        _fail("B01_CANDIDATE_VERSION_INVALID", "segment")
    if record["record_version"] != 1 and not allow_child:
        _fail("B01_CHILD_CREATION_OUT_OF_SCOPE")
    if payload["parent_candidate_version_ref"] is not None and not allow_child:
        _fail("B01_CHILD_CREATION_OUT_OF_SCOPE")
    if payload["origin_commit_intent_ref"] is not None and not allow_child:
        _fail("B01_CHILD_CREATION_OUT_OF_SCOPE")
    _validate_attempt_refs(payload["origin_attempt_refs"])
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
        allowed_item_keys = {"lineage_id", "text", "item_hash"}
        if "quote" in item:
            allowed_item_keys.add("quote")
        _exact_keys(item, allowed_item_keys, "B01_CANDIDATE_VERSION_INVALID")
        if item["lineage_id"] in seen:
            _fail("B01_DUPLICATE_LINEAGE_ID")
        seen.add(item["lineage_id"])
        item_preimage = {"lineage_id": item["lineage_id"], "text": item["text"]}
        if "quote" in item:
            item_preimage["quote_if_present"] = item["quote"]
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


def pointer_logical_key(chapter_revision_ref: dict[str, Any], seg: int) -> str:
    chapter_id, revision_no = _segment_id(chapter_revision_ref)
    return f"fixture:m3_candidate.current/{chapter_id}/r{revision_no}/seg{seg}"


def build_pointer_snapshot(
    *,
    project_scope_id: str,
    author_workspace_logical_key: str,
    chapter_revision_ref: dict[str, Any],
    seg: int,
    candidate_ref: dict[str, Any],
    operation_id: str,
    created_at: str,
) -> dict[str, Any]:
    validate_chapter_revision_ref(chapter_revision_ref)
    validate_record_ref(candidate_ref)
    payload_without_hash = {
        "project_scope_id": project_scope_id,
        "author_workspace_logical_key": author_workspace_logical_key,
        "logical_pointer_key": pointer_logical_key(chapter_revision_ref, seg),
        "pointer_namespace": FIXTURE_POINTER_NAMESPACE,
        "chapter_revision_ref": deepcopy(chapter_revision_ref),
        "seg": seg,
        "generation": 1,
        "current_candidate_version_ref": deepcopy(candidate_ref),
        "snapshot_kind": "BASELINE_VERSIONED",
        "snapshot_operation_id": operation_id,
    }
    payload = {
        **payload_without_hash,
        "snapshot_request_hash": sha256_value(payload_without_hash),
    }
    record_id = f"pointer-snapshot:{sha256_value(payload_without_hash)[:32]}"
    return make_record(
        record_type="M3_CANDIDATE_POINTER_SNAPSHOT",
        record_id=record_id,
        record_version=1,
        payload=payload,
        created_at=created_at,
    )


def validate_pointer_snapshot(record: dict[str, Any]) -> None:
    validate_record(record)
    if record["record_type"] != "M3_CANDIDATE_POINTER_SNAPSHOT":
        _fail("B01_POINTER_SCOPE_MISMATCH", "record type")
    payload = record["payload"]
    expected = {
        "project_scope_id",
        "author_workspace_logical_key",
        "logical_pointer_key",
        "pointer_namespace",
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
    if payload["generation"] != 1 or payload["snapshot_kind"] != "BASELINE_VERSIONED":
        _fail("B01_POINTER_SCOPE_MISMATCH", "initialization")
    if payload["logical_pointer_key"] != pointer_logical_key(
        payload["chapter_revision_ref"], payload["seg"]
    ):
        _fail("B01_POINTER_SCOPE_MISMATCH", "logical key")
    preimage = {
        key: value for key, value in payload.items() if key != "snapshot_request_hash"
    }
    if payload["snapshot_request_hash"] != sha256_value(preimage):
        _fail("B01_POINTER_SCOPE_MISMATCH", "request hash")


def make_lineage_locator(
    candidate_version: dict[str, Any], lineage_id: str
) -> dict[str, Any]:
    validate_candidate_version(candidate_version, allow_child=True)
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


def validate_lineage_locator(locator: dict[str, Any]) -> None:
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
    validate_record_ref(locator["candidate_version_ref"])
    preimage = {key: value for key, value in locator.items() if key != "locator_hash"}
    if locator["locator_hash"] != sha256_value(preimage):
        _fail("B01_LINEAGE_INDEX_INVALID", "locator hash")


def project_version_diff(
    parent: dict[str, Any], child: dict[str, Any], *, persist: bool = False
) -> dict[str, Any]:
    if persist:
        _fail("B01_DERIVED_VIEW_PERSIST_FORBIDDEN")
    try:
        validate_candidate_version(parent, allow_child=True)
        validate_candidate_version(child, allow_child=True)
    except B01ContractError as error:
        _fail("B01_VERSION_DIFF_INVALID", error.code)
    parent_ref = record_ref(parent)
    if child["payload"]["parent_candidate_version_ref"] != parent_ref:
        _fail("B01_VERSION_DIFF_INVALID", "parent reference")
    if (
        child["payload"]["chapter_revision_ref"]
        != parent["payload"]["chapter_revision_ref"]
        or child["payload"]["seg"] != parent["payload"]["seg"]
    ):
        _fail("B01_VERSION_DIFF_INVALID", "scope")
    parent_items = parent["payload"]["items"]
    child_items = child["payload"]["items"]
    changed: list[str] = []
    for index in range(max(len(parent_items), len(child_items))):
        if index >= len(parent_items) or index >= len(child_items):
            changed.append(f"/items/{index}")
        elif parent_items[index] != child_items[index]:
            changed.append(f"/items/{index}")
    return {
        "view_type": "DERIVED_RECOMPUTABLE",
        "parent_candidate_version_ref": parent_ref,
        "child_candidate_version_ref": record_ref(child),
        "changed_json_pointers": sorted(
            set(changed), key=lambda item: item.encode("utf-8")
        ),
        "excluded_sidecar_proposal_refs": [],
    }


def make_read_only_child(
    parent: dict[str, Any], raw_items: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build a synthetic child for structural diff fixtures; never publish it."""
    validate_candidate_version(parent)
    payload = parent["payload"]
    items = [
        _stored_item(payload["chapter_revision_ref"], payload["seg"], index, raw)
        for index, raw in enumerate(raw_items)
    ]
    lineage_index = [
        {
            "lineage_id": item["lineage_id"],
            "json_pointer": f"/items/{index}",
            "item_hash": item["item_hash"],
        }
        for index, item in enumerate(items)
    ]
    child_payload_without_hash = {
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
    return make_record(
        record_type="M3_CANDIDATE_VERSION",
        record_id=f"{parent['record_id']}:synthetic-child",
        record_version=2,
        payload=child_payload,
        created_at=parent["created_at"],
    )


def _record_storage_key(record: dict[str, Any]) -> str:
    return f"{record['record_type']}:{record['record_id']}:{record['record_version']}"


class FixtureStore:
    """Atomic JSON fixture store. The caller controls and isolates its directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.state_path = root / "state.json"
        self.events: list[str] = []

    @staticmethod
    def empty_state() -> dict[str, Any]:
        return {"records": {}, "pointers": {}, "operations": {}}

    def read(self) -> dict[str, Any]:
        self.events.append("fixture_storage_read")
        if not self.state_path.exists():
            return self.empty_state()
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def commit(self, state: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.root / ".state.json.pending"
        payload = json.dumps(
            _normalize(state),
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self.state_path)
        self.events.append("fixture_storage_atomic_replace")


class SegmentIndexSnapshotWriter:
    @staticmethod
    def build(**kwargs: Any) -> dict[str, Any]:
        return build_segment_index_snapshot(**kwargs)


class CandidateVersionStore:
    @staticmethod
    def build_root(**kwargs: Any) -> dict[str, Any]:
        return build_root_candidate_version(**kwargs)


class CandidatePointerSnapshotWriter:
    @staticmethod
    def build(**kwargs: Any) -> dict[str, Any]:
        return build_pointer_snapshot(**kwargs)


class VersionDiffProjector:
    @staticmethod
    def project(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
        return project_version_diff(parent, child)


class B01Service:
    def __init__(self, store: FixtureStore) -> None:
        self.store = store

    def initialize_root_baseline(
        self,
        *,
        admission: dict[str, Any],
        project_scope_id: str,
        author_workspace_logical_key: str,
        chapter_revision_ref: dict[str, Any],
        revision_text_sha256: str,
        segment_inputs: list[dict[str, Any]],
        seg: int,
        origin_attempt_refs: list[dict[str, Any]],
        raw_items: list[dict[str, Any]],
        operation_id: str,
        created_at: str,
        pointer_namespace: str = FIXTURE_POINTER_NAMESPACE,
        crash_point: str | None = None,
    ) -> dict[str, Any]:
        validate_admission(admission)
        if pointer_namespace != FIXTURE_POINTER_NAMESPACE:
            _fail("B01_POINTER_SCOPE_MISMATCH")
        if crash_point == "before_staging":
            _fail("B01_SIMULATED_CRASH", crash_point)
        segment_record = SegmentIndexSnapshotWriter.build(
            project_scope_id=project_scope_id,
            author_workspace_logical_key=author_workspace_logical_key,
            chapter_revision_ref=chapter_revision_ref,
            revision_text_sha256=revision_text_sha256,
            segment_inputs=segment_inputs,
            created_at=created_at,
        )
        validate_segment_index_snapshot(segment_record)
        if seg > len(segment_record["payload"]["segments"]):
            _fail("B01_SEGMENT_INDEX_INVALID", "selected segment")
        candidate_record = CandidateVersionStore.build_root(
            chapter_revision_ref=chapter_revision_ref,
            seg=seg,
            origin_attempt_refs=origin_attempt_refs,
            raw_items=raw_items,
            created_at=created_at,
        )
        validate_candidate_version(candidate_record)
        pointer_record = CandidatePointerSnapshotWriter.build(
            project_scope_id=project_scope_id,
            author_workspace_logical_key=author_workspace_logical_key,
            chapter_revision_ref=chapter_revision_ref,
            seg=seg,
            candidate_ref=record_ref(candidate_record),
            operation_id=operation_id,
            created_at=created_at,
        )
        validate_pointer_snapshot(pointer_record)
        request_hash = pointer_record["payload"]["snapshot_request_hash"]
        state = self.store.read()
        prior_operation = state["operations"].get(operation_id)
        if prior_operation is not None:
            if prior_operation["request_hash"] != request_hash:
                _fail("B01_OPERATION_CONFLICT")
            return deepcopy(prior_operation["result"])
        pointer_key = pointer_record["payload"]["logical_pointer_key"]
        if pointer_key in state["pointers"]:
            _fail("B01_POINTER_ALREADY_INITIALIZED")
        result = {
            "segment_index_snapshot_ref": record_ref(segment_record),
            "candidate_version_ref": record_ref(candidate_record),
            "candidate_pointer_snapshot_ref": record_ref(pointer_record),
            "logical_pointer_key": pointer_key,
        }
        staged = deepcopy(state)
        for record in (segment_record, candidate_record, pointer_record):
            staged["records"][_record_storage_key(record)] = record
        staged["pointers"][pointer_key] = record_ref(candidate_record)
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
        if reopened != staged:
            _fail("B01_TRANSACTION_READBACK_INVALID")
        return result


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
