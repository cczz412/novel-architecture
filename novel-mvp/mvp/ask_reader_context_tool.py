"""M6 防剧透查询＋证据上下文结果的严格人读出口。

核心只校验和排版现役组合结果；不读工作区、不重新查询、不调用模型，
也不把证据包装成故事结论。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, TextIO

try:
    from . import ask_tool
except ImportError:  # pragma: no cover - 直接运行脚本时使用
    import ask_tool  # type: ignore[no-redef]


TOP_LEVEL_KEYS = {
    "facts_snapshot",
    "chapter_index_snapshot",
    "chapters_snapshot",
    "visible_chapter_revision_refs",
    "m6",
}
WATERMARK_KEYS = {"version", "sha256"}
M6_KEYS = {"reader_scope", "query", "matches", "evidence", "excluded_counts"}
READER_SCOPE_KEYS = {
    "mode",
    "as_of_chapter_id",
    "visible_chapter_count",
    "future_chapter_count",
    "blocked_fact_count",
}
EVIDENCE_WITH_CONTEXT_KEYS = ask_tool.EVIDENCE_KEYS | {"context"}
CONTEXT_KEYS = {
    "window_start",
    "window_end",
    "text",
    "highlight_start",
    "highlight_end",
}
EVIDENCE_BASE_ORDER = (
    "fact_id",
    "source",
    "quote",
    "chapter_revision_ref",
    "anchor_ref",
)


class AskReaderContextToolError(ValueError):
    """组合结果无法证明截点、证据或高亮闭合时拒绝。"""


def _valid_int(value: object, *, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _validate_watermark(
    value: object,
    label: str,
    *,
    allow_missing: bool,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != WATERMARK_KEYS:
        raise AskReaderContextToolError(f"{label}_SNAPSHOT_IDENTITY_INVALID")
    version = value.get("version")
    sha256 = value.get("sha256")
    if not _valid_int(version, minimum=0):
        raise AskReaderContextToolError(f"{label}_SNAPSHOT_IDENTITY_INVALID")
    if version == 0:
        if not allow_missing or sha256 is not None:
            raise AskReaderContextToolError(f"{label}_SNAPSHOT_IDENTITY_INVALID")
    elif not isinstance(sha256, str) or ask_tool.SHA256_RE.fullmatch(sha256) is None:
        raise AskReaderContextToolError(f"{label}_SNAPSHOT_IDENTITY_INVALID")
    return copy.deepcopy(value)


def _ref_key(value: dict[str, Any]) -> tuple[str, int, str]:
    return (
        value["chapter_id"],
        value["revision_no"],
        value["revision_text_sha256"],
    )


def _validate_visible_refs(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise AskReaderContextToolError("VISIBLE_CHAPTER_REVISION_REFS_INVALID")
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_ref in enumerate(value, start=1):
        if not ask_tool._valid_revision_ref(raw_ref):
            raise AskReaderContextToolError(
                f"VISIBLE_CHAPTER_REVISION_REF_INVALID:{index}"
            )
        chapter_id = raw_ref["chapter_id"]
        if chapter_id in seen:
            raise AskReaderContextToolError(
                f"VISIBLE_CHAPTER_REVISION_REF_DUPLICATE:{chapter_id}"
            )
        seen.add(chapter_id)
        refs.append(copy.deepcopy(raw_ref))
    return refs


def _validate_reader_scope(
    value: object,
    visible_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != READER_SCOPE_KEYS:
        raise AskReaderContextToolError("READER_SCOPE_INVALID")
    if value.get("mode") != "AS_OF_CHAPTER":
        raise AskReaderContextToolError("READER_SCOPE_MODE_INVALID")
    as_of = value.get("as_of_chapter_id")
    if not isinstance(as_of, str) or not as_of:
        raise AskReaderContextToolError("READER_SCOPE_CUTOFF_INVALID")
    for key in (
        "visible_chapter_count",
        "future_chapter_count",
        "blocked_fact_count",
    ):
        if not _valid_int(value.get(key), minimum=0):
            raise AskReaderContextToolError(f"READER_SCOPE_COUNT_INVALID:{key}")
    if (
        value["visible_chapter_count"] != len(visible_refs)
        or not visible_refs
        or visible_refs[-1]["chapter_id"] != as_of
    ):
        raise AskReaderContextToolError("READER_SCOPE_VISIBLE_PREFIX_MISMATCH")
    return copy.deepcopy(value)


def _validate_context(
    value: object,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    fact_id = evidence["fact_id"]
    if not isinstance(value, dict) or set(value) != CONTEXT_KEYS:
        raise AskReaderContextToolError(f"CONTEXT_SHAPE_INVALID:{fact_id}")
    window_start = value.get("window_start")
    window_end = value.get("window_end")
    text = value.get("text")
    highlight_start = value.get("highlight_start")
    highlight_end = value.get("highlight_end")
    if (
        not _valid_int(window_start, minimum=0)
        or not _valid_int(window_end, minimum=1)
        or window_start >= window_end
        or not isinstance(text, str)
        or window_end - window_start != len(text)
        or not _valid_int(highlight_start, minimum=0)
        or not _valid_int(highlight_end, minimum=1)
        or highlight_start >= highlight_end
        or highlight_end > len(text)
    ):
        raise AskReaderContextToolError(f"CONTEXT_COORDINATE_INVALID:{fact_id}")
    quote = evidence["quote"]
    anchor = evidence["anchor_ref"]
    if (
        text[highlight_start:highlight_end] != quote
        or window_start + highlight_start != anchor["start"]
        or window_start + highlight_end != anchor["end"]
    ):
        raise AskReaderContextToolError(f"CONTEXT_HIGHLIGHT_MISMATCH:{fact_id}")
    return copy.deepcopy(value)


def validate_result(value: object) -> dict[str, Any]:
    """严格校验完整组合结果，不读取任何外部状态。"""
    if not isinstance(value, dict) or set(value) != TOP_LEVEL_KEYS:
        raise AskReaderContextToolError("READER_CONTEXT_RESULT_SHAPE_INVALID")
    facts_snapshot = _validate_watermark(
        value["facts_snapshot"],
        "FACTS",
        allow_missing=True,
    )
    index_snapshot = _validate_watermark(
        value["chapter_index_snapshot"],
        "CHAPTER_INDEX",
        allow_missing=False,
    )
    chapters_snapshot = _validate_watermark(
        value["chapters_snapshot"],
        "CHAPTERS",
        allow_missing=False,
    )
    if index_snapshot["version"] != chapters_snapshot["version"]:
        raise AskReaderContextToolError("CHAPTER_SNAPSHOT_VERSION_DIVERGED")

    visible_refs = _validate_visible_refs(value["visible_chapter_revision_refs"])
    raw_m6 = value["m6"]
    if not isinstance(raw_m6, dict) or set(raw_m6) != M6_KEYS:
        raise AskReaderContextToolError("M6_READER_CONTEXT_SHAPE_INVALID")
    reader_scope = _validate_reader_scope(raw_m6["reader_scope"], visible_refs)
    raw_evidence = raw_m6["evidence"]
    if not isinstance(raw_evidence, list):
        raise AskReaderContextToolError("M6_EVIDENCE_NOT_LIST")

    base_evidence: list[dict[str, Any]] = []
    context_by_fact: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(raw_evidence, start=1):
        if not isinstance(item, dict) or set(item) != EVIDENCE_WITH_CONTEXT_KEYS:
            raise AskReaderContextToolError(
                f"M6_EVIDENCE_CONTEXT_SHAPE_INVALID:{index}"
            )
        base = {key: copy.deepcopy(item[key]) for key in EVIDENCE_BASE_ORDER}
        base_evidence.append(base)
        context_by_fact[base["fact_id"]] = _validate_context(item["context"], base)

    try:
        base_result = ask_tool.validate_result(
            {
                "query": raw_m6["query"],
                "matches": raw_m6["matches"],
                "evidence": base_evidence,
                "excluded_counts": raw_m6["excluded_counts"],
            }
        )
    except ask_tool.AskToolError as exc:
        raise AskReaderContextToolError(f"M6_RESULT_INVALID:{exc}") from exc

    visible_keys = {_ref_key(ref) for ref in visible_refs}
    evidence_by_id = {item["fact_id"]: item for item in base_result["evidence"]}
    for match in base_result["matches"]:
        fact_id = match["fact_id"]
        evidence = evidence_by_id[fact_id]
        if (
            _ref_key(match["chapter_revision_ref"]) not in visible_keys
            or _ref_key(evidence["chapter_revision_ref"]) not in visible_keys
        ):
            raise AskReaderContextToolError(f"FUTURE_OR_UNKNOWN_CHAPTER:{fact_id}")

    enriched_evidence = [
        {
            **copy.deepcopy(item),
            "context": context_by_fact[item["fact_id"]],
        }
        for item in base_result["evidence"]
    ]
    return {
        "facts_snapshot": facts_snapshot,
        "chapter_index_snapshot": index_snapshot,
        "chapters_snapshot": chapters_snapshot,
        "visible_chapter_revision_refs": visible_refs,
        "m6": {
            "reader_scope": reader_scope,
            "query": base_result["query"],
            "matches": base_result["matches"],
            "evidence": enriched_evidence,
            "excluded_counts": base_result["excluded_counts"],
        },
    }


def render_result(value: object) -> str:
    """把严格校验后的组合结果排成人读证据文本，不生成故事答案。"""
    checked = validate_result(value)
    m6 = checked["m6"]
    scope = m6["reader_scope"]
    evidence_by_id = {item["fact_id"]: item for item in m6["evidence"]}
    lines = [
        "M6 截止章节证据查询",
        f"原问题：{m6['query']}",
        f"截至章节：{scope['as_of_chapter_id']}",
        "防剧透声明：只展示冻结章节索引中截至该章的证据与同 revision 上下文。",
        (
            "范围统计："
            f"可见章节 {scope['visible_chapter_count']}，"
            f"未来章节 {scope['future_chapter_count']}，"
            f"拦截未来事实 {scope['blocked_fact_count']}。"
        ),
        f"命中：{len(m6['matches'])} 条",
        "",
    ]
    if not m6["matches"]:
        lines.extend(
            [
                "截至该章和当前证据门下，没有符合当前版本与证据门的命中。",
                "",
            ]
        )
    else:
        for index, match in enumerate(m6["matches"], start=1):
            evidence = evidence_by_id[match["fact_id"]]
            ref = match["chapter_revision_ref"]
            anchor = evidence["anchor_ref"]
            context = evidence["context"]
            highlighted = (
                context["text"][: context["highlight_start"]]
                + "【"
                + context["text"][
                    context["highlight_start"] : context["highlight_end"]
                ]
                + "】"
                + context["text"][context["highlight_end"] :]
            )
            lines.extend(
                [
                    f"[{index}] 事实 {match['fact_id']}",
                    f"事实句：{match['text']}",
                    (
                        "章节 revision："
                        f"{ref['chapter_id']} / r{ref['revision_no']} / "
                        f"{ref['revision_text_sha256']}"
                    ),
                    f"证据来源：{evidence['source']}",
                    f"原文 quote：{evidence['quote']}",
                    f"anchor：[{anchor['start']}, {anchor['end']})",
                    f"anchor SHA-256：{anchor['slice_sha256']}",
                    (
                        "同 revision 上下文："
                        f"[{context['window_start']}, {context['window_end']}) "
                        f"{highlighted}"
                    ),
                    "",
                ]
            )
    lines.append("排除统计：")
    for key in ask_tool.EXCLUDED_COUNT_KEYS:
        label = ask_tool.EXCLUDED_COUNT_LABELS.get(key, key)
        lines.append(f"- {label}（{key}）：{m6['excluded_counts'][key]}")
    return "\n".join(lines) + "\n"


def _read_json(path_text: str | None, stdin: TextIO) -> dict[str, Any]:
    try:
        if path_text in {None, "-"}:
            value = json.load(stdin)
        else:
            value = json.loads(Path(path_text).read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AskReaderContextToolError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise AskReaderContextToolError("INPUT_OBJECT_REQUIRED")
    return value


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_text_atomic(path: Path, value: str) -> None:
    if not path.parent.is_dir():
        raise AskReaderContextToolError("OUTPUT_PARENT_NOT_DIRECTORY")
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
            handle.write(value.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="M6 LOCAL_FILESYSTEM_ONLY 截止章节证据人读工具"
    )
    parser.add_argument("--input", help="组合结果 JSON；不给或 - 时读 stdin")
    parser.add_argument("--output", help="人读 UTF-8 文本；不给或 - 时写 stdout")
    args = parser.parse_args(argv)
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        if (
            args.input not in {None, "-"}
            and args.output not in {None, "-"}
            and Path(args.input).resolve() == Path(args.output).resolve()
        ):
            raise AskReaderContextToolError("INPUT_OUTPUT_PATH_MUST_DIFFER")
        rendered = render_result(_read_json(args.input, stdin))
        if args.output in {None, "-"}:
            stdout.write(rendered)
            stdout.flush()
        else:
            _write_text_atomic(Path(args.output), rendered)
    except (AskReaderContextToolError, OSError) as exc:
        stderr.write(f"ask_reader_context_tool error: {exc}\n")
        stderr.flush()
        return 2
    return 0


__all__ = [
    "AskReaderContextToolError",
    "render_result",
    "validate_result",
]


if __name__ == "__main__":
    raise SystemExit(main())
