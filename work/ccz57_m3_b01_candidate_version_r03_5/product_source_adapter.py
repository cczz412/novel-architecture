"""Map safe AuthorWorkspace metadata into one B-01 source generation.

The adapter reads no chapter body and owns no product writer. It double-reads a
fixed four-key metadata view, validates the current C11/C10 binding, and emits
one in-memory immutable input record for the existing B-01 contract.
"""

from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from b01_contract import (
    B01ContractError,
    PRODUCT_READ_ONLY_ACCESS,
    make_read_only_input_record,
    record_ref,
    sha256_value,
    validate_chapter_revision_ref,
)

PRODUCT_ROOT = Path(__file__).resolve().parents[2] / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from contracts import validate_c11_chapter_revision_ledger as c11_contract
    from contracts.validate_c10_intake_material_identity import (
        ContractValidationError as C10ContractValidationError,
    )
    from contracts.validate_c10_intake_material_identity import (
        validate_record as validate_c10_record,
    )
    from mvp.workspace import AuthorWorkspace
finally:
    sys.path.pop(0)


ADAPTER_CONTRACT = "B01_AUTHOR_WORKSPACE_SOURCE_GENERATION_V1"
SOURCE_MODULE_IDENTITY = "B01_AUTHOR_WORKSPACE_SOURCE_ADAPTER_R01"
SAFE_LOGICAL_KEYS = (
    "chapter_admission_operations",
    "chapter_index",
    "chapter_materials",
    "chapter_revisions",
)
FORBIDDEN_LOGICAL_KEYS = frozenset({"chapter_sources", "chapters", "draft"})
_ENTRY_KEYS = {"logical_key", "version", "sha256", "payload"}
_INDEX_REF_KEYS = {"chapter_id", "revision_no", "revision_text_sha256"}


def _fail(code: str, detail: str = "") -> None:
    raise B01ContractError(code, detail)


def _product_payload_sha256(value: Any) -> str:
    try:
        encoded = (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise B01ContractError(
            "B01_PRODUCT_SOURCE_ENTRY_INVALID", "payload is not canonical JSON"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _read_workspace_entry(
    workspace: AuthorWorkspace, logical_key: str
) -> dict[str, Any] | None:
    if not isinstance(workspace, AuthorWorkspace):
        _fail("B01_PRODUCT_SOURCE_HANDLE_INVALID")
    if logical_key not in SAFE_LOGICAL_KEYS or logical_key in FORBIDDEN_LOGICAL_KEYS:
        _fail("B01_PRODUCT_SOURCE_SCOPE_ESCAPE", logical_key)
    return AuthorWorkspace.read(workspace, logical_key)


def _validated_entry(logical_key: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _ENTRY_KEYS:
        _fail("B01_PRODUCT_SOURCE_ENTRY_INVALID", logical_key)
    if (
        value["logical_key"] != logical_key
        or type(value["version"]) is not int
        or value["version"] < 1
        or not isinstance(value["sha256"], str)
        or value["sha256"] != _product_payload_sha256(value["payload"])
    ):
        _fail("B01_PRODUCT_SOURCE_ENTRY_INVALID", logical_key)
    return deepcopy(value)


def _stable_entries(workspace: AuthorWorkspace) -> dict[str, dict[str, Any]]:
    first = {
        key: _validated_entry(key, _read_workspace_entry(workspace, key))
        for key in SAFE_LOGICAL_KEYS
    }
    second = {
        key: _validated_entry(key, _read_workspace_entry(workspace, key))
        for key in SAFE_LOGICAL_KEYS
    }
    if first != second:
        _fail("B01_PRODUCT_SOURCE_SNAPSHOT_DRIFT")
    return second


def _current_revision_ref(index_payload: Any, chapter_id: str) -> dict[str, Any]:
    if not isinstance(index_payload, list):
        _fail("B01_PRODUCT_CHAPTER_INDEX_INVALID")
    seen: set[str] = set()
    selected: dict[str, Any] | None = None
    for value in index_payload:
        if not isinstance(value, dict) or set(value) != _INDEX_REF_KEYS:
            _fail("B01_PRODUCT_CHAPTER_INDEX_INVALID")
        validate_chapter_revision_ref(value)
        if value["chapter_id"] in seen:
            _fail("B01_PRODUCT_CHAPTER_INDEX_INVALID", "duplicate chapter")
        seen.add(value["chapter_id"])
        if value["chapter_id"] == chapter_id:
            selected = deepcopy(value)
    if selected is None:
        _fail("B01_PRODUCT_CHAPTER_NOT_FOUND", chapter_id)
    return selected


def _validated_materials(payload: Any) -> list[dict[str, Any]]:
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema", "records"}
        or payload.get("schema") != "chapter-materials-v1"
        or not isinstance(payload.get("records"), dict)
    ):
        _fail("B01_PRODUCT_MATERIAL_STORE_INVALID")
    materials: list[dict[str, Any]] = []
    for material_id, value in payload["records"].items():
        if not isinstance(material_id, str) or not material_id:
            _fail("B01_PRODUCT_MATERIAL_STORE_INVALID")
        try:
            material = validate_c10_record(deepcopy(value))
        except C10ContractValidationError as exc:
            raise B01ContractError("B01_PRODUCT_MATERIAL_STORE_INVALID") from exc
        if material["material_unit_id"] != material_id:
            _fail("B01_PRODUCT_MATERIAL_STORE_INVALID")
        materials.append(material)
    return materials


def _validated_current_revision(
    ledger_payload: Any,
    chapter_revision_ref: dict[str, Any],
    materials: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        not isinstance(ledger_payload, dict)
        or set(ledger_payload) != {"schema", "next_chapter_number", "ledgers"}
        or ledger_payload.get("schema") != "chapter-revision-ledgers-v1"
        or not isinstance(ledger_payload.get("ledgers"), dict)
    ):
        _fail("B01_PRODUCT_REVISION_STORE_INVALID")
    chapter_id = chapter_revision_ref["chapter_id"]
    ledger = ledger_payload["ledgers"].get(chapter_id)
    if not isinstance(ledger, dict):
        _fail("B01_PRODUCT_REVISION_STORE_INVALID", "ledger missing")
    try:
        c11_contract.validate_schema_document(c11_contract.schema_validator(), ledger)
    except c11_contract.ContractError as exc:
        raise B01ContractError("B01_PRODUCT_REVISION_STORE_INVALID") from exc
    revisions = ledger["revisions"]
    if (
        ledger.get("chapter_id") != chapter_id
        or not isinstance(revisions, list)
        or [value.get("revision_no") for value in revisions]
        != list(range(1, len(revisions) + 1))
        or ledger.get("current_revision_no") != len(revisions)
    ):
        _fail("B01_PRODUCT_REVISION_STORE_INVALID", "revision sequence")
    current = revisions[-1]
    expected_ref = {
        "chapter_id": chapter_id,
        "revision_no": current["revision_no"],
        "revision_text_sha256": current["text_sha256"],
    }
    if expected_ref != chapter_revision_ref or current.get("actor") != "AUTHOR":
        _fail("B01_PRODUCT_REVISION_NOT_CURRENT")
    eligibility = c11_contract.validate_current_c10_eligibility(
        current["content_ref"],
        current["origin_material_ref"],
        materials,
        require_referenced_revision_is_current=True,
    )
    if eligibility != "C10_CONFIRMED_CHAPTER_ELIGIBLE":
        _fail("B01_PRODUCT_CURRENT_C10_INELIGIBLE", eligibility)
    return deepcopy(ledger), deepcopy(current)


def _validated_initial_operation(
    payload: Any, chapter_id: str, first_revision: dict[str, Any]
) -> dict[str, Any]:
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema", "operations"}
        or payload.get("schema") != "chapter-admission-operations-v1"
        or not isinstance(payload.get("operations"), dict)
    ):
        _fail("B01_PRODUCT_ADMISSION_STORE_INVALID")
    matches = [
        deepcopy(value)
        for operation_id, value in payload["operations"].items()
        if isinstance(operation_id, str)
        and isinstance(value, dict)
        and value.get("operation_id") == operation_id
        and value.get("chapter_id") == chapter_id
    ]
    if len(matches) != 1:
        _fail("B01_PRODUCT_ADMISSION_STORE_INVALID", "chapter operation")
    operation = matches[0]
    origin = first_revision.get("origin_material_ref")
    if (
        first_revision.get("revision_no") != 1
        or first_revision.get("change_kind") != "INITIAL"
        or not isinstance(origin, dict)
        or operation.get("revision_no") != 1
        or operation.get("revision_text_sha256") != first_revision.get("text_sha256")
        or operation.get("operation_id") != first_revision.get("commit_operation_id")
        or operation.get("material_unit_id") != origin.get("material_unit_id")
    ):
        _fail("B01_PRODUCT_ADMISSION_STORE_INVALID", "initial binding")
    return operation


def build_author_workspace_source_generation(
    workspace: AuthorWorkspace, *, chapter_id: str
) -> dict[str, Any]:
    """Return one read-only B-01 source-generation binding for a current chapter."""
    if not isinstance(chapter_id, str) or not chapter_id:
        _fail("B01_PRODUCT_CHAPTER_ID_INVALID")
    if not isinstance(workspace, AuthorWorkspace):
        _fail("B01_PRODUCT_SOURCE_HANDLE_INVALID")
    entries = _stable_entries(workspace)
    chapter_revision_ref = _current_revision_ref(
        entries["chapter_index"]["payload"], chapter_id
    )
    materials = _validated_materials(entries["chapter_materials"]["payload"])
    ledger, current = _validated_current_revision(
        entries["chapter_revisions"]["payload"],
        chapter_revision_ref,
        materials,
    )
    operation = _validated_initial_operation(
        entries["chapter_admission_operations"]["payload"],
        chapter_id,
        ledger["revisions"][0],
    )
    watermarks = {
        key: {
            "version": entries[key]["version"],
            "sha256": entries[key]["sha256"],
        }
        for key in SAFE_LOGICAL_KEYS
    }
    manifest_basis = {
        "adapter_contract": ADAPTER_CONTRACT,
        "project_scope_id": workspace.project_id,
        "chapter_revision_ref": chapter_revision_ref,
        "current_content_ref": current["content_ref"],
        "current_origin_material_ref": current["origin_material_ref"],
        "chapter_admission_operation_id": operation["operation_id"],
        "workspace_watermarks": watermarks,
    }
    manifest_sha256 = sha256_value(manifest_basis)
    generation = make_read_only_input_record(
        record_type="M1_ACCEPTED_SOURCE_GENERATION",
        record_id=f"m1-generation-{manifest_sha256[:16]}",
        record_version=1,
        source_module="M1_READ_ONLY_ADAPTER",
        access=PRODUCT_READ_ONLY_ACCESS,
        retention_class="CORE_IMMUTABLE_AUDIT",
        created_at=current["committed_at"],
        payload={
            "workspace_generation_schema": "author-workspace-generation-v1",
            "chapter_admission_identity": (
                "AUTHOR_WORKSPACE_INITIAL_CHAPTER_ADMISSION_R01"
            ),
            "workspace_generation_id": f"g_{manifest_sha256}",
            "manifest_sha256": manifest_sha256,
            "chapter_revision_ref": chapter_revision_ref,
        },
    )
    return {
        "adapter_contract": ADAPTER_CONTRACT,
        "project_scope_id": workspace.project_id,
        "author_workspace_logical_key": workspace.project_id,
        "chapter_revision_ref": chapter_revision_ref,
        "accepted_source_generation_ref": record_ref(generation),
        "source_generation_record": generation,
        "writing_material_refs": [],
        "writing_material_records": [],
        "source_module_identity": SOURCE_MODULE_IDENTITY,
        "workspace_watermarks": watermarks,
        "read_logical_keys": list(SAFE_LOGICAL_KEYS),
        "forbidden_logical_keys": sorted(FORBIDDEN_LOGICAL_KEYS),
        "product_writes": 0,
        "model_api_calls": 0,
        "real_novel_body_reads": 0,
    }
