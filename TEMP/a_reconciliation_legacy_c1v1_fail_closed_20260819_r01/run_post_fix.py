from __future__ import annotations

import json
import shutil
from pathlib import Path

import run_fail_first as shared


TASK_ROOT = Path(__file__).resolve().parent
EXPECTED_ERROR = "LEGACY_RECONCILIATION_V1_REQUIRES_LEGACY_C1"


def _caught_error(call) -> str | None:
    try:
        call()
    except Exception as exc:  # noqa: BLE001 - harness 要保留现役入口真实错误名
        return str(exc)
    return None


def main() -> int:
    helpers = shared._load_test_helpers()
    cases_root = TASK_ROOT / "post_fix_cases"
    if cases_root.exists():
        shutil.rmtree(cases_root)
    cases_root.mkdir(parents=True)
    results = []

    observe_root = cases_root / "PF-01_observe_rejected"
    helpers._init(observe_root)
    shared._promote_current_c1_to_v1(helpers, observe_root)
    candidate = helpers._candidate(observe_root, "op-pf01-observe-c1v1")
    before = shared._snapshot(observe_root)
    error = _caught_error(
        lambda: helpers.reconcile.record_reconciliation_candidate(
            observe_root,
            candidate=candidate,
            timestamp=helpers.NOW,
        )
    )
    after = shared._snapshot(observe_root)
    results.append(
        {
            "case_id": "PF-01",
            "name": "observe_c1_v1_rejected_before_write",
            "actual": error,
            "expected": EXPECTED_ERROR,
            "zero_writes": before == after,
            "changed_files": shared._changed(before, after),
            "pass": error == EXPECTED_ERROR and before == after,
        }
    )

    admission_root = cases_root / "PF-02_admission_rejected"
    helpers._init(admission_root)
    candidate = helpers._candidate(admission_root, "op-pf02-legacy-observe")
    helpers.reconcile.record_reconciliation_candidate(
        admission_root,
        candidate=candidate,
        timestamp=helpers.NOW,
    )
    action = helpers._admission_action(admission_root, candidate, "op-pf02-admit-c1v1")
    shared._promote_current_c1_to_v1(helpers, admission_root)
    before = shared._snapshot(admission_root)
    error = _caught_error(
        lambda: helpers.reconcile.admit_reconciled_facts(
            admission_root,
            action=action,
            candidate=candidate,
            timestamp=helpers.NOW,
        )
    )
    after = shared._snapshot(admission_root)
    facts = helpers._read_json(admission_root / "facts.json")
    results.append(
        {
            "case_id": "PF-02",
            "name": "admission_c1_v1_rejected_before_write",
            "actual": error,
            "expected": EXPECTED_ERROR,
            "zero_writes": before == after,
            "changed_files": shared._changed(before, after),
            "facts_count": len(facts),
            "pass": error == EXPECTED_ERROR and before == after and not facts,
        }
    )

    reader_root = cases_root / "PF-03_reader_fail_closed"
    helpers._init(reader_root)
    candidate = helpers._candidate(reader_root, "op-pf03-legacy-observe")
    helpers.reconcile.record_reconciliation_candidate(
        reader_root,
        candidate=candidate,
        timestamp=helpers.NOW,
    )
    action = helpers._admission_action(reader_root, candidate, "op-pf03-legacy-admit")
    helpers.reconcile.admit_reconciled_facts(
        reader_root,
        action=action,
        candidate=candidate,
        timestamp=helpers.NOW,
    )
    shared._promote_current_c1_to_v1(helpers, reader_root)
    before = shared._snapshot(reader_root)
    states = helpers.reconcile.reconciliation_edge_states(reader_root)
    after = shared._snapshot(reader_root)
    all_stale = all(
        "LEGACY_RE_CHAPTER_REVISION_UNKNOWN" in state["stale_reasons"]
        for state in states
    )
    no_actual_support = not any(state["actual_support"] for state in states)
    results.append(
        {
            "case_id": "PF-03",
            "name": "r06_reader_on_c1_v1_is_legacy_stale",
            "actual": "LEGACY_RE_CHAPTER_REVISION_UNKNOWN",
            "expected": "LEGACY_RE_CHAPTER_REVISION_UNKNOWN",
            "zero_writes": before == after,
            "changed_files": shared._changed(before, after),
            "all_edges_stale_for_missing_revision_ref": all_stale,
            "actual_support_refs": [
                state["edge_ref"] for state in states if state["actual_support"]
            ],
            "pass": before == after and all_stale and no_actual_support,
        }
    )

    legacy_root = cases_root / "PF-04_legacy_c1_v0_unchanged"
    helpers._init(legacy_root)
    candidate = helpers._candidate(legacy_root, "op-pf04-legacy-observe")
    observe_receipt = helpers.reconcile.record_reconciliation_candidate(
        legacy_root,
        candidate=candidate,
        timestamp=helpers.NOW,
    )
    action = helpers._admission_action(legacy_root, candidate, "op-pf04-legacy-admit")
    admission_receipt = helpers.reconcile.admit_reconciled_facts(
        legacy_root,
        action=action,
        candidate=candidate,
        timestamp=helpers.NOW,
    )
    states = helpers.reconcile.reconciliation_edge_states(legacy_root)
    actual_support_refs = [state["edge_ref"] for state in states if state["actual_support"]]
    results.append(
        {
            "case_id": "PF-04",
            "name": "legacy_c1_v0_behavior_unchanged",
            "observe_status": observe_receipt["status"],
            "edge_count": observe_receipt["edge_count"],
            "admission_status": admission_receipt["status"],
            "facts_writes": admission_receipt["facts_writes"],
            "actual_support_refs": actual_support_refs,
            "pass": (
                observe_receipt["status"] == "COMMITTED"
                and observe_receipt["edge_count"] == 6
                and admission_receipt["status"] == "COMMITTED"
                and admission_receipt["facts_writes"] == 4
                and len(actual_support_refs) == 2
            ),
        }
    )

    output = {
        "task_id": "A-RECONCILIATION-LEGACY-C1V1-FAIL-CLOSED-01",
        "phase": "POST_FIX",
        "formal_sha": shared._sha(shared.FORMAL),
        "all_pass": all(item["pass"] for item in results),
        "results": results,
        "api_calls": 0,
        "model_calls": 0,
        "automatic_retries": 0,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["all_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
