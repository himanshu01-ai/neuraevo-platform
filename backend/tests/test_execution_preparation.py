"""Unit tests for the Sprint 13.3 Capability Resolution & Execution Preparation.

Covers the additive preparation layer end to end without touching any network,
SDK, AI, tool execution, permission check, registry, runtime, memory, or
database:

* the immutable :class:`ExecutionPreparation` DTO and :class:`ExecutionStrategy`
  enum (defaults, immutability, JSON round-trip);
* the deterministic :class:`ExecutionPreparationEngine` (capability, permission,
  and service mapping; strategy selection; blocker generation; step count;
  determinism; statelessness; plan non-mutation);
* the extended :class:`PlanValidator` (``validate_preparation`` duplicate/
  negative/invalid-strategy checks);
* the extended :class:`PlanningExplanationBuilder` (``build_with_preparation``);
* the extended :class:`PlanningEngine` (``prepare`` + backward-compatible
  injection alongside the 13.2 analyzer);
* the composition-root wiring (``get_execution_preparation_engine`` + injection);
  and
* regression that Sprint 13.1/13.2 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_preparation
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
from app.services.planning.execution_preparation_engine import (
    ExecutionPreparationEngine,
)
from app.services.planning.execution_preparation_models import (
    ExecutionPreparation,
    ExecutionStrategy,
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


def _preparation(**overrides):
    data = dict(
        required_capabilities=["Calendar"],
        external_services=["Calendar Service"],
        permissions_required=["Calendar Write"],
        estimated_execution_steps=3,
        can_execute_immediately=False,
        blocked_by=["Need Permission"],
        execution_strategy=ExecutionStrategy.SEQUENTIAL.value,
    )
    data.update(overrides)
    return ExecutionPreparation(**data)


def _full_engine():
    return PlanningEngine(
        HeuristicPlanningProvider(),
        PlanValidator(),
        PlanningExplanationBuilder(),
        PlanAnalyzer(),
        ExecutionPreparationEngine(),
    )


# =====================================================================
# ExecutionPreparation DTO / ExecutionStrategy enum
# =====================================================================
class ExecutionPreparationModelTests(unittest.TestCase):
    def test_list_fields_default_empty(self):
        prep = ExecutionPreparation(
            estimated_execution_steps=0,
            can_execute_immediately=True,
            execution_strategy="Sequential",
        )
        self.assertEqual(prep.required_capabilities, [])
        self.assertEqual(prep.external_services, [])
        self.assertEqual(prep.permissions_required, [])
        self.assertEqual(prep.blocked_by, [])

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionPreparation(estimated_execution_steps=1)  # others missing

    def test_is_immutable(self):
        prep = _preparation()
        with self.assertRaises(ValidationError):
            prep.can_execute_immediately = True

    def test_json_round_trip(self):
        prep = _preparation()
        restored = ExecutionPreparation.model_validate_json(
            prep.model_dump_json()
        )
        self.assertEqual(restored, prep)

    def test_strategy_enum_values(self):
        self.assertEqual(
            {s.value for s in ExecutionStrategy},
            {"Sequential", "Parallel", "Hybrid"},
        )


# =====================================================================
# ExecutionPreparationEngine — capability / permission / service mapping
# =====================================================================
class PreparationMappingTests(unittest.TestCase):
    def setUp(self):
        self.engine = ExecutionPreparationEngine()

    def test_travel_capabilities(self):
        prep = self.engine.prepare(_plan(category="travel"))
        self.assertEqual(
            set(prep.required_capabilities),
            {"Calendar", "Maps", "Email", "Browser"},
        )

    def test_travel_permissions(self):
        prep = self.engine.prepare(_plan(category="travel"))
        self.assertEqual(
            set(prep.permissions_required),
            {"Calendar Write", "Email Send", "Location"},
        )

    def test_study_capabilities_and_no_permissions(self):
        prep = self.engine.prepare(_plan(category="study"))
        self.assertEqual(set(prep.required_capabilities), {"Browser", "Documents"})
        self.assertEqual(prep.permissions_required, [])

    def test_business_capabilities(self):
        prep = self.engine.prepare(_plan(category="business"))
        self.assertEqual(
            set(prep.required_capabilities),
            {"Browser", "Documents", "Spreadsheet"},
        )

    def test_scheduling_capabilities(self):
        prep = self.engine.prepare(_plan(category="scheduling"))
        self.assertEqual(
            set(prep.required_capabilities),
            {"Calendar", "Reminder", "Notifications"},
        )

    def test_external_services_derived_from_capabilities(self):
        prep = self.engine.prepare(_plan(category="study"))
        self.assertEqual(set(prep.external_services), {"Web", "Document Storage"})

    def test_unknown_category_has_no_capabilities(self):
        prep = self.engine.prepare(_plan(category="mystery"))
        self.assertEqual(prep.required_capabilities, [])
        self.assertEqual(prep.external_services, [])
        self.assertEqual(prep.permissions_required, [])

    def test_estimated_steps_matches_plan(self):
        prep = self.engine.prepare(_plan(category="travel", steps=4))
        self.assertEqual(prep.estimated_execution_steps, 4)


# =====================================================================
# ExecutionPreparationEngine — strategy selection
# =====================================================================
class StrategySelectionTests(unittest.TestCase):
    def setUp(self):
        self.engine = ExecutionPreparationEngine()

    def _strategy(self, category):
        return self.engine.prepare(_plan(category=category)).execution_strategy

    def test_travel_sequential(self):
        self.assertEqual(self._strategy("travel"), "Sequential")

    def test_business_parallel(self):
        self.assertEqual(self._strategy("business"), "Parallel")

    def test_fitness_hybrid(self):
        self.assertEqual(self._strategy("fitness"), "Hybrid")

    def test_unknown_defaults_sequential(self):
        self.assertEqual(self._strategy("mystery"), "Sequential")

    def test_strategy_always_in_allowed_set(self):
        allowed = {s.value for s in ExecutionStrategy}
        for category in ("travel", "interview", "fitness", "business",
                         "study", "scheduling", "mystery"):
            self.assertIn(self._strategy(category), allowed)


# =====================================================================
# ExecutionPreparationEngine — blockers & immediacy
# =====================================================================
class BlockerGenerationTests(unittest.TestCase):
    def setUp(self):
        self.engine = ExecutionPreparationEngine()

    def test_missing_information_blocks(self):
        prep = self.engine.prepare(_plan(missing=["the destination"]))
        self.assertIn("Need Missing Information", prep.blocked_by)
        self.assertFalse(prep.can_execute_immediately)

    def test_confirmation_blocks(self):
        prep = self.engine.prepare(_plan(confirm=True))
        self.assertIn("Need User Approval", prep.blocked_by)

    def test_permissions_block(self):
        prep = self.engine.prepare(_plan(category="scheduling"))
        self.assertIn("Need Permission", prep.blocked_by)

    def test_services_require_authentication(self):
        prep = self.engine.prepare(_plan(category="study"))
        self.assertIn("Need Authentication", prep.blocked_by)

    def test_account_services_require_external_account(self):
        prep = self.engine.prepare(_plan(category="travel"))
        self.assertIn("Need External Account", prep.blocked_by)

    def test_no_blockers_can_execute_immediately(self):
        prep = self.engine.prepare(_plan(category="", missing=[], confirm=False))
        self.assertEqual(prep.blocked_by, [])
        self.assertTrue(prep.can_execute_immediately)

    def test_blockers_never_empty_strings(self):
        prep = self.engine.prepare(
            _plan(category="travel", missing=["x"], confirm=True)
        )
        self.assertTrue(prep.blocked_by)
        self.assertTrue(all(b.strip() for b in prep.blocked_by))

    def test_blockers_have_no_duplicates(self):
        prep = self.engine.prepare(
            _plan(category="travel", missing=["x"], confirm=True)
        )
        self.assertEqual(len(prep.blocked_by), len(set(prep.blocked_by)))


# =====================================================================
# ExecutionPreparationEngine — determinism / statelessness / purity
# =====================================================================
class PreparationEngineQualityTests(unittest.TestCase):
    def setUp(self):
        self.engine = ExecutionPreparationEngine()

    def test_deterministic(self):
        plan = _plan(category="travel", missing=["x"], confirm=True)
        self.assertEqual(self.engine.prepare(plan), self.engine.prepare(plan))

    def test_stateless(self):
        self.assertEqual(vars(self.engine), {})

    def test_does_not_mutate_plan(self):
        plan = _plan(category="travel", missing=["x"], confirm=True)
        before = plan.model_dump()
        self.engine.prepare(plan)
        self.assertEqual(plan.model_dump(), before)

    def test_produces_execution_preparation(self):
        self.assertIsInstance(
            self.engine.prepare(_plan()), ExecutionPreparation
        )


# =====================================================================
# PlanValidator.validate_preparation
# =====================================================================
class ValidatePreparationTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_preparation_passes(self):
        self.validator.validate_preparation(_preparation())  # no raise

    def test_duplicate_capabilities_rejected(self):
        prep = _preparation(required_capabilities=["Calendar", "Calendar"])
        with self.assertRaises(PlanValidationError):
            self.validator.validate_preparation(prep)

    def test_duplicate_permissions_rejected(self):
        prep = _preparation(
            permissions_required=["Calendar Write", "Calendar Write"]
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_preparation(prep)

    def test_duplicate_services_rejected(self):
        prep = _preparation(
            external_services=["Calendar Service", "Calendar Service"]
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_preparation(prep)

    def test_negative_step_count_rejected(self):
        prep = _preparation(estimated_execution_steps=-1)
        with self.assertRaises(PlanValidationError):
            self.validator.validate_preparation(prep)

    def test_invalid_strategy_rejected(self):
        prep = _preparation(execution_strategy="Telepathic")
        with self.assertRaises(PlanValidationError):
            self.validator.validate_preparation(prep)

    def test_duplicate_blockers_rejected(self):
        prep = _preparation(blocked_by=["Need Permission", "Need Permission"])
        with self.assertRaises(PlanValidationError):
            self.validator.validate_preparation(prep)

    def test_empty_blocker_rejected(self):
        prep = _preparation(blocked_by=["   "])
        with self.assertRaises(PlanValidationError):
            self.validator.validate_preparation(prep)

    def test_engine_output_always_validates(self):
        engine = ExecutionPreparationEngine()
        for category in ("travel", "interview", "fitness", "business",
                         "study", "scheduling", "mystery"):
            with self.subTest(category=category):
                prep = engine.prepare(
                    _plan(category=category, missing=["x"], confirm=True)
                )
                self.validator.validate_preparation(prep)  # no raise


# =====================================================================
# PlanningExplanationBuilder.build_with_preparation
# =====================================================================
class BuildWithPreparationTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.plan = _plan(category="travel")

    def test_mentions_capabilities(self):
        text = self.builder.build_with_preparation(
            self.plan, _preparation(required_capabilities=["Calendar", "Email"])
        )
        self.assertIn("Calendar", text)
        self.assertIn("Email", text)

    def test_mentions_services(self):
        text = self.builder.build_with_preparation(
            self.plan, _preparation(external_services=["Calendar Service"])
        )
        self.assertIn("Calendar Service", text)

    def test_mentions_permissions(self):
        text = self.builder.build_with_preparation(
            self.plan, _preparation(permissions_required=["Calendar Write"])
        )
        self.assertIn("permission", text.lower())
        self.assertIn("Calendar Write", text)

    def test_says_can_start_when_immediate(self):
        text = self.builder.build_with_preparation(
            self.plan,
            _preparation(can_execute_immediately=True, blocked_by=[]),
        )
        self.assertIn("start on this right away", text)

    def test_lists_blockers_when_not_immediate(self):
        text = self.builder.build_with_preparation(
            self.plan,
            _preparation(
                can_execute_immediately=False,
                blocked_by=["Need User Approval", "Need Permission"],
            ),
        )
        self.assertIn("still need to be resolved", text)
        # Rendered in user language, without the "Need " prefix.
        self.assertIn("User Approval", text)
        self.assertIn("Permission", text)

    def test_reuses_base_narration(self):
        text = self.builder.build_with_preparation(self.plan, _preparation())
        self.assertIn("I will", text)


# =====================================================================
# PlanningEngine.prepare
# =====================================================================
class PlanningEnginePrepareTests(unittest.TestCase):
    def setUp(self):
        self.plan = _plan(category="travel")
        self.analysis = MagicMock(name="PlanAnalysis")
        self.preparation = _preparation()
        self.provider = MagicMock()
        self.validator = MagicMock()
        self.explanation_builder = MagicMock()
        self.preparation_engine = MagicMock(name="ExecutionPreparationEngine")
        self.preparation_engine.prepare.return_value = self.preparation
        self.engine = PlanningEngine(
            self.provider,
            self.validator,
            self.explanation_builder,
            MagicMock(name="PlanAnalyzer"),
            self.preparation_engine,
        )

    def test_delegates_to_preparation_engine_with_plan(self):
        self.engine.prepare(self.plan, self.analysis)
        self.preparation_engine.prepare.assert_called_once_with(self.plan)

    def test_validates_the_preparation(self):
        self.engine.prepare(self.plan, self.analysis)
        self.validator.validate_preparation.assert_called_once_with(
            self.preparation
        )

    def test_returns_validated_preparation_unchanged(self):
        self.assertIs(
            self.engine.prepare(self.plan, self.analysis), self.preparation
        )

    def test_preparation_engine_exception_propagates(self):
        self.preparation_engine.prepare.side_effect = RuntimeError("prep boom")
        with self.assertRaises(RuntimeError):
            self.engine.prepare(self.plan, self.analysis)

    def test_preparation_engine_stored_as_attribute(self):
        self.assertIs(self.engine.preparation_engine, self.preparation_engine)

    def test_engine_without_preparation_engine_raises(self):
        engine = PlanningEngine(
            self.provider, self.validator, self.explanation_builder
        )
        with self.assertRaises(RuntimeError):
            engine.prepare(self.plan, self.analysis)


class PlanningEnginePrepareIntegrationTests(unittest.TestCase):
    """Real preparation engine + validator; the engine guarantees validity."""

    def setUp(self):
        self.engine = _full_engine()

    def test_prepares_a_travel_plan(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        analysis = self.engine.analyze(plan)
        preparation = self.engine.prepare(plan, analysis)
        self.assertIn("Calendar", preparation.required_capabilities)
        self.assertEqual(preparation.execution_strategy, "Sequential")
        self.assertFalse(preparation.can_execute_immediately)

    def test_engine_rejects_malformed_preparation(self):
        bad = _preparation(execution_strategy="Nonsense")
        prep_engine = MagicMock()
        prep_engine.prepare.return_value = bad
        engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
            PlanAnalyzer(),
            prep_engine,
        )
        with self.assertRaises(PlanValidationError):
            engine.prepare(_plan(), MagicMock())


# =====================================================================
# Backward compatibility of the engine's construction shape
# =====================================================================
class EngineConstructionShapeTests(unittest.TestCase):
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

    def test_four_arg_engine_adds_only_analyzer(self):
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

    def test_five_arg_engine_adds_preparation_engine(self):
        engine = _full_engine()
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


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class ExecutionPreparationDependencyTests(unittest.TestCase):
    def test_get_execution_preparation_engine_returns_engine(self):
        from app.core.dependencies import get_execution_preparation_engine

        self.assertIsInstance(
            get_execution_preparation_engine(), ExecutionPreparationEngine
        )

    def test_engine_injects_preparation_engine(self):
        from app.core.dependencies import get_planning_engine

        prep_engine = MagicMock()
        engine = get_planning_engine(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), prep_engine
        )
        self.assertIs(engine.preparation_engine, prep_engine)

    def test_engine_without_preparation_engine_backward_compatible(self):
        from app.core.dependencies import get_planning_engine

        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertFalse(hasattr(engine, "preparation_engine"))

    def test_composition_root_end_to_end(self):
        from app.core.dependencies import (
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
        )
        plan = engine.create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        analysis = engine.analyze(plan)
        preparation = engine.prepare(plan, analysis)
        self.assertIsInstance(preparation, ExecutionPreparation)
        self.assertTrue(
            engine.explanation_builder.build_with_preparation(plan, preparation)
        )


# =====================================================================
# Regression: Sprint 13.1 / 13.2 behaviour unchanged
# =====================================================================
class Sprint131And132RegressionTests(unittest.TestCase):
    def test_create_plan_unchanged(self):
        engine = _full_engine()
        plan = engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_analyze_still_works(self):
        engine = _full_engine()
        plan = engine.create_plan(PlanningRequest(user_request="plan a vacation"))
        analysis = engine.analyze(plan)
        self.assertFalse(analysis.ready_for_execution)

    def test_base_explanation_still_works(self):
        text = PlanningExplanationBuilder().build(_plan(category="travel"))
        self.assertIn("I will", text)

    def test_plan_validate_still_works(self):
        PlanValidator().validate(
            ExecutionPlan(
                goal="g",
                summary="s",
                steps=[
                    ExecutionStep(step_number=1, description="A", reason="r"),
                ],
            )
        )


if __name__ == "__main__":
    unittest.main()
