"""Offline C2/C1 contract replay; no production imports, body reads or writes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator


NORMALIZATION_VERSION = "LF_SPLIT_EDGE_WS_V1"
# Python 3.12 whitespace, frozen explicitly so a runtime Unicode upgrade cannot drift.
EDGE_WS = "\t\n\v\f\r\x1c\x1d\x1e\x1f \x85\xa0\u1680" + "".join(
    chr(n) for n in range(0x2000, 0x200B)
) + "\u2028\u2029\u202f\u205f\u3000"
SCHEMA_PATH = Path(__file__).with_name("C2_C1_TEXT_MAP.schema.json")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def replay_mapping(text: str) -> dict:
    """Map every normalized code point to one original code point, including LF."""
    paragraphs = []
    cursor = 0
    for line in text.split("\n"):
        start = cursor + len(line) - len(line.lstrip(EDGE_WS))
        end = cursor + len(line.rstrip(EDGE_WS))
        if start < end:
            paragraphs.append((start, end))
        cursor += len(line) + 1
    offsets = []
    for index, (start, end) in enumerate(paragraphs):
        if index:
            # Preserve the first actual LF between nonempty paragraphs.
            offsets.append(text.index("\n", paragraphs[index - 1][1], start))
        offsets.extend(range(start, end))
    removed = []
    previous = 0
    for offset in offsets + [len(text)]:
        if previous < offset:
            removed.append({"start": previous, "end": offset,
                            "text": text[previous:offset]})
        previous = offset + 1
    return {"normalized_text": "".join(text[i] for i in offsets),
            "char_map": offsets, "removed_whitespace": removed}


def validate_mapping(evidence: dict, snapshot: dict) -> dict:
    """Return a proposed slice only; snapshot is independently supplied by the caller.

    The caller owns the current revision and responsibility assignment. An evidence
    object is never permitted to supply its own trusted snapshot in production.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not Draft202012Validator(schema).is_valid(evidence):
        raise ValueError("TEXT_MAP_SCHEMA_INVALID")
    snapshot_schema = {"$ref": "#/$defs/snapshot", "$defs": schema["$defs"]}
    if not Draft202012Validator(snapshot_schema).is_valid(snapshot):
        raise ValueError("TEXT_MAP_SNAPSHOT_INVALID")
    ref = snapshot["chapter_revision_ref"]
    text = snapshot["text"]
    if sha256(text) != ref["revision_text_sha256"]:
        raise ValueError("TEXT_MAP_SNAPSHOT_SHA_MISMATCH")
    if evidence["chapter_revision_ref"] != ref:
        raise ValueError("TEXT_MAP_REVISION_MISMATCH")
    replay = replay_mapping(text)
    for key, value in replay.items():
        if evidence[key] != value:
            raise ValueError("TEXT_MAP_REPLAY_MISMATCH")
    flat = replay["normalized_text"]
    responsibility = snapshot["responsibility"]
    if evidence["responsibility"] != responsibility:
        raise ValueError("TEXT_MAP_RESPONSIBILITY_MISMATCH")
    left, right = responsibility["start"], responsibility["end"]
    if not (0 <= left < right <= len(flat)):
        raise ValueError("TEXT_MAP_RESPONSIBILITY_INVALID")
    # Responsibility consists of whole natural paragraphs; halo is never admitted.
    if (left and flat[left - 1] != "\n") or (right < len(flat) and flat[right] != "\n"):
        raise ValueError("TEXT_MAP_RESPONSIBILITY_INVALID")
    start, end = evidence["match_start"], evidence["match_end"]
    if not left <= start < end <= right:
        raise ValueError("TEXT_MAP_OUTSIDE_RESPONSIBILITY")
    match = flat[start:end]
    if not match.strip(EDGE_WS) or match[0] == "\n" or match[-1] == "\n":
        raise ValueError("TEXT_MAP_MATCH_INVALID")
    if evidence["normalized_match"] != match:
        raise ValueError("TEXT_MAP_MATCH_MISMATCH")
    # Count overlapping occurrences too. Coordinates alone do not disambiguate.
    if flat.find(match) != start or flat.find(match, start + 1) != -1:
        raise ValueError("TEXT_MAP_AMBIGUOUS_QUOTE")
    offsets = replay["char_map"]
    original_start, original_end = offsets[start], offsets[end - 1] + 1
    original_slice = text[original_start:original_end]
    if (evidence["original_start"], evidence["original_end"]) != (
        original_start, original_end
    ):
        raise ValueError("TEXT_MAP_ORIGINAL_RANGE_MISMATCH")
    if evidence["original_slice"] != original_slice:
        raise ValueError("TEXT_MAP_ORIGINAL_SLICE_MISMATCH")
    if evidence["original_slice_sha256"] != sha256(original_slice):
        raise ValueError("TEXT_MAP_ORIGINAL_SHA_MISMATCH")
    # Accept exactly the raw slice or exactly M2's normalized slice, never arbitrary
    # whitespace removal, paraphrases, punctuation edits, NFC or case folding.
    if evidence["quote_original"] not in (original_slice, match):
        raise ValueError("TEXT_MAP_CANDIDATE_QUOTE_MISMATCH")
    return {"chapter_revision_ref": dict(ref), "start": original_start,
            "end": original_end, "text": original_slice,
            "sha256": sha256(original_slice)}
