"""Validate TRACEABLE_PROVENANCE_SEAL v1 structural bindings."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "TRACEABLE_PROVENANCE_SEAL.schema.json"
FIXTURE_PATH = DIR / "TRACEABLE_PROVENANCE_SEAL.fixtures.jsonl"

STRUCTURAL_VALID = "STRUCTURAL_VALID"
STRUCTURAL_VALID_OWNER_UNRESOLVED = "STRUCTURAL_VALID_OWNER_UNRESOLVED"
STRUCTURAL_INVALID = "STRUCTURAL_INVALID"

FORBIDDEN_CONTENT_KEYS = {
    "body",
    "chapter_text",
    "database_table",
    "file_path",
    "path",
    "physical_path",
    "quote",
    "sql",
    "summary",
    "table_name",
    "text",
}

FORMATION_RULES: dict[str, dict[str, Any]] = {
    "C10_SPAN_TO_C11_REVISION": {
        "subject": "C11_CHAPTER_REVISION",
        "claim": "OWNER_COMMIT_CLAIM",
        "roles": {"CONTENT_BASIS", "OWNER_COMMIT_RECEIPT"},
    },
    "WORK_DRAFT_TO_C11_REVISION": {
        "subject": "C11_CHAPTER_REVISION",
        "claim": "OWNER_COMMIT_CLAIM",
        "roles": {
            "CONTENT_BASIS",
            "AUTHORITY_EVIDENCE",
            "OWNER_COMMIT_RECEIPT",
        },
    },
    "LEGACY_SNAPSHOT_TO_C11_REVISION": {
        "subject": "C11_CHAPTER_REVISION",
        "claim": "OWNER_UNRESOLVED_CLAIM",
        "roles": {"CONTENT_BASIS", "OWNER_COMMIT_RECEIPT"},
    },
    "PROSE_EXTRACTION": {
        "subject": "FACT_CANDIDATE_VERSION",
        "claim": "OWNER_UNRESOLVED_CLAIM",
        "roles": {
            "CONTENT_BASIS",
            "SOURCE_EVIDENCE_ANCHOR",
            "PRODUCER_RECEIPT",
        },
    },
    "AUTHOR_DECLARATION": {
        "subject": "FACT_CANDIDATE_VERSION",
        "claim": "OWNER_UNRESOLVED_CLAIM",
        "roles": {"CONTENT_BASIS", "AUTHORITY_EVIDENCE", "PRODUCER_RECEIPT"},
    },
    "SYSTEM_PROPOSAL": {
        "subject": "FACT_CANDIDATE_VERSION",
        "claim": "OWNER_UNRESOLVED_CLAIM",
        "roles": {"CONTENT_BASIS", "PRODUCER_RECEIPT"},
    },
    "CHAPTER_LOCAL_DELTA": {
        "subject": "FACT_CANDIDATE_VERSION",
        "claim": "OWNER_UNRESOLVED_CLAIM",
        "roles": {"CONTENT_BASIS", "PRODUCER_RECEIPT"},
    },
    "AUTHOR_ADOPTION": {
        "subject": "FORMAL_FACT_VERSION",
        "claim": "OWNER_UNRESOLVED_CLAIM",
        "roles": {
            "CONTENT_BASIS",
            "AUTHORITY_EVIDENCE",
            "OWNER_COMMIT_RECEIPT",
        },
    },
    "DELEGATED_SYSTEM_ADOPTION": {
        "subject": "FORMAL_FACT_VERSION",
        "claim": "OWNER_UNRESOLVED_CLAIM",
        "roles": {
            "CONTENT_BASIS",
            "AUTHORITY_EVIDENCE",
            "OWNER_COMMIT_RECEIPT",
        },
    },
    "CHAPTER_CLOSEOUT_ADMISSION": {
        "subject": "FORMAL_FACT_VERSION",
        "claim": "OWNER_UNRESOLVED_CLAIM",
        "roles": {
            "CONTENT_BASIS",
            "AUTHORITY_EVIDENCE",
            "OWNER_COMMIT_RECEIPT",
        },
    },
    "SETTINGSTORE_COMMIT": {
        "subject": "SETTING_LEDGER_RECORD",
        "claim": "OWNER_COMMIT_CLAIM",
        "roles": {"CONTENT_BASIS", "OWNER_COMMIT_RECEIPT", "CHANGE_RECORD"},
    },
    "PLANSTORE_COMMIT": {
        "subject": "PLAN_LEDGER_RECORD",
        "claim": "OWNER_COMMIT_CLAIM",
        "roles": {"CONTENT_BASIS", "OWNER_COMMIT_RECEIPT", "CHANGE_RECORD"},
    },
}


class ContractError(ValueError):
    """A provenance seal structural invariant failed."""


def _load_schema() -> dict[str, Any]:
    value = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


SCHEMA = _load_schema()
VALIDATOR = Draft202012Validator(SCHEMA)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def seal_sha256(document: dict[str, Any]) -> str:
    payload = copy.deepcopy(document)
    payload.pop("seal_sha256", None)
    return sha256_json(payload)


def seal_document(document: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    result["seal_sha256"] = seal_sha256(result)
    return result


def _schema_path(error: Any) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "$"


def _validate_schema(document: Any) -> None:
    errors = sorted(
        VALIDATOR.iter_errors(document),
        key=lambda item: (list(item.absolute_path), item.message),
    )
    if errors:
        first = errors[0]
        raise ContractError(f"SCHEMA_INVALID:{_schema_path(first)}:{first.validator}")


def _walk_forbidden_content(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_CONTENT_KEYS:
                raise ContractError(f"PROTECTED_CONTENT_KEY_FORBIDDEN:{path}.{key}")
            _walk_forbidden_content(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_forbidden_content(item, f"{path}[{index}]")


def _iter_wrappers(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [document["subject_ref"], *[item["ref"] for item in document["direct_basis_refs"]]]


def _validate_scope_first(document: dict[str, Any]) -> None:
    scope = document["truth_scope_ref"]
    for wrapper in _iter_wrappers(document):
        if wrapper["truth_scope_ref"] != scope:
            raise ContractError("TRUTH_SCOPE_MISMATCH")


def _require_wrapper(
    wrapper: dict[str, Any],
    *,
    source_kind: str,
    source_contract: str | None,
    source_contract_version: str | None,
    stable_id: str | None,
    revision: int | str | None,
    logical_content_sha256: str | None,
) -> None:
    expected = {
        "source_kind": source_kind,
        "stable_id": stable_id,
        "revision": revision,
        "logical_content_sha256": logical_content_sha256,
    }
    if source_contract is not None:
        expected["source_contract"] = source_contract
    if source_contract_version is not None:
        expected["source_contract_version"] = source_contract_version
    for key, value in expected.items():
        if wrapper[key] != value:
            raise ContractError(f"OWNER_WRAPPER_MISMATCH:{key}")


def _validate_owner_wrapper(wrapper: dict[str, Any]) -> None:
    owner = wrapper["owner_ref"]
    kind = owner["kind"]
    if kind == "C10_MATERIAL_IDENTITY_REVISION":
        _require_wrapper(
            wrapper,
            source_kind="material_identity",
            source_contract="C10_INTAKE_MATERIAL_IDENTITY",
            source_contract_version=owner["record_contract_version"],
            stable_id=owner["material_unit_id"],
            revision=owner["identity_revision_no"],
            logical_content_sha256=owner["identity_revision_sha256"],
        )
    elif kind == "C10_SOURCE_SPAN":
        _require_wrapper(
            wrapper,
            source_kind="source_span",
            source_contract="C10_INTAKE_MATERIAL_IDENTITY",
            source_contract_version=None,
            stable_id=owner["source_id"],
            revision=owner["source_sha256"],
            logical_content_sha256=owner["slice_sha256"],
        )
        if owner["end"] <= owner["start"]:
            raise ContractError("C10_SOURCE_SPAN_EMPTY_OR_REVERSED")
    elif kind == "C11_CHAPTER_REVISION":
        _require_wrapper(
            wrapper,
            source_kind="chapter_revision",
            source_contract="C11_CHAPTER_REVISION_LEDGER",
            source_contract_version="v1",
            stable_id=owner["chapter_id"],
            revision=owner["revision_no"],
            logical_content_sha256=owner["revision_text_sha256"],
        )
        if wrapper["logical_ledger_name"] != "chapter":
            raise ContractError("C11_LEDGER_NAME_MISMATCH")
    elif kind == "C11_VERIFIED_ANCHOR":
        _require_wrapper(
            wrapper,
            source_kind="chapter_anchor",
            source_contract="C11_CHAPTER_REVISION_LEDGER",
            source_contract_version="v1",
            stable_id=owner["chapter_id"],
            revision=owner["revision_no"],
            logical_content_sha256=owner["slice_sha256"],
        )
        if wrapper["logical_ledger_name"] != "chapter":
            raise ContractError("C11_ANCHOR_LEDGER_NAME_MISMATCH")
        if owner["end"] <= owner["start"]:
            raise ContractError("C11_ANCHOR_EMPTY_OR_REVERSED")
    elif kind == "CHAPTER_REVISION_COMMIT_RECEIPT":
        _require_wrapper(
            wrapper,
            source_kind="owner_commit_receipt",
            source_contract="CHAPTER_REVISION_COMMIT_RECEIPT",
            source_contract_version="v1",
            stable_id=owner["operation_id"],
            revision=owner["after_revision_no"],
            logical_content_sha256=owner["receipt_sha256"],
        )
        if wrapper["logical_ledger_name"] != "chapter":
            raise ContractError("C11_RECEIPT_LEDGER_NAME_MISMATCH")
    elif kind == "WORK_DRAFT_REVISION":
        _require_wrapper(
            wrapper,
            source_kind="work_draft",
            source_contract="WORK_DRAFT_REVISION",
            source_contract_version="v1",
            stable_id=owner["work_ref"],
            revision=owner["work_rev"],
            logical_content_sha256=owner["content_sha256"],
        )
    elif kind == "OWNER_ACTION":
        _require_wrapper(
            wrapper,
            source_kind="owner_action",
            source_contract=owner["action_contract"],
            source_contract_version=owner["action_contract_version"],
            stable_id=owner["action_id"],
            revision=owner["action_contract_version"],
            logical_content_sha256=owner["action_sha256"],
        )
    elif kind == "SETTING_LEDGER_RECORD":
        _require_wrapper(
            wrapper,
            source_kind="ledger_entry",
            source_contract=owner["record_contract"],
            source_contract_version=owner["record_contract_version"],
            stable_id=owner["record_id"],
            revision=owner["rev"],
            logical_content_sha256=owner["record_sha256"],
        )
        if wrapper["logical_ledger_name"] != owner["ledger_name"]:
            raise ContractError("SETTING_LEDGER_NAME_MISMATCH")
    elif kind == "PLAN_LEDGER_RECORD":
        _require_wrapper(
            wrapper,
            source_kind="ledger_entry",
            source_contract="PLAN_LEDGER_STORAGE",
            source_contract_version=None,
            stable_id=owner["object_id"],
            revision=owner["rev"],
            logical_content_sha256=owner["record_sha256"],
        )
        if wrapper["logical_ledger_name"] not in {"planning", "longline"}:
            raise ContractError("PLAN_LEDGER_NAME_MISMATCH")
    elif kind == "OWNER_COMMIT_RECEIPT":
        _require_wrapper(
            wrapper,
            source_kind="owner_commit_receipt",
            source_contract=owner["owner_contract"],
            source_contract_version=None,
            stable_id=owner["operation_id"],
            revision=owner["subject_revision"],
            logical_content_sha256=owner["receipt_sha256"],
        )
    elif kind == "CHANGE_RECORD":
        _require_wrapper(
            wrapper,
            source_kind="change_record",
            source_contract=owner["owner_contract"],
            source_contract_version=None,
            stable_id=owner["operation_id"],
            revision=owner["subject_revision"],
            logical_content_sha256=owner["change_record_sha256"],
        )
    elif kind == "OWNER_UNRESOLVED_REF":
        _require_wrapper(
            wrapper,
            source_kind="unresolved_owner",
            source_contract=owner["expected_owner_contract"],
            source_contract_version="UNRESOLVED",
            stable_id=None,
            revision=None,
            logical_content_sha256=None,
        )
        if owner["missing_identity_semantics"] != sorted(
            owner["missing_identity_semantics"]
        ):
            raise ContractError("UNRESOLVED_SEMANTICS_NOT_SORTED")
    else:  # pragma: no cover - schema oneOf closes this branch
        raise ContractError(f"OWNER_REF_KIND_UNKNOWN:{kind}")


def _sort_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return canonical_bytes(value).decode("utf-8")
    return str(value)


def basis_sort_key(item: dict[str, Any]) -> tuple[str, ...]:
    ref = item["ref"]
    return tuple(
        _sort_value(value)
        for value in (
            item["basis_role"],
            ref["source_kind"],
            ref["logical_ledger_name"],
            ref["stable_id"],
            ref["revision"],
            ref["role"],
            ref["source_contract"],
            ref["source_contract_version"],
            ref["logical_content_sha256"],
        )
    )


def _basis(document: dict[str, Any], role: str) -> list[dict[str, Any]]:
    return [item["ref"] for item in document["direct_basis_refs"] if item["basis_role"] == role]


def _owner_kind(wrapper: dict[str, Any]) -> str:
    owner = wrapper["owner_ref"]
    if owner["kind"] == "OWNER_UNRESOLVED_REF":
        return owner["object_role"]
    return owner["kind"]


def _all_unresolved(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        wrapper
        for wrapper in _iter_wrappers(document)
        if wrapper["owner_ref"]["kind"] == "OWNER_UNRESOLVED_REF"
    ]


def _validate_order_and_duplicates(document: dict[str, Any]) -> None:
    basis = document["direct_basis_refs"]
    if basis != sorted(basis, key=basis_sort_key):
        raise ContractError("DIRECT_BASIS_REFS_NOT_CANONICALLY_SORTED")
    seen: set[bytes] = set()
    for item in basis:
        identity = canonical_bytes(item["ref"])
        if identity in seen:
            raise ContractError("DIRECT_BASIS_REF_DUPLICATE")
        seen.add(identity)


def _validate_claim_and_formation(document: dict[str, Any]) -> None:
    formation = document["formation_kind"]
    rule = FORMATION_RULES[formation]
    subject_kind = _owner_kind(document["subject_ref"])
    if subject_kind != rule["subject"]:
        raise ContractError("FORMATION_SUBJECT_OWNER_MISMATCH")
    if document["claim_kind"] != rule["claim"]:
        raise ContractError("FORMATION_CLAIM_KIND_MISMATCH")

    roles = {item["basis_role"] for item in document["direct_basis_refs"]}
    missing = sorted(rule["roles"] - roles)
    if missing:
        raise ContractError(f"FORMATION_BASIS_ROLE_MISSING:{','.join(missing)}")

    unresolved = _all_unresolved(document)
    if rule["claim"] == "OWNER_UNRESOLVED_CLAIM" and not unresolved:
        raise ContractError("OWNER_UNRESOLVED_REF_REQUIRED")
    if rule["claim"] == "OWNER_COMMIT_CLAIM" and unresolved:
        raise ContractError("OWNER_COMMIT_CLAIM_HAS_UNRESOLVED_REF")


def _validate_c11_receipt(document: dict[str, Any]) -> None:
    subject = document["subject_ref"]["owner_ref"]
    receipts = [
        ref["owner_ref"]
        for ref in _basis(document, "OWNER_COMMIT_RECEIPT")
        if ref["owner_ref"]["kind"] == "CHAPTER_REVISION_COMMIT_RECEIPT"
    ]
    if len(receipts) != 1:
        raise ContractError("C11_COMMIT_RECEIPT_REQUIRED_ONCE")
    receipt = receipts[0]
    if receipt["status"] != "COMMITTED" or receipt["result"] != "REVISION_APPENDED":
        raise ContractError("C11_COMMIT_RECEIPT_NOT_COMMITTED")
    if (
        receipt["chapter_id"] != subject["chapter_id"]
        or receipt["after_revision_no"] != subject["revision_no"]
        or receipt["text_sha256"] != subject["revision_text_sha256"]
    ):
        raise ContractError("C11_COMMIT_RECEIPT_SUBJECT_MISMATCH")
    if receipt["after_revision_no"] != receipt["before_revision_no"] + 1:
        raise ContractError("C11_COMMIT_RECEIPT_REVISION_NOT_ADVANCED")


def _validate_chapter_formation(document: dict[str, Any]) -> None:
    formation = document["formation_kind"]
    if formation not in {
        "C10_SPAN_TO_C11_REVISION",
        "WORK_DRAFT_TO_C11_REVISION",
        "LEGACY_SNAPSHOT_TO_C11_REVISION",
    }:
        return
    _validate_c11_receipt(document)
    content_kinds = {_owner_kind(ref) for ref in _basis(document, "CONTENT_BASIS")}
    if formation == "C10_SPAN_TO_C11_REVISION":
        if not {"C10_MATERIAL_IDENTITY_REVISION", "C10_SOURCE_SPAN"}.issubset(
            content_kinds
        ):
            raise ContractError("C10_CHAPTER_BASIS_INCOMPLETE")
        material = next(
            ref["owner_ref"]
            for ref in _basis(document, "CONTENT_BASIS")
            if ref["owner_ref"]["kind"] == "C10_MATERIAL_IDENTITY_REVISION"
        )
        if (
            material["identity_role"] != "CHAPTER"
            or material["identity_state"] != "CONFIRMED"
        ):
            raise ContractError("C10_CONFIRMED_CHAPTER_IDENTITY_REQUIRED")
        span = next(
            ref["owner_ref"]
            for ref in _basis(document, "CONTENT_BASIS")
            if ref["owner_ref"]["kind"] == "C10_SOURCE_SPAN"
        )
        if material["source_ref"] != {
            key: value for key, value in span.items() if key != "kind"
        }:
            raise ContractError("C10_MATERIAL_SOURCE_SPAN_MISMATCH")
    elif formation == "WORK_DRAFT_TO_C11_REVISION":
        work_refs = [
            ref["owner_ref"]
            for ref in _basis(document, "CONTENT_BASIS")
            if ref["owner_ref"]["kind"] == "WORK_DRAFT_REVISION"
        ]
        if len(work_refs) != 1:
            raise ContractError("WORK_DRAFT_BASIS_REQUIRED")
        if work_refs[0]["content_sha256"] != document["subject_ref"]["owner_ref"][
            "revision_text_sha256"
        ]:
            raise ContractError("WORK_DRAFT_C11_TEXT_SHA_MISMATCH")
        actions = [
            ref["owner_ref"]
            for ref in _basis(document, "AUTHORITY_EVIDENCE")
            if ref["owner_ref"]["kind"] == "OWNER_ACTION"
        ]
        if len(actions) != 1 or (
            actions[0]["action_contract"] != "WORK_DRAFT_HANDOVER_ACTION"
            or actions[0]["action_contract_version"] != "v2"
            or actions[0]["actor"] != "AUTHOR"
        ):
            raise ContractError("WORK_DRAFT_HANDOVER_ACTION_REQUIRED")
    else:
        unresolved_roles = {
            ref["owner_ref"]["object_role"]
            for ref in _basis(document, "CONTENT_BASIS")
            if ref["owner_ref"]["kind"] == "OWNER_UNRESOLVED_REF"
        }
        if "LEGACY_C1_SNAPSHOT" not in unresolved_roles:
            raise ContractError("LEGACY_SNAPSHOT_OWNER_REF_REQUIRED")


def _validate_candidate_formation(document: dict[str, Any]) -> None:
    formation = document["formation_kind"]
    if formation not in {
        "PROSE_EXTRACTION",
        "AUTHOR_DECLARATION",
        "SYSTEM_PROPOSAL",
        "CHAPTER_LOCAL_DELTA",
    }:
        return
    subject = document["subject_ref"]["owner_ref"]
    if subject["object_role"] != "FACT_CANDIDATE_VERSION":
        raise ContractError("FACT_CANDIDATE_OWNER_REF_REQUIRED")
    if formation == "PROSE_EXTRACTION":
        chapter_refs = [
            ref["owner_ref"]
            for ref in _basis(document, "CONTENT_BASIS")
            if ref["owner_ref"]["kind"] == "C11_CHAPTER_REVISION"
        ]
        anchors = [
            ref["owner_ref"]
            for ref in _basis(document, "SOURCE_EVIDENCE_ANCHOR")
            if ref["owner_ref"]["kind"] == "C11_VERIFIED_ANCHOR"
        ]
        if len(chapter_refs) != 1 or len(anchors) != 1:
            raise ContractError("PROSE_EXTRACTION_C11_EVIDENCE_REQUIRED")
        chapter = chapter_refs[0]
        anchor = anchors[0]
        if (
            anchor["chapter_id"] != chapter["chapter_id"]
            or anchor["revision_no"] != chapter["revision_no"]
            or anchor["revision_text_sha256"] != chapter["revision_text_sha256"]
        ):
            raise ContractError("PROSE_EXTRACTION_ANCHOR_REVISION_MISMATCH")
        implicit = any(
            ref["role"] == "implicit_fact_evidence"
            for ref in _basis(document, "CONTENT_BASIS")
        )
        if implicit and not _basis(document, "INFERENCE_TRACE"):
            raise ContractError("IMPLICIT_FACT_INFERENCE_TRACE_REQUIRED")
    elif formation == "AUTHOR_DECLARATION":
        if _basis(document, "SOURCE_EVIDENCE_ANCHOR"):
            raise ContractError("AUTHOR_DECLARATION_ANCHOR_FORBIDDEN")
        actions = [
            ref["owner_ref"]
            for ref in _basis(document, "AUTHORITY_EVIDENCE")
            if ref["owner_ref"]["kind"] == "OWNER_ACTION"
        ]
        if len(actions) != 1 or actions[0]["actor"] != "AUTHOR":
            raise ContractError("AUTHOR_DECLARATION_ACTION_REQUIRED")
    elif formation == "CHAPTER_LOCAL_DELTA" and _basis(
        document, "SOURCE_EVIDENCE_ANCHOR"
    ):
        raise ContractError("CHAPTER_LOCAL_DELTA_ANCHOR_FORBIDDEN")


def _validate_formal_fact_formation(document: dict[str, Any]) -> None:
    formation = document["formation_kind"]
    if formation not in {
        "AUTHOR_ADOPTION",
        "DELEGATED_SYSTEM_ADOPTION",
        "CHAPTER_CLOSEOUT_ADMISSION",
    }:
        return
    subject = document["subject_ref"]["owner_ref"]
    if subject["object_role"] != "FORMAL_FACT_VERSION":
        raise ContractError("FORMAL_FACT_OWNER_REF_REQUIRED")
    content_roles = {
        ref["owner_ref"].get("object_role")
        for ref in _basis(document, "CONTENT_BASIS")
        if ref["owner_ref"]["kind"] == "OWNER_UNRESOLVED_REF"
    }
    if "FACT_CANDIDATE_VERSION" not in content_roles:
        raise ContractError("FORMAL_FACT_CANDIDATE_BASIS_REQUIRED")
    authority_roles = {
        ref["owner_ref"].get("object_role")
        for ref in _basis(document, "AUTHORITY_EVIDENCE")
        if ref["owner_ref"]["kind"] == "OWNER_UNRESOLVED_REF"
    }
    actions = [
        ref["owner_ref"]
        for ref in _basis(document, "AUTHORITY_EVIDENCE")
        if ref["owner_ref"]["kind"] == "OWNER_ACTION"
    ]
    if formation == "AUTHOR_ADOPTION":
        if len(actions) != 1 or actions[0]["actor"] != "AUTHOR":
            raise ContractError("AUTHOR_ADOPTION_ACTION_REQUIRED")
    elif formation == "DELEGATED_SYSTEM_ADOPTION":
        if "PERMISSION_SNAPSHOT" not in authority_roles:
            raise ContractError("DELEGATED_PERMISSION_SNAPSHOT_REQUIRED")
        if any(action["actor"] == "AUTHOR" for action in actions):
            raise ContractError("DELEGATED_ADOPTION_AUTHOR_ATTESTATION_FORBIDDEN")
    elif "CHAPTER_CLOSEOUT_RECEIPT" not in authority_roles:
        raise ContractError("CHAPTER_CLOSEOUT_RECEIPT_REQUIRED")


def _validate_owner_commit_binding(document: dict[str, Any]) -> None:
    formation = document["formation_kind"]
    if formation not in {"SETTINGSTORE_COMMIT", "PLANSTORE_COMMIT"}:
        return
    subject = document["subject_ref"]
    owner = subject["owner_ref"]
    receipts = [
        ref["owner_ref"]
        for ref in _basis(document, "OWNER_COMMIT_RECEIPT")
        if ref["owner_ref"]["kind"] == "OWNER_COMMIT_RECEIPT"
    ]
    changes = [
        ref["owner_ref"]
        for ref in _basis(document, "CHANGE_RECORD")
        if ref["owner_ref"]["kind"] == "CHANGE_RECORD"
    ]
    if len(receipts) != 1 or len(changes) != 1:
        raise ContractError("OWNER_COMMIT_AND_CHANGE_RECORD_REQUIRED_ONCE")
    receipt = receipts[0]
    change = changes[0]
    if receipt["status"] != "COMMITTED":
        raise ContractError("OWNER_COMMIT_RECEIPT_NOT_COMMITTED")
    if (
        receipt["subject_stable_id"] != subject["stable_id"]
        or receipt["subject_revision"] != subject["revision"]
        or receipt["subject_sha256"] != subject["logical_content_sha256"]
    ):
        raise ContractError("OWNER_COMMIT_RECEIPT_SUBJECT_MISMATCH")
    if (
        change["subject_stable_id"] != subject["stable_id"]
        or change["subject_revision"] != subject["revision"]
        or change["after_subject_sha256"] != subject["logical_content_sha256"]
        or change["operation_id"] != receipt["operation_id"]
        or change["owner_contract"] != receipt["owner_contract"]
    ):
        raise ContractError("CHANGE_RECORD_SUBJECT_MISMATCH")

    revision = subject["revision"]
    prior = _basis(document, "PRIOR_SUBJECT_VERSION")
    if not isinstance(revision, int):
        raise ContractError("OWNER_SUBJECT_REVISION_MUST_BE_INTEGER")
    if revision == 1:
        if prior:
            raise ContractError("PRIOR_SUBJECT_VERSION_FORBIDDEN_ON_CREATE")
        if change["before_subject_sha256"] is not None:
            raise ContractError("CREATE_CHANGE_BEFORE_MUST_BE_NULL")
    else:
        if len(prior) != 1:
            raise ContractError("PRIOR_SUBJECT_VERSION_REQUIRED_ON_UPDATE")
        prior_ref = prior[0]
        if (
            prior_ref["owner_ref"]["kind"] != owner["kind"]
            or prior_ref["stable_id"] != subject["stable_id"]
            or prior_ref["revision"] != revision - 1
            or change["before_subject_sha256"]
            != prior_ref["logical_content_sha256"]
        ):
            raise ContractError("PRIOR_SUBJECT_VERSION_MISMATCH")

    if formation == "SETTINGSTORE_COMMIT":
        if receipt["owner_contract"] != "SETTING_LEDGER_STORAGE":
            raise ContractError("SETTINGSTORE_RECEIPT_OWNER_MISMATCH")
        content = _basis(document, "CONTENT_BASIS")
        setting_material_refs = [
            ref["owner_ref"]
            for ref in content
            if ref["role"] == "setting_material"
            and ref["owner_ref"]["kind"] == "C10_MATERIAL_IDENTITY_REVISION"
        ]
        setting_material = bool(setting_material_refs)
        if setting_material and any(
            ref["identity_role"] != "SETTING"
            or ref["identity_state"] != "CONFIRMED"
            for ref in setting_material_refs
        ):
            raise ContractError("C10_CONFIRMED_SETTING_IDENTITY_REQUIRED")
        if setting_material and not (
            owner["source_identity"] == "author_declared"
            and owner["confirm_status"] == "confirmed"
            and "AUTHOR_ATTESTATION" in owner["evidence_refs"]
        ):
            raise ContractError("SETTING_MATERIAL_AUTHOR_ATTESTATION_REQUIRED")
    elif receipt["owner_contract"] != "PLAN_LEDGER_STORAGE":
        raise ContractError("PLANSTORE_RECEIPT_OWNER_MISMATCH")
    elif (
        subject["logical_ledger_name"] == "longline"
        and owner["object_kind"]
        not in {"longline_volume", "character_destiny", "inspiration"}
    ):
        raise ContractError("LONGLINE_PLANSTORE_OBJECT_KIND_INVALID")


def validate_seal(document: Any) -> str:
    _validate_schema(document)
    _validate_scope_first(document)
    _walk_forbidden_content(document)
    for wrapper in _iter_wrappers(document):
        _validate_owner_wrapper(wrapper)
    _validate_order_and_duplicates(document)
    _validate_claim_and_formation(document)
    _validate_chapter_formation(document)
    _validate_candidate_formation(document)
    _validate_formal_fact_formation(document)
    _validate_owner_commit_binding(document)
    if document["seal_sha256"] != seal_sha256(document):
        raise ContractError("SEAL_SHA256_MISMATCH")
    if _all_unresolved(document):
        return STRUCTURAL_VALID_OWNER_UNRESOLVED
    return STRUCTURAL_VALID


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContractError(f"FIXTURE_JSON_INVALID:{line_no}") from exc
        rows.append(row)
    return rows


def validate_fixture_case(case: dict[str, Any]) -> str:
    expected = case.get("expected_result")
    if expected not in {
        STRUCTURAL_VALID,
        STRUCTURAL_VALID_OWNER_UNRESOLVED,
        STRUCTURAL_INVALID,
    }:
        raise ContractError("FIXTURE_EXPECTED_RESULT_INVALID")
    try:
        result = validate_seal(case.get("document"))
    except ContractError as exc:
        if expected != STRUCTURAL_INVALID:
            raise ContractError(f"FIXTURE_UNEXPECTED_INVALID:{case.get('case_id')}:{exc}") from exc
        expected_error = case.get("expected_error")
        if not isinstance(expected_error, str) or not str(exc).startswith(expected_error):
            raise ContractError(
                f"FIXTURE_ERROR_MISMATCH:{case.get('case_id')}:{exc}"
            ) from exc
        return STRUCTURAL_INVALID
    if result != expected:
        raise ContractError(
            f"FIXTURE_RESULT_MISMATCH:{case.get('case_id')}:{result}:{expected}"
        )
    return result


def validate_all_fixtures(path: Path = FIXTURE_PATH) -> dict[str, int]:
    counts = {
        STRUCTURAL_VALID: 0,
        STRUCTURAL_VALID_OWNER_UNRESOLVED: 0,
        STRUCTURAL_INVALID: 0,
    }
    for case in load_fixtures(path):
        counts[validate_fixture_case(case)] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=FIXTURE_PATH)
    args = parser.parse_args()
    try:
        counts = validate_all_fixtures(args.fixtures)
    except (ContractError, OSError) as exc:
        print(json.dumps({"status": STRUCTURAL_INVALID, "error": str(exc)}, sort_keys=True))
        return 1
    print(
        json.dumps(
            {
                "contract": "TRACEABLE_PROVENANCE_SEAL",
                "version": "v1",
                "status": "PASS",
                "counts": counts,
                "owner_resolution_performed": False,
                "network_calls": 0,
                "model_calls": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
