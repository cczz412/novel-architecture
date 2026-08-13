#!/usr/bin/env python3
"""Mechanical gate and blind semantic scoring for the RULE prompt screen."""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

from jsonschema import Draft202012Validator


sys.dont_write_bytecode = True
RUNNER_PATH = Path(__file__).resolve().parent / "run_rule_prompt_screen.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("rule_prompt_runner", RUNNER_PATH)
if RUNNER_SPEC is None or RUNNER_SPEC.loader is None:
    raise RuntimeError("RUNNER_IMPORT_FAILED")
runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(runner)
RUN_ROOT = runner.RUN_ROOT
RAW = RUN_ROOT / "inference/NEW_RULES_RAW_48.jsonl"
RESULT = RUN_ROOT / "inference/NEW_RULES_RESULT.json"
RUN_IDENTITY = RUN_ROOT / "RUN_IDENTITY.json"
EXECUTION_TICKET = RUN_ROOT / "AUTHORIZATION_TICKET.json"
REQUEST_PATHS = {
    "RULE-1-PLUS-ONE": RUN_ROOT / "requests/RULE_1_PLUS_ONE_REQUESTS_24.jsonl",
    "RULE-2-PLUS-TWO": RUN_ROOT / "requests/RULE_2_PLUS_TWO_REQUESTS_24.jsonl",
}
MAX_OUTPUT_TOKENS = 2048
BASELINE_F1 = 0.352941
BASELINE_RECALL = 0.332143
CHALLENGER_F1_GATE = 0.372941
RULE2_MINIMUM_LEAD = Decimal("0.020000")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fact_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_bytes(jsonl_bytes(rows))


def load_wo() -> Any:
    spec = importlib.util.spec_from_file_location("rule_prompt_wo", runner.WO_SCORER)
    if spec is None or spec.loader is None:
        raise RuntimeError("WO_SCORER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def repeated_chunk(raw: str) -> bool:
    compact = re.sub(r"\s+", "", raw)
    if len(compact) < 240:
        return False
    chunks = Counter(compact[index : index + 80] for index in range(0, len(compact) - 79, 8))
    return any(count >= 3 for count in chunks.values())


def parse_facts(
    raw: str, validator: Draft202012Validator
) -> tuple[bool, bool, list[dict[str, Any]]]:
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError:
        value = None
    json_valid = isinstance(value, dict)
    schema_valid = json_valid and not list(validator.iter_errors(value))
    if json_valid and isinstance(value.get("facts"), list):
        facts = [
            item
            for item in value["facts"]
            if isinstance(item, dict) and isinstance(item.get("fact"), str) and item["fact"]
        ]
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
        if isinstance(candidate, dict) and isinstance(candidate.get("fact"), str):
            if candidate["fact"]:
                recovered.append(candidate)
    return json_valid, schema_valid, recovered


def gold_map() -> dict[str, list[dict[str, Any]]]:
    rows = read_jsonl(runner.GOLD)
    cases = [f"C{index:02d}" for index in range(1, 25)]
    if [row.get("case_id") for row in rows] != cases:
        raise RuntimeError("GOLD_CASE_ORDER_DRIFT")
    return {
        row["case_id"]: [
            {
                "fact_id": f"{row['case_id']}-F{index:03d}",
                "fact": fact["fact_sentence"],
                "status": fact["status"],
                "speaker": fact["speaker"],
                "evidence_ids": fact["evidence_ids"],
            }
            for index, fact in enumerate(row["facts"], 1)
        ]
        for row in rows
    }


def target_ids() -> dict[str, list[str]]:
    result = {}
    for row in read_jsonl(runner.TXX):
        result[row["case_id"]] = [unit["id"] for unit in row["target_units"]]
    return result


def evidence_diagnostic(item: dict[str, Any], allowlist: list[str]) -> dict[str, bool]:
    value = item.get("evidence_ids")
    structural_illegal = (
        not isinstance(value, list)
        or not value
        or not all(isinstance(identifier, str) and identifier in allowlist for identifier in value)
    )
    if structural_illegal:
        return {
            "hard_illegal": True,
            "ordered": False,
            "continuous": False,
        }
    positions = [allowlist.index(identifier) for identifier in value]
    ordered = positions == sorted(positions) and len(set(positions)) == len(positions)
    continuous = ordered and positions == list(range(positions[0], positions[-1] + 1))
    return {"hard_illegal": False, "ordered": ordered, "continuous": continuous}


def mechanical_case(
    row: dict[str, Any], validator: Draft202012Validator, valid_ids: dict[str, list[str]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    json_valid, schema_valid, facts = parse_facts(row["raw_output"], validator)
    duplicates = sum(
        count - 1 for count in Counter(item.get("fact") for item in facts).values() if count > 1
    )
    evidence = [evidence_diagnostic(item, valid_ids[row["case_id"]]) for item in facts]
    return (
        {
            "case_id": row["case_id"],
            "predictions": len(facts),
            "json_valid": json_valid,
            "schema_valid": schema_valid,
            "empty_answer": len(facts) == 0,
            "illegal_evidence_predictions": sum(item["hard_illegal"] for item in evidence),
            "evidence_order_violations": sum(
                not item["hard_illegal"] and not item["ordered"] for item in evidence
            ),
            "evidence_continuity_violations": sum(
                not item["hard_illegal"] and not item["continuous"] for item in evidence
            ),
            "duplicate_predictions": duplicates,
            "repetition_detected": duplicates > 0 or repeated_chunk(row["raw_output"]),
            "token_limit_hit": row.get("finish_reason") == "length"
            or row.get("generation_tokens_including_stop", 0) >= MAX_OUTPUT_TOKENS,
        },
        facts,
    )


def mechanical_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    predictions = sum(row["predictions"] for row in rows)
    result = {
        "cases": len(rows),
        "predictions": predictions,
        "strict_json_cases": sum(row["json_valid"] for row in rows),
        "schema_cases": sum(row["schema_valid"] for row in rows),
        "empty_answer_cases": sum(row["empty_answer"] for row in rows),
        "illegal_evidence_predictions": sum(row["illegal_evidence_predictions"] for row in rows),
        "evidence_order_violations": sum(row["evidence_order_violations"] for row in rows),
        "evidence_continuity_violations": sum(
            row["evidence_continuity_violations"] for row in rows
        ),
        "repetition_cases": sum(row["repetition_detected"] for row in rows),
        "token_limit_cases": sum(row["token_limit_hit"] for row in rows),
        "duplicate_predictions": sum(row["duplicate_predictions"] for row in rows),
    }
    result["evidence_order_accuracy"] = (
        round((predictions - result["evidence_order_violations"]) / predictions, 6)
        if predictions
        else 1.0
    )
    result["evidence_continuity_accuracy"] = (
        round((predictions - result["evidence_continuity_violations"]) / predictions, 6)
        if predictions
        else 1.0
    )
    result["mechanically_eligible"] = (
        result["cases"] == 24
        and result["strict_json_cases"] == 24
        and result["schema_cases"] >= 22
        and result["empty_answer_cases"] == 0
        and result["illegal_evidence_predictions"] == 0
        and result["repetition_cases"] == 0
        and result["token_limit_cases"] == 0
        and result["duplicate_predictions"] == 0
    )
    result["order_and_continuity_are_diagnostics_not_hard_gates"] = True
    return result


def verify_frozen_baseline() -> dict[str, Any]:
    rows, projection_sha, _ = runner.exact_base_projection()
    if len(rows) != 24 or projection_sha != runner.EXPECTED["base_projection_sha256"]:
        raise RuntimeError("BASE_PROJECTION_DRIFT")
    validator = Draft202012Validator(json.loads(runner.SCHEMA.read_text(encoding="utf-8")))
    valid_ids = target_ids()
    cases = [mechanical_case(row, validator, valid_ids)[0] for row in rows]
    mechanical = mechanical_summary(cases)
    expected = {
        "cases": 24,
        "strict_json_cases": 24,
        "schema_cases": 22,
        "empty_answer_cases": 0,
        "illegal_evidence_predictions": 0,
        "repetition_cases": 0,
        "token_limit_cases": 0,
        "duplicate_predictions": 0,
        "mechanically_eligible": True,
    }
    for key, value in expected.items():
        if mechanical.get(key) != value:
            raise RuntimeError(f"BASE_MECHANICAL_DRIFT:{key}")
    final = read_json(runner.BASE_CONTEXT_FINAL)
    semantic = final.get("semantic", {}).get("variants", {}).get("BASE_READ2")
    prf = semantic.get("semantic_recoverable") if semantic else None
    if prf != {
        "tp": 93,
        "fp": 154,
        "fn": 187,
        "precision": 0.376518,
        "recall": BASELINE_RECALL,
        "f1": BASELINE_F1,
    }:
        raise RuntimeError("BASE_SEMANTIC_DRIFT")
    return {
        "variant": "RULE-0-MINIMAL",
        "source": "FROZEN_BASE_READ2_H180_OUT2_NO_RERUN",
        "mechanical": mechanical,
        "semantic_recoverable": prf,
        "semantic_tp": semantic["semantic_tp"],
        "status_correct": semantic["status_correct"],
        "speaker_correct": semantic["speaker_correct"],
        "evidence_correct": semantic["evidence_correct"],
    }


def reusable_decisions() -> dict[tuple[str, str], dict[str, Any]]:
    sources = (
        (runner.BASE_CONTEXT_DECISIONS, 223, "BASE_CONTEXT_223"),
        (runner.READ2_R02, 381, "READ2_CARRYOVER_R02_381"),
    )
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for path, expected_rows, label in sources:
        rows = read_jsonl(path)
        if len(rows) != expected_rows:
            raise RuntimeError(f"REUSABLE_DECISION_ROWS_DRIFT:{label}")
        for row in rows:
            text = row.get("prediction_fact", "")
            key = (row.get("case_id"), row.get("prediction_fact_sha256"))
            if fact_sha(text) != key[1]:
                raise RuntimeError(f"REUSABLE_DECISION_KEY_DRIFT:{label}")
            category = row.get("category")
            matched = row.get("matched_gold_fact_id")
            if category not in {"SEMANTIC_EQUIVALENT", "NOT_MATCH", "OUT_OF_SCOPE"}:
                raise RuntimeError(f"REUSABLE_DECISION_CATEGORY_DRIFT:{label}")
            if category != "SEMANTIC_EQUIVALENT" and matched is not None:
                raise RuntimeError(f"REUSABLE_DECISION_MATCH_DRIFT:{label}")
            compact = {
                "case_id": key[0],
                "prediction_fact": text,
                "prediction_fact_sha256": key[1],
                "category": category,
                "matched_gold_fact_id": matched,
            }
            previous = result.get(key)
            if previous is not None and (
                previous["category"] != category
                or previous["matched_gold_fact_id"] != matched
                or previous["prediction_fact"] != text
            ):
                raise RuntimeError(f"REUSABLE_DECISION_CONFLICT:{key[0]}:{key[1]}")
            result[key] = compact
    return result


def added_decisions(
    path: Path | None, queue: list[dict[str, Any]]
) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None:
        return {}
    rows = read_jsonl(path)
    expected = {(row["case_id"], row["prediction_fact_sha256"]): row for row in queue}
    result = {}
    for row in rows:
        if fact_sha(row.get("prediction_fact", "")) != row.get(
            "prediction_fact_sha256"
        ):
            raise RuntimeError("ADJUDICATION_PREDICTION_FACT_SHA_DRIFT")
        key = (row.get("case_id"), row.get("prediction_fact_sha256"))
        if key in result or key not in expected:
            raise RuntimeError("ADJUDICATION_DUPLICATE_OR_UNKNOWN_KEY")
        source = expected[key]
        for field in (
            "case_id",
            "prediction_fact",
            "prediction_fact_sha256",
            "input_bundle_sha256",
            "new_rules_raw_sha256",
            "gold_sha256",
            "semantic_policy_sha256",
            "candidate_gold_facts",
        ):
            if row.get(field) != source.get(field):
                raise RuntimeError(f"ADJUDICATION_IDENTITY_DRIFT:{field}")
        category = row.get("category")
        matched = row.get("matched_gold_fact_id")
        if category == "SEMANTIC_EQUIVALENT":
            if matched not in {item["fact_id"] for item in row["candidate_gold_facts"]}:
                raise RuntimeError("ADJUDICATION_MATCHED_GOLD_INVALID")
        elif category not in {"NOT_MATCH", "OUT_OF_SCOPE"} or matched is not None:
            raise RuntimeError("ADJUDICATION_CATEGORY_OR_MATCH_INVALID")
        result[key] = row
    if set(result) != set(expected):
        raise RuntimeError("ADJUDICATION_COVERAGE_INCOMPLETE")
    return result


def validate_anonymous_queue(rows: list[dict[str, Any]]) -> None:
    seen: set[tuple[str, str]] = set()
    for row in rows:
        text = row.get("prediction_fact", "")
        digest = row.get("prediction_fact_sha256")
        if not isinstance(text, str) or fact_sha(text) != digest:
            raise RuntimeError("BLIND_QUEUE_PREDICTION_FACT_SHA_DRIFT")
        key = (row.get("case_id"), digest)
        if key in seen:
            raise RuntimeError("BLIND_QUEUE_DUPLICATE_KEY")
        seen.add(key)


def anonymous_queue(pending: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows = sorted(pending.values(), key=lambda row: (row["case_id"], row["prediction_fact_sha256"]))

    def identity_leak(value: Any) -> str | None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower() in {"variant", "arm"}:
                    return key
                found = identity_leak(item)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = identity_leak(item)
                if found is not None:
                    return found
        elif isinstance(value, str) and value in runner.VARIANTS:
            return value
        return None

    leak = identity_leak(rows)
    if leak is not None:
        raise RuntimeError(f"BLIND_QUEUE_IDENTITY_LEAK:{leak}")
    validate_anonymous_queue(rows)
    return rows


def semantic_score(
    rows: list[dict[str, Any]],
    parsed: dict[tuple[str, str], list[dict[str, Any]]],
    eligible_variants: list[str],
    bundle_sha: str,
    raw_sha: str,
    added: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    wo = load_wo()
    gold = gold_map()
    frozen = reusable_decisions()
    pending: dict[tuple[str, str], dict[str, Any]] = {}
    cases = []
    for variant in eligible_variants:
        for row in (item for item in rows if item["variant"] == variant):
            case_id = row["case_id"]
            predictions = parsed[(variant, case_id)]
            expected = gold[case_id]
            pairs, unmatched = wo.match(expected, predictions, normalized=True)
            used_gold = {gold_index for _, gold_index in pairs}
            for prediction_index in unmatched:
                text = predictions[prediction_index]["fact"]
                key = (case_id, fact_sha(text))
                decision = frozen.get(key) or added.get(key)
                if decision is None:
                    pending.setdefault(
                        key,
                        {
                            "case_id": case_id,
                            "prediction_fact": text,
                            "prediction_fact_sha256": key[1],
                            "input_bundle_sha256": bundle_sha,
                            "new_rules_raw_sha256": raw_sha,
                            "gold_sha256": runner.EXPECTED["gold_sha256"],
                            "semantic_policy_sha256": runner.EXPECTED[
                                "semantic_policy_sha256"
                            ],
                            "candidate_gold_facts": [
                                {"fact_id": item["fact_id"], "fact": item["fact"]}
                                for item in expected
                            ],
                            "category": None,
                            "matched_gold_fact_id": None,
                        },
                    )
                    continue
                if decision["category"] != "SEMANTIC_EQUIVALENT":
                    continue
                matched_id = decision.get("matched_gold_fact_id")
                gold_index = next(
                    (
                        index
                        for index, item in enumerate(expected)
                        if item["fact_id"] == matched_id
                    ),
                    None,
                )
                if gold_index is None:
                    raise RuntimeError("DECISION_MATCHED_GOLD_ID_INVALID")
                if gold_index not in used_gold:
                    pairs.append((prediction_index, gold_index))
                    used_gold.add(gold_index)
            status_ok = speaker_ok = evidence_ok = 0
            for prediction_index, gold_index in pairs:
                prediction = predictions[prediction_index]
                target = expected[gold_index]
                status_ok += prediction.get("status") == target["status"]
                speaker_ok += prediction.get("speaker") == target["speaker"]
                evidence_ok += prediction.get("evidence_ids") == target["evidence_ids"]
            cases.append(
                {
                    "variant": variant,
                    "case_id": case_id,
                    "gold": len(expected),
                    "predictions": len(predictions),
                    "semantic_tp": len(pairs),
                    "status_correct": status_ok,
                    "speaker_correct": speaker_ok,
                    "evidence_correct": evidence_ok,
                }
            )
    variants = {}
    for variant in eligible_variants:
        group = [row for row in cases if row["variant"] == variant]
        tp = sum(row["semantic_tp"] for row in group)
        predictions = sum(row["predictions"] for row in group)
        gold_count = sum(row["gold"] for row in group)
        variants[variant] = {
            "semantic_recoverable": wo.prf(tp, predictions - tp, gold_count - tp),
            "semantic_tp": tp,
            "predictions": predictions,
            "gold": gold_count,
            "status_correct": sum(row["status_correct"] for row in group),
            "speaker_correct": sum(row["speaker_correct"] for row in group),
            "evidence_correct": sum(row["evidence_correct"] for row in group),
        }
    return {"variants": variants, "case_metrics": cases}, anonymous_queue(pending)


def verify_execution_identity(raw_sha: str) -> dict[str, Any]:
    for path in (*REQUEST_PATHS.values(), EXECUTION_TICKET, RUN_IDENTITY, RESULT, RAW):
        if not path.is_file():
            raise RuntimeError(f"EXECUTION_IDENTITY_MEMBER_MISSING:{path}")
    ticket_sha = sha256(EXECUTION_TICKET)
    runner.validate_ticket(EXECUTION_TICKET, require_run_root_absent=False)
    current = {
        "spec_sha256": sha256(runner.SPEC),
        "runner_sha256": sha256(Path(runner.__file__)),
        "scorer_sha256": sha256(Path(__file__)),
        "prepare_receipt_sha256": sha256(runner.PREP_RECEIPT),
        "model_receipt_sha256": sha256(runner.MODEL_RECEIPT),
    }
    identity = read_json(RUN_IDENTITY)
    result = read_json(RESULT)
    identity_fixed = {
        "status": "AUTHORIZED_INFERENCE_STARTED",
        "run_id": runner.RUN_ID,
        "ticket_sha256": ticket_sha,
        "ticket_copy_sha256": ticket_sha,
        **current,
        "authorized_commands": ["infer-new-rules"],
        "adapter_loaded": False,
        "retry": 0,
        "api_calls": 0,
    }
    for key, expected in identity_fixed.items():
        if identity.get(key) != expected:
            raise RuntimeError(f"RUN_IDENTITY_FIELD_DRIFT:{key}")
    result_fixed = {
        "status": "PASS_NEW_RULES_48_INFERENCE",
        "run_id": runner.RUN_ID,
        "rows": 48,
        "rows_by_variant": {variant: 24 for variant in runner.VARIANTS},
        "raw_sha256": raw_sha,
        "request_sha256_by_variant": {
            variant: sha256(path) for variant, path in REQUEST_PATHS.items()
        },
        "ticket_sha256": ticket_sha,
        "ticket_copy_sha256": ticket_sha,
        **current,
        "adapter_loaded": False,
        "retry": 0,
        "api_calls": 0,
        "model_load_count": 1,
    }
    for key, expected in result_fixed.items():
        if result.get(key) != expected:
            raise RuntimeError(f"INFERENCE_RESULT_FIELD_DRIFT:{key}")
    expected_gate = [
        {
            "load_index": 1,
            "load_scope": "SHARED_UNFINETUNED_BASE_FOR_RULE1_RULE2",
            "gate": {
                "member_count": runner.MODEL_FILE_COUNT,
                "total_bytes": runner.MODEL_TOTAL_BYTES,
                "revision": runner.MODEL_REVISION,
            },
        }
    ]
    if result.get("model_member_gates_before_each_load") != expected_gate:
        raise RuntimeError("MODEL_MEMBER_GATE_DRIFT")
    return {
        "ticket_sha256": ticket_sha,
        **current,
        "ticket_authority_fields_nonempty": True,
        "identity_boundary_zh": "内部身份完整且需控制窗独立run audit",
        "model_member_gate": expected_gate[0],
    }


def source_rows() -> tuple[list[dict[str, Any]], str, str, dict[str, Any]]:
    runner.verify_static_inputs()
    raw_sha = sha256(RAW)
    execution = verify_execution_identity(raw_sha)
    rows = read_jsonl(RAW)
    if len(rows) != 48:
        raise RuntimeError("RAW_ROWS_NOT_48")
    cases = [f"C{index:02d}" for index in range(1, 25)]
    for variant in runner.VARIANTS:
        current = [row for row in rows if row.get("variant") == variant]
        if [row.get("case_id") for row in current] != cases:
            raise RuntimeError(f"RAW_VARIANT_CASE_ORDER_DRIFT:{variant}")
    _, projection_sha, projection_bytes = runner.exact_base_projection()
    if projection_sha != runner.EXPECTED["base_projection_sha256"]:
        raise RuntimeError("RUNTIME_BASE_PROJECTION_DRIFT")
    bundle = projection_bytes + RAW.read_bytes() + b"".join(
        path.read_bytes() for path in REQUEST_PATHS.values()
    )
    return rows, hashlib.sha256(bundle).hexdigest(), raw_sha, execution


def verify_pre_identity(
    raw_sha: str, bundle_sha: str
) -> tuple[dict[str, Any], list[dict[str, Any]], str, str, bytes]:
    metrics_path = RUN_ROOT / "scoring/pre/METRICS.json"
    queue_path = RUN_ROOT / "scoring/pre/BLIND_QUEUE.jsonl"
    if not metrics_path.is_file() or not queue_path.is_file():
        raise RuntimeError("FINAL_PRE_INPUT_MISSING")
    metrics_sha = sha256(metrics_path)
    queue_sha = sha256(queue_path)
    metrics = read_json(metrics_path)
    if metrics.get("new_rules_raw_sha256") != raw_sha:
        raise RuntimeError("FINAL_RAW_SHA_DRIFT")
    if metrics.get("input_bundle_sha256") != bundle_sha:
        raise RuntimeError("FINAL_INPUT_BUNDLE_SHA_DRIFT")
    if metrics.get("blind_queue_sha256") != queue_sha:
        raise RuntimeError("FINAL_PRE_QUEUE_SHA_DRIFT")
    queue_bytes = queue_path.read_bytes()
    queue_rows = read_jsonl(queue_path)
    validate_anonymous_queue(queue_rows)
    return metrics, queue_rows, metrics_sha, queue_sha, queue_bytes


def verify_fresh_queue_against_pre(
    fresh_queue: list[dict[str, Any]],
    pre_queue: list[dict[str, Any]],
    pre_queue_bytes: bytes,
    pre_metrics: dict[str, Any],
) -> None:
    validate_anonymous_queue(fresh_queue)
    validate_anonymous_queue(pre_queue)
    fresh_bytes = jsonl_bytes(fresh_queue)
    if fresh_bytes != pre_queue_bytes:
        raise RuntimeError("FINAL_FRESH_QUEUE_BYTES_DRIFT")
    digest = hashlib.sha256(fresh_bytes).hexdigest()
    if digest != pre_metrics.get("blind_queue_sha256"):
        raise RuntimeError("FINAL_FRESH_QUEUE_SHA_DRIFT")


def verify_pre_recomputed_state(
    pre_metrics: dict[str, Any],
    baseline: dict[str, Any],
    mechanical: dict[str, dict[str, Any]],
    mechanical_cases: list[dict[str, Any]],
    eligible: list[str],
    fresh_semantic: dict[str, Any],
    fresh_pending: list[dict[str, Any]],
) -> None:
    expected = {
        "rule0_frozen_baseline": baseline,
        "challenger_mechanical": mechanical,
        "mechanical_case_metrics": mechanical_cases,
        "mechanically_eligible_challengers": eligible,
        "semantic": fresh_semantic,
        "semantic_pending": len(fresh_pending),
        "evidence_order_and_continuity_fairly_recomputed_for_all_cells": True,
        "reusable_semantic_decision_batches": {
            "BASE_CONTEXT_223": runner.EXPECTED["base_context_decisions_sha256"],
            "READ2_CARRYOVER_R02_381": runner.EXPECTED["read2_r02_sha256"],
        },
        "block300_adjudications_reused": False,
        "baseline_rerun": False,
    }
    for key, value in expected.items():
        if pre_metrics.get(key) != value:
            raise RuntimeError(f"FINAL_PRE_RECOMPUTED_STATE_DRIFT:{key}")


def select_rule(
    semantic: dict[str, Any], mechanical: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    qualified = []
    diagnostics = {}
    for variant in runner.VARIANTS:
        score = semantic["variants"].get(variant)
        if score is None:
            diagnostics[variant] = {"qualified": False, "reason": "MECHANICAL_FAIL"}
            continue
        prf = score["semantic_recoverable"]
        passed = (
            mechanical[variant]["mechanically_eligible"]
            and prf["recall"] >= BASELINE_RECALL
            and prf["f1"] >= CHALLENGER_F1_GATE
        )
        diagnostics[variant] = {
            "qualified": passed,
            "recall": prf["recall"],
            "f1": prf["f1"],
            "recall_gate": BASELINE_RECALL,
            "replacement_f1_gate": CHALLENGER_F1_GATE,
        }
        if passed:
            qualified.append(variant)
    if not qualified:
        selected = "RULE-0-MINIMAL"
        branch = "NO_CHALLENGER_QUALIFIED_BASELINE_RETAINED"
    elif len(qualified) == 1:
        selected = qualified[0]
        branch = "ONLY_ONE_CHALLENGER_QUALIFIED"
    else:
        one = Decimal(
            str(semantic["variants"]["RULE-1-PLUS-ONE"]["semantic_recoverable"]["f1"])
        )
        two = Decimal(
            str(semantic["variants"]["RULE-2-PLUS-TWO"]["semantic_recoverable"]["f1"])
        )
        if two - one >= RULE2_MINIMUM_LEAD:
            selected = "RULE-2-PLUS-TWO"
            branch = "RULE2_BEATS_RULE1_BY_AT_LEAST_0.02"
        else:
            selected = "RULE-1-PLUS-ONE"
            branch = "BOTH_QUALIFY_RULE2_LEAD_BELOW_0.02_PREFER_RULE1"
    return {
        "selected_rule": selected,
        "selection_rule_branch": branch,
        "qualified_challengers": qualified,
        "challenger_diagnostics": diagnostics,
        "baseline_f1": BASELINE_F1,
        "baseline_recall": BASELINE_RECALL,
        "challenger_replacement_f1_gate": CHALLENGER_F1_GATE,
        "rule2_minimum_lead_over_rule1": str(RULE2_MINIMUM_LEAD),
        "rule2_lead_comparison": "DECIMAL_FIXED_POINT",
        "scope_name_zh": "未微调Base+H180+OUT2+完整责任段的RULE本机Demo",
        "does_not_authorize_training_or_production": True,
    }


def score(adjudications: Path | None, final: bool) -> None:
    rows, bundle_sha, raw_sha, execution = source_rows()
    validator = Draft202012Validator(json.loads(runner.SCHEMA.read_text(encoding="utf-8")))
    valid_ids = target_ids()
    mechanical_cases = []
    parsed = {}
    mechanical = {}
    for variant in runner.VARIANTS:
        current = []
        for row in (item for item in rows if item["variant"] == variant):
            metrics, facts = mechanical_case(row, validator, valid_ids)
            current.append(metrics)
            parsed[(variant, row["case_id"])] = facts
        mechanical_cases.extend({"variant": variant, **item} for item in current)
        mechanical[variant] = mechanical_summary(current)
    eligible = [
        variant for variant in runner.VARIANTS if mechanical[variant]["mechanically_eligible"]
    ]
    baseline = verify_frozen_baseline()
    pre_metrics_sha = pre_queue_sha = adjudications_sha = None
    if final:
        (
            pre_metrics,
            queue,
            pre_metrics_sha,
            pre_queue_sha,
            pre_queue_bytes,
        ) = verify_pre_identity(raw_sha, bundle_sha)
        fresh_semantic, fresh_pending = semantic_score(
            rows, parsed, eligible, bundle_sha, raw_sha, {}
        )
        verify_fresh_queue_against_pre(
            fresh_pending, queue, pre_queue_bytes, pre_metrics
        )
        verify_pre_recomputed_state(
            pre_metrics,
            baseline,
            mechanical,
            mechanical_cases,
            eligible,
            fresh_semantic,
            fresh_pending,
        )
        if queue and adjudications is None:
            raise RuntimeError("FINAL_ADJUDICATIONS_REQUIRED")
        adjudications_sha = sha256(adjudications) if adjudications is not None else None
        added = added_decisions(adjudications, queue)
    else:
        if adjudications is not None:
            raise RuntimeError("PRE_DOES_NOT_ACCEPT_ADJUDICATIONS")
        added = {}
    semantic, pending = semantic_score(rows, parsed, eligible, bundle_sha, raw_sha, added)
    if final and pending:
        raise RuntimeError("FINAL_SEMANTIC_PENDING_NOT_ZERO")
    selection = select_rule(semantic, mechanical) if final or not eligible else None
    if not eligible:
        status = "MECHANICAL_NO_CHALLENGER_QUALIFIED_BASELINE_RETAINED"
        pending = []
    elif final:
        status = "PASS_RULE_PROMPT_DEMO_SELECTION_COMPLETE"
    elif not pending:
        status = "READY_FOR_FINAL_NO_NEW_ADJUDICATIONS"
    else:
        status = "PENDING_BLIND_SEMANTIC_REVIEW"
    output_dir = RUN_ROOT / ("scoring/final" if final else "scoring/pre")
    if output_dir.exists():
        raise RuntimeError(f"OUTPUT_DIR_EXISTS_NO_OVERWRITE:{output_dir}")
    result = {
        "status": status,
        "scope_name_zh": "未微调Base+H180+OUT2+完整责任段的RULE本机Demo",
        "input_bundle_sha256": bundle_sha,
        "new_rules_raw_sha256": raw_sha,
        "gold_sha256": runner.EXPECTED["gold_sha256"],
        "semantic_policy_sha256": runner.EXPECTED["semantic_policy_sha256"],
        "execution_identity": execution,
        "rule0_frozen_baseline": baseline,
        "challenger_mechanical": mechanical,
        "mechanical_case_metrics": mechanical_cases,
        "mechanically_eligible_challengers": eligible,
        "semantic": semantic,
        "semantic_pending": len(pending),
        "blind_queue_sha256": hashlib.sha256(jsonl_bytes(pending)).hexdigest(),
        "selection": selection,
        "evidence_order_and_continuity_fairly_recomputed_for_all_cells": True,
        "reusable_semantic_decision_batches": {
            "BASE_CONTEXT_223": runner.EXPECTED["base_context_decisions_sha256"],
            "READ2_CARRYOVER_R02_381": runner.EXPECTED["read2_r02_sha256"],
        },
        "block300_adjudications_reused": False,
        "baseline_rerun": False,
        "api_calls": 0,
    }
    if final:
        result.update(
            {
                "pre_metrics_sha256": pre_metrics_sha,
                "pre_queue_sha256": pre_queue_sha,
                "adjudications_sha256": adjudications_sha,
            }
        )
    write_json(output_dir / "METRICS.json", result)
    write_jsonl(output_dir / "BLIND_QUEUE.jsonl", pending)
    if sha256(output_dir / "BLIND_QUEUE.jsonl") != result["blind_queue_sha256"]:
        raise RuntimeError("WRITTEN_BLIND_QUEUE_SHA_DRIFT")
    if final:
        write_json(
            output_dir / "FINAL_RECEIPT.json",
            {
                "schema_version": "base-h180-out2-rule-screen-final-receipt/1.0",
                "status": "FINAL_SCORING_COMPLETE",
                "new_rules_raw_sha256": raw_sha,
                "input_bundle_sha256": bundle_sha,
                "pre_metrics_sha256": pre_metrics_sha,
                "pre_queue_sha256": pre_queue_sha,
                "adjudications_sha256": adjudications_sha,
                "final_metrics_sha256": sha256(output_dir / "METRICS.json"),
                "final_queue_sha256": sha256(output_dir / "BLIND_QUEUE.jsonl"),
                "semantic_pending": len(pending),
                "api_calls": 0,
                "model_loads": 0,
                "training": 0,
                "inference": 0,
            },
        )
    print(json.dumps({"status": status, "eligible": eligible, "semantic_pending": len(pending)}))


def self_test() -> dict[str, Any]:
    runner.verify_static_inputs()
    baseline = verify_frozen_baseline()
    allowlist = ["T01", "T02", "T03"]
    ordered_gap = evidence_diagnostic({"evidence_ids": ["T01", "T03"]}, allowlist)
    reversed_ids = evidence_diagnostic({"evidence_ids": ["T03", "T02"]}, allowlist)
    out_of_scope = evidence_diagnostic({"evidence_ids": ["T04"]}, allowlist)
    if ordered_gap["hard_illegal"] or ordered_gap["continuous"]:
        raise RuntimeError("SELF_TEST_GAP_DIAGNOSTIC_FAILED")
    if reversed_ids["hard_illegal"] or reversed_ids["ordered"]:
        raise RuntimeError("SELF_TEST_ORDER_DIAGNOSTIC_FAILED")
    if not out_of_scope["hard_illegal"]:
        raise RuntimeError("SELF_TEST_OUT_OF_ALLOWLIST_GATE_FAILED")
    sample_a = {
        ("C01", fact_sha("甲事实")): {
            "case_id": "C01",
            "prediction_fact": "甲事实",
            "prediction_fact_sha256": fact_sha("甲事实"),
            "input_bundle_sha256": "b",
            "new_rules_raw_sha256": "r",
            "gold_sha256": "g",
            "semantic_policy_sha256": "p",
            "candidate_gold_facts": [],
            "category": None,
            "matched_gold_fact_id": None,
        },
        ("C02", fact_sha("乙事实")): {
            "case_id": "C02",
            "prediction_fact": "乙事实",
            "prediction_fact_sha256": fact_sha("乙事实"),
            "input_bundle_sha256": "b",
            "new_rules_raw_sha256": "r",
            "gold_sha256": "g",
            "semantic_policy_sha256": "p",
            "candidate_gold_facts": [],
            "category": None,
            "matched_gold_fact_id": None,
        },
    }
    sample_b = dict(reversed(list(sample_a.items())))
    if jsonl_bytes(anonymous_queue(sample_a)) != jsonl_bytes(anonymous_queue(sample_b)):
        raise RuntimeError("SELF_TEST_QUEUE_ORDER_INVARIANCE_FAILED")
    fresh_queue = anonymous_queue(sample_a)
    tampered_queue = json.loads(json.dumps(fresh_queue, ensure_ascii=False))
    tampered_queue[0]["prediction_fact"] = "被改过的事实"
    tampered_queue[0]["prediction_fact_sha256"] = fact_sha("被改过的事实")
    tampered_bytes = jsonl_bytes(tampered_queue)
    try:
        verify_fresh_queue_against_pre(
            fresh_queue,
            tampered_queue,
            tampered_bytes,
            {"blind_queue_sha256": hashlib.sha256(tampered_bytes).hexdigest()},
        )
    except RuntimeError as error:
        if str(error) != "FINAL_FRESH_QUEUE_BYTES_DRIFT":
            raise
    else:
        raise RuntimeError("SELF_TEST_FRESH_QUEUE_REBUILD_TAMPER_NOT_BLOCKED")
    mechanical = {variant: {"mechanically_eligible": True} for variant in runner.VARIANTS}

    def semantics(one: float, two: float) -> dict[str, Any]:
        return {
            "variants": {
                "RULE-1-PLUS-ONE": {
                    "semantic_recoverable": {"f1": one, "recall": 0.34}
                },
                "RULE-2-PLUS-TWO": {
                    "semantic_recoverable": {"f1": two, "recall": 0.34}
                },
            }
        }

    if select_rule(semantics(0.38, 0.39), mechanical)["selected_rule"] != "RULE-1-PLUS-ONE":
        raise RuntimeError("SELF_TEST_NEAR_TIE_RULE1_FAILED")
    if (
        select_rule(semantics(0.493369, 0.513369), mechanical)["selected_rule"]
        != "RULE-2-PLUS-TWO"
    ):
        raise RuntimeError("SELF_TEST_DECIMAL_BOUNDARY_RULE2_FAILED")
    ticket = {
        "schema_version": "base-h180-out2-full-target-rule-screen-ticket/1.0",
        "approved": True,
        "authorized_by": "CZ_CONTROL_WINDOW",
        "decision_id": "SELF_TEST_ONLY",
        "decision_text_sha256": "self-test-decision-sha",
        "source_thread_id": "self-test-thread",
        "issued_at": "2026-08-10T00:00:00+08:00",
        "scope": "BASE_H180_OUT2_FULL_TARGET_RULE_SCREEN_SINGLE_48_INFERENCE",
        "run_id": runner.RUN_ID,
        "run_root": str(runner.RUN_ROOT),
        "authorized_commands": ["infer-new-rules"],
        "spec_sha256": sha256(runner.SPEC),
        "runner_sha256": sha256(Path(runner.__file__)),
        "scorer_sha256": sha256(Path(__file__)),
        "prepare_receipt_sha256": sha256(runner.PREP_RECEIPT),
        "model_receipt_sha256": runner.MODEL_RECEIPT_SHA,
        **runner.EXPECTED,
    }
    with tempfile.TemporaryDirectory() as temporary_directory:
        normal_path = Path(temporary_directory) / "normal_ticket.json"
        blank_path = Path(temporary_directory) / "blank_ticket.json"
        normal_path.write_text(
            json.dumps(ticket, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        runner.validate_ticket(normal_path, require_run_root_absent=False)
        blank = dict(ticket)
        blank["authorized_by"] = ""
        blank_path.write_text(
            json.dumps(blank, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        try:
            runner.validate_ticket(blank_path, require_run_root_absent=False)
        except RuntimeError as error:
            if str(error) != "TICKET_AUTHORITY_MISSING:authorized_by":
                raise
        else:
            raise RuntimeError("SELF_TEST_BLANK_TICKET_AUTHORITY_NOT_BLOCKED")
    return {
        "status": "PASS_TARGETED_SELF_TEST",
        "request_derivation": runner.verify_request_derivation(),
        "baseline_schema_cases": baseline["mechanical"]["schema_cases"],
        "baseline_evidence_diagnostics_recomputed": True,
        "out_of_allowlist_remains_hard_gate": True,
        "order_and_gap_are_diagnostics": True,
        "blind_queue_order_invariant_and_identity_free": True,
        "fresh_queue_rebuild_blocks_synchronized_tamper": True,
        "complete_runner_ticket_validation_normal_path": "PASS",
        "empty_authority_ticket_rejected": True,
        "decimal_boundary_0_513369_minus_0_493369_selects_rule2": True,
        "selection_branches": "PASS_DECIMAL_FIXED_POINT",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("static-check", "self-test", "pre", "final"))
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    if args.command == "static-check":
        if args.adjudications is not None:
            raise RuntimeError("STATIC_CHECK_TAKES_NO_ADJUDICATIONS")
        print(
            json.dumps(
                {
                    "status": "PASS_STATIC_INPUTS",
                    "inputs": runner.verify_static_inputs(),
                    "baseline": verify_frozen_baseline(),
                    "reusable_semantic_decision_keys": len(reusable_decisions()),
                    "run_root_exists": RUN_ROOT.exists(),
                },
                ensure_ascii=False,
            )
        )
        return
    if args.command == "self-test":
        if args.adjudications is not None:
            raise RuntimeError("SELF_TEST_TAKES_NO_ADJUDICATIONS")
        print(json.dumps(self_test(), ensure_ascii=False))
        return
    score(args.adjudications, args.command == "final")


if __name__ == "__main__":
    main()
