"""Unit tests for the Sprint 14.4 Capability Dispatcher.

Covers the capability-routing layer end to end without touching any network, SDK,
AI, clock, UUID, concrete capability, capability instantiation, registry,
execution, or database:

* the immutable :class:`CapabilityDispatchPlan` / :class:`CapabilityAssignment`
  DTOs and the :class:`CapabilityDispatchStatus` enum (defaults, immutability,
  required fields, enum values);
* the deterministic, stateless :class:`CapabilityDispatcher` (unit->capability
  mapping, order preservation, unresolved handling, status derivation, empty
  plan, determinism, statelessness, non-mutation, provider independence);
* the composition-root wiring (``get_capability_dispatcher`` +
  ``CapabilityDispatcherDep``); and
* regression that the Sprint 14.2 dispatch layer and the Sprint 13 pipeline are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_capability_dispatcher
"""

import unittest

from pydantic import ValidationError

from app.services.runtime.capability_dispatcher import CapabilityDispatcher
from app.services.runtime.capability_dispatcher_models import (
    CapabilityAssignment,
    CapabilityDispatchPlan,
    CapabilityDispatchStatus,
)
from app.services.runtime.task_dispatcher_models import DispatchPlan


# =====================================================================
# Helpers
# =====================================================================
def _dispatch_plan(
    ready=(),
    blocked=(),
    deferred=(),
    status=None,
    runtime_id="runtime-exec-x",
    execution_id="exec-x",
):
    if status is None:
        status = (
            "READY"
            if ready
            else "BLOCKED"
            if blocked
            else "WAITING"
            if deferred
            else "COMPLETED"
        )
    return DispatchPlan(
        runtime_id=runtime_id,
        execution_id=execution_id,
        dispatch_status=status,
        ready_execution_units=list(ready),
        blocked_execution_units=list(blocked),
        deferred_execution_units=list(deferred),
        dispatch_metadata={},
    )


def _create(dispatch_plan=None):
    return CapabilityDispatcher().create_capability_dispatch_plan(
        dispatch_plan if dispatch_plan is not None else _dispatch_plan(["u1"])
    )


def _cap_plan(**overrides):
    assignments = overrides.pop(
        "capability_assignments",
        [CapabilityAssignment(execution_unit_id="u1", capability_name="capability-u1")],
    )
    data = dict(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        dispatch_status="READY",
        capability_assignments=assignments,
        unresolved_execution_units=[],
        dispatch_metadata={},
    )
    data.update(overrides)
    return CapabilityDispatchPlan(**data)


# =====================================================================
# DTOs
# =====================================================================
class CapabilityDispatchModelTests(unittest.TestCase):
    def test_plan_defaults(self):
        plan = CapabilityDispatchPlan(
            runtime_id="r", execution_id="e", dispatch_status="COMPLETED"
        )
        self.assertEqual(plan.capability_assignments, [])
        self.assertEqual(plan.unresolved_execution_units, [])
        self.assertEqual(plan.dispatch_metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            CapabilityDispatchPlan(runtime_id="r")  # rest missing

    def test_assignment_requires_fields(self):
        with self.assertRaises(ValidationError):
            CapabilityAssignment(execution_unit_id="u")  # capability missing

    def test_plan_immutable(self):
        with self.assertRaises(ValidationError):
            _cap_plan().dispatch_status = "PARTIAL"

    def test_assignment_immutable(self):
        assignment = CapabilityAssignment(
            execution_unit_id="u1", capability_name="capability-u1"
        )
        with self.assertRaises(ValidationError):
            assignment.capability_name = "other"

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in CapabilityDispatchStatus},
            {"READY", "PARTIAL", "UNRESOLVED", "COMPLETED"},
        )

    def test_produces_capability_dispatch_plan(self):
        self.assertIsInstance(_create(), CapabilityDispatchPlan)


# =====================================================================
# Mapping & ordering
# =====================================================================
class MappingTests(unittest.TestCase):
    def test_each_ready_unit_is_assigned(self):
        plan = _create(_dispatch_plan(["u1", "u2", "u3"]))
        self.assertEqual(
            [a.execution_unit_id for a in plan.capability_assignments],
            ["u1", "u2", "u3"],
        )
        self.assertEqual(plan.unresolved_execution_units, [])

    def test_capability_name_derived_from_unit_id(self):
        plan = _create(_dispatch_plan(["wf-abc-u1"]))
        assignment = plan.capability_assignments[0]
        self.assertEqual(assignment.execution_unit_id, "wf-abc-u1")
        self.assertEqual(assignment.capability_name, "capability-wf-abc-u1")

    def test_preserves_ordering_exactly(self):
        # Deliberately unsorted ready ids — routing must never reorder.
        plan = _create(_dispatch_plan(["u3", "u1", "u2"]))
        self.assertEqual(
            [a.execution_unit_id for a in plan.capability_assignments],
            ["u3", "u1", "u2"],
        )

    def test_deterministic_mapping(self):
        source = _dispatch_plan(["u1", "u2"])
        self.assertEqual(_create(source), _create(source))


# =====================================================================
# Unresolved handling & status derivation (the deterministic rules)
# =====================================================================
class StatusDerivationTests(unittest.TestCase):
    def test_all_ready_resolved_is_ready(self):
        self.assertEqual(_create(_dispatch_plan(["u1", "u2"])).dispatch_status, "READY")

    def test_mixed_resolved_unresolved_is_partial(self):
        plan = _create(_dispatch_plan(["u1", "   ", "u2"]))
        self.assertEqual(plan.dispatch_status, "PARTIAL")
        self.assertEqual(
            [a.execution_unit_id for a in plan.capability_assignments], ["u1", "u2"]
        )
        self.assertEqual(plan.unresolved_execution_units, ["   "])

    def test_all_unresolved_is_unresolved(self):
        plan = _create(_dispatch_plan(["  ", ""], status="READY"))
        self.assertEqual(plan.dispatch_status, "UNRESOLVED")
        self.assertEqual(plan.capability_assignments, [])

    def test_no_ready_with_blocked_is_unresolved(self):
        plan = _create(_dispatch_plan(blocked=["b1"], status="BLOCKED"))
        self.assertEqual(plan.dispatch_status, "UNRESOLVED")

    def test_no_ready_with_deferred_is_unresolved(self):
        plan = _create(_dispatch_plan(deferred=["w1"], status="WAITING"))
        self.assertEqual(plan.dispatch_status, "UNRESOLVED")

    def test_empty_plan_is_completed(self):
        plan = _create(_dispatch_plan(status="COMPLETED"))
        self.assertEqual(plan.dispatch_status, "COMPLETED")
        self.assertEqual(plan.capability_assignments, [])
        self.assertEqual(plan.unresolved_execution_units, [])


# =====================================================================
# Preservation & identity/metadata
# =====================================================================
class PreservationTests(unittest.TestCase):
    def test_does_not_mutate_dispatch_plan(self):
        source = _dispatch_plan(["u1", "u2"], blocked=["b1"])
        before = source.model_dump()
        _create(source)
        self.assertEqual(source.model_dump(), before)

    def test_ids_come_from_dispatch_plan(self):
        source = _dispatch_plan(
            ["u1"], runtime_id="runtime-abc", execution_id="exec-abc"
        )
        plan = _create(source)
        self.assertEqual(plan.runtime_id, "runtime-abc")
        self.assertEqual(plan.execution_id, "exec-abc")

    def test_metadata_counts_are_deterministic(self):
        plan = _create(_dispatch_plan(["u1", "   ", "u2"]))
        self.assertEqual(plan.dispatch_metadata["ready_count"], 3)
        self.assertEqual(plan.dispatch_metadata["assigned_count"], 2)
        self.assertEqual(plan.dispatch_metadata["unresolved_count"], 1)
        self.assertEqual(plan.dispatch_metadata["source_dispatch_status"], "READY")


# =====================================================================
# Provider independence
# =====================================================================
class ProviderIndependenceTests(unittest.TestCase):
    def test_routes_arbitrary_unit_ids(self):
        # No knowledge of concrete capabilities: any unit id routes to a derived
        # capability key, never a Browser/Email/Calendar/Python/GitHub name.
        plan = _create(_dispatch_plan(["anything", "x-9", "unit_42"]))
        for assignment in plan.capability_assignments:
            self.assertTrue(
                assignment.capability_name.startswith("capability-")
            )

    def test_plain_data_only(self):
        plan = _create(_dispatch_plan(["u1"], blocked=["b1"]))
        plain = (str, int, float, bool, type(None))
        for value in plan.dispatch_metadata.values():
            self.assertIsInstance(value, plain)
        for unit_id in plan.unresolved_execution_units:
            self.assertIsInstance(unit_id, str)


# =====================================================================
# Statelessness & determinism
# =====================================================================
class DispatcherQualityTests(unittest.TestCase):
    def setUp(self):
        self.dispatcher = CapabilityDispatcher()
        self.source = _dispatch_plan(["u1", "u2"], blocked=["b1"])

    def test_stateless(self):
        self.assertEqual(vars(self.dispatcher), {})

    def test_no_state_accumulates(self):
        self.dispatcher.create_capability_dispatch_plan(self.source)
        self.assertEqual(vars(self.dispatcher), {})

    def test_deterministic(self):
        self.assertEqual(
            self.dispatcher.create_capability_dispatch_plan(self.source),
            self.dispatcher.create_capability_dispatch_plan(self.source),
        )

    def test_independent_dispatchers_agree(self):
        self.assertEqual(
            CapabilityDispatcher().create_capability_dispatch_plan(self.source),
            CapabilityDispatcher().create_capability_dispatch_plan(self.source),
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class CapabilityDispatcherDependencyTests(unittest.TestCase):
    def test_get_capability_dispatcher_returns_dispatcher(self):
        from app.core.dependencies import get_capability_dispatcher

        self.assertIsInstance(get_capability_dispatcher(), CapabilityDispatcher)

    def test_get_capability_dispatcher_is_stateless(self):
        from app.core.dependencies import get_capability_dispatcher

        self.assertEqual(vars(get_capability_dispatcher()), {})

    def test_injected_dispatcher_creates_plan(self):
        from app.core.dependencies import get_capability_dispatcher

        plan = get_capability_dispatcher().create_capability_dispatch_plan(
            _dispatch_plan(["u1"])
        )
        self.assertIsInstance(plan, CapabilityDispatchPlan)

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import CapabilityDispatcherDep

        self.assertIsNotNone(CapabilityDispatcherDep)

    def test_existing_dependencies_unchanged(self):
        from app.core.dependencies import get_task_dispatcher
        from app.services.runtime.task_dispatcher import TaskDispatcher

        self.assertIsInstance(get_task_dispatcher(), TaskDispatcher)


# =====================================================================
# Regression: Sprint 14.2 dispatch & Sprint 13 pipeline unchanged
# =====================================================================
class Sprint14RegressionTests(unittest.TestCase):
    def test_real_pipeline_dispatch_is_unresolved(self):
        # The fresh trip plan yields an all-deferred DispatchPlan (no ready
        # units), so capability routing is UNRESOLVED — nothing is routed.
        from app.core.dependencies import (
            get_execution_orchestration_engine,
            get_execution_runtime,
            get_task_dispatcher,
        )
        from app.services.planning import PlanningRequest

        orchestration = get_execution_orchestration_engine().create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        context = get_execution_runtime().create_context(orchestration)
        dispatch_plan = get_task_dispatcher().create_dispatch_plan(context)
        capability_plan = _create(dispatch_plan)
        self.assertEqual(capability_plan.dispatch_status, "UNRESOLVED")
        self.assertEqual(capability_plan.capability_assignments, [])

    def test_task_dispatcher_still_works(self):
        source = _dispatch_plan(["u1"])
        self.assertIsInstance(source, DispatchPlan)
        self.assertEqual(source.dispatch_status, "READY")


if __name__ == "__main__":
    unittest.main()
