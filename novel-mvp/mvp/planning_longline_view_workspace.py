"""AuthorWorkspace 中 current plan 的稳定长线只读入口。"""

from __future__ import annotations

from typing import Any, NoReturn

from . import plan_workspace, planning_longline_view_tool
from .workspace import AuthorWorkspace, WorkspaceError


class PlanningLonglineViewWorkspaceError(RuntimeError):
    """工作区计划缺失、损坏或在读取期间发生变化。"""


def _fail(code: str, detail: str = "") -> NoReturn:
    raise PlanningLonglineViewWorkspaceError(
        f"{code}:{detail}" if detail else code
    )


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _read_and_validate(workspace: AuthorWorkspace, phase: str) -> dict[str, Any]:
    try:
        entry = plan_workspace.read_plan(workspace)
    except (
        plan_workspace.PlanWorkspaceError,
        plan_workspace.planstore.PlanstoreError,
        WorkspaceError,
    ) as exc:
        _fail("CURRENT_PLAN_READ_REJECTED", f"{phase}:{exc}")
    if entry is None:
        _fail("CURRENT_PLAN_NOT_FOUND", phase)
    try:
        return planning_longline_view_tool.execute(entry)
    except planning_longline_view_tool.PlanningLonglineViewError as exc:
        _fail("CURRENT_PLAN_REJECTED", f"{phase}:{exc}")


def execute(workspace: AuthorWorkspace) -> dict[str, Any]:
    """双读 current plan；水位变化时拒绝返回旧视图，全程零写。"""
    handle = _require_workspace(workspace)
    first = _read_and_validate(handle, "first")
    second = _read_and_validate(handle, "second")
    if (
        first["source_plan_version"] != second["source_plan_version"]
        or first["source_plan_sha256"] != second["source_plan_sha256"]
    ):
        _fail("PLAN_SOURCE_CHANGED_DURING_READ")
    return second
