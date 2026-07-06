"""Execution coordinator (Sprint 13.7 — deterministic queue construction).

Reasoning-only component that converts an :class:`ExecutionWorkflow` into an
immutable, provider-independent :class:`ExecutionQueue`. It organises execution
only: it turns workflow steps into execution units, preserving their order,
groups, and dependencies, assigns per-unit and queue statuses deterministically,
and computes ready/blocked counts — but it never executes, resolves, or acquires
anything.

Fully deterministic and offline: no AI, network, SDK, Runtime, Session, Registry,
Permission, Tool framework, Memory, or Gemini. Same workflow in -> same queue
out.
"""

from typing import List

from app.services.planning.execution_queue_models import (
    ExecutionQueue,
    ExecutionUnit,
    ExecutionUnitStatus,
    QueueStatus,
)
from app.services.planning.execution_workflow_models import (
    ExecutionWorkflow,
    WorkflowStatus,
)

# Workflow status -> queue status. A merely planned (cancelled) workflow cannot
# proceed, so it maps to a blocked queue.
_WORKFLOW_TO_QUEUE_STATUS = {
    WorkflowStatus.READY.value: QueueStatus.READY.value,
    WorkflowStatus.WAITING.value: QueueStatus.WAITING.value,
    WorkflowStatus.BLOCKED.value: QueueStatus.BLOCKED.value,
    WorkflowStatus.PLANNED.value: QueueStatus.BLOCKED.value,
}


class ExecutionCoordinator:
    """Stateless organiser: :class:`ExecutionWorkflow` -> :class:`ExecutionQueue`.

    Holds no state and owns no session, provider, or cache. It preserves the
    workflow's step order, groups, and dependencies while turning each step into
    an execution unit, derives per-unit and queue statuses from the workflow
    status, and counts ready/blocked units. It never executes a step.
    """

    def create_queue(self, workflow: ExecutionWorkflow) -> ExecutionQueue:
        """Return a deterministic :class:`ExecutionQueue` for ``workflow``.

        Each workflow step becomes an :class:`ExecutionUnit` (order, group, and
        dependencies preserved); unit and queue statuses are derived from the
        workflow status; and ready/blocked counts are computed from the units.
        The workflow is only read — never mutated — and nothing is executed.
        """
        queue_status = _WORKFLOW_TO_QUEUE_STATUS.get(
            workflow.workflow_status, QueueStatus.BLOCKED.value
        )
        units = self._units(workflow)
        ready_units = sum(
            1 for unit in units if unit.status == ExecutionUnitStatus.READY.value
        )
        blocked_units = sum(
            1
            for unit in units
            if unit.status == ExecutionUnitStatus.BLOCKED.value
        )

        return ExecutionQueue(
            queue_id=f"queue-{workflow.workflow_id}",
            workflow_id=workflow.workflow_id,
            status=queue_status,
            execution_units=units,
            total_units=len(units),
            ready_units=ready_units,
            blocked_units=blocked_units,
            metadata={
                "workflow_status": workflow.workflow_status,
                "execution_mode": workflow.execution_mode,
                "resumable": workflow.resumable,
            },
        )

    @classmethod
    def _units(cls, workflow: ExecutionWorkflow) -> List[ExecutionUnit]:
        """Turn workflow steps into ordered execution units (status derived)."""
        units: List[ExecutionUnit] = []
        for step in workflow.ordered_steps:
            units.append(
                ExecutionUnit(
                    unit_id=f"{workflow.workflow_id}-u{step.step_number}",
                    step_number=step.step_number,
                    description=step.description,
                    execution_group=step.group,
                    status=cls._unit_status(
                        workflow.workflow_status, step.depends_on
                    ),
                    dependencies=list(step.depends_on),
                    metadata={"workflow_id": workflow.workflow_id},
                )
            )
        return units

    @staticmethod
    def _unit_status(workflow_status: str, depends_on: List[int]) -> str:
        """Derive a unit's status from the workflow status and its dependencies.

        In a ready workflow a unit is ``READY`` when it has no dependencies and
        ``BLOCKED`` when it does (it must wait on predecessors). A waiting
        workflow makes every unit ``WAITING``; a blocked or merely planned
        workflow makes every unit ``BLOCKED``.
        """
        if workflow_status == WorkflowStatus.READY.value:
            return (
                ExecutionUnitStatus.READY.value
                if not depends_on
                else ExecutionUnitStatus.BLOCKED.value
            )
        if workflow_status == WorkflowStatus.WAITING.value:
            return ExecutionUnitStatus.WAITING.value
        return ExecutionUnitStatus.BLOCKED.value
