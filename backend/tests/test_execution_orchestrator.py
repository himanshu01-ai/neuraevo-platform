"""Unit tests for the Sprint 13.6 Execution Orchestrator.

Covers the additive workflow layer end to end without touching any network, SDK,
AI, tool execution, permission check, registry, runtime, memory, or database:

* the immutable :class:`ExecutionWorkflow` / :class:`WorkflowStep` DTOs and the
  :class:`WorkflowStatus` / :class:`ExecutionMode` enums (defaults, immutability,
  JSON round-trip);
* the deterministic :class:`ExecutionOrchestrator` (mode mapping, status
  mapping, step ordering + grouping, resumability, workflow id, determinism,
  statelessness, purity);
* the extended :class:`PlanValidator` (``validate_execution_workflow``);
* the extended :class:`PlanningExplanationBuilder` (``build_with_execution_workflow``);
* the extended :class:`PlanningEngine` (``create_execution_workflow`` +
  backward-compatible injection alongside the 13.2–13.5 collaborators);
* the composition-root wiring (``get_execution_orchestrator`` + injection); and
* regression that Sprint 13.1–13.5 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_orchestrator
"""

import unittest
from unittest.mock import MagicMock

from pydantic import ValidationError

from app.services.planning import (
    ExecutionPlan,
    ExecutionStep,
    HeuristicPlanningProvider,
    PlanningEngine,
    PlanningExplanationBuilder,
    PlanningRequest,
    PlanValidationError,
    PlanValidator,
)
from app.services.planning.decision_engine import DecisionEngine
from app.services.planning.execution_intent_engine import ExecutionIntentEngine
from app.services.planning.execution_intent_models import ExecutionIntent
from app.services.planning.execution_orchestrator import ExecutionOrchestrator
from app.services.planning.execution_preparation_engine import (
    ExecutionPreparationEngine,
)
from app.services.planning.execution_preparation_models import (
    ExecutionPreparation,
)
from app.services.planning.execution_workflow_models import (
    ExecutionMode,
    ExecutionWorkflow,
    WorkflowStatus,
    WorkflowStep,
)
from app.services.planning.plan_analyzer import PlanAnalyzer


# =====================================================================
# Helpers
# =====================================================================
def _plan(goal="Do the thing", steps=4):
    return ExecutionPlan(
        goal=goal,
        summary="A short summary of the plan.",
        steps=[
            ExecutionStep(
                step_number=i + 1,
                description=f"Step {i + 1}",
                reason="Because it is needed.",
                dependencies=[i] if i > 0 else [],
            )
            for i in range(steps)
        ],
    )


def _prep(strategy="Sequential"):
    return ExecutionPreparation(
        required_capabilities=[],
        external_services=[],
        permissions_required=[],
        estimated_execution_steps=4,
        can_execute_immediately=True,
        blocked_by=[],
        execution_strategy=strategy,
    )


def _intent(intent_type="EXECUTE_NOW"):
    return ExecutionIntent(
        intent=intent_type,
        should_execute=intent_type == "EXECUTE_NOW",
        requires_user_action=intent_type == "WAIT_FOR_USER",
        recommended_next_step="next",
        execution_priority=1,
        defer_reason="Deferred until resolved: x." if intent_type == "DEFER" else "",
    )


def _decision(status="APPROVED"):
    from app.services.planning.decision_models import ExecutionDecision

    return ExecutionDecision(
        status=status,
        can_execute=status == "APPROVED",
        reason="reason",
        blocking_reasons=[],
        confidence=1.0,
    )


def _workflow(**overrides):
    data = dict(
        workflow_id="wf-abc123",
        workflow_status=WorkflowStatus.READY.value,
        ordered_steps=[
            WorkflowStep(step_number=1, description="A", group=1),
            WorkflowStep(step_number=2, description="B", group=2, depends_on=[1]),
        ],
        estimated_total_steps=2,
        execution_mode=ExecutionMode.SEQUENTIAL.value,
        resumable=True,
        metadata={},
    )
    data.update(overrides)
    return ExecutionWorkflow(**data)


def _create(plan, prep, intent, decision=None):
    return ExecutionOrchestrator().create_workflow(
        plan, MagicMock(), prep, decision or _decision(), intent
    )


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
    )


# =====================================================================
# DTOs / enums
# =====================================================================
class ExecutionWorkflowModelTests(unittest.TestCase):
    def test_defaults(self):
        workflow = ExecutionWorkflow(
            workflow_id="wf-1",
            workflow_status="READY",
            estimated_total_steps=0,
            execution_mode="SEQUENTIAL",
            resumable=False,
        )
        self.assertEqual(workflow.ordered_steps, [])
        self.assertEqual(workflow.metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionWorkflow(workflow_id="wf-1")  # others missing

    def test_is_immutable(self):
        with self.assertRaises(ValidationError):
            _workflow().resumable = False

    def test_step_is_immutable(self):
        with self.assertRaises(ValidationError):
            WorkflowStep(step_number=1, description="A", group=1).group = 2

    def test_json_round_trip(self):
        workflow = _workflow()
        restored = ExecutionWorkflow.model_validate_json(
            workflow.model_dump_json()
        )
        self.assertEqual(restored, workflow)

    def test_enum_values(self):
        self.assertEqual(
            {s.value for s in WorkflowStatus},
            {"PLANNED", "READY", "WAITING", "BLOCKED"},
        )
        self.assertEqual(
            {m.value for m in ExecutionMode},
            {"SEQUENTIAL", "PARALLEL", "HYBRID"},
        )


# =====================================================================
# ExecutionOrchestrator — mode mapping & grouping
# =====================================================================
class WorkflowModeTests(unittest.TestCase):
    def test_sequential_gives_one_group_per_step(self):
        workflow = _create(_plan(steps=4), _prep("Sequential"), _intent())
        self.assertEqual(workflow.execution_mode, "SEQUENTIAL")
        self.assertEqual(
            [s.group for s in workflow.ordered_steps], [1, 2, 3, 4]
        )

    def test_parallel_groups_all_steps_together(self):
        workflow = _create(_plan(steps=4), _prep("Parallel"), _intent())
        self.assertEqual(workflow.execution_mode, "PARALLEL")
        self.assertEqual(
            [s.group for s in workflow.ordered_steps], [1, 1, 1, 1]
        )

    def test_hybrid_groups_steps_in_pairs(self):
        workflow = _create(_plan(steps=6), _prep("Hybrid"), _intent())
        self.assertEqual(workflow.execution_mode, "HYBRID")
        self.assertEqual(
            [s.group for s in workflow.ordered_steps], [1, 1, 2, 2, 3, 3]
        )

    def test_unknown_strategy_defaults_sequential(self):
        workflow = _create(_plan(steps=2), _prep("Mystery"), _intent())
        self.assertEqual(workflow.execution_mode, "SEQUENTIAL")

    def test_ordering_and_dependencies_preserved(self):
        plan = _plan(steps=3)
        workflow = _create(plan, _prep("Sequential"), _intent())
        self.assertEqual(
            [s.step_number for s in workflow.ordered_steps], [1, 2, 3]
        )
        self.assertEqual(workflow.ordered_steps[1].depends_on, [1])


# =====================================================================
# ExecutionOrchestrator — status & resumability mapping
# =====================================================================
class WorkflowStatusTests(unittest.TestCase):
    def test_execute_now_is_ready(self):
        workflow = _create(_plan(), _prep(), _intent("EXECUTE_NOW"))
        self.assertEqual(workflow.workflow_status, "READY")
        self.assertTrue(workflow.resumable)

    def test_wait_for_user_is_waiting(self):
        workflow = _create(_plan(), _prep(), _intent("WAIT_FOR_USER"))
        self.assertEqual(workflow.workflow_status, "WAITING")
        self.assertTrue(workflow.resumable)

    def test_defer_is_blocked(self):
        workflow = _create(_plan(), _prep(), _intent("DEFER"))
        self.assertEqual(workflow.workflow_status, "BLOCKED")
        self.assertTrue(workflow.resumable)

    def test_cancel_is_planned_and_not_resumable(self):
        workflow = _create(_plan(), _prep(), _intent("CANCEL"))
        self.assertEqual(workflow.workflow_status, "PLANNED")
        self.assertFalse(workflow.resumable)


# =====================================================================
# ExecutionOrchestrator — id, counts, metadata, quality
# =====================================================================
class WorkflowContentTests(unittest.TestCase):
    def setUp(self):
        self.orchestrator = ExecutionOrchestrator()

    def test_estimated_total_matches_steps(self):
        workflow = _create(_plan(steps=5), _prep(), _intent())
        self.assertEqual(workflow.estimated_total_steps, 5)
        self.assertEqual(len(workflow.ordered_steps), 5)

    def test_workflow_id_is_non_empty_and_prefixed(self):
        workflow = _create(_plan(), _prep(), _intent())
        self.assertTrue(workflow.workflow_id.startswith("wf-"))

    def test_workflow_id_deterministic_and_content_sensitive(self):
        a = _create(_plan(goal="Alpha"), _prep(), _intent())
        b = _create(_plan(goal="Alpha"), _prep(), _intent())
        c = _create(_plan(goal="Beta"), _prep(), _intent())
        self.assertEqual(a.workflow_id, b.workflow_id)
        self.assertNotEqual(a.workflow_id, c.workflow_id)

    def test_metadata_records_context(self):
        workflow = _create(
            _plan(), _prep("Parallel"), _intent("WAIT_FOR_USER"),
            _decision("WAITING_FOR_INFORMATION"),
        )
        self.assertEqual(workflow.metadata["source_intent"], "WAIT_FOR_USER")
        self.assertEqual(
            workflow.metadata["decision_status"], "WAITING_FOR_INFORMATION"
        )
        self.assertEqual(workflow.metadata["group_count"], 1)

    def test_empty_plan_yields_empty_workflow(self):
        empty = ExecutionPlan(goal="g", summary="s", steps=[])
        workflow = _create(empty, _prep(), _intent("CANCEL"))
        self.assertEqual(workflow.ordered_steps, [])
        self.assertEqual(workflow.estimated_total_steps, 0)

    def test_deterministic(self):
        plan, prep, intent, decision = (
            _plan(steps=6), _prep("Hybrid"), _intent("DEFER"), _decision("BLOCKED")
        )
        analysis = MagicMock()
        self.assertEqual(
            self.orchestrator.create_workflow(plan, analysis, prep, decision, intent),
            self.orchestrator.create_workflow(plan, analysis, prep, decision, intent),
        )

    def test_stateless(self):
        self.assertEqual(vars(self.orchestrator), {})

    def test_does_not_mutate_plan(self):
        plan = _plan(steps=4)
        before = plan.model_dump()
        _create(plan, _prep(), _intent())
        self.assertEqual(plan.model_dump(), before)

    def test_produces_execution_workflow(self):
        self.assertIsInstance(
            _create(_plan(), _prep(), _intent()), ExecutionWorkflow
        )


# =====================================================================
# PlanValidator.validate_execution_workflow
# =====================================================================
class ValidateWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_workflow_passes(self):
        self.validator.validate_execution_workflow(_workflow())  # no raise

    def test_empty_workflow_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_workflow(_workflow(workflow_id="  "))

    def test_invalid_status_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_workflow(
                _workflow(workflow_status="RUNNING")
            )

    def test_invalid_mode_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_workflow(
                _workflow(execution_mode="TELEPATHIC")
            )

    def test_negative_total_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_workflow(
                _workflow(ordered_steps=[], estimated_total_steps=-1)
            )

    def test_count_mismatch_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_workflow(
                _workflow(estimated_total_steps=99)
            )

    def test_duplicate_step_numbers_rejected(self):
        workflow = _workflow(
            ordered_steps=[
                WorkflowStep(step_number=1, description="A", group=1),
                WorkflowStep(step_number=1, description="B", group=2),
            ],
            estimated_total_steps=2,
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_workflow(workflow)

    def test_non_positive_group_rejected(self):
        workflow = _workflow(
            ordered_steps=[
                WorkflowStep(step_number=1, description="A", group=0),
            ],
            estimated_total_steps=1,
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_workflow(workflow)

    def test_orchestrator_output_always_validates(self):
        for strategy in ("Sequential", "Parallel", "Hybrid"):
            for intent_type in ("EXECUTE_NOW", "WAIT_FOR_USER", "DEFER", "CANCEL"):
                with self.subTest(strategy=strategy, intent=intent_type):
                    workflow = _create(
                        _plan(steps=5), _prep(strategy), _intent(intent_type)
                    )
                    self.validator.validate_execution_workflow(workflow)


# =====================================================================
# PlanningExplanationBuilder.build_with_execution_workflow
# =====================================================================
class BuildWithWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.plan = _plan()

    def test_ready_message(self):
        text = self.builder.build_with_execution_workflow(
            self.plan, _workflow(workflow_status="READY")
        )
        self.assertIn("ready to run", text)

    def test_mentions_mode_and_step_count(self):
        text = self.builder.build_with_execution_workflow(
            self.plan,
            _workflow(execution_mode="PARALLEL", estimated_total_steps=2),
        )
        self.assertIn("several steps at once", text)
        self.assertIn("2 steps", text)

    def test_resumable_note(self):
        text = self.builder.build_with_execution_workflow(
            self.plan, _workflow(resumable=True)
        )
        self.assertIn("paused and resumed", text)

    def test_non_resumable_omits_note(self):
        text = self.builder.build_with_execution_workflow(
            self.plan,
            _workflow(
                workflow_status="PLANNED", resumable=False
            ),
        )
        self.assertNotIn("paused and resumed", text)

    def test_reuses_base_narration(self):
        text = self.builder.build_with_execution_workflow(self.plan, _workflow())
        self.assertIn("I will", text)


# =====================================================================
# PlanningEngine.create_execution_workflow
# =====================================================================
class PlanningEngineCreateWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.plan = _plan()
        self.analysis = MagicMock()
        self.preparation = MagicMock()
        self.decision = MagicMock()
        self.intent = MagicMock()
        self.workflow = _workflow()
        self.validator = MagicMock()
        self.orchestrator = MagicMock(name="ExecutionOrchestrator")
        self.orchestrator.create_workflow.return_value = self.workflow
        self.engine = PlanningEngine(
            MagicMock(),
            self.validator,
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            self.orchestrator,
        )

    def test_delegates_to_orchestrator_with_all_inputs(self):
        self.engine.create_execution_workflow(
            self.plan, self.analysis, self.preparation, self.decision, self.intent
        )
        self.orchestrator.create_workflow.assert_called_once_with(
            self.plan, self.analysis, self.preparation, self.decision, self.intent
        )

    def test_validates_the_workflow(self):
        self.engine.create_execution_workflow(
            self.plan, self.analysis, self.preparation, self.decision, self.intent
        )
        self.validator.validate_execution_workflow.assert_called_once_with(
            self.workflow
        )

    def test_returns_validated_workflow_unchanged(self):
        self.assertIs(
            self.engine.create_execution_workflow(
                self.plan, self.analysis, self.preparation, self.decision,
                self.intent,
            ),
            self.workflow,
        )

    def test_orchestrator_exception_propagates(self):
        self.orchestrator.create_workflow.side_effect = RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            self.engine.create_execution_workflow(
                self.plan, self.analysis, self.preparation, self.decision,
                self.intent,
            )

    def test_orchestrator_stored_as_attribute(self):
        self.assertIs(self.engine.orchestrator, self.orchestrator)

    def test_engine_without_orchestrator_raises(self):
        engine = PlanningEngine(MagicMock(), MagicMock(), MagicMock())
        with self.assertRaises(RuntimeError):
            engine.create_execution_workflow(
                self.plan, self.analysis, self.preparation, self.decision,
                self.intent,
            )


class PlanningEngineWorkflowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_full_pipeline_produces_valid_workflow(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="business strategy grow revenue")
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
        self.assertEqual(workflow.execution_mode, "PARALLEL")
        self.assertEqual(
            workflow.estimated_total_steps, len(plan.steps)
        )

    def test_engine_rejects_malformed_workflow(self):
        bad = _workflow(workflow_status="RUNNING")
        orchestrator = MagicMock()
        orchestrator.create_workflow.return_value = bad
        engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            DecisionEngine(),
            ExecutionIntentEngine(),
            orchestrator,
        )
        with self.assertRaises(PlanValidationError):
            engine.create_execution_workflow(
                _plan(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
            )


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

    def test_seven_arg_engine_has_no_orchestrator(self):
        engine = PlanningEngine(
            *self._base(),
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            DecisionEngine(),
            ExecutionIntentEngine(),
        )
        self.assertNotIn("orchestrator", vars(engine))

    def test_eight_arg_engine_adds_orchestrator(self):
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
            },
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class ExecutionOrchestratorDependencyTests(unittest.TestCase):
    def test_get_execution_orchestrator_returns_orchestrator(self):
        from app.core.dependencies import get_execution_orchestrator

        self.assertIsInstance(
            get_execution_orchestrator(), ExecutionOrchestrator
        )

    def test_engine_injects_orchestrator(self):
        from app.core.dependencies import get_planning_engine

        orchestrator = MagicMock()
        engine = get_planning_engine(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), orchestrator,
        )
        self.assertIs(engine.orchestrator, orchestrator)

    def test_engine_without_orchestrator_backward_compatible(self):
        from app.core.dependencies import get_planning_engine

        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertFalse(hasattr(engine, "orchestrator"))

    def test_composition_root_end_to_end(self):
        from app.core.dependencies import (
            get_decision_engine,
            get_execution_intent_engine,
            get_execution_orchestrator,
            get_execution_preparation_engine,
            get_plan_analyzer,
            get_plan_validator,
            get_planning_engine,
            get_planning_explanation_builder,
            get_planning_provider,
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
        self.assertIsInstance(workflow, ExecutionWorkflow)
        self.assertIn(workflow.workflow_status, {s.value for s in WorkflowStatus})
        self.assertTrue(
            engine.explanation_builder.build_with_execution_workflow(
                plan, workflow
            )
        )


# =====================================================================
# Regression: Sprint 13.1–13.5 behaviour unchanged
# =====================================================================
class Sprint131To135RegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_create_plan_unchanged(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_intent_still_works(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="plan a vacation")
        )
        analysis = self.engine.analyze(plan)
        preparation = self.engine.prepare(plan, analysis)
        decision = self.engine.decide(plan, analysis, preparation)
        intent = self.engine.create_execution_intent(
            plan, analysis, preparation, decision
        )
        self.assertEqual(intent.intent, "WAIT_FOR_USER")

    def test_base_explanation_still_works(self):
        self.assertIn("I will", PlanningExplanationBuilder().build(_plan()))


if __name__ == "__main__":
    unittest.main()
