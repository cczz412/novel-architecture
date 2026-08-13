#!/usr/bin/env python3
"""Thin L6 and REAL24 scorer for the READ1 TRAIN48 mixed sentinel."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any

from jsonschema import Draft202012Validator


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs/T5_R04_READ1_TRAIN48_MIXED_SENTINEL_R01"
ROUND_SCORER = REPO / "finetuning/experiments/T5_R04_READ_CONTEXT_ROUND1_LORA_DEMO_20260809_R01/score_read_round1.py"
OLD_RAW = REPO / "runs/T5_R04_READ_CONTEXT_ROUND1_LORA_DEMO_R01/inference/RAW_OUTPUTS_144.jsonl"
OLD_ADJUDICATIONS = REPO / "runs/T5_R04_READ_CONTEXT_ROUND1_LORA_DEMO_R01/semantic_review/SEMANTIC_ADJUDICATIONS_1536.jsonl"
L6_GOLD = REPO / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/L6_GOLD_6.jsonl"
L6_INDEX = REPO / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/L6_SOURCE_INDEX.jsonl"
SCHEMA = REPO / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
REAL_TXX = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01/REAL24_TXX_MAP.jsonl"
EXPECTED_SHA = {
    ROUND_SCORER: "476daaf478274ffb82a25e593b19523a43996047c495a1fee377da965a195fbf",
    OLD_RAW: "705f1e0df1088aa32ae6e26e9d38dcb86d92226a6fe3b5089033266c2ce2eec4",
    OLD_ADJUDICATIONS: "5a3c3fe864d78711bc281de055f6405f13aaf142da3a4bd4c181cf7497d9b581",
    L6_GOLD: "79ab2bf95aef439d3183d6cb1df3a59f6a3f706275714974fd4ed256469ba579",
    L6_INDEX: "d09841d845b6bc080cadc354f26947995353e404a254e77f0e7eef9be6969687",
}
MAX_OUTPUT_TOKENS = 2048


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fact_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def load_round_scorer() -> Any:
    for path, expected in EXPECTED_SHA.items():
        if sha256(path) != expected:
            raise RuntimeError(f"SCORING_SOURCE_DRIFT:{path}")
    spec = importlib.util.spec_from_file_location("round1_scorer_for_mixed", ROUND_SCORER)
    if spec is None or spec.loader is None:
        raise RuntimeError("ROUND_SCORER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def repeated_chunk(raw: str) -> bool:
    compact = re.sub(r"\s+", "", raw)
    if len(compact) < 240:
        return False
    chunks = Counter(compact[index : index + 80] for index in range(0, len(compact) - 79, 8))
    return any(count >= 3 for count in chunks.values())


def l6_gold_map() -> dict[str, list[dict[str, Any]]]:
    rows = read_jsonl(L6_GOLD)
    if [row["case_id"] for row in rows] != [f"LC-L{index:02d}" for index in range(1, 7)]:
        raise RuntimeError("L6_GOLD_ORDER_DRIFT")
    return {
        row["case_id"]: [
            {
                "fact_id": fact["fact_id"],
                "fact": fact["fact_sentence"],
                "status": fact["status"],
                "speaker": fact["speaker"],
                "evidence_ids": fact["evidence_ids"],
            }
            for fact in row["facts"]
        ]
        for row in rows
    }


def decision_index(
    path: Path | None,
    raw_sha: str,
    gold_sha: str,
    gold: dict[str, list[dict[str, Any]]],
) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None:
        return {}
    result = {}
    for row in read_jsonl(path):
        if row.get("raw_sha256") != raw_sha or row.get("gold_sha256") != gold_sha:
            raise RuntimeError("ADJUDICATION_IDENTITY_DRIFT")
        key = (row.get("case_id"), row.get("prediction_fact_sha256"))
        if key in result or fact_sha(row.get("prediction_fact", "")) != key[1]:
            raise RuntimeError("ADJUDICATION_DUPLICATE_OR_FACT_DRIFT")
        valid_ids = {fact["fact_id"] for fact in gold.get(key[0], [])}
        category = row.get("category")
        matched = row.get("matched_gold_fact_id")
        if category == "SEMANTIC_EQUIVALENT" and matched not in valid_ids:
            raise RuntimeError("ADJUDICATION_GOLD_ID_INVALID")
        if category in {"NOT_MATCH", "OUT_OF_SCOPE"} and matched is not None:
            raise RuntimeError("ADJUDICATION_CATEGORY_INVALID")
        if category not in {"SEMANTIC_EQUIVALENT", "NOT_MATCH", "OUT_OF_SCOPE"}:
            raise RuntimeError("ADJUDICATION_CATEGORY_UNKNOWN")
        result[key] = row
    return result


def build_l6_raw(step: int, output: Path) -> list[dict[str, Any]]:
    initial = read_jsonl(RUN / "INITIAL_RAW.jsonl")
    variants = ["BASE_L6", "DENSE24_L6", f"MIXED{step}_L6"]
    rows = [row for row in initial if row["variant"] in variants]
    if step != 96:
        rows = [row for row in rows if row["variant"] != f"MIXED{step}_L6"]
        probe = RUN / ("FALLBACK72_RAW.jsonl" if step == 72 else f"PROBE{step}_RAW.jsonl")
        rows.extend(row for row in read_jsonl(probe) if row["variant"] == f"MIXED{step}_L6")
    case_order = [f"LC-L{index:02d}" for index in range(1, 7)]
    by_key = {(row["variant"], row["case_id"]): row for row in rows}
    canonical = [by_key[variant, case] for variant in variants for case in case_order]
    write_jsonl(output, canonical)
    return canonical


def score_l6(step: int, adjudications: Path | None) -> dict[str, Any]:
    scoring_dir = RUN / f"scoring/l6_step{step}"
    raw_path = scoring_dir / "L6_RAW_18.jsonl"
    if not raw_path.exists():
        raw_rows = build_l6_raw(step, raw_path)
    else:
        raw_rows = read_jsonl(raw_path)
    round_scorer = load_round_scorer()
    wo = round_scorer.load_wo()
    gold = l6_gold_map()
    case_order = list(gold)
    variants = ("BASE_L6", "DENSE24_L6", f"MIXED{step}_L6")
    if len(raw_rows) != 18 or Counter(row["variant"] for row in raw_rows) != Counter({variant: 6 for variant in variants}):
        raise RuntimeError("L6_RAW_NOT_THREE_BY_SIX")
    for variant in variants:
        if [row["case_id"] for row in raw_rows if row["variant"] == variant] != case_order:
            raise RuntimeError(f"L6_CASE_ORDER_DRIFT:{variant}")
    raw_sha = sha256(raw_path)
    gold_sha = sha256(L6_GOLD)
    decisions = decision_index(adjudications, raw_sha, gold_sha, gold)
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    source = {row["case_id"]: row for row in read_jsonl(L6_INDEX)}
    valid_ids = {case: {unit["id"] for unit in row["target_units"]} for case, row in source.items()}
    pending: dict[tuple[str, str], dict[str, Any]] = {}
    case_metrics = []
    for row in raw_rows:
        case_id = row["case_id"]
        expected = gold[case_id]
        json_valid, schema_valid, predicted = round_scorer.recoverable_parse(row["raw_output"], validator)
        pairs, unmatched = wo.match(expected, predicted, normalized=True)
        used_gold = {gold_index for _, gold_index in pairs}
        for prediction_index in unmatched:
            text = predicted[prediction_index].get("fact", "")
            key = (case_id, fact_sha(text))
            decision = decisions.get(key)
            if decision is None:
                pending[key] = {
                    "case_id": case_id,
                    "prediction_fact": text,
                    "prediction_fact_sha256": key[1],
                    "raw_sha256": raw_sha,
                    "gold_sha256": gold_sha,
                    "candidate_gold_facts": [{"fact_id": fact["fact_id"], "fact": fact["fact"]} for fact in expected],
                    "numbered_target": "".join(f"[{unit['id']}]{unit['text']}" for unit in source[case_id]["target_units"]),
                }
            elif decision["category"] == "SEMANTIC_EQUIVALENT":
                gold_index = next(index for index, fact in enumerate(expected) if fact["fact_id"] == decision["matched_gold_fact_id"])
                if gold_index not in used_gold:
                    pairs.append((prediction_index, gold_index))
                    used_gold.add(gold_index)
        status_ok = speaker_ok = evidence_ok = 0
        for prediction_index, gold_index in pairs:
            prediction = predicted[prediction_index]
            target = expected[gold_index]
            status_ok += prediction.get("status") == target["status"]
            speaker_ok += prediction.get("speaker") == target["speaker"]
            evidence_ok += prediction.get("evidence_ids") == target["evidence_ids"]
        duplicates = sum(count - 1 for count in Counter(item.get("fact") for item in predicted).values() if count > 1)
        illegal = sum(
            not isinstance(item.get("evidence_ids"), list)
            or any(evidence_id not in valid_ids[case_id] for evidence_id in item.get("evidence_ids", []))
            for item in predicted
        )
        case_metrics.append(
            {
                "variant": row["variant"],
                "case_id": case_id,
                "gold": len(expected),
                "predictions": len(predicted),
                "semantic_tp": len(pairs),
                "json_valid": json_valid,
                "schema_valid": schema_valid,
                "status_correct": status_ok,
                "speaker_correct": speaker_ok,
                "evidence_correct": evidence_ok,
                "illegal_evidence_predictions": illegal,
                "duplicate_predictions": duplicates,
                "repetition_detected": duplicates > 0 or repeated_chunk(row["raw_output"]),
                "token_limit_hit": row.get("token_limit_hit") is True,
                "clean_stop": row.get("finish_reason") == "stop" and bool(row.get("stop_token_is_eos_eot")),
            }
        )
    by_variant = {}
    for variant in variants:
        group = [row for row in case_metrics if row["variant"] == variant]
        tp = sum(row["semantic_tp"] for row in group)
        predictions = sum(row["predictions"] for row in group)
        gold_count = sum(row["gold"] for row in group)
        by_variant[variant] = {
            "semantic_recoverable": wo.prf(tp, predictions - tp, gold_count - tp),
            "zero_case_prediction_counts": {row["case_id"]: row["predictions"] for row in group if row["gold"] == 0},
            "json_valid_cases": sum(row["json_valid"] for row in group),
            "schema_valid_cases": sum(row["schema_valid"] for row in group),
            "status_correct": sum(row["status_correct"] for row in group),
            "speaker_correct": sum(row["speaker_correct"] for row in group),
            "evidence_correct": sum(row["evidence_correct"] for row in group),
            "illegal_evidence_predictions": sum(row["illegal_evidence_predictions"] for row in group),
            "duplicate_predictions": sum(row["duplicate_predictions"] for row in group),
            "repetition_cases": sum(row["repetition_detected"] for row in group),
            "token_limit_cases": sum(row["token_limit_hit"] for row in group),
            "clean_stop_cases": sum(row["clean_stop"] for row in group),
        }
    return {
        "status": "PASS_FINAL_SCORING" if adjudications is not None and not pending else "PENDING_BLIND_SEMANTIC_REVIEW",
        "evaluation_scope": "READ1_UNSEEN_FACT_DENSITY_ONLY_NOT_CONTEXT_RANGE_COMPARISON",
        "forbidden_from_training": True,
        "raw_sha256": raw_sha,
        "gold_sha256": gold_sha,
        "gold_fact_count": sum(map(len, gold.values())),
        "semantic_pending": len(pending),
        "semantic_metric_is_final": adjudications is not None and not pending,
        "variants": by_variant,
        "case_metrics": case_metrics,
        "blind_queue": list(pending.values()),
        "api_calls": 0,
    }


def l6_command(step: int, final: bool, adjudications: Path | None) -> None:
    output = RUN / f"scoring/l6_step{step}" / ("FINAL_METRICS.json" if final else "PRE_METRICS.json")
    queue_path = RUN / f"scoring/l6_step{step}" / ("FINAL_PENDING.jsonl" if final else "BLIND_QUEUE.jsonl")
    if output.exists() or queue_path.exists():
        raise RuntimeError("L6_SCORING_OUTPUT_EXISTS_NO_OVERWRITE")
    result = score_l6(step, adjudications if final else None)
    queue = result.pop("blind_queue")
    write_json(output, result)
    write_jsonl(queue_path, queue)
    if final and (queue or result["semantic_pending"] != 0):
        raise RuntimeError("L6_FINAL_STILL_PENDING")
    print(json.dumps({"status": result["status"], "semantic_pending": result["semantic_pending"]}, ensure_ascii=False))


def gate(step: int) -> None:
    metrics = json.loads((RUN / f"scoring/l6_step{step}/FINAL_METRICS.json").read_text(encoding="utf-8"))
    mixed_name = f"MIXED{step}_L6"
    base = metrics["variants"]["BASE_L6"]["semantic_recoverable"]
    dense = metrics["variants"]["DENSE24_L6"]["semantic_recoverable"]
    mixed = metrics["variants"][mixed_name]["semantic_recoverable"]
    raw_path = RUN / (
        "INITIAL_RAW.jsonl"
        if step == 96
        else "FALLBACK72_RAW.jsonl"
        if step == 72
        else f"PROBE{step}_RAW.jsonl"
    )
    raw_rows = read_jsonl(raw_path)
    allowed_variants = {mixed_name, f"MIXED{step}_REAL_SENTINEL"}
    observed = [row for row in raw_rows if row["variant"] in allowed_variants]
    if len(observed) != 14:
        raise RuntimeError("GATE_NOT_14_ROWS")
    zero_counts = metrics["variants"][mixed_name]["zero_case_prediction_counts"]
    checks = {
        "fourteen_rows_no_repetition": sum(row["repetition_detected"] for row in observed) == 0,
        "fourteen_rows_no_token_limit": sum(row["token_limit_hit"] for row in observed) == 0,
        "both_zero_cases_have_zero_predictions": zero_counts == {"LC-L01": 0, "LC-L02": 0},
        "l6_f1_not_below_base": mixed["f1"] >= base["f1"],
        "l6_f1_not_below_dense24": mixed["f1"] >= dense["f1"],
        "l6_fp_not_above_base": mixed["fp"] <= base["fp"],
        "l6_fp_not_above_dense24": mixed["fp"] <= dense["fp"],
    }
    write_json(
        RUN / f"GATE_{step}.json",
        {
            "step": step,
            "pass": all(checks.values()),
            "checks": checks,
            "stability": {
                "repetition_rows": sum(row["repetition_detected"] for row in observed),
                "token_limit_rows": sum(row["token_limit_hit"] for row in observed),
                "duplicate_facts": sum(row["duplicate_facts"] for row in observed),
            },
            "l6": {"base": base, "dense24": dense, "mixed": mixed},
        },
    )
    print(json.dumps({"step": step, "pass": all(checks.values()), "checks": checks}, ensure_ascii=False))


def prepare_real(step: int) -> tuple[Path, Path, Path]:
    full_raw = RUN / f"REAL24_MIXED{step}.jsonl"
    new_rows = read_jsonl(full_raw)
    if len(new_rows) != 24:
        raise RuntimeError("REAL24_MIXED_NOT_24")
    new_by_case = {row["case_id"]: {**row, "variant": "LORA_READ1"} for row in new_rows}
    old_rows = read_jsonl(OLD_RAW)
    shadow = [new_by_case[row["case_id"]] if row["variant"] == "LORA_READ1" else row for row in old_rows]
    out = RUN / f"scoring/real_step{step}"
    shadow_path = out / "SHADOW_RAW_144.jsonl"
    inherited_path = out / "INHERITED_ADJUDICATIONS.jsonl"
    write_jsonl(shadow_path, shadow)
    shadow_sha = sha256(shadow_path)
    inherited = [{**row, "raw_sha256": shadow_sha} for row in read_jsonl(OLD_ADJUDICATIONS)]
    write_jsonl(inherited_path, inherited)
    return out, shadow_path, inherited_path


def real_pre(step: int) -> None:
    out, shadow, inherited = prepare_real(step)
    scorer = load_round_scorer()
    scorer.RAW = shadow
    result = scorer.score(inherited)
    queue = result.pop("blind_queue")
    target_map = {row["case_id"]: row for row in read_jsonl(REAL_TXX)}
    for row in queue:
        row["numbered_target"] = "".join(f"[{unit['id']}]{unit['text']}" for unit in target_map[row["case_id"]]["target_units"])
    write_json(out / "PRE_METRICS.json", result)
    write_jsonl(out / "BLIND_QUEUE_INCREMENTAL.jsonl", queue)
    print(json.dumps({"semantic_pending": len(queue), "shadow_raw_sha256": sha256(shadow)}, ensure_ascii=False))


def real_final(step: int, adjudications: Path) -> None:
    out = RUN / f"scoring/real_step{step}"
    shadow = out / "SHADOW_RAW_144.jsonl"
    inherited = out / "INHERITED_ADJUDICATIONS.jsonl"
    queue = read_jsonl(out / "BLIND_QUEUE_INCREMENTAL.jsonl")
    incremental = read_jsonl(adjudications)
    expected = {(row["case_id"], row["prediction_fact_sha256"]) for row in queue}
    actual = {(row.get("case_id"), row.get("prediction_fact_sha256")) for row in incremental}
    if actual != expected or len(incremental) != len(expected):
        raise RuntimeError("REAL_INCREMENTAL_ADJUDICATION_COVERAGE_MISMATCH")
    combined = out / "COMBINED_ADJUDICATIONS.jsonl"
    write_jsonl(combined, read_jsonl(inherited) + incremental)
    scorer = load_round_scorer()
    scorer.RAW = shadow
    result = scorer.score(combined)
    pending = result.pop("blind_queue")
    if pending or result["semantic_pending"] != 0:
        raise RuntimeError("REAL_FINAL_STILL_PENDING")
    write_json(out / "FINAL_METRICS.json", result)
    print(json.dumps({"status": result["status"], "semantic_pending": 0}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("l6-pre", "l6-final", "gate", "real-pre", "real-final"),
    )
    parser.add_argument("--step", type=int, required=True, choices=(24, 48, 72, 96))
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    if args.command in {"l6-final", "real-final"} and args.adjudications is None:
        parser.error(f"{args.command} requires --adjudications")
    if args.command == "l6-pre":
        l6_command(args.step, final=False, adjudications=None)
    elif args.command == "l6-final":
        l6_command(args.step, final=True, adjudications=args.adjudications)
    elif args.command == "gate":
        gate(args.step)
    elif args.command == "real-pre":
        real_pre(args.step)
    else:
        real_final(args.step, args.adjudications)


if __name__ == "__main__":
    main()
