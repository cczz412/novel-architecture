"""十本固定账户籍到 AuthorWorkspace 的最小持久化适配器。

长期状态只保存固定身份和顺序。能力、内容与路由建议由调用方在读取时显式提供，
再交给独立目录工具校验和排列；本模块不创建任何具体账本。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from . import ledger_directory_tool
from .workspace import AuthorWorkspace


LOGICAL_KEY = "ledger_directory"
REGISTRATION_SCHEMA = "author-ledger-directory-registration-v1"
REGISTRATION_IDENTITY = "AUTHOR_LEDGER_DIRECTORY_REGISTRATION_R01"
REGISTRATION_PAYLOAD_KEYS = frozenset(
    {"schema", "directory_identity", "ledger_names"}
)
STATE_KEYS = frozenset({"logical_key", "version", "sha256", "payload"})
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class LedgerDirectoryWorkspaceError(RuntimeError):
    """十账户籍未初始化、损坏或读取期间发生变化。"""


def _fail(code: str) -> None:
    raise LedgerDirectoryWorkspaceError(code)


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
        raise LedgerDirectoryWorkspaceError(
            "DIRECTORY_REGISTRATION_NOT_JSON_SERIALIZABLE"
        ) from exc
    return (text + "\n").encode("utf-8")


def _registration_payload() -> dict[str, Any]:
    return {
        "schema": REGISTRATION_SCHEMA,
        "directory_identity": REGISTRATION_IDENTITY,
        "ledger_names": list(ledger_directory_tool.FIXED_LEDGER_NAMES),
    }


def _validated_registration_payload(value: object) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != REGISTRATION_PAYLOAD_KEYS
        or value.get("schema") != REGISTRATION_SCHEMA
        or value.get("directory_identity") != REGISTRATION_IDENTITY
        or value.get("ledger_names")
        != list(ledger_directory_tool.FIXED_LEDGER_NAMES)
    ):
        _fail("DIRECTORY_REGISTRATION_INVALID")
    return copy.deepcopy(value)


def _validated_registration_state(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != STATE_KEYS:
        _fail("DIRECTORY_STATE_INVALID")
    version = value.get("version")
    sha256 = value.get("sha256")
    payload = _validated_registration_payload(value.get("payload"))
    if (
        value.get("logical_key") != LOGICAL_KEY
        or isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
        or not isinstance(sha256, str)
        or SHA256_RE.fullmatch(sha256) is None
        or hashlib.sha256(_canonical_bytes(payload)).hexdigest() != sha256
    ):
        _fail("DIRECTORY_STATE_INVALID")
    return {
        "logical_key": LOGICAL_KEY,
        "version": version,
        "sha256": sha256,
        "payload": payload,
    }


def _validated_capability_view(capability_snapshot: object) -> dict[str, Any]:
    try:
        view = ledger_directory_tool.execute(capability_snapshot)
    except ledger_directory_tool.LedgerDirectoryError as exc:
        raise LedgerDirectoryWorkspaceError(
            f"CAPABILITY_SNAPSHOT_INVALID:{exc}"
        ) from exc
    for ledger in view["ledgers"]:
        if (
            ledger["capability_status"] != "REUSABLE_STORAGE_AVAILABLE"
            and ledger["content_status"] != "UNKNOWN"
        ):
            _fail(f"UNAVAILABLE_LEDGER_CONTENT_MUST_BE_UNKNOWN:{ledger['ledger_name']}")
    return copy.deepcopy(view)


def initialize_directory(
    workspace: AuthorWorkspace,
    operation_id: str,
    expected_version: int = 0,
) -> dict[str, Any]:
    """显式登记固定十账户籍；读取入口永远不会调用本函数。"""
    handle = _require_workspace(workspace)
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version < 0
    ):
        _fail("DIRECTORY_EXPECTED_VERSION_INVALID")
    receipt = handle.commit(
        operation_id,
        {LOGICAL_KEY: _registration_payload()},
        {LOGICAL_KEY: expected_version},
    )
    return {
        "status": receipt["status"],
        "operation_id": receipt["operation_id"],
        "version": receipt["versions"][LOGICAL_KEY],
        "sha256": receipt["payload_sha256"][LOGICAL_KEY],
        "generation_id": receipt["generation_id"],
        "replayed": receipt["replayed"],
    }


def read_directory(
    workspace: AuthorWorkspace,
    capability_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """只读固定户籍并临时叠加当前能力快照，前后水位变化则整批拒绝。"""
    handle = _require_workspace(workspace)
    raw_before = handle.read(LOGICAL_KEY)
    if raw_before is None:
        _fail("DIRECTORY_NOT_INITIALIZED")
    before = _validated_registration_state(raw_before)
    view = _validated_capability_view(capability_snapshot)
    if view["ledgers"] and [
        ledger["ledger_name"] for ledger in view["ledgers"]
    ] != before["payload"]["ledger_names"]:
        _fail("CAPABILITY_SNAPSHOT_LEDGER_IDENTITY_MISMATCH")

    raw_after = handle.read(LOGICAL_KEY)
    if raw_after is None:
        _fail("DIRECTORY_CHANGED_DURING_READ")
    after = _validated_registration_state(raw_after)
    if (after["version"], after["sha256"]) != (
        before["version"],
        before["sha256"],
    ):
        _fail("DIRECTORY_CHANGED_DURING_READ")

    return {
        "registration": {
            "identity": before["payload"]["directory_identity"],
            "version": before["version"],
            "sha256": before["sha256"],
            "ledger_names": copy.deepcopy(before["payload"]["ledger_names"]),
        },
        "directory_view": copy.deepcopy(view),
    }
