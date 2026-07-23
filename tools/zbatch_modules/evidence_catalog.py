"""模块 1：从单章正文确定性生成冻结证据目录。"""

from __future__ import annotations

import re
from typing import Any


def nonspace_chars(value: str) -> int:
    return len(re.sub(r"\s+", "", value or ""))


def quote_windows(text: str, *, width: int = 22, step: int = 16) -> list[str]:
    """从一段原文确定性切出重叠短引，全部保持原文连续字节。"""
    value = text.strip()
    positions = [index for index, char in enumerate(value) if not char.isspace()]
    total = len(positions)
    if total < 10:
        return []
    if total <= 25:
        return [value]
    chunks: list[str] = []
    starts = list(range(0, total - width + 1, step))
    tail_start = total - width
    if not starts or starts[-1] != tail_start:
        starts.append(tail_start)
    for start in starts:
        end = start + width
        char_start = positions[start]
        char_end = positions[end - 1] + 1
        chunk = value[char_start:char_end].strip()
        if 10 <= nonspace_chars(chunk) <= 25:
            chunks.append(chunk)
    return chunks


def build_evidence_catalog(chapter: int, text: str) -> list[dict[str, Any]]:
    """生成冻结证据目录；模型只能选，不再自由截短引。"""
    quotes = quote_windows(text, width=22, step=18)
    return [
        {"anchor_id": f"E{index:04d}", "chapter": chapter, "quote": quote}
        for index, quote in enumerate(quotes, 1)
    ]


def evidence_catalog_coverage(text: str, catalog: list[dict[str, Any]]) -> float:
    """计算原文非空白字符中，有多少落在至少一个冻结短引里。"""
    nonspace_positions = {index for index, char in enumerate(text) if not char.isspace()}
    if not nonspace_positions:
        return 1.0
    covered: set[int] = set()
    for entry in catalog:
        quote = entry.get("quote") if isinstance(entry, dict) else None
        if not isinstance(quote, str) or not quote:
            continue
        start = 0
        while True:
            found = text.find(quote, start)
            if found < 0:
                break
            covered.update(
                index
                for index in range(found, found + len(quote))
                if not text[index].isspace()
            )
            start = found + 1
    return len(covered & nonspace_positions) / len(nonspace_positions)
