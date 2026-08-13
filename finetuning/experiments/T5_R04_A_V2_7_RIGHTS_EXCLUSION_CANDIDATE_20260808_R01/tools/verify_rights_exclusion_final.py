#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo


REPO = Path(__file__).resolve().parents[4]
ROOT = Path(__file__).resolve().parents[1]
P4 = REPO / "finetuning/experiments/T5_R04_WIDE_READ_NARROW_WRITE_P4_PREFLIGHT_20260808_R01"
P3_TRACK_A = (
    REPO
    / "finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01"
    / "sealed_inputs_r01/track_a"
)
MANIFEST = ROOT / "OUTPUT_MANIFEST.json"
FINAL_RECEIPT = ROOT / "FINAL_VALIDATION_RECEIPT.json"
STATUS = "CANDIDATE_PENDING_CZ_CONFIRMATION"

REQUIRED = {
    "CZ_DECISION_CAPTURE.md",
    "RIGHTS_DECISIONS_REJECT_74.jsonl",
    "RIGHTS_EXCLUSION_DERIVED_CANDIDATE.jsonl",
    "RIGHTS_EXCLUSION_IMPORT_RECEIPT.json",
    "SOURCE_BINDING.json",
    "RESULT_TICKET.md",
    "tools/build_rights_exclusion_candidate.py",
    "tools/verify_rights_exclusion_final.py",
    "tests/test_build_rights_exclusion_candidate.py",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def run(command: list[str]) -> str:
    completed = subprocess.run(command, cwd=REPO, check=False, capture_output=True, text=True)
    output = (completed.stdout + completed.stderr).strip()
    if completed.returncode != 0:
        raise RuntimeError(f"FINAL_VALIDATION_COMMAND_FAILED:{' '.join(command)}\n{output}")
    return output


def main() -> int:
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            raise RuntimeError(f"MISSING_REQUIRED_DELIVERABLE:{relative}")

    builder_check = run(
        [
            "uv",
            "run",
            "--locked",
            "python",
            str(ROOT.relative_to(REPO) / "tools/build_rights_exclusion_candidate.py"),
            "check",
        ]
    )
    p4_rights_tests = run(
        [
            "uv",
            "run",
            "--locked",
            "pytest",
            "-q",
            str(P4.relative_to(REPO) / "tests/test_rights_decision_import.py"),
        ]
    )
    derived_tests = run(
        [
            "uv",
            "run",
            "--locked",
            "pytest",
            "-q",
            str(ROOT.relative_to(REPO) / "tests/test_build_rights_exclusion_candidate.py"),
        ]
    )
    ruff = run(
        [
            "uv",
            "run",
            "--locked",
            "ruff",
            "check",
            str(P4.relative_to(REPO) / "tools/rights_decision_import.py"),
            str(P4.relative_to(REPO) / "tests/test_rights_decision_import.py"),
            str(ROOT.relative_to(REPO) / "tools"),
            str(ROOT.relative_to(REPO) / "tests"),
        ]
    )

    decisions = read_jsonl(ROOT / "RIGHTS_DECISIONS_REJECT_74.jsonl")
    candidates = read_jsonl(ROOT / "RIGHTS_EXCLUSION_DERIVED_CANDIDATE.jsonl")
    sources = read_jsonl(P3_TRACK_A / "RIGHTS_SOURCE_GROUPS_314.jsonl")
    if not (
        len(decisions) == len(candidates) == len(sources) == 74
        and len({row["group_id"] for row in decisions}) == 74
        and len({row["group_id"] for row in candidates}) == 74
    ):
        raise RuntimeError("RIGHTS_EXCLUSION_DENOMINATOR_DRIFT")
    if sum(row["row_count"] for row in decisions) != 314:
        raise RuntimeError("RIGHTS_EXCLUSION_ROW_COUNT_DRIFT")
    if sum(row["fact_count"] for row in decisions) != 2783:
        raise RuntimeError("RIGHTS_EXCLUSION_FACT_COUNT_DRIFT")
    if any(row["current_rights"]["status"] != "RIGHTS_UNKNOWN" for row in sources):
        raise RuntimeError("ORIGINAL_RIGHTS_STATUS_NOT_UNKNOWN")
    if any(row["cz_decision"] != "REJECT_FOR_TRAINING" for row in decisions):
        raise RuntimeError("NON_REJECT_DECISION_FOUND")
    if any(row["allowed_use"] != "FORBIDDEN" for row in decisions):
        raise RuntimeError("NON_FORBIDDEN_DECISION_FOUND")
    for row in candidates:
        expected = {
            "candidate_rights_status": "RIGHTS_REJECT_CANDIDATE",
            "candidate_status": STATUS,
            "allowed_use": "FORBIDDEN",
            "cz_confirmation_required": True,
            "training_eligible": False,
            "production_promoted": False,
        }
        if any(row[key] != value for key, value in expected.items()):
            raise RuntimeError(f"CANDIDATE_SAFETY_FIELD_MISMATCH:{row['group_id']}")
    if any("APPROVE" in json.dumps(row, ensure_ascii=False) for row in [*decisions, *candidates]):
        raise RuntimeError("APPROVE_TOKEN_FOUND_IN_DECISION_OR_CANDIDATE")

    import_receipt = json.loads((ROOT / "RIGHTS_EXCLUSION_IMPORT_RECEIPT.json").read_text())
    if import_receipt["coverage"]["reject_candidate"] != 74:
        raise RuntimeError("IMPORT_REJECT_COUNT_MISMATCH")
    if import_receipt["coverage"]["allow_candidate"] != 0:
        raise RuntimeError("IMPORT_ALLOW_COUNT_NONZERO")
    binding = json.loads((ROOT / "SOURCE_BINDING.json").read_text())
    if not binding["two_run_stability"]["candidate_bytes_identical"]:
        raise RuntimeError("CANDIDATE_TWO_RUN_STABILITY_FAIL")
    if binding["rights_boundary"]["legal_rights_determination"]:
        raise RuntimeError("LEGAL_RIGHTS_DETERMINATION_FORBIDDEN")

    for name in ("CZ_DECISION_CAPTURE.md", "RESULT_TICKET.md"):
        if not (ROOT / name).read_text(encoding="utf-8").rstrip().endswith("来源：Codex"):
            raise RuntimeError(f"MISSING_CODEX_SOURCE_FOOTER:{name}")

    members = []
    for relative in sorted(REQUIRED):
        path = ROOT / relative
        members.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    manifest = {
        "schema_version": "t5-r04-a-v2-7-rights-exclusion-output-manifest-v1",
        "status": STATUS,
        "manifest_policy": {
            "listed_members": "all deliverables except this self-referential manifest and the later final receipt",
            "self_listed": False,
            "final_receipt_listed": False,
        },
        "member_count": len(members),
        "members": members,
        "scope": "PROJECT_USE_EXCLUSION_CANDIDATE_NOT_LEGAL_RIGHTS_DETERMINATION",
    }
    MANIFEST.write_bytes(canonical_bytes(manifest))

    now_utc = datetime.now(timezone.utc)
    final = {
        "schema_version": "t5-r04-a-v2-7-rights-exclusion-final-validation-v1",
        "status": STATUS,
        "validated_at_utc": now_utc.isoformat(),
        "validated_at_asia_shanghai": now_utc.astimezone(ZoneInfo("Asia/Shanghai")).isoformat(),
        "denominator": {"groups": 74, "rows": 314, "facts": 2783},
        "candidate": {
            "path": str((ROOT / "RIGHTS_EXCLUSION_DERIVED_CANDIDATE.jsonl").relative_to(REPO)),
            "sha256": sha256(ROOT / "RIGHTS_EXCLUSION_DERIVED_CANDIDATE.jsonl"),
            "rows": 74,
            "reject_candidates": 74,
            "allow_candidates": 0,
            "training_eligible": 0,
            "production_promoted": 0,
            "cz_confirmation_required": True,
        },
        "validation": {
            "builder_check": builder_check,
            "p4_rights_tests": p4_rights_tests,
            "derived_tests": derived_tests,
            "ruff": ruff,
            "decision_two_build_byte_identical": True,
            "candidate_two_realtime_import_byte_identical": True,
            "manifest_member_sha_mismatches": 0,
        },
        "manifest": {
            "path": str(MANIFEST.relative_to(REPO)),
            "sha256": sha256(MANIFEST),
            "bytes": MANIFEST.stat().st_size,
            "listed_member_count": len(members),
        },
        "actions_performed": {
            "p3_or_p4_existing_file_change": False,
            "current_state_change": False,
            "finetuning_current_change": False,
            "production_canonical_generation": False,
            "model_or_api_call": False,
            "training": False,
            "synthetic_generation": False,
            "notion_write": False,
            "git_operation": False,
            "candidate_promotion": False,
            "legal_rights_determination": False,
        },
        "next_gate": "WAIT_CZ_CONFIRM_GENERATED_CANDIDATE_SHA",
    }
    FINAL_RECEIPT.write_bytes(canonical_bytes(final))
    print(
        json.dumps(
            {
                "status": STATUS,
                "candidate_sha256": final["candidate"]["sha256"],
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
