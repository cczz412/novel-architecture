"""把 AuthorWorkspace 中的 current confirmed C4 内容交给 M11 原型。

本模块只读取 ``facts`` 与 ``chapter_index``，不接路径、作者 ID、项目 ID，
也不解析通用 URI / object_ref。调用方仍显式提供 M11 的任务、预算和排序；
事实身份、真实内容、证据与有限回取句柄由本适配器从绑定工作区核验或生成。
结果只存在内存，不写任何 workspace 逻辑键。
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any, NoReturn

from . import ask_tool, fact_workspace, packer, packer_tool
from .workspace import AuthorWorkspace, SHA256_RE


PROTOTYPE_IDENTITY = "M11_CURRENT_FACT_MATERIAL_WORKSPACE_PROTOTYPE"
PROTOTYPE_VERSION = "v1"
RECALL_PROTOTYPE_IDENTITY = "M11_CURRENT_FACT_LIMITED_RECALL_PROTOTYPE"
MATERIAL_IDENTITY = "CURRENT_CONFIRMED_FACT"
RECALL_PREFIX = "c4-current://"
ADAPTER_MATERIAL_FIELDS = (
    packer.REQUIRED_MATERIAL_FIELDS - {"recall_handle"}
) | {"material_identity"}
RESULT_FIELDS = {
    "prototype",
    "workspace_binding_sha256",
    "source_snapshots",
    "decision_state",
    "m11_result",
    "loaded_facts",
    "omitted_fact_index",
    "unresolved",
    "errors",
}
LOADED_FACT_FIELDS = {"material_identity", "fact", "why_loaded"}
OMITTED_FACT_FIELDS = {
    "material_identity",
    "fact_id",
    "reason",
    "recall_disposition",
    "recall_handle",
}


class PackerFactWorkspaceError(RuntimeError):
    """M11 不能从绑定工作区形成可信的 current fact 内容包。"""


def _fail(code: str) -> NoReturn:
    raise PackerFactWorkspaceError(code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _workspace_binding(workspace: AuthorWorkspace) -> str:
    payload = (
        "m11-current-fact-workspace-v1\0"
        f"{workspace.author_id}\0{workspace.project_id}"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _source_snapshots(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "facts": copy.deepcopy(view["facts_snapshot"]),
        "chapter_index": copy.deepcopy(view["chapter_index_snapshot"]),
    }


def _read_current_view(workspace: AuthorWorkspace) -> dict[str, Any]:
    try:
        return fact_workspace.read_current_snapshot(workspace)
    except fact_workspace.FactWorkspaceError as exc:
        raise PackerFactWorkspaceError(f"CURRENT_FACT_SOURCE_INVALID:{exc}") from exc


def _eligibility_failure(fact: dict[str, Any]) -> str | None:
    status = fact.get("status")
    if status == "extracted":
        return "FACT_NOT_CONFIRMED:EXTRACTED"
    if status == "rejected":
        return "FACT_NOT_CONFIRMED:REJECTED"
    if status == "needs_recheck":
        return "FACT_NOT_CONFIRMED:NEEDS_RECHECK"
    if status != "confirmed":
        return "FACT_STATUS_INVALID"
    if fact.get("anchor_state") != "VERIFIED":
        return "FACT_EVIDENCE_NOT_VERIFIED"
    if fact.get("recheck") is not None:
        return "FACT_RECHECK_NOT_NULL"
    if not ask_tool._anchor_valid(fact):
        return "FACT_EVIDENCE_INVALID"
    return None


def _fact_indexes(
    view: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    eligible: dict[str, dict[str, Any]] = {}
    ineligible: dict[str, str] = {}
    for fact in view["facts"]:
        fact_id = fact["id"]
        failure = _eligibility_failure(fact)
        if failure is None:
            eligible[fact_id] = copy.deepcopy(fact)
        else:
            ineligible[fact_id] = failure
    return eligible, ineligible


def _recall_handle(fact_id: str) -> str:
    return f"{RECALL_PREFIX}{fact_id}"


def _effective_pack_request(
    pack_request: object,
    view: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(pack_request, dict):
        _fail("PACK_REQUEST_NOT_OBJECT")
    if set(pack_request) != packer_tool.REQUEST_FIELDS:
        _fail("PACK_REQUEST_FIELDS_INVALID")
    if pack_request.get("task_actuality_scope") != "CURRENT_TRUTH_REQUIRED":
        _fail("CURRENT_FACT_TASK_SCOPE_REQUIRED")

    raw_materials = pack_request.get("candidate_materials")
    if not isinstance(raw_materials, list) or not raw_materials:
        _fail("CURRENT_FACT_CANDIDATES_REQUIRED")
    eligible, ineligible = _fact_indexes(view)
    stale_ids = set(view["stale_fact_ids"])
    effective_materials: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_materials):
        if not isinstance(raw, dict) or set(raw) != ADAPTER_MATERIAL_FIELDS:
            _fail(f"CURRENT_FACT_CANDIDATE_FIELDS_INVALID:{index}")
        fact_id = raw.get("id")
        if not isinstance(fact_id, str) or not fact_id:
            _fail(f"CURRENT_FACT_ID_INVALID:{index}")
        if fact_id in seen_ids:
            _fail(f"CURRENT_FACT_ID_DUPLICATE:{fact_id}")
        seen_ids.add(fact_id)
        if raw.get("material_identity") != MATERIAL_IDENTITY:
            _fail(f"CURRENT_FACT_MATERIAL_IDENTITY_INVALID:{fact_id}")
        if fact_id in stale_ids:
            _fail(f"CURRENT_FACT_STALE_REVISION:{fact_id}")
        if fact_id in ineligible:
            _fail(f"CURRENT_FACT_INELIGIBLE:{fact_id}:{ineligible[fact_id]}")
        if fact_id not in eligible:
            _fail(f"CURRENT_FACT_NOT_FOUND:{fact_id}")
        if raw.get("actuality_class") not in {
            "CURRENT_FACT_OR_STATE",
            "UNRESOLVED",
        }:
            _fail(f"CURRENT_FACT_ACTUALITY_INVALID:{fact_id}")

        disposition = raw.get("recall_disposition")
        if disposition == "RETRIEVABLE":
            recall_handle: str | None = _recall_handle(fact_id)
        elif disposition == "NOT_RETRIEVABLE":
            recall_handle = None
        else:
            _fail(f"CURRENT_FACT_RECALL_DISPOSITION_INVALID:{fact_id}")
        effective = {
            key: copy.deepcopy(value)
            for key, value in raw.items()
            if key != "material_identity"
        }
        effective["recall_handle"] = recall_handle
        effective_materials.append(effective)

    effective_request = copy.deepcopy(pack_request)
    effective_request["candidate_materials"] = effective_materials
    return effective_request


def _loaded_fact_rows(
    m11_result: dict[str, Any],
    facts_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for material in m11_result["loaded"]:
        fact_id = material["id"]
        fact = facts_by_id.get(fact_id)
        if fact is None:
            _fail(f"PACKER_LOADED_FACT_NOT_ELIGIBLE:{fact_id}")
        rows.append(
            {
                "material_identity": MATERIAL_IDENTITY,
                "fact": copy.deepcopy(fact),
                "why_loaded": m11_result["why_loaded"][fact_id],
            }
        )
    return rows


def _omitted_fact_rows(m11_result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "material_identity": MATERIAL_IDENTITY,
            "fact_id": row["id"],
            "reason": row["reason"],
            "recall_disposition": row["recall_disposition"],
            "recall_handle": row["recall_handle"],
        }
        for row in m11_result["omitted"]
    ]


def execute(
    workspace: AuthorWorkspace,
    pack_request: dict[str, Any],
) -> dict[str, Any]:
    """从同一绑定工作区读取 current C4，执行 M11，并补回真实内容。"""

    handle = _require_workspace(workspace)
    current_view = _read_current_view(handle)
    effective_request = _effective_pack_request(pack_request, current_view)
    try:
        m11_result = packer_tool.execute(effective_request)
    except packer_tool.PackerToolError as exc:
        raise PackerFactWorkspaceError(f"M11_PACK_REJECTED:{exc}") from exc

    after_view = _read_current_view(handle)
    if _source_snapshots(after_view) != _source_snapshots(current_view):
        _fail("CURRENT_FACT_SOURCE_CHANGED_DURING_PACK")

    eligible, _ = _fact_indexes(current_view)
    loaded_facts = _loaded_fact_rows(m11_result, eligible)
    if m11_result["decision_state"] != "READY" and loaded_facts:
        _fail("M11_STOP_LEAKED_FACT_CONTENT")
    return {
        "prototype": {
            "identity": PROTOTYPE_IDENTITY,
            "version": PROTOTYPE_VERSION,
        },
        "workspace_binding_sha256": _workspace_binding(handle),
        "source_snapshots": _source_snapshots(current_view),
        "decision_state": m11_result["decision_state"],
        "m11_result": copy.deepcopy(m11_result),
        "loaded_facts": loaded_facts,
        "omitted_fact_index": _omitted_fact_rows(m11_result),
        "unresolved": copy.deepcopy(m11_result["unresolved"]),
        "errors": copy.deepcopy(m11_result["errors"]),
    }


def _valid_snapshot_identity(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {"version", "sha256"}:
        return False
    version = value["version"]
    sha256 = value["sha256"]
    return (
        isinstance(version, int)
        and not isinstance(version, bool)
        and version >= 0
        and (
            (version == 0 and sha256 is None)
            or (
                version > 0
                and isinstance(sha256, str)
                and SHA256_RE.fullmatch(sha256) is not None
            )
        )
    )


def _validated_pack_result(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RESULT_FIELDS:
        _fail("FACT_PACK_RESULT_FIELDS_INVALID")
    result = copy.deepcopy(value)
    if result["prototype"] != {
        "identity": PROTOTYPE_IDENTITY,
        "version": PROTOTYPE_VERSION,
    }:
        _fail("FACT_PACK_RESULT_IDENTITY_INVALID")
    binding = result["workspace_binding_sha256"]
    if not isinstance(binding, str) or SHA256_RE.fullmatch(binding) is None:
        _fail("FACT_PACK_WORKSPACE_BINDING_INVALID")
    sources = result["source_snapshots"]
    if (
        not isinstance(sources, dict)
        or set(sources) != {"facts", "chapter_index"}
        or not _valid_snapshot_identity(sources["facts"])
        or not _valid_snapshot_identity(sources["chapter_index"])
    ):
        _fail("FACT_PACK_SOURCE_SNAPSHOTS_INVALID")
    try:
        m11_result = packer_tool.validate_render_result(result["m11_result"])
    except packer_tool.PackerToolError as exc:
        raise PackerFactWorkspaceError(f"FACT_PACK_M11_RESULT_INVALID:{exc}") from exc
    if (
        result["decision_state"] != m11_result["decision_state"]
        or result["unresolved"] != m11_result["unresolved"]
        or result["errors"] != m11_result["errors"]
    ):
        _fail("FACT_PACK_M11_MIRROR_MISMATCH")

    loaded_rows = result["loaded_facts"]
    if not isinstance(loaded_rows, list) or len(loaded_rows) != len(m11_result["loaded"]):
        _fail("FACT_PACK_LOADED_FACTS_INVALID")
    for index, (row, material) in enumerate(
        zip(loaded_rows, m11_result["loaded"], strict=True)
    ):
        if not isinstance(row, dict) or set(row) != LOADED_FACT_FIELDS:
            _fail(f"FACT_PACK_LOADED_FACT_INVALID:{index}")
        fact = row["fact"]
        if (
            row["material_identity"] != MATERIAL_IDENTITY
            or not isinstance(fact, dict)
            or fact.get("id") != material["id"]
            or _eligibility_failure(fact) is not None
            or row["why_loaded"] != m11_result["why_loaded"][material["id"]]
        ):
            _fail(f"FACT_PACK_LOADED_FACT_INVALID:{index}")

    omitted_rows = result["omitted_fact_index"]
    if not isinstance(omitted_rows, list) or len(omitted_rows) != len(
        m11_result["omitted"]
    ):
        _fail("FACT_PACK_OMISSION_INDEX_INVALID")
    for index, (row, omission) in enumerate(
        zip(omitted_rows, m11_result["omitted"], strict=True)
    ):
        expected = {
            "material_identity": MATERIAL_IDENTITY,
            "fact_id": omission["id"],
            "reason": omission["reason"],
            "recall_disposition": omission["recall_disposition"],
            "recall_handle": omission["recall_handle"],
        }
        if not isinstance(row, dict) or set(row) != OMITTED_FACT_FIELDS or row != expected:
            _fail(f"FACT_PACK_OMISSION_INDEX_INVALID:{index}")
    result["m11_result"] = m11_result
    return result


def recall_omitted(
    workspace: AuthorWorkspace,
    pack_result: dict[str, Any],
    recall_handle: str,
) -> dict[str, Any]:
    """只回取同一包明确遗漏、可回取且仍绑定原水位的一条 current C4。"""

    handle = _require_workspace(workspace)
    result = _validated_pack_result(pack_result)
    if result["workspace_binding_sha256"] != _workspace_binding(handle):
        _fail("RECALL_WORKSPACE_BINDING_MISMATCH")
    if result["decision_state"] != "READY":
        _fail("RECALL_REQUIRES_READY_PACK")
    if not isinstance(recall_handle, str):
        _fail("RECALL_HANDLE_INVALID")
    matches = [
        row
        for row in result["omitted_fact_index"]
        if row["recall_disposition"] == "RETRIEVABLE"
        and row["recall_handle"] == recall_handle
    ]
    if len(matches) != 1:
        _fail("RECALL_HANDLE_NOT_IN_PACK_OMISSIONS")
    omission = matches[0]
    fact_id = omission["fact_id"]
    if recall_handle != _recall_handle(fact_id):
        _fail("RECALL_HANDLE_IDENTITY_MISMATCH")

    current_view = _read_current_view(handle)
    if _source_snapshots(current_view) != result["source_snapshots"]:
        _fail("RECALL_SOURCE_SNAPSHOT_CHANGED")
    eligible, _ = _fact_indexes(current_view)
    fact = eligible.get(fact_id)
    if fact is None:
        _fail(f"RECALL_FACT_NO_LONGER_ELIGIBLE:{fact_id}")
    return {
        "prototype": {
            "identity": RECALL_PROTOTYPE_IDENTITY,
            "version": PROTOTYPE_VERSION,
        },
        "workspace_binding_sha256": result["workspace_binding_sha256"],
        "source_snapshots": copy.deepcopy(result["source_snapshots"]),
        "material_identity": MATERIAL_IDENTITY,
        "fact_id": fact_id,
        "recall_handle": recall_handle,
        "omission_reason": omission["reason"],
        "fact": copy.deepcopy(fact),
    }


__all__ = [
    "MATERIAL_IDENTITY",
    "PackerFactWorkspaceError",
    "execute",
    "recall_omitted",
]
