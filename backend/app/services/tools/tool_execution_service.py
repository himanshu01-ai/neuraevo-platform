"""Tool Execution Service (Sprint 11.1 — stateless delegator).

Receives a :class:`ToolExecutionRequest`, delegates execution to an injected
:class:`ToolProvider`, and returns the provider's
:class:`ToolExecutionResult` unchanged. That is its entire responsibility.

It performs NO planning, permissions, retries, repository usage, AI logic, or
runtime coordination. The provider is injected via the constructor (never
instantiated here). No concrete provider exists yet — real tools and their
execution are later sprints.
"""

from app.services.tools.models import (
    ToolExecutionRequest,
    ToolExecutionResult,
)
from app.services.tools.providers.base import ToolProvider


class ToolExecutionService:
    """Delegates tool execution to an injected provider.

    Stateless: it holds only the injected provider and owns no session,
    repository, or cache. A pure pass-through to the provider seam, so provider
    replacement requires no change here.
    """

    def __init__(self, provider: ToolProvider) -> None:
        self.provider = provider

    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        """Return the provider's result for ``request``, unchanged.

        The request is passed to the provider untouched and the returned result
        is handed back to the caller as-is. Provider exceptions propagate
        unchanged.
        """
        return self.provider.execute(request)
