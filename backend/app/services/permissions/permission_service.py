"""Permission Service (Sprint 11.3 — stateless delegator).

Receives a :class:`PermissionRequest`, delegates the decision to an injected
:class:`PermissionProvider`, and returns the provider's
:class:`PermissionResult` unchanged. That is its entire responsibility.

It performs NO tool execution, planning, user-approval flow, retries, logging,
repository usage, or runtime coordination. The provider is injected via the
constructor (never instantiated here). No concrete provider exists yet — real
permission decisions are later sprints.
"""

from app.services.permissions.models import (
    PermissionRequest,
    PermissionResult,
)
from app.services.permissions.providers.base import PermissionProvider


class PermissionService:
    """Delegates permission checks to an injected provider.

    Stateless: it holds only the injected provider and owns no session,
    repository, or cache. A pure pass-through to the provider seam, so provider
    replacement requires no change here.
    """

    def __init__(self, provider: PermissionProvider) -> None:
        self.provider = provider

    def check_permission(
        self, request: PermissionRequest
    ) -> PermissionResult:
        """Return the provider's decision for ``request``, unchanged.

        The request is passed to the provider untouched and the returned result
        is handed back to the caller as-is. Provider exceptions propagate
        unchanged.
        """
        return self.provider.check_permission(request)
