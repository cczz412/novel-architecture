#!/usr/bin/env python3
"""V02/C6：把 C4 候选事件机械路由到三章 49 个正式计分原子。

本工具只做位置路由，不做语义判断：

- 候选侧位置来自 C4 ``minimal_anchor_ids`` / ``support_obligations``；
- 金标侧位置只取当章、可计分原子的 ``source_evidence`` 区间；
- 同一正文内精确重叠至少 6 个非空白字符才连边；
- 双向度数都为 1 才冻结为机械唯一路由。

机械唯一路由不等于语义命中。最终映射未获 CZ 人工判词前，不允许重跑 C5。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import v02_anchor_first_experiment as prep
from pipeline_common import model_benchmark
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
C1_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "C_anchor_first_experiment"
)
C4_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C4_r03_20260725"
C6_OUTPUT_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C6_control_and_crosswalk"
    / "crosswalk"
)

CASE_ORDER = ("B02-U0039", "B03-U0041", "B01-U0033")
EXPECTED_DENOMINATORS = {
    "B02-U0039": 8,
    "B03-U0041": 16,
    "B01-U0033": 25,
}
EXPECTED_EVENT_COUNTS = {
    "B02-U0039": 13,
    "B03-U0041": 10,
    "B01-U0033": 14,
}
EXPECTED_OBLIGATION_COUNTS = {
    "B02-U0039": 25,
    "B03-U0041": 10,
    "B01-U0033": 14,
}
MIN_OVERLAP_NONSPACE = 6

ROUTE_UNIQUE = "MECHANICAL_UNIQUE_ROUTE"
ROUTE_AMBIGUOUS = "AMBIGUOUS_ROUTE"
ROUTE_NONE = "NO_POSITION_ROUTE"


class C6CrosswalkError(ZBatchError):
    """C6 机械路由不能从冻结实物重建。"""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return model_benchmark.sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C6CrosswalkError(f"冻结件不存在：{path}")
    return model_benchmark.sha256_file(path)


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _nonspace_count(text: str) -> int:
    return sum(not char.isspace() for char in text)


def _case_manifest_rows() -> dict[str, Mapping[str, Any]]:
    path = C1_DIR / "source_manifest.json"
    manifest = read_json(path)
    rows = manifest.get("chapters")
    if (
        manifest.get("schema_version") != "v02-anchor-first-source-manifest.v1"
        or manifest.get("offline_denominator") != 49
        or not isinstance(rows, list)
        or [row.get("case_id") for row in rows] != list(CASE_ORDER)
    ):
        raise C6CrosswalkError("C1 来源清单身份、顺序或 49 分母漂移")
    return {str(row["case_id"]): row for row in rows}


def _catalog(case_id: str) -> tuple[dict[str, Mapping[str, Any]], str]:
    path = C1_DIR / f"catalogs/{case_id}.json"
    document = read_json(path)
    entries = document.get("entries")
    if (
        document.get("case_id") != case_id
        or not isinstance(entries, list)
        or document.get("entry_count") != len(entries)
    ):
        raise C6CrosswalkError(f"{case_id} 冻结锚目录漂移")
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in entries:
        if not isinstance(row, Mapping):
            raise C6CrosswalkError(f"{case_id} 锚目录含非对象")
        anchor_id = row.get("anchor_id")
        start = row.get("body_start_char")
        end = row.get("body_end_char_exclusive")
        if (
            not isinstance(anchor_id, str)
            or anchor_id in by_id
            or isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or not 0 <= start < end
        ):
            raise C6CrosswalkError(f"{case_id} 锚目录身份或区间非法")
        by_id[anchor_id] = row
    return by_id, sha256_file(path)


def _candidate_document(case_id: str) -> tuple[Mapping[str, Any], str]:
    path = C4_RUN_DIR / f"samples/main/{case_id}/candidate/model_json.json"
    candidate = read_json(path)
    events = candidate.get("events")
    if (
        candidate.get("schema_version") != "closed_anchor_alignment.v1"
        or not isinstance(events, list)
        or len(events) != EXPECTED_EVENT_COUNTS[case_id]
    ):
        raise C6CrosswalkError(f"{case_id} C4 候选事件身份或条数漂移")
    return candidate, sha256_file(path)


def _formal_parts(
    case_id: str,
    manifest_row: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], str]:
    gold_ref = manifest_row.get("formal_gold")
    if not isinstance(gold_ref, Mapping):
        raise C6CrosswalkError(f"{case_id} 缺正式金标引用")
    path = ROOT / str(gold_ref.get("path"))
    digest = sha256_file(path)
    if digest != gold_ref.get("sha256"):
        raise C6CrosswalkError(f"{case_id} 正式金标 SHA 漂移")
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
        raise C6CrosswalkError(f"{case_id} 正式计分原子分母漂移")
    if len({part.get("part_id") for part in parts}) != len(parts):
        raise C6CrosswalkError(f"{case_id} 正式计分原子 ID 重复")
    return parts, digest


def _ranges_from_anchor_ids(
    case_id: str,
    anchor_ids: Sequence[Any],
    catalog: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if (
        not isinstance(anchor_ids, list)
        or not anchor_ids
        or any(not isinstance(value, str) for value in anchor_ids)
        or len(anchor_ids) != len(set(anchor_ids))
    ):
        raise C6CrosswalkError(f"{case_id} 候选锚 ID 非法")
    ranges: list[dict[str, Any]] = []
    for anchor_id in anchor_ids:
        row = catalog.get(anchor_id)
        if row is None:
            raise C6CrosswalkError(f"{case_id} 候选锚不在冻结目录：{anchor_id}")
        ranges.append(
            {
                "anchor_id": anchor_id,
                "start": int(row["body_start_char"]),
                "end": int(row["body_end_char_exclusive"]),
            }
        )
    return ranges


def _candidate_nodes(
    case_id: str,
    candidate: Mapping[str, Any],
    catalog: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    event_nodes: list[dict[str, Any]] = []
    obligation_nodes: list[dict[str, Any]] = []
    for event in candidate["events"]:
        if not isinstance(event, Mapping):
            raise C6CrosswalkError(f"{case_id} 候选事件不是对象")
        event_id = event.get("event_id")
        event_text = event.get("event")
        obligations = event.get("support_obligations")
        if (
            not isinstance(event_id, str)
            or not isinstance(event_text, str)
            or not isinstance(obligations, list)
            or not obligations
        ):
            raise C6CrosswalkError(f"{case_id} 候选事件合同缺字段")
        event_ranges = _ranges_from_anchor_ids(
            case_id,
            event.get("minimal_anchor_ids"),
            catalog,
        )
        event_nodes.append(
            {
                "node_id": event_id,
                "parent_event_id": event_id,
                "candidate_text_sha256": model_benchmark.sha256_bytes(
                    event_text.encode("utf-8")
                ),
                "anchor_ids": list(event["minimal_anchor_ids"]),
                "ranges": event_ranges,
            }
        )
        for index, obligation in enumerate(obligations, 1):
            if not isinstance(obligation, Mapping):
                raise C6CrosswalkError(f"{event_id} 支撑义务不是对象")
            claim_span = obligation.get("claim_span")
            if not isinstance(claim_span, str) or claim_span not in event_text:
                raise C6CrosswalkError(f"{event_id} 支撑义务没有逐字落在事件句")
            obligation_nodes.append(
                {
                    "node_id": f"{event_id}#O{index:02d}",
                    "parent_event_id": event_id,
                    "candidate_text_sha256": model_benchmark.sha256_bytes(
                        claim_span.encode("utf-8")
                    ),
                    "anchor_ids": list(obligation.get("anchor_ids") or []),
                    "ranges": _ranges_from_anchor_ids(
                        case_id,
                        obligation.get("anchor_ids"),
                        catalog,
                    ),
                }
            )
    if len(obligation_nodes) != EXPECTED_OBLIGATION_COUNTS[case_id]:
        raise C6CrosswalkError(f"{case_id} 支撑义务条数漂移")
    return event_nodes, obligation_nodes


def _gold_nodes(
    case_id: str,
    parts: Sequence[Mapping[str, Any]],
    *,
    inventory_unit: int,
    source_body_sha256: str,
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for part in parts:
        part_id = part.get("part_id")
        evidence = part.get("source_evidence")
        if not isinstance(part_id, str) or not isinstance(evidence, list):
            raise C6CrosswalkError(f"{case_id} 正式原子缺 ID 或证据")
        ranges: list[dict[str, Any]] = []
        for row in evidence:
            if not isinstance(row, Mapping) or row.get("inventory_unit") != inventory_unit:
                raise C6CrosswalkError(f"{part_id} 计分证据越出目标章")
            if row.get("cache_body_sha256") != source_body_sha256:
                raise C6CrosswalkError(f"{part_id} 证据正文 SHA 漂移")
            start = row.get("cache_body_start_char")
            end = row.get("cache_body_end_char_exclusive")
            anchor_id = row.get("anchor_id")
            if (
                not isinstance(anchor_id, str)
                or isinstance(start, bool)
                or not isinstance(start, int)
                or isinstance(end, bool)
                or not isinstance(end, int)
                or not 0 <= start < end
            ):
                raise C6CrosswalkError(f"{part_id} 证据区间非法")
            ranges.append({"evidence_id": anchor_id, "start": start, "end": end})
        if not ranges:
            raise C6CrosswalkError(f"{part_id} 没有目标章计分证据")
        nodes.append(
            {
                "node_id": part_id,
                "claim_sha256": model_benchmark.sha256_bytes(
                    str(part.get("claim", "")).encode("utf-8")
                ),
                "ranges": ranges,
            }
        )
    return nodes


def _overlap_edge(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    source_body: str,
) -> dict[str, Any] | None:
    intersections: list[dict[str, Any]] = []
    for left_range in left["ranges"]:
        for right_range in right["ranges"]:
            start = max(int(left_range["start"]), int(right_range["start"]))
            end = min(int(left_range["end"]), int(right_range["end"]))
            if start >= end:
                continue
            nonspace = _nonspace_count(source_body[start:end])
            if nonspace < MIN_OVERLAP_NONSPACE:
                continue
            intersections.append(
                {
                    "start": start,
                    "end": end,
                    "nonspace_overlap": nonspace,
                    "candidate_anchor_id": left_range["anchor_id"],
                    "gold_evidence_id": right_range["evidence_id"],
                }
            )
    if not intersections:
        return None
    return {
        "candidate_node_id": left["node_id"],
        "gold_atom_id": right["node_id"],
        "max_nonspace_overlap": max(
            row["nonspace_overlap"] for row in intersections
        ),
        "intersections": intersections,
    }


def _route_graph(
    candidate_nodes: Sequence[Mapping[str, Any]],
    gold_nodes: Sequence[Mapping[str, Any]],
    source_body: str,
) -> dict[str, Any]:
    edges = [
        edge
        for candidate in candidate_nodes
        for gold in gold_nodes
        if (edge := _overlap_edge(candidate, gold, source_body)) is not None
    ]
    candidate_neighbors = {
        node["node_id"]: sorted(
            {
                edge["gold_atom_id"]
                for edge in edges
                if edge["candidate_node_id"] == node["node_id"]
            }
        )
        for node in candidate_nodes
    }
    gold_neighbors = {
        node["node_id"]: sorted(
            {
                edge["candidate_node_id"]
                for edge in edges
                if edge["gold_atom_id"] == node["node_id"]
            }
        )
        for node in gold_nodes
    }
    unique_edges = [
        edge
        for edge in edges
        if len(candidate_neighbors[edge["candidate_node_id"]]) == 1
        and len(gold_neighbors[edge["gold_atom_id"]]) == 1
    ]

    def route_status(degree: int, unique: bool) -> str:
        if degree == 0:
            return ROUTE_NONE
        if unique:
            return ROUTE_UNIQUE
        return ROUTE_AMBIGUOUS

    unique_pairs = {
        (edge["candidate_node_id"], edge["gold_atom_id"]) for edge in unique_edges
    }
    candidate_rows = [
        {
            **dict(node),
            "neighbor_gold_atom_ids": candidate_neighbors[node["node_id"]],
            "degree": len(candidate_neighbors[node["node_id"]]),
            "route_status": route_status(
                len(candidate_neighbors[node["node_id"]]),
                any(
                    candidate == node["node_id"]
                    for candidate, _gold in unique_pairs
                ),
            ),
        }
        for node in candidate_nodes
    ]
    gold_rows = [
        {
            **dict(node),
            "neighbor_candidate_node_ids": gold_neighbors[node["node_id"]],
            "degree": len(gold_neighbors[node["node_id"]]),
            "route_status": route_status(
                len(gold_neighbors[node["node_id"]]),
                any(gold == node["node_id"] for _candidate, gold in unique_pairs),
            ),
        }
        for node in gold_nodes
    ]
    return {
        "edges": edges,
        "unique_edges": unique_edges,
        "candidate_rows": candidate_rows,
        "gold_rows": gold_rows,
    }


def _status_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        status: sum(row["route_status"] == status for row in rows)
        for status in (ROUTE_UNIQUE, ROUTE_AMBIGUOUS, ROUTE_NONE)
    }


def _human_queue_rows(
    case_id: str,
    gold_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    *,
    candidate_file_sha256: str,
    formal_gold_sha256: str,
    source_body_sha256: str,
) -> list[dict[str, Any]]:
    candidate_ids = [str(row["node_id"]) for row in candidate_rows]
    candidate_by_id = {str(row["node_id"]): row for row in candidate_rows}
    pending: list[dict[str, Any]] = []
    for gold in gold_rows:
        if gold["route_status"] == ROUTE_UNIQUE:
            continue
        positional = list(gold["neighbor_candidate_node_ids"])
        review_ids = positional or candidate_ids
        choices = [
            {
                "choice_id": f"MAP_TO::{candidate_id}",
                "candidate_event_id": candidate_by_id[candidate_id][
                    "parent_event_id"
                ],
                "candidate_node_id": candidate_id,
                "candidate_text_sha256": candidate_by_id[candidate_id][
                    "candidate_text_sha256"
                ],
            }
            for candidate_id in review_ids
        ]
        choices.append(
            {
                "choice_id": "NO_CORRESPONDENCE",
                "candidate_event_id": None,
                "candidate_node_id": None,
            }
        )
        pending.append(
            {
                "case_id": case_id,
                "atom_id": gold["node_id"],
                "source_body_sha256": source_body_sha256,
                "candidate_file_sha256": candidate_file_sha256,
                "formal_gold_sha256": formal_gold_sha256,
                "gold_claim_sha256": gold["claim_sha256"],
                "gold_evidence_ranges": gold["ranges"],
                "mechanical_failure_reason": gold["route_status"],
                "position_candidate_node_ids": positional,
                "candidate_event_ids": sorted(
                    {
                        candidate_by_id[node_id]["parent_event_id"]
                        for node_id in review_ids
                    }
                ),
                "choices": choices,
                "verdict_fields": {
                    "selected_choice_id": None,
                    "semantic_match": None,
                    "fact_head": None,
                    "qualifiers": None,
                    "actuality": None,
                    "anchor_support": None,
                    "reason": None,
                    "reviewer": None,
                    "reviewed_at": None,
                },
            }
        )
    return pending


def build_crosswalk() -> dict[str, bytes]:
    manifest_rows = _case_manifest_rows()
    chapter_results: list[dict[str, Any]] = []
    human_rows: list[dict[str, Any]] = []
    frozen_event_routes: list[dict[str, Any]] = []
    frozen_obligation_routes: list[dict[str, Any]] = []

    for case_id in CASE_ORDER:
        manifest_row = manifest_rows[case_id]
        catalog, catalog_sha = _catalog(case_id)
        candidate, candidate_sha = _candidate_document(case_id)
        parts, gold_sha = _formal_parts(case_id, manifest_row)
        source = prep.load_case_source(prep.CASE_BY_ID[case_id])
        source_body = str(source["body"])
        source_sha = str(source["body_sha256"])
        if source_sha != manifest_row["chapter_cache"]["body_sha256"]:
            raise C6CrosswalkError(f"{case_id} C1 正文 SHA 漂移")
        event_nodes, obligation_nodes = _candidate_nodes(
            case_id, candidate, catalog
        )
        gold_nodes = _gold_nodes(
            case_id,
            parts,
            inventory_unit=int(manifest_row["inventory_unit"]),
            source_body_sha256=source_sha,
        )
        event_graph = _route_graph(event_nodes, gold_nodes, source_body)
        obligation_graph = _route_graph(obligation_nodes, gold_nodes, source_body)

        frozen_event_routes.extend(
            {
                "case_id": case_id,
                **edge,
                "route_status": ROUTE_UNIQUE,
                "mechanical_route_is_not_semantic_verdict": True,
            }
            for edge in event_graph["unique_edges"]
        )
        frozen_obligation_routes.extend(
            {
                "case_id": case_id,
                **edge,
                "route_status": ROUTE_UNIQUE,
                "mechanical_route_is_not_semantic_verdict": True,
            }
            for edge in obligation_graph["unique_edges"]
        )
        human_rows.extend(
            _human_queue_rows(
                case_id,
                event_graph["gold_rows"],
                event_graph["candidate_rows"],
                candidate_file_sha256=candidate_sha,
                formal_gold_sha256=gold_sha,
                source_body_sha256=source_sha,
            )
        )
        chapter_results.append(
            {
                "case_id": case_id,
                "inventory_unit": manifest_row["inventory_unit"],
                "source_body_sha256": source_sha,
                "catalog_sha256": catalog_sha,
                "candidate_file_sha256": candidate_sha,
                "formal_gold_sha256": gold_sha,
                "formal_denominator": len(gold_nodes),
                "candidate_event_total": len(event_nodes),
                "candidate_obligation_total": len(obligation_nodes),
                "event_graph": {
                    "candidate_status_counts": _status_counts(
                        event_graph["candidate_rows"]
                    ),
                    "gold_status_counts": _status_counts(
                        event_graph["gold_rows"]
                    ),
                    "candidate_rows": event_graph["candidate_rows"],
                    "gold_rows": event_graph["gold_rows"],
                    "edges": event_graph["edges"],
                    "unique_edges": event_graph["unique_edges"],
                },
                "obligation_graph": {
                    "candidate_status_counts": _status_counts(
                        obligation_graph["candidate_rows"]
                    ),
                    "gold_status_counts": _status_counts(
                        obligation_graph["gold_rows"]
                    ),
                    "candidate_rows": obligation_graph["candidate_rows"],
                    "gold_rows": obligation_graph["gold_rows"],
                    "edges": obligation_graph["edges"],
                    "unique_edges": obligation_graph["unique_edges"],
                },
            }
        )

    event_unique_total = len(frozen_event_routes)
    obligation_unique_total = len(frozen_obligation_routes)
    if (
        sum(row["candidate_event_total"] for row in chapter_results) != 37
        or sum(row["candidate_obligation_total"] for row in chapter_results) != 49
        or sum(row["formal_denominator"] for row in chapter_results) != 49
        or event_unique_total != 13
        or obligation_unique_total != 11
        or len(human_rows) != 36
    ):
        raise C6CrosswalkError("C6 机械路由实物计数漂移")

    crosswalk = {
        "schema_version": "v02-c6-mechanical-crosswalk-partial.v1",
        "status": "PARTIAL_FROZEN_PENDING_CZ",
        "algorithm": {
            "same_case_and_source_body_required": True,
            "candidate_positions_from": (
                "C4 minimal_anchor_ids and support_obligations anchor_ids"
            ),
            "gold_positions_from": (
                "formal score eligible target-unit source_evidence ranges"
            ),
            "minimum_exact_overlap_nonspace_characters": MIN_OVERLAP_NONSPACE,
            "unique_rule": "candidate_degree==1 AND gold_degree==1",
            "forbidden_matching_methods": [
                "text_similarity",
                "person_name",
                "ordinal_guess",
                "llm_judgment",
                "greedy_merge",
            ],
        },
        "counts": {
            "candidate_event_total": 37,
            "candidate_obligation_total": 49,
            "formal_gold_atom_total": 49,
            "event_unique_route_total": event_unique_total,
            "obligation_unique_route_total": obligation_unique_total,
            "pending_gold_atom_total_event_graph": len(human_rows),
        },
        "chapters": chapter_results,
        "frozen_event_unique_routes": frozen_event_routes,
        "frozen_obligation_unique_routes": frozen_obligation_routes,
        "mechanical_route_is_not_semantic_verdict": True,
        "formal_mapping_frozen": False,
        "c5_scoring_allowed": False,
        "model_api_calls": 0,
        "network_requests": 0,
        "formal_gold_text_emitted": False,
    }
    queue = {
        "schema_version": "v02-c6-human-verdict-queue.v1",
        "status": "PENDING_CZ",
        "row_total": len(human_rows),
        "rows": human_rows,
        "allowed_semantic_match_values": [
            "FULL_MATCH",
            "PARTIAL_MATCH",
            "NO_MATCH",
        ],
        "mechanical_route_is_not_semantic_verdict": True,
        "gold_claim_or_quote_emitted": False,
        "model_judgment_used": False,
        "similarity_auto_merge_used": False,
    }
    gate = {
        "schema_version": "v02-c6-crosswalk-gate.v1",
        "status": "HARD_STOP_PENDING_CZ_MAPPING_VERDICTS",
        "control_output_prerequisite_evaluated_elsewhere": True,
        "mechanical_crosswalk_partial_frozen": True,
        "formal_mapping_frozen": False,
        "pending_human_verdict_total": len(human_rows),
        "c5_rescore_allowed": False,
        "reason": (
            "49 个计分原子仍有人工判词待定；机械位置路由不等于语义命中，"
            "不能据此重跑 C5。"
        ),
        "ling_l1_allowed_before_c6_closure": False,
    }
    ownership = {
        "schema_version": "v02-c6-ownership-ticket.v1",
        "ownership": "V02_new_zone",
        "touched_surface": "V02_C1_C4_formal_gold_read_only",
        "legacy_write_required": False,
        "test_three_counts": {
            "targeted": None,
            "v02": None,
            "full_suite": None,
        },
        "formal_gold_or_pointer_write": False,
        "current_chain_write": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    artifacts = {
        "mechanical_crosswalk_partial.json": canonical_bytes(crosswalk),
        "human_verdict_queue.json": canonical_bytes(queue),
        "mapping_gate.json": canonical_bytes(gate),
        "ownership_ticket.json": canonical_bytes(ownership),
    }
    manifest_preimage = {
        path: model_benchmark.sha256_bytes(raw)
        for path, raw in sorted(artifacts.items())
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c6-crosswalk-manifest.v1",
            "file_total_excluding_self": len(manifest_preimage),
            "files": [
                {"path": path, "sha256": digest}
                for path, digest in manifest_preimage.items()
            ],
            "artifact_set_sha256": canonical_sha(manifest_preimage),
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def write_or_verify(output_dir: Path = C6_OUTPUT_DIR) -> dict[str, Any]:
    first = build_crosswalk()
    second = build_crosswalk()
    if first != second:
        raise C6CrosswalkError("C6 机械路由连续两次构造不一致")
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative, raw in sorted(first.items()):
        path = output_dir / relative
        if path.is_file():
            if path.read_bytes() != raw:
                raise C6CrosswalkError(f"C6 已有路由工件漂移：{relative}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    if actual != set(first):
        raise C6CrosswalkError("C6 路由目录存在未登记文件")
    return {
        "status": "HARD_STOP_PENDING_CZ_MAPPING_VERDICTS",
        "output_dir": display_path(output_dir),
        "artifact_manifest_sha256": sha256_file(
            output_dir / "artifact_manifest.json"
        ),
        "mechanical_crosswalk_sha256": sha256_file(
            output_dir / "mechanical_crosswalk_partial.json"
        ),
        "human_verdict_queue_sha256": sha256_file(
            output_dir / "human_verdict_queue.json"
        ),
        "mechanical_double_run_identical": True,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=C6_OUTPUT_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        json.dumps(
            write_or_verify(args.output_dir.resolve()),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
