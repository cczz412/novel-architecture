# 执行身份：Codex
"""Opt-in A fact judging. Transport and model policy remain with the caller."""
import copy
import hashlib
import json
import os

EXECUTION_IDENTITY = 'Codex'
MAX_BYTES = 8192


def settings():
    mode = os.environ.get('PIPELINE_A_MODE', 'legacy')
    brief = os.environ.get('PIPELINE_A_INCLUDE_BRIEF', 'true')
    if mode not in ('legacy', 'fact_judge'):
        raise ValueError('PIPELINE_A_MODE 只能是 legacy 或 fact_judge')
    if brief not in ('true', 'false'):
        raise ValueError('PIPELINE_A_INCLUDE_BRIEF 只能是 true 或 false')
    return {'mode': mode, 'include_brief': brief == 'true'}


def checkpoint_identity():
    config = settings()
    # Preserve the default legacy identity shape; every nondefault combination differs.
    return {} if config == {'mode': 'legacy', 'include_brief': True} else {'a_settings': config}


def require_checkpoint(previous, current):
    if previous != current:
        raise ValueError('A 路径或计划口径改变，不能续用旧检查点')
