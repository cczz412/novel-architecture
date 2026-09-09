"""M2 切窗器：章节正文 → 冠军结构责任段（C2）。

切窗结构沿用研究仓验证过的守擂冠军配方：
    完整自然责任段 620–923 字 + 每侧最多 180 字只读背景（halo）
（出处：小说架构仓 T5_R04 系列对照实验；参数在 config.json，由调用方传入）

产出合同：字符串 legacy 入口保持 C2 v0；C1 v1 current view 入口产出 C2 v1。
注意：start/end 是相对「自然段规范化拼接文本」（段落去空行后用单个换行重排）
的字符偏移，不是原始文件里的偏移。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

try:
    from . import text_mapping as mapping_runtime
except ImportError:  # direct local-file CLI
    import text_mapping as mapping_runtime

from jsonschema import Draft202012Validator


C11_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "contracts"
    / "C11_CHAPTER_REVISION_LEDGER.schema.json"
)


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


def _validated_c1_v1_text(chapter: dict) -> tuple[str, dict]:
    schema = json.loads(C11_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    if next(validator.iter_errors(chapter), None) is not None:
        raise ValueError("C1_V1_CURRENT_VIEW_INVALID")
    revision_ref = chapter["chapter_revision_ref"]
    if revision_ref["chapter_id"] != chapter["id"]:
        raise ValueError("C1_V1_REVISION_CHAPTER_MISMATCH")
    text = chapter["text"]
    if revision_ref["revision_text_sha256"] != hashlib.sha256(text.encode("utf-8")).hexdigest():
        raise ValueError("C1_V1_REVISION_SHA_MISMATCH")
    return text, copy.deepcopy(revision_ref)


def segment_chapter(
    text: str | dict, lo: int, hi: int, halo: int, *, text_mapping: bool = False
) -> list[dict]:
    """整章切窗；C1 v1 对象逐字段继承 revision ref，字符串保持 legacy v0。"""
    revision_ref = None
    if isinstance(text, dict):
        text, revision_ref = _validated_c1_v1_text(text)
    elif not isinstance(text, str):
        raise ValueError("SEGMENT_INPUT_MUST_BE_C1_V1_OR_LEGACY_TEXT")
    if type(text_mapping) is not bool:
        raise ValueError("TEXT_MAPPING_OPTION_MUST_BE_BOOL")
    if text_mapping and revision_ref is None:
        raise ValueError("TEXT_MAPPING_REQUIRES_C1_V1")
    context = None
    if text_mapping:
        context = mapping_runtime.build_context(text)
    flat = "\n".join(split_paragraphs(text))
    out = []
    for i, s in enumerate(build_segments(text, lo, hi), 1):
        segment = {
            "seg": i,
            "text": s["text"],
            "start": s["start"],
            "end": s["end"],
            "halo_before": flat[max(0, s["start"] - halo): s["start"]],
            "halo_after": flat[s["end"]: s["end"] + halo],
        }
        if revision_ref is not None:
            segment = {
                "contract": "C2_SEGMENT",
                "version": "v1",
                "chapter_revision_ref": copy.deepcopy(revision_ref),
                **segment,
            }
        if context is not None:
            segment["text_map"] = copy.deepcopy(context)
        out.append(segment)
    return out
