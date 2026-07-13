"""Scheduling Platform models (Sprint 16.7 — immutable schedule DTOs + errors).

Provider-independent, immutable DTOs, the type/status enums, and the deterministic
errors for the AI Employee Scheduling Platform: the schedule request, the queued
entry, its compact metadata, and the result of a scheduling operation. The
scheduler decides *when* workflows execute — it executes nothing itself.

All timing is a deterministic integer *tick* supplied by the caller — there is no
wall-clock, timer, ``time.sleep``, ``threading``, ``asyncio``, or cron anywhere.
These carry only plain data plus the frozen Sprint 16.2 :class:`WorkflowInstance`
to schedule — never a provider/SDK object, and never a live policy/planner/queue
object crosses the boundary. Strictly additive to Sprints 1.x–16.6, whose modules
are left untouched.
"""

from enum import Enum
from typing import Annotated, Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.ai_employee.platform_models import WorkflowInstance

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


# =====================================================================
# Deterministic errors
# =====================================================================
class ScheduleError(Exception):
    """Base class for the Scheduling Platform's deterministic errors."""


class ScheduleNotFoundError(ScheduleError):
    """Raised when an operation targets a schedule entry that does not exist."""


class InvalidScheduleError(ScheduleError):
    """Raised when a request is structurally invalid (e.g. AT_TIME without a tick)."""


# =====================================================================
# Enums
# =====================================================================
class ScheduleType(str, Enum):
    """The allowed, deterministic schedule types.

    ``IMMEDIATE`` — execute at the current tick. ``DELAYED`` — execute after a delay
    of ticks. ``AT_TIME`` — execute at a specific tick. ``RECURRING`` — execute
    repeatedly every interval of ticks. Kept as a ``str`` enum so each serialises to
    its label.
    """

    IMMEDIATE = "IMMEDIATE"
    DELAYED = "DELAYED"
    AT_TIME = "AT_TIME"
    RECURRING = "RECURRING"


class ScheduleStatus(str, Enum):
    """The allowed, deterministic statuses of a :class:`ScheduleEntry`.

    ``SCHEDULED`` — queued, eligible to run when due. ``RUNNING`` — being executed.
    ``PAUSED`` — held; not eligible to run. ``COMPLETED`` — executed (non-recurring).
    ``CANCELLED`` — removed by the operator. Kept as a ``str`` enum so each
    serialises to its label.
    """

    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# =====================================================================
# DTOs
# =====================================================================
class ScheduleRequest(BaseModel):
    """Immutable request to schedule a workflow (no execution).

    ``frozen=True`` makes instances immutable. ``request_id`` names the request;
    ``workflow_id`` optionally names the workflow instance (the instance is
    authoritative); ``schedule_type`` is one of the :class:`ScheduleType` labels;
    ``delay`` is the tick offset for ``DELAYED`` (and the initial offset for
    ``RECURRING``); ``at_tick`` is the target tick for ``AT_TIME``; ``interval`` is
    the recurrence period in ticks for ``RECURRING``; ``max_occurrences`` optionally
    bounds a recurring schedule; and ``request_metadata`` carries plain descriptors.
    Producing this DTO schedules nothing.
    """

    model_config = ConfigDict(frozen=True)

    request_id: _NonEmptyStr
    workflow_id: str = ""
    schedule_type: ScheduleType = ScheduleType.IMMEDIATE
    delay: int = Field(default=0, ge=0)
    at_tick: Optional[int] = Field(default=None, ge=0)
    interval: Optional[int] = Field(default=None, ge=1)
    max_occurrences: Optional[int] = Field(default=None, ge=1)
    request_metadata: Dict[str, Any] = Field(default_factory=dict)


class ScheduleMetadata(BaseModel):
    """Immutable, compact descriptor of a schedule entry (no instance payload).

    ``frozen=True`` makes instances immutable. ``schedule_id`` names the schedule;
    ``schedule_type`` is one of the :class:`ScheduleType` labels; ``created_at_tick``
    is the deterministic tick it was created at; ``interval`` is the recurrence
    period (``None`` for non-recurring); and ``metadata`` carries plain descriptors.
    Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    schedule_id: _NonEmptyStr
    schedule_type: ScheduleType = ScheduleType.IMMEDIATE
    created_at_tick: int = Field(default=0, ge=0)
    interval: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ScheduleEntry(BaseModel):
    """Immutable queued schedule for one workflow instance (no execution).

    ``frozen=True`` makes instances immutable, so a transition produces a new
    instance. ``entry_id`` names the entry; ``workflow_id`` links it to the workflow
    instance; ``instance`` is the frozen Sprint 16.2 :class:`WorkflowInstance` to
    execute; ``schedule_type`` is one of the :class:`ScheduleType` labels;
    ``status`` is one of the :class:`ScheduleStatus` labels;
    ``next_execution_tick`` is the deterministic tick it becomes due; ``interval`` is
    the recurrence period (``None`` for non-recurring); ``occurrences`` is how many
    times it has executed; ``max_occurrences`` optionally bounds recurrence;
    ``created_at_tick`` is the creation tick; ``metadata`` is the compact
    :class:`ScheduleMetadata`; and ``entry_metadata`` carries plain descriptors. The
    entry holds scheduling state only — it executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    entry_id: _NonEmptyStr
    workflow_id: _NonEmptyStr
    instance: WorkflowInstance
    schedule_type: ScheduleType
    status: ScheduleStatus = ScheduleStatus.SCHEDULED
    next_execution_tick: int = Field(default=0, ge=0)
    interval: Optional[int] = None
    occurrences: int = Field(default=0, ge=0)
    max_occurrences: Optional[int] = None
    created_at_tick: int = Field(default=0, ge=0)
    metadata: ScheduleMetadata
    entry_metadata: Dict[str, Any] = Field(default_factory=dict)


class ScheduleResult(BaseModel):
    """Immutable result of a scheduling operation (no execution).

    ``frozen=True`` makes instances immutable. ``entry_id``/``workflow_id`` link the
    result to its entry and workflow; ``operation`` names the operation (e.g.
    ``"schedule"``, ``"cancel"``, ``"reschedule"``, ``"execute"``); ``success`` is
    the outcome; ``entry`` is the resulting :class:`ScheduleEntry` (``None`` when not
    applicable); and ``result_metadata`` carries plain descriptors. Producing this
    DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    entry_id: str = ""
    workflow_id: str = ""
    operation: _NonEmptyStr
    success: bool
    entry: Optional[ScheduleEntry] = None
    result_metadata: Dict[str, Any] = Field(default_factory=dict)
