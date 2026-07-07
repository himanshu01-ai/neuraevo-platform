"""Unit tests for the Sprint 13.12 Execution Monitor.

Covers the additive monitoring layer end to end without touching any network,
SDK, AI, tool execution, permission check, registry, runtime, memory, or
database:

* the immutable :class:`ExecutionMonitoringReport` DTO and the
  :class:`ExecutionHealthStatus` enum (defaults, immutability, JSON round-trip);
* the deterministic :class:`ExecutionMonitor` (node grouping, completed-node
  derivation, progress/status echo, health derivation, warnings, empty schedule,
  determinism, statelessness, input non-mutation);
* the extended :class:`PlanValidator` (``validate_execution_monitoring_report``);
* the extended :class:`PlanningExplanationBuilder`
  (``build_with_execution_monitoring_report``);
* the extended :class:`PlanningEngine` (``create_execution_monitoring_report`` +
  backward-compatible injection alongside the 13.2–13.11 collaborators);
* the composition-root wiring (``get_execution_monitor`` + injection); and
* regression that Sprint 13.1–13.11 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_monitor
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
from app.services.planning.execution_intent_engine import ExecutionIntentEngine
from app.services.planning.execution_monitor import ExecutionMonitor
from app.services.planning.execution_monitor_models import (
    ExecutionHealthStatus,
    ExecutionMonitoringReport,
)
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
def _sched_node(node_id, priority):
    return ScheduledNode(
        node_id=node_id,
        execution_unit_id=f"unit-{node_id}",
        priority=priority,
        scheduled=True,
        reason="Ready and selected for execution.",
        metadata={},
    )


def _schedule(
    scheduled=("n1",),
    deferred=("n2",),
    blocked=("n3",),
    strategy="SEQUENTIAL",
    execution_id="exec-x",
):
    nodes = [_sched_node(n, i + 1) for i, n in enumerate(scheduled)]
    return ExecutionSchedule(
        schedule_id=f"schedule-{execution_id}",
        execution_id=execution_id,
        scheduled_nodes=nodes,
        deferred_nodes=list(deferred),
        blocked_nodes=list(blocked),
        execution_order=[n.node_id for n in nodes],
        scheduling_strategy=strategy,
        metadata={},
    )


def _state(
    overall_state="RUNNING",
    progress=0.0,
    failed_tasks=0,
    total_tasks=0,
    execution_id="exec-x",
):
    return ExecutionState(
        execution_id=execution_id,
        overall_state=overall_state,
        total_tasks=total_tasks,
        ready_tasks=0,
        waiting_tasks=0,
        running_tasks=0,
        completed_tasks=0,
        failed_tasks=failed_tasks,
        cancelled_tasks=0,
        skipped_tasks=0,
        progress_percentage=progress,
        active_task_ids=[],
        terminal=False,
        metadata={},
    )


def _create(schedule=None, state=None):
    return ExecutionMonitor().create_report(
        schedule if schedule is not None else _schedule(),
        state if state is not None else _state(),
    )


def _report(**overrides):
    data = dict(
        report_id="monitor-exec-x",
        execution_id="exec-x",
        execution_status="RUNNING",
        overall_progress=50.0,
        active_nodes=["n1"],
        blocked_nodes=["n3"],
        completed_nodes=[],
        pending_nodes=["n2"],
        health_status="HEALTHY",
        warnings=[],
        metadata={},
    )
    data.update(overrides)
    return ExecutionMonitoringReport(**data)


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
    )


# =====================================================================
# DTOs
# =====================================================================
class ReportModelTests(unittest.TestCase):
    def test_report_defaults(self):
        report = ExecutionMonitoringReport(
            report_id="r1",
            execution_id="e1",
            execution_status="RUNNING",
            overall_progress=0.0,
            health_status="HEALTHY",
        )
        self.assertEqual(report.active_nodes, [])
        self.assertEqual(report.blocked_nodes, [])
        self.assertEqual(report.completed_nodes, [])
        self.assertEqual(report.pending_nodes, [])
        self.assertEqual(report.warnings, [])
        self.assertEqual(report.metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionMonitoringReport(report_id="r1")  # rest missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _report().health_status = "FAILED"

    def test_json_round_trip(self):
        report = _create(_schedule(("n1", "n2"), ("n5",), ("n3", "n4")))
        restored = ExecutionMonitoringReport.model_validate_json(
            report.model_dump_json()
        )
        self.assertEqual(restored, report)

    def test_enum_values(self):
        self.assertEqual(
            {s.value for s in ExecutionHealthStatus},
            {"HEALTHY", "WARNING", "BLOCKED", "COMPLETED", "FAILED"},
        )


# =====================================================================
# ExecutionMonitor — node grouping
# =====================================================================
class MonitorGroupingTests(unittest.TestCase):
    def test_scheduled_become_active(self):
        report = _create(_schedule(("n1", "n2"), (), ()))
        self.assertEqual(report.active_nodes, ["n1", "n2"])

    def test_deferred_become_pending(self):
        report = _create(_schedule(("n1",), ("n2", "n3"), ()))
        self.assertEqual(report.pending_nodes, ["n2", "n3"])

    def test_blocked_carried_through(self):
        report = _create(_schedule(("n1",), (), ("n8", "n9")))
        self.assertEqual(report.blocked_nodes, ["n8", "n9"])

    def test_completed_empty_for_forward_schedule(self):
        report = _create(_schedule(("n1", "n2"), ("n3",), ("n4",)))
        self.assertEqual(report.completed_nodes, [])

    def test_groups_are_disjoint(self):
        report = _create(_schedule(("n1", "n2"), ("n3",), ("n4",)))
        sets = [
            set(report.active_nodes),
            set(report.pending_nodes),
            set(report.blocked_nodes),
            set(report.completed_nodes),
        ]
        for first in range(len(sets)):
            for second in range(first + 1, len(sets)):
                self.assertFalse(sets[first] & sets[second])

    def test_links_execution_and_report_id(self):
        report = _create(state=_state(execution_id="exec-42"))
        self.assertEqual(report.execution_id, "exec-42")
        self.assertIn("exec-42", report.report_id)

    def test_metadata_counts(self):
        report = _create(_schedule(("n1", "n2"), ("n3",), ("n4", "n5")))
        self.assertEqual(report.metadata["active_count"], 2)
        self.assertEqual(report.metadata["pending_count"], 1)
        self.assertEqual(report.metadata["blocked_count"], 2)


# =====================================================================
# ExecutionMonitor — status & progress come from ExecutionState
# =====================================================================
class MonitorStateEchoTests(unittest.TestCase):
    def test_status_echoes_state(self):
        report = _create(state=_state(overall_state="WAITING"))
        self.assertEqual(report.execution_status, "WAITING")

    def test_progress_comes_from_state(self):
        report = _create(state=_state(progress=42.0))
        self.assertEqual(report.overall_progress, 42.0)


# =====================================================================
# ExecutionMonitor — health derivation
# =====================================================================
class MonitorHealthTests(unittest.TestCase):
    def test_failed_state_is_failed(self):
        report = _create(state=_state(overall_state="FAILED"))
        self.assertEqual(report.health_status, "FAILED")

    def test_completed_state_is_completed(self):
        report = _create(
            _schedule((), (), ()), _state(overall_state="COMPLETED")
        )
        self.assertEqual(report.health_status, "COMPLETED")

    def test_cancelled_state_is_warning(self):
        report = _create(
            _schedule((), (), ()), _state(overall_state="CANCELLED")
        )
        self.assertEqual(report.health_status, "WARNING")

    def test_blocked_without_active_is_blocked(self):
        report = _create(_schedule((), (), ("n3",)))
        self.assertEqual(report.health_status, "BLOCKED")

    def test_blocked_with_active_is_warning(self):
        report = _create(_schedule(("n1",), (), ("n3",)))
        self.assertEqual(report.health_status, "WARNING")

    def test_active_and_unblocked_is_healthy(self):
        report = _create(_schedule(("n1",), ("n2",), ()))
        self.assertEqual(report.health_status, "HEALTHY")

    def test_pending_without_active_is_warning(self):
        report = _create(_schedule((), ("n2",), ()))
        self.assertEqual(report.health_status, "WARNING")

    def test_empty_schedule_running_is_healthy(self):
        report = _create(_schedule((), (), ()))
        self.assertEqual(report.health_status, "HEALTHY")


# =====================================================================
# ExecutionMonitor — warnings
# =====================================================================
class MonitorWarningTests(unittest.TestCase):
    def test_blocked_warning(self):
        report = _create(_schedule(("n1",), (), ("n3", "n4")))
        self.assertTrue(
            any("blocked" in w.lower() for w in report.warnings)
        )

    def test_failed_state_warning(self):
        report = _create(state=_state(overall_state="FAILED"))
        self.assertTrue(any("failed" in w.lower() for w in report.warnings))

    def test_cancelled_state_warning(self):
        report = _create(
            _schedule((), (), ()), _state(overall_state="CANCELLED")
        )
        self.assertTrue(any("cancelled" in w.lower() for w in report.warnings))

    def test_failed_tasks_warning_when_not_failed_overall(self):
        report = _create(state=_state(failed_tasks=2, total_tasks=3))
        self.assertTrue(
            any("2 task(s) have failed" in w for w in report.warnings)
        )

    def test_healthy_has_no_warnings(self):
        report = _create(_schedule(("n1",), ("n2",), ()))
        self.assertEqual(report.warnings, [])


# =====================================================================
# ExecutionMonitor — empty report & quality
# =====================================================================
class MonitorQualityTests(unittest.TestCase):
    def setUp(self):
        self.monitor = ExecutionMonitor()

    def test_empty_schedule_empty_report(self):
        report = self.monitor.create_report(_schedule((), (), ()), _state())
        self.assertEqual(report.active_nodes, [])
        self.assertEqual(report.pending_nodes, [])
        self.assertEqual(report.blocked_nodes, [])
        self.assertEqual(report.completed_nodes, [])

    def test_deterministic(self):
        schedule = _schedule(("n1", "n2"), ("n3",), ("n4",))
        state = _state(progress=25.0)
        self.assertEqual(
            self.monitor.create_report(schedule, state),
            self.monitor.create_report(schedule, state),
        )

    def test_stateless(self):
        self.assertEqual(vars(self.monitor), {})

    def test_does_not_mutate_inputs(self):
        schedule = _schedule(("n1",), ("n2",), ("n3",))
        state = _state()
        before_sched = schedule.model_dump()
        before_state = state.model_dump()
        self.monitor.create_report(schedule, state)
        self.assertEqual(schedule.model_dump(), before_sched)
        self.assertEqual(state.model_dump(), before_state)

    def test_produces_monitoring_report(self):
        self.assertIsInstance(_create(), ExecutionMonitoringReport)


# =====================================================================
# PlanValidator.validate_execution_monitoring_report
# =====================================================================
class ValidateReportTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_passes(self):
        self.validator.validate_execution_monitoring_report(_report())

    def test_empty_report_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_monitoring_report(
                _report(report_id=" ")
            )

    def test_empty_execution_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_monitoring_report(
                _report(execution_id="")
            )

    def test_invalid_status_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_monitoring_report(
                _report(execution_status="MELTDOWN")
            )

    def test_invalid_health_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_monitoring_report(
                _report(health_status="GREAT")
            )

    def test_progress_out_of_range_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_monitoring_report(
                _report(overall_progress=150.0)
            )

    def test_empty_node_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_monitoring_report(
                _report(active_nodes=["n1", " "])
            )

    def test_duplicate_node_ids_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_monitoring_report(
                _report(active_nodes=["n1", "n1"])
            )

    def test_overlapping_groups_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_monitoring_report(
                _report(active_nodes=["n1"], pending_nodes=["n1"])
            )

    def test_empty_warning_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_monitoring_report(
                _report(warnings=["  "])
            )

    def test_failed_status_requires_failed_health(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_monitoring_report(
                _report(execution_status="FAILED", health_status="HEALTHY")
            )

    def test_completed_status_requires_completed_health(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_monitoring_report(
                _report(
                    execution_status="COMPLETED",
                    health_status="HEALTHY",
                    blocked_nodes=[],
                    pending_nodes=[],
                    active_nodes=[],
                )
            )

    def test_blocked_health_requires_blocked_nodes(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_monitoring_report(
                _report(health_status="BLOCKED", blocked_nodes=[])
            )

    def test_monitor_output_always_validates(self):
        scenarios = (
            _schedule(("n1", "n2"), ("n3",), ("n4",)),
            _schedule((), (), ("n3",)),
            _schedule((), (), ()),
            _schedule(("n1",), (), ()),
        )
        states = (
            _state(overall_state="RUNNING"),
            _state(overall_state="FAILED"),
            _state(overall_state="COMPLETED"),
            _state(overall_state="CANCELLED"),
            _state(overall_state="PARTIALLY_COMPLETED", failed_tasks=1,
                   total_tasks=3),
        )
        for schedule in scenarios:
            for state in states:
                with self.subTest(schedule=schedule, state=state.overall_state):
                    self.validator.validate_execution_monitoring_report(
                        ExecutionMonitor().create_report(schedule, state)
                    )


# =====================================================================
# PlanningExplanationBuilder.build_with_execution_monitoring_report
# =====================================================================
class BuildWithReportTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )

    def test_describes_health_and_progress(self):
        report = _create(
            _schedule(("n1",), ("n2",), ()), _state(progress=40.0)
        )
        text = self.builder.build_with_execution_monitoring_report(
            self.plan, report
        )
        self.assertIn("progressing normally", text)
        self.assertIn("40%", text)

    def test_describes_counts(self):
        report = _create(_schedule(("n1", "n2"), ("n3",), ("n4",)))
        text = self.builder.build_with_execution_monitoring_report(
            self.plan, report
        )
        self.assertIn("2 task(s) active", text)
        self.assertIn("1 waiting", text)
        self.assertIn("1 held up", text)

    def test_blocked_phrase(self):
        report = _create(_schedule((), (), ("n3",)))
        text = self.builder.build_with_execution_monitoring_report(
            self.plan, report
        )
        self.assertIn("on hold", text)

    def test_reuses_base_narration(self):
        text = self.builder.build_with_execution_monitoring_report(
            self.plan, _create()
        )
        self.assertIn("I will", text)


# =====================================================================
# PlanningEngine.create_execution_monitoring_report
# =====================================================================
class PlanningEngineCreateReportTests(unittest.TestCase):
    def setUp(self):
        self.schedule = _schedule()
        self.state = _state()
        self.report = _report()
        self.validator = MagicMock()
        self.monitor = MagicMock(name="Monitor")
        self.monitor.create_report.return_value = self.report
        self.engine = PlanningEngine(
            MagicMock(), self.validator, MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), self.monitor,
        )

    def test_delegates_to_monitor(self):
        self.engine.create_execution_monitoring_report(
            self.schedule, self.state
        )
        self.monitor.create_report.assert_called_once_with(
            self.schedule, self.state
        )

    def test_validates_the_report(self):
        self.engine.create_execution_monitoring_report(
            self.schedule, self.state
        )
        self.validator.validate_execution_monitoring_report.assert_called_once_with(
            self.report
        )

    def test_returns_validated_report_unchanged(self):
        self.assertIs(
            self.engine.create_execution_monitoring_report(
                self.schedule, self.state
            ),
            self.report,
        )

    def test_monitor_exception_propagates(self):
        self.monitor.create_report.side_effect = RuntimeError("x")
        with self.assertRaises(RuntimeError):
            self.engine.create_execution_monitoring_report(
                self.schedule, self.state
            )

    def test_monitor_stored_as_attribute(self):
        self.assertIs(self.engine.monitor, self.monitor)

    def test_engine_without_monitor_raises(self):
        engine = PlanningEngine(MagicMock(), MagicMock(), MagicMock())
        with self.assertRaises(RuntimeError):
            engine.create_execution_monitoring_report(
                self.schedule, self.state
            )


class PlanningEngineReportIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_full_pipeline_produces_valid_report(self):
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
        self.assertEqual(report.execution_status, state.overall_state)
        self.assertIn(
            report.health_status, {s.value for s in ExecutionHealthStatus}
        )

    def test_engine_rejects_malformed_report(self):
        bad = _report(health_status="GREAT")
        monitor = MagicMock()
        monitor.create_report.return_value = bad
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
            monitor,
        )
        with self.assertRaises(PlanValidationError):
            engine.create_execution_monitoring_report(_schedule(), _state())


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

    def _through_scheduler(self):
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
        )

    def test_three_arg_engine_keeps_original_attributes(self):
        self.assertEqual(
            set(vars(PlanningEngine(*self._base()))),
            {"provider", "validator", "explanation_builder"},
        )

    def test_thirteen_arg_engine_has_no_monitor(self):
        engine = PlanningEngine(*self._base(), *self._through_scheduler())
        self.assertNotIn("monitor", vars(engine))

    def test_fourteen_arg_engine_adds_monitor(self):
        self.assertEqual(
            set(vars(_full_engine())),
            {
                "provider", "validator", "explanation_builder", "analyzer",
                "preparation_engine", "decision_engine", "intent_engine",
                "orchestrator", "coordinator", "lifecycle_engine",
                "state_manager", "dependency_graph_builder", "scheduler",
                "monitor",
            },
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class MonitorDependencyTests(unittest.TestCase):
    def test_get_monitor_returns_monitor(self):
        from app.core.dependencies import get_execution_monitor

        self.assertIsInstance(get_execution_monitor(), ExecutionMonitor)

    def test_engine_injects_monitor(self):
        from app.core.dependencies import get_planning_engine

        monitor = MagicMock()
        engine = get_planning_engine(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), monitor,
        )
        self.assertIs(engine.monitor, monitor)

    def test_engine_without_monitor_backward_compatible(self):
        from app.core.dependencies import get_planning_engine

        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertFalse(hasattr(engine, "monitor"))

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
        self.assertIsInstance(report, ExecutionMonitoringReport)
        self.assertIn(
            report.health_status, {s.value for s in ExecutionHealthStatus}
        )
        self.assertTrue(
            engine.explanation_builder.build_with_execution_monitoring_report(
                plan, report
            )
        )


# =====================================================================
# Regression: Sprint 13.1–13.11 behaviour unchanged
# =====================================================================
class Sprint131To1311RegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_create_plan_unchanged(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_schedule_still_works(self):
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
        self.assertEqual(schedule.execution_id, state.execution_id)

    def test_base_explanation_still_works(self):
        plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip")
        )
        self.assertIn("I will", PlanningExplanationBuilder().build(plan))


if __name__ == "__main__":
    unittest.main()
