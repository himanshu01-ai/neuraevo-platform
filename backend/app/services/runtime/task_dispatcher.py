"""Task dispatcher (Sprint 14.2 — deterministic dispatch-plan construction).

Reasoning-only component that consumes an :class:`ExecutionRuntimeContext` and
determines which execution unit(s) are eligible to leave the runtime, producing a
single immutable, provider-independent :class:`DispatchPlan`. It reads the
:class:`ExecutionQueue` from the orchestration, groups the units into ready,
blocked, and deferred sets in the queue's exact order, and derives a dispatch
status — but it never executes, dispatches a capability, resolves, or acquires
anything, and it never mutates the runtime context or the queue.

Fully deterministic and offline: no AI, network, clock, UUID, SDK, capability
knowledge, recovery, approval, Runtime global, or persistence. Same runtime
context in -> same dispatch plan out.
"""

from typing import List

from app.services.planning.execution_queue_models import ExecutionUnitStatus
from app.services.runtime.execution_runtime_models import ExecutionRuntimeContext
from app.services.runtime.task_dispatcher_models import (
    DispatchPlan,
    DispatchStatus,
)


class TaskDispatcher:
    """Stateless dispatcher: :class:`ExecutionRuntimeContext` -> dispatch plan.

    Holds no state and owns no session, provider, cache, clock, or global. It
    reads the orchestration's execution queue, partitions the units by status
    into ready/blocked/deferred (queue order preserved), and derives the dispatch
    status — ready when any unit can start, else blocked, else waiting, else
    completed for an empty queue. It never executes, dispatches a capability,
    recovers, or approves, and it never mutates the runtime context or queue.
    """

    def create_dispatch_plan(
        self, context: ExecutionRuntimeContext
    ) -> DispatchPlan:
        """Return a deterministic :class:`DispatchPlan` (no execution).

        The queue's units are grouped by status — ``READY`` to ready, ``BLOCKED``
        to blocked, ``WAITING`` to deferred — preserving the queue's exact
        ordering; the dispatch status follows a fixed precedence (ready, then
        blocked, then deferred, then completed for an empty queue). The runtime
        context and queue are only read — never mutated — and nothing is executed
        or dispatched.
        """
        units = context.orchestration.queue.execution_units
        ready = self._ids(units, ExecutionUnitStatus.READY.value)
        blocked = self._ids(units, ExecutionUnitStatus.BLOCKED.value)
        deferred = self._ids(units, ExecutionUnitStatus.WAITING.value)

        return DispatchPlan(
            runtime_id=context.runtime_id,
            execution_id=context.execution_id,
            dispatch_status=self._status(ready, blocked, deferred).value,
            ready_execution_units=ready,
            blocked_execution_units=blocked,
            deferred_execution_units=deferred,
            dispatch_metadata={
                "total_units": len(units),
                "ready_count": len(ready),
                "blocked_count": len(blocked),
                "deferred_count": len(deferred),
                "queue_status": context.orchestration.queue.status,
            },
        )

    @staticmethod
    def _ids(units, status: str) -> List[str]:
        """Return the unit ids with ``status``, preserving queue order."""
        return [unit.unit_id for unit in units if unit.status == status]

    @staticmethod
    def _status(
        ready: List[str], blocked: List[str], deferred: List[str]
    ) -> DispatchStatus:
        """Derive the dispatch status by fixed, deterministic precedence.

        Any ready unit makes the dispatch ``READY``; otherwise blocked units make
        it ``BLOCKED``, then deferred units make it ``WAITING``; an empty queue
        (no ready, blocked, or deferred units) is ``COMPLETED``.
        """
        if ready:
            return DispatchStatus.READY
        if blocked:
            return DispatchStatus.BLOCKED
        if deferred:
            return DispatchStatus.WAITING
        return DispatchStatus.COMPLETED
