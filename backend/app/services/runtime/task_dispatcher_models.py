"""Task dispatcher models (Sprint 14.2 — immutable dispatch-plan DTOs).

Provider-independent, immutable statement of *which execution units are eligible
to leave the runtime*: a dispatch status plus the unit ids grouped into ready,
blocked, and deferred sets, in the queue's exact order. This DESCRIBES dispatch
eligibility only; it never executes, dispatches, resolves, or acquires anything —
no execution runs here.

Carries only plain data (ids, a label, plain string lists) — no SDK, Runtime,
Tool, or Planner-framework type crosses this boundary. Strictly additive to
Sprint 14.1, whose modules are left untouched.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class DispatchStatus(str, Enum):
    """The allowed, deterministic dispatch statuses.

    ``READY`` — at least one unit is eligible to dispatch now. ``WAITING`` — no
    ready units, but deferred units remain. ``BLOCKED`` — no ready units, but
    blocked units remain. ``COMPLETED`` — the queue is empty (nothing left to
    dispatch). Kept as a ``str`` enum so each serialises to its label.
    """

    READY = "READY"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"


class DispatchPlan(BaseModel):
    """Immutable dispatch plan over a runtime's execution queue (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime context; ``dispatch_status`` is one of the
    :class:`DispatchStatus` labels; ``ready_execution_units``,
    ``blocked_execution_units``, and ``deferred_execution_units`` are the unit ids
    grouped by status, preserving the queue's exact ordering; and
    ``dispatch_metadata`` carries provider/telemetry data. This is a plan only —
    it enumerates eligibility and dispatches nothing. Producing this DTO executes
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    dispatch_status: str
    ready_execution_units: List[str] = Field(default_factory=list)
    blocked_execution_units: List[str] = Field(default_factory=list)
    deferred_execution_units: List[str] = Field(default_factory=list)
    dispatch_metadata: Dict[str, Any] = Field(default_factory=dict)
