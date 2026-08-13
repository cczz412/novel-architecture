#!/usr/bin/env python3
"""Create immutable review targets and finalize only from bound independent evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from jsonschema import Draft202012Validator


EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "tools"))
import run_wo01_scope_probe as runner  # noqa: E402

REVIEW_TARGETS = EXP / "review_targets"
INDEPENDENT_REVIEWS = EXP / "independent_reviews"
OUTPUT_MANIFEST = EXP / "OUTPUT_MANIFEST.json"
FINAL_RECEIPT = EXP / "FINAL_VALIDATION_RECEIPT.json"
REVIEW_SCHEMA = EXP / "INDEPENDENT_REVIEW_RECEIPT_SCHEMA.json"
FINAL_SCHEMA = EXP / "FINAL_VALIDATION_RECEIPT_SCHEMA.json"
LEGACY_REVIEW_TARGET = EXP / "REVIEW_TARGET_MANIFEST.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return runner.read_json(path)


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    with path.open("xb") as handle:
        handle.write(payload)


def excluded(relative: str, *, stage: str) -> bool:
    parts = Path(relative).parts
    if any(part in {"__pycache__", ".pytest_cache", "build_runs"} for part in parts):
        return True
    if relative in {OUTPUT_MANIFEST.name, FINAL_RECEIPT.name}:
        return True
    if stage == "review" and parts and parts[0] in {"review_targets", "independent_reviews"}:
        return True
    return False


def member_rows(*, stage: str) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(EXP.rglob("*")):
        relative = str(path.relative_to(EXP))
        if excluded(relative, stage=stage):
            continue
        if path.is_symlink():
            raise RuntimeError(f"FORMAL_FILE_SYMLINK_FORBIDDEN:{relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RuntimeError(f"FORMAL_FILE_NOT_REGULAR:{relative}")
        rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    return rows


def validate_manifest_exact(path: Path, *, stage: str) -> dict[str, Any]:
    manifest = read_json(path)
    rows = manifest.get("members")
    if not isinstance(rows, list) or manifest.get("member_count") != len(rows):
        raise RuntimeError("MANIFEST_MEMBER_COUNT_INVALID")
    if len({row["path"] for row in rows}) != len(rows):
        raise RuntimeError("MANIFEST_DUPLICATE_MEMBER")
    actual = member_rows(stage=stage)
    if rows != actual:
        expected_paths = {row["path"] for row in rows}
        actual_paths = {row["path"] for row in actual}
        raise RuntimeError(
            f"MANIFEST_EXACT_FILE_SET_OR_SHA_DRIFT:extra={sorted(actual_paths-expected_paths)}:missing={sorted(expected_paths-actual_paths)}"
        )
    return manifest


def source_bindings() -> dict[str, str]:
    paths = {
        "runner_sha256": EXP / "tools/run_wo01_scope_probe.py",
        "scorer_sha256": EXP / "tools/score_wo01_scope_probe.py",
        "builder_sha256": EXP / "tools/build_preflight_evidence.py",
        "validator_sha256": EXP / "tools/validate_preflight.py",
        "mechanical_runner_sha256": EXP / "tools/run_mechanical_checks.py",
        "determinism_runner_sha256": EXP / "tools/run_build_determinism_check.py",
        "finalizer_sha256": EXP / "tools/finalize_preflight.py",
        "tests_sha256": EXP / "tests/test_wo01_runner_scorer.py",
        "fixture_branches_sha256": EXP / "test_fixtures/SCORER_BRANCH_FIXTURES.jsonl",
        "fixture_cross_arm_sha256": EXP / "test_fixtures/CROSS_ARM_SHARED_ADJUDICATION.json",
        "authorization_schema_sha256": EXP / "RUN_AUTHORIZATION_SCHEMA.json",
        "adjudication_schema_sha256": EXP / "SEMANTIC_ADJUDICATION_SCHEMA.json",
        "bootstrap_contract_sha256": EXP / "BOOTSTRAP_CONTRACT.json",
        "execution_lock_sha256": EXP / "EXECUTION_LOCK.json",
        "scoring_contract_sha256": EXP / "SCORING_CONTRACT.md",
        "review_schema_sha256": REVIEW_SCHEMA,
        "final_schema_sha256": FINAL_SCHEMA,
        "vendor_manifest_sha256": EXP / "VENDOR_SOURCE_MANIFEST.json",
        "r01_manifest_sha256": runner.R01 / "OUTPUT_MANIFEST.json",
    }
    return {key: sha256(path) for key, path in paths.items()}


def validate_existing_evidence() -> dict[str, Any]:
    mechanical_path = EXP / "MECHANICAL_CHECKS_RECEIPT.json"
    mechanical = read_json(mechanical_path)
    if mechanical.get("status") != "PASS" or not all(row.get("pass") for row in mechanical.get("results", [])):
        raise RuntimeError("MECHANICAL_CHECKS_NOT_BOUND_PASS")
    if mechanical.get("source_bindings") != source_bindings():
        raise RuntimeError("MECHANICAL_CHECK_SOURCE_DRIFT")
    determinism = read_json(EXP / "BUILD_DETERMINISM_RECEIPT.json")
    if determinism.get("status") != "PASS_TWO_BUILD_BYTE_IDENTICAL" or determinism.get("mismatches") != 0:
        raise RuntimeError("BUILD_DETERMINISM_NOT_PASS")
    if determinism.get("source_bindings") != {
        key: value
        for key, value in source_bindings().items()
        if key in determinism.get("source_bindings", {})
    }:
        raise RuntimeError("BUILD_DETERMINISM_SOURCE_DRIFT")
    if any(path.name in {"__pycache__", ".pytest_cache"} for path in EXP.rglob("*")):
        raise RuntimeError("CACHE_PATHS_PRESENT")
    if runner.RUN_CLAIMS.exists():
        claims = list(runner.RUN_CLAIMS.glob("WO01-*.json"))
        if claims:
            raise RuntimeError("RUNTIME_CLAIM_EXISTS_PREFLIGHT_NOT_RUN")
    return {"mechanical_sha256": sha256(mechanical_path), "determinism_sha256": sha256(EXP / "BUILD_DETERMINISM_RECEIPT.json")}


def prepare_review() -> dict[str, Any]:
    validate_existing_evidence()
    members = member_rows(stage="review")
    manifest = {
        "schema_version": "t5-r04-wo01-runner-scorer-review-target-v2",
        "status": "READY_FOR_INDEPENDENT_READONLY_REVIEW",
        "member_count": len(members),
        "members": members,
        "review_must_cover": [
            "two_message_serialization",
            "formal_run_provenance",
            "runtime_path_symlink_guards",
            "vendor_and_model_identity",
            "blind_semantic_review",
            "immutable_scoring",
            "bootstrap_contract",
            "strict_json",
            "no_model_api_training",
        ],
    }
    payload = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    target_sha = hashlib.sha256(payload).hexdigest()
    target = REVIEW_TARGETS / f"REVIEW_TARGET_{target_sha}.json"
    if target.exists():
        raise RuntimeError("REVIEW_TARGET_ALREADY_EXISTS_NO_OVERWRITE")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        handle.write(payload)
    return {**manifest, "review_target_path": str(target), "review_target_sha256": target_sha}


def validate_review(target: Path, review_path: Path) -> dict[str, Any]:
    if target.parent != REVIEW_TARGETS or review_path.parent != INDEPENDENT_REVIEWS:
        raise RuntimeError("REVIEW_EVIDENCE_PATH_NOT_FIXED")
    if target.is_symlink() or review_path.is_symlink():
        raise RuntimeError("REVIEW_EVIDENCE_SYMLINK_FORBIDDEN")
    target_sha = sha256(target)
    if target.name != f"REVIEW_TARGET_{target_sha}.json":
        raise RuntimeError("REVIEW_TARGET_FILENAME_SHA_MISMATCH")
    if review_path.name != f"INDEPENDENT_REVIEW_{target_sha}.json":
        raise RuntimeError("INDEPENDENT_REVIEW_FILENAME_TARGET_MISMATCH")
    target_manifest = validate_manifest_exact(target, stage="review")
    review = read_json(review_path)
    errors = sorted(Draft202012Validator(read_json(REVIEW_SCHEMA)).iter_errors(review), key=lambda e: list(e.absolute_path))
    if errors:
        raise RuntimeError("INDEPENDENT_REVIEW_SCHEMA_INVALID:" + "|".join(e.message for e in errors))
    if review["status"] != "PASS" or review["review_target_manifest_sha256"] != target_sha:
        raise RuntimeError("INDEPENDENT_REVIEW_NOT_PASS_OR_TARGET_DRIFT")
    if review["reviewed_member_count"] != target_manifest["member_count"]:
        raise RuntimeError("INDEPENDENT_REVIEW_MEMBER_COUNT_DRIFT")
    kinds = [row["kind"] for row in review["command_evidence"]]
    if sorted(kinds) != ["pytest", "readonly_validator", "ruff"]:
        raise RuntimeError("INDEPENDENT_REVIEW_COMMAND_EVIDENCE_INCOMPLETE")
    return review


def finalize(target: Path, review_path: Path) -> dict[str, Any]:
    evidence = validate_existing_evidence()
    review = validate_review(target, review_path)
    if OUTPUT_MANIFEST.exists() or FINAL_RECEIPT.exists():
        raise RuntimeError("FINAL_OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    members = member_rows(stage="output")
    manifest = {
        "schema_version": "t5-r04-wo01-runner-scorer-output-manifest-v2",
        "status": "PASS_OUTPUT_SET_BOUND_EXACT_FILE_SET",
        "member_count": len(members),
        "members": members,
    }
    write_json_exclusive(OUTPUT_MANIFEST, manifest)
    tests_stdout = read_json(EXP / "MECHANICAL_CHECKS_RECEIPT.json")["results"][0]["stdout"]
    match = re.search(r"(\d+) passed", tests_stdout)
    if not match:
        raise RuntimeError("TEST_PASS_COUNT_NOT_RECORDED")
    receipt = {
        "schema_version": "t5-r04-wo01-runner-scorer-final-validation-v2",
        "status": "PASS_RUNNER_SCORER_PREFLIGHT_NO_MODEL_RUN_AUTHORITY",
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_manifest_sha256": sha256(OUTPUT_MANIFEST),
        "review_target_manifest_sha256": sha256(target),
        "independent_readonly_review_sha256": sha256(review_path),
        "mechanical_checks_receipt_sha256": evidence["mechanical_sha256"],
        "build_determinism_receipt_sha256": evidence["determinism_sha256"],
        "execution_identity": {**runner.current_execution_contract_identity(), "runner_sha256": sha256(EXP / "tools/run_wo01_scope_probe.py"), "vendor_identity": runner.verify_vendor_sources()},
        "r01_input_manifest_sha256": runner.EXPECTED["r01_manifest"],
        "tests_passed": int(match.group(1)),
        "model_run_authorized": False,
        "training_authorized": False,
        "api_authorized": False,
        "model_loaded": False,
        "model_inference_calls": 0,
        "api_calls": 0,
        "training_started": False,
        "synthetic_generated": False,
        "old_inputs_modified": False,
        "current_pointer_modified": False,
        "notion_written": False,
        "git_operated": False,
        "runtime_claim_created": False,
        "next_action": "HARD_STOP_WAIT_FOR_SEPARATE_CZ_MODEL_RUN_TICKET",
    }
    errors = list(Draft202012Validator(read_json(FINAL_SCHEMA)).iter_errors(receipt))
    if errors:
        raise RuntimeError("FINAL_RECEIPT_SCHEMA_INVALID")
    write_json_exclusive(FINAL_RECEIPT, receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare-review", "finalize"))
    parser.add_argument("--review-target", type=Path)
    parser.add_argument("--review-receipt", type=Path)
    args = parser.parse_args()
    if args.command == "prepare-review":
        result = prepare_review()
    else:
        if args.review_target is None or args.review_receipt is None:
            parser.error("finalize 需要 --review-target 和 --review-receipt")
        result = finalize(args.review_target, args.review_receipt)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
