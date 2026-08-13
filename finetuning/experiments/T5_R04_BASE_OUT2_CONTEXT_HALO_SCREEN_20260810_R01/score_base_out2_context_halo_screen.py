#!/usr/bin/env python3
"""Mechanical gate and blind semantic scoring for the Base OUT2 halo screen."""

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
RUNNER_PATH = Path(__file__).resolve().parent / "run_base_out2_context_halo_screen.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("base_out2_halo_runner", RUNNER_PATH)
if RUNNER_SPEC is None or RUNNER_SPEC.loader is None:
    raise RuntimeError("RUNNER_IMPORT_FAILED")
runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(runner)
RUN_ROOT = runner.RUN_ROOT
RAW = RUN_ROOT / "inference/NEW_HALOS_RAW_48.jsonl"
RESULT = RUN_ROOT / "inference/NEW_HALOS_RESULT.json"
RUN_IDENTITY = RUN_ROOT / "RUN_IDENTITY.json"
EXECUTION_TICKET = RUN_ROOT / "AUTHORIZATION_TICKET.json"
REQUEST_PATHS = {
    120: RUN_ROOT / "requests/HALO120_OUT2_READ2_24.jsonl",
    60: RUN_ROOT / "requests/HALO60_OUT2_READ2_24.jsonl",
}
VARIANT_TO_HALO = {value: key for key, value in runner.VARIANTS.items()}
MAX_OUTPUT_TOKENS = 2048


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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
    ).encode("utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_bytes(jsonl_bytes(rows))


def load_wo() -> Any:
    spec = importlib.util.spec_from_file_location("base_out2_halo_wo", runner.WO_SCORER)
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


def parse_facts(raw: str, validator: Draft202012Validator) -> tuple[bool, bool, list[dict[str, Any]]]:
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
        if isinstance(candidate, dict) and isinstance(candidate.get("fact"), str) and candidate["fact"]:
            recovered.append(candidate)
    return json_valid, schema_valid, recovered


def gold_map() -> dict[str, list[dict[str, Any]]]:
    rows = read_jsonl(runner.GOLD)
    cases = [f"C{index:02d}" for index in range(1, 25)]
    if [row.get("case_id") for row in rows] != cases:
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


def target_ids() -> dict[str, set[str]]:
    result = {}
    for row in read_jsonl(runner.TXX):
        result[row["case_id"]] = {unit["id"] for unit in row["target_units"]}
    return result


def mechanical_case(
    row: dict[str, Any], validator: Draft202012Validator, valid_ids: dict[str, set[str]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    json_valid, schema_valid, facts = parse_facts(row["raw_output"], validator)
    duplicates = sum(
        count - 1 for count in Counter(item.get("fact") for item in facts).values() if count > 1
    )
    illegal = sum(
        not isinstance(item.get("evidence_ids"), list)
        or any(value not in valid_ids[row["case_id"]] for value in item.get("evidence_ids", []))
        for item in facts
    )
    return (
        {
            "case_id": row["case_id"],
            "predictions": len(facts),
            "json_valid": json_valid,
            "schema_valid": schema_valid,
            "illegal_evidence_predictions": illegal,
            "duplicate_predictions": duplicates,
            "repetition_detected": duplicates > 0 or repeated_chunk(row["raw_output"]),
            "token_limit_hit": row.get("finish_reason") == "length"
            or row.get("generation_tokens_including_stop", 0) >= MAX_OUTPUT_TOKENS,
        },
        facts,
    )


def mechanical_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {
        "cases": len(rows),
        "strict_json_cases": sum(row["json_valid"] for row in rows),
        "schema_cases": sum(row["schema_valid"] for row in rows),
        "illegal_evidence_predictions": sum(row["illegal_evidence_predictions"] for row in rows),
        "repetition_cases": sum(row["repetition_detected"] for row in rows),
        "token_limit_cases": sum(row["token_limit_hit"] for row in rows),
        "duplicate_predictions": sum(row["duplicate_predictions"] for row in rows),
    }
    result["mechanically_eligible"] = (
        result["cases"] == 24
        and result["strict_json_cases"] == 24
        and result["illegal_evidence_predictions"] == 0
        and result["repetition_cases"] == 0
        and result["token_limit_cases"] == 0
        and result["duplicate_predictions"] == 0
    )
    result["schema_is_reported_not_a_hard_gate"] = True
    return result


def verify_h180_baseline() -> dict[str, Any]:
    rows, projection_sha = runner.exact_h180_projection()
    if len(rows) != 24 or projection_sha != runner.EXPECTED["h180_projection_sha256"]:
        raise RuntimeError("H180_PROJECTION_DRIFT")
    final = read_json(runner.BASE_CONTEXT_FINAL)
    mechanical = final.get("mechanical_variants", {}).get("BASE_READ2")
    semantic = final.get("semantic", {}).get("variants", {}).get("BASE_READ2")
    expected_mechanical = {
        "cases": 24,
        "strict_json_cases": 24,
        "schema_cases": 22,
        "illegal_evidence_predictions": 0,
        "repetition_cases": 0,
        "token_limit_cases": 0,
        "duplicate_predictions": 0,
        "mechanically_eligible": True,
    }
    for key, expected in expected_mechanical.items():
        if mechanical.get(key) != expected:
            raise RuntimeError(f"H180_MECHANICAL_BASELINE_DRIFT:{key}")
    prf = semantic.get("semantic_recoverable")
    if prf != {
        "tp": 93,
        "fp": 154,
        "fn": 187,
        "precision": 0.376518,
        "recall": 0.332143,
        "f1": 0.352941,
    }:
        raise RuntimeError("H180_SEMANTIC_BASELINE_DRIFT")
    return {
        **expected_mechanical,
        "semantic_recoverable": prf,
        "semantic_tp": semantic["semantic_tp"],
        "status_correct": semantic["status_correct"],
        "speaker_correct": semantic["speaker_correct"],
        "evidence_correct": semantic["evidence_correct"],
        "serialized_output_chars": sum(len(row["raw_output"]) for row in rows),
        "source": "FROZEN_H180_BASE_READ2_NO_RERUN",
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
        key = (row.get("case_id"), row.get("prediction_fact_sha256"))
        if key in result or key not in expected:
            raise RuntimeError("ADJUDICATION_DUPLICATE_OR_UNKNOWN_KEY")
        source = expected[key]
        for field in (
            "case_id",
            "prediction_fact",
            "prediction_fact_sha256",
            "input_bundle_sha256",
            "new_halos_raw_sha256",
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
    pending = {}
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
                            "new_halos_raw_sha256": raw_sha,
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
    pending_rows = sorted(
        pending.values(),
        key=lambda row: (row["case_id"], row["prediction_fact_sha256"]),
    )
    return {"variants": variants, "case_metrics": cases}, pending_rows


def verify_execution_identity(raw_sha: str) -> dict[str, Any]:
    for path in (*REQUEST_PATHS.values(), EXECUTION_TICKET, RUN_IDENTITY, RESULT, RAW):
        if not path.is_file():
            raise RuntimeError(f"EXECUTION_IDENTITY_MEMBER_MISSING:{path}")
    ticket_sha = sha256(EXECUTION_TICKET)
    ticket = read_json(EXECUTION_TICKET)
    if set(ticket) != runner.TICKET_KEYS:
        raise RuntimeError("EXECUTION_TICKET_KEYS_DRIFT")
    current = {
        "spec_sha256": sha256(runner.SPEC),
        "runner_sha256": sha256(Path(runner.__file__)),
        "scorer_sha256": sha256(Path(__file__)),
        "prepare_receipt_sha256": sha256(runner.PREP_RECEIPT),
        "model_receipt_sha256": sha256(runner.MODEL_RECEIPT),
    }
    fixed_ticket = {
        "schema_version": "base-out2-context-halo-screen-ticket/1.0",
        "approved": True,
        "scope": "BASE_OUT2_CONTEXT_HALO_SCREEN_SINGLE_48_INFERENCE",
        "run_id": runner.RUN_ID,
        "run_root": str(RUN_ROOT),
        "authorized_commands": ["infer-new-halos"],
        **current,
        **runner.EXPECTED,
    }
    for key, expected in fixed_ticket.items():
        if ticket.get(key) != expected:
            raise RuntimeError(f"EXECUTION_TICKET_FIELD_DRIFT:{key}")
    identity = read_json(RUN_IDENTITY)
    result = read_json(RESULT)
    identity_fixed = {
        "status": "AUTHORIZED_INFERENCE_STARTED",
        "run_id": runner.RUN_ID,
        "ticket_sha256": ticket_sha,
        "ticket_copy_sha256": ticket_sha,
        **current,
        "authorized_commands": ["infer-new-halos"],
        "adapter_loaded": False,
        "retry": 0,
        "api_calls": 0,
    }
    for key, expected in identity_fixed.items():
        if identity.get(key) != expected:
            raise RuntimeError(f"RUN_IDENTITY_FIELD_DRIFT:{key}")
    result_fixed = {
        "status": "PASS_NEW_HALOS_48_INFERENCE",
        "run_id": runner.RUN_ID,
        "rows": 48,
        "rows_by_variant": {variant: 24 for variant in runner.VARIANTS.values()},
        "raw_sha256": raw_sha,
        "request_sha256_by_halo": {
            str(halo): sha256(path) for halo, path in REQUEST_PATHS.items()
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
            "load_scope": "SHARED_UNFINETUNED_BASE_FOR_HALO120_HALO60",
            "gate": {
                "member_count": runner.MODEL_FILE_COUNT,
                "total_bytes": runner.MODEL_TOTAL_BYTES,
                "revision": runner.MODEL_REVISION,
            },
        }
    ]
    if result.get("model_member_gates_before_each_load") != expected_gate:
        raise RuntimeError("MODEL_MEMBER_GATE_DRIFT")
    return {"ticket_sha256": ticket_sha, **current, "model_member_gate": expected_gate[0]}


def source_rows() -> tuple[list[dict[str, Any]], str, str, dict[str, Any]]:
    runner.verify_static_inputs()
    raw_sha = sha256(RAW)
    execution = verify_execution_identity(raw_sha)
    rows = read_jsonl(RAW)
    if len(rows) != 48:
        raise RuntimeError("RAW_ROWS_NOT_48")
    cases = [f"C{index:02d}" for index in range(1, 25)]
    for variant in runner.VARIANTS.values():
        current = [row for row in rows if row.get("variant") == variant]
        if [row.get("case_id") for row in current] != cases:
            raise RuntimeError(f"RAW_VARIANT_CASE_ORDER_DRIFT:{variant}")
        expected_arm = f"HALO{VARIANT_TO_HALO[variant]}"
        if any(row.get("arm") != expected_arm for row in current):
            raise RuntimeError(f"RAW_ARM_DRIFT:{variant}")
    _, projection_sha = runner.exact_h180_projection()
    if projection_sha != runner.EXPECTED["h180_projection_sha256"]:
        raise RuntimeError("RUNTIME_H180_PROJECTION_DRIFT")
    projection_bytes = b"".join(
        line
        for line in runner.PARENT_RAW.read_bytes().splitlines(keepends=True)
        if json.loads(line).get("variant") == "BASE_READ2"
    )
    bundle = projection_bytes + RAW.read_bytes() + b"".join(
        path.read_bytes() for path in REQUEST_PATHS.values()
    )
    return rows, hashlib.sha256(bundle).hexdigest(), raw_sha, execution


def verify_pre_identity(
    raw_sha: str,
    bundle_sha: str,
    pre_metrics_path: Path | None = None,
    pre_queue_path: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], str, str]:
    metrics_path = pre_metrics_path or RUN_ROOT / "scoring/pre/METRICS.json"
    queue_path = pre_queue_path or RUN_ROOT / "scoring/pre/BLIND_QUEUE.jsonl"
    if not metrics_path.is_file() or not queue_path.is_file():
        raise RuntimeError("FINAL_PRE_INPUT_MISSING")
    metrics_sha = sha256(metrics_path)
    queue_sha = sha256(queue_path)
    metrics = read_json(metrics_path)
    if metrics.get("new_halos_raw_sha256") != raw_sha:
        raise RuntimeError("FINAL_RAW_SHA_DRIFT")
    if metrics.get("input_bundle_sha256") != bundle_sha:
        raise RuntimeError("FINAL_INPUT_BUNDLE_SHA_DRIFT")
    if metrics.get("blind_queue_sha256") != queue_sha:
        raise RuntimeError("FINAL_PRE_QUEUE_SHA_DRIFT")
    return metrics, read_jsonl(queue_path), metrics_sha, queue_sha


def select_halo(
    semantic: dict[str, Any], mechanical: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    baseline = verify_h180_baseline()
    candidates = {
        "H180": {
            "f1": baseline["semantic_recoverable"]["f1"],
            "schema_cases": baseline["schema_cases"],
            "halo_chars_each_side_max": 180,
            "source": "FROZEN_REUSE",
        }
    }
    for variant, value in semantic["variants"].items():
        if not mechanical[variant]["mechanically_eligible"]:
            continue
        halo = VARIANT_TO_HALO[variant]
        candidates[f"H{halo}"] = {
            "f1": value["semantic_recoverable"]["f1"],
            "schema_cases": mechanical[variant]["schema_cases"],
            "halo_chars_each_side_max": halo,
            "source": "NEW_INFERENCE",
        }
    best_f1 = max(value["f1"] for value in candidates.values())
    near = [name for name, value in candidates.items() if best_f1 - value["f1"] < 0.02]
    max_schema = max(candidates[name]["schema_cases"] for name in near)
    schema_finalists = [name for name in near if candidates[name]["schema_cases"] == max_schema]
    selected = min(
        schema_finalists,
        key=lambda name: candidates[name]["halo_chars_each_side_max"],
    )
    if len(candidates) == 1:
        branch = "NO_NEW_HALO_QUALIFIED_H180_RETAINED"
    elif len(near) > 1:
        branch = "WITHIN_0.02_SCHEMA_THEN_SHORTER_HALO"
    else:
        branch = "HIGHEST_RECOVERABLE_SEMANTIC_F1"
    return {
        "selected_halo": selected,
        "selection_rule_branch": branch,
        "near_tie_halos": near,
        "tie_threshold_strictly_below": 0.02,
        "candidates": candidates,
        "fixed_output_format": "OUT2-IDLIST",
        "does_not_authorize_training_or_production": True,
        "scope_name_zh": "未微调本地4B+OUT2的本机CONTEXT_HALO Demo",
    }


def score(adjudications: Path | None, final: bool) -> None:
    rows, bundle_sha, raw_sha, execution = source_rows()
    validator = Draft202012Validator(json.loads(runner.SCHEMA.read_text(encoding="utf-8")))
    valid_ids = target_ids()
    mechanical_cases = []
    parsed = {}
    mechanical = {}
    for variant in runner.VARIANTS.values():
        current = []
        for row in (item for item in rows if item["variant"] == variant):
            metrics, facts = mechanical_case(row, validator, valid_ids)
            current.append(metrics)
            parsed[(variant, row["case_id"])] = facts
        mechanical_cases.extend({"variant": variant, **item} for item in current)
        mechanical[variant] = mechanical_summary(current)
    eligible = [
        variant
        for variant in runner.VARIANTS.values()
        if mechanical[variant]["mechanically_eligible"]
    ]
    pre_metrics_sha = pre_queue_sha = adjudications_sha = None
    if final:
        pre_metrics, queue, pre_metrics_sha, pre_queue_sha = verify_pre_identity(
            raw_sha, bundle_sha
        )
        if pre_metrics.get("eligible_new_variants") != eligible:
            raise RuntimeError("FINAL_ELIGIBLE_VARIANTS_DRIFT")
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
    selection = None
    status = "PENDING_BLIND_SEMANTIC_REVIEW"
    if not eligible:
        status = "MECHANICAL_NO_NEW_HALO_QUALIFIED_H180_RETAINED"
        pending = []
        selection = select_halo(semantic, mechanical)
    elif final:
        status = "PASS_CONTEXT_HALO_DEMO_SELECTION_COMPLETE"
        selection = select_halo(semantic, mechanical)
    elif not pending:
        status = "READY_FOR_FINAL_NO_NEW_ADJUDICATIONS"
    output_dir = RUN_ROOT / ("scoring/final" if final else "scoring/pre")
    if output_dir.exists():
        raise RuntimeError(f"OUTPUT_DIR_EXISTS_NO_OVERWRITE:{output_dir}")
    result = {
        "status": status,
        "scope_name_zh": "未微调本地4B+OUT2的本机CONTEXT_HALO Demo",
        "input_bundle_sha256": bundle_sha,
        "new_halos_raw_sha256": raw_sha,
        "gold_sha256": runner.EXPECTED["gold_sha256"],
        "semantic_policy_sha256": runner.EXPECTED["semantic_policy_sha256"],
        "execution_identity": execution,
        "h180_frozen_baseline": verify_h180_baseline(),
        "new_halo_mechanical": mechanical,
        "mechanical_case_metrics": mechanical_cases,
        "eligible_new_variants": eligible,
        "semantic": semantic,
        "semantic_pending": len(pending),
        "blind_queue_sha256": hashlib.sha256(jsonl_bytes(pending)).hexdigest(),
        "selection": selection,
        "schema_is_reported_and_used_only_as_tiebreak": True,
        "reusable_semantic_decision_batches": {
            "BASE_CONTEXT_223": runner.EXPECTED["base_context_decisions_sha256"],
            "READ2_CARRYOVER_R02_381": runner.EXPECTED["read2_r02_sha256"],
        },
        "fixed_output_format": "OUT2-IDLIST",
        "h180_rerun": False,
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
                "schema_version": "base-out2-context-halo-final-receipt/1.0",
                "status": "FINAL_SCORING_COMPLETE",
                "new_halos_raw_sha256": raw_sha,
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("static-check", "pre", "final"))
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    if args.command == "static-check":
        if args.adjudications is not None:
            raise RuntimeError("STATIC_CHECK_TAKES_NO_ADJUDICATIONS")
        result = {
            "status": "PASS_STATIC_INPUTS",
            "inputs": runner.verify_static_inputs(),
            "h180_baseline": verify_h180_baseline(),
            "reusable_semantic_decision_keys": len(reusable_decisions()),
            "run_root_exists": RUN_ROOT.exists(),
        }
        print(json.dumps(result, ensure_ascii=False))
        return
    score(args.adjudications, args.command == "final")


if __name__ == "__main__":
    main()
