#!/usr/bin/env python3
"""Score only the ticketed TRAIN96 READ1 sample-mean L6 probe."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any
from zoneinfo import ZoneInfo


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
SPEC_PATH = EXP / "SPEC.json"
TRAIN96_PACKAGE = (
    REPO
    / "finetuning/experiments/"
    "T5_R04_READ1_TRAIN96_TOKEN_WEIGHTED_QUALIFICATION_20260810_R01"
)
TRAIN = TRAIN96_PACKAGE / "READ_1_TARGET_TRAIN96.jsonl"
TOKEN_STATS = TRAIN96_PACKAGE / "TRAIN96_TOKEN_STATS.json"
RUNNER = EXP / "run_train96_sample_mean.py"
RUN_ROOT = REPO / "runs/T5_R04_READ1_TRAIN96_SAMPLE_MEAN_QUALIFICATION_R01"
PARENT_SCORER = (
    REPO
    / "finetuning/experiments/"
    "T5_R04_READ1_TRAIN72_TOKEN_WEIGHTED_REDUCER_DIAGNOSTIC_20260810_R01/"
    "score_token_weighted_diagnostic.py"
)
PARENT_RUN = REPO / "runs/T5_R04_READ1_TRAIN72_V2_QUALIFICATION_R01"
PARENT_L6_RAW = PARENT_RUN / "inference/L6_RAW_12.jsonl"
L6_ROOT = (
    REPO
    / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01"
)
L6_GOLD = L6_ROOT / "L6_GOLD_6.jsonl"
L6_INDEX = L6_ROOT / "L6_SOURCE_INDEX.jsonl"
SCHEMA = (
    REPO
    / "finetuning/experiments/"
    "T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/"
    "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
)

EXPECTED = {
    "parent_scorer_sha256": "facdaafa689726104f0d408b235fe551190266a4a9f9641014460879f0e3293e",
    "parent_l6_raw_sha256": "e3c662cb87aaf8ba6862ce37c562de3752f554e2877079833da49e97dcf7646d",
    "base_l6_projection_sha256": "db5d40432a0849b78f3d5a09824251af4574002205b5221892bc9b32b3649476",
    "l6_gold_sha256": "79ab2bf95aef439d3183d6cb1df3a59f6a3f706275714974fd4ed256469ba579",
    "l6_index_sha256": "d09841d845b6bc080cadc354f26947995353e404a254e77f0e7eef9be6969687",
    "schema_sha256": "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14",
}
CASE_ORDER = [f"LC-L{i:02d}" for i in range(1, 7)]
LORA_VARIANT = "TRAIN96_SAMPLE_MEAN_LORA_L6"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def compact_jsonl(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    ).encode()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def project_parent_base() -> bytes:
    rows = [row for row in read_jsonl(PARENT_L6_RAW) if row.get("variant") == "BASE_L6"]
    if len(rows) != 6 or [row.get("case_id") for row in rows] != CASE_ORDER:
        raise RuntimeError("PARENT_BASE_L6_PROJECTION_DRIFT")
    payload = compact_jsonl(rows)
    if hashlib.sha256(payload).hexdigest() != EXPECTED["base_l6_projection_sha256"]:
        raise RuntimeError("PARENT_BASE_L6_PROJECTION_SHA_DRIFT")
    return payload


def lora_raw_path() -> Path:
    """Return this qualification run's own LoRA raw output path."""
    return RUN_ROOT / "inference/L6_TRAIN96_SAMPLE_MEAN_LORA_RAW_6.jsonl"


def static_check() -> dict[str, Any]:
    spec = read_json(SPEC_PATH)
    fixed = {
        TRAIN: spec["training_input"]["sha256"],
        TOKEN_STATS: spec["token_accounting"]["sha256"],
        PARENT_SCORER: EXPECTED["parent_scorer_sha256"],
        PARENT_L6_RAW: EXPECTED["parent_l6_raw_sha256"],
        L6_GOLD: EXPECTED["l6_gold_sha256"],
        L6_INDEX: EXPECTED["l6_index_sha256"],
        SCHEMA: EXPECTED["schema_sha256"],
    }
    for path, expected in fixed.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"SCORING_SOURCE_DRIFT:{path}")
    if sha256(Path(__file__)) != spec["components"]["scorer_sha256"]:
        raise RuntimeError("SCORER_SHA_DRIFT")
    if sha256(RUNNER) != spec["components"]["runner_sha256"]:
        raise RuntimeError("RUNNER_SHA_DRIFT")
    return {
        "status": "PASS_STATIC_PREPARED_NOT_RUN",
        "parent_base_rows": 6,
        "parent_base_projection_sha256": hashlib.sha256(project_parent_base()).hexdigest(),
        "run_root_exists": RUN_ROOT.exists(),
        "model_loaded": False,
        "api_calls": 0,
    }


def load_parent() -> Any:
    if sha256(PARENT_SCORER) != EXPECTED["parent_scorer_sha256"]:
        raise RuntimeError("PARENT_SCORER_SHA_DRIFT")
    module_spec = importlib.util.spec_from_file_location("train96_scoring_core", PARENT_SCORER)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("PARENT_SCORER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    module.EXP = EXP
    module.SPEC_PATH = SPEC_PATH
    module.RUNNER = RUNNER
    module.TRAIN = TRAIN
    module.RUN_ROOT = RUN_ROOT
    module.VARIANTS = ("BASE_L6", LORA_VARIANT)
    module.static_check = static_check
    module.runtime_rows = runtime_rows
    module.mechanical_report = mechanical_report
    return module


def runtime_rows() -> tuple[list[dict[str, Any]], str]:
    base_path = RUN_ROOT / "data/BASE_L6_REUSED.jsonl"
    lora_path = lora_raw_path()
    if not base_path.is_file() or base_path.read_bytes() != project_parent_base():
        raise RuntimeError("REUSED_BASE_L6_IDENTITY_DRIFT")
    base = read_jsonl(base_path)
    lora = read_jsonl(lora_path)
    if len(lora) != 6 or [row.get("case_id") for row in lora] != CASE_ORDER:
        raise RuntimeError("TRAIN96_LORA_L6_DENOMINATOR_OR_ORDER_DRIFT")
    if any(row.get("variant") != LORA_VARIANT for row in lora):
        raise RuntimeError("TRAIN96_LORA_L6_VARIANT_DRIFT")
    combined = compact_jsonl(base + lora)
    return base + lora, hashlib.sha256(combined).hexdigest()


def mechanical_report(parsed: list[dict[str, Any]], combined_sha: str) -> dict[str, Any]:
    lora = [row for row in parsed if row["variant"] == LORA_VARIANT]
    counts = {row["case_id"]: row["predictions"] for row in lora}
    checks = {
        "json_6_of_6": sum(row["json_valid"] for row in lora) == 6,
        "schema_6_of_6": sum(row["schema_valid"] for row in lora) == 6,
        "zero_cases_both_empty": counts.get("LC-L01") == 0 and counts.get("LC-L02") == 0,
        "four_nonempty_cases_each_nonempty": all(counts.get(f"LC-L{i:02d}", 0) >= 1 for i in range(3, 7)),
        "illegal_evidence_zero": sum(row["illegal_evidence_predictions"] for row in lora) == 0,
        "repetition_zero": sum(row["repetition_detected"] for row in lora) == 0,
        "token_limit_zero": sum(row["token_limit_hit"] for row in lora) == 0,
        "duplicate_facts_zero": sum(row["duplicate_predictions"] for row in lora) == 0,
    }
    raw = lora_raw_path()
    return {
        "status": "PASS_L6_MECHANICAL_GATE" if all(checks.values()) else "FAIL_L6_MECHANICAL_GATE",
        "pass": all(checks.values()),
        "checks": checks,
        "combined_raw_sha256": combined_sha,
        "train96_sample_mean_lora_raw_sha256": sha256(raw),
        "prediction_counts": counts,
        "json_valid_cases": sum(row["json_valid"] for row in lora),
        "schema_valid_cases": sum(row["schema_valid"] for row in lora),
        "illegal_evidence_predictions": sum(row["illegal_evidence_predictions"] for row in lora),
        "repetition_cases": sum(row["repetition_detected"] for row in lora),
        "token_limit_cases": sum(row["token_limit_hit"] for row in lora),
        "duplicate_predictions": sum(row["duplicate_predictions"] for row in lora),
    }


def semantic_score(
    parent: Any,
    parsed: list[dict[str, Any]],
    combined_sha: str,
    gold: dict[str, list[dict[str, Any]]],
    units: dict[str, list[dict[str, Any]]],
    adjudications: Path | None,
) -> dict[str, Any]:
    """Score this run's current raw without inheriting the parent's old filename."""
    core = parent.load_core()
    wo = core.load_wo()
    decisions = (
        parent.decision_index(adjudications, combined_sha, gold) if adjudications else {}
    )
    pending: dict[tuple[str, str], dict[str, Any]] = {}
    reviewed: set[tuple[str, str]] = set()
    case_metrics = []
    for row in parsed:
        case_id = row["case_id"]
        expected = gold[case_id]
        predicted = row["predicted"]
        pairs, unmatched = wo.match(expected, predicted, normalized=True)
        used_gold = {gold_index for _, gold_index in pairs}
        for prediction_index in unmatched:
            text = predicted[prediction_index].get("fact", "")
            key = (case_id, parent.fact_sha(text))
            reviewed.add(key)
            decision = decisions.get(key)
            if decision is None:
                pending[key] = {
                    "case_id": case_id,
                    "prediction_fact": text,
                    "prediction_fact_sha256": key[1],
                    "raw_sha256": combined_sha,
                    "gold_sha256": parent.L6_GOLD_SHA,
                    "candidate_gold_facts": [
                        {"fact_id": fact["fact_id"], "fact": fact["fact"]}
                        for fact in expected
                    ],
                    "numbered_target": "".join(
                        f"[{unit['id']}]{unit['text']}" for unit in units[case_id]
                    ),
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
        status_ok = speaker_ok = evidence_ok = 0
        for prediction_index, gold_index in pairs:
            prediction = predicted[prediction_index]
            target = expected[gold_index]
            status_ok += prediction.get("status") == target["status"]
            speaker_ok += prediction.get("speaker") == target["speaker"]
            evidence_ok += prediction.get("evidence_ids") == target["evidence_ids"]
        case_metrics.append(
            {
                "variant": row["variant"],
                "case_id": case_id,
                "gold": len(expected),
                "predictions": len(predicted),
                "semantic_tp": len(pairs),
                "json_valid": row["json_valid"],
                "schema_valid": row["schema_valid"],
                "status_correct": status_ok,
                "speaker_correct": speaker_ok,
                "evidence_correct": evidence_ok,
                "illegal_evidence_predictions": row["illegal_evidence_predictions"],
                "duplicate_predictions": row["duplicate_predictions"],
                "repetition_detected": row["repetition_detected"],
                "token_limit_hit": row["token_limit_hit"],
            }
        )
    if adjudications is not None and set(decisions) != reviewed:
        raise RuntimeError("ADJUDICATION_COVERAGE_NOT_EXACT")
    variants = {}
    for variant in ("BASE_L6", LORA_VARIANT):
        group = [row for row in case_metrics if row["variant"] == variant]
        tp = sum(row["semantic_tp"] for row in group)
        predictions = sum(row["predictions"] for row in group)
        gold_count = sum(row["gold"] for row in group)
        variants[variant] = {
            "semantic_recoverable": wo.prf(tp, predictions - tp, gold_count - tp),
            "json_valid_cases": sum(row["json_valid"] for row in group),
            "schema_valid_cases": sum(row["schema_valid"] for row in group),
            "status_correct": sum(row["status_correct"] for row in group),
            "status_correct_rate_on_semantic_tp": round(
                sum(row["status_correct"] for row in group) / tp if tp else 0.0, 6
            ),
            "speaker_correct": sum(row["speaker_correct"] for row in group),
            "evidence_correct": sum(row["evidence_correct"] for row in group),
            "illegal_evidence_predictions": sum(
                row["illegal_evidence_predictions"] for row in group
            ),
            "duplicate_predictions": sum(row["duplicate_predictions"] for row in group),
            "repetition_cases": sum(row["repetition_detected"] for row in group),
            "token_limit_cases": sum(row["token_limit_hit"] for row in group),
            "empty_gold_case_prediction_counts": {
                row["case_id"]: row["predictions"] for row in group if row["gold"] == 0
            },
        }
    return {
        "status": "PASS_FINAL_SCORING"
        if adjudications is not None and not pending
        else "PENDING_BLIND_SEMANTIC_REVIEW",
        "dataset": "L6",
        "qualification_identity": "TRAIN96_SAMPLE_MEAN",
        "combined_raw_sha256": combined_sha,
        "parent_l6_raw_sha256": EXPECTED["parent_l6_raw_sha256"],
        "train96_sample_mean_lora_raw_sha256": sha256(lora_raw_path()),
        "gold_sha256": parent.L6_GOLD_SHA,
        "gold_fact_count": 18,
        "semantic_pending": len(pending),
        "semantic_metric_is_final": adjudications is not None and not pending,
        "variants": variants,
        "case_metrics": case_metrics,
        "blind_queue": list(pending.values()),
        "api_calls": 0,
    }


def verify_pre_raw_identity(pre_gate: dict[str, Any], combined_sha: str) -> None:
    """Bind final scoring to the exact base+LoRA raw pair seen by l6-pre."""
    current_lora_sha = sha256(lora_raw_path())
    if pre_gate.get("combined_raw_sha256") != combined_sha:
        raise RuntimeError("L6_FINAL_COMBINED_RAW_SHA_DRIFT")
    if pre_gate.get("train96_sample_mean_lora_raw_sha256") != current_lora_sha:
        raise RuntimeError("L6_FINAL_LORA_RAW_SHA_DRIFT")


def run_pre() -> None:
    parent = load_parent()
    output = RUN_ROOT / "scoring/l6_pre"
    if output.exists():
        raise RuntimeError(f"SCORING_OUTPUT_EXISTS_NO_OVERWRITE:{output}")
    parsed, combined_sha, gold, units = parent.parsed_case_rows()
    mechanical = mechanical_report(parsed, combined_sha)
    output.mkdir(parents=True)
    parent.write_json(output / "L6_MECHANICAL_GATE.json", mechanical)
    if not mechanical["pass"]:
        parent.write_json(
            output / "METRICS.json",
            {
                "status": "FAIL_L6_MECHANICAL_GATE",
                "semantic_review_started": False,
                "semantic_metric_is_final": False,
                "mechanical_gate": mechanical,
                "api_calls": 0,
            },
        )
        parent.write_json(
            RUN_ROOT / "L6_MECHANICAL_FAIL_TICKET.json",
            {
                "schema_version": "read1-train96-sample-mean-l6-mechanical-fail/1.0",
                "status": "FAIL_L6_MECHANICAL_GATE",
                "stopped_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
                "run_id": RUN_ROOT.name,
                "failure_reason": [name for name, passed in mechanical["checks"].items() if not passed],
                "mechanical_summary": mechanical,
                "hard_stop": {
                    "blind_review_started": False,
                    "l6_final_run": False,
                    "real24_run": False,
                    "retry": 0,
                    "api_calls": 0,
                },
            },
        )
        print(json.dumps({"status": "FAIL_L6_MECHANICAL_GATE", "blind_queue_created": False}))
        return
    result = semantic_score(parent, parsed, combined_sha, gold, units, None)
    queue = result.pop("blind_queue")
    parent.write_json(output / "METRICS.json", result)
    parent.write_jsonl(output / "BLIND_QUEUE.jsonl", queue)
    print(json.dumps({"status": result["status"], "semantic_pending": result["semantic_pending"]}))


def run_final(adjudications: Path) -> None:
    parent = load_parent()
    pre_gate = RUN_ROOT / "scoring/l6_pre/L6_MECHANICAL_GATE.json"
    if not pre_gate.is_file():
        raise RuntimeError("L6_MECHANICAL_GATE_NOT_PASSED_FINAL_FORBIDDEN")
    frozen_pre_gate = read_json(pre_gate)
    if frozen_pre_gate.get("pass") is not True:
        raise RuntimeError("L6_MECHANICAL_GATE_NOT_PASSED_FINAL_FORBIDDEN")
    output = RUN_ROOT / "scoring/l6_final"
    if output.exists():
        raise RuntimeError(f"SCORING_OUTPUT_EXISTS_NO_OVERWRITE:{output}")
    parsed, combined_sha, gold, units = parent.parsed_case_rows()
    verify_pre_raw_identity(frozen_pre_gate, combined_sha)
    if not mechanical_report(parsed, combined_sha)["pass"]:
        raise RuntimeError("L6_FINAL_CURRENT_MECHANICAL_GATE_FAILED")
    result = semantic_score(parent, parsed, combined_sha, gold, units, adjudications)
    queue = result.pop("blind_queue")
    if queue or result["semantic_pending"] != 0:
        raise RuntimeError("FINAL_SCORING_STILL_PENDING")
    base = result["variants"]["BASE_L6"]["semantic_recoverable"]
    lora = result["variants"][LORA_VARIANT]["semantic_recoverable"]
    gate = {
        "dataset": "L6",
        "pass": lora["f1"] >= base["f1"],
        "check": "train96_lora_f1_not_below_same_contract_reused_base",
        "base_semantic": base,
        "train96_lora_semantic": lora,
        "real24_run": False,
    }
    output.mkdir(parents=True)
    parent.write_json(output / "METRICS.json", result)
    parent.write_jsonl(output / "BLIND_QUEUE.jsonl", [])
    parent.write_json(output / "L6_GATE.json", gate)
    print(json.dumps({"status": result["status"], "semantic_pending": 0, "gate": gate["pass"]}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("static-check", "l6-pre", "l6-final"))
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    if args.command == "static-check":
        print(json.dumps(static_check(), ensure_ascii=False, indent=2))
    elif args.command == "l6-pre":
        run_pre()
    else:
        if args.adjudications is None:
            parser.error("l6-final requires --adjudications")
        run_final(args.adjudications)


if __name__ == "__main__":
    main()
