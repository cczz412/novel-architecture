from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_reporting_views as reporting  # noqa: E402


pytestmark = pytest.mark.v02


def test_three_views_report_micro_macro_and_chapter_range() -> None:
    receipt = reporting.build_views(
        reporting.three_chapter_example_input()
    )
    views = receipt["views"]
    assert views["micro_average"]["fraction"] == "25/49"
    assert views["micro_average"]["rate"] == round(25 / 49, 6)
    assert views["micro_average"]["must_not_be_reported_alone"] is True
    assert views["macro_average"]["rate"] == 0.5275
    by_chapter = views["per_chapter_and_range"]
    assert [row["fraction"] for row in by_chapter["chapters"]] == [
        "5/8",
        "7/16",
        "13/25",
    ]
    assert by_chapter["minimum_rate"] == 0.4375
    assert by_chapter["maximum_rate"] == 0.625
    assert by_chapter["spread"] == 0.1875


def test_three_chapters_are_explicitly_not_generalizable() -> None:
    receipt = reporting.build_views(
        reporting.three_chapter_example_input()
    )
    boundary = receipt["generalization_boundary"]
    assert boundary["chapter_total"] == 3
    assert boundary["insufficient_to_generalize"] is True
    assert "不足以代表跨书、总体或稳定泛化表现" in boundary[
        "required_statement"
    ]
    assert receipt["exploratory_only"] is True
    assert receipt["quality_verdict_allowed"] is False
    assert receipt["separate_quality_authority_required"] is True
    assert "winner" not in receipt
    assert "experiment_gate_pass" not in receipt


@pytest.mark.parametrize(
    "aggregate",
    ["25/49", {"numerator": 25, "denominator": 49}],
)
def test_standalone_25_of_49_is_rejected(aggregate: object) -> None:
    with pytest.raises(reporting.ReportingViewsError, match="25/49"):
        reporting.build_views(
            {
                "schema_version": "v02-reporting-views-input.v1",
                "report_id": "BAD-STANDALONE",
                "exploratory_only": True,
                "aggregate": aggregate,
            }
        )


def test_any_aggregate_without_chapters_is_rejected() -> None:
    with pytest.raises(reporting.ReportingViewsError, match="缺逐章输入"):
        reporting.build_views(
            {
                "schema_version": "v02-reporting-views-input.v1",
                "report_id": "BAD-STANDALONE",
                "exploratory_only": True,
                "aggregate": "4/10",
            }
        )


def test_exploratory_input_cannot_smuggle_a_winner() -> None:
    document = reporting.three_chapter_example_input()
    document["winner"] = "treatment"
    with pytest.raises(reporting.ReportingViewsError, match="未声明字段"):
        reporting.build_views(document)


@pytest.mark.parametrize(
    "field,value",
    [
        ("winner_arm", "treatment"),
        ("best_arm", "treatment"),
        ("quality_result", {"status": "PASS"}),
        ("experiment_gate_pass", True),
        ("recommended-arm", "treatment"),
        ("chosen_arm", "treatment"),
        ("champion_arm", "treatment"),
    ],
)
def test_automatic_three_chapter_exploratory_mode_rejects_decision_aliases(
    field: str,
    value: object,
) -> None:
    document = reporting.three_chapter_example_input()
    document["exploratory_only"] = False
    document[field] = value
    with pytest.raises(reporting.ReportingViewsError, match="未声明字段"):
        reporting.build_views(document)


def test_missing_report_or_case_identity_is_hard_rejected() -> None:
    document = reporting.three_chapter_example_input()
    del document["report_id"]
    with pytest.raises(reporting.ReportingViewsError, match="report_id"):
        reporting.build_views(document)

    document = reporting.three_chapter_example_input()
    del document["chapters"][0]["case_id"]
    with pytest.raises(reporting.ReportingViewsError, match="case_id"):
        reporting.build_views(document)


def test_more_than_three_chapters_still_cannot_self_authorize_quality() -> None:
    document = reporting.three_chapter_example_input()
    document["chapters"].append(
        {"case_id": "B04-U0003", "numerator": 9, "denominator": 12}
    )
    document["exploratory_only"] = False
    document["quality_verdict_allowed"] = True
    receipt = reporting.build_views(document)
    assert receipt["generalization_boundary"]["chapter_total"] == 4
    assert receipt["exploratory_only"] is False
    assert receipt["quality_verdict_allowed"] is False
    assert receipt["separate_quality_authority_required"] is True


def test_more_than_three_chapters_reject_winner_aliases_too() -> None:
    document = reporting.three_chapter_example_input()
    document["chapters"].append(
        {"case_id": "B04-U0003", "numerator": 9, "denominator": 12}
    )
    document["winner_arm"] = "treatment"
    with pytest.raises(reporting.ReportingViewsError, match="未声明字段"):
        reporting.build_views(document)


def test_chapter_row_rejects_uncontracted_decision_fields() -> None:
    document = reporting.three_chapter_example_input()
    document["chapters"][0]["chosen_arm"] = "treatment"
    with pytest.raises(reporting.ReportingViewsError, match="未声明字段"):
        reporting.build_views(document)


def test_duplicate_chapter_and_bad_fraction_are_rejected() -> None:
    document = reporting.three_chapter_example_input()
    document["chapters"][1]["case_id"] = document["chapters"][0]["case_id"]
    with pytest.raises(reporting.ReportingViewsError, match="重复"):
        reporting.build_views(document)

    document = reporting.three_chapter_example_input()
    document["chapters"][0]["numerator"] = 9
    with pytest.raises(reporting.ReportingViewsError, match="不合法"):
        reporting.build_views(document)


def test_double_build_and_write_are_byte_identical(tmp_path: Path) -> None:
    assert reporting.build_artifacts() == reporting.build_artifacts()
    first = reporting.write_or_verify(tmp_path)
    before = {
        path.name: path.read_bytes() for path in sorted(tmp_path.iterdir())
    }
    second = reporting.write_or_verify(tmp_path)
    after = {
        path.name: path.read_bytes() for path in sorted(tmp_path.iterdir())
    }
    assert first == second
    assert before == after
    receipt = json.loads(
        (tmp_path / "standalone_25_of_49_reject_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["status"] == "REJECTED"
