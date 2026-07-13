"""Agent coordinator (Sprint 16.9 — coordinate collaboration; never execute).

Defines :class:`AgentCoordinator`, the coordinator of the Agent Coordination
Platform. It coordinates the collaboration of multiple AI Employees, following the
flow ``AgentCoordinator -> {AgentRegistry, AgentResolver, CoordinationPolicy,
TaskDelegator, CollaborationContext}`` (with the Sprint 16.4 Notification engine as
an integration) and deciding *which* agent handles *which* work:

    register_agent   (add an agent to the registry + the collaboration ledger)
    delegate_task    (resolve -> policy -> assign the task to one agent)
    coordinate       (resolve -> policy -> assign to one/several agents, or fan a
                      task's subtasks out to their own agents)
    cancel_task      (drop a delegated task from the collaboration ledger)
    list_agents      (the registered roster)

It never executes a workflow or capability itself: every run is delegated through
the :class:`TaskDelegator` (which delegates to the frozen Sprint 16.1
:class:`AIEmployee`). There is no networking, RPC, message broker, thread, or async
loop anywhere. Constructor injection only; its only state is the injected registry
and collaboration ledger — no static, singleton, or service-locator state. Strictly
additive to Sprints 1.x–16.8, whose modules are left untouched.
"""

from typing import List

from app.services.ai_employee.coordination.collaboration import (
    CollaborationContext,
)
from app.services.ai_employee.coordination.delegator import TaskDelegator
from app.services.ai_employee.coordination.models import (
    AgentNotFoundError,
    AgentProfile,
    AgentTask,
    CoordinationContext,
    DelegationResult,
)
from app.services.ai_employee.coordination.policy import CoordinationPolicy
from app.services.ai_employee.coordination.registry import AgentRegistry
from app.services.ai_employee.coordination.resolver import AgentResolver
from app.services.ai_employee.notification.manager import NotificationManager
from app.services.ai_employee.notification.models import NotificationEvent


class AgentCoordinator:
    """Coordinates collaboration over registry, resolver, policy, delegator, ledger.

    Constructed with an injected :class:`AgentRegistry`, :class:`AgentResolver`,
    :class:`CoordinationPolicy`, :class:`TaskDelegator`, :class:`CollaborationContext`,
    and Sprint 16.4 :class:`NotificationManager` (constructor injection; it
    instantiates none of them). It registers agents, resolves and assigns tasks per
    the policy, fans subtasks out to their own agents, cancels tracked tasks, and
    lists the roster — delegating every run through the :class:`TaskDelegator` and
    executing no workflow or capability itself. Its only state is the injected
    registry and collaboration ledger.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        resolver: AgentResolver,
        policy: CoordinationPolicy,
        delegator: TaskDelegator,
        collaboration: CollaborationContext,
        notification_manager: NotificationManager,
    ) -> None:
        self.registry = registry
        self.resolver = resolver
        self.policy = policy
        self.delegator = delegator
        self.collaboration = collaboration
        self.notification_manager = notification_manager

    # --- registration ----------------------------------------------------
    def register_agent(self, agent: AgentProfile) -> AgentProfile:
        """Register ``agent`` in the registry and record it in the collaboration ledger."""
        registered = self.registry.register(agent)
        self.collaboration.add_agent(registered.agent_id)
        return registered

    def list_agents(self) -> List[AgentProfile]:
        """Return the registered roster in registration order."""
        return self.registry.list()

    # --- single-agent delegation ----------------------------------------
    def delegate_task(self, task: AgentTask) -> DelegationResult:
        """Assign the whole ``task`` to the single agent the policy selects.

        Resolves the suitable candidates, asks the policy, and delegates the task to
        the first selected agent through the :class:`TaskDelegator` (which runs it via
        the :class:`AIEmployee`). Records the delegation in the collaboration ledger
        and announces it. Returns an ``"unassigned"`` result when no agent is
        suitable. The coordinator decides *who* and delegates the *running*; it
        executes nothing itself.
        """
        candidates = self.resolver.resolve(task, self.registry.list())
        decision = self.policy.decide(task, candidates)
        if not decision.selected_agent_ids:
            return self._unassigned(task, decision.policy)

        agent = self.registry.find(decision.selected_agent_ids[0])
        if agent is None:  # pragma: no cover - registry/decision are consistent
            return self._unassigned(task, decision.policy)

        self.notification_manager.notify(
            NotificationEvent.WORKFLOW_STARTED, task.task_id
        )
        result = self.delegator.delegate(task, agent, decision.policy)
        self.collaboration.record_delegation(task.task_id, agent.agent_id)
        return result

    # --- multi-agent / subtask coordination -----------------------------
    def coordinate(self, task: AgentTask) -> List[DelegationResult]:
        """Coordinate ``task`` across one or more agents and return every result.

        When ``task`` has subtasks, each subtask is resolved to its own agent and the
        children are aggregated into one parent :class:`DelegationResult` (subtask
        delegation). Otherwise the policy selects one or several agents and the whole
        task is delegated to each (single or collaborative). Every run is delegated
        through the :class:`TaskDelegator`; the coordinator executes nothing itself.
        """
        if task.subtasks:
            return [self._coordinate_subtasks(task)]
        return self._coordinate_whole(task)

    def _coordinate_whole(self, task: AgentTask) -> List[DelegationResult]:
        """Resolve, apply the policy, and delegate the whole task to each selection."""
        candidates = self.resolver.resolve(task, self.registry.list())
        decision = self.policy.decide(task, candidates)
        if not decision.selected_agent_ids:
            return [self._unassigned(task, decision.policy)]

        agents = [
            found
            for agent_id in decision.selected_agent_ids
            if (found := self.registry.find(agent_id)) is not None
        ]
        results: List[DelegationResult] = []
        for index, agent in enumerate(agents):
            self.notification_manager.notify(
                NotificationEvent.WORKFLOW_STARTED, task.task_id
            )
            results.append(
                self.delegator.delegate(task, agent, decision.policy)
            )
            # A collaborative task has one primary owner (the first selection);
            # every collaborator is recorded as a participant.
            if index == 0:
                self.collaboration.record_delegation(
                    task.task_id, agent.agent_id
                )
            else:
                self.collaboration.add_agent(agent.agent_id)
        return results

    def _coordinate_subtasks(self, task: AgentTask) -> DelegationResult:
        """Resolve each subtask to its own agent and delegate them (aggregated)."""
        roster = self.registry.list()
        assignments = []
        unassigned_ids: List[str] = []
        for subtask in task.subtasks:
            agent = self.resolver.resolve_best(subtask, roster)
            if agent is None:
                unassigned_ids.append(subtask.task_id)
                continue
            assignments.append((subtask, agent))

        for subtask, agent in assignments:
            self.notification_manager.notify(
                NotificationEvent.WORKFLOW_STARTED, subtask.task_id
            )

        parent = self.delegator.delegate_subtasks(
            task, assignments, self.policy.__class__.__name__
        )
        for subtask, agent in assignments:
            self.collaboration.record_delegation(
                subtask.task_id, agent.agent_id
            )
        if unassigned_ids:
            # A subtask that no agent could take means the parent is not fully
            # coordinated: it cannot report success even if its assigned children
            # all completed.
            return parent.model_copy(
                update={
                    "success": False,
                    "status": "failed",
                    "result_metadata": {
                        **parent.result_metadata,
                        "unassigned_subtask_ids": unassigned_ids,
                    },
                }
            )
        return parent

    # --- cancellation ----------------------------------------------------
    def cancel_task(self, task_id: str) -> DelegationResult:
        """Drop a delegated ``task_id`` from the collaboration ledger and announce it.

        Raises :class:`TaskNotFoundError` when the task is not tracked. Because the
        platform coordinates rather than runs, cancellation is a state operation: the
        task and its ownership are removed from the ledger and a cancellation is
        announced. It stops no running execution (there is none to stop here).
        """
        owner = self.collaboration.remove_task(task_id)
        self.notification_manager.notify(
            NotificationEvent.WORKFLOW_CANCELLED, task_id
        )
        return DelegationResult(
            task_id=task_id,
            agent_id=owner,
            assigned=False,
            success=True,
            status="cancelled",
        )

    # --- reads -----------------------------------------------------------
    def coordination_context(self) -> CoordinationContext:
        """Return an immutable snapshot of the current collaboration state."""
        return self.collaboration.snapshot()

    def require_agent(self, agent_id: str) -> AgentProfile:
        """Return the registered agent with ``agent_id`` or raise :class:`AgentNotFoundError`."""
        agent = self.registry.find(agent_id)
        if agent is None:
            raise AgentNotFoundError(f"no such agent: {agent_id}")
        return agent

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _unassigned(task: AgentTask, policy: str) -> DelegationResult:
        """Build the ``"unassigned"`` result for a task no agent was suitable for."""
        return DelegationResult(
            task_id=task.task_id,
            agent_id=None,
            assigned=False,
            success=False,
            status="unassigned",
            policy=policy,
            result_metadata={"reason": "no suitable agent"},
        )
