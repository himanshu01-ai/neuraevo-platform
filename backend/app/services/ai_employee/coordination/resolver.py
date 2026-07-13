"""Agent resolver (Sprint 16.9 — resolve the most suitable agents, configurable).

Defines :class:`AgentResolver`, the configurable component that resolves *which*
registered agents are suitable for a given :class:`AgentTask` and ranks them
best-first. Resolution filters candidates by the configured criteria — availability
(:class:`AgentStatus`), role, and capabilities — and ranks the survivors by
priority (higher first), breaking ties by ``agent_id`` for a fully deterministic
order.

The resolver *selects candidates*; it decides no final assignment (that is the
coordination policy's job), delegates nothing, and executes nothing. It never
touches the Workflow Coordinator, a capability, a repository, a database, a thread,
or the network. Deterministic and stateless. Strictly additive to Sprints
1.x–16.8, whose modules are left untouched.
"""

from typing import List, Optional

from app.services.ai_employee.coordination.models import (
    AgentProfile,
    AgentStatus,
    AgentTask,
)


class AgentResolver:
    """Filters and ranks candidate agents for a task (configurable, deterministic).

    Constructed with three configurable criteria: ``require_available`` (keep only
    :class:`AgentStatus.AVAILABLE` agents; default ``True``), ``require_role`` (when
    the task names a ``required_role``, keep only agents whose role matches; default
    ``True``), and ``require_all_capabilities`` (when ``True``, keep only agents whose
    capabilities cover *all* the task's ``required_capabilities``; when ``False``,
    keep agents that cover *at least one*; default ``True``). ``resolve`` returns the
    surviving candidates ranked by priority (highest first, ties broken by
    ``agent_id``); ``resolve_best`` returns the single top candidate or ``None``. It
    assigns, delegates, and executes nothing.
    """

    def __init__(
        self,
        require_available: bool = True,
        require_role: bool = True,
        require_all_capabilities: bool = True,
    ) -> None:
        self.require_available = require_available
        self.require_role = require_role
        self.require_all_capabilities = require_all_capabilities

    def resolve(
        self, task: AgentTask, agents: List[AgentProfile]
    ) -> List[AgentProfile]:
        """Return the agents suitable for ``task``, ranked best-first.

        Filters ``agents`` by the configured availability/role/capability criteria,
        then sorts the survivors by descending ``priority`` with an ascending
        ``agent_id`` tie-break so the order is deterministic. Returns an empty list
        when none is suitable.
        """
        suitable = [
            agent for agent in agents if self._is_suitable(task, agent)
        ]
        return sorted(
            suitable, key=lambda agent: (-agent.priority, agent.agent_id)
        )

    def resolve_best(
        self, task: AgentTask, agents: List[AgentProfile]
    ) -> Optional[AgentProfile]:
        """Return the single most suitable agent for ``task``, or ``None`` if none."""
        ranked = self.resolve(task, agents)
        return ranked[0] if ranked else None

    # --- criteria --------------------------------------------------------
    def _is_suitable(self, task: AgentTask, agent: AgentProfile) -> bool:
        """Return whether ``agent`` passes every configured criterion for ``task``."""
        if self.require_available and agent.status != AgentStatus.AVAILABLE:
            return False
        if (
            self.require_role
            and task.required_role
            and agent.role != task.required_role
        ):
            return False
        return self._has_capabilities(task, agent)

    def _has_capabilities(
        self, task: AgentTask, agent: AgentProfile
    ) -> bool:
        """Return whether ``agent`` covers the task's required capabilities.

        No required capability is trivially satisfied. Otherwise, when
        ``require_all_capabilities`` is set the agent must cover every required
        capability; when it is not, covering at least one suffices.
        """
        required = task.required_capabilities
        if not required:
            return True
        owned = set(agent.capabilities)
        if self.require_all_capabilities:
            return owned.issuperset(required)
        return any(capability in owned for capability in required)
