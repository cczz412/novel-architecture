"""M6 查询证据的机械上下文展开工具。

对象核心只使用现役 M6 结果中的 VERIFIED anchor 和调用方提供的 C1 v1
current view；不搜索相似文本，不猜位置，不读工作区，不调模型。
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
from typing import Any, TextIO

if __package__:
    from . import ask_tool
else:  # 允许直接运行本地文件工具。
    import ask_tool


TRANSPORT_SCOPE = "LOCAL_FILESYSTEM_ONLY"
REQUEST_FIELDS = frozenset({"m6_result", "current_chapters", "before_chars", "after_chars"})
M6_FIELDS = frozenset({"query", "matches", "evidence", "excluded_counts"})
MATCH_FIELDS = frozenset({"fact_id", "chapter_id", "text", "chapter_revision_ref"})
EVIDENCE_FIELDS = frozenset(
    {"fact_id", "source", "quote", "chapter_revision_ref", "anchor_ref"}
)
C1_FIELDS = frozenset(
    {"contract", "version", "id", "title", "kind", "text", "added_at", "chapter_revision_ref"}
)
CHAPTER_ID_RE = re.compile(r"^c[0-9]{2,}$")


class AskContextError(RuntimeError):
    """证据与 current C1 无法逐字对平时整批拒绝。"""


def _valid_int(value: object, *, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _validate_revision_ref(value: object, *, reason: str) -> dict[str, Any]:
    if not ask_tool._valid_revision_ref(value):
        raise AskContextError(reason)
    return copy.deepcopy(value)


def _chapter_index(raw_chapters: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_chapters, list):
        raise AskContextError("CURRENT_CHAPTERS_MUST_BE_LIST")
    indexed: dict[str, dict[str, Any]] = {}
    for index, chapter in enumerate(raw_chapters, start=1):
        if not isinstance(chapter, dict) or set(chapter) != C1_FIELDS:
            raise AskContextError(f"C1_CURRENT_VIEW_SHAPE_INVALID:{index}")
        if (
            chapter.get("contract") != "C1_CHAPTER_DOC"
            or chapter.get("version") != "v1"
            or chapter.get("kind") != "draft"
            or not isinstance(chapter.get("id"), str)
            or CHAPTER_ID_RE.fullmatch(chapter["id"]) is None
            or not isinstance(chapter.get("title"), str)
            or not chapter["title"]
            or not isinstance(chapter.get("text"), str)
            or not isinstance(chapter.get("added_at"), str)
            or not chapter["added_at"]
        ):
            raise AskContextError(f"C1_CURRENT_VIEW_IDENTITY_INVALID:{index}")
        revision_ref = _validate_revision_ref(
            chapter["chapter_revision_ref"],
            reason=f"C1_CURRENT_VIEW_REVISION_REF_INVALID:{index}",
        )
        if revision_ref["chapter_id"] != chapter["id"]:
            raise AskContextError(f"C1_CURRENT_VIEW_REVISION_CHAPTER_MISMATCH:{index}")
        text_sha = hashlib.sha256(chapter["text"].encode("utf-8")).hexdigest()
        if revision_ref["revision_text_sha256"] != text_sha:
            raise AskContextError(f"C1_CURRENT_VIEW_TEXT_SHA_MISMATCH:{index}")
        if chapter["id"] in indexed:
            raise AskContextError(f"C1_CURRENT_VIEW_DUPLICATE:{chapter['id']}")
        indexed[chapter["id"]] = copy.deepcopy(chapter)
    return indexed


def _validate_m6_result(raw: object) -> tuple[dict[str, Any], dict[str, dict], dict[str, dict]]:
    if not isinstance(raw, dict) or set(raw) != M6_FIELDS:
        raise AskContextError("M6_RESULT_SHAPE_INVALID")
    if not isinstance(raw.get("query"), str) or not raw["query"].strip():
        raise AskContextError("M6_QUERY_INVALID")
    if not isinstance(raw.get("matches"), list) or not isinstance(raw.get("evidence"), list):
        raise AskContextError("M6_MATCH_OR_EVIDENCE_NOT_LIST")
    counts = raw.get("excluded_counts")
    if (
        not isinstance(counts, dict)
        or set(counts) != set(ask_tool.EXCLUDED_COUNT_KEYS)
        or any(not _valid_int(value, minimum=0) for value in counts.values())
    ):
        raise AskContextError("M6_EXCLUDED_COUNTS_INVALID")

    matches: dict[str, dict] = {}
    for index, match in enumerate(raw["matches"], start=1):
        if not isinstance(match, dict) or set(match) != MATCH_FIELDS:
            raise AskContextError(f"M6_MATCH_SHAPE_INVALID:{index}")
        fact_id = match.get("fact_id")
        if not isinstance(fact_id, str) or not fact_id:
            raise AskContextError(f"M6_MATCH_FACT_ID_INVALID:{index}")
        if fact_id in matches:
            raise AskContextError(f"M6_MATCH_DUPLICATE:{fact_id}")
        if (
            not isinstance(match.get("chapter_id"), str)
            or not match["chapter_id"]
            or not isinstance(match.get("text"), str)
            or not match["text"]
        ):
            raise AskContextError(f"M6_MATCH_CONTENT_INVALID:{index}")
        _validate_revision_ref(
            match["chapter_revision_ref"],
            reason=f"M6_MATCH_REVISION_REF_INVALID:{index}",
        )
        matches[fact_id] = match

    evidence: dict[str, dict] = {}
    for index, item in enumerate(raw["evidence"], start=1):
        if not isinstance(item, dict) or set(item) != EVIDENCE_FIELDS:
            raise AskContextError(f"M6_EVIDENCE_SHAPE_INVALID:{index}")
        fact_id = item.get("fact_id")
        if not isinstance(fact_id, str) or not fact_id:
            raise AskContextError(f"M6_EVIDENCE_FACT_ID_INVALID:{index}")
        if fact_id in evidence:
            raise AskContextError(f"M6_EVIDENCE_DUPLICATE:{fact_id}")
        if not isinstance(item.get("source"), str) or not item["source"]:
            raise AskContextError(f"M6_EVIDENCE_SOURCE_INVALID:{index}")
        if not isinstance(item.get("quote"), str) or not item["quote"]:
            raise AskContextError(f"M6_EVIDENCE_QUOTE_INVALID:{index}")
        _validate_revision_ref(
            item["chapter_revision_ref"],
            reason=f"M6_EVIDENCE_REVISION_REF_INVALID:{index}",
        )
        evidence[fact_id] = item

    if set(matches) != set(evidence):
        orphan_matches = sorted(set(matches) - set(evidence))
        orphan_evidence = sorted(set(evidence) - set(matches))
        raise AskContextError(
            "M6_MATCH_EVIDENCE_PAIRING_MISMATCH:"
            f"matches={','.join(orphan_matches)}:evidence={','.join(orphan_evidence)}"
        )
    return copy.deepcopy(raw), matches, evidence


def _context_for_evidence(
    match: dict[str, Any],
    evidence: dict[str, Any],
    chapter: dict[str, Any],
    *,
    before_chars: int,
    after_chars: int,
) -> dict[str, Any]:
    match_ref = match["chapter_revision_ref"]
    evidence_ref = evidence["chapter_revision_ref"]
    chapter_ref = chapter["chapter_revision_ref"]
    if match["chapter_id"] != chapter["id"] or match_ref != evidence_ref:
        raise AskContextError(f"M6_PAIR_REVISION_OR_CHAPTER_MISMATCH:{match['fact_id']}")
    if evidence_ref != chapter_ref:
        raise AskContextError(f"M6_EVIDENCE_NOT_CURRENT_C1:{match['fact_id']}")

    anchor = evidence["anchor_ref"]
    if not isinstance(anchor, dict) or set(anchor) != ask_tool.ANCHOR_REF_KEYS:
        raise AskContextError(f"M6_ANCHOR_SHAPE_INVALID:{match['fact_id']}")
    if any(anchor.get(key) != evidence_ref[key] for key in ask_tool.REVISION_REF_KEYS):
        raise AskContextError(f"M6_ANCHOR_REVISION_REF_MISMATCH:{match['fact_id']}")
    start, end = anchor.get("start"), anchor.get("end")
    quote = evidence["quote"]
    if (
        anchor.get("coordinate_basis") != ask_tool.COORDINATE_BASIS
        or not _valid_int(start, minimum=0)
        or not _valid_int(end, minimum=1)
        or start >= end
        or end - start != len(quote)
        or not isinstance(anchor.get("slice_sha256"), str)
        or ask_tool.SHA256_RE.fullmatch(anchor["slice_sha256"]) is None
    ):
        raise AskContextError(f"M6_ANCHOR_INVALID:{match['fact_id']}")
    text = chapter["text"]
    if end > len(text) or text[start:end] != quote:
        raise AskContextError(f"M6_ANCHOR_QUOTE_MISMATCH:{match['fact_id']}")
    quote_sha = hashlib.sha256(quote.encode("utf-8")).hexdigest()
    if anchor["slice_sha256"] != quote_sha:
        raise AskContextError(f"M6_ANCHOR_QUOTE_SHA_MISMATCH:{match['fact_id']}")

    window_start = max(0, start - before_chars)
    window_end = min(len(text), end + after_chars)
    return {
        "window_start": window_start,
        "window_end": window_end,
        "text": text[window_start:window_end],
        "highlight_start": start - window_start,
        "highlight_end": end - window_start,
    }


def execute(request: dict) -> dict:
    """为现役 M6 证据增加可回验的机械上下文窗口。"""
    if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
        raise AskContextError("REQUEST_SHAPE_INVALID")
    before_chars = request["before_chars"]
    after_chars = request["after_chars"]
    if not _valid_int(before_chars, minimum=0) or not _valid_int(after_chars, minimum=0):
        raise AskContextError("CONTEXT_WINDOW_PARAMETER_INVALID")

    m6_result, matches, evidence_by_id = _validate_m6_result(request["m6_result"])
    chapters = _chapter_index(request["current_chapters"])
    enriched: list[dict[str, Any]] = []
    for evidence in m6_result["evidence"]:
        fact_id = evidence["fact_id"]
        match = matches[fact_id]
        chapter = chapters.get(match["chapter_id"])
        if chapter is None:
            raise AskContextError(f"M6_EVIDENCE_CHAPTER_MISSING:{fact_id}")
        context = _context_for_evidence(
            match,
            evidence_by_id[fact_id],
            chapter,
            before_chars=before_chars,
            after_chars=after_chars,
        )
        enriched.append({**copy.deepcopy(evidence), "context": context})
    m6_result["evidence"] = enriched
    return m6_result


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise AskContextError(f"FILE_NOT_UTF8:{path}") from exc
    except json.JSONDecodeError as exc:
        raise AskContextError(f"FILE_NOT_JSON:{path}:{exc}") from exc


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        temp_name = None
        _fsync_directory(path.parent)
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="M6 LOCAL_FILESYSTEM_ONLY 证据上下文工具")
    parser.add_argument("--input", help="M6 结果＋C1 current view JSON；不给时读 stdin")
    parser.add_argument("--output", help="带上下文的 M6 JSON；不给时写 stdout")
    args = parser.parse_args(argv)
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        if args.input:
            request = _read_json(Path(args.input))
        else:
            try:
                request = json.load(stdin)
            except json.JSONDecodeError as exc:
                raise AskContextError(f"STDIN_NOT_JSON:{exc}") from exc
        result = execute(request)
        if args.output:
            _write_json_atomic(Path(args.output), result)
        else:
            json.dump(result, stdout, ensure_ascii=False, sort_keys=True, indent=2)
            stdout.write("\n")
            stdout.flush()
    except (AskContextError, OSError) as exc:
        stderr.write(f"M6_ASK_CONTEXT_REJECTED:{exc}\n")
        stderr.flush()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
