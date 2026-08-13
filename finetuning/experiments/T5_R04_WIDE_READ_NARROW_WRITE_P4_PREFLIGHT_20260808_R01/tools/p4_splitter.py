#!/usr/bin/env python3
"""P4 deterministic whole-chapter splitter and toy preflight renderer.

The splitter is deliberately gold-blind. Frozen gold spans may be supplied only
to the separate classification function after boundaries have been produced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


TERMINATORS = set("。！？!?；;")
OPEN_QUOTES = {"“": "”", "‘": "’", "「": "」", "『": "』"}
CLOSE_QUOTES = set(OPEN_QUOTES.values())
GRANULARITIES = {
    "P4-GRAN-10": 10,
    "P4-GRAN-20": 20,
    "P4-GRAN-30": 30,
}
TOY_ONLY_SYSTEM_PROMPT = "TOY_ONLY：读取只读前缀，只从尾部编号区举证；输出严格 JSON。"
TOY_ONLY_OUTPUT_CONTRACT = {
    "root": "facts",
    "required_fact_keys": ["fact", "status", "speaker", "evidence_ids"],
    "evidence_source": "RESPONSIBILITY_EXCERPT_ALLOWED_IDS_ONLY",
    "identity": "TOY_ONLY_NOT_P3_C0",
}


class SplitterError(ValueError):
    """Raised when source or span invariants fail."""


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_source_bytes(source_bytes: bytes, expected_source_sha256: str) -> str:
    actual = sha256_bytes(source_bytes)
    if actual != expected_source_sha256:
        raise SplitterError(
            f"source SHA drift: expected={expected_source_sha256} actual={actual}"
        )
    try:
        text = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SplitterError("source is not strict UTF-8; automatic transcoding is forbidden") from exc
    if text.encode("utf-8") != source_bytes:
        raise SplitterError("strict UTF-8 round trip does not reproduce source bytes")
    return text


def _byte_offsets(text: str) -> list[int]:
    offsets = [0]
    total = 0
    for char in text:
        total += len(char.encode("utf-8"))
        offsets.append(total)
    return offsets


def _raw_boundaries(text: str) -> list[int]:
    boundaries: list[int] = []
    quote_stack: list[str] = []
    pending_quoted_end = False
    for index, char in enumerate(text):
        if char in OPEN_QUOTES:
            quote_stack.append(OPEN_QUOTES[char])
        elif char in CLOSE_QUOTES:
            if quote_stack and quote_stack[-1] == char:
                quote_stack.pop()
            if pending_quoted_end and not quote_stack:
                next_char = text[index + 1] if index + 1 < len(text) else ""
                # A closing quote followed by attribution (for example
                # “走吧。”他说。) is still part of the same dialogue turn.
                # Only a real end-of-line/end-of-text closes the turn here.
                if not next_char or next_char == "\n":
                    boundaries.append(index + 1)
                pending_quoted_end = False

        if char in TERMINATORS:
            if quote_stack:
                pending_quoted_end = True
            else:
                boundaries.append(index + 1)
        elif char == "\n" and not quote_stack:
            boundaries.append(index + 1)

    if not boundaries or boundaries[-1] != len(text):
        boundaries.append(len(text))
    return sorted(set(boundaries))


def atomize(text: str) -> list[dict[str, Any]]:
    """Split only at sentence/newline/full-dialogue-turn boundaries."""
    if not text:
        raise SplitterError("whole chapter is empty")
    byte_offsets = _byte_offsets(text)
    raw: list[tuple[int, int]] = []
    start = 0
    for end in _raw_boundaries(text):
        if end <= start:
            continue
        piece = text[start:end]
        if piece.strip() or not raw:
            raw.append((start, end))
        else:
            previous_start, _ = raw.pop()
            raw.append((previous_start, end))
        start = end
    if start < len(text):
        raw.append((start, len(text)))
    if "".join(text[start:end] for start, end in raw) != text:
        raise SplitterError("atomic units do not reconstruct original text")

    atoms = []
    for index, (start, end) in enumerate(raw, 1):
        atoms.append(
            {
                "atom_id": f"U{index:04d}",
                "start_char": start,
                "end_char_exclusive": end,
                "start_byte": byte_offsets[start],
                "end_byte_exclusive": byte_offsets[end],
                "text": text[start:end],
            }
        )
    return atoms


def _balanced_cut_indices(atoms: list[dict[str, Any]], requested_zones: int) -> list[int]:
    zone_count = min(requested_zones, len(atoms))
    if zone_count <= 0:
        raise SplitterError("zone count must be positive")
    if zone_count == 1:
        return [len(atoms)]

    total_bytes = atoms[-1]["end_byte_exclusive"]
    cuts: list[int] = []
    previous = 0
    atom_count = len(atoms)
    for boundary_number in range(1, zone_count):
        desired = total_bytes * boundary_number / zone_count
        remaining_zones = zone_count - boundary_number
        low = previous + 1
        high = atom_count - remaining_zones
        candidates = range(low, high + 1)
        cut = min(
            candidates,
            key=lambda idx: (abs(atoms[idx - 1]["end_byte_exclusive"] - desired), idx),
        )
        cuts.append(cut)
        previous = cut
    cuts.append(atom_count)
    return cuts


def split_chapter(
    source_bytes: bytes,
    source_id: str,
    granularity: str,
    expected_source_sha256: str,
) -> dict[str, Any]:
    if granularity not in GRANULARITIES:
        raise SplitterError(f"unknown granularity: {granularity}")
    text = decode_source_bytes(source_bytes, expected_source_sha256)
    atoms = atomize(text)
    cuts = _balanced_cut_indices(atoms, GRANULARITIES[granularity])
    zones: list[dict[str, Any]] = []
    start_index = 0
    for zone_index, end_index in enumerate(cuts, 1):
        members = atoms[start_index:end_index]
        start_atom = members[0]
        end_atom = members[-1]
        zone_text = "".join(member["text"] for member in members)
        zones.append(
            {
                "zone_id": f"{granularity}-Z{zone_index:03d}",
                "start_char": start_atom["start_char"],
                "end_char_exclusive": end_atom["end_char_exclusive"],
                "start_byte": start_atom["start_byte"],
                "end_byte_exclusive": end_atom["end_byte_exclusive"],
                "atom_ids": [member["atom_id"] for member in members],
                "text": zone_text,
            }
        )
        start_index = end_index

    if "".join(zone["text"] for zone in zones) != text:
        raise SplitterError("responsibility zones do not reconstruct original text")
    return {
        "schema_version": "t5-r04-p4-splitter-output-v1",
        "source_id": source_id,
        "source_sha256": sha256_bytes(source_bytes),
        "granularity": granularity,
        "requested_zone_count": GRANULARITIES[granularity],
        "actual_zone_count": len(zones),
        "atomic_unit_count": len(atoms),
        "source_char_count": len(text),
        "source_byte_count": len(source_bytes),
        "atoms": atoms,
        "zones": zones,
    }


def _zones_intersecting_span(
    zones: list[dict[str, Any]], start: int, end: int
) -> list[str]:
    if not 0 <= start < end:
        return []
    return [
        zone["zone_id"]
        for zone in zones
        if zone["start_char"] < end and start < zone["end_char_exclusive"]
    ]


def classify_frozen_gold(
    source_bytes: bytes,
    split_result: dict[str, Any],
    gold_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify frozen spans after splitting; this function never changes boundaries."""
    text = decode_source_bytes(source_bytes, split_result["source_sha256"])
    if split_result["source_byte_count"] != len(source_bytes):
        raise SplitterError("split result byte count does not match bound source")
    if split_result["source_char_count"] != len(text):
        raise SplitterError("split result character count does not match bound source")
    audits = []
    for fact in gold_facts:
        zone_ids: list[str] = []
        span_audits = []
        uncovered = False
        for span in fact["evidence_spans"]:
            start = span["start_char"]
            end = span["end_char_exclusive"]
            expected = span["text"]
            exact = 0 <= start <= end <= len(text) and text[start:end] == expected
            intersecting = (
                _zones_intersecting_span(split_result["zones"], start, end) if exact else []
            )
            if not exact or not intersecting:
                uncovered = True
            zone_ids.extend(intersecting)
            span_audits.append(
                {
                    **span,
                    "exact_source_match": exact,
                    "intersecting_zone_ids": intersecting,
                }
            )
        unique_zones = sorted(set(zone_ids))
        if uncovered:
            classification = "UNMAPPABLE_OR_NOT_FULLY_COVERED"
        elif len(unique_zones) == 1:
            classification = "WITHIN_ONE_RESPONSIBILITY_ZONE"
        else:
            classification = "CROSS_RESPONSIBILITY_ZONES"
        audits.append(
            {
                "fact_id": fact["fact_id"],
                "classification": classification,
                "zone_ids": unique_zones,
                "evidence_spans": span_audits,
            }
        )
    return {
        "schema_version": "t5-r04-p4-frozen-gold-zone-audit-v1",
        "granularity": split_result["granularity"],
        "facts": audits,
    }


def build_denominator_registry(
    gold_facts: list[dict[str, Any]], audits: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    all_gold = [fact["fact_id"] for fact in gold_facts]
    own_contained: dict[str, list[str]] = {}
    for granularity, audit in audits.items():
        own_contained[granularity] = sorted(
            fact["fact_id"]
            for fact in audit["facts"]
            if fact["classification"] == "WITHIN_ONE_RESPONSIBILITY_ZONE"
        )
    common = sorted(set.intersection(*(set(items) for items in own_contained.values())))
    return {
        "schema_version": "t5-r04-p4-fixed-denominator-registry-v1",
        "all_gold_fact_ids": all_gold,
        "all_gold_denominator": len(all_gold),
        "common_contained_fact_ids": common,
        "common_contained_denominator": len(common),
        "per_granularity_contained_diagnostic_only": own_contained,
        "winner_rule": (
            "cross-granularity comparison must report common-contained and all-gold; "
            "per-granularity contained sets are diagnostic only"
        ),
    }


def _responsibility_atoms(split_result: dict[str, Any], zone: dict[str, Any]) -> list[dict[str, Any]]:
    lookup = {atom["atom_id"]: atom for atom in split_result["atoms"]}
    return [lookup[atom_id] for atom_id in zone["atom_ids"]]


def render_pair(
    split_result: dict[str, Any],
    zone_index: int,
    system_prompt: str,
    output_contract: dict[str, Any],
    local_halo_zones: int = 1,
) -> dict[str, Any]:
    """Render model payloads with only READ_CONTEXT.text different."""
    zones = split_result["zones"]
    if not 0 <= zone_index < len(zones):
        raise SplitterError("zone index outside range")
    target = zones[zone_index]
    atoms = _responsibility_atoms(split_result, target)
    visible_tail_rows = []
    audit_tail_rows = []
    allowed_ids = []
    for index, atom in enumerate(atoms, 1):
        local_id = f"T{index:02d}"
        allowed_ids.append(local_id)
        visible_tail_rows.append({"evidence_id": local_id, "text": atom["text"]})
        audit_tail_rows.append(
            {
                "evidence_id": local_id,
                "stable_atom_id": atom["atom_id"],
                "start_char": atom["start_char"],
                "end_char_exclusive": atom["end_char_exclusive"],
                "start_byte": atom["start_byte"],
                "end_byte_exclusive": atom["end_byte_exclusive"],
                "text": atom["text"],
            }
        )
    local_start = max(0, zone_index - local_halo_zones)
    local_end = min(len(zones), zone_index + local_halo_zones + 1)
    local_text = "".join(zone["text"] for zone in zones[local_start:local_end])
    full_text = "".join(zone["text"] for zone in zones)
    common = {
        "schema_version": "t5-r04-p4-wide-read-narrow-write-input-v2",
        "system_prompt": system_prompt,
        "output_contract": output_contract,
        "read_context": {"numbered": False, "text": None},
        "responsibility_excerpt": {
            "allowed_evidence_ids": allowed_ids,
            "rows": visible_tail_rows,
        },
    }
    local_payload = json.loads(json.dumps(common, ensure_ascii=False))
    full_payload = json.loads(json.dumps(common, ensure_ascii=False))
    local_payload["read_context"]["text"] = local_text
    full_payload["read_context"]["text"] = full_text
    return {
        "model_payloads": {"local": local_payload, "full": full_payload},
        "run_sidecar": {
            "arms": {
                "local": {
                    "arm": "LOCAL_READ",
                    "read_zone_start_index": local_start,
                    "read_zone_end_index_exclusive": local_end,
                },
                "full": {
                    "arm": "FULL_CHAPTER_READ",
                    "read_zone_start_index": 0,
                    "read_zone_end_index_exclusive": len(zones),
                },
            },
            "responsibility_mapping": {
                "zone_id": target["zone_id"],
                "rows": audit_tail_rows,
            },
        },
    }


def build_toy(
    source_path: Path,
    gold_path: Path,
    expected_source_sha256: str,
) -> dict[str, Any]:
    source_bytes = source_path.read_bytes()
    decode_source_bytes(source_bytes, expected_source_sha256)
    # Produce every boundary set before the frozen gold sidecar is opened.
    # This makes the gold-blind ordering mechanically inspectable.
    splits = {
        granularity: split_chapter(
            source_bytes,
            "TOY-CHAPTER-001",
            granularity,
            expected_source_sha256,
        )
        for granularity in GRANULARITIES
    }
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    outputs = {}
    audits: dict[str, dict[str, Any]] = {}
    for granularity, split_result in splits.items():
        audit = classify_frozen_gold(source_bytes, split_result, gold["facts"])
        audits[granularity] = audit
        outputs[granularity] = {
            "split": split_result,
            "frozen_gold_audit": audit,
            "input_pair": render_pair(
                split_result,
                min(4, len(split_result["zones"]) - 1),
                TOY_ONLY_SYSTEM_PROMPT,
                TOY_ONLY_OUTPUT_CONTRACT,
            ),
        }
    return {
        "schema_version": "t5-r04-p4-toy-splitter-build-v1",
        "source_sha256": sha256_bytes(source_bytes),
        "source_binding_verified": True,
        "strict_utf8_round_trip_verified": True,
        "gold_sha256": sha256_bytes(gold_path.read_bytes()),
        "gold_read_after_split_only": True,
        "denominator_registry": build_denominator_registry(gold["facts"], audits),
        "outputs": outputs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = build_toy(args.source, args.gold, args.expected_source_sha256)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical_json_bytes(result))
    print(json.dumps({"status": "PASS", "out": str(args.out), "sha256": sha256_bytes(args.out.read_bytes())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
