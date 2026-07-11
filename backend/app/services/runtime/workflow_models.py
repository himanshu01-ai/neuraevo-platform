"""Workflow models (Sprint 15.15 — immutable multi-capability workflow DTOs).

Provider-independent, immutable DTOs and errors for Multi-Capability Workflow
Integration: the step definition, the artifact reference shared between steps, the
per-step execution reference, and the final workflow result. This sprint *coordinates*
the existing Sprint 15 capabilities (Browser, Python, File System, Email, Calendar,
GitHub) — each already a Sprint 14.3 :class:`ExecutionCapability` — into a
deterministic sequential workflow. It performs no planning and no AI autonomy: the
steps are given, and the coordinator executes them, threading outputs and artifacts
between them.

These carry only plain data across the boundary — never a provider/SDK object; each
capability already returns a plain :class:`CapabilityExecutionResult`, and a
:class:`WorkflowArtifactReference` is a plain descriptor of an artifact another
capability produced. Strictly additive to Sprints 15.1–15.14, whose modules are left
untouched. The mutable-facing but externally-immutable execution context lives in
:mod:`app.services.runtime.workflow_execution_context`.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class WorkflowError(Exception):
    """Base class for deterministic workflow errors.

    The coordinator catches these at its boundary and reports a graceful ``FAILED``
    :class:`WorkflowExecutionResult`; the exception object never escapes.
    """


class WorkflowValidationError(WorkflowError):
    """Raised when a workflow is structurally invalid (no steps, duplicate/unknown ids)."""


class CapabilityUnavailableError(WorkflowError):
    """Raised when a step names a capability the router cannot resolve."""


class WorkflowBindingError(WorkflowError):
    """Raised when an input binding references an unknown step or missing output path."""


class ArtifactMissingError(WorkflowError):
    """Raised when a step requires an artifact that no prior step produced."""


class WorkflowStatus(str, Enum):
    """The allowed, deterministic workflow-level statuses.

    ``PENDING`` — not started. ``RUNNING`` — steps in progress. ``COMPLETED`` — every
    step succeeded. ``FAILED`` — validation failed or a step reported ``FAILED`` and
    the workflow stopped. Kept as a ``str`` enum so each serialises to its label.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkflowStep(BaseModel):
    """Immutable definition of one workflow step (no execution).

    ``frozen=True`` makes instances immutable. ``step_id`` uniquely names the step;
    ``capability_name`` selects the capability the router dispatches to (e.g.
    ``"browser"``, ``"python"``, ``"filesystem"``, ``"email"``, ``"calendar"``,
    ``"github"``); ``inputs`` are the static ``capability_inputs``; ``input_bindings``
    map an input key to a reference resolved against prior results
    (``"<step_id>.<dotted.path>"``, ``"input.<key>"``, or ``"artifact:<id>[.field]"``)
    so one capability's outputs become the next one's inputs; ``required_artifacts``
    are artifact ids that must already exist (else the step fails with a clear
    ``artifact missing`` error); ``depends_on`` lists earlier steps this one needs;
    and ``step_metadata`` carries plain descriptors. Building this DTO executes
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    step_id: str
    capability_name: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    input_bindings: Dict[str, str] = Field(default_factory=dict)
    required_artifacts: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    step_metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowArtifactReference(BaseModel):
    """Immutable reference to an artifact one capability produced (no SDK object).

    ``frozen=True`` makes instances immutable. ``reference_id`` is the deterministic
    ``"<step_id>:<artifact_id>"`` handle; ``artifact_id``/``artifact_type``/``name``/
    ``path`` are the plain descriptors copied from the producing capability's already
    plain artifact output; ``source_step``/``source_capability`` record its origin;
    and ``reference_metadata`` carries plain descriptors. It never holds a provider
    object — only a plain reference other steps can pass along.
    """

    model_config = ConfigDict(frozen=True)

    reference_id: str
    artifact_id: str
    artifact_type: str = "UNKNOWN"
    name: str = ""
    source_step: str = ""
    source_capability: str = ""
    path: Optional[str] = None
    reference_metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityExecutionReference(BaseModel):
    """Immutable record of one step's execution (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``step_id``/``capability_name`` name
    the step; ``execution_status`` echoes the capability's status
    (``COMPLETED``/``FAILED``); ``outputs`` are the plain ``capability_outputs``;
    ``artifact_reference_ids`` link the artifacts the step produced; and
    ``execution_metadata`` carries plain descriptors. Producing it runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    step_id: str
    capability_name: str
    execution_status: str
    outputs: Dict[str, Any] = Field(default_factory=dict)
    artifact_reference_ids: List[str] = Field(default_factory=list)
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionResult(BaseModel):
    """Immutable result of running a workflow (no SDK object exposed).

    ``frozen=True`` makes instances immutable. ``workflow_id`` echoes the workflow;
    ``workflow_status`` is a :class:`WorkflowStatus` label; ``step_references`` are
    the per-step :class:`CapabilityExecutionReference` records in execution order;
    ``artifacts`` are all the :class:`WorkflowArtifactReference` records produced;
    ``final_outputs`` are the last completed step's plain outputs; ``failed_step_id``
    names the step that failed (``None`` on success); ``completed_step_count`` and
    ``total_step_count`` are the tallies; and ``result_metadata`` carries plain
    descriptors (including any error). Producing this DTO runs nothing further.
    """

    model_config = ConfigDict(frozen=True)

    workflow_id: str
    workflow_status: str
    step_references: List[CapabilityExecutionReference] = Field(default_factory=list)
    artifacts: List[WorkflowArtifactReference] = Field(default_factory=list)
    final_outputs: Dict[str, Any] = Field(default_factory=dict)
    failed_step_id: Optional[str] = None
    completed_step_count: int = 0
    total_step_count: int = 0
    result_metadata: Dict[str, Any] = Field(default_factory=dict)
