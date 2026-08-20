"""AuthorWorkspace 到现役 M9 ``overview_tool`` 的只读适配层。

调用方只能交入已绑定作者与项目的 ``AuthorWorkspace`` 句柄，并显式指定
``chapter_id``、``generated_at`` 与 provider。本模块只读 ``facts`` 和
``chapter_index``，不猜当前章、不写缓存，也不改变 M9 对象核心语义。
"""

from __future__ import annotations

import copy
from typing import Any

from . import factstore, overview, overview_tool
from .workspace import AUTHOR_ID_RE, PROJECT_ID_RE, AuthorWorkspace


FACTS_LOGICAL_KEY = "facts"
CHAPTER_INDEX_LOGICAL_KEY = "chapter_index"
SAVED_RESULT_KEYS = {
    "workspace_binding",
    "facts_snapshot",
    "chapter_index_snapshot",
    "m9",
}
WORKSPACE_BINDING_KEYS = {"author_id", "project_id"}
SNAPSHOT_IDENTITY_KEYS = {"version", "sha256"}


class OverviewWorkspaceError(overview.OverviewError):
    """M9 工作区适配器拒绝了非句柄或不一致的当前快照。"""


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        raise OverviewWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _clean_string(value: object, *, reason: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise OverviewWorkspaceError(reason)
    return value


def _read_list_snapshot(
    workspace: AuthorWorkspace,
    logical_key: str,
) -> dict[str, Any]:
    entry = workspace.read(logical_key)
    if entry is None:
        raise OverviewWorkspaceError(f"{logical_key.upper()}_SNAPSHOT_MISSING")
    if (
        not isinstance(entry, dict)
        or entry.get("logical_key") != logical_key
        or not isinstance(entry.get("version"), int)
        or isinstance(entry.get("version"), bool)
        or entry["version"] < 1
        or not isinstance(entry.get("sha256"), str)
        or overview.SHA256_RE.fullmatch(entry["sha256"]) is None
        or not isinstance(entry.get("payload"), list)
    ):
        raise OverviewWorkspaceError(f"{logical_key.upper()}_WORKSPACE_ENTRY_INVALID")
    return {
        "version": entry["version"],
        "sha256": entry["sha256"],
        "payload": copy.deepcopy(entry["payload"]),
    }


def _valid_revision_ref(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == overview.REVISION_REF_KEYS
        and isinstance(value.get("chapter_id"), str)
        and bool(value["chapter_id"])
        and value["chapter_id"] == value["chapter_id"].strip()
        and isinstance(value.get("revision_no"), int)
        and not isinstance(value["revision_no"], bool)
        and value["revision_no"] >= 1
        and isinstance(value.get("revision_text_sha256"), str)
        and overview.SHA256_RE.fullmatch(value["revision_text_sha256"]) is not None
    )


def _current_revision_ref(
    chapter_index: list[Any],
    chapter_id: str,
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for index, raw_ref in enumerate(chapter_index, start=1):
        if not _valid_revision_ref(raw_ref):
            raise OverviewWorkspaceError(f"CHAPTER_INDEX_REVISION_REF_INVALID:{index}")
        if raw_ref["chapter_id"] == chapter_id:
            matches.append(raw_ref)
    if not matches:
        raise OverviewWorkspaceError(f"CURRENT_REVISION_REF_MISSING:{chapter_id}")
    if len(matches) != 1:
        raise OverviewWorkspaceError(f"CURRENT_REVISION_REF_DUPLICATE:{chapter_id}")
    return copy.deepcopy(matches[0])


def _facts_for_chapter(
    raw_facts: list[Any],
    *,
    chapter_id: str,
    current_revision_ref: dict[str, Any],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for index, raw_fact in enumerate(raw_facts, start=1):
        if not isinstance(raw_fact, dict):
            raise OverviewWorkspaceError(f"FACTS_ITEM_NOT_OBJECT:{index}")
        fact_chapter_id = raw_fact.get("chapter_id")
        if (
            not isinstance(fact_chapter_id, str)
            or not fact_chapter_id
            or fact_chapter_id != fact_chapter_id.strip()
        ):
            raise OverviewWorkspaceError(f"FACT_CHAPTER_ID_INVALID:{index}")
        if fact_chapter_id != chapter_id:
            continue
        if raw_fact.get("chapter_revision_ref") != current_revision_ref:
            fact_id = raw_fact.get("id", index)
            raise OverviewWorkspaceError(
                f"FACT_CURRENT_REVISION_REF_MISMATCH:{fact_id}"
            )
        selected.append(copy.deepcopy(raw_fact))
    return selected


def _source_revision(
    facts_snapshot: dict[str, Any],
    chapter_index_snapshot: dict[str, Any],
) -> str:
    return (
        f"author-workspace:facts:v{facts_snapshot['version']}:"
        f"{facts_snapshot['sha256']}:chapter-index:"
        f"v{chapter_index_snapshot['version']}:{chapter_index_snapshot['sha256']}"
    )


def _workspace_binding(workspace: AuthorWorkspace) -> dict[str, str]:
    return {
        "author_id": workspace.author_id,
        "project_id": workspace.project_id,
    }


def _read_validated_sources(
    workspace: AuthorWorkspace,
    chapter_id: str,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
]:
    facts_snapshot = _read_list_snapshot(workspace, FACTS_LOGICAL_KEY)
    chapter_index_snapshot = _read_list_snapshot(
        workspace,
        CHAPTER_INDEX_LOGICAL_KEY,
    )
    current_ref = _current_revision_ref(
        chapter_index_snapshot["payload"],
        chapter_id,
    )
    facts = _facts_for_chapter(
        facts_snapshot["payload"],
        chapter_id=chapter_id,
        current_revision_ref=current_ref,
    )
    return facts_snapshot, chapter_index_snapshot, current_ref, facts


def _source_watermark(
    facts_snapshot: dict[str, Any],
    chapter_index_snapshot: dict[str, Any],
) -> tuple[tuple[int, str], tuple[int, str]]:
    return (
        (facts_snapshot["version"], facts_snapshot["sha256"]),
        (
            chapter_index_snapshot["version"],
            chapter_index_snapshot["sha256"],
        ),
    )


def _snapshot_identity(value: object, *, label: str) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != SNAPSHOT_IDENTITY_KEYS
        or not isinstance(value.get("version"), int)
        or isinstance(value.get("version"), bool)
        or value["version"] < 1
        or not isinstance(value.get("sha256"), str)
        or overview.SHA256_RE.fullmatch(value["sha256"]) is None
    ):
        raise OverviewWorkspaceError(f"SAVED_{label}_IDENTITY_INVALID")
    return copy.deepcopy(value)


def _saved_basis(saved_result: object) -> dict[str, Any]:
    if not isinstance(saved_result, dict) or set(saved_result) != SAVED_RESULT_KEYS:
        raise OverviewWorkspaceError("SAVED_RESULT_SHAPE_INVALID")
    binding = saved_result["workspace_binding"]
    if (
        not isinstance(binding, dict)
        or set(binding) != WORKSPACE_BINDING_KEYS
        or not isinstance(binding.get("author_id"), str)
        or AUTHOR_ID_RE.fullmatch(binding["author_id"]) is None
        or not isinstance(binding.get("project_id"), str)
        or PROJECT_ID_RE.fullmatch(binding["project_id"]) is None
    ):
        raise OverviewWorkspaceError("SAVED_WORKSPACE_BINDING_INVALID")
    facts_identity = _snapshot_identity(
        saved_result["facts_snapshot"],
        label="FACTS_SNAPSHOT",
    )
    index_identity = _snapshot_identity(
        saved_result["chapter_index_snapshot"],
        label="CHAPTER_INDEX_SNAPSHOT",
    )
    m9 = saved_result["m9"]
    if (
        not isinstance(m9, dict)
        or m9.get("contract") != overview.OUTPUT_CONTRACT
        or m9.get("version") != overview.OUTPUT_VERSION
        or m9.get("projection_only") is not True
        or m9.get("writes_truth") is not False
        or m9.get("basis") != "fact_snapshot"
        or not _valid_revision_ref(m9.get("chapter_revision_ref"))
    ):
        raise OverviewWorkspaceError("SAVED_M9_PROTOTYPE_IDENTITY_INVALID")
    chapter_ref = m9["chapter_revision_ref"]
    source_summary = m9.get("source_summary")
    if (
        m9.get("chapter_ref") != chapter_ref["chapter_id"]
        or not isinstance(source_summary, dict)
        or source_summary.get("chapter_revision_ref") != chapter_ref
        or source_summary.get("source_revision")
        != _source_revision(facts_identity, index_identity)
        or not isinstance(source_summary.get("source_facts_sha256"), str)
        or overview.SHA256_RE.fullmatch(source_summary["source_facts_sha256"])
        is None
    ):
        raise OverviewWorkspaceError("SAVED_M9_BASIS_INCONSISTENT")
    return {
        "workspace_binding": copy.deepcopy(binding),
        "facts_snapshot": facts_identity,
        "chapter_index_snapshot": index_identity,
        "chapter_revision_ref": copy.deepcopy(chapter_ref),
    }


def execute(
    workspace: AuthorWorkspace,
    chapter_id: str,
    generated_at: str,
    overview_provider: overview.OverviewProvider,
) -> dict[str, Any]:
    """读取目标章当前事实，并原样调用 M9 对象核心。"""

    handle = _require_workspace(workspace)
    clean_chapter_id = _clean_string(chapter_id, reason="CHAPTER_ID_INVALID")
    clean_generated_at = _clean_string(generated_at, reason="GENERATED_AT_INVALID")
    first_facts, first_index, _, _ = _read_validated_sources(
        handle,
        clean_chapter_id,
    )
    facts_snapshot, chapter_index_snapshot, current_ref, facts = (
        _read_validated_sources(handle, clean_chapter_id)
    )
    source_watermark = _source_watermark(
        facts_snapshot,
        chapter_index_snapshot,
    )
    if _source_watermark(first_facts, first_index) != source_watermark:
        raise OverviewWorkspaceError("M9_SOURCE_CHANGED_BEFORE_PROVIDER")
    m9 = overview_tool.execute(
        {
            "facts": facts,
            "current_revision_ref": current_ref,
            "source_revision": _source_revision(
                facts_snapshot,
                chapter_index_snapshot,
            ),
            "generated_at": clean_generated_at,
        },
        overview_provider,
    )
    after_facts = _read_list_snapshot(handle, FACTS_LOGICAL_KEY)
    after_index = _read_list_snapshot(handle, CHAPTER_INDEX_LOGICAL_KEY)
    if _source_watermark(after_facts, after_index) != source_watermark:
        raise OverviewWorkspaceError("M9_SOURCE_CHANGED_DURING_PROVIDER")
    return {
        "workspace_binding": _workspace_binding(handle),
        "facts_snapshot": {
            "version": facts_snapshot["version"],
            "sha256": facts_snapshot["sha256"],
        },
        "chapter_index_snapshot": {
            "version": chapter_index_snapshot["version"],
            "sha256": chapter_index_snapshot["sha256"],
        },
        "m9": m9,
    }


def inspect_freshness(
    workspace: AuthorWorkspace,
    saved_result: dict[str, Any],
) -> dict[str, Any]:
    """只按工作区快照身份判断一张已保存 M9 原型是否仍为当前。"""

    handle = _require_workspace(workspace)
    saved_basis = _saved_basis(saved_result)
    current_binding = _workspace_binding(handle)
    if saved_basis["workspace_binding"] != current_binding:
        raise OverviewWorkspaceError("SAVED_WORKSPACE_BINDING_MISMATCH")

    facts_snapshot = _read_list_snapshot(handle, FACTS_LOGICAL_KEY)
    chapter_index_snapshot = _read_list_snapshot(handle, CHAPTER_INDEX_LOGICAL_KEY)
    try:
        factstore.validate_c4_v1_snapshot(facts_snapshot["payload"])
    except factstore.FactstoreError as exc:
        raise OverviewWorkspaceError(
            f"CURRENT_FACTS_SNAPSHOT_INVALID:{exc}"
        ) from exc
    current_ref = _current_revision_ref(
        chapter_index_snapshot["payload"],
        saved_basis["chapter_revision_ref"]["chapter_id"],
    )
    current_basis = {
        "workspace_binding": current_binding,
        "facts_snapshot": {
            "version": facts_snapshot["version"],
            "sha256": facts_snapshot["sha256"],
        },
        "chapter_index_snapshot": {
            "version": chapter_index_snapshot["version"],
            "sha256": chapter_index_snapshot["sha256"],
        },
        "chapter_revision_ref": current_ref,
    }

    stale_reasons: list[str] = []
    if saved_basis["facts_snapshot"] != current_basis["facts_snapshot"]:
        stale_reasons.append("FACTS_SNAPSHOT_CHANGED")
    if (
        saved_basis["chapter_index_snapshot"]
        != current_basis["chapter_index_snapshot"]
    ):
        stale_reasons.append("CHAPTER_INDEX_SNAPSHOT_CHANGED")
    if saved_basis["chapter_revision_ref"] != current_basis["chapter_revision_ref"]:
        stale_reasons.append("CHAPTER_REVISION_CHANGED")
    return {
        "freshness": "STALE" if stale_reasons else "CURRENT",
        "stale_reasons": stale_reasons,
        "saved_basis": saved_basis,
        "current_basis": current_basis,
    }


__all__ = ["OverviewWorkspaceError", "execute", "inspect_freshness"]
