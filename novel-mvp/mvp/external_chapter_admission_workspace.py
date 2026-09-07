"""把当前已保存的外部 C10 章节接成 C11 INITIAL 与 C1；不确认事实。

输入仅为绑定工作区和点名动作，正文始终从 M1 不可变上传原件取得。
与作者工作稿共用章节存储、编号及原子事务，来源和接纳动作保持不同身份。
"""

from __future__ import annotations

import copy
from typing import Any, NoReturn

from contracts import validate_c11_chapter_revision_ledger as c11_contract
from contracts.validate_c10_intake_material_identity import (
    c1_emission_eligible,
    current_identity,
    validate_record,
)
from mvp import chapter_initial_admission_workspace as admission
from mvp import chapterize, external_chapter_route_tool, ingest_workspace
from mvp import input_router, intake_identity
from mvp.workspace import OPERATION_ID_RE, AuthorWorkspace


ACTION_CONTRACT = "EXTERNAL_CHAPTER_ADMISSION_ACTION"
RECEIPT_IDENTITY = "EXTERNAL_CHAPTER_INITIAL_ADMISSION_R01"
ACTION_KEYS = {
    "contract",
    "version",
    "operation_id",
    "actor",
    "intent",
    "material_unit_id",
    "identity_revision_no",
    "chapter_title",
    "expected_m1_state",
    "expected_next_chapter_number",
}


class ExternalChapterAdmissionError(ValueError):
    """外部材料不能按这次点名动作接纳。"""


def _fail(code: str) -> NoReturn:
    raise ExternalChapterAdmissionError(code)


def _workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _validated_action(action: object) -> dict[str, Any]:
    if not isinstance(action, dict) or set(action) != ACTION_KEYS:
        _fail("EXTERNAL_ADMISSION_ACTION_FIELDS_INVALID")
    if (
        action["contract"] != ACTION_CONTRACT
        or action["version"] != "v1"
        or action["actor"] != "AUTHOR"
        or action["intent"] != "ADMIT_AS_INITIAL_CHAPTER"
    ):
        _fail("EXTERNAL_ADMISSION_ACTION_IDENTITY_INVALID")
    for key in ("operation_id", "material_unit_id", "chapter_title"):
        value = action[key]
        if not isinstance(value, str) or not value or value != value.strip():
            _fail(f"EXTERNAL_ADMISSION_ACTION_FIELD_INVALID:{key}")
    if OPERATION_ID_RE.fullmatch(action["operation_id"]) is None:
        _fail("OPERATION_ID_INVALID")
    for key in ("identity_revision_no", "expected_next_chapter_number"):
        if type(action[key]) is not int or action[key] < 1:
            _fail(f"EXTERNAL_ADMISSION_ACTION_FIELD_INVALID:{key}")
    admission._validated_m1_state(action["expected_m1_state"])
    admission._canonical_bytes(action)
    return copy.deepcopy(action)


def _materials(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = snapshot["module_state"].get("material_units")
    if not isinstance(records, list) or not records:
        _fail("EXTERNAL_M1_MATERIALS_REQUIRED")
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        try:
            validated = validate_record(copy.deepcopy(record))
        except (ValueError, TypeError, KeyError) as exc:
            raise ExternalChapterAdmissionError("EXTERNAL_M1_MATERIAL_INVALID") from exc
        material_id = validated["material_unit_id"]
        if material_id in indexed:
            _fail("EXTERNAL_M1_MATERIAL_DUPLICATE")
        indexed[material_id] = validated
    return indexed


def _source(snapshot: dict[str, Any], source_id: str) -> dict[str, Any]:
    stored = snapshot["module_state"].get("sources")
    if not isinstance(stored, list) or any(not isinstance(row, dict) for row in stored):
        _fail("EXTERNAL_M1_SOURCES_INVALID")
    matches = [row for row in stored if row.get("source_id") == source_id]
    if len(matches) != 1:
        _fail("EXTERNAL_M1_SOURCE_NOT_UNIQUE")
    saved = matches[0]
    uploads = [
        upload
        for upload in snapshot["upload_sources"]
        if upload.source_name == saved.get("source_name")
    ]
    if len(uploads) != 1:
        _fail("EXTERNAL_DIRECT_TEXT_UPLOAD_REQUIRED")
    upload = uploads[0]
    # Reuse M1's decoder/format gate. Do not trust a stored decoded string alone.
    items, receipt = input_router.collect_uploads([upload])
    if receipt["status"] != "READY" or len(items) != 1:
        _fail("EXTERNAL_DIRECT_TEXT_UPLOAD_REQUIRED")
    item = items[0]
    if (
        item["source_name"] != upload.source_name
        or item["raw_bytes"] != upload.raw_bytes
    ):
        _fail("EXTERNAL_DIRECT_TEXT_UPLOAD_REQUIRED")
    expected = intake_identity._source_record(
        item["source_name"],
        item["raw_bytes"],
        item["encoding"],
        intake_identity._decode_source(item["raw_bytes"], item["encoding"]),
    )
    expected_saved = {
        key: value for key, value in expected.items() if key != "original_bytes_base64"
    }
    if saved != expected_saved:
        _fail("EXTERNAL_M1_SOURCE_REPLAY_MISMATCH")
    upload_record = next(
        row for row in snapshot["uploads"] if row["source_name"] == upload.source_name
    )
    expected["origin"] = {
        "kind": admission.EXTERNAL_KIND,
        "immutable_receipt": copy.deepcopy(upload_record["immutable_receipt"]),
    }
    return admission._validated_source(expected, source_id)


def _material_context(
    snapshot: dict[str, Any], material: dict[str, Any]
) -> dict[str, Any]:
    if not c1_emission_eligible(material):
        _fail("C10_NOT_CONFIRMED_CHAPTER")
    ref = material["source_ref"]
    source = _source(snapshot, ref["source_id"])
    source_materials = [
        row
        for row in _materials(snapshot).values()
        if row["source_ref"]["source_id"] == source["source_id"]
    ]
    try:
        intake_identity._validate_exact_coverage(
            source_materials, source["decoded_text"]
        )
    except ValueError as exc:
        raise ExternalChapterAdmissionError(
            "EXTERNAL_M1_SOURCE_COVERAGE_INVALID"
        ) from exc
    start, end = ref["start"], ref["end"]
    if not 0 <= start < end <= len(source["decoded_text"]):
        _fail("EXTERNAL_MATERIAL_SPAN_INVALID")
    text = source["decoded_text"][start:end]
    if (
        ref["source_sha256"] != source["source_sha256"]
        or ref["slice_sha256"] != admission._text_sha256(text)
        or material["material_unit_id"]
        != intake_identity._stable_unit_id(source["source_id"], start, end)
    ):
        _fail("EXTERNAL_MATERIAL_SOURCE_MISMATCH")
    if not text.strip():
        _fail("EXTERNAL_CHAPTER_TEXT_EMPTY")
    chapterization = chapterize.chapterize_text(
        text,
        default_title=source["source_name"],
        format_hint=intake_identity._chapterization_format_hint(source["source_name"]),
    )
    if chapterization["status"] == "BLOCKED":
        _fail("EXTERNAL_CHAPTER_BOUNDARY_BLOCKED")
    if len(chapterization["candidates"]) != 1:
        _fail("EXTERNAL_MATERIAL_REQUIRES_CHAPTER_SPLIT")
    return {
        "source": source,
        "text": text,
        "title": chapterization["candidates"][0]["title"],
    }


def _require_new_material(payloads: dict[str, Any], material: dict[str, Any]) -> None:
    if material["material_unit_id"] in payloads[admission.MATERIAL_KEY]["records"]:
        _fail("EXTERNAL_MATERIAL_ALREADY_ADMITTED")
    selected_ref = material["source_ref"]
    for admitted in payloads[admission.MATERIAL_KEY]["records"].values():
        old_ref = admitted["source_ref"]
        if old_ref["source_id"] == selected_ref["source_id"] and max(
            old_ref["start"], selected_ref["start"]
        ) < min(old_ref["end"], selected_ref["end"]):
            _fail("EXTERNAL_MATERIAL_OVERLAPS_ADMITTED_CHAPTER")


def preview_external_chapters(workspace: AuthorWorkspace) -> dict[str, Any]:
    """列出当前材料可否接成单章及动作所需水位；不返回正文，不写章节。"""
    handle = _workspace(workspace)
    before = admission._read_bundle(handle)
    snapshot = ingest_workspace.load_persisted_m1_snapshot(handle)
    candidates = []
    for material in _materials(snapshot).values():
        row = {
            "material_unit_id": material["material_unit_id"],
            "identity_revision_no": current_identity(material)["revision_no"],
            "source_ref": copy.deepcopy(material["source_ref"]),
        }
        try:
            _require_new_material(before["payloads"], material)
            context = _material_context(snapshot, material)
            row.update(
                eligible=True,
                title=context["title"],
                chars=len(context["text"]),
                reason=None,
            )
        except ExternalChapterAdmissionError as exc:
            row.update(eligible=False, title=None, chars=None, reason=str(exc))
        candidates.append(row)
    if (
        admission._read_bundle(handle)["raw"] != before["raw"]
        or ingest_workspace.read_persisted_m1_state(handle)["state_identity"]
        != snapshot["state_identity"]
    ):
        _fail("EXTERNAL_ADMISSION_PREVIEW_CHANGED")
    return {
        "identity": "EXTERNAL_CHAPTER_ADMISSION_PREVIEW_R01",
        "m1_state": copy.deepcopy(snapshot["state_identity"]),
        "next_chapter_number": before["payloads"][admission.LEDGER_KEY][
            "next_chapter_number"
        ],
        "candidates": candidates,
        "writes": [],
    }


def _result(
    bundle: dict[str, Any], operation: dict[str, Any], *, replayed: bool
) -> dict[str, Any]:
    chapter_id = operation["chapter_id"]
    payloads = bundle["payloads"]
    material = payloads[admission.MATERIAL_KEY]["records"][
        operation["material_unit_id"]
    ]
    ledger = payloads[admission.LEDGER_KEY]["ledgers"][chapter_id]
    chapter = next(
        row for row in payloads[admission.CHAPTERS_KEY] if row["id"] == chapter_id
    )
    route = external_chapter_route_tool.execute(
        {
            "material_identity": material,
            "chapter_revision_ledger": ledger,
            "chapter_doc": chapter,
        }
    )
    return {
        "identity": RECEIPT_IDENTITY,
        "status": admission.EXTERNAL_STAGE,
        "operation_id": operation["operation_id"],
        "replayed": replayed,
        "chapter_id": chapter_id,
        "chapter_revision_ref": copy.deepcopy(chapter["chapter_revision_ref"]),
        "source_ref": copy.deepcopy(material["source_ref"]),
        "material_unit_id": material["material_unit_id"],
        "identity_revision_no": operation["identity_revision_no"],
        "m1_state": copy.deepcopy(operation["m1_state"]),
        "workspace_state": copy.deepcopy(bundle["watermarks"]),
        "route_receipt": route,
        "facts_write": 0,
        "planstore_write": 0,
    }


def commit_external_chapter(
    workspace: AuthorWorkspace,
    action: dict[str, Any],
    committed_at: str,
) -> dict[str, Any]:
    """只从当前已保存的 C10 章节及原上传取得正文，原子接成一条 INITIAL。"""
    handle = _workspace(workspace)
    action = _validated_action(action)
    committed_at, added_at = admission._committed_at(committed_at)
    request_sha = admission._sha256(
        {"external_action": action, "committed_at": committed_at}
    )
    handle.recover()
    before = admission._read_bundle(handle)
    payloads = copy.deepcopy(before["payloads"])
    operations = payloads[admission.OPERATIONS_KEY]["operations"]
    existing = operations.get(action["operation_id"])
    if existing is not None:
        if (
            existing.get("kind") != admission.EXTERNAL_KIND
            or existing["request_sha256"] != request_sha
        ):
            _fail("OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST")
        if admission._read_bundle(handle)["raw"] != before["raw"]:
            _fail("EXTERNAL_ADMISSION_STATE_CHANGED_DURING_REPLAY")
        return _result(before, existing, replayed=True)
    next_number = payloads[admission.LEDGER_KEY]["next_chapter_number"]
    if next_number != action["expected_next_chapter_number"]:
        _fail("EXTERNAL_CHAPTER_ALLOCATOR_CHANGED")
    snapshot = ingest_workspace.load_persisted_m1_snapshot(handle)
    if snapshot["state_identity"] != action["expected_m1_state"]:
        _fail("EXTERNAL_M1_STATE_STALE")
    material = _materials(snapshot).get(action["material_unit_id"])
    if material is None:
        _fail("EXTERNAL_MATERIAL_NOT_FOUND")
    identity_revision = current_identity(material)["revision_no"]
    if identity_revision != action["identity_revision_no"]:
        _fail("EXTERNAL_C10_REVISION_STALE")
    _require_new_material(payloads, material)
    context = _material_context(snapshot, material)
    source, text = context["source"], context["text"]
    source_id = source["source_id"]
    prior_source = payloads[admission.SOURCE_KEY]["sources"].get(source_id)
    if prior_source is not None:
        if prior_source["origin"]["kind"] != admission.EXTERNAL_KIND or {
            k: v for k, v in prior_source.items() if k != "origin"
        } != {k: v for k, v in source.items() if k != "origin"}:
            _fail("EXTERNAL_SOURCE_ID_COLLISION")
        source = prior_source
    chapter_id = f"c{next_number:02d}"
    text_sha = admission._text_sha256(text)
    revision_ref = {
        "chapter_id": chapter_id,
        "revision_no": 1,
        "revision_text_sha256": text_sha,
    }
    ledger = {
        "contract": "CHAPTER_REVISION_LEDGER",
        "version": "v1",
        "chapter_id": chapter_id,
        "current_revision_no": 1,
        "last_operation_id": action["operation_id"],
        "revisions": [
            {
                "revision_no": 1,
                "title": action["chapter_title"],
                "text_sha256": text_sha,
                "chars": len(text),
                "content_ref": {"kind": "C10_SOURCE_SPAN", **material["source_ref"]},
                "origin_material_ref": {
                    "material_unit_id": material["material_unit_id"],
                    "identity_revision_no": identity_revision,
                },
                "change_kind": "INITIAL",
                "restores_revision_no": None,
                "committed_at": committed_at,
                "commit_operation_id": action["operation_id"],
                "actor": "AUTHOR",
            }
        ],
    }
    gate = c11_contract.validate_initial_commit(ledger, [material])
    if gate != "C10_CONFIRMED_CHAPTER_ELIGIBLE":
        _fail(f"EXTERNAL_INITIAL_C11_GATE_FAILED:{gate}")
    chapter = {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": chapter_id,
        "title": action["chapter_title"],
        "kind": "draft",
        "text": text,
        "added_at": added_at,
        "chapter_revision_ref": revision_ref,
    }
    operation = {
        "kind": admission.EXTERNAL_KIND,
        "stage": admission.EXTERNAL_STAGE,
        "operation_id": action["operation_id"],
        "request_sha256": request_sha,
        "chapter_title": action["chapter_title"],
        "chapter_id": chapter_id,
        "source_id": source_id,
        "material_unit_id": material["material_unit_id"],
        "identity_revision_no": identity_revision,
        "revision_no": 1,
        "revision_text_sha256": text_sha,
        "committed_at": committed_at,
        "m1_state": copy.deepcopy(snapshot["state_identity"]),
    }
    payloads[admission.SOURCE_KEY]["schema"] = admission.EXTERNAL_SOURCE_STORE_SCHEMA
    payloads[admission.OPERATIONS_KEY]["schema"] = (
        admission.EXTERNAL_OPERATION_STORE_SCHEMA
    )
    payloads[admission.SOURCE_KEY]["sources"][source_id] = source
    payloads[admission.MATERIAL_KEY]["records"][material["material_unit_id"]] = material
    payloads[admission.LEDGER_KEY]["ledgers"][chapter_id] = ledger
    payloads[admission.LEDGER_KEY]["next_chapter_number"] = next_number + 1
    payloads[admission.CHAPTERS_KEY].append(chapter)
    payloads[admission.INDEX_KEY].append(revision_ref)
    operations[action["operation_id"]] = operation
    payloads = admission._validated_payloads(payloads)
    # Validate the exact downstream route before the first visible write.
    external_chapter_route_tool.execute(
        {
            "material_identity": material,
            "chapter_revision_ledger": ledger,
            "chapter_doc": chapter,
        }
    )
    handle.commit_guarded(
        action["operation_id"],
        payloads,
        before["watermarks"],
        snapshot["state_identity"],
    )
    after = admission._read_bundle(handle)
    return _result(
        after,
        after["payloads"][admission.OPERATIONS_KEY]["operations"][
            action["operation_id"]
        ],
        replayed=False,
    )


def resolve_external_admission(
    workspace: AuthorWorkspace, operation_id: str
) -> dict[str, Any]:
    """重开时从正式 owner 读回外部接纳结果，附逐字章节供现有 M2 使用。"""
    handle = _workspace(workspace)
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        _fail("OPERATION_ID_INVALID")
    first = admission._read_bundle(handle)
    operation = first["payloads"][admission.OPERATIONS_KEY]["operations"].get(
        operation_id
    )
    if operation is None or operation.get("kind") != admission.EXTERNAL_KIND:
        _fail("EXTERNAL_ADMISSION_NOT_FOUND")
    if admission._read_bundle(handle)["raw"] != first["raw"]:
        _fail("EXTERNAL_ADMISSION_STATE_CHANGED_DURING_READ")
    chapter_id = operation["chapter_id"]
    return {
        **_result(first, operation, replayed=True),
        "chapter": copy.deepcopy(
            next(
                row
                for row in first["payloads"][admission.CHAPTERS_KEY]
                if row["id"] == chapter_id
            )
        ),
        "ledger": copy.deepcopy(
            first["payloads"][admission.LEDGER_KEY]["ledgers"][chapter_id]
        ),
        "material": copy.deepcopy(
            first["payloads"][admission.MATERIAL_KEY]["records"][
                operation["material_unit_id"]
            ]
        ),
    }


__all__ = [
    "ExternalChapterAdmissionError",
    "preview_external_chapters",
    "commit_external_chapter",
    "resolve_external_admission",
]
