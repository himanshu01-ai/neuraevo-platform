"""AI Employee models (Sprint 16.1 — immutable AI Employee Foundation DTOs).

Provider-independent, immutable DTOs and enums for the AI Employee Foundation:
the employee profile, the employee session, the runtime-bound employee context,
the delegated task, and the final execution result. This layer *owns* employee
sessions and task delegation and *orchestrates* the existing Planning Engine and
Workflow Coordinator — it plans nothing itself and executes no capability.

These carry only plain data plus the frozen Sprint 13 :class:`ExecutionPlan` and
the frozen Sprint 15.15 :class:`WorkflowExecutionResult` — never a provider/SDK
object crosses this boundary. Runtime references are exposed as plain string
descriptors, never live collaborator objects. Strictly additive to Sprints
1.x–15.15, whose modules are left untouched. The orchestration that produces
these lives in :mod:`app.services.ai_employee.ai_employee`.
"""

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.planning.models import ExecutionPlan
from app.services.runtime.workflow_models import WorkflowExecutionResult

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class TaskPriority(str, Enum):
    """The allowed, deterministic priority levels of a :class:`TaskDelegation`.

    ``LOW``/``NORMAL``/``HIGH``/``URGENT`` describe how the delegating layer ranks
    the task; the foundation records the priority but does not itself schedule or
    reorder work on it. Kept as a ``str`` enum so each serialises to its label.
    """

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class EmployeeSessionStatus(str, Enum):
    """The allowed, deterministic statuses of an :class:`EmployeeSession`.

    ``PENDING`` — created, not started. ``RUNNING`` — a delegation is being
    coordinated. ``COMPLETED`` — the coordinated workflow completed. ``FAILED`` —
    the coordinated workflow failed (or was structurally invalid). Kept as a
    ``str`` enum so each serialises to its label.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EmployeeProfile(BaseModel):
    """Immutable profile identifying one AI Employee (no execution).

    ``frozen=True`` makes instances immutable. ``employee_id`` uniquely names the
    employee; ``name`` is its human label; ``role`` is an optional descriptive
    role; ``capabilities`` lists the capability names the employee is declared to
    use (descriptive only — the foundation never dispatches to them directly); and
    ``profile_metadata`` carries plain descriptors. Building this DTO executes
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    employee_id: _NonEmptyStr
    name: _NonEmptyStr
    role: str = ""
    capabilities: List[str] = Field(default_factory=list)
    profile_metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskDelegation(BaseModel):
    """Immutable description of work delegated to an AI Employee (no execution).

    ``frozen=True`` makes instances immutable. ``task_id`` uniquely names the
    delegation; ``task`` is the required, non-empty user task the Planning Engine
    reasons about; ``constraints`` lists plain-text constraints the delegating
    layer attached; ``priority`` is a :class:`TaskPriority` label
    (defaults to ``NORMAL``); and ``delegation_metadata`` carries plain
    descriptors. This is an input only — constructing it delegates, plans, and
    executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    task_id: _NonEmptyStr
    task: _NonEmptyStr
    constraints: List[str] = Field(default_factory=list)
    priority: TaskPriority = TaskPriority.NORMAL
    delegation_metadata: Dict[str, Any] = Field(default_factory=dict)


class EmployeeSession(BaseModel):
    """Immutable identity and lifecycle state of one employee session.

    ``frozen=True`` makes instances immutable, so a lifecycle transition produces
    a new instance rather than mutating this one. ``session_id`` deterministically
    names the session; ``employee_id``/``task_id`` link it to its employee and
    delegation; ``status`` is one of the :class:`EmployeeSessionStatus` labels;
    ``active_workflow_id`` names the workflow the session is coordinating (``None``
    until one is bound); ``started_at_sequence`` is a deterministic ordinal (an
    integer, never a clock time) and ``completed_at_sequence`` its terminal
    counterpart (``None`` until the session is terminal); and ``session_metadata``
    carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    session_id: _NonEmptyStr
    employee_id: _NonEmptyStr
    task_id: _NonEmptyStr
    status: EmployeeSessionStatus = EmployeeSessionStatus.PENDING
    active_workflow_id: Optional[str] = None
    started_at_sequence: int = Field(default=0, ge=0)
    completed_at_sequence: Optional[int] = Field(default=None, ge=0)
    session_metadata: Dict[str, Any] = Field(default_factory=dict)


class EmployeeContext(BaseModel):
    """Immutable runtime-bound context for one employee session (no execution).

    ``frozen=True`` makes instances immutable. ``employee_id`` links the context
    to its employee; ``profile`` is the bound :class:`EmployeeProfile`; ``session``
    is the bound :class:`EmployeeSession`; ``runtime_references`` maps a subsystem
    name to a plain descriptor of the wired collaborator (e.g.
    ``{"planning_engine": "PlanningEngine"}``) — plain strings only, so no live
    collaborator or SDK object ever crosses this boundary; and ``context_metadata``
    carries plain descriptors. Building this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    employee_id: _NonEmptyStr
    profile: EmployeeProfile
    session: EmployeeSession
    runtime_references: Dict[str, str] = Field(default_factory=dict)
    context_metadata: Dict[str, Any] = Field(default_factory=dict)


class EmployeeExecutionResult(BaseModel):
    """Immutable result of a coordinated delegation (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``employee_id``/``session_id``/
    ``task_id`` link the result to its employee, session, and delegation;
    ``status`` mirrors the terminal :class:`EmployeeSessionStatus`
    (``COMPLETED``/``FAILED``); ``context`` is the :class:`EmployeeContext` bound
    when the session started (its ``session`` is the bind-time ``RUNNING``
    snapshot); ``plan`` is the reasoned Sprint 13 :class:`ExecutionPlan` the
    Planning Engine produced; ``workflow_result`` is the Sprint 15.15
    :class:`WorkflowExecutionResult` the Workflow Coordinator produced;
    ``session`` is the terminal :class:`EmployeeSession` (``COMPLETED``/``FAILED``
    with its completion ordinal set); and ``result_metadata`` carries plain
    descriptors. Every embedded value is itself a frozen DTO, so nothing here
    executes or mutates anything.
    """

    model_config = ConfigDict(frozen=True)

    employee_id: _NonEmptyStr
    session_id: _NonEmptyStr
    task_id: _NonEmptyStr
    status: EmployeeSessionStatus
    context: EmployeeContext
    plan: ExecutionPlan
    workflow_result: WorkflowExecutionResult
    session: EmployeeSession
    result_metadata: Dict[str, Any] = Field(default_factory=dict)
