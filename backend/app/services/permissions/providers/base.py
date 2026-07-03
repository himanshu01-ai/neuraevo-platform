"""Permission provider contract (Sprint 11.3 — abstraction only).

Defines the replaceable interface that future permission strategies will
implement. This sprint ships ONLY the abstraction: no concrete permission
logic, no user-approval flow, no HTTP client, no SDK, no OAuth, and no
execution. Concrete providers — added in later sprints — own all decision
logic behind this interface, isolated from services, repositories, models, and
routers.
"""

from abc import ABC, abstractmethod

from app.services.permissions.models import (
    PermissionRequest,
    PermissionResult,
)


class PermissionProvider(ABC):
    """Replaceable strategy that decides whether a tool call is permitted.

    Concrete implementations (added in a later sprint) live behind this
    interface so the rest of the system stays policy-agnostic. ``name``
    identifies the provider; ``check_permission`` evaluates a request and
    returns a provider-independent :class:`PermissionResult`. This sprint
    provides only the abstract contract — there is no concrete provider yet.
    """

    name: str

    @abstractmethod
    def check_permission(
        self, request: PermissionRequest
    ) -> PermissionResult:
        """Decide whether ``request`` is permitted.

        Returns a provider-independent :class:`PermissionResult`; no
        provider/SDK object crosses this boundary. Performs no tool execution.
        """
