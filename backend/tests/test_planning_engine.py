"""Unit tests for the Sprint 13.1 Intelligent Planning Engine.

Covers the reasoning-only planning layer end to end without touching any
network, SDK, AI, tool execution, permission check, or database:

* the provider-independent DTOs (validation, defaults, immutability);
* the :class:`PlanningProvider` abstraction and the deterministic
  :class:`HeuristicPlanningProvider` default (plan generation across goal
  categories, determinism, provider independence);
* the :class:`PlanValidator` structural/logical rules;
* the :class:`PlanningExplanationBuilder` human narration;
* the :class:`PlanningEngine` coordinator (reason -> validate -> explain);
* the composition-root wiring; and
* regression that the frozen Sprint 11.4 ``app.services.planner`` layer is
  untouched.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_planning_engine
"""

import unittest
from unittest.mock import MagicMock

from pydantic import ValidationError

from app.services.planner import ExecutionPlan as PlannerExecutionPlan
from app.services.planner import PlanningStep as PlannerPlanningStep
from app.services.planning import (
    ExecutionPlan,
    ExecutionStep,
    HeuristicPlanningProvider,
    PlanningEngine,
    PlanningExplanationBuilder,
    PlanningProvider,
    PlanningRequest,
    PlanStepStatus,
    PlanValidationError,
    PlanValidator,
)
from app.services.planning.providers.base import (
    PlanningProvider as BasePlanningProvider,
)


# =====================================================================
# Helpers
# =====================================================================
def _step(number, description, reason="Because it is needed.", **kwargs):
    return ExecutionStep(
        step_number=number, description=description, reason=reason, **kwargs
    )


def _valid_plan(**overrides):
    data = dict(
        goal="Do the thing",
        summary="A short summary of the plan.",
        steps=[
            _step(1, "Understand the request"),
            _step(2, "Act on the request", dependencies=[1]),
        ],
    )
    data.update(overrides)
    return ExecutionPlan(**data)


# =====================================================================
# Provider abstraction
# =====================================================================
class PlanningProviderAbstractionTests(unittest.TestCase):
    def test_provider_is_the_abstract_base(self):
        self.assertIs(PlanningProvider, BasePlanningProvider)

    def test_provider_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            PlanningProvider()  # abstract create_plan not implemented

    def test_concrete_subclass_is_instantiable(self):
        class OkProvider(PlanningProvider):
            name = "ok"

            def create_plan(self, request):
                return _valid_plan()

        provider = OkProvider()
        self.assertIsInstance(provider, PlanningProvider)


# =====================================================================
# Models: PlanStepStatus / ExecutionStep
# =====================================================================
class PlanStepStatusTests(unittest.TestCase):
    def test_planned_is_the_only_status(self):
        self.assertEqual([s.value for s in PlanStepStatus], ["planned"])

    def test_planned_serialises_to_planned(self):
        self.assertEqual(PlanStepStatus.PLANNED.value, "planned")
        self.assertEqual(PlanStepStatus.PLANNED, "planned")  # str enum


class ExecutionStepModelTests(unittest.TestCase):
    def test_minimal_step_defaults(self):
        step = _step(1, "Do it")
        self.assertEqual(step.expected_tool, None)
        self.assertEqual(step.dependencies, [])
        self.assertIs(step.status, PlanStepStatus.PLANNED)

    def test_trims_description_and_reason(self):
        step = ExecutionStep(
            step_number=1, description="  Do it  ", reason="  why  "
        )
        self.assertEqual(step.description, "Do it")
        self.assertEqual(step.reason, "why")

    def test_rejects_empty_description(self):
        with self.assertRaises(ValidationError):
            ExecutionStep(step_number=1, description="", reason="why")

    def test_rejects_whitespace_reason(self):
        with self.assertRaises(ValidationError):
            ExecutionStep(step_number=1, description="Do it", reason="   ")

    def test_rejects_step_number_below_one(self):
        with self.assertRaises(ValidationError):
            _step(0, "Do it")

    def test_rejects_non_positive_dependency(self):
        with self.assertRaises(ValidationError):
            _step(2, "Do it", dependencies=[0])

    def test_rejects_blank_expected_tool(self):
        with self.assertRaises(ValidationError):
            _step(1, "Do it", expected_tool="   ")

    def test_trims_expected_tool(self):
        step = _step(1, "Do it", expected_tool="  calendar  ")
        self.assertEqual(step.expected_tool, "calendar")

    def test_is_immutable(self):
        step = _step(1, "Do it")
        with self.assertRaises(ValidationError):
            step.step_number = 2


# =====================================================================
# Models: ExecutionPlan
# =====================================================================
class ExecutionPlanModelTests(unittest.TestCase):
    def test_requires_goal_and_summary(self):
        with self.assertRaises(ValidationError):
            ExecutionPlan(goal="only goal")  # summary missing

    def test_trims_and_rejects_empty_goal(self):
        with self.assertRaises(ValidationError):
            ExecutionPlan(goal="   ", summary="s")

    def test_defaults(self):
        plan = ExecutionPlan(goal="g", summary="s")
        self.assertEqual(plan.steps, [])
        self.assertEqual(plan.missing_information, [])
        self.assertFalse(plan.requires_user_confirmation)
        self.assertEqual(plan.metadata, {})

    def test_estimated_step_count_defaults_to_len_steps(self):
        plan = _valid_plan()
        self.assertEqual(plan.estimated_step_count, 2)

    def test_estimated_step_count_defaults_to_zero_when_empty(self):
        plan = ExecutionPlan(goal="g", summary="s")
        self.assertEqual(plan.estimated_step_count, 0)

    def test_explicit_estimated_step_count_is_respected(self):
        plan = _valid_plan(estimated_step_count=9)
        self.assertEqual(plan.estimated_step_count, 9)

    def test_is_immutable(self):
        plan = _valid_plan()
        with self.assertRaises(ValidationError):
            plan.goal = "changed"


# =====================================================================
# Models: PlanningRequest
# =====================================================================
class PlanningRequestModelTests(unittest.TestCase):
    def test_defaults_context_and_memory_to_empty(self):
        request = PlanningRequest(user_request="do it")
        self.assertEqual(request.conversation_context, "")
        self.assertEqual(request.memory_summary, "")

    def test_rejects_empty_user_request(self):
        with self.assertRaises(ValidationError):
            PlanningRequest(user_request="")

    def test_rejects_whitespace_user_request(self):
        with self.assertRaises(ValidationError):
            PlanningRequest(user_request="   ")

    def test_trims_user_request(self):
        request = PlanningRequest(user_request="  plan a trip  ")
        self.assertEqual(request.user_request, "plan a trip")


# =====================================================================
# PlanValidator
# =====================================================================
class PlanValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_plan_passes(self):
        self.validator.validate(_valid_plan())  # no raise
        self.assertTrue(self.validator.is_valid(_valid_plan()))

    def test_empty_plan_rejected(self):
        plan = ExecutionPlan(goal="g", summary="s", steps=[])
        with self.assertRaises(PlanValidationError):
            self.validator.validate(plan)
        self.assertFalse(self.validator.is_valid(plan))

    def test_duplicate_step_numbers_rejected(self):
        plan = ExecutionPlan(
            goal="g",
            summary="s",
            steps=[_step(1, "A"), _step(1, "B")],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate(plan)

    def test_duplicate_descriptions_rejected(self):
        plan = ExecutionPlan(
            goal="g",
            summary="s",
            steps=[_step(1, "Same"), _step(2, "Same", dependencies=[1])],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate(plan)

    def test_non_sequential_numbers_rejected(self):
        plan = ExecutionPlan(
            goal="g",
            summary="s",
            steps=[_step(1, "A"), _step(3, "B")],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate(plan)

    def test_self_dependency_rejected(self):
        plan = ExecutionPlan(
            goal="g",
            summary="s",
            steps=[_step(1, "A"), _step(2, "B", dependencies=[2])],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate(plan)

    def test_forward_dependency_rejected(self):
        plan = ExecutionPlan(
            goal="g",
            summary="s",
            steps=[_step(1, "A", dependencies=[2]), _step(2, "B")],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate(plan)

    def test_unknown_dependency_rejected(self):
        plan = ExecutionPlan(
            goal="g",
            summary="s",
            steps=[
                _step(1, "A"),
                _step(2, "B", dependencies=[1]),
                _step(3, "C", dependencies=[9]),
            ],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate(plan)

    def test_duplicate_dependencies_within_step_rejected(self):
        plan = ExecutionPlan(
            goal="g",
            summary="s",
            steps=[
                _step(1, "A"),
                _step(2, "B", dependencies=[1]),
                _step(3, "C", dependencies=[1, 1]),
            ],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate(plan)


# =====================================================================
# PlanningExplanationBuilder
# =====================================================================
class PlanningExplanationBuilderTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()

    def test_returns_non_empty_string(self):
        text = self.builder.build(_valid_plan())
        self.assertIsInstance(text, str)
        self.assertTrue(text)

    def test_preserves_step_order(self):
        text = self.builder.build(_valid_plan())
        self.assertLess(text.index("understand"), text.index("act"))

    def test_mentions_confirmation_when_required(self):
        text = self.builder.build(
            _valid_plan(requires_user_confirmation=True)
        )
        self.assertIn("won't take any action", text)

    def test_omits_confirmation_when_not_required(self):
        text = self.builder.build(
            _valid_plan(requires_user_confirmation=False)
        )
        self.assertNotIn("won't take any action", text)

    def test_lists_missing_information(self):
        text = self.builder.build(
            _valid_plan(missing_information=["the destination", "the dates"])
        )
        self.assertIn("need a few details", text)
        self.assertIn("the destination", text)
        self.assertIn("the dates", text)

    def test_single_step_uses_simple_phrasing(self):
        plan = ExecutionPlan(
            goal="g", summary="s", steps=[_step(1, "Do the only thing")]
        )
        text = self.builder.build(plan)
        self.assertIn("I will do the only thing", text)
        self.assertNotIn("first", text)

    def test_empty_plan_explained_gracefully(self):
        plan = ExecutionPlan(goal="Do the thing", summary="s")
        text = self.builder.build(plan)
        self.assertIn("no steps planned", text)


# =====================================================================
# HeuristicPlanningProvider (concrete default + provider independence)
# =====================================================================
class HeuristicPlanningProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = HeuristicPlanningProvider()
        self.validator = PlanValidator()

    _CATEGORY_REQUESTS = {
        "travel": "Help me plan a trip to Japan",
        "interview": "I have a job interview next week, help me prepare",
        "fitness": "I want to build muscle and improve my fitness",
        "business": "Help me create a business strategy to grow revenue",
        "study": "I need to study for my certification exam",
        "scheduling": "Help me organize my day and schedule my tasks",
    }

    def test_name_is_heuristic(self):
        self.assertEqual(self.provider.name, "heuristic")

    def test_all_categories_produce_valid_plans(self):
        for category, request in self._CATEGORY_REQUESTS.items():
            with self.subTest(category=category):
                plan = self.provider.create_plan(
                    PlanningRequest(user_request=request)
                )
                self.validator.validate(plan)  # no raise
                self.assertTrue(plan.steps)
                self.assertEqual(plan.metadata["category"], category)
                self.assertEqual(plan.metadata["provider"], "heuristic")

    def test_all_steps_are_planned_and_counted(self):
        for request in self._CATEGORY_REQUESTS.values():
            plan = self.provider.create_plan(
                PlanningRequest(user_request=request)
            )
            self.assertTrue(
                all(s.status is PlanStepStatus.PLANNED for s in plan.steps)
            )
            self.assertEqual(plan.estimated_step_count, len(plan.steps))

    def test_unknown_request_falls_back_to_generic(self):
        plan = self.provider.create_plan(
            PlanningRequest(user_request="zzzzz qwerty please help")
        )
        self.assertEqual(plan.metadata["category"], "generic")
        self.assertTrue(plan.requires_user_confirmation)
        self.validator.validate(plan)

    def test_travel_requires_confirmation_and_understands_destination(self):
        plan = self.provider.create_plan(
            PlanningRequest(user_request="plan a vacation")
        )
        self.assertTrue(plan.requires_user_confirmation)
        self.assertIn("destination", plan.steps[0].description.lower())

    def test_fitness_does_not_require_confirmation(self):
        plan = self.provider.create_plan(
            PlanningRequest(user_request="build a workout routine")
        )
        self.assertFalse(plan.requires_user_confirmation)

    def test_missing_information_reported_when_absent(self):
        plan = self.provider.create_plan(
            PlanningRequest(user_request="plan a vacation")
        )
        self.assertIn("the destination", plan.missing_information)
        self.assertIn("your travel dates", plan.missing_information)

    def test_missing_information_pruned_when_supplied(self):
        plan = self.provider.create_plan(
            PlanningRequest(
                user_request="plan a trip",
                conversation_context="We are going to Paris next week",
            )
        )
        self.assertEqual(plan.missing_information, [])

    def test_is_deterministic(self):
        request = PlanningRequest(user_request="Help me plan a trip to Japan")
        self.assertEqual(
            self.provider.create_plan(request),
            self.provider.create_plan(request),
        )

    def test_dependencies_form_a_linear_chain(self):
        plan = self.provider.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.steps[0].dependencies, [])
        for previous, step in zip(plan.steps, plan.steps[1:]):
            self.assertEqual(step.dependencies, [previous.step_number])


# =====================================================================
# PlanningEngine (collaborators mocked where useful)
# =====================================================================
class PlanningEngineTests(unittest.TestCase):
    def setUp(self):
        self.request = PlanningRequest(user_request="Help me plan a trip")
        self.plan = _valid_plan()
        self.provider = MagicMock(name="PlanningProvider")
        self.provider.create_plan.return_value = self.plan
        self.validator = MagicMock(name="PlanValidator")
        self.explanation_builder = MagicMock(name="PlanningExplanationBuilder")
        self.engine = PlanningEngine(
            self.provider, self.validator, self.explanation_builder
        )

    def test_create_plan_delegates_to_provider_once(self):
        self.engine.create_plan(self.request)
        self.provider.create_plan.assert_called_once_with(self.request)

    def test_create_plan_validates_the_plan(self):
        self.engine.create_plan(self.request)
        self.validator.validate.assert_called_once_with(self.plan)

    def test_create_plan_returns_the_validated_plan_unchanged(self):
        self.assertIs(self.engine.create_plan(self.request), self.plan)

    def test_provider_exception_propagates(self):
        self.provider.create_plan.side_effect = RuntimeError("planning boom")
        with self.assertRaises(RuntimeError):
            self.engine.create_plan(self.request)

    def test_explain_delegates_to_explanation_builder(self):
        self.explanation_builder.build.return_value = "an explanation"
        result = self.engine.explain(self.plan)
        self.explanation_builder.build.assert_called_once_with(self.plan)
        self.assertEqual(result, "an explanation")

    def test_stateless_only_injected_collaborators(self):
        self.assertEqual(
            set(vars(self.engine)),
            {"provider", "validator", "explanation_builder"},
        )

    def test_constructor_stores_injected_collaborators(self):
        self.assertIs(self.engine.provider, self.provider)
        self.assertIs(self.engine.validator, self.validator)
        self.assertIs(
            self.engine.explanation_builder, self.explanation_builder
        )


class PlanningEngineValidationIntegrationTests(unittest.TestCase):
    """Engine wired to the real validator rejects malformed provider output."""

    def _engine_with_plan(self, plan):
        provider = MagicMock(name="PlanningProvider")
        provider.create_plan.return_value = plan
        return PlanningEngine(
            provider, PlanValidator(), PlanningExplanationBuilder()
        )

    def test_engine_rejects_empty_plan(self):
        engine = self._engine_with_plan(
            ExecutionPlan(goal="g", summary="s", steps=[])
        )
        with self.assertRaises(PlanValidationError):
            engine.create_plan(PlanningRequest(user_request="x"))

    def test_engine_rejects_forward_dependency_plan(self):
        engine = self._engine_with_plan(
            ExecutionPlan(
                goal="g",
                summary="s",
                steps=[_step(1, "A", dependencies=[2]), _step(2, "B")],
            )
        )
        with self.assertRaises(PlanValidationError):
            engine.create_plan(PlanningRequest(user_request="x"))


class PlanningEngineEndToEndTests(unittest.TestCase):
    """Real provider + validator + builder, no mocks, no execution."""

    def setUp(self):
        self.engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
        )

    def test_plans_and_explains_a_travel_request(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")
        explanation = self.engine.explain(plan)
        self.assertIn("trip", explanation)
        self.assertIn("first", explanation)


# =====================================================================
# Provider independence
# =====================================================================
class ProviderIndependenceTests(unittest.TestCase):
    def test_engine_works_with_any_provider(self):
        custom_plan = _valid_plan(goal="Custom goal")

        class StubProvider(PlanningProvider):
            name = "stub"

            def create_plan(self, request):
                return custom_plan

        engine = PlanningEngine(
            StubProvider(), PlanValidator(), PlanningExplanationBuilder()
        )
        plan = engine.create_plan(PlanningRequest(user_request="anything"))
        self.assertIs(plan, custom_plan)
        self.assertEqual(plan.goal, "Custom goal")

    def test_plan_dtos_expose_no_provider_object(self):
        plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip")
        )
        # Round-trips through plain JSON — proves no SDK/provider object leaks.
        restored = ExecutionPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(restored, plan)


# =====================================================================
# Regression: frozen Sprint 11.4 planner untouched
# =====================================================================
class FrozenPlannerRegressionTests(unittest.TestCase):
    def test_planner_and_planning_execution_plans_are_distinct(self):
        self.assertIsNot(PlannerExecutionPlan, ExecutionPlan)

    def test_planner_execution_plan_shape_unchanged(self):
        plan = PlannerExecutionPlan()
        self.assertEqual(plan.steps, [])
        self.assertNotIn("goal", PlannerExecutionPlan.model_fields)

    def test_planner_planning_step_shape_unchanged(self):
        step = PlannerPlanningStep(tool_name="send_email", description="do it")
        self.assertEqual(step.tool_name, "send_email")

    def test_planning_execution_plan_has_reasoning_shape(self):
        self.assertIn("goal", ExecutionPlan.model_fields)
        self.assertIn("missing_information", ExecutionPlan.model_fields)

    def test_frozen_planner_provider_seam_still_raises(self):
        from app.core.dependencies import get_planner_provider

        with self.assertRaises(NotImplementedError):
            get_planner_provider()


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class PlanningDependencyTests(unittest.TestCase):
    def test_planning_provider_is_the_heuristic_default(self):
        from app.core.dependencies import get_planning_provider

        self.assertIsInstance(
            get_planning_provider(), HeuristicPlanningProvider
        )

    def test_plan_validator_resolves(self):
        from app.core.dependencies import get_plan_validator

        self.assertIsInstance(get_plan_validator(), PlanValidator)

    def test_explanation_builder_resolves(self):
        from app.core.dependencies import get_planning_explanation_builder

        self.assertIsInstance(
            get_planning_explanation_builder(), PlanningExplanationBuilder
        )

    def test_engine_resolves_with_injected_collaborators(self):
        from app.core.dependencies import get_planning_engine

        provider = MagicMock(name="PlanningProvider")
        validator = MagicMock(name="PlanValidator")
        builder = MagicMock(name="PlanningExplanationBuilder")
        engine = get_planning_engine(provider, validator, builder)
        self.assertIsInstance(engine, PlanningEngine)
        self.assertIs(engine.provider, provider)
        self.assertIs(engine.validator, validator)
        self.assertIs(engine.explanation_builder, builder)

    def test_composition_root_produces_working_engine(self):
        from app.core.dependencies import (
            get_plan_validator,
            get_planning_engine,
            get_planning_explanation_builder,
            get_planning_provider,
        )

        engine = get_planning_engine(
            get_planning_provider(),
            get_plan_validator(),
            get_planning_explanation_builder(),
        )
        plan = engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertTrue(plan.steps)
        self.assertTrue(engine.explain(plan))


if __name__ == "__main__":
    unittest.main()
