"""CHAPTER_SLOT_SNAPSHOT → m10-scene-slice-r1 的显式补料薄适配器。"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn

from jsonschema import Draft202012Validator


if __package__:
    from . import scene_export, scene_export_tool
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import scene_export, scene_export_tool


SNAPSHOT_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "contracts"
    / "CHAPTER_SLOT_SNAPSHOT.schema.json"
)
REQUEST_KEYS = {
    "chapter_slot_snapshot",
    "anchors",
    "export_context",
    "scene_bindings",
    "event_bindings",
}
EXPORT_CONTEXT_KEYS = {
    "project",
    "generated_at",
    "model",
    "book_title",
    "plan_id",
    "basis_note",
    "chapter_hint",
    "chapter_title",
}
SCENE_BINDING_KEYS = {
    "scene_ref",
    "location_anchor_ref",
    "time",
    "character_presence",
    "writing_guidance",
}
EVENT_BINDING_KEYS = {
    "event_ref",
    "visual",
    "shot_hint",
    "dialogue_bindings",
}
DIALOGUE_BINDING_KEYS = {"id", "info", "speaker_ref", "tone"}


class M10SceneSliceAdapterError(ValueError):
    """显式补料不足、歧义或与章槽快照不一致。"""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _fail(code: str, detail: str = "") -> NoReturn:
    raise M10SceneSliceAdapterError(code, detail)


def _mapping(value: Any, field: str, *, keys: set[str] | None = None) -> dict:
    if not isinstance(value, dict):
        _fail("OBJECT_REQUIRED", field)
    if keys is not None and set(value) != keys:
        _fail("FIELDS_INVALID", field)
    return value


def _list(value: Any, field: str) -> list:
    if not isinstance(value, list):
        _fail("ARRAY_REQUIRED", field)
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail("TEXT_REQUIRED", field)
    return value


def _text_list(value: Any, field: str, *, unique: bool = False) -> list[str]:
    rows = _list(value, field)
    if any(
        not isinstance(item, str) or not item.strip() or item != item.strip()
        for item in rows
    ):
        _fail("TEXT_ARRAY_INVALID", field)
    if unique and len(rows) != len(set(rows)):
        _fail("DUPLICATE_REFERENCE", field)
    return list(rows)


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail("POSITIVE_INTEGER_REQUIRED", field)
    return value


def _index_exact(rows: Any, field: str, ref_field: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for index, raw in enumerate(_list(rows, field)):
        row = _mapping(raw, f"{field}[{index}]")
        ref = _text(row.get(ref_field), f"{field}[{index}].{ref_field}")
        if ref in result:
            _fail("DUPLICATE_BINDING", f"{field}:{ref}")
        result[ref] = row
    return result


def _validate_snapshot(snapshot: dict) -> None:
    if snapshot.get("contract") != "CHAPTER_SLOT_SNAPSHOT":
        _fail("CHAPTER_SLOT_SNAPSHOT_REQUIRED")
    schema = json.loads(SNAPSHOT_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(snapshot),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path) or "$"
        _fail("SNAPSHOT_SCHEMA_INVALID", f"{path}:{first.message}")

    watermark = snapshot["generation_watermark"]
    if (
        watermark["source_plan_version"] != snapshot["source_plan_version"]
        or watermark["source_plan_sha256"] != snapshot["source_plan_sha256"]
        or watermark["slot_rev"] != snapshot["slot_rev"]
    ):
        _fail("SNAPSHOT_WATERMARK_MISMATCH")
    basis = snapshot["basis_refs"]
    if (
        basis["slot_ref"] != snapshot["slot_ref"]
        or basis["scene_refs"] != snapshot["scene_refs"]
        or basis["storyline_refs"] != snapshot["storyline_refs"]
    ):
        _fail("SNAPSHOT_BASIS_MISMATCH")

    scenes = _index_exact(snapshot["scenes"], "snapshot.scenes", "id")
    events = _index_exact(snapshot["events"], "snapshot.events", "id")
    if not snapshot["scene_refs"] or not scenes:
        _fail("EMPTY_CHAPTER_SLOT_SNAPSHOT")
    if list(scenes) != snapshot["scene_refs"]:
        _fail("SNAPSHOT_SCENE_ORDER_MISMATCH")

    ordered_event_refs: list[str] = []
    for scene_ref in snapshot["scene_refs"]:
        scene = scenes[scene_ref]
        if scene["slot_ref"] != snapshot["slot_ref"]:
            _fail("SNAPSHOT_SCENE_SLOT_MISMATCH", scene_ref)
        for event_ref in scene["pe_refs"]:
            if event_ref in ordered_event_refs:
                _fail("DUPLICATE_EVENT_REFERENCE", event_ref)
            event = events.get(event_ref)
            if event is None:
                _fail("SNAPSHOT_EVENT_NOT_FOUND", event_ref)
            if event["scene_ref"] != scene_ref:
                _fail("SNAPSHOT_EVENT_SCENE_MISMATCH", event_ref)
            ordered_event_refs.append(event_ref)
    if list(events) != ordered_event_refs or basis["event_refs"] != ordered_event_refs:
        _fail("SNAPSHOT_EVENT_ORDER_MISMATCH")


def _anchor_indexes(anchors: list) -> tuple[dict[str, dict], dict[str, dict]]:
    by_id: dict[str, dict] = {}
    character_by_entity: dict[str, dict] = {}
    entity_refs: set[str] = set()
    for index, raw in enumerate(anchors):
        anchor = _mapping(raw, f"anchors[{index}]")
        anchor_id = _text(anchor.get("anchor_id"), f"anchors[{index}].anchor_id")
        entity_ref = _text(anchor.get("entity_ref"), f"anchors[{index}].entity_ref")
        kind = anchor.get("kind")
        if kind not in {"character", "location"}:
            _fail("ANCHOR_KIND_INVALID", anchor_id)
        if anchor_id in by_id:
            _fail("DUPLICATE_ANCHOR_ID", anchor_id)
        if entity_ref in entity_refs:
            _fail("DUPLICATE_ANCHOR_ENTITY", entity_ref)
        by_id[anchor_id] = anchor
        entity_refs.add(entity_ref)
        if kind == "character":
            character_by_entity[entity_ref] = anchor
    return by_id, character_by_entity


def _complete_bindings(
    actual: dict[str, dict], expected_refs: list[str], label: str
) -> None:
    expected = set(expected_refs)
    if set(actual) != expected:
        missing = sorted(expected - set(actual))
        extra = sorted(set(actual) - expected)
        _fail(f"{label}_INCOMPLETE", f"missing={missing}:extra={extra}")


def execute(request: dict) -> dict:
    """把章槽快照和显式绑定转换为现役 scene_export_tool 请求。"""
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        _fail("REQUEST_FIELDS_INVALID")
    snapshot = copy.deepcopy(
        _mapping(request.get("chapter_slot_snapshot"), "chapter_slot_snapshot")
    )
    _validate_snapshot(snapshot)
    anchors = copy.deepcopy(_list(request.get("anchors"), "anchors"))
    anchor_by_id, character_by_entity = _anchor_indexes(anchors)
    context = _mapping(
        copy.deepcopy(request.get("export_context")),
        "export_context",
        keys=EXPORT_CONTEXT_KEYS,
    )
    chapter_hint = _positive_int(context["chapter_hint"], "export_context.chapter_hint")
    for field in EXPORT_CONTEXT_KEYS - {"chapter_hint"}:
        _text(context[field], f"export_context.{field}")

    scene_bindings = _index_exact(
        copy.deepcopy(request.get("scene_bindings")),
        "scene_bindings",
        "scene_ref",
    )
    event_bindings = _index_exact(
        copy.deepcopy(request.get("event_bindings")),
        "event_bindings",
        "event_ref",
    )
    _complete_bindings(scene_bindings, snapshot["scene_refs"], "SCENE_BINDINGS")
    _complete_bindings(
        event_bindings, snapshot["basis_refs"]["event_refs"], "EVENT_BINDINGS"
    )
    for binding in scene_bindings.values():
        if set(binding) != SCENE_BINDING_KEYS:
            _fail("FIELDS_INVALID", f"scene_binding:{binding.get('scene_ref')}")
    for binding in event_bindings.values():
        if set(binding) != EVENT_BINDING_KEYS:
            _fail("FIELDS_INVALID", f"event_binding:{binding.get('event_ref')}")

    snapshot_scenes = {scene["id"]: scene for scene in snapshot["scenes"]}
    snapshot_events = {event["id"]: event for event in snapshot["events"]}
    normalized_scenes: list[dict] = []
    normalized_events: list[dict] = []
    scene_count = len(snapshot["scene_refs"])
    global_dialogue_ids: set[str] = set()
    for scene_order, scene_ref in enumerate(snapshot["scene_refs"], start=1):
        scene = snapshot_scenes[scene_ref]
        binding = scene_bindings[scene_ref]
        location_ref = _text(
            binding["location_anchor_ref"],
            f"scene_bindings[{scene_ref}].location_anchor_ref",
        )
        location_anchor = anchor_by_id.get(location_ref)
        if location_anchor is None or location_anchor.get("kind") != "location":
            _fail("LOCATION_ANCHOR_MISSING", location_ref)

        characters = _text_list(
            scene.get("characters"), f"snapshot.scenes[{scene_ref}].characters", unique=True
        )
        if not characters:
            _fail("SCENE_CHARACTERS_REQUIRED", scene_ref)
        for character_ref in characters:
            if character_ref not in character_by_entity:
                _fail("CHARACTER_ANCHOR_MISSING", character_ref)
        presence = _mapping(
            binding["character_presence"],
            f"scene_bindings[{scene_ref}].character_presence",
        )
        if set(presence) != set(characters):
            _fail("CHARACTER_PRESENCE_INCOMPLETE", scene_ref)
        for character_ref, description in presence.items():
            _text(
                description,
                f"scene_bindings[{scene_ref}].character_presence[{character_ref}]",
            )

        snapshot_dialogue = _text_list(
            scene.get("dialogue_hints", []),
            f"snapshot.scenes[{scene_ref}].dialogue_hints",
            unique=True,
        )
        normalized_dialogue: list[dict] = []
        bound_dialogue_info: list[str] = []
        for event_ref in scene["pe_refs"]:
            event = snapshot_events[event_ref]
            event_binding = event_bindings[event_ref]
            dialogue_refs: list[str] = []
            for index, raw_dialogue in enumerate(
                _list(
                    event_binding["dialogue_bindings"],
                    f"event_bindings[{event_ref}].dialogue_bindings",
                )
            ):
                dialogue = _mapping(
                    raw_dialogue,
                    f"event_bindings[{event_ref}].dialogue_bindings[{index}]",
                    keys=DIALOGUE_BINDING_KEYS,
                )
                hint_id = _text(dialogue["id"], f"dialogue[{event_ref}][{index}].id")
                if hint_id in global_dialogue_ids:
                    _fail("DUPLICATE_DIALOGUE_BINDING_ID", hint_id)
                global_dialogue_ids.add(hint_id)
                info = _text(dialogue["info"], f"dialogue[{hint_id}].info")
                speaker_ref = _text(
                    dialogue["speaker_ref"], f"dialogue[{hint_id}].speaker_ref"
                )
                if speaker_ref not in characters:
                    _fail("DIALOGUE_SPEAKER_NOT_IN_SCENE", hint_id)
                if speaker_ref not in character_by_entity:
                    _fail("CHARACTER_ANCHOR_MISSING", speaker_ref)
                tone = _text(dialogue["tone"], f"dialogue[{hint_id}].tone")
                normalized_dialogue.append(
                    {
                        "id": hint_id,
                        "kind": "information_point",
                        "speaker_ref": speaker_ref,
                        "info": info,
                        "tone": tone,
                    }
                )
                bound_dialogue_info.append(info)
                dialogue_refs.append(hint_id)
            normalized_events.append(
                {
                    "id": event_ref,
                    "scene_ref": scene_ref,
                    "action": event["text"],
                    "visual": _text(
                        event_binding["visual"], f"event_bindings[{event_ref}].visual"
                    ),
                    "dialogue_hint_refs": dialogue_refs,
                    "shot_hint": _text(
                        event_binding["shot_hint"],
                        f"event_bindings[{event_ref}].shot_hint",
                    ),
                }
            )
        if bound_dialogue_info != snapshot_dialogue:
            _fail("DIALOGUE_BINDING_INCOMPLETE", scene_ref)

        spoiler_notes = _text_list(
            scene.get("spoiler_notes", []),
            f"snapshot.scenes[{scene_ref}].spoiler_notes",
        )
        writing_guidance = _text_list(
            binding["writing_guidance"],
            f"scene_bindings[{scene_ref}].writing_guidance",
        )
        normalized_scenes.append(
            {
                "id": scene_ref,
                "chapter_hint": chapter_hint,
                "chapter_title": context["chapter_title"],
                "scene_order": scene_order,
                "scene_count": scene_count,
                "goal": scene["goal"],
                "summary": scene["summary"],
                "location_ref": location_ref,
                "time": _text(binding["time"], f"scene_bindings[{scene_ref}].time"),
                "visual_hint": _text(
                    scene.get("visual_hint"), f"snapshot.scenes[{scene_ref}].visual_hint"
                ),
                "characters": characters,
                "character_presence": copy.deepcopy(presence),
                "mood_in": _text(
                    scene.get("mood_in"), f"snapshot.scenes[{scene_ref}].mood_in"
                ),
                "mood_out": _text(
                    scene.get("mood_out"), f"snapshot.scenes[{scene_ref}].mood_out"
                ),
                "turn": _text(scene.get("turn"), f"snapshot.scenes[{scene_ref}].turn"),
                "pov": _text(scene.get("pov"), f"snapshot.scenes[{scene_ref}].pov"),
                "resistance": _text(
                    scene.get("resistance"),
                    f"snapshot.scenes[{scene_ref}].resistance",
                ),
                "writing_guidance": writing_guidance,
                "spoiler_guard": [
                    {
                        "audience_state": "known_at_scene",
                        "instruction": note,
                    }
                    for note in spoiler_notes
                ],
                "dialogue_hints": normalized_dialogue,
                "pe_refs": list(scene["pe_refs"]),
            }
        )

    source = {
        "contract": scene_export.SOURCE_CONTRACT,
        "scene_export_slice": scene_export.SOURCE_SLICE,
        "project": context["project"],
        "generated_at": context["generated_at"],
        "model": context["model"],
        "book_title": context["book_title"],
        "plan_id": context["plan_id"],
        "basis_note": context["basis_note"],
        "anchors": anchors,
        "scenes": normalized_scenes,
        "planned_events": normalized_events,
    }
    output_request = {"source": source}
    scene_export_tool.execute(copy.deepcopy(output_request))
    return output_request


# LOCAL_FILESYSTEM_ONLY: 只把本地 JSON 文件适配到纯对象 execute。
def _load_request(input_path: str | None) -> dict:
    if input_path in {None, "-"}:
        raw = sys.stdin.buffer.read()
    else:
        path = Path(input_path)
        if not path.is_file():
            _fail("INPUT_PATH_NOT_FILE", str(path))
        raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise M10SceneSliceAdapterError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        _fail("REQUEST_OBJECT_REQUIRED")
    return value


def _output_bytes(value: dict) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_atomic(path: Path, value: dict) -> None:
    if not path.parent.is_dir():
        _fail("OUTPUT_PARENT_NOT_DIRECTORY", str(path.parent))
    if path.exists() and not path.is_file():
        _fail("OUTPUT_PATH_NOT_FILE", str(path))
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(_output_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _validate_paths(input_path: str | None, output_path: str | None) -> None:
    if input_path in {None, "-"} or output_path in {None, "-"}:
        return
    if Path(input_path).resolve() == Path(output_path).resolve():
        _fail("INPUT_OUTPUT_PATH_MUST_DIFFER")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把章槽快照和显式补料转换成 M10 输入")
    parser.add_argument("--input", help="输入 JSON；省略或 - 表示 stdin")
    parser.add_argument("--output", help="输出 JSON；省略或 - 表示 stdout")
    args = parser.parse_args(argv)
    try:
        _validate_paths(args.input, args.output)
        result = execute(_load_request(args.input))
        if args.output in {None, "-"}:
            sys.stdout.buffer.write(_output_bytes(result))
            sys.stdout.buffer.flush()
        else:
            _write_atomic(Path(args.output), result)
    except (
        OSError,
        M10SceneSliceAdapterError,
        scene_export.SceneExportError,
        scene_export_tool.SceneExportToolError,
    ) as exc:
        print(f"M10_SCENE_SLICE_ADAPTER_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
