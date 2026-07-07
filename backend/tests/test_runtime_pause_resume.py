"""Unit tests for the Sprint 14.12 Runtime Pause/Resume Manager.

Covers the runtime pause/resume coordination layer end to end without touching any
network, SDK, AI, clock, UUID, capability, execution, thread/process pausing, or
database:

* the immutable :class:`RuntimePauseResumeState` DTO and the
  :class:`PauseResumeStatus` enum (defaults, immutability, required fields, enum
  values);
* the deterministic, stateless :class:`RuntimePauseResumeManager` (every
  RuntimeHealthStatus mapping, can_pause/can_resume/requires_operator_action
  rules, deterministic descriptors, determinism, statelessness, non-mutation,
  provider independence);
* the composition-root wiring (``get_runtime_pause_resume_manager`` +
  ``RuntimePauseResumeManagerDep``); and
* regression that the Sprint 14.11 monitor and Sprint 13 pipeline are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_runtime_pause_resume
"""

import unittest

from pydantic import ValidationError

from app.services.runtime.runtime_execution_monitor_models import (
    RuntimeExecutionHealth,
    RuntimeHealthStatus,
)
from app.services.runtime.runtime_pause_resume_manager import (
    RuntimePauseResumeManager,
)
from app.services.runtime.runtime_pause_resume_models import (
    PauseResumeStatus,
    RuntimePauseResumeState,
)


# Health status -> (pause_resume_status, can_pause, can_resume, operator_action).
EXPECTED = {
    "HEALTHY": ("RUNNING", True, False, False),
    "WARNING": ("PAUSED", False, True, False),
    "COMPLETED": ("COMPLETED", False, False, False),
    "FAILED": ("FAILED", False, False, True),
}


# =====================================================================
# Helpers
# =====================================================================
def _health(
    health_status="HEALTHY",
    score=100,
    runtime_id="runtime-exec-x",
    execution_id="exec-x",
):
    return RuntimeExecutionHealth(
        runtime_id=runtime_id,
        execution_id=execution_id,
        health_status=health_status,
        health_score=score,
        runtime_warnings=[],
        runtime_metadata={},
    )


def _pr(health=None):
    return RuntimePauseResumeManager().create_pause_resume_state(
        health if health is not None else _health()
    )


def _model(**overrides):
    data = dict(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        pause_resume_status="RUNNING",
        can_pause=True,
        can_resume=False,
        requires_operator_action=False,
        pause_resume_metadata={},
    )
    data.update(overrides)
    return RuntimePauseResumeState(**data)


# =====================================================================
# DTOs
# =====================================================================
class PauseResumeModelTests(unittest.TestCase):
    def test_defaults(self):
        state = RuntimePauseResumeState(
            runtime_id="r",
            execution_id="e",
            pause_resume_status="RUNNING",
            can_pause=True,
            can_resume=False,
            requires_operator_action=False,
        )
        self.assertEqual(state.pause_resume_metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            RuntimePauseResumeState(runtime_id="r")  # rest missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _model().pause_resume_status = "PAUSED"
        with self.assertRaises(ValidationError):
            _model().can_pause = False

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in PauseResumeStatus},
            {"RUNNING", "PAUSED", "COMPLETED", "FAILED", "CANCELLED"},
        )

    def test_produces_state(self):
        self.assertIsInstance(_pr(), RuntimePauseResumeState)


# =====================================================================
# Status mapping — every RuntimeHealthStatus
# =====================================================================
class MappingTests(unittest.TestCase):
    def test_every_health_status_maps(self):
        for health_status in RuntimeHealthStatus:
            with self.subTest(health_status=health_status.value):
                state = _pr(_health(health_status.value))
                expected_status, _, _, _ = EXPECTED[health_status.value]
                self.assertEqual(state.pause_resume_status, expected_status)

    def test_healthy_is_running(self):
        self.assertEqual(_pr(_health("HEALTHY")).pause_resume_status, "RUNNING")

    def test_warning_is_paused(self):
        self.assertEqual(_pr(_health("WARNING")).pause_resume_status, "PAUSED")

    def test_completed_is_completed(self):
        self.assertEqual(
            _pr(_health("COMPLETED")).pause_resume_status, "COMPLETED"
        )

    def test_failed_is_failed(self):
        self.assertEqual(_pr(_health("FAILED")).pause_resume_status, "FAILED")

    def test_cancelled_is_never_derived_from_health(self):
        produced = {
            _pr(_health(hs.value)).pause_resume_status
            for hs in RuntimeHealthStatus
        }
        self.assertNotIn("CANCELLED", produced)


# =====================================================================
# can_pause / can_resume / requires_operator_action rules
# =====================================================================
class CapabilityRuleTests(unittest.TestCase):
    def _flags(self, state):
        return (
            state.can_pause,
            state.can_resume,
            state.requires_operator_action,
        )

    def test_flags_match_every_status(self):
        for health_status in RuntimeHealthStatus:
            with self.subTest(health_status=health_status.value):
                state = _pr(_health(health_status.value))
                _, can_pause, can_resume, operator = EXPECTED[
                    health_status.value
                ]
                self.assertEqual(
                    self._flags(state), (can_pause, can_resume, operator)
                )

    def test_can_pause_only_for_running(self):
        self.assertTrue(_pr(_health("HEALTHY")).can_pause)
        for status in ("WARNING", "COMPLETED", "FAILED"):
            with self.subTest(status=status):
                self.assertFalse(_pr(_health(status)).can_pause)

    def test_can_resume_only_for_paused(self):
        self.assertTrue(_pr(_health("WARNING")).can_resume)
        for status in ("HEALTHY", "COMPLETED", "FAILED"):
            with self.subTest(status=status):
                self.assertFalse(_pr(_health(status)).can_resume)

    def test_operator_action_only_for_failed(self):
        self.assertTrue(_pr(_health("FAILED")).requires_operator_action)
        for status in ("HEALTHY", "WARNING", "COMPLETED"):
            with self.subTest(status=status):
                self.assertFalse(
                    _pr(_health(status)).requires_operator_action
                )


# =====================================================================
# Metadata, determinism, non-mutation, provider independence, statelessness
# =====================================================================
class ManagerQualityTests(unittest.TestCase):
    def test_metadata_has_deterministic_descriptors(self):
        state = _pr(_health("WARNING", score=75))
        self.assertEqual(state.pause_resume_metadata["health_status"], "WARNING")
        self.assertEqual(
            state.pause_resume_metadata["pause_resume_status"], "PAUSED"
        )
        self.assertTrue(state.pause_resume_metadata["can_resume"])
        self.assertEqual(state.pause_resume_metadata["health_score"], 75)

    def test_ids_from_health(self):
        state = _pr(
            _health("HEALTHY", runtime_id="runtime-abc", execution_id="exec-abc")
        )
        self.assertEqual(state.runtime_id, "runtime-abc")
        self.assertEqual(state.execution_id, "exec-abc")

    def test_deterministic(self):
        health = _health("WARNING")
        manager = RuntimePauseResumeManager()
        self.assertEqual(
            manager.create_pause_resume_state(health),
            manager.create_pause_resume_state(health),
        )

    def test_independent_managers_agree(self):
        health = _health("FAILED")
        self.assertEqual(
            RuntimePauseResumeManager().create_pause_resume_state(health),
            RuntimePauseResumeManager().create_pause_resume_state(health),
        )

    def test_does_not_mutate_health(self):
        health = _health("WARNING")
        before = health.model_dump()
        _pr(health)
        self.assertEqual(health.model_dump(), before)

    def test_plain_data_only(self):
        state = _pr(_health("FAILED"))
        plain = (str, int, float, bool, type(None))
        for value in state.pause_resume_metadata.values():
            self.assertIsInstance(value, plain)

    def test_stateless(self):
        self.assertEqual(vars(RuntimePauseResumeManager()), {})

    def test_no_state_accumulates(self):
        manager = RuntimePauseResumeManager()
        manager.create_pause_resume_state(_health())
        self.assertEqual(vars(manager), {})


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class PauseResumeDependencyTests(unittest.TestCase):
    def test_get_manager_returns_manager(self):
        from app.core.dependencies import get_runtime_pause_resume_manager

        self.assertIsInstance(
            get_runtime_pause_resume_manager(), RuntimePauseResumeManager
        )

    def test_get_manager_is_stateless(self):
        from app.core.dependencies import get_runtime_pause_resume_manager

        self.assertEqual(vars(get_runtime_pause_resume_manager()), {})

    def test_injected_manager_creates_state(self):
        from app.core.dependencies import get_runtime_pause_resume_manager

        state = get_runtime_pause_resume_manager().create_pause_resume_state(
            _health("WARNING")
        )
        self.assertIsInstance(state, RuntimePauseResumeState)
        self.assertEqual(state.pause_resume_status, "PAUSED")

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import RuntimePauseResumeManagerDep

        self.assertIsNotNone(RuntimePauseResumeManagerDep)

    def test_existing_dependencies_unchanged(self):
        from app.core.dependencies import get_runtime_execution_monitor
        from app.services.runtime.runtime_execution_monitor import (
            RuntimeExecutionMonitor,
        )

        self.assertIsInstance(
            get_runtime_execution_monitor(), RuntimeExecutionMonitor
        )


# =====================================================================
# Regression: Sprint 14.11 monitor & Sprint 13 pipeline unchanged
# =====================================================================
class Sprint14RegressionTests(unittest.TestCase):
    def test_monitor_chain_still_works(self):
        # state manager -> monitor -> pause/resume manager compose cleanly.
        from app.core.dependencies import (
            get_runtime_execution_monitor,
            get_runtime_pause_resume_manager,
        )
        from app.services.runtime.runtime_execution_state_models import (
            RuntimeExecutionState,
        )

        state = RuntimeExecutionState(
            runtime_id="runtime-exec-x",
            execution_id="exec-x",
            state_status="RUNNING",
            current_stage="ACTIVE",
            is_active=True,
            is_terminal=False,
            runtime_metadata={},
        )
        health = get_runtime_execution_monitor().create_health(state)
        pause_resume = get_runtime_pause_resume_manager().create_pause_resume_state(
            health
        )
        self.assertEqual(pause_resume.pause_resume_status, "RUNNING")
        self.assertTrue(pause_resume.can_pause)

    def test_orchestration_pipeline_unchanged(self):
        from app.core.dependencies import get_execution_orchestration_engine
        from app.services.planning import PlanningRequest

        result = get_execution_orchestration_engine().create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertEqual(result.plan.goal, "Plan your trip")


if __name__ == "__main__":
    unittest.main()
