"""Execution scheduler (Sprint 16.7 — delegate scheduled execution to the lifecycle).

Defines :class:`ExecutionScheduler`, which coordinates the execution of *due*
scheduled workflows by delegating to the frozen Sprint 16.2
:class:`WorkflowLifecycleManager`. Execution always flows

    ExecutionScheduler -> WorkflowLifecycleManager -> WorkflowCoordinator

so this component never calls the :class:`WorkflowCoordinator` directly and never
touches a capability — it hands the workflow instance to the lifecycle manager's
``run`` and reports the outcome.

It holds no schedule state (the manager owns the queue), performs no wall-clock
timing, and starts no background worker. Constructor injection only; deterministic.
Strictly additive to Sprints 1.x–16.6, whose modules are left untouched.
"""

from typing import List

from app.services.ai_employee.platform_models import (
    WorkflowInstance,
    WorkflowLifecycleState,
    WorkflowLifecycleStatus,
)
from app.services.ai_employee.scheduler.models import (
    ScheduleEntry,
    ScheduleResult,
    ScheduleStatus,
)
from app.services.ai_employee.workflow_lifecycle_manager import (
    WorkflowLifecycleManager,
)


class ExecutionScheduler:
    """Executes due scheduled workflows through the lifecycle manager (never directly).

    Constructed with an injected :class:`WorkflowLifecycleManager` (constructor
    injection; it instantiates none). ``execute_entry``/``execute_due`` delegate a
    schedule entry's workflow to the lifecycle manager's ``run`` — the only path to
    the Workflow Coordinator and the capabilities. ``pause_execution`` and
    ``resume_execution`` transition a schedule entry's status between ``PAUSED`` and
    ``SCHEDULED``. It holds no mutable state, never calls the Workflow Coordinator or
    a capability itself, and performs no wall-clock timing.
    """

    def __init__(self, lifecycle_manager: WorkflowLifecycleManager) -> None:
        self.lifecycle_manager = lifecycle_manager

    def execute_entry(self, entry: ScheduleEntry) -> ScheduleResult:
        """Execute one due ``entry`` by delegating its workflow to the lifecycle manager.

        Ensures the workflow instance is ``PENDING`` (resetting a spent instance so a
        recurring occurrence can run again), then hands it to the lifecycle manager's
        ``run`` — which starts it and drives the Workflow Coordinator. Reports the
        deterministic terminal outcome; it calls no coordinator or capability itself.
        """
        instance = entry.instance
        if instance.lifecycle_state.status != WorkflowLifecycleStatus.PENDING:
            instance = self._reset(instance)
        executed = self.lifecycle_manager.run(instance)
        final = executed.lifecycle_state.status
        return ScheduleResult(
            entry_id=entry.entry_id,
            workflow_id=entry.workflow_id,
            operation="execute",
            success=final == WorkflowLifecycleStatus.COMPLETED,
            entry=entry.model_copy(update={"status": ScheduleStatus.COMPLETED}),
            result_metadata={"final_status": final.value},
        )

    def execute_due(
        self, entries: List[ScheduleEntry]
    ) -> List[ScheduleResult]:
        """Execute each due entry in order and return the results."""
        return [self.execute_entry(entry) for entry in entries]

    def pause_execution(self, entry: ScheduleEntry) -> ScheduleEntry:
        """Return ``entry`` transitioned to ``PAUSED`` (held from execution)."""
        return entry.model_copy(update={"status": ScheduleStatus.PAUSED})

    def resume_execution(self, entry: ScheduleEntry) -> ScheduleEntry:
        """Return ``entry`` transitioned back to ``SCHEDULED`` (eligible again)."""
        return entry.model_copy(update={"status": ScheduleStatus.SCHEDULED})

    @staticmethod
    def _reset(instance: WorkflowInstance) -> WorkflowInstance:
        """Return a fresh ``PENDING`` copy of ``instance`` for a repeated run."""
        return instance.model_copy(
            update={"lifecycle_state": WorkflowLifecycleState()}
        )
