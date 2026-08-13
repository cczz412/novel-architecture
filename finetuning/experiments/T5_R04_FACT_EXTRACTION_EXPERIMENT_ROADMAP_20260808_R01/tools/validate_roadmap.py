from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
ROADMAP = Path(__file__).resolve().parents[1]

EXPECTED_CATEGORY_COUNTS = {
    "独立 LoRA": 14,
    "无需独立新增 LoRA 的输入／推理格": 43,
    "完整章专项": 9,
}
REQUIRED_ARM_FIELDS = {
    "arm_id",
    "question_cn",
    "single_variable",
    "category",
    "data_requirement",
    "status",
    "checkpoint_or_parent",
    "known_result",
    "result_ticket_path",
    "result_ticket_sha256",
    "research_basis_paths",
    "prerequisites",
    "promotion_gate",
    "forbidden",
    "training_performed",
}
EXPECTED_M1_F1 = {
    "a_full": 0.769231,
    "c2_full": 0.893617,
    "d_range": 0.804348,
    "e_unit_quote": 0.865979,
}
EXPECTED_P3_F1 = {
    "c0_current_minimal": 0.893617,
    "c1_rulebook_8": 0.621622,
    "c2_purpose_short": 0.891304,
    "c4_previous_state_confirmed": 0.824742,
}
EXPECTED_BASE_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
EXPECTED_BASE_RECEIPT_SHA = (
    "431f5a7e82c46c716ac5419cd59bc4312bbc50292b09f0b3c842ab08b07d8bb6"
)
EXPECTED_P4_LOCKED_AGENTS_SHA = (
    "8d9d45562c1556d584266f1685cf02063c0582f745f2c66fd05c4807519d14de"
)
EXPECTED_CURRENT_AGENTS_SHA = (
    "c66848166159a44c21a548137393e0f08ab03e6f536661ba22c610f62f8f089e"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def check_arm_registry(errors: list[str]) -> dict:
    registry = load_json(ROADMAP / "ARM_REGISTRY.json")
    arms = registry["arms"]
    ids = [arm["arm_id"] for arm in arms]
    if len(arms) != 66:
        errors.append(f"ARM_COUNT:{len(arms)}")
    if len(ids) != len(set(ids)):
        errors.append("ARM_ID_DUPLICATE")
    for arm in arms:
        missing = REQUIRED_ARM_FIELDS - set(arm)
        if missing:
            errors.append(f"ARM_FIELDS:{arm.get('arm_id')}:{sorted(missing)}")
        if arm.get("category") not in registry["allowed_categories"]:
            errors.append(f"ARM_CATEGORY:{arm.get('arm_id')}")
        if arm.get("status") not in registry["allowed_statuses"]:
            errors.append(f"ARM_STATUS:{arm.get('arm_id')}")
        parent = arm.get("checkpoint_or_parent")
        if not isinstance(parent, dict) or not parent.get("id"):
            errors.append(f"ARM_PARENT_MISSING:{arm.get('arm_id')}")
        if arm.get("category") == "独立 LoRA":
            if parent.get("id") == "QWEN3_4B_ORIGINAL_BASE":
                if parent.get("model_revision") != EXPECTED_BASE_REVISION:
                    errors.append(f"LORA_BASE_REVISION:{arm.get('arm_id')}")
                if parent.get("model_receipt_sha256") != EXPECTED_BASE_RECEIPT_SHA:
                    errors.append(f"LORA_BASE_RECEIPT:{arm.get('arm_id')}")
            elif not parent.get("sha256"):
                errors.append(f"LORA_PARENT_SHA_MISSING:{arm.get('arm_id')}")
    category_counts = Counter(arm["category"] for arm in arms)
    if dict(category_counts) != EXPECTED_CATEGORY_COUNTS:
        errors.append(f"CATEGORY_COUNTS:{dict(category_counts)}")
    authority = registry["authority_boundary"]
    if any(
        authority[key]
        for key in (
            "may_call_model_or_api",
            "may_train",
            "may_generate_data",
            "may_change_current_pointer",
            "local_qwen_is_production_model",
            "s02_rights_exclusion_candidate_training_eligible",
        )
    ):
        errors.append("AUTHORITY_BOUNDARY_NOT_FALSE")

    arm_by_id = {arm["arm_id"]: arm for arm in arms}
    metadata_ids = {
        "FULL-META-M0-NONE",
        "FULL-META-M1-REAL",
        "FULL-META-C-NONCE",
    }
    if {
        arm_by_id[arm_id].get("shared_control_binding_id")
        for arm_id in metadata_ids
    } != {"META_WRNW_FIXED_CONDITION_R01"}:
        errors.append("METADATA_SHARED_WRNW_BINDING")
    metadata_contract = registry["family_contracts"].get(
        "META_WRNW_FIXED_CONDITION_R01", {}
    )
    required_metadata_controls = {
        "checkpoint_sha256",
        "chapter_set_sha256",
        "read_mode",
        "granularity",
        "splitter_sha256",
        "model_visible_payload_except_metadata",
        "decode",
        "evaluator",
    }
    if set(metadata_contract.get("must_bind_same_values", [])) != (
        required_metadata_controls
    ):
        errors.append("METADATA_CONTROL_SET")

    retrieved = arm_by_id.get("INPUT-EX-RETRIEVED-BOUNDARY-0TO2", {})
    retrieved_forbidden = " ".join(retrieved.get("forbidden", []))
    if not all(token in retrieved_forbidden for token in ("gold", "case_id", "模型输出")):
        errors.append("RETRIEVED_EXAMPLE_LEAKAGE_GUARD")

    facts_first_contract = registry["family_contracts"].get(
        "FACTS_FIRST_ZERO_TRAINING_GATE_R01", {}
    )
    if facts_first_contract.get("status") != "NEEDS_METRIC_CONTRACT":
        errors.append("FACTS_FIRST_GATE_STATUS")
    if facts_first_contract.get("execution_ready") is not False:
        errors.append("FACTS_FIRST_GATE_EXECUTION_READY")
    if facts_first_contract.get("pass_thresholds") is not None:
        errors.append("FACTS_FIRST_THRESHOLDS_PREMATURELY_SET")
    metric_evidence = facts_first_contract.get("metric_evidence", {})
    for path_key, sha_key in (
        ("m1_scorer_path", "m1_scorer_sha256"),
        ("m1_semantic_scorer_path", "m1_semantic_scorer_sha256"),
        ("m1_dev_comparison_path", "m1_dev_comparison_sha256"),
    ):
        path = resolve(metric_evidence.get(path_key, ""))
        if not path.is_file() or sha256(path) != metric_evidence.get(sha_key):
            errors.append(f"FACTS_FIRST_METRIC_EVIDENCE:{path_key}")
    if "42/42" not in facts_first_contract.get("known_metric_gap", ""):
        errors.append("FACTS_FIRST_42_42_GAP_NOT_RECORDED")
    for arm_id in (
        "INPUT-FS-GOLD-FACTS-CITATION-ORACLE",
        "INPUT-FS-PREDICTED-FACTS-CITATION",
    ):
        if arm_id not in arm_by_id:
            errors.append(f"FACTS_FIRST_GATE_ARM_MISSING:{arm_id}")
    for arm_id in ("LORA-FS-STAGE1-FACTS", "LORA-FS-STAGE2-CITATION"):
        if arm_by_id[arm_id].get("gate_state") != "BLOCKED_NEEDS_METRIC_CONTRACT":
            errors.append(f"FACTS_FIRST_LORA_NOT_BLOCKED:{arm_id}")
    for arm in arms:
        prerequisites = " ".join(arm.get("prerequisites", []))
        if "CONFIRM24" in prerequisites or "确认集" in prerequisites or "确认门" in prerequisites:
            errors.append(f"FAMILY_PREREQUISITE_USES_CONFIRM24:{arm['arm_id']}")
    return {
        "arm_count": len(arms),
        "category_counts": dict(category_counts),
        "status_counts": dict(Counter(arm["status"] for arm in arms)),
    }


def iter_source_records(source_map: dict):
    for pair in source_map["research_pairs"]:
        yield f"{pair['pair_id']}:raw", pair["raw"]
        yield f"{pair['pair_id']}:conclusion", pair["conclusion"]
    for source in source_map["historical_sources"]:
        yield source["source_id"], source
    for source in source_map["local_sources"]:
        yield source["source_id"], source


def check_source_map(errors: list[str]) -> dict:
    source_map = load_json(ROADMAP / "SOURCE_MAP.json")
    checked = 0
    ids: list[str] = []
    for source_id, record in iter_source_records(source_map):
        ids.append(source_id)
        path = resolve(record["path"])
        if not path.is_file():
            errors.append(f"SOURCE_MISSING:{source_id}:{path}")
            continue
        actual = sha256(path)
        if actual != record["sha256"]:
            errors.append(f"SOURCE_SHA:{source_id}:{actual}")
        checked += 1
    if len(ids) != len(set(ids)):
        errors.append("SOURCE_ID_DUPLICATE")
    if len(source_map["research_pairs"]) != 6:
        errors.append("RESEARCH_PAIR_COUNT")
    return {"source_records_checked": checked, "research_pair_count": 6}


def check_known_results(errors: list[str]) -> dict:
    m1 = load_json(
        ROOT
        / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/m1_r01/closeout_r01/DEV24_COMPARISON_UPDATE72.json"
    )
    m1_seen = {
        row["arm"]: row["semantic_recoverable"]["f1"] for row in m1["rows"]
    }
    if m1_seen != EXPECTED_M1_F1:
        errors.append(f"M1_F1:{m1_seen}")

    p3 = load_json(
        ROOT
        / "finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01/results_r01/scoring_r02/CONTEXT_CONTRACT_METRICS.json"
    )
    p3_seen = {
        arm_id: p3["metrics"][arm_id]["semantic_recoverable"]["f1"]
        for arm_id in EXPECTED_P3_F1
    }
    if p3_seen != EXPECTED_P3_F1:
        errors.append(f"P3_F1:{p3_seen}")
    leakage = p3["diagnostics"]["c4_background_only_unsupported_fact"]["count"]
    if leakage != 2:
        errors.append(f"P3_C4_LEAKAGE:{leakage}")

    semantic = load_json(
        ROOT
        / "finetuning/experiments/T5_R04_SEMANTIC_CORE_MIX_PROBE_20260807_R01/dev_core/zero_training_r01/results/BLIND_SEMANTIC_METRICS.json"
    )
    z00 = semantic["Z00_A"]
    z01 = semantic["Z01_C2"]
    marker_delta_points = (z01["f1"] - z00["f1"]) * 100
    if abs(marker_delta_points - (-4.121763143179635)) > 1e-12:
        errors.append(f"SEMANTIC_MARKER_F1_DELTA:{marker_delta_points}")
    if z01["predicted_fact_count"] - z00["predicted_fact_count"] != 46:
        errors.append("SEMANTIC_MARKER_PREDICTED_DELTA")
    if z01["covered_gold_facts"] - z00["covered_gold_facts"] != 1:
        errors.append("SEMANTIC_MARKER_COVERAGE_DELTA")

    s02 = load_json(
        ROOT
        / "finetuning/experiments/T5_R04_A_V2_7_RIGHTS_EXCLUSION_CANDIDATE_20260808_R01/RIGHTS_EXCLUSION_IMPORT_RECEIPT.json"
    )
    coverage = s02["coverage"]
    expected_s02 = {
        "source_groups": 74,
        "rows": 314,
        "facts": 2783,
        "reject_candidate": 74,
        "allow_candidate": 0,
    }
    for key, expected in expected_s02.items():
        if coverage[key] != expected:
            errors.append(f"S02_{key}:{coverage[key]}")
    if s02["safety"]["training_eligible_groups"] != 0:
        errors.append("S02_TRAINING_ELIGIBLE")

    p4 = load_json(
        ROOT
        / "finetuning/experiments/T5_R04_WIDE_READ_NARROW_WRITE_P4_PREFLIGHT_20260808_R01/P4_FINAL_VALIDATION_RECEIPT.json"
    )
    if p4["actions_performed"]["model_or_api_call"]:
        errors.append("P4_MODEL_OR_API_CALL")
    if p4["results"]["eligible_real_chapters"] != 0:
        errors.append("P4_REAL_CHAPTER_COUNT")

    return {
        "m1_semantic_f1": m1_seen,
        "p3_semantic_f1": p3_seen,
        "p3_c4_leakage_cases": leakage,
        "semantic_marker": {
            "z00_f1": z00["f1"],
            "z01_f1": z01["f1"],
            "delta_points_exact": marker_delta_points,
            "delta_points_rounded_2dp": round(marker_delta_points, 2),
            "extra_predictions": 46,
            "extra_gold_coverage": 1,
        },
        "s02_counts": expected_s02,
        "p4_model_inference_calls": 0,
    }


def check_markdown_footers(errors: list[str]) -> dict:
    markdown_files = sorted(ROADMAP.glob("*.md"))
    for path in markdown_files:
        text = path.read_text(encoding="utf-8").rstrip()
        if not text.endswith("来源：Codex"):
            errors.append(f"MISSING_SOURCE_FOOTER:{path.name}")
    return {"markdown_files_checked": len(markdown_files)}


def check_contract_language(errors: list[str]) -> dict:
    texts = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(ROADMAP.glob("*.md"))
    }
    combined = "\n".join(texts.values())
    if "4.13" in combined:
        errors.append("STALE_MARKER_DELTA_4_13")
    if "同 checkpoint 输入对照" in combined:
        errors.append("STALE_INPUT_CATEGORY_NAME")
    queue = texts["EXECUTION_QUEUE.md"]
    required_phrases = (
        "禁止把不同家族交叉成全因子大组合",
        "Gold facts → citation Oracle",
        "NEEDS_METRIC_CONTRACT",
        "META_WRNW_FIXED_CONDITION_R01",
        "看到 CONFIRM24 结果之前",
    )
    for phrase in required_phrases:
        if phrase not in queue:
            errors.append(f"QUEUE_CONTRACT_MISSING:{phrase}")
    data_pool = texts["DATA_POOL_PLAN.md"]
    if "CONFIRM24 只运行一次" not in data_pool:
        errors.append("CONFIRM24_REUSE_GUARD_MISSING")
    if "只给已冻结的 `C0 vs BEST-SHORT-CONTRACT` 最终合同使用一次" not in texts["RESULT_TICKET.md"]:
        errors.append("CONFIRM24_RESULT_TICKET_CONFLICT")
    return {"required_contract_phrases_checked": len(required_phrases) + 1}


def check_p4_drift(errors: list[str]) -> dict:
    source_map = load_json(ROADMAP / "SOURCE_MAP.json")
    drift = source_map.get("drift_dispositions", [])
    if len(drift) != 1:
        errors.append(f"P4_DRIFT_RECORD_COUNT:{len(drift)}")
        return {"drift_recorded": False}
    record = drift[0]
    p4_manifest = load_json(resolve(record["upstream_artifact"]))
    p4_agents = next(
        source
        for source in p4_manifest["sources"]
        if source["source_id"] == "P4-LOCAL-AGENTS"
    )
    current_agents_sha = sha256(ROOT / "AGENTS.md")
    if p4_agents["sha256"] != EXPECTED_P4_LOCKED_AGENTS_SHA:
        errors.append("P4_LOCKED_AGENTS_SHA")
    if current_agents_sha != EXPECTED_CURRENT_AGENTS_SHA:
        errors.append(f"CURRENT_AGENTS_SHA:{current_agents_sha}")
    if current_agents_sha == p4_agents["sha256"]:
        errors.append("P4_DRIFT_NOT_PRESENT")
    if record.get("current_recursive_reverification") != "FAIL_UPSTREAM_CONTEXT_DRIFT":
        errors.append("P4_DRIFT_DISPOSITION")
    return {
        "drift_recorded": True,
        "p4_locked_agents_sha256": p4_agents["sha256"],
        "current_agents_sha256": current_agents_sha,
        "recursive_reverification": "FAIL_UPSTREAM_CONTEXT_DRIFT_NO_RESEAL",
    }


def check_pointer_observations(errors: list[str]) -> dict:
    source_map = load_json(ROADMAP / "SOURCE_MAP.json")
    observations = {
        row["path"]: row for row in source_map["concurrent_state_observations"]
    }
    expected_paths = {"governance/CURRENT_STATE.json", "finetuning/CURRENT.json"}
    if set(observations) != expected_paths:
        errors.append("POINTER_OBSERVATION_SET")
        return observations

    governance = observations["governance/CURRENT_STATE.json"]
    if governance["roadmap_opening_sha256"] != (
        "1d1fca5302cc1fea62e12a8a5362ab7fb9f6a6b9a0b945f886f27e173ec569bc"
    ):
        errors.append("GOVERNANCE_OPENING_SHA")
    if governance.get("changed_by_this_roadmap") is not False:
        errors.append("GOVERNANCE_DRIFT_OWNERSHIP")
    if governance.get("disposition") != (
        "EXTERNAL_CONCURRENT_DRIFT_NOT_ROADMAP_FAILURE_DO_NOT_REVERT"
    ):
        errors.append("GOVERNANCE_DRIFT_DISPOSITION")

    finetuning = observations["finetuning/CURRENT.json"]
    if finetuning["roadmap_opening_sha256"] != (
        "5abaa79b952532881dfc5e147e7da190471baba386aac263474b51edd414f8dd"
    ):
        errors.append("FINETUNING_CURRENT_OPENING_SHA")
    if finetuning.get("changed_by_this_roadmap") is not False:
        errors.append("FINETUNING_CURRENT_OWNERSHIP")

    current = {}
    for rel, observation in observations.items():
        actual = sha256(ROOT / rel)
        current[rel] = actual
        if actual != observation["seal_observed_sha256"]:
            errors.append(f"POINTER_SEAL_OBSERVATION:{rel}:{actual}")
    return {
        "observations": observations,
        "current_sha256": current,
    }


def check_manifest(errors: list[str]) -> dict:
    manifest_path = ROADMAP / "OUTPUT_MANIFEST.json"
    manifest = load_json(manifest_path)
    listed = manifest["files"]
    names = [entry["path"] for entry in listed]
    if len(names) != len(set(names)):
        errors.append("MANIFEST_DUPLICATE_PATH")
    for entry in listed:
        path = ROADMAP / entry["path"]
        if not path.is_file():
            errors.append(f"MANIFEST_MISSING:{entry['path']}")
            continue
        if path.stat().st_size != entry["bytes"]:
            errors.append(f"MANIFEST_BYTES:{entry['path']}")
        actual = sha256(path)
        if actual != entry["sha256"]:
            errors.append(f"MANIFEST_SHA:{entry['path']}:{actual}")
    if "OUTPUT_MANIFEST.json" in names or "FINAL_VALIDATION_RECEIPT.json" in names:
        errors.append("MANIFEST_RECURSIVE_MEMBER")
    return {"manifest_member_count": len(listed)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("pre", "final"), default="pre")
    args = parser.parse_args()

    errors: list[str] = []
    report = {
        "arms": check_arm_registry(errors),
        "sources": check_source_map(errors),
        "known_results": check_known_results(errors),
        "markdown": check_markdown_footers(errors),
        "contracts": check_contract_language(errors),
        "p4_drift": check_p4_drift(errors),
        "protected_pointers": check_pointer_observations(errors),
    }
    if args.stage == "final":
        report["manifest"] = check_manifest(errors)
        receipt = load_json(ROADMAP / "FINAL_VALIDATION_RECEIPT.json")
        if receipt["status"] != "PASS_ROADMAP_R01_GOVERNANCE_ONLY_HARD_STOP":
            errors.append("FINAL_RECEIPT_STATUS")
        verifier_history = {
            row["system"]: row for row in receipt.get("old_verifier_call_history", [])
        }
        if set(verifier_history) != {"P3", "P4", "S02"}:
            errors.append("OLD_VERIFIER_HISTORY_SET")
        elif not all(row.get("called") for row in verifier_history.values()):
            errors.append("OLD_VERIFIER_CALL_NOT_RECORDED")
        if verifier_history.get("P4", {}).get("result") != (
            "HARD_STOP_ASSERTION_ERROR_P4_LOCAL_AGENTS"
        ):
            errors.append("P4_VERIFIER_RESULT_LEDGER")
        s02_history = verifier_history.get("S02", {})
        if not s02_history.get("transient_byte_change") or not s02_history.get(
            "restored_original_bytes"
        ):
            errors.append("S02_TRANSIENT_RESTORE_LEDGER")
        actions = receipt.get("actions_performed", {})
        if not all(
            actions.get(key)
            for key in (
                "p3_old_verifier_run",
                "p4_old_verifier_run",
                "s02_old_verifier_run",
                "old_receipt_transient_change_then_restored",
            )
        ):
            errors.append("OLD_VERIFIER_ACTION_LEDGER")
        if actions.get("old_verifier_run_during_corrective_revision") is not False:
            errors.append("CORRECTIVE_REVISION_RERAN_OLD_VERIFIER")
        review = receipt.get("independent_readonly_review", {})
        if review.get("old_p4_or_s02_verifier_run") is not True:
            errors.append("INDEPENDENT_REVIEW_OLD_VERIFIER_ACTION_LEDGER")
        if review.get("completed_old_rerun_or_reseal") is not False:
            errors.append("INDEPENDENT_REVIEW_OLD_RERUN_OR_RESEAL_LEDGER")

    payload = {
        "status": "PASS" if not errors else "FAIL",
        "stage": args.stage,
        "report": report,
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
