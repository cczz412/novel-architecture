"""AuthorWorkspace 中全部已保存 M9 卡片的稳定只读文档。

本模块只沿用现役清单顺序并拼接现役单卡 Markdown；不重新排序、摘要、
生成、刷新或删除任何概览卡。
"""

from __future__ import annotations

import copy
from typing import Any, NoReturn

from . import overview_card_workspace, overview_reader_workspace
from .workspace import AuthorWorkspace


class OverviewBookWorkspaceError(RuntimeError):
    """已保存卡片不能组成一个水位一致的项目概览文档。"""


def _fail(code: str, detail: str = "") -> NoReturn:
    raise OverviewBookWorkspaceError(f"{code}:{detail}" if detail else code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _list_cards(workspace: AuthorWorkspace) -> dict[str, Any]:
    try:
        inventory = overview_card_workspace.list_overview_cards(workspace)
    except overview_card_workspace.OverviewCardWorkspaceError as exc:
        raise OverviewBookWorkspaceError("BOOK_OVERVIEW_INVENTORY_REJECTED") from exc
    if (
        not isinstance(inventory, dict)
        or set(inventory) != {"watermarks", "cards"}
        or not isinstance(inventory.get("watermarks"), dict)
        or not isinstance(inventory.get("cards"), list)
    ):
        _fail("BOOK_OVERVIEW_INVENTORY_SHAPE_INVALID")
    return inventory


def _read_card_view(
    workspace: AuthorWorkspace,
    chapter_id: str,
) -> dict[str, Any]:
    try:
        view = overview_reader_workspace.read_saved_overview_card_view(
            workspace,
            chapter_id,
        )
    except overview_reader_workspace.OverviewReaderWorkspaceError as exc:
        raise OverviewBookWorkspaceError("BOOK_OVERVIEW_CARD_VIEW_REJECTED") from exc
    if not isinstance(view, dict):
        _fail("BOOK_OVERVIEW_CARD_DISAPPEARED", chapter_id)
    return view


def _view_matches_inventory_item(
    view: dict[str, Any],
    item: object,
) -> bool:
    return (
        isinstance(item, dict)
        and view.get("chapter_id") == item.get("chapter_id")
        and view.get("overview_cards_version")
        == item.get("overview_cards_version")
        and view.get("overview_cards_sha256")
        == item.get("overview_cards_sha256")
        and view.get("chapter_revision_ref")
        == item.get("chapter_revision_ref")
        and view.get("facts_snapshot") == item.get("facts_snapshot")
        and view.get("chapter_index_snapshot")
        == item.get("chapter_index_snapshot")
        and view.get("freshness") == item.get("freshness")
        and view.get("stale_reasons") == item.get("stale_reasons")
        and isinstance(view.get("markdown"), str)
        and bool(view["markdown"])
    )


def _render_document(
    workspace: AuthorWorkspace,
    *,
    status: str,
    current_count: int,
    stale_count: int,
    card_markdowns: list[str],
) -> str:
    lines = [
        "# 项目已保存概览",
        "",
        f"- 作者工作区：{workspace.author_id}",
        f"- 项目：{workspace.project_id}",
        f"- 状态：{status}",
        f"- 已保存卡片：{len(card_markdowns)}",
        f"- 当前卡片：{current_count}",
        f"- 历史卡片：{stale_count}",
        "",
    ]
    if not card_markdowns:
        lines.extend(["当前没有已保存的 M9 概览卡。", ""])
        return "\n".join(lines)
    lines.extend(["## 章节概览", ""])
    lines.append("\n\n---\n\n".join(markdown.rstrip("\n") for markdown in card_markdowns))
    lines.append("")
    return "\n".join(lines)


def read_saved_overview_book_view(
    workspace: AuthorWorkspace,
) -> dict[str, Any]:
    """按现役 inventory 顺序返回全部已保存卡片的作者可读文档。"""
    handle = _require_workspace(workspace)
    first_inventory = _list_cards(handle)
    card_markdowns: list[str] = []
    current_count = 0
    stale_count = 0
    for item in first_inventory["cards"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("chapter_id"), str)
            or not item["chapter_id"]
        ):
            _fail("BOOK_OVERVIEW_INVENTORY_ITEM_INVALID")
        view = _read_card_view(handle, item["chapter_id"])
        if not _view_matches_inventory_item(view, item):
            _fail("BOOK_OVERVIEW_SNAPSHOT_MISMATCH", item["chapter_id"])
        if view["freshness"] == "CURRENT":
            current_count += 1
        elif view["freshness"] == "STALE":
            stale_count += 1
        else:
            _fail("BOOK_OVERVIEW_FRESHNESS_INVALID", item["chapter_id"])
        card_markdowns.append(view["markdown"])

    final_inventory = _list_cards(handle)
    if final_inventory != first_inventory:
        _fail("BOOK_OVERVIEW_CHANGED_DURING_READ")
    status = "EMPTY" if not card_markdowns else "READY"
    markdown = _render_document(
        handle,
        status=status,
        current_count=current_count,
        stale_count=stale_count,
        card_markdowns=card_markdowns,
    )
    return copy.deepcopy(
        {
            "status": status,
            "workspace_binding": {
                "author_id": handle.author_id,
                "project_id": handle.project_id,
            },
            "card_count": len(card_markdowns),
            "current_count": current_count,
            "stale_count": stale_count,
            "watermarks": first_inventory["watermarks"],
            "markdown": markdown,
        }
    )


__all__ = ["OverviewBookWorkspaceError", "read_saved_overview_book_view"]
