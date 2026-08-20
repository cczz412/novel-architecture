"""M10 场景卡原型对 AuthorWorkspace 的最小持久化适配器。

这里只保存已经由现役 M10 新鲜度入口确认仍适用于当前计划的原型结果。
路径、锁、原子提交、操作幂等和崩溃恢复仍全部由 workspace backend 负责。
"""

from __future__ import annotations

import copy
from typing import Any, NoReturn

from . import scene_export_workspace
from .workspace import AuthorWorkspace


SCENE_CARDS_LOGICAL_KEY = "scene_cards"
STORE_VERSION = "m10-scene-card-workspace-v1"
STORE_KEYS = {"store_version", "slots"}


class SceneCardWorkspaceError(RuntimeError):
    """场景卡存储请求或读回内容不符合当前原型边界。"""


def _fail(code: str, detail: str = "") -> NoReturn:
    raise SceneCardWorkspaceError(f"{code}:{detail}" if detail else code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _validated_scene_result(
    value: object,
    *,
    author_id: str,
    project_id: str,
) -> tuple[dict[str, Any], str]:
    candidate = copy.deepcopy(value)
    try:
        # 复用现役 M10 保存结果校验；这里不复制另一套 C8／绑定规则。
        binding = scene_export_workspace._saved_binding(candidate)
    except scene_export_workspace.SceneExportWorkspaceError as exc:
        raise SceneCardWorkspaceError("SCENE_RESULT_INVALID") from exc
    if (
        binding["author_id"] != author_id
        or binding["project_id"] != project_id
    ):
        _fail("SCENE_RESULT_WORKSPACE_MISMATCH")
    return candidate, binding["slot_ref"]


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
        or not isinstance(value.get("slots"), dict)
    ):
        _fail("SCENE_CARD_STORE_INVALID")
    slots: dict[str, dict[str, Any]] = {}
    for slot_ref, raw_result in value["slots"].items():
        if (
            not isinstance(slot_ref, str)
            or not slot_ref
            or slot_ref != slot_ref.strip()
        ):
            _fail("SCENE_CARD_SLOT_REF_INVALID")
        result, result_slot_ref = _validated_scene_result(
            raw_result,
            author_id=author_id,
            project_id=project_id,
        )
        if result_slot_ref != slot_ref:
            _fail("SCENE_CARD_SLOT_KEY_MISMATCH", slot_ref)
        slots[slot_ref] = result
    return {"store_version": STORE_VERSION, "slots": slots}


def _empty_store() -> dict[str, Any]:
    return {"store_version": STORE_VERSION, "slots": {}}


def _read_store_entry(workspace: AuthorWorkspace) -> tuple[dict[str, Any], dict] | None:
    entry = workspace.read(SCENE_CARDS_LOGICAL_KEY)
    if entry is None:
        return None
    store = _validated_store(
        entry.get("payload"),
        author_id=workspace.author_id,
        project_id=workspace.project_id,
    )
    return store, entry


def read_scene_cards(
    workspace: AuthorWorkspace,
    slot_ref: str,
) -> dict[str, Any] | None:
    """严格读回一个章槽的原型结果；空存储或未保存章槽返回 None。"""
    handle = _require_workspace(workspace)
    if not isinstance(slot_ref, str) or not slot_ref or slot_ref != slot_ref.strip():
        _fail("SLOT_REF_INVALID")
    loaded = _read_store_entry(handle)
    if loaded is None:
        return None
    store, entry = loaded
    scene_result = store["slots"].get(slot_ref)
    if scene_result is None:
        return None
    return {
        "version": entry["version"],
        "sha256": entry["sha256"],
        "slot_ref": slot_ref,
        "scene_result": copy.deepcopy(scene_result),
    }


def save_scene_cards(
    workspace: AuthorWorkspace,
    operation_id: str,
    scene_result: dict[str, Any],
    expected_version: int,
    *,
    anchors: list[dict[str, Any]],
    scene_bindings: list[dict[str, Any]],
    event_bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    """确认全部既有场景仍为 CURRENT，再按 slot_ref 原子保存原型结果。"""
    handle = _require_workspace(workspace)
    candidate, slot_ref = _validated_scene_result(
        scene_result,
        author_id=handle.author_id,
        project_id=handle.project_id,
    )
    freshness = scene_export_workspace.inspect_freshness(
        handle,
        candidate,
        copy.deepcopy(anchors),
        copy.deepcopy(scene_bindings),
        copy.deepcopy(event_bindings),
    )
    if freshness["new_scene_ids"] or freshness["removed_scene_ids"]:
        _fail("SCENE_RESULT_NOT_CURRENT", slot_ref)
    if not freshness["scenes"] or any(
        row.get("status") != "CURRENT" or row.get("reasons")
        for row in freshness["scenes"]
    ):
        _fail("SCENE_RESULT_NOT_CURRENT", slot_ref)

    loaded = _read_store_entry(handle)
    store = _empty_store() if loaded is None else loaded[0]
    store["slots"][slot_ref] = candidate
    return handle.commit(
        operation_id,
        {SCENE_CARDS_LOGICAL_KEY: store},
        {SCENE_CARDS_LOGICAL_KEY: expected_version},
    )


__all__ = [
    "SceneCardWorkspaceError",
    "read_scene_cards",
    "save_scene_cards",
]
