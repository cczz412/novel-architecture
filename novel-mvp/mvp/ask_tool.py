"""M6 零模型、LOCAL_FILESYSTEM_ONLY 的证据查询工具。

核心 ``execute(request)`` 只接收内存对象，不知道项目目录或 facts.json。
文件、stdin/stdout 仅由本文件的命令行适配层处理。输出是工具运输外壳，
不是正式 C6 或新的产品合同。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


TRANSPORT_SCOPE = "LOCAL_FILESYSTEM_ONLY"
COORDINATE_BASIS = "CHAPTER_REVISION_TEXT_UNICODE_CODEPOINT_0_BASED_HALF_OPEN"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVISION_REF_KEYS = {"chapter_id", "revision_no", "revision_text_sha256"}
ANCHOR_REF_KEYS = {
    "chapter_id",
    "revision_no",
    "revision_text_sha256",
    "coordinate_basis",
    "start",
    "end",
    "slice_sha256",
}
EXCLUDED_COUNT_KEYS = (
    "invalid_c4_v1",
    "extracted",
    "rejected",
    "needs_recheck",
    "current_revision_missing",
    "stale_revision",
    "unverified_evidence",
    "invalid_evidence",
    "keyword_miss",
)
RESULT_KEYS = {"query", "matches", "evidence", "excluded_counts"}
MATCH_KEYS = {"fact_id", "chapter_id", "text", "chapter_revision_ref"}
EVIDENCE_KEYS = {
    "fact_id",
    "source",
    "quote",
    "chapter_revision_ref",
    "anchor_ref",
}
EXCLUDED_COUNT_LABELS = {
    "invalid_c4_v1": "非法 C4",
    "extracted": "尚未确认",
    "rejected": "已拒绝",
    "needs_recheck": "需要复核",
    "current_revision_missing": "缺少当前章节版本",
    "stale_revision": "旧章节版本",
    "unverified_evidence": "证据未验证",
    "invalid_evidence": "证据坐标损坏",
    "keyword_miss": "关键词未命中",
}


class AskToolError(ValueError):
    """请求或本地适配输入不满足查询前提。"""


def _is_int(value: object, *, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _valid_revision_ref(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == REVISION_REF_KEYS
        and isinstance(value.get("chapter_id"), str)
        and bool(value["chapter_id"])
        and _is_int(value.get("revision_no"), minimum=1)
        and _valid_sha256(value.get("revision_text_sha256"))
    )


def _current_revision_index(raw_refs: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_refs, list):
        raise AskToolError("current_revision_refs 必须是列表")
    result: dict[str, dict[str, Any]] = {}
    for index, ref in enumerate(raw_refs):
        if not _valid_revision_ref(ref):
            raise AskToolError(f"current_revision_refs[{index}] 不是合法 revision ref")
        chapter_id = ref["chapter_id"]
        if chapter_id in result:
            raise AskToolError(f"current revision 重复：{chapter_id}")
        result[chapter_id] = copy.deepcopy(ref)
    return result


def _c4_identity_valid(fact: object) -> bool:
    return (
        isinstance(fact, dict)
        and fact.get("contract") == "C4_FACT_QUERY"
        and fact.get("version") == "v1"
        and isinstance(fact.get("id"), str)
        and bool(fact["id"])
        and isinstance(fact.get("chapter_id"), str)
        and bool(fact["chapter_id"])
        and isinstance(fact.get("text"), str)
        and bool(fact["text"])
        and isinstance(fact.get("quote"), str)
        and isinstance(fact.get("source"), str)
        and bool(fact["source"])
    )


def _anchor_valid(fact: dict[str, Any]) -> bool:
    revision_ref = fact.get("chapter_revision_ref")
    anchor = fact.get("anchor_ref")
    quote = fact.get("quote")
    if (
        fact.get("anchor_state") != "VERIFIED"
        or fact.get("recheck") is not None
        or not _valid_revision_ref(revision_ref)
        or not isinstance(anchor, dict)
        or set(anchor) != ANCHOR_REF_KEYS
        or not isinstance(quote, str)
        or not quote
    ):
        return False
    if any(anchor.get(key) != revision_ref[key] for key in REVISION_REF_KEYS):
        return False
    start, end = anchor.get("start"), anchor.get("end")
    if (
        anchor.get("coordinate_basis") != COORDINATE_BASIS
        or not _is_int(start, minimum=0)
        or not _is_int(end, minimum=1)
        or start >= end
        or end - start != len(quote)
        or not _valid_sha256(anchor.get("slice_sha256"))
    ):
        return False
    quote_sha256 = hashlib.sha256(quote.encode("utf-8")).hexdigest()
    return anchor["slice_sha256"] == quote_sha256


def _matches(text: str, keywords: list[str]) -> bool:
    folded = text.casefold()
    return all(keyword.casefold() in folded for keyword in keywords)


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """查询调用者提供的 C4 v1 快照，不读取任何文件或项目目录。"""

    if not isinstance(request, dict):
        raise AskToolError("request 必须是对象")
    if set(request) != {"query", "facts", "current_revision_refs"}:
        raise AskToolError(
            "request 只允许 query、facts、current_revision_refs"
        )
    query = request["query"]
    if not isinstance(query, str) or not query.strip():
        raise AskToolError("query 必须是非空字符串")
    keywords = query.split()
    facts = request["facts"]
    if not isinstance(facts, list):
        raise AskToolError("facts 必须是 C4 v1 对象列表")
    current_refs = _current_revision_index(request["current_revision_refs"])
    counts = {key: 0 for key in EXCLUDED_COUNT_KEYS}
    matches: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    seen_fact_ids: set[str] = set()

    for fact in facts:
        if not _c4_identity_valid(fact):
            counts["invalid_c4_v1"] += 1
            continue
        fact_id = fact["id"]
        if fact_id in seen_fact_ids:
            raise AskToolError(f"C4 fact id 重复：{fact_id}")
        seen_fact_ids.add(fact_id)
        status = fact.get("status")
        if status == "extracted":
            counts["extracted"] += 1
            continue
        if status == "rejected":
            counts["rejected"] += 1
            continue
        if status == "needs_recheck":
            counts["needs_recheck"] += 1
            continue
        if status != "confirmed":
            counts["invalid_c4_v1"] += 1
            continue
        revision_ref = fact.get("chapter_revision_ref")
        if not _valid_revision_ref(revision_ref):
            counts["invalid_c4_v1"] += 1
            continue
        if revision_ref["chapter_id"] != fact["chapter_id"]:
            counts["invalid_c4_v1"] += 1
            continue
        current_ref = current_refs.get(fact["chapter_id"])
        if current_ref is None:
            counts["current_revision_missing"] += 1
            continue
        if revision_ref != current_ref:
            counts["stale_revision"] += 1
            continue
        if fact.get("anchor_state") != "VERIFIED":
            counts["unverified_evidence"] += 1
            continue
        if not _anchor_valid(fact):
            counts["invalid_evidence"] += 1
            continue
        if not _matches(fact["text"], keywords):
            counts["keyword_miss"] += 1
            continue
        matches.append(
            {
                "fact_id": fact_id,
                "chapter_id": fact["chapter_id"],
                "text": fact["text"],
                "chapter_revision_ref": copy.deepcopy(revision_ref),
            }
        )
        evidence.append(
            {
                "fact_id": fact_id,
                "source": fact["source"],
                "quote": fact["quote"],
                "chapter_revision_ref": copy.deepcopy(revision_ref),
                "anchor_ref": copy.deepcopy(fact["anchor_ref"]),
            }
        )

    return {
        "query": query,
        "matches": matches,
        "evidence": evidence,
        "excluded_counts": counts,
    }


def _validate_result_match(value: object, index: int) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != MATCH_KEYS:
        raise AskToolError(f"matches[{index}] 形状损坏")
    fact_id = value.get("fact_id")
    chapter_id = value.get("chapter_id")
    text = value.get("text")
    revision_ref = value.get("chapter_revision_ref")
    if (
        not isinstance(fact_id, str)
        or not fact_id
        or not isinstance(chapter_id, str)
        or not chapter_id
        or not isinstance(text, str)
        or not text
        or not _valid_revision_ref(revision_ref)
        or revision_ref["chapter_id"] != chapter_id
    ):
        raise AskToolError(f"matches[{index}] 内容损坏")
    return copy.deepcopy(value)


def _validate_result_evidence(value: object, index: int) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != EVIDENCE_KEYS:
        raise AskToolError(f"evidence[{index}] 形状损坏")
    fact_id = value.get("fact_id")
    source = value.get("source")
    quote = value.get("quote")
    revision_ref = value.get("chapter_revision_ref")
    anchor = value.get("anchor_ref")
    if (
        not isinstance(fact_id, str)
        or not fact_id
        or not isinstance(source, str)
        or not source
        or not isinstance(quote, str)
        or not quote
        or not _valid_revision_ref(revision_ref)
        or not isinstance(anchor, dict)
        or set(anchor) != ANCHOR_REF_KEYS
    ):
        raise AskToolError(f"evidence[{index}] 内容损坏")
    if any(anchor.get(key) != revision_ref[key] for key in REVISION_REF_KEYS):
        raise AskToolError(f"evidence[{index}] revision 与 anchor 不一致")
    start = anchor.get("start")
    end = anchor.get("end")
    if (
        anchor.get("coordinate_basis") != COORDINATE_BASIS
        or not _is_int(start, minimum=0)
        or not _is_int(end, minimum=1)
        or start >= end
        or end - start != len(quote)
        or not _valid_sha256(anchor.get("slice_sha256"))
        or anchor["slice_sha256"]
        != hashlib.sha256(quote.encode("utf-8")).hexdigest()
    ):
        raise AskToolError(f"evidence[{index}] anchor 或 SHA 损坏")
    return copy.deepcopy(value)


def validate_result(result: object) -> dict[str, Any]:
    """严格校验现有 M6 结果；不查询 facts，也不生成新结论。"""
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        raise AskToolError("M6 result 形状损坏")
    query = result.get("query")
    matches = result.get("matches")
    evidence = result.get("evidence")
    counts = result.get("excluded_counts")
    if not isinstance(query, str) or not query.strip():
        raise AskToolError("M6 result query 损坏")
    if not isinstance(matches, list) or not isinstance(evidence, list):
        raise AskToolError("M6 result matches/evidence 必须是列表")
    if not isinstance(counts, dict) or set(counts) != set(EXCLUDED_COUNT_KEYS):
        raise AskToolError("M6 result excluded_counts 形状损坏")
    if any(not _is_int(counts[key], minimum=0) for key in EXCLUDED_COUNT_KEYS):
        raise AskToolError("M6 result excluded_counts 数值损坏")

    checked_matches: list[dict[str, Any]] = []
    match_by_id: dict[str, dict[str, Any]] = {}
    for index, raw_match in enumerate(matches):
        match = _validate_result_match(raw_match, index)
        fact_id = match["fact_id"]
        if fact_id in match_by_id:
            raise AskToolError(f"matches fact_id 重复：{fact_id}")
        match_by_id[fact_id] = match
        checked_matches.append(match)

    checked_evidence: list[dict[str, Any]] = []
    evidence_by_id: dict[str, dict[str, Any]] = {}
    for index, raw_evidence in enumerate(evidence):
        evidence_item = _validate_result_evidence(raw_evidence, index)
        fact_id = evidence_item["fact_id"]
        if fact_id in evidence_by_id:
            raise AskToolError(f"evidence fact_id 重复：{fact_id}")
        evidence_by_id[fact_id] = evidence_item
        checked_evidence.append(evidence_item)

    if set(match_by_id) != set(evidence_by_id):
        raise AskToolError("matches 与 evidence 未按 fact_id 一一闭合")
    for fact_id, match in match_by_id.items():
        evidence_item = evidence_by_id[fact_id]
        if match["chapter_revision_ref"] != evidence_item["chapter_revision_ref"]:
            raise AskToolError(f"事实与证据 revision 不一致：{fact_id}")

    return {
        "query": query,
        "matches": checked_matches,
        "evidence": checked_evidence,
        "excluded_counts": copy.deepcopy(counts),
    }


def render_result(result: object) -> str:
    """把已校验 M6 结果稳定排成人读证据文本，不增加推断。"""
    checked = validate_result(result)
    evidence_by_id = {
        item["fact_id"]: item for item in checked["evidence"]
    }
    lines = [
        "M6 证据查询结果",
        f"原查询：{checked['query']}",
        f"符合证据门的命中：{len(checked['matches'])} 条",
        "",
    ]
    if not checked["matches"]:
        lines.extend(["没有符合当前版本与证据门的命中。", ""])
    else:
        for index, match in enumerate(checked["matches"], start=1):
            evidence_item = evidence_by_id[match["fact_id"]]
            revision_ref = match["chapter_revision_ref"]
            anchor = evidence_item["anchor_ref"]
            lines.extend(
                [
                    f"[{index}] 事实 {match['fact_id']}",
                    f"事实句：{match['text']}",
                    (
                        "章节版本："
                        f"{revision_ref['chapter_id']} / revision "
                        f"{revision_ref['revision_no']}"
                    ),
                    f"章节文本 SHA-256：{revision_ref['revision_text_sha256']}",
                    f"证据来源：{evidence_item['source']}",
                    f"原文证据：{evidence_item['quote']}",
                    f"证据坐标：[{anchor['start']}, {anchor['end']})",
                    f"坐标口径：{anchor['coordinate_basis']}",
                    f"证据片段 SHA-256：{anchor['slice_sha256']}",
                    "",
                ]
            )
    lines.append("排除统计：")
    for key in EXCLUDED_COUNT_KEYS:
        lines.append(f"- {EXCLUDED_COUNT_LABELS[key]}（{key}）：{checked['excluded_counts'][key]}")
    return "\n".join(lines) + "\n"


def _read_request(path_text: str | None) -> dict[str, Any]:
    if path_text in {None, "-"}:
        raw = sys.stdin.read()
    else:
        raw = Path(path_text).read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AskToolError(f"输入不是合法 JSON：{exc.msg}") from exc
    if not isinstance(value, dict):
        raise AskToolError("输入 JSON 顶层必须是对象")
    return value


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    payload = _json_bytes(value)
    parent = path.parent
    if not parent.is_dir():
        raise AskToolError(f"输出目录不存在：{parent}")
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
    except BaseException:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _atomic_write_text(path: Path, value: str) -> None:
    payload = value.encode("utf-8")
    parent = path.parent
    if not parent.is_dir():
        raise AskToolError(f"输出目录不存在：{parent}")
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


def _write_rendered(path_text: str | None, rendered: str) -> None:
    if path_text in {None, "-"}:
        sys.stdout.buffer.write(rendered.encode("utf-8"))
        sys.stdout.buffer.flush()
        return
    _atomic_write_text(Path(path_text), rendered)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="M6 LOCAL_FILESYSTEM_ONLY C4 v1 evidence query tool"
    )
    parser.add_argument("--input", help="本地 JSON；省略或 - 时读 stdin")
    parser.add_argument("--output", help="本地输出；省略或 - 时写 stdout")
    parser.add_argument(
        "--render",
        action="store_true",
        help="把已存在的 M6 result JSON 排成人读证据文本",
    )
    args = parser.parse_args(argv)
    try:
        value = _read_request(args.input)
        if args.render:
            _write_rendered(args.output, render_result(value))
        else:
            _write_result(args.output, execute(value))
    except (AskToolError, OSError) as exc:
        print(f"ask_tool error: {exc}", file=sys.stderr)
        return 2
    return 0


__all__ = ["AskToolError", "execute", "render_result", "validate_result"]


if __name__ == "__main__":
    raise SystemExit(main())
