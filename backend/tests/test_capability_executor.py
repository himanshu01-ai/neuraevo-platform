"""Unit tests for the Sprint 14.5 Capability Executor.

Covers the capability-invocation layer end to end using only deterministic in-test
:class:`ExecutionCapability` doubles — no concrete Browser/Email/Calendar/Python/
GitHub capability, no network, SDK, clock, UUID, registry, or database:

* the immutable :class:`CapabilityExecutionSummary` DTO and the
  :class:`ExecutionSummaryStatus` enum (defaults, immutability, required fields);
* the :class:`CapabilityExecutor` (delegated invocation through the interface,
  order preservation, aggregation, success/partial/total-failure/cancellation
  outcomes, empty plan, provider-error propagation, determinism, statelessness,
  non-mutation);
* the composition-root wiring (``get_capability_executor`` injecting the seam +
  ``CapabilityExecutorDep``); and
* regression that the Sprint 14.3 seam and Sprint 14.4 dispatcher are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_capability_executor
"""

import unittest

from pydantic import ValidationError

from app.services.runtime.capability_dispatcher_models import (
    CapabilityAssignment,
    CapabilityDispatchPlan,
)
from app.services.runtime.capability_executor import CapabilityExecutor
from app.services.runtime.capability_executor_models import (
    CapabilityExecutionSummary,
    ExecutionSummaryStatus,
)
from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionResult,
)


# =====================================================================
# In-test ExecutionCapability doubles (NOT real capabilities)
# =====================================================================
def _result(request, status):
    return CapabilityExecutionResult(
        runtime_id=request.runtime_id,
        execution_id=request.execution_id,
        execution_unit_id=request.execution_unit_id,
        capability_name=request.capability_name,
        execution_status=status,
        capability_outputs={"echo": request.execution_unit_id},
        execution_metadata={},
    )


class _StatusCapability(ExecutionCapability):
    """Deterministic double: returns a fixed status, overridable per unit id."""

    def __init__(self, status="COMPLETED", per_unit=None):
        self._status = status
        self._per_unit = per_unit or {}

    def execute(self, request):
        status = self._per_unit.get(request.execution_unit_id, self._status)
        return _result(request, status)


class _RecordingCapability(ExecutionCapability):
    """Deterministic double that records the unit ids it was invoked for."""

    def __init__(self, status="COMPLETED"):
        self.calls = []
        self._status = status

    def execute(self, request):
        self.calls.append(request.execution_unit_id)
        return _result(request, self._status)


class _RaisingCapability(ExecutionCapability):
    """Double that raises — used to verify provider errors propagate unchanged."""

    def execute(self, request):
        raise RuntimeError("provider boom")


# =====================================================================
# Helpers
# =====================================================================
def _plan(units=("u1",), status="READY"):
    return CapabilityDispatchPlan(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        dispatch_status=status,
        capability_assignments=[
            CapabilityAssignment(
                execution_unit_id=u, capability_name=f"capability-{u}"
            )
            for u in units
        ],
        unresolved_execution_units=[],
        dispatch_metadata={},
    )


def _execute(dispatch_plan, capability):
    return CapabilityExecutor(capability).execute(dispatch_plan)


def _summary(**overrides):
    data = dict(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        execution_status="COMPLETED",
        completed_execution_units=["u1"],
        failed_execution_units=[],
        cancelled_execution_units=[],
        execution_results=[],
        execution_metadata={},
    )
    data.update(overrides)
    return CapabilityExecutionSummary(**data)


# =====================================================================
# DTOs
# =====================================================================
class SummaryModelTests(unittest.TestCase):
    def test_summary_defaults(self):
        summary = CapabilityExecutionSummary(
            runtime_id="r", execution_id="e", execution_status="COMPLETED"
        )
        self.assertEqual(summary.completed_execution_units, [])
        self.assertEqual(summary.failed_execution_units, [])
        self.assertEqual(summary.cancelled_execution_units, [])
        self.assertEqual(summary.execution_results, [])
        self.assertEqual(summary.execution_metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            CapabilityExecutionSummary(runtime_id="r")  # rest missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _summary().execution_status = "FAILED"

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in ExecutionSummaryStatus},
            {"COMPLETED", "PARTIAL", "FAILED", "CANCELLED"},
        )

    def test_produces_summary(self):
        self.assertIsInstance(
            _execute(_plan(), _StatusCapability()), CapabilityExecutionSummary
        )


# =====================================================================
# Successful execution
# =====================================================================
class SuccessfulExecutionTests(unittest.TestCase):
    def test_all_completed_is_completed(self):
        summary = _execute(_plan(("u1", "u2", "u3")), _StatusCapability("COMPLETED"))
        self.assertEqual(summary.execution_status, "COMPLETED")
        self.assertEqual(summary.completed_execution_units, ["u1", "u2", "u3"])
        self.assertEqual(summary.failed_execution_units, [])

    def test_aggregates_results(self):
        summary = _execute(_plan(("u1", "u2")), _StatusCapability("COMPLETED"))
        self.assertEqual(len(summary.execution_results), 2)
        self.assertTrue(
            all(
                isinstance(r, CapabilityExecutionResult)
                for r in summary.execution_results
            )
        )

    def test_invokes_capability_once_per_assignment(self):
        capability = _RecordingCapability()
        _execute(_plan(("u1", "u2", "u3")), capability)
        self.assertEqual(capability.calls, ["u1", "u2", "u3"])

    def test_preserves_execution_order(self):
        # Deliberately unsorted assignment order — execution must not reorder.
        capability = _RecordingCapability()
        summary = _execute(_plan(("u3", "u1", "u2")), capability)
        self.assertEqual(capability.calls, ["u3", "u1", "u2"])
        self.assertEqual(
            [r.execution_unit_id for r in summary.execution_results],
            ["u3", "u1", "u2"],
        )


# =====================================================================
# Partial failure / total failure / cancellation
# =====================================================================
class OutcomeTests(unittest.TestCase):
    def test_partial_failure_is_partial(self):
        summary = _execute(
            _plan(("u1", "u2", "u3")),
            _StatusCapability("COMPLETED", {"u2": "FAILED"}),
        )
        self.assertEqual(summary.execution_status, "PARTIAL")
        self.assertEqual(summary.failed_execution_units, ["u2"])
        self.assertEqual(summary.completed_execution_units, ["u1", "u3"])

    def test_total_failure_is_failed(self):
        summary = _execute(_plan(("u1", "u2")), _StatusCapability("FAILED"))
        self.assertEqual(summary.execution_status, "FAILED")
        self.assertEqual(summary.failed_execution_units, ["u1", "u2"])

    def test_all_cancelled_is_cancelled(self):
        summary = _execute(_plan(("u1", "u2")), _StatusCapability("CANCELLED"))
        self.assertEqual(summary.execution_status, "CANCELLED")
        self.assertEqual(summary.cancelled_execution_units, ["u1", "u2"])

    def test_cancelled_results_propagate_in_mix(self):
        summary = _execute(
            _plan(("u1", "u2")),
            _StatusCapability("COMPLETED", {"u2": "CANCELLED"}),
        )
        self.assertEqual(summary.execution_status, "PARTIAL")
        self.assertEqual(summary.cancelled_execution_units, ["u2"])
        self.assertEqual(summary.completed_execution_units, ["u1"])

    def test_failed_and_cancelled_mix_is_partial(self):
        summary = _execute(
            _plan(("u1", "u2")),
            _StatusCapability("FAILED", {"u2": "CANCELLED"}),
        )
        self.assertEqual(summary.execution_status, "PARTIAL")
        self.assertEqual(summary.failed_execution_units, ["u1"])
        self.assertEqual(summary.cancelled_execution_units, ["u2"])


# =====================================================================
# Empty plan
# =====================================================================
class EmptyPlanTests(unittest.TestCase):
    def test_empty_plan_is_completed(self):
        summary = _execute(_plan((), status="UNRESOLVED"), _StatusCapability())
        self.assertEqual(summary.execution_status, "COMPLETED")
        self.assertEqual(summary.execution_results, [])

    def test_empty_plan_never_invokes_capability(self):
        capability = _RecordingCapability()
        _execute(_plan((), status="COMPLETED"), capability)
        self.assertEqual(capability.calls, [])


# =====================================================================
# Provider error propagation
# =====================================================================
class ProviderErrorTests(unittest.TestCase):
    def test_capability_exception_propagates_unchanged(self):
        with self.assertRaises(RuntimeError) as ctx:
            _execute(_plan(("u1",)), _RaisingCapability())
        self.assertEqual(str(ctx.exception), "provider boom")

    def test_exception_is_not_swallowed_into_summary(self):
        with self.assertRaises(RuntimeError):
            _execute(_plan(("u1", "u2")), _RaisingCapability())


# =====================================================================
# Determinism, preservation & statelessness
# =====================================================================
class QualityTests(unittest.TestCase):
    def test_deterministic(self):
        plan = _plan(("u1", "u2"))
        capability = _StatusCapability("COMPLETED")
        self.assertEqual(_execute(plan, capability), _execute(plan, capability))

    def test_independent_executors_agree(self):
        plan = _plan(("u1", "u2"), status="READY")
        self.assertEqual(
            CapabilityExecutor(_StatusCapability()).execute(plan),
            CapabilityExecutor(_StatusCapability()).execute(plan),
        )

    def test_does_not_mutate_dispatch_plan(self):
        plan = _plan(("u1", "u2"))
        before = plan.model_dump()
        _execute(plan, _StatusCapability("FAILED"))
        self.assertEqual(plan.model_dump(), before)

    def test_ids_and_metadata_from_plan(self):
        summary = _execute(
            _plan(("u1", "u2", "u3")),
            _StatusCapability("COMPLETED", {"u3": "FAILED"}),
        )
        self.assertEqual(summary.runtime_id, "runtime-exec-x")
        self.assertEqual(summary.execution_id, "exec-x")
        self.assertEqual(summary.execution_metadata["total"], 3)
        self.assertEqual(summary.execution_metadata["completed_count"], 2)
        self.assertEqual(summary.execution_metadata["failed_count"], 1)

    def test_holds_only_injected_capability(self):
        capability = _StatusCapability()
        executor = CapabilityExecutor(capability)
        self.assertEqual(set(vars(executor)), {"capability"})
        self.assertIs(executor.capability, capability)

    def test_no_state_accumulates_across_calls(self):
        capability = _StatusCapability()
        executor = CapabilityExecutor(capability)
        executor.execute(_plan(("u1",)))
        self.assertEqual(set(vars(executor)), {"capability"})


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class ExecutorDependencyTests(unittest.TestCase):
    def test_get_capability_executor_wires_injected_capability(self):
        from app.core.dependencies import get_capability_executor

        capability = _StatusCapability()
        executor = get_capability_executor(capability)
        self.assertIsInstance(executor, CapabilityExecutor)
        self.assertIs(executor.capability, capability)

    def test_injected_executor_runs(self):
        from app.core.dependencies import get_capability_executor

        summary = get_capability_executor(_StatusCapability()).execute(
            _plan(("u1",))
        )
        self.assertEqual(summary.execution_status, "COMPLETED")

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import CapabilityExecutorDep

        self.assertIsNotNone(CapabilityExecutorDep)

    def test_capability_seam_still_raises(self):
        # The executor injects the capability through the existing 14.3 seam,
        # which stays unfulfilled until a concrete capability is wired.
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()


# =====================================================================
# Regression: Sprint 14.4 dispatcher & 14.3 seam unchanged
# =====================================================================
class Sprint14RegressionTests(unittest.TestCase):
    def test_capability_dispatcher_still_works(self):
        from app.core.dependencies import get_capability_dispatcher
        from app.services.runtime.task_dispatcher_models import DispatchPlan

        dispatch_plan = DispatchPlan(
            runtime_id="runtime-exec-x",
            execution_id="exec-x",
            dispatch_status="READY",
            ready_execution_units=["u1"],
            blocked_execution_units=[],
            deferred_execution_units=[],
            dispatch_metadata={},
        )
        result = get_capability_dispatcher().create_capability_dispatch_plan(
            dispatch_plan
        )
        self.assertEqual(result.dispatch_status, "READY")

    def test_orchestration_pipeline_unchanged(self):
        from app.core.dependencies import get_execution_orchestration_engine
        from app.services.planning import PlanningRequest

        result = get_execution_orchestration_engine().create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertEqual(result.plan.goal, "Plan your trip")


if __name__ == "__main__":
    unittest.main()
