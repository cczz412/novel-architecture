#!/usr/bin/env python3
"""Produce the frozen R01 to R02 trade-off comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def delta(new: float, old: float) -> dict:
    return {
        "absolute": new - old,
        "relative_rate": (new - old) / old if old else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r01-metrics", type=Path, required=True)
    parser.add_argument("--r01-units", type=Path, required=True)
    parser.add_argument("--r02-metrics", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    r01 = load(args.r01_metrics)
    r02 = load(args.r02_metrics)
    r01_maps = [json.loads(line) for line in args.r01_units.read_text(encoding="utf-8").splitlines()]
    r01_total_units = sum(len(row["all_units"]) for row in r01_maps)
    r01_visible_units = sum(sum(unit["local_id"] is not None for unit in row["all_units"]) for row in r01_maps)
    r01_chars = sum(row["source_char_count"] for row in r01_maps)
    r01_mean_ids = sum(
        len(json.loads(line).get("selected_ids", []))
        for line in (args.r01_metrics.parent / "FACT_MAPPING_AUDIT.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("status") == "PASS"
    ) / r01["facts_mapped_pass"]

    r02_units = r02["unit_map"]
    result = {
        "schema_version": "t5-r04-c2-unit-r01-r02-comparison-v1",
        "same_prototype_windows": True,
        "thresholds_changed": False,
        "single_global_atomizer_change": "unit_max_chars 80 -> 40",
        "r01": {
            "total_units": r01_total_units,
            "average_unit_chars": r01_chars / r01_total_units,
            "average_visible_ids_per_window": r01_visible_units / r01["prototype_windows"],
            "mean_evidence_ids_per_uniquely_mapped_fact": r01_mean_ids,
            "extra_context_chars": r01["extra_context_chars"],
            "cross_unit_facts": r01["cross_unit_evidence_facts"],
            "cross_unit_rate": r01["cross_unit_evidence_facts"] / r01["facts_mapped_pass"],
            "duplicate_text_ambiguities": r01["non_unique_evidence_cases"],
        },
        "r02": {
            "total_units": r02_units["total_units"],
            "average_unit_chars": r02_units["average_unit_chars"],
            "average_visible_ids_per_window": r02_units["average_visible_ids_per_window"],
            "mean_evidence_ids_per_uniquely_mapped_fact": r02["id_count"]["mean"],
            "extra_context_chars": r02["extra_context_chars"],
            "cross_unit_facts": r02["cross_unit_evidence_facts"],
            "cross_unit_rate": r02["cross_unit_evidence_rate"],
            "duplicate_text_ambiguities": r02["contract_b"]["unresolved_duplicate_text_facts"],
        },
    }
    result["growth"] = {
        "total_units": delta(result["r02"]["total_units"], result["r01"]["total_units"]),
        "average_unit_chars": delta(result["r02"]["average_unit_chars"], result["r01"]["average_unit_chars"]),
        "average_visible_ids_per_window": delta(result["r02"]["average_visible_ids_per_window"], result["r01"]["average_visible_ids_per_window"]),
        "mean_evidence_ids_per_fact": delta(result["r02"]["mean_evidence_ids_per_uniquely_mapped_fact"], result["r01"]["mean_evidence_ids_per_uniquely_mapped_fact"]),
        "cross_unit_rate": delta(result["r02"]["cross_unit_rate"], result["r01"]["cross_unit_rate"]),
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
