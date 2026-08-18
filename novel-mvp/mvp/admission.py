"""Pre-M3 本地准入门：C1 正文视图 → 可进入 M2/M3 的精确原文片段。

本模块不改 C1、不改章节边界、不抽事实、不调模型。它只隔离机械上
明确的作者／读者提示，并阻断 C1 已明确标为 outline 的材料；独立方括号
块身份不明时失败关闭，整章不下发。
"""

from __future__ import annotations

import hashlib
import re
from typing import Any


IDENTITY = "NOVEL_MVP_PRE_M3_ADMISSION_R01"
EXPLICIT_OUTLINE_STATUS = "NOT_M3_ELIGIBLE__EXPLICIT_OUTLINE"

_EXPLICIT_PREFIX = re.compile(
    r"^(?:作者(?:备注|说明|的话|有话说)|题外话|写在前面|写在后面|温馨提示|读者须知|备注)\s*[:：]"
)
_EXPLICIT_NOTE_CUES = (
    "作者备注",
    "作者说明",
    "作者有话说",
    "题外话",
    "写在前面",
    "写在后面",
    "温馨提示",
    "读者须知",
    "不喜勿进",
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _standalone_bracket_spans(text: str) -> list[tuple[int, int]]:
    """找独占结构块的【……】，块内允许换行。"""
    spans: list[tuple[int, int]] = []
    cursor = 0
    while cursor < len(text):
        start = text.find("【", cursor)
        if start < 0:
            break
        end_marker = text.find("】", start + 1)
        if end_marker < 0:
            break
        end = end_marker + 1
        line_start = text.rfind("\n", 0, start) + 1
        next_newline = text.find("\n", end)
        line_end = len(text) if next_newline < 0 else next_newline
        if not text[line_start:start].strip() and not text[end:line_end].strip():
            spans.append((start, end))
            cursor = end
        else:
            cursor = start + 1
    return spans


def _paragraph_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    if start >= end:
        return []
    value = text[start:end]
    boundaries = [0]
    boundaries.extend(match.end() for match in re.finditer(r"(?:\r?\n){2,}", value))
    boundaries.append(len(value))
    spans: list[tuple[int, int]] = []
    for left, right in zip(boundaries, boundaries[1:]):
        absolute_left = start + left
        absolute_right = start + right
        while absolute_left < absolute_right and text[absolute_left].isspace():
            absolute_left += 1
        while absolute_right > absolute_left and text[absolute_right - 1].isspace():
            absolute_right -= 1
        if absolute_left < absolute_right:
            spans.append((absolute_left, absolute_right))
    return spans


def _excluded_spans(text: str) -> list[dict[str, Any]]:
    bracket_spans = _standalone_bracket_spans(text)
    excluded: list[dict[str, Any]] = []
    for start, end in bracket_spans:
        value = text[start:end]
        explicit = any(cue in value for cue in _EXPLICIT_NOTE_CUES)
        excluded.append(
            {
                "start": start,
                "end": end,
                "role": "author_note" if explicit else "uncertain",
                "rule_id": (
                    "standalone_bracket_with_explicit_author_reader_cue"
                    if explicit
                    else "standalone_bracket_without_decisive_cue"
                ),
            }
        )

    cursor = 0
    for bracket_start, bracket_end in [*bracket_spans, (len(text), len(text))]:
        for start, end in _paragraph_spans(text, cursor, bracket_start):
            if _EXPLICIT_PREFIX.match(text[start:end].lstrip()):
                excluded.append(
                    {
                        "start": start,
                        "end": end,
                        "role": "author_note",
                        "rule_id": "paragraph_starts_with_explicit_author_note_prefix",
                    }
                )
        cursor = bracket_end
    return sorted(excluded, key=lambda item: (item["start"], item["end"]))


def _partition(text: str) -> list[dict[str, Any]]:
    """让 C1 text 每个字符恰好进入一个可回验片段。"""
    excluded = _excluded_spans(text)
    segments: list[dict[str, Any]] = []
    cursor = 0
    for item in [*excluded, {"start": len(text), "end": len(text)}]:
        start = item["start"]
        if start < cursor:
            raise RuntimeError("Pre-M3 准入片段发生重叠")
        if cursor < start:
            value = text[cursor:start]
            left_trim = len(value) - len(value.lstrip()) if cursor > 0 else 0
            right_trimmed = len(value.rstrip()) if start < len(text) else len(value)
            story_start = cursor + left_trim
            story_end = cursor + right_trimmed
            if story_start >= story_end:
                segments.append(
                    {"start": cursor, "end": start, "role": "separator", "rule_id": "whitespace"}
                )
                cursor = item["end"]
                if item["end"] > item["start"]:
                    segments.append(dict(item))
                continue
            if cursor < story_start:
                segments.append(
                    {"start": cursor, "end": story_start, "role": "separator", "rule_id": "whitespace"}
                )
            if story_start < story_end:
                segments.append(
                    {
                        "start": story_start,
                        "end": story_end,
                        "role": "story",
                        "rule_id": "not_excluded_by_pre_m3_admission",
                    }
                )
            if story_end < start:
                segments.append(
                    {"start": story_end, "end": start, "role": "separator", "rule_id": "whitespace"}
                )
        if item["end"] > item["start"]:
            segments.append(dict(item))
        cursor = item["end"]

    if not text:
        return []
    ordered = sorted(segments, key=lambda item: item["start"])
    if ordered[0]["start"] != 0 or ordered[-1]["end"] != len(text):
        raise RuntimeError("Pre-M3 准入片段没有覆盖完整 C1 text")
    for left, right in zip(ordered, ordered[1:]):
        if left["end"] != right["start"]:
            raise RuntimeError("Pre-M3 准入片段存在缺口或重叠")
    return ordered


def _public_segment(segment: dict[str, Any], chapter: dict, text: str) -> dict[str, Any]:
    start = segment["start"]
    end = segment["end"]
    value = text[start:end]
    return {
        "role": segment["role"],
        "send_to_m3": segment["role"] == "story",
        "rule_id": segment["rule_id"],
        "source_ref": {
            "chapter_id": chapter["id"],
            "coordinate_basis": "c1_text",
            "start": start,
            "end": end,
        },
        "text": value,
        "text_sha256": _sha256_text(value),
    }


def _explicit_outline_receipt(chapter: dict, text: str) -> dict[str, Any]:
    """C1 已有 outline 身份是唯一判据；不读取正文词句猜材料类型。"""
    coverage = []
    if text:
        coverage = [
            _public_segment(
                {
                    "start": 0,
                    "end": len(text),
                    "role": "outline",
                    "rule_id": "c1_kind_explicit_outline",
                },
                chapter,
                text,
            )
        ]
    return {
        "identity": IDENTITY,
        "contract_status": "INTERNAL_CONSUMER_VIEW_NO_C1_C2_CHANGE",
        "status": EXPLICIT_OUTLINE_STATUS,
        "source": {
            "chapter_id": chapter["id"],
            "coordinate_basis": "c1_text",
            "text_sha256": _sha256_text(text),
            "chars": len(text),
        },
        "coverage_segments": coverage,
        "candidate_story_segments": [],
        "m3_eligible_targets": [],
        "isolated_author_note_segments": [],
        "uncertain_segments": [],
        "excluded_outline_segments": coverage,
        "blocks": [
            {
                "type": "explicit_outline_not_m3_eligible",
                "detail": "C1 kind=outline，由显式材料身份确定，不进入 M3",
            }
        ],
        "api_calls": 0,
        "automatic_retries": 0,
    }


def apply_pre_m3_admission(chapter: dict) -> dict[str, Any]:
    """返回当前 C1 的 M3 消费资格视图；不修改传入章节。"""
    if not isinstance(chapter, dict) or not isinstance(chapter.get("text"), str):
        raise ValueError("Pre-M3 准入门需要含 text 的 C1 章节对象")
    if not chapter.get("id"):
        raise ValueError("Pre-M3 准入门需要 C1 chapter id")

    text = chapter["text"]
    if chapter.get("kind") == "outline":
        return _explicit_outline_receipt(chapter, text)

    coverage = [_public_segment(item, chapter, text) for item in _partition(text)]
    story = [item for item in coverage if item["role"] == "story"]
    author_notes = [item for item in coverage if item["role"] == "author_note"]
    uncertain = [item for item in coverage if item["role"] == "uncertain"]
    blocks: list[dict[str, str]] = []
    if uncertain:
        status = "NEED_CONFIRM"
        eligible: list[dict[str, Any]] = []
        blocks.append({"type": "uncertain_material_identity", "detail": "存在机械上无法确认身份的独立块"})
    elif not story:
        status = "NEED_CONFIRM"
        eligible = []
        blocks.append({"type": "no_admissible_story", "detail": "没有可证明为书稿的正文片段"})
    else:
        status = "READY"
        eligible = story

    return {
        "identity": IDENTITY,
        "contract_status": "INTERNAL_CONSUMER_VIEW_NO_C1_C2_CHANGE",
        "status": status,
        "source": {
            "chapter_id": chapter["id"],
            "coordinate_basis": "c1_text",
            "text_sha256": _sha256_text(text),
            "chars": len(text),
        },
        "coverage_segments": coverage,
        "candidate_story_segments": story,
        "m3_eligible_targets": eligible,
        "isolated_author_note_segments": author_notes,
        "uncertain_segments": uncertain,
        "excluded_outline_segments": [],
        "blocks": blocks,
        "api_calls": 0,
        "automatic_retries": 0,
    }
