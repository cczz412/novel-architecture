from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_deepseek_official_v4_pro_provider_is_isolated_and_secret_free() -> None:
    path = ROOT / "config/providers/deepseek_official_v4_pro.json"
    raw = path.read_text(encoding="utf-8")
    provider = json.loads(raw)

    assert provider["provider"] == "deepseek_official"
    assert provider["enabled_by_default"] is False
    assert provider["base_url"] == "https://api.deepseek.com"
    assert provider["endpoint"] == "/chat/completions"
    assert provider["allowed_models"] == ["deepseek-v4-pro"]
    assert provider["model"] == "deepseek-v4-pro"
    assert provider["api_key_env"] == "DEEPSEEK_API_KEY"
    assert provider["thinking"] == {"type": "enabled"}
    assert provider["reasoning_effort"] == "high"
    assert "temperature" not in provider
    assert provider["activation_policy_ref"] == (
        "config/providers/provider_access_policy.json#deepseek_official"
    )
    policy = json.loads(
        (ROOT / "config/providers/provider_access_policy.json").read_text(
            encoding="utf-8"
        )
    )["providers"]["deepseek_official"]
    assert policy["default_action"] == "deny"
    assert policy["standing_authorized"] is True
    assert policy["approval_scope"] == "standing_until_explicit_revocation"
    assert policy["per_run_user_confirmation_required"] is False
    assert policy["automatic_fallback_allowed"] is False
    assert policy["may_replace_default_chain"] is False
    assert "sk-" not in raw.lower()


def test_deepseek_official_keychain_tools_share_one_identity() -> None:
    shell = (ROOT / "tools/deepseek_official_key.sh").read_text(encoding="utf-8")
    swift = (ROOT / "tools/deepseek_official_key_save.swift").read_text(encoding="utf-8")

    service = "cn.cz.novel-architecture.deepseek.official.v4-pro"
    account = "DEEPSEEK_API_KEY"
    assert service in shell and service in swift
    assert account in shell and account in swift
    assert "SENSENOVA_API_KEY" not in shell
    assert "SENSENOVA_API_KEY" not in swift
    assert "unset CZ_DEEPSEEK_OFFICIAL_API_APPROVAL" not in shell


def test_deepseek_official_key_loader_help_is_zero_call() -> None:
    result = subprocess.run(
        [str(ROOT / "tools/deepseek_official_key.sh"), "help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "DeepSeek 官方 V4 Pro" in result.stdout
    assert "DEEPSEEK_API_KEY" in result.stdout
    assert "长期授权" in result.stdout


def test_deepseek_official_loader_denies_run_without_machine_execution_ack() -> None:
    environment = os.environ.copy()
    environment.pop("CZ_DEEPSEEK_OFFICIAL_API_APPROVAL", None)
    result = subprocess.run(
        [str(ROOT / "tools/deepseek_official_key.sh"), "run", "/usr/bin/true"],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 77
    assert "缺少机器执行票" in result.stderr
    assert "长期授权" in result.stderr
