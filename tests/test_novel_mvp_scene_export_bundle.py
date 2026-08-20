from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
BUNDLE_TOOL = PRODUCT_ROOT / "mvp/scene_export_bundle.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import scene_export_bundle, scene_export_tool
finally:
    sys.path.pop(0)


PLAN_SHA = "a" * 64


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _source() -> dict:
    return {
        "contract": "C7_PLOT_LAYER v1",
        "scene_export_slice": "m10-scene-slice-r1",
        "project": "_synthetic_bundle",
        "generated_at": "2026-08-19 23:00:00",
        "model": "stub",
        "book_title": "雨夜送信",
        "plan_id": "PLAN-BUNDLE-r1",
        "basis_note": "synthetic-plan@r1",
        "anchors": [
            {
                "anchor_id": "AN-CHAR-001",
                "kind": "character",
                "entity_ref": "CH-001",
                "name": "林照",
                "aliases": [],
                "look": "深蓝雨衣",
                "voice_hint": "克制",
                "status": "confirmed",
                "source_refs": ["SYN-CHAR-001"],
                "revision": 1,
            },
            {
                "anchor_id": "AN-LOC-001",
                "kind": "location",
                "entity_ref": "LOC-001",
                "name": "纸灯巷",
                "aliases": [],
                "look": "雨夜青石巷",
                "voice_hint": "",
                "status": "confirmed",
                "source_refs": ["SYN-LOC-001"],
                "revision": 1,
            },
        ],
        "scenes": [
            {
                "id": "SCN-001",
                "chapter_hint": 1,
                "chapter_title": "雨夜送信",
                "scene_order": 1,
                "scene_count": 1,
                "goal": "把信交到约定地点",
                "summary": "林照冒雨进入纸灯巷",
                "location_ref": "AN-LOC-001",
                "time": "雨夜",
                "visual_hint": "只展示当前可见的巷口",
                "characters": ["CH-001"],
                "character_presence": {"CH-001": "独自进入巷口"},
                "mood_in": "戒备",
                "mood_out": "决定行动",
                "turn": "发现接头暗号",
                "pov": "CH-001",
                "resistance": "接头人尚未出现",
                "writing_guidance": ["只表现当前场已知信息"],
                "spoiler_guard": [
                    {
                        "audience_state": "known_at_scene",
                        "instruction": "不得展示信中谜底",
                    }
                ],
                "dialogue_hints": [
                    {
                        "id": "D-001",
                        "kind": "information_point",
                        "speaker_ref": "CH-001",
                        "info": "确认暗号与约定一致",
                        "tone": "压低声音",
                    }
                ],
                "pe_refs": ["PE-001"],
            }
        ],
        "planned_events": [
            {
                "id": "PE-001",
                "scene_ref": "SCN-001",
                "action": "林照核对墙上的接头暗号",
                "visual": "雨水沿着旧砖墙流下",
                "dialogue_hint_refs": ["D-001"],
                "shot_hint": "中景",
            }
        ],
    }


def _prototype() -> dict:
    return scene_export_tool.execute({"source": _source()})


def _identity() -> dict:
    return {"source_plan_version": 7, "source_plan_sha256": PLAN_SHA}


def _request() -> dict:
    return {"c8_prototype": _prototype(), "source_identity": _identity()}


def _zip_parts(payload: bytes) -> tuple[dict[str, bytes], dict]:
    with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    return parts, json.loads(parts["manifest.json"])


def test_bundle_has_exact_members_crc_and_recomputable_manifest() -> None:
    prototype = _prototype()
    payload = scene_export_bundle.build_bundle(prototype, _identity())

    with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
        assert archive.namelist() == list(scene_export_bundle.MEMBER_ORDER)
        assert archive.testzip() is None
        for info in archive.infolist():
            assert info.date_time == scene_export_bundle.FIXED_ZIP_TIMESTAMP
            assert info.compress_type == zipfile.ZIP_STORED
            assert info.external_attr >> 16 == scene_export_bundle.FIXED_FILE_MODE
        json_payload = archive.read("scene_cards.json")
        markdown_payload = archive.read("scene_cards.md")
        manifest = json.loads(archive.read("manifest.json"))

    assert json.loads(json_payload) == prototype
    assert markdown_payload.decode("utf-8") == scene_export_tool.render_all(prototype)
    assert manifest["bundle_identity"] == {
        "contract": scene_export_bundle.BUNDLE_IDENTITY,
        "version": scene_export_bundle.BUNDLE_VERSION,
        "format": "ZIP_STORED_TEXT_ONLY",
    }
    assert manifest["c8_identity"] == {
        "contract": prototype["contract"],
        "version": prototype["version"],
        "export_id": prototype["export_id"],
        "source_sha256": prototype["source_sha256"],
    }
    assert manifest["source_plan"] == {"version": 7, "sha256": PLAN_SHA}
    assert manifest["card_ids"] == ["SC-SCN-001"]
    assert manifest["ai_label"] == prototype["ai_label"]
    assert manifest["member_order"] == list(scene_export_bundle.MEMBER_ORDER)
    assert manifest["members"] == {
        "scene_cards.json": {
            "bytes": len(json_payload),
            "sha256": _sha(json_payload),
        },
        "scene_cards.md": {
            "bytes": len(markdown_payload),
            "sha256": _sha(markdown_payload),
        },
    }


def test_core_is_deterministic_and_does_not_modify_inputs() -> None:
    prototype = _prototype()
    identity = _identity()
    prototype_before = copy.deepcopy(prototype)
    identity_before = copy.deepcopy(identity)

    first = scene_export_bundle.build_bundle(prototype, identity)
    second = scene_export_bundle.build_bundle(prototype, identity)

    assert first == second
    assert prototype == prototype_before
    assert identity == identity_before


@pytest.mark.parametrize(
    "fault",
    ["bad_c8", "bad_source", "missing_plan", "frame_reference"],
)
def test_bad_c8_source_or_missing_plan_watermark_is_rejected(fault: str) -> None:
    prototype = _prototype()
    identity = _identity()
    if fault == "bad_c8":
        prototype["contract"] = "WRONG"
    elif fault == "bad_source":
        identity["source_plan_sha256"] = "broken"
    elif fault == "missing_plan":
        identity.pop("source_plan_version")
    else:
        prototype["cards"][0]["frame_refs"] = ["/tmp/frame.png"]

    with pytest.raises(scene_export_bundle.SceneExportBundleError):
        scene_export_bundle.build_bundle(prototype, identity)


def test_embedded_workspace_watermark_must_match_explicit_source() -> None:
    prototype = _prototype()
    prototype["workspace_basis"] = {
        "source_plan_version": 8,
        "source_plan_sha256": PLAN_SHA,
    }

    with pytest.raises(
        scene_export_bundle.SceneExportBundleError,
        match="EMBEDDED_SOURCE_IDENTITY_MISMATCH",
    ):
        scene_export_bundle.build_bundle(prototype, _identity())


def test_cli_is_byte_identical_across_processes(tmp_path: Path) -> None:
    input_path = tmp_path / "request.json"
    first_path = tmp_path / "first.zip"
    second_path = tmp_path / "second.zip"
    input_path.write_text(
        json.dumps(_request(), ensure_ascii=False),
        encoding="utf-8",
    )
    input_before = input_path.read_bytes()
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    for output_path in (first_path, second_path):
        completed = subprocess.run(
            [
                sys.executable,
                str(BUNDLE_TOOL),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        assert completed.returncode == 0, completed.stderr

    assert first_path.read_bytes() == second_path.read_bytes()
    assert input_path.read_bytes() == input_before


def test_output_cannot_overwrite_input_and_failure_preserves_old_zip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "bundle.zip"
    input_path.write_text(json.dumps(_request(), ensure_ascii=False), encoding="utf-8")
    input_before = input_path.read_bytes()

    assert (
        scene_export_bundle.main(
            ["--input", str(input_path), "--output", str(input_path)]
        )
        == 2
    )
    assert input_path.read_bytes() == input_before

    output_path.write_bytes(b"old-zip-sentinel")
    output_before = output_path.read_bytes()

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("synthetic zip replace failure")

    monkeypatch.setattr(scene_export_bundle.os, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic zip replace failure"):
        scene_export_bundle._write_bundle_atomic(
            output_path,
            scene_export_bundle.build_bundle(_prototype(), _identity()),
        )

    assert output_path.read_bytes() == output_before
    assert not list(tmp_path.glob(".bundle.zip.*.tmp"))
