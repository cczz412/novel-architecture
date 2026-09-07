"""Protect external-source INITIAL admission, replay, and the shared chapter owner."""

from __future__ import annotations

import base64
import copy
import hashlib
import inspect
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "novel-mvp"))
try:
    from contracts import validate_c11_chapter_revision_ledger as c11_contract
    from mvp import (
        chapter_handover_workspace,
        chapter_initial_admission_workspace as initial,
    )
    from mvp import chapter_workspace, external_chapter_admission_workspace as external
    from mvp import (
        ingest,
        ingest_workspace,
        plan_workspace,
        segment_tool,
        store,
        work_draft_workspace,
    )
    from mvp.upload_source import UploadSource
    from mvp.workspace import (
        ProjectNotFoundError,
        IntegrityError,
        InjectedWorkspaceCrash,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


AT = "2026-09-07T12:00:00+08:00"
TEXT = "第一章 雨夜\r\n\r\n  林乔把信交给守门人。\r\n雨还没有停。  "


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_ROOT", tmp_path / "legacy-m1")
    router = WorkspaceRouter(tmp_path / "runtime")
    workspace = router.create_project("author:alice", "合成接纳测试")
    return router, workspace, tmp_path / "runtime"


def _persist(
    workspace, *, texts=(TEXT,), operation="op-m1", role="CHAPTER", uploads=None
):
    store.init_project(operation)
    uploads = uploads or [
        UploadSource(f"source-{chr(96 + i)}.txt", text.encode(), encoding_hint="utf-8")
        for i, text in enumerate(texts, 1)
    ]
    result = ingest.ingest_uploads(operation, uploads, material_role=role)
    versions = {
        key: (workspace.read(key) or {}).get("version", 0)
        for key in ingest_workspace.VISIBLE_KEYS
    }
    ingest_workspace.persist_m1_result(workspace, operation, result, versions)
    return result


def _action(workspace, *, index=0, operation="op-admit"):
    preview = external.preview_external_chapters(workspace)
    item = preview["candidates"][index]
    return {
        "contract": external.ACTION_CONTRACT,
        "version": "v1",
        "operation_id": operation,
        "actor": "AUTHOR",
        "intent": "ADMIT_AS_INITIAL_CHAPTER",
        "material_unit_id": item["material_unit_id"],
        "identity_revision_no": item["identity_revision_no"],
        "chapter_title": item["title"] or "点名章节",
        "expected_m1_state": preview["m1_state"],
        "expected_next_chapter_number": preview["next_chapter_number"],
    }


def _tree(root):
    return {
        str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }


def _states(workspace):
    return {key: workspace.read(key) for key in initial.STATE_KEYS}


def _mutate_m1(workspace, mutate):
    manifest = workspace.read("input_manifest")
    state = workspace.read("module_state")
    changed = copy.deepcopy(state["payload"])
    mutate(changed)
    workspace.commit(
        "op-m1-altered",
        {"input_manifest": manifest["payload"], "module_state": changed},
        {"input_manifest": manifest["version"], "module_state": state["version"]},
    )


def test_saved_raw_c10_initial_c1_route_m2_and_reopen(setup):
    router, workspace, runtime = setup
    m1 = _persist(workspace)
    assert "chapter_revision_ref" not in m1["chapters"][0]
    raw_before = _tree(runtime)
    action = _action(workspace)
    assert _tree(runtime) == raw_before
    receipt = external.commit_external_chapter(workspace, action, AT)
    assert receipt["status"] == "EXTERNAL_INITIAL_COMMITTED"
    assert receipt["replayed"] is False
    assert receipt["facts_write"] == receipt["planstore_write"] == 0
    assert receipt["route_receipt"]["next_station"] == "M2_SEGMENT"
    assert receipt["route_receipt"]["source_kind"] == "EXTERNAL_CONFIRMED_CHAPTER"
    assert set(receipt["workspace_state"]) == initial.STATE_KEYS
    assert {v["version"] for v in receipt["workspace_state"].values()} == {1}
    reopened = WorkspaceRouter(runtime).open_project(
        "author:alice", workspace.project_id
    )
    resolved = external.resolve_external_admission(reopened, action["operation_id"])
    assert resolved["chapter"]["text"] == TEXT
    assert (
        c11_contract.validate_initial_commit(resolved["ledger"], [resolved["material"]])
        == "C10_CONFIRMED_CHAPTER_ELIGIBLE"
    )
    assert chapter_workspace.read_c1_current_views(reopened) == [resolved["chapter"]]
    source = next(
        iter(workspace.read("chapter_sources")["payload"]["sources"].values())
    )
    assert source["origin"]["kind"] == "EXTERNAL_UPLOAD"
    assert "work_ref" not in source["origin"]
    assert base64.b64decode(source["original_bytes_base64"]) == TEXT.encode()
    assert resolved["material"] == m1["material_units"][0]
    assert (
        resolved["ledger"]["revisions"][0]["origin_material_ref"][
            "identity_revision_no"
        ]
        == 1
    )
    c2 = segment_tool.execute(
        {
            "items": [resolved["chapter"]],
            "options": {"seg_min_chars": 10, "seg_max_chars": 80, "halo_chars": 5},
        }
    )
    assert c2["items"]
    assert all(
        item["chapter_revision_ref"] == receipt["chapter_revision_ref"]
        for item in c2["items"]
    )
    assert (
        workspace.read("draft")
        is workspace.read("plan")
        is workspace.read("facts")
        is None
    )
    with pytest.raises(ProjectNotFoundError):
        router.open_project("author:bob", workspace.project_id)


def test_three_chapters_share_allocator_and_never_overwrite(setup):
    _, workspace, _ = setup
    texts = tuple(f"第{i}章 章名\n正文{i}。" for i in range(1, 4))
    _persist(workspace, texts=texts)
    for i in range(3):
        before = copy.deepcopy((workspace.read("chapters") or {}).get("payload", []))
        result = external.commit_external_chapter(
            workspace, _action(workspace, index=i, operation=f"op-admit-{i}"), AT
        )
        chapters = chapter_workspace.read_c1_current_views(workspace)
        assert result["chapter_id"] == f"c{i + 1:02d}"
        assert chapters[:-1] == before
    assert [c["text"] for c in chapters] == list(texts)
    assert workspace.read("chapter_revisions")["payload"]["next_chapter_number"] == 4


def test_one_source_can_hold_two_explicit_nonoverlapping_chapter_materials(setup):
    _, workspace, _ = setup
    a, b = "第一章 雨夜\n林乔拆信。\n", "第二章 天明\n守门人离开。\n"
    raw = a + b
    declarations = []
    for start, end in [(0, len(a)), (len(a), len(raw))]:
        d = ingest._whole_source_declaration(end - start, "CHAPTER")
        d.update(start=start, end=end)
        declarations.append(d)
    _persist(
        workspace,
        uploads=[
            UploadSource(
                "two.txt",
                raw.encode(),
                declarations=declarations,
                encoding_hint="utf-8",
            )
        ],
    )
    for i in range(2):
        external.commit_external_chapter(
            workspace, _action(workspace, index=i, operation=f"op-admit-{i}"), AT
        )
    assert len(workspace.read("chapter_sources")["payload"]["sources"]) == 1
    assert [c["text"] for c in chapter_workspace.read_c1_current_views(workspace)] == [
        a,
        b,
    ]


def test_exact_replay_is_read_only_and_can_survive_later_m1_manifest(setup):
    _, workspace, runtime = setup
    _persist(workspace)
    action = _action(workspace)
    first = external.commit_external_chapter(workspace, action, AT)
    _persist(workspace, texts=("第二章 新材料\n信已寄出。",), operation="op-next-m1")
    before = _tree(runtime)
    replay = external.commit_external_chapter(workspace, action, AT)
    assert replay["replayed"] is True
    assert replay["chapter_revision_ref"] == first["chapter_revision_ref"]
    assert (
        external.resolve_external_admission(workspace, action["operation_id"])[
            "chapter"
        ]["text"]
        == TEXT
    )
    assert _tree(runtime) == before
    changed = {**action, "chapter_title": "另一标题"}
    with pytest.raises(
        external.ExternalChapterAdmissionError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        external.commit_external_chapter(workspace, changed, AT)
    assert _tree(runtime) == before
    # A different upload remains admissible without dropping the frozen first source.
    second = external.commit_external_chapter(
        workspace, _action(workspace, operation="op-admit-2"), AT
    )
    assert second["chapter_id"] == "c02"


def test_same_material_under_new_operation_is_not_new_chapter(setup):
    _, workspace, runtime = setup
    _persist(workspace)
    external.commit_external_chapter(workspace, _action(workspace), AT)
    action = _action(workspace, operation="op-duplicate")
    before = _tree(runtime)
    with pytest.raises(
        external.ExternalChapterAdmissionError,
        match="EXTERNAL_MATERIAL_ALREADY_ADMITTED",
    ):
        external.commit_external_chapter(workspace, action, AT)
    assert _tree(runtime) == before


@pytest.mark.parametrize("role", [None, "INTRO"])
def test_unknown_and_non_chapter_are_not_admitted(setup, role):
    _, workspace, runtime = setup
    _persist(workspace, role=role)
    preview = external.preview_external_chapters(workspace)
    assert preview["candidates"][0]["eligible"] is False
    before = _tree(runtime)
    with pytest.raises(
        external.ExternalChapterAdmissionError, match="C10_NOT_CONFIRMED_CHAPTER"
    ):
        external.commit_external_chapter(workspace, _action(workspace), AT)
    assert _tree(runtime) == before


def test_multi_chapter_material_is_rejected_without_changing_boundaries(setup):
    _, workspace, runtime = setup
    _persist(workspace, texts=("第一章 雨夜\n林乔拆信。\n第二章 天明\n守门人离开。",))
    preview = external.preview_external_chapters(workspace)
    assert (
        preview["candidates"][0]["reason"] == "EXTERNAL_MATERIAL_REQUIRES_CHAPTER_SPLIT"
    )
    before = _tree(runtime)
    with pytest.raises(
        external.ExternalChapterAdmissionError,
        match="EXTERNAL_MATERIAL_REQUIRES_CHAPTER_SPLIT",
    ):
        external.commit_external_chapter(workspace, _action(workspace), AT)
    assert _tree(runtime) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("chapter_title", ""),
        ("chapter_title", " title "),
        ("operation_id", "../../bad"),
        ("actor", "MODEL"),
        ("intent", "REPLACE"),
        ("version", "v2"),
        ("identity_revision_no", True),
        ("expected_next_chapter_number", False),
        ("expected_m1_state", {}),
        ("expected_m1_state", {"input_manifest": None, "module_state": None}),
    ],
)
def test_malformed_actions_do_not_touch_state(setup, field, value):
    _, workspace, runtime = setup
    _persist(workspace)
    action = _action(workspace)
    action[field] = value
    before = _tree(runtime)
    with pytest.raises(ValueError):
        external.commit_external_chapter(workspace, action, AT)
    assert _tree(runtime) == before


@pytest.mark.parametrize(
    "extra", ["text", "path", "author_id", "project_id", "lane", "work_ref"]
)
def test_action_cannot_supply_body_path_or_identity(setup, extra):
    _, workspace, runtime = setup
    _persist(workspace)
    action = {**_action(workspace), extra: "caller supplied"}
    before = _tree(runtime)
    with pytest.raises(
        external.ExternalChapterAdmissionError, match="ACTION_FIELDS_INVALID"
    ):
        external.commit_external_chapter(workspace, action, AT)
    assert _tree(runtime) == before


@pytest.mark.parametrize("bad", [None, [], "bad", 7])
def test_non_object_action_and_unbound_handle_fail(setup, bad):
    _, workspace, runtime = setup
    before = _tree(runtime)
    with pytest.raises(
        external.ExternalChapterAdmissionError, match="ACTION_FIELDS_INVALID"
    ):
        external.commit_external_chapter(workspace, bad, AT)
    with pytest.raises(
        external.ExternalChapterAdmissionError, match="AUTHOR_WORKSPACE_HANDLE_REQUIRED"
    ):
        external.commit_external_chapter(Path("/tmp/unbound"), {}, AT)
    assert _tree(runtime) == before
    assert list(inspect.signature(external.commit_external_chapter).parameters) == [
        "workspace",
        "action",
        "committed_at",
    ]


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("material_unit_id", "MU-NOT-FOUND", "EXTERNAL_MATERIAL_NOT_FOUND"),
        ("identity_revision_no", 2, "EXTERNAL_C10_REVISION_STALE"),
        ("expected_next_chapter_number", 2, "EXTERNAL_CHAPTER_ALLOCATOR_CHANGED"),
    ],
)
def test_wrong_selection_has_no_writes(setup, field, value, error):
    _, workspace, runtime = setup
    _persist(workspace)
    action = {**_action(workspace), field: value}
    before = _tree(runtime)
    with pytest.raises(external.ExternalChapterAdmissionError, match=error):
        external.commit_external_chapter(workspace, action, AT)
    assert _tree(runtime) == before


def test_stale_m1_reference_is_rejected(setup):
    _, workspace, runtime = setup
    _persist(workspace)
    action = _action(workspace)
    _persist(workspace, texts=("第二章 天明\n另一材料。",), operation="op-new-m1")
    before = _tree(runtime)
    with pytest.raises(
        external.ExternalChapterAdmissionError, match="EXTERNAL_M1_STATE_STALE"
    ):
        external.commit_external_chapter(workspace, action, AT)
    assert _tree(runtime) == before


@pytest.mark.parametrize(
    "corruption", ["decoded", "source_sha", "slice_sha", "span", "duplicate"]
)
def test_saved_material_must_replay_from_raw_and_exact_span(setup, corruption):
    _, workspace, runtime = setup
    _persist(workspace)
    action = _action(workspace)

    def corrupt(state):
        if corruption == "decoded":
            state["sources"][0]["decoded_text"] += "被篡改"
        elif corruption == "source_sha":
            state["sources"][0]["source_sha256"] = "0" * 64
        elif corruption == "slice_sha":
            state["material_units"][0]["source_ref"]["slice_sha256"] = "0" * 64
        elif corruption == "span":
            state["material_units"][0]["source_ref"]["end"] += 999
        else:
            state["material_units"].append(copy.deepcopy(state["material_units"][0]))

    _mutate_m1(workspace, corrupt)
    action["expected_m1_state"] = ingest_workspace.read_persisted_m1_state(workspace)[
        "state_identity"
    ]
    before = _tree(runtime)
    with pytest.raises(external.ExternalChapterAdmissionError):
        external.commit_external_chapter(workspace, action, AT)
    assert _tree(runtime) == before


def test_current_identity_revision_is_preserved_not_reset(setup):
    _, workspace, _ = setup
    _persist(workspace)

    def revise(state):
        record = state["material_units"][0]
        revision = copy.deepcopy(record["identity_revisions"][0])
        revision.update(revision_no=2, reason="重新确认用途", recorded_at=AT)
        record["identity_revisions"].append(revision)

    _mutate_m1(workspace, revise)
    action = _action(workspace)
    assert action["identity_revision_no"] == 2
    external.commit_external_chapter(workspace, action, AT)
    resolved = external.resolve_external_admission(workspace, action["operation_id"])
    assert (
        resolved["ledger"]["revisions"][0]["origin_material_ref"][
            "identity_revision_no"
        ]
        == 2
    )
    assert len(resolved["material"]["identity_revisions"]) == 2


def test_m1_race_at_atomic_commit_rejects_all_chapter_writes(setup, monkeypatch):
    _, workspace, _ = setup
    _persist(workspace)
    action = _action(workspace)
    original = workspace.commit_guarded

    def race(operation, mutations, expected, guards):
        _persist(workspace, texts=("第二章 天明\n新上传。",), operation="op-racing-m1")
        return original(operation, mutations, expected, guards)

    monkeypatch.setattr(workspace, "commit_guarded", race)
    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        external.commit_external_chapter(workspace, action, AT)
    assert all(value is None for value in _states(workspace).values())


def test_concurrent_admission_cannot_duplicate_allocator(setup, monkeypatch):
    _, workspace, _ = setup
    _persist(workspace, texts=(TEXT, "第二章 天明\n守门人离开。"))
    first = _action(workspace)
    racing = _action(workspace, index=1, operation="op-racing-admit")
    original = workspace.commit_guarded

    def race(operation, mutations, expected, guards):
        monkeypatch.setattr(workspace, "commit_guarded", original)
        external.commit_external_chapter(workspace, racing, AT)
        return original(operation, mutations, expected, guards)

    monkeypatch.setattr(workspace, "commit_guarded", race)
    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        external.commit_external_chapter(workspace, first, AT)
    chapters = chapter_workspace.read_c1_current_views(workspace)
    assert len(chapters) == 1 and chapters[0]["id"] == "c01"
    assert chapters[0]["text"].startswith("第二章")


@pytest.mark.parametrize(
    "point,committed", [("after_prepare", False), ("after_pointer_swap", True)]
)
def test_crash_recovery_is_entire_before_or_after(setup, point, committed):
    router, workspace, _ = setup
    _persist(workspace)
    action = _action(workspace)

    def crash(actual):
        if actual == point:
            raise InjectedWorkspaceCrash(actual)

    router._set_failure_hook_for_testing(crash)
    with pytest.raises(InjectedWorkspaceCrash, match=point):
        external.commit_external_chapter(workspace, action, AT)
    router._set_failure_hook_for_testing(None)
    workspace.recover()
    assert all(value is not None for value in _states(workspace).values()) is committed
    replay = external.commit_external_chapter(workspace, action, AT)
    assert replay["chapter_id"] == "c01"
    assert replay["replayed"] is committed


def test_legacy_current_views_are_not_silently_migrated(setup):
    _, workspace, runtime = setup
    m1 = _persist(workspace)
    action = _action(workspace)
    workspace.commit("op-legacy-c1", {"chapters": m1["chapters"]}, {"chapters": 0})
    before = _tree(runtime)
    with pytest.raises(
        initial.ChapterInitialAdmissionError, match="CHAPTER_ADMISSION_STATE_PARTIAL"
    ):
        external.commit_external_chapter(workspace, action, AT)
    assert _tree(runtime) == before


def _author_work(workspace, slot="S-0001", expected=0):
    work_draft_workspace.save_current_work_draft(
        workspace,
        {
            "operation_id": f"op-work-{slot}",
            "slot_ref": slot,
            "source_outline_ref": f"{slot}@outline-r1",
            "expected_rev": expected,
            "entry_mode": "typed",
            "author_text": f"作者自写{slot}。",
        },
    )
    draft = workspace.read("draft")["payload"]
    return {
        "contract": "WORK_DRAFT_HANDOVER_ACTION",
        "version": "v2",
        "operation_id": f"op-author-{slot}",
        "actor": "author",
        "intent": "adopt_as_manuscript",
        "work_ref": draft["work_ref"],
        "work_rev": draft["work_rev"],
        "slot_ref": slot,
        "source_outline_ref": f"{slot}@outline-r1",
        "chapter_title": "作者章节",
        "target_contract": "C1_CHAPTER_DOC",
        "target_planstore_result": "handover_parts",
    }


@pytest.mark.parametrize("author_first", [True, False])
def test_author_work_and_external_sources_coexist_without_identity_leak(
    setup, author_first
):
    _, workspace, runtime = setup
    _persist(workspace)
    author = _author_work(workspace)
    if author_first:
        initial.commit_initial_work_draft(workspace, author, AT)
    ext_action = _action(workspace)
    external.commit_external_chapter(workspace, ext_action, AT)
    if not author_first:
        initial.commit_initial_work_draft(workspace, author, AT)
    ext = external.resolve_external_admission(workspace, ext_action["operation_id"])
    own = initial.resolve_initial_admission(workspace, author["operation_id"])
    assert {ext["chapter_id"], own["chapter_id"]} == {"c01", "c02"}
    assert ext["chapter"]["text"] == TEXT
    assert own["chapter"]["text"] == "作者自写S-0001。"
    assert own["status"] == "AW_COMMITTED_PLANSTORE_PENDING"
    before = _tree(runtime)
    with pytest.raises(
        initial.ChapterInitialAdmissionError, match="WORK_DRAFT_ADMISSION_REQUIRED"
    ):
        initial.resolve_initial_admission(workspace, ext_action["operation_id"])
    with pytest.raises(
        external.ExternalChapterAdmissionError, match="EXTERNAL_ADMISSION_NOT_FOUND"
    ):
        external.resolve_external_admission(workspace, author["operation_id"])
    assert _tree(runtime) == before
    assert initial.commit_initial_work_draft(workspace, author, AT)["replayed"] is True


def test_existing_author_plan_handover_still_works_with_external_chapter(setup):
    _, workspace, runtime = setup
    _persist(workspace)
    ext_action = _action(workspace)
    external.commit_external_chapter(workspace, ext_action, AT)
    author = _author_work(workspace)
    initial.commit_initial_work_draft(workspace, author, AT)
    # Use the same minimal public plan shape as the existing author handover contract.
    plan = {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-TEST", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "goal": "拆信",
                "summary": "拆信",
                "entry_state": "未拆",
                "storyline_refs": [],
                "scene_refs": [],
                "exit_condition": "已拆",
                "exit_hook": "下封信",
                "must_not": [],
                "risks": [],
                "target_length": 1000,
                "outline_checkpoint": {
                    "outline_rev": 1,
                    "source_slot_ref": "S-0001",
                    "source_commit_seq": 1,
                },
                "slot_status": "planned",
                "handover_parts": [],
                "truth_bearing": "primary",
                "rev": 1,
            }
        ],
        **{
            key: []
            for key in (
                "scenes",
                "events",
                "storylines",
                "hooks",
                "widgets",
                "pins",
                "must_carries",
                "option_records",
                "slot_mappings",
                "reconciliation_edges",
            )
        },
        "stop_points": {},
        "id_counters": {"MAP": 0, "RE": 0},
    }
    plan_workspace.save_plan(workspace, "op-plan", plan, 0)
    before = _tree(runtime)
    with pytest.raises(
        chapter_handover_workspace.ChapterHandoverWorkspaceError,
        match="CHAPTER_ADMISSION_STAGE_INVALID",
    ):
        chapter_handover_workspace.complete_pending_handover(
            workspace, ext_action["operation_id"], "op-wrong-plan", AT
        )
    assert _tree(runtime) == before
    result = chapter_handover_workspace.complete_pending_handover(
        workspace, author["operation_id"], "op-own-plan", AT
    )
    assert result["mapping"]["chapter_id"] == "c02"
    assert (
        external.resolve_external_admission(workspace, ext_action["operation_id"])[
            "chapter"
        ]["text"]
        == TEXT
    )


def test_corrupted_frozen_source_is_rejected_on_reopen(setup):
    _, workspace, runtime = setup
    _persist(workspace)
    action = _action(workspace)
    external.commit_external_chapter(workspace, action, AT)
    entry = workspace.read("chapter_sources")
    changed = copy.deepcopy(entry["payload"])
    next(iter(changed["sources"].values()))["decoded_text"] += "不可冒充原文"
    workspace.commit(
        "op-corrupt-frozen",
        {"chapter_sources": changed},
        {"chapter_sources": entry["version"]},
    )
    before = _tree(runtime)
    with pytest.raises(
        initial.ChapterInitialAdmissionError, match="EXTERNAL_SOURCE_INVALID"
    ):
        external.resolve_external_admission(workspace, action["operation_id"])
    assert _tree(runtime) == before


@pytest.mark.parametrize("encoding", ["gb18030", "utf-8-sig"])
def test_raw_encoding_and_decoded_text_are_both_preserved(setup, encoding):
    _, workspace, _ = setup
    raw = TEXT.encode(encoding)
    _persist(
        workspace, uploads=[UploadSource("source.txt", raw, encoding_hint=encoding)]
    )
    action = _action(workspace)
    external.commit_external_chapter(workspace, action, AT)
    source = next(
        iter(workspace.read("chapter_sources")["payload"]["sources"].values())
    )
    assert base64.b64decode(source["original_bytes_base64"]) == raw
    assert (
        external.resolve_external_admission(workspace, action["operation_id"])[
            "chapter"
        ]["text"]
        == TEXT
    )


def test_raw_blob_corruption_cannot_be_hidden_by_saved_decoded_text(setup):
    _, workspace, runtime = setup
    _persist(workspace)
    action = _action(workspace)
    blobs = [p for p in runtime.rglob("*.blob") if p.read_bytes() == TEXT.encode()]
    assert len(blobs) == 1
    blobs[0].write_bytes(TEXT.encode() + b"corrupted")
    before = _tree(runtime)
    with pytest.raises(IntegrityError, match="IMMUTABLE_BLOB_INTEGRITY_MISMATCH"):
        external.commit_external_chapter(workspace, action, AT)
    assert all(value is None for value in _states(workspace).values())
    assert _tree(runtime) == before


def test_repartitioning_source_cannot_duplicate_already_admitted_text(setup):
    _, workspace, runtime = setup
    raw = "林乔拆开了信。\n守门人转身离开。\n"

    def upload_at(cut):
        declarations = []
        for start, end in [(0, cut), (cut, len(raw))]:
            declaration = ingest._whole_source_declaration(end - start, "CHAPTER")
            declaration.update(start=start, end=end)
            declarations.append(declaration)
        return UploadSource(
            "source.txt", raw.encode(), declarations=declarations, encoding_hint="utf-8"
        )

    cut = raw.index("\n") + 1
    _persist(workspace, uploads=[upload_at(cut)])
    external.commit_external_chapter(workspace, _action(workspace), AT)
    _persist(workspace, operation="op-repartition", uploads=[upload_at(cut + 2)])
    action = _action(workspace, operation="op-overlap")
    before = _tree(runtime)
    with pytest.raises(
        external.ExternalChapterAdmissionError,
        match="EXTERNAL_MATERIAL_OVERLAPS_ADMITTED_CHAPTER",
    ):
        external.commit_external_chapter(workspace, action, AT)
    assert _tree(runtime) == before


def test_author_source_still_requires_the_entire_work_draft(setup):
    _, workspace, _ = setup
    action = _author_work(workspace)
    initial.commit_initial_work_draft(workspace, action, AT)
    payloads = copy.deepcopy(initial._read_bundle(workspace)["payloads"])
    source = next(iter(payloads["chapter_sources"]["sources"].values()))
    material = next(iter(payloads["chapter_materials"]["records"].values()))
    chapter = payloads["chapters"][0]
    trimmed = source["decoded_text"][1:]
    trimmed_sha = hashlib.sha256(trimmed.encode()).hexdigest()
    material["source_ref"].update(start=1, slice_sha256=trimmed_sha)
    revision = payloads["chapter_revisions"]["ledgers"][chapter["id"]]["revisions"][0]
    revision.update(text_sha256=trimmed_sha, chars=len(trimmed))
    revision["content_ref"].update(start=1, slice_sha256=trimmed_sha)
    chapter["text"] = trimmed
    chapter["chapter_revision_ref"]["revision_text_sha256"] = trimmed_sha
    payloads["chapter_index"][0]["revision_text_sha256"] = trimmed_sha
    payloads["chapter_admission_operations"]["operations"][action["operation_id"]][
        "revision_text_sha256"
    ] = trimmed_sha
    # All C10/C11/C1 hashes now agree, but an author handover must not trim text.
    with pytest.raises(
        initial.ChapterInitialAdmissionError,
        match="CHAPTER_ADMISSION_OPERATION_REFERENCE_MISMATCH",
    ):
        initial._validated_payloads(payloads)
