"""Human Approval Engine package (Sprint 16.3 — production-grade approvals).

Enhances the Sprint 16.2 ApprovalManager abstraction additively into a
production-grade Human Approval Engine, following the flow
``ApprovalManager -> ApprovalPolicy -> ApprovalRequest -> ApprovalDecision``:

* the immutable DTOs :class:`ApprovalRequest`, :class:`ApprovalDecision`,
  :class:`ApprovalQueue`, :class:`ApprovalHistory`,
  :class:`ApprovalHistoryEntry`, and :class:`ApprovalPolicyResult`, plus the
  :class:`ApprovalRiskLevel` and :class:`ApprovalDecisionStatus` enums;
* the configurable :class:`RiskModel` (action -> risk level);
* the :class:`ApprovalPolicy` abstraction with :class:`AutoApprovalPolicy` and
  :class:`RiskBasedApprovalPolicy`;
* the deterministic in-memory :class:`ApprovalQueueManager`;
* the :class:`ApprovalManager` engine (the single approval entry point); and
* the :class:`ApprovalWorkflowCoordinator` integration that pauses/resumes/cancels
  a job via the frozen Sprint 16.2 :class:`WorkflowLifecycleManager`.

This package is strictly additive to — and leaves untouched — every frozen sprint
through 16.2, and it imports no capability module.
"""

from app.services.ai_employee.approval.coordinator import (
    ApprovalWorkflowCoordinator,
    ApprovalWorkflowOutcome,
)
from app.services.ai_employee.approval.manager import ApprovalManager
from app.services.ai_employee.approval.models import (
    ApprovalDecision,
    ApprovalDecisionStatus,
    ApprovalHistory,
    ApprovalHistoryEntry,
    ApprovalPolicyResult,
    ApprovalQueue,
    ApprovalRequest,
    ApprovalRiskLevel,
    RISK_ORDER,
)
from app.services.ai_employee.approval.policies import (
    ApprovalPolicy,
    AutoApprovalPolicy,
    RiskBasedApprovalPolicy,
)
from app.services.ai_employee.approval.queue import ApprovalQueueManager
from app.services.ai_employee.approval.risk import (
    DEFAULT_ACTION_RISK,
    RiskModel,
)

__all__ = [
    # DTOs & enums
    "ApprovalRequest",
    "ApprovalDecision",
    "ApprovalDecisionStatus",
    "ApprovalQueue",
    "ApprovalHistory",
    "ApprovalHistoryEntry",
    "ApprovalPolicyResult",
    "ApprovalRiskLevel",
    "RISK_ORDER",
    # risk model
    "RiskModel",
    "DEFAULT_ACTION_RISK",
    # policies
    "ApprovalPolicy",
    "AutoApprovalPolicy",
    "RiskBasedApprovalPolicy",
    # queue + engine + integration
    "ApprovalQueueManager",
    "ApprovalManager",
    "ApprovalWorkflowCoordinator",
    "ApprovalWorkflowOutcome",
]
