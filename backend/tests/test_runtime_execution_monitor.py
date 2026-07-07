"""Unit tests for the Sprint 14.11 Runtime Execution Monitor.

Covers the runtime health layer end to end without touching any network, SDK, AI,
clock, UUID, capability, execution, or database:

* the immutable :class:`RuntimeExecutionHealth` DTO and the
  :class:`RuntimeHealthStatus` enum (defaults, immutability, required fields, enum
  values);
* the deterministic, stateless :class:`RuntimeExecutionMonitor` (every
  RuntimeStateStatus mapping, health score, warning generation, empty warnings,
  determinism, statelessness, non-mutation, provider independence);
* the composition-root wiring (``get_runtime_execution_monitor`` +
  ``RuntimeExecutionMonitorDep``); and
* regression that the Sprint 14.10 state manager and Sprint 13 pipeline are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_runtime_execution_monitor
"""

import unittest

from pydantic import ValidationError

from app.services.runtime.runtime_execution_monitor import (
    RuntimeExecutionMonitor,
)
from app.services.runtime.runtime_execution_monitor_models import (
    RuntimeExecutionHealth,
    RuntimeHealthStatus,
)
from app.services.runtime.runtime_execution_state_models import (
    RuntimeExecutionState,
    RuntimeStateStatus,
)


# State status -> (expected health status, score, warnings).
EXPECTED = {
    "INITIALIZED": ("HEALTHY", 100, []),
    "RUNNING": ("HEALTHY", 100, []),
    "COMPLETED": ("COMPLETED", 100, []),
    "FAILED": ("FAILED", 0, ["Execution failed"]),
    "CANCELLED": ("WARNING", 75, ["Execution cancelled"]),
}
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}


# =====================================================================
# Helpers
# =====================================================================
def _state(
    state_status="RUNNING",
    runtime_id="runtime-exec-x",
    execution_id="exec-x",
):
    return RuntimeExecutionState(
        runtime_id=runtime_id,
        execution_id=execution_id,
        state_status=state_status,
        current_stage=state_status,
        is_active=state_status == "RUNNING",
        is_terminal=state_status in TERMINAL_STATUSES,
        runtime_metadata={},
    )


def _health(state=None):
    return RuntimeExecutionMonitor().create_health(
        state if state is not None else _state()
    )


def _model(**overrides):
    data = dict(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        health_status="HEALTHY",
        health_score=100,
        runtime_warnings=[],
        runtime_metadata={},
    )
    data.update(overrides)
    return RuntimeExecutionHealth(**data)


# =====================================================================
# DTOs
# =====================================================================
class HealthModelTests(unittest.TestCase):
    def test_defaults(self):
        health = RuntimeExecutionHealth(
            runtime_id="r",
            execution_id="e",
            health_status="HEALTHY",
            health_score=100,
        )
        self.assertEqual(health.runtime_warnings, [])
        self.assertEqual(health.runtime_metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            RuntimeExecutionHealth(runtime_id="r")  # rest missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _model().health_status = "FAILED"
        with self.assertRaises(ValidationError):
            _model().health_score = 0

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in RuntimeHealthStatus},
            {"HEALTHY", "WARNING", "FAILED", "COMPLETED"},
        )

    def test_produces_health(self):
        self.assertIsInstance(_health(), RuntimeExecutionHealth)


# =====================================================================
# Status mapping — every RuntimeStateStatus
# =====================================================================
class HealthMappingTests(unittest.TestCase):
    def test_every_state_status_maps(self):
        for state_status in RuntimeStateStatus:
            with self.subTest(state_status=state_status.value):
                health = _health(_state(state_status.value))
                expected_status, _, _ = EXPECTED[state_status.value]
                self.assertEqual(health.health_status, expected_status)

    def test_initialized_and_running_are_healthy(self):
        self.assertEqual(_health(_state("INITIALIZED")).health_status, "HEALTHY")
        self.assertEqual(_health(_state("RUNNING")).health_status, "HEALTHY")

    def test_completed_is_completed(self):
        self.assertEqual(_health(_state("COMPLETED")).health_status, "COMPLETED")

    def test_failed_is_failed(self):
        self.assertEqual(_health(_state("FAILED")).health_status, "FAILED")

    def test_cancelled_is_warning(self):
        self.assertEqual(_health(_state("CANCELLED")).health_status, "WARNING")


# =====================================================================
# Health score
# =====================================================================
class HealthScoreTests(unittest.TestCase):
    def test_scores_for_every_status(self):
        for state_status in RuntimeStateStatus:
            with self.subTest(state_status=state_status.value):
                _, expected_score, _ = EXPECTED[state_status.value]
                self.assertEqual(
                    _health(_state(state_status.value)).health_score,
                    expected_score,
                )

    def test_healthy_and_completed_score_100(self):
        self.assertEqual(_health(_state("RUNNING")).health_score, 100)
        self.assertEqual(_health(_state("COMPLETED")).health_score, 100)

    def test_warning_scores_75(self):
        self.assertEqual(_health(_state("CANCELLED")).health_score, 75)

    def test_failed_scores_0(self):
        self.assertEqual(_health(_state("FAILED")).health_score, 0)


# =====================================================================
# Warnings
# =====================================================================
class WarningTests(unittest.TestCase):
    def test_failed_warning(self):
        self.assertEqual(
            _health(_state("FAILED")).runtime_warnings, ["Execution failed"]
        )

    def test_cancelled_warning(self):
        self.assertEqual(
            _health(_state("CANCELLED")).runtime_warnings,
            ["Execution cancelled"],
        )

    def test_empty_warnings_otherwise(self):
        for status in ("INITIALIZED", "RUNNING", "COMPLETED"):
            with self.subTest(status=status):
                self.assertEqual(_health(_state(status)).runtime_warnings, [])

    def test_warnings_match_every_status(self):
        for state_status in RuntimeStateStatus:
            with self.subTest(state_status=state_status.value):
                _, _, expected_warnings = EXPECTED[state_status.value]
                self.assertEqual(
                    _health(_state(state_status.value)).runtime_warnings,
                    expected_warnings,
                )


# =====================================================================
# Determinism, non-mutation, provider independence, statelessness
# =====================================================================
class MonitorQualityTests(unittest.TestCase):
    def test_deterministic(self):
        state = _state("FAILED")
        monitor = RuntimeExecutionMonitor()
        self.assertEqual(
            monitor.create_health(state), monitor.create_health(state)
        )

    def test_independent_monitors_agree(self):
        state = _state("CANCELLED")
        self.assertEqual(
            RuntimeExecutionMonitor().create_health(state),
            RuntimeExecutionMonitor().create_health(state),
        )

    def test_ids_and_metadata_from_state(self):
        health = _health(_state("RUNNING"))
        self.assertEqual(health.runtime_id, "runtime-exec-x")
        self.assertEqual(health.execution_id, "exec-x")
        self.assertEqual(health.runtime_metadata["state_status"], "RUNNING")
        self.assertEqual(health.runtime_metadata["health_status"], "HEALTHY")

    def test_does_not_mutate_state(self):
        state = _state("CANCELLED")
        before = state.model_dump()
        _health(state)
        self.assertEqual(state.model_dump(), before)

    def test_plain_data_only(self):
        health = _health(_state("FAILED"))
        plain = (str, int, float, bool, type(None))
        for value in health.runtime_metadata.values():
            self.assertIsInstance(value, plain)
        for warning in health.runtime_warnings:
            self.assertIsInstance(warning, str)

    def test_stateless(self):
        self.assertEqual(vars(RuntimeExecutionMonitor()), {})

    def test_no_state_accumulates(self):
        monitor = RuntimeExecutionMonitor()
        monitor.create_health(_state())
        self.assertEqual(vars(monitor), {})


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class MonitorDependencyTests(unittest.TestCase):
    def test_get_monitor_returns_monitor(self):
        from app.core.dependencies import get_runtime_execution_monitor

        self.assertIsInstance(
            get_runtime_execution_monitor(), RuntimeExecutionMonitor
        )

    def test_get_monitor_is_stateless(self):
        from app.core.dependencies import get_runtime_execution_monitor

        self.assertEqual(vars(get_runtime_execution_monitor()), {})

    def test_injected_monitor_creates_health(self):
        from app.core.dependencies import get_runtime_execution_monitor

        health = get_runtime_execution_monitor().create_health(_state("FAILED"))
        self.assertIsInstance(health, RuntimeExecutionHealth)
        self.assertEqual(health.health_status, "FAILED")

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import RuntimeExecutionMonitorDep

        self.assertIsNotNone(RuntimeExecutionMonitorDep)

    def test_existing_dependencies_unchanged(self):
        from app.core.dependencies import get_runtime_execution_state_manager
        from app.services.runtime.runtime_execution_state_manager import (
            RuntimeExecutionStateManager,
        )

        self.assertIsInstance(
            get_runtime_execution_state_manager(), RuntimeExecutionStateManager
        )


# =====================================================================
# Regression: Sprint 14.10 state manager & Sprint 13 pipeline unchanged
# =====================================================================
class Sprint14RegressionTests(unittest.TestCase):
    def test_state_chain_still_works(self):
        # lifecycle manager -> state manager -> monitor compose cleanly.
        from app.core.dependencies import (
            get_execution_lifecycle_manager,
            get_runtime_execution_monitor,
            get_runtime_execution_state_manager,
        )
        from app.services.runtime.execution_event_models import (
            ExecutionEvent,
            ExecutionEventLog,
        )

        log = ExecutionEventLog(
            runtime_id="runtime-exec-x",
            execution_id="exec-x",
            event_status="FAILED",
            events=[
                ExecutionEvent(
                    event_id="event-1",
                    event_type="FAILED",
                    execution_id="exec-x",
                    runtime_id="runtime-exec-x",
                    event_sequence=1,
                )
            ],
            event_count=1,
            event_metadata={},
        )
        lifecycle = get_execution_lifecycle_manager().create_lifecycle(log)
        state = get_runtime_execution_state_manager().create_state(lifecycle)
        health = get_runtime_execution_monitor().create_health(state)
        self.assertEqual(health.health_status, "FAILED")
        self.assertEqual(health.health_score, 0)
        self.assertEqual(health.runtime_warnings, ["Execution failed"])

    def test_orchestration_pipeline_unchanged(self):
        from app.core.dependencies import get_execution_orchestration_engine
        from app.services.planning import PlanningRequest

        result = get_execution_orchestration_engine().create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertEqual(result.plan.goal, "Plan your trip")


if __name__ == "__main__":
    unittest.main()
