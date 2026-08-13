#!/usr/bin/env python3
"""WO-01 三臂专用 scorer；不认识历史 arm，也不运行模型。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import re
import sys
import unicodedata
from typing import Any

from jsonschema import Draft202012Validator

sys.dont_write_bytecode = True

import run_wo01_scope_probe as runner  # noqa: E402


REPO = Path(__file__).resolve().parents[4]
EXP = Path(__file__).resolve().parents[1]
R01 = REPO / "finetuning/experiments/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_PREFLIGHT_20260808_R01"
CANONICAL = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/set_b_r03_work/sealed/T5_R04_SYNTHETIC_MICRO24_SET_B_R03_20260808/canonical/CANONICAL_MICRO24_SET_B_R03.jsonl"
SCHEMA = REPO / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
ADJUDICATION_SCHEMA = EXP / "SEMANTIC_ADJUDICATION_SCHEMA.json"
P3_SCORER = REPO / "finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01/tools/score_p3_context_probe.py"
M1_DETERMINISTIC = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/m1_r01/tools/score_m1_deterministic.py"
M1_SEMANTIC = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/m1_r01/tools/adjudicate_and_score_m1.py"

ARMS = ("TARGET_ONLY", "SMALL_HALO", "CURRENT_WINDOW")
ALLOWED_STATUS = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}
REQUIRED_KEYS = {"fact", "status", "speaker", "evidence_ids"}
SEMANTIC_EQUIVALENT = "SEMANTIC_EQUIVALENT"
PARTIAL_CATEGORIES = {
    "PARTIALLY_CORRECT_OVER_BROAD",
    "PARTIALLY_CORRECT_UNDER_SPECIFIED",
}
NONMATCH_CATEGORIES = {
    "WRONG",
    "EXTRA_BUT_TEXT_SUPPORTED_FACT",
    "HALLUCINATED",
    "UNCLEAR",
}
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 2026080801
EXPECTED = {
    "canonical": "fa04ce5e5f819f4f87aec248ef8c306541b04128d67f0b79cc7e61f2d401d7d9",
    "schema": "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14",
    "p3_scorer": "c7df1d96d785122d7af818c39c168be646298aa158cfa698102f24e4094e6674",
    "m1_deterministic": "cced79b678fe563665a7b007077eccf9dae7e6696916f9235293b80a5c9a4e43",
    "m1_semantic": "5e2751ea56e009d0139acc68c90bd64d356584ef0e7cd862413530222779dc09",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    return runner.strict_json_loads(path.read_bytes())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [runner.strict_json_loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"".join(
            (
                json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                + "\n"
            ).encode("utf-8")
            for row in rows
        )
    )


def verify_sources() -> dict[str, str]:
    paths = {
        "canonical": CANONICAL,
        "schema": SCHEMA,
        "p3_scorer": P3_SCORER,
        "m1_deterministic": M1_DETERMINISTIC,
        "m1_semantic": M1_SEMANTIC,
    }
    result = {}
    for source_id, path in paths.items():
        actual = sha256(path)
        if actual != EXPECTED[source_id]:
            raise RuntimeError(f"SCORER_SOURCE_SHA_DRIFT:{source_id}:{actual}")
        result[source_id] = actual
    return result


def normalize_fact(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKC", value)
    return "".join(
        character
        for character in value
        if not unicodedata.category(character).startswith(("P", "S", "Z"))
    )


def prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def one_to_one_fact_match(
    gold: list[dict[str, Any]],
    predicted: list[dict[str, Any]],
    *,
    normalized: bool,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    key = (
        (lambda row: normalize_fact(row.get("fact")))
        if normalized
        else (lambda row: row.get("fact") if isinstance(row.get("fact"), str) else "")
    )
    gold_by_key: dict[str, list[int]] = defaultdict(list)
    for gold_index, row in enumerate(gold):
        gold_by_key[key(row)].append(gold_index)
    used: set[int] = set()
    pairs = []
    unmatched_predictions = []
    for prediction_index, row in enumerate(predicted):
        value = key(row)
        candidates = [index for index in gold_by_key.get(value, []) if index not in used]
        if value and candidates:
            used.add(candidates[0])
            pairs.append((prediction_index, candidates[0]))
        else:
            unmatched_predictions.append(prediction_index)
    return pairs, unmatched_predictions, [index for index in range(len(gold)) if index not in used]


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
        if isinstance(value, dict) and isinstance(value.get("fact"), str):
            found.append(value)
    return found


def repeated_chunk(raw: str) -> bool:
    compact = re.sub(r"\s+", "", raw)
    if len(compact) < 240:
        return False
    windows = Counter(
        compact[index : index + 80] for index in range(0, len(compact) - 79, 8)
    )
    return any(count >= 3 for count in windows.values())


def analyze_raw(raw: str, schema: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = runner.strict_json_loads(raw.strip())
        json_valid = True
    except (json.JSONDecodeError, RuntimeError):
        parsed = None
        json_valid = False
    schema_errors = []
    if json_valid:
        validator = Draft202012Validator(schema)
        schema_errors = sorted(
            error.json_path + ":" + error.validator
            for error in validator.iter_errors(parsed)
        )
    else:
        schema_errors = ["json_parse"]
    schema_valid = not schema_errors
    structured = parsed.get("facts", []) if schema_valid else []
    recovered = scan_fact_objects(raw)
    keys = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in recovered]
    duplicate_objects = sum(count - 1 for count in Counter(keys).values() if count > 1)
    return {
        "json_valid": json_valid,
        "schema_valid": schema_valid,
        "schema_errors": schema_errors,
        "parsed_output": parsed,
        "structured_fact_objects": structured,
        "recovered_fact_objects": recovered,
        "exact_duplicate_fact_object_count": duplicate_objects,
        "repetition_detected": duplicate_objects > 0 or repeated_chunk(raw),
    }


def canonical_map() -> dict[str, dict[str, Any]]:
    rows = read_jsonl(CANONICAL)
    if len(rows) != 24 or len({row["case_id"] for row in rows}) != 24:
        raise RuntimeError("CANONICAL_NOT_24_UNIQUE_CASES")
    if sum(len(row["facts"]) for row in rows) != 48:
        raise RuntimeError("CANONICAL_NOT_48_GOLD_FACTS")
    return {row["case_id"]: row for row in rows}


def gold_rows(case: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "fact_id": row["fact_id"],
            "fact": row["fact_sentence"],
            "status": row["status"],
            "speaker": row["speaker"],
            "evidence_ids": row["evidence"]["unit_ids"],
        }
        for row in case["facts"]
    ]


def adjudication_index(
    rows: list[dict[str, Any]],
    source_raw_sha256: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    schema = read_json(ADJUDICATION_SCHEMA)
    validator = Draft202012Validator(schema)
    canonical = canonical_map()
    index = {}
    for row in rows:
        errors = sorted(error.message for error in validator.iter_errors(row))
        if errors:
            raise RuntimeError(f"SEMANTIC_ADJUDICATION_SCHEMA_INVALID:{errors}")
        case_id = row["case_id"]
        if case_id not in canonical:
            raise RuntimeError(f"SEMANTIC_ADJUDICATION_UNKNOWN_CASE:{case_id}")
        if row["source_raw_sha256"] != source_raw_sha256:
            raise RuntimeError("SEMANTIC_ADJUDICATION_RAW_IDENTITY_MISMATCH")
        if text_sha256(row["prediction_fact"]) != row["prediction_fact_sha256"]:
            raise RuntimeError("SEMANTIC_ADJUDICATION_PREDICTION_SHA_MISMATCH")
        gold_ids = {fact["fact_id"] for fact in canonical[case_id]["facts"]}
        category = row["category"]
        matched = row["matched_gold_fact_id"]
        counts_as_tp = row["counts_as_tp"]
        if category == SEMANTIC_EQUIVALENT:
            if not counts_as_tp or matched not in gold_ids:
                raise RuntimeError("SEMANTIC_EQUIVALENT_BINDING_INVALID")
        elif category in PARTIAL_CATEGORIES:
            if counts_as_tp or matched not in gold_ids:
                raise RuntimeError("SEMANTIC_PARTIAL_BINDING_INVALID")
        elif category in NONMATCH_CATEGORIES:
            if counts_as_tp or matched is not None:
                raise RuntimeError("SEMANTIC_NONMATCH_BINDING_INVALID")
        else:
            raise RuntimeError(f"SEMANTIC_ADJUDICATION_CATEGORY_UNKNOWN:{category}")
        key = (case_id, row["prediction_fact_sha256"])
        if key in index:
            raise RuntimeError(f"SEMANTIC_ADJUDICATION_DUPLICATE:{key}")
        index[key] = row
    return index


def semantic_pairs(
    case_id: str,
    gold: list[dict[str, Any]],
    predicted: list[dict[str, Any]],
    decisions: dict[tuple[str, str], dict[str, Any]],
) -> tuple[list[tuple[int, int]], list[dict[str, Any]]]:
    pairs, unmatched, _ = one_to_one_fact_match(gold, predicted, normalized=True)
    used_gold = {gold_index for _, gold_index in pairs}
    queue = []
    gold_by_id = {row["fact_id"]: index for index, row in enumerate(gold)}
    for prediction_index in unmatched:
        prediction = predicted[prediction_index]
        fact = prediction.get("fact") if isinstance(prediction.get("fact"), str) else ""
        prediction_sha = text_sha256(fact)
        key = (case_id, prediction_sha)
        decision = decisions.get(key)
        if decision is None:
            queue.append(
                {
                    "case_id": case_id,
                    "prediction_index": prediction_index,
                    "prediction_fact": fact,
                    "prediction_fact_sha256": prediction_sha,
                    "same_case_review_required": True,
                }
            )
            continue
        gold_id = decision.get("matched_gold_fact_id")
        if decision.get("counts_as_tp") and gold_id in gold_by_id:
            gold_index = gold_by_id[gold_id]
            if gold_index not in used_gold:
                used_gold.add(gold_index)
                pairs.append((prediction_index, gold_index))
    return sorted(pairs), queue


def score_case(
    raw_row: dict[str, Any],
    case: dict[str, Any],
    schema: dict[str, Any],
    decisions: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    arm = raw_row["arm"]
    case_id = raw_row["case_id"]
    if arm not in ARMS or case_id != case["case_id"]:
        raise RuntimeError("RAW_CASE_IDENTITY_MISMATCH")
    analysis = analyze_raw(raw_row["raw_output"], schema)
    gold = gold_rows(case)
    recovered = analysis["recovered_fact_objects"]
    structured = analysis["structured_fact_objects"]
    strict_pairs, _, strict_missing = one_to_one_fact_match(
        gold, structured, normalized=False
    )
    recoverable_pairs, semantic_queue = semantic_pairs(
        case_id, gold, recovered, decisions
    )
    structured_pairs, structured_queue = semantic_pairs(
        case_id, gold, structured, decisions
    )
    structured_queue_keys = {
        (row["prediction_index"], row["prediction_fact_sha256"])
        for row in structured_queue
    }
    semantic_queue = [
        row
        for row in semantic_queue
        if (row["prediction_index"], row["prediction_fact_sha256"])
        not in structured_queue_keys
    ] + structured_queue

    valid_ids = [unit["id"] for unit in case["micro_atomizer"]["target_units"]]
    evidence = Counter()
    for prediction in recovered:
        ids = prediction.get("evidence_ids") if isinstance(prediction.get("evidence_ids"), list) else []
        evidence["all_ids"] += len(ids)
        evidence["valid_ids"] += sum(item in valid_ids for item in ids)
        evidence["nonexistent_ids"] += sum(item not in valid_ids for item in ids)
        evidence["read_only_ids"] += sum(
            isinstance(item, str) and item.startswith("B") for item in ids
        )

    status_correct = speaker_correct = evidence_exact = usable = 0
    for prediction_index, gold_index in recoverable_pairs:
        prediction = recovered[prediction_index]
        gold_fact = gold[gold_index]
        status_ok = prediction.get("status") == gold_fact["status"]
        speaker_ok = prediction.get("speaker") == gold_fact["speaker"]
        evidence_ok = prediction.get("evidence_ids") == gold_fact["evidence_ids"]
        status_correct += status_ok
        speaker_correct += speaker_ok
        evidence_exact += evidence_ok
        usable += analysis["schema_valid"] and status_ok and speaker_ok and evidence_ok

    required_present = sum(
        len(REQUIRED_KEYS & set(row)) for row in recovered if isinstance(row, dict)
    )
    gold_count = len(gold)
    strict_tp = len(strict_pairs)
    recoverable_tp = len(recoverable_pairs)
    structured_tp = len(structured_pairs)
    context_text = case["source"]["read_only_before"] + case["source"]["read_only_after"]
    context_overlap_candidates = sum(
        isinstance(row.get("fact"), str)
        and bool(row["fact"])
        and row["fact"] in context_text
        and row["fact"] not in case["source"]["target"]
        for row in recovered
    )
    clean_stop = (
        raw_row.get("finish_reason") == "stop"
        and bool(raw_row.get("stop_token_is_eos_eot"))
    )
    return {
        "arm": arm,
        "case_id": case_id,
        "gold_fact_count": gold_count,
        "recovered_prediction_count": len(recovered),
        "structured_prediction_count": len(structured),
        "strict_structured": prf(strict_tp, len(structured) - strict_tp, len(strict_missing)),
        "semantic_recoverable": prf(
            recoverable_tp, len(recovered) - recoverable_tp, gold_count - recoverable_tp
        ),
        "semantic_structured": prf(
            structured_tp, len(structured) - structured_tp, gold_count - structured_tp
        ),
        "end_to_end_usable": prf(usable, len(recovered) - usable, gold_count - usable),
        "semantic_final": not semantic_queue,
        "semantic_pending": semantic_queue,
        "json_valid": analysis["json_valid"],
        "schema_valid": analysis["schema_valid"],
        "schema_errors": analysis["schema_errors"],
        "required_key_recall": {
            "present": required_present,
            "total": len(REQUIRED_KEYS) * len(recovered),
        },
        "status_legality": {
            "legal": sum(row.get("status") in ALLOWED_STATUS for row in recovered),
            "denominator": len(recovered),
        },
        "status_on_semantic_matches": {
            "correct": status_correct,
            "denominator": recoverable_tp,
        },
        "speaker_on_semantic_matches": {
            "correct": speaker_correct,
            "denominator": recoverable_tp,
        },
        "evidence_on_semantic_matches": {
            "exact": evidence_exact,
            "denominator": recoverable_tp,
        },
        "evidence_ids": dict(evidence),
        "read_only_leakage": {
            "evidence_id_cases": int(evidence["read_only_ids"] > 0),
            "text_overlap_candidates": context_overlap_candidates,
        },
        "empty_case_false_positive": bool(not gold and recovered),
        "repetition_detected": analysis["repetition_detected"],
        "exact_duplicate_fact_object_count": analysis[
            "exact_duplicate_fact_object_count"
        ],
        "clean_stop": clean_stop,
        "token_limit_hit": raw_row.get("finish_reason") in {"length", "max_tokens"},
        "finish_reason": raw_row.get("finish_reason"),
    }


def aggregate_case_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 24:
        raise RuntimeError(f"ARM_CASE_DENOMINATOR_NOT_24:{len(rows)}")
    counts = Counter()
    for row in rows:
        for prefix in (
            "strict_structured",
            "semantic_recoverable",
            "semantic_structured",
            "end_to_end_usable",
        ):
            for key in ("tp", "fp", "fn"):
                counts[f"{prefix}_{key}"] += row[prefix][key]
        counts["gold"] += row["gold_fact_count"]
        counts["predictions"] += row["recovered_prediction_count"]
        counts["json"] += row["json_valid"]
        counts["schema"] += row["schema_valid"]
        counts["clean_stop"] += row["clean_stop"]
        counts["repetition"] += row["repetition_detected"]
        counts["token_limit"] += row["token_limit_hit"]
        counts["empty_false_positive"] += row["empty_case_false_positive"]
        counts["read_only_leakage"] += row["read_only_leakage"]["evidence_id_cases"]
        counts["nonexistent_ids"] += row["evidence_ids"].get("nonexistent_ids", 0)
        counts["all_ids"] += row["evidence_ids"].get("all_ids", 0)
        counts["status_correct"] += row["status_on_semantic_matches"]["correct"]
        counts["status_den"] += row["status_on_semantic_matches"]["denominator"]
        counts["speaker_correct"] += row["speaker_on_semantic_matches"]["correct"]
        counts["speaker_den"] += row["speaker_on_semantic_matches"]["denominator"]
        counts["evidence_exact"] += row["evidence_on_semantic_matches"]["exact"]
        counts["evidence_den"] += row["evidence_on_semantic_matches"]["denominator"]
        counts["semantic_pending"] += len(row["semantic_pending"])
    result = {
        "case_count": 24,
        "gold_fact_count": counts["gold"],
        "prediction_count": counts["predictions"],
        "json_parse": {"cases": counts["json"], "denominator": 24},
        "complete_schema": {"cases": counts["schema"], "denominator": 24},
        "strict_structured": prf(
            counts["strict_structured_tp"],
            counts["strict_structured_fp"],
            counts["strict_structured_fn"],
        ),
        "semantic_recoverable": prf(
            counts["semantic_recoverable_tp"],
            counts["semantic_recoverable_fp"],
            counts["semantic_recoverable_fn"],
        ),
        "semantic_structured": prf(
            counts["semantic_structured_tp"],
            counts["semantic_structured_fp"],
            counts["semantic_structured_fn"],
        ),
        "end_to_end_usable": prf(
            counts["end_to_end_usable_tp"],
            counts["end_to_end_usable_fp"],
            counts["end_to_end_usable_fn"],
        ),
        "status": {"correct": counts["status_correct"], "denominator": counts["status_den"]},
        "speaker": {"correct": counts["speaker_correct"], "denominator": counts["speaker_den"]},
        "evidence_binding": {"exact": counts["evidence_exact"], "denominator": counts["evidence_den"]},
        "nonexistent_evidence_ids": {"count": counts["nonexistent_ids"], "all_ids": counts["all_ids"]},
        "read_only_leakage_cases": counts["read_only_leakage"],
        "empty_case_false_positive_cases": counts["empty_false_positive"],
        "termination": {
            "clean_cases": counts["clean_stop"],
            "repetition_cases": counts["repetition"],
            "token_limit_cases": counts["token_limit"],
        },
        "semantic_pending_count": counts["semantic_pending"],
    }
    result["semantic_final"] = counts["semantic_pending"] == 0
    return result


def percentile_type7(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def paired_bootstrap_f1_delta(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    *,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    if len(left) != 24 or len(right) != 24:
        raise RuntimeError("BOOTSTRAP_REQUIRES_24_PAIRED_CASES")
    if [row["case_id"] for row in left] != [row["case_id"] for row in right]:
        raise RuntimeError("BOOTSTRAP_CASE_ORDER_MISMATCH")
    rng = random.Random(seed)
    deltas = []
    for _ in range(samples):
        indices = [rng.randrange(24) for _ in range(24)]
        scores = []
        for rows in (left, right):
            tp = sum(rows[index]["semantic_recoverable"]["tp"] for index in indices)
            fp = sum(rows[index]["semantic_recoverable"]["fp"] for index in indices)
            fn = sum(rows[index]["semantic_recoverable"]["fn"] for index in indices)
            scores.append(prf(tp, fp, fn)["f1"])
        deltas.append(scores[1] - scores[0])
    return {
        "comparison": f"{left[0]['arm']}_TO_{right[0]['arm']}",
        "unit": "paired_case_with_replacement",
        "resampled_cases_per_draw": 24,
        "samples": samples,
        "seed": seed,
        "interval": "two_sided_percentile_type7_95_percent",
        "delta_direction": "right_f1_minus_left_f1",
        "lower_2_5_percent": round(percentile_type7(deltas, 0.025), 6),
        "upper_97_5_percent": round(percentile_type7(deltas, 0.975), 6),
    }


def verify_raw_rows_against_plan(raw_rows: list[dict[str, Any]]) -> None:
    plan = runner.load_execution_plan()
    if len(raw_rows) != 72:
        raise RuntimeError("RAW_NOT_72_ROWS")
    required_identity = {
        "sequence_index",
        "arm",
        "row_index",
        "case_id",
        "request_sha256",
        "gold_binding_sha256",
    }
    seen = set()
    for expected_sequence, (raw, expected) in enumerate(
        zip(raw_rows, plan, strict=True),
        start=1,
    ):
        if not required_identity.issubset(raw):
            raise RuntimeError(f"RAW_IDENTITY_FIELDS_MISSING:{expected_sequence}")
        identity = (
            raw["sequence_index"],
            raw["arm"],
            raw["row_index"],
            raw["case_id"],
            raw["request_sha256"],
            raw["gold_binding_sha256"],
        )
        expected_identity = (
            expected_sequence,
            expected["arm"],
            expected["row_index"],
            expected["case_id"],
            expected["request_sha256"],
            expected["gold_binding_sha256"],
        )
        if identity != expected_identity:
            raise RuntimeError(f"RAW_ROW_IDENTITY_DRIFT:{expected_sequence}")
        if (raw["arm"], raw["row_index"]) in seen:
            raise RuntimeError("RAW_DUPLICATE_ARM_ROW_INDEX")
        seen.add((raw["arm"], raw["row_index"]))


def expected_model_identity_from_receipt() -> dict[str, Any]:
    receipt = runner.read_json(runner.MODEL / "MODEL_RECEIPT.json")
    return {
        "receipt_sha256": runner.EXPECTED["model_receipt"],
        "revision": runner.MODEL_REVISION,
        "verified_member_count": 13,
        "verified_total_bytes": receipt["official_total_bytes"],
        "members": [row["path"] for row in receipt["files"]],
    }


def _safe_file(path: Path, *, root: Path, exact: Path) -> Path:
    runner.assert_safe_path(path, root=root, exact=exact, must_exist=True)
    if not path.is_file():
        raise RuntimeError(f"SCORER_REQUIRED_REGULAR_FILE_MISSING:{path.name}")
    return path


def verify_formal_run_provenance_core(
    run_dir: Path,
    *,
    run_root: Path,
    claims_root: Path,
    ticket_validator: Any,
    process_identity_provider: Any = runner.freeze_process_identity,
    model_identity_provider: Any = expected_model_identity_from_receipt,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    runner.assert_safe_path(run_dir, root=run_root, must_exist=True)
    if not run_dir.is_dir() or run_dir.parent != run_root:
        raise RuntimeError("SCORER_RUN_DIR_NOT_FIXED_CHILD")
    raw_path = _safe_file(run_dir / "RAW_OUTPUTS_72.jsonl", root=run_root, exact=run_dir / "RAW_OUTPUTS_72.jsonl")
    receipt_path = _safe_file(run_dir / "RUN_RECEIPT.json", root=run_root, exact=run_dir / "RUN_RECEIPT.json")
    auth_copy = _safe_file(run_dir / "RUN_AUTHORIZATION_TICKET.json", root=run_root, exact=run_dir / "RUN_AUTHORIZATION_TICKET.json")
    start_path = _safe_file(run_dir / "RUN_START_RECEIPT.json", root=run_root, exact=run_dir / "RUN_START_RECEIPT.json")
    chain_path = _safe_file(run_dir / "RUN_START_CHAIN_RECEIPT.json", root=run_root, exact=run_dir / "RUN_START_CHAIN_RECEIPT.json")
    ticket = ticket_validator(auth_copy, run_dir)
    run_id = ticket["run_id"]
    if run_dir != run_root / run_id:
        raise RuntimeError("SCORER_RUN_ID_DIRECTORY_MISMATCH")
    claim_path = _safe_file(claims_root / f"{run_id}.json", root=run_root, exact=claims_root / f"{run_id}.json")
    claim = read_json(claim_path)
    start = read_json(start_path)
    chain = read_json(chain_path)
    receipt = read_json(receipt_path)
    process_identity = process_identity_provider()
    ticket_sha = sha256(auth_copy)
    plan_sha = runner.execution_plan_identity_sha256()
    common = {
        "run_id": run_id,
        "authorized_output_dir": str(run_dir),
        "authorization_ticket_sha256": ticket_sha,
        "runner_sha256": process_identity["runner_sha256"],
        "r01_manifest_sha256": runner.EXPECTED["r01_manifest"],
        "request_plan_sha256": plan_sha,
        "process_identity_at_start": process_identity,
    }
    if claim != {**common, "status": "RUN_ID_CLAIMED_NO_REUSE"}:
        raise RuntimeError("RUN_CLAIM_IDENTITY_DRIFT")
    if any(start.get(key) != value for key, value in common.items()):
        raise RuntimeError("RUN_START_IDENTITY_DRIFT")
    if (
        start.get("status") != "RUN_STARTED_MODEL_NOT_YET_LOADED"
        or start.get("request_count") != 72
        or start.get("arm_order") != list(ARMS)
        or start.get("claim_sha256") != sha256(claim_path)
        or start.get("authorization_ticket_copy_sha256") != ticket_sha
        or start.get("authorization_validation") != runner.authorization_validation_projection(ticket)
    ):
        raise RuntimeError("RUN_START_CONTRACT_DRIFT")
    expected_chain = {
        "status": "PASS_RUN_START_CHAIN_BOUND_BEFORE_MODEL_LOAD",
        "run_id": run_id,
        "authorization_ticket_copy_sha256": ticket_sha,
        "claim_sha256": sha256(claim_path),
        "run_start_receipt_sha256": sha256(start_path),
        "runner_sha256": process_identity["runner_sha256"],
        "r01_manifest_sha256": runner.EXPECTED["r01_manifest"],
        "request_plan_sha256": plan_sha,
        "process_identity_at_start": process_identity,
    }
    if chain != expected_chain:
        raise RuntimeError("RUN_START_CHAIN_DRIFT")
    expected_receipt = {
        "status": "PASS_WO01_INFERENCE_COMPLETE_PENDING_SCORING",
        "run_id": run_id,
        "cases": 72,
        "arm_order": list(ARMS),
        "request_plan_sha256": plan_sha,
        "r01_manifest_sha256": runner.EXPECTED["r01_manifest"],
        "authorization_ticket_sha256": ticket_sha,
        "authorization_ticket_copy_sha256": ticket_sha,
        "runner_sha256": process_identity["runner_sha256"],
        "claim_sha256": sha256(claim_path),
        "run_start_receipt_sha256": sha256(start_path),
        "run_start_chain_receipt_sha256": sha256(chain_path),
        "model_identity": model_identity_provider(),
        "vendor_identity": process_identity["vendor_identity"],
        "process_identity_at_start": process_identity,
        "process_identity_at_completion": process_identity,
        "resource_controls": {
            "minimum_free_memory_percent": runner.MIN_FREE_MEMORY_PERCENT,
            "mlx_wired_limit_bytes": runner.MLX_WIRED_LIMIT_BYTES,
            "mlx_memory_limit_bytes": runner.MLX_MEMORY_LIMIT_BYTES,
            "mlx_cache_limit_bytes": runner.MLX_CACHE_LIMIT_BYTES,
            "clear_cache_after_each_case": True,
        },
        "retry_count": 0,
        "model_run_authorized": True,
        "training_authorized": False,
        "api_authorized": False,
        "training": False,
        "api_called": False,
    }
    for key, value in expected_receipt.items():
        if receipt.get(key) != value:
            raise RuntimeError(f"RUN_RECEIPT_IDENTITY_MISMATCH:{key}")
    allowed_receipt_keys = set(expected_receipt) | {
        "completed_at",
        "raw_sha256",
        "memory_before",
        "memory_after",
        "peak_mlx_bytes",
        "elapsed_seconds",
    }
    if set(receipt) != allowed_receipt_keys:
        raise RuntimeError("RUN_RECEIPT_FIXED_STRUCTURE_DRIFT")
    raw_sha = sha256(raw_path)
    if receipt.get("raw_sha256") != raw_sha:
        raise RuntimeError("RUN_RECEIPT_RAW_SHA_MISMATCH")
    raw_rows = read_jsonl(raw_path)
    verify_raw_rows_against_plan(raw_rows)
    return {
        "ticket": ticket,
        "run_id": run_id,
        "raw_sha256": raw_sha,
        "run_receipt_sha256": sha256(receipt_path),
        "authorization_ticket_sha256": ticket_sha,
        "runner_sha256": receipt["runner_sha256"],
        "r01_manifest_sha256": receipt["r01_manifest_sha256"],
        "request_plan_sha256": receipt["request_plan_sha256"],
        "execution_contract": process_identity["execution_contract"],
        "vendor_identity": process_identity["vendor_identity"],
        "rows": 72,
    }, raw_rows


def verify_formal_run_provenance(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return verify_formal_run_provenance_core(
        run_dir,
        run_root=runner.RUN_ROOT,
        claims_root=runner.RUN_CLAIMS,
        ticket_validator=runner.validate_authorization_ticket,
    )


def build_blind_queue(
    pending_occurrences: list[dict[str, Any]],
    source_raw_sha256: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blind_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    occurrence_sidecar = []
    for occurrence in pending_occurrences:
        key = (occurrence["case_id"], occurrence["prediction_fact_sha256"])
        public = {
            "case_id": occurrence["case_id"],
            "prediction_fact": occurrence["prediction_fact"],
            "prediction_fact_sha256": occurrence["prediction_fact_sha256"],
            "source_raw_sha256": source_raw_sha256,
            "same_case_review_required": True,
        }
        if key in blind_by_key and blind_by_key[key] != public:
            raise RuntimeError(f"BLIND_QUEUE_CONFLICT:{key}")
        blind_by_key[key] = public
        occurrence_sidecar.append(
            {
                "arm": occurrence["arm"],
                "case_id": occurrence["case_id"],
                "prediction_index": occurrence["prediction_index"],
                "prediction_fact_sha256": occurrence["prediction_fact_sha256"],
                "source_raw_sha256": source_raw_sha256,
            }
        )
    queue = [
        {
            "candidate_id": f"WO01-SEM-{candidate_index:04d}",
            **blind_by_key[key],
        }
        for candidate_index, key in enumerate(sorted(blind_by_key), start=1)
    ]
    return queue, occurrence_sidecar


def score_rows(
    raw_rows: list[dict[str, Any]],
    adjudications: list[dict[str, Any]],
    raw_identity: dict[str, Any],
    *,
    allow_bootstrap: bool,
) -> dict[str, Any]:
    verify_sources()
    canonical = canonical_map()
    schema = read_json(SCHEMA)
    source_raw_sha256 = raw_identity["raw_sha256"]
    decisions = adjudication_index(adjudications, source_raw_sha256)
    if len(raw_rows) != 72 or len({(row.get("arm"), row.get("case_id")) for row in raw_rows}) != 72:
        raise RuntimeError("RAW_NOT_72_UNIQUE_ARM_CASES")
    if Counter(row["arm"] for row in raw_rows) != Counter({arm: 24 for arm in ARMS}):
        raise RuntimeError("RAW_ARM_COUNTS_NOT_24_EACH")
    case_order = list(canonical)
    by_arm: dict[str, list[dict[str, Any]]] = {}
    pending_occurrences = []
    for arm in ARMS:
        arm_rows = [row for row in raw_rows if row["arm"] == arm]
        if [row["case_id"] for row in arm_rows] != case_order:
            raise RuntimeError(f"RAW_CASE_ORDER_DRIFT:{arm}")
        scored = [score_case(row, canonical[row["case_id"]], schema, decisions) for row in arm_rows]
        by_arm[arm] = scored
        pending_occurrences.extend(
            {**item, "arm": arm}
            for row in scored
            for item in row["semantic_pending"]
        )
    queue, occurrence_sidecar = build_blind_queue(
        pending_occurrences,
        source_raw_sha256,
    )
    metrics = {arm: aggregate_case_rows(rows) for arm, rows in by_arm.items()}
    bootstrap = []
    if not queue and allow_bootstrap:
        bootstrap = [
            paired_bootstrap_f1_delta(by_arm["TARGET_ONLY"], by_arm["SMALL_HALO"]),
            paired_bootstrap_f1_delta(by_arm["SMALL_HALO"], by_arm["CURRENT_WINDOW"]),
        ]
    return {
        "status": (
            "PASS_WO01_SCORING_COMPLETE"
            if not queue
            else "HARD_STOP_SEMANTIC_ADJUDICATION_REQUIRED"
        ),
        "semantic_final": not queue,
        "arms": metrics,
        "case_metrics": [row for arm in ARMS for row in by_arm[arm]],
        "semantic_candidate_queue": queue,
        "semantic_candidate_occurrence_sidecar": occurrence_sidecar,
        "paired_bootstrap": bootstrap,
        "raw_identity": raw_identity,
        "bootstrap_contract": {
            "samples": BOOTSTRAP_SAMPLES,
            "seed": BOOTSTRAP_SEED,
            "unit": "paired_case_with_replacement",
            "interval": "two_sided_percentile_type7_95_percent",
            "comparisons": [
                "TARGET_ONLY_TO_SMALL_HALO",
                "SMALL_HALO_TO_CURRENT_WINDOW",
            ],
        },
        "training": False,
        "model_called_by_scorer": False,
    }


def scoring_identity(raw_identity: dict[str, Any]) -> dict[str, Any]:
    identity = raw_identity["execution_contract"]
    ticket = raw_identity["ticket"]
    for key, value in identity.items():
        if ticket.get(key) != value:
            raise RuntimeError(f"SCORER_TICKET_CONTRACT_DRIFT:{key}")
    return identity


def _write_pre_adjudication_core(
    run_dir: Path,
    raw_rows: list[dict[str, Any]],
    raw_identity: dict[str, Any],
) -> dict[str, Any]:
    output_dir = run_dir / "scoring_pre_adjudication"
    private_dir = run_dir / "scoring_private_occurrence"
    blind_dir = run_dir / "blind_review_package"
    if output_dir.exists():
        raise RuntimeError("PRE_ADJUDICATION_OUTPUT_ALREADY_EXISTS")
    if private_dir.exists() or blind_dir.exists():
        raise RuntimeError("PRE_ADJUDICATION_AUX_OUTPUT_ALREADY_EXISTS")
    result = score_rows(
        raw_rows,
        [],
        raw_identity,
        allow_bootstrap=False,
    )
    result["status"] = "PASS_PRE_ADJUDICATION_QUEUE_READY_NOT_FINAL"
    result["semantic_metrics_are_final"] = False
    result["paired_bootstrap"] = []
    output_dir.mkdir()
    private_dir.mkdir()
    blind_dir.mkdir()
    metrics_path = output_dir / "PRE_ADJUDICATION_METRICS.json"
    queue_path = output_dir / "SEMANTIC_CANDIDATE_QUEUE_BLIND.jsonl"
    sidecar_path = private_dir / "SEMANTIC_CANDIDATE_OCCURRENCE_SIDECAR.jsonl"
    private_sidecar = result.pop("semantic_candidate_occurrence_sidecar")
    queue = result.pop("semantic_candidate_queue")
    result.pop("case_metrics")
    write_json(metrics_path, result)
    write_jsonl(queue_path, queue)
    write_jsonl(sidecar_path, private_sidecar)
    write_json(
        private_dir / "AUDIENCE.json",
        {"audience": "SCORER_ONLY", "contains_arm_occurrence_mapping": True},
    )
    canonical = canonical_map()
    casebook_rows = []
    for case_id in sorted({row["case_id"] for row in queue}):
        case = canonical[case_id]
        casebook_rows.append(
            {
                "case_id": case_id,
                "source": case["source"],
                "gold_facts": gold_rows(case),
            }
        )
    blind_queue_path = blind_dir / "SEMANTIC_CANDIDATE_QUEUE_BLIND.jsonl"
    blind_casebook_path = blind_dir / "SAME_CASE_SOURCE_AND_GOLD.jsonl"
    write_jsonl(blind_queue_path, queue)
    write_jsonl(blind_casebook_path, casebook_rows)
    blind_members = [
        {"path": blind_queue_path.name, "bytes": blind_queue_path.stat().st_size, "sha256": sha256(blind_queue_path)},
        {"path": blind_casebook_path.name, "bytes": blind_casebook_path.stat().st_size, "sha256": sha256(blind_casebook_path)},
    ]
    blind_manifest_path = blind_dir / "BLIND_REVIEW_PACKAGE_MANIFEST.json"
    write_json(
        blind_manifest_path,
        {
            "status": "BLIND_REVIEW_PACKAGE_NO_ARM_MAPPING",
            "source_raw_sha256": raw_identity["raw_sha256"],
            "candidate_count": len(queue),
            "members": blind_members,
        },
    )
    identity = scoring_identity(raw_identity)
    receipt = {
        "status": "PASS_PRE_ADJUDICATION_IMMUTABLE_NOT_FINAL",
        "run_id": raw_identity["run_id"],
        "raw_sha256": raw_identity["raw_sha256"],
        "run_receipt_sha256": raw_identity["run_receipt_sha256"],
        "metrics_sha256": sha256(metrics_path),
        "blind_queue_sha256": sha256(queue_path),
        "occurrence_sidecar_sha256": sha256(sidecar_path),
        "blind_review_package_manifest_sha256": sha256(blind_manifest_path),
        "semantic_candidate_count": len(queue),
        "scoring_identity": identity,
        "semantic_metrics_are_final": False,
        "bootstrap_generated": False,
    }
    write_json(output_dir / "PRE_ADJUDICATION_RECEIPT.json", receipt)
    return receipt


def score_pre_adjudication(run_dir: Path) -> dict[str, Any]:
    raw_identity, raw_rows = verify_formal_run_provenance(run_dir)
    return _write_pre_adjudication_core(run_dir, raw_rows, raw_identity)


def _write_final_scoring_core(
    run_dir: Path,
    adjudications_path: Path,
    raw_rows: list[dict[str, Any]],
    raw_identity: dict[str, Any],
) -> dict[str, Any]:
    pre_dir = run_dir / "scoring_pre_adjudication"
    final_dir = run_dir / "scoring_final"
    expected_adjudications = (
        run_dir / "semantic_adjudications/SEMANTIC_ADJUDICATIONS.jsonl"
    )
    if final_dir.exists():
        raise RuntimeError("FINAL_SCORING_OUTPUT_ALREADY_EXISTS")
    if adjudications_path != expected_adjudications or not adjudications_path.is_file():
        raise RuntimeError("FINAL_ADJUDICATION_PATH_NOT_FIXED_OR_MISSING")
    pre_receipt_path = pre_dir / "PRE_ADJUDICATION_RECEIPT.json"
    pre_queue_path = pre_dir / "SEMANTIC_CANDIDATE_QUEUE_BLIND.jsonl"
    pre_metrics_path = pre_dir / "PRE_ADJUDICATION_METRICS.json"
    pre_sidecar_path = run_dir / "scoring_private_occurrence/SEMANTIC_CANDIDATE_OCCURRENCE_SIDECAR.jsonl"
    blind_manifest_path = run_dir / "blind_review_package/BLIND_REVIEW_PACKAGE_MANIFEST.json"
    adjudication_review_receipt_path = adjudications_path.parent / "SEMANTIC_ADJUDICATION_REVIEW_RECEIPT.json"
    for path in (
        adjudications_path,
        pre_receipt_path,
        pre_queue_path,
        pre_metrics_path,
        pre_sidecar_path,
        blind_manifest_path,
        adjudication_review_receipt_path,
    ):
        runner.assert_safe_path(path, root=run_dir.parent, must_exist=True)
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"FINAL_SCORING_INPUT_SYMLINK_OR_NOT_FILE:{path.name}")
    if not all(
        path.is_file()
        for path in (
            pre_receipt_path,
            pre_queue_path,
            pre_metrics_path,
            pre_sidecar_path,
            blind_manifest_path,
            adjudication_review_receipt_path,
        )
    ):
        raise RuntimeError("PRE_ADJUDICATION_EVIDENCE_MISSING")
    pre_receipt = read_json(pre_receipt_path)
    if (
        pre_receipt.get("status") != "PASS_PRE_ADJUDICATION_IMMUTABLE_NOT_FINAL"
        or pre_receipt.get("blind_queue_sha256") != sha256(pre_queue_path)
        or pre_receipt.get("metrics_sha256") != sha256(pre_metrics_path)
        or pre_receipt.get("occurrence_sidecar_sha256") != sha256(pre_sidecar_path)
    ):
        raise RuntimeError("PRE_ADJUDICATION_ARTIFACT_DRIFT")
    if (
        pre_receipt.get("raw_sha256") != raw_identity["raw_sha256"]
        or pre_receipt.get("run_receipt_sha256")
        != raw_identity["run_receipt_sha256"]
    ):
        raise RuntimeError("PRE_ADJUDICATION_RAW_IDENTITY_DRIFT")
    if pre_receipt.get("scoring_identity") != scoring_identity(raw_identity):
        raise RuntimeError("PRE_ADJUDICATION_SCORING_IDENTITY_DRIFT")
    if pre_receipt.get("blind_review_package_manifest_sha256") != sha256(blind_manifest_path):
        raise RuntimeError("BLIND_REVIEW_PACKAGE_DRIFT")
    review_receipt = read_json(adjudication_review_receipt_path)
    if (
        review_receipt.get("status") != "PASS_BLIND_SEMANTIC_REVIEW_COMPLETE"
        or review_receipt.get("blind_review_package_manifest_sha256") != sha256(blind_manifest_path)
        or review_receipt.get("adjudication_sha256") != sha256(adjudications_path)
        or review_receipt.get("source_raw_sha256") != raw_identity["raw_sha256"]
    ):
        raise RuntimeError("SEMANTIC_REVIEW_RECEIPT_BINDING_DRIFT")
    adjudications = read_jsonl(adjudications_path)
    decision_keys = set(
        adjudication_index(adjudications, raw_identity["raw_sha256"])
    )
    queue_rows = read_jsonl(pre_queue_path)
    queue_keys = {
        (row["case_id"], row["prediction_fact_sha256"])
        for row in queue_rows
    }
    if decision_keys != queue_keys:
        raise RuntimeError("FINAL_ADJUDICATION_SET_NOT_EXACT_PRE_QUEUE")
    result = score_rows(
        raw_rows,
        adjudications,
        raw_identity,
        allow_bootstrap=True,
    )
    if not result["semantic_final"] or result["semantic_candidate_queue"]:
        raise RuntimeError("FINAL_SCORING_SEMANTIC_PENDING_NOT_ZERO")
    result["status"] = "PASS_FINAL_SCORING_COMPLETE"
    result["semantic_metrics_are_final"] = True
    final_dir.mkdir()
    metrics_path = final_dir / "FINAL_METRICS.json"
    write_json(metrics_path, result)
    receipt = {
        "status": "PASS_FINAL_SCORING_IMMUTABLE_COMPLETE",
        "run_id": raw_identity["run_id"],
        "raw_sha256": raw_identity["raw_sha256"],
        "run_receipt_sha256": raw_identity["run_receipt_sha256"],
        "pre_adjudication_receipt_sha256": sha256(pre_receipt_path),
        "blind_queue_sha256": sha256(pre_queue_path),
        "adjudication_sha256": sha256(adjudications_path),
        "semantic_adjudication_review_receipt_sha256": sha256(adjudication_review_receipt_path),
        "final_metrics_sha256": sha256(metrics_path),
        "scoring_identity": scoring_identity(raw_identity),
        "semantic_pending": 0,
        "bootstrap_generated": True,
    }
    write_json(final_dir / "FINAL_SCORING_RECEIPT.json", receipt)
    return receipt


def score_final(run_dir: Path, adjudications_path: Path) -> dict[str, Any]:
    runner.assert_safe_path(adjudications_path, root=runner.RUN_ROOT, must_exist=True)
    if adjudications_path.is_symlink():
        raise RuntimeError("FINAL_ADJUDICATION_SYMLINK_FORBIDDEN")
    raw_identity, raw_rows = verify_formal_run_provenance(run_dir)
    return _write_final_scoring_core(
        run_dir,
        adjudications_path,
        raw_rows,
        raw_identity,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("validate", "pre-adjudication", "final-scoring"),
    )
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        print(
            json.dumps(
                {
                    "status": "PASS_WO01_SCORER_SOURCES_BOUND",
                    "sources": verify_sources(),
                    "arms": list(ARMS),
                    "cases_per_arm": 24,
                    "gold_facts": 48,
                    "bootstrap_samples": BOOTSTRAP_SAMPLES,
                    "bootstrap_seed": BOOTSTRAP_SEED,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return
    if args.run_dir is None:
        parser.error("评分需要 --run-dir")
    if args.command == "pre-adjudication":
        print(json.dumps(score_pre_adjudication(args.run_dir), ensure_ascii=False))
        return
    if args.adjudications is None:
        parser.error("final-scoring 需要 --adjudications")
    print(
        json.dumps(
            score_final(args.run_dir, args.adjudications),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
