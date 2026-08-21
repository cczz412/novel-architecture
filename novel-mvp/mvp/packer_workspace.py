"""M11 packer 的 AuthorWorkspace recall-handle 预检薄层。"""

from __future__ import annotations

import copy
from typing import Any

from . import packer_tool, recall_handle_workspace
from .workspace import AuthorWorkspace


class PackerWorkspaceError(ValueError):
    """M11 请求含缺失、过期或运行中变化的 recall handle。"""


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        raise PackerWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _retrievable_handles(request: Any) -> list[str]:
    if not isinstance(request, dict):
        raise PackerWorkspaceError("M11_REQUEST_NOT_OBJECT")
    materials = request.get("candidate_materials")
    if not isinstance(materials, list):
        raise PackerWorkspaceError("M11_CANDIDATE_MATERIALS_NOT_LIST")
    handles: list[str] = []
    for index, material in enumerate(materials):
        if not isinstance(material, dict):
            raise PackerWorkspaceError(f"M11_CANDIDATE_NOT_OBJECT:{index}")
        if material.get("recall_disposition") == "RETRIEVABLE":
            handle = material.get("recall_handle")
            if not isinstance(handle, str) or not handle.strip():
                raise PackerWorkspaceError(f"M11_RECALL_HANDLE_MISSING:{index}")
            handles.append(handle)
    return sorted(set(handles))


def _resolve_all(
    workspace: AuthorWorkspace, handles: list[str]
) -> dict[str, dict[str, Any]]:
    resolved: dict[str, dict[str, Any]] = {}
    for handle in handles:
        try:
            resolved[handle] = recall_handle_workspace.resolve_handle(
                workspace, handle
            )
        except recall_handle_workspace.RecallHandleNotFoundError as exc:
            raise PackerWorkspaceError(f"M11_RECALL_HANDLE_NOT_FOUND:{handle}") from exc
        except recall_handle_workspace.RecallHandleStaleError as exc:
            raise PackerWorkspaceError(f"M11_RECALL_HANDLE_STALE:{handle}") from exc
        except recall_handle_workspace.RecallHandleWorkspaceError as exc:
            raise PackerWorkspaceError(f"M11_RECALL_HANDLE_INVALID:{handle}") from exc
    return resolved


def execute(workspace: AuthorWorkspace, request: dict[str, Any]) -> dict[str, Any]:
    """先验 recall handle，再复用现有 packer；结果仍是既有 M11 原型形状。"""
    workspace = _require_workspace(workspace)
    handles = _retrievable_handles(request)
    before = _resolve_all(workspace, handles)
    try:
        result = packer_tool.execute(copy.deepcopy(request))
    except packer_tool.PackerToolError as exc:
        raise PackerWorkspaceError(f"M11_PACKER_REJECTED:{exc}") from exc
    after = _resolve_all(workspace, handles)
    if before != after:
        raise PackerWorkspaceError("M11_RECALL_SOURCE_CHANGED_DURING_PACK")
    return result


def resolve_for_machine(
    workspace: AuthorWorkspace, handle: str
) -> dict[str, Any]:
    """仅供内部预检来源绑定；不返回材料正文。"""
    workspace = _require_workspace(workspace)
    try:
        return recall_handle_workspace.resolve_handle(workspace, handle)
    except recall_handle_workspace.RecallHandleWorkspaceError as exc:
        raise PackerWorkspaceError(f"M11_RECALL_RESOLVE_REJECTED:{exc}") from exc


__all__ = ["PackerWorkspaceError", "execute", "resolve_for_machine"]
