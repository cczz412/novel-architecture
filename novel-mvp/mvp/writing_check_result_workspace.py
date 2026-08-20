"""把正式 WRITING_DESK_CHECK_RESULT v1 追加进唯一本地 owner，并按 ref 读回。

调用方只能交已绑定的 AuthorWorkspace。本模块在写入前用现役结果工具
重生成并逐字段核对，再把结果追加到逻辑键 writing_check_results。
它不计算 current／stale，不解释 completed，也不做 full_check。
"""

from __future__ import annotations

import copy
from typing import Any, NoReturn

from . import writing_check_result_tool
from .workspace import AuthorWorkspace


LOGICAL_KEY = "writing_check_results"
STORE_SCHEMA = "writing-check-results-v1"
STORE_KEYS = {"schema", "results"}
ENTRY_KEYS = {"result", "result_sha256", "unknown_overlays"}
WORKSPACE_ENTRY_KEYS = {"logical_key", "version", "sha256", "payload"}


class WritingCheckResultWorkspaceError(writing_check_result_tool.WritingCheckResultError):
    """检测结果 owner 或 resolver 拒绝了非句柄、冲突或损坏内容。"""


def _fail(code: str) -> NoReturn:
    raise WritingCheckResultWorkspaceError(code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _canonical_result_sha(result: dict[str, Any]) -> str:
    return writing_check_result_tool._sha256(
        writing_check_result_tool._canonical_bytes(result)
    )


def _empty_store() -> dict[str, Any]:
    return {"schema": STORE_SCHEMA, "results": {}}


def _validated_stored_result(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("RESULTS_STORE_INVALID")
    candidate = copy.deepcopy(value)
    try:
        writing_check_result_tool._validate_result_shape(candidate)
    except writing_check_result_tool.WritingCheckResultError as exc:
        raise WritingCheckResultWorkspaceError("RESULTS_STORE_INVALID") from exc
    return candidate


def _validated_entry(value: object, *, check_result_ref: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != ENTRY_KEYS:
        _fail("RESULTS_STORE_INVALID")
    result = _validated_stored_result(value.get("result"))
    if result["check_result_ref"] != check_result_ref:
        _fail("RESULTS_STORE_INVALID")
    result_sha256 = value.get("result_sha256")
    if (
        not isinstance(result_sha256, str)
        or writing_check_result_tool.SHA256_RE.fullmatch(result_sha256) is None
        or result_sha256 != _canonical_result_sha(result)
    ):
        _fail("RESULTS_STORE_INVALID")
    overlays = value.get("unknown_overlays")
    if not isinstance(overlays, list):
        _fail("RESULTS_STORE_INVALID")
    return {
        "result": result,
        "result_sha256": result_sha256,
        "unknown_overlays": copy.deepcopy(overlays),
    }


def _validated_store(value: object) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != STORE_KEYS
        or value.get("schema") != STORE_SCHEMA
        or not isinstance(value.get("results"), dict)
    ):
        _fail("RESULTS_STORE_INVALID")
    results: dict[str, dict[str, Any]] = {}
    for raw_ref, raw_entry in value["results"].items():
        if not isinstance(raw_ref, str) or not raw_ref:
            _fail("RESULTS_STORE_INVALID")
        results[raw_ref] = _validated_entry(raw_entry, check_result_ref=raw_ref)
    return {"schema": STORE_SCHEMA, "results": results}


def _validated_workspace_entry(entry: object) -> dict[str, Any]:
    if (
        not isinstance(entry, dict)
        or set(entry) != WORKSPACE_ENTRY_KEYS
        or entry.get("logical_key") != LOGICAL_KEY
        or not isinstance(entry.get("version"), int)
        or isinstance(entry.get("version"), bool)
        or entry["version"] < 1
        or not isinstance(entry.get("sha256"), str)
        or writing_check_result_tool.SHA256_RE.fullmatch(entry["sha256"]) is None
    ):
        _fail("RESULTS_WORKSPACE_ENTRY_INVALID")
    store = _validated_store(entry.get("payload"))
    return {
        "version": entry["version"],
        "sha256": entry["sha256"],
        "payload": store,
    }


def _read_store_entry(workspace: AuthorWorkspace) -> dict[str, Any] | None:
    entry = workspace.read(LOGICAL_KEY)
    if entry is None:
        return None
    return _validated_workspace_entry(entry)


def _commit_expectation(
    expected_version: int,
    expected_sha256: str | None,
) -> Any:
    if expected_sha256 is None:
        return expected_version
    return {"version": expected_version, "sha256": expected_sha256}


def _regenerate_formal_result(
    input_package: object,
    result: object,
) -> dict[str, Any]:
    if not isinstance(result, dict) or "judgments" not in result:
        _fail("CALLER_RESULT_INVALID")
    regenerated = writing_check_result_tool.execute(
        {
            "input_package": copy.deepcopy(input_package),
            "provider_response": {
                "judgments": copy.deepcopy(result["judgments"]),
            },
        }
    )
    if regenerated != result:
        _fail("CALLER_RESULT_MISMATCH")
    return regenerated


def save_writing_check_result(
    workspace: AuthorWorkspace,
    operation_id: str,
    input_package: dict[str, Any],
    result: dict[str, Any],
    expected_version: int,
    expected_sha256: str | None,
) -> dict[str, Any]:
    """重生成正式结果并追加到唯一 owner；同 ref 同内容走现有幂等，异内容拒绝。"""

    handle = _require_workspace(workspace)
    formal = _regenerate_formal_result(input_package, result)
    if operation_id != formal["operation_id"]:
        _fail("OPERATION_ID_MISMATCH")
    check_result_ref = formal["check_result_ref"]
    new_entry = {
        "result": copy.deepcopy(formal),
        "result_sha256": _canonical_result_sha(formal),
        "unknown_overlays": [],
    }

    loaded = _read_store_entry(handle)
    store = _empty_store() if loaded is None else copy.deepcopy(loaded["payload"])
    existing = store["results"].get(check_result_ref)
    if existing is not None and existing != new_entry:
        _fail("CHECK_RESULT_REF_CONFLICT")
    store["results"][check_result_ref] = new_entry
    return handle.commit(
        operation_id,
        {LOGICAL_KEY: store},
        {LOGICAL_KEY: _commit_expectation(expected_version, expected_sha256)},
    )


def resolve_writing_check_result(
    workspace: AuthorWorkspace,
    check_result_ref: str,
) -> dict[str, Any]:
    """只按绑定 workspace 中的完整 ref 读回深拷贝正式结果；不宣称 CURRENT。"""

    handle = _require_workspace(workspace)
    if not isinstance(check_result_ref, str) or not check_result_ref:
        _fail("CHECK_RESULT_REF_INVALID")
    loaded = _read_store_entry(handle)
    if loaded is None:
        _fail("CHECK_RESULT_REF_NOT_FOUND")
    entry = loaded["payload"]["results"].get(check_result_ref)
    if entry is None:
        _fail("CHECK_RESULT_REF_NOT_FOUND")
    return {
        "result": copy.deepcopy(entry["result"]),
        "result_sha256": entry["result_sha256"],
        "version": loaded["version"],
        "sha256": loaded["sha256"],
    }


__all__ = [
    "WritingCheckResultWorkspaceError",
    "resolve_writing_check_result",
    "save_writing_check_result",
]
