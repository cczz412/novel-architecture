"""M4 独立文件工具：C1/C2/C3 v1 对象 → C4 v1 extracted 快照。

只做本地对象和本地文件转换；不接收 project_dir，不写 facts.json，不做作者确认。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

try:
    from . import factstore
except ImportError:  # pragma: no cover - 直接运行脚本时使用
    import factstore  # type: ignore[no-redef]


REQUIRED_REQUEST_KEYS = {
    "chapter",
    "segments",
    "candidates",
    "source",
    "added_at",
}
OPTIONAL_REQUEST_KEYS = {"existing_c4"}
BATCH_REQUIRED_REQUEST_KEYS = {"items", "source", "added_at"}
BATCH_OPTIONAL_REQUEST_KEYS = {"existing_c4"}
BATCH_ITEM_KEYS = {"chapter", "segments", "candidates"}


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """纯对象入口；任一输入坏掉就抛错，不返回半批 C4。"""
    if not isinstance(request, dict):
        raise factstore.FactstoreError("FACT_TOOL_REQUEST_NOT_OBJECT")
    missing = REQUIRED_REQUEST_KEYS - set(request)
    extra = set(request) - REQUIRED_REQUEST_KEYS - OPTIONAL_REQUEST_KEYS
    if missing:
        raise factstore.FactstoreError(
            f"FACT_TOOL_REQUEST_MISSING:{','.join(sorted(missing))}"
        )
    if extra:
        raise factstore.FactstoreError(
            f"FACT_TOOL_REQUEST_EXTRA:{','.join(sorted(extra))}"
        )
    facts, new_ids = factstore.build_extracted_c4_snapshot(
        chapter=request["chapter"],
        segments=request["segments"],
        candidates=request["candidates"],
        existing_facts=request.get("existing_c4", []),
        source=request["source"],
        added_at=request["added_at"],
    )
    return {
        "facts": facts,
        "added_fact_refs": new_ids,
        "added_count": len(new_ids),
    }


def execute_batch(request: dict[str, Any]) -> dict[str, Any]:
    """按显式 items 顺序复用单章入口，累积一个完整 C4 快照。"""
    if not isinstance(request, dict):
        raise factstore.FactstoreError("FACT_TOOL_BATCH_REQUEST_NOT_OBJECT")
    missing = BATCH_REQUIRED_REQUEST_KEYS - set(request)
    extra = (
        set(request)
        - BATCH_REQUIRED_REQUEST_KEYS
        - BATCH_OPTIONAL_REQUEST_KEYS
    )
    if missing:
        raise factstore.FactstoreError(
            f"FACT_TOOL_BATCH_REQUEST_MISSING:{','.join(sorted(missing))}"
        )
    if extra:
        raise factstore.FactstoreError(
            f"FACT_TOOL_BATCH_REQUEST_EXTRA:{','.join(sorted(extra))}"
        )
    items = request["items"]
    if not isinstance(items, list) or not items:
        raise factstore.FactstoreError("FACT_TOOL_BATCH_ITEMS_REQUIRED")

    facts = request.get("existing_c4", [])
    added_fact_refs: list[str] = []
    seen_chapters: set[str] = set()
    seen_revision_refs: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != BATCH_ITEM_KEYS:
            raise factstore.FactstoreError(
                f"FACT_TOOL_BATCH_ITEM_SHAPE_INVALID:{index}"
            )
        result = execute(
            {
                **item,
                "source": request["source"],
                "added_at": request["added_at"],
                "existing_c4": facts,
            }
        )
        chapter = item["chapter"]
        chapter_id = chapter["id"]
        revision_key = json.dumps(
            chapter["chapter_revision_ref"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if revision_key in seen_revision_refs:
            raise factstore.FactstoreError(
                "FACT_TOOL_BATCH_REVISION_REF_DUPLICATE"
            )
        if chapter_id in seen_chapters:
            raise factstore.FactstoreError(
                "FACT_TOOL_BATCH_CHAPTER_ID_DUPLICATE"
            )
        seen_revision_refs.add(revision_key)
        seen_chapters.add(chapter_id)
        facts = result["facts"]
        added_fact_refs.extend(result["added_fact_refs"])
    return {
        "facts": facts,
        "added_fact_refs": added_fact_refs,
        "added_count": len(added_fact_refs),
    }


def execute_request(request: dict[str, Any]) -> dict[str, Any]:
    """CLI 运输分流：显式识别原单章形状或新增批次形状。"""
    has_single = "chapter" in request
    has_batch = "items" in request
    if has_single and has_batch:
        raise factstore.FactstoreError("FACT_TOOL_REQUEST_SHAPE_AMBIGUOUS")
    if has_batch:
        return execute_batch(request)
    return execute(request)


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _read_request(path: str | None) -> dict[str, Any]:
    if path is None or path == "-":
        value = json.load(sys.stdin)
    else:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise factstore.FactstoreError("FACT_TOOL_REQUEST_NOT_OBJECT")
    return value


def _reject_input_output_alias(
    input_path: str | None,
    output_path: str | None,
) -> None:
    if input_path in {None, "-"} or output_path in {None, "-"}:
        return
    source = Path(input_path)
    destination = Path(output_path)
    if source.resolve(strict=False) == destination.resolve(strict=False):
        raise factstore.FactstoreError("FACT_TOOL_INPUT_OUTPUT_SAME_FILE")
    if source.exists() and destination.exists() and source.samefile(destination):
        raise factstore.FactstoreError("FACT_TOOL_INPUT_OUTPUT_SAME_FILE")


def _write_json_atomic(path: Path, value: Any) -> None:
    if not path.parent.is_dir():
        raise factstore.FactstoreError("FACT_TOOL_OUTPUT_PARENT_NOT_FOUND")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LOCAL_FILESYSTEM_ONLY：把 C3 v1 批次转换为 C4 v1 extracted 快照"
    )
    parser.add_argument("--input", help="本地 JSON 文件；省略或 - 表示 stdin")
    parser.add_argument("--output", help="本地 JSON 文件；省略或 - 表示 stdout")
    args = parser.parse_args()
    try:
        _reject_input_output_alias(args.input, args.output)
        result = execute_request(_read_request(args.input))
        if args.output is None or args.output == "-":
            sys.stdout.buffer.write(_json_bytes(result))
        else:
            _write_json_atomic(Path(args.output), result)
    except (factstore.FactstoreError, json.JSONDecodeError, OSError) as exc:
        sys.stderr.write(
            json.dumps(
                {"status": "REJECTED", "reason": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
