"""Canonical current ledger references and the fixed CCZ-126 -> C9 adapter."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from typing import Any, Mapping, NoReturn

from . import ledger_read_runtime, unified_retrieval_core as c9


OBJECT_REF_PREFIX = "ledger-read://current/"
OBJECT_REF_FIELDS = {"tool", "selector"}


class C9LedgerReadAdapterError(ValueError):
    """A C9 need is not a canonical current ledger read reference."""


def _fail(code: str) -> NoReturn:
    raise C9LedgerReadAdapterError(code)


def _encoded_payload(payload: Mapping[str, Any]) -> str:
    raw = ledger_read_runtime.canonical_json(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _object_ref(tool: str, selector: Mapping[str, Any]) -> str:
    payload = {"tool": tool, "selector": copy.deepcopy(dict(selector))}
    return f"{OBJECT_REF_PREFIX}{_encoded_payload(payload)}"


def directory_object_ref() -> str:
    return _object_ref("get_ledger_directory", {})


def chapter_evidence_object_ref(
    chapter_id: str,
    *,
    include_chapter_text: bool = False,
) -> str:
    return _object_ref(
        "get_chapter_evidence_slice",
        {
            "chapter_id": chapter_id,
            "include_chapter_text": include_chapter_text,
        },
    )


def ledger_entries_object_ref(
    ledger_name: str,
    refs: list[str],
) -> str:
    profiles = {
        "章节账": "chapter_metadata",
        "事实账": "fact_record",
        "人物账": "character_definition",
        "地点账": "location_definition",
        "物品账": "item_definition",
        "势力账": "faction_definition",
        "体系账": "system_definition",
        "世界规则账": "world_rule_definition",
    }
    profile = profiles.get(ledger_name)
    if profile is None:
        _fail("LEDGER_OBJECT_REF_PROFILE_UNSUPPORTED")
    return _object_ref(
        "get_ledger_entries_by_ref",
        {
            "ledger_name": ledger_name,
            "read_profile": profile,
            "refs": copy.deepcopy(refs),
        },
    )


def parse_object_ref(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.startswith(OBJECT_REF_PREFIX):
        _fail("LEDGER_OBJECT_REF_INVALID")
    encoded = value.removeprefix(OBJECT_REF_PREFIX)
    if not encoded:
        _fail("LEDGER_OBJECT_REF_INVALID")
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C9LedgerReadAdapterError("LEDGER_OBJECT_REF_INVALID") from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != OBJECT_REF_FIELDS
        or not isinstance(payload.get("tool"), str)
        or not isinstance(payload.get("selector"), dict)
    ):
        _fail("LEDGER_OBJECT_REF_INVALID")
    if _object_ref(payload["tool"], payload["selector"]) != value:
        _fail("LEDGER_OBJECT_REF_NOT_CANONICAL")
    tool = payload["tool"]
    selector = payload["selector"]
    if tool == "get_ledger_directory" and selector == {}:
        return copy.deepcopy(payload)
    if tool == "get_chapter_evidence_slice" and isinstance(selector, dict):
        if set(selector) == {"chapter_id", "include_chapter_text"}:
            return copy.deepcopy(payload)
    if tool == "get_ledger_entries_by_ref" and isinstance(selector, dict):
        if set(selector) == {"ledger_name", "read_profile", "refs"}:
            return copy.deepcopy(payload)
    _fail("LEDGER_OBJECT_REF_SHAPE_UNSUPPORTED")


def _read_request(
    session: ledger_read_runtime.CurrentLedgerReadSession,
    c9_request: Mapping[str, Any],
    need: Mapping[str, Any],
) -> dict[str, Any]:
    parsed = parse_object_ref(need["object_ref"])
    request_id = hashlib.sha256(
        c9.canonical_bytes(
            {
                "c9_request_sha256": c9_request["request_sha256"],
                "need_id": need["need_id"],
                "object_ref": need["object_ref"],
            }
        )
    ).hexdigest()[:32]
    request = {
        "contract": "LEDGER_READ_REQUEST",
        "version": ledger_read_runtime.VERSION,
        "execution_context": {
            "request_id": f"REQ-C9-{request_id}",
            "caller_id": session.execution_context["caller_id"],
            "author_id": session.author_id,
            "project_id": session.project_id,
            "permission_profile": session.execution_context["permission_profile"],
            "permission_policy_version": session.execution_context[
                "permission_policy_version"
            ],
        },
        "tool": parsed["tool"],
        "basis": {"mode": "current_at_start"},
        "selector": parsed["selector"],
    }
    return ledger_read_runtime.validate_ledger_read_document(request)


def _outcome(need: Mapping[str, Any], response: Mapping[str, Any]) -> dict[str, Any]:
    material_text = (
        ledger_read_runtime.canonical_json(response["data"])
        if response["status"] == "OK"
        else None
    )
    return {
        "need_id": need["need_id"],
        "source_status": response["status"],
        "reason_code": response["reason_code"],
        "source_document": copy.deepcopy(dict(response)),
        "material_text": material_text,
    }


def read_need(
    session: ledger_read_runtime.CurrentLedgerReadSession,
    c9_request: Mapping[str, Any],
    need: Mapping[str, Any],
) -> dict[str, Any]:
    request = _read_request(session, c9_request, need)
    return _outcome(need, ledger_read_runtime.execute_read(session, request))


def current_advanced_outcome(
    session: ledger_read_runtime.CurrentLedgerReadSession,
    c9_request: Mapping[str, Any],
    need: Mapping[str, Any],
) -> dict[str, Any]:
    request = _read_request(session, c9_request, need)
    response = ledger_read_runtime.current_advanced_response(session, request)
    return _outcome(need, response)


def bind_projection(
    document: dict[str, Any],
    need: dict[str, Any],
    material_text: str | None,
    basis_mode: str,
) -> dict[str, Any]:
    checked = ledger_read_runtime.validate_ledger_read_document(document)
    parsed = parse_object_ref(need["object_ref"])
    if checked["tool"] != parsed["tool"]:
        _fail("LEDGER_BINDING_TOOL_MISMATCH")
    expected_material = (
        ledger_read_runtime.canonical_json(checked["data"])
        if checked["status"] == "OK"
        else None
    )
    if material_text != expected_material:
        _fail("LEDGER_BINDING_MATERIAL_MISMATCH")
    receipt = checked["receipt"]
    selector = {
        "selector_kind": "LEDGER_READ_DATA",
        "selector_ref": need["object_ref"],
    }
    selector["selector_sha256"] = c9.sha256_json(selector)
    return {
        "canonical_object_ref": need["object_ref"],
        "truth_scope_ref": {
            "author_id": receipt["author_id"],
            "project_id": receipt["project_id"],
        },
        "source_object_sha256": c9.sha256_json(checked),
        "source_revision_ref": receipt["storage_generation"],
        "basis_mode": basis_mode,
        "read_request_id": checked["request_id"],
        "basis_sha256": receipt["basis_sha256"],
        "source_manifest_sha256": c9.sha256_json(receipt["source_manifest"]),
        "projection_selector": selector,
        "projected_material_sha256": (
            hashlib.sha256(material_text.encode("utf-8")).hexdigest()
            if material_text is not None
            else None
        ),
        "pin_proof_status": "CURRENT_AT_START",
    }


def trusted_source_registry() -> dict[str, Any]:
    """Return a fresh copy of the only registry this composition may inject."""
    return {
        "LEDGER_READ_TOOL_CONTRACT": {
            "source_contract": "LEDGER_READ_TOOL_CONTRACT",
            "source_contract_version": ledger_read_runtime.VERSION,
            "validator_id": "ccz126-ledger-read-response-validator-v1",
            "validate_document": ledger_read_runtime.validate_ledger_read_document,
            "bind_projection": bind_projection,
        }
    }


__all__ = [
    "C9LedgerReadAdapterError",
    "bind_projection",
    "chapter_evidence_object_ref",
    "current_advanced_outcome",
    "directory_object_ref",
    "ledger_entries_object_ref",
    "parse_object_ref",
    "read_need",
]
