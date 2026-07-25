#!/usr/bin/env python3
"""V02/C10.2：把章级计数机械展开成三套报告视图。

三套视图固定为：微平均、宏平均、逐章值与范围。三章只允许写成探索性
观察，不能冒充跨书或总体泛化结论。只有 ``25/49`` 这类合计而没有逐章
输入的报告会被直接拒收。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
DEFAULT_OUTPUT_DIR = V02_ROOT / "V02_C10_scoreability_and_reporting_20260725"

ALLOWED_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "report_id",
        "exploratory_only",
        "quality_verdict_allowed",
        "chapters",
        "aggregate",
    }
)
ALLOWED_CHAPTER_FIELDS = frozenset({"case_id", "numerator", "denominator"})


class ReportingViewsError(RuntimeError):
    """报告输入不能按三套固定口径安全展开。"""


def stable_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")


def _display_fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _decimal(value: Fraction) -> float:
    return round(float(value), 6)


def _percent_one_decimal(value: Fraction) -> str:
    return f"{float(value) * 100:.1f}%"


def build_views(document: Mapping[str, Any]) -> dict[str, Any]:
    """计算微平均、宏平均、逐章值与范围，不下实验胜负。"""

    if document.get("schema_version") != "v02-reporting-views-input.v1":
        raise ReportingViewsError("报告输入 schema_version 不受支持")
    unexpected_top_level = sorted(
        str(key) for key in set(document) - ALLOWED_TOP_LEVEL_FIELDS
    )
    if unexpected_top_level:
        raise ReportingViewsError(
            f"报告含合同未声明字段：{unexpected_top_level}"
        )
    report_value = document.get("report_id")
    if not isinstance(report_value, str) or not report_value.strip():
        raise ReportingViewsError("报告缺 report_id 身份")
    report_id = report_value.strip()
    exploratory_value = document.get("exploratory_only", False)
    quality_authority_value = document.get(
        "quality_verdict_allowed",
        False,
    )
    if not isinstance(exploratory_value, bool):
        raise ReportingViewsError("exploratory_only 必须是布尔值")
    if not isinstance(quality_authority_value, bool):
        raise ReportingViewsError("quality_verdict_allowed 必须是布尔值")
    chapters = document.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        aggregate = document.get("aggregate")
        is_standalone_25_of_49 = aggregate == "25/49" or (
            isinstance(aggregate, Mapping)
            and aggregate.get("numerator") == 25
            and aggregate.get("denominator") == 49
        )
        if is_standalone_25_of_49:
            raise ReportingViewsError(
                "单独 25/49 拒收：必须同时提供逐章分子、分母与范围"
            )
        raise ReportingViewsError("缺逐章输入，合计值不得单独成报告")
    if "aggregate" in document:
        raise ReportingViewsError("逐章输入与 aggregate 不得并存")

    chapter_count = len(chapters)
    insufficient_to_generalize = chapter_count <= 3
    exploratory_only = exploratory_value or insufficient_to_generalize

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in chapters:
        if not isinstance(row, Mapping):
            raise ReportingViewsError("逐章行不是对象")
        unexpected_chapter_fields = sorted(
            str(key) for key in set(row) - ALLOWED_CHAPTER_FIELDS
        )
        if unexpected_chapter_fields:
            raise ReportingViewsError(
                f"逐章行含合同未声明字段：{unexpected_chapter_fields}"
            )
        case_value = row.get("case_id")
        if not isinstance(case_value, str) or not case_value.strip():
            raise ReportingViewsError("逐章行缺 case_id 身份")
        case_id = case_value.strip()
        numerator = row.get("numerator")
        denominator = row.get("denominator")
        if not case_id or case_id in seen:
            raise ReportingViewsError("逐章 case_id 缺失或重复")
        if (
            isinstance(numerator, bool)
            or not isinstance(numerator, int)
            or isinstance(denominator, bool)
            or not isinstance(denominator, int)
            or denominator <= 0
            or numerator < 0
            or numerator > denominator
        ):
            raise ReportingViewsError(f"{case_id} 分子分母不合法")
        seen.add(case_id)
        fraction = Fraction(numerator, denominator)
        normalized.append(
            {
                "case_id": case_id,
                "numerator": numerator,
                "denominator": denominator,
                "fraction": _display_fraction(fraction),
                "rate": _decimal(fraction),
                "display_percent": _percent_one_decimal(fraction),
            }
        )

    total_numerator = sum(row["numerator"] for row in normalized)
    total_denominator = sum(row["denominator"] for row in normalized)
    micro = Fraction(total_numerator, total_denominator)
    chapter_fractions = [
        Fraction(row["numerator"], row["denominator"]) for row in normalized
    ]
    macro = sum(chapter_fractions, Fraction(0, 1)) / len(chapter_fractions)
    minimum = min(chapter_fractions)
    maximum = max(chapter_fractions)
    spread = maximum - minimum
    return {
        "schema_version": "v02-reporting-views-receipt.v1",
        "report_id": report_id,
        "exploratory_only": exploratory_only,
        "quality_verdict_allowed": False,
        "separate_quality_authority_required": True,
        "views": {
            "micro_average": {
                "meaning": "把各章分子相加、分母相加；大分母章节权重更高。",
                "numerator": total_numerator,
                "denominator": total_denominator,
                "fraction": f"{total_numerator}/{total_denominator}",
                "rate": _decimal(micro),
                "display_percent": _percent_one_decimal(micro),
                "must_not_be_reported_alone": True,
            },
            "macro_average": {
                "meaning": "先算每章比例再等权平均；每章权重相同。",
                "chapter_total": chapter_count,
                "rate": _decimal(macro),
                "display_percent": _percent_one_decimal(macro),
            },
            "per_chapter_and_range": {
                "meaning": "逐章原值与最小、最大、跨度；不能藏掉难章。",
                "chapters": normalized,
                "minimum_rate": _decimal(minimum),
                "maximum_rate": _decimal(maximum),
                "spread": _decimal(spread),
                "minimum_display_percent": _percent_one_decimal(minimum),
                "maximum_display_percent": _percent_one_decimal(maximum),
                "spread_display_percentage_points": (
                    f"{float(spread) * 100:.1f}"
                ),
            },
        },
        "generalization_boundary": {
            "chapter_total": chapter_count,
            "insufficient_to_generalize": insufficient_to_generalize,
            "required_statement": (
                f"本报告只覆盖 {chapter_count} 章，只能作为探索性观察，"
                "不足以代表跨书、总体或稳定泛化表现。"
                if insufficient_to_generalize
                else "本工具不自动授予泛化资格；仍须按另行批准的样本设计判断。"
            ),
            "standalone_micro_fraction_is_formal_conclusion": False,
        },
    }


def reporting_contract() -> dict[str, Any]:
    return {
        "schema_version": "v02-reporting-views-contract.v1",
        "required_input": {
            "schema_version": "v02-reporting-views-input.v1",
            "chapters": "非空数组；每行 case_id、numerator、denominator",
            "exploratory_only": "布尔值",
        },
        "strict_field_policy": (
            "输入只认合同白名单；顶层或逐章行出现任何未声明字段一律拒收，"
            "不得靠改名夹带赢家、过闸、推荐或升格结论。"
        ),
        "required_views": [
            "micro_average",
            "macro_average",
            "per_chapter_and_range",
        ],
        "three_chapter_rule": (
            "三章必须标 exploratory_only；写明不足以泛化，不得下胜负。"
        ),
        "standalone_25_of_49_rule": (
            "只有 25/49 而无逐章值与范围时直接拒收。"
        ),
        "precision_rule": (
            "保留精确分子分母供复算，面向人的百分比只显示一位小数；"
            "不得把 51.02% 写成总体精度。"
        ),
        "quality_authority_rule": (
            "本工具只展开报告口径，任何章数都不得授予质量胜负资格；"
            "正式质量结论须另有独立批准票。"
        ),
    }


def three_chapter_example_input() -> dict[str, Any]:
    return {
        "schema_version": "v02-reporting-views-input.v1",
        "report_id": "C7_TREATMENT_COVERAGE_EXAMPLE",
        "exploratory_only": True,
        "quality_verdict_allowed": False,
        "chapters": [
            {"case_id": "B02-U0039", "numerator": 5, "denominator": 8},
            {"case_id": "B03-U0041", "numerator": 7, "denominator": 16},
            {"case_id": "B01-U0033", "numerator": 13, "denominator": 25},
        ],
    }


def build_artifacts() -> dict[str, bytes]:
    example = three_chapter_example_input()
    reject_message: str
    try:
        build_views(
            {
                "schema_version": "v02-reporting-views-input.v1",
                "report_id": "REJECT_STANDALONE_25_OF_49",
                "exploratory_only": True,
                "aggregate": "25/49",
            }
        )
    except ReportingViewsError as exc:
        reject_message = str(exc)
    else:
        raise ReportingViewsError("单独 25/49 未被拒收")
    return {
        "reporting_views_contract.json": stable_json_bytes(
            reporting_contract()
        ),
        "three_chapter_example_input.json": stable_json_bytes(example),
        "three_chapter_reporting_views.json": stable_json_bytes(
            build_views(example)
        ),
        "standalone_25_of_49_reject_receipt.json": stable_json_bytes(
            {
                "schema_version": "v02-reporting-reject-receipt.v1",
                "status": "REJECTED",
                "input": "25/49",
                "reason": reject_message,
                "quality_verdict_allowed": False,
            }
        ),
    }


def write_or_verify(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    shas: dict[str, str] = {}
    for name, raw in build_artifacts().items():
        path = output_dir / name
        if path.exists() and path.read_bytes() != raw:
            raise ReportingViewsError(f"既有产物字节不一致：{path}")
        path.write_bytes(raw)
        shas[name] = hashlib.sha256(raw).hexdigest()
    return shas


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument("--input", type=Path)
    args = parser.parse_args(argv)
    if args.input:
        document = json.loads(args.input.read_text(encoding="utf-8"))
        print(stable_json_bytes(build_views(document)).decode("utf-8"), end="")
        return 0
    print(
        json.dumps(
            write_or_verify(args.output_dir),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
