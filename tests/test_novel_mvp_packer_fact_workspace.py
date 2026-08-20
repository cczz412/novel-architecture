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
    from mvp import factstore, packer_fact_workspace, packer_tool
    from mvp.workspace import ProjectNotFoundError, WorkspaceRouter
finally:
    sys.path.pop(0)


PRINCIPAL = "auth:m11-fact-author"
CHAPTER_TEXT = "甲拿起钥匙。乙关上门。丙点亮灯。"
UPDATED_TEXT = "甲把钥匙交给乙。乙关上门。丙点亮灯。"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_ref(
    *,
    text: str = CHAPTER_TEXT,
    revision_no: int = 1,
) -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": revision_no,
        "revision_text_sha256": _sha(text),
    }


def _fact(
    fact_id: str,
    quote: str,
    *,
    status: str = "confirmed",
    revision_text: str = CHAPTER_TEXT,
    revision_no: int = 1,
    anchor_state: str = "VERIFIED",
) -> dict:
    revision_ref = _revision_ref(text=revision_text, revision_no=revision_no)
    start = revision_text.index(quote) if quote in revision_text else 0
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": "c01",
        "text": f"事实句：{quote}",
        "quote": quote,
        "status": status,
        "source": "M11_CURRENT_FACT_SYNTHETIC_FIXTURE",
        "note": "",
        "added_at": "2026-08-20 10:00:00",
        "seg": 1,
        "decided_at": "2026-08-20 10:01:00",
        "chapter_revision_ref": revision_ref,
        "anchor_ref": (
            {
                **revision_ref,
                "coordinate_basis": factstore.ANCHOR_COORDINATE_BASIS,
                "start": start,
                "end": start + len(quote),
                "slice_sha256": _sha(quote),
            }
            if anchor_state == "VERIFIED"
            else None
        ),
        "anchor_state": anchor_state,
        "recheck": (
            {
                "previous_status": "confirmed",
                "reason": "evidence_gone",
                "from_revision_no": 1,
                "target_revision_no": 2,
                "flagged_at": "2026-08-20 10:02:00",
            }
            if status == "needs_recheck"
            else None
        ),
    }


def _material(
    fact_id: str,
    *,
    tokens: int,
    obligation: str = "MAY",
    rank: int | None = 1,
    actuality: str = "CURRENT_FACT_OR_STATE",
    recall: str = "RETRIEVABLE",
    unresolved_reason: str | None = None,
) -> dict:
    return {
        "material_identity": packer_fact_workspace.MATERIAL_IDENTITY,
        "id": fact_id,
        "estimated_tokens": tokens,
        "actuality_class": actuality,
        "obligation_tier": obligation,
        "selection_rank": rank,
        "task_relation": f"{fact_id} 是本章任务需要的当前事实",
        "recall_disposition": recall,
        "unresolved_reason": unresolved_reason,
    }


def _request(*materials: dict, budget: int = 100) -> dict:
    return {
        "task_id": "M11-CURRENT-FACT-SYNTHETIC",
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


def _hard(fact_id: str, tokens: int) -> dict:
    return _material(
        fact_id,
        tokens=tokens,
        obligation="HARD",
        rank=None,
    )


def _open_workspace(tmp_path: Path, *, principal: str = PRINCIPAL):
    tmp_path.mkdir(parents=True, exist_ok=True)
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project(principal, "M11 C4 合成项目")
    return runtime_root, router, workspace


def _commit_sources(
    workspace,
    facts: list[dict],
    *,
    current_ref: dict | None = None,
    operation_id: str = "op-m11-current-fact-sources",
) -> dict:
    return workspace.commit(
        operation_id,
        {
            "facts": facts,
            "chapter_index": [current_ref or _revision_ref()],
        },
        {"facts": 0, "chapter_index": 0},
    )


def _inventory(root: Path) -> list[tuple[str, bool, bytes | None]]:
    return [
        (
            str(path.relative_to(root)),
            path.is_dir(),
            None if path.is_dir() else path.read_bytes(),
        )
        for path in sorted(root.rglob("*"))
    ]


def _ready_pack(workspace) -> tuple[dict, dict, dict]:
    first = _fact("f001", "甲拿起钥匙。")
    second = _fact("f002", "乙关上门。")
    _commit_sources(workspace, [first, second])
    result = packer_fact_workspace.execute(
        workspace,
        _request(_hard("f001", 60), _material("f002", tokens=50), budget=70),
    )
    return result, first, second


def test_loads_current_confirmed_fact_content_and_recalls_omission_without_writes(
    tmp_path: Path,
) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    first = _fact("f001", "甲拿起钥匙。")
    second = _fact("f002", "乙关上门。")
    receipt = _commit_sources(workspace, [first, second])
    before = _inventory(runtime_root)

    result = packer_fact_workspace.execute(
        workspace,
        _request(_hard("f001", 60), _material("f002", tokens=50), budget=70),
    )

    assert result["decision_state"] == "READY"
    assert result["source_snapshots"] == {
        "facts": {
            "version": receipt["versions"]["facts"],
            "sha256": receipt["payload_sha256"]["facts"],
        },
        "chapter_index": {
            "version": receipt["versions"]["chapter_index"],
            "sha256": receipt["payload_sha256"]["chapter_index"],
        },
    }
    assert result["m11_result"]["budget"]["used_tokens"] == 60
    assert result["loaded_facts"] == [
        {
            "material_identity": "CURRENT_CONFIRMED_FACT",
            "fact": first,
            "why_loaded": "HARD 保底义务；f001 是本章任务需要的当前事实",
        }
    ]
    assert result["omitted_fact_index"] == [
        {
            "material_identity": "CURRENT_CONFIRMED_FACT",
            "fact_id": "f002",
            "reason": "BUDGET_OPTIONAL_DEFERRED",
            "recall_disposition": "RETRIEVABLE",
            "recall_handle": "c4-current://f002",
        }
    ]
    recalled = packer_fact_workspace.recall_omitted(
        workspace,
        result,
        "c4-current://f002",
    )
    assert recalled["fact"] == second
    assert recalled["omission_reason"] == "BUDGET_OPTIONAL_DEFERRED"
    assert _inventory(runtime_root) == before

    result["loaded_facts"][0]["fact"]["text"] = "调用方篡改返回值"
    assert workspace.read("facts")["payload"] == [first, second]


def test_unrequested_ineligible_fact_is_excluded_but_cannot_become_candidate(
    tmp_path: Path,
) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    current = _fact("f001", "甲拿起钥匙。")
    extracted = _fact("f002", "乙关上门。", status="extracted")
    _commit_sources(workspace, [current, extracted])
    before = _inventory(runtime_root)

    result = packer_fact_workspace.execute(
        workspace,
        _request(_hard("f001", 20), budget=100),
    )

    assert result["decision_state"] == "READY"
    assert [row["fact"]["id"] for row in result["loaded_facts"]] == ["f001"]
    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="CURRENT_FACT_INELIGIBLE:f002:FACT_NOT_CONFIRMED:EXTRACTED",
    ):
        packer_fact_workspace.execute(
            workspace,
            _request(_hard("f002", 20), budget=100),
        )
    assert _inventory(runtime_root) == before


@pytest.mark.parametrize(
    ("fact", "error"),
    [
        (_fact("f001", "甲拿起钥匙。", status="extracted"), "EXTRACTED"),
        (_fact("f001", "甲拿起钥匙。", status="rejected"), "REJECTED"),
        (
            _fact("f001", "甲拿起钥匙。", status="needs_recheck"),
            "NEEDS_RECHECK",
        ),
        (
            _fact(
                "f001",
                "甲拿起钥匙。",
                anchor_state="LEGACY_UNVERIFIED",
            ),
            "FACT_EVIDENCE_NOT_VERIFIED",
        ),
    ],
)
def test_ineligible_fact_kinds_fail_closed_without_writes(
    tmp_path: Path,
    fact: dict,
    error: str,
) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    _commit_sources(workspace, [fact])
    before = _inventory(runtime_root)

    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match=error,
    ):
        packer_fact_workspace.execute(
            workspace,
            _request(_hard("f001", 20), budget=100),
        )

    assert _inventory(runtime_root) == before


def test_bad_anchor_and_old_revision_fail_closed_without_writes(tmp_path: Path) -> None:
    bad_root = tmp_path / "bad"
    runtime_root, _, bad_workspace = _open_workspace(bad_root)
    bad_anchor = _fact("f001", "甲拿起钥匙。")
    bad_anchor["anchor_ref"]["slice_sha256"] = "0" * 64
    _commit_sources(bad_workspace, [bad_anchor])
    before_bad = _inventory(runtime_root)
    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="CURRENT_FACT_SOURCE_INVALID",
    ):
        packer_fact_workspace.execute(
            bad_workspace,
            _request(_hard("f001", 20), budget=100),
        )
    assert _inventory(runtime_root) == before_bad

    stale_root = tmp_path / "stale"
    runtime_root, _, stale_workspace = _open_workspace(stale_root)
    stale = _fact("f001", "甲拿起钥匙。")
    _commit_sources(
        stale_workspace,
        [stale],
        current_ref=_revision_ref(text=UPDATED_TEXT, revision_no=2),
    )
    before_stale = _inventory(runtime_root)
    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="CURRENT_FACT_STALE_REVISION:f001",
    ):
        packer_fact_workspace.execute(
            stale_workspace,
            _request(_hard("f001", 20), budget=100),
        )
    assert _inventory(runtime_root) == before_stale


def test_source_change_during_pack_discards_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    _commit_sources(workspace, [_fact("f001", "甲拿起钥匙。")])
    before = _inventory(runtime_root)
    real_read = packer_fact_workspace.fact_workspace.read_current_snapshot
    stable = real_read(workspace)
    changed = copy.deepcopy(stable)
    changed["facts_snapshot"]["version"] += 1
    calls = 0

    def drifting_read(_workspace):
        nonlocal calls
        calls += 1
        return copy.deepcopy(stable if calls == 1 else changed)

    monkeypatch.setattr(
        packer_fact_workspace.fact_workspace,
        "read_current_snapshot",
        drifting_read,
    )

    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="CURRENT_FACT_SOURCE_CHANGED_DURING_PACK",
    ):
        packer_fact_workspace.execute(
            workspace,
            _request(_hard("f001", 20), budget=100),
        )
    assert _inventory(runtime_root) == before


def test_hard_budget_and_unresolved_stop_do_not_leak_fact_content(
    tmp_path: Path,
) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    facts = [
        _fact("f001", "甲拿起钥匙。"),
        _fact("f002", "乙关上门。"),
    ]
    _commit_sources(workspace, facts)
    before = _inventory(runtime_root)

    hard_stop = packer_fact_workspace.execute(
        workspace,
        _request(_hard("f001", 60), _hard("f002", 50), budget=100),
    )
    unresolved = packer_fact_workspace.execute(
        workspace,
        _request(
            _material(
                "f001",
                tokens=20,
                obligation="HARD",
                rank=None,
                actuality="UNRESOLVED",
                unresolved_reason="作者尚未决定该事实是否属于本次检查范围",
            ),
            budget=100,
        ),
    )

    assert hard_stop["decision_state"] == "STOP_HARD_BUDGET"
    assert unresolved["decision_state"] == "STOP_UNRESOLVED"
    for stopped in (hard_stop, unresolved):
        assert stopped["loaded_facts"] == []
        text = json.dumps(stopped, ensure_ascii=False, sort_keys=True)
        assert "甲拿起钥匙" not in text
        assert "乙关上门" not in text
        with pytest.raises(
            packer_fact_workspace.PackerFactWorkspaceError,
            match="RECALL_REQUIRES_READY_PACK",
        ):
            packer_fact_workspace.recall_omitted(
                workspace,
                stopped,
                "c4-current://f001",
            )
    assert _inventory(runtime_root) == before


@pytest.mark.parametrize(
    "dangerous_handle",
    [
        "file:///etc/passwd",
        "plan://PE-0001",
        "chapter://c01",
        "../facts.json",
        "/private/tmp/facts.json",
        "c4-current://f999",
        "c4-current://f001",
    ],
)
def test_recall_rejects_dangerous_or_non_omitted_handles(
    tmp_path: Path,
    dangerous_handle: str,
) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    result, _, _ = _ready_pack(workspace)
    before = _inventory(runtime_root)

    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="RECALL_HANDLE_NOT_IN_PACK_OMISSIONS",
    ):
        packer_fact_workspace.recall_omitted(
            workspace,
            result,
            dangerous_handle,
        )
    assert _inventory(runtime_root) == before


def test_recall_rejects_changed_source_and_tampered_omission(tmp_path: Path) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    result, _, _ = _ready_pack(workspace)
    facts_state = workspace.read("facts")
    workspace.commit(
        "op-advance-facts-after-pack",
        {"facts": facts_state["payload"]},
        {"facts": facts_state["version"]},
    )
    before = _inventory(runtime_root)
    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="RECALL_SOURCE_SNAPSHOT_CHANGED",
    ):
        packer_fact_workspace.recall_omitted(
            workspace,
            result,
            "c4-current://f002",
        )
    assert _inventory(runtime_root) == before

    tampered = copy.deepcopy(result)
    tampered["omitted_fact_index"][0]["fact_id"] = "f999"
    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="FACT_PACK_OMISSION_INDEX_INVALID",
    ):
        packer_fact_workspace.recall_omitted(
            workspace,
            tampered,
            "c4-current://f002",
        )


def test_cross_author_path_and_arbitrary_material_identity_fail_closed(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    alice = router.create_project(PRINCIPAL, "甲项目")
    result, _, _ = _ready_pack(alice)
    bob = router.create_project("auth:other-author", "乙项目")
    _commit_sources(
        bob,
        [_fact("f001", "甲拿起钥匙。"), _fact("f002", "乙关上门。")],
        operation_id="op-bob-current-facts",
    )
    before = _inventory(runtime_root)

    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="RECALL_WORKSPACE_BINDING_MISMATCH",
    ):
        packer_fact_workspace.recall_omitted(
            bob,
            result,
            "c4-current://f002",
        )
    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        packer_fact_workspace.execute(
            tmp_path / "project",
            _request(_hard("f001", 20)),
        )
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project(PRINCIPAL, bob.project_id)

    bad_identity = _hard("f001", 20)
    bad_identity["material_identity"] = "FUTURE_PLAN"
    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="CURRENT_FACT_MATERIAL_IDENTITY_INVALID",
    ):
        packer_fact_workspace.execute(alice, _request(bad_identity))

    future = _hard("f001", 20)
    future["actuality_class"] = "FUTURE_PLAN_OR_PROJECTION"
    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="CURRENT_FACT_ACTUALITY_INVALID",
    ):
        packer_fact_workspace.execute(alice, _request(future))

    caller_handle = _hard("f001", 20)
    caller_handle["recall_handle"] = "file:///etc/passwd"
    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="CURRENT_FACT_CANDIDATE_FIELDS_INVALID",
    ):
        packer_fact_workspace.execute(alice, _request(caller_handle))
    assert _inventory(runtime_root) == before


def test_empty_workspace_and_unknown_fact_reject_without_side_effects(
    tmp_path: Path,
) -> None:
    runtime_root, _, workspace = _open_workspace(tmp_path)
    workspace.commit(
        "op-empty-current-index",
        {"chapter_index": []},
        {"chapter_index": 0},
    )
    before = _inventory(runtime_root)
    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="CURRENT_FACT_NOT_FOUND:f001",
    ):
        packer_fact_workspace.execute(
            workspace,
            _request(_hard("f001", 20)),
        )
    assert _inventory(runtime_root) == before


def test_restart_returns_byte_stable_pack_and_recall(tmp_path: Path) -> None:
    runtime_root, router, workspace = _open_workspace(tmp_path)
    result, _, _ = _ready_pack(workspace)
    recalled = packer_fact_workspace.recall_omitted(
        workspace,
        result,
        "c4-current://f002",
    )
    before = _inventory(runtime_root)

    restarted = WorkspaceRouter(runtime_root).open_project(
        PRINCIPAL,
        workspace.project_id,
    )
    restarted_result = packer_fact_workspace.execute(
        restarted,
        _request(_hard("f001", 60), _material("f002", tokens=50), budget=70),
    )
    restarted_recall = packer_fact_workspace.recall_omitted(
        restarted,
        restarted_result,
        "c4-current://f002",
    )

    assert json.dumps(result, ensure_ascii=False, sort_keys=True) == json.dumps(
        restarted_result,
        ensure_ascii=False,
        sort_keys=True,
    )
    assert json.dumps(recalled, ensure_ascii=False, sort_keys=True) == json.dumps(
        restarted_recall,
        ensure_ascii=False,
        sort_keys=True,
    )
    assert router.open_project(PRINCIPAL, workspace.project_id).read("facts") is not None
    assert _inventory(runtime_root) == before


def test_public_validator_is_strict_and_returns_a_deep_copy(tmp_path: Path) -> None:
    _, _, workspace = _open_workspace(tmp_path)
    result, _, _ = _ready_pack(workspace)

    validated = packer_fact_workspace.validate_result(result)
    assert validated == result
    validated["loaded_facts"][0]["fact"]["text"] = "调用方修改副本"
    assert result["loaded_facts"][0]["fact"]["text"] == "事实句：甲拿起钥匙。"

    bad_mirror = copy.deepcopy(result)
    bad_mirror["decision_state"] = "STOP_UNRESOLVED"
    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="FACT_PACK_M11_MIRROR_MISMATCH",
    ):
        packer_fact_workspace.validate_result(bad_mirror)

    bad_loaded = copy.deepcopy(result)
    bad_loaded["loaded_facts"][0]["fact"]["status"] = "extracted"
    with pytest.raises(
        packer_fact_workspace.PackerFactWorkspaceError,
        match="FACT_PACK_LOADED_FACT_INVALID",
    ):
        packer_fact_workspace.validate_result(bad_loaded)
