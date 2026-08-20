"""M9 原型概览卡对 AuthorWorkspace 的最小持久化适配器。

这里只保存已经由现役 M9 新鲜度入口确认仍为 CURRENT 的原型结果。
路径、锁、原子提交、操作幂等和崩溃恢复仍全部由 workspace backend 负责。
"""

from __future__ import annotations

import copy
from typing import Any, NoReturn

from . import overview, overview_workspace
from .workspace import AuthorWorkspace


OVERVIEW_CARDS_LOGICAL_KEY = "overview_cards"
STORE_VERSION = "m9-overview-card-workspace-v1"
STORE_KEYS = {"store_version", "chapters"}
WORKSPACE_ENTRY_KEYS = {"logical_key", "version", "sha256", "payload"}
FRESHNESS_KEYS = {"freshness", "stale_reasons", "saved_basis", "current_basis"}
BASIS_KEYS = {
    "workspace_binding",
    "facts_snapshot",
    "chapter_index_snapshot",
    "chapter_revision_ref",
}


class OverviewCardWorkspaceError(RuntimeError):
    """概览卡存储请求或读回内容不符合当前 M9 原型边界。"""


def _fail(code: str, detail: str = "") -> NoReturn:
    raise OverviewCardWorkspaceError(f"{code}:{detail}" if detail else code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _clean_chapter_id(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        _fail("CHAPTER_ID_INVALID")
    return value


def _validated_overview_result(
    value: object,
    *,
    author_id: str,
    project_id: str,
) -> tuple[dict[str, Any], str]:
    candidate = copy.deepcopy(value)
    try:
        basis = overview_workspace._saved_basis(candidate)
    except overview_workspace.OverviewWorkspaceError as exc:
        raise OverviewCardWorkspaceError("OVERVIEW_RESULT_INVALID") from exc
    binding = basis["workspace_binding"]
    if binding["author_id"] != author_id or binding["project_id"] != project_id:
        _fail("OVERVIEW_RESULT_WORKSPACE_MISMATCH")
    return candidate, basis["chapter_revision_ref"]["chapter_id"]


def _validated_store(
    value: object,
    *,
    author_id: str,
    project_id: str,
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != STORE_KEYS
        or value.get("store_version") != STORE_VERSION
        or not isinstance(value.get("chapters"), dict)
    ):
        _fail("OVERVIEW_CARD_STORE_INVALID")
    chapters: dict[str, dict[str, Any]] = {}
    seen_identities: set[str] = set()
    for raw_chapter_id, raw_result in value["chapters"].items():
        chapter_id = _clean_chapter_id(raw_chapter_id)
        result, result_chapter_id = _validated_overview_result(
            raw_result,
            author_id=author_id,
            project_id=project_id,
        )
        if result_chapter_id in seen_identities:
            _fail("OVERVIEW_CARD_CHAPTER_IDENTITY_DUPLICATE", result_chapter_id)
        if result_chapter_id != chapter_id:
            _fail("OVERVIEW_CARD_CHAPTER_KEY_MISMATCH", chapter_id)
        seen_identities.add(result_chapter_id)
        chapters[chapter_id] = result
    return {"store_version": STORE_VERSION, "chapters": chapters}


def _empty_store() -> dict[str, Any]:
    return {"store_version": STORE_VERSION, "chapters": {}}


def _read_store_entry(
    workspace: AuthorWorkspace,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    entry = workspace.read(OVERVIEW_CARDS_LOGICAL_KEY)
    if entry is None:
        return None
    store = _validated_store(
        entry.get("payload"),
        author_id=workspace.author_id,
        project_id=workspace.project_id,
    )
    return store, entry


def _entry_watermark(
    entry: object,
    *,
    logical_key: str,
) -> dict[str, Any]:
    if entry is None:
        return {"version": 0, "sha256": None}
    if (
        not isinstance(entry, dict)
        or set(entry) != WORKSPACE_ENTRY_KEYS
        or entry.get("logical_key") != logical_key
        or not isinstance(entry.get("version"), int)
        or isinstance(entry.get("version"), bool)
        or entry["version"] < 1
        or not isinstance(entry.get("sha256"), str)
        or overview.SHA256_RE.fullmatch(entry["sha256"]) is None
    ):
        _fail("INVENTORY_WORKSPACE_ENTRY_INVALID", logical_key)
    return {"version": entry["version"], "sha256": entry["sha256"]}


def _read_store_snapshot(
    workspace: AuthorWorkspace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    loaded = _read_store_entry(workspace)
    if loaded is None:
        return _empty_store(), _entry_watermark(
            None,
            logical_key=OVERVIEW_CARDS_LOGICAL_KEY,
        )
    store, entry = loaded
    return store, _entry_watermark(
        entry,
        logical_key=OVERVIEW_CARDS_LOGICAL_KEY,
    )


def _read_source_watermarks(workspace: AuthorWorkspace) -> dict[str, dict[str, Any]]:
    return {
        logical_key: _entry_watermark(
            workspace.read(logical_key),
            logical_key=logical_key,
        )
        for logical_key in ("facts", "chapter_index")
    }


def _valid_snapshot_identity(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"version", "sha256"}
        and isinstance(value.get("version"), int)
        and not isinstance(value["version"], bool)
        and value["version"] >= 1
        and isinstance(value.get("sha256"), str)
        and overview.SHA256_RE.fullmatch(value["sha256"]) is not None
    )


def _validated_freshness(
    value: object,
    *,
    workspace: AuthorWorkspace,
    saved_result: dict[str, Any],
) -> tuple[str, list[str], dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != FRESHNESS_KEYS:
        _fail("INVENTORY_FRESHNESS_RESULT_INVALID")
    try:
        expected_saved_basis = overview_workspace._saved_basis(saved_result)
    except overview_workspace.OverviewWorkspaceError as exc:
        raise OverviewCardWorkspaceError("OVERVIEW_RESULT_INVALID") from exc
    if value["saved_basis"] != expected_saved_basis:
        _fail("INVENTORY_FRESHNESS_SAVED_BASIS_MISMATCH")

    current_basis = value["current_basis"]
    expected_binding = {
        "author_id": workspace.author_id,
        "project_id": workspace.project_id,
    }
    if (
        not isinstance(current_basis, dict)
        or set(current_basis) != BASIS_KEYS
        or current_basis.get("workspace_binding") != expected_binding
        or not _valid_snapshot_identity(current_basis.get("facts_snapshot"))
        or not _valid_snapshot_identity(
            current_basis.get("chapter_index_snapshot")
        )
        or not overview_workspace._valid_revision_ref(
            current_basis.get("chapter_revision_ref")
        )
        or current_basis["chapter_revision_ref"]["chapter_id"]
        != expected_saved_basis["chapter_revision_ref"]["chapter_id"]
    ):
        _fail("INVENTORY_FRESHNESS_CURRENT_BASIS_INVALID")

    expected_reasons: list[str] = []
    if (
        expected_saved_basis["facts_snapshot"]
        != current_basis["facts_snapshot"]
    ):
        expected_reasons.append("FACTS_SNAPSHOT_CHANGED")
    if (
        expected_saved_basis["chapter_index_snapshot"]
        != current_basis["chapter_index_snapshot"]
    ):
        expected_reasons.append("CHAPTER_INDEX_SNAPSHOT_CHANGED")
    if (
        expected_saved_basis["chapter_revision_ref"]
        != current_basis["chapter_revision_ref"]
    ):
        expected_reasons.append("CHAPTER_REVISION_CHANGED")
    expected_freshness = "STALE" if expected_reasons else "CURRENT"
    if (
        value["freshness"] != expected_freshness
        or value["stale_reasons"] != expected_reasons
    ):
        _fail("INVENTORY_FRESHNESS_RESULT_INCONSISTENT")
    return expected_freshness, expected_reasons, expected_saved_basis


def read_overview_card(
    workspace: AuthorWorkspace,
    chapter_id: str,
) -> dict[str, Any] | None:
    """严格读回一章原型概览；空存储或未保存章节返回 None。"""
    handle = _require_workspace(workspace)
    clean_chapter_id = _clean_chapter_id(chapter_id)
    loaded = _read_store_entry(handle)
    if loaded is None:
        return None
    store, entry = loaded
    overview_result = store["chapters"].get(clean_chapter_id)
    if overview_result is None:
        return None
    return {
        "version": entry["version"],
        "sha256": entry["sha256"],
        "chapter_id": clean_chapter_id,
        "overview_result": copy.deepcopy(overview_result),
    }


def list_overview_cards(workspace: AuthorWorkspace) -> dict[str, Any]:
    """按稳定章节顺序列出已保存卡及现役全局快照新鲜度。"""
    handle = _require_workspace(workspace)
    store, overview_cards_watermark = _read_store_snapshot(handle)
    source_watermarks = _read_source_watermarks(handle)
    first_watermarks = {
        "overview_cards": overview_cards_watermark,
        **source_watermarks,
    }

    cards: list[dict[str, Any]] = []
    for chapter_id in sorted(store["chapters"]):
        saved_result = store["chapters"][chapter_id]
        try:
            freshness_result = overview_workspace.inspect_freshness(
                handle,
                saved_result,
            )
        except overview_workspace.OverviewWorkspaceError as exc:
            raise OverviewCardWorkspaceError(
                "INVENTORY_FRESHNESS_INSPECTION_FAILED"
            ) from exc
        freshness, stale_reasons, saved_basis = _validated_freshness(
            freshness_result,
            workspace=handle,
            saved_result=saved_result,
        )
        synopsis = saved_result["m9"].get("synopsis")
        if (
            not isinstance(synopsis, str)
            or not synopsis
            or synopsis != synopsis.strip()
        ):
            _fail("INVENTORY_SYNOPSIS_INVALID", chapter_id)
        cards.append(
            {
                "chapter_id": chapter_id,
                "overview_cards_version": overview_cards_watermark["version"],
                "overview_cards_sha256": overview_cards_watermark["sha256"],
                "chapter_revision_ref": copy.deepcopy(
                    saved_basis["chapter_revision_ref"]
                ),
                "facts_snapshot": copy.deepcopy(saved_basis["facts_snapshot"]),
                "chapter_index_snapshot": copy.deepcopy(
                    saved_basis["chapter_index_snapshot"]
                ),
                "freshness": freshness,
                "stale_reasons": list(stale_reasons),
                "synopsis": synopsis,
            }
        )

    _, final_overview_cards_watermark = _read_store_snapshot(handle)
    final_watermarks = {
        "overview_cards": final_overview_cards_watermark,
        **_read_source_watermarks(handle),
    }
    if final_watermarks != first_watermarks:
        changed = sorted(
            key
            for key in first_watermarks
            if first_watermarks[key] != final_watermarks[key]
        )
        _fail("INVENTORY_WATERMARK_CHANGED", ",".join(changed))
    return copy.deepcopy(
        {
            "watermarks": first_watermarks,
            "cards": cards,
        }
    )


def save_overview_card(
    workspace: AuthorWorkspace,
    operation_id: str,
    overview_result: dict[str, Any],
    expected_version: int,
) -> dict[str, Any]:
    """确认原型卡仍为 CURRENT，再按 chapter_id 原子保存。"""
    handle = _require_workspace(workspace)
    candidate, chapter_id = _validated_overview_result(
        overview_result,
        author_id=handle.author_id,
        project_id=handle.project_id,
    )
    try:
        freshness = overview_workspace.inspect_freshness(handle, candidate)
    except overview_workspace.OverviewWorkspaceError as exc:
        raise OverviewCardWorkspaceError("OVERVIEW_RESULT_FRESHNESS_INVALID") from exc
    if freshness.get("freshness") != "CURRENT" or freshness.get("stale_reasons"):
        reasons = freshness.get("stale_reasons")
        detail = ",".join(reasons) if isinstance(reasons, list) else chapter_id
        _fail("OVERVIEW_RESULT_NOT_CURRENT", detail)

    loaded = _read_store_entry(handle)
    store = _empty_store() if loaded is None else loaded[0]
    store["chapters"][chapter_id] = candidate
    return handle.commit(
        operation_id,
        {OVERVIEW_CARDS_LOGICAL_KEY: store},
        {OVERVIEW_CARDS_LOGICAL_KEY: expected_version},
    )


__all__ = [
    "OverviewCardWorkspaceError",
    "list_overview_cards",
    "read_overview_card",
    "save_overview_card",
]
