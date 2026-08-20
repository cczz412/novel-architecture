"""AuthorWorkspace 到现役 M7 ``check_tool`` 的工作区适配层。

调用方只能交入已绑定作者与项目的 ``AuthorWorkspace`` 句柄。本模块只读
逻辑键 ``facts`` 与 ``chapter_index``，并可把当前 C6 v1 投影保存到唯一的
``health_report`` 槽位；不认路径、作者 ID 或项目 ID，也不改事实或章索引。
"""

from __future__ import annotations

import copy
from typing import Any

from . import check_tool
from .workspace import AuthorWorkspace


FACTS_LOGICAL_KEY = "facts"
CHAPTER_INDEX_LOGICAL_KEY = "chapter_index"
HEALTH_REPORT_LOGICAL_KEY = "health_report"
SAVED_REPORT_VERSION = "m7-health-report-workspace-v1"
SAVED_REPORT_KEYS = {
    "store_version",
    "workspace_binding",
    "facts_snapshot",
    "chapter_index_snapshot",
    "m7",
}
C6_REPORT_KEYS = {
    "contract",
    "version",
    "project",
    "generated_at",
    "model",
    "chapter_revision_refs",
    "source_revision_state",
    "scan",
    "conflicts",
    "insufficient",
    "alias_hints",
    "integrity",
    "summary",
}
ADAPTER_CONFIG_KEYS = {
    "project_label",
    "generated_at",
    "scope_name",
    "scope_kind",
    "kinds",
}


class CheckWorkspaceError(check_tool.CheckToolError):
    """M7 工作区适配器拒绝了非句柄或损坏的读取结果。"""


def _valid_revision_ref(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == check_tool.REVISION_REF_KEYS
        and isinstance(value.get("chapter_id"), str)
        and bool(value["chapter_id"])
        and isinstance(value.get("revision_no"), int)
        and not isinstance(value["revision_no"], bool)
        and value["revision_no"] >= 1
        and isinstance(value.get("revision_text_sha256"), str)
        and check_tool.SHA256_RE.fullmatch(value["revision_text_sha256"])
        is not None
    )


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        raise CheckWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _read_list_snapshot(
    workspace: AuthorWorkspace,
    logical_key: str,
) -> dict[str, Any]:
    entry = workspace.read(logical_key)
    if entry is None:
        return {"version": 0, "sha256": None, "payload": []}
    if (
        not isinstance(entry, dict)
        or entry.get("logical_key") != logical_key
        or not isinstance(entry.get("version"), int)
        or isinstance(entry.get("version"), bool)
        or entry["version"] < 1
        or not isinstance(entry.get("sha256"), str)
        or check_tool.SHA256_RE.fullmatch(entry["sha256"]) is None
        or not isinstance(entry.get("payload"), list)
    ):
        raise CheckWorkspaceError(f"{logical_key.upper()}_WORKSPACE_ENTRY_INVALID")
    return {
        "version": entry["version"],
        "sha256": entry["sha256"],
        "payload": copy.deepcopy(entry["payload"]),
    }


def _current_revision_refs(
    facts: list[Any],
    chapter_index: list[Any],
) -> list[dict[str, Any]]:
    refs_by_chapter: dict[str, dict[str, Any]] = {}
    for index, ref in enumerate(chapter_index):
        if not _valid_revision_ref(ref):
            raise CheckWorkspaceError(f"CHAPTER_INDEX_REF_INVALID:{index}")
        chapter_id = ref["chapter_id"]
        if chapter_id in refs_by_chapter:
            raise CheckWorkspaceError(f"CHAPTER_INDEX_REF_DUPLICATE:{chapter_id}")
        refs_by_chapter[chapter_id] = copy.deepcopy(ref)
    if facts and not chapter_index:
        raise CheckWorkspaceError("CHAPTER_INDEX_REQUIRED_FOR_NONEMPTY_FACTS")
    fact_chapters: set[str] = set()
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            raise CheckWorkspaceError(f"FACTS_ITEM_NOT_OBJECT:{index}")
        chapter_id = fact.get("chapter_id")
        revision_ref = fact.get("chapter_revision_ref")
        if (
            not isinstance(chapter_id, str)
            or not chapter_id
            or not isinstance(revision_ref, dict)
            or revision_ref.get("chapter_id") != chapter_id
        ):
            raise CheckWorkspaceError(f"FACT_CHAPTER_ID_MISMATCH:{index}")
        fact_chapters.add(chapter_id)
    missing = sorted(fact_chapters - set(refs_by_chapter))
    if missing:
        raise CheckWorkspaceError(
            f"CHAPTER_INDEX_REF_MISSING:{','.join(missing)}"
        )
    return [copy.deepcopy(ref) for ref in chapter_index]


def _split_config(check_config: object) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(check_config, dict) or set(check_config) != ADAPTER_CONFIG_KEYS:
        raise CheckWorkspaceError(
            "check_config 只允许 project_label、generated_at、scope_name、scope_kind、kinds"
        )
    project_label = check_config["project_label"]
    generated_at = check_config["generated_at"]
    if not isinstance(project_label, str) or not project_label.strip():
        raise CheckWorkspaceError("project_label 必须是非空显示名")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise CheckWorkspaceError("generated_at 必须显式提供")
    core_config = {
        "scope_name": copy.deepcopy(check_config["scope_name"]),
        "scope_kind": copy.deepcopy(check_config["scope_kind"]),
        "kinds": copy.deepcopy(check_config["kinds"]),
    }
    return project_label, generated_at, core_config


def _read_validated_sources(
    workspace: AuthorWorkspace,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    facts_snapshot = _read_list_snapshot(workspace, FACTS_LOGICAL_KEY)
    chapter_index_snapshot = _read_list_snapshot(
        workspace,
        CHAPTER_INDEX_LOGICAL_KEY,
    )
    current_revision_refs = _current_revision_refs(
        facts_snapshot["payload"],
        chapter_index_snapshot["payload"],
    )
    return facts_snapshot, chapter_index_snapshot, current_revision_refs


def _source_watermark(
    facts_snapshot: dict[str, Any],
    chapter_index_snapshot: dict[str, Any],
) -> tuple[tuple[int, str | None], tuple[int, str | None]]:
    return (
        (facts_snapshot["version"], facts_snapshot["sha256"]),
        (
            chapter_index_snapshot["version"],
            chapter_index_snapshot["sha256"],
        ),
    )


def _validate_watermark(value: object, *, label: str) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "sha256"}
        or not isinstance(value.get("version"), int)
        or isinstance(value["version"], bool)
        or value["version"] < 0
    ):
        raise CheckWorkspaceError(f"{label}_SNAPSHOT_INVALID")
    sha256 = value["sha256"]
    if value["version"] == 0:
        if sha256 is not None:
            raise CheckWorkspaceError(f"{label}_SNAPSHOT_INVALID")
    elif (
        not isinstance(sha256, str)
        or check_tool.SHA256_RE.fullmatch(sha256) is None
    ):
        raise CheckWorkspaceError(f"{label}_SNAPSHOT_INVALID")
    return {"version": value["version"], "sha256": sha256}


def _validate_c6_report(value: object) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != C6_REPORT_KEYS
        or value.get("contract") != "C6_HEALTH_REPORT"
        or value.get("version") != "v1"
        or any(
            not isinstance(value.get(key), str) or not value[key].strip()
            for key in ("project", "generated_at", "model")
        )
        or value.get("source_revision_state")
        not in {"CURRENT", "STALE", "LEGACY_REVISION_UNKNOWN"}
        or not isinstance(value.get("chapter_revision_refs"), list)
        or any(
            not _valid_revision_ref(ref)
            for ref in value["chapter_revision_refs"]
        )
        or len(
            {
                ref["chapter_id"]
                for ref in value["chapter_revision_refs"]
            }
        )
        != len(value["chapter_revision_refs"])
        or not isinstance(value.get("scan"), dict)
        or not isinstance(value.get("conflicts"), list)
        or not isinstance(value.get("insufficient"), list)
        or not isinstance(value.get("alias_hints"), list)
        or not isinstance(value.get("integrity"), dict)
        or not isinstance(value.get("summary"), dict)
    ):
        raise CheckWorkspaceError("HEALTH_REPORT_C6_V1_INVALID")
    return copy.deepcopy(value)


def _validate_saved_payload(
    value: object,
    *,
    workspace: AuthorWorkspace,
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != SAVED_REPORT_KEYS
        or value.get("store_version") != SAVED_REPORT_VERSION
        or not isinstance(value.get("workspace_binding"), dict)
        or set(value["workspace_binding"]) != {"author_id", "project_id"}
    ):
        raise CheckWorkspaceError("HEALTH_REPORT_STORE_INVALID")
    binding = value["workspace_binding"]
    if (
        binding.get("author_id") != workspace.author_id
        or binding.get("project_id") != workspace.project_id
    ):
        raise CheckWorkspaceError("HEALTH_REPORT_WORKSPACE_BINDING_MISMATCH")
    facts_snapshot = _validate_watermark(
        value.get("facts_snapshot"),
        label="FACTS",
    )
    chapter_index_snapshot = _validate_watermark(
        value.get("chapter_index_snapshot"),
        label="CHAPTER_INDEX",
    )
    report = _validate_c6_report(value.get("m7"))
    if report["source_revision_state"] != "CURRENT":
        raise CheckWorkspaceError("HEALTH_REPORT_STORED_STATE_NOT_CURRENT")
    return {
        "store_version": SAVED_REPORT_VERSION,
        "workspace_binding": copy.deepcopy(binding),
        "facts_snapshot": facts_snapshot,
        "chapter_index_snapshot": chapter_index_snapshot,
        "m7": report,
    }


def _read_saved_entry(
    workspace: AuthorWorkspace,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    entry = workspace.read(HEALTH_REPORT_LOGICAL_KEY)
    if entry is None:
        return None
    if (
        not isinstance(entry, dict)
        or entry.get("logical_key") != HEALTH_REPORT_LOGICAL_KEY
        or not isinstance(entry.get("version"), int)
        or isinstance(entry.get("version"), bool)
        or entry["version"] < 1
        or not isinstance(entry.get("sha256"), str)
        or check_tool.SHA256_RE.fullmatch(entry["sha256"]) is None
    ):
        raise CheckWorkspaceError("HEALTH_REPORT_WORKSPACE_ENTRY_INVALID")
    return _validate_saved_payload(entry.get("payload"), workspace=workspace), entry


def _watermark_state(
    *,
    saved: dict[str, Any],
    current: dict[str, Any],
    label: str,
) -> str | None:
    if current["version"] < saved["version"]:
        raise CheckWorkspaceError(f"{label}_SNAPSHOT_VERSION_REGRESSED")
    if current["version"] == saved["version"]:
        if current["sha256"] != saved["sha256"]:
            raise CheckWorkspaceError(f"{label}_SNAPSHOT_SHA_CONFLICT")
        return None
    return f"{label}_SNAPSHOT_ADVANCED"


def execute(
    workspace: AuthorWorkspace,
    check_config: dict[str, Any],
    finding_provider: check_tool.FindingProvider,
) -> dict[str, Any]:
    """从同一绑定工作区自读 facts/current refs，再调用 M7 对象核心。"""

    handle = _require_workspace(workspace)
    project_label, generated_at, core_config = _split_config(check_config)
    first_facts, first_index, _ = _read_validated_sources(handle)
    facts_snapshot, chapter_index_snapshot, current_revision_refs = (
        _read_validated_sources(handle)
    )
    source_watermark = _source_watermark(
        facts_snapshot,
        chapter_index_snapshot,
    )
    if _source_watermark(first_facts, first_index) != source_watermark:
        raise CheckWorkspaceError("M7_SOURCE_CHANGED_BEFORE_PROVIDER")
    report = check_tool.execute(
        {
            "project": project_label,
            "generated_at": generated_at,
            "facts": facts_snapshot["payload"],
            "current_revision_refs": current_revision_refs,
            "check_config": core_config,
        },
        finding_provider,
    )
    after_facts = _read_list_snapshot(handle, FACTS_LOGICAL_KEY)
    after_index = _read_list_snapshot(handle, CHAPTER_INDEX_LOGICAL_KEY)
    if _source_watermark(after_facts, after_index) != source_watermark:
        raise CheckWorkspaceError("M7_SOURCE_CHANGED_DURING_PROVIDER")
    return {
        "facts_snapshot": {
            "version": facts_snapshot["version"],
            "sha256": facts_snapshot["sha256"],
        },
        "chapter_index_snapshot": {
            "version": chapter_index_snapshot["version"],
            "sha256": chapter_index_snapshot["sha256"],
        },
        "m7": report,
    }


def execute_and_save(
    workspace: AuthorWorkspace,
    operation_id: str,
    check_config: dict[str, Any],
    finding_provider: check_tool.FindingProvider,
    expected_report_version: int,
) -> dict[str, Any]:
    """生成新鲜 C6 v1 报告，并覆盖唯一的 current 报告槽位。"""

    handle = _require_workspace(workspace)
    if (
        not isinstance(expected_report_version, int)
        or isinstance(expected_report_version, bool)
        or expected_report_version < 0
    ):
        raise CheckWorkspaceError("EXPECTED_REPORT_VERSION_INVALID")
    generated = execute(handle, check_config, finding_provider)
    facts_now = _read_list_snapshot(handle, FACTS_LOGICAL_KEY)
    chapter_index_now = _read_list_snapshot(handle, CHAPTER_INDEX_LOGICAL_KEY)
    if _source_watermark(facts_now, chapter_index_now) != _source_watermark(
        generated["facts_snapshot"],
        generated["chapter_index_snapshot"],
    ):
        raise CheckWorkspaceError("M7_SOURCE_CHANGED_BEFORE_SAVE")
    payload = {
        "store_version": SAVED_REPORT_VERSION,
        "workspace_binding": {
            "author_id": handle.author_id,
            "project_id": handle.project_id,
        },
        "facts_snapshot": copy.deepcopy(generated["facts_snapshot"]),
        "chapter_index_snapshot": copy.deepcopy(
            generated["chapter_index_snapshot"]
        ),
        "m7": _validate_c6_report(generated["m7"]),
    }
    receipt = handle.commit(
        operation_id,
        {HEALTH_REPORT_LOGICAL_KEY: payload},
        {HEALTH_REPORT_LOGICAL_KEY: expected_report_version},
    )
    return {
        "receipt": receipt,
        "facts_snapshot": copy.deepcopy(payload["facts_snapshot"]),
        "chapter_index_snapshot": copy.deepcopy(
            payload["chapter_index_snapshot"]
        ),
        "m7": copy.deepcopy(payload["m7"]),
    }


def read_saved(workspace: AuthorWorkspace) -> dict[str, Any] | None:
    """读回 current 报告，并只在返回副本上派生 CURRENT/STALE。"""

    handle = _require_workspace(workspace)
    loaded = _read_saved_entry(handle)
    if loaded is None:
        return None
    payload, entry = loaded
    facts_now = _read_list_snapshot(handle, FACTS_LOGICAL_KEY)
    chapter_index_now = _read_list_snapshot(handle, CHAPTER_INDEX_LOGICAL_KEY)
    reasons = [
        reason
        for reason in (
            _watermark_state(
                saved=payload["facts_snapshot"],
                current=facts_now,
                label="FACTS",
            ),
            _watermark_state(
                saved=payload["chapter_index_snapshot"],
                current=chapter_index_now,
                label="CHAPTER_INDEX",
            ),
        )
        if reason is not None
    ]
    report = copy.deepcopy(payload["m7"])
    report["source_revision_state"] = "STALE" if reasons else "CURRENT"
    return {
        "health_report_snapshot": {
            "version": entry["version"],
            "sha256": entry["sha256"],
        },
        "facts_snapshot": copy.deepcopy(payload["facts_snapshot"]),
        "chapter_index_snapshot": copy.deepcopy(
            payload["chapter_index_snapshot"]
        ),
        "current_facts_snapshot": {
            "version": facts_now["version"],
            "sha256": facts_now["sha256"],
        },
        "current_chapter_index_snapshot": {
            "version": chapter_index_now["version"],
            "sha256": chapter_index_now["sha256"],
        },
        "stale_reasons": reasons,
        "m7": report,
    }


__all__ = ["CheckWorkspaceError", "execute", "execute_and_save", "read_saved"]
