"""Unit tests for the Sprint 13.5 Execution Intent layer.

Covers the additive intent layer end to end without touching any network, SDK,
AI, tool execution, permission check, registry, runtime, memory, or database:

* the immutable :class:`ExecutionIntent` DTO and :class:`ExecutionIntentType`
  enum (defaults, immutability, JSON round-trip);
* the deterministic :class:`ExecutionIntentEngine` (the mandated status→intent
  mapping, all fields, determinism, statelessness, purity);
* the extended :class:`PlanValidator` (``validate_execution_intent`` intent/
  next-step/priority/consistency/defer-reason checks);
* the extended :class:`PlanningExplanationBuilder` (``build_with_execution_intent``);
* the extended :class:`PlanningEngine` (``create_execution_intent`` +
  backward-compatible injection alongside the 13.2–13.4 collaborators);
* the composition-root wiring (``get_execution_intent_engine`` + injection); and
* regression that Sprint 13.1–13.4 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_intent
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
from app.services.planning.decision_models import ExecutionDecision
from app.services.planning.execution_intent_engine import ExecutionIntentEngine
from app.services.planning.execution_intent_models import (
    ExecutionIntent,
    ExecutionIntentType,
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


def _intent_for(plan):
    """Run the full deterministic chain to an ExecutionIntent for ``plan``."""
    analysis = PlanAnalyzer().analyze(plan)
    preparation = ExecutionPreparationEngine().prepare(plan)
    decision = DecisionEngine().decide(plan, analysis, preparation)
    return ExecutionIntentEngine().create_intent(
        plan, analysis, preparation, decision
    )


def _decision(status, blocking_reasons=None, confidence=1.0):
    return ExecutionDecision(
        status=status,
        can_execute=status == "APPROVED",
        reason="reason",
        blocking_reasons=blocking_reasons or [],
        confidence=confidence,
    )


def _intent(**overrides):
    data = dict(
        intent=ExecutionIntentType.EXECUTE_NOW.value,
        should_execute=True,
        requires_user_action=False,
        recommended_next_step="Proceed with execution.",
        execution_priority=3,
        defer_reason="",
    )
    data.update(overrides)
    return ExecutionIntent(**data)


def _full_engine():
    return PlanningEngine(
        HeuristicPlanningProvider(),
        PlanValidator(),
        PlanningExplanationBuilder(),
        PlanAnalyzer(),
        ExecutionPreparationEngine(),
        DecisionEngine(),
        ExecutionIntentEngine(),
    )


# =====================================================================
# ExecutionIntent DTO / ExecutionIntentType enum
# =====================================================================
class ExecutionIntentModelTests(unittest.TestCase):
    def test_defer_reason_defaults_empty(self):
        intent = ExecutionIntent(
            intent="EXECUTE_NOW",
            should_execute=True,
            requires_user_action=False,
            recommended_next_step="go",
            execution_priority=3,
        )
        self.assertEqual(intent.defer_reason, "")

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionIntent(intent="EXECUTE_NOW")  # others missing

    def test_is_immutable(self):
        intent = _intent()
        with self.assertRaises(ValidationError):
            intent.should_execute = False

    def test_json_round_trip(self):
        intent = _intent(
            intent="DEFER",
            should_execute=False,
            execution_priority=1,
            defer_reason="Deferred until resolved: Need Permission.",
        )
        restored = ExecutionIntent.model_validate_json(intent.model_dump_json())
        self.assertEqual(restored, intent)

    def test_intent_enum_values(self):
        self.assertEqual(
            {t.value for t in ExecutionIntentType},
            {"EXECUTE_NOW", "WAIT_FOR_USER", "DEFER", "CANCEL"},
        )


# =====================================================================
# ExecutionIntentEngine — mandated status -> intent mapping
# =====================================================================
class IntentMappingTests(unittest.TestCase):
    def test_approved_maps_to_execute_now(self):
        intent = _intent_for(_plan(category="", missing=[], confirm=False))
        self.assertEqual(intent.intent, "EXECUTE_NOW")
        self.assertTrue(intent.should_execute)
        self.assertFalse(intent.requires_user_action)

    def test_waiting_for_information_maps_to_wait_for_user(self):
        intent = _intent_for(_plan(missing=["the destination"]))
        self.assertEqual(intent.intent, "WAIT_FOR_USER")
        self.assertTrue(intent.requires_user_action)
        self.assertFalse(intent.should_execute)

    def test_waiting_for_confirmation_maps_to_wait_for_user(self):
        intent = _intent_for(_plan(category="", missing=[], confirm=True))
        self.assertEqual(intent.intent, "WAIT_FOR_USER")
        self.assertTrue(intent.requires_user_action)

    def test_blocked_maps_to_defer(self):
        intent = _intent_for(_plan(category="study", missing=[], confirm=False))
        self.assertEqual(intent.intent, "DEFER")
        self.assertFalse(intent.should_execute)
        self.assertTrue(intent.defer_reason.strip())

    def test_rejected_maps_to_cancel(self):
        intent = _intent_for(_plan(steps=0))
        self.assertEqual(intent.intent, "CANCEL")
        self.assertFalse(intent.should_execute)
        self.assertFalse(intent.requires_user_action)


# =====================================================================
# ExecutionIntentEngine — field content
# =====================================================================
class IntentContentTests(unittest.TestCase):
    def setUp(self):
        self.engine = ExecutionIntentEngine()

    def _intent(self, decision):
        return self.engine.create_intent(
            _plan(), MagicMock(), MagicMock(), decision
        )

    def test_priority_is_non_negative_and_ordered(self):
        execute = self._intent(_decision("APPROVED"))
        wait = self._intent(_decision("WAITING_FOR_INFORMATION"))
        defer = self._intent(_decision("BLOCKED", ["Need Permission"]))
        cancel = self._intent(_decision("REJECTED"))
        for intent in (execute, wait, defer, cancel):
            self.assertGreaterEqual(intent.execution_priority, 0)
        self.assertGreater(execute.execution_priority, wait.execution_priority)
        self.assertGreater(wait.execution_priority, defer.execution_priority)
        self.assertGreater(defer.execution_priority, cancel.execution_priority)

    def test_recommended_next_step_non_empty(self):
        for status in (
            "APPROVED",
            "WAITING_FOR_INFORMATION",
            "WAITING_FOR_CONFIRMATION",
            "BLOCKED",
            "REJECTED",
        ):
            decision = _decision(
                status,
                ["Need Permission"] if status == "BLOCKED" else [],
            )
            self.assertTrue(self._intent(decision).recommended_next_step.strip())

    def test_defer_reason_only_for_defer(self):
        self.assertEqual(self._intent(_decision("APPROVED")).defer_reason, "")
        self.assertEqual(
            self._intent(_decision("REJECTED")).defer_reason, ""
        )
        defer = self._intent(_decision("BLOCKED", ["Need Authentication"]))
        self.assertIn("Need Authentication", defer.defer_reason)

    def test_should_execute_matches_execute_now_only(self):
        self.assertTrue(self._intent(_decision("APPROVED")).should_execute)
        self.assertFalse(
            self._intent(_decision("WAITING_FOR_CONFIRMATION")).should_execute
        )


# =====================================================================
# ExecutionIntentEngine — determinism / statelessness / purity
# =====================================================================
class IntentEngineQualityTests(unittest.TestCase):
    def setUp(self):
        self.engine = ExecutionIntentEngine()

    def test_deterministic(self):
        plan = _plan(category="study")
        analysis = PlanAnalyzer().analyze(plan)
        preparation = ExecutionPreparationEngine().prepare(plan)
        decision = DecisionEngine().decide(plan, analysis, preparation)
        self.assertEqual(
            self.engine.create_intent(plan, analysis, preparation, decision),
            self.engine.create_intent(plan, analysis, preparation, decision),
        )

    def test_stateless(self):
        self.assertEqual(vars(self.engine), {})

    def test_does_not_mutate_decision(self):
        decision = _decision("BLOCKED", ["Need Permission"])
        before = decision.model_dump()
        self.engine.create_intent(_plan(), MagicMock(), MagicMock(), decision)
        self.assertEqual(decision.model_dump(), before)

    def test_produces_execution_intent(self):
        self.assertIsInstance(
            self.engine.create_intent(
                _plan(), MagicMock(), MagicMock(), _decision("APPROVED")
            ),
            ExecutionIntent,
        )


# =====================================================================
# PlanValidator.validate_execution_intent
# =====================================================================
class ValidateExecutionIntentTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_intent_passes(self):
        self.validator.validate_execution_intent(_intent())  # no raise

    def test_invalid_intent_rejected(self):
        intent = _intent(intent="TELEPORT", should_execute=False)
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_intent(intent)

    def test_empty_next_step_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_intent(
                _intent(recommended_next_step="   ")
            )

    def test_negative_priority_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_intent(
                _intent(execution_priority=-1)
            )

    def test_should_execute_inconsistent_rejected(self):
        intent = _intent(
            intent="WAIT_FOR_USER",
            should_execute=True,
            requires_user_action=False,
            recommended_next_step="wait",
            execution_priority=2,
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_intent(intent)

    def test_requires_user_action_inconsistent_rejected(self):
        intent = _intent(
            intent="EXECUTE_NOW",
            should_execute=True,
            requires_user_action=True,
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_intent(intent)

    def test_defer_without_reason_rejected(self):
        intent = _intent(
            intent="DEFER",
            should_execute=False,
            requires_user_action=False,
            recommended_next_step="defer",
            execution_priority=1,
            defer_reason="   ",
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_intent(intent)

    def test_engine_output_always_validates(self):
        for plan in (
            _plan(category="", missing=[], confirm=False),
            _plan(missing=["x"]),
            _plan(confirm=True),
            _plan(category="study"),
            _plan(steps=0),
        ):
            with self.subTest(plan=plan.metadata):
                self.validator.validate_execution_intent(_intent_for(plan))


# =====================================================================
# PlanningExplanationBuilder.build_with_execution_intent
# =====================================================================
class BuildWithExecutionIntentTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.plan = _plan(category="travel")

    def test_execute_now_message(self):
        text = self.builder.build_with_execution_intent(self.plan, _intent())
        self.assertIn("carry this out now", text)

    def test_wait_for_user_message(self):
        intent = _intent(
            intent="WAIT_FOR_USER",
            should_execute=False,
            requires_user_action=True,
            recommended_next_step="wait",
            execution_priority=2,
        )
        text = self.builder.build_with_execution_intent(self.plan, intent)
        self.assertIn("need something from you", text)

    def test_defer_message_includes_reason(self):
        intent = _intent(
            intent="DEFER",
            should_execute=False,
            requires_user_action=False,
            recommended_next_step="defer",
            execution_priority=1,
            defer_reason="Deferred until resolved: Need Permission.",
        )
        text = self.builder.build_with_execution_intent(self.plan, intent)
        self.assertIn("set this aside", text)
        self.assertIn("Deferred until resolved", text)

    def test_cancel_message(self):
        intent = _intent(
            intent="CANCEL",
            should_execute=False,
            requires_user_action=False,
            recommended_next_step="abandon",
            execution_priority=0,
        )
        text = self.builder.build_with_execution_intent(self.plan, intent)
        self.assertIn("won't pursue", text)

    def test_reuses_base_narration(self):
        text = self.builder.build_with_execution_intent(self.plan, _intent())
        self.assertIn("I will", text)


# =====================================================================
# PlanningEngine.create_execution_intent
# =====================================================================
class PlanningEngineCreateIntentTests(unittest.TestCase):
    def setUp(self):
        self.plan = _plan(category="travel")
        self.analysis = MagicMock(name="PlanAnalysis")
        self.preparation = MagicMock(name="ExecutionPreparation")
        self.decision = MagicMock(name="ExecutionDecision")
        self.intent = _intent()
        self.provider = MagicMock()
        self.validator = MagicMock()
        self.explanation_builder = MagicMock()
        self.intent_engine = MagicMock(name="ExecutionIntentEngine")
        self.intent_engine.create_intent.return_value = self.intent
        self.engine = PlanningEngine(
            self.provider,
            self.validator,
            self.explanation_builder,
            MagicMock(name="PlanAnalyzer"),
            MagicMock(name="ExecutionPreparationEngine"),
            MagicMock(name="DecisionEngine"),
            self.intent_engine,
        )

    def test_delegates_to_intent_engine_with_all_inputs(self):
        self.engine.create_execution_intent(
            self.plan, self.analysis, self.preparation, self.decision
        )
        self.intent_engine.create_intent.assert_called_once_with(
            self.plan, self.analysis, self.preparation, self.decision
        )

    def test_validates_the_intent(self):
        self.engine.create_execution_intent(
            self.plan, self.analysis, self.preparation, self.decision
        )
        self.validator.validate_execution_intent.assert_called_once_with(
            self.intent
        )

    def test_returns_validated_intent_unchanged(self):
        self.assertIs(
            self.engine.create_execution_intent(
                self.plan, self.analysis, self.preparation, self.decision
            ),
            self.intent,
        )

    def test_intent_engine_exception_propagates(self):
        self.intent_engine.create_intent.side_effect = RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            self.engine.create_execution_intent(
                self.plan, self.analysis, self.preparation, self.decision
            )

    def test_intent_engine_stored_as_attribute(self):
        self.assertIs(self.engine.intent_engine, self.intent_engine)

    def test_engine_without_intent_engine_raises(self):
        engine = PlanningEngine(
            self.provider, self.validator, self.explanation_builder
        )
        with self.assertRaises(RuntimeError):
            engine.create_execution_intent(
                self.plan, self.analysis, self.preparation, self.decision
            )


class PlanningEngineCreateIntentIntegrationTests(unittest.TestCase):
    """Real intent engine + validator; the engine guarantees validity."""

    def setUp(self):
        self.engine = _full_engine()

    def test_full_pipeline_produces_valid_intent(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        analysis = self.engine.analyze(plan)
        preparation = self.engine.prepare(plan, analysis)
        decision = self.engine.decide(plan, analysis, preparation)
        intent = self.engine.create_execution_intent(
            plan, analysis, preparation, decision
        )
        self.assertEqual(intent.intent, "WAIT_FOR_USER")
        self.assertTrue(intent.requires_user_action)

    def test_engine_rejects_malformed_intent(self):
        bad = _intent(intent="NONSENSE", should_execute=False)
        intent_engine = MagicMock()
        intent_engine.create_intent.return_value = bad
        engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            DecisionEngine(),
            intent_engine,
        )
        with self.assertRaises(PlanValidationError):
            engine.create_execution_intent(
                _plan(), MagicMock(), MagicMock(), MagicMock()
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

    def test_six_arg_engine_has_no_intent_engine(self):
        engine = PlanningEngine(
            *self._base(),
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            DecisionEngine(),
        )
        self.assertNotIn("intent_engine", vars(engine))

    def test_seven_arg_engine_adds_intent_engine(self):
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
            },
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class ExecutionIntentDependencyTests(unittest.TestCase):
    def test_get_execution_intent_engine_returns_engine(self):
        from app.core.dependencies import get_execution_intent_engine

        self.assertIsInstance(
            get_execution_intent_engine(), ExecutionIntentEngine
        )

    def test_engine_injects_intent_engine(self):
        from app.core.dependencies import get_planning_engine

        intent_engine = MagicMock()
        engine = get_planning_engine(
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            intent_engine,
        )
        self.assertIs(engine.intent_engine, intent_engine)

    def test_engine_without_intent_engine_backward_compatible(self):
        from app.core.dependencies import get_planning_engine

        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertFalse(hasattr(engine, "intent_engine"))

    def test_composition_root_end_to_end(self):
        from app.core.dependencies import (
            get_decision_engine,
            get_execution_intent_engine,
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
        self.assertIsInstance(intent, ExecutionIntent)
        self.assertIn(intent.intent, {t.value for t in ExecutionIntentType})
        self.assertTrue(
            engine.explanation_builder.build_with_execution_intent(plan, intent)
        )


# =====================================================================
# Regression: Sprint 13.1–13.4 behaviour unchanged
# =====================================================================
class Sprint131To134RegressionTests(unittest.TestCase):
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
        self.assertEqual(
            self.engine.prepare(plan, analysis).execution_strategy, "Sequential"
        )

    def test_decide_still_works(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        analysis = self.engine.analyze(plan)
        preparation = self.engine.prepare(plan, analysis)
        decision = self.engine.decide(plan, analysis, preparation)
        self.assertEqual(decision.status, "WAITING_FOR_INFORMATION")


if __name__ == "__main__":
    unittest.main()
