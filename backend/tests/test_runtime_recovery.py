"""Unit tests for the Sprint 14.13 Runtime Recovery Coordinator.

Covers the runtime recovery coordination layer end to end without touching any
network, SDK, AI, clock, UUID, capability, execution, retry, or database:

* the immutable :class:`RuntimeRecoveryState` DTO and the :class:`RecoveryStatus`
  / :class:`RecoveryStrategy` enums (defaults, immutability, required fields, enum
  values);
* the deterministic, stateless :class:`RuntimeRecoveryCoordinator` (every
  PauseResumeStatus mapping, recovery_required rules, strategy selection,
  deterministic descriptors, determinism, statelessness, non-mutation, provider
  independence);
* the composition-root wiring (``get_runtime_recovery_coordinator`` +
  ``RuntimeRecoveryCoordinatorDep``); and
* regression that the Sprint 14.12 pause/resume manager and Sprint 13 pipeline are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_runtime_recovery
"""

import unittest

from pydantic import ValidationError

from app.services.runtime.runtime_pause_resume_models import (
    PauseResumeStatus,
    RuntimePauseResumeState,
)
from app.services.runtime.runtime_recovery_coordinator import (
    RuntimeRecoveryCoordinator,
)
from app.services.runtime.runtime_recovery_models import (
    RecoveryStatus,
    RecoveryStrategy,
    RuntimeRecoveryState,
)


# Pause/resume status -> (recovery_status, recovery_strategy, recovery_required).
EXPECTED = {
    "RUNNING": ("NOT_REQUIRED", "NONE", False),
    "PAUSED": ("READY", "RESUME", True),
    "COMPLETED": ("NOT_REQUIRED", "NONE", False),
    "FAILED": ("FAILED", "MANUAL", True),
    "CANCELLED": ("READY", "RESTART", True),
}


# =====================================================================
# Helpers
# =====================================================================
def _pause_resume(
    pause_resume_status="RUNNING",
    runtime_id="runtime-exec-x",
    execution_id="exec-x",
):
    return RuntimePauseResumeState(
        runtime_id=runtime_id,
        execution_id=execution_id,
        pause_resume_status=pause_resume_status,
        can_pause=pause_resume_status == "RUNNING",
        can_resume=pause_resume_status == "PAUSED",
        requires_operator_action=pause_resume_status in ("FAILED", "CANCELLED"),
        pause_resume_metadata={},
    )


def _recovery(pause_resume=None):
    return RuntimeRecoveryCoordinator().create_recovery_state(
        pause_resume if pause_resume is not None else _pause_resume()
    )


def _model(**overrides):
    data = dict(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        recovery_status="READY",
        recovery_required=True,
        recovery_strategy="RESUME",
        recovery_metadata={},
    )
    data.update(overrides)
    return RuntimeRecoveryState(**data)


# =====================================================================
# DTOs
# =====================================================================
class RecoveryModelTests(unittest.TestCase):
    def test_defaults(self):
        state = RuntimeRecoveryState(
            runtime_id="r",
            execution_id="e",
            recovery_status="NOT_REQUIRED",
            recovery_required=False,
            recovery_strategy="NONE",
        )
        self.assertEqual(state.recovery_metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            RuntimeRecoveryState(runtime_id="r")  # rest missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _model().recovery_status = "FAILED"
        with self.assertRaises(ValidationError):
            _model().recovery_strategy = "MANUAL"

    def test_recovery_status_enum_values(self):
        self.assertEqual(
            {s.value for s in RecoveryStatus},
            {"NOT_REQUIRED", "READY", "RECOVERING", "FAILED"},
        )

    def test_recovery_strategy_enum_values(self):
        self.assertEqual(
            {s.value for s in RecoveryStrategy},
            {"NONE", "RESUME", "RESTART", "MANUAL"},
        )

    def test_produces_recovery_state(self):
        self.assertIsInstance(_recovery(), RuntimeRecoveryState)


# =====================================================================
# Status mapping — every PauseResumeStatus
# =====================================================================
class MappingTests(unittest.TestCase):
    def test_every_pause_resume_status_maps(self):
        for pause_resume_status in PauseResumeStatus:
            with self.subTest(pause_resume_status=pause_resume_status.value):
                state = _recovery(_pause_resume(pause_resume_status.value))
                expected_status, expected_strategy, _ = EXPECTED[
                    pause_resume_status.value
                ]
                self.assertEqual(state.recovery_status, expected_status)
                self.assertEqual(state.recovery_strategy, expected_strategy)

    def test_running_not_required(self):
        state = _recovery(_pause_resume("RUNNING"))
        self.assertEqual(state.recovery_status, "NOT_REQUIRED")
        self.assertEqual(state.recovery_strategy, "NONE")

    def test_paused_ready_resume(self):
        state = _recovery(_pause_resume("PAUSED"))
        self.assertEqual(state.recovery_status, "READY")
        self.assertEqual(state.recovery_strategy, "RESUME")

    def test_failed_manual(self):
        state = _recovery(_pause_resume("FAILED"))
        self.assertEqual(state.recovery_status, "FAILED")
        self.assertEqual(state.recovery_strategy, "MANUAL")

    def test_cancelled_restart(self):
        state = _recovery(_pause_resume("CANCELLED"))
        self.assertEqual(state.recovery_status, "READY")
        self.assertEqual(state.recovery_strategy, "RESTART")

    def test_recovering_is_never_derived(self):
        produced = {
            _recovery(_pause_resume(ps.value)).recovery_status
            for ps in PauseResumeStatus
        }
        self.assertNotIn("RECOVERING", produced)


# =====================================================================
# recovery_required & strategy selection rules
# =====================================================================
class RecoveryRuleTests(unittest.TestCase):
    def test_recovery_required_matches_every_status(self):
        for pause_resume_status in PauseResumeStatus:
            with self.subTest(pause_resume_status=pause_resume_status.value):
                state = _recovery(_pause_resume(pause_resume_status.value))
                _, _, expected_required = EXPECTED[pause_resume_status.value]
                self.assertEqual(state.recovery_required, expected_required)

    def test_required_only_for_ready_and_failed(self):
        # READY (PAUSED, CANCELLED) and FAILED -> required; others not.
        for status in ("PAUSED", "CANCELLED", "FAILED"):
            with self.subTest(status=status):
                self.assertTrue(_recovery(_pause_resume(status)).recovery_required)
        for status in ("RUNNING", "COMPLETED"):
            with self.subTest(status=status):
                self.assertFalse(
                    _recovery(_pause_resume(status)).recovery_required
                )

    def test_strategy_selection(self):
        strategies = {
            "RUNNING": "NONE",
            "PAUSED": "RESUME",
            "COMPLETED": "NONE",
            "FAILED": "MANUAL",
            "CANCELLED": "RESTART",
        }
        for status, strategy in strategies.items():
            with self.subTest(status=status):
                self.assertEqual(
                    _recovery(_pause_resume(status)).recovery_strategy, strategy
                )


# =====================================================================
# Metadata, determinism, non-mutation, provider independence, statelessness
# =====================================================================
class CoordinatorQualityTests(unittest.TestCase):
    def test_metadata_has_deterministic_descriptors(self):
        state = _recovery(_pause_resume("PAUSED"))
        self.assertEqual(
            state.recovery_metadata["pause_resume_status"], "PAUSED"
        )
        self.assertEqual(state.recovery_metadata["recovery_status"], "READY")
        self.assertEqual(state.recovery_metadata["recovery_strategy"], "RESUME")
        self.assertTrue(state.recovery_metadata["recovery_required"])

    def test_ids_from_pause_resume(self):
        state = _recovery(
            _pause_resume("RUNNING", runtime_id="runtime-abc", execution_id="exec-abc")
        )
        self.assertEqual(state.runtime_id, "runtime-abc")
        self.assertEqual(state.execution_id, "exec-abc")

    def test_deterministic(self):
        pause_resume = _pause_resume("PAUSED")
        coordinator = RuntimeRecoveryCoordinator()
        self.assertEqual(
            coordinator.create_recovery_state(pause_resume),
            coordinator.create_recovery_state(pause_resume),
        )

    def test_independent_coordinators_agree(self):
        pause_resume = _pause_resume("FAILED")
        self.assertEqual(
            RuntimeRecoveryCoordinator().create_recovery_state(pause_resume),
            RuntimeRecoveryCoordinator().create_recovery_state(pause_resume),
        )

    def test_does_not_mutate_pause_resume(self):
        pause_resume = _pause_resume("CANCELLED")
        before = pause_resume.model_dump()
        _recovery(pause_resume)
        self.assertEqual(pause_resume.model_dump(), before)

    def test_plain_data_only(self):
        state = _recovery(_pause_resume("FAILED"))
        plain = (str, int, float, bool, type(None))
        for value in state.recovery_metadata.values():
            self.assertIsInstance(value, plain)

    def test_stateless(self):
        self.assertEqual(vars(RuntimeRecoveryCoordinator()), {})

    def test_no_state_accumulates(self):
        coordinator = RuntimeRecoveryCoordinator()
        coordinator.create_recovery_state(_pause_resume())
        self.assertEqual(vars(coordinator), {})


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class RecoveryDependencyTests(unittest.TestCase):
    def test_get_coordinator_returns_coordinator(self):
        from app.core.dependencies import get_runtime_recovery_coordinator

        self.assertIsInstance(
            get_runtime_recovery_coordinator(), RuntimeRecoveryCoordinator
        )

    def test_get_coordinator_is_stateless(self):
        from app.core.dependencies import get_runtime_recovery_coordinator

        self.assertEqual(vars(get_runtime_recovery_coordinator()), {})

    def test_injected_coordinator_creates_state(self):
        from app.core.dependencies import get_runtime_recovery_coordinator

        state = get_runtime_recovery_coordinator().create_recovery_state(
            _pause_resume("PAUSED")
        )
        self.assertIsInstance(state, RuntimeRecoveryState)
        self.assertEqual(state.recovery_strategy, "RESUME")

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import RuntimeRecoveryCoordinatorDep

        self.assertIsNotNone(RuntimeRecoveryCoordinatorDep)

    def test_existing_dependencies_unchanged(self):
        from app.core.dependencies import get_runtime_pause_resume_manager
        from app.services.runtime.runtime_pause_resume_manager import (
            RuntimePauseResumeManager,
        )

        self.assertIsInstance(
            get_runtime_pause_resume_manager(), RuntimePauseResumeManager
        )


# =====================================================================
# Regression: Sprint 14.12 pause/resume manager & Sprint 13 pipeline unchanged
# =====================================================================
class Sprint14RegressionTests(unittest.TestCase):
    def test_pause_resume_chain_still_works(self):
        # monitor -> pause/resume manager -> recovery coordinator compose cleanly.
        from app.core.dependencies import (
            get_runtime_pause_resume_manager,
            get_runtime_recovery_coordinator,
        )
        from app.services.runtime.runtime_execution_monitor_models import (
            RuntimeExecutionHealth,
        )

        health = RuntimeExecutionHealth(
            runtime_id="runtime-exec-x",
            execution_id="exec-x",
            health_status="WARNING",
            health_score=75,
            runtime_warnings=["Execution cancelled"],
            runtime_metadata={},
        )
        pause_resume = get_runtime_pause_resume_manager().create_pause_resume_state(
            health
        )
        recovery = get_runtime_recovery_coordinator().create_recovery_state(
            pause_resume
        )
        self.assertEqual(recovery.recovery_status, "READY")
        self.assertEqual(recovery.recovery_strategy, "RESUME")
        self.assertTrue(recovery.recovery_required)

    def test_orchestration_pipeline_unchanged(self):
        from app.core.dependencies import get_execution_orchestration_engine
        from app.services.planning import PlanningRequest

        result = get_execution_orchestration_engine().create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertEqual(result.plan.goal, "Plan your trip")


if __name__ == "__main__":
    unittest.main()
