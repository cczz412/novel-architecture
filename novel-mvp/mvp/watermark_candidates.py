"""M1 保守水印候选检测。

只在多章的开头／结尾找重复短行，输出可回验坐标。它不删文、
不改 C1、不阻断导入，也不会把候选写成“已确认水印”。
"""

from __future__ import annotations

import hashlib
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
    "text",
    "text_sha256",
}
BOUNDARY_LINE_COUNT = 3
MIN_CANDIDATE_CHARS = 2
MAX_CANDIDATE_CHARS = 120
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


def _validated_chapter(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != CHAPTER_KEYS:
        raise WatermarkCandidateError("WATERMARK_CHAPTER_SHAPE_INVALID")
    text = value["text"]
    source_body_start = value["source_body_start"]
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
        if content.strip():
            rows.append(
                {
                    "chapter_start": cursor,
                    "chapter_end": end,
                    "source_start": chapter["source_body_start"] + cursor,
                    "source_end": chapter["source_body_start"] + end,
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
                    "source_start": chapter["source_body_start"] + cursor,
                    "source_end": chapter["source_body_start"] + len(chapter["text"]),
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
                "source_start": row["source_start"],
                "source_end": row["source_end"],
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
        "candidate_count": len(candidates),
        "candidates": candidates,
        "api_calls": 0,
        "model_calls": 0,
        "automatic_retries": 0,
    }
