"""M6 读者“截至某章”的零模型机械查询工具。

核心 ``execute(request)`` 只处理内存对象：它按调用方给定的当前章节
顺序截取可见前缀，再原样调用现役 ``ask_tool``。文件和
stdin/stdout 只是 LOCAL_FILESYSTEM_ONLY 运输适配层。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

try:
    from . import ask_tool, factstore
except ImportError:  # pragma: no cover - 直接运行脚本时使用
    import ask_tool  # type: ignore[no-redef]
    import factstore  # type: ignore[no-redef]


TRANSPORT_SCOPE = "LOCAL_FILESYSTEM_ONLY"
REQUEST_KEYS = {
    "query",
    "facts",
    "current_revision_refs",
    "as_of_chapter_id",
}


class ReaderScopeError(ValueError):
    """读者截点请求或本地运输不满足失败关闭条件。"""


def _ordered_current_refs(raw_refs: object) -> list[dict[str, Any]]:
    if not isinstance(raw_refs, list) or not raw_refs:
        raise ReaderScopeError("current_revision_refs 必须是非空列表")

    result: list[dict[str, Any]] = []
    seen_chapter_ids: set[str] = set()
    for index, ref in enumerate(raw_refs):
        if not ask_tool._valid_revision_ref(ref):
            raise ReaderScopeError(
                f"current_revision_refs[{index}] 不是合法 revision ref"
            )
        chapter_id = ref["chapter_id"]
        if chapter_id in seen_chapter_ids:
            raise ReaderScopeError("current_revision_refs 存在重复章节")
        seen_chapter_ids.add(chapter_id)
        result.append(copy.deepcopy(ref))
    return result


def _validated_facts(raw_facts: object) -> list[dict[str, Any]]:
    try:
        return factstore.validate_c4_v1_snapshot(raw_facts)
    except factstore.FactstoreError as exc:
        raise ReaderScopeError(f"facts 不是合法 C4 v1 快照：{exc}") from exc


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """按调用方明确给定的章节顺序，只查询截点以前的事实。"""

    if not isinstance(request, dict):
        raise ReaderScopeError("request 必须是对象")
    if set(request) != REQUEST_KEYS:
        raise ReaderScopeError(
            "request 只允许 query、facts、current_revision_refs、"
            "as_of_chapter_id"
        )

    query = request["query"]
    if not isinstance(query, str) or not query.strip():
        raise ReaderScopeError("query 必须是非空字符串")
    as_of_chapter_id = request["as_of_chapter_id"]
    if not isinstance(as_of_chapter_id, str) or not as_of_chapter_id:
        raise ReaderScopeError("as_of_chapter_id 必须是非空字符串")

    current_refs = _ordered_current_refs(request["current_revision_refs"])
    facts = _validated_facts(request["facts"])
    positions = {
        ref["chapter_id"]: position
        for position, ref in enumerate(current_refs)
    }
    if as_of_chapter_id not in positions:
        raise ReaderScopeError("as_of_chapter_id 不在当前章节索引中")
    if any(fact["chapter_id"] not in positions for fact in facts):
        raise ReaderScopeError("facts 存在不属于当前章节索引的记录")

    cutoff = positions[as_of_chapter_id]
    visible_refs = current_refs[: cutoff + 1]
    visible_facts = [
        fact for fact in facts if positions[fact["chapter_id"]] <= cutoff
    ]
    blocked_fact_count = len(facts) - len(visible_facts)

    try:
        query_result = ask_tool.execute(
            {
                "query": query,
                "facts": visible_facts,
                "current_revision_refs": visible_refs,
            }
        )
    except ask_tool.AskToolError as exc:
        raise ReaderScopeError(f"M6 查询拒绝：{exc}") from exc

    return {
        "reader_scope": {
            "mode": "AS_OF_CHAPTER",
            "as_of_chapter_id": as_of_chapter_id,
            "visible_chapter_count": cutoff + 1,
            "future_chapter_count": len(current_refs) - cutoff - 1,
            "blocked_fact_count": blocked_fact_count,
        },
        **query_result,
    }


def _read_request(path_text: str | None) -> dict[str, Any]:
    if path_text in {None, "-"}:
        raw = sys.stdin.read()
    else:
        raw = Path(path_text).read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReaderScopeError(f"输入不是合法 JSON：{exc.msg}") from exc
    if not isinstance(value, dict):
        raise ReaderScopeError("输入 JSON 顶层必须是对象")
    return value


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    payload = _json_bytes(value)
    parent = path.parent
    if not parent.is_dir():
        raise ReaderScopeError(f"输出目录不存在：{parent}")
    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        directory_descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _write_result(path_text: str | None, result: dict[str, Any]) -> None:
    if path_text in {None, "-"}:
        sys.stdout.buffer.write(_json_bytes(result))
        sys.stdout.buffer.flush()
        return
    _atomic_write_json(Path(path_text), result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="M6 LOCAL_FILESYSTEM_ONLY reader as-of chapter query tool"
    )
    parser.add_argument("--input", help="本地 JSON；省略或 - 时读 stdin")
    parser.add_argument("--output", help="本地 JSON；省略或 - 时写 stdout")
    args = parser.parse_args(argv)
    try:
        request = _read_request(args.input)
        result = execute(request)
        _write_result(args.output, result)
    except (ReaderScopeError, OSError) as exc:
        print(f"ask_reader_scope_tool error: {exc}", file=sys.stderr)
        return 2
    return 0


__all__ = ["ReaderScopeError", "execute"]


if __name__ == "__main__":
    raise SystemExit(main())
