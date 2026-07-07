"""Runtime execution monitor (Sprint 14.11 — deterministic health evaluation).

Reasoning-only component that consumes a :class:`RuntimeExecutionState` and
produces a single immutable, provider-independent :class:`RuntimeExecutionHealth`.
It monitors runtime health only: it maps the state status to a health status,
assigns a deterministic health score, and generates any runtime warnings — but it
never executes a capability, dispatches work, recovers, approves, or changes the
runtime state.

Fully deterministic and offline: no AI, network, clock, UUID, SDK, capability
knowledge, Runtime global, or persistence. Same runtime state in -> same health
out.
"""

from typing import List

from app.services.runtime.runtime_execution_monitor_models import (
    RuntimeExecutionHealth,
    RuntimeHealthStatus,
)
from app.services.runtime.runtime_execution_state_models import (
    RuntimeExecutionState,
)

# State status -> health status (the mandated deterministic mapping). Any unmapped
# status falls back to HEALTHY.
_STATE_TO_HEALTH = {
    "INITIALIZED": RuntimeHealthStatus.HEALTHY,
    "RUNNING": RuntimeHealthStatus.HEALTHY,
    "COMPLETED": RuntimeHealthStatus.COMPLETED,
    "FAILED": RuntimeHealthStatus.FAILED,
    "CANCELLED": RuntimeHealthStatus.WARNING,
}

# Health status -> deterministic 0–100 score.
_HEALTH_SCORE = {
    RuntimeHealthStatus.HEALTHY: 100,
    RuntimeHealthStatus.COMPLETED: 100,
    RuntimeHealthStatus.WARNING: 75,
    RuntimeHealthStatus.FAILED: 0,
}

# State status -> deterministic runtime warnings (empty for any other status).
_STATE_WARNINGS = {
    "FAILED": ("Execution failed",),
    "CANCELLED": ("Execution cancelled",),
}


class RuntimeExecutionMonitor:
    """Stateless monitor: :class:`RuntimeExecutionState` -> health snapshot.

    Holds no state and owns no session, provider, cache, clock, or global. It maps
    the state status to a health status, looks up the deterministic score for that
    status, and emits the warnings for a failed or cancelled execution (none
    otherwise). It never executes, dispatches, recovers, or approves, and it never
    changes the runtime state.
    """

    def create_health(
        self, state: RuntimeExecutionState
    ) -> RuntimeExecutionHealth:
        """Return a deterministic :class:`RuntimeExecutionHealth` (no execution).

        The health status follows the fixed state→health mapping (an unmapped
        status falls back to ``HEALTHY``); the score is the fixed value for that
        health status; and the warnings are the fixed list for a failed/cancelled
        state (empty otherwise). The runtime state is only read — never changed —
        and nothing is executed.
        """
        health_status = _STATE_TO_HEALTH.get(
            state.state_status, RuntimeHealthStatus.HEALTHY
        )
        health_score = _HEALTH_SCORE[health_status]
        warnings = self._warnings(state.state_status)

        return RuntimeExecutionHealth(
            runtime_id=state.runtime_id,
            execution_id=state.execution_id,
            health_status=health_status.value,
            health_score=health_score,
            runtime_warnings=warnings,
            runtime_metadata={
                "state_status": state.state_status,
                "health_status": health_status.value,
                "health_score": health_score,
                "warning_count": len(warnings),
                "is_active": state.is_active,
                "is_terminal": state.is_terminal,
            },
        )

    @staticmethod
    def _warnings(state_status: str) -> List[str]:
        """Return the deterministic warnings for ``state_status`` (empty if none)."""
        return list(_STATE_WARNINGS.get(state_status, ()))
