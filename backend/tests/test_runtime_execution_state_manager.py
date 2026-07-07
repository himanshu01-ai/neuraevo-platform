"""Unit tests for the Sprint 14.10 Runtime Execution State Manager.

Covers the runtime state layer end to end without touching any network, SDK, AI,
clock, UUID, capability, execution, or database:

* the immutable :class:`RuntimeExecutionState` DTO and the
  :class:`RuntimeStateStatus` enum (defaults, immutability, required fields, enum
  values);
* the deterministic, stateless :class:`RuntimeExecutionStateManager` (every
  LifecycleStatus mapping, current-stage preservation, active/terminal detection,
  default lifecycle, determinism, statelessness, non-mutation, provider
  independence);
* the composition-root wiring (``get_runtime_execution_state_manager`` +
  ``RuntimeExecutionStateManagerDep``); and
* regression that the Sprint 14.9 lifecycle manager and Sprint 13 pipeline are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_runtime_execution_state_manager
"""

import unittest

from pydantic import ValidationError

from app.services.runtime.execution_lifecycle_models import (
    LifecycleStatus,
    RuntimeExecutionLifecycle,
)
from app.services.runtime.runtime_execution_state_manager import (
    RuntimeExecutionStateManager,
)
from app.services.runtime.runtime_execution_state_models import (
    RuntimeExecutionState,
    RuntimeStateStatus,
)


# Lifecycle status -> expected runtime state status (a 1:1 identity mapping).
EXPECTED_STATE = {
    "INITIALIZED": "INITIALIZED",
    "RUNNING": "RUNNING",
    "COMPLETED": "COMPLETED",
    "FAILED": "FAILED",
    "CANCELLED": "CANCELLED",
}
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}


# =====================================================================
# Helpers
# =====================================================================
def _lifecycle(
    lifecycle_status="RUNNING",
    current_stage=None,
    runtime_id="runtime-exec-x",
    execution_id="exec-x",
):
    return RuntimeExecutionLifecycle(
        runtime_id=runtime_id,
        execution_id=execution_id,
        lifecycle_status=lifecycle_status,
        lifecycle_events=[],
        current_stage=(
            current_stage if current_stage is not None else lifecycle_status
        ),
        is_terminal=lifecycle_status in TERMINAL_STATUSES,
        lifecycle_metadata={},
    )


def _state(lifecycle=None):
    return RuntimeExecutionStateManager().create_state(
        lifecycle if lifecycle is not None else _lifecycle()
    )


def _model(**overrides):
    data = dict(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        state_status="RUNNING",
        current_stage="ACTIVE",
        is_active=True,
        is_terminal=False,
        runtime_metadata={},
    )
    data.update(overrides)
    return RuntimeExecutionState(**data)


# =====================================================================
# DTOs
# =====================================================================
class RuntimeStateModelTests(unittest.TestCase):
    def test_defaults(self):
        state = RuntimeExecutionState(
            runtime_id="r",
            execution_id="e",
            state_status="INITIALIZED",
            current_stage="INITIALIZED",
            is_active=False,
            is_terminal=False,
        )
        self.assertEqual(state.runtime_metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            RuntimeExecutionState(runtime_id="r")  # rest missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _model().state_status = "COMPLETED"
        with self.assertRaises(ValidationError):
            _model().is_active = False

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in RuntimeStateStatus},
            {"INITIALIZED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"},
        )

    def test_produces_state(self):
        self.assertIsInstance(_state(), RuntimeExecutionState)


# =====================================================================
# Status mapping — every LifecycleStatus
# =====================================================================
class StateMappingTests(unittest.TestCase):
    def test_every_lifecycle_status_maps(self):
        for lifecycle_status in LifecycleStatus:
            with self.subTest(lifecycle_status=lifecycle_status.value):
                state = _state(_lifecycle(lifecycle_status.value))
                self.assertEqual(
                    state.state_status, EXPECTED_STATE[lifecycle_status.value]
                )

    def test_initialized_maps(self):
        self.assertEqual(_state(_lifecycle("INITIALIZED")).state_status, "INITIALIZED")

    def test_running_maps(self):
        self.assertEqual(_state(_lifecycle("RUNNING")).state_status, "RUNNING")

    def test_terminal_states_map_directly(self):
        for status in ("COMPLETED", "FAILED", "CANCELLED"):
            with self.subTest(status=status):
                self.assertEqual(_state(_lifecycle(status)).state_status, status)


# =====================================================================
# Current stage preservation
# =====================================================================
class CurrentStageTests(unittest.TestCase):
    def test_current_stage_copied_directly(self):
        # The stage is copied verbatim, not derived from the state status.
        state = _state(_lifecycle("RUNNING", current_stage="ACTIVE"))
        self.assertEqual(state.current_stage, "ACTIVE")

    def test_arbitrary_stage_preserved(self):
        state = _state(_lifecycle("COMPLETED", current_stage="SOME_STAGE"))
        self.assertEqual(state.current_stage, "SOME_STAGE")


# =====================================================================
# Active & terminal detection
# =====================================================================
class ActiveTerminalTests(unittest.TestCase):
    def test_active_only_for_running(self):
        self.assertTrue(_state(_lifecycle("RUNNING")).is_active)
        for status in ("INITIALIZED", "COMPLETED", "FAILED", "CANCELLED"):
            with self.subTest(status=status):
                self.assertFalse(_state(_lifecycle(status)).is_active)

    def test_terminal_only_for_terminal_statuses(self):
        for status in ("COMPLETED", "FAILED", "CANCELLED"):
            with self.subTest(status=status):
                self.assertTrue(_state(_lifecycle(status)).is_terminal)
        for status in ("INITIALIZED", "RUNNING"):
            with self.subTest(status=status):
                self.assertFalse(_state(_lifecycle(status)).is_terminal)

    def test_running_is_active_not_terminal(self):
        state = _state(_lifecycle("RUNNING"))
        self.assertTrue(state.is_active)
        self.assertFalse(state.is_terminal)

    def test_completed_is_terminal_not_active(self):
        state = _state(_lifecycle("COMPLETED"))
        self.assertFalse(state.is_active)
        self.assertTrue(state.is_terminal)


# =====================================================================
# Default lifecycle, determinism, non-mutation, provider independence
# =====================================================================
class StateQualityTests(unittest.TestCase):
    def test_default_lifecycle(self):
        # A minimal (default) INITIALIZED lifecycle -> idle, non-active state.
        state = _state(_lifecycle("INITIALIZED", current_stage="INITIALIZED"))
        self.assertEqual(state.state_status, "INITIALIZED")
        self.assertFalse(state.is_active)
        self.assertFalse(state.is_terminal)

    def test_deterministic(self):
        lifecycle = _lifecycle("RUNNING")
        manager = RuntimeExecutionStateManager()
        self.assertEqual(
            manager.create_state(lifecycle), manager.create_state(lifecycle)
        )

    def test_independent_managers_agree(self):
        lifecycle = _lifecycle("COMPLETED")
        self.assertEqual(
            RuntimeExecutionStateManager().create_state(lifecycle),
            RuntimeExecutionStateManager().create_state(lifecycle),
        )

    def test_ids_and_metadata_from_lifecycle(self):
        state = _state(_lifecycle("RUNNING"))
        self.assertEqual(state.runtime_id, "runtime-exec-x")
        self.assertEqual(state.execution_id, "exec-x")
        self.assertEqual(state.runtime_metadata["lifecycle_status"], "RUNNING")
        self.assertEqual(state.runtime_metadata["state_status"], "RUNNING")

    def test_does_not_mutate_lifecycle(self):
        lifecycle = _lifecycle("RUNNING", current_stage="ACTIVE")
        before = lifecycle.model_dump()
        _state(lifecycle)
        self.assertEqual(lifecycle.model_dump(), before)

    def test_plain_data_only(self):
        state = _state(_lifecycle("RUNNING"))
        plain = (str, int, float, bool, type(None))
        for value in state.runtime_metadata.values():
            self.assertIsInstance(value, plain)

    def test_stateless(self):
        self.assertEqual(vars(RuntimeExecutionStateManager()), {})

    def test_no_state_accumulates(self):
        manager = RuntimeExecutionStateManager()
        manager.create_state(_lifecycle())
        self.assertEqual(vars(manager), {})


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class StateManagerDependencyTests(unittest.TestCase):
    def test_get_manager_returns_manager(self):
        from app.core.dependencies import get_runtime_execution_state_manager

        self.assertIsInstance(
            get_runtime_execution_state_manager(), RuntimeExecutionStateManager
        )

    def test_get_manager_is_stateless(self):
        from app.core.dependencies import get_runtime_execution_state_manager

        self.assertEqual(vars(get_runtime_execution_state_manager()), {})

    def test_injected_manager_creates_state(self):
        from app.core.dependencies import get_runtime_execution_state_manager

        state = get_runtime_execution_state_manager().create_state(
            _lifecycle("RUNNING")
        )
        self.assertIsInstance(state, RuntimeExecutionState)
        self.assertEqual(state.state_status, "RUNNING")

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import RuntimeExecutionStateManagerDep

        self.assertIsNotNone(RuntimeExecutionStateManagerDep)

    def test_existing_dependencies_unchanged(self):
        from app.core.dependencies import get_execution_lifecycle_manager
        from app.services.runtime.execution_lifecycle_manager import (
            ExecutionLifecycleManager,
        )

        self.assertIsInstance(
            get_execution_lifecycle_manager(), ExecutionLifecycleManager
        )


# =====================================================================
# Regression: Sprint 14.9 lifecycle manager & Sprint 13 pipeline unchanged
# =====================================================================
class Sprint14RegressionTests(unittest.TestCase):
    def test_lifecycle_chain_still_works(self):
        # event manager -> lifecycle manager -> state manager compose cleanly.
        from app.core.dependencies import (
            get_execution_event_manager,
            get_execution_lifecycle_manager,
            get_runtime_execution_state_manager,
        )
        from app.services.runtime.execution_controller_models import (
            ExecutionControlState,
        )

        control_state = ExecutionControlState(
            runtime_id="runtime-exec-x",
            execution_id="exec-x",
            control_status="COMPLETED",
            can_pause=False,
            can_resume=False,
            can_cancel=False,
            can_restart=True,
            control_metadata={},
        )
        log = get_execution_event_manager().create_event_log(control_state)
        lifecycle = get_execution_lifecycle_manager().create_lifecycle(log)
        state = get_runtime_execution_state_manager().create_state(lifecycle)
        self.assertEqual(state.state_status, "COMPLETED")
        self.assertTrue(state.is_terminal)
        self.assertFalse(state.is_active)

    def test_orchestration_pipeline_unchanged(self):
        from app.core.dependencies import get_execution_orchestration_engine
        from app.services.planning import PlanningRequest

        result = get_execution_orchestration_engine().create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertEqual(result.plan.goal, "Plan your trip")


if __name__ == "__main__":
    unittest.main()
