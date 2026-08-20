"""M9 最小事实概览原型：C4 v1 快照对象 -> 只读章概览投影。

本模块只处理内存对象，不读取路径、项目或事实账。``overview_provider`` 是
唯一的模型供应器替换缝；调用者可以像本票一样传入冻结离线映射适配器。

作者卡只收录已确认事实。provider 只负责给 confirmed refs 分组、排序和选
orphan；它返回的自由文字不会进入梗概、事件点或视觉提示。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable
from typing import Any


OUTPUT_CONTRACT = "C5_OVERVIEW_CARD_PROTOTYPE"
OUTPUT_VERSION = "v0"
MODEL_PROVIDER_SWAP_POINT = "MODEL_PROVIDER_SWAP_POINT"
COORDINATE_BASIS = "CHAPTER_REVISION_TEXT_UNICODE_CODEPOINT_0_BASED_HALF_OPEN"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUEST_KEYS = frozenset(
    {"facts", "current_revision_ref", "source_revision", "generated_at"}
)
REVISION_REF_KEYS = frozenset(
    {"chapter_id", "revision_no", "revision_text_sha256"}
)
ANCHOR_REF_KEYS = frozenset(
    {
        "chapter_id",
        "revision_no",
        "revision_text_sha256",
        "coordinate_basis",
        "start",
        "end",
        "slice_sha256",
    }
)
C4_REQUIRED_KEYS = frozenset(
    {
        "contract",
        "version",
        "id",
        "chapter_id",
        "text",
        "quote",
        "status",
        "source",
        "note",
        "added_at",
        "chapter_revision_ref",
        "anchor_ref",
        "anchor_state",
        "recheck",
    }
)
C4_OPTIONAL_KEYS = frozenset({"seg", "decided_at"})
CURRENT_FACT_STATUSES = frozenset({"extracted", "confirmed", "rejected"})
AUTHOR_CARD_FACT_STATUS = "confirmed"
PROVIDER_RESULT_KEYS = frozenset(
    {"synopsis", "beats", "visual_hint", "orphan_refs"}
)
PROVIDER_BEAT_KEYS = frozenset({"text", "fact_refs", "visual_hint"})
CARD_KEYS = frozenset(
    {
        "contract",
        "version",
        "projection_only",
        "writes_truth",
        "basis",
        "card_id",
        "chapter_ref",
        "chapter_revision_ref",
        "synopsis",
        "beats",
        "orphan_refs",
        "visual_hint",
        "coverage",
        "source_summary",
        "evidence",
        "generated_at",
    }
)
CARD_BEAT_KEYS = frozenset({"beat_id", "text", "fact_refs", "visual_hint"})
COVERAGE_KEYS = frozenset(
    {
        "fact_count",
        "beat_ref_count",
        "orphan_count",
        "covered_fact_count",
        "coverage_ratio",
    }
)
SOURCE_SUMMARY_KEYS = frozenset(
    {
        "source_revision",
        "source_facts_sha256",
        "chapter_revision_ref",
        "fact_count",
        "status_counts",
        "fact_refs",
    }
)
SOURCE_FACT_REF_KEYS = frozenset({"fact_id", "status", "record_sha256"})
EVIDENCE_KEYS = frozenset(
    {
        "fact_id",
        "status",
        "source",
        "quote",
        "chapter_revision_ref",
        "anchor_ref",
    }
)


class OverviewError(ValueError):
    """输入或供应器输出不能组成完整、可追溯的原型概览。"""


OverviewProvider = Callable[[dict[str, Any]], dict[str, Any]]


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_int(value: object, *, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _valid_revision_ref(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == REVISION_REF_KEYS
        and isinstance(value.get("chapter_id"), str)
        and bool(value["chapter_id"])
        and _is_int(value.get("revision_no"), minimum=1)
        and _is_sha256(value.get("revision_text_sha256"))
    )


def _require_clean_string(value: object, *, reason: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or value != value.strip() or (not allow_empty and not value):
        raise OverviewError(reason)
    return value


def _validate_fact(
    value: object,
    *,
    current_revision_ref: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OverviewError(f"C4_FACT_NOT_OBJECT:{index}")
    missing = sorted(C4_REQUIRED_KEYS - value.keys())
    extra = sorted(value.keys() - C4_REQUIRED_KEYS - C4_OPTIONAL_KEYS)
    if missing:
        raise OverviewError(f"C4_FACT_MISSING_FIELDS:{index}:{','.join(missing)}")
    if extra:
        raise OverviewError(f"C4_FACT_EXTRA_FIELDS:{index}:{','.join(extra)}")
    if value["contract"] != "C4_FACT_QUERY" or value["version"] != "v1":
        raise OverviewError(f"C4_FACT_IDENTITY_INVALID:{index}")

    fact_id = _require_clean_string(value["id"], reason=f"C4_FACT_ID_INVALID:{index}")
    chapter_id = _require_clean_string(
        value["chapter_id"], reason=f"C4_CHAPTER_ID_INVALID:{fact_id}"
    )
    _require_clean_string(value["text"], reason=f"C4_TEXT_INVALID:{fact_id}")
    quote = _require_clean_string(value["quote"], reason=f"C4_QUOTE_INVALID:{fact_id}")
    _require_clean_string(value["source"], reason=f"C4_SOURCE_INVALID:{fact_id}")
    _require_clean_string(
        value["note"], reason=f"C4_NOTE_INVALID:{fact_id}", allow_empty=True
    )
    _require_clean_string(value["added_at"], reason=f"C4_ADDED_AT_INVALID:{fact_id}")
    if "decided_at" in value:
        _require_clean_string(
            value["decided_at"], reason=f"C4_DECIDED_AT_INVALID:{fact_id}"
        )
    if "seg" in value and not _is_int(value["seg"], minimum=1):
        raise OverviewError(f"C4_SEG_INVALID:{fact_id}")

    status = value["status"]
    if status not in CURRENT_FACT_STATUSES:
        raise OverviewError(f"C4_STATUS_NOT_CURRENT_OVERVIEW_INPUT:{fact_id}:{status}")
    if chapter_id != current_revision_ref["chapter_id"]:
        raise OverviewError(f"C4_MIXED_CHAPTER:{fact_id}")
    revision_ref = value["chapter_revision_ref"]
    if not _valid_revision_ref(revision_ref):
        raise OverviewError(f"C4_REVISION_REF_INVALID:{fact_id}")
    if revision_ref != current_revision_ref:
        raise OverviewError(f"C4_STALE_REVISION:{fact_id}")
    if value["anchor_state"] != "VERIFIED" or value["recheck"] is not None:
        raise OverviewError(f"C4_EVIDENCE_NOT_CURRENT_VERIFIED:{fact_id}")

    anchor = value["anchor_ref"]
    if not isinstance(anchor, dict) or set(anchor) != ANCHOR_REF_KEYS:
        raise OverviewError(f"C4_ANCHOR_SHAPE_INVALID:{fact_id}")
    if any(anchor[key] != current_revision_ref[key] for key in REVISION_REF_KEYS):
        raise OverviewError(f"C4_ANCHOR_REVISION_MISMATCH:{fact_id}")
    start = anchor["start"]
    end = anchor["end"]
    if (
        anchor["coordinate_basis"] != COORDINATE_BASIS
        or not _is_int(start, minimum=0)
        or not _is_int(end, minimum=1)
        or start >= end
        or end - start != len(quote)
        or not _is_sha256(anchor["slice_sha256"])
        or hashlib.sha256(quote.encode("utf-8")).hexdigest() != anchor["slice_sha256"]
    ):
        raise OverviewError(f"C4_ANCHOR_QUOTE_INVALID:{fact_id}")
    return value


def _validate_request(
    request: object,
) -> tuple[list[dict[str, Any]], dict[str, Any], str, str, str]:
    if not isinstance(request, dict):
        raise OverviewError("REQUEST_NOT_OBJECT")
    missing = sorted(REQUEST_KEYS - request.keys())
    extra = sorted(request.keys() - REQUEST_KEYS)
    if missing:
        raise OverviewError(f"REQUEST_MISSING_FIELDS:{','.join(missing)}")
    if extra:
        raise OverviewError(f"REQUEST_EXTRA_FIELDS:{','.join(extra)}")

    current_revision_ref = request["current_revision_ref"]
    if not _valid_revision_ref(current_revision_ref):
        raise OverviewError("CURRENT_REVISION_REF_INVALID")
    source_revision = _require_clean_string(
        request["source_revision"], reason="SOURCE_REVISION_INVALID"
    )
    generated_at = _require_clean_string(
        request["generated_at"], reason="GENERATED_AT_INVALID"
    )
    raw_facts = request["facts"]
    if not isinstance(raw_facts, list) or not raw_facts:
        raise OverviewError("FACTS_MUST_BE_NONEMPTY_LIST")

    facts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_fact in enumerate(raw_facts, start=1):
        fact = _validate_fact(
            raw_fact,
            current_revision_ref=current_revision_ref,
            index=index,
        )
        fact_id = fact["id"]
        if fact_id in seen_ids:
            raise OverviewError(f"DUPLICATE_C4_FACT_ID:{fact_id}")
        seen_ids.add(fact_id)
        facts.append(fact)
    facts_sha256 = _canonical_sha256(facts)
    return facts, current_revision_ref, source_revision, generated_at, facts_sha256


def _provider_key(*, current_revision_ref: dict[str, Any], facts_sha256: str) -> str:
    return (
        f"{current_revision_ref['chapter_id']}:"
        f"r{current_revision_ref['revision_no']}:"
        f"{facts_sha256}"
    )


def provider_key_for_request(request: dict[str, Any]) -> str:
    """返回冻结离线 responses 映射所用的稳定键。"""
    _, current_revision_ref, _, _, facts_sha256 = _validate_request(request)
    return _provider_key(
        current_revision_ref=current_revision_ref,
        facts_sha256=facts_sha256,
    )


def _confirmed_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [fact for fact in facts if fact["status"] == AUTHOR_CARD_FACT_STATUS]


def _join_confirmed_texts(
    facts_by_id: dict[str, dict[str, Any]], refs: list[str]
) -> str:
    return "".join(facts_by_id[ref]["text"] for ref in refs)


def _validate_provider_result(
    value: object,
    *,
    confirmed_ids: set[str],
    snapshot_ids: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, dict):
        raise OverviewError("PROVIDER_RESULT_NOT_OBJECT")
    missing = sorted(PROVIDER_RESULT_KEYS - value.keys())
    extra = sorted(value.keys() - PROVIDER_RESULT_KEYS)
    if missing:
        raise OverviewError(f"PROVIDER_RESULT_MISSING_FIELDS:{','.join(missing)}")
    if extra:
        raise OverviewError(f"PROVIDER_RESULT_EXTRA_FIELDS:{','.join(extra)}")

    _require_clean_string(value["synopsis"], reason="SYNOPSIS_INVALID")
    _require_clean_string(
        value["visual_hint"], reason="VISUAL_HINT_INVALID", allow_empty=True
    )
    raw_beats = value["beats"]
    orphan_refs = value["orphan_refs"]
    if not isinstance(raw_beats, list):
        raise OverviewError("BEATS_NOT_LIST")
    if not isinstance(orphan_refs, list):
        raise OverviewError("ORPHAN_REFS_NOT_LIST")

    references: list[str] = []
    beats: list[dict[str, Any]] = []
    for index, raw_beat in enumerate(raw_beats, start=1):
        if not isinstance(raw_beat, dict) or set(raw_beat) != PROVIDER_BEAT_KEYS:
            raise OverviewError(f"BEAT_SHAPE_INVALID:{index}")
        _require_clean_string(raw_beat["text"], reason=f"BEAT_TEXT_INVALID:{index}")
        _require_clean_string(
            raw_beat["visual_hint"],
            reason=f"BEAT_VISUAL_HINT_INVALID:{index}",
            allow_empty=True,
        )
        fact_refs = raw_beat["fact_refs"]
        if not isinstance(fact_refs, list) or not fact_refs:
            raise OverviewError(f"BEAT_FACT_REFS_MUST_BE_NONEMPTY_LIST:{index}")
        if any(not isinstance(ref, str) or not ref for ref in fact_refs):
            raise OverviewError(f"BEAT_FACT_REF_INVALID:{index}")
        references.extend(fact_refs)
        beats.append(
            {
                "beat_id": f"b{index:02d}",
                "fact_refs": list(fact_refs),
            }
        )

    if any(not isinstance(ref, str) or not ref for ref in orphan_refs):
        raise OverviewError("ORPHAN_REF_INVALID")
    references.extend(orphan_refs)
    unknown = sorted(set(references) - snapshot_ids)
    if unknown:
        raise OverviewError(f"UNKNOWN_FACT_REFS:{','.join(unknown)}")
    non_confirmed = sorted(set(references) - confirmed_ids)
    if non_confirmed:
        raise OverviewError(f"NON_CONFIRMED_FACT_REFS:{','.join(non_confirmed)}")
    duplicates = sorted(ref for ref, count in Counter(references).items() if count > 1)
    if duplicates:
        raise OverviewError(f"DUPLICATE_FACT_REFS:{','.join(duplicates)}")
    missing_refs = sorted(confirmed_ids - set(references))
    if missing_refs:
        raise OverviewError(f"UNCOVERED_FACT_REFS:{','.join(missing_refs)}")
    return beats, list(orphan_refs)


def execute(request: dict[str, Any], overview_provider: OverviewProvider) -> dict[str, Any]:
    """把一章 current C4 v1 快照投影成一张仅含已确认事实的原型概览卡。"""
    if not callable(overview_provider):
        raise OverviewError("OVERVIEW_PROVIDER_NOT_CALLABLE")
    facts, current_ref, source_revision, generated_at, facts_sha256 = _validate_request(
        request
    )
    confirmed = _confirmed_facts(facts)
    if not confirmed:
        raise OverviewError("NO_CONFIRMED_FACTS")
    confirmed_ids = {fact["id"] for fact in confirmed}
    snapshot_ids = {fact["id"] for fact in facts}
    provider_request = {
        "provider_key": _provider_key(
            current_revision_ref=current_ref,
            facts_sha256=facts_sha256,
        ),
        "provider_swap_point": MODEL_PROVIDER_SWAP_POINT,
        "basis": "fact_snapshot",
        "projection_only": True,
        "writes_truth": False,
        "current_revision_ref": copy.deepcopy(current_ref),
        "source_facts_sha256": facts_sha256,
        "facts": copy.deepcopy(confirmed),
    }
    provider_result = overview_provider(provider_request)
    provider_beats, orphan_refs = _validate_provider_result(
        provider_result,
        confirmed_ids=confirmed_ids,
        snapshot_ids=snapshot_ids,
    )

    facts_by_id = {fact["id"]: fact for fact in confirmed}
    ordered_refs: list[str] = []
    beats: list[dict[str, Any]] = []
    for provider_beat in provider_beats:
        fact_refs = provider_beat["fact_refs"]
        ordered_refs.extend(fact_refs)
        beats.append(
            {
                "beat_id": provider_beat["beat_id"],
                "text": _join_confirmed_texts(facts_by_id, fact_refs),
                "fact_refs": list(fact_refs),
                "visual_hint": "",
            }
        )
    ordered_refs.extend(orphan_refs)
    synopsis = _join_confirmed_texts(facts_by_id, ordered_refs)

    source_fact_refs = [
        {
            "fact_id": fact["id"],
            "status": fact["status"],
            "record_sha256": _canonical_sha256(fact),
        }
        for fact in confirmed
    ]
    evidence = [
        {
            "fact_id": fact["id"],
            "status": fact["status"],
            "source": fact["source"],
            "quote": fact["quote"],
            "chapter_revision_ref": copy.deepcopy(fact["chapter_revision_ref"]),
            "anchor_ref": copy.deepcopy(fact["anchor_ref"]),
        }
        for fact in confirmed
    ]
    beat_ref_count = sum(len(beat["fact_refs"]) for beat in beats)
    return {
        "contract": OUTPUT_CONTRACT,
        "version": OUTPUT_VERSION,
        "projection_only": True,
        "writes_truth": False,
        "basis": "fact_snapshot",
        "card_id": (
            f"prototype:{current_ref['chapter_id']}:"
            f"r{current_ref['revision_no']}:{facts_sha256[:12]}"
        ),
        "chapter_ref": current_ref["chapter_id"],
        "chapter_revision_ref": copy.deepcopy(current_ref),
        "synopsis": synopsis,
        "beats": beats,
        "orphan_refs": orphan_refs,
        "visual_hint": "",
        "coverage": {
            "fact_count": len(confirmed),
            "beat_ref_count": beat_ref_count,
            "orphan_count": len(orphan_refs),
            "covered_fact_count": beat_ref_count + len(orphan_refs),
            "coverage_ratio": 1.0,
        },
        "source_summary": {
            "source_revision": source_revision,
            "source_facts_sha256": facts_sha256,
            "chapter_revision_ref": copy.deepcopy(current_ref),
            "fact_count": len(confirmed),
            "status_counts": dict(
                sorted(Counter(fact["status"] for fact in confirmed).items())
            ),
            "fact_refs": source_fact_refs,
        },
        "evidence": evidence,
        "generated_at": generated_at,
    }


def _validate_card_evidence(
    value: object,
    *,
    current_revision_ref: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != EVIDENCE_KEYS:
        raise OverviewError(f"CARD_EVIDENCE_SHAPE_INVALID:{index}")
    fact_id = _require_clean_string(
        value["fact_id"], reason=f"CARD_EVIDENCE_FACT_ID_INVALID:{index}"
    )
    if value["status"] != AUTHOR_CARD_FACT_STATUS:
        raise OverviewError(f"CARD_EVIDENCE_STATUS_NOT_CONFIRMED:{fact_id}")
    _require_clean_string(
        value["source"], reason=f"CARD_EVIDENCE_SOURCE_INVALID:{fact_id}"
    )
    quote = _require_clean_string(
        value["quote"], reason=f"CARD_EVIDENCE_QUOTE_INVALID:{fact_id}"
    )
    if value["chapter_revision_ref"] != current_revision_ref:
        raise OverviewError(f"CARD_EVIDENCE_REVISION_MISMATCH:{fact_id}")
    anchor = value["anchor_ref"]
    if not isinstance(anchor, dict) or set(anchor) != ANCHOR_REF_KEYS:
        raise OverviewError(f"CARD_EVIDENCE_ANCHOR_SHAPE_INVALID:{fact_id}")
    if any(anchor[key] != current_revision_ref[key] for key in REVISION_REF_KEYS):
        raise OverviewError(f"CARD_EVIDENCE_ANCHOR_REVISION_MISMATCH:{fact_id}")
    start = anchor["start"]
    end = anchor["end"]
    if (
        anchor["coordinate_basis"] != COORDINATE_BASIS
        or not _is_int(start, minimum=0)
        or not _is_int(end, minimum=1)
        or start >= end
        or end - start != len(quote)
        or not _is_sha256(anchor["slice_sha256"])
        or hashlib.sha256(quote.encode("utf-8")).hexdigest()
        != anchor["slice_sha256"]
    ):
        raise OverviewError(f"CARD_EVIDENCE_ANCHOR_QUOTE_INVALID:{fact_id}")
    return value


def validate_card(value: object) -> dict[str, Any]:
    """严格校验一张现役 M9 prototype 卡，不调用 provider。"""
    if not isinstance(value, dict) or set(value) != CARD_KEYS:
        raise OverviewError("CARD_SHAPE_INVALID")
    if (
        value["contract"] != OUTPUT_CONTRACT
        or value["version"] != OUTPUT_VERSION
        or value["projection_only"] is not True
        or value["writes_truth"] is not False
        or value["basis"] != "fact_snapshot"
    ):
        raise OverviewError("CARD_IDENTITY_INVALID")

    current_ref = value["chapter_revision_ref"]
    if not _valid_revision_ref(current_ref):
        raise OverviewError("CARD_CHAPTER_REVISION_REF_INVALID")
    chapter_id = _require_clean_string(
        value["chapter_ref"], reason="CARD_CHAPTER_REF_INVALID"
    )
    if chapter_id != current_ref["chapter_id"]:
        raise OverviewError("CARD_CHAPTER_IDENTITY_MISMATCH")
    synopsis = _require_clean_string(value["synopsis"], reason="CARD_SYNOPSIS_INVALID")
    _require_clean_string(
        value["visual_hint"], reason="CARD_VISUAL_HINT_INVALID", allow_empty=True
    )
    generated_at = _require_clean_string(
        value["generated_at"], reason="CARD_GENERATED_AT_INVALID"
    )

    raw_evidence = value["evidence"]
    if not isinstance(raw_evidence, list) or not raw_evidence:
        raise OverviewError("CARD_EVIDENCE_MUST_BE_NONEMPTY_LIST")
    evidence: list[dict[str, Any]] = []
    evidence_by_id: dict[str, dict[str, Any]] = {}
    for index, raw_item in enumerate(raw_evidence, start=1):
        item = _validate_card_evidence(
            raw_item,
            current_revision_ref=current_ref,
            index=index,
        )
        fact_id = item["fact_id"]
        if fact_id in evidence_by_id:
            raise OverviewError(f"CARD_EVIDENCE_FACT_ID_DUPLICATE:{fact_id}")
        evidence_by_id[fact_id] = item
        evidence.append(item)

    source_summary = value["source_summary"]
    if not isinstance(source_summary, dict) or set(source_summary) != SOURCE_SUMMARY_KEYS:
        raise OverviewError("CARD_SOURCE_SUMMARY_SHAPE_INVALID")
    source_revision = _require_clean_string(
        source_summary["source_revision"],
        reason="CARD_SOURCE_REVISION_INVALID",
    )
    source_facts_sha256 = source_summary["source_facts_sha256"]
    if not _is_sha256(source_facts_sha256):
        raise OverviewError("CARD_SOURCE_FACTS_SHA256_INVALID")
    if source_summary["chapter_revision_ref"] != current_ref:
        raise OverviewError("CARD_SOURCE_REVISION_REF_MISMATCH")
    if (
        not _is_int(source_summary["fact_count"], minimum=1)
        or source_summary["fact_count"] != len(evidence)
    ):
        raise OverviewError("CARD_SOURCE_FACT_COUNT_MISMATCH")
    expected_status_counts = dict(
        sorted(Counter(item["status"] for item in evidence).items())
    )
    if source_summary["status_counts"] != expected_status_counts:
        raise OverviewError("CARD_STATUS_COUNTS_MISMATCH")

    raw_source_refs = source_summary["fact_refs"]
    if not isinstance(raw_source_refs, list):
        raise OverviewError("CARD_SOURCE_FACT_REFS_NOT_LIST")
    source_ref_ids: set[str] = set()
    for index, raw_ref in enumerate(raw_source_refs, start=1):
        if not isinstance(raw_ref, dict) or set(raw_ref) != SOURCE_FACT_REF_KEYS:
            raise OverviewError(f"CARD_SOURCE_FACT_REF_SHAPE_INVALID:{index}")
        fact_id = _require_clean_string(
            raw_ref["fact_id"], reason=f"CARD_SOURCE_FACT_REF_ID_INVALID:{index}"
        )
        if fact_id in source_ref_ids:
            raise OverviewError(f"CARD_SOURCE_FACT_REF_DUPLICATE:{fact_id}")
        evidence_item = evidence_by_id.get(fact_id)
        if evidence_item is None:
            raise OverviewError(f"CARD_SOURCE_FACT_REF_UNKNOWN:{fact_id}")
        if raw_ref["status"] != evidence_item["status"]:
            raise OverviewError(f"CARD_SOURCE_FACT_REF_STATUS_MISMATCH:{fact_id}")
        if not _is_sha256(raw_ref["record_sha256"]):
            raise OverviewError(f"CARD_SOURCE_FACT_REF_SHA256_INVALID:{fact_id}")
        source_ref_ids.add(fact_id)
    missing_source_refs = sorted(set(evidence_by_id) - source_ref_ids)
    if missing_source_refs:
        raise OverviewError(
            f"CARD_SOURCE_FACT_REFS_MISSING:{','.join(missing_source_refs)}"
        )

    raw_beats = value["beats"]
    if not isinstance(raw_beats, list):
        raise OverviewError("CARD_BEATS_NOT_LIST")
    beats: list[dict[str, Any]] = []
    references: list[str] = []
    for index, raw_beat in enumerate(raw_beats, start=1):
        if not isinstance(raw_beat, dict) or set(raw_beat) != CARD_BEAT_KEYS:
            raise OverviewError(f"CARD_BEAT_SHAPE_INVALID:{index}")
        if raw_beat["beat_id"] != f"b{index:02d}":
            raise OverviewError(f"CARD_BEAT_ID_INVALID:{index}")
        _require_clean_string(
            raw_beat["text"], reason=f"CARD_BEAT_TEXT_INVALID:{index}"
        )
        _require_clean_string(
            raw_beat["visual_hint"],
            reason=f"CARD_BEAT_VISUAL_HINT_INVALID:{index}",
            allow_empty=True,
        )
        fact_refs = raw_beat["fact_refs"]
        if not isinstance(fact_refs, list) or not fact_refs:
            raise OverviewError(f"CARD_BEAT_FACT_REFS_INVALID:{index}")
        if any(not isinstance(ref, str) or not ref or ref != ref.strip() for ref in fact_refs):
            raise OverviewError(f"CARD_BEAT_FACT_REF_INVALID:{index}")
        references.extend(fact_refs)
        beats.append(raw_beat)

    orphan_refs = value["orphan_refs"]
    if not isinstance(orphan_refs, list):
        raise OverviewError("CARD_ORPHAN_REFS_NOT_LIST")
    if any(not isinstance(ref, str) or not ref or ref != ref.strip() for ref in orphan_refs):
        raise OverviewError("CARD_ORPHAN_REF_INVALID")
    references.extend(orphan_refs)
    unknown_refs = sorted(set(references) - set(evidence_by_id))
    if unknown_refs:
        raise OverviewError(f"CARD_FACT_REFS_UNKNOWN:{','.join(unknown_refs)}")
    duplicate_refs = sorted(
        ref for ref, count in Counter(references).items() if count > 1
    )
    if duplicate_refs:
        raise OverviewError(f"CARD_FACT_REFS_DUPLICATE:{','.join(duplicate_refs)}")
    missing_refs = sorted(set(evidence_by_id) - set(references))
    if missing_refs:
        raise OverviewError(f"CARD_FACT_REFS_MISSING:{','.join(missing_refs)}")

    coverage = value["coverage"]
    beat_ref_count = sum(len(beat["fact_refs"]) for beat in beats)
    expected_coverage = {
        "fact_count": len(evidence),
        "beat_ref_count": beat_ref_count,
        "orphan_count": len(orphan_refs),
        "covered_fact_count": len(references),
        "coverage_ratio": 1.0,
    }
    if (
        not isinstance(coverage, dict)
        or set(coverage) != COVERAGE_KEYS
        or any(
            not _is_int(coverage[key], minimum=0)
            for key in (
                "fact_count",
                "beat_ref_count",
                "orphan_count",
                "covered_fact_count",
            )
        )
        or coverage != expected_coverage
        or not isinstance(coverage["coverage_ratio"], float)
    ):
        raise OverviewError("CARD_COVERAGE_MISMATCH")
    expected_card_id = (
        f"prototype:{chapter_id}:r{current_ref['revision_no']}:"
        f"{source_facts_sha256[:12]}"
    )
    if value["card_id"] != expected_card_id:
        raise OverviewError("CARD_ID_MISMATCH")
    return copy.deepcopy(
        {
            **value,
            "synopsis": synopsis,
            "generated_at": generated_at,
            "source_summary": {
                **source_summary,
                "source_revision": source_revision,
            },
        }
    )


def render_card(value: object) -> str:
    """把一张已闭合的 M9 prototype 卡稳定渲染为作者可读 UTF-8 文本。"""
    card = validate_card(value)
    revision_ref = card["chapter_revision_ref"]
    source_summary = card["source_summary"]
    evidence_by_id = {item["fact_id"]: item for item in card["evidence"]}
    lines = [
        f"# 单章概览卡｜{card['chapter_ref']}",
        "",
        f"- 章节版本：r{revision_ref['revision_no']}",
        f"- 章节正文 SHA256：{revision_ref['revision_text_sha256']}",
        f"- 事实快照：{source_summary['source_revision']}",
        f"- 事实快照 SHA256：{source_summary['source_facts_sha256']}",
        f"- 生成时间：{card['generated_at']}",
        "",
        "## 梗概",
        "",
        card["synopsis"],
        "",
        "## 事件点",
        "",
    ]
    if card["beats"]:
        for index, beat in enumerate(card["beats"], start=1):
            references = "、".join(beat["fact_refs"])
            lines.append(f"{index}. {beat['text']}（事实：{references}）")
    else:
        lines.append("- 无（所有事实均列在散条事实中）")
    lines.extend(["", "## 散条事实", ""])
    if card["orphan_refs"]:
        for fact_id in card["orphan_refs"]:
            lines.append(f"- [{fact_id}] {evidence_by_id[fact_id]['quote']}")
    else:
        lines.append("- 无（全部事实已进入事件点）")
    lines.extend(["", "## 原文证据", ""])
    for item in card["evidence"]:
        lines.append(
            f"- [{item['fact_id']}] 状态：{item['status']}；来源：{item['source']}"
        )
        quote = item["quote"].replace("\n", "\n  > ")
        lines.append(f"  > {quote}")
    coverage = card["coverage"]
    lines.extend(
        [
            "",
            "## 覆盖",
            "",
            f"- 事实总数：{coverage['fact_count']}",
            f"- 事件点引用：{coverage['beat_ref_count']}",
            f"- 散条事实：{coverage['orphan_count']}",
            (
                f"- 已覆盖：{coverage['covered_fact_count']}"
                f"/{coverage['fact_count']}"
            ),
            "",
        ]
    )
    return "\n".join(lines)
