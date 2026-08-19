from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
TOOL_PATH = PRODUCT_ROOT / "mvp/chapter_slot_snapshot_tool.py"
SCHEMA_PATH = PRODUCT_ROOT / "contracts/CHAPTER_SLOT_SNAPSHOT.schema.json"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import chapter_slot_snapshot_tool as tool
    from mvp import scene_export
finally:
    sys.path.pop(0)


NOW = "2026-08-19 11:00:00"


def _plan() -> dict:
    return {
        "schema": "plan-v2",
        "ledger": "plan",
        "book": {"id": "BK-SNAPSHOT", "volumes_enabled": False},
        "slot_sequence": ["S-0001"],
        "volumes": [],
        "slots": [
            {
                "id": "S-0001",
                "volume_ref": None,
                "title_hint": "雨巷来信",
                "goal": "让两人决定是否共同送信",
                "summary": "作者计划让两人在雨巷形成临时同盟",
                "entry_state": "双方互不信任",
                "storyline_refs": ["L-0001"],
                "scene_refs": ["SCN-0001"],
                "exit_condition": "双方同意共同送信",
                "exit_hook": "寄件人身份仍未知",
                "must_not": ["不得把寄件人身份提前揭晓"],
                "risks": ["人物动机交代不足"],
                "target_length": 1600,
                "outline_checkpoint": {
                    "outline_rev": 2,
                    "source_slot_ref": "S-0001",
                    "source_commit_seq": 9,
                },
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
                "source_identity": "author_declared",
                "created_at": NOW,
                "updated_at": NOW,
                "rev": 3,
                "note": "",
            }
        ],
        "scenes": [
            {
                "id": "SCN-0001",
                "slot_ref": "S-0001",
                "goal": "完成密封信交接",
                "summary": "两人在雨巷确认送信时限",
                "location": "纸灯巷口",
                "characters": ["CH-001", "CH-002"],
                "pe_refs": ["PE-0001"],
                "mood_in": "戒备",
                "mood_out": "临时同盟",
                "visual_hint": "纸灯倒影被雨水打碎",
                "dialogue_hints": ["只透露天亮前必须送达"],
                "resistance": "双方都不肯说明来源",
                "turn": "许岚交出密封信",
                "pov": "CH-001",
                "spoiler_notes": ["不得展示信内页"],
                "word_estimate": 800,
                "truth_bearing": "handed_over",
                "source_identity": "author_declared",
                "created_at": NOW,
                "updated_at": NOW,
                "rev": 4,
                "note": "",
            }
        ],
        "events": [
            {
                "id": "PE-0001",
                "text": "许岚计划把密封信交给林照",
                "scene_ref": "SCN-0001",
                "storyline_ref": "L-0001",
                "purpose": "advance",
                "hook_links": [],
                "story_time_hint": "雨夜",
                "digest_status": "digested",
                "digest_ref": "OPT-0001",
                "origin_ref": "S-0001",
                "repair_ref": None,
                "deviation_note": None,
                "defer_count": 0,
                "truth_bearing": "handed_over",
                "prose_status": "written",
                "prose_basis": "verified",
                "impact": "normal",
                "source_identity": "author_declared",
                "created_at": NOW,
                "updated_at": NOW,
                "rev": 5,
                "note": "",
            }
        ],
        "storylines": [
            {
                "id": "L-0001",
                "name": "密封信去向",
                "alias": "送信线",
                "priority": 1,
                "members": ["CH-001", "CH-002"],
                "line_status": "active",
                "last_scene_ref": "SCN-0001",
                "source_identity": "author_declared",
                "created_at": NOW,
                "updated_at": NOW,
                "rev": 2,
                "note": "",
            }
        ],
        "hooks": [],
        "widgets": [],
        "pins": [],
        "must_carries": [],
        "option_records": [
            {
                "id": "OPT-0001",
                "slot_ref": "S-0001",
                "digest_applied": ["PE-0001"],
            }
        ],
        "slot_mappings": [],
        "reconciliation_edges": [],
        "stop_points": {},
        "id_counters": {"MAP": 0, "RE": 0},
    }


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _request(plan: dict | None = None) -> dict:
    plan = _plan() if plan is None else plan
    return {
        "plan": plan,
        "slot_ref": "S-0001",
        "source_plan_version": 7,
        "source_plan_sha256": hashlib.sha256(_canonical_bytes(plan)).hexdigest(),
    }


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key for child in value.values() for key in _all_keys(child)
        }
    if isinstance(value, list):
        return {key for child in value for key in _all_keys(child)}
    return set()


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        capture_output=True,
        check=False,
    )


def test_projects_closed_read_only_snapshot_without_mutating_plan() -> None:
    request = _request()
    before = copy.deepcopy(request)

    first = tool.execute(request)
    second = tool.execute(copy.deepcopy(request))

    assert request == before
    assert _canonical_bytes(first) == _canonical_bytes(second)
    assert first["contract"] == "CHAPTER_SLOT_SNAPSHOT"
    assert first["version"] == "v1"
    assert first["status"] == "plan"
    assert first["source_plan_version"] == 7
    assert first["basis_refs"] == {
        "slot_ref": "S-0001",
        "scene_refs": ["SCN-0001"],
        "event_refs": ["PE-0001"],
        "storyline_refs": ["L-0001"],
    }
    assert first["generation_watermark"]["slot_rev"] == 3
    assert first["generation_watermark"]["outline_source_commit_seq"] == 9
    assert first["scenes"][0]["rev"] == 4
    assert first["events"][0]["rev"] == 5
    assert first["storylines"][0]["rev"] == 2
    forbidden = {
        "facts",
        "actual",
        "actuality",
        "confirmed",
        "handover_parts",
        "slot_status",
        "truth_bearing",
        "digest_status",
        "digest_ref",
        "prose_status",
        "reconciliation_edges",
    }
    assert forbidden.isdisjoint(_all_keys(first))


def test_schema_accepts_output_and_rejects_identity_or_truth_drift() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    valid = tool.execute(_request())
    assert list(validator.iter_errors(valid)) == []

    for mutate in (
        lambda value: value.update(contract="C7_PLOT_LAYER v1"),
        lambda value: value.update(status="confirmed"),
        lambda value: value.update(actual=True),
    ):
        invalid = copy.deepcopy(valid)
        mutate(invalid)
        assert list(validator.iter_errors(invalid))


def test_c7_identity_coexists_and_m10_normalized_slice_gap_remains() -> None:
    c7 = {
        "contract": "C7_PLOT_LAYER v1",
        "cards": [{"id": "card01"}],
        "conflicts": [],
    }
    c7_before = copy.deepcopy(c7)
    snapshot = tool.execute(_request())

    assert c7 == c7_before
    assert snapshot["contract"] != c7["contract"]
    assert "cards" not in snapshot and "scenes" not in c7
    with pytest.raises(scene_export.SceneExportError) as exc_info:
        scene_export.export_scene_cards(snapshot)
    assert exc_info.value.code == "UNKNOWN_FIELDS"


@pytest.mark.parametrize(
    ("mutate", "error_code"),
    [
        (lambda request: request.update(slot_ref="S-9999"), "SLOT_NOT_FOUND"),
        (
            lambda request: request["plan"]["slots"][0]["scene_refs"].append(
                "SCN-0001"
            ),
            "DUPLICATE_REFERENCE",
        ),
        (
            lambda request: request["plan"]["scenes"][0].update(
                pe_refs=["PE-9999"]
            ),
            "PLAN_INVALID",
        ),
        (
            lambda request: request["plan"]["slots"][0].update(rev=0),
            "REVISION_INVALID",
        ),
        (
            lambda request: request.update(source_plan_sha256="0" * 64),
            "SOURCE_PLAN_SHA_MISMATCH",
        ),
        (
            lambda request: (
                request["plan"]["slots"][0].update(storyline_refs=["L-9999"]),
                request["plan"]["events"][0].update(storyline_ref="L-9999"),
            ),
            "STORYLINE_NOT_FOUND",
        ),
        (
            lambda request: request["plan"].update(facts=[]),
            "TRUTH_FIELD_FORBIDDEN",
        ),
    ],
)
def test_rejects_stale_or_non_closed_inputs(mutate, error_code: str) -> None:
    request = _request()
    mutate(request)
    if error_code != "SOURCE_PLAN_SHA_MISMATCH":
        request["source_plan_sha256"] = hashlib.sha256(
            _canonical_bytes(request["plan"])
        ).hexdigest()

    with pytest.raises(tool.ChapterSlotSnapshotError) as exc_info:
        tool.execute(request)

    assert exc_info.value.code == error_code


def test_cli_file_round_trip_is_parseable_after_restart(tmp_path: Path) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "snapshot.json"
    input_path.write_text(json.dumps(_request(), ensure_ascii=False), encoding="utf-8")

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 0, completed.stderr.decode()
    persisted = json.loads(output_path.read_bytes())
    assert persisted == tool.execute(_request())
    assert json.loads(output_path.read_text(encoding="utf-8"))["status"] == "plan"


def test_failed_cli_does_not_replace_existing_output(tmp_path: Path) -> None:
    request = _request()
    request["source_plan_sha256"] = "0" * 64
    input_path = tmp_path / "bad-request.json"
    output_path = tmp_path / "existing.json"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    before = b'{"keep":"old"}\n'
    output_path.write_bytes(before)

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 2
    assert b"SOURCE_PLAN_SHA_MISMATCH" in completed.stderr
    assert output_path.read_bytes() == before
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []
