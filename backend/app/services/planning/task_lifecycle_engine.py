"""Task lifecycle engine (Sprint 13.8 — deterministic lifecycle construction).

Reasoning-only component that manages the execution-state lifecycle of the
:class:`ExecutionUnit` records inside an :class:`ExecutionQueue`, producing one
immutable :class:`TaskLifecycle` per unit. It represents execution state only:
it initialises each lifecycle's starting state, computes its allowed transitions
and terminal flag, and seeds an immutable history — but it never executes,
resolves, or acquires anything, and it never mutates the queue.

Fully deterministic and offline: no AI, network, SDK, Runtime, Session, Registry,
Permission, Tool framework, Memory, or Gemini. Same queue in -> same lifecycles
out.
"""

from typing import List, Tuple

from app.services.planning.execution_queue_models import (
    ExecutionQueue,
    ExecutionUnitStatus,
)
from app.services.planning.task_lifecycle_models import (
    TASK_LIFECYCLE_TRANSITIONS,
    TERMINAL_TASK_STATES,
    TaskLifecycle,
    TaskLifecycleState,
)

# Queue unit status -> the lifecycle state the unit starts in.
_UNIT_STATUS_TO_STATE = {
    ExecutionUnitStatus.READY.value: TaskLifecycleState.READY.value,
    ExecutionUnitStatus.WAITING.value: TaskLifecycleState.WAITING.value,
    ExecutionUnitStatus.BLOCKED.value: TaskLifecycleState.WAITING.value,
}

# The valid genesis path to each possible starting state (every lifecycle begins
# at CREATED). These paths follow the canonical transition table exactly.
_INIT_PATH = {
    TaskLifecycleState.READY.value: (
        TaskLifecycleState.CREATED.value,
        TaskLifecycleState.READY.value,
    ),
    TaskLifecycleState.WAITING.value: (
        TaskLifecycleState.CREATED.value,
        TaskLifecycleState.READY.value,
        TaskLifecycleState.WAITING.value,
    ),
}


class TaskLifecycleEngine:
    """Stateless builder: :class:`ExecutionQueue` -> ``List[TaskLifecycle]``.

    Holds no state and owns no session, provider, or cache. It creates one
    lifecycle per execution unit, derives the deterministic starting state from
    the unit's status, seeds the immutable genesis history, and computes the
    allowed transitions and terminal flag from the canonical table. It never
    executes a step and never mutates the queue.
    """

    def create_lifecycles(self, queue: ExecutionQueue) -> List[TaskLifecycle]:
        """Return one deterministic :class:`TaskLifecycle` per queue unit.

        Each unit's status determines its starting lifecycle state; the queue is
        only read — never mutated — and nothing is executed.
        """
        return [self._lifecycle(unit) for unit in queue.execution_units]

    @classmethod
    def _lifecycle(cls, unit) -> TaskLifecycle:
        """Build the immutable lifecycle for a single execution ``unit``."""
        start_state = _UNIT_STATUS_TO_STATE.get(
            unit.status, TaskLifecycleState.WAITING.value
        )
        history: Tuple[str, ...] = _INIT_PATH[start_state]
        previous_state = history[-2] if len(history) >= 2 else None

        return TaskLifecycle(
            unit_id=unit.unit_id,
            current_state=start_state,
            previous_state=previous_state,
            allowed_next_states=list(TASK_LIFECYCLE_TRANSITIONS[start_state]),
            is_terminal=start_state in TERMINAL_TASK_STATES,
            state_history=list(history),
            metadata={
                "step_number": unit.step_number,
                "queue_unit_status": unit.status,
            },
        )
