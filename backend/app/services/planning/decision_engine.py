"""Decision engine (Sprint 13.4 — deterministic execution decision).

Reasoning-only component that weighs an :class:`ExecutionPlan`, its
:class:`PlanAnalysis`, and its :class:`ExecutionPreparation` and produces an
immutable :class:`ExecutionDecision`. It classifies readiness into exactly one
:class:`DecisionStatus`; it never executes, resolves, or acquires anything.

Fully deterministic and offline: no AI, network, SDK, Runtime, Registry,
Permission, Tool execution, memory, or persistence. Same inputs in -> same
decision out.
"""

from app.services.planning.analysis_models import PlanAnalysis
from app.services.planning.decision_models import DecisionStatus, ExecutionDecision
from app.services.planning.execution_preparation_models import (
    ExecutionPreparation,
)
from app.services.planning.models import ExecutionPlan

# Blockers that represent hard, capability/permission/account requirements — as
# opposed to the softer "missing information" and "user approval" gates, which
# have their own dedicated statuses.
_HARD_BLOCKERS = frozenset(
    {"Need Permission", "Need Authentication", "Need External Account"}
)

# Deterministic, plain-language justification per decision.
_DECISION_REASONS = {
    DecisionStatus.APPROVED.value: (
        "All prerequisites are satisfied; the plan is approved for execution."
    ),
    DecisionStatus.WAITING_FOR_INFORMATION.value: (
        "Required information is missing; the plan is waiting for clarification."
    ),
    DecisionStatus.WAITING_FOR_CONFIRMATION.value: (
        "The plan is ready but requires user confirmation before proceeding."
    ),
    DecisionStatus.BLOCKED.value: (
        "The plan is blocked by unmet capability, permission, or account "
        "requirements."
    ),
    DecisionStatus.REJECTED.value: (
        "The plan cannot be executed as formulated."
    ),
}


class DecisionEngine:
    """Stateless decider: (plan, analysis, preparation) -> :class:`ExecutionDecision`.

    Holds no state and owns no session, provider, or cache. It classifies the
    plan into exactly one :class:`DecisionStatus` using a fixed precedence —
    rejected, then waiting-for-information, then blocked, then
    waiting-for-confirmation, then approved — so the outcome is always
    deterministic. It never executes a step.
    """

    def decide(
        self,
        plan: ExecutionPlan,
        analysis: PlanAnalysis,
        preparation: ExecutionPreparation,
    ) -> ExecutionDecision:
        """Return a deterministic :class:`ExecutionDecision` (no execution).

        The status is chosen by fixed precedence; ``can_execute`` is True only
        when approved; ``blocking_reasons`` restates what still stands in the way
        (the preparation's blockers, or the viability reason when rejected); and
        ``confidence`` is carried from the analysis. Nothing is executed.
        """
        status = self._classify(plan, analysis, preparation)
        can_execute = status == DecisionStatus.APPROVED.value
        if status == DecisionStatus.REJECTED.value:
            blocking_reasons = ["Plan has no steps"]
        else:
            blocking_reasons = list(preparation.blocked_by)

        return ExecutionDecision(
            status=status,
            can_execute=can_execute,
            reason=_DECISION_REASONS[status],
            blocking_reasons=blocking_reasons,
            confidence=analysis.confidence,
        )

    @staticmethod
    def _classify(
        plan: ExecutionPlan,
        analysis: PlanAnalysis,
        preparation: ExecutionPreparation,
    ) -> str:
        """Choose a single status by fixed, deterministic precedence."""
        # 1. Not viable at all — nothing to execute.
        if not plan.steps:
            return DecisionStatus.REJECTED.value
        # 2. Missing information must be gathered before anything else.
        if not analysis.ready_for_execution or analysis.missing_information:
            return DecisionStatus.WAITING_FOR_INFORMATION.value
        # 3. Hard capability/permission/account requirements block execution.
        if any(
            blocker in _HARD_BLOCKERS for blocker in preparation.blocked_by
        ):
            return DecisionStatus.BLOCKED.value
        # 4. Otherwise the only remaining gate is user confirmation.
        if analysis.requires_confirmation or plan.requires_user_confirmation:
            return DecisionStatus.WAITING_FOR_CONFIRMATION.value
        # 5. Everything is satisfied.
        return DecisionStatus.APPROVED.value
