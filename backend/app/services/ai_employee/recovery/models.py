"""Recovery engine models (Sprint 16.8 — immutable recovery DTOs + enums).

Provider-independent, immutable DTOs and enums for the production-grade Recovery
engine: the failure classification, the recovery request, the policy-evaluation
result, the recovery result, and the audit history. Recovery decides *how* a failed
workflow recovers — it executes nothing itself.

All retry timing is a deterministic integer *tick* supplied by the caller — there
is no wall-clock, timer, thread, or async loop anywhere. These carry only plain
data plus the frozen Sprint 16.2 :class:`WorkflowInstance` being recovered — never a
provider/SDK object, and never a live policy/strategy/classifier/coordinator object
crosses the boundary. Strictly additive to Sprints 1.x–16.7, whose modules are left
untouched.
"""

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.ai_employee.platform_models import WorkflowInstance

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class FailureType(str, Enum):
    """The allowed, deterministic failure classifications.

    ``TRANSIENT`` — a temporary fault (retry may succeed). ``PERMANENT`` — a durable
    fault (retry will not help). ``USER_ACTION`` — needs a human/user step.
    ``SYSTEM`` — an internal system fault. ``UNKNOWN`` — unclassified. The mapping
    from a failure reason to a type lives in the *configurable* classifier, not
    here. Kept as a ``str`` enum so each serialises to its label.
    """

    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    USER_ACTION = "USER_ACTION"
    SYSTEM = "SYSTEM"
    UNKNOWN = "UNKNOWN"


class RetryStrategyType(str, Enum):
    """The allowed, deterministic retry-timing strategies.

    ``IMMEDIATE`` — retry at the current tick. ``DELAYED`` — retry after a fixed
    offset. ``FIXED_INTERVAL`` — retry after the same offset each attempt.
    ``EXPONENTIAL_BACKOFF`` — retry after an offset that doubles per attempt. Kept as
    a ``str`` enum so each serialises to its label.
    """

    IMMEDIATE = "IMMEDIATE"
    DELAYED = "DELAYED"
    EXPONENTIAL_BACKOFF = "EXPONENTIAL_BACKOFF"
    FIXED_INTERVAL = "FIXED_INTERVAL"


class FailureInfo(BaseModel):
    """Immutable classification of one workflow failure (no execution).

    ``frozen=True`` makes instances immutable. ``workflow_id`` links the failure to
    its workflow; ``failure_type`` is the classified :class:`FailureType`; ``reason``
    is the plain-text failure reason; ``attempt`` is the failed attempt number; and
    ``metadata`` carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    workflow_id: str = ""
    failure_type: FailureType = FailureType.UNKNOWN
    reason: str = ""
    attempt: int = Field(default=0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecoveryRequest(BaseModel):
    """Immutable request to recover a failed workflow (no execution).

    ``frozen=True`` makes instances immutable. ``request_id`` names the request;
    ``workflow_id`` links it to the workflow; ``instance`` is the frozen Sprint 16.2
    :class:`WorkflowInstance` being recovered; ``failure_reason`` is the plain-text
    reason (the classifier maps it to a :class:`FailureType`); ``attempt`` is the
    failed attempt number; and ``request_metadata`` carries plain descriptors.
    Producing this DTO recovers nothing.
    """

    model_config = ConfigDict(frozen=True)

    request_id: _NonEmptyStr
    workflow_id: _NonEmptyStr
    instance: WorkflowInstance
    failure_reason: str = ""
    attempt: int = Field(default=0, ge=0)
    request_metadata: Dict[str, Any] = Field(default_factory=dict)


class RecoveryPolicyResult(BaseModel):
    """Immutable result of evaluating a failure against a recovery policy.

    ``frozen=True`` makes instances immutable. ``policy`` names the deciding policy;
    ``should_retry`` is whether to retry; ``requires_manual`` is whether a human must
    step in; ``max_attempts`` is the policy's retry bound (``None`` if unbounded or
    not applicable); ``failure_type`` echoes the classified :class:`FailureType`;
    ``reason`` is a plain-text rationale; and ``result_metadata`` carries plain
    descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    policy: _NonEmptyStr
    should_retry: bool
    requires_manual: bool = False
    max_attempts: Optional[int] = None
    failure_type: FailureType = FailureType.UNKNOWN
    reason: str = ""
    result_metadata: Dict[str, Any] = Field(default_factory=dict)


class RecoveryResult(BaseModel):
    """Immutable outcome of a recovery operation (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``request_id``/``workflow_id`` link
    the result to its request and workflow; ``action`` names the action taken
    (``"retry"``, ``"abort"``, ``"manual"``); ``success`` is whether the operation
    completed; ``recovered`` is whether a retry ended in a completed workflow;
    ``requires_manual`` flags a manual recovery; ``next_retry_tick`` is the strategy's
    computed retry tick (``None`` when not retrying); ``failure_type`` is the
    classified :class:`FailureType`; ``policy`` names the deciding policy;
    ``final_status`` is the workflow's terminal status after execution (``None`` for
    manual); and ``result_metadata`` carries plain descriptors. Producing this DTO
    runs nothing further.
    """

    model_config = ConfigDict(frozen=True)

    request_id: str = ""
    workflow_id: str = ""
    action: _NonEmptyStr
    success: bool
    recovered: bool = False
    requires_manual: bool = False
    next_retry_tick: Optional[int] = None
    failure_type: FailureType = FailureType.UNKNOWN
    policy: str = ""
    final_status: Optional[str] = None
    result_metadata: Dict[str, Any] = Field(default_factory=dict)


class RecoveryHistoryEntry(BaseModel):
    """Immutable pairing of a recovery request with its result (audit record)."""

    model_config = ConfigDict(frozen=True)

    request: RecoveryRequest
    result: RecoveryResult


class RecoveryHistory(BaseModel):
    """Immutable audit history of recovery attempts (deterministic order).

    ``frozen=True`` makes instances immutable. ``entries`` are the recorded
    :class:`RecoveryHistoryEntry` pairs in attempt order; ``total`` is their count;
    and ``history_metadata`` carries plain descriptors. Producing this DTO runs
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    entries: List[RecoveryHistoryEntry] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    history_metadata: Dict[str, Any] = Field(default_factory=dict)
