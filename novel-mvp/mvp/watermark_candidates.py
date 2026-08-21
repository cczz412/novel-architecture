"""M1 保守水印候选检测。

只在多章的开头／结尾找重复短行，输出可回验坐标。它不删文、
不改 C1、不阻断导入，也不会把候选写成“已确认水印”。
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
from typing import Any


IDENTITY = "M1_CONSERVATIVE_WATERMARK_CANDIDATES_R01"
CHAPTER_KEYS = {
    "chapter_key",
    "source_id",
    "source_name",
    "source_sha256",
    "material_unit_id",
    "identity_revision_no",
    "chapter_index",
    "source_body_start",
    "source_body_end",
    "text",
    "text_sha256",
}
BOUNDARY_LINE_COUNT = 3
MIN_CANDIDATE_CHARS = 2
MAX_CANDIDATE_CHARS = 120
ACTION_KEYS = {
    "contract",
    "version",
    "operation_id",
    "actor",
    "intent",
    "source_receipt_sha256",
    "candidate_ids",
}
SOURCE_KEYS = {
    "storage_contract",
    "source_id",
    "source_name",
    "source_sha256",
    "encoding",
    "normalization",
    "original_bytes_base64",
    "decoded_text",
}
OPERATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_CUE_RE = re.compile(
    r"(?:"
    r"本章完|未完待续|"
    r"求(?:收藏|推荐|月票|投票|礼物|追读)|"
    r"(?:请|记得).{0,8}(?:收藏|关注|投票|追读)|"
    r"最新网址|手机用户请|请记住本站|"
    r"感谢.{0,8}(?:支持|阅读)"
    r")"
)


class WatermarkCandidateError(ValueError):
    """水印候选输入不能机械回验。"""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_sha256(value: Any) -> str:
    try:
        payload = (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise WatermarkCandidateError("WATERMARK_VALUE_NOT_JSON") from exc
    return hashlib.sha256(payload).hexdigest()


def _validated_chapter(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != CHAPTER_KEYS:
        raise WatermarkCandidateError("WATERMARK_CHAPTER_SHAPE_INVALID")
    text = value["text"]
    source_body_start = value["source_body_start"]
    source_body_end = value["source_body_end"]
    revision_no = value["identity_revision_no"]
    chapter_index = value["chapter_index"]
    text_fields = (
        "chapter_key",
        "source_id",
        "source_name",
        "source_sha256",
        "material_unit_id",
        "text_sha256",
    )
    if any(not isinstance(value[key], str) or not value[key] for key in text_fields):
        raise WatermarkCandidateError("WATERMARK_CHAPTER_IDENTITY_INVALID")
    if (
        not isinstance(text, str)
        or isinstance(source_body_start, bool)
        or not isinstance(source_body_start, int)
        or source_body_start < 0
        or isinstance(source_body_end, bool)
        or not isinstance(source_body_end, int)
        or source_body_end < source_body_start
        or source_body_end - source_body_start != len(text)
        or isinstance(revision_no, bool)
        or not isinstance(revision_no, int)
        or revision_no < 1
        or isinstance(chapter_index, bool)
        or not isinstance(chapter_index, int)
        or chapter_index < 1
        or value["text_sha256"] != _sha256_text(text)
        or not re.fullmatch(r"[0-9a-f]{64}", value["source_sha256"])
    ):
        raise WatermarkCandidateError("WATERMARK_CHAPTER_INTEGRITY_INVALID")
    return dict(value)


def _line_rows(chapter: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = 0
    for raw in chapter["text"].splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        end = cursor + len(content)
        line_end = cursor + len(raw)
        if content.strip():
            rows.append(
                {
                    "chapter_start": cursor,
                    "chapter_end": end,
                    "chapter_line_end": line_end,
                    "source_start": chapter["source_body_start"] + cursor,
                    "source_end": chapter["source_body_start"] + end,
                    "source_line_end": chapter["source_body_start"] + line_end,
                    "raw_text": content,
                    "normalized_text": content.strip(),
                }
            )
        cursor += len(raw)
    if cursor < len(chapter["text"]):
        content = chapter["text"][cursor:]
        if content.strip():
            rows.append(
                {
                    "chapter_start": cursor,
                    "chapter_end": len(chapter["text"]),
                    "chapter_line_end": len(chapter["text"]),
                    "source_start": chapter["source_body_start"] + cursor,
                    "source_end": chapter["source_body_start"] + len(chapter["text"]),
                    "source_line_end": chapter["source_body_start"] + len(chapter["text"]),
                    "raw_text": content,
                    "normalized_text": content.strip(),
                }
            )
    for index, row in enumerate(rows):
        in_prefix = index < BOUNDARY_LINE_COUNT
        in_suffix = len(rows) - index <= BOUNDARY_LINE_COUNT
        if in_prefix and in_suffix:
            row["boundary_position"] = "both"
        elif in_prefix:
            row["boundary_position"] = "prefix"
        elif in_suffix:
            row["boundary_position"] = "suffix"
        else:
            row["boundary_position"] = "middle"
        row["is_boundary"] = in_prefix or in_suffix
    return rows


def inspect(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    """返回只标不剥的候选小票；输入和章节文本字节不变。"""
    if not isinstance(chapters, list):
        raise WatermarkCandidateError("WATERMARK_CHAPTERS_NOT_LIST")
    normalized = [_validated_chapter(chapter) for chapter in chapters]
    chapter_keys = [chapter["chapter_key"] for chapter in normalized]
    if len(chapter_keys) != len(set(chapter_keys)):
        raise WatermarkCandidateError("WATERMARK_CHAPTER_KEY_DUPLICATE")

    grouped: dict[str, list[dict[str, Any]]] = {}
    order: dict[str, tuple[int, int]] = {}
    for chapter_position, chapter in enumerate(normalized):
        for line_position, row in enumerate(_line_rows(chapter)):
            text = row["normalized_text"]
            if (
                not row["is_boundary"]
                or len(text) < MIN_CANDIDATE_CHARS
                or len(text) > MAX_CANDIDATE_CHARS
            ):
                continue
            occurrence = {
                "chapter_key": chapter["chapter_key"],
                "source_id": chapter["source_id"],
                "source_name": chapter["source_name"],
                "source_sha256": chapter["source_sha256"],
                "material_unit_id": chapter["material_unit_id"],
                "identity_revision_no": chapter["identity_revision_no"],
                "chapter_index": chapter["chapter_index"],
                "coordinate_basis": "DECODED_UNICODE_CODEPOINT_V1",
                "boundary_position": row["boundary_position"],
                "chapter_start": row["chapter_start"],
                "chapter_end": row["chapter_end"],
                "chapter_line_end": row["chapter_line_end"],
                "source_start": row["source_start"],
                "source_end": row["source_end"],
                "source_line_end": row["source_line_end"],
                "raw_text": row["raw_text"],
            }
            grouped.setdefault(text, []).append(occurrence)
            order.setdefault(text, (chapter_position, line_position))

    candidates: list[dict[str, Any]] = []
    for text in sorted(grouped, key=lambda value: order[value]):
        occurrences = grouped[text]
        distinct_chapters = {row["chapter_key"] for row in occurrences}
        if len(distinct_chapters) < 2:
            continue
        digest = _sha256_text(text)
        candidates.append(
            {
                "candidate_id": f"wm-{digest[:16]}",
                "normalized_text": text,
                "normalized_text_sha256": digest,
                "signals": {
                    "exact_after_outer_whitespace_trim": True,
                    "repeated_across_chapters": True,
                    "boundary_line": True,
                    "non_narrative_cue": _CUE_RE.search(text) is not None,
                },
                "chapter_count": len(distinct_chapters),
                "occurrence_count": len(occurrences),
                "occurrences": occurrences,
                "status": "CANDIDATE_ONLY",
                "action": "kept_flagged",
                "author_decision": "not_requested",
            }
        )

    return {
        "identity": IDENTITY,
        "policy": {
            "candidate_equivalence": "TRIM_OUTER_WHITESPACE_THEN_EXACT",
            "mechanically_confirmed": False,
            "blocks_import": False,
            "mutates_original_text": False,
            "default_action": "kept_flagged",
            "derived_clean_copy_requires_author_confirmation": True,
        },
        "source_chapter_count": len(normalized),
        "chapter_refs": [
            {
                key: chapter[key]
                for key in (
                    "chapter_key",
                    "source_id",
                    "source_name",
                    "source_sha256",
                    "material_unit_id",
                    "identity_revision_no",
                    "chapter_index",
                    "source_body_start",
                    "source_body_end",
                    "text_sha256",
                )
            }
            for chapter in normalized
        ],
        "candidate_count": len(candidates),
        "candidates": candidates,
        "api_calls": 0,
        "model_calls": 0,
        "automatic_retries": 0,
    }


def _validated_action(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != ACTION_KEYS:
        raise WatermarkCandidateError("WATERMARK_CLEAN_ACTION_SHAPE_INVALID")
    operation_id = value["operation_id"]
    source_sha = value["source_receipt_sha256"]
    candidate_ids = value["candidate_ids"]
    if (
        value["contract"] != "M1_WATERMARK_DERIVED_CLEAN_ACTION"
        or value["version"] != "v1"
        or value["actor"] != "author"
        or value["intent"] != "create_derived_clean_copy"
        or not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
        or not isinstance(source_sha, str)
        or re.fullmatch(r"[0-9a-f]{64}", source_sha) is None
        or not isinstance(candidate_ids, list)
        or not candidate_ids
        or any(not isinstance(item, str) or not item for item in candidate_ids)
        or len(candidate_ids) != len(set(candidate_ids))
    ):
        raise WatermarkCandidateError("WATERMARK_CLEAN_ACTION_INVALID")
    return {
        **copy.deepcopy(value),
        "candidate_ids": sorted(candidate_ids),
    }


def _chapters_from_sources(
    sources: list[dict[str, Any]], source_receipt: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if not isinstance(sources, list) or not isinstance(source_receipt, dict):
        raise WatermarkCandidateError("WATERMARK_CLEAN_SOURCE_INPUT_INVALID")
    source_map: dict[str, dict[str, Any]] = {}
    for source in sources:
        if not isinstance(source, dict) or set(source) != SOURCE_KEYS:
            raise WatermarkCandidateError("WATERMARK_CLEAN_SOURCE_INVALID")
        source_id = source.get("source_id")
        source_name = source.get("source_name")
        source_sha = source.get("source_sha256")
        decoded_text = source.get("decoded_text")
        if (
            not isinstance(source_id, str)
            or not source_id
            or source_id in source_map
            or not isinstance(source_name, str)
            or not source_name
            or not isinstance(source_sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", source_sha) is None
            or not isinstance(decoded_text, str)
            or source.get("storage_contract") != "INTAKE_PARENT_SOURCE_V1"
            or source.get("normalization") != "none"
            or not isinstance(source.get("encoding"), str)
            or not source["encoding"]
            or not isinstance(source.get("original_bytes_base64"), str)
        ):
            raise WatermarkCandidateError("WATERMARK_CLEAN_SOURCE_INVALID")
        try:
            raw = base64.b64decode(source["original_bytes_base64"], validate=True)
            decoded = raw.decode(source["encoding"], errors="strict")
        except (ValueError, LookupError, UnicodeDecodeError) as exc:
            raise WatermarkCandidateError("WATERMARK_CLEAN_SOURCE_INVALID") from exc
        if hashlib.sha256(raw).hexdigest() != source_sha or decoded != decoded_text:
            raise WatermarkCandidateError("WATERMARK_CLEAN_SOURCE_INTEGRITY_INVALID")
        source_map[source_id] = copy.deepcopy(source)
    refs = source_receipt.get("chapter_refs")
    if not isinstance(refs, list):
        raise WatermarkCandidateError("WATERMARK_CHAPTER_REFS_INVALID")
    chapters: list[dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            raise WatermarkCandidateError("WATERMARK_CHAPTER_REF_INVALID")
        source = source_map.get(ref.get("source_id"))
        start = ref.get("source_body_start")
        end = ref.get("source_body_end")
        if (
            source is None
            or ref.get("source_name") != source["source_name"]
            or ref.get("source_sha256") != source["source_sha256"]
            or isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or not 0 <= start <= end <= len(source["decoded_text"])
        ):
            raise WatermarkCandidateError("WATERMARK_CHAPTER_REF_SOURCE_MISMATCH")
        text = source["decoded_text"][start:end]
        chapters.append(
            _validated_chapter(
                {
                    **copy.deepcopy(ref),
                    "text": text,
                }
            )
        )
    return chapters, source_map


def receipt_sha256(
    sources: list[dict[str, Any]], source_receipt: dict[str, Any]
) -> str:
    """给作者动作生成可回验的候选快照 SHA。"""
    chapters, _ = _chapters_from_sources(sources, source_receipt)
    rebuilt_receipt = inspect(chapters)
    if source_receipt != rebuilt_receipt:
        raise WatermarkCandidateError("WATERMARK_SOURCE_RECEIPT_MISMATCH")
    return _canonical_sha256(rebuilt_receipt)


def derive_clean_copy(
    sources: list[dict[str, Any]],
    source_receipt: dict[str, Any],
    action: dict[str, Any],
) -> dict[str, Any]:
    """只按作者明确选中的候选组生成派生文本；不做任何写入。"""
    normalized_chapters, source_map = _chapters_from_sources(
        sources, source_receipt
    )
    rebuilt_receipt = inspect(normalized_chapters)
    if source_receipt != rebuilt_receipt:
        raise WatermarkCandidateError("WATERMARK_SOURCE_RECEIPT_MISMATCH")
    normalized_action = _validated_action(action)
    receipt_sha = _canonical_sha256(rebuilt_receipt)
    if normalized_action["source_receipt_sha256"] != receipt_sha:
        raise WatermarkCandidateError("WATERMARK_SOURCE_RECEIPT_SHA_MISMATCH")
    candidates = {
        candidate["candidate_id"]: candidate
        for candidate in rebuilt_receipt["candidates"]
    }
    unknown = sorted(set(normalized_action["candidate_ids"]) - set(candidates))
    if unknown:
        raise WatermarkCandidateError(
            f"WATERMARK_CLEAN_UNKNOWN_CANDIDATE:{','.join(unknown)}"
        )

    removals_by_source: dict[str, list[dict[str, Any]]] = {}
    for candidate_id in normalized_action["candidate_ids"]:
        for occurrence in candidates[candidate_id]["occurrences"]:
            removals_by_source.setdefault(occurrence["source_id"], []).append(
                {
                    "candidate_id": candidate_id,
                    "chapter_key": occurrence["chapter_key"],
                    "raw_text": occurrence["raw_text"],
                    "source_start": occurrence["source_start"],
                    "source_end": occurrence["source_line_end"],
                    "coordinate_basis": occurrence["coordinate_basis"],
                }
            )

    derived: list[dict[str, Any]] = []
    for source in sources:
        source_id = source["source_id"]
        source = source_map[source_id]
        original = source["decoded_text"]
        removals = sorted(
            removals_by_source.get(source_id, []),
            key=lambda row: (row["source_start"], row["source_end"]),
        )
        for left, right in zip(removals, removals[1:]):
            if left["source_end"] > right["source_start"]:
                raise WatermarkCandidateError("WATERMARK_CLEAN_SPAN_OVERLAP")
        text = original
        for removal in reversed(removals):
            start = removal["source_start"]
            end = removal["source_end"]
            if not 0 <= start <= end <= len(text):
                raise WatermarkCandidateError("WATERMARK_CLEAN_SPAN_INVALID")
            if text[start:end].rstrip("\r\n") != removal["raw_text"]:
                raise WatermarkCandidateError("WATERMARK_CLEAN_SOURCE_TEXT_MISMATCH")
            text = text[:start] + text[end:]
        derived.append(
            {
                "source_id": source_id,
                "source_name": source["source_name"],
                "original_source_sha256": source["source_sha256"],
                "original_decoded_text_sha256": _sha256_text(original),
                "derived_decoded_text": text,
                "derived_decoded_text_sha256": _sha256_text(text),
                "removed_occurrences": removals,
            }
        )

    return {
        "identity": "M1_WATERMARK_DERIVED_CLEAN_COPY_R01",
        "status": "DERIVED_CLEAN_COPY_READY",
        "operation_id": normalized_action["operation_id"],
        "source_receipt_sha256": receipt_sha,
        "selected_candidate_ids": normalized_action["candidate_ids"],
        "derived_sources": derived,
        "effects": {
            "original_upload_write": 0,
            "c10_write": 0,
            "c1_write": 0,
            "workspace_write": 0,
        },
        "api_calls": 0,
        "model_calls": 0,
        "automatic_retries": 0,
    }
