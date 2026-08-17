"""Capability executor (Sprint 14.5 — deterministic capability invocation).

Consumes a :class:`CapabilityDispatchPlan` and delegates execution to a single
injected :class:`ExecutionCapability` implementation, invoking its ``execute`` for
every resolved assignment (in order) and aggregating the returned
:class:`CapabilityExecutionResult` objects into a
:class:`CapabilityExecutionSummary`. It executes ONLY through the
:class:`ExecutionCapability` interface: it knows nothing about Browser, Email,
Calendar, Python, GitHub, Files, or any concrete capability; it performs no
routing, no capability resolution, no recovery, and no approvals; and it never
mutates the dispatch plan. Provider errors propagate unchanged — the executor
does not catch them.

Deterministic and offline within the executor itself: no AI, network, clock,
UUID, SDK, capability resolution, registry, or Runtime global. Same dispatch plan
plus the same capability implementation -> identical summary.
"""

from typing import List

from app.services.runtime.capability_dispatcher_models import (
    CapabilityDispatchPlan,
)
from app.services.runtime.capability_executor_models import (
    CapabilityExecutionSummary,
    ExecutionSummaryStatus,
)
from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
    CapabilityExecutionStatus,
)


class CapabilityExecutor:
    """Executor: (:class:`CapabilityDispatchPlan`) -> execution summary.

    Stateless beyond the injected :class:`ExecutionCapability` reference — it owns
    no session, cache, clock, registry, or mutable state. It invokes the injected
    capability's ``execute`` once per resolved assignment (assignment order
    preserved), aggregates the results by outcome, and derives an overall status.
    It never resolves or instantiates a capability, performs no routing, and never
    mutates the dispatch plan; provider exceptions propagate unchanged.
    """

    def __init__(self, capability: ExecutionCapability) -> None:
        self.capability = capability

    def execute(
        self, dispatch_plan: CapabilityDispatchPlan
    ) -> CapabilityExecutionSummary:
        """Return a deterministic :class:`CapabilityExecutionSummary` (delegated).

        Invokes the injected capability's ``execute`` for each assignment in
        order, aggregates the returned results by outcome (completed/failed/
        cancelled), and derives the overall status — completed when everything
        completed (or nothing was invoked), failed/cancelled when everything
        shared that outcome, and partial for a mix. The dispatch plan is only
        read — never mutated. A capability exception propagates unchanged.
        """
        results: List[CapabilityExecutionResult] = []
        completed: List[str] = []
        failed: List[str] = []
        cancelled: List[str] = []

        for assignment in dispatch_plan.capability_assignments:
            request = CapabilityExecutionRequest(
                runtime_id=dispatch_plan.runtime_id,
                execution_id=dispatch_plan.execution_id,
                execution_unit_id=assignment.execution_unit_id,
                capability_name=assignment.capability_name,
                capability_inputs={},
                capability_metadata={},
            )
            result = self.capability.execute(request)
            results.append(result)
            self._bucket(result, completed, failed, cancelled)

        status = self._status(results, completed, failed, cancelled)

        return CapabilityExecutionSummary(
            runtime_id=dispatch_plan.runtime_id,
            execution_id=dispatch_plan.execution_id,
            execution_status=status.value,
            completed_execution_units=completed,
            failed_execution_units=failed,
            cancelled_execution_units=cancelled,
            execution_results=results,
            execution_metadata={
                "total": len(results),
                "completed_count": len(completed),
                "failed_count": len(failed),
                "cancelled_count": len(cancelled),
                "source_dispatch_status": dispatch_plan.dispatch_status,
            },
        )

    @staticmethod
    def _bucket(
        result: CapabilityExecutionResult,
        completed: List[str],
        failed: List[str],
        cancelled: List[str],
    ) -> None:
        """Record a result's unit id in the bucket matching its status."""
        status = result.execution_status
        if status == CapabilityExecutionStatus.COMPLETED.value:
            completed.append(result.execution_unit_id)
        elif status == CapabilityExecutionStatus.FAILED.value:
            failed.append(result.execution_unit_id)
        elif status == CapabilityExecutionStatus.CANCELLED.value:
            cancelled.append(result.execution_unit_id)

    @staticmethod
    def _status(
        results: List[CapabilityExecutionResult],
        completed: List[str],
        failed: List[str],
        cancelled: List[str],
    ) -> ExecutionSummaryStatus:
        """Derive the aggregate status by fixed, deterministic precedence.

        An empty pass (nothing invoked) is completed; otherwise a uniform outcome
        yields that outcome (all completed -> completed, all failed -> failed, all
        cancelled -> cancelled) and any mix yields partial.
        """
        total = len(results)
        if total == 0:
            return ExecutionSummaryStatus.COMPLETED
        if len(completed) == total:
            return ExecutionSummaryStatus.COMPLETED
        if len(failed) == total:
            return ExecutionSummaryStatus.FAILED
        if len(cancelled) == total:
            return ExecutionSummaryStatus.CANCELLED
        return ExecutionSummaryStatus.PARTIAL
