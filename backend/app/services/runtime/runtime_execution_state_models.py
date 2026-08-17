"""Runtime execution state models (Sprint 14.10 — immutable runtime-state DTOs).

Provider-independent, immutable snapshot of *the current runtime execution state*
derived from a lifecycle: an overall state status, the current stage, and whether
execution is active or terminal. This REPRESENTS the current state only; the
snapshot executes, dispatches, and changes nothing — it is derived from a
lifecycle.

Carries only plain data (ids, a label, a stage string, bools) — no SDK, Runtime,
Tool, capability, or provider type crosses this boundary. Strictly additive to
Sprints 14.1–14.9, whose modules are left untouched. It knows nothing about any
concrete capability.
"""

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class RuntimeStateStatus(str, Enum):
    """The allowed, deterministic runtime state statuses.

    ``INITIALIZED`` — the runtime is initialised. ``RUNNING`` — it is active.
    ``COMPLETED``/``FAILED``/``CANCELLED`` are the terminal outcomes. Kept as a
    ``str`` enum so each serialises to its label.
    """

    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RuntimeExecutionState(BaseModel):
    """Immutable current runtime execution state (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime session; ``state_status`` is one of the
    :class:`RuntimeStateStatus` labels; ``current_stage`` is copied directly from
    the lifecycle; ``is_active`` is true only while running; ``is_terminal`` marks
    a terminal state; and ``runtime_metadata`` carries deterministic state
    descriptors. This is a snapshot only; producing it executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    state_status: str
    current_stage: str
    is_active: bool
    is_terminal: bool
    runtime_metadata: Dict[str, Any] = Field(default_factory=dict)
