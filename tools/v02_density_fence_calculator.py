#!/usr/bin/env python3
"""Offline calculator for the v0.2 chapter-density budget fence.

This candidate freezes only the formulas and mechanical follow-up rules named
in the v0.2 design:

* ``len_coef = clip(sqrt(L / L50), 0.80, 1.25)``;
* ``load_ratio = (N_est + 0.25 * max(0, P_est - N_est))
  / (32 * len_coef)``;
* the load-ratio class selects ``density_coef``;
* 25, 32, and 40 are respectively the lower, reference, and upper fence
  bases, and every base is multiplied by both coefficients.

There is deliberately no numeric L50 default.  A calculation remains
``L50_MISSING`` unless the caller supplies L50 for that calculation.  The
small/medium/large block-size policy is also kept as
``BLOCK_SIZE_POLICY_MISSING`` because this candidate has no evidence to invent
those values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from decimal import Decimal, ROUND_HALF_UP, localcontext
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "B4_2_density_fence_calculator"
)

L50_MISSING = "L50_MISSING"
BLOCK_SIZE_POLICY_MISSING = "BLOCK_SIZE_POLICY_MISSING"
CHAPTER_TYPE_SOURCE = "LOAD_RATIO_FORMULA_ONLY"
BLIND_PRODUCTION_INPUT_ERROR = (
    "BLIND_PRODUCTION_97_184_FORBIDDEN_AS_CHAPTER_TYPE_INPUT"
)
MANUAL_CHAPTER_TYPE_INPUT_ERROR = (
    "MANUAL_CHAPTER_TYPE_INPUT_FORBIDDEN_USE_LOAD_RATIO"
)

LEN_COEF_MIN = Decimal("0.80")
LEN_COEF_MAX = Decimal("1.25")
LOAD_RATIO_NORMAL_MIN = Decimal("0.75")
LOAD_RATIO_NORMAL_MAX = Decimal("1.25")

BASE_FENCE_ROWS: tuple[tuple[str, int, str], ...] = (
    ("lower_bound", 25, "下限"),
    ("reference_budget", 32, "参考值"),
    ("upper_bound", 40, "上限"),
)

DENSITY_ROWS: tuple[dict[str, Any], ...] = (
    {
        "density_class": "WATER",
        "density_label": "水文",
        "condition": "load_ratio < 0.75",
        "density_coef": Decimal("0.80"),
    },
    {
        "density_class": "NORMAL",
        "density_label": "普通",
        "condition": "0.75 <= load_ratio <= 1.25",
        "density_coef": Decimal("1.00"),
    },
    {
        "density_class": "HIGH_INFORMATION",
        "density_label": "高信息",
        "condition": "load_ratio > 1.25",
        "density_coef": Decimal("1.25"),
    },
)

ROUNDING_POLICY = {
    "policy_id": "ROUND_HALF_UP_CANDIDATE_UNCONFIRMED",
    "method": "Decimal.quantize(1, rounding=ROUND_HALF_UP)",
    "tie_example": "32.5 -> 33",
    "python_builtin_round_used": False,
    "product_policy_status": "PENDING_CONFIRMATION",
    "authority_claim": "候选机械口径，不冒充已拍产品事实",
}

BLIND_PRODUCTION_GUARD = {
    "minimum_inclusive": 97,
    "maximum_inclusive": 184,
    "allowed_as_chapter_type_input": False,
    "failure_code": BLIND_PRODUCTION_INPUT_ERROR,
    "chapter_type_source": CHAPTER_TYPE_SOURCE,
}


class DensityFenceError(ValueError):
    """Raised when a caller violates the frozen calculator contract."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _tree_hash(artifacts: Mapping[str, bytes]) -> str:
    inventory = [
        {"path": path, "bytes": len(data), "sha256": _sha256(data)}
        for path, data in sorted(artifacts.items())
    ]
    return _sha256(_canonical_bytes(inventory))


def _require_int(
    value: Any,
    field: str,
    *,
    strictly_positive: bool,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DensityFenceError(f"{field} must be an integer")
    if strictly_positive and value <= 0:
        raise DensityFenceError(f"{field} must be greater than zero")
    if not strictly_positive and value < 0:
        raise DensityFenceError(f"{field} must be zero or greater")
    return value


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _guard_chapter_type_input(value: Any | None) -> None:
    if value is None:
        return
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 97 <= value <= 184
    ):
        raise DensityFenceError(BLIND_PRODUCTION_INPUT_ERROR)
    raise DensityFenceError(MANUAL_CHAPTER_TYPE_INPUT_ERROR)


def _density_row(load_ratio: Decimal) -> dict[str, Any]:
    if load_ratio < LOAD_RATIO_NORMAL_MIN:
        return DENSITY_ROWS[0]
    if load_ratio <= LOAD_RATIO_NORMAL_MAX:
        return DENSITY_ROWS[1]
    return DENSITY_ROWS[2]


def _budget_row(
    role: str,
    base_value: int,
    label_zh: str,
    len_coef: Decimal,
    density_coef: Decimal,
) -> dict[str, Any]:
    unrounded = Decimal(base_value) * len_coef * density_coef
    rounded = int(unrounded.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return {
        "role": role,
        "label_zh": label_zh,
        "base_value": base_value,
        "unrounded": _decimal_text(unrounded),
        "budget": rounded,
    }


def _count_assessment(
    raw_candidate_count: int | None,
    *,
    lower_bound: int,
    upper_bound: int,
) -> dict[str, Any]:
    common = {
        "raw_candidate_count": raw_candidate_count,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "anomaly_threshold_strictly_above": 2 * upper_bound,
        "auto_fill_allowed": False,
        "auto_truncation_allowed": False,
    }
    if raw_candidate_count is None:
        return {
            **common,
            "status": "RAW_CANDIDATE_COUNT_NOT_PROVIDED",
            "granularity_anomaly": False,
            "next_action": "NO_COUNT_ACTION",
        }
    if raw_candidate_count < lower_bound:
        return {
            **common,
            "status": "legitimate_underfill",
            "granularity_anomaly": False,
            "next_action": "DO_NOT_ADD_ITEMS",
        }
    if raw_candidate_count <= upper_bound:
        return {
            **common,
            "status": "within_fence",
            "granularity_anomaly": False,
            "next_action": "KEEP_COUNT",
        }
    anomaly = raw_candidate_count > 2 * upper_bound
    return {
        **common,
        "status": (
            "granularity_anomaly"
            if anomaly
            else "over_upper_review_required"
        ),
        "granularity_anomaly": anomaly,
        "next_action": "REVIEW_MERGE_AND_DEDUPLICATE_NO_TRUNCATION",
    }


def calculate_density_fence(
    *,
    length_chars: int,
    l50_chars: int | None,
    n_est: int,
    p_est: int,
    raw_candidate_count: int | None = None,
    chapter_type_input: Any | None = None,
) -> dict[str, Any]:
    """Calculate one fence only when this call explicitly supplies L50.

    ``chapter_type_input`` exists only as a hard guard for accidental manual or
    blind-production classification.  A valid call must leave it as ``None``;
    the chapter-density class is derived exclusively from ``load_ratio``.
    """

    length_chars = _require_int(
        length_chars,
        "length_chars",
        strictly_positive=True,
    )
    n_est = _require_int(n_est, "n_est", strictly_positive=False)
    p_est = _require_int(p_est, "p_est", strictly_positive=False)
    if raw_candidate_count is not None:
        raw_candidate_count = _require_int(
            raw_candidate_count,
            "raw_candidate_count",
            strictly_positive=False,
        )
    _guard_chapter_type_input(chapter_type_input)

    base_result: dict[str, Any] = {
        "schema_version": "v02-b4-2-density-fence-result-v0.1",
        "inputs": {
            "length_chars": length_chars,
            "l50_chars": (
                L50_MISSING if l50_chars is None else l50_chars
            ),
            "n_est": n_est,
            "p_est": p_est,
            "raw_candidate_count": raw_candidate_count,
        },
        "chapter_type_source": CHAPTER_TYPE_SOURCE,
        "blind_production_input_guard": dict(BLIND_PRODUCTION_GUARD),
        "block_size_policy": BLOCK_SIZE_POLICY_MISSING,
        "rounding_policy": dict(ROUNDING_POLICY),
    }

    if l50_chars is None:
        return {
            **base_result,
            "calculation_status": L50_MISSING,
            "missing_policy_codes": [
                L50_MISSING,
                BLOCK_SIZE_POLICY_MISSING,
            ],
            "l50_scope": "NO_VALUE_SUPPLIED_NO_CALCULATION",
            "calculation": None,
        }

    l50_chars = _require_int(
        l50_chars,
        "l50_chars",
        strictly_positive=True,
    )
    base_result["inputs"]["l50_chars"] = l50_chars

    precision = max(
        50,
        len(str(length_chars))
        + len(str(l50_chars))
        + len(str(n_est))
        + len(str(p_est))
        + 20,
    )
    with localcontext() as context:
        context.prec = precision
        length_ratio = Decimal(length_chars) / Decimal(l50_chars)
        raw_len_coef = length_ratio.sqrt()
        len_coef = min(max(raw_len_coef, LEN_COEF_MIN), LEN_COEF_MAX)
        p_surplus = max(0, p_est - n_est)
        adjusted_load_numerator = Decimal(n_est) + (
            Decimal("0.25") * Decimal(p_surplus)
        )
        load_ratio = adjusted_load_numerator / (Decimal(32) * len_coef)
        density = _density_row(load_ratio)
        density_coef: Decimal = density["density_coef"]
        budget_rows = [
            _budget_row(role, base, label, len_coef, density_coef)
            for role, base, label in BASE_FENCE_ROWS
        ]
    budget_by_role = {row["role"]: row for row in budget_rows}
    lower_bound = budget_by_role["lower_bound"]["budget"]
    upper_bound = budget_by_role["upper_bound"]["budget"]

    return {
        **base_result,
        "calculation_status": "CALCULATED_WITH_OPEN_POLICY_GAPS",
        "missing_policy_codes": [BLOCK_SIZE_POLICY_MISSING],
        "l50_scope": "EXPLICIT_SINGLE_CALCULATION_INPUT_NOT_GLOBAL_POLICY",
        "calculation": {
            "length_ratio": _decimal_text(length_ratio),
            "raw_len_coef": _decimal_text(raw_len_coef),
            "len_coef": _decimal_text(len_coef),
            "len_coef_clip": {
                "minimum": "0.80",
                "maximum": "1.25",
            },
            "p_surplus_over_n": p_surplus,
            "adjusted_load_numerator": _decimal_text(
                adjusted_load_numerator
            ),
            "load_ratio": _decimal_text(load_ratio),
            "density_class": density["density_class"],
            "density_label": density["density_label"],
            "density_condition": density["condition"],
            "density_coef": _decimal_text(density_coef),
            "budget_fence": budget_by_role,
            "count_assessment": _count_assessment(
                raw_candidate_count,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
            ),
        },
    }


def build_formula_freeze() -> dict[str, Any]:
    return {
        "schema_version": "v02-b4-2-formula-freeze-v0.1",
        "candidate_id": "B4_2_density_fence_calculator",
        "authority_boundary": {
            "design": "统一设计稿｜抽取工序重设计 v0.2",
            "section": "三｜冻结公式",
            "work_order": "连夜施工令 B4.2",
        },
        "formulas": {
            "len_coef": "clip(sqrt(L/L50),0.80,1.25)",
            "load_ratio": (
                "(N_est+0.25*max(0,P_est-N_est))/(32*len_coef)"
            ),
            "budget": (
                "round(base_value*len_coef*density_coef)"
            ),
        },
        "base_fence_mapping": [
            {
                "role": role,
                "label_zh": label,
                "base_value": base,
            }
            for role, base, label in BASE_FENCE_ROWS
        ],
        "base_mapping_interpretation": (
            "25/32/40 同时形成下限/参考值/上限；"
            "不是分别绑定三种章型。章型只选择 density_coef。"
        ),
        "density_mapping": [
            {
                "density_class": row["density_class"],
                "density_label": row["density_label"],
                "condition": row["condition"],
                "density_coef": _decimal_text(row["density_coef"]),
            }
            for row in DENSITY_ROWS
        ],
        "count_rules": {
            "below_lower": {
                "status": "legitimate_underfill",
                "auto_fill_allowed": False,
            },
            "above_upper": {
                "auto_truncation_allowed": False,
                "next_action": (
                    "REVIEW_MERGE_AND_DEDUPLICATE_NO_TRUNCATION"
                ),
            },
            "granularity_anomaly": {
                "condition": "raw_candidate_count > 2 * upper_bound",
                "strict_operator": ">",
            },
        },
        "rounding_policy": dict(ROUNDING_POLICY),
        "chapter_type_input_policy": dict(BLIND_PRODUCTION_GUARD),
        "missing_material_policy": {
            "l50": L50_MISSING,
            "block_size_policy": BLOCK_SIZE_POLICY_MISSING,
            "numeric_l50_default_built_in": False,
            "calculation_requires_explicit_l50": True,
        },
        "scope": {
            "model_api_calls": 0,
            "network_requests": 0,
            "notion_writes": 0,
            "default_route_mutations": 0,
            "formal_gold_mutations": 0,
            "governance_mutations": 0,
        },
    }


def build_request_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": (
            "https://local.invalid/contracts/"
            "v02-density-fence-request.schema.json"
        ),
        "title": "v0.2 B4.2 密度围栏计算请求",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {
                "const": "v02-b4-2-density-fence-request-v0.1"
            },
            "length_chars": {"type": "integer", "minimum": 1},
            "l50_chars": {
                "oneOf": [
                    {"type": "integer", "minimum": 1},
                    {"const": L50_MISSING},
                ],
                "description": (
                    "没有用户显式输入时只能写 L50_MISSING，"
                    "不得内置猜值。"
                ),
            },
            "n_est": {"type": "integer", "minimum": 0},
            "p_est": {"type": "integer", "minimum": 0},
            "raw_candidate_count": {"type": "integer", "minimum": 0},
            "chapter_type_source": {"const": CHAPTER_TYPE_SOURCE},
            "block_size_policy": {
                "const": BLOCK_SIZE_POLICY_MISSING,
                "description": "小中大三类块尺寸尚缺材料。",
            },
        },
        "required": [
            "schema_version",
            "length_chars",
            "l50_chars",
            "n_est",
            "p_est",
            "chapter_type_source",
            "block_size_policy",
        ],
        "allOf": [
            {
                "not": {"required": ["blind_production_count"]},
                "description": (
                    "盲产 97-184 不得作为章型输入；"
                    "章型只按 load_ratio 公式产生。"
                ),
            }
        ],
        "x_missing_policy_codes": [
            L50_MISSING,
            BLOCK_SIZE_POLICY_MISSING,
        ],
        "x_forbidden_chapter_type_input": dict(
            BLIND_PRODUCTION_GUARD
        ),
    }


def _request_example(
    *,
    l50_chars: int | str,
    raw_candidate_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": "v02-b4-2-density-fence-request-v0.1",
        "length_chars": 1000,
        "l50_chars": l50_chars,
        "n_est": 24,
        "p_est": 24,
        "raw_candidate_count": raw_candidate_count,
        "chapter_type_source": CHAPTER_TYPE_SOURCE,
        "block_size_policy": BLOCK_SIZE_POLICY_MISSING,
    }


def _vector(
    vector_id: str,
    purpose: str,
    inputs: Mapping[str, Any],
    checks: Mapping[str, Any],
) -> dict[str, Any]:
    result = calculate_density_fence(**inputs)
    observed: dict[str, Any] = {}
    passed = True
    for path, expected in checks.items():
        value: Any = result
        for part in path.split("."):
            value = value[part]
        observed[path] = value
        if value != expected:
            passed = False
    return {
        "vector_id": vector_id,
        "purpose": purpose,
        "inputs": dict(inputs),
        "checks": dict(checks),
        "observed": observed,
        "passed": passed,
        "result": result,
    }


def _error_vector(
    vector_id: str,
    purpose: str,
    inputs: Mapping[str, Any],
    expected_error: str,
) -> dict[str, Any]:
    try:
        calculate_density_fence(**inputs)
    except DensityFenceError as exc:
        observed_error = str(exc)
    else:
        observed_error = "NO_ERROR"
    return {
        "vector_id": vector_id,
        "purpose": purpose,
        "inputs": dict(inputs),
        "expected_error": expected_error,
        "observed_error": observed_error,
        "passed": observed_error == expected_error,
    }


def build_test_vectors() -> dict[str, Any]:
    vectors = [
        _vector(
            "B4-F-THRESHOLD-001",
            "低于 0.75 归水文。",
            {
                "length_chars": 1000,
                "l50_chars": 1000,
                "n_est": 23,
                "p_est": 23,
            },
            {
                "calculation.density_class": "WATER",
                "calculation.density_coef": "0.80",
            },
        ),
        _vector(
            "B4-F-THRESHOLD-002",
            "0.75 边界归普通。",
            {
                "length_chars": 1000,
                "l50_chars": 1000,
                "n_est": 24,
                "p_est": 24,
            },
            {
                "calculation.load_ratio": "0.75",
                "calculation.density_class": "NORMAL",
            },
        ),
        _vector(
            "B4-F-THRESHOLD-003",
            "1.25 边界归普通。",
            {
                "length_chars": 1000,
                "l50_chars": 1000,
                "n_est": 40,
                "p_est": 40,
            },
            {
                "calculation.load_ratio": "1.25",
                "calculation.density_class": "NORMAL",
            },
        ),
        _vector(
            "B4-F-THRESHOLD-004",
            "高于 1.25 归高信息。",
            {
                "length_chars": 1000,
                "l50_chars": 1000,
                "n_est": 41,
                "p_est": 41,
            },
            {
                "calculation.density_class": "HIGH_INFORMATION",
                "calculation.density_coef": "1.25",
            },
        ),
        _vector(
            "B4-F-LOAD-001",
            "P_est 只对超过 N_est 的部分计入四分之一。",
            {
                "length_chars": 1000,
                "l50_chars": 1000,
                "n_est": 20,
                "p_est": 36,
            },
            {
                "calculation.adjusted_load_numerator": "24.00",
                "calculation.load_ratio": "0.75",
                "calculation.density_class": "NORMAL",
            },
        ),
        _vector(
            "B4-F-CLIP-001",
            "长度系数低端裁到 0.80。",
            {
                "length_chars": 25,
                "l50_chars": 100,
                "n_est": 16,
                "p_est": 16,
            },
            {"calculation.len_coef": "0.80"},
        ),
        _vector(
            "B4-F-CLIP-002",
            "长度系数高端裁到 1.25。",
            {
                "length_chars": 400,
                "l50_chars": 100,
                "n_est": 40,
                "p_est": 40,
            },
            {"calculation.len_coef": "1.25"},
        ),
        _vector(
            "B4-F-BASE-001",
            "25/32/40 固定对应下限/参考值/上限。",
            {
                "length_chars": 1000,
                "l50_chars": 1000,
                "n_est": 32,
                "p_est": 32,
            },
            {
                (
                    "calculation.budget_fence.lower_bound.base_value"
                ): 25,
                (
                    "calculation.budget_fence.reference_budget.base_value"
                ): 32,
                (
                    "calculation.budget_fence.upper_bound.base_value"
                ): 40,
                "calculation.budget_fence.lower_bound.budget": 25,
                "calculation.budget_fence.reference_budget.budget": 32,
                "calculation.budget_fence.upper_bound.budget": 40,
            },
        ),
        _vector(
            "B4-F-ROUND-001",
            "32.5 明确按 half-up 候选口径得到 33。",
            {
                "length_chars": 4225,
                "l50_chars": 4096,
                "n_est": 32,
                "p_est": 32,
            },
            {
                (
                    "calculation.budget_fence."
                    "reference_budget.unrounded"
                ): "32.50000000",
                (
                    "calculation.budget_fence."
                    "reference_budget.budget"
                ): 33,
                "rounding_policy.policy_id": (
                    "ROUND_HALF_UP_CANDIDATE_UNCONFIRMED"
                ),
            },
        ),
        _vector(
            "B4-F-UNDERFILL-001",
            "低于下限是合法欠产出，不补条。",
            {
                "length_chars": 1000,
                "l50_chars": 1000,
                "n_est": 24,
                "p_est": 24,
                "raw_candidate_count": 24,
            },
            {
                "calculation.count_assessment.status": (
                    "legitimate_underfill"
                ),
                (
                    "calculation.count_assessment.auto_fill_allowed"
                ): False,
            },
        ),
        _vector(
            "B4-F-UPPER-001",
            "高于上限先合并去重，不截断。",
            {
                "length_chars": 1000,
                "l50_chars": 1000,
                "n_est": 32,
                "p_est": 32,
                "raw_candidate_count": 41,
            },
            {
                "calculation.count_assessment.status": (
                    "over_upper_review_required"
                ),
                (
                    "calculation.count_assessment."
                    "auto_truncation_allowed"
                ): False,
                "calculation.count_assessment.next_action": (
                    "REVIEW_MERGE_AND_DEDUPLICATE_NO_TRUNCATION"
                ),
            },
        ),
        _vector(
            "B4-F-ANOMALY-001",
            "正好两倍上限不标颗粒度异常。",
            {
                "length_chars": 1000,
                "l50_chars": 1000,
                "n_est": 32,
                "p_est": 32,
                "raw_candidate_count": 80,
            },
            {
                (
                    "calculation.count_assessment."
                    "granularity_anomaly"
                ): False,
            },
        ),
        _vector(
            "B4-F-ANOMALY-002",
            "严格高于两倍上限才标颗粒度异常。",
            {
                "length_chars": 1000,
                "l50_chars": 1000,
                "n_est": 32,
                "p_est": 32,
                "raw_candidate_count": 81,
            },
            {
                "calculation.count_assessment.status": (
                    "granularity_anomaly"
                ),
                (
                    "calculation.count_assessment."
                    "granularity_anomaly"
                ): True,
                (
                    "calculation.count_assessment."
                    "auto_truncation_allowed"
                ): False,
            },
        ),
        _vector(
            "B4-F-MISSING-001",
            "未显式给 L50 时不计算。",
            {
                "length_chars": 1000,
                "l50_chars": None,
                "n_est": 24,
                "p_est": 24,
            },
            {
                "calculation_status": L50_MISSING,
                "calculation": None,
            },
        ),
        _error_vector(
            "B4-F-BLIND-001",
            "盲产 97-184 不得作为章型输入。",
            {
                "length_chars": 1000,
                "l50_chars": 1000,
                "n_est": 32,
                "p_est": 32,
                "chapter_type_input": 97,
            },
            BLIND_PRODUCTION_INPUT_ERROR,
        ),
    ]
    failed = [row["vector_id"] for row in vectors if not row["passed"]]
    if failed:
        raise DensityFenceError(
            "built-in regression vector failed: " + ", ".join(failed)
        )
    return {
        "schema_version": "v02-b4-2-test-vectors-v0.1",
        "synthetic_fixture_notice": (
            "这些 L50 是回归向量显式输入，不是产品默认值或校准结论。"
        ),
        "vector_count": len(vectors),
        "passed_count": len(vectors),
        "vectors": vectors,
    }


def build_acceptance_receipt(
    test_vectors: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "v02-b4-2-acceptance-v0.1",
        "candidate_id": "B4_2_density_fence_calculator",
        "result": "PASS_CANDIDATE_WITH_OPEN_POLICY_GAPS",
        "vector_count": test_vectors["vector_count"],
        "passed_count": test_vectors["passed_count"],
        "coverage": [
            "load_ratio_below_0.75",
            "load_ratio_equal_0.75_normal",
            "load_ratio_equal_1.25_normal",
            "load_ratio_above_1.25",
            "len_coef_low_clip",
            "len_coef_high_clip",
            "base_25_32_40_mapping",
            "round_half_up_tie",
            "legitimate_underfill_no_fill",
            "over_upper_merge_deduplicate_no_truncation",
            "strictly_over_two_times_upper_anomaly",
            "l50_missing_no_calculation",
            "blind_production_97_184_forbidden",
        ],
        "open_policy_gaps": [
            L50_MISSING,
            BLOCK_SIZE_POLICY_MISSING,
            "ROUND_HALF_UP_PRODUCT_POLICY_UNCONFIRMED",
        ],
        "numeric_l50_default_built_in": False,
        "block_size_values_invented": False,
        "blind_production_range_used_for_chapter_type": False,
        "scope": {
            "model_api_calls": 0,
            "network_requests": 0,
            "notion_writes": 0,
            "default_route_mutations": 0,
            "formal_gold_mutations": 0,
            "governance_mutations": 0,
        },
    }


def build_core_artifacts() -> dict[str, bytes]:
    formula_freeze = build_formula_freeze()
    request_schema = build_request_schema()
    missing_request = _request_example(
        l50_chars=L50_MISSING,
        raw_candidate_count=24,
    )
    explicit_request = _request_example(
        l50_chars=1000,
        raw_candidate_count=41,
    )
    missing_result = calculate_density_fence(
        length_chars=missing_request["length_chars"],
        l50_chars=None,
        n_est=missing_request["n_est"],
        p_est=missing_request["p_est"],
        raw_candidate_count=missing_request["raw_candidate_count"],
    )
    explicit_result = calculate_density_fence(
        length_chars=explicit_request["length_chars"],
        l50_chars=explicit_request["l50_chars"],
        n_est=explicit_request["n_est"],
        p_est=explicit_request["p_est"],
        raw_candidate_count=explicit_request["raw_candidate_count"],
    )
    test_vectors = build_test_vectors()
    acceptance = build_acceptance_receipt(test_vectors)
    return {
        "formula_freeze.json": _json_bytes(formula_freeze),
        "schemas/density_fence_request.schema.json": _json_bytes(
            request_schema
        ),
        "examples/l50_missing_request.json": _json_bytes(missing_request),
        "examples/l50_missing_result.json": _json_bytes(missing_result),
        (
            "examples/block_size_policy_missing_request.json"
        ): _json_bytes(explicit_request),
        "examples/calculated_candidate_result.json": _json_bytes(
            explicit_result
        ),
        "test_vectors.json": _json_bytes(test_vectors),
        "acceptance_receipt.json": _json_bytes(acceptance),
    }


def build_manifest(core_artifacts: Mapping[str, bytes]) -> dict[str, Any]:
    inventory = [
        {
            "path": path,
            "bytes": len(data),
            "sha256": _sha256(data),
        }
        for path, data in sorted(core_artifacts.items())
    ]
    return {
        "schema_version": "v02-b4-2-density-fence-manifest-v0.1",
        "candidate_id": "B4_2_density_fence_calculator",
        "candidate_status": "candidate_silver_not_active",
        "artifact_count": len(inventory),
        "artifacts": inventory,
        "bundle_content_hash": _sha256(_canonical_bytes(inventory)),
        "formula_freeze": {
            "len_coef": "clip(sqrt(L/L50),0.80,1.25)",
            "load_ratio": (
                "(N_est+0.25*max(0,P_est-N_est))/(32*len_coef)"
            ),
            "base_fence_mapping": {
                "25": "lower_bound",
                "32": "reference_budget",
                "40": "upper_bound",
            },
            "density_coef_mapping": {
                "WATER_load_ratio_lt_0.75": "0.80",
                "NORMAL_0.75_to_1.25_inclusive": "1.00",
                "HIGH_INFORMATION_load_ratio_gt_1.25": "1.25",
            },
            "rounding_policy": dict(ROUNDING_POLICY),
        },
        "open_policy_gaps": [
            L50_MISSING,
            BLOCK_SIZE_POLICY_MISSING,
            "ROUND_HALF_UP_PRODUCT_POLICY_UNCONFIRMED",
        ],
        "chapter_type_guard": dict(BLIND_PRODUCTION_GUARD),
        "release_isolation": {
            "activation_allowed": False,
            "formal_gold_changed": False,
            "default_chain_changed": False,
            "current_state_changed": False,
        },
        "scope": {
            "model_api_calls": 0,
            "network_requests": 0,
            "notion_writes": 0,
            "default_route_mutations": 0,
            "formal_gold_mutations": 0,
            "governance_mutations": 0,
        },
    }


def build_bundle_files() -> dict[str, bytes]:
    core = build_core_artifacts()
    manifest = build_manifest(core)
    return {**core, "manifest.json": _json_bytes(manifest)}


def _write_files(
    output_dir: Path,
    artifacts: Mapping[str, bytes],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, data in artifacts.items():
        target = output_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def write_bundle(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    files = build_bundle_files()
    _write_files(output_dir, files)
    return {
        "result": "BUILT",
        "output_dir": str(output_dir),
        "file_count": len(files),
        "tree_sha256": _tree_hash(files),
    }


def _read_tree(
    bundle_dir: Path,
    *,
    include_double_run: bool,
) -> dict[str, bytes]:
    ignored = set() if include_double_run else {"double_run_receipt.json"}
    return {
        str(path.relative_to(bundle_dir)): path.read_bytes()
        for path in sorted(bundle_dir.rglob("*"))
        if path.is_file() and path.name not in ignored
    }


def check_bundle(bundle_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    expected = build_bundle_files()
    observed = _read_tree(bundle_dir, include_double_run=False)
    if set(observed) != set(expected):
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        raise DensityFenceError(
            f"bundle inventory mismatch; missing={missing}; extra={extra}"
        )
    drifted = [
        path
        for path in sorted(expected)
        if observed[path] != expected[path]
    ]
    if drifted:
        raise DensityFenceError(
            "bundle byte drift: " + ", ".join(drifted)
        )

    tree_sha = _tree_hash(expected)
    double_run_path = bundle_dir / "double_run_receipt.json"
    double_run_present = double_run_path.is_file()
    if double_run_present:
        receipt = json.loads(double_run_path.read_bytes())
        if receipt.get("schema_version") != (
            "v02-b4-2-double-run-receipt-v0.1"
        ):
            raise DensityFenceError("double-run receipt schema mismatch")
        if receipt.get("byte_identical") is not True:
            raise DensityFenceError("double-run receipt is not PASS")
        for field in (
            "pass1_tree_sha256",
            "pass2_tree_sha256",
            "target_tree_sha256",
        ):
            if receipt.get(field) != tree_sha:
                raise DensityFenceError(
                    f"double-run receipt {field} mismatch"
                )
        if receipt.get("target_manifest_sha256") != _sha256(
            expected["manifest.json"]
        ):
            raise DensityFenceError(
                "double-run receipt manifest hash mismatch"
            )

    vectors = json.loads(expected["test_vectors.json"])
    return {
        "result": "PASS",
        "bundle_dir": str(bundle_dir),
        "tree_sha256": tree_sha,
        "vector_count": vectors["vector_count"],
        "passed_count": vectors["passed_count"],
        "double_run_receipt_present": double_run_present,
    }


def write_double_run_receipt(
    bundle_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as first_temp, (
        tempfile.TemporaryDirectory()
    ) as second_temp:
        first_dir = Path(first_temp) / "bundle"
        second_dir = Path(second_temp) / "bundle"
        write_bundle(first_dir)
        write_bundle(second_dir)
        pass1 = _read_tree(first_dir, include_double_run=False)
        pass2 = _read_tree(second_dir, include_double_run=False)

    target = _read_tree(bundle_dir, include_double_run=False)
    pass1_tree = _tree_hash(pass1)
    pass2_tree = _tree_hash(pass2)
    target_tree = _tree_hash(target)
    byte_identical = pass1 == pass2 == target
    if not byte_identical:
        raise DensityFenceError("independent double run is not byte identical")

    vectors = build_test_vectors()
    receipt = {
        "schema_version": "v02-b4-2-double-run-receipt-v0.1",
        "runs": 2,
        "byte_identical": True,
        "pass1_tree_sha256": pass1_tree,
        "pass2_tree_sha256": pass2_tree,
        "target_tree_sha256": target_tree,
        "target_manifest_sha256": _sha256(target["manifest.json"]),
        "vector_count_each_run": vectors["vector_count"],
        "passed_count_each_run": vectors["passed_count"],
        "numeric_l50_default_built_in": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    (bundle_dir / "double_run_receipt.json").write_bytes(
        _json_bytes(receipt)
    )
    return {"result": "PASS_BYTE_IDENTICAL", **receipt}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="v0.2 B4.2 离线密度围栏计算器"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    calculate = subparsers.add_parser("calculate")
    calculate.add_argument("--length-chars", type=int, required=True)
    calculate.add_argument("--l50-chars", type=int)
    calculate.add_argument("--n-est", type=int, required=True)
    calculate.add_argument("--p-est", type=int, required=True)
    calculate.add_argument("--raw-candidate-count", type=int)

    build = subparsers.add_parser("build")
    build.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    validate = subparsers.add_parser("validate-bundle")
    validate.add_argument(
        "--bundle-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )

    double_run = subparsers.add_parser("double-run")
    double_run.add_argument(
        "--bundle-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "calculate":
        result = calculate_density_fence(
            length_chars=args.length_chars,
            l50_chars=args.l50_chars,
            n_est=args.n_est,
            p_est=args.p_est,
            raw_candidate_count=args.raw_candidate_count,
        )
    elif args.command == "build":
        result = write_bundle(args.output_dir)
    elif args.command == "validate-bundle":
        result = check_bundle(args.bundle_dir)
    elif args.command == "double-run":
        result = write_double_run_receipt(args.bundle_dir)
    else:  # pragma: no cover - argparse already rejects this path.
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
