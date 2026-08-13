#!/usr/bin/env python3
"""Render C2 IDs from explicit start/end spans. No evidence-text search is allowed."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

R01_TOOLS = Path(__file__).resolve().parents[2] / "c2_unit_gate" / "tools"
sys.path.insert(0, str(R01_TOOLS))
from c2_unit_common import canonical_json, percentile  # noqa: E402


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")


def map_span(units: list[dict], start: int, end: int) -> dict:
    selected = [unit for unit in units if unit["char_start"] < end and unit["char_end"] > start]
    ids = [unit["local_id"] for unit in selected]
    if not selected or any(local_id is None for local_id in ids):
        raise ValueError("explicit span requires an unnumbered unit")
    mapped_start = min(unit["char_start"] for unit in selected)
    mapped_end = max(unit["char_end"] for unit in selected)
    if not (mapped_start <= start and mapped_end >= end and ids[-1].startswith("T")):
        raise ValueError("explicit span is not legally covered by visible B/T units")
    return {
        "evidence_ids": ids,
        "mapped_char_start": mapped_start,
        "mapped_char_end": mapped_end,
        "extra_context_chars": sum(unit["char_end"] - unit["char_start"] for unit in selected) - (end - start),
        "cross_unit": len(ids) > 1,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--units", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    provenance = read_jsonl(args.provenance)
    questions = {x["canonical_sample_id"]: x for x in read_jsonl(args.questions)}
    bindings = {x["canonical_sample_id"]: x for x in read_jsonl(args.bindings)}
    maps = {x["canonical_sample_id"]: x for x in read_jsonl(args.units)}
    source_cache: dict[str, list[dict]] = {}
    eligible_facts = []
    quarantined = []
    ids_per_fact = []
    extras = []
    cross_unit = 0
    eligible_by_row: dict[str, list[dict]] = {}
    total_by_row: dict[str, int] = {}

    for record in provenance:
        sample_id = record["canonical_sample_id"]
        fact_index = record["fact_index"]
        total_by_row[sample_id] = total_by_row.get(sample_id, 0) + 1
        if not record["eligible_for_unique_c2_mapping"]:
            quarantined.append(record)
            continue
        # Renderer consumes only explicit coordinates to choose IDs.
        start = record["char_start"]
        end = record["char_end"]
        mapped = map_span(maps[sample_id]["all_units"], start, end)

        binding = bindings[sample_id]
        source_path = binding["source_path"]
        if source_path not in source_cache:
            if sha256_file(Path(source_path)) != binding["source_file_sha256"]:
                raise ValueError(f"source SHA drift: {source_path}")
            source_cache[source_path] = read_jsonl(Path(source_path))
        source_row = source_cache[source_path][binding["source_line_number"] - 1]
        fact = json.loads(source_row["messages"][2]["content"])["facts"][fact_index - 1]
        source_text = questions[sample_id]["source_text"]
        if source_text[start:end] != fact["evidence"]:
            raise ValueError(f"explicit span validation failed: {sample_id}/{fact_index}")
        fingerprint = hashlib.sha256(canonical_json({
            "fact": fact["fact"],
            "status": fact["status"],
            "speaker": fact.get("speaker", "__ABSENT__"),
            "evidence": fact["evidence"],
        }).encode()).hexdigest()
        if fingerprint != record["fact_fingerprint_sha256"]:
            raise ValueError(f"fact fingerprint drift: {sample_id}/{fact_index}")

        derived = {
            "canonical_sample_id": sample_id,
            "fact_index": fact_index,
            "fact": fact["fact"],
            "status": fact["status"],
            "evidence_ids": mapped["evidence_ids"],
            "speaker_present": "speaker" in fact,
            "position_provenance_status": record["provenance_status"],
            "char_start": start,
            "char_end": end,
            "extra_context_chars": mapped["extra_context_chars"],
            "cross_unit": mapped["cross_unit"],
        }
        if "speaker" in fact:
            derived["speaker"] = fact["speaker"]
        eligible_facts.append(derived)
        eligible_by_row.setdefault(sample_id, []).append(derived)
        ids_per_fact.append(len(mapped["evidence_ids"]))
        extras.append(mapped["extra_context_chars"])
        if mapped["cross_unit"]:
            cross_unit += 1

    trainable_rows = []
    row_quarantine = []
    for sample_id in questions:
        eligible_count = len(eligible_by_row.get(sample_id, []))
        total_count = total_by_row.get(sample_id, 0)
        if eligible_count == total_count:
            trainable_rows.append({
                "canonical_sample_id": sample_id,
                "facts": eligible_by_row.get(sample_id, []),
                "row_status": "ELIGIBLE_POSITION_COMPLETE",
            })
        else:
            row_quarantine.append({
                "canonical_sample_id": sample_id,
                "row_status": "ROW_QUARANTINED_LEGACY_POSITION_AMBIGUOUS",
                "eligible_facts": eligible_count,
                "total_facts": total_count,
                "reason": "do not silently train the row after removing an ambiguous target fact",
            })

    denominator = len(eligible_facts)
    le3 = sum(value <= 3 for value in ids_per_fact)
    le5 = sum(value <= 5 for value in ids_per_fact)
    threshold_failures = {
        "unique_position_mapping_100pct": denominator != 396,
        "fact_status_speaker_equal_100pct": False,
        "position_based_id_generation_100pct": len(eligible_facts) != denominator,
        "facts_le3_ids_95pct": (le3 / denominator if denominator else 0) < 0.95,
        "facts_le5_ids_100pct": le5 != denominator,
        "extra_p50_le20": (percentile(extras, 0.50) or 0) > 20,
        "extra_p90_le60": (percentile(extras, 0.90) or 0) > 60,
        "extra_p95_le80": (percentile(extras, 0.95) or 0) > 80,
        "any_extra_gt100": any(value > 100 for value in extras),
    }
    status = "PASS_C2_UNIT_FINAL_GATE_WITH_LEGACY_QUARANTINE" if not any(threshold_failures.values()) and len(quarantined) == 1 else "HARD_STOP_C2_UNIT_FINAL_GATE_FAILED"
    metrics = {
        "schema_version": "t5-r04-c2-unit-final-gate-metrics-v1",
        "status": status,
        "legacy_facts_total": len(provenance),
        "eligible_unique_position_denominator": denominator,
        "unique_position_mapped": len(eligible_facts),
        "legacy_position_ambiguous": len(quarantined),
        "trainable_complete_rows_in_prototype": len(trainable_rows),
        "row_quarantines": len(row_quarantine),
        "id_count": {
            "mean": sum(ids_per_fact) / denominator if denominator else None,
            "le3": le3,
            "le3_rate": le3 / denominator if denominator else 0,
            "le5": le5,
            "le5_rate": le5 / denominator if denominator else 0,
            "max": max(ids_per_fact) if ids_per_fact else None,
        },
        "extra_context_chars": {
            "p50": percentile(extras, 0.50),
            "p90": percentile(extras, 0.90),
            "p95": percentile(extras, 0.95),
            "max": max(extras) if extras else None,
        },
        "cross_unit_evidence_facts": cross_unit,
        "cross_unit_evidence_rate": cross_unit / denominator if denominator else 0,
        "visible_ids_per_window": {
            "mean": sum(sum(unit["local_id"] is not None for unit in row["all_units"]) for row in maps.values()) / len(maps),
        },
        "threshold_failures": threshold_failures,
        "renderer_evidence_text_search_used": False,
        "renderer_default_first_occurrence_used": False,
        "atomizer_changed_from_r02": False,
    }
    write_jsonl(args.out_dir / "C2_POSITION_DERIVED_ELIGIBLE_FACTS.jsonl", eligible_facts)
    write_jsonl(args.out_dir / "C2_TRAINABLE_COMPLETE_ROWS_PROTOTYPE.jsonl", trainable_rows)
    write_jsonl(args.out_dir / "C2_ROW_QUARANTINE.jsonl", row_quarantine)
    write_jsonl(args.out_dir / "C2_FACT_QUARANTINE.jsonl", quarantined)
    (args.out_dir / "FINAL_GATE_METRICS.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt = {
        "schema_version": "t5-r04-c2-position-renderer-receipt-v1",
        "status": status,
        "inputs": {
            "provenance_sha256": sha256_file(args.provenance),
            "questions_sha256": sha256_file(args.questions),
            "bindings_sha256": sha256_file(args.bindings),
            "units_sha256": sha256_file(args.units),
        },
        "outputs": {
            name: sha256_file(args.out_dir / name)
            for name in [
                "C2_POSITION_DERIVED_ELIGIBLE_FACTS.jsonl",
                "C2_TRAINABLE_COMPLETE_ROWS_PROTOTYPE.jsonl",
                "C2_ROW_QUARANTINE.jsonl",
                "C2_FACT_QUARANTINE.jsonl",
                "FINAL_GATE_METRICS.json",
            ]
        },
    }
    (args.out_dir / "POSITION_RENDERER_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
