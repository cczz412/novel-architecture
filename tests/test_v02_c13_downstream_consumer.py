from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C13_downstream_consumer_program_20260725"
)
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

import v02_c13_downstream_consumer as c13  # noqa: E402


pytestmark = pytest.mark.v02


def _decoded_artifacts() -> dict[str, Any]:
    return {
        name: (
            json.loads(raw.decode("utf-8"))
            if name.endswith(".json")
            else raw.decode("utf-8")
        )
        for name, raw in c13.build_artifacts().items()
    }


def _request_messages(artifacts: dict[str, Any]) -> list[tuple[str, list[dict[str, str]]]]:
    return [
        (name, payload["messages"])
        for name, payload in sorted(artifacts.items())
        if name.startswith("requests/") and name.endswith(".json")
    ]


def _send_surfaces(artifacts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        name: payload
        for name, payload in sorted(artifacts.items())
        if name.startswith("send_surfaces/") and name.endswith(".json")
    }


def _valid_common(material_id: str, task: str) -> dict[str, Any]:
    return {
        "material_id": material_id,
        "external_knowledge_used": False,
        "task": task,
    }


def _insufficient_answers() -> list[dict[str, Any]]:
    return [
        {
            "question_family": family,
            "status": "MATERIAL_INSUFFICIENT",
            "answer": "",
            "supporting_fact_ids": [],
            "missing_bucket": "FACT_NOT_EXTRACTED",
            "missing_reason": "材料没有提供足够事实。",
        }
        for family in c13.QUESTION_FAMILIES
    ]


def test_call_plan_is_exactly_18_normal_plus_two_six_call_floors() -> None:
    built = _decoded_artifacts()
    plan = built["plans/call_plan.json"]
    nodes = plan["nodes"]

    assert plan["planned_call_total"] == 30
    assert plan["normal_task_calls"] == 18
    assert plan["shuffled_floor_calls"] == 6
    assert plan["blank_floor_calls"] == 6
    assert len(nodes) == 30
    assert Counter(row["task"] for row in nodes) == {
        "A": 10,
        "B": 10,
        "C": 10,
    }
    assert Counter(
        row["floor_kind"] for row in nodes if row["floor_kind"] is not None
    ) == {
        "SHUFFLED_FACT_ORDER": 6,
        "CHAPTER_NUMBER_ONLY": 6,
    }
    assert plan["floor_task_distribution"] == {
        "SHUFFLED_FACT_ORDER": {"A": 2, "B": 2, "C": 2},
        "CHAPTER_NUMBER_ONLY": {"A": 2, "B": 2, "C": 2},
    }
    assert plan["floor_uses_same_task_and_output_contract_as_normal"] is True
    assert len({row["call_id"] for row in nodes}) == 30
    assert len({row["source_request_sha256"] for row in nodes}) == 30
    assert len({row["send_surface_sha256"] for row in nodes}) == 30


def test_every_node_is_a_clean_two_message_conversation() -> None:
    built = _decoded_artifacts()
    plan = built["plans/call_plan.json"]
    requests = dict(_request_messages(built))

    assert plan["each_call_has_isolated_conversation"] is True
    assert all(row["conversation_isolated"] is True for row in plan["nodes"])
    for row in plan["nodes"]:
        messages = requests[row["source_request_path"]]
        assert [message["role"] for message in messages] == ["system", "user"]
        assert all(set(message) == {"role", "content"} for message in messages)
        user_payload = json.loads(messages[1]["content"])
        assert set(user_payload) == {
            "task_instruction",
            "output_contract",
            "material",
        }
        assert user_payload["material"]["material_id"]


def test_actual_send_surface_is_messages_only_and_matches_reviewed_sha() -> None:
    built = _decoded_artifacts()
    plan = built["plans/call_plan.json"]
    dispatch = built["plans/provider_dispatch_plan.json"]
    send_surfaces = _send_surfaces(built)

    assert len(send_surfaces) == 30
    assert dispatch["actual_send_surface"] == "MESSAGES_ONLY"
    assert dispatch["private_request_wrapper_may_be_sent"] is False
    by_call = {row["call_id"]: row for row in plan["nodes"]}
    for call_id, row in by_call.items():
        send_path = row["send_surface_path"]
        payload = send_surfaces[send_path]
        assert set(payload) == {"messages"}
        assert row["send_surface"] == "MESSAGES_ONLY"
        assert row["send_surface_sha256"] == c13.sha256_bytes(
            c13.canonical_bytes(payload)
        )
        assert row["messages_sha256"] == c13.sha256_bytes(
            c13.canonical_bytes(payload["messages"])
        )
    for row in dispatch["dispatch_nodes"]:
        base = by_call[row["base_call_id"]]
        assert row["send_surface"] == "MESSAGES_ONLY"
        assert row["send_surface_path"] == base["send_surface_path"]
        assert row["send_surface_sha256"] == base["send_surface_sha256"]
        assert "request_path" not in row


def test_private_request_wrapper_shape_is_uniform_but_never_sendable() -> None:
    built = _decoded_artifacts()
    requests = [
        payload
        for name, payload in built.items()
        if name.startswith("requests/") and name.endswith(".json")
    ]
    assert len(requests) == 30
    assert {
        tuple(sorted(payload))
        for payload in requests
    } == {
        (
            "call_id",
            "floor_kind",
            "messages",
            "schema_version",
            "task",
        )
    }


def test_model_visible_surface_has_no_identity_route_provider_or_gold_leak() -> None:
    built = _decoded_artifacts()
    forbidden = (
        "/Users/",
        "runs/",
        "reports/",
        "大王饶命",
        "神秘复苏",
        "知否",
        "作者",
        "B01-U0033",
        "B02-U0039",
        "B03-U0041",
        "实验臂",
        "对照臂",
        "treatment",
        "control",
        "sensenova",
        "deepseek",
        "qwen",
        "doubao",
        "豆包",
        "minimax",
        "ling",
        "provider",
        "gold",
        "金标",
        "v02",
        "c13",
        "上游",
        "隔断",
        "评测",
        "实验",
        "provisional_ai_downstream",
    )
    for name, messages in _request_messages(built):
        visible = json.dumps(messages, ensure_ascii=False).lower()
        assert not c13.visible_leak_hits(messages), name
        for marker in forbidden:
            assert marker.lower() not in visible, (name, marker)


def test_floor_calls_do_not_tell_receiver_that_they_are_floor_controls() -> None:
    built = _decoded_artifacts()
    plan = built["plans/call_plan.json"]
    requests = dict(_request_messages(built))
    forbidden_control_hints = (
        "floor",
        "地板",
        "shuffled",
        "打乱",
        "blank",
        "空白组",
        "对照组",
        "control",
    )

    for row in plan["nodes"]:
        if row["floor_kind"] is None:
            continue
        visible = json.dumps(
            requests[row["source_request_path"]],
            ensure_ascii=False,
        ).lower()
        for hint in forbidden_control_hints:
            assert hint.lower() not in visible, (row["call_id"], hint)


def test_single_chapter_inputs_are_labeled_and_never_aggregated_as_long_term() -> None:
    built = _decoded_artifacts()
    private_map = built[
        "private_not_model_visible/material_identity_map.json"
    ]
    assert len(private_map["rows"]) == 6
    assert all(
        row["coverage_scope"] == "SINGLE_CHAPTER_ONLY"
        and row["cumulative_chapter_count"] == 1
        and row["facts_through_chapter_available"] is False
        and row["short_term_usefulness_only"] is True
        for row in private_map["rows"]
    )

    preflight = built["preflight/preflight_receipt.json"]
    assert preflight["input_scope_blocking"] is False
    assert preflight["execute_allowed"] is False

    scope = built["preflight/input_scope_receipt.json"]
    assert scope["facts_through_chapter_preferred"] is True
    assert scope["facts_through_chapter_available"] is False
    assert scope["coverage_scope"] == "SINGLE_CHAPTER_ONLY"
    assert scope["cumulative_chapter_count_per_material"] == 1
    assert scope["status"] == "PASS_SINGLE_CHAPTER_SHORT_TERM_ONLY"
    assert scope["short_term_usefulness_only"] is True
    assert scope["multi_chapter_and_single_chapter_may_be_aggregated"] is False


def test_incomplete_four_views_explicitly_say_not_provided_and_never_guess() -> None:
    views = c13.build_mechanical_views(
        [
            {
                "fact_id": "F001",
                "fact": "因为他担心计划尚未完成，所以决定离开。",
            }
        ]
    )
    assert views["timeline"] == {
        "status": "PROVIDED_MECHANICAL",
        "items": [{"seq": 1, "fact_id": "F001"}],
    }
    for slot in ("causal_edges", "character_states", "unresolved_items"):
        assert views[slot] == {"status": "NOT_PROVIDED", "items": []}
        assert views[slot]["status"]


def test_scope_fields_are_authorized_and_material_schema_is_neutral() -> None:
    built = _decoded_artifacts()
    contract = built["contracts/isolation_contract.json"]
    assert "COVERAGE_SCOPE" in contract["allowed_visible_surfaces"]
    assert "CUMULATIVE_CHAPTER_COUNT" in contract["allowed_visible_surfaces"]
    for _, messages in _request_messages(built):
        material = json.loads(messages[1]["content"])["material"]
        assert material["schema_version"] == "chapter-fact-material.v1"
        assert material["coverage_scope"] == "SINGLE_CHAPTER_ONLY"
        assert material["cumulative_chapter_count"] == 1


def test_floor_derivations_have_private_base_material_provenance() -> None:
    built = _decoded_artifacts()
    plan = built["plans/call_plan.json"]
    provenance = built[
        "private_not_model_visible/floor_derivation_map.json"
    ]
    floor_nodes = [row for row in plan["nodes"] if row["floor_kind"]]
    assert len(floor_nodes) == 12
    assert provenance["model_visible"] is False
    assert len(provenance["rows"]) == 12
    expected = {
        (
            row["call_id"],
            row["material_id"],
            row["base_material_id"],
            row["floor_kind"],
        )
        for row in floor_nodes
    }
    actual = {
        (
            row["call_id"],
            row["derived_material_id"],
            row["base_material_id"],
            row["floor_kind"],
        )
        for row in provenance["rows"]
    }
    assert actual == expected


def test_nine_missing_buckets_keep_authoritative_chinese_names() -> None:
    expected = {
        "ATTRIBUTION_MISSING": (
            "归属层缺失",
            "Notion §9.1-E.4 bucket 1",
        ),
        "REALIS_MODALITY_POLARITY_MISSING": (
            "否定／情态／未然未分离",
            "Notion §9.1-E.4 bucket 2",
        ),
        "COREFERENCE_UNRESOLVED": (
            "指代未消解",
            "Notion §9.1-E.4 bucket 3",
        ),
        "SUBJECT_PREDICATE_OBJECT_MISSING": (
            "主谓宾未成格",
            "Notion §9.1-E.4 bucket 4",
        ),
        "STATE_SLOT_MISSING": (
            "状态槽缺失／不可续接",
            "Notion §9.1-E.4 bucket 5",
        ),
        "TIME_CHAPTER_ORDER_MISSING": (
            "时间／章序信息缺失",
            "Notion §9.1-E.4 bucket 6",
        ),
        "FACT_NOT_EXTRACTED": (
            "根本没抽到",
            "Notion §9.1-E.4 bucket 7",
        ),
        "SCENE_VISUAL_MISSING": (
            "画面／场景信息缺失",
            "Notion C11.2 bucket 8",
        ),
        "EMOTION_INTENSITY_MISSING": (
            "情绪／强度信息缺失",
            "Notion C11.2 bucket 9",
        ),
    }
    assert tuple(c13.MISSING_BUCKET_AUTHORITY) == c13.MISSING_BUCKETS
    assert {
        key: (row["display_name"], row["authority"])
        for key, row in c13.MISSING_BUCKET_AUTHORITY.items()
    } == expected


def test_task_a_rejects_unknown_fields_and_dangling_fact_ids() -> None:
    payload = {
        **_valid_common("M01", "A"),
        "outline_beats": [
            {
                "beat_id": "B1",
                "proposal": "延续现有行动。",
                "basis_fact_ids": ["F001"],
            }
        ],
        "gaps": [],
    }
    assert c13.validate_task_a(
        payload,
        expected_material_id="M01",
        allowed_fact_ids={"F001"},
    ) == payload
    annotated = c13.annotate_provisional_output(payload)
    assert annotated["_internal_classification"] == "PROVISIONAL_AI_DOWNSTREAM"
    assert "_internal_classification" not in payload

    unknown_field = copy.deepcopy(payload)
    unknown_field["unexpected"] = True
    with pytest.raises(c13.C13Error, match="字段不闭合"):
        c13.validate_task_a(
            unknown_field,
            expected_material_id="M01",
            allowed_fact_ids={"F001"},
        )

    dangling = copy.deepcopy(payload)
    dangling["outline_beats"][0]["basis_fact_ids"] = ["F999"]
    with pytest.raises(c13.C13Error, match="未知 fact_id"):
        c13.validate_task_a(
            dangling,
            expected_material_id="M01",
            allowed_fact_ids={"F001"},
        )


def test_task_b_rejects_fake_answer_and_dangling_support() -> None:
    payload = {
        **_valid_common("M01", "B"),
        "answers": _insufficient_answers(),
    }
    assert c13.validate_task_b(
        payload,
        expected_material_id="M01",
        allowed_fact_ids={"F001"},
    ) == payload

    fake_answer = copy.deepcopy(payload)
    fake_answer["answers"][0]["answer"] = "模型擅自补出的答案"
    with pytest.raises(c13.C13Error, match="不得伪造答案"):
        c13.validate_task_b(
            fake_answer,
            expected_material_id="M01",
            allowed_fact_ids={"F001"},
        )

    dangling = copy.deepcopy(payload)
    dangling["answers"][0].update(
        {
            "status": "ANSWERED",
            "answer": "有答案",
            "supporting_fact_ids": ["F999"],
            "missing_bucket": None,
            "missing_reason": "",
        }
    )
    with pytest.raises(c13.C13Error, match="未知 fact_id"):
        c13.validate_task_b(
            dangling,
            expected_material_id="M01",
            allowed_fact_ids={"F001"},
        )


def test_task_c_rejects_unknown_fields_dangling_ids_and_missing_rating() -> None:
    payload = {
        **_valid_common("M01", "C"),
        "ratings": [
            {"fact_id": "F001", "label": "USABLE", "reason": "主体清楚。"},
            {
                "fact_id": "F002",
                "label": "AMBIGUOUS",
                "reason": "时间不清。",
            },
        ],
    }
    assert c13.validate_task_c(
        payload,
        expected_material_id="M01",
        allowed_fact_ids={"F001", "F002"},
    ) == payload

    missing = copy.deepcopy(payload)
    missing["ratings"].pop()
    with pytest.raises(c13.C13Error, match="没有逐条"):
        c13.validate_task_c(
            missing,
            expected_material_id="M01",
            allowed_fact_ids={"F001", "F002"},
        )

    dangling = copy.deepcopy(payload)
    dangling["ratings"][1]["fact_id"] = "F999"
    with pytest.raises(c13.C13Error, match="缺失、重复或未知"):
        c13.validate_task_c(
            dangling,
            expected_material_id="M01",
            allowed_fact_ids={"F001", "F002"},
        )

    unknown_field = copy.deepcopy(payload)
    unknown_field["ratings"][0]["confidence"] = 1
    with pytest.raises(c13.C13Error, match="字段不闭合"):
        c13.validate_task_c(
            unknown_field,
            expected_material_id="M01",
            allowed_fact_ids={"F001", "F002"},
        )


def test_prompt_review_gate_keeps_transport_completely_untouched() -> None:
    built = _decoded_artifacts()
    hard_stop = built["preflight/prompt_review_gate.json"]
    scope = built["preflight/input_scope_receipt.json"]
    preflight = built["preflight/preflight_receipt.json"]
    manifest = built["artifact_manifest.json"]

    assert hard_stop["blocking"] is True
    codes = {row["code"] for row in hard_stop["blocking_reasons"]}
    assert codes == {
        "NOTION_EXACT_PROMPT_LEAK_REVIEW_PENDING",
        "THREE_PROVIDER_WIRE_ADAPTERS_PENDING",
        "FLOOR_PASS_CRITERION_PENDING",
    }
    assert preflight["provider_selection_blocking"] is False
    assert preflight["provider_transport_adapter_blocking"] is True
    assert preflight["floor_pass_criterion_blocking"] is True
    assert preflight["input_scope_blocking"] is False
    assert preflight["prompt_leak_review_blocking"] is True
    assert preflight["execute_allowed"] is False
    for receipt in (hard_stop, preflight, manifest):
        assert receipt["model_api_calls"] == 0
        assert receipt["network_requests"] == 0
    assert hard_stop["key_value_read"] is False
    assert scope["execute_allowed_after_all_other_gates"] is True
    assert {
        "FLOOR_PASS_CRITERION_FROZEN",
        "THREE_PROVIDER_WIRE_ADAPTERS_ZERO_CALL_RENDER_PASSED",
    }.issubset(hard_stop["resume_requirements"])


def test_three_provider_plan_is_30_each_90_total_and_qwen_is_primary() -> None:
    built = _decoded_artifacts()
    plan = built["plans/provider_dispatch_plan.json"]
    rows = plan["dispatch_nodes"]

    assert len(rows) == 90
    assert Counter(row["provider_id"] for row in rows) == {
        "qianwen_platform": 30,
        "volcengine_ark": 30,
        "tencent_tokenhub": 30,
    }
    assert plan["primary_readout_provider"] == "qianwen_platform"
    assert plan["primary_readout_model"] == "qwen3.7-max-2026-05-20"
    assert plan["provider_scores_may_be_averaged_or_weighted"] is False
    assert plan["provider_scores_may_be_merged"] is False
    assert plan["qwen_floor_failure_allows_replication_to_replace_primary"] is False
    assert plan["top3_missing_bucket_ranking_consistency_required"] is True
    for provider_id in (
        "qianwen_platform",
        "volcengine_ark",
        "tencent_tokenhub",
    ):
        provider_rows = [
            row for row in rows if row["provider_id"] == provider_id
        ]
        assert Counter(row["floor_kind"] for row in provider_rows) == {
            None: 18,
            "SHUFFLED_FACT_ORDER": 6,
            "CHAPTER_NUMBER_ONLY": 6,
        }


def test_same_slot_visible_messages_sha_is_identical_across_all_providers() -> None:
    built = _decoded_artifacts()
    plan = built["plans/provider_dispatch_plan.json"]
    by_slot: dict[str, set[str]] = {}
    for row in plan["dispatch_nodes"]:
        by_slot.setdefault(row["base_call_id"], set()).add(
            row["messages_sha256"]
        )
    assert len(by_slot) == 30
    assert all(len(values) == 1 for values in by_slot.values())


def test_provider_models_are_exact_and_never_visible_in_prompts() -> None:
    built = _decoded_artifacts()
    plan = built["plans/provider_dispatch_plan.json"]
    profiles = {
        row["provider_id"]: row for row in plan["provider_profiles"]
    }
    assert {
        provider: row["model_id"] for provider, row in profiles.items()
    } == {
        "qianwen_platform": "qwen3.7-max-2026-05-20",
        "volcengine_ark": "doubao-seed-2-1-pro-260628",
        "tencent_tokenhub": "minimax-m3",
    }
    assert all(row["automatic_fallback_allowed"] is False for row in profiles.values())
    assert all(
        row["live_catalog_or_identity_gate_passed"] is False
        for row in profiles.values()
    )
    assert all(
        row["wire_adapter_status"]
        == "BLOCKED_PENDING_ZERO_CALL_RENDER_AND_FIELD_EVIDENCE"
        and row["wire_adapter_zero_call_render_passed"] is False
        and "request_parameters" not in row
        for row in profiles.values()
    )
    visible = json.dumps(_request_messages(built), ensure_ascii=False).lower()
    for row in profiles.values():
        assert row["provider_id"].lower() not in visible
        assert row["model_id"].lower() not in visible


def test_prompt_review_bundle_contains_exact_30_messages_and_is_not_approved() -> None:
    built = _decoded_artifacts()
    bundle = built["prompt_review/exact_visible_messages.json"]
    requests = {
        name.removeprefix("requests/").removesuffix(".json"): messages
        for name, messages in _request_messages(built)
    }
    assert bundle["status"] == "PENDING_NOTION_LEAK_REVIEW"
    assert bundle["slot_total"] == 30
    assert bundle["approved_to_send"] is False
    assert len(bundle["rows"]) == 30
    for row in bundle["rows"]:
        assert row["messages"] == requests[row["call_id"]]
        assert row["messages_sha256"] == c13.sha256_bytes(
            c13.canonical_bytes(row["messages"])
        )


def test_visible_material_ids_are_uniform_and_do_not_reveal_floor_kind() -> None:
    built = _decoded_artifacts()
    plan = built["plans/call_plan.json"]
    material_ids = [row["material_id"] for row in plan["nodes"]]
    assert all(
        len(material_id) == 11
        and material_id.startswith("D")
        and material_id[1:].isalnum()
        for material_id in material_ids
    )
    assert not any(material_id.startswith(("M", "V")) for material_id in material_ids)


def test_receiver_has_no_tools_network_parent_context_or_floor_identity() -> None:
    built = _decoded_artifacts()
    contract = built["contracts/isolation_contract.json"]
    assert contract["tools_or_network_available_to_receiver"] is False
    assert contract["parent_conversation_inherited"] is False
    assert contract["provider_or_model_visible_to_receiver"] is False
    assert contract["floor_identity_visible_to_receiver"] is False
    assert contract["self_judge"] is False
    assert contract["same_family_judge"] is False
    assert contract["executor_self_assess"] is False
