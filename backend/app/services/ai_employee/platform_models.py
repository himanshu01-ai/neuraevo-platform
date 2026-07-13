"""AI Employee Execution Platform models (Sprint 16.2 — immutable job DTOs).

Provider-independent, immutable DTOs, enums, and the lifecycle error for the AI
Employee Execution Platform: the lifecycle state, the progress snapshot, the
stored notification, the approval decision, the persistence snapshot, and the
:class:`WorkflowInstance` that owns one delegated job. This layer introduces the
*lifecycle of a delegated job* and coordinates the existing Sprint 13 Planning
Engine and Sprint 15.15 Workflow Coordinator through extensible managers — it
plans nothing, executes no capability, and never imports a capability module.

These carry only plain data plus the frozen Sprint 13 :class:`ExecutionPlan` and
the frozen Sprint 15.15 :class:`WorkflowStep` / :class:`WorkflowExecutionResult`
— never a provider/SDK object crosses this boundary, and manager references are
exposed as plain string descriptors. Strictly additive to Sprints 1.x–16.1,
whose modules are left untouched. The coordination that produces these lives in
:mod:`app.services.ai_employee.workflow_lifecycle_manager` and the extensible
managers around it.
"""

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.planning.models import ExecutionPlan
from app.services.runtime.workflow_models import (
    WorkflowExecutionResult,
    WorkflowStep,
)

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class WorkflowLifecycleError(Exception):
    """Raised on an invalid lifecycle transition (e.g. pausing a completed job).

    The lifecycle manager validates each transition against the deterministic
    transition table before applying it and raises this when a caller requests an
    illegal move; it never leaves an instance in a half-changed state.
    """


class WorkflowLifecycleStatus(str, Enum):
    """The allowed, deterministic lifecycle statuses of a :class:`WorkflowInstance`.

    ``PENDING`` — created, not started. ``RUNNING`` — started (or resumed/retried).
    ``PAUSED`` — temporarily halted. ``CANCELLED`` — terminated by the operator.
    ``COMPLETED`` — the coordinated workflow finished. ``FAILED`` — the workflow
    failed (retryable via the Recovery Manager). Kept as a ``str`` enum so each
    serialises to its label.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkflowProgressStatus(str, Enum):
    """The allowed, deterministic progress statuses of a :class:`WorkflowProgress`.

    ``PENDING`` — no step completed yet. ``IN_PROGRESS`` — some but not all steps
    completed. ``COMPLETED`` — every step completed. ``FAILED`` — a step failed.
    Kept as a ``str`` enum so each serialises to its label.
    """

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkflowNotificationEvent(str, Enum):
    """The allowed, deterministic notification events (stored, never delivered).

    ``WORKFLOW_STARTED``/``WORKFLOW_COMPLETED``/``WORKFLOW_FAILED`` mark lifecycle
    milestones and ``APPROVAL_REQUIRED`` marks a gated run. Kept as a ``str`` enum
    so each serialises to its label.
    """

    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    APPROVAL_REQUIRED = "approval_required"


class WorkflowLifecycleState(BaseModel):
    """Immutable lifecycle state of one delegated job (a transition produces a new one).

    ``frozen=True`` makes instances immutable. ``status`` is the current
    :class:`WorkflowLifecycleStatus`; ``previous_status`` is the status it moved
    from (``None`` at genesis); ``attempt`` is the retry counter (0 until the
    Recovery Manager retries); ``is_terminal`` marks a status no further transition
    leaves (``COMPLETED``/``CANCELLED``); ``transition_sequence`` is a deterministic
    ordinal that increments once per transition (an integer, never a clock time);
    and ``state_metadata`` carries plain descriptors. Producing this DTO runs
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    status: WorkflowLifecycleStatus = WorkflowLifecycleStatus.PENDING
    previous_status: Optional[WorkflowLifecycleStatus] = None
    attempt: int = Field(default=0, ge=0)
    is_terminal: bool = False
    transition_sequence: int = Field(default=0, ge=0)
    state_metadata: Dict[str, Any] = Field(default_factory=dict)

    def transition_to(
        self,
        status: WorkflowLifecycleStatus,
        *,
        terminal: bool = False,
        attempt: Optional[int] = None,
    ) -> "WorkflowLifecycleState":
        """Return the next immutable state (pure construction — no validation).

        Builds a new :class:`WorkflowLifecycleState` whose ``previous_status`` is
        this state's ``status``, whose ``transition_sequence`` is one greater, and
        whose ``attempt`` is carried over unless overridden (the Recovery Manager
        overrides it on retry). This is a deterministic data transform only — it
        makes no decision about whether the transition is *allowed* (the lifecycle
        manager owns that guard) and executes nothing.
        """
        return WorkflowLifecycleState(
            status=status,
            previous_status=self.status,
            attempt=self.attempt if attempt is None else attempt,
            is_terminal=terminal,
            transition_sequence=self.transition_sequence + 1,
            state_metadata={},
        )


class WorkflowProgress(BaseModel):
    """Immutable progress snapshot of one delegated job (deterministic only).

    ``frozen=True`` makes instances immutable. ``current_step`` is the 1-based
    position the job is at (0 before it starts); ``total_steps`` is the workflow's
    step count; ``completed_steps`` is how many finished; ``failed_step`` names the
    step that failed (``None`` otherwise); ``percentage`` is the integer completion
    0–100; and ``status`` is one of the :class:`WorkflowProgressStatus` labels.
    ``progress_metadata`` carries plain descriptors. Producing this DTO runs
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    current_step: int = Field(default=0, ge=0)
    total_steps: int = Field(default=0, ge=0)
    completed_steps: int = Field(default=0, ge=0)
    failed_step: Optional[str] = None
    percentage: int = Field(default=0, ge=0, le=100)
    status: WorkflowProgressStatus = WorkflowProgressStatus.PENDING
    progress_metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowNotification(BaseModel):
    """Immutable stored notification about a job (stored only — never delivered).

    ``frozen=True`` makes instances immutable. ``notification_id`` is the
    deterministic ``"notification-<instance_id>-<sequence>"`` handle;
    ``workflow_instance_id`` links it to its job; ``event`` is one of the
    :class:`WorkflowNotificationEvent` labels; ``message`` is a plain-text summary;
    ``sequence`` is the deterministic per-instance ordinal; and
    ``notification_metadata`` carries plain descriptors. This is a record only —
    the Notification Manager stores it and does not push, email, or otherwise
    deliver it (delivery belongs to a later Sprint 16.x).
    """

    model_config = ConfigDict(frozen=True)

    notification_id: _NonEmptyStr
    workflow_instance_id: _NonEmptyStr
    event: WorkflowNotificationEvent
    message: str = ""
    sequence: int = Field(default=0, ge=0)
    notification_metadata: Dict[str, Any] = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    """Immutable outcome of an approval check (no UI, voice, mobile, or permissions).

    ``frozen=True`` makes instances immutable. ``workflow_instance_id`` links the
    decision to its job; ``approved`` is the verdict; ``requires_approval`` records
    whether the policy would have gated the run; ``policy`` names the deciding
    policy (e.g. ``"AutoApprovalPolicy"``); ``reason`` is a plain-text rationale;
    and ``decision_metadata`` carries plain descriptors. Producing this DTO runs
    nothing and touches no permission system.
    """

    model_config = ConfigDict(frozen=True)

    workflow_instance_id: _NonEmptyStr
    approved: bool
    requires_approval: bool = False
    policy: str = ""
    reason: str = ""
    decision_metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowInstance(BaseModel):
    """Immutable state of one delegated job (owns lifecycle, progress, references).

    ``frozen=True`` makes instances immutable, so every lifecycle transition
    produces a new instance rather than mutating this one. ``instance_id``
    deterministically names the job; ``employee_id``/``task_id`` link it to its
    employee and delegation; ``workflow_id`` names the coordinated workflow;
    ``lifecycle_state`` is the owned :class:`WorkflowLifecycleState`; ``progress``
    is the owned :class:`WorkflowProgress`; ``plan`` is the reasoned Sprint 13
    :class:`ExecutionPlan`; ``workflow_steps`` are the Sprint 15.15
    :class:`WorkflowStep` records the Workflow Coordinator will run;
    ``total_steps`` is their count; ``workflow_result`` is the Sprint 15.15
    :class:`WorkflowExecutionResult` (``None`` until the job runs);
    ``manager_references`` maps a collaborator name to a plain descriptor (its
    class name — never the live object, so no SDK/manager object crosses the
    boundary); and ``instance_metadata`` carries plain descriptors. The instance
    owns state only — it never executes a capability itself.
    """

    model_config = ConfigDict(frozen=True)

    instance_id: _NonEmptyStr
    employee_id: _NonEmptyStr
    task_id: _NonEmptyStr
    workflow_id: _NonEmptyStr
    lifecycle_state: WorkflowLifecycleState
    progress: WorkflowProgress
    plan: ExecutionPlan
    workflow_steps: List[WorkflowStep] = Field(default_factory=list)
    total_steps: int = Field(default=0, ge=0)
    workflow_result: Optional[WorkflowExecutionResult] = None
    manager_references: Dict[str, str] = Field(default_factory=dict)
    instance_metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowSnapshot(BaseModel):
    """Immutable point-in-time capture of a :class:`WorkflowInstance` for persistence.

    ``frozen=True`` makes instances immutable. ``snapshot_id`` is the deterministic
    ``"snapshot-<instance_id>-<sequence>"`` handle; ``workflow_instance_id`` links
    it to its job; ``instance`` is the captured :class:`WorkflowInstance` (itself
    frozen); ``sequence`` is the deterministic save ordinal; and
    ``snapshot_metadata`` carries plain descriptors. The Persistence Manager
    produces one per save; producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    snapshot_id: _NonEmptyStr
    workflow_instance_id: _NonEmptyStr
    instance: WorkflowInstance
    sequence: int = Field(default=0, ge=0)
    snapshot_metadata: Dict[str, Any] = Field(default_factory=dict)
