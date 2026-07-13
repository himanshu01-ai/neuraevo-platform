"""Workflow lifecycle manager (Sprint 16.2 — coordinate a delegated job's life).

Defines :class:`WorkflowLifecycleManager`, the coordinator that owns the lifecycle
of one delegated job. It follows the locked flow:

    WorkflowInstance -> WorkflowLifecycleManager
        -> [ProgressTracker, ApprovalManager, NotificationManager,
            RecoveryManager, PersistenceManager]
        -> WorkflowCoordinator -> ExecutionCapabilities

It creates an immutable :class:`WorkflowInstance` (attaching a reasoned Sprint 13
:class:`ExecutionPlan` from the Planning Engine), coordinates the seven lifecycle
transitions (start, pause, resume, cancel, retry, complete, fail) as deterministic
moves over the immutable instance, and — when a job is run — drives the Sprint
15.15 :class:`WorkflowCoordinator` to execute the given steps, folding the result
into progress and a terminal state.

It contains no business logic of its own: it validates each transition against a
deterministic table, delegates progress to the tracker, approval to the approval
policy, notifications to the notification store, retries to the recovery policy,
and persistence to the persistence store, and it reaches capabilities *only*
through the Workflow Coordinator — never importing a capability module. Constructor
injection only; stateless beyond its injected collaborators (no static, singleton,
or service-locator state); deterministic. Strictly additive to Sprints 1.x–16.1.
"""

from typing import Any, Dict, FrozenSet, List, Optional

from app.services.ai_employee.approval_manager import ApprovalManager
from app.services.ai_employee.models import EmployeeProfile, TaskDelegation
from app.services.ai_employee.notification_manager import NotificationManager
from app.services.ai_employee.persistence_manager import PersistenceManager
from app.services.ai_employee.platform_models import (
    WorkflowInstance,
    WorkflowLifecycleError,
    WorkflowLifecycleState,
    WorkflowLifecycleStatus,
)
from app.services.ai_employee.progress_tracker import ProgressTracker
from app.services.ai_employee.recovery_manager import RecoveryManager
from app.services.planning.models import PlanningRequest
from app.services.planning.planning_engine import PlanningEngine
from app.services.runtime.workflow_coordinator import WorkflowCoordinator
from app.services.runtime.workflow_models import (
    WorkflowExecutionResult,
    WorkflowStatus,
    WorkflowStep,
)

# Deterministic table of the lifecycle moves the manager permits. A transition
# outside this table raises :class:`WorkflowLifecycleError`; the terminal statuses
# (``COMPLETED``/``CANCELLED``) have no outgoing moves. ``FAILED`` is retryable
# (``-> RUNNING``) via the Recovery Manager, so it is not terminal.
_ALLOWED_TRANSITIONS: Dict[WorkflowLifecycleStatus, FrozenSet[WorkflowLifecycleStatus]] = {
    WorkflowLifecycleStatus.PENDING: frozenset(
        {WorkflowLifecycleStatus.RUNNING, WorkflowLifecycleStatus.CANCELLED}
    ),
    WorkflowLifecycleStatus.RUNNING: frozenset(
        {
            WorkflowLifecycleStatus.PAUSED,
            WorkflowLifecycleStatus.CANCELLED,
            WorkflowLifecycleStatus.COMPLETED,
            WorkflowLifecycleStatus.FAILED,
        }
    ),
    WorkflowLifecycleStatus.PAUSED: frozenset(
        {WorkflowLifecycleStatus.RUNNING, WorkflowLifecycleStatus.CANCELLED}
    ),
    WorkflowLifecycleStatus.FAILED: frozenset(
        {WorkflowLifecycleStatus.RUNNING}
    ),
    WorkflowLifecycleStatus.COMPLETED: frozenset(),
    WorkflowLifecycleStatus.CANCELLED: frozenset(),
}

_TERMINAL_STATUSES: FrozenSet[WorkflowLifecycleStatus] = frozenset(
    {WorkflowLifecycleStatus.COMPLETED, WorkflowLifecycleStatus.CANCELLED}
)


class WorkflowLifecycleManager:
    """Coordinates one delegated job's lifecycle over immutable instances.

    Constructed with an injected :class:`PlanningEngine`, :class:`WorkflowCoordinator`,
    and the five managers (:class:`ProgressTracker`, :class:`ApprovalManager`,
    :class:`NotificationManager`, :class:`RecoveryManager`,
    :class:`PersistenceManager`) — constructor injection; it instantiates none of
    them. It creates instances, coordinates the seven lifecycle transitions, and
    runs a job through the Workflow Coordinator, delegating each concern to the
    matching collaborator. It holds no mutable state itself (the notification and
    persistence stores live inside their managers), performs no planning or
    execution of its own, and reaches capabilities only through the coordinator.
    """

    def __init__(
        self,
        planning_engine: PlanningEngine,
        workflow_coordinator: WorkflowCoordinator,
        progress_tracker: ProgressTracker,
        approval_manager: ApprovalManager,
        notification_manager: NotificationManager,
        recovery_manager: RecoveryManager,
        persistence_manager: PersistenceManager,
    ) -> None:
        self.planning_engine = planning_engine
        self.workflow_coordinator = workflow_coordinator
        self.progress_tracker = progress_tracker
        self.approval_manager = approval_manager
        self.notification_manager = notification_manager
        self.recovery_manager = recovery_manager
        self.persistence_manager = persistence_manager

    # --- instance creation ----------------------------------------------
    def create_instance(
        self,
        profile: EmployeeProfile,
        delegation: TaskDelegation,
        workflow_steps: List[WorkflowStep],
    ) -> WorkflowInstance:
        """Create a ``PENDING`` :class:`WorkflowInstance` for a delegated job.

        Coordinates the Planning Engine to *reason* about ``delegation.task``
        (attaching an :class:`ExecutionPlan`), initialises progress via the tracker,
        binds plain manager-reference descriptors, and persists the instance via the
        persistence manager. The instance owns state only — nothing is executed and
        no capability is touched. Ids are derived deterministically, so the same
        profile and delegation always yield the same instance.
        """
        plan = self.planning_engine.create_plan(
            PlanningRequest(user_request=delegation.task)
        )
        total_steps = len(workflow_steps)
        instance = WorkflowInstance(
            instance_id=self._instance_id(profile, delegation),
            employee_id=profile.employee_id,
            task_id=delegation.task_id,
            workflow_id=self._workflow_id(delegation),
            lifecycle_state=WorkflowLifecycleState(
                status=WorkflowLifecycleStatus.PENDING
            ),
            progress=self.progress_tracker.initialize(total_steps),
            plan=plan,
            workflow_steps=list(workflow_steps),
            total_steps=total_steps,
            workflow_result=None,
            manager_references=self._manager_references(),
            instance_metadata={"priority": delegation.priority.value},
        )
        self.persistence_manager.save_instance(instance)
        return instance

    # --- lifecycle transitions ------------------------------------------
    def start(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Coordinate ``PENDING -> RUNNING``; record ``workflow_started``; persist."""
        started = self._transition(instance, WorkflowLifecycleStatus.RUNNING)
        self.notification_manager.workflow_started(started)
        return self._persist(started)

    def pause(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Coordinate ``RUNNING -> PAUSED``; persist."""
        return self._persist(
            self._transition(instance, WorkflowLifecycleStatus.PAUSED)
        )

    def resume(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Coordinate ``PAUSED -> RUNNING``; persist."""
        return self._persist(
            self._transition(instance, WorkflowLifecycleStatus.RUNNING)
        )

    def cancel(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Coordinate an active job to a terminal ``CANCELLED``; persist."""
        return self._persist(
            self._transition(
                instance, WorkflowLifecycleStatus.CANCELLED, terminal=True
            )
        )

    def complete(
        self, instance: WorkflowInstance, workflow_result: WorkflowExecutionResult
    ) -> WorkflowInstance:
        """Coordinate ``RUNNING -> COMPLETED``; fold in progress/result; persist.

        Derives the final progress from ``workflow_result`` via the tracker,
        transitions to the terminal ``COMPLETED`` state, attaches the result, and
        records ``workflow_completed``.
        """
        completed = self._transition(
            instance, WorkflowLifecycleStatus.COMPLETED, terminal=True
        )
        completed = completed.model_copy(
            update={
                "progress": self.progress_tracker.track(workflow_result),
                "workflow_result": workflow_result,
            }
        )
        self.notification_manager.workflow_completed(completed)
        return self._persist(completed)

    def fail(
        self,
        instance: WorkflowInstance,
        workflow_result: Optional[WorkflowExecutionResult] = None,
    ) -> WorkflowInstance:
        """Coordinate ``RUNNING -> FAILED``; fold in progress/result; persist.

        Transitions to the retryable ``FAILED`` state, folds in the derived
        progress and the result when one is supplied, and records
        ``workflow_failed``. ``FAILED`` is not terminal — the Recovery Manager may
        later retry it.
        """
        failed = self._transition(instance, WorkflowLifecycleStatus.FAILED)
        if workflow_result is not None:
            failed = failed.model_copy(
                update={
                    "progress": self.progress_tracker.track(workflow_result),
                    "workflow_result": workflow_result,
                }
            )
        self.notification_manager.workflow_failed(failed)
        return self._persist(failed)

    def retry(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Coordinate a retry of a ``FAILED`` job via the Recovery Manager; persist.

        Consults the recovery policy: if it cannot retry (wrong status or retries
        exhausted) a :class:`WorkflowLifecycleError` is raised; otherwise the policy
        produces a new ``RUNNING`` instance with the attempt counter advanced, which
        is then persisted.
        """
        if not self.recovery_manager.can_retry(instance):
            raise WorkflowLifecycleError(
                f"instance {instance.instance_id} is not retryable "
                f"(status={instance.lifecycle_state.status.value}, "
                f"attempt={instance.lifecycle_state.attempt})"
            )
        return self._persist(self.recovery_manager.retry(instance))

    # --- run (drives the Workflow Coordinator) --------------------------
    def run(
        self,
        instance: WorkflowInstance,
        initial_inputs: Optional[Dict[str, Any]] = None,
    ) -> WorkflowInstance:
        """Run a ``PENDING`` job end-to-end and return its terminal instance.

        Consults the approval policy first: if the job ``requires_approval`` it
        records an ``approval_required`` notification and returns the instance
        un-started (a later approved re-run proceeds). Otherwise it starts the job,
        drives the Workflow Coordinator over the instance's steps (the only path to
        the capabilities), and transitions to ``COMPLETED`` or ``FAILED`` from the
        coordinator's deterministic result. The manager plans nothing here and
        executes no capability itself.
        """
        if self.approval_manager.requires_approval(instance):
            self.notification_manager.approval_required(instance)
            return instance.model_copy(
                update={
                    "instance_metadata": {
                        **instance.instance_metadata,
                        "approval_required": True,
                    }
                }
            )

        started = self.start(instance)
        result = self.workflow_coordinator.execute(
            started.workflow_steps,
            workflow_id=started.workflow_id,
            runtime_id=started.instance_id,
            execution_id=started.instance_id,
            initial_inputs=initial_inputs,
        )
        if result.workflow_status == WorkflowStatus.COMPLETED.value:
            return self.complete(started, result)
        return self.fail(started, result)

    # --- helpers ---------------------------------------------------------
    def _transition(
        self,
        instance: WorkflowInstance,
        new_status: WorkflowLifecycleStatus,
        *,
        terminal: bool = False,
    ) -> WorkflowInstance:
        """Validate and apply a lifecycle transition, returning a new instance.

        Raises :class:`WorkflowLifecycleError` when ``new_status`` is not an allowed
        move from the current status; otherwise builds the next immutable
        :class:`WorkflowLifecycleState` and returns a copy of the instance carrying
        it. No progress, result, or notification is changed here.
        """
        current = instance.lifecycle_state.status
        if new_status not in _ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise WorkflowLifecycleError(
                f"cannot transition {current.value} -> {new_status.value} "
                f"for instance {instance.instance_id}"
            )
        new_state = instance.lifecycle_state.transition_to(
            new_status, terminal=terminal
        )
        return instance.model_copy(update={"lifecycle_state": new_state})

    def _persist(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Persist ``instance`` via the persistence manager and return it."""
        self.persistence_manager.save_instance(instance)
        return instance

    def _manager_references(self) -> Dict[str, str]:
        """Return plain class-name descriptors of the wired collaborators.

        Exposes names only — never the live objects — so no SDK/manager object
        crosses the :class:`WorkflowInstance` boundary.
        """
        return {
            "planning_engine": type(self.planning_engine).__name__,
            "workflow_coordinator": type(self.workflow_coordinator).__name__,
            "progress_tracker": type(self.progress_tracker).__name__,
            "approval_manager": type(self.approval_manager).__name__,
            "notification_manager": type(self.notification_manager).__name__,
            "recovery_manager": type(self.recovery_manager).__name__,
            "persistence_manager": type(self.persistence_manager).__name__,
        }

    @staticmethod
    def _instance_id(
        profile: EmployeeProfile, delegation: TaskDelegation
    ) -> str:
        """Derive the deterministic instance id from the profile and delegation."""
        return f"instance-{profile.employee_id}-{delegation.task_id}"

    @staticmethod
    def _workflow_id(delegation: TaskDelegation) -> str:
        """Derive the deterministic workflow id from the delegation."""
        return f"workflow-{delegation.task_id}"
