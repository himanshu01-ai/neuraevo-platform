"""Execution event models (Sprint 14.8 — immutable event-log DTOs).

Provider-independent, immutable record of *the runtime events for one control
state*: an event-log status, the ordered events, and their count. This RECORDS
events only; the log object executes, dispatches, and changes nothing — it is
derived from a control-state snapshot.

Carries only plain data (ids, labels, an int, nested plain event records) — no
SDK, Runtime, Tool, capability, or provider type crosses this boundary. Strictly
additive to Sprints 14.1–14.7, whose modules are left untouched. It knows nothing
about any concrete capability.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class EventStatus(str, Enum):
    """The allowed, deterministic event-log statuses.

    ``INITIALIZED`` — the runtime is initialised (not yet active). ``ACTIVE`` —
    the runtime is active. ``COMPLETED``/``FAILED``/``CANCELLED`` are the terminal
    outcomes. Kept as a ``str`` enum so each serialises to its label.
    """

    INITIALIZED = "INITIALIZED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionEvent(BaseModel):
    """A single, immutable runtime execution event (no execution).

    ``event_id`` is a deterministic identifier derived from the runtime id,
    execution id, and sequence; ``event_type`` names the runtime state the event
    represents; ``execution_id`` and ``runtime_id`` link back to the runtime
    session; and ``event_sequence`` is its 1-based position in the log. Frozen;
    this is a record only — nothing is executed.
    """

    model_config = ConfigDict(frozen=True)

    event_id: str
    event_type: str
    execution_id: str
    runtime_id: str
    event_sequence: int


class ExecutionEventLog(BaseModel):
    """Immutable log of runtime events for one control state (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime session; ``event_status`` is one of the
    :class:`EventStatus` labels; ``events`` are the ordered :class:`ExecutionEvent`
    records (deterministic ordering by sequence); ``event_count`` is
    ``len(events)``; and ``event_metadata`` carries deterministic state
    descriptors. This is an event history only; producing it executes nothing.
    An empty ``events`` list (with ``event_count`` 0) is a valid empty history.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    event_status: str
    events: List[ExecutionEvent] = Field(default_factory=list)
    event_count: int = 0
    event_metadata: Dict[str, Any] = Field(default_factory=dict)
