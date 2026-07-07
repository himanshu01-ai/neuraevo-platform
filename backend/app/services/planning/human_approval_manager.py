"""Human approval manager (Sprint 13.14 — deterministic approval governance).

Reasoning-only component that consumes an :class:`ExecutionIntent`, an
:class:`ExecutionSchedule`, and a :class:`RecoveryPlan` and produces a single
immutable, provider-independent :class:`ApprovalPlan`. It GOVERNS approval: it
decides whether human sign-off is required, builds deterministic checkpoints over
the scheduled execution units, identifies the pending approvals, and marks which
nodes are cleared versus held — but it never requests approval, resumes, retries,
executes, resolves, or acquires anything, and it never mutates its inputs.

Fully deterministic and offline: no AI, network, SDK, Runtime, Session, Registry,
Permission, Tool framework, Memory, or Gemini. Same inputs in -> same plan out.
"""

from typing import List, Tuple

from app.services.planning.approval_models import (
    ApprovalCheckpoint,
    ApprovalPlan,
    ApprovalStrategy,
)
from app.services.planning.execution_intent_models import (
    ExecutionIntent,
    ExecutionIntentType,
)
from app.services.planning.execution_schedule_models import ExecutionSchedule
from app.services.planning.recovery_models import RecoveryPlan, RecoveryStrategy

# Recovery strategies that gate on a recovery approval / a manual review.
_RECOVERY_APPROVAL = frozenset(
    {RecoveryStrategy.RETRY.value, RecoveryStrategy.RESUME.value}
)
_RECOVERY_REVIEW = frozenset(
    {RecoveryStrategy.REPLAN.value, RecoveryStrategy.ABORT.value}
)

# Plain-language reason per approval strategy (no implementation terms).
_PLAN_REASONS = {
    ApprovalStrategy.NO_APPROVAL: (
        "No approval is required; execution may proceed."
    ),
    ApprovalStrategy.BEFORE_EXECUTION: (
        "Approval is required before execution begins."
    ),
    ApprovalStrategy.BEFORE_RECOVERY: (
        "Approval is required before recovery is carried out."
    ),
    ApprovalStrategy.MANUAL_REVIEW: (
        "Manual review is required before anything continues."
    ),
}
_REASON_EMPTY = "No execution is scheduled; no approval is required."

# Plain-language reason per checkpoint (no implementation terms).
_CHECKPOINT_REASONS = {
    ApprovalStrategy.BEFORE_EXECUTION: "Approval required before this step runs.",
    ApprovalStrategy.BEFORE_RECOVERY: (
        "Approval required before recovery proceeds."
    ),
    ApprovalStrategy.MANUAL_REVIEW: (
        "Manual review required before this step continues."
    ),
}


class HumanApprovalManager:
    """Stateless manager: (intent, schedule, recovery) -> :class:`ApprovalPlan`.

    Holds no state and owns no session, provider, or cache. The recovery plan and
    intent decide the strategy — a recovery gate takes precedence over the
    pre-execution intent gate — while the schedule supplies the concrete
    execution units the checkpoints govern. It governs only; it never requests
    approval, resumes, or executes a step, and never mutates its inputs.
    """

    def create_approval_plan(
        self,
        intent: ExecutionIntent,
        schedule: ExecutionSchedule,
        recovery: RecoveryPlan,
    ) -> ApprovalPlan:
        """Return a deterministic :class:`ApprovalPlan` (no execution).

        Selects a strategy: an empty schedule needs no approval; a recovery that
        retries or resumes gates before recovery, while one that replans or aborts
        needs manual review; otherwise a ``WAIT_FOR_USER`` intent gates before
        execution and everything else needs no approval. When approval is
        required, one checkpoint is created per scheduled execution unit and every
        checkpoint is pending; those nodes are held while the rest are cleared.
        Inputs are only read.
        """
        scheduled_ids = [node.node_id for node in schedule.scheduled_nodes]
        strategy, reason = self._select(intent, schedule, recovery)

        requires_approval = strategy is not ApprovalStrategy.NO_APPROVAL

        if requires_approval:
            checkpoints = [
                ApprovalCheckpoint(
                    checkpoint_id=f"checkpoint-{node.execution_unit_id}",
                    execution_unit_id=node.execution_unit_id,
                    reason=_CHECKPOINT_REASONS[strategy],
                    required=True,
                    metadata={"node_id": node.node_id},
                )
                for node in schedule.scheduled_nodes
            ]
            pending_approvals = [cp.checkpoint_id for cp in checkpoints]
            approved_nodes: List[str] = []
            blocked_nodes = list(scheduled_ids)
        else:
            checkpoints = []
            pending_approvals = []
            approved_nodes = list(scheduled_ids)
            blocked_nodes = []

        return ApprovalPlan(
            approval_id=f"approval-{schedule.execution_id}",
            execution_id=schedule.execution_id,
            approval_strategy=strategy.value,
            approval_checkpoints=checkpoints,
            pending_approvals=pending_approvals,
            approved_nodes=approved_nodes,
            blocked_nodes=blocked_nodes,
            requires_approval=requires_approval,
            approval_reason=reason,
            metadata={
                "approval_strategy": strategy.value,
                "recovery_strategy": recovery.recovery_strategy,
                "intent": intent.intent,
                "checkpoint_count": len(checkpoints),
                "pending_count": len(pending_approvals),
                "approved_count": len(approved_nodes),
                "blocked_count": len(blocked_nodes),
            },
        )

    @staticmethod
    def _select(
        intent: ExecutionIntent,
        schedule: ExecutionSchedule,
        recovery: RecoveryPlan,
    ) -> Tuple[ApprovalStrategy, str]:
        """Choose the (strategy, reason) pair deterministically.

        An empty schedule needs no approval. A recovery that replans or aborts
        needs a manual review; one that retries or resumes gates before recovery.
        Otherwise a ``WAIT_FOR_USER`` intent gates before execution, and any other
        intent needs no approval. The recovery gate is checked before the intent
        gate so an active recovery governs approval.
        """
        empty = not (
            schedule.scheduled_nodes
            or schedule.deferred_nodes
            or schedule.blocked_nodes
        )
        if empty:
            return ApprovalStrategy.NO_APPROVAL, _REASON_EMPTY

        if recovery.recovery_strategy in _RECOVERY_REVIEW:
            return (
                ApprovalStrategy.MANUAL_REVIEW,
                _PLAN_REASONS[ApprovalStrategy.MANUAL_REVIEW],
            )
        if recovery.recovery_strategy in _RECOVERY_APPROVAL:
            return (
                ApprovalStrategy.BEFORE_RECOVERY,
                _PLAN_REASONS[ApprovalStrategy.BEFORE_RECOVERY],
            )
        if intent.intent == ExecutionIntentType.WAIT_FOR_USER.value:
            return (
                ApprovalStrategy.BEFORE_EXECUTION,
                _PLAN_REASONS[ApprovalStrategy.BEFORE_EXECUTION],
            )
        return (
            ApprovalStrategy.NO_APPROVAL,
            _PLAN_REASONS[ApprovalStrategy.NO_APPROVAL],
        )
