"""Tools package (Sprint 11.1 — Agent Execution Core foundation).

Ships ONLY the tool-execution framework: the provider-independent
:class:`ToolExecutionRequest` / :class:`ToolExecutionResult` models, the
abstract :class:`ToolProvider` contract, and the stateless
:class:`ToolExecutionService` delegator. No concrete tool, HTTP client, SDK,
OAuth, permissions, planner, or registry — those belong to later sprints.
"""

from app.services.tools.models import (
    ToolExecutionRequest,
    ToolExecutionResult,
)
from app.services.tools.providers import ToolProvider
from app.services.tools.tool_execution_service import ToolExecutionService

__all__ = [
    "ToolExecutionService",
    "ToolProvider",
    "ToolExecutionRequest",
    "ToolExecutionResult",
]
