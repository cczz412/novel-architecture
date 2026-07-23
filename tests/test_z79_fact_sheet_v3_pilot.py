from __future__ import annotations

import json

import z79_fact_sheet_v3_pilot as z79


def test_v2_sources_are_pinned_and_read_only() -> None:
    receipt = z79.assert_v2_sources()
    assert receipt["status"] == "pass"
    assert len(receipt["sources"]) == 9


def test_v3_system_has_only_the_two_approved_repair_groups() -> None:
    system, meta = z79.render_system(3)
    assert meta["line_diff"]["only_additions"] is True
    assert meta["line_diff"]["removed_lines"] == []
    assert system.count(z79.JUDGMENT_RULE) == 1
    assert system.count(z79.ANCHOR_SUPPORT_RULE) == 1
    assert system.count(z79.QUESTION_EXAMPLE) == 1
    assert all(token not in system for token in z79.CASE_TOKENS_FORBIDDEN_IN_INJECTION)
    assert meta["repairs"][0]["repair_id"] == "anchor_support_complete"
    assert meta["repairs"][1]["repair_id"] == "dialogue_conclusion_separation"


def test_v3_additions_are_in_the_four_fixed_unique_locations() -> None:
    system, _ = z79.render_system(13)
    registry = z79.layer_registry()
    assert registry["status"] == "pass_four_unique_locations"
    assert len(registry["rows"]) == 4
    assert len({row["addition_id"] for row in registry["rows"]}) == 4
    assert all(row["unique_location"] for row in registry["rows"])
    positions = [system.index(section) for section in z79.FIXED_SYSTEM_LAYER_ORDER]
    assert positions == sorted(positions)
    assert system.index(z79.JUDGMENT_RULE) < system.index("【证据规则】")
    assert system.index(z79.ANCHOR_SUPPORT_RULE) < system.index("【静默检查】")
    assert system.index(z79.QUESTION_EXAMPLE) < system.index("【正例区结束】")


def test_v3_dedup_receipt_preserves_v2_six_rows_and_adds_registry_only() -> None:
    base = z79._v2_package()["deduplication"]
    current = z79.updated_deduplication_receipt()
    assert current["merged_duplicates"] == base["merged_duplicates"]
    assert current["precedence"] == base["precedence"]
    assert current["moved_near_output"] == base["moved_near_output"]
    assert current["base_v2_deduplication"]["merged_duplicate_count"] == 6
    assert current["base_v2_deduplication"]["preserved_unchanged"] is True
    assert current["v3_unique_layer_additions"] == z79.layer_registry()["rows"]
    assert current["v3_duplicate_expression_elsewhere"] is False


def test_candidate_body_changes_only_system_and_user_text() -> None:
    for chapter in z79.TARGET_CHAPTERS:
        candidate, diff = z79.build_candidate_body(chapter)
        assert diff["changed_paths"] == ["$.messages[0].content", "$.messages[1].content"]
        assert diff["sampling_and_transport_unchanged"] is True
        assert diff["user_line_diff"]["added_lines"] == [z79.FINAL_ANCHOR_REMINDER]
        assert diff["user_line_diff"]["removed_lines"] == []
        assert candidate["messages"][1]["content"].endswith(z79.FINAL_REMINDER)
        assert z79.z68.request_has_prohibited_input(candidate) == []


def test_question_example_is_mechanically_decoupled_from_six_corpora() -> None:
    receipt = z79.question_example_decoupling()
    assert receipt["status"] == "pass"
    assert all(row["status"] == "pass" for row in receipt["gates"].values())


def test_targeted_retry_contract_is_exactly_v2() -> None:
    package = z79.build_package()
    assert package["targeted_retry_system"] == z79.z77.RETRY_SYSTEM
    assert package["targeted_retry_equals_v2"] is True
    assert package["targeted_retry_policy"] == {
        "eligible": ["event超过100个非空字符", "anchor_id格式非法或不在当前冻结目录"],
        "per_event_limit": 1,
        "per_chapter_limit": 3,
        "total_limit": 6,
        "other_errors": "hard_stop_no_repair",
    }


def test_zero_call_prepare_is_repeatable_and_writes_supplemental_ledgers(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    z79.prepare(first)
    z79.prepare(second)
    assert z79.verify_prepared(first, require_zero_call=True)["status"] == "pass"
    assert z79.verify_prepared(second, require_zero_call=True)["status"] == "pass"
    package_one = z79.read_json(first / "prompt_candidates/事实说明书注入包_v3.json")
    package_two = z79.read_json(second / "prompt_candidates/事实说明书注入包_v3.json")
    assert package_one == package_two
    assert z79.read_json(first / "prompt_candidates/v3层位登记表.json") == package_one[
        "layer_registry"
    ]
    assert z79.read_json(first / "prompt_candidates/去重与唯一落点账_v3.json") == package_one[
        "deduplication"
    ]
    assert not z79.call_artifacts_present(first)


def test_package_can_be_round_tripped_without_model_visible_drift() -> None:
    package = z79.build_package()
    encoded = json.dumps(package, ensure_ascii=False, sort_keys=True)
    decoded = json.loads(encoded)
    assert decoded == package
    assert package["v2_to_v3_diff"]["repair_group_count"] == 2
    assert package["v2_to_v3_diff"]["no_third_change"] is True
