from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys

import pytest


EXP = Path(__file__).resolve().parents[1]
TOOLS = EXP / "tools"
sys.path.insert(0, str(TOOLS))

from wo01_renderer import (  # noqa: E402
    ARM_ORDER,
    contains_forbidden_visible_metadata,
    context_for_arm,
    parse_user_sections,
    read_jsonl_strict,
    render_model_visible,
    strict_read_utf8,
    validate_projection,
)


BUILD_SPEC = importlib.util.spec_from_file_location(
    "build_wo01_inputs", TOOLS / "build_wo01_inputs.py"
)
assert BUILD_SPEC and BUILD_SPEC.loader
BUILD = importlib.util.module_from_spec(BUILD_SPEC)
BUILD_SPEC.loader.exec_module(BUILD)


def samples_and_system():
    _, samples = read_jsonl_strict(BUILD.CANONICAL)
    system, _ = BUILD.p3_baseline()
    return samples, system


def test_strict_utf8_and_invalid_bytes(tmp_path: Path):
    good = tmp_path / "good.txt"
    good.write_bytes("甲\r\n乙".encode("utf-8"))
    raw, text = strict_read_utf8(good)
    assert text.encode("utf-8") == raw
    assert b"\r\n" in raw
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff")
    with pytest.raises(UnicodeDecodeError):
        strict_read_utf8(bad)


def test_24_cases_have_gold_independent_three_way_scope():
    samples, _ = samples_and_system()
    assert len(samples) == 24
    distinct_target_small = 0
    distinct_small_current = 0
    for sample in samples:
        validated = validate_projection(sample)
        assert validated["before"] and validated["target"] and validated["after"]
        assert context_for_arm(validated, "TARGET_ONLY") == ("", "")
        small = context_for_arm(validated, "SMALL_HALO")
        current = context_for_arm(validated, "CURRENT_WINDOW")
        assert len(small[0]) == min(8, len(validated["before"]))
        assert len(small[1]) == min(8, len(validated["after"]))
        assert small[0] == validated["before"][-8:]
        assert small[1] == validated["after"][:8]
        assert current == (validated["before"], validated["after"])
        distinct_target_small += small != ("", "")
        distinct_small_current += small != current
    assert distinct_target_small == 24
    assert distinct_small_current == 24


def test_gold_mutation_does_not_change_any_model_input():
    samples, system = samples_and_system()
    for sample in samples:
        mutated = copy.deepcopy(sample)
        mutated["facts"] = [{"changed": True, "evidence": "not consulted"}]
        mutated["expected_fact_count"] = 999
        for arm in ARM_ORDER:
            assert render_model_visible(sample, arm, system) == render_model_visible(
                mutated, arm, system
            )


def test_visible_payload_has_no_hidden_arm_case_or_coordinates():
    samples, system = samples_and_system()
    for sample in samples:
        for arm in ARM_ORDER:
            visible = render_model_visible(sample, arm, system)
            assert set(visible) == {"messages"}
            assert contains_forbidden_visible_metadata(visible) == []


def test_three_arms_only_change_read_only_sections():
    samples, system = samples_and_system()
    for sample in samples:
        visible = {
            arm: render_model_visible(sample, arm, system) for arm in ARM_ORDER
        }
        assert len({row["messages"][0]["content"] for row in visible.values()}) == 1
        sections = {
            arm: parse_user_sections(row["messages"][1]["content"])
            for arm, row in visible.items()
        }
        assert len({parts["target"] for parts in sections.values()}) == 1
        assert set(sections["TARGET_ONLY"]) == {"before", "target", "after"}


def test_two_builds_are_byte_identical(tmp_path: Path):
    first = tmp_path / "run_1"
    second = tmp_path / "run_2"
    BUILD.build(first)
    BUILD.build(second)
    comparison = BUILD.compare_trees(first, second)
    assert comparison["status"] == "PASS_TWO_RUN_BYTE_IDENTICAL"
    assert comparison["mismatches"] == 0


def test_length_report_is_character_only_and_all_transitions_change():
    samples, system = samples_and_system()
    visible_by_arm = {
        arm: [render_model_visible(sample, arm, system) for sample in samples]
        for arm in ARM_ORDER
    }
    report = BUILD.build_length_report(
        [sample["case_id"] for sample in samples], visible_by_arm
    )
    assert report["status"] == "PASS_CHARACTER_LENGTH_GUARD_NO_TOKENIZER"
    assert report["measurement_contract"]["tokenizer_loaded"] is False
    assert report["measurement_contract"]["token_count_claimed"] is False
    assert len(report["per_case"]) == 24
    for row in report["per_case"]:
        arms = row["arms"]
        assert (
            arms["TARGET_ONLY"]["unicode_characters"]
            < arms["SMALL_HALO"]["unicode_characters"]
            < arms["CURRENT_WINDOW"]["unicode_characters"]
        )
        assert (
            arms["TARGET_ONLY"]["utf8_bytes"]
            < arms["SMALL_HALO"]["utf8_bytes"]
            < arms["CURRENT_WINDOW"]["utf8_bytes"]
        )
