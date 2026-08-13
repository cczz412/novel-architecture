#!/usr/bin/env python3
"""Run and record the actual locked test/Ruff/validator commands."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


EXP = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
RECEIPT = EXP / "MECHANICAL_CHECKS_RECEIPT.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode("utf-8")).hexdigest(),
        "pass": completed.returncode == 0,
        "environment_overrides": {"PYTHONDONTWRITEBYTECODE": "1"},
    }


def main() -> None:
    relative = EXP.relative_to(REPO)
    commands = [
        [
            "uv",
            "run",
            "--locked",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            str(relative / "tests/test_wo01_runner_scorer.py"),
        ],
        ["uv", "run", "--locked", "ruff", "check", str(relative / "tools"), str(relative / "tests")],
        ["uv", "run", "--locked", "python", str(relative / "tools/run_wo01_scope_probe.py"), "validate"],
        ["uv", "run", "--locked", "python", str(relative / "tools/score_wo01_scope_probe.py"), "validate"],
        ["uv", "run", "--locked", "python", str(relative / "tools/validate_preflight.py"), "--stage", "pre"],
    ]
    results = [run(command) for command in commands]
    status = "PASS" if all(row["pass"] for row in results) else "HARD_STOP_CHECK_FAILED"
    receipt = {
        "schema_version": "t5-r04-wo01-runner-scorer-mechanical-checks-v1",
        "status": status,
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "source_bindings": {
            "runner_sha256": sha256(EXP / "tools/run_wo01_scope_probe.py"),
            "scorer_sha256": sha256(EXP / "tools/score_wo01_scope_probe.py"),
            "builder_sha256": sha256(EXP / "tools/build_preflight_evidence.py"),
            "validator_sha256": sha256(EXP / "tools/validate_preflight.py"),
            "mechanical_runner_sha256": sha256(EXP / "tools/run_mechanical_checks.py"),
            "determinism_runner_sha256": sha256(EXP / "tools/run_build_determinism_check.py"),
            "finalizer_sha256": sha256(EXP / "tools/finalize_preflight.py"),
            "tests_sha256": sha256(EXP / "tests/test_wo01_runner_scorer.py"),
            "fixture_branches_sha256": sha256(EXP / "test_fixtures/SCORER_BRANCH_FIXTURES.jsonl"),
            "fixture_cross_arm_sha256": sha256(EXP / "test_fixtures/CROSS_ARM_SHARED_ADJUDICATION.json"),
            "authorization_schema_sha256": sha256(EXP / "RUN_AUTHORIZATION_SCHEMA.json"),
            "adjudication_schema_sha256": sha256(EXP / "SEMANTIC_ADJUDICATION_SCHEMA.json"),
            "bootstrap_contract_sha256": sha256(EXP / "BOOTSTRAP_CONTRACT.json"),
            "execution_lock_sha256": sha256(EXP / "EXECUTION_LOCK.json"),
            "scoring_contract_sha256": sha256(EXP / "SCORING_CONTRACT.md"),
            "review_schema_sha256": sha256(EXP / "INDEPENDENT_REVIEW_RECEIPT_SCHEMA.json"),
            "final_schema_sha256": sha256(EXP / "FINAL_VALIDATION_RECEIPT_SCHEMA.json"),
            "vendor_manifest_sha256": sha256(EXP / "VENDOR_SOURCE_MANIFEST.json"),
            "r01_manifest_sha256": sha256(REPO / "finetuning/experiments/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_PREFLIGHT_20260808_R01/OUTPUT_MANIFEST.json"),
        },
        "model_loaded": False,
        "model_inference_calls": 0,
        "api_calls": 0,
        "training_started": False,
    }
    RECEIPT.write_bytes(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
