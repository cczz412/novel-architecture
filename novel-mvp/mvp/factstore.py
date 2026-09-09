"""M4/M5 事实变更的唯一事务入口。

本模块不判断事实真假。它只把作者已经明确的确认／驳回／改写动作，
以及既有 facts 准入结果，交给 planstore 的跨文件事务协调器提交。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

try:
    from . import planstore, text_mapping
except ImportError:  # pragma: no cover - 直接运行脚本时使用
    import planstore  # type: ignore[no-redef]
    import text_mapping  # type: ignore[no-redef]


STATUS_EXTRACTED = "extracted"
STATUS_CONFIRMED = "confirmed"
STATUS_REJECTED = "rejected"
FACT_STATUSES = {STATUS_EXTRACTED, STATUS_CONFIRMED, STATUS_REJECTED}
ACTION_KEYS = {
    "contract",
    "version",
    "operation_id",
    "actor",
    "fact_ref",
    "expected_status",
    "expected_fact_sha256",
    "decision",
    "replacement_text",
    "note",
}
DECISIONS = {"confirm", "reject", "edit", "edit_and_confirm"}
FAULT_POINTS = {
    "after_prepare",
    "after_facts",
    "after_fact_causal_edges",
    "after_plan",
    "after_blob",
    "during_history",
    "after_history",
    "before_commit",
    "after_commit",
}
FACT_ID_RE = re.compile(r"f(\d+)$")
CAUSAL_EDGE_ID_RE = re.compile(r"CE-(\d+)$")
CAUSAL_EDGE_FILENAME = "fact_causal_edges.json"
CAUSAL_EDGE_CONTRACT = "FACT_CAUSAL_EDGE"
CAUSAL_EDGE_VERSION = "fact-causal-edge-v1"
CAUSAL_EDGE_STATUSES = {"candidate", "confirmed", "retired"}
CAUSAL_EDGE_SOURCES = {
    "author_declared",
    "draft_inferred",
    "model_suggested",
}
CAUSAL_EDGE_SPANS = {"直接", "长程"}
CAUSAL_EDGE_REVIEW_DECISIONS = {"confirm", "retire", "defer"}
CAUSAL_EDGE_CANDIDATE_REQUIRED_KEYS = {
    "source_identity",
    "from_fact_ref",
    "to_fact_ref",
    "span",
}
CAUSAL_EDGE_CANDIDATE_OPTIONAL_KEYS = {"evidence_refs", "note"}
C11_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "contracts"
    / "C11_CHAPTER_REVISION_LEDGER.schema.json"
)
CAUSAL_EDGE_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "contracts"
    / "FACT_CAUSAL_EDGE.schema.json"
)
ANCHOR_COORDINATE_BASIS = "CHAPTER_REVISION_TEXT_UNICODE_CODEPOINT_0_BASED_HALF_OPEN"


class FactstoreError(planstore.PlanstoreError):
    """事实动作在写前或恢复时被拒绝。"""


def allocate_fact_ids(facts: list[dict[str, Any]], count: int) -> list[str]:
    """从现有最大 f 号顺延，逐个查重。"""
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise FactstoreError("FACT_ID_COUNT_INVALID")
    used = {
        item.get("id")
        for item in facts
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    numbers = [
        int(match.group(1))
        for item in facts
        if isinstance(item, dict)
        for match in [FACT_ID_RE.fullmatch(str(item.get("id") or ""))]
        if match is not None
    ]
    next_number = max(numbers, default=0) + 1
    result: list[str] = []
    while len(result) < count:
        fact_ref = f"f{next_number:03d}"
        if fact_ref not in used:
            result.append(fact_ref)
            used.add(fact_ref)
        next_number += 1
    return result


@lru_cache(maxsize=1)
def _c11_validator() -> Draft202012Validator:
    schema = json.loads(C11_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _validate_c11_object(
    value: Any, contract: str, version: str = "v1"
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FactstoreError(f"{contract}_NOT_OBJECT")
    if value.get("contract") != contract or value.get("version") != version:
        raise FactstoreError(f"{contract}_IDENTITY_INVALID")
    # The optional, explicitly named mapping extension belongs to C2/C3/C4.
    # Validate its proof separately; the frozen C11 base schema stays unchanged.
    base = dict(value)
    extension = None
    if contract == "C2_SEGMENT" and "text_map" in base:
        extension = base.pop("text_map")
    elif contract in {"C3_FACT_CANDIDATE", "C4_FACT_QUERY"} and "text_map_evidence" in base:
        extension = base.pop("text_map_evidence")
    errors = sorted(
        _c11_validator().iter_errors(base), key=lambda item: list(item.path)
    )
    if errors:
        first = errors[0]
        path = "/".join(map(str, first.path)) or "$"
        raise FactstoreError(f"{contract}_SCHEMA_INVALID:{path}:{first.message}")
    if value != base:
        try:
            if contract == "C2_SEGMENT":
                text_mapping.validate_segment(value)
            else:
                result = text_mapping.validate_origin_evidence(extension)
                if contract == "C3_FACT_CANDIDATE":
                    text_mapping.validate_fact_adaptation(value)
                    if (value["quote"] != extension["quote_original"]
                            or value["chapter_revision_ref"] != result["chapter_revision_ref"]
                            or value["seg"] != extension["responsibility"]["seg"]):
                        raise ValueError("C3_TEXT_MAP_ORIGIN_MISMATCH")
                else:
                    if (value["quote"] != result["text"]
                            or value["chapter_id"] != result["chapter_revision_ref"]["chapter_id"]
                            or value.get("seg") != extension["responsibility"]["seg"]):
                        raise ValueError("C4_TEXT_MAP_ORIGIN_MISMATCH")
                    current_ref = value["chapter_revision_ref"]
                    origin_ref = result["chapter_revision_ref"]
                    if current_ref["revision_no"] <= origin_ref["revision_no"]:
                        if current_ref != origin_ref:
                            raise ValueError("C4_TEXT_MAP_ORIGIN_REVISION_MISMATCH")
                        anchor = value["anchor_ref"]
                        if (not isinstance(anchor, dict)
                                or anchor.get("start") != result["start"]
                                or anchor.get("end") != result["end"]):
                            raise ValueError("C4_TEXT_MAP_ORIGIN_ANCHOR_MISMATCH")
        except (ValueError, KeyError, TypeError) as exc:
            raise FactstoreError(f"{contract}_TEXT_MAP_INVALID:{exc}") from exc
    return value


def validate_c4_v1_snapshot(value: Any) -> list[dict[str, Any]]:
    """校验并复制一份完整 C4 v1 快照，不授予任何新状态或写权限。"""
    if not isinstance(value, list):
        raise FactstoreError("C4_V1_SNAPSHOT_NOT_LIST")
    facts = [
        copy.deepcopy(_validate_c11_object(fact, "C4_FACT_QUERY")) for fact in value
    ]
    fact_refs = [fact["id"] for fact in facts]
    if len(fact_refs) != len(set(fact_refs)):
        raise FactstoreError("C4_FACT_ID_DUPLICATE")
    for fact in facts:
        revision_ref = fact["chapter_revision_ref"]
        if revision_ref["chapter_id"] != fact["chapter_id"]:
            raise FactstoreError("C4_CHAPTER_REVISION_REF_MISMATCH")
        if fact["anchor_state"] != "VERIFIED":
            continue
        quote = fact["quote"]
        anchor = fact["anchor_ref"]
        if not quote or not isinstance(anchor, dict):
            raise FactstoreError("C4_VERIFIED_ANCHOR_INVALID")
        if any(anchor.get(key) != revision_ref[key] for key in revision_ref):
            raise FactstoreError("C4_ANCHOR_REVISION_REF_MISMATCH")
        start, end = anchor["start"], anchor["end"]
        if end - start != len(quote):
            raise FactstoreError("C4_ANCHOR_QUOTE_LENGTH_MISMATCH")
        quote_sha = hashlib.sha256(quote.encode("utf-8")).hexdigest()
        if anchor["slice_sha256"] != quote_sha:
            raise FactstoreError("C4_ANCHOR_QUOTE_SHA_MISMATCH")
    return facts


@lru_cache(maxsize=1)
def _causal_edge_validator() -> Draft202012Validator:
    schema = json.loads(CAUSAL_EDGE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _parse_causal_edge_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise FactstoreError(f"{label}_INVALID")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise FactstoreError(f"{label}_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FactstoreError(f"{label}_TIMEZONE_REQUIRED")
    return parsed


def validate_fact_causal_edge_record(value: Any) -> dict[str, Any]:
    """校验并复制一条正式因果边，不授予确认权限。"""
    if not isinstance(value, dict):
        raise FactstoreError("FACT_CAUSAL_EDGE_NOT_OBJECT")
    errors = sorted(
        _causal_edge_validator().iter_errors(value),
        key=lambda item: (list(item.absolute_path), item.message),
    )
    if errors:
        first = errors[0]
        path = "/".join(map(str, first.absolute_path)) or "$"
        raise FactstoreError(
            f"FACT_CAUSAL_EDGE_SCHEMA_INVALID:{path}:{first.validator}"
        )
    if (
        value.get("contract") != CAUSAL_EDGE_CONTRACT
        or value.get("version") != CAUSAL_EDGE_VERSION
    ):
        raise FactstoreError("FACT_CAUSAL_EDGE_IDENTITY_INVALID")
    created = _parse_causal_edge_timestamp(
        value["created_at"], "CAUSAL_EDGE_CREATED_AT"
    )
    updated = _parse_causal_edge_timestamp(
        value["updated_at"], "CAUSAL_EDGE_UPDATED_AT"
    )
    if updated < created:
        raise FactstoreError("CAUSAL_EDGE_UPDATED_AT_BEFORE_CREATED_AT")
    if value["confirm_status"] == "confirmed" and not value["evidence_refs"]:
        raise FactstoreError("CAUSAL_EDGE_CONFIRMED_REQUIRES_EVIDENCE")
    if value["from_fact_ref"] == value["to_fact_ref"]:
        raise FactstoreError("CAUSAL_EDGE_SELF_LOOP_FORBIDDEN")
    return copy.deepcopy(value)


def validate_fact_causal_edge_snapshot(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise FactstoreError("FACT_CAUSAL_EDGE_SNAPSHOT_NOT_LIST")
    edges = [validate_fact_causal_edge_record(item) for item in value]
    edge_refs = [item["id"] for item in edges]
    if len(edge_refs) != len(set(edge_refs)):
        raise FactstoreError("FACT_CAUSAL_EDGE_ID_DUPLICATE")
    return edges


def _load_fact_causal_edges(root: Path) -> list[dict[str, Any]]:
    path = root / CAUSAL_EDGE_FILENAME
    if not path.exists() or not path.read_bytes():
        return []
    return validate_fact_causal_edge_snapshot(planstore._read_json(path))


def read_fact_causal_edges(project_dir: str | Path) -> list[dict[str, Any]]:
    """读回全部 current 因果边，包含候选与已退役记录。"""
    return copy.deepcopy(_load_fact_causal_edges(Path(project_dir)))


def read_confirmed_fact_causal_edges(project_dir: str | Path) -> list[dict[str, Any]]:
    """给 M6/M8/评测的只读面只暴露已确认边。"""
    return [
        item
        for item in read_fact_causal_edges(project_dir)
        if item["confirm_status"] == "confirmed"
    ]


def allocate_fact_causal_edge_ids(edges: list[dict[str, Any]], count: int) -> list[str]:
    """从现存最大 CE 号顺延；退役记录仍占号。"""
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise FactstoreError("FACT_CAUSAL_EDGE_ID_COUNT_INVALID")
    validated = validate_fact_causal_edge_snapshot(edges)
    used = {item["id"] for item in validated}
    numbers = [
        int(match.group(1))
        for item in validated
        for match in [CAUSAL_EDGE_ID_RE.fullmatch(item["id"])]
        if match is not None
    ]
    next_number = max(numbers, default=0) + 1
    result: list[str] = []
    while len(result) < count:
        edge_ref = f"CE-{next_number:04d}"
        if edge_ref not in used:
            result.append(edge_ref)
            used.add(edge_ref)
        next_number += 1
    return result


def fact_causal_edge_sha256(edge: dict[str, Any]) -> str:
    return planstore._sha256_json(validate_fact_causal_edge_record(edge))


def _normalized_text_with_raw_positions(raw_text: str) -> tuple[str, list[int]]:
    chunks: list[tuple[int, int]] = []
    cursor = 0
    for match in re.finditer(r"\n\s*\n|\n", raw_text):
        chunks.append((cursor, match.start()))
        cursor = match.end()
    chunks.append((cursor, len(raw_text)))

    paragraphs: list[tuple[str, int, int]] = []
    for start, end in chunks:
        chunk = raw_text[start:end]
        stripped = chunk.strip()
        if not stripped:
            continue
        left_trim = len(chunk) - len(chunk.lstrip())
        raw_start = start + left_trim
        paragraphs.append((stripped, raw_start, raw_start + len(stripped)))

    normalized_parts: list[str] = []
    raw_positions: list[int] = []
    previous_raw_end: int | None = None
    for paragraph, raw_start, raw_end in paragraphs:
        if normalized_parts:
            if previous_raw_end is None:
                raise FactstoreError("C2_NORMALIZED_TO_REVISION_MAPPING_INVALID")
            separator = raw_text.find("\n", previous_raw_end, raw_start)
            if separator < 0:
                raise FactstoreError("C2_NORMALIZED_TO_REVISION_MAPPING_INVALID")
            normalized_parts.append("\n")
            raw_positions.append(separator)
        normalized_parts.append(paragraph)
        raw_positions.extend(range(raw_start, raw_end))
        previous_raw_end = raw_end
    return "".join(normalized_parts), raw_positions


def build_extracted_c4_snapshot(
    *,
    chapter: dict[str, Any],
    segments: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    existing_facts: list[dict[str, Any]],
    source: str,
    added_at: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """把同一 C1 revision 下的 C2/C3 对象纯函数转换为 C4 v1 extracted 快照。"""
    chapter = _validate_c11_object(chapter, "C1_CHAPTER_DOC")
    if not isinstance(source, str) or not source.strip():
        raise FactstoreError("C4_SOURCE_INVALID")
    if not isinstance(added_at, str) or not added_at.strip():
        raise FactstoreError("C4_ADDED_AT_INVALID")
    if not isinstance(segments, list) or not isinstance(candidates, list):
        raise FactstoreError("C2_C3_BATCH_NOT_LIST")
    if not isinstance(existing_facts, list):
        raise FactstoreError("C4_EXISTING_SNAPSHOT_NOT_LIST")

    revision_ref = chapter["chapter_revision_ref"]
    chapter_text = chapter["text"]
    if revision_ref["chapter_id"] != chapter["id"]:
        raise FactstoreError("C1_REVISION_CHAPTER_MISMATCH")
    chapter_sha = hashlib.sha256(chapter_text.encode("utf-8")).hexdigest()
    if revision_ref["revision_text_sha256"] != chapter_sha:
        raise FactstoreError("C1_REVISION_SHA_MISMATCH")
    normalized_text, raw_positions = _normalized_text_with_raw_positions(chapter_text)

    segments_by_no: dict[int, dict[str, Any]] = {}
    occupied_ranges: list[tuple[int, int]] = []
    for segment in segments:
        segment = _validate_c11_object(segment, "C2_SEGMENT")
        if segment["chapter_revision_ref"] != revision_ref:
            raise FactstoreError("C2_REVISION_REF_MISMATCH")
        if segment["seg"] in segments_by_no:
            raise FactstoreError("C2_SEGMENT_NUMBER_DUPLICATE")
        start, end = segment["start"], segment["end"]
        if end != start + len(segment["text"]):
            raise FactstoreError("C2_SEGMENT_RANGE_LENGTH_MISMATCH")
        if normalized_text[start:end] != segment["text"]:
            raise FactstoreError("C2_SEGMENT_TEXT_RANGE_MISMATCH")
        if any(
            start < other_end and other_start < end
            for other_start, other_end in occupied_ranges
        ):
            raise FactstoreError("C2_SEGMENT_RANGE_OVERLAP")
        occupied_ranges.append((start, end))
        segments_by_no[segment["seg"]] = segment

    facts_before = validate_c4_v1_snapshot(existing_facts)

    validated_candidates: list[tuple[dict[str, Any], dict[str, Any], int, int]] = []
    for candidate in candidates:
        candidate = _validate_c11_object(candidate, "C3_FACT_CANDIDATE")
        if candidate["chapter_revision_ref"] != revision_ref:
            raise FactstoreError("C3_REVISION_REF_MISMATCH")
        if not candidate["text"].strip():
            raise FactstoreError("C3_FACT_TEXT_EMPTY")
        segment = segments_by_no.get(candidate["seg"])
        if segment is None:
            raise FactstoreError("C3_SEGMENT_NOT_FOUND")
        quote = candidate["quote"]
        if "text_map" in segment:
            try:
                mapped = text_mapping.validate_candidate(candidate, segment, chapter=chapter)
            except (ValueError, KeyError, TypeError) as exc:
                raise FactstoreError(f"C3_TEXT_MAP_INVALID:{exc}") from exc
            validated_candidates.append((candidate, segment, mapped["start"], mapped["end"]))
            continue
        if "text_map_evidence" in candidate:
            raise FactstoreError("C3_TEXT_MAP_WITHOUT_C2_CONTEXT")
        if not quote:
            raise FactstoreError("C3_QUOTE_REQUIRED_FOR_VERIFIED_ANCHOR")
        local_start = segment["text"].find(quote)
        if local_start < 0:
            raise FactstoreError("C3_QUOTE_NOT_IN_C2_SEGMENT")
        if segment["text"].find(quote, local_start + 1) >= 0:
            raise FactstoreError("C3_QUOTE_AMBIGUOUS_IN_C2_SEGMENT")
        normalized_start = segment["start"] + local_start
        normalized_end = normalized_start + len(quote)
        quote_positions = raw_positions[normalized_start:normalized_end]
        if len(quote_positions) != len(quote):
            raise FactstoreError("C3_QUOTE_REVISION_MAPPING_INCOMPLETE")
        raw_start = quote_positions[0]
        raw_end = quote_positions[-1] + 1
        if (
            quote_positions != list(range(raw_start, raw_end))
            or chapter_text[raw_start:raw_end] != quote
        ):
            raise FactstoreError("C3_QUOTE_NOT_CONTIGUOUS_IN_REVISION")
        validated_candidates.append((candidate, segment, raw_start, raw_end))

    new_ids = allocate_fact_ids(facts_before, len(validated_candidates))
    new_records: list[dict[str, Any]] = []
    for (candidate, segment, raw_start, raw_end), fact_ref in zip(
        validated_candidates, new_ids
    ):
        quote = (chapter_text[raw_start:raw_end]
                 if "text_map_evidence" in candidate else candidate["quote"])
        record = {
            "contract": "C4_FACT_QUERY",
            "version": "v1",
            "id": fact_ref,
            "chapter_id": chapter["id"],
            "text": candidate["text"],
            "quote": quote,
            "status": STATUS_EXTRACTED,
            "source": source,
            "note": "",
            "added_at": added_at,
            "seg": segment["seg"],
            "chapter_revision_ref": copy.deepcopy(revision_ref),
            "anchor_ref": {
                **copy.deepcopy(revision_ref),
                "coordinate_basis": ANCHOR_COORDINATE_BASIS,
                "start": raw_start,
                "end": raw_end,
                "slice_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
            },
            "anchor_state": "VERIFIED",
            "recheck": None,
        }
        if "text_map_evidence" in candidate:
            record["text_map_evidence"] = copy.deepcopy(candidate["text_map_evidence"])
        new_records.append(copy.deepcopy(_validate_c11_object(record, "C4_FACT_QUERY")))
    return [*facts_before, *new_records], new_ids


def fact_sha256(fact: dict[str, Any]) -> str:
    return planstore._sha256_json(fact)


def c4_snapshot_sha256(snapshot: list[dict[str, Any]]) -> str:
    return planstore._sha256_json(validate_c4_v1_snapshot(snapshot))


def new_operation_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _validate_facts(facts: Any) -> list[dict[str, Any]]:
    if not isinstance(facts, list) or any(not isinstance(item, dict) for item in facts):
        raise FactstoreError("C4_FACTS_NOT_LIST")
    refs = [item.get("id") for item in facts]
    if any(
        not isinstance(ref, str) or FACT_ID_RE.fullmatch(ref) is None for ref in refs
    ):
        raise FactstoreError("C4_FACT_ID_INVALID")
    if len(refs) != len(set(refs)):
        raise FactstoreError("C4_FACT_ID_DUPLICATE")
    if any(item.get("status") not in FACT_STATUSES for item in facts):
        raise FactstoreError("C4_FACT_STATUS_INVALID")
    return facts


def _validate_review_action(action: Any) -> None:
    if not isinstance(action, dict) or set(action) != ACTION_KEYS:
        raise FactstoreError("FACT_REVIEW_ACTION_SCHEMA_MISMATCH")
    if action.get("contract") != "FACT_REVIEW_ACTION" or action.get("version") != "v1":
        raise FactstoreError("FACT_REVIEW_ACTION_IDENTITY_INVALID")
    if action.get("actor") != "author":
        raise FactstoreError("FACT_REVIEW_AUTHOR_REQUIRED")
    planstore._validate_operation_id(action.get("operation_id"))
    if (
        not isinstance(action.get("fact_ref"), str)
        or FACT_ID_RE.fullmatch(action["fact_ref"]) is None
    ):
        raise FactstoreError("FACT_REVIEW_FACT_REF_INVALID")
    if action.get("expected_status") not in FACT_STATUSES:
        raise FactstoreError("FACT_REVIEW_EXPECTED_STATUS_INVALID")
    if (
        not isinstance(action.get("expected_fact_sha256"), str)
        or planstore.SHA256_RE.fullmatch(action["expected_fact_sha256"]) is None
    ):
        raise FactstoreError("FACT_REVIEW_EXPECTED_SHA_INVALID")
    decision = action.get("decision")
    if decision not in DECISIONS:
        raise FactstoreError("FACT_REVIEW_DECISION_INVALID")
    if not isinstance(action.get("note"), str):
        raise FactstoreError("FACT_REVIEW_NOTE_INVALID")
    replacement = action.get("replacement_text")
    if decision in {"edit", "edit_and_confirm"}:
        if not isinstance(replacement, str) or not replacement.strip():
            raise FactstoreError("FACT_REVIEW_REPLACEMENT_REQUIRED")
    elif replacement is not None:
        raise FactstoreError("FACT_REVIEW_REPLACEMENT_FORBIDDEN")


def build_review_action(
    fact: dict[str, Any],
    *,
    decision: str,
    note: str = "",
    replacement_text: str | None = None,
    operation_id: str | None = None,
) -> dict[str, Any]:
    """供旧调用面构造与当前记录精确绑定的作者动作。"""
    action = {
        "contract": "FACT_REVIEW_ACTION",
        "version": "v1",
        "operation_id": operation_id or new_operation_id("op-m5-review"),
        "actor": "author",
        "fact_ref": fact.get("id"),
        "expected_status": fact.get("status"),
        "expected_fact_sha256": fact_sha256(fact),
        "decision": decision,
        "replacement_text": replacement_text,
        "note": note,
    }
    _validate_review_action(action)
    return action


def apply_review_action_to_c4_snapshot(
    *,
    snapshot: list[dict[str, Any]],
    action: dict[str, Any],
    chapter_revision_ref: dict[str, Any],
    decided_at: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """纯对象执行一条正式 M5 动作；不提交文件、不碰 planstore。"""
    facts_before = validate_c4_v1_snapshot(snapshot)
    _validate_review_action(action)
    if not isinstance(decided_at, str) or not decided_at.strip():
        raise FactstoreError("FACT_REVIEW_DECIDED_AT_INVALID")
    matches = [fact for fact in facts_before if fact["id"] == action["fact_ref"]]
    if len(matches) != 1:
        raise FactstoreError("FACT_REVIEW_TARGET_NOT_FOUND")
    fact_before = matches[0]
    if fact_before["chapter_revision_ref"] != chapter_revision_ref:
        raise FactstoreError("STALE_CHAPTER_REVISION_REF")
    if (
        fact_before["status"] != action["expected_status"]
        or fact_sha256(fact_before) != action["expected_fact_sha256"]
    ):
        raise FactstoreError("STALE_FACT_REVISION")

    facts_after = copy.deepcopy(facts_before)
    fact_after = next(fact for fact in facts_after if fact["id"] == action["fact_ref"])
    decision = action["decision"]
    if decision == "confirm":
        fact_after["status"] = STATUS_CONFIRMED
    elif decision == "reject":
        fact_after["status"] = STATUS_REJECTED
    elif decision in {"edit", "edit_and_confirm"}:
        old_text = fact_after["text"]
        fact_after["text"] = action["replacement_text"].strip()
        fact_after["note"] = action["note"] or f"原文候选：{old_text}"
        if decision == "edit_and_confirm":
            fact_after["status"] = STATUS_CONFIRMED
    if action["note"] and decision not in {"edit", "edit_and_confirm"}:
        fact_after["note"] = action["note"]
    if decision in {"confirm", "reject", "edit_and_confirm"}:
        fact_after["decided_at"] = decided_at

    facts_after = validate_c4_v1_snapshot(facts_after)
    return facts_after, {
        "operation_id": action["operation_id"],
        "fact_ref": action["fact_ref"],
        "decision": decision,
        "before_status": fact_before["status"],
        "after_status": fact_after["status"],
        "before_fact_sha256": fact_sha256(fact_before),
        "after_fact_sha256": fact_sha256(fact_after),
        "changed_fields": sorted(
            key for key in fact_after if fact_before.get(key) != fact_after.get(key)
        ),
    }


def _history_row(
    *,
    operation_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
    timestamp: str,
    note: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    content_hash, blob = planstore._blob_record(before)
    return (
        {
            "ts": timestamp,
            "op": operation_id,
            "actor": "author",
            "action": "fact_basis_stale",
            "object_id": after["id"],
            "rev": after["rev"],
            "changes": {"edge_status": [before["edge_status"], after["edge_status"]]},
            "content_hash": content_hash,
            "note": note,
        },
        blob,
    )


def commit_facts_transaction_locked(
    root: Path,
    *,
    operation_id: str,
    action_name: str,
    request_sha256: str,
    facts_after: list[dict[str, Any]],
    plan_after: dict[str, Any] | None,
    history_rows: list[dict[str, Any]],
    blobs: list[dict[str, Any]],
    receipt: dict[str, Any],
    timestamp: str,
    fault_at: str | None = None,
    extra_replacements: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    """已经持有 `.planstore.lock` 时，唯一允许替换 facts.json 的底层入口。"""
    _validate_facts(facts_after)
    replacements = {
        "facts.json": planstore._canonical_bytes(facts_after),
        **(extra_replacements or {}),
    }
    if plan_after is not None:
        planstore._validate_plan(plan_after)
        replacements["plan.json"] = planstore._canonical_bytes(plan_after)
    appends = {}
    if history_rows:
        appends["plan_history.jsonl"] = b"".join(
            planstore._canonical_bytes(row) for row in history_rows
        )
    return planstore._commit_generic_transaction_locked(
        root,
        operation_id=operation_id,
        action_name=action_name,
        request_sha256=request_sha256,
        replacements=replacements,
        appends=appends,
        blobs=blobs,
        receipt=receipt,
        timestamp=timestamp,
        fault_at=fault_at,
    )


def _replayed_receipt(root: Path, operation_id: str) -> dict[str, Any]:
    prepare = next(
        (
            row
            for row in planstore._operation_rows(root, operation_id)
            if row.get("phase") == "prepare"
        ),
        None,
    )
    if prepare is None or not isinstance(prepare.get("receipt"), dict):
        raise FactstoreError("COMMITTED_FACTSTORE_RECEIPT_UNRESOLVABLE")
    return {
        **copy.deepcopy(prepare["receipt"]),
        "story_commit_seq": prepare["story_commit_seq"],
        "replayed": True,
    }


def _validate_causal_edge_fact_refs(
    edge: dict[str, Any],
    facts_by_ref: dict[str, dict[str, Any]],
    *,
    require_confirmed_endpoints: bool,
) -> None:
    endpoints = {edge["from_fact_ref"], edge["to_fact_ref"]}
    if not endpoints.issubset(facts_by_ref):
        raise FactstoreError("FACT_CAUSAL_EDGE_ENDPOINT_NOT_FOUND")
    evidence_fact_refs = {
        ref for ref in edge["evidence_refs"] if ref != "AUTHOR_ATTESTATION"
    }
    if not evidence_fact_refs.issubset(facts_by_ref):
        raise FactstoreError("FACT_CAUSAL_EDGE_EVIDENCE_NOT_FOUND")
    if require_confirmed_endpoints and any(
        facts_by_ref[ref]["status"] != STATUS_CONFIRMED for ref in endpoints
    ):
        raise FactstoreError("FACT_CAUSAL_EDGE_ENDPOINT_NOT_CONFIRMED")


def _causal_edge_history_row(
    *,
    operation_id: str,
    actor: str,
    action_name: str,
    before: dict[str, Any],
    after: dict[str, Any],
    timestamp: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    content_hash, blob = planstore._blob_record(before)
    return (
        {
            "ts": timestamp,
            "op": operation_id,
            "actor": actor,
            "action": action_name,
            "object_id": after["id"],
            "rev": after["rev"],
            "changes": {
                "fact_causal_edge": [copy.deepcopy(before), copy.deepcopy(after)]
            },
            "content_hash": content_hash,
            "note": "FACT_CAUSAL_EDGE writer",
        },
        blob,
    )


def _commit_fact_causal_edges_locked(
    root: Path,
    *,
    operation_id: str,
    action_name: str,
    request_sha256: str,
    edges_after: list[dict[str, Any]],
    history_rows: list[dict[str, Any]],
    blobs: list[dict[str, Any]],
    receipt: dict[str, Any],
    timestamp: str,
    fault_at: str | None,
) -> dict[str, Any]:
    edges_after = validate_fact_causal_edge_snapshot(edges_after)
    return planstore._commit_generic_transaction_locked(
        root,
        operation_id=operation_id,
        action_name=action_name,
        request_sha256=request_sha256,
        replacements={
            CAUSAL_EDGE_FILENAME: planstore._canonical_bytes(edges_after),
        },
        appends={
            "plan_history.jsonl": b"".join(
                planstore._canonical_bytes(row) for row in history_rows
            )
        },
        blobs=blobs,
        receipt=receipt,
        timestamp=timestamp,
        fault_at=fault_at,
    )


def _build_fact_causal_edge_candidate(
    *,
    item: Any,
    edge_ref: str,
    timestamp: str,
    actor: str,
) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise FactstoreError("FACT_CAUSAL_EDGE_CANDIDATE_NOT_OBJECT")
    keys = set(item)
    if not CAUSAL_EDGE_CANDIDATE_REQUIRED_KEYS.issubset(keys) or not keys.issubset(
        CAUSAL_EDGE_CANDIDATE_REQUIRED_KEYS | CAUSAL_EDGE_CANDIDATE_OPTIONAL_KEYS
    ):
        raise FactstoreError("FACT_CAUSAL_EDGE_CANDIDATE_SCHEMA_MISMATCH")
    source_identity = item.get("source_identity")
    if source_identity not in CAUSAL_EDGE_SOURCES:
        raise FactstoreError("FACT_CAUSAL_EDGE_SOURCE_INVALID")
    if actor == "machine" and source_identity == "author_declared":
        raise FactstoreError("FACT_CAUSAL_EDGE_AUTHOR_SOURCE_REQUIRED")
    evidence_refs = item.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        raise FactstoreError("FACT_CAUSAL_EDGE_EVIDENCE_INVALID")
    if "AUTHOR_ATTESTATION" in evidence_refs and actor != "author":
        raise FactstoreError("FACT_CAUSAL_EDGE_AUTHOR_ATTESTATION_REQUIRED")
    return validate_fact_causal_edge_record(
        {
            "contract": CAUSAL_EDGE_CONTRACT,
            "version": CAUSAL_EDGE_VERSION,
            "id": edge_ref,
            "source_identity": source_identity,
            "confirm_status": "candidate",
            "evidence_refs": copy.deepcopy(evidence_refs),
            "created_at": timestamp,
            "updated_at": timestamp,
            "rev": 1,
            "note": item.get("note", ""),
            "from_fact_ref": item.get("from_fact_ref"),
            "to_fact_ref": item.get("to_fact_ref"),
            "span": item.get("span"),
        }
    )


def add_fact_causal_edge_candidates(
    project_dir: str | Path,
    *,
    items: list[dict[str, Any]],
    actor: str,
    timestamp: str,
    operation_id: str | None = None,
    fault_at: str | None = None,
) -> dict[str, Any]:
    """为候选因果边发 CE 号并写入事实账；任何来源都只能得到 candidate。"""
    if not isinstance(items, list) or not items:
        raise FactstoreError("FACT_CAUSAL_EDGE_CANDIDATES_REQUIRED")
    if actor not in {"author", "machine"}:
        raise FactstoreError("FACT_CAUSAL_EDGE_ACTOR_INVALID")
    _parse_causal_edge_timestamp(timestamp, "CAUSAL_EDGE_TIMESTAMP")
    if fault_at is not None and fault_at not in FAULT_POINTS:
        raise FactstoreError("UNKNOWN_FACT_CAUSAL_EDGE_FAULT_POINT")
    operation_id = operation_id or new_operation_id("op-m4-causal-edge-add")
    planstore._validate_operation_id(operation_id)
    for index, item in enumerate(items, start=1):
        _build_fact_causal_edge_candidate(
            item=item,
            edge_ref=f"CE-{index:04d}",
            timestamp=timestamp,
            actor=actor,
        )
    request_sha = planstore._sha256_json(
        {
            "items": items,
            "actor": actor,
            "timestamp": timestamp,
        }
    )
    root = Path(project_dir)
    with planstore._exclusive_lock(root):
        planstore._recover_pending_locked(root, timestamp=timestamp)
        status = planstore._operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            if status["request_sha256"] != request_sha:
                raise FactstoreError("OPERATION_ID_PAYLOAD_CONFLICT")
            return _replayed_receipt(root, operation_id)
        if status["terminal_phase"] == "rolled_back":
            raise FactstoreError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        if status["state"] == "NEEDS_MANUAL_RECOVERY":
            raise FactstoreError("OPERATION_NEEDS_MANUAL_RECOVERY")

        facts = _validate_facts(planstore._read_json(root / "facts.json"))
        facts_by_ref = {item["id"]: item for item in facts}
        edges_before = _load_fact_causal_edges(root)
        new_ids = allocate_fact_causal_edge_ids(edges_before, len(items))
        new_edges = [
            _build_fact_causal_edge_candidate(
                item=item,
                edge_ref=edge_ref,
                timestamp=timestamp,
                actor=actor,
            )
            for item, edge_ref in zip(items, new_ids)
        ]
        for edge in new_edges:
            _validate_causal_edge_fact_refs(
                edge, facts_by_ref, require_confirmed_endpoints=False
            )
        edges_after = [*edges_before, *new_edges]
        history_rows: list[dict[str, Any]] = []
        blobs: list[dict[str, Any]] = []
        for edge in new_edges:
            row, blob = _causal_edge_history_row(
                operation_id=operation_id,
                actor=actor,
                action_name="fact_causal_edge_candidate_add",
                before={"id": edge["id"], "rev": 0, "state": "absent"},
                after=edge,
                timestamp=timestamp,
            )
            history_rows.append(row)
            blobs.append(blob)
        return _commit_fact_causal_edges_locked(
            root,
            operation_id=operation_id,
            action_name="fact_causal_edge_candidate_add",
            request_sha256=request_sha,
            edges_after=edges_after,
            history_rows=history_rows,
            blobs=blobs,
            receipt={
                "operation_id": operation_id,
                "status": "COMMITTED",
                "new_ce_ids": new_ids,
                "candidate_count": len(new_edges),
                "confirmed_writes": 0,
            },
            timestamp=timestamp,
            fault_at=fault_at,
        )


def review_fact_causal_edge(
    project_dir: str | Path,
    *,
    edge_ref: str,
    expected_status: str,
    expected_edge_sha256: str,
    decision: str,
    actor: str,
    operation_id: str,
    timestamp: str,
    evidence_refs: list[str] | None = None,
    note: str | None = None,
    fault_at: str | None = None,
) -> dict[str, Any]:
    """作者确认、退役或暂缓一条因果边；不创建长期 action 对象。"""
    if actor != "author":
        raise FactstoreError("FACT_CAUSAL_EDGE_REVIEW_AUTHOR_REQUIRED")
    if not isinstance(edge_ref, str) or CAUSAL_EDGE_ID_RE.fullmatch(edge_ref) is None:
        raise FactstoreError("FACT_CAUSAL_EDGE_REVIEW_REF_INVALID")
    if expected_status not in CAUSAL_EDGE_STATUSES:
        raise FactstoreError("FACT_CAUSAL_EDGE_REVIEW_EXPECTED_STATUS_INVALID")
    if (
        not isinstance(expected_edge_sha256, str)
        or planstore.SHA256_RE.fullmatch(expected_edge_sha256) is None
    ):
        raise FactstoreError("FACT_CAUSAL_EDGE_REVIEW_EXPECTED_SHA_INVALID")
    if decision not in CAUSAL_EDGE_REVIEW_DECISIONS:
        raise FactstoreError("FACT_CAUSAL_EDGE_REVIEW_DECISION_INVALID")
    if evidence_refs is not None and not isinstance(evidence_refs, list):
        raise FactstoreError("FACT_CAUSAL_EDGE_REVIEW_EVIDENCE_INVALID")
    if note is not None and not isinstance(note, str):
        raise FactstoreError("FACT_CAUSAL_EDGE_REVIEW_NOTE_INVALID")
    if decision in {"retire", "defer"} and evidence_refs is not None:
        raise FactstoreError("FACT_CAUSAL_EDGE_REVIEW_EVIDENCE_FORBIDDEN")
    if decision == "defer" and note not in {None, ""}:
        raise FactstoreError("FACT_CAUSAL_EDGE_DEFER_PAYLOAD_FORBIDDEN")
    if fault_at is not None and fault_at not in FAULT_POINTS:
        raise FactstoreError("UNKNOWN_FACT_CAUSAL_EDGE_FAULT_POINT")
    planstore._validate_operation_id(operation_id)
    _parse_causal_edge_timestamp(timestamp, "CAUSAL_EDGE_TIMESTAMP")
    request_sha = planstore._sha256_json(
        {
            "edge_ref": edge_ref,
            "expected_status": expected_status,
            "expected_edge_sha256": expected_edge_sha256,
            "decision": decision,
            "actor": actor,
            "operation_id": operation_id,
            "timestamp": timestamp,
            "evidence_refs": evidence_refs,
            "note": note,
        }
    )
    root = Path(project_dir)
    with planstore._exclusive_lock(root):
        planstore._recover_pending_locked(root, timestamp=timestamp)
        status = planstore._operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            if status["request_sha256"] != request_sha:
                raise FactstoreError("OPERATION_ID_PAYLOAD_CONFLICT")
            return _replayed_receipt(root, operation_id)
        if status["terminal_phase"] == "rolled_back":
            raise FactstoreError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        if status["state"] == "NEEDS_MANUAL_RECOVERY":
            raise FactstoreError("OPERATION_NEEDS_MANUAL_RECOVERY")

        edges_before = _load_fact_causal_edges(root)
        matches = [item for item in edges_before if item["id"] == edge_ref]
        if len(matches) != 1:
            raise FactstoreError("FACT_CAUSAL_EDGE_REVIEW_TARGET_NOT_FOUND")
        edge_before = matches[0]
        if (
            edge_before["confirm_status"] != expected_status
            or fact_causal_edge_sha256(edge_before) != expected_edge_sha256
        ):
            raise FactstoreError("STALE_FACT_CAUSAL_EDGE_REVISION")
        if decision == "defer":
            return {
                "operation_id": operation_id,
                "status": "NO_CHANGE",
                "decision": "defer",
                "edge_ref": edge_ref,
                "confirm_status": edge_before["confirm_status"],
                "rev": edge_before["rev"],
                "edge_sha256": fact_causal_edge_sha256(edge_before),
                "story_commit_seq": planstore._latest_committed_story_seq(root),
                "replayed": False,
            }

        if decision == "confirm" and edge_before["confirm_status"] != "candidate":
            raise FactstoreError("FACT_CAUSAL_EDGE_CONFIRM_TRANSITION_INVALID")
        if decision == "retire" and edge_before["confirm_status"] == "retired":
            raise FactstoreError("FACT_CAUSAL_EDGE_RETIRE_TRANSITION_INVALID")

        edge_after = copy.deepcopy(edge_before)
        if decision == "confirm":
            if evidence_refs is not None:
                edge_after["evidence_refs"] = copy.deepcopy(evidence_refs)
            edge_after["confirm_status"] = "confirmed"
        else:
            edge_after["confirm_status"] = "retired"
        if note is not None:
            edge_after["note"] = note
        edge_after["updated_at"] = timestamp
        edge_after["rev"] += 1
        edge_after = validate_fact_causal_edge_record(edge_after)

        facts = _validate_facts(planstore._read_json(root / "facts.json"))
        _validate_causal_edge_fact_refs(
            edge_after,
            {item["id"]: item for item in facts},
            require_confirmed_endpoints=decision == "confirm",
        )
        edges_after = [
            edge_after if item["id"] == edge_ref else item for item in edges_before
        ]
        row, blob = _causal_edge_history_row(
            operation_id=operation_id,
            actor="author",
            action_name="fact_causal_edge_review",
            before=edge_before,
            after=edge_after,
            timestamp=timestamp,
        )
        return _commit_fact_causal_edges_locked(
            root,
            operation_id=operation_id,
            action_name="fact_causal_edge_review",
            request_sha256=request_sha,
            edges_after=edges_after,
            history_rows=[row],
            blobs=[blob],
            receipt={
                "operation_id": operation_id,
                "status": "COMMITTED",
                "decision": decision,
                "edge_ref": edge_ref,
                "before_status": edge_before["confirm_status"],
                "after_status": edge_after["confirm_status"],
                "before_edge_sha256": fact_causal_edge_sha256(edge_before),
                "after_edge_sha256": fact_causal_edge_sha256(edge_after),
                "rev": edge_after["rev"],
                "fact_causal_edge_writes": 1,
            },
            timestamp=timestamp,
            fault_at=fault_at,
        )


def add_fact_candidates(
    project_dir: str | Path,
    *,
    chapter_id: str,
    items: list[dict[str, Any]],
    source: str,
    timestamp: str,
    operation_id: str | None = None,
) -> dict[str, Any]:
    """C3 候选仍只进 extracted，但与 M5 共用文件锁和恢复事务。"""
    if not isinstance(items, list) or not isinstance(source, str):
        raise FactstoreError("FACT_CANDIDATE_INPUT_INVALID")
    root = Path(project_dir)
    operation_id = operation_id or new_operation_id("op-m4-candidates")
    planstore._validate_operation_id(operation_id)
    valid = [
        item
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("text"), str)
        and item["text"].strip()
    ]
    request_sha = planstore._sha256_json(
        {
            "chapter_id": chapter_id,
            "items": valid,
            "source": source,
            "timestamp": timestamp,
        }
    )
    with planstore._exclusive_lock(root):
        planstore._recover_pending_locked(root, timestamp=timestamp)
        status = planstore._operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            if status["request_sha256"] != request_sha:
                raise FactstoreError("OPERATION_ID_PAYLOAD_CONFLICT")
            return _replayed_receipt(root, operation_id)
        if status["terminal_phase"] == "rolled_back":
            raise FactstoreError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        if status["state"] == "NEEDS_MANUAL_RECOVERY":
            raise FactstoreError("OPERATION_NEEDS_MANUAL_RECOVERY")
        chapters = planstore._read_json(root / "chapters.json")
        if not isinstance(chapters, list) or chapter_id not in {
            item.get("id") for item in chapters if isinstance(item, dict)
        }:
            raise FactstoreError("FACT_CANDIDATE_CHAPTER_NOT_FOUND")
        facts_before = _validate_facts(planstore._read_json(root / "facts.json"))
        new_ids = allocate_fact_ids(facts_before, len(valid))
        new_records = []
        for item, fact_ref in zip(valid, new_ids):
            record = {
                "id": fact_ref,
                "chapter_id": chapter_id,
                "text": item["text"].strip(),
                "quote": str(item.get("quote") or "").strip(),
                "status": STATUS_EXTRACTED,
                "source": source,
                "note": "",
                "added_at": timestamp,
            }
            if item.get("seg"):
                record["seg"] = item["seg"]
            new_records.append(record)
        facts_after = [*copy.deepcopy(facts_before), *new_records]
        receipt = {
            "operation_id": operation_id,
            "status": "COMMITTED",
            "chapter_id": chapter_id,
            "candidate_count": len(new_records),
            "new_f_ids": new_ids,
            "confirmed_writes": 0,
            "actual_changes": 0,
        }
        return commit_facts_transaction_locked(
            root,
            operation_id=operation_id,
            action_name="fact_candidates_add",
            request_sha256=request_sha,
            facts_after=facts_after,
            plan_after=None,
            history_rows=[],
            blobs=[],
            receipt=receipt,
            timestamp=timestamp,
        )


def _contains_reference(value: Any, refs: set[str]) -> bool:
    if isinstance(value, dict):
        return any(_contains_reference(item, refs) for item in value.values())
    if isinstance(value, list):
        return any(_contains_reference(item, refs) for item in value)
    return isinstance(value, str) and value in refs


def repair_duplicate_fact_ids(
    project_dir: str | Path,
    *,
    timestamp: str,
    operation_id: str | None = None,
) -> dict[str, Any]:
    """旧坏账修号也走事务；被规划账引用的重复号因归属不明而失败关闭。"""
    root = Path(project_dir)
    operation_id = operation_id or new_operation_id("op-m4-repair-ids")
    planstore._validate_operation_id(operation_id)
    with planstore._exclusive_lock(root):
        planstore._recover_pending_locked(root, timestamp=timestamp)
        status = planstore._operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            return _replayed_receipt(root, operation_id)
        if status["terminal_phase"] == "rolled_back":
            raise FactstoreError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        if status["state"] == "NEEDS_MANUAL_RECOVERY":
            raise FactstoreError("OPERATION_NEEDS_MANUAL_RECOVERY")
        raw = planstore._read_json(root / "facts.json")
        if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
            raise FactstoreError("C4_FACTS_NOT_LIST")
        seen: set[str] = set()
        latecomers = []
        for item in raw:
            fact_ref = item.get("id")
            if not isinstance(fact_ref, str) or FACT_ID_RE.fullmatch(fact_ref) is None:
                raise FactstoreError("C4_FACT_ID_INVALID")
            if item.get("status") not in FACT_STATUSES:
                raise FactstoreError("C4_FACT_STATUS_INVALID")
            if fact_ref in seen:
                latecomers.append(item)
            else:
                seen.add(fact_ref)
        if not latecomers:
            return {"total": len(raw), "remap": [], "status": "NO_CHANGES"}
        duplicate_refs = {item["id"] for item in latecomers}
        if (root / "plan.json").exists():
            plan = planstore._read_json(root / "plan.json")
            planstore._validate_plan(plan)
            if _contains_reference(plan, duplicate_refs):
                raise FactstoreError("DUPLICATE_FACT_REF_REFERENCED_REPAIR_AMBIGUOUS")
        facts_after = copy.deepcopy(raw)
        new_ids = allocate_fact_ids(facts_after, len(latecomers))
        remap = []
        late_indexes = []
        seen.clear()
        for index, item in enumerate(facts_after):
            if item["id"] in seen:
                late_indexes.append(index)
            else:
                seen.add(item["id"])
        for index, new_id in zip(late_indexes, new_ids):
            item = facts_after[index]
            remap.append(
                {
                    "old": item["id"],
                    "new": new_id,
                    "chapter_id": item.get("chapter_id"),
                    "seg": item.get("seg"),
                    "text": str(item.get("text", ""))[:40],
                }
            )
            item["id_remapped_from"] = item["id"]
            item["id"] = new_id
        report = {"repaired_at": timestamp, "total": len(facts_after), "remap": remap}
        request_sha = planstore._sha256_json(
            {"operation_id": operation_id, "duplicate_refs": sorted(duplicate_refs)}
        )
        return commit_facts_transaction_locked(
            root,
            operation_id=operation_id,
            action_name="fact_id_repair",
            request_sha256=request_sha,
            facts_after=facts_after,
            plan_after=None,
            history_rows=[],
            blobs=[],
            receipt={**report, "operation_id": operation_id, "status": "COMMITTED"},
            timestamp=timestamp,
            extra_replacements={
                "repair_ids_report.json": planstore._canonical_bytes(report)
            },
        )


def review_fact(
    project_dir: str | Path,
    *,
    action: dict[str, Any],
    timestamp: str,
    fault_at: str | None = None,
) -> dict[str, Any]:
    """确认、驳回、改判或改写一个现有 C4 条目。"""
    if fault_at is not None and fault_at not in FAULT_POINTS:
        raise FactstoreError("UNKNOWN_FACT_REVIEW_FAULT_POINT")
    _validate_review_action(action)
    root = Path(project_dir)
    operation_id = action["operation_id"]
    request_sha = planstore._sha256_json(action)
    with planstore._exclusive_lock(root):
        planstore._recover_pending_locked(root, timestamp=timestamp)
        status = planstore._operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            if status["request_sha256"] != request_sha:
                raise FactstoreError("OPERATION_ID_PAYLOAD_CONFLICT")
            return _replayed_receipt(root, operation_id)
        if status["terminal_phase"] == "rolled_back":
            raise FactstoreError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        if status["state"] == "NEEDS_MANUAL_RECOVERY":
            raise FactstoreError("OPERATION_NEEDS_MANUAL_RECOVERY")

        facts_before = _validate_facts(planstore._read_json(root / "facts.json"))
        matches = [item for item in facts_before if item["id"] == action["fact_ref"]]
        if len(matches) != 1:
            raise FactstoreError("FACT_REVIEW_TARGET_NOT_FOUND")
        fact_before = matches[0]
        if (
            fact_before["status"] != action["expected_status"]
            or fact_sha256(fact_before) != action["expected_fact_sha256"]
        ):
            raise FactstoreError("STALE_FACT_REVISION")

        facts_after = copy.deepcopy(facts_before)
        fact_after = next(
            item for item in facts_after if item["id"] == action["fact_ref"]
        )
        before_status = fact_after["status"]
        before_sha = fact_sha256(fact_after)
        decision = action["decision"]
        if decision == "confirm":
            fact_after["status"] = STATUS_CONFIRMED
        elif decision == "reject":
            fact_after["status"] = STATUS_REJECTED
        elif decision in {"edit", "edit_and_confirm"}:
            old_text = str(fact_after.get("text", ""))
            fact_after["text"] = action["replacement_text"].strip()
            fact_after["note"] = action["note"] or f"原文候选：{old_text}"
            if decision == "edit_and_confirm":
                fact_after["status"] = STATUS_CONFIRMED
        if action["note"] and decision not in {"edit", "edit_and_confirm"}:
            fact_after["note"] = action["note"]
        if decision in {"confirm", "reject", "edit_and_confirm"}:
            fact_after["decided_at"] = timestamp

        plan_after = None
        history_rows: list[dict[str, Any]] = []
        blobs: list[dict[str, Any]] = []
        stale_edge_refs: list[str] = []
        plan_path = root / "plan.json"
        if plan_path.exists():
            plan_after = copy.deepcopy(planstore._read_json(plan_path))
            planstore._validate_plan(plan_after)
            for edge in plan_after["reconciliation_edges"]:
                if (
                    edge["edge_status"] != "active"
                    or action["fact_ref"] not in edge["actual_fact_refs"]
                ):
                    continue
                edge_before = copy.deepcopy(edge)
                edge["edge_status"] = "stale"
                edge["rev"] += 1
                row, blob = _history_row(
                    operation_id=operation_id,
                    before=edge_before,
                    after=edge,
                    timestamp=timestamp,
                    note="M5 事实状态或文本改变，旧 actual support 失效",
                )
                history_rows.append(row)
                blobs.append(blob)
                stale_edge_refs.append(edge["id"])

        receipt = {
            "operation_id": operation_id,
            "status": "COMMITTED",
            "fact_ref": action["fact_ref"],
            "decision": decision,
            "before_status": before_status,
            "after_status": fact_after["status"],
            "before_fact_sha256": before_sha,
            "after_fact_sha256": fact_sha256(fact_after),
            "stale_edge_refs": stale_edge_refs,
            "facts_writes": 1,
            "plan_writes": 1 if stale_edge_refs else 0,
            "actual_support_invalidated": len(stale_edge_refs),
            "stored_actual_fields": 0,
        }
        return commit_facts_transaction_locked(
            root,
            operation_id=operation_id,
            action_name="fact_review",
            request_sha256=request_sha,
            facts_after=facts_after,
            plan_after=plan_after if stale_edge_refs else None,
            history_rows=history_rows,
            blobs=blobs,
            receipt=receipt,
            timestamp=timestamp,
            fault_at=fault_at,
        )
