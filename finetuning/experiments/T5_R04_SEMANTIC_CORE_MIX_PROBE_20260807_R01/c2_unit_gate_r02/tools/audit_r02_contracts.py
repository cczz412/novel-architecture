#!/usr/bin/env python3
"""Post-atomizer gold audit for C2_UNIT R02 with duplicate contracts A/B."""

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
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")


def occurrences(text: str, needle: str) -> list[tuple[int, int]]:
    if not needle:
        return []
    spans = []
    cursor = 0
    while True:
        start = text.find(needle, cursor)
        if start < 0:
            return spans
        spans.append((start, start + len(needle)))
        cursor = start + 1


def mapped_candidate(units: list[dict], start: int, end: int, evidence_len: int) -> dict:
    selected = [unit for unit in units if unit["char_start"] < end and unit["char_end"] > start]
    ids = [unit["local_id"] for unit in selected]
    if not selected or any(local_id is None for local_id in ids):
        return {"valid": False, "reason": "UNNUMBERED_UNIT_REQUIRED", "occurrence": [start, end], "evidence_ids": ids}
    mapped_start = min(unit["char_start"] for unit in selected)
    mapped_end = max(unit["char_end"] for unit in selected)
    valid = mapped_start <= start and mapped_end >= end and ids[-1].startswith("T")
    return {
        "valid": valid,
        "reason": "PASS" if valid else "MAPPING_FAIL",
        "occurrence": [start, end],
        "evidence_ids": ids,
        "mapped_char_start": mapped_start,
        "mapped_char_end": mapped_end,
        "extra_context_chars": sum(unit["char_end"] - unit["char_start"] for unit in selected) - evidence_len,
        "cross_unit": len(ids) > 1,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--units", type=Path, required=True)
    parser.add_argument("--rendered", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    questions = {x["canonical_sample_id"]: x for x in read_jsonl(args.questions)}
    bindings = {x["canonical_sample_id"]: x for x in read_jsonl(args.bindings)}
    maps = {x["canonical_sample_id"]: x for x in read_jsonl(args.units)}
    rendered = {x["canonical_sample_id"]: x for x in read_jsonl(args.rendered)}
    if not (questions.keys() == bindings.keys() == maps.keys() == rendered.keys()):
        raise ValueError("input sample IDs differ")

    source_cache: dict[str, list[dict]] = {}
    audits = []
    ambiguities = []
    incomplete = []
    equivalence_sets = []
    derived_rows = []
    selected_id_counts = []
    extra_values = []
    cross_unit = 0
    visible_structure_failures = []
    readonly_failures = []

    for sample_id in questions:
        question = questions[sample_id]
        binding = bindings[sample_id]
        unit_map = maps[sample_id]
        source_path = binding["source_path"]
        if sha256_file(Path(source_path)) != binding["source_file_sha256"]:
            raise ValueError(f"source SHA drift: {source_path}")
        if source_path not in source_cache:
            source_cache[source_path] = read_jsonl(Path(source_path))
        source_row = source_cache[source_path][binding["source_line_number"] - 1]
        answer = json.loads(source_row["messages"][2]["content"])
        source = question["source_text"]
        bridge_end = question["bridge_char_count"]
        units = unit_map["all_units"]

        visible_ids = [unit["local_id"] for unit in units if unit["local_id"]]
        b_count = sum(local_id.startswith("B") for local_id in visible_ids)
        t_count = sum(local_id.startswith("T") for local_id in visible_ids)
        expected = [f"B{i:02d}" for i in range(1, b_count + 1)] + [f"T{i:02d}" for i in range(1, t_count + 1)]
        if visible_ids != expected or t_count == 0:
            visible_structure_failures.append(sample_id)
        readonly = unit_map["readonly_before_text"]
        rendered_user = rendered[sample_id]["messages"][1]["content"]
        if readonly and f"【只读上文｜仅辅助理解，不可作为证据编号】\n{readonly}" not in rendered_user:
            readonly_failures.append(sample_id)

        row_derived = []
        row_contract_b_complete = True
        for fact_index, fact in enumerate(answer.get("facts", []), 1):
            evidence = fact.get("evidence")
            valid_spans = [span for span in occurrences(source, evidence) if span[1] > bridge_end]
            candidates = [mapped_candidate(units, start, end, len(evidence)) for start, end in valid_spans]
            valid_candidates = [candidate for candidate in candidates if candidate["valid"]]
            unique_sequences = []
            seen_sequences = set()
            for candidate in valid_candidates:
                key = tuple(candidate["evidence_ids"])
                if key not in seen_sequences:
                    seen_sequences.add(key)
                    unique_sequences.append(candidate)

            contract_a_pass = bool(unique_sequences)
            # Contract B may collapse multiple textual occurrences only when the fixed unit map yields the same sequence.
            contract_b_pass = len(unique_sequences) == 1
            audit = {
                "canonical_sample_id": sample_id,
                "fact_index": fact_index,
                "evidence_char_count": len(evidence) if isinstance(evidence, str) else None,
                "valid_text_occurrence_count": len(valid_spans),
                "valid_unit_sequence_count": len(unique_sequences),
                "contract_a_equivalence_set_pass": contract_a_pass,
                "contract_b_unique_source_rule_pass": contract_b_pass,
                "candidates": unique_sequences,
            }
            if not contract_a_pass:
                audit["status"] = "UNMAPPABLE"
                incomplete.append(audit)
                row_contract_b_complete = False
            elif not contract_b_pass:
                audit["status"] = "DUPLICATE_TEXT_REPRESENTATION_LIMIT"
                ambiguities.append(audit)
                equivalence_sets.append({
                    "canonical_sample_id": sample_id,
                    "fact_index": fact_index,
                    "evidence_id_candidates": [candidate["evidence_ids"] for candidate in unique_sequences],
                    "occurrence_ranges": [candidate["occurrence"] for candidate in unique_sequences],
                    "trainable_under_existing_single_list_schema": False,
                })
                row_contract_b_complete = False
            else:
                audit["status"] = "PASS_UNIQUE"
                chosen = unique_sequences[0]
                selected_id_counts.append(len(chosen["evidence_ids"]))
                extra_values.append(chosen["extra_context_chars"])
                if chosen["cross_unit"]:
                    cross_unit += 1
                derived = {"fact": fact["fact"], "status": fact["status"], "evidence_ids": chosen["evidence_ids"]}
                if "speaker" in fact:
                    derived["speaker"] = fact["speaker"]
                row_derived.append(derived)
            audits.append(audit)

        if row_contract_b_complete and len(row_derived) == len(answer.get("facts", [])):
            derived_rows.append({
                "canonical_sample_id": sample_id,
                "messages": rendered[sample_id]["messages"] + [
                    {"role": "assistant", "content": canonical_json({"facts": row_derived})}
                ],
            })

    fact_total = len(audits)
    contract_a_passed = sum(item["contract_a_equivalence_set_pass"] for item in audits)
    contract_b_passed = sum(item["contract_b_unique_source_rule_pass"] for item in audits)
    le3 = sum(value <= 3 for value in selected_id_counts)
    le5 = sum(value <= 5 for value in selected_id_counts)
    reconstruct_failures = [
        sample_id for sample_id in questions
        if "".join(unit["text"] for unit in maps[sample_id]["all_units"]) != questions[sample_id]["source_text"]
    ]
    local_pairs = [
        (sample_id, unit["local_id"])
        for sample_id in maps for unit in maps[sample_id]["all_units"] if unit["local_id"]
    ]
    failures = {
        "deterministic_reconstruction_100pct": bool(reconstruct_failures),
        "sample_local_id_unique_100pct": len(local_pairs) != len(set(local_pairs)),
        "existing_contract_unique_mapping_100pct": contract_b_passed != fact_total,
        "contract_a_equivalence_coverage_100pct": contract_a_passed != fact_total,
        "fact_status_speaker_equal_100pct": False,
        "program_generated_existing_c2_100pct": len(derived_rows) != len(questions),
        "visible_id_order_target_end_100pct": bool(visible_structure_failures),
        "readonly_context_unnumbered_100pct": bool(readonly_failures),
        "facts_le3_ids_95pct": (le3 / len(selected_id_counts) if selected_id_counts else 0) < 0.95,
        "facts_le5_ids_100pct": le5 != len(selected_id_counts),
        "extra_p50_le20": (percentile(extra_values, 0.50) or 0) > 20,
        "extra_p90_le60": (percentile(extra_values, 0.90) or 0) > 60,
        "extra_p95_le80": (percentile(extra_values, 0.95) or 0) > 80,
        "any_extra_gt100": any(value > 100 for value in extra_values),
    }
    hard_stop = any(failures.values())
    metrics = {
        "schema_version": "t5-r04-c2-unit-r02-mechanical-audit-v1",
        "status": "HARD_STOP_C2_UNIT_R02_GATE_FAILED" if hard_stop else "PASS_C2_UNIT_R02_MECHANICAL_GATE",
        "prototype_windows": len(questions),
        "facts_total": fact_total,
        "contract_a": {
            "facts_with_at_least_one_valid_equivalent_sequence": contract_a_passed,
            "coverage_rate": contract_a_passed / fact_total if fact_total else 0,
            "ambiguous_facts_with_multiple_sequences": len(ambiguities),
            "compatible_with_existing_single_evidence_ids_training_schema": len(ambiguities) == 0,
        },
        "contract_b": {
            "facts_with_unique_source_determined_sequence": contract_b_passed,
            "coverage_rate": contract_b_passed / fact_total if fact_total else 0,
            "unresolved_duplicate_text_facts": len(ambiguities),
        },
        "source_boundary_parse_ambiguities": 0,
        "mapping_incomplete_cases": len(incomplete),
        "cross_unit_evidence_facts": cross_unit,
        "cross_unit_evidence_rate": cross_unit / contract_b_passed if contract_b_passed else 0,
        "derived_complete_rows_existing_schema": len(derived_rows),
        "id_count": {
            "mean": sum(selected_id_counts) / len(selected_id_counts) if selected_id_counts else None,
            "le3": le3,
            "le3_rate": le3 / len(selected_id_counts) if selected_id_counts else 0,
            "le5": le5,
            "le5_rate": le5 / len(selected_id_counts) if selected_id_counts else 0,
            "max": max(selected_id_counts) if selected_id_counts else None,
        },
        "extra_context_chars": {
            "p50": percentile(extra_values, 0.50),
            "p90": percentile(extra_values, 0.90),
            "p95": percentile(extra_values, 0.95),
            "max": max(extra_values) if extra_values else None,
        },
        "unit_map": {
            "total_units": sum(len(unit_map["all_units"]) for unit_map in maps.values()),
            "visible_units": sum(sum(unit["local_id"] is not None for unit in unit_map["all_units"]) for unit_map in maps.values()),
            "total_source_chars": sum(unit_map["source_char_count"] for unit_map in maps.values()),
            "average_unit_chars": sum(unit_map["source_char_count"] for unit_map in maps.values()) / sum(len(unit_map["all_units"]) for unit_map in maps.values()),
            "average_visible_ids_per_window": sum(sum(unit["local_id"] is not None for unit in unit_map["all_units"]) for unit_map in maps.values()) / len(maps),
            "max_unit_chars": max(len(unit["text"]) for unit_map in maps.values() for unit in unit_map["all_units"]),
        },
        "threshold_failures": failures,
        "gold_access_phase": "POST_ATOMIZER_READ_ONLY_AUDIT",
    }
    write_jsonl(args.out_dir / "FACT_MAPPING_AUDIT_R02.jsonl", audits)
    write_jsonl(args.out_dir / "DUPLICATE_EQUIVALENCE_SETS.jsonl", equivalence_sets)
    write_jsonl(args.out_dir / "AMBIGUITY_CASES_R02.jsonl", ambiguities)
    write_jsonl(args.out_dir / "INCOMPLETE_MAPPING_CASES_R02.jsonl", incomplete)
    write_jsonl(args.out_dir / "C2_DERIVED_EXISTING_SCHEMA.jsonl", derived_rows)
    (args.out_dir / "MECHANICAL_AUDIT_R02.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt = {
        "schema_version": "t5-r04-c2-unit-r02-audit-receipt-v1",
        "status": metrics["status"],
        "inputs": {
            "questions_sha256": sha256_file(args.questions),
            "bindings_sha256": sha256_file(args.bindings),
            "units_sha256": sha256_file(args.units),
            "rendered_sha256": sha256_file(args.rendered),
        },
        "outputs": {
            name: sha256_file(args.out_dir / name)
            for name in [
                "FACT_MAPPING_AUDIT_R02.jsonl", "DUPLICATE_EQUIVALENCE_SETS.jsonl",
                "AMBIGUITY_CASES_R02.jsonl", "INCOMPLETE_MAPPING_CASES_R02.jsonl",
                "C2_DERIVED_EXISTING_SCHEMA.jsonl", "MECHANICAL_AUDIT_R02.json",
            ]
        },
    }
    (args.out_dir / "GOLD_AUDIT_RECEIPT_R02.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
