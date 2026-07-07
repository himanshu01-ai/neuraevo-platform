"""Unit tests for the Sprint 13.11 Execution Scheduler.

Covers the additive scheduling layer end to end without touching any network,
SDK, AI, tool execution, permission check, registry, runtime, memory, or
database:

* the immutable :class:`ExecutionSchedule` / :class:`ScheduledNode` DTOs and the
  :class:`SchedulingStrategy` enum (defaults, immutability, JSON round-trip);
* the deterministic :class:`ExecutionScheduler` (strategy resolution, scheduled/
  deferred/blocked separation, execution order, empty graph, determinism,
  statelessness, input non-mutation);
* the extended :class:`PlanValidator` (``validate_execution_schedule``);
* the extended :class:`PlanningExplanationBuilder`
  (``build_with_execution_schedule``);
* the extended :class:`PlanningEngine` (``create_execution_schedule`` +
  backward-compatible injection alongside the 13.2–13.10 collaborators);
* the composition-root wiring (``get_execution_scheduler`` + injection); and
* regression that Sprint 13.1–13.10 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_scheduler
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
from app.services.planning.execution_dependency_graph import (
    ExecutionDependencyGraphBuilder,
)
from app.services.planning.execution_dependency_graph_models import (
    ExecutionDependencyGraph,
    ExecutionNode,
)
from app.services.planning.execution_intent_engine import ExecutionIntentEngine
from app.services.planning.execution_orchestrator import ExecutionOrchestrator
from app.services.planning.execution_preparation_engine import (
    ExecutionPreparationEngine,
)
from app.services.planning.execution_schedule_models import (
    ExecutionSchedule,
    ScheduledNode,
    SchedulingStrategy,
)
from app.services.planning.execution_scheduler import ExecutionScheduler
from app.services.planning.execution_state_manager import ExecutionStateManager
from app.services.planning.execution_state_models import ExecutionState
from app.services.planning.plan_analyzer import PlanAnalyzer
from app.services.planning.task_lifecycle_engine import TaskLifecycleEngine


# =====================================================================
# Helpers
# =====================================================================
def _node(node_id, ready):
    return ExecutionNode(
        node_id=node_id,
        execution_unit_id=f"unit-{node_id}",
        dependencies=[],
        dependents=[],
        ready=ready,
        blocked=not ready,
        metadata={},
    )


def _graph(ready_ids, blocked_ids=(), strategy=None):
    nodes = [_node(n, True) for n in ready_ids] + [
        _node(n, False) for n in blocked_ids
    ]
    metadata = {"node_count": len(nodes)}
    if strategy is not None:
        metadata["execution_mode"] = strategy
    return ExecutionDependencyGraph(
        graph_id="g",
        nodes=nodes,
        edges=[],
        root_nodes=list(ready_ids) + list(blocked_ids),
        leaf_nodes=[],
        ready_nodes=list(ready_ids),
        blocked_nodes=list(blocked_ids),
        has_cycles=False,
        metadata=metadata,
    )


def _state(execution_id="exec-x"):
    return ExecutionState(
        execution_id=execution_id,
        overall_state="RUNNING",
        total_tasks=0,
        ready_tasks=0,
        waiting_tasks=0,
        running_tasks=0,
        completed_tasks=0,
        failed_tasks=0,
        cancelled_tasks=0,
        skipped_tasks=0,
        progress_percentage=0.0,
        active_task_ids=[],
        terminal=False,
        metadata={},
    )


def _create(graph, state=None):
    return ExecutionScheduler().create_schedule(graph, state or _state())


def _scheduled(node_id, priority=1):
    return ScheduledNode(
        node_id=node_id,
        execution_unit_id=f"unit-{node_id}",
        priority=priority,
        scheduled=True,
        reason="Ready and selected for execution.",
        metadata={},
    )


def _schedule(**overrides):
    nodes = overrides.pop("scheduled_nodes", [_scheduled("n1", 1)])
    data = dict(
        schedule_id="schedule-exec-x",
        execution_id="exec-x",
        scheduled_nodes=nodes,
        deferred_nodes=["n2"],
        blocked_nodes=["n3"],
        execution_order=[n.node_id for n in nodes],
        scheduling_strategy=SchedulingStrategy.SEQUENTIAL.value,
        metadata={},
    )
    data.update(overrides)
    return ExecutionSchedule(**data)


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
        ExecutionDependencyGraphBuilder(),
        ExecutionScheduler(),
    )


# =====================================================================
# DTOs
# =====================================================================
class ScheduleModelTests(unittest.TestCase):
    def test_schedule_defaults(self):
        schedule = ExecutionSchedule(
            schedule_id="s1",
            execution_id="e1",
            scheduling_strategy="SEQUENTIAL",
        )
        self.assertEqual(schedule.scheduled_nodes, [])
        self.assertEqual(schedule.deferred_nodes, [])
        self.assertEqual(schedule.execution_order, [])

    def test_node_defaults(self):
        node = ScheduledNode(
            node_id="n1",
            execution_unit_id="u1",
            priority=1,
            scheduled=True,
            reason="r",
        )
        self.assertEqual(node.metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionSchedule(schedule_id="s1")  # execution_id/strategy missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _schedule().scheduling_strategy = "PARALLEL"
        with self.assertRaises(ValidationError):
            _scheduled("n1").scheduled = False

    def test_json_round_trip(self):
        schedule = _create(_graph(["n1", "n2"], ["n3"], "PARALLEL"))
        restored = ExecutionSchedule.model_validate_json(
            schedule.model_dump_json()
        )
        self.assertEqual(restored, schedule)

    def test_enum_values(self):
        self.assertEqual(
            {s.value for s in SchedulingStrategy},
            {"SEQUENTIAL", "PARALLEL", "HYBRID"},
        )


# =====================================================================
# ExecutionScheduler — strategy resolution & selection
# =====================================================================
class SchedulerStrategyTests(unittest.TestCase):
    def test_defaults_to_sequential(self):
        schedule = _create(_graph(["n1", "n2", "n3"]))
        self.assertEqual(schedule.scheduling_strategy, "SEQUENTIAL")
        self.assertEqual([n.node_id for n in schedule.scheduled_nodes], ["n1"])
        self.assertEqual(schedule.deferred_nodes, ["n2", "n3"])

    def test_sequential_schedules_one(self):
        schedule = _create(_graph(["n1", "n2", "n3"], strategy="SEQUENTIAL"))
        self.assertEqual(len(schedule.scheduled_nodes), 1)
        self.assertEqual(schedule.deferred_nodes, ["n2", "n3"])

    def test_parallel_schedules_all(self):
        schedule = _create(_graph(["n1", "n2", "n3"], strategy="PARALLEL"))
        self.assertEqual(
            [n.node_id for n in schedule.scheduled_nodes],
            ["n1", "n2", "n3"],
        )
        self.assertEqual(schedule.deferred_nodes, [])

    def test_hybrid_schedules_first_half(self):
        schedule = _create(
            _graph(["n1", "n2", "n3", "n4"], strategy="HYBRID")
        )
        self.assertEqual(
            [n.node_id for n in schedule.scheduled_nodes], ["n1", "n2"]
        )
        self.assertEqual(schedule.deferred_nodes, ["n3", "n4"])

    def test_scheduling_strategy_key_wins(self):
        graph = _graph(["n1", "n2"])
        graph = graph.model_copy(
            update={"metadata": {"scheduling_strategy": "PARALLEL"}}
        )
        self.assertEqual(_create(graph).scheduling_strategy, "PARALLEL")

    def test_unknown_strategy_falls_back(self):
        schedule = _create(_graph(["n1"], strategy="TELEPORT"))
        self.assertEqual(schedule.scheduling_strategy, "SEQUENTIAL")


# =====================================================================
# ExecutionScheduler — separation, order, blocked, empty
# =====================================================================
class SchedulerContentTests(unittest.TestCase):
    def test_blocked_nodes_carried_through(self):
        schedule = _create(_graph(["n1"], ["n2", "n3"]))
        self.assertEqual(schedule.blocked_nodes, ["n2", "n3"])

    def test_scheduled_deferred_blocked_disjoint(self):
        schedule = _create(_graph(["n1", "n2"], ["n3"], strategy="SEQUENTIAL"))
        scheduled = {n.node_id for n in schedule.scheduled_nodes}
        self.assertFalse(scheduled & set(schedule.deferred_nodes))
        self.assertFalse(scheduled & set(schedule.blocked_nodes))

    def test_execution_order_matches_scheduled(self):
        schedule = _create(_graph(["n1", "n2", "n3"], strategy="PARALLEL"))
        self.assertEqual(
            schedule.execution_order,
            [n.node_id for n in schedule.scheduled_nodes],
        )

    def test_priority_is_ordered(self):
        schedule = _create(_graph(["n1", "n2", "n3"], strategy="PARALLEL"))
        self.assertEqual(
            [n.priority for n in schedule.scheduled_nodes], [1, 2, 3]
        )

    def test_scheduled_nodes_link_units(self):
        node = _create(_graph(["n1"])).scheduled_nodes[0]
        self.assertEqual(node.execution_unit_id, "unit-n1")
        self.assertTrue(node.scheduled)
        self.assertTrue(node.reason.strip())

    def test_schedule_links_execution(self):
        schedule = _create(_graph(["n1"]), _state("exec-42"))
        self.assertEqual(schedule.execution_id, "exec-42")
        self.assertIn("exec-42", schedule.schedule_id)

    def test_empty_graph_empty_schedule(self):
        schedule = _create(_graph([]))
        self.assertEqual(schedule.scheduled_nodes, [])
        self.assertEqual(schedule.deferred_nodes, [])
        self.assertEqual(schedule.blocked_nodes, [])
        self.assertEqual(schedule.execution_order, [])

    def test_no_ready_nodes_schedules_nothing(self):
        schedule = _create(_graph([], ["n1", "n2"]))
        self.assertEqual(schedule.scheduled_nodes, [])
        self.assertEqual(schedule.blocked_nodes, ["n1", "n2"])


# =====================================================================
# ExecutionScheduler — quality
# =====================================================================
class SchedulerQualityTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = ExecutionScheduler()

    def test_deterministic(self):
        graph = _graph(["n1", "n2", "n3"], ["n4"], strategy="HYBRID")
        state = _state()
        self.assertEqual(
            self.scheduler.create_schedule(graph, state),
            self.scheduler.create_schedule(graph, state),
        )

    def test_stateless(self):
        self.assertEqual(vars(self.scheduler), {})

    def test_does_not_mutate_inputs(self):
        graph = _graph(["n1", "n2"], ["n3"])
        state = _state()
        before_g = graph.model_dump()
        before_s = state.model_dump()
        self.scheduler.create_schedule(graph, state)
        self.assertEqual(graph.model_dump(), before_g)
        self.assertEqual(state.model_dump(), before_s)

    def test_produces_execution_schedule(self):
        self.assertIsInstance(_create(_graph(["n1"])), ExecutionSchedule)


# =====================================================================
# PlanValidator.validate_execution_schedule
# =====================================================================
class ValidateScheduleTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_passes(self):
        self.validator.validate_execution_schedule(_schedule())

    def test_empty_schedule_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_schedule(_schedule(schedule_id=" "))

    def test_empty_execution_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_schedule(
                _schedule(execution_id="")
            )

    def test_invalid_strategy_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_schedule(
                _schedule(scheduling_strategy="WARP")
            )

    def test_negative_priority_rejected(self):
        node = ScheduledNode.model_construct(
            node_id="n1", execution_unit_id="u1", priority=-1,
            scheduled=True, reason="r", metadata={},
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_schedule(
                _schedule(scheduled_nodes=[node], execution_order=["n1"])
            )

    def test_not_scheduled_flag_rejected(self):
        node = ScheduledNode(
            node_id="n1", execution_unit_id="u1", priority=1,
            scheduled=False, reason="r",
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_schedule(
                _schedule(scheduled_nodes=[node], execution_order=["n1"])
            )

    def test_empty_reason_rejected(self):
        node = ScheduledNode(
            node_id="n1", execution_unit_id="u1", priority=1,
            scheduled=True, reason="   ",
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_schedule(
                _schedule(scheduled_nodes=[node], execution_order=["n1"])
            )

    def test_execution_order_mismatch_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_schedule(
                _schedule(execution_order=["nope"])
            )

    def test_execution_order_length_mismatch_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_schedule(
                _schedule(execution_order=["n1", "n1"])
            )

    def test_overlapping_sets_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_schedule(
                _schedule(deferred_nodes=["n1"])  # n1 also scheduled
            )

    def test_duplicate_deferred_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_schedule(
                _schedule(deferred_nodes=["n2", "n2"])
            )

    def test_scheduler_output_always_validates(self):
        for strategy in ("SEQUENTIAL", "PARALLEL", "HYBRID", None):
            with self.subTest(strategy=strategy):
                self.validator.validate_execution_schedule(
                    _create(_graph(["n1", "n2", "n3"], ["n4"], strategy))
                )


# =====================================================================
# PlanningExplanationBuilder.build_with_execution_schedule
# =====================================================================
class BuildWithScheduleTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )

    def test_describes_scheduled_and_deferred(self):
        schedule = _create(_graph(["n1", "n2", "n3"], strategy="SEQUENTIAL"))
        text = self.builder.build_with_execution_schedule(self.plan, schedule)
        self.assertIn("lined up 1 task", text)
        self.assertIn("2 more are ready", text)

    def test_parallel_phrase(self):
        schedule = _create(_graph(["n1", "n2"], strategy="PARALLEL"))
        text = self.builder.build_with_execution_schedule(self.plan, schedule)
        self.assertIn("at the same time", text)

    def test_empty_message(self):
        text = self.builder.build_with_execution_schedule(
            self.plan, _create(_graph([]))
        )
        self.assertIn("Nothing is scheduled", text)

    def test_reuses_base_narration(self):
        text = self.builder.build_with_execution_schedule(
            self.plan, _create(_graph(["n1"]))
        )
        self.assertIn("I will", text)


# =====================================================================
# PlanningEngine.create_execution_schedule
# =====================================================================
class PlanningEngineCreateScheduleTests(unittest.TestCase):
    def setUp(self):
        self.graph = _graph(["n1"])
        self.state = _state()
        self.schedule = _schedule()
        self.validator = MagicMock()
        self.scheduler = MagicMock(name="Scheduler")
        self.scheduler.create_schedule.return_value = self.schedule
        self.engine = PlanningEngine(
            MagicMock(), self.validator, MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), self.scheduler,
        )

    def test_delegates_to_scheduler(self):
        self.engine.create_execution_schedule(self.graph, self.state)
        self.scheduler.create_schedule.assert_called_once_with(
            self.graph, self.state
        )

    def test_validates_the_schedule(self):
        self.engine.create_execution_schedule(self.graph, self.state)
        self.validator.validate_execution_schedule.assert_called_once_with(
            self.schedule
        )

    def test_returns_validated_schedule_unchanged(self):
        self.assertIs(
            self.engine.create_execution_schedule(self.graph, self.state),
            self.schedule,
        )

    def test_scheduler_exception_propagates(self):
        self.scheduler.create_schedule.side_effect = RuntimeError("x")
        with self.assertRaises(RuntimeError):
            self.engine.create_execution_schedule(self.graph, self.state)

    def test_scheduler_stored_as_attribute(self):
        self.assertIs(self.engine.scheduler, self.scheduler)

    def test_engine_without_scheduler_raises(self):
        engine = PlanningEngine(MagicMock(), MagicMock(), MagicMock())
        with self.assertRaises(RuntimeError):
            engine.create_execution_schedule(self.graph, self.state)


class PlanningEngineScheduleIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_full_pipeline_produces_valid_schedule(self):
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
        graph = self.engine.create_execution_dependency_graph(queue, lifecycles)
        schedule = self.engine.create_execution_schedule(graph, state)
        self.assertEqual(schedule.scheduling_strategy, "SEQUENTIAL")
        self.assertEqual(schedule.execution_id, state.execution_id)

    def test_engine_rejects_malformed_schedule(self):
        bad = _schedule(scheduling_strategy="WARP")
        scheduler = MagicMock()
        scheduler.create_schedule.return_value = bad
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
            ExecutionStateManager(),
            ExecutionDependencyGraphBuilder(),
            scheduler,
        )
        with self.assertRaises(PlanValidationError):
            engine.create_execution_schedule(_graph(["n1"]), _state())


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

    def _through_graph_builder(self):
        return (
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            DecisionEngine(),
            ExecutionIntentEngine(),
            ExecutionOrchestrator(),
            ExecutionCoordinator(),
            TaskLifecycleEngine(),
            ExecutionStateManager(),
            ExecutionDependencyGraphBuilder(),
        )

    def test_three_arg_engine_keeps_original_attributes(self):
        self.assertEqual(
            set(vars(PlanningEngine(*self._base()))),
            {"provider", "validator", "explanation_builder"},
        )

    def test_twelve_arg_engine_has_no_scheduler(self):
        engine = PlanningEngine(*self._base(), *self._through_graph_builder())
        self.assertNotIn("scheduler", vars(engine))

    def test_thirteen_arg_engine_adds_scheduler(self):
        self.assertEqual(
            set(vars(_full_engine())),
            {
                "provider", "validator", "explanation_builder", "analyzer",
                "preparation_engine", "decision_engine", "intent_engine",
                "orchestrator", "coordinator", "lifecycle_engine",
                "state_manager", "dependency_graph_builder", "scheduler",
            },
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class SchedulerDependencyTests(unittest.TestCase):
    def test_get_scheduler_returns_scheduler(self):
        from app.core.dependencies import get_execution_scheduler

        self.assertIsInstance(get_execution_scheduler(), ExecutionScheduler)

    def test_engine_injects_scheduler(self):
        from app.core.dependencies import get_planning_engine

        scheduler = MagicMock()
        engine = get_planning_engine(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), scheduler,
        )
        self.assertIs(engine.scheduler, scheduler)

    def test_engine_without_scheduler_backward_compatible(self):
        from app.core.dependencies import get_planning_engine

        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertFalse(hasattr(engine, "scheduler"))

    def test_composition_root_end_to_end(self):
        from app.core.dependencies import (
            get_decision_engine,
            get_execution_coordinator,
            get_execution_dependency_graph_builder,
            get_execution_intent_engine,
            get_execution_orchestrator,
            get_execution_preparation_engine,
            get_execution_scheduler,
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
            get_execution_dependency_graph_builder(),
            get_execution_scheduler(),
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
        graph = engine.create_execution_dependency_graph(queue, lifecycles)
        schedule = engine.create_execution_schedule(graph, state)
        self.assertIsInstance(schedule, ExecutionSchedule)
        self.assertIn(
            schedule.scheduling_strategy, {s.value for s in SchedulingStrategy}
        )
        self.assertTrue(
            engine.explanation_builder.build_with_execution_schedule(
                plan, schedule
            )
        )


# =====================================================================
# Regression: Sprint 13.1–13.10 behaviour unchanged
# =====================================================================
class Sprint131To1310RegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_create_plan_unchanged(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_dependency_graph_still_works(self):
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
        graph = self.engine.create_execution_dependency_graph(queue, lifecycles)
        self.assertEqual(len(graph.nodes), len(plan.steps))

    def test_base_explanation_still_works(self):
        plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip")
        )
        self.assertIn("I will", PlanningExplanationBuilder().build(plan))


if __name__ == "__main__":
    unittest.main()
