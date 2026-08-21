from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import (
        chapter_fact_material_bundle_workspace,
        factstore,
        packer_fact_workspace,
        packer_tool,
        plan_workspace,
    )
    from mvp.workspace import WorkspaceRouter
finally:
    sys.path.pop(0)


NOW = "2026-08-20 10:00:00"
CHAPTER_TEXT = "林照已经拿到旧钥匙。许岚已经关上门。"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _option_record(
    record_id: str,
    *,
    event_ref: str,
    group_status: str = "active",
) -> dict:
    active = group_status == "active"
    return {
        "id": record_id,
        "slot_ref": "S-0001",
        "question": "下一章采用哪条未来计划？",
        "options": [
            {
                "key": "A",
                "summary": "采用当前计划",
                "why_fit": "符合当前规划",
                "changes": "推进下一章",
                "risks": "动机要写清",
                "digest_refs": [event_ref] if active else [],
            },
            {
                "key": "B",
                "summary": "未采用方案",
                "why_fit": "只是候选",
                "changes": "不落位",
                "risks": "不应进入供料",
                "digest_refs": [],
            },
        ],
        "chosen_key": "A" if active else None,
        "decided_by": "author",
        "decided_at": NOW,
        "digest_applied": [event_ref] if active else [],
        "variant_note": None,
        "card_ref": "AC-0001",
        "recommended_key": "B",
        "group_status": group_status,
        "source_identity": "author_declared",
        "created_at": NOW,
        "updated_at": NOW,
        "rev": 1,
        "note": "未来计划选择记录",
    }


def _event(
    event_ref: str,
    *,
    text: str,
    digest_status: str,
    digest_ref: str | None,
    rev: int,
) -> dict:
    return {
        "id": event_ref,
        "scene_ref": "SCN-0001",
        "text": text,
        "storyline_ref": "L-0001",
        "purpose": "advance",
        "hook_links": [],
        "story_time_hint": "下一章雨夜",
        "digest_status": digest_status,
        "digest_ref": digest_ref,
        "origin_ref": "AC-0001",
        "repair_ref": None,
        "deviation_note": None,
        "defer_count": 0,
        "truth_bearing": "primary",
        "prose_status": "unwritten",
        "prose_basis": None,
        "impact": "normal",
        "source_identity": "author_declared",
        "created_at": NOW,
        "updated_at": NOW,
        "rev": rev,
        "note": "",
    }


def _plan() -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-M11-BUNDLE", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "goal": "规划下一章的送信决定",
                "summary": "这些都是未来计划，不是已经发生的事实",
                "entry_state": "双方仍互不信任",
                "storyline_refs": ["L-0001"],
                "scene_refs": ["SCN-0001"],
                "exit_condition": "林照决定送信",
                "exit_hook": "寄件人身份未知",
                "must_not": ["不得把未来计划写成已发生事实"],
                "risks": ["动机需要写清"],
                "target_length": 1200,
                "outline_checkpoint": {
                    "outline_rev": 3,
                    "source_slot_ref": "S-0001",
                    "source_commit_seq": 8,
                },
                "slot_status": "planned",
                "handover_parts": [],
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 2,
            }
        ],
        "scenes": [
            {
                "id": "SCN-0001",
                "slot_ref": "S-0001",
                "goal": "下一章完成密封信交接",
                "summary": "许岚计划在雨巷交信",
                "location": "纸灯巷口",
                "characters": ["CH-0001", "CH-0002"],
                "pe_refs": ["PE-0001", "PE-PENDING", "PE-VOIDED"],
                "mood_in": "戒备",
                "mood_out": "试探",
                "visual_hint": "雨水打碎纸灯倒影",
                "dialogue_hints": ["只透露天亮前必须送达"],
                "resistance": "双方不肯说明来源",
                "turn": "许岚计划交出密封信",
                "pov": "CH-0001",
                "spoiler_notes": ["不得展示信内页"],
                "word_estimate": 1200,
                "truth_bearing": "primary",
                "updated_at": NOW,
                "rev": 4,
            }
        ],
        "events": [
            _event(
                "PE-0001",
                text="许岚计划在下一章把密封信交给林照",
                digest_status="digested",
                digest_ref="OPT-0001",
                rev=5,
            ),
            _event(
                "PE-PENDING",
                text="未选择候选未来计划绝不能进入供料",
                digest_status="pending",
                digest_ref=None,
                rev=1,
            ),
            _event(
                "PE-VOIDED",
                text="被作废的未来计划绝不能进入供料",
                digest_status="voided",
                digest_ref="OPT-VOIDED",
                rev=2,
            ),
        ],
        "storylines": [
            {
                "id": "L-0001",
                "name": "密封信去向",
                "alias": "送信线",
                "priority": 1,
                "members": ["CH-0001", "CH-0002"],
                "line_status": "active",
                "rev": 2,
            }
        ],
        "hooks": [],
        "widgets": [],
        "pins": [],
        "must_carries": [],
        "option_records": [
            _option_record("OPT-0001", event_ref="PE-0001"),
            _option_record(
                "OPT-VOIDED",
                event_ref="PE-VOIDED",
                group_status="discarded",
            ),
        ],
        "slot_mappings": [],
        "reconciliation_edges": [],
        "stop_points": {},
        "id_counters": {"MAP": 0, "RE": 0},
    }


def _revision_ref(*, chapter_text: str = CHAPTER_TEXT) -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": 1,
        "revision_text_sha256": _sha(chapter_text),
    }


def _fact(
    fact_id: str,
    quote: str,
    *,
    status: str = "confirmed",
    chapter_text: str = CHAPTER_TEXT,
) -> dict:
    ref = _revision_ref(chapter_text=chapter_text)
    start = chapter_text.index(quote)
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": "c01",
        "text": f"已经发生：{quote}",
        "quote": quote,
        "status": status,
        "source": "M11_BUNDLE_SYNTHETIC",
        "note": "",
        "added_at": NOW,
        "seg": 1,
        "decided_at": NOW,
        "chapter_revision_ref": ref,
        "anchor_ref": {
            **ref,
            "coordinate_basis": factstore.ANCHOR_COORDINATE_BASIS,
            "start": start,
            "end": start + len(quote),
            "slice_sha256": _sha(quote),
        },
        "anchor_state": "VERIFIED",
        "recheck": None,
    }


def _material(
    fact_id: str,
    *,
    tokens: int = 20,
    obligation: str = "HARD",
) -> dict:
    return {
        "material_identity": packer_fact_workspace.MATERIAL_IDENTITY,
        "id": fact_id,
        "estimated_tokens": tokens,
        "actuality_class": "CURRENT_FACT_OR_STATE",
        "obligation_tier": obligation,
        "selection_rank": None if obligation == "HARD" else 1,
        "task_relation": "这是章事实稿需要的已发生事实",
        "recall_disposition": "RETRIEVABLE",
        "unresolved_reason": None,
    }


def _request(*materials: dict, budget: int = 100) -> dict:
    return {
        "task_id": "M11-CHAPTER-FACT-MATERIAL-BUNDLE",
        "task_actuality_scope": "CURRENT_TRUTH_REQUIRED",
        "budget_tokens": budget,
        "token_estimator": {
            "identity": packer_tool.ESTIMATOR_IDENTITY,
            "estimates": {
                material["id"]: material["estimated_tokens"]
                for material in materials
            },
        },
        "candidate_materials": list(materials),
    }


def _workspace(
    tmp_path: Path,
    *,
    principal: str = "auth:alice",
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project(principal, "M11 组合供料项目")
    plan_workspace.save_plan(workspace, f"op-plan-{principal}", _plan(), 0)
    facts = [
        _fact("f001", "林照已经拿到旧钥匙。"),
        _fact("f002", "许岚已经关上门。", status="extracted"),
    ]
    workspace.commit(
        f"op-facts-{principal}",
        {"facts": facts, "chapter_index": [_revision_ref()]},
        {"facts": 0, "chapter_index": 0},
    )
    return runtime_root, router, workspace


def _inventory(root: Path) -> list[tuple[str, bool, bytes | None]]:
    return [
        (
            str(path.relative_to(root)),
            path.is_dir(),
            None if path.is_dir() else path.read_bytes(),
        )
        for path in sorted(root.rglob("*"))
    ]


def test_stable_bundle_keeps_current_facts_and_future_planning_separate(
    tmp_path: Path,
) -> None:
    runtime_root, _, workspace = _workspace(tmp_path)
    before = _inventory(runtime_root)

    result = chapter_fact_material_bundle_workspace.execute(
        workspace,
        "S-0001",
        _request(_material("f001")),
    )

    assert result["current_fact_pack"]["decision_state"] == "READY"
    assert [
        row["fact"]["id"] for row in result["current_fact_pack"]["loaded_facts"]
    ] == ["f001"]
    assert "f002" not in json.dumps(
        result["current_fact_pack"], ensure_ascii=False, sort_keys=True
    )
    assert [
        row["id"] for row in result["planning_supply"]["future_event_materials"]
    ] == ["PE-0001"]
    text = json.dumps(result, ensure_ascii=False, sort_keys=True)
    assert "未选择候选未来计划绝不能进入供料" not in text
    assert "被作废的未来计划绝不能进入供料" not in text
    assert "许岚计划在下一章把密封信交给林照" not in json.dumps(
        result["current_fact_pack"], ensure_ascii=False
    )
    assert "林照已经拿到旧钥匙" not in json.dumps(
        result["planning_supply"], ensure_ascii=False
    )
    assert chapter_fact_material_bundle_workspace.validate_result(result) == result
    assert _inventory(runtime_root) == before


@pytest.mark.parametrize("status", ["extracted", "rejected"])
def test_non_confirmed_fact_cannot_enter_combined_bundle(
    tmp_path: Path,
    status: str,
) -> None:
    runtime_root, _, workspace = _workspace(tmp_path)
    facts = workspace.read("facts")
    blocked = _fact("f002", "许岚已经关上门。", status=status)
    workspace.commit(
        f"op-set-{status}",
        {"facts": [facts["payload"][0], blocked]},
        {"facts": facts["version"]},
    )
    before = _inventory(runtime_root)

    with pytest.raises(
        chapter_fact_material_bundle_workspace.ChapterFactMaterialBundleWorkspaceError,
        match=f"FACT_NOT_CONFIRMED:{status.upper()}",
    ):
        chapter_fact_material_bundle_workspace.execute(
            workspace, "S-0001", _request(_material("f002"))
        )

    assert _inventory(runtime_root) == before


def test_restart_returns_byte_stable_bundle_without_writes(tmp_path: Path) -> None:
    runtime_root, _, workspace = _workspace(tmp_path)
    request = _request(_material("f001"))
    expected = chapter_fact_material_bundle_workspace.execute(
        workspace, "S-0001", request
    )
    before = _inventory(runtime_root)
    child = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from mvp.chapter_fact_material_bundle_workspace import execute
from mvp.workspace import WorkspaceRouter
workspace = WorkspaceRouter(sys.argv[2]).open_project(sys.argv[3], sys.argv[4])
value = execute(workspace, sys.argv[5], json.loads(sys.argv[6]))
sys.stdout.buffer.write((json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(\",\", \":\")) + \"\\n\").encode(\"utf-8\"))
"""

    reopened = subprocess.run(
        [
            sys.executable,
            "-c",
            child,
            str(PRODUCT_ROOT),
            str(runtime_root),
            "auth:alice",
            workspace.project_id,
            "S-0001",
            json.dumps(request, ensure_ascii=False),
        ],
        capture_output=True,
        check=True,
    )

    assert reopened.stdout == _canonical_bytes(expected)
    assert _inventory(runtime_root) == before


def test_non_ready_fact_pack_returns_no_partial_bundle(tmp_path: Path) -> None:
    runtime_root, _, workspace = _workspace(tmp_path)
    before = _inventory(runtime_root)
    second = _fact("f003", "许岚已经关上门。")
    facts = workspace.read("facts")
    workspace.commit(
        "op-add-second-confirmed-fact",
        {"facts": [facts["payload"][0], second]},
        {"facts": facts["version"]},
    )
    before = _inventory(runtime_root)

    with pytest.raises(
        chapter_fact_material_bundle_workspace.ChapterFactMaterialBundleWorkspaceError,
        match="CURRENT_FACT_PACK_NOT_READY:STOP_HARD_BUDGET",
    ):
        chapter_fact_material_bundle_workspace.execute(
            workspace,
            "S-0001",
            _request(
                _material("f001", tokens=60),
                _material("f003", tokens=50),
                budget=100,
            ),
        )

    assert _inventory(runtime_root) == before


@pytest.mark.parametrize("source_key", ["plan", "facts", "chapter_index"])
def test_final_source_watermark_change_discards_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_key: str,
) -> None:
    runtime_root, _, workspace = _workspace(tmp_path)
    request = _request(_material("f001"))
    stable = chapter_fact_material_bundle_workspace.execute(
        workspace, "S-0001", request
    )["source_snapshots"]
    changed = copy.deepcopy(stable)
    changed[source_key]["version"] += 1
    snapshots = [stable, changed]
    before = _inventory(runtime_root)
    monkeypatch.setattr(
        chapter_fact_material_bundle_workspace,
        "_read_current_source_snapshots",
        lambda _workspace: copy.deepcopy(snapshots.pop(0)),
    )

    with pytest.raises(
        chapter_fact_material_bundle_workspace.ChapterFactMaterialBundleWorkspaceError,
        match="BUNDLE_SOURCE_CHANGED_DURING_ASSEMBLY",
    ):
        chapter_fact_material_bundle_workspace.execute(
            workspace, "S-0001", request
        )

    assert snapshots == []
    assert _inventory(runtime_root) == before


def test_path_and_cross_author_project_cannot_leak_materials(tmp_path: Path) -> None:
    runtime_root, router, alice = _workspace(tmp_path / "alice")
    alice_result = chapter_fact_material_bundle_workspace.execute(
        alice, "S-0001", _request(_material("f001"))
    )
    fake_path = tmp_path / "project"
    with pytest.raises(
        chapter_fact_material_bundle_workspace.ChapterFactMaterialBundleWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        chapter_fact_material_bundle_workspace.execute(
            fake_path, "S-0001", _request(_material("f001"))
        )
    assert not fake_path.exists()

    bob = router.create_project("auth:bob", "M11 乙项目")
    plan_workspace.save_plan(bob, "op-plan-bob", _plan(), 0)
    bob_text = "林照已经交出旧钥匙。许岚已经关上门。"
    bob_ref = _revision_ref(chapter_text=bob_text)
    bob_fact = _fact(
        "f001",
        "林照已经交出旧钥匙。",
        chapter_text=bob_text,
    )
    bob_fact["text"] = "乙项目独立事实"
    bob.commit(
        "op-facts-bob",
        {"facts": [bob_fact], "chapter_index": [bob_ref]},
        {"facts": 0, "chapter_index": 0},
    )
    bob_result = chapter_fact_material_bundle_workspace.execute(
        bob, "S-0001", _request(_material("f001"))
    )

    assert (
        alice_result["workspace_binding_sha256"]
        != bob_result["workspace_binding_sha256"]
    )
    assert "林照已经拿到旧钥匙" not in json.dumps(
        bob_result, ensure_ascii=False, sort_keys=True
    )
    assert "乙项目独立事实" not in json.dumps(
        alice_result, ensure_ascii=False, sort_keys=True
    )
    assert router.open_project("auth:alice", alice.project_id).project_id == alice.project_id
    assert runtime_root.exists()


def test_bundle_validator_rejects_tampering_and_bad_sha(tmp_path: Path) -> None:
    _, _, workspace = _workspace(tmp_path)
    result = chapter_fact_material_bundle_workspace.execute(
        workspace, "S-0001", _request(_material("f001"))
    )
    validated = chapter_fact_material_bundle_workspace.validate_result(result)
    validated["planning_supply"]["future_event_materials"][0]["text"] = "改副本"
    assert result["planning_supply"]["future_event_materials"][0]["text"] != "改副本"

    changed_role = copy.deepcopy(result)
    changed_role["content_roles"][
        "planning_supply"
    ] = "CURRENT_CONFIRMED_FACTS_ALREADY_OCCURRED"
    with pytest.raises(
        chapter_fact_material_bundle_workspace.ChapterFactMaterialBundleWorkspaceError,
        match="BUNDLE_CONTENT_ROLES_INVALID",
    ):
        chapter_fact_material_bundle_workspace.validate_result(changed_role)

    changed_supply = copy.deepcopy(result)
    changed_supply["planning_supply"]["future_event_materials"][0][
        "text"
    ] = "被篡改的未来计划"
    with pytest.raises(
        chapter_fact_material_bundle_workspace.ChapterFactMaterialBundleWorkspaceError,
        match="BUNDLE_SHA256_INVALID",
    ):
        chapter_fact_material_bundle_workspace.validate_result(changed_supply)
