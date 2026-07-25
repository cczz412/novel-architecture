from __future__ import annotations

import ast
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from tools import v02_density_fence_calculator as fence


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "v02_density_fence_calculator.py"
BUNDLE_DIR = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "B4_2_density_fence_calculator"
)


def _calculate(
    *,
    length_chars: int = 1000,
    l50_chars: int | None = 1000,
    n_est: int = 32,
    p_est: int = 32,
    raw_candidate_count: int | None = None,
) -> dict[str, object]:
    return fence.calculate_density_fence(
        length_chars=length_chars,
        l50_chars=l50_chars,
        n_est=n_est,
        p_est=p_est,
        raw_candidate_count=raw_candidate_count,
    )


def _calculation(result: dict[str, object]) -> dict[str, object]:
    value = result["calculation"]
    assert isinstance(value, dict)
    return value


def _count_assessment(result: dict[str, object]) -> dict[str, object]:
    value = _calculation(result)["count_assessment"]
    assert isinstance(value, dict)
    return value


def test_len_coef_uses_sqrt_then_clips_both_ends() -> None:
    below = _calculation(
        _calculate(length_chars=25, l50_chars=100, n_est=16, p_est=16)
    )
    at_low = _calculation(
        _calculate(length_chars=64, l50_chars=100, n_est=16, p_est=16)
    )
    at_high = _calculation(
        _calculate(
            length_chars=15625,
            l50_chars=10000,
            n_est=40,
            p_est=40,
        )
    )
    above = _calculation(
        _calculate(length_chars=400, l50_chars=100, n_est=40, p_est=40)
    )

    assert below["raw_len_coef"] == "0.5"
    assert below["len_coef"] == "0.80"
    assert at_low["len_coef"] == "0.8"
    assert at_high["len_coef"] == "1.25"
    assert above["raw_len_coef"] == "2"
    assert above["len_coef"] == "1.25"


def test_load_ratio_formula_counts_only_positive_p_surplus() -> None:
    with_surplus = _calculation(_calculate(n_est=20, p_est=36))
    no_surplus = _calculation(_calculate(n_est=24, p_est=12))

    assert with_surplus["p_surplus_over_n"] == 16
    assert with_surplus["adjusted_load_numerator"] == "24.00"
    assert with_surplus["load_ratio"] == "0.75"
    assert no_surplus["p_surplus_over_n"] == 0
    assert no_surplus["adjusted_load_numerator"] == "24.00"
    assert no_surplus["load_ratio"] == "0.75"


@pytest.mark.parametrize(
    ("n_est", "expected_ratio", "expected_class", "expected_coef"),
    [
        (23, "0.71875", "WATER", "0.80"),
        (24, "0.75", "NORMAL", "1.00"),
        (40, "1.25", "NORMAL", "1.00"),
        (41, "1.28125", "HIGH_INFORMATION", "1.25"),
    ],
)
def test_density_thresholds_put_both_boundaries_in_normal(
    n_est: int,
    expected_ratio: str,
    expected_class: str,
    expected_coef: str,
) -> None:
    calculation = _calculation(_calculate(n_est=n_est, p_est=n_est))
    assert calculation["load_ratio"] == expected_ratio
    assert calculation["density_class"] == expected_class
    assert calculation["density_coef"] == expected_coef


def test_25_32_40_are_lower_reference_upper_not_chapter_classes() -> None:
    calculation = _calculation(_calculate())
    budget_fence = calculation["budget_fence"]

    assert budget_fence["lower_bound"] == {
        "role": "lower_bound",
        "label_zh": "下限",
        "base_value": 25,
        "unrounded": "25.00",
        "budget": 25,
    }
    assert budget_fence["reference_budget"] == {
        "role": "reference_budget",
        "label_zh": "参考值",
        "base_value": 32,
        "unrounded": "32.00",
        "budget": 32,
    }
    assert budget_fence["upper_bound"] == {
        "role": "upper_bound",
        "label_zh": "上限",
        "base_value": 40,
        "unrounded": "40.00",
        "budget": 40,
    }


def test_density_coef_multiplies_all_three_fence_bases() -> None:
    water = _calculation(_calculate(n_est=23, p_est=23))
    high = _calculation(_calculate(n_est=41, p_est=41))

    assert {
        role: water["budget_fence"][role]["budget"]
        for role in (
            "lower_bound",
            "reference_budget",
            "upper_bound",
        )
    } == {
        "lower_bound": 20,
        "reference_budget": 26,
        "upper_bound": 32,
    }
    assert {
        role: high["budget_fence"][role]["budget"]
        for role in (
            "lower_bound",
            "reference_budget",
            "upper_bound",
        )
    } == {
        "lower_bound": 31,
        "reference_budget": 40,
        "upper_bound": 50,
    }


def test_rounding_is_explicit_half_up_candidate_not_python_round() -> None:
    result = _calculate(
        length_chars=4225,
        l50_chars=4096,
        n_est=32,
        p_est=32,
    )
    reference = _calculation(result)["budget_fence"]["reference_budget"]

    assert Decimal(reference["unrounded"]) == Decimal("32.5")
    assert reference["budget"] == 33
    assert round(32.5) == 32
    assert result["rounding_policy"] == fence.ROUNDING_POLICY
    assert (
        result["rounding_policy"]["product_policy_status"]
        == "PENDING_CONFIRMATION"
    )


def test_missing_l50_returns_explicit_placeholders_and_no_calculation() -> None:
    result = _calculate(l50_chars=None, n_est=24, p_est=24)

    assert result["calculation_status"] == fence.L50_MISSING
    assert result["inputs"]["l50_chars"] == fence.L50_MISSING
    assert result["calculation"] is None
    assert result["missing_policy_codes"] == [
        fence.L50_MISSING,
        fence.BLOCK_SIZE_POLICY_MISSING,
    ]
    assert result["block_size_policy"] == fence.BLOCK_SIZE_POLICY_MISSING


def test_explicit_l50_is_single_calculation_input_not_global_policy() -> None:
    result = _calculate()

    assert result["calculation_status"] == (
        "CALCULATED_WITH_OPEN_POLICY_GAPS"
    )
    assert result["l50_scope"] == (
        "EXPLICIT_SINGLE_CALCULATION_INPUT_NOT_GLOBAL_POLICY"
    )
    assert result["missing_policy_codes"] == [
        fence.BLOCK_SIZE_POLICY_MISSING
    ]


def test_below_lower_is_legitimate_underfill_and_never_auto_fills() -> None:
    assessment = _count_assessment(
        _calculate(n_est=24, p_est=24, raw_candidate_count=24)
    )

    assert assessment["lower_bound"] == 25
    assert assessment["status"] == "legitimate_underfill"
    assert assessment["auto_fill_allowed"] is False
    assert assessment["next_action"] == "DO_NOT_ADD_ITEMS"


def test_lower_and_upper_boundaries_are_inside_the_fence() -> None:
    at_lower = _count_assessment(_calculate(raw_candidate_count=25))
    at_upper = _count_assessment(_calculate(raw_candidate_count=40))

    assert at_lower["status"] == "within_fence"
    assert at_upper["status"] == "within_fence"


def test_above_upper_reviews_merge_and_deduplicate_without_truncating() -> None:
    assessment = _count_assessment(_calculate(raw_candidate_count=41))

    assert assessment["status"] == "over_upper_review_required"
    assert assessment["auto_truncation_allowed"] is False
    assert assessment["next_action"] == (
        "REVIEW_MERGE_AND_DEDUPLICATE_NO_TRUNCATION"
    )


def test_granularity_anomaly_is_strictly_above_twice_upper() -> None:
    exactly_twice = _count_assessment(_calculate(raw_candidate_count=80))
    over_twice = _count_assessment(_calculate(raw_candidate_count=81))

    assert exactly_twice["anomaly_threshold_strictly_above"] == 80
    assert exactly_twice["granularity_anomaly"] is False
    assert exactly_twice["status"] == "over_upper_review_required"
    assert over_twice["granularity_anomaly"] is True
    assert over_twice["status"] == "granularity_anomaly"
    assert over_twice["auto_truncation_allowed"] is False


@pytest.mark.parametrize("blind_count", [97, 120, 184])
def test_blind_production_97_to_184_is_forbidden_as_chapter_type_input(
    blind_count: int,
) -> None:
    with pytest.raises(
        fence.DensityFenceError,
        match=fence.BLIND_PRODUCTION_INPUT_ERROR,
    ):
        fence.calculate_density_fence(
            length_chars=1000,
            l50_chars=1000,
            n_est=32,
            p_est=32,
            chapter_type_input=blind_count,
        )


def test_any_manual_chapter_type_override_is_forbidden() -> None:
    with pytest.raises(
        fence.DensityFenceError,
        match=fence.MANUAL_CHAPTER_TYPE_INPUT_ERROR,
    ):
        fence.calculate_density_fence(
            length_chars=1000,
            l50_chars=1000,
            n_est=32,
            p_est=32,
            chapter_type_input="普通",
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"length_chars": 0},
        {"l50_chars": 0},
        {"n_est": -1},
        {"p_est": -1},
        {"raw_candidate_count": -1},
        {"length_chars": True},
    ],
)
def test_invalid_counts_are_rejected(changes: dict[str, object]) -> None:
    inputs: dict[str, object] = {
        "length_chars": 1000,
        "l50_chars": 1000,
        "n_est": 32,
        "p_est": 32,
        "raw_candidate_count": None,
    }
    inputs.update(changes)
    with pytest.raises(fence.DensityFenceError):
        fence.calculate_density_fence(**inputs)


def test_schema_and_examples_keep_both_material_gaps_explicit() -> None:
    schema = json.loads(
        (
            BUNDLE_DIR
            / "schemas"
            / "density_fence_request.schema.json"
        ).read_text()
    )
    missing_request = json.loads(
        (
            BUNDLE_DIR / "examples" / "l50_missing_request.json"
        ).read_text()
    )
    block_request = json.loads(
        (
            BUNDLE_DIR
            / "examples"
            / "block_size_policy_missing_request.json"
        ).read_text()
    )

    assert schema["x_missing_policy_codes"] == [
        fence.L50_MISSING,
        fence.BLOCK_SIZE_POLICY_MISSING,
    ]
    assert schema["properties"]["l50_chars"]["oneOf"][1] == {
        "const": fence.L50_MISSING
    }
    assert schema["properties"]["block_size_policy"] == {
        "const": fence.BLOCK_SIZE_POLICY_MISSING,
        "description": "小中大三类块尺寸尚缺材料。",
    }
    assert (
        schema["x_forbidden_chapter_type_input"]
        == fence.BLIND_PRODUCTION_GUARD
    )
    assert missing_request["l50_chars"] == fence.L50_MISSING
    assert (
        missing_request["block_size_policy"]
        == fence.BLOCK_SIZE_POLICY_MISSING
    )
    assert (
        block_request["block_size_policy"]
        == fence.BLOCK_SIZE_POLICY_MISSING
    )


def test_checked_in_bundle_matches_deterministic_builder() -> None:
    expected = fence.build_bundle_files()
    for relative_path, data in expected.items():
        target = BUNDLE_DIR / relative_path
        assert target.is_file(), relative_path
        assert target.read_bytes() == data, relative_path

    checked = fence.check_bundle(BUNDLE_DIR)
    assert checked["result"] == "PASS"
    assert checked["vector_count"] == 15
    assert checked["passed_count"] == 15
    assert checked["double_run_receipt_present"]


def test_manifest_hashes_artifacts_and_keeps_release_isolated() -> None:
    manifest = json.loads((BUNDLE_DIR / "manifest.json").read_text())

    assert manifest["candidate_status"] == "candidate_silver_not_active"
    assert manifest["formula_freeze"]["base_fence_mapping"] == {
        "25": "lower_bound",
        "32": "reference_budget",
        "40": "upper_bound",
    }
    assert manifest["formula_freeze"]["rounding_policy"] == (
        fence.ROUNDING_POLICY
    )
    assert manifest["open_policy_gaps"] == [
        fence.L50_MISSING,
        fence.BLOCK_SIZE_POLICY_MISSING,
        "ROUND_HALF_UP_PRODUCT_POLICY_UNCONFIRMED",
    ]
    assert manifest["release_isolation"] == {
        "activation_allowed": False,
        "formal_gold_changed": False,
        "default_chain_changed": False,
        "current_state_changed": False,
    }
    assert manifest["scope"] == {
        "model_api_calls": 0,
        "network_requests": 0,
        "notion_writes": 0,
        "default_route_mutations": 0,
        "formal_gold_mutations": 0,
        "governance_mutations": 0,
    }
    for row in manifest["artifacts"]:
        target = BUNDLE_DIR / row["path"]
        assert target.stat().st_size == row["bytes"]
        assert fence._sha256(target.read_bytes()) == row["sha256"]


def test_double_run_receipt_is_byte_identical_and_offline() -> None:
    receipt = json.loads(
        (BUNDLE_DIR / "double_run_receipt.json").read_text()
    )

    assert receipt["runs"] == 2
    assert receipt["byte_identical"]
    assert receipt["vector_count_each_run"] == 15
    assert receipt["passed_count_each_run"] == 15
    assert receipt["pass1_tree_sha256"] == receipt["pass2_tree_sha256"]
    assert receipt["pass1_tree_sha256"] == receipt["target_tree_sha256"]
    assert receipt["numeric_l50_default_built_in"] is False
    assert receipt["model_api_calls"] == 0
    assert receipt["network_requests"] == 0


def test_cli_requires_explicit_l50_to_calculate(tmp_path: Path) -> None:
    missing = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "calculate",
            "--length-chars",
            "1000",
            "--n-est",
            "24",
            "--p-est",
            "24",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    missing_result = json.loads(missing.stdout)
    assert missing_result["calculation_status"] == fence.L50_MISSING
    assert missing_result["calculation"] is None

    explicit = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "calculate",
            "--length-chars",
            "1000",
            "--l50-chars",
            "1000",
            "--n-est",
            "24",
            "--p-est",
            "24",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    explicit_result = json.loads(explicit.stdout)
    assert explicit_result["calculation_status"] == (
        "CALCULATED_WITH_OPEN_POLICY_GAPS"
    )
    assert explicit_result["calculation"]["density_class"] == "NORMAL"

    output_dir = tmp_path / "bundle"
    built = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "build",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(built.stdout)["result"] == "BUILT"

    double_run = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "double-run",
            "--bundle-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(double_run.stdout)["result"] == (
        "PASS_BYTE_IDENTICAL"
    )

    validated = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "validate-bundle",
            "--bundle-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(validated.stdout)[
        "double_run_receipt_present"
    ]


def test_tool_imports_no_network_client() -> None:
    tree = ast.parse(TOOL_PATH.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".", 1)[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])

    forbidden = {
        "aiohttp",
        "httpx",
        "requests",
        "socket",
        "urllib",
        "websocket",
    }
    assert imported_roots.isdisjoint(forbidden)
