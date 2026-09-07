from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import planstore, settingstore
finally:
    sys.path.pop(0)


NOW = "2026-08-22T12:00:00+08:00"
LATER = "2026-08-22T12:05:00+08:00"


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


def _without_id(record: dict) -> dict:
    payload = copy.deepcopy(record)
    payload.pop("id", None)
    return payload


def _character_payload(**overrides) -> dict:
    payload = {
        "canonical_name": "沈砚",
        "aliases": [],
        "role_tag": "主角",
        "profile": "出身北城，擅长拆解机关。",
        "visibility": "AUTHOR",
        "destiny_ref": None,
        "state_timeline": [],
        "relationships": [],
        "desire_seq": [],
        "ordeal_seq": [],
        "intent_seq": [],
        "choice_seq": [],
        "source_identity": "author_declared",
        "confirm_status": "confirmed",
        "evidence_refs": ["AUTHOR_ATTESTATION"],
        "story_time": None,
        "note": "",
    }
    payload.update(overrides)
    return payload


def _location_payload() -> dict:
    return {
        "name": "北城",
        "aliases": [],
        "loc_type": "城",
        "parent_ref": None,
        "profile": "北境商路枢纽。",
        "state_timeline": [],
        "source_identity": "author_declared",
        "confirm_status": "confirmed",
        "evidence_refs": ["AUTHOR_ATTESTATION"],
        "story_time": None,
        "note": "",
    }


def _item_payload() -> dict:
    return {
        "name": "玄铁令",
        "item_type": "信物",
        "first_seen": {
            "chapter_revision_ref": {
                "chapter_id": "c05",
                "revision_no": 1,
                "revision_text_sha256": "b" * 64,
            },
            "story_order": 50,
        },
        "ownership": [],
        "item_status": [],
        "source_identity": "author_declared",
        "confirm_status": "confirmed",
        "evidence_refs": ["AUTHOR_ATTESTATION"],
        "story_time": None,
        "note": "",
    }


def _faction_payload() -> dict:
    return {
        "name": "白鹤盟",
        "aliases": [],
        "fac_type": "组织",
        "members": [],
        "relations": [],
        "profile": "北境商盟。",
        "source_identity": "author_declared",
        "confirm_status": "confirmed",
        "evidence_refs": ["AUTHOR_ATTESTATION"],
        "story_time": None,
        "note": "",
    }


def _system_payload() -> dict:
    return {
        "name": "炼气",
        "category": "等级体系",
        "rank_order": 1,
        "relations": [],
        "scope": "东陆修士",
        "pack_ref": None,
        "source_identity": "author_declared",
        "confirm_status": "confirmed",
        "evidence_refs": ["AUTHOR_ATTESTATION"],
        "story_time": None,
        "note": "",
    }


def _world_rule_payload() -> dict:
    return {
        "rule_text": "东陆修士突破金丹时必须经历雷劫。",
        "scope": "东陆修士",
        "hardness": "hard",
        "exceptions": [],
        "source_identity": "author_declared",
        "confirm_status": "confirmed",
        "evidence_refs": ["AUTHOR_ATTESTATION"],
        "story_time": None,
        "note": "",
    }


LEDGER_PAYLOADS = {
    "character": _character_payload,
    "location": _location_payload,
    "item": _item_payload,
    "faction": _faction_payload,
    "system": _system_payload,
    "world_rule": _world_rule_payload,
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
                "text": "林乔把钥匙锁进木匣。",
                "added_at": NOW,
                "chapter_revision_ref": {
                    "chapter_id": "c01",
                    "revision_no": 1,
                    "revision_text_sha256": hashlib.sha256(
                        "林乔把钥匙锁进木匣。".encode("utf-8")
                    ).hexdigest(),
                },
            }
        ],
    )
    _write_json(root / "facts.json", [])
    (root / "plan_history.jsonl").touch()
    (root / "commit_log.jsonl").touch()


def _write(root: Path, *, ledger: str = "character", operation_id: str = "op-setting-01", **kwargs):
    payload = kwargs.pop("record", None)
    if payload is None:
        payload = LEDGER_PAYLOADS[ledger]()
    return settingstore.write_setting_record(
        root,
        ledger=ledger,
        operation_id=operation_id,
        record=payload,
        timestamp=kwargs.pop("timestamp", NOW),
        **kwargs,
    )


def test_character_create_commits_atomically_and_leaves_other_ledgers_untouched(
    tmp_path: Path,
) -> None:
    root = tmp_path / "book"
    _init(root)
    facts_sha = _sha(root / "facts.json")
    chapters_sha = _sha(root / "chapters.json")
    plan_before = _read_json(root / "plan.json")

    receipt = _write(root)
    records = settingstore.read_setting_records(root, "character")
    plan = _read_json(root / "plan.json")
    commit_rows = _read_jsonl(root / "commit_log.jsonl")

    assert receipt == {
        "operation_id": "op-setting-01",
        "status": "COMMITTED",
        "ledger": "character",
        "record_ref": "CH-0001",
        "rev": 1,
        "created": True,
        "story_commit_seq": 1,
        "replayed": False,
    }
    assert [item["id"] for item in records] == ["CH-0001"]
    assert records[0]["canonical_name"] == "沈砚"
    assert records[0]["rev"] == 1
    assert plan["id_counters"]["CH"] == 1
    assert plan["id_counters"]["MAP"] == plan_before["id_counters"]["MAP"]
    assert plan["id_counters"]["RE"] == plan_before["id_counters"]["RE"]
    assert [row["phase"] for row in commit_rows] == ["prepare", "commit"]
    assert commit_rows[0]["action"] == "setting_ledger_write"
    assert {row["path"] for row in commit_rows[0]["files"]} >= {
        "characters.json",
        "plan.json",
        "plan_history.jsonl",
    }
    assert _sha(root / "facts.json") == facts_sha
    assert _sha(root / "chapters.json") == chapters_sha
    assert not (root / "locations.json").exists()
    assert planstore.verify_storage(root)["status"] == "PASS"


@pytest.mark.parametrize(
    ("ledger", "entry_id", "filename", "counter_key"),
    [
        ("character", "CH-0001", "characters.json", "CH"),
        ("location", "LOC-0001", "locations.json", "LOC"),
        ("item", "IT-0001", "items.json", "IT"),
        ("faction", "FA-0001", "factions.json", "FA"),
        ("system", "SY-0001", "systems.json", "SY"),
        ("world_rule", "RU-0001", "world_rules.json", "RU"),
    ],
)
def test_all_six_setting_ledgers_share_the_same_writer(
    tmp_path: Path,
    ledger: str,
    entry_id: str,
    filename: str,
    counter_key: str,
) -> None:
    root = tmp_path / ledger
    _init(root)
    receipt = _write(root, ledger=ledger, operation_id=f"op-{ledger}-01")
    assert receipt["record_ref"] == entry_id
    assert receipt["created"] is True
    assert _read_json(root / filename)[0]["id"] == entry_id
    assert _read_json(root / "plan.json")["id_counters"][counter_key] == 1
    assert planstore.verify_storage(root)["status"] == "PASS"


def test_update_bumps_rev_keeps_id_and_does_not_recycle_on_retire(tmp_path: Path) -> None:
    root = tmp_path / "book"
    _init(root)
    created = _write(root)
    current = settingstore.read_setting_records(root, "character")[0]
    updated_payload = _without_id(current)
    updated_payload["id"] = current["id"]
    updated_payload["profile"] = "北城出身，后来改了背景卡。"

    updated = settingstore.write_setting_record(
        root,
        ledger="character",
        operation_id="op-setting-02",
        record=updated_payload,
        timestamp=LATER,
        expected_rev=1,
    )
    after_update = settingstore.read_setting_records(root, "character")[0]
    assert created["record_ref"] == updated["record_ref"] == "CH-0001"
    assert updated["rev"] == 2
    assert updated["created"] is False
    assert after_update["profile"].startswith("北城出身")
    assert after_update["created_at"] == NOW
    assert after_update["updated_at"] == LATER
    assert _read_json(root / "plan.json")["id_counters"]["CH"] == 1

    retired_payload = _without_id(after_update)
    retired_payload["id"] = "CH-0001"
    retired_payload["confirm_status"] = "retired"
    retired_payload["evidence_refs"] = []
    settingstore.write_setting_record(
        root,
        ledger="character",
        operation_id="op-setting-03",
        record=retired_payload,
        timestamp="2026-08-22T12:10:00+08:00",
        expected_rev=2,
    )
    second = _write(root, operation_id="op-setting-04", timestamp="2026-08-22T12:11:00+08:00")
    ids = [item["id"] for item in settingstore.read_setting_records(root, "character")]
    assert ids == ["CH-0001", "CH-0002"]
    assert second["record_ref"] == "CH-0002"
    assert _read_json(root / "plan.json")["id_counters"]["CH"] == 2
    assert settingstore.read_setting_records(root, "character")[0]["confirm_status"] == "retired"


def test_replay_is_idempotent_and_equivalent_write_is_no_change(tmp_path: Path) -> None:
    root = tmp_path / "book"
    _init(root)
    first = _write(root)
    replay = _write(root)
    current = settingstore.read_setting_records(root, "character")[0]
    no_change = settingstore.write_setting_record(
        root,
        ledger="character",
        operation_id="op-setting-no-change",
        record=current,
        timestamp=LATER,
    )
    assert first["record_ref"] == replay["record_ref"] == "CH-0001"
    assert replay["replayed"] is True
    assert no_change["status"] == "NO_CHANGE"
    assert no_change["rev"] == 1
    assert len(settingstore.read_setting_records(root, "character")) == 1
    assert _read_json(root / "plan.json")["id_counters"]["CH"] == 1
    assert [row["op"] for row in _read_jsonl(root / "commit_log.jsonl")] == [
        "op-setting-01",
        "op-setting-01",
    ]


def test_caller_chosen_id_and_invalid_payload_are_rejected_before_prepare(
    tmp_path: Path,
) -> None:
    root = tmp_path / "book"
    _init(root)
    before = {
        path.name: _sha(path)
        for path in (root / "plan.json", root / "plan_history.jsonl", root / "commit_log.jsonl")
    }
    private = _character_payload()
    private["id"] = "CH-0001"
    with pytest.raises(settingstore.SettingstoreError, match="SETTING_RECORD_NOT_FOUND"):
        settingstore.write_setting_record(
            root,
            ledger="character",
            operation_id="op-private-id",
            record=private,
            timestamp=NOW,
        )
    bad = _character_payload()
    bad["canonical_name"] = ""
    with pytest.raises(settingstore.SettingstoreError, match="SETTING_CONTRACT_INVALID"):
        settingstore.write_setting_record(
            root,
            ledger="character",
            operation_id="op-invalid-payload",
            record=bad,
            timestamp=NOW,
        )
    after = {
        path.name: _sha(path)
        for path in (root / "plan.json", root / "plan_history.jsonl", root / "commit_log.jsonl")
    }
    assert after == before
    assert _read_jsonl(root / "commit_log.jsonl") == []
    assert planstore.operation_status(root, "op-private-id")["state"] == "NOT_HAPPENED"
    assert planstore.operation_status(root, "op-invalid-payload")["state"] == "NOT_HAPPENED"


def test_character_write_fills_omitted_v11_sequences(tmp_path: Path) -> None:
    root = tmp_path / "book"
    _init(root)
    payload = _character_payload()
    for key in ("desire_seq", "ordeal_seq", "intent_seq", "choice_seq"):
        payload.pop(key)
    settingstore.write_setting_record(
        root,
        ledger="character",
        operation_id="op-setting-omit-seq",
        record=payload,
        timestamp=NOW,
    )
    saved = settingstore.read_setting_records(root, "character")[0]
    assert saved["version"] == "character-ledger-content-v1.1"
    assert saved["desire_seq"] == []
    assert saved["ordeal_seq"] == []
    assert saved["intent_seq"] == []
    assert saved["choice_seq"] == []


def test_character_write_rejects_desire_missing_source_fact_ref(tmp_path: Path) -> None:
    root = tmp_path / "book"
    _init(root)
    payload = _character_payload()
    payload["desire_seq"] = [
        {
            "id": "DESIRE-0001",
            "subject_ref": "CH-0001",
            "content": "想亲手拆开北城禁门。",
            "status": "活跃",
            "achieved_fact_ref": None,
            "next_desire_ref": None,
        }
    ]
    with pytest.raises(settingstore.SettingstoreError, match="SETTING_CONTRACT_INVALID"):
        settingstore.write_setting_record(
            root,
            ledger="character",
            operation_id="op-setting-desire-no-source",
            record=payload,
            timestamp=NOW,
        )
    assert settingstore.read_setting_records(root, "character") == []
    assert planstore.operation_status(root, "op-setting-desire-no-source")["state"] == "NOT_HAPPENED"


@pytest.mark.parametrize("ledger", ["longline", "plan", "fact", "chapter"])
def test_rejects_non_setting_ledgers(tmp_path: Path, ledger: str) -> None:
    root = tmp_path / ledger
    _init(root)
    with pytest.raises(settingstore.SettingstoreError, match="LEDGER_NOT_A_SETTING_LEDGER"):
        settingstore.write_setting_record(
            root,
            ledger=ledger,
            operation_id="op-wrong-ledger",
            record=_character_payload(),
            timestamp=NOW,
        )
    assert _read_jsonl(root / "commit_log.jsonl") == []


@pytest.mark.parametrize(
    ("fault_at", "expected_recovery"),
    [
        ("after_prepare", "ROLLED_BACK"),
        ("after_characters", "ROLLED_BACK"),
        ("after_blob", "ROLLED_BACK"),
        ("during_history", "ROLLED_BACK"),
        ("after_history", "COMMITTED"),
        ("before_commit", "COMMITTED"),
    ],
)
def test_fault_injection_recovers_generic_setting_transaction(
    tmp_path: Path,
    fault_at: str,
    expected_recovery: str,
) -> None:
    root = tmp_path / fault_at
    _init(root)
    facts_sha = _sha(root / "facts.json")
    before_plan = _sha(root / "plan.json")

    with pytest.raises(planstore.InjectedCrash, match=fault_at):
        _write(root, fault_at=fault_at)

    recovered = planstore.recover(root, timestamp="2026-08-22T12:01:00+08:00")
    state = planstore.operation_status(root, "op-setting-01")
    assert _sha(root / "facts.json") == facts_sha
    if expected_recovery == "ROLLED_BACK":
        assert recovered == [{"operation_id": "op-setting-01", "result": "ROLLED_BACK"}]
        assert state["state"] == "NOT_HAPPENED"
        assert state["terminal_phase"] == "rolled_back"
        assert _sha(root / "plan.json") == before_plan
        assert "CH" not in _read_json(root / "plan.json")["id_counters"]
        assert settingstore.read_setting_records(root, "character") == []
        assert [row["phase"] for row in _read_jsonl(root / "commit_log.jsonl")] == [
            "prepare",
            "rolled_back",
        ]
        with pytest.raises(
            settingstore.SettingstoreError,
            match="OPERATION_ROLLED_BACK_REQUIRES_NEW_ID",
        ):
            _write(root)
        retry = _write(root, operation_id="op-setting-retry")
        assert retry["record_ref"] == "CH-0001"
        assert _read_json(root / "plan.json")["id_counters"]["CH"] == 1
    else:
        assert recovered == [{"operation_id": "op-setting-01", "result": "COMMITTED"}]
        assert state["state"] == "COMMITTED"
        assert settingstore.read_setting_records(root, "character")[0]["id"] == "CH-0001"
        assert _read_json(root / "plan.json")["id_counters"]["CH"] == 1
        assert planstore.verify_storage(root)["status"] == "PASS"


def test_verify_detects_bypass_edits_to_characters_and_counters(tmp_path: Path) -> None:
    root = tmp_path / "book"
    _init(root)
    _write(root)
    records = _read_json(root / "characters.json")
    records[0]["profile"] = "旁路改写"
    _write_json(root / "characters.json", records)
    with pytest.raises(planstore.PlanstoreError, match="FINAL_CHARACTERS_COMMIT_HASH_MISMATCH"):
        planstore.verify_storage(root)

    root2 = tmp_path / "counters"
    _init(root2)
    _write(root2)
    plan = _read_json(root2 / "plan.json")
    plan["id_counters"]["CH"] = 9
    _write_json(root2 / "plan.json", plan)
    with pytest.raises(planstore.PlanstoreError, match="FINAL_PLAN_COMMIT_HASH_MISMATCH"):
        planstore.verify_storage(root2)


def test_second_ledger_write_does_not_move_character_counter_or_facts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "book"
    _init(root)
    _write(root)
    facts_sha = _sha(root / "facts.json")
    character_sha = _sha(root / "characters.json")
    _write(root, ledger="location", operation_id="op-location-01")
    assert _sha(root / "facts.json") == facts_sha
    assert _sha(root / "characters.json") == character_sha
    assert _read_json(root / "plan.json")["id_counters"] == {
        "MAP": 1,
        "RE": 0,
        "CH": 1,
        "LOC": 1,
    }
    assert settingstore.read_setting_records(root, "location")[0]["id"] == "LOC-0001"
    assert planstore.verify_storage(root)["status"] == "PASS"


def test_stale_expected_rev_is_rejected_before_prepare(tmp_path: Path) -> None:
    root = tmp_path / "book"
    _init(root)
    _write(root)
    current = settingstore.read_setting_records(root, "character")[0]
    payload = _without_id(current)
    payload["id"] = current["id"]
    payload["profile"] = "这版已经过期。"
    log_before = _read_jsonl(root / "commit_log.jsonl")
    with pytest.raises(settingstore.SettingstoreError, match="STALE_SETTING_REVISION"):
        settingstore.write_setting_record(
            root,
            ledger="character",
            operation_id="op-stale-rev",
            record=payload,
            timestamp=LATER,
            expected_rev=9,
        )
    assert _read_jsonl(root / "commit_log.jsonl") == log_before
    assert settingstore.read_setting_records(root, "character")[0]["rev"] == 1


def test_storage_contract_names_planstore_reuse_and_forbids_private_writers() -> None:
    text = (
        PRODUCT_ROOT / "contracts" / "SETTING_LEDGER_STORAGE.md"
    ).read_text(encoding="utf-8")
    for needle in (
        "setting-ledger-storage-v1",
        "UNIFIED_WRITER_SETTINGSTORE_V1",
        "只有 settingstore",
        "id_counters",
        "不得消耗",
        "长线真值住规划账",
        "知情边字段枚举（T3）",
        "ADD-043",
        "READER 侧数据结构",
        "新账申请流程",
    ):
        assert needle in text


def test_initialize_allocator_preserves_written_counters(tmp_path: Path) -> None:
    assert settingstore.initialize_setting_allocator(tmp_path, book_id="BK-TEST")["status"] == "INITIALIZED"
    planstore._validate_plan(_read_json(tmp_path / "plan.json"))
    settingstore.write_setting_record(
        tmp_path, ledger="character", operation_id="init-character",
        record=_character_payload(), timestamp=NOW,
    )
    before = (tmp_path / "plan.json").read_bytes()
    assert _read_json(tmp_path / "plan.json")["id_counters"]["CH"] == 1
    assert settingstore.initialize_setting_allocator(tmp_path, book_id="BK-TEST")["status"] == "ALREADY_INITIALIZED"
    assert (tmp_path / "plan.json").read_bytes() == before
    with pytest.raises(settingstore.SettingstoreError, match="BOOK_ID_CONFLICT"):
        settingstore.initialize_setting_allocator(tmp_path, book_id="BK-OTHER")
    assert (tmp_path / "plan.json").read_bytes() == before


def test_initialize_allocator_rejects_orphan_records(tmp_path: Path) -> None:
    _write_json(tmp_path / "characters.json", [{"id": "CH-0001"}])
    with pytest.raises(settingstore.SettingstoreError, match="MISSING_WITH_EXISTING_RECORDS"):
        settingstore.initialize_setting_allocator(tmp_path, book_id="BK-TEST")
    assert not (tmp_path / "plan.json").exists()


@pytest.mark.parametrize("bad_id", [None, "", " ", " BK-TEST"])
def test_initialize_allocator_rejects_invalid_identity(tmp_path: Path, bad_id) -> None:
    with pytest.raises(settingstore.SettingstoreError, match="BOOK_ID_INVALID"):
        settingstore.initialize_setting_allocator(tmp_path, book_id=bad_id)
    assert not (tmp_path / "plan.json").exists()


def test_initialize_allocator_failed_replace_leaves_no_plan(tmp_path: Path, monkeypatch) -> None:
    original = planstore.os.replace
    def fail_replace(*args):
        raise OSError("injected replace failure")
    monkeypatch.setattr(planstore.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected"):
        settingstore.initialize_setting_allocator(tmp_path, book_id="BK-TEST")
    assert not (tmp_path / "plan.json").exists()
    monkeypatch.setattr(planstore.os, "replace", original)
    assert settingstore.initialize_setting_allocator(tmp_path, book_id="BK-TEST")["status"] == "INITIALIZED"
    planstore._validate_plan(_read_json(tmp_path / "plan.json"))


def test_initialize_allocator_rejects_counter_drift(tmp_path: Path) -> None:
    settingstore.initialize_setting_allocator(tmp_path, book_id="BK-TEST")
    plan = _read_json(tmp_path / "plan.json")
    plan["id_counters"]["CH"] = 8
    _write_json(tmp_path / "plan.json", plan)
    before = (tmp_path / "plan.json").read_bytes()
    with pytest.raises(settingstore.SettingstoreError, match="COUNTER_DRIFT"):
        settingstore.initialize_setting_allocator(tmp_path, book_id="BK-TEST")
    assert (tmp_path / "plan.json").read_bytes() == before


@pytest.mark.parametrize("after_replace", [False, True])
def test_initialize_allocator_fsync_failure_leaves_absent_or_valid_plan(
    tmp_path: Path, monkeypatch, after_replace: bool,
) -> None:
    target = "_fsync_directory" if after_replace else None
    def fail_sync(*args):
        raise OSError("injected sync failure")
    if target:
        monkeypatch.setattr(planstore, target, fail_sync)
    else:
        monkeypatch.setattr(planstore.os, "fsync", fail_sync)
    with pytest.raises(OSError, match="injected"):
        settingstore.initialize_setting_allocator(tmp_path, book_id="BK-TEST")
    path = tmp_path / "plan.json"
    assert path.exists() == after_replace
    if after_replace:
        planstore._validate_plan(_read_json(path))
        assert _read_json(path)["book"]["id"] == "BK-TEST"


def test_initialize_allocator_concurrent_calls_only_create_once(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(
            lambda _: settingstore.initialize_setting_allocator(tmp_path, book_id="BK-TEST"),
            range(4),
        ))
    assert [row["status"] for row in results].count("INITIALIZED") == 1
    assert [row["status"] for row in results].count("ALREADY_INITIALIZED") == 3


def test_initialize_allocator_accepts_empty_ledger_files(tmp_path: Path) -> None:
    for spec in settingstore.LEDGERS.values():
        (tmp_path / spec.filename).write_bytes(b"")
    assert settingstore.initialize_setting_allocator(tmp_path, book_id="BK-EMPTY")["status"] == "INITIALIZED"
    assert all(settingstore.read_setting_records(tmp_path, name) == [] for name in settingstore.LEDGERS)
