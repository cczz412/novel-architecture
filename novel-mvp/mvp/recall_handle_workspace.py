"""AuthorWorkspace 内的 M11 recall handle 绑定与新鲜度解析器。

来源 owner 只登记 opaque handle → current source ref。本文不解释 object_ref 的领域语义，
不复制材料正文，也不让 M11 扫描项目或重写来源对象。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from .workspace import (
    AuthorWorkspace,
    InvalidLogicalKeyError,
    OperationConflictError,
    VersionConflictError,
)


LOGICAL_KEY = "recall_handles"
REGISTRY_SCHEMA_VERSION = "m11-recall-handle-registry-v1"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
HANDLE_RE = re.compile(r"rh_[0-9a-f]{32}\Z")
OPERATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
REGISTRY_KEYS = {"schema_version", "bindings", "operations"}
BINDING_KEYS = {"handle", "source_owner", "source_ref"}
SOURCE_REF_KEYS = {"logical_key", "object_ref", "version", "sha256"}
OPERATION_KEYS = {"operation_id", "parent_version", "request_sha256", "handles"}


class RecallHandleWorkspaceError(ValueError):
    """recall handle 注册、解析或新鲜度检查失败。"""


class RecallHandleNotFoundError(RecallHandleWorkspaceError):
    """当前作者项目中不存在该 handle。"""


class RecallHandleStaleError(RecallHandleWorkspaceError):
    """handle 存在，但绑定的来源版本已不是 current。"""


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        raise RecallHandleWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise RecallHandleWorkspaceError("RECALL_VALUE_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any, code: str, *, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or any(ord(char) < 32 for char in value)
    ):
        raise RecallHandleWorkspaceError(code)
    return value


def _handle(value: Any) -> str:
    value = _text(value, "RECALL_HANDLE_INVALID", maximum=35)
    if HANDLE_RE.fullmatch(value) is None:
        raise RecallHandleWorkspaceError("RECALL_HANDLE_INVALID")
    return value


def _mint_handle(
    workspace: AuthorWorkspace,
    source_owner: str,
    source_ref: Mapping[str, Any],
) -> str:
    digest = _sha256(
        {
            "author_id": workspace.author_id,
            "project_id": workspace.project_id,
            "source_owner": source_owner,
            "source_ref": copy.deepcopy(dict(source_ref)),
        }
    )
    return f"rh_{digest[:32]}"


def _source_ref(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != SOURCE_REF_KEYS:
        raise RecallHandleWorkspaceError("RECALL_SOURCE_REF_INVALID")
    logical_key = _text(
        value.get("logical_key"), "RECALL_SOURCE_REF_INVALID", maximum=100
    )
    if logical_key == LOGICAL_KEY:
        raise RecallHandleWorkspaceError("RECALL_SOURCE_REF_SELF_REFERENCE")
    object_ref = _text(
        value.get("object_ref"), "RECALL_SOURCE_REF_INVALID", maximum=500
    )
    version = value.get("version")
    digest = value.get("sha256")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
        or not isinstance(digest, str)
        or SHA256_RE.fullmatch(digest) is None
    ):
        raise RecallHandleWorkspaceError("RECALL_SOURCE_REF_INVALID")
    return {
        "logical_key": logical_key,
        "object_ref": object_ref,
        "version": version,
        "sha256": digest,
    }


def _binding(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != BINDING_KEYS:
        raise RecallHandleWorkspaceError("RECALL_BINDING_INVALID")
    return {
        "handle": _handle(value.get("handle")),
        "source_owner": _text(
            value.get("source_owner"),
            "RECALL_SOURCE_OWNER_INVALID",
            maximum=100,
        ),
        "source_ref": _source_ref(value.get("source_ref")),
    }


def _operation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != OPERATION_KEYS:
        raise RecallHandleWorkspaceError("RECALL_REGISTRY_OPERATION_INVALID")
    operation_id = value.get("operation_id")
    parent_version = value.get("parent_version")
    digest = value.get("request_sha256")
    handles = value.get("handles")
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
        or isinstance(parent_version, bool)
        or not isinstance(parent_version, int)
        or parent_version < 0
        or not isinstance(digest, str)
        or SHA256_RE.fullmatch(digest) is None
        or not isinstance(handles, list)
        or not handles
        or any(not isinstance(handle, str) for handle in handles)
        or handles != sorted(set(handles))
    ):
        raise RecallHandleWorkspaceError("RECALL_REGISTRY_OPERATION_INVALID")
    return {
        "operation_id": operation_id,
        "parent_version": parent_version,
        "request_sha256": digest,
        "handles": list(handles),
    }


def _empty_registry() -> dict[str, Any]:
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "bindings": [],
        "operations": [],
    }


def _registry(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != REGISTRY_KEYS
        or value.get("schema_version") != REGISTRY_SCHEMA_VERSION
        or not isinstance(value.get("bindings"), list)
        or not isinstance(value.get("operations"), list)
    ):
        raise RecallHandleWorkspaceError("RECALL_REGISTRY_INVALID")
    bindings = [_binding(row) for row in value["bindings"]]
    operations = [_operation(row) for row in value["operations"]]
    handles = [row["handle"] for row in bindings]
    operation_ids = [row["operation_id"] for row in operations]
    if handles != sorted(handles) or len(handles) != len(set(handles)):
        raise RecallHandleWorkspaceError("RECALL_REGISTRY_BINDING_DUPLICATE")
    if len(operation_ids) != len(set(operation_ids)):
        raise RecallHandleWorkspaceError("RECALL_REGISTRY_OPERATION_DUPLICATE")
    if any(
        operation["parent_version"] != index
        for index, operation in enumerate(operations)
    ):
        raise RecallHandleWorkspaceError(
            "RECALL_REGISTRY_OPERATION_PARENT_INVALID"
        )
    operation_handles = [
        handle
        for operation in operations
        for handle in operation["handles"]
    ]
    if (
        len(operation_handles) != len(set(operation_handles))
        or set(operation_handles) != set(handles)
    ):
        raise RecallHandleWorkspaceError("RECALL_REGISTRY_OPERATION_UNKNOWN_HANDLE")
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "bindings": bindings,
        "operations": operations,
    }


def _validated_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "logical_key",
        "version",
        "sha256",
        "payload",
    }:
        raise RecallHandleWorkspaceError("RECALL_REGISTRY_STATE_INVALID")
    version = value.get("version")
    digest = value.get("sha256")
    if (
        value.get("logical_key") != LOGICAL_KEY
        or isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
        or not isinstance(digest, str)
        or SHA256_RE.fullmatch(digest) is None
        or _sha256(value.get("payload")) != digest
    ):
        raise RecallHandleWorkspaceError("RECALL_REGISTRY_STATE_INVALID")
    return {**value, "payload": _registry(value["payload"])}


def _read_registry_state(workspace: AuthorWorkspace) -> dict[str, Any]:
    state = workspace.read(LOGICAL_KEY)
    if state is None:
        return {
            "logical_key": LOGICAL_KEY,
            "version": 0,
            "sha256": None,
            "payload": _empty_registry(),
        }
    validated = _validated_state(state)
    if any(
        binding["handle"]
        != _mint_handle(
            workspace,
            binding["source_owner"],
            binding["source_ref"],
        )
        for binding in validated["payload"]["bindings"]
    ):
        raise RecallHandleWorkspaceError("RECALL_HANDLE_MINT_IDENTITY_INVALID")
    return validated


def _source_state(
    workspace: AuthorWorkspace,
    source_ref: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        state = workspace.read(source_ref["logical_key"])
    except InvalidLogicalKeyError as exc:
        raise RecallHandleWorkspaceError("RECALL_SOURCE_LOGICAL_KEY_INVALID") from exc
    if state is None:
        raise RecallHandleStaleError("RECALL_HANDLE_STALE")
    if (
        state.get("version") != source_ref["version"]
        or state.get("sha256") != source_ref["sha256"]
    ):
        raise RecallHandleStaleError("RECALL_HANDLE_STALE")
    return state


def _validate_current_source(
    workspace: AuthorWorkspace, binding: dict[str, Any]
) -> tuple[int, str]:
    state = _source_state(workspace, binding["source_ref"])
    return state["version"], state["sha256"]


def build_binding(
    workspace: AuthorWorkspace,
    *,
    source_owner: str,
    source_ref: Mapping[str, Any],
) -> dict[str, Any]:
    """由绑定工作区为来源快照生成不透明 handle；不返回来源正文。"""
    workspace = _require_workspace(workspace)
    owner = _text(
        source_owner,
        "RECALL_SOURCE_OWNER_INVALID",
        maximum=100,
    )
    normalized_ref = _source_ref(source_ref)
    binding = {
        "handle": _mint_handle(workspace, owner, normalized_ref),
        "source_owner": owner,
        "source_ref": normalized_ref,
    }
    _validate_current_source(workspace, binding)
    return binding


def register_bindings(
    workspace: AuthorWorkspace,
    *,
    operation_id: str,
    bindings: list[dict[str, Any]],
    expected_registry_version: int,
) -> dict[str, Any]:
    """由来源 owner 登记 handle；同一 handle 不能静默改绑。"""
    workspace = _require_workspace(workspace)
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        raise RecallHandleWorkspaceError("RECALL_OPERATION_ID_INVALID")
    if (
        isinstance(expected_registry_version, bool)
        or not isinstance(expected_registry_version, int)
        or expected_registry_version < 0
        or not isinstance(bindings, list)
        or not bindings
    ):
        raise RecallHandleWorkspaceError("RECALL_REGISTER_INPUT_INVALID")
    normalized = sorted(
        (_binding(row) for row in bindings),
        key=lambda row: row["handle"],
    )
    if any(
        row["handle"]
        != _mint_handle(workspace, row["source_owner"], row["source_ref"])
        for row in normalized
    ):
        raise RecallHandleWorkspaceError("RECALL_HANDLE_NOT_MINTED_FOR_SOURCE")
    handles = [row["handle"] for row in normalized]
    if len(handles) != len(set(handles)):
        raise RecallHandleWorkspaceError("RECALL_REGISTER_HANDLE_DUPLICATE")
    request_sha = _sha256({"bindings": normalized})
    state = _read_registry_state(workspace)
    registry = copy.deepcopy(state["payload"])
    existing_operation = next(
        (
            row
            for row in registry["operations"]
            if row["operation_id"] == operation_id
        ),
        None,
    )
    if existing_operation is not None:
        if existing_operation["request_sha256"] != request_sha:
            raise OperationConflictError(
                "OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST"
            )
        operation_index = registry["operations"].index(existing_operation)
        parent_version = existing_operation["parent_version"]
        replay_operations = copy.deepcopy(
            registry["operations"][: operation_index + 1]
        )
        replay_handles = {
            handle
            for operation in replay_operations
            for handle in operation["handles"]
        }
        registry = _registry(
            {
                "schema_version": REGISTRY_SCHEMA_VERSION,
                "bindings": [
                    copy.deepcopy(row)
                    for row in registry["bindings"]
                    if row["handle"] in replay_handles
                ],
                "operations": replay_operations,
            }
        )
    else:
        if expected_registry_version != state["version"]:
            raise VersionConflictError("VERSION_CONFLICT")
        parent_version = state["version"]
        existing_handles = {row["handle"] for row in registry["bindings"]}
        if existing_handles.intersection(handles):
            raise RecallHandleWorkspaceError("RECALL_HANDLE_ALREADY_REGISTERED")
        before_sources = {
            row["handle"]: _validate_current_source(workspace, row)
            for row in normalized
        }
        after_sources = {
            row["handle"]: _validate_current_source(workspace, row)
            for row in normalized
        }
        if before_sources != after_sources:
            raise RecallHandleStaleError("RECALL_SOURCE_CHANGED_DURING_REGISTER")
        registry["bindings"].extend(copy.deepcopy(normalized))
        registry["bindings"].sort(key=lambda row: row["handle"])
        registry["operations"].append(
            {
                "operation_id": operation_id,
                "parent_version": parent_version,
                "request_sha256": request_sha,
                "handles": handles,
            }
        )
        registry = _registry(registry)

    return workspace.commit(
        operation_id,
        {LOGICAL_KEY: registry},
        {LOGICAL_KEY: parent_version},
    )


def resolve_handle(
    workspace: AuthorWorkspace,
    handle: str,
) -> dict[str, Any]:
    """内部调试／机器预检：确认 handle 及其来源逻辑快照仍 current。"""
    workspace = _require_workspace(workspace)
    handle = _handle(handle)
    state_before = _read_registry_state(workspace)
    binding = next(
        (row for row in state_before["payload"]["bindings"] if row["handle"] == handle),
        None,
    )
    if binding is None:
        raise RecallHandleNotFoundError("RECALL_HANDLE_NOT_FOUND")
    source_before = _validate_current_source(workspace, binding)
    state_after = _read_registry_state(workspace)
    binding_after = next(
        (row for row in state_after["payload"]["bindings"] if row["handle"] == handle),
        None,
    )
    if binding_after != binding:
        raise RecallHandleStaleError("RECALL_HANDLE_CHANGED_DURING_RESOLVE")
    source_after = _validate_current_source(workspace, binding_after)
    if (
        state_before["version"],
        state_before["sha256"],
        source_before,
    ) != (
        state_after["version"],
        state_after["sha256"],
        source_after,
    ):
        raise RecallHandleStaleError("RECALL_HANDLE_CHANGED_DURING_RESOLVE")
    return copy.deepcopy(binding_after)


def read_registry(workspace: AuthorWorkspace) -> dict[str, Any]:
    workspace = _require_workspace(workspace)
    state = _read_registry_state(workspace)
    return {
        "version": state["version"],
        "sha256": state["sha256"],
        "bindings": copy.deepcopy(state["payload"]["bindings"]),
    }


__all__ = [
    "RecallHandleNotFoundError",
    "RecallHandleStaleError",
    "RecallHandleWorkspaceError",
    "build_binding",
    "read_registry",
    "register_bindings",
    "resolve_handle",
]
