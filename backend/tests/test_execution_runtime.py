"""Unit tests for the Sprint 14.1 Execution Runtime.

Covers the first runtime layer end to end without touching any network, SDK, AI,
clock, UUID, tool execution, dispatcher, recovery, approval, or database:

* the immutable :class:`ExecutionRuntimeContext` DTO and the
  :class:`ExecutionRuntimeStatus` enum (defaults, immutability, required fields);
* the deterministic, stateless :class:`ExecutionRuntime` (deterministic runtime
  id, INITIALIZED status, empty variable/output/metadata stores, orchestration
  preservation, determinism, statelessness, provider independence);
* the composition-root wiring (``get_execution_runtime`` + ``ExecutionRuntimeDep``);
  and
* regression that the Sprint 13 orchestration pipeline is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_runtime
"""

import unittest

from pydantic import ValidationError

from app.core.dependencies import get_execution_orchestration_engine
from app.services.planning import PlanningRequest
from app.services.planning.planning_engine import ExecutionOrchestrationResult
from app.services.runtime.execution_runtime import ExecutionRuntime
from app.services.runtime.execution_runtime_models import (
    ExecutionRuntimeContext,
    ExecutionRuntimeStatus,
)


# =====================================================================
# Helpers
# =====================================================================
def _orchestration(text="plan a trip to Japan"):
    engine = get_execution_orchestration_engine()
    return engine.create_execution_orchestration(
        PlanningRequest(user_request=text)
    )


def _context(orchestration=None):
    return ExecutionRuntime().create_context(
        orchestration if orchestration is not None else _orchestration()
    )


# =====================================================================
# DTOs
# =====================================================================
class RuntimeContextModelTests(unittest.TestCase):
    def setUp(self):
        self.orchestration = _orchestration()

    def test_context_defaults(self):
        context = ExecutionRuntimeContext(
            runtime_id="r",
            execution_id="e",
            runtime_status="INITIALIZED",
            orchestration=self.orchestration,
            created_at_sequence=0,
        )
        self.assertIsNone(context.current_execution_unit_id)
        self.assertEqual(context.execution_variables, {})
        self.assertEqual(context.execution_outputs, {})
        self.assertEqual(context.execution_metadata, {})
        self.assertEqual(context.metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionRuntimeContext(runtime_id="r")  # rest missing

    def test_immutable(self):
        context = _context(self.orchestration)
        with self.assertRaises(ValidationError):
            context.runtime_status = "READY"
        with self.assertRaises(ValidationError):
            context.execution_variables = {"x": 1}

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in ExecutionRuntimeStatus},
            {"INITIALIZED", "READY", "PAUSED", "CANCELLED", "COMPLETED"},
        )

    def test_produces_runtime_context(self):
        self.assertIsInstance(_context(self.orchestration), ExecutionRuntimeContext)


# =====================================================================
# Deterministic runtime ids
# =====================================================================
class RuntimeIdTests(unittest.TestCase):
    def setUp(self):
        self.orchestration = _orchestration()

    def test_runtime_id_derived_from_execution_id(self):
        context = _context(self.orchestration)
        self.assertEqual(
            context.runtime_id, f"runtime-{context.execution_id}"
        )

    def test_execution_id_comes_from_orchestration(self):
        context = _context(self.orchestration)
        self.assertEqual(
            context.execution_id, self.orchestration.state.execution_id
        )

    def test_same_orchestration_same_runtime_id(self):
        self.assertEqual(
            _context(self.orchestration).runtime_id,
            _context(self.orchestration).runtime_id,
        )

    def test_different_orchestrations_differ(self):
        trip = _context(_orchestration("plan a trip to Japan"))
        interview = _context(_orchestration("prepare me for my interview"))
        self.assertNotEqual(trip.runtime_id, interview.runtime_id)


# =====================================================================
# Initialization
# =====================================================================
class RuntimeInitializationTests(unittest.TestCase):
    def setUp(self):
        self.context = _context()

    def test_status_always_initialized(self):
        self.assertEqual(self.context.runtime_status, "INITIALIZED")

    def test_current_execution_unit_id_none(self):
        self.assertIsNone(self.context.current_execution_unit_id)

    def test_created_at_sequence_is_zero_integer(self):
        self.assertEqual(self.context.created_at_sequence, 0)
        self.assertIsInstance(self.context.created_at_sequence, int)
        self.assertNotIsInstance(self.context.created_at_sequence, bool)

    def test_created_at_sequence_is_deterministic(self):
        orchestration = _orchestration()
        self.assertEqual(
            _context(orchestration).created_at_sequence,
            _context(orchestration).created_at_sequence,
        )


# =====================================================================
# Orchestration preservation
# =====================================================================
class OrchestrationPreservationTests(unittest.TestCase):
    def setUp(self):
        self.orchestration = _orchestration()

    def test_orchestration_stored_by_identity(self):
        context = _context(self.orchestration)
        self.assertIs(context.orchestration, self.orchestration)

    def test_orchestration_accessible(self):
        context = _context(self.orchestration)
        self.assertEqual(context.orchestration.plan.goal, "Plan your trip")
        self.assertIs(
            context.orchestration.approval_plan,
            self.orchestration.approval_plan,
        )

    def test_orchestration_not_modified(self):
        before = (
            self.orchestration.plan.goal,
            self.orchestration.approval_plan.approval_strategy,
            len(self.orchestration.queue.execution_units),
        )
        _context(self.orchestration)
        after = (
            self.orchestration.plan.goal,
            self.orchestration.approval_plan.approval_strategy,
            len(self.orchestration.queue.execution_units),
        )
        self.assertEqual(before, after)

    def test_orchestration_type_preserved(self):
        context = _context(self.orchestration)
        self.assertIsInstance(
            context.orchestration, ExecutionOrchestrationResult
        )


# =====================================================================
# Empty working stores & metadata
# =====================================================================
class RuntimeStoreTests(unittest.TestCase):
    def setUp(self):
        self.orchestration = _orchestration()
        self.context = _context(self.orchestration)

    def test_execution_variables_empty(self):
        self.assertEqual(self.context.execution_variables, {})

    def test_execution_outputs_empty(self):
        self.assertEqual(self.context.execution_outputs, {})

    def test_execution_metadata_empty(self):
        self.assertEqual(self.context.execution_metadata, {})

    def test_metadata_is_deterministic_and_descriptive(self):
        self.assertEqual(
            self.context.metadata["total_execution_units"],
            len(self.orchestration.queue.execution_units),
        )
        self.assertEqual(
            self.context.metadata["source_execution_id"],
            self.orchestration.state.execution_id,
        )

    def test_metadata_is_deterministic(self):
        self.assertEqual(
            _context(self.orchestration).metadata,
            _context(self.orchestration).metadata,
        )


# =====================================================================
# Provider independence
# =====================================================================
class ProviderIndependenceTests(unittest.TestCase):
    def test_runtime_needs_no_provider(self):
        # Constructed with no provider/session/SDK argument at all.
        runtime = ExecutionRuntime()
        self.assertIsInstance(
            runtime.create_context(_orchestration()), ExecutionRuntimeContext
        )

    def test_plain_data_only(self):
        context = _context()
        plain = (str, int, float, bool, type(None))
        for store in (
            context.execution_variables,
            context.execution_outputs,
            context.execution_metadata,
            context.metadata,
        ):
            for value in store.values():
                self.assertIsInstance(value, plain)


# =====================================================================
# Statelessness & determinism
# =====================================================================
class RuntimeQualityTests(unittest.TestCase):
    def setUp(self):
        self.runtime = ExecutionRuntime()
        self.orchestration = _orchestration()

    def test_stateless(self):
        self.assertEqual(vars(self.runtime), {})

    def test_no_state_accumulates_across_calls(self):
        self.runtime.create_context(self.orchestration)
        self.assertEqual(vars(self.runtime), {})

    def test_deterministic(self):
        self.assertEqual(
            self.runtime.create_context(self.orchestration),
            self.runtime.create_context(self.orchestration),
        )

    def test_independent_runtimes_agree(self):
        self.assertEqual(
            ExecutionRuntime().create_context(self.orchestration),
            ExecutionRuntime().create_context(self.orchestration),
        )

    def test_one_orchestration_one_context(self):
        self.assertIsInstance(
            self.runtime.create_context(self.orchestration),
            ExecutionRuntimeContext,
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class RuntimeDependencyTests(unittest.TestCase):
    def test_get_execution_runtime_returns_runtime(self):
        from app.core.dependencies import get_execution_runtime

        self.assertIsInstance(get_execution_runtime(), ExecutionRuntime)

    def test_get_execution_runtime_is_stateless(self):
        from app.core.dependencies import get_execution_runtime

        self.assertEqual(vars(get_execution_runtime()), {})

    def test_injected_runtime_creates_context(self):
        from app.core.dependencies import get_execution_runtime

        context = get_execution_runtime().create_context(_orchestration())
        self.assertIsInstance(context, ExecutionRuntimeContext)
        self.assertEqual(context.runtime_status, "INITIALIZED")

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import ExecutionRuntimeDep

        self.assertIsNotNone(ExecutionRuntimeDep)

    def test_existing_orchestration_dependency_unchanged(self):
        # The Sprint 13.15 coordinator provider still works untouched.
        engine = get_execution_orchestration_engine()
        result = engine.create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertIsInstance(result, ExecutionOrchestrationResult)


# =====================================================================
# Regression: Sprint 13 pipeline unchanged
# =====================================================================
class Sprint13RegressionTests(unittest.TestCase):
    def test_orchestration_pipeline_still_produces_all_stages(self):
        result = _orchestration()
        self.assertEqual(len(result), 14)
        self.assertEqual(result.plan.goal, "Plan your trip")

    def test_runtime_does_not_disturb_orchestration_determinism(self):
        first = _orchestration()
        _context(first)
        second = _orchestration()
        self.assertEqual(first, second)

    def test_runtime_context_carries_orchestration_execution_id(self):
        result = _orchestration()
        context = _context(result)
        self.assertEqual(context.execution_id, result.state.execution_id)


if __name__ == "__main__":
    unittest.main()
