"""Progress tracker (Sprint 16.2 — deterministic job progress; no execution).

Defines :class:`ProgressTracker`, the deterministic component that derives an
immutable :class:`WorkflowProgress` for a delegated job — either an initial
snapshot for a not-yet-started job or a snapshot derived from the Sprint 15.15
:class:`WorkflowExecutionResult` the Workflow Coordinator produced.

It executes nothing, dispatches to no capability, and holds no state — the same
inputs always yield the same progress. Strictly additive to Sprints 1.x–16.1.
"""

from app.services.ai_employee.platform_models import (
    WorkflowProgress,
    WorkflowProgressStatus,
)
from app.services.runtime.workflow_models import WorkflowExecutionResult


class ProgressTracker:
    """Derives deterministic :class:`WorkflowProgress` snapshots (no execution).

    Stateless: ``initialize`` builds the pre-start snapshot from a step count, and
    ``track`` reads a :class:`WorkflowExecutionResult`'s deterministic tallies
    (completed count, total count, failed step id) into a snapshot. It tracks the
    current step, completed steps, failed step, an integer percentage, and a
    status — nothing more — and never executes, dispatches, or mutates its input.
    """

    def initialize(self, total_steps: int) -> WorkflowProgress:
        """Return the pre-start progress snapshot for a job with ``total_steps``.

        Nothing has run yet: the current step and completed count are 0, there is
        no failed step, the percentage is 0, and the status is ``PENDING``.
        """
        return WorkflowProgress(
            current_step=0,
            total_steps=max(total_steps, 0),
            completed_steps=0,
            failed_step=None,
            percentage=0,
            status=WorkflowProgressStatus.PENDING,
        )

    def track(self, result: WorkflowExecutionResult) -> WorkflowProgress:
        """Return the progress derived from a workflow ``result`` (deterministic).

        Reads the result's deterministic tallies — ``completed_step_count``,
        ``total_step_count``, ``failed_step_id`` — and computes the current step,
        an integer percentage (floored, never a float), and the status: ``FAILED``
        when a step failed, ``COMPLETED`` when every step finished, ``PENDING``
        when none did, else ``IN_PROGRESS``. It never executes or mutates the
        result.
        """
        total = max(result.total_step_count, 0)
        completed = max(result.completed_step_count, 0)
        failed_step = result.failed_step_id
        percentage = 0 if total == 0 else (completed * 100) // total

        if failed_step is not None:
            status = WorkflowProgressStatus.FAILED
            current_step = min(completed + 1, total) if total else 0
        elif total > 0 and completed >= total:
            status = WorkflowProgressStatus.COMPLETED
            current_step = total
            percentage = 100
        elif completed == 0:
            status = WorkflowProgressStatus.PENDING
            current_step = 0
        else:
            status = WorkflowProgressStatus.IN_PROGRESS
            current_step = min(completed + 1, total)

        return WorkflowProgress(
            current_step=current_step,
            total_steps=total,
            completed_steps=completed,
            failed_step=failed_step,
            percentage=percentage,
            status=status,
        )
