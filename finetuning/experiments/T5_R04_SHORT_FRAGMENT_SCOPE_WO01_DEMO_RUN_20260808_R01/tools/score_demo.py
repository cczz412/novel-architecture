#!/usr/bin/env python3
"""Minimal paired scorer for the WO-01 three-arm Demo."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import unicodedata

from jsonschema import Draft202012Validator


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
EXP = Path(__file__).resolve().parents[1]
RUN = REPO / "runs/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_DEMO_R01/full_72"
INPUT = REPO / "finetuning/experiments/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_PREFLIGHT_20260808_R01"
CANONICAL = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/set_b_r03_work/sealed/T5_R04_SYNTHETIC_MICRO24_SET_B_R03_20260808/canonical/CANONICAL_MICRO24_SET_B_R03.jsonl"
SCHEMA = REPO / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
ARMS = ("TARGET_ONLY", "SMALL_HALO", "CURRENT_WINDOW")
STATUS = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_bytes())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode() + b"\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_bytes(b"".join((json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode() for row in rows))


def normalize(text) -> str:
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKC", text)
    return "".join(char for char in text if not unicodedata.category(char).startswith(("P", "S", "Z")))


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 6), "recall": round(r, 6), "f1": round(f, 6)}


def canonical_map() -> dict:
    rows = read_jsonl(CANONICAL)
    if len(rows) != 24 or sum(len(row["facts"]) for row in rows) != 48:
        raise RuntimeError("DEV_DENOMINATOR_DRIFT")
    return {row["case_id"]: row for row in rows}


def gold(case: dict) -> list[dict]:
    return [{"fact_id": row["fact_id"], "fact": row["fact_sentence"], "status": row["status"], "speaker": row["speaker"], "evidence_ids": row["evidence"]["unit_ids"]} for row in case["facts"]]


def parse(raw: str) -> tuple[bool, list[dict]]:
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError:
        return False, []
    valid = not list(Draft202012Validator(read_json(SCHEMA)).iter_errors(value))
    return valid, value.get("facts", []) if valid else []


def match(gold_rows: list[dict], predictions: list[dict], *, normalized: bool) -> tuple[list[tuple[int, int]], list[int]]:
    key = (lambda value: normalize(value)) if normalized else (lambda value: value if isinstance(value, str) else "")
    pools = defaultdict(list)
    for index, row in enumerate(gold_rows):
        pools[key(row["fact"])].append(index)
    used, pairs, pending = set(), [], []
    for prediction_index, row in enumerate(predictions):
        candidates = [index for index in pools[key(row.get("fact"))] if index not in used]
        if key(row.get("fact")) and candidates:
            used.add(candidates[0])
            pairs.append((prediction_index, candidates[0]))
        else:
            pending.append(prediction_index)
    return pairs, pending


def adjudication_index(path: Path | None, raw_sha: str, canonical: dict) -> dict:
    if path is None:
        return {}
    index = {}
    for row in read_jsonl(path):
        if row.get("source_raw_sha256") != raw_sha:
            raise RuntimeError("ADJUDICATION_RAW_DRIFT")
        key = (row["case_id"], row["prediction_fact_sha256"])
        if key in index:
            raise RuntimeError("ADJUDICATION_DUPLICATE")
        if row["case_id"] not in canonical:
            raise RuntimeError("ADJUDICATION_UNKNOWN_CASE")
        if hashlib.sha256(row["prediction_fact"].encode()).hexdigest() != row["prediction_fact_sha256"]:
            raise RuntimeError("ADJUDICATION_FACT_SHA_DRIFT")
        valid_gold = {item["fact_id"] for item in canonical[row["case_id"]]["facts"]}
        if row["category"] == "SEMANTIC_EQUIVALENT":
            if row.get("matched_gold_fact_id") not in valid_gold:
                raise RuntimeError("ADJUDICATION_GOLD_BINDING_INVALID")
        elif row["category"] != "NOT_MATCH" or row.get("matched_gold_fact_id") is not None:
            raise RuntimeError("ADJUDICATION_CATEGORY_INVALID")
        index[key] = row
    return index


def score(raw_path: Path, adjudications: Path | None) -> dict:
    rows = read_jsonl(raw_path)
    canonical = canonical_map()
    case_order = list(canonical)
    if len(rows) != 72 or Counter(row["arm"] for row in rows) != Counter({arm: 24 for arm in ARMS}):
        raise RuntimeError("RAW_NOT_3X24")
    for arm in ARMS:
        if [row["case_id"] for row in rows if row["arm"] == arm] != case_order:
            raise RuntimeError("RAW_CASE_ORDER_DRIFT")
    raw_sha = sha256(raw_path)
    decisions = adjudication_index(adjudications, raw_sha, canonical)
    cases, pending = [], {}
    for row in rows:
        case = canonical[row["case_id"]]
        gold_rows = gold(case)
        schema_valid, predictions = parse(row["raw_output"])
        strict_pairs, _ = match(gold_rows, predictions, normalized=False)
        semantic_pairs, unmatched = match(gold_rows, predictions, normalized=True)
        used_gold = {gold_index for _, gold_index in semantic_pairs}
        for prediction_index in unmatched:
            fact = predictions[prediction_index].get("fact", "")
            fact_sha = hashlib.sha256(fact.encode()).hexdigest()
            decision = decisions.get((row["case_id"], fact_sha))
            if decision and decision["category"] == "SEMANTIC_EQUIVALENT":
                gold_index = next((index for index, item in enumerate(gold_rows) if item["fact_id"] == decision["matched_gold_fact_id"]), None)
                if gold_index is not None and gold_index not in used_gold:
                    semantic_pairs.append((prediction_index, gold_index))
                    used_gold.add(gold_index)
            elif decision is None:
                pending[(row["case_id"], fact_sha)] = {"case_id": row["case_id"], "prediction_fact": fact, "prediction_fact_sha256": fact_sha, "source_raw_sha256": raw_sha}
        status_ok = speaker_ok = evidence_ok = 0
        for prediction_index, gold_index in semantic_pairs:
            prediction, expected = predictions[prediction_index], gold_rows[gold_index]
            status_ok += prediction.get("status") == expected["status"]
            speaker_ok += prediction.get("speaker") == expected["speaker"]
            evidence_ok += prediction.get("evidence_ids") == expected["evidence_ids"]
        fact_strings = [item.get("fact") for item in predictions]
        duplicate = sum(count - 1 for count in Counter(fact_strings).values() if count > 1)
        cases.append({"arm": row["arm"], "case_id": row["case_id"], "gold": len(gold_rows), "predictions": len(predictions), "schema_valid": schema_valid, "strict_tp": len(strict_pairs), "semantic_tp": len(semantic_pairs), "status_correct": status_ok, "speaker_correct": speaker_ok, "evidence_correct": evidence_ok, "empty_false_positive": not gold_rows and bool(predictions), "duplicate_facts": duplicate, "token_limit_hit": row.get("finish_reason") == "length", "clean_stop": row.get("finish_reason") == "stop" and bool(row.get("stop_token_is_eos_eot")), "output_tokens": row.get("output_tokens")})
    by_arm = {}
    for arm in ARMS:
        group = [row for row in cases if row["arm"] == arm]
        gold_count, pred_count = sum(row["gold"] for row in group), sum(row["predictions"] for row in group)
        strict_tp, semantic_tp = sum(row["strict_tp"] for row in group), sum(row["semantic_tp"] for row in group)
        by_arm[arm] = {"semantic": prf(semantic_tp, pred_count - semantic_tp, gold_count - semantic_tp), "strict": prf(strict_tp, pred_count - strict_tp, gold_count - strict_tp), "schema_valid": sum(row["schema_valid"] for row in group), "status_correct": sum(row["status_correct"] for row in group), "speaker_correct": sum(row["speaker_correct"] for row in group), "evidence_correct": sum(row["evidence_correct"] for row in group), "semantic_matches": semantic_tp, "empty_false_positive_cases": sum(row["empty_false_positive"] for row in group), "duplicate_facts": sum(row["duplicate_facts"] for row in group), "token_limit_cases": sum(row["token_limit_hit"] for row in group), "clean_stop_cases": sum(row["clean_stop"] for row in group), "output_tokens": {"total": sum(row["output_tokens"] or 0 for row in group), "mean": round(sum(row["output_tokens"] or 0 for row in group) / 24, 3)}}
    return {"status": "PASS_FINAL_SCORING" if not pending else "PENDING_BLIND_SEMANTIC_REVIEW", "raw_sha256": raw_sha, "semantic_pending": len(pending), "arms": by_arm, "case_metrics": cases, "blind_queue": list(pending.values()), "model_called_by_scorer": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=RUN / "RAW_OUTPUTS.jsonl")
    parser.add_argument("--adjudications", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = score(args.raw, args.adjudications)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    queue = result.pop("blind_queue")
    write_json(args.output_dir / "METRICS.json", result)
    write_jsonl(args.output_dir / "BLIND_QUEUE.jsonl", queue)
    canonical = canonical_map()
    casebook = [{"case_id": case_id, "source": canonical[case_id]["source"], "gold": gold(canonical[case_id])} for case_id in sorted({row["case_id"] for row in queue})]
    write_jsonl(args.output_dir / "BLIND_CASEBOOK.jsonl", casebook)
    write_json(args.output_dir / "SCORING_RECEIPT.json", {"status": result["status"], "raw_sha256": result["raw_sha256"], "semantic_pending": result["semantic_pending"], "metrics_sha256": sha256(args.output_dir / "METRICS.json"), "blind_queue_sha256": sha256(args.output_dir / "BLIND_QUEUE.jsonl"), "api_calls": 0, "training_started": False})
    print(json.dumps({"status": result["status"], "semantic_pending": result["semantic_pending"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
