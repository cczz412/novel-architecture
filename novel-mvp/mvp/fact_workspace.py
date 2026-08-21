"""C4 v1 快照到 AuthorWorkspace 的最小持久化适配器。

只使用 AuthorWorkspace 的逻辑键 ``facts``；不接路径、作者 ID、项目 ID，
不调用 legacy facts.json writer，也不做 M5 作者确认。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from . import (
    chapter_workspace,
    extract_workspace,
    fact_tool,
    factstore,
    segment_workspace,
)
from .workspace import AuthorWorkspace, OperationConflictError


LOGICAL_KEY = "facts"
MATERIALIZATION_KEY = "fact_materialization_runs"
MATERIALIZATION_SCHEMA = "m4-materialization-ledger-v1"
UPSTREAM_KEYS = (
    "chapters",
    "chapter_index",
    "segments",
    "fact_candidates",
)
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
PROCESSED_KEYS = {
    "chapter_revision_ref",
    "c3_candidates_sha256",
    "c3_candidate_count",
    "first_operation_id",
}
MATERIALIZATION_OPERATION_KEYS = {
    "operation_id",
    "request_sha256",
    "added_chapter_ids",
    "source_identity",
    "facts_snapshot",
}


class FactWorkspaceError(factstore.FactstoreError):
    """适配器输入不是受绑定 workspace 能力或合法版本时拒绝。"""


class FactWorkspaceSourceChangedError(FactWorkspaceError):
    """M4 运行期间的来源水位已经变化。"""


def _require_workspace(value: Any) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        raise FactWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
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
        raise FactWorkspaceError("M4_SOURCE_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def _payload_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _empty_materialization_ledger() -> dict[str, Any]:
    return {
        "schema": MATERIALIZATION_SCHEMA,
        "processed_chapters": {},
        "operations": [],
    }


def _validated_source_identity(value: object) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != set(UPSTREAM_KEYS):
        raise FactWorkspaceError("M4_MATERIALIZATION_SOURCE_IDENTITY_INVALID")
    result: dict[str, dict[str, Any]] = {}
    for key in UPSTREAM_KEYS:
        identity = value.get(key)
        if (
            not isinstance(identity, dict)
            or set(identity) != {"version", "sha256"}
            or not isinstance(identity.get("version"), int)
            or isinstance(identity.get("version"), bool)
            or identity["version"] < 1
            or not isinstance(identity.get("sha256"), str)
            or SHA256_RE.fullmatch(identity["sha256"]) is None
        ):
            raise FactWorkspaceError(
                "M4_MATERIALIZATION_SOURCE_IDENTITY_INVALID"
            )
        result[key] = copy.deepcopy(identity)
    return result


def _validated_materialization_ledger(value: object) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "processed_chapters", "operations"}
        or value.get("schema") != MATERIALIZATION_SCHEMA
        or not isinstance(value.get("processed_chapters"), dict)
        or not isinstance(value.get("operations"), list)
    ):
        raise FactWorkspaceError("M4_MATERIALIZATION_LEDGER_INVALID")
    processed: dict[str, dict[str, Any]] = {}
    for chapter_id, row in value["processed_chapters"].items():
        if (
            not isinstance(chapter_id, str)
            or not chapter_id
            or not isinstance(row, dict)
            or set(row) != PROCESSED_KEYS
        ):
            raise FactWorkspaceError("M4_MATERIALIZATION_LEDGER_INVALID")
        try:
            ref = chapter_workspace._validated_revision_refs(
                [row["chapter_revision_ref"]]
            )[chapter_id]
        except (chapter_workspace.ChapterWorkspaceError, KeyError) as exc:
            raise FactWorkspaceError("M4_MATERIALIZATION_LEDGER_INVALID") from exc
        count = row.get("c3_candidate_count")
        digest = row.get("c3_candidates_sha256")
        operation_id = row.get("first_operation_id")
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or not isinstance(digest, str)
            or SHA256_RE.fullmatch(digest) is None
            or not isinstance(operation_id, str)
            or not operation_id
        ):
            raise FactWorkspaceError("M4_MATERIALIZATION_LEDGER_INVALID")
        processed[chapter_id] = {
            "chapter_revision_ref": ref,
            "c3_candidates_sha256": digest,
            "c3_candidate_count": count,
            "first_operation_id": operation_id,
        }

    operations: list[dict[str, Any]] = []
    seen_operations: set[str] = set()
    covered_chapters: list[str] = []
    previous_facts_version = 0
    for row in value["operations"]:
        if not isinstance(row, dict) or set(row) != MATERIALIZATION_OPERATION_KEYS:
            raise FactWorkspaceError("M4_MATERIALIZATION_LEDGER_INVALID")
        operation_id = row.get("operation_id")
        request_sha = row.get("request_sha256")
        added = row.get("added_chapter_ids")
        facts_snapshot = row.get("facts_snapshot")
        if (
            not isinstance(operation_id, str)
            or not operation_id
            or operation_id in seen_operations
            or not isinstance(request_sha, str)
            or SHA256_RE.fullmatch(request_sha) is None
            or not isinstance(added, list)
            or not added
            or any(
                not isinstance(chapter_id, str) or not chapter_id
                for chapter_id in added
            )
            or len(added) != len(set(added))
            or not isinstance(facts_snapshot, dict)
            or set(facts_snapshot) != {"version", "sha256"}
            or not isinstance(facts_snapshot.get("version"), int)
            or isinstance(facts_snapshot.get("version"), bool)
            or facts_snapshot["version"] <= previous_facts_version
            or not isinstance(facts_snapshot.get("sha256"), str)
            or SHA256_RE.fullmatch(facts_snapshot["sha256"]) is None
        ):
            raise FactWorkspaceError("M4_MATERIALIZATION_LEDGER_INVALID")
        seen_operations.add(operation_id)
        covered_chapters.extend(added)
        previous_facts_version = facts_snapshot["version"]
        operations.append(
            {
                "operation_id": operation_id,
                "request_sha256": request_sha,
                "added_chapter_ids": list(added),
                "source_identity": _validated_source_identity(
                    row["source_identity"]
                ),
                "facts_snapshot": copy.deepcopy(facts_snapshot),
            }
        )
    if len(covered_chapters) != len(set(covered_chapters)) or set(
        covered_chapters
    ) != set(processed):
        raise FactWorkspaceError("M4_MATERIALIZATION_LEDGER_COVERAGE_INVALID")
    if any(
        processed[chapter_id]["first_operation_id"] != operation["operation_id"]
        for operation in operations
        for chapter_id in operation["added_chapter_ids"]
    ):
        raise FactWorkspaceError("M4_MATERIALIZATION_LEDGER_COVERAGE_INVALID")
    return {
        "schema": MATERIALIZATION_SCHEMA,
        "processed_chapters": processed,
        "operations": operations,
    }


def _read_materialization_state(workspace: AuthorWorkspace) -> dict[str, Any]:
    state = workspace.read(MATERIALIZATION_KEY)
    if state is None:
        return {
            "version": 0,
            "sha256": None,
            "payload": _empty_materialization_ledger(),
        }
    state = _validated_state_entry(state, MATERIALIZATION_KEY)
    return {
        "version": state["version"],
        "sha256": state["sha256"],
        "payload": _validated_materialization_ledger(state["payload"]),
    }


def _validated_state_entry(value: Any, logical_key: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "logical_key",
        "version",
        "sha256",
        "payload",
    }:
        raise FactWorkspaceError(f"M4_SOURCE_STATE_INVALID:{logical_key}")
    version = value.get("version")
    sha256 = value.get("sha256")
    if (
        value.get("logical_key") != logical_key
        or isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
        or not isinstance(sha256, str)
        or SHA256_RE.fullmatch(sha256) is None
        or hashlib.sha256(_canonical_bytes(value.get("payload"))).hexdigest()
        != sha256
    ):
        raise FactWorkspaceError(f"M4_SOURCE_STATE_INVALID:{logical_key}")
    return value


def _source_identity(states: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "version": states[key]["version"],
            "sha256": states[key]["sha256"],
        }
        for key in UPSTREAM_KEYS
    }


def _read_upstream_states(
    workspace: AuthorWorkspace,
) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for key in UPSTREAM_KEYS:
        state = workspace.read(key)
        if state is None:
            raise FactWorkspaceError(f"M4_SOURCE_STATE_MISSING:{key}")
        states[key] = _validated_state_entry(state, key)
    return states


def _read_current_upstream(
    workspace: AuthorWorkspace,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    states_before = _read_upstream_states(workspace)
    try:
        chapters = chapter_workspace.read_c1_current_views(workspace)
        segments_payload = segment_workspace.read_current_segments(workspace)
        candidates_payload = (
            extract_workspace.read_current_complete_fact_candidates(workspace)
        )
    except (
        chapter_workspace.ChapterWorkspaceError,
        segment_workspace.SegmentWorkspaceError,
        extract_workspace.ExtractWorkspaceError,
    ) as exc:
        raise FactWorkspaceError(f"M4_CURRENT_SOURCE_INVALID:{exc}") from exc

    states_after = _read_upstream_states(workspace)
    before_identity = _source_identity(states_before)
    after_identity = _source_identity(states_after)
    if before_identity != after_identity:
        raise FactWorkspaceSourceChangedError(
            "M4_CURRENT_SOURCE_CHANGED_DURING_READ"
        )
    if (
        chapters != states_after["chapters"]["payload"]
        or segments_payload != states_after["segments"]["payload"]
        or candidates_payload != states_after["fact_candidates"]["payload"]
    ):
        raise FactWorkspaceError("M4_CURRENT_SOURCE_PAYLOAD_DRIFT")

    current_refs = states_after["chapter_index"]["payload"]
    try:
        checked_chapters, checked_refs = chapter_workspace._validated_batch(
            chapters,
            current_refs,
        )
    except chapter_workspace.ChapterWorkspaceError as exc:
        raise FactWorkspaceError(f"M4_CURRENT_SOURCE_INVALID:{exc}") from exc
    if checked_chapters != chapters or checked_refs != current_refs:
        raise FactWorkspaceError("M4_CURRENT_SOURCE_PAYLOAD_DRIFT")
    return (
        copy.deepcopy(chapters),
        copy.deepcopy(segments_payload["items"]),
        copy.deepcopy(candidates_payload["items"]),
        after_identity,
    )


def save_snapshot(
    workspace: AuthorWorkspace,
    *,
    operation_id: str,
    snapshot: list[dict[str, Any]],
    expected_version: int,
) -> dict[str, Any]:
    """校验整批 C4 v1 后，通过 workspace.commit 原子替换逻辑键 facts。"""
    workspace = _require_workspace(workspace)
    if (
        not isinstance(expected_version, int)
        or isinstance(expected_version, bool)
        or expected_version < 0
    ):
        raise FactWorkspaceError("FACTS_EXPECTED_VERSION_INVALID")
    facts = factstore.validate_c4_v1_snapshot(snapshot)
    receipt = workspace.commit(
        operation_id,
        {LOGICAL_KEY: facts},
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


def read_snapshot(workspace: AuthorWorkspace) -> dict[str, Any]:
    """读取并重新校验当前 facts；缺失时返回空的 version 0 视图。"""
    workspace = _require_workspace(workspace)
    current = workspace.read(LOGICAL_KEY)
    if current is None:
        return {"version": 0, "sha256": None, "facts": []}
    facts = factstore.validate_c4_v1_snapshot(current["payload"])
    return {
        "version": current["version"],
        "sha256": current["sha256"],
        "facts": copy.deepcopy(facts),
    }


def _read_current_fact_view_source(
    workspace: AuthorWorkspace,
) -> dict[str, Any]:
    facts_state = workspace.read(LOGICAL_KEY)
    if facts_state is None:
        facts_snapshot = {"version": 0, "sha256": None, "payload": []}
    else:
        facts_snapshot = _validated_state_entry(facts_state, LOGICAL_KEY)

    index_state = workspace.read("chapter_index")
    if index_state is None:
        raise FactWorkspaceError("M4_CURRENT_CHAPTER_INDEX_MISSING")
    index_snapshot = _validated_state_entry(index_state, "chapter_index")

    try:
        facts = factstore.validate_c4_v1_snapshot(facts_snapshot["payload"])
    except factstore.FactstoreError as exc:
        raise FactWorkspaceError(f"M4_CURRENT_FACTS_INVALID:{exc}") from exc
    try:
        refs_by_chapter = chapter_workspace._validated_revision_refs(
            index_snapshot["payload"]
        )
    except chapter_workspace.ChapterWorkspaceError as exc:
        raise FactWorkspaceError(
            f"M4_CURRENT_CHAPTER_INDEX_INVALID:{exc}"
        ) from exc

    current_facts: list[dict[str, Any]] = []
    stale_fact_ids: list[str] = []
    for fact in facts:
        chapter_id = fact["chapter_id"]
        current_ref = refs_by_chapter.get(chapter_id)
        if current_ref is None:
            raise FactWorkspaceError(
                f"M4_CURRENT_FACT_CHAPTER_UNKNOWN:{fact['id']}:{chapter_id}"
            )
        if fact["chapter_revision_ref"] == current_ref:
            current_facts.append(copy.deepcopy(fact))
        else:
            stale_fact_ids.append(fact["id"])

    return {
        "facts": current_facts,
        "stale_fact_ids": stale_fact_ids,
        "facts_snapshot": {
            "version": facts_snapshot["version"],
            "sha256": facts_snapshot["sha256"],
        },
        "chapter_index_snapshot": {
            "version": index_snapshot["version"],
            "sha256": index_snapshot["sha256"],
        },
    }


def _current_fact_view_watermark(
    view: dict[str, Any],
) -> tuple[tuple[Any, Any], tuple[Any, Any]]:
    return (
        (
            view["facts_snapshot"]["version"],
            view["facts_snapshot"]["sha256"],
        ),
        (
            view["chapter_index_snapshot"]["version"],
            view["chapter_index_snapshot"]["sha256"],
        ),
    )


def read_current_snapshot(workspace: AuthorWorkspace) -> dict[str, Any]:
    """只返回仍绑定 chapter_index current revision 的 C4 事实。"""
    workspace = _require_workspace(workspace)
    first_view = _read_current_fact_view_source(workspace)
    try:
        current_view = _read_current_fact_view_source(workspace)
    except FactWorkspaceError as exc:
        raise FactWorkspaceSourceChangedError(
            "M4_CURRENT_FACT_VIEW_SOURCE_CHANGED_DURING_READ"
        ) from exc
    current_watermark = _current_fact_view_watermark(current_view)
    if _current_fact_view_watermark(first_view) != current_watermark:
        raise FactWorkspaceSourceChangedError(
            "M4_CURRENT_FACT_VIEW_SOURCE_CHANGED_DURING_READ"
        )

    try:
        after_view = _read_current_fact_view_source(workspace)
    except FactWorkspaceError as exc:
        raise FactWorkspaceSourceChangedError(
            "M4_CURRENT_FACT_VIEW_SOURCE_CHANGED_DURING_READ"
        ) from exc
    if _current_fact_view_watermark(after_view) != current_watermark:
        raise FactWorkspaceSourceChangedError(
            "M4_CURRENT_FACT_VIEW_SOURCE_CHANGED_DURING_READ"
        )
    return copy.deepcopy(current_view)


def _revision_key(value: Any) -> str:
    if not isinstance(value, dict):
        raise FactWorkspaceError("M4_REVISION_REF_INVALID")
    return _canonical_bytes(value).decode("utf-8")


def materialize_current_extracted_snapshot(
    workspace: AuthorWorkspace,
    *,
    operation_id: str,
    source: str,
    added_at: str,
) -> dict[str, Any]:
    """把尚未处理的 current 章节全有或全无地追加进 C4。"""
    workspace = _require_workspace(workspace)
    if not isinstance(operation_id, str) or not operation_id:
        raise FactWorkspaceError("M4_OPERATION_ID_INVALID")
    if not isinstance(source, str) or not source or source != source.strip():
        raise FactWorkspaceError("M4_SOURCE_INVALID")
    if (
        not isinstance(added_at, str)
        or not added_at
        or added_at != added_at.strip()
    ):
        raise FactWorkspaceError("M4_ADDED_AT_INVALID")

    materialization_state = _read_materialization_state(workspace)
    request_sha = _payload_sha256(
        {
            "operation_id": operation_id,
            "source": source,
            "added_at": added_at,
        }
    )
    existing_operation = next(
        (
            row
            for row in materialization_state["payload"]["operations"]
            if row["operation_id"] == operation_id
        ),
        None,
    )
    if existing_operation is not None:
        if existing_operation["request_sha256"] != request_sha:
            raise OperationConflictError(
                "OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST"
            )
        return {
            "status": "COMMITTED",
            "operation_id": operation_id,
            "version": existing_operation["facts_snapshot"]["version"],
            "sha256": existing_operation["facts_snapshot"]["sha256"],
            "added_chapter_ids": copy.deepcopy(
                existing_operation["added_chapter_ids"]
            ),
            "replayed": True,
        }

    facts_state = workspace.read(LOGICAL_KEY)
    if facts_state is None:
        if materialization_state["version"] != 0:
            raise FactWorkspaceError("M4_FACTS_MATERIALIZATION_STATE_DIVERGED")
        existing_facts: list[dict[str, Any]] = []
        facts_version = 0
        facts_sha = None
    else:
        facts_state = _validated_state_entry(facts_state, LOGICAL_KEY)
        existing_facts = factstore.validate_c4_v1_snapshot(
            facts_state["payload"]
        )
        facts_version = facts_state["version"]
        facts_sha = facts_state["sha256"]
        if materialization_state["version"] == 0:
            raise FactWorkspaceError("M4_MATERIALIZATION_LEDGER_MISSING")

    processed = materialization_state["payload"]["processed_chapters"]
    operations = materialization_state["payload"]["operations"]
    if operations and facts_version < operations[-1]["facts_snapshot"]["version"]:
        raise FactWorkspaceError("M4_FACTS_MATERIALIZATION_STATE_DIVERGED")
    if any(
        fact["chapter_id"] not in processed
        or fact["chapter_revision_ref"]
        != processed[fact["chapter_id"]]["chapter_revision_ref"]
        for fact in existing_facts
    ):
        raise FactWorkspaceError("M4_FACTS_MATERIALIZATION_STATE_DIVERGED")

    chapters, segments, candidates, source_identity = _read_current_upstream(
        workspace
    )

    chapter_keys = [
        _revision_key(chapter["chapter_revision_ref"]) for chapter in chapters
    ]
    if len(chapter_keys) != len(set(chapter_keys)):
        raise FactWorkspaceError("M4_CHAPTER_REVISION_REF_DUPLICATE")
    segments_by_revision: dict[str, list[dict[str, Any]]] = {
        key: [] for key in chapter_keys
    }
    candidates_by_revision: dict[str, list[dict[str, Any]]] = {
        key: [] for key in chapter_keys
    }
    for segment in segments:
        key = _revision_key(segment.get("chapter_revision_ref"))
        if key not in segments_by_revision:
            raise FactWorkspaceError("M4_SEGMENT_CURRENT_CHAPTER_NOT_FOUND")
        segments_by_revision[key].append(segment)
    for candidate in candidates:
        key = _revision_key(candidate.get("chapter_revision_ref"))
        if key not in candidates_by_revision:
            raise FactWorkspaceError("M4_CANDIDATE_CURRENT_CHAPTER_NOT_FOUND")
        candidates_by_revision[key].append(candidate)
    if any(not segments_by_revision[key] for key in chapter_keys):
        raise FactWorkspaceError("M4_CHAPTER_SEGMENTS_MISSING")

    current_by_id = {
        chapter["id"]: chapter["chapter_revision_ref"]
        for chapter in chapters
    }
    if set(processed) - set(current_by_id):
        raise FactWorkspaceError("M4_PROCESSED_CHAPTER_NO_LONGER_CURRENT")
    for chapter_id, record in processed.items():
        if record["chapter_revision_ref"] != current_by_id[chapter_id]:
            raise FactWorkspaceError("M4_REVISION_LIFECYCLE_REQUIRED")
        key = _revision_key(current_by_id[chapter_id])
        current_candidates = candidates_by_revision[key]
        if (
            record["c3_candidate_count"] != len(current_candidates)
            or record["c3_candidates_sha256"]
            != _payload_sha256(current_candidates)
        ):
            raise FactWorkspaceError("M4_PROCESSED_C3_CHANGED")

    new_chapters = [chapter for chapter in chapters if chapter["id"] not in processed]
    if not new_chapters:
        return {
            "status": "NO_CHANGE",
            "operation_id": operation_id,
            "version": facts_version,
            "sha256": facts_sha,
            "added_chapter_ids": [],
            "replayed": False,
        }

    snapshot: list[dict[str, Any]] = copy.deepcopy(existing_facts)
    processed_after = copy.deepcopy(processed)
    try:
        for chapter in new_chapters:
            key = _revision_key(chapter["chapter_revision_ref"])
            chapter_candidates = candidates_by_revision[key]
            candidate_keys = [_canonical_bytes(row) for row in chapter_candidates]
            if len(candidate_keys) != len(set(candidate_keys)):
                raise FactWorkspaceError("M4_C3_DUPLICATE_CANDIDATE")
            result = fact_tool.execute(
                {
                    "chapter": chapter,
                    "segments": segments_by_revision[key],
                    "candidates": chapter_candidates,
                    "existing_c4": snapshot,
                    "source": source,
                    "added_at": added_at,
                }
            )
            snapshot = result["facts"]
            processed_after[chapter["id"]] = {
                "chapter_revision_ref": copy.deepcopy(
                    chapter["chapter_revision_ref"]
                ),
                "c3_candidates_sha256": _payload_sha256(chapter_candidates),
                "c3_candidate_count": len(chapter_candidates),
                "first_operation_id": operation_id,
            }
    except (factstore.FactstoreError, KeyError, TypeError) as exc:
        raise FactWorkspaceError(f"M4_MATERIALIZATION_REJECTED:{exc}") from exc

    snapshot = factstore.validate_c4_v1_snapshot(snapshot)
    if snapshot[: len(existing_facts)] != existing_facts:
        raise FactWorkspaceError("M4_EXISTING_FACTS_CHANGED_DURING_APPEND")
    if any(
        fact["status"] != factstore.STATUS_EXTRACTED
        for fact in snapshot[len(existing_facts) :]
    ):
        raise FactWorkspaceError("M4_NEW_FACT_STATUS_NOT_EXTRACTED")

    try:
        _, _, _, latest_identity = _read_current_upstream(workspace)
    except FactWorkspaceError as exc:
        raise FactWorkspaceSourceChangedError(
            "M4_SOURCE_CHANGED_DURING_RUN"
        ) from exc
    if latest_identity != source_identity:
        raise FactWorkspaceSourceChangedError("M4_SOURCE_CHANGED_DURING_RUN")

    facts_snapshot = {
        "version": facts_version + 1,
        "sha256": _payload_sha256(snapshot),
    }
    ledger = copy.deepcopy(materialization_state["payload"])
    added_chapter_ids = [chapter["id"] for chapter in new_chapters]
    ledger["processed_chapters"] = processed_after
    ledger["operations"].append(
        {
            "operation_id": operation_id,
            "request_sha256": request_sha,
            "added_chapter_ids": added_chapter_ids,
            "source_identity": copy.deepcopy(source_identity),
            "facts_snapshot": facts_snapshot,
        }
    )
    ledger = _validated_materialization_ledger(ledger)
    expected = {
        LOGICAL_KEY: {"version": facts_version, "sha256": facts_sha},
        MATERIALIZATION_KEY: {
            "version": materialization_state["version"],
            "sha256": materialization_state["sha256"],
        },
    }
    committed = workspace.commit_guarded(
        operation_id,
        {LOGICAL_KEY: snapshot, MATERIALIZATION_KEY: ledger},
        expected,
        source_identity,
    )
    return {
        "status": committed["status"],
        "operation_id": operation_id,
        "version": committed["versions"][LOGICAL_KEY],
        "sha256": committed["payload_sha256"][LOGICAL_KEY],
        "added_chapter_ids": added_chapter_ids,
        "generation_id": committed["generation_id"],
        "replayed": committed["replayed"],
    }
