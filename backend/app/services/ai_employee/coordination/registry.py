"""Agent registry (Sprint 16.9 — maintain the roster of available AI Employees).

Defines :class:`AgentRegistry`, the component that maintains the set of AI
Employees available for coordination. It supports ``register`` (add or update an
agent), ``unregister`` (remove one), ``find`` (look one up), and ``list`` (the full
roster). It is a plain in-memory roster: it holds registered
:class:`AgentProfile`\\ s in deterministic registration order and decides nothing
about *which* agent handles work (that is the resolver's and policy's job).

It performs no resolution, no delegation, and no execution; it never touches the
Workflow Coordinator, a capability, a repository, a database, a thread, or the
network. Its only state is the in-memory roster. Strictly additive to Sprints
1.x–16.8, whose modules are left untouched.
"""

from typing import Dict, List, Optional

from app.services.ai_employee.coordination.models import (
    AgentNotFoundError,
    AgentProfile,
)


class AgentRegistry:
    """In-memory roster of registered agents (roster only, no decisions).

    Holds :class:`AgentProfile`\\ s keyed by ``agent_id`` in registration order.
    ``register`` adds a new agent or replaces an existing one with the same id;
    ``unregister`` removes one (raising :class:`AgentNotFoundError` when it is
    absent); ``find`` returns an agent or ``None``; and ``list`` returns the full
    roster in registration order. It resolves, delegates, and executes nothing.
    """

    def __init__(self) -> None:
        self._agents: Dict[str, AgentProfile] = {}

    def register(self, agent: AgentProfile) -> AgentProfile:
        """Register ``agent`` (adding it, or replacing one with the same id).

        Re-registering an existing ``agent_id`` replaces its profile while keeping
        the agent's original position in the roster, so registration order stays
        deterministic. Returns the registered agent.
        """
        self._agents[agent.agent_id] = agent
        return agent

    def unregister(self, agent_id: str) -> AgentProfile:
        """Remove and return the agent with ``agent_id``.

        Raises :class:`AgentNotFoundError` when no such agent is registered.
        """
        agent = self._agents.pop(agent_id, None)
        if agent is None:
            raise AgentNotFoundError(f"no such agent: {agent_id}")
        return agent

    def find(self, agent_id: str) -> Optional[AgentProfile]:
        """Return the agent with ``agent_id``, or ``None`` when it is not registered."""
        return self._agents.get(agent_id)

    def list(self) -> List[AgentProfile]:
        """Return every registered agent in deterministic registration order."""
        return list(self._agents.values())
