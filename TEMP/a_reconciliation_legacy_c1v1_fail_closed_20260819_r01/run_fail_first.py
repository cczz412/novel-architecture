from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
TASK_ROOT = Path(__file__).resolve().parent
FORMAL = REPO / "novel-mvp" / "mvp" / "reconcile.py"
TEST_MODULE = REPO / "tests" / "test_novel_mvp_reconciliation_facts_admission.py"


def _load_test_helpers():
    spec = importlib.util.spec_from_file_location("reconciliation_fixture_helpers", TEST_MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError("TEST_HELPERS_UNLOADABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _promote_current_c1_to_v1(helpers, root: Path) -> dict:
    chapters = helpers._read_json(root / "chapters.json")
    chapter = chapters[0]
    text_sha = hashlib.sha256(chapter["text"].encode("utf-8")).hexdigest()
    chapter.update(
        contract="C1_CHAPTER_DOC",
        version="v1",
        chapter_revision_ref={
            "chapter_id": chapter["id"],
            "revision_no": 1,
            "revision_text_sha256": text_sha,
        },
    )
    helpers._write_json(root / "chapters.json", chapters)
    return chapter


def _changed(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )


def main() -> int:
    helpers = _load_test_helpers()
    cases_root = TASK_ROOT / "fail_first_cases"
    if cases_root.exists():
        shutil.rmtree(cases_root)
    cases_root.mkdir(parents=True)
    formal_before = _sha(FORMAL)
    results = []

    observe_root = cases_root / "FF-01_observe_on_c1_v1"
    helpers._init(observe_root)
    _promote_current_c1_to_v1(helpers, observe_root)
    observe_candidate = helpers._candidate(observe_root, "op-ff01-observe-c1v1")
    before = _snapshot(observe_root)
    receipt = helpers.reconcile.record_reconciliation_candidate(
        observe_root,
        candidate=observe_candidate,
        timestamp=helpers.NOW,
    )
    after = _snapshot(observe_root)
    edges = helpers._read_json(observe_root / "plan.json")["reconciliation_edges"]
    wrong_success = receipt["status"] == "COMMITTED" and bool(edges) and all(
        "chapter_revision_ref" not in edge for edge in edges
    )
    results.append(
        {
            "case_id": "FF-01",
            "name": "legacy_observe_creates_r06_re_on_c1_v1",
            "wrong_success": wrong_success,
            "formal_error": None,
            "before_files": before,
            "after_files": after,
            "changed_files": _changed(before, after),
            "edge_count": len(edges),
            "edges_missing_chapter_revision_ref": sum(
                "chapter_revision_ref" not in edge for edge in edges
            ),
        }
    )

    admission_root = cases_root / "FF-02_admission_on_c1_v1"
    helpers._init(admission_root)
    _promote_current_c1_to_v1(helpers, admission_root)
    admission_candidate = helpers._candidate(admission_root, "op-ff02-observe-c1v1")
    helpers.reconcile.record_reconciliation_candidate(
        admission_root,
        candidate=admission_candidate,
        timestamp=helpers.NOW,
    )
    action = helpers._admission_action(
        admission_root,
        admission_candidate,
        "op-ff02-admit-c1v1",
    )
    before = _snapshot(admission_root)
    receipt = helpers.reconcile.admit_reconciled_facts(
        admission_root,
        action=action,
        candidate=admission_candidate,
        timestamp=helpers.NOW,
    )
    after = _snapshot(admission_root)
    facts = helpers._read_json(admission_root / "facts.json")
    wrong_success = receipt["status"] == "COMMITTED" and receipt["facts_writes"] > 0
    results.append(
        {
            "case_id": "FF-02",
            "name": "legacy_admission_writes_facts_on_c1_v1",
            "wrong_success": wrong_success,
            "formal_error": None,
            "before_files": before,
            "after_files": after,
            "changed_files": _changed(before, after),
            "facts_writes": receipt["facts_writes"],
            "facts_count_after": len(facts),
        }
    )

    reader_root = cases_root / "FF-03_reader_sha_only_support_on_c1_v1"
    helpers._init(reader_root)
    _promote_current_c1_to_v1(helpers, reader_root)
    reader_candidate = helpers._candidate(reader_root, "op-ff03-observe-c1v1")
    helpers.reconcile.record_reconciliation_candidate(
        reader_root,
        candidate=reader_candidate,
        timestamp=helpers.NOW,
    )
    reader_action = helpers._admission_action(
        reader_root,
        reader_candidate,
        "op-ff03-admit-c1v1",
    )
    helpers.reconcile.admit_reconciled_facts(
        reader_root,
        action=reader_action,
        candidate=reader_candidate,
        timestamp=helpers.NOW,
    )
    plan = helpers._read_json(reader_root / "plan.json")
    before = _snapshot(reader_root)
    states = helpers.reconcile.reconciliation_edge_states(reader_root)
    after = _snapshot(reader_root)
    missing_ref = all("chapter_revision_ref" not in edge for edge in plan["reconciliation_edges"])
    actual_refs = [state["edge_ref"] for state in states if state["actual_support"]]
    wrong_success = missing_ref and bool(actual_refs)
    results.append(
        {
            "case_id": "FF-03",
            "name": "r06_reader_sha_only_actual_support_on_c1_v1",
            "wrong_success": wrong_success,
            "formal_error": None,
            "before_files": before,
            "after_files": after,
            "changed_files": _changed(before, after),
            "actual_support_refs": actual_refs,
            "reader_writes": len(_changed(before, after)),
        }
    )

    output = {
        "task_id": "A-RECONCILIATION-LEGACY-C1V1-FAIL-CLOSED-01",
        "phase": "FAIL_FIRST",
        "formal_sha_before": formal_before,
        "formal_sha_after": _sha(FORMAL),
        "formal_write_count": 0,
        "all_three_wrong_success_proven": all(item["wrong_success"] for item in results),
        "results": results,
        "api_calls": 0,
        "model_calls": 0,
        "automatic_retries": 0,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["all_three_wrong_success_proven"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
