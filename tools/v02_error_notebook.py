#!/usr/bin/env python3
"""Offline, append-only error notebook for extraction-redesign v0.2.

The notebook stores only seven machine-readable fields:

* error candidate id;
* candidate SHA-256;
* B2 failure fine code;
* the corresponding one of six B2 routes;
* a symbolic program assertion;
* an error-candidate-only status;
* source receipt SHA-256.

It deliberately has no place for novel text, formal-gold answers, quotes,
secrets, or full human verdicts.  Every input is leak-scanned before contract
validation.  This module is not connected to any active runner and performs no
semantic repair or truth promotion.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_DIR = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "B4_3_error_notebook"
)
DEFAULT_FAILURE_MAP_PATH = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "B2_gate_contract_v0.1"
    / "examples"
    / "valid"
    / "failure_code_map.json"
)

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
CANDIDATE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
ASSERTION_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,95}$")

ROUTE_IDS = (
    "STRUCTURE",
    "BOUNDARY",
    "FACT",
    "QUALIFIER",
    "ANCHOR",
    "PROVENANCE_BUDGET",
)
ERROR_STATUSES = (
    "RECORDED_ERROR_CANDIDATE",
    "QUARANTINED_ERROR_CANDIDATE",
    "RETIRED_ERROR_CANDIDATE",
)
ENTRY_FIELDS = (
    "error_candidate_id",
    "candidate_sha256",
    "failure_fine_code",
    "failure_route",
    "program_assertion",
    "status",
    "source_receipt_sha256",
)

# Keys are normalized to lowercase ASCII letters and digits before matching.
# These tokens are intentionally broader than the schema: a prohibited key is
# rejected by the leak scanner before the ordinary unknown-field check.
FORBIDDEN_KEY_TOKENS = (
    "answer",
    "quote",
    "excerpt",
    "verbatim",
    "plaintext",
    "sourcetext",
    "noveltext",
    "chaptertext",
    "body",
    "content",
    "corpus",
    "formalgold",
    "goldanswer",
    "prompt",
    "completion",
    "response",
    "apikey",
    "accesskey",
    "privatekey",
    "secret",
    "password",
    "passwd",
    "accesstoken",
    "refreshtoken",
    "humanjudgment",
    "humanjudgement",
    "humanverdict",
    "manualjudgment",
    "manualjudgement",
    "manualverdict",
    "rationale",
    "reasoning",
)

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|secret|password|passwd)"
        r"\b\s*[:=]\s*[\"']?[^,\s\"']{8,}",
        re.IGNORECASE,
    ),
)


class ErrorNotebookError(ValueError):
    """Base exception for an error-notebook contract violation."""


class LeakageRejectedError(ErrorNotebookError):
    """Raised before schema validation when input may contain forbidden data."""


class ContractValidationError(ErrorNotebookError):
    """Raised when a leak-free object violates the strict entry contract."""


class DuplicateIdentityError(ErrorNotebookError):
    """Raised when append-only identity or de-duplication rules are violated."""


@dataclass(frozen=True)
class FailureAllowlist:
    """Validated read-only projection of the B2 failure-code map."""

    fine_to_route: dict[str, str]
    source_sha256: str
    contract_hash: str


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _ledger_line(value: Mapping[str, str]) -> bytes:
    return _canonical_bytes(value) + b"\n"


def _tree_hash(artifacts: Mapping[str, bytes]) -> str:
    inventory = [
        {"path": path, "bytes": len(data), "sha256": _sha256(data)}
        for path, data in sorted(artifacts.items())
    ]
    return _sha256(_canonical_bytes(inventory))


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractValidationError("duplicate JSON key rejected")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ContractValidationError(f"non-finite JSON number rejected: {value}")


def strict_json_loads(raw: bytes) -> Any:
    """Decode strict JSON without duplicate keys or non-finite numbers."""

    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ContractValidationError("input must be valid UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except ErrorNotebookError:
        raise
    except json.JSONDecodeError as exc:
        raise ContractValidationError("input must be one complete JSON object") from exc


def _normalized_key(key: str) -> str:
    return "".join(character for character in key.lower() if character.isalnum())


def _scan_raw_for_secret(raw: bytes) -> str:
    """First-pass scan that never echoes a possible secret in an error."""

    if b"\x00" in raw:
        raise LeakageRejectedError("NUL byte rejected by leak scanner")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise LeakageRejectedError("non-UTF-8 input rejected by leak scanner") from exc
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise LeakageRejectedError("secret-like value rejected by leak scanner")
    return text


def _scan_value_for_leak(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise LeakageRejectedError("non-string key rejected by leak scanner")
            normalized = _normalized_key(key)
            if any(token in normalized for token in FORBIDDEN_KEY_TOKENS):
                raise LeakageRejectedError(
                    f"forbidden field rejected by leak scanner: {key}"
                )
            _scan_value_for_leak(child)
        return
    if isinstance(value, list):
        for child in value:
            _scan_value_for_leak(child)
        return
    if not isinstance(value, str):
        return
    for pattern in SECRET_PATTERNS:
        if pattern.search(value):
            raise LeakageRejectedError("secret-like value rejected by leak scanner")
    if len(value) > 160:
        raise LeakageRejectedError("long free-text-like value rejected by leak scanner")
    if any(character.isspace() for character in value):
        raise LeakageRejectedError("whitespace prose-like value rejected by leak scanner")
    if any(ord(character) > 127 for character in value):
        raise LeakageRejectedError("non-ASCII prose-like value rejected by leak scanner")
    if "://" in value:
        raise LeakageRejectedError("URL-like value rejected; store only its receipt SHA")


def leak_scan_and_load(raw: bytes) -> Any:
    """Run the strict leak scan before returning parsed JSON."""

    _scan_raw_for_secret(raw)
    value = strict_json_loads(raw)
    _scan_value_for_leak(value)
    return value


def load_failure_allowlist(
    path: Path = DEFAULT_FAILURE_MAP_PATH,
) -> FailureAllowlist:
    """Read and validate B2's frozen fine-code map without modifying it."""

    raw = path.read_bytes()
    value = strict_json_loads(raw)
    if not isinstance(value, dict):
        raise ContractValidationError("B2 failure map must be an object")
    contract_hash = value.get("contract_hash")
    rows = value.get("fine_codes")
    routing = value.get("routing_categories")
    if not isinstance(contract_hash, str) or not HEX64_RE.fullmatch(contract_hash):
        raise ContractValidationError("B2 contract_hash must be lowercase SHA-256")
    if not isinstance(rows, list) or not rows:
        raise ContractValidationError("B2 fine_codes must be a non-empty list")
    if not isinstance(routing, list):
        raise ContractValidationError("B2 routing_categories must be a list")
    listed_routes = tuple(
        item.get("route_id") for item in routing if isinstance(item, dict)
    )
    if listed_routes != ROUTE_IDS:
        raise ContractValidationError("B2 six-route order or coverage changed")

    fine_to_route: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ContractValidationError("B2 fine-code row must be an object")
        fine_code = row.get("fine_code")
        route = row.get("normalized_route")
        if not isinstance(fine_code, str) or not ASSERTION_RE.fullmatch(fine_code):
            raise ContractValidationError("B2 fine code has an invalid identifier")
        if route not in ROUTE_IDS:
            raise ContractValidationError("B2 fine code has an unknown route")
        if fine_code in fine_to_route:
            raise ContractValidationError("B2 fine code is duplicated")
        fine_to_route[fine_code] = route
    if len(fine_to_route) != 69:
        raise ContractValidationError("B2 fine-code count must remain 69")
    return FailureAllowlist(
        fine_to_route=fine_to_route,
        source_sha256=_sha256(raw),
        contract_hash=contract_hash,
    )


def build_schema(allowlist: FailureAllowlist) -> dict[str, Any]:
    """Build the strict JSON Schema for one notebook line."""

    return {
        "$schema": DRAFT_2020_12,
        "$id": "https://local.invalid/v02/error_notebook_entry.schema.json",
        "title": "v0.2 error notebook entry",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "error_candidate_id": {
                "type": "string",
                "minLength": 3,
                "maxLength": 128,
                "pattern": CANDIDATE_ID_RE.pattern,
            },
            "candidate_sha256": {
                "type": "string",
                "pattern": HEX64_RE.pattern,
            },
            "failure_fine_code": {
                "type": "string",
                "enum": list(allowlist.fine_to_route),
            },
            "failure_route": {
                "type": "string",
                "enum": list(ROUTE_IDS),
            },
            "program_assertion": {
                "type": "string",
                "minLength": 3,
                "maxLength": 96,
                "pattern": ASSERTION_RE.pattern,
            },
            "status": {
                "type": "string",
                "enum": list(ERROR_STATUSES),
            },
            "source_receipt_sha256": {
                "type": "string",
                "pattern": HEX64_RE.pattern,
            },
        },
        "required": list(ENTRY_FIELDS),
        "allOf": [
            {
                "if": {
                    "properties": {
                        "failure_fine_code": {
                            "enum": [
                                fine_code
                                for fine_code, mapped_route in (
                                    allowlist.fine_to_route.items()
                                )
                                if mapped_route == route
                            ]
                        }
                    },
                    "required": ["failure_fine_code"],
                },
                "then": {
                    "properties": {
                        "failure_route": {
                            "const": route,
                        }
                    },
                    "required": ["failure_route"],
                },
            }
            for route in ROUTE_IDS
        ],
    }


def validate_entry(
    entry: Any,
    allowlist: FailureAllowlist | None = None,
) -> dict[str, str]:
    """Leak-scan and validate one in-memory entry."""

    _scan_value_for_leak(entry)
    if allowlist is None:
        allowlist = load_failure_allowlist()
    if not isinstance(entry, dict):
        raise ContractValidationError("entry must be one JSON object")
    actual_fields = set(entry)
    expected_fields = set(ENTRY_FIELDS)
    if actual_fields != expected_fields:
        missing = sorted(expected_fields - actual_fields)
        unknown = sorted(actual_fields - expected_fields)
        raise ContractValidationError(
            f"entry fields mismatch; missing={missing}; unknown={unknown}"
        )
    if any(not isinstance(entry[field], str) for field in ENTRY_FIELDS):
        raise ContractValidationError("all seven entry fields must be strings")

    error_candidate_id = entry["error_candidate_id"]
    candidate_sha256 = entry["candidate_sha256"]
    failure_fine_code = entry["failure_fine_code"]
    failure_route = entry["failure_route"]
    program_assertion = entry["program_assertion"]
    status = entry["status"]
    source_receipt_sha256 = entry["source_receipt_sha256"]

    if not CANDIDATE_ID_RE.fullmatch(error_candidate_id):
        raise ContractValidationError("error_candidate_id has an invalid identifier")
    if not HEX64_RE.fullmatch(candidate_sha256):
        raise ContractValidationError("candidate_sha256 must be lowercase SHA-256")
    if failure_fine_code not in allowlist.fine_to_route:
        raise ContractValidationError("failure_fine_code is not in the B2 allowlist")
    expected_route = allowlist.fine_to_route[failure_fine_code]
    if failure_route != expected_route:
        raise ContractValidationError(
            "failure_route does not match the B2 fine-code mapping"
        )
    if not ASSERTION_RE.fullmatch(program_assertion):
        raise ContractValidationError("program_assertion must be a symbolic identifier")
    if status not in ERROR_STATUSES:
        raise ContractValidationError("status cannot activate or promote a candidate")
    if not HEX64_RE.fullmatch(source_receipt_sha256):
        raise ContractValidationError(
            "source_receipt_sha256 must be lowercase SHA-256"
        )
    return {field: entry[field] for field in ENTRY_FIELDS}


def load_entry_bytes(
    raw: bytes,
    allowlist: FailureAllowlist | None = None,
) -> dict[str, str]:
    """Leak-scan raw input, then parse and validate it."""

    value = leak_scan_and_load(raw)
    return validate_entry(value, allowlist)


def dedupe_identity(entry: Mapping[str, str]) -> tuple[str, str, str]:
    """Return the immutable failure fingerprint used for de-duplication."""

    return (
        entry["candidate_sha256"],
        entry["failure_fine_code"],
        entry["program_assertion"],
    )


def validate_entry_sequence(entries: Sequence[Mapping[str, str]]) -> None:
    """Enforce one-to-one candidate binding and no repeated failure identity."""

    candidate_to_sha: dict[str, str] = {}
    sha_to_candidate: dict[str, str] = {}
    seen_failures: set[tuple[str, str, str]] = set()
    for entry in entries:
        candidate_id = entry["error_candidate_id"]
        candidate_sha = entry["candidate_sha256"]
        prior_sha = candidate_to_sha.setdefault(candidate_id, candidate_sha)
        if prior_sha != candidate_sha:
            raise DuplicateIdentityError(
                "error_candidate_id cannot be rebound to another SHA"
            )
        prior_candidate = sha_to_candidate.setdefault(candidate_sha, candidate_id)
        if prior_candidate != candidate_id:
            raise DuplicateIdentityError(
                "candidate SHA cannot be rebound to another error_candidate_id"
            )
        identity = dedupe_identity(entry)
        if identity in seen_failures:
            raise DuplicateIdentityError(
                "duplicate candidate SHA + fine code + program assertion rejected"
            )
        seen_failures.add(identity)


def read_ledger_bytes(
    raw: bytes,
    allowlist: FailureAllowlist | None = None,
) -> list[dict[str, str]]:
    """Validate and read a complete JSONL ledger without modifying it."""

    if allowlist is None:
        allowlist = load_failure_allowlist()
    if not raw:
        return []
    _scan_raw_for_secret(raw)
    if b"\r" in raw:
        raise ContractValidationError("ledger must use LF line endings")
    if not raw.endswith(b"\n"):
        raise ContractValidationError("ledger has an incomplete final line")
    lines = raw[:-1].split(b"\n")
    if any(not line for line in lines):
        raise ContractValidationError("blank ledger lines are forbidden")
    entries = [load_entry_bytes(line, allowlist) for line in lines]
    validate_entry_sequence(entries)
    return entries


def read_ledger(
    ledger_path: Path,
    failure_map_path: Path = DEFAULT_FAILURE_MAP_PATH,
) -> list[dict[str, str]]:
    """Read and validate an append-only JSONL ledger."""

    allowlist = load_failure_allowlist(failure_map_path)
    return read_ledger_bytes(ledger_path.read_bytes(), allowlist)


def validate_ledger(
    ledger_path: Path,
    failure_map_path: Path = DEFAULT_FAILURE_MAP_PATH,
) -> dict[str, Any]:
    """Return a safe validation receipt for a JSONL ledger."""

    entries = read_ledger(ledger_path, failure_map_path)
    return {
        "result": "PASS",
        "entry_count": len(entries),
        "unique_failure_identity_count": len(
            {dedupe_identity(entry) for entry in entries}
        ),
        "truth_promotion_allowed": False,
        "semantic_auto_repair": False,
    }


def append_entry(
    ledger_path: Path,
    entry: Any,
    failure_map_path: Path = DEFAULT_FAILURE_MAP_PATH,
) -> dict[str, Any]:
    """Validate and append exactly one line while preserving all prior bytes."""

    allowlist = load_failure_allowlist(failure_map_path)
    validated = validate_entry(entry, allowlist)
    line = _ledger_line(validated)
    # Re-parse the exact bytes that will be persisted, so dict callers cannot
    # bypass the raw-input scanner.
    persisted = load_entry_bytes(line, allowlist)

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
    descriptor = os.open(ledger_path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "r+b", buffering=0) as handle:
            descriptor = -1
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            prior = handle.read()
            existing = read_ledger_bytes(prior, allowlist)
            validate_entry_sequence([*existing, persisted])
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return {
        "result": "APPENDED",
        "entry_count": len(existing) + 1,
        "dedupe_identity": list(dedupe_identity(persisted)),
        "prior_bytes_preserved": True,
        "truth_promotion_allowed": False,
    }


def valid_example() -> dict[str, str]:
    return {
        "error_candidate_id": "B4-3-CANDIDATE-001",
        "candidate_sha256": "1" * 64,
        "failure_fine_code": "H01_ATOMIC_BOUNDARY",
        "failure_route": "BOUNDARY",
        "program_assertion": "ASSERT_ATOMIC_BOUNDARY_FAILED",
        "status": "RECORDED_ERROR_CANDIDATE",
        "source_receipt_sha256": "2" * 64,
    }


def invalid_example() -> dict[str, str]:
    value = valid_example()
    value["quote"] = "SYNTHETIC_CANARY_NOT_SOURCE_TEXT"
    return value


def run_canary(
    allowlist: FailureAllowlist | None = None,
) -> dict[str, Any]:
    """Exercise rejection paths with synthetic, non-source values in memory."""

    if allowlist is None:
        allowlist = load_failure_allowlist()
    base = valid_example()
    cases: list[tuple[str, Any, type[ErrorNotebookError]]] = []

    forbidden_field = copy.deepcopy(base)
    forbidden_field["answer"] = "SYNTHETIC_CANARY"
    cases.append(("FORBIDDEN_FIELD", forbidden_field, LeakageRejectedError))

    prose_like = copy.deepcopy(base)
    prose_like["error_candidate_id"] = "CANARY。SYNTHETIC"
    cases.append(("SUSPECTED_BODY", prose_like, LeakageRejectedError))

    secret_like = copy.deepcopy(base)
    secret_like["program_assertion"] = "Bearer SYNTHETIC_CANARY_123456"
    cases.append(("SUSPECTED_SECRET", secret_like, LeakageRejectedError))

    unknown_code = copy.deepcopy(base)
    unknown_code["failure_fine_code"] = "UNKNOWN_FINE_CODE"
    cases.append(("UNKNOWN_FINE_CODE", unknown_code, ContractValidationError))

    wrong_route = copy.deepcopy(base)
    wrong_route["failure_route"] = "FACT"
    cases.append(("ROUTE_MISMATCH", wrong_route, ContractValidationError))

    active_status = copy.deepcopy(base)
    active_status["status"] = "ACTIVE"
    cases.append(("TRUTH_PROMOTION_STATUS", active_status, ContractValidationError))

    results: list[dict[str, str]] = []
    for case_id, candidate, expected_error in cases:
        try:
            validate_entry(candidate, allowlist)
        except expected_error:
            results.append({"case_id": case_id, "result": "REJECTED_AS_EXPECTED"})
        else:
            raise AssertionError(f"canary did not reject {case_id}")

    try:
        validated = validate_entry(base, allowlist)
        validate_entry_sequence([validated, copy.deepcopy(validated)])
    except DuplicateIdentityError:
        results.append(
            {"case_id": "DUPLICATE_IDENTITY", "result": "REJECTED_AS_EXPECTED"}
        )
    else:
        raise AssertionError("canary did not reject duplicate identity")

    return {
        "canary_id": "B4_3_ERROR_NOTEBOOK_LEAK_AND_IDENTITY_CANARY_V1",
        "result": "PASS",
        "case_count": len(results),
        "passed_count": len(results),
        "cases": results,
        "runtime_inputs_persisted": False,
        "real_secret_or_novel_text_used": False,
    }


def _readme_text() -> bytes:
    return """# B4.3 错题本最小版

✅ 这是一份离线、只追加的错误候选索引，不是答案库，也不是真值库。

每一行只准保存 7 项：错误候选身份、候选 SHA、B2 失败细码、对应六类码、程序断言代号、错误候选状态、来源票据 SHA。没有原文、答案、短引、正文、密钥和人工判词的位置。

写入顺序固定为：泄漏扫描 → 严格字段检查 → B2 细码与六类码核对 → 候选身份与重复项检查 → 只追加写入。任一步失败都不落盘。

候选身份由“错误候选身份＋候选 SHA”共同绑定；任一边不能换绑。重复项按“候选 SHA＋失败细码＋程序断言”识别，换状态或来源票据 SHA 不能绕过去再写一遍。

这份候选没有接现役运行器，不自动修复语义，也不能把错误候选升成正式真值。

来源：Codex
""".encode("utf-8")


def build_artifacts(
    failure_map_path: Path = DEFAULT_FAILURE_MAP_PATH,
) -> dict[str, bytes]:
    """Build the complete deterministic B4.3 candidate bundle."""

    allowlist = load_failure_allowlist(failure_map_path)
    schema = build_schema(allowlist)
    good = validate_entry(valid_example(), allowlist)
    bad = invalid_example()
    try:
        validate_entry(bad, allowlist)
    except LeakageRejectedError:
        invalid_rejected = True
    else:
        invalid_rejected = False
    if not invalid_rejected:
        raise AssertionError("checked-in invalid example must be rejected")
    canary = run_canary(allowlist)
    sample_ledger = _ledger_line(good)
    parsed_sample = read_ledger_bytes(sample_ledger, allowlist)
    if parsed_sample != [good]:
        raise AssertionError("sample ledger readback changed the entry")

    canary_plan = {
        "schema_version": "v02-b4-3-error-notebook-canary-v1",
        "canary_id": canary["canary_id"],
        "case_ids": [item["case_id"] for item in canary["cases"]],
        "expected_result": "ALL_REJECTED",
        "runtime_inputs_generated_in_memory": True,
        "runtime_inputs_persisted": False,
        "real_secret_or_novel_text_used": False,
    }
    acceptance = {
        "schema_version": "v02-b4-3-error-notebook-acceptance-v0.1",
        "candidate_id": "B4_3_error_notebook",
        "candidate_status": "candidate_silver_not_active",
        "result": "PASS_ENGINEERING_CANDIDATE_ONLY",
        "checks": {
            "strict_schema": True,
            "allowed_entry_field_count": len(ENTRY_FIELDS),
            "b2_fine_code_count": len(allowlist.fine_to_route),
            "six_route_count": len(ROUTE_IDS),
            "valid_example_accepted": True,
            "invalid_example_rejected_before_schema": invalid_rejected,
            "sample_append_only_ledger_readback": True,
            "canary_cases_passed": canary["passed_count"],
            "dedupe_identity_rule_active": True,
        },
        "storage_boundary": {
            "allowed_fields": list(ENTRY_FIELDS),
            "free_text_fields": 0,
            "candidate_statuses_only": list(ERROR_STATUSES),
            "truth_promotion_allowed": False,
            "semantic_auto_repair": False,
            "active_runner_connected": False,
        },
        "source_allowlist": {
            "kind": "B2_FINE_CODE_MAP_READ_ONLY",
            "sha256": allowlist.source_sha256,
            "contract_hash": allowlist.contract_hash,
        },
        "scope": {
            "model_api_calls": 0,
            "network_requests": 0,
            "notion_writes": 0,
            "current_state_mutations": 0,
            "formal_gold_mutations": 0,
            "default_route_mutations": 0,
            "outbox_mutations": 0,
        },
    }
    base_artifacts = {
        "README.md": _readme_text(),
        "acceptance_receipt.json": _json_bytes(acceptance),
        "canary/canary_plan.json": _json_bytes(canary_plan),
        "canary/canary_receipt.json": _json_bytes(canary),
        "examples/invalid/forbidden_quote_field.json": _json_bytes(bad),
        "examples/valid/error_entry.json": _json_bytes(good),
        "notebook.jsonl": sample_ledger,
        "schemas/error_notebook_entry.schema.json": _json_bytes(schema),
    }
    artifact_tree_sha256 = _tree_hash(base_artifacts)
    inventory = [
        {"path": path, "bytes": len(data), "sha256": _sha256(data)}
        for path, data in sorted(base_artifacts.items())
    ]
    manifest = {
        "schema_version": "v02-b4-3-error-notebook-manifest-v0.1",
        "candidate_id": "B4_3_error_notebook",
        "candidate_status": "candidate_silver_not_active",
        "artifact_count": len(inventory),
        "artifacts": inventory,
        "bundle_content_hash": artifact_tree_sha256,
        "contract": {
            "allowed_entry_fields": list(ENTRY_FIELDS),
            "failure_code_source": (
                "B2_gate_contract_v0.1/examples/valid/failure_code_map.json"
            ),
            "failure_code_source_sha256": allowlist.source_sha256,
            "failure_code_contract_hash": allowlist.contract_hash,
            "failure_code_count": len(allowlist.fine_to_route),
            "route_ids": list(ROUTE_IDS),
            "unknown_fine_code_policy": "REJECT",
            "route_mismatch_policy": "REJECT",
        },
        "append_only_identity_rule": {
            "candidate_binding": [
                "error_candidate_id",
                "candidate_sha256",
            ],
            "dedupe_key": [
                "candidate_sha256",
                "failure_fine_code",
                "program_assertion",
            ],
            "status_or_receipt_change_creates_new_identity": False,
        },
        "release_isolation": {
            "activation_allowed": False,
            "active_runner_connected": False,
            "semantic_auto_repair": False,
            "truth_promotion_allowed": False,
            "formal_gold_changed": False,
            "default_chain_changed": False,
            "current_state_changed": False,
        },
        "scope": acceptance["scope"],
    }
    without_double_run = {
        **base_artifacts,
        "manifest.json": _json_bytes(manifest),
    }
    full_tree_sha256 = _tree_hash(without_double_run)
    double_run_receipt = {
        "schema_version": "v02-b4-3-double-run-receipt-v0.1",
        "result": "PASS",
        "byte_identical": True,
        "compared_file_count": len(without_double_run),
        "hash_scope": "ALL_BUNDLE_FILES_EXCEPT_DOUBLE_RUN_RECEIPT",
        "pass1_tree_sha256": full_tree_sha256,
        "pass2_tree_sha256": full_tree_sha256,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    return {
        **without_double_run,
        "double_run_receipt.json": _json_bytes(double_run_receipt),
    }


def write_artifacts(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    """Write only the controlled bundle paths; never delete unrelated files."""

    output_dir.mkdir(parents=True, exist_ok=True)
    existing = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    unexpected = existing - set(artifacts)
    if unexpected:
        raise ErrorNotebookError(
            f"refusing to overwrite bundle with unexpected files: {sorted(unexpected)}"
        )
    for relative_path, data in sorted(artifacts.items()):
        target = output_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def check_bundle(
    bundle_dir: Path = DEFAULT_BUNDLE_DIR,
    failure_map_path: Path = DEFAULT_FAILURE_MAP_PATH,
) -> dict[str, Any]:
    """Compare a bundle to a fresh deterministic build and validate its ledger."""

    expected = build_artifacts(failure_map_path)
    actual_names = {
        path.relative_to(bundle_dir).as_posix()
        for path in bundle_dir.rglob("*")
        if path.is_file()
    }
    if actual_names != set(expected):
        raise ErrorNotebookError(
            "bundle file set differs from the deterministic contract"
        )
    for relative_path, expected_bytes in expected.items():
        actual = (bundle_dir / relative_path).read_bytes()
        if actual != expected_bytes:
            raise ErrorNotebookError(f"bundle artifact drift: {relative_path}")
    ledger_receipt = validate_ledger(
        bundle_dir / "notebook.jsonl",
        failure_map_path,
    )
    return {
        "result": "PASS",
        "file_count": len(expected),
        "tree_sha256": _tree_hash(expected),
        "ledger_entry_count": ledger_receipt["entry_count"],
        "candidate_status": "candidate_silver_not_active",
        "truth_promotion_allowed": False,
    }


def double_run(
    failure_map_path: Path = DEFAULT_FAILURE_MAP_PATH,
) -> dict[str, Any]:
    """Build twice in isolated directories and compare every byte."""

    first = build_artifacts(failure_map_path)
    second = build_artifacts(failure_map_path)
    with tempfile.TemporaryDirectory() as first_tmp:
        with tempfile.TemporaryDirectory() as second_tmp:
            first_dir = Path(first_tmp)
            second_dir = Path(second_tmp)
            write_artifacts(first_dir, first)
            write_artifacts(second_dir, second)
            first_bytes = {
                path.relative_to(first_dir).as_posix(): path.read_bytes()
                for path in first_dir.rglob("*")
                if path.is_file()
            }
            second_bytes = {
                path.relative_to(second_dir).as_posix(): path.read_bytes()
                for path in second_dir.rglob("*")
                if path.is_file()
            }
    byte_identical = first_bytes == second_bytes
    if not byte_identical:
        raise ErrorNotebookError("isolated builds are not byte-identical")
    first_scope = {
        path: data
        for path, data in first_bytes.items()
        if path != "double_run_receipt.json"
    }
    second_scope = {
        path: data
        for path, data in second_bytes.items()
        if path != "double_run_receipt.json"
    }
    return {
        "schema_version": "v02-b4-3-double-run-receipt-v0.1",
        "result": "PASS",
        "byte_identical": True,
        "compared_file_count": len(first_scope),
        "hash_scope": "ALL_BUNDLE_FILES_EXCEPT_DOUBLE_RUN_RECEIPT",
        "pass1_tree_sha256": _tree_hash(first_scope),
        "pass2_tree_sha256": _tree_hash(second_scope),
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument(
        "--output-dir",
        type=_path,
        default=DEFAULT_BUNDLE_DIR,
    )
    build_parser.add_argument(
        "--failure-map",
        type=_path,
        default=DEFAULT_FAILURE_MAP_PATH,
    )

    validate_bundle_parser = subparsers.add_parser("validate-bundle")
    validate_bundle_parser.add_argument(
        "--bundle-dir",
        type=_path,
        default=DEFAULT_BUNDLE_DIR,
    )
    validate_bundle_parser.add_argument(
        "--failure-map",
        type=_path,
        default=DEFAULT_FAILURE_MAP_PATH,
    )

    double_run_parser = subparsers.add_parser("double-run")
    double_run_parser.add_argument(
        "--failure-map",
        type=_path,
        default=DEFAULT_FAILURE_MAP_PATH,
    )

    append_parser = subparsers.add_parser("append")
    append_parser.add_argument("--ledger", type=_path, required=True)
    append_parser.add_argument("--entry", type=_path, required=True)
    append_parser.add_argument(
        "--failure-map",
        type=_path,
        default=DEFAULT_FAILURE_MAP_PATH,
    )

    read_parser = subparsers.add_parser("read")
    read_parser.add_argument("--ledger", type=_path, required=True)
    read_parser.add_argument(
        "--failure-map",
        type=_path,
        default=DEFAULT_FAILURE_MAP_PATH,
    )

    validate_ledger_parser = subparsers.add_parser("validate-ledger")
    validate_ledger_parser.add_argument("--ledger", type=_path, required=True)
    validate_ledger_parser.add_argument(
        "--failure-map",
        type=_path,
        default=DEFAULT_FAILURE_MAP_PATH,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "build":
            artifacts = build_artifacts(arguments.failure_map)
            write_artifacts(arguments.output_dir, artifacts)
            result = check_bundle(arguments.output_dir, arguments.failure_map)
        elif arguments.command == "validate-bundle":
            result = check_bundle(arguments.bundle_dir, arguments.failure_map)
        elif arguments.command == "double-run":
            result = double_run(arguments.failure_map)
        elif arguments.command == "append":
            raw = arguments.entry.read_bytes()
            allowlist = load_failure_allowlist(arguments.failure_map)
            entry = load_entry_bytes(raw, allowlist)
            result = append_entry(arguments.ledger, entry, arguments.failure_map)
        elif arguments.command == "read":
            result = {
                "result": "PASS",
                "entries": read_ledger(arguments.ledger, arguments.failure_map),
                "truth_promotion_allowed": False,
            }
        elif arguments.command == "validate-ledger":
            result = validate_ledger(arguments.ledger, arguments.failure_map)
        else:  # pragma: no cover - argparse enforces the command choices.
            parser.error("unknown command")
            return 2
    except (OSError, ErrorNotebookError) as exc:
        print(
            json.dumps(
                {
                    "result": "REJECTED",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
