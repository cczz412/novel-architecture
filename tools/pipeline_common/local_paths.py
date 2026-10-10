# 执行身份：Codex
"""Resolve explicitly configured external paths without opening their contents."""
import os
from pathlib import Path


def external_path(variable: str) -> Path:
    value = os.environ.get(variable, '').strip()
    if not value:
        raise ValueError(f'请设置外部路径环境变量 {variable}；真实目录不要写进仓库')
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f'外部路径环境变量 {variable} 必须是绝对路径')
    return Path(os.path.normpath(str(path)))
