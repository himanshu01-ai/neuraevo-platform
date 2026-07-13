"""Notification Engine models (Sprint 16.4 — immutable notification DTOs).

Provider-independent, immutable DTOs and enums for the production-grade
Notification Engine: the notification event, the priority, the lifecycle status,
the notification message, the queued item, the history entry, and the
policy-evaluation result. This layer *upgrades* the Sprint 16.2
NotificationManager abstraction additively — it introduces no change to any frozen
module and remains provider-independent.

These carry only plain data — never a provider/SDK object, and never a live
policy/queue/dispatcher object crosses the boundary. All timing is a deterministic
integer sequence (never a clock). It manages notification *lifecycle* only and
delivers nothing externally. Strictly additive to Sprints 1.x–16.3, whose modules
are left untouched.
"""

from enum import Enum
from typing import Annotated, Any, Dict

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class NotificationEvent(str, Enum):
    """The allowed, deterministic notification events across the platform.

    Workflow lifecycle (``WORKFLOW_STARTED``/``WORKFLOW_COMPLETED``/
    ``WORKFLOW_FAILED``/``WORKFLOW_PAUSED``/``WORKFLOW_RESUMED``/
    ``WORKFLOW_CANCELLED``), approval (``APPROVAL_REQUIRED``/``APPROVAL_APPROVED``/
    ``APPROVAL_REJECTED``), and recovery (``RECOVERY_STARTED``/
    ``RECOVERY_COMPLETED``). Kept as a ``str`` enum so each serialises to its label.
    """

    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    WORKFLOW_PAUSED = "WORKFLOW_PAUSED"
    WORKFLOW_RESUMED = "WORKFLOW_RESUMED"
    WORKFLOW_CANCELLED = "WORKFLOW_CANCELLED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_APPROVED = "APPROVAL_APPROVED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    RECOVERY_STARTED = "RECOVERY_STARTED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"


class NotificationPriority(str, Enum):
    """The allowed, deterministic notification priorities.

    ``LOW``/``NORMAL``/``HIGH``/``CRITICAL`` order how urgently a notification is
    dispatched; the mapping from event to priority lives in the *configurable*
    priority model, not here. Kept as a ``str`` enum so each serialises to its
    label.
    """

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Deterministic ordering of the priorities (low → critical) for queue ordering.
# Kept beside the enum so every consumer ranks priority identically.
PRIORITY_ORDER: Dict[NotificationPriority, int] = {
    NotificationPriority.LOW: 0,
    NotificationPriority.NORMAL: 1,
    NotificationPriority.HIGH: 2,
    NotificationPriority.CRITICAL: 3,
}


class NotificationStatus(str, Enum):
    """The allowed, deterministic lifecycle states of a :class:`NotificationMessage`.

    ``PENDING`` — created, not yet queued. ``QUEUED`` — awaiting a dispatch
    decision. ``DISPATCHED`` — handed to the dispatcher. ``DELIVERED`` — the
    dispatcher confirmed delivery (in-memory only — nothing leaves the process).
    Kept as a ``str`` enum so each serialises to its label.
    """

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    DISPATCHED = "DISPATCHED"
    DELIVERED = "DELIVERED"


class NotificationMessage(BaseModel):
    """Immutable notification record (created, queued, dispatched — never delivered externally).

    ``frozen=True`` makes instances immutable, so a lifecycle transition produces a
    new instance. ``message_id`` is the deterministic
    ``"notification-<workflow_id>-<sequence>"`` handle; ``workflow_id`` links it to
    its job; ``event`` is one of the :class:`NotificationEvent` labels; ``priority``
    is the assessed :class:`NotificationPriority`; ``status`` is one of the
    :class:`NotificationStatus` labels; ``message`` is a plain-text summary;
    ``created_at_sequence`` is the deterministic ordinal (never a clock); and
    ``message_metadata`` carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    message_id: _NonEmptyStr
    workflow_id: _NonEmptyStr
    event: NotificationEvent
    priority: NotificationPriority = NotificationPriority.NORMAL
    status: NotificationStatus = NotificationStatus.PENDING
    message: str = ""
    created_at_sequence: int = Field(default=0, ge=0)
    message_metadata: Dict[str, Any] = Field(default_factory=dict)


class NotificationQueueItem(BaseModel):
    """Immutable queued wrapper around a :class:`NotificationMessage` (priority order).

    ``frozen=True`` makes instances immutable. ``item_id`` is the deterministic
    handle; ``message`` is the queued :class:`NotificationMessage`; ``priority``
    echoes the message's priority (the ordering key); ``sequence`` is the
    deterministic enqueue ordinal used for FIFO ordering within a priority;
    ``queued_at_sequence`` records when it was enqueued; and ``item_metadata``
    carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    item_id: _NonEmptyStr
    message: NotificationMessage
    priority: NotificationPriority = NotificationPriority.NORMAL
    sequence: int = Field(default=0, ge=0)
    queued_at_sequence: int = Field(default=0, ge=0)
    item_metadata: Dict[str, Any] = Field(default_factory=dict)


class NotificationHistoryEntry(BaseModel):
    """Immutable audit record of a notification at one lifecycle point.

    ``frozen=True`` makes instances immutable. ``entry_id`` is the deterministic
    handle; ``message`` is the :class:`NotificationMessage` captured at this point;
    ``status`` is the :class:`NotificationStatus` recorded (a message may appear
    more than once as it moves QUEUED → DISPATCHED → DELIVERED);
    ``recorded_at_sequence`` is the deterministic ordinal; and ``entry_metadata``
    carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    entry_id: _NonEmptyStr
    message: NotificationMessage
    status: NotificationStatus
    recorded_at_sequence: int = Field(default=0, ge=0)
    entry_metadata: Dict[str, Any] = Field(default_factory=dict)


class NotificationPolicyResult(BaseModel):
    """Immutable result of evaluating the queue against a notification policy.

    ``frozen=True`` makes instances immutable. ``policy`` names the deciding policy;
    ``should_dispatch`` is whether queued notifications are now dispatchable;
    ``batch_size`` is how many to dispatch (0 when holding); ``reason`` is a
    plain-text rationale; and ``result_metadata`` carries plain descriptors.
    Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    policy: _NonEmptyStr
    should_dispatch: bool
    batch_size: int = Field(default=0, ge=0)
    reason: str = ""
    result_metadata: Dict[str, Any] = Field(default_factory=dict)
