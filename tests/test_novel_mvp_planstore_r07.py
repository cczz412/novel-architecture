from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
PLANSTORE_SCRIPT = PRODUCT_ROOT / "mvp" / "planstore.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import planstore
finally:
    sys.path.pop(0)


NOW = "2026-08-19 12:00:00"
CHAPTER_TEXT = "林乔把钥匙锁进木匣。"


def _canonical_bytes(value) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value))


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _revision_ref(revision_no: int = 1, text: str = CHAPTER_TEXT) -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": revision_no,
        "revision_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def _plan() -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-0001", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "goal": "让钥匙去向成为本章推进点",
                "summary": "作者计划让林乔收起钥匙",
                "entry_state": "钥匙仍在桌上",
                "storyline_refs": [],
                "scene_refs": ["SCN-0001"],
                "exit_condition": "钥匙被妥善收起",
                "exit_hook": "谁会来找钥匙",
                "must_not": ["不得把计划冒充事实"],
                "risks": [],
                "target_length": 1200,
                "slot_status": "handed_over",
                "handover_parts": [],
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 1,
            }
        ],
        "scenes": [
            {
                "id": "SCN-0001",
                "slot_ref": "S-0001",
                "goal": "处理钥匙",
                "summary": "林乔收起钥匙",
                "pe_refs": ["PE-0001"],
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 1,
            }
        ],
        "events": [
            {
                "id": "PE-0001",
                "scene_ref": "SCN-0001",
                "text": "林乔收起钥匙",
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 1,
            }
        ],
        "storylines": [],
        "hooks": [],
        "widgets": [],
        "pins": [],
        "must_carries": [],
        "option_records": [],
        "slot_mappings": [
            {
                "id": "MAP-0001",
                "slot_ref": "S-0001",
                "chapter_id": "c01",
                "expected_chapter_no": 1,
                "mapping_kind": "as_written",
                "reason": "当前章承接该规划槽",
                "decided_by": "author",
                "mapping_status": "active",
                "superseded_by": None,
            }
        ],
        "reconciliation_edges": [],
        "stop_points": {},
        "id_counters": {"MAP": 1, "RE": 0},
    }


def _planning_record() -> dict:
    return {
        "planned_ref": "PE-0001",
        "planned_rev": 1,
        "chapter_ref": "c01",
        "slot_ref": "S-0001",
        "source_item_key": "author-plan-check-01",
        "outcome": "exact",
        "coverage": "full",
        "variant_note": None,
        "author_decision": {
            "action": "accept_as_is",
            "decided_at": NOW,
            "note": "作者确认按当前正文版本保存这次规划对照",
        },
        "decided_by": "author",
    }


def _legacy_edge() -> dict:
    return {
        "id": "RE-0001",
        "planned_ref": "PE-0001",
        "planned_rev": 1,
        "actual_fact_refs": [],
        "actual_fact_basis_sha256": None,
        "chapter_ref": "c01",
        "slot_ref": "S-0001",
        "chapter_text_sha256": _revision_ref()["revision_text_sha256"],
        "source_run_id": "legacy-r06-observe-01",
        "source_item_key": "legacy-item-01",
        "outcome": "exact",
        "coverage": "full",
        "variant_note": None,
        "author_decision": None,
        "basis_commit_seq": 0,
        "decided_by": "auto",
        "edge_status": "active",
        "superseded_by": None,
        "rev": 1,
    }


def _init(root: Path, *, plan: dict | None = None) -> None:
    root.mkdir(parents=True)
    _write_json(root / "plan.json", _plan() if plan is None else plan)
    _write_json(
        root / "chapters.json",
        [
            {
                "contract": "C1_CHAPTER_DOC",
                "version": "v1",
                "id": "c01",
                "title": "合成章",
                "kind": "draft",
                "text": CHAPTER_TEXT,
                "added_at": NOW,
                "chapter_revision_ref": _revision_ref(),
            }
        ],
    )
    _write_json(root / "facts.json", [])
    (root / "plan_history.jsonl").touch()
    (root / "commit_log.jsonl").touch()


def _write(root: Path, *, operation_id: str = "op-plan-r07-01", **kwargs):
    return planstore.write_revision_aware_planning_record(
        root,
        operation_id=operation_id,
        planning_record=_planning_record(),
        chapter_revision_ref=_revision_ref(),
        current_chapter_revision_ref=_revision_ref(),
        timestamp=NOW,
        **kwargs,
    )


def test_user_visible_demo_writes_and_reads_current_revision_planning_record(
    tmp_path: Path,
) -> None:
    root = tmp_path / "book"
    _init(root)
    facts_sha = _sha(root / "facts.json")

    receipt = _write(root)
    view = planstore.read_planning_records(root)

    assert receipt == {
        "operation_id": "op-plan-r07-01",
        "status": "COMMITTED",
        "record_version": "r07",
        "record_ref": "RE-0001",
        "chapter_revision_ref": _revision_ref(),
        "story_commit_seq": 1,
        "facts_writes": 0,
        "new_f_ids": 0,
        "actual_changes": 0,
        "replayed": False,
    }
    assert view["record_identity"] == "plan-v2-r07"
    assert view["revision_aware"] is True
    assert view["read_only_compatibility"] is False
    assert view["records"][0]["chapter_revision_ref"] == _revision_ref()
    assert view["records"][0]["author_decision"]["action"] == "accept_as_is"
    assert _sha(root / "facts.json") == facts_sha
    assert planstore.verify_storage(root)["status"] == "PASS"


def test_r07_write_recovers_complete_generic_transaction(tmp_path: Path) -> None:
    root = tmp_path / "book"
    _init(root)

    with pytest.raises(planstore.InjectedCrash, match="after_history"):
        _write(root, fault_at="after_history")

    with pytest.raises(planstore.PlanstoreError, match="STORAGE_RECOVERY_REQUIRED"):
        planstore.read_planning_records(root)
    assert planstore.recover(root, timestamp="2026-08-19 12:01:00") == [
        {"operation_id": "op-plan-r07-01", "result": "COMMITTED"}
    ]
    assert planstore.read_planning_records(root)["records"][0]["id"] == "RE-0001"
    assert planstore.operation_status(root, "op-plan-r07-01")["state"] == "COMMITTED"
    assert planstore.verify_storage(root)["status"] == "PASS"


def test_stale_explicit_chapter_revision_ref_is_rejected_before_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "book"
    _init(root)
    before = {
        path.name: _sha(path)
        for path in (root / "plan.json", root / "plan_history.jsonl", root / "commit_log.jsonl")
    }

    with pytest.raises(planstore.PlanstoreError, match="STALE_CHAPTER_REVISION_REF"):
        planstore.write_revision_aware_planning_record(
            root,
            operation_id="op-stale-r07",
            planning_record=_planning_record(),
            chapter_revision_ref=_revision_ref(),
            current_chapter_revision_ref=_revision_ref(2, "林乔把钥匙交给周宁。"),
            timestamp=NOW,
        )

    after = {
        path.name: _sha(path)
        for path in (root / "plan.json", root / "plan_history.jsonl", root / "commit_log.jsonl")
    }
    assert after == before
    assert planstore.operation_status(root, "op-stale-r07")["state"] == "NOT_HAPPENED"


def test_r07_replay_is_idempotent_and_equivalent_new_action_is_no_change(
    tmp_path: Path,
) -> None:
    root = tmp_path / "book"
    _init(root)

    first = _write(root)
    replay = _write(root)
    no_change = _write(root, operation_id="op-plan-r07-no-change")

    assert first["record_ref"] == replay["record_ref"] == no_change["record_ref"]
    assert replay["replayed"] is True
    assert no_change["status"] == "NO_CHANGE"
    assert no_change["story_commit_seq"] == 1
    assert len(_read_json(root / "plan.json")["reconciliation_edges"]) == 1
    assert [row["op"] for row in _read_jsonl(root / "commit_log.jsonl")] == [
        "op-plan-r07-01",
        "op-plan-r07-01",
    ]
    assert planstore.operation_status(root, "op-plan-r07-no-change")["state"] == "NOT_HAPPENED"


def test_legacy_r06_plan_is_readable_but_cannot_masquerade_or_accept_r07_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "book"
    legacy_plan = _plan()
    legacy_plan["reconciliation_edges"] = [_legacy_edge()]
    legacy_plan["id_counters"]["RE"] = 1
    _init(root, plan=legacy_plan)

    view = planstore.read_planning_records(root)

    assert view["record_identity"] == "plan-v2-r06-legacy-read-only"
    assert view["revision_aware"] is False
    assert view["read_only_compatibility"] is True
    assert "chapter_revision_ref" not in view["records"][0]
    with pytest.raises(planstore.PlanstoreError, match="LEGACY_R06_RE_MIGRATION_REQUIRED:RE-0001"):
        _write(root, operation_id="op-r07-over-legacy")


def test_cli_user_planning_action_uses_unmodified_synthetic_input(tmp_path: Path) -> None:
    root = tmp_path / "book"
    _init(root)
    record_path = root / "user-planning-record.json"
    revision_path = root / "chapter-revision-ref.json"
    _write_json(record_path, _planning_record())
    _write_json(revision_path, _revision_ref())
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            str(PLANSTORE_SCRIPT),
            "planning-write-r07",
            str(root),
            "--operation-id",
            "op-cli-user-plan-r07",
            "--record",
            str(record_path),
            "--chapter-revision-ref",
            str(revision_path),
            "--current-chapter-revision-ref",
            str(revision_path),
            "--timestamp",
            NOW,
        ],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert json.loads(completed.stdout)["record_ref"] == "RE-0001"
    assert _read_json(root / "plan.json")["reconciliation_edges"][0][
        "chapter_revision_ref"
    ] == _revision_ref()
