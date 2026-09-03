"""Trusted AuthorWorkspace reader -> CCZ-126 adapter -> existing C9 v2 root."""

from __future__ import annotations

import copy
from typing import Any, Mapping, NoReturn

from . import c9_ledger_read_adapter as adapter
from . import ledger_read_runtime
from . import unified_retrieval_core as c9
from .workspace import AuthorWorkspace


class UnifiedRetrievalCompositionError(ValueError):
    """The trusted product composition does not match the bound workspace."""


def _fail(code: str) -> NoReturn:
    raise UnifiedRetrievalCompositionError(code)


def _validate_composition_scope(
    workspace: AuthorWorkspace,
    request: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(workspace, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    checked = c9.validate_request(request)
    if checked["basis_mode"] != "current_at_start":
        _fail("COMPOSITION_CURRENT_ONLY")
    scope = checked["scope"]
    if (
        scope["author_id"] != workspace.author_id
        or scope["project_id"] != workspace.project_id
    ):
        _fail("COMPOSITION_SCOPE_MISMATCH")
    for need in checked["source_needs"]:
        if need["source_contract"] != "LEDGER_READ_TOOL_CONTRACT":
            _fail(f"COMPOSITION_SOURCE_CONTRACT_UNSUPPORTED:{need['need_id']}")
        adapter.parse_object_ref(need["object_ref"])
    return checked


def _advanced_outcomes(
    session: ledger_read_runtime.CurrentLedgerReadSession,
    request: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        adapter.current_advanced_outcome(session, request, need)
        for need in request["source_needs"]
    ]


def run_current_retrieval(
    workspace: AuthorWorkspace,
    trusted_execution_context: Mapping[str, Any],
    c9_request: Mapping[str, Any],
) -> dict[str, Any]:
    """Run one current-only retrieval without accepting caller-supplied trust hooks."""
    checked_request = _validate_composition_scope(workspace, c9_request)
    plan = c9.prepare_plan(checked_request)
    session = ledger_read_runtime.open_current_reader_session(
        workspace,
        trusted_execution_context,
    )
    outcomes = [
        adapter.read_need(session, checked_request, need)
        for need in checked_request["source_needs"]
    ]
    if not session.is_current():
        outcomes = _advanced_outcomes(session, checked_request)

    registry = adapter.trusted_source_registry()
    result = c9.compile_result(
        checked_request,
        plan,
        outcomes,
        registry,
    )
    if not session.is_current():
        outcomes = _advanced_outcomes(session, checked_request)
        result = c9.compile_result(
            checked_request,
            plan,
            outcomes,
            registry,
        )
    return copy.deepcopy(
        c9.validate_result(
            result,
            checked_request,
            plan,
            outcomes,
            registry,
        )
    )


__all__ = ["UnifiedRetrievalCompositionError", "run_current_retrieval"]
