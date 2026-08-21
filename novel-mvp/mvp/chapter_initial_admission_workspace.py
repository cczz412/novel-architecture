"""把作者明确交棒的 current 工作稿原子接成 C10、C11 与 C1。

这是 AuthorWorkspace 内的 INITIAL 章节接收器。它负责冻结工作稿来源、
分配稳定 chapter_id、通过正式 C10/C11 机器门，并一次提交 C1 current view。
planstore 仍是第二步；本模块只诚实记录 AW_COMMITTED_PLANSTORE_PENDING。
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, NoReturn

from contracts import validate_c11_chapter_revision_ledger as c11_contract
from contracts.validate_c10_intake_material_identity import validate_record
from mvp import chapter_workspace, store, work_draft_workspace
from mvp.workspace import OPERATION_ID_RE, SHA256_RE, AuthorWorkspace


SOURCE_KEY = "chapter_sources"
MATERIAL_KEY = "chapter_materials"
LEDGER_KEY = "chapter_revisions"
CHAPTERS_KEY = "chapters"
INDEX_KEY = "chapter_index"
OPERATIONS_KEY = "chapter_admission_operations"
STATE_KEYS = {
    SOURCE_KEY,
    MATERIAL_KEY,
    LEDGER_KEY,
    CHAPTERS_KEY,
    INDEX_KEY,
    OPERATIONS_KEY,
}
SOURCE_STORE_SCHEMA = "chapter-sources-v1"
MATERIAL_STORE_SCHEMA = "chapter-materials-v1"
LEDGER_STORE_SCHEMA = "chapter-revision-ledgers-v1"
OPERATION_STORE_SCHEMA = "chapter-admission-operations-v1"
ADMISSION_IDENTITY = "AUTHOR_WORKSPACE_INITIAL_CHAPTER_ADMISSION_R01"
SOURCE_KEYS = {
    "storage_contract",
    "source_id",
    "source_name",
    "source_sha256",
    "encoding",
    "normalization",
    "original_bytes_base64",
    "decoded_text",
    "origin",
}
SOURCE_ORIGIN_KEYS = {
    "kind",
    "work_ref",
    "work_rev",
    "handover_operation_id",
}
ADMISSION_KEYS = {
    "operation_id",
    "request_sha256",
    "stage",
    "work_ref",
    "work_rev",
    "slot_ref",
    "source_outline_ref",
    "chapter_title",
    "chapter_id",
    "source_id",
    "material_unit_id",
    "revision_no",
    "revision_text_sha256",
    "committed_at",
    "plan_handover",
}
ADMISSION_STAGES = {
    "AW_COMMITTED_PLANSTORE_PENDING",
    "HANDOVER_COMPLETE",
}
PLAN_HANDOVER_KEYS = {
    "operation_id",
    "request_sha256",
    "plan_version",
    "plan_sha256",
    "mapping_id",
    "handover_part_no",
    "handed_at",
}


class ChapterInitialAdmissionError(ValueError):
    """工作稿还不能成为一条合法 INITIAL 章节。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise ChapterInitialAdmissionError(code)


def _workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ChapterInitialAdmissionError("VALUE_NOT_CANONICAL_JSON") from exc


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(value: object) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _text_sha256(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _committed_at(value: object) -> tuple[str, str]:
    if not isinstance(value, str) or not value or value != value.strip():
        _fail("COMMITTED_AT_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ChapterInitialAdmissionError("COMMITTED_AT_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("COMMITTED_AT_INVALID")
    return value, parsed.strftime("%Y-%m-%d %H:%M:%S")


def _empty_payloads() -> dict[str, object]:
    return {
        SOURCE_KEY: {"schema": SOURCE_STORE_SCHEMA, "sources": {}},
        MATERIAL_KEY: {"schema": MATERIAL_STORE_SCHEMA, "records": {}},
        LEDGER_KEY: {
            "schema": LEDGER_STORE_SCHEMA,
            "next_chapter_number": 1,
            "ledgers": {},
        },
        CHAPTERS_KEY: [],
        INDEX_KEY: [],
        OPERATIONS_KEY: {"schema": OPERATION_STORE_SCHEMA, "operations": {}},
    }


def _entry(entry: object, logical_key: str) -> tuple[int, str, object]:
    if (
        not isinstance(entry, dict)
        or set(entry) != {"logical_key", "version", "sha256", "payload"}
        or entry.get("logical_key") != logical_key
        or not isinstance(entry.get("version"), int)
        or isinstance(entry.get("version"), bool)
        or entry["version"] < 1
        or not isinstance(entry.get("sha256"), str)
        or SHA256_RE.fullmatch(entry["sha256"]) is None
    ):
        _fail(f"CHAPTER_ADMISSION_WORKSPACE_ENTRY_INVALID:{logical_key}")
    return entry["version"], entry["sha256"], copy.deepcopy(entry["payload"])


def _validated_source(value: object, source_id: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != SOURCE_KEYS:
        _fail("CHAPTER_SOURCE_STORE_INVALID")
    origin = value.get("origin")
    if not isinstance(origin, dict) or set(origin) != SOURCE_ORIGIN_KEYS:
        _fail("CHAPTER_SOURCE_STORE_INVALID")
    raw_base64 = value.get("original_bytes_base64")
    if (
        value.get("storage_contract") != "INTAKE_PARENT_SOURCE_V1"
        or value.get("source_id") != source_id
        or not isinstance(value.get("source_name"), str)
        or not value["source_name"]
        or not isinstance(value.get("source_sha256"), str)
        or SHA256_RE.fullmatch(value["source_sha256"]) is None
        or value.get("encoding") != "utf-8"
        or value.get("normalization") != "none"
        or not isinstance(raw_base64, str)
        or not isinstance(value.get("decoded_text"), str)
        or origin.get("kind") != "AUTHOR_WORK_DRAFT_FREEZE"
        or not isinstance(origin.get("work_ref"), str)
        or not origin["work_ref"]
        or not isinstance(origin.get("work_rev"), int)
        or isinstance(origin.get("work_rev"), bool)
        or origin["work_rev"] < 1
        or not isinstance(origin.get("handover_operation_id"), str)
        or OPERATION_ID_RE.fullmatch(origin["handover_operation_id"]) is None
    ):
        _fail("CHAPTER_SOURCE_STORE_INVALID")
    try:
        raw = base64.b64decode(raw_base64, validate=True)
        decoded = raw.decode("utf-8", errors="strict")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ChapterInitialAdmissionError("CHAPTER_SOURCE_STORE_INVALID") from exc
    if decoded != value["decoded_text"]:
        _fail("CHAPTER_SOURCE_TEXT_MISMATCH")
    if _sha256_bytes(raw) != value["source_sha256"]:
        _fail("CHAPTER_SOURCE_SHA_MISMATCH")
    return copy.deepcopy(value)


def _validated_admission(value: object, operation_id: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != ADMISSION_KEYS:
        _fail("CHAPTER_ADMISSION_OPERATION_STORE_INVALID")
    string_fields = (
        "operation_id",
        "stage",
        "work_ref",
        "slot_ref",
        "source_outline_ref",
        "chapter_title",
        "chapter_id",
        "source_id",
        "material_unit_id",
        "committed_at",
    )
    if any(not isinstance(value.get(key), str) or not value[key] for key in string_fields):
        _fail("CHAPTER_ADMISSION_OPERATION_STORE_INVALID")
    if (
        value["operation_id"] != operation_id
        or OPERATION_ID_RE.fullmatch(operation_id) is None
        or value["stage"] not in ADMISSION_STAGES
        or not isinstance(value.get("request_sha256"), str)
        or SHA256_RE.fullmatch(value["request_sha256"]) is None
        or not isinstance(value.get("revision_text_sha256"), str)
        or SHA256_RE.fullmatch(value["revision_text_sha256"]) is None
        or value.get("revision_no") != 1
        or not isinstance(value.get("work_rev"), int)
        or isinstance(value.get("work_rev"), bool)
        or value["work_rev"] < 1
    ):
        _fail("CHAPTER_ADMISSION_OPERATION_STORE_INVALID")
    _committed_at(value["committed_at"])
    plan_handover = value.get("plan_handover")
    if value["stage"] == "AW_COMMITTED_PLANSTORE_PENDING":
        if plan_handover is not None:
            _fail("PENDING_ADMISSION_HAS_PLAN_HANDOVER")
    elif (
        not isinstance(plan_handover, dict)
        or set(plan_handover) != PLAN_HANDOVER_KEYS
        or not isinstance(plan_handover.get("operation_id"), str)
        or OPERATION_ID_RE.fullmatch(plan_handover["operation_id"]) is None
        or not isinstance(plan_handover.get("request_sha256"), str)
        or SHA256_RE.fullmatch(plan_handover["request_sha256"]) is None
        or not isinstance(plan_handover.get("plan_version"), int)
        or isinstance(plan_handover.get("plan_version"), bool)
        or plan_handover["plan_version"] < 1
        or not isinstance(plan_handover.get("plan_sha256"), str)
        or SHA256_RE.fullmatch(plan_handover["plan_sha256"]) is None
        or not isinstance(plan_handover.get("mapping_id"), str)
        or not plan_handover["mapping_id"]
        or not isinstance(plan_handover.get("handover_part_no"), int)
        or isinstance(plan_handover.get("handover_part_no"), bool)
        or plan_handover["handover_part_no"] < 1
    ):
        _fail("COMPLETED_ADMISSION_PLAN_HANDOVER_INVALID")
    if plan_handover is not None:
        _committed_at(plan_handover.get("handed_at"))
    return copy.deepcopy(value)


def _validated_payloads(payloads: dict[str, object]) -> dict[str, object]:
    source_store = payloads[SOURCE_KEY]
    material_store = payloads[MATERIAL_KEY]
    ledger_store = payloads[LEDGER_KEY]
    operation_store = payloads[OPERATIONS_KEY]
    if (
        not isinstance(source_store, dict)
        or set(source_store) != {"schema", "sources"}
        or source_store.get("schema") != SOURCE_STORE_SCHEMA
        or not isinstance(source_store.get("sources"), dict)
        or not isinstance(material_store, dict)
        or set(material_store) != {"schema", "records"}
        or material_store.get("schema") != MATERIAL_STORE_SCHEMA
        or not isinstance(material_store.get("records"), dict)
        or not isinstance(ledger_store, dict)
        or set(ledger_store) != {"schema", "next_chapter_number", "ledgers"}
        or ledger_store.get("schema") != LEDGER_STORE_SCHEMA
        or not isinstance(ledger_store.get("ledgers"), dict)
        or not isinstance(ledger_store.get("next_chapter_number"), int)
        or isinstance(ledger_store.get("next_chapter_number"), bool)
        or ledger_store["next_chapter_number"] < 1
        or not isinstance(operation_store, dict)
        or set(operation_store) != {"schema", "operations"}
        or operation_store.get("schema") != OPERATION_STORE_SCHEMA
        or not isinstance(operation_store.get("operations"), dict)
    ):
        _fail("CHAPTER_ADMISSION_STORE_INVALID")

    sources = {
        source_id: _validated_source(source, source_id)
        for source_id, source in source_store["sources"].items()
        if isinstance(source_id, str) and source_id
    }
    if len(sources) != len(source_store["sources"]):
        _fail("CHAPTER_SOURCE_STORE_INVALID")

    materials: dict[str, dict[str, Any]] = {}
    for material_id, material in material_store["records"].items():
        if not isinstance(material_id, str) or not material_id:
            _fail("CHAPTER_MATERIAL_STORE_INVALID")
        try:
            validated = validate_record(copy.deepcopy(material))
        except ValueError as exc:
            raise ChapterInitialAdmissionError("CHAPTER_MATERIAL_STORE_INVALID") from exc
        if validated["material_unit_id"] != material_id:
            _fail("CHAPTER_MATERIAL_STORE_INVALID")
        source_ref = validated["source_ref"]
        source = sources.get(source_ref["source_id"])
        if source is None or source_ref["source_sha256"] != source["source_sha256"]:
            _fail("CHAPTER_MATERIAL_SOURCE_MISMATCH")
        start, end = source_ref["start"], source_ref["end"]
        text = source["decoded_text"]
        if not 0 <= start < end <= len(text):
            _fail("CHAPTER_MATERIAL_SOURCE_MISMATCH")
        if _text_sha256(text[start:end]) != source_ref["slice_sha256"]:
            _fail("CHAPTER_MATERIAL_SLICE_MISMATCH")
        materials[material_id] = validated

    ledgers: dict[str, dict[str, Any]] = {}
    material_records = list(materials.values())
    for chapter_id, ledger in ledger_store["ledgers"].items():
        if (
            not isinstance(chapter_id, str)
            or not isinstance(ledger, dict)
            or ledger.get("chapter_id") != chapter_id
        ):
            _fail("CHAPTER_REVISION_STORE_INVALID")
        try:
            result = c11_contract.validate_initial_commit(
                copy.deepcopy(ledger), material_records
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise ChapterInitialAdmissionError("CHAPTER_REVISION_STORE_INVALID") from exc
        if result != "C10_CONFIRMED_CHAPTER_ELIGIBLE":
            _fail(f"CHAPTER_REVISION_C10_GATE_FAILED:{result}")
        ledgers[chapter_id] = copy.deepcopy(ledger)

    expected_ids = [f"c{number:02d}" for number in range(1, len(ledgers) + 1)]
    if set(ledgers) != set(expected_ids):
        _fail("CHAPTER_ID_SEQUENCE_INVALID")
    if ledger_store["next_chapter_number"] != len(ledgers) + 1:
        _fail("CHAPTER_ID_ALLOCATOR_INVALID")

    chapters = payloads[CHAPTERS_KEY]
    chapter_index = payloads[INDEX_KEY]
    try:
        validated_chapters, validated_index = chapter_workspace._validated_batch(
            chapters, chapter_index
        ) if ledgers else ([], [])
    except (ValueError, TypeError, KeyError) as exc:
        raise ChapterInitialAdmissionError("C1_CURRENT_VIEW_STORE_INVALID") from exc
    if (not ledgers and (chapters != [] or chapter_index != [])) or [
        row["id"] for row in validated_chapters
    ] != expected_ids:
        _fail("C1_CURRENT_VIEW_STORE_INVALID")

    operations = {
        operation_id: _validated_admission(value, operation_id)
        for operation_id, value in operation_store["operations"].items()
        if isinstance(operation_id, str) and operation_id
    }
    if len(operations) != len(operation_store["operations"]):
        _fail("CHAPTER_ADMISSION_OPERATION_STORE_INVALID")
    if len(operations) != len(ledgers):
        _fail("CHAPTER_ADMISSION_OPERATION_COUNT_MISMATCH")
    if len(sources) != len(materials) or len(materials) != len(ledgers):
        _fail("CHAPTER_ADMISSION_OWNER_COUNT_MISMATCH")

    chapter_by_id = {chapter["id"]: chapter for chapter in validated_chapters}
    seen_work: set[tuple[str, int]] = set()
    seen_slots: set[str] = set()
    seen_chapters: set[str] = set()
    seen_sources: set[str] = set()
    seen_materials: set[str] = set()
    for operation in operations.values():
        work_key = (operation["work_ref"], operation["work_rev"])
        if (
            work_key in seen_work
            or operation["slot_ref"] in seen_slots
            or operation["chapter_id"] in seen_chapters
        ):
            _fail("CHAPTER_ADMISSION_OPERATION_DUPLICATE_IDENTITY")
        seen_work.add(work_key)
        seen_slots.add(operation["slot_ref"])
        seen_chapters.add(operation["chapter_id"])
        seen_sources.add(operation["source_id"])
        seen_materials.add(operation["material_unit_id"])
        source = sources.get(operation["source_id"])
        material = materials.get(operation["material_unit_id"])
        ledger = ledgers.get(operation["chapter_id"])
        chapter = chapter_by_id.get(operation["chapter_id"])
        if source is None or material is None or ledger is None or chapter is None:
            _fail("CHAPTER_ADMISSION_OPERATION_REFERENCE_MISSING")
        revision = ledger["revisions"][0]
        ref = chapter["chapter_revision_ref"]
        if (
            source["origin"]["work_ref"] != operation["work_ref"]
            or source["origin"]["work_rev"] != operation["work_rev"]
            or source["origin"]["handover_operation_id"] != operation["operation_id"]
            or material["source_ref"]["source_id"] != operation["source_id"]
            or revision["origin_material_ref"]["material_unit_id"]
            != operation["material_unit_id"]
            or revision["commit_operation_id"] != operation["operation_id"]
            or revision["title"] != operation["chapter_title"]
            or revision["committed_at"] != operation["committed_at"]
            or revision["text_sha256"] != operation["revision_text_sha256"]
            or chapter["title"] != operation["chapter_title"]
            or chapter["text"] != source["decoded_text"]
            or ref["revision_no"] != 1
            or ref["revision_text_sha256"] != operation["revision_text_sha256"]
        ):
            _fail("CHAPTER_ADMISSION_OPERATION_REFERENCE_MISMATCH")
    if seen_chapters != set(ledgers) or seen_sources != set(sources):
        _fail("CHAPTER_ADMISSION_OPERATION_REFERENCE_SET_MISMATCH")
    if seen_materials != set(materials):
        _fail("CHAPTER_ADMISSION_OPERATION_REFERENCE_SET_MISMATCH")

    return {
        SOURCE_KEY: {"schema": SOURCE_STORE_SCHEMA, "sources": sources},
        MATERIAL_KEY: {"schema": MATERIAL_STORE_SCHEMA, "records": materials},
        LEDGER_KEY: {
            "schema": LEDGER_STORE_SCHEMA,
            "next_chapter_number": ledger_store["next_chapter_number"],
            "ledgers": ledgers,
        },
        CHAPTERS_KEY: validated_chapters,
        INDEX_KEY: validated_index,
        OPERATIONS_KEY: {
            "schema": OPERATION_STORE_SCHEMA,
            "operations": operations,
        },
    }


def _read_bundle(workspace: AuthorWorkspace) -> dict[str, Any]:
    raw = {key: workspace.read(key) for key in STATE_KEYS}
    present = {key for key, value in raw.items() if value is not None}
    if present and present != STATE_KEYS:
        _fail("CHAPTER_ADMISSION_STATE_PARTIAL")
    if not present:
        payloads = _empty_payloads()
        watermarks = {key: {"version": 0, "sha256": None} for key in STATE_KEYS}
    else:
        payloads: dict[str, object] = {}
        watermarks: dict[str, dict[str, object]] = {}
        for key in STATE_KEYS:
            version, sha256, payload = _entry(raw[key], key)
            payloads[key] = payload
            watermarks[key] = {"version": version, "sha256": sha256}
        payloads = _validated_payloads(payloads)
    return {"payloads": payloads, "watermarks": watermarks, "raw": raw}


def _stable_ids(
    workspace: AuthorWorkspace,
    work_ref: str,
    work_rev: int,
    text_sha256: str,
    text_length: int,
) -> tuple[str, str]:
    source_digest = _text_sha256(
        f"{workspace.project_id}\0{work_ref}\0{work_rev}\0{text_sha256}"
    )
    source_id = f"SRC-WORK-{source_digest[:20].upper()}"
    material_digest = _text_sha256(f"{source_id}:0:{text_length}")
    return source_id, f"MU-WORK-{material_digest[:20].upper()}"


def _request_sha(action: Mapping[str, Any], committed_at: str) -> str:
    return _sha256(
        {
            "handover_action": copy.deepcopy(dict(action)),
            "committed_at": committed_at,
        }
    )


def _result(
    bundle: dict[str, Any],
    operation: dict[str, Any],
    *,
    replayed: bool,
) -> dict[str, Any]:
    plan_handover = copy.deepcopy(operation["plan_handover"])
    return {
        "identity": ADMISSION_IDENTITY,
        "status": operation["stage"],
        "replayed": replayed,
        "operation_id": operation["operation_id"],
        "chapter_id": operation["chapter_id"],
        "chapter_revision_ref": {
            "chapter_id": operation["chapter_id"],
            "revision_no": 1,
            "revision_text_sha256": operation["revision_text_sha256"],
        },
        "source_ref": {
            "source_id": operation["source_id"],
            "material_unit_id": operation["material_unit_id"],
            "identity_revision_no": 1,
        },
        "workspace_state": copy.deepcopy(bundle["watermarks"]),
        "plan_handover": plan_handover,
        "planstore_write": 0 if plan_handover is None else 1,
    }


def commit_initial_work_draft(
    workspace: AuthorWorkspace,
    handover_action: Mapping[str, Any],
    committed_at: str,
) -> dict[str, Any]:
    """把一个 current 工作稿接成受控 INITIAL 章节；planstore 留在待处理态。"""
    handle = _workspace(workspace)
    normalized_action = work_draft_workspace._validated_handover_action(
        handover_action
    )
    committed_at, added_at = _committed_at(committed_at)
    request_sha = _request_sha(normalized_action, committed_at)
    handle.recover()

    before = _read_bundle(handle)
    existing = before["payloads"][OPERATIONS_KEY]["operations"].get(
        normalized_action["operation_id"]
    )
    if existing is not None:
        if existing["request_sha256"] != request_sha:
            _fail("OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST")
        after = _read_bundle(handle)
        if before["raw"] != after["raw"]:
            _fail("CHAPTER_ADMISSION_STATE_CHANGED_DURING_REPLAY")
        return _result(after, existing, replayed=True)

    preflight = work_draft_workspace.prepare_explicit_handover(
        handle, normalized_action
    )
    draft = preflight["current_work_draft"]
    text = draft["text"]
    if not text:
        _fail("INITIAL_CHAPTER_TEXT_EMPTY")
    text_sha = _text_sha256(text)
    source_id, material_id = _stable_ids(
        handle,
        draft["work_ref"],
        draft["work_rev"],
        text_sha,
        len(text),
    )
    operations = before["payloads"][OPERATIONS_KEY]["operations"]
    if any(
        operation["work_ref"] == draft["work_ref"]
        and operation["work_rev"] == draft["work_rev"]
        for operation in operations.values()
    ):
        _fail("WORK_DRAFT_REVISION_ALREADY_ADMITTED")
    if any(
        operation["slot_ref"] == draft["slot_ref"]
        for operation in operations.values()
    ):
        _fail("SLOT_ALREADY_HAS_INITIAL_CHAPTER")

    payloads = copy.deepcopy(before["payloads"])
    next_number = payloads[LEDGER_KEY]["next_chapter_number"]
    chapter_id = f"c{next_number:02d}"
    raw = text.encode("utf-8")
    source = {
        "storage_contract": "INTAKE_PARENT_SOURCE_V1",
        "source_id": source_id,
        "source_name": f"work-draft-{source_id[-12:].lower()}.txt",
        "source_sha256": _sha256_bytes(raw),
        "encoding": "utf-8",
        "normalization": "none",
        "original_bytes_base64": base64.b64encode(raw).decode("ascii"),
        "decoded_text": text,
        "origin": {
            "kind": "AUTHOR_WORK_DRAFT_FREEZE",
            "work_ref": draft["work_ref"],
            "work_rev": draft["work_rev"],
            "handover_operation_id": normalized_action["operation_id"],
        },
    }
    source_ref = {
        "source_id": source_id,
        "source_sha256": source["source_sha256"],
        "coordinate_basis": "DECODED_UNICODE_CODEPOINT_V1",
        "start": 0,
        "end": len(text),
        "slice_sha256": text_sha,
    }
    material = {
        "contract": "C10_INTAKE_MATERIAL_IDENTITY",
        "version": "v4",
        "material_unit_id": material_id,
        "source_ref": source_ref,
        "identity_revisions": [
            {
                "revision_no": 1,
                "role": "CHAPTER",
                "state": "CONFIRMED",
                "basis": {
                    "type": "USER_DECLARATION",
                    "reference": (
                        f"WORK_DRAFT_HANDOVER_ACTION:{normalized_action['operation_id']}"
                    ),
                },
                "actor": {
                    "type": "USER",
                    "reference": f"{draft['work_ref']}@r{draft['work_rev']}",
                },
                "recorded_at": committed_at,
                "reason": "作者明确选择以当前工作稿作为章节正文",
            }
        ],
    }
    ledger = {
        "contract": "CHAPTER_REVISION_LEDGER",
        "version": "v1",
        "chapter_id": chapter_id,
        "current_revision_no": 1,
        "revisions": [
            {
                "revision_no": 1,
                "title": normalized_action["chapter_title"],
                "text_sha256": text_sha,
                "chars": len(text),
                "content_ref": {"kind": "C10_SOURCE_SPAN", **source_ref},
                "origin_material_ref": {
                    "material_unit_id": material_id,
                    "identity_revision_no": 1,
                },
                "change_kind": "INITIAL",
                "restores_revision_no": None,
                "committed_at": committed_at,
                "commit_operation_id": normalized_action["operation_id"],
                "actor": "AUTHOR",
            }
        ],
        "last_operation_id": normalized_action["operation_id"],
    }
    gate = c11_contract.validate_initial_commit(ledger, [
        *payloads[MATERIAL_KEY]["records"].values(),
        material,
    ])
    if gate != "C10_CONFIRMED_CHAPTER_ELIGIBLE":
        _fail(f"INITIAL_C11_GATE_FAILED:{gate}")
    revision_ref = {
        "chapter_id": chapter_id,
        "revision_no": 1,
        "revision_text_sha256": text_sha,
    }
    chapter = {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": chapter_id,
        "title": normalized_action["chapter_title"],
        "kind": "draft",
        "text": text,
        "added_at": added_at,
        "chapter_revision_ref": revision_ref,
    }
    try:
        store._validate_c1_v1_current_view(chapter)
    except (ValueError, TypeError, KeyError) as exc:
        raise ChapterInitialAdmissionError("INITIAL_C1_INVALID") from exc
    operation = {
        "operation_id": normalized_action["operation_id"],
        "request_sha256": request_sha,
        "stage": "AW_COMMITTED_PLANSTORE_PENDING",
        "work_ref": draft["work_ref"],
        "work_rev": draft["work_rev"],
        "slot_ref": draft["slot_ref"],
        "source_outline_ref": draft["source_outline_ref"],
        "chapter_title": normalized_action["chapter_title"],
        "chapter_id": chapter_id,
        "source_id": source_id,
        "material_unit_id": material_id,
        "revision_no": 1,
        "revision_text_sha256": text_sha,
        "committed_at": committed_at,
        "plan_handover": None,
    }

    payloads[SOURCE_KEY]["sources"][source_id] = source
    payloads[MATERIAL_KEY]["records"][material_id] = material
    payloads[LEDGER_KEY]["ledgers"][chapter_id] = ledger
    payloads[LEDGER_KEY]["next_chapter_number"] = next_number + 1
    payloads[CHAPTERS_KEY].append(chapter)
    payloads[INDEX_KEY].append(revision_ref)
    payloads[OPERATIONS_KEY]["operations"][normalized_action["operation_id"]] = operation
    payloads = _validated_payloads(payloads)

    handle.commit_guarded(
        normalized_action["operation_id"],
        payloads,
        before["watermarks"],
        {"draft": preflight["draft_workspace"]},
    )
    after = _read_bundle(handle)
    saved = after["payloads"][OPERATIONS_KEY]["operations"][
        normalized_action["operation_id"]
    ]
    return _result(after, saved, replayed=False)


def resolve_initial_admission(
    workspace: AuthorWorkspace,
    operation_id: str,
) -> dict[str, Any]:
    """跨重启读回一条已接收交棒；不把 pending 冒充 planstore 已完成。"""
    handle = _workspace(workspace)
    if not isinstance(operation_id, str) or OPERATION_ID_RE.fullmatch(operation_id) is None:
        _fail("OPERATION_ID_INVALID")
    first = _read_bundle(handle)
    operation = first["payloads"][OPERATIONS_KEY]["operations"].get(operation_id)
    if operation is None:
        _fail("CHAPTER_ADMISSION_OPERATION_NOT_FOUND")
    second = _read_bundle(handle)
    if first["raw"] != second["raw"]:
        _fail("CHAPTER_ADMISSION_STATE_CHANGED_DURING_READ")
    chapter_id = operation["chapter_id"]
    return {
        **_result(second, operation, replayed=True),
        "chapter": copy.deepcopy(
            next(
                row
                for row in second["payloads"][CHAPTERS_KEY]
                if row["id"] == chapter_id
            )
        ),
        "ledger": copy.deepcopy(
            second["payloads"][LEDGER_KEY]["ledgers"][chapter_id]
        ),
        "material": copy.deepcopy(
            second["payloads"][MATERIAL_KEY]["records"][
                operation["material_unit_id"]
            ]
        ),
    }


__all__ = [
    "ChapterInitialAdmissionError",
    "commit_initial_work_draft",
    "resolve_initial_admission",
]
