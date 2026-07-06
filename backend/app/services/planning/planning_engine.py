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
from app.services.planning.execution_preparation_engine import (
    ExecutionPreparationEngine,
)
from app.services.planning.execution_preparation_models import (
    ExecutionPreparation,
)
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
        preparation_engine: Optional[ExecutionPreparationEngine] = None,
    ) -> None:
        self.provider = provider
        self.validator = validator
        self.explanation_builder = explanation_builder
        # Sprint 13.2/13.3: the analyzer and preparation engine are optional,
        # additive collaborators. Each is stored only when injected so that
        # earlier-sprint construction (three or four arguments) keeps exactly its
        # original attributes and its tests pass unchanged. ``analyze`` requires
        # the analyzer and ``prepare`` requires the preparation engine;
        # ``create_plan``/``explain`` require neither.
        if analyzer is not None:
            self.analyzer = analyzer
        if preparation_engine is not None:
            self.preparation_engine = preparation_engine

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

    def prepare(
        self, plan: ExecutionPlan, analysis: PlanAnalysis
    ) -> ExecutionPreparation:
        """Prepare ``plan`` for eventual execution (PREPARATION ONLY).

        Sprint 13.3 addition. Delegates to the injected
        :class:`ExecutionPreparationEngine` to determine which capabilities,
        services, and permissions the plan would require, how it would be
        sequenced, and what blocks it — then validates the result via the
        injected :class:`PlanValidator`. The ``analysis`` is accepted as the
        upstream reasoning context for this pipeline stage; the preparation is
        derived from the plan itself (which already carries the missing-info and
        confirmation signals). Nothing is executed, resolved, or acquired. Raises
        :class:`RuntimeError` if no preparation engine was injected and
        :class:`PlanValidationError` if the preparation is malformed; engine
        exceptions propagate unchanged.
        """
        preparation_engine = getattr(self, "preparation_engine", None)
        if preparation_engine is None:
            raise RuntimeError(
                "PlanningEngine has no ExecutionPreparationEngine injected; "
                "provide one to call prepare()."
            )
        preparation = preparation_engine.prepare(plan)
        self.validator.validate_preparation(preparation)
        return preparation
