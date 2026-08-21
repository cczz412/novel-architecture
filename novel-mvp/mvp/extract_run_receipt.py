"""M3 运行完整性回执的纯对象合同。

回执只描述一次 C2→C3 运行是否完整。它不保存原始模型正文，不替代 C3，
也不允许不完整运行成为 current C3。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any


LEDGER_SCHEMA_VERSION = "m3-fact-candidate-run-ledger-v1"
RECEIPT_SCHEMA_VERSION = "m3-fact-candidate-run-receipt-v1"
COMPLETE = "COMPLETE"
FAILURE_STATES = {
    "FAILED_TIMEOUT",
    "INCOMPLETE_TRUNCATED",
    "FAILED_TRANSPORT",
    "FAILED_RAW_RESPONSE",
    "FAILED_PROVIDER_SHAPE",
}
COMPLETION_STATES = {COMPLETE, *FAILURE_STATES}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
OPERATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")

RECEIPT_KEYS = {
    "schema_version",
    "operation_id",
    "completion_state",
    "provider_ref",
    "source_identity",
    "expected_item_keys",
    "completed_item_keys",
    "unprocessed_item_keys",
    "accepted_candidate_count",
    "attempt_count",
    "responses_identity",
    "failure",
    "candidate_snapshot",
    "ledger_parent_version",
    "candidate_parent_version",
    "request_sha256",
}
FAILURE_KEYS = {
    "code",
    "failed_item_key",
    "finish_reason",
    "raw_response_sha256",
    "raw_response_bytes",
}
IDENTITY_KEYS = {"version", "sha256"}
SOURCE_KEYS = {"segments", "chapter_index"}
RESPONSES_IDENTITY_KEYS = {"kind", "sha256", "item_keys"}
CANDIDATE_SNAPSHOT_KEYS = {"version", "sha256"}


class ExtractRunReceiptError(ValueError):
    """运行回执形状或不变式不合法。"""


def canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ExtractRunReceiptError("RUN_RECEIPT_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def payload_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _nonempty_string(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ExtractRunReceiptError(code)
    return value


def _identity(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != IDENTITY_KEYS:
        raise ExtractRunReceiptError(code)
    version = value.get("version")
    digest = value.get("sha256")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
        or not isinstance(digest, str)
        or SHA256_RE.fullmatch(digest) is None
    ):
        raise ExtractRunReceiptError(code)
    return {"version": version, "sha256": digest}


def _source_identity(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != SOURCE_KEYS:
        raise ExtractRunReceiptError("RUN_RECEIPT_SOURCE_IDENTITY_INVALID")
    return {
        key: _identity(value[key], "RUN_RECEIPT_SOURCE_IDENTITY_INVALID")
        for key in sorted(SOURCE_KEYS)
    }


def _item_keys(value: Any, code: str, *, allow_empty: bool) -> list[str]:
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or any(not isinstance(key, str) or not key or key != key.strip() for key in value)
        or len(value) != len(set(value))
    ):
        raise ExtractRunReceiptError(code)
    return list(value)


def _responses_identity(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RESPONSES_IDENTITY_KEYS:
        raise ExtractRunReceiptError("RUN_RECEIPT_RESPONSES_IDENTITY_INVALID")
    kind = _nonempty_string(
        value.get("kind"), "RUN_RECEIPT_RESPONSES_IDENTITY_INVALID"
    )
    digest = value.get("sha256")
    item_keys = _item_keys(
        value.get("item_keys"),
        "RUN_RECEIPT_RESPONSES_IDENTITY_INVALID",
        allow_empty=False,
    )
    if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
        raise ExtractRunReceiptError("RUN_RECEIPT_RESPONSES_IDENTITY_INVALID")
    if item_keys != sorted(item_keys):
        raise ExtractRunReceiptError("RUN_RECEIPT_RESPONSES_IDENTITY_INVALID")
    return {"kind": kind, "sha256": digest, "item_keys": item_keys}


def _candidate_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != CANDIDATE_SNAPSHOT_KEYS:
        raise ExtractRunReceiptError("RUN_RECEIPT_CANDIDATE_SNAPSHOT_INVALID")
    return _identity(value, "RUN_RECEIPT_CANDIDATE_SNAPSHOT_INVALID")


def _failure(value: Any, state: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FAILURE_KEYS:
        raise ExtractRunReceiptError("RUN_RECEIPT_FAILURE_INVALID")
    code = _nonempty_string(value.get("code"), "RUN_RECEIPT_FAILURE_INVALID")
    failed_item_key = value.get("failed_item_key")
    finish_reason = value.get("finish_reason")
    raw_sha = value.get("raw_response_sha256")
    raw_bytes = value.get("raw_response_bytes")
    if failed_item_key is not None:
        failed_item_key = _nonempty_string(
            failed_item_key, "RUN_RECEIPT_FAILURE_INVALID"
        )
    if finish_reason is not None:
        finish_reason = _nonempty_string(
            finish_reason, "RUN_RECEIPT_FAILURE_INVALID"
        )
    if (raw_sha is None) != (raw_bytes is None):
        raise ExtractRunReceiptError("RUN_RECEIPT_FAILURE_INVALID")
    if raw_sha is not None and (
        not isinstance(raw_sha, str)
        or SHA256_RE.fullmatch(raw_sha) is None
        or isinstance(raw_bytes, bool)
        or not isinstance(raw_bytes, int)
        or raw_bytes < 0
    ):
        raise ExtractRunReceiptError("RUN_RECEIPT_FAILURE_INVALID")
    if state in {"INCOMPLETE_TRUNCATED", "FAILED_RAW_RESPONSE"} and raw_sha is None:
        raise ExtractRunReceiptError("RUN_RECEIPT_RAW_RESPONSE_IDENTITY_REQUIRED")
    return {
        "code": code,
        "failed_item_key": failed_item_key,
        "finish_reason": finish_reason,
        "raw_response_sha256": raw_sha,
        "raw_response_bytes": raw_bytes,
    }


def _request_sha_payload(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in receipt.items()
        if key != "request_sha256"
    }


def validate_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RECEIPT_KEYS:
        raise ExtractRunReceiptError("RUN_RECEIPT_SHAPE_INVALID")
    if value.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise ExtractRunReceiptError("RUN_RECEIPT_SCHEMA_INVALID")
    operation_id = value.get("operation_id")
    if not isinstance(operation_id, str) or OPERATION_ID_RE.fullmatch(operation_id) is None:
        raise ExtractRunReceiptError("RUN_RECEIPT_OPERATION_ID_INVALID")
    state = value.get("completion_state")
    if not isinstance(state, str) or state not in COMPLETION_STATES:
        raise ExtractRunReceiptError("RUN_RECEIPT_COMPLETION_STATE_INVALID")
    provider_ref = _nonempty_string(
        value.get("provider_ref"), "RUN_RECEIPT_PROVIDER_REF_INVALID"
    )
    source_identity = _source_identity(value.get("source_identity"))
    expected = _item_keys(
        value.get("expected_item_keys"),
        "RUN_RECEIPT_EXPECTED_ITEMS_INVALID",
        allow_empty=False,
    )
    completed = _item_keys(
        value.get("completed_item_keys"),
        "RUN_RECEIPT_COMPLETED_ITEMS_INVALID",
        allow_empty=True,
    )
    unprocessed = _item_keys(
        value.get("unprocessed_item_keys"),
        "RUN_RECEIPT_UNPROCESSED_ITEMS_INVALID",
        allow_empty=True,
    )
    if completed + unprocessed != expected:
        raise ExtractRunReceiptError("RUN_RECEIPT_ITEM_PARTITION_INVALID")
    accepted = value.get("accepted_candidate_count")
    attempt_count = value.get("attempt_count")
    ledger_parent = value.get("ledger_parent_version")
    candidate_parent = value.get("candidate_parent_version")
    if (
        isinstance(accepted, bool)
        or not isinstance(accepted, int)
        or accepted < 0
        or attempt_count != 1
        or isinstance(ledger_parent, bool)
        or not isinstance(ledger_parent, int)
        or ledger_parent < 0
    ):
        raise ExtractRunReceiptError("RUN_RECEIPT_COUNTER_INVALID")
    if candidate_parent is not None and (
        isinstance(candidate_parent, bool)
        or not isinstance(candidate_parent, int)
        or candidate_parent < 0
    ):
        raise ExtractRunReceiptError("RUN_RECEIPT_COUNTER_INVALID")

    responses_identity = value.get("responses_identity")
    failure = value.get("failure")
    candidate_snapshot = value.get("candidate_snapshot")
    if state == COMPLETE:
        responses_identity = _responses_identity(responses_identity)
        candidate_snapshot = _candidate_snapshot(candidate_snapshot)
        if (
            failure is not None
            or completed != expected
            or unprocessed
            or candidate_parent is None
            or candidate_snapshot["version"] != candidate_parent + 1
            or responses_identity["item_keys"] != sorted(expected)
        ):
            raise ExtractRunReceiptError("RUN_RECEIPT_COMPLETE_INVARIANT_FAILED")
    else:
        if responses_identity is not None or candidate_snapshot is not None or candidate_parent is not None:
            raise ExtractRunReceiptError("RUN_RECEIPT_FAILURE_INVARIANT_FAILED")
        failure = _failure(failure, state)
        failed_item_key = failure["failed_item_key"]
        if failed_item_key is not None:
            if not unprocessed or unprocessed[0] != failed_item_key:
                raise ExtractRunReceiptError("RUN_RECEIPT_FAILED_ITEM_INVALID")
        elif completed:
            raise ExtractRunReceiptError("RUN_RECEIPT_FAILED_ITEM_INVALID")

    normalized = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "operation_id": operation_id,
        "completion_state": state,
        "provider_ref": provider_ref,
        "source_identity": source_identity,
        "expected_item_keys": expected,
        "completed_item_keys": completed,
        "unprocessed_item_keys": unprocessed,
        "accepted_candidate_count": accepted,
        "attempt_count": 1,
        "responses_identity": responses_identity,
        "failure": failure,
        "candidate_snapshot": candidate_snapshot,
        "ledger_parent_version": ledger_parent,
        "candidate_parent_version": candidate_parent,
        "request_sha256": value.get("request_sha256"),
    }
    request_sha = normalized["request_sha256"]
    expected_request_sha = payload_sha256(_request_sha_payload(normalized))
    if request_sha != expected_request_sha:
        raise ExtractRunReceiptError("RUN_RECEIPT_REQUEST_SHA_INVALID")
    return copy.deepcopy(normalized)


def _with_request_sha(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt = copy.deepcopy(receipt)
    receipt["request_sha256"] = payload_sha256(_request_sha_payload(receipt))
    return validate_receipt(receipt)


def build_complete_receipt(
    *,
    operation_id: str,
    provider_ref: str,
    source_identity: dict[str, Any],
    expected_item_keys: list[str],
    accepted_candidate_count: int,
    responses_identity: dict[str, Any],
    candidate_snapshot: dict[str, Any],
    ledger_parent_version: int,
    candidate_parent_version: int,
) -> dict[str, Any]:
    return _with_request_sha(
        {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "operation_id": operation_id,
            "completion_state": COMPLETE,
            "provider_ref": provider_ref,
            "source_identity": copy.deepcopy(source_identity),
            "expected_item_keys": list(expected_item_keys),
            "completed_item_keys": list(expected_item_keys),
            "unprocessed_item_keys": [],
            "accepted_candidate_count": accepted_candidate_count,
            "attempt_count": 1,
            "responses_identity": copy.deepcopy(responses_identity),
            "failure": None,
            "candidate_snapshot": copy.deepcopy(candidate_snapshot),
            "ledger_parent_version": ledger_parent_version,
            "candidate_parent_version": candidate_parent_version,
            "request_sha256": "",
        }
    )


def build_failure_receipt(
    *,
    operation_id: str,
    completion_state: str,
    provider_ref: str,
    source_identity: dict[str, Any],
    expected_item_keys: list[str],
    completed_item_keys: list[str],
    accepted_candidate_count: int,
    failure: dict[str, Any],
    ledger_parent_version: int,
) -> dict[str, Any]:
    return _with_request_sha(
        {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "operation_id": operation_id,
            "completion_state": completion_state,
            "provider_ref": provider_ref,
            "source_identity": copy.deepcopy(source_identity),
            "expected_item_keys": list(expected_item_keys),
            "completed_item_keys": list(completed_item_keys),
            "unprocessed_item_keys": list(
                expected_item_keys[len(completed_item_keys) :]
            ),
            "accepted_candidate_count": accepted_candidate_count,
            "attempt_count": 1,
            "responses_identity": None,
            "failure": copy.deepcopy(failure),
            "candidate_snapshot": None,
            "ledger_parent_version": ledger_parent_version,
            "candidate_parent_version": None,
            "request_sha256": "",
        }
    )


def empty_ledger() -> dict[str, Any]:
    return {"schema_version": LEDGER_SCHEMA_VERSION, "runs": []}


def validate_ledger(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "runs"}
        or value.get("schema_version") != LEDGER_SCHEMA_VERSION
        or not isinstance(value.get("runs"), list)
    ):
        raise ExtractRunReceiptError("RUN_LEDGER_INVALID")
    runs = [validate_receipt(row) for row in value["runs"]]
    operation_ids = [row["operation_id"] for row in runs]
    if len(operation_ids) != len(set(operation_ids)):
        raise ExtractRunReceiptError("RUN_LEDGER_OPERATION_DUPLICATE")
    if any(
        receipt["ledger_parent_version"] != index
        for index, receipt in enumerate(runs)
    ):
        raise ExtractRunReceiptError("RUN_LEDGER_PARENT_VERSION_INVALID")
    return {"schema_version": LEDGER_SCHEMA_VERSION, "runs": runs}
