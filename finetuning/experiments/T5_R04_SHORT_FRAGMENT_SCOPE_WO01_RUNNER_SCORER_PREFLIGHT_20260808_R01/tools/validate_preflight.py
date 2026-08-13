#!/usr/bin/env python3
"""Mechanical validator for the WO-01 runner/scorer preflight revision."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


EXP = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(EXP / "tools"))

import run_wo01_scope_probe as runner  # noqa: E402
import score_wo01_scope_probe as scorer  # noqa: E402
import finalize_preflight as finalizer  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    return json.loads(path.read_bytes(), object_pairs_hook=no_duplicate_keys)


def read_jsonl(path: Path) -> list[Any]:
    return [
        json.loads(line, object_pairs_hook=no_duplicate_keys)
        for line in path.read_bytes().splitlines()
        if line.strip()
    ]


def validate_all_json() -> None:
    for path in sorted(EXP.rglob("*")):
        if not path.is_file() or any(
            part in {"__pycache__", ".pytest_cache"} for part in path.parts
        ):
            continue
        if path.suffix == ".json":
            read_json(path)
        elif path.suffix == ".jsonl":
            read_jsonl(path)


def validate_core() -> dict[str, Any]:
    validate_all_json()
    plan = runner.load_execution_plan()
    identities = runner.verify_frozen_identities()
    scorer_sources = scorer.verify_sources()
    if len(plan) != 72:
        raise RuntimeError("PLAN_NOT_72")
    if any(len(row["request"]["messages"]) != 2 for row in plan):
        raise RuntimeError("PLAN_MESSAGE_COUNT_DRIFT")

    derived = EXP / "derived_candidate"
    dry = read_json(derived / "NO_MODEL_DRY_RUN_RECEIPT.json")
    if dry != {
        "api_calls": 0,
        "blind_queue_arm_exposure": False,
        "cross_arm_shared_adjudication": True,
        "fixture_role": "TEST_ONLY_NOT_MODEL_OUTPUT_NOT_EXPERIMENT_RESULT",
        "legacy_messages_minus_last_used": False,
        "messages_per_request": 2,
        "model_inference_calls": 0,
        "model_loaded": False,
        "schema_version": "t5-r04-wo01-no-model-dry-run-receipt-v1",
        "scorer_fixture_cases": 8,
        "serialization_rows": 72,
        "status": "PASS_TEST_ONLY_RUNNER_SCORER_DRY_RUN",
        "system_and_user_both_serialized": 72,
        "tokenizer_loaded": False,
        "training_started": False,
    }:
        raise RuntimeError("DRY_RUN_RECEIPT_DRIFT")
    serialization = read_jsonl(derived / "TEST_ONLY_SERIALIZATION_EVIDENCE_72.jsonl")
    if len(serialization) != 72 or any(
        row["roles_passed_to_serializer"] != ["system", "user"]
        or row["message_count_passed_to_serializer"] != 2
        or not row["system_content_present_in_serialized_prompt"]
        or not row["user_content_present_in_serialized_prompt"]
        or row["legacy_messages_minus_last_used"]
        for row in serialization
    ):
        raise RuntimeError("TWO_MESSAGE_SERIALIZATION_EVIDENCE_FAILED")
    if len({(row["arm"], row["case_id"]) for row in serialization}) != 72:
        raise RuntimeError("SERIALIZATION_BINDING_NOT_72_UNIQUE")

    fixtures = read_jsonl(derived / "TEST_ONLY_SCORER_BRANCH_RESULTS_8.jsonl")
    if len(fixtures) != 8 or any(
        row["fixture_role"] != "TEST_ONLY_NOT_MODEL_OUTPUT_NOT_EXPERIMENT_RESULT"
        for row in fixtures
    ):
        raise RuntimeError("SCORER_FIXTURE_RESULT_DRIFT")
    branches = {row["expected_branch"]: row["observed"] for row in fixtures}
    required_branches = {
        "perfect",
        "natural_empty",
        "malformed_recoverable",
        "illegal_evidence",
        "read_only_leakage",
        "repetition",
        "token_limit",
        "status_invalid",
    }
    if set(branches) != required_branches:
        raise RuntimeError("SCORER_FIXTURE_BRANCH_COVERAGE")
    if branches["malformed_recoverable"]["schema_valid"]:
        raise RuntimeError("MALFORMED_WASHED_TO_SCHEMA_PASS")
    if branches["malformed_recoverable"]["semantic_recoverable"]["tp"] != 1:
        raise RuntimeError("MALFORMED_RECOVERABLE_SEMANTIC_NOT_RECORDED")
    if branches["illegal_evidence"]["end_to_end_usable"]["tp"] != 0:
        raise RuntimeError("ILLEGAL_EVIDENCE_WASHED_TO_USABLE")
    if branches["read_only_leakage"]["read_only_leakage"]["evidence_id_cases"] != 1:
        raise RuntimeError("READ_ONLY_LEAKAGE_NOT_DETECTED")
    if not branches["repetition"]["repetition_detected"]:
        raise RuntimeError("REPETITION_NOT_DETECTED")
    if not branches["token_limit"]["token_limit_hit"]:
        raise RuntimeError("TOKEN_LIMIT_NOT_DETECTED")
    cross_arm = read_json(
        derived / "TEST_ONLY_CROSS_ARM_ADJUDICATION_RECEIPT.json"
    )
    if (
        cross_arm["status"]
        != "PASS_TEST_ONLY_CROSS_ARM_BLIND_ADJUDICATION"
        or not cross_arm["one_decision_reused_by_all_arms"]
        or cross_arm["arm_exposed_in_blind_queue"]
        or cross_arm["blind_queue_candidates_for_three_occurrences"] != 1
        or cross_arm["hidden_occurrence_sidecar_rows"] != 3
    ):
        raise RuntimeError("CROSS_ARM_BLIND_ADJUDICATION_FAILED")

    bootstrap = read_json(EXP / "BOOTSTRAP_CONTRACT.json")
    if (
        bootstrap["resamples"] != scorer.BOOTSTRAP_SAMPLES
        or bootstrap["seed"] != scorer.BOOTSTRAP_SEED
        or bootstrap["sampling_unit"] != "paired_case_with_replacement"
        or bootstrap["interval_method"] != "two_sided_percentile_type7"
    ):
        raise RuntimeError("BOOTSTRAP_CODE_CONTRACT_DRIFT")
    lock = read_json(EXP / "EXECUTION_LOCK.json")
    if any(lock[key] for key in ("model_run_authorized", "training_authorized", "api_authorized")):
        raise RuntimeError("EXECUTION_AUTHORITY_ESCALATION")
    if lock["authorization_ticket_present"]:
        raise RuntimeError("UNAUTHORIZED_TICKET_CLAIM")
    determinism = read_json(EXP / "BUILD_DETERMINISM_RECEIPT.json")
    if (
        determinism["status"] != "PASS_TWO_BUILD_BYTE_IDENTICAL"
        or determinism["mismatches"]
        or determinism["run_1_members"] != determinism["run_2_members"]
        or determinism["source_bindings"] != finalizer.source_bindings()
    ):
        raise RuntimeError("BUILD_DETERMINISM_FAILED")
    return {
        "status": "PASS_WO01_RUNNER_SCORER_PREFLIGHT_CORE",
        "r01_manifest_sha256": identities["r01_manifest"]["sha256"],
        "runner_plan_rows": len(plan),
        "messages_per_request": 2,
        "serialization_evidence_rows": len(serialization),
        "scorer_fixture_branches": len(fixtures),
        "cross_arm_blind_shared_adjudication": True,
        "bootstrap_resamples": bootstrap["resamples"],
        "bootstrap_seed": bootstrap["seed"],
        "scorer_source_count": len(scorer_sources),
        "model_loaded": False,
        "model_run_authorized": False,
    }


def validate_manifest(path: Path) -> None:
    manifest = read_json(path)
    members = manifest["members"]
    if len(members) != manifest["member_count"] or len({row["path"] for row in members}) != len(members):
        raise RuntimeError(f"MANIFEST_MEMBER_COUNT_OR_DUPLICATE:{path.name}")
    for row in members:
        member = EXP / row["path"]
        if not member.is_file():
            raise RuntimeError(f"MANIFEST_MEMBER_MISSING:{row['path']}")
        if member.stat().st_size != row["bytes"] or sha256(member) != row["sha256"]:
            raise RuntimeError(f"MANIFEST_MEMBER_DRIFT:{row['path']}")


def validate_final() -> dict[str, Any]:
    core = validate_core()
    cache_paths = [
        path
        for path in EXP.rglob("*")
        if path.name in {"__pycache__", ".pytest_cache"}
    ]
    if cache_paths:
        raise RuntimeError(f"CACHE_PATHS_PRESENT:{cache_paths}")
    output = EXP / "OUTPUT_MANIFEST.json"
    receipt = read_json(EXP / "FINAL_VALIDATION_RECEIPT.json")
    errors = list(
        __import__("jsonschema").Draft202012Validator(
            read_json(EXP / "FINAL_VALIDATION_RECEIPT_SCHEMA.json")
        ).iter_errors(receipt)
    )
    if errors:
        raise RuntimeError("FINAL_RECEIPT_SCHEMA_INVALID")
    target_sha = receipt["review_target_manifest_sha256"]
    target = EXP / "review_targets" / f"REVIEW_TARGET_{target_sha}.json"
    review = EXP / "independent_reviews" / f"INDEPENDENT_REVIEW_{target_sha}.json"
    finalizer.validate_manifest_exact(target, stage="review")
    finalizer.validate_manifest_exact(output, stage="output")
    finalizer.validate_review(target, review)
    if receipt["status"] != "PASS_RUNNER_SCORER_PREFLIGHT_NO_MODEL_RUN_AUTHORITY":
        raise RuntimeError("FINAL_RECEIPT_STATUS")
    if receipt["output_manifest_sha256"] != sha256(output):
        raise RuntimeError("FINAL_RECEIPT_OUTPUT_MANIFEST_BINDING")
    if receipt["independent_readonly_review_sha256"] != sha256(review):
        raise RuntimeError("FINAL_RECEIPT_REVIEW_BINDING")
    if receipt["mechanical_checks_receipt_sha256"] != sha256(EXP / "MECHANICAL_CHECKS_RECEIPT.json"):
        raise RuntimeError("FINAL_RECEIPT_MECHANICAL_BINDING")
    if receipt["build_determinism_receipt_sha256"] != sha256(EXP / "BUILD_DETERMINISM_RECEIPT.json"):
        raise RuntimeError("FINAL_RECEIPT_DETERMINISM_BINDING")
    if receipt["execution_identity"] != {
        **runner.current_execution_contract_identity(),
        "runner_sha256": sha256(EXP / "tools/run_wo01_scope_probe.py"),
        "vendor_identity": runner.verify_vendor_sources(),
    }:
        raise RuntimeError("FINAL_RECEIPT_EXECUTION_IDENTITY_DRIFT")
    return {**core, "status": "PASS_FINAL", "cache_paths": 0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("pre", "final"), default="pre")
    parser.add_argument("--write-receipt", type=Path)
    args = parser.parse_args()
    result = validate_final() if args.stage == "final" else validate_core()
    if args.write_receipt:
        args.write_receipt.write_bytes(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
            + b"\n"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
