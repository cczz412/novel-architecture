from __future__ import annotations

from tools import model_call_profiles as profiles


def test_all_model_call_profiles_are_mechanically_valid() -> None:
    assert profiles.validate_all_profiles() == []


def test_qwen_thinking_profile_keeps_reasoning_and_avoids_incompatible_json_mode() -> None:
    profile = profiles.load_profile(
        "qianwen_qwen3_7_flash_thinking_prompt_json"
    )
    request = profiles.render_qianwen_request(
        profile,
        [
            {"role": "system", "content": "只返回 JSON 对象。"},
            {"role": "user", "content": "抽取本章事实。"},
        ],
    )
    body = request["body"]
    assert body["model"] == "qwen3.7-flash"
    assert body["temperature"] == 0.2
    assert body["stream"] is True
    assert body["enable_thinking"] is True
    assert body["thinking_budget"] == 32768
    assert body["stream_options"] == {"include_usage": True}
    assert "response_format" not in body
    assert "max_tokens" not in body
    assert "max_completion_tokens" not in body
    assert request["expected_response_model"] == "qwen3.7-flash"


def test_qwen_json_object_profile_closes_thinking_and_omits_output_cap() -> None:
    profile = profiles.load_profile(
        "qianwen_qwen3_7_flash_json_object_no_thinking"
    )
    request = profiles.render_qianwen_request(
        profile,
        [{"role": "user", "content": "请只输出 JSON。"}],
    )
    body = request["body"]
    assert body["enable_thinking"] is False
    assert body["response_format"] == {"type": "json_object"}
    assert body["stream"] is False
    assert "max_tokens" not in body
    assert "thinking_budget" not in body


def test_agent_plan_deepseek_profiles_use_catalog_request_ids_and_high() -> None:
    cases = [
        (
            "agent_plan_deepseek_v4_flash_high_json_object",
            "deepseek-v4-flash-modelhub",
            "deepseek-v4-flash-260425",
        ),
        (
            "agent_plan_deepseek_v4_pro_high_json_object",
            "deepseek-v4-pro-modelhub",
            "deepseek-v4-pro-260425",
        ),
    ]
    for profile_id, request_model, response_model in cases:
        profile = profiles.load_profile(profile_id)
        preview = profiles.render_agent_plan_command(
            profile,
            prompt="抽取本章事实，只返回 JSON。",
        )
        argv = preview["argv"]
        assert argv[:12] == [
            "env",
            "-u",
            "ARK_API_KEY",
            "-u",
            "ARK_BASE_URL",
            "-u",
            "ARK_REGION",
            "-u",
            "ARK_PROFILE",
            "-u",
            "VOLCENGINE_AGENT_PLAN_API_KEY",
            "arkcli",
        ]
        assert argv[argv.index("--model") + 1] == request_model
        assert argv[argv.index("--reasoning-effort") + 1] == "high"
        assert argv[argv.index("--temperature") + 1] == "0.2"
        assert argv[argv.index("--text-format") + 1] == "json_object"
        assert "--max-output-tokens" not in argv
        assert preview["expected_response_model"] == response_model
        assert preview["credential_source"] == "arkcli_profile_managed"
        assert set(preview["unset_environment"]) == {
            "ARK_API_KEY",
            "ARK_BASE_URL",
            "ARK_REGION",
            "ARK_PROFILE",
            "VOLCENGINE_AGENT_PLAN_API_KEY",
        }


def test_agent_plan_minimax_does_not_invent_deepseek_reasoning_effort() -> None:
    profile = profiles.load_profile(
        "agent_plan_minimax_m3_thinking_json_object"
    )
    preview = profiles.render_agent_plan_command(
        profile,
        prompt="抽取本章事实，只返回 JSON。",
    )
    argv = preview["argv"]
    assert argv[0] == "env"
    assert argv[11] == "arkcli"
    assert argv[argv.index("--model") + 1] == "minimax-m3-modelhub"
    assert argv[argv.index("--thinking") + 1] == "enabled"
    assert "--reasoning-effort" not in argv
    assert "--max-output-tokens" not in argv
    assert preview["expected_response_model"] == "minimax-m3"
    assert preview["credential_source"] == "arkcli_profile_managed"
    assert profile["json_output"]["mode"] == (
        "provider_json_object_hint_exact_fence_normalization_local_schema"
    )
    assert profile["json_output"]["normalization_policy"] == {
        "provider_guarantees_raw_json": False,
        "accepted_raw_shapes": [
            "raw_json_object",
            "exact_single_lowercase_json_fence",
        ],
        "allow_prefix_or_suffix_prose": False,
        "raw_receipt_may_be_reclassified": False,
        "normalized_status_name": "normalized_quality_pass",
    }


def test_registry_routes_each_candidate_model_to_one_preferred_profile() -> None:
    registry = profiles.load_registry()
    assert registry["preferred_profiles"] == {
        "qwen3.7-flash": "qianwen_qwen3_7_flash_thinking_prompt_json",
        "deepseek-v4-flash": (
            "agent_plan_deepseek_v4_flash_high_json_object"
        ),
        "deepseek-v4-pro": "agent_plan_deepseek_v4_pro_high_json_object",
        "minimax-m3": "agent_plan_minimax_m3_thinking_json_object",
    }
