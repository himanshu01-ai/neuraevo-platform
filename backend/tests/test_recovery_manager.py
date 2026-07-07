"""Unit tests for the Sprint 13.13 Recovery Manager.

Covers the additive recovery-planning layer end to end without touching any
network, SDK, AI, tool execution, permission check, registry, runtime, memory, or
database:

* the immutable :class:`RecoveryPlan` DTO and the :class:`RecoveryStrategy` enum
  (defaults, immutability, JSON round-trip);
* the deterministic :class:`RecoveryManager` (strategy selection, affected-node
  identification, recoverable/unrecoverable partition, intervention decision,
  empty execution, determinism, statelessness, input non-mutation);
* the extended :class:`PlanValidator` (``validate_recovery_plan``);
* the extended :class:`PlanningExplanationBuilder` (``build_with_recovery_plan``);
* the extended :class:`PlanningEngine` (``create_recovery_plan`` +
  backward-compatible injection alongside the 13.2–13.12 collaborators);
* the composition-root wiring (``get_recovery_manager`` + injection); and
* regression that Sprint 13.1–13.12 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_recovery_manager
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
from app.services.planning.execution_monitor import ExecutionMonitor
from app.services.planning.execution_monitor_models import (
    ExecutionMonitoringReport,
)
from app.services.planning.execution_orchestrator import ExecutionOrchestrator
from app.services.planning.execution_preparation_engine import (
    ExecutionPreparationEngine,
)
from app.services.planning.execution_scheduler import ExecutionScheduler
from app.services.planning.execution_state_manager import ExecutionStateManager
from app.services.planning.execution_state_models import ExecutionState
from app.services.planning.plan_analyzer import PlanAnalyzer
from app.services.planning.recovery_manager import RecoveryManager
from app.services.planning.recovery_models import RecoveryPlan, RecoveryStrategy
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


def _graph(ready_ids=("n1",), blocked_ids=(), has_cycles=False):
    nodes = [_node(n, True) for n in ready_ids] + [
        _node(n, False) for n in blocked_ids
    ]
    return ExecutionDependencyGraph(
        graph_id="g",
        nodes=nodes,
        edges=[],
        root_nodes=[n.node_id for n in nodes],
        leaf_nodes=[],
        ready_nodes=list(ready_ids),
        blocked_nodes=list(blocked_ids),
        has_cycles=has_cycles,
        metadata={},
    )


def _report(
    health="HEALTHY",
    active=("n1",),
    blocked=(),
    pending=(),
    execution_id="exec-x",
):
    return ExecutionMonitoringReport(
        report_id=f"monitor-{execution_id}",
        execution_id=execution_id,
        execution_status="RUNNING",
        overall_progress=0.0,
        active_nodes=list(active),
        blocked_nodes=list(blocked),
        completed_nodes=[],
        pending_nodes=list(pending),
        health_status=health,
        warnings=[],
        metadata={},
    )


def _state(overall_state="RUNNING", execution_id="exec-x"):
    return ExecutionState(
        execution_id=execution_id,
        overall_state=overall_state,
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


def _create(report=None, state=None, graph=None):
    return RecoveryManager().create_recovery_plan(
        report if report is not None else _report(),
        state if state is not None else _state(),
        graph if graph is not None else _graph(),
    )


def _plan(**overrides):
    data = dict(
        recovery_id="recovery-exec-x",
        execution_id="exec-x",
        recovery_strategy="RETRY",
        affected_nodes=["n1"],
        recoverable_nodes=["n1"],
        unrecoverable_nodes=[],
        requires_user_intervention=False,
        recovery_reason="reason",
        metadata={},
    )
    data.update(overrides)
    return RecoveryPlan(**data)


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
        ExecutionMonitor(),
        RecoveryManager(),
    )


# =====================================================================
# DTOs
# =====================================================================
class RecoveryModelTests(unittest.TestCase):
    def test_plan_defaults(self):
        plan = RecoveryPlan(
            recovery_id="r1",
            execution_id="e1",
            recovery_strategy="NO_ACTION",
            requires_user_intervention=False,
            recovery_reason="ok",
        )
        self.assertEqual(plan.affected_nodes, [])
        self.assertEqual(plan.recoverable_nodes, [])
        self.assertEqual(plan.unrecoverable_nodes, [])
        self.assertEqual(plan.metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            RecoveryPlan(recovery_id="r1")  # rest missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _plan().recovery_strategy = "ABORT"

    def test_json_round_trip(self):
        plan = _create(
            _report(health="FAILED", active=("n1",), blocked=("n2",)),
            graph=_graph(ready_ids=("n1",), blocked_ids=("n2",)),
        )
        restored = RecoveryPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(restored, plan)

    def test_enum_values(self):
        self.assertEqual(
            {s.value for s in RecoveryStrategy},
            {"NO_ACTION", "RETRY", "RESUME", "REPLAN", "ABORT"},
        )


# =====================================================================
# RecoveryManager — strategy selection (the deterministic rules)
# =====================================================================
class RecoveryStrategyTests(unittest.TestCase):
    def test_healthy_is_no_action(self):
        plan = _create(_report(health="HEALTHY"))
        self.assertEqual(plan.recovery_strategy, "NO_ACTION")

    def test_completed_is_no_action(self):
        plan = _create(_report(health="COMPLETED", active=()))
        self.assertEqual(plan.recovery_strategy, "NO_ACTION")

    def test_warning_is_no_action(self):
        plan = _create(
            _report(health="WARNING", active=("n1",), blocked=("n2",)),
            graph=_graph(ready_ids=("n1",), blocked_ids=("n2",)),
        )
        self.assertEqual(plan.recovery_strategy, "NO_ACTION")

    def test_failed_with_recoverable_is_retry(self):
        plan = _create(
            _report(health="FAILED", active=("n1",), blocked=("n2",)),
            graph=_graph(ready_ids=("n1",), blocked_ids=("n2",)),
        )
        self.assertEqual(plan.recovery_strategy, "RETRY")

    def test_failed_without_recoverable_is_abort(self):
        plan = _create(
            _report(health="FAILED", active=(), blocked=("n2",)),
            graph=_graph(ready_ids=(), blocked_ids=("n2",)),
        )
        self.assertEqual(plan.recovery_strategy, "ABORT")

    def test_blocked_with_executable_path_is_resume(self):
        plan = _create(
            _report(health="BLOCKED", active=(), blocked=("n2",)),
            graph=_graph(ready_ids=("n1",), blocked_ids=("n2",)),
        )
        self.assertEqual(plan.recovery_strategy, "RESUME")

    def test_blocked_deadlock_is_replan(self):
        plan = _create(
            _report(health="BLOCKED", active=(), blocked=("n2",)),
            graph=_graph(ready_ids=(), blocked_ids=("n2",)),
        )
        self.assertEqual(plan.recovery_strategy, "REPLAN")

    def test_blocked_cycle_is_replan(self):
        plan = _create(
            _report(health="BLOCKED", active=(), blocked=("n2",)),
            graph=_graph(
                ready_ids=("n1",), blocked_ids=("n2",), has_cycles=True
            ),
        )
        self.assertEqual(plan.recovery_strategy, "REPLAN")

    def test_empty_execution_is_no_action(self):
        plan = _create(
            _report(health="FAILED", active=(), blocked=()),
            graph=_graph(ready_ids=(), blocked_ids=()),
        )
        self.assertEqual(plan.recovery_strategy, "NO_ACTION")


# =====================================================================
# RecoveryManager — intervention decision
# =====================================================================
class RecoveryInterventionTests(unittest.TestCase):
    def test_no_action_needs_no_intervention(self):
        self.assertFalse(
            _create(_report(health="HEALTHY")).requires_user_intervention
        )

    def test_retry_needs_no_intervention(self):
        plan = _create(
            _report(health="FAILED", active=("n1",), blocked=("n2",)),
            graph=_graph(ready_ids=("n1",), blocked_ids=("n2",)),
        )
        self.assertFalse(plan.requires_user_intervention)

    def test_resume_needs_no_intervention(self):
        plan = _create(
            _report(health="BLOCKED", active=(), blocked=("n2",)),
            graph=_graph(ready_ids=("n1",), blocked_ids=("n2",)),
        )
        self.assertFalse(plan.requires_user_intervention)

    def test_replan_needs_intervention(self):
        plan = _create(
            _report(health="BLOCKED", active=(), blocked=("n2",)),
            graph=_graph(ready_ids=(), blocked_ids=("n2",)),
        )
        self.assertTrue(plan.requires_user_intervention)

    def test_abort_needs_intervention(self):
        plan = _create(
            _report(health="FAILED", active=(), blocked=("n2",)),
            graph=_graph(ready_ids=(), blocked_ids=("n2",)),
        )
        self.assertTrue(plan.requires_user_intervention)


# =====================================================================
# RecoveryManager — affected / recoverable / unrecoverable nodes
# =====================================================================
class RecoveryNodeTests(unittest.TestCase):
    def test_retry_marks_affected_recoverable(self):
        plan = _create(
            _report(health="FAILED", active=("n1",), blocked=("n2",)),
            graph=_graph(ready_ids=("n1",), blocked_ids=("n2",)),
        )
        self.assertEqual(set(plan.affected_nodes), {"n1", "n2"})
        self.assertEqual(set(plan.recoverable_nodes), {"n1", "n2"})
        self.assertEqual(plan.unrecoverable_nodes, [])

    def test_abort_marks_affected_unrecoverable(self):
        plan = _create(
            _report(health="FAILED", active=(), blocked=("n2",)),
            graph=_graph(ready_ids=(), blocked_ids=("n2",)),
        )
        self.assertEqual(plan.affected_nodes, ["n2"])
        self.assertEqual(plan.recoverable_nodes, [])
        self.assertEqual(plan.unrecoverable_nodes, ["n2"])

    def test_no_action_has_no_affected_nodes(self):
        plan = _create(
            _report(health="WARNING", active=("n1",), blocked=("n2",)),
            graph=_graph(ready_ids=("n1",), blocked_ids=("n2",)),
        )
        self.assertEqual(plan.affected_nodes, [])
        self.assertEqual(plan.recoverable_nodes, [])
        self.assertEqual(plan.unrecoverable_nodes, [])

    def test_recoverable_unrecoverable_partition_affected(self):
        plan = _create(
            _report(health="FAILED", active=("n1",), blocked=("n2",)),
            graph=_graph(ready_ids=("n1",), blocked_ids=("n2",)),
        )
        self.assertEqual(
            set(plan.recoverable_nodes) | set(plan.unrecoverable_nodes),
            set(plan.affected_nodes),
        )
        self.assertFalse(
            set(plan.recoverable_nodes) & set(plan.unrecoverable_nodes)
        )

    def test_affected_ordered_by_graph(self):
        graph = _graph(ready_ids=("b",), blocked_ids=("a", "c"))
        report = _report(health="FAILED", active=(), blocked=("c", "a"))
        plan = _create(report, graph=graph)
        self.assertEqual(plan.affected_nodes, ["a", "c"])

    def test_links_execution_and_recovery_id(self):
        plan = _create(state=_state(execution_id="exec-42"))
        self.assertEqual(plan.execution_id, "exec-42")
        self.assertIn("exec-42", plan.recovery_id)

    def test_reason_is_populated(self):
        self.assertTrue(_create().recovery_reason.strip())


# =====================================================================
# RecoveryManager — quality
# =====================================================================
class RecoveryQualityTests(unittest.TestCase):
    def setUp(self):
        self.manager = RecoveryManager()

    def test_deterministic(self):
        report = _report(health="FAILED", active=("n1",), blocked=("n2",))
        state = _state()
        graph = _graph(ready_ids=("n1",), blocked_ids=("n2",))
        self.assertEqual(
            self.manager.create_recovery_plan(report, state, graph),
            self.manager.create_recovery_plan(report, state, graph),
        )

    def test_stateless(self):
        self.assertEqual(vars(self.manager), {})

    def test_does_not_mutate_inputs(self):
        report = _report(health="FAILED", active=("n1",), blocked=("n2",))
        state = _state()
        graph = _graph(ready_ids=("n1",), blocked_ids=("n2",))
        before = (report.model_dump(), state.model_dump(), graph.model_dump())
        self.manager.create_recovery_plan(report, state, graph)
        self.assertEqual(
            (report.model_dump(), state.model_dump(), graph.model_dump()),
            before,
        )

    def test_produces_recovery_plan(self):
        self.assertIsInstance(_create(), RecoveryPlan)


# =====================================================================
# PlanValidator.validate_recovery_plan
# =====================================================================
class ValidateRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_passes(self):
        self.validator.validate_recovery_plan(_plan())

    def test_valid_abort_passes(self):
        self.validator.validate_recovery_plan(
            _plan(
                recovery_strategy="ABORT",
                affected_nodes=["n1"],
                recoverable_nodes=[],
                unrecoverable_nodes=["n1"],
                requires_user_intervention=True,
            )
        )

    def test_empty_recovery_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_recovery_plan(_plan(recovery_id=" "))

    def test_empty_execution_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_recovery_plan(_plan(execution_id=""))

    def test_invalid_strategy_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_recovery_plan(
                _plan(recovery_strategy="PANIC")
            )

    def test_empty_reason_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_recovery_plan(_plan(recovery_reason="   "))

    def test_empty_node_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_recovery_plan(
                _plan(affected_nodes=["n1", " "], recoverable_nodes=["n1"])
            )

    def test_duplicate_node_ids_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_recovery_plan(
                _plan(
                    affected_nodes=["n1", "n1"], recoverable_nodes=["n1"]
                )
            )

    def test_recoverable_not_subset_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_recovery_plan(
                _plan(affected_nodes=["n1"], recoverable_nodes=["x"])
            )

    def test_recoverable_unrecoverable_overlap_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_recovery_plan(
                _plan(
                    affected_nodes=["n1"],
                    recoverable_nodes=["n1"],
                    unrecoverable_nodes=["n1"],
                )
            )

    def test_intervention_on_retry_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_recovery_plan(
                _plan(requires_user_intervention=True)  # RETRY
            )

    def test_missing_intervention_on_replan_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_recovery_plan(
                _plan(
                    recovery_strategy="REPLAN",
                    affected_nodes=["n1"],
                    recoverable_nodes=[],
                    unrecoverable_nodes=["n1"],
                    requires_user_intervention=False,
                )
            )

    def test_no_action_with_affected_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_recovery_plan(
                _plan(
                    recovery_strategy="NO_ACTION",
                    affected_nodes=["n1"],
                    recoverable_nodes=["n1"],
                    unrecoverable_nodes=[],
                    requires_user_intervention=False,
                )
            )

    def test_manager_output_always_validates(self):
        reports_graphs = (
            (_report(health="HEALTHY"), _graph()),
            (
                _report(health="FAILED", active=("n1",), blocked=("n2",)),
                _graph(ready_ids=("n1",), blocked_ids=("n2",)),
            ),
            (
                _report(health="FAILED", active=(), blocked=("n2",)),
                _graph(ready_ids=(), blocked_ids=("n2",)),
            ),
            (
                _report(health="BLOCKED", active=(), blocked=("n2",)),
                _graph(ready_ids=("n1",), blocked_ids=("n2",)),
            ),
            (
                _report(health="BLOCKED", active=(), blocked=("n2",)),
                _graph(ready_ids=(), blocked_ids=("n2",)),
            ),
            (
                _report(health="BLOCKED", active=(), blocked=("n2",)),
                _graph(
                    ready_ids=("n1",), blocked_ids=("n2",), has_cycles=True
                ),
            ),
            (_report(health="WARNING"), _graph()),
            (_report(health="FAILED"), _graph(ready_ids=(), blocked_ids=())),
        )
        for report, graph in reports_graphs:
            with self.subTest(health=report.health_status):
                self.validator.validate_recovery_plan(
                    RecoveryManager().create_recovery_plan(
                        report, _state(), graph
                    )
                )


# =====================================================================
# PlanningExplanationBuilder.build_with_recovery_plan
# =====================================================================
class BuildWithRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )

    def test_describes_retry(self):
        recovery = _create(
            _report(health="FAILED", active=("n1",), blocked=("n2",)),
            graph=_graph(ready_ids=("n1",), blocked_ids=("n2",)),
        )
        text = self.builder.build_with_recovery_plan(self.plan, recovery)
        self.assertIn("retry", text.lower())

    def test_describes_no_action(self):
        recovery = _create(_report(health="HEALTHY"))
        text = self.builder.build_with_recovery_plan(self.plan, recovery)
        self.assertIn("nothing to recover", text.lower())

    def test_intervention_note_for_replan(self):
        recovery = _create(
            _report(health="BLOCKED", active=(), blocked=("n2",)),
            graph=_graph(ready_ids=(), blocked_ids=("n2",)),
        )
        text = self.builder.build_with_recovery_plan(self.plan, recovery)
        self.assertIn("your input", text.lower())

    def test_no_intervention_note_for_retry(self):
        recovery = _create(
            _report(health="FAILED", active=("n1",), blocked=("n2",)),
            graph=_graph(ready_ids=("n1",), blocked_ids=("n2",)),
        )
        text = self.builder.build_with_recovery_plan(self.plan, recovery)
        self.assertNotIn("your input", text.lower())

    def test_reuses_base_narration(self):
        text = self.builder.build_with_recovery_plan(self.plan, _create())
        self.assertIn("I will", text)


# =====================================================================
# PlanningEngine.create_recovery_plan
# =====================================================================
class PlanningEngineCreateRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.report = _report()
        self.state = _state()
        self.graph = _graph()
        self.recovery = _plan()
        self.validator = MagicMock()
        self.manager = MagicMock(name="RecoveryManager")
        self.manager.create_recovery_plan.return_value = self.recovery
        self.engine = PlanningEngine(
            MagicMock(), self.validator, MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), self.manager,
        )

    def test_delegates_to_manager(self):
        self.engine.create_recovery_plan(self.report, self.state, self.graph)
        self.manager.create_recovery_plan.assert_called_once_with(
            self.report, self.state, self.graph
        )

    def test_validates_the_plan(self):
        self.engine.create_recovery_plan(self.report, self.state, self.graph)
        self.validator.validate_recovery_plan.assert_called_once_with(
            self.recovery
        )

    def test_returns_validated_plan_unchanged(self):
        self.assertIs(
            self.engine.create_recovery_plan(
                self.report, self.state, self.graph
            ),
            self.recovery,
        )

    def test_manager_exception_propagates(self):
        self.manager.create_recovery_plan.side_effect = RuntimeError("x")
        with self.assertRaises(RuntimeError):
            self.engine.create_recovery_plan(
                self.report, self.state, self.graph
            )

    def test_manager_stored_as_attribute(self):
        self.assertIs(self.engine.recovery_manager, self.manager)

    def test_engine_without_manager_raises(self):
        engine = PlanningEngine(MagicMock(), MagicMock(), MagicMock())
        with self.assertRaises(RuntimeError):
            engine.create_recovery_plan(self.report, self.state, self.graph)


class PlanningEngineRecoveryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_full_pipeline_produces_valid_recovery_plan(self):
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
        report = self.engine.create_execution_monitoring_report(schedule, state)
        recovery = self.engine.create_recovery_plan(report, state, graph)
        self.assertEqual(recovery.execution_id, state.execution_id)
        self.assertIn(
            recovery.recovery_strategy, {s.value for s in RecoveryStrategy}
        )

    def test_engine_rejects_malformed_recovery_plan(self):
        bad = _plan(recovery_strategy="PANIC")
        manager = MagicMock()
        manager.create_recovery_plan.return_value = bad
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
            ExecutionScheduler(),
            ExecutionMonitor(),
            manager,
        )
        with self.assertRaises(PlanValidationError):
            engine.create_recovery_plan(_report(), _state(), _graph())


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

    def _through_monitor(self):
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
            ExecutionScheduler(),
            ExecutionMonitor(),
        )

    def test_three_arg_engine_keeps_original_attributes(self):
        self.assertEqual(
            set(vars(PlanningEngine(*self._base()))),
            {"provider", "validator", "explanation_builder"},
        )

    def test_fourteen_arg_engine_has_no_recovery_manager(self):
        engine = PlanningEngine(*self._base(), *self._through_monitor())
        self.assertNotIn("recovery_manager", vars(engine))

    def test_fifteen_arg_engine_adds_recovery_manager(self):
        self.assertEqual(
            set(vars(_full_engine())),
            {
                "provider", "validator", "explanation_builder", "analyzer",
                "preparation_engine", "decision_engine", "intent_engine",
                "orchestrator", "coordinator", "lifecycle_engine",
                "state_manager", "dependency_graph_builder", "scheduler",
                "monitor", "recovery_manager",
            },
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class RecoveryDependencyTests(unittest.TestCase):
    def test_get_manager_returns_manager(self):
        from app.core.dependencies import get_recovery_manager

        self.assertIsInstance(get_recovery_manager(), RecoveryManager)

    def test_engine_injects_manager(self):
        from app.core.dependencies import get_planning_engine

        manager = MagicMock()
        engine = get_planning_engine(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), manager,
        )
        self.assertIs(engine.recovery_manager, manager)

    def test_engine_without_manager_backward_compatible(self):
        from app.core.dependencies import get_planning_engine

        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertFalse(hasattr(engine, "recovery_manager"))

    def test_composition_root_end_to_end(self):
        from app.core.dependencies import (
            get_decision_engine,
            get_execution_coordinator,
            get_execution_dependency_graph_builder,
            get_execution_intent_engine,
            get_execution_monitor,
            get_execution_orchestrator,
            get_execution_preparation_engine,
            get_execution_scheduler,
            get_execution_state_manager,
            get_plan_analyzer,
            get_plan_validator,
            get_planning_engine,
            get_planning_explanation_builder,
            get_planning_provider,
            get_recovery_manager,
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
            get_execution_monitor(),
            get_recovery_manager(),
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
        report = engine.create_execution_monitoring_report(schedule, state)
        recovery = engine.create_recovery_plan(report, state, graph)
        self.assertIsInstance(recovery, RecoveryPlan)
        self.assertIn(
            recovery.recovery_strategy, {s.value for s in RecoveryStrategy}
        )
        self.assertTrue(
            engine.explanation_builder.build_with_recovery_plan(plan, recovery)
        )


# =====================================================================
# Regression: Sprint 13.1–13.12 behaviour unchanged
# =====================================================================
class Sprint131To1312RegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_create_plan_unchanged(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_monitoring_report_still_works(self):
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
        report = self.engine.create_execution_monitoring_report(schedule, state)
        self.assertEqual(report.execution_id, state.execution_id)

    def test_base_explanation_still_works(self):
        plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip")
        )
        self.assertIn("I will", PlanningExplanationBuilder().build(plan))


if __name__ == "__main__":
    unittest.main()
