#!/usr/bin/env python3
"""Gold-free parsing and deterministic C2_UNIT atomization helpers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable


BACKGROUND = "【小说背景卡｜只辅助理解，不代替证据】"
IDENTITY = "【短段身份】"
POS_BOUNDARY = "【责任边界｜用于判断归属，不是额外证据】"
POS_RAW = "【连续短段原文｜evidence 只能从这里逐字复制】"
SPECIAL_TARGET = "【本段负责区｜只抽证据结束位置落在这里的事实】"
SPECIAL_LEFT_PREFIX = "【只读左重叠区｜"


class BoundaryError(ValueError):
    """Raised when the question cannot be parsed exactly once."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_identity(user_text: str) -> dict[str, str]:
    matches = re.findall(
        r"【短段身份】\n- segment_id：([^\n]+)\n- sample_id：([^\n]+)\n- split：([^\n]+)",
        user_text,
    )
    if len(matches) != 1:
        raise BoundaryError(f"identity match count={len(matches)}")
    segment_id, source_sample_id, split = matches[0]
    return {
        "segment_id": segment_id.strip(),
        "source_sample_id": source_sample_id.strip(),
        "split": split.strip(),
    }


def parse_background_card(user_text: str) -> tuple[str, dict[str, Any]]:
    prefix = BACKGROUND + "\n"
    if not user_text.startswith(prefix):
        raise BoundaryError("background marker missing or not first")
    end = user_text.find("\n\n" + IDENTITY)
    if end < 0:
        raise BoundaryError("background card end marker missing")
    raw = user_text[len(prefix) : end]
    try:
        card = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BoundaryError(f"background JSON invalid: {exc}") from exc
    return raw, card


def _after_marker(user_text: str, marker: str) -> str:
    token = marker + "\n"
    if user_text.count(token) != 1:
        raise BoundaryError(f"marker count for {marker!r}={user_text.count(token)}")
    return user_text.split(token, 1)[1]


def parse_question(system_text: str, user_text: str) -> dict[str, Any]:
    """Parse only system/user content. This function has no answer argument."""
    background_raw, card = parse_background_card(user_text)
    identity = parse_identity(user_text)
    canonical_sample_id = identity["segment_id"]

    if POS_RAW + "\n" in user_text:
        if user_text.count(POS_BOUNDARY) != 1:
            raise BoundaryError("positive boundary marker is not unique")
        raw = _after_marker(user_text, POS_RAW)
        counts = re.findall(r"- 左侧重叠字符数：(\d+)", user_text)
        if len(counts) != 1:
            raise BoundaryError(f"left-overlap count matches={len(counts)}")
        left_count = int(counts[0])
        if not 0 <= left_count <= len(raw):
            raise BoundaryError(f"left-overlap count {left_count} outside raw length {len(raw)}")
        bridge_text = raw[:left_count]
        target_text = raw[left_count:]
        source_kind = "positive_continuous"
    else:
        left_headers = re.findall(r"^【只读左重叠区｜[^\n]+】$", user_text, re.M)
        if len(left_headers) != 1:
            raise BoundaryError(f"special left marker matches={len(left_headers)}")
        left_marker = left_headers[0]
        left_start = user_text.index(left_marker) + len(left_marker)
        if user_text[left_start : left_start + 1] != "\n":
            raise BoundaryError("special left marker is not line terminated")
        target_token = "\n\n" + SPECIAL_TARGET + "\n"
        if user_text.count(target_token) != 1:
            raise BoundaryError(f"special target marker matches={user_text.count(target_token)}")
        target_marker_start = user_text.index(target_token)
        bridge_text = user_text[left_start + 1 : target_marker_start]
        target_text = user_text[target_marker_start + len(target_token) :]
        raw = bridge_text + target_text
        left_count = len(bridge_text)
        source_kind = "special_explicit"

    if not target_text:
        raise BoundaryError("target region is empty")
    if canonical_sample_id != identity["segment_id"]:
        raise BoundaryError("canonical sample ID drift")

    return {
        "schema_version": "t5-r04-c2-unit-gold-free-question-v1",
        "canonical_sample_id": canonical_sample_id,
        "source_sample_id": identity["source_sample_id"],
        "segment_id": identity["segment_id"],
        "split": identity["split"],
        "source_kind": source_kind,
        "system_text": system_text,
        "background_card_raw": background_raw,
        "background_card": card,
        "bridge_text": bridge_text,
        "target_text": target_text,
        "source_text": raw,
        "bridge_char_count": left_count,
        "source_text_sha256": sha256_text(raw),
    }


@dataclass(frozen=True)
class Unit:
    region: str
    start: int
    end: int
    text: str


STRONG_END = set("。！？!?…")
WEAK_END = set("；;，,：:")
CLOSERS = set("\"'”’》〉】）)]」』")


def _candidate_boundaries(text: str, offset: int) -> tuple[set[int], set[int]]:
    strong: set[int] = set()
    weak: set[int] = set()
    for idx, ch in enumerate(text):
        absolute = offset + idx + 1
        if ch == "\n":
            strong.add(absolute)
        elif ch in STRONG_END:
            end = idx + 1
            while end < len(text) and text[end] in CLOSERS:
                end += 1
            strong.add(offset + end)
        elif ch in WEAK_END:
            weak.add(absolute)
    return strong, weak


def _initial_spans(text: str, offset: int, max_chars: int) -> list[tuple[int, int]]:
    if not text:
        return []
    strong, weak = _candidate_boundaries(text, offset)
    result: list[tuple[int, int]] = []
    start = offset
    limit = offset + len(text)
    while start < limit:
        cap = min(start + max_chars, limit)
        strong_before = [x for x in strong if start < x <= cap]
        if strong_before:
            end = max(strong_before)
        else:
            weak_before = [x for x in weak if start + 12 <= x <= cap]
            end = max(weak_before) if weak_before else cap
        if end <= start:
            raise BoundaryError("atomizer did not advance")
        result.append((start, end))
        start = end
    return result


def _merge_tiny(spans: list[tuple[int, int]], source: str, max_chars: int, min_visible: int) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    idx = 0
    while idx < len(spans):
        start, end = spans[idx]
        visible = len(source[start:end].strip())
        if visible < min_visible and idx + 1 < len(spans) and spans[idx + 1][1] - start <= max_chars:
            end = spans[idx + 1][1]
            idx += 1
        elif visible < min_visible and merged and end - merged[-1][0] <= max_chars:
            start = merged[-1][0]
            merged.pop()
        merged.append((start, end))
        idx += 1
    return merged


def atomize_region(source: str, region: str, start: int, end: int, max_chars: int, min_visible: int) -> list[Unit]:
    text = source[start:end]
    spans = _initial_spans(text, start, max_chars=max_chars)
    spans = _merge_tiny(spans, source, max_chars=max_chars, min_visible=min_visible)
    units = [Unit(region, a, b, source[a:b]) for a, b in spans]
    if "".join(unit.text for unit in units) != text:
        raise BoundaryError(f"{region} units cannot reconstruct region")
    return units


def atomize_question(question: dict[str, Any], max_chars: int = 80, min_visible: int = 8, visible_bridge_units: int = 3) -> dict[str, Any]:
    source = question["source_text"]
    bridge_end = question["bridge_char_count"]
    bridge_units = atomize_region(source, "bridge", 0, bridge_end, max_chars, min_visible)
    target_units = atomize_region(source, "target", bridge_end, len(source), max_chars, min_visible)
    visible_bridge_start = max(0, len(bridge_units) - visible_bridge_units)

    all_units: list[dict[str, Any]] = []
    b_index = 0
    for idx, unit in enumerate(bridge_units):
        visible_id = None
        if idx >= visible_bridge_start:
            b_index += 1
            visible_id = f"B{b_index:02d}"
        all_units.append({
            "region": unit.region,
            "local_id": visible_id,
            "char_start": unit.start,
            "char_end": unit.end,
            "text": unit.text,
            "text_sha256": sha256_text(unit.text),
        })
    for idx, unit in enumerate(target_units, 1):
        all_units.append({
            "region": unit.region,
            "local_id": f"T{idx:02d}",
            "char_start": unit.start,
            "char_end": unit.end,
            "text": unit.text,
            "text_sha256": sha256_text(unit.text),
        })

    visible_units = [unit for unit in all_units if unit["local_id"]]
    if len({unit["local_id"] for unit in visible_units}) != len(visible_units):
        raise BoundaryError("local IDs are not unique")
    if "".join(unit["text"] for unit in all_units) != source:
        raise BoundaryError("all units cannot reconstruct source")
    if len(target_units) > 99 or b_index > 99:
        raise BoundaryError("local ID width exceeded")

    readonly_before = "".join(unit["text"] for unit in all_units if unit["region"] == "bridge" and unit["local_id"] is None)
    return {
        "schema_version": "t5-r04-c2-unit-map-v1",
        "canonical_sample_id": question["canonical_sample_id"],
        "source_kind": question["source_kind"],
        "source_text_sha256": question["source_text_sha256"],
        "source_char_count": len(source),
        "bridge_char_count": bridge_end,
        "target_char_count": len(source) - bridge_end,
        "readonly_before_text": readonly_before,
        "readonly_before_char_count": len(readonly_before),
        "all_units": all_units,
        "visible_unit_count": len(visible_units),
        "target_unit_count": len(target_units),
        "atomizer": {
            "max_chars": max_chars,
            "min_visible_chars_for_tiny_merge": min_visible,
            "visible_bridge_units": visible_bridge_units,
        },
    }


def render_c2_user(question: dict[str, Any], unit_map: dict[str, Any]) -> str:
    identity = (
        f"【短段身份】\n- segment_id：{question['segment_id']}\n"
        f"- sample_id：{question['source_sample_id']}\n- split：{question['split']}"
    )
    parts = [BACKGROUND, question["background_card_raw"], "", identity]
    readonly = unit_map["readonly_before_text"]
    if readonly:
        parts.extend(["", "【只读上文｜仅辅助理解，不可作为证据编号】", readonly])
    parts.extend(["", "【C2_UNIT 可取证区｜只能返回下列 B/T 编号】"])
    for unit in unit_map["all_units"]:
        if unit["local_id"]:
            parts.append(f"[{unit['local_id']}]{unit['text']}")
    return "\n".join(parts)


def percentile(values: Iterable[int], p: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    fraction = pos - lo
    return ordered[lo] * (1 - fraction) + ordered[hi] * fraction
