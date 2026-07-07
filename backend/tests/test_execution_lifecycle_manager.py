"""Unit tests for the Sprint 14.9 Execution Lifecycle Manager.

Covers the runtime lifecycle layer end to end without touching any network, SDK,
AI, clock, UUID, capability, execution, or database:

* the immutable :class:`RuntimeExecutionLifecycle` DTO and the
  :class:`LifecycleStatus` enum (defaults, immutability, required fields, enum
  values);
* the deterministic, stateless :class:`ExecutionLifecycleManager` (every
  EventStatus mapping, event-order preservation, current stage, terminal
  detection, empty event log, determinism, statelessness, non-mutation, provider
  independence);
* the composition-root wiring (``get_execution_lifecycle_manager`` +
  ``ExecutionLifecycleManagerDep``); and
* regression that the Sprint 14.8 event manager and Sprint 13 pipeline are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_lifecycle_manager
"""

import unittest

from pydantic import ValidationError

from app.services.runtime.execution_event_models import (
    EventStatus,
    ExecutionEvent,
    ExecutionEventLog,
)
from app.services.runtime.execution_lifecycle_manager import (
    ExecutionLifecycleManager,
)
from app.services.runtime.execution_lifecycle_models import (
    LifecycleStatus,
    RuntimeExecutionLifecycle,
)


# Event status -> expected lifecycle status.
EXPECTED_LIFECYCLE = {
    "INITIALIZED": "INITIALIZED",
    "ACTIVE": "RUNNING",
    "COMPLETED": "COMPLETED",
    "FAILED": "FAILED",
    "CANCELLED": "CANCELLED",
}
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}


# =====================================================================
# Helpers
# =====================================================================
def _event(event_type="ACTIVE", sequence=1):
    return ExecutionEvent(
        event_id=f"event-{sequence}",
        event_type=event_type,
        execution_id="exec-x",
        runtime_id="runtime-exec-x",
        event_sequence=sequence,
    )


def _event_log(
    event_status="ACTIVE",
    events=None,
    runtime_id="runtime-exec-x",
    execution_id="exec-x",
):
    if events is None:
        events = [_event(event_status, 1)]
    return ExecutionEventLog(
        runtime_id=runtime_id,
        execution_id=execution_id,
        event_status=event_status,
        events=events,
        event_count=len(events),
        event_metadata={},
    )


def _lifecycle(event_log=None):
    return ExecutionLifecycleManager().create_lifecycle(
        event_log if event_log is not None else _event_log()
    )


def _model(**overrides):
    data = dict(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        lifecycle_status="RUNNING",
        lifecycle_events=[_event("ACTIVE", 1)],
        current_stage="ACTIVE",
        is_terminal=False,
        lifecycle_metadata={},
    )
    data.update(overrides)
    return RuntimeExecutionLifecycle(**data)


# =====================================================================
# DTOs
# =====================================================================
class LifecycleModelTests(unittest.TestCase):
    def test_defaults(self):
        lifecycle = RuntimeExecutionLifecycle(
            runtime_id="r",
            execution_id="e",
            lifecycle_status="INITIALIZED",
            current_stage="INITIALIZED",
            is_terminal=False,
        )
        self.assertEqual(lifecycle.lifecycle_events, [])
        self.assertEqual(lifecycle.lifecycle_metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            RuntimeExecutionLifecycle(runtime_id="r")  # rest missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _model().lifecycle_status = "COMPLETED"
        with self.assertRaises(ValidationError):
            _model().is_terminal = True

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in LifecycleStatus},
            {"INITIALIZED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"},
        )

    def test_produces_lifecycle(self):
        self.assertIsInstance(_lifecycle(), RuntimeExecutionLifecycle)


# =====================================================================
# Status mapping — every EventStatus
# =====================================================================
class LifecycleMappingTests(unittest.TestCase):
    def test_every_event_status_maps(self):
        for event_status in EventStatus:
            with self.subTest(event_status=event_status.value):
                lifecycle = _lifecycle(_event_log(event_status.value))
                self.assertEqual(
                    lifecycle.lifecycle_status,
                    EXPECTED_LIFECYCLE[event_status.value],
                )

    def test_initialized_is_initialized(self):
        self.assertEqual(
            _lifecycle(_event_log("INITIALIZED")).lifecycle_status, "INITIALIZED"
        )

    def test_active_is_running(self):
        self.assertEqual(
            _lifecycle(_event_log("ACTIVE")).lifecycle_status, "RUNNING"
        )

    def test_terminal_events_map_directly(self):
        for status in ("COMPLETED", "FAILED", "CANCELLED"):
            with self.subTest(status=status):
                self.assertEqual(
                    _lifecycle(_event_log(status)).lifecycle_status, status
                )


# =====================================================================
# Terminal detection
# =====================================================================
class TerminalDetectionTests(unittest.TestCase):
    def test_terminal_statuses_are_terminal(self):
        for status in ("COMPLETED", "FAILED", "CANCELLED"):
            with self.subTest(status=status):
                self.assertTrue(_lifecycle(_event_log(status)).is_terminal)

    def test_non_terminal_statuses_are_not_terminal(self):
        for status in ("INITIALIZED", "ACTIVE"):
            with self.subTest(status=status):
                self.assertFalse(_lifecycle(_event_log(status)).is_terminal)


# =====================================================================
# Current stage & ordering
# =====================================================================
class StageOrderingTests(unittest.TestCase):
    def test_current_stage_is_latest_event_type(self):
        log = _event_log(
            "ACTIVE",
            events=[_event("INITIALIZED", 1), _event("ACTIVE", 2)],
        )
        self.assertEqual(_lifecycle(log).current_stage, "ACTIVE")

    def test_preserves_event_order_exactly(self):
        events = [
            _event("INITIALIZED", 1),
            _event("ACTIVE", 2),
            _event("COMPLETED", 3),
        ]
        lifecycle = _lifecycle(_event_log("COMPLETED", events=events))
        self.assertEqual(
            [e.event_type for e in lifecycle.lifecycle_events],
            ["INITIALIZED", "ACTIVE", "COMPLETED"],
        )
        self.assertEqual(
            [e.event_sequence for e in lifecycle.lifecycle_events], [1, 2, 3]
        )

    def test_single_event_stage(self):
        self.assertEqual(_lifecycle(_event_log("ACTIVE")).current_stage, "ACTIVE")


# =====================================================================
# Empty event log
# =====================================================================
class EmptyEventLogTests(unittest.TestCase):
    def test_empty_log_preserves_empty_events(self):
        lifecycle = _lifecycle(_event_log("INITIALIZED", events=[]))
        self.assertEqual(lifecycle.lifecycle_events, [])

    def test_empty_log_stage_falls_back_to_event_status(self):
        lifecycle = _lifecycle(_event_log("COMPLETED", events=[]))
        self.assertEqual(lifecycle.current_stage, "COMPLETED")
        self.assertEqual(lifecycle.lifecycle_status, "COMPLETED")
        self.assertTrue(lifecycle.is_terminal)


# =====================================================================
# Determinism, non-mutation, provider independence, statelessness
# =====================================================================
class LifecycleQualityTests(unittest.TestCase):
    def test_deterministic(self):
        log = _event_log("ACTIVE")
        manager = ExecutionLifecycleManager()
        self.assertEqual(
            manager.create_lifecycle(log), manager.create_lifecycle(log)
        )

    def test_independent_managers_agree(self):
        log = _event_log("COMPLETED")
        self.assertEqual(
            ExecutionLifecycleManager().create_lifecycle(log),
            ExecutionLifecycleManager().create_lifecycle(log),
        )

    def test_ids_and_metadata_from_log(self):
        lifecycle = _lifecycle(_event_log("ACTIVE"))
        self.assertEqual(lifecycle.runtime_id, "runtime-exec-x")
        self.assertEqual(lifecycle.execution_id, "exec-x")
        self.assertEqual(lifecycle.lifecycle_metadata["event_status"], "ACTIVE")
        self.assertEqual(
            lifecycle.lifecycle_metadata["lifecycle_status"], "RUNNING"
        )

    def test_does_not_mutate_event_log(self):
        log = _event_log(
            "COMPLETED",
            events=[_event("ACTIVE", 1), _event("COMPLETED", 2)],
        )
        before = log.model_dump()
        _lifecycle(log)
        self.assertEqual(log.model_dump(), before)

    def test_plain_data_only(self):
        lifecycle = _lifecycle(_event_log("ACTIVE"))
        plain = (str, int, float, bool, type(None))
        for value in lifecycle.lifecycle_metadata.values():
            self.assertIsInstance(value, plain)

    def test_stateless(self):
        self.assertEqual(vars(ExecutionLifecycleManager()), {})

    def test_no_state_accumulates(self):
        manager = ExecutionLifecycleManager()
        manager.create_lifecycle(_event_log())
        self.assertEqual(vars(manager), {})


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class LifecycleDependencyTests(unittest.TestCase):
    def test_get_manager_returns_manager(self):
        from app.core.dependencies import get_execution_lifecycle_manager

        self.assertIsInstance(
            get_execution_lifecycle_manager(), ExecutionLifecycleManager
        )

    def test_get_manager_is_stateless(self):
        from app.core.dependencies import get_execution_lifecycle_manager

        self.assertEqual(vars(get_execution_lifecycle_manager()), {})

    def test_injected_manager_creates_lifecycle(self):
        from app.core.dependencies import get_execution_lifecycle_manager

        lifecycle = get_execution_lifecycle_manager().create_lifecycle(
            _event_log("ACTIVE")
        )
        self.assertIsInstance(lifecycle, RuntimeExecutionLifecycle)
        self.assertEqual(lifecycle.lifecycle_status, "RUNNING")

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import ExecutionLifecycleManagerDep

        self.assertIsNotNone(ExecutionLifecycleManagerDep)

    def test_existing_dependencies_unchanged(self):
        from app.core.dependencies import get_execution_event_manager
        from app.services.runtime.execution_event_manager import (
            ExecutionEventManager,
        )

        self.assertIsInstance(
            get_execution_event_manager(), ExecutionEventManager
        )


# =====================================================================
# Regression: Sprint 14.8 event manager & Sprint 13 pipeline unchanged
# =====================================================================
class Sprint14RegressionTests(unittest.TestCase):
    def test_event_manager_chain_still_works(self):
        # controller -> event manager -> lifecycle manager all compose cleanly.
        from app.core.dependencies import (
            get_execution_event_manager,
            get_execution_lifecycle_manager,
        )
        from app.services.runtime.execution_controller_models import (
            ExecutionControlState,
        )

        control_state = ExecutionControlState(
            runtime_id="runtime-exec-x",
            execution_id="exec-x",
            control_status="RUNNING",
            can_pause=True,
            can_resume=False,
            can_cancel=True,
            can_restart=False,
            control_metadata={},
        )
        log = get_execution_event_manager().create_event_log(control_state)
        lifecycle = get_execution_lifecycle_manager().create_lifecycle(log)
        self.assertEqual(lifecycle.lifecycle_status, "RUNNING")
        self.assertEqual(lifecycle.current_stage, "ACTIVE")

    def test_orchestration_pipeline_unchanged(self):
        from app.core.dependencies import get_execution_orchestration_engine
        from app.services.planning import PlanningRequest

        result = get_execution_orchestration_engine().create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertEqual(result.plan.goal, "Plan your trip")


if __name__ == "__main__":
    unittest.main()
