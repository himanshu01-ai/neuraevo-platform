"""Unit tests for the Sprint 14.7 Execution Controller.

Covers the runtime control layer end to end without touching any network, SDK,
AI, clock, UUID, capability, execution, or database:

* the immutable :class:`ExecutionControlState` DTO and the :class:`ControlStatus`
  enum (defaults, immutability, required fields, enum values);
* the deterministic, stateless :class:`ExecutionController` (every ProgressStatus
  mapping, the control permissions per status, deterministic descriptors,
  determinism, statelessness, non-mutation, provider independence);
* the composition-root wiring (``get_execution_controller`` +
  ``ExecutionControllerDep``); and
* regression that the Sprint 14.6 progress runtime and Sprint 13 pipeline are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_controller
"""

import unittest

from pydantic import ValidationError

from app.services.runtime.execution_controller import ExecutionController
from app.services.runtime.execution_controller_models import (
    ControlStatus,
    ExecutionControlState,
)
from app.services.runtime.execution_progress_models import (
    ExecutionProgress,
    ProgressStatus,
)


# Progress status -> expected control status (the mandated mapping).
EXPECTED_CONTROL = {
    "NOT_STARTED": "IDLE",
    "IN_PROGRESS": "RUNNING",
    "COMPLETED": "COMPLETED",
    "FAILED": "FAILED",
    "CANCELLED": "CANCELLED",
    "PARTIAL": "RUNNING",
}

# Control status -> (can_pause, can_resume, can_cancel, can_restart).
EXPECTED_PERMISSIONS = {
    "RUNNING": (True, False, True, False),
    "COMPLETED": (False, False, False, True),
    "FAILED": (False, False, False, True),
    "CANCELLED": (False, False, False, True),
    "IDLE": (False, False, False, False),
}


# =====================================================================
# Helpers
# =====================================================================
def _progress(
    status="IN_PROGRESS",
    percentage=50,
    runtime_id="runtime-exec-x",
    execution_id="exec-x",
):
    return ExecutionProgress(
        runtime_id=runtime_id,
        execution_id=execution_id,
        progress_status=status,
        total_execution_units=2,
        completed_execution_units=1,
        failed_execution_units=0,
        cancelled_execution_units=0,
        completion_percentage=percentage,
        progress_metadata={},
    )


def _control(progress=None):
    return ExecutionController().create_control_state(
        progress if progress is not None else _progress()
    )


def _state(**overrides):
    data = dict(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        control_status="RUNNING",
        can_pause=True,
        can_resume=False,
        can_cancel=True,
        can_restart=False,
        control_metadata={},
    )
    data.update(overrides)
    return ExecutionControlState(**data)


# =====================================================================
# DTOs
# =====================================================================
class ControlStateModelTests(unittest.TestCase):
    def test_defaults(self):
        state = ExecutionControlState(
            runtime_id="r",
            execution_id="e",
            control_status="IDLE",
            can_pause=False,
            can_resume=False,
            can_cancel=False,
            can_restart=False,
        )
        self.assertEqual(state.control_metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionControlState(runtime_id="r")  # rest missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _state().control_status = "PAUSED"
        with self.assertRaises(ValidationError):
            _state().can_pause = False

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in ControlStatus},
            {"RUNNING", "PAUSED", "CANCELLED", "COMPLETED", "FAILED", "IDLE"},
        )

    def test_produces_control_state(self):
        self.assertIsInstance(_control(), ExecutionControlState)


# =====================================================================
# State mapping — every ProgressStatus
# =====================================================================
class StateMappingTests(unittest.TestCase):
    def test_every_progress_status_maps(self):
        for progress_status in ProgressStatus:
            with self.subTest(progress_status=progress_status.value):
                state = _control(_progress(progress_status.value))
                self.assertEqual(
                    state.control_status,
                    EXPECTED_CONTROL[progress_status.value],
                )

    def test_not_started_is_idle(self):
        self.assertEqual(_control(_progress("NOT_STARTED")).control_status, "IDLE")

    def test_in_progress_is_running(self):
        self.assertEqual(_control(_progress("IN_PROGRESS")).control_status, "RUNNING")

    def test_partial_is_running(self):
        self.assertEqual(_control(_progress("PARTIAL")).control_status, "RUNNING")

    def test_terminal_states_map_directly(self):
        for status in ("COMPLETED", "FAILED", "CANCELLED"):
            with self.subTest(status=status):
                self.assertEqual(_control(_progress(status)).control_status, status)

    def test_paused_is_never_derived_from_progress(self):
        produced = {
            _control(_progress(ps.value)).control_status for ps in ProgressStatus
        }
        self.assertNotIn("PAUSED", produced)


# =====================================================================
# Control permissions
# =====================================================================
class ControlPermissionTests(unittest.TestCase):
    def _perms(self, state):
        return (
            state.can_pause,
            state.can_resume,
            state.can_cancel,
            state.can_restart,
        )

    def test_permissions_match_control_status(self):
        for progress_status, control_status in EXPECTED_CONTROL.items():
            with self.subTest(progress_status=progress_status):
                state = _control(_progress(progress_status))
                self.assertEqual(
                    self._perms(state), EXPECTED_PERMISSIONS[control_status]
                )

    def test_running_can_pause_and_cancel(self):
        state = _control(_progress("IN_PROGRESS"))
        self.assertTrue(state.can_pause)
        self.assertTrue(state.can_cancel)
        self.assertFalse(state.can_resume)
        self.assertFalse(state.can_restart)

    def test_terminal_can_only_restart(self):
        for status in ("COMPLETED", "FAILED", "CANCELLED"):
            with self.subTest(status=status):
                state = _control(_progress(status))
                self.assertEqual(
                    self._perms(state), (False, False, False, True)
                )

    def test_idle_allows_nothing(self):
        state = _control(_progress("NOT_STARTED"))
        self.assertEqual(self._perms(state), (False, False, False, False))


# =====================================================================
# Metadata, determinism, non-mutation, provider independence
# =====================================================================
class ControllerQualityTests(unittest.TestCase):
    def test_metadata_has_deterministic_descriptors(self):
        state = _control(_progress("COMPLETED", percentage=100))
        self.assertEqual(state.control_metadata["progress_status"], "COMPLETED")
        self.assertEqual(state.control_metadata["control_status"], "COMPLETED")
        self.assertTrue(state.control_metadata["is_terminal"])
        self.assertFalse(state.control_metadata["is_active"])
        self.assertEqual(state.control_metadata["completion_percentage"], 100)

    def test_ids_come_from_progress(self):
        state = _control(
            _progress(runtime_id="runtime-abc", execution_id="exec-abc")
        )
        self.assertEqual(state.runtime_id, "runtime-abc")
        self.assertEqual(state.execution_id, "exec-abc")

    def test_deterministic(self):
        progress = _progress("PARTIAL")
        controller = ExecutionController()
        self.assertEqual(
            controller.create_control_state(progress),
            controller.create_control_state(progress),
        )

    def test_independent_controllers_agree(self):
        progress = _progress("IN_PROGRESS")
        self.assertEqual(
            ExecutionController().create_control_state(progress),
            ExecutionController().create_control_state(progress),
        )

    def test_does_not_mutate_progress(self):
        progress = _progress("IN_PROGRESS")
        before = progress.model_dump()
        _control(progress)
        self.assertEqual(progress.model_dump(), before)

    def test_plain_data_only(self):
        state = _control(_progress("IN_PROGRESS"))
        plain = (str, int, float, bool, type(None))
        for value in state.control_metadata.values():
            self.assertIsInstance(value, plain)


# =====================================================================
# Statelessness
# =====================================================================
class StatelessTests(unittest.TestCase):
    def test_stateless(self):
        self.assertEqual(vars(ExecutionController()), {})

    def test_no_state_accumulates(self):
        controller = ExecutionController()
        controller.create_control_state(_progress())
        self.assertEqual(vars(controller), {})


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class ControllerDependencyTests(unittest.TestCase):
    def test_get_controller_returns_controller(self):
        from app.core.dependencies import get_execution_controller

        self.assertIsInstance(get_execution_controller(), ExecutionController)

    def test_get_controller_is_stateless(self):
        from app.core.dependencies import get_execution_controller

        self.assertEqual(vars(get_execution_controller()), {})

    def test_injected_controller_creates_state(self):
        from app.core.dependencies import get_execution_controller

        state = get_execution_controller().create_control_state(
            _progress("IN_PROGRESS")
        )
        self.assertIsInstance(state, ExecutionControlState)
        self.assertEqual(state.control_status, "RUNNING")

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import ExecutionControllerDep

        self.assertIsNotNone(ExecutionControllerDep)

    def test_existing_dependencies_unchanged(self):
        from app.core.dependencies import get_execution_progress_runtime
        from app.services.runtime.execution_progress_runtime import (
            ExecutionProgressRuntime,
        )

        self.assertIsInstance(
            get_execution_progress_runtime(), ExecutionProgressRuntime
        )


# =====================================================================
# Regression: Sprint 14.6 progress runtime & Sprint 13 pipeline unchanged
# =====================================================================
class Sprint14RegressionTests(unittest.TestCase):
    def test_progress_runtime_still_works(self):
        from app.core.dependencies import get_execution_progress_runtime
        from app.services.runtime.capability_executor_models import (
            CapabilityExecutionSummary,
        )

        summary = CapabilityExecutionSummary(
            runtime_id="runtime-exec-x",
            execution_id="exec-x",
            execution_status="COMPLETED",
            completed_execution_units=[],
            failed_execution_units=[],
            cancelled_execution_units=[],
            execution_results=[],
            execution_metadata={},
        )
        progress = get_execution_progress_runtime().create_progress(summary)
        self.assertEqual(progress.progress_status, "NOT_STARTED")

    def test_orchestration_pipeline_unchanged(self):
        from app.core.dependencies import get_execution_orchestration_engine
        from app.services.planning import PlanningRequest

        result = get_execution_orchestration_engine().create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertEqual(result.plan.goal, "Plan your trip")


if __name__ == "__main__":
    unittest.main()
