"""Execution controller models (Sprint 14.7 — immutable control-state DTOs).

Provider-independent, immutable statement of *what control the runtime currently
permits*: an overall control status plus the boolean control actions (pause,
resume, cancel, restart) that are available in that status. This REPRESENTS
control only; the state object executes, dispatches, and changes nothing — it is
derived from an execution-progress snapshot.

Carries only plain data (ids, a label, bools) — no SDK, Runtime, Tool,
capability, or provider type crosses this boundary. Strictly additive to Sprints
14.1–14.6, whose modules are left untouched. It knows nothing about any concrete
capability.
"""

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class ControlStatus(str, Enum):
    """The allowed, deterministic runtime control statuses.

    ``RUNNING`` — work is progressing and may be paused or cancelled. ``PAUSED`` —
    held, and may be resumed or cancelled. ``COMPLETED``/``FAILED``/``CANCELLED``
    — terminal, and may only be restarted. ``IDLE`` — nothing has started, so no
    action applies. Kept as a ``str`` enum so each serialises to its label.
    """

    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    IDLE = "IDLE"


class ExecutionControlState(BaseModel):
    """Immutable control state for one runtime session (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime session; ``control_status`` is one of the
    :class:`ControlStatus` labels; ``can_pause``/``can_resume``/``can_cancel``/
    ``can_restart`` are the deterministic control actions available in that
    status; and ``control_metadata`` carries deterministic state descriptors. This
    is a control snapshot only — it changes no execution progress and runs
    nothing. Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    control_status: str
    can_pause: bool
    can_resume: bool
    can_cancel: bool
    can_restart: bool
    control_metadata: Dict[str, Any] = Field(default_factory=dict)
