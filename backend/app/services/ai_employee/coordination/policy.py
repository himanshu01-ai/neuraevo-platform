"""Coordination policies (Sprint 16.9 — configurable delegation rules).

Defines the :class:`CoordinationPolicy` abstraction and its three implementations,
which decide *which* of the resolver's ranked candidate agents actually receive a
task:

* :class:`SingleAgentPolicy` — assign the whole task to the single most suitable
  candidate (the resolver's top pick).
* :class:`CollaborativePolicy` — fan the task out to several candidates at once
  (all of them, or up to a configurable bound).
* :class:`PriorityPolicy` — assign the task to the one candidate with the highest
  ``priority`` (ties broken deterministically by ``agent_id``).

Each policy is deterministic and stateless and returns an immutable
:class:`CoordinationPolicyResult` — it resolves nothing (the candidates are given),
delegates nothing, and executes nothing. Strictly additive to Sprints 1.x–16.8,
whose modules are left untouched.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.services.ai_employee.coordination.models import (
    AgentProfile,
    AgentTask,
    CoordinationPolicyResult,
)


class CoordinationPolicy(ABC):
    """Abstraction that decides which candidates receive a task (no execution).

    An implementation returns a :class:`CoordinationPolicyResult` for an
    :class:`AgentTask` and the resolver's ranked ``candidates`` — which agent ids are
    selected and whether the decision is collaborative. Implementations must be
    deterministic and must not resolve, delegate, or execute anything.
    """

    @abstractmethod
    def decide(
        self, task: AgentTask, candidates: List[AgentProfile]
    ) -> CoordinationPolicyResult:
        """Return the coordination decision for ``task`` over ``candidates``."""


class SingleAgentPolicy(CoordinationPolicy):
    """Policy that assigns the whole task to the single most suitable candidate.

    ``decide`` selects the resolver's top-ranked candidate (the first in the given
    order) and never fans out. Selects nothing when there is no candidate.
    Deterministic and stateless.
    """

    _POLICY_NAME = "SingleAgentPolicy"

    def decide(
        self, task: AgentTask, candidates: List[AgentProfile]
    ) -> CoordinationPolicyResult:
        """Return a single-agent decision (the top candidate, or none)."""
        if not candidates:
            return CoordinationPolicyResult(
                policy=self._POLICY_NAME,
                selected_agent_ids=[],
                collaborative=False,
                reason="no suitable agent",
            )
        chosen = candidates[0]
        return CoordinationPolicyResult(
            policy=self._POLICY_NAME,
            selected_agent_ids=[chosen.agent_id],
            collaborative=False,
            reason=f"assigned to most suitable agent {chosen.agent_id}",
        )


class CollaborativePolicy(CoordinationPolicy):
    """Policy that fans the task out to several candidates at once.

    Constructed with an optional ``max_agents`` bound (``None`` means all
    candidates). ``decide`` selects the first ``max_agents`` candidates (in the
    resolver's ranked order) and marks the decision collaborative when more than one
    agent is selected. Selects nothing when there is no candidate. Deterministic and
    stateless.
    """

    _POLICY_NAME = "CollaborativePolicy"

    def __init__(self, max_agents: Optional[int] = None) -> None:
        self.max_agents = None if max_agents is None else max(max_agents, 0)

    def decide(
        self, task: AgentTask, candidates: List[AgentProfile]
    ) -> CoordinationPolicyResult:
        """Return a collaborative decision over the (bounded) candidate set."""
        selected = (
            candidates
            if self.max_agents is None
            else candidates[: self.max_agents]
        )
        selected_ids = [agent.agent_id for agent in selected]
        return CoordinationPolicyResult(
            policy=self._POLICY_NAME,
            selected_agent_ids=selected_ids,
            collaborative=len(selected_ids) > 1,
            reason=f"assigned to {len(selected_ids)} collaborating agent(s)",
        )


class PriorityPolicy(CoordinationPolicy):
    """Policy that assigns the task to the single highest-priority candidate.

    ``decide`` selects the candidate with the greatest ``priority`` regardless of the
    incoming order, breaking ties by ``agent_id`` for determinism, and never fans
    out. Selects nothing when there is no candidate. Deterministic and stateless.
    """

    _POLICY_NAME = "PriorityPolicy"

    def decide(
        self, task: AgentTask, candidates: List[AgentProfile]
    ) -> CoordinationPolicyResult:
        """Return a single-agent decision for the highest-priority candidate."""
        if not candidates:
            return CoordinationPolicyResult(
                policy=self._POLICY_NAME,
                selected_agent_ids=[],
                collaborative=False,
                reason="no suitable agent",
            )
        # Highest priority first, ties broken by the smallest ``agent_id`` — the
        # same deterministic ordering the resolver applies.
        chosen = sorted(
            candidates, key=lambda agent: (-agent.priority, agent.agent_id)
        )[0]
        return CoordinationPolicyResult(
            policy=self._POLICY_NAME,
            selected_agent_ids=[chosen.agent_id],
            collaborative=False,
            reason=(
                f"assigned to highest-priority agent {chosen.agent_id} "
                f"(priority {chosen.priority})"
            ),
        )
