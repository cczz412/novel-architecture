#!/usr/bin/env python3
"""AA 批证据锚机械审计器。

只依赖 Python 标准库。它从 AA 续批拆分页的 manifest 读取大纲正文，
再到对应书的章节包中逐字核验“章号/序号＋原文短引”。

纪律：
- 不调用模型；
- 不改大纲或章节原文；
- 不做标点、空格、繁简或省略号归一化；
- 只剥短引最外层的 Markdown 包裹符；
- 非正文文件单独记账，不混入故事证据有效率。
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPLIT_ROOT = ROOT / "TEMP" / "AA批回包续_20260717" / "拆分上传"
DEFAULT_BOOKS_ROOT = ROOT / "TEMP" / "AA批外发包_20260717" / "books"

CODE_RE = re.compile(r"^AA(?P<number>\d{2})$")
SEQUENCE_RE = re.compile(r"^(?P<number>\d{1,4})_")
CHAPTER_RE = re.compile(r"第\s*(?P<number>[0-9〇零一二三四五六七八九十百两]+)\s*(?:章|回|节)")
OBJECT_ID_RE = re.compile(r"(?<![A-Z])(?P<type>[A-Z]{1,3})[-_]?\d{1,4}(?!\d)")

LOCATOR = r"(?:(?:第\s*0*(?P<chapter>\d{1,3})\s*章)|(?:序\s*0*(?P<sequence>\d{1,3})))"
# 章号与短引之间只允许排版标点。若放开成任意文字，
# “读到第3章时放弃‘逐章一条’”会被误认成证据锚。
SEPARATOR = r"(?P<separator>[\s·｜|:：—–\-]{0,8})"
QUOTE = (
    r"(?:"
    r"「(?P<corner>[^」\n]+)」"
    r"|『(?P<double_corner>[^』\n]+)』"
    r"|“(?P<curly>[^”\n]+)”"
    r"|\"(?P<straight>[^\"\n]+)\""
    r"|‘(?P<single_curly>[^’\n]+)’"
    r"|`(?P<backtick>[^`\n]+)`"
    r")"
)
ANCHOR_RE = re.compile(LOCATOR + SEPARATOR + QUOTE)
ANCHOR_LIKE_RE = re.compile(LOCATOR + r"[\s·｜|:：—–\-]{0,8}[「『“\"‘`]")

QUOTE_GROUPS = ("corner", "double_corner", "curly", "straight", "single_curly", "backtick")
MARKDOWN_WRAPPERS = (("**", "**"), ("__", "__"), ("~~", "~~"), ("`", "`"))
NON_STORY_HINTS = ("上架感言", "请假", "单章", "完本感言", "作者的话", "写在前面")


class AuditError(RuntimeError):
    """可读的审计输入错误。"""


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def parse_codes(spec: str) -> list[str]:
    """解析 AA11-AA16,AA20 这类范围。"""
    result: list[str] = []
    for raw in (piece.strip() for piece in spec.split(",")):
        if not raw:
            continue
        range_match = re.fullmatch(r"AA(\d{2})-AA(\d{2})", raw)
        if range_match:
            start, end = map(int, range_match.groups())
            if start > end:
                raise AuditError(f"编号范围倒置：{raw}")
            result.extend(f"AA{number:02d}" for number in range(start, end + 1))
            continue
        if not CODE_RE.fullmatch(raw):
            raise AuditError(f"无法识别的编号：{raw}")
        result.append(raw)
    return list(dict.fromkeys(result))


def chinese_number(value: str) -> int | None:
    """把一至九十九等中文章号转成整数。"""
    if value.isdigit():
        return int(value)
    digits = {"〇": 0, "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100}
    total = 0
    current = 0
    seen = False
    for char in value:
        if char in digits:
            current = digits[char]
            seen = True
        elif char in units:
            unit = units[char]
            total += (current or 1) * unit
            current = 0
            seen = True
        else:
            return None
    return total + current if seen else None


def source_logical_chapter(path: Path, text: str) -> int | None:
    candidates = [path.stem]
    candidates.extend(line.strip() for line in text.splitlines()[:5] if line.strip())
    for candidate in candidates:
        match = CHAPTER_RE.search(candidate)
        if match:
            return chinese_number(match.group("number"))
    return None


def source_sequence(path: Path) -> int | None:
    match = SEQUENCE_RE.match(path.name)
    return int(match.group("number")) if match else None


def is_non_story_source(path: Path, text: str) -> bool:
    name = path.stem
    first_lines = " ".join(line.strip() for line in text.splitlines()[:3] if line.strip())
    return any(hint in name or hint in first_lines for hint in NON_STORY_HINTS)


def strip_markdown_wrapper(quote: str) -> tuple[str, str | None]:
    """只剥整个短引最外层的 Markdown 包裹，不碰短引内部。"""
    for left, right in MARKDOWN_WRAPPERS:
        if quote.startswith(left) and quote.endswith(right) and len(quote) > len(left) + len(right):
            return quote[len(left):-len(right)], left
    return quote, None


def quote_from_match(match: re.Match[str]) -> str:
    for group in QUOTE_GROUPS:
        value = match.group(group)
        if value is not None:
            return value
    raise AuditError("内部错误：锚正则命中但没有短引")


def infer_object_type(line: str, start: int, section: str) -> str:
    before = line[:start]
    matches = list(OBJECT_ID_RE.finditer(before)) or list(OBJECT_ID_RE.finditer(line))
    if matches:
        # 表格首个 ID 通常是本记录类型；后面的 L1、上游 C002 等多是
        # 故事线或引用。取最后一个会把 AA20 的 C001 错认成 L。
        return matches[0].group("type")
    section_match = OBJECT_ID_RE.search(section)
    return section_match.group("type") if section_match else "未标"


def parse_anchor_line(line: str, *, section: str = "", line_number: int = 1) -> list[dict[str, Any]]:
    stripped = line.lstrip()
    if (stripped.startswith("#") or stripped.startswith("<summary")) and "锚" not in line and "证据" not in line:
        return []
    anchors: list[dict[str, Any]] = []
    for match in ANCHOR_RE.finditer(line):
        raw_quote = quote_from_match(match)
        quote, wrapper = strip_markdown_wrapper(raw_quote)
        kind = "chapter" if match.group("chapter") is not None else "sequence"
        number = int(match.group("chapter") or match.group("sequence"))
        anchors.append({
            "locator_kind": kind,
            "locator_number": number,
            "raw_locator": match.group(0)[: match.group(0).find(raw_quote)],
            "separator": match.group("separator"),
            "quote": quote,
            "raw_quote": raw_quote,
            "markdown_wrapper_removed": wrapper,
            "quote_chars": len(quote),
            "length_gate": "pass" if 10 <= len(quote) <= 25 else "fail",
            "line": line_number,
            "column": match.start() + 1,
            "section": section,
            "object_type": infer_object_type(line, match.start(), section),
            "line_text": line.rstrip("\n"),
        })
    return anchors


def parse_outline_files(files: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    anchors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for path in files:
        section = ""
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                section = stripped.lstrip("#").strip()
            parsed = parse_anchor_line(line, section=section, line_number=line_number)
            for item in parsed:
                item["outline_path"] = rel(path)
                anchors.append(item)
            if not (stripped.startswith("#") or stripped.startswith("<summary")):
                like_count = len(list(ANCHOR_LIKE_RE.finditer(line)))
                if like_count > len(parsed):
                    warnings.append({
                        "outline_path": rel(path),
                        "line": line_number,
                        "reason": "存在锚样式开头，但成对引号解析数不足",
                        "anchor_like_count": like_count,
                        "parsed_count": len(parsed),
                        "line_text": line,
                    })
    return anchors, warnings


def deduplicate_anchors(anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, int, str], dict[str, Any]] = {}
    for anchor in anchors:
        key = (anchor["locator_kind"], anchor["locator_number"], anchor["quote"])
        if key not in unique:
            row = dict(anchor)
            row["occurrences"] = [{
                "outline_path": anchor["outline_path"],
                "line": anchor["line"],
                "column": anchor["column"],
                "section": anchor["section"],
                "object_type": anchor["object_type"],
            }]
            unique[key] = row
        else:
            unique[key]["occurrences"].append({
                "outline_path": anchor["outline_path"],
                "line": anchor["line"],
                "column": anchor["column"],
                "section": anchor["section"],
                "object_type": anchor["object_type"],
            })
    result = list(unique.values())
    for row in result:
        row["occurrence_count"] = len(row["occurrences"])
    result.sort(key=lambda row: (
        0 if row["locator_kind"] == "sequence" else 1,
        row["locator_number"],
        row["outline_path"],
        row["line"],
        row["column"],
    ))
    return result


def load_manifest(split_root: Path, code: str) -> tuple[dict[str, Any], Path]:
    path = split_root / code / "_manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"manifest 读取失败：{path}：{exc}") from exc
    if data.get("code") != code:
        raise AuditError(f"manifest 编号不符：{path}")
    return data, path


def outline_files_from_manifest(split_root: Path, code: str, manifest: dict[str, Any]) -> list[Path]:
    pages = manifest.get("outline_pages")
    if not isinstance(pages, list) or not pages:
        raise AuditError(f"{code} manifest 缺 outline_pages")
    files: list[Path] = []
    for page in pages:
        filename = page.get("file") if isinstance(page, dict) else None
        if not filename:
            raise AuditError(f"{code} outline_pages 条目缺文件名")
        path = split_root / code / filename
        if not path.is_file():
            raise AuditError(f"{code} 大纲拆分页不存在：{path}")
        files.append(path)
    return files


def find_book_dir(books_root: Path, code: str) -> Path:
    matches = sorted(path for path in books_root.glob(f"{code}_*") if path.is_dir())
    if len(matches) != 1:
        raise AuditError(f"{code} 章节包目录应唯一，实得 {len(matches)}：{matches}")
    return matches[0]


def load_sources(book_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chapter_dir = book_dir / "chapters"
    if not chapter_dir.is_dir():
        raise AuditError(f"缺章节目录：{chapter_dir}")
    sources: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for path in sorted(chapter_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        sequence = source_sequence(path)
        logical = source_logical_chapter(path, text)
        row = {
            "path": path,
            "rel_path": rel(path),
            "sequence": sequence,
            "logical_chapter": logical,
            "non_story_source": is_non_story_source(path, text),
            "text": text,
            "chars": len(text),
            "sha256": sha256_text(text),
        }
        sources.append(row)
        if sequence is None:
            warnings.append({"source_path": rel(path), "reason": "文件名缺少可解析序号"})
        if logical is None and not row["non_story_source"]:
            warnings.append({"source_path": rel(path), "reason": "未识别逻辑章号"})
    if not sources:
        raise AuditError(f"章节目录为空：{chapter_dir}")
    return sources, warnings


def source_indexes(sources: list[dict[str, Any]]) -> tuple[dict[int, list[dict[str, Any]]], dict[int, list[dict[str, Any]]]]:
    by_sequence: dict[int, list[dict[str, Any]]] = defaultdict(list)
    by_chapter: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for source in sources:
        if source["sequence"] is not None:
            by_sequence[source["sequence"]].append(source)
        if source["logical_chapter"] is not None:
            by_chapter[source["logical_chapter"]].append(source)
    return dict(by_sequence), dict(by_chapter)


def resolve_candidates(
    anchor: dict[str, Any],
    by_sequence: dict[int, list[dict[str, Any]]],
    by_chapter: dict[int, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], str]:
    number = anchor["locator_number"]
    if anchor["locator_kind"] == "sequence":
        return by_sequence.get(number, []), "sequence"
    candidates = by_chapter.get(number, [])
    if candidates:
        return candidates, "logical_chapter"
    fallback = by_sequence.get(number, [])
    return fallback, "fallback_sequence" if fallback else "unresolved"


def exact_check(
    anchor: dict[str, Any],
    by_sequence: dict[int, list[dict[str, Any]]],
    by_chapter: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    candidates, resolution = resolve_candidates(anchor, by_sequence, by_chapter)
    result = {
        "resolution": resolution,
        "candidate_sources": [source["rel_path"] for source in candidates],
        "status": "source_missing" if not candidates else "no_exact_match",
        "matched_source": None,
        "match_offset": None,
        "non_story_source": False,
        "mechanical_valid": False,
    }
    for source in candidates:
        offset = source["text"].find(anchor["quote"])
        if offset < 0:
            continue
        non_story = bool(source["non_story_source"])
        result.update({
            "status": "exact_match_non_story" if non_story else "exact_match",
            "matched_source": source["rel_path"],
            "match_offset": offset,
            "non_story_source": non_story,
            "mechanical_valid": not non_story and anchor["length_gate"] == "pass",
        })
        return result
    return result


def evenly_spaced_indices(length: int, count: int) -> list[int]:
    if count >= length:
        return list(range(length))
    if count <= 1:
        return [length // 2]
    raw = [round(i * (length - 1) / (count - 1)) for i in range(count)]
    return list(dict.fromkeys(raw))


def spread_sample(anchors: list[dict[str, Any]], limit: int) -> set[int]:
    """按章序均匀取样，并尽量让每种对象类型至少出现一次。"""
    if len(anchors) <= limit:
        return set(range(len(anchors)))
    selected = set(evenly_spaced_indices(len(anchors), limit))
    all_types: dict[str, list[int]] = defaultdict(list)
    for index, anchor in enumerate(anchors):
        all_types[anchor["object_type"]].append(index)
    represented = Counter(anchors[index]["object_type"] for index in selected)
    for object_type in sorted(all_types):
        if represented[object_type] or len(selected) >= limit and all(represented[t] <= 1 for t in represented):
            continue
        candidate = all_types[object_type][len(all_types[object_type]) // 2]
        removable = [
            index for index in selected
            if represented[anchors[index]["object_type"]] > 1
        ]
        if not removable:
            break
        remove = min(removable, key=lambda index: abs(index - candidate))
        represented[anchors[remove]["object_type"]] -= 1
        selected.remove(remove)
        selected.add(candidate)
        represented[object_type] += 1
    return selected


def audit_book(
    code: str,
    *,
    mode: str,
    audit_all: bool,
    sample_size: int,
    split_root: Path,
    books_root: Path,
) -> dict[str, Any]:
    manifest, manifest_path = load_manifest(split_root, code)
    outline_files = outline_files_from_manifest(split_root, code, manifest)
    book_dir = find_book_dir(books_root, code)
    sources, source_warnings = load_sources(book_dir)
    occurrences, parse_warnings = parse_outline_files(outline_files)
    anchors = deduplicate_anchors(occurrences)
    by_sequence, by_chapter = source_indexes(sources)

    if mode == "preflight":
        selected: set[int] = set()
    elif audit_all:
        selected = set(range(len(anchors)))
    else:
        selected = spread_sample(anchors, sample_size)

    checked: list[dict[str, Any]] = []
    for index, anchor in enumerate(anchors):
        row = dict(anchor)
        row["anchor_id"] = f"{code}-E{index + 1:04d}"
        row["selected"] = index in selected
        if index in selected:
            row.update(exact_check(row, by_sequence, by_chapter))
        else:
            candidates, resolution = resolve_candidates(row, by_sequence, by_chapter)
            row.update({
                "resolution": resolution,
                "candidate_sources": [source["rel_path"] for source in candidates],
                "status": "preflight_only" if mode == "preflight" else "not_sampled",
                "matched_source": None,
                "match_offset": None,
                "non_story_source": False,
                "mechanical_valid": False,
            })
        checked.append(row)

    statuses = Counter(row["status"] for row in checked if row["selected"])
    selected_rows = [row for row in checked if row["selected"]]
    story_rows = [row for row in selected_rows if not row["non_story_source"]]
    valid_rows = [row for row in story_rows if row["mechanical_valid"]]
    exact_rows = [row for row in selected_rows if row["status"] in {"exact_match", "exact_match_non_story"}]
    result = {
        "code": code,
        "book": manifest.get("book"),
        "mode": mode,
        "audit_policy": "all_unique_anchors" if mode == "audit" and audit_all else (
            f"spread_{sample_size}_chapter_and_type" if mode == "audit" else "format_and_locator_preflight"
        ),
        "manifest_path": rel(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "outline_files": [{"path": rel(path), "sha256": sha256_file(path)} for path in outline_files],
        "book_dir": rel(book_dir),
        "source_file_count": len(sources),
        "source_files": [{
            "path": source["rel_path"],
            "sequence": source["sequence"],
            "logical_chapter": source["logical_chapter"],
            "non_story_source": source["non_story_source"],
            "chars": source["chars"],
            "sha256": source["sha256"],
        } for source in sources],
        "anchor_occurrence_count": len(occurrences),
        "unique_anchor_count": len(anchors),
        "duplicate_occurrence_count": len(occurrences) - len(anchors),
        "selected_count": len(selected_rows),
        "exact_match_count": len(exact_rows),
        "story_selected_count": len(story_rows),
        "mechanical_valid_count": len(valid_rows),
        "story_mechanical_valid_rate": (len(valid_rows) / len(story_rows)) if story_rows else None,
        "length_gate_fail_count": sum(row["length_gate"] == "fail" for row in selected_rows),
        "non_story_match_count": statuses["exact_match_non_story"],
        "status_counts": dict(sorted(statuses.items())),
        "locator_resolution_counts": dict(sorted(Counter(row["resolution"] for row in checked).items())),
        "object_type_counts": dict(sorted(Counter(row["object_type"] for row in anchors).items())),
        "parse_warnings": parse_warnings,
        "source_warnings": source_warnings,
        "anchors": checked,
    }
    return result


def combined_input_fingerprint(books: Iterable[dict[str, Any]]) -> str:
    rows: list[str] = []
    for book in books:
        rows.append(f"{book['manifest_path']}\t{book['manifest_sha256']}")
        rows.extend(f"{item['path']}\t{item['sha256']}" for item in book["outline_files"])
        rows.extend(f"{item['path']}\t{item['sha256']}" for item in book["source_files"])
    return sha256_text("\n".join(sorted(rows)))


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1%}"


def render_report(payload: dict[str, Any]) -> str:
    books = payload["books"]
    audited = [book for book in books if book["mode"] == "audit"]
    preflight = [book for book in books if book["mode"] == "preflight"]
    lines = [
        "# AA批续22本证据锚机械审计",
        "",
        f"> 生成时间：{payload['generated_at']}  ",
        "> 性质：零模型调用、只读核验；所有短引按原字符逐字查找，不做任何归一化。  ",
        "> 用途：仅内部结构研究。",
        "",
        "## 结论卡",
        "",
    ]
    if audited:
        selected = sum(book["selected_count"] for book in audited)
        exact = sum(book["exact_match_count"] for book in audited)
        valid = sum(book["mechanical_valid_count"] for book in audited)
        story = sum(book["story_selected_count"] for book in audited)
        lines.extend([
            f"- 已正式核验 {len(audited)} 本，共抽中/全检 {selected} 条唯一锚；逐字命中 {exact} 条。",
            f"- 排除非正文命中后，故事证据机械有效 {valid}/{story}（{pct(valid / story if story else None)}）。",
            "- “机械有效”同时要求：能定位到对应源文件、短引逐字命中、长度为10～25字、源文件是正文。",
        ])
    if preflight:
        lines.append(f"- 另有 {len(preflight)} 本只做格式、数量和源文件定位预演；未把预演当正式命中审计。")
    lines.extend([
        "",
        "## 逐本结果",
        "",
        "| 编号 | 书名 | 阶段 | 唯一锚 | 本轮核验 | 逐字命中 | 故事证据有效 | 长度越界 | 非正文命中 | 解析警告 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for book in books:
        lines.append(
            f"| {book['code']} | {book['book']} | {'正式审计' if book['mode'] == 'audit' else '预演'} | "
            f"{book['unique_anchor_count']} | {book['selected_count']} | {book['exact_match_count']} | "
            f"{book['mechanical_valid_count']}/{book['story_selected_count']} | {book['length_gate_fail_count']} | "
            f"{book['non_story_match_count']} | {len(book['parse_warnings']) + len(book['source_warnings'])} |"
        )

    failures = [
        (book, anchor)
        for book in audited
        for anchor in book["anchors"]
        if anchor["selected"] and not anchor["mechanical_valid"]
    ]
    lines.extend(["", "## 未过机械闸的明细", ""])
    if not failures:
        lines.append("本轮正式核验没有未过项。")
    else:
        lines.append("下面逐条列出，不自动修补、不替模型改锚。")
        lines.append("")
        for book, anchor in failures:
            source = anchor["matched_source"] or "；".join(anchor["candidate_sources"]) or "未找到源文件"
            reason_parts = []
            if anchor["status"] == "no_exact_match":
                reason_parts.append("短引逐字未命中")
            elif anchor["status"] == "source_missing":
                reason_parts.append("定位不到源文件")
            elif anchor["status"] == "exact_match_non_story":
                reason_parts.append("命中非正文")
            if anchor["length_gate"] == "fail":
                reason_parts.append(f"长度{anchor['quote_chars']}字")
            lines.append(
                f"- `{anchor['anchor_id']}` {book['code']} {anchor['locator_kind']} {anchor['locator_number']}："
                f"「{anchor['quote']}」；{'、'.join(reason_parts) or anchor['status']}；源：`{source}`；"
                f"大纲：`{anchor['outline_path']}:{anchor['line']}`"
            )

    lines.extend(["", "## 解析与源文件警告", ""])
    warning_count = 0
    for book in books:
        for warning in book["parse_warnings"]:
            warning_count += 1
            lines.append(
                f"- {book['code']} 大纲 `{warning['outline_path']}:{warning['line']}`：{warning['reason']}"
            )
        for warning in book["source_warnings"]:
            warning_count += 1
            lines.append(f"- {book['code']} 源 `{warning['source_path']}`：{warning['reason']}")
    if not warning_count:
        lines.append("无。")

    lines.extend([
        "",
        "## 口径与可复核信息",
        "",
        "- 统计单位是“同一本书内去重后的章/序号＋短引”；重复出现仍在机器明细保留出现位置，但不重复抬高样本数。",
        "- `第N章` 优先按源文件的真实章标题定位；`序NN` 按材料包文件序号定位。只有识别不到真实章号时才回退到文件序号，并在明细标出。",
        "- 标题含“上架感言、请假、单章、完本感言、作者的话、写在前面”的源文件单列为非正文。",
        "- 不改标点、不压空格、不替换省略号、不做繁简转换；逐字没命中就记失败。",
        f"- 审计器 SHA-256：`{payload['auditor_sha256']}`",
        f"- 输入合并指纹 SHA-256：`{payload['input_fingerprint_sha256']}`",
        "- 模型调用数：0；密钥读取数：0；outbox 写入：0。",
        "",
        "来源：Codex",
        "",
    ])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AA 批证据锚机械审计")
    parser.add_argument("--audit-codes", default="", help="正式审计编号，如 AA11-AA16")
    parser.add_argument("--preflight-codes", default="", help="只做格式/数量预演的编号")
    parser.add_argument("--all-anchor-codes", default="", help="正式审计中全检唯一锚的编号；其余均匀抽样")
    parser.add_argument("--sample-size", type=int, default=20, help="非全检书每本抽样数")
    parser.add_argument("--split-root", type=Path, default=DEFAULT_SPLIT_ROOT)
    parser.add_argument("--books-root", type=Path, default=DEFAULT_BOOKS_ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.sample_size < 1:
        raise AuditError("sample-size 必须大于 0")
    audit_codes = parse_codes(args.audit_codes)
    preflight_codes = parse_codes(args.preflight_codes)
    all_anchor_codes = set(parse_codes(args.all_anchor_codes))
    overlap = set(audit_codes) & set(preflight_codes)
    if overlap:
        raise AuditError(f"同一编号不能同时正式审计和预演：{sorted(overlap)}")
    if not audit_codes and not preflight_codes:
        raise AuditError("至少提供 audit-codes 或 preflight-codes")
    unknown_all = all_anchor_codes - set(audit_codes)
    if unknown_all:
        raise AuditError(f"all-anchor-codes 必须属于 audit-codes：{sorted(unknown_all)}")

    split_root = args.split_root.resolve()
    books_root = args.books_root.resolve()
    output_dir = args.output_dir.resolve()
    books: list[dict[str, Any]] = []
    for code in audit_codes:
        books.append(audit_book(
            code,
            mode="audit",
            audit_all=code in all_anchor_codes,
            sample_size=args.sample_size,
            split_root=split_root,
            books_root=books_root,
        ))
    for code in preflight_codes:
        books.append(audit_book(
            code,
            mode="preflight",
            audit_all=False,
            sample_size=args.sample_size,
            split_root=split_root,
            books_root=books_root,
        ))

    payload = {
        "schema_version": "aa-anchor-audit-v1",
        "generated_at": now_iso(),
        "auditor_path": rel(Path(__file__)),
        "auditor_sha256": sha256_file(Path(__file__)),
        "input_fingerprint_sha256": combined_input_fingerprint(books),
        "audit_codes": audit_codes,
        "preflight_codes": preflight_codes,
        "all_anchor_codes": sorted(all_anchor_codes),
        "sample_size": args.sample_size,
        "model_calls": 0,
        "secret_reads": 0,
        "outbox_writes": 0,
        "books": books,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "审计明细.json", payload)
    report = render_report(payload)
    write_text(output_dir / "审计报告.md", report)
    summary = {
        key: payload[key]
        for key in (
            "schema_version", "generated_at", "auditor_path", "auditor_sha256",
            "input_fingerprint_sha256", "audit_codes", "preflight_codes",
            "all_anchor_codes", "sample_size", "model_calls", "secret_reads", "outbox_writes",
        )
    }
    summary["books"] = [{
        key: book[key]
        for key in (
            "code", "book", "mode", "audit_policy", "source_file_count",
            "anchor_occurrence_count", "unique_anchor_count", "duplicate_occurrence_count",
            "selected_count", "exact_match_count", "story_selected_count",
            "mechanical_valid_count", "story_mechanical_valid_rate", "length_gate_fail_count",
            "non_story_match_count", "status_counts", "locator_resolution_counts",
        )
    } for book in books]
    write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError as exc:
        print(f"错误：{exc}")
        raise SystemExit(2) from exc
