from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
TOOL_PATH = PRODUCT_ROOT / "mvp/plan_selection_target_tool.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import plan_selection_target_tool, plan_tool
finally:
    sys.path.pop(0)


def _option(option_id: str) -> dict:
    return {
        "id": option_id,
        "label": f"{option_id}项局部规划方向",
        "reveal_intent": f"只透露{option_id}项对应的信息点",
    }


def _card(
    card_id: str,
    planning_card_ref: str,
    *,
    recommended: str = "B",
) -> dict:
    return {
        "id": card_id,
        "role": "attach",
        "title": f"{card_id}的合成规划卡",
        "purpose_note": "只绑定局部选择，不写计划",
        "options": [_option("C"), _option("A"), _option("B")],
        "recommended_option_ref": recommended,
        "planning_card_ref": planning_card_ref,
        "planning_card_rev": 3,
        "guidance": {
            "card_problem": "明确这一张卡要解决的问题",
            "dialogue_reveal": "只给信息点，不给成文",
            "plugin_craft": "",
        },
    }


def _c7() -> dict:
    return {
        "contract": "C7_PLOT_LAYER v1",
        "project": "合成选择目标项目",
        "generated_at": "2026-08-20 00:30:00",
        "model": "FROZEN_SYNTHETIC_PROVIDER",
        "purpose": "让角色发现线索",
        "purpose_note": "不在本章揭底",
        "mode": "forward",
        "purpose_placement": "attach",
        "chapter_intent": "只推进调查",
        "confirmed_fact_ids": [],
        "cards": [
            _card("card01", "AC-0007"),
            _card("card02", "AC-0008", recommended="A"),
        ],
        "conflicts": [],
    }


def _request(
    c7: dict,
    *,
    card_local_id: str = "card01",
    choice: str = "B",
    sha256: str | None = None,
) -> dict:
    return {
        "c7": c7,
        "expected_c7_snapshot_sha256": (
            plan_tool.c7_snapshot_sha256(c7) if sha256 is None else sha256
        ),
        "card_local_id": card_local_id,
        "choice": choice,
    }


def _run_cli(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        input=stdin,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


@pytest.mark.parametrize(
    ("choice", "recommended_match"),
    [("A", False), ("B", True), ("C", False), ("discard", None)],
)
def test_four_choices_bind_original_card_option_and_recommendation_truthfully(
    choice: str,
    recommended_match: bool | None,
) -> None:
    c7 = _c7()
    request = _request(c7, choice=choice)
    before = copy.deepcopy(request)

    result = plan_selection_target_tool.execute(request)

    assert request == before
    assert result["kind"] == "C7_LOCAL_SELECTION_TARGET_PROTOTYPE"
    assert result["identity"] == "transport_only_no_plan_write"
    assert result["card"] == c7["cards"][0]
    assert result["planning_card_ref"] == "AC-0007"
    assert result["planning_card_rev"] == 3
    assert result["recommended_option_ref"] == "B"
    assert result["is_recommended_choice"] is recommended_match
    if choice == "discard":
        assert result["selected_option"] is None
        assert result["selection_target_summary"] == {
            "card_title": c7["cards"][0]["title"],
            "option_label": None,
            "reveal_intent": None,
        }
    else:
        expected_option = next(
            option for option in c7["cards"][0]["options"] if option["id"] == choice
        )
        assert result["selected_option"] == expected_option
        assert result["selection_target_summary"] == {
            "card_title": c7["cards"][0]["title"],
            "option_label": expected_option["label"],
            "reveal_intent": expected_option["reveal_intent"],
        }
    assert not (
        {
            "contract",
            "option_record",
            "expected_revs",
            "plan_mutations",
            "digest_applied",
        }
        & set(result)
    )


def test_nonrecommended_choice_on_second_card_is_not_rewritten_to_recommendation() -> None:
    c7 = _c7()

    result = plan_selection_target_tool.execute(
        _request(c7, card_local_id="card02", choice="C")
    )

    assert result["choice"] == "C"
    assert result["selected_option"]["id"] == "C"
    assert result["recommended_option_ref"] == "A"
    assert result["is_recommended_choice"] is False
    assert result["planning_card_ref"] == "AC-0008"


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        ("stale_sha", "STALE_C7_SNAPSHOT"),
        ("bad_sha", "EXPECTED_C7_SNAPSHOT_SHA256_INVALID"),
        ("missing_card", "CARD_LOCAL_ID_NOT_FOUND:card99"),
        ("bad_card", "CARD_LOCAL_ID_INVALID"),
        ("bad_choice", "CHOICE_INVALID:D"),
        ("missing_choice_option", "CHOICE_OPTION_NOT_FOUND:A"),
        ("bad_c7", "C7_SNAPSHOT_INVALID:RECOMMENDED_OPTION_NOT_FOUND"),
        ("missing_field", "REQUEST_FIELDS_INVALID"),
    ],
)
def test_stale_bad_card_choice_or_c7_fails_closed(
    damage: str,
    reason: str,
) -> None:
    c7 = _c7()
    request = _request(c7)
    if damage == "stale_sha":
        request["expected_c7_snapshot_sha256"] = "0" * 64
    elif damage == "bad_sha":
        request["expected_c7_snapshot_sha256"] = "short"
    elif damage == "missing_card":
        request["card_local_id"] = "card99"
    elif damage == "bad_card":
        request["card_local_id"] = ""
    elif damage == "bad_choice":
        request["choice"] = "D"
    elif damage == "missing_choice_option":
        c7["cards"][0]["options"] = [
            option for option in c7["cards"][0]["options"] if option["id"] != "A"
        ]
        request = _request(c7, choice="A")
    elif damage == "bad_c7":
        c7["cards"][0]["recommended_option_ref"] = "Z"
        request["c7"] = c7
    else:
        request.pop("choice")

    with pytest.raises(
        plan_selection_target_tool.PlanSelectionTargetToolError,
        match=reason,
    ):
        plan_selection_target_tool.execute(request)


def test_card_or_option_list_reorder_changes_sha_and_rejects_old_selection() -> None:
    c7 = _c7()
    old_sha = plan_tool.c7_snapshot_sha256(c7)
    cards_reordered = copy.deepcopy(c7)
    cards_reordered["cards"].reverse()
    options_reordered = copy.deepcopy(c7)
    options_reordered["cards"][0]["options"].reverse()

    assert plan_tool.c7_snapshot_sha256(cards_reordered) != old_sha
    assert plan_tool.c7_snapshot_sha256(options_reordered) != old_sha
    for changed in (cards_reordered, options_reordered):
        with pytest.raises(
            plan_selection_target_tool.PlanSelectionTargetToolError,
            match="STALE_C7_SNAPSHOT",
        ):
            plan_selection_target_tool.execute(
                _request(changed, sha256=old_sha)
            )


def test_cli_file_stdout_and_repeated_processes_are_byte_stable(
    tmp_path: Path,
) -> None:
    request = _request(_c7(), choice="C")
    input_path = tmp_path / "c7-choice.json"
    first_path = tmp_path / "target-first.json"
    second_path = tmp_path / "target-second.json"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")

    first = _run_cli("--input", str(input_path), "--output", str(first_path))
    second = _run_cli("--input", str(input_path), "--output", str(second_path))
    stdout = _run_cli("--input", str(input_path))

    assert first.returncode == second.returncode == stdout.returncode == 0
    expected = plan_selection_target_tool._output_bytes(
        plan_selection_target_tool.execute(request)
    )
    assert first_path.read_bytes() == second_path.read_bytes() == stdout.stdout
    assert stdout.stdout == expected


def test_cli_same_path_and_atomic_failure_preserve_existing_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(_c7())
    same_path = tmp_path / "same.json"
    same_bytes = json.dumps(request, ensure_ascii=False).encode("utf-8")
    same_path.write_bytes(same_bytes)

    completed = _run_cli(
        "--input",
        str(same_path),
        "--output",
        str(same_path),
    )
    assert completed.returncode == 2
    assert b"INPUT_OUTPUT_PATH_MUST_DIFFER" in completed.stderr
    assert same_path.read_bytes() == same_bytes

    output_path = tmp_path / "existing-target.json"
    original = b'{"keep":"old"}\n'
    output_path.write_bytes(original)

    def fail_replace(*args, **kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(plan_selection_target_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        plan_selection_target_tool._write_json_atomic(
            output_path,
            plan_selection_target_tool.execute(request),
        )
    assert output_path.read_bytes() == original
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []
