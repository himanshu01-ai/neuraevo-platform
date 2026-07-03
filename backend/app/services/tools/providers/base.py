"""Tool provider contract (Sprint 11.1 — abstraction only).

Defines the replaceable interface that every future tool will implement. This
sprint ships ONLY the abstraction: no concrete tool (Gmail, Calendar, Browser,
Slack, WhatsApp, GitHub, …), no HTTP client, no SDK, no OAuth, and no execution
logic. Concrete providers — added in later sprints — own all tool-specific code
behind this interface, isolated from services, repositories, models, and
routers.
"""

from abc import ABC, abstractmethod

from app.services.tools.models import (
    ToolExecutionRequest,
    ToolExecutionResult,
)


class ToolProvider(ABC):
    """Replaceable strategy that validates and executes a single tool.

    Concrete implementations (added in a later sprint) live behind this
    interface so the rest of the system stays tool-agnostic. ``tool_name`` and
    ``description`` identify/describe the tool; ``validate`` checks a request
    before execution; ``execute`` performs it and returns a provider-independent
    :class:`ToolExecutionResult`. This sprint provides only the abstract
    contract — there is no concrete provider yet.
    """

    tool_name: str
    description: str

    @abstractmethod
    def validate(self, request: ToolExecutionRequest) -> None:
        """Validate ``request`` for this tool, raising on invalid input.

        Concrete providers raise a domain error when the request is not
        executable; a successful return means the request is well-formed.
        """

    @abstractmethod
    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        """Execute the tool for ``request`` and return the result.

        Returns a provider-independent :class:`ToolExecutionResult`; no
        provider/SDK object crosses this boundary.
        """
