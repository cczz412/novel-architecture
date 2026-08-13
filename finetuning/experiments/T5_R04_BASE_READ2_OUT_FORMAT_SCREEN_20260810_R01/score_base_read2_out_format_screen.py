#!/usr/bin/env python3
"""Mechanical gate and blind semantic scoring for BASE+READ2 OUT2/OUT3/OUT4 Demo."""

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


sys.dont_write_bytecode = True
RUNNER_PATH = Path(__file__).resolve().parent / "run_base_read2_out_format_screen.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("base_read2_out_format_runner", RUNNER_PATH)
if RUNNER_SPEC is None or RUNNER_SPEC.loader is None:
    raise RuntimeError("RUNNER_IMPORT_FAILED")
runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(runner)
RUN_ROOT = runner.RUN_ROOT
RAW = RUN_ROOT / "inference/NEW_FORMATS_RAW_48.jsonl"
RESULT = RUN_ROOT / "inference/NEW_FORMATS_RESULT.json"
RUN_IDENTITY = RUN_ROOT / "RUN_IDENTITY.json"
EXECUTION_TICKET = RUN_ROOT / "AUTHORIZATION_TICKET.json"
REQUEST_PATHS = {
    "OUT3-IDRANGE": RUN_ROOT / "requests/OUT3_IDRANGE_READ2_24.jsonl",
    "OUT4-IDQUOTE": RUN_ROOT / "requests/OUT4_IDQUOTE_READ2_24.jsonl",
}
VARIANT_TO_FORMAT = {value: key for key, value in runner.VARIANTS.items()}
STATUS_VALUES = {
    "已发生",
    "正在发生",
    "计划",
    "承诺",
    "条件",
    "推测",
    "误信",
    "否定",
}
MAX_OUTPUT_TOKENS = 2048
RANGE_PATTERN = re.compile(r"^T(\d{2})(?:-T(\d{2}))?$")
ID_PATTERN = re.compile(r"^T\d{2}$")


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
    spec = importlib.util.spec_from_file_location("out_format_wo", runner.WO_SCORER)
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


def gold_map() -> dict[str, list[dict[str, Any]]]:
    rows = read_jsonl(runner.GOLD)
    if [row.get("case_id") for row in rows] != [f"C{i:02d}" for i in range(1, 25)]:
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


def unit_maps() -> tuple[dict[str, list[str]], dict[str, dict[str, str]]]:
    order = {}
    texts = {}
    rows = read_jsonl(runner.TXX)
    if [row.get("case_id") for row in rows] != [f"C{i:02d}" for i in range(1, 25)]:
        raise RuntimeError("TXX_CASE_ORDER_DRIFT")
    for row in rows:
        ids = [unit["id"] for unit in row["target_units"]]
        if ids != [f"T{index:02d}" for index in range(1, len(ids) + 1)]:
            raise RuntimeError(f"TXX_ID_ORDER_DRIFT:{row['case_id']}")
        order[row["case_id"]] = ids
        texts[row["case_id"]] = {unit["id"]: unit["text"] for unit in row["target_units"]}
    return order, texts


def top_level_parse(raw: str) -> tuple[bool, Any]:
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError:
        return False, None
    return isinstance(value, dict), value


def recovered_facts(raw: str, value: Any) -> tuple[bool, list[dict[str, Any]]]:
    if isinstance(value, dict) and isinstance(value.get("facts"), list):
        facts = [
            item
            for item in value["facts"]
            if isinstance(item, dict) and isinstance(item.get("fact"), str) and item["fact"]
        ]
        readable = len(facts) == len(value["facts"])
        return readable, facts
    decoder = json.JSONDecoder()
    facts = []
    for start, character in enumerate(raw):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and isinstance(candidate.get("fact"), str) and candidate["fact"]:
            facts.append(candidate)
    return False, facts


def common_item_schema(item: Any) -> bool:
    return (
        isinstance(item, dict)
        and isinstance(item.get("fact"), str)
        and bool(item["fact"])
        and item.get("status") in STATUS_VALUES
        and (item.get("speaker") is None or isinstance(item.get("speaker"), str))
    )


def range_string_shape_valid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    match = RANGE_PATTERN.fullmatch(value)
    if match is None:
        return False
    return match.group(2) is None or int(match.group(1)) < int(match.group(2))


def schema_valid(value: Any, out_format: str) -> bool:
    if not isinstance(value, dict) or set(value) != {"facts"} or not isinstance(value["facts"], list):
        return False
    expected = (
        {"fact", "status", "speaker", "evidence_ranges"}
        if out_format == "OUT3-IDRANGE"
        else {"fact", "status", "speaker", "unit_ids", "quote"}
    )
    for item in value["facts"]:
        if not common_item_schema(item) or set(item) != expected:
            return False
        if out_format == "OUT3-IDRANGE":
            ranges = item["evidence_ranges"]
            if (
                not isinstance(ranges, list)
                or len(ranges) != 1
                or not range_string_shape_valid(ranges[0])
            ):
                return False
        else:
            ids = item["unit_ids"]
            if not isinstance(ids, list) or not ids or not all(
                isinstance(entry, str) and ID_PATTERN.fullmatch(entry) for entry in ids
            ):
                return False
            if not isinstance(item["quote"], str) or not item["quote"]:
                return False
    return True


def expand_ranges(value: Any, valid_order: list[str]) -> tuple[list[str], bool]:
    if not isinstance(value, list) or len(value) != 1:
        return [], False
    expanded = []
    for entry in value:
        if not range_string_shape_valid(entry):
            return [], False
        match = RANGE_PATTERN.fullmatch(entry)
        assert match is not None
        start = int(match.group(1))
        end = int(match.group(2) or match.group(1))
        if start > end:
            return [], False
        current = [f"T{index:02d}" for index in range(start, end + 1)]
        if any(unit_id not in valid_order for unit_id in current):
            return [], False
        expanded.extend(current)
    if len(expanded) != len(set(expanded)):
        return [], False
    positions = [valid_order.index(unit_id) for unit_id in expanded]
    if positions != sorted(positions):
        return [], False
    return expanded, True


def validate_quote_item(
    item: dict[str, Any], valid_order: list[str], unit_texts: dict[str, str]
) -> tuple[list[str], bool]:
    ids = item.get("unit_ids")
    quote = item.get("quote")
    if (
        not isinstance(ids, list)
        or not ids
        or not all(isinstance(unit_id, str) and unit_id in unit_texts for unit_id in ids)
        or len(ids) != len(set(ids))
        or not isinstance(quote, str)
        or not quote
    ):
        return [], False
    positions = [valid_order.index(unit_id) for unit_id in ids]
    if positions != list(range(positions[0], positions[0] + len(positions))):
        return [], False
    selected_text = "".join(unit_texts[unit_id] for unit_id in ids)
    return ids, quote in selected_text


def mechanical_case(
    row: dict[str, Any], out_format: str, orders: dict[str, list[str]], texts: dict[str, dict[str, str]]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[list[str]]]:
    json_valid, value = top_level_parse(row["raw_output"])
    readable, facts = recovered_facts(row["raw_output"], value)
    full_schema = json_valid and schema_valid(value, out_format)
    evidence_lists = []
    invalid_range = invalid_quote = illegal = 0
    for item in facts:
        if out_format == "OUT3-IDRANGE":
            evidence, valid = expand_ranges(item.get("evidence_ranges"), orders[row["case_id"]])
            invalid_range += not valid
        else:
            evidence, valid = validate_quote_item(
                item, orders[row["case_id"]], texts[row["case_id"]]
            )
            invalid_quote += not valid
        illegal += not valid
        evidence_lists.append(evidence)
    duplicates = sum(
        count - 1 for count in Counter(item.get("fact") for item in facts).values() if count > 1
    )
    metrics = {
        "case_id": row["case_id"],
        "predictions": len(facts),
        "json_valid": json_valid,
        "readable_facts": readable,
        "schema_valid": full_schema,
        "illegal_evidence_predictions": illegal,
        "invalid_range_predictions": invalid_range,
        "invalid_quote_predictions": invalid_quote,
        "duplicate_predictions": duplicates,
        "repetition_detected": duplicates > 0 or repeated_chunk(row["raw_output"]),
        "token_limit_hit": row.get("finish_reason") == "length"
        or row.get("generation_tokens_including_stop", 0) >= MAX_OUTPUT_TOKENS,
    }
    return metrics, facts, evidence_lists


def mechanical_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {
        "cases": len(rows),
        "strict_json_cases": sum(row["json_valid"] for row in rows),
        "readable_facts_cases": sum(row["readable_facts"] for row in rows),
        "schema_cases": sum(row["schema_valid"] for row in rows),
        "illegal_evidence_predictions": sum(row["illegal_evidence_predictions"] for row in rows),
        "invalid_range_predictions": sum(row["invalid_range_predictions"] for row in rows),
        "invalid_quote_predictions": sum(row["invalid_quote_predictions"] for row in rows),
        "repetition_cases": sum(row["repetition_detected"] for row in rows),
        "token_limit_cases": sum(row["token_limit_hit"] for row in rows),
        "duplicate_predictions": sum(row["duplicate_predictions"] for row in rows),
    }
    result["format_qualified"] = (
        result["cases"] == 24
        and result["strict_json_cases"] == 24
        and result["readable_facts_cases"] == 24
        and result["schema_cases"] >= 22
        and result["illegal_evidence_predictions"] == 0
        and result["repetition_cases"] == 0
        and result["token_limit_cases"] == 0
        and result["duplicate_predictions"] == 0
    )
    result["schema_floor_from_out2"] = 22
    return result


def verify_out2_baseline() -> dict[str, Any]:
    rows, projection_sha = runner.exact_read2_projection()
    if projection_sha != runner.EXPECTED["read2_projection_sha256"] or len(rows) != 24:
        raise RuntimeError("OUT2_PROJECTION_DRIFT")
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
    }
    if any(mechanical.get(key) != value for key, value in expected_mechanical.items()):
        raise RuntimeError("OUT2_MECHANICAL_BASELINE_DRIFT")
    prf = semantic.get("semantic_recoverable", {})
    if prf != {
        "tp": 93,
        "fp": 154,
        "fn": 187,
        "precision": 0.376518,
        "recall": 0.332143,
        "f1": 0.352941,
    }:
        raise RuntimeError("OUT2_SEMANTIC_BASELINE_DRIFT")
    return {
        "format_qualified": True,
        "strict_json_cases": 24,
        "readable_facts_cases": 24,
        "schema_cases": 22,
        "illegal_evidence_predictions": 0,
        "repetition_cases": 0,
        "token_limit_cases": 0,
        "duplicate_predictions": 0,
        "semantic_recoverable": prf,
        "semantic_tp": semantic["semantic_tp"],
        "status_correct": semantic["status_correct"],
        "speaker_correct": semantic["speaker_correct"],
        "evidence_correct": semantic["evidence_correct"],
        "serialized_output_chars": sum(len(row["raw_output"]) for row in rows),
        "source": "FROZEN_EXISTING_OUT2_BASE_READ2_NO_RERUN",
    }


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
        "runner_sha256": sha256(runner.Path(runner.__file__)),
        "scorer_sha256": sha256(Path(__file__)),
        "prepare_receipt_sha256": sha256(runner.PREP_RECEIPT),
        "model_receipt_sha256": sha256(runner.MODEL_RECEIPT),
    }
    fixed_ticket = {
        "schema_version": "base-read2-out-format-screen-ticket/1.0",
        "approved": True,
        "scope": "BASE_READ2_OUT_FORMAT_SCREEN_SINGLE_48_INFERENCE",
        "run_id": runner.RUN_ID,
        "run_root": str(RUN_ROOT),
        "authorized_commands": ["infer-new-formats"],
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
        "authorized_commands": ["infer-new-formats"],
        "adapter_loaded": False,
        "retry": 0,
        "api_calls": 0,
    }
    for key, expected in identity_fixed.items():
        if identity.get(key) != expected:
            raise RuntimeError(f"RUN_IDENTITY_FIELD_DRIFT:{key}")
    result_fixed = {
        "status": "PASS_NEW_OUT_FORMATS_48_INFERENCE",
        "run_id": runner.RUN_ID,
        "rows": 48,
        "rows_by_variant": {variant: 24 for variant in runner.VARIANTS.values()},
        "raw_sha256": raw_sha,
        "request_sha256_by_format": {
            out_format: sha256(path) for out_format, path in REQUEST_PATHS.items()
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
            "load_scope": "SHARED_UNFINETUNED_BASE_FOR_OUT3_OUT4",
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
    expected_cases = [f"C{i:02d}" for i in range(1, 25)]
    for variant in runner.VARIANTS.values():
        current = [row for row in rows if row.get("variant") == variant]
        if [row.get("case_id") for row in current] != expected_cases:
            raise RuntimeError(f"RAW_VARIANT_CASE_ORDER_DRIFT:{variant}")
        expected_format = VARIANT_TO_FORMAT[variant]
        if any(row.get("arm") != expected_format for row in current):
            raise RuntimeError(f"RAW_ARM_DRIFT:{variant}")
    if Counter(row.get("variant") for row in rows) != Counter(
        {variant: 24 for variant in runner.VARIANTS.values()}
    ):
        raise RuntimeError("RAW_VARIANT_COUNTS_DRIFT")
    for out_format, path in REQUEST_PATHS.items():
        if sha256(path) != runner.EXPECTED[f"{out_format[:4].lower()}_request_sha256"]:
            raise RuntimeError(f"RUNTIME_REQUEST_SHA_DRIFT:{out_format}")
    out2_bytes = b"".join(
        line
        for line in runner.PARENT_RAW.read_bytes().splitlines(keepends=True)
        if json.loads(line).get("variant") == "BASE_READ2"
    )
    bundle = out2_bytes + RAW.read_bytes() + b"".join(path.read_bytes() for path in REQUEST_PATHS.values())
    return rows, hashlib.sha256(bundle).hexdigest(), raw_sha, execution


def frozen_decisions() -> dict[tuple[str, str], dict[str, Any]]:
    rows = read_jsonl(runner.BASE_CONTEXT_DECISIONS)
    if len(rows) != 223:
        raise RuntimeError("FROZEN_DECISIONS_ROWS_DRIFT")
    result = {}
    for row in rows:
        key = (row.get("case_id"), row.get("prediction_fact_sha256"))
        if key in result or fact_sha(row.get("prediction_fact", "")) != key[1]:
            raise RuntimeError("FROZEN_DECISION_KEY_DRIFT")
        if row.get("category") not in {"SEMANTIC_EQUIVALENT", "NOT_MATCH", "OUT_OF_SCOPE"}:
            raise RuntimeError("FROZEN_DECISION_CATEGORY_DRIFT")
        result[key] = row
    return result


def added_decisions(path: Path | None, queue: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
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
            "new_formats_raw_sha256",
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
    evidence: dict[tuple[str, str], list[list[str]]],
    eligible_variants: list[str],
    bundle_sha: str,
    raw_sha: str,
    added: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    wo = load_wo()
    gold = gold_map()
    frozen = frozen_decisions()
    pending = {}
    cases = []
    for variant in eligible_variants:
        for row in (item for item in rows if item["variant"] == variant):
            case_id = row["case_id"]
            predictions = parsed[(variant, case_id)]
            evidence_lists = evidence[(variant, case_id)]
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
                            "new_formats_raw_sha256": raw_sha,
                            "gold_sha256": runner.EXPECTED["gold_sha256"],
                            "semantic_policy_sha256": runner.EXPECTED["semantic_policy_sha256"],
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
                    (index for index, item in enumerate(expected) if item["fact_id"] == matched_id),
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
                evidence_ok += evidence_lists[prediction_index] == target["evidence_ids"]
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
    if metrics.get("new_formats_raw_sha256") != raw_sha:
        raise RuntimeError("FINAL_RAW_SHA_DRIFT")
    if metrics.get("input_bundle_sha256") != bundle_sha:
        raise RuntimeError("FINAL_INPUT_BUNDLE_SHA_DRIFT")
    if metrics.get("blind_queue_sha256") != queue_sha:
        raise RuntimeError("FINAL_PRE_QUEUE_SHA_DRIFT")
    return metrics, read_jsonl(queue_path), metrics_sha, queue_sha


def choose_format(
    new_semantic: dict[str, Any], mechanical: dict[str, dict[str, Any]], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    out2 = verify_out2_baseline()
    candidates = {
        "OUT2-IDLIST": {
            "f1": out2["semantic_recoverable"]["f1"],
            "schema_cases": out2["schema_cases"],
            "evidence_accuracy": out2["evidence_correct"] / out2["semantic_tp"],
            "serialized_output_chars": out2["serialized_output_chars"],
            "complexity_rank": 1,
        }
    }
    for out_format, variant in runner.VARIANTS.items():
        if not mechanical[variant]["format_qualified"]:
            continue
        semantic = new_semantic["variants"][variant]
        tp = semantic["semantic_tp"]
        candidates[out_format] = {
            "f1": semantic["semantic_recoverable"]["f1"],
            "schema_cases": mechanical[variant]["schema_cases"],
            "evidence_accuracy": semantic["evidence_correct"] / tp if tp else 0.0,
            "serialized_output_chars": sum(
                len(row["raw_output"]) for row in rows if row["variant"] == variant
            ),
            "complexity_rank": {"OUT3-IDRANGE": 2, "OUT4-IDQUOTE": 3}[out_format],
        }
    qualified_new = [name for name in candidates if name != "OUT2-IDLIST"]
    if not qualified_new:
        return {
            "selected_format": "OUT2-IDLIST",
            "selection_rule_branch": "NO_NEW_FORMAT_QUALIFIED_OUT2_RETAINED",
            "near_tie_formats": ["OUT2-IDLIST"],
            "tie_threshold_strictly_below": 0.02,
            "candidates": candidates,
            "does_not_authorize_out_or_training": True,
            "scope_name_zh": "未微调本地4B+READ2+REAL24输出形式Demo",
        }
    if max(candidates[name]["f1"] for name in qualified_new) <= candidates["OUT2-IDLIST"]["f1"]:
        return {
            "selected_format": "OUT2-IDLIST",
            "selection_rule_branch": "NO_NEW_FORMAT_IMPROVED_OUT2_RETAINED",
            "near_tie_formats": ["OUT2-IDLIST"],
            "tie_threshold_strictly_below": 0.02,
            "candidates": candidates,
            "does_not_authorize_out_or_training": True,
            "scope_name_zh": "未微调本地4B+READ2+REAL24输出形式Demo",
        }
    best_f1 = max(value["f1"] for value in candidates.values())
    near = [name for name, value in candidates.items() if best_f1 - value["f1"] < 0.02]
    selected = sorted(
        near,
        key=lambda name: (
            -candidates[name]["schema_cases"],
            -candidates[name]["evidence_accuracy"],
            candidates[name]["serialized_output_chars"],
            candidates[name]["complexity_rank"],
        ),
    )[0]
    branch = "HIGHEST_RECOVERABLE_SEMANTIC_F1"
    if len(near) > 1:
        branch = "WITHIN_0.02_SCHEMA_THEN_EVIDENCE_THEN_SHORTER_SIMPLER"
    return {
        "selected_format": selected,
        "selection_rule_branch": branch,
        "near_tie_formats": near,
        "tie_threshold_strictly_below": 0.02,
        "candidates": candidates,
        "does_not_authorize_out_or_training": True,
        "scope_name_zh": "未微调本地4B+READ2+REAL24输出形式Demo",
    }


def score(adjudications: Path | None, final: bool) -> None:
    rows, bundle_sha, raw_sha, execution = source_rows()
    orders, texts = unit_maps()
    mechanical_cases = []
    parsed = {}
    evidence = {}
    mechanical = {}
    for variant in runner.VARIANTS.values():
        current = []
        out_format = VARIANT_TO_FORMAT[variant]
        for row in (item for item in rows if item["variant"] == variant):
            metrics, facts, evidence_lists = mechanical_case(row, out_format, orders, texts)
            metrics["variant"] = variant
            current.append(metrics)
            parsed[(variant, row["case_id"])] = facts
            evidence[(variant, row["case_id"])] = evidence_lists
        mechanical_cases.extend(current)
        mechanical[variant] = mechanical_summary(current)
    eligible = [variant for variant in runner.VARIANTS.values() if mechanical[variant]["format_qualified"]]
    pre_metrics_sha = pre_queue_sha = adjudications_sha = None
    if final:
        pre_metrics, queue, pre_metrics_sha, pre_queue_sha = verify_pre_identity(
            raw_sha, bundle_sha
        )
        if queue and adjudications is None:
            raise RuntimeError("FINAL_ADJUDICATIONS_REQUIRED")
        adjudications_sha = sha256(adjudications) if adjudications is not None else None
        added = added_decisions(adjudications, queue)
    else:
        if adjudications is not None:
            raise RuntimeError("PRE_DOES_NOT_ACCEPT_ADJUDICATIONS")
        added = {}
    semantic, pending = semantic_score(rows, parsed, evidence, eligible, bundle_sha, raw_sha, added)
    selection = None
    if final and pending:
        raise RuntimeError("FINAL_SEMANTIC_PENDING_NOT_ZERO")
    if final or not eligible:
        selection = choose_format(semantic, mechanical, rows) if not pending else None
    status = "PENDING_BLIND_SEMANTIC_REVIEW"
    if not eligible:
        status = "MECHANICAL_NO_NEW_FORMAT_QUALIFIED_OUT2_RETAINED"
        pending = []
    elif final:
        status = "PASS_OUT_FORMAT_DEMO_SELECTION_COMPLETE"
    output_dir = RUN_ROOT / ("scoring/final" if final else "scoring/pre")
    result = {
        "status": status,
        "scope_name_zh": "未微调本地4B+READ2+REAL24输出形式Demo",
        "input_bundle_sha256": bundle_sha,
        "new_formats_raw_sha256": raw_sha,
        "gold_sha256": runner.EXPECTED["gold_sha256"],
        "semantic_policy_sha256": runner.EXPECTED["semantic_policy_sha256"],
        "execution_identity": execution,
        "out2_frozen_baseline": verify_out2_baseline(),
        "new_format_mechanical": mechanical,
        "mechanical_case_metrics": mechanical_cases,
        "eligible_new_variants": eligible,
        "semantic": semantic,
        "semantic_pending": len(pending),
        "blind_queue_sha256": hashlib.sha256(jsonl_bytes(pending)).hexdigest(),
        "selection": selection,
        "quote_gold_standard_created": False,
        "out2_rerun": False,
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
                "schema_version": "base-read2-out-format-screen-final-receipt/1.0",
                "status": "FINAL_SCORING_COMPLETE",
                "new_formats_raw_sha256": raw_sha,
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
            "out2_baseline": verify_out2_baseline(),
            "run_root_exists": RUN_ROOT.exists(),
        }
        print(json.dumps(result, ensure_ascii=False))
        return
    score(args.adjudications, args.command == "final")


if __name__ == "__main__":
    main()
