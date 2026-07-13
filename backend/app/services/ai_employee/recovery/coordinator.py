"""Recovery coordinator (Sprint 16.8 — delegate recovery execution to the lifecycle).

Defines :class:`RecoveryCoordinator`, which coordinates the *execution* of a
recovery by delegating to the frozen Sprint 16.2 :class:`WorkflowLifecycleManager`.
Execution always flows

    RecoveryCoordinator -> WorkflowLifecycleManager -> WorkflowCoordinator

so this component never calls the :class:`WorkflowCoordinator` directly and never
touches a capability — it hands the workflow instance to the lifecycle manager's
transitions and reports the outcome.

It holds no recovery state, performs no wall-clock timing, and starts no background
worker. Constructor injection only; deterministic. Strictly additive to Sprints
1.x–16.7, whose modules are left untouched.
"""

from app.services.ai_employee.platform_models import (
    WorkflowInstance,
    WorkflowLifecycleState,
    WorkflowLifecycleStatus,
)
from app.services.ai_employee.workflow_lifecycle_manager import (
    WorkflowLifecycleManager,
)


class RecoveryCoordinator:
    """Executes recovery actions through the lifecycle manager (never directly).

    Constructed with an injected :class:`WorkflowLifecycleManager` (constructor
    injection; it instantiates none). ``execute_retry`` re-runs a failed workflow
    through the lifecycle manager's ``run`` (the only path to the Workflow
    Coordinator and the capabilities); ``resume_workflow`` resumes a paused workflow;
    and ``abort_workflow`` cancels a workflow to a terminal state. It holds no mutable
    state, never calls the Workflow Coordinator or a capability itself, and performs
    no wall-clock timing.
    """

    def __init__(self, lifecycle_manager: WorkflowLifecycleManager) -> None:
        self.lifecycle_manager = lifecycle_manager

    def execute_retry(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Re-run a failed ``instance`` by delegating to the lifecycle manager.

        Resets a spent instance to ``PENDING`` so the retry can run, then hands it to
        the lifecycle manager's ``run`` — which starts it and drives the Workflow
        Coordinator. Returns the executed instance; it calls no coordinator or
        capability itself.
        """
        return self.lifecycle_manager.run(self._to_pending(instance))

    def resume_workflow(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Resume a paused ``instance`` via the lifecycle manager (``PAUSED -> RUNNING``)."""
        return self.lifecycle_manager.resume(instance)

    def abort_workflow(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Abort ``instance`` to a terminal ``CANCELLED`` via the lifecycle manager.

        Resets a spent instance to ``PENDING`` (from which the lifecycle manager
        permits cancellation), then cancels it. Returns the cancelled instance; it
        calls no coordinator or capability itself.
        """
        return self.lifecycle_manager.cancel(self._to_pending(instance))

    @staticmethod
    def _to_pending(instance: WorkflowInstance) -> WorkflowInstance:
        """Return a fresh ``PENDING`` copy of ``instance`` when it is not already so."""
        if instance.lifecycle_state.status == WorkflowLifecycleStatus.PENDING:
            return instance
        return instance.model_copy(
            update={"lifecycle_state": WorkflowLifecycleState()}
        )
