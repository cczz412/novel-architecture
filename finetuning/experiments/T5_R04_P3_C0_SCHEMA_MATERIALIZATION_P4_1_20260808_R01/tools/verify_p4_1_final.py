#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


REPO = Path(__file__).resolve().parents[4]
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "P4_1_OUTPUT_MANIFEST.json"
FINAL_RECEIPT = ROOT / "P4_1_FINAL_VALIDATION_RECEIPT.json"
STATUS = "PASS_P3_C0_STRUCTURAL_SCHEMA_MATERIALIZED_NO_RUN_AUTHORITY"

REQUIRED = {
    "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json",
    "P3_C0_SCHEMA_SOURCE_BINDING.json",
    "P3_C0_RUNTIME_VALIDATION_LAYERS.md",
    "P3_C0_SCHEMA_MUTATION_CORPUS.jsonl",
    "tools/verify_p3_c0_schema_equivalence.py",
    "tests/test_p3_c0_schema_equivalence.py",
    "P4_1_SCHEMA_EQUIVALENCE_RECEIPT.json",
    "P4_1_GAP_005_RESOLUTION_TICKET.md",
    "P4_1_GAP_LIST.jsonl",
    "P4_1_RESULT_TICKET.md",
    "tools/verify_p4_1_final.py",
}


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> str:
    completed = subprocess.run(command, cwd=REPO, check=False, capture_output=True, text=True)
    output = (completed.stdout + completed.stderr).strip()
    if completed.returncode != 0:
        raise RuntimeError(f"FINAL_VALIDATION_COMMAND_FAILED:{' '.join(command)}\n{output}")
    return output


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            raise RuntimeError(f"MISSING_REQUIRED_DELIVERABLE:{relative}")

    equivalence_output = run(
        [
            "uv",
            "run",
            "--locked",
            "python",
            str(ROOT.relative_to(REPO) / "tools/verify_p3_c0_schema_equivalence.py"),
            "check",
        ]
    )
    pytest_output = run(
        [
            "uv",
            "run",
            "--locked",
            "pytest",
            "-q",
            str(ROOT.relative_to(REPO) / "tests/test_p3_c0_schema_equivalence.py"),
        ]
    )
    ruff_output = run(
        [
            "uv",
            "run",
            "--locked",
            "ruff",
            "check",
            str(ROOT.relative_to(REPO) / "tools"),
            str(ROOT.relative_to(REPO) / "tests"),
        ]
    )

    receipt = read_json(ROOT / "P4_1_SCHEMA_EQUIVALENCE_RECEIPT.json")
    if receipt["status"] != STATUS:
        raise RuntimeError("EQUIVALENCE_RECEIPT_STATUS_MISMATCH")
    if (
        receipt["mutation_corpus"]["cases"] != 44
        or receipt["mutation_corpus"]["accepted_language_mismatches"] != 0
    ):
        raise RuntimeError("MUTATION_RESULT_MISMATCH")
    if receipt["frozen_gold_replay"] != {
        "accepted_by_runner": 24,
        "accepted_by_schema": 24,
        "accepted_language_mismatches": 0,
        "cases": 24,
    }:
        raise RuntimeError("GOLD_REPLAY_RESULT_MISMATCH")
    historical = receipt["historical_c0_replay"]
    if not (
        historical["accepted_language_mismatches"] == 0
        and historical["cases"] == 24
        and historical["json_valid"] == 24
        and historical["schema_invalid"] == 6
        and historical["schema_valid"] == 18
        and historical["ordered_case_ids_match_gold"] is True
    ):
        raise RuntimeError("HISTORICAL_REPLAY_RESULT_MISMATCH")
    if receipt["accepted_language_equivalence"]["mismatches_total"] != 0:
        raise RuntimeError("ACCEPTED_LANGUAGE_MISMATCH")
    expected_statement = (
        "44 条目标 corpus 接受语言等价；正常返回的 42 条布尔等价；"
        "2 条 oracle 异常单列且 Schema 正常拒绝；不声称失败方式相同。"
    )
    if receipt["equivalence_statement"] != expected_statement:
        raise RuntimeError("EQUIVALENCE_STATEMENT_MISMATCH")
    if receipt["normal_return_boolean_equivalence"]["mismatches_total"] != 0:
        raise RuntimeError("NORMAL_RETURN_BOOLEAN_MISMATCH")
    exception_audit = receipt["oracle_exception_audit"]
    if not (
        exception_audit["count"] == 2
        and [row["case_id"] for row in exception_audit["cases"]] == ["M043", "M044"]
        and all(row["exception_type"] == "TypeError" for row in exception_audit["cases"])
        and exception_audit["schema_rejected_all"] is True
        and exception_audit["failure_mode_equivalence_claimed"] is False
    ):
        raise RuntimeError("ORACLE_EXCEPTION_AUDIT_MISMATCH")
    pairing = receipt["case_pairing"]
    if not (
        pairing["gold_unique"] is True
        and pairing["historical_unique"] is True
        and pairing["ordered_lists_equal"] is True
        and pairing["ordered_case_id_sha256"] == historical["ordered_case_id_sha256"]
    ):
        raise RuntimeError("CASE_PAIRING_MISMATCH")
    oracle = receipt["frozen_check_schema_import"]
    if oracle["method"] != "FROZEN_SOURCE_AST_ORACLE" or oracle["full_runner_module_import_succeeded"]:
        raise RuntimeError("ORACLE_IDENTITY_MISMATCH")
    if oracle["lineno_start"] != 462 or oracle["lineno_end"] != 488:
        raise RuntimeError("ORACLE_LINE_BINDING_MISMATCH")

    for name in (
        "P3_C0_RUNTIME_VALIDATION_LAYERS.md",
        "P4_1_GAP_005_RESOLUTION_TICKET.md",
        "P4_1_RESULT_TICKET.md",
    ):
        if not (ROOT / name).read_text(encoding="utf-8").rstrip().endswith("来源：Codex"):
            raise RuntimeError(f"MISSING_CODEX_SOURCE_FOOTER:{name}")

    gap_rows = [
        json.loads(line)
        for line in (ROOT / "P4_1_GAP_LIST.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(gap_rows) != 5 or len({row["gap_id"] for row in gap_rows}) != 5:
        raise RuntimeError("GAP_LIST_INVALID")
    gap_text = (ROOT / "P4_1_GAP_LIST.jsonl").read_text(encoding="utf-8")
    if "目标 corpus 上布尔等价" in gap_text or "正常返回的 42 条布尔等价" not in gap_text:
        raise RuntimeError("STALE_BOOLEAN_EQUIVALENCE_CLAIM")

    members = []
    for relative in sorted(REQUIRED):
        path = ROOT / relative
        members.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    manifest = {
        "schema_version": "t5-r04-p4-1-output-manifest-v1",
        "status": STATUS,
        "manifest_policy": {
            "listed_members": "all deliverables except this self-referential manifest and the later final receipt",
            "self_listed": False,
            "final_receipt_listed": False,
        },
        "member_count": len(members),
        "members": members,
        "scope": "STRUCTURAL_SCHEMA_MATERIALIZATION_ONLY_NO_RUN_AUTHORITY",
    }
    MANIFEST.write_bytes(canonical_bytes(manifest))

    now_utc = datetime.now(timezone.utc)
    now_shanghai = now_utc.astimezone(ZoneInfo("Asia/Shanghai"))
    final = {
        "schema_version": "t5-r04-p4-1-final-validation-receipt-v1",
        "status": STATUS,
        "validated_at_utc": now_utc.isoformat(),
        "validated_at_asia_shanghai": now_shanghai.isoformat(),
        "validation": {
            "equivalence_check": equivalence_output,
            "pytest_command": "uv run --locked pytest -q "
            + str(ROOT.relative_to(REPO) / "tests/test_p3_c0_schema_equivalence.py"),
            "pytest_result": pytest_output,
            "ruff_command": "uv run --locked ruff check "
            + str(ROOT.relative_to(REPO) / "tools")
            + " "
            + str(ROOT.relative_to(REPO) / "tests"),
            "ruff_result": ruff_output,
            "mutation_cases": 44,
            "gold_replay": "24/24 accepted by both",
            "historical_replay": "18 valid / 6 invalid / 0 accepted-language mismatches",
            "accepted_language_mismatches_total": 0,
            "normal_return_boolean_mismatches_total": 0,
            "oracle_exception_cases": ["M043", "M044"],
            "oracle_exception_type": "TypeError",
            "ordered_case_id_sha256": pairing["ordered_case_id_sha256"],
            "oracle": "FROZEN_SOURCE_AST_ORACLE",
        },
        "construction_history": receipt["construction_history"],
        "manifest": {
            "path": str(MANIFEST.relative_to(REPO)),
            "bytes": MANIFEST.stat().st_size,
            "sha256": sha256(MANIFEST),
            "listed_member_count": len(members),
        },
        "actions_performed": {
            "model_or_api_call": False,
            "training": False,
            "synthetic_generation": False,
            "p3_or_p4_existing_file_change": False,
            "prompt_or_renderer_change": False,
            "gold_change": False,
            "notion_write": False,
            "git_operation": False,
            "current_pointer_change": False,
            "production_canonical_generation": False,
            "rights_release": False,
        },
        "authority": {
            "model_run": False,
            "training": False,
            "synthetic_generation": False,
            "real_six_arm_experiment": False,
            "production_promotion": False,
        },
    }
    FINAL_RECEIPT.write_bytes(canonical_bytes(final))
    print(
        json.dumps(
            {
                "status": STATUS,
                "manifest_sha256": sha256(MANIFEST),
                "final_receipt_sha256": sha256(FINAL_RECEIPT),
                "member_count": len(members),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
