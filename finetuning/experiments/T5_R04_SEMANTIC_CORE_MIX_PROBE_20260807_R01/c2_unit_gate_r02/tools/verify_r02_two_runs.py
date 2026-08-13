#!/usr/bin/env python3
"""Verify R02 two-run byte identity and frozen upstream identities."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FILES = [
    "SOURCE_UNITS.jsonl",
    "C2_QUESTIONS.jsonl",
    "ATOMIZER_RECEIPT.json",
    "FACT_MAPPING_AUDIT_R02.jsonl",
    "DUPLICATE_EQUIVALENCE_SETS.jsonl",
    "AMBIGUITY_CASES_R02.jsonl",
    "INCOMPLETE_MAPPING_CASES_R02.jsonl",
    "C2_DERIVED_EXISTING_SCHEMA.jsonl",
    "MECHANICAL_AUDIT_R02.json",
    "GOLD_AUDIT_RECEIPT_R02.json",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root: Path) -> list[dict]:
    return [
        {"path": str(path.relative_to(root)), "sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-1", type=Path, required=True)
    parser.add_argument("--run-2", type=Path, required=True)
    parser.add_argument("--r01-root", type=Path, required=True)
    parser.add_argument("--evaluator-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    comparisons = []
    for name in FILES:
        left = args.run_1 / name
        right = args.run_2 / name
        comparisons.append({
            "path": name,
            "run_1_sha256": sha256_file(left),
            "run_2_sha256": sha256_file(right),
            "byte_identical": left.read_bytes() == right.read_bytes(),
        })
    r01_inventory = inventory(args.r01_root)
    evaluator_inventory = inventory(args.evaluator_root)
    all_identical = all(item["byte_identical"] for item in comparisons)
    result = {
        "schema_version": "t5-r04-c2-unit-r02-two-run-comparison-v1",
        "status": "PASS_REPRODUCIBLE_R02_HARD_STOP_RETAINED" if all_identical else "FAIL_NONDETERMINISTIC",
        "all_outputs_byte_identical": all_identical,
        "gate_outcome": json.loads((args.run_1 / "MECHANICAL_AUDIT_R02.json").read_text(encoding="utf-8"))["status"],
        "comparisons": comparisons,
        "frozen_r01": {
            "file_count": len(r01_inventory),
            "aggregate_sha256": hashlib.sha256(json.dumps(r01_inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        },
        "frozen_evaluator_r02": {
            "file_count": len(evaluator_inventory),
            "aggregate_sha256": hashlib.sha256(json.dumps(evaluator_inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        },
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not all_identical:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
