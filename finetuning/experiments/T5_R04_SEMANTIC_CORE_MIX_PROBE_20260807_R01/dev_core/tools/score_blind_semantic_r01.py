#!/usr/bin/env python3
"""Reveal the frozen blind key and score the completed local semantic review."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


DEV = Path(__file__).resolve().parents[1]
RESULTS = DEV / "zero_training_r01" / "results"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def parse_prediction_count(raw_output: str) -> int:
    parsed = json.loads(raw_output)
    facts = parsed.get("fact_sentences")
    if not isinstance(facts, list) or any(not isinstance(item, str) for item in facts):
        raise ValueError("blind output is not the frozen fact_sentences schema")
    return len(facts)


def finish(counts: dict[str, int]) -> dict[str, float | int]:
    matched_pred = counts["matched_prediction_facts"]
    predicted = counts["predicted_fact_count"]
    covered_gold = counts["covered_gold_facts"]
    gold = counts["gold_fact_count"]
    precision = matched_pred / predicted if predicted else (1.0 if gold == 0 else 0.0)
    recall = covered_gold / gold if gold else (1.0 if predicted == 0 else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        **counts,
        "unmatched_prediction_facts": predicted - matched_pred,
        "missed_gold_facts": gold - covered_gold,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def add(target: dict[str, int], source: dict[str, int]) -> None:
    for key in ("matched_prediction_facts", "predicted_fact_count", "covered_gold_facts", "gold_fact_count"):
        target[key] += source[key]


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def semantic_counts(gold_count: int, pred_count: int, matches: list[list[int]]) -> dict[str, int]:
    gold_indices = [int(pair[0]) for pair in matches]
    pred_indices = [int(pair[1]) for pair in matches]
    if any(index < 1 or index > gold_count for index in gold_indices):
        raise ValueError(f"gold match index outside 1..{gold_count}: {matches}")
    if any(index < 1 or index > pred_count for index in pred_indices):
        raise ValueError(f"prediction match index outside 1..{pred_count}: {matches}")
    if len(gold_indices) != len(set(gold_indices)):
        raise ValueError(f"one gold fact matched more than once: {matches}")
    matched_gold = len(set(gold_indices))
    matched_pred = len(set(pred_indices))
    return {
        "matched_prediction_facts": matched_pred,
        "predicted_fact_count": pred_count,
        "covered_gold_facts": matched_gold,
        "gold_fact_count": gold_count,
    }


def aggregate(rows: list[dict[str, Any]], arm: str) -> dict[str, float | int]:
    counts = {
        "matched_prediction_facts": 0,
        "predicted_fact_count": 0,
        "covered_gold_facts": 0,
        "gold_fact_count": 0,
    }
    for row in rows:
        add(counts, row[arm]["semantic_match"])
    return finish(counts)


def bootstrap(rows: list[dict[str, Any]], iterations: int = 10000) -> dict[str, Any]:
    rng = random.Random(20260807)
    deltas = {metric: [] for metric in ("precision", "recall", "f1")}
    for _ in range(iterations):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        metrics = {arm: aggregate(sample, arm) for arm in ("Z00", "Z01")}
        for metric in deltas:
            deltas[metric].append(metrics["Z01"][metric] - metrics["Z00"][metric])
    return {
        "iterations": iterations,
        "seed": 20260807,
        "delta_definition": "Z01_C2_minus_Z00_A",
        **{
            metric: {
                "mean": sum(values) / len(values),
                "ci95_low": percentile(values, 0.025),
                "ci95_high": percentile(values, 0.975),
            }
            for metric, values in deltas.items()
        },
    }


def bucket(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[field])].append(row)
    return {
        name: {
            "cases": len(group),
            "Z00_A": aggregate(group, "Z00"),
            "Z01_C2": aggregate(group, "Z01"),
        }
        for name, group in sorted(groups.items())
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    queue_path = RESULTS / "BLIND_REVIEW_QUEUE.jsonl"
    key_path = RESULTS / "BLIND_KEY.json"
    review_path = RESULTS / "BLIND_SEMANTIC_REVIEW_R01.jsonl"
    paired_path = RESULTS / "PAIRED_CASE_METRICS.jsonl"
    queue = read_jsonl(queue_path)
    key = read_json(key_path)
    reviews = read_jsonl(review_path)
    paired = read_jsonl(paired_path)
    queue_by_case = {row["case_id"]: row for row in queue}
    key_by_case = {row["case_id"]: row for row in key}
    review_by_case = {row["case_id"]: row for row in reviews}
    paired_by_case = {row["case_id"]: row for row in paired}
    case_ids = [row["case_id"] for row in queue]
    for label, mapping in (("key", key_by_case), ("review", review_by_case), ("paired", paired_by_case)):
        if set(mapping) != set(case_ids) or len(mapping) != len(case_ids):
            raise SystemExit(f"HARD_STOP {label} case set does not exactly match the blind queue")

    revealed: list[dict[str, Any]] = []
    for case_id in case_ids:
        queue_row = queue_by_case[case_id]
        review = review_by_case[case_id]
        key_row = key_by_case[case_id]
        gold_count = len(queue_row["gold_fact_sentences"])
        blind_counts = {
            label: semantic_counts(
                gold_count,
                parse_prediction_count(queue_row[f"output_{label}"]),
                review[label]["matches"],
            )
            for label in ("X", "Y")
        }
        arm_rows: dict[str, Any] = {}
        for label in ("X", "Y"):
            arm = key_row[label]
            arm_rows[arm] = {
                "blind_label": label,
                "matches": review[label]["matches"],
                "semantic_match": blind_counts[label],
                "case_metric": finish(blind_counts[label]),
                "predicted_fact_count": parse_prediction_count(queue_row[f"output_{label}"]),
            }
        paired_meta = paired_by_case[case_id]
        delta = arm_rows["Z01"]["case_metric"]["f1"] - arm_rows["Z00"]["case_metric"]["f1"]
        direction = "C2_better" if delta > 1e-12 else "A_better" if delta < -1e-12 else "same"
        revealed.append(
            {
                "case_id": case_id,
                "confidence": review["confidence"],
                "gold_fact_count": gold_count,
                "gold_fact_bucket": paired_meta["gold_fact_bucket"],
                "visible_id_count": paired_meta["visible_id_count"],
                "visible_id_bucket": paired_meta["visible_id_bucket"],
                "input_token_delta_z01_minus_z00": paired_meta["input_token_delta_z01_minus_z00"],
                "semantic_f1_delta_z01_minus_z00": delta,
                "paired_direction": direction,
                "Z00": arm_rows["Z00"],
                "Z01": arm_rows["Z01"],
            }
        )

    directions = {name: sum(row["paired_direction"] == name for row in revealed) for name in ("A_better", "C2_better", "same")}
    metrics = {
        "status": "PASS_LOCAL_BLIND_SEMANTIC_DIAGNOSTIC_SINGLE_REVIEWER",
        "scope": {
            "cases": len(revealed),
            "gold_facts": sum(row["gold_fact_count"] for row in revealed),
            "review_confidence": {
                "high": sum(row["confidence"] == "high" for row in revealed),
                "medium": sum(row["confidence"] == "medium" for row in revealed),
            },
        },
        "Z00_A": aggregate(revealed, "Z00"),
        "Z01_C2": aggregate(revealed, "Z01"),
        "paired": {
            **directions,
            "bootstrap_95ci": bootstrap(revealed),
        },
        "stratified": {
            "gold_fact_count": bucket(revealed, "gold_fact_bucket"),
            "visible_id_count": bucket(revealed, "visible_id_bucket"),
        },
        "unavailable_strata": {
            "gold_evidence_ids_count": "CORE_GOLD_HAS_NO_POSITION_PROVENANCE",
            "cross_unit_gold": "CORE_GOLD_HAS_NO_POSITION_PROVENANCE",
            "action": "DO_NOT_INFER_FROM_CROSS_UNIT_POSSIBLE_PROXY",
        },
        "interpretation_boundary": {
            "machine_exact": "separate deterministic same-case string score",
            "semantic_review": "single local blind diagnostic pass",
            "formal_A_vs_C2_winner_allowed": False,
            "second_independent_semantic_review_required_before_formal_win": True,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "BLIND_SEMANTIC_CASES.jsonl", revealed)
    write_json(args.output_dir / "BLIND_SEMANTIC_METRICS.json", metrics)
    write_json(
        args.output_dir / "BLIND_REVIEW_RECEIPT.json",
        {
            "status": "PASS_BLIND_REVIEW_REVEALED_AFTER_ANNOTATION",
            "inputs": {
                "blind_queue": {"sha256": sha256(queue_path), "bytes": queue_path.stat().st_size},
                "blind_key": {"sha256": sha256(key_path), "bytes": key_path.stat().st_size},
                "blind_review": {"sha256": sha256(review_path), "bytes": review_path.stat().st_size},
                "paired_machine_metrics": {"sha256": sha256(paired_path), "bytes": paired_path.stat().st_size},
            },
            "scorer_sha256": sha256(Path(__file__)),
            "outputs": {
                "BLIND_SEMANTIC_CASES.jsonl": sha256(args.output_dir / "BLIND_SEMANTIC_CASES.jsonl"),
                "BLIND_SEMANTIC_METRICS.json": sha256(args.output_dir / "BLIND_SEMANTIC_METRICS.json"),
            },
        },
    )


if __name__ == "__main__":
    main()
