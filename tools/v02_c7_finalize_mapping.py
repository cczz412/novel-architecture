#!/usr/bin/env python3
"""V02/C7：把五类已拍判词冻结成 49 条实验臂工作映射。

本工具只做机械合成，不读取正文，不调用模型，也不改写 C1～C7 旧件。
输出是 V02 候选区的常驻工作真源，不是正式金标。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import v02_c7_consensus_tally as consensus


ROOT = Path(__file__).resolve().parents[1]
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
C6_DIR = V02_ROOT / "V02_C6_control_and_crosswalk/crosswalk"
C75_DIR = V02_ROOT / "V02_C7_human_verdict_workspace"
C77_DIR = V02_ROOT / "V02_C7_6_7_ai_consensus_workspace"
C4_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C4_r03_20260725"
DEFAULT_OUTPUT_DIR = (
    V02_ROOT / "V02_C7_final_mapping_and_C5_rescore/mapping"
)

CROSSWALK = C6_DIR / "mechanical_crosswalk_partial.json"
HUMAN_QUEUE = C6_DIR / "human_verdict_queue.json"
C75_POLICY = C75_DIR / "c7_5_mapping_cardinality_policy.json"
C76_RESOLUTION = C77_DIR / "c7_6_one_to_many_resolution.json"
C76_POLICY = C77_DIR / "c7_6_split_degree_policy.json"
TALLY = C77_DIR / "consensus_tally_two_votes.json"
DISAGREEMENT_QUEUE = C77_DIR / "cz_disagreement_queue.json"
FIRST_VOTE = C77_DIR / "votes/terra_independent_window_1.json"
SECOND_VOTE = C77_DIR / "votes/notion_independent_window_2.json"

CASE_ORDER = ("B02-U0039", "B03-U0041", "B01-U0033")
CASE_DENOMINATORS = {
    "B02-U0039": 8,
    "B03-U0041": 16,
    "B01-U0033": 25,
}
NO_CORRESPONDENCE = "NO_CORRESPONDENCE"

EXPECTED_INPUT_SHAS = {
    "mechanical_crosswalk_partial.json": (
        "cf6c6122ba063fcb0956c6d5d493042398afbb37b412c4f71f27026f9a7da310"
    ),
    "human_verdict_queue.json": (
        "071ac5f887721339e2c88b1d3785638303613264d16c056b8478adee189c0dd4"
    ),
    "c7_5_mapping_cardinality_policy.json": (
        "34efe343912feacc3094fe7f7dab8a9f40bae568fde694e8305234348b7b5ec6"
    ),
    "c7_6_one_to_many_resolution.json": (
        "734df094d065843f563df877630a81394d9ef7a6cac9c9543235327593e61bb2"
    ),
    "c7_6_split_degree_policy.json": (
        "94c43070039b67437a139088fbd8c5974d2b077a5185b3e5d335922c5c37a86d"
    ),
    "consensus_tally_two_votes.json": (
        "4862fa954413042b2443bf3d33deb16c2a3ec8ede968a72f84b58875a3c47a43"
    ),
    "cz_disagreement_queue.json": (
        "6850352335ca9ba9520b21145d6af62fae6895751d2add776efcce3f6e25f97e"
    ),
    "terra_independent_window_1.json": (
        "62a020d4b3a0af3038f833f06c194a55a60434f348c661934b52ab147af26350"
    ),
    "notion_independent_window_2.json": (
        "030e7326ced70587eead46ec766f46de16f04e5984ef591c245f331ed97653a8"
    ),
}

MANUAL_VERDICTS = {
    "C7-010": ("EV-C0041-04", "EV-C0041-06"),
    "C7-023": ("EV-C0033-11",),
}
EXPECTED_TREATMENT_EVENT_COUNTS = {
    "B02-U0039": 13,
    "B03-U0041": 10,
    "B01-U0033": 14,
}
EXPECTED_TREATMENT_CANDIDATE_SHAS = {
    "B02-U0039": (
        "ff15bc7c0a48e8d0f9627ff6dd52f7223d1056b6e317cae242a2609db89ea074"
    ),
    "B03-U0041": (
        "f915b4387e7ea7c206b7c6f9374f9ca13986458bc1998c94b88f69253e5658f2"
    ),
    "B01-U0033": (
        "95a3aa343255b262986f06405d49a7c776c3c553c4829585a10c0259af15650a"
    ),
}


class C7FinalizeError(RuntimeError):
    """C7 最终映射不能从冻结件安全重建。"""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C7FinalizeError(f"冻结件不存在：{path}")
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _input_paths() -> dict[str, Path]:
    return {
        CROSSWALK.name: CROSSWALK,
        HUMAN_QUEUE.name: HUMAN_QUEUE,
        C75_POLICY.name: C75_POLICY,
        C76_RESOLUTION.name: C76_RESOLUTION,
        C76_POLICY.name: C76_POLICY,
        TALLY.name: TALLY,
        DISAGREEMENT_QUEUE.name: DISAGREEMENT_QUEUE,
        FIRST_VOTE.name: FIRST_VOTE,
        SECOND_VOTE.name: SECOND_VOTE,
    }


def _verify_inputs() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name, path in _input_paths().items():
        digest = sha256_file(path)
        if digest != EXPECTED_INPUT_SHAS[name]:
            raise C7FinalizeError(f"C7 输入 SHA 漂移：{name}")
        rows.append(
            {
                "path": display_path(path),
                "sha256": digest,
            }
        )
    return rows


def _queue_rows() -> tuple[list[Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    document = read_json(HUMAN_QUEUE)
    rows = document.get("rows")
    if (
        document.get("row_total") != 36
        or not isinstance(rows, list)
        or len(rows) != 36
    ):
        raise C7FinalizeError("C6 判词队列不是冻结的 36 行")
    by_row_id: dict[str, Mapping[str, Any]] = {}
    for sequence, row in enumerate(rows, 1):
        if not isinstance(row, Mapping):
            raise C7FinalizeError("C6 判词队列含非对象")
        row_id = f"C7-{sequence:03d}"
        atom_id = row.get("atom_id")
        if not isinstance(atom_id, str) or row_id in by_row_id:
            raise C7FinalizeError("C6 判词队列原子身份非法")
        by_row_id[row_id] = row
    return rows, by_row_id


def _formal_atom_order(crosswalk: Mapping[str, Any]) -> list[dict[str, str]]:
    chapters = crosswalk.get("chapters")
    if (
        not isinstance(chapters, list)
        or [row.get("case_id") for row in chapters] != list(CASE_ORDER)
    ):
        raise C7FinalizeError("C6 章节顺序漂移")
    ordered: list[dict[str, str]] = []
    for chapter in chapters:
        case_id = str(chapter["case_id"])
        gold_rows = chapter.get("event_graph", {}).get("gold_rows")
        if not isinstance(gold_rows, list):
            raise C7FinalizeError(f"{case_id} 缺正式原子顺序")
        for row in gold_rows:
            atom_id = row.get("node_id") if isinstance(row, Mapping) else None
            if not isinstance(atom_id, str):
                raise C7FinalizeError(f"{case_id} 正式原子身份非法")
            ordered.append({"case_id": case_id, "atom_id": atom_id})
    if (
        len(ordered) != 49
        or len({row["atom_id"] for row in ordered}) != 49
        or Counter(row["case_id"] for row in ordered) != CASE_DENOMINATORS
    ):
        raise C7FinalizeError("正式 49 原子顺序、唯一性或章分母漂移")
    return ordered


def _validate_choice_ids(
    row: Mapping[str, Any],
    choice_ids: Sequence[str],
) -> list[str]:
    allowed = [
        str(choice["choice_id"])
        for choice in row.get("choices", [])
        if isinstance(choice, Mapping)
    ]
    if (
        not choice_ids
        or len(choice_ids) != len(set(choice_ids))
        or any(choice_id not in allowed for choice_id in choice_ids)
        or (
            NO_CORRESPONDENCE in choice_ids
            and list(choice_ids) != [NO_CORRESPONDENCE]
        )
    ):
        raise C7FinalizeError(f"{row.get('atom_id')} 判词不在冻结选项内")
    return [choice_id for choice_id in allowed if choice_id in choice_ids]


def _resolution_lookup(
    crosswalk: Mapping[str, Any],
    queue_by_row_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    resolved: dict[str, dict[str, Any]] = {}

    for route in crosswalk.get("frozen_event_unique_routes", []):
        if not isinstance(route, Mapping):
            raise C7FinalizeError("C6 唯一路由含非对象")
        atom_id = str(route["gold_atom_id"])
        event_id = str(route["candidate_node_id"])
        resolved[atom_id] = {
            "selected_choice_ids": [f"MAP_TO::{event_id}"],
            "candidate_event_ids": [event_id],
            "mapping_source": "MECHANICAL_C6_UNIQUE_ROUTE",
            "source_detail": {
                "route_status": route.get("route_status"),
                "mechanical_route_is_not_semantic_verdict": route.get(
                    "mechanical_route_is_not_semantic_verdict"
                ),
            },
        }

    c75 = read_json(C75_POLICY)
    if (
        c75.get("auto_resolution_total") != 8
        or len(c75.get("auto_resolutions", [])) != 8
    ):
        raise C7FinalizeError("C7.5 八行回填漂移")
    for row in c75["auto_resolutions"]:
        atom_id = str(row["atom_id"])
        event_id = str(row["resolved_candidate_event_id"])
        if atom_id in resolved:
            raise C7FinalizeError(f"C7.5 重复接管原子：{atom_id}")
        resolved[atom_id] = {
            "selected_choice_ids": [f"MAP_TO::{event_id}"],
            "candidate_event_ids": [event_id],
            "mapping_source": "MECHANICAL_C7_5",
            "source_detail": {
                "row_id": row["row_id"],
                "basis": row["basis"],
            },
        }

    c76 = read_json(C76_RESOLUTION)
    if (
        c76.get("resolution_total") != 2
        or len(c76.get("resolutions", [])) != 2
    ):
        raise C7FinalizeError("C7.6 两行回填漂移")
    for row in c76["resolutions"]:
        atom_id = str(row["atom_id"])
        event_ids = [str(value) for value in row["resolved_candidate_event_ids"]]
        if atom_id in resolved:
            raise C7FinalizeError(f"C7.6 重复接管原子：{atom_id}")
        resolved[atom_id] = {
            "selected_choice_ids": [
                f"MAP_TO::{event_id}" for event_id in event_ids
            ],
            "candidate_event_ids": event_ids,
            "mapping_source": "MECHANICAL_C7_6",
            "source_detail": {
                "row_id": row["row_id"],
                "basis": row["basis"],
                "position_overlap_verified": row[
                    "position_overlap_verified"
                ],
            },
        }

    recomputed_tally = consensus.tally_votes([FIRST_VOTE, SECOND_VOTE])
    if canonical_bytes(recomputed_tally) != TALLY.read_bytes():
        raise C7FinalizeError("两张原票重算结果与落盘总票不一致")
    if (
        recomputed_tally.get("unanimous_working_verdict_total") != 24
        or recomputed_tally.get("disagreement_total") != 2
    ):
        raise C7FinalizeError("C7.7 一致票或分歧数漂移")
    for verdict in recomputed_tally["unanimous_working_verdicts"]:
        row_id = str(verdict["packet_id"])
        queue_row = queue_by_row_id[row_id]
        atom_id = str(queue_row["atom_id"])
        choice_ids = _validate_choice_ids(
            queue_row,
            [str(value) for value in verdict["selected_choice_ids"]],
        )
        if atom_id in resolved:
            raise C7FinalizeError(f"AI 合议重复接管原子：{atom_id}")
        resolved[atom_id] = {
            "selected_choice_ids": choice_ids,
            "candidate_event_ids": [
                choice_id.removeprefix("MAP_TO::")
                for choice_id in choice_ids
                if choice_id != NO_CORRESPONDENCE
            ],
            "mapping_source": "AI_CONSENSUS",
            "source_detail": {
                "row_id": row_id,
                "independent_vote_total": 2,
                "verdict_identity": "working_verdict_not_gold",
            },
        }

    for row_id, event_ids in MANUAL_VERDICTS.items():
        queue_row = queue_by_row_id[row_id]
        atom_id = str(queue_row["atom_id"])
        choice_ids = _validate_choice_ids(
            queue_row,
            [f"MAP_TO::{event_id}" for event_id in event_ids],
        )
        if atom_id in resolved:
            raise C7FinalizeError(f"CZ 判词重复接管原子：{atom_id}")
        resolved[atom_id] = {
            "selected_choice_ids": choice_ids,
            "candidate_event_ids": list(event_ids),
            "mapping_source": "CZ_MANUAL",
            "source_detail": {
                "row_id": row_id,
                "authority": "notion_ledger_2026-07-25_15:16",
                "verdict_identity": "working_verdict_not_gold",
            },
        }

    if len(resolved) != 49:
        raise C7FinalizeError(f"最终映射没有覆盖 49 原子：{len(resolved)}")
    return resolved


def _cardinality_metrics(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_case: dict[str, dict[str, Any]] = {}
    event_to_atoms: dict[tuple[str, str], list[str]] = defaultdict(list)
    split_histogram: Counter[int] = Counter()
    mapped_atom_total = 0
    link_total = 0

    for row in rows:
        case_id = str(row["case_id"])
        event_ids = [str(value) for value in row["candidate_event_ids"]]
        split_degree = len(event_ids)
        if split_degree:
            mapped_atom_total += 1
            link_total += split_degree
            split_histogram[split_degree] += 1
            for event_id in event_ids:
                event_to_atoms[(case_id, event_id)].append(str(row["atom_id"]))

    merge_histogram = Counter(
        len(atom_ids) for atom_ids in event_to_atoms.values()
    )
    for case_id in CASE_ORDER:
        case_rows = [row for row in rows if row["case_id"] == case_id]
        case_events = {
            event_id
            for row in case_rows
            for event_id in row["candidate_event_ids"]
        }
        case_event_loads = [
            {
                "event_id": event_id,
                "atom_ids": sorted(event_to_atoms[(case_id, event_id)]),
                "atom_count": len(event_to_atoms[(case_id, event_id)]),
            }
            for event_id in sorted(case_events)
        ]
        case_mapped = sum(bool(row["candidate_event_ids"]) for row in case_rows)
        case_split_hist = Counter(
            len(row["candidate_event_ids"])
            for row in case_rows
            if row["candidate_event_ids"]
        )
        case_merge_hist = Counter(
            row["atom_count"] for row in case_event_loads
        )
        denominator = CASE_DENOMINATORS[case_id]
        by_case[case_id] = {
            "scoring_atom_total": denominator,
            "mapped_atom_total": case_mapped,
            "unmapped_atom_total": denominator - case_mapped,
            "coverage_rate": case_mapped / denominator,
            "mapped_parent_event_total": len(case_events),
            "atom_split_degree_histogram": {
                str(key): value for key, value in sorted(case_split_hist.items())
            },
            "mapped_event_degree_histogram": {
                str(key): value for key, value in sorted(case_merge_hist.items())
            },
            "maximum_events_per_atom": max(case_split_hist, default=0),
            "maximum_atoms_per_mapped_event": max(case_merge_hist, default=0),
            "event_loads": case_event_loads,
        }

    return {
        "schema_version": "v02-c7-treatment-cardinality-metrics.v1",
        "arm": "treatment",
        "produced_parent_event_total": 37,
        "scoring_atom_total": 49,
        "mapped_atom_total": mapped_atom_total,
        "unmapped_atom_total": 49 - mapped_atom_total,
        "coverage_rate": mapped_atom_total / 49,
        "atom_to_event_link_total": link_total,
        "mapped_parent_event_total": len(event_to_atoms),
        "atom_split_degree_histogram": {
            str(key): value for key, value in sorted(split_histogram.items())
        },
        "one_event_atom_count": split_histogram[1],
        "multi_event_atom_count": sum(
            value for key, value in split_histogram.items() if key > 1
        ),
        "maximum_events_per_atom": max(split_histogram, default=0),
        "mapped_event_degree_histogram": {
            str(key): value for key, value in sorted(merge_histogram.items())
        },
        "one_to_one_mapped_event_count": merge_histogram[1],
        "many_to_one_mapped_event_count": sum(
            value for key, value in merge_histogram.items() if key > 1
        ),
        "maximum_atoms_per_mapped_event": max(merge_histogram, default=0),
        "by_case_breakdown": by_case,
        "event_loads": [
            {
                "case_id": case_id,
                "event_id": event_id,
                "atom_ids": sorted(atom_ids),
                "atom_count": len(atom_ids),
                "mapping_sources": sorted(
                    {
                        str(row["mapping_source"])
                        for row in rows
                        if row["case_id"] == case_id
                        and event_id in row["candidate_event_ids"]
                    }
                ),
            }
            for (case_id, event_id), atom_ids in sorted(event_to_atoms.items())
        ],
    }


def _verify_treatment_event_identities(
    rows: Sequence[Mapping[str, Any]],
) -> None:
    known_by_case: dict[str, set[str]] = {}
    for case_id in CASE_ORDER:
        path = C4_RUN_DIR / f"samples/main/{case_id}/candidate/model_json.json"
        if sha256_file(path) != EXPECTED_TREATMENT_CANDIDATE_SHAS[case_id]:
            raise C7FinalizeError(f"{case_id} C4 候选件 SHA 漂移")
        candidate = read_json(path)
        events = candidate.get("events")
        if (
            not isinstance(events, list)
            or len(events) != EXPECTED_TREATMENT_EVENT_COUNTS[case_id]
        ):
            raise C7FinalizeError(f"{case_id} C4 候选事件数漂移")
        event_ids = {
            str(event.get("event_id"))
            for event in events
            if isinstance(event, Mapping)
            and isinstance(event.get("event_id"), str)
        }
        if len(event_ids) != len(events):
            raise C7FinalizeError(f"{case_id} C4 候选事件身份非法")
        known_by_case[case_id] = event_ids

    for row in rows:
        case_id = str(row["case_id"])
        unknown = set(row["candidate_event_ids"]) - known_by_case[case_id]
        if unknown:
            raise C7FinalizeError(
                f"{row['atom_id']} 映射到当章候选池外事件：{sorted(unknown)}"
            )


def build_artifacts() -> dict[str, bytes]:
    input_receipts = _verify_inputs()
    crosswalk = read_json(CROSSWALK)
    if (
        crosswalk.get("counts", {}).get("event_unique_route_total") != 13
        or crosswalk.get("formal_mapping_frozen") is not False
    ):
        raise C7FinalizeError("C6 部分映射身份或旧冻结状态漂移")
    _queue_rows_list, queue_by_row_id = _queue_rows()
    ordered_atoms = _formal_atom_order(crosswalk)
    resolved = _resolution_lookup(crosswalk, queue_by_row_id)

    mapping_rows: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    for ordinal, atom in enumerate(ordered_atoms, 1):
        atom_id = atom["atom_id"]
        resolution = resolved[atom_id]
        event_ids = list(resolution["candidate_event_ids"])
        source = str(resolution["mapping_source"])
        source_counts[source] += 1
        mapping_rows.append(
            {
                "ordinal": ordinal,
                "case_id": atom["case_id"],
                "atom_id": atom_id,
                "mapping_outcome": (
                    "MAPPED" if event_ids else NO_CORRESPONDENCE
                ),
                "selected_choice_ids": list(
                    resolution["selected_choice_ids"]
                ),
                "candidate_event_ids": event_ids,
                "split_degree": len(event_ids),
                "mapping_source": source,
                "source_detail": resolution["source_detail"],
                "verdict_identity": "working_mapping_not_gold",
            }
        )

    _verify_treatment_event_identities(mapping_rows)
    expected_source_counts = {
        "MECHANICAL_C6_UNIQUE_ROUTE": 13,
        "MECHANICAL_C7_5": 8,
        "MECHANICAL_C7_6": 2,
        "AI_CONSENSUS": 24,
        "CZ_MANUAL": 2,
    }
    if source_counts != expected_source_counts:
        raise C7FinalizeError(
            f"五类判词计数漂移：{dict(source_counts)}"
        )
    metrics = _cardinality_metrics(mapping_rows)
    if (
        metrics["mapped_atom_total"] != 25
        or metrics["unmapped_atom_total"] != 24
        or metrics["atom_to_event_link_total"] != 28
        or metrics["mapped_parent_event_total"] != 21
        or metrics["atom_split_degree_histogram"] != {"1": 22, "2": 3}
        or metrics["mapped_event_degree_histogram"]
        != {"1": 16, "2": 3, "3": 2}
    ):
        raise C7FinalizeError("冻结映射的覆盖、拆分度或合并度漂移")

    manual_receipt = {
        "schema_version": "v02-c7-cz-manual-verdict-receipt.v1",
        "status": "PASS",
        "authority": "notion_ledger_2026-07-25_15:16",
        "authority_page_url": (
            "https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c"
        ),
        "adjudication_page_url": (
            "https://app.notion.com/p/3a85cadc4d0f815b9539c1258d3dc301"
        ),
        "source_marker": "CZ_MANUAL",
        "verdicts": [
            {
                "row_id": row_id,
                "selected_choice_ids": [
                    f"MAP_TO::{event_id}" for event_id in event_ids
                ],
            }
            for row_id, event_ids in MANUAL_VERDICTS.items()
        ],
        "model_api_calls": 0,
        "network_requests": 0,
    }
    mapping = {
        "schema_version": "v02-c7-final-treatment-mapping.v1",
        "status": "FROZEN_V02_WORKING_TRUTH",
        "mapping_identity": "working_mapping_not_gold",
        "formal_gold_changed": False,
        "formal_gold_text_emitted": False,
        "case_order": list(CASE_ORDER),
        "scoring_atom_total": 49,
        "row_total": len(mapping_rows),
        "source_counts": dict(sorted(source_counts.items())),
        "rows": mapping_rows,
        "mapping_freeze_allowed": True,
        "c5_rescore_allowed": True,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    freeze_receipt = {
        "schema_version": "v02-c7-mapping-freeze-receipt.v1",
        "status": "PASS_MAPPING_FROZEN",
        "input_receipts": input_receipts,
        "mapping_row_total": 49,
        "orphan_atom_total": 0,
        "duplicate_atom_total": 0,
        "source_counts": dict(sorted(source_counts.items())),
        "mapping_freeze_allowed": True,
        "c5_rescore_allowed": True,
        "old_c1_c4_c6_c7_artifacts_rewritten": False,
        "formal_gold_or_pointer_changed": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    artifacts = {
        "cz_manual_verdict_receipt.json": canonical_bytes(manual_receipt),
        "final_treatment_mapping.json": canonical_bytes(mapping),
        "mapping_freeze_receipt.json": canonical_bytes(freeze_receipt),
        "treatment_cardinality_metrics.json": canonical_bytes(metrics),
    }
    preimage = {
        relative: sha256_bytes(raw)
        for relative, raw in sorted(artifacts.items())
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c7-final-mapping-manifest.v1",
            "file_total_excluding_self": len(preimage),
            "files": [
                {"path": relative, "sha256": digest}
                for relative, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(canonical_bytes(preimage)),
            "mapping_freeze_allowed": True,
            "c5_rescore_allowed": True,
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def write_or_verify(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    first = build_artifacts()
    second = build_artifacts()
    if first != second:
        raise C7FinalizeError("C7 最终映射连续两次构造不一致")
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative, raw in sorted(first.items()):
        path = output_dir / relative
        if path.is_file():
            if path.read_bytes() != raw:
                raise C7FinalizeError(f"C7 已有最终工件漂移：{relative}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    if actual != set(first):
        raise C7FinalizeError("C7 最终映射目录存在未登记文件")
    mapping = read_json(output_dir / "final_treatment_mapping.json")
    metrics = read_json(output_dir / "treatment_cardinality_metrics.json")
    return {
        "status": mapping["status"],
        "output_dir": display_path(output_dir),
        "mapping_sha256": sha256_file(
            output_dir / "final_treatment_mapping.json"
        ),
        "artifact_manifest_sha256": sha256_file(
            output_dir / "artifact_manifest.json"
        ),
        "mapped_atom_total": metrics["mapped_atom_total"],
        "coverage_rate": metrics["coverage_rate"],
        "mechanical_double_run_identical": True,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
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
