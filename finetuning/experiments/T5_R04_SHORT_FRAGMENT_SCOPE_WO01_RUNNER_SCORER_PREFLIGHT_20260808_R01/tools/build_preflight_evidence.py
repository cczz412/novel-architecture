#!/usr/bin/env python3
"""Build deterministic WO-01 runner/scorer TEST_ONLY preflight evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import run_wo01_scope_probe as runner
import score_wo01_scope_probe as scorer


EXP = Path(__file__).resolve().parents[1]
FIXTURES = EXP / "test_fixtures/SCORER_BRANCH_FIXTURES.jsonl"
CROSS_ARM_FIXTURE = EXP / "test_fixtures/CROSS_ARM_SHARED_ADJUDICATION.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def source_binding() -> dict[str, Any]:
    runner_sources = runner.verify_frozen_identities()
    scorer_sources = scorer.verify_sources()
    return {
        "schema_version": "t5-r04-wo01-runner-scorer-source-binding-v1",
        "status": "PASS_SOURCES_BOUND_INPUT_PREFLIGHT_ONLY",
        "r01_disposition": {
            "input_materials": "PASS_INPUT_PREFLIGHT_ONLY",
            "run_ready_claim": "WITHDRAWN_BY_THIS_REVISION",
            "old_files_modified": False,
            "manifest_sha256": runner.EXPECTED["r01_manifest"],
        },
        "runner_sources": runner_sources,
        "scorer_sources": scorer_sources,
        "runner_sha256": sha256(EXP / "tools/run_wo01_scope_probe.py"),
        "scorer_sha256": sha256(EXP / "tools/score_wo01_scope_probe.py"),
        "fixture_sha256": sha256(FIXTURES),
        "cross_arm_fixture_sha256": sha256(CROSS_ARM_FIXTURE),
        "semantic_adjudication_schema_sha256": sha256(
            EXP / "SEMANTIC_ADJUDICATION_SCHEMA.json"
        ),
        "run_authorization_schema_sha256": sha256(
            EXP / "RUN_AUTHORIZATION_SCHEMA.json"
        ),
        "scoring_contract_sha256": sha256(EXP / "SCORING_CONTRACT.md"),
        "bootstrap_contract_sha256": sha256(EXP / "BOOTSTRAP_CONTRACT.json"),
        "execution_lock_sha256": sha256(EXP / "EXECUTION_LOCK.json"),
        "vendor_manifest_sha256": sha256(EXP / "VENDOR_SOURCE_MANIFEST.json"),
        "vendor_identity": runner.verify_vendor_sources(),
        "model_run_authorized": False,
        "training_authorized": False,
        "api_authorized": False,
    }


def score_fixtures() -> list[dict[str, Any]]:
    schema = scorer.read_json(scorer.SCHEMA)
    canonical = scorer.canonical_map()
    rows = scorer.read_jsonl(FIXTURES)
    results = []
    for fixture in rows:
        raw = {
            "arm": "TARGET_ONLY",
            "case_id": fixture["case_id"],
            "raw_output": fixture["raw_output"],
            "finish_reason": fixture["finish_reason"],
            "stop_token_is_eos_eot": fixture["stop_token_is_eos_eot"],
        }
        result = scorer.score_case(raw, canonical[fixture["case_id"]], schema, {})
        results.append(
            {
                "fixture_id": fixture["fixture_id"],
                "fixture_role": "TEST_ONLY_NOT_MODEL_OUTPUT_NOT_EXPERIMENT_RESULT",
                "expected_branch": fixture["expected_branch"],
                "observed": result,
            }
        )
    return results


def cross_arm_adjudication_evidence() -> dict[str, Any]:
    fixture = runner.read_json(CROSS_ARM_FIXTURE)
    raw_sha = fixture["decision"]["source_raw_sha256"]
    decisions = scorer.adjudication_index([fixture["decision"]], raw_sha)
    case = scorer.canonical_map()[fixture["case_id"]]
    gold = scorer.gold_rows(case)
    prediction = [{"fact": fixture["prediction_fact"]}]
    per_arm = [
        scorer.semantic_pairs(fixture["case_id"], gold, prediction, decisions)
        for _arm in fixture["arms"]
    ]
    occurrences = [
        {
            "arm": arm,
            "case_id": fixture["case_id"],
            "prediction_index": 0,
            "prediction_fact": fixture["prediction_fact"],
            "prediction_fact_sha256": fixture["decision"][
                "prediction_fact_sha256"
            ],
        }
        for arm in fixture["arms"]
    ]
    queue, sidecar = scorer.build_blind_queue(occurrences, raw_sha)
    return {
        "status": "PASS_TEST_ONLY_CROSS_ARM_BLIND_ADJUDICATION",
        "fixture_role": "TEST_ONLY_NOT_MODEL_OUTPUT_NOT_EXPERIMENT_RESULT",
        "shared_key": [fixture["case_id"], fixture["decision"]["prediction_fact_sha256"]],
        "arms": fixture["arms"],
        "one_decision_reused_by_all_arms": per_arm == [([(0, 0)], [])] * 3,
        "blind_queue_candidates_for_three_occurrences": len(queue),
        "arm_exposed_in_blind_queue": any("arm" in row for row in queue),
        "hidden_occurrence_sidecar_rows": len(sidecar),
        "source_raw_sha256": raw_sha,
    }


def build(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    serialization = runner.build_test_only_serialization_evidence()
    fixture_results = score_fixtures()
    cross_arm = cross_arm_adjudication_evidence()
    write_json(output / "SOURCE_BINDING.json", source_binding())
    write_jsonl(output / "TEST_ONLY_SERIALIZATION_EVIDENCE_72.jsonl", serialization)
    write_jsonl(output / "TEST_ONLY_SCORER_BRANCH_RESULTS_8.jsonl", fixture_results)
    write_json(output / "TEST_ONLY_CROSS_ARM_ADJUDICATION_RECEIPT.json", cross_arm)
    receipt = {
        "schema_version": "t5-r04-wo01-no-model-dry-run-receipt-v1",
        "status": "PASS_TEST_ONLY_RUNNER_SCORER_DRY_RUN",
        "serialization_rows": len(serialization),
        "messages_per_request": 2,
        "system_and_user_both_serialized": sum(
            row["system_content_present_in_serialized_prompt"]
            and row["user_content_present_in_serialized_prompt"]
            for row in serialization
        ),
        "legacy_messages_minus_last_used": any(
            row["legacy_messages_minus_last_used"] for row in serialization
        ),
        "scorer_fixture_cases": len(fixture_results),
        "cross_arm_shared_adjudication": cross_arm[
            "one_decision_reused_by_all_arms"
        ],
        "blind_queue_arm_exposure": cross_arm["arm_exposed_in_blind_queue"],
        "fixture_role": "TEST_ONLY_NOT_MODEL_OUTPUT_NOT_EXPERIMENT_RESULT",
        "model_loaded": False,
        "tokenizer_loaded": False,
        "model_inference_calls": 0,
        "api_calls": 0,
        "training_started": False,
    }
    write_json(output / "NO_MODEL_DRY_RUN_RECEIPT.json", receipt)
    return receipt


def compare(first: Path, second: Path) -> dict[str, Any]:
    left = {str(path.relative_to(first)): path for path in first.rglob("*") if path.is_file()}
    right = {str(path.relative_to(second)): path for path in second.rglob("*") if path.is_file()}
    if set(left) != set(right):
        raise RuntimeError("BUILD_FILE_SET_MISMATCH")
    mismatches = [relative for relative in sorted(left) if left[relative].read_bytes() != right[relative].read_bytes()]
    if mismatches:
        raise RuntimeError(f"BUILD_BYTE_MISMATCH:{mismatches}")
    digest = hashlib.sha256(
        b"".join(
            relative.encode("utf-8") + b"\0" + left[relative].read_bytes()
            for relative in sorted(left)
        )
    ).hexdigest()
    return {
        "status": "PASS_TWO_BUILD_BYTE_IDENTICAL",
        "file_count": len(left),
        "mismatches": 0,
        "tree_digest": digest,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{args.output}")
    print(json.dumps(build(args.output), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
