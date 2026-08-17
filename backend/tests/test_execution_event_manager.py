"""Unit tests for the Sprint 14.8 Execution Event Manager.

Covers the runtime event layer end to end without touching any network, SDK, AI,
clock, UUID, capability, execution, or database:

* the immutable :class:`ExecutionEventLog` / :class:`ExecutionEvent` DTOs and the
  :class:`EventStatus` enum (defaults, immutability, required fields, enum values);
* the deterministic, stateless :class:`ExecutionEventManager` (every ControlStatus
  mapping, single-event generation, event ordering, deterministic ids,
  determinism, statelessness, non-mutation, provider independence);
* the composition-root wiring (``get_execution_event_manager`` +
  ``ExecutionEventManagerDep``); and
* regression that the Sprint 14.7 controller and Sprint 13 pipeline are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_event_manager
"""

import unittest

from pydantic import ValidationError

from app.services.runtime.execution_controller_models import (
    ControlStatus,
    ExecutionControlState,
)
from app.services.runtime.execution_event_manager import ExecutionEventManager
from app.services.runtime.execution_event_models import (
    EventStatus,
    ExecutionEvent,
    ExecutionEventLog,
)


# Control status -> expected event status (PAUSED is unmapped -> INITIALIZED).
EXPECTED_EVENT = {
    "IDLE": "INITIALIZED",
    "RUNNING": "ACTIVE",
    "COMPLETED": "COMPLETED",
    "FAILED": "FAILED",
    "CANCELLED": "CANCELLED",
    "PAUSED": "INITIALIZED",
}


# =====================================================================
# Helpers
# =====================================================================
def _control_state(
    control_status="RUNNING",
    runtime_id="runtime-exec-x",
    execution_id="exec-x",
):
    return ExecutionControlState(
        runtime_id=runtime_id,
        execution_id=execution_id,
        control_status=control_status,
        can_pause=False,
        can_resume=False,
        can_cancel=False,
        can_restart=False,
        control_metadata={},
    )


def _log(control_state=None):
    return ExecutionEventManager().create_event_log(
        control_state if control_state is not None else _control_state()
    )


def _event(**overrides):
    data = dict(
        event_id="event-abc",
        event_type="ACTIVE",
        execution_id="exec-x",
        runtime_id="runtime-exec-x",
        event_sequence=1,
    )
    data.update(overrides)
    return ExecutionEvent(**data)


# =====================================================================
# DTOs
# =====================================================================
class EventModelTests(unittest.TestCase):
    def test_log_defaults(self):
        log = ExecutionEventLog(
            runtime_id="r", execution_id="e", event_status="INITIALIZED"
        )
        self.assertEqual(log.events, [])
        self.assertEqual(log.event_count, 0)
        self.assertEqual(log.event_metadata, {})

    def test_log_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionEventLog(runtime_id="r")  # rest missing

    def test_event_requires_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionEvent(event_id="e")  # rest missing

    def test_log_immutable(self):
        with self.assertRaises(ValidationError):
            _log().event_status = "ACTIVE"

    def test_event_immutable(self):
        with self.assertRaises(ValidationError):
            _event().event_sequence = 2

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in EventStatus},
            {"INITIALIZED", "ACTIVE", "COMPLETED", "FAILED", "CANCELLED"},
        )

    def test_produces_event_log(self):
        self.assertIsInstance(_log(), ExecutionEventLog)


# =====================================================================
# Status mapping — every ControlStatus
# =====================================================================
class EventMappingTests(unittest.TestCase):
    def test_every_control_status_maps(self):
        for control_status in ControlStatus:
            with self.subTest(control_status=control_status.value):
                log = _log(_control_state(control_status.value))
                self.assertEqual(
                    log.event_status, EXPECTED_EVENT[control_status.value]
                )

    def test_idle_is_initialized(self):
        self.assertEqual(_log(_control_state("IDLE")).event_status, "INITIALIZED")

    def test_running_is_active(self):
        self.assertEqual(_log(_control_state("RUNNING")).event_status, "ACTIVE")

    def test_terminal_states_map_directly(self):
        for status in ("COMPLETED", "FAILED", "CANCELLED"):
            with self.subTest(status=status):
                self.assertEqual(_log(_control_state(status)).event_status, status)

    def test_paused_falls_back_to_initialized(self):
        # PAUSED is not in the spec mapping (unreachable from the 14.7
        # controller); it falls back to INITIALIZED.
        self.assertEqual(_log(_control_state("PAUSED")).event_status, "INITIALIZED")

    def test_event_type_represents_state(self):
        log = _log(_control_state("RUNNING"))
        self.assertEqual(log.events[0].event_type, "ACTIVE")


# =====================================================================
# Event generation, ordering & ids
# =====================================================================
class EventGenerationTests(unittest.TestCase):
    def test_generates_single_event(self):
        log = _log(_control_state("RUNNING"))
        self.assertEqual(len(log.events), 1)
        self.assertEqual(log.event_count, 1)

    def test_event_count_matches_events(self):
        log = _log()
        self.assertEqual(log.event_count, len(log.events))

    def test_sequence_starts_at_one(self):
        self.assertEqual(_log().events[0].event_sequence, 1)

    def test_event_carries_ids(self):
        log = _log(
            _control_state("RUNNING", runtime_id="runtime-abc", execution_id="exec-abc")
        )
        event = log.events[0]
        self.assertEqual(event.runtime_id, "runtime-abc")
        self.assertEqual(event.execution_id, "exec-abc")

    def test_event_id_is_deterministic(self):
        state = _control_state("RUNNING")
        self.assertEqual(
            _log(state).events[0].event_id, _log(state).events[0].event_id
        )

    def test_event_id_prefixed(self):
        self.assertTrue(_log().events[0].event_id.startswith("event-"))

    def test_event_id_differs_by_execution(self):
        first = _log(_control_state("RUNNING", execution_id="exec-1"))
        second = _log(_control_state("RUNNING", execution_id="exec-2"))
        self.assertNotEqual(
            first.events[0].event_id, second.events[0].event_id
        )


# =====================================================================
# Empty history handling (DTO)
# =====================================================================
class EmptyHistoryTests(unittest.TestCase):
    def test_empty_history_is_valid(self):
        log = ExecutionEventLog(
            runtime_id="r",
            execution_id="e",
            event_status="INITIALIZED",
            events=[],
            event_count=0,
        )
        self.assertEqual(log.events, [])
        self.assertEqual(log.event_count, 0)

    def test_manager_always_produces_one_event(self):
        for control_status in ControlStatus:
            with self.subTest(control_status=control_status.value):
                log = _log(_control_state(control_status.value))
                self.assertEqual(log.event_count, 1)


# =====================================================================
# Determinism, non-mutation, provider independence, statelessness
# =====================================================================
class EventQualityTests(unittest.TestCase):
    def test_deterministic(self):
        state = _control_state("RUNNING")
        manager = ExecutionEventManager()
        self.assertEqual(
            manager.create_event_log(state), manager.create_event_log(state)
        )

    def test_independent_managers_agree(self):
        state = _control_state("COMPLETED")
        self.assertEqual(
            ExecutionEventManager().create_event_log(state),
            ExecutionEventManager().create_event_log(state),
        )

    def test_ids_and_metadata_from_control_state(self):
        log = _log(_control_state("RUNNING"))
        self.assertEqual(log.runtime_id, "runtime-exec-x")
        self.assertEqual(log.execution_id, "exec-x")
        self.assertEqual(log.event_metadata["control_status"], "RUNNING")
        self.assertEqual(log.event_metadata["event_status"], "ACTIVE")

    def test_does_not_mutate_control_state(self):
        state = _control_state("RUNNING")
        before = state.model_dump()
        _log(state)
        self.assertEqual(state.model_dump(), before)

    def test_plain_data_only(self):
        log = _log(_control_state("RUNNING"))
        plain = (str, int, float, bool, type(None))
        for value in log.event_metadata.values():
            self.assertIsInstance(value, plain)

    def test_stateless(self):
        self.assertEqual(vars(ExecutionEventManager()), {})

    def test_no_state_accumulates(self):
        manager = ExecutionEventManager()
        manager.create_event_log(_control_state())
        self.assertEqual(vars(manager), {})


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class EventManagerDependencyTests(unittest.TestCase):
    def test_get_manager_returns_manager(self):
        from app.core.dependencies import get_execution_event_manager

        self.assertIsInstance(
            get_execution_event_manager(), ExecutionEventManager
        )

    def test_get_manager_is_stateless(self):
        from app.core.dependencies import get_execution_event_manager

        self.assertEqual(vars(get_execution_event_manager()), {})

    def test_injected_manager_creates_log(self):
        from app.core.dependencies import get_execution_event_manager

        log = get_execution_event_manager().create_event_log(
            _control_state("RUNNING")
        )
        self.assertIsInstance(log, ExecutionEventLog)
        self.assertEqual(log.event_status, "ACTIVE")

    def test_dependency_dep_alias_exists(self):
        from app.core.dependencies import ExecutionEventManagerDep

        self.assertIsNotNone(ExecutionEventManagerDep)

    def test_existing_dependencies_unchanged(self):
        from app.core.dependencies import get_execution_controller
        from app.services.runtime.execution_controller import ExecutionController

        self.assertIsInstance(get_execution_controller(), ExecutionController)


# =====================================================================
# Regression: Sprint 14.7 controller & Sprint 13 pipeline unchanged
# =====================================================================
class Sprint14RegressionTests(unittest.TestCase):
    def test_controller_still_works(self):
        from app.core.dependencies import get_execution_controller
        from app.services.runtime.execution_progress_models import (
            ExecutionProgress,
        )

        progress = ExecutionProgress(
            runtime_id="runtime-exec-x",
            execution_id="exec-x",
            progress_status="IN_PROGRESS",
            total_execution_units=2,
            completed_execution_units=1,
            failed_execution_units=0,
            cancelled_execution_units=0,
            completion_percentage=50,
            progress_metadata={},
        )
        state = get_execution_controller().create_control_state(progress)
        self.assertEqual(state.control_status, "RUNNING")

    def test_orchestration_pipeline_unchanged(self):
        from app.core.dependencies import get_execution_orchestration_engine
        from app.services.planning import PlanningRequest

        result = get_execution_orchestration_engine().create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertEqual(result.plan.goal, "Plan your trip")


if __name__ == "__main__":
    unittest.main()
