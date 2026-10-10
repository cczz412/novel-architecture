# 执行身份：Codex
"""C 的默认选择和检查点隔离；零请求。"""
import pytest
from pipeline_common import c_viewpoint


def test_default_and_all_c_modes_have_distinct_checkpoints(monkeypatch):
    monkeypatch.delenv('PIPELINE_C_VIEWPOINT_MODE', raising=False)
    assert c_viewpoint.settings() == {'mode': 'legacy', 'version': 1}
    assert c_viewpoint.checkpoint_identity() == {}
    identities = []
    for mode in ('legacy', 'evidence', 'evidence_deepseek'):
        monkeypatch.setenv('PIPELINE_C_VIEWPOINT_MODE', mode)
        identity = c_viewpoint.checkpoint_identity()
        for previous in identities:
            with pytest.raises(ValueError, match='不能续用旧检查点'):
                c_viewpoint.require_checkpoint(previous, identity)
            with pytest.raises(ValueError, match='不能续用旧检查点'):
                c_viewpoint.require_checkpoint(identity, previous)
        c_viewpoint.require_checkpoint(identity, identity)
        identities.append(identity)


@pytest.mark.parametrize('value', ['', 'invalid', 'LEGACY'])
def test_invalid_c_mode_is_rejected(monkeypatch, value):
    monkeypatch.setenv('PIPELINE_C_VIEWPOINT_MODE', value)
    with pytest.raises(ValueError, match='PIPELINE_C_VIEWPOINT_MODE'):
        c_viewpoint.settings()
