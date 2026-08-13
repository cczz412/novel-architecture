#!/usr/bin/env python3
"""Thin recoverable semantic scorer for the READ1 TRAIN72 V2 qualification."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
SPEC_PATH = EXP / "RUN_SPEC.json"
RUNNER = EXP / "run_read1_train72_v2.py"
RUN_ROOT = REPO / "runs/T5_R04_READ1_TRAIN72_V2_QUALIFICATION_R01"
CORE_SCORER = (
    REPO
    / "finetuning/experiments/T5_R04_READ_CONTEXT_ROUND1_LORA_DEMO_20260809_R01"
    / "score_read_round1.py"
)
L6_ROOT = REPO / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01"
L6_GOLD = L6_ROOT / "L6_GOLD_6.jsonl"
L6_INDEX = L6_ROOT / "L6_SOURCE_INDEX.jsonl"
REAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
REAL_GOLD = REAL_ROOT / "REAL24_GOLD_24.jsonl"
REAL_TXX = REAL_ROOT / "REAL24_TXX_MAP.jsonl"
SCHEMA = (
    REPO
    / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01"
    / "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
)

CORE_SCORER_SHA = "476daaf478274ffb82a25e593b19523a43996047c495a1fee377da965a195fbf"
L6_GOLD_SHA = "79ab2bf95aef439d3183d6cb1df3a59f6a3f706275714974fd4ed256469ba579"
L6_INDEX_SHA = "d09841d845b6bc080cadc354f26947995353e404a254e77f0e7eef9be6969687"
REAL_GOLD_SHA = "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4"
REAL_TXX_SHA = "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a"
SCHEMA_SHA = "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14"
MAX_OUTPUT_TOKENS = 2048


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fact_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strict_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RuntimeError(f"DUPLICATE_JSON_KEY:{label}:{key}")
            result[key] = value
        return result

    value = json.loads(data.decode("utf-8", errors="strict"), object_pairs_hook=reject_duplicates)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{label}")
    return value


def read_json(path: Path) -> dict[str, Any]:
    return strict_json_bytes(path.read_bytes(), str(path))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for index, line in enumerate(path.read_bytes().splitlines(), 1):
        if line.strip():
            rows.append(strict_json_bytes(line, f"{path}:{index}"))
    return rows


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


def load_core() -> Any:
    if sha256(CORE_SCORER) != CORE_SCORER_SHA:
        raise RuntimeError("CORE_SCORER_SHA_DRIFT")
    spec = importlib.util.spec_from_file_location("read1_train72_v2_core", CORE_SCORER)
    if spec is None or spec.loader is None:
        raise RuntimeError("CORE_SCORER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def static_check() -> dict[str, Any]:
    spec = read_json(SPEC_PATH)
    fixed = {
        CORE_SCORER: CORE_SCORER_SHA,
        L6_GOLD: L6_GOLD_SHA,
        L6_INDEX: L6_INDEX_SHA,
        REAL_GOLD: REAL_GOLD_SHA,
        REAL_TXX: REAL_TXX_SHA,
        SCHEMA: SCHEMA_SHA,
    }
    for path, expected in fixed.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"SCORING_SOURCE_DRIFT:{path}")
    if sha256(Path(__file__)) != spec["components"]["scorer_sha256"]:
        raise RuntimeError("SCORER_SHA_DRIFT")
    if sha256(RUNNER) != spec["components"]["runner_sha256"]:
        raise RuntimeError("RUNNER_SHA_DRIFT")
    return {"status": "PASS", "model_loaded": False, "api_calls": 0}


def strict_output_parse(
    raw: str, validator: Draft202012Validator, core: Any
) -> tuple[bool, bool, list[dict[str, Any]]]:
    try:
        value = strict_json_bytes(raw.strip().encode("utf-8"), "model_output")
    except (json.JSONDecodeError, UnicodeDecodeError, RuntimeError):
        _, _, recovered = core.recoverable_parse(raw, validator)
        return False, False, recovered
    schema_valid = not list(validator.iter_errors(value))
    if not isinstance(value.get("facts"), list):
        _, _, recovered = core.recoverable_parse(raw, validator)
        return True, schema_valid, recovered
    facts = [
        item
        for item in value["facts"]
        if isinstance(item, dict) and isinstance(item.get("fact"), str) and item["fact"]
    ]
    return True, schema_valid, facts


def gold_and_units(dataset: str) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], Path]:
    if dataset == "l6":
        gold_path, units_path = L6_GOLD, L6_INDEX
        expected_cases = [f"LC-L{index:02d}" for index in range(1, 7)]
    else:
        gold_path, units_path = REAL_GOLD, REAL_TXX
        expected_cases = [f"C{index:02d}" for index in range(1, 25)]
    gold_rows = read_jsonl(gold_path)
    unit_rows = read_jsonl(units_path)
    if [row["case_id"] for row in gold_rows] != expected_cases:
        raise RuntimeError(f"GOLD_CASE_ORDER_DRIFT:{dataset}")
    unit_by_case = {row["case_id"]: row["target_units"] for row in unit_rows}
    if set(unit_by_case) != set(expected_cases):
        raise RuntimeError(f"TXX_CASE_SET_DRIFT:{dataset}")
    gold = {}
    for row in gold_rows:
        facts = []
        for index, fact in enumerate(row["facts"], 1):
            facts.append(
                {
                    "fact_id": fact.get("fact_id") or f"{row['case_id']}-F{index:03d}",
                    "fact": fact["fact_sentence"],
                    "status": fact["status"],
                    "speaker": fact["speaker"],
                    "evidence_ids": fact["evidence_ids"],
                }
            )
        gold[row["case_id"]] = facts
    return gold, unit_by_case, gold_path


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


def score(dataset: str, adjudications: Path | None) -> dict[str, Any]:
    static_check()
    core = load_core()
    wo = core.load_wo()
    gold, units, gold_path = gold_and_units(dataset)
    case_order = list(gold)
    raw_path = RUN_ROOT / f"inference/{'L6_RAW_12' if dataset == 'l6' else 'REAL24_RAW_48'}.jsonl"
    raw_rows = read_jsonl(raw_path)
    variants = (f"BASE_{dataset.upper()}", f"LORA_{dataset.upper()}")
    expected_each = 6 if dataset == "l6" else 24
    if len(raw_rows) != expected_each * 2 or Counter(row.get("variant") for row in raw_rows) != Counter(
        {variant: expected_each for variant in variants}
    ):
        raise RuntimeError(f"RAW_VARIANT_DENOMINATOR_DRIFT:{dataset}")
    for variant in variants:
        if [row.get("case_id") for row in raw_rows if row.get("variant") == variant] != case_order:
            raise RuntimeError(f"RAW_CASE_ORDER_DRIFT:{variant}")

    raw_sha = sha256(raw_path)
    gold_sha = sha256(gold_path)
    decisions = decision_index(adjudications, raw_sha, gold_sha, gold)
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    valid_ids = {case: {unit["id"] for unit in target_units} for case, target_units in units.items()}
    pending: dict[tuple[str, str], dict[str, Any]] = {}
    reviewed_keys: set[tuple[str, str]] = set()
    case_metrics = []
    for row in raw_rows:
        case_id = row["case_id"]
        expected = gold[case_id]
        json_valid, schema_valid, predicted = strict_output_parse(row["raw_output"], validator, core)
        pairs, unmatched = wo.match(expected, predicted, normalized=True)
        used_gold = {gold_index for _, gold_index in pairs}
        out_of_scope = 0
        for prediction_index in unmatched:
            text = predicted[prediction_index].get("fact", "")
            key = (case_id, fact_sha(text))
            reviewed_keys.add(key)
            decision = decisions.get(key)
            if decision is None:
                pending[key] = {
                    "case_id": case_id,
                    "prediction_fact": text,
                    "prediction_fact_sha256": key[1],
                    "raw_sha256": raw_sha,
                    "gold_sha256": gold_sha,
                    "candidate_gold_facts": [
                        {"fact_id": fact["fact_id"], "fact": fact["fact"]} for fact in expected
                    ],
                    "numbered_target": "".join(f"[{unit['id']}]{unit['text']}" for unit in units[case_id]),
                }
            elif decision["category"] == "SEMANTIC_EQUIVALENT":
                gold_index = next(
                    index
                    for index, fact in enumerate(expected)
                    if fact["fact_id"] == decision["matched_gold_fact_id"]
                )
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
        duplicate_predictions = sum(
            count - 1 for count in Counter(item.get("fact") for item in predicted).values() if count > 1
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
                "illegal_evidence_predictions": illegal_evidence,
                "out_of_scope_predictions": out_of_scope,
                "duplicate_predictions": duplicate_predictions,
                "repetition_detected": duplicate_predictions > 0 or core.repeated_chunk(row["raw_output"]),
                "token_limit_hit": row.get("token_limit_hit") is True
                or row.get("finish_reason") == "length"
                or row.get("generation_tokens_including_stop", 0) >= MAX_OUTPUT_TOKENS,
                "clean_stop": row.get("finish_reason") == "stop" and bool(row.get("stop_token_is_eos_eot")),
            }
        )
    if adjudications is not None and set(decisions) != reviewed_keys:
        raise RuntimeError("ADJUDICATION_COVERAGE_NOT_EXACT")

    by_variant = {}
    for variant in variants:
        group = [row for row in case_metrics if row["variant"] == variant]
        tp = sum(row["semantic_tp"] for row in group)
        predictions = sum(row["predictions"] for row in group)
        gold_count = sum(row["gold"] for row in group)
        by_variant[variant] = {
            "semantic_recoverable": wo.prf(tp, predictions - tp, gold_count - tp),
            "json_valid_cases": sum(row["json_valid"] for row in group),
            "schema_valid_cases": sum(row["schema_valid"] for row in group),
            "status_correct": sum(row["status_correct"] for row in group),
            "status_correct_rate_on_semantic_tp": round(
                sum(row["status_correct"] for row in group) / tp if tp else 0.0, 6
            ),
            "speaker_correct": sum(row["speaker_correct"] for row in group),
            "evidence_correct": sum(row["evidence_correct"] for row in group),
            "illegal_evidence_predictions": sum(row["illegal_evidence_predictions"] for row in group),
            "out_of_scope_predictions": sum(row["out_of_scope_predictions"] for row in group),
            "duplicate_predictions": sum(row["duplicate_predictions"] for row in group),
            "repetition_cases": sum(row["repetition_detected"] for row in group),
            "token_limit_cases": sum(row["token_limit_hit"] for row in group),
            "clean_stop_cases": sum(row["clean_stop"] for row in group),
            "empty_gold_case_prediction_counts": {
                row["case_id"]: row["predictions"] for row in group if row["gold"] == 0
            },
        }
    return {
        "status": "PASS_FINAL_SCORING" if adjudications is not None and not pending else "PENDING_BLIND_SEMANTIC_REVIEW",
        "dataset": dataset.upper(),
        "raw_sha256": raw_sha,
        "gold_sha256": gold_sha,
        "gold_fact_count": sum(map(len, gold.values())),
        "semantic_pending": len(pending),
        "semantic_metric_is_final": adjudications is not None and not pending,
        "variants": by_variant,
        "case_metrics": case_metrics,
        "blind_queue": list(pending.values()),
        "historical_reference": {"dense_train36_iter24_real24_f1": 0.428},
        "api_calls": 0,
    }


def gate(dataset: str, result: dict[str, Any]) -> dict[str, Any]:
    base = result["variants"][f"BASE_{dataset.upper()}"]
    lora = result["variants"][f"LORA_{dataset.upper()}"]
    lora_semantic = lora["semantic_recoverable"]
    base_semantic = base["semantic_recoverable"]
    if dataset == "l6":
        checks = {
            "json_6_of_6": lora["json_valid_cases"] == 6,
            "schema_6_of_6": lora["schema_valid_cases"] == 6,
            "illegal_evidence_zero": lora["illegal_evidence_predictions"] == 0,
            "repetition_zero": lora["repetition_cases"] == 0,
            "token_limit_zero": lora["token_limit_cases"] == 0,
            "duplicate_facts_zero": lora["duplicate_predictions"] == 0,
            "two_zero_cases_both_empty": lora["empty_gold_case_prediction_counts"]
            == {"LC-L01": 0, "LC-L02": 0},
            "nonempty_cases_not_all_empty": any(
                row["predictions"] > 0
                for row in result["case_metrics"]
                if row["variant"] == "LORA_L6" and row["gold"] > 0
            ),
            "lora_f1_not_below_same_contract_base": lora_semantic["f1"] >= base_semantic["f1"],
        }
    else:
        checks = {
            "schema_24_of_24": lora["schema_valid_cases"] == 24,
            "illegal_evidence_zero": lora["illegal_evidence_predictions"] == 0,
            "repetition_zero": lora["repetition_cases"] == 0,
            "token_limit_zero": lora["token_limit_cases"] == 0,
            "duplicate_facts_zero": lora["duplicate_predictions"] == 0,
            "lora_f1_strictly_above_same_contract_base": lora_semantic["f1"] > base_semantic["f1"],
            "lora_recall_not_below_same_contract_base": lora_semantic["recall"] >= base_semantic["recall"],
            "status_correct_on_tp_at_least_half": lora["status_correct_rate_on_semantic_tp"] >= 0.5,
        }
    return {
        "dataset": dataset.upper(),
        "pass": all(checks.values()),
        "checks": checks,
        "base_semantic": base_semantic,
        "lora_semantic": lora_semantic,
        "historical_dense_train36_iter24_real24_f1": 0.428,
        "run_spec_sha256": sha256(SPEC_PATH),
        "runner_sha256": sha256(RUNNER),
        "scorer_sha256": sha256(Path(__file__)),
    }


def run_command(dataset: str, final: bool, adjudications: Path | None) -> None:
    if final and adjudications is None:
        raise RuntimeError("FINAL_REQUIRES_ADJUDICATIONS")
    output = RUN_ROOT / f"scoring/{dataset}_{'final' if final else 'pre'}"
    if output.exists():
        raise RuntimeError(f"SCORING_OUTPUT_EXISTS_NO_OVERWRITE:{output}")
    result = score(dataset, adjudications if final else None)
    queue = result.pop("blind_queue")
    if final and (queue or result["semantic_pending"] != 0):
        raise RuntimeError("FINAL_SCORING_STILL_PENDING")
    output.mkdir(parents=True)
    write_json(output / "METRICS.json", result)
    write_jsonl(output / "BLIND_QUEUE.jsonl", queue)
    if final:
        gate_result = gate(dataset, result)
        write_json(output / ("L6_GATE.json" if dataset == "l6" else "REAL24_GATE.json"), gate_result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "dataset": dataset,
                "semantic_pending": result["semantic_pending"],
                "gate": gate(dataset, result)["pass"] if final else None,
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("static-check", "l6-pre", "l6-final", "real24-pre", "real24-final"))
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    if args.command == "static-check":
        print(json.dumps(static_check(), ensure_ascii=False, indent=2))
        return
    dataset = "l6" if args.command.startswith("l6-") else "real24"
    final = args.command.endswith("-final")
    run_command(dataset, final, args.adjudications)


if __name__ == "__main__":
    main()
