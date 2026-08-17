"""Approval manager (Sprint 16.2 — approval abstraction + auto policy).

Defines the :class:`ApprovalManager` abstraction and its basic implementation
:class:`AutoApprovalPolicy`. The abstraction lets later Sprint 16.x policies
(manual, role-based, threshold) plug in behind ``requires_approval``/``approve``/
``reject`` without any change to the lifecycle manager. The basic policy
auto-approves every job — it never gates a run.

No UI, no voice, no mobile, and no permission-system redesign: an approval is a
deterministic decision returned as an immutable :class:`ApprovalDecision`.
Stateless and deterministic. Strictly additive to Sprints 1.x–16.1.
"""

from abc import ABC, abstractmethod

from app.services.ai_employee.platform_models import (
    ApprovalDecision,
    WorkflowInstance,
)


class ApprovalManager(ABC):
    """Abstraction for deciding whether a delegated job may proceed (no execution).

    A policy answers three questions about a :class:`WorkflowInstance`: whether it
    ``requires_approval`` before running, and — when asked — an ``approve`` or
    ``reject`` :class:`ApprovalDecision`. Implementations must be deterministic and
    must not touch any UI, voice, mobile, or permission system. The lifecycle
    manager consults the policy but never assumes a concrete one.
    """

    @abstractmethod
    def requires_approval(self, instance: WorkflowInstance) -> bool:
        """Return whether ``instance`` must be approved before it may run."""

    @abstractmethod
    def approve(self, instance: WorkflowInstance) -> ApprovalDecision:
        """Return an approving :class:`ApprovalDecision` for ``instance``."""

    @abstractmethod
    def reject(self, instance: WorkflowInstance) -> ApprovalDecision:
        """Return a rejecting :class:`ApprovalDecision` for ``instance``."""


class AutoApprovalPolicy(ApprovalManager):
    """Basic policy that auto-approves every job — it never gates a run.

    ``requires_approval`` is always ``False``, so the lifecycle manager proceeds
    without a manual step; ``approve`` returns an approved decision and ``reject``
    a rejected one, both attributed to this policy. Deterministic and stateless;
    it touches no UI, voice, mobile, or permission system.
    """

    _POLICY_NAME = "AutoApprovalPolicy"

    def requires_approval(self, instance: WorkflowInstance) -> bool:
        """Return ``False`` — this policy never requires manual approval."""
        return False

    def approve(self, instance: WorkflowInstance) -> ApprovalDecision:
        """Return an approving decision attributed to this policy."""
        return ApprovalDecision(
            workflow_instance_id=instance.instance_id,
            approved=True,
            requires_approval=False,
            policy=self._POLICY_NAME,
            reason="auto-approved",
        )

    def reject(self, instance: WorkflowInstance) -> ApprovalDecision:
        """Return a rejecting decision attributed to this policy."""
        return ApprovalDecision(
            workflow_instance_id=instance.instance_id,
            approved=False,
            requires_approval=False,
            policy=self._POLICY_NAME,
            reason="rejected",
        )
