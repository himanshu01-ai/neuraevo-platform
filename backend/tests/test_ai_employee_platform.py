"""Unit + integration tests for the Sprint 16.2 AI Employee Execution Platform.

Exercises the *lifecycle of a delegated job*: :class:`WorkflowLifecycleManager`
coordinating an immutable :class:`WorkflowInstance` through its five managers
(:class:`ProgressTracker`, :class:`ApprovalManager`, :class:`NotificationManager`,
:class:`RecoveryManager`, :class:`PersistenceManager`), the real Sprint 13
Planning Engine, and the real Sprint 15.15 Workflow Coordinator. No network or
SDK: the coordinator runs over an offline, deterministic stub
:class:`ExecutionCapability`; recording doubles isolate the manager to assert
*invocation* precisely.

Covers, as the sprint requires: workflow lifecycle (create/start/pause/resume/
cancel/complete/fail and invalid-transition guards), retry, progress tracking, the
approval abstraction, notification creation (stored, not delivered), recovery,
persistence, DI wiring, immutability, and regression (Sprint 16.1 Foundation, the
Planning Engine, and the Workflow Coordinator provider are unchanged; the platform
imports no capability module).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_ai_employee_platform
"""

import ast
import os
import unittest

from pydantic import ValidationError

from app.services.ai_employee import (
    ApprovalDecision,
    ApprovalManager,
    AutoApprovalPolicy,
    BasicRecoveryManager,
    EmployeeProfile,
    InMemoryNotificationManager,
    InMemoryPersistenceManager,
    NotificationManager,
    PersistenceManager,
    ProgressTracker,
    RecoveryManager,
    TaskDelegation,
    TaskPriority,
    WorkflowInstance,
    WorkflowLifecycleError,
    WorkflowLifecycleManager,
    WorkflowLifecycleState,
    WorkflowLifecycleStatus,
    WorkflowNotification,
    WorkflowNotificationEvent,
    WorkflowProgress,
    WorkflowProgressStatus,
    WorkflowSnapshot,
)
from app.services.planning.models import ExecutionPlan, PlanningRequest
from app.services.planning.planning_engine import PlanningEngine
from app.services.runtime.artifact_coordinator import ArtifactCoordinator
from app.services.runtime.capability_router import CapabilityRouter
from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
    CapabilityExecutionStatus,
)
from app.services.runtime.workflow_coordinator import WorkflowCoordinator
from app.services.runtime.workflow_models import (
    WorkflowExecutionResult,
    WorkflowStatus,
    WorkflowStep,
)

_COMPLETED = CapabilityExecutionStatus.COMPLETED.value
_FAILED = CapabilityExecutionStatus.FAILED.value


# =====================================================================
# Offline capability doubles (NOT real capabilities)
# =====================================================================
class _CompletingCapability(ExecutionCapability):
    def execute(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=_COMPLETED,
            capability_outputs={"ok": True},
            execution_metadata={},
        )


class _FailingCapability(ExecutionCapability):
    def execute(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=_FAILED,
            capability_outputs={"error": "boom"},
            execution_metadata={},
        )


# =====================================================================
# Recording / stub doubles
# =====================================================================
class _RecordingPlanningEngine:
    """Records ``create_plan`` calls; returns a real fixed plan (duck-typed)."""

    def __init__(self):
        self._plan = ExecutionPlan(goal="reason about it", summary="a plan")
        self.requests = []

    def create_plan(self, request: PlanningRequest) -> ExecutionPlan:
        self.requests.append(request)
        return self._plan


class _RecordingWorkflowCoordinator:
    """Records ``execute`` calls; returns a fixed workflow result (duck-typed)."""

    def __init__(self, result: WorkflowExecutionResult):
        self._result = result
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
            {
                "steps": steps,
                "workflow_id": workflow_id,
                "runtime_id": runtime_id,
                "execution_id": execution_id,
                "initial_inputs": initial_inputs,
            }
        )
        return self._result


class _AlwaysApprovalRequiredPolicy(ApprovalManager):
    """A policy that always gates a run — to exercise the approval path."""

    def requires_approval(self, instance) -> bool:
        return True

    def approve(self, instance) -> ApprovalDecision:
        return ApprovalDecision(
            workflow_instance_id=instance.instance_id,
            approved=True,
            requires_approval=True,
            policy="AlwaysApprovalRequired",
            reason="approved",
        )

    def reject(self, instance) -> ApprovalDecision:
        return ApprovalDecision(
            workflow_instance_id=instance.instance_id,
            approved=False,
            requires_approval=True,
            policy="AlwaysApprovalRequired",
            reason="rejected",
        )


# =====================================================================
# Helpers
# =====================================================================
def _profile() -> EmployeeProfile:
    return EmployeeProfile(employee_id="e1", name="Ada")


def _delegation(task_id="t1") -> TaskDelegation:
    return TaskDelegation(
        task_id=task_id, task="plan a trip", priority=TaskPriority.HIGH
    )


def _steps(n=2):
    return [
        WorkflowStep(step_id=f"s{i}", capability_name="demo")
        for i in range(1, n + 1)
    ]


def _real_planning():
    from app.core.dependencies import get_execution_orchestration_engine

    return get_execution_orchestration_engine()


def _manager(
    capability=None, planning=None, coordinator=None, approval=None
) -> WorkflowLifecycleManager:
    """A lifecycle manager with fresh, isolated managers for each test."""
    if coordinator is not None:
        workflow_coordinator = coordinator
    else:
        workflow_coordinator = WorkflowCoordinator(
            CapabilityRouter({"demo": capability or _CompletingCapability()}),
            ArtifactCoordinator(),
        )
    return WorkflowLifecycleManager(
        planning if planning is not None else _real_planning(),
        workflow_coordinator,
        ProgressTracker(),
        approval or AutoApprovalPolicy(),
        InMemoryNotificationManager(),
        BasicRecoveryManager(),
        InMemoryPersistenceManager(),
    )


def _workflow_result(status, total=2, completed=2, failed=None):
    return WorkflowExecutionResult(
        workflow_id="wf",
        workflow_status=status,
        failed_step_id=failed,
        completed_step_count=completed,
        total_step_count=total,
    )


# =====================================================================
# Instance creation
# =====================================================================
class InstanceCreationTests(unittest.TestCase):
    def test_create_instance_is_pending_with_derived_ids(self):
        mgr = _manager()
        instance = mgr.create_instance(_profile(), _delegation(), _steps())
        self.assertIsInstance(instance, WorkflowInstance)
        self.assertEqual(instance.instance_id, "instance-e1-t1")
        self.assertEqual(instance.workflow_id, "workflow-t1")
        self.assertEqual(
            instance.lifecycle_state.status, WorkflowLifecycleStatus.PENDING
        )
        self.assertEqual(instance.total_steps, 2)
        self.assertEqual(instance.progress.status, WorkflowProgressStatus.PENDING)
        self.assertEqual(instance.progress.percentage, 0)
        self.assertIsNone(instance.workflow_result)

    def test_create_instance_attaches_a_plan(self):
        mgr = _manager()
        instance = mgr.create_instance(_profile(), _delegation(), _steps())
        self.assertIsInstance(instance.plan, ExecutionPlan)
        self.assertTrue(instance.plan.goal)

    def test_manager_references_are_plain_strings(self):
        mgr = _manager()
        instance = mgr.create_instance(_profile(), _delegation(), _steps())
        self.assertEqual(
            set(instance.manager_references),
            {
                "planning_engine",
                "workflow_coordinator",
                "progress_tracker",
                "approval_manager",
                "notification_manager",
                "recovery_manager",
                "persistence_manager",
            },
        )
        for value in instance.manager_references.values():
            self.assertIsInstance(value, str)

    def test_create_instance_persists(self):
        mgr = _manager()
        instance = mgr.create_instance(_profile(), _delegation(), _steps())
        self.assertEqual(
            mgr.persistence_manager.load_instance(instance.instance_id), instance
        )

    def test_create_instance_is_deterministic(self):
        first = _manager().create_instance(_profile(), _delegation(), _steps())
        second = _manager().create_instance(_profile(), _delegation(), _steps())
        self.assertEqual(first, second)


# =====================================================================
# Lifecycle transitions
# =====================================================================
class LifecycleTransitionTests(unittest.TestCase):
    def setUp(self):
        self.mgr = _manager()
        self.instance = self.mgr.create_instance(
            _profile(), _delegation(), _steps()
        )

    def test_start_moves_pending_to_running(self):
        started = self.mgr.start(self.instance)
        self.assertEqual(
            started.lifecycle_state.status, WorkflowLifecycleStatus.RUNNING
        )
        self.assertEqual(
            started.lifecycle_state.previous_status,
            WorkflowLifecycleStatus.PENDING,
        )
        self.assertEqual(started.lifecycle_state.transition_sequence, 1)

    def test_start_records_started_notification(self):
        self.mgr.start(self.instance)
        events = [
            n.event
            for n in self.mgr.notification_manager.notifications(
                self.instance.instance_id
            )
        ]
        self.assertIn(WorkflowNotificationEvent.WORKFLOW_STARTED, events)

    def test_pause_and_resume(self):
        paused = self.mgr.pause(self.mgr.start(self.instance))
        self.assertEqual(
            paused.lifecycle_state.status, WorkflowLifecycleStatus.PAUSED
        )
        resumed = self.mgr.resume(paused)
        self.assertEqual(
            resumed.lifecycle_state.status, WorkflowLifecycleStatus.RUNNING
        )

    def test_cancel_is_terminal(self):
        cancelled = self.mgr.cancel(self.mgr.start(self.instance))
        self.assertEqual(
            cancelled.lifecycle_state.status, WorkflowLifecycleStatus.CANCELLED
        )
        self.assertTrue(cancelled.lifecycle_state.is_terminal)

    def test_cancel_directly_from_pending(self):
        cancelled = self.mgr.cancel(self.instance)
        self.assertEqual(
            cancelled.lifecycle_state.status, WorkflowLifecycleStatus.CANCELLED
        )

    def test_complete_folds_in_progress_and_result(self):
        started = self.mgr.start(self.instance)
        result = _workflow_result(WorkflowStatus.COMPLETED.value)
        completed = self.mgr.complete(started, result)
        self.assertEqual(
            completed.lifecycle_state.status, WorkflowLifecycleStatus.COMPLETED
        )
        self.assertTrue(completed.lifecycle_state.is_terminal)
        self.assertEqual(completed.progress.percentage, 100)
        self.assertIs(completed.workflow_result, result)

    def test_complete_records_completed_notification(self):
        started = self.mgr.start(self.instance)
        self.mgr.complete(started, _workflow_result(WorkflowStatus.COMPLETED.value))
        events = [
            n.event
            for n in self.mgr.notification_manager.notifications(
                self.instance.instance_id
            )
        ]
        self.assertIn(WorkflowNotificationEvent.WORKFLOW_COMPLETED, events)

    def test_fail_is_not_terminal_and_notifies(self):
        started = self.mgr.start(self.instance)
        failed = self.mgr.fail(
            started,
            _workflow_result(
                WorkflowStatus.FAILED.value, completed=1, failed="s2"
            ),
        )
        self.assertEqual(
            failed.lifecycle_state.status, WorkflowLifecycleStatus.FAILED
        )
        self.assertFalse(failed.lifecycle_state.is_terminal)
        self.assertEqual(failed.progress.status, WorkflowProgressStatus.FAILED)
        events = [
            n.event
            for n in self.mgr.notification_manager.notifications(
                self.instance.instance_id
            )
        ]
        self.assertIn(WorkflowNotificationEvent.WORKFLOW_FAILED, events)

    def test_every_transition_persists_latest(self):
        started = self.mgr.start(self.instance)
        loaded = self.mgr.persistence_manager.load_instance(
            self.instance.instance_id
        )
        self.assertEqual(
            loaded.lifecycle_state.status, WorkflowLifecycleStatus.RUNNING
        )
        self.assertEqual(loaded, started)

    def test_invalid_transitions_raise(self):
        # pause is only valid from RUNNING (instance is PENDING)
        with self.assertRaises(WorkflowLifecycleError):
            self.mgr.pause(self.instance)
        # resume is only valid from PAUSED (instance is RUNNING)
        with self.assertRaises(WorkflowLifecycleError):
            self.mgr.resume(self.mgr.start(self.instance))
        # complete is only valid from RUNNING (instance is PENDING)
        with self.assertRaises(WorkflowLifecycleError):
            self.mgr.complete(
                self.instance, _workflow_result(WorkflowStatus.COMPLETED.value)
            )

    def test_no_transition_out_of_terminal(self):
        started = self.mgr.start(self.instance)
        completed = self.mgr.complete(
            started, _workflow_result(WorkflowStatus.COMPLETED.value)
        )
        with self.assertRaises(WorkflowLifecycleError):
            self.mgr.start(completed)
        with self.assertRaises(WorkflowLifecycleError):
            self.mgr.pause(completed)


# =====================================================================
# Run (drives the Workflow Coordinator)
# =====================================================================
class RunTests(unittest.TestCase):
    def test_run_completes_end_to_end(self):
        mgr = _manager(_CompletingCapability())
        instance = mgr.create_instance(_profile(), _delegation(), _steps())
        done = mgr.run(instance)
        self.assertEqual(
            done.lifecycle_state.status, WorkflowLifecycleStatus.COMPLETED
        )
        self.assertEqual(done.progress.status, WorkflowProgressStatus.COMPLETED)
        self.assertEqual(done.progress.percentage, 100)
        self.assertEqual(
            done.workflow_result.workflow_status, WorkflowStatus.COMPLETED.value
        )

    def test_run_fails_gracefully(self):
        mgr = _manager(_FailingCapability())
        instance = mgr.create_instance(_profile(), _delegation(), _steps())
        done = mgr.run(instance)
        self.assertEqual(
            done.lifecycle_state.status, WorkflowLifecycleStatus.FAILED
        )
        self.assertEqual(
            done.workflow_result.workflow_status, WorkflowStatus.FAILED.value
        )

    def test_run_gated_by_approval_does_not_start(self):
        mgr = _manager(approval=_AlwaysApprovalRequiredPolicy())
        instance = mgr.create_instance(_profile(), _delegation(), _steps())
        gated = mgr.run(instance)
        # still PENDING (never started) and an approval_required notification stored
        self.assertEqual(
            gated.lifecycle_state.status, WorkflowLifecycleStatus.PENDING
        )
        self.assertTrue(gated.instance_metadata.get("approval_required"))
        events = [
            n.event
            for n in mgr.notification_manager.notifications(instance.instance_id)
        ]
        self.assertEqual(events, [WorkflowNotificationEvent.APPROVAL_REQUIRED])

    def test_run_forwards_steps_and_ids_to_coordinator(self):
        recording = _RecordingWorkflowCoordinator(
            _workflow_result(WorkflowStatus.COMPLETED.value)
        )
        mgr = _manager(coordinator=recording)
        instance = mgr.create_instance(_profile(), _delegation(), _steps())
        mgr.run(instance, initial_inputs={"seed": 1})
        self.assertEqual(len(recording.calls), 1)
        call = recording.calls[0]
        self.assertEqual(call["steps"], instance.workflow_steps)
        self.assertEqual(call["workflow_id"], "workflow-t1")
        self.assertEqual(call["runtime_id"], "instance-e1-t1")
        self.assertEqual(call["execution_id"], "instance-e1-t1")
        self.assertEqual(call["initial_inputs"], {"seed": 1})

    def test_run_is_deterministic(self):
        first = _manager(_CompletingCapability())
        second = _manager(_CompletingCapability())
        r1 = first.run(first.create_instance(_profile(), _delegation(), _steps()))
        r2 = second.run(
            second.create_instance(_profile(), _delegation(), _steps())
        )
        self.assertEqual(r1, r2)

    def test_run_never_holds_capability_state(self):
        # The lifecycle manager exposes exactly its seven collaborators — no
        # capability, router, or capability handle of its own.
        mgr = _manager()
        self.assertEqual(
            set(vars(mgr)),
            {
                "planning_engine",
                "workflow_coordinator",
                "progress_tracker",
                "approval_manager",
                "notification_manager",
                "recovery_manager",
                "persistence_manager",
            },
        )


# =====================================================================
# Progress tracking
# =====================================================================
class ProgressTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tracker = ProgressTracker()

    def test_initialize_is_pending(self):
        progress = self.tracker.initialize(3)
        self.assertEqual(progress.status, WorkflowProgressStatus.PENDING)
        self.assertEqual(progress.total_steps, 3)
        self.assertEqual(progress.percentage, 0)
        self.assertEqual(progress.current_step, 0)

    def test_track_completed(self):
        progress = self.tracker.track(
            _workflow_result(WorkflowStatus.COMPLETED.value, total=4, completed=4)
        )
        self.assertEqual(progress.status, WorkflowProgressStatus.COMPLETED)
        self.assertEqual(progress.percentage, 100)
        self.assertEqual(progress.current_step, 4)

    def test_track_failed(self):
        progress = self.tracker.track(
            _workflow_result(
                WorkflowStatus.FAILED.value, total=4, completed=1, failed="s2"
            )
        )
        self.assertEqual(progress.status, WorkflowProgressStatus.FAILED)
        self.assertEqual(progress.failed_step, "s2")
        self.assertEqual(progress.percentage, 25)

    def test_track_partial_is_in_progress(self):
        progress = self.tracker.track(
            WorkflowExecutionResult(
                workflow_id="wf",
                workflow_status=WorkflowStatus.RUNNING.value,
                completed_step_count=2,
                total_step_count=5,
            )
        )
        self.assertEqual(progress.status, WorkflowProgressStatus.IN_PROGRESS)
        self.assertEqual(progress.percentage, 40)
        self.assertEqual(progress.current_step, 3)

    def test_track_is_deterministic(self):
        result = _workflow_result(WorkflowStatus.COMPLETED.value)
        self.assertEqual(self.tracker.track(result), self.tracker.track(result))


# =====================================================================
# Approval abstraction
# =====================================================================
class ApprovalManagerTests(unittest.TestCase):
    def setUp(self):
        self.policy = AutoApprovalPolicy()
        self.instance = _manager().create_instance(
            _profile(), _delegation(), _steps()
        )

    def test_auto_policy_never_requires_approval(self):
        self.assertFalse(self.policy.requires_approval(self.instance))

    def test_approve_returns_approved_decision(self):
        decision = self.policy.approve(self.instance)
        self.assertIsInstance(decision, ApprovalDecision)
        self.assertTrue(decision.approved)
        self.assertEqual(decision.policy, "AutoApprovalPolicy")
        self.assertEqual(decision.workflow_instance_id, self.instance.instance_id)

    def test_reject_returns_rejected_decision(self):
        decision = self.policy.reject(self.instance)
        self.assertFalse(decision.approved)

    def test_auto_policy_is_an_approval_manager(self):
        self.assertIsInstance(self.policy, ApprovalManager)


# =====================================================================
# Notification creation (stored, not delivered)
# =====================================================================
class NotificationManagerTests(unittest.TestCase):
    def setUp(self):
        self.notifications = InMemoryNotificationManager()
        self.instance = _manager().create_instance(
            _profile(), _delegation(), _steps()
        )

    def test_is_a_notification_manager(self):
        self.assertIsInstance(self.notifications, NotificationManager)

    def test_four_event_helpers_record_the_right_events(self):
        self.notifications.workflow_started(self.instance)
        self.notifications.workflow_completed(self.instance)
        self.notifications.workflow_failed(self.instance)
        self.notifications.approval_required(self.instance)
        events = [
            n.event
            for n in self.notifications.notifications(self.instance.instance_id)
        ]
        self.assertEqual(
            events,
            [
                WorkflowNotificationEvent.WORKFLOW_STARTED,
                WorkflowNotificationEvent.WORKFLOW_COMPLETED,
                WorkflowNotificationEvent.WORKFLOW_FAILED,
                WorkflowNotificationEvent.APPROVAL_REQUIRED,
            ],
        )

    def test_deterministic_ids_and_sequences(self):
        first = self.notifications.workflow_started(self.instance)
        second = self.notifications.workflow_completed(self.instance)
        self.assertEqual(first.sequence, 0)
        self.assertEqual(second.sequence, 1)
        self.assertEqual(
            first.notification_id,
            f"notification-{self.instance.instance_id}-0",
        )

    def test_notifications_filter_by_instance(self):
        self.notifications.workflow_started(self.instance)
        self.assertEqual(len(self.notifications.notifications("other")), 0)
        self.assertEqual(
            len(self.notifications.notifications(self.instance.instance_id)), 1
        )
        self.assertEqual(len(self.notifications.notifications()), 1)


# =====================================================================
# Recovery
# =====================================================================
class RecoveryManagerTests(unittest.TestCase):
    def setUp(self):
        self.recovery = BasicRecoveryManager()
        self.mgr = _manager(_FailingCapability())
        self.failed = self.mgr.run(
            self.mgr.create_instance(_profile(), _delegation(), _steps())
        )

    def test_is_a_recovery_manager(self):
        self.assertIsInstance(self.recovery, RecoveryManager)

    def test_can_retry_failed_instance(self):
        self.assertTrue(self.recovery.can_retry(self.failed))

    def test_cannot_retry_non_failed_instance(self):
        pending = self.mgr.create_instance(
            _profile(), _delegation("t2"), _steps()
        )
        self.assertFalse(self.recovery.can_retry(pending))

    def test_retry_moves_to_running_and_increments_attempt(self):
        retried = self.recovery.retry(self.failed)
        self.assertEqual(
            retried.lifecycle_state.status, WorkflowLifecycleStatus.RUNNING
        )
        self.assertEqual(retried.lifecycle_state.attempt, 1)

    def test_abort_is_terminal_cancelled(self):
        aborted = self.recovery.abort(self.failed)
        self.assertEqual(
            aborted.lifecycle_state.status, WorkflowLifecycleStatus.CANCELLED
        )
        self.assertTrue(aborted.lifecycle_state.is_terminal)

    def test_lifecycle_retry_delegates_and_persists(self):
        retried = self.mgr.retry(self.failed)
        self.assertEqual(
            retried.lifecycle_state.status, WorkflowLifecycleStatus.RUNNING
        )
        self.assertEqual(retried.lifecycle_state.attempt, 1)
        self.assertEqual(
            self.mgr.persistence_manager.load_instance(retried.instance_id),
            retried,
        )

    def test_lifecycle_retry_raises_when_exhausted(self):
        retried = self.mgr.retry(self.failed)  # attempt -> 1
        refailed = self.mgr.fail(
            retried, _workflow_result(WorkflowStatus.FAILED.value, failed="s1")
        )
        with self.assertRaises(WorkflowLifecycleError):
            self.mgr.retry(refailed)  # attempt 1 == max_attempts 1

    def test_lifecycle_retry_raises_on_non_failed(self):
        pending = self.mgr.create_instance(
            _profile(), _delegation("t3"), _steps()
        )
        with self.assertRaises(WorkflowLifecycleError):
            self.mgr.retry(pending)


# =====================================================================
# Persistence
# =====================================================================
class PersistenceManagerTests(unittest.TestCase):
    def setUp(self):
        self.persistence = InMemoryPersistenceManager()
        self.instance = _manager().create_instance(
            _profile(), _delegation(), _steps()
        )

    def test_is_a_persistence_manager(self):
        self.assertIsInstance(self.persistence, PersistenceManager)

    def test_save_returns_snapshot(self):
        snapshot = self.persistence.save_instance(self.instance)
        self.assertIsInstance(snapshot, WorkflowSnapshot)
        self.assertEqual(snapshot.workflow_instance_id, self.instance.instance_id)
        self.assertIs(snapshot.instance, self.instance)
        self.assertEqual(snapshot.sequence, 1)
        self.assertEqual(
            snapshot.snapshot_id, f"snapshot-{self.instance.instance_id}-1"
        )

    def test_load_returns_saved_instance(self):
        self.persistence.save_instance(self.instance)
        self.assertEqual(
            self.persistence.load_instance(self.instance.instance_id),
            self.instance,
        )

    def test_load_missing_returns_none(self):
        self.assertIsNone(self.persistence.load_instance("nope"))

    def test_delete_reports_existence(self):
        self.persistence.save_instance(self.instance)
        self.assertTrue(self.persistence.delete_instance(self.instance.instance_id))
        self.assertFalse(
            self.persistence.delete_instance(self.instance.instance_id)
        )
        self.assertIsNone(
            self.persistence.load_instance(self.instance.instance_id)
        )

    def test_save_overwrites_latest_wins(self):
        self.persistence.save_instance(self.instance)
        updated = self.instance.model_copy(
            update={"instance_metadata": {"v": 2}}
        )
        snapshot = self.persistence.save_instance(updated)
        self.assertEqual(snapshot.sequence, 2)
        self.assertEqual(
            self.persistence.load_instance(self.instance.instance_id), updated
        )


# =====================================================================
# Immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def setUp(self):
        mgr = _manager(_CompletingCapability())
        self.instance = mgr.run(
            mgr.create_instance(_profile(), _delegation(), _steps())
        )
        self.snapshot = InMemoryPersistenceManager().save_instance(self.instance)

    def test_instance_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.instance.instance_id = "other"

    def test_lifecycle_state_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.instance.lifecycle_state.status = WorkflowLifecycleStatus.PENDING

    def test_progress_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.instance.progress.percentage = 0

    def test_notification_is_frozen(self):
        notification = InMemoryNotificationManager().workflow_started(
            self.instance
        )
        with self.assertRaises(ValidationError):
            notification.message = "x"

    def test_approval_decision_is_frozen(self):
        decision = AutoApprovalPolicy().approve(self.instance)
        with self.assertRaises(ValidationError):
            decision.approved = False

    def test_snapshot_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.snapshot.sequence = 99


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_lifecycle_manager_wires_all_collaborators(self):
        from app.core.dependencies import get_workflow_lifecycle_manager

        mgr = get_workflow_lifecycle_manager()
        self.assertIsInstance(mgr, WorkflowLifecycleManager)
        self.assertIsInstance(mgr.planning_engine, PlanningEngine)
        self.assertIsInstance(mgr.workflow_coordinator, WorkflowCoordinator)
        self.assertIsInstance(mgr.progress_tracker, ProgressTracker)
        self.assertIsInstance(mgr.approval_manager, ApprovalManager)
        self.assertIsInstance(mgr.notification_manager, NotificationManager)
        self.assertIsInstance(mgr.recovery_manager, RecoveryManager)
        self.assertIsInstance(mgr.persistence_manager, PersistenceManager)

    def test_basic_manager_providers(self):
        from app.core.dependencies import (
            get_approval_manager,
            get_notification_manager,
            get_persistence_manager,
            get_progress_tracker,
            get_workflow_recovery_manager,
        )

        self.assertIsInstance(get_progress_tracker(), ProgressTracker)
        self.assertIsInstance(get_approval_manager(), AutoApprovalPolicy)
        self.assertIsInstance(
            get_notification_manager(), InMemoryNotificationManager
        )
        self.assertIsInstance(
            get_workflow_recovery_manager(), BasicRecoveryManager
        )
        self.assertIsInstance(
            get_persistence_manager(), InMemoryPersistenceManager
        )

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            ApprovalManagerDep,
            NotificationManagerDep,
            PersistenceManagerDep,
            ProgressTrackerDep,
            WorkflowLifecycleManagerDep,
            WorkflowRecoveryManagerDep,
        )

        for dep in (
            ProgressTrackerDep,
            ApprovalManagerDep,
            NotificationManagerDep,
            WorkflowRecoveryManagerDep,
            PersistenceManagerDep,
            WorkflowLifecycleManagerDep,
        ):
            self.assertIsNotNone(dep)

    def test_provider_uses_injected_collaborators(self):
        from app.core.dependencies import get_workflow_lifecycle_manager

        planning = _RecordingPlanningEngine()
        mgr = get_workflow_lifecycle_manager(planning_engine=planning)
        self.assertIs(mgr.planning_engine, planning)

    def test_wired_manager_runs_a_delegation(self):
        from app.core.dependencies import get_workflow_lifecycle_manager

        mgr = get_workflow_lifecycle_manager()
        mgr.workflow_coordinator = WorkflowCoordinator(
            CapabilityRouter({"demo": _CompletingCapability()}),
            ArtifactCoordinator(),
        )
        done = mgr.run(mgr.create_instance(_profile(), _delegation(), _steps()))
        self.assertEqual(
            done.lifecycle_state.status, WorkflowLifecycleStatus.COMPLETED
        )


# =====================================================================
# Regression: Foundation / Planning / Workflow unchanged; no capability import
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

    def test_foundation_ai_employee_still_works(self):
        from app.core.dependencies import get_ai_employee

        employee = get_ai_employee()
        self.assertEqual(
            set(vars(employee)), {"planning_engine", "workflow_coordinator"}
        )

    def test_planning_engine_still_reasons(self):
        plan = _real_planning().create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_existing_workflow_coordinator_provider_unchanged(self):
        from app.core.dependencies import get_workflow_coordinator

        self.assertIsInstance(get_workflow_coordinator(), WorkflowCoordinator)

    def test_platform_imports_no_capability_module(self):
        # Architectural guard: no Sprint 16.2 platform module may import any of the
        # six capability modules — the platform reaches capabilities only through
        # the Workflow Coordinator.
        import app.services.ai_employee as pkg

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
