"""Execution runtime models (Sprint 14.1 — immutable runtime-context DTOs).

Provider-independent, immutable *runtime session state* for one execution: a
runtime status, the Sprint 13 orchestration output the session was initialized
from, the currently-selected execution unit (none at init), and the empty
variable/output/metadata working stores. This ESTABLISHES runtime state only; it
never dispatches, executes, recovers, approves, or performs any I/O — no
execution actually runs here.

Carries only plain data plus the frozen Sprint 13 :class:`ExecutionOrchestration
Result` — no SDK, network, clock, UUID, or provider type crosses this boundary.
Strictly additive to Sprints 13.1–13.15, whose modules are left untouched.
"""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from app.services.planning.planning_engine import ExecutionOrchestrationResult


class ExecutionRuntimeStatus(str, Enum):
    """The allowed, deterministic runtime-session statuses.

    ``INITIALIZED`` is the only status a freshly created context carries;
    ``READY``/``PAUSED``/``CANCELLED``/``COMPLETED`` are reserved for the later
    runtime sprints that will drive the session. Kept as a ``str`` enum so each
    serialises to its label.
    """

    INITIALIZED = "INITIALIZED"
    READY = "READY"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class ExecutionRuntimeContext(BaseModel):
    """Immutable runtime context for one execution session (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` is deterministic
    (derived from ``execution_id``); ``execution_id`` links to the orchestrated
    execution; ``runtime_status`` is one of the :class:`ExecutionRuntimeStatus`
    labels (always ``INITIALIZED`` at creation); ``orchestration`` is the
    preserved, unmodified Sprint 13 :class:`ExecutionOrchestrationResult`;
    ``current_execution_unit_id`` is the unit the runtime is positioned on
    (``None`` at init); ``execution_variables``/``execution_outputs``/
    ``execution_metadata`` are the runtime working stores (empty at init);
    ``created_at_sequence`` is a deterministic genesis sequence position (an
    integer, never a clock time); and ``metadata`` carries provider/telemetry
    data. ``arbitrary_types_allowed`` plus :class:`SkipValidation` on
    ``orchestration`` store the Sprint 13 result exactly as produced — the same
    object, never re-validated or reconstructed — so it is preserved untouched.
    Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    runtime_id: str
    execution_id: str
    runtime_status: str
    orchestration: SkipValidation[ExecutionOrchestrationResult]
    current_execution_unit_id: Optional[str] = None
    execution_variables: Dict[str, Any] = Field(default_factory=dict)
    execution_outputs: Dict[str, Any] = Field(default_factory=dict)
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at_sequence: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
