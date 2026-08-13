#!/usr/bin/env python3
"""Measure prompt token burden for the frozen DEV_CORE zero-training arms."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

from transformers import AutoTokenizer


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def percentile(values: list[int], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize(values: list[int]) -> dict:
    return {
        "count": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "mean": sum(values) / len(values),
        "p90": percentile(values, 0.90),
        "max": max(values),
        "total": sum(values),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sealed-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    arms = {
        "Z00_A_CORE_FACT_ONLY": "Z00_BASE_A_CORE_QUESTIONS.jsonl",
        "Z01_C2_CORE_FACT_ONLY": "Z01_BASE_C2_CORE_QUESTIONS.jsonl",
        "Z02_C2_CORE_WITH_CITATION": "Z02C_C2_CORE_WITH_CITATION_QUESTIONS.jsonl",
    }
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True)
    rows_by_arm = {name: load_jsonl(args.sealed_dir / filename) for name, filename in arms.items()}
    case_orders = [[row["case_id"] for row in rows] for rows in rows_by_arm.values()]
    if any(order != case_orders[0] for order in case_orders[1:]):
        raise SystemExit("arm case orders differ")

    counts: dict[str, list[int]] = {}
    for arm, rows in rows_by_arm.items():
        arm_counts = []
        for row in rows:
            encoded = tokenizer.apply_chat_template(
                row["messages"],
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
            )
            arm_counts.append(len(encoded["input_ids"]))
        counts[arm] = arm_counts

    per_case = []
    for index, case_id in enumerate(case_orders[0]):
        z00 = counts["Z00_A_CORE_FACT_ONLY"][index]
        z01 = counts["Z01_C2_CORE_FACT_ONLY"][index]
        z02 = counts["Z02_C2_CORE_WITH_CITATION"][index]
        per_case.append(
            {
                "case_id": case_id,
                "z00_tokens": z00,
                "z01_tokens": z01,
                "z02_tokens": z02,
                "marker_delta_z01_minus_z00": z01 - z00,
                "citation_instruction_delta_z02_minus_z01": z02 - z01,
            }
        )

    tokenizer_json = args.model_dir / "tokenizer.json"
    receipt = {
        "schema_version": "t5-r04-dev-core-representation-burden-v1",
        "status": "PASS_TOKEN_MEASUREMENT_ONLY_NO_INFERENCE",
        "model_identity": {
            "model_dir_name": args.model_dir.name,
            "tokenizer_class": tokenizer.__class__.__name__,
            "tokenizer_json_sha256": sha256(tokenizer_json) if tokenizer_json.exists() else None,
        },
        "arm_input_tokens": {arm: summarize(values) for arm, values in counts.items()},
        "paired_deltas": {
            "marker_burden_z01_minus_z00": summarize(
                [row["marker_delta_z01_minus_z00"] for row in per_case]
            ),
            "citation_instruction_z02_minus_z01": summarize(
                [row["citation_instruction_delta_z02_minus_z01"] for row in per_case]
            ),
        },
        "method": "Qwen chat template tokenization with add_generation_prompt; no model inference",
        "per_case": per_case,
    }
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
