# 执行身份：Codex
"""只执行摘要写入语句；不会执行生产入口、预算、网关。"""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from pipeline_common.c_viewpoint import settings


@pytest.mark.parametrize('mode', [None, 'legacy', 'evidence', 'evidence_deepseek'])
def test_run_receipt_reports_text_and_selected_c_mode(monkeypatch, mode):
    monkeypatch.delenv('PIPELINE_C_VIEWPOINT_MODE', raising=False)
    if mode is not None:
        monkeypatch.setenv('PIPELINE_C_VIEWPOINT_MODE', mode)
    path = Path(__file__).resolve().parents[1] / 'tools/run_pipeline.py'
    tree = ast.parse(path.read_text())
    execute = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
    # 当前入口最早写入的运行摘要；历史不可达分支不执行。
    statement = next(n for n in execute.body if isinstance(n, ast.Expr)
                     and isinstance(n.value, ast.Call)
                     and isinstance(n.value.func, ast.Name) and n.value.func.id == 'write_json'
                     and any(isinstance(c, ast.Constant) and c.value == 'run_status.json'
                             for c in ast.walk(n)))
    writes = []
    namespace = {'write_json': lambda p, data: writes.append((p, data)),
                 'output': Path('fictional'), 'result': {'complete': True, 'method': 'fictional'},
                 'budget': SimpleNamespace(spent=lambda: (0, 0)), 'c_viewpoint_settings': settings}
    exec(compile(ast.Module(body=[statement], type_ignores=[]), '<receipt only>', 'exec'), namespace)
    assert writes == [(Path('fictional/run_status.json'), {
        'complete': True, 'method': 'fictional', 'requests': 0, 'charged_tokens': 0,
        'C_mode': 'text', 'C_viewpoint_mode': mode or 'legacy', 'eligible_for_blind': False})]
