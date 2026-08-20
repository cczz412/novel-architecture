"""M2 独立文件工具：C1 v1 运输外壳 → C2 v1 运输外壳。

``execute`` 只处理内存对象。命令行的本地文件读写集中在本文件末尾的
``LOCAL_FILESYSTEM_ONLY`` 适配层，未来可由 AuthorWorkspace 直接传入 JSON 字节。
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
from typing import Any


if __package__:
    from . import segment
else:  # 允许直接运行 python novel-mvp/mvp/segment_tool.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import segment


OPTION_KEYS = frozenset({"seg_min_chars", "seg_max_chars", "halo_chars"})
REQUEST_KEYS = frozenset({"items", "options"})
RENDER_REQUEST_KEYS = frozenset({"source_request", "c2_result"})
C2_RESULT_KEYS = frozenset({"items", "receipt"})
C2_ITEM_KEYS = frozenset(
    {
        "contract",
        "version",
        "chapter_revision_ref",
        "seg",
        "text",
        "start",
        "end",
        "halo_before",
        "halo_after",
    }
)


class SegmentToolError(ValueError):
    """运输外壳、C1 输入或本地文件适配不合法。"""


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SegmentToolError("VALUE_NOT_JSON_SERIALIZABLE") from exc


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _validate_request(request: object) -> tuple[list[dict], dict[str, int]]:
    if not isinstance(request, dict):
        raise SegmentToolError("REQUEST_MUST_BE_OBJECT")
    keys = set(request)
    if keys != REQUEST_KEYS:
        missing = sorted(REQUEST_KEYS - keys)
        extra = sorted(keys - REQUEST_KEYS)
        raise SegmentToolError(f"REQUEST_FIELDS_INVALID:missing={missing}:extra={extra}")

    items = request["items"]
    if not isinstance(items, list):
        raise SegmentToolError("ITEMS_MUST_BE_ARRAY")
    if not items:
        raise SegmentToolError("ITEMS_MUST_BE_NONEMPTY_ARRAY")
    if any(not isinstance(item, dict) for item in items):
        raise SegmentToolError("ITEMS_MUST_CONTAIN_OBJECTS")

    options = request["options"]
    if not isinstance(options, dict):
        raise SegmentToolError("OPTIONS_MUST_BE_OBJECT")
    option_keys = set(options)
    if option_keys != OPTION_KEYS:
        missing = sorted(OPTION_KEYS - option_keys)
        extra = sorted(option_keys - OPTION_KEYS)
        raise SegmentToolError(f"OPTIONS_FIELDS_INVALID:missing={missing}:extra={extra}")

    normalized: dict[str, int] = {}
    for key in OPTION_KEYS:
        value = options[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise SegmentToolError(f"OPTION_MUST_BE_INTEGER:{key}")
        normalized[key] = value
    if normalized["seg_min_chars"] <= 0:
        raise SegmentToolError("SEG_MIN_CHARS_MUST_BE_POSITIVE")
    if normalized["seg_max_chars"] < normalized["seg_min_chars"]:
        raise SegmentToolError("SEG_MAX_CHARS_BELOW_MIN")
    if normalized["halo_chars"] < 0:
        raise SegmentToolError("HALO_CHARS_MUST_BE_NON_NEGATIVE")

    _canonical_json_bytes(request)
    return items, normalized


def _validate_batch_identity(items: list[dict]) -> None:
    seen_chapter_ids: set[str] = set()
    seen_revision_refs: set[tuple[str, int, str]] = set()
    for item in items:
        chapter_id = item["id"]
        revision_ref = item["chapter_revision_ref"]
        revision_identity = (
            revision_ref["chapter_id"],
            revision_ref["revision_no"],
            revision_ref["revision_text_sha256"],
        )
        if revision_identity in seen_revision_refs:
            raise SegmentToolError("DUPLICATE_CHAPTER_REVISION_REF")
        if chapter_id in seen_chapter_ids:
            raise SegmentToolError(f"DUPLICATE_CHAPTER_ID:{chapter_id}")
        seen_revision_refs.add(revision_identity)
        seen_chapter_ids.add(chapter_id)


def _coverage_error(chapter_id: str, code: str) -> None:
    raise SegmentToolError(f"CHAPTER_COVERAGE_INVALID:{chapter_id}:{code}")


def _chapter_coverage_receipt(
    chapter: dict,
    segments: list[dict],
    *,
    seg_max_chars: int,
    halo_chars: int,
) -> dict[str, Any]:
    chapter_id = chapter["id"]
    revision_ref = chapter["chapter_revision_ref"]
    normalized_text = "\n".join(segment.split_paragraphs(chapter["text"]))
    if not normalized_text:
        raise SegmentToolError(f"CHAPTER_TEXT_EMPTY_AFTER_NORMALIZATION:{chapter_id}")
    if not segments:
        _coverage_error(chapter_id, "NO_SEGMENTS")

    previous_end = 0
    responsibility_texts: list[str] = []
    segment_lengths: list[int] = []
    for expected_number, item in enumerate(segments, 1):
        if not isinstance(item, dict):
            _coverage_error(chapter_id, "SEGMENT_NOT_OBJECT")
        if item.get("contract") != "C2_SEGMENT" or item.get("version") != "v1":
            _coverage_error(chapter_id, "C2_IDENTITY_MISMATCH")
        if item.get("chapter_revision_ref") != revision_ref:
            _coverage_error(chapter_id, "REVISION_REF_MISMATCH")
        if item.get("seg") != expected_number:
            _coverage_error(chapter_id, "SEGMENT_SEQUENCE_MISMATCH")

        text = item.get("text")
        start = item.get("start")
        end = item.get("end")
        if not isinstance(text, str) or not text:
            _coverage_error(chapter_id, "RESPONSIBILITY_TEXT_INVALID")
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or start < 0
            or end != start + len(text)
            or end > len(normalized_text)
        ):
            _coverage_error(chapter_id, "COORDINATES_INVALID")
        if normalized_text[start:end] != text:
            _coverage_error(chapter_id, "COORDINATE_TEXT_MISMATCH")
        if expected_number == 1:
            if start != 0:
                _coverage_error(chapter_id, "LEADING_GAP")
        elif normalized_text[previous_end:start] != "\n":
            _coverage_error(chapter_id, "GAP_OVERLAP_OR_ORDER_MISMATCH")

        expected_halo_before = normalized_text[max(0, start - halo_chars):start]
        expected_halo_after = normalized_text[end:end + halo_chars]
        if item.get("halo_before") != expected_halo_before:
            _coverage_error(chapter_id, "HALO_BEFORE_MISMATCH")
        if item.get("halo_after") != expected_halo_after:
            _coverage_error(chapter_id, "HALO_AFTER_MISMATCH")

        responsibility_texts.append(text)
        segment_lengths.append(len(text))
        previous_end = end

    if previous_end != len(normalized_text):
        _coverage_error(chapter_id, "TRAILING_GAP")
    if "\n".join(responsibility_texts) != normalized_text:
        _coverage_error(chapter_id, "RESPONSIBILITY_REASSEMBLY_MISMATCH")

    return {
        "chapter_revision_ref": json.loads(
            _canonical_json_bytes(revision_ref)
        ),
        "segment_count": len(segments),
        "normalized_char_count": len(normalized_text),
        "max_segment_chars": max(segment_lengths),
        "oversize_segment_count": sum(
            length > seg_max_chars for length in segment_lengths
        ),
        "coverage_sha256": hashlib.sha256(
            normalized_text.encode("utf-8")
        ).hexdigest(),
    }


def execute(request: dict) -> dict:
    """校验整批 C1 v1 后切窗；不读写路径，也不改变 C1/C2 对象字段。"""
    items, options = _validate_request(request)

    # 先让现役 M2 校验器检查完整批次，再开始生成任何 C2。
    for index, item in enumerate(items):
        try:
            segment._validated_c1_v1_text(item)
        except (KeyError, TypeError, ValueError) as exc:
            raise SegmentToolError(f"C1_ITEM_INVALID:{index}:{exc}") from exc
    _validate_batch_identity(items)

    output_items: list[dict] = []
    chapter_receipts: list[dict] = []
    for item in items:
        chapter_segments = segment.segment_chapter(
            item,
            options["seg_min_chars"],
            options["seg_max_chars"],
            options["halo_chars"],
        )
        chapter_receipts.append(
            _chapter_coverage_receipt(
                item,
                chapter_segments,
                seg_max_chars=options["seg_max_chars"],
                halo_chars=options["halo_chars"],
            )
        )
        output_items.extend(chapter_segments)

    return {
        "items": output_items,
        "receipt": {
            "input_count": len(items),
            "output_count": len(output_items),
            "input_sha256": _sha256(request),
            "output_sha256": _sha256(output_items),
            "chapter_receipts": chapter_receipts,
        },
    }


def _validated_render_payload(
    value: object,
) -> tuple[dict[str, Any], dict[str, Any], list[list[dict[str, Any]]]]:
    if not isinstance(value, dict) or set(value) != RENDER_REQUEST_KEYS:
        raise SegmentToolError("RENDER_REQUEST_FIELDS_INVALID")
    source_request = value["source_request"]
    c2_result = value["c2_result"]
    items, options = _validate_request(source_request)
    for index, item in enumerate(items):
        try:
            segment._validated_c1_v1_text(item)
        except (KeyError, TypeError, ValueError) as exc:
            raise SegmentToolError(f"RENDER_C1_ITEM_INVALID:{index}:{exc}") from exc
    _validate_batch_identity(items)

    if not isinstance(c2_result, dict) or set(c2_result) != C2_RESULT_KEYS:
        raise SegmentToolError("RENDER_C2_RESULT_FIELDS_INVALID")
    c2_items = c2_result["items"]
    if not isinstance(c2_items, list):
        raise SegmentToolError("RENDER_C2_ITEMS_MUST_BE_ARRAY")

    chapters_by_revision: dict[bytes, int] = {}
    for index, chapter in enumerate(items):
        ref = chapter["chapter_revision_ref"]
        chapters_by_revision[_canonical_json_bytes(ref)] = index
    grouped: list[list[dict[str, Any]]] = [[] for _ in items]
    observed_chapter_order: list[str] = []
    for index, c2_item in enumerate(c2_items):
        if not isinstance(c2_item, dict) or set(c2_item) != C2_ITEM_KEYS:
            raise SegmentToolError(f"RENDER_C2_ITEM_SHAPE_INVALID:{index}")
        ref = c2_item.get("chapter_revision_ref")
        if not isinstance(ref, dict):
            raise SegmentToolError(f"RENDER_C2_REVISION_REF_INVALID:{index}")
        revision_identity = _canonical_json_bytes(ref)
        chapter_index = chapters_by_revision.get(revision_identity)
        if chapter_index is None:
            raise SegmentToolError(f"RENDER_C2_SOURCE_REF_NOT_FOUND:{index}")
        grouped[chapter_index].append(copy.deepcopy(c2_item))
        chapter_id = ref["chapter_id"]
        if not observed_chapter_order or observed_chapter_order[-1] != chapter_id:
            observed_chapter_order.append(chapter_id)

    expected_chapter_order = [chapter["id"] for chapter in items]
    if observed_chapter_order != expected_chapter_order:
        raise SegmentToolError("RENDER_C2_CHAPTER_ORDER_INVALID")

    expected_chapter_receipts = [
        _chapter_coverage_receipt(
            chapter,
            chapter_segments,
            seg_max_chars=options["seg_max_chars"],
            halo_chars=options["halo_chars"],
        )
        for chapter, chapter_segments in zip(items, grouped, strict=True)
    ]
    expected_receipt = {
        "input_count": len(items),
        "output_count": len(c2_items),
        "input_sha256": _sha256(source_request),
        "output_sha256": _sha256(c2_items),
        "chapter_receipts": expected_chapter_receipts,
    }
    if c2_result["receipt"] != expected_receipt:
        raise SegmentToolError("RENDER_C2_RECEIPT_MISMATCH")
    return (
        copy.deepcopy(source_request),
        copy.deepcopy(c2_result),
        grouped,
    )


def validate_render_request(value: object) -> dict[str, Any]:
    """校验 C1 来源与已有 C2 结果闭合，不再执行切段。"""
    source_request, c2_result, _ = _validated_render_payload(value)
    return {"source_request": source_request, "c2_result": c2_result}


def _append_text_block(lines: list[str], label: str, value: str) -> None:
    lines.extend(
        [
            f"{label}（{len(value)} 字）：",
            "````text",
            value if value else "（无）",
            "````",
            "",
        ]
    )


def render_segment_map(value: object) -> str:
    """把已校验的 C2 结果排成人读责任段地图，不改写正文。"""
    source_request, c2_result, grouped = _validated_render_payload(value)
    chapters = source_request["items"]
    receipts = c2_result["receipt"]["chapter_receipts"]
    lines = [
        "# M2 责任段地图",
        "",
        "> 责任文本是本段唯一可产生事实的范围；前后上下文只读，不属于责任文本。",
        "",
    ]
    for chapter, chapter_segments, receipt in zip(
        chapters,
        grouped,
        receipts,
        strict=True,
    ):
        ref = chapter["chapter_revision_ref"]
        lines.extend(
            [
                f"## 章节 {chapter['id']}",
                "",
                f"- 修订号：{ref['revision_no']}",
                f"- 修订门牌：`{_canonical_json_bytes(ref).decode('utf-8')}`",
                f"- 正文 SHA-256：`{ref['revision_text_sha256']}`",
                f"- 责任段数：{len(chapter_segments)}",
                f"- 规范化正文字数：{receipt['normalized_char_count']}",
                f"- 覆盖 SHA-256：`{receipt['coverage_sha256']}`",
                "- 可回拼提示：按段号顺序，用一个换行连接所有责任文本，即得到上述规范化正文。",
                "",
            ]
        )
        for c2_item in chapter_segments:
            lines.extend(
                [
                    f"### 段号 {c2_item['seg']}",
                    "",
                    f"- 责任范围：`[{c2_item['start']}, {c2_item['end']})`",
                    f"- 来源正文 SHA-256：`{ref['revision_text_sha256']}`",
                    "",
                ]
            )
            _append_text_block(lines, "责任文本", c2_item["text"])
            _append_text_block(
                lines,
                "前置上下文（只读，不属于责任文本）",
                c2_item["halo_before"],
            )
            _append_text_block(
                lines,
                "后置上下文（只读，不属于责任文本）",
                c2_item["halo_after"],
            )
    return "\n".join(lines).rstrip() + "\n"


# LOCAL_FILESYSTEM_ONLY: 仅供当前本机 CLI；未来由 AuthorWorkspace 传 JSON 字节。
def _load_request(input_path: str | None) -> dict:
    if input_path in {None, "-"}:
        raw = sys.stdin.buffer.read()
    else:
        path = Path(input_path)
        if not path.is_file():
            raise SegmentToolError(f"INPUT_PATH_NOT_FILE:{path}")
        raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SegmentToolError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise SegmentToolError("REQUEST_MUST_BE_OBJECT")
    return value


def _json_output_bytes(value: dict) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic(path: Path, value: dict) -> None:
    parent = path.parent
    if not parent.is_dir():
        raise SegmentToolError(f"OUTPUT_PARENT_NOT_DIRECTORY:{parent}")
    if path.exists() and not path.is_file():
        raise SegmentToolError(f"OUTPUT_PATH_NOT_FILE:{path}")

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(_json_output_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
        _fsync_directory(parent)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _write_text_atomic(path: Path, value: str) -> None:
    parent = path.parent
    if not parent.is_dir():
        raise SegmentToolError(f"OUTPUT_PARENT_NOT_DIRECTORY:{parent}")
    if path.exists() and not path.is_file():
        raise SegmentToolError(f"OUTPUT_PATH_NOT_FILE:{path}")

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(value.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
        _fsync_directory(parent)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _file_identity(
    path: Path,
    *,
    label: str,
) -> tuple[Path, os.stat_result | None]:
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise SegmentToolError(f"FILE_IDENTITY_UNAVAILABLE:{label}") from exc
    try:
        stat_result = path.stat()
    except FileNotFoundError:
        stat_result = None
    except OSError as exc:
        raise SegmentToolError(f"FILE_IDENTITY_UNAVAILABLE:{label}") from exc
    return resolved, stat_result


def _same_file_identity(left: Path, right: Path) -> bool:
    left_resolved, left_stat = _file_identity(left, label="INPUT")
    right_resolved, right_stat = _file_identity(right, label="OUTPUT")
    return left_resolved == right_resolved or (
        left_stat is not None
        and right_stat is not None
        and os.path.samestat(left_stat, right_stat)
    )


def _validate_adapter_paths(input_path: str | None, output_path: str | None) -> None:
    if input_path in {None, "-"} or output_path in {None, "-"}:
        return
    if _same_file_identity(Path(input_path), Path(output_path)):
        raise SegmentToolError("INPUT_OUTPUT_PATH_MUST_DIFFER")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 C1 v1 JSON 切成 C2 v1 JSON")
    parser.add_argument("--input", help="输入 JSON 文件；省略或 - 表示 stdin")
    parser.add_argument("--output", help="输出 JSON 文件；省略或 - 表示 stdout")
    parser.add_argument(
        "--render",
        action="store_true",
        help="把 source_request＋c2_result 运输对象排成人读责任段地图",
    )
    args = parser.parse_args(argv)

    try:
        _validate_adapter_paths(args.input, args.output)
        request = _load_request(args.input)
        if args.render:
            rendered = render_segment_map(request)
            if args.output in {None, "-"}:
                sys.stdout.buffer.write(rendered.encode("utf-8"))
                sys.stdout.buffer.flush()
            else:
                _write_text_atomic(Path(args.output), rendered)
        else:
            result = execute(request)
            if args.output in {None, "-"}:
                sys.stdout.buffer.write(_json_output_bytes(result))
                sys.stdout.buffer.flush()
            else:
                _write_json_atomic(Path(args.output), result)
    except (OSError, SegmentToolError) as exc:
        print(f"SEGMENT_TOOL_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
