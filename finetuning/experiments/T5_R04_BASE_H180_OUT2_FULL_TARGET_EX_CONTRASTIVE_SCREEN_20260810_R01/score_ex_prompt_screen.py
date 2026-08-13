#!/usr/bin/env python3
"""Mechanical gate and blind semantic scoring for the single EX arm."""

from __future__ import annotations

import argparse
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
RUNNER_PATH = Path(__file__).resolve().parent / "run_ex_prompt_screen.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("ex_prompt_runner", RUNNER_PATH)
if RUNNER_SPEC is None or RUNNER_SPEC.loader is None:
    raise RuntimeError("EX_RUNNER_IMPORT_FAILED")
runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(runner)
RULE_SCORER_SPEC = importlib.util.spec_from_file_location(
    "stable_rule_scorer", runner.RULE_SCORER_PATH
)
if RULE_SCORER_SPEC is None or RULE_SCORER_SPEC.loader is None:
    raise RuntimeError("STABLE_RULE_SCORER_IMPORT_FAILED")
stable_score = importlib.util.module_from_spec(RULE_SCORER_SPEC)
RULE_SCORER_SPEC.loader.exec_module(stable_score)

RUN_ROOT = runner.RUN_ROOT
RAW = RUN_ROOT / "inference/EX1_RAW_24.jsonl"
RESULT = RUN_ROOT / "inference/EX1_RESULT.json"
RUN_IDENTITY = RUN_ROOT / "RUN_IDENTITY.json"
EXECUTION_TICKET = RUN_ROOT / "AUTHORIZATION_TICKET.json"
REQUEST = RUN_ROOT / "requests/EX_1_CONTRASTIVE_PAIR_REQUESTS_24.jsonl"
BASELINE_F1 = Decimal("0.352941")
BASELINE_RECALL = Decimal("0.332143")
CHALLENGER_F1_GATE = Decimal("0.372941")
COPY_WINDOW_LENGTH = 12


def sha256(path: Path) -> str:
    return runner.sha256(path)


def fact_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return runner.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return runner.read_jsonl(path)


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return runner.jsonl_bytes(rows)


def write_json(path: Path, value: Any) -> None:
    runner.write_json(path, value)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    runner.write_jsonl(path, rows)


def recursive_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            strings.extend(recursive_strings(key))
            strings.extend(recursive_strings(item))
    elif isinstance(value, list):
        for item in value:
            strings.extend(recursive_strings(item))
    elif isinstance(value, str):
        strings.append(value)
    return strings


def terms_in_strings(values: list[str]) -> list[str]:
    return sorted(
        {term for value in values for term in runner.FORBIDDEN_COPY_TERMS if term in value}
    )


def normalized_copy_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def example_body_windows() -> set[str]:
    pair = read_json(runner.PAIR)
    bodies = [
        normalized_copy_text(runner.strip_contract_boilerplate(member["user"]))
        for member in pair["members"]
    ]
    return {
        body[index : index + COPY_WINDOW_LENGTH]
        for body in bodies
        for index in range(max(0, len(body) - COPY_WINDOW_LENGTH + 1))
    }


def fact_body_copy_overlaps(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    body_windows = example_body_windows()
    overlaps = []
    for fact in facts:
        text = fact.get("fact")
        if not isinstance(text, str):
            continue
        normalized = normalized_copy_text(text)
        windows = {
            normalized[index : index + COPY_WINDOW_LENGTH]
            for index in range(max(0, len(normalized) - COPY_WINDOW_LENGTH + 1))
        }
        matching = sorted(windows & body_windows)
        if matching:
            overlaps.append(
                {
                    "prediction_fact_sha256": fact_sha(text),
                    "overlap_windows": matching,
                }
            )
    return overlaps


def copy_leak_diagnostic(raw_output: str, facts: list[dict[str, Any]]) -> dict[str, Any]:
    raw_terms = terms_in_strings([raw_output])
    decoded_strings: list[str] = []
    try:
        decoded_strings = recursive_strings(json.loads(raw_output.strip()))
    except json.JSONDecodeError:
        pass
    decoded_terms = terms_in_strings(decoded_strings)
    recovered_fact_terms = terms_in_strings(recursive_strings(facts))
    combined = sorted(set(raw_terms) | set(decoded_terms) | set(recovered_fact_terms))
    fact_overlaps = fact_body_copy_overlaps(facts)
    return {
        "raw_supplement_terms": raw_terms,
        "decoded_json_string_terms": decoded_terms,
        "recovered_fact_object_terms": recovered_fact_terms,
        "combined_terms": combined,
        "parsed_fact_12_unicode_body_overlaps": fact_overlaps,
        "minimum_contiguous_unicode_copy_length": COPY_WINDOW_LENGTH,
        "copy_leak": bool(combined or fact_overlaps),
        "raw_check_is_supplement_only": True,
    }


def mechanical_case(
    row: dict[str, Any], validator: Draft202012Validator, valid_ids: dict[str, list[str]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metrics, facts = stable_score.mechanical_case(row, validator, valid_ids)
    copy_diagnostic = copy_leak_diagnostic(row["raw_output"], facts)
    metrics["contrastive_example_copy_leak_terms"] = copy_diagnostic["combined_terms"]
    metrics["contrastive_example_fact_12_unicode_copy_overlaps"] = copy_diagnostic[
        "parsed_fact_12_unicode_body_overlaps"
    ]
    metrics["contrastive_example_copy_leak"] = copy_diagnostic["copy_leak"]
    metrics["contrastive_example_copy_diagnostic"] = copy_diagnostic
    return metrics, facts


def mechanical_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = stable_score.mechanical_summary(rows)
    result["contrastive_example_copy_leak_cases"] = sum(
        row["contrastive_example_copy_leak"] for row in rows
    )
    result["contrastive_example_copy_leak_terms"] = sorted(
        {term for row in rows for term in row["contrastive_example_copy_leak_terms"]}
    )
    result["contrastive_example_fact_12_unicode_copy_leak_cases"] = sum(
        bool(row["contrastive_example_fact_12_unicode_copy_overlaps"]) for row in rows
    )
    result["contrastive_example_fact_12_unicode_copy_windows"] = sorted(
        {
            window
            for row in rows
            for overlap in row["contrastive_example_fact_12_unicode_copy_overlaps"]
            for window in overlap["overlap_windows"]
        }
    )
    result["mechanically_eligible"] = (
        result["mechanically_eligible"]
        and result["contrastive_example_copy_leak_cases"] == 0
    )
    result["copy_leak_is_a_hard_gate"] = True
    return result


def frozen_baseline() -> dict[str, Any]:
    baseline = stable_score.verify_frozen_baseline()
    prf = baseline["semantic_recoverable"]
    if prf != {
        "tp": 93,
        "fp": 154,
        "fn": 187,
        "precision": 0.376518,
        "recall": 0.332143,
        "f1": 0.352941,
    }:
        raise RuntimeError("EX0_FROZEN_BASELINE_DRIFT")
    return {
        **baseline,
        "variant": "EX-0-NONE",
        "source": "FROZEN_RULE0_BASELINE_NO_RERUN",
    }


def reusable_decisions() -> dict[tuple[str, str], dict[str, Any]]:
    result = stable_score.reusable_decisions()
    rows = read_jsonl(runner.RULE_R02_ADJUDICATIONS)
    if len(rows) != 478:
        raise RuntimeError("RULE_R02_REUSABLE_ROWS_DRIFT")
    for row in rows:
        text = row.get("prediction_fact", "")
        key = (row.get("case_id"), row.get("prediction_fact_sha256"))
        if fact_sha(text) != key[1]:
            raise RuntimeError("RULE_R02_REUSABLE_FACT_SHA_DRIFT")
        category = row.get("category")
        matched = row.get("matched_gold_fact_id")
        if category not in {"SEMANTIC_EQUIVALENT", "NOT_MATCH", "OUT_OF_SCOPE"}:
            raise RuntimeError("RULE_R02_REUSABLE_CATEGORY_DRIFT")
        if category != "SEMANTIC_EQUIVALENT" and matched is not None:
            raise RuntimeError("RULE_R02_REUSABLE_MATCH_DRIFT")
        compact = {
            "case_id": key[0],
            "prediction_fact": text,
            "prediction_fact_sha256": key[1],
            "category": category,
            "matched_gold_fact_id": matched,
        }
        previous = result.get(key)
        if previous is not None and previous != compact:
            raise RuntimeError(f"REUSABLE_DECISION_CONFLICT:{key[0]}:{key[1]}")
        result[key] = compact
    return result


CANONICAL_ARM_IDENTITIES = {"ex-0-none", "ex-1-contrastive-pair"}
IDENTITY_MARKER = re.compile(
    r"(?:^|[^a-z0-9])(ex[-_]?[01]|arms?|variants?)(?:$|[^a-z0-9])", re.I
)


def contains_identity_marker(value: str) -> bool:
    lowered = value.casefold()
    return any(identity in lowered for identity in CANONICAL_ARM_IDENTITIES) or bool(
        IDENTITY_MARKER.search(value)
    )


def identity_leak(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if contains_identity_marker(str(key)):
                return key
            found = identity_leak(item)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = identity_leak(item)
            if found is not None:
                return found
    elif isinstance(value, str):
        if contains_identity_marker(value):
            return value
    return None


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
    leak = identity_leak(rows)
    if leak is not None:
        raise RuntimeError(f"BLIND_QUEUE_IDENTITY_LEAK:{leak}")


def anonymous_queue(pending: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows = sorted(pending.values(), key=lambda row: (row["case_id"], row["prediction_fact_sha256"]))
    validate_anonymous_queue(rows)
    return rows


def added_decisions(
    path: Path | None, queue: list[dict[str, Any]]
) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None:
        return {}
    rows = read_jsonl(path)
    validate_anonymous_queue(rows)
    expected = {(row["case_id"], row["prediction_fact_sha256"]): row for row in queue}
    result = {}
    for row in rows:
        if fact_sha(row.get("prediction_fact", "")) != row.get("prediction_fact_sha256"):
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
            "source_raw_sha256",
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
    parsed: dict[str, list[dict[str, Any]]],
    eligible: bool,
    bundle_sha: str,
    raw_sha: str,
    added: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not eligible:
        return {"variants": {}, "case_metrics": []}, []
    wo = stable_score.load_wo()
    gold = stable_score.gold_map()
    frozen = reusable_decisions()
    pending: dict[tuple[str, str], dict[str, Any]] = {}
    cases = []
    for row in rows:
        case_id = row["case_id"]
        predictions = parsed[case_id]
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
                        "source_raw_sha256": raw_sha,
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
                "case_id": case_id,
                "gold": len(expected),
                "predictions": len(predictions),
                "semantic_tp": len(pairs),
                "status_correct": status_ok,
                "speaker_correct": speaker_ok,
                "evidence_correct": evidence_ok,
            }
        )
    tp = sum(row["semantic_tp"] for row in cases)
    predictions = sum(row["predictions"] for row in cases)
    gold_count = sum(row["gold"] for row in cases)
    variant = {
        "semantic_recoverable": wo.prf(tp, predictions - tp, gold_count - tp),
        "semantic_tp": tp,
        "predictions": predictions,
        "gold": gold_count,
        "status_correct": sum(row["status_correct"] for row in cases),
        "speaker_correct": sum(row["speaker_correct"] for row in cases),
        "evidence_correct": sum(row["evidence_correct"] for row in cases),
    }
    return {
        "variants": {runner.VARIANT: variant},
        "case_metrics": cases,
    }, anonymous_queue(pending)


def verify_request_result_binding(
    request_path: Path, ticket: dict[str, Any], result: dict[str, Any] | None
) -> str:
    actual_bytes = request_path.read_bytes()
    actual_sha = hashlib.sha256(actual_bytes).hexdigest()
    rebuilt_bytes = runner.jsonl_bytes(runner.build_requests())
    if runner.REQUEST_SHA != runner.EXPECTED["ex1_request_sha256"]:
        raise RuntimeError("RUNNER_REQUEST_CONSTANT_DRIFT")
    if ticket.get("ex1_request_sha256") != runner.REQUEST_SHA:
        raise RuntimeError("TICKET_EX1_REQUEST_SHA_DRIFT")
    if actual_sha != runner.REQUEST_SHA:
        raise RuntimeError("ACTUAL_EX1_REQUEST_SHA_DRIFT")
    if actual_bytes != rebuilt_bytes:
        raise RuntimeError("ACTUAL_EX1_REQUEST_BYTES_DRIFT")
    if result is not None and result.get("request_sha256") != runner.REQUEST_SHA:
        raise RuntimeError("RESULT_EX1_REQUEST_SHA_DRIFT")
    return actual_sha


def require_result_file(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError("EX1_RESULT_MISSING_NOT_SCOREABLE")


def verify_execution_identity(
    *,
    request_path: Path = REQUEST,
    execution_ticket_path: Path = EXECUTION_TICKET,
    run_identity_path: Path = RUN_IDENTITY,
    result_path: Path = RESULT,
    raw_path: Path = RAW,
) -> tuple[str, dict[str, Any]]:
    require_result_file(result_path)
    for path in (request_path, execution_ticket_path):
        if not path.is_file():
            raise RuntimeError(f"EXECUTION_IDENTITY_MEMBER_MISSING:{path}")
    runner.validate_ticket(execution_ticket_path, require_run_root_absent=False)
    ticket = read_json(execution_ticket_path)
    verify_request_result_binding(request_path, ticket, None)
    for path in (run_identity_path, raw_path):
        if not path.is_file():
            raise RuntimeError(f"EXECUTION_IDENTITY_MEMBER_MISSING:{path}")
    result = read_json(result_path)
    request_sha = verify_request_result_binding(request_path, ticket, result)
    raw_sha = sha256(raw_path)
    ticket_sha = sha256(execution_ticket_path)
    current = {
        "spec_sha256": sha256(runner.SPEC),
        "runner_sha256": sha256(Path(runner.__file__)),
        "scorer_sha256": sha256(Path(__file__)),
        "prepare_receipt_sha256": sha256(runner.PREP_RECEIPT),
        "model_receipt_sha256": sha256(runner.stable.MODEL_RECEIPT),
    }
    identity = read_json(run_identity_path)
    identity_fixed = {
        "status": "AUTHORIZED_INFERENCE_STARTED",
        "run_id": runner.RUN_ID,
        "ticket_sha256": ticket_sha,
        "ticket_copy_sha256": ticket_sha,
        **current,
        "authorized_commands": ["infer-ex1"],
        "adapter_loaded": False,
        "retry": 0,
        "api_calls": 0,
    }
    for key, expected in identity_fixed.items():
        if identity.get(key) != expected:
            raise RuntimeError(f"RUN_IDENTITY_FIELD_DRIFT:{key}")
    result_fixed = {
        "status": "PASS_EX1_24_INFERENCE",
        "run_id": runner.RUN_ID,
        "rows": 24,
        "variant": runner.VARIANT,
        "raw_sha256": raw_sha,
        "request_sha256": runner.REQUEST_SHA,
        "fixed_pair_sha256": sha256(runner.PAIR),
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
            "load_scope": "UNFINETUNED_BASE_FOR_EX1_ONLY",
            "gate": {
                "member_count": runner.stable.MODEL_FILE_COUNT,
                "total_bytes": runner.stable.MODEL_TOTAL_BYTES,
                "revision": runner.stable.MODEL_REVISION,
            },
        }
    ]
    if result.get("model_member_gates_before_each_load") != expected_gate:
        raise RuntimeError("MODEL_MEMBER_GATE_DRIFT")
    return raw_sha, {
        "ticket_sha256": ticket_sha,
        "request_sha256": request_sha,
        "request_rebuilt_byte_equal": True,
        **current,
        "ticket_authority_fields_nonempty": True,
        "identity_boundary_zh": "内部身份完整且需控制窗独立run audit",
        "model_member_gate": expected_gate[0],
    }


def source_rows() -> tuple[list[dict[str, Any]], str, str, dict[str, Any]]:
    runner.verify_static_inputs()
    raw_sha, execution = verify_execution_identity()
    rows = read_jsonl(RAW)
    cases = [f"C{index:02d}" for index in range(1, 25)]
    if len(rows) != 24 or [row.get("case_id") for row in rows] != cases:
        raise RuntimeError("EX1_RAW_CASE_ORDER_DRIFT")
    if any(row.get("variant") != runner.VARIANT for row in rows):
        raise RuntimeError("EX1_RAW_VARIANT_DRIFT")
    _, projection_sha, projection_bytes = runner.stable.exact_base_projection()
    if projection_sha != runner.EXPECTED["base_projection_sha256"]:
        raise RuntimeError("EX0_PROJECTION_DRIFT")
    bundle = projection_bytes + RAW.read_bytes() + REQUEST.read_bytes() + runner.PAIR.read_bytes()
    return rows, hashlib.sha256(bundle).hexdigest(), raw_sha, execution


def verify_pre_identity(
    raw_sha: str, bundle_sha: str
) -> tuple[dict[str, Any], list[dict[str, Any]], str, str, bytes]:
    metrics_path = RUN_ROOT / "scoring/pre/METRICS.json"
    queue_path = RUN_ROOT / "scoring/pre/BLIND_QUEUE.jsonl"
    if not metrics_path.is_file() or not queue_path.is_file():
        raise RuntimeError("FINAL_PRE_INPUT_MISSING")
    metrics = read_json(metrics_path)
    metrics_sha = sha256(metrics_path)
    queue_sha = sha256(queue_path)
    if metrics.get("source_raw_sha256") != raw_sha:
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
    if hashlib.sha256(fresh_bytes).hexdigest() != pre_metrics.get("blind_queue_sha256"):
        raise RuntimeError("FINAL_FRESH_QUEUE_SHA_DRIFT")


def selection(semantic: dict[str, Any], mechanical: dict[str, Any]) -> dict[str, Any]:
    score = semantic["variants"].get(runner.VARIANT)
    qualified = False
    if score is not None:
        prf = score["semantic_recoverable"]
        qualified = (
            mechanical["mechanically_eligible"]
            and Decimal(str(prf["recall"])) >= BASELINE_RECALL
            and Decimal(str(prf["f1"])) >= CHALLENGER_F1_GATE
        )
    return {
        "selected_arm": runner.VARIANT if qualified else "EX-0-NONE",
        "branch": "EX1_QUALIFIED_REPLACES_EX0" if qualified else "EX1_NOT_QUALIFIED_EX0_RETAINED",
        "ex1_qualified": qualified,
        "ex1_minimum_recall": str(BASELINE_RECALL),
        "ex1_minimum_f1": str(CHALLENGER_F1_GATE),
        "comparison": "DECIMAL_FIXED_POINT",
        "scope_name_zh": "未微调Base+H180+OUT2+完整责任段+RULE0的EX本机Demo",
        "does_not_authorize_training_or_production": True,
    }


def verify_pre_recomputed_state(
    pre: dict[str, Any],
    baseline: dict[str, Any],
    mechanical: dict[str, Any],
    cases: list[dict[str, Any]],
    eligible: bool,
    semantic: dict[str, Any],
    pending: list[dict[str, Any]],
) -> None:
    expected = {
        "ex0_frozen_baseline": baseline,
        "ex1_mechanical": mechanical,
        "mechanical_case_metrics": cases,
        "ex1_mechanically_eligible": eligible,
        "semantic": semantic,
        "semantic_pending": len(pending),
        "copy_leak_is_a_hard_gate": True,
        "baseline_rerun": False,
    }
    for key, value in expected.items():
        if pre.get(key) != value:
            raise RuntimeError(f"FINAL_PRE_RECOMPUTED_STATE_DRIFT:{key}")


def score(adjudications: Path | None, final: bool) -> None:
    rows, bundle_sha, raw_sha, execution = source_rows()
    validator = Draft202012Validator(json.loads(runner.stable.SCHEMA.read_text(encoding="utf-8")))
    valid_ids = stable_score.target_ids()
    case_metrics = []
    parsed = {}
    for row in rows:
        metrics, facts = mechanical_case(row, validator, valid_ids)
        case_metrics.append(metrics)
        parsed[row["case_id"]] = facts
    mechanical = mechanical_summary(case_metrics)
    eligible = mechanical["mechanically_eligible"]
    baseline = frozen_baseline()
    pre_metrics_sha = pre_queue_sha = adjudications_sha = None
    if final:
        pre, queue, pre_metrics_sha, pre_queue_sha, pre_queue_bytes = verify_pre_identity(
            raw_sha, bundle_sha
        )
        fresh_semantic, fresh_pending = semantic_score(
            rows, parsed, eligible, bundle_sha, raw_sha, {}
        )
        verify_fresh_queue_against_pre(fresh_pending, queue, pre_queue_bytes, pre)
        verify_pre_recomputed_state(
            pre, baseline, mechanical, case_metrics, eligible, fresh_semantic, fresh_pending
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
    if not eligible:
        status = "EX1_MECHANICAL_FAIL_EX0_RETAINED"
        pending = []
    elif final:
        status = "PASS_EX_PROMPT_DEMO_SELECTION_COMPLETE"
    elif pending:
        status = "PENDING_BLIND_SEMANTIC_REVIEW"
    else:
        status = "READY_FOR_FINAL_NO_NEW_ADJUDICATIONS"
    verdict = selection(semantic, mechanical) if final or not eligible else None
    output_dir = RUN_ROOT / ("scoring/final" if final else "scoring/pre")
    if output_dir.exists():
        raise RuntimeError(f"OUTPUT_DIR_EXISTS_NO_OVERWRITE:{output_dir}")
    result = {
        "status": status,
        "scope_name_zh": "未微调Base+H180+OUT2+完整责任段+RULE0的EX本机Demo",
        "input_bundle_sha256": bundle_sha,
        "source_raw_sha256": raw_sha,
        "fixed_pair_sha256": runner.EXPECTED["fixed_pair_sha256"],
        "gold_sha256": runner.EXPECTED["gold_sha256"],
        "semantic_policy_sha256": runner.EXPECTED["semantic_policy_sha256"],
        "execution_identity": execution,
        "ex0_frozen_baseline": baseline,
        "ex1_mechanical": mechanical,
        "mechanical_case_metrics": case_metrics,
        "ex1_mechanically_eligible": eligible,
        "semantic": semantic,
        "semantic_pending": len(pending),
        "blind_queue_sha256": hashlib.sha256(jsonl_bytes(pending)).hexdigest(),
        "selection": verdict,
        "copy_leak_is_a_hard_gate": True,
        "reusable_semantic_decision_batches": {
            "BASE_CONTEXT_223": runner.EXPECTED["base_context_decisions_sha256"],
            "READ2_CARRYOVER_R02_381": runner.EXPECTED["read2_r02_sha256"],
            "RULE_R02_478": runner.EXPECTED["rule_r02_adjudications_sha256"],
        },
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
                "schema_version": "base-h180-out2-full-target-ex-final-receipt/1.0",
                "status": "FINAL_SCORING_COMPLETE",
                "source_raw_sha256": raw_sha,
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
    static = runner.verify_static_inputs()
    baseline = frozen_baseline()
    validator = Draft202012Validator(
        json.loads(runner.stable.SCHEMA.read_text(encoding="utf-8"))
    )
    escaped_copy = (
        '{"facts":[{"fact":"\\u5468\\u68e0出现。","status":"已发生",'
        '"speaker":null,"evidence_ids":["T01"]}]}'
    )
    escaped_metrics, escaped_facts = mechanical_case(
        {
            "case_id": "C01",
            "raw_output": escaped_copy,
            "finish_reason": "stop",
            "generation_tokens_including_stop": 20,
        },
        validator,
        {"C01": ["T01"]},
    )
    escaped_diagnostic = escaped_metrics["contrastive_example_copy_diagnostic"]
    if (
        "周棠" in escaped_copy
        or not escaped_metrics["json_valid"]
        or not escaped_metrics["contrastive_example_copy_leak"]
        or escaped_diagnostic["raw_supplement_terms"]
        or "周棠" not in escaped_diagnostic["decoded_json_string_terms"]
        or "周棠" not in escaped_diagnostic["recovered_fact_object_terms"]
        or escaped_facts[0]["fact"] != "周棠出现。"
    ):
        raise RuntimeError("SELF_TEST_COPY_HARD_GATE_FAILED")
    recovered_copy = (
        'prefix {"fact":"\\u5468\\u68e0出现。","status":"已发生",'
        '"speaker":null,"evidence_ids":["T01"]} suffix'
    )
    recovered_metrics, _ = mechanical_case(
        {
            "case_id": "C01",
            "raw_output": recovered_copy,
            "finish_reason": "stop",
            "generation_tokens_including_stop": 20,
        },
        validator,
        {"C01": ["T01"]},
    )
    if (
        not recovered_metrics["contrastive_example_copy_leak"]
        or "周棠"
        not in recovered_metrics["contrastive_example_copy_diagnostic"][
            "recovered_fact_object_terms"
        ]
    ):
        raise RuntimeError("SELF_TEST_RECOVERED_FACT_COPY_HARD_GATE_FAILED")
    example_body = runner.strip_contract_boilerplate(
        read_json(runner.PAIR)["members"][0]["user"]
    )
    anchor = example_body.index("棚外偶尔")
    exact_twelve = example_body[anchor : anchor + COPY_WINDOW_LENGTH]
    if len(exact_twelve) != COPY_WINDOW_LENGTH or any(
        term in exact_twelve for term in runner.FORBIDDEN_COPY_TERMS
    ):
        raise RuntimeError("SELF_TEST_12_UNICODE_COPY_FIXTURE_DRIFT")

    def one_fact_raw(text: str) -> str:
        return json.dumps(
            {
                "facts": [
                    {
                        "fact": text,
                        "status": "已发生",
                        "speaker": None,
                        "evidence_ids": ["T01"],
                    }
                ]
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    twelve_metrics, _ = mechanical_case(
        {
            "case_id": "C01",
            "raw_output": one_fact_raw(exact_twelve),
            "finish_reason": "stop",
            "generation_tokens_including_stop": 20,
        },
        validator,
        {"C01": ["T01"]},
    )
    twelve_overlaps = twelve_metrics[
        "contrastive_example_fact_12_unicode_copy_overlaps"
    ]
    if (
        not twelve_metrics["contrastive_example_copy_leak"]
        or len(twelve_overlaps) != 1
        or twelve_overlaps[0]["overlap_windows"] != [exact_twelve]
    ):
        raise RuntimeError("SELF_TEST_12_UNICODE_FACT_COPY_HARD_GATE_FAILED")
    eleven_metrics, _ = mechanical_case(
        {
            "case_id": "C01",
            "raw_output": one_fact_raw(exact_twelve[: COPY_WINDOW_LENGTH - 1]),
            "finish_reason": "stop",
            "generation_tokens_including_stop": 20,
        },
        validator,
        {"C01": ["T01"]},
    )
    if (
        eleven_metrics["contrastive_example_copy_leak"]
        or eleven_metrics["contrastive_example_fact_12_unicode_copy_overlaps"]
    ):
        raise RuntimeError("SELF_TEST_11_UNICODE_FACT_COPY_FALSE_POSITIVE")
    sample = {
        ("C01", fact_sha("甲事实")): {
            "case_id": "C01",
            "prediction_fact": "甲事实",
            "prediction_fact_sha256": fact_sha("甲事实"),
            "input_bundle_sha256": "b",
            "source_raw_sha256": "r",
            "gold_sha256": "g",
            "semantic_policy_sha256": "p",
            "candidate_gold_facts": [],
            "category": None,
            "matched_gold_fact_id": None,
        }
    }
    fresh = anonymous_queue(sample)
    identity_tampered_cases = []
    for marker in ("EX0", "EX1", "EX-0-NONE", "EX-1-CONTRASTIVE-PAIR"):
        for location in ("key", "value"):
            candidate = json.loads(json.dumps(fresh, ensure_ascii=False))
            if location == "key":
                candidate[0][f"source_{marker}_note"] = "hidden"
            else:
                candidate[0]["source_note"] = f"hidden {marker} identity"
            try:
                validate_anonymous_queue(candidate)
            except RuntimeError as error:
                if not str(error).startswith("BLIND_QUEUE_IDENTITY_LEAK:"):
                    raise
            else:
                raise RuntimeError(
                    f"SELF_TEST_ANONYMOUS_IDENTITY_LEAK_NOT_BLOCKED:{marker}:{location}"
                )
            identity_tampered_cases.append(candidate)
    tampered = json.loads(json.dumps(fresh, ensure_ascii=False))
    tampered[0]["prediction_fact"] = "被改过的事实"
    tampered[0]["prediction_fact_sha256"] = fact_sha("被改过的事实")
    tampered_bytes = jsonl_bytes(tampered)
    try:
        verify_fresh_queue_against_pre(
            fresh,
            tampered,
            tampered_bytes,
            {"blind_queue_sha256": hashlib.sha256(tampered_bytes).hexdigest()},
        )
    except RuntimeError as error:
        if str(error) != "FINAL_FRESH_QUEUE_BYTES_DRIFT":
            raise
    else:
        raise RuntimeError("SELF_TEST_FRESH_QUEUE_TAMPER_NOT_BLOCKED")
    mechanical = {"mechanically_eligible": True}

    def semantic(f1: float, recall: float) -> dict[str, Any]:
        return {
            "variants": {
                runner.VARIANT: {"semantic_recoverable": {"f1": f1, "recall": recall}}
            }
        }

    if selection(semantic(0.372941, 0.332143), mechanical)["selected_arm"] != runner.VARIANT:
        raise RuntimeError("SELF_TEST_DECIMAL_GATE_BOUNDARY_FAILED")
    if selection(semantic(0.37294, 0.332143), mechanical)["selected_arm"] != "EX-0-NONE":
        raise RuntimeError("SELF_TEST_DECIMAL_GATE_BELOW_BOUNDARY_FAILED")
    ticket = {
        "schema_version": "base-h180-out2-full-target-ex-contrastive-ticket/1.0",
        "approved": True,
        "authorized_by": "CZ_CONTROL_WINDOW",
        "decision_id": "SELF_TEST_ONLY",
        "decision_text_sha256": "self-test-decision-sha",
        "source_thread_id": "self-test-thread",
        "issued_at": "2026-08-10T00:00:00+08:00",
        "scope": "BASE_H180_OUT2_FULL_TARGET_EX_CONTRASTIVE_SINGLE_24_INFERENCE",
        "run_id": runner.RUN_ID,
        "run_root": str(runner.RUN_ROOT),
        "authorized_commands": ["infer-ex1"],
        "spec_sha256": sha256(runner.SPEC),
        "runner_sha256": sha256(Path(runner.__file__)),
        "scorer_sha256": sha256(Path(__file__)),
        "prepare_receipt_sha256": sha256(runner.PREP_RECEIPT),
        "model_receipt_sha256": runner.stable.MODEL_RECEIPT_SHA,
        **runner.EXPECTED,
    }
    with tempfile.TemporaryDirectory() as temporary_directory:
        normal = Path(temporary_directory) / "normal.json"
        blank = Path(temporary_directory) / "blank.json"
        request = Path(temporary_directory) / "request.jsonl"
        result = Path(temporary_directory) / "result.json"
        tampered_result = Path(temporary_directory) / "tampered-result.json"
        raw = Path(temporary_directory) / "raw.jsonl"
        run_identity = Path(temporary_directory) / "run-identity.json"
        missing_result = Path(temporary_directory) / "missing-result.json"
        leaky_adjudications = Path(temporary_directory) / "leaky-adjudications.jsonl"
        normal.write_text(json.dumps(ticket, ensure_ascii=False) + "\n", encoding="utf-8")
        runner.validate_ticket(normal, require_run_root_absent=False)
        for index, identity_tampered in enumerate(identity_tampered_cases):
            leaky_adjudications.write_bytes(jsonl_bytes(identity_tampered))
            try:
                added_decisions(leaky_adjudications, fresh)
            except RuntimeError as error:
                if not str(error).startswith("BLIND_QUEUE_IDENTITY_LEAK:"):
                    raise
            else:
                raise RuntimeError(
                    f"SELF_TEST_ADJUDICATION_IDENTITY_LEAK_NOT_BLOCKED:{index}"
                )
        request.write_bytes(runner.jsonl_bytes(runner.build_requests()))
        try:
            verify_execution_identity(
                request_path=request,
                execution_ticket_path=normal,
                run_identity_path=run_identity,
                result_path=missing_result,
                raw_path=raw,
            )
        except RuntimeError as error:
            if str(error) != "EX1_RESULT_MISSING_NOT_SCOREABLE":
                raise
        else:
            raise RuntimeError("SELF_TEST_REAL_ENTRY_MISSING_RESULT_NOT_BLOCKED")
        raw.write_bytes(b"self-test raw\n")
        ticket_sha = sha256(normal)
        current = {
            "spec_sha256": sha256(runner.SPEC),
            "runner_sha256": sha256(Path(runner.__file__)),
            "scorer_sha256": sha256(Path(__file__)),
            "prepare_receipt_sha256": sha256(runner.PREP_RECEIPT),
            "model_receipt_sha256": sha256(runner.stable.MODEL_RECEIPT),
        }
        write_json(
            run_identity,
            {
                "status": "AUTHORIZED_INFERENCE_STARTED",
                "run_id": runner.RUN_ID,
                "ticket_sha256": ticket_sha,
                "ticket_copy_sha256": ticket_sha,
                **current,
                "authorized_commands": ["infer-ex1"],
                "adapter_loaded": False,
                "retry": 0,
                "api_calls": 0,
            },
        )
        result_value = {
            "status": "PASS_EX1_24_INFERENCE",
            "run_id": runner.RUN_ID,
            "rows": 24,
            "variant": runner.VARIANT,
            "raw_sha256": sha256(raw),
            "request_sha256": runner.REQUEST_SHA,
            "fixed_pair_sha256": sha256(runner.PAIR),
            "ticket_sha256": ticket_sha,
            "ticket_copy_sha256": ticket_sha,
            **current,
            "adapter_loaded": False,
            "retry": 0,
            "api_calls": 0,
            "model_load_count": 1,
            "model_member_gates_before_each_load": [
                {
                    "load_index": 1,
                    "load_scope": "UNFINETUNED_BASE_FOR_EX1_ONLY",
                    "gate": {
                        "member_count": runner.stable.MODEL_FILE_COUNT,
                        "total_bytes": runner.stable.MODEL_TOTAL_BYTES,
                        "revision": runner.stable.MODEL_REVISION,
                    },
                }
            ],
        }
        write_json(result, result_value)
        verified_raw_sha, verified_identity = verify_execution_identity(
            request_path=request,
            execution_ticket_path=normal,
            run_identity_path=run_identity,
            result_path=result,
            raw_path=raw,
        )
        if (
            verified_raw_sha != sha256(raw)
            or verified_identity.get("request_sha256") != runner.REQUEST_SHA
            or verified_identity.get("request_rebuilt_byte_equal") is not True
        ):
            raise RuntimeError("SELF_TEST_REAL_IDENTITY_ENTRY_NORMAL_PATH_FAILED")
        tampered_requests = runner.build_requests()
        tampered_requests[0]["messages"][-1]["content"] += "篡改"
        request.write_bytes(runner.jsonl_bytes(tampered_requests))
        tampered_request_sha = sha256(request)
        result_value["request_sha256"] = tampered_request_sha
        write_json(tampered_result, result_value)
        try:
            verify_execution_identity(
                request_path=request,
                execution_ticket_path=normal,
                run_identity_path=run_identity,
                result_path=tampered_result,
                raw_path=raw,
            )
        except RuntimeError as error:
            if str(error) != "ACTUAL_EX1_REQUEST_SHA_DRIFT":
                raise
        else:
            raise RuntimeError("SELF_TEST_REQUEST_AND_RESULT_TAMPER_NOT_BLOCKED")
        bad = dict(ticket)
        bad["authorized_by"] = ""
        blank.write_text(json.dumps(bad, ensure_ascii=False) + "\n", encoding="utf-8")
        try:
            runner.validate_ticket(blank, require_run_root_absent=False)
        except RuntimeError as error:
            if str(error) != "TICKET_AUTHORITY_MISSING:authorized_by":
                raise
        else:
            raise RuntimeError("SELF_TEST_BLANK_TICKET_NOT_BLOCKED")
    return {
        "status": "PASS_TARGETED_SELF_TEST",
        "request_derivation": static["request_derivation"],
        "pair_validation": static["pair_validation"],
        "anti_copy": static["anti_copy"],
        "baseline_f1": baseline["semantic_recoverable"]["f1"],
        "decoded_and_recovered_copy_hard_gate": "PASS",
        "escaped_unicode_copy_hard_gate": "PASS",
        "parsed_fact_12_unicode_body_copy_hard_gate": "PASS",
        "parsed_fact_11_unicode_non_copy_control": "PASS",
        "anonymous_queue_and_adjudication_ex0_ex1_key_value_leaks_blocked": True,
        "neutral_source_raw_sha256_field_passed": True,
        "request_and_result_joint_tamper_blocked": True,
        "missing_result_status": "EX1_RESULT_MISSING_NOT_SCOREABLE",
        "missing_result_test_used_real_verify_execution_identity_entry": True,
        "fresh_queue_tamper_blocked": True,
        "decimal_gate_boundary": "PASS",
        "complete_ticket_validation": "PASS",
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
                    "baseline": frozen_baseline(),
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
