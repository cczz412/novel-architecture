from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_provider(name: str) -> dict:
    return json.loads((ROOT / "config/providers" / name).read_text(encoding="utf-8"))


def test_provider_policy_keeps_official_deepseek_default_denied() -> None:
    policy = load_provider("provider_access_policy.json")
    official = policy["providers"]["deepseek_official"]
    assert policy["default_chain_provider"] == "sensenova"
    assert policy["default_chain_changed"] is False
    assert official["default_action"] == "deny"
    assert official["approval_scope"] == "current_task_one_command_only"
    assert official["loader_ack_exact_value"] == "USE_OFFICIAL_DEEPSEEK_API_ONCE"


def test_volcengine_ark_channel_and_requested_models_are_exact() -> None:
    provider = load_provider("volcengine_ark_multi_model.json")
    assert provider["base_url"] == "https://ark.cn-beijing.volces.com/api/v3"
    assert provider["endpoint"] == "/chat/completions"
    assert provider["api_key_env"] == "ARK_API_KEY"
    assert provider["enabled_by_default"] is False
    models = {row["requested_name"]: row for row in provider["models"]}
    assert models["GLM-5.2"]["model_id"] == "glm-5-2-260617"
    assert models["Doubao-Seed-Evolving"]["model_id"] == "doubao-seed-evolving"
    assert models["Doubao-Seed-2.1-turbo"]["model_id"] == "doubao-seed-2-1-turbo-260628"
    assert models["Doubao-Seed-2.1-pro"]["model_id"] == "doubao-seed-2-1-pro-260628"
    assert models["DeepSeek-V4-pro"]["model_id"] == "deepseek-v4-pro-260425"
    assert models["DeepSeek-V4-flash"]["model_id"] == "deepseek-v4-flash-260425"
    assert models["Kimi-K2"]["model_id"] is None
    assert models["Kimi-K2"]["call_ready"] is False


def test_volcengine_agent_plan_forbids_auto_and_requires_exact_models() -> None:
    provider = load_provider("volcengine_agent_plan.json")
    assert provider["base_url"] == "https://ark.cn-beijing.volces.com/api/plan/v3"
    assert provider["api_key_env"] == "VOLCENGINE_AGENT_PLAN_API_KEY"
    assert provider["arkcli_profile"] == "agent-plan_cn-beijing_personal"
    assert provider["enabled_by_default"] is False
    assert provider["default_model"] is None
    assert provider["auto_model_allowed"] is False
    assert provider["exact_model_id_required"] is True
    assert provider["request_response_model_binding_required"] is True
    model_ids = {row["model_id"] for row in provider["models"]}
    assert "auto" not in model_ids
    assert "deepseek-v4-pro-260425" in model_ids
    assert "deepseek-v4-flash-260425" in model_ids
    assert "doubao-seed-2-1-turbo-260628" in model_ids
    models = {row["model_id"]: row for row in provider["models"]}
    flash = models["deepseek-v4-flash-260425"]
    assert flash["call_ready"] is False
    assert flash["status"] == "blocked_prefer_sensenova_free_quota"
    assert all(
        row["call_ready"]
        for model_id, row in models.items()
        if model_id != "deepseek-v4-flash-260425"
    )

    policy = load_provider("provider_access_policy.json")
    agent_plan = policy["providers"]["volcengine_agent_plan"]
    assert agent_plan["may_replace_default_chain"] is False
    assert agent_plan["require_live_model_catalog_check"] is True
    assert agent_plan["exact_model_id_required"] is True
    assert agent_plan["auto_model_forbidden"] is True
    flash_route = agent_plan["model_route_overrides"]["deepseek-v4-flash-260425"]
    assert flash_route["default_action"] == "deny"
    assert flash_route["preferred_provider"] == "sensenova"


def test_qianwen_channel_and_requested_models_are_exact() -> None:
    provider = load_provider("qianwen_platform_multi_model.json")
    assert provider["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert provider["endpoint"] == "/chat/completions"
    assert provider["api_key_env"] == "DASHSCOPE_API_KEY"
    assert provider["enabled_by_default"] is False
    assert provider["token_plan_key_supported_by_this_config"] is False
    assert [row["model_id"] for row in provider["models"]] == [
        "qwen3.7-plus",
        "qwen3.7-max",
        "qwen3.7-max-2026-05-20",
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "glm-5.2",
        "kimi-k2.7-code",
    ]
    assert all(row["call_ready"] for row in provider["models"])
    fixed_max = next(
        row
        for row in provider["models"]
        if row["model_id"] == "qwen3.7-max-2026-05-20"
    )
    assert fixed_max["fixed_snapshot"] is True
    assert fixed_max["structured_output"] is False
    assert fixed_max["live_catalog_check_required_before_run"] is True


def test_tencent_tokenhub_channel_and_requested_models_are_exact() -> None:
    provider = load_provider("tencent_tokenhub_multi_model.json")
    assert provider["base_url"] == "https://tokenhub.tencentmaas.com/v1"
    assert provider["endpoint"] == "/chat/completions"
    assert provider["model_catalog_endpoint"] == "/models"
    assert provider["model_catalog_check_required_before_run"] is True
    assert provider["api_key_env"] == "TENCENT_TOKENHUB_API_KEY"
    assert provider["enabled_by_default"] is False
    assert provider["default_model"] is None
    assert [row["model_id"] for row in provider["models"]] == [
        "hy3",
        "hy-role",
        "deepseek-v4-flash-202605",
        "deepseek-v4-pro-202606",
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "glm-5.2",
        "glm-5.1",
        "kimi-k2.7-code-highspeed",
        "kimi-k3",
        "kimi-k2.7-code",
        "kimi-k2.6",
        "minimax-m3",
        "minimax-m2.7",
    ]
    models = {row["model_id"]: row for row in provider["models"]}
    assert "structured_output" not in models["hy-role"]["capabilities"]
    assert "structured_output" not in models["minimax-m3"]["capabilities"]
    assert "structured_output" not in models["minimax-m2.7"]["capabilities"]


def test_longcat_channel_uses_external_key_pool_and_exact_model() -> None:
    provider = load_provider("longcat_platform.json")
    assert provider["base_url"] == "https://api.longcat.chat/openai/v1"
    assert provider["endpoint"] == "/chat/completions"
    assert provider["model_catalog_endpoint"] == "/models"
    assert provider["model_catalog_check_required_before_run"] is True
    assert provider["model_catalog_status_policy"] == "presence_only"
    assert provider["api_key_env"] == "LONGCAT_API_KEY"
    assert provider["enabled_by_default"] is False
    assert provider["default_model"] is None
    assert provider["status"] == "configured_catalog_verified_benchmark_transport_hard_stopped"
    structured = provider["structured_output_contract"]
    assert structured["status"] == "not_documented_by_provider"
    assert structured["do_not_send"] == [
        "response_format",
        "json_object",
        "json_schema",
    ]
    assert structured["tool_calling_is_not_structured_output"] is True
    assert provider["models"] == [
        {
            "requested_name": "LongCat-2.0",
            "model_id": "LongCat-2.0",
            "call_ready": True,
            "capabilities": ["thinking", "function_calling"],
            "context_tokens": 1048576,
            "max_output_tokens": 131072,
        }
    ]
    loader = Path(provider["external_key_loader"])
    assert loader == Path(
        "/Users/a1234/挣钱/danmaku-psychology-workspace/06_operations/api-pool/"
        "scripts/longcat-env.zsh"
    )
    assert loader.is_file()


def test_ant_ling_channel_uses_exact_ling_3_flash_contract() -> None:
    provider = load_provider("ant_ling.json")
    assert provider["provider"] == "ant_ling"
    assert provider["base_url"] == "https://api.ant-ling.com/v1"
    assert provider["endpoint"] == "/chat/completions"
    assert provider["api_key_env"] == "ANT_LING_API_KEY"
    assert provider["enabled_by_default"] is False
    assert provider["default_model"] is None
    assert provider["models"] == [
        {
            "requested_name": "Ling 3.0 Flash",
            "model_id": "Ling-3.0-flash",
            "call_ready": True,
            "capabilities": [
                "thinking",
                "structured_output",
                "function_calling",
            ],
            "context_tokens": 262144,
            "max_expandable_context_tokens": 1048576,
            "max_output_tokens": None,
            "thinking_contract": {
                "field": "thinking.type",
                "default": "enable",
                "allowed_values": ["enable", "disable"],
            },
            "structured_output_contract": {
                "json_object": True,
                "json_schema": True,
            },
            "benchmark_note": (
                "官方未在已读文档中给出最大输出 token 数，因此不臆造上限；"
                "每次正式试验须按当次任务冻结护栏并以供应商响应为准。"
            ),
        }
    ]


def test_tencent_tokenhub_policy_stays_isolated_and_catalog_gated() -> None:
    policy = load_provider("provider_access_policy.json")
    tencent = policy["providers"]["tencent_tokenhub"]
    assert tencent["default_action"] == "deny_until_explicit_model_run_order"
    assert tencent["may_replace_default_chain"] is False
    assert tencent["require_live_model_catalog_check"] is True


def test_longcat_policy_stays_isolated_and_catalog_gated() -> None:
    policy = load_provider("provider_access_policy.json")
    longcat = policy["providers"]["longcat_platform"]
    assert longcat["default_action"] == "deny_until_explicit_model_run_order"
    assert longcat["may_replace_default_chain"] is False
    assert longcat["require_live_model_catalog_check"] is True
    assert longcat["key_source"] == "external_api_pool"


def test_ant_ling_policy_stays_isolated_from_default_chain() -> None:
    policy = load_provider("provider_access_policy.json")
    ant_ling = policy["providers"]["ant_ling"]
    assert policy["default_chain_provider"] == "sensenova"
    assert policy["default_chain_changed"] is False
    assert ant_ling["default_action"] == "deny_until_explicit_model_run_order"
    assert ant_ling["status"] == "isolated_configuration_only"
    assert ant_ling["may_replace_default_chain"] is False
    assert ant_ling["exact_model_id_required"] is True


def test_shared_keychain_loader_is_zero_call_and_names_all_providers() -> None:
    result = subprocess.run(
        [str(ROOT / "tools/provider_keychain.sh"), "help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "volcengine_ark" in result.stdout
    assert "qianwen_platform" in result.stdout
    assert "tencent_tokenhub" in result.stdout
    assert "ant_ling" in result.stdout
    assert "不会试调用模型" in result.stdout

    shell = (ROOT / "tools/provider_keychain.sh").read_text(encoding="utf-8")
    swift = (ROOT / "tools/provider_key_save.swift").read_text(encoding="utf-8")
    for service, account in [
        ("cn.cz.novel-architecture.volcengine.ark", "ARK_API_KEY"),
        (
            "cn.cz.novel-architecture.volcengine.agent-plan",
            "VOLCENGINE_AGENT_PLAN_API_KEY",
        ),
        ("cn.cz.novel-architecture.qianwen.platform", "DASHSCOPE_API_KEY"),
        (
            "cn.cz.novel-architecture.tencent.tokenhub",
            "TENCENT_TOKENHUB_API_KEY",
        ),
        ("cn.cz.novel-architecture.ant-ling.api", "ANT_LING_API_KEY"),
    ]:
        assert service in shell
        assert account in shell
        assert account in swift or "CommandLine.arguments[3]" in swift
    assert 'PROVIDER_ID" == "volcengine_agent_plan"' in shell
    assert 'export ARK_API_KEY="$api_key"' in shell


def test_unknown_provider_is_rejected_before_any_keychain_read() -> None:
    result = subprocess.run(
        [str(ROOT / "tools/provider_keychain.sh"), "check", "unknown_provider"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "不认识的供应商" in result.stderr
