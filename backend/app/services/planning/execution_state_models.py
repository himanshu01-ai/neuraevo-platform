"""Execution state models (Sprint 13.9 — immutable aggregate-state DTO).

Provider-independent, immutable aggregate of *the overall execution state* of a
set of task lifecycles: an overall state label, per-state counts, a progress
percentage, the active task ids, and whether execution has terminated. This is
STATE ONLY: it describes an aggregate; it never executes, resolves, or acquires
anything — no execution layer exists.

Carries only plain data (labels, ints, a float, plain string lists) — no SDK,
Runtime, Tool, or Planner-framework type crosses this boundary. Strictly additive
to Sprints 13.1–13.8, whose modules are left untouched.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class ExecutionStateType(str, Enum):
    """The allowed, deterministic overall execution states.

    ``READY``/``WAITING``/``RUNNING`` are in-progress aggregates;
    ``PARTIALLY_COMPLETED`` means some tasks are done while others remain;
    ``COMPLETED``/``FAILED``/``CANCELLED`` are outcome aggregates. Kept as a
    ``str`` enum so each serialises to its label.
    """

    READY = "READY"
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionState(BaseModel):
    """Immutable aggregate execution state over task lifecycles (no execution).

    ``frozen=True`` makes instances immutable. ``execution_id`` is a deterministic
    identifier; ``overall_state`` is one of the :class:`ExecutionStateType`
    labels; the ``*_tasks`` fields count lifecycles in each lifecycle state;
    ``progress_percentage`` is completed/total as a ``0.0``–``100.0`` value;
    ``active_task_ids`` lists the ids of non-terminal tasks; ``terminal`` marks
    that every task has terminated; and ``metadata`` carries provider/telemetry
    data. The value types are intentionally plain — permissive :class:`int`/
    :class:`float` — so the :class:`PlanValidator` is the single place the domain
    rules (valid state, non-negative and consistent counts, progress range,
    terminal and active-id consistency) are enforced. Producing this DTO executes
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    execution_id: str
    overall_state: str
    total_tasks: int
    ready_tasks: int
    waiting_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    cancelled_tasks: int
    skipped_tasks: int
    progress_percentage: float
    active_task_ids: List[str] = Field(default_factory=list)
    terminal: bool
    metadata: Dict[str, Any] = Field(default_factory=dict)
