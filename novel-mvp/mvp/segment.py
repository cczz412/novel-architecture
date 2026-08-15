"""M2 切窗器：章节正文 → 冠军结构责任段（C2）。

切窗结构沿用研究仓验证过的守擂冠军配方：
    完整自然责任段 620–923 字 + 每侧最多 180 字只读背景（halo）
（出处：小说架构仓 T5_R04 系列对照实验；参数在 config.json，由调用方传入）

产出合同：contracts/C2_SEGMENT.md（v0）。
注意：start/end 是相对「自然段规范化拼接文本」（段落去空行后用单个换行重排）
的字符偏移，不是原始文件里的偏移。
"""

from __future__ import annotations

import re


def split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\n\s*\n|\n", text)]
    return [p for p in parts if p]


def build_segments(text: str, lo: int, hi: int) -> list[dict]:
    """按自然段拼责任段：攒到 >=lo 字收口；单段超 hi 的自然段独立成段（保完整性）。"""
    paras = split_paragraphs(text)
    segments: list[list[str]] = []
    buf: list[str] = []
    buf_len = 0
    for p in paras:
        if buf and buf_len + len(p) > hi and buf_len >= lo:
            segments.append(buf)
            buf, buf_len = [], 0
        buf.append(p)
        buf_len += len(p)
    if buf:
        # 尾段太短时并回上一段，避免碎尾
        if segments and buf_len < lo // 2:
            segments[-1].extend(buf)
        else:
            segments.append(buf)
    joined = ["\n".join(s) for s in segments]
    out = []
    cursor = 0
    flat = "\n".join(paras)
    for seg in joined:
        start = flat.find(seg[:30], cursor)
        if start < 0:
            start = cursor
        out.append({"text": seg, "start": start, "end": start + len(seg)})
        cursor = start + len(seg)
    return out


def segment_chapter(text: str, lo: int, hi: int, halo: int) -> list[dict]:
    """整章切窗，返回 C2 责任段列表（含 seg 序号、位置、左右 halo）。"""
    flat = "\n".join(split_paragraphs(text))
    out = []
    for i, s in enumerate(build_segments(text, lo, hi), 1):
        out.append({
            "seg": i,
            "text": s["text"],
            "start": s["start"],
            "end": s["end"],
            "halo_before": flat[max(0, s["start"] - halo): s["start"]],
            "halo_after": flat[s["end"]: s["end"] + halo],
        })
    return out
