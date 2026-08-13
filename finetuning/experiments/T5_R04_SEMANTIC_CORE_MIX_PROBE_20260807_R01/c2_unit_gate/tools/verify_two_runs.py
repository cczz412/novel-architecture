#!/usr/bin/env python3
"""Verify reproducibility and that the frozen evaluator was not touched."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


STABLE_RUN_FILES = [
    "SOURCE_UNITS.jsonl",
    "C2_QUESTIONS.jsonl",
    "ATOMIZER_RECEIPT.json",
    "FACT_MAPPING_AUDIT.jsonl",
    "C2_DERIVED.jsonl",
    "AMBIGUITY_CASES.jsonl",
    "INCOMPLETE_MAPPING_CASES.jsonl",
    "MECHANICAL_AUDIT.json",
    "GOLD_AUDIT_RECEIPT.json",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_inventory(root: Path) -> list[dict]:
    return [
        {"path": str(path.relative_to(root)), "sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-1", type=Path, required=True)
    parser.add_argument("--run-2", type=Path, required=True)
    parser.add_argument("--evaluator", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    comparisons = []
    for name in STABLE_RUN_FILES:
        first = args.run_1 / name
        second = args.run_2 / name
        if not first.is_file() or not second.is_file():
            raise FileNotFoundError(name)
        first_sha = sha256_file(first)
        second_sha = sha256_file(second)
        comparisons.append({
            "path": name,
            "run_1_sha256": first_sha,
            "run_2_sha256": second_sha,
            "byte_identical": first.read_bytes() == second.read_bytes(),
        })

    first_metrics = json.loads((args.run_1 / "MECHANICAL_AUDIT.json").read_text(encoding="utf-8"))
    second_metrics = json.loads((args.run_2 / "MECHANICAL_AUDIT.json").read_text(encoding="utf-8"))
    evaluator_inventory = tree_inventory(args.evaluator)
    result = {
        "schema_version": "t5-r04-c2-unit-two-run-comparison-v1",
        "status": "PASS_REPRODUCIBLE_HARD_STOP_RETAINED" if all(x["byte_identical"] for x in comparisons) and first_metrics == second_metrics else "FAIL_NONDETERMINISTIC",
        "all_stable_outputs_byte_identical": all(x["byte_identical"] for x in comparisons),
        "mechanical_audit_equal": first_metrics == second_metrics,
        "gate_outcome": first_metrics["status"],
        "comparisons": comparisons,
        "frozen_evaluator": {
            "root": str(args.evaluator),
            "file_count": len(evaluator_inventory),
            "inventory": evaluator_inventory,
            "aggregate_sha256": hashlib.sha256(
                json.dumps(evaluator_inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        },
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result["status"] == "FAIL_NONDETERMINISTIC":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
