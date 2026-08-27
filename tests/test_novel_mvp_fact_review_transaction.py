from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
MVP_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(MVP_ROOT))

from mvp import factstore, planstore, reconcile, store  # noqa: E402
import cli as product_cli  # noqa: E402


NOW = "2026-08-18 23:00:00"
CAUSAL_NOW = "2026-08-27T18:00:00+08:00"
TEXT = "林乔把钥匙锁进木匣。"


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")


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


def _fact(status: str = "extracted") -> dict:
    return {
        "id": "f001",
        "chapter_id": "c01",
        "text": "林乔拿起钥匙。",
        "quote": "林乔拿起钥匙。",
        "status": status,
        "source": "synthetic-c3",
        "note": "",
        "added_at": "2026-08-18 22:00:00",
    }


def _plan_with_active_support(fact: dict) -> dict:
    chapter_sha = hashlib.sha256(TEXT.encode()).hexdigest()
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "scene_refs": ["SCN-0001"],
                "slot_status": "handed_over",
                "handover_parts": [
                    {
                        "part_no": 1,
                        "chapter_id": "c01",
                        "covered_scene_refs": ["SCN-0001"],
                        "covered_pe_refs": ["PE-0001"],
                        "handed_at": NOW,
                        "decided_by": "author",
                    }
                ],
                "truth_bearing": "handed_over",
                "rev": 2,
            }
        ],
        "scenes": [
            {
                "id": "SCN-0001",
                "slot_ref": "S-0001",
                "pe_refs": ["PE-0001"],
                "truth_bearing": "handed_over",
                "rev": 2,
            }
        ],
        "events": [
            {
                "id": "PE-0001",
                "scene_ref": "SCN-0001",
                "text": "林乔拿起钥匙。",
                "truth_bearing": "handed_over",
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
                "reason": "",
                "decided_by": "author",
                "mapping_status": "active",
                "superseded_by": None,
            }
        ],
        "reconciliation_edges": [
            {
                "id": "RE-0001",
                "planned_ref": "PE-0001",
                "planned_rev": 1,
                "actual_fact_refs": ["f001"],
                "actual_fact_basis_sha256": planstore._fact_basis_sha256([fact]),
                "chapter_ref": "c01",
                "slot_ref": "S-0001",
                "chapter_text_sha256": chapter_sha,
                "source_run_id": "op-reconcile-01",
                "source_item_key": "I-01",
                "outcome": "exact",
                "coverage": "full",
                "variant_note": None,
                "author_decision": None,
                "basis_commit_seq": 0,
                "decided_by": "author",
                "edge_status": "active",
                "superseded_by": None,
                "rev": 2,
            }
        ],
        "stop_points": {},
        "id_counters": {"MAP": 1, "RE": 1},
    }


def _init(root: Path, *, status: str = "extracted", with_support: bool = False) -> dict:
    root.mkdir(parents=True)
    fact = _fact("confirmed" if with_support else status)
    _write_json(root / "facts.json", [fact])
    _write_json(root / "chapters.json", [{"id": "c01", "kind": "draft", "text": TEXT}])
    if with_support:
        _write_json(root / "plan.json", _plan_with_active_support(fact))
    (root / "commit_log.jsonl").touch()
    (root / "plan_history.jsonl").touch()
    return fact


def _action(
    fact: dict, operation_id: str, decision: str, text: str | None = None
) -> dict:
    return factstore.build_review_action(
        fact,
        operation_id=operation_id,
        decision=decision,
        replacement_text=text,
    )


def _init_causal(root: Path, *, second_status: str = "confirmed") -> list[dict]:
    root.mkdir(parents=True)
    first = _fact("confirmed")
    second = {
        **_fact(second_status),
        "id": "f002",
        "text": "木匣因此无法被旁人打开。",
        "quote": "木匣因此无法被旁人打开。",
    }
    facts = [first, second]
    _write_json(root / "facts.json", facts)
    (root / "commit_log.jsonl").touch()
    (root / "plan_history.jsonl").touch()
    return facts


def _causal_candidate(
    *,
    source_identity: str = "model_suggested",
    evidence_refs: list[str] | None = None,
    from_fact_ref: str = "f001",
    to_fact_ref: str = "f002",
) -> dict:
    return {
        "source_identity": source_identity,
        "evidence_refs": ["f001"] if evidence_refs is None else evidence_refs,
        "note": "",
        "from_fact_ref": from_fact_ref,
        "to_fact_ref": to_fact_ref,
        "span": "直接",
    }


def test_confirm_reject_rejudge_and_atomic_edit_confirm(tmp_path: Path) -> None:
    root = tmp_path / "book"
    original = _init(root)
    confirm = factstore.review_fact(
        root,
        action=_action(original, "op-confirm-01", "confirm"),
        timestamp=NOW,
    )
    assert confirm["after_status"] == "confirmed"

    confirmed = _read_json(root / "facts.json")[0]
    reject = factstore.review_fact(
        root,
        action=_action(confirmed, "op-reject-01", "reject"),
        timestamp="2026-08-18 23:01:00",
    )
    assert (
        reject["before_status"] == "confirmed" and reject["after_status"] == "rejected"
    )

    rejected = _read_json(root / "facts.json")[0]
    edited = factstore.review_fact(
        root,
        action=_action(
            rejected, "op-edit-confirm-01", "edit_and_confirm", "林乔把钥匙交给苏晚。"
        ),
        timestamp="2026-08-18 23:02:00",
    )
    current = _read_json(root / "facts.json")[0]
    assert edited["after_status"] == "confirmed"
    assert current["text"] == "林乔把钥匙交给苏晚。"
    assert current["note"] == "原文候选：林乔拿起钥匙。"
    assert [
        row["action"]
        for row in _read_jsonl(root / "commit_log.jsonl")
        if row["phase"] == "prepare"
    ] == [
        "fact_review",
        "fact_review",
        "fact_review",
    ]


def test_legacy_store_and_cli_surface_delegate_to_transaction_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(store, "DATA_ROOT", tmp_path)
    store.init_project("book")
    chapter = store.add_chapter("book", "合成章", TEXT)
    assert (
        store.add_fact_candidates(
            "book",
            chapter["id"],
            [{"text": "林乔拿起钥匙。", "quote": "林乔拿起钥匙。"}],
            "fixture",
        )
        == 1
    )
    store.set_status("book", "f001", store.STATUS_CONFIRMED)
    store.review_fact(
        "book",
        "f001",
        decision="edit_and_confirm",
        replacement_text="林乔把钥匙交给苏晚。",
    )
    actions = [
        row["action"]
        for row in _read_jsonl(tmp_path / "book" / "commit_log.jsonl")
        if row.get("phase") == "prepare"
    ]
    assert actions == ["fact_candidates_add", "fact_review", "fact_review"]
    assert _read_json(tmp_path / "book" / "facts.json")[0]["status"] == "confirmed"


def test_old_cli_edit_and_confirm_is_one_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(store, "DATA_ROOT", tmp_path)
    store.init_project("book")
    chapter = store.add_chapter("book", "合成章", TEXT)
    store.add_fact_candidates(
        "book",
        chapter["id"],
        [{"text": "林乔拿起钥匙。", "quote": "林乔拿起钥匙。"}],
        "fixture",
    )
    answers = iter(["e", "林乔把钥匙交给苏晚。"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    product_cli.cmd_confirm(SimpleNamespace(project="book", chapter=None))
    fact = _read_json(tmp_path / "book" / "facts.json")[0]
    assert fact["text"] == "林乔把钥匙交给苏晚。" and fact["status"] == "confirmed"
    prepares = [
        row
        for row in _read_jsonl(tmp_path / "book" / "commit_log.jsonl")
        if row.get("phase") == "prepare" and row.get("action") == "fact_review"
    ]
    assert len(prepares) == 1


def test_legacy_duplicate_id_repair_uses_same_transaction_coordinator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(store, "DATA_ROOT", tmp_path)
    store.init_project("book")
    root = tmp_path / "book"
    duplicate = [_fact(), {**_fact(), "chapter_id": "c02", "text": "另一条旧记录"}]
    _write_json(root / "facts.json", duplicate)
    report = store.repair_ids("book")
    assert len(report["remap"]) == 1
    assert len({item["id"] for item in _read_json(root / "facts.json")}) == 2
    prepare = next(
        row
        for row in _read_jsonl(root / "commit_log.jsonl")
        if row["phase"] == "prepare"
    )
    assert prepare["action"] == "fact_id_repair"
    assert {item["path"] for item in prepare["files"]} == {
        "facts.json",
        "repair_ids_report.json",
    }


def test_stale_action_is_rejected_before_write(tmp_path: Path) -> None:
    root = tmp_path / "book"
    original = _init(root)
    stale = _action(original, "op-stale-01", "confirm")
    current = _read_json(root / "facts.json")
    current[0]["note"] = "并发修改"
    _write_json(root / "facts.json", current)
    before = (root / "facts.json").read_bytes()
    with pytest.raises(factstore.FactstoreError, match="STALE_FACT_REVISION"):
        factstore.review_fact(root, action=stale, timestamp=NOW)
    assert (root / "facts.json").read_bytes() == before
    assert _read_jsonl(root / "commit_log.jsonl") == []


def test_model_cannot_forge_author_review(tmp_path: Path) -> None:
    root = tmp_path / "book"
    original = _init(root)
    action = _action(original, "op-forged-model-01", "confirm")
    action["actor"] = "model"
    before = (root / "facts.json").read_bytes()
    with pytest.raises(factstore.FactstoreError, match="FACT_REVIEW_AUTHOR_REQUIRED"):
        factstore.review_fact(root, action=action, timestamp=NOW)
    assert (root / "facts.json").read_bytes() == before
    assert _read_jsonl(root / "commit_log.jsonl") == []


def test_rejudge_invalidates_old_actual_support_and_does_not_revive_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "book"
    confirmed = _init(root, with_support=True)
    assert reconcile.reconciliation_edge_states(root)[0]["actual_support"] is True
    rejected = factstore.review_fact(
        root,
        action=_action(confirmed, "op-support-reject", "reject"),
        timestamp=NOW,
    )
    assert rejected["stale_edge_refs"] == ["RE-0001"]
    state = reconcile.reconciliation_edge_states(root)[0]
    assert state["current"] is False and state["actual_support"] is False
    assert (
        _read_json(root / "plan.json")["reconciliation_edges"][0]["edge_status"]
        == "stale"
    )

    current_fact = _read_json(root / "facts.json")[0]
    factstore.review_fact(
        root,
        action=_action(current_fact, "op-support-reconfirm", "confirm"),
        timestamp="2026-08-18 23:03:00",
    )
    edge = _read_json(root / "plan.json")["reconciliation_edges"][0]
    assert edge["edge_status"] == "stale"
    assert reconcile.reconciliation_edge_states(root)[0]["actual_support"] is False
    assert planstore.verify_storage(root)["status"] == "PASS"


def test_same_operation_replays_and_different_payload_conflicts(tmp_path: Path) -> None:
    root = tmp_path / "book"
    original = _init(root)
    action = _action(original, "op-idempotent-01", "confirm")
    first = factstore.review_fact(root, action=action, timestamp=NOW)
    second = factstore.review_fact(root, action=action, timestamp=NOW)
    assert first["after_fact_sha256"] == second["after_fact_sha256"]
    assert first["replayed"] is False and second["replayed"] is True
    assert [row["phase"] for row in _read_jsonl(root / "commit_log.jsonl")] == [
        "prepare",
        "commit",
    ]
    conflict = copy.deepcopy(action)
    conflict["note"] = "不同载荷"
    with pytest.raises(factstore.FactstoreError, match="OPERATION_ID_PAYLOAD_CONFLICT"):
        factstore.review_fact(root, action=conflict, timestamp=NOW)


@pytest.mark.parametrize(
    ("fault_at", "expected_state"),
    [
        ("after_prepare", "NOT_HAPPENED"),
        ("after_facts", "NOT_HAPPENED"),
        ("after_plan", "NOT_HAPPENED"),
        ("after_blob", "NOT_HAPPENED"),
        ("during_history", "NOT_HAPPENED"),
        ("after_history", "COMMITTED"),
        ("before_commit", "COMMITTED"),
        ("after_commit", "COMMITTED"),
    ],
)
def test_cross_file_fault_recovery(
    tmp_path: Path, fault_at: str, expected_state: str
) -> None:
    root = tmp_path / fault_at
    confirmed = _init(root, with_support=True)
    action = _action(confirmed, f"op-crash-{fault_at}", "reject")
    with pytest.raises(planstore.InjectedCrash):
        factstore.review_fact(root, action=action, timestamp=NOW, fault_at=fault_at)
    planstore.recover(root, timestamp="2026-08-18 23:10:00")
    assert (
        planstore.operation_status(root, action["operation_id"])["state"]
        == expected_state
    )
    fact = _read_json(root / "facts.json")[0]
    edge = _read_json(root / "plan.json")["reconciliation_edges"][0]
    if expected_state == "COMMITTED":
        assert fact["status"] == "rejected" and edge["edge_status"] == "stale"
    else:
        assert fact["status"] == "confirmed" and edge["edge_status"] == "active"


def test_cross_process_same_operation_has_one_commit(tmp_path: Path) -> None:
    root = tmp_path / "book"
    original = _init(root)
    action = _action(original, "op-cross-process-01", "confirm")
    action_path = tmp_path / "action.json"
    _write_json(action_path, action)
    code = (
        "import json,sys; from pathlib import Path; from mvp import factstore; "
        "a=json.loads(Path(sys.argv[2]).read_text()); "
        "print(json.dumps(factstore.review_fact(sys.argv[1],action=a,timestamp='2026-08-18 23:00:00')))"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(MVP_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(root), str(action_path)],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(2)
    ]
    outputs = [process.communicate(timeout=20) for process in processes]
    assert [process.returncode for process in processes] == [0, 0], outputs
    receipts = [json.loads(stdout) for stdout, _ in outputs]
    assert sorted(item["replayed"] for item in receipts) == [False, True]
    assert [row["phase"] for row in _read_jsonl(root / "commit_log.jsonl")] == [
        "prepare",
        "commit",
    ]


def test_cross_process_competing_rejudgments_cannot_both_commit(tmp_path: Path) -> None:
    root = tmp_path / "book"
    original = _init(root)
    action_paths = []
    for operation_id, decision in (
        ("op-race-confirm", "confirm"),
        ("op-race-reject", "reject"),
    ):
        path = tmp_path / f"{operation_id}.json"
        _write_json(path, _action(original, operation_id, decision))
        action_paths.append(path)
    code = (
        "import json,sys; from pathlib import Path; from mvp import factstore; "
        "a=json.loads(Path(sys.argv[2]).read_text()); "
        "print(json.dumps(factstore.review_fact(sys.argv[1],action=a,timestamp='2026-08-18 23:00:00')))"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(MVP_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(root), str(path)],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for path in action_paths
    ]
    outputs = [process.communicate(timeout=20) for process in processes]
    assert sorted(process.returncode for process in processes) == [0, 1], outputs
    assert sum("STALE_FACT_REVISION" in stderr for _, stderr in outputs) == 1
    phases = [row["phase"] for row in _read_jsonl(root / "commit_log.jsonl")]
    assert phases == ["prepare", "commit"]


def test_fact_causal_edge_candidate_confirm_retire_and_read_surfaces(
    tmp_path: Path,
) -> None:
    root = tmp_path / "book"
    _init_causal(root)
    added = factstore.add_fact_causal_edge_candidates(
        root,
        items=[_causal_candidate()],
        actor="machine",
        timestamp=CAUSAL_NOW,
        operation_id="op-causal-add-01",
    )
    assert added["new_ce_ids"] == ["CE-0001"]
    edge = factstore.read_fact_causal_edges(root)[0]
    assert edge["confirm_status"] == "candidate"
    assert edge["source_identity"] == "model_suggested"
    assert factstore.read_confirmed_fact_causal_edges(root) == []

    confirmed = factstore.review_fact_causal_edge(
        root,
        edge_ref=edge["id"],
        expected_status=edge["confirm_status"],
        expected_edge_sha256=factstore.fact_causal_edge_sha256(edge),
        decision="confirm",
        actor="author",
        operation_id="op-causal-confirm-01",
        timestamp="2026-08-27T18:01:00+08:00",
    )
    assert confirmed["before_status"] == "candidate"
    assert confirmed["after_status"] == "confirmed"
    current = factstore.read_confirmed_fact_causal_edges(root)[0]
    assert current["id"] == "CE-0001" and current["rev"] == 2

    retired = factstore.review_fact_causal_edge(
        root,
        edge_ref=current["id"],
        expected_status=current["confirm_status"],
        expected_edge_sha256=factstore.fact_causal_edge_sha256(current),
        decision="retire",
        actor="author",
        operation_id="op-causal-retire-01",
        timestamp="2026-08-27T18:02:00+08:00",
        note="作者撤回这条因果判断",
    )
    assert retired["after_status"] == "retired"
    assert factstore.read_confirmed_fact_causal_edges(root) == []

    second = factstore.add_fact_causal_edge_candidates(
        root,
        items=[_causal_candidate(from_fact_ref="f002", to_fact_ref="f001")],
        actor="machine",
        timestamp="2026-08-27T18:03:00+08:00",
        operation_id="op-causal-add-02",
    )
    assert second["new_ce_ids"] == ["CE-0002"]
    history = _read_jsonl(root / "plan_history.jsonl")
    assert [row["action"] for row in history] == [
        "fact_causal_edge_candidate_add",
        "fact_causal_edge_review",
        "fact_causal_edge_review",
        "fact_causal_edge_candidate_add",
    ]


@pytest.mark.parametrize(
    ("item", "actor", "reason"),
    [
        (
            _causal_candidate(source_identity="author_declared"),
            "machine",
            "FACT_CAUSAL_EDGE_AUTHOR_SOURCE_REQUIRED",
        ),
        (
            _causal_candidate(evidence_refs=["AUTHOR_ATTESTATION"]),
            "machine",
            "FACT_CAUSAL_EDGE_AUTHOR_ATTESTATION_REQUIRED",
        ),
        (
            _causal_candidate(from_fact_ref="f001", to_fact_ref="f001"),
            "author",
            "CAUSAL_EDGE_SELF_LOOP_FORBIDDEN",
        ),
        (
            _causal_candidate(to_fact_ref="f999"),
            "machine",
            "FACT_CAUSAL_EDGE_ENDPOINT_NOT_FOUND",
        ),
        (
            _causal_candidate(evidence_refs=["f999"]),
            "machine",
            "FACT_CAUSAL_EDGE_EVIDENCE_NOT_FOUND",
        ),
    ],
)
def test_fact_causal_edge_bad_candidates_are_zero_write(
    tmp_path: Path, item: dict, actor: str, reason: str
) -> None:
    root = tmp_path / reason
    _init_causal(root)
    with pytest.raises(factstore.FactstoreError, match=reason):
        factstore.add_fact_causal_edge_candidates(
            root,
            items=[item],
            actor=actor,
            timestamp=CAUSAL_NOW,
            operation_id=f"op-causal-invalid-{len(reason)}",
        )
    assert factstore.read_fact_causal_edges(root) == []
    assert _read_jsonl(root / "commit_log.jsonl") == []


def test_fact_causal_edge_author_gate_evidence_gate_and_defer_are_zero_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "book"
    _init_causal(root, second_status="extracted")
    factstore.add_fact_causal_edge_candidates(
        root,
        items=[_causal_candidate(evidence_refs=[])],
        actor="machine",
        timestamp=CAUSAL_NOW,
        operation_id="op-causal-gates-add",
    )
    edge = factstore.read_fact_causal_edges(root)[0]
    edge_bytes = (root / factstore.CAUSAL_EDGE_FILENAME).read_bytes()
    log_bytes = (root / "commit_log.jsonl").read_bytes()

    deferred = factstore.review_fact_causal_edge(
        root,
        edge_ref=edge["id"],
        expected_status=edge["confirm_status"],
        expected_edge_sha256=factstore.fact_causal_edge_sha256(edge),
        decision="defer",
        actor="author",
        operation_id="op-causal-defer-01",
        timestamp="2026-08-27T18:01:00+08:00",
    )
    assert deferred["status"] == "NO_CHANGE"
    assert (root / factstore.CAUSAL_EDGE_FILENAME).read_bytes() == edge_bytes
    assert (root / "commit_log.jsonl").read_bytes() == log_bytes

    with pytest.raises(
        factstore.FactstoreError,
        match="FACT_CAUSAL_EDGE_REVIEW_AUTHOR_REQUIRED",
    ):
        factstore.review_fact_causal_edge(
            root,
            edge_ref=edge["id"],
            expected_status=edge["confirm_status"],
            expected_edge_sha256=factstore.fact_causal_edge_sha256(edge),
            decision="confirm",
            actor="machine",
            operation_id="op-causal-forged-confirm",
            timestamp="2026-08-27T18:01:00+08:00",
            evidence_refs=["AUTHOR_ATTESTATION"],
        )
    assert (root / factstore.CAUSAL_EDGE_FILENAME).read_bytes() == edge_bytes
    assert (root / "commit_log.jsonl").read_bytes() == log_bytes

    with pytest.raises(
        factstore.FactstoreError,
        match="FACT_CAUSAL_EDGE_ENDPOINT_NOT_CONFIRMED",
    ):
        factstore.review_fact_causal_edge(
            root,
            edge_ref=edge["id"],
            expected_status=edge["confirm_status"],
            expected_edge_sha256=factstore.fact_causal_edge_sha256(edge),
            decision="confirm",
            actor="author",
            operation_id="op-causal-unconfirmed-endpoint",
            timestamp="2026-08-27T18:01:00+08:00",
            evidence_refs=["AUTHOR_ATTESTATION"],
        )
    assert (root / factstore.CAUSAL_EDGE_FILENAME).read_bytes() == edge_bytes
    assert (root / "commit_log.jsonl").read_bytes() == log_bytes

    facts = _read_json(root / "facts.json")
    facts[1]["status"] = "confirmed"
    _write_json(root / "facts.json", facts)
    with pytest.raises(
        factstore.FactstoreError,
        match="CAUSAL_EDGE_CONFIRMED_REQUIRES_EVIDENCE",
    ):
        factstore.review_fact_causal_edge(
            root,
            edge_ref=edge["id"],
            expected_status=edge["confirm_status"],
            expected_edge_sha256=factstore.fact_causal_edge_sha256(edge),
            decision="confirm",
            actor="author",
            operation_id="op-causal-missing-evidence",
            timestamp="2026-08-27T18:02:00+08:00",
        )
    assert (root / factstore.CAUSAL_EDGE_FILENAME).read_bytes() == edge_bytes
    assert (root / "commit_log.jsonl").read_bytes() == log_bytes

    changed = factstore.read_fact_causal_edges(root)
    changed[0]["note"] = "并发改动"
    _write_json(root / factstore.CAUSAL_EDGE_FILENAME, changed)
    changed_bytes = (root / factstore.CAUSAL_EDGE_FILENAME).read_bytes()
    with pytest.raises(
        factstore.FactstoreError,
        match="STALE_FACT_CAUSAL_EDGE_REVISION",
    ):
        factstore.review_fact_causal_edge(
            root,
            edge_ref=edge["id"],
            expected_status=edge["confirm_status"],
            expected_edge_sha256=factstore.fact_causal_edge_sha256(edge),
            decision="retire",
            actor="author",
            operation_id="op-causal-stale-review",
            timestamp="2026-08-27T18:03:00+08:00",
        )
    assert (root / factstore.CAUSAL_EDGE_FILENAME).read_bytes() == changed_bytes
    assert (root / "commit_log.jsonl").read_bytes() == log_bytes


def test_fact_causal_edge_operation_replays_and_payload_conflicts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "book"
    _init_causal(root)
    kwargs = {
        "items": [_causal_candidate()],
        "actor": "machine",
        "timestamp": CAUSAL_NOW,
        "operation_id": "op-causal-idempotent-add",
    }
    first = factstore.add_fact_causal_edge_candidates(root, **kwargs)
    second = factstore.add_fact_causal_edge_candidates(root, **kwargs)
    assert first["new_ce_ids"] == second["new_ce_ids"] == ["CE-0001"]
    assert first["replayed"] is False and second["replayed"] is True
    conflict = copy.deepcopy(kwargs)
    conflict["items"] = [_causal_candidate(from_fact_ref="f002", to_fact_ref="f001")]
    with pytest.raises(factstore.FactstoreError, match="OPERATION_ID_PAYLOAD_CONFLICT"):
        factstore.add_fact_causal_edge_candidates(root, **conflict)
    assert [item["id"] for item in factstore.read_fact_causal_edges(root)] == [
        "CE-0001"
    ]

    edge = factstore.read_fact_causal_edges(root)[0]
    review_kwargs = {
        "edge_ref": edge["id"],
        "expected_status": edge["confirm_status"],
        "expected_edge_sha256": factstore.fact_causal_edge_sha256(edge),
        "decision": "confirm",
        "actor": "author",
        "operation_id": "op-causal-idempotent-confirm",
        "timestamp": "2026-08-27T18:01:00+08:00",
    }
    confirmed = factstore.review_fact_causal_edge(root, **review_kwargs)
    replayed = factstore.review_fact_causal_edge(root, **review_kwargs)
    assert confirmed["after_edge_sha256"] == replayed["after_edge_sha256"]
    assert confirmed["replayed"] is False and replayed["replayed"] is True


@pytest.mark.parametrize(
    ("fault_at", "expected_state"),
    [
        ("after_prepare", "NOT_HAPPENED"),
        ("after_fact_causal_edges", "NOT_HAPPENED"),
        ("after_blob", "NOT_HAPPENED"),
        ("after_history", "COMMITTED"),
        ("before_commit", "COMMITTED"),
        ("after_commit", "COMMITTED"),
    ],
)
def test_fact_causal_edge_fault_recovery(
    tmp_path: Path, fault_at: str, expected_state: str
) -> None:
    root = tmp_path / fault_at
    _init_causal(root)
    operation_id = f"op-causal-crash-{fault_at}"
    with pytest.raises(planstore.InjectedCrash):
        factstore.add_fact_causal_edge_candidates(
            root,
            items=[_causal_candidate()],
            actor="machine",
            timestamp=CAUSAL_NOW,
            operation_id=operation_id,
            fault_at=fault_at,
        )
    planstore.recover(root, timestamp="2026-08-27T18:10:00+08:00")
    assert planstore.operation_status(root, operation_id)["state"] == expected_state
    edges = factstore.read_fact_causal_edges(root)
    if expected_state == "COMMITTED":
        assert [item["id"] for item in edges] == ["CE-0001"]
    else:
        assert edges == []


@pytest.mark.parametrize(
    ("fault_at", "expected_state", "expected_status"),
    [
        ("after_fact_causal_edges", "NOT_HAPPENED", "candidate"),
        ("after_history", "COMMITTED", "confirmed"),
    ],
)
def test_fact_causal_edge_review_fault_recovery(
    tmp_path: Path,
    fault_at: str,
    expected_state: str,
    expected_status: str,
) -> None:
    root = tmp_path / f"review-{fault_at}"
    _init_causal(root)
    factstore.add_fact_causal_edge_candidates(
        root,
        items=[_causal_candidate()],
        actor="machine",
        timestamp=CAUSAL_NOW,
        operation_id=f"op-causal-review-setup-{fault_at}",
    )
    edge = factstore.read_fact_causal_edges(root)[0]
    operation_id = f"op-causal-review-crash-{fault_at}"
    with pytest.raises(planstore.InjectedCrash):
        factstore.review_fact_causal_edge(
            root,
            edge_ref=edge["id"],
            expected_status=edge["confirm_status"],
            expected_edge_sha256=factstore.fact_causal_edge_sha256(edge),
            decision="confirm",
            actor="author",
            operation_id=operation_id,
            timestamp="2026-08-27T18:01:00+08:00",
            fault_at=fault_at,
        )
    planstore.recover(root, timestamp="2026-08-27T18:10:00+08:00")
    assert planstore.operation_status(root, operation_id)["state"] == expected_state
    assert (
        factstore.read_fact_causal_edges(root)[0]["confirm_status"] == expected_status
    )


def test_direct_facts_writer_is_confined_to_factstore_and_bootstrap() -> None:
    mvp = MVP_ROOT / "mvp"
    factstore_text = (mvp / "factstore.py").read_text(encoding="utf-8")
    reconcile_text = (mvp / "reconcile.py").read_text(encoding="utf-8")
    store_text = (mvp / "store.py").read_text(encoding="utf-8")
    assert '"facts.json": planstore._canonical_bytes(facts_after)' in factstore_text
    assert '"facts.json": planstore._canonical_bytes' not in reconcile_text
    assert (
        store_text.count('_save(d / "facts.json"') == 1
    )  # 只剩 init_project 的空账初始化
    assert 'f["status"] =' not in store_text


def test_contract_and_docs_name_the_unique_writer() -> None:
    contract = (MVP_ROOT / "contracts" / "FACT_REVIEW_ACTION.md").read_text(
        encoding="utf-8"
    )
    c4 = (MVP_ROOT / "contracts" / "C4_FACT_QUERY.md").read_text(encoding="utf-8")
    assert "FACT_REVIEW_ACTION" in contract
    assert "factstore.py" in contract and "author" in contract
    assert "FACT_REVIEW_ACTION.md" in c4 and "prepare／commit" in c4
