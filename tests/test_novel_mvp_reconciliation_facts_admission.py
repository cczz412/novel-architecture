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
RECONCILE_SCRIPT = PRODUCT_ROOT / "mvp" / "reconcile.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import planstore, reconcile
finally:
    sys.path.pop(0)


NOW = "2026-08-18 22:00:00"
TEXT = (
    "林乔把铜钥匙锁进木匣。\n"
    "林乔把银钥匙交给苏晚。\n"
    "城门整夜敞开。\n"
    "黑影掠过窗边。\n"
    "苏晚发现地窖入口。"
)


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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plan() -> dict:
    events = [
        ("PE-0001", "林乔把铜钥匙锁进木匣"),
        ("PE-0002", "林乔把银钥匙交给周宁"),
        ("PE-0003", "周宁点燃灯塔"),
        ("PE-0004", "城门在午夜关闭"),
        ("PE-0005", "黑影是沈默"),
    ]
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
                "must_not": ["计划不能冒充事实"],
                "risks": [],
                "target_length": 1200,
                "outline_checkpoint": {
                    "outline_rev": 2,
                    "source_slot_ref": "S-0001",
                    "source_commit_seq": 0,
                },
                "slot_status": "planned",
                "handover_parts": [],
                "truth_bearing": "primary",
                "updated_at": "2026-08-18 21:00:00",
                "rev": 2,
            }
        ],
        "scenes": [
            {
                "id": "SCN-0001",
                "slot_ref": "S-0001",
                "goal": "原场目标",
                "summary": "原场梗概",
                "pe_refs": [item[0] for item in events],
                "truth_bearing": "primary",
                "updated_at": "2026-08-18 21:00:00",
                "rev": 1,
            }
        ],
        "events": [
            {
                "id": event_id,
                "scene_ref": "SCN-0001",
                "text": text,
                "truth_bearing": "primary",
                "updated_at": "2026-08-18 21:00:00",
                "rev": 1,
            }
            for event_id, text in events
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


def _work() -> dict:
    return {
        "contract": "WRITING_DESK_WORK_DRAFT",
        "version": "v1",
        "work_ref": "S-0001@work",
        "slot_ref": "S-0001",
        "source_outline_ref": "S-0001@outline-r2",
        "work_rev": 1,
        "state": "working",
        "entry_mode": "typed",
        "text": TEXT,
        "text_sha256": hashlib.sha256(TEXT.encode()).hexdigest(),
        "last_operation_id": "op-work-01",
    }


def _handover_action() -> dict:
    return {
        "contract": "WORK_DRAFT_HANDOVER_ACTION",
        "version": "v1",
        "operation_id": "op-handover-reconcile-fixture",
        "actor": "author",
        "intent": "adopt_as_manuscript",
        "work_ref": "S-0001@work",
        "work_rev": 1,
        "slot_ref": "S-0001",
        "source_outline_ref": "S-0001@outline-r2",
        "target_contract": "C1_CHAPTER_DOC",
        "target_planstore_result": "handover_parts",
    }


def _init(root: Path) -> dict:
    root.mkdir(parents=True)
    _write_json(root / "plan.json", _plan())
    _write_json(root / "chapters.json", [])
    _write_json(root / "facts.json", [])
    (root / "plan_history.jsonl").touch()
    (root / "commit_log.jsonl").touch()
    return planstore.accept_work_draft_handover(
        root,
        action=_handover_action(),
        current_work=_work(),
        title="合成章",
        timestamp=NOW,
    )


def _candidate(root: Path, operation_id: str = "op-reconcile-observe-01") -> dict:
    plan = _read_json(root / "plan.json")
    revs = {item["id"]: item["rev"] for item in plan["events"]}
    chapter = _read_json(root / "chapters.json")[0]
    facts = [
        {"candidate_ref": "FC-01", "text": "林乔把铜钥匙锁进木匣。", "quote": "林乔把铜钥匙锁进木匣。", "seg": 1, "source": "synthetic-c3"},
        {"candidate_ref": "FC-02", "text": "林乔把银钥匙交给苏晚。", "quote": "林乔把银钥匙交给苏晚。", "seg": 1, "source": "synthetic-c3"},
        {"candidate_ref": "FC-03", "text": "城门整夜敞开。", "quote": "城门整夜敞开。", "seg": 1, "source": "synthetic-c3"},
        {"candidate_ref": "FC-04", "text": "苏晚发现地窖入口。", "quote": "苏晚发现地窖入口。", "seg": 1, "source": "synthetic-c3"},
    ]
    rows = [
        ("I-01", "PE-0001", "exact", None, "林乔把铜钥匙锁进木匣。", ["FC-01"]),
        ("I-02", "PE-0002", "variant", "交付对象从周宁变成苏晚", "林乔把银钥匙交给苏晚。", ["FC-02"]),
        ("I-03", "PE-0003", "unrealized", None, None, []),
        ("I-04", "PE-0004", "contradicted", None, "城门整夜敞开。", ["FC-03"]),
        ("I-05", "PE-0005", "ambiguous", None, "黑影掠过窗边。", []),
        ("I-06", None, "unplanned", None, "苏晚发现地窖入口。", ["FC-04"]),
    ]
    return {
        "contract": "RECONCILIATION_CANDIDATE",
        "version": "v1",
        "reconcile_run_id": operation_id,
        "chapter_ref": chapter["id"],
        "chapter_text_sha256": hashlib.sha256(chapter["text"].encode()).hexdigest(),
        "slot_ref": "S-0001",
        "planning_basis_commit_seq": 1,
        "fact_candidates": facts,
        "items": [
            {
                "item_key": key,
                "planned_ref": planned_ref,
                "planned_rev": None if planned_ref is None else revs[planned_ref],
                "outcome": outcome,
                "coverage": "full",
                "variant_note": variant_note,
                "evidence_quote": quote,
                "fact_candidate_refs": refs,
                "rationale": "固定六态夹具",
            }
            for key, planned_ref, outcome, variant_note, quote, refs in rows
        ],
    }


def _admission_action(root: Path, candidate: dict, operation_id: str = "op-fact-admit-01") -> dict:
    edges = {edge["source_item_key"]: edge for edge in _read_json(root / "plan.json")["reconciliation_edges"]}
    return {
        "contract": "RECONCILIATION_FACT_ADMISSION_ACTION",
        "version": "v1",
        "operation_id": operation_id,
        "actor": "author",
        "reconcile_run_id": candidate["reconcile_run_id"],
        "candidate_sha256": reconcile._canonical_sha(candidate),
        "chapter_ref": candidate["chapter_ref"],
        "chapter_text_sha256": candidate["chapter_text_sha256"],
        "decisions": [
            {"edge_ref": edges["I-01"]["id"], "edge_rev": 1, "fact_candidate_refs": ["FC-01"], "reconciliation_action": None, "note": ""},
            {"edge_ref": edges["I-02"]["id"], "edge_rev": 1, "fact_candidate_refs": ["FC-02"], "reconciliation_action": "accept_as_is", "note": "接受变体"},
            {"edge_ref": edges["I-04"]["id"], "edge_rev": 1, "fact_candidate_refs": ["FC-03"], "reconciliation_action": "accept_as_is", "note": "以书稿为准"},
            {"edge_ref": edges["I-06"]["id"], "edge_rev": 1, "fact_candidate_refs": ["FC-04"], "reconciliation_action": "accept_as_is", "note": "确认重要新增"},
        ],
    }


def _observe(root: Path, candidate: dict | None = None) -> tuple[dict, dict]:
    candidate = _candidate(root) if candidate is None else candidate
    receipt = reconcile.record_reconciliation_candidate(root, candidate=candidate, timestamp=NOW)
    return candidate, receipt


def _admit(root: Path, candidate: dict, action: dict | None = None) -> tuple[dict, dict]:
    action = _admission_action(root, candidate) if action is None else action
    receipt = reconcile.admit_reconciled_facts(root, action=action, candidate=candidate, timestamp=NOW)
    return action, receipt


def _semantic_plan(plan: dict) -> dict:
    return {
        "slot": [plan["slots"][0][key] for key in ("goal", "summary", "entry_state", "exit_condition", "exit_hook")],
        "scene": [plan["scenes"][0][key] for key in ("goal", "summary")],
        "events": [item["text"] for item in plan["events"]],
    }


def _invoke(script: Path, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _input_file(root: Path, name: str, value: dict) -> Path:
    path = root / name
    _write_json(path, value)
    return path


def test_six_state_observation_writes_edges_but_no_facts_or_actual(tmp_path: Path) -> None:
    root = tmp_path / "observe"
    _init(root)
    plan_before = _semantic_plan(_read_json(root / "plan.json"))
    candidate, receipt = _observe(root)
    plan = _read_json(root / "plan.json")
    assert receipt["edge_count"] == 6
    assert {edge["outcome"] for edge in plan["reconciliation_edges"]} == reconcile.OUTCOMES
    assert all(edge["actual_fact_refs"] == [] for edge in plan["reconciliation_edges"])
    assert _read_json(root / "facts.json") == []
    assert not any(item["actual_support"] for item in reconcile.reconciliation_edge_states(root))
    assert _semantic_plan(plan) == plan_before
    assert candidate["chapter_text_sha256"] == plan["reconciliation_edges"][0]["chapter_text_sha256"]


def test_author_admission_writes_confirmed_facts_and_only_exact_variant_support_actual(tmp_path: Path) -> None:
    root = tmp_path / "admit"
    _init(root)
    plan_before = _semantic_plan(_read_json(root / "plan.json"))
    candidate, _ = _observe(root)
    _, receipt = _admit(root, candidate)
    facts = _read_json(root / "facts.json")
    plan = _read_json(root / "plan.json")
    assert receipt["facts_writes"] == 4
    assert [item["id"] for item in facts] == ["f001", "f002", "f003", "f004"]
    assert all(item["status"] == "confirmed" and item["quote"] in TEXT for item in facts)
    states = {item["edge_ref"]: item for item in reconcile.reconciliation_edge_states(root)}
    edges = {edge["outcome"]: edge for edge in plan["reconciliation_edges"]}
    assert states[edges["exact"]["id"]]["actual_support"] is True
    assert states[edges["variant"]["id"]]["actual_support"] is True
    assert states[edges["contradicted"]["id"]]["actual_support"] is False
    assert states[edges["unplanned"]["id"]]["actual_support"] is False
    assert edges["unrealized"]["actual_fact_refs"] == edges["ambiguous"]["actual_fact_refs"] == []
    assert _semantic_plan(plan) == plan_before
    assert not any("actual" in item for item in plan["events"])
    verified = planstore.verify_storage(root)
    assert verified["status"] == "PASS" and verified["confirmed_fact_count"] == 4


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda action: action.update(actor="model"), "FACT_ADMISSION_AUTHOR_REQUIRED"),
        (
            lambda action: action["decisions"][1].update(reconciliation_action=None),
            "DIFFERENCE_REQUIRES_ACCEPT_AS_IS",
        ),
        (
            lambda action: action["decisions"][0].update(edge_rev=99),
            "STALE_OR_WRONG_RECONCILIATION_EDGE",
        ),
        (
            lambda action: action["decisions"][0].update(fact_candidate_refs=["FC-99"]),
            "FACT_ADMISSION_CANDIDATE_REFS_INVALID",
        ),
    ],
)
def test_admission_permission_and_stale_guards_reject_before_write(
    tmp_path: Path, mutate, reason: str
) -> None:
    root = tmp_path / reason
    _init(root)
    candidate, _ = _observe(root)
    action = _admission_action(root, candidate)
    mutate(action)
    facts_sha = _sha(root / "facts.json")
    plan_sha = _sha(root / "plan.json")
    with pytest.raises(reconcile.ReconciliationError, match=reason):
        reconcile.admit_reconciled_facts(root, action=action, candidate=candidate, timestamp=NOW)
    assert _sha(root / "facts.json") == facts_sha
    assert _sha(root / "plan.json") == plan_sha


def test_unrealized_and_ambiguous_cannot_enter_fact_admission(tmp_path: Path) -> None:
    root = tmp_path / "no-fact-path"
    _init(root)
    candidate, _ = _observe(root)
    edges = {edge["source_item_key"]: edge for edge in _read_json(root / "plan.json")["reconciliation_edges"]}
    action = _admission_action(root, candidate)
    action["decisions"] = [
        {"edge_ref": edges["I-03"]["id"], "edge_rev": 1, "fact_candidate_refs": ["FC-01"], "reconciliation_action": "accept_as_is", "note": ""}
    ]
    with pytest.raises(reconcile.ReconciliationError, match="FACT_ADMISSION_CANDIDATE_REFS_INVALID"):
        reconcile.admit_reconciled_facts(root, action=action, candidate=candidate, timestamp=NOW)
    assert _read_json(root / "facts.json") == []


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda candidate: candidate.update(chapter_text_sha256="0" * 64), "STALE_C1_TEXT"),
        (lambda candidate: candidate["items"][0].update(planned_rev=99), "STALE_PLANNED_REVISION"),
        (lambda candidate: candidate["fact_candidates"][0].update(quote="不存在"), "C3_CANDIDATE_EVIDENCE_INVALID"),
        (lambda candidate: candidate["items"].pop(0), "RECONCILIATION_PLANNED_COVERAGE_INCOMPLETE"),
        (lambda candidate: candidate["items"][0].update(actual=True), "RECONCILIATION_ITEM_SCHEMA_MISMATCH"),
    ],
)
def test_observation_candidate_guards_reject_before_prepare(
    tmp_path: Path, mutate, reason: str
) -> None:
    root = tmp_path / reason
    _init(root)
    candidate = _candidate(root)
    mutate(candidate)
    with pytest.raises(reconcile.ReconciliationError, match=reason):
        reconcile.record_reconciliation_candidate(root, candidate=candidate, timestamp=NOW)
    assert len(_read_jsonl(root / "commit_log.jsonl")) == 2
    assert _read_json(root / "plan.json")["reconciliation_edges"] == []


def test_fact_change_and_planning_change_remove_actual_support_then_mark_stale(tmp_path: Path) -> None:
    root = tmp_path / "stale"
    _init(root)
    candidate, _ = _observe(root)
    _admit(root, candidate)
    facts = _read_json(root / "facts.json")
    facts[0]["status"] = "rejected"
    chapters = _read_json(root / "chapters.json")
    chapters[0]["text"] += "\n作者后来修订了这一章。"
    plan = _read_json(root / "plan.json")
    plan["events"][1]["rev"] += 1
    plan["events"] = [item for item in plan["events"] if item["id"] != "PE-0003"]
    plan["scenes"][0]["pe_refs"].remove("PE-0003")
    plan["slot_mappings"] = []
    plan["id_counters"]["MAP"] = 0
    with planstore._exclusive_lock(root):
        planstore._commit_generic_transaction_locked(
            root,
            operation_id="op-legitimate-upstream-change",
            action_name="test_upstream_change",
            request_sha256=reconcile._canonical_sha({"facts": facts, "plan": plan}),
            replacements={
                "facts.json": _canonical_bytes(facts),
                "chapters.json": _canonical_bytes(chapters),
                "plan.json": _canonical_bytes(plan),
            },
            appends={},
            blobs=[],
            receipt={"status": "COMMITTED"},
            timestamp=NOW,
        )
    states = {item["edge_ref"]: item for item in reconcile.reconciliation_edge_states(root)}
    edges = {edge["source_item_key"]: edge for edge in plan["reconciliation_edges"]}
    assert "STALE_FACT_BASIS" in states[edges["I-01"]["id"]]["stale_reasons"]
    assert "STALE_PLANNED_REVISION" in states[edges["I-02"]["id"]]["stale_reasons"]
    assert "STALE_PLANNED_REVISION" in states[edges["I-03"]["id"]]["stale_reasons"]
    assert all("STALE_C1_TEXT" in item["stale_reasons"] for item in states.values())
    assert all("STALE_SLOT_MAPPING" in item["stale_reasons"] for item in states.values())
    assert states[edges["I-01"]["id"]]["actual_support"] is False
    receipt = reconcile.mark_stale_reconciliation_edges(
        root, operation_id="op-mark-stale-01", timestamp=NOW
    )
    assert set(receipt["stale_edge_refs"]) >= {edges["I-01"]["id"], edges["I-02"]["id"]}
    current = _read_json(root / "plan.json")
    assert {edge["edge_status"] for edge in current["reconciliation_edges"] if edge["id"] in receipt["stale_edge_refs"]} == {"stale"}


@pytest.mark.parametrize(
    ("fault_at", "expected"),
    [
        ("after_prepare", "ROLLED_BACK"),
        ("after_plan", "ROLLED_BACK"),
        ("after_blob", "ROLLED_BACK"),
        ("during_history", "ROLLED_BACK"),
        ("after_history", "COMMITTED"),
        ("before_commit", "COMMITTED"),
        ("after_commit", "COMMITTED"),
    ],
)
def test_observation_faults_recover_across_processes(
    tmp_path: Path, fault_at: str, expected: str
) -> None:
    root = tmp_path / f"observe-{fault_at}"
    _init(root)
    candidate_path = _input_file(root, "candidate.json", _candidate(root))
    crashed = _invoke(
        RECONCILE_SCRIPT,
        root,
        "observe",
        str(root),
        "--candidate",
        str(candidate_path),
        "--timestamp",
        NOW,
        "--fault-at",
        fault_at,
    )
    assert crashed.returncode == 75, crashed.stdout + crashed.stderr
    recovered = _invoke(PLANSTORE_SCRIPT, root, "recover", str(root), "--timestamp", NOW)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    state = planstore.operation_status(root, "op-reconcile-observe-01")
    if expected == "ROLLED_BACK":
        assert state["terminal_phase"] == "rolled_back"
        assert _read_json(root / "plan.json")["reconciliation_edges"] == []
    else:
        assert state["state"] == "COMMITTED"
        assert len(_read_json(root / "plan.json")["reconciliation_edges"]) == 6
    assert _read_json(root / "facts.json") == []


@pytest.mark.parametrize(
    ("fault_at", "expected"),
    [
        ("after_prepare", "ROLLED_BACK"),
        ("after_facts", "ROLLED_BACK"),
        ("after_plan", "ROLLED_BACK"),
        ("after_blob", "ROLLED_BACK"),
        ("during_history", "ROLLED_BACK"),
        ("after_history", "COMMITTED"),
        ("before_commit", "COMMITTED"),
        ("after_commit", "COMMITTED"),
    ],
)
def test_admission_faults_recover_facts_and_edges_together(
    tmp_path: Path, fault_at: str, expected: str
) -> None:
    root = tmp_path / f"admit-{fault_at}"
    _init(root)
    candidate, _ = _observe(root)
    action = _admission_action(root, candidate)
    candidate_path = _input_file(root, "candidate.json", candidate)
    action_path = _input_file(root, "action.json", action)
    crashed = _invoke(
        RECONCILE_SCRIPT,
        root,
        "admit",
        str(root),
        "--candidate",
        str(candidate_path),
        "--action",
        str(action_path),
        "--timestamp",
        NOW,
        "--fault-at",
        fault_at,
    )
    assert crashed.returncode == 75, crashed.stdout + crashed.stderr
    recovered = _invoke(PLANSTORE_SCRIPT, root, "recover", str(root), "--timestamp", NOW)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    state = planstore.operation_status(root, "op-fact-admit-01")
    edges = _read_json(root / "plan.json")["reconciliation_edges"]
    if expected == "ROLLED_BACK":
        assert state["terminal_phase"] == "rolled_back"
        assert _read_json(root / "facts.json") == []
        assert all(edge["actual_fact_refs"] == [] for edge in edges)
    else:
        assert state["state"] == "COMMITTED"
        assert len(_read_json(root / "facts.json")) == 4
        assert sum(bool(edge["actual_fact_refs"]) for edge in edges) == 4


def test_cross_process_replay_is_idempotent_for_observation_and_admission(tmp_path: Path) -> None:
    root = tmp_path / "cross-process"
    _init(root)
    candidate = _candidate(root)
    candidate_path = _input_file(root, "candidate.json", candidate)
    observe_args = ["observe", str(root), "--candidate", str(candidate_path), "--timestamp", NOW]
    first = _invoke(RECONCILE_SCRIPT, root, *observe_args)
    replay = _invoke(RECONCILE_SCRIPT, root, *observe_args)
    assert first.returncode == replay.returncode == 0
    assert json.loads(first.stdout)["replayed"] is False
    assert json.loads(replay.stdout)["replayed"] is True
    action = _admission_action(root, candidate)
    action_path = _input_file(root, "action.json", action)
    admit_args = [
        "admit",
        str(root),
        "--candidate",
        str(candidate_path),
        "--action",
        str(action_path),
        "--timestamp",
        NOW,
    ]
    admitted = _invoke(RECONCILE_SCRIPT, root, *admit_args)
    admitted_replay = _invoke(RECONCILE_SCRIPT, root, *admit_args)
    assert admitted.returncode == admitted_replay.returncode == 0
    assert json.loads(admitted_replay.stdout)["replayed"] is True
    assert len(_read_json(root / "facts.json")) == 4
    assert len(_read_json(root / "plan.json")["reconciliation_edges"]) == 6


def test_concurrent_same_admission_creates_one_fact_set_and_one_commit(tmp_path: Path) -> None:
    root = tmp_path / "concurrent-admission"
    _init(root)
    candidate, _ = _observe(root)
    action = _admission_action(root, candidate)
    candidate_path = _input_file(root, "candidate.json", candidate)
    action_path = _input_file(root, "action.json", action)
    command = [
        sys.executable,
        str(RECONCILE_SCRIPT),
        "admit",
        str(root),
        "--candidate",
        str(candidate_path),
        "--action",
        str(action_path),
        "--timestamp",
        NOW,
    ]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    processes = [
        subprocess.Popen(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        for _ in range(2)
    ]
    outputs = [process.communicate(timeout=20) for process in processes]
    assert [process.returncode for process in processes] == [0, 0], outputs
    assert len(_read_json(root / "facts.json")) == 4
    phases = [
        row["phase"]
        for row in _read_jsonl(root / "commit_log.jsonl")
        if row.get("op") == "op-fact-admit-01"
    ]
    assert phases == ["prepare", "commit"]
