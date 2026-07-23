"""中性事件提取后的局部覆盖诊断。

本模块只比较冻结证据目录和同章事件引用，不调用模型，也不把未引用片段
直接判成语义漏项。它输出两层账：全部连续空档，以及按确定性词面信号筛出的
复核候选。
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


ANCHOR_ID = re.compile(r"^E(?P<number>\d{4})$")

CUE_GROUPS: dict[str, tuple[str, ...]] = {
    "认知或推断": (
        "得知", "发现", "认出", "意识", "明白", "想到", "想起", "判断", "怀疑",
        "不会是", "难道", "似乎", "可能", "也许", "觉得", "确认", "原来", "意味着",
    ),
    "身份或识别特征": (
        "外貌", "特征", "发色", "瞳孔", "鼻梁", "嘴唇", "五官", "皱纹", "瞎了",
        "眼睛", "照片", "身份", "名字", "长袍", "软帽",
    ),
    "后续动作或承接": (
        "明天", "后天", "随后", "之后", "下次", "再去", "再次", "将会", "会在",
        "等待", "打算", "决定", "准备", "同意", "接受", "约定", "以后",
    ),
    "风险或规则": (
        "否则", "风险", "危险", "厄运", "失控", "恐惧", "惊悚", "再次降临",
        "不能", "不得", "必须", "有时", "可能",
    ),
    "家庭或现实义务": (
        "班森", "梅丽莎", "哥哥", "妹妹", "家人", "家庭", "负担", "维持生活",
        "学费", "回家", "亲人",
    ),
    "仪式或兑现动作": (
        "占卜", "塔罗", "仪式", "执行", "完成", "翻开", "愚者", "进入帐篷",
    ),
}


class CoverageDiagnosticError(ValueError):
    """诊断输入不完整或自相矛盾。"""


def nonspace(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def anchor_number(anchor_id: str) -> int:
    match = ANCHOR_ID.fullmatch(anchor_id)
    if match is None:
        raise CoverageDiagnosticError(f"证据编号非法：{anchor_id}")
    return int(match.group("number"))


def anchor_range(start: str, end: str) -> list[str]:
    first = anchor_number(start)
    last = anchor_number(end)
    if first > last:
        raise CoverageDiagnosticError(f"证据范围倒置：{start}..{end}")
    return [f"E{number:04d}" for number in range(first, last + 1)]


def collect_anchor_usage(events: list[dict[str, Any]]) -> dict[str, list[str]]:
    usage: dict[str, list[str]] = {}
    for event in events:
        event_id = event.get("event_id")
        if not isinstance(event_id, str):
            raise CoverageDiagnosticError("事件缺合法 event_id")
        anchors = event.get("anchors")
        if not isinstance(anchors, list):
            raise CoverageDiagnosticError(f"{event_id} anchors 不是数组")
        for anchor in anchors:
            anchor_id = anchor.get("anchor_id") if isinstance(anchor, dict) else None
            if not isinstance(anchor_id, str):
                raise CoverageDiagnosticError(f"{event_id} 含非法证据编号")
            anchor_number(anchor_id)
            usage.setdefault(anchor_id, []).append(event_id)
    return usage


def locate_catalog_spans(text: str, entries: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    """把按正文顺序生成的目录短引重新定位到原文。"""
    spans: dict[str, tuple[int, int]] = {}
    previous_start = 0
    previous_number = 0
    for entry in entries:
        anchor_id = entry.get("anchor_id")
        quote = entry.get("quote")
        if not isinstance(anchor_id, str) or not isinstance(quote, str) or not quote:
            raise CoverageDiagnosticError("证据目录条目形状非法")
        number = anchor_number(anchor_id)
        if number != previous_number + 1:
            raise CoverageDiagnosticError(f"证据目录编号不连续：{anchor_id}")
        start = text.find(quote, previous_start)
        if start < 0:
            raise CoverageDiagnosticError(f"证据短引无法回原文定位：{anchor_id}")
        spans[anchor_id] = (start, start + len(quote))
        previous_start = start
        previous_number = number
    return spans


def cue_hits(text: str) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for group, terms in CUE_GROUPS.items():
        matched = [term for term in terms if term in text]
        if matched:
            hits[group] = matched
    if "？" in text or "?" in text:
        hits["问句"] = ["？"]
    return hits


def boundary_hits(text: str) -> list[str]:
    marks = {
        "句号": "。",
        "问号": "？",
        "叹号": "！",
        "分号": "；",
        "引号": "“",
    }
    return [name for name, mark in marks.items() if mark in text]


def _preview(value: str, limit: int = 180) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _continuous_text(
    text: str,
    spans: dict[str, tuple[int, int]],
    anchor_ids: list[str],
) -> str:
    return text[spans[anchor_ids[0]][0] : spans[anchor_ids[-1]][1]]


def group_unreferenced_runs(
    *,
    chapter: int,
    text: str,
    entries: list[dict[str, Any]],
    usage: dict[str, list[str]],
) -> list[dict[str, Any]]:
    spans = locate_catalog_spans(text, entries)
    runs: list[list[str]] = []
    for entry in entries:
        anchor_id = str(entry["anchor_id"])
        if anchor_id in usage:
            continue
        if not runs or anchor_number(anchor_id) != anchor_number(runs[-1][-1]) + 1:
            runs.append([anchor_id])
        else:
            runs[-1].append(anchor_id)

    catalog_ids = [str(row["anchor_id"]) for row in entries]
    result: list[dict[str, Any]] = []
    for index, anchor_ids in enumerate(runs, 1):
        first_pos = catalog_ids.index(anchor_ids[0])
        last_pos = catalog_ids.index(anchor_ids[-1])
        fragment = _continuous_text(text, spans, anchor_ids)
        result.append(
            {
                "gap_id": f"GAP-C{chapter:04d}-{index:03d}",
                "chapter": chapter,
                "start_anchor_id": anchor_ids[0],
                "end_anchor_id": anchor_ids[-1],
                "anchor_count": len(anchor_ids),
                "anchor_ids": anchor_ids,
                "left_used_anchor_id": catalog_ids[first_pos - 1] if first_pos > 0 else None,
                "right_used_anchor_id": catalog_ids[last_pos + 1] if last_pos + 1 < len(catalog_ids) else None,
                "nonspace_chars": len(nonspace(fragment)),
                "text_sha256": hashlib.sha256(fragment.encode("utf-8")).hexdigest(),
                "preview": _preview(fragment),
                "status": "catalog_anchor_gap_review",
                "not_a_semantic_verdict": True,
                "boundary_note": "只表示连续证据目录窗未被同章事件锚引用，不等于已确认语义漏抽。",
            }
        )
    return result


def _split_cluster(first: int, last: int, *, maximum: int = 18) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    cursor = first
    while cursor <= last:
        end = min(last, cursor + maximum - 1)
        windows.append((cursor, end))
        if end == last:
            break
        cursor = end - 1
    return windows


def heuristic_candidates(
    *,
    chapter: int,
    text: str,
    entries: list[dict[str, Any]],
    usage: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """把全部空档压成带明确信号的局部候选，不声称候选一定是漏项。"""
    spans = locate_catalog_spans(text, entries)
    entry_map = {str(row["anchor_id"]): row for row in entries}
    gaps = group_unreferenced_runs(
        chapter=chapter,
        text=text,
        entries=entries,
        usage=usage,
    )
    candidates: list[dict[str, Any]] = []
    for gap in gaps:
        ids = gap["anchor_ids"]
        signal_positions = [
            index
            for index, anchor_id in enumerate(ids)
            if cue_hits(str(entry_map[anchor_id]["quote"]))
        ]
        if not signal_positions:
            continue
        clusters: list[list[int]] = []
        for position in signal_positions:
            if not clusters or position - clusters[-1][-1] > 3:
                clusters.append([position])
            else:
                clusters[-1].append(position)
        for cluster in clusters:
            first = max(0, cluster[0] - 1)
            last = min(len(ids) - 1, cluster[-1] + 1)
            for window_first, window_last in _split_cluster(first, last):
                window_ids = ids[window_first : window_last + 1]
                fragment = _continuous_text(text, spans, window_ids)
                hits = cue_hits(fragment)
                boundaries = boundary_hits(fragment)
                groups = [name for name in hits if name != "问句"]
                hit_total = sum(len(values) for values in hits.values())
                keep = bool(boundaries) and (
                    (len(groups) >= 2 and hit_total >= 2)
                    or ("问句" in hits and len(groups) >= 1)
                    or "身份或识别特征" in hits
                )
                if not keep:
                    continue
                candidates.append(
                    {
                        "candidate_id": "",
                        "chapter": chapter,
                        "source_gap_id": gap["gap_id"],
                        "start_anchor_id": window_ids[0],
                        "end_anchor_id": window_ids[-1],
                        "anchor_count": len(window_ids),
                        "anchor_ids": window_ids,
                        "used_by_event_ids": [],
                        "cue_hits": hits,
                        "boundary_hits": boundaries,
                        "signal_score": len(groups) * 2 + (1 if "问句" in hits else 0),
                        "nonspace_chars": len(nonspace(fragment)),
                        "continuous_text": fragment,
                        "text_sha256": hashlib.sha256(fragment.encode("utf-8")).hexdigest(),
                        "status": "candidate_review",
                        "not_a_semantic_verdict": True,
                        "known_target_ids": [],
                    }
                )
    candidates.sort(
        key=lambda row: (
            row["chapter"],
            anchor_number(row["start_anchor_id"]),
            anchor_number(row["end_anchor_id"]),
        )
    )
    for index, row in enumerate(candidates, 1):
        row["candidate_id"] = f"COV-C{chapter:04d}-{index:03d}"
    return candidates


def catalog_coverage_candidates(
    *,
    chapter: int,
    entries: list[dict[str, Any]],
    maximum: int = 18,
) -> list[dict[str, Any]]:
    """把冻结目录切成全覆盖候选段，供程序点名器使用。"""

    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise CoverageDiagnosticError("候选段最大锚数必须是正整数")
    anchor_ids = [str(row.get("anchor_id") or "") for row in entries]
    if not anchor_ids:
        raise CoverageDiagnosticError(f"第 {chapter} 章冻结证据目录为空")
    for expected, anchor_id in enumerate(anchor_ids, 1):
        if anchor_number(anchor_id) != expected:
            raise CoverageDiagnosticError(
                f"第 {chapter} 章冻结证据目录编号不连续：{anchor_id}"
            )

    candidates: list[dict[str, Any]] = []
    for offset in range(0, len(anchor_ids), maximum):
        selected = anchor_ids[offset : offset + maximum]
        candidates.append(
            {
                "candidate_id": f"COV-C{chapter:04d}-{len(candidates) + 1:03d}",
                "chapter": chapter,
                "start_anchor_id": selected[0],
                "end_anchor_id": selected[-1],
                "anchor_count": len(selected),
                "anchor_ids": selected,
                "status": "catalog_coverage_candidate",
                "not_a_semantic_verdict": True,
            }
        )
    audit_catalog_candidate_coverage(
        chapter=chapter,
        entries=entries,
        candidates=candidates,
    )
    return candidates


def audit_catalog_candidate_coverage(
    *,
    chapter: int,
    entries: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """硬验候选段并集覆盖冻结目录；允许段间重叠，但不准漏锚或越界。"""

    catalog_ids = [str(row.get("anchor_id") or "") for row in entries]
    catalog_set = set(catalog_ids)
    if len(catalog_ids) != len(catalog_set):
        raise CoverageDiagnosticError(f"第 {chapter} 章冻结证据目录含重复编号")
    covered: set[str] = set()
    for row in candidates:
        candidate_id = str(row.get("candidate_id") or "")
        ids = row.get("anchor_ids")
        if not candidate_id or not isinstance(ids, list) or not ids:
            raise CoverageDiagnosticError(f"第 {chapter} 章候选段形状非法：{candidate_id}")
        clean_ids = [str(value) for value in ids]
        numbers = [anchor_number(value) for value in clean_ids]
        if numbers != list(range(numbers[0], numbers[-1] + 1)):
            raise CoverageDiagnosticError(f"候选段 {candidate_id} 的证据编号不连续")
        if row.get("start_anchor_id") != clean_ids[0] or row.get("end_anchor_id") != clean_ids[-1]:
            raise CoverageDiagnosticError(f"候选段 {candidate_id} 的起止编号与列表不一致")
        outside = sorted(set(clean_ids) - catalog_set)
        if outside:
            raise CoverageDiagnosticError(f"候选段 {candidate_id} 含目录外证据：{outside}")
        covered.update(clean_ids)
    missing = [anchor_id for anchor_id in catalog_ids if anchor_id not in covered]
    if missing:
        raise CoverageDiagnosticError(
            f"第 {chapter} 章候选段未全覆盖冻结目录：{missing}"
        )
    return {
        "chapter": chapter,
        "status": "pass",
        "catalog_anchor_total": len(catalog_ids),
        "candidate_total": len(candidates),
        "covered_unique_anchor_total": len(covered),
        "missing_anchor_ids": [],
        "outside_catalog_anchor_ids": [],
        "overlap_allowed": True,
    }


def evaluate_known_targets(
    *,
    target_config: dict[str, Any],
    catalogs: dict[int, list[dict[str, Any]]],
    events_by_chapter: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    def span_result(span: dict[str, Any]) -> dict[str, Any]:
        span_chapter = int(span["chapter"])
        span_catalog = {
            str(row["anchor_id"]): str(row["quote"])
            for row in catalogs[span_chapter]
        }
        span_usage = collect_anchor_usage(events_by_chapter[span_chapter])
        span_ids = anchor_range(str(span["start_anchor_id"]), str(span["end_anchor_id"]))
        span_missing = [anchor_id for anchor_id in span_ids if anchor_id not in span_catalog]
        span_referenced = [anchor_id for anchor_id in span_ids if anchor_id in span_usage]
        span_unreferenced = [anchor_id for anchor_id in span_ids if anchor_id not in span_usage]
        if span_missing:
            span_status = "target_anchor_missing_from_catalog"
        elif not span_referenced:
            span_status = "anchor_span_unreferenced"
        elif not span_unreferenced:
            span_status = "anchor_span_fully_referenced"
        else:
            span_status = "anchor_span_partially_referenced"
        quote_fragments = [str(value) for value in span.get("required_quote_fragments", [])]
        joined = "\n".join(span_catalog.get(anchor_id, "") for anchor_id in span_ids)
        return {
            "chapter": span_chapter,
            "start_anchor_id": span_ids[0],
            "end_anchor_id": span_ids[-1],
            "anchor_count": len(span_ids),
            "role": span.get("role", ""),
            "status": span_status,
            "missing_from_catalog": span_missing,
            "referenced_anchor_ids": span_referenced,
            "unreferenced_anchor_ids": span_unreferenced,
            "referenced_by_events": {
                anchor_id: span_usage[anchor_id] for anchor_id in span_referenced
            },
            "required_quote_checks": {
                quote: quote in joined for quote in quote_fragments
            },
        }

    results: list[dict[str, Any]] = []
    for target in target_config.get("targets", []):
        chapter = int(target["chapter"])
        entries = catalogs[chapter]
        catalog_map = {str(row["anchor_id"]): str(row["quote"]) for row in entries}
        usage = collect_anchor_usage(events_by_chapter[chapter])
        ids = anchor_range(str(target["start_anchor_id"]), str(target["end_anchor_id"]))
        missing_from_catalog = [anchor_id for anchor_id in ids if anchor_id not in catalog_map]
        referenced = [anchor_id for anchor_id in ids if anchor_id in usage]
        unreferenced = [anchor_id for anchor_id in ids if anchor_id not in usage]
        if missing_from_catalog:
            status = "target_anchor_missing_from_catalog"
        elif not referenced:
            status = "anchor_span_unreferenced"
        elif not unreferenced:
            status = "anchor_span_fully_referenced"
        else:
            status = "anchor_span_partially_referenced"
        expected = target.get("expected_anchor_status")
        if expected is not None and status != expected:
            raise CoverageDiagnosticError(
                f"已知靶 {target['id']} 状态漂移：expected={expected}, actual={status}"
            )
        terms = [str(value) for value in target.get("semantic_terms", [])]
        semantic_event_hits = []
        for event in events_by_chapter[chapter]:
            summary = str(event.get("event", ""))
            matched = [term for term in terms if term in summary]
            if matched:
                semantic_event_hits.append({"event_id": event["event_id"], "matched_terms": matched})
        linked_events = []
        for link in target.get("linked_events", []):
            linked_chapter = int(link["chapter"])
            event_map = {
                str(row["event_id"]): row for row in events_by_chapter[linked_chapter]
            }
            linked_event = event_map.get(str(link["event_id"]))
            expected_anchor_ids = [str(value) for value in link.get("expected_anchor_ids", [])]
            actual_anchor_ids = [
                str(anchor.get("anchor_id"))
                for anchor in (linked_event or {}).get("anchors", [])
                if isinstance(anchor, dict) and isinstance(anchor.get("anchor_id"), str)
            ]
            summary = str((linked_event or {}).get("event", ""))
            required_summary_fragments = [
                str(value) for value in link.get("required_summary_fragments", [])
            ]
            linked_events.append(
                {
                    **link,
                    "present": linked_event is not None,
                    "actual_anchor_ids": actual_anchor_ids,
                    "expected_anchor_ids_match": (
                        not expected_anchor_ids or actual_anchor_ids == expected_anchor_ids
                    ),
                    "summary_fragment_checks": {
                        fragment: fragment in summary for fragment in required_summary_fragments
                    },
                }
            )
        required_quotes = [str(value) for value in target.get("required_quote_fragments", [])]
        target_text = "\n".join(catalog_map.get(anchor_id, "") for anchor_id in ids)
        results.append(
            {
                "id": target["id"],
                "label": target["label"],
                "chapter": chapter,
                "start_anchor_id": ids[0],
                "end_anchor_id": ids[-1],
                "anchor_count": len(ids),
                "status": status,
                "missing_from_catalog": missing_from_catalog,
                "referenced_anchor_ids": referenced,
                "unreferenced_anchor_ids": unreferenced,
                "referenced_by_events": {
                    anchor_id: usage[anchor_id] for anchor_id in referenced
                },
                "required_quote_checks": {
                    quote: quote in target_text for quote in required_quotes
                },
                "event_summary_term_hits": semantic_event_hits,
                "linked_events": linked_events,
                "related_spans": [span_result(span) for span in target.get("related_spans", [])],
                "interpretation_boundary": target.get("interpretation_boundary", ""),
                "t4_regression_target": bool(target.get("t4_regression_target", True)),
            }
        )
    return results


def scan_book(
    *,
    book_dir: Path,
    extract_dir: Path,
    target_config: dict[str, Any],
    chapter_start: int,
    chapter_end: int,
) -> dict[str, Any]:
    catalogs: dict[int, list[dict[str, Any]]] = {}
    events_by_chapter: dict[int, list[dict[str, Any]]] = {}
    chapter_texts: dict[int, str] = {}
    chapter_rows: list[dict[str, Any]] = []
    all_gaps: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []
    all_catalog_candidates: list[dict[str, Any]] = []
    candidate_coverage_audits: list[dict[str, Any]] = []

    for chapter in range(chapter_start, chapter_end + 1):
        chapter_files = sorted((book_dir / "chapters").glob(f"{chapter:04d}_*.txt"))
        if len(chapter_files) != 1:
            raise CoverageDiagnosticError(
                f"第 {chapter} 章正文应有且仅有一个文件，实际 {len(chapter_files)} 个"
            )
        text = chapter_files[0].read_text(encoding="utf-8").strip()
        catalog_doc = _read_json(extract_dir / "evidence_catalogs" / f"ch{chapter:04d}.json")
        event_doc = _read_json(extract_dir / "events" / f"ch{chapter:04d}.json")
        entries = catalog_doc.get("entries")
        events = event_doc.get("events")
        if not isinstance(entries, list) or not isinstance(events, list):
            raise CoverageDiagnosticError(f"第 {chapter} 章目录或事件结构非法")
        if catalog_doc.get("chapter") != chapter or event_doc.get("chapter") != chapter:
            raise CoverageDiagnosticError(f"第 {chapter} 章工件章号不一致")
        if catalog_doc.get("coverage") != 1.0:
            raise CoverageDiagnosticError(f"第 {chapter} 章证据目录覆盖率不是 1.0")
        catalogs[chapter] = entries
        events_by_chapter[chapter] = events
        chapter_texts[chapter] = text
        usage = collect_anchor_usage(events)
        catalog_ids = {str(row["anchor_id"]) for row in entries}
        outside = sorted(set(usage) - catalog_ids)
        if outside:
            raise CoverageDiagnosticError(f"第 {chapter} 章事件引用目录外证据：{outside}")
        gaps = group_unreferenced_runs(
            chapter=chapter,
            text=text,
            entries=entries,
            usage=usage,
        )
        candidates = heuristic_candidates(
            chapter=chapter,
            text=text,
            entries=entries,
            usage=usage,
        )
        full_coverage_candidates = catalog_coverage_candidates(
            chapter=chapter,
            entries=entries,
        )
        coverage_audit = audit_catalog_candidate_coverage(
            chapter=chapter,
            entries=entries,
            candidates=full_coverage_candidates,
        )
        all_gaps.extend(gaps)
        all_candidates.extend(candidates)
        all_catalog_candidates.extend(full_coverage_candidates)
        candidate_coverage_audits.append(coverage_audit)
        chapter_rows.append(
            {
                "chapter": chapter,
                "catalog_anchor_total": len(entries),
                "event_total": len(events),
                "anchor_reference_total": sum(len(row.get("anchors", [])) for row in events),
                "used_unique_anchor_total": len(usage),
                "unreferenced_anchor_total": len(entries) - len(usage),
                "raw_gap_run_total": len(gaps),
                "heuristic_candidate_total": len(candidates),
                "catalog_coverage_candidate_total": len(full_coverage_candidates),
                "catalog_candidate_coverage_status": coverage_audit["status"],
            }
        )

    known_targets = evaluate_known_targets(
        target_config=target_config,
        catalogs=catalogs,
        events_by_chapter=events_by_chapter,
    )
    candidate_index = {
        chapter: [row for row in all_candidates if row["chapter"] == chapter]
        for chapter in range(chapter_start, chapter_end + 1)
    }
    for target in known_targets:
        start = anchor_number(target["start_anchor_id"])
        end = anchor_number(target["end_anchor_id"])
        overlapping = [
            row
            for row in candidate_index[target["chapter"]]
            if anchor_number(row["start_anchor_id"]) <= end
            and anchor_number(row["end_anchor_id"]) >= start
        ]
        target["overlapping_heuristic_candidate_ids"] = [
            row["candidate_id"] for row in overlapping
        ]
        for row in overlapping:
            row["known_target_ids"].append(target["id"])

    return {
        "schema_version": "z-extraction-coverage-diagnostic-v3",
        "scope": {
            "chapter_start": chapter_start,
            "chapter_end": chapter_end,
            "model_calls": 0,
            "semantic_claim": "未引用片段只进候选池，不自动判为真实漏项",
            "known_limit": "只看证据编号引用和词面信号；锚已被引用但目标语义只在宽锚中顺带出现的情况，仍需人工回原文判断",
            "candidate_overlap_note": "候选局部窗为保留上下文允许少量重叠；候选数不是互不相交的语义漏项数",
            "program_naming_contract": "程序点名器只读取全覆盖候选段；每个冻结目录锚必须归属至少一个候选段，段间重叠允许。",
        },
        "metrics": {
            "chapter_total": len(chapter_rows),
            "catalog_anchor_total": sum(row["catalog_anchor_total"] for row in chapter_rows),
            "event_total": sum(row["event_total"] for row in chapter_rows),
            "anchor_reference_total": sum(row["anchor_reference_total"] for row in chapter_rows),
            "used_unique_anchor_total": sum(row["used_unique_anchor_total"] for row in chapter_rows),
            "unreferenced_anchor_total": sum(row["unreferenced_anchor_total"] for row in chapter_rows),
            "raw_gap_run_total": len(all_gaps),
            "heuristic_candidate_total": len(all_candidates),
            "catalog_coverage_candidate_total": len(all_catalog_candidates),
            "catalog_candidate_coverage_passes": sum(
                row["status"] == "pass" for row in candidate_coverage_audits
            ),
            "known_target_total": len(known_targets),
            "known_target_unreferenced_total": sum(
                row["status"] == "anchor_span_unreferenced" for row in known_targets
            ),
        },
        "chapters": chapter_rows,
        "known_targets": known_targets,
        "heuristic_candidates": all_candidates,
        "catalog_coverage_candidates": all_catalog_candidates,
        "candidate_coverage_audits": candidate_coverage_audits,
        "raw_gap_runs": all_gaps,
    }


def _read_json(path: Path) -> dict[str, Any]:
    import json

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CoverageDiagnosticError(f"缺诊断输入：{path}") from error
    if not isinstance(value, dict):
        raise CoverageDiagnosticError(f"JSON 顶层不是对象：{path}")
    return value
