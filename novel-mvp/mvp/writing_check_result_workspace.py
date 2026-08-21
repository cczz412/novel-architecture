"""把正式 WRITING_DESK_CHECK_RESULT v1 追加进唯一本地 owner，并按 ref 读回。

调用方只能交已绑定的 AuthorWorkspace。本模块在写入前用现役结果工具
重生成并逐字段核对，再把结果追加到逻辑键 writing_check_results。
它不计算 current／stale，不解释 completed，也不做 full_check。
"""

from __future__ import annotations

import copy
from typing import Any, NoReturn

from . import (
    chapter_slot_snapshot_tool,
    chapter_slot_workspace,
    work_draft_workspace,
    writing_check_package_tool,
    writing_check_result_tool,
)
from .workspace import OPERATION_ID_RE, AuthorWorkspace


LOGICAL_KEY = "writing_check_results"
STORE_SCHEMA = "writing-check-results-v1"
STORE_KEYS = {"schema", "results"}
ENTRY_KEYS = {"result", "result_sha256", "unknown_overlays"}
WORKSPACE_ENTRY_KEYS = {"logical_key", "version", "sha256", "payload"}
UNKNOWN_ADJUDICATION_RECEIPT_KEYS = {
    "contract",
    "version",
    "adjudication_ref",
    "operation_id",
    "actor",
    "check_result_ref",
    "finding_ref",
    "decision",
    "basis",
    "status",
}
UNKNOWN_ADJUDICATION_DECISIONS = {"covered", "missing", "mismatch"}


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


def _validated_unknown_overlay(
    value: object,
    *,
    check_result_ref: str,
    unknown_finding_refs: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != UNKNOWN_ADJUDICATION_RECEIPT_KEYS:
        _fail("UNKNOWN_ADJUDICATION_RECEIPT_INVALID")
    operation_id = value.get("operation_id")
    finding_ref = value.get("finding_ref")
    if (
        value.get("contract")
        != "WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_RECEIPT"
        or value.get("version") != "v1"
        or not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
        or value.get("actor") != "author"
        or value.get("check_result_ref") != check_result_ref
        or not isinstance(finding_ref, str)
        or finding_ref not in unknown_finding_refs
        or value.get("decision") not in UNKNOWN_ADJUDICATION_DECISIONS
        or value.get("basis") != "self_reported"
        or value.get("status") != "recorded"
        or value.get("adjudication_ref")
        != f"{finding_ref}#adjudication-{operation_id}"
    ):
        _fail("UNKNOWN_ADJUDICATION_RECEIPT_INVALID")
    return copy.deepcopy(value)


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
    unknown_finding_refs = {
        writing_check_result_tool.finding_ref(check_result_ref, judgment)
        for judgment in result["judgments"]
        if judgment["category"] == "unknown"
    }
    validated_overlays = [
        _validated_unknown_overlay(
            overlay,
            check_result_ref=check_result_ref,
            unknown_finding_refs=unknown_finding_refs,
        )
        for overlay in overlays
    ]
    operation_ids = [overlay["operation_id"] for overlay in validated_overlays]
    finding_refs = [overlay["finding_ref"] for overlay in validated_overlays]
    if (
        len(operation_ids) != len(set(operation_ids))
        or len(finding_refs) != len(set(finding_refs))
    ):
        _fail("UNKNOWN_ADJUDICATION_RECEIPT_DUPLICATE")
    return {
        "result": result,
        "result_sha256": result_sha256,
        "unknown_overlays": validated_overlays,
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
    operation_ids = [
        overlay["operation_id"]
        for entry in results.values()
        for overlay in entry["unknown_overlays"]
    ]
    if len(operation_ids) != len(set(operation_ids)):
        _fail("UNKNOWN_ADJUDICATION_OPERATION_ID_DUPLICATE")
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


def _read_current_draft(workspace: AuthorWorkspace) -> dict[str, Any]:
    try:
        current = work_draft_workspace.read_current_work_draft(workspace)
    except work_draft_workspace.WorkDraftWorkspaceError as exc:
        raise WritingCheckResultWorkspaceError("CURRENT_WORK_DRAFT_INVALID") from exc
    if current.get("status") != "READY" or current.get("current_work_draft") is None:
        _fail("CURRENT_WORK_DRAFT_REQUIRED")
    return current


def _read_current_slot(
    workspace: AuthorWorkspace,
    slot_ref: str,
) -> dict[str, Any]:
    try:
        return chapter_slot_workspace.execute(workspace, slot_ref)
    except (
        chapter_slot_workspace.ChapterSlotWorkspaceError,
        chapter_slot_snapshot_tool.ChapterSlotSnapshotError,
    ) as exc:
        raise WritingCheckResultWorkspaceError("CURRENT_CHAPTER_SLOT_INVALID") from exc


def _assert_result_is_current(
    entry: dict[str, Any],
    current_draft: dict[str, Any],
    slot: dict[str, Any],
) -> None:
    result = entry["result"]
    draft = current_draft["current_work_draft"]
    if (
        result["status"] != "completed"
        or result["slot_ref"] != draft["slot_ref"]
        or result["work_ref"] != draft["work_ref"]
        or result["work_rev"] != draft["work_rev"]
        or result["work_text_sha256"] != draft["text_sha256"]
        or result["source_outline_ref"] != draft["source_outline_ref"]
        or result["slot_ref"] != slot["slot_ref"]
        or result["source_commit_seq"]
        != slot["outline_checkpoint"]["source_commit_seq"]
    ):
        _fail("WRITING_CHECK_RESULT_NOT_CURRENT")
    try:
        package = writing_check_package_tool.execute(
            {
                "work_draft": copy.deepcopy(draft),
                "chapter_slot_snapshot": copy.deepcopy(slot),
                "check_operation_id": result["operation_id"],
            }
        )
        rebuilt = writing_check_result_tool.execute(
            {
                "input_package": package,
                "provider_response": {
                    "judgments": copy.deepcopy(result["judgments"]),
                },
            }
        )
    except (
        writing_check_package_tool.WritingCheckPackageError,
        writing_check_result_tool.WritingCheckResultError,
    ) as exc:
        raise WritingCheckResultWorkspaceError(
            "WRITING_CHECK_RESULT_NOT_CURRENT"
        ) from exc
    if rebuilt != result:
        _fail("WRITING_CHECK_RESULT_NOT_CURRENT")


def resolve_current_writing_check_result_entry(
    workspace: AuthorWorkspace,
    check_result_ref: str,
) -> dict[str, Any]:
    """稳定复核 result、工作稿和章槽仍 current；不产生写入。"""
    handle = _require_workspace(workspace)
    first_entry = resolve_writing_check_result_entry(handle, check_result_ref)
    first_draft = _read_current_draft(handle)
    second_draft = _read_current_draft(handle)
    if first_draft != second_draft:
        _fail("WORK_DRAFT_CHANGED_DURING_RESULT_READ")
    draft = second_draft["current_work_draft"]
    first_slot = _read_current_slot(handle, draft["slot_ref"])
    second_slot = _read_current_slot(handle, draft["slot_ref"])
    if first_slot != second_slot:
        _fail("CHAPTER_SLOT_CHANGED_DURING_RESULT_READ")
    _assert_result_is_current(first_entry, second_draft, second_slot)

    second_entry = resolve_writing_check_result_entry(handle, check_result_ref)
    draft_after = _read_current_draft(handle)
    slot_after = _read_current_slot(handle, draft["slot_ref"])
    if second_entry != first_entry:
        _fail("CHECK_RESULT_OWNER_CHANGED_DURING_RESULT_READ")
    if draft_after != second_draft:
        _fail("WORK_DRAFT_CHANGED_DURING_RESULT_READ")
    if slot_after != second_slot:
        _fail("CHAPTER_SLOT_CHANGED_DURING_RESULT_READ")
    return {
        **copy.deepcopy(first_entry),
        "draft_workspace": copy.deepcopy(second_draft["draft_workspace"]),
        "current_work_draft": copy.deepcopy(draft),
        "chapter_slot_snapshot": copy.deepcopy(second_slot),
    }


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


def resolve_writing_check_result_entry(
    workspace: AuthorWorkspace,
    check_result_ref: str,
) -> dict[str, Any]:
    """读回完整 owner entry；不宣称 result 或 overlay 仍为 CURRENT。"""

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
        "unknown_overlays": copy.deepcopy(entry["unknown_overlays"]),
        "version": loaded["version"],
        "sha256": loaded["sha256"],
    }


def resolve_writing_check_result(
    workspace: AuthorWorkspace,
    check_result_ref: str,
) -> dict[str, Any]:
    """只按完整 ref 读回正式结果；保持旧返回形状，不宣称 CURRENT。"""
    entry = resolve_writing_check_result_entry(workspace, check_result_ref)
    return {
        "result": entry["result"],
        "result_sha256": entry["result_sha256"],
        "version": entry["version"],
        "sha256": entry["sha256"],
    }


__all__ = [
    "WritingCheckResultWorkspaceError",
    "resolve_current_writing_check_result_entry",
    "resolve_writing_check_result",
    "resolve_writing_check_result_entry",
    "save_writing_check_result",
]
