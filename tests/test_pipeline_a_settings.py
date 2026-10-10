# 执行身份：Codex
"""A path selection and checkpoint compatibility; no model or transport calls."""
import importlib.util
from pathlib import Path

import pytest


def load_settings():
    path = Path(__file__).resolve().parents[1] / "tools/pipeline_common/a_fact_judge.py"
    spec = importlib.util.spec_from_file_location("a_settings_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_fact_judge_and_legacy_fallback(monkeypatch):
    a = load_settings()
    monkeypatch.delenv("PIPELINE_A_MODE", raising=False)
    monkeypatch.delenv("PIPELINE_A_INCLUDE_BRIEF", raising=False)
    # 原作业自测断言：assert a.settings()["mode"] == "legacy"
    # CZ 2026-10-10 16:49 拍板 A 默认切 fact_judge
    assert a.settings() == {"mode": "fact_judge", "include_brief": True}
    monkeypatch.setenv("PIPELINE_A_MODE", "legacy")
    assert a.settings() == {"mode": "legacy", "include_brief": True}


def test_default_and_legacy_cannot_share_checkpoint(monkeypatch):
    a = load_settings()
    monkeypatch.delenv("PIPELINE_A_MODE", raising=False)
    monkeypatch.delenv("PIPELINE_A_INCLUDE_BRIEF", raising=False)
    current = a.checkpoint_identity()
    monkeypatch.setenv("PIPELINE_A_MODE", "legacy")
    legacy = a.checkpoint_identity()
    assert legacy == {}
    assert current == {"a_settings": {"mode": "fact_judge", "include_brief": True}}
    for previous, selected in ((legacy, current), (current, legacy)):
        with pytest.raises(ValueError, match="不能续用旧检查点"):
            a.require_checkpoint(previous, selected)
    a.require_checkpoint(current, current)


@pytest.mark.parametrize("value", ["", "invalid", "FACT_JUDGE"])
def test_invalid_mode_still_rejected(monkeypatch, value):
    monkeypatch.setenv("PIPELINE_A_MODE", value)
    with pytest.raises(ValueError, match="PIPELINE_A_MODE"):
        load_settings().settings()


def test_all_four_checkpoint_settings_remain_distinct(monkeypatch):
    a = load_settings()
    identities = []
    for mode in ("legacy", "fact_judge"):
        for brief in ("true", "false"):
            monkeypatch.setenv("PIPELINE_A_MODE", mode)
            monkeypatch.setenv("PIPELINE_A_INCLUDE_BRIEF", brief)
            identity = a.checkpoint_identity()
            assert identity not in identities
            identities.append(identity)
