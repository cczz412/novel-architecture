#!/usr/bin/env python3
"""Backfill explicit spans only for uniquely matched legacy facts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r02-audit", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    audits = read_jsonl(args.r02_audit)
    questions = {x["canonical_sample_id"]: x for x in read_jsonl(args.questions)}
    bindings = {x["canonical_sample_id"]: x for x in read_jsonl(args.bindings)}
    source_cache: dict[str, list[dict]] = {}
    provenance = []
    quarantine = []

    for audit in audits:
        sample_id = audit["canonical_sample_id"]
        fact_index = audit["fact_index"]
        binding = bindings[sample_id]
        source_path = binding["source_path"]
        if source_path not in source_cache:
            if sha256_file(Path(source_path)) != binding["source_file_sha256"]:
                raise ValueError(f"source SHA drift: {source_path}")
            source_cache[source_path] = read_jsonl(Path(source_path))
        source_row = source_cache[source_path][binding["source_line_number"] - 1]
        fact = json.loads(source_row["messages"][2]["content"])["facts"][fact_index - 1]
        evidence = fact["evidence"]
        fingerprint = sha256_text(canonical({
            "fact": fact["fact"],
            "status": fact["status"],
            "speaker": fact.get("speaker", "__ABSENT__"),
            "evidence": evidence,
        }))
        base = {
            "canonical_sample_id": sample_id,
            "fact_index": fact_index,
            "fact_fingerprint_sha256": fingerprint,
            "evidence_text_sha256": sha256_text(evidence),
            "source_text_sha256": questions[sample_id]["source_text_sha256"],
        }
        candidates = audit.get("candidates", [])
        if audit["status"] == "PASS_UNIQUE" and len(candidates) == 1:
            start, end = candidates[0]["occurrence"]
            source_text = questions[sample_id]["source_text"]
            if source_text[start:end] != evidence:
                raise ValueError(f"span does not recover evidence: {sample_id}/{fact_index}")
            provenance.append({
                **base,
                "coordinate_space": "c2_source_text_bridge_plus_target",
                "indexing": "unicode_codepoint_0_based_half_open",
                "char_start": start,
                "char_end": end,
                "provenance_status": "LEGACY_UNIQUE_TEXT_MATCH_BACKFILL",
                "eligible_for_unique_c2_mapping": True,
            })
        elif audit["status"] == "DUPLICATE_TEXT_REPRESENTATION_LIMIT" and len(candidates) > 1:
            record = {
                **base,
                "provenance_status": "LEGACY_POSITION_AMBIGUOUS",
                "eligible_for_unique_c2_mapping": False,
                "candidate_ranges": [candidate["occurrence"] for candidate in candidates],
            }
            provenance.append(record)
            quarantine.append({
                **record,
                "reason": "legacy A gold stores evidence_text but no authoritative occurrence position",
                "reentry_condition": "restore authoritative explicit span through canonical gold revision",
                "exclude_from_unique_c2_train_and_score_denominator": True,
                "containing_row_must_not_be_silently_trained_with_fact_removed": True,
            })
        else:
            raise ValueError(f"unsupported audit state: {sample_id}/{fact_index}/{audit['status']}")

    if len(provenance) != len(audits):
        raise ValueError("provenance count mismatch")
    provenance_path = args.out_dir / "A_POSITION_PROVENANCE_SIDECAR.jsonl"
    quarantine_path = args.out_dir / "LEGACY_POSITION_QUARANTINE.jsonl"
    write_jsonl(provenance_path, provenance)
    write_jsonl(quarantine_path, quarantine)
    receipt = {
        "schema_version": "t5-r04-a-position-provenance-migration-receipt-v1",
        "status": "PASS_LEGACY_POSITION_SIDECAR_BUILT",
        "facts_total": len(provenance),
        "unique_position_backfilled": sum(x["eligible_for_unique_c2_mapping"] for x in provenance),
        "legacy_position_ambiguous": len(quarantine),
        "default_first_occurrence_used": False,
        "manual_position_guess_used": False,
        "outputs": {
            "provenance_sha256": sha256_file(provenance_path),
            "quarantine_sha256": sha256_file(quarantine_path),
        },
    }
    (args.out_dir / "POSITION_MIGRATION_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
