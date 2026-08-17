"""Approval ↔ workflow integration (Sprint 16.3 — pause/resume/cancel on approval).

Defines :class:`ApprovalWorkflowCoordinator`, the additive integration that wires
approval outcomes to workflow lifecycle transitions without touching either frozen
component. It uses the injected Sprint 16.2 :class:`WorkflowLifecycleManager`
(through its existing public ``start``/``pause``/``resume``/``cancel`` transitions)
and the Sprint 16.3 :class:`ApprovalManager` engine (the single approval entry
point) to realise the required behaviour:

    approval required  ->  workflow pauses, request enqueued (PENDING)
    approved           ->  workflow resumes
    rejected           ->  workflow cancelled

It redesigns neither the :class:`WorkflowInstance` nor the
:class:`WorkflowLifecycleManager`; it delegates every approval decision to the
engine and every state change to the lifecycle manager. It executes no capability,
schedules nothing, and sends no notification. Constructor injection only;
stateless beyond its two collaborators; deterministic. Strictly additive to
Sprints 1.x–16.2.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.ai_employee.approval.manager import ApprovalManager
from app.services.ai_employee.approval.models import (
    ApprovalDecision,
    ApprovalDecisionStatus,
    ApprovalRequest,
)
from app.services.ai_employee.platform_models import (
    WorkflowInstance,
    WorkflowLifecycleStatus,
)
from app.services.ai_employee.workflow_lifecycle_manager import (
    WorkflowLifecycleManager,
)


class ApprovalWorkflowOutcome(BaseModel):
    """Immutable result of an approval step over a workflow (no execution).

    ``frozen=True`` makes instances immutable. ``instance`` is the resulting
    :class:`WorkflowInstance` after any lifecycle transition (paused, resumed, or
    cancelled); ``request`` is the raised :class:`ApprovalRequest`; ``decision`` is
    the :class:`ApprovalDecision` the engine recorded; and ``outcome_metadata``
    carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    instance: WorkflowInstance
    request: ApprovalRequest
    decision: ApprovalDecision
    outcome_metadata: Dict[str, Any] = Field(default_factory=dict)


class ApprovalWorkflowCoordinator:
    """Wires approval outcomes to lifecycle transitions (uses both, redesigns none).

    Constructed with an injected :class:`WorkflowLifecycleManager` and
    :class:`ApprovalManager` (constructor injection; it instantiates neither). It
    delegates every approval decision to the engine and every state change to the
    lifecycle manager's public transitions. It holds no mutable state, executes no
    capability, and never persists a workflow itself.
    """

    def __init__(
        self,
        lifecycle_manager: WorkflowLifecycleManager,
        approval_manager: ApprovalManager,
    ) -> None:
        self.lifecycle_manager = lifecycle_manager
        self.approval_manager = approval_manager

    def request_approval(
        self,
        instance: WorkflowInstance,
        step_id: str,
        requested_action: str,
        reason: str = "",
    ) -> ApprovalWorkflowOutcome:
        """Raise an approval request for a step and pause the job if it is gated.

        Ensures the job is ``RUNNING`` (starting a ``PENDING`` one first), raises a
        deterministic :class:`ApprovalRequest`, and submits it to the engine. When
        the engine returns ``PENDING`` (approval required) the workflow is paused
        via the lifecycle manager and the request is left enqueued; when the engine
        auto-approves, the workflow keeps running. The engine owns the decision —
        this only maps it to a lifecycle transition.
        """
        running = self._ensure_running(instance)
        request = self.approval_manager.create_request(
            running.workflow_id, step_id, requested_action, reason
        )
        decision = self.approval_manager.submit(request)
        if decision.decision == ApprovalDecisionStatus.PENDING:
            paused = self.lifecycle_manager.pause(running)
            return ApprovalWorkflowOutcome(
                instance=paused, request=request, decision=decision
            )
        return ApprovalWorkflowOutcome(
            instance=running, request=request, decision=decision
        )

    def approve(
        self,
        instance: WorkflowInstance,
        request: ApprovalRequest,
        approver_id: str,
        reason: str = "",
    ) -> ApprovalWorkflowOutcome:
        """Record an approval and resume the paused workflow.

        Delegates the ``APPROVED`` decision to the engine, then resumes the job via
        the lifecycle manager (``PAUSED -> RUNNING``).
        """
        decision = self.approval_manager.approve(request, approver_id, reason)
        resumed = self.lifecycle_manager.resume(instance)
        return ApprovalWorkflowOutcome(
            instance=resumed, request=request, decision=decision
        )

    def reject(
        self,
        instance: WorkflowInstance,
        request: ApprovalRequest,
        approver_id: str,
        reason: str = "",
    ) -> ApprovalWorkflowOutcome:
        """Record a rejection and cancel the workflow.

        Delegates the ``REJECTED`` decision to the engine, then cancels the job via
        the lifecycle manager (``-> CANCELLED``).
        """
        decision = self.approval_manager.reject(request, approver_id, reason)
        cancelled = self.lifecycle_manager.cancel(instance)
        return ApprovalWorkflowOutcome(
            instance=cancelled, request=request, decision=decision
        )

    def _ensure_running(
        self, instance: WorkflowInstance
    ) -> WorkflowInstance:
        """Return a ``RUNNING`` instance, starting a ``PENDING`` one if needed."""
        if instance.lifecycle_state.status == WorkflowLifecycleStatus.PENDING:
            return self.lifecycle_manager.start(instance)
        return instance
