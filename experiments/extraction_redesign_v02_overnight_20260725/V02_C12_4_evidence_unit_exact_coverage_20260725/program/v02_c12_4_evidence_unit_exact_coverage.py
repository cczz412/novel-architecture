#!/usr/bin/env python3
"""V02/C12.4：用逐字证据单元重放旧映射队列。

本件只回答一个窄问题：如果在 C6/C8 的旧分叉点使用更严格的机械
证据单元规则，原来 36／32 条需要语义判词的行能减少多少。

机械工作路由不是语义真值。本件不回写已经冻结的 C7/C8 工作映射，
不生成 FULL_MATCH、ANCHOR_PARTIAL 或五层分数。
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


def _find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "tools").is_dir():
            return parent
    raise RuntimeError("无法定位小说架构仓库根目录")


ROOT = _find_repo_root()
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import v02_anchor_first_experiment as prep  # noqa: E402


V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
OUTPUT_DIR = V02_ROOT / "V02_C12_4_evidence_unit_exact_coverage_20260725"
REPORT_DIR = ROOT / "reports/抽取工序重设计v0.2_C12积压优化项_20260725"
SELF_PATH = Path(__file__).resolve()
NEW_TEST = ROOT / "tests/test_v02_c12_4_evidence_unit_exact_coverage.py"

C1_DIR = V02_ROOT / "C_anchor_first_experiment"
C6_DIR = V02_ROOT / "V02_C6_control_and_crosswalk/crosswalk"
C7_DIR = V02_ROOT / "V02_C7_final_mapping_and_C5_rescore"
C8_DIR = V02_ROOT / "V02_C8_control_mapping_and_interpretability"
TREATMENT_RUN = ROOT / "runs/V02_实验A锚先行倒装_C4_r03_20260725"
CONTROL_RUN = ROOT / "runs/V02_实验A锚先行倒装_C6对照臂_r05_20260725"

SOURCE_MANIFEST = C1_DIR / "source_manifest.json"
C6_CROSSWALK = C6_DIR / "mechanical_crosswalk_partial.json"
TREATMENT_QUEUE = C6_DIR / "human_verdict_queue.json"
TREATMENT_FINAL = C7_DIR / "mapping/final_treatment_mapping.json"
TREATMENT_CARDINALITY = C7_DIR / "mapping/treatment_cardinality_metrics.json"
CONTROL_ROUTE_LEDGER = C8_DIR / "preparation/route_ledger_private.json"
CONTROL_PREFREEZE = C8_DIR / "preparation/mechanical_prefreeze_private.json"
CONTROL_SOURCE_LOCK = C8_DIR / "preparation/source_lock.json"
CONTROL_FINAL = C8_DIR / "control_mapping/final_control_mapping.json"
CONTROL_CARDINALITY = C8_DIR / "control_mapping/control_cardinality_metrics.json"

C12_WORK_ORDER_PAGE = (
    "https://app.notion.com/p/"
    "v0-2-0API-A-CZ-Codex-_20260725-eb8821e57b67472db9f220b46110dcfd"
)
C12_LEDGER_PAGE = "https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c"

CASE_ORDER = ("B02-U0039", "B03-U0041", "B01-U0033")
EXPECTED_DENOMINATORS = {
    "B02-U0039": 8,
    "B03-U0041": 16,
    "B01-U0033": 25,
}
EXPECTED_TREATMENT_EVENTS = {
    "B02-U0039": 13,
    "B03-U0041": 10,
    "B01-U0033": 14,
}
EXPECTED_CONTROL_EVENTS = {
    "B02-U0039": 44,
    "B03-U0041": 10,
    "B01-U0033": 75,
}

EXPECTED_FROZEN_SHA256 = {
    SOURCE_MANIFEST: "039f1fcc3c0ee5c22e1a6588f806a6c7eb2e543c91bbae608a6f48d73aa6b023",
    C6_CROSSWALK: "cf6c6122ba063fcb0956c6d5d493042398afbb37b412c4f71f27026f9a7da310",
    TREATMENT_QUEUE: "071ac5f887721339e2c88b1d3785638303613264d16c056b8478adee189c0dd4",
    TREATMENT_FINAL: "7ddfcb2b29ed7fc1340ebd323da8603f44a3bef7d6511bce474ecbbf78acea51",
    TREATMENT_CARDINALITY: "72136f51d54b76ed4b7d156d6551ded35b2d8eccee57ba1e07d82368cc71b2d1",
    CONTROL_ROUTE_LEDGER: "d61b03f7eb50cb9c72882cd31ece798c30c3d21bccd029f33e5163a3d574a920",
    CONTROL_PREFREEZE: "618ede3db63bee07b93b5217dc1e07b4aa97b1c913aea0b221ae553fcffe2b23",
    CONTROL_SOURCE_LOCK: "fa3a9a9f81dca52889c78a5e62a1dbbce0db448647a15b07d8951a5cec587a70",
    CONTROL_FINAL: "f216ab50c94fbc7069b5b1561c24e4cac709d669012623bd8296198b801cc3d7",
    CONTROL_CARDINALITY: "3d1c41141b6da876cf22278cbfbe3719a8d3b90692c8d99f27f723f21d1ec6b0",
}

PROTECTED_ROOTS = (
    C1_DIR,
    C6_DIR,
    C7_DIR,
    C8_DIR,
    TREATMENT_RUN,
    CONTROL_RUN,
    ROOT / "reports/Z93_五本结构层金标v1.3转正_20260723",
    ROOT / "config/gold",
)

RELATIONS = ("EXACT", "CONTAINS", "CONTAINED_BY", "PARTIAL", "DISJOINT")
SEMANTIC_FIELDS = {
    "semantic_match": None,
    "fact_head": None,
    "qualifiers": None,
    "actuality": None,
    "anchor_support": None,
    "fcr": None,
    "qcr_full": None,
    "asr_full": None,
    "ucr": None,
    "sop": None,
}


class C12EvidenceUnitError(RuntimeError):
    """C12.4 无法从冻结输入安全构造证据单元覆盖层。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C12EvidenceUnitError(f"冻结输入不存在：{path}")
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_expected_frozen_inputs() -> dict[str, str]:
    actual: dict[str, str] = {}
    for path, expected in EXPECTED_FROZEN_SHA256.items():
        digest = sha256_file(path)
        if digest != expected:
            raise C12EvidenceUnitError(
                f"冻结真源 SHA 漂移：{display_path(path)} "
                f"expected={expected} actual={digest}"
            )
        actual[display_path(path)] = digest
    return actual


def _assert_safe_output_path(path: Path) -> None:
    resolved = path.resolve()
    for protected in PROTECTED_ROOTS:
        protected_resolved = protected.resolve()
        if resolved == protected_resolved or resolved.is_relative_to(
            protected_resolved
        ):
            raise C12EvidenceUnitError(
                f"C12.4 输出路径落入冻结根：{display_path(path)}"
            )


def _normalize_ranges(
    ranges: Sequence[Mapping[str, Any]],
    *,
    body_length: int,
    identity: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(ranges, 1):
        start = row.get("start")
        end = row.get("end")
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or not 0 <= start < end <= body_length
        ):
            raise C12EvidenceUnitError(f"{identity} 第{index}个区间非法")
        normalized.append(
            {
                "start": start,
                "end": end,
                "source_id": str(
                    row.get("evidence_id")
                    or row.get("anchor_id")
                    or f"R{index:02d}"
                ),
            }
        )
    if not normalized:
        raise C12EvidenceUnitError(f"{identity} 没有坐标区间")
    return normalized


def _position_set(ranges: Sequence[Mapping[str, Any]]) -> frozenset[int]:
    return frozenset(
        position
        for row in ranges
        for position in range(int(row["start"]), int(row["end"]))
    )


def coordinate_relation(
    candidate_ranges: Sequence[Mapping[str, Any]],
    evidence_ranges: Sequence[Mapping[str, Any]],
) -> str:
    candidate = _position_set(candidate_ranges)
    evidence = _position_set(evidence_ranges)
    if candidate == evidence:
        return "EXACT"
    if evidence < candidate:
        return "CONTAINS"
    if candidate < evidence:
        return "CONTAINED_BY"
    if candidate & evidence:
        return "PARTIAL"
    return "DISJOINT"


def fully_covers(
    ranges: Sequence[Mapping[str, Any]],
    *,
    start: int,
    end: int,
) -> bool:
    """半开区间并集是否无缝覆盖 [start,end)。"""

    clipped = sorted(
        (
            max(start, int(row["start"])),
            min(end, int(row["end"])),
        )
        for row in ranges
        if max(start, int(row["start"])) < min(end, int(row["end"]))
    )
    cursor = start
    for left, right in clipped:
        if left > cursor:
            return False
        cursor = max(cursor, right)
        if cursor >= end:
            return True
    return cursor >= end


def reverse_lookup_evidence_unit(
    *,
    body: str,
    row: Mapping[str, Any],
    identity: str,
) -> dict[str, Any]:
    start = row.get("cache_body_start_char", row.get("start"))
    end = row.get("cache_body_end_char_exclusive", row.get("end"))
    quote = row.get("quote")
    if (
        isinstance(start, bool)
        or not isinstance(start, int)
        or isinstance(end, bool)
        or not isinstance(end, int)
        or not 0 <= start < end <= len(body)
    ):
        raise C12EvidenceUnitError(f"{identity}: EVIDENCE_REVERSE_LOOKUP_FAILED")
    actual = body[start:end]
    if not isinstance(quote, str) or actual != quote:
        raise C12EvidenceUnitError(f"{identity}: EVIDENCE_REVERSE_LOOKUP_FAILED")
    occurrence = body.count(quote)
    return {
        "unit_id": str(row.get("anchor_id") or row.get("evidence_id") or identity),
        "start": start,
        "end": end,
        "char_count": len(quote),
        "quote_sha256": sha256_bytes(quote.encode("utf-8")),
        "source_occurrence_count": occurrence,
        "source_unique": occurrence == 1,
    }


def _load_manifest() -> tuple[dict[str, Mapping[str, Any]], Mapping[str, Any]]:
    document = read_json(SOURCE_MANIFEST)
    rows = document.get("chapters")
    if (
        document.get("schema_version") != "v02-anchor-first-source-manifest.v1"
        or document.get("offline_denominator") != 49
        or not isinstance(rows, list)
        or [row.get("case_id") for row in rows] != list(CASE_ORDER)
    ):
        raise C12EvidenceUnitError("C1 来源清单身份、顺序或分母漂移")
    return {str(row["case_id"]): row for row in rows}, document


def _load_source(
    case_id: str,
    manifest_row: Mapping[str, Any],
) -> dict[str, Any]:
    source = prep.load_case_source(prep.CASE_BY_ID[case_id])
    cache = manifest_row.get("chapter_cache")
    if (
        not isinstance(cache, Mapping)
        or source["body_sha256"] != cache.get("body_sha256")
        or len(source["body"]) != cache.get("body_char_count")
    ):
        raise C12EvidenceUnitError(f"{case_id} 冻结正文身份漂移")
    return dict(source)


def _load_catalog(
    *,
    case_id: str,
    path: Path,
    expected_sha256: str | None,
    body: str,
    body_sha256: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    digest = sha256_file(path)
    if expected_sha256 is not None and digest != expected_sha256:
        raise C12EvidenceUnitError(f"{case_id} 锚目录 SHA 漂移")
    document = read_json(path)
    entries = document.get("entries")
    if (
        document.get("case_id") != case_id
        or document.get("source_body_sha256") != body_sha256
        or not isinstance(entries, list)
        or document.get("entry_count") != len(entries)
    ):
        raise C12EvidenceUnitError(f"{case_id} 锚目录身份漂移")
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise C12EvidenceUnitError(f"{case_id} 锚目录含非对象")
        anchor_id = entry.get("anchor_id")
        start = entry.get("body_start_char")
        end = entry.get("body_end_char_exclusive")
        quote = entry.get("quote")
        if (
            not isinstance(anchor_id, str)
            or not anchor_id
            or anchor_id in result
            or isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or not 0 <= start < end <= len(body)
            or not isinstance(quote, str)
            or body[start:end] != quote
        ):
            raise C12EvidenceUnitError(
                f"{case_id}/{anchor_id}: ANCHOR_REVERSE_LOOKUP_FAILED"
            )
        result[anchor_id] = {
            "anchor_id": anchor_id,
            "start": start,
            "end": end,
            "quote_sha256": sha256_bytes(quote.encode("utf-8")),
        }
    return result, {
        "path": display_path(path),
        "sha256": digest,
        "entry_total": len(result),
        "reverse_lookup_pass_total": len(result),
    }


def _anchor_ranges(
    *,
    case_id: str,
    anchor_ids: Sequence[Any],
    catalog: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if (
        not isinstance(anchor_ids, list)
        or not anchor_ids
        or any(not isinstance(anchor_id, str) for anchor_id in anchor_ids)
        or len(set(anchor_ids)) != len(anchor_ids)
    ):
        raise C12EvidenceUnitError(f"{case_id} 候选锚 ID 列表非法")
    ranges: list[dict[str, Any]] = []
    for anchor_id in anchor_ids:
        row = catalog.get(anchor_id)
        if row is None:
            raise C12EvidenceUnitError(
                f"{case_id}/{anchor_id}: ANCHOR_REVERSE_LOOKUP_FAILED"
            )
        ranges.append(
            {
                "anchor_id": anchor_id,
                "start": int(row["start"]),
                "end": int(row["end"]),
            }
        )
    return ranges


def _load_formal_atoms(
    *,
    case_id: str,
    manifest_row: Mapping[str, Any],
    body: str,
    body_sha256: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    ref = manifest_row.get("formal_gold")
    if not isinstance(ref, Mapping):
        raise C12EvidenceUnitError(f"{case_id} 缺正式金标引用")
    path = ROOT / str(ref.get("path"))
    digest = sha256_file(path)
    if digest != ref.get("sha256"):
        raise C12EvidenceUnitError(f"{case_id} 正式金标 SHA 漂移")
    document = read_json(path)
    parts = [
        part
        for item in document.get("layered_items", [])
        if isinstance(item, Mapping)
        for part in item.get("parts", [])
        if isinstance(part, Mapping)
        and part.get("formal_score_eligible") is True
        and part.get("score_in_single_chapter") is True
    ]
    if len(parts) != EXPECTED_DENOMINATORS[case_id]:
        raise C12EvidenceUnitError(f"{case_id} 正式计分原子分母漂移")
    atoms: dict[str, dict[str, Any]] = {}
    for part in parts:
        atom_id = part.get("part_id")
        evidence = part.get("source_evidence")
        if (
            not isinstance(atom_id, str)
            or atom_id in atoms
            or not isinstance(evidence, list)
            or not evidence
        ):
            raise C12EvidenceUnitError(f"{case_id} 正式原子身份漂移")
        units: list[dict[str, Any]] = []
        for index, row in enumerate(evidence, 1):
            if (
                not isinstance(row, Mapping)
                or row.get("inventory_unit") != manifest_row.get("inventory_unit")
                or row.get("cache_body_sha256") != body_sha256
            ):
                raise C12EvidenceUnitError(f"{atom_id} 证据越章或正文 SHA 漂移")
            units.append(
                reverse_lookup_evidence_unit(
                    body=body,
                    row=row,
                    identity=f"{atom_id}/E{index:02d}",
                )
            )
        atoms[atom_id] = {
            "atom_id": atom_id,
            "claim_sha256": sha256_bytes(
                str(part.get("claim") or "").encode("utf-8")
            ),
            "evidence_units": units,
        }

    all_units = [
        (atom_id, unit)
        for atom_id, atom in atoms.items()
        for unit in atom["evidence_units"]
    ]
    for atom_id, atom in atoms.items():
        for unit in atom["evidence_units"]:
            overlaps = [
                other_atom_id
                for other_atom_id, other in all_units
                if other_atom_id != atom_id
                and max(unit["start"], other["start"])
                < min(unit["end"], other["end"])
            ]
            unit["overlaps_other_atom_ids"] = sorted(set(overlaps))

    return atoms, {
        "path": display_path(path),
        "sha256": digest,
        "atom_total": len(atoms),
        "evidence_unit_total": sum(
            len(atom["evidence_units"]) for atom in atoms.values()
        ),
        "quote_text_emitted": False,
    }


def _load_treatment_events(
    *,
    case_id: str,
    body: str,
    body_sha256: str,
    queue_rows: Sequence[Mapping[str, Any]],
    crosswalk_case: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidate_path = (
        TREATMENT_RUN / f"samples/main/{case_id}/candidate/model_json.json"
    )
    candidate_sha = sha256_file(candidate_path)
    queue_shas = {
        row.get("candidate_file_sha256")
        for row in queue_rows
        if row.get("case_id") == case_id
    }
    if queue_shas != {candidate_sha}:
        raise C12EvidenceUnitError(f"{case_id} 实验臂候选 SHA 漂移")
    catalog_path = C1_DIR / f"catalogs/{case_id}.json"
    catalog, catalog_receipt = _load_catalog(
        case_id=case_id,
        path=catalog_path,
        expected_sha256=str(crosswalk_case.get("catalog_sha256")),
        body=body,
        body_sha256=body_sha256,
    )
    document = read_json(candidate_path)
    events = document.get("events")
    if (
        document.get("schema_version") != "closed_anchor_alignment.v1"
        or not isinstance(events, list)
        or len(events) != EXPECTED_TREATMENT_EVENTS[case_id]
    ):
        raise C12EvidenceUnitError(f"{case_id} 实验臂事件合同漂移")
    result: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping):
            raise C12EvidenceUnitError(f"{case_id} 实验臂含非对象事件")
        event_id = event.get("event_id")
        text = event.get("event")
        obligations = event.get("support_obligations")
        if (
            not isinstance(event_id, str)
            or not isinstance(text, str)
            or not isinstance(obligations, list)
            or not obligations
        ):
            raise C12EvidenceUnitError(f"{case_id} 实验臂事件字段漂移")
        obligation_rows: list[dict[str, Any]] = []
        for index, obligation in enumerate(obligations, 1):
            if not isinstance(obligation, Mapping):
                raise C12EvidenceUnitError(f"{event_id} 支撑义务不是对象")
            claim_span = obligation.get("claim_span")
            if (
                not isinstance(claim_span, str)
                or text.count(claim_span) != 1
            ):
                raise C12EvidenceUnitError(
                    f"{event_id}/O{index:02d}: CLAIM_SPAN_BINDING_FAILED"
                )
            obligation_rows.append(
                {
                    "index": index,
                    "claim_span": claim_span,
                    "claim_span_sha256": sha256_bytes(
                        claim_span.encode("utf-8")
                    ),
                    "anchor_ids": list(obligation.get("anchor_ids") or []),
                    "ranges": _anchor_ranges(
                        case_id=case_id,
                        anchor_ids=obligation.get("anchor_ids"),
                        catalog=catalog,
                    ),
                }
            )
        result.append(
            {
                "event_id": event_id,
                "event_text": text,
                "event_text_sha256": sha256_bytes(text.encode("utf-8")),
                "anchor_ids": list(event.get("minimal_anchor_ids") or []),
                "ranges": _anchor_ranges(
                    case_id=case_id,
                    anchor_ids=event.get("minimal_anchor_ids"),
                    catalog=catalog,
                ),
                "obligations": obligation_rows,
            }
        )
    return result, {
        "candidate_path": display_path(candidate_path),
        "candidate_sha256": candidate_sha,
        "catalog": catalog_receipt,
        "event_total": len(result),
    }


def _load_control_events(
    *,
    case_id: str,
    body: str,
    body_sha256: str,
    source_lock: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case_inputs = source_lock.get("case_inputs")
    if not isinstance(case_inputs, Mapping):
        raise C12EvidenceUnitError("C8 source_lock 缺 case_inputs")
    ref = case_inputs.get(case_id)
    if not isinstance(ref, Mapping):
        raise C12EvidenceUnitError(f"C8 source_lock 缺 {case_id}")
    candidate_path = ROOT / str(ref.get("candidate_path"))
    catalog_path = ROOT / str(ref.get("catalog_path"))
    candidate_sha = sha256_file(candidate_path)
    if (
        candidate_sha != ref.get("candidate_sha256")
        or body_sha256 != ref.get("source_body_sha256")
    ):
        raise C12EvidenceUnitError(f"{case_id} 对照臂候选或正文 SHA 漂移")
    catalog, catalog_receipt = _load_catalog(
        case_id=case_id,
        path=catalog_path,
        expected_sha256=str(ref.get("catalog_sha256")),
        body=body,
        body_sha256=body_sha256,
    )
    document = read_json(candidate_path)
    events = document.get("events")
    if (
        document.get("schema_version") != "z-event-v1"
        or not isinstance(events, list)
        or len(events) != EXPECTED_CONTROL_EVENTS[case_id]
    ):
        raise C12EvidenceUnitError(f"{case_id} 对照臂事件合同漂移")
    result: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping):
            raise C12EvidenceUnitError(f"{case_id} 对照臂含非对象事件")
        event_id = event.get("event_id")
        text = event.get("event")
        anchors = event.get("anchors")
        if (
            not isinstance(event_id, str)
            or not isinstance(text, str)
            or not isinstance(anchors, list)
            or not anchors
        ):
            raise C12EvidenceUnitError(f"{case_id} 对照臂事件字段漂移")
        anchor_ids = [
            anchor.get("anchor_id")
            for anchor in anchors
            if isinstance(anchor, Mapping)
        ]
        result.append(
            {
                "event_id": event_id,
                "event_text": text,
                "event_text_sha256": sha256_bytes(text.encode("utf-8")),
                "anchor_ids": anchor_ids,
                "ranges": _anchor_ranges(
                    case_id=case_id,
                    anchor_ids=anchor_ids,
                    catalog=catalog,
                ),
                "obligations": [],
            }
        )
    return result, {
        "candidate_path": display_path(candidate_path),
        "candidate_sha256": candidate_sha,
        "catalog": catalog_receipt,
        "event_total": len(result),
    }


def _unit_candidate_audit(
    *,
    arm: str,
    event: Mapping[str, Any],
    unit: Mapping[str, Any],
    body: str,
) -> dict[str, Any]:
    quote = body[int(unit["start"]) : int(unit["end"])]
    occurrence = str(event["event_text"]).count(quote)
    event_anchor_cover = fully_covers(
        event["ranges"],
        start=int(unit["start"]),
        end=int(unit["end"]),
    )
    obligation_indexes: list[int] = []
    if arm == "treatment":
        for obligation in event["obligations"]:
            if (
                str(obligation["claim_span"]).count(quote) == 1
                and fully_covers(
                    obligation["ranges"],
                    start=int(unit["start"]),
                    end=int(unit["end"]),
                )
            ):
                obligation_indexes.append(int(obligation["index"]))
        claim_binding = len(obligation_indexes) == 1
    else:
        claim_binding = True

    codes: list[str] = []
    if unit["source_occurrence_count"] != 1:
        codes.append("EVIDENCE_QUOTE_NOT_UNIQUE_IN_SOURCE")
    if occurrence == 0:
        codes.append("NO_EXACT_EVENT_SURFACE")
    elif occurrence > 1:
        codes.append("EVENT_SURFACE_OCCURRENCE_AMBIGUOUS")
    if not event_anchor_cover:
        codes.append("EVIDENCE_UNIT_NOT_FULLY_ANCHORED")
    if not claim_binding:
        codes.append("CLAIM_SPAN_BINDING_FAILED")
    if unit["overlaps_other_atom_ids"]:
        codes.append("EVIDENCE_COORD_OVERLAPS_OTHER_ATOM")
    surface_anchor_eligible = (
        unit["source_occurrence_count"] == 1
        and occurrence == 1
        and event_anchor_cover
        and not unit["overlaps_other_atom_ids"]
    )
    return {
        "unit_id": unit["unit_id"],
        "quote_sha256": unit["quote_sha256"],
        "source_unique": unit["source_unique"],
        "event_surface_occurrence_count": occurrence,
        "event_anchor_full_cover": event_anchor_cover,
        "claim_span_binding": (
            "NOT_APPLICABLE" if arm == "control" else claim_binding
        ),
        "claim_span_indexes": obligation_indexes,
        "surface_anchor_eligible_before_claim_binding": (
            surface_anchor_eligible
        ),
        "eligible": not codes,
        "refusal_codes": codes,
    }


def _find_multi_event_exact_cover(
    event_unit_sets: Sequence[tuple[str, frozenset[str]]],
    all_unit_ids: frozenset[str],
) -> list[tuple[str, ...]]:
    eligible = [(event_id, covered) for event_id, covered in event_unit_sets if covered]
    solutions: list[tuple[str, ...]] = []
    max_size = min(len(all_unit_ids), len(eligible))
    for size in range(2, max_size + 1):
        for combination in itertools.combinations(eligible, size):
            covered_sets = [row[1] for row in combination]
            if set().union(*covered_sets) != set(all_unit_ids):
                continue
            if sum(len(value) for value in covered_sets) != len(all_unit_ids):
                continue
            solutions.append(tuple(row[0] for row in combination))
        if solutions:
            break
    return solutions


def _row_audit(
    *,
    arm: str,
    baseline_row: Mapping[str, Any],
    atom: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    body: str,
    frozen_mapping: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_ranges = [
        {
            "start": int(unit["start"]),
            "end": int(unit["end"]),
            "evidence_id": unit["unit_id"],
        }
        for unit in atom["evidence_units"]
    ]
    candidate_rows: list[dict[str, Any]] = []
    eligible_event_ids: list[str] = []
    surface_anchor_unit_sets: list[tuple[str, frozenset[str]]] = []
    relation_counts: Counter[str] = Counter()
    full_anchor_cover_ids: list[str] = []

    for event in events:
        relation = coordinate_relation(event["ranges"], evidence_ranges)
        relation_counts[relation] += 1
        unit_audits = [
            _unit_candidate_audit(
                arm=arm,
                event=event,
                unit=unit,
                body=body,
            )
            for unit in atom["evidence_units"]
        ]
        covered_unit_ids = frozenset(
            row["unit_id"] for row in unit_audits if row["eligible"]
        )
        surface_anchor_unit_sets.append(
            (
                str(event["event_id"]),
                frozenset(
                    row["unit_id"]
                    for row in unit_audits
                    if row["surface_anchor_eligible_before_claim_binding"]
                ),
            )
        )
        full_anchor_cover = all(
            row["event_anchor_full_cover"] for row in unit_audits
        )
        if full_anchor_cover:
            full_anchor_cover_ids.append(str(event["event_id"]))
        eligible = len(covered_unit_ids) == len(atom["evidence_units"])
        if eligible:
            eligible_event_ids.append(str(event["event_id"]))
        if relation != "DISJOINT" or any(
            row["event_surface_occurrence_count"] > 0 for row in unit_audits
        ):
            candidate_rows.append(
                {
                    "event_id": event["event_id"],
                    "event_text_sha256": event["event_text_sha256"],
                    "anchor_ids": event["anchor_ids"],
                    "coordinate_relation": relation,
                    "full_anchor_cover": full_anchor_cover,
                    "strict_all_units_eligible": eligible,
                    "unit_audits": unit_audits,
                }
            )

    all_unit_ids = frozenset(
        str(unit["unit_id"]) for unit in atom["evidence_units"]
    )
    multi_event_solutions = _find_multi_event_exact_cover(
        surface_anchor_unit_sets, all_unit_ids
    )
    refusal_codes: list[str] = []
    if len(eligible_event_ids) == 0:
        refusal_codes.append("ROW_ZERO_ELIGIBLE_EVENT")
    elif len(eligible_event_ids) > 1:
        refusal_codes.append("ROW_MULTIPLE_ELIGIBLE_EVENTS")
    if len(full_anchor_cover_ids) > 1:
        refusal_codes.append("ROW_MULTIPLE_FULL_COVERAGE_CANDIDATES")
    if multi_event_solutions:
        refusal_codes.append("MULTI_EVENT_SET_COVER_FORBIDDEN")
    if not eligible_event_ids and any(
        relation_counts[relation]
        for relation in ("EXACT", "CONTAINS", "CONTAINED_BY", "PARTIAL")
    ):
        refusal_codes.append("PARTIAL_COVERAGE_ONLY")
    if len(eligible_event_ids) == 1:
        decision = "MECHANICAL_WORKING_ROUTE"
        selected_event_ids = eligible_event_ids
    else:
        decision = "SEMANTIC_VERDICT_STILL_REQUIRED"
        selected_event_ids = []
    if not selected_event_ids:
        refusal_codes.append("AUTO_NO_CORRESPONDENCE_FORBIDDEN")

    frozen_ids = list(frozen_mapping.get("candidate_event_ids") or [])
    frozen_agreement = (
        sorted(selected_event_ids) == sorted(frozen_ids)
        if selected_event_ids
        else None
    )
    return {
        "arm": arm,
        "case_id": baseline_row["case_id"],
        "atom_id": baseline_row["atom_id"],
        "baseline_reason": (
            baseline_row.get("mechanical_failure_reason")
            or baseline_row.get("route_status")
        ),
        "baseline_mapping_source": baseline_row.get("mapping_source"),
        "formal_claim_sha256": atom["claim_sha256"],
        "evidence_units": [
            {
                **unit,
                "overlaps_other_atom_ids": unit["overlaps_other_atom_ids"],
            }
            for unit in atom["evidence_units"]
        ],
        "inspected_event_total": len(events),
        "coordinate_relation_counts": {
            relation: relation_counts[relation] for relation in RELATIONS
        },
        "full_anchor_cover_event_ids": full_anchor_cover_ids,
        "strict_eligible_event_ids": eligible_event_ids,
        "multi_event_exact_cover_solutions": [
            list(solution) for solution in multi_event_solutions
        ],
        "near_candidate_rows": candidate_rows,
        "selected_event_ids": selected_event_ids,
        "decision": decision,
        "refusal_codes": sorted(set(refusal_codes)),
        "mapping_identity": "working_route_not_semantic_verdict",
        "semantic_support_verified": False,
        "quality_score_eligible": False,
        "semantic_fields": dict(SEMANTIC_FIELDS),
        "frozen_mapping_audit": {
            "existing_mapping_source": frozen_mapping.get("mapping_source"),
            "existing_mapping_outcome": frozen_mapping.get("mapping_outcome"),
            "existing_candidate_event_ids": frozen_ids,
            "strict_route_agrees_with_existing": frozen_agreement,
            "existing_mapping_rewritten": False,
        },
    }


def _final_mapping_by_atom(path: Path) -> dict[str, Mapping[str, Any]]:
    document = read_json(path)
    rows = document.get("rows")
    if not isinstance(rows, list) or len(rows) != 49:
        raise C12EvidenceUnitError(f"冻结映射 49 行漂移：{display_path(path)}")
    result = {str(row["atom_id"]): row for row in rows}
    if len(result) != 49:
        raise C12EvidenceUnitError(f"冻结映射原子 ID 重复：{display_path(path)}")
    return result


def _source_bundle() -> dict[str, Any]:
    frozen_top = _assert_expected_frozen_inputs()
    manifest_rows, _manifest = _load_manifest()
    crosswalk = read_json(C6_CROSSWALK)
    queue = read_json(TREATMENT_QUEUE)
    route_ledger = read_json(CONTROL_ROUTE_LEDGER)
    source_lock = read_json(CONTROL_SOURCE_LOCK)
    queue_rows = queue.get("rows")
    control_rows_all = route_ledger.get("rows")
    if not isinstance(queue_rows, list) or len(queue_rows) != 36:
        raise C12EvidenceUnitError("实验臂旧 36 行队列漂移")
    if not isinstance(control_rows_all, list) or len(control_rows_all) != 49:
        raise C12EvidenceUnitError("对照臂旧 49 行路线账漂移")
    control_rows = [
        row
        for row in control_rows_all
        if row.get("mapping_source") != "MECHANICAL_C6_UNIQUE_ROUTE"
    ]
    if len(control_rows) != 32:
        raise C12EvidenceUnitError("对照臂旧 32 行判词基数漂移")
    chapters = crosswalk.get("chapters")
    if not isinstance(chapters, list) or len(chapters) != 3:
        raise C12EvidenceUnitError("C6 crosswalk 章节清单漂移")
    crosswalk_by_case = {str(row["case_id"]): row for row in chapters}

    source_records: dict[str, Any] = {
        "frozen_top_level_inputs": frozen_top,
        "chapters": [],
    }
    material: dict[str, Any] = {}
    for case_id in CASE_ORDER:
        manifest_row = manifest_rows[case_id]
        source = _load_source(case_id, manifest_row)
        body = str(source["body"])
        body_sha = str(source["body_sha256"])
        atoms, gold_receipt = _load_formal_atoms(
            case_id=case_id,
            manifest_row=manifest_row,
            body=body,
            body_sha256=body_sha,
        )
        treatment_events, treatment_receipt = _load_treatment_events(
            case_id=case_id,
            body=body,
            body_sha256=body_sha,
            queue_rows=queue_rows,
            crosswalk_case=crosswalk_by_case[case_id],
        )
        control_events, control_receipt = _load_control_events(
            case_id=case_id,
            body=body,
            body_sha256=body_sha,
            source_lock=source_lock,
        )
        source_records["chapters"].append(
            {
                "case_id": case_id,
                "source_body_sha256": body_sha,
                "body_char_count": len(body),
                "formal_gold": gold_receipt,
                "treatment": treatment_receipt,
                "control": control_receipt,
            }
        )
        material[case_id] = {
            "body": body,
            "atoms": atoms,
            "treatment_events": treatment_events,
            "control_events": control_events,
        }
    treatment_anchor_total = sum(
        chapter["treatment"]["catalog"]["reverse_lookup_pass_total"]
        for chapter in source_records["chapters"]
    )
    control_anchor_total = sum(
        chapter["control"]["catalog"]["reverse_lookup_pass_total"]
        for chapter in source_records["chapters"]
    )
    source_records["catalog_reverse_lookup"] = {
        "treatment_catalog_entries": treatment_anchor_total,
        "control_catalog_entries": control_anchor_total,
        "independent_catalog_checks_total": (
            treatment_anchor_total + control_anchor_total
        ),
        "same_coordinate_identity_unique_anchor_total": (
            treatment_anchor_total
            if treatment_anchor_total == control_anchor_total
            else None
        ),
    }
    return {
        "queue_rows": queue_rows,
        "control_rows": control_rows,
        "material": material,
        "source_records": source_records,
    }


def _summarize_arm(
    *,
    arm: str,
    rows: Sequence[Mapping[str, Any]],
    baseline: int,
) -> dict[str, Any]:
    resolved = [
        row for row in rows if row["decision"] == "MECHANICAL_WORKING_ROUTE"
    ]
    remaining = baseline - len(resolved)
    by_case = []
    for case_id in CASE_ORDER:
        case_rows = [row for row in rows if row["case_id"] == case_id]
        case_resolved = [
            row
            for row in case_rows
            if row["decision"] == "MECHANICAL_WORKING_ROUTE"
        ]
        by_case.append(
            {
                "case_id": case_id,
                "baseline_semantic_verdict_rows": len(case_rows),
                "strict_mechanical_routes": len(case_resolved),
                "remaining_semantic_verdict_rows": len(case_rows)
                - len(case_resolved),
            }
        )
    return {
        "arm": arm,
        "baseline_semantic_verdict_rows": baseline,
        "strict_mechanical_routes": len(resolved),
        "remaining_semantic_verdict_rows": remaining,
        "reduction_percentage_points": (
            0.0 if baseline == 0 else 100.0 * len(resolved) / baseline
        ),
        "resolved_rows": [
            {
                "case_id": row["case_id"],
                "atom_id": row["atom_id"],
                "selected_event_ids": row["selected_event_ids"],
                "frozen_mapping_agreement": row["frozen_mapping_audit"][
                    "strict_route_agrees_with_existing"
                ],
            }
            for row in resolved
        ],
        "by_case": by_case,
    }


def _mapping_source_audit(path: Path, *, arm: str) -> dict[str, Any]:
    document = read_json(path)
    rows = document["rows"]
    mapped = [row for row in rows if row.get("mapping_outcome") == "MAPPED"]
    mechanical = [
        row
        for row in mapped
        if str(row.get("mapping_source") or "").startswith("MECHANICAL_")
    ]
    return {
        "arm": arm,
        "working_mapped_atom_total": len(mapped),
        "mechanical_source_working_mapped_atom_total": len(mechanical),
        "mechanical_rows_semantic_score_admission_allowed": False,
        "all_working_rows_require_independent_match_verdict_for_five_layers": True,
    }


def _report(summary: Mapping[str, Any], audit: Mapping[str, Any]) -> str:
    treatment = summary["arms"]["treatment"]
    control = summary["arms"]["control"]
    resolved_control = "、".join(
        f'{row["atom_id"]}→{"+".join(row["selected_event_ids"])}'
        for row in control["resolved_rows"]
    )
    return f"""# C12.4｜证据单元精确覆盖停点回包

✅ 结论：这条纯机械路线没有达到“替代 AI 合议”的目标。

- 实验臂旧队列：{treatment["baseline_semantic_verdict_rows"]} 条 → 严格机械回收
  {treatment["strict_mechanical_routes"]} 条 → 仍需语义判词
  {treatment["remaining_semantic_verdict_rows"]} 条。
- 对照臂旧队列：{control["baseline_semantic_verdict_rows"]} 条 → 严格机械回收
  {control["strict_mechanical_routes"]} 条 → 仍需语义判词
  {control["remaining_semantic_verdict_rows"]} 条。
- 两条回收：{resolved_control or "无"}。
- 合计只从 68 条降到
  {summary["combined"]["remaining_semantic_verdict_rows"]} 条，没有达到原供料建议的
  “降到 18 条以内”。

## 为什么只放这两条

放行条件同时要求：冻结短引在章内唯一；同一事件句逐字带齐全部短引；事件锚
完整覆盖每个原文坐标；实验臂还要逐条落进唯一 `claim_span` 及其锚；整行只能
有一个事件合格。多事件拼接、多个合格事件、只覆盖坐标、相似度、最长重合和
自动判“无对应”全部拒绝。

这只证明“事件句逐字携带并锚住了冻结证据表面”，仍不能证明事实头、限定、
实际性、锚承托质量或五层分数正确。

## 一个容易误读的地方

“36／32”是 C6/C8 当时的旧队列快照。两臂 49 行工作映射后来已经冻结，
本件只做影子回放，没有重开 68 条当前待办，也没有回改旧判词。

当前真正缺的是双臂共 98 条“原子×臂”的独立语义判词／RFU 账，不是把
旧机械位置边改名成语义真值。

## 冻结映射保护

- 严格回收件与现有工作映射冲突：{audit["strict_route_conflict_total"]}。
- 冻结映射回写：0。
- 模型 API／网络请求：0／0。
- 正式金标文本没有写入回包或新 JSON；新件只留坐标、ID 与 SHA。
- 质量胜负未登记；C5 历史结论不追改。

## 测试边界

- 每个证据短引与锚短引均按原坐标逐字回贴。
- 机械工作路由统一标 `working_route_not_semantic_verdict`，
  `semantic_support_verified=false`，五层字段保持空。
- 构造连续两次必须字节一致；冻结真源 SHA 前后必须不变。

## 归属票

- 归属＝V02 新区候选诊断件。
- 触碰面＝只读 C1/C6/C7/C8 与 C4/C6 运行真源；只写 C12.4 新目录和本回包；
  LEGACY 写入 0。
- 测试三读数＝定向／V02／整仓在最终验证后回填到 Notion 回执，不写死旧数。

来源：Codex
"""


def build_artifacts() -> dict[str, bytes]:
    bundle = _source_bundle()
    treatment_mapping = _final_mapping_by_atom(TREATMENT_FINAL)
    control_mapping = _final_mapping_by_atom(CONTROL_FINAL)

    treatment_rows: list[dict[str, Any]] = []
    for baseline in bundle["queue_rows"]:
        case_id = str(baseline["case_id"])
        atom_id = str(baseline["atom_id"])
        material = bundle["material"][case_id]
        treatment_rows.append(
            _row_audit(
                arm="treatment",
                baseline_row=baseline,
                atom=material["atoms"][atom_id],
                events=material["treatment_events"],
                body=material["body"],
                frozen_mapping=treatment_mapping[atom_id],
            )
        )

    control_rows: list[dict[str, Any]] = []
    for baseline in bundle["control_rows"]:
        case_id = str(baseline["case_id"])
        atom_id = str(baseline["atom_id"])
        material = bundle["material"][case_id]
        control_rows.append(
            _row_audit(
                arm="control",
                baseline_row=baseline,
                atom=material["atoms"][atom_id],
                events=material["control_events"],
                body=material["body"],
                frozen_mapping=control_mapping[atom_id],
            )
        )

    treatment_summary = _summarize_arm(
        arm="treatment", rows=treatment_rows, baseline=36
    )
    control_summary = _summarize_arm(
        arm="control", rows=control_rows, baseline=32
    )
    strict_rows = [
        row
        for row in treatment_rows + control_rows
        if row["decision"] == "MECHANICAL_WORKING_ROUTE"
    ]
    conflicts = [
        row
        for row in strict_rows
        if row["frozen_mapping_audit"]["strict_route_agrees_with_existing"]
        is not True
    ]
    summary = {
        "schema_version": "v02-c12-4-semantic-queue-reduction.v1",
        "status": "MECHANICAL_ROUTE_INSUFFICIENT_FOR_AI_CONSENSUS_REPLACEMENT",
        "arms": {
            "treatment": treatment_summary,
            "control": control_summary,
        },
        "combined": {
            "baseline_semantic_verdict_rows": 68,
            "strict_mechanical_routes": len(strict_rows),
            "remaining_semantic_verdict_rows": 68 - len(strict_rows),
            "target_remaining_semantic_verdict_rows": 18,
            "target_met": 68 - len(strict_rows) <= 18,
        },
        "historical_snapshot_not_current_open_queue": True,
        "current_missing_semantic_outcomes_atom_arm_minimum": 98,
        "working_mapping_only": True,
        "semantic_support_verified": False,
        "quality_result_registered": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    audit = {
        "schema_version": "v02-c12-4-frozen-mapping-audit.v1",
        "treatment": _mapping_source_audit(
            TREATMENT_FINAL, arm="treatment"
        ),
        "control": _mapping_source_audit(CONTROL_FINAL, arm="control"),
        "strict_route_total": len(strict_rows),
        "strict_route_conflict_total": len(conflicts),
        "strict_route_conflicts": [
            {
                "arm": row["arm"],
                "case_id": row["case_id"],
                "atom_id": row["atom_id"],
                "selected_event_ids": row["selected_event_ids"],
                "existing_candidate_event_ids": row["frozen_mapping_audit"][
                    "existing_candidate_event_ids"
                ],
            }
            for row in conflicts
        ],
        "frozen_mapping_write_total": 0,
        "semantic_score_edges_emitted": 0,
        "quality_result_registered": False,
    }
    contract = {
        "schema_version": "v02-c12-4-evidence-unit-contract.v1",
        "evidence_unit": "ONE_FORMAL_SOURCE_EVIDENCE_EXACT_RANGE",
        "strict_route_all_required": [
            "source_body_sha_and_all_input_sha_locked",
            "body_start_end_reverse_lookup_equals_frozen_quote",
            "evidence_quote_unique_in_source_body",
            "one_event_contains_every_evidence_quote_verbatim_exactly_once",
            "same_event_anchor_union_fully_covers_every_evidence_range",
            "treatment_quote_bound_to_one_claim_span_and_its_anchor_union",
            "evidence_coordinate_does_not_overlap_other_formal_atom",
            "exactly_one_event_passes_all_units",
        ],
        "forbidden": [
            "punctuation_normalization",
            "semantic_similarity",
            "longest_overlap",
            "coverage_threshold_below_full",
            "best_score_selection",
            "multi_event_set_cover",
            "automatic_no_correspondence",
            "semantic_promotion",
            "frozen_verdict_rewrite",
        ],
        "relation_values": list(RELATIONS),
        "mapping_identity": "working_route_not_semantic_verdict",
        "semantic_support_verified": False,
    }
    authority = {
        "schema_version": "v02-c12-4-authority-receipt.v1",
        "work_order_page": C12_WORK_ORDER_PAGE,
        "ledger_page": C12_LEDGER_PAGE,
        "scope": "C12.4 X05 证据单元精确覆盖",
        "authorization": (
            "影子重放旧36/32判词队列，量出严格机械路线能减少多少语义判词；"
            "不得回改已冻结判词。"
        ),
        "model_api_calls": 0,
        "network_requests": 0,
        "quality_result_registered": False,
    }
    implementation_binding = {
        "schema_version": "v02-c12-4-implementation-binding.v1",
        "program": {
            "path": display_path(SELF_PATH),
            "sha256": sha256_file(SELF_PATH),
        },
        "test": {
            "path": display_path(NEW_TEST),
            "sha256": sha256_file(NEW_TEST),
        },
        "output_rebuild_depends_on_this_binding": True,
        "program_or_test_change_requires_artifact_regeneration": True,
    }
    overlay = {
        "schema_version": "v02-c12-4-mechanical-resolution-overlay.v1",
        "status": "DIAGNOSTIC_OVERLAY_ONLY",
        "treatment_rows": treatment_rows,
        "control_rows": control_rows,
        "frozen_mapping_rewrite_allowed": False,
        "semantic_score_admission_allowed": False,
        "gold_or_candidate_text_emitted": False,
    }
    report = _report(summary, audit)
    artifacts = {
        "authority_receipt.json": canonical_bytes(authority),
        "implementation_binding_receipt.json": canonical_bytes(
            implementation_binding
        ),
        "evidence_unit_contract.json": canonical_bytes(contract),
        "source_binding_receipt.json": canonical_bytes(
            bundle["source_records"]
        ),
        "mechanical_resolution_overlay.json": canonical_bytes(overlay),
        "semantic_queue_reduction.json": canonical_bytes(summary),
        "frozen_mapping_audit.json": canonical_bytes(audit),
        "C12_4_stop_receipt.md": report.encode("utf-8"),
    }
    core_preimage = {
        name: sha256_bytes(raw) for name, raw in sorted(artifacts.items())
    }
    artifacts["double_run_receipt.json"] = canonical_bytes(
        {
            "schema_version": "v02-c12-4-double-run-receipt.v1",
            "status": "PASS_TWO_BUILDS_BYTE_IDENTICAL",
            "core_artifact_set_sha256": sha256_bytes(
                canonical_bytes(core_preimage)
            ),
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    preimage = {
        name: sha256_bytes(raw) for name, raw in sorted(artifacts.items())
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c12-4-artifact-manifest.v1",
            "file_total_excluding_self": len(preimage),
            "files": [
                {"path": name, "sha256": digest}
                for name, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(canonical_bytes(preimage)),
            "frozen_mapping_write_total": 0,
            "quality_result_registered": False,
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def _verify_or_write(
    output_dir: Path,
    artifacts: Mapping[str, bytes],
    *,
    write: bool,
) -> None:
    _assert_safe_output_path(output_dir)
    if write:
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, raw in artifacts.items():
            path = output_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
        and path.relative_to(output_dir).parts[0] != "program"
    }
    if actual != set(artifacts):
        raise C12EvidenceUnitError(
            "C12.4 输出集合不闭合："
            f"missing={sorted(set(artifacts) - actual)} "
            f"unexpected={sorted(actual - set(artifacts))}"
        )
    for name, raw in artifacts.items():
        if (output_dir / name).read_bytes() != raw:
            raise C12EvidenceUnitError(f"C12.4 输出字节漂移：{name}")


def write_or_verify(
    output_dir: Path = OUTPUT_DIR,
    report_dir: Path = REPORT_DIR,
    *,
    write: bool = True,
) -> dict[str, Any]:
    _assert_safe_output_path(report_dir)
    before = _assert_expected_frozen_inputs()
    first = build_artifacts()
    second = build_artifacts()
    if first != second:
        raise C12EvidenceUnitError("C12.4 连续两次构造不一致")
    _verify_or_write(output_dir, first, write=write)

    report_path = report_dir / "C12_4_停点回包.md"
    if write:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_bytes(first["C12_4_stop_receipt.md"])
    elif not report_path.is_file():
        raise C12EvidenceUnitError("reports 停点回包不存在，--check 不会代建")
    if report_path.read_bytes() != first["C12_4_stop_receipt.md"]:
        raise C12EvidenceUnitError("reports 停点回包与工件正文不一致")
    after = _assert_expected_frozen_inputs()
    if before != after:
        raise C12EvidenceUnitError("C12.4 运行期间冻结输入 SHA 漂移")

    manifest = json.loads(first["artifact_manifest.json"].decode("utf-8"))
    summary = json.loads(
        first["semantic_queue_reduction.json"].decode("utf-8")
    )
    return {
        "status": summary["status"],
        "output_dir": display_path(output_dir),
        "report_path": display_path(report_path),
        "artifact_set_sha256": manifest["artifact_set_sha256"],
        "treatment": summary["arms"]["treatment"],
        "control": summary["arms"]["control"],
        "combined": summary["combined"],
        "frozen_input_sha_unchanged": True,
        "quality_result_registered": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V02 C12.4 证据单元精确覆盖")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument(
        "--check",
        action="store_true",
        help="只回读核验既有输出，不写文件",
    )
    args = parser.parse_args()
    receipt = write_or_verify(
        args.output_dir,
        args.report_dir,
        write=not args.check,
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
