from __future__ import annotations

from experiments.extraction_redesign_v02_overnight_20260725.V02_R1_route_comparison_r02_20260726 import (
    v02_r1_route_runner as runner,
)


def test_frozen_tree_is_valid_before_send() -> None:
    assert runner.verify_frozen_tree()["status"] == "PASS"


def test_open_cell_is_answerable_without_material() -> None:
    cell = {
        "cell_id": "B02-U0039::R1-Q06",
        "expected": "OPEN",
        "required_parts": [],
    }
    result = runner.cell_score(cell, [], {"B02-U0039-S0001"})
    assert result["answerable"] is True
    assert result["critical_errors"] == []


def test_answered_cell_requires_each_source_group() -> None:
    cell = {
        "cell_id": "X::Q",
        "expected": "ANSWERED",
        "required_parts": [
            {
                "part_id": "P1",
                "source_id_groups": [["S1"], ["S2", "S3"]],
                "must_retain_uncertainty": False,
                "must_retain_negation": False,
            }
        ],
    }
    result = runner.cell_score(
        cell,
        [
            {
                "material_id": "F1",
                "statement": "事实",
                "source_ids": ["S1", "S3"],
                "kind": "FACT",
            }
        ],
        {"S1", "S2", "S3"},
    )
    assert result["answerable"] is True


def test_cold_pointer_cannot_substitute_for_an_answer_fact() -> None:
    cell = {
        "cell_id": "X::Q",
        "expected": "ANSWERED",
        "required_parts": [
            {
                "part_id": "P1",
                "source_id_groups": [["S1"]],
                "must_retain_uncertainty": False,
                "must_retain_negation": False,
            }
        ],
    }
    result = runner.cell_score(
        cell,
        [
            {
                "material_id": "COLD::S1",
                "statement": "",
                "source_ids": ["S1"],
                "kind": "COLD_POINTER",
            }
        ],
        {"S1"},
    )
    assert result["answerable"] is False
    assert result["missing_part_ids"] == ["P1"]


def test_invalid_source_and_modality_loss_are_critical_errors() -> None:
    cell = {
        "cell_id": "X::Q",
        "expected": "ANSWERED",
        "required_parts": [
            {
                "part_id": "P1",
                "source_id_groups": [["S1"]],
                "must_retain_uncertainty": True,
                "must_retain_negation": False,
            }
        ],
    }
    result = runner.cell_score(
        cell,
        [
            {
                "material_id": "F1",
                "statement": "这件事已经确定",
                "source_ids": ["S1", "BAD"],
                "kind": "FACT",
            }
        ],
        {"S1"},
    )
    codes = {row["code"] for row in result["critical_errors"]}
    assert codes == {"INVALID_SOURCE_ID", "UNCERTAINTY_UPGRADED"}


def test_material_token_excludes_reasoning_tokens() -> None:
    usage = {
        "completion_tokens": 100,
        "completion_tokens_details": {"reasoning_tokens": 60},
    }
    assert runner.usage_material_tokens(usage) == 40
