"""把作者对 current T14 unknown finding 的首次裁决保存回结果 owner。

原模型 judgment 永远保持 ``unknown``。本模块只在 parent result、工作稿与
章槽仍 current 时，向该结果的 ``unknown_overlays`` 追加正式 receipt。
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, NoReturn

from . import plan_workspace, writing_check_result_tool, writing_check_result_workspace
from .workspace import OPERATION_ID_RE, AuthorWorkspace


ACTION_KEYS = {
    "contract",
    "version",
    "operation_id",
    "actor",
    "check_result_ref",
    "finding_ref",
    "work_ref",
    "work_rev",
    "source_outline_ref",
    "source_commit_seq",
    "decision",
}
DECISIONS = {"covered", "missing", "mismatch"}
ZERO_EFFECTS = {
    "check_result": "unchanged_unknown",
    "work_draft": "none",
    "plan": "none",
    "facts": "none",
    "handover": "none",
}


class WritingCheckUnknownAdjudicationWorkspaceError(RuntimeError):
    """作者裁决不属于 current unknown，或保存过程失去稳定来源。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise WritingCheckUnknownAdjudicationWorkspaceError(code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _reference(value: object, code: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        _fail(code)
    return value


def _positive_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail(code)
    return value


def _non_negative_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(code)
    return value


def _validated_action(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != ACTION_KEYS:
        _fail("UNKNOWN_ADJUDICATION_ACTION_INVALID")
    operation_id = value.get("operation_id")
    if (
        value.get("contract")
        != "WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION"
        or value.get("version") != "v1"
        or not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
        or value.get("actor") != "author"
        or value.get("decision") not in DECISIONS
    ):
        _fail("UNKNOWN_ADJUDICATION_ACTION_INVALID")
    action = copy.deepcopy(value)
    action["check_result_ref"] = _reference(
        value["check_result_ref"],
        "CHECK_RESULT_REF_INVALID",
    )
    action["finding_ref"] = _reference(value["finding_ref"], "FINDING_REF_INVALID")
    action["work_ref"] = _reference(value["work_ref"], "WORK_REF_INVALID")
    action["work_rev"] = _positive_int(value["work_rev"], "WORK_REV_INVALID")
    action["source_outline_ref"] = _reference(
        value["source_outline_ref"],
        "SOURCE_OUTLINE_REF_INVALID",
    )
    action["source_commit_seq"] = _non_negative_int(
        value["source_commit_seq"],
        "SOURCE_COMMIT_SEQ_INVALID",
    )
    return action


def _canonical_bytes(value: object) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise WritingCheckUnknownAdjudicationWorkspaceError(
            "ACTION_NOT_CANONICAL_JSON"
        ) from exc
    return (text + "\n").encode("utf-8")


def _internal_operation_id(action: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_bytes(action)).hexdigest()[:32]
    return f"t14-unknown-adjudication-{digest}"


def _receipt(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract": "WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_RECEIPT",
        "version": "v1",
        "adjudication_ref": (
            f"{action['finding_ref']}#adjudication-{action['operation_id']}"
        ),
        "operation_id": action["operation_id"],
        "actor": "author",
        "check_result_ref": action["check_result_ref"],
        "finding_ref": action["finding_ref"],
        "decision": action["decision"],
        "basis": "self_reported",
        "status": "recorded",
    }


def _store(workspace: AuthorWorkspace) -> dict[str, Any]:
    try:
        loaded = writing_check_result_workspace._read_store_entry(workspace)
    except writing_check_result_workspace.WritingCheckResultWorkspaceError as exc:
        raise WritingCheckUnknownAdjudicationWorkspaceError(
            "WRITING_CHECK_RESULTS_STORE_INVALID"
        ) from exc
    if loaded is None:
        _fail("CHECK_RESULT_REF_NOT_FOUND")
    return loaded


def _unknown_judgments(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for judgment in result["judgments"]:
        if judgment["category"] != "unknown":
            continue
        finding_ref = writing_check_result_tool.finding_ref(
            result["check_result_ref"],
            judgment,
        )
        if finding_ref in rows:
            _fail("UNKNOWN_FINDING_REF_COLLISION")
        rows[finding_ref] = copy.deepcopy(judgment)
    return rows


def _action_from_receipt(
    result: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract": "WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION",
        "version": "v1",
        "operation_id": receipt["operation_id"],
        "actor": "author",
        "check_result_ref": result["check_result_ref"],
        "finding_ref": receipt["finding_ref"],
        "work_ref": result["work_ref"],
        "work_rev": result["work_rev"],
        "source_outline_ref": result["source_outline_ref"],
        "source_commit_seq": result["source_commit_seq"],
        "decision": receipt["decision"],
    }


def _find_operation(
    store: dict[str, Any],
    operation_id: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    found: tuple[dict[str, Any], dict[str, Any]] | None = None
    for entry in store["payload"]["results"].values():
        for receipt in entry["unknown_overlays"]:
            if receipt["operation_id"] != operation_id:
                continue
            if found is not None:
                _fail("UNKNOWN_ADJUDICATION_OPERATION_DUPLICATE")
            found = (entry["result"], receipt)
    return found


def _validate_action_against_result(
    action: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    if (
        action["check_result_ref"] != result["check_result_ref"]
        or action["work_ref"] != result["work_ref"]
        or action["work_rev"] != result["work_rev"]
        or action["source_outline_ref"] != result["source_outline_ref"]
        or action["source_commit_seq"] != result["source_commit_seq"]
    ):
        _fail("UNKNOWN_ADJUDICATION_PARENT_MISMATCH")
    judgment = _unknown_judgments(result).get(action["finding_ref"])
    if judgment is None:
        _fail("UNKNOWN_FINDING_NOT_FOUND")
    return judgment


def _result_payload(
    entry: dict[str, Any],
    receipt: dict[str, Any],
    judgment: dict[str, Any],
    *,
    replayed: bool,
) -> dict[str, Any]:
    return {
        "status": "RECORDED",
        "replayed": replayed,
        "receipt": copy.deepcopy(receipt),
        "parent_result_sha256": entry["result_sha256"],
        "writing_check_results_snapshot": {
            "version": entry["version"],
            "sha256": entry["sha256"],
        },
        "evidence_text_kind": writing_check_result_tool.evidence_text_kind(
            judgment
        ),
        "effects": copy.deepcopy(ZERO_EFFECTS),
    }


def record_unknown_adjudication(
    workspace: AuthorWorkspace,
    action: dict[str, Any],
) -> dict[str, Any]:
    """保存作者首次裁决；同动作精确重放，不改原 unknown judgment。"""
    handle = _require_workspace(workspace)
    normalized = _validated_action(action)
    expected_receipt = _receipt(normalized)
    initial_store = _store(handle)
    replay = _find_operation(initial_store, normalized["operation_id"])
    if replay is not None:
        replay_result, replay_receipt = replay
        if (
            _action_from_receipt(replay_result, replay_receipt) != normalized
            or replay_receipt != expected_receipt
        ):
            _fail("OPERATION_ID_REUSED_WITH_DIFFERENT_ACTION")
        judgment = _validate_action_against_result(normalized, replay_result)
        return _result_payload(
            {
                "result_sha256": writing_check_result_workspace._canonical_result_sha(
                    replay_result
                ),
                "version": initial_store["version"],
                "sha256": initial_store["sha256"],
            },
            replay_receipt,
            judgment,
            replayed=True,
        )

    try:
        current = writing_check_result_workspace.resolve_current_writing_check_result_entry(
            handle,
            normalized["check_result_ref"],
        )
    except writing_check_result_workspace.WritingCheckResultWorkspaceError as exc:
        raise WritingCheckUnknownAdjudicationWorkspaceError(
            f"CURRENT_CHECK_RESULT_REJECTED:{exc}"
        ) from exc
    judgment = _validate_action_against_result(normalized, current["result"])
    if any(
        overlay["finding_ref"] == normalized["finding_ref"]
        for overlay in current["unknown_overlays"]
    ):
        _fail("UNKNOWN_FINDING_ALREADY_ADJUDICATED")

    latest = _store(handle)
    if (latest["version"], latest["sha256"]) != (
        current["version"],
        current["sha256"],
    ):
        _fail("WRITING_CHECK_RESULTS_CHANGED_BEFORE_COMMIT")
    if _find_operation(latest, normalized["operation_id"]) is not None:
        _fail("WRITING_CHECK_RESULTS_CHANGED_BEFORE_COMMIT")
    store_payload = copy.deepcopy(latest["payload"])
    target = store_payload["results"].get(normalized["check_result_ref"])
    if target is None or target["result_sha256"] != current["result_sha256"]:
        _fail("WRITING_CHECK_RESULTS_CHANGED_BEFORE_COMMIT")
    if any(
        overlay["finding_ref"] == normalized["finding_ref"]
        for overlay in target["unknown_overlays"]
    ):
        _fail("UNKNOWN_FINDING_ALREADY_ADJUDICATED")
    target["unknown_overlays"].append(expected_receipt)
    store_payload = writing_check_result_workspace._validated_store(store_payload)

    slot = current["chapter_slot_snapshot"]
    commit = handle.commit_guarded(
        _internal_operation_id(normalized),
        {writing_check_result_workspace.LOGICAL_KEY: store_payload},
        {
            writing_check_result_workspace.LOGICAL_KEY: {
                "version": latest["version"],
                "sha256": latest["sha256"],
            }
        },
        {
            "draft": copy.deepcopy(current["draft_workspace"]),
            plan_workspace.PLAN_LOGICAL_KEY: {
                "version": slot["source_plan_version"],
                "sha256": slot["source_plan_sha256"],
            },
        },
    )
    after = writing_check_result_workspace.resolve_writing_check_result_entry(
        handle,
        normalized["check_result_ref"],
    )
    matches = [
        overlay
        for overlay in after["unknown_overlays"]
        if overlay["operation_id"] == normalized["operation_id"]
    ]
    if len(matches) != 1 or matches[0] != expected_receipt:
        _fail("UNKNOWN_ADJUDICATION_NOT_FOUND_AFTER_COMMIT")
    return _result_payload(
        after,
        matches[0],
        judgment,
        replayed=commit["replayed"],
    )


__all__ = [
    "WritingCheckUnknownAdjudicationWorkspaceError",
    "record_unknown_adjudication",
]
