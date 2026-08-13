#!/usr/bin/env python3
"""Fair scoring-only R02 for the already executed BLOCK300 Stage1 raw."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
SPEC = EXP / "SPEC.json"
PREP_RECEIPT = EXP / "PREPARE_RECEIPT.json"
R01_EXP = ROOT / "finetuning/experiments/T5_R04_BASE_OUT2_BLOCK300_STAGE1_SCREEN_20260810_R01"
R01_SCORER_PATH = R01_EXP / "score_block300_stage1.py"
R01_SCORER_SPEC = importlib.util.spec_from_file_location("block300_r01_scorer_for_fair_r02", R01_SCORER_PATH)
if R01_SCORER_SPEC is None or R01_SCORER_SPEC.loader is None:
    raise RuntimeError("R01_SCORER_IMPORT_FAILED")
r01 = importlib.util.module_from_spec(R01_SCORER_SPEC)
R01_SCORER_SPEC.loader.exec_module(r01)
runner = r01.runner

RUN_ROOT = runner.RUN_ROOT
RAW = runner.RUN_ROOT / "inference/BLOCK300_STAGE1_RAW_22.jsonl"
RESULT = runner.RUN_ROOT / "inference/BLOCK300_STAGE1_RESULT.json"
IDENTITY = runner.RUN_ROOT / "RUN_IDENTITY.json"
TICKET = runner.RUN_ROOT / "AUTHORIZATION_TICKET.json"
SCORING_ROOT = RUN_ROOT / "scoring_r02"
PRE_METRICS = SCORING_ROOT / "pre/METRICS.json"
PRE_QUEUE = SCORING_ROOT / "pre/BLIND_QUEUE.jsonl"
FINAL_METRICS = SCORING_ROOT / "final/METRICS.json"
FINAL_QUEUE = SCORING_ROOT / "final/BLIND_QUEUE.jsonl"

EXPECTED_R01_PACKAGE = {
    R01_EXP / "README.md": "4e05070a3334e681e337f24456c0c30be4340785845276cf5b13c26a7c98345e",
    R01_EXP / "SPEC.json": "83aa7b59394c70621b6ae719ebe528c83a2a4e6835aba4a1a82f38f0f36f13d1",
    R01_EXP / "run_block300_stage1.py": "94012594e122e6403ed2786421170eccd6971bc09044105da1bbdf290f18334f",
    R01_EXP / "score_block300_stage1.py": "711fd7824ea44fafe2afb6d19f5d3a695d1406cab9a50542faafef79cf7f1c13",
    runner.SOURCE_MAP: "33c3efb0d28af06dd2e970a5076c33a06f5d01ea2e0bb646c63da8bdcff06301",
    runner.REQUESTS: "d5943413bae0ae2c3abf6cb1d581f238a5c4162622b7b15547494155789ea168",
    R01_EXP / "PREPARE_RECEIPT.json": "17d340e9c629030d3804bec40d9ae9c20d86c0e49ca4fc9e2c54c4d55e37c850",
}
EXPECTED_R01_RUN = {
    TICKET: "f469994648cc6c1cda8611704c893e99b4ace0a4134716043c6b99c985b8a2a0",
    IDENTITY: "a936409dd80adc38f09197a70003213bbd67107ce786ab147a5a9c5072d612d6",
    RAW: "39999bf84e5ce95b11f7ef63cdc59ec309c7dec7620e3a99d4f3f02481c94b9d",
    RESULT: "0f0e95338e1e5f3293e09c8e03b9f0193a1f51268061c179524609d0dbbba68b",
}
EXPECTED_FROZEN = {
    runner.GOLD: "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    runner.OLD_TXX: "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a",
    runner.PARENT_RAW: "f9bd1fc02f93cfb7c51193f1dc319753472949bc2bbde4360a6779c415cdb28e",
    runner.H180_REQUEST: "126b0f0843fdd244f007a46361397f24f97ce8d71c73d760ae9ad5a6bf5b3088",
    runner.BASE_CONTEXT_FINAL: "f625c10ecf0e1d4be8eade2032dc2fdbe6d398ac55a6ad89f47abffa117825c7",
    runner.SCHEMA: "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14",
    runner.POLICY: "73083a1d91edcc8fadabd2342fc59b89e10ef770aeaa6ffe926867f4f4c39a93",
    runner.WO_SCORER: "eed88ee3c02eb9963cc10f67c06f343415d3a3aed27dd6a71f79e420ccea9d1c",
}
FULL_TARGET_STAGE1_PROJECTION_SHA = "7873faab7047a185acadccf71d304a591e28706fb017a4bd119461cb232a9f99"
MINIMUM_LEGAL_F1 = 0.3693975903614458


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


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


def full_target_stage1_projection_bytes() -> bytes:
    selected = []
    for line in runner.PARENT_RAW.read_bytes().splitlines(keepends=True):
        row = json.loads(line)
        if row.get("variant") == "BASE_READ2" and row.get("case_id") in runner.STAGE_CASES:
            selected.append(line)
    return b"".join(selected)


def full_target_stage1_rows() -> list[dict[str, Any]]:
    return [json.loads(line) for line in full_target_stage1_projection_bytes().splitlines() if line]


def evidence_contract(values: Any, allowed_ids: list[str]) -> dict[str, bool]:
    membership_valid = (
        isinstance(values, list)
        and bool(values)
        and all(isinstance(value, str) and value in allowed_ids for value in values)
    )
    if not membership_valid:
        return {
            "membership_valid": False,
            "order_violation": False,
            "gap_violation": False,
            "duplicate_id_violation": False,
        }
    indexes = [allowed_ids.index(value) for value in values]
    ordered = sorted(indexes)
    unique_ordered = sorted(set(indexes))
    return {
        "membership_valid": True,
        "order_violation": indexes != ordered,
        "gap_violation": unique_ordered != list(range(unique_ordered[0], unique_ordered[-1] + 1)),
        "duplicate_id_violation": len(indexes) != len(set(indexes)),
    }


def evidence_diagnostics(facts_and_allowed: list[tuple[dict[str, Any], list[str]]]) -> dict[str, Any]:
    total = len(facts_and_allowed)
    illegal = order_bad = gap_bad = duplicate_bad = combined = 0
    for fact, allowed in facts_and_allowed:
        contract = evidence_contract(fact.get("evidence_ids"), allowed)
        if not contract["membership_valid"]:
            illegal += 1
            continue
        order_bad += contract["order_violation"]
        gap_bad += contract["gap_violation"]
        duplicate_bad += contract["duplicate_id_violation"]
        combined += contract["order_violation"] or contract["gap_violation"]
    denominator = total or 1
    return {
        "predictions": total,
        "out_of_allowlist_or_empty_or_nonlist": illegal,
        "order_or_gap_violations": combined,
        "order_violations": order_bad,
        "gap_violations": gap_bad,
        "duplicate_id_violations": duplicate_bad,
        "order_accuracy": round((total - illegal - order_bad) / denominator, 6),
        "continuity_accuracy": round((total - illegal - gap_bad) / denominator, 6),
        "contract_accuracy_without_minimality": round((total - illegal - combined) / denominator, 6),
    }


def candidate_mechanical(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    validator = Draft202012Validator(read_json(runner.SCHEMA))
    mappings = {row["request_id"]: row for row in read_jsonl(runner.SOURCE_MAP)}
    parsed: dict[str, list[dict[str, Any]]] = {}
    cases = []
    facts_by_parent: dict[str, list[tuple[str, str]]] = defaultdict(list)
    diagnostic_inputs = []
    for row in rows:
        json_valid, schema_valid, facts = r01.parse_facts(row["raw_output"], validator)
        mapping = mappings[row["request_id"]]
        allowed = [unit["id"] for unit in mapping["target_units"]]
        contracts = [evidence_contract(fact.get("evidence_ids"), allowed) for fact in facts]
        illegal = sum(not contract["membership_valid"] for contract in contracts)
        within_duplicates = sum(count - 1 for count in Counter(fact["fact"] for fact in facts).values() if count > 1)
        facts_by_parent[row["case_id"]].extend((row["request_id"], fact["fact"]) for fact in facts)
        diagnostic_inputs.extend((fact, allowed) for fact in facts)
        parsed[row["request_id"]] = facts
        cases.append(
            {
                "request_id": row["request_id"],
                "case_id": row["case_id"],
                "predictions": len(facts),
                "strict_json": json_valid,
                "complete_schema": schema_valid,
                "out_of_allowlist_or_empty_or_nonlist": illegal,
                "within_block_duplicate_predictions": within_duplicates,
                "repetition_detected": within_duplicates > 0 or r01.repeated_chunk(row["raw_output"]),
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
        "out_of_allowlist_or_empty_or_nonlist_predictions": sum(row["out_of_allowlist_or_empty_or_nonlist"] for row in cases),
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
        and summary["out_of_allowlist_or_empty_or_nonlist_predictions"] == 0
        and summary["repetition_rows"] == 0
        and summary["token_limit_rows"] == 0
        and summary["within_block_duplicate_predictions"] == 0
        and summary["retry"] == 0
    )
    return {
        "summary": summary,
        "evidence_format_diagnostics": evidence_diagnostics(diagnostic_inputs),
        "case_metrics": cases,
    }, parsed


def full_target_evidence_diagnostics() -> dict[str, Any]:
    validator = Draft202012Validator(read_json(runner.SCHEMA))
    old_txx = {row["case_id"]: [unit["id"] for unit in row["target_units"]] for row in read_jsonl(runner.OLD_TXX)}
    rows = full_target_stage1_rows()
    inputs = []
    strict_json = complete_schema = 0
    for row in rows:
        json_valid, schema_valid, facts = r01.parse_facts(row["raw_output"], validator)
        strict_json += json_valid
        complete_schema += schema_valid
        inputs.extend((fact, old_txx[row["case_id"]]) for fact in facts)
    diagnostics = evidence_diagnostics(inputs)
    diagnostics.update({"rows": len(rows), "strict_json_rows": strict_json, "complete_schema_rows": complete_schema})
    return diagnostics


def input_bundle_sha(raw_sha: str) -> str:
    payload = {
        "raw_sha256": raw_sha,
        "r01_ticket_sha256": EXPECTED_R01_RUN[TICKET],
        "r01_run_identity_sha256": EXPECTED_R01_RUN[IDENTITY],
        "r01_result_sha256": EXPECTED_R01_RUN[RESULT],
        "mapping_sha256": EXPECTED_R01_PACKAGE[runner.SOURCE_MAP],
        "requests_sha256": EXPECTED_R01_PACKAGE[runner.REQUESTS],
        "gold_sha256": EXPECTED_FROZEN[runner.GOLD],
        "full_target_stage1_projection_sha256": FULL_TARGET_STAGE1_PROJECTION_SHA,
        "base_context_final_sha256": EXPECTED_FROZEN[runner.BASE_CONTEXT_FINAL],
        "spec_sha256": sha256(SPEC),
        "scorer_sha256": sha256(Path(__file__)),
        "prepare_receipt_sha256": sha256(PREP_RECEIPT),
    }
    return sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def verify_frozen_inputs() -> tuple[list[dict[str, Any]], str, dict[str, Any], dict[str, Any]]:
    for expected in (EXPECTED_R01_PACKAGE, EXPECTED_R01_RUN, EXPECTED_FROZEN):
        if {path: sha256(path) for path in expected} != expected:
            raise RuntimeError("FROZEN_INPUT_SHA_DRIFT")
    runner.verify_static_outputs()
    rows, raw_sha = r01.verify_execution_identity()
    if raw_sha != EXPECTED_R01_RUN[RAW]:
        raise RuntimeError("R01_RAW_SHA_DRIFT")
    projection = full_target_stage1_projection_bytes()
    if len(projection.splitlines()) != 8 or sha256_bytes(projection) != FULL_TARGET_STAGE1_PROJECTION_SHA:
        raise RuntimeError("FULL_TARGET_STAGE1_PROJECTION_DRIFT")
    baseline = r01.baseline_stage1()
    if baseline != {
        "tp": 29,
        "fp": 52,
        "fn": 56,
        "predictions": 81,
        "gold": 85,
        "f1": 0.3493975903614458,
        "source_sha256": EXPECTED_FROZEN[runner.BASE_CONTEXT_FINAL],
    }:
        raise RuntimeError("FULL_TARGET_BASELINE_DRIFT")
    candidate, _ = candidate_mechanical(rows)
    full_target = full_target_evidence_diagnostics()
    expected_candidate = {
        "predictions": 117,
        "out_of_allowlist_or_empty_or_nonlist": 0,
        "order_or_gap_violations": 7,
        "order_violations": 1,
        "gap_violations": 7,
    }
    expected_full = {
        "predictions": 81,
        "out_of_allowlist_or_empty_or_nonlist": 0,
        "order_or_gap_violations": 6,
        "order_violations": 3,
        "gap_violations": 4,
    }
    if any(candidate["evidence_format_diagnostics"][key] != value for key, value in expected_candidate.items()):
        raise RuntimeError("BLOCK300_EVIDENCE_DIAGNOSTIC_DRIFT")
    if any(full_target[key] != value for key, value in expected_full.items()):
        raise RuntimeError("FULL_TARGET_EVIDENCE_DIAGNOSTIC_DRIFT")
    return rows, raw_sha, candidate, {"baseline": baseline, "evidence_format_diagnostics": full_target}


def verify_pre_identity(pre_metrics: dict[str, Any], raw_sha: str) -> None:
    if pre_metrics.get("raw_sha256") != raw_sha:
        raise RuntimeError("PRE_TO_FINAL_RAW_DRIFT")
    if pre_metrics.get("input_bundle_sha256") != input_bundle_sha(raw_sha):
        raise RuntimeError("PRE_TO_FINAL_INPUT_BUNDLE_DRIFT")
    if pre_metrics.get("requests_sha256") != sha256(runner.REQUESTS):
        raise RuntimeError("PRE_TO_FINAL_REQUESTS_DRIFT")
    if pre_metrics.get("source_map_sha256") != sha256(runner.SOURCE_MAP):
        raise RuntimeError("PRE_TO_FINAL_SOURCE_MAP_DRIFT")
    if pre_metrics.get("gold_sha256") != sha256(runner.GOLD):
        raise RuntimeError("PRE_TO_FINAL_GOLD_DRIFT")
    if pre_metrics.get("full_target_stage1_projection_sha256") != FULL_TARGET_STAGE1_PROJECTION_SHA:
        raise RuntimeError("PRE_TO_FINAL_BASELINE_PROJECTION_DRIFT")
    if pre_metrics.get("blind_queue_sha256") != sha256(PRE_QUEUE):
        raise RuntimeError("PRE_TO_FINAL_QUEUE_DRIFT")


def semantic_with_r02_bundle(
    rows: list[dict[str, Any]],
    parsed: dict[str, list[dict[str, Any]]],
    raw_sha: str,
    adjudications: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    r01.input_bundle_sha = input_bundle_sha
    return r01.semantic(rows, parsed, raw_sha, adjudications)


def pre() -> None:
    if PRE_METRICS.exists() or PRE_QUEUE.exists():
        raise RuntimeError("PRE_OUTPUT_EXISTS_NO_OVERWRITE")
    rows, raw_sha, candidate_static, full_target = verify_frozen_inputs()
    mechanical, parsed = candidate_mechanical(rows)
    if mechanical != candidate_static:
        raise RuntimeError("CANDIDATE_MECHANICAL_REBUILD_DRIFT")
    if mechanical["summary"]["mechanically_passed"]:
        semantic_preview, queue = semantic_with_r02_bundle(rows, parsed, raw_sha, {})
    else:
        semantic_preview, queue = None, []
    queue_bytes = jsonl_bytes(queue)
    metrics = {
        "status": "PASS_MECHANICAL_PENDING_BLIND_REVIEW" if queue else ("FAIL_MECHANICAL_HARD_STOP" if not mechanical["summary"]["mechanically_passed"] else "PASS_NO_PENDING_READY_FINAL"),
        "raw_sha256": raw_sha,
        "input_bundle_sha256": input_bundle_sha(raw_sha),
        "requests_sha256": sha256(runner.REQUESTS),
        "source_map_sha256": sha256(runner.SOURCE_MAP),
        "gold_sha256": sha256(runner.GOLD),
        "full_target_stage1_projection_sha256": FULL_TARGET_STAGE1_PROJECTION_SHA,
        "mechanical": mechanical,
        "frozen_full_target_stage1": full_target,
        "semantic_preview": semantic_preview,
        "semantic_pending": len(queue),
        "blind_queue_sha256": sha256_bytes(queue_bytes),
        "formal_final_executed": False,
    }
    write_json(PRE_METRICS, metrics)
    write_jsonl(PRE_QUEUE, queue)
    print(json.dumps({"status": metrics["status"], "pending": len(queue), "queue_sha256": sha256(PRE_QUEUE)}))


def final(adjudications_path: Path) -> None:
    if FINAL_METRICS.exists() or FINAL_QUEUE.exists():
        raise RuntimeError("FINAL_OUTPUT_EXISTS_NO_OVERWRITE")
    if not PRE_METRICS.is_file() or not PRE_QUEUE.is_file():
        raise RuntimeError("PRE_OUTPUT_MISSING")
    rows, raw_sha, candidate_static, full_target = verify_frozen_inputs()
    pre_metrics = read_json(PRE_METRICS)
    if not pre_metrics["mechanical"]["summary"]["mechanically_passed"]:
        raise RuntimeError("FINAL_FORBIDDEN_AFTER_MECHANICAL_FAIL")
    verify_pre_identity(pre_metrics, raw_sha)
    mechanical, parsed = candidate_mechanical(rows)
    if mechanical != candidate_static or mechanical != pre_metrics["mechanical"]:
        raise RuntimeError("PRE_TO_FINAL_MECHANICAL_DRIFT")
    _preview, expected_queue = semantic_with_r02_bundle(rows, parsed, raw_sha, {})
    if jsonl_bytes(expected_queue) != PRE_QUEUE.read_bytes():
        raise RuntimeError("PRE_QUEUE_REBUILD_DRIFT")
    decisions = r01.verify_adjudications(adjudications_path, expected_queue)
    semantic_result, pending = semantic_with_r02_bundle(rows, parsed, raw_sha, decisions)
    if pending:
        raise RuntimeError("SEMANTIC_PENDING_NOT_ZERO")
    legal_tp = semantic_result["legal_tp"]
    predictions = semantic_result["predictions"]
    candidate_f1_exact = 2 * legal_tp / (predictions + 85) if predictions + 85 else 0.0
    passed = candidate_f1_exact + 1e-12 >= MINIMUM_LEGAL_F1
    metrics = {
        "status": "PASS_STAGE1_MAY_REQUEST_NEXT_WORKORDER" if passed else "FAIL_STAGE1_RETAIN_FULL_TARGET_CLOSE_BLOCK300",
        "raw_sha256": raw_sha,
        "input_bundle_sha256": input_bundle_sha(raw_sha),
        "pre_metrics_sha256": sha256(PRE_METRICS),
        "pre_queue_sha256": sha256(PRE_QUEUE),
        "adjudications_sha256": sha256(adjudications_path),
        "mechanical": mechanical,
        "frozen_full_target_stage1": full_target,
        "block300_stage1": semantic_result,
        "minimum_legal_f1": MINIMUM_LEGAL_F1,
        "candidate_f1_exact_for_gate": candidate_f1_exact,
        "gate_passed": passed,
        "semantic_pending": 0,
        "model_or_inference_executed": False,
    }
    write_json(FINAL_METRICS, metrics)
    write_jsonl(FINAL_QUEUE, [])
    print(json.dumps({"status": metrics["status"], "f1": candidate_f1_exact, "gate_passed": passed}))


def static_check() -> None:
    rows, raw_sha, candidate, full_target = verify_frozen_inputs()
    print(json.dumps({
        "status": "PASS_STATIC_FAIR_SCORING_R02",
        "rows": len(rows),
        "raw_sha256": raw_sha,
        "candidate_mechanical_passed": candidate["summary"]["mechanically_passed"],
        "candidate_evidence_diagnostics": candidate["evidence_format_diagnostics"],
        "full_target_evidence_diagnostics": full_target["evidence_format_diagnostics"],
        "full_target_f1": full_target["baseline"]["f1"],
        "minimum_legal_f1": MINIMUM_LEGAL_F1,
        "formal_pre_exists": PRE_METRICS.exists() or PRE_QUEUE.exists(),
        "formal_final_exists": FINAL_METRICS.exists() or FINAL_QUEUE.exists(),
    }, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("static-check", "pre", "final"))
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    if args.command == "static-check":
        if args.adjudications:
            raise RuntimeError("STATIC_CHECK_TAKES_NO_ADJUDICATIONS")
        static_check()
    elif args.command == "pre":
        if args.adjudications:
            raise RuntimeError("PRE_TAKES_NO_ADJUDICATIONS")
        pre()
    else:
        if args.adjudications is None:
            raise RuntimeError("FINAL_REQUIRES_ADJUDICATIONS")
        final(args.adjudications)


if __name__ == "__main__":
    main()
