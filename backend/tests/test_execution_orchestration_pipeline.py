"""Integration tests for the Sprint 13.15 Execution Orchestration pipeline.

Covers the single orchestration coordinator — :meth:`PlanningEngine.
create_execution_orchestration` — which composes every frozen Sprint 13.1–13.14
stage into one deterministic pipeline, plus the
:meth:`PlanningExplanationBuilder.build_execution_pipeline_summary` digest and the
composition-root ``get_execution_orchestration_engine`` seam. This is
integration only: no new DTO, engine, manager, execution, network, SDK, AI, or
database. It verifies:

* the complete end-to-end pipeline (all fourteen stages produced, chained);
* deterministic outputs (same request -> equal result);
* stage ordering (the exact pipeline order);
* propagation of failures (missing collaborator, stage error, validation error);
* no stage skipped;
* no mutation between stages (frozen outputs; re-run stability);
* backward compatibility (orchestration == manual composition; construction shape);
* dependency injection (the wired coordinator); and
* full regression that Sprint 13.1–13.14 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_orchestration_pipeline
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
from app.services.planning.approval_models import ApprovalPlan
from app.services.planning.decision_engine import DecisionEngine
from app.services.planning.decision_models import ExecutionDecision
from app.services.planning.execution_coordinator import ExecutionCoordinator
from app.services.planning.execution_dependency_graph import (
    ExecutionDependencyGraphBuilder,
)
from app.services.planning.execution_dependency_graph_models import (
    ExecutionDependencyGraph,
)
from app.services.planning.execution_intent_engine import ExecutionIntentEngine
from app.services.planning.execution_intent_models import ExecutionIntent
from app.services.planning.execution_monitor import ExecutionMonitor
from app.services.planning.execution_monitor_models import (
    ExecutionMonitoringReport,
)
from app.services.planning.execution_orchestrator import ExecutionOrchestrator
from app.services.planning.execution_preparation_engine import (
    ExecutionPreparationEngine,
)
from app.services.planning.execution_preparation_models import (
    ExecutionPreparation,
)
from app.services.planning.execution_queue_models import ExecutionQueue
from app.services.planning.execution_schedule_models import ExecutionSchedule
from app.services.planning.execution_scheduler import ExecutionScheduler
from app.services.planning.execution_state_manager import ExecutionStateManager
from app.services.planning.execution_state_models import ExecutionState
from app.services.planning.execution_workflow_models import ExecutionWorkflow
from app.services.planning.human_approval_manager import HumanApprovalManager
from app.services.planning.models import ExecutionPlan
from app.services.planning.plan_analyzer import PlanAnalyzer
from app.services.planning.analysis_models import PlanAnalysis
from app.services.planning.planning_engine import ExecutionOrchestrationResult
from app.services.planning.recovery_manager import RecoveryManager
from app.services.planning.recovery_models import RecoveryPlan
from app.services.planning.task_lifecycle_engine import TaskLifecycleEngine
from app.services.planning.task_lifecycle_models import TaskLifecycle


# The pipeline stage methods, in the exact order the coordinator must run them.
STAGES = [
    "create_plan",
    "analyze",
    "prepare",
    "decide",
    "create_execution_intent",
    "create_execution_workflow",
    "create_execution_queue",
    "create_task_lifecycles",
    "create_execution_state",
    "create_execution_dependency_graph",
    "create_execution_schedule",
    "create_execution_monitoring_report",
    "create_recovery_plan",
    "create_approval_plan",
]

# The full set of engine attributes after Sprint 13.14 (unchanged by 13.15).
FULL_ENGINE_ATTRS = {
    "provider", "validator", "explanation_builder", "analyzer",
    "preparation_engine", "decision_engine", "intent_engine", "orchestrator",
    "coordinator", "lifecycle_engine", "state_manager",
    "dependency_graph_builder", "scheduler", "monitor", "recovery_manager",
    "approval_manager",
}


# =====================================================================
# Helpers
# =====================================================================
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
        HumanApprovalManager(),
    )


def _request(text="plan a trip to Japan"):
    return PlanningRequest(user_request=text)


def _run(engine=None, request=None):
    engine = engine if engine is not None else _full_engine()
    return engine.create_execution_orchestration(
        request if request is not None else _request()
    )


def _manual(engine, request):
    """Run the pipeline stage by stage, exactly as the coordinator should."""
    plan = engine.create_plan(request)
    analysis = engine.analyze(plan)
    preparation = engine.prepare(plan, analysis)
    decision = engine.decide(plan, analysis, preparation)
    intent = engine.create_execution_intent(plan, analysis, preparation, decision)
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
    approval = engine.create_approval_plan(intent, schedule, recovery)
    return {
        "plan": plan, "analysis": analysis, "preparation": preparation,
        "decision": decision, "intent": intent, "workflow": workflow,
        "queue": queue, "lifecycles": tuple(lifecycles), "state": state,
        "graph": graph, "schedule": schedule, "monitoring_report": report,
        "recovery_plan": recovery, "approval_plan": approval,
    }


def _record_order(engine):
    """Wrap each stage method to log call order; return the shared list."""
    order = []
    for name in STAGES:
        original = getattr(engine, name)

        def make(stage_name, orig):
            def wrapper(*args, **kwargs):
                order.append(stage_name)
                return orig(*args, **kwargs)
            return wrapper

        setattr(engine, name, make(name, original))
    return order


def _bad_report(execution_id="exec-x"):
    return ExecutionMonitoringReport(
        report_id=f"monitor-{execution_id}",
        execution_id=execution_id,
        execution_status="RUNNING",
        overall_progress=0.0,
        active_nodes=[],
        blocked_nodes=[],
        completed_nodes=[],
        pending_nodes=[],
        health_status="GREAT",  # invalid -> validator rejects
        warnings=[],
        metadata={},
    )


# =====================================================================
# Complete end-to-end pipeline
# =====================================================================
class EndToEndPipelineTests(unittest.TestCase):
    def setUp(self):
        self.result = _run()

    def test_returns_orchestration_result(self):
        self.assertIsInstance(self.result, ExecutionOrchestrationResult)
        self.assertEqual(len(self.result), 14)

    def test_every_stage_output_has_the_right_type(self):
        r = self.result
        self.assertIsInstance(r.plan, ExecutionPlan)
        self.assertIsInstance(r.analysis, PlanAnalysis)
        self.assertIsInstance(r.preparation, ExecutionPreparation)
        self.assertIsInstance(r.decision, ExecutionDecision)
        self.assertIsInstance(r.intent, ExecutionIntent)
        self.assertIsInstance(r.workflow, ExecutionWorkflow)
        self.assertIsInstance(r.queue, ExecutionQueue)
        self.assertIsInstance(r.lifecycles, tuple)
        self.assertTrue(all(isinstance(x, TaskLifecycle) for x in r.lifecycles))
        self.assertIsInstance(r.state, ExecutionState)
        self.assertIsInstance(r.graph, ExecutionDependencyGraph)
        self.assertIsInstance(r.schedule, ExecutionSchedule)
        self.assertIsInstance(r.monitoring_report, ExecutionMonitoringReport)
        self.assertIsInstance(r.recovery_plan, RecoveryPlan)
        self.assertIsInstance(r.approval_plan, ApprovalPlan)

    def test_stages_are_chained_by_execution_id(self):
        r = self.result
        execution_id = r.state.execution_id
        self.assertEqual(r.schedule.execution_id, execution_id)
        self.assertEqual(r.monitoring_report.execution_id, execution_id)
        self.assertEqual(r.recovery_plan.execution_id, execution_id)
        self.assertEqual(r.approval_plan.execution_id, execution_id)

    def test_structural_consistency_across_stages(self):
        r = self.result
        self.assertEqual(len(r.lifecycles), len(r.queue.execution_units))
        self.assertEqual(len(r.graph.nodes), len(r.plan.steps))


# =====================================================================
# Deterministic outputs
# =====================================================================
class DeterminismTests(unittest.TestCase):
    def test_same_request_same_result(self):
        engine = _full_engine()
        self.assertEqual(_run(engine), _run(engine))

    def test_independent_engines_agree(self):
        self.assertEqual(_run(_full_engine()), _run(_full_engine()))

    def test_summary_is_deterministic(self):
        engine = _full_engine()
        r1, r2 = _run(engine), _run(engine)
        builder = PlanningExplanationBuilder()
        self.assertEqual(
            builder.build_execution_pipeline_summary(
                r1.plan, r1.decision, r1.intent, r1.state,
                r1.monitoring_report, r1.recovery_plan, r1.approval_plan,
            ),
            builder.build_execution_pipeline_summary(
                r2.plan, r2.decision, r2.intent, r2.state,
                r2.monitoring_report, r2.recovery_plan, r2.approval_plan,
            ),
        )


# =====================================================================
# Stage ordering & no stage skipped
# =====================================================================
class StageOrderingTests(unittest.TestCase):
    def test_runs_every_stage_in_order(self):
        engine = _full_engine()
        order = _record_order(engine)
        engine.create_execution_orchestration(_request())
        self.assertEqual(order, STAGES)

    def test_no_stage_skipped(self):
        engine = _full_engine()
        order = _record_order(engine)
        engine.create_execution_orchestration(_request())
        self.assertEqual(len(order), len(STAGES))
        self.assertEqual(set(order), set(STAGES))

    def test_each_stage_runs_exactly_once(self):
        engine = _full_engine()
        order = _record_order(engine)
        engine.create_execution_orchestration(_request())
        for stage in STAGES:
            self.assertEqual(order.count(stage), 1)


# =====================================================================
# Propagation of failures
# =====================================================================
class FailurePropagationTests(unittest.TestCase):
    def test_missing_collaborator_propagates(self):
        engine = PlanningEngine(
            HeuristicPlanningProvider(), PlanValidator(),
            PlanningExplanationBuilder(),
        )  # no analyzer or downstream collaborators
        with self.assertRaises(RuntimeError):
            engine.create_execution_orchestration(_request())

    def test_stage_error_propagates_and_aborts(self):
        engine = _full_engine()
        engine.create_recovery_plan = MagicMock(
            side_effect=RuntimeError("boom")
        )
        engine.create_approval_plan = MagicMock(name="approval")
        with self.assertRaises(RuntimeError):
            engine.create_execution_orchestration(_request())
        # The stage after the failure never runs.
        engine.create_approval_plan.assert_not_called()

    def test_validation_failure_propagates(self):
        engine = _full_engine()
        engine.monitor = MagicMock()
        engine.monitor.create_report.return_value = _bad_report()
        with self.assertRaises(PlanValidationError):
            engine.create_execution_orchestration(_request())

    def test_provider_exception_propagates(self):
        engine = _full_engine()
        engine.provider = MagicMock()
        engine.provider.create_plan.side_effect = ValueError("bad request")
        with self.assertRaises(ValueError):
            engine.create_execution_orchestration(_request())


# =====================================================================
# No mutation between stages
# =====================================================================
class NoMutationTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()
        self.result = _run(self.engine)

    def test_result_dtos_are_frozen(self):
        with self.assertRaises(ValidationError):
            self.result.plan.goal = "changed"
        with self.assertRaises(ValidationError):
            self.result.state.overall_state = "FAILED"
        with self.assertRaises(ValidationError):
            self.result.approval_plan.approval_strategy = "NO_APPROVAL"

    def test_result_container_is_immutable(self):
        with self.assertRaises(AttributeError):
            self.result.plan = None

    def test_rerunning_downstream_stages_is_stable(self):
        r = self.result
        self.assertEqual(
            self.engine.create_execution_monitoring_report(r.schedule, r.state),
            r.monitoring_report,
        )
        self.assertEqual(
            self.engine.create_recovery_plan(
                r.monitoring_report, r.state, r.graph
            ),
            r.recovery_plan,
        )
        self.assertEqual(
            self.engine.create_approval_plan(
                r.intent, r.schedule, r.recovery_plan
            ),
            r.approval_plan,
        )


# =====================================================================
# Backward compatibility
# =====================================================================
class BackwardCompatibilityTests(unittest.TestCase):
    def test_orchestration_equals_manual_composition(self):
        engine = _full_engine()
        request = _request()
        result = engine.create_execution_orchestration(request)
        manual = _manual(_full_engine(), request)
        for field, value in manual.items():
            with self.subTest(field=field):
                self.assertEqual(getattr(result, field), value)

    def test_three_arg_engine_still_constructs(self):
        engine = PlanningEngine(
            HeuristicPlanningProvider(), PlanValidator(),
            PlanningExplanationBuilder(),
        )
        self.assertEqual(
            set(vars(engine)),
            {"provider", "validator", "explanation_builder"},
        )
        # The classic three-argument API keeps working.
        plan = engine.create_plan(_request())
        self.assertTrue(engine.explain(plan))

    def test_construction_shape_unchanged_by_integration(self):
        self.assertEqual(set(vars(_full_engine())), FULL_ENGINE_ATTRS)

    def test_per_stage_methods_still_callable_standalone(self):
        engine = _full_engine()
        plan = engine.create_plan(_request())
        self.assertEqual(plan.goal, "Plan your trip")
        analysis = engine.analyze(plan)
        self.assertIsInstance(analysis, PlanAnalysis)


# =====================================================================
# ExplanationBuilder.build_execution_pipeline_summary
# =====================================================================
class PipelineSummaryTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.result = _run()

    def _summary(self):
        r = self.result
        return self.builder.build_execution_pipeline_summary(
            r.plan, r.decision, r.intent, r.state, r.monitoring_report,
            r.recovery_plan, r.approval_plan,
        )

    def test_reuses_base_narration(self):
        self.assertIn("I will", self._summary())

    def test_mentions_progress(self):
        self.assertIn("Progress:", self._summary())

    def test_is_nonempty_digest(self):
        self.assertGreater(len(self._summary()), len(self.builder.build(
            self.result.plan
        )))

    def test_uses_only_existing_dtos(self):
        # Smoke: the summary builds from the frozen stage DTOs without error.
        self.assertIsInstance(self._summary(), str)


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class OrchestrationDependencyTests(unittest.TestCase):
    def test_provider_returns_wired_engine(self):
        from app.core.dependencies import get_execution_orchestration_engine

        engine = get_execution_orchestration_engine()
        self.assertIsInstance(engine, PlanningEngine)
        self.assertEqual(set(vars(engine)), FULL_ENGINE_ATTRS)

    def test_wired_engine_runs_pipeline(self):
        from app.core.dependencies import get_execution_orchestration_engine

        engine = get_execution_orchestration_engine()
        result = engine.create_execution_orchestration(_request())
        self.assertIsInstance(result, ExecutionOrchestrationResult)
        self.assertIsInstance(result.approval_plan, ApprovalPlan)

    def test_wired_engine_summary_builds(self):
        from app.core.dependencies import get_execution_orchestration_engine

        engine = get_execution_orchestration_engine()
        r = engine.create_execution_orchestration(_request())
        self.assertTrue(
            engine.explanation_builder.build_execution_pipeline_summary(
                r.plan, r.decision, r.intent, r.state, r.monitoring_report,
                r.recovery_plan, r.approval_plan,
            )
        )

    def test_existing_planning_engine_provider_unchanged(self):
        from app.core.dependencies import get_planning_engine

        # Backward-compatible three-argument DI keeps its original shape.
        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertFalse(hasattr(engine, "approval_manager"))


# =====================================================================
# Full regression: Sprint 13.1–13.14 behaviour unchanged
# =====================================================================
class Sprint131To1314RegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_create_plan_unchanged(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_full_manual_pipeline_still_works(self):
        result = _manual(self.engine, _request())
        self.assertIsInstance(result["approval_plan"], ApprovalPlan)
        self.assertEqual(
            result["approval_plan"].execution_id, result["state"].execution_id
        )

    def test_base_explanation_still_works(self):
        plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip")
        )
        self.assertIn("I will", PlanningExplanationBuilder().build(plan))


if __name__ == "__main__":
    unittest.main()
