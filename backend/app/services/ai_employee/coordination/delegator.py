"""Task delegator (Sprint 16.9 — assign work; delegate running to the AIEmployee).

Defines :class:`TaskDelegator`, which *assigns* a coordinated task to one or more
agents by delegating the actual running to the frozen Sprint 16.1
:class:`AIEmployee`. Execution always flows

    TaskDelegator -> AIEmployee -> Planning Engine + Workflow Coordinator

so this component never calls the :class:`WorkflowCoordinator` directly and never
touches a capability — it hands each agent's :class:`EmployeeProfile` and the task's
supplied :class:`WorkflowStep`\\ s to the :class:`AIEmployee` and reports the
outcome as an immutable :class:`DelegationResult`.

It supports single-agent, multi-agent, and subtask delegation. It holds no
coordination state, performs no resolution or policy decision (those are given), and
never touches a repository, database, thread, or the network. Constructor injection
only; deterministic. Strictly additive to Sprints 1.x–16.8, whose modules are left
untouched.
"""

from typing import List, Sequence, Tuple

from app.services.ai_employee.ai_employee import AIEmployee
from app.services.ai_employee.coordination.models import (
    AgentProfile,
    AgentTask,
    DelegationResult,
)
from app.services.ai_employee.models import (
    EmployeeSessionStatus,
    TaskDelegation,
)


class TaskDelegator:
    """Assigns work to agents by delegating the running to the AIEmployee.

    Constructed with an injected :class:`AIEmployee` (constructor injection; it
    instantiates none). ``delegate`` assigns the whole task to one agent;
    ``delegate_all`` assigns it to several agents at once; and ``delegate_subtasks``
    assigns each of a task's subtasks to its own agent and aggregates the children
    into one parent :class:`DelegationResult`. Every path runs the work only through
    the :class:`AIEmployee` — never the Workflow Coordinator and never a capability.
    It holds no mutable state and performs no resolution or policy decision.
    """

    def __init__(self, ai_employee: AIEmployee) -> None:
        self.ai_employee = ai_employee

    def delegate(
        self,
        task: AgentTask,
        agent: AgentProfile,
        policy: str = "",
    ) -> DelegationResult:
        """Delegate the whole ``task`` to one ``agent`` via the :class:`AIEmployee`.

        Builds a Sprint 16.1 :class:`TaskDelegation` from the task, hands the agent's
        :class:`EmployeeProfile` and the task's supplied ``workflow_steps`` to the
        :class:`AIEmployee`, and reports the outcome. Success mirrors the employee's
        terminal ``COMPLETED`` status. It executes nothing itself.
        """
        employee_result = self.ai_employee.delegate(
            agent.profile,
            self._to_delegation(task),
            list(task.workflow_steps),
            task.initial_inputs or None,
        )
        success = (
            employee_result.status == EmployeeSessionStatus.COMPLETED
        )
        return DelegationResult(
            task_id=task.task_id,
            agent_id=agent.agent_id,
            assigned=True,
            success=success,
            status="completed" if success else "failed",
            policy=policy,
            employee_result=employee_result,
        )

    def delegate_all(
        self,
        task: AgentTask,
        agents: Sequence[AgentProfile],
        policy: str = "",
    ) -> List[DelegationResult]:
        """Delegate the whole ``task`` to each of ``agents`` and return every result.

        Each agent runs the same task through the :class:`AIEmployee`; the results
        preserve the given agent order. Returns an empty list when no agent is given.
        """
        return [self.delegate(task, agent, policy) for agent in agents]

    def delegate_subtasks(
        self,
        task: AgentTask,
        assignments: Sequence[Tuple[AgentTask, AgentProfile]],
        policy: str = "",
    ) -> DelegationResult:
        """Delegate each of ``task``'s subtasks to its assigned agent (aggregated).

        ``assignments`` pairs each subtask with the agent chosen for it. Every
        subtask is delegated to its agent via the :class:`AIEmployee`, and the child
        results are aggregated into one parent :class:`DelegationResult` (no agent of
        its own): the parent succeeds only when every subtask succeeds. It executes
        nothing itself.
        """
        children = [
            self.delegate(subtask, agent, policy)
            for subtask, agent in assignments
        ]
        success = bool(children) and all(child.success for child in children)
        return DelegationResult(
            task_id=task.task_id,
            agent_id=None,
            assigned=bool(children),
            success=success,
            status="completed" if success else "failed",
            policy=policy,
            employee_result=None,
            subtask_results=children,
            result_metadata={"subtask_count": len(children)},
        )

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _to_delegation(task: AgentTask) -> TaskDelegation:
        """Build the Sprint 16.1 :class:`TaskDelegation` for ``task``."""
        return TaskDelegation(
            task_id=task.task_id,
            task=task.description,
            constraints=list(task.constraints),
            priority=task.priority,
            delegation_metadata=dict(task.task_metadata),
        )
