"""C10 Intake 材料身份：显式 source-span 写入与 C1 投影门。

本模块不读内容猜身份。调用方必须给出 C10 允许的 role/state/authority，
正式 validator 验证通过后才存材料；只有当前 Confirmed Chapter 可投影到 C1。
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from contracts.validate_c10_intake_material_identity import (
    CONTRACT_ID,
    COORDINATE_BASIS,
    V2_VERSION,
    V3_VERSION,
    V4_VERSION,
    VERSION,
    c1_emission_eligible,
    validate_record,
)
from mvp import chapterize, store


SOURCE_STORAGE_VERSION = "INTAKE_PARENT_SOURCE_V1"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _recorded_at_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _stable_source_id(raw_bytes: bytes, encoding: str) -> str:
    digest = _sha256_bytes(raw_bytes + b"\x00" + encoding.encode("utf-8"))
    return f"SRC-{digest[:20].upper()}"


def _stable_unit_id(source_id: str, start: int, end: int) -> str:
    digest = _sha256_text(f"{source_id}:{start}:{end}")
    return f"MU-{digest[:20].upper()}"


def _decode_source(raw_bytes: bytes, encoding: str) -> str:
    if not isinstance(raw_bytes, bytes):
        raise ValueError("Explicit material intake 需要原始 bytes")
    if not isinstance(encoding, str) or not encoding:
        raise ValueError("Explicit material intake 需要明确 encoding")
    try:
        return raw_bytes.decode(encoding, errors="strict")
    except (LookupError, UnicodeDecodeError) as exc:
        raise ValueError(f"source 严格解码失败：{exc}") from exc


def _source_record(source_name: str, raw_bytes: bytes, encoding: str, decoded: str) -> dict:
    if not isinstance(source_name, str) or not source_name:
        raise ValueError("source_name 必须是非空字符串")
    source_id = _stable_source_id(raw_bytes, encoding)
    return {
        "storage_contract": SOURCE_STORAGE_VERSION,
        "source_id": source_id,
        "source_name": source_name,
        "source_sha256": _sha256_bytes(raw_bytes),
        "encoding": encoding,
        "normalization": "none",
        "original_bytes_base64": base64.b64encode(raw_bytes).decode("ascii"),
        "decoded_text": decoded,
    }


def _contract_version_for_declarations(declarations: list[dict[str, Any]]) -> str:
    """显式 Tags/Title/Setting 批次分别写 v4/v3/v2，其余入口继续写 v1。"""
    if any(
        isinstance(declaration, dict) and declaration.get("role") == "TAGS"
        for declaration in declarations
    ):
        return V4_VERSION
    if any(
        isinstance(declaration, dict) and declaration.get("role") == "TITLE"
        for declaration in declarations
    ):
        return V3_VERSION
    if any(
        isinstance(declaration, dict) and declaration.get("role") == "SETTING"
        for declaration in declarations
    ):
        return V2_VERSION
    return VERSION


def _build_record(
    source: dict,
    decoded: str,
    declaration: dict[str, Any],
    contract_version: str,
) -> dict:
    required = {"start", "end", "role", "state", "basis", "actor", "reason"}
    allowed = required | {"recorded_at"}
    missing = required - set(declaration)
    extra = set(declaration) - allowed
    if missing or extra:
        raise ValueError(
            f"material declaration 字段不符：missing={sorted(missing)} extra={sorted(extra)}"
        )
    start = declaration["start"]
    end = declaration["end"]
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(decoded):
        raise ValueError(f"material span 越界或为空：[{start}, {end}) / {len(decoded)}")
    record = {
        "contract": CONTRACT_ID,
        "version": contract_version,
        "material_unit_id": _stable_unit_id(source["source_id"], start, end),
        "source_ref": {
            "source_id": source["source_id"],
            "source_sha256": source["source_sha256"],
            "coordinate_basis": COORDINATE_BASIS,
            "start": start,
            "end": end,
            "slice_sha256": _sha256_text(decoded[start:end]),
        },
        "identity_revisions": [
            {
                "revision_no": 1,
                "role": declaration["role"],
                "state": declaration["state"],
                "basis": declaration["basis"],
                "actor": declaration["actor"],
                "recorded_at": declaration.get("recorded_at") or _recorded_at_now(),
                "reason": declaration["reason"],
            }
        ],
    }
    return validate_record(record, f"product.{record['material_unit_id']}")


def _validate_exact_coverage(records: list[dict], decoded: str) -> None:
    spans = sorted(
        (record["source_ref"]["start"], record["source_ref"]["end"])
        for record in records
    )
    if not spans:
        raise ValueError("Explicit material intake 至少需要一个 material span")
    cursor = 0
    for start, end in spans:
        if start != cursor:
            relation = "重叠" if start < cursor else "缺口"
            raise ValueError(f"material spans 存在{relation}：cursor={cursor}, next_start={start}")
        cursor = end
    if cursor != len(decoded):
        raise ValueError(f"material spans 未覆盖 source 尾部：{cursor} != {len(decoded)}")


def _chapterization_format_hint(source_name: str) -> str:
    if source_name.endswith("#word/document.xml"):
        return "docx"
    if Path(source_name).suffix.lower() == ".md":
        return "md"
    return "text"


def _prepare_c1_projection(
    records: list[dict], decoded: str, default_title: str, source_name: str
) -> tuple[list[dict], list[dict], list[str]]:
    pending: list[dict] = []
    receipts: list[dict] = []
    warnings: list[str] = []
    for record in records:
        if not c1_emission_eligible(record):
            continue
        ref = record["source_ref"]
        material_text = decoded[ref["start"] : ref["end"]]
        if _sha256_text(material_text) != ref["slice_sha256"]:
            raise ValueError("C10 exact slice 在 C1 投影前复验失败")
        result = chapterize.chapterize_text(
            material_text,
            default_title=default_title,
            format_hint=_chapterization_format_hint(source_name),
        )
        if result["status"] == "BLOCKED":
            raise chapterize.ChapterizationBlocked(result)
        first_index = len(pending)
        for candidate in result["candidates"]:
            pending.append(
                {
                    "title": candidate["title"],
                    "text": candidate["text"],
                    "kind": "draft",
                }
            )
        receipts.append(
            {
                "material_unit_id": record["material_unit_id"],
                "identity_revision_no": record["identity_revisions"][-1]["revision_no"],
                "pending_c1_start": first_index,
                "pending_c1_end": len(pending),
                "chapterization": result,
            }
        )
        warnings.extend(result["warnings"])
    return pending, receipts, warnings


def _decode_stored_source(source: dict[str, Any]) -> str:
    required = {
        "storage_contract",
        "source_id",
        "source_name",
        "source_sha256",
        "encoding",
        "normalization",
        "original_bytes_base64",
        "decoded_text",
    }
    if set(source) != required or source["storage_contract"] != SOURCE_STORAGE_VERSION:
        raise ValueError("不支持的 Intake parent source 形状")
    if source["normalization"] != "none":
        raise ValueError("Intake parent source 禁止 normalization")
    try:
        raw = base64.b64decode(source["original_bytes_base64"], validate=True)
    except ValueError as exc:
        raise ValueError(f"Intake parent source base64 损坏：{exc}") from exc
    if _sha256_bytes(raw) != source["source_sha256"]:
        raise ValueError("Intake parent source raw SHA 复验失败")
    decoded = _decode_source(raw, source["encoding"])
    if decoded != source["decoded_text"]:
        raise ValueError("Intake parent source 精确解码文本复验失败")
    return decoded


def _persist_projection(
    project: str,
    pending: list[dict],
    projection_receipts: list[dict],
) -> list[dict]:
    chapters = store.add_chapters(project, pending) if pending else []
    persisted: list[dict] = []
    for receipt in projection_receipts:
        start = receipt.pop("pending_c1_start")
        end = receipt.pop("pending_c1_end")
        persisted.append(
            {
                "material_unit_id": receipt["material_unit_id"],
                "identity_revision_no": receipt["identity_revision_no"],
                "chapter_ids": [item["id"] for item in chapters[start:end]],
            }
        )
    store.add_intake_c1_projections(project, persisted)
    return chapters


def _prepare_explicit_material(
    *,
    source_name: str,
    raw_bytes: bytes,
    encoding: str,
    declarations: list[dict[str, Any]],
    default_title: str | None = None,
    chapter_no_hint: int | None = None,
) -> dict[str, Any]:
    decoded = _decode_source(raw_bytes, encoding)
    source = _source_record(source_name, raw_bytes, encoding, decoded)
    if not isinstance(declarations, list):
        raise ValueError("declarations 必须是数组")
    contract_version = _contract_version_for_declarations(declarations)
    records = [
        _build_record(source, decoded, item, contract_version)
        for item in declarations
    ]
    _validate_exact_coverage(records, decoded)
    pending, projection_receipts, warnings = _prepare_c1_projection(
        records,
        decoded,
        default_title or source_name,
        source_name,
    )
    return {
        "source": source,
        "records": records,
        "pending": pending,
        "projection_receipts": projection_receipts,
        "warnings": warnings,
        "chapter_no_hint": chapter_no_hint,
    }


def _validate_batch_chapter_sequence(prepared: list[dict[str, Any]]) -> None:
    numbers: list[int | None] = []
    for item in prepared:
        hint = item["chapter_no_hint"]
        for receipt in item["projection_receipts"]:
            candidates = receipt["chapterization"]["candidates"]
            if len(candidates) == 1:
                content_number = candidates[0].get("chapter_no")
                if (
                    type(hint) is int
                    and type(content_number) is int
                    and hint != content_number
                ):
                    source_name = item["source"]["source_name"]
                    raise ValueError(
                        "文件名章号与正文标题章号冲突，禁止猜真值："
                        f"{source_name} 文件名={hint} 正文={content_number}"
                    )
            for candidate in candidates:
                number = candidate.get("chapter_no")
                if number is None and len(candidates) == 1:
                    number = hint
                numbers.append(number)
    if len(numbers) <= 1 or not any(number is not None for number in numbers):
        return
    if not all(type(number) is int for number in numbers):
        raise ValueError(f"跨文件章序部分缺号，禁止宣称完整成功：{numbers}")
    for previous, current in zip(numbers, numbers[1:]):
        if current != previous + 1:
            raise ValueError(f"跨文件章序必须连续递增，实际为：{numbers}")


def ingest_explicit_material_batch(
    project: str,
    items: list[dict[str, Any]],
    *,
    enforce_global_chapter_sequence: bool = False,
) -> dict[str, Any]:
    """整批先完成解码、C10、切章和碰撞预检，再统一落盘。"""
    if not isinstance(items, list) or not items:
        raise ValueError("Explicit material batch 至少需要一个 source")
    required = {"source_name", "raw_bytes", "encoding", "declarations"}
    allowed = required | {"default_title", "chapter_no_hint"}
    prepared: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"batch[{index}] 必须是对象")
        missing = required - set(item)
        extra = set(item) - allowed
        if missing or extra:
            raise ValueError(
                f"batch[{index}] 字段不符：missing={sorted(missing)} extra={sorted(extra)}"
            )
        prepared.append(_prepare_explicit_material(**item))

    source_ids = [item["source"]["source_id"] for item in prepared]
    unit_ids = [
        record["material_unit_id"]
        for item in prepared
        for record in item["records"]
    ]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("同批 C10 source_id 重复；相同内容的多个输入必须先人工确认")
    if len(unit_ids) != len(set(unit_ids)):
        raise ValueError("同批 C10 material_unit_id 重复")
    existing_sources = {
        item.get("source_id") for item in store.intake_sources(project) if isinstance(item, dict)
    }
    existing_units = {
        item.get("material_unit_id")
        for item in store.intake_material_units(project)
        if isinstance(item, dict)
    }
    if collisions := sorted(set(source_ids) & existing_sources):
        raise ValueError(f"C10 source_id 已存在：{collisions}")
    if collisions := sorted(set(unit_ids) & existing_units):
        raise ValueError(f"C10 material_unit_id 已存在：{collisions}")
    if enforce_global_chapter_sequence:
        _validate_batch_chapter_sequence(prepared)

    pending: list[dict] = []
    receipts: list[dict] = []
    warnings: list[str] = []
    for item in prepared:
        offset = len(pending)
        pending.extend(item["pending"])
        for original in item["projection_receipts"]:
            receipt = dict(original)
            receipt["pending_c1_start"] += offset
            receipt["pending_c1_end"] += offset
            receipts.append(receipt)
        warnings.extend(item["warnings"])

    for item in prepared:
        store.add_intake_source(project, item["source"])
    records = [record for item in prepared for record in item["records"]]
    store.add_intake_material_units(project, records)
    chapters = _persist_projection(project, pending, receipts)
    current_keys = {
        (record["material_unit_id"], record["identity_revisions"][-1]["revision_no"])
        for record in records
        if c1_emission_eligible(record)
    }
    projection_receipts = [
        item
        for item in store.intake_c1_projections(project)
        if (item["material_unit_id"], item["identity_revision_no"]) in current_keys
    ]
    return {
        "sources": [item["source"] for item in prepared],
        "material_units": records,
        "chapters": chapters,
        "projection_receipts": projection_receipts,
        "warnings": warnings,
        "api_calls": 0,
        "automatic_retries": 0,
    }


def ingest_explicit_materials(
    project: str,
    *,
    source_name: str,
    raw_bytes: bytes,
    encoding: str,
    declarations: list[dict[str, Any]],
) -> dict[str, Any]:
    """保存显式 C10 units，并只把 Confirmed Chapter 批量投影成 C1。

    declarations 必须覆盖整个精确解码 source。不能确认的区间要显式传 Unknown，
    不能靠省略区间或把剩余文本默认成 Chapter。
    """
    batch = ingest_explicit_material_batch(
        project,
        [
            {
                "source_name": source_name,
                "raw_bytes": raw_bytes,
                "encoding": encoding,
                "declarations": declarations,
            }
        ],
    )
    return {
        "source": batch["sources"][0],
        "material_units": batch["material_units"],
        "chapters": batch["chapters"],
        "projection_receipts": batch["projection_receipts"],
        "warnings": batch["warnings"],
        "api_calls": 0,
        "automatic_retries": 0,
    }


def project_material_units_to_c1(
    project: str, material_unit_ids: list[str]
) -> dict[str, Any]:
    """按已存 C10 的当前 revision 投影；同一 revision 重复调用不会再写 C1。"""
    wanted = set(material_unit_ids)
    if not wanted or len(wanted) != len(material_unit_ids):
        raise ValueError("material_unit_ids 必须非空且不重复")
    records = [
        record
        for record in store.intake_material_units(project)
        if record.get("material_unit_id") in wanted
    ]
    if {record["material_unit_id"] for record in records} != wanted:
        raise ValueError("存在找不到的 C10 material unit")
    existing = {
        (item["material_unit_id"], item["identity_revision_no"])
        for item in store.intake_c1_projections(project)
    }
    eligible = []
    for record in records:
        validate_record(record, f"product.{record['material_unit_id']}")
        key = (record["material_unit_id"], record["identity_revisions"][-1]["revision_no"])
        if c1_emission_eligible(record) and key not in existing:
            eligible.append(record)

    sources = {item["source_id"]: item for item in store.intake_sources(project)}
    pending: list[dict] = []
    receipts: list[dict] = []
    warnings: list[str] = []
    for record in eligible:
        ref = record["source_ref"]
        source = sources.get(ref["source_id"])
        if source is None:
            raise ValueError(f"C10 parent source 不存在：{ref['source_id']}")
        decoded = _decode_stored_source(source)
        if source["source_sha256"] != ref["source_sha256"]:
            raise ValueError("C10 record 与 parent source SHA 不一致")
        unit_pending, unit_receipts, unit_warnings = _prepare_c1_projection(
            [record], decoded, source["source_name"], source["source_name"]
        )
        offset = len(pending)
        for receipt in unit_receipts:
            receipt["pending_c1_start"] += offset
            receipt["pending_c1_end"] += offset
        pending.extend(unit_pending)
        receipts.extend(unit_receipts)
        warnings.extend(unit_warnings)
    chapters = _persist_projection(project, pending, receipts)
    return {
        "chapters": chapters,
        "projection_receipts": [
            item
            for item in store.intake_c1_projections(project)
            if item["material_unit_id"] in wanted
        ],
        "warnings": warnings,
        "api_calls": 0,
        "automatic_retries": 0,
    }


def append_identity_revision(
    project: str,
    material_unit_id: str,
    *,
    role: str | None,
    state: str,
    basis: dict[str, Any],
    actor: dict[str, Any],
    reason: str | None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """给既有稳定 span 追加一条 C10 revision，不覆盖历史。"""
    matches = [
        record
        for record in store.intake_material_units(project)
        if record.get("material_unit_id") == material_unit_id
    ]
    if len(matches) != 1:
        raise ValueError(f"C10 material unit 必须唯一存在：{material_unit_id}")
    current = matches[0]
    revisions = [*current["identity_revisions"]]
    revisions.append(
        {
            "revision_no": len(revisions) + 1,
            "role": role,
            "state": state,
            "basis": basis,
            "actor": actor,
            "recorded_at": recorded_at or _recorded_at_now(),
            "reason": reason,
        }
    )
    revised = {**current, "identity_revisions": revisions}
    validate_record(revised, f"product.{material_unit_id}")
    return store.append_intake_identity_revision(project, revised)


def current_c1_eligibility(record: dict[str, Any]) -> bool:
    """从正式 C10 当前 revision 派生资格；不另存独立布尔真值。"""
    validate_record(record, f"product.{record.get('material_unit_id', 'unknown')}")
    return c1_emission_eligible(record)
