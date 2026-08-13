#!/usr/bin/env python3
"""Score only the density-paired READ1 L6 qualification probe."""

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
SPEC_PATH = EXP / "DENSITY_PAIRED_SPEC.json"
RUNNER = EXP / "run_density_paired.py"
TRAIN = EXP / "READ_1_TARGET_TRAIN72_DENSITY_PAIRED.jsonl"
PAIR_MAP = EXP / "DENSITY_PAIR_MAP.json"
RUN_ROOT = REPO / "runs/T5_R04_READ1_TRAIN72_DENSITY_PAIRED_R01"
SOURCE_TRAIN = (
    REPO
    / "finetuning/experiments/T5_R04_READ_CONTEXT_TRAIN72_RENDER_CONTRACT_V2_20260809_R01"
    / "READ_1_TARGET_TRAIN72.jsonl"
)
PARENT_RUN = REPO / "runs/T5_R04_READ1_TRAIN72_V2_QUALIFICATION_R01"
PARENT_FAIL_TICKET = PARENT_RUN / "L6_MECHANICAL_FAIL_TICKET.json"
STAGE2_RUN = REPO / "runs/T5_R04_READ1_TRAIN72_LONG_SM12_STAGE2_R01"
STAGE2_FAIL_TICKET = STAGE2_RUN / "L6_MECHANICAL_FAIL_TICKET.json"
PARENT_L6_RAW = PARENT_RUN / "inference/L6_RAW_12.jsonl"
CORE_SCORER = (
    REPO
    / "finetuning/experiments/T5_R04_READ_CONTEXT_ROUND1_LORA_DEMO_20260809_R01"
    / "score_read_round1.py"
)
L6_ROOT = REPO / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01"
L6_GOLD = L6_ROOT / "L6_GOLD_6.jsonl"
L6_INDEX = L6_ROOT / "L6_SOURCE_INDEX.jsonl"
SCHEMA = (
    REPO
    / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01"
    / "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
)

TRAIN_SHA = "9c1a2202380f5c589d590a34354309643b1bb8fc0a12732184e11a282c924797"
PAIR_MAP_SHA = "5150d835085a92af6df6e9fe140fe82f0afab2e649d6b986a5ed3f146953bcdc"
SOURCE_TRAIN_SHA = "21213ae287d002351136b92c9caeb7388d2e71432574f9c8dcdf5ec1c3797f76"
PARENT_FAIL_TICKET_SHA = "d4bde13591bff46613f43a50d948b990bba20e5162889ae4e5deb0bb0c587b53"
STAGE2_FAIL_TICKET_SHA = "c2ccee02959307e291f3b38a3ba7882dfd6434d54c9539625e4d983aeb9d1c1a"
PARENT_L6_RAW_SHA = "e3c662cb87aaf8ba6862ce37c562de3752f554e2877079833da49e97dcf7646d"
CORE_SCORER_SHA = "476daaf478274ffb82a25e593b19523a43996047c495a1fee377da965a195fbf"
L6_GOLD_SHA = "79ab2bf95aef439d3183d6cb1df3a59f6a3f706275714974fd4ed256469ba579"
L6_INDEX_SHA = "d09841d845b6bc080cadc354f26947995353e404a254e77f0e7eef9be6969687"
SCHEMA_SHA = "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14"
MAX_OUTPUT_TOKENS = 2048
CASE_ORDER = [f"LC-L{i:02d}" for i in range(1, 7)]
VARIANTS = ("BASE_L6", "DENSITY_PAIRED_LORA_L6")


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
    return [
        strict_json_bytes(line, f"{path}:{index}")
        for index, line in enumerate(path.read_bytes().splitlines(), 1)
        if line.strip()
    ]


def compact_jsonl(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_bytes(compact_jsonl(rows))


def load_core() -> Any:
    if sha256(CORE_SCORER) != CORE_SCORER_SHA:
        raise RuntimeError("CORE_SCORER_SHA_DRIFT")
    module_spec = importlib.util.spec_from_file_location("density_paired_scoring_core", CORE_SCORER)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("CORE_SCORER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def project_parent_base() -> bytes:
    rows = [row for row in read_jsonl(PARENT_L6_RAW) if row.get("variant") == "BASE_L6"]
    if len(rows) != 6 or [row.get("case_id") for row in rows] != CASE_ORDER:
        raise RuntimeError("PARENT_BASE_L6_PROJECTION_DRIFT")
    return compact_jsonl(rows)


def static_check() -> dict[str, Any]:
    spec = read_json(SPEC_PATH)
    fixed = {
        TRAIN: TRAIN_SHA,
        PAIR_MAP: PAIR_MAP_SHA,
        SOURCE_TRAIN: SOURCE_TRAIN_SHA,
        PARENT_FAIL_TICKET: PARENT_FAIL_TICKET_SHA,
        STAGE2_FAIL_TICKET: STAGE2_FAIL_TICKET_SHA,
        PARENT_L6_RAW: PARENT_L6_RAW_SHA,
        CORE_SCORER: CORE_SCORER_SHA,
        L6_GOLD: L6_GOLD_SHA,
        L6_INDEX: L6_INDEX_SHA,
        SCHEMA: SCHEMA_SHA,
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


def gold_and_units() -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    gold_rows = read_jsonl(L6_GOLD)
    unit_rows = read_jsonl(L6_INDEX)
    if [row["case_id"] for row in gold_rows] != CASE_ORDER:
        raise RuntimeError("L6_GOLD_CASE_ORDER_DRIFT")
    units = {row["case_id"]: row["target_units"] for row in unit_rows}
    if set(units) != set(CASE_ORDER):
        raise RuntimeError("L6_TXX_CASE_SET_DRIFT")
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
    return gold, units


def runtime_rows() -> tuple[list[dict[str, Any]], str]:
    base_path = RUN_ROOT / "data/BASE_L6_REUSED.jsonl"
    lora_path = RUN_ROOT / "inference/L6_DENSITY_PAIRED_LORA_RAW_6.jsonl"
    if not base_path.is_file() or base_path.read_bytes() != project_parent_base():
        raise RuntimeError("REUSED_BASE_L6_IDENTITY_DRIFT")
    base = read_jsonl(base_path)
    lora = read_jsonl(lora_path)
    if len(lora) != 6 or [row.get("case_id") for row in lora] != CASE_ORDER:
        raise RuntimeError("DENSITY_PAIRED_LORA_L6_DENOMINATOR_OR_ORDER_DRIFT")
    if any(row.get("variant") != "DENSITY_PAIRED_LORA_L6" for row in lora):
        raise RuntimeError("DENSITY_PAIRED_LORA_L6_VARIANT_DRIFT")
    combined = compact_jsonl(base + lora)
    return base + lora, hashlib.sha256(combined).hexdigest()


def parsed_case_rows() -> tuple[
    list[dict[str, Any]],
    str,
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
]:
    static_check()
    core = load_core()
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    gold, units = gold_and_units()
    rows, combined_sha = runtime_rows()
    parsed = []
    for row in rows:
        case_id = row["case_id"]
        json_valid, schema_valid, predicted = strict_output_parse(row["raw_output"], validator, core)
        valid_ids = {unit["id"] for unit in units[case_id]}
        illegal = sum(
            not isinstance(item.get("evidence_ids"), list)
            or any(evidence_id not in valid_ids for evidence_id in item.get("evidence_ids", []))
            for item in predicted
        )
        duplicates = sum(
            count - 1 for count in Counter(item.get("fact") for item in predicted).values() if count > 1
        )
        parsed.append(
            {
                "variant": row["variant"],
                "case_id": case_id,
                "gold": len(gold[case_id]),
                "predicted": predicted,
                "predictions": len(predicted),
                "json_valid": json_valid,
                "schema_valid": schema_valid,
                "illegal_evidence_predictions": illegal,
                "duplicate_predictions": duplicates,
                "repetition_detected": duplicates > 0 or core.repeated_chunk(row["raw_output"]),
                "token_limit_hit": row.get("token_limit_hit") is True
                or row.get("finish_reason") == "length"
                or row.get("generation_tokens_including_stop", 0) >= MAX_OUTPUT_TOKENS,
            }
        )
    return parsed, combined_sha, gold, units


def mechanical_report(parsed: list[dict[str, Any]], combined_sha: str) -> dict[str, Any]:
    lora = [row for row in parsed if row["variant"] == "DENSITY_PAIRED_LORA_L6"]
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
    return {
        "status": "PASS_L6_MECHANICAL_GATE" if all(checks.values()) else "FAIL_L6_MECHANICAL_GATE",
        "pass": all(checks.values()),
        "checks": checks,
        "combined_raw_sha256": combined_sha,
        "parent_l6_raw_sha256": PARENT_L6_RAW_SHA,
        "density_paired_lora_raw_sha256": sha256(
            RUN_ROOT / "inference/L6_DENSITY_PAIRED_LORA_RAW_6.jsonl"
        ),
        "prediction_counts": counts,
        "json_valid_cases": sum(row["json_valid"] for row in lora),
        "schema_valid_cases": sum(row["schema_valid"] for row in lora),
        "illegal_evidence_predictions": sum(row["illegal_evidence_predictions"] for row in lora),
        "repetition_cases": sum(row["repetition_detected"] for row in lora),
        "token_limit_cases": sum(row["token_limit_hit"] for row in lora),
        "duplicate_predictions": sum(row["duplicate_predictions"] for row in lora),
    }


def decision_index(
    path: Path, combined_sha: str, gold: dict[str, list[dict[str, Any]]]
) -> dict[tuple[str, str], dict[str, Any]]:
    decisions = {}
    for row in read_jsonl(path):
        if row.get("raw_sha256") != combined_sha or row.get("gold_sha256") != L6_GOLD_SHA:
            raise RuntimeError("ADJUDICATION_IDENTITY_DRIFT")
        key = (row.get("case_id"), row.get("prediction_fact_sha256"))
        if key in decisions or fact_sha(row.get("prediction_fact", "")) != key[1]:
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
        decisions[key] = row
    return decisions


def semantic_score(
    parsed: list[dict[str, Any]],
    combined_sha: str,
    gold: dict[str, list[dict[str, Any]]],
    units: dict[str, list[dict[str, Any]]],
    adjudications: Path | None,
) -> dict[str, Any]:
    core = load_core()
    wo = core.load_wo()
    decisions = decision_index(adjudications, combined_sha, gold) if adjudications else {}
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
            key = (case_id, fact_sha(text))
            reviewed.add(key)
            decision = decisions.get(key)
            if decision is None:
                pending[key] = {
                    "case_id": case_id,
                    "prediction_fact": text,
                    "prediction_fact_sha256": key[1],
                    "raw_sha256": combined_sha,
                    "gold_sha256": L6_GOLD_SHA,
                    "candidate_gold_facts": [
                        {"fact_id": fact["fact_id"], "fact": fact["fact"]} for fact in expected
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
    for variant in VARIANTS:
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
            "illegal_evidence_predictions": sum(row["illegal_evidence_predictions"] for row in group),
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
        "combined_raw_sha256": combined_sha,
        "parent_l6_raw_sha256": PARENT_L6_RAW_SHA,
        "density_paired_lora_raw_sha256": sha256(
            RUN_ROOT / "inference/L6_DENSITY_PAIRED_LORA_RAW_6.jsonl"
        ),
        "gold_sha256": L6_GOLD_SHA,
        "gold_fact_count": 18,
        "semantic_pending": len(pending),
        "semantic_metric_is_final": adjudications is not None and not pending,
        "variants": variants,
        "case_metrics": case_metrics,
        "blind_queue": list(pending.values()),
        "api_calls": 0,
    }


def run_pre() -> None:
    output = RUN_ROOT / "scoring/l6_pre"
    if output.exists():
        raise RuntimeError(f"SCORING_OUTPUT_EXISTS_NO_OVERWRITE:{output}")
    parsed, combined_sha, gold, units = parsed_case_rows()
    mechanical = mechanical_report(parsed, combined_sha)
    output.mkdir(parents=True)
    write_json(output / "L6_MECHANICAL_GATE.json", mechanical)
    if not mechanical["pass"]:
        write_json(
            output / "METRICS.json",
            {
                "status": "FAIL_L6_MECHANICAL_GATE",
                "semantic_review_started": False,
                "semantic_metric_is_final": False,
                "mechanical_gate": mechanical,
                "api_calls": 0,
            },
        )
        print(json.dumps({"status": "FAIL_L6_MECHANICAL_GATE", "blind_queue_created": False}))
        return
    result = semantic_score(parsed, combined_sha, gold, units, None)
    queue = result.pop("blind_queue")
    write_json(output / "METRICS.json", result)
    write_jsonl(output / "BLIND_QUEUE.jsonl", queue)
    print(json.dumps({"status": result["status"], "semantic_pending": result["semantic_pending"]}))


def run_final(adjudications: Path) -> None:
    pre_gate = RUN_ROOT / "scoring/l6_pre/L6_MECHANICAL_GATE.json"
    if not pre_gate.is_file() or read_json(pre_gate).get("pass") is not True:
        raise RuntimeError("L6_MECHANICAL_GATE_NOT_PASSED_FINAL_FORBIDDEN")
    output = RUN_ROOT / "scoring/l6_final"
    if output.exists():
        raise RuntimeError(f"SCORING_OUTPUT_EXISTS_NO_OVERWRITE:{output}")
    parsed, combined_sha, gold, units = parsed_case_rows()
    result = semantic_score(parsed, combined_sha, gold, units, adjudications)
    queue = result.pop("blind_queue")
    if queue or result["semantic_pending"] != 0:
        raise RuntimeError("FINAL_SCORING_STILL_PENDING")
    base = result["variants"]["BASE_L6"]["semantic_recoverable"]
    lora = result["variants"]["DENSITY_PAIRED_LORA_L6"]["semantic_recoverable"]
    gate = {
        "dataset": "L6",
        "pass": lora["f1"] >= base["f1"],
        "check": "density_paired_lora_f1_not_below_same_contract_reused_base",
        "base_semantic": base,
        "density_paired_lora_semantic": lora,
        "spec_sha256": sha256(SPEC_PATH),
        "runner_sha256": sha256(RUNNER),
        "scorer_sha256": sha256(Path(__file__)),
        "real24_run": False,
    }
    output.mkdir(parents=True)
    write_json(output / "METRICS.json", result)
    write_jsonl(output / "BLIND_QUEUE.jsonl", [])
    write_json(output / "L6_GATE.json", gate)
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
