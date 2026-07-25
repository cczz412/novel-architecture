#!/usr/bin/env python3
"""V02/C8：列出 ANCHOR_PARTIAL 与五层计分缺口，不生成语义分。

本工具只读 C1、Z97 与 C7 冻结件，并观察 C8 同批产物是否已经存在。
它不会把机械路由当成语义命中，不会把缺失项补成 0，也不会调用模型或网络。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
C1_SCORE_TEMPLATE = (
    V02_ROOT / "C_anchor_first_experiment/gate/offline_score_template.json"
)
Z97_CORE = ROOT / "experiments/Z97_rfu_ucr_ledger_20260724/core.py"
C7_MAPPING = (
    V02_ROOT
    / "V02_C7_final_mapping_and_C5_rescore/mapping/final_treatment_mapping.json"
)
C7_CARDINALITY = (
    V02_ROOT
    / "V02_C7_final_mapping_and_C5_rescore/mapping/"
    "treatment_cardinality_metrics.json"
)
C7_MATERIAL_SUFFICIENCY = (
    V02_ROOT
    / "V02_C7_final_mapping_and_C5_rescore/c5_rescore/"
    "material_sufficiency.json"
)
C8_DIR = V02_ROOT / "V02_C8_control_mapping_and_interpretability"
DEFAULT_OUTPUT_DIR = C8_DIR / "gap_inventory"

CONTROL_MAPPING = C8_DIR / "control_mapping/final_control_mapping.json"
CONTROL_CARDINALITY = C8_DIR / "control_mapping/control_cardinality_metrics.json"
BIAS_AUDIT = C8_DIR / "consensus/audit_bias_receipt.json"
N10_TREATMENT = C8_DIR / "N10/treatment_reverse_table.json"
N10_CONTROL = C8_DIR / "N10/control_reverse_table.json"
N10_REASON_GAP = C8_DIR / "N10/unmatched_reason_gap.json"
N11_EMPTY = C8_DIR / "N11/empty_extraction_floor.json"
N11_RANDOM = C8_DIR / "N11/random_alignment_floor.json"
N11_BLOCK = C8_DIR / "N11/n11_block_receipt.json"

EXPECTED_INPUT_SHAS = {
    "c1_offline_score_template": (
        "d5b3cc43c7e5a4dd7a026ee31fd0c684d2276781407ec509bddc337fc0b9fbc6"
    ),
    "z97_core": (
        "f84c1f015777756a01a505ea25ada73ab796d42b6ca933a7f5c56a129d81974f"
    ),
    "c7_treatment_mapping": (
        "7ddfcb2b29ed7fc1340ebd323da8603f44a3bef7d6511bce474ecbbf78acea51"
    ),
    "c7_treatment_cardinality": (
        "72136f51d54b76ed4b7d156d6551ded35b2d8eccee57ba1e07d82368cc71b2d1"
    ),
    "c7_material_sufficiency": (
        "87c9c9cc6b2edfe8323bfa53b7aa2cacb790c341c5a565358baa994c90c6e329"
    ),
}
INPUT_PATHS = {
    "c1_offline_score_template": C1_SCORE_TEMPLATE,
    "z97_core": Z97_CORE,
    "c7_treatment_mapping": C7_MAPPING,
    "c7_treatment_cardinality": C7_CARDINALITY,
    "c7_material_sufficiency": C7_MATERIAL_SUFFICIENCY,
}

CASE_DENOMINATORS = {
    "B02-U0039": 8,
    "B03-U0041": 16,
    "B01-U0033": 25,
}
TOTAL_SCORING_ATOMS = 49
TREATMENT_PARENT_EVENTS = 37
CONTROL_PARENT_EVENTS = 129
MINIMUM_PARENT_CLAIMS = TREATMENT_PARENT_EVENTS + CONTROL_PARENT_EVENTS

BLOCKED = "BLOCKED"
MISSING = "MISSING"
READY = "READY"


class C8GapInventoryError(RuntimeError):
    """C8 缺口票不能从冻结输入安全重建。"""


def stable_json_bytes(value: Any) -> bytes:
    """编码为稳定、可复验的 JSON 字节。"""

    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    """读取文件并返回 SHA-256。"""

    if not path.is_file():
        raise C8GapInventoryError(f"冻结输入不存在：{path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    """读取 JSON。"""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise C8GapInventoryError(f"不能读取 JSON：{path}") from exc


def display_path(path: Path) -> str:
    """尽量返回仓库相对路径。"""

    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _bind_inputs() -> dict[str, dict[str, str]]:
    bindings: dict[str, dict[str, str]] = {}
    for label, path in INPUT_PATHS.items():
        observed = sha256_file(path)
        expected = EXPECTED_INPUT_SHAS[label]
        if observed != expected:
            raise C8GapInventoryError(f"冻结输入 SHA 漂移：{label}")
        bindings[label] = {
            "path": display_path(path),
            "sha256": observed,
        }
    return bindings


def _verify_contract_observations() -> dict[str, Any]:
    template = read_json(C1_SCORE_TEMPLATE)
    chapters = template.get("chapters")
    if not isinstance(chapters, Mapping):
        raise C8GapInventoryError("C1 离线模板缺 chapters")
    observed_denominators: dict[str, dict[str, int]] = {}
    for case_id, denominator in CASE_DENOMINATORS.items():
        chapter = chapters.get(case_id)
        if not isinstance(chapter, Mapping):
            raise C8GapInventoryError(f"C1 离线模板缺章节：{case_id}")
        layers = chapter.get("layers")
        if not isinstance(layers, Mapping):
            raise C8GapInventoryError(f"C1 离线模板缺五层：{case_id}")
        layer_denominators = {
            layer: int(row.get("denominator"))
            for layer, row in layers.items()
            if isinstance(row, Mapping)
        }
        if set(layer_denominators) != {
            "FCR",
            "QCR_full",
            "ASR_full",
            "UCR",
            "SOP",
        } or set(layer_denominators.values()) != {denominator}:
            raise C8GapInventoryError(f"C1 五层固定分母结构漂移：{case_id}")
        observed_denominators[case_id] = layer_denominators

    core_source = Z97_CORE.read_text(encoding="utf-8")
    required_signatures = (
        "def select_max_weight_matches(",
        "qcr = _ratio(qualifier_complete, head_covered)",
        "asr = _ratio(anchor_complete, len(selected))",
        "ucr = _ratio(usable_weight, total_weight)",
        "sop = _ratio(fully_supported_claims, len(validated_claims))",
    )
    missing_signatures = [
        signature for signature in required_signatures if signature not in core_source
    ]
    if missing_signatures:
        raise C8GapInventoryError(
            f"Z97 五层公式结构漂移：{missing_signatures}"
        )

    mapping = read_json(C7_MAPPING)
    cardinality = read_json(C7_CARDINALITY)
    if mapping.get("row_total") != TOTAL_SCORING_ATOMS:
        raise C8GapInventoryError("C7 实验臂映射不是 49 行")
    if cardinality.get("mapped_atom_total") != 25:
        raise C8GapInventoryError("C7 实验臂覆盖不再是 25/49")
    if cardinality.get("maximum_atoms_per_mapped_event") != 3:
        raise C8GapInventoryError("C7 N:1 最大合并度漂移")
    if cardinality.get("maximum_events_per_atom") != 2:
        raise C8GapInventoryError("C7 1:N 最大拆分度漂移")

    material = read_json(C7_MATERIAL_SUFFICIENCY)
    if material.get("selected_conclusion") != (
        "MATERIALS_INSUFFICIENT_CANNOT_ADJUDICATE"
    ):
        raise C8GapInventoryError("C7 材料不足结论发生漂移")
    return {
        "c1_layer_denominators": observed_denominators,
        "z97_formula_signatures_verified": list(required_signatures),
        "treatment_cardinality": {
            "mapped_atom_total": 25,
            "scoring_atom_total": 49,
            "maximum_atoms_per_mapped_event": 3,
            "maximum_events_per_atom": 2,
        },
        "c7_selected_conclusion": material["selected_conclusion"],
    }


def _blocking_conflicts() -> list[dict[str, Any]]:
    return [
        {
            "status": BLOCKED,
            "severity": "P0",
            "conflict_id": "C8-P0-CARDINALITY-CONTRACT",
            "plain_language": (
                "C7 工作映射允许多原子共用一事件，也允许一原子对应多事件；"
                "Z97 现有匹配器却只准一对一。直接套用会静默丢边。"
            ),
            "evidence": {
                "treatment_maximum_atoms_per_mapped_event": 3,
                "treatment_maximum_events_per_atom": 2,
                "z97_matching_contract": "ONE_TO_ONE_MAX_WEIGHT",
            },
            "must_be_decided_before_scoring": (
                "由 CZ 拍定五层如何承接 N:1／1:N，或另建不丢边的桥接计分合同。"
            ),
            "mechanical_routes_may_substitute_semantic_verdicts": False,
        },
        {
            "status": BLOCKED,
            "severity": "P0",
            "conflict_id": "C8-P0-DENOMINATOR-CONTRACT",
            "plain_language": (
                "C1 模板把五层分母都写成 49 原子；Z97 的限定完整率、"
                "锚支撑率和表面支撑率分别使用命中事实头、选中匹配、候选主张作分母。"
                "两套数字不能直接互填。"
            ),
            "evidence": {
                "c1_each_layer_chapter_denominators_sum_to": 49,
                "z97_denominators": {
                    "FCR": "RFU_TOTAL",
                    "QCR_full": "HEAD_COVERED",
                    "ASR_full": "SELECTED_MATCHES",
                    "UCR": "TOTAL_RFU_WEIGHT",
                    "SOP": "CANDIDATE_CLAIMS",
                },
            },
            "must_be_decided_before_scoring": (
                "由 CZ 拍定 C1 与 Z97 的桥接口径；此前五层只能列缺口，不能填数。"
            ),
            "missing_values_may_be_filled_with_zero": False,
        },
    ]


def _gap_rows() -> list[dict[str, Any]]:
    shared = {
        "scoring_atom_total_per_arm": TOTAL_SCORING_ATOMS,
        "arm_total": 2,
        "mechanical_route_is_semantic_verdict": False,
    }
    return [
        {
            "layer": "ANCHOR_PARTIAL",
            "status": BLOCKED,
            "missing_inputs": [
                "49 原子逐条的最小支撑义务定义与冻结身份",
                "双臂逐原子、逐主张的锚承托判词",
                "N:1／1:N 下同一原子的支撑义务如何合并的已拍合同",
                "合格裁判资格票与判词来源 SHA",
            ],
            "required_labor": ["需合议", "需 CZ 拍"],
            "estimated_rows": {
                "minimum_atom_arm_outcomes": 98,
                "exact_component_verdict_rows": None,
                "why_exact_is_missing": "每条候选主张拆成几个部件尚未冻结",
            },
            "denominator_status": "MISSING_ADJUDICATED_SUPPORT_OBLIGATIONS",
            **shared,
        },
        {
            "layer": "FCR",
            "status": BLOCKED,
            "missing_inputs": [
                "49 条 RFU 的事实头真值定义",
                "双臂候选事件拆出的 CandidateClaim 全量清单",
                "RFU 与候选主张间冻结的 head_match 判词",
                "解决 N:1／1:N 与 Z97 一对一冲突的桥接合同",
            ],
            "required_labor": ["纯程序", "需合议", "需 CZ 拍"],
            "estimated_rows": {
                "rfu_truth_rows": 49,
                "minimum_parent_candidate_claim_rows": 166,
                "minimum_atom_arm_outcomes": 98,
                "exact_match_verdict_edges": None,
            },
            "denominator_status": "BLOCKED_BY_CARDINALITY_CONTRACT",
            **shared,
        },
        {
            "layer": "QCR_full",
            "status": BLOCKED,
            "missing_inputs": [
                "49 条 RFU 的必要限定清单",
                "候选主张逐条限定字段",
                "每个必要限定的 present／missing／contradicted／unclear 判词",
                "C1 固定 49 与 Z97 动态 head_covered 分母的桥接合同",
            ],
            "required_labor": ["纯程序", "需合议", "需 CZ 拍"],
            "estimated_rows": {
                "minimum_atom_arm_outcomes": 98,
                "exact_qualifier_item_verdict_rows": None,
                "why_exact_is_missing": "每条 RFU 有几个必要限定尚未冻结",
            },
            "denominator_status": "BLOCKED_BY_DENOMINATOR_CONTRACT",
            **shared,
        },
        {
            "layer": "ASR_full",
            "status": BLOCKED,
            "missing_inputs": [
                "双臂 CandidateClaim 的 claim_components 全量拆分",
                "每个主张部件的 supported／partial／unsupported／wrong_anchor 判词",
                "N:1／1:N 下 selected_matches 分母桥接合同",
            ],
            "required_labor": ["纯程序", "需合议", "需 CZ 拍"],
            "estimated_rows": {
                "minimum_parent_candidate_claim_rows": 166,
                "minimum_anchor_component_verdict_rows": 166,
                "exact_anchor_component_verdict_rows": None,
            },
            "denominator_status": "BLOCKED_BY_BOTH_P0_CONFLICTS",
            **shared,
        },
        {
            "layer": "UCR",
            "status": BLOCKED,
            "missing_inputs": [
                "49 条 RFU 的已拍权重与 criticality",
                "FCR、QCR_full、ASR_full 与 atomicity 的冻结判词",
                "N:1／1:N 下可用事实权重只计一次的桥接合同",
            ],
            "required_labor": ["纯程序", "需合议", "需 CZ 拍"],
            "estimated_rows": {
                "rfu_weight_rows": 49,
                "minimum_atom_arm_usability_outcomes": 98,
                "exact_match_verdict_edges": None,
            },
            "denominator_status": "MISSING_APPROVED_RFU_WEIGHTS",
            **shared,
        },
        {
            "layer": "SOP",
            "status": BLOCKED,
            "missing_inputs": [
                "双臂完整 CandidateClaim 宇宙与 candidate_universe_complete 票",
                "每条候选主张的全部部件锚支撑判词",
                "合格裁判资格票",
                "C1 固定 49 与 Z97 候选主张数分母的桥接合同",
            ],
            "required_labor": ["纯程序", "需合议", "需 CZ 拍"],
            "estimated_rows": {
                "minimum_parent_candidate_claim_rows": 166,
                "minimum_candidate_claim_support_outcomes": 166,
                "exact_candidate_claim_rows": None,
            },
            "denominator_status": "BLOCKED_BY_DENOMINATOR_CONTRACT",
            **shared,
        },
    ]


def _optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = read_json(path)
    if not isinstance(value, Mapping):
        raise C8GapInventoryError(f"可选票据不是对象：{path}")
    return dict(value)


def _file_state(path: Path) -> dict[str, Any]:
    document = _optional_json(path)
    if document is None:
        return {
            "status": MISSING,
            "path": display_path(path),
            "sha256": None,
            "reported_status": None,
        }
    return {
        "status": READY,
        "path": display_path(path),
        "sha256": sha256_file(path),
        "reported_status": document.get("status"),
    }


def _control_mapping_state() -> tuple[dict[str, Any], dict[str, Any]]:
    mapping_state = _file_state(CONTROL_MAPPING)
    cardinality_state = _file_state(CONTROL_CARDINALITY)
    if mapping_state["status"] == MISSING:
        return mapping_state, cardinality_state
    mapping = read_json(CONTROL_MAPPING)
    if mapping.get("row_total") != TOTAL_SCORING_ATOMS:
        mapping_state["status"] = BLOCKED
        mapping_state["reason"] = "CONTROL_MAPPING_ROW_TOTAL_IS_NOT_49"
    if cardinality_state["status"] == READY:
        cardinality = read_json(CONTROL_CARDINALITY)
        if cardinality.get("scoring_atom_total") != TOTAL_SCORING_ATOMS:
            cardinality_state["status"] = BLOCKED
            cardinality_state["reason"] = "CONTROL_CARDINALITY_TOTAL_IS_NOT_49"
    return mapping_state, cardinality_state


def _n10_state() -> dict[str, Any]:
    treatment = _file_state(N10_TREATMENT)
    control = _file_state(N10_CONTROL)
    reason_gap = _file_state(N10_REASON_GAP)
    gap_total: int | None = None
    if reason_gap["status"] == READY:
        document = read_json(N10_REASON_GAP)
        raw = document.get("gap_total")
        gap_total = raw if isinstance(raw, int) else None
    complete = bool(
        treatment["status"] == READY
        and control["status"] == READY
        and control["reported_status"] not in {"BLOCKED_CONTROL_MAPPING", BLOCKED}
        and gap_total == 0
    )
    return {
        "status": READY if complete else BLOCKED,
        "complete": complete,
        "treatment": treatment,
        "control": control,
        "reason_gap": reason_gap,
        "unmatched_reason_gap_total": gap_total,
        "missing_counts_are_not_zero_filled": True,
    }


def _n11_state() -> dict[str, Any]:
    empty = _file_state(N11_EMPTY)
    random = _file_state(N11_RANDOM)
    block = _file_state(N11_BLOCK)
    complete = bool(
        empty["status"] == READY
        and random["status"] == READY
        and random["reported_status"] not in {"BLOCKED_CONTROL_MAPPING", BLOCKED}
    )
    return {
        "status": READY if complete else BLOCKED,
        "complete": complete,
        "empty_extraction_floor": empty,
        "random_alignment_floor": random,
        "block_receipt": block,
        "five_layer_floor_values": None,
        "five_layer_floor_values_status": "NOT_DEFINED_DO_NOT_INVENT",
    }


def _bias_state() -> dict[str, Any]:
    evidence = _file_state(BIAS_AUDIT)
    if evidence["status"] == MISSING:
        return {
            "status": MISSING,
            "complete": False,
            "consistency": None,
            "evidence": evidence,
        }
    document = read_json(BIAS_AUDIT)
    rows = document.get("rows")
    complete = bool(
        document.get("status") == "AVAILABLE"
        and document.get("audit_packet_total") == 6
        and document.get("comparable_total") == 6
        and document.get("matches_old_working_mapping_total") == 6
        and document.get("consistency_rate") == 1.0
        and isinstance(rows, list)
        and len(rows) == 6
        and all(
            isinstance(row, Mapping)
            and row.get("status") == "COMPARABLE"
            and row.get("matches_old_working_mapping") is True
            and row.get("old_mapping_changed") is False
            for row in rows
        )
    )
    return {
        "status": READY if complete else BLOCKED,
        "complete": complete,
        "consistency": (
            {
                "matched_total": 6,
                "comparable_total": 6,
                "fraction": "6/6",
                "rate": 1.0,
                "below_5_of_6_risk": False,
            }
            if complete
            else None
        ),
        "evidence": evidence,
    }


def _source_counts(mapping: Mapping[str, Any]) -> dict[str, int]:
    rows = mapping.get("rows")
    if not isinstance(rows, list):
        raise C8GapInventoryError("映射缺 rows")
    return dict(
        sorted(
            Counter(
                str(row.get("mapping_source"))
                for row in rows
                if isinstance(row, Mapping)
            ).items()
        )
    )


def _first_screen_readiness() -> dict[str, Any]:
    treatment_mapping = read_json(C7_MAPPING)
    treatment_cardinality = read_json(C7_CARDINALITY)
    control_mapping_state, control_cardinality_state = _control_mapping_state()
    control_mapping = (
        read_json(CONTROL_MAPPING)
        if control_mapping_state["status"] == READY
        else None
    )
    control_cardinality = (
        read_json(CONTROL_CARDINALITY)
        if control_cardinality_state["status"] == READY
        else None
    )
    n10 = _n10_state()
    n11 = _n11_state()
    bias = _bias_state()

    slots = [
        {
            "slot": 1,
            "label": "两臂父事件数",
            "status": READY,
            "value": {
                "control": CONTROL_PARENT_EVENTS,
                "treatment": TREATMENT_PARENT_EVENTS,
            },
        },
        {
            "slot": 2,
            "label": "49 原子覆盖",
            "status": (
                READY if control_cardinality is not None else MISSING
            ),
            "value": {
                "control": (
                    {
                        "mapped_atom_total": control_cardinality.get(
                            "mapped_atom_total"
                        ),
                        "coverage_rate": control_cardinality.get("coverage_rate"),
                    }
                    if control_cardinality is not None
                    else None
                ),
                "treatment": {
                    "mapped_atom_total": treatment_cardinality["mapped_atom_total"],
                    "coverage_rate": treatment_cardinality["coverage_rate"],
                },
            },
            "mechanical_route_is_not_semantic_coverage": True,
        },
        {
            "slot": 3,
            "label": "合并度",
            "status": (
                READY if control_cardinality is not None else MISSING
            ),
            "value": {
                "control": (
                    {
                        "histogram": control_cardinality.get(
                            "mapped_event_degree_histogram"
                        ),
                        "maximum": control_cardinality.get(
                            "maximum_atoms_per_mapped_event"
                        ),
                    }
                    if control_cardinality is not None
                    else None
                ),
                "treatment": {
                    "histogram": treatment_cardinality[
                        "mapped_event_degree_histogram"
                    ],
                    "maximum": treatment_cardinality[
                        "maximum_atoms_per_mapped_event"
                    ],
                },
            },
        },
        {
            "slot": 4,
            "label": "拆分度",
            "status": (
                READY if control_cardinality is not None else MISSING
            ),
            "value": {
                "control": (
                    {
                        "histogram": control_cardinality.get(
                            "atom_split_degree_histogram"
                        ),
                        "maximum": control_cardinality.get(
                            "maximum_events_per_atom"
                        ),
                    }
                    if control_cardinality is not None
                    else None
                ),
                "treatment": {
                    "histogram": treatment_cardinality[
                        "atom_split_degree_histogram"
                    ],
                    "maximum": treatment_cardinality[
                        "maximum_events_per_atom"
                    ],
                },
            },
        },
        {
            "slot": 5,
            "label": "N10 未命中三分表",
            "status": n10["status"],
            "value": n10 if n10["complete"] else None,
            "diagnostic": n10,
        },
        {
            "slot": 6,
            "label": "N11 两条地板线",
            "status": n11["status"],
            "value": n11 if n11["complete"] else None,
            "diagnostic": n11,
        },
        {
            "slot": 7,
            "label": "判词来源构成",
            "status": READY if control_mapping is not None else MISSING,
            "value": {
                "control": (
                    _source_counts(control_mapping)
                    if control_mapping is not None
                    else None
                ),
                "treatment": _source_counts(treatment_mapping),
            },
        },
        {
            "slot": 8,
            "label": "偏袒检测自洽一致率",
            "status": bias["status"],
            "value": bias["consistency"],
            "diagnostic": bias,
        },
        {
            "slot": 9,
            "label": "人工判断条数与合议条数",
            "status": READY if control_mapping is not None else MISSING,
            "value": {
                "control": (
                    _source_counts(control_mapping)
                    if control_mapping is not None
                    else None
                ),
                "treatment": _source_counts(treatment_mapping),
            },
        },
    ]
    return {
        "status": BLOCKED,
        "schema_version": "v02-c8-first-screen-readiness.v1",
        "all_nine_slots_ready": all(row["status"] == READY for row in slots),
        "slots": slots,
        "control_mapping": control_mapping_state,
        "control_cardinality": control_cardinality_state,
        "semantic_five_layer_values": None,
        "semantic_five_layer_status": "BLOCKED_BY_GAP_INVENTORY",
        "missing_values_are_not_zero": True,
        "coverage_guard": {
            "known_treatment_coverage": 25 / 49,
            "known_treatment_coverage_fraction": "25/49",
            "anti_spin_rule": (
                "错误率下降但覆盖也下降时，只能登记疑似以少产出换低错误率，"
                "不得判实验过闸。"
            ),
            "control_fragmentation_rule": (
                "对照臂 129 条事件若只换来相近或更低覆盖，只登记碎词风险，"
                "不得替实验臂下胜负结论。"
            ),
        },
    }


def build_documents() -> tuple[dict[str, Any], dict[str, Any], str]:
    """构造三份确定性输出。"""

    bindings = _bind_inputs()
    observations = _verify_contract_observations()
    gap_inventory = {
        "status": BLOCKED,
        "schema_version": "v02-c8-gap-inventory.v1",
        "blocking_conflicts": _blocking_conflicts(),
        "score_calculation_invoked": False,
        "semantic_values_emitted": False,
        "mechanical_routes_counted_as_semantic_hits": False,
        "missing_values_filled_with_zero": False,
        "input_bindings": bindings,
        "contract_observations": observations,
        "common_prerequisites": [
            {
                "status": BLOCKED,
                "item": "JUDGE_ELIGIBILITY",
                "estimated_rows": 2,
                "required_labor": ["需 CZ 拍"],
                "reason": "双臂各需独立裁判资格票；C1 现状不准签 judge green。",
            },
            {
                "status": BLOCKED,
                "item": "CANDIDATE_UNIVERSE_COMPLETE",
                "estimated_rows": 2,
                "required_labor": ["纯程序", "需合议"],
                "reason": "SOP 只有在双臂候选主张全集完整时才可解释。",
            },
            {
                "status": BLOCKED,
                "item": "RFU_REFERENCE_CONTRACT",
                "estimated_rows": 49,
                "required_labor": ["需合议", "需 CZ 拍"],
                "reason": "现有 49 原子尚未补齐 Z97 RFU 的事实头、限定、权重和最小支撑集。",
            },
        ],
        "gaps": _gap_rows(),
        "estimated_scale_summary": {
            "rfu_truth_rows": 49,
            "atom_arm_outcome_rows_minimum": 98,
            "parent_event_rows_minimum": MINIMUM_PARENT_CLAIMS,
            "claim_component_and_verdict_rows_exact": None,
            "why_exact_is_missing": (
                "候选事件尚未机械拆成完整 CandidateClaim，且 N:1／1:N 桥接合同未拍。"
            ),
        },
        "next_decisions_required": [
            "拍定 N:1／1:N 与 Z97 一对一评分器的桥接合同",
            "拍定 C1 固定 49 分母与 Z97 动态分母的桥接合同",
            "拍定 49 条 RFU 真值补齐与双臂独立裁判资格",
        ],
        "quality_result_registered": False,
    }
    readiness = _first_screen_readiness()
    readme = _render_readme(gap_inventory, readiness)
    return gap_inventory, readiness, readme


def _render_readme(
    gap_inventory: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> str:
    ready_slots = sum(
        row["status"] == READY for row in readiness["slots"]  # type: ignore[index]
    )
    lines = [
        "# BLOCKED：两项 P0 合同冲突未解，禁止计算五层成绩",
        "",
        "这份工件只回答“还缺什么”，不产生任何新的语义分。",
        "",
        "- P0 BLOCKED：C7 允许 N:1／1:N，Z97 现有匹配器只准一对一。",
        "- P0 BLOCKED：C1 把五层分母都写成 49，Z97 有三层使用动态分母。",
        "- `ANCHOR_PARTIAL` 与五层都没有拿机械路由冒充语义命中。",
        "- 缺失值保持为空，不补成 0。",
        "",
        f"首屏 9 项当前可直接出 {ready_slots} 项；其余均显式写成缺件或阻断。",
        "实验臂已知覆盖是 25／49；在对照覆盖与双臂语义判词齐全前，不能判实验胜负。",
        "",
        "输入冻结件：",
    ]
    for label, row in gap_inventory["input_bindings"].items():  # type: ignore[index]
        lines.append(f"- {label}：`{row['sha256']}`")
    lines.extend(
        [
            "",
            "下一步只应补齐缺口并拍两项桥接合同；不要调阈值、改分母或填假分。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def build_artifacts() -> dict[str, bytes]:
    """返回三份确定性工件。"""

    gap_inventory, readiness, readme = build_documents()
    return {
        "gap_inventory.json": stable_json_bytes(gap_inventory),
        "first_screen_readiness.json": stable_json_bytes(readiness),
        "README.md": readme.encode("utf-8"),
    }


def write_or_verify(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    """写出工件；已有字节不同时拒绝覆盖。"""

    artifacts = build_artifacts()
    output_dir.mkdir(parents=True, exist_ok=True)
    receipts: dict[str, str] = {}
    for name, raw in artifacts.items():
        path = output_dir / name
        if path.exists() and path.read_bytes() != raw:
            raise C8GapInventoryError(f"已有工件与重建结果不一致：{path}")
        if not path.exists():
            path.write_bytes(raw)
        receipts[name] = hashlib.sha256(raw).hexdigest()
    return receipts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    artifacts = build_artifacts()
    if args.check:
        for name, expected in artifacts.items():
            path = args.output_dir / name
            if not path.is_file() or path.read_bytes() != expected:
                raise C8GapInventoryError(f"工件缺失或漂移：{path}")
        return 0
    receipts = write_or_verify(args.output_dir)
    print(json.dumps(receipts, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
