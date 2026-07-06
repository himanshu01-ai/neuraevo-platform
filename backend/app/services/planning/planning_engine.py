"""Planning Engine (Sprint 13.1 — reason, validate, explain; never execute).

The Planning Engine teaches the AI Employee to *think before acting*. It sits
between the Conversation Runtime and a future execution layer and coordinates
three injected, provider-independent collaborators:

    PlanningProvider.create_plan()          -> ExecutionPlan  (reasoning)
    PlanValidator.validate()                -> guarantees well-formedness
    PlanningExplanationBuilder.build()      -> human explanation

It performs NO action execution, tool calls, permission checks, persistence, or
AI/SDK work of its own — it only reasons (via the provider), guarantees the plan
is valid, and can explain it. The output of the engine is a validated
:class:`ExecutionPlan`; nothing downstream is triggered here.
"""

from app.services.planning.models import ExecutionPlan, PlanningRequest
from app.services.planning.plan_explanation_builder import (
    PlanningExplanationBuilder,
)
from app.services.planning.plan_validator import PlanValidator
from app.services.planning.providers.base import PlanningProvider


class PlanningEngine:
    """Coordinates provider planning, validation, and explanation.

    Collaborators are injected (Dependency Inversion): the planning provider that
    produces the plan, the validator that guarantees it is well-formed, and the
    explanation builder that renders it for a human. Stateless beyond those three
    references — it holds no session, repository, or cache — so provider or
    strategy replacement requires no change here. The engine never executes a
    step.
    """

    def __init__(
        self,
        provider: PlanningProvider,
        validator: PlanValidator,
        explanation_builder: PlanningExplanationBuilder,
    ) -> None:
        self.provider = provider
        self.validator = validator
        self.explanation_builder = explanation_builder

    def create_plan(self, request: PlanningRequest) -> ExecutionPlan:
        """Reason about ``request`` and return a validated :class:`ExecutionPlan`.

        Delegates plan construction to the provider, then validates the result
        so every plan the engine returns is guaranteed well-formed. A malformed
        plan raises :class:`PlanValidationError`; provider exceptions propagate
        unchanged. Nothing is executed.
        """
        plan = self.provider.create_plan(request)
        self.validator.validate(plan)
        return plan

    def explain(self, plan: ExecutionPlan) -> str:
        """Return a plain-language explanation of ``plan`` (explanation only)."""
        return self.explanation_builder.build(plan)
