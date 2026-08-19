"""plan-v2 对 AuthorWorkspace 的最小持久化适配器。

本模块只认识已绑定作者与项目的 ``AuthorWorkspace`` 能力句柄。路径、锁、目录、
崩溃恢复和未来云端替换全部仍由 workspace backend 负责。
"""

from __future__ import annotations

import copy
from typing import Any

from . import planstore
from .workspace import AuthorWorkspace


PLAN_LOGICAL_KEY = "plan"


class PlanWorkspaceError(RuntimeError):
    """计划持久化适配器拒绝了非能力句柄或损坏的读取结果。"""


def _require_workspace(workspace: object) -> AuthorWorkspace:
    if not isinstance(workspace, AuthorWorkspace):
        raise PlanWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return workspace


def _validated_plan_copy(plan: Any) -> dict:
    candidate = copy.deepcopy(plan)
    # 只复用 planstore 现役纯对象校验；不调用它的路径、锁或恢复入口。
    planstore._validate_plan(candidate)
    return candidate


def read_plan(workspace: AuthorWorkspace) -> dict | None:
    """读取逻辑键 plan；空项目返回 None，读取本身不创建目录。"""
    handle = _require_workspace(workspace)
    entry = handle.read(PLAN_LOGICAL_KEY)
    if entry is None:
        return None
    plan = _validated_plan_copy(entry.get("payload"))
    return {
        "version": entry["version"],
        "sha256": entry["sha256"],
        "plan": plan,
    }


def save_plan(
    workspace: AuthorWorkspace,
    operation_id: str,
    plan: dict,
    expected_version: int,
) -> dict:
    """校验并原子保存完整 plan-v2；幂等与版本竞争由 workspace 统一裁决。"""
    handle = _require_workspace(workspace)
    candidate = _validated_plan_copy(plan)
    return handle.commit(
        operation_id,
        {PLAN_LOGICAL_KEY: candidate},
        {PLAN_LOGICAL_KEY: expected_version},
    )
