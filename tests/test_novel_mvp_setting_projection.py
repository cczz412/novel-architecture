from __future__ import annotations

import copy
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
FIXTURE = ROOT / "tests/fixtures/novel_mvp/setting_projection"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import planstore, setting_projection as projection, settingstore
finally:
    sys.path.pop(0)


NOW = "2026-09-07T00:00:00+00:00"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _init(tmp_path: Path, *, facts=None, bindings=None) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    for path in FIXTURE.glob("*.json"):
        shutil.copyfile(path, project / path.name)
    if facts is not None:
        _write(project / "facts.json", facts)
    if bindings is not None:
        _write(project / projection.BINDINGS_FILENAME, bindings)
    return project


def _facts() -> list[dict]:
    return _load(FIXTURE / "facts.json")


def _bindings() -> list[dict]:
    return _load(FIXTURE / projection.BINDINGS_FILENAME)


def _binding(**changes) -> dict:
    row = _bindings()[0]
    row.update(changes)
    return row


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and not path.name.endswith(".lock")
    }


def _business_files(root: Path) -> dict[str, bytes]:
    names = {spec.filename for spec in settingstore.LEDGERS.values()}
    names |= {"plan.json", "plan_history.jsonl"}
    return {
        name: (root / name).read_bytes() for name in names if (root / name).exists()
    }


def test_north_tower_confirmed_facts_reach_all_six_ledgers(tmp_path: Path) -> None:
    root = _init(tmp_path)
    before_facts = (root / "facts.json").read_bytes()
    receipt = projection.project_confirmed_facts(root, operation_id="north-tower")
    assert receipt["contract"] == "SETTING_PROJECTION_RECEIPT"
    assert receipt["shape_status"] == "CANDIDATE_SHAPE_NOT_FROZEN"
    assert receipt["confirmed_fact_count"] == 9
    assert receipt["written_ledger_count"] == receipt["written_entry_count"] == 6
    assert receipt["projected_fact_count"] == 8
    assert (
        receipt["created_count"],
        receipt["appended_count"],
        receipt["skipped_count"],
    ) == (6, 2, 2)
    assert receipt["unbound_confirmed_count"] == 1
    assert receipt["unbound_confirmed_fact_ids"] == ["f009"]
    assert (root / "facts.json").read_bytes() == before_facts
    for ledger, spec in settingstore.LEDGERS.items():
        rows = settingstore.read_setting_records(root, ledger)
        assert len(rows) == 1
        row = rows[0]
        settingstore._validate_payload(spec, row)
        assert row["source_identity"] == "draft_inferred"
        assert row["confirm_status"] == "candidate"
        assert row["story_time"] is None
        assert len(row["evidence_refs"]) == 1
        assert "AUTHOR_ATTESTATION" not in json.dumps(row)
    character = settingstore.read_setting_records(root, "character")[0]
    assert character["id"] == "CH-0001"
    assert character["rev"] == 2
    assert character["evidence_refs"] == ["f007"]
    state = character["state_timeline"][0]
    assert state["ch_ref"] == character["id"]
    assert state["value"] == "北塔"
    assert state["story_time"] == {
        "start": {"chapter_revision_ref": _facts()[6]["chapter_revision_ref"]},
        "end": None,
    }


def test_operation_replay_is_exact_and_does_not_consult_changed_inputs(
    tmp_path: Path,
) -> None:
    root = _init(tmp_path)
    receipt = projection.project_confirmed_facts(root, operation_id="same-op")
    snapshot = _snapshot(root)
    assert projection.project_confirmed_facts(root, operation_id="same-op") == receipt
    assert _snapshot(root) == snapshot
    # 历史回执不冒充当前证明，原始输入后来损坏也不能把重放变成一次新写入。
    (root / "facts.json").write_text("坏 JSON", encoding="utf-8")
    (root / projection.BINDINGS_FILENAME).unlink()
    before = _business_files(root)
    assert projection.project_confirmed_facts(root, operation_id="same-op") == receipt
    assert _business_files(root) == before


def test_new_operation_also_deduplicates_already_projected_facts(
    tmp_path: Path,
) -> None:
    root = _init(tmp_path)
    projection.project_confirmed_facts(root, operation_id="first")
    before = _business_files(root)
    receipt = projection.project_confirmed_facts(root, operation_id="second")
    assert receipt["written_entry_count"] == 0
    assert receipt["created_count"] == receipt["appended_count"] == 0
    assert (
        len(
            [
                row
                for row in receipt["items"]
                if row["reason_code"] == "ALREADY_PROJECTED"
            ],
        )
        == 8
    )
    assert _business_files(root) == before


@pytest.mark.parametrize("explicit_id", [False, True])
def test_existing_target_appends_by_id_or_exact_name(
    tmp_path: Path,
    explicit_id: bool,
) -> None:
    root = _init(tmp_path, facts=[_facts()[0]], bindings=[_bindings()[0]])
    projection.project_confirmed_facts(root, operation_id="definition")
    binding = _bindings()[6]
    if explicit_id:
        binding["target"]["entry_id"] = "CH-0001"
    _write(root / "facts.json", [_facts()[0], _facts()[6]])
    _write(root / projection.BINDINGS_FILENAME, [_bindings()[0], binding])
    receipt = projection.project_confirmed_facts(root, operation_id="state")
    assert receipt["created_count"] == 0
    assert receipt["appended_count"] == 1
    rows = settingstore.read_setting_records(root, "character")
    assert len(rows) == 1
    assert rows[0]["rev"] == 2
    assert rows[0]["state_timeline"][0]["evidence_refs"] == ["f007"]


def test_new_state_gets_a_writer_allocated_id_before_self_reference(
    tmp_path: Path,
) -> None:
    root = _init(tmp_path, facts=[_facts()[6]], bindings=[_bindings()[6]])
    receipt = projection.project_confirmed_facts(root, operation_id="state-first")
    character = settingstore.read_setting_records(root, "character")[0]
    assert receipt["created_count"] == 1
    assert receipt["appended_count"] == 0
    assert character["id"] == "CH-0001"
    assert character["rev"] == 2
    assert character["state_timeline"][0]["ch_ref"] == "CH-0001"
    assert _load(root / "plan.json")["id_counters"]["CH"] == 1


@pytest.mark.parametrize("status", ["extracted", "rejected", "needs_recheck"])
def test_nonconfirmed_fact_never_creates_a_setting(tmp_path: Path, status: str) -> None:
    fact = _facts()[0]
    fact["status"] = status
    if status == "needs_recheck":
        fact["recheck"] = {
            "previous_status": "confirmed",
            "reason": "evidence_gone",
            "from_revision_no": 1,
            "target_revision_no": 2,
            "flagged_at": NOW,
        }
    root = _init(tmp_path, facts=[fact], bindings=[_bindings()[0]])
    receipt = projection.project_confirmed_facts(root, operation_id="unconfirmed")
    assert receipt["written_entry_count"] == 0
    assert receipt["items"][0]["reason_code"] == "FACT_NOT_CONFIRMED"
    assert not (root / "characters.json").exists()
    assert not (root / "plan_history.jsonl").exists()


def test_unbound_confirmed_facts_are_counted_without_guessing_or_plan(
    tmp_path: Path,
) -> None:
    root = _init(tmp_path, facts=_facts()[:2], bindings=[])
    (root / "plan.json").unlink()
    receipt = projection.project_confirmed_facts(root, operation_id="no-bindings")
    assert receipt["unbound_confirmed_fact_ids"] == ["f001", "f002"]
    assert receipt["skipped_count"] == 2
    assert receipt["written_ledger_count"] == 0
    assert all(
        not (root / spec.filename).exists() for spec in settingstore.LEDGERS.values()
    )


def test_missing_binding_file_is_empty_not_autogenerated(tmp_path: Path) -> None:
    root = _init(tmp_path, facts=[_facts()[0]], bindings=[])
    path = root / projection.BINDINGS_FILENAME
    path.unlink()
    receipt = projection.project_confirmed_facts(root, operation_id="missing-file")
    assert receipt["unbound_confirmed_fact_ids"] == ["f001"]
    assert not path.exists()


@pytest.mark.parametrize("legacy", [False, True])
def test_confirmed_definition_does_not_require_reading_chapter_text(
    tmp_path: Path,
    legacy: bool,
) -> None:
    fact = _facts()[0]
    if legacy:
        fact = {
            key: fact[key]
            for key in (
                "id",
                "chapter_id",
                "text",
                "quote",
                "status",
                "source",
                "note",
                "added_at",
            )
        }
    else:
        fact.update(anchor_state="LEGACY_UNVERIFIED", anchor_ref=None, quote="")
    root = _init(tmp_path, facts=[fact], bindings=[_bindings()[0]])
    (root / "chapters.json").write_text("不应该读取的坏 JSON", encoding="utf-8")
    assert (
        projection.project_confirmed_facts(
            root,
            operation_id="definition-only",
        )["created_count"]
        == 1
    )


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"fact_id": "not-a-fact"}, "BINDING_FACT_ID_INVALID"),
        ({"ledger": "fact"}, "BINDING_LEDGER_INVALID"),
        ({"ledger": []}, "BINDING_LEDGER_INVALID"),
        ({"target": {"entry_id": None, "canonical_name": " "}}, "BINDING_NAME_INVALID"),
        (
            {"target": {"entry_id": "LOC-0001", "canonical_name": "林舟"}},
            "BINDING_ENTRY_ID_INVALID",
        ),
        ({"target": {"entry_id": None}}, "BINDING_TARGET_INVALID"),
        ({"kind": "guess"}, "BINDING_KIND_INVALID"),
        ({"proposer": "administrator"}, "BINDING_PROPOSER_INVALID"),
        ({"note": None}, "BINDING_NOTE_INVALID"),
        ({"state_key": "alive"}, "BINDING_DEFINITION_STATE_KEY_FORBIDDEN"),
        (
            {"value": {"evidence_refs": ["AUTHOR_ATTESTATION"]}},
            "BINDING_DEFINITION_VALUE_INVALID",
        ),
        ({"value": "新的正文"}, "BINDING_DEFINITION_VALUE_INVALID"),
        (
            {"kind": "state", "state_key": "location", "value": None},
            "BINDING_STATE_VALUE_REQUIRED",
        ),
        (
            {"kind": "state", "state_key": "alive", "value": "alive"},
            "BINDING_ALIVE_REQUIRES_AUTHOR_ACTION",
        ),
    ],
)
def test_binding_errors_have_stable_codes(change: dict, code: str) -> None:
    with pytest.raises(projection.SettingProjectionError) as raised:
        projection.validate_setting_projection_binding(_binding(**change))
    assert raised.value.code == code
    assert str(raised.value) == code


def test_duplicate_binding_rows_are_not_silently_deduplicated() -> None:
    row = _binding()
    with pytest.raises(
        projection.SettingProjectionError,
        match="BINDING_FACT_DUPLICATE",
    ):
        projection.validate_setting_projection_bindings([row, copy.deepcopy(row)])


@pytest.mark.parametrize("ledger", ["system", "world_rule"])
def test_no_fabricated_state_column_for_system_or_world_rule(ledger: str) -> None:
    with pytest.raises(
        projection.SettingProjectionError,
        match="BINDING_STATE_NOT_SUPPORTED",
    ):
        projection.validate_setting_projection_binding(
            _binding(ledger=ledger, kind="state", state_key="status", value="开启"),
        )


@pytest.mark.parametrize("proposer", ["author", "model", "rule"])
def test_proposer_is_not_an_author_signature(tmp_path: Path, proposer: str) -> None:
    root = _init(tmp_path, facts=[_facts()[0]], bindings=[_binding(proposer=proposer)])
    projection.project_confirmed_facts(root, operation_id="proposer")
    row = settingstore.read_setting_records(root, "character")[0]
    assert (
        row["confirm_status"],
        row["source_identity"],
        row["evidence_refs"],
    ) == ("candidate", "draft_inferred", ["f001"])


@pytest.mark.parametrize(
    ("binding", "code"),
    [
        (_binding(fact_id="f999"), "BINDING_FACT_NOT_FOUND"),
        (
            _binding(target={"entry_id": "CH-9999", "canonical_name": "林舟"}),
            "PROJECTION_TARGET_NOT_FOUND",
        ),
        (_binding(value={"role_tag": []}), "PROJECTION_CONTENT_INVALID"),
    ],
)
def test_invalid_batch_does_not_start_a_setting_transaction(
    tmp_path: Path,
    binding: dict,
    code: str,
) -> None:
    root = _init(tmp_path, facts=[_facts()[0]], bindings=[binding])
    before = _snapshot(root)
    with pytest.raises(projection.SettingProjectionError, match=code):
        projection.project_confirmed_facts(root, operation_id="bad-input")
    assert _snapshot(root) == before


def test_plan_counter_base_is_required_but_never_fabricated(tmp_path: Path) -> None:
    root = _init(tmp_path, facts=[_facts()[0]], bindings=[_binding()])
    (root / "plan.json").unlink()
    with pytest.raises(
        projection.SettingProjectionError,
        match="PROJECTION_PLAN_REQUIRED",
    ):
        projection.project_confirmed_facts(root, operation_id="missing-plan")
    assert not (root / "commit_log.jsonl").exists()
    assert not (root / "plan.json").exists()


def test_legacy_state_without_story_anchor_is_rejected_before_write(
    tmp_path: Path,
) -> None:
    fact = {
        key: _facts()[6][key]
        for key in (
            "id",
            "chapter_id",
            "text",
            "quote",
            "status",
            "source",
            "note",
            "added_at",
        )
    }
    root = _init(tmp_path, facts=[fact], bindings=[_bindings()[6]])
    with pytest.raises(
        projection.SettingProjectionError,
        match="PROJECTION_STORY_ANCHOR_REQUIRED",
    ):
        projection.project_confirmed_facts(root, operation_id="no-time")
    assert not (root / "characters.json").exists()


def test_author_confirmed_card_is_not_downgraded_or_re_signed(tmp_path: Path) -> None:
    root = _init(tmp_path, facts=[_facts()[0]], bindings=[_binding()])
    record = projection._record(None, _binding(), _facts()[0])
    record.update(
        source_identity="author_declared",
        confirm_status="confirmed",
        evidence_refs=["AUTHOR_ATTESTATION"],
    )
    settingstore.write_setting_record(
        root,
        ledger="character",
        operation_id="author-definition",
        record=record,
        timestamp=NOW,
    )
    before = _snapshot(root)
    with pytest.raises(
        projection.SettingProjectionError,
        match="PROJECTION_TARGET_PROTECTED",
    ):
        projection.project_confirmed_facts(root, operation_id="protected")
    assert _snapshot(root) == before


@pytest.mark.parametrize(
    "point",
    [
        "after_prepare",
        "after_characters",
        "after_plan",
        "during_history",
        "after_history",
        "after_commit",
    ],
)
def test_interrupted_child_write_resumes_under_same_parent_id(
    tmp_path: Path,
    monkeypatch,
    point: str,
) -> None:
    root = _init(tmp_path, facts=[_facts()[0]], bindings=[_binding()])
    original = settingstore.write_setting_record
    fired = False

    def once(*args, **kwargs):
        nonlocal fired
        if not fired:
            fired = True
            kwargs["fault_at"] = point
        return original(*args, **kwargs)

    monkeypatch.setattr(settingstore, "write_setting_record", once)
    with pytest.raises(planstore.InjectedCrash):
        projection.project_confirmed_facts(root, operation_id="resume-parent")
    receipt = projection.project_confirmed_facts(root, operation_id="resume-parent")
    assert receipt["created_count"] == 1
    assert len(settingstore.read_setting_records(root, "character")) == 1
    assert _load(root / "plan.json")["id_counters"]["CH"] == 1
    assert (
        projection.project_confirmed_facts(
            root,
            operation_id="resume-parent",
        )
        == receipt
    )


def test_missing_receipt_after_committed_write_does_not_repeat_append(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = _init(tmp_path, facts=[_facts()[6]], bindings=[_bindings()[6]])
    original = projection._memo
    fired = False

    def once(root, operation_id, action, payload, timestamp):
        nonlocal fired
        if not fired and payload.get("action") == "created":
            fired = True
            raise planstore.InjectedCrash("写完条目、保存事实结果前中断")
        return original(root, operation_id, action, payload, timestamp)

    monkeypatch.setattr(projection, "_memo", once)
    with pytest.raises(planstore.InjectedCrash):
        projection.project_confirmed_facts(root, operation_id="receipt-interruption")
    receipt = projection.project_confirmed_facts(
        root,
        operation_id="receipt-interruption",
    )
    row = settingstore.read_setting_records(root, "character")[0]
    assert row["rev"] == 2
    assert len(row["state_timeline"]) == 1
    assert receipt["created_count"] == 1


def test_same_operation_concurrent_calls_share_one_receipt(tmp_path: Path) -> None:
    root = _init(tmp_path, facts=[_facts()[0]], bindings=[_binding()])
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(
            pool.map(
                lambda _: projection.project_confirmed_facts(
                    root,
                    operation_id="concurrent",
                ),
                range(2),
            ),
        )
    assert receipts[0] == receipts[1]
    assert len(settingstore.read_setting_records(root, "character")) == 1
    assert _load(root / "plan.json")["id_counters"]["CH"] == 1


def test_changed_binding_on_an_already_projected_fact_is_not_a_second_writer(
    tmp_path: Path,
) -> None:
    root = _init(tmp_path, facts=[_facts()[0]], bindings=[_binding()])
    projection.project_confirmed_facts(root, operation_id="original")
    _write(
        root / projection.BINDINGS_FILENAME,
        [_binding(target={"entry_id": None, "canonical_name": "另一个人"})],
    )
    before = _business_files(root)
    with pytest.raises(
        projection.SettingProjectionError,
        match="PROJECTION_PREVIOUS_BINDING_CONFLICT",
    ):
        projection.project_confirmed_facts(root, operation_id="changed")
    assert _business_files(root) == before


@pytest.mark.parametrize(
    ("ledger", "name", "key", "value", "destination"),
    [
        ("character", "林舟", "alias", "阿舟", "aliases"),
        (
            "character",
            "林舟",
            "relationship",
            {"target_ref": "CH-0002", "kind": "同伴"},
            "relationships",
        ),
        ("location", "北塔", "alias", "旧北塔", "aliases"),
        ("location", "北塔", "access", "开放", "state_timeline"),
        ("item", "铜钥匙", "ownership", "CH-0001", "ownership"),
        ("item", "铜钥匙", "condition", "完好", "item_status"),
        (
            "faction",
            "守塔人",
            "member",
            {"ch_ref": "CH-0001", "role": "值守"},
            "members",
        ),
        (
            "faction",
            "守塔人",
            "relation",
            {"target_ref": "FA-0002", "kind": "互助"},
            "relations",
        ),
        ("faction", "守塔人", "alias", "塔卫", "aliases"),
    ],
)
def test_state_goes_to_its_ledger_contract_column(
    tmp_path: Path,
    ledger: str,
    name: str,
    key: str,
    value,
    destination: str,
) -> None:
    facts, bindings = _facts()[:6], _bindings()[:6]
    root = _init(tmp_path, facts=facts, bindings=bindings)
    projection.project_confirmed_facts(root, operation_id="six-definitions")
    # 此处测合同字段和引用形状；不声称已解析 CH-0002／FA-0002 指向的外部条目。
    fact = copy.deepcopy(_facts()[6])
    fact.update(
        id="f012",
        text="用于合同落位的合成状态事实。",
        quote="",
        anchor_ref=None,
        anchor_state="LEGACY_UNVERIFIED",
    )
    binding = _binding(
        fact_id="f012",
        ledger=ledger,
        target={"entry_id": None, "canonical_name": name},
        kind="state",
        state_key=key,
        value=value,
    )
    _write(root / "facts.json", facts + [fact])
    _write(root / projection.BINDINGS_FILENAME, bindings + [binding])
    receipt = projection.project_confirmed_facts(root, operation_id="append-state")
    row = settingstore.read_setting_records(root, ledger)[0]
    assert receipt["appended_count"] == 1
    assert len(row[destination]) == 1
    assert row[destination][0]["evidence_refs"] == ["f012"]
    assert row[destination][0]["story_time"]["end"] is None
    settingstore._validate_payload(settingstore.LEDGERS[ledger], row)


def test_two_same_time_states_are_rejected_before_any_setting_write(
    tmp_path: Path,
) -> None:
    fact = copy.deepcopy(_facts()[6])
    fact["id"] = "f012"
    binding = copy.deepcopy(_bindings()[6])
    binding["fact_id"] = "f012"
    root = _init(
        tmp_path,
        facts=[_facts()[0], _facts()[6], fact],
        bindings=[_bindings()[0], _bindings()[6], binding],
    )
    with pytest.raises(
        projection.SettingProjectionError,
        match="PROJECTION_CONTENT_INVALID",
    ):
        projection.project_confirmed_facts(root, operation_id="same-time")
    assert not (root / "characters.json").exists()
    assert not (root / "commit_log.jsonl").exists()


def test_interrupted_run_rejects_changed_inputs_and_a_different_parent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = _init(tmp_path, facts=[_facts()[0]], bindings=[_binding()])
    original = settingstore.write_setting_record

    def crash(*args, **kwargs):
        kwargs["fault_at"] = "after_commit"
        return original(*args, **kwargs)

    monkeypatch.setattr(settingstore, "write_setting_record", crash)
    with pytest.raises(planstore.InjectedCrash):
        projection.project_confirmed_facts(root, operation_id="unfinished")
    monkeypatch.setattr(settingstore, "write_setting_record", original)
    with pytest.raises(
        projection.SettingProjectionError,
        match="PROJECTION_PREVIOUS_RUN_INCOMPLETE",
    ):
        projection.project_confirmed_facts(root, operation_id="another-parent")
    _write(root / projection.BINDINGS_FILENAME, [_binding(note="输入后来变了")])
    with pytest.raises(
        projection.SettingProjectionError,
        match="PROJECTION_INPUT_CHANGED",
    ):
        projection.project_confirmed_facts(root, operation_id="unfinished")
    assert len(settingstore.read_setting_records(root, "character")) == 1


def test_workspace_allocator_initialization_is_explicit_and_idempotent(tmp_path: Path) -> None:
    from mvp.workspace import WorkspaceRouter
    workspace = WorkspaceRouter(tmp_path).create_project("auth:allocator", "初始化")
    assert projection.initialize_setting_allocator(workspace, book_id="BK-TEST")["status"] == "INITIALIZED"
    assert projection.initialize_setting_allocator(workspace, book_id="BK-TEST")["status"] == "ALREADY_INITIALIZED"
    assert workspace.read("plan") is None
    root = projection._bound_project_dir(workspace)
    assert _load(root / "plan.json")["book"]["id"] == "BK-TEST"


def test_workspace_allocator_refuses_unsynchronized_logical_plan(tmp_path: Path) -> None:
    from mvp import plan_workspace
    from mvp.workspace import WorkspaceRouter
    workspace = WorkspaceRouter(tmp_path).create_project("auth:allocator", "初始化")
    plan_workspace.save_plan(workspace, "logical-plan", _load(FIXTURE / "plan.json"), 0)
    with pytest.raises(projection.SettingProjectionError, match="LOGICAL_PLAN_REQUIRES_RECONCILIATION"):
        projection.initialize_setting_allocator(workspace, book_id="BK-0001")
    assert not (projection._bound_project_dir(workspace) / "plan.json").exists()


def test_workspace_allocator_holds_workspace_lock_until_physical_write(tmp_path: Path, monkeypatch) -> None:
    import fcntl
    from mvp.workspace import WorkspaceRouter
    workspace = WorkspaceRouter(tmp_path).create_project("auth:allocator", "初始化")
    root = projection._bound_project_dir(workspace)
    original = settingstore.initialize_setting_allocator
    def check_lock(project, *, book_id):
        with (root / ".workspace.lock").open("rb") as handle:
            with pytest.raises(BlockingIOError):
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return original(project, book_id=book_id)
    monkeypatch.setattr(settingstore, "initialize_setting_allocator", check_lock)
    assert projection.initialize_setting_allocator(workspace, book_id="BK-TEST")["status"] == "INITIALIZED"


@pytest.mark.parametrize("via_adapter", [False, True])
def test_allocator_blocks_later_logical_plan_write(tmp_path: Path, via_adapter: bool) -> None:
    from mvp import plan_workspace
    from mvp.workspace import WorkspaceError, WorkspaceRouter
    workspace = WorkspaceRouter(tmp_path).create_project("auth:allocator", "初始化")
    projection.initialize_setting_allocator(workspace, book_id="BK-TEST")
    root = projection._bound_project_dir(workspace)
    physical_before = (root / "plan.json").read_bytes()
    other_plan = _load(FIXTURE / "plan.json")
    with pytest.raises(WorkspaceError, match="PHYSICAL_PLAN_REQUIRES_RECONCILIATION"):
        if via_adapter:
            plan_workspace.save_plan(workspace, "conflicting-plan", other_plan, 0)
        else:
            workspace.commit("conflicting-plan", {"plan": other_plan}, {"plan": 0})
    assert workspace.read("plan") is None
    assert (root / "plan.json").read_bytes() == physical_before


def test_allocator_and_logical_plan_creation_have_one_winner(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from mvp import plan_workspace
    from mvp.workspace import WorkspaceError, WorkspaceRouter
    workspace = WorkspaceRouter(tmp_path).create_project("auth:allocator", "竞争初始化")
    start = Barrier(2)
    def initialize():
        start.wait()
        try:
            projection.initialize_setting_allocator(workspace, book_id="BK-TEST")
            return "physical"
        except projection.SettingProjectionError as exc:
            assert "LOGICAL_PLAN_REQUIRES_RECONCILIATION" in str(exc)
            return "blocked"
    def save():
        start.wait()
        try:
            plan_workspace.save_plan(workspace, "logical-plan", _load(FIXTURE / "plan.json"), 0)
            return "logical"
        except WorkspaceError as exc:
            assert "PHYSICAL_PLAN_REQUIRES_RECONCILIATION" in str(exc)
            return "blocked"
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(initialize)
        second = pool.submit(save)
        results = [first.result(), second.result()]
    assert results.count("blocked") == 1
    root = projection._bound_project_dir(workspace)
    assert (root / "plan.json").exists() != (workspace.read("plan") is not None)
