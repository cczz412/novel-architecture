#!/usr/bin/env python3
"""V02/C8 N11：定义空抽取与随机对齐地板线。

随机对齐使用章内、双臂配对的 SHA256 排序置换，不依赖 Python 随机库，
不允许挑种子。缺对照映射时保持 C8 历史阻断分支；只有 C11 映射与冻结
票同时命中预写 SHA、且工作映射身份过闸后，才激活双臂机械地板。无论
哪个阶段，本工具都不伪造 ANCHOR_PARTIAL 或五层语义分。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
C8_ROOT = V02_ROOT / "V02_C8_control_mapping_and_interpretability"
DEFAULT_OUTPUT_DIR = C8_ROOT / "N11"

TREATMENT_MAPPING = (
    V02_ROOT
    / "V02_C7_final_mapping_and_C5_rescore/mapping/"
    "final_treatment_mapping.json"
)
CONTROL_MAPPING = C8_ROOT / "control_mapping/final_control_mapping.json"
CONTROL_FREEZE_RECEIPT = (
    C8_ROOT / "control_mapping/mapping_freeze_receipt.json"
)
CONTROL_READINESS = (
    V02_ROOT
    / "V02_C7_final_mapping_and_C5_rescore/c5_rescore/"
    "control_mapping_readiness.json"
)

EXPECTED_TREATMENT_MAPPING_SHA = (
    "7ddfcb2b29ed7fc1340ebd323da8603f44a3bef7d6511bce474ecbbf78acea51"
)
EXPECTED_CONTROL_READINESS_SHA = (
    "af88f4e070a9b8ee199f8270bb7e5e5206683a9f70dd38d74b36f0f0387997a6"
)
EXPECTED_CONTROL_MAPPING_SHA = (
    "f216ab50c94fbc7069b5b1561c24e4cac709d669012623bd8296198b801cc3d7"
)
EXPECTED_CONTROL_FREEZE_RECEIPT_SHA = (
    "b69c4747032fadb023915de900f153ed1af71e2c27f7b28de0d51598ff29c69a"
)
CASE_ORDER = ("B02-U0039", "B03-U0041", "B01-U0033")
CASE_DENOMINATORS = {
    "B02-U0039": 8,
    "B03-U0041": 16,
    "B01-U0033": 25,
}

CONTRACT_VERSION = "v02-c8-n11-floor-contract.v1"
BLOCKED_CONTROL = "BLOCKED_CONTROL_MAPPING"
ACTIVE_BOTH_ARMS = "BOTH_ARMS_MECHANICAL_FLOORS_READY"
EXPECTED_CONDITIONAL_INVALIDATION = {
    "trigger": "CZ_APPROVES_X04",
    "required_action": "INVALIDATE_AND_RECOMPUTE_AS_BOUNDS",
    "active_now": False,
    "current_artifact_remains_unconditional_truth": False,
}
MIN_TRIAL_COUNT = 100
DEFAULT_TRIAL_COUNT = 1000
QUANTILE_POINTS = (0.05, 0.25, 0.5, 0.75, 0.95)

Edge = tuple[str, str, str]


class N11Error(RuntimeError):
    """N11 不能从冻结件安全生成。"""


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
        raise N11Error(f"冻结件不存在：{path}")
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _verified_control_mapping() -> tuple[dict[str, Any], dict[str, str]]:
    mapping_sha = sha256_file(CONTROL_MAPPING)
    if mapping_sha != EXPECTED_CONTROL_MAPPING_SHA:
        raise N11Error("C11 对照工作映射 SHA 漂移")
    receipt_sha = sha256_file(CONTROL_FREEZE_RECEIPT)
    if receipt_sha != EXPECTED_CONTROL_FREEZE_RECEIPT_SHA:
        raise N11Error("C11 对照映射冻结票 SHA 漂移")

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
        raise N11Error("C11 对照映射工作身份或冻结边界漂移")
    _mapping_rows(mapping)
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
        raise N11Error("C11 对照映射冻结票身份或保护边界漂移")
    return mapping, {
        "mapping_sha256": mapping_sha,
        "freeze_receipt_sha256": receipt_sha,
    }


def _validate_trial_count(trial_count: int) -> None:
    if isinstance(trial_count, bool) or trial_count < MIN_TRIAL_COUNT:
        raise N11Error(
            f"随机对齐至少需要 {MIN_TRIAL_COUNT} 次，收到 {trial_count}"
        )


def _mapping_rows(mapping: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = mapping.get("rows")
    if not isinstance(rows, list) or len(rows) != 49:
        raise N11Error("映射不是 49 行冻结原子表")
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    normalized: list[Mapping[str, Any]] = []
    for ordinal, raw in enumerate(rows, 1):
        if not isinstance(raw, Mapping):
            raise N11Error("映射含非对象行")
        case_id = raw.get("case_id")
        atom_id = raw.get("atom_id")
        event_ids = raw.get("candidate_event_ids")
        if (
            raw.get("ordinal") != ordinal
            or case_id not in CASE_ORDER
            or not isinstance(atom_id, str)
            or atom_id in seen
            or not isinstance(event_ids, list)
            or any(not isinstance(value, str) for value in event_ids)
            or len(event_ids) != len(set(event_ids))
        ):
            raise N11Error("映射原子身份、顺序或事件列表非法")
        seen.add(atom_id)
        counts[str(case_id)] += 1
        normalized.append(raw)
    if counts != CASE_DENOMINATORS:
        raise N11Error("映射章分母漂移")
    return normalized


def atom_ids_by_case(
    mapping: Mapping[str, Any],
) -> dict[str, list[str]]:
    result = {case_id: [] for case_id in CASE_ORDER}
    for row in _mapping_rows(mapping):
        result[str(row["case_id"])].append(str(row["atom_id"]))
    return result


def mapping_edges(mapping: Mapping[str, Any]) -> set[Edge]:
    edges: set[Edge] = set()
    for row in _mapping_rows(mapping):
        case_id = str(row["case_id"])
        atom_id = str(row["atom_id"])
        for event_id in row["candidate_event_ids"]:
            edge = (case_id, atom_id, str(event_id))
            if edge in edges:
                raise N11Error("映射含重复边")
            edges.add(edge)
    return edges


def atom_set_sha256(mapping: Mapping[str, Any]) -> str:
    rows = [
        {"case_id": str(row["case_id"]), "atom_id": str(row["atom_id"])}
        for row in _mapping_rows(mapping)
    ]
    return sha256_bytes(canonical_bytes(rows))


def derive_root_seed(
    *,
    atom_set_sha: str,
    treatment_mapping_sha: str,
    control_mapping_sha: str,
    trial_count: int,
) -> tuple[str, dict[str, Any]]:
    _validate_trial_count(trial_count)
    for label, digest in {
        "atom_set_sha": atom_set_sha,
        "treatment_mapping_sha": treatment_mapping_sha,
        "control_mapping_sha": control_mapping_sha,
    }.items():
        if len(digest) != 64 or any(
            value not in "0123456789abcdef" for value in digest
        ):
            raise N11Error(f"{label} 不是小写 SHA256")
    preimage = {
        "contract_version": CONTRACT_VERSION,
        "atom_set_sha256": atom_set_sha,
        "treatment_mapping_sha256": treatment_mapping_sha,
        "control_mapping_sha256": control_mapping_sha,
        "trial_count": trial_count,
        "permutation": "paired_sha256_rank_within_case",
        "quantile_method": "nearest_rank",
    }
    return sha256_bytes(canonical_bytes(preimage)), preimage


def paired_permutation(
    atom_ids_by_case_value: Mapping[str, Sequence[str]],
    root_seed: str,
    trial_index: int,
) -> dict[str, str]:
    if trial_index < 0:
        raise N11Error("trial_index 不能为负数")
    if len(root_seed) != 64:
        raise N11Error("root_seed 不是 SHA256")
    result: dict[str, str] = {}
    for case_id in CASE_ORDER:
        atom_ids = list(atom_ids_by_case_value.get(case_id, []))
        if (
            len(atom_ids) != CASE_DENOMINATORS[case_id]
            or len(atom_ids) != len(set(atom_ids))
        ):
            raise N11Error(f"{case_id} 原子集合不能生成章内双射")
        source = sorted(atom_ids)
        destination = sorted(
            atom_ids,
            key=lambda atom_id: (
                hashlib.sha256(
                    (
                        f"{root_seed}|{trial_index}|{case_id}|{atom_id}"
                    ).encode("utf-8")
                ).hexdigest(),
                atom_id,
            ),
        )
        result.update(zip(source, destination, strict=True))
    if (
        len(result) != 49
        or set(result) != set(result.values())
        or any(
            next(
                case_id
                for case_id, atom_ids in atom_ids_by_case_value.items()
                if atom_id in atom_ids
            )
            != next(
                case_id
                for case_id, atom_ids in atom_ids_by_case_value.items()
                if target in atom_ids
            )
            for atom_id, target in result.items()
        )
    ):
        raise N11Error("SHA 排序没有形成章内 49 原子双射")
    return result


def permute_edges(edges: Iterable[Edge], permutation: Mapping[str, str]) -> set[Edge]:
    randomized: set[Edge] = set()
    for case_id, atom_id, event_id in edges:
        target = permutation.get(atom_id)
        if not isinstance(target, str):
            raise N11Error(f"置换缺原子：{atom_id}")
        randomized.add((case_id, target, event_id))
    if len(randomized) != len(set(edges)):
        raise N11Error("置换改变了边总数")
    return randomized


def cardinality_signature(edges: Iterable[Edge]) -> dict[str, Any]:
    edge_set = set(edges)
    atom_to_events: dict[tuple[str, str], set[str]] = defaultdict(set)
    event_to_atoms: dict[tuple[str, str], set[str]] = defaultdict(set)
    for case_id, atom_id, event_id in edge_set:
        atom_to_events[(case_id, atom_id)].add(event_id)
        event_to_atoms[(case_id, event_id)].add(atom_id)
    split = Counter(len(values) for values in atom_to_events.values())
    merge = Counter(len(values) for values in event_to_atoms.values())
    return {
        "edge_total": len(edge_set),
        "mapped_atom_total": len(atom_to_events),
        "mapped_event_total": len(event_to_atoms),
        "split_degree_histogram": {
            str(key): value for key, value in sorted(split.items())
        },
        "merge_degree_histogram": {
            str(key): value for key, value in sorted(merge.items())
        },
    }


def comparison_metrics(
    reference_edges: Iterable[Edge],
    predicted_edges: Iterable[Edge],
    all_atoms: Iterable[tuple[str, str]],
) -> dict[str, Any]:
    reference = set(reference_edges)
    predicted = set(predicted_edges)
    atoms = list(all_atoms)
    intersection = reference & predicted
    precision = len(intersection) / len(predicted) if predicted else None
    recall = len(intersection) / len(reference) if reference else None
    if precision is None or recall is None:
        f1 = None
    elif precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    reference_by_atom: dict[tuple[str, str], set[str]] = defaultdict(set)
    predicted_by_atom: dict[tuple[str, str], set[str]] = defaultdict(set)
    for case_id, atom_id, event_id in reference:
        reference_by_atom[(case_id, atom_id)].add(event_id)
    for case_id, atom_id, event_id in predicted:
        predicted_by_atom[(case_id, atom_id)].add(event_id)

    exact_count = sum(
        reference_by_atom[atom] == predicted_by_atom[atom] for atom in atoms
    )
    reference_positive_atoms = [
        atom for atom in atoms if reference_by_atom[atom]
    ]
    positive_exact_count = sum(
        reference_by_atom[atom] == predicted_by_atom[atom]
        for atom in reference_positive_atoms
    )
    mapped_status_equal_count = sum(
        bool(reference_by_atom[atom]) == bool(predicted_by_atom[atom])
        for atom in atoms
    )
    predicted_mapped_total = sum(
        bool(predicted_by_atom[atom]) for atom in atoms
    )
    return {
        "reference_edge_total": len(reference),
        "predicted_edge_total": len(predicted),
        "correct_edge_total": len(intersection),
        "edge_precision": precision,
        "edge_recall": recall,
        "edge_f1": f1,
        "atom_exact_event_set_count": exact_count,
        "atom_exact_event_set_accuracy": exact_count / len(atoms),
        "reference_mapped_atom_total": len(reference_positive_atoms),
        "positive_atom_exact_count": positive_exact_count,
        "positive_atom_exact_recall": (
            positive_exact_count / len(reference_positive_atoms)
            if reference_positive_atoms
            else None
        ),
        "mapped_status_equal_count": mapped_status_equal_count,
        "mapped_status_accuracy": mapped_status_equal_count / len(atoms),
        "predicted_mapped_atom_total": predicted_mapped_total,
        "predicted_coverage_rate": predicted_mapped_total / len(atoms),
    }


def nearest_rank(values: Sequence[float], probability: float) -> float:
    if not values:
        raise N11Error("空序列不能计算分位数")
    if probability <= 0 or probability > 1:
        raise N11Error("nearest-rank 分位点必须在 (0, 1] 内")
    ordered = sorted(values)
    index = math.ceil(probability * len(ordered)) - 1
    return ordered[index]


def _metric_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    metric_names = (
        "edge_precision",
        "edge_recall",
        "edge_f1",
        "atom_exact_event_set_accuracy",
        "positive_atom_exact_recall",
        "mapped_status_accuracy",
    )
    result: dict[str, Any] = {}
    for name in metric_names:
        values = [
            float(row[name]) for row in rows if row.get(name) is not None
        ]
        result[name] = {
            "defined_trial_total": len(values),
            "mean": fmean(values) if values else None,
            "quantiles_nearest_rank": {
                f"p{int(probability * 100):02d}": nearest_rank(
                    values, probability
                )
                for probability in QUANTILE_POINTS
            }
            if values
            else None,
        }
    return result


def run_random_alignment_floors(
    treatment_mapping: Mapping[str, Any],
    control_mapping: Mapping[str, Any],
    *,
    treatment_mapping_sha: str,
    control_mapping_sha: str,
    trial_count: int = DEFAULT_TRIAL_COUNT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_trial_count(trial_count)
    treatment_atoms = atom_ids_by_case(treatment_mapping)
    control_atoms = atom_ids_by_case(control_mapping)
    if treatment_atoms != control_atoms:
        raise N11Error("双臂 49 原子身份或章内顺序不一致")

    atom_sha = atom_set_sha256(treatment_mapping)
    root_seed, seed_preimage = derive_root_seed(
        atom_set_sha=atom_sha,
        treatment_mapping_sha=treatment_mapping_sha,
        control_mapping_sha=control_mapping_sha,
        trial_count=trial_count,
    )
    all_atoms = [
        (case_id, atom_id)
        for case_id in CASE_ORDER
        for atom_id in treatment_atoms[case_id]
    ]
    references = {
        "treatment": mapping_edges(treatment_mapping),
        "control": mapping_edges(control_mapping),
    }
    reference_signatures = {
        arm: cardinality_signature(edges)
        for arm, edges in references.items()
    }
    rows_by_arm: dict[str, list[dict[str, Any]]] = {
        "treatment": [],
        "control": [],
    }
    permutation_receipts: list[dict[str, Any]] = []

    for trial_index in range(trial_count):
        permutation = paired_permutation(
            treatment_atoms, root_seed, trial_index
        )
        permutation_sha = sha256_bytes(canonical_bytes(permutation))
        permutation_receipts.append(
            {
                "trial_index": trial_index,
                "permutation_sha256": permutation_sha,
            }
        )
        for arm in ("treatment", "control"):
            randomized = permute_edges(references[arm], permutation)
            if cardinality_signature(randomized) != reference_signatures[arm]:
                raise N11Error(f"{arm} 随机置换改变映射拓扑")
            metrics = comparison_metrics(
                references[arm], randomized, all_atoms
            )
            rows_by_arm[arm].append(
                {
                    "trial_index": trial_index,
                    "permutation_sha256": permutation_sha,
                    **metrics,
                }
            )

    floor = {
        "schema_version": "v02-c8-n11-random-alignment-floor.v1",
        "status": "RANDOM_ALIGNMENT_FLOOR_READY",
        "trial_count": trial_count,
        "minimum_trial_count": MIN_TRIAL_COUNT,
        "paired_across_arms": True,
        "within_case_only": True,
        "identity_permutation_rejected_or_resampled": False,
        "root_seed_sha256": root_seed,
        "reference_cardinality_signatures": reference_signatures,
        "arms": {
            arm: {
                "summary": _metric_summary(rows),
                "trial_rows": rows,
            }
            for arm, rows in rows_by_arm.items()
        },
        "permutation_receipts_sha256": sha256_bytes(
            canonical_bytes(permutation_receipts)
        ),
        "semantic_five_layer_scores_emitted": False,
        "formal_gold_text_emitted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    seed_receipt = {
        "schema_version": "v02-c8-n11-seed-receipt.v1",
        "status": "SEED_FROZEN",
        "root_seed_sha256": root_seed,
        "seed_preimage": seed_preimage,
        "seed_preimage_sha256": sha256_bytes(
            canonical_bytes(seed_preimage)
        ),
        "human_selected_seed": False,
        "time_based_seed": False,
        "python_random_library_used": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    return floor, seed_receipt


def _empty_floor(
    treatment_mapping: Mapping[str, Any],
    control_mapping: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    treatment_atoms = atom_ids_by_case(treatment_mapping)
    all_atoms = [
        (case_id, atom_id)
        for case_id in CASE_ORDER
        for atom_id in treatment_atoms[case_id]
    ]
    treatment_metrics = comparison_metrics(
        mapping_edges(treatment_mapping),
        set(),
        all_atoms,
    )
    control_metrics = (
        comparison_metrics(
            mapping_edges(control_mapping),
            set(),
            all_atoms,
        )
        if control_mapping is not None
        else None
    )
    return {
        "schema_version": "v02-c8-n11-empty-extraction-floor.v1",
        "status": "EMPTY_EXTRACTION_MECHANICAL_FLOOR_READY",
        "unique_outcome_total": 1,
        "equivalent_repeat_count": DEFAULT_TRIAL_COUNT,
        "effective_independent_sample_total": 1,
        "shared_mechanical_floor": {
            "predicted_event_total": 0,
            "predicted_mapped_atom_total": 0,
            "predicted_coverage_rate": 0.0,
            "edge_precision": None,
            "edge_precision_status": "UNDEFINED_NO_PREDICTIONS",
        },
        "treatment_reference_comparison": treatment_metrics,
        "control_reference_comparison": (
            {
                "status": "EMPTY_EXTRACTION_CONTROL_COMPARISON_READY",
                "metrics": control_metrics,
            }
            if control_metrics is not None
            else {
                "status": BLOCKED_CONTROL,
                "metrics": None,
            }
        ),
        "warning": (
            "全原子 exact accuracy 会把真实未命中行也算对，不能替代"
            "正例原子召回；空抽取主地板只认覆盖 0 与正例召回 0。"
        ),
        "semantic_five_layer_scores_emitted": False,
        "anchor_partial_scores_emitted": False,
        "formal_gold_text_emitted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def build_artifacts(
    trial_count: int = DEFAULT_TRIAL_COUNT,
) -> dict[str, bytes]:
    _validate_trial_count(trial_count)
    treatment_sha = sha256_file(TREATMENT_MAPPING)
    if treatment_sha != EXPECTED_TREATMENT_MAPPING_SHA:
        raise N11Error("实验臂映射 SHA 漂移")
    readiness_sha = sha256_file(CONTROL_READINESS)
    if readiness_sha != EXPECTED_CONTROL_READINESS_SHA:
        raise N11Error("对照臂准备度票 SHA 漂移")
    treatment_mapping = read_json(TREATMENT_MAPPING)
    _mapping_rows(treatment_mapping)
    readiness = read_json(CONTROL_READINESS)
    if (
        readiness.get("control_mapping_frozen") is not False
        or readiness.get("semantic_verdict_pending_total") != 32
    ):
        raise N11Error("对照臂准备度身份漂移")
    control_mapping: dict[str, Any] | None = None
    control_pins: dict[str, str] | None = None
    if CONTROL_MAPPING.exists():
        control_mapping, control_pins = _verified_control_mapping()

    atom_sha = atom_set_sha256(treatment_mapping)
    contract = {
        "schema_version": CONTRACT_VERSION,
        "status": (
            "ACTIVE_BOTH_MAPPINGS_VERIFIED"
            if control_mapping is not None
            else "ACTIVE_CONTROL_MAPPING_REQUIRED"
        ),
        "minimum_random_trial_count": MIN_TRIAL_COUNT,
        "default_random_trial_count": DEFAULT_TRIAL_COUNT,
        "requested_random_trial_count": trial_count,
        "empty_extraction": {
            "deterministic": True,
            "effective_independent_sample_total": 1,
            "precision_without_predictions": "UNDEFINED_NO_PREDICTIONS",
        },
        "random_alignment": {
            "permutation": "paired_sha256_rank_within_case",
            "same_permutation_used_by_both_arms": True,
            "preserve_each_arm_mapping_topology": True,
            "identity_permutation_is_counted": True,
            "resampling_or_seed_selection_forbidden": True,
            "quantile_method": "nearest_rank",
            "quantiles": ["p05", "p25", "p50", "p75", "p95"],
        },
        "boundaries": {
            "chance_alignment_is_not_model_quality": True,
            "anchor_partial_floor_not_computable_without_semantic_labels": True,
            "five_layer_floor_not_computable_without_semantic_labels": True,
            "gold_text_forbidden": True,
        },
        "model_api_calls": 0,
        "network_requests": 0,
    }
    empty_floor = _empty_floor(treatment_mapping, control_mapping)
    if control_mapping is not None and control_pins is not None:
        random_floor, seed_receipt = run_random_alignment_floors(
            treatment_mapping,
            control_mapping,
            treatment_mapping_sha=treatment_sha,
            control_mapping_sha=control_pins["mapping_sha256"],
            trial_count=trial_count,
        )
        random_floor["anchor_partial_scores_emitted"] = False
        random_floor["quality_result_registered"] = False
        activation_receipt = {
            "schema_version": "v02-c8-n11-control-activation-receipt.v1",
            "status": "PASS_CONTROL_MAPPING_DOUBLE_PIN_AND_IDENTITY",
            "mapping_path": display_path(CONTROL_MAPPING),
            "mapping_sha256": control_pins["mapping_sha256"],
            "freeze_receipt_path": display_path(CONTROL_FREEZE_RECEIPT),
            "freeze_receipt_sha256": control_pins[
                "freeze_receipt_sha256"
            ],
            "mapping_identity": "working_mapping_not_gold",
            "formal_gold_changed": False,
            "conditional_invalidation": EXPECTED_CONDITIONAL_INVALIDATION,
            "scoring_atom_total": 49,
            "empty_extraction_both_arms_ready": True,
            "random_alignment_both_arms_ready": True,
            "semantic_five_layer_scores_emitted": False,
            "anchor_partial_scores_emitted": False,
            "quality_result_registered": False,
            "formal_gold_text_emitted": False,
            "model_api_calls": 0,
            "network_requests": 0,
        }
        source_receipt = {
            "schema_version": "v02-c8-n11-source-receipt.v1",
            "treatment_mapping": {
                "path": display_path(TREATMENT_MAPPING),
                "sha256": treatment_sha,
            },
            "control_mapping": {
                "path": display_path(CONTROL_MAPPING),
                "sha256": control_pins["mapping_sha256"],
                "status": "FROZEN_V02_WORKING_TRUTH",
                "mapping_identity": "working_mapping_not_gold",
            },
            "control_freeze_receipt": {
                "path": display_path(CONTROL_FREEZE_RECEIPT),
                "sha256": control_pins["freeze_receipt_sha256"],
            },
            "atom_set_sha256": atom_sha,
            "model_api_calls": 0,
            "network_requests": 0,
        }
        artifacts = {
            "n11_contract.json": canonical_bytes(contract),
            "source_receipt.json": canonical_bytes(source_receipt),
            "seed_receipt.json": canonical_bytes(seed_receipt),
            "empty_extraction_floor.json": canonical_bytes(empty_floor),
            "random_alignment_floor.json": canonical_bytes(random_floor),
            "n11_activation_receipt.json": canonical_bytes(
                activation_receipt
            ),
        }
        preimage = {
            relative: sha256_bytes(raw)
            for relative, raw in sorted(artifacts.items())
        }
        artifacts["artifact_manifest.json"] = canonical_bytes(
            {
                "schema_version": "v02-c8-n11-manifest.v1",
                "file_total_excluding_self": len(preimage),
                "files": [
                    {"path": relative, "sha256": digest}
                    for relative, digest in sorted(preimage.items())
                ],
                "artifact_set_sha256": sha256_bytes(
                    canonical_bytes(preimage)
                ),
                "status": ACTIVE_BOTH_ARMS,
                "semantic_five_layer_scores_emitted": False,
                "anchor_partial_scores_emitted": False,
                "quality_result_registered": False,
                "model_api_calls": 0,
                "network_requests": 0,
            }
        )
        return artifacts

    random_floor = {
        "schema_version": "v02-c8-n11-random-alignment-floor.v1",
        "status": BLOCKED_CONTROL,
        "trial_count_requested": trial_count,
        "trial_count_executed": 0,
        "missing_input": display_path(CONTROL_MAPPING),
        "root_seed_sha256": None,
        "arms": {
            "treatment": None,
            "control": None,
        },
        "semantic_five_layer_scores_emitted": False,
        "quality_result_registered": False,
        "formal_gold_text_emitted": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    seed_receipt = {
        "schema_version": "v02-c8-n11-seed-receipt.v1",
        "status": BLOCKED_CONTROL,
        "root_seed_sha256": None,
        "reason": "根种子必须绑定双臂冻结映射 SHA；缺对照映射时不得先挑种子。",
        "seed_preimage_partial": {
            "contract_version": CONTRACT_VERSION,
            "atom_set_sha256": atom_sha,
            "treatment_mapping_sha256": treatment_sha,
            "control_mapping_sha256": None,
            "trial_count": trial_count,
            "permutation": "paired_sha256_rank_within_case",
            "quantile_method": "nearest_rank",
        },
        "human_selected_seed": False,
        "time_based_seed": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    block_receipt = {
        "schema_version": "v02-c8-n11-block-receipt.v1",
        "status": BLOCKED_CONTROL,
        "missing_input": display_path(CONTROL_MAPPING),
        "control_readiness_path": display_path(CONTROL_READINESS),
        "control_readiness_sha256": readiness_sha,
        "mechanical_unique_route_total": 17,
        "semantic_verdict_pending_total": 32,
        "random_trials_executed": 0,
        "five_layer_scores_fabricated": False,
        "quality_result_registered": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    source_receipt = {
        "schema_version": "v02-c8-n11-source-receipt.v1",
        "treatment_mapping": {
            "path": display_path(TREATMENT_MAPPING),
            "sha256": treatment_sha,
        },
        "control_mapping": {
            "path": display_path(CONTROL_MAPPING),
            "sha256": None,
            "status": BLOCKED_CONTROL,
        },
        "atom_set_sha256": atom_sha,
        "model_api_calls": 0,
        "network_requests": 0,
    }

    artifacts = {
        "n11_contract.json": canonical_bytes(contract),
        "source_receipt.json": canonical_bytes(source_receipt),
        "seed_receipt.json": canonical_bytes(seed_receipt),
        "empty_extraction_floor.json": canonical_bytes(empty_floor),
        "random_alignment_floor.json": canonical_bytes(random_floor),
        "n11_block_receipt.json": canonical_bytes(block_receipt),
    }
    preimage = {
        relative: sha256_bytes(raw)
        for relative, raw in sorted(artifacts.items())
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c8-n11-manifest.v1",
            "file_total_excluding_self": len(preimage),
            "files": [
                {"path": relative, "sha256": digest}
                for relative, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(canonical_bytes(preimage)),
            "status": BLOCKED_CONTROL,
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def write_or_verify(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    trial_count: int = DEFAULT_TRIAL_COUNT,
) -> dict[str, Any]:
    if (
        CONTROL_MAPPING.exists()
        and output_dir.resolve() == DEFAULT_OUTPUT_DIR.resolve()
    ):
        raise N11Error(
            "C8 历史 N11 输出只读；映射激活后必须用 --output-dir 写入新目录"
        )
    first = build_artifacts(trial_count)
    second = build_artifacts(trial_count)
    if first != second:
        raise N11Error("N11 连续两次构造不一致")
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative, raw in sorted(first.items()):
        path = output_dir / relative
        if path.is_file():
            if path.read_bytes() != raw:
                raise N11Error(f"N11 已有工件漂移：{relative}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    if actual != set(first):
        raise N11Error("N11 输出目录存在未登记文件")
    random_floor = read_json(output_dir / "random_alignment_floor.json")
    active = random_floor.get("status") == "RANDOM_ALIGNMENT_FLOOR_READY"
    return {
        "status": ACTIVE_BOTH_ARMS if active else BLOCKED_CONTROL,
        "output_dir": display_path(output_dir),
        "empty_extraction_floor_ready": True,
        "random_alignment_trial_count_executed": (
            random_floor["trial_count"] if active else 0
        ),
        "random_alignment_trial_count_requested": trial_count,
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
    parser.add_argument(
        "--trial-count", type=int, default=DEFAULT_TRIAL_COUNT
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        json.dumps(
            write_or_verify(args.output_dir.resolve(), args.trial_count),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
