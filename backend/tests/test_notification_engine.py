"""Unit + integration tests for the Sprint 16.4 Notification Engine.

Exercises the production-grade notification subsystem: the configurable
:class:`PriorityModel`, the :class:`NotificationPolicy` implementations
(:class:`ImmediateNotificationPolicy`, :class:`BatchedNotificationPolicy`), the
deterministic priority :class:`NotificationQueue`, the
:class:`NotificationDispatcher` abstraction with
:class:`InMemoryNotificationDispatcher`, the :class:`NotificationHistory` store,
the :class:`NotificationManager` engine, and the
:class:`NotificationWorkflowCoordinator` that records notifications from the frozen
Sprint 16.2 :class:`WorkflowLifecycleManager` transitions. No network or SDK;
everything is deterministic, in-memory, and delivers nothing externally.

Covers, as the sprint requires: notification creation, priority ordering,
policies, immediate dispatch, batch dispatch, queue operations, history, workflow
integration, the dispatcher abstraction, DTO immutability, DI wiring, and
regression (Sprints 16.1–16.3 unchanged; the frozen notification abstraction still
works; the notification sub-package imports no capability module).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_notification_engine
"""

import ast
import os
import unittest

from pydantic import ValidationError

from app.services.ai_employee import (
    EmployeeProfile,
    TaskDelegation,
    WorkflowLifecycleStatus,
)
from app.services.ai_employee.notification import (
    BatchedNotificationPolicy,
    DEFAULT_EVENT_PRIORITY,
    ImmediateNotificationPolicy,
    InMemoryNotificationDispatcher,
    NotificationDispatcher,
    NotificationEvent,
    NotificationHistory,
    NotificationHistoryEntry,
    NotificationManager,
    NotificationMessage,
    NotificationPolicy,
    NotificationPolicyResult,
    NotificationPriority,
    NotificationQueue,
    NotificationQueueItem,
    NotificationStatus,
    NotificationWorkflowCoordinator,
    PriorityModel,
)
from app.services.runtime.workflow_models import (
    WorkflowExecutionResult,
    WorkflowStatus,
    WorkflowStep,
)


# =====================================================================
# Helpers
# =====================================================================
def _engine(policy=None):
    return NotificationManager(
        policy or ImmediateNotificationPolicy(),
        NotificationQueue(),
        InMemoryNotificationDispatcher(),
        NotificationHistory(),
        PriorityModel(),
    )


def _message(
    priority=NotificationPriority.NORMAL,
    event=NotificationEvent.WORKFLOW_STARTED,
    workflow_id="wf1",
    message_id="m1",
):
    return NotificationMessage(
        message_id=message_id,
        workflow_id=workflow_id,
        event=event,
        priority=priority,
    )


def _item(priority, sequence, workflow_id="wf1", event=NotificationEvent.WORKFLOW_STARTED):
    return NotificationQueueItem(
        item_id=f"item-{sequence}",
        message=_message(
            priority, event, workflow_id, message_id=f"m-{sequence}"
        ),
        priority=priority,
        sequence=sequence,
    )


def _profile():
    return EmployeeProfile(employee_id="e1", name="Ada")


def _delegation(task_id="t1"):
    return TaskDelegation(task_id=task_id, task="do it")


def _steps():
    return [WorkflowStep(step_id="s1", capability_name="demo")]


def _workflow_result(status=WorkflowStatus.COMPLETED.value):
    return WorkflowExecutionResult(
        workflow_id="wf", workflow_status=status, total_step_count=1
    )


def _coordinator():
    from app.core.dependencies import get_workflow_lifecycle_manager

    return NotificationWorkflowCoordinator(
        get_workflow_lifecycle_manager(), _engine()
    )


# =====================================================================
# Priority model
# =====================================================================
class PriorityModelTests(unittest.TestCase):
    def setUp(self):
        self.model = PriorityModel()

    def test_default_mapping_covers_every_event(self):
        for event in NotificationEvent:
            self.assertIn(event, DEFAULT_EVENT_PRIORITY)
            self.assertIsInstance(
                self.model.priority(event), NotificationPriority
            )

    def test_failure_is_critical(self):
        self.assertEqual(
            self.model.priority(NotificationEvent.WORKFLOW_FAILED),
            NotificationPriority.CRITICAL,
        )

    def test_pause_is_low(self):
        self.assertEqual(
            self.model.priority(NotificationEvent.WORKFLOW_PAUSED),
            NotificationPriority.LOW,
        )

    def test_priority_is_configurable(self):
        model = PriorityModel(
            event_priority={
                NotificationEvent.WORKFLOW_STARTED: NotificationPriority.CRITICAL
            }
        )
        self.assertEqual(
            model.priority(NotificationEvent.WORKFLOW_STARTED),
            NotificationPriority.CRITICAL,
        )

    def test_priority_is_deterministic(self):
        self.assertEqual(
            self.model.priority(NotificationEvent.APPROVAL_REQUIRED),
            self.model.priority(NotificationEvent.APPROVAL_REQUIRED),
        )


# =====================================================================
# Policies
# =====================================================================
class NotificationPolicyTests(unittest.TestCase):
    def test_immediate_dispatches_whenever_pending(self):
        policy = ImmediateNotificationPolicy()
        result = policy.evaluate(2)
        self.assertIsInstance(result, NotificationPolicyResult)
        self.assertTrue(result.should_dispatch)
        self.assertEqual(result.batch_size, 2)

    def test_immediate_holds_when_empty(self):
        result = ImmediateNotificationPolicy().evaluate(0)
        self.assertFalse(result.should_dispatch)
        self.assertEqual(result.batch_size, 0)

    def test_batched_holds_below_threshold(self):
        policy = BatchedNotificationPolicy(batch_size=3)
        self.assertFalse(policy.evaluate(2).should_dispatch)

    def test_batched_dispatches_at_threshold(self):
        policy = BatchedNotificationPolicy(batch_size=3)
        result = policy.evaluate(3)
        self.assertTrue(result.should_dispatch)
        self.assertEqual(result.batch_size, 3)

    def test_policies_are_notification_policies(self):
        self.assertIsInstance(ImmediateNotificationPolicy(), NotificationPolicy)
        self.assertIsInstance(BatchedNotificationPolicy(), NotificationPolicy)


# =====================================================================
# Queue operations & priority ordering
# =====================================================================
class NotificationQueueTests(unittest.TestCase):
    def setUp(self):
        self.queue = NotificationQueue()

    def test_enqueue_and_pending_count(self):
        self.queue.enqueue(_item(NotificationPriority.NORMAL, 1))
        self.assertEqual(self.queue.pending_count(), 1)

    def test_priority_ordering_highest_first(self):
        self.queue.enqueue(_item(NotificationPriority.LOW, 1))
        self.queue.enqueue(_item(NotificationPriority.CRITICAL, 2))
        self.queue.enqueue(_item(NotificationPriority.NORMAL, 3))
        order = [item.priority for item in self.queue.pending()]
        self.assertEqual(
            order,
            [
                NotificationPriority.CRITICAL,
                NotificationPriority.NORMAL,
                NotificationPriority.LOW,
            ],
        )

    def test_fifo_within_same_priority(self):
        self.queue.enqueue(_item(NotificationPriority.HIGH, 1))
        self.queue.enqueue(_item(NotificationPriority.HIGH, 2))
        order = [item.sequence for item in self.queue.pending()]
        self.assertEqual(order, [1, 2])

    def test_peek_does_not_remove(self):
        self.queue.enqueue(_item(NotificationPriority.LOW, 1))
        self.queue.enqueue(_item(NotificationPriority.CRITICAL, 2))
        peeked = self.queue.peek()
        self.assertEqual(peeked.priority, NotificationPriority.CRITICAL)
        self.assertEqual(self.queue.pending_count(), 2)

    def test_dequeue_returns_highest_priority(self):
        self.queue.enqueue(_item(NotificationPriority.LOW, 1))
        self.queue.enqueue(_item(NotificationPriority.CRITICAL, 2))
        self.assertEqual(
            self.queue.dequeue().priority, NotificationPriority.CRITICAL
        )
        self.assertEqual(self.queue.pending_count(), 1)

    def test_dequeue_empty_returns_none(self):
        self.assertIsNone(self.queue.dequeue())

    def test_dequeue_batch_retrieval(self):
        for i, prio in enumerate(
            (NotificationPriority.LOW, NotificationPriority.CRITICAL,
             NotificationPriority.HIGH),
            start=1,
        ):
            self.queue.enqueue(_item(prio, i))
        released = self.queue.dequeue_batch(2)
        self.assertEqual(
            [item.priority for item in released],
            [NotificationPriority.CRITICAL, NotificationPriority.HIGH],
        )
        self.assertEqual(self.queue.pending_count(), 1)


# =====================================================================
# Notification creation & immediate dispatch
# =====================================================================
class NotificationCreationTests(unittest.TestCase):
    def test_notify_creates_queued_message_with_priority(self):
        engine = _engine(BatchedNotificationPolicy(10))  # hold so it stays queued
        message = engine.notify(NotificationEvent.WORKFLOW_FAILED, "wf1")
        self.assertIsInstance(message, NotificationMessage)
        self.assertEqual(message.event, NotificationEvent.WORKFLOW_FAILED)
        self.assertEqual(message.priority, NotificationPriority.CRITICAL)
        self.assertEqual(message.status, NotificationStatus.QUEUED)
        self.assertEqual(message.workflow_id, "wf1")

    def test_message_ids_are_deterministic(self):
        a = _engine(BatchedNotificationPolicy(10)).notify(
            NotificationEvent.WORKFLOW_STARTED, "wf1"
        )
        b = _engine(BatchedNotificationPolicy(10)).notify(
            NotificationEvent.WORKFLOW_STARTED, "wf1"
        )
        self.assertEqual(a.message_id, b.message_id)

    def test_immediate_policy_dispatches_on_notify(self):
        engine = _engine()  # immediate
        engine.notify(NotificationEvent.WORKFLOW_STARTED, "wf1")
        self.assertEqual(len(engine.pending()), 0)
        self.assertEqual(len(engine.dispatched()), 1)
        self.assertEqual(
            engine.dispatched()[0].status, NotificationStatus.DISPATCHED
        )

    def test_batched_policy_holds_until_threshold(self):
        engine = _engine(BatchedNotificationPolicy(3))
        engine.notify(NotificationEvent.WORKFLOW_STARTED, "wf1")
        engine.notify(NotificationEvent.WORKFLOW_STARTED, "wf1")
        self.assertEqual(len(engine.pending()), 2)
        self.assertEqual(len(engine.dispatched()), 0)
        engine.notify(NotificationEvent.WORKFLOW_STARTED, "wf1")  # triggers flush
        self.assertEqual(len(engine.pending()), 0)
        self.assertEqual(len(engine.dispatched()), 3)

    def test_flush_dispatches_in_priority_order(self):
        engine = _engine(BatchedNotificationPolicy(10))  # never auto-flush
        engine.notify(NotificationEvent.WORKFLOW_PAUSED, "wf1")   # LOW
        engine.notify(NotificationEvent.WORKFLOW_FAILED, "wf1")   # CRITICAL
        engine.notify(NotificationEvent.WORKFLOW_STARTED, "wf1")  # NORMAL
        dispatched = engine.flush()
        self.assertEqual(
            [m.priority for m in dispatched],
            [
                NotificationPriority.CRITICAL,
                NotificationPriority.NORMAL,
                NotificationPriority.LOW,
            ],
        )

    def test_notify_is_deterministic(self):
        first = _engine()
        second = _engine()
        first.notify(NotificationEvent.WORKFLOW_COMPLETED, "wf1")
        second.notify(NotificationEvent.WORKFLOW_COMPLETED, "wf1")
        self.assertEqual(first.dispatched(), second.dispatched())


# =====================================================================
# Dispatcher abstraction
# =====================================================================
class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.dispatcher = InMemoryNotificationDispatcher()

    def test_is_a_notification_dispatcher(self):
        self.assertIsInstance(self.dispatcher, NotificationDispatcher)

    def test_dispatch_marks_dispatched(self):
        dispatched = self.dispatcher.dispatch(_message())
        self.assertEqual(dispatched.status, NotificationStatus.DISPATCHED)
        self.assertEqual(len(self.dispatcher.dispatched()), 1)

    def test_dispatch_batch(self):
        result = self.dispatcher.dispatch_batch(
            [_message(message_id="m1"), _message(message_id="m2")]
        )
        self.assertEqual(len(result), 2)
        self.assertTrue(
            all(m.status == NotificationStatus.DISPATCHED for m in result)
        )

    def test_mark_delivered_moves_to_delivered(self):
        dispatched = self.dispatcher.dispatch(_message())
        delivered = self.dispatcher.mark_delivered(dispatched)
        self.assertEqual(delivered.status, NotificationStatus.DELIVERED)
        self.assertEqual(len(self.dispatcher.delivered()), 1)
        self.assertEqual(len(self.dispatcher.dispatched()), 0)


# =====================================================================
# History
# =====================================================================
class NotificationHistoryTests(unittest.TestCase):
    def test_immediate_flow_records_full_lifecycle(self):
        engine = _engine()
        message = engine.notify(NotificationEvent.WORKFLOW_STARTED, "wf1")
        engine.mark_delivered(engine.dispatched()[0])
        statuses = [
            entry.status for entry in engine.history.find_by_workflow("wf1")
        ]
        self.assertEqual(
            statuses,
            [
                NotificationStatus.QUEUED,
                NotificationStatus.DISPATCHED,
                NotificationStatus.DELIVERED,
            ],
        )

    def test_find_by_workflow(self):
        engine = _engine()
        engine.notify(NotificationEvent.WORKFLOW_STARTED, "wf1")
        engine.notify(NotificationEvent.WORKFLOW_STARTED, "wf2")
        self.assertTrue(
            all(
                e.message.workflow_id == "wf1"
                for e in engine.history.find_by_workflow("wf1")
            )
        )
        self.assertEqual(len(engine.history.find_by_workflow("nope")), 0)

    def test_find_by_type(self):
        engine = _engine()
        engine.notify(NotificationEvent.WORKFLOW_STARTED, "wf1")
        engine.notify(NotificationEvent.WORKFLOW_FAILED, "wf1")
        found = engine.history.find_by_type(NotificationEvent.WORKFLOW_FAILED)
        self.assertTrue(
            all(
                e.message.event == NotificationEvent.WORKFLOW_FAILED
                for e in found
            )
        )

    def test_find_by_status(self):
        engine = _engine()
        engine.notify(NotificationEvent.WORKFLOW_STARTED, "wf1")
        queued = engine.history.find_by_status(NotificationStatus.QUEUED)
        dispatched = engine.history.find_by_status(NotificationStatus.DISPATCHED)
        self.assertEqual(len(queued), 1)
        self.assertEqual(len(dispatched), 1)


# =====================================================================
# Workflow integration
# =====================================================================
class WorkflowIntegrationTests(unittest.TestCase):
    def _started(self, coord):
        instance = coord.lifecycle_manager.create_instance(
            _profile(), _delegation(), _steps()
        )
        return coord.start(instance)

    def _events(self, coord, instance_id):
        return [
            entry.message.event
            for entry in coord.notification_manager.history.find_by_workflow(
                instance_id
            )
            if entry.status == NotificationStatus.QUEUED
        ]

    def test_start_records_started_notification(self):
        coord = _coordinator()
        started = self._started(coord)
        self.assertEqual(
            started.lifecycle_state.status, WorkflowLifecycleStatus.RUNNING
        )
        self.assertIn(
            NotificationEvent.WORKFLOW_STARTED,
            self._events(coord, started.instance_id),
        )

    def test_pause_resume_cancel_record_notifications(self):
        coord = _coordinator()
        started = self._started(coord)
        paused = coord.pause(started)
        resumed = coord.resume(paused)
        cancelled = coord.cancel(resumed)
        self.assertEqual(
            cancelled.lifecycle_state.status,
            WorkflowLifecycleStatus.CANCELLED,
        )
        events = self._events(coord, started.instance_id)
        for expected in (
            NotificationEvent.WORKFLOW_STARTED,
            NotificationEvent.WORKFLOW_PAUSED,
            NotificationEvent.WORKFLOW_RESUMED,
            NotificationEvent.WORKFLOW_CANCELLED,
        ):
            self.assertIn(expected, events)

    def test_complete_records_completed_notification(self):
        coord = _coordinator()
        started = self._started(coord)
        completed = coord.complete(started, _workflow_result())
        self.assertEqual(
            completed.lifecycle_state.status,
            WorkflowLifecycleStatus.COMPLETED,
        )
        self.assertIn(
            NotificationEvent.WORKFLOW_COMPLETED,
            self._events(coord, started.instance_id),
        )

    def test_fail_records_failed_notification(self):
        coord = _coordinator()
        started = self._started(coord)
        failed = coord.fail(
            started, _workflow_result(WorkflowStatus.FAILED.value)
        )
        self.assertEqual(
            failed.lifecycle_state.status, WorkflowLifecycleStatus.FAILED
        )
        self.assertIn(
            NotificationEvent.WORKFLOW_FAILED,
            self._events(coord, started.instance_id),
        )

    def test_coordinator_holds_no_state(self):
        coord = _coordinator()
        self.assertEqual(
            set(vars(coord)),
            {"lifecycle_manager", "notification_manager"},
        )


# =====================================================================
# DTO immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def setUp(self):
        self.engine = _engine(BatchedNotificationPolicy(10))
        self.message = self.engine.notify(
            NotificationEvent.WORKFLOW_STARTED, "wf1"
        )

    def test_message_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.message.status = NotificationStatus.DELIVERED

    def test_queue_item_is_frozen(self):
        item = self.engine.pending()[0]
        with self.assertRaises(ValidationError):
            item.priority = NotificationPriority.LOW

    def test_history_entry_is_frozen(self):
        entry = self.engine.history.all()[0]
        with self.assertRaises(ValidationError):
            entry.status = NotificationStatus.DELIVERED

    def test_policy_result_is_frozen(self):
        result = ImmediateNotificationPolicy().evaluate(1)
        with self.assertRaises(ValidationError):
            result.should_dispatch = False


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_basic_providers(self):
        from app.core.dependencies import (
            get_notification_dispatcher,
            get_notification_history,
            get_notification_policy,
            get_notification_priority_model,
            get_notification_queue,
        )

        self.assertIsInstance(get_notification_priority_model(), PriorityModel)
        self.assertIsInstance(
            get_notification_policy(), ImmediateNotificationPolicy
        )
        self.assertIsInstance(get_notification_queue(), NotificationQueue)
        self.assertIsInstance(
            get_notification_dispatcher(), InMemoryNotificationDispatcher
        )
        self.assertIsInstance(get_notification_history(), NotificationHistory)

    def test_engine_provider_wires_collaborators(self):
        from app.core.dependencies import get_notification_engine

        engine = get_notification_engine()
        self.assertIsInstance(engine, NotificationManager)
        self.assertIsInstance(engine.policy, NotificationPolicy)
        self.assertIsInstance(engine.queue, NotificationQueue)
        self.assertIsInstance(engine.dispatcher, NotificationDispatcher)
        self.assertIsInstance(engine.history, NotificationHistory)
        self.assertIsInstance(engine.priority_model, PriorityModel)

    def test_engine_provider_uses_injected(self):
        from app.core.dependencies import get_notification_engine

        policy = BatchedNotificationPolicy(5)
        engine = get_notification_engine(policy=policy)
        self.assertIs(engine.policy, policy)

    def test_coordinator_provider_wires_collaborators(self):
        from app.core.dependencies import get_notification_workflow_coordinator
        from app.services.ai_employee import WorkflowLifecycleManager

        coord = get_notification_workflow_coordinator()
        self.assertIsInstance(coord, NotificationWorkflowCoordinator)
        self.assertIsInstance(
            coord.lifecycle_manager, WorkflowLifecycleManager
        )
        self.assertIsInstance(coord.notification_manager, NotificationManager)

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            NotificationDispatcherDep,
            NotificationEngineDep,
            NotificationHistoryDep,
            NotificationPolicyDep,
            NotificationPriorityModelDep,
            NotificationQueueDep,
            NotificationWorkflowCoordinatorDep,
        )

        for dep in (
            NotificationPriorityModelDep,
            NotificationPolicyDep,
            NotificationQueueDep,
            NotificationDispatcherDep,
            NotificationHistoryDep,
            NotificationEngineDep,
            NotificationWorkflowCoordinatorDep,
        ):
            self.assertIsNotNone(dep)


# =====================================================================
# Regression: prior sprints frozen; frozen notification intact; no capability
# =====================================================================
class RegressionTests(unittest.TestCase):
    _FORBIDDEN_CAPABILITY_MODULES = {
        "browser_capability",
        "python_capability",
        "filesystem_capability",
        "email_capability",
        "calendar_capability",
        "github_capability",
    }

    def test_frozen_162_notification_manager_unchanged(self):
        # The frozen Sprint 16.2 NotificationManager ABC + InMemoryNotificationManager
        # still exist and behave as before (distinct from the Sprint 16.4 engine).
        from app.core.dependencies import get_notification_manager
        from app.services.ai_employee import (
            InMemoryNotificationManager as FrozenInMemory,
        )
        from app.services.ai_employee import (
            NotificationManager as FrozenNotificationManager,
        )

        frozen = get_notification_manager()
        self.assertIsInstance(frozen, FrozenInMemory)
        self.assertIsInstance(frozen, FrozenNotificationManager)
        self.assertIsNot(FrozenNotificationManager, NotificationManager)

    def test_frozen_163_approval_engine_unchanged(self):
        from app.core.dependencies import get_approval_engine
        import app.services.ai_employee.approval as approval_engine

        self.assertIsInstance(
            get_approval_engine(), approval_engine.ApprovalManager
        )

    def test_frozen_162_lifecycle_manager_unchanged(self):
        from app.core.dependencies import get_workflow_lifecycle_manager
        from app.services.ai_employee import WorkflowLifecycleManager

        self.assertIsInstance(
            get_workflow_lifecycle_manager(), WorkflowLifecycleManager
        )

    def test_frozen_161_ai_employee_unchanged(self):
        from app.core.dependencies import get_ai_employee

        self.assertEqual(
            set(vars(get_ai_employee())),
            {"planning_engine", "workflow_coordinator"},
        )

    def test_notification_package_imports_no_capability_module(self):
        import app.services.ai_employee.notification as pkg

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
                    if tail in self._FORBIDDEN_CAPABILITY_MODULES:
                        offenders.append((filename, name))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
