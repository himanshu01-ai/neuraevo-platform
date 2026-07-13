"""AI Employee Service Layer models (Sprint 16.10 — immutable service DTOs).

Provider-independent, immutable DTOs, the service enums, the deterministic
service exceptions, and the task-lifecycle transition table for the AI Employee
Service Layer — the single, stable public entry point applications use to submit
and control AI Employee tasks. The Service Layer *coordinates external requests*
and always delegates the running to the frozen Sprint 16.1 :class:`AIEmployee`; it
executes no workflow and no capability itself.

There is no HTTP, REST, GraphQL, gRPC, WebSocket, auth, LLM provider, or database
anywhere. These carry only plain data plus the frozen Sprint 16.1
:class:`EmployeeProfile` (the delegation target) and the frozen Sprint 15.15
:class:`WorkflowStep` (the executable work an :class:`AIEmployee` runs) — never a
provider/SDK object, and never a raw internal exception crosses the service
boundary (the :class:`~app.services.ai_employee.service.error_mapper.ErrorMapper`
converts every exception into a stable :class:`ServiceError`). Strictly additive to
Sprints 1.x–16.9, whose modules are left untouched.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.ai_employee.models import EmployeeProfile, TaskPriority
from app.services.runtime.workflow_models import WorkflowStep

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


# =====================================================================
# Enums
# =====================================================================
class TaskState(str, Enum):
    """The allowed, deterministic lifecycle states of a service task.

    ``RUNNING`` — accepted and in flight. ``PAUSED`` — temporarily held.
    ``COMPLETED`` — the delegated run finished successfully. ``FAILED`` — the
    delegated run finished unsuccessfully. ``CANCELLED`` — withdrawn by the caller.
    Because delegation to the :class:`AIEmployee` is synchronous and deterministic,
    a freshly submitted task lands terminal (``COMPLETED``/``FAILED``); the control
    operations then transition it per :func:`next_task_state`. Kept as a ``str`` enum
    so each serialises to its label.
    """

    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskAction(str, Enum):
    """The allowed control actions a caller can request on a task."""

    PAUSE = "PAUSE"
    RESUME = "RESUME"
    CANCEL = "CANCEL"


class SessionStatus(str, Enum):
    """The allowed, deterministic statuses of a service session."""

    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class HealthState(str, Enum):
    """The allowed, deterministic health states of the platform or a subsystem.

    ``HEALTHY`` — every reported subsystem is up. ``DEGRADED`` — some are up and some
    are not. ``UNHEALTHY`` — none are up. Kept as a ``str`` enum so each serialises to
    its label.
    """

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class ServiceErrorCode(str, Enum):
    """The allowed, deterministic service error codes crossing the boundary.

    Stable codes let an application branch on the failure without ever seeing a raw
    internal exception. Kept as a ``str`` enum so each serialises to its label.
    """

    VALIDATION_ERROR = "VALIDATION_ERROR"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    TASK_NOT_PAUSABLE = "TASK_NOT_PAUSABLE"
    TASK_NOT_RESUMABLE = "TASK_NOT_RESUMABLE"
    TASK_NOT_CANCELLABLE = "TASK_NOT_CANCELLABLE"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    DELEGATION_FAILED = "DELEGATION_FAILED"
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    SCHEDULE_NOT_FOUND = "SCHEDULE_NOT_FOUND"
    PERSISTENCE_ERROR = "PERSISTENCE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# =====================================================================
# Deterministic service exceptions (internal — mapped, never surfaced raw)
# =====================================================================
class ServiceException(Exception):
    """Base class for the Service Layer's internal, deterministic exceptions.

    These are raised inside the Service Layer and always converted to a stable
    :class:`ServiceError` by the :class:`ErrorMapper` before any result leaves the
    boundary — a raw exception never reaches the caller.
    """


class ValidationException(ServiceException):
    """Raised when an incoming request fails validation (carries the issues)."""

    def __init__(self, message: str, issues: Optional[List[str]] = None) -> None:
        super().__init__(message)
        self.issues = list(issues or [])


class TaskNotFoundException(ServiceException):
    """Raised when an operation targets a task the service is not tracking."""


class SessionNotFoundException(ServiceException):
    """Raised when an operation targets a session that does not exist."""


class InvalidTaskTransitionException(ServiceException):
    """Raised when a control action is illegal for a task's current state.

    Carries the current ``state`` and the attempted ``action`` so the
    :class:`ErrorMapper` can pick the precise not-pausable/not-resumable/
    not-cancellable code.
    """

    def __init__(self, state: "TaskState", action: "TaskAction") -> None:
        super().__init__(
            f"cannot {action.value} a task in state {state.value}"
        )
        self.state = state
        self.action = action


# =====================================================================
# Task-lifecycle transition table (deterministic, no execution)
# =====================================================================
# The allowed (state, action) -> next-state transitions. PAUSE/RESUME apply only to
# in-flight tasks; CANCEL withdraws a task from any non-cancelled state.
_TRANSITIONS: Dict[Any, "TaskState"] = {
    (TaskState.RUNNING, TaskAction.PAUSE): TaskState.PAUSED,
    (TaskState.PAUSED, TaskAction.RESUME): TaskState.RUNNING,
    (TaskState.RUNNING, TaskAction.CANCEL): TaskState.CANCELLED,
    (TaskState.PAUSED, TaskAction.CANCEL): TaskState.CANCELLED,
    (TaskState.COMPLETED, TaskAction.CANCEL): TaskState.CANCELLED,
    (TaskState.FAILED, TaskAction.CANCEL): TaskState.CANCELLED,
}


def next_task_state(state: TaskState, action: TaskAction) -> TaskState:
    """Return the next :class:`TaskState` for ``action`` on ``state`` (deterministic).

    Raises :class:`InvalidTaskTransitionException` when the transition is not allowed
    (e.g. pausing a terminal task, resuming a running task, cancelling an
    already-cancelled task). Pure — it transitions nothing itself.
    """
    try:
        return _TRANSITIONS[(state, action)]
    except KeyError:
        raise InvalidTaskTransitionException(state=state, action=action)


# =====================================================================
# DTOs
# =====================================================================
class ServiceError(BaseModel):
    """Immutable, provider-independent description of a service failure.

    ``frozen=True`` makes instances immutable. ``code`` is a stable
    :class:`ServiceErrorCode` an application can branch on; ``message`` is a
    deterministic human-readable description; ``retryable`` hints whether retrying may
    help; and ``error_metadata`` carries plain descriptors (e.g. validation issues).
    No raw exception detail or provider/SDK object crosses this boundary.
    """

    model_config = ConfigDict(frozen=True)

    code: ServiceErrorCode
    message: str = ""
    retryable: bool = False
    error_metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskSubmissionRequest(BaseModel):
    """Immutable request to submit a task through the Service Layer (no execution).

    ``frozen=True`` makes instances immutable. ``request_id`` names the submission;
    ``employee`` is the frozen Sprint 16.1 :class:`EmployeeProfile` the service hands
    to the :class:`AIEmployee`; ``task_id`` is the caller's business task id and
    ``task`` the required, non-empty task the employee's Planning Engine reasons
    about; ``priority`` is a :class:`TaskPriority` label; ``constraints`` are
    plain-text constraints carried to the delegation; ``workflow_steps`` are the
    frozen Sprint 15.15 :class:`WorkflowStep`\\ s the :class:`AIEmployee` executes
    (supplied by the caller, never invented); ``initial_inputs`` seed that execution;
    ``idempotency_key`` (when set) deduplicates retries; and ``request_metadata``
    carries plain descriptors. This is an input only — constructing it submits,
    delegates, and executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    request_id: _NonEmptyStr
    employee: EmployeeProfile
    task_id: _NonEmptyStr
    task: _NonEmptyStr
    priority: TaskPriority = TaskPriority.NORMAL
    constraints: List[str] = Field(default_factory=list)
    workflow_steps: List[WorkflowStep] = Field(default_factory=list)
    initial_inputs: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None
    request_metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskSubmissionResponse(BaseModel):
    """Immutable, stable response to a task submission (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``request_id`` echoes the submission;
    ``task_id`` is the service-assigned task id; ``accepted`` is whether the task was
    accepted; ``state`` is the resulting :class:`TaskState` (``None`` when rejected);
    ``session_id`` names the created session; ``idempotent`` flags a response replayed
    from a prior identical submission; ``error`` is the :class:`ServiceError` when the
    submission was rejected; and ``response_metadata`` carries plain descriptors.
    Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    request_id: str = ""
    task_id: str = ""
    accepted: bool = False
    state: Optional[TaskState] = None
    session_id: Optional[str] = None
    idempotent: bool = False
    error: Optional[ServiceError] = None
    response_metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskStatusResponse(BaseModel):
    """Immutable, stable status of a task (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``task_id`` names the task; ``state``
    is its current :class:`TaskState` (``None`` when the task is unknown); ``success``
    is whether it completed successfully; ``session_id`` names its session;
    ``detail`` is a plain-text label; ``error`` is a :class:`ServiceError` for a
    not-found or illegal-operation read; ``result_summary`` is a provider-independent
    summary of the delegated outcome (e.g. workflow status, planned step count); and
    ``response_metadata`` carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    task_id: str = ""
    state: Optional[TaskState] = None
    success: bool = False
    session_id: Optional[str] = None
    detail: str = ""
    error: Optional[ServiceError] = None
    result_summary: Dict[str, Any] = Field(default_factory=dict)
    response_metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionInfo(BaseModel):
    """Immutable snapshot of one service session (no execution).

    ``frozen=True`` makes instances immutable. ``session_id`` names the session;
    ``employee_id``/``task_id`` link it to its employee and task; ``status`` is a
    :class:`SessionStatus`; ``active`` mirrors whether it is ``ACTIVE``;
    ``created_at_sequence`` is a deterministic ordinal (an integer, never a clock
    time) and ``closed_at_sequence`` its terminal counterpart (``None`` until closed);
    and ``session_metadata`` carries plain descriptors. Producing this DTO runs
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    session_id: _NonEmptyStr
    employee_id: str = ""
    task_id: str = ""
    status: SessionStatus = SessionStatus.ACTIVE
    active: bool = True
    created_at_sequence: int = Field(default=0, ge=0)
    closed_at_sequence: Optional[int] = Field(default=None, ge=0)
    session_metadata: Dict[str, Any] = Field(default_factory=dict)


class HealthStatus(BaseModel):
    """Immutable, provider-independent health report of the platform.

    ``frozen=True`` makes instances immutable. ``state`` is the overall
    :class:`HealthState`; ``ready`` is whether the platform is ready to accept work;
    ``components`` maps each reported subsystem name to its :class:`HealthState`
    label; ``detail`` is a plain-text summary; and ``health_metadata`` carries plain
    descriptors. Producing this DTO runs nothing and exposes no provider object.
    """

    model_config = ConfigDict(frozen=True)

    state: HealthState
    ready: bool = False
    components: Dict[str, str] = Field(default_factory=dict)
    detail: str = ""
    health_metadata: Dict[str, Any] = Field(default_factory=dict)


class IdempotencyRecord(BaseModel):
    """Immutable record deduplicating a submission by its idempotency key.

    ``frozen=True`` makes instances immutable. ``key`` is the idempotency key;
    ``request_id``/``task_id`` link it to the original submission and its assigned
    task; ``fingerprint`` is the deterministic digest of the original request (a
    matching key with a different fingerprint is a conflict); ``response`` is the
    original :class:`TaskSubmissionResponse` to replay; ``created_at_sequence`` is a
    deterministic ordinal; and ``record_metadata`` carries plain descriptors.
    Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    key: _NonEmptyStr
    request_id: str = ""
    task_id: str = ""
    fingerprint: str = ""
    response: TaskSubmissionResponse
    created_at_sequence: int = Field(default=0, ge=0)
    record_metadata: Dict[str, Any] = Field(default_factory=dict)
