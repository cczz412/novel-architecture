#!/usr/bin/env python3
"""V02/C12.1：为 Z97 五层候选计分补多对多适配层并重跑 C5 充分性。

旧 Z97 核心已经作为历史工程件验收并发布，本文件只读复用它的单条合同
校验与边权公式，不回写旧核心、旧票据或任何历史成绩。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence


def _find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "tools").is_dir():
            return parent
    raise RuntimeError("无法定位小说架构仓库根目录")


ROOT = _find_repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.Z97_rfu_ucr_ledger_20260724.core import (  # noqa: E402
    Z97ContractError,
    compute_edge_weight,
    sha256_bytes as z97_sha256_bytes,
    stable_json_bytes as z97_stable_json_bytes,
    validate_candidate_claim,
    validate_judge_eligibility,
    validate_match_verdict,
    validate_rfu,
)


V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
OUTPUT_DIR = (
    V02_ROOT
    / "V02_C12_1_cardinality_score_and_c5_rescore_20260725"
)
REPORT_DIR = (
    ROOT
    / "reports/抽取工序重设计v0.2_C12积压优化项_20260725"
)

Z97_CORE = ROOT / "experiments/Z97_rfu_ucr_ledger_20260724/core.py"
TREATMENT_MAPPING = (
    V02_ROOT
    / "V02_C7_final_mapping_and_C5_rescore/mapping/"
    "final_treatment_mapping.json"
)
TREATMENT_CARDINALITY = (
    V02_ROOT
    / "V02_C7_final_mapping_and_C5_rescore/mapping/"
    "treatment_cardinality_metrics.json"
)
CONTROL_MAPPING = (
    V02_ROOT
    / "V02_C8_control_mapping_and_interpretability/control_mapping/"
    "final_control_mapping.json"
)
CONTROL_CARDINALITY = (
    V02_ROOT
    / "V02_C8_control_mapping_and_interpretability/control_mapping/"
    "control_cardinality_metrics.json"
)
C8_GAP_INVENTORY = (
    V02_ROOT
    / "V02_C8_control_mapping_and_interpretability/gap_inventory/"
    "gap_inventory.json"
)
C11_C5_RECEIPT = (
    V02_ROOT
    / "V02_C11_product_north_star_20260725/"
    "C11_1_control_terminal_and_rescore/c5_rescore_receipt.json"
)
C1_SCORE_TEMPLATE = (
    V02_ROOT / "C_anchor_first_experiment/gate/offline_score_template.json"
)
Z89_SCORE_TICKET = (
    ROOT
    / "runs/Z97_RFU建账与UCR五层候选_v1.0_20260724/"
    "SCORE/z89_score_ticket.json"
)

EXPECTED_INPUT_SHAS = {
    Z97_CORE: "f84c1f015777756a01a505ea25ada73ab796d42b6ca933a7f5c56a129d81974f",
    TREATMENT_MAPPING: "7ddfcb2b29ed7fc1340ebd323da8603f44a3bef7d6511bce474ecbbf78acea51",
    TREATMENT_CARDINALITY: "72136f51d54b76ed4b7d156d6551ded35b2d8eccee57ba1e07d82368cc71b2d1",
    CONTROL_MAPPING: "f216ab50c94fbc7069b5b1561c24e4cac709d669012623bd8296198b801cc3d7",
    CONTROL_CARDINALITY: "3d1c41141b6da876cf22278cbfbe3719a8d3b90692c8d99f27f723f21d1ec6b0",
    C8_GAP_INVENTORY: "03da0b4c4e7fca8a7a08dd03065ba5f292b2d8e906635979b9f388ad714d3bf3",
    C11_C5_RECEIPT: "e08701613a60ae7efc70c6b7ea80aa9ef1ce87b6882ab448dfc2f6d9e17a1f4d",
    C1_SCORE_TEMPLATE: "d5b3cc43c7e5a4dd7a026ee31fd0c684d2276781407ec509bddc337fc0b9fbc6",
    Z89_SCORE_TICKET: "26ec3015f97342b53b50a874e813225ebd59b96cccda552e36e822593910be19",
}

C12_WORK_ORDER_PAGE = (
    "https://app.notion.com/p/"
    "v0-2-0API-A-CZ-Codex-_20260725-eb8821e57b67472db9f220b46110dcfd"
)
C12_READBACK_AT = "2026-07-25T12:43:42.877Z"
CONCLUSION_MISSING = "MATERIALS_INSUFFICIENT_CANNOT_ADJUDICATE"

CASE_DENOMINATORS = {
    "B02-U0039": 8,
    "B03-U0041": 16,
    "B01-U0033": 25,
}

WORKTREE_BASELINE_BEFORE_C12 = [
    {
        "status": "M",
        "path": "decisions.md",
        "category": "V02_OUTSIDE_EXISTING_DIRTY_DO_NOT_TOUCH",
    },
    {
        "status": "M",
        "path": "tests/test_v02_c11_finalize_control_and_rescore.py",
        "category": "V02_EXISTING_MODIFIED_DO_NOT_TOUCH",
    },
    {
        "status": "M",
        "path": "tests/test_v02_duse_contract.py",
        "category": "V02_EXISTING_MODIFIED_DO_NOT_TOUCH",
    },
    {
        "status": "M",
        "path": "tools/v02_duse_contract.py",
        "category": "V02_EXISTING_MODIFIED_DO_NOT_TOUCH",
    },
    {
        "status": "??",
        "path": "tests/test_v02_c11_source_coverage.py",
        "category": "V02_EXISTING_UNTRACKED_DO_NOT_TOUCH",
    },
    {
        "status": "??",
        "path": "tests/test_v02_c11_structure_paper_design.py",
        "category": "V02_EXISTING_UNTRACKED_DO_NOT_TOUCH",
    },
]


class C12CardinalityError(RuntimeError):
    """C12.1 不能从冻结件安全构造多对多适配或 C5 新票。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C12CardinalityError(f"冻结输入不存在：{path}")
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ratio(numerator: float, denominator: float) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": None if denominator == 0 else numerator / denominator,
    }


def _qualifier_full(
    rfu: Mapping[str, Any],
    verdict: Mapping[str, Any],
) -> bool:
    required = [row["qualifier_id"] for row in rfu["required_qualifiers"]]
    if not required:
        return True
    statuses = {
        row["qualifier_id"]: row["status"]
        for row in verdict["qualifier_results"]
    }
    return all(statuses.get(qualifier_id) == "present" for qualifier_id in required)


def _anchor_full(verdict: Mapping[str, Any]) -> bool:
    rows = verdict["anchor_component_results"]
    return bool(rows) and all(row["status"] == "supported" for row in rows)


def _validate_graph_inputs(
    rfus: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    verdicts: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    validated_rfus = sorted(
        (validate_rfu(row) for row in rfus),
        key=lambda row: row["rfu_id"],
    )
    validated_claims = sorted(
        (validate_candidate_claim(row) for row in claims),
        key=lambda row: row["claim_id"],
    )
    validated_verdicts = sorted(
        (validate_match_verdict(row) for row in verdicts),
        key=lambda row: (row["rfu_id"], row["claim_id"]),
    )
    rfu_by_id = {row["rfu_id"]: row for row in validated_rfus}
    claim_by_id = {row["claim_id"]: row for row in validated_claims}
    if len(rfu_by_id) != len(validated_rfus):
        raise Z97ContractError("RFU 身份重复")
    if len(claim_by_id) != len(validated_claims):
        raise Z97ContractError("CandidateClaim 身份重复")

    seen_pairs: set[tuple[str, str]] = set()
    for verdict in validated_verdicts:
        rfu = rfu_by_id.get(verdict["rfu_id"])
        claim = claim_by_id.get(verdict["claim_id"])
        if rfu is None or claim is None:
            raise Z97ContractError("MatchVerdict 引用未知 RFU 或主张")
        pair = (verdict["rfu_id"], verdict["claim_id"])
        if pair in seen_pairs:
            raise Z97ContractError(f"同一 RFU/主张有多条判词：{pair}")
        seen_pairs.add(pair)

        expected_qualifiers = {
            row["qualifier_id"] for row in rfu["required_qualifiers"]
        }
        actual_qualifiers = {
            row["qualifier_id"] for row in verdict["qualifier_results"]
        }
        if actual_qualifiers != expected_qualifiers:
            raise Z97ContractError("判词限定结果没有完整对齐 RFU 限定清单")

        expected_components = {
            row["component_id"] for row in claim["claim_components"]
        }
        actual_components = {
            row["component_id"] for row in verdict["anchor_component_results"]
        }
        if actual_components != expected_components:
            raise Z97ContractError("判词锚结果没有完整对齐候选主张部件")
    return validated_rfus, validated_claims, validated_verdicts


def select_many_to_many_matches(
    rfus: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    verdicts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """保留全部正权冻结边；RFU 与主张两侧都不做排他占位。"""

    validated_rfus, validated_claims, validated_verdicts = _validate_graph_inputs(
        rfus,
        claims,
        verdicts,
    )
    known_rfus = {row["rfu_id"] for row in validated_rfus}
    known_claims = {row["claim_id"] for row in validated_claims}
    selected = []
    for verdict in validated_verdicts:
        if (
            verdict["rfu_id"] not in known_rfus
            or verdict["claim_id"] not in known_claims
        ):
            raise Z97ContractError("MatchVerdict 引用未知 RFU 或主张")
        weight = compute_edge_weight(verdict)
        if weight <= 0:
            continue
        selected.append(
            {
                "rfu_id": verdict["rfu_id"],
                "claim_id": verdict["claim_id"],
                "edge_weight": weight,
                "verdict": verdict,
            }
        )
    return sorted(selected, key=lambda row: (row["rfu_id"], row["claim_id"]))


def compute_many_to_many_score_ticket(
    rfus: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    verdicts: Sequence[Mapping[str, Any]],
    *,
    judge_eligibility: Mapping[str, Any],
    candidate_universe_complete: bool,
    legacy_metrics_read_only: Mapping[str, Any] | None = None,
    ticket_id: str = "RFU-SCORE-TICKET-V02-MULTIGRAPH",
) -> dict[str, Any]:
    """按旧五层公式的计数单位计算候选多对多票，不拼接不同边补语义。"""

    validated_rfus, validated_claims, validated_verdicts = _validate_graph_inputs(
        rfus,
        claims,
        verdicts,
    )
    eligibility = validate_judge_eligibility(judge_eligibility)
    if not isinstance(candidate_universe_complete, bool):
        raise Z97ContractError("candidate_universe_complete 必须是布尔值")

    legacy_before = (
        z97_sha256_bytes(z97_stable_json_bytes(legacy_metrics_read_only))
        if legacy_metrics_read_only is not None
        else None
    )
    legacy_copy = (
        deepcopy(dict(legacy_metrics_read_only))
        if legacy_metrics_read_only is not None
        else None
    )
    legacy_after = (
        z97_sha256_bytes(z97_stable_json_bytes(legacy_copy))
        if legacy_copy is not None
        else None
    )
    if legacy_before != legacy_after:
        raise AssertionError("旧成绩只读副本发生漂移")

    selected = select_many_to_many_matches(
        validated_rfus,
        validated_claims,
        validated_verdicts,
    )
    by_rfu: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in selected:
        by_rfu[edge["rfu_id"]].append(edge)
        by_claim[edge["claim_id"]].append(edge)

    head_covered = 0
    qualifier_complete = 0
    usable_weight = 0.0
    total_weight = sum(float(row["weight"]) for row in validated_rfus)
    per_rfu: list[dict[str, Any]] = []
    for rfu in validated_rfus:
        edges = by_rfu.get(rfu["rfu_id"], [])
        head_ok = any(edge["verdict"]["head_match"] == "yes" for edge in edges)
        qualifier_ok = any(
            edge["verdict"]["head_match"] == "yes"
            and _qualifier_full(rfu, edge["verdict"])
            for edge in edges
        )
        usable_edges = [
            edge
            for edge in edges
            if edge["verdict"]["head_match"] == "yes"
            and _qualifier_full(rfu, edge["verdict"])
            and _anchor_full(edge["verdict"])
            and edge["verdict"]["atomicity"]
            in {"atomic", "mechanically_splittable"}
        ]
        head_covered += int(head_ok)
        qualifier_complete += int(qualifier_ok)
        if usable_edges:
            usable_weight += float(rfu["weight"])
        per_rfu.append(
            {
                "rfu_id": rfu["rfu_id"],
                "selected_claim_ids": sorted(
                    edge["claim_id"] for edge in edges
                ),
                "selected_edge_total": len(edges),
                "head_covered": head_ok,
                "required_qualifiers_complete": qualifier_ok,
                "has_individually_usable_edge": bool(usable_edges),
                "is_usable": bool(usable_edges),
                "cross_edge_semantic_stitching_used": False,
            }
        )

    anchor_complete_edge_total = sum(
        int(_anchor_full(edge["verdict"])) for edge in selected
    )
    fully_supported_claims = sum(
        int(
            any(
                _anchor_full(edge["verdict"])
                for edge in by_claim.get(row["claim_id"], [])
            )
        )
        for row in validated_claims
    )
    fcr = _ratio(head_covered, len(validated_rfus))
    qcr = _ratio(qualifier_complete, head_covered)
    asr = _ratio(anchor_complete_edge_total, len(selected))
    ucr = _ratio(usable_weight, total_weight)
    sop = _ratio(fully_supported_claims, len(validated_claims))
    five_layer_values_present = all(
        metric["value"] is not None for metric in (fcr, qcr, asr, ucr, sop)
    )
    sop_threshold_met = bool(
        candidate_universe_complete
        and sop["value"] is not None
        and sop["value"] >= 0.98
    )

    rfu_degrees = Counter(len(edges) for edges in by_rfu.values())
    claim_degrees = Counter(len(edges) for edges in by_claim.values())
    return {
        "schema_version": "ucr-score-ticket-v02-many-to-many-v1",
        "ticket_id": ticket_id,
        "status": (
            "candidate_metrics_complete_not_released"
            if five_layer_values_present
            else "candidate_metrics_incomplete"
        ),
        "matching_contract": {
            "cardinality": "many_to_many",
            "positive_frozen_edges_are_preserved": True,
            "rfu_metrics_count_each_rfu_at_most_once": True,
            "claim_metrics_count_each_claim_at_most_once": True,
            "asr_counts_selected_edges": True,
            "cross_edge_semantic_stitching": False,
            "historical_z97_core_rewritten": False,
        },
        "denominator_contract": {
            "FCR": "VALIDATED_RFU_TOTAL",
            "QCR_full": "HEAD_COVERED_UNIQUE_RFU_TOTAL",
            "ASR_full": "SELECTED_POSITIVE_EDGE_TOTAL",
            "UCR": "VALIDATED_RFU_WEIGHT_TOTAL",
            "SOP": "VALIDATED_CANDIDATE_CLAIM_TOTAL",
        },
        "metrics": {
            "FCR": fcr,
            "QCR_full": qcr,
            "ASR_full": asr,
            "UCR": ucr,
            "SOP": {
                **sop,
                "candidate_universe_complete": candidate_universe_complete,
                "threshold_met": sop_threshold_met,
            },
        },
        "cardinality": {
            "selected_edge_total": len(selected),
            "matched_rfu_total": len(by_rfu),
            "matched_claim_total": len(by_claim),
            "rfu_degree_histogram": {
                str(key): value for key, value in sorted(rfu_degrees.items())
            },
            "claim_degree_histogram": {
                str(key): value for key, value in sorted(claim_degrees.items())
            },
            "maximum_claims_per_rfu": max(rfu_degrees, default=0),
            "maximum_rfus_per_claim": max(claim_degrees, default=0),
        },
        "selected_matches": [
            {
                "rfu_id": edge["rfu_id"],
                "claim_id": edge["claim_id"],
                "edge_weight": edge["edge_weight"],
            }
            for edge in selected
        ],
        "per_rfu": per_rfu,
        "unmatched_rfu_ids": [
            row["rfu_id"]
            for row in validated_rfus
            if row["rfu_id"] not in by_rfu
        ],
        "unmatched_claim_ids": [
            row["claim_id"]
            for row in validated_claims
            if row["claim_id"] not in by_claim
        ],
        "formal_score_eligible": bool(
            eligibility["eligible"]
            and candidate_universe_complete
            and five_layer_values_present
        ),
        "eligibility": eligibility,
        "legacy_metrics_read_only": legacy_copy,
        "legacy_metrics_sha256_before": legacy_before,
        "legacy_metrics_sha256_after": legacy_after,
    }


def _verify_inputs() -> list[dict[str, str]]:
    rows = []
    for path, expected in EXPECTED_INPUT_SHAS.items():
        actual = sha256_file(path)
        if actual != expected:
            raise C12CardinalityError(f"冻结输入 SHA 漂移：{display_path(path)}")
        rows.append({"path": display_path(path), "sha256": actual})

    treatment_mapping = read_json(TREATMENT_MAPPING)
    control_mapping = read_json(CONTROL_MAPPING)
    treatment_cardinality = read_json(TREATMENT_CARDINALITY)
    control_cardinality = read_json(CONTROL_CARDINALITY)
    if (
        treatment_mapping.get("row_total") != 49
        or control_mapping.get("row_total") != 49
        or treatment_cardinality.get("mapped_atom_total") != 25
        or control_cardinality.get("mapped_atom_total") != 40
        or treatment_cardinality.get("atom_to_event_link_total") != 28
        or control_cardinality.get("atom_to_event_link_total") != 46
    ):
        raise C12CardinalityError("C7/C11 双臂映射或基数读数漂移")

    gap_inventory = read_json(C8_GAP_INVENTORY)
    conflicts = {
        row.get("conflict_id")
        for row in gap_inventory.get("blocking_conflicts", [])
        if isinstance(row, Mapping)
    }
    if conflicts != {
        "C8-P0-CARDINALITY-CONTRACT",
        "C8-P0-DENOMINATOR-CONTRACT",
    }:
        raise C12CardinalityError("C8.3 两项 P0 身份漂移")

    old_receipt = read_json(C11_C5_RECEIPT)
    if (
        old_receipt.get("selected_conclusion") != CONCLUSION_MISSING
        or old_receipt.get("quality_result_registered") is not False
    ):
        raise C12CardinalityError("C11 历史 C5 票身份漂移")
    return rows


def _denominator_crosswalk() -> dict[str, Any]:
    z89 = read_json(Z89_SCORE_TICKET)
    z89_metrics = z89.get("metrics", {})
    old_values = {
        layer: z89_metrics.get(layer, {}).get("denominator")
        for layer in ("FCR", "QCR_full", "ASR_full", "UCR", "SOP")
    }
    expected_old_values = {
        "FCR": 23,
        "QCR_full": 13,
        "ASR_full": 23,
        "UCR": 23.0,
        "SOP": 23,
    }
    if old_values != expected_old_values:
        raise C12CardinalityError("Z89 唯一五层演示分母漂移")

    rows = [
        {
            "layer": "FCR",
            "formula_denominator": "VALIDATED_RFU_TOTAL",
            "c5_current_denominator": None,
            "c5_status": "RFU_REFERENCE_ROWS_MISSING",
            "z89_historical_demo_denominator": 23,
            "difference_from_49_for_demo_only": -26,
            "why_not_49": "49 是三章计分原子数；当前尚未生成并冻结三章 RFU 账。",
        },
        {
            "layer": "QCR_full",
            "formula_denominator": "HEAD_COVERED_UNIQUE_RFU_TOTAL",
            "c5_current_denominator": None,
            "c5_status": "HEAD_MATCH_VERDICTS_MISSING",
            "z89_historical_demo_denominator": 13,
            "difference_from_49_for_demo_only": -36,
            "why_not_49": "只把事实头已命中的 RFU 放进分母，分母由判词结果决定。",
        },
        {
            "layer": "ASR_full",
            "formula_denominator": "SELECTED_POSITIVE_EDGE_TOTAL",
            "c5_current_denominator": None,
            "c5_status": "SEMANTIC_MATCH_EDGES_MISSING",
            "z89_historical_demo_denominator": 23,
            "difference_from_49_for_demo_only": -26,
            "why_not_49": "多对多后分母是冻结语义边数，不能拿工作路由边或原子数替代。",
        },
        {
            "layer": "UCR",
            "formula_denominator": "VALIDATED_RFU_WEIGHT_TOTAL",
            "c5_current_denominator": None,
            "c5_status": "APPROVED_RFU_WEIGHTS_MISSING",
            "z89_historical_demo_denominator": 23.0,
            "difference_from_49_for_demo_only": None,
            "why_not_49": "分母是权重总量，计量单位不是条数，禁止与 49 相加或合算。",
        },
        {
            "layer": "SOP",
            "formula_denominator": "VALIDATED_CANDIDATE_CLAIM_TOTAL",
            "c5_current_denominator": None,
            "c5_status": "CANDIDATE_CLAIM_UNIVERSE_MISSING",
            "z89_historical_demo_denominator": 23,
            "difference_from_49_for_demo_only": -26,
            "why_not_49": "分母随候选主张全集变化；37/129 父事件数也不能冒充主张数。",
        },
    ]
    return {
        "schema_version": "v02-c12-1-five-layer-denominator-crosswalk.v1",
        "status": "PASS_EXPLICIT_DENOMINATORS_NO_FORCED_49",
        "c1_reference_scoring_atom_total": 49,
        "c1_reference_by_case": CASE_DENOMINATORS,
        "c1_reference_role": "coverage_universe_not_universal_five_layer_denominator",
        "c5_directly_scoreable_layers": [],
        "c5_layers_remaining_missing": [
            "FCR",
            "QCR_full",
            "ASR_full",
            "UCR",
            "SOP",
        ],
        "rows": rows,
        "z89_demo_may_be_used_as_c5_value": False,
        "different_denominator_units_may_be_added_or_averaged": False,
    }


def _markdown_denominator_table(crosswalk: Mapping[str, Any]) -> str:
    lines = [
        "| 层 | C5 当前分母 | 真正来源 | Z89 单章旧演示 | 与49差额（只看旧演示） |",
        "|---|---:|---|---:|---:|",
    ]
    for row in crosswalk["rows"]:
        current = (
            str(row["c5_current_denominator"])
            if row["c5_current_denominator"] is not None
            else f"`{row['c5_status']}`"
        )
        diff = row["difference_from_49_for_demo_only"]
        diff_text = str(diff) if diff is not None else "不可相减（单位不同）"
        lines.append(
            "| {layer} | {current} | `{source}` | {demo} | {diff} |".format(
                layer=row["layer"],
                current=current,
                source=row["formula_denominator"],
                demo=row["z89_historical_demo_denominator"],
                diff=diff_text,
            )
        )
    return "\n".join(lines)


def build_artifacts() -> dict[str, bytes]:
    verified_inputs = _verify_inputs()
    denominator_crosswalk = _denominator_crosswalk()
    treatment = read_json(TREATMENT_CARDINALITY)
    control = read_json(CONTROL_CARDINALITY)

    adapter_contract = {
        "schema_version": "v02-c12-1-cardinality-score-adapter.v1",
        "status": "PASS_MANY_TO_MANY_ADAPTER_READY",
        "legacy_z97_core_rewritten": False,
        "selection_rule": "KEEP_EVERY_POSITIVE_FROZEN_VERDICT_EDGE",
        "duplicate_pair_rule": "REJECT",
        "supported_cardinalities": ["1:1", "N:1", "1:N", "N:M"],
        "aggregation_rule": {
            "rfu_layers": "count_each_unique_rfu_at_most_once",
            "claim_layers": "count_each_unique_claim_at_most_once",
            "edge_layer": "ASR_full_counts_each_selected_positive_edge",
            "cross_edge_semantic_stitching": "FORBIDDEN",
        },
        "regression_cases_required": [
            "N_TO_1",
            "ONE_TO_N",
            "MANY_TO_MANY_CROSS",
        ],
        "formal_chain_connected": False,
        "historical_scores_rewritten": False,
    }
    rescore_receipt = {
        "schema_version": "v02-c12-1-c5-rescore-receipt.v1",
        "status": CONCLUSION_MISSING,
        "selected_conclusion": CONCLUSION_MISSING,
        "reason": (
            "多对多保边与五层分母来源两项工程 P0 已清；双臂逐原子的 "
            "ANCHOR_PARTIAL、RFU 真值账、候选主张全集和五层语义判词仍缺。"
        ),
        "cleared_engineering_items": [
            "C8-P0-CARDINALITY-CONTRACT",
            "C8-P0-DENOMINATOR-CONTRACT",
        ],
        "remaining_missing_codes": [
            "TWO_ARM_ANCHOR_PARTIAL_VERDICTS_MISSING",
            "RFU_REFERENCE_ROWS_MISSING",
            "HEAD_QUALIFIER_ANCHOR_ATOMICITY_VERDICTS_MISSING",
            "APPROVED_RFU_WEIGHTS_MISSING",
            "CANDIDATE_CLAIM_UNIVERSE_MISSING",
            "JUDGE_ELIGIBILITY_MISSING",
        ],
        "gate_checks": {
            "anchor_partial_relative_reduction_at_least_50_percent": "MISSING_INPUT",
            "anchor_partial_declines_in_at_least_two_of_three_chapters": "MISSING_INPUT",
            "fcr_qcr_asr_ucr_no_regression": "MISSING_INPUT",
            "sop_at_least_0_98": "MISSING_INPUT",
            "zero_additional_model_calls_for_this_rescore": True,
            "c1_scoring_atom_total_remains_49": True,
            "dynamic_denominators_forced_to_49": False,
        },
        "evaluate_gate_invoked": False,
        "quality_result_registered": False,
        "winner_declaration_allowed": False,
        "causal_attribution_allowed": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    first_screen = {
        "schema_version": "v02-c12-1-first-screen.v1",
        "engineering_result": "PASS",
        "quality_result": "NOT_REGISTERED_MATERIALS_INSUFFICIENT",
        "arm_event_counts": {
            "control": control["produced_parent_event_total"],
            "treatment": treatment["produced_parent_event_total"],
        },
        "working_mapping_coverage": {
            "control": {
                "mapped_atom_total": control["mapped_atom_total"],
                "denominator": 49,
            },
            "treatment": {
                "mapped_atom_total": treatment["mapped_atom_total"],
                "denominator": 49,
            },
            "is_five_layer_score": False,
        },
        "working_mapping_links": {
            "control": control["atom_to_event_link_total"],
            "treatment": treatment["atom_to_event_link_total"],
            "may_substitute_semantic_match_edges": False,
        },
        "c8_p0_status": {
            "many_to_many_adapter": "CLEARED",
            "denominator_source_table": "CLEARED",
        },
        "directly_scoreable_five_layers": [],
        "five_layers_remaining_missing": denominator_crosswalk[
            "c5_layers_remaining_missing"
        ],
        "c5_selected_conclusion": CONCLUSION_MISSING,
        "worktree_preexisting_dirty": WORKTREE_BASELINE_BEFORE_C12,
        "outside_v02_preexisting_dirty_present": True,
        "outside_v02_preexisting_dirty_touched_by_c12": False,
        "concurrent_change_after_c12_started": {
            "path": "tools/v02_c13_downstream_consumer.py",
            "first_seen_local_time": "2026-07-25T20:57:28+08:00",
            "touched_by_c12": False,
            "effect": "tool_registry 单测因尚未登记而单独失败",
        },
        "model_api_calls": 0,
        "network_requests": 0,
        "git_commit_or_push": False,
    }
    authority = {
        "schema_version": "v02-c12-1-authority-receipt.v1",
        "notion_work_order_page": C12_WORK_ORDER_PAGE,
        "connector_readback_at": C12_READBACK_AT,
        "scope": "C12.1",
        "authorization": (
            "清 C8.3 两项 P0；多对多适配、五层分母对照、直接重跑 C5。"
        ),
        "input_receipts": verified_inputs,
        "legacy_z97_core_rewritten": False,
        "historical_c5_artifacts_rewritten": False,
    }
    report = f"""# C12.1 停点回包｜多对多计分适配＋五层分母对照＋C5复算

✅ 工程面通过：多对多关系不会再被一对一匹配器静默丢边，N:1、1:N、
多对多交叉三类回归均已单列。旧 Z97 核心和历史票据没有回写。

⚠️ C5 质量结论仍是 `{CONCLUSION_MISSING}`。这不是质量失败。两项工程
阻塞已经清掉，但双臂逐原子的锚承托判词、RFU 真值账、候选主张全集和
五层语义判词仍不存在，不能拿工作映射或 0 补空。

## 五层分母

{_markdown_denominator_table(denominator_crosswalk)}

49 继续只表示三章 8／16／25 个计分原子的覆盖宇宙。QCR、ASR、UCR、
SOP 的分母来源不同，禁止强改成 49，也禁止相加或合算。

## C5 重跑

- 两项 C8.3 工程阻塞：已清。
- 可直接产出五层成绩：0 层。
- 继续缺材料：FCR、QCR_full、ASR_full、UCR、SOP。
- 数字闸：没有调用；质量胜负：没有登记。
- 模型 API／网络请求：0／0。

## 保护面

- 没改 Z97 历史核心、旧 C5／C7／C8／C11 工件。
- 没碰现役链、正式金标、指针、122 条、默认链、outbox。
- 没提交、没推送 Git。

## 自修账

- 把批次适配器从 `tools/` 根层移回 C12 的 V02 候选区，避免违反工具出生门槛；
 复验＝工具登记测试在并发 C13 文件出现前通过。
- 修正“未匹配主张被审计字段误报为已匹配”；复验＝1 个 RFU、2 个主张、
 仅 1 条边时，已匹配 1、未匹配 `C2`、SOP 1／2。
- 修正 `--check` 在报告目录缺失时先建目录的问题；复验＝只报缺件、不写目录。

## 验收

- C12.1 精确回归：7／7 通过；相关联合回归：30／30 通过。
- V02 标记测试：266 通过。
- 整仓回归：并发 C13 文件出现前 1291 通过／40 预期跳过／1003 子测试通过；
  两项修复后排除其已知登记缺口，1289 通过／40 预期跳过／1003 子测试通过。
- 唯一并发红灯＝另一路在 20:57 新增
  `tools/v02_c13_downstream_consumer.py` 尚未登记；C12.1 未读取、未修改、未代修。
- 只读终审：P0／P1／P2＝0／0／0。

## 归属票

- 归属＝V02 新区候选。
- 触碰面＝只读 Z97／C5／C7／C8／C11 冻结件；只写 C12.1 V02 目录与本回包；
  LEGACY 写入 0。
- 测试三读数＝整仓有效回归 1289 通过／V02 266 通过／C12.1 新增失败 0。

来源：Codex
"""
    artifacts = {
        "adapter_contract.json": canonical_bytes(adapter_contract),
        "authority_receipt.json": canonical_bytes(authority),
        "c5_rescore_receipt.json": canonical_bytes(rescore_receipt),
        "first_screen_metrics.json": canonical_bytes(first_screen),
        "five_layer_denominator_crosswalk.json": canonical_bytes(
            denominator_crosswalk
        ),
        "C12_1_stop_receipt.md": report.encode("utf-8"),
    }
    preimage = {
        name: sha256_bytes(raw) for name, raw in sorted(artifacts.items())
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c12-1-artifact-manifest.v1",
            "file_total_excluding_self": len(preimage),
            "files": [
                {"path": name, "sha256": digest}
                for name, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(canonical_bytes(preimage)),
            "selected_conclusion": CONCLUSION_MISSING,
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
        raise C12CardinalityError(
            "C12.1 输出集合不闭合："
            f"missing={sorted(set(artifacts) - actual)} "
            f"unexpected={sorted(actual - set(artifacts))}"
        )
    for name, raw in artifacts.items():
        if (output_dir / name).read_bytes() != raw:
            raise C12CardinalityError(f"C12.1 输出字节漂移：{name}")


def write_or_verify(
    output_dir: Path = OUTPUT_DIR,
    report_dir: Path = REPORT_DIR,
    *,
    write: bool = True,
) -> dict[str, Any]:
    first = build_artifacts()
    second = build_artifacts()
    if first != second:
        raise C12CardinalityError("C12.1 连续两次构造不一致")
    _verify_or_write(output_dir, first, write=write)

    report_path = report_dir / "C12_1_停点回包.md"
    if write:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_bytes(first["C12_1_stop_receipt.md"])
    elif not report_path.is_file():
        raise C12CardinalityError("reports 停点回包不存在，--check 不会代建")
    if report_path.read_bytes() != first["C12_1_stop_receipt.md"]:
        raise C12CardinalityError("reports 停点回包与工件正文不一致")

    manifest = json.loads(first["artifact_manifest.json"].decode("utf-8"))
    return {
        "status": "PASS",
        "output_dir": display_path(output_dir),
        "report_path": display_path(report_path),
        "artifact_set_sha256": manifest["artifact_set_sha256"],
        "selected_conclusion": manifest["selected_conclusion"],
        "model_api_calls": 0,
        "network_requests": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V02 C12.1 多对多适配与 C5 复算")
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
