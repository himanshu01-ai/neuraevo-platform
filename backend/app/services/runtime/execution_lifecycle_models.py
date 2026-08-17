"""Execution lifecycle models (Sprint 14.9 — immutable lifecycle DTOs).

Provider-independent, immutable snapshot of *the runtime execution lifecycle*
aggregated from an event log: an overall lifecycle status, the preserved events,
the current stage, and whether the lifecycle has terminated. This REPRESENTS the
lifecycle only; the snapshot executes, dispatches, and changes nothing — it is
derived from an event log.

Carries only plain data (ids, labels, a bool, nested plain event records) — no
SDK, Runtime, Tool, capability, or provider type crosses this boundary. Strictly
additive to Sprints 14.1–14.8, whose modules are left untouched. It knows nothing
about any concrete capability.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.execution_event_models import ExecutionEvent


class LifecycleStatus(str, Enum):
    """The allowed, deterministic runtime lifecycle statuses.

    ``INITIALIZED`` — the runtime is initialised. ``RUNNING`` — it is active.
    ``COMPLETED``/``FAILED``/``CANCELLED`` are the terminal outcomes. Kept as a
    ``str`` enum so each serialises to its label.
    """

    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RuntimeExecutionLifecycle(BaseModel):
    """Immutable runtime lifecycle snapshot for one execution (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime session; ``lifecycle_status`` is one of the
    :class:`LifecycleStatus` labels; ``lifecycle_events`` are the events preserved
    exactly as received (order intact); ``current_stage`` is the latest event
    type; ``is_terminal`` marks a terminal lifecycle; and ``lifecycle_metadata``
    carries deterministic state descriptors. This is a snapshot only; producing it
    executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    lifecycle_status: str
    lifecycle_events: List[ExecutionEvent] = Field(default_factory=list)
    current_stage: str
    is_terminal: bool
    lifecycle_metadata: Dict[str, Any] = Field(default_factory=dict)
