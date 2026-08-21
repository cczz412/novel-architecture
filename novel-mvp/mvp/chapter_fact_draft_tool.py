"""把作者明确填写的章事实句与规划水位冻结为非正式 prototype。

本工具只编译纯对象和本地 JSON 文件。它不写 AuthorWorkspace，不分配章节或
事实编号，也不产生 C1／C3／C4／C11 身份或确认结果。
"""

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


if __package__:
    from . import chapter_slot_snapshot_tool
else:  # 允许直接运行 python novel-mvp/mvp/chapter_fact_draft_tool.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import chapter_slot_snapshot_tool


PROTOTYPE_IDENTITY = "CHAPTER_FACT_DRAFT_PROTOTYPE_R01"
REQUEST_KEYS = {
    "operation_id",
    "actor",
    "chapter_slot_snapshot",
    "entries",
}
ENTRY_KEYS = {"fact_text", "writing_note"}
RESULT_KEYS = {
    "identity",
    "prototype",
    "operation_id",
    "actor",
    "slot",
    "planning_source",
    "entries",
    "effects",
    "prototype_sha256",
}
SLOT_KEYS = {"slot_ref", "slot_rev", "source_outline_ref"}
PLANNING_SOURCE_KEYS = {
    "source_plan_version",
    "source_plan_sha256",
    "chapter_slot_snapshot_sha256",
    "generation_watermark",
    "source_commit_seq",
}
WATERMARK_KEYS = {
    "source_plan_version",
    "source_plan_sha256",
    "slot_rev",
    "outline_source_commit_seq",
}
EFFECTS = {"c11": "none", "facts": "none", "plan": "none"}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
OPERATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


class ChapterFactDraftToolError(ValueError):
    """章事实稿 prototype 输入或本地文件适配不合法。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise ChapterFactDraftToolError(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ChapterFactDraftToolError("VALUE_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _validated_slot_snapshot(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("CHAPTER_SLOT_SNAPSHOT_REQUIRED")
    snapshot = copy.deepcopy(value)
    try:
        chapter_slot_snapshot_tool._validate_output(snapshot)
    except chapter_slot_snapshot_tool.ChapterSlotSnapshotError as exc:
        raise ChapterFactDraftToolError(
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
    if list(scenes) != snapshot["scene_refs"]:
        _fail("CHAPTER_SLOT_SCENE_ORDER_MISMATCH")

    events: dict[str, dict[str, Any]] = {}
    for event in snapshot["events"]:
        event_id = event["id"]
        if event_id in events:
            _fail("CHAPTER_SLOT_DUPLICATE_EVENT")
        events[event_id] = event

    ordered_event_refs: list[str] = []
    for scene_ref in snapshot["scene_refs"]:
        scene = scenes[scene_ref]
        if scene["slot_ref"] != snapshot["slot_ref"]:
            _fail("CHAPTER_SLOT_SCENE_MISMATCH")
        for event_ref in scene["pe_refs"]:
            if event_ref in ordered_event_refs:
                _fail("CHAPTER_SLOT_DUPLICATE_EVENT_REF")
            event = events.get(event_ref)
            if event is None or event["scene_ref"] != scene_ref:
                _fail("CHAPTER_SLOT_EVENT_BINDING_INVALID")
            ordered_event_refs.append(event_ref)
    if list(events) != ordered_event_refs or basis["event_refs"] != ordered_event_refs:
        _fail("CHAPTER_SLOT_EVENT_ORDER_MISMATCH")

    checkpoint = snapshot["outline_checkpoint"]
    if not isinstance(checkpoint, dict):
        _fail("CURRENT_OUTLINE_CHECKPOINT_REQUIRED")
    if checkpoint["source_slot_ref"] != snapshot["slot_ref"]:
        _fail("OUTLINE_CHECKPOINT_SLOT_MISMATCH")
    if watermark["outline_source_commit_seq"] != checkpoint["source_commit_seq"]:
        _fail("OUTLINE_COMMIT_WATERMARK_MISMATCH")
    return snapshot


def _validated_entries(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        _fail("ENTRIES_MUST_BE_NONEMPTY_ARRAY")
    entries: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != ENTRY_KEYS:
            _fail(f"ENTRY_FIELDS_INVALID:{index}")
        fact_text = item["fact_text"]
        writing_note = item["writing_note"]
        if not isinstance(fact_text, str) or not fact_text.strip():
            _fail(f"FACT_TEXT_INVALID:{index}")
        if not isinstance(writing_note, str):
            _fail(f"WRITING_NOTE_INVALID:{index}")
        entries.append(
            {
                "fact_text": fact_text,
                "writing_note": writing_note,
            }
        )
    return entries


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """冻结作者条目与规划水位；不执行交棒、确认或任何持久化。"""
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        _fail("REQUEST_FIELDS_INVALID")
    operation_id = request["operation_id"]
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        _fail("OPERATION_ID_INVALID")
    if request["actor"] != "author":
        _fail("AUTHOR_ACTOR_REQUIRED")

    snapshot = _validated_slot_snapshot(request["chapter_slot_snapshot"])
    entries = _validated_entries(request["entries"])
    checkpoint = snapshot["outline_checkpoint"]
    source_outline_ref = (
        f"{snapshot['slot_ref']}@outline-r{checkpoint['outline_rev']}"
    )
    package_core = {
        "identity": PROTOTYPE_IDENTITY,
        "prototype": True,
        "operation_id": operation_id,
        "actor": "author",
        "slot": {
            "slot_ref": snapshot["slot_ref"],
            "slot_rev": snapshot["slot_rev"],
            "source_outline_ref": source_outline_ref,
        },
        "planning_source": {
            "source_plan_version": snapshot["source_plan_version"],
            "source_plan_sha256": snapshot["source_plan_sha256"],
            "chapter_slot_snapshot_sha256": _sha256(snapshot),
            "generation_watermark": copy.deepcopy(
                snapshot["generation_watermark"]
            ),
            "source_commit_seq": checkpoint["source_commit_seq"],
        },
        "entries": entries,
        "effects": copy.deepcopy(EFFECTS),
    }
    return {
        **package_core,
        "prototype_sha256": _sha256(package_core),
    }


def _positive_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail(code)
    return value


def _non_negative_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(code)
    return value


def _sha256_text(value: object, code: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        _fail(code)
    return value


def validate_result(result: object) -> dict[str, Any]:
    """严格校验 prototype 全形状、水位、条目和自校验 SHA。"""
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        _fail("RESULT_FIELDS_INVALID")
    if result["identity"] != PROTOTYPE_IDENTITY or result["prototype"] is not True:
        _fail("RESULT_IDENTITY_INVALID")
    operation_id = result["operation_id"]
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        _fail("RESULT_OPERATION_ID_INVALID")
    if result["actor"] != "author":
        _fail("RESULT_ACTOR_INVALID")

    slot = result["slot"]
    if not isinstance(slot, dict) or set(slot) != SLOT_KEYS:
        _fail("RESULT_SLOT_INVALID")
    slot_ref = slot["slot_ref"]
    if not isinstance(slot_ref, str) or not slot_ref:
        _fail("RESULT_SLOT_INVALID")
    slot_rev = _positive_int(slot["slot_rev"], "RESULT_SLOT_INVALID")
    source_outline_ref = slot["source_outline_ref"]
    outline_prefix = f"{slot_ref}@outline-r"
    if (
        not isinstance(source_outline_ref, str)
        or not source_outline_ref.startswith(outline_prefix)
        or not source_outline_ref.removeprefix(outline_prefix).isdigit()
        or int(source_outline_ref.removeprefix(outline_prefix)) < 1
    ):
        _fail("RESULT_OUTLINE_REF_INVALID")

    planning = result["planning_source"]
    if not isinstance(planning, dict) or set(planning) != PLANNING_SOURCE_KEYS:
        _fail("RESULT_PLANNING_SOURCE_INVALID")
    source_plan_version = _positive_int(
        planning["source_plan_version"], "RESULT_PLANNING_SOURCE_INVALID"
    )
    source_plan_sha = _sha256_text(
        planning["source_plan_sha256"], "RESULT_PLANNING_SOURCE_INVALID"
    )
    _sha256_text(
        planning["chapter_slot_snapshot_sha256"],
        "RESULT_PLANNING_SOURCE_INVALID",
    )
    source_commit_seq = _non_negative_int(
        planning["source_commit_seq"], "RESULT_PLANNING_SOURCE_INVALID"
    )
    watermark = planning["generation_watermark"]
    if not isinstance(watermark, dict) or set(watermark) != WATERMARK_KEYS:
        _fail("RESULT_WATERMARK_INVALID")
    if (
        watermark["source_plan_version"] != source_plan_version
        or watermark["source_plan_sha256"] != source_plan_sha
        or watermark["slot_rev"] != slot_rev
        or watermark["outline_source_commit_seq"] != source_commit_seq
    ):
        _fail("RESULT_WATERMARK_MISMATCH")

    entries = _validated_entries(result["entries"])
    if result["effects"] != EFFECTS:
        _fail("RESULT_EFFECTS_INVALID")
    prototype_sha = _sha256_text(
        result["prototype_sha256"], "RESULT_SHA_INVALID"
    )
    core = copy.deepcopy(result)
    core.pop("prototype_sha256")
    if _sha256(core) != prototype_sha:
        _fail("PROTOTYPE_SHA_MISMATCH")
    validated = copy.deepcopy(result)
    validated["entries"] = entries
    return validated


def _indented_block(value: str) -> str:
    return "\n".join(f"    {line}" for line in value.split("\n"))


def render_result(result: object) -> str:
    """把已验证 prototype 排成作者可读文本，不增加任何交棒或真值结论。"""
    validated = validate_result(result)
    slot = validated["slot"]
    planning = validated["planning_source"]
    lines = [
        "# 章事实稿原型｜尚未交棒｜尚未进入事实账",
        "",
        f"- 章槽：`{slot['slot_ref']}`",
        f"- 章槽修订：`r{slot['slot_rev']}`",
        f"- 章纲来源：`{slot['source_outline_ref']}`",
        f"- 规划版本：`{planning['source_plan_version']}`",
        f"- 规划 SHA256：`{planning['source_plan_sha256']}`",
        f"- 规划提交水位：`{planning['source_commit_seq']}`",
        f"- 操作号：`{validated['operation_id']}`",
        f"- 原型 SHA256：`{validated['prototype_sha256']}`",
        "",
        "## 有序事实句",
    ]
    for index, entry in enumerate(validated["entries"], start=1):
        lines.extend(
            [
                "",
                f"### {index}. 事实句",
                "",
                _indented_block(entry["fact_text"]),
            ]
        )
        if entry["writing_note"]:
            lines.extend(
                [
                    "",
                    "**写法批注**",
                    "",
                    _indented_block(entry["writing_note"]),
                ]
            )
    lines.extend(
        [
            "",
            "## 写入结果",
            "",
            "- C11 写入：0",
            "- 事实账写入：0",
            "- 规划账写入：0",
            "",
        ]
    )
    return "\n".join(lines)


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
        raise ChapterFactDraftToolError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        _fail("INPUT_OBJECT_REQUIRED")
    return value


def _same_file_identity(input_path: str | None, output_path: str | None) -> bool:
    if input_path in {None, "-"} or output_path in {None, "-"}:
        return False
    source = Path(input_path)
    target = Path(output_path)
    try:
        if source.resolve() == target.resolve():
            return True
        if source.exists() and target.exists() and os.path.samefile(source, target):
            return True
    except OSError as exc:
        raise ChapterFactDraftToolError("FILE_IDENTITY_UNAVAILABLE") from exc
    return False


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_atomic(output_path: str | None, value: dict[str, Any]) -> None:
    _write_bytes_atomic(output_path, _canonical_bytes(value))


def _write_bytes_atomic(output_path: str | None, payload: bytes) -> None:
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
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="冻结作者章事实稿 prototype")
    parser.add_argument("--input", default="-")
    parser.add_argument("--output", default="-")
    parser.add_argument(
        "--render",
        action="store_true",
        help="把已经生成的 prototype JSON 渲染成作者可读 Markdown",
    )
    args = parser.parse_args(argv)
    try:
        if _same_file_identity(args.input, args.output):
            _fail("INPUT_OUTPUT_PATH_MUST_DIFFER")
        value = _load_request(args.input)
        if args.render:
            _write_bytes_atomic(args.output, render_result(value).encode("utf-8"))
        else:
            _write_atomic(args.output, execute(value))
    except (OSError, ChapterFactDraftToolError) as exc:
        print(f"CHAPTER_FACT_DRAFT_TOOL_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


__all__ = [
    "ChapterFactDraftToolError",
    "execute",
    "render_result",
    "validate_result",
]


if __name__ == "__main__":
    raise SystemExit(main())
