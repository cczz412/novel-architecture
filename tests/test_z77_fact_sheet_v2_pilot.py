from __future__ import annotations

import copy

import pytest

import z77_fact_sheet_v2_pilot as z77
from zbatch_modules import neutral_extract
from zbatch_modules.errors import ZBatchError


def catalog(*ids: str) -> list[dict[str, object]]:
    return [
        {"anchor_id": value, "chapter": 3, "quote": f"支持短引{index}"}
        for index, value in enumerate(ids, 1)
    ]


def event(event_id: str, text: str, *anchors: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event": text,
        "anchors": [{"anchor_id": value} for value in anchors],
    }


def envelope(*events: dict[str, object]) -> dict[str, object]:
    return {"schema_version": "z-event-v1", "chapter": 3, "events": list(events)}


def test_threshold_receipt_matches_live_validator() -> None:
    receipt = z77.length_threshold_receipt()
    assert receipt["maximum_nonspace_characters"] == 100
    accepted = envelope(event("EV-C0003-01", "甲" * 100, "E0001"))
    rejected = envelope(event("EV-C0003-01", "甲" * 101, "E0001"))
    assert neutral_extract.audit_event_envelope(accepted, 3, catalog("E0001"))[0] == []
    assert "EV-C0003-01事件摘要长度非法" in neutral_extract.audit_event_envelope(
        rejected, 3, catalog("E0001")
    )[0]


def test_v2_system_is_one_ordered_message_and_keeps_eight_positive_groups() -> None:
    system, meta = z77.render_system(3)
    assert meta["message_count"] == 1
    assert meta["examples"]["retained_source_group_ids"] == list(z77.SELECTED_EIGHT)
    assert meta["examples"]["added_content_groups"] == ["COG-BG-01", "UNRESOLVED-01"]
    assert "ANCHOR-COPY-01" in system
    assert "太大版（错误）" not in system
    assert "太小版（错误）" not in system
    assert system.index("【判断规则】") < system.index("【异题材正例区")
    assert system.index("【异题材正例区") < system.index("【输出合同与硬红线")
    assert "每条 event 不超过 100 个非空字符" in system
    assert "不同事件可以共用同一 anchor_id" in system


def test_candidate_body_has_one_system_and_three_line_final_reminder() -> None:
    candidate, diff = z77.build_candidate_body(13)
    assert [row["role"] for row in candidate["messages"]] == ["system", "user"]
    assert candidate["messages"][1]["content"].endswith(z77.FINAL_REMINDER)
    assert diff["changed_paths"] == ["$.messages[0].content", "$.messages[1].content"]
    assert diff["top_level_unchanged_except_messages"] is True
    assert z77.z68.request_has_prohibited_input(candidate) == []


def test_only_overlength_and_missing_anchor_are_targeted_retry_eligible() -> None:
    doc = envelope(
        event("EV-C0003-01", "甲" * 101, "E0001"),
        event("EV-C0003-02", "分析员确认记录已经复核完毕。", "E1108"),
    )
    result = z77.analyze_main_response(doc, chapter=3, catalog=catalog("E0001", "E0108"))
    assert result["hard_reasons"] == []
    assert [row["event_id"] for row in result["eligible"]] == [
        "EV-C0003-01",
        "EV-C0003-02",
    ]


def test_duplicate_anchor_is_new_failure_and_hard_stops() -> None:
    doc = envelope(
        event("EV-C0003-01", "分析员确认记录已经复核完毕。", "E0001", "E0001")
    )
    result = z77.analyze_main_response(doc, chapter=3, catalog=catalog("E0001"))
    assert result["eligible"] == []
    assert result["hard_reasons"] == ["EV-C0003-01 同一事件 anchor_id 重复"]


def test_retry_replacements_obey_length_anchor_and_split_policy() -> None:
    rows = z77.validate_replacements(
        {
            "replacement_events": [
                {"event": "分析员确认第一项记录完整。", "anchors": [{"anchor_id": "E0001"}]},
                {"event": "分析员仍无法确认第二项记录来源。", "anchors": [{"anchor_id": "E0002"}]},
            ]
        },
        catalog=catalog("E0001", "E0002"),
        allow_multiple=True,
    )
    assert len(rows) == 2
    with pytest.raises(ZBatchError, match="不得在定点重试时拆成多条"):
        z77.validate_replacements(
            {"replacement_events": rows},
            catalog=catalog("E0001", "E0002"),
            allow_multiple=False,
        )


def test_apply_replacements_only_changes_target_semantics_and_renumbers() -> None:
    original = envelope(
        event("EV-C0003-01", "分析员先核对第一份记录。", "E0001"),
        event("EV-C0003-02", "甲" * 101, "E0002"),
        event("EV-C0003-03", "分析员随后封存全部记录。", "E0003"),
    )
    replacements = {
        1: [
            {"event": "分析员确认第二份记录缺页。", "anchors": [{"anchor_id": "E0002"}]},
            {"event": "分析员尚未查明缺页原因。", "anchors": [{"anchor_id": "E0002"}]},
        ]
    }
    result = z77.apply_replacements(original, chapter=3, replacements=replacements)
    assert [row["event_id"] for row in result["events"]] == [
        "EV-C0003-01",
        "EV-C0003-02",
        "EV-C0003-03",
        "EV-C0003-04",
    ]
    assert result["events"][0]["event"] == original["events"][0]["event"]
    assert result["events"][-1]["event"] == original["events"][-1]["event"]


def test_retry_request_contains_no_gold_and_names_only_the_bad_event() -> None:
    bad = event("EV-C0003-02", "甲" * 101, "E0001")
    messages = z77.build_retry_messages(
        chapter=3,
        original_event=bad,
        violations=["event_nonspace_chars=101>100"],
        chapter_text="分析员查看记录。",
        catalog=catalog("E0001"),
    )
    assert [row["role"] for row in messages] == ["system", "user"]
    assert "EV-C0003-02" in messages[1]["content"]
    assert z77.z68.request_has_prohibited_input({"messages": messages}) == []


def test_zero_call_prepare_is_repeatable_in_isolated_directories(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    z77.prepare(first)
    z77.prepare(second)
    one = z77.verify_prepared(first, require_zero_call=True)
    two = z77.verify_prepared(second, require_zero_call=True)
    assert one["status"] == two["status"] == "pass"
    package_one = z77.read_json(first / "prompt_candidates/事实说明书注入包_v2.json")
    package_two = z77.read_json(second / "prompt_candidates/事实说明书注入包_v2.json")
    assert package_one == package_two


def test_apply_replacements_does_not_mutate_input() -> None:
    original = envelope(event("EV-C0003-01", "甲" * 101, "E0001"))
    snapshot = copy.deepcopy(original)
    z77.apply_replacements(
        original,
        chapter=3,
        replacements={0: [{"event": "分析员确认记录完整。", "anchors": [{"anchor_id": "E0001"}]}]},
    )
    assert original == snapshot
