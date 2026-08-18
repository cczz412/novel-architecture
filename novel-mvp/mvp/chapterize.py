"""安全机械切章：单份原文 → 可回验章节候选。

只接受独占一行的明确“第 X 章”或“Chapter X”标题。任何章号矛盾、
标题内嵌第二个章节标记或非空前置材料都会失败关闭，不产生可落盘候选。
"""

from __future__ import annotations

import hashlib
import re
from typing import Any


IDENTITY = "NOVEL_MVP_SAFE_CHAPTERIZATION_R01"

_CHINESE_HEADING = re.compile(
    r"^第(?P<number>[零〇一二三四五六七八九十百千万两0-9]+)章"
    r"(?:(?:[ \t]+|[:：][ \t]*)(?P<title>.+))?$"
)
_CHINESE_SECTION_HEADING = re.compile(
    r"^第(?P<number>[零〇一二三四五六七八九十百千万两0-9]+)节"
    r"(?:(?:[ \t]+|[:：][ \t]*)(?P<title>.+))?$"
)
_ENGLISH_HEADING = re.compile(
    r"^Chapter[ \t]*(?P<number>[0-9]+)"
    r"(?:(?:[ \t]+|[:：][ \t]*)(?P<title>.+))?$",
    re.IGNORECASE,
)
_NESTED_CHAPTER_MARKER = re.compile(
    r"^(?:第[零〇一二三四五六七八九十百千万两0-9]+[章节]|Chapter[ \t]*[0-9]+)",
    re.IGNORECASE,
)
_MARKDOWN_HEADING = re.compile(r"^#{1,6}[ \t]+(?P<value>.+)$")
_MARKDOWN_FENCE = re.compile(r"^[ \t]*(?:```|~~~)")
_COMPACT_CHINESE_HEADING = re.compile(
    r"^第(?P<number>[零〇一二三四五六七八九十百千万两0-9]+)章(?P<title>[^\r\n]+)$"
)
_AMBIGUOUS_COMPACT_SECTION_LINE = re.compile(
    r"^第[零〇一二三四五六七八九十百千万两0-9]+节(?P<suffix>[^\r\n]+)$"
)
_HEADING_SEPARATORS = frozenset(":：-—_·")
_SENTENCE_ENDINGS = frozenset("。！？!?")
_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
           "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_SMALL_UNITS = {"十": 10, "百": 100, "千": 1000}


class ChapterizationBlocked(SystemExit):
    """切章结果不完整或自相矛盾；调用方必须在写 C1 前停止。"""

    def __init__(self, receipt: dict[str, Any]):
        self.receipt = receipt
        detail = receipt["blocks"][0]["detail"] if receipt["blocks"] else "未知切章错误"
        super().__init__(f"切章强停：{detail}")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _chapter_number(value: str) -> int:
    if value.isascii() and value.isdigit():
        return int(value)
    total = 0
    section = 0
    digit = 0
    for char in value:
        if char in _DIGITS:
            digit = _DIGITS[char]
        elif char in _SMALL_UNITS:
            section += (digit or 1) * _SMALL_UNITS[char]
            digit = 0
        elif char == "万":
            total += (section + digit or 1) * 10_000
            section = 0
            digit = 0
        else:
            raise ValueError(f"不支持的中文章号：{value}")
    return total + section + digit


def _line_spans(text: str) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    cursor = 0
    for raw in text.splitlines(keepends=True):
        end = cursor + len(raw)
        lines.append(
            {
                "start": cursor,
                "end": end,
                "content": raw.rstrip("\r\n"),
            }
        )
        cursor = end
    if cursor < len(text):
        lines.append({"start": cursor, "end": len(text), "content": text[cursor:]})
    return lines


def _visible_line(line: dict[str, Any], format_hint: str) -> str:
    value = line["content"].strip()
    if format_hint == "md" and (markdown := _MARKDOWN_HEADING.fullmatch(value)):
        return markdown.group("value").strip()
    return value


def _heading(line: dict[str, Any], format_hint: str) -> dict[str, Any] | None:
    value = _visible_line(line, format_hint)
    match = (
        _CHINESE_HEADING.fullmatch(value)
        or _ENGLISH_HEADING.fullmatch(value)
        or _CHINESE_SECTION_HEADING.fullmatch(value)
    )
    if not match:
        return None
    display_title = (match.group("title") or "").strip()
    return {
        "start": line["start"],
        "end": line["end"],
        "heading_text": value,
        "chapter_no": _chapter_number(match.group("number")),
        "display_title": display_title,
    }


def _visible_lines(
    lines: list[dict[str, Any]],
    format_hint: str,
) -> list[dict[str, Any]]:
    if format_hint != "md":
        return lines
    visible: list[dict[str, Any]] = []
    fenced = False
    for line in lines:
        if _MARKDOWN_FENCE.match(line["content"]):
            fenced = not fenced
            continue
        if not fenced:
            visible.append(line)
    return visible


def _normalized_title(value: str) -> str:
    return re.sub(r"[\s:：\-—_·]+", "", value)


def _stable_double_heading_groups(
    text: str,
    lines: list[dict[str, Any]],
    headings: list[dict[str, Any]],
    format_hint: str,
) -> tuple[list[dict[str, Any]], list[int]]:
    visible = _visible_lines(lines, format_hint)
    pairs: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for heading in headings:
        nested = _CHINESE_HEADING.fullmatch(heading["display_title"])
        if nested is None:
            continue
        nested_number = _chapter_number(nested.group("number"))
        nested_title = (nested.group("title") or "").strip()
        if nested_number != heading["chapter_no"] or not nested_title:
            continue
        right_line = next(
            (
                line
                for line in visible
                if line["start"] >= heading["end"] and line["content"].strip()
            ),
            None,
        )
        if right_line is None or text[heading["end"] : right_line["start"]].strip():
            continue
        compact = _COMPACT_CHINESE_HEADING.fullmatch(
            _visible_line(right_line, format_hint)
        )
        if compact is None:
            continue
        compact_number = _chapter_number(compact.group("number"))
        compact_title = compact.group("title").strip()
        if (
            compact_number == heading["chapter_no"]
            and _normalized_title(compact_title) == _normalized_title(nested_title)
        ):
            pairs.append((heading, right_line, nested_title))

    numbers = [left["chapter_no"] for left, _, _ in pairs]
    stable = (
        len(pairs) >= 2
        and len(numbers) == len(set(numbers))
        and all(current == previous + 1 for previous, current in zip(numbers, numbers[1:]))
    )
    if not stable:
        return headings, []

    by_start = {left["start"]: (right, title) for left, right, title in pairs}
    compact_starts = {right["start"] for _, right, _ in pairs}
    collapsed: list[dict[str, Any]] = []
    for heading in headings:
        if heading["start"] in compact_starts:
            continue
        pair = by_start.get(heading["start"])
        if pair is None:
            collapsed.append(heading)
            continue
        right, title = pair
        collapsed.append(
            {
                **heading,
                "end": right["end"],
                "heading_text": _visible_line(right, format_hint),
                "display_title": title,
            }
        )
    return collapsed, numbers


def _ambiguous_unrecognized_heading(
    lines: list[dict[str, Any]],
    format_hint: str,
) -> str | None:
    """找出不足以授予章节身份、也不应被无标题 fallback 忽略的结构信号。"""
    for line in _visible_lines(lines, format_hint):
        value = _visible_line(line, format_hint)
        match = _AMBIGUOUS_COMPACT_SECTION_LINE.fullmatch(value)
        if not match:
            continue
        suffix = match.group("suffix")
        separated = suffix[0].isspace() or suffix[0] in _HEADING_SEPARATORS
        if not separated and any(char in _SENTENCE_ENDINGS for char in suffix):
            return value
    return None


def _coverage(text: str, spans: list[dict[str, Any]]) -> dict[str, int]:
    cursor = 0
    lost = 0
    duplicated = 0
    reordered = 0
    illegal_overlap = 0
    covered = 0
    for item in spans:
        start = item["start"]
        end = item["end"]
        if not 0 <= start <= end <= len(text):
            illegal_overlap += 1
            continue
        if start < cursor:
            duplicated += cursor - start
            illegal_overlap += 1
        elif start > cursor:
            lost += start - cursor
        if start < cursor:
            reordered += 1
        covered += max(0, end - max(start, cursor))
        cursor = max(cursor, end)
    if cursor < len(text):
        lost += len(text) - cursor
    return {
        "source_chars": len(text),
        "covered_chars": covered,
        "lost_chars": lost,
        "duplicated_chars": duplicated,
        "reordered_chars": reordered,
        "illegal_overlap": illegal_overlap,
    }


def _public_span(text: str, role: str, start: int, end: int) -> dict[str, Any]:
    return {
        "role": role,
        "start": start,
        "end": end,
        "text_sha256": _sha256_text(text[start:end]),
    }


def _blocked(text: str, block_type: str, detail: str) -> dict[str, Any]:
    spans = [_public_span(text, "blocked_source", 0, len(text))] if text else []
    return {
        "identity": IDENTITY,
        "status": "BLOCKED",
        "source_sha256": _sha256_text(text),
        "source_chars": len(text),
        "candidates": [],
        "coverage_segments": spans,
        "coverage": _coverage(text, spans),
        "warnings": [f"强停：{detail}"],
        "blocks": [{"type": block_type, "detail": detail}],
        "api_calls": 0,
        "automatic_retries": 0,
    }


def chapterize_text(
    text: str,
    *,
    default_title: str,
    format_hint: str = "text",
) -> dict[str, Any]:
    """生成不带 C1 扩展字段的章节候选及内部来源坐标回执。"""
    if not isinstance(text, str):
        raise ValueError("chapterize_text 需要字符串原文")
    if format_hint not in {"text", "md", "docx"}:
        raise ValueError(f"不支持的 chapterization format_hint：{format_hint}")
    lines = _line_spans(text)
    headings = [
        item
        for line in _visible_lines(lines, format_hint)
        if (item := _heading(line, format_hint))
    ]
    headings, collapsed_numbers = _stable_double_heading_groups(
        text,
        lines,
        headings,
        format_hint,
    )

    if not headings:
        ambiguous = _ambiguous_unrecognized_heading(lines, format_hint)
        if ambiguous:
            return _blocked(
                text,
                "ambiguous_unrecognized_heading",
                f"无明确章标题，但出现不能安全当作无标题正文的结构行：{ambiguous}",
            )
        spans = [_public_span(text, "chapter_body:1", 0, len(text))] if text else []
        candidate = {
            "title": default_title,
            "display_title": default_title,
            "chapter_no": None,
            "text": text,
            "text_sha256": _sha256_text(text),
            "source_ref": {
                "coordinate_basis": "source_text",
                "heading_start": None,
                "heading_end": None,
                "body_start": 0,
                "body_end": len(text),
            },
        }
        return {
            "identity": IDENTITY,
            "status": "SINGLE_UNTITLED",
            "source_sha256": _sha256_text(text),
            "source_chars": len(text),
            "candidates": [candidate],
            "coverage_segments": spans,
            "coverage": _coverage(text, spans),
            "warnings": ["未识别到明确章标题；整份输入保留为一个 C1，没有猜测章界"],
            "blocks": [],
            "api_calls": 0,
            "automatic_retries": 0,
        }

    preamble = text[: headings[0]["start"]]
    if preamble.strip():
        return _blocked(
            text,
            "non_whitespace_before_first_chapter",
            "首个明确章标题前存在非空材料，当前基础切章不能安全归属",
        )

    for item in headings:
        if item["display_title"] and _NESTED_CHAPTER_MARKER.match(item["display_title"]):
            return _blocked(
                text,
                "ambiguous_heading_conflict",
                f"标题行内出现第二个章节标记：{item['heading_text']}",
            )

    numbers = [item["chapter_no"] for item in headings]
    for previous, current in zip(numbers, numbers[1:]):
        if current != previous + 1:
            return _blocked(
                text,
                "chapter_sequence_contradiction",
                f"章序必须连续递增，实际相邻章号为 {previous} → {current}",
            )

    candidates: list[dict[str, Any]] = []
    spans: list[dict[str, Any]] = []
    warnings: list[str] = []
    if collapsed_numbers:
        warnings.append(
            f"折叠稳定重复的同章双标题门牌：{collapsed_numbers}；两行原文均由 heading span 覆盖"
        )
    if headings[0]["start"]:
        spans.append(_public_span(text, "separator_before_first_chapter", 0, headings[0]["start"]))
    for index, item in enumerate(headings):
        body_start = item["end"]
        body_end = headings[index + 1]["start"] if index + 1 < len(headings) else len(text)
        body = text[body_start:body_end]
        candidates.append(
            {
                "title": item["heading_text"],
                "display_title": item["display_title"] or item["heading_text"],
                "chapter_no": item["chapter_no"],
                "text": body,
                "text_sha256": _sha256_text(body),
                "source_ref": {
                    "coordinate_basis": "source_text",
                    "heading_start": item["start"],
                    "heading_end": item["end"],
                    "body_start": body_start,
                    "body_end": body_end,
                },
            }
        )
        spans.append(_public_span(text, f"chapter_heading:{index + 1}", item["start"], item["end"]))
        if body_start < body_end:
            spans.append(_public_span(text, f"chapter_body:{index + 1}", body_start, body_end))
        if not body.strip():
            warnings.append(f"第 {index + 1} 个章节候选正文为空；保留空章且不吸收相邻正文")

    coverage = _coverage(text, spans)
    if any(coverage[key] for key in ("lost_chars", "duplicated_chars", "reordered_chars", "illegal_overlap")):
        return _blocked(text, "source_coverage_failure", "章节来源坐标存在缺口、重叠或乱序")

    duplicate_titles = {
        value for value in (item["display_title"] for item in candidates)
        if sum(candidate["display_title"] == value for candidate in candidates) > 1
    }
    for value in sorted(duplicate_titles):
        warnings.append(f"显示标题《{value}》重复；章节按独立顺序身份全部保留")

    return {
        "identity": IDENTITY,
        "status": "READY",
        "source_sha256": _sha256_text(text),
        "source_chars": len(text),
        "candidates": candidates,
        "coverage_segments": spans,
        "coverage": coverage,
        "warnings": warnings,
        "blocks": [],
        "api_calls": 0,
        "automatic_retries": 0,
    }
