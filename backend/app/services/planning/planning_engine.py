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

from typing import Optional

from app.services.planning.analysis_models import PlanAnalysis
from app.services.planning.models import ExecutionPlan, PlanningRequest
from app.services.planning.plan_analyzer import PlanAnalyzer
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
        analyzer: Optional[PlanAnalyzer] = None,
    ) -> None:
        self.provider = provider
        self.validator = validator
        self.explanation_builder = explanation_builder
        # Sprint 13.2: the analyzer is an optional, additive collaborator. It is
        # stored only when injected so that Sprint 13.1 three-argument
        # construction keeps exactly its original attributes (and its tests pass
        # unchanged). ``analyze`` requires it; ``create_plan``/``explain`` do not.
        if analyzer is not None:
            self.analyzer = analyzer

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

    def analyze(self, plan: ExecutionPlan) -> PlanAnalysis:
        """Analyse ``plan`` into a validated :class:`PlanAnalysis` (reasoning only).

        Sprint 13.2 addition. Delegates to the injected :class:`PlanAnalyzer`,
        then validates the result via the injected :class:`PlanValidator` so
        every analysis the engine returns is guaranteed well-formed. Determines
        whether the plan is ready, needs confirmation, needs clarification, or is
        missing information — but executes nothing. Raises :class:`RuntimeError`
        if no analyzer was injected, and :class:`PlanValidationError` if the
        analysis is malformed; analyzer exceptions propagate unchanged.
        """
        analyzer = getattr(self, "analyzer", None)
        if analyzer is None:
            raise RuntimeError(
                "PlanningEngine has no PlanAnalyzer injected; provide one to "
                "call analyze()."
            )
        analysis = analyzer.analyze(plan)
        self.validator.validate_analysis(analysis)
        return analysis
