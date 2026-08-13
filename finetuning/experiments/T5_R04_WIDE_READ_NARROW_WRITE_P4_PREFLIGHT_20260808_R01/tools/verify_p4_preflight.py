#!/usr/bin/env python3
"""Mechanically verify and seal the P4 preflight-only deliverables."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


P4 = Path(__file__).resolve().parents[1]
REPO = P4.parents[2]
FINAL_STATUS = "P4_REAL_DIAG_NOT_READY_SYNTHETIC_CONTRACT_ONLY"
EXCLUDED_NAMES = {"P4_OUTPUT_MANIFEST.json", "P4_FINAL_VALIDATION_RECEIPT.json"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def resolve_source(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else REPO / path


def assert_source_manifest() -> dict[str, Any]:
    manifest = read_json(P4 / "P4_SOURCE_MANIFEST.json")
    assert manifest["status"] == "P4_SOURCE_INPUTS_VERIFIED_READ_ONLY"
    assert manifest["research_pairing_contract"]["pair_count"] == 6
    assert len(manifest["sources"]) == 24
    pair_ids = set()
    for item in manifest["sources"]:
        path = resolve_source(item["path"])
        data = path.read_bytes()
        assert len(data) == item["bytes"], item["source_id"]
        assert sha256_bytes(data) == item["sha256"], item["source_id"]
        if item.get("pair_id"):
            pair_ids.add(item["pair_id"])
    assert len(pair_ids) == 6
    return manifest


def assert_c0_binding() -> dict[str, Any]:
    binding = read_json(P4 / "P4_C0_SOURCE_BINDING.json")
    assert binding["status"] == "PASS_P3_C0_SOURCE_ARTIFACTS_LOCATED_P4_RUN_NOT_AUTHORIZED"
    for key in (
        "p3_c0_questions",
        "p3_c0_build_script",
        "p3_c0_run_script",
        "source_renderer",
        "source_c2_rendered_questions",
    ):
        item = binding[key]
        path = resolve_source(item["path"])
        assert sha256(path) == item["sha256"], key
    questions = jsonl(resolve_source(binding["p3_c0_questions"]["path"]))
    assert len(questions) == binding["p3_c0_questions"]["rows"] == 24
    system_prompts = [row["messages"][0]["content"] for row in questions]
    assert len(set(system_prompts)) == 1
    assert sha256_bytes(system_prompts[0].encode("utf-8")) == binding["system_prompt"]["utf8_sha256"]
    assert binding["p4_boundary"]["model_run_authorized"] is False
    return binding


def assert_rights() -> dict[str, Any]:
    receipt = read_json(P4 / "RIGHTS_IMPORT_DRY_RUN_RECEIPT.json")
    assert receipt["status"] == "PASS_DRY_RUN_ALL_RIGHTS_UNKNOWN_NO_PROMOTION"
    assert receipt["mode"] == "DRY_RUN"
    assert receipt["coverage"]["source_groups"] == 74
    assert receipt["coverage"]["rows"] == 314
    assert receipt["coverage"]["facts"] == 2783
    assert receipt["coverage"]["allow_candidate"] == 0
    assert receipt["safety"]["training_eligible_groups"] == 0
    assert receipt["baseline_contract"]["frozen"] is True
    assert receipt["runtime_clock"]["clock_source"] == "SYSTEM_UTC"
    assert receipt["runtime_clock"]["validation_date_source"] == "SYSTEM_ASIA_SHANGHAI_CURRENT_DATE"
    assert receipt["safety"]["replay_can_train_or_promote"] is False
    assert len(receipt["preflight_corrections"]) >= 9
    for key in ("source_groups", "decisions", "schema", "importer"):
        item = receipt["inputs"][key]
        assert sha256(Path(item["path"])) == item["sha256"], key
    candidate_path = Path(receipt["output"]["path"])
    assert sha256(candidate_path) == receipt["output"]["sha256"]
    rows = jsonl(candidate_path)
    assert len(rows) == 74
    source_snapshot_sha = receipt["inputs"]["source_groups"]["sha256"]
    for row in rows:
        assert row["candidate_rights_status"] == "RIGHTS_UNKNOWN"
        assert row["candidate_status"] == "CANDIDATE_PENDING_CZ_CONFIRMATION"
        assert row["training_eligible"] is False
        assert row["allowed_use"] is None
        assert row["validity"] is None
        assert row["source_groups_authority_snapshot_sha256"] == source_snapshot_sha
        assert len(row["source_group_sha256"]) == 64
        assert len(row["decision_row_sha256"]) == 64
    ticket = (P4 / "RIGHTS_IMPORT_PREFLIGHT_TICKET.md").read_text(encoding="utf-8")
    assert receipt["output"]["sha256"] in ticket
    assert "21 passed" in ticket
    assert "REPLAY_ONLY" in ticket
    assert "TEST_ONLY" in ticket
    return receipt


def assert_chapter_audit() -> dict[str, Any]:
    audit = read_json(P4 / "CHAPTER_DIAG12_ELIGIBILITY_AUDIT.json")
    assert audit["audit_mode"] == "REGISTRY_ONLY_NO_CHAPTER_TEXT_READ"
    assert audit["candidate_record_count"] == len(audit["candidates"]) == 100
    assert audit["unique_chapter_sha_count"] == 89
    assert audit["eligible_count"] == 0
    assert audit["shortfall"] == 12
    assert audit["final_status"] == "HARD_STOP_NO_ELIGIBLE_COMPLETE_CHAPTERS"
    assert audit["unique_chapter_disposition"] == {
        "BLOCKED_SOURCE_ANOMALY": 2,
        "EVAL_HOLDOUT": 8,
        "TRAIN": 79,
    }
    assert not any(row["eligible"] for row in audit["candidates"])
    assert not any(row["sha_live_recomputed"] for row in audit["candidates"])
    for item in audit["evidence_files"]:
        path = Path(item["path"])
        assert path.stat().st_size == item["bytes"]
        assert sha256(path) == item["sha256"]
    return audit


def load_splitter():
    path = P4 / "tools/p4_splitter.py"
    spec = importlib.util.spec_from_file_location("p4_splitter_final", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def assert_splitter() -> dict[str, Any]:
    comparison = read_json(P4 / "toy_validation/r02/P4_TWO_RUN_COMPARISON.json")
    assert comparison["status"] == "PASS_R02_TOY_SPLITTER_TWO_RUN_BYTE_IDENTICAL"
    assert comparison["all_files_byte_identical"] is True
    run_1 = P4 / "toy_validation/r02/run_1/TOY_SPLITTER_BUILD.json"
    run_2 = P4 / "toy_validation/r02/run_2/TOY_SPLITTER_BUILD.json"
    assert run_1.read_bytes() == run_2.read_bytes()
    assert sha256(run_1) == comparison["comparisons"][0]["run_1_sha256"]

    splitter = load_splitter()
    text = "".join(f"第{index:03d}个完整原子单元含中文🙂。" for index in range(1, 73))
    raw = text.encode("utf-8")
    source_sha = sha256_bytes(raw)
    expected = {"P4-GRAN-10": 10, "P4-GRAN-20": 20, "P4-GRAN-30": 30}
    signatures = []
    for granularity, zone_count in expected.items():
        first = splitter.split_chapter(raw, "FINAL-TOY-72", granularity, source_sha)
        second = splitter.split_chapter(raw, "FINAL-TOY-72", granularity, source_sha)
        assert splitter.canonical_json_bytes(first) == splitter.canonical_json_bytes(second)
        assert first["actual_zone_count"] == zone_count
        assert "".join(zone["text"] for zone in first["zones"]).encode("utf-8") == raw
        signatures.append(
            tuple((zone["start_byte"], zone["end_byte_exclusive"]) for zone in first["zones"])
        )
    assert len(set(signatures)) == 3
    return comparison


def assert_contracts() -> None:
    wrnw = (P4 / "P4_WRNW_CONTRACT.md").read_text(encoding="utf-8")
    spec = (P4 / "P4_SPLITTER_SPEC.md").read_text(encoding="utf-8")
    prereg = (P4 / "P4_ZERO_TRAINING_PREREG.md").read_text(encoding="utf-8")
    result = (P4 / "P4_PREFLIGHT_RESULT_TICKET.md").read_text(encoding="utf-8")
    for token in (
        "共同可抽交集",
        "整章 all-gold",
        "跨区事实",
        "audit sidecar",
        "Doubao Mini/Lite",
    ):
        assert token in wrnw or token in prereg, token
    for token in ("P4-GRAN-10", "P4-GRAN-20", "P4-GRAN-30", "strict UTF-8"):
        assert token in spec, token
    for token in ("Holm", "10,000", "独立冻结的完整章 holdout", "0.02"):
        assert token in prereg, token
    assert FINAL_STATUS in result
    gaps = jsonl(P4 / "P4_PREFLIGHT_GAP_LIST.jsonl")
    assert len(gaps) >= 6
    assert any(row["gap_id"] == "P4-GAP-001" for row in gaps)


def run_checks() -> list[dict[str, Any]]:
    commands = [
        [
            "uv",
            "run",
            "--locked",
            "pytest",
            "-q",
            str(P4 / "tests"),
        ],
        [
            "uv",
            "run",
            "--locked",
            "ruff",
            "check",
            str(P4 / "tools"),
            str(P4 / "tests"),
        ],
    ]
    receipts = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=REPO,
            check=False,
            capture_output=True,
            text=True,
        )
        output = (completed.stdout + completed.stderr).strip()
        if completed.returncode != 0:
            raise RuntimeError(f"command failed: {' '.join(command)}\n{output}")
        receipts.append(
            {
                "command": " ".join(command),
                "exit_code": completed.returncode,
                "output": output,
            }
        )
    return receipts


def artifact_files() -> list[Path]:
    paths = []
    for path in P4.rglob("*"):
        if not path.is_file():
            continue
        if path.name in EXCLUDED_NAMES or path.suffix == ".pyc" or "__pycache__" in path.parts:
            continue
        paths.append(path)
    return sorted(paths)


def write_manifest() -> dict[str, Any]:
    members = [
        {
            "path": str(path.relative_to(P4)),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in artifact_files()
    ]
    manifest = {
        "schema_version": "t5-r04-p4-output-manifest-v1",
        "status": FINAL_STATUS,
        "member_count": len(members),
        "members": members,
    }
    path = P4 / "P4_OUTPUT_MANIFEST.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return manifest


def main() -> int:
    source_manifest = assert_source_manifest()
    c0 = assert_c0_binding()
    rights = assert_rights()
    chapter = assert_chapter_audit()
    splitter = assert_splitter()
    assert_contracts()
    test_receipts = run_checks()
    manifest = write_manifest()

    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    receipt = {
        "schema_version": "t5-r04-p4-final-validation-receipt-v1",
        "status": FINAL_STATUS,
        "validated_at_utc": now_utc.isoformat(),
        "validated_at_asia_shanghai": now_utc.astimezone(ZoneInfo("Asia/Shanghai")).isoformat(),
        "results": {
            "eligible_real_chapters": chapter["eligible_count"],
            "target_real_chapters": chapter["target_count"],
            "rights_groups": rights["coverage"]["source_groups"],
            "rights_allow_candidates": rights["coverage"]["allow_candidate"],
            "rights_training_eligible": rights["safety"]["training_eligible_groups"],
            "splitter_two_run_byte_identical": splitter["all_files_byte_identical"],
            "research_sources_verified": len(source_manifest["sources"]),
            "p3_c0_source_bound": c0["status"],
        },
        "preregistered": {
            "six_arms": True,
            "chapter_level_merge": True,
            "common_contained_fixed_denominator": True,
            "all_gold_fixed_denominator": True,
            "cross_zone_diagnostics": True,
            "multiple_comparison_rules": True,
            "independent_holdout": True,
        },
        "construction_failures_preserved": {
            "splitter_initial_api_mismatch": "5 failed",
            "rights_wrong_test_scope": "1 failed / 18 passed",
            "rights_replay_assertion_lag": "2 failed / 17 passed",
            "rights_test_only_assertion_lag": "3 failed / 17 passed",
            "rights_test_only_replay_status_lag": "1 failed / 19 passed",
            "final_validator_model_name_separator_mismatch": "1 failed before final receipt",
            "splitter_r01_invalidation_ticket": "construction_history/P4_SPLITTER_R01_INVALIDATION_TICKET.md",
            "rights_corrections_in_receipt": len(rights["preflight_corrections"]),
        },
        "tests": test_receipts,
        "actions_performed": {
            "training": False,
            "model_or_api_call": False,
            "real_novel_text_read": False,
            "synthetic_chapter_generation": False,
            "real_six_arm_run": False,
            "notion_write": False,
            "git_action": False,
            "current_pointer_change": False,
            "p2_or_p3_sealed_change": False,
            "production_canonical_generation": False,
        },
        "output_manifest": {
            "path": "P4_OUTPUT_MANIFEST.json",
            "member_count": manifest["member_count"],
            "sha256": sha256(P4 / "P4_OUTPUT_MANIFEST.json"),
        },
        "hard_stop": {
            "reason": "REAL_CHAPTER_DIAG12_ELIGIBLE_COUNT_BELOW_12",
            "next_run_authorized": False,
        },
    }
    path = P4 / "P4_FINAL_VALIDATION_RECEIPT.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": FINAL_STATUS,
                "receipt_sha256": sha256(path),
                "output_manifest_sha256": receipt["output_manifest"]["sha256"],
                "artifact_members": manifest["member_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
