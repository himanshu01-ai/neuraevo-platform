"""Task lifecycle models (Sprint 13.8 — immutable lifecycle DTO).

Provider-independent, immutable representation of *the execution-state lifecycle*
of a single execution unit: its current and previous state, the states it may
transition to next, whether it has reached a terminal state, and its immutable
state history. This is STATE ONLY: it describes a lifecycle; it never executes,
resolves, or acquires anything — no execution layer exists.

Carries only plain data (labels, a bool, plain string lists) — no SDK, Runtime,
Tool, or Planner-framework type crosses this boundary. Strictly additive to
Sprints 13.1–13.7, whose modules are left untouched.

The canonical transition table (:data:`TASK_LIFECYCLE_TRANSITIONS`) and the
derived terminal set (:data:`TERMINAL_TASK_STATES`) live here as the single
source of truth shared by the engine and the validator.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


class TaskLifecycleState(str, Enum):
    """The allowed task-lifecycle states.

    ``CREATED`` is the genesis; ``READY``/``WAITING``/``RUNNING`` are active
    states; ``COMPLETED``/``FAILED``/``CANCELLED``/``SKIPPED`` are terminal. Kept
    as a ``str`` enum so each serialises to its label.
    """

    CREATED = "CREATED"
    READY = "READY"
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


# The canonical, deterministic transition table. A state whose tuple is empty is
# terminal. This is the single source of truth for both the engine and validator.
TASK_LIFECYCLE_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    TaskLifecycleState.CREATED.value: (TaskLifecycleState.READY.value,),
    TaskLifecycleState.READY.value: (
        TaskLifecycleState.WAITING.value,
        TaskLifecycleState.RUNNING.value,
        TaskLifecycleState.CANCELLED.value,
    ),
    TaskLifecycleState.WAITING.value: (
        TaskLifecycleState.READY.value,
        TaskLifecycleState.CANCELLED.value,
    ),
    TaskLifecycleState.RUNNING.value: (
        TaskLifecycleState.COMPLETED.value,
        TaskLifecycleState.FAILED.value,
        TaskLifecycleState.CANCELLED.value,
    ),
    TaskLifecycleState.COMPLETED.value: (),
    TaskLifecycleState.FAILED.value: (),
    TaskLifecycleState.CANCELLED.value: (),
    TaskLifecycleState.SKIPPED.value: (),
}

# States with no outgoing transitions are terminal.
TERMINAL_TASK_STATES = frozenset(
    state for state, nxt in TASK_LIFECYCLE_TRANSITIONS.items() if not nxt
)


class TaskLifecycle(BaseModel):
    """Immutable lifecycle of one execution unit (no execution).

    ``frozen=True`` makes instances immutable. ``unit_id`` links to the execution
    unit; ``current_state`` is one of the :class:`TaskLifecycleState` labels;
    ``previous_state`` is the state before it (``None`` at genesis);
    ``allowed_next_states`` are the states it may transition to;
    ``is_terminal`` marks a terminal state; ``state_history`` is the immutable,
    ordered record of states it has occupied (ending at ``current_state``); and
    ``metadata`` carries provider/telemetry data. The value types are
    intentionally plain — permissive :class:`str` — so the :class:`PlanValidator`
    is the single place the domain rules (valid states, canonical transitions,
    terminal consistency, coherent history) are enforced. Producing this DTO
    executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    unit_id: str
    current_state: str
    previous_state: Optional[str] = None
    allowed_next_states: List[str] = Field(default_factory=list)
    is_terminal: bool
    state_history: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
