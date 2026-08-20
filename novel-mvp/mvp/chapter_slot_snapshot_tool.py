"""plan-v2 章槽只读快照的纯对象核心与本地文件适配层。"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn

from jsonschema import Draft202012Validator


if __package__:
    from . import planstore
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import planstore


CONTRACT = "CHAPTER_SLOT_SNAPSHOT"
VERSION = "v1"
SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "contracts"
    / "CHAPTER_SLOT_SNAPSHOT.schema.json"
)
REQUEST_KEYS = {
    "plan",
    "slot_ref",
    "source_plan_version",
    "source_plan_sha256",
}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
FORBIDDEN_TRUTH_KEYS = {
    "facts",
    "actual",
    "actuality",
    "confirmed",
    "confirmation_status",
}
SCENE_OPTIONAL_FIELDS = {
    "location",
    "characters",
    "mood_in",
    "mood_out",
    "visual_hint",
    "dialogue_hints",
    "resistance",
    "turn",
    "pov",
    "spoiler_notes",
    "word_estimate",
}
EVENT_OPTIONAL_FIELDS = {
    "storyline_ref",
    "purpose",
    "story_time_hint",
    "origin_ref",
    "repair_ref",
    "deviation_note",
    "defer_count",
}


class ChapterSlotSnapshotError(ValueError):
    """输入无法在不猜语义的前提下投影为章槽快照。"""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _fail(code: str, detail: str = "") -> NoReturn:
    raise ChapterSlotSnapshotError(code, detail)


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ChapterSlotSnapshotError("VALUE_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail("REVISION_INVALID", field)
    return value


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("INTEGER_INVALID", field)
    return value


def _plain_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("INTEGER_INVALID", field)
    return value


def _string(value: Any, field: str, *, non_empty: bool = False) -> str:
    if not isinstance(value, str) or (non_empty and not value):
        _fail("STRING_INVALID", field)
    return value


def _nullable_string(value: Any, field: str) -> str | None:
    if value is not None and not isinstance(value, str):
        _fail("STRING_OR_NULL_INVALID", field)
    return value


def _unique_strings(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        _fail("REFERENCE_LIST_INVALID", field)
    if len(value) != len(set(value)):
        _fail("DUPLICATE_REFERENCE", field)
    return list(value)


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _fail("STRING_LIST_INVALID", field)
    return list(value)


def _index_unique(rows: Any, label: str) -> dict[str, dict]:
    if not isinstance(rows, list):
        _fail("PLAN_COLLECTION_INVALID", label)
    result: dict[str, dict] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail("PLAN_OBJECT_INVALID", f"{label}[{index}]")
        object_id = _string(row.get("id"), f"{label}[{index}].id", non_empty=True)
        if object_id in result:
            _fail("DUPLICATE_OBJECT_ID", f"{label}:{object_id}")
        result[object_id] = row
    return result


def _reject_truth_fields(value: Any, path: str = "plan") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_TRUTH_KEYS:
                _fail("TRUTH_FIELD_FORBIDDEN", f"{path}.{key}")
            _reject_truth_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_truth_fields(child, f"{path}[{index}]")


def _outline_checkpoint(value: Any, slot_ref: str) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {
        "outline_rev",
        "source_slot_ref",
        "source_commit_seq",
    }:
        _fail("OUTLINE_CHECKPOINT_INVALID")
    if value.get("source_slot_ref") != slot_ref:
        _fail("OUTLINE_CHECKPOINT_SLOT_MISMATCH")
    _positive_int(value.get("outline_rev"), "outline_checkpoint.outline_rev")
    _integer(
        value.get("source_commit_seq"),
        "outline_checkpoint.source_commit_seq",
    )
    return copy.deepcopy(value)


def _scene_slice(scene: dict, slot_ref: str) -> dict:
    if scene.get("slot_ref") != slot_ref:
        _fail("SCENE_SLOT_MISMATCH", str(scene.get("id")))
    result = {
        "id": _string(scene.get("id"), "scene.id", non_empty=True),
        "rev": _positive_int(scene.get("rev"), f"scene[{scene.get('id')}].rev"),
        "slot_ref": slot_ref,
        "goal": _string(scene.get("goal"), f"scene[{scene.get('id')}].goal"),
        "summary": _string(
            scene.get("summary"), f"scene[{scene.get('id')}].summary"
        ),
        "pe_refs": _unique_strings(
            scene.get("pe_refs"), f"scene[{scene.get('id')}].pe_refs"
        ),
    }
    for field in SCENE_OPTIONAL_FIELDS & set(scene):
        result[field] = copy.deepcopy(scene[field])
    return result


def _event_slice(event: dict, scene_ref: str, storyline_refs: set[str]) -> dict:
    if event.get("scene_ref") != scene_ref:
        _fail("EVENT_SCENE_MISMATCH", str(event.get("id")))
    storyline_ref = event.get("storyline_ref")
    if storyline_ref is not None and storyline_ref not in storyline_refs:
        _fail("EVENT_STORYLINE_NOT_IN_SLOT", str(event.get("id")))
    result = {
        "id": _string(event.get("id"), "event.id", non_empty=True),
        "rev": _positive_int(event.get("rev"), f"event[{event.get('id')}].rev"),
        "scene_ref": scene_ref,
        "text": _string(event.get("text"), f"event[{event.get('id')}].text"),
    }
    for field in EVENT_OPTIONAL_FIELDS & set(event):
        result[field] = copy.deepcopy(event[field])
    return result


def _storyline_slice(storyline: dict) -> dict:
    storyline_id = _string(storyline.get("id"), "storyline.id", non_empty=True)
    alias = _nullable_string(storyline.get("alias"), f"storyline[{storyline_id}].alias")
    priority = _plain_integer(
        storyline.get("priority"), f"storyline[{storyline_id}].priority"
    )
    line_status = storyline.get("line_status")
    if line_status not in {"active", "paused", "converged", "merged"}:
        _fail("STORYLINE_STATUS_INVALID", storyline_id)
    return {
        "id": storyline_id,
        "rev": _positive_int(
            storyline.get("rev"), f"storyline[{storyline_id}].rev"
        ),
        "name": _string(storyline.get("name"), f"storyline[{storyline_id}].name"),
        "alias": alias,
        "priority": priority,
        "members": _unique_strings(
            storyline.get("members"), f"storyline[{storyline_id}].members"
        ),
        "line_status": line_status,
    }


def _validate_output(value: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path) or "$"
        _fail("OUTPUT_SCHEMA_INVALID", f"{path}:{first.message}")


def execute(request: dict) -> dict:
    """纯对象投影：合法 plan-v2＋稳定槽引用 → 只读章槽快照。"""
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        _fail("REQUEST_FIELDS_INVALID")
    plan = copy.deepcopy(request.get("plan"))
    if not isinstance(plan, dict):
        _fail("PLAN_OBJECT_REQUIRED")
    slot_ref = _string(request.get("slot_ref"), "slot_ref", non_empty=True)
    source_version = _positive_int(
        request.get("source_plan_version"), "source_plan_version"
    )
    source_sha = request.get("source_plan_sha256")
    if not isinstance(source_sha, str) or SHA256_RE.fullmatch(source_sha) is None:
        _fail("SOURCE_PLAN_SHA_INVALID")
    if _sha256(plan) != source_sha:
        _fail("SOURCE_PLAN_SHA_MISMATCH")

    _reject_truth_fields(plan)
    try:
        planstore._validate_plan(plan)
    except planstore.PlanstoreError as exc:
        _fail("PLAN_INVALID", str(exc))

    slots = _index_unique(plan.get("slots"), "slots")
    scenes = _index_unique(plan.get("scenes"), "scenes")
    events = _index_unique(plan.get("events"), "events")
    storylines = _index_unique(plan.get("storylines"), "storylines")
    slot = slots.get(slot_ref)
    if slot is None:
        _fail("SLOT_NOT_FOUND", slot_ref)

    slot_rev = _positive_int(slot.get("rev"), "slot.rev")
    scene_refs = _unique_strings(slot.get("scene_refs"), "slot.scene_refs")
    storyline_refs = _unique_strings(
        slot.get("storyline_refs"), "slot.storyline_refs"
    )
    must_not = _string_list(slot.get("must_not"), "slot.must_not")
    risks = _string_list(slot.get("risks"), "slot.risks")
    checkpoint = _outline_checkpoint(slot.get("outline_checkpoint"), slot_ref)

    scene_slices: list[dict] = []
    event_slices: list[dict] = []
    event_refs: list[str] = []
    seen_event_refs: set[str] = set()
    for scene_ref in scene_refs:
        scene = scenes.get(scene_ref)
        if scene is None:
            _fail("SCENE_NOT_FOUND", scene_ref)
        scene_slice = _scene_slice(scene, slot_ref)
        scene_slices.append(scene_slice)
        for event_ref in scene_slice["pe_refs"]:
            if event_ref in seen_event_refs:
                _fail("DUPLICATE_REFERENCE", f"events:{event_ref}")
            seen_event_refs.add(event_ref)
            event = events.get(event_ref)
            if event is None:
                _fail("EVENT_NOT_FOUND", event_ref)
            event_slices.append(
                _event_slice(event, scene_ref, set(storyline_refs))
            )
            event_refs.append(event_ref)

    storyline_slices = []
    for storyline_ref in storyline_refs:
        storyline = storylines.get(storyline_ref)
        if storyline is None:
            _fail("STORYLINE_NOT_FOUND", storyline_ref)
        storyline_slices.append(_storyline_slice(storyline))

    outline_source_commit_seq = (
        None if checkpoint is None else checkpoint["source_commit_seq"]
    )
    output = {
        "contract": CONTRACT,
        "version": VERSION,
        "status": "plan",
        "source_plan_version": source_version,
        "source_plan_sha256": source_sha,
        "generation_watermark": {
            "source_plan_version": source_version,
            "source_plan_sha256": source_sha,
            "slot_rev": slot_rev,
            "outline_source_commit_seq": outline_source_commit_seq,
        },
        "basis_refs": {
            "slot_ref": slot_ref,
            "scene_refs": scene_refs,
            "event_refs": event_refs,
            "storyline_refs": storyline_refs,
        },
        "slot_ref": slot_ref,
        "slot_rev": slot_rev,
        "goal": _string(slot.get("goal"), "slot.goal"),
        "summary": _string(slot.get("summary"), "slot.summary"),
        "entry_state": _nullable_string(slot.get("entry_state"), "slot.entry_state"),
        "exit_condition": _nullable_string(
            slot.get("exit_condition"), "slot.exit_condition"
        ),
        "exit_hook": _nullable_string(slot.get("exit_hook"), "slot.exit_hook"),
        "storyline_refs": storyline_refs,
        "scene_refs": scene_refs,
        "must_not": must_not,
        "risks": risks,
        "outline_checkpoint": checkpoint,
        "scenes": scene_slices,
        "events": event_slices,
        "storylines": storyline_slices,
    }
    _validate_output(output)
    return output


# LOCAL_FILESYSTEM_ONLY: 只做本地 JSON 文件适配；核心 execute 不接路径。
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
        raise ChapterSlotSnapshotError("INPUT_JSON_INVALID") from exc
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
    parser = argparse.ArgumentParser(description="导出 plan-v2 章槽只读快照")
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
    except (OSError, ChapterSlotSnapshotError) as exc:
        print(f"CHAPTER_SLOT_SNAPSHOT_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
