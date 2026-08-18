#!/usr/bin/env python3
"""Run the single C11 r1->r2 stale-propagation contract/runtime probe."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any


os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

REPO = Path("/Users/a1234/挣钱/小说架构")
ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
CONTRACTS = REPO / "novel-mvp/contracts"

INPUTS = [
    CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.md",
    CONTRACTS / "C1_CHAPTER_DOC.md",
    CONTRACTS / "C4_FACT_QUERY.md",
    CONTRACTS / "C6_HEALTH_REPORT.md",
    CONTRACTS / "PLAN_LEDGER_STORAGE.md",
    CONTRACTS / "RECONCILIATION_FACT_ADMISSION_ACTION.md",
    CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.schema.json",
    CONTRACTS / "validate_c11_chapter_revision_ledger.py",
    REPO
    / "TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/CZ_ONE_PAGE_VERDICT.md",
    REPO
    / "TEMP/chatgpt_review_returns/R13_SIX_WINDOW_CURRENT_FORMAL_REVIEW_R04_ADVISORY_20260819_R01/extracted/05_NEXT_TASK_PORTFOLIO.md",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_c11_validator():
    path = CONTRACTS / "validate_c11_chapter_revision_ledger.py"
    sys.path.insert(0, str(CONTRACTS))
    spec = importlib.util.spec_from_file_location("c11_one_scenario_probe", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("C11_VALIDATOR_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def has_all(text: str, anchors: list[str]) -> bool:
    return all(anchor in text for anchor in anchors)


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    missing = [str(path) for path in INPUTS if not path.is_file()]
    if missing:
        write_json(
            RESULTS / "probe_result.json",
            {
                "task_id": "D-C11-R2-STALE-PROPAGATION-ONE-SCENARIO-01",
                "status": "RUNTIME_OR_CONTRACT_GAP_FOUND",
                "material_status": "MATERIAL_MISSING",
                "missing": missing,
            },
        )
        return 2

    before = {str(path): sha256_file(path) for path in INPUTS}
    c11 = load_c11_validator()

    old_text = "甲拿起钥匙。乙离开。"
    new_text = "甲放下钥匙。乙回家。"
    quote = "甲拿起钥匙。"
    r1 = c11.ledger_one(old_text)
    r2 = c11.append_replace(r1, new_text, operation_id="op-c11-r2")
    c11.validate_ledger(r2, previous=r1)
    c11.validate_schema_document(c11.schema_validator(), r2)
    current = r2["revisions"][-1]
    current_ref = c11.revision_ref("c01", 2, new_text)

    # This C1 document is only a scenario fixture for an equality predicate.
    # It is not a substitute for a product current-view writer.
    c1_fixture = {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": "c01",
        "title": current["title"],
        "kind": "draft",
        "text": new_text,
        "added_at": "2026-08-19 00:00:00",
        "chapter_revision_ref": current_ref,
    }
    c11.validate_schema_document(c11.schema_validator(), c1_fixture)
    c1_identity_predicate = (
        c1_fixture["id"] == r2["chapter_id"]
        and c1_fixture["chapter_revision_ref"] == current_ref
        and current["text_sha256"] == c11.sha256_text(c1_fixture["text"])
        and current["text_sha256"]
        == c1_fixture["chapter_revision_ref"]["revision_text_sha256"]
    )

    fact_r1 = c11.base_fact(old_text, quote, verified=True)
    fact_r2 = c11.migrate_fact(fact_r1, old_text, new_text, 2)
    consumer_results = {
        consumer: c11.consumer_allows(fact_r2, consumer)
        for consumer in ("M6", "M8", "M11")
    }

    plan_contract = (CONTRACTS / "PLAN_LEDGER_STORAGE.md").read_text(
        encoding="utf-8"
    )
    c11_contract = (CONTRACTS / "C11_CHAPTER_REVISION_LEDGER.md").read_text(
        encoding="utf-8"
    )
    c1_contract = (CONTRACTS / "C1_CHAPTER_DOC.md").read_text(encoding="utf-8")
    c4_contract = (CONTRACTS / "C4_FACT_QUERY.md").read_text(encoding="utf-8")
    c6_contract = (CONTRACTS / "C6_HEALTH_REPORT.md").read_text(encoding="utf-8")
    admission_contract = (
        CONTRACTS / "RECONCILIATION_FACT_ADMISSION_ACTION.md"
    ).read_text(encoding="utf-8")

    formal_cases = {
        case_id: c11.evaluate(case_id)
        for case_id in (
            "CR-02",
            "CR-17",
            "CR-23",
            "CR-24",
            "CR-40",
            "CR-12",
            "CR-13",
            "CR-29",
            "CR-30",
            "CR-41",
        )
    }

    old_admission_action = {
        "operation_id": "op-admit-r1",
        "chapter_ref": "c01",
        "chapter_revision_ref": c11.revision_ref("c01", 1, old_text),
        "chapter_text_sha256": c11.sha256_text(old_text),
    }
    stale_action_predicate = (
        old_admission_action["chapter_revision_ref"] != current_ref
        and old_admission_action["chapter_text_sha256"]
        != c11.sha256_text(c1_fixture["text"])
    )

    contract_anchors = {
        "fact_evidence_gone_and_consumers": has_all(
            c11_contract,
            ["needs_recheck / evidence_gone", "M6、M8、M11 不消费"],
        ),
        "basis_pin_and_re_stale": has_all(
            plan_contract,
            [
                "pin_status",
                "needs_recheck",
                "edge_status=stale",
                "actual_fact_refs",
            ],
        ),
        "actual_unsupported_when_not_current": has_all(
            plan_contract,
            ["actual 派生支持必须同时满足", "任一不满足即不得支持 actual"],
        ),
        "c6_reader_derives_stale": has_all(
            c6_contract,
            ["由读取端与 C11 派生", "整份报告的 `source_revision_state` 派生为 STALE"],
        ),
        "admission_rejects_before_writes": has_all(
            admission_contract,
            ["任一失败都在写前拒绝", "facts 与 planstore 都保持 0 变化"],
        ),
        "shared_lock_and_atomic_group": has_all(
            c11_contract,
            ["复用现有 `.planstore.lock`", "恢复只能得到完整 before 或完整 after"],
        ),
        "idempotency_and_conflict": has_all(
            admission_contract,
            ["同号同载荷回放", "同号不同载荷拒绝"],
        ),
    }

    explicit_runtime_gaps = {
        "c1_v1_current_view_writer": "现役产品仍输出 v0-r01" in c1_contract,
        "c4_revision_aware_product_writer": "revision-aware 产品迁移另开施工票"
        in c4_contract,
        "planstore_r07_revision_seam": "r07 chapter revision 接缝正式冻结、产品实现待下一票"
        in plan_contract,
        "reconciliation_v2_admission": "现役 `reconcile.py` 仍实现 v1"
        in admission_contract,
        "c6_v1_current_reader_not_in_supplied_executable_surface": not hasattr(
            c11, "derive_c6_source_revision_state"
        ),
        "cross_owner_revision_commit_coordinator": not hasattr(
            c11, "commit_revision_transaction"
        ),
    }

    gates = [
        {
            "gate": 1,
            "name": "C11 current -> C1 current view exact identity",
            "contract_or_validator_check": c1_identity_predicate,
            "runtime_execution": "UNTESTABLE",
            "verdict": "VALIDATOR_FIXTURE_PASS__RUNTIME_UNTESTABLE",
            "reason": "The supplied validator can validate an exact C1 fixture, but no current C1 v1 projection writer is executable in the supplied surface.",
        },
        {
            "gate": 2,
            "name": "f001 needs_recheck/evidence_gone and consumer exclusion",
            "contract_or_validator_check": fact_r2["status"] == "needs_recheck"
            and fact_r2["recheck"]["reason"] == "evidence_gone"
            and not any(consumer_results.values())
            and formal_cases["CR-17"] == "NEEDS_RECHECK_EVIDENCE_GONE"
            and formal_cases["CR-24"] == "ALL_CURRENT_TRUTH_CONSUMERS_EXCLUDE",
            "runtime_execution": "NOT_IMPLEMENTED",
            "verdict": "FORMAL_VALIDATOR_PASS__PRODUCT_RUNTIME_NOT_IMPLEMENTED",
            "reason": "Formal migration/filter functions pass; C4 v1 revision-aware product migration is explicitly pending.",
        },
        {
            "gate": 3,
            "name": "basis pin needs_recheck and active RE stale",
            "contract_or_validator_check": contract_anchors[
                "basis_pin_and_re_stale"
            ]
            and formal_cases["CR-40"] == "RE_STALE_NO_ACTUAL_SUPPORT",
            "runtime_execution": "NOT_IMPLEMENTED",
            "verdict": "CONTRACT_AND_FIXTURE_ONLY__R07_RUNTIME_NOT_IMPLEMENTED",
            "reason": "The current formal validator mutates only a local edge fixture and has no planstore r07 writer or basis-pin transition runtime.",
        },
        {
            "gate": 4,
            "name": "actual support becomes unsupported",
            "contract_or_validator_check": contract_anchors[
                "actual_unsupported_when_not_current"
            ]
            and formal_cases["CR-40"] == "RE_STALE_NO_ACTUAL_SUPPORT",
            "runtime_execution": "NOT_IMPLEMENTED",
            "verdict": "CONTRACT_AND_FIXTURE_ONLY__R07_RUNTIME_NOT_IMPLEMENTED",
            "reason": "The no-support rule is frozen, but no current r07 derived-actual runtime is available here.",
        },
        {
            "gate": 5,
            "name": "C6 r1 report is derived STALE by current reader",
            "contract_or_validator_check": contract_anchors[
                "c6_reader_derives_stale"
            ]
            and formal_cases["CR-23"] == "STALE_NO_AUTOMATIC_RERUN",
            "runtime_execution": "UNTESTABLE",
            "verdict": "FORMAL_PREDICATE_PASS__CURRENT_READER_UNTESTABLE",
            "reason": "The validator compares refs but does not expose the C6 current reader that overrides an input self-report.",
        },
        {
            "gate": 6,
            "name": "r1 admission is rejected before any write",
            "contract_or_validator_check": stale_action_predicate
            and contract_anchors["admission_rejects_before_writes"],
            "runtime_execution": "NOT_IMPLEMENTED",
            "verdict": "CONTRACT_PREDICATE_PASS__V2_RUNTIME_NOT_IMPLEMENTED",
            "reason": "The stale mismatch is deterministic, while the contract explicitly says the current reconcile runtime remains v1.",
        },
        {
            "gate": 7,
            "name": "revision commit and admission share one lock and reread current",
            "contract_or_validator_check": contract_anchors[
                "shared_lock_and_atomic_group"
            ],
            "runtime_execution": "NOT_IMPLEMENTED",
            "verdict": "CONTRACT_DEFINED__COORDINATOR_NOT_IMPLEMENTED",
            "reason": "No executable cross-owner revision commit coordinator exists in the supplied runtime surface.",
        },
        {
            "gate": 8,
            "name": "operation replay idempotency and payload conflict",
            "contract_or_validator_check": contract_anchors[
                "idempotency_and_conflict"
            ]
            and formal_cases["CR-12"] == "REPLAYED_ORIGINAL_RECEIPT"
            and formal_cases["CR-13"] == "OPERATION_ID_PAYLOAD_CONFLICT",
            "runtime_execution": "UNTESTABLE",
            "verdict": "FORMAL_VALIDATOR_PASS__CROSS_OWNER_RUNTIME_UNTESTABLE",
            "reason": "C11 fixture semantics pass, but the combined revision/admission transaction path is absent.",
        },
        {
            "gate": 9,
            "name": "faults recover only all-before or all-after",
            "contract_or_validator_check": formal_cases["CR-29"]
            == "ALL_BEFORE_OR_ALL_AFTER"
            and formal_cases["CR-30"] == "NEEDS_MANUAL_RECOVERY"
            and formal_cases["CR-41"] == "RECOVERED_ALL_BEFORE",
            "runtime_execution": "UNTESTABLE",
            "verdict": "FORMAL_VALIDATOR_PASS__TRANSACTION_RUNTIME_UNTESTABLE",
            "reason": "The formal SHA classifier passes; there is no executable multi-owner transaction to fault-inject.",
        },
        {
            "gate": 10,
            "name": "runtime absence is not reported as PASS",
            "contract_or_validator_check": all(explicit_runtime_gaps.values()),
            "runtime_execution": "RUNTIME_GAP_CONFIRMED",
            "verdict": "PASS_GAP_DETECTION",
            "reason": "Formal contracts explicitly distinguish frozen v1/r07/v2 semantics from current product implementations.",
        },
    ]

    fixture = {
        "identity": "D_C11_R2_STALE_PROPAGATION_ONE_SCENARIO_FIXTURE_R01",
        "chapter_id": "c01",
        "r1_text": old_text,
        "r2_text": new_text,
        "removed_quote": quote,
        "fact_id": "f001",
        "ledger_r1": r1,
        "ledger_r2": r2,
        "c1_r2_contract_fixture": c1_fixture,
        "fact_r1": fact_r1,
        "fact_after_formal_migration": fact_r2,
        "old_admission_action_minimum": old_admission_action,
        "fixture_identity_sha256": "",
        "warning": "Contract fixture only; not a product state or author truth write.",
    }
    fixture["fixture_identity_sha256"] = canonical_sha(
        {key: value for key, value in fixture.items() if key != "fixture_identity_sha256"}
    )

    after = {str(path): sha256_file(path) for path in INPUTS}
    changed = sorted(path for path in before if before[path] != after[path])
    cache_hits = sorted(
        str(path)
        for path in ROOT.rglob("*")
        if path.name in {"__pycache__", ".pytest_cache"} or path.suffix == ".pyc"
    )
    all_formal_checks = all(gate["contract_or_validator_check"] for gate in gates)
    runtime_gap_count = sum(
        gate["runtime_execution"] in {"NOT_IMPLEMENTED", "UNTESTABLE", "RUNTIME_GAP_CONFIRMED"}
        for gate in gates
    )
    status = (
        "RUNTIME_OR_CONTRACT_GAP_FOUND"
        if not changed and not cache_hits and all_formal_checks and runtime_gap_count
        else "CZ_DECISION_REQUIRED"
    )

    manifest = {
        "identity": "D_C11_R2_STALE_PROPAGATION_INPUT_MANIFEST_R01",
        "material_status": "STABLE" if not changed else "MATERIAL_CHANGED",
        "inputs": [
            {
                "path": path,
                "before_sha256": before[path],
                "after_sha256": after[path],
                "stable": before[path] == after[path],
            }
            for path in sorted(before)
        ],
        "changed_during_probe": changed,
    }
    inventory = {
        "identity": "D_C11_R2_STALE_PROPAGATION_RUNTIME_INVENTORY_R01",
        "supplied_executable_surface": [
            "novel-mvp/contracts/validate_c11_chapter_revision_ledger.py"
        ],
        "formal_validator_cases": formal_cases,
        "explicit_runtime_gaps": explicit_runtime_gaps,
        "contract_anchors": contract_anchors,
        "product_runtime_chain_executed_end_to_end": False,
    }
    ledger = {
        "identity": "D_C11_R2_STALE_PROPAGATION_GATE_LEDGER_R01",
        "task_id": "D-C11-R2-STALE-PROPAGATION-ONE-SCENARIO-01",
        "status": status,
        "verdict": status,
        "gates": gates,
        "statistics": {
            "gates_total": len(gates),
            "contract_or_validator_checks_passed": sum(
                gate["contract_or_validator_check"] for gate in gates
            ),
            "product_runtime_gates_passed": 0,
            "runtime_gap_gates": runtime_gap_count,
            "new_semantic_wrong_success": 0,
            "input_drift": len(changed),
            "cache_hits": len(cache_hits),
            "api_calls": 0,
            "model_calls": 0,
            "automatic_retries": 0,
            "formal_writes": 0,
        },
        "scope": "ONE_SCENARIO_ONLY",
        "product_promotion": False,
    }
    no_touch = {
        "identity": "D_C11_R2_STALE_PROPAGATION_NO_TOUCH_R01",
        "designated_inputs_unchanged": not changed,
        "changed_inputs": changed,
        "cache_hits": cache_hits,
        "unauthorized_write_path": 0,
        "formal_writes": 0,
        "product_writes": 0,
        "r13_writes": 0,
        "gold_reads_or_writes": 0,
        "novel_reads": 0,
        "notion_operations": 0,
        "git_operations": 0,
        "api_calls": 0,
        "model_calls": 0,
        "automatic_retries": 0,
    }

    write_json(RESULTS / "scenario_fixture.json", fixture)
    write_json(RESULTS / "input_manifest.json", manifest)
    write_json(RESULTS / "runtime_capability_inventory.json", inventory)
    write_json(RESULTS / "gate_ledger.json", ledger)
    write_json(RESULTS / "no_touch_receipt.json", no_touch)
    write_json(
        RESULTS / "probe_result.json",
        {
            "task_id": ledger["task_id"],
            "status": status,
            "verdict": status,
            "gate_ledger": "results/gate_ledger.json",
            "fixture": "results/scenario_fixture.json",
            "runtime_inventory": "results/runtime_capability_inventory.json",
            "input_manifest": "results/input_manifest.json",
            "no_touch_receipt": "results/no_touch_receipt.json",
        },
    )

    print(
        f"{ledger['task_id']}: status={status} "
        f"formal_checks={ledger['statistics']['contract_or_validator_checks_passed']}/10 "
        "product_runtime_pass=0/10 runtime_gap_gates=10 "
        f"input_drift={len(changed)} cache={len(cache_hits)} "
        "API=0 models=0 retries=0 formal_writes=0"
    )
    return 0 if status == "RUNTIME_OR_CONTRACT_GAP_FOUND" else 1


if __name__ == "__main__":
    raise SystemExit(main())
