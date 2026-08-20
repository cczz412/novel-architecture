"""M10 场景卡原型的独立文件工具外壳。"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn


if __package__:
    from . import scene_export
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import scene_export


REQUEST_KEYS = {"source"}


class SceneExportToolError(ValueError):
    """文件工具外壳或规范化批次不闭合。"""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _fail(code: str, detail: str = "") -> NoReturn:
    raise SceneExportToolError(code, detail)


def _mapping(value: Any, field: str) -> dict:
    if not isinstance(value, dict):
        _fail("INVALID_BATCH_SHAPE", field)
    return value


def _list(value: Any, field: str) -> list:
    if not isinstance(value, list):
        _fail("INVALID_BATCH_SHAPE", field)
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("INVALID_BATCH_SHAPE", field)
    return value


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail("INVALID_SCENE_POSITION", field)
    return value


def _validate_closed_batch(source: dict) -> None:
    if source.get("contract") != scene_export.SOURCE_CONTRACT:
        _fail("INVALID_SOURCE_CONTRACT")
    if source.get("scene_export_slice") != scene_export.SOURCE_SLICE:
        _fail("INVALID_SOURCE_SLICE")

    event_index: dict[str, dict] = {}
    for index, raw_event in enumerate(
        _list(source.get("planned_events"), "source.planned_events")
    ):
        event = _mapping(raw_event, f"planned_events[{index}]")
        event_id = _text(event.get("id"), f"planned_events[{index}].id")
        if event_id in event_index:
            _fail("DUPLICATE_PLANNED_EVENT", event_id)
        event_index[event_id] = event

    scene_ids: set[str] = set()
    positions: set[tuple[int, int]] = set()
    counts_by_chapter: dict[int, int] = {}
    referenced_events: set[str] = set()
    for index, raw_scene in enumerate(_list(source.get("scenes"), "source.scenes")):
        scene = _mapping(raw_scene, f"scenes[{index}]")
        scene_id = _text(scene.get("id"), f"scenes[{index}].id")
        if scene_id in scene_ids:
            _fail("DUPLICATE_SCENE_ID", scene_id)
        scene_ids.add(scene_id)

        chapter = _positive_int(
            scene.get("chapter_hint"), f"scenes[{scene_id}].chapter_hint"
        )
        order = _positive_int(
            scene.get("scene_order"), f"scenes[{scene_id}].scene_order"
        )
        count = _positive_int(
            scene.get("scene_count"), f"scenes[{scene_id}].scene_count"
        )
        if order > count:
            _fail("SCENE_POSITION_OUT_OF_RANGE", scene_id)
        if (chapter, order) in positions:
            _fail("DUPLICATE_SCENE_POSITION", f"chapter={chapter},order={order}")
        positions.add((chapter, order))
        prior_count = counts_by_chapter.setdefault(chapter, count)
        if prior_count != count:
            _fail("SCENE_COUNT_INCONSISTENT", f"chapter={chapter}")

        local_refs: set[str] = set()
        for raw_ref in _list(scene.get("pe_refs"), f"scenes[{scene_id}].pe_refs"):
            event_ref = _text(raw_ref, f"scenes[{scene_id}].pe_refs[]")
            if event_ref in local_refs or event_ref in referenced_events:
                _fail("DUPLICATE_EVENT_REFERENCE", event_ref)
            local_refs.add(event_ref)
            referenced_events.add(event_ref)
            event = event_index.get(event_ref)
            if event is None:
                _fail("EVENT_NOT_FOUND", event_ref)
            if event.get("scene_ref") != scene_id:
                _fail("EVENT_SCENE_MISMATCH", event_ref)

    unreferenced = sorted(set(event_index) - referenced_events)
    if unreferenced:
        _fail("UNREFERENCED_PLANNED_EVENT", ",".join(unreferenced))


def execute(request: dict) -> dict:
    """校验一个规范化 M10 场景切片，并原样调用现有导出核心。"""
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        _fail("REQUEST_FIELDS_INVALID")
    source = copy.deepcopy(request.get("source"))
    if not isinstance(source, dict):
        _fail("SOURCE_OBJECT_REQUIRED")
    _validate_closed_batch(source)
    return scene_export.export_scene_cards(source)


def _validated_prototype_card_ids(prototype: dict) -> list[str]:
    scene_export.validate_c8_prototype(prototype)
    card_ids: list[str] = []
    seen_card_ids: set[str] = set()
    for index, raw_card in enumerate(_list(prototype.get("cards"), "cards")):
        card = _mapping(raw_card, f"cards[{index}]")
        current_card_id = card.get("card_id")
        if not isinstance(current_card_id, str) or not current_card_id:
            _fail("C8_CARD_ID_INVALID", str(index))
        if current_card_id in seen_card_ids:
            _fail("CARD_ID_NOT_UNIQUE", current_card_id)
        seen_card_ids.add(current_card_id)
        card_ids.append(current_card_id)
    return card_ids


def _prototype_copy(c8_prototype: object) -> dict:
    prototype = copy.deepcopy(c8_prototype)
    if not isinstance(prototype, dict):
        _fail("C8_PROTOTYPE_OBJECT_REQUIRED")
    return prototype


def render_card(c8_prototype: dict, card_id: str) -> str:
    """按唯一 card_id 选择现有 C8 原型卡，并复用现役文本渲染器。"""
    if (
        not isinstance(card_id, str)
        or not card_id
        or card_id != card_id.strip()
    ):
        _fail("CARD_ID_INVALID")
    prototype = _prototype_copy(c8_prototype)
    card_ids = _validated_prototype_card_ids(prototype)
    if card_id not in card_ids:
        _fail("CARD_ID_NOT_FOUND", card_id)
    return scene_export.render_scene_card(prototype, card_ids.index(card_id))


def render_all(c8_prototype: dict) -> str:
    """按 C8 原顺序把全部场景卡渲染成一份稳定 Markdown。"""
    prototype = _prototype_copy(c8_prototype)
    card_ids = _validated_prototype_card_ids(prototype)
    book_title = _text(prototype.get("book_title"), "book_title")
    export_id = _text(prototype.get("export_id"), "export_id")
    source_sha256 = _text(prototype.get("source_sha256"), "source_sha256")
    range_value = _mapping(prototype.get("range"), "range")
    chapters = _list(range_value.get("chapters"), "range.chapters")
    if not chapters or any(
        isinstance(chapter, bool) or not isinstance(chapter, int) or chapter < 1
        for chapter in chapters
    ):
        _fail("C8_CHAPTER_RANGE_INVALID")

    header = "\n".join(
        [
            f"# {book_title}｜M10 场景卡",
            "",
            f"- 导出身份：`{export_id}`",
            f"- 来源 SHA256：`{source_sha256}`",
            f"- 章节：{', '.join(str(chapter) for chapter in chapters)}",
            f"- 卡片总数：{len(card_ids)}",
        ]
    )
    sections = [
        (
            f"## 场景卡 {index} · `{card_id}`\n\n"
            f"{scene_export.render_scene_card(prototype, index - 1).rstrip()}"
        )
        for index, card_id in enumerate(card_ids, 1)
    ]
    return f"{header}\n\n" + "\n\n---\n\n".join(sections) + "\n"


# LOCAL_FILESYSTEM_ONLY: 仅把本地 JSON 文件适配到纯对象 execute。
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
        raise SceneExportToolError("INPUT_JSON_INVALID") from exc
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
    _write_bytes_atomic(path, _output_bytes(value))


def _write_text_atomic(path: Path, value: str) -> None:
    _write_bytes_atomic(path, value.encode("utf-8"))


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
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
            handle.write(payload)
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


def _validate_mode(mode: str, card_id: str | None) -> None:
    if mode == "json":
        if card_id is not None:
            _fail("MODE_ARGUMENT_CONFLICT", "json-with-card-id")
        return
    if mode == "render-card":
        if card_id is None:
            _fail("CARD_ID_REQUIRED")
        return
    if card_id is not None:
        _fail("MODE_ARGUMENT_CONFLICT", "render-all-with-card-id")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导出 M10 场景卡原型 JSON")
    parser.add_argument("--input", help="输入 JSON；省略或 - 表示 stdin")
    parser.add_argument("--output", help="输出 JSON；省略或 - 表示 stdout")
    parser.add_argument(
        "--mode",
        choices=("json", "render-card", "render-all"),
        default="json",
        help=(
            "json 保持原导出；render-card 导出单卡文本；"
            "render-all 导出全部卡 Markdown"
        ),
    )
    parser.add_argument("--card-id", help="render-card 模式要导出的唯一 card_id")
    args = parser.parse_args(argv)
    try:
        _validate_mode(args.mode, args.card_id)
        _validate_paths(args.input, args.output)
        source = _load_request(args.input)
        if args.mode == "json":
            result = execute(source)
            if args.output in {None, "-"}:
                sys.stdout.buffer.write(_output_bytes(result))
                sys.stdout.buffer.flush()
            else:
                _write_atomic(Path(args.output), result)
        elif args.mode == "render-card":
            rendered = render_card(source, args.card_id)
            if args.output in {None, "-"}:
                sys.stdout.buffer.write(rendered.encode("utf-8"))
                sys.stdout.buffer.flush()
            else:
                _write_text_atomic(Path(args.output), rendered)
        else:
            rendered = render_all(source)
            if args.output in {None, "-"}:
                sys.stdout.buffer.write(rendered.encode("utf-8"))
                sys.stdout.buffer.flush()
            else:
                _write_text_atomic(Path(args.output), rendered)
    except (OSError, SceneExportToolError, scene_export.SceneExportError) as exc:
        print(f"SCENE_EXPORT_TOOL_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
