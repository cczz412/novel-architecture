"""M5 当前章分页结果的只读 Markdown 文件工具。"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn


if __package__:
    from . import factstore
else:  # 允许直接运行 python novel-mvp/mvp/review_page_tool.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import factstore


PAGE_KEYS = {
    "chapter_id",
    "chapter_revision_ref",
    "facts_snapshot",
    "items",
    "has_more",
    "next_after_fact_ref",
}
REVISION_REF_KEYS = {
    "chapter_id",
    "revision_no",
    "revision_text_sha256",
}
FACTS_SNAPSHOT_KEYS = {"version", "sha256"}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class ReviewPageToolError(ValueError):
    """分页审查单输入或本地文件适配不合法。"""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _fail(code: str, detail: str = "") -> NoReturn:
    raise ReviewPageToolError(code, detail)


def _clean_chapter_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "/" in value
        or "\\" in value
        or value in {".", ".."}
    ):
        _fail("PAGE_CHAPTER_ID_INVALID")
    return value


def _revision_ref(value: object, chapter_id: str) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != REVISION_REF_KEYS
        or value.get("chapter_id") != chapter_id
        or not isinstance(value.get("revision_no"), int)
        or isinstance(value.get("revision_no"), bool)
        or value["revision_no"] < 1
        or not isinstance(value.get("revision_text_sha256"), str)
        or SHA256_RE.fullmatch(value["revision_text_sha256"]) is None
    ):
        _fail("PAGE_CHAPTER_REVISION_INVALID")
    return copy.deepcopy(value)


def _facts_snapshot(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FACTS_SNAPSHOT_KEYS:
        _fail("PAGE_FACTS_SNAPSHOT_INVALID")
    version = value.get("version")
    sha256 = value.get("sha256")
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        _fail("PAGE_FACTS_SNAPSHOT_INVALID")
    if version == 0:
        if sha256 is not None:
            _fail("PAGE_FACTS_SNAPSHOT_INVALID")
    elif (
        not isinstance(sha256, str)
        or SHA256_RE.fullmatch(sha256) is None
    ):
        _fail("PAGE_FACTS_SNAPSHOT_INVALID")
    return {"version": version, "sha256": sha256}


def _fact_ref_or_none(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or factstore.FACT_ID_RE.fullmatch(value) is None:
        _fail("PAGE_NEXT_CURSOR_INVALID")
    return value


def validate_page(value: object) -> dict[str, Any]:
    """严格校验并复制现役 read_chapter_review_page 输出。"""
    if not isinstance(value, dict) or set(value) != PAGE_KEYS:
        _fail("PAGE_FIELDS_INVALID")
    chapter_id = _clean_chapter_id(value.get("chapter_id"))
    revision_ref = _revision_ref(value.get("chapter_revision_ref"), chapter_id)
    facts_snapshot = _facts_snapshot(value.get("facts_snapshot"))
    if not isinstance(value.get("items"), list):
        _fail("PAGE_ITEMS_INVALID")
    try:
        items = factstore.validate_c4_v1_snapshot(value["items"])
    except factstore.FactstoreError as exc:
        raise ReviewPageToolError("PAGE_ITEMS_INVALID", str(exc)) from exc
    if facts_snapshot["version"] == 0 and items:
        _fail("PAGE_ITEMS_WITHOUT_FACTS_SNAPSHOT")
    for fact in items:
        if fact["chapter_id"] != chapter_id:
            _fail("PAGE_ITEM_CHAPTER_MISMATCH", fact["id"])
        if fact["chapter_revision_ref"] != revision_ref:
            _fail("PAGE_ITEM_REVISION_MISMATCH", fact["id"])
        if (
            fact["status"] != "extracted"
            or fact["anchor_state"] != "VERIFIED"
            or fact["recheck"] is not None
        ):
            _fail("PAGE_ITEM_NOT_PENDING_REVIEW", fact["id"])

    has_more = value.get("has_more")
    if not isinstance(has_more, bool):
        _fail("PAGE_HAS_MORE_INVALID")
    next_cursor = _fact_ref_or_none(value.get("next_after_fact_ref"))
    if has_more and not items:
        _fail("PAGE_HAS_MORE_WITHOUT_ITEMS")
    if items and next_cursor != items[-1]["id"]:
        _fail("PAGE_NEXT_CURSOR_MISMATCH")

    return {
        "chapter_id": chapter_id,
        "chapter_revision_ref": revision_ref,
        "facts_snapshot": facts_snapshot,
        "items": items,
        "has_more": has_more,
        "next_after_fact_ref": next_cursor,
    }


def _blockquote(value: str) -> str:
    lines = value.splitlines() or [""]
    return "\n".join(f"> {line}" if line else ">" for line in lines)


def render_page(value: object) -> str:
    """把一页 M5 待审候选渲染成稳定、证据完整的 Markdown。"""
    page = validate_page(value)
    revision = page["chapter_revision_ref"]
    snapshot = page["facts_snapshot"]
    cursor = page["next_after_fact_ref"]
    lines = [
        f"# 章节 {page['chapter_id']}｜事实审查单",
        "",
        f"- 当前 revision：r{revision['revision_no']}",
        f"- revision 正文 SHA256：`{revision['revision_text_sha256']}`",
        f"- facts 版本：{snapshot['version']}",
        f"- facts SHA256：`{snapshot['sha256'] or 'NONE'}`",
        f"- 本页数量：{len(page['items'])}",
        f"- 是否还有下一页：{'是' if page['has_more'] else '否'}",
        f"- 下一续看锚：`{cursor or 'NONE'}`",
        "",
        "> 本页只供作者审查，尚未确认/驳回。",
    ]
    if not page["items"]:
        lines.extend(["", "本页没有待审条目。"])
        return "\n".join(lines) + "\n"

    for index, fact in enumerate(page["items"], 1):
        anchor = fact["anchor_ref"]
        lines.extend(
            [
                "",
                "---",
                "",
                f"## {index}. `{fact['id']}`",
                "",
                f"- 当前状态：`{fact['status']}`",
                f"- 来源：{fact['source']}",
                (
                    "- 章节 revision："
                    f"`{revision['chapter_id']}@r{revision['revision_no']}`"
                ),
                (
                    "- anchor span："
                    f"`[{anchor['start']}, {anchor['end']})` "
                    f"（{anchor['coordinate_basis']}）"
                ),
                f"- anchor slice SHA256：`{anchor['slice_sha256']}`",
                "",
                "### 事实句",
                "",
                _blockquote(fact["text"]),
                "",
                "### 原文 quote",
                "",
                _blockquote(fact["quote"]),
            ]
        )
    return "\n".join(lines) + "\n"


# LOCAL_FILESYSTEM_ONLY: 仅把本地 JSON 页对象适配到纯对象 render_page。
def _load_page(input_path: str | None) -> dict[str, Any]:
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
        raise ReviewPageToolError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        _fail("PAGE_OBJECT_REQUIRED")
    return value


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_markdown_atomic(path: Path, markdown: str) -> None:
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
            handle.write(markdown.encode("utf-8"))
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
    parser = argparse.ArgumentParser(description="把 M5 分页结果渲染成事实审查单")
    parser.add_argument("--input", help="输入分页 JSON；省略或 - 表示 stdin")
    parser.add_argument("--output", help="输出 Markdown；省略或 - 表示 stdout")
    args = parser.parse_args(argv)
    try:
        _validate_paths(args.input, args.output)
        markdown = render_page(_load_page(args.input))
        if args.output in {None, "-"}:
            sys.stdout.buffer.write(markdown.encode("utf-8"))
            sys.stdout.buffer.flush()
        else:
            _write_markdown_atomic(Path(args.output), markdown)
    except (OSError, ReviewPageToolError) as exc:
        print(f"REVIEW_PAGE_TOOL_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


__all__ = ["ReviewPageToolError", "render_page", "validate_page"]


if __name__ == "__main__":
    raise SystemExit(main())
