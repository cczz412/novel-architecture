#!/usr/bin/env python3
"""V02/C8 N10：生成双向映射表，并把不能诚实归因的未命中留成缺口。

本工具只读 C6/C7/C11 冻结件。缺对照映射时保持 C8 历史阻断分支；
只有 C11 映射与冻结票同时命中预写 SHA、且工作映射身份过闸后，才生成
对照臂双向映射。NO_CORRESPONDENCE 本身不能证明是「漏抽」还是
「错配」，因此两臂都不会被程序擅自补成语义病名。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
C8_ROOT = V02_ROOT / "V02_C8_control_mapping_and_interpretability"
DEFAULT_OUTPUT_DIR = C8_ROOT / "N10"

TREATMENT_MAPPING = (
    V02_ROOT
    / "V02_C7_final_mapping_and_C5_rescore/mapping/"
    "final_treatment_mapping.json"
)
TREATMENT_ROUTE_GRAPH = (
    V02_ROOT
    / "V02_C6_control_and_crosswalk/crosswalk/"
    "mechanical_crosswalk_partial.json"
)
CONTROL_MAPPING = C8_ROOT / "control_mapping/final_control_mapping.json"
CONTROL_FREEZE_RECEIPT = (
    C8_ROOT / "control_mapping/mapping_freeze_receipt.json"
)
CONTROL_ROUTE_LEDGER = C8_ROOT / "preparation/route_ledger_private.json"
CONTROL_READINESS = (
    V02_ROOT
    / "V02_C7_final_mapping_and_C5_rescore/c5_rescore/"
    "control_mapping_readiness.json"
)
TREATMENT_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C4_r03_20260725"
CONTROL_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C6对照臂_r05_20260725"

CASE_ORDER = ("B02-U0039", "B03-U0041", "B01-U0033")
CASE_DENOMINATORS = {
    "B02-U0039": 8,
    "B03-U0041": 16,
    "B01-U0033": 25,
}
TREATMENT_EVENT_COUNTS = {
    "B02-U0039": 13,
    "B03-U0041": 10,
    "B01-U0033": 14,
}
CONTROL_EVENT_COUNTS = {
    "B02-U0039": 44,
    "B03-U0041": 10,
    "B01-U0033": 75,
}
EXPECTED_SHAS = {
    "treatment_mapping": (
        "7ddfcb2b29ed7fc1340ebd323da8603f44a3bef7d6511bce474ecbbf78acea51"
    ),
    "treatment_route_graph": (
        "cf6c6122ba063fcb0956c6d5d493042398afbb37b412c4f71f27026f9a7da310"
    ),
    "control_readiness": (
        "af88f4e070a9b8ee199f8270bb7e5e5206683a9f70dd38d74b36f0f0387997a6"
    ),
    "control_mapping": (
        "f216ab50c94fbc7069b5b1561c24e4cac709d669012623bd8296198b801cc3d7"
    ),
    "control_freeze_receipt": (
        "b69c4747032fadb023915de900f153ed1af71e2c27f7b28de0d51598ff29c69a"
    ),
    "control_route_ledger": (
        "d61b03f7eb50cb9c72882cd31ece798c30c3d21bccd029f33e5163a3d574a920"
    ),
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
EXPECTED_CONTROL_CANDIDATE_SHAS = {
    "B02-U0039": (
        "64eaea14c5a979d8f8a9223f6f91b36a551229b94c537092b4b95a49aa98e5cd"
    ),
    "B03-U0041": (
        "a735021d3d0d357c2fe0a227d2967f94cd8b6ba7b002cf4cbe2e1de58c1fb13b"
    ),
    "B01-U0033": (
        "d570c51f1299f32747ab8c030a95063e439a6d00e4126ac1018c744f38de6db1"
    ),
}

BLOCKED_CONTROL = "BLOCKED_CONTROL_MAPPING"
MISSING_REASON = "MISSING_UNMATCHED_REASON"
ACTIVE_BOTH_ARMS = "BOTH_ARMS_REVERSE_TABLES_READY_REASON_GAPS_OPEN"
EXPECTED_CONDITIONAL_INVALIDATION = {
    "trigger": "CZ_APPROVES_X04",
    "required_action": "INVALIDATE_AND_RECOMPUTE_AS_BOUNDS",
    "active_now": False,
    "current_artifact_remains_unconditional_truth": False,
}


class N10Error(RuntimeError):
    """N10 不能从冻结件安全生成。"""


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
        raise N10Error(f"冻结件不存在：{path}")
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _assert_sha(label: str, path: Path, expected: str) -> str:
    actual = sha256_file(path)
    if actual != expected:
        raise N10Error(f"{label} SHA 漂移")
    return actual


def _route_rows() -> dict[str, dict[str, Any]]:
    document = read_json(TREATMENT_ROUTE_GRAPH)
    chapters = document.get("chapters")
    if (
        not isinstance(chapters, list)
        or [row.get("case_id") for row in chapters] != list(CASE_ORDER)
    ):
        raise N10Error("C6 路由图章节顺序漂移")

    rows: dict[str, dict[str, Any]] = {}
    for chapter in chapters:
        case_id = str(chapter["case_id"])
        gold_rows = chapter.get("event_graph", {}).get("gold_rows")
        if not isinstance(gold_rows, list):
            raise N10Error(f"{case_id} 缺原子路由行")
        for raw in gold_rows:
            if not isinstance(raw, Mapping):
                raise N10Error(f"{case_id} 含非法原子路由行")
            atom_id = raw.get("node_id")
            route_status = raw.get("route_status")
            candidates = raw.get("neighbor_candidate_node_ids")
            if (
                not isinstance(atom_id, str)
                or not isinstance(route_status, str)
                or not isinstance(candidates, list)
                or any(not isinstance(value, str) for value in candidates)
                or atom_id in rows
            ):
                raise N10Error(f"{case_id} 原子路由身份非法")
            rows[atom_id] = {
                "case_id": case_id,
                "mechanical_route_status": route_status,
                "position_candidate_event_ids": list(candidates),
            }

    if (
        len(rows) != 49
        or Counter(row["case_id"] for row in rows.values())
        != CASE_DENOMINATORS
    ):
        raise N10Error("C6 原子路由总数或章分母漂移")
    return rows


def _control_route_rows() -> dict[str, dict[str, Any]]:
    _assert_sha(
        "对照臂位置路由账",
        CONTROL_ROUTE_LEDGER,
        EXPECTED_SHAS["control_route_ledger"],
    )
    document = read_json(CONTROL_ROUTE_LEDGER)
    raw_rows = document.get("rows")
    if (
        document.get("row_total") != 49
        or not isinstance(raw_rows, list)
        or len(raw_rows) != 49
    ):
        raise N10Error("对照臂位置路由账不是 49 行")

    rows: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    for ordinal, raw in enumerate(raw_rows, 1):
        if not isinstance(raw, Mapping):
            raise N10Error("对照臂位置路由账含非对象行")
        case_id = raw.get("case_id")
        atom_id = raw.get("atom_id")
        route_status = raw.get("route_status")
        candidates = raw.get("position_candidate_event_ids")
        if (
            raw.get("sequence") != ordinal
            or case_id not in CASE_ORDER
            or not isinstance(atom_id, str)
            or atom_id in rows
            or not isinstance(route_status, str)
            or not isinstance(candidates, list)
            or any(not isinstance(value, str) for value in candidates)
            or len(candidates) != len(set(candidates))
        ):
            raise N10Error("对照臂位置路由账身份或候选列表非法")
        rows[atom_id] = {
            "case_id": str(case_id),
            "mechanical_route_status": route_status,
            "position_candidate_event_ids": list(candidates),
        }
        counts[str(case_id)] += 1
    if counts != CASE_DENOMINATORS:
        raise N10Error("对照臂位置路由账章分母漂移")
    return rows


def _treatment_event_ids() -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    by_case: dict[str, list[str]] = {}
    receipts: list[dict[str, str]] = []
    for case_id in CASE_ORDER:
        path = (
            TREATMENT_RUN_DIR
            / f"samples/main/{case_id}/candidate/model_json.json"
        )
        digest = _assert_sha(
            f"{case_id} 实验臂候选",
            path,
            EXPECTED_TREATMENT_CANDIDATE_SHAS[case_id],
        )
        document = read_json(path)
        events = document.get("events")
        if not isinstance(events, list) or len(events) != TREATMENT_EVENT_COUNTS[
            case_id
        ]:
            raise N10Error(f"{case_id} 实验臂事件数漂移")
        event_ids = [
            event.get("event_id") if isinstance(event, Mapping) else None
            for event in events
        ]
        if (
            any(not isinstance(value, str) for value in event_ids)
            or len(set(event_ids)) != len(event_ids)
        ):
            raise N10Error(f"{case_id} 实验臂事件身份非法")
        by_case[case_id] = [str(value) for value in event_ids]
        receipts.append({"path": display_path(path), "sha256": digest})
    return by_case, receipts


def _control_event_ids() -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    by_case: dict[str, list[str]] = {}
    receipts: list[dict[str, str]] = []
    for case_id in CASE_ORDER:
        path = (
            CONTROL_RUN_DIR
            / f"samples/main/{case_id}/candidate/model_json.json"
        )
        digest = _assert_sha(
            f"{case_id} 对照臂候选",
            path,
            EXPECTED_CONTROL_CANDIDATE_SHAS[case_id],
        )
        document = read_json(path)
        events = document.get("events")
        if (
            not isinstance(events, list)
            or len(events) != CONTROL_EVENT_COUNTS[case_id]
        ):
            raise N10Error(f"{case_id} 对照臂事件数漂移")
        event_ids = [
            event.get("event_id") if isinstance(event, Mapping) else None
            for event in events
        ]
        if (
            any(not isinstance(value, str) for value in event_ids)
            or len(set(event_ids)) != len(event_ids)
        ):
            raise N10Error(f"{case_id} 对照臂事件身份非法")
        by_case[case_id] = [str(value) for value in event_ids]
        receipts.append({"path": display_path(path), "sha256": digest})
    return by_case, receipts


def _verified_control_mapping() -> tuple[dict[str, Any], dict[str, str]]:
    mapping_sha = _assert_sha(
        "C11 对照工作映射",
        CONTROL_MAPPING,
        EXPECTED_SHAS["control_mapping"],
    )
    receipt_sha = _assert_sha(
        "C11 对照映射冻结票",
        CONTROL_FREEZE_RECEIPT,
        EXPECTED_SHAS["control_freeze_receipt"],
    )
    mapping = read_json(CONTROL_MAPPING)
    receipt = read_json(CONTROL_FREEZE_RECEIPT)
    terminal = receipt.get("terminal_row")
    if (
        mapping.get("schema_version")
        != "v02-c11-final-control-mapping.v1"
        or mapping.get("status") != "FROZEN_V02_WORKING_TRUTH"
        or mapping.get("arm") != "control"
        or mapping.get("mapping_identity") != "working_mapping_not_gold"
        or mapping.get("formal_gold_changed") is not False
        or mapping.get("formal_gold_text_emitted") is not False
        or mapping.get("case_order") != list(CASE_ORDER)
        or mapping.get("scoring_atom_total") != 49
        or mapping.get("row_total") != 49
        or mapping.get("source_counts")
        != {
            "AI_CONSENSUS": 20,
            "CZ_MANUAL": 1,
            "MECHANICAL_C6_UNIQUE_ROUTE": 17,
            "MECHANICAL_C7_5_SINGLE_CANDIDATE": 11,
        }
        or mapping.get("conditional_invalidation")
        != EXPECTED_CONDITIONAL_INVALIDATION
        or mapping.get("mapping_freeze_allowed") is not True
        or mapping.get("c5_rescore_allowed") is not True
    ):
        raise N10Error("C11 对照映射工作身份或冻结边界漂移")
    if (
        receipt.get("schema_version")
        != "v02-c11-control-mapping-freeze-receipt.v1"
        or receipt.get("status")
        != "PASS_MAPPING_FROZEN_AFTER_C11_1_TERMINAL_DERIVATION"
        or receipt.get("mapping_row_total") != 49
        or receipt.get("mapping_freeze_allowed") is not True
        or receipt.get("c5_rescore_allowed") is not True
        or receipt.get("formal_gold_or_pointer_changed") is not False
        or receipt.get("c9_history_rewritten") is not False
        or receipt.get(
            "c8_invalid_pending_engineering_fix_manually_erased"
        )
        is not False
        or receipt.get("terminal_source") != "CZ_MANUAL"
        or receipt.get("conditional_invalidation")
        != EXPECTED_CONDITIONAL_INVALIDATION
        or receipt.get("required_receipt_statement")
        != (
            "C11.1 mechanical derivation, CZ did not rejudge this row, "
            "revocable."
        )
        or not isinstance(terminal, Mapping)
        or terminal.get("source_row_id") != "C8-R036"
        or terminal.get("atom_id") != "Z74B-B01-U0033-A09"
        or terminal.get("case_id") != "B01-U0033"
        or terminal.get("selected_event_ids") != ["EV-C0033-43"]
    ):
        raise N10Error("C11 对照映射冻结票身份或保护边界漂移")
    return mapping, {
        "mapping_sha256": mapping_sha,
        "freeze_receipt_sha256": receipt_sha,
    }


def _reverse_table(
    mapping: Mapping[str, Any],
    route_rows: Mapping[str, Mapping[str, Any]],
    event_ids_by_case: Mapping[str, Sequence[str]],
    *,
    arm: str = "treatment",
    expected_mapped_atoms: int = 25,
    expected_gap_total: int = 24,
    expected_event_total: int = 37,
    expected_mapped_events: int = 21,
    expected_edge_total: int = 28,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = mapping.get("rows")
    if (
        mapping.get("status") != "FROZEN_V02_WORKING_TRUTH"
        or mapping.get("row_total") != 49
        or not isinstance(rows, list)
        or len(rows) != 49
    ):
        raise N10Error("实验臂冻结映射身份或行数漂移")

    event_to_atoms: dict[tuple[str, str], list[str]] = defaultdict(list)
    event_to_sources: dict[tuple[str, str], set[str]] = defaultdict(set)
    atom_rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    seen_atoms: set[str] = set()
    forward_edges: set[tuple[str, str, str]] = set()

    known_by_case = {
        case_id: set(event_ids_by_case[case_id]) for case_id in CASE_ORDER
    }
    for ordinal, raw in enumerate(rows, 1):
        if not isinstance(raw, Mapping):
            raise N10Error("实验臂映射含非对象行")
        case_id = raw.get("case_id")
        atom_id = raw.get("atom_id")
        event_ids = raw.get("candidate_event_ids")
        if (
            raw.get("ordinal") != ordinal
            or case_id not in CASE_ORDER
            or not isinstance(atom_id, str)
            or atom_id in seen_atoms
            or not isinstance(event_ids, list)
            or any(not isinstance(value, str) for value in event_ids)
            or len(event_ids) != len(set(event_ids))
            or atom_id not in route_rows
        ):
            raise N10Error("实验臂映射原子身份、顺序或事件列表非法")
        seen_atoms.add(atom_id)
        unknown = set(event_ids) - known_by_case[str(case_id)]
        if unknown:
            raise N10Error(f"{atom_id} 含当章候选池外事件：{sorted(unknown)}")

        mapping_outcome = raw.get("mapping_outcome")
        if bool(event_ids) != (mapping_outcome == "MAPPED"):
            raise N10Error(f"{atom_id} 映射结果与事件列表不一致")
        route = route_rows[atom_id]
        if route.get("case_id") != case_id:
            raise N10Error(f"{atom_id} 路由章身份漂移")

        for event_id in event_ids:
            key = (str(case_id), str(event_id))
            event_to_atoms[key].append(atom_id)
            event_to_sources[key].add(str(raw.get("mapping_source")))
            forward_edges.add((str(case_id), atom_id, str(event_id)))

        if event_ids:
            reason = None
            reason_status = "NOT_APPLICABLE_MAPPED"
        else:
            reason = MISSING_REASON
            reason_status = "NEEDS_EXPLICIT_UNMATCHED_REASON_VERDICT"
            gaps.append(
                {
                    "ordinal": ordinal,
                    "case_id": case_id,
                    "atom_id": atom_id,
                    "mapping_source": raw.get("mapping_source"),
                    "mechanical_route_status": route[
                        "mechanical_route_status"
                    ],
                    "position_candidate_event_ids": route[
                        "position_candidate_event_ids"
                    ],
                    "missing_field": "semantic_unmatched_reason",
                    "allowed_values": [
                        "OMISSION",
                        "SEMANTIC_MISMATCH",
                        "POSITION_NO_CANDIDATE",
                    ],
                    "automatic_inference_forbidden": True,
                }
            )

        atom_rows.append(
            {
                "ordinal": ordinal,
                "case_id": case_id,
                "atom_id": atom_id,
                "mapped_event_ids": list(event_ids),
                "mapping_outcome": mapping_outcome,
                "mapping_source": raw.get("mapping_source"),
                "mechanical_route_status": route[
                    "mechanical_route_status"
                ],
                "position_candidate_event_ids": route[
                    "position_candidate_event_ids"
                ],
                "semantic_unmatched_reason": reason,
                "unmatched_reason_status": reason_status,
            }
        )

    if len(seen_atoms) != 49:
        raise N10Error("实验臂原子集合不是 49 条唯一原子")

    event_rows: list[dict[str, Any]] = []
    reverse_edges: set[tuple[str, str, str]] = set()
    for case_id in CASE_ORDER:
        for event_id in event_ids_by_case[case_id]:
            key = (case_id, event_id)
            atom_ids = sorted(event_to_atoms.get(key, []))
            for atom_id in atom_ids:
                reverse_edges.add((case_id, atom_id, event_id))
            if not atom_ids:
                status = "UNMAPPED_OUTPUT_EVENT"
            elif len(atom_ids) == 1:
                status = "MAPPED_TO_ONE_ATOM"
            else:
                status = "MAPPED_TO_MULTIPLE_ATOMS"
            event_rows.append(
                {
                    "case_id": case_id,
                    "event_id": event_id,
                    "mapped_atom_ids": atom_ids,
                    "atom_count": len(atom_ids),
                    "reverse_status": status,
                    "mapping_sources": sorted(
                        event_to_sources.get(key, set())
                    ),
                }
            )

    if forward_edges != reverse_edges:
        raise N10Error("实验臂正向边与反向边不一致")

    mapped_atoms = sum(bool(row["mapped_event_ids"]) for row in atom_rows)
    mapped_events = sum(bool(row["mapped_atom_ids"]) for row in event_rows)
    route_counts = Counter(
        str(row["mechanical_route_status"]) for row in atom_rows
    )
    unmapped_route_counts = Counter(
        str(row["mechanical_route_status"])
        for row in atom_rows
        if not row["mapped_event_ids"]
    )
    if (
        mapped_atoms != expected_mapped_atoms
        or len(gaps) != expected_gap_total
        or len(event_rows) != expected_event_total
        or mapped_events != expected_mapped_events
        or len(forward_edges) != expected_edge_total
    ):
        raise N10Error(f"{arm} 臂 N10 覆盖、事件或边总数漂移")

    table = {
        "schema_version": "v02-c8-n10-reverse-table.v1",
        "status": (
            "TREATMENT_REVERSE_TABLE_READY_REASON_GAP_OPEN"
            if arm == "treatment"
            else "CONTROL_REVERSE_TABLE_READY_REASON_GAP_OPEN"
        ),
        "arm": arm,
        "mapping_identity": "working_mapping_not_gold",
        "scoring_atom_total": 49,
        "produced_event_total": len(event_rows),
        "mapped_atom_total": mapped_atoms,
        "unmapped_atom_total": 49 - mapped_atoms,
        "mapped_output_event_total": mapped_events,
        "unmapped_output_event_total": len(event_rows) - mapped_events,
        "atom_to_event_link_total": len(forward_edges),
        "semantic_unmatched_reason_counts": {
            "MISSING_UNMATCHED_REASON": len(gaps),
            "OMISSION": 0,
            "POSITION_NO_CANDIDATE": 0,
            "SEMANTIC_MISMATCH": 0,
        },
        "mechanical_route_status_counts": dict(sorted(route_counts.items())),
        "unmapped_atom_mechanical_route_status_counts": dict(
            sorted(unmapped_route_counts.items())
        ),
        "event_rows": event_rows,
        "atom_rows": atom_rows,
        "forward_reverse_edges_equal": True,
        "no_correspondence_used_as_semantic_reason": False,
        "formal_gold_text_emitted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    gap = {
        "schema_version": "v02-c8-n10-unmatched-reason-gap.v1",
        "status": "MISSING_UNMATCHED_REASON_VERDICTS",
        "arm": arm,
        "gap_total": len(gaps),
        "reason": (
            "NO_CORRESPONDENCE 只说明未冻结对应事件，不能单凭该字段判断"
            "是漏抽还是错配；机械 NO_POSITION_ROUTE 也不自动升级为语义病名。"
        ),
        "rows": gaps,
        "formal_gold_text_emitted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    return table, gap


def build_artifacts() -> dict[str, bytes]:
    treatment_mapping_sha = _assert_sha(
        "实验臂最终映射",
        TREATMENT_MAPPING,
        EXPECTED_SHAS["treatment_mapping"],
    )
    treatment_route_sha = _assert_sha(
        "实验臂位置路由图",
        TREATMENT_ROUTE_GRAPH,
        EXPECTED_SHAS["treatment_route_graph"],
    )
    control_readiness_sha = _assert_sha(
        "对照臂准备度票",
        CONTROL_READINESS,
        EXPECTED_SHAS["control_readiness"],
    )
    route_rows = _route_rows()
    event_ids_by_case, candidate_receipts = _treatment_event_ids()
    treatment, gap = _reverse_table(
        read_json(TREATMENT_MAPPING),
        route_rows,
        event_ids_by_case,
    )

    readiness = read_json(CONTROL_READINESS)
    if (
        readiness.get("control_mapping_frozen") is not False
        or readiness.get("semantic_verdict_pending_total") != 32
    ):
        raise N10Error("对照臂准备度身份漂移")

    contract = {
        "schema_version": "v02-c8-n10-contract.v1",
        "status": (
            "ACTIVE_BOTH_ARMS"
            if CONTROL_MAPPING.exists()
            else "ACTIVE_CONTROL_MAPPING_REQUIRED"
        ),
        "unit": "event_to_scoring_atom",
        "unmatched_reason_enum": [
            "OMISSION",
            "SEMANTIC_MISMATCH",
            "POSITION_NO_CANDIDATE",
        ],
        "missing_reason_code": MISSING_REASON,
        "rules": {
            "forward_and_reverse_edges_must_match": True,
            "one_event_may_map_to_multiple_atoms": True,
            "one_atom_may_map_to_multiple_events": True,
            "unmapped_output_event_is_not_automatically_mismatch": True,
            "no_correspondence_is_not_semantic_reason": True,
            "mechanical_route_is_not_semantic_verdict": True,
            "unknown_reason_must_remain_missing": True,
        },
        "formal_gold_text_emitted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    if CONTROL_MAPPING.exists():
        control_mapping, pins = _verified_control_mapping()
        control_route_rows = _control_route_rows()
        control_event_ids, control_candidate_receipts = _control_event_ids()
        control, control_gap = _reverse_table(
            control_mapping,
            control_route_rows,
            control_event_ids,
            arm="control",
            expected_mapped_atoms=40,
            expected_gap_total=9,
            expected_event_total=129,
            expected_mapped_events=38,
            expected_edge_total=46,
        )
        activation_receipt = {
            "schema_version": "v02-c8-n10-control-activation-receipt.v1",
            "status": "PASS_CONTROL_MAPPING_DOUBLE_PIN_AND_IDENTITY",
            "mapping_path": display_path(CONTROL_MAPPING),
            "mapping_sha256": pins["mapping_sha256"],
            "freeze_receipt_path": display_path(CONTROL_FREEZE_RECEIPT),
            "freeze_receipt_sha256": pins["freeze_receipt_sha256"],
            "mapping_identity": "working_mapping_not_gold",
            "formal_gold_changed": False,
            "conditional_invalidation": EXPECTED_CONDITIONAL_INVALIDATION,
            "scoring_atom_total": 49,
            "produced_event_total": 129,
            "mapped_atom_total": 40,
            "unmapped_atom_total": 9,
            "mapped_output_event_total": 38,
            "atom_to_event_link_total": 46,
            "semantic_unmatched_reasons_inferred": False,
            "quality_result_registered": False,
            "formal_gold_text_emitted": False,
            "model_api_calls": 0,
            "network_requests": 0,
        }
        source_receipt = {
            "schema_version": "v02-c8-n10-source-receipt.v1",
            "treatment_mapping": {
                "path": display_path(TREATMENT_MAPPING),
                "sha256": treatment_mapping_sha,
            },
            "treatment_route_graph": {
                "path": display_path(TREATMENT_ROUTE_GRAPH),
                "sha256": treatment_route_sha,
            },
            "treatment_candidates": candidate_receipts,
            "control_mapping": {
                "path": display_path(CONTROL_MAPPING),
                "sha256": pins["mapping_sha256"],
                "status": "FROZEN_V02_WORKING_TRUTH",
                "mapping_identity": "working_mapping_not_gold",
            },
            "control_freeze_receipt": {
                "path": display_path(CONTROL_FREEZE_RECEIPT),
                "sha256": pins["freeze_receipt_sha256"],
            },
            "control_route_ledger": {
                "path": display_path(CONTROL_ROUTE_LEDGER),
                "sha256": EXPECTED_SHAS["control_route_ledger"],
            },
            "control_candidates": control_candidate_receipts,
            "model_api_calls": 0,
            "network_requests": 0,
        }
        artifacts = {
            "n10_contract.json": canonical_bytes(contract),
            "source_receipt.json": canonical_bytes(source_receipt),
            "treatment_reverse_table.json": canonical_bytes(treatment),
            "unmatched_reason_gap.json": canonical_bytes(gap),
            "control_reverse_table.json": canonical_bytes(control),
            "control_unmatched_reason_gap.json": canonical_bytes(control_gap),
            "control_mapping_activation_receipt.json": canonical_bytes(
                activation_receipt
            ),
        }
        preimage = {
            relative: sha256_bytes(raw)
            for relative, raw in sorted(artifacts.items())
        }
        artifacts["artifact_manifest.json"] = canonical_bytes(
            {
                "schema_version": "v02-c8-n10-manifest.v1",
                "file_total_excluding_self": len(preimage),
                "files": [
                    {"path": relative, "sha256": digest}
                    for relative, digest in sorted(preimage.items())
                ],
                "artifact_set_sha256": sha256_bytes(
                    canonical_bytes(preimage)
                ),
                "status": ACTIVE_BOTH_ARMS,
                "model_api_calls": 0,
                "network_requests": 0,
            }
        )
        return artifacts

    control_table = {
        "schema_version": "v02-c8-n10-reverse-table.v1",
        "status": BLOCKED_CONTROL,
        "arm": "control",
        "mapping_path": display_path(CONTROL_MAPPING),
        "mapping_file_exists": False,
        "scoring_atom_total": 49,
        "mechanical_unique_route_total": 17,
        "semantic_verdict_pending_total": 32,
        "reverse_table_generated": False,
        "mechanical_routes_counted_as_semantic_mapping": False,
        "formal_gold_text_emitted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    control_block = {
        "schema_version": "v02-c8-n10-control-block-receipt.v1",
        "status": BLOCKED_CONTROL,
        "missing_input": display_path(CONTROL_MAPPING),
        "reason": (
            "对照臂只有 17 条机械唯一路由与 32 条待语义判词；"
            "机械路由不得冒充冻结语义映射。"
        ),
        "control_readiness_path": display_path(CONTROL_READINESS),
        "control_readiness_sha256": control_readiness_sha,
        "quality_result_registered": False,
        "formal_gold_text_emitted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    source_receipt = {
        "schema_version": "v02-c8-n10-source-receipt.v1",
        "treatment_mapping": {
            "path": display_path(TREATMENT_MAPPING),
            "sha256": treatment_mapping_sha,
        },
        "treatment_route_graph": {
            "path": display_path(TREATMENT_ROUTE_GRAPH),
            "sha256": treatment_route_sha,
        },
        "treatment_candidates": candidate_receipts,
        "control_mapping": {
            "path": display_path(CONTROL_MAPPING),
            "sha256": None,
            "status": BLOCKED_CONTROL,
        },
        "model_api_calls": 0,
        "network_requests": 0,
    }

    artifacts = {
        "n10_contract.json": canonical_bytes(contract),
        "source_receipt.json": canonical_bytes(source_receipt),
        "treatment_reverse_table.json": canonical_bytes(treatment),
        "unmatched_reason_gap.json": canonical_bytes(gap),
        "control_reverse_table.json": canonical_bytes(control_table),
        "control_mapping_block_receipt.json": canonical_bytes(control_block),
    }
    preimage = {
        relative: sha256_bytes(raw)
        for relative, raw in sorted(artifacts.items())
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c8-n10-manifest.v1",
            "file_total_excluding_self": len(preimage),
            "files": [
                {"path": relative, "sha256": digest}
                for relative, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(canonical_bytes(preimage)),
            "status": "TREATMENT_READY_CONTROL_BLOCKED",
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def write_or_verify(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    if (
        CONTROL_MAPPING.exists()
        and output_dir.resolve() == DEFAULT_OUTPUT_DIR.resolve()
    ):
        raise N10Error(
            "C8 历史 N10 输出只读；映射激活后必须用 --output-dir 写入新目录"
        )
    first = build_artifacts()
    second = build_artifacts()
    if first != second:
        raise N10Error("N10 连续两次构造不一致")
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative, raw in sorted(first.items()):
        path = output_dir / relative
        if path.is_file():
            if path.read_bytes() != raw:
                raise N10Error(f"N10 已有工件漂移：{relative}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    if actual != set(first):
        raise N10Error("N10 输出目录存在未登记文件")
    treatment = read_json(output_dir / "treatment_reverse_table.json")
    control = read_json(output_dir / "control_reverse_table.json")
    active = control.get("status") == (
        "CONTROL_REVERSE_TABLE_READY_REASON_GAP_OPEN"
    )
    return {
        "status": ACTIVE_BOTH_ARMS if active else "TREATMENT_READY_CONTROL_BLOCKED",
        "output_dir": display_path(output_dir),
        "mapped_atom_total": treatment["mapped_atom_total"],
        "missing_unmatched_reason_total": treatment[
            "semantic_unmatched_reason_counts"
        ][MISSING_REASON],
        "control_status": control["status"],
        "control_mapped_atom_total": (
            control["mapped_atom_total"] if active else None
        ),
        "control_missing_unmatched_reason_total": (
            control["semantic_unmatched_reason_counts"][MISSING_REASON]
            if active
            else None
        ),
        "artifact_manifest_sha256": sha256_file(
            output_dir / "artifact_manifest.json"
        ),
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
