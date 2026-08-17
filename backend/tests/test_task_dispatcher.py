"""Unit tests for the Sprint 14.2 Task Dispatcher.

Covers the runtime dispatch layer end to end without touching any network, SDK,
AI, clock, UUID, capability, recovery, approval, execution, or database:

* the immutable :class:`DispatchPlan` DTO and the :class:`DispatchStatus` enum
  (defaults, immutability, required fields);
* the deterministic, stateless :class:`TaskDispatcher` (status derivation,
  ready/blocked/deferred partitioning, queue-order preservation, empty queue,
  determinism, statelessness, non-mutation of the runtime context and queue,
  provider independence);
* the composition-root wiring (``get_task_dispatcher`` + ``TaskDispatcherDep``);
  and
* regression that Sprint 14.1 runtime and the Sprint 13 pipeline are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_task_dispatcher
"""

import unittest

from pydantic import ValidationError

from app.core.dependencies import get_execution_orchestration_engine
from app.services.planning import PlanningRequest
from app.services.planning.execution_queue_models import (
    ExecutionQueue,
    ExecutionUnit,
)
from app.services.runtime.execution_runtime import ExecutionRuntime
from app.services.runtime.execution_runtime_models import ExecutionRuntimeContext
from app.services.runtime.task_dispatcher import TaskDispatcher
from app.services.runtime.task_dispatcher_models import (
    DispatchPlan,
    DispatchStatus,
)


# =====================================================================
# Helpers
# =====================================================================
_BASE_ORCH = None


def _base_orchestration():
    global _BASE_ORCH
    if _BASE_ORCH is None:
        engine = get_execution_orchestration_engine()
        _BASE_ORCH = engine.create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
    return _BASE_ORCH


def _unit(unit_id, status, step_number=1):
    return ExecutionUnit(
        unit_id=unit_id,
        step_number=step_number,
        description="d",
        execution_group=1,
        status=status,
        dependencies=[],
        metadata={},
    )


def _queue(units, status="READY"):
    return ExecutionQueue(
        queue_id="q",
        workflow_id="wf",
        status=status,
        execution_units=list(units),
        total_units=len(units),
        ready_units=sum(1 for u in units if u.status == "READY"),
        blocked_units=sum(1 for u in units if u.status == "BLOCKED"),
        metadata={},
    )


def _context(queue=None):
    orchestration = _base_orchestration()
    if queue is not None:
        orchestration = orchestration._replace(queue=queue)
    return ExecutionRuntime().create_context(orchestration)


def _dispatch(context=None, queue=None):
    if context is None:
        context = _context(queue)
    return TaskDispatcher().create_dispatch_plan(context)


def _plan(**overrides):
    data = dict(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        dispatch_status="READY",
        ready_execution_units=["u1"],
        blocked_execution_units=[],
        deferred_execution_units=[],
        dispatch_metadata={},
    )
    data.update(overrides)
    return DispatchPlan(**data)


# =====================================================================
# DTOs
# =====================================================================
class DispatchModelTests(unittest.TestCase):
    def test_plan_defaults(self):
        plan = DispatchPlan(
            runtime_id="r", execution_id="e", dispatch_status="COMPLETED"
        )
        self.assertEqual(plan.ready_execution_units, [])
        self.assertEqual(plan.blocked_execution_units, [])
        self.assertEqual(plan.deferred_execution_units, [])
        self.assertEqual(plan.dispatch_metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            DispatchPlan(runtime_id="r")  # rest missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _plan().dispatch_status = "BLOCKED"
        with self.assertRaises(ValidationError):
            _plan().ready_execution_units = ["x"]

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in DispatchStatus},
            {"READY", "WAITING", "BLOCKED", "COMPLETED"},
        )

    def test_produces_dispatch_plan(self):
        self.assertIsInstance(_dispatch(), DispatchPlan)


# =====================================================================
# Status derivation (the deterministic rules)
# =====================================================================
class DispatchStatusTests(unittest.TestCase):
    def test_ready_queue_is_ready(self):
        plan = _dispatch(queue=_queue([_unit("u1", "READY")]))
        self.assertEqual(plan.dispatch_status, "READY")

    def test_no_ready_with_blocked_is_blocked(self):
        plan = _dispatch(
            queue=_queue([_unit("u1", "BLOCKED")], status="BLOCKED")
        )
        self.assertEqual(plan.dispatch_status, "BLOCKED")

    def test_no_ready_with_deferred_is_waiting(self):
        plan = _dispatch(
            queue=_queue([_unit("u1", "WAITING")], status="WAITING")
        )
        self.assertEqual(plan.dispatch_status, "WAITING")

    def test_empty_queue_is_completed(self):
        plan = _dispatch(queue=_queue([]))
        self.assertEqual(plan.dispatch_status, "COMPLETED")

    def test_ready_takes_precedence_over_blocked_and_deferred(self):
        plan = _dispatch(
            queue=_queue(
                [
                    _unit("b", "BLOCKED", 1),
                    _unit("r", "READY", 2),
                    _unit("w", "WAITING", 3),
                ]
            )
        )
        self.assertEqual(plan.dispatch_status, "READY")

    def test_blocked_takes_precedence_over_deferred(self):
        plan = _dispatch(
            queue=_queue(
                [_unit("b", "BLOCKED", 1), _unit("w", "WAITING", 2)],
                status="BLOCKED",
            )
        )
        self.assertEqual(plan.dispatch_status, "BLOCKED")


# =====================================================================
# Queue partitioning, ordering & preservation
# =====================================================================
class QueuePartitionTests(unittest.TestCase):
    def test_partitions_by_status(self):
        plan = _dispatch(
            queue=_queue(
                [
                    _unit("r1", "READY", 1),
                    _unit("b1", "BLOCKED", 2),
                    _unit("w1", "WAITING", 3),
                    _unit("r2", "READY", 4),
                ]
            )
        )
        self.assertEqual(plan.ready_execution_units, ["r1", "r2"])
        self.assertEqual(plan.blocked_execution_units, ["b1"])
        self.assertEqual(plan.deferred_execution_units, ["w1"])

    def test_preserves_queue_ordering_exactly(self):
        # Deliberately unsorted step numbers — the dispatcher must never reorder.
        plan = _dispatch(
            queue=_queue(
                [
                    _unit("u3", "READY", 3),
                    _unit("u1", "READY", 1),
                    _unit("u2", "READY", 2),
                ]
            )
        )
        self.assertEqual(plan.ready_execution_units, ["u3", "u1", "u2"])

    def test_does_not_mutate_queue(self):
        queue = _queue([_unit("u1", "READY", 1), _unit("u2", "BLOCKED", 2)])
        before = queue.model_dump()
        _dispatch(queue=queue)
        self.assertEqual(queue.model_dump(), before)

    def test_does_not_mutate_runtime_context(self):
        context = _context(_queue([_unit("u1", "READY")]))
        TaskDispatcher().create_dispatch_plan(context)
        self.assertEqual(context.runtime_status, "INITIALIZED")
        self.assertIsNone(context.current_execution_unit_id)
        self.assertEqual(context.execution_variables, {})


# =====================================================================
# Ids & metadata
# =====================================================================
class DispatchIdentityTests(unittest.TestCase):
    def test_ids_come_from_runtime_context(self):
        context = _context(_queue([_unit("u1", "READY")]))
        plan = TaskDispatcher().create_dispatch_plan(context)
        self.assertEqual(plan.runtime_id, context.runtime_id)
        self.assertEqual(plan.execution_id, context.execution_id)

    def test_metadata_counts_are_deterministic(self):
        queue = _queue(
            [
                _unit("r1", "READY", 1),
                _unit("b1", "BLOCKED", 2),
                _unit("w1", "WAITING", 3),
            ]
        )
        plan = _dispatch(queue=queue)
        self.assertEqual(plan.dispatch_metadata["total_units"], 3)
        self.assertEqual(plan.dispatch_metadata["ready_count"], 1)
        self.assertEqual(plan.dispatch_metadata["blocked_count"], 1)
        self.assertEqual(plan.dispatch_metadata["deferred_count"], 1)
        self.assertEqual(plan.dispatch_metadata["queue_status"], queue.status)


# =====================================================================
# Provider independence
# =====================================================================
class ProviderIndependenceTests(unittest.TestCase):
    def test_dispatcher_needs_no_provider(self):
        dispatcher = TaskDispatcher()
        self.assertIsInstance(
            dispatcher.create_dispatch_plan(_context()), DispatchPlan
        )

    def test_plain_data_only(self):
        plan = _dispatch(
            queue=_queue([_unit("u1", "READY"), _unit("u2", "BLOCKED", 2)])
        )
        plain = (str, int, float, bool, type(None))
        for value in plan.dispatch_metadata.values():
            self.assertIsInstance(value, plain)
        for unit_id in (
            plan.ready_execution_units
            + plan.blocked_execution_units
            + plan.deferred_execution_units
        ):
            self.assertIsInstance(unit_id, str)


# =====================================================================
# Statelessness & determinism
# =====================================================================
class DispatchQualityTests(unittest.TestCase):
    def setUp(self):
        self.dispatcher = TaskDispatcher()
        self.context = _context(
            _queue([_unit("u1", "READY", 1), _unit("u2", "BLOCKED", 2)])
        )

    def test_stateless(self):
        self.assertEqual(vars(self.dispatcher), {})

    def test_no_state_accumulates_across_calls(self):
        self.dispatcher.create_dispatch_plan(self.context)
        self.assertEqual(vars(self.dispatcher), {})

    def test_deterministic(self):
        self.assertEqual(
            self.dispatcher.create_dispatch_plan(self.context),
            self.dispatcher.create_dispatch_plan(self.context),
        )

    def test_independent_dispatchers_agree(self):
        self.assertEqual(
            TaskDispatcher().create_dispatch_plan(self.context),
            TaskDispatcher().create_dispatch_plan(self.context),
        )

    def test_same_runtime_identical_plan(self):
        context = _context(_queue([_unit("u1", "READY")]))
        self.assertEqual(
            _dispatch(context), _dispatch(context)
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DispatcherDependencyTests(unittest.TestCase):
    def test_get_task_dispatcher_returns_dispatcher(self):
        from app.core.dependencies import get_task_dispatcher

        self.assertIsInstance(get_task_dispatcher(), TaskDispatcher)

    def test_get_task_dispatcher_is_stateless(self):
        from app.core.dependencies import get_task_dispatcher

        self.assertEqual(vars(get_task_dispatcher()), {})

    def test_injected_dispatcher_creates_plan(self):
        from app.core.dependencies import get_task_dispatcher

        plan = get_task_dispatcher().create_dispatch_plan(_context())
        self.assertIsInstance(plan, DispatchPlan)

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import TaskDispatcherDep

        self.assertIsNotNone(TaskDispatcherDep)

    def test_existing_runtime_dependency_unchanged(self):
        from app.core.dependencies import get_execution_runtime

        self.assertIsInstance(get_execution_runtime(), ExecutionRuntime)


# =====================================================================
# Regression: Sprint 14.1 runtime & Sprint 13 pipeline unchanged
# =====================================================================
class Sprint14RegressionTests(unittest.TestCase):
    def test_runtime_context_still_initializes(self):
        context = _context()
        self.assertIsInstance(context, ExecutionRuntimeContext)
        self.assertEqual(context.runtime_status, "INITIALIZED")

    def test_real_pipeline_dispatch_is_waiting(self):
        # The fresh trip plan gates on confirmation, so every queued unit is
        # WAITING (deferred) — the dispatcher reports WAITING, dispatching nothing.
        plan = _dispatch(_context())
        self.assertEqual(plan.dispatch_status, "WAITING")
        self.assertEqual(plan.ready_execution_units, [])
        self.assertEqual(
            len(plan.deferred_execution_units),
            len(_base_orchestration().queue.execution_units),
        )

    def test_orchestration_pipeline_unchanged(self):
        result = _base_orchestration()
        self.assertEqual(len(result), 14)
        self.assertEqual(result.plan.goal, "Plan your trip")


if __name__ == "__main__":
    unittest.main()
