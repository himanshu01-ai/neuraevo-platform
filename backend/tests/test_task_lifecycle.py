"""Unit tests for the Sprint 13.8 Task Lifecycle layer.

Covers the additive lifecycle layer end to end without touching any network, SDK,
AI, tool execution, permission check, registry, runtime, memory, or database:

* the immutable :class:`TaskLifecycle` DTO, the :class:`TaskLifecycleState` enum,
  and the canonical transition table (defaults, immutability, JSON round-trip);
* the deterministic :class:`TaskLifecycleEngine` (one lifecycle per unit,
  starting-state derivation, allowed transitions, terminal flags, immutable
  history, determinism, statelessness, queue non-mutation);
* the extended :class:`PlanValidator` (``validate_task_lifecycles``);
* the extended :class:`PlanningExplanationBuilder` (``build_with_task_lifecycles``);
* the extended :class:`PlanningEngine` (``create_task_lifecycles`` +
  backward-compatible injection alongside the 13.2–13.7 collaborators);
* the composition-root wiring (``get_task_lifecycle_engine`` + injection); and
* regression that Sprint 13.1–13.7 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_task_lifecycle
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
from app.services.planning.execution_queue_models import (
    ExecutionQueue,
    ExecutionUnit,
)
from app.services.planning.plan_analyzer import PlanAnalyzer
from app.services.planning.task_lifecycle_engine import TaskLifecycleEngine
from app.services.planning.task_lifecycle_models import (
    TASK_LIFECYCLE_TRANSITIONS,
    TERMINAL_TASK_STATES,
    TaskLifecycle,
    TaskLifecycleState,
)


# =====================================================================
# Helpers
# =====================================================================
def _queue(statuses):
    units = [
        ExecutionUnit(
            unit_id=f"u{i + 1}",
            step_number=i + 1,
            description=f"Step {i + 1}",
            execution_group=1,
            status=status,
            dependencies=[],
        )
        for i, status in enumerate(statuses)
    ]
    return ExecutionQueue(
        queue_id="q1",
        workflow_id="wf1",
        status="READY",
        execution_units=units,
        total_units=len(units),
        ready_units=sum(1 for s in statuses if s == "READY"),
        blocked_units=sum(1 for s in statuses if s == "BLOCKED"),
        metadata={},
    )


def _lifecycles(statuses):
    return TaskLifecycleEngine().create_lifecycles(_queue(statuses))


def _lifecycle(**overrides):
    data = dict(
        unit_id="u1",
        current_state=TaskLifecycleState.READY.value,
        previous_state=TaskLifecycleState.CREATED.value,
        allowed_next_states=list(
            TASK_LIFECYCLE_TRANSITIONS[TaskLifecycleState.READY.value]
        ),
        is_terminal=False,
        state_history=[
            TaskLifecycleState.CREATED.value,
            TaskLifecycleState.READY.value,
        ],
        metadata={},
    )
    data.update(overrides)
    return TaskLifecycle(**data)


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
    )


# =====================================================================
# DTO / enum / transition table
# =====================================================================
class TaskLifecycleModelTests(unittest.TestCase):
    def test_defaults(self):
        lifecycle = TaskLifecycle(
            unit_id="u1", current_state="READY", is_terminal=False
        )
        self.assertIsNone(lifecycle.previous_state)
        self.assertEqual(lifecycle.allowed_next_states, [])
        self.assertEqual(lifecycle.state_history, [])
        self.assertEqual(lifecycle.metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            TaskLifecycle(unit_id="u1")  # current_state / is_terminal missing

    def test_is_immutable(self):
        with self.assertRaises(ValidationError):
            _lifecycle().current_state = "RUNNING"

    def test_json_round_trip(self):
        lifecycle = _lifecycle()
        restored = TaskLifecycle.model_validate_json(lifecycle.model_dump_json())
        self.assertEqual(restored, lifecycle)

    def test_enum_values(self):
        self.assertEqual(
            {s.value for s in TaskLifecycleState},
            {
                "CREATED", "READY", "WAITING", "RUNNING",
                "COMPLETED", "FAILED", "CANCELLED", "SKIPPED",
            },
        )

    def test_terminal_states(self):
        self.assertEqual(
            TERMINAL_TASK_STATES,
            frozenset({"COMPLETED", "FAILED", "CANCELLED", "SKIPPED"}),
        )

    def test_transition_table_matches_spec(self):
        self.assertEqual(TASK_LIFECYCLE_TRANSITIONS["CREATED"], ("READY",))
        self.assertEqual(
            TASK_LIFECYCLE_TRANSITIONS["READY"],
            ("WAITING", "RUNNING", "CANCELLED"),
        )
        self.assertEqual(
            TASK_LIFECYCLE_TRANSITIONS["WAITING"], ("READY", "CANCELLED")
        )
        self.assertEqual(
            TASK_LIFECYCLE_TRANSITIONS["RUNNING"],
            ("COMPLETED", "FAILED", "CANCELLED"),
        )
        for terminal in ("COMPLETED", "FAILED", "CANCELLED", "SKIPPED"):
            self.assertEqual(TASK_LIFECYCLE_TRANSITIONS[terminal], ())


# =====================================================================
# TaskLifecycleEngine — construction
# =====================================================================
class LifecycleConstructionTests(unittest.TestCase):
    def test_one_lifecycle_per_unit(self):
        self.assertEqual(len(_lifecycles(["READY", "WAITING", "BLOCKED"])), 3)

    def test_unit_ids_preserved(self):
        lifecycles = _lifecycles(["READY", "WAITING"])
        self.assertEqual([l.unit_id for l in lifecycles], ["u1", "u2"])

    def test_ready_unit_starts_ready(self):
        lifecycle = _lifecycles(["READY"])[0]
        self.assertEqual(lifecycle.current_state, "READY")
        self.assertEqual(lifecycle.previous_state, "CREATED")
        self.assertEqual(lifecycle.state_history, ["CREATED", "READY"])
        self.assertFalse(lifecycle.is_terminal)

    def test_waiting_unit_starts_waiting(self):
        lifecycle = _lifecycles(["WAITING"])[0]
        self.assertEqual(lifecycle.current_state, "WAITING")
        self.assertEqual(lifecycle.previous_state, "READY")
        self.assertEqual(
            lifecycle.state_history, ["CREATED", "READY", "WAITING"]
        )

    def test_blocked_unit_starts_waiting(self):
        lifecycle = _lifecycles(["BLOCKED"])[0]
        self.assertEqual(lifecycle.current_state, "WAITING")

    def test_allowed_next_states_from_table(self):
        ready = _lifecycles(["READY"])[0]
        self.assertEqual(
            set(ready.allowed_next_states),
            {"WAITING", "RUNNING", "CANCELLED"},
        )
        waiting = _lifecycles(["WAITING"])[0]
        self.assertEqual(
            set(waiting.allowed_next_states), {"READY", "CANCELLED"}
        )

    def test_no_lifecycle_is_terminal_at_start(self):
        for lifecycle in _lifecycles(["READY", "WAITING", "BLOCKED"]):
            self.assertFalse(lifecycle.is_terminal)

    def test_metadata_records_unit_context(self):
        lifecycle = _lifecycles(["WAITING"])[0]
        self.assertEqual(lifecycle.metadata["step_number"], 1)
        self.assertEqual(lifecycle.metadata["queue_unit_status"], "WAITING")

    def test_empty_queue_yields_no_lifecycles(self):
        self.assertEqual(_lifecycles([]), [])


# =====================================================================
# TaskLifecycleEngine — quality
# =====================================================================
class LifecycleEngineQualityTests(unittest.TestCase):
    def setUp(self):
        self.engine = TaskLifecycleEngine()

    def test_deterministic(self):
        queue = _queue(["READY", "WAITING", "BLOCKED"])
        self.assertEqual(
            self.engine.create_lifecycles(queue),
            self.engine.create_lifecycles(queue),
        )

    def test_stateless(self):
        self.assertEqual(vars(self.engine), {})

    def test_does_not_mutate_queue(self):
        queue = _queue(["READY", "WAITING"])
        before = queue.model_dump()
        self.engine.create_lifecycles(queue)
        self.assertEqual(queue.model_dump(), before)

    def test_produces_task_lifecycles(self):
        for lifecycle in self.engine.create_lifecycles(_queue(["READY"])):
            self.assertIsInstance(lifecycle, TaskLifecycle)


# =====================================================================
# PlanValidator.validate_task_lifecycles
# =====================================================================
class ValidateLifecyclesTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_passes(self):
        self.validator.validate_task_lifecycles([_lifecycle()])  # no raise

    def test_empty_list_passes(self):
        self.validator.validate_task_lifecycles([])  # no raise

    def test_empty_unit_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_task_lifecycles([_lifecycle(unit_id="  ")])

    def test_invalid_current_state_rejected(self):
        bad = TaskLifecycle.model_construct(
            unit_id="u1",
            current_state="ZOMBIE",
            previous_state=None,
            allowed_next_states=[],
            is_terminal=True,
            state_history=["ZOMBIE"],
            metadata={},
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_task_lifecycles([bad])

    def test_wrong_allowed_next_states_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_task_lifecycles(
                [_lifecycle(allowed_next_states=["RUNNING"])]
            )

    def test_wrong_is_terminal_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_task_lifecycles([_lifecycle(is_terminal=True)])

    def test_terminal_state_consistency(self):
        # COMPLETED is terminal: empty transitions, is_terminal True.
        self.validator.validate_task_lifecycles(
            [
                _lifecycle(
                    current_state="COMPLETED",
                    previous_state="RUNNING",
                    allowed_next_states=[],
                    is_terminal=True,
                    state_history=[
                        "CREATED", "READY", "RUNNING", "COMPLETED"
                    ],
                )
            ]
        )

    def test_empty_history_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_task_lifecycles(
                [_lifecycle(state_history=[])]
            )

    def test_history_not_ending_at_current_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_task_lifecycles(
                [_lifecycle(state_history=["CREATED"])]
            )

    def test_invalid_history_transition_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_task_lifecycles(
                [
                    _lifecycle(
                        current_state="READY",
                        previous_state="RUNNING",
                        state_history=["CREATED", "RUNNING", "READY"],
                    )
                ]
            )

    def test_previous_state_mismatch_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_task_lifecycles(
                [_lifecycle(previous_state="WAITING")]
            )

    def test_duplicate_unit_ids_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_task_lifecycles(
                [_lifecycle(unit_id="dup"), _lifecycle(unit_id="dup")]
            )

    def test_engine_output_always_validates(self):
        for statuses in (
            ["READY", "WAITING", "BLOCKED"],
            ["READY", "READY"],
            [],
        ):
            with self.subTest(statuses=statuses):
                self.validator.validate_task_lifecycles(_lifecycles(statuses))


# =====================================================================
# PlanningExplanationBuilder.build_with_task_lifecycles
# =====================================================================
class BuildWithLifecyclesTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )

    def test_counts_ready_and_waiting(self):
        text = self.builder.build_with_task_lifecycles(
            self.plan, _lifecycles(["READY", "WAITING", "BLOCKED"])
        )
        self.assertIn("tracking 3 tasks", text)
        self.assertIn("1 ready", text)
        self.assertIn("2 waiting", text)

    def test_empty_lifecycles_message(self):
        text = self.builder.build_with_task_lifecycles(self.plan, [])
        self.assertIn("no tasks to track", text)

    def test_reuses_base_narration(self):
        text = self.builder.build_with_task_lifecycles(
            self.plan, _lifecycles(["READY"])
        )
        self.assertIn("I will", text)


# =====================================================================
# PlanningEngine.create_task_lifecycles
# =====================================================================
class PlanningEngineCreateLifecyclesTests(unittest.TestCase):
    def setUp(self):
        self.queue = _queue(["READY", "WAITING"])
        self.lifecycles = [_lifecycle()]
        self.validator = MagicMock()
        self.lifecycle_engine = MagicMock(name="TaskLifecycleEngine")
        self.lifecycle_engine.create_lifecycles.return_value = self.lifecycles
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
            self.lifecycle_engine,
        )

    def test_delegates_to_lifecycle_engine_with_queue(self):
        self.engine.create_task_lifecycles(self.queue)
        self.lifecycle_engine.create_lifecycles.assert_called_once_with(
            self.queue
        )

    def test_validates_the_lifecycles(self):
        self.engine.create_task_lifecycles(self.queue)
        self.validator.validate_task_lifecycles.assert_called_once_with(
            self.lifecycles
        )

    def test_returns_validated_lifecycles_unchanged(self):
        self.assertIs(
            self.engine.create_task_lifecycles(self.queue), self.lifecycles
        )

    def test_lifecycle_engine_exception_propagates(self):
        self.lifecycle_engine.create_lifecycles.side_effect = RuntimeError("x")
        with self.assertRaises(RuntimeError):
            self.engine.create_task_lifecycles(self.queue)

    def test_lifecycle_engine_stored_as_attribute(self):
        self.assertIs(self.engine.lifecycle_engine, self.lifecycle_engine)

    def test_engine_without_lifecycle_engine_raises(self):
        engine = PlanningEngine(MagicMock(), MagicMock(), MagicMock())
        with self.assertRaises(RuntimeError):
            engine.create_task_lifecycles(self.queue)


class PlanningEngineLifecycleIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_full_pipeline_produces_valid_lifecycles(self):
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
        self.assertTrue(
            all(l.current_state == "WAITING" for l in lifecycles)
        )

    def test_engine_rejects_malformed_lifecycles(self):
        bad = [_lifecycle(is_terminal=True)]  # READY is not terminal
        lifecycle_engine = MagicMock()
        lifecycle_engine.create_lifecycles.return_value = bad
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
            lifecycle_engine,
        )
        with self.assertRaises(PlanValidationError):
            engine.create_task_lifecycles(_queue(["READY"]))


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

    def test_nine_arg_engine_has_no_lifecycle_engine(self):
        engine = PlanningEngine(
            *self._base(),
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            DecisionEngine(),
            ExecutionIntentEngine(),
            ExecutionOrchestrator(),
            ExecutionCoordinator(),
        )
        self.assertNotIn("lifecycle_engine", vars(engine))

    def test_ten_arg_engine_adds_lifecycle_engine(self):
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
            },
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class TaskLifecycleDependencyTests(unittest.TestCase):
    def test_get_task_lifecycle_engine_returns_engine(self):
        from app.core.dependencies import get_task_lifecycle_engine

        self.assertIsInstance(
            get_task_lifecycle_engine(), TaskLifecycleEngine
        )

    def test_engine_injects_lifecycle_engine(self):
        from app.core.dependencies import get_planning_engine

        lifecycle_engine = MagicMock()
        engine = get_planning_engine(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            lifecycle_engine,
        )
        self.assertIs(engine.lifecycle_engine, lifecycle_engine)

    def test_engine_without_lifecycle_engine_backward_compatible(self):
        from app.core.dependencies import get_planning_engine

        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertFalse(hasattr(engine, "lifecycle_engine"))

    def test_composition_root_end_to_end(self):
        from app.core.dependencies import (
            get_decision_engine,
            get_execution_coordinator,
            get_execution_intent_engine,
            get_execution_orchestrator,
            get_execution_preparation_engine,
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
        self.assertEqual(len(lifecycles), len(plan.steps))
        self.assertTrue(
            engine.explanation_builder.build_with_task_lifecycles(
                plan, lifecycles
            )
        )


# =====================================================================
# Regression: Sprint 13.1–13.7 behaviour unchanged
# =====================================================================
class Sprint131To137RegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_create_plan_unchanged(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_queue_still_works(self):
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
        self.assertEqual(queue.total_units, len(plan.steps))

    def test_base_explanation_still_works(self):
        plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip")
        )
        self.assertIn("I will", PlanningExplanationBuilder().build(plan))


if __name__ == "__main__":
    unittest.main()
