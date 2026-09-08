"""Explicit C2/C3/C4 text-map extension, using the frozen replay contract."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path


_SPEC = importlib.util.spec_from_file_location(
    "_c2_c1_text_map_contract",
    Path(__file__).resolve().parents[1] / "contracts/validate_c2_c1_text_map.py",
)
_CONTRACT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CONTRACT)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def build_context(text: str) -> dict:
    return {"normalization_version": _CONTRACT.NORMALIZATION_VERSION,
            "original_text": text, **_CONTRACT.replay_mapping(text)}


def validate_segment(segment: dict) -> dict:
    context = segment.get("text_map")
    if not isinstance(context, dict) or not isinstance(context.get("original_text"), str):
        raise ValueError("C2_TEXT_MAP_CONTEXT_INVALID")
    text = context["original_text"]
    if _canonical(context) != _canonical(build_context(text)):
        raise ValueError("C2_TEXT_MAP_REPLAY_MISMATCH")
    if _CONTRACT.sha256(text) != segment["chapter_revision_ref"]["revision_text_sha256"]:
        raise ValueError("C2_TEXT_MAP_REVISION_SHA_MISMATCH")
    left, right = segment["start"], segment["end"]
    flat = context["normalized_text"]
    if (type(left) is not int or type(right) is not int
            or not 0 <= left < right <= len(flat)
            or flat[left:right] != segment["text"]
            or (left and flat[left - 1] != "\n")
            or (right < len(flat) and flat[right] != "\n")):
        raise ValueError("C2_TEXT_MAP_RESPONSIBILITY_INVALID")
    return {"text": text, "chapter_revision_ref": segment["chapter_revision_ref"],
            "responsibility": {k: segment[k] for k in ("seg", "start", "end")}}


def build_evidence(segment: dict, quote: str) -> dict:
    snapshot = validate_segment(segment)
    context = segment["text_map"]
    if not isinstance(quote, str) or not quote:
        raise ValueError("C3_TEXT_MAP_QUOTE_REQUIRED")
    # This creates a candidate match, not an approval. Exact raw-or-normalized
    # equality is checked by the contract below; arbitrary whitespace edits fail.
    match = _CONTRACT.replay_mapping(quote)["normalized_text"]
    left, right = segment["start"], segment["end"]
    start = context["normalized_text"].find(match, left, right)
    if not match or start < left:
        raise ValueError("C3_TEXT_MAP_QUOTE_OUTSIDE_RESPONSIBILITY")
    end = start + len(match)
    raw_start = context["char_map"][start]
    raw_end = context["char_map"][end - 1] + 1
    raw_slice = snapshot["text"][raw_start:raw_end]
    evidence = {
        "contract": "C2_C1_TEXT_MAP", "version": "v1",
        "normalization_version": context["normalization_version"],
        "chapter_revision_ref": copy.deepcopy(snapshot["chapter_revision_ref"]),
        **{key: copy.deepcopy(context[key]) for key in
           ("normalized_text", "char_map", "removed_whitespace")},
        "responsibility": dict(snapshot["responsibility"]),
        "quote_original": quote, "normalized_match": match,
        "match_start": start, "match_end": end,
        "original_start": raw_start, "original_end": raw_end,
        "original_slice": raw_slice, "original_slice_sha256": _CONTRACT.sha256(raw_slice),
    }
    _CONTRACT.validate_mapping(evidence, snapshot)
    return evidence


def validate_candidate(candidate: dict, segment: dict, *, chapter: dict | None = None) -> dict:
    snapshot = validate_segment(segment)
    if chapter is not None:
        if (snapshot["chapter_revision_ref"] != chapter["chapter_revision_ref"]
                or snapshot["text"] != chapter["text"]):
            raise ValueError("C3_TEXT_MAP_CURRENT_CHAPTER_MISMATCH")
        snapshot["text"] = chapter["text"]
    evidence = candidate.get("text_map_evidence")
    result = _CONTRACT.validate_mapping(evidence, snapshot)
    if (candidate["quote"] != evidence["quote_original"]
            or candidate["chapter_revision_ref"] != snapshot["chapter_revision_ref"]
            or candidate["seg"] != snapshot["responsibility"]["seg"]):
        raise ValueError("C3_TEXT_MAP_CANDIDATE_IDENTITY_MISMATCH")
    return result


def validate_origin_evidence(evidence: object) -> dict:
    """Reconstruct the origin chapter without allocating by untrusted offsets.

    This checks stored proof consistency, not current responsibility authority.
    Admission additionally calls validate_candidate against the trusted C1/C2.
    """
    from jsonschema import Draft202012Validator

    schema = json.loads(_CONTRACT.SCHEMA_PATH.read_text(encoding="utf-8"))
    if not Draft202012Validator(schema).is_valid(evidence):
        raise ValueError("TEXT_MAP_SCHEMA_INVALID")
    if len(evidence["char_map"]) != len(evidence["normalized_text"]):
        raise ValueError("TEXT_MAP_REPLAY_MISMATCH")
    pieces = [(int(offset), int(offset) + 1, char)
              for offset, char in zip(evidence["char_map"], evidence["normalized_text"])]
    pieces.extend((int(row["start"]), int(row["end"]), row["text"])
                  for row in evidence["removed_whitespace"])
    pieces.sort(key=lambda row: row[0])
    cursor = 0
    texts = []
    for start, end, text in pieces:
        if start != cursor or end - start != len(text):
            raise ValueError("TEXT_MAP_ORIGIN_PARTITION_INVALID")
        texts.append(text)
        cursor = end
    return _CONTRACT.validate_mapping(evidence, {
        "text": "".join(texts),
        "chapter_revision_ref": evidence["chapter_revision_ref"],
        "responsibility": evidence["responsibility"],
    })
