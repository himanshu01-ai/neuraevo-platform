"""Approval policies (Sprint 16.3 — policy abstraction + two implementations).

Defines the :class:`ApprovalPolicy` abstraction and two implementations that
*determine whether approval is required* for an :class:`ApprovalRequest`:

* :class:`AutoApprovalPolicy` — never requires approval (auto-approves every
  request); useful for trusted/low-stakes flows.
* :class:`RiskBasedApprovalPolicy` — requires approval when the request's risk
  level meets or exceeds a configurable threshold (default ``HIGH``); below the
  threshold it auto-approves.

Each policy is deterministic and stateless and returns an immutable
:class:`ApprovalPolicyResult`. Policies decide *whether* approval is required —
they neither queue, decide, execute, nor persist anything. Strictly additive to
Sprints 1.x–16.2.
"""

from abc import ABC, abstractmethod

from app.services.ai_employee.approval.models import (
    ApprovalDecisionStatus,
    ApprovalPolicyResult,
    ApprovalRequest,
    ApprovalRiskLevel,
    RISK_ORDER,
)


class ApprovalPolicy(ABC):
    """Abstraction that decides whether an :class:`ApprovalRequest` needs approval.

    An implementation reads the request (its risk level and action) and returns an
    :class:`ApprovalPolicyResult` — ``requires_approval`` plus the auto-decision it
    would apply otherwise. Implementations must be deterministic and must not
    queue, decide, execute, or persist anything; the engine coordinates those.
    """

    @abstractmethod
    def evaluate(self, request: ApprovalRequest) -> ApprovalPolicyResult:
        """Return the :class:`ApprovalPolicyResult` for ``request``."""


class AutoApprovalPolicy(ApprovalPolicy):
    """Policy that never requires approval — it auto-approves every request.

    Deterministic and stateless: ``evaluate`` always returns
    ``requires_approval=False`` with an ``APPROVED`` auto-decision, echoing the
    request's risk level for the audit trail. Distinct from the frozen Sprint 16.2
    ``AutoApprovalPolicy`` (which is a lifecycle :class:`ApprovalManager`); this one
    is an :class:`ApprovalPolicy` consulted by the Sprint 16.3 engine.
    """

    _POLICY_NAME = "AutoApprovalPolicy"

    def evaluate(self, request: ApprovalRequest) -> ApprovalPolicyResult:
        """Return an auto-approving result (approval never required)."""
        return ApprovalPolicyResult(
            policy=self._POLICY_NAME,
            requires_approval=False,
            risk_level=request.risk_level,
            reason="auto-approved (no approval required)",
            auto_decision=ApprovalDecisionStatus.APPROVED,
        )


class RiskBasedApprovalPolicy(ApprovalPolicy):
    """Policy that requires approval at or above a configurable risk threshold.

    Constructed with a ``threshold`` risk level (default ``HIGH``). ``evaluate``
    requires human approval when the request's risk level ranks at or above the
    threshold, and otherwise auto-approves. Deterministic and stateless; it decides
    only — it queues, decides, executes, and persists nothing.
    """

    _POLICY_NAME = "RiskBasedApprovalPolicy"

    def __init__(
        self, threshold: ApprovalRiskLevel = ApprovalRiskLevel.HIGH
    ) -> None:
        self.threshold = threshold

    def evaluate(self, request: ApprovalRequest) -> ApprovalPolicyResult:
        """Return a result gating on ``risk_level >= threshold``."""
        requires = RISK_ORDER[request.risk_level] >= RISK_ORDER[self.threshold]
        if requires:
            return ApprovalPolicyResult(
                policy=self._POLICY_NAME,
                requires_approval=True,
                risk_level=request.risk_level,
                reason=(
                    f"risk {request.risk_level.value} at or above threshold "
                    f"{self.threshold.value}; human approval required"
                ),
                auto_decision=None,
            )
        return ApprovalPolicyResult(
            policy=self._POLICY_NAME,
            requires_approval=False,
            risk_level=request.risk_level,
            reason=(
                f"risk {request.risk_level.value} below threshold "
                f"{self.threshold.value}; auto-approved"
            ),
            auto_decision=ApprovalDecisionStatus.APPROVED,
        )
