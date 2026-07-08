"""Unit tests for the Sprint 14.14 Runtime Resource Coordinator.

Covers the runtime resource readiness layer end to end without touching any
network, SDK, AI, clock, UUID, capability, allocation, reservation, execution, or
database:

* the immutable :class:`RuntimeResourceState` DTO and the :class:`ResourceStatus`
  enum (defaults, immutability, required fields, enum values);
* the deterministic, stateless :class:`RuntimeResourceCoordinator` (every
  RecoveryStatus mapping, resources_ready rules, empty required_resources,
  deterministic descriptors, determinism, statelessness, non-mutation, provider
  independence);
* the composition-root wiring (``get_runtime_resource_coordinator`` +
  ``RuntimeResourceCoordinatorDep``); and
* regression that the Sprint 14.13 recovery coordinator and Sprint 13 pipeline are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_runtime_resource
"""

import unittest

from pydantic import ValidationError

from app.services.runtime.runtime_recovery_models import (
    RecoveryStatus,
    RuntimeRecoveryState,
)
from app.services.runtime.runtime_resource_coordinator import (
    RuntimeResourceCoordinator,
)
from app.services.runtime.runtime_resource_models import (
    ResourceStatus,
    RuntimeResourceState,
)


# Recovery status -> (resource_status, resources_ready).
EXPECTED = {
    "NOT_REQUIRED": ("READY", True),
    "READY": ("WAITING", False),
    "RECOVERING": ("BLOCKED", False),
    "FAILED": ("BLOCKED", False),
}


# =====================================================================
# Helpers
# =====================================================================
def _recovery(
    recovery_status="NOT_REQUIRED",
    runtime_id="runtime-exec-x",
    execution_id="exec-x",
):
    return RuntimeRecoveryState(
        runtime_id=runtime_id,
        execution_id=execution_id,
        recovery_status=recovery_status,
        recovery_required=recovery_status in ("READY", "FAILED"),
        recovery_strategy="NONE",
        recovery_metadata={},
    )


def _resource(recovery=None):
    return RuntimeResourceCoordinator().create_resource_state(
        recovery if recovery is not None else _recovery()
    )


def _model(**overrides):
    data = dict(
        runtime_id="runtime-exec-x",
        execution_id="exec-x",
        resource_status="READY",
        resources_ready=True,
        required_resources=(),
        resource_metadata={},
    )
    data.update(overrides)
    return RuntimeResourceState(**data)


# =====================================================================
# DTOs
# =====================================================================
class ResourceModelTests(unittest.TestCase):
    def test_defaults(self):
        state = RuntimeResourceState(
            runtime_id="r",
            execution_id="e",
            resource_status="READY",
            resources_ready=True,
        )
        self.assertEqual(state.required_resources, ())
        self.assertEqual(state.resource_metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            RuntimeResourceState(runtime_id="r")  # rest missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _model().resource_status = "WAITING"
        with self.assertRaises(ValidationError):
            _model().resources_ready = False

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in ResourceStatus},
            {"READY", "WAITING", "BLOCKED", "COMPLETED"},
        )

    def test_produces_resource_state(self):
        self.assertIsInstance(_resource(), RuntimeResourceState)


# =====================================================================
# Status mapping — every RecoveryStatus
# =====================================================================
class MappingTests(unittest.TestCase):
    def test_every_recovery_status_maps(self):
        for recovery_status in RecoveryStatus:
            with self.subTest(recovery_status=recovery_status.value):
                state = _resource(_recovery(recovery_status.value))
                expected_status, _ = EXPECTED[recovery_status.value]
                self.assertEqual(state.resource_status, expected_status)

    def test_not_required_is_ready(self):
        self.assertEqual(
            _resource(_recovery("NOT_REQUIRED")).resource_status, "READY"
        )

    def test_ready_is_waiting(self):
        self.assertEqual(
            _resource(_recovery("READY")).resource_status, "WAITING"
        )

    def test_recovering_is_blocked(self):
        self.assertEqual(
            _resource(_recovery("RECOVERING")).resource_status, "BLOCKED"
        )

    def test_failed_is_blocked(self):
        self.assertEqual(
            _resource(_recovery("FAILED")).resource_status, "BLOCKED"
        )

    def test_completed_is_never_derived(self):
        produced = {
            _resource(_recovery(rs.value)).resource_status
            for rs in RecoveryStatus
        }
        self.assertNotIn("COMPLETED", produced)


# =====================================================================
# resources_ready & required_resources rules
# =====================================================================
class ResourceRuleTests(unittest.TestCase):
    def test_resources_ready_matches_every_status(self):
        for recovery_status in RecoveryStatus:
            with self.subTest(recovery_status=recovery_status.value):
                state = _resource(_recovery(recovery_status.value))
                _, expected_ready = EXPECTED[recovery_status.value]
                self.assertEqual(state.resources_ready, expected_ready)

    def test_ready_only_for_not_required(self):
        self.assertTrue(_resource(_recovery("NOT_REQUIRED")).resources_ready)
        for status in ("READY", "RECOVERING", "FAILED"):
            with self.subTest(status=status):
                self.assertFalse(_resource(_recovery(status)).resources_ready)

    def test_required_resources_always_empty(self):
        for recovery_status in RecoveryStatus:
            with self.subTest(recovery_status=recovery_status.value):
                state = _resource(_recovery(recovery_status.value))
                self.assertEqual(state.required_resources, ())
                self.assertIsInstance(state.required_resources, tuple)


# =====================================================================
# Metadata, determinism, non-mutation, provider independence, statelessness
# =====================================================================
class CoordinatorQualityTests(unittest.TestCase):
    def test_metadata_has_deterministic_descriptors(self):
        state = _resource(_recovery("NOT_REQUIRED"))
        self.assertEqual(
            state.resource_metadata["recovery_status"], "NOT_REQUIRED"
        )
        self.assertEqual(state.resource_metadata["resource_status"], "READY")
        self.assertTrue(state.resource_metadata["resources_ready"])
        self.assertEqual(state.resource_metadata["required_resource_count"], 0)

    def test_ids_from_recovery(self):
        state = _resource(
            _recovery("NOT_REQUIRED", runtime_id="runtime-abc", execution_id="exec-abc")
        )
        self.assertEqual(state.runtime_id, "runtime-abc")
        self.assertEqual(state.execution_id, "exec-abc")

    def test_deterministic(self):
        recovery = _recovery("READY")
        coordinator = RuntimeResourceCoordinator()
        self.assertEqual(
            coordinator.create_resource_state(recovery),
            coordinator.create_resource_state(recovery),
        )

    def test_independent_coordinators_agree(self):
        recovery = _recovery("FAILED")
        self.assertEqual(
            RuntimeResourceCoordinator().create_resource_state(recovery),
            RuntimeResourceCoordinator().create_resource_state(recovery),
        )

    def test_does_not_mutate_recovery(self):
        recovery = _recovery("FAILED")
        before = recovery.model_dump()
        _resource(recovery)
        self.assertEqual(recovery.model_dump(), before)

    def test_plain_data_only(self):
        state = _resource(_recovery("FAILED"))
        plain = (str, int, float, bool, type(None))
        for value in state.resource_metadata.values():
            self.assertIsInstance(value, plain)

    def test_stateless(self):
        self.assertEqual(vars(RuntimeResourceCoordinator()), {})

    def test_no_state_accumulates(self):
        coordinator = RuntimeResourceCoordinator()
        coordinator.create_resource_state(_recovery())
        self.assertEqual(vars(coordinator), {})


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class ResourceDependencyTests(unittest.TestCase):
    def test_get_coordinator_returns_coordinator(self):
        from app.core.dependencies import get_runtime_resource_coordinator

        self.assertIsInstance(
            get_runtime_resource_coordinator(), RuntimeResourceCoordinator
        )

    def test_get_coordinator_is_stateless(self):
        from app.core.dependencies import get_runtime_resource_coordinator

        self.assertEqual(vars(get_runtime_resource_coordinator()), {})

    def test_injected_coordinator_creates_state(self):
        from app.core.dependencies import get_runtime_resource_coordinator

        state = get_runtime_resource_coordinator().create_resource_state(
            _recovery("NOT_REQUIRED")
        )
        self.assertIsInstance(state, RuntimeResourceState)
        self.assertEqual(state.resource_status, "READY")

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import RuntimeResourceCoordinatorDep

        self.assertIsNotNone(RuntimeResourceCoordinatorDep)

    def test_existing_dependencies_unchanged(self):
        from app.core.dependencies import get_runtime_recovery_coordinator
        from app.services.runtime.runtime_recovery_coordinator import (
            RuntimeRecoveryCoordinator,
        )

        self.assertIsInstance(
            get_runtime_recovery_coordinator(), RuntimeRecoveryCoordinator
        )


# =====================================================================
# Regression: Sprint 14.13 recovery coordinator & Sprint 13 pipeline unchanged
# =====================================================================
class Sprint14RegressionTests(unittest.TestCase):
    def test_recovery_chain_still_works(self):
        # pause/resume -> recovery coordinator -> resource coordinator compose.
        from app.core.dependencies import (
            get_runtime_recovery_coordinator,
            get_runtime_resource_coordinator,
        )
        from app.services.runtime.runtime_pause_resume_models import (
            RuntimePauseResumeState,
        )

        pause_resume = RuntimePauseResumeState(
            runtime_id="runtime-exec-x",
            execution_id="exec-x",
            pause_resume_status="RUNNING",
            can_pause=True,
            can_resume=False,
            requires_operator_action=False,
            pause_resume_metadata={},
        )
        recovery = get_runtime_recovery_coordinator().create_recovery_state(
            pause_resume
        )
        resource = get_runtime_resource_coordinator().create_resource_state(
            recovery
        )
        self.assertEqual(resource.resource_status, "READY")
        self.assertTrue(resource.resources_ready)

    def test_orchestration_pipeline_unchanged(self):
        from app.core.dependencies import get_execution_orchestration_engine
        from app.services.planning import PlanningRequest

        result = get_execution_orchestration_engine().create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertEqual(result.plan.goal, "Plan your trip")


if __name__ == "__main__":
    unittest.main()
