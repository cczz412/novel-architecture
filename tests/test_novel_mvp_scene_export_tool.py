from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
TOOL_PATH = PRODUCT_ROOT / "mvp/scene_export_tool.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import scene_export, scene_export_tool
finally:
    sys.path.pop(0)


def _anchor(
    anchor_id: str,
    kind: str,
    entity_ref: str,
    name: str,
    look: str,
) -> dict:
    return {
        "anchor_id": anchor_id,
        "kind": kind,
        "entity_ref": entity_ref,
        "name": name,
        "aliases": [],
        "look": look,
        "voice_hint": "克制" if kind == "character" else "",
        "status": "confirmed",
        "source_refs": [f"SYN-{anchor_id}"],
        "revision": 1,
    }


def _scene(
    scene_id: str,
    order: int,
    location_ref: str,
    characters: list[str],
    speaker_ref: str,
    event_ref: str,
    scene_count: int = 2,
) -> dict:
    hint_id = f"D-{order:03d}"
    return {
        "id": scene_id,
        "chapter_hint": 1,
        "chapter_title": "雨夜送信",
        "scene_order": order,
        "scene_count": scene_count,
        "goal": f"完成第{order}段推进",
        "summary": f"第{order}场计划摘要",
        "location_ref": location_ref,
        "time": "雨夜",
        "visual_hint": f"第{order}场只展示当前可见环境",
        "characters": characters,
        "character_presence": {
            ref: f"{ref}处于第{order}场计划位置" for ref in characters
        },
        "mood_in": "戒备",
        "mood_out": "决定行动",
        "turn": f"第{order}场计划转折",
        "pov": characters[0],
        "resistance": "双方掌握的信息不对称",
        "writing_guidance": ["只表现当前场已知信息"],
        "spoiler_guard": [
            {
                "audience_state": "known_at_scene",
                "instruction": f"不得展示第{order}场之后的答案",
            }
        ],
        "dialogue_hints": [
            {
                "id": hint_id,
                "kind": "information_point",
                "speaker_ref": speaker_ref,
                "info": f"透露第{order}场必须知道的信息点",
                "tone": "压低声音",
            }
        ],
        "pe_refs": [event_ref],
    }


def _event(event_id: str, scene_ref: str, order: int) -> dict:
    return {
        "id": event_id,
        "scene_ref": scene_ref,
        "action": f"执行第{order}场计划动作",
        "visual": f"第{order}场动作的当前画面",
        "dialogue_hint_refs": [f"D-{order:03d}"],
        "shot_hint": "中景",
    }


def _source() -> dict:
    scene_one = _scene(
        "SCN-001",
        1,
        "AN-LOC-001",
        ["CH-001", "CH-002"],
        "CH-002",
        "PE-001",
    )
    scene_two = _scene(
        "SCN-002",
        2,
        "AN-LOC-002",
        ["CH-001"],
        "CH-001",
        "PE-002",
    )
    return {
        "contract": "C7_PLOT_LAYER v1",
        "scene_export_slice": "m10-scene-slice-r1",
        "project": "_synthetic_scene_tool",
        "generated_at": "2026-08-19 12:00:00",
        "model": "stub",
        "book_title": "雨夜送信",
        "plan_id": "PLAN-SYN-r1",
        "basis_note": "synthetic-plan@r1",
        "anchors": [
            _anchor("AN-CHAR-001", "character", "CH-001", "林照", "深蓝雨衣"),
            _anchor("AN-CHAR-002", "character", "CH-002", "许岚", "灰色风衣"),
            _anchor("AN-LOC-001", "location", "LOC-001", "纸灯巷", "雨夜青石巷"),
            _anchor("AN-LOC-002", "location", "LOC-002", "旧码头", "雾中木栈桥"),
        ],
        "scenes": [scene_two, scene_one],
        "planned_events": [
            _event("PE-002", "SCN-002", 2),
            _event("PE-001", "SCN-001", 1),
        ],
    }


def _request() -> dict:
    return {"source": _source()}


def _three_card_prototype() -> dict:
    source = _source()
    for scene in source["scenes"]:
        scene["scene_count"] = 3
    source["anchors"].append(
        _anchor("AN-LOC-003", "location", "LOC-003", "钟楼", "晨雾中的钟楼")
    )
    source["scenes"].append(
        _scene(
            "SCN-003",
            3,
            "AN-LOC-003",
            ["CH-002"],
            "CH-002",
            "PE-003",
            scene_count=3,
        )
    )
    source["planned_events"].append(_event("PE-003", "SCN-003", 3))
    return scene_export_tool.execute({"source": source})


def _markdown_card_body(markdown: str, index: int, card_id: str) -> str:
    heading = f"## 场景卡 {index} · `{card_id}`\n\n"
    start = markdown.index(heading) + len(heading)
    end = markdown.find("\n\n---\n\n", start)
    if end < 0:
        end = len(markdown)
    return markdown[start:end].rstrip() + "\n"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        capture_output=True,
        check=False,
    )


def test_multi_scene_export_is_stable_sorted_and_reference_faithful() -> None:
    request = _request()
    before = copy.deepcopy(request)

    first = scene_export_tool.execute(request)
    second = scene_export_tool.execute(copy.deepcopy(request))

    assert request == before
    assert first == second
    scene_export.validate_c8_prototype(first)
    assert first["contract"] == "C8_SCENE_CARD_PROTOTYPE"
    assert first["range"] == {
        "chapters": [1],
        "scene_ids": ["SCN-001", "SCN-002"],
    }
    assert [card["card_id"] for card in first["cards"]] == [
        "SC-SCN-001",
        "SC-SCN-002",
    ]
    assert [card["shots"][1]["beat_ref"] for card in first["cards"]] == [
        "PE-001",
        "PE-002",
    ]


def test_anchor_selection_keeps_character_and_location_identity() -> None:
    result = scene_export_tool.execute(_request())
    first, second = result["cards"]

    assert first["setting"]["location_ref"] == "AN-LOC-001"
    assert second["setting"]["location_ref"] == "AN-LOC-002"
    assert first["cast"] == [
        {"anchor_ref": "AN-CHAR-001", "presence": "CH-001处于第1场计划位置"},
        {"anchor_ref": "AN-CHAR-002", "presence": "CH-002处于第1场计划位置"},
    ]
    assert second["cast"] == [
        {"anchor_ref": "AN-CHAR-001", "presence": "CH-001处于第2场计划位置"}
    ]


def test_ambiguous_character_anchor_is_rejected() -> None:
    request = _request()
    duplicate = copy.deepcopy(request["source"]["anchors"][0])
    duplicate["anchor_id"] = "AN-CHAR-009"
    request["source"]["anchors"].append(duplicate)

    with pytest.raises(scene_export.SceneExportError) as exc_info:
        scene_export_tool.execute(request)

    assert exc_info.value.code == "DUPLICATE_CHARACTER_ANCHOR"


@pytest.mark.parametrize(
    ("mutate", "error_code"),
    [
        (
            lambda source: source["scenes"][0]["spoiler_guard"][0].update(
                audience_state="future_reveal"
            ),
            "FUTURE_SPOILER_FORBIDDEN",
        ),
        (
            lambda source: source["scenes"][0].update(
                dialogue_hints=[
                    {
                        "id": "D-002",
                        "kind": "verbatim_line",
                        "speaker_ref": "CH-001",
                        "line": "我已经知道答案。",
                        "tone": "平静",
                    }
                ]
            ),
            "DIALOGUE_PROSE_FORBIDDEN",
        ),
    ],
)
def test_future_spoiler_or_sentence_dialogue_rejects_whole_batch(
    mutate, error_code: str
) -> None:
    request = _request()
    mutate(request["source"])

    with pytest.raises(scene_export.SceneExportError) as exc_info:
        scene_export_tool.execute(request)

    assert exc_info.value.code == error_code


@pytest.mark.parametrize(
    ("mutate", "error_code"),
    [
        (
            lambda source: source["planned_events"].pop(),
            "EVENT_NOT_FOUND",
        ),
        (
            lambda source: source["planned_events"][1].update(scene_ref="SCN-002"),
            "EVENT_SCENE_MISMATCH",
        ),
        (
            lambda source: source["planned_events"].append(
                _event("PE-003", "SCN-001", 1)
            ),
            "UNREFERENCED_PLANNED_EVENT",
        ),
        (
            lambda source: source["scenes"][0].update(scene_order=3),
            "SCENE_POSITION_OUT_OF_RANGE",
        ),
        (
            lambda source: source["scenes"][0].update(scene_order=1),
            "DUPLICATE_SCENE_POSITION",
        ),
    ],
)
def test_bad_reference_or_scene_position_rejects_before_export(
    mutate, error_code: str
) -> None:
    request = _request()
    mutate(request["source"])

    with pytest.raises(scene_export_tool.SceneExportToolError) as exc_info:
        scene_export_tool.execute(request)

    assert exc_info.value.code == error_code


def test_chapter_slot_snapshot_is_not_accepted_as_normalized_m10_slice() -> None:
    request = {
        "source": {
            "contract": "CHAPTER_SLOT_SNAPSHOT",
            "version": "v1",
            "status": "plan",
        }
    }

    with pytest.raises(scene_export_tool.SceneExportToolError) as exc_info:
        scene_export_tool.execute(request)

    assert exc_info.value.code == "INVALID_SOURCE_CONTRACT"


def test_cli_file_round_trip_can_be_read_by_another_process(tmp_path: Path) -> None:
    input_path = tmp_path / "m10-source.json"
    output_path = tmp_path / "c8-prototype.json"
    input_path.write_text(json.dumps(_request(), ensure_ascii=False), encoding="utf-8")

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 0, completed.stderr.decode()
    assert output_path.read_bytes() == scene_export_tool._output_bytes(
        scene_export_tool.execute(_request())
    )
    persisted = json.loads(output_path.read_bytes())
    assert persisted == scene_export_tool.execute(_request())
    reader = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json,sys; print(json.load(open(sys.argv[1]))['contract'])",
            str(output_path),
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    assert reader.stdout.strip() == "C8_SCENE_CARD_PROTOTYPE"


def test_failed_cli_does_not_overwrite_existing_output(tmp_path: Path) -> None:
    request = _request()
    request["source"]["scenes"][0]["spoiler_guard"][0][
        "audience_state"
    ] = "future_reveal"
    input_path = tmp_path / "bad-source.json"
    output_path = tmp_path / "existing-output.json"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    before = b'{"keep":"old"}\n'
    output_path.write_bytes(before)

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 2
    assert b"FUTURE_SPOILER_FORBIDDEN" in completed.stderr
    assert output_path.read_bytes() == before
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []


def test_render_card_selects_exact_second_card_without_mutating_input() -> None:
    prototype = scene_export_tool.execute(_request())
    before = copy.deepcopy(prototype)

    rendered = scene_export_tool.render_card(prototype, "SC-SCN-002")

    assert prototype == before
    assert rendered == scene_export.render_scene_card(prototype, 1)
    assert "第2场计划摘要" in rendered
    assert "第1场计划摘要" not in rendered
    assert "旧码头" in rendered
    assert "纸灯巷" not in rendered


def test_render_card_cli_is_utf8_restart_readable_and_byte_stable(
    tmp_path: Path,
) -> None:
    prototype = scene_export_tool.execute(_request())
    input_path = tmp_path / "c8-prototype.json"
    first_path = tmp_path / "scene-two-first.txt"
    second_path = tmp_path / "scene-two-second.txt"
    input_path.write_text(json.dumps(prototype, ensure_ascii=False), encoding="utf-8")
    args = ("--mode", "render-card", "--card-id", "SC-SCN-002")

    first = _run_cli(*args, "--input", str(input_path), "--output", str(first_path))
    second = _run_cli(
        *args,
        "--input",
        str(input_path),
        "--output",
        str(second_path),
    )

    assert first.returncode == second.returncode == 0
    expected = scene_export_tool.render_card(prototype, "SC-SCN-002").encode()
    assert first_path.read_bytes() == second_path.read_bytes() == expected
    reader = subprocess.run(
        [
            sys.executable,
            "-c",
            "import pathlib,sys; print(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8').splitlines()[0])",
            str(first_path),
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    assert "场2/2" in reader.stdout


@pytest.mark.parametrize(
    ("damage", "extra_args", "error_code"),
    [
        ("none", ("--mode", "render-card"), "CARD_ID_REQUIRED"),
        (
            "none",
            ("--mode", "render-card", "--card-id", "SC-NOT-FOUND"),
            "CARD_ID_NOT_FOUND",
        ),
        (
            "duplicate",
            ("--mode", "render-card", "--card-id", "SC-SCN-001"),
            "CARD_ID_NOT_UNIQUE",
        ),
        (
            "missing_card_id",
            ("--mode", "render-card", "--card-id", "SC-SCN-002"),
            "C8_CARD_ID_INVALID",
        ),
        (
            "bad_c8",
            ("--mode", "render-card", "--card-id", "SC-SCN-001"),
            "INVALID_OUTPUT_CONTRACT",
        ),
        (
            "none",
            ("--card-id", "SC-SCN-001"),
            "MODE_ARGUMENT_CONFLICT",
        ),
    ],
)
def test_render_card_failures_preserve_existing_output_and_leave_no_tmp(
    tmp_path: Path,
    damage: str,
    extra_args: tuple[str, ...],
    error_code: str,
) -> None:
    prototype = scene_export_tool.execute(_request())
    if damage == "duplicate":
        prototype["cards"][1]["card_id"] = prototype["cards"][0]["card_id"]
    elif damage == "missing_card_id":
        prototype["cards"][0].pop("card_id")
    elif damage == "bad_c8":
        prototype["contract"] = "BROKEN"
    input_path = tmp_path / f"{error_code}-input.json"
    output_path = tmp_path / f"{error_code}-existing.txt"
    input_path.write_text(json.dumps(prototype, ensure_ascii=False), encoding="utf-8")
    original = b"keep-existing-output\n"
    output_path.write_bytes(original)

    completed = _run_cli(
        *extra_args,
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    )

    assert completed.returncode == 2
    assert error_code.encode() in completed.stderr
    assert output_path.read_bytes() == original
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []


def test_empty_card_id_and_atomic_replace_failure_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prototype = scene_export_tool.execute(_request())
    with pytest.raises(
        scene_export_tool.SceneExportToolError,
        match="CARD_ID_INVALID",
    ):
        scene_export_tool.render_card(prototype, " ")

    output_path = tmp_path / "existing-card.txt"
    original = b"existing\n"
    output_path.write_bytes(original)

    def fail_replace(*args, **kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(scene_export_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        scene_export_tool._write_text_atomic(output_path, "new text\n")
    assert output_path.read_bytes() == original
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []


def test_render_all_three_cards_preserves_order_headers_and_core_content() -> None:
    prototype = _three_card_prototype()
    before = copy.deepcopy(prototype)

    markdown = scene_export_tool.render_all(prototype)

    assert prototype == before
    assert markdown.startswith("# 雨夜送信｜M10 场景卡\n")
    assert "- 卡片总数：3" in markdown
    assert "- 章节：1" in markdown
    card_ids = [card["card_id"] for card in prototype["cards"]]
    headings = [f"## 场景卡 {index} · `{card_id}`" for index, card_id in enumerate(card_ids, 1)]
    assert [markdown.index(heading) for heading in headings] == sorted(
        markdown.index(heading) for heading in headings
    )
    assert markdown.count("\n\n---\n\n") == 2
    for index, card_id in enumerate(card_ids, 1):
        assert _markdown_card_body(markdown, index, card_id) == (
            scene_export.render_scene_card(prototype, index - 1)
        )

    second_body = _markdown_card_body(markdown, 2, card_ids[1])
    assert "旧码头" in second_body
    assert "纸灯巷" not in second_body
    assert "许岚" not in second_body
    assert "透露第1场必须知道的信息点" not in second_body


def test_render_all_cli_file_and_stdout_are_cross_process_byte_stable(
    tmp_path: Path,
) -> None:
    prototype = _three_card_prototype()
    input_path = tmp_path / "c8-three-cards.json"
    first_path = tmp_path / "all-cards-first.md"
    second_path = tmp_path / "all-cards-second.md"
    input_path.write_text(json.dumps(prototype, ensure_ascii=False), encoding="utf-8")
    args = ("--mode", "render-all", "--input", str(input_path))

    first = _run_cli(*args, "--output", str(first_path))
    second = _run_cli(*args, "--output", str(second_path))
    stdout = _run_cli(*args)

    assert first.returncode == second.returncode == stdout.returncode == 0
    expected = scene_export_tool.render_all(prototype).encode()
    assert first_path.read_bytes() == second_path.read_bytes() == stdout.stdout == expected


@pytest.mark.parametrize(
    ("damage", "extra_args", "error_code"),
    [
        ("duplicate", (), "CARD_ID_NOT_UNIQUE"),
        ("empty", (), "INVALID_OUTPUT_CARDS"),
        ("bad_c8", (), "INVALID_OUTPUT_CONTRACT"),
        (
            "none",
            ("--card-id", "SC-SCN-001"),
            "MODE_ARGUMENT_CONFLICT",
        ),
    ],
)
def test_render_all_failures_preserve_existing_output_and_leave_no_tmp(
    tmp_path: Path,
    damage: str,
    extra_args: tuple[str, ...],
    error_code: str,
) -> None:
    prototype = _three_card_prototype()
    if damage == "duplicate":
        prototype["cards"][1]["card_id"] = prototype["cards"][0]["card_id"]
    elif damage == "empty":
        prototype["cards"] = []
    elif damage == "bad_c8":
        prototype["contract"] = "BROKEN"
    input_path = tmp_path / f"render-all-{error_code}.json"
    output_path = tmp_path / f"render-all-{error_code}.md"
    input_path.write_text(json.dumps(prototype, ensure_ascii=False), encoding="utf-8")
    original = b"keep-existing-markdown\n"
    output_path.write_bytes(original)

    completed = _run_cli(
        "--mode",
        "render-all",
        *extra_args,
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    )

    assert completed.returncode == 2
    assert error_code.encode() in completed.stderr
    assert output_path.read_bytes() == original
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []
