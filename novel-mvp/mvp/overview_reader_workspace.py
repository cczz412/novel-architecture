"""AuthorWorkspace 中已保存 M9 卡片的一键只读视图。

这里只组合现役卡片清单、单卡读回和 Markdown 渲染。它不生成、刷新、删除
或保存概览，也不接受路径、作者号或项目号。
"""

from __future__ import annotations

import copy
from typing import Any, NoReturn

from . import overview, overview_card_workspace
from .workspace import AuthorWorkspace


class OverviewReaderWorkspaceError(RuntimeError):
    """已保存概览不能组成单一、一致的作者可读视图。"""


def _fail(code: str, detail: str = "") -> NoReturn:
    raise OverviewReaderWorkspaceError(f"{code}:{detail}" if detail else code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _clean_chapter_id(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        _fail("CHAPTER_ID_INVALID")
    return value


def _list_cards(workspace: AuthorWorkspace) -> dict[str, Any]:
    try:
        return overview_card_workspace.list_overview_cards(workspace)
    except overview_card_workspace.OverviewCardWorkspaceError as exc:
        raise OverviewReaderWorkspaceError(
            "SAVED_CARD_INVENTORY_REJECTED"
        ) from exc


def _find_inventory_item(
    inventory: object,
    chapter_id: str,
) -> dict[str, Any] | None:
    if (
        not isinstance(inventory, dict)
        or set(inventory) != {"watermarks", "cards"}
        or not isinstance(inventory.get("watermarks"), dict)
        or not isinstance(inventory.get("cards"), list)
    ):
        _fail("SAVED_CARD_INVENTORY_SHAPE_INVALID")
    matches = [
        item
        for item in inventory["cards"]
        if isinstance(item, dict) and item.get("chapter_id") == chapter_id
    ]
    if len(matches) > 1:
        _fail("SAVED_CARD_INVENTORY_CHAPTER_DUPLICATE", chapter_id)
    return None if not matches else matches[0]


def _read_card(
    workspace: AuthorWorkspace,
    chapter_id: str,
) -> dict[str, Any] | None:
    try:
        return overview_card_workspace.read_overview_card(workspace, chapter_id)
    except overview_card_workspace.OverviewCardWorkspaceError as exc:
        raise OverviewReaderWorkspaceError("SAVED_CARD_READ_REJECTED") from exc


def _same_inventory_snapshot(
    first: dict[str, Any],
    second: dict[str, Any],
    *,
    chapter_id: str,
) -> dict[str, Any] | None:
    if first["watermarks"] != second["watermarks"]:
        _fail("SAVED_CARD_VIEW_CHANGED_DURING_READ")
    first_item = _find_inventory_item(first, chapter_id)
    second_item = _find_inventory_item(second, chapter_id)
    if first_item != second_item:
        _fail("SAVED_CARD_VIEW_CHANGED_DURING_READ")
    return first_item


def _render_markdown(
    card: dict[str, Any],
    *,
    freshness: str,
    stale_reasons: list[str],
) -> str:
    try:
        rendered = overview.render_card(card)
    except overview.OverviewError as exc:
        raise OverviewReaderWorkspaceError("SAVED_CARD_RENDER_REJECTED") from exc
    if freshness == "CURRENT":
        return "# 当前概览（CURRENT）\n\n" + rendered
    reasons = "\n".join(f"- `{reason}`" for reason in stale_reasons)
    return (
        "# ⚠️ 历史概览（已过期）\n\n"
        "> 这张卡只供查看历史，不是当前概览。\n\n"
        "过期原因：\n\n"
        f"{reasons}\n\n"
        f"{rendered}"
    )


def read_saved_overview_card_view(
    workspace: AuthorWorkspace,
    chapter_id: str,
) -> dict[str, Any] | None:
    """稳定读出一章已保存卡、现役新鲜度和作者可读 Markdown。"""
    handle = _require_workspace(workspace)
    clean_chapter_id = _clean_chapter_id(chapter_id)
    first_inventory = _list_cards(handle)
    first_item = _find_inventory_item(first_inventory, clean_chapter_id)
    if first_item is None:
        second_inventory = _list_cards(handle)
        _same_inventory_snapshot(
            first_inventory,
            second_inventory,
            chapter_id=clean_chapter_id,
        )
        return None

    saved = _read_card(handle, clean_chapter_id)
    if saved is None:
        _fail("SAVED_CARD_VIEW_CHANGED_DURING_READ")
    overview_watermark = first_inventory["watermarks"].get("overview_cards")
    if (
        not isinstance(overview_watermark, dict)
        or saved.get("chapter_id") != clean_chapter_id
        or saved.get("version") != first_item.get("overview_cards_version")
        or saved.get("sha256") != first_item.get("overview_cards_sha256")
        or saved.get("version") != overview_watermark.get("version")
        or saved.get("sha256") != overview_watermark.get("sha256")
    ):
        _fail("SAVED_CARD_VIEW_CHANGED_DURING_READ")

    saved_result = saved.get("overview_result")
    if (
        not isinstance(saved_result, dict)
        or saved_result.get("facts_snapshot") != first_item.get("facts_snapshot")
        or saved_result.get("chapter_index_snapshot")
        != first_item.get("chapter_index_snapshot")
        or not isinstance(saved_result.get("m9"), dict)
        or saved_result["m9"].get("chapter_revision_ref")
        != first_item.get("chapter_revision_ref")
    ):
        _fail("SAVED_CARD_VIEW_IDENTITY_MISMATCH")

    second_inventory = _list_cards(handle)
    stable_item = _same_inventory_snapshot(
        first_inventory,
        second_inventory,
        chapter_id=clean_chapter_id,
    )
    if stable_item is None:
        _fail("SAVED_CARD_VIEW_CHANGED_DURING_READ")
    freshness = stable_item.get("freshness")
    stale_reasons = stable_item.get("stale_reasons")
    if (
        freshness not in {"CURRENT", "STALE"}
        or not isinstance(stale_reasons, list)
        or (freshness == "CURRENT" and stale_reasons)
        or (freshness == "STALE" and not stale_reasons)
        or any(not isinstance(reason, str) or not reason for reason in stale_reasons)
    ):
        _fail("SAVED_CARD_FRESHNESS_INVALID")
    markdown = _render_markdown(
        saved_result["m9"],
        freshness=freshness,
        stale_reasons=stale_reasons,
    )
    return copy.deepcopy(
        {
            "chapter_id": clean_chapter_id,
            "overview_cards_version": saved["version"],
            "overview_cards_sha256": saved["sha256"],
            "chapter_revision_ref": stable_item["chapter_revision_ref"],
            "facts_snapshot": stable_item["facts_snapshot"],
            "chapter_index_snapshot": stable_item["chapter_index_snapshot"],
            "freshness": freshness,
            "stale_reasons": stale_reasons,
            "markdown": markdown,
        }
    )


__all__ = ["OverviewReaderWorkspaceError", "read_saved_overview_card_view"]
