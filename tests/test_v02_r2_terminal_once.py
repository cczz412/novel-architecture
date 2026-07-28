from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.V02_R2_terminal_once_20260727 import (
    terminal_controller as terminal,
)


def test_question_adapter_accepts_shared_ten_slot_template() -> None:
    case_ids = ["C1", "C2", "C3"]
    question_set = {
        "questions": [
            {
                "question_id": f"Q{index:02d}",
                "question_text": "主角当前在哪里，处于什么状态？",
            }
            for index in range(1, 11)
        ]
    }
    cells = terminal.extract_question_cells(question_set, case_ids=case_ids)
    assert len(cells) == 30
    assert {row["case_id"] for row in cells} == set(case_ids)


def test_question_adapter_rejects_wrong_layout() -> None:
    with pytest.raises(terminal.TerminalError, match="QUESTION_LAYOUT_INVALID"):
        terminal.extract_question_cells(
            {"questions": [{"question_id": "Q1", "question_text": "x"}]},
            case_ids=["C1", "C2", "C3"],
        )


def test_model_selection_rejects_unknown_source_id() -> None:
    envelope = {
        "model": terminal.EXPECTED_RESPONSE_MODEL,
        "content": json.dumps(
            {"status": "ANSWER", "selected_source_ids": ["UNKNOWN"]}
        ),
    }
    with pytest.raises(
        terminal.TerminalError,
        match="MODEL_SELECTION_SOURCE_ID_UNKNOWN",
    ):
        terminal.parse_model_selection(
            envelope,
            allowed_source_ids={"C1-S0001"},
        )


def test_gold_adapter_supports_inline_heads() -> None:
    gold = {
        "cells": [
            {
                "case_id": case_id,
                "question_id": f"Q{index:02d}",
                "answerability": "ANSWERABLE",
                "required_heads": [
                    {
                        "head_id": f"H{index:02d}",
                        "source_id_groups": [[f"{case_id}-S0001"]],
                    }
                ],
            }
            for case_id in ("C1", "C2", "C3")
            for index in range(1, 11)
        ]
    }
    cells = terminal.extract_gold_cells(gold)
    assert len(cells) == 30
    assert cells[0]["required_heads"][0]["source_id_groups"]


def test_gold_adapter_supports_shared_head_catalog() -> None:
    gold = {
        "head_catalog": [
            {
                "head_id": f"H{index:02d}",
                "source_id_groups": [["C1-S0001"]],
            }
            for index in range(1, 11)
        ],
        "cells": [
            {
                "case_id": case_id,
                "question_id": f"Q{index:02d}",
                "required_head_ids": [f"H{index:02d}"],
            }
            for case_id in ("C1", "C2", "C3")
            for index in range(1, 11)
        ],
    }
    cells = terminal.extract_gold_cells(gold)
    assert len(cells) == 30


def test_score_counts_extra_source_as_critical_error() -> None:
    answer = {
        "claims": [
            {
                "source_id": "C1-S9999",
                "source_id_aliases": ["C1-S9999"],
            }
        ],
        "status": "ANSWER",
        "answer_payload_sha256": "a" * 64,
        "cost": {"model_elapsed_ms": 1},
        "usage": {"total_tokens": 1},
    }
    gold = {
        "cell_id": "C1::Q01",
        "question_id": "Q01",
        "answerability": "ANSWERABLE",
        "required_heads": [
            {
                "head_id": "H01",
                "source_id_groups": [["C1-S0001"]],
            }
        ],
    }
    result = terminal.score_answer(answer=answer, gold=gold)
    assert result["critical_error"] is True
    assert result["full_supported"] is False


def test_zero_api_preflight_is_private_free(tmp_path: Path) -> None:
    result = terminal.zero_api_preflight(tmp_path)
    assert result["status"] == "PASS"
    assert result["model_api_calls"] == 0
    assert result["network_requests"] == 0
    assert result["terminal_private_files_read"] == 0
    assert result["route_counts"] == {"A5": 30, "QEC": 30}
