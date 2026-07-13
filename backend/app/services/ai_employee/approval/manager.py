"""Approval engine (Sprint 16.3 — the production-grade ApprovalManager).

Defines :class:`ApprovalManager`, the coordinator of the Human Approval Engine. It
follows the locked flow ``ApprovalManager -> ApprovalPolicy -> ApprovalRequest ->
ApprovalDecision`` and coordinates the injected :class:`ApprovalPolicy`,
:class:`RiskModel`, and :class:`ApprovalQueueManager`:

    create_request  (assess risk, build a deterministic request)
    evaluate        (ask the policy whether approval is required)
    submit          (auto-decide, or enqueue as PENDING)
    approve/reject/expire  (record a terminal decision, dequeue)
    pending / queue_snapshot / history  (read the queue and audit trail)

It coordinates the approval flow only: it never executes workflow logic, never
executes a capability, and never persists a workflow. Constructor injection only;
its only mutable state is a deterministic sequence counter and the audit history
(instance state — never static, singleton, or a service locator). Fully
deterministic (no clock, UUID, network, or SDK). Strictly additive to Sprints
1.x–16.2, whose modules are left untouched.
"""

from typing import List, Optional

from app.services.ai_employee.approval.models import (
    ApprovalDecision,
    ApprovalDecisionStatus,
    ApprovalHistory,
    ApprovalHistoryEntry,
    ApprovalPolicyResult,
    ApprovalQueue,
    ApprovalRequest,
    ApprovalRiskLevel,
)
from app.services.ai_employee.approval.policies import ApprovalPolicy
from app.services.ai_employee.approval.queue import ApprovalQueueManager
from app.services.ai_employee.approval.risk import RiskModel

# Approver id recorded when a policy auto-decides (no human involved).
_AUTO_APPROVER = "auto"


class ApprovalManager:
    """Coordinates the approval flow over policy, risk model, and queue.

    Constructed with an injected :class:`ApprovalPolicy`, :class:`RiskModel`, and
    :class:`ApprovalQueueManager` (constructor injection; it instantiates none of
    them). It assesses risk, raises requests, asks the policy whether approval is
    required, enqueues pending requests, records terminal decisions, and exposes
    the queue and an audit history. It holds a deterministic sequence counter and
    the history only; it executes no workflow, no capability, and persists no
    workflow. This is the single approval entry point.
    """

    def __init__(
        self,
        policy: ApprovalPolicy,
        risk_model: RiskModel,
        queue: ApprovalQueueManager,
    ) -> None:
        self.policy = policy
        self.risk_model = risk_model
        self.queue = queue
        self._sequence = 0
        self._history: List[ApprovalHistoryEntry] = []

    # --- risk & requests -------------------------------------------------
    def assess_risk(self, requested_action: str) -> ApprovalRiskLevel:
        """Assess the risk level of ``requested_action`` via the risk model."""
        return self.risk_model.assess(requested_action)

    def create_request(
        self,
        workflow_id: str,
        step_id: str,
        requested_action: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """Build a deterministic :class:`ApprovalRequest` (does not enqueue).

        Assesses the action's risk via the risk model, assigns the next
        deterministic ordinal and id, and returns the request. It neither evaluates
        a policy nor queues anything — ``submit`` does that.
        """
        self._sequence += 1
        return ApprovalRequest(
            request_id=f"approval-{workflow_id}-{step_id}-{self._sequence}",
            workflow_id=workflow_id,
            step_id=step_id,
            reason=reason,
            risk_level=self.risk_model.assess(requested_action),
            requested_action=requested_action,
            created_at_sequence=self._sequence,
        )

    def evaluate(self, request: ApprovalRequest) -> ApprovalPolicyResult:
        """Return the active policy's :class:`ApprovalPolicyResult` for ``request``."""
        return self.policy.evaluate(request)

    def requires_approval(self, request: ApprovalRequest) -> bool:
        """Return whether the active policy requires approval for ``request``."""
        return self.policy.evaluate(request).requires_approval

    # --- submission & decisions -----------------------------------------
    def submit(self, request: ApprovalRequest) -> ApprovalDecision:
        """Submit ``request`` for a decision (auto-decide, or enqueue as PENDING).

        Asks the policy: when approval is not required the request is auto-decided
        ``APPROVED`` (attributed to the ``auto`` approver); when it is required the
        request is enqueued and a ``PENDING`` decision is recorded to await a human.
        Either decision is appended to the audit history and returned. Nothing is
        executed or persisted.
        """
        result = self.policy.evaluate(request)
        if result.requires_approval:
            self.queue.enqueue(request)
            return self._decide(
                request,
                ApprovalDecisionStatus.PENDING,
                approver_id=None,
                reason=result.reason,
            )
        return self._decide(
            request,
            ApprovalDecisionStatus.APPROVED,
            approver_id=_AUTO_APPROVER,
            reason=result.reason,
        )

    def approve(
        self,
        request: ApprovalRequest,
        approver_id: str,
        reason: str = "",
    ) -> ApprovalDecision:
        """Record an ``APPROVED`` decision by ``approver_id`` and dequeue ``request``."""
        self.queue.dequeue(request.request_id)
        return self._decide(
            request,
            ApprovalDecisionStatus.APPROVED,
            approver_id=approver_id,
            reason=reason or "approved",
        )

    def reject(
        self,
        request: ApprovalRequest,
        approver_id: str,
        reason: str = "",
    ) -> ApprovalDecision:
        """Record a ``REJECTED`` decision by ``approver_id`` and dequeue ``request``."""
        self.queue.dequeue(request.request_id)
        return self._decide(
            request,
            ApprovalDecisionStatus.REJECTED,
            approver_id=approver_id,
            reason=reason or "rejected",
        )

    def expire(
        self, request: ApprovalRequest, reason: str = ""
    ) -> ApprovalDecision:
        """Record an ``EXPIRED`` decision for a lapsed pending ``request`` and dequeue it."""
        self.queue.dequeue(request.request_id)
        return self._decide(
            request,
            ApprovalDecisionStatus.EXPIRED,
            approver_id=None,
            reason=reason or "expired without decision",
        )

    # --- reads -----------------------------------------------------------
    def pending(self) -> List[ApprovalRequest]:
        """Return the pending requests awaiting a decision (enqueue order)."""
        return self.queue.pending()

    def find_by_workflow(self, workflow_id: str) -> List[ApprovalRequest]:
        """Return the pending requests for ``workflow_id``."""
        return self.queue.find_by_workflow(workflow_id)

    def queue_snapshot(self) -> ApprovalQueue:
        """Return an immutable snapshot of the pending-approval queue."""
        return self.queue.snapshot()

    def history(self) -> ApprovalHistory:
        """Return an immutable snapshot of the approval audit history."""
        entries = list(self._history)
        return ApprovalHistory(entries=entries, total=len(entries))

    # --- helpers ---------------------------------------------------------
    def _decide(
        self,
        request: ApprovalRequest,
        status: ApprovalDecisionStatus,
        approver_id: Optional[str],
        reason: str,
    ) -> ApprovalDecision:
        """Build a deterministic decision, append it to the history, and return it."""
        self._sequence += 1
        decision = ApprovalDecision(
            request_id=request.request_id,
            workflow_id=request.workflow_id,
            decision=status,
            approver_id=approver_id,
            reason=reason,
            decided_at_sequence=self._sequence,
        )
        self._history.append(
            ApprovalHistoryEntry(request=request, decision=decision)
        )
        return decision
