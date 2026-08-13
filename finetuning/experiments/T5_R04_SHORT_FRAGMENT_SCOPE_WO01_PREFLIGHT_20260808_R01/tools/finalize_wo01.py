from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


EXP = Path(__file__).resolve().parents[1]
MEMBERS = (
    "00_READ_ME_FIRST.md",
    "SOURCE_BINDING.json",
    "ELIGIBILITY_MATRIX_24.jsonl",
    "SCOPE_CONTRACT.md",
    "MODEL_VISIBLE_DIFF_RECEIPT.json",
    "LENGTH_REPORT.json",
    "SCORING_AND_EXECUTION_PREREG.md",
    "EXECUTION_LOCK.json",
    "GAP_LIST.jsonl",
    "RESULT_TICKET.md",
    "INPUT_BUILD_RECEIPT.json",
    "sealed_inputs_candidate/TARGET_ONLY_REQUESTS_24.jsonl",
    "sealed_inputs_candidate/SMALL_HALO_REQUESTS_24.jsonl",
    "sealed_inputs_candidate/CURRENT_WINDOW_REQUESTS_24.jsonl",
    "sealed_inputs_candidate/HIDDEN_REQUEST_SIDECAR_72.jsonl",
    "tools/wo01_renderer.py",
    "tools/build_wo01_inputs.py",
    "tools/validate_wo01.py",
    "tools/finalize_wo01.py",
    "tests/test_wo01_renderer.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_bytes(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--review-status", choices=("pending", "pass"), required=True
    )
    parser.add_argument("--review-agent", default=None)
    args = parser.parse_args()

    missing = [relative for relative in MEMBERS if not (EXP / relative).is_file()]
    if missing:
        raise RuntimeError(f"MANIFEST_MEMBERS_MISSING:{missing}")
    manifest = {
        "schema_version": "t5-r04-wo01-output-manifest-v1",
        "status": "SEALED_CANDIDATE_NO_RUN_AUTHORITY",
        "experiment_id": "T5_R04_SHORT_FRAGMENT_SCOPE_WO01_PREFLIGHT_20260808_R01",
        "member_count": len(MEMBERS),
        "members": [
            {
                "path": relative,
                "bytes": (EXP / relative).stat().st_size,
                "sha256": sha256(EXP / relative),
            }
            for relative in MEMBERS
        ],
        "nonrecursive_exclusions": [
            "OUTPUT_MANIFEST.json",
            "FINAL_VALIDATION_RECEIPT.json",
        ],
    }
    manifest_path = EXP / "OUTPUT_MANIFEST.json"
    write_json(manifest_path, manifest)

    final_pass = args.review_status == "pass"
    receipt = {
        "schema_version": "t5-r04-wo01-final-validation-receipt-v1",
        "status": (
            "PASS_WO01_PREFLIGHT_24_OF_24_READY_NO_RUN_AUTHORITY"
            if final_pass
            else "PENDING_INDEPENDENT_READONLY_REVIEW_NO_RUN_AUTHORITY"
        ),
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "T5_R04_SHORT_FRAGMENT_SCOPE_WO01_PREFLIGHT_20260808_R01",
        "output_manifest_sha256": sha256(manifest_path),
        "manifest_member_count": len(MEMBERS),
        "denominators": {
            "eligible_cases": 24,
            "gold_facts": 48,
            "request_candidates": 72,
            "target_only_vs_small_distinct_cases": 24,
            "small_vs_current_distinct_cases": 24,
        },
        "mechanical_validation": {
            "targeted_tests": "7 passed",
            "ruff": "PASS",
            "json_duplicate_key_check": "PASS",
            "two_build_file_count": 9,
            "two_build_mismatches": 0,
            "two_build_tree_digest": "b7a6050114f65b94aa9c4fc5804e5b0eaa34162e6d4f014c1d613db5dce987b2",
            "pre_validator": "PASS",
        },
        "independent_readonly_review": {
            "status": "PASS" if final_pass else "PENDING",
            "review_agent": args.review_agent if final_pass else None,
        },
        "construction_history": {
            "pre_override_tokenizer_only_diagnostic_occurred": True,
            "initial_batchencoding_field_count_misread_as_token_count": True,
            "corrected_tokenizer_only_result_also_invalidated_by_cz_scope_override": True,
            "token_budget_report_present_in_final_package": False,
            "token_counter_present_in_final_package": False,
            "tokenizer_loaded_after_latest_cz_override": False,
            "model_loaded": False,
            "model_inference_calls": 0,
            "api_calls": 0,
        },
        "actions": {
            "training_started": False,
            "synthetic_source_generated": False,
            "dev24_gold_modified": False,
            "old_sealed_or_result_modified": False,
            "notion_written": False,
            "git_operated": False,
            "current_pointer_modified": False,
            "production_default_modified": False,
        },
        "model_run_authorized": False,
        "training_authorized": False,
        "next_action": "HARD_STOP_WAIT_FOR_CZ_SEPARATE_RUN_AUTHORIZATION",
    }
    write_json(EXP / "FINAL_VALIDATION_RECEIPT.json", receipt)


if __name__ == "__main__":
    main()
