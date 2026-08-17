"""Unit + integration tests for the Sprint 16.9 Agent Coordination Platform.

Exercises the coordination subsystem: the :class:`AgentRegistry` (roster), the
configurable :class:`AgentResolver` (which agents are suitable, ranked), the
:class:`CoordinationPolicy` implementations (:class:`SingleAgentPolicy`,
:class:`CollaborativePolicy`, :class:`PriorityPolicy`), the :class:`TaskDelegator`
(delegates the running to the frozen Sprint 16.1 :class:`AIEmployee`), the
:class:`CollaborationContext` (live ledger), and the :class:`AgentCoordinator` that
coordinates them and integrates with the Sprint 16.4 notification engine.

The platform coordinates *which* AI Employee handles *which* work; it executes no
workflow or capability itself — every run is delegated to the :class:`AIEmployee`,
which here runs over deterministic recording doubles so a delegation resolves to a
fixed ``COMPLETED``/``FAILED`` outcome with no network or SDK.

Covers, as the sprint requires: agent registration, agent resolution, task
delegation, single-agent coordination, multi-agent coordination, subtask
delegation, collaboration context, policies, notification integration, DTO
immutability, DI wiring, and regression (Sprints 16.1–16.8 unchanged; the
coordination sub-package imports no capability, Workflow Coordinator, repository,
thread, async, or network facility).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_agent_coordination
"""

import ast
import os
import unittest

from pydantic import ValidationError

from app.services.ai_employee import (
    AIEmployee,
    EmployeeProfile,
)
import app.services.ai_employee.notification as ne
from app.services.ai_employee.coordination import (
    AgentCoordinator,
    AgentNotFoundError,
    AgentProfile,
    AgentRegistry,
    AgentResolver,
    AgentStatus,
    AgentTask,
    CollaborationContext,
    CollaborativePolicy,
    CoordinationContext,
    CoordinationPolicy,
    CoordinationPolicyResult,
    DelegationResult,
    PriorityPolicy,
    SingleAgentPolicy,
    TaskDelegator,
    TaskNotFoundError,
)
from app.services.ai_employee.models import EmployeeSessionStatus, TaskPriority
from app.services.planning.models import ExecutionPlan
from app.services.runtime.workflow_models import (
    WorkflowExecutionResult,
    WorkflowStatus,
    WorkflowStep,
)

_COMPLETED = WorkflowStatus.COMPLETED.value
_FAILED = WorkflowStatus.FAILED.value


# =====================================================================
# Offline recording doubles for the AIEmployee's collaborators
# =====================================================================
class _RecordingPlanningEngine:
    """Duck-types the one :class:`PlanningEngine` method the foundation uses."""

    def create_plan(self, request) -> ExecutionPlan:
        return ExecutionPlan(goal="reason about it", summary="a plan")


class _RecordingWorkflowCoordinator:
    """Records every ``execute`` call; returns a fixed workflow result."""

    def __init__(self, status: str = _COMPLETED) -> None:
        self._status = status
        self.calls = []

    def execute(
        self,
        steps,
        workflow_id="workflow",
        runtime_id="",
        execution_id="",
        initial_inputs=None,
    ) -> WorkflowExecutionResult:
        self.calls.append(
            {"steps": steps, "initial_inputs": initial_inputs}
        )
        return WorkflowExecutionResult(
            workflow_id=workflow_id,
            workflow_status=self._status,
            total_step_count=len(steps),
        )


# =====================================================================
# Helpers
# =====================================================================
def _ai_employee(status: str = _COMPLETED):
    """AIEmployee over deterministic recording doubles (no network/SDK)."""
    coordinator = _RecordingWorkflowCoordinator(status)
    return AIEmployee(_RecordingPlanningEngine(), coordinator), coordinator


def _notification() -> ne.NotificationManager:
    return ne.NotificationManager(
        ne.ImmediateNotificationPolicy(),
        ne.NotificationQueue(),
        ne.InMemoryNotificationDispatcher(),
        ne.NotificationHistory(),
        ne.PriorityModel(),
    )


def _agent(
    agent_id="a1",
    role="writer",
    capabilities=("python",),
    priority=0,
    status=AgentStatus.AVAILABLE,
) -> AgentProfile:
    return AgentProfile(
        agent_id=agent_id,
        profile=EmployeeProfile(employee_id=f"e-{agent_id}", name=agent_id),
        role=role,
        capabilities=list(capabilities),
        priority=priority,
        status=status,
    )


def _task(
    task_id="t1",
    description="write the report",
    required_role="writer",
    required_capabilities=("python",),
    priority=TaskPriority.NORMAL,
    steps=True,
    subtasks=(),
) -> AgentTask:
    return AgentTask(
        task_id=task_id,
        description=description,
        required_role=required_role,
        required_capabilities=list(required_capabilities),
        priority=priority,
        workflow_steps=(
            [WorkflowStep(step_id="s1", capability_name="demo")]
            if steps
            else []
        ),
        subtasks=list(subtasks),
    )


def _coordinator(policy=None, status=_COMPLETED, resolver=None):
    ai, workflow = _ai_employee(status)
    coordinator = AgentCoordinator(
        AgentRegistry(),
        resolver or AgentResolver(),
        policy or SingleAgentPolicy(),
        TaskDelegator(ai),
        CollaborationContext(),
        _notification(),
    )
    return coordinator, workflow


# =====================================================================
# Agent registration (AgentRegistry)
# =====================================================================
class AgentRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = AgentRegistry()

    def test_register_adds_and_returns(self):
        agent = _agent("a1")
        self.assertIs(self.registry.register(agent), agent)
        self.assertIs(self.registry.find("a1"), agent)

    def test_list_preserves_registration_order(self):
        for agent_id in ("a1", "a2", "a3"):
            self.registry.register(_agent(agent_id))
        self.assertEqual(
            [a.agent_id for a in self.registry.list()], ["a1", "a2", "a3"]
        )

    def test_register_replaces_same_id_keeping_position(self):
        self.registry.register(_agent("a1", priority=1))
        self.registry.register(_agent("a2", priority=2))
        self.registry.register(_agent("a1", priority=9))  # replace
        listed = self.registry.list()
        self.assertEqual([a.agent_id for a in listed], ["a1", "a2"])
        self.assertEqual(listed[0].priority, 9)

    def test_find_missing_returns_none(self):
        self.assertIsNone(self.registry.find("nope"))

    def test_unregister_removes_and_returns(self):
        self.registry.register(_agent("a1"))
        removed = self.registry.unregister("a1")
        self.assertEqual(removed.agent_id, "a1")
        self.assertIsNone(self.registry.find("a1"))

    def test_unregister_missing_raises(self):
        with self.assertRaises(AgentNotFoundError):
            self.registry.unregister("nope")


# =====================================================================
# Agent resolution (AgentResolver)
# =====================================================================
class AgentResolverTests(unittest.TestCase):
    def setUp(self):
        self.resolver = AgentResolver()

    def test_filters_by_availability(self):
        agents = [
            _agent("busy", status=AgentStatus.BUSY),
            _agent("free", status=AgentStatus.AVAILABLE),
        ]
        resolved = self.resolver.resolve(_task(), agents)
        self.assertEqual([a.agent_id for a in resolved], ["free"])

    def test_filters_by_role(self):
        agents = [
            _agent("writer", role="writer"),
            _agent("coder", role="coder"),
        ]
        resolved = self.resolver.resolve(
            _task(required_role="writer"), agents
        )
        self.assertEqual([a.agent_id for a in resolved], ["writer"])

    def test_requires_all_capabilities_by_default(self):
        agents = [
            _agent("partial", capabilities=("python",)),
            _agent("full", capabilities=("python", "email")),
        ]
        task = _task(required_capabilities=("python", "email"))
        resolved = self.resolver.resolve(task, agents)
        self.assertEqual([a.agent_id for a in resolved], ["full"])

    def test_any_capability_when_not_requiring_all(self):
        resolver = AgentResolver(require_all_capabilities=False)
        agents = [_agent("partial", capabilities=("python",))]
        task = _task(required_capabilities=("python", "email"))
        self.assertEqual(
            [a.agent_id for a in resolver.resolve(task, agents)], ["partial"]
        )

    def test_ranks_by_priority_then_id(self):
        agents = [
            _agent("low", priority=1),
            _agent("high_b", priority=9),
            _agent("high_a", priority=9),
        ]
        resolved = self.resolver.resolve(_task(), agents)
        # priority desc, then agent_id asc for the tie at priority 9
        self.assertEqual(
            [a.agent_id for a in resolved], ["high_a", "high_b", "low"]
        )

    def test_resolve_best_returns_top_or_none(self):
        self.assertIsNone(self.resolver.resolve_best(_task(), []))
        agents = [_agent("a", priority=1), _agent("b", priority=5)]
        self.assertEqual(
            self.resolver.resolve_best(_task(), agents).agent_id, "b"
        )

    def test_relaxed_criteria_ignore_role_and_availability(self):
        resolver = AgentResolver(
            require_available=False, require_role=False
        )
        agents = [_agent("x", role="other", status=AgentStatus.BUSY)]
        self.assertEqual(len(resolver.resolve(_task(), agents)), 1)


# =====================================================================
# Coordination policies
# =====================================================================
class CoordinationPolicyTests(unittest.TestCase):
    def _candidates(self):
        # Already ranked best-first as the resolver would return them.
        return [_agent("a", priority=5), _agent("b", priority=3)]

    def test_policies_are_coordination_policies(self):
        for policy in (
            SingleAgentPolicy(),
            CollaborativePolicy(),
            PriorityPolicy(),
        ):
            self.assertIsInstance(policy, CoordinationPolicy)

    def test_single_agent_picks_top(self):
        result = SingleAgentPolicy().decide(_task(), self._candidates())
        self.assertIsInstance(result, CoordinationPolicyResult)
        self.assertEqual(result.selected_agent_ids, ["a"])
        self.assertFalse(result.collaborative)

    def test_single_agent_none_when_empty(self):
        result = SingleAgentPolicy().decide(_task(), [])
        self.assertEqual(result.selected_agent_ids, [])
        self.assertFalse(result.collaborative)

    def test_collaborative_selects_all(self):
        result = CollaborativePolicy().decide(_task(), self._candidates())
        self.assertEqual(result.selected_agent_ids, ["a", "b"])
        self.assertTrue(result.collaborative)

    def test_collaborative_respects_max_agents(self):
        result = CollaborativePolicy(max_agents=1).decide(
            _task(), self._candidates()
        )
        self.assertEqual(result.selected_agent_ids, ["a"])
        self.assertFalse(result.collaborative)

    def test_priority_picks_highest_regardless_of_order(self):
        # Unordered candidates: highest priority must still win.
        candidates = [_agent("low", priority=1), _agent("high", priority=8)]
        result = PriorityPolicy().decide(_task(), candidates)
        self.assertEqual(result.selected_agent_ids, ["high"])

    def test_priority_tie_breaks_on_agent_id(self):
        candidates = [_agent("b", priority=5), _agent("a", priority=5)]
        result = PriorityPolicy().decide(_task(), candidates)
        self.assertEqual(result.selected_agent_ids, ["a"])


# =====================================================================
# Collaboration context (ledger)
# =====================================================================
class CollaborationContextTests(unittest.TestCase):
    def setUp(self):
        self.ledger = CollaborationContext(context_id="team")

    def test_add_agent_is_idempotent(self):
        self.ledger.add_agent("a1")
        self.ledger.add_agent("a1")
        self.assertEqual(self.ledger.agents(), ["a1"])

    def test_record_delegation_tracks_task_owner_participant(self):
        self.ledger.record_delegation("t1", "a1")
        self.assertEqual(self.ledger.tasks(), ["t1"])
        self.assertEqual(self.ledger.owner_of("t1"), "a1")
        self.assertIn("a1", self.ledger.agents())

    def test_record_delegation_updates_owner_without_dup(self):
        self.ledger.record_delegation("t1", "a1")
        self.ledger.record_delegation("t1", "a2")
        self.assertEqual(self.ledger.tasks(), ["t1"])
        self.assertEqual(self.ledger.owner_of("t1"), "a2")

    def test_remove_task_returns_owner(self):
        self.ledger.record_delegation("t1", "a1")
        self.assertEqual(self.ledger.remove_task("t1"), "a1")
        self.assertEqual(self.ledger.tasks(), [])
        self.assertIsNone(self.ledger.owner_of("t1"))

    def test_remove_missing_task_raises(self):
        with self.assertRaises(TaskNotFoundError):
            self.ledger.remove_task("nope")

    def test_snapshot_is_immutable_capture(self):
        self.ledger.record_delegation("t1", "a1")
        snap = self.ledger.snapshot()
        self.assertIsInstance(snap, CoordinationContext)
        self.assertEqual(snap.context_id, "team")
        self.assertEqual(snap.ownership, {"t1": "a1"})
        # The snapshot is a copy: mutating the ledger does not change it.
        self.ledger.record_delegation("t2", "a2")
        self.assertEqual(snap.task_ids, ["t1"])


# =====================================================================
# Task delegation (TaskDelegator) — delegates to the AIEmployee
# =====================================================================
class TaskDelegatorTests(unittest.TestCase):
    def test_delegate_single_runs_via_ai_employee(self):
        ai, workflow = _ai_employee(_COMPLETED)
        result = TaskDelegator(ai).delegate(_task(), _agent("a1"), "P")
        self.assertTrue(result.assigned)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.agent_id, "a1")
        self.assertEqual(result.policy, "P")
        self.assertIsNotNone(result.employee_result)
        self.assertEqual(
            result.employee_result.status, EmployeeSessionStatus.COMPLETED
        )
        self.assertEqual(len(workflow.calls), 1)  # delegated the running

    def test_delegate_reports_failure(self):
        ai, _ = _ai_employee(_FAILED)
        result = TaskDelegator(ai).delegate(_task(), _agent("a1"))
        self.assertFalse(result.success)
        self.assertEqual(result.status, "failed")

    def test_delegate_all_runs_each_agent(self):
        ai, workflow = _ai_employee(_COMPLETED)
        agents = [_agent("a1"), _agent("a2")]
        results = TaskDelegator(ai).delegate_all(_task(), agents, "P")
        self.assertEqual([r.agent_id for r in results], ["a1", "a2"])
        self.assertEqual(len(workflow.calls), 2)

    def test_delegate_subtasks_aggregates_children(self):
        ai, _ = _ai_employee(_COMPLETED)
        sub_a = _task(task_id="s1")
        sub_b = _task(task_id="s2")
        parent = TaskDelegator(ai).delegate_subtasks(
            _task(task_id="p1", steps=False),
            [(sub_a, _agent("a1")), (sub_b, _agent("a2"))],
            "P",
        )
        self.assertIsNone(parent.agent_id)
        self.assertTrue(parent.success)
        self.assertEqual(
            [c.task_id for c in parent.subtask_results], ["s1", "s2"]
        )
        self.assertEqual(parent.result_metadata["subtask_count"], 2)

    def test_delegate_subtasks_fails_if_any_child_fails(self):
        ai, _ = _ai_employee(_FAILED)
        parent = TaskDelegator(ai).delegate_subtasks(
            _task(task_id="p1", steps=False),
            [(_task(task_id="s1"), _agent("a1"))],
        )
        self.assertFalse(parent.success)

    def test_delegator_only_holds_ai_employee(self):
        ai, _ = _ai_employee()
        self.assertEqual(set(vars(TaskDelegator(ai))), {"ai_employee"})


# =====================================================================
# Registration through the coordinator
# =====================================================================
class CoordinatorRegistrationTests(unittest.TestCase):
    def test_register_agent_adds_to_registry_and_ledger(self):
        coordinator, _ = _coordinator()
        coordinator.register_agent(_agent("a1"))
        self.assertEqual(
            [a.agent_id for a in coordinator.list_agents()], ["a1"]
        )
        self.assertIn("a1", coordinator.coordination_context().agent_ids)

    def test_require_agent_raises_when_missing(self):
        coordinator, _ = _coordinator()
        with self.assertRaises(AgentNotFoundError):
            coordinator.require_agent("nope")


# =====================================================================
# Task delegation (single agent) through the coordinator
# =====================================================================
class DelegateTaskTests(unittest.TestCase):
    def test_delegates_to_single_best_agent(self):
        coordinator, _ = _coordinator(policy=SingleAgentPolicy())
        coordinator.register_agent(_agent("a1", priority=1))
        coordinator.register_agent(_agent("a2", priority=9))
        result = coordinator.delegate_task(_task())
        self.assertEqual(result.agent_id, "a2")  # higher priority ranks first
        self.assertTrue(result.success)
        self.assertEqual(result.status, "completed")
        self.assertEqual(
            coordinator.coordination_context().ownership["t1"], "a2"
        )

    def test_unassigned_when_no_suitable_agent(self):
        coordinator, _ = _coordinator()
        coordinator.register_agent(_agent("a1", role="other"))
        result = coordinator.delegate_task(_task(required_role="writer"))
        self.assertFalse(result.assigned)
        self.assertFalse(result.success)
        self.assertEqual(result.status, "unassigned")
        self.assertIsNone(result.agent_id)

    def test_delegation_does_not_execute_when_unassigned(self):
        coordinator, workflow = _coordinator()
        coordinator.register_agent(_agent("a1", role="other"))
        coordinator.delegate_task(_task(required_role="writer"))
        self.assertEqual(workflow.calls, [])  # nothing was run


# =====================================================================
# Single- and multi-agent coordination
# =====================================================================
class CoordinateTests(unittest.TestCase):
    def test_single_agent_coordination_returns_one_result(self):
        coordinator, _ = _coordinator(policy=SingleAgentPolicy())
        coordinator.register_agent(_agent("a1", priority=1))
        coordinator.register_agent(_agent("a2", priority=9))
        results = coordinator.coordinate(_task())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].agent_id, "a2")

    def test_multi_agent_coordination_fans_out(self):
        coordinator, workflow = _coordinator(policy=CollaborativePolicy())
        coordinator.register_agent(_agent("a1", priority=1))
        coordinator.register_agent(_agent("a2", priority=9))
        results = coordinator.coordinate(_task())
        self.assertEqual({r.agent_id for r in results}, {"a1", "a2"})
        self.assertTrue(all(r.success for r in results))
        self.assertEqual(len(workflow.calls), 2)  # both agents ran

    def test_multi_agent_records_primary_owner_and_participants(self):
        coordinator, _ = _coordinator(policy=CollaborativePolicy())
        coordinator.register_agent(_agent("a1", priority=1))
        coordinator.register_agent(_agent("a2", priority=9))
        coordinator.coordinate(_task())
        context = coordinator.coordination_context()
        self.assertEqual(context.ownership["t1"], "a2")  # top-ranked primary
        self.assertEqual(set(context.agent_ids), {"a1", "a2"})

    def test_coordinate_unassigned_when_none_suitable(self):
        coordinator, _ = _coordinator(policy=CollaborativePolicy())
        results = coordinator.coordinate(_task())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "unassigned")

    def test_priority_policy_selects_highest(self):
        coordinator, _ = _coordinator(policy=PriorityPolicy())
        coordinator.register_agent(_agent("a1", priority=3))
        coordinator.register_agent(_agent("a2", priority=7))
        results = coordinator.coordinate(_task())
        self.assertEqual(results[0].agent_id, "a2")


# =====================================================================
# Subtask delegation through the coordinator
# =====================================================================
class SubtaskCoordinationTests(unittest.TestCase):
    def test_subtasks_each_delegated_to_own_agent(self):
        coordinator, workflow = _coordinator(policy=SingleAgentPolicy())
        coordinator.register_agent(
            _agent("writer", role="writer", capabilities=("python",))
        )
        coordinator.register_agent(
            _agent("mailer", role="mailer", capabilities=("email",))
        )
        parent_task = _task(
            task_id="p1",
            required_role="",
            required_capabilities=(),
            steps=False,
            subtasks=(
                _task(
                    task_id="s1",
                    required_role="writer",
                    required_capabilities=("python",),
                ),
                _task(
                    task_id="s2",
                    required_role="mailer",
                    required_capabilities=("email",),
                ),
            ),
        )
        results = coordinator.coordinate(parent_task)
        self.assertEqual(len(results), 1)
        parent = results[0]
        self.assertTrue(parent.success)
        children = {c.task_id: c.agent_id for c in parent.subtask_results}
        self.assertEqual(children, {"s1": "writer", "s2": "mailer"})
        self.assertEqual(len(workflow.calls), 2)

    def test_unassigned_subtask_fails_parent(self):
        coordinator, _ = _coordinator(policy=SingleAgentPolicy())
        coordinator.register_agent(
            _agent("writer", role="writer", capabilities=("python",))
        )
        parent_task = _task(
            task_id="p1",
            required_role="",
            required_capabilities=(),
            steps=False,
            subtasks=(
                _task(
                    task_id="s1",
                    required_role="writer",
                    required_capabilities=("python",),
                ),
                _task(
                    task_id="s2",
                    required_role="mailer",
                    required_capabilities=("email",),
                ),
            ),
        )
        parent = coordinator.coordinate(parent_task)[0]
        self.assertFalse(parent.success)
        self.assertEqual(parent.status, "failed")
        self.assertEqual(
            parent.result_metadata["unassigned_subtask_ids"], ["s2"]
        )


# =====================================================================
# Cancellation
# =====================================================================
class CancelTaskTests(unittest.TestCase):
    def test_cancel_removes_task_from_ledger(self):
        coordinator, _ = _coordinator()
        coordinator.register_agent(_agent("a1"))
        coordinator.delegate_task(_task())
        result = coordinator.cancel_task("t1")
        self.assertEqual(result.status, "cancelled")
        self.assertTrue(result.success)
        self.assertEqual(result.agent_id, "a1")
        self.assertEqual(coordinator.coordination_context().task_ids, [])

    def test_cancel_missing_task_raises(self):
        coordinator, _ = _coordinator()
        with self.assertRaises(TaskNotFoundError):
            coordinator.cancel_task("nope")


# =====================================================================
# Notification integration
# =====================================================================
class NotificationIntegrationTests(unittest.TestCase):
    def test_delegation_announces_workflow_started(self):
        coordinator, _ = _coordinator()
        coordinator.register_agent(_agent("a1"))
        coordinator.delegate_task(_task())
        events = [
            n.event for n in coordinator.notification_manager.dispatched()
        ]
        self.assertIn(ne.NotificationEvent.WORKFLOW_STARTED, events)

    def test_cancellation_announces_workflow_cancelled(self):
        coordinator, _ = _coordinator()
        coordinator.register_agent(_agent("a1"))
        coordinator.delegate_task(_task())
        coordinator.cancel_task("t1")
        events = [
            n.event for n in coordinator.notification_manager.dispatched()
        ]
        self.assertIn(ne.NotificationEvent.WORKFLOW_CANCELLED, events)


# =====================================================================
# DTO immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def test_agent_profile_is_frozen(self):
        with self.assertRaises(ValidationError):
            _agent("a1").priority = 9

    def test_agent_task_is_frozen(self):
        with self.assertRaises(ValidationError):
            _task().description = "changed"

    def test_delegation_result_is_frozen(self):
        result = DelegationResult(status="completed")
        with self.assertRaises(ValidationError):
            result.success = True

    def test_policy_result_is_frozen(self):
        result = SingleAgentPolicy().decide(_task(), [_agent("a1")])
        with self.assertRaises(ValidationError):
            result.collaborative = True

    def test_coordination_context_is_frozen(self):
        snapshot = CollaborationContext().snapshot()
        with self.assertRaises(ValidationError):
            snapshot.context_id = "x"

    def test_agent_profile_requires_non_empty_id(self):
        with self.assertRaises(ValidationError):
            AgentProfile(
                agent_id="  ",
                profile=EmployeeProfile(employee_id="e1", name="Ada"),
            )

    def test_agent_task_requires_non_empty_description(self):
        with self.assertRaises(ValidationError):
            AgentTask(task_id="t1", description="")


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_basic_providers(self):
        from app.core.dependencies import (
            get_agent_registry,
            get_agent_resolver,
            get_collaboration_context,
            get_coordination_policy,
            get_task_delegator,
        )

        self.assertIsInstance(get_agent_registry(), AgentRegistry)
        self.assertIsInstance(get_agent_resolver(), AgentResolver)
        self.assertIsInstance(get_coordination_policy(), SingleAgentPolicy)
        self.assertIsInstance(get_task_delegator(), TaskDelegator)
        self.assertIsInstance(
            get_collaboration_context(), CollaborationContext
        )

    def test_coordinator_provider_wires_collaborators(self):
        from app.core.dependencies import get_agent_coordinator

        coordinator = get_agent_coordinator()
        self.assertIsInstance(coordinator, AgentCoordinator)
        self.assertIsInstance(coordinator.registry, AgentRegistry)
        self.assertIsInstance(coordinator.resolver, AgentResolver)
        self.assertIsInstance(coordinator.policy, CoordinationPolicy)
        self.assertIsInstance(coordinator.delegator, TaskDelegator)
        self.assertIsInstance(
            coordinator.collaboration, CollaborationContext
        )
        self.assertIsInstance(
            coordinator.delegator.ai_employee, AIEmployee
        )

    def test_coordinator_provider_uses_injected(self):
        from app.core.dependencies import get_agent_coordinator

        policy = CollaborativePolicy()
        coordinator = get_agent_coordinator(policy=policy)
        self.assertIs(coordinator.policy, policy)

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            AgentCoordinatorDep,
            AgentRegistryDep,
            AgentResolverDep,
            CollaborationContextDep,
            CoordinationPolicyDep,
            TaskDelegatorDep,
        )

        for dep in (
            AgentRegistryDep,
            AgentResolverDep,
            CoordinationPolicyDep,
            TaskDelegatorDep,
            CollaborationContextDep,
            AgentCoordinatorDep,
        ):
            self.assertIsNotNone(dep)


# =====================================================================
# Regression: prior sprints frozen; no forbidden imports
# =====================================================================
class RegressionTests(unittest.TestCase):
    _FORBIDDEN_MODULES = {
        "browser_capability",
        "python_capability",
        "filesystem_capability",
        "email_capability",
        "calendar_capability",
        "github_capability",
        "workflow_coordinator",
        "repository",
        "threading",
        "asyncio",
        "socket",
        "requests",
        "httpx",
    }

    def test_frozen_168_recovery_engine_unchanged(self):
        from app.core.dependencies import get_recovery_engine
        import app.services.ai_employee.recovery as recovery_engine

        self.assertIsInstance(
            get_recovery_engine(), recovery_engine.RecoveryManager
        )

    def test_frozen_167_scheduler_unchanged(self):
        from app.core.dependencies import get_scheduler_manager
        import app.services.ai_employee.scheduler as scheduler_engine

        self.assertIsInstance(
            get_scheduler_manager(), scheduler_engine.SchedulerManager
        )

    def test_frozen_161_ai_employee_unchanged(self):
        from app.core.dependencies import get_ai_employee

        self.assertEqual(
            set(vars(get_ai_employee())),
            {"planning_engine", "workflow_coordinator"},
        )

    def test_coordination_package_imports_nothing_forbidden(self):
        import app.services.ai_employee.coordination as pkg

        package_dir = os.path.dirname(pkg.__file__)
        offenders = []
        for filename in os.listdir(package_dir):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(package_dir, filename)
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module)
                elif isinstance(node, ast.Import):
                    names.extend(alias.name for alias in node.names)
                for name in names:
                    tail = name.rsplit(".", 1)[-1]
                    if tail in self._FORBIDDEN_MODULES:
                        offenders.append((filename, name))
        self.assertEqual(offenders, [])

    def test_coordinator_never_holds_workflow_coordinator(self):
        # The coordinator reaches execution only via the delegator -> AIEmployee;
        # it holds no Workflow Coordinator, capability, or repository reference.
        coordinator, _ = _coordinator()
        self.assertEqual(
            set(vars(coordinator)),
            {
                "registry",
                "resolver",
                "policy",
                "delegator",
                "collaboration",
                "notification_manager",
            },
        )


if __name__ == "__main__":
    unittest.main()
