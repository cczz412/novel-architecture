from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .jsonutil import DuplicateKeyError, raw_decode_object

SHA256_64 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_FINAL_FIELDS = ("verdict",)


@dataclass(frozen=True)
class MechanicalResult:
    mechanical_status: str
    failure_stage: str | None
    failure_code: str | None
    semantic_gate_eligible: bool
    transport_ok: bool
    parse_ok: bool
    schema_ok: bool
    parsed: dict[str, Any] | None
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "mechanical_status": self.mechanical_status,
            "failure_stage": self.failure_stage,
            "failure_code": self.failure_code,
            "semantic_gate_eligible": self.semantic_gate_eligible,
            "transport_ok": self.transport_ok,
            "parse_ok": self.parse_ok,
            "schema_ok": self.schema_ok,
            "parsed": self.parsed,
            "detail": self.detail,
        }


def _fail(stage: str, code: str, detail: str, *, transport_ok: bool, parse_ok: bool, schema_ok: bool) -> MechanicalResult:
    return MechanicalResult(
        mechanical_status="FAIL",
        failure_stage=stage,
        failure_code=code,
        semantic_gate_eligible=False,
        transport_ok=transport_ok,
        parse_ok=parse_ok,
        schema_ok=schema_ok,
        parsed=None,
        detail=detail,
    )


def assess_envelope(case: dict[str, Any]) -> MechanicalResult:
    """Assess a synthetic envelope. Never promote reasoning JSON to final."""
    _ = case.get("reasoning_raw")
    transport = case.get("transport") or {}
    if transport.get("complete") is not True:
        return _fail(
            "TRANSPORT",
            "INCOMPLETE",
            "transport.complete is not true",
            transport_ok=False,
            parse_ok=False,
            schema_ok=False,
        )
    http_status = transport.get("http_status")
    if not isinstance(http_status, int) or http_status < 200 or http_status > 299:
        return _fail(
            "TRANSPORT",
            "HTTP_ERROR",
            f"http_status={http_status!r}",
            transport_ok=False,
            parse_ok=False,
            schema_ok=False,
        )
    if transport.get("generation_complete") is not True:
        return _fail(
            "TRANSPORT",
            "GENERATION_INCOMPLETE",
            "generation_complete is not true",
            transport_ok=False,
            parse_ok=False,
            schema_ok=False,
        )

    final_raw = case.get("final_raw")
    if not isinstance(final_raw, str) or not final_raw.strip():
        return _fail(
            "PARSE",
            "FINAL_MISSING",
            "final channel empty; reasoning is not a fallback",
            transport_ok=True,
            parse_ok=False,
            schema_ok=False,
        )
    stripped = final_raw.strip()
    if stripped.startswith("```"):
        return _fail(
            "PARSE",
            "FENCED_JSON",
            "final channel is fenced; checker does not unfence",
            transport_ok=True,
            parse_ok=False,
            schema_ok=False,
        )
    try:
        parsed, trailing = raw_decode_object(final_raw)
    except DuplicateKeyError as exc:
        return _fail(
            "PARSE",
            "DUPLICATE_KEY",
            f"duplicate key {exc}",
            transport_ok=True,
            parse_ok=False,
            schema_ok=False,
        )
    except json.JSONDecodeError as exc:
        return _fail(
            "PARSE",
            "TRUNCATED",
            str(exc),
            transport_ok=True,
            parse_ok=False,
            schema_ok=False,
        )
    if trailing.strip():
        return _fail(
            "PARSE",
            "TRAILING_PROSE",
            "non-empty trailing content after JSON",
            transport_ok=True,
            parse_ok=False,
            schema_ok=False,
        )
    if not isinstance(parsed, dict):
        return _fail(
            "PARSE",
            "ROOT_NOT_OBJECT",
            f"root type={type(parsed).__name__}",
            transport_ok=True,
            parse_ok=False,
            schema_ok=False,
        )

    missing = [name for name in REQUIRED_FINAL_FIELDS if name not in parsed]
    if missing:
        return _fail(
            "SCHEMA",
            "MISSING_FIELD",
            f"missing {missing}",
            transport_ok=True,
            parse_ok=True,
            schema_ok=False,
        )
    verdict = parsed.get("verdict")
    if not isinstance(verdict, str) or not verdict.strip():
        return _fail(
            "SCHEMA",
            "MISSING_FIELD",
            "verdict must be a non-empty string",
            transport_ok=True,
            parse_ok=True,
            schema_ok=False,
        )
    if "reason_code" in parsed:
        reason_code = parsed.get("reason_code")
        if reason_code is not None and not isinstance(reason_code, str):
            return _fail(
                "SCHEMA",
                "MISSING_FIELD",
                "reason_code must be string or null when present",
                transport_ok=True,
                parse_ok=True,
                schema_ok=False,
            )
    if case.get("check_nonce") is True:
        nonce = parsed.get("request_nonce")
        expected_nonce = case.get("expected_nonce")
        if not isinstance(nonce, str) or nonce != expected_nonce:
            return _fail(
                "SCHEMA",
                "NONCE_MISMATCH",
                "request_nonce does not match expected_nonce",
                transport_ok=True,
                parse_ok=True,
                schema_ok=False,
            )
    identity_hash = parsed.get("candidate_identity_hash")
    if identity_hash is not None:
        if not isinstance(identity_hash, str) or SHA256_64.fullmatch(identity_hash) is None:
            return _fail(
                "SCHEMA",
                "HASH_NOT_64_HEX",
                "candidate_identity_hash must be 64 lowercase hex; 62-char values are not padded",
                transport_ok=True,
                parse_ok=True,
                schema_ok=False,
            )

    return MechanicalResult(
        mechanical_status="PASS",
        failure_stage=None,
        failure_code=None,
        semantic_gate_eligible=True,
        transport_ok=True,
        parse_ok=True,
        schema_ok=True,
        parsed=parsed,
        detail="ok",
    )
