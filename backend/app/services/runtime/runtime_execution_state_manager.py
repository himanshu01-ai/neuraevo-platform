"""Runtime execution state manager (Sprint 14.10 — deterministic state snapshot).

Reasoning-only component that consumes a :class:`RuntimeExecutionLifecycle` and
produces a single immutable, provider-independent :class:`RuntimeExecutionState`.
It represents the current runtime execution state only: it maps the lifecycle
status to a state status, copies the current stage, and marks whether execution
is active or terminal — but it never executes a capability, dispatches work,
recovers, approves, or changes the lifecycle.

Fully deterministic and offline: no AI, network, clock, UUID, SDK, capability
knowledge, Runtime global, or persistence. Same lifecycle in -> same runtime state
out.
"""

from app.services.runtime.execution_lifecycle_models import (
    RuntimeExecutionLifecycle,
)
from app.services.runtime.runtime_execution_state_models import (
    RuntimeExecutionState,
    RuntimeStateStatus,
)

# Lifecycle status -> runtime state status (the mandated deterministic mapping;
# a 1:1 identity over the shared label set). Any unmapped status falls back to
# INITIALIZED.
_LIFECYCLE_TO_STATE = {
    "INITIALIZED": RuntimeStateStatus.INITIALIZED,
    "RUNNING": RuntimeStateStatus.RUNNING,
    "COMPLETED": RuntimeStateStatus.COMPLETED,
    "FAILED": RuntimeStateStatus.FAILED,
    "CANCELLED": RuntimeStateStatus.CANCELLED,
}

# The state statuses that represent a terminated runtime.
_TERMINAL_STATES = frozenset(
    {
        RuntimeStateStatus.COMPLETED,
        RuntimeStateStatus.FAILED,
        RuntimeStateStatus.CANCELLED,
    }
)


class RuntimeExecutionStateManager:
    """Stateless manager: :class:`RuntimeExecutionLifecycle` -> runtime state.

    Holds no state and owns no session, provider, cache, clock, or global. It maps
    the lifecycle status to a state status, copies the current stage directly, and
    marks the active flag (only while running) and the terminal flag (only for
    completed/failed/cancelled). It never executes, dispatches, recovers, or
    approves, and it never changes the lifecycle.
    """

    def create_state(
        self, lifecycle: RuntimeExecutionLifecycle
    ) -> RuntimeExecutionState:
        """Return a deterministic :class:`RuntimeExecutionState` (no execution).

        The state status follows the fixed lifecycle→state mapping (an unmapped
        status falls back to ``INITIALIZED``); the current stage is copied
        directly from the lifecycle; ``is_active`` is true only while running; and
        ``is_terminal`` is true only for completed/failed/cancelled. The lifecycle
        is only read — never changed — and nothing is executed.
        """
        state_status = _LIFECYCLE_TO_STATE.get(
            lifecycle.lifecycle_status, RuntimeStateStatus.INITIALIZED
        )
        is_active = state_status == RuntimeStateStatus.RUNNING
        is_terminal = state_status in _TERMINAL_STATES

        return RuntimeExecutionState(
            runtime_id=lifecycle.runtime_id,
            execution_id=lifecycle.execution_id,
            state_status=state_status.value,
            current_stage=lifecycle.current_stage,
            is_active=is_active,
            is_terminal=is_terminal,
            runtime_metadata={
                "lifecycle_status": lifecycle.lifecycle_status,
                "state_status": state_status.value,
                "current_stage": lifecycle.current_stage,
                "is_active": is_active,
                "is_terminal": is_terminal,
            },
        )
