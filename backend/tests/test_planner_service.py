"""Unit tests for the Sprint 11.4 Planner framework (abstraction only).

The provider is mocked, so no network, SDK, AI, tool execution, permission
check, or registry is touched. The tests verify the provider abstraction, that
``PlannerService`` delegates to the injected provider exactly once (request
forwarded, plan returned unchanged, exceptions propagated), that the service is
a stateless, constructor-injected pass-through, the model contracts (validation
+ immutability + defaults), and the composition-root wiring.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_planner_service
"""

import unittest
from unittest.mock import MagicMock

from pydantic import ValidationError

from app.services.planner import (
    ExecutionPlan,
    PlannerProvider,
    PlannerService,
    PlanningStep,
)
from app.services.planner.providers.base import (
    PlannerProvider as BasePlannerProvider,
)


# =====================================================================
# Provider abstraction
# =====================================================================
class PlannerProviderAbstractionTests(unittest.TestCase):
    def test_provider_is_the_abstract_base(self):
        self.assertIs(PlannerProvider, BasePlannerProvider)

    def test_provider_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            PlannerProvider()  # abstract create_plan not implemented

    def test_concrete_subclass_is_instantiable(self):
        class OkProvider(PlannerProvider):
            name = "ok"

            def create_plan(self, user_request):
                return ExecutionPlan()

        provider = OkProvider()
        self.assertIsInstance(provider, PlannerProvider)


# =====================================================================
# PlannerService (provider mocked)
# =====================================================================
class PlannerServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user_request = "Email Ada tomorrow's agenda"
        self.plan = ExecutionPlan(
            steps=[
                PlanningStep(
                    tool_name="send_email",
                    arguments={"to": "ada@example.com"},
                    description="Send the agenda email",
                )
            ]
        )
        self.provider = MagicMock(name="PlannerProvider")
        self.provider.create_plan.return_value = self.plan
        self.service = PlannerService(self.provider)

    def test_delegates_to_provider_exactly_once(self):
        self.service.create_plan(self.user_request)
        self.provider.create_plan.assert_called_once()

    def test_request_forwarded_unchanged(self):
        self.service.create_plan(self.user_request)
        self.provider.create_plan.assert_called_once_with(self.user_request)
        self.assertIs(
            self.provider.create_plan.call_args.args[0], self.user_request
        )

    def test_result_returned_unchanged(self):
        result = self.service.create_plan(self.user_request)
        self.assertIs(result, self.plan)

    def test_provider_exception_propagates(self):
        self.provider.create_plan.side_effect = RuntimeError("planning boom")
        with self.assertRaises(RuntimeError):
            self.service.create_plan(self.user_request)

    def test_stateless_only_injected_provider(self):
        self.assertEqual(set(vars(self.service)), {"provider"})

    def test_constructor_uses_injected_provider(self):
        self.assertIs(self.service.provider, self.provider)


# =====================================================================
# Models: PlanningStep / ExecutionPlan validation, defaults, immutability
# =====================================================================
class PlannerModelTests(unittest.TestCase):
    def test_step_trims_tool_name_and_description(self):
        step = PlanningStep(
            tool_name="  send_email  ", description="  do it  "
        )
        self.assertEqual(step.tool_name, "send_email")
        self.assertEqual(step.description, "do it")

    def test_step_rejects_empty_tool_name(self):
        with self.assertRaises(ValidationError):
            PlanningStep(tool_name="", description="x")

    def test_step_rejects_whitespace_tool_name(self):
        with self.assertRaises(ValidationError):
            PlanningStep(tool_name="   ", description="x")

    def test_step_rejects_empty_description(self):
        with self.assertRaises(ValidationError):
            PlanningStep(tool_name="send_email", description="")

    def test_step_rejects_whitespace_description(self):
        with self.assertRaises(ValidationError):
            PlanningStep(tool_name="send_email", description="   ")

    def test_step_requires_tool_name_and_description(self):
        with self.assertRaises(ValidationError):
            PlanningStep()  # both required

    def test_step_arguments_default_empty(self):
        step = PlanningStep(tool_name="send_email", description="do it")
        self.assertEqual(step.arguments, {})

    def test_step_is_immutable(self):
        step = PlanningStep(tool_name="send_email", description="do it")
        with self.assertRaises(ValidationError):
            step.tool_name = "other"

    def test_plan_defaults_to_empty_steps(self):
        plan = ExecutionPlan()
        self.assertEqual(plan.steps, [])

    def test_plan_is_immutable(self):
        plan = ExecutionPlan()
        with self.assertRaises(ValidationError):
            plan.steps = [
                PlanningStep(tool_name="x", description="y")
            ]

    def test_plan_holds_steps(self):
        step = PlanningStep(tool_name="send_email", description="do it")
        plan = ExecutionPlan(steps=[step])
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].tool_name, "send_email")


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class PlannerDependencyTests(unittest.TestCase):
    def test_service_provider_resolves_with_injected_provider(self):
        from app.core.dependencies import get_planner_service

        provider = MagicMock(name="PlannerProvider")
        service = get_planner_service(provider)
        self.assertIsInstance(service, PlannerService)
        self.assertIs(service.provider, provider)

    def test_provider_seam_unfulfilled_until_later_sprint(self):
        # Sprint 11.4 ships only the framework: no concrete provider exists,
        # so the provider composition-root seam intentionally raises.
        from app.core.dependencies import get_planner_provider

        with self.assertRaises(NotImplementedError):
            get_planner_provider()


if __name__ == "__main__":
    unittest.main()
