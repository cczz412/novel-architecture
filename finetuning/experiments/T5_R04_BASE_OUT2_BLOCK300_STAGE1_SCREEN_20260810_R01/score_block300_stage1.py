#!/usr/bin/env python3
"""Mechanical gate and responsibility-aware semantic scoring for BLOCK300 Stage1."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any

from jsonschema import Draft202012Validator


sys.dont_write_bytecode = True
RUNNER_PATH = Path(__file__).resolve().parent / "run_block300_stage1.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("block300_stage1_runner", RUNNER_PATH)
if RUNNER_SPEC is None or RUNNER_SPEC.loader is None:
    raise RuntimeError("RUNNER_IMPORT_FAILED")
runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(runner)
RUN_ROOT = runner.RUN_ROOT
RAW = RUN_ROOT / "inference/BLOCK300_STAGE1_RAW_22.jsonl"
RESULT = RUN_ROOT / "inference/BLOCK300_STAGE1_RESULT.json"
IDENTITY = RUN_ROOT / "RUN_IDENTITY.json"
TICKET = RUN_ROOT / "AUTHORIZATION_TICKET.json"
PRE_METRICS = RUN_ROOT / "scoring/pre/METRICS.json"
PRE_QUEUE = RUN_ROOT / "scoring/pre/BLIND_QUEUE.jsonl"
FINAL_METRICS = RUN_ROOT / "scoring/final/METRICS.json"
FINAL_QUEUE = RUN_ROOT / "scoring/final/BLIND_QUEUE.jsonl"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fact_sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return (
        "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) for row in rows)
        + ("\n" if rows else "")
    ).encode()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_bytes(jsonl_bytes(rows))


def load_wo() -> Any:
    spec = importlib.util.spec_from_file_location("block300_wo", runner.WO_SCORER)
    if spec is None or spec.loader is None:
        raise RuntimeError("WO_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_facts(raw: str, validator: Draft202012Validator) -> tuple[bool, bool, list[dict[str, Any]]]:
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError:
        value = None
    json_valid = isinstance(value, dict)
    schema_valid = json_valid and not list(validator.iter_errors(value))
    if json_valid and isinstance(value.get("facts"), list):
        facts = [item for item in value["facts"] if isinstance(item, dict) and isinstance(item.get("fact"), str) and item["fact"]]
        return True, schema_valid, facts
    decoder = json.JSONDecoder()
    recovered = []
    for start, character in enumerate(raw):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and isinstance(candidate.get("fact"), str) and candidate["fact"]:
            recovered.append(candidate)
    return json_valid, schema_valid, recovered


def repeated_chunk(raw: str) -> bool:
    compact = re.sub(r"\s+", "", raw)
    if len(compact) < 240:
        return False
    chunks = Counter(compact[index : index + 80] for index in range(0, len(compact) - 79, 8))
    return any(count >= 3 for count in chunks.values())


def input_bundle_sha(raw_sha: str) -> str:
    payload = "|".join(
        [
            raw_sha,
            sha256(runner.REQUESTS),
            sha256(runner.SOURCE_MAP),
            sha256(runner.GOLD),
            sha256(runner.SPEC),
            sha256(Path(__file__)),
        ]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def verify_execution_identity() -> tuple[list[dict[str, Any]], str]:
    for path in (RAW, RESULT, IDENTITY, TICKET, runner.REQUESTS, runner.SOURCE_MAP):
        if not path.is_file():
            raise RuntimeError(f"EXECUTION_MEMBER_MISSING:{path}")
    raw_sha = sha256(RAW)
    result = read_json(RESULT)
    identity = read_json(IDENTITY)
    ticket_sha = sha256(TICKET)
    expected_common = {
        "ticket_sha256": ticket_sha,
        "spec_sha256": sha256(runner.SPEC),
        "runner_sha256": sha256(RUNNER_PATH),
        "scorer_sha256": sha256(Path(__file__)),
        "prepare_receipt_sha256": sha256(runner.PREP_RECEIPT),
        "source_map_sha256": sha256(runner.SOURCE_MAP),
        "requests_sha256": sha256(runner.REQUESTS),
    }
    for key, expected in expected_common.items():
        if identity.get(key) != expected or result.get(key) != expected:
            raise RuntimeError(f"EXECUTION_IDENTITY_DRIFT:{key}")
    if result.get("raw_sha256") != raw_sha or result.get("rows") != 22:
        raise RuntimeError("INFERENCE_RESULT_RAW_DRIFT")
    if result.get("adapter_loaded") is not False or result.get("retry") != 0 or result.get("api_calls") != 0:
        raise RuntimeError("INFERENCE_BOUNDARY_DRIFT")
    gates = result.get("model_member_gates_before_each_load")
    if not isinstance(gates, list) or len(gates) != 1 or result.get("model_load_count") != 1:
        raise RuntimeError("MODEL_LOAD_GATE_COUNT_DRIFT")
    gate = gates[0].get("gate", {})
    if gate != {"member_count": 13, "total_bytes": 8060917568, "revision": runner.MODEL_REVISION}:
        raise RuntimeError("MODEL_MEMBER_GATE_DRIFT")
    rows = read_jsonl(RAW)
    mapping = read_jsonl(runner.SOURCE_MAP)
    expected_order = [row["request_id"] for row in mapping]
    if len(rows) != 22 or [row.get("request_id") for row in rows] != expected_order:
        raise RuntimeError("RAW_ROW_ORDER_DRIFT")
    if any(row.get("variant") != runner.VARIANT for row in rows):
        raise RuntimeError("RAW_VARIANT_DRIFT")
    return rows, raw_sha


def local_evidence_valid(values: Any, valid_ids: list[str]) -> bool:
    if not isinstance(values, list) or not values or any(not isinstance(value, str) for value in values):
        return False
    if len(values) != len(set(values)) or any(value not in valid_ids for value in values):
        return False
    indexes = [valid_ids.index(value) for value in values]
    return indexes == list(range(indexes[0], indexes[0] + len(indexes)))


def mechanical(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    validator = Draft202012Validator(read_json(runner.SCHEMA))
    mappings = {row["request_id"]: row for row in read_jsonl(runner.SOURCE_MAP)}
    parsed = {}
    cases = []
    facts_by_parent: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in rows:
        json_valid, schema_valid, facts = parse_facts(row["raw_output"], validator)
        mapping = mappings[row["request_id"]]
        valid_ids = [unit["id"] for unit in mapping["target_units"]]
        illegal = sum(not local_evidence_valid(fact.get("evidence_ids"), valid_ids) for fact in facts)
        within_duplicates = sum(count - 1 for count in Counter(fact["fact"] for fact in facts).values() if count > 1)
        facts_by_parent[row["case_id"]].extend(
            (row["request_id"], fact["fact"]) for fact in facts
        )
        parsed[row["request_id"]] = facts
        cases.append(
            {
                "request_id": row["request_id"],
                "case_id": row["case_id"],
                "predictions": len(facts),
                "strict_json": json_valid,
                "complete_schema": schema_valid,
                "illegal_or_noncontinuous_evidence": illegal,
                "within_block_duplicate_predictions": within_duplicates,
                "repetition_detected": within_duplicates > 0 or repeated_chunk(row["raw_output"]),
                "token_limit_hit": row.get("finish_reason") == "length" or row.get("generation_tokens_including_stop", 0) >= 2048,
            }
        )
    cross_duplicates = 0
    for occurrences in facts_by_parent.values():
        blocks_by_fact: dict[str, set[str]] = defaultdict(set)
        for request_id, fact in occurrences:
            blocks_by_fact[fact].add(request_id)
        cross_duplicates += sum(len(blocks) - 1 for blocks in blocks_by_fact.values())
    summary = {
        "rows": len(cases),
        "strict_json_rows": sum(row["strict_json"] for row in cases),
        "complete_schema_rows": sum(row["complete_schema"] for row in cases),
        "illegal_or_noncontinuous_evidence_predictions": sum(row["illegal_or_noncontinuous_evidence"] for row in cases),
        "repetition_rows": sum(row["repetition_detected"] for row in cases),
        "token_limit_rows": sum(row["token_limit_hit"] for row in cases),
        "within_block_duplicate_predictions": sum(row["within_block_duplicate_predictions"] for row in cases),
        "cross_block_duplicate_predictions": cross_duplicates,
        "retry": read_json(RESULT)["retry"],
    }
    summary["mechanically_passed"] = (
        summary["rows"] == 22
        and summary["strict_json_rows"] == 22
        and summary["complete_schema_rows"] == 22
        and summary["illegal_or_noncontinuous_evidence_predictions"] == 0
        and summary["repetition_rows"] == 0
        and summary["token_limit_rows"] == 0
        and summary["within_block_duplicate_predictions"] == 0
        and summary["retry"] == 0
    )
    return {"summary": summary, "case_metrics": cases}, parsed


def gold_and_ownership() -> tuple[dict[str, list[dict[str, Any]]], dict[str, str | None]]:
    old_txx = {row["case_id"]: row for row in read_jsonl(runner.OLD_TXX)}
    mappings = read_jsonl(runner.SOURCE_MAP)
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for mapping in mappings:
        by_case[mapping["parent_case_id"]].append(mapping)
    gold = {}
    owners = {}
    for row in read_jsonl(runner.GOLD):
        if row["case_id"] not in runner.STAGE_CASES:
            continue
        case_id = row["case_id"]
        units = {unit["id"]: (unit["start"], unit["end"]) for unit in old_txx[case_id]["target_units"]}
        facts = []
        for index, fact in enumerate(row["facts"], 1):
            fact_id = f"{case_id}-F{index:03d}"
            start = min(units[unit][0] for unit in fact["evidence_ids"])
            end = max(units[unit][1] for unit in fact["evidence_ids"])
            owner_rows = [block for block in by_case[case_id] if block["original_target_start"] <= start and end <= block["original_target_end"]]
            owner = owner_rows[0]["request_id"] if len(owner_rows) == 1 else None
            owners[fact_id] = owner
            facts.append(
                {
                    "fact_id": fact_id,
                    "fact": fact["fact_sentence"],
                    "status": fact["status"],
                    "speaker": fact["speaker"],
                    "evidence_ids": fact["evidence_ids"],
                    "evidence_original_target_start": start,
                    "evidence_original_target_end": end,
                }
            )
        gold[case_id] = facts
    if sum(len(value) for value in gold.values()) != 85 or sum(value is None for value in owners.values()) != 8:
        raise RuntimeError("GOLD_DENOMINATOR_OR_OWNERSHIP_DRIFT")
    return gold, owners


def queue_identity(bundle_sha: str, raw_sha: str, case_id: str, fact: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "prediction_fact": fact,
        "prediction_fact_sha256": fact_sha(fact),
        "input_bundle_sha256": bundle_sha,
        "raw_sha256": raw_sha,
        "gold_sha256": runner.EXPECTED["gold_sha256"],
        "semantic_policy_sha256": runner.EXPECTED["semantic_policy_sha256"],
        "candidate_gold_facts": [{"fact_id": item["fact_id"], "fact": item["fact"]} for item in candidates],
        "category": None,
        "matched_gold_fact_id": None,
    }


def verify_adjudications(path: Path | None, queue: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None:
        return {}
    expected = {(row["case_id"], row["prediction_fact_sha256"]): row for row in queue}
    result = {}
    for row in read_jsonl(path):
        key = (row.get("case_id"), row.get("prediction_fact_sha256"))
        if key not in expected or key in result:
            raise RuntimeError("ADJUDICATION_UNKNOWN_OR_DUPLICATE_KEY")
        source = expected[key]
        for field in source:
            if field in {"category", "matched_gold_fact_id"}:
                continue
            if row.get(field) != source[field]:
                raise RuntimeError(f"ADJUDICATION_IDENTITY_DRIFT:{field}")
        category = row.get("category")
        matched = row.get("matched_gold_fact_id")
        if category == "SEMANTIC_EQUIVALENT":
            if matched not in {item["fact_id"] for item in source["candidate_gold_facts"]}:
                raise RuntimeError("ADJUDICATION_MATCHED_GOLD_INVALID")
        elif category not in {"NOT_MATCH", "OUT_OF_SCOPE"} or matched is not None:
            raise RuntimeError("ADJUDICATION_CATEGORY_INVALID")
        result[key] = row
    if set(result) != set(expected):
        raise RuntimeError("ADJUDICATION_COVERAGE_INCOMPLETE")
    return result


def semantic(
    rows: list[dict[str, Any]],
    parsed: dict[str, list[dict[str, Any]]],
    raw_sha: str,
    adjudications: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    wo = load_wo()
    gold, owners = gold_and_ownership()
    mapping = {row["request_id"]: row for row in read_jsonl(runner.SOURCE_MAP)}
    bundle_sha = input_bundle_sha(raw_sha)
    pending = {}
    matched_candidates = []
    for row in rows:
        request_id = row["request_id"]
        case_id = row["case_id"]
        by_normalized: dict[str, list[str]] = defaultdict(list)
        for item in gold[case_id]:
            by_normalized[wo.normalize(item["fact"])].append(item["fact_id"])
        for prediction in parsed[request_id]:
            text = prediction["fact"]
            normalized = wo.normalize(text)
            matched_id = by_normalized.get(normalized, [None])[0] if normalized else None
            if matched_id is None:
                key = (case_id, fact_sha(text))
                decision = adjudications.get(key)
                if decision is None:
                    pending.setdefault(key, queue_identity(bundle_sha, raw_sha, case_id, text, gold[case_id]))
                elif decision["category"] == "SEMANTIC_EQUIVALENT":
                    matched_id = decision["matched_gold_fact_id"]
            matched_candidates.append(
                {
                    "case_id": case_id,
                    "request_id": request_id,
                    "prediction": prediction,
                    "matched_gold_fact_id": matched_id,
                }
            )
    used_gold = set()
    tp = status_ok = speaker_ok = evidence_ok = 0
    crossing_overreach = wrong_block_overreach = 0
    case_metrics = []
    case_acc: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    gold_lookup = {item["fact_id"]: item for facts in gold.values() for item in facts}
    for item in matched_candidates:
        case_id = item["case_id"]
        case_acc[case_id]["predictions"] += 1
        matched_id = item["matched_gold_fact_id"]
        if matched_id is None:
            continue
        owner = owners[matched_id]
        if owner is None:
            crossing_overreach += 1
            case_acc[case_id]["crossing_overreach"] += 1
            continue
        if owner != item["request_id"]:
            wrong_block_overreach += 1
            case_acc[case_id]["wrong_block_overreach"] += 1
            continue
        if matched_id in used_gold:
            continue
        used_gold.add(matched_id)
        tp += 1
        case_acc[case_id]["tp"] += 1
        prediction = item["prediction"]
        target = gold_lookup[matched_id]
        status_ok += prediction.get("status") == target["status"]
        speaker_ok += prediction.get("speaker") == target["speaker"]
        local = {unit["id"]: unit for unit in mapping[item["request_id"]]["target_units"]}
        evidence = prediction.get("evidence_ids", [])
        if evidence and all(unit in local for unit in evidence):
            start = min(local[unit]["original_target_start"] for unit in evidence)
            end = max(local[unit]["original_target_end"] for unit in evidence)
            evidence_ok += (start, end) == (target["evidence_original_target_start"], target["evidence_original_target_end"])
    predictions = len(matched_candidates)
    metrics = wo.prf(tp, predictions - tp, 85 - tp)
    for case_id in runner.STAGE_CASES:
        values = case_acc[case_id]
        case_metrics.append(
            {
                "case_id": case_id,
                "gold": len(gold[case_id]),
                "predictions": values["predictions"],
                "legal_tp": values["tp"],
                "crossing_overreach_hits": values["crossing_overreach"],
                "wrong_block_overreach_hits": values["wrong_block_overreach"],
            }
        )
    result = {
        "semantic_recoverable_responsibility_legal": metrics,
        "gold": 85,
        "contained_gold": 77,
        "crossing_gold_forced_fn": 8,
        "predictions": predictions,
        "legal_tp": tp,
        "contained_recall": round(tp / 77, 6),
        "crossing_fact_overreach_hits": crossing_overreach,
        "wrong_block_overreach_hits": wrong_block_overreach,
        "status_correct": status_ok,
        "speaker_correct": speaker_ok,
        "evidence_coordinate_span_correct": evidence_ok,
        "case_metrics": case_metrics,
    }
    return result, sorted(pending.values(), key=lambda row: (row["case_id"], row["prediction_fact_sha256"]))


def baseline_stage1() -> dict[str, Any]:
    final = read_json(runner.BASE_CONTEXT_FINAL)
    cases = [row for row in final["semantic"]["case_metrics"] if row["variant"] == "BASE_READ2" and row["case_id"] in runner.STAGE_CASES]
    tp = sum(row["semantic_tp"] for row in cases)
    predictions = sum(row["predictions"] for row in cases)
    gold = sum(row["gold"] for row in cases)
    if (len(cases), tp, predictions, gold) != (8, 29, 81, 85):
        raise RuntimeError("FROZEN_FULL_TARGET_STAGE1_BASELINE_DRIFT")
    f1 = 2 * tp / (predictions + gold)
    return {"tp": tp, "fp": predictions - tp, "fn": gold - tp, "predictions": predictions, "gold": gold, "f1": f1, "source_sha256": sha256(runner.BASE_CONTEXT_FINAL)}


def pre() -> None:
    if PRE_METRICS.exists() or PRE_QUEUE.exists():
        raise RuntimeError("PRE_OUTPUT_EXISTS_NO_OVERWRITE")
    runner.verify_static_outputs()
    rows, raw_sha = verify_execution_identity()
    mechanical_result, parsed = mechanical(rows)
    baseline = baseline_stage1()
    if mechanical_result["summary"]["mechanically_passed"]:
        semantic_result, queue = semantic(rows, parsed, raw_sha, {})
    else:
        semantic_result, queue = None, []
    queue_bytes = jsonl_bytes(queue)
    metrics = {
        "status": "PASS_MECHANICAL_PENDING_BLIND_REVIEW" if queue else ("FAIL_MECHANICAL_HARD_STOP" if not mechanical_result["summary"]["mechanically_passed"] else "PASS_NO_PENDING_READY_FINAL"),
        "raw_sha256": raw_sha,
        "input_bundle_sha256": input_bundle_sha(raw_sha),
        "requests_sha256": sha256(runner.REQUESTS),
        "source_map_sha256": sha256(runner.SOURCE_MAP),
        "gold_sha256": runner.EXPECTED["gold_sha256"],
        "mechanical": mechanical_result,
        "frozen_full_target_stage1": baseline,
        "semantic_preview": semantic_result,
        "semantic_pending": len(queue),
        "blind_queue_sha256": hashlib.sha256(queue_bytes).hexdigest(),
        "full24_run_authorized": False,
    }
    write_json(PRE_METRICS, metrics)
    write_jsonl(PRE_QUEUE, queue)
    print(json.dumps({"status": metrics["status"], "pending": len(queue), "queue_sha256": sha256(PRE_QUEUE)}))


def final(adjudications_path: Path) -> None:
    if FINAL_METRICS.exists() or FINAL_QUEUE.exists():
        raise RuntimeError("FINAL_OUTPUT_EXISTS_NO_OVERWRITE")
    if not PRE_METRICS.is_file() or not PRE_QUEUE.is_file():
        raise RuntimeError("PRE_OUTPUT_MISSING")
    runner.verify_static_outputs()
    pre_metrics = read_json(PRE_METRICS)
    if not pre_metrics["mechanical"]["summary"]["mechanically_passed"]:
        raise RuntimeError("FINAL_FORBIDDEN_AFTER_MECHANICAL_FAIL")
    rows, raw_sha = verify_execution_identity()
    current_bundle_sha = input_bundle_sha(raw_sha)
    if raw_sha != pre_metrics["raw_sha256"] or sha256(PRE_QUEUE) != pre_metrics["blind_queue_sha256"]:
        raise RuntimeError("PRE_TO_FINAL_RAW_OR_QUEUE_DRIFT")
    if current_bundle_sha != pre_metrics.get("input_bundle_sha256"):
        raise RuntimeError("PRE_TO_FINAL_INPUT_BUNDLE_DRIFT")
    if (
        sha256(runner.REQUESTS) != pre_metrics.get("requests_sha256")
        or sha256(runner.SOURCE_MAP) != pre_metrics.get("source_map_sha256")
        or runner.EXPECTED["gold_sha256"] != pre_metrics.get("gold_sha256")
    ):
        raise RuntimeError("PRE_TO_FINAL_STATIC_INPUT_IDENTITY_DRIFT")
    mechanical_result, parsed = mechanical(rows)
    _semantic_preview, expected_queue = semantic(rows, parsed, raw_sha, {})
    if jsonl_bytes(expected_queue) != PRE_QUEUE.read_bytes():
        raise RuntimeError("PRE_QUEUE_REBUILD_DRIFT")
    decisions = verify_adjudications(adjudications_path, expected_queue)
    semantic_result, pending = semantic(rows, parsed, raw_sha, decisions)
    if pending:
        raise RuntimeError("SEMANTIC_PENDING_NOT_ZERO")
    baseline = baseline_stage1()
    candidate_f1 = semantic_result["semantic_recoverable_responsibility_legal"]["f1"]
    legal_tp = semantic_result["legal_tp"]
    predictions = semantic_result["predictions"]
    candidate_f1_exact = 2 * legal_tp / (predictions + 85) if predictions + 85 else 0.0
    passed = candidate_f1_exact + 1e-12 >= baseline["f1"] + 0.02
    metrics = {
        "status": "PASS_STAGE1_MAY_PREPARE_FULL24_SEPARATELY" if passed else "FAIL_STAGE1_RETAIN_FULL_TARGET_CLOSE_BLOCK300",
        "raw_sha256": raw_sha,
        "input_bundle_sha256": current_bundle_sha,
        "pre_metrics_sha256": sha256(PRE_METRICS),
        "pre_queue_sha256": sha256(PRE_QUEUE),
        "adjudications_sha256": sha256(adjudications_path),
        "mechanical": mechanical_result,
        "frozen_full_target_stage1": baseline,
        "block300_stage1": semantic_result,
        "minimum_absolute_f1_gain": 0.02,
        "candidate_f1_exact_for_gate": candidate_f1_exact,
        "f1_gain": round(candidate_f1_exact - baseline["f1"], 6),
        "gate_passed": passed,
        "semantic_pending": 0,
        "full24_run_executed": False,
    }
    write_json(FINAL_METRICS, metrics)
    write_jsonl(FINAL_QUEUE, [])
    print(json.dumps({"status": metrics["status"], "f1": candidate_f1, "gate_passed": passed}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("pre", "final"))
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    if args.command == "pre":
        if args.adjudications:
            raise RuntimeError("PRE_TAKES_NO_ADJUDICATIONS")
        pre()
    else:
        if args.adjudications is None:
            raise RuntimeError("FINAL_REQUIRES_ADJUDICATIONS")
        final(args.adjudications)


if __name__ == "__main__":
    main()
