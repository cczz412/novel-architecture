"""CCZ-126 current-only reader for AuthorWorkspace chapter and fact state.

The reader opens one AuthorWorkspace generation snapshot, validates each logical
state once, and emits the frozen LEDGER_READ_RESPONSE v1 shape.  It does not
write workspace state, expose physical paths, or open pinned/setting/plan data.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, NoReturn

from . import chapter_workspace, factstore, ledger_directory_workspace
from .workspace import AuthorWorkspace, CurrentGenerationSnapshot


VERSION = "ledger-read-tool-contract-v1"
LIMIT_POLICY_VERSION = "limit-policy-v1"
MAX_REFS = 50
MAX_BUSINESS_ITEMS = 100
MAX_RESPONSE_BYTES = 256 * 1024
SNAPSHOT_KEYS = ("ledger_directory", "chapters", "chapter_index", "facts")
TRUSTED_CONTEXT_FIELDS = {
    "caller_id",
    "permission_profile",
    "permission_policy_version",
}
OPEN_ENTRY_PROFILES = {
    "章节账": "chapter_metadata",
    "事实账": "fact_record",
}
UNAVAILABLE_ENTRY_LEDGERS = {
    "人物账",
    "地点账",
    "物品账",
    "势力账",
    "体系账",
    "世界规则账",
}


class LedgerReadRuntimeError(ValueError):
    """The trusted composition or current reader boundary was violated."""


def _fail(code: str) -> NoReturn:
    raise LedgerReadRuntimeError(code)


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise LedgerReadRuntimeError("VALUE_NOT_JSON_SERIALIZABLE") from exc


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _contract_validator() -> ModuleType:
    path = (
        Path(__file__).resolve().parent.parent
        / "contracts"
        / "validate_ledger_read_tool_contract.py"
    )
    spec = importlib.util.spec_from_file_location(
        "mvp_ledger_read_tool_contract_validator",
        path,
    )
    if spec is None or spec.loader is None:
        _fail("LEDGER_READ_VALIDATOR_NOT_LOADABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_ledger_read_document(document: Any) -> dict[str, Any]:
    return copy.deepcopy(_contract_validator().validate_document(document))


def _trusted_context(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != TRUSTED_CONTEXT_FIELDS:
        _fail("TRUSTED_EXECUTION_CONTEXT_INVALID")
    result = copy.deepcopy(dict(value))
    if any(
        not isinstance(result[field], str) or not result[field].strip()
        for field in result
    ):
        _fail("TRUSTED_EXECUTION_CONTEXT_INVALID")
    return result


@dataclass(frozen=True)
class CurrentLedgerReadSession:
    """One validated, current-at-start read session; callers use the factory."""

    workspace: AuthorWorkspace
    snapshot: CurrentGenerationSnapshot
    execution_context: dict[str, str]
    directory_state: dict[str, Any] | None
    chapters_state: dict[str, Any] | None
    chapter_index_state: dict[str, Any] | None
    facts_state: dict[str, Any] | None
    chapters_by_id: dict[str, dict[str, Any]]
    facts_by_id: dict[str, dict[str, Any]]
    confirmed_facts_by_revision: dict[tuple[str, int, str], list[dict[str, Any]]]
    capability_snapshot: dict[str, Any] | None
    source_error: str | None

    @property
    def author_id(self) -> str:
        return self.workspace.author_id

    @property
    def project_id(self) -> str:
        return self.workspace.project_id

    @property
    def storage_generation(self) -> str:
        return self.snapshot.generation_id or "author-workspace-empty-v1"

    def is_current(self) -> bool:
        return self.workspace.is_current_snapshot(self.snapshot)


def _state_content_status(state: dict[str, Any] | None) -> str:
    if state is None or state["payload"] == []:
        return "EMPTY"
    return "PRESENT"


def _state_watermark(state: dict[str, Any] | None, logical_key: str) -> str:
    if state is None:
        return f"{logical_key}@0"
    return f"{logical_key}@{state['version']}:{state['sha256']}"


def _capability_snapshot(
    workspace: AuthorWorkspace,
    snapshot: CurrentGenerationSnapshot,
    trusted: dict[str, str],
    directory_state: dict[str, Any],
    chapters_state: dict[str, Any] | None,
    facts_state: dict[str, Any] | None,
) -> dict[str, Any]:
    ledgers = [
        {
            "ledger_name": "章节账",
            "runtime_status": "AVAILABLE",
            "content_status": _state_content_status(chapters_state),
            "visibility": "FULL",
            "reason_code": (
                "REGISTERED_EMPTY"
                if _state_content_status(chapters_state) == "EMPTY"
                else None
            ),
            "source_watermark": _state_watermark(chapters_state, "chapters"),
        },
        {
            "ledger_name": "事实账",
            "runtime_status": "AVAILABLE",
            "content_status": _state_content_status(facts_state),
            "visibility": "FULL",
            "reason_code": (
                "REGISTERED_EMPTY"
                if _state_content_status(facts_state) == "EMPTY"
                else None
            ),
            "source_watermark": _state_watermark(facts_state, "facts"),
        },
    ]
    for ledger_name in ("人物账", "地点账", "物品账", "势力账", "体系账", "世界规则账"):
        ledgers.append(
            {
                "ledger_name": ledger_name,
                "runtime_status": "UNAVAILABLE",
                "content_status": "UNKNOWN",
                "visibility": "FULL",
                "reason_code": "CAPABILITY_UNAVAILABLE",
                "source_watermark": None,
            }
        )
    ledgers.extend(
        [
            {
                "ledger_name": "长线账",
                "runtime_status": "UNAVAILABLE",
                "content_status": "UNKNOWN",
                "visibility": "FULL",
                "reason_code": "PROJECTION_NOT_AVAILABLE",
                "source_watermark": None,
            },
            {
                "ledger_name": "规划账",
                "runtime_status": "UNAVAILABLE",
                "content_status": "UNKNOWN",
                "visibility": "FULL",
                "reason_code": "CAPABILITY_UNAVAILABLE",
                "source_watermark": None,
            },
        ]
    )
    registration = ledger_directory_workspace._validated_registration_state(
        directory_state
    )
    core = {
        "author_id": workspace.author_id,
        "project_id": workspace.project_id,
        "permission_profile": trusted["permission_profile"],
        "permission_policy_version": trusted["permission_policy_version"],
        "storage_generation": snapshot.generation_id or "author-workspace-empty-v1",
        "directory_registration": {
            "identity": registration["payload"]["directory_identity"],
            "version": registration["version"],
            "sha256": registration["sha256"],
        },
        "ledgers": ledgers,
    }
    document = {
        "contract": "LEDGER_CAPABILITY_SNAPSHOT",
        "version": VERSION,
        "snapshot_id": f"CAP-{_sha256_json(core)[:32]}",
        **core,
        "tool_contract_version": VERSION,
        "generated_at": "1970-01-01T00:00:00Z",
    }
    return validate_ledger_read_document(document)


def open_current_reader_session(
    workspace: AuthorWorkspace,
    trusted_execution_context: Mapping[str, Any],
) -> CurrentLedgerReadSession:
    """Read four logical keys once and build disposable in-memory indexes."""
    if not isinstance(workspace, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    trusted = _trusted_context(trusted_execution_context)
    snapshot = workspace.read_current_snapshot(list(SNAPSHOT_KEYS))
    directory_state = snapshot.read("ledger_directory")
    chapters_state = snapshot.read("chapters")
    chapter_index_state = snapshot.read("chapter_index")
    facts_state = snapshot.read("facts")
    chapters_by_id: dict[str, dict[str, Any]] = {}
    facts_by_id: dict[str, dict[str, Any]] = {}
    facts_by_revision: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    capability: dict[str, Any] | None = None
    source_error: str | None = None

    if directory_state is None:
        source_error = "DIRECTORY_NOT_INITIALIZED"
    else:
        try:
            ledger_directory_workspace._validated_registration_state(directory_state)
            if chapters_state is None and chapter_index_state is None:
                chapters: list[dict[str, Any]] = []
            elif chapters_state is None or chapter_index_state is None:
                raise ValueError("C1_WORKSPACE_STATE_MISSING")
            else:
                if chapters_state["version"] != chapter_index_state["version"]:
                    raise ValueError("C1_WORKSPACE_STATE_VERSION_DIVERGED")
                chapters, _ = chapter_workspace._validated_batch(
                    chapters_state["payload"],
                    chapter_index_state["payload"],
                )
            facts = (
                []
                if facts_state is None
                else factstore.validate_c4_v1_snapshot(facts_state["payload"])
            )
            chapters_by_id = {chapter["id"]: chapter for chapter in chapters}
            facts_by_id = {fact["id"]: fact for fact in facts}
            for fact in facts:
                if fact["status"] != factstore.STATUS_CONFIRMED:
                    continue
                ref = fact["chapter_revision_ref"]
                key = (
                    ref["chapter_id"],
                    ref["revision_no"],
                    ref["revision_text_sha256"],
                )
                facts_by_revision.setdefault(key, []).append(fact)
            for rows in facts_by_revision.values():
                rows.sort(key=lambda item: item["id"])
            capability = _capability_snapshot(
                workspace,
                snapshot,
                trusted,
                directory_state,
                chapters_state,
                facts_state,
            )
        except Exception:
            source_error = "SOURCE_CORRUPTED"

    return CurrentLedgerReadSession(
        workspace=workspace,
        snapshot=snapshot,
        execution_context=trusted,
        directory_state=copy.deepcopy(directory_state),
        chapters_state=copy.deepcopy(chapters_state),
        chapter_index_state=copy.deepcopy(chapter_index_state),
        facts_state=copy.deepcopy(facts_state),
        chapters_by_id=copy.deepcopy(chapters_by_id),
        facts_by_id=copy.deepcopy(facts_by_id),
        confirmed_facts_by_revision=copy.deepcopy(facts_by_revision),
        capability_snapshot=copy.deepcopy(capability),
        source_error=source_error,
    )


def _source_sort_key(item: dict[str, Any]) -> tuple[str, ...]:
    revision = item["revision"]
    revision_key = (
        f"integer:{revision:020d}"
        if isinstance(revision, int) and not isinstance(revision, bool)
        else f"string:{revision}"
    )
    return (
        item["source_kind"],
        item["logical_ledger_name"] or "",
        item["stable_id"],
        revision_key,
        item["role"],
        item["source_contract"],
        item["source_contract_version"],
        item["logical_content_sha256"],
    )


def _chapter_source(chapter: dict[str, Any], role: str) -> dict[str, Any]:
    ref = chapter["chapter_revision_ref"]
    return {
        "source_kind": "chapter_revision",
        "source_contract": "C1_CHAPTER_DOC",
        "source_contract_version": "v1",
        "logical_ledger_name": "章节账",
        "object_type": "chapter_revision",
        "stable_id": chapter["id"],
        "revision": ref["revision_no"],
        "logical_content_sha256": ref["revision_text_sha256"],
        "role": role,
        "binding_mode": "resolved_at_read",
        "retired_notice": False,
        "compiler_version": None,
        "input_basis_sha256": None,
    }


def _fact_source(
    fact: dict[str, Any],
    facts_state: dict[str, Any],
    role: str,
) -> dict[str, Any]:
    return {
        "source_kind": "ledger_entry",
        "source_contract": "C4_FACT_QUERY",
        "source_contract_version": "v1",
        "logical_ledger_name": "事实账",
        "object_type": "fact_record",
        "stable_id": fact["id"],
        "revision": f"workspace-facts-v{facts_state['version']}",
        "logical_content_sha256": _sha256_json(fact),
        "role": role,
        "binding_mode": "resolved_at_read",
        "retired_notice": False,
        "compiler_version": None,
        "input_basis_sha256": None,
    }


def _directory_source(capability: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_kind": "directory_capability_snapshot",
        "source_contract": "LEDGER_CAPABILITY_SNAPSHOT",
        "source_contract_version": VERSION,
        "logical_ledger_name": None,
        "object_type": "ledger_capability_snapshot",
        "stable_id": capability["snapshot_id"],
        "revision": capability["storage_generation"],
        "logical_content_sha256": _sha256_json(capability),
        "role": "directory_capability",
        "binding_mode": "resolved_at_read",
        "retired_notice": False,
        "compiler_version": None,
        "input_basis_sha256": None,
    }


def _base_response(
    session: CurrentLedgerReadSession,
    request: dict[str, Any],
    *,
    status: str,
    reason_code: str | None,
    message: str,
    data: Any,
    empty_scope: str | None,
    source_manifest: list[dict[str, Any]],
    business_items: int,
    unauthorized: bool = False,
) -> dict[str, Any]:
    context = request["execution_context"]
    manifest = sorted(copy.deepcopy(source_manifest), key=_source_sort_key)
    response = {
        "contract": "LEDGER_READ_RESPONSE",
        "version": VERSION,
        "status": status,
        "reason_code": reason_code,
        "message": message,
        "request_id": context["request_id"],
        "tool": request["tool"],
        "basis_mode": request["basis"]["mode"],
        "data": copy.deepcopy(data),
        "empty_scope": empty_scope,
        "receipt": {
            "author_id": context["author_id"] if unauthorized else session.author_id,
            "project_id": context["project_id"] if unauthorized else session.project_id,
            "permission_policy_version": context["permission_policy_version"],
            "tool_contract_version": VERSION,
            "storage_generation": (
                "masked" if unauthorized else session.storage_generation
            ),
            "capability_snapshot_id": (
                None
                if unauthorized or session.capability_snapshot is None
                else session.capability_snapshot["snapshot_id"]
            ),
            "source_manifest": [] if reason_code == "UNAUTHORIZED" else manifest,
            "basis_sha256": "0" * 64,
        },
        "limits": {
            "policy_version": LIMIT_POLICY_VERSION,
            "business_items": business_items,
            "response_bytes": 0,
            "truncated": False,
        },
    }
    response["receipt"]["basis_sha256"] = _contract_validator().basis_sha256(response)
    for _ in range(8):
        size = len(canonical_json(response).encode("utf-8"))
        if response["limits"]["response_bytes"] == size:
            break
        response["limits"]["response_bytes"] = size
    return response


def _final_response(
    session: CurrentLedgerReadSession,
    request: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    response = _base_response(session, request, **kwargs)
    if (
        response["limits"]["business_items"] > MAX_BUSINESS_ITEMS
        or response["limits"]["response_bytes"] > MAX_RESPONSE_BYTES
    ):
        response = _base_response(
            session,
            request,
            status="REJECTED",
            reason_code="RESULT_TOO_LARGE",
            message="读取结果超过当前整批返回上限。",
            data=None,
            empty_scope=None,
            source_manifest=[],
            business_items=0,
        )
    return validate_ledger_read_document(response)


def _rejected(
    session: CurrentLedgerReadSession,
    request: dict[str, Any],
    reason_code: str,
    message: str,
    *,
    unauthorized: bool = False,
    source_manifest: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return _final_response(
        session,
        request,
        status="REJECTED",
        reason_code=reason_code,
        message=message,
        data=None,
        empty_scope=None,
        source_manifest=source_manifest or [],
        business_items=0,
        unauthorized=unauthorized,
    )


def current_advanced_response(
    session: CurrentLedgerReadSession,
    request: Mapping[str, Any],
) -> dict[str, Any]:
    checked = validate_ledger_read_document(request)
    return _rejected(
        session,
        checked,
        "CURRENT_ADVANCED",
        "读取期间 current generation 已前进，本次结果不交付。",
    )


def execute_read(
    session: CurrentLedgerReadSession,
    request: Mapping[str, Any],
) -> dict[str, Any]:
    """Execute one validated request against an already-open current session."""
    if not isinstance(session, CurrentLedgerReadSession):
        _fail("CURRENT_LEDGER_READ_SESSION_REQUIRED")
    checked = validate_ledger_read_document(request)
    context = checked["execution_context"]
    expected = {
        **session.execution_context,
        "author_id": session.author_id,
        "project_id": session.project_id,
    }
    scope_mismatch = any(context[field] != expected[field] for field in expected)
    if checked["basis"]["mode"] != "current_at_start":
        return _rejected(
            session,
            checked,
            "INVALID_PIN_SET",
            "AuthorWorkspace 当前没有公开 pinned generation 读取能力。",
            unauthorized=scope_mismatch,
            source_manifest=checked["basis"]["source_manifest"],
        )
    if scope_mismatch:
        return _rejected(
            session,
            checked,
            "UNAUTHORIZED",
            "当前读取请求不属于这份作者项目能力句柄。",
            unauthorized=True,
        )
    if not session.is_current():
        return current_advanced_response(session, checked)

    tool = checked["tool"]
    if tool == "get_longline_box_status":
        return _rejected(
            session,
            checked,
            "PROJECTION_NOT_AVAILABLE",
            "长线 BOX 合法投影入口尚未开放。",
        )
    if tool == "get_character_knowledge_edges_as_of":
        return _rejected(
            session,
            checked,
            "FORMAL_CONTRACT_NOT_AVAILABLE",
            "知情边读取面尚未正式开放。",
        )
    if tool == "get_character_state_as_of":
        return _rejected(
            session,
            checked,
            "CAPABILITY_UNAVAILABLE",
            "人物时点状态 reader 尚未接入这一 current 会话。",
        )
    if session.source_error is not None:
        status = (
            "ERROR"
            if session.source_error in {"DIRECTORY_NOT_INITIALIZED", "SOURCE_CORRUPTED"}
            else "REJECTED"
        )
        return _final_response(
            session,
            checked,
            status=status,
            reason_code=session.source_error,
            message="当前 AuthorWorkspace 来源不能形成合法公共读取回执。",
            data=None,
            empty_scope=None,
            source_manifest=[],
            business_items=0,
        )

    assert session.capability_snapshot is not None
    if tool == "get_ledger_directory":
        return _final_response(
            session,
            checked,
            status="OK",
            reason_code=None,
            message="已读取十账 current 能力目录。",
            data={"capability_snapshot": session.capability_snapshot},
            empty_scope=None,
            source_manifest=[_directory_source(session.capability_snapshot)],
            business_items=10,
        )

    selector = checked["selector"]
    if tool == "get_chapter_evidence_slice":
        chapter = session.chapters_by_id.get(selector["chapter_id"])
        if chapter is None:
            return _rejected(
                session,
                checked,
                "ENTRY_NOT_FOUND",
                "没有找到点名的 current 章节。",
            )
        ref = chapter["chapter_revision_ref"]
        key = (ref["chapter_id"], ref["revision_no"], ref["revision_text_sha256"])
        facts = session.confirmed_facts_by_revision.get(key, [])
        if not facts:
            return _final_response(
                session,
                checked,
                status="EMPTY",
                reason_code="NO_MATCHING_ENTRIES",
                message="这个 current 章节修订没有匹配的已确认事实。",
                data=None,
                empty_scope="current_confirmed_facts_for_selected_chapter_revision",
                source_manifest=[_chapter_source(chapter, "selected_chapter")],
                business_items=0,
            )
        chapter_projection = copy.deepcopy(chapter)
        if not selector["include_chapter_text"]:
            chapter_projection.pop("text", None)
        fact_state = session.facts_state
        assert fact_state is not None
        sources = [_chapter_source(chapter, "selected_chapter")]
        sources.extend(
            _fact_source(fact, fact_state, "matched_confirmed_fact") for fact in facts
        )
        return _final_response(
            session,
            checked,
            status="OK",
            reason_code=None,
            message=f"已读取 1 个章节修订和 {len(facts)} 条匹配事实。",
            data={
                "chapter": chapter_projection,
                "confirmed_facts": facts,
            },
            empty_scope=None,
            source_manifest=sources,
            business_items=1 + len(facts),
        )

    if tool == "get_ledger_entries_by_ref":
        ledger_name = selector["ledger_name"]
        if ledger_name in UNAVAILABLE_ENTRY_LEDGERS:
            return _rejected(
                session,
                checked,
                "CAPABILITY_UNAVAILABLE",
                "这本设定账还没有接入同一 AuthorWorkspace current 会话。",
            )
        if ledger_name not in OPEN_ENTRY_PROFILES:
            return _rejected(
                session,
                checked,
                "READ_PROFILE_NOT_FROZEN",
                "这个账本没有冻结可用的通用点读档位。",
            )
        refs = selector["refs"]
        if len(refs) > MAX_REFS:
            return _rejected(
                session,
                checked,
                "RESULT_TOO_LARGE",
                "一次点读最多接收 50 个稳定引用。",
            )
        source_rows: list[dict[str, Any]] = []
        entries: list[dict[str, Any]] = []
        for stable_id in refs:
            if ledger_name == "章节账":
                entry = session.chapters_by_id.get(stable_id)
                if entry is None:
                    return _rejected(
                        session,
                        checked,
                        "ENTRY_NOT_FOUND",
                        "至少一个章节稳定引用不存在，整批不返回。",
                    )
                projection = copy.deepcopy(entry)
                projection.pop("text", None)
                entries.append(
                    {
                        "ledger_name": ledger_name,
                        "id": stable_id,
                        "read_profile": selector["read_profile"],
                        "entry": projection,
                    }
                )
                source_rows.append(_chapter_source(entry, "requested_entry"))
            else:
                entry = session.facts_by_id.get(stable_id)
                if entry is None:
                    return _rejected(
                        session,
                        checked,
                        "ENTRY_NOT_FOUND",
                        "至少一个事实稳定引用不存在，整批不返回。",
                    )
                entries.append(
                    {
                        "ledger_name": ledger_name,
                        "id": stable_id,
                        "read_profile": selector["read_profile"],
                        "entry": copy.deepcopy(entry),
                    }
                )
                assert session.facts_state is not None
                source_rows.append(
                    _fact_source(entry, session.facts_state, "requested_entry")
                )
        return _final_response(
            session,
            checked,
            status="OK",
            reason_code=None,
            message=f"已按请求顺序读取 {len(entries)} 条记录。",
            data={"entries": entries},
            empty_scope=None,
            source_manifest=source_rows,
            business_items=len(entries),
        )

    _fail("LEDGER_READ_TOOL_UNSUPPORTED")


__all__ = [
    "CurrentLedgerReadSession",
    "LedgerReadRuntimeError",
    "canonical_json",
    "current_advanced_response",
    "execute_read",
    "open_current_reader_session",
    "validate_ledger_read_document",
]
