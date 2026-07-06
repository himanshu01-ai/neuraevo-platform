"""Unit tests for the Sprint 13.4 Decision Engine.

Covers the additive decision layer end to end without touching any network, SDK,
AI, tool execution, permission check, registry, runtime, memory, or database:

* the immutable :class:`ExecutionDecision` DTO and :class:`DecisionStatus` enum
  (defaults, immutability, JSON round-trip);
* the deterministic :class:`DecisionEngine` (all five statuses, precedence,
  can_execute, blocking reasons, confidence carry-through, determinism,
  statelessness, purity);
* the extended :class:`PlanValidator` (``validate_decision`` status/reason/
  confidence/consistency/duplicate checks);
* the extended :class:`PlanningExplanationBuilder` (``build_with_decision``);
* the extended :class:`PlanningEngine` (``decide`` + backward-compatible
  injection alongside the 13.2 analyzer and 13.3 preparation engine);
* the composition-root wiring (``get_decision_engine`` + injection); and
* regression that Sprint 13.1–13.3 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_decision_engine
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
from app.services.planning.decision_models import (
    DecisionStatus,
    ExecutionDecision,
)
from app.services.planning.execution_preparation_engine import (
    ExecutionPreparationEngine,
)
from app.services.planning.plan_analyzer import PlanAnalyzer


# =====================================================================
# Helpers
# =====================================================================
def _plan(category="", missing=None, confirm=False, steps=2):
    return ExecutionPlan(
        goal="Do the thing",
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
        missing_information=missing or [],
        requires_user_confirmation=confirm,
        metadata={"category": category} if category else {},
    )


def _derive(plan):
    """Produce consistent analysis + preparation for ``plan`` (real components)."""
    return PlanAnalyzer().analyze(plan), ExecutionPreparationEngine().prepare(plan)


def _decide(plan):
    analysis, preparation = _derive(plan)
    return DecisionEngine().decide(plan, analysis, preparation)


def _decision(**overrides):
    data = dict(
        status=DecisionStatus.APPROVED.value,
        can_execute=True,
        reason="All prerequisites are satisfied.",
        blocking_reasons=[],
        confidence=1.0,
    )
    data.update(overrides)
    return ExecutionDecision(**data)


def _full_engine():
    return PlanningEngine(
        HeuristicPlanningProvider(),
        PlanValidator(),
        PlanningExplanationBuilder(),
        PlanAnalyzer(),
        ExecutionPreparationEngine(),
        DecisionEngine(),
    )


# =====================================================================
# ExecutionDecision DTO / DecisionStatus enum
# =====================================================================
class ExecutionDecisionModelTests(unittest.TestCase):
    def test_blocking_reasons_default_empty(self):
        decision = ExecutionDecision(
            status="APPROVED",
            can_execute=True,
            reason="ok",
            confidence=1.0,
        )
        self.assertEqual(decision.blocking_reasons, [])

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionDecision(status="APPROVED")  # others missing

    def test_is_immutable(self):
        decision = _decision()
        with self.assertRaises(ValidationError):
            decision.can_execute = False

    def test_json_round_trip(self):
        decision = _decision(
            status="BLOCKED",
            can_execute=False,
            blocking_reasons=["Need Permission"],
            confidence=0.8,
        )
        restored = ExecutionDecision.model_validate_json(
            decision.model_dump_json()
        )
        self.assertEqual(restored, decision)

    def test_status_enum_values(self):
        self.assertEqual(
            {s.value for s in DecisionStatus},
            {
                "APPROVED",
                "WAITING_FOR_INFORMATION",
                "WAITING_FOR_CONFIRMATION",
                "BLOCKED",
                "REJECTED",
            },
        )


# =====================================================================
# DecisionEngine — classification of every status
# =====================================================================
class DecisionClassificationTests(unittest.TestCase):
    def test_approved_when_ready_and_unblocked(self):
        decision = _decide(_plan(category="", missing=[], confirm=False))
        self.assertEqual(decision.status, "APPROVED")
        self.assertTrue(decision.can_execute)
        self.assertEqual(decision.blocking_reasons, [])

    def test_waiting_for_information_when_missing(self):
        decision = _decide(_plan(missing=["the destination"]))
        self.assertEqual(decision.status, "WAITING_FOR_INFORMATION")
        self.assertFalse(decision.can_execute)

    def test_waiting_for_confirmation_when_only_confirmation_pending(self):
        decision = _decide(_plan(category="", missing=[], confirm=True))
        self.assertEqual(decision.status, "WAITING_FOR_CONFIRMATION")
        self.assertFalse(decision.can_execute)

    def test_blocked_when_hard_requirements(self):
        decision = _decide(_plan(category="study", missing=[], confirm=False))
        self.assertEqual(decision.status, "BLOCKED")
        self.assertFalse(decision.can_execute)

    def test_rejected_when_no_steps(self):
        decision = _decide(_plan(steps=0))
        self.assertEqual(decision.status, "REJECTED")
        self.assertFalse(decision.can_execute)
        self.assertEqual(decision.blocking_reasons, ["Plan has no steps"])

    def test_information_precedence_over_blocked_and_confirmation(self):
        # A travel plan is missing dates AND has hard blockers AND needs
        # confirmation: information wins by precedence.
        decision = _decide(
            _plan(category="travel", missing=["dates"], confirm=True)
        )
        self.assertEqual(decision.status, "WAITING_FOR_INFORMATION")

    def test_blocked_precedence_over_confirmation(self):
        decision = _decide(
            _plan(category="study", missing=[], confirm=True)
        )
        self.assertEqual(decision.status, "BLOCKED")


# =====================================================================
# DecisionEngine — decision content
# =====================================================================
class DecisionContentTests(unittest.TestCase):
    def setUp(self):
        self.engine = DecisionEngine()

    def test_can_execute_only_when_approved(self):
        approved = _decide(_plan(category="", missing=[], confirm=False))
        self.assertTrue(approved.can_execute)
        for plan in (
            _plan(missing=["x"]),
            _plan(confirm=True),
            _plan(category="study"),
            _plan(steps=0),
        ):
            self.assertFalse(_decide(plan).can_execute)

    def test_reason_is_non_empty(self):
        for plan in (
            _plan(category="", missing=[], confirm=False),
            _plan(missing=["x"]),
            _plan(confirm=True),
            _plan(category="study"),
            _plan(steps=0),
        ):
            self.assertTrue(_decide(plan).reason.strip())

    def test_confidence_carried_from_analysis(self):
        plan = _plan(missing=["a", "b"], confirm=True)
        analysis, preparation = _derive(plan)
        decision = self.engine.decide(plan, analysis, preparation)
        self.assertEqual(decision.confidence, analysis.confidence)

    def test_blocking_reasons_mirror_preparation(self):
        plan = _plan(category="study", missing=[], confirm=False)
        analysis, preparation = _derive(plan)
        decision = self.engine.decide(plan, analysis, preparation)
        self.assertEqual(decision.blocking_reasons, list(preparation.blocked_by))

    def test_blocking_reasons_never_empty_strings(self):
        decision = _decide(
            _plan(category="travel", missing=["x"], confirm=True)
        )
        self.assertTrue(all(b.strip() for b in decision.blocking_reasons))


# =====================================================================
# DecisionEngine — determinism / statelessness / purity
# =====================================================================
class DecisionEngineQualityTests(unittest.TestCase):
    def setUp(self):
        self.engine = DecisionEngine()

    def test_deterministic(self):
        plan = _plan(category="travel", missing=["x"], confirm=True)
        analysis, preparation = _derive(plan)
        self.assertEqual(
            self.engine.decide(plan, analysis, preparation),
            self.engine.decide(plan, analysis, preparation),
        )

    def test_stateless(self):
        self.assertEqual(vars(self.engine), {})

    def test_does_not_mutate_inputs(self):
        plan = _plan(category="travel", missing=["x"], confirm=True)
        analysis, preparation = _derive(plan)
        before = (plan.model_dump(), analysis.model_dump(), preparation.model_dump())
        self.engine.decide(plan, analysis, preparation)
        self.assertEqual(
            (plan.model_dump(), analysis.model_dump(), preparation.model_dump()),
            before,
        )

    def test_produces_execution_decision(self):
        plan = _plan()
        analysis, preparation = _derive(plan)
        self.assertIsInstance(
            self.engine.decide(plan, analysis, preparation), ExecutionDecision
        )


# =====================================================================
# PlanValidator.validate_decision
# =====================================================================
class ValidateDecisionTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_decision_passes(self):
        self.validator.validate_decision(_decision())  # no raise

    def test_invalid_status_rejected(self):
        decision = _decision(status="MAYBE", can_execute=False)
        with self.assertRaises(PlanValidationError):
            self.validator.validate_decision(decision)

    def test_empty_reason_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_decision(_decision(reason="   "))

    def test_confidence_out_of_range_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_decision(_decision(confidence=1.5))

    def test_can_execute_inconsistent_with_status_rejected(self):
        decision = _decision(
            status="BLOCKED", can_execute=True, blocking_reasons=[]
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_decision(decision)

    def test_approved_with_blockers_rejected(self):
        decision = _decision(
            status="APPROVED",
            can_execute=True,
            blocking_reasons=["Need Permission"],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_decision(decision)

    def test_duplicate_blocking_reasons_rejected(self):
        decision = _decision(
            status="BLOCKED",
            can_execute=False,
            blocking_reasons=["Need Permission", "Need Permission"],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_decision(decision)

    def test_empty_blocking_reason_rejected(self):
        decision = _decision(
            status="BLOCKED", can_execute=False, blocking_reasons=["   "]
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_decision(decision)

    def test_engine_output_always_validates(self):
        for plan in (
            _plan(category="", missing=[], confirm=False),
            _plan(missing=["x"]),
            _plan(confirm=True),
            _plan(category="study"),
            _plan(category="travel", missing=["x"], confirm=True),
            _plan(steps=0),
        ):
            with self.subTest(plan=plan.metadata):
                self.validator.validate_decision(_decide(plan))  # no raise


# =====================================================================
# PlanningExplanationBuilder.build_with_decision
# =====================================================================
class BuildWithDecisionTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.plan = _plan(category="travel")

    def test_approved_message(self):
        text = self.builder.build_with_decision(
            self.plan, _decision(status="APPROVED", can_execute=True)
        )
        self.assertIn("go ahead", text)

    def test_waiting_for_information_message(self):
        text = self.builder.build_with_decision(
            self.plan,
            _decision(
                status="WAITING_FOR_INFORMATION",
                can_execute=False,
                blocking_reasons=["Need Missing Information"],
            ),
        )
        self.assertIn("waiting", text.lower())
        self.assertIn("Outstanding items", text)
        self.assertIn("Missing Information", text)

    def test_blocked_lists_outstanding_items(self):
        text = self.builder.build_with_decision(
            self.plan,
            _decision(
                status="BLOCKED",
                can_execute=False,
                blocking_reasons=["Need Permission", "Need Authentication"],
            ),
        )
        self.assertIn("Permission", text)
        self.assertIn("Authentication", text)

    def test_approved_has_no_outstanding_items(self):
        text = self.builder.build_with_decision(
            self.plan, _decision(status="APPROVED", can_execute=True)
        )
        self.assertNotIn("Outstanding items", text)

    def test_reuses_base_narration(self):
        text = self.builder.build_with_decision(self.plan, _decision())
        self.assertIn("I will", text)


# =====================================================================
# PlanningEngine.decide
# =====================================================================
class PlanningEngineDecideTests(unittest.TestCase):
    def setUp(self):
        self.plan = _plan(category="travel")
        self.analysis = MagicMock(name="PlanAnalysis")
        self.preparation = MagicMock(name="ExecutionPreparation")
        self.decision = _decision()
        self.provider = MagicMock()
        self.validator = MagicMock()
        self.explanation_builder = MagicMock()
        self.decision_engine = MagicMock(name="DecisionEngine")
        self.decision_engine.decide.return_value = self.decision
        self.engine = PlanningEngine(
            self.provider,
            self.validator,
            self.explanation_builder,
            MagicMock(name="PlanAnalyzer"),
            MagicMock(name="ExecutionPreparationEngine"),
            self.decision_engine,
        )

    def test_delegates_to_decision_engine_with_all_inputs(self):
        self.engine.decide(self.plan, self.analysis, self.preparation)
        self.decision_engine.decide.assert_called_once_with(
            self.plan, self.analysis, self.preparation
        )

    def test_validates_the_decision(self):
        self.engine.decide(self.plan, self.analysis, self.preparation)
        self.validator.validate_decision.assert_called_once_with(self.decision)

    def test_returns_validated_decision_unchanged(self):
        self.assertIs(
            self.engine.decide(self.plan, self.analysis, self.preparation),
            self.decision,
        )

    def test_decision_engine_exception_propagates(self):
        self.decision_engine.decide.side_effect = RuntimeError("decide boom")
        with self.assertRaises(RuntimeError):
            self.engine.decide(self.plan, self.analysis, self.preparation)

    def test_decision_engine_stored_as_attribute(self):
        self.assertIs(self.engine.decision_engine, self.decision_engine)

    def test_engine_without_decision_engine_raises(self):
        engine = PlanningEngine(
            self.provider, self.validator, self.explanation_builder
        )
        with self.assertRaises(RuntimeError):
            engine.decide(self.plan, self.analysis, self.preparation)


class PlanningEngineDecideIntegrationTests(unittest.TestCase):
    """Real decision engine + validator; the engine guarantees validity."""

    def setUp(self):
        self.engine = _full_engine()

    def test_full_pipeline_produces_valid_decision(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        analysis = self.engine.analyze(plan)
        preparation = self.engine.prepare(plan, analysis)
        decision = self.engine.decide(plan, analysis, preparation)
        self.assertEqual(decision.status, "WAITING_FOR_INFORMATION")
        self.assertFalse(decision.can_execute)

    def test_engine_rejects_malformed_decision(self):
        bad = _decision(status="NONSENSE", can_execute=False)
        decision_engine = MagicMock()
        decision_engine.decide.return_value = bad
        engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            decision_engine,
        )
        with self.assertRaises(PlanValidationError):
            engine.decide(_plan(), MagicMock(), MagicMock())


# =====================================================================
# Backward compatibility of the engine's construction shape
# =====================================================================
class EngineConstructionShapeTests(unittest.TestCase):
    _BASE = None

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

    def test_four_arg_engine_adds_only_analyzer(self):
        engine = PlanningEngine(*self._base(), PlanAnalyzer())
        self.assertEqual(
            set(vars(engine)),
            {"provider", "validator", "explanation_builder", "analyzer"},
        )

    def test_five_arg_engine_adds_preparation_engine(self):
        engine = PlanningEngine(
            *self._base(), PlanAnalyzer(), ExecutionPreparationEngine()
        )
        self.assertEqual(
            set(vars(engine)),
            {
                "provider",
                "validator",
                "explanation_builder",
                "analyzer",
                "preparation_engine",
            },
        )

    def test_six_arg_engine_adds_decision_engine(self):
        engine = _full_engine()
        self.assertEqual(
            set(vars(engine)),
            {
                "provider",
                "validator",
                "explanation_builder",
                "analyzer",
                "preparation_engine",
                "decision_engine",
            },
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DecisionEngineDependencyTests(unittest.TestCase):
    def test_get_decision_engine_returns_engine(self):
        from app.core.dependencies import get_decision_engine

        self.assertIsInstance(get_decision_engine(), DecisionEngine)

    def test_engine_injects_decision_engine(self):
        from app.core.dependencies import get_planning_engine

        decision_engine = MagicMock()
        engine = get_planning_engine(
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            decision_engine,
        )
        self.assertIs(engine.decision_engine, decision_engine)

    def test_engine_without_decision_engine_backward_compatible(self):
        from app.core.dependencies import get_planning_engine

        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertFalse(hasattr(engine, "decision_engine"))

    def test_composition_root_end_to_end(self):
        from app.core.dependencies import (
            get_decision_engine,
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
        )
        plan = engine.create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        analysis = engine.analyze(plan)
        preparation = engine.prepare(plan, analysis)
        decision = engine.decide(plan, analysis, preparation)
        self.assertIsInstance(decision, ExecutionDecision)
        self.assertIn(decision.status, {s.value for s in DecisionStatus})
        self.assertTrue(
            engine.explanation_builder.build_with_decision(plan, decision)
        )


# =====================================================================
# Regression: Sprint 13.1 / 13.2 / 13.3 behaviour unchanged
# =====================================================================
class Sprint131To133RegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_create_plan_unchanged(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_analyze_still_works(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="plan a vacation")
        )
        self.assertFalse(self.engine.analyze(plan).ready_for_execution)

    def test_prepare_still_works(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        analysis = self.engine.analyze(plan)
        preparation = self.engine.prepare(plan, analysis)
        self.assertEqual(preparation.execution_strategy, "Sequential")

    def test_base_explanation_still_works(self):
        self.assertIn(
            "I will", PlanningExplanationBuilder().build(_plan(category="travel"))
        )


if __name__ == "__main__":
    unittest.main()
