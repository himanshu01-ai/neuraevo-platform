"""Execution intent engine (Sprint 13.5 — deterministic intent from decision).

Reasoning-only component that converts an :class:`ExecutionDecision` (weighed
alongside its :class:`ExecutionPlan`, :class:`PlanAnalysis`, and
:class:`ExecutionPreparation`) into an immutable :class:`ExecutionIntent`. It
records an intention only — execute now, wait, defer, or cancel — and never
executes, resolves, or acquires anything.

Fully deterministic and offline: no AI, network, SDK, Runtime, Session, Registry,
Tool framework, Memory, or Gemini. Same inputs in -> same intent out.
"""

from app.services.planning.analysis_models import PlanAnalysis
from app.services.planning.decision_models import DecisionStatus, ExecutionDecision
from app.services.planning.execution_intent_models import (
    ExecutionIntent,
    ExecutionIntentType,
)
from app.services.planning.execution_preparation_models import (
    ExecutionPreparation,
)
from app.services.planning.models import ExecutionPlan

# Decision status -> intent (the mandated deterministic mapping).
_STATUS_TO_INTENT = {
    DecisionStatus.APPROVED.value: ExecutionIntentType.EXECUTE_NOW.value,
    DecisionStatus.WAITING_FOR_INFORMATION.value: (
        ExecutionIntentType.WAIT_FOR_USER.value
    ),
    DecisionStatus.WAITING_FOR_CONFIRMATION.value: (
        ExecutionIntentType.WAIT_FOR_USER.value
    ),
    DecisionStatus.BLOCKED.value: ExecutionIntentType.DEFER.value,
    DecisionStatus.REJECTED.value: ExecutionIntentType.CANCEL.value,
}

# Intent -> deterministic next-step guidance (plain language).
_NEXT_STEP = {
    ExecutionIntentType.EXECUTE_NOW.value: "Proceed with execution.",
    ExecutionIntentType.WAIT_FOR_USER.value: (
        "Wait for the user to supply the required information or confirmation."
    ),
    ExecutionIntentType.DEFER.value: (
        "Resolve the outstanding requirements, then re-evaluate."
    ),
    ExecutionIntentType.CANCEL.value: (
        "Abandon this plan; a new plan is required."
    ),
}

# Intent -> deterministic non-negative urgency score (higher = act sooner).
_PRIORITY = {
    ExecutionIntentType.EXECUTE_NOW.value: 3,
    ExecutionIntentType.WAIT_FOR_USER.value: 2,
    ExecutionIntentType.DEFER.value: 1,
    ExecutionIntentType.CANCEL.value: 0,
}


class ExecutionIntentEngine:
    """Stateless converter: decision -> :class:`ExecutionIntent`.

    Holds no state and owns no session, provider, or cache. It maps the decision
    status to exactly one :class:`ExecutionIntentType` via the mandated
    deterministic mapping and derives the remaining fields from that intent (plus
    the decision's blockers for a deferral reason). It never executes a step.
    """

    def create_intent(
        self,
        plan: ExecutionPlan,
        analysis: PlanAnalysis,
        preparation: ExecutionPreparation,
        decision: ExecutionDecision,
    ) -> ExecutionIntent:
        """Return a deterministic :class:`ExecutionIntent` for ``decision``.

        The intent follows the fixed status→intent mapping; ``should_execute`` is
        true only for ``EXECUTE_NOW`` and ``requires_user_action`` only for
        ``WAIT_FOR_USER``; ``defer_reason`` is populated only when deferring. The
        plan, analysis, and preparation are accepted as the upstream reasoning
        context. Nothing is executed.
        """
        intent = _STATUS_TO_INTENT[decision.status]
        return ExecutionIntent(
            intent=intent,
            should_execute=intent == ExecutionIntentType.EXECUTE_NOW.value,
            requires_user_action=(
                intent == ExecutionIntentType.WAIT_FOR_USER.value
            ),
            recommended_next_step=_NEXT_STEP[intent],
            execution_priority=_PRIORITY[intent],
            defer_reason=self._defer_reason(intent, decision),
        )

    @staticmethod
    def _defer_reason(intent: str, decision: ExecutionDecision) -> str:
        """Explain a deferral from the decision's blockers (empty otherwise)."""
        if intent != ExecutionIntentType.DEFER.value:
            return ""
        reasons = ", ".join(decision.blocking_reasons) or "unmet requirements"
        return f"Deferred until resolved: {reasons}."
