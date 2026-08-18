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


NOW = "2026-08-18 20:00:00"


def _canonical_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value))


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_bytes(b"".join(_canonical_bytes(row) for row in rows))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
                "goal": "原计划目标",
                "summary": "原计划梗概",
                "entry_state": "原计划入口",
                "storyline_refs": [],
                "scene_refs": ["SCN-0001"],
                "exit_condition": "原计划出口",
                "exit_hook": "原计划钩子",
                "must_not": ["不得把计划冒充事实"],
                "risks": [],
                "target_length": 1200,
                "outline_checkpoint": {
                    "outline_rev": 2,
                    "source_slot_ref": "S-0001",
                    "source_commit_seq": 7,
                },
                "slot_status": "planned",
                "handover_parts": [],
                "truth_bearing": "primary",
                "updated_at": "2026-08-18 19:00:00",
                "rev": 2,
            }
        ],
        "scenes": [
            {
                "id": "SCN-0001",
                "slot_ref": "S-0001",
                "goal": "原场目标",
                "summary": "原场梗概",
                "pe_refs": ["PE-0001"],
                "truth_bearing": "primary",
                "updated_at": "2026-08-18 19:00:00",
                "rev": 1,
            }
        ],
        "events": [
            {
                "id": "PE-0001",
                "scene_ref": "SCN-0001",
                "text": "原计划事件",
                "truth_bearing": "primary",
                "updated_at": "2026-08-18 19:00:00",
                "rev": 1,
            }
        ],
        "storylines": [],
        "hooks": [],
        "widgets": [],
        "pins": [],
        "must_carries": [],
        "option_records": [],
        "slot_mappings": [],
        "reconciliation_edges": [],
        "stop_points": {},
        "id_counters": {"MAP": 0, "RE": 0},
    }


def _work(text: str = "作者当前工作稿。") -> dict:
    return {
        "contract": "WRITING_DESK_WORK_DRAFT",
        "version": "v1",
        "work_ref": "S-0001@work",
        "slot_ref": "S-0001",
        "source_outline_ref": "S-0001@outline-r2",
        "work_rev": 2,
        "state": "working",
        "entry_mode": "edited",
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "last_operation_id": "op-work-r2",
    }


def _action(operation_id: str = "op-handover-01") -> dict:
    return {
        "contract": "WORK_DRAFT_HANDOVER_ACTION",
        "version": "v1",
        "operation_id": operation_id,
        "actor": "author",
        "intent": "adopt_as_manuscript",
        "work_ref": "S-0001@work",
        "work_rev": 2,
        "slot_ref": "S-0001",
        "source_outline_ref": "S-0001@outline-r2",
        "target_contract": "C1_CHAPTER_DOC",
        "target_planstore_result": "handover_parts",
    }


def _init(root: Path, *, plan: dict | None = None) -> None:
    root.mkdir(parents=True)
    _write_json(root / "plan.json", _plan() if plan is None else plan)
    _write_json(root / "chapters.json", [])
    _write_json(root / "facts.json", {"sentinel": "must-not-change", "facts": []})
    (root / "plan_history.jsonl").touch()
    (root / "commit_log.jsonl").touch()


def _invoke_cli(root: Path, command: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(PLANSTORE_SCRIPT), command, str(root), *args],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _input_files(root: Path, operation_id: str = "op-handover-01", *, text: str = "作者当前工作稿。") -> tuple[Path, Path]:
    action_path = root / f"{operation_id}.action.json"
    work_path = root / f"{operation_id}.work.json"
    _write_json(action_path, _action(operation_id))
    _write_json(work_path, _work(text))
    return action_path, work_path


def _handover_cli_args(action_path: Path, work_path: Path, *, title: str = "样章") -> list[str]:
    return [
        "--action",
        str(action_path),
        "--work",
        str(work_path),
        "--title",
        title,
        "--timestamp",
        NOW,
    ]


def _semantic_plan_text(plan: dict) -> dict:
    slot = plan["slots"][0]
    scene = plan["scenes"][0]
    event = plan["events"][0]
    return {
        "slot": [slot["goal"], slot["summary"], slot["entry_state"], slot["exit_condition"], slot["exit_hook"]],
        "scene": [scene["goal"], scene["summary"]],
        "event": event["text"],
    }


def test_handover_commits_c1_plan_mapping_history_and_blobs_atomically(tmp_path: Path) -> None:
    root = tmp_path / "book"
    _init(root)
    before_plan_text = _semantic_plan_text(_read_json(root / "plan.json"))
    facts_sha = _sha(root / "facts.json")

    receipt = planstore.accept_work_draft_handover(
        root,
        action=_action(),
        current_work=_work(),
        title="样章",
        timestamp=NOW,
    )

    assert receipt["status"] == "COMMITTED"
    assert receipt["mapping"]["id"] == "MAP-0001"
    assert receipt["mapping"]["mapping_status"] == "active"
    chapters = _read_json(root / "chapters.json")
    plan = _read_json(root / "plan.json")
    assert chapters == [
        {
            "id": "c01",
            "title": "样章",
            "kind": "draft",
            "text": "作者当前工作稿。",
            "added_at": NOW,
        }
    ]
    assert plan["slots"][0]["slot_status"] == "handed_over"
    assert len(plan["slots"][0]["handover_parts"]) == 1
    assert plan["slot_mappings"] == [receipt["mapping"]]
    assert _semantic_plan_text(plan) == before_plan_text
    assert _sha(root / "facts.json") == facts_sha

    phases = [row["phase"] for row in _read_jsonl(root / "commit_log.jsonl")]
    history = _read_jsonl(root / "plan_history.jsonl")
    assert phases == ["prepare", "commit"]
    assert {row["object_id"] for row in history} == {"S-0001", "SCN-0001", "PE-0001"}
    for row in history:
        digest = row["content_hash"].removeprefix("sha256:")
        blob = root / "blobs" / digest[:2] / f"{digest}.json"
        assert blob.exists() and _sha(blob) == digest
    assert planstore.verify_storage(root)["status"] == "PASS"


@pytest.mark.parametrize(
    ("mutate_action", "mutate_work", "title", "reason"),
    [
        (lambda value: value.pop("intent"), lambda value: None, "样章", "HANDOVER_ACTION_SCHEMA_MISMATCH"),
        (lambda value: value.update(work_rev=1), lambda value: None, "样章", "STALE_WORK_REVISION"),
        (lambda value: value.update(slot_ref="S-9999"), lambda value: None, "样章", "SLOT_REF_MISMATCH"),
        (lambda value: value.update(actual=True), lambda value: None, "样章", "HANDOVER_TRUTH_MUTATION_FORBIDDEN"),
        (lambda value: None, lambda value: value.update(text_sha256="bad"), "样章", "WORK_TEXT_SHA_MISMATCH"),
        (lambda value: None, lambda value: None, "", "C1_TITLE_INVALID"),
    ],
)
def test_write_guards_reject_before_prepare(
    tmp_path: Path, mutate_action, mutate_work, title: str, reason: str
) -> None:
    root = tmp_path / reason
    _init(root)
    action = _action()
    work = _work()
    mutate_action(action)
    mutate_work(work)
    with pytest.raises(planstore.PlanstoreError, match=reason):
        planstore.accept_work_draft_handover(
            root,
            action=action,
            current_work=work,
            title=title,
            timestamp=NOW,
        )
    assert _read_jsonl(root / "commit_log.jsonl") == []
    assert _read_json(root / "chapters.json") == []


def test_bad_existing_map_rejected_before_prepare(tmp_path: Path) -> None:
    root = tmp_path / "bad-map"
    bad = _plan()
    bad["slot_mappings"] = [
        {
            "id": "MAP-0001",
            "slot_ref": "S-0001",
            "chapter_id": "c99",
            "expected_chapter_no": 1,
            "mapping_kind": "as_written",
            "reason": "",
            "decided_by": "author",
            "mapping_status": "superseded",
            "superseded_by": "MAP-9999",
        }
    ]
    bad["id_counters"]["MAP"] = 1
    _init(root, plan=bad)
    with pytest.raises(planstore.PlanstoreError, match="SUPERSEDED_BY_INVALID"):
        planstore.accept_work_draft_handover(
            root,
            action=_action(),
            current_work=_work(),
            title="样章",
            timestamp=NOW,
        )
    assert _read_jsonl(root / "commit_log.jsonl") == []


def test_existing_mapping_with_missing_c1_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "bad-map-chapter"
    bad = _plan()
    bad["slot_mappings"] = [
        {
            "id": "MAP-0001",
            "slot_ref": "S-0001",
            "chapter_id": "c99",
            "expected_chapter_no": 1,
            "mapping_kind": "as_written",
            "reason": "",
            "decided_by": "author",
            "mapping_status": "active",
            "superseded_by": None,
        }
    ]
    bad["id_counters"]["MAP"] = 1
    _init(root, plan=bad)
    with pytest.raises(planstore.PlanstoreError, match="MAPPING_CHAPTER_REF_NOT_FOUND"):
        planstore.accept_work_draft_handover(
            root,
            action=_action(),
            current_work=_work(),
            title="样章",
            timestamp=NOW,
        )
    assert _read_jsonl(root / "commit_log.jsonl") == []


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"mapping_kind": "invented"}, "MAPPING_KIND_INVALID"),
        ({"mapping_kind": "inserted"}, "MAPPING_SLOT_REF_MUST_BE_NULL"),
        ({"slot_ref": "S-9999"}, "MAPPING_SLOT_REF_INVALID"),
        ({"chapter_id": "chapter-one"}, "MAPPING_CHAPTER_ID_INVALID"),
        ({"expected_chapter_no": 0}, "MAPPING_EXPECTED_CHAPTER_NO_INVALID"),
        ({"reason": None}, "MAPPING_REASON_INVALID"),
        ({"decided_by": "model"}, "MAPPING_DECIDED_BY_INVALID"),
    ],
)
def test_existing_mapping_contract_shape_is_enforced_before_prepare(
    tmp_path: Path, change: dict, reason: str
) -> None:
    root = tmp_path / reason
    bad = _plan()
    mapping = {
        "id": "MAP-0001",
        "slot_ref": "S-0001",
        "chapter_id": None,
        "expected_chapter_no": 1,
        "mapping_kind": "as_written",
        "reason": "预调整",
        "decided_by": "author",
        "mapping_status": "active",
        "superseded_by": None,
    }
    mapping.update(change)
    bad["slot_mappings"] = [mapping]
    bad["id_counters"]["MAP"] = 1
    _init(root, plan=bad)
    with pytest.raises(planstore.PlanstoreError, match=reason):
        planstore.accept_work_draft_handover(
            root,
            action=_action(),
            current_work=_work(),
            title="样章",
            timestamp=NOW,
        )
    assert _read_jsonl(root / "commit_log.jsonl") == []


@pytest.mark.parametrize(
    ("fault_at", "expected_recovery"),
    [
        ("after_prepare", "ROLLED_BACK"),
        ("after_chapters", "ROLLED_BACK"),
        ("after_blob", "ROLLED_BACK"),
        ("during_history", "ROLLED_BACK"),
        ("after_history", "ROLLED_BACK"),
        ("after_plan", "COMMITTED"),
        ("before_commit", "COMMITTED"),
        ("after_commit", "COMMITTED"),
    ],
)
def test_fault_injection_recovers_in_new_process(
    tmp_path: Path, fault_at: str, expected_recovery: str
) -> None:
    root = tmp_path / fault_at
    _init(root)
    facts_sha = _sha(root / "facts.json")
    before_plan_sha = _sha(root / "plan.json")
    action_path, work_path = _input_files(root)

    crashed = _invoke_cli(
        root,
        "handover",
        *_handover_cli_args(action_path, work_path),
        "--fault-at",
        fault_at,
    )
    assert crashed.returncode == 75, crashed.stdout + crashed.stderr
    pending = _invoke_cli(root, "status", "op-handover-01")
    assert json.loads(pending.stdout)["state"] in {"PENDING_RECOVERY", "COMMITTED"}

    recovered = _invoke_cli(root, "recover", "--timestamp", "2026-08-18 20:01:00")
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    state = json.loads(_invoke_cli(root, "status", "op-handover-01").stdout)
    assert _sha(root / "facts.json") == facts_sha
    if expected_recovery == "ROLLED_BACK":
        assert state["state"] == "NOT_HAPPENED" and state["terminal_phase"] == "rolled_back"
        assert _sha(root / "plan.json") == before_plan_sha
        assert _read_json(root / "chapters.json") == []
        assert _read_jsonl(root / "plan_history.jsonl") == []
        assert list((root / "blobs").glob("*/*.json")) == []
        assert [row["phase"] for row in _read_jsonl(root / "commit_log.jsonl")] == [
            "prepare",
            "rolled_back",
        ]
    else:
        assert state["state"] == "COMMITTED"
        assert len(_read_json(root / "chapters.json")) == 1
        assert len(_read_json(root / "plan.json")["slot_mappings"]) == 1
        assert [row["phase"] for row in _read_jsonl(root / "commit_log.jsonl")] == [
            "prepare",
            "commit",
        ]
        assert planstore.verify_storage(root)["status"] == "PASS"


def test_cross_process_replay_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "replay"
    _init(root)
    action_path, work_path = _input_files(root)
    args = _handover_cli_args(action_path, work_path)

    first = _invoke_cli(root, "handover", *args)
    replay = _invoke_cli(root, "handover", *args)
    assert first.returncode == replay.returncode == 0
    assert json.loads(first.stdout)["replayed"] is False
    assert json.loads(replay.stdout)["replayed"] is True
    assert len(_read_json(root / "chapters.json")) == 1
    assert len(_read_json(root / "plan.json")["slots"][0]["handover_parts"]) == 1
    assert len(_read_json(root / "plan.json")["slot_mappings"]) == 1
    assert [row["phase"] for row in _read_jsonl(root / "commit_log.jsonl")] == ["prepare", "commit"]


def test_concurrent_same_operation_creates_one_chapter_part_map_and_commit(tmp_path: Path) -> None:
    root = tmp_path / "concurrent-same"
    _init(root)
    action_path, work_path = _input_files(root)
    command = [
        sys.executable,
        str(PLANSTORE_SCRIPT),
        "handover",
        str(root),
        *_handover_cli_args(action_path, work_path),
    ]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    processes = [subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) for _ in range(2)]
    outputs = [process.communicate(timeout=20) for process in processes]
    assert [process.returncode for process in processes] == [0, 0], outputs
    assert len(_read_json(root / "chapters.json")) == 1
    plan = _read_json(root / "plan.json")
    assert len(plan["slots"][0]["handover_parts"]) == len(plan["slot_mappings"]) == 1
    assert [row["phase"] for row in _read_jsonl(root / "commit_log.jsonl")] == ["prepare", "commit"]


def test_concurrent_different_operations_allow_only_one_handover(tmp_path: Path) -> None:
    root = tmp_path / "concurrent-different"
    _init(root)
    files = [_input_files(root, operation_id) for operation_id in ("op-a", "op-b")]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    processes = []
    for action_path, work_path in files:
        command = [
            sys.executable,
            str(PLANSTORE_SCRIPT),
            "handover",
            str(root),
            *_handover_cli_args(action_path, work_path),
        ]
        processes.append(
            subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        )
    outputs = [process.communicate(timeout=20) for process in processes]
    assert sorted(process.returncode for process in processes) == [0, 2], outputs
    rejected = [json.loads(stdout) for process, (stdout, _) in zip(processes, outputs) if process.returncode == 2]
    assert rejected[0]["reason"] == "SLOT_ALREADY_HANDED_OVER"
    assert len(_read_json(root / "chapters.json")) == 1
    plan = _read_json(root / "plan.json")
    assert len(plan["slots"][0]["handover_parts"]) == len(plan["slot_mappings"]) == 1


def test_cross_process_same_operation_different_payload_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "conflict"
    _init(root)
    action_path, work_path = _input_files(root)
    first = _invoke_cli(root, "handover", *_handover_cli_args(action_path, work_path))
    conflict = _invoke_cli(
        root,
        "handover",
        *_handover_cli_args(action_path, work_path, title="另一标题"),
    )
    assert first.returncode == 0
    assert conflict.returncode == 2
    assert json.loads(conflict.stdout)["reason"] == "OPERATION_ID_PAYLOAD_CONFLICT"
    assert len(_read_json(root / "chapters.json")) == 1


def test_status_distinguishes_not_happened_pending_committed_and_rolled_back(tmp_path: Path) -> None:
    root = tmp_path / "states"
    _init(root)
    assert planstore.operation_status(root, "op-state")["state"] == "NOT_HAPPENED"
    with pytest.raises(planstore.InjectedCrash):
        planstore.accept_work_draft_handover(
            root,
            action=_action("op-state"),
            current_work=_work(),
            title="样章",
            timestamp=NOW,
            fault_at="after_prepare",
        )
    assert planstore.operation_status(root, "op-state")["state"] == "PENDING_RECOVERY"
    assert planstore.recover(root, timestamp="2026-08-18 20:01:00")[0]["result"] == "ROLLED_BACK"
    rolled_back = planstore.operation_status(root, "op-state")
    assert rolled_back["state"] == "NOT_HAPPENED" and rolled_back["terminal_phase"] == "rolled_back"

    receipt = planstore.accept_work_draft_handover(
        root,
        action=_action("op-state-2"),
        current_work=_work(),
        title="样章",
        timestamp=NOW,
    )
    assert receipt["status"] == "COMMITTED"
    assert planstore.operation_status(root, "op-state-2")["state"] == "COMMITTED"


def test_unknown_post_prepare_file_hash_requires_manual_recovery(tmp_path: Path) -> None:
    root = tmp_path / "manual"
    _init(root)
    with pytest.raises(planstore.InjectedCrash):
        planstore.accept_work_draft_handover(
            root,
            action=_action(),
            current_work=_work(),
            title="样章",
            timestamp=NOW,
            fault_at="after_prepare",
        )
    (root / "plan.json").write_text('{"corrupt":"unexpected"}\n', encoding="utf-8")
    assert planstore.operation_status(root, "op-handover-01")["state"] == "NEEDS_MANUAL_RECOVERY"
    with pytest.raises(planstore.PlanstoreError, match="NEEDS_MANUAL_RECOVERY.*UNRECOGNIZED_FILE_HASH"):
        planstore.recover(root, timestamp="2026-08-18 20:01:00")


def test_verify_detects_history_blob_corruption(tmp_path: Path) -> None:
    root = tmp_path / "blob-corrupt"
    _init(root)
    planstore.accept_work_draft_handover(
        root,
        action=_action(),
        current_work=_work(),
        title="样章",
        timestamp=NOW,
    )
    first = _read_jsonl(root / "plan_history.jsonl")[0]
    digest = first["content_hash"].removeprefix("sha256:")
    blob = root / "blobs" / digest[:2] / f"{digest}.json"
    blob.write_text("{}\n", encoding="utf-8")
    with pytest.raises(planstore.PlanstoreError, match="HISTORY_BLOB_MISMATCH"):
        planstore.verify_storage(root)


def test_verify_detects_final_plan_drift_from_latest_commit(tmp_path: Path) -> None:
    root = tmp_path / "plan-drift"
    _init(root)
    planstore.accept_work_draft_handover(
        root,
        action=_action(),
        current_work=_work(),
        title="样章",
        timestamp=NOW,
    )
    plan = _read_json(root / "plan.json")
    plan["slots"][0]["summary"] = "未经过 writer 的静默改写"
    _write_json(root / "plan.json", plan)
    with pytest.raises(planstore.PlanstoreError, match="FINAL_PLAN_COMMIT_HASH_MISMATCH"):
        planstore.verify_storage(root)


def test_verify_detects_history_manifest_drift(tmp_path: Path) -> None:
    root = tmp_path / "history-manifest-drift"
    _init(root)
    planstore.accept_work_draft_handover(
        root,
        action=_action(),
        current_work=_work(),
        title="样章",
        timestamp=NOW,
    )
    commit_rows = _read_jsonl(root / "commit_log.jsonl")
    history_entry = next(
        row
        for row in commit_rows[0]["files"]
        if row.get("path") == "plan_history.jsonl"
    )
    history_entry["append_sha256"] = "0" * 64
    _write_jsonl(root / "commit_log.jsonl", commit_rows)
    with pytest.raises(planstore.PlanstoreError, match="HISTORY_APPEND_MANIFEST_MISMATCH"):
        planstore.verify_storage(root)
