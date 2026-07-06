"""Execution state manager (Sprint 13.9 — deterministic lifecycle aggregation).

Reasoning-only component that aggregates a list of :class:`TaskLifecycle` records
into a single immutable, provider-independent :class:`ExecutionState`. It
represents execution state only: it counts every lifecycle state, computes an
overall state and a progress percentage, identifies the active task ids, and
detects terminal execution — but it never executes, resolves, or acquires
anything, and it never mutates the lifecycles.

Fully deterministic and offline: no AI, network, SDK, Runtime, Session, Registry,
Permission, Tool framework, Memory, or Gemini. Same lifecycles in -> same state
out.
"""

import hashlib
from typing import List

from app.services.planning.execution_state_models import (
    ExecutionState,
    ExecutionStateType,
)
from app.services.planning.task_lifecycle_models import (
    TERMINAL_TASK_STATES,
    TaskLifecycle,
    TaskLifecycleState,
)


class ExecutionStateManager:
    """Stateless aggregator: ``List[TaskLifecycle]`` -> :class:`ExecutionState`.

    Holds no state and owns no session, provider, or cache. It counts lifecycles
    by state, derives the overall state by a fixed precedence, computes progress
    from completed tasks only, and marks execution terminal only when every task
    is terminal. It never executes a step and never mutates the lifecycles.
    """

    def create_state(
        self, lifecycles: List[TaskLifecycle]
    ) -> ExecutionState:
        """Return a deterministic :class:`ExecutionState` for ``lifecycles``.

        Counts each lifecycle state, computes the overall state, progress,
        active task ids, and the terminal flag. The lifecycles are only read —
        never mutated — and nothing is executed.
        """
        total = len(lifecycles)
        ready = self._count(lifecycles, TaskLifecycleState.READY.value)
        waiting = self._count(lifecycles, TaskLifecycleState.WAITING.value)
        running = self._count(lifecycles, TaskLifecycleState.RUNNING.value)
        completed = self._count(lifecycles, TaskLifecycleState.COMPLETED.value)
        failed = self._count(lifecycles, TaskLifecycleState.FAILED.value)
        cancelled = self._count(lifecycles, TaskLifecycleState.CANCELLED.value)
        skipped = self._count(lifecycles, TaskLifecycleState.SKIPPED.value)

        active_task_ids = [
            lifecycle.unit_id
            for lifecycle in lifecycles
            if lifecycle.current_state not in TERMINAL_TASK_STATES
        ]
        terminal_count = completed + failed + cancelled + skipped
        terminal = total > 0 and terminal_count == total
        progress = round((completed / total) * 100, 2) if total else 0.0

        return ExecutionState(
            execution_id=self._execution_id(lifecycles),
            overall_state=self._overall_state(
                total, running, completed, failed, cancelled, waiting,
                terminal_count,
            ),
            total_tasks=total,
            ready_tasks=ready,
            waiting_tasks=waiting,
            running_tasks=running,
            completed_tasks=completed,
            failed_tasks=failed,
            cancelled_tasks=cancelled,
            skipped_tasks=skipped,
            progress_percentage=progress,
            active_task_ids=active_task_ids,
            terminal=terminal,
            metadata={
                "terminal_tasks": terminal_count,
                "active_tasks": len(active_task_ids),
            },
        )

    @staticmethod
    def _count(lifecycles: List[TaskLifecycle], state: str) -> int:
        """Count lifecycles whose current state is ``state``."""
        return sum(1 for l in lifecycles if l.current_state == state)

    @staticmethod
    def _overall_state(
        total: int,
        running: int,
        completed: int,
        failed: int,
        cancelled: int,
        waiting: int,
        terminal_count: int,
    ) -> str:
        """Derive the overall state by a fixed, deterministic precedence.

        An empty set is ``READY``; any failure dominates and yields ``FAILED``;
        an all-terminal set is ``CANCELLED`` when wholly cancelled else
        ``COMPLETED``; otherwise any completed work makes it
        ``PARTIALLY_COMPLETED``, then ``RUNNING`` dominates, then ``CANCELLED``
        dominates the remaining ready/waiting, then ``WAITING``, else ``READY``.
        """
        if total == 0:
            return ExecutionStateType.READY.value
        if failed > 0:
            return ExecutionStateType.FAILED.value
        if terminal_count == total:
            if cancelled == total:
                return ExecutionStateType.CANCELLED.value
            return ExecutionStateType.COMPLETED.value
        if completed > 0:
            return ExecutionStateType.PARTIALLY_COMPLETED.value
        if running > 0:
            return ExecutionStateType.RUNNING.value
        if cancelled > 0:
            return ExecutionStateType.CANCELLED.value
        if waiting > 0:
            return ExecutionStateType.WAITING.value
        return ExecutionStateType.READY.value

    @staticmethod
    def _execution_id(lifecycles: List[TaskLifecycle]) -> str:
        """Derive a stable, deterministic id from the lifecycle unit ids."""
        raw = "|".join(lifecycle.unit_id for lifecycle in lifecycles)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"exec-{digest}"
