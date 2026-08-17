"""Collaboration context (Sprint 16.9 — maintain live collaboration state).

Defines :class:`CollaborationContext`, the component that maintains the *live* state
of an ongoing coordination: the participating agents, the delegated tasks, the
ownership of each task, and plain coordination metadata. It records what the
:class:`~app.services.ai_employee.coordination.coordinator.AgentCoordinator` decides
and produces an immutable :class:`CoordinationContext` snapshot on demand.

It is a plain in-memory ledger: it decides nothing about *which* agent handles work
(the resolver and policy decide) and runs nothing (the delegator delegates to the
:class:`AIEmployee`). It never touches the Workflow Coordinator, a capability, a
repository, a database, a thread, or the network. Its only state is the in-memory
ledger, kept in deterministic insertion order. Strictly additive to Sprints
1.x–16.8, whose modules are left untouched.
"""

from typing import Any, Dict, List, Optional

from app.services.ai_employee.coordination.models import (
    CoordinationContext,
    TaskNotFoundError,
)


class CollaborationContext:
    """In-memory ledger of collaboration state (ledger only, no decisions).

    Tracks participating agent ids, delegated task ids, and the task -> agent
    ownership map, all in deterministic insertion order. ``add_agent`` records a
    participant; ``record_delegation`` records a delegated task and its owner;
    ``remove_task`` drops a delegated task (raising :class:`TaskNotFoundError` when
    it is absent); ``owner_of`` looks up a task's owner; ``agents``/``tasks`` read the
    ledgers; and ``snapshot`` captures an immutable :class:`CoordinationContext`. It
    resolves, delegates, and executes nothing.
    """

    def __init__(
        self,
        context_id: str = "collaboration",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.context_id = context_id
        self._agent_ids: List[str] = []
        self._task_ids: List[str] = []
        self._ownership: Dict[str, str] = {}
        self._metadata: Dict[str, Any] = dict(metadata or {})

    # --- recording -------------------------------------------------------
    def add_agent(self, agent_id: str) -> None:
        """Record ``agent_id`` as a participant (idempotent, keeps first position)."""
        if agent_id not in self._agent_ids:
            self._agent_ids.append(agent_id)

    def record_delegation(self, task_id: str, agent_id: str) -> None:
        """Record that ``task_id`` was delegated to ``agent_id`` (owner, participant).

        Adds the task to the delegated ledger (first delegation only), sets or
        updates its owner, and records the owner as a participant. Re-delegating an
        existing task updates its owner without duplicating the task id.
        """
        if task_id not in self._task_ids:
            self._task_ids.append(task_id)
        self._ownership[task_id] = agent_id
        self.add_agent(agent_id)

    def remove_task(self, task_id: str) -> str:
        """Drop the delegated ``task_id`` and return the ``agent_id`` that owned it.

        Raises :class:`TaskNotFoundError` when the task is not tracked. The owning
        agent stays a participant; only the task and its ownership are removed.
        """
        if task_id not in self._ownership:
            raise TaskNotFoundError(f"no such delegated task: {task_id}")
        owner = self._ownership.pop(task_id)
        self._task_ids.remove(task_id)
        return owner

    # --- reads -----------------------------------------------------------
    def owner_of(self, task_id: str) -> Optional[str]:
        """Return the ``agent_id`` that owns ``task_id``, or ``None`` if untracked."""
        return self._ownership.get(task_id)

    def agents(self) -> List[str]:
        """Return the participating agent ids in registration order."""
        return list(self._agent_ids)

    def tasks(self) -> List[str]:
        """Return the delegated task ids in delegation order."""
        return list(self._task_ids)

    def snapshot(self) -> CoordinationContext:
        """Return an immutable :class:`CoordinationContext` capture of the state."""
        return CoordinationContext(
            context_id=self.context_id,
            agent_ids=list(self._agent_ids),
            task_ids=list(self._task_ids),
            ownership=dict(self._ownership),
            context_metadata=dict(self._metadata),
        )
