"""Unit tests for the Sprint 13.9 Execution State Manager.

Covers the additive aggregate-state layer end to end without touching any
network, SDK, AI, tool execution, permission check, registry, runtime, memory, or
database:

* the immutable :class:`ExecutionState` DTO and :class:`ExecutionStateType` enum
  (defaults, immutability, JSON round-trip);
* the deterministic :class:`ExecutionStateManager` (all overall-state rules,
  counts, progress, active ids, terminal detection, determinism, statelessness,
  lifecycle non-mutation);
* the extended :class:`PlanValidator` (``validate_execution_state``);
* the extended :class:`PlanningExplanationBuilder` (``build_with_execution_state``);
* the extended :class:`PlanningEngine` (``create_execution_state`` +
  backward-compatible injection alongside the 13.2–13.8 collaborators);
* the composition-root wiring (``get_execution_state_manager`` + injection); and
* regression that Sprint 13.1–13.8 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_state_manager
"""

import unittest
from unittest.mock import MagicMock

from pydantic import ValidationError

from app.services.planning import (
    HeuristicPlanningProvider,
    PlanningEngine,
    PlanningExplanationBuilder,
    PlanningRequest,
    PlanValidationError,
    PlanValidator,
)
from app.services.planning.decision_engine import DecisionEngine
from app.services.planning.execution_coordinator import ExecutionCoordinator
from app.services.planning.execution_intent_engine import ExecutionIntentEngine
from app.services.planning.execution_orchestrator import ExecutionOrchestrator
from app.services.planning.execution_preparation_engine import (
    ExecutionPreparationEngine,
)
from app.services.planning.execution_state_manager import ExecutionStateManager
from app.services.planning.execution_state_models import (
    ExecutionState,
    ExecutionStateType,
)
from app.services.planning.plan_analyzer import PlanAnalyzer
from app.services.planning.task_lifecycle_engine import TaskLifecycleEngine
from app.services.planning.task_lifecycle_models import (
    TASK_LIFECYCLE_TRANSITIONS,
    TERMINAL_TASK_STATES,
    TaskLifecycle,
)


# =====================================================================
# Helpers
# =====================================================================
def _lc(unit_id, state):
    return TaskLifecycle(
        unit_id=unit_id,
        current_state=state,
        previous_state=None,
        allowed_next_states=list(TASK_LIFECYCLE_TRANSITIONS[state]),
        is_terminal=state in TERMINAL_TASK_STATES,
        state_history=[state],
        metadata={},
    )


def _state(lifecycles):
    return ExecutionStateManager().create_state(lifecycles)


def _exec_state(**overrides):
    data = dict(
        execution_id="exec-abc",
        overall_state=ExecutionStateType.READY.value,
        total_tasks=2,
        ready_tasks=2,
        waiting_tasks=0,
        running_tasks=0,
        completed_tasks=0,
        failed_tasks=0,
        cancelled_tasks=0,
        skipped_tasks=0,
        progress_percentage=0.0,
        active_task_ids=["a", "b"],
        terminal=False,
        metadata={},
    )
    data.update(overrides)
    return ExecutionState(**data)


def _full_engine():
    return PlanningEngine(
        HeuristicPlanningProvider(),
        PlanValidator(),
        PlanningExplanationBuilder(),
        PlanAnalyzer(),
        ExecutionPreparationEngine(),
        DecisionEngine(),
        ExecutionIntentEngine(),
        ExecutionOrchestrator(),
        ExecutionCoordinator(),
        TaskLifecycleEngine(),
        ExecutionStateManager(),
    )


# =====================================================================
# DTO / enum
# =====================================================================
class ExecutionStateModelTests(unittest.TestCase):
    def test_defaults(self):
        state = ExecutionState(
            execution_id="e1",
            overall_state="READY",
            total_tasks=0,
            ready_tasks=0,
            waiting_tasks=0,
            running_tasks=0,
            completed_tasks=0,
            failed_tasks=0,
            cancelled_tasks=0,
            skipped_tasks=0,
            progress_percentage=0.0,
            terminal=False,
        )
        self.assertEqual(state.active_task_ids, [])
        self.assertEqual(state.metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionState(execution_id="e1")  # many fields missing

    def test_is_immutable(self):
        with self.assertRaises(ValidationError):
            _exec_state().terminal = True

    def test_json_round_trip(self):
        state = _state([_lc("a", "COMPLETED"), _lc("b", "RUNNING")])
        restored = ExecutionState.model_validate_json(state.model_dump_json())
        self.assertEqual(restored, state)

    def test_enum_values(self):
        self.assertEqual(
            {s.value for s in ExecutionStateType},
            {
                "READY", "WAITING", "RUNNING", "PARTIALLY_COMPLETED",
                "COMPLETED", "FAILED", "CANCELLED",
            },
        )


# =====================================================================
# ExecutionStateManager — overall-state rules
# =====================================================================
class OverallStateTests(unittest.TestCase):
    def test_empty_is_ready_zero_progress(self):
        state = _state([])
        self.assertEqual(state.overall_state, "READY")
        self.assertEqual(state.progress_percentage, 0.0)
        self.assertFalse(state.terminal)

    def test_all_ready_is_ready(self):
        self.assertEqual(
            _state([_lc("a", "READY"), _lc("b", "READY")]).overall_state, "READY"
        )

    def test_all_waiting_is_waiting(self):
        self.assertEqual(
            _state([_lc("a", "WAITING")]).overall_state, "WAITING"
        )

    def test_running_dominates_ready(self):
        self.assertEqual(
            _state([_lc("a", "RUNNING"), _lc("b", "READY")]).overall_state,
            "RUNNING",
        )

    def test_cancelled_dominates_ready_and_waiting(self):
        self.assertEqual(
            _state([_lc("a", "CANCELLED"), _lc("b", "WAITING")]).overall_state,
            "CANCELLED",
        )

    def test_completed_and_active_is_partially_completed(self):
        self.assertEqual(
            _state([_lc("a", "COMPLETED"), _lc("b", "RUNNING")]).overall_state,
            "PARTIALLY_COMPLETED",
        )

    def test_failed_dominates_partially_completed(self):
        self.assertEqual(
            _state([_lc("a", "FAILED"), _lc("b", "COMPLETED")]).overall_state,
            "FAILED",
        )

    def test_all_completed_is_completed(self):
        state = _state([_lc("a", "COMPLETED"), _lc("b", "COMPLETED")])
        self.assertEqual(state.overall_state, "COMPLETED")
        self.assertTrue(state.terminal)

    def test_all_cancelled_is_cancelled(self):
        state = _state([_lc("a", "CANCELLED"), _lc("b", "CANCELLED")])
        self.assertEqual(state.overall_state, "CANCELLED")
        self.assertTrue(state.terminal)

    def test_mixed_terminal_completed_and_cancelled_is_completed(self):
        state = _state([_lc("a", "COMPLETED"), _lc("b", "CANCELLED")])
        self.assertEqual(state.overall_state, "COMPLETED")
        self.assertTrue(state.terminal)


# =====================================================================
# ExecutionStateManager — counts, progress, active, terminal
# =====================================================================
class StateContentTests(unittest.TestCase):
    def test_counts_every_state(self):
        state = _state(
            [
                _lc("a", "READY"),
                _lc("b", "WAITING"),
                _lc("c", "RUNNING"),
                _lc("d", "COMPLETED"),
                _lc("e", "FAILED"),
                _lc("f", "CANCELLED"),
                _lc("g", "SKIPPED"),
            ]
        )
        self.assertEqual(state.total_tasks, 7)
        self.assertEqual(state.ready_tasks, 1)
        self.assertEqual(state.waiting_tasks, 1)
        self.assertEqual(state.running_tasks, 1)
        self.assertEqual(state.completed_tasks, 1)
        self.assertEqual(state.failed_tasks, 1)
        self.assertEqual(state.cancelled_tasks, 1)
        self.assertEqual(state.skipped_tasks, 1)

    def test_progress_from_completed_only(self):
        state = _state(
            [_lc("a", "COMPLETED"), _lc("b", "RUNNING"), _lc("c", "READY"),
             _lc("d", "WAITING")]
        )
        self.assertEqual(state.progress_percentage, 25.0)

    def test_active_task_ids_are_non_terminal(self):
        state = _state(
            [_lc("a", "READY"), _lc("b", "COMPLETED"), _lc("c", "RUNNING")]
        )
        self.assertEqual(state.active_task_ids, ["a", "c"])

    def test_terminal_only_when_all_terminal(self):
        self.assertFalse(
            _state([_lc("a", "COMPLETED"), _lc("b", "RUNNING")]).terminal
        )
        self.assertTrue(
            _state([_lc("a", "COMPLETED"), _lc("b", "SKIPPED")]).terminal
        )

    def test_execution_id_deterministic_and_content_sensitive(self):
        a = _state([_lc("a", "READY")])
        b = _state([_lc("a", "READY")])
        c = _state([_lc("z", "READY")])
        self.assertEqual(a.execution_id, b.execution_id)
        self.assertNotEqual(a.execution_id, c.execution_id)
        self.assertTrue(a.execution_id.startswith("exec-"))


# =====================================================================
# ExecutionStateManager — quality
# =====================================================================
class ManagerQualityTests(unittest.TestCase):
    def setUp(self):
        self.manager = ExecutionStateManager()

    def test_deterministic(self):
        lifecycles = [_lc("a", "COMPLETED"), _lc("b", "RUNNING")]
        self.assertEqual(
            self.manager.create_state(lifecycles),
            self.manager.create_state(lifecycles),
        )

    def test_stateless(self):
        self.assertEqual(vars(self.manager), {})

    def test_does_not_mutate_lifecycles(self):
        lifecycles = [_lc("a", "COMPLETED"), _lc("b", "RUNNING")]
        before = [l.model_dump() for l in lifecycles]
        self.manager.create_state(lifecycles)
        self.assertEqual([l.model_dump() for l in lifecycles], before)

    def test_produces_execution_state(self):
        self.assertIsInstance(_state([_lc("a", "READY")]), ExecutionState)


# =====================================================================
# PlanValidator.validate_execution_state
# =====================================================================
class ValidateExecutionStateTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_passes(self):
        self.validator.validate_execution_state(_exec_state())  # no raise

    def test_empty_execution_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_state(_exec_state(execution_id=" "))

    def test_invalid_overall_state_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_state(
                _exec_state(overall_state="EXPLODED")
            )

    def test_negative_count_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_state(_exec_state(ready_tasks=-1))

    def test_counts_exceeding_total_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_state(
                _exec_state(total_tasks=1, ready_tasks=2, active_task_ids=["a"])
            )

    def test_progress_out_of_range_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_state(
                _exec_state(progress_percentage=150.0)
            )

    def test_terminal_flag_inconsistent_rejected(self):
        # 2 completed => every task terminal, so terminal must be True.
        bad = _exec_state(
            overall_state="COMPLETED",
            ready_tasks=0,
            completed_tasks=2,
            progress_percentage=100.0,
            active_task_ids=[],
            terminal=False,
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_state(bad)

    def test_terminal_overall_state_must_be_outcome(self):
        bad = _exec_state(
            overall_state="RUNNING",
            ready_tasks=0,
            completed_tasks=2,
            progress_percentage=100.0,
            active_task_ids=[],
            terminal=True,
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_state(bad)

    def test_empty_active_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_state(
                _exec_state(active_task_ids=["a", "  "])
            )

    def test_duplicate_active_ids_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_state(
                _exec_state(active_task_ids=["a", "a"])
            )

    def test_active_id_count_mismatch_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_state(
                _exec_state(active_task_ids=["a"])  # total 2, 0 terminal => 2
            )

    def test_manager_output_always_validates(self):
        for lifecycles in (
            [],
            [_lc("a", "READY"), _lc("b", "WAITING")],
            [_lc("a", "COMPLETED"), _lc("b", "RUNNING")],
            [_lc("a", "FAILED"), _lc("b", "COMPLETED")],
            [_lc("a", "COMPLETED"), _lc("b", "COMPLETED")],
            [_lc("a", "CANCELLED"), _lc("b", "WAITING")],
        ):
            with self.subTest(lifecycles=[l.current_state for l in lifecycles]):
                self.validator.validate_execution_state(_state(lifecycles))


# =====================================================================
# PlanningExplanationBuilder.build_with_execution_state
# =====================================================================
class BuildWithExecutionStateTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )

    def test_completed_message_and_progress(self):
        state = _state([_lc("a", "COMPLETED"), _lc("b", "COMPLETED")])
        text = self.builder.build_with_execution_state(self.plan, state)
        self.assertIn("complete", text.lower())
        self.assertIn("100%", text)

    def test_running_message(self):
        state = _state([_lc("a", "RUNNING"), _lc("b", "READY")])
        text = self.builder.build_with_execution_state(self.plan, state)
        self.assertIn("in progress", text)

    def test_reuses_base_narration(self):
        text = self.builder.build_with_execution_state(
            self.plan, _state([_lc("a", "READY")])
        )
        self.assertIn("I will", text)


# =====================================================================
# PlanningEngine.create_execution_state
# =====================================================================
class PlanningEngineCreateStateTests(unittest.TestCase):
    def setUp(self):
        self.lifecycles = [_lc("a", "READY")]
        self.state = _exec_state()
        self.validator = MagicMock()
        self.state_manager = MagicMock(name="ExecutionStateManager")
        self.state_manager.create_state.return_value = self.state
        self.engine = PlanningEngine(
            MagicMock(),
            self.validator,
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            self.state_manager,
        )

    def test_delegates_to_state_manager(self):
        self.engine.create_execution_state(self.lifecycles)
        self.state_manager.create_state.assert_called_once_with(self.lifecycles)

    def test_validates_the_state(self):
        self.engine.create_execution_state(self.lifecycles)
        self.validator.validate_execution_state.assert_called_once_with(
            self.state
        )

    def test_returns_validated_state_unchanged(self):
        self.assertIs(
            self.engine.create_execution_state(self.lifecycles), self.state
        )

    def test_state_manager_exception_propagates(self):
        self.state_manager.create_state.side_effect = RuntimeError("x")
        with self.assertRaises(RuntimeError):
            self.engine.create_execution_state(self.lifecycles)

    def test_state_manager_stored_as_attribute(self):
        self.assertIs(self.engine.state_manager, self.state_manager)

    def test_engine_without_state_manager_raises(self):
        engine = PlanningEngine(MagicMock(), MagicMock(), MagicMock())
        with self.assertRaises(RuntimeError):
            engine.create_execution_state(self.lifecycles)


class PlanningEngineStateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_full_pipeline_produces_valid_state(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        analysis = self.engine.analyze(plan)
        preparation = self.engine.prepare(plan, analysis)
        decision = self.engine.decide(plan, analysis, preparation)
        intent = self.engine.create_execution_intent(
            plan, analysis, preparation, decision
        )
        workflow = self.engine.create_execution_workflow(
            plan, analysis, preparation, decision, intent
        )
        queue = self.engine.create_execution_queue(workflow)
        lifecycles = self.engine.create_task_lifecycles(queue)
        state = self.engine.create_execution_state(lifecycles)
        self.assertEqual(state.total_tasks, len(plan.steps))
        self.assertEqual(state.overall_state, "WAITING")

    def test_engine_rejects_malformed_state(self):
        bad = _exec_state(progress_percentage=200.0)
        state_manager = MagicMock()
        state_manager.create_state.return_value = bad
        engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            DecisionEngine(),
            ExecutionIntentEngine(),
            ExecutionOrchestrator(),
            ExecutionCoordinator(),
            TaskLifecycleEngine(),
            state_manager,
        )
        with self.assertRaises(PlanValidationError):
            engine.create_execution_state([_lc("a", "READY")])


# =====================================================================
# Backward compatibility of the engine's construction shape
# =====================================================================
class EngineConstructionShapeTests(unittest.TestCase):
    def _base(self):
        return (
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
        )

    def test_three_arg_engine_keeps_original_attributes(self):
        self.assertEqual(
            set(vars(PlanningEngine(*self._base()))),
            {"provider", "validator", "explanation_builder"},
        )

    def test_ten_arg_engine_has_no_state_manager(self):
        engine = PlanningEngine(
            *self._base(),
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            DecisionEngine(),
            ExecutionIntentEngine(),
            ExecutionOrchestrator(),
            ExecutionCoordinator(),
            TaskLifecycleEngine(),
        )
        self.assertNotIn("state_manager", vars(engine))

    def test_eleven_arg_engine_adds_state_manager(self):
        self.assertEqual(
            set(vars(_full_engine())),
            {
                "provider",
                "validator",
                "explanation_builder",
                "analyzer",
                "preparation_engine",
                "decision_engine",
                "intent_engine",
                "orchestrator",
                "coordinator",
                "lifecycle_engine",
                "state_manager",
            },
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class ExecutionStateManagerDependencyTests(unittest.TestCase):
    def test_get_execution_state_manager_returns_manager(self):
        from app.core.dependencies import get_execution_state_manager

        self.assertIsInstance(
            get_execution_state_manager(), ExecutionStateManager
        )

    def test_engine_injects_state_manager(self):
        from app.core.dependencies import get_planning_engine

        state_manager = MagicMock()
        engine = get_planning_engine(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            state_manager,
        )
        self.assertIs(engine.state_manager, state_manager)

    def test_engine_without_state_manager_backward_compatible(self):
        from app.core.dependencies import get_planning_engine

        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertFalse(hasattr(engine, "state_manager"))

    def test_composition_root_end_to_end(self):
        from app.core.dependencies import (
            get_decision_engine,
            get_execution_coordinator,
            get_execution_intent_engine,
            get_execution_orchestrator,
            get_execution_preparation_engine,
            get_execution_state_manager,
            get_plan_analyzer,
            get_plan_validator,
            get_planning_engine,
            get_planning_explanation_builder,
            get_planning_provider,
            get_task_lifecycle_engine,
        )

        engine = get_planning_engine(
            get_planning_provider(),
            get_plan_validator(),
            get_planning_explanation_builder(),
            get_plan_analyzer(),
            get_execution_preparation_engine(),
            get_decision_engine(),
            get_execution_intent_engine(),
            get_execution_orchestrator(),
            get_execution_coordinator(),
            get_task_lifecycle_engine(),
            get_execution_state_manager(),
        )
        plan = engine.create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        analysis = engine.analyze(plan)
        preparation = engine.prepare(plan, analysis)
        decision = engine.decide(plan, analysis, preparation)
        intent = engine.create_execution_intent(
            plan, analysis, preparation, decision
        )
        workflow = engine.create_execution_workflow(
            plan, analysis, preparation, decision, intent
        )
        queue = engine.create_execution_queue(workflow)
        lifecycles = engine.create_task_lifecycles(queue)
        state = engine.create_execution_state(lifecycles)
        self.assertIsInstance(state, ExecutionState)
        self.assertIn(state.overall_state, {s.value for s in ExecutionStateType})
        self.assertTrue(
            engine.explanation_builder.build_with_execution_state(plan, state)
        )


# =====================================================================
# Regression: Sprint 13.1–13.8 behaviour unchanged
# =====================================================================
class Sprint131To138RegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_create_plan_unchanged(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_lifecycles_still_work(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        analysis = self.engine.analyze(plan)
        preparation = self.engine.prepare(plan, analysis)
        decision = self.engine.decide(plan, analysis, preparation)
        intent = self.engine.create_execution_intent(
            plan, analysis, preparation, decision
        )
        workflow = self.engine.create_execution_workflow(
            plan, analysis, preparation, decision, intent
        )
        queue = self.engine.create_execution_queue(workflow)
        lifecycles = self.engine.create_task_lifecycles(queue)
        self.assertEqual(len(lifecycles), len(plan.steps))

    def test_base_explanation_still_works(self):
        plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip")
        )
        self.assertIn("I will", PlanningExplanationBuilder().build(plan))


if __name__ == "__main__":
    unittest.main()
