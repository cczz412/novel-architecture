#!/usr/bin/env python3
"""Independent mechanical verifier for the P3 dual-track deliverables."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path("/Users/a1234/挣钱/小说架构")
EXP = REPO / "finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01"
SEALED = EXP / "sealed_inputs_r01"
RESULTS = EXP / "results_r01"
SCORING = RESULTS / "scoring_r02"
P2 = REPO / "finetuning/experiments/T5_R04_PRODUCTION_CANONICAL_PREREQUISITE_REPAIR_P2_20260808_R01/sealed_r01"
CANONICAL = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/set_b_r03_work/sealed/T5_R04_SYNTHETIC_MICRO24_SET_B_R03_20260808/canonical/CANONICAL_MICRO24_SET_B_R03.jsonl"
OLD_METRICS = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/m1_r01/semantic_scoring_r01/M1_FINAL_LAYERED_METRICS.json"
ARMS = ("c0_current_minimal", "c1_rulebook_8", "c2_purpose_short", "c4_previous_state_confirmed")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail(message: str) -> None:
    raise RuntimeError(message)


def main() -> None:
    # Track A: recompute the exact 314-row source partition from current P2 sealed bytes.
    p2_receipt = json.loads((EXP / "P3_P2_SOURCE_BINDING_RECEIPT.json").read_text(encoding="utf-8"))
    for name, binding in p2_receipt["bindings"].items():
        path = REPO / binding["path"]
        if path.stat().st_size != binding["bytes"] or sha256(path) != binding["sha256"]:
            fail(f"P2 sealed binding drift: {name}")
    ledger = read_jsonl(P2 / "PRODUCTION_ELIGIBILITY_LEDGER_398.jsonl")
    ordinary = [row for row in ledger if row.get("rights_status") == "RIGHTS_UNKNOWN"]
    groups = read_jsonl(SEALED / "track_a/RIGHTS_SOURCE_GROUPS_314.jsonl")
    templates = read_jsonl(SEALED / "track_a/RIGHTS_DECISION_TEMPLATE.jsonl")
    if len(ordinary) != 314 or sum(row["facts_count"] for row in ordinary) != 2783:
        fail("P2 ordinary denominator drift")
    if len(groups) != 74 or len(templates) != 74:
        fail("rights group/template denominator drift")
    ledger_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ordinary:
        ledger_by_source[row["source_id"]].append(row)
    grouped_row_ids: list[str] = []
    for group in groups:
        source_id = group["source_identity"]["source_id"]
        source_rows = ledger_by_source[source_id]
        if group["coverage"]["row_count"] != len(source_rows):
            fail(f"rights group row count mismatch: {source_id}")
        if group["coverage"]["fact_count"] != sum(row["facts_count"] for row in source_rows):
            fail(f"rights group fact count mismatch: {source_id}")
        if set(group["coverage"]["row_ids"]) != {row["row_id"] for row in source_rows}:
            fail(f"rights group row identity mismatch: {source_id}")
        if group["candidate_decision"] != "RIGHTS_UNKNOWN":
            fail(f"rights group was silently promoted: {source_id}")
        grouped_row_ids.extend(group["coverage"]["row_ids"])
    if len(grouped_row_ids) != 314 or len(set(grouped_row_ids)) != 314 or set(grouped_row_ids) != {row["row_id"] for row in ordinary}:
        fail("314 rights rows do not close one-to-one")

    # Track B: same canonical, same user/assistant messages, only the pre-registered system suffix changes.
    canonical_rows = read_jsonl(CANONICAL)
    if len(canonical_rows) != 24 or sum(len(row["facts"]) for row in canonical_rows) != 48:
        fail("DEV24 denominator drift")
    canonical = {row["case_id"]: row for row in canonical_rows}
    questions: dict[str, list[dict[str, Any]]] = {}
    for arm in ARMS:
        rows = read_jsonl(SEALED / f"track_b/prompts/{arm}_QUESTIONS_24.jsonl")
        if len(rows) != 24 or [row["case_id"] for row in rows] != list(canonical):
            fail(f"question denominator/order drift: {arm}")
        questions[arm] = rows
    for index, base in enumerate(questions["c0_current_minimal"]):
        for arm in ARMS[1:]:
            candidate = questions[arm][index]
            if candidate["messages"][1:] != base["messages"][1:]:
                fail(f"user or assistant bytes changed: {arm}/{base['case_id']}")
            added = candidate["messages"][0]["content"][len(base["messages"][0]["content"]):]
            if not added:
                fail(f"missing pre-registered system suffix: {arm}/{base['case_id']}")
            for fact in canonical[base["case_id"]]["facts"]:
                if fact["fact_sentence"] and fact["fact_sentence"] in added:
                    fail(f"gold leaked verbatim into system suffix: {arm}/{base['case_id']}")
    c4_cases = {row["case_id"]: row for row in questions["c4_previous_state_confirmed"]}
    for case_id, case in canonical.items():
        if case["source"]["read_only_before"] not in c4_cases[case_id]["messages"][0]["content"]:
            fail(f"C4 before provenance missing: {case_id}")

    # Raw inference and baseline identity.
    if sha256(REPO / "finetuning/CURRENT.json") != "5abaa79b952532881dfc5e147e7da190471baba386aac263474b51edd414f8dd":
        fail("finetuning current pointer drift")
    baseline = json.loads((RESULTS / "CONTEXT_BASELINE_REPRODUCTION_RECEIPT.json").read_text(encoding="utf-8"))
    if baseline.get("status") != "PASS_C0_BASELINE_STABLE_PROJECTION_BYTE_IDENTICAL" or baseline.get("differences"):
        fail("C0 baseline did not reproduce")
    raw_bindings = {}
    for arm in ARMS:
        raw_path = RESULTS / "raw" / arm / "RAW_OUTPUTS.jsonl"
        receipt_path = RESULTS / "raw" / arm / "INFERENCE_RECEIPT.json"
        rows = read_jsonl(raw_path)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if len(rows) != 24 or [row["case_id"] for row in rows] != list(canonical):
            fail(f"raw denominator/order drift: {arm}")
        if receipt.get("raw_sha256") != sha256(raw_path) or receipt.get("training") is not False or receipt.get("api_called") is not False:
            fail(f"raw receipt mismatch or forbidden action: {arm}")
        if any(row["finish_reason"] != "stop" or not row["stop_token_is_eos_eot"] for row in rows):
            fail(f"non-clean stop found: {arm}")
        raw_bindings[arm] = sha256(raw_path)

    # Score closure and exact preservation of the historical C0 score.
    metrics_doc = json.loads((SCORING / "CONTEXT_CONTRACT_METRICS.json").read_text(encoding="utf-8"))
    metrics = metrics_doc["metrics"]
    old = json.loads(OLD_METRICS.read_text(encoding="utf-8"))
    old_c0 = next(row for row in old["metrics"] if row["arm"] == "c2_full" and row["optimizer_update"] == 72 and row["split"] == "dev24")
    for key in ("strict_fact", "normalized_fact", "semantic_recoverable", "semantic_structured", "complete_schema", "status_legality", "status_accuracy_on_semantic_matches", "speaker_accuracy_on_semantic_matches", "output_tokens"):
        if metrics["c0_current_minimal"][key] != old_c0[key]:
            fail(f"C0 metric drift: {key}")
    for key in ("clean_cases", "repetition_cases", "token_limit_cases"):
        if metrics["c0_current_minimal"]["termination"][key] != old_c0["termination"][key]:
            fail(f"C0 termination metric drift: {key}")
    if metrics["c0_current_minimal"]["termination"]["exact_duplicate_objects"] != 0:
        fail("C0 duplicate-object metric drift")
    if metrics["c0_current_minimal"]["prediction_count"] != old_c0["prediction_count"]:
        fail("C0 prediction count drift")
    adjudications = read_jsonl(SCORING / "P3_SEMANTIC_ADJUDICATION_79.jsonl")
    if len(adjudications) != 79 or len({(row["case_id"], row["prediction_fact"]) for row in adjudications}) != 79:
        fail("semantic adjudication denominator drift")
    if Counter(row["review_source"] for row in adjudications) != Counter({"REUSED_FROZEN_M1_SAME_CASE_IDENTICAL_PREDICTION": 69, "P3_INDEPENDENT_SAME_CASE_REVIEW": 10}):
        fail("semantic adjudication source counts drift")
    paired = read_jsonl(SCORING / "CONTEXT_CONTRACT_PAIRED_CASES_24.jsonl")
    if len(paired) != 24 or len({row["case_id"] for row in paired}) != 24 or any(set(row["arms"]) != set(ARMS) for row in paired):
        fail("paired case report drift")
    leak = metrics_doc["diagnostics"]["c4_background_only_unsupported_fact"]
    if leak["count"] != 2 or leak["case_ids"] != ["MICRO24B-S16", "MICRO24B-S23"]:
        fail("C4 read-only leakage denominator drift")

    # Manifest is non-circular: it binds all managed deliverables except itself and this receipt.
    manifest_path = EXP / "P3_OUTPUT_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "P3_HARD_STOP_COMPLETE_CANDIDATE_LOCAL_RESULT":
        fail("P3 output manifest status invalid")
    for member in manifest["members"]:
        path = EXP / member["path"]
        if not path.is_file() or path.stat().st_size != member["bytes"] or sha256(path) != member["sha256"]:
            fail(f"manifest member mismatch: {member['path']}")
    receipt = {
        "status": "PASS_P3_FINAL_MECHANICAL_VALIDATION_HARD_STOP",
        "rights": {"rows": 314, "facts": 2783, "groups": 74, "approved_groups": 0},
        "context": {"arms_run": list(ARMS), "cases_each": 24, "raw_outputs": 96, "semantic_unique_predictions": 79, "new_same_case_reviews": 10, "c3_not_run": True, "c5_not_run": True},
        "c0_baseline_stable_projection_sha256": baseline["new_stable_projection_sha256"],
        "raw_bindings": raw_bindings,
        "manifest_sha256": sha256(manifest_path),
        "managed_member_count": manifest["member_count"],
        "training": False, "api_called": False, "p2_sealed_modified": False, "current_pointer_modified": False,
    }
    target = EXP / "P3_FINAL_VALIDATION_RECEIPT.json"
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
