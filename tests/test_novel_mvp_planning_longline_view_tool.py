from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
TOOL_PATH = PRODUCT_ROOT / "mvp" / "planning_longline_view_tool.py"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import planning_longline_view_tool
finally:
    sys.path.pop(0)


NOW = "2026-08-20 15:00:00"


def _common(object_id: str, *, rev: int = 1) -> dict:
    return {
        "id": object_id,
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
        "book": {"id": "BK-LONGLINE", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "scene_refs": ["SCN-0001", "SCN-0002"],
                "storyline_refs": ["L-0002", "L-0001"],
            }
        ],
        "scenes": [
            {
                "id": "SCN-0001",
                "slot_ref": "S-0001",
                "pe_refs": ["PE-0001"],
            },
            {
                "id": "SCN-0002",
                "slot_ref": "S-0001",
                "pe_refs": ["PE-0002"],
            },
        ],
        "events": [
            {
                "id": "PE-0001",
                "scene_ref": "SCN-0001",
                "storyline_ref": "L-0001",
                "hook_links": [{"hook_ref": "H-0001", "role": "payoff"}],
            },
            {
                "id": "PE-0002",
                "scene_ref": "SCN-0002",
                "storyline_ref": "L-0002",
                "hook_links": [
                    {"hook_ref": "H-0001", "role": "plant"},
                    {"hook_ref": "H-0002", "role": "plant"},
                ],
            },
        ],
        "storylines": [
            {
                **_common("L-0002", rev=3),
                "name": "寄件人身份线",
                "alias": None,
                "priority": 2,
                "members": ["CH-001"],
                "line_status": "paused",
                "last_scene_ref": "SCN-0002",
            },
            {
                **_common("L-0001", rev=2),
                "name": "密封信去向线",
                "alias": "送信线",
                "priority": 1,
                "members": ["CH-001", "CH-0002"],
                "line_status": "active",
                "last_scene_ref": "SCN-0001",
            },
        ],
        "hooks": [
            {
                **_common("H-0002"),
                "content": "寄件人的身份暂时不揭晓",
                "plant_refs": [{"ref": "PE-0002", "note": "只留下封蜡纹样"}],
                "payoff_slot_ref": None,
                "hook_status": "open",
                "paid_by_ref": None,
                "defer_count": 0,
                "revealed": False,
                "revealed_at": None,
                "safety_summary": "寄件人身份仍未安排揭晓。",
                "truth_bearing": "primary",
            },
            {
                **_common("H-0001", rev=4),
                "content": "密封信会让主角被迫离城",
                "plant_refs": [{"ref": "PE-0002", "note": "先出现密封信"}],
                "payoff_slot_ref": "S-0001",
                "hook_status": "paid",
                "paid_by_ref": "PE-0001",
                "defer_count": 1,
                "revealed": True,
                "revealed_at": "SCN-0001",
                "safety_summary": "离城安排已经进入当前规划。",
                "truth_bearing": "shadow",
            },
        ],
        "widgets": [],
        "pins": [],
        "must_carries": [],
        "option_records": [],
        "slot_mappings": [],
        "reconciliation_edges": [],
        "stop_points": {},
        "id_counters": {"MAP": 0, "RE": 0},
    }


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _entry(plan: dict | None = None, *, version: int = 7) -> dict:
    value = _plan() if plan is None else plan
    return {
        "version": version,
        "sha256": hashlib.sha256(_canonical_bytes(value)).hexdigest(),
        "plan": copy.deepcopy(value),
    }


def test_valid_view_keeps_plan_order_and_calls_paid_only_a_planning_arrangement() -> None:
    source = _entry()
    before = copy.deepcopy(source)

    result = planning_longline_view_tool.execute(source)

    assert result["identity"] == "M8_CURRENT_PLANNING_LONGLINE_VIEW"
    assert result["version"] == "v1"
    assert result["scope"] == "PLANNING_NOT_FACT"
    assert result["source_plan_version"] == 7
    assert result["source_plan_sha256"] == source["sha256"]
    assert [row["id"] for row in result["storylines"]] == ["L-0002", "L-0001"]
    assert [row["id"] for row in result["hooks"]] == ["H-0002", "H-0001"]
    assert result["unavailable"] == ["卷纲", "人物命运", "灵感与预计使用时机"]
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True)
    assert "不表示故事已经发生" in rendered
    assert "只表示已经安排回收，不表示实际兑现" in rendered
    assert "实际已兑现" not in rendered
    assert source == before


def test_empty_storylines_and_hooks_return_an_explicit_empty_view() -> None:
    plan = _plan()
    plan["slot_sequence"] = []
    plan["slots"] = []
    plan["scenes"] = []
    plan["events"] = []
    plan["storylines"] = []
    plan["hooks"] = []

    result = planning_longline_view_tool.execute(_entry(plan))

    assert result["storylines"] == []
    assert result["hooks"] == []
    assert result["scope"] == "PLANNING_NOT_FACT"
    assert result["unavailable"] == ["卷纲", "人物命运", "灵感与预计使用时机"]


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda plan: plan["storylines"][0].pop("last_scene_ref"), "OBJECT_FIELDS_MISSING"),
        (lambda plan: plan["storylines"][0].__setitem__("extra", True), "OBJECT_FIELDS_EXTRA"),
        (lambda plan: plan["storylines"][0].__setitem__("members", ["林照"]), "REFERENCE_INVALID"),
        (lambda plan: plan["storylines"][0].__setitem__("last_scene_ref", "SCN-9999"), "STORYLINE_LAST_SCENE_REF_INVALID"),
        (lambda plan: plan["slots"][0].__setitem__("storyline_refs", ["L-9999"]), "SLOT_STORYLINE_REF_NOT_FOUND"),
        (lambda plan: plan["events"][0].pop("storyline_ref"), "EVENT_STORYLINE_REF_MISSING"),
        (lambda plan: plan["events"][0].__setitem__("storyline_ref", "L-9999"), "EVENT_STORYLINE_REF_NOT_FOUND"),
    ],
)
def test_bad_storyline_shape_or_reference_fails_closed(mutate, error: str) -> None:
    plan = _plan()
    mutate(plan)
    with pytest.raises(planning_longline_view_tool.PlanningLonglineViewError, match=error):
        planning_longline_view_tool.execute(_entry(plan))


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda plan: plan["hooks"][0].pop("safety_summary"), "OBJECT_FIELDS_MISSING"),
        (lambda plan: plan["hooks"][0].__setitem__("actual_fulfilled", True), "OBJECT_FIELDS_EXTRA"),
        (lambda plan: plan["hooks"][0]["plant_refs"][0].__setitem__("ref", "PE-9999"), "HOOK_PLANT_TARGET_NOT_FOUND"),
        (lambda plan: plan["hooks"][1].__setitem__("payoff_slot_ref", "S-9999"), "HOOK_PAYOFF_SLOT_REF_NOT_FOUND"),
        (lambda plan: plan["hooks"][1].__setitem__("paid_by_ref", "PE-9999"), "HOOK_PAID_BY_REF_NOT_FOUND"),
        (lambda plan: plan["events"][0].__setitem__("hook_links", []), "HOOK_PAID_EVENT_LINK_MISSING"),
        (lambda plan: plan["hooks"][1].__setitem__("revealed_at", "SCN-9999"), "HOOK_REVEALED_AT_NOT_FOUND"),
    ],
)
def test_bad_hook_shape_or_reference_fails_closed(mutate, error: str) -> None:
    plan = _plan()
    mutate(plan)
    with pytest.raises(planning_longline_view_tool.PlanningLonglineViewError, match=error):
        planning_longline_view_tool.execute(_entry(plan))


def test_nonempty_volumes_and_snapshot_identity_drift_are_hard_stops() -> None:
    with_volume = _plan()
    with_volume["volumes"] = [{"id": "VOL-0001"}]
    with pytest.raises(
        planning_longline_view_tool.PlanningLonglineViewError,
        match="VOLUMES_NOT_SUPPORTED",
    ):
        planning_longline_view_tool.execute(_entry(with_volume))

    bad_sha = _entry()
    bad_sha["sha256"] = "0" * 64
    with pytest.raises(
        planning_longline_view_tool.PlanningLonglineViewError,
        match="SOURCE_PLAN_SHA_MISMATCH",
    ):
        planning_longline_view_tool.execute(bad_sha)


def test_cli_is_byte_stable_and_failed_request_keeps_old_output(tmp_path: Path) -> None:
    input_path = tmp_path / "plan.json"
    output_path = tmp_path / "view.json"
    second_output = tmp_path / "view-second.json"
    input_path.write_bytes(_canonical_bytes(_entry()))

    first = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        check=False,
    )
    second = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "--input",
            str(input_path),
            "--output",
            str(second_output),
        ],
        capture_output=True,
        check=False,
    )
    assert first.returncode == second.returncode == 0
    assert output_path.read_bytes() == second_output.read_bytes()

    old = output_path.read_bytes()
    bad_plan = _plan()
    bad_plan["volumes"] = [{"id": "VOL-0001"}]
    input_path.write_bytes(_canonical_bytes(_entry(bad_plan)))
    failed = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        check=False,
    )
    assert failed.returncode == 1
    assert b"VOLUMES_NOT_SUPPORTED" in failed.stderr
    assert output_path.read_bytes() == old
    assert not list(tmp_path.glob(f".{output_path.name}.*.tmp"))


@pytest.mark.parametrize("alias_kind", ["same", "symlink", "hardlink"])
def test_cli_rejects_input_output_aliases(tmp_path: Path, alias_kind: str) -> None:
    input_path = tmp_path / "plan.json"
    input_path.write_bytes(_canonical_bytes(_entry()))
    if alias_kind == "same":
        output_path = input_path
    elif alias_kind == "symlink":
        output_path = tmp_path / "view-link.json"
        output_path.symlink_to(input_path)
    else:
        output_path = tmp_path / "view-hard.json"
        os.link(input_path, output_path)
    before = input_path.read_bytes()

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert b"OUTPUT_MUST_NOT_OVERWRITE_INPUT" in result.stderr
    assert input_path.read_bytes() == before


def test_replace_failure_preserves_old_output_and_removes_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "view.json"
    output_path.write_bytes(b"old-view\n")
    result = planning_longline_view_tool.execute(_entry())

    def fail_replace(source, target) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(planning_longline_view_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        planning_longline_view_tool._write_atomic(str(output_path), result)

    assert output_path.read_bytes() == b"old-view\n"
    assert not list(tmp_path.glob(f".{output_path.name}.*.tmp"))
