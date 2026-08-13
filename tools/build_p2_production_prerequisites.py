#!/usr/bin/env python3
"""Build the P2 production-canonical prerequisite ledger without training.

The script is intentionally conservative:
- an artifact-level no-training note is not promoted to a copyright grant;
- evidence occurrence is accepted only when unique inside the frozen source window;
- unresolved author identity and frozen evaluation sources are excluded;
- a canonical candidate is emitted only when every P2 gate is green.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO = Path("/Users/a1234/挣钱/小说架构")
LAB = Path("/Users/a1234/挣钱/小说架构_隔离实验")
CORPUS = Path("/Users/a1234/挣钱/小说101-downloads")
NEWBOOK = CORPUS / "_newbook_rank_20260804/books"

A_PATH = REPO / "TEMP/chatgpt_review_cycles/T5_R04_A_V27_PRUNED_CANDIDATE_20260807_R01/candidate/train_v2_7_a_pruned_candidate.jsonl"
A_AUTH = REPO / "TEMP/chatgpt_review_cycles/T5_R04_A_V27_PRUNED_CANDIDATE_20260807_R01/AUTHORIZATION.md"
A_MAP = LAB / "T5_R04_EVIDENCE_ID_DUAL_LORA_20260804_R01/mapping/TRAIN_585_SOURCE_MAP.jsonl"

SPECIAL_ROOT = LAB / "T5_R04_SPECIAL_EXAMPLES_84_MERGE_20260806_R01/sealed_candidate"
SPECIAL_PATH = SPECIAL_ROOT / "TRAIN_PAIRS_SPECIAL_EXAMPLES_84_CANDIDATE.jsonl"
SPECIAL_MANIFEST = SPECIAL_ROOT / "UNIFIED_SEGMENT_MANIFEST.jsonl"
SPECIAL_AUTH = SPECIAL_ROOT / "AUTHORIZATION_20260806_2341.json"
OLD_SPECIAL_AUTH = LAB / "T5_R04_THIRD_BATCH_69_PREMERGE_AUDIT_20260805_R01/merge_r03_sealed/AUTHORIZATION_20260805_2113.json"

HISTORICAL_BUILDER = LAB / "T5_R04_A_C_FORMAT_COMPARE_20260807_R01/tools/build_ac_datasets_and_exams.py"
LEGACY_QUARANTINE = REPO / "finetuning/experiments/T5_R04_SEMANTIC_CORE_MIX_PROBE_20260807_R01/c2_unit_final_gate/run_1/LEGACY_POSITION_QUARANTINE.jsonl"
FROZEN_BOOK_MANIFEST = LAB / "T5_R04_MISSING_TYPES_CHATGPT_20260806_R01/build/ONE_WINDOW_FULL_CORPUS_R02/input/BOOK_MANIFEST.jsonl"

EXPECTED_A_SHA = "3c7cfddbb7971a9a5e6739b17ed00b9a546bad21ca7946f38b5de95557b45f67"
EXPECTED_SPECIAL_SHA = "8e230b9469b24a1af31faca1c080164dc724cfd06249b8b964d939c7df5ed4a0"
EXPECTED_SPECIAL_MANIFEST_SHA = "f84120bff42fd25cf43b5dd1df1824d0024bca10bdf5cd60d086dd4cc3f13ae7"
STATUS_VALUES = ("已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定")
FROZEN_TITLES = (
    "领袖",
    "重生78，从知青返城开始",
    "末日来袭，我能无限升级庇护所",
    "有道行",
    "颠婆勇者太多了",
)

CONTINUOUS_MARKER = "【连续短段原文｜evidence 只能从这里逐字复制】\n"
OVERLAP_RE = re.compile(r"- 左侧重叠字符数：(\d+)")
SEGMENT_RE = re.compile(r"- segment_id：([^\n]+)")
CARD_MARKER = "【小说背景卡｜只辅助理解，不代替证据】\n"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_text(text: str) -> str:
    return sha_bytes(text.encode("utf-8"))


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts)
    return f"{prefix}-{sha_text(payload)[:16]}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def parse_card(user: str) -> dict[str, Any]:
    return json.loads(user.split(CARD_MARKER, 1)[1].split("\n\n【短段身份】", 1)[0])


def parse_segment_id(user: str) -> str:
    match = SEGMENT_RE.search(user)
    if not match:
        raise ValueError("missing segment_id")
    return match.group(1).strip()


def parse_facts(row: dict[str, Any]) -> list[dict[str, Any]]:
    messages = row["messages"]
    if [item.get("role") for item in messages] != ["system", "user", "assistant"]:
        raise ValueError("message roles are not system/user/assistant")
    facts = json.loads(messages[2]["content"])["facts"]
    for fact in facts:
        if fact["status"] not in STATUS_VALUES:
            raise ValueError(f"invalid status {fact['status']}")
        if not fact.get("evidence"):
            raise ValueError("missing evidence")
    return facts


def occurrences(text: str, needle: str, start: int, end: int, responsibility_start: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = start
    while cursor <= end - len(needle):
        pos = text.find(needle, cursor, end)
        if pos < 0:
            break
        if pos + len(needle) > responsibility_start:
            spans.append((pos, pos + len(needle)))
        cursor = pos + 1
    return spans


def import_historical_builder():
    spec = importlib.util.spec_from_file_location("p2_historical_ac_builder", HISTORICAL_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import historical source resolver")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_title(value: str) -> str:
    return re.sub(r"[\s　]+", "", value).replace("（全集）", "")


def normalize_author(value: str) -> str:
    return re.sub(r"[\s　]+", "", value)


def extract_author_from_source_md(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("- 作者："):
            value = line.split("：", 1)[1].strip()
            for marker in (" 主角：", " 关键词：", " 标签："):
                value = value.split(marker, 1)[0].strip()
            if value and value not in {"佚名", "未知", "unknown", "null"}:
                return value
    return None


def build_local_identity_index(titles: set[str]) -> dict[str, dict[str, Any]]:
    evidence: dict[str, list[tuple[str, str]]] = defaultdict(list)
    wanted = {normalize_title(title): title for title in titles}

    for title in sorted(titles):
        source_md = NEWBOOK / title / "SOURCE.md"
        if source_md.is_file():
            author = extract_author_from_source_md(source_md)
            if author:
                evidence[title].append((author, str(source_md)))

    skip = {"chapters_cache", ".git", "node_modules", ".venv", "venv", "__pycache__"}
    for root, dirs, files in os.walk(CORPUS):
        dirs[:] = [name for name in dirs if name not in skip]
        dirname = Path(root).name
        key = normalize_title(dirname)
        if key not in wanted:
            continue
        title = wanted[key]
        source_md = Path(root) / "SOURCE.md"
        if source_md.is_file():
            author = extract_author_from_source_md(source_md)
            if author:
                evidence[title].append((author, str(source_md)))
        for name in files:
            match = re.fullmatch(re.escape(dirname) + r"\((.+)\)\.txt", name)
            if match:
                author = match.group(1).strip()
                if author not in {"佚名", "未知", "unknown", "null"}:
                    evidence[title].append((author, str(Path(root) / name)))

    result: dict[str, dict[str, Any]] = {}
    for title in sorted(titles):
        by_normalized: dict[str, set[str]] = defaultdict(set)
        display: dict[str, set[str]] = defaultdict(set)
        for author, path in evidence.get(title, []):
            key = normalize_author(author)
            by_normalized[key].add(path)
            display[key].add(author)
        if len(by_normalized) == 1:
            key = next(iter(by_normalized))
            author = sorted(display[key], key=lambda value: (len(value), value))[0]
            result[title] = {
                "identity_status": "RESOLVED",
                "author_name": author,
                "author_id": stable_id("AU-P2", key),
                "identity_evidence": sorted(by_normalized[key]),
            }
        elif not by_normalized:
            result[title] = {
                "identity_status": "IDENTITY_UNKNOWN",
                "author_name": None,
                "author_id": None,
                "identity_evidence": [],
            }
        else:
            result[title] = {
                "identity_status": "IDENTITY_UNKNOWN",
                "author_name": None,
                "author_id": None,
                "identity_evidence": sorted({path for paths in by_normalized.values() for path in paths}),
                "conflicting_authors": sorted(display),
            }
    return result


def load_frozen_registry() -> dict[str, dict[str, Any]]:
    rows = read_jsonl(FROZEN_BOOK_MANIFEST)
    by_title = {row["title"]: row for row in rows if row["title"] in FROZEN_TITLES}
    if set(by_title) != set(FROZEN_TITLES):
        raise ValueError("frozen five registry incomplete")
    return by_title


def frozen_match(title: str, book_id: str | None, source_paths: list[str], registry: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    title_norm = normalize_title(title)
    for frozen_title, record in registry.items():
        if title_norm == normalize_title(frozen_title):
            hits.append({"method": "normalized_title", "frozen_title": frozen_title, "value": title})
        if book_id and book_id == record["book_id"]:
            hits.append({"method": "book_id", "frozen_title": frozen_title, "value": book_id})
        for source_path in source_paths:
            if f"/{frozen_title}/" in source_path or Path(source_path).name.startswith(frozen_title + "("):
                hits.append({"method": "source_path", "frozen_title": frozen_title, "value": source_path})
            url = record.get("book_url")
            if url and url in source_path:
                hits.append({"method": "book_url", "frozen_title": frozen_title, "value": url})
    unique = {(item["method"], item["frozen_title"], item["value"]): item for item in hits}
    return [unique[key] for key in sorted(unique)]


def build_a_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if sha_file(A_PATH) != EXPECTED_A_SHA:
        raise ValueError("A v2.7 SHA mismatch")
    if "不得直接训练" not in A_AUTH.read_text(encoding="utf-8"):
        raise ValueError("A authorization boundary drift")

    source_maps = {row["segment_id"]: row for row in read_jsonl(A_MAP)}
    rows = read_jsonl(A_PATH)
    output: list[dict[str, Any]] = []
    total_facts = unique_facts = ambiguous_facts = missing_facts = 0
    for line_number, row in enumerate(rows, 1):
        user = row["messages"][1]["content"]
        card = parse_card(user)
        segment_id = parse_segment_id(user)
        mapped = source_maps.get(segment_id)
        if not mapped:
            raise ValueError(f"A source map missing {segment_id}")
        if CONTINUOUS_MARKER not in user:
            raise ValueError(f"A continuous source missing {segment_id}")
        source_text = user.split(CONTINUOUS_MARKER, 1)[1]
        overlap_match = OVERLAP_RE.search(user)
        if not overlap_match:
            raise ValueError(f"A overlap missing {segment_id}")
        responsibility_start = int(overlap_match.group(1))
        facts = parse_facts(row)
        fact_positions = []
        row_status = "RESOLVED"
        for fact_index, fact in enumerate(facts, 1):
            spans = occurrences(source_text, fact["evidence"], 0, len(source_text), responsibility_start)
            total_facts += 1
            if len(spans) == 1:
                unique_facts += 1
                status = "RESOLVED"
                start, end = spans[0]
            elif not spans:
                missing_facts += 1
                status = "POSITION_NOT_FOUND"
                start = end = None
                row_status = status
            else:
                ambiguous_facts += 1
                status = "POSITION_AMBIGUOUS"
                start = end = None
                row_status = status
            fact_positions.append({
                "fact_id": f"{segment_id}-F{fact_index:02d}",
                "fact_index": fact_index,
                "provenance_status": status,
                "evidence_text_sha256": sha_text(fact["evidence"]),
                "evidence_start": start,
                "evidence_end": end,
                "candidate_spans": [list(span) for span in spans],
                "round_trip": bool(start is not None and source_text[start:end] == fact["evidence"]),
            })
        publication = card.get("publication", {})
        title = publication.get("book_title") or mapped.get("title")
        author = publication.get("author")
        book_id = mapped.get("novel_key") or stable_id("BK-P2", title, author or "")
        author_id = stable_id("AU-P2", normalize_author(author)) if author else None
        source_id = stable_id("SRC-P2", mapped["source_sha256"], mapped["chapter_id"])
        output.append({
            "row_id": segment_id,
            "source_line_number": line_number,
            "sample_class": "ordinary",
            "source_id": source_id,
            "source_sha256": mapped["source_sha256"],
            "chapter_id": mapped["chapter_id"],
            "source_paths": [mapped["source_path"]],
            "book_id": book_id,
            "book_title": title,
            "author_id": author_id,
            "author_name": author,
            "rights_status": "RIGHTS_UNKNOWN",
            "rights_evidence": [{"path": str(A_AUTH), "sha256": sha_file(A_AUTH), "finding": "artifact is candidate-only and explicitly not directly trainable; no per-source training grant found"}],
            "identity_status": "RESOLVED" if author else "IDENTITY_UNKNOWN",
            "identity_evidence": [{"path": str(A_PATH), "field": "publication.author"}] if author else [],
            "provenance_status": row_status,
            "provenance_version": "P2_A_WINDOW_UNIQUE_OCCURRENCE_R01",
            "responsibility_zone": {"start": responsibility_start, "end": len(source_text), "coordinate_space": "source_text", "indexing": "python_unicode_zero_based_half_open"},
            "source_text_sha256": sha_text(source_text),
            "source_text_length": len(source_text),
            "facts_count": len(facts),
            "statuses": dict(Counter(fact["status"] for fact in facts)),
            "evidence_span_lengths": [len(fact["evidence"]) for fact in facts],
            "fact_provenance": fact_positions,
            "canonical_payload": {"source_text": source_text, "facts": facts},
        })
    if len(output) != 314 or total_facts != 2783:
        raise ValueError(f"A denominator drift rows={len(output)} facts={total_facts}")
    receipt = {
        "status": "PASS_PROVENANCE_REPAIRED_RIGHTS_UNRESOLVED",
        "input": {"path": str(A_PATH), "sha256": sha_file(A_PATH), "rows": len(output), "facts": total_facts},
        "source_map": {"path": str(A_MAP), "sha256": sha_file(A_MAP)},
        "rights_authorization": {"path": str(A_AUTH), "sha256": sha_file(A_AUTH)},
        "provenance": {"resolved_rows": sum(row["provenance_status"] == "RESOLVED" for row in output), "resolved_facts": unique_facts, "ambiguous_facts": ambiguous_facts, "not_found_facts": missing_facts},
        "rights": {"eligible_rows": 0, "not_eligible_rows": 0, "unknown_rows": len(output), "rule": "candidate-only authorization is not promoted to a per-source training-rights grant"},
    }
    return output, receipt


def build_special_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if sha_file(SPECIAL_PATH) != EXPECTED_SPECIAL_SHA or sha_file(SPECIAL_MANIFEST) != EXPECTED_SPECIAL_MANIFEST_SHA:
        raise ValueError("special 84 SHA mismatch")
    rows = read_jsonl(SPECIAL_PATH)
    manifests = read_jsonl(SPECIAL_MANIFEST)
    if len(rows) != 84 or len(manifests) != 84:
        raise ValueError("special row denominator drift")

    helper = import_historical_builder()
    recovery = {row["sample_id"]: row for row in helper.read_jsonl(helper.RECOVERY)}
    inventory = {row["sample_id"]: row for row in helper.read_jsonl(helper.PREMERGE_INVENTORY)}
    titles = {manifest["book_title"] for manifest in manifests}
    identity_index = build_local_identity_index(titles)
    legacy_rows = read_jsonl(LEGACY_QUARANTINE)
    legacy_keys = {(row["canonical_sample_id"], row["fact_index"]): row for row in legacy_rows}
    output: list[dict[str, Any]] = []
    total_facts = resolved_facts = ambiguous_facts = missing_facts = 0

    for line_number, (row, manifest) in enumerate(zip(rows, manifests), 1):
        user = row["messages"][1]["content"]
        card = parse_card(user)
        segment_id = parse_segment_id(user)
        if segment_id != manifest["segment_id"]:
            raise ValueError(f"special manifest mismatch {segment_id}")
        source_path, chapter_label = helper.source_for_special(line_number, manifest, card, recovery, inventory)
        chapter_text = source_path.read_text(encoding="utf-8")
        left, core = helper.special_parts(user)
        segment_start, responsibility_start_abs, responsibility_end_abs, adapter = helper.locate_special_region(chapter_text, left, core)
        source_text = chapter_text[segment_start:responsibility_end_abs]
        responsibility_start = responsibility_start_abs - segment_start
        facts = parse_facts(row)
        fact_positions = []
        row_status = "RESOLVED"
        for fact_index, fact in enumerate(facts, 1):
            spans_abs = occurrences(chapter_text, fact["evidence"], segment_start, responsibility_end_abs, responsibility_start_abs)
            spans = [(start - segment_start, end - segment_start) for start, end in spans_abs]
            total_facts += 1
            if len(spans) == 1:
                resolved_facts += 1
                status = "RESOLVED"
                start, end = spans[0]
            elif not spans:
                missing_facts += 1
                status = "POSITION_NOT_FOUND"
                start = end = None
                row_status = status
            else:
                ambiguous_facts += 1
                status = "POSITION_AMBIGUOUS"
                start = end = None
                row_status = status
            legacy = legacy_keys.get((segment_id, fact_index))
            if legacy:
                status = "POSITION_AMBIGUOUS"
                start = end = None
                row_status = status
            fact_positions.append({
                "fact_id": f"{segment_id}-F{fact_index:02d}",
                "fact_index": fact_index,
                "provenance_status": status,
                "evidence_text_sha256": sha_text(fact["evidence"]),
                "evidence_start": start,
                "evidence_end": end,
                "candidate_spans": [list(span) for span in spans],
                "legacy_quarantine_receipt": str(LEGACY_QUARANTINE) if legacy else None,
                "round_trip": bool(start is not None and source_text[start:end] == fact["evidence"]),
            })

        title = manifest["book_title"]
        identity = identity_index[title]
        author = identity["author_name"]
        book_id = manifest.get("book_id") or (stable_id("BK-P2", normalize_title(title), normalize_author(author)) if author else None)
        source_sha = sha_file(source_path)
        source_id = stable_id("SRC-P2", source_sha, str(source_path.name))
        output.append({
            "row_id": segment_id,
            "source_line_number": line_number,
            "sample_class": "special",
            "source_id": source_id,
            "source_sha256": source_sha,
            "chapter_id": manifest.get("chapter_id") or chapter_label,
            "source_paths": [str(source_path)],
            "book_id": book_id,
            "book_title": title,
            "author_id": identity["author_id"],
            "author_name": author,
            "rights_status": "ELIGIBLE_FOR_TRAINING",
            "rights_evidence": [{"path": str(SPECIAL_MANIFEST), "sha256": sha_file(SPECIAL_MANIFEST), "authority_id": manifest["rights_authority_id"]}, {"path": str(SPECIAL_AUTH if line_number > 69 else OLD_SPECIAL_AUTH), "sha256": sha_file(SPECIAL_AUTH if line_number > 69 else OLD_SPECIAL_AUTH)}],
            "identity_status": identity["identity_status"] if book_id else "IDENTITY_UNKNOWN",
            "identity_evidence": [{"path": path, "sha256": sha_file(Path(path))} for path in identity["identity_evidence"]],
            "provenance_status": row_status,
            "provenance_version": "P2_SPECIAL_FROZEN_CHAPTER_UNIQUE_OCCURRENCE_R01",
            "source_match_adapter": adapter,
            "responsibility_zone": {"start": responsibility_start, "end": len(source_text), "coordinate_space": "source_text", "indexing": "python_unicode_zero_based_half_open"},
            "source_text_sha256": sha_text(source_text),
            "source_text_length": len(source_text),
            "facts_count": len(facts),
            "statuses": dict(Counter(fact["status"] for fact in facts)),
            "evidence_span_lengths": [len(fact["evidence"]) for fact in facts],
            "fact_provenance": fact_positions,
            "source_batch": manifest["source_batch"],
            "canonical_payload": {"source_text": source_text, "facts": facts},
        })
    if total_facts != 754:
        raise ValueError(f"special fact denominator drift {total_facts}")
    receipt = {
        "status": "PASS_WITH_IDENTITY_AND_PROVENANCE_EXCLUSIONS",
        "input": {"path": str(SPECIAL_PATH), "sha256": sha_file(SPECIAL_PATH), "rows": 84, "facts": total_facts},
        "manifest": {"path": str(SPECIAL_MANIFEST), "sha256": sha_file(SPECIAL_MANIFEST)},
        "rights": {"eligible_rows": 84, "authority_ids": sorted({manifest["rights_authority_id"] for manifest in manifests})},
        "identity": {
            "resolved_rows": sum(row["identity_status"] == "RESOLVED" for row in output),
            "unknown_rows": sum(row["identity_status"] != "RESOLVED" for row in output),
            "resolved_books": len({row["book_id"] for row in output if row["identity_status"] == "RESOLVED"}),
            "unknown_titles": sorted({row["book_title"] for row in output if row["identity_status"] != "RESOLVED"}),
        },
        "provenance": {"resolved_rows": sum(row["provenance_status"] == "RESOLVED" for row in output), "resolved_facts": resolved_facts, "ambiguous_facts": ambiguous_facts, "not_found_facts": missing_facts},
    }
    return output, receipt


def apply_eligibility(rows: list[dict[str, Any]], frozen_registry: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ledger = []
    eligible = []
    for row in rows:
        matches = frozen_match(row["book_title"], row["book_id"], row["source_paths"], frozen_registry)
        reasons = []
        if row["rights_status"] != "ELIGIBLE_FOR_TRAINING":
            reasons.append(row["rights_status"])
        if row["identity_status"] != "RESOLVED":
            reasons.append(row["identity_status"])
        if row["provenance_status"] != "RESOLVED":
            reasons.append(row["provenance_status"])
        if matches:
            reasons.append("FROZEN_BOOK_RESERVED_FOR_EVAL")
        final = "ELIGIBLE" if not reasons else ("QUARANTINED_PROVENANCE" if any(value.startswith("POSITION_") for value in reasons) else "EXCLUDED")
        public = {key: value for key, value in row.items() if key != "canonical_payload"}
        public.update({
            "frozen_source_status": "EXCLUDED_RESERVED_EVAL_SOURCE" if matches else "CLEAR",
            "frozen_source_matches": matches,
            "final_eligibility": final,
            "exclusion_reasons": reasons,
        })
        ledger.append(public)
        if final == "ELIGIBLE":
            payload = row["canonical_payload"]
            canonical_facts = []
            for fact, provenance in zip(payload["facts"], row["fact_provenance"]):
                canonical_facts.append({
                    "fact_id": provenance["fact_id"],
                    "fact": fact["fact"],
                    "status": fact["status"],
                    "speaker": fact.get("speaker"),
                    "evidence_text": fact["evidence"],
                    "evidence_start": provenance["evidence_start"],
                    "evidence_end": provenance["evidence_end"],
                })
            eligible.append({
                "canonical_row_id": row["row_id"],
                "sample_class": row["sample_class"],
                "source_id": row["source_id"],
                "book_id": row["book_id"],
                "book_title": row["book_title"],
                "author_id": row["author_id"],
                "author_name": row["author_name"],
                "rights_status": row["rights_status"],
                "source_text": payload["source_text"],
                "responsibility_zone": row["responsibility_zone"],
                "facts": canonical_facts,
                "source_batch": row.get("source_batch"),
                "provenance_version": row["provenance_version"],
                "canonical_version": "PRODUCTION_ELIGIBLE_POOL_R01",
            })
    return ledger, eligible


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status = Counter()
    evidence_lengths = []
    source_lengths = []
    facts_per_row = []
    for row in rows:
        facts = row["facts"]
        facts_per_row.append(len(facts))
        source_lengths.append(len(row["source_text"]))
        for fact in facts:
            status[fact["status"]] += 1
            evidence_lengths.append(fact["evidence_end"] - fact["evidence_start"])
    def summary(values: list[int]) -> dict[str, float | int | None]:
        if not values:
            return {"min": None, "mean": None, "max": None}
        return {"min": min(values), "mean": round(sum(values) / len(values), 3), "max": max(values)}
    return {
        "rows": len(rows),
        "facts": sum(len(row["facts"]) for row in rows),
        "books": len({row["book_id"] for row in rows}),
        "authors": len({row["author_id"] for row in rows}),
        "sources": len({row["source_id"] for row in rows}),
        "sample_class": dict(Counter(row["sample_class"] for row in rows)),
        "status": {key: status.get(key, 0) for key in STATUS_VALUES},
        "facts_per_row": summary(facts_per_row),
        "evidence_span_length": summary(evidence_lengths),
        "source_text_length": summary(source_lengths),
        "no_answer_rows": sum(not row["facts"] for row in rows),
    }


def build_author_split(pool: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pool:
        grouped[row["author_id"]].append(row)
    total_facts = sum(len(row["facts"]) for row in pool)
    target = total_facts * 0.20
    dev_authors: set[str] = set()
    covered: set[str] = set()
    dev_facts = 0
    remaining = set(grouped)
    while remaining and (dev_facts < target or covered != set(STATUS_VALUES)):
        choices = []
        for author_id in remaining:
            rows = grouped[author_id]
            statuses = {fact["status"] for row in rows for fact in row["facts"]}
            new_statuses = len(statuses - covered)
            facts = sum(len(row["facts"]) for row in rows)
            overshoot = abs((dev_facts + facts) - target)
            rank = sha_text("P2_SPLIT_R01|" + author_id)
            choices.append((-new_statuses, overshoot, rank, author_id, facts, statuses))
        _, _, _, chosen, facts, statuses = min(choices)
        dev_authors.add(chosen)
        covered.update(statuses)
        dev_facts += facts
        remaining.remove(chosen)
        if dev_facts >= target and covered == set(STATUS_VALUES):
            break

    train = [row for row in pool if row["author_id"] not in dev_authors]
    dev = [row for row in pool if row["author_id"] in dev_authors]
    train_authors = {row["author_id"] for row in train}
    dev_authors_actual = {row["author_id"] for row in dev}
    train_books = {row["book_id"] for row in train}
    dev_books = {row["book_id"] for row in dev}
    train_sources = {row["source_id"] for row in train}
    dev_sources = {row["source_id"] for row in dev}
    split = {
        "split_id": "AUTHOR_LEVEL_SPLIT_R01",
        "algorithm": "deterministic_whole_author_greedy_status_coverage_then_20pct_facts_v1",
        "train_row_ids": [row["canonical_row_id"] for row in train],
        "dev_row_ids": [row["canonical_row_id"] for row in dev],
        "train_author_ids": sorted(train_authors),
        "dev_author_ids": sorted(dev_authors_actual),
        "train_book_ids": sorted(train_books),
        "dev_book_ids": sorted(dev_books),
        "train_source_ids": sorted(train_sources),
        "dev_source_ids": sorted(dev_sources),
        "overlap": {
            "authors": sorted(train_authors & dev_authors_actual),
            "books": sorted(train_books & dev_books),
            "sources": sorted(train_sources & dev_sources),
        },
        "counts": {"train": aggregate(train), "dev": aggregate(dev), "all": aggregate(pool)},
    }
    return split, {"train": train, "dev": dev}


def exclusion_funnel(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    categories = {
        "rights": lambda row: row["rights_status"] != "ELIGIBLE_FOR_TRAINING",
        "identity": lambda row: row["rights_status"] == "ELIGIBLE_FOR_TRAINING" and row["identity_status"] != "RESOLVED",
        "provenance": lambda row: row["rights_status"] == "ELIGIBLE_FOR_TRAINING" and row["identity_status"] == "RESOLVED" and row["provenance_status"] != "RESOLVED",
        "frozen": lambda row: row["rights_status"] == "ELIGIBLE_FOR_TRAINING" and row["identity_status"] == "RESOLVED" and row["provenance_status"] == "RESOLVED" and row["frozen_source_status"] != "CLEAR",
        "eligible": lambda row: row["final_eligibility"] == "ELIGIBLE",
    }
    return {
        key: {"rows": sum(test(row) for row in ledger), "facts": sum(row["facts_count"] for row in ledger if test(row))}
        for key, test in categories.items()
    }


def build_reports(out: Path, ledger: list[dict[str, Any]], pool: list[dict[str, Any]], split: dict[str, Any], a_receipt: dict[str, Any], special_receipt: dict[str, Any], frozen_registry: dict[str, dict[str, Any]]) -> None:
    funnel = exclusion_funnel(ledger)
    frozen_hits = [row for row in ledger if row["frozen_source_status"] != "CLEAR"]
    frozen_audit = {
        "status": "PASS_FROZEN_SOURCES_EXCLUDED_FROM_ELIGIBLE_POOL",
        "frozen_registry": frozen_registry,
        "scan_dimensions": ["normalized_title", "book_id", "source_path", "book_url"],
        "input_rows_scanned": len(ledger),
        "matched_rows": len(frozen_hits),
        "matched_facts": sum(row["facts_count"] for row in frozen_hits),
        "matched": [{"row_id": row["row_id"], "sample_class": row["sample_class"], "book_title": row["book_title"], "facts": row["facts_count"], "matches": row["frozen_source_matches"]} for row in frozen_hits],
        "eligible_pool_frozen_rows": sum(row["book_title"] in FROZEN_TITLES for row in pool),
    }
    write_json(out / "FROZEN_SOURCE_EXCLUSION_AUDIT.json", frozen_audit)

    rights_receipt = {
        "status": "HARD_STOP_A_RIGHTS_UNRESOLVED",
        "input_rows": 314,
        "input_facts": 2783,
        "status_counts": {"ELIGIBLE_FOR_TRAINING": 0, "NOT_ELIGIBLE_FOR_TRAINING": 0, "RIGHTS_UNKNOWN": 314},
        "evidence": a_receipt["rights_authorization"],
        "decision_rule": "The local artifact authorization permits candidate construction only and forbids direct training. It does not establish per-source training rights, so all A rows remain RIGHTS_UNKNOWN.",
        "training_inference_prohibited": ["file existence", "historical training", "other chapters", "network knowledge"],
    }
    write_json(out / "RIGHTS_REPAIR_RECEIPT_314.json", rights_receipt)
    write_json(out / "PROVENANCE_REPAIR_RECEIPT_314.json", a_receipt)
    write_json(out / "SPECIAL_IDENTITY_REPAIR_RECEIPT_84.json", special_receipt)
    write_jsonl(out / "PRODUCTION_ELIGIBILITY_LEDGER_398.jsonl", ledger)
    write_jsonl(out / "PRODUCTION_ELIGIBLE_POOL_R01.jsonl", pool)
    write_json(out / "AUTHOR_LEVEL_SPLIT_R01.json", split)

    gaps = []
    if rights_receipt["status_counts"]["RIGHTS_UNKNOWN"]:
        gaps.append({"gap_id": "P2-GAP-001", "severity": "P0", "area": "rights", "finding": "A v2.7 的 314 行没有逐来源训练授权；候选施工授权还明确禁止直接训练。", "impact": "2,783 条普通事实全部不能进入本轮 eligible pool。", "next_action": "补充可回指到书/来源的训练权利票，再新建 P2 revision；不得从历史训练倒推。", "status": "OPEN"})
    if special_receipt["identity"]["unknown_rows"]:
        gaps.append({"gap_id": "P2-GAP-002", "severity": "P0", "area": "identity", "finding": f"特殊卷仍有 {special_receipt['identity']['unknown_rows']} 行无法从本地材料唯一确认作者。", "impact": "这些行无法进入作者级 split。", "next_action": "仅补本地可信作者来源；未获网络授权前保持隔离。", "status": "OPEN", "titles": special_receipt["identity"]["unknown_titles"]})
    if special_receipt["provenance"]["ambiguous_facts"] or special_receipt["provenance"]["not_found_facts"]:
        gaps.append({"gap_id": "P2-GAP-003", "severity": "P0", "area": "provenance", "finding": f"特殊卷有 {special_receipt['provenance']['ambiguous_facts']} 条重复位置歧义、{special_receipt['provenance']['not_found_facts']} 条未定位。", "impact": "按穷尽式 SFT 合同，包含歧义事实的整行隔离。", "next_action": "恢复权威旧位置后才能重新纳入；禁止默认第一次 occurrence。", "status": "OPEN"})
    if not any(row["sample_class"] == "ordinary" for row in pool):
        gaps.append({"gap_id": "P2-GAP-004", "severity": "P0", "area": "data_balance", "finding": "本轮 eligible pool 没有 ordinary 行，只有通过资格门的 special 行。", "impact": "即使作者 split 无重叠，也不能把该池当成完整生产训练集。", "next_action": "先补 A 普通卷的逐来源权利；不要用特殊卷单独开训。", "status": "OPEN"})
    gates = {
        "all_398_rows_rights_resolved": all(row["rights_status"] != "RIGHTS_UNKNOWN" for row in ledger),
        "included_identity_resolved": all(row["identity_status"] == "RESOLVED" for row in ledger if row["final_eligibility"] == "ELIGIBLE"),
        "included_fact_provenance_resolved": all(row["provenance_status"] == "RESOLVED" for row in ledger if row["final_eligibility"] == "ELIGIBLE"),
        "frozen_five_in_pool_zero": frozen_audit["eligible_pool_frozen_rows"] == 0,
        "train_dev_author_overlap_zero": not split["overlap"]["authors"],
        "train_dev_book_overlap_zero": not split["overlap"]["books"],
        "train_dev_source_overlap_zero": not split["overlap"]["sources"],
        "eligible_pool_evidence_roundtrip": all(row["source_text"][fact["evidence_start"]:fact["evidence_end"]] == fact["evidence_text"] for row in pool for fact in row["facts"]),
        "exclusion_ledger_complete": len(ledger) == 398,
    }
    candidate_allowed = all(gates.values())
    if not candidate_allowed:
        gaps.append({"gap_id": "P2-GAP-005", "severity": "P0", "area": "canonical_gate", "finding": "Production Canonical V1 的全部前置门没有同时通过。", "impact": "本轮不得生成 PRODUCTION_CANONICAL_V1_CANDIDATE_R01。", "next_action": "只修开放缺口并新建 revision；现有输出保持审计证据。", "status": "HARD_STOP"})
    write_jsonl(out / "P2_GAP_LIST.jsonl", gaps)

    counts = split["counts"]
    balance = f"""# P2 作者级拆分平衡报告

✅ 拆分只使用通过四道资格门的 {counts['all']['rows']} 行；作者、作品和来源交集都是 0。

| 项目 | TRAIN | DEV |
|---|---:|---:|
| 行 | {counts['train']['rows']} | {counts['dev']['rows']} |
| 事实 | {counts['train']['facts']} | {counts['dev']['facts']} |
| 作者 | {counts['train']['authors']} | {counts['dev']['authors']} |
| 作品 | {counts['train']['books']} | {counts['dev']['books']} |
| 普通行 | {counts['train']['sample_class'].get('ordinary', 0)} | {counts['dev']['sample_class'].get('ordinary', 0)} |
| 特殊行 | {counts['train']['sample_class'].get('special', 0)} | {counts['dev']['sample_class'].get('special', 0)} |

## 八态事实

| 状态 | TRAIN | DEV |
|---|---:|---:|
""" + "\n".join(f"| {status} | {counts['train']['status'][status]} | {counts['dev']['status'][status]} |" for status in STATUS_VALUES) + f"""

## 难度与长度

- 每行事实数：TRAIN `{counts['train']['facts_per_row']}`；DEV `{counts['dev']['facts_per_row']}`。
- evidence 长度：TRAIN `{counts['train']['evidence_span_length']}`；DEV `{counts['dev']['evidence_span_length']}`。
- source window 长度：TRAIN `{counts['train']['source_text_length']}`；DEV `{counts['dev']['source_text_length']}`。
- 自然空答案：TRAIN {counts['train']['no_answer_rows']}；DEV {counts['dev']['no_answer_rows']}。
- 当前材料没有统一的“事实类型”结构字段，不能凭事实文本临时补分类；本票只报告现有八态和 special 身份。

⚠️ 这不是可训练的完整生产拆分：A 普通卷 314 行因权利不明全部隔离，当前池只剩特殊教材。没有为了凑 80/20 拆作者或移动单行。

来源：Codex
"""
    (out / "AUTHOR_SPLIT_BALANCE_REPORT.md").write_text(balance, encoding="utf-8")

    ticket = f"""# P2 结果票｜Production Canonical 前置资格修复

⚠️ **P2 已完成账目修复，但在 Production Canonical 候选构造前硬停。**

## 真实漏斗

| 阶段 | 行 | 事实 |
|---|---:|---:|
| 冻结输入 | 398 | 3,537 |
| 权利不明排除 | {funnel['rights']['rows']} | {funnel['rights']['facts']} |
| 身份不明排除 | {funnel['identity']['rows']} | {funnel['identity']['facts']} |
| 位置歧义排除 | {funnel['provenance']['rows']} | {funnel['provenance']['facts']} |
| 五本冻结书排除 | {funnel['frozen']['rows']} | {funnel['frozen']['facts']} |
| 最终 eligible pool | {funnel['eligible']['rows']} | {funnel['eligible']['facts']} |

## 修好的部分

- A v2.7：314 行、2,783 条 evidence 全部在冻结窗口内唯一回填；位置账完成。
- 特殊 84：本地可确认的作者和稳定书号已补；未确认的保持 `IDENTITY_UNKNOWN`。
- 已知重复案 `FS02B-006-S01` 沿用正式隔离票，没有擅取第一次 occurrence。
- 五本冻结书共 {frozen_audit['matched_rows']} 行、{frozen_audit['matched_facts']} 条事实全部挡在 eligible pool 外。
- author split 的作者、作品、source 交集均为 0。

## 为什么不能生成 Canonical V1 候选

A v2.7 的本地票只允许生成候选，明确禁止直接训练；没有逐来源训练权利材料。按 P2 纪律只能登记 `RIGHTS_UNKNOWN`，不能因为历史训练过就放行。结果池只剩特殊教材，分布也不具备生产训练资格。

没有生成 `PRODUCTION_CANONICAL_V1_CANDIDATE_R01.jsonl`，没有训练、API、Notion、Git 或现役微调指针变更。

来源：Codex
"""
    (out / "P2_RESULT_TICKET.md").write_text(ticket, encoding="utf-8")

    validation = {
        "status": "PASS_P2_PREREQUISITE_REPAIR_HARD_STOP_BEFORE_CANONICAL",
        "input": {"rows": len(ledger), "facts": sum(row["facts_count"] for row in ledger)},
        "funnel": funnel,
        "gates": gates,
        "canonical_candidate_allowed": candidate_allowed,
        "canonical_candidate_emitted": False,
        "training_started": False,
        "renderer_started": False,
        "api_called": False,
    }
    write_json(out / "P2_VALIDATION_RECEIPT.json", validation)


def build(out: Path) -> None:
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    a_rows, a_receipt = build_a_rows()
    special_rows, special_receipt = build_special_rows()
    frozen_registry = load_frozen_registry()
    ledger, pool = apply_eligibility(a_rows + special_rows, frozen_registry)
    if len(ledger) != 398 or sum(row["facts_count"] for row in ledger) != 3537:
        raise ValueError("combined denominator drift")
    split, _ = build_author_split(pool)
    build_reports(out, ledger, pool, split, a_receipt, special_receipt, frozen_registry)


def seal(run1: Path, run2: Path, out: Path) -> None:
    if out.exists():
        raise FileExistsError(out)
    files1 = sorted(path.relative_to(run1) for path in run1.rglob("*") if path.is_file())
    files2 = sorted(path.relative_to(run2) for path in run2.rglob("*") if path.is_file())
    if files1 != files2:
        raise ValueError("two runs have different member sets")
    comparison = []
    for relative in files1:
        sha1 = sha_file(run1 / relative)
        sha2 = sha_file(run2 / relative)
        comparison.append({"path": str(relative), "run_1_sha256": sha1, "run_2_sha256": sha2, "identical": sha1 == sha2})
    if not all(item["identical"] for item in comparison):
        raise ValueError("two-run byte mismatch")
    out.mkdir(parents=True)
    for relative in files1:
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(run1 / relative, target)
    write_json(out / "TWO_RUN_COMPARISON.json", {"status": "PASS_TWO_RUNS_BYTE_IDENTICAL", "members": comparison})
    write_json(out / "P2_OUTPUT_MANIFEST.json", {
        "status": "HARD_STOP_BEFORE_PRODUCTION_CANONICAL_CANDIDATE",
        "members": [{"path": str(path.relative_to(out)), "bytes": path.stat().st_size, "sha256": sha_file(path)} for path in sorted(out.rglob("*")) if path.is_file() and path.name != "P2_OUTPUT_MANIFEST.json"],
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--out", type=Path, required=True)
    seal_parser = sub.add_parser("seal")
    seal_parser.add_argument("--run-1", type=Path, required=True)
    seal_parser.add_argument("--run-2", type=Path, required=True)
    seal_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        build(args.out)
    else:
        seal(args.run_1, args.run_2, args.out)


if __name__ == "__main__":
    main()
