# 执行身份：Codex
"""Experimental C viewpoint evidence; legacy is the default, no transport here."""
import copy
import json
import os
import re

EXECUTION_IDENTITY = 'Codex'
CONTEXT_KEY = '_c_viewpoint_context'
METHOD = 'text_c_viewpoint_evidence_v123'


def settings():
    mode = os.environ.get('PIPELINE_C_VIEWPOINT_MODE', 'legacy')
    if mode not in ('legacy', 'evidence'):
        raise ValueError('PIPELINE_C_VIEWPOINT_MODE 只能是 legacy 或 evidence')
    return {'mode': mode, 'version': 1}


def checkpoint_identity():
    config = settings()
    return {} if config['mode'] == 'legacy' else {'c_viewpoint_settings': config}


def require_checkpoint(previous, current):
    if previous != current:
        raise ValueError('C 视角方法改变，不能续用旧检查点')
