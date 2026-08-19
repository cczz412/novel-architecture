"""AuthorWorkspace 当前场景卡到 M10 无帧文本 ZIP 的只读适配层。"""

from __future__ import annotations

import copy
import hashlib
from typing import Any, NoReturn

from . import (
    plan_workspace,
    scene_card_workspace,
    scene_export_bundle,
    scene_export_workspace,
)
from .workspace import AuthorWorkspace


FRESHNESS_FIELDS = {
    "slot_ref",
    "plan_snapshot_changed",
    "saved_plan_snapshot",
    "current_plan_snapshot",
    "scenes",
    "new_scene_ids",
    "removed_scene_ids",
}


class SceneExportBundleWorkspaceError(RuntimeError):
    """已保存 C8、当前计划或逐场依赖未闭合时拒绝打包。"""


def _fail(code: str, detail: str = "") -> NoReturn:
    raise SceneExportBundleWorkspaceError(
        f"{code}:{detail}" if detail else code
    )


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _scene_snapshot_identity(
    value: object,
    *,
    slot_ref: str,
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("slot_ref") != slot_ref
        or not isinstance(value.get("version"), int)
        or isinstance(value.get("version"), bool)
        or value["version"] < 1
        or not _valid_sha256(value.get("sha256"))
        or not isinstance(value.get("scene_result"), dict)
    ):
        _fail("SCENE_CARD_SNAPSHOT_INVALID")
    return {"version": value["version"], "sha256": value["sha256"]}


def _plan_snapshot_identity(value: object) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("version"), int)
        or isinstance(value.get("version"), bool)
        or value["version"] < 1
        or not _valid_sha256(value.get("sha256"))
        or not isinstance(value.get("plan"), dict)
    ):
        _fail("PLAN_SNAPSHOT_INVALID")
    return {"version": value["version"], "sha256": value["sha256"]}


def _source_identity(scene_result: dict[str, Any]) -> dict[str, Any]:
    basis = scene_result.get("workspace_basis")
    if not isinstance(basis, dict):
        _fail("SCENE_RESULT_WORKSPACE_BASIS_INVALID")
    version = basis.get("source_plan_version")
    source_sha = basis.get("source_plan_sha256")
    if (
        not isinstance(version, int)
        or isinstance(version, bool)
        or version < 1
        or not _valid_sha256(source_sha)
    ):
        _fail("SCENE_RESULT_SOURCE_PLAN_INVALID")
    return {
        "source_plan_version": version,
        "source_plan_sha256": source_sha,
    }


def _validate_freshness(
    value: object,
    *,
    slot_ref: str,
    source_identity: dict[str, Any],
    current_plan: dict[str, Any],
) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != FRESHNESS_FIELDS
        or value.get("slot_ref") != slot_ref
        or not isinstance(value.get("new_scene_ids"), list)
        or not isinstance(value.get("removed_scene_ids"), list)
    ):
        _fail("FRESHNESS_RESULT_INVALID")
    scenes = value.get("scenes")
    if (
        value.get("new_scene_ids")
        or value.get("removed_scene_ids")
        or not isinstance(scenes, list)
        or not scenes
        or any(
            not isinstance(row, dict)
            or row.get("status") != "CURRENT"
            or row.get("reasons") != []
            for row in scenes
        )
    ):
        _fail("SCENE_RESULT_NOT_CURRENT")
    saved = value.get("saved_plan_snapshot")
    current = value.get("current_plan_snapshot")
    expected = {
        "version": source_identity["source_plan_version"],
        "sha256": source_identity["source_plan_sha256"],
    }
    if (
        value.get("plan_snapshot_changed") is not False
        or saved != expected
        or current != expected
        or current != current_plan
    ):
        _fail("SCENE_RESULT_PLAN_WATERMARK_NOT_CURRENT")


def execute(
    workspace: AuthorWorkspace,
    slot_ref: str,
    anchors: list[dict[str, Any]],
    scene_bindings: list[dict[str, Any]],
    event_bindings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """只在已保存 C8 与当前计划、场景依赖全部闭合时返回 ZIP。"""

    handle = _require_workspace(workspace)
    before_scene = scene_card_workspace.read_scene_cards(handle, slot_ref)
    if before_scene is None:
        return None
    before_scene_identity = _scene_snapshot_identity(
        before_scene,
        slot_ref=slot_ref,
    )
    before_plan = plan_workspace.read_plan(handle)
    before_plan_identity = _plan_snapshot_identity(before_plan)
    scene_result = copy.deepcopy(before_scene["scene_result"])
    source_identity = _source_identity(scene_result)

    try:
        freshness = scene_export_workspace.inspect_freshness(
            handle,
            scene_result,
            copy.deepcopy(anchors),
            copy.deepcopy(scene_bindings),
            copy.deepcopy(event_bindings),
        )
    except scene_export_workspace.SceneExportWorkspaceError as exc:
        raise SceneExportBundleWorkspaceError(
            f"FRESHNESS_CHECK_FAILED:{exc}"
        ) from exc
    _validate_freshness(
        freshness,
        slot_ref=slot_ref,
        source_identity=source_identity,
        current_plan=before_plan_identity,
    )

    try:
        zip_bytes = scene_export_bundle.build_bundle(
            scene_result,
            source_identity,
        )
    except scene_export_bundle.SceneExportBundleError as exc:
        raise SceneExportBundleWorkspaceError(
            f"TEXT_BUNDLE_BUILD_FAILED:{exc}"
        ) from exc

    after_scene = scene_card_workspace.read_scene_cards(handle, slot_ref)
    if after_scene is None:
        _fail("SCENE_CARD_SNAPSHOT_CHANGED_DURING_BUNDLE")
    after_scene_identity = _scene_snapshot_identity(
        after_scene,
        slot_ref=slot_ref,
    )
    after_plan = plan_workspace.read_plan(handle)
    after_plan_identity = _plan_snapshot_identity(after_plan)
    if after_scene_identity != before_scene_identity:
        _fail("SCENE_CARD_SNAPSHOT_CHANGED_DURING_BUNDLE")
    if after_plan_identity != before_plan_identity:
        _fail("PLAN_SNAPSHOT_CHANGED_DURING_BUNDLE")

    return {
        "slot_ref": slot_ref,
        "zip_bytes": zip_bytes,
        "zip_sha256": hashlib.sha256(zip_bytes).hexdigest(),
        "zip_size_bytes": len(zip_bytes),
        "source_plan": {
            "version": source_identity["source_plan_version"],
            "sha256": source_identity["source_plan_sha256"],
        },
        "scene_cards_snapshot": before_scene_identity,
    }


__all__ = ["SceneExportBundleWorkspaceError", "execute"]
