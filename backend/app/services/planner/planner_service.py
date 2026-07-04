"""Planner Service (Sprint 11.4 — stateless delegator).

Receives a user request, delegates plan construction to an injected
:class:`PlannerProvider`, and returns the provider's :class:`ExecutionPlan`
unchanged. That is its entire responsibility.

It performs NO tool execution, permission checks, registry access, retries,
logging, or runtime coordination. The provider is injected via the constructor
(never instantiated here). No concrete provider exists yet — real planning is a
later sprint.
"""

from app.services.planner.models import ExecutionPlan
from app.services.planner.providers.base import PlannerProvider


class PlannerService:
    """Delegates plan creation to an injected provider.

    Stateless: it holds only the injected provider and owns no session,
    repository, or cache. A pure pass-through to the provider seam, so provider
    replacement requires no change here.
    """

    def __init__(self, provider: PlannerProvider) -> None:
        self.provider = provider

    def create_plan(self, user_request: str) -> ExecutionPlan:
        """Return the provider's plan for ``user_request``, unchanged.

        The request is passed to the provider untouched and the returned plan is
        handed back to the caller as-is. Provider exceptions propagate
        unchanged. Nothing is executed.
        """
        return self.provider.create_plan(user_request)
