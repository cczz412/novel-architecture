"""把 current 工作稿与 current 章槽快照冻结为检测输入包。

本工具只编译机械输入：作者原文、计划水位、PE 事件与 must_not
约束。它不执行检测，不生成 WRITING_DESK_CHECK_RESULT，也不读写工作区。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn

if __package__:
    from . import chapter_slot_snapshot_tool, work_draft_workspace
    from .workspace import OPERATION_ID_RE
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import chapter_slot_snapshot_tool, work_draft_workspace
    from mvp.workspace import OPERATION_ID_RE


PROTOTYPE_IDENTITY = "WRITING_CHECK_INPUT_PACKAGE_PROTOTYPE_R01"
REQUEST_KEYS = {"work_draft", "chapter_slot_snapshot", "check_operation_id"}


class WritingCheckPackageError(ValueError):
    """检测输入尚不能安全冻结。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise WritingCheckPackageError(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise WritingCheckPackageError("VALUE_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validated_work_draft(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("WRITING_DESK_WORK_DRAFT_REQUIRED")
    candidate = copy.deepcopy(value)
    work_rev = candidate.get("work_rev")
    if isinstance(work_rev, bool) or not isinstance(work_rev, int) or work_rev < 1:
        _fail("WORK_DRAFT_REVISION_INVALID")
    try:
        validated = work_draft_workspace._validated_entry(
            {
                "logical_key": "draft",
                "version": work_rev,
                "sha256": _sha256_bytes(_canonical_bytes(candidate)),
                "payload": candidate,
            }
        )
    except work_draft_workspace.WorkDraftWorkspaceError as exc:
        raise WritingCheckPackageError(f"WORK_DRAFT_INVALID:{exc.code}") from exc
    return validated["current_work_draft"]


def _validated_slot_snapshot(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("CHAPTER_SLOT_SNAPSHOT_REQUIRED")
    snapshot = copy.deepcopy(value)
    try:
        chapter_slot_snapshot_tool._validate_output(snapshot)
    except chapter_slot_snapshot_tool.ChapterSlotSnapshotError as exc:
        raise WritingCheckPackageError(
            f"CHAPTER_SLOT_SNAPSHOT_INVALID:{exc.code}"
        ) from exc

    watermark = snapshot["generation_watermark"]
    if (
        watermark["source_plan_version"] != snapshot["source_plan_version"]
        or watermark["source_plan_sha256"] != snapshot["source_plan_sha256"]
        or watermark["slot_rev"] != snapshot["slot_rev"]
    ):
        _fail("CHAPTER_SLOT_WATERMARK_MISMATCH")
    basis = snapshot["basis_refs"]
    if (
        basis["slot_ref"] != snapshot["slot_ref"]
        or basis["scene_refs"] != snapshot["scene_refs"]
        or basis["storyline_refs"] != snapshot["storyline_refs"]
    ):
        _fail("CHAPTER_SLOT_BASIS_MISMATCH")

    scenes: dict[str, dict[str, Any]] = {}
    for scene in snapshot["scenes"]:
        scene_id = scene["id"]
        if scene_id in scenes:
            _fail("CHAPTER_SLOT_DUPLICATE_SCENE")
        scenes[scene_id] = scene
    events: dict[str, dict[str, Any]] = {}
    for event in snapshot["events"]:
        event_id = event["id"]
        if event_id in events:
            _fail("DUPLICATE_REQUIREMENT_REF")
        events[event_id] = event
    if list(scenes) != snapshot["scene_refs"]:
        _fail("CHAPTER_SLOT_SCENE_ORDER_MISMATCH")

    ordered_event_refs: list[str] = []
    for scene_ref in snapshot["scene_refs"]:
        scene = scenes[scene_ref]
        if scene["slot_ref"] != snapshot["slot_ref"]:
            _fail("CHAPTER_SLOT_SCENE_MISMATCH")
        for event_ref in scene["pe_refs"]:
            if event_ref in ordered_event_refs:
                _fail("DUPLICATE_REQUIREMENT_REF")
            event = events.get(event_ref)
            if event is None or event["scene_ref"] != scene_ref:
                _fail("CHAPTER_SLOT_EVENT_BINDING_INVALID")
            ordered_event_refs.append(event_ref)
    if list(events) != ordered_event_refs or basis["event_refs"] != ordered_event_refs:
        _fail("CHAPTER_SLOT_EVENT_ORDER_MISMATCH")
    return snapshot


def _must_not_ref(source_outline_ref: str, text: str) -> str:
    digest = hashlib.sha256(b"must_not\0" + text.encode("utf-8")).hexdigest()[:12]
    return f"{source_outline_ref}#must_not:{digest}"


def _requirements(
    snapshot: dict[str, Any], source_outline_ref: str
) -> list[dict[str, str]]:
    rows = [
        {
            "requirement_ref": event["id"],
            "source_kind": "planned_event",
            "source_text": event["text"],
        }
        for event in snapshot["events"]
    ]
    rows.extend(
        {
            "requirement_ref": _must_not_ref(source_outline_ref, text),
            "source_kind": "must_not",
            "source_text": text,
        }
        for text in snapshot["must_not"]
    )
    refs = [row["requirement_ref"] for row in rows]
    if len(refs) != len(set(refs)):
        _fail("DUPLICATE_REQUIREMENT_REF")
    return rows


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """纯对象入口：冻结原文、章槽水位与机械 requirement。"""
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        _fail("REQUEST_FIELDS_INVALID")
    operation_id = request["check_operation_id"]
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        _fail("CHECK_OPERATION_ID_INVALID")
    draft = _validated_work_draft(request["work_draft"])
    snapshot = _validated_slot_snapshot(request["chapter_slot_snapshot"])
    if draft["slot_ref"] != snapshot["slot_ref"]:
        _fail("WORK_AND_SLOT_REF_MISMATCH")
    checkpoint = snapshot["outline_checkpoint"]
    if not isinstance(checkpoint, dict):
        _fail("CURRENT_OUTLINE_CHECKPOINT_REQUIRED")
    expected_outline_ref = (
        f"{snapshot['slot_ref']}@outline-r{checkpoint['outline_rev']}"
    )
    if draft["source_outline_ref"] != expected_outline_ref:
        _fail("SOURCE_OUTLINE_REF_STALE")
    if (
        snapshot["generation_watermark"]["outline_source_commit_seq"]
        != checkpoint["source_commit_seq"]
    ):
        _fail("OUTLINE_COMMIT_WATERMARK_MISMATCH")

    requirements = _requirements(snapshot, draft["source_outline_ref"])
    requirement_refs = [row["requirement_ref"] for row in requirements]
    package_core = {
        "identity": PROTOTYPE_IDENTITY,
        "prototype": True,
        "check_operation_id": operation_id,
        "work": {
            "slot_ref": draft["slot_ref"],
            "work_ref": draft["work_ref"],
            "work_rev": draft["work_rev"],
            "source_outline_ref": draft["source_outline_ref"],
            "text": draft["text"],
            "text_sha256": draft["text_sha256"],
        },
        "planning_source": {
            "source_plan_version": snapshot["source_plan_version"],
            "source_plan_sha256": snapshot["source_plan_sha256"],
            "generation_watermark": copy.deepcopy(
                snapshot["generation_watermark"]
            ),
            "source_commit_seq": checkpoint["source_commit_seq"],
        },
        "requirements": requirements,
        "scope": {
            "mode": "chapter",
            "target_ref": draft["slot_ref"],
            "requirement_refs": requirement_refs,
        },
    }
    return {
        **package_core,
        "input_package_sha256": _sha256_bytes(_canonical_bytes(package_core)),
    }


# LOCAL_FILESYSTEM_ONLY: 路径只在 CLI 适配层出现；纯对象 execute 不接路径。
def _load_request(input_path: str | None) -> dict[str, Any]:
    if input_path in {None, "-"}:
        raw = sys.stdin.buffer.read()
    else:
        path = Path(input_path)
        if not path.is_file():
            _fail("INPUT_PATH_NOT_FILE")
        raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WritingCheckPackageError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        _fail("INPUT_OBJECT_REQUIRED")
    return value


def _same_input_output_path(input_path: str | None, output_path: str | None) -> bool:
    if input_path in {None, "-"} or output_path in {None, "-"}:
        return False
    source = Path(input_path)
    target = Path(output_path)
    if source.resolve() == target.resolve():
        return True
    if source.exists() and target.exists():
        return os.path.samefile(source, target)
    return False


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_atomic(output_path: str | None, value: dict[str, Any]) -> None:
    payload = _canonical_bytes(value)
    if output_path in {None, "-"}:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
        return
    path = Path(output_path)
    if not path.parent.is_dir():
        _fail("OUTPUT_PARENT_NOT_DIRECTORY")
    if path.exists() and not path.is_file():
        _fail("OUTPUT_PATH_NOT_FILE")
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
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(path.parent)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="冻结工作稿与章槽为零 API 检测输入包"
    )
    parser.add_argument("--input", default="-")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    try:
        if _same_input_output_path(args.input, args.output):
            _fail("OUTPUT_MUST_NOT_OVERWRITE_INPUT")
        result = execute(_load_request(args.input))
        _write_atomic(args.output, result)
    except (OSError, WritingCheckPackageError) as exc:
        print(f"WRITING_CHECK_PACKAGE_ERROR:{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
