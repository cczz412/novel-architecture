#!/usr/bin/env python3
"""Verify the two position-contract gate runs are byte-identical."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FILES = [
    "A_POSITION_PROVENANCE_SIDECAR.jsonl",
    "LEGACY_POSITION_QUARANTINE.jsonl",
    "POSITION_MIGRATION_RECEIPT.json",
    "C2_POSITION_DERIVED_ELIGIBLE_FACTS.jsonl",
    "C2_TRAINABLE_COMPLETE_ROWS_PROTOTYPE.jsonl",
    "C2_ROW_QUARANTINE.jsonl",
    "C2_FACT_QUARANTINE.jsonl",
    "FINAL_GATE_METRICS.json",
    "POSITION_RENDERER_RECEIPT.json",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-1", type=Path, required=True)
    parser.add_argument("--run-2", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for name in FILES:
        left = args.run_1 / name
        right = args.run_2 / name
        rows.append({
            "path": name,
            "run_1_sha256": sha(left),
            "run_2_sha256": sha(right),
            "byte_identical": left.read_bytes() == right.read_bytes(),
        })
    passed = all(row["byte_identical"] for row in rows)
    result = {
        "schema_version": "t5-r04-c2-unit-final-gate-two-run-v1",
        "status": "PASS_FINAL_GATE_TWO_RUN_IDENTICAL" if passed else "FAIL_FINAL_GATE_NONDETERMINISTIC",
        "all_outputs_byte_identical": passed,
        "comparisons": rows,
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
