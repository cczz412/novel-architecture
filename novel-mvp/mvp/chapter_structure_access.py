"""R01 provider types only. Stage two must supply actual host authorization."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, ContextManager, Mapping, Protocol

from .chapter_structure_contract import StructureError

ActionGrant = Mapping[str, object]


class StructureAccessContext:
    """No JSON, same-name class or client constructor can mint a capability."""

    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise StructureError("CAPABILITY_UNAVAILABLE")


class StructureAccessProvider(ABC):
    @abstractmethod
    def resolve_author_session(self, *args, **kwargs): ...

    @abstractmethod
    def resolve_workflow_permit(self, *args, **kwargs): ...

    @abstractmethod
    def resolve_permission_snapshot(self, *args, **kwargs): ...

    @abstractmethod
    def issue_action_grant(self, *args, **kwargs) -> ActionGrant: ...

    @abstractmethod
    def authorize_action(self, *args, **kwargs): ...

    @abstractmethod
    def with_current_authorization(
        self, *args, **kwargs
    ) -> ContextManager[Callable]: ...


class _BoundAccess(Protocol):
    """Private host binding type, not a JSON record or a new public API."""

    provider: StructureAccessProvider
    kernel: Any
    actor_ref: str
    actor_kind: str
    action_grant_ref: str
    access_basis_sha256: str


def require_bound_access(
    workspace, access_context, action_grant, request
) -> _BoundAccess:
    """Fail before probing objects. No provider registration/issuer in stage one."""
    raise StructureError("CAPABILITY_UNAVAILABLE")
