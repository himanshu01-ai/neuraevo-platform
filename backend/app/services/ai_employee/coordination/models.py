"""Agent Coordination Platform models (Sprint 16.9 — immutable coordination DTOs).

Provider-independent, immutable DTOs, the :class:`AgentStatus` enum, and the
deterministic errors for the AI Employee Agent Coordination Platform: the
registered agent profile, the task to coordinate, the outcome of a policy
evaluation, the result of a delegation, and the immutable snapshot of collaboration
state. The platform *coordinates* multiple AI Employees — deciding *which* agent
handles *which* work — and delegates the actual running to the frozen Sprint 16.1
:class:`AIEmployee`; it executes no workflow and no capability itself.

There is no networking, RPC, message broker, thread, or async loop anywhere. These
carry only plain data plus the frozen Sprint 16.1 :class:`EmployeeProfile` (the
delegation target), the frozen Sprint 15.15 :class:`WorkflowStep` (the executable
work an :class:`AIEmployee` runs), and the frozen Sprint 16.1
:class:`EmployeeExecutionResult` (the delegated outcome) — never a provider/SDK
object, and never a live registry/resolver/policy/delegator object crosses the
boundary. Strictly additive to Sprints 1.x–16.8, whose modules are left untouched.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.ai_employee.models import (
    EmployeeExecutionResult,
    EmployeeProfile,
    TaskPriority,
)
from app.services.runtime.workflow_models import WorkflowStep

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


# =====================================================================
# Deterministic errors
# =====================================================================
class CoordinationError(Exception):
    """Base class for the Agent Coordination Platform's deterministic errors."""


class AgentNotFoundError(CoordinationError):
    """Raised when an operation targets an agent that is not registered."""


class TaskNotFoundError(CoordinationError):
    """Raised when an operation targets a task that the platform is not tracking."""


# =====================================================================
# Enums
# =====================================================================
class AgentStatus(str, Enum):
    """The allowed, deterministic availability states of a registered agent.

    ``AVAILABLE`` — free to take on delegated work. ``BUSY`` — currently occupied
    and not eligible for new work. ``OFFLINE`` — unregistered from active
    coordination. The resolver treats only ``AVAILABLE`` agents as candidates when
    availability is required. Kept as a ``str`` enum so each serialises to its label.
    """

    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


# =====================================================================
# DTOs
# =====================================================================
class AgentProfile(BaseModel):
    """Immutable profile of one AI Employee registered for coordination (no execution).

    ``frozen=True`` makes instances immutable. ``agent_id`` uniquely names the agent
    within the platform; ``profile`` is the frozen Sprint 16.1
    :class:`EmployeeProfile` the delegator hands to the :class:`AIEmployee` when the
    agent is assigned work; ``role`` is the coordination-facing role the resolver
    matches on; ``capabilities`` is the coordination-facing capability set the
    resolver matches on; ``priority`` ranks the agent when several are suitable
    (higher wins); ``status`` is the :class:`AgentStatus` availability; and
    ``agent_metadata`` carries plain descriptors. Building this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    agent_id: _NonEmptyStr
    profile: EmployeeProfile
    role: str = ""
    capabilities: List[str] = Field(default_factory=list)
    priority: int = Field(default=0, ge=0)
    status: AgentStatus = AgentStatus.AVAILABLE
    agent_metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentTask(BaseModel):
    """Immutable description of work to coordinate across agents (no execution).

    ``frozen=True`` makes instances immutable. ``task_id`` uniquely names the task;
    ``description`` is the required, non-empty user task the assigned employee's
    Planning Engine reasons about; ``required_role`` is an optional role the resolver
    must match; ``required_capabilities`` are capability names the resolver must
    match; ``priority`` is a :class:`TaskPriority` label (defaults to ``NORMAL``);
    ``workflow_steps`` are the frozen Sprint 15.15 :class:`WorkflowStep`\\ s the
    :class:`AIEmployee` executes (the executable work is supplied by the delegating
    layer, never invented here); ``initial_inputs`` seed that execution;
    ``constraints`` are plain-text constraints carried to the delegation;
    ``subtasks`` are child :class:`AgentTask`\\ s for subtask delegation; and
    ``task_metadata`` carries plain descriptors. This is an input only —
    constructing it coordinates, delegates, and executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    task_id: _NonEmptyStr
    description: _NonEmptyStr
    required_role: str = ""
    required_capabilities: List[str] = Field(default_factory=list)
    priority: TaskPriority = TaskPriority.NORMAL
    workflow_steps: List[WorkflowStep] = Field(default_factory=list)
    initial_inputs: Dict[str, Any] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)
    subtasks: List["AgentTask"] = Field(default_factory=list)
    task_metadata: Dict[str, Any] = Field(default_factory=dict)


class CoordinationPolicyResult(BaseModel):
    """Immutable outcome of evaluating a task against a coordination policy.

    ``frozen=True`` makes instances immutable. ``policy`` names the deciding policy;
    ``selected_agent_ids`` are the agents the policy chose (empty when none is
    suitable); ``collaborative`` is whether the decision fans work out to more than
    one agent; ``reason`` is a plain-text rationale; and ``result_metadata`` carries
    plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    policy: _NonEmptyStr
    selected_agent_ids: List[str] = Field(default_factory=list)
    collaborative: bool = False
    reason: str = ""
    result_metadata: Dict[str, Any] = Field(default_factory=dict)


class DelegationResult(BaseModel):
    """Immutable outcome of delegating a task to an agent (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``task_id`` links the result to its
    task; ``agent_id`` is the assigned agent (``None`` when unassigned, or when the
    result aggregates subtasks); ``assigned`` is whether an agent took the work;
    ``success`` is whether the delegated execution completed; ``status`` is the
    coordination outcome label (``"completed"``, ``"failed"``, ``"unassigned"``, or
    ``"cancelled"``); ``policy`` names the deciding policy; ``employee_result`` is the
    frozen Sprint 16.1 :class:`EmployeeExecutionResult` the :class:`AIEmployee`
    produced (``None`` when nothing was executed); ``subtask_results`` are the child
    :class:`DelegationResult`\\ s for a subtask delegation; and ``result_metadata``
    carries plain descriptors. Every embedded value is itself a frozen DTO, so
    nothing here executes or mutates anything.
    """

    model_config = ConfigDict(frozen=True)

    task_id: str = ""
    agent_id: Optional[str] = None
    assigned: bool = False
    success: bool = False
    status: _NonEmptyStr
    policy: str = ""
    employee_result: Optional[EmployeeExecutionResult] = None
    subtask_results: List["DelegationResult"] = Field(default_factory=list)
    result_metadata: Dict[str, Any] = Field(default_factory=dict)


class CoordinationContext(BaseModel):
    """Immutable snapshot of collaboration state (no execution).

    ``frozen=True`` makes instances immutable. ``context_id`` names the collaboration;
    ``agent_ids`` are the agents participating in it (registration order);
    ``task_ids`` are the delegated tasks (delegation order); ``ownership`` maps each
    delegated ``task_id`` to the ``agent_id`` that owns it; and ``context_metadata``
    carries plain descriptors. This is a read-only capture produced by the live
    :class:`~app.services.ai_employee.coordination.collaboration.CollaborationContext`
    — producing it runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    context_id: str = ""
    agent_ids: List[str] = Field(default_factory=list)
    task_ids: List[str] = Field(default_factory=list)
    ownership: Dict[str, str] = Field(default_factory=dict)
    context_metadata: Dict[str, Any] = Field(default_factory=dict)


# Resolve the self-referential forward references (``subtasks`` / ``subtask_results``).
AgentTask.model_rebuild()
DelegationResult.model_rebuild()
