"""新版作者项目列表与打开入口。

这个入口只把已认证作者交给 WorkspaceRouter，并只开放 list/open。
它不创建或迁移项目，也不返回正文、物理路径或存储后端。
"""

from __future__ import annotations

import os

from .workspace import AuthorWorkspace, WorkspaceRouter


class AuthorProjectEntry:
    """让作者列出自己的新版项目，并按项目号打开其中一本。"""

    __slots__ = ("__router",)

    def __init__(self, runtime_root: str | os.PathLike[str]):
        self.__router = WorkspaceRouter(runtime_root)

    def list(self, authenticated_principal: str) -> list[dict[str, str]]:
        """只返回项目号、显示名和创建时间。"""
        return self.__router.list_projects(authenticated_principal)

    def open(
        self,
        authenticated_principal: str,
        project_id: str,
    ) -> AuthorWorkspace:
        """返回绑定当前作者与指定项目的 AuthorWorkspace 句柄。"""
        return self.__router.open_project(authenticated_principal, project_id)
