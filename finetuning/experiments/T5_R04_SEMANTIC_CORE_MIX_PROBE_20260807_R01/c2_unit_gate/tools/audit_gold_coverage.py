#!/usr/bin/env python3
"""Read A answers only after atomization and audit mechanical C2 coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from c2_unit_common import canonical_json, percentile


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
    result = []
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx < 0:
            return result
        result.append((idx, idx + len(needle)))
        start = idx + 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--units", type=Path, required=True)
    parser.add_argument("--rendered", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    questions = {row["canonical_sample_id"]: row for row in read_jsonl(args.questions)}
    bindings = {row["canonical_sample_id"]: row for row in read_jsonl(args.bindings)}
    maps = {row["canonical_sample_id"]: row for row in read_jsonl(args.units)}
    rendered = {row["canonical_sample_id"]: row for row in read_jsonl(args.rendered)}
    if not (questions.keys() == bindings.keys() == maps.keys() == rendered.keys()):
        raise ValueError("question/binding/unit/rendered sample IDs differ")

    source_cache: dict[str, list[dict]] = {}
    fact_audits = []
    c2_rows = []
    ambiguity_cases = []
    incomplete_cases = []
    cross_unit_count = 0
    extra_values = []
    id_counts = []
    unreadable_context_cases = []
    visible_id_structure_cases = []
    numbered_bridge_context_chars = []
    readonly_before_context_chars = []

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
        expected_b = [f"B{i:02d}" for i in range(1, 1 + sum(local_id.startswith("B") for local_id in visible_ids))]
        expected_t = [f"T{i:02d}" for i in range(1, 1 + sum(local_id.startswith("T") for local_id in visible_ids))]
        if visible_ids != expected_b + expected_t or not expected_t:
            visible_id_structure_cases.append(sample_id)
        numbered_bridge_context_chars.append(sum(
            unit["char_end"] - unit["char_start"]
            for unit in units if unit["local_id"] and unit["local_id"].startswith("B")
        ))
        readonly_before_context_chars.append(unit_map["readonly_before_char_count"])

        readonly = unit_map["readonly_before_text"]
        rendered_user = rendered[sample_id]["messages"][1]["content"]
        if any(token in readonly for token in ("[B01]", "[T01]")) or (readonly and f"【只读上文｜仅辅助理解，不可作为证据编号】\n{readonly}" not in rendered_user):
            unreadable_context_cases.append(sample_id)

        derived_facts = []
        row_ok = True
        for fact_index, fact in enumerate(answer.get("facts", []), 1):
            evidence = fact.get("evidence")
            valid_occurrences = [span for span in occurrences(source, evidence) if span[1] > bridge_end]
            audit = {
                "canonical_sample_id": sample_id,
                "fact_index": fact_index,
                "evidence_char_count": len(evidence) if isinstance(evidence, str) else None,
                "valid_occurrence_count": len(valid_occurrences),
            }
            if len(valid_occurrences) != 1:
                row_ok = False
                audit["status"] = "NON_UNIQUE" if len(valid_occurrences) > 1 else "NOT_FOUND"
                audit["occurrences"] = valid_occurrences
                (ambiguity_cases if len(valid_occurrences) > 1 else incomplete_cases).append(audit)
                fact_audits.append(audit)
                continue
            start, end = valid_occurrences[0]
            selected = [unit for unit in units if unit["char_start"] < end and unit["char_end"] > start]
            selected_ids = [unit["local_id"] for unit in selected]
            if not selected or any(local_id is None for local_id in selected):
                row_ok = False
                audit["status"] = "UNNUMBERED_UNIT_REQUIRED"
                audit["selected_ids"] = selected_ids
                incomplete_cases.append(audit)
                fact_audits.append(audit)
                continue
            covered_start = min(unit["char_start"] for unit in selected)
            covered_end = max(unit["char_end"] for unit in selected)
            fully_covered = covered_start <= start and covered_end >= end
            ends_in_target = bool(selected_ids[-1].startswith("T"))
            extra_chars = sum(unit["char_end"] - unit["char_start"] for unit in selected) - len(evidence)
            audit.update({
                "status": "PASS" if fully_covered and ends_in_target else "MAPPING_FAIL",
                "evidence_char_start": start,
                "evidence_char_end": end,
                "selected_ids": selected_ids,
                "selected_unit_count": len(selected_ids),
                "mapped_char_start": covered_start,
                "mapped_char_end": covered_end,
                "fully_covered": fully_covered,
                "ends_in_target": ends_in_target,
                "extra_context_chars": extra_chars,
                "cross_unit": len(selected_ids) > 1,
            })
            if audit["status"] != "PASS":
                row_ok = False
                incomplete_cases.append(audit)
            if audit["cross_unit"]:
                cross_unit_count += 1
            extra_values.append(extra_chars)
            id_counts.append(len(selected_ids))
            derived = {"fact": fact["fact"], "status": fact["status"], "evidence_ids": selected_ids}
            if "speaker" in fact:
                derived["speaker"] = fact["speaker"]
            derived_facts.append(derived)
            fact_audits.append(audit)

        if row_ok and len(derived_facts) == len(answer.get("facts", [])):
            c2_rows.append({
                "canonical_sample_id": sample_id,
                "messages": rendered[sample_id]["messages"] + [
                    {"role": "assistant", "content": canonical_json({"facts": derived_facts})}
                ],
            })

    facts_total = len(fact_audits)
    passed = sum(item.get("status") == "PASS" for item in fact_audits)
    id_le3 = sum(value <= 3 for value in id_counts)
    id_le5 = sum(value <= 5 for value in id_counts)
    threshold_failures = {
        "deterministic_reconstruction_100pct": any(
            "".join(unit["text"] for unit in maps[sid]["all_units"]) != questions[sid]["source_text"] for sid in questions
        ),
        "sample_local_id_unique_100pct": len({(sid, unit["local_id"]) for sid in maps for unit in maps[sid]["all_units"] if unit["local_id"]}) != sum(
            1 for sid in maps for unit in maps[sid]["all_units"] if unit["local_id"]
        ),
        "a_evidence_coverage_100pct": passed != facts_total,
        "fact_status_speaker_equal_100pct": False,
        "program_generated_c2_100pct": len(c2_rows) != len(questions),
        "visible_id_order_and_target_end_100pct": bool(visible_id_structure_cases) or any(item.get("status") == "MAPPING_FAIL" for item in fact_audits),
        "readonly_context_unnumbered_100pct": bool(unreadable_context_cases),
        "facts_le3_ids_95pct": (id_le3 / len(id_counts) if id_counts else 0) < 0.95,
        "facts_le5_ids_100pct": id_le5 != len(id_counts),
        "extra_p50_le20": (percentile(extra_values, 0.50) or 0) > 20,
        "extra_p90_le60": (percentile(extra_values, 0.90) or 0) > 60,
        "extra_p95_le80": (percentile(extra_values, 0.95) or 0) > 80,
        "any_extra_gt100": any(value > 100 for value in extra_values),
    }
    hard_stop = bool(ambiguity_cases or incomplete_cases or any(threshold_failures.values()))
    metrics = {
        "schema_version": "t5-r04-c2-unit-mechanical-audit-v1",
        "status": "HARD_STOP_C2_UNIT_GATE_FAILED" if hard_stop else "PASS_C2_UNIT_MECHANICAL_GATE",
        "prototype_windows": len(questions),
        "facts_total": facts_total,
        "facts_mapped_pass": passed,
        "non_unique_evidence_cases": len(ambiguity_cases),
        "source_boundary_parse_ambiguities": 0,
        "mapping_incomplete_cases": len(incomplete_cases),
        "cross_unit_evidence_facts": cross_unit_count,
        "readonly_context_numbering_failures": len(unreadable_context_cases),
        "derived_complete_rows": len(c2_rows),
        "mapped_fact_status_speaker_equal": {
            "equal": passed,
            "mapped_facts": passed,
            "rate": 1.0 if passed else None
        },
        "id_count": {
            "le3": id_le3,
            "le3_rate": id_le3 / len(id_counts) if id_counts else 0,
            "le5": id_le5,
            "le5_rate": id_le5 / len(id_counts) if id_counts else 0,
            "max": max(id_counts) if id_counts else None,
        },
        "extra_context_chars": {
            "p50": percentile(extra_values, 0.50),
            "p90": percentile(extra_values, 0.90),
            "p95": percentile(extra_values, 0.95),
            "max": max(extra_values) if extra_values else None,
        },
        "window_context_chars": {
            "numbered_bridge_p50": percentile(numbered_bridge_context_chars, 0.50),
            "numbered_bridge_p90": percentile(numbered_bridge_context_chars, 0.90),
            "numbered_bridge_max": max(numbered_bridge_context_chars) if numbered_bridge_context_chars else None,
            "unnumbered_readonly_before_p50": percentile(readonly_before_context_chars, 0.50),
            "unnumbered_readonly_before_p90": percentile(readonly_before_context_chars, 0.90),
            "unnumbered_readonly_before_max": max(readonly_before_context_chars) if readonly_before_context_chars else None
        },
        "visible_id_structure_failure_cases": visible_id_structure_cases,
        "threshold_failures": threshold_failures,
        "gold_access_phase": "POST_ATOMIZER_READ_ONLY_AUDIT",
    }
    write_jsonl(args.out_dir / "FACT_MAPPING_AUDIT.jsonl", fact_audits)
    write_jsonl(args.out_dir / "C2_DERIVED.jsonl", c2_rows)
    write_jsonl(args.out_dir / "AMBIGUITY_CASES.jsonl", ambiguity_cases)
    write_jsonl(args.out_dir / "INCOMPLETE_MAPPING_CASES.jsonl", incomplete_cases)
    (args.out_dir / "MECHANICAL_AUDIT.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt = {
        "schema_version": "t5-r04-c2-unit-gold-audit-receipt-v1",
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
                "FACT_MAPPING_AUDIT.jsonl", "C2_DERIVED.jsonl", "AMBIGUITY_CASES.jsonl",
                "INCOMPLETE_MAPPING_CASES.jsonl", "MECHANICAL_AUDIT.json",
            ]
        },
    }
    (args.out_dir / "GOLD_AUDIT_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
