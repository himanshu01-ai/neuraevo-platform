"""Human Approval Engine models (Sprint 16.3 — immutable approval DTOs).

Provider-independent, immutable DTOs and enums for the production-grade Human
Approval Engine: the risk level, the decision status, the approval request, the
approval decision, the deterministic in-memory queue snapshot, the audit history,
and the policy-evaluation result. This layer *enhances* the Sprint 16.2
ApprovalManager abstraction additively — it introduces no change to any frozen
module and remains the single approval subsystem.

These carry only plain data — never a provider/SDK object, and never a live
manager/policy/queue object crosses the boundary. All timing is a deterministic
integer sequence (never a clock). Strictly additive to Sprints 1.x–16.2, whose
modules are left untouched.
"""

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class ApprovalRiskLevel(str, Enum):
    """The allowed, deterministic risk levels of a requested action.

    ``LOW`` (e.g. read file, search email, list calendar), ``MEDIUM`` (e.g. create
    event, draft email, git branch), ``HIGH`` (e.g. delete files, commit code, move
    repositories), and ``CRITICAL`` (e.g. send email, delete repository, future
    payment actions). The mapping from action to level lives in the *configurable*
    risk model, not here. Kept as a ``str`` enum so each serialises to its label.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Deterministic ordering of the risk levels (low → critical) for threshold
# comparisons. Kept beside the enum so every consumer ranks risk identically.
RISK_ORDER: Dict[ApprovalRiskLevel, int] = {
    ApprovalRiskLevel.LOW: 0,
    ApprovalRiskLevel.MEDIUM: 1,
    ApprovalRiskLevel.HIGH: 2,
    ApprovalRiskLevel.CRITICAL: 3,
}


class ApprovalDecisionStatus(str, Enum):
    """The allowed, deterministic states of an :class:`ApprovalDecision`.

    ``APPROVED`` — the action may proceed. ``REJECTED`` — the action is denied.
    ``PENDING`` — awaiting a human decision (queued). ``EXPIRED`` — the pending
    request lapsed without a decision. Kept as a ``str`` enum so each serialises to
    its label.
    """

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"
    EXPIRED = "EXPIRED"


class ApprovalRequest(BaseModel):
    """Immutable representation of one approval request (no execution).

    ``frozen=True`` makes instances immutable. ``request_id`` is the deterministic
    ``"approval-<workflow_id>-<step_id>-<sequence>"`` handle; ``workflow_id`` and
    ``step_id`` locate the gated step; ``reason`` explains why approval was sought;
    ``risk_level`` is the assessed :class:`ApprovalRiskLevel`; ``requested_action``
    names the action under review (e.g. ``"send_email"``); ``created_at_sequence``
    is the deterministic ordinal at which it was raised; and ``request_metadata``
    carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    request_id: _NonEmptyStr
    workflow_id: _NonEmptyStr
    step_id: str = ""
    reason: str = ""
    risk_level: ApprovalRiskLevel = ApprovalRiskLevel.MEDIUM
    requested_action: str = ""
    created_at_sequence: int = Field(default=0, ge=0)
    request_metadata: Dict[str, Any] = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    """Immutable outcome of an approval request (no execution, no persistence).

    ``frozen=True`` makes instances immutable. ``request_id``/``workflow_id`` link
    the decision to its request and job; ``decision`` is one of the
    :class:`ApprovalDecisionStatus` labels; ``approver_id`` names who decided
    (``"auto"`` for a policy auto-decision, ``None`` while ``PENDING``); ``reason``
    is a plain-text rationale; ``decided_at_sequence`` is the deterministic ordinal
    (never a clock time); and ``decision_metadata`` carries plain descriptors.
    Producing this DTO runs nothing and persists no workflow.
    """

    model_config = ConfigDict(frozen=True)

    request_id: _NonEmptyStr
    workflow_id: _NonEmptyStr
    decision: ApprovalDecisionStatus
    approver_id: Optional[str] = None
    reason: str = ""
    decided_at_sequence: int = Field(default=0, ge=0)
    decision_metadata: Dict[str, Any] = Field(default_factory=dict)


class ApprovalQueue(BaseModel):
    """Immutable snapshot of the pending-approval queue (deterministic order).

    ``frozen=True`` makes instances immutable. ``queue_id`` names the queue;
    ``pending_requests`` are the queued :class:`ApprovalRequest` records in
    enqueue order; ``total`` and ``pending_count`` are the tallies; and
    ``queue_metadata`` carries plain descriptors. This is a read-only capture — the
    mutable queue operations live in the queue manager, which returns one of
    these. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    queue_id: str = "approval-queue"
    pending_requests: List[ApprovalRequest] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    pending_count: int = Field(default=0, ge=0)
    queue_metadata: Dict[str, Any] = Field(default_factory=dict)


class ApprovalHistoryEntry(BaseModel):
    """Immutable pairing of a request with one decision recorded against it.

    ``frozen=True`` makes instances immutable. ``request`` is the raised
    :class:`ApprovalRequest`; ``decision`` is the :class:`ApprovalDecision`
    recorded for it (a request may appear more than once as it moves from
    ``PENDING`` to a terminal decision). Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    request: ApprovalRequest
    decision: ApprovalDecision


class ApprovalHistory(BaseModel):
    """Immutable audit history of approval activity (no execution, no persistence).

    ``frozen=True`` makes instances immutable. ``entries`` are the recorded
    :class:`ApprovalHistoryEntry` pairs in decision order; ``total`` is their
    count; and ``history_metadata`` carries plain descriptors. The engine returns a
    fresh snapshot per query. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    entries: List[ApprovalHistoryEntry] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    history_metadata: Dict[str, Any] = Field(default_factory=dict)


class ApprovalPolicyResult(BaseModel):
    """Immutable result of evaluating an :class:`ApprovalRequest` against a policy.

    ``frozen=True`` makes instances immutable. ``policy`` names the deciding policy;
    ``requires_approval`` is whether a human must decide; ``risk_level`` echoes the
    assessed :class:`ApprovalRiskLevel`; ``reason`` is a plain-text rationale;
    ``auto_decision`` is the status the policy would auto-apply when no human is
    needed (``APPROVED`` for an auto-approval, ``None`` when approval is required);
    and ``result_metadata`` carries plain descriptors. Producing this DTO runs
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    policy: _NonEmptyStr
    requires_approval: bool
    risk_level: ApprovalRiskLevel
    reason: str = ""
    auto_decision: Optional[ApprovalDecisionStatus] = None
    result_metadata: Dict[str, Any] = Field(default_factory=dict)
