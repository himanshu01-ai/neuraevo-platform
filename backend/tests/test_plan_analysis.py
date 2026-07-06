"""Unit tests for the Sprint 13.2 Plan Refinement & Clarification layer.

Covers the additive analysis layer end to end without touching any network,
SDK, AI, tool execution, permission check, runtime, memory, or database:

* the immutable :class:`PlanAnalysis` DTO (validation, defaults, immutability,
  JSON round-trip);
* the deterministic :class:`PlanAnalyzer` (ready/not-ready, confirmation,
  clarification, confidence, risk summary, determinism, statelessness);
* the extended :class:`PlanValidator` (``validate_analysis`` duplicate/empty/
  confidence checks);
* the extended :class:`PlanningExplanationBuilder` (``build_with_analysis``);
* the extended :class:`PlanningEngine` (``analyze`` + backward-compatible
  analyzer injection);
* the composition-root wiring (``get_plan_analyzer`` + engine injection); and
* regression that Sprint 13.1 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_plan_analysis
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
from app.services.planning.analysis_models import PlanAnalysis
from app.services.planning.plan_analyzer import PlanAnalyzer


# =====================================================================
# Helpers
# =====================================================================
def _step(number, description, reason="Because it is needed.", **kwargs):
    return ExecutionStep(
        step_number=number, description=description, reason=reason, **kwargs
    )


def _plan(missing=None, requires_confirmation=False):
    return ExecutionPlan(
        goal="Do the thing",
        summary="A short summary of the plan.",
        steps=[
            _step(1, "Understand the request"),
            _step(2, "Act on the request", dependencies=[1]),
        ],
        missing_information=missing or [],
        requires_user_confirmation=requires_confirmation,
    )


def _analysis(**overrides):
    data = dict(
        ready_for_execution=True,
        requires_confirmation=False,
        requires_clarification=False,
        missing_information=[],
        clarification_questions=[],
        risk_summary="Plan is ready for execution with no outstanding risks.",
        confidence=1.0,
    )
    data.update(overrides)
    return PlanAnalysis(**data)


# =====================================================================
# PlanAnalysis DTO
# =====================================================================
class PlanAnalysisModelTests(unittest.TestCase):
    def test_defaults_for_list_fields(self):
        analysis = PlanAnalysis(
            ready_for_execution=True,
            requires_confirmation=False,
            requires_clarification=False,
            risk_summary="ok",
            confidence=0.5,
        )
        self.assertEqual(analysis.missing_information, [])
        self.assertEqual(analysis.clarification_questions, [])

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            PlanAnalysis(ready_for_execution=True)  # others missing

    def test_confidence_rejects_above_one(self):
        with self.assertRaises(ValidationError):
            _analysis(confidence=1.5)

    def test_confidence_rejects_below_zero(self):
        with self.assertRaises(ValidationError):
            _analysis(confidence=-0.1)

    def test_confidence_boundaries_allowed(self):
        self.assertEqual(_analysis(confidence=0.0).confidence, 0.0)
        self.assertEqual(_analysis(confidence=1.0).confidence, 1.0)

    def test_is_immutable(self):
        analysis = _analysis()
        with self.assertRaises(ValidationError):
            analysis.ready_for_execution = False

    def test_json_round_trip(self):
        analysis = _analysis(
            ready_for_execution=False,
            requires_clarification=True,
            missing_information=["the destination"],
            clarification_questions=["Could you tell me the destination?"],
            risk_summary="Not ready.",
            confidence=0.8,
        )
        restored = PlanAnalysis.model_validate_json(analysis.model_dump_json())
        self.assertEqual(restored, analysis)


# =====================================================================
# PlanAnalyzer
# =====================================================================
class PlanAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = PlanAnalyzer()

    def test_ready_when_no_missing_information(self):
        analysis = self.analyzer.analyze(_plan(missing=[]))
        self.assertTrue(analysis.ready_for_execution)
        self.assertFalse(analysis.requires_clarification)
        self.assertEqual(analysis.clarification_questions, [])

    def test_not_ready_when_missing_information(self):
        analysis = self.analyzer.analyze(_plan(missing=["the destination"]))
        self.assertFalse(analysis.ready_for_execution)
        self.assertTrue(analysis.requires_clarification)

    def test_one_clarification_question_per_missing_item(self):
        analysis = self.analyzer.analyze(
            _plan(missing=["the destination", "your travel dates"])
        )
        self.assertEqual(
            analysis.clarification_questions,
            [
                "Could you tell me the destination?",
                "Could you tell me your travel dates?",
            ],
        )

    def test_confirmation_mirrors_plan(self):
        self.assertTrue(
            self.analyzer.analyze(
                _plan(requires_confirmation=True)
            ).requires_confirmation
        )
        self.assertFalse(
            self.analyzer.analyze(
                _plan(requires_confirmation=False)
            ).requires_confirmation
        )

    def test_missing_information_carried_through(self):
        missing = ["the destination", "your travel dates"]
        analysis = self.analyzer.analyze(_plan(missing=missing))
        self.assertEqual(analysis.missing_information, missing)

    def test_confidence_full_when_ready_and_no_confirmation(self):
        self.assertEqual(self.analyzer.analyze(_plan()).confidence, 1.0)

    def test_confidence_penalises_confirmation(self):
        analysis = self.analyzer.analyze(_plan(requires_confirmation=True))
        self.assertEqual(analysis.confidence, 0.9)

    def test_confidence_penalises_missing_information(self):
        analysis = self.analyzer.analyze(
            _plan(missing=["a", "b"], requires_confirmation=True)
        )
        self.assertEqual(analysis.confidence, 0.5)

    def test_confidence_never_below_zero(self):
        analysis = self.analyzer.analyze(
            _plan(missing=["a", "b", "c", "d", "e", "f"])
        )
        self.assertGreaterEqual(analysis.confidence, 0.0)
        self.assertEqual(analysis.confidence, 0.0)

    def test_risk_summary_deterministic_states(self):
        ready = self.analyzer.analyze(_plan())
        self.assertEqual(
            ready.risk_summary,
            "Plan is ready for execution with no outstanding risks.",
        )
        confirm = self.analyzer.analyze(_plan(requires_confirmation=True))
        self.assertEqual(
            confirm.risk_summary,
            "Plan is complete but requires user confirmation before execution.",
        )
        not_ready = self.analyzer.analyze(_plan(missing=["x"]))
        self.assertIn("Not ready", not_ready.risk_summary)
        self.assertIn("1 required detail", not_ready.risk_summary)

    def test_deterministic(self):
        plan = _plan(missing=["x"], requires_confirmation=True)
        self.assertEqual(
            self.analyzer.analyze(plan), self.analyzer.analyze(plan)
        )

    def test_stateless(self):
        self.assertEqual(vars(self.analyzer), {})

    def test_does_not_mutate_plan(self):
        plan = _plan(missing=["the destination"])
        before = plan.model_dump()
        self.analyzer.analyze(plan)
        self.assertEqual(plan.model_dump(), before)

    def test_produces_plan_analysis_instance(self):
        self.assertIsInstance(self.analyzer.analyze(_plan()), PlanAnalysis)


# =====================================================================
# PlanValidator.validate_analysis
# =====================================================================
class ValidateAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_analysis_passes(self):
        self.validator.validate_analysis(_analysis())  # no raise

    def test_confidence_out_of_range_rejected(self):
        # DTO blocks out-of-range construction; use model_construct to bypass it
        # and prove the validator itself also rejects (defence-in-depth).
        bad = PlanAnalysis.model_construct(
            ready_for_execution=True,
            requires_confirmation=False,
            requires_clarification=False,
            missing_information=[],
            clarification_questions=[],
            risk_summary="ok",
            confidence=1.5,
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_analysis(bad)

    def test_duplicate_missing_fields_rejected(self):
        analysis = _analysis(missing_information=["the destination", "the destination"])
        with self.assertRaises(PlanValidationError):
            self.validator.validate_analysis(analysis)

    def test_empty_missing_entry_rejected(self):
        analysis = _analysis(missing_information=["   "])
        with self.assertRaises(PlanValidationError):
            self.validator.validate_analysis(analysis)

    def test_duplicate_clarification_questions_rejected(self):
        analysis = _analysis(clarification_questions=["Q?", "Q?"])
        with self.assertRaises(PlanValidationError):
            self.validator.validate_analysis(analysis)

    def test_empty_clarification_entry_rejected(self):
        analysis = _analysis(clarification_questions=[""])
        with self.assertRaises(PlanValidationError):
            self.validator.validate_analysis(analysis)


# =====================================================================
# PlanningExplanationBuilder.build_with_analysis
# =====================================================================
class BuildWithAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.plan = _plan()

    def test_prepends_clarification_note(self):
        text = self.builder.build_with_analysis(
            self.plan, _analysis(requires_clarification=True)
        )
        self.assertTrue(
            text.startswith(
                "I need a little more information before I can continue."
            )
        )

    def test_appends_confirmation_note(self):
        # ready_for_execution=False so only the confirmation note is appended.
        text = self.builder.build_with_analysis(
            self.plan,
            _analysis(requires_confirmation=True, ready_for_execution=False),
        )
        self.assertTrue(
            text.endswith("I'll wait for your confirmation before executing.")
        )

    def test_appends_ready_note(self):
        text = self.builder.build_with_analysis(
            self.plan, _analysis(ready_for_execution=True)
        )
        self.assertTrue(text.endswith("The plan is ready for execution."))

    def test_ready_and_confirmation_both_appended(self):
        text = self.builder.build_with_analysis(
            self.plan,
            _analysis(ready_for_execution=True, requires_confirmation=True),
        )
        self.assertIn(
            "I'll wait for your confirmation before executing.", text
        )
        self.assertIn("The plan is ready for execution.", text)

    def test_not_ready_omits_ready_note(self):
        text = self.builder.build_with_analysis(
            self.plan,
            _analysis(ready_for_execution=False, requires_clarification=True),
        )
        self.assertNotIn("The plan is ready for execution.", text)

    def test_reuses_base_narration(self):
        text = self.builder.build_with_analysis(self.plan, _analysis())
        self.assertIn("understand the request", text)


# =====================================================================
# PlanningEngine.analyze
# =====================================================================
class PlanningEngineAnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.plan = _plan()
        self.analysis = _analysis()
        self.provider = MagicMock(name="PlanningProvider")
        self.validator = MagicMock(name="PlanValidator")
        self.explanation_builder = MagicMock(name="PlanningExplanationBuilder")
        self.analyzer = MagicMock(name="PlanAnalyzer")
        self.analyzer.analyze.return_value = self.analysis
        self.engine = PlanningEngine(
            self.provider,
            self.validator,
            self.explanation_builder,
            self.analyzer,
        )

    def test_delegates_to_analyzer_once(self):
        self.engine.analyze(self.plan)
        self.analyzer.analyze.assert_called_once_with(self.plan)

    def test_validates_the_analysis(self):
        self.engine.analyze(self.plan)
        self.validator.validate_analysis.assert_called_once_with(self.analysis)

    def test_returns_validated_analysis_unchanged(self):
        self.assertIs(self.engine.analyze(self.plan), self.analysis)

    def test_analyzer_exception_propagates(self):
        self.analyzer.analyze.side_effect = RuntimeError("analyze boom")
        with self.assertRaises(RuntimeError):
            self.engine.analyze(self.plan)

    def test_analyzer_stored_as_attribute(self):
        self.assertIs(self.engine.analyzer, self.analyzer)

    def test_engine_without_analyzer_raises_on_analyze(self):
        engine = PlanningEngine(
            self.provider, self.validator, self.explanation_builder
        )
        with self.assertRaises(RuntimeError):
            engine.analyze(self.plan)


class PlanningEngineBackwardCompatTests(unittest.TestCase):
    """The Sprint 13.2 analyzer injection must not disturb 13.1 construction."""

    def test_three_arg_engine_keeps_original_attributes(self):
        engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
        )
        self.assertEqual(
            set(vars(engine)),
            {"provider", "validator", "explanation_builder"},
        )

    def test_four_arg_engine_adds_analyzer_attribute(self):
        engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
            PlanAnalyzer(),
        )
        self.assertEqual(
            set(vars(engine)),
            {"provider", "validator", "explanation_builder", "analyzer"},
        )

    def test_create_plan_still_works_without_analyzer(self):
        engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
        )
        self.assertTrue(
            engine.create_plan(PlanningRequest(user_request="plan a trip")).steps
        )


class PlanningEngineAnalyzeIntegrationTests(unittest.TestCase):
    """Real analyzer + validator; the engine guarantees a valid analysis."""

    def setUp(self):
        self.engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
            PlanAnalyzer(),
        )

    def test_missing_info_plan_analyses_as_not_ready(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="plan a vacation")
        )
        analysis = self.engine.analyze(plan)
        self.assertFalse(analysis.ready_for_execution)
        self.assertTrue(analysis.requires_clarification)
        self.assertTrue(analysis.clarification_questions)

    def test_engine_rejects_malformed_analysis(self):
        bad = PlanAnalysis.model_construct(
            ready_for_execution=True,
            requires_confirmation=False,
            requires_clarification=False,
            missing_information=["dup", "dup"],
            clarification_questions=[],
            risk_summary="ok",
            confidence=0.5,
        )
        analyzer = MagicMock()
        analyzer.analyze.return_value = bad
        engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
            analyzer,
        )
        with self.assertRaises(PlanValidationError):
            engine.analyze(_plan())


# =====================================================================
# Provider output feeds the analyzer coherently
# =====================================================================
class ProviderToAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.provider = HeuristicPlanningProvider()
        self.analyzer = PlanAnalyzer()

    def test_supplied_context_yields_ready_analysis(self):
        plan = self.provider.create_plan(
            PlanningRequest(
                user_request="plan a trip",
                conversation_context="We are going to Paris next week",
            )
        )
        analysis = self.analyzer.analyze(plan)
        self.assertTrue(analysis.ready_for_execution)
        self.assertEqual(analysis.missing_information, [])

    def test_scheduling_plan_ready_but_requires_confirmation(self):
        plan = self.provider.create_plan(
            PlanningRequest(user_request="organize my day and schedule tasks")
        )
        analysis = self.analyzer.analyze(plan)
        self.assertTrue(analysis.ready_for_execution)
        self.assertTrue(analysis.requires_confirmation)
        self.assertEqual(analysis.confidence, 0.9)


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class PlanAnalyzerDependencyTests(unittest.TestCase):
    def test_get_plan_analyzer_returns_analyzer(self):
        from app.core.dependencies import get_plan_analyzer

        self.assertIsInstance(get_plan_analyzer(), PlanAnalyzer)

    def test_engine_injects_analyzer(self):
        from app.core.dependencies import get_planning_engine

        provider = MagicMock()
        validator = MagicMock()
        builder = MagicMock()
        analyzer = MagicMock()
        engine = get_planning_engine(provider, validator, builder, analyzer)
        self.assertIs(engine.analyzer, analyzer)

    def test_engine_without_analyzer_is_backward_compatible(self):
        from app.core.dependencies import get_planning_engine

        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertEqual(
            set(vars(engine)),
            {"provider", "validator", "explanation_builder"},
        )

    def test_composition_root_end_to_end(self):
        from app.core.dependencies import (
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
        )
        plan = engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        analysis = engine.analyze(plan)
        self.assertIsInstance(analysis, PlanAnalysis)
        self.assertLessEqual(analysis.confidence, 1.0)
        self.assertTrue(
            engine.explanation_builder.build_with_analysis(plan, analysis)
        )


# =====================================================================
# Regression: Sprint 13.1 behaviour unchanged
# =====================================================================
class Sprint131RegressionTests(unittest.TestCase):
    def test_create_plan_unchanged(self):
        engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
            PlanAnalyzer(),
        )
        plan = engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_plan_validate_still_works(self):
        validator = PlanValidator()
        validator.validate(_plan())  # no raise

    def test_base_explanation_still_works(self):
        text = PlanningExplanationBuilder().build(_plan())
        self.assertIn("I will", text)


if __name__ == "__main__":
    unittest.main()
