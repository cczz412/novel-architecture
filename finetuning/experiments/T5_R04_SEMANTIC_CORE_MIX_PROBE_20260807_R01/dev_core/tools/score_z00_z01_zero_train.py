#!/usr/bin/env python3
"""Deterministically score the paired DEV_CORE Z00/Z01 base-model outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable


DEV = Path(__file__).resolve().parents[1]
SEALED = DEV / "sealed_r01"
RUN = DEV / "zero_training_r01"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def normalize(value: Any) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or "")))


def recover_complete_strings(text: str) -> list[str]:
    marker = re.search(r'"fact_sentences"\s*:\s*\[', text)
    if not marker:
        return []
    values: list[str] = []
    index = marker.end()
    decoder = json.JSONDecoder()
    while index < len(text):
        while index < len(text) and text[index] in " \t\r\n,":
            index += 1
        if index >= len(text) or text[index] == "]":
            break
        try:
            value, consumed = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            break
        if not isinstance(value, str):
            break
        values.append(value)
        index += consumed
    return values


def count_match(gold: list[str], pred: list[str]) -> dict[str, int]:
    left = Counter(normalize(item) for item in gold)
    right = Counter(normalize(item) for item in pred)
    tp = sum((left & right).values())
    return {"tp": tp, "fp": sum(right.values()) - tp, "fn": sum(left.values()) - tp}


def finish(counts: dict[str, int]) -> dict[str, float | int]:
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    precision = tp / (tp + fp) if tp + fp else (1.0 if fn == 0 else 0.0)
    recall = tp / (tp + fn) if tp + fn else (1.0 if fp == 0 else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {**counts, "precision": precision, "recall": recall, "f1": f1}


def add(target: dict[str, int], source: dict[str, int]) -> None:
    for key in ("tp", "fp", "fn"):
        target[key] += source[key]


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize(values: list[float | int]) -> dict[str, float | int]:
    numeric = [float(value) for value in values]
    return {
        "count": len(values),
        "min": min(numeric),
        "median": statistics.median(numeric),
        "mean": sum(numeric) / len(numeric),
        "p90": percentile(numeric, 0.90),
        "max": max(numeric),
        "total": sum(numeric),
    }


def gold_fact_bucket(count: int) -> str:
    if count == 0:
        return "0"
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    return "3_plus"


def visible_id_bucket(count: int) -> str:
    if count <= 24:
        return "23_24"
    if count <= 26:
        return "25_26"
    return "27_28"


def aggregate(rows: list[dict[str, Any]], match_key: str) -> dict[str, Any]:
    counts = {"tp": 0, "fp": 0, "fn": 0}
    for row in rows:
        add(counts, row[match_key])
    return finish(counts)


def bucket_metrics(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[field])].append(row)
    return {
        key: {
            "cases": len(group),
            "structured_exact_fact": aggregate(group, "structured_exact_match"),
            "recoverable_exact_fact": aggregate(group, "recoverable_exact_match"),
        }
        for key, group in sorted(grouped.items())
    }


def bootstrap_paired(pairs: list[dict[str, Any]], match_key: str, iterations: int = 10000) -> dict[str, Any]:
    rng = random.Random(20260807)
    metric_values = {name: [] for name in ("precision", "recall", "f1")}
    count = len(pairs)
    for _ in range(iterations):
        sample = [pairs[rng.randrange(count)] for _ in range(count)]
        arm_metrics = {}
        for arm in ("Z00", "Z01"):
            counts = {"tp": 0, "fp": 0, "fn": 0}
            for pair in sample:
                add(counts, pair[arm][match_key])
            arm_metrics[arm] = finish(counts)
        for metric in metric_values:
            metric_values[metric].append(arm_metrics["Z01"][metric] - arm_metrics["Z00"][metric])
    result: dict[str, Any] = {
        "iterations": iterations,
        "seed": 20260807,
        "delta_definition": "Z01_minus_Z00",
    }
    for metric, values in metric_values.items():
        result[metric] = {
            "mean": sum(values) / len(values),
            "ci95_low": percentile(values, 0.025),
            "ci95_high": percentile(values, 0.975),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    gold_rows = read_jsonl(SEALED / "CORE_GOLD.jsonl")
    source_rows = read_jsonl(SEALED / "DEV_CORE_SOURCE_WINDOWS.jsonl")
    gold_by_id = {row["case_id"]: row for row in gold_rows}
    source_by_id = {row["case_id"]: row for row in source_rows}
    raw_by_arm = {
        "Z00": read_jsonl(RUN / "arm_z00/RAW_OUTPUTS.jsonl"),
        "Z01": read_jsonl(RUN / "arm_z01/RAW_OUTPUTS.jsonl"),
    }
    order = [row["case_id"] for row in gold_rows]
    if any([row["case_id"] for row in rows] != order for rows in raw_by_arm.values()):
        raise SystemExit("HARD_STOP raw/gold case order mismatch")

    case_rows: list[dict[str, Any]] = []
    by_arm_case: dict[tuple[str, str], dict[str, Any]] = {}
    for arm, raw_rows in raw_by_arm.items():
        for raw in raw_rows:
            case_id = raw["case_id"]
            gold = gold_by_id[case_id]["fact_sentences"]
            parsed = raw.get("parsed_output")
            structured = parsed.get("fact_sentences", []) if raw.get("schema_valid") and isinstance(parsed, dict) else []
            recovered = structured if structured else recover_complete_strings(raw["raw_output"])
            normalized = [normalize(item) for item in recovered]
            repeats = Counter(normalized)
            visible = int(source_by_id[case_id]["target_unit_count"]) + int(source_by_id[case_id]["visible_bridge_unit_count"])
            row = {
                "arm": arm,
                "case_id": case_id,
                "gold_fact_count": len(gold),
                "predicted_fact_count": len(structured),
                "recoverable_fact_count": len(recovered),
                "gold_fact_bucket": gold_fact_bucket(len(gold)),
                "visible_id_count": visible,
                "visible_id_bucket": visible_id_bucket(visible),
                "gold_evidence_ids_count": None,
                "cross_unit_gold": None,
                "structured_exact_match": count_match(gold, structured),
                "recoverable_exact_match": count_match(gold, recovered),
                "json_valid": bool(raw["json_valid"]),
                "schema_valid": bool(raw["schema_valid"]),
                "strict_repetition": bool(repeats and max(repeats.values()) >= 3),
                "duplicate_fact_count": sum(count - 1 for count in repeats.values() if count > 1),
                "reached_max_output_tokens": bool(raw["reached_max_output_tokens"]),
                "normal_completion": bool(raw["schema_valid"] and not raw["reached_max_output_tokens"]),
                "input_tokens": int(raw["input_tokens"]),
                "output_tokens": int(raw["output_tokens"]),
                "elapsed_seconds": float(raw["elapsed_seconds"]),
                "raw_output_sha256": hashlib.sha256(raw["raw_output"].encode("utf-8")).hexdigest(),
                "has_any_machine_exact_hit": count_match(gold, structured)["tp"] > 0,
                "fully_machine_exact": count_match(gold, structured)["fn"] == 0 and count_match(gold, structured)["fp"] == 0,
            }
            case_rows.append(row)
            by_arm_case[(arm, case_id)] = row

    paired_rows: list[dict[str, Any]] = []
    for case_id in order:
        z00, z01 = by_arm_case[("Z00", case_id)], by_arm_case[("Z01", case_id)]
        z00_metrics = finish(z00["structured_exact_match"])
        z01_metrics = finish(z01["structured_exact_match"])
        delta = z01_metrics["f1"] - z00_metrics["f1"]
        paired_rows.append(
            {
                "case_id": case_id,
                "gold_fact_count": z00["gold_fact_count"],
                "gold_fact_bucket": z00["gold_fact_bucket"],
                "visible_id_count": z01["visible_id_count"],
                "visible_id_bucket": z01["visible_id_bucket"],
                "gold_evidence_ids_count": None,
                "cross_unit_gold": None,
                "input_token_delta_z01_minus_z00": z01["input_tokens"] - z00["input_tokens"],
                "output_token_delta_z01_minus_z00": z01["output_tokens"] - z00["output_tokens"],
                "structured_f1_z00": z00_metrics["f1"],
                "structured_f1_z01": z01_metrics["f1"],
                "structured_f1_delta_z01_minus_z00": delta,
                "paired_direction": "C2_better" if delta > 0 else "A_better" if delta < 0 else "same",
                "Z00": z00,
                "Z01": z01,
            }
        )

    arm_metrics = {}
    for arm in ("Z00", "Z01"):
        rows = [row for row in case_rows if row["arm"] == arm]
        arm_metrics[arm] = {
            "cases": len(rows),
            "structured_exact_fact": aggregate(rows, "structured_exact_match"),
            "recoverable_exact_fact": aggregate(rows, "recoverable_exact_match"),
            "schema_valid_cases": sum(row["schema_valid"] for row in rows),
            "json_valid_cases": sum(row["json_valid"] for row in rows),
            "strict_repetition_cases": sum(row["strict_repetition"] for row in rows),
            "truncated_cases": sum(row["reached_max_output_tokens"] for row in rows),
            "normal_completion_cases": sum(row["normal_completion"] for row in rows),
            "cases_with_any_machine_exact_hit": sum(row["has_any_machine_exact_hit"] for row in rows),
            "fully_machine_exact_cases": sum(row["fully_machine_exact"] for row in rows),
            "input_tokens": summarize([row["input_tokens"] for row in rows]),
            "output_tokens": summarize([row["output_tokens"] for row in rows]),
            "elapsed_seconds": summarize([row["elapsed_seconds"] for row in rows]),
            "by_gold_fact_count": bucket_metrics(rows, "gold_fact_bucket"),
            "by_visible_id_count": bucket_metrics(rows, "visible_id_bucket"),
        }

    directions = Counter(row["paired_direction"] for row in paired_rows)
    metrics = {
        "schema_version": "t5-r04-dev-core-zero-training-metrics-v1",
        "status": "COMPLETE_MACHINE_EXACT_AND_DIAGNOSTIC_ONLY",
        "denominator": {"cases_per_arm": 48, "core_gold_facts": 95},
        "arm_metrics": arm_metrics,
        "paired": {
            "A_better_cases": directions["A_better"],
            "C2_better_cases": directions["C2_better"],
            "same_cases": directions["same"],
            "input_token_delta_z01_minus_z00": summarize(
                [row["input_token_delta_z01_minus_z00"] for row in paired_rows]
            ),
            "output_token_delta_z01_minus_z00": summarize(
                [row["output_token_delta_z01_minus_z00"] for row in paired_rows]
            ),
            "structured_exact_bootstrap": bootstrap_paired(paired_rows, "structured_exact_match"),
            "recoverable_exact_bootstrap": bootstrap_paired(paired_rows, "recoverable_exact_match"),
        },
        "stratification_availability": {
            "gold_fact_count": "AVAILABLE",
            "visible_id_count": "AVAILABLE",
            "gold_evidence_ids_count": "UNAVAILABLE_CORE_GOLD_HAS_NO_POSITION_PROVENANCE",
            "cross_unit_gold": "UNAVAILABLE_CORE_GOLD_HAS_NO_POSITION_PROVENANCE",
            "action": "DO_NOT_INFER_FROM_CROSS_UNIT_POSSIBLE_PROXY; keep Z03 pending",
        },
        "semantic_boundary": {
            "machine_score": "same-case normalized exact string matching only",
            "true_semantic_correctness": "BLIND_REVIEW_REQUIRED_NOT_AUTO_SCORED",
            "single_total_score_created": False,
        },
    }

    blind_rows, blind_key = [], []
    for case_id in order:
        digest = hashlib.sha256(f"dev-core-blind|{case_id}".encode()).digest()
        swap = digest[0] % 2 == 1
        mapping = {"X": "Z01", "Y": "Z00"} if swap else {"X": "Z00", "Y": "Z01"}
        raw_map = {
            arm: raw_by_arm[arm][order.index(case_id)]["raw_output"] for arm in ("Z00", "Z01")
        }
        blind_id = hashlib.sha256(f"blind|{case_id}".encode()).hexdigest()[:16]
        blind_rows.append(
            {
                "blind_id": blind_id,
                "case_id": case_id,
                "gold_fact_sentences": gold_by_id[case_id]["fact_sentences"],
                "output_X": raw_map[mapping["X"]],
                "output_Y": raw_map[mapping["Y"]],
                "review_fields": [
                    "semantic_precision_X_Y",
                    "semantic_recall_X_Y",
                    "cold_fact_overextraction_X_Y",
                    "notes",
                ],
            }
        )
        blind_key.append({"blind_id": blind_id, "case_id": case_id, **mapping})

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "CASE_METRICS.jsonl", case_rows)
    write_jsonl(args.output_dir / "PAIRED_CASE_METRICS.jsonl", paired_rows)
    write_json(args.output_dir / "ZERO_TRAINING_METRICS.json", metrics)
    write_jsonl(args.output_dir / "BLIND_REVIEW_QUEUE.jsonl", blind_rows)
    write_json(args.output_dir / "BLIND_KEY.json", blind_key)
    artifacts = {}
    for path in sorted(args.output_dir.iterdir()):
        if path.name == "SCORER_RECEIPT.json":
            continue
        artifacts[path.name] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    write_json(
        args.output_dir / "SCORER_RECEIPT.json",
        {
            "status": "PASS_DETERMINISTIC_SCORING_OUTPUT",
            "scorer_sha256": sha256(Path(__file__)),
            "raw_inputs": {
                "Z00": sha256(RUN / "arm_z00/RAW_OUTPUTS.jsonl"),
                "Z01": sha256(RUN / "arm_z01/RAW_OUTPUTS.jsonl"),
                "CORE_GOLD": sha256(SEALED / "CORE_GOLD.jsonl"),
            },
            "artifacts": artifacts,
        },
    )


if __name__ == "__main__":
    main()
