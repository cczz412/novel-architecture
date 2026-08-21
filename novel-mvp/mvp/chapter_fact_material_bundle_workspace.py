"""把 current confirmed 事实包与当前章规划供料合成一次性只读原型。

两部分保持分账：``current_fact_pack`` 只装已经发生且已确认的事实，
``planning_supply`` 只装未来计划与写法提示。结果不写工作区、不创建正式
上下文合同，也不成为章事实稿的正式消费者。
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, NoReturn

from . import (
    chapter_fact_supply_workspace,
    fact_workspace,
    packer_fact_workspace,
    plan_workspace,
)
from .workspace import AuthorWorkspace, SHA256_RE


PROTOTYPE_IDENTITY = "M11_CHAPTER_FACT_MATERIAL_BUNDLE_PROTOTYPE"
PROTOTYPE_VERSION = "v1"
CURRENT_FACT_ROLE = "CURRENT_CONFIRMED_FACTS_ALREADY_OCCURRED"
PLANNING_SUPPLY_ROLE = "FUTURE_PLAN_AND_WRITING_NOTES_NOT_FACT"
RESULT_FIELDS = {
    "prototype",
    "workspace_binding_sha256",
    "source_snapshots",
    "content_roles",
    "current_fact_pack",
    "planning_supply",
    "writes",
    "bundle_sha256",
}
SOURCE_FIELDS = {"plan", "facts", "chapter_index"}


class ChapterFactMaterialBundleWorkspaceError(RuntimeError):
    """当前工作区不能形成同一水位上的事实与规划供料原型。"""


def _fail(code: str, detail: str = "") -> NoReturn:
    raise ChapterFactMaterialBundleWorkspaceError(
        f"{code}:{detail}" if detail else code
    )


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _canonical_bytes(value: object) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ChapterFactMaterialBundleWorkspaceError(
            "BUNDLE_VALUE_NOT_JSON_SERIALIZABLE"
        ) from exc
    return (text + "\n").encode("utf-8")


def _payload_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _valid_snapshot_identity(value: object, *, allow_empty: bool) -> bool:
    if not isinstance(value, dict) or set(value) != {"version", "sha256"}:
        return False
    version = value["version"]
    sha256 = value["sha256"]
    if isinstance(version, bool) or not isinstance(version, int):
        return False
    if allow_empty and version == 0:
        return sha256 is None
    return (
        version >= 1
        and isinstance(sha256, str)
        and SHA256_RE.fullmatch(sha256) is not None
    )


def _source_snapshots(
    planning_supply: dict[str, Any],
    current_fact_pack: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        "plan": {
            "version": planning_supply["source_plan_version"],
            "sha256": planning_supply["source_plan_sha256"],
        },
        "facts": copy.deepcopy(current_fact_pack["source_snapshots"]["facts"]),
        "chapter_index": copy.deepcopy(
            current_fact_pack["source_snapshots"]["chapter_index"]
        ),
    }


def _read_current_source_snapshots(
    workspace: AuthorWorkspace,
) -> dict[str, dict[str, Any]]:
    try:
        plan_entry = plan_workspace.read_plan(workspace)
    except plan_workspace.PlanWorkspaceError as exc:
        raise ChapterFactMaterialBundleWorkspaceError(
            f"CURRENT_PLAN_SOURCE_INVALID:{exc}"
        ) from exc
    if plan_entry is None:
        _fail("CURRENT_PLAN_SOURCE_NOT_FOUND")
    try:
        fact_view = fact_workspace.read_current_snapshot(workspace)
    except fact_workspace.FactWorkspaceError as exc:
        raise ChapterFactMaterialBundleWorkspaceError(
            f"CURRENT_FACT_SOURCE_INVALID:{exc}"
        ) from exc
    return {
        "plan": {
            "version": plan_entry["version"],
            "sha256": plan_entry["sha256"],
        },
        "facts": copy.deepcopy(fact_view["facts_snapshot"]),
        "chapter_index": copy.deepcopy(fact_view["chapter_index_snapshot"]),
    }


def _without_sha(value: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(value)
    payload.pop("bundle_sha256", None)
    return payload


def validate_result(value: object) -> dict[str, Any]:
    """严格校验已有组合原型及其摘要，不重新读取工作区。"""

    if not isinstance(value, dict) or set(value) != RESULT_FIELDS:
        _fail("BUNDLE_RESULT_FIELDS_INVALID")
    result = copy.deepcopy(value)
    if result["prototype"] != {
        "identity": PROTOTYPE_IDENTITY,
        "version": PROTOTYPE_VERSION,
    }:
        _fail("BUNDLE_PROTOTYPE_IDENTITY_INVALID")
    binding = result["workspace_binding_sha256"]
    if not isinstance(binding, str) or SHA256_RE.fullmatch(binding) is None:
        _fail("BUNDLE_WORKSPACE_BINDING_INVALID")
    sources = result["source_snapshots"]
    if (
        not isinstance(sources, dict)
        or set(sources) != SOURCE_FIELDS
        or not _valid_snapshot_identity(sources["plan"], allow_empty=False)
        or not _valid_snapshot_identity(sources["facts"], allow_empty=True)
        or not _valid_snapshot_identity(
            sources["chapter_index"], allow_empty=True
        )
    ):
        _fail("BUNDLE_SOURCE_SNAPSHOTS_INVALID")
    if result["content_roles"] != {
        "current_fact_pack": CURRENT_FACT_ROLE,
        "planning_supply": PLANNING_SUPPLY_ROLE,
    }:
        _fail("BUNDLE_CONTENT_ROLES_INVALID")
    if result["writes"] != "none":
        _fail("BUNDLE_WRITES_INVALID")
    try:
        fact_pack = packer_fact_workspace.validate_result(
            result["current_fact_pack"]
        )
    except packer_fact_workspace.PackerFactWorkspaceError as exc:
        raise ChapterFactMaterialBundleWorkspaceError(
            f"BUNDLE_CURRENT_FACT_PACK_INVALID:{exc}"
        ) from exc
    if fact_pack["decision_state"] != "READY":
        _fail("BUNDLE_CURRENT_FACT_PACK_NOT_READY", fact_pack["decision_state"])
    if fact_pack["workspace_binding_sha256"] != binding:
        _fail("BUNDLE_WORKSPACE_BINDING_MISMATCH")
    try:
        planning_supply = chapter_fact_supply_workspace.validate_result(
            result["planning_supply"]
        )
    except chapter_fact_supply_workspace.ChapterFactSupplyWorkspaceError as exc:
        raise ChapterFactMaterialBundleWorkspaceError(
            f"BUNDLE_PLANNING_SUPPLY_INVALID:{exc}"
        ) from exc
    expected_sources = _source_snapshots(planning_supply, fact_pack)
    if sources != expected_sources:
        _fail("BUNDLE_SOURCE_SNAPSHOT_MISMATCH")
    digest = result["bundle_sha256"]
    if (
        not isinstance(digest, str)
        or SHA256_RE.fullmatch(digest) is None
        or digest != _payload_sha256(_without_sha(result))
    ):
        _fail("BUNDLE_SHA256_INVALID")
    result["current_fact_pack"] = fact_pack
    result["planning_supply"] = planning_supply
    return result


def execute(
    workspace: AuthorWorkspace,
    slot_ref: str,
    pack_request: dict[str, Any],
) -> dict[str, Any]:
    """读取同一项目的事实与规划供料，形成零写入的一次性原型。"""

    handle = _require_workspace(workspace)
    try:
        planning_supply = chapter_fact_supply_workspace.validate_result(
            chapter_fact_supply_workspace.execute(handle, slot_ref)
        )
    except chapter_fact_supply_workspace.ChapterFactSupplyWorkspaceError as exc:
        raise ChapterFactMaterialBundleWorkspaceError(
            f"PLANNING_SUPPLY_REJECTED:{exc}"
        ) from exc
    try:
        current_fact_pack = packer_fact_workspace.validate_result(
            packer_fact_workspace.execute(handle, pack_request)
        )
    except packer_fact_workspace.PackerFactWorkspaceError as exc:
        raise ChapterFactMaterialBundleWorkspaceError(
            f"CURRENT_FACT_PACK_REJECTED:{exc}"
        ) from exc
    if current_fact_pack["decision_state"] != "READY":
        _fail(
            "CURRENT_FACT_PACK_NOT_READY",
            current_fact_pack["decision_state"],
        )

    expected_sources = _source_snapshots(planning_supply, current_fact_pack)
    first_after = _read_current_source_snapshots(handle)
    second_after = _read_current_source_snapshots(handle)
    if first_after != expected_sources or second_after != expected_sources:
        _fail("BUNDLE_SOURCE_CHANGED_DURING_ASSEMBLY")

    result = {
        "prototype": {
            "identity": PROTOTYPE_IDENTITY,
            "version": PROTOTYPE_VERSION,
        },
        "workspace_binding_sha256": current_fact_pack[
            "workspace_binding_sha256"
        ],
        "source_snapshots": expected_sources,
        "content_roles": {
            "current_fact_pack": CURRENT_FACT_ROLE,
            "planning_supply": PLANNING_SUPPLY_ROLE,
        },
        "current_fact_pack": current_fact_pack,
        "planning_supply": planning_supply,
        "writes": "none",
    }
    result["bundle_sha256"] = _payload_sha256(result)
    return validate_result(result)


__all__ = [
    "ChapterFactMaterialBundleWorkspaceError",
    "execute",
    "validate_result",
]
