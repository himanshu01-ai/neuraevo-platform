"""Unit + integration tests for the Sprint 16.7 Scheduling Platform.

Exercises the scheduler subsystem: the :class:`SchedulePolicy` implementations, the
deterministic :class:`SchedulePlanner` (tick math), the tick-ordered
:class:`ScheduleQueue`, the :class:`ExecutionScheduler` (delegates to the frozen
Sprint 16.2 :class:`WorkflowLifecycleManager`), and the :class:`SchedulerManager`
that coordinates them and integrates with the Sprint 16.5 persistence and Sprint
16.4 notification engines. All timing is a deterministic caller-supplied integer
tick — no wall-clock, timers, threading, asyncio, or cron.

Covers, as the sprint requires: immediate/delayed/recurring scheduling,
rescheduling, cancellation, planner, policy, queue ordering, execution delegation,
persistence integration, notification integration, DTO immutability, DI wiring, and
regression (Sprints 16.1–16.6 unchanged; the frozen planning ``ExecutionScheduler``
is distinct; the scheduler sub-package imports no capability, Workflow Coordinator,
timer, threading, asyncio, or cron facility).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_scheduler
"""

import ast
import os
import unittest

from pydantic import ValidationError

from app.services.ai_employee import (
    AutoApprovalPolicy,
    BasicRecoveryManager,
    EmployeeProfile,
    InMemoryNotificationManager,
    InMemoryPersistenceManager,
    ProgressTracker,
    TaskDelegation,
    WorkflowLifecycleManager,
    WorkflowLifecycleStatus,
)
import app.services.ai_employee.notification as ne
from app.services.ai_employee.persistence import (
    InMemoryPersistenceRepository,
    PersistenceManager,
)
from app.services.ai_employee.scheduler import (
    DelayedPolicy,
    ExecutionScheduler,
    ImmediatePolicy,
    InvalidScheduleError,
    RecurringPolicy,
    RequestSchedulePolicy,
    ScheduleEntry,
    ScheduleNotFoundError,
    SchedulePlanner,
    SchedulePolicy,
    ScheduleQueue,
    ScheduleRequest,
    ScheduleResult,
    ScheduleStatus,
    ScheduleType,
    SchedulerManager,
)
from app.services.runtime.artifact_coordinator import ArtifactCoordinator
from app.services.runtime.capability_router import CapabilityRouter
from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionResult,
    CapabilityExecutionStatus,
)
from app.services.runtime.workflow_coordinator import WorkflowCoordinator
from app.services.runtime.workflow_models import WorkflowStep

_COMPLETED = CapabilityExecutionStatus.COMPLETED.value
_FAILED = CapabilityExecutionStatus.FAILED.value


# =====================================================================
# Offline capability doubles + helpers
# =====================================================================
class _CompletingCapability(ExecutionCapability):
    def execute(self, request):
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=_COMPLETED,
            capability_outputs={},
            execution_metadata={},
        )


class _FailingCapability(ExecutionCapability):
    def execute(self, request):
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=_FAILED,
            capability_outputs={"error": "boom"},
            execution_metadata={},
        )


def _lifecycle(capability=None):
    from app.core.dependencies import get_execution_orchestration_engine

    return WorkflowLifecycleManager(
        get_execution_orchestration_engine(),
        WorkflowCoordinator(
            CapabilityRouter({"demo": capability or _CompletingCapability()}),
            ArtifactCoordinator(),
        ),
        ProgressTracker(),
        AutoApprovalPolicy(),
        InMemoryNotificationManager(),
        BasicRecoveryManager(),
        InMemoryPersistenceManager(),
    )


def _notification():
    return ne.NotificationManager(
        ne.ImmediateNotificationPolicy(),
        ne.NotificationQueue(),
        ne.InMemoryNotificationDispatcher(),
        ne.NotificationHistory(),
        ne.PriorityModel(),
    )


def _manager(policy=None, capability=None, lifecycle=None):
    return SchedulerManager(
        policy or RequestSchedulePolicy(),
        SchedulePlanner(),
        ScheduleQueue(),
        ExecutionScheduler(lifecycle or _lifecycle(capability)),
        PersistenceManager(InMemoryPersistenceRepository()),
        _notification(),
    )


def _instance(task_id="t1", lifecycle=None):
    lifecycle = lifecycle or _lifecycle()
    return lifecycle.create_instance(
        EmployeeProfile(employee_id="e1", name="Ada"),
        TaskDelegation(task_id=task_id, task="do it"),
        [WorkflowStep(step_id="s1", capability_name="demo")],
    )


def _request(request_id="r1", **kwargs):
    return ScheduleRequest(request_id=request_id, **kwargs)


# =====================================================================
# Planner
# =====================================================================
class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = SchedulePlanner()

    def test_immediate(self):
        self.assertEqual(
            self.planner.plan(_request(schedule_type=ScheduleType.IMMEDIATE), 7),
            7,
        )

    def test_delayed(self):
        self.assertEqual(
            self.planner.plan(
                _request(schedule_type=ScheduleType.DELAYED, delay=5), 10
            ),
            15,
        )

    def test_at_time(self):
        self.assertEqual(
            self.planner.plan(
                _request(schedule_type=ScheduleType.AT_TIME, at_tick=42), 3
            ),
            42,
        )

    def test_recurring_first_occurrence(self):
        self.assertEqual(
            self.planner.plan(
                _request(schedule_type=ScheduleType.RECURRING, interval=3), 4
            ),
            4,
        )

    def test_next_recurrence(self):
        self.assertEqual(self.planner.next_recurrence(4, 3), 7)

    def test_at_time_requires_tick(self):
        with self.assertRaises(InvalidScheduleError):
            self.planner.plan(_request(schedule_type=ScheduleType.AT_TIME), 0)

    def test_recurring_requires_interval(self):
        with self.assertRaises(InvalidScheduleError):
            self.planner.plan(
                _request(schedule_type=ScheduleType.RECURRING), 0
            )


# =====================================================================
# Policy
# =====================================================================
class PolicyTests(unittest.TestCase):
    def test_request_policy_is_pass_through(self):
        request = _request(schedule_type=ScheduleType.DELAYED, delay=2)
        self.assertEqual(RequestSchedulePolicy().apply(request), request)

    def test_immediate_policy_forces_immediate(self):
        applied = ImmediatePolicy().apply(
            _request(schedule_type=ScheduleType.DELAYED, delay=9)
        )
        self.assertEqual(applied.schedule_type, ScheduleType.IMMEDIATE)

    def test_delayed_policy_applies_default_delay(self):
        applied = DelayedPolicy(default_delay=4).apply(_request())
        self.assertEqual(applied.schedule_type, ScheduleType.DELAYED)
        self.assertEqual(applied.delay, 4)

    def test_recurring_policy_applies_default_interval(self):
        applied = RecurringPolicy(default_interval=6).apply(_request())
        self.assertEqual(applied.schedule_type, ScheduleType.RECURRING)
        self.assertEqual(applied.interval, 6)

    def test_policies_are_schedule_policies(self):
        for policy in (
            RequestSchedulePolicy(),
            ImmediatePolicy(),
            DelayedPolicy(),
            RecurringPolicy(),
        ):
            self.assertIsInstance(policy, SchedulePolicy)


# =====================================================================
# Queue ordering
# =====================================================================
class QueueTests(unittest.TestCase):
    def setUp(self):
        self.queue = ScheduleQueue()
        self.lifecycle = _lifecycle()

    def _entry(self, entry_id, tick, status=ScheduleStatus.SCHEDULED, task="t"):
        from app.services.ai_employee.scheduler.models import ScheduleMetadata

        return ScheduleEntry(
            entry_id=entry_id,
            workflow_id=f"wf-{entry_id}",
            instance=_instance(task, self.lifecycle),
            schedule_type=ScheduleType.IMMEDIATE,
            status=status,
            next_execution_tick=tick,
            created_at_tick=0,
            metadata=ScheduleMetadata(
                schedule_id=entry_id, schedule_type=ScheduleType.IMMEDIATE
            ),
        )

    def test_ordered_by_tick(self):
        self.queue.enqueue(self._entry("a", 5, task="t1"))
        self.queue.enqueue(self._entry("b", 1, task="t2"))
        self.queue.enqueue(self._entry("c", 3, task="t3"))
        self.assertEqual(
            [e.entry_id for e in self.queue.pending()], ["b", "c", "a"]
        )

    def test_peek_is_earliest(self):
        self.queue.enqueue(self._entry("a", 5, task="t1"))
        self.queue.enqueue(self._entry("b", 1, task="t2"))
        self.assertEqual(self.queue.peek().entry_id, "b")

    def test_dequeue_due_releases_due_scheduled(self):
        self.queue.enqueue(self._entry("a", 1, task="t1"))
        self.queue.enqueue(self._entry("b", 8, task="t2"))
        due = self.queue.dequeue_due(3)
        self.assertEqual([e.entry_id for e in due], ["a"])
        self.assertEqual([e.entry_id for e in self.queue.pending()], ["b"])

    def test_dequeue_due_skips_paused(self):
        self.queue.enqueue(
            self._entry("a", 1, status=ScheduleStatus.PAUSED, task="t1")
        )
        self.assertEqual(self.queue.dequeue_due(10), [])

    def test_remove_and_get_and_update(self):
        self.queue.enqueue(self._entry("a", 1, task="t1"))
        self.assertEqual(self.queue.get("a").entry_id, "a")
        updated = self.queue.get("a").model_copy(
            update={"next_execution_tick": 9}
        )
        self.assertTrue(self.queue.update(updated))
        self.assertEqual(self.queue.get("a").next_execution_tick, 9)
        self.assertIsNotNone(self.queue.remove("a"))
        self.assertIsNone(self.queue.get("a"))


# =====================================================================
# Immediate / delayed / recurring scheduling
# =====================================================================
class SchedulingTests(unittest.TestCase):
    def test_immediate_scheduling(self):
        manager = _manager()
        result = manager.schedule(
            _request(schedule_type=ScheduleType.IMMEDIATE),
            _instance("t1"),
            now_tick=4,
        )
        self.assertIsInstance(result, ScheduleResult)
        self.assertEqual(result.entry.schedule_type, ScheduleType.IMMEDIATE)
        self.assertEqual(result.entry.next_execution_tick, 4)
        self.assertEqual(result.entry.status, ScheduleStatus.SCHEDULED)

    def test_delayed_scheduling(self):
        manager = _manager()
        result = manager.schedule(
            _request(schedule_type=ScheduleType.DELAYED, delay=6),
            _instance("t1"),
            now_tick=2,
        )
        self.assertEqual(result.entry.next_execution_tick, 8)

    def test_recurring_scheduling(self):
        manager = _manager()
        result = manager.schedule(
            _request(
                schedule_type=ScheduleType.RECURRING,
                interval=3,
                max_occurrences=2,
            ),
            _instance("t1"),
            now_tick=0,
        )
        self.assertEqual(result.entry.schedule_type, ScheduleType.RECURRING)
        self.assertEqual(result.entry.interval, 3)
        self.assertEqual(result.entry.max_occurrences, 2)

    def test_list_returns_scheduled_entries(self):
        manager = _manager()
        manager.schedule(_request("r1"), _instance("t1"), now_tick=0)
        manager.schedule(_request("r2"), _instance("t2"), now_tick=0)
        self.assertEqual(len(manager.list()), 2)

    def test_scheduling_is_deterministic(self):
        a = _manager().schedule(_request(), _instance("t1"))
        b = _manager().schedule(_request(), _instance("t1"))
        self.assertEqual(a.entry.entry_id, b.entry.entry_id)


# =====================================================================
# run_due / execution delegation / recurring re-enqueue
# =====================================================================
class RunDueTests(unittest.TestCase):
    def test_run_due_executes_immediate(self):
        manager = _manager()
        manager.schedule(
            _request(schedule_type=ScheduleType.IMMEDIATE),
            _instance("t1"),
            now_tick=0,
        )
        results = manager.run_due(0)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].success)
        self.assertEqual(results[0].result_metadata["final_status"], "COMPLETED")
        self.assertEqual(manager.list(), [])

    def test_run_due_ignores_not_yet_due(self):
        manager = _manager()
        manager.schedule(
            _request(schedule_type=ScheduleType.DELAYED, delay=5),
            _instance("t1"),
            now_tick=0,
        )
        self.assertEqual(manager.run_due(3), [])
        self.assertEqual(len(manager.list()), 1)

    def test_recurring_re_enqueues_next_occurrence(self):
        manager = _manager()
        manager.schedule(
            _request(schedule_type=ScheduleType.RECURRING, interval=3),
            _instance("t1"),
            now_tick=0,
        )
        manager.run_due(0)  # first occurrence at tick 0
        pending = manager.list()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].next_execution_tick, 3)
        self.assertEqual(pending[0].occurrences, 1)

    def test_recurring_stops_at_max_occurrences(self):
        manager = _manager()
        manager.schedule(
            _request(
                schedule_type=ScheduleType.RECURRING,
                interval=1,
                max_occurrences=2,
            ),
            _instance("t1"),
            now_tick=0,
        )
        manager.run_due(0)  # occurrence 1 -> re-enqueue at tick 1
        manager.run_due(1)  # occurrence 2 -> max reached, no re-enqueue
        self.assertEqual(manager.list(), [])

    def test_run_due_delegates_to_lifecycle_and_reports_failure(self):
        manager = _manager(capability=_FailingCapability())
        manager.schedule(_request(), _instance("t1"), now_tick=0)
        results = manager.run_due(0)
        self.assertFalse(results[0].success)
        self.assertEqual(results[0].result_metadata["final_status"], "FAILED")

    def test_execution_scheduler_delegates_via_lifecycle(self):
        lifecycle = _lifecycle()
        scheduler = ExecutionScheduler(lifecycle)
        self.assertIs(scheduler.lifecycle_manager, lifecycle)
        # only collaborator is the lifecycle manager — no coordinator/capability
        self.assertEqual(set(vars(scheduler)), {"lifecycle_manager"})


# =====================================================================
# Reschedule / cancel / pause / resume
# =====================================================================
class RescheduleCancelTests(unittest.TestCase):
    def setUp(self):
        self.manager = _manager()
        self.result = self.manager.schedule(
            _request(schedule_type=ScheduleType.DELAYED, delay=2),
            _instance("t1"),
            now_tick=0,
        )
        self.entry_id = self.result.entry.entry_id

    def test_reschedule_recomputes_tick(self):
        result = self.manager.reschedule(
            self.entry_id,
            _request(schedule_type=ScheduleType.DELAYED, delay=9),
            now_tick=1,
        )
        self.assertEqual(result.entry.next_execution_tick, 10)
        self.assertEqual(
            self.manager.list()[0].next_execution_tick, 10
        )

    def test_reschedule_missing_raises(self):
        with self.assertRaises(ScheduleNotFoundError):
            self.manager.reschedule("nope", _request())

    def test_cancel_removes_entry(self):
        result = self.manager.cancel(self.entry_id)
        self.assertEqual(result.entry.status, ScheduleStatus.CANCELLED)
        self.assertEqual(self.manager.list(), [])

    def test_cancel_missing_raises(self):
        with self.assertRaises(ScheduleNotFoundError):
            self.manager.cancel("nope")

    def test_pause_holds_from_execution_then_resume_runs(self):
        self.manager.pause(self.entry_id)
        self.assertEqual(
            self.manager.list()[0].status, ScheduleStatus.PAUSED
        )
        self.assertEqual(self.manager.run_due(100), [])  # paused: not run
        self.manager.resume(self.entry_id)
        self.assertEqual(len(self.manager.run_due(100)), 1)  # now runs


# =====================================================================
# Persistence integration
# =====================================================================
class PersistenceIntegrationTests(unittest.TestCase):
    def test_schedule_persists_the_instance(self):
        manager = _manager()
        instance = _instance("t1")
        manager.schedule(_request(), instance, now_tick=0)
        self.assertTrue(manager.persistence.exists(instance.instance_id))
        self.assertEqual(
            manager.persistence.load(instance.instance_id), instance
        )


# =====================================================================
# Notification integration
# =====================================================================
class NotificationIntegrationTests(unittest.TestCase):
    def test_run_due_records_started_notification(self):
        manager = _manager()
        manager.schedule(_request(), _instance("t1"), now_tick=0)
        manager.run_due(0)
        events = [n.event for n in manager.notification_manager.dispatched()]
        self.assertIn(ne.NotificationEvent.WORKFLOW_STARTED, events)

    def test_cancel_records_cancelled_notification(self):
        manager = _manager()
        result = manager.schedule(_request(), _instance("t1"), now_tick=0)
        manager.cancel(result.entry.entry_id)
        events = [n.event for n in manager.notification_manager.dispatched()]
        self.assertIn(ne.NotificationEvent.WORKFLOW_CANCELLED, events)


# =====================================================================
# DTO immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def setUp(self):
        self.manager = _manager()
        self.result = self.manager.schedule(
            _request(), _instance("t1"), now_tick=0
        )

    def test_request_is_frozen(self):
        with self.assertRaises(ValidationError):
            _request().schedule_type = ScheduleType.DELAYED

    def test_entry_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.result.entry.status = ScheduleStatus.CANCELLED

    def test_metadata_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.result.entry.metadata.created_at_tick = 99

    def test_result_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.result.success = False


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_basic_providers(self):
        from app.core.dependencies import (
            get_schedule_planner,
            get_schedule_policy,
            get_schedule_queue,
            get_workflow_execution_scheduler,
        )

        self.assertIsInstance(get_schedule_policy(), RequestSchedulePolicy)
        self.assertIsInstance(get_schedule_planner(), SchedulePlanner)
        self.assertIsInstance(get_schedule_queue(), ScheduleQueue)
        self.assertIsInstance(
            get_workflow_execution_scheduler(), ExecutionScheduler
        )

    def test_manager_provider_wires_collaborators(self):
        from app.core.dependencies import get_scheduler_manager

        manager = get_scheduler_manager()
        self.assertIsInstance(manager, SchedulerManager)
        self.assertIsInstance(manager.policy, SchedulePolicy)
        self.assertIsInstance(manager.planner, SchedulePlanner)
        self.assertIsInstance(manager.queue, ScheduleQueue)
        self.assertIsInstance(
            manager.execution_scheduler, ExecutionScheduler
        )
        self.assertIsInstance(manager.persistence, PersistenceManager)

    def test_manager_provider_uses_injected(self):
        from app.core.dependencies import get_scheduler_manager

        policy = ImmediatePolicy()
        manager = get_scheduler_manager(policy=policy)
        self.assertIs(manager.policy, policy)

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            SchedulePlannerDep,
            SchedulePolicyDep,
            ScheduleQueueDep,
            SchedulerManagerDep,
            WorkflowExecutionSchedulerDep,
        )

        for dep in (
            SchedulePolicyDep,
            SchedulePlannerDep,
            ScheduleQueueDep,
            WorkflowExecutionSchedulerDep,
            SchedulerManagerDep,
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
        "threading",
        "asyncio",
        "time",
        "sched",
        "croniter",
        "apscheduler",
        "celery",
        "temporalio",
    }

    def test_frozen_planning_execution_scheduler_is_distinct(self):
        from app.core.dependencies import get_execution_scheduler
        from app.services.planning.execution_scheduler import (
            ExecutionScheduler as PlanningExecutionScheduler,
        )

        self.assertIsInstance(
            get_execution_scheduler(), PlanningExecutionScheduler
        )
        self.assertIsNot(PlanningExecutionScheduler, ExecutionScheduler)

    def test_frozen_166_memory_orchestrator_unchanged(self):
        from app.core.dependencies import get_memory_orchestrator
        import app.services.ai_employee.memory as memory_engine

        self.assertIsInstance(
            get_memory_orchestrator(), memory_engine.MemoryOrchestrator
        )

    def test_frozen_161_ai_employee_unchanged(self):
        from app.core.dependencies import get_ai_employee

        self.assertEqual(
            set(vars(get_ai_employee())),
            {"planning_engine", "workflow_coordinator"},
        )

    def test_scheduler_package_imports_nothing_forbidden(self):
        import app.services.ai_employee.scheduler as pkg

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


if __name__ == "__main__":
    unittest.main()
