"""AuthorWorkspace → CHAPTER_SLOT_SNAPSHOT v1 的只读适配层。

调用方只能交付已经绑定作者与项目的能力句柄和明确章槽号。本模块读取当前
``plan`` 逻辑键，随后原样调用现有章槽快照对象核心；它没有任何写入口。
"""

from __future__ import annotations

import re
from typing import Any, NoReturn

from . import chapter_slot_snapshot_tool, plan_workspace
from .workspace import AuthorWorkspace


PLAN_ENTRY_KEYS = frozenset({"version", "sha256", "plan"})
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class ChapterSlotWorkspaceError(RuntimeError):
    """工作区句柄或当前 plan 身份不足以产生章槽只读快照。"""


def _fail(code: str, detail: str = "") -> NoReturn:
    raise ChapterSlotWorkspaceError(f"{code}:{detail}" if detail else code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _validate_plan_entry(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != PLAN_ENTRY_KEYS:
        _fail("PLAN_SNAPSHOT_IDENTITY_INVALID")
    version = value.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        _fail("PLAN_SNAPSHOT_VERSION_INVALID")
    sha256 = value.get("sha256")
    if not isinstance(sha256, str) or SHA256_RE.fullmatch(sha256) is None:
        _fail("PLAN_SNAPSHOT_SHA_INVALID")
    if not isinstance(value.get("plan"), dict):
        _fail("PLAN_SNAPSHOT_OBJECT_REQUIRED")
    return value


def execute(workspace: AuthorWorkspace, slot_ref: str) -> dict[str, Any]:
    """从当前 plan 投影调用方明确点名的唯一章槽；全程只读。"""
    handle = _require_workspace(workspace)
    if not isinstance(slot_ref, str) or not slot_ref or slot_ref != slot_ref.strip():
        _fail("SLOT_REF_INVALID")

    current = plan_workspace.read_plan(handle)
    if current is None:
        _fail("PLAN_SNAPSHOT_NOT_FOUND")
    entry = _validate_plan_entry(current)
    output = chapter_slot_snapshot_tool.execute(
        {
            "plan": entry["plan"],
            "slot_ref": slot_ref,
            "source_plan_version": entry["version"],
            "source_plan_sha256": entry["sha256"],
        }
    )
    if (
        output.get("contract") != chapter_slot_snapshot_tool.CONTRACT
        or output.get("version") != chapter_slot_snapshot_tool.VERSION
        or output.get("slot_ref") != slot_ref
        or output.get("source_plan_version") != entry["version"]
        or output.get("source_plan_sha256") != entry["sha256"]
    ):
        _fail("CHAPTER_SLOT_SNAPSHOT_IDENTITY_DRIFT")
    return output
