#!/usr/bin/env python3
"""Recoverable semantic scorer for the six READ Round1 variants."""

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
RUN_ROOT = REPO / "runs/T5_R04_READ_CONTEXT_ROUND1_LORA_DEMO_R01"
RAW = RUN_ROOT / "inference/RAW_OUTPUTS_144.jsonl"
GOLD = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01/REAL24_GOLD_24.jsonl"
TXX = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01/REAL24_TXX_MAP.jsonl"
SCHEMA = REPO / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
WO_SCORER = REPO / "finetuning/experiments/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_DEMO_RUN_20260808_R01/tools/score_demo.py"
VARIANTS = ("BASE_READ1", "BASE_READ2", "BASE_READ4", "LORA_READ1", "LORA_READ2", "LORA_READ4")
MAX_OUTPUT_TOKENS = 2048


def load_wo() -> Any:
    spec = importlib.util.spec_from_file_location("wo01_minimal_scorer", WO_SCORER)
    if spec is None or spec.loader is None:
        raise RuntimeError("WO01_SCORER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fact_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def repeated_chunk(raw: str) -> bool:
    compact = re.sub(r"\s+", "", raw)
    if len(compact) < 240:
        return False
    chunks = Counter(compact[index : index + 80] for index in range(0, len(compact) - 79, 8))
    return any(count >= 3 for count in chunks.values())


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
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def scan_fact_objects(raw: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    found: list[dict[str, Any]] = []
    for start, character in enumerate(raw):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("fact"), str) and value["fact"]:
            found.append(value)
    return found


def gold_map() -> dict[str, list[dict[str, Any]]]:
    rows = read_jsonl(GOLD)
    if [row["case_id"] for row in rows] != [f"C{i:02d}" for i in range(1, 25)]:
        raise RuntimeError("GOLD_CASE_ORDER_DRIFT")
    result = {}
    for row in rows:
        result[row["case_id"]] = [
            {
                "fact_id": f"{row['case_id']}-F{index:03d}",
                "fact": fact["fact_sentence"],
                "status": fact["status"],
                "speaker": fact["speaker"],
                "evidence_ids": fact["evidence_ids"],
            }
            for index, fact in enumerate(row["facts"], 1)
        ]
    return result


def recoverable_parse(raw: str, validator: Draft202012Validator) -> tuple[bool, bool, list[dict[str, Any]]]:
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError:
        return False, False, scan_fact_objects(raw)
    schema_valid = not list(validator.iter_errors(value))
    if not isinstance(value, dict) or not isinstance(value.get("facts"), list):
        return True, schema_valid, scan_fact_objects(raw)
    facts = [item for item in value["facts"] if isinstance(item, dict) and isinstance(item.get("fact"), str) and item["fact"]]
    return True, schema_valid, facts


def decisions(path: Path | None, raw_sha: str, gold_sha: str, gold: dict[str, list[dict[str, Any]]]) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None:
        return {}
    result = {}
    for row in read_jsonl(path):
        if row.get("raw_sha256") != raw_sha or row.get("gold_sha256") != gold_sha:
            raise RuntimeError("ADJUDICATION_IDENTITY_DRIFT")
        key = (row.get("case_id"), row.get("prediction_fact_sha256"))
        if key in result or fact_sha(row.get("prediction_fact", "")) != key[1]:
            raise RuntimeError("ADJUDICATION_DUPLICATE_OR_FACT_DRIFT")
        valid_ids = {item["fact_id"] for item in gold.get(key[0], [])}
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


def score(adjudication_path: Path | None) -> dict[str, Any]:
    wo = load_wo()
    raw_rows = read_jsonl(RAW)
    gold = gold_map()
    case_order = list(gold)
    if len(raw_rows) != 144 or Counter(row.get("variant") for row in raw_rows) != Counter({variant: 24 for variant in VARIANTS}):
        raise RuntimeError("RAW_NOT_SIX_BY_24")
    for variant in VARIANTS:
        if [row.get("case_id") for row in raw_rows if row.get("variant") == variant] != case_order:
            raise RuntimeError(f"RAW_CASE_ORDER_DRIFT:{variant}")
    raw_sha = sha256(RAW)
    gold_sha = sha256(GOLD)
    decision_index = decisions(adjudication_path, raw_sha, gold_sha, gold)
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    valid_ids = {row["case_id"]: {unit["id"] for unit in row["target_units"]} for row in read_jsonl(TXX)}
    pending: dict[tuple[str, str], dict[str, Any]] = {}
    case_metrics = []
    for row in raw_rows:
        case_id = row["case_id"]
        expected = gold[case_id]
        json_valid, schema_valid, predicted = recoverable_parse(row["raw_output"], validator)
        pairs, unmatched = wo.match(expected, predicted, normalized=True)
        used_gold = {gold_index for _, gold_index in pairs}
        out_of_scope = 0
        for prediction_index in unmatched:
            text = predicted[prediction_index].get("fact", "")
            key = (case_id, fact_sha(text))
            decision = decision_index.get(key)
            if decision is None:
                pending[key] = {
                    "case_id": case_id,
                    "prediction_fact": text,
                    "prediction_fact_sha256": key[1],
                    "raw_sha256": raw_sha,
                    "gold_sha256": gold_sha,
                    "candidate_gold_facts": [{"fact_id": item["fact_id"], "fact": item["fact"]} for item in expected],
                }
            elif decision["category"] == "SEMANTIC_EQUIVALENT":
                gold_index = next(index for index, item in enumerate(expected) if item["fact_id"] == decision["matched_gold_fact_id"])
                if gold_index not in used_gold:
                    pairs.append((prediction_index, gold_index))
                    used_gold.add(gold_index)
            elif decision["category"] == "OUT_OF_SCOPE":
                out_of_scope += 1
        status_ok = speaker_ok = evidence_ok = 0
        for prediction_index, gold_index in pairs:
            prediction = predicted[prediction_index]
            target = expected[gold_index]
            status_ok += prediction.get("status") == target["status"]
            speaker_ok += prediction.get("speaker") == target["speaker"]
            evidence_ok += prediction.get("evidence_ids") == target["evidence_ids"]
        illegal_evidence = sum(
            not isinstance(item.get("evidence_ids"), list)
            or any(evidence_id not in valid_ids[case_id] for evidence_id in item.get("evidence_ids", []))
            for item in predicted
        )
        duplicates = sum(count - 1 for count in Counter(item.get("fact") for item in predicted).values() if count > 1)
        case_metrics.append(
            {
                "variant": row["variant"],
                "arm": row["arm"],
                "case_id": case_id,
                "gold": len(expected),
                "predictions": len(predicted),
                "semantic_tp": len(pairs),
                "json_valid": json_valid,
                "schema_valid": schema_valid,
                "status_correct": status_ok,
                "speaker_correct": speaker_ok,
                "evidence_correct": evidence_ok,
                "illegal_evidence_predictions": illegal_evidence,
                "out_of_scope_predictions": out_of_scope,
                "duplicate_predictions": duplicates,
                "repetition_detected": duplicates > 0 or repeated_chunk(row["raw_output"]),
                "token_limit_hit": row.get("finish_reason") == "length" or row.get("generation_tokens_including_stop", 0) >= MAX_OUTPUT_TOKENS,
                "clean_stop": row.get("finish_reason") == "stop" and bool(row.get("stop_token_is_eos_eot")),
                "input_tokens": row.get("input_tokens"),
                "output_tokens": row.get("output_tokens_excluding_stop"),
            }
        )
    by_variant = {}
    for variant in VARIANTS:
        group = [row for row in case_metrics if row["variant"] == variant]
        tp = sum(row["semantic_tp"] for row in group)
        predictions = sum(row["predictions"] for row in group)
        gold_count = sum(row["gold"] for row in group)
        by_variant[variant] = {
            "semantic_recoverable": wo.prf(tp, predictions - tp, gold_count - tp),
            "json_valid_cases": sum(row["json_valid"] for row in group),
            "schema_valid_cases": sum(row["schema_valid"] for row in group),
            "status_correct": sum(row["status_correct"] for row in group),
            "speaker_correct": sum(row["speaker_correct"] for row in group),
            "evidence_correct": sum(row["evidence_correct"] for row in group),
            "illegal_evidence_predictions": sum(row["illegal_evidence_predictions"] for row in group),
            "out_of_scope_predictions": sum(row["out_of_scope_predictions"] for row in group),
            "duplicate_predictions": sum(row["duplicate_predictions"] for row in group),
            "repetition_cases": sum(row["repetition_detected"] for row in group),
            "token_limit_cases": sum(row["token_limit_hit"] for row in group),
            "clean_stop_cases": sum(row["clean_stop"] for row in group),
        }
    entity_diagnostics = []
    names = {"C06": ("九皇子", "哑奴"), "C18": ("谢珩", "陆骁", "赵飞龙")}
    for row in raw_rows:
        if row["case_id"] in names:
            hits = [name for name in names[row["case_id"]] if name in row["raw_output"]]
            entity_diagnostics.append({"variant": row["variant"], "case_id": row["case_id"], "resolved_name_mentions": hits})
    return {
        "status": "PASS_FINAL_SCORING" if adjudication_path is not None and not pending else "PENDING_BLIND_SEMANTIC_REVIEW",
        "raw_sha256": raw_sha,
        "gold_sha256": gold_sha,
        "gold_fact_count": sum(map(len, gold.values())),
        "semantic_pending": len(pending),
        "semantic_metric_is_final": adjudication_path is not None and not pending,
        "variants": by_variant,
        "case_metrics": case_metrics,
        "entity_resolution_diagnostic_only": entity_diagnostics,
        "blind_queue": list(pending.values()),
        "api_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("pre", "final"))
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    if args.command == "final" and args.adjudications is None:
        parser.error("final requires --adjudications")
    output = RUN_ROOT / ("scoring_final" if args.command == "final" else "scoring_pre")
    if output.exists():
        raise RuntimeError(f"SCORING_OUTPUT_EXISTS_NO_OVERWRITE:{output}")
    result = score(args.adjudications)
    output.mkdir(parents=True)
    queue = result.pop("blind_queue")
    write_json(output / "METRICS.json", result)
    write_jsonl(output / "BLIND_QUEUE.jsonl", queue)
    print(json.dumps({"status": result["status"], "semantic_pending": result["semantic_pending"], "gold_facts": result["gold_fact_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
