"""Execution queue models (Sprint 13.7 — immutable queue DTOs).

Provider-independent, immutable description of *how a workflow's steps would be
queued* for eventual execution: an ordered list of execution units (each with a
group, dependencies, and a status), plus queue-level status and ready/blocked
counts. This is ORGANISATION ONLY: it describes a queue; it never executes,
resolves, or acquires anything — no execution layer exists.

Carries only plain data (ids, labels, ints, nested plain unit records) — no SDK,
Runtime, Tool, or Planner-framework type crosses this boundary. Strictly additive
to Sprints 13.1–13.6, whose modules are left untouched.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class QueueStatus(str, Enum):
    """The allowed, deterministic queue statuses.

    ``READY`` — at least one unit can start now. ``WAITING`` — the queue is held
    pending the user. ``BLOCKED`` — nothing can start yet. These are the only
    permitted values; a status is always chosen deterministically. Kept as a
    ``str`` enum so it serialises to its label.
    """

    READY = "READY"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"


class ExecutionUnitStatus(str, Enum):
    """The allowed, deterministic per-unit statuses.

    ``READY`` — the unit has no unmet dependencies and may start. ``WAITING`` —
    held pending the user. ``BLOCKED`` — waiting on predecessors or a blocked
    workflow. Kept as a ``str`` enum so it serialises to its label.
    """

    READY = "READY"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"


class ExecutionUnit(BaseModel):
    """A single, immutable queued unit of work (no execution).

    ``unit_id`` is a deterministic identifier; ``step_number`` preserves the
    workflow's ordering; ``description`` restates the step; ``execution_group``
    preserves the workflow group; ``status`` is one of the
    :class:`ExecutionUnitStatus` labels; ``dependencies`` preserves the step's
    dependencies; and ``metadata`` carries provider/telemetry data. Frozen — a
    unit cannot be mutated. This is structure only; nothing is executed.
    """

    model_config = ConfigDict(frozen=True)

    unit_id: str
    step_number: int
    description: str
    execution_group: int
    status: str
    dependencies: List[int] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionQueue(BaseModel):
    """Immutable queue of execution units for a workflow (no execution).

    ``frozen=True`` makes instances immutable. ``queue_id`` is a deterministic
    identifier; ``workflow_id`` links back to the source workflow; ``status`` is
    one of the :class:`QueueStatus` labels; ``execution_units`` are the ordered,
    grouped units; ``total_units`` counts them; ``ready_units`` and
    ``blocked_units`` count units in those statuses; and ``metadata`` carries
    provider/telemetry data. The value types are intentionally plain — permissive
    :class:`str`/:class:`int` — so the :class:`PlanValidator` is the single place
    the domain rules (valid statuses, non-negative and consistent counts, unique
    units, positive groups) are enforced. Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    queue_id: str
    workflow_id: str
    status: str
    execution_units: List[ExecutionUnit] = Field(default_factory=list)
    total_units: int
    ready_units: int
    blocked_units: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
