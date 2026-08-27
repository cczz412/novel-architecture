from __future__ import annotations

import hashlib
import json
from typing import Any

ALLOWED_READ_LEDGERS = {"EXTRACTION_CORRECTION", "EXAM", "EVIDENCE_GATE", "API_EVAL"}
ALLOWED_165_TYPES = {"Attempt", "ResultVersion"}
FORBIDDEN_165_WRITE_TYPES = {"Patch", "CandidateSentence", "ResultVersionWrite"}


def sha256_utf8(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: Any) -> str:
    blob = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return sha256_utf8(blob)


def refs_error(pack: dict[str, Any]) -> str | None:
    artifacts = pack.get("artifacts") or []
    seen_raw: dict[str, str] = {}
    for art in artifacts:
        if art.get("artifact_kind") == "RAW":
            artifact_id = art["artifact_id"]
            declared = art["sha256"]
            payload = art.get("payload_utf8")
            if payload is not None and sha256_utf8(payload) != declared:
                return f"RAW_HASH_MISMATCH:{artifact_id}"
            if art.get("immutable") is not True:
                return f"RAW_NOT_IMMUTABLE:{artifact_id}"
            if artifact_id in seen_raw and seen_raw[artifact_id] != declared:
                return f"RAW_SHA256_MUTATED:{artifact_id}"
            seen_raw[artifact_id] = declared
            if art.get("update_sha256"):
                return f"RAW_SHA256_UPDATE_FORBIDDEN:{artifact_id}"

    raw_hashes = set(seen_raw.values())
    for repair in pack.get("repairs") or []:
        if "derived_from_raw_sha256" not in repair:
            return f"REPAIR_MISSING_DERIVED_FROM:{repair.get('repair_id')}"
        derived = repair.get("derived_from_raw_sha256")
        if derived not in raw_hashes:
            return f"REPAIR_DERIVED_FROM_UNKNOWN_RAW:{repair.get('repair_id')}"
        if repair.get("primary_eval_eligible") is not False:
            return f"REPAIR_CANNOT_BE_PRIMARY:{repair.get('repair_id')}"
        if repair.get("washes_raw_mechanical") is True:
            return f"REPAIR_CANNOT_WASH_RAW:{repair.get('repair_id')}"

    for review in pack.get("reviews") or []:
        if review.get("mutates_model_json") is True or review.get("rewrites_model_json") is True:
            return f"REVIEW_CANNOT_MUTATE_MODEL_JSON:{review.get('review_id')}"

    for attempt in pack.get("attempts") or []:
        if attempt.get("attempt_role") == "RETRY" and attempt.get("replaces_primary") is True:
            return f"RETRY_CANNOT_REPLACE_PRIMARY:{attempt.get('attempt_id')}"

    for ref in pack.get("foreign_refs") or []:
        if ref.get("access") != "READ_ONLY":
            return f"FOREIGN_REF_NOT_READ_ONLY:{ref.get('record_id')}"
        if ref.get("ledger") not in ALLOWED_READ_LEDGERS:
            return f"FOREIGN_REF_LEDGER:{ref.get('ledger')}"
        declared_hash = ref.get("record_hash")
        source_hash = ref.get("source_hash")
        if source_hash and declared_hash != source_hash:
            return f"PREP_STOP_HASH_MISMATCH:{ref.get('record_id')}"
        if ref.get("ledger") == "EXTRACTION_CORRECTION":
            if ref.get("record_type") in FORBIDDEN_165_WRITE_TYPES:
                return f"EVAL_CANNOT_WRITE_165:{ref.get('record_type')}"
            if ref.get("record_type") not in ALLOWED_165_TYPES:
                return f"EVAL_165_TYPE_NOT_EXPOSED:{ref.get('record_type')}"
            extra_fields = set(ref.get("requested_fields") or []) - {
                "record_id",
                "record_version",
                "record_hash",
                "status",
            }
            if extra_fields:
                return f"EVAL_165_FIELD_NOT_EXPOSED:{sorted(extra_fields)}"
        if ref.get("write_patch") is True:
            return "EVAL_CANNOT_WRITE_PATCH"
        if ref.get("drift_to_new_source_version") is True:
            return f"OLD_REF_MUST_NOT_DRIFT:{ref.get('record_id')}"

    return None
