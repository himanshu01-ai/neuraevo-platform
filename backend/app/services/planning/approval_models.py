"""Approval models (Sprint 13.14 — immutable approval-plan DTOs).

Provider-independent, immutable *governance of human approval* for an execution:
a chosen approval strategy, the deterministic checkpoints at which a human must
sign off, which approvals are still pending, which nodes are already cleared or
held pending approval, and a plain-language reason. This GOVERNS approval only;
it never requests approval, resumes, retries, executes, resolves, or acquires
anything — no execution layer exists.

Carries only plain data (ids, a label, bools, plain string lists, nested plain
checkpoint records) — no SDK, Runtime, Tool, or Planner-framework type crosses
this boundary. Strictly additive to Sprints 13.1–13.13, whose modules are left
untouched.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class ApprovalStrategy(str, Enum):
    """The allowed, deterministic approval strategies.

    ``NO_APPROVAL`` means execution may proceed without sign-off;
    ``BEFORE_EXECUTION`` gates the work until a human approves it starting;
    ``BEFORE_RECOVERY`` gates a recovery until it is approved; ``MANUAL_REVIEW``
    requires a human to review before anything continues. Kept as a ``str`` enum
    so each serialises to its label.
    """

    NO_APPROVAL = "NO_APPROVAL"
    BEFORE_EXECUTION = "BEFORE_EXECUTION"
    BEFORE_RECOVERY = "BEFORE_RECOVERY"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ApprovalCheckpoint(BaseModel):
    """A single, immutable approval checkpoint (no execution).

    ``checkpoint_id`` is a deterministic identifier; ``execution_unit_id`` links
    to the execution unit the checkpoint gates; ``reason`` explains the gate in
    plain language; ``required`` marks whether a human must sign off here; and
    ``metadata`` carries provider/telemetry data. Frozen; this is structure only.
    """

    model_config = ConfigDict(frozen=True)

    checkpoint_id: str
    execution_unit_id: str
    reason: str
    required: bool
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ApprovalPlan(BaseModel):
    """Immutable plan governing human approval of an execution (no execution).

    ``frozen=True`` makes instances immutable. ``approval_id`` is a deterministic
    identifier; ``execution_id`` links to the execution; ``approval_strategy`` is
    one of the :class:`ApprovalStrategy` labels; ``approval_checkpoints`` are the
    :class:`ApprovalCheckpoint` gates; ``pending_approvals`` are the checkpoint
    ids still awaiting sign-off; ``approved_nodes`` are the node ids cleared to
    proceed; ``blocked_nodes`` are the node ids held pending approval;
    ``requires_approval`` is true for every strategy except ``NO_APPROVAL``;
    ``approval_reason`` is a plain-language justification; and ``metadata`` carries
    provider/telemetry data. The value types are intentionally plain — permissive
    lists of ids and nested checkpoints — so the :class:`PlanValidator` is the
    single place the domain rules (valid strategy, pending referencing known
    checkpoints, approved/blocked disjoint, approval-flag consistency) are
    enforced. Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    approval_id: str
    execution_id: str
    approval_strategy: str
    approval_checkpoints: List[ApprovalCheckpoint] = Field(default_factory=list)
    pending_approvals: List[str] = Field(default_factory=list)
    approved_nodes: List[str] = Field(default_factory=list)
    blocked_nodes: List[str] = Field(default_factory=list)
    requires_approval: bool
    approval_reason: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
