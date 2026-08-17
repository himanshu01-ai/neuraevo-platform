"""Execution progress runtime (Sprint 14.6 — deterministic progress aggregation).

Reasoning-only component that consumes a :class:`CapabilityExecutionSummary` and
produces a single immutable, provider-independent :class:`ExecutionProgress`. It
tracks runtime execution progress only: it counts the per-outcome units, derives
an overall progress status, and computes a deterministic integer completion
percentage — but it never executes a capability, dispatches work, performs
routing, recovers, approves, or mutates the summary.

Fully deterministic and offline: no AI, network, clock, UUID, SDK, capability
knowledge, Runtime global, or persistence. Same summary in -> same progress out.
"""

from app.services.runtime.capability_executor_models import (
    CapabilityExecutionSummary,
)
from app.services.runtime.execution_progress_models import (
    ExecutionProgress,
    ProgressStatus,
)


class ExecutionProgressRuntime:
    """Stateless tracker: :class:`CapabilityExecutionSummary` -> progress.

    Holds no state and owns no session, provider, cache, clock, or global. It
    counts the summary's completed/failed/cancelled units against the total units
    executed, derives the overall status by a fixed precedence, and computes a
    deterministic integer completion percentage. It never executes, dispatches,
    routes, recovers, or approves, and it never mutates the summary.
    """

    def create_progress(
        self, summary: CapabilityExecutionSummary
    ) -> ExecutionProgress:
        """Return a deterministic :class:`ExecutionProgress` for ``summary``.

        The total is the number of executed results; the completed/failed/
        cancelled counts come from the summary's outcome lists; the status is
        derived by a fixed precedence; and the completion percentage is the
        integer-rounded ``completed / total * 100``. The summary is only read —
        never mutated — and nothing is executed.
        """
        total = len(summary.execution_results)
        completed = len(summary.completed_execution_units)
        failed = len(summary.failed_execution_units)
        cancelled = len(summary.cancelled_execution_units)

        status = self._status(total, completed, failed, cancelled)
        percentage = self._percentage(completed, total)

        return ExecutionProgress(
            runtime_id=summary.runtime_id,
            execution_id=summary.execution_id,
            progress_status=status.value,
            total_execution_units=total,
            completed_execution_units=completed,
            failed_execution_units=failed,
            cancelled_execution_units=cancelled,
            completion_percentage=percentage,
            progress_metadata={
                "total": total,
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
                "in_progress": total - completed - failed - cancelled,
                "source_status": summary.execution_status,
            },
        )

    @staticmethod
    def _status(
        total: int, completed: int, failed: int, cancelled: int
    ) -> ProgressStatus:
        """Derive the progress status by fixed, deterministic precedence.

        An empty pass is not started; a uniform terminal outcome yields that
        outcome (all completed/failed/cancelled); an all-terminal mix is partial;
        and any remaining non-terminal units make it in progress.
        """
        if total == 0:
            return ProgressStatus.NOT_STARTED
        if completed == total:
            return ProgressStatus.COMPLETED
        if failed == total:
            return ProgressStatus.FAILED
        if cancelled == total:
            return ProgressStatus.CANCELLED
        if completed + failed + cancelled == total:
            return ProgressStatus.PARTIAL
        return ProgressStatus.IN_PROGRESS

    @staticmethod
    def _percentage(completed: int, total: int) -> int:
        """Return the deterministic integer ``completed / total * 100``.

        Uses pure-integer round-half-up (``(completed * 100 + total // 2) //
        total``) so the percentage is deterministic and float-free; an empty pass
        is 0.
        """
        if total == 0:
            return 0
        return (completed * 100 + total // 2) // total
