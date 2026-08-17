"""Runtime pause/resume manager (Sprint 14.12 — deterministic pause/resume state).

Reasoning-only component that consumes a :class:`RuntimeExecutionHealth` and
produces a single immutable, provider-independent :class:`RuntimePauseResumeState`.
It coordinates runtime pause/resume state only: it maps the health status to a
pause/resume status and computes whether execution can be paused, can be resumed,
or requires operator action — but it never executes a capability, pauses a thread
or process, resumes execution, recovers, or changes the runtime health.

Fully deterministic and offline: no AI, network, clock, UUID, SDK, capability
knowledge, Runtime global, or persistence. Same health in -> same pause/resume
state out.
"""

from app.services.runtime.runtime_execution_monitor_models import (
    RuntimeExecutionHealth,
)
from app.services.runtime.runtime_pause_resume_models import (
    PauseResumeStatus,
    RuntimePauseResumeState,
)

# Health status -> pause/resume status (the mandated deterministic mapping). Any
# unmapped status falls back to RUNNING.
_HEALTH_TO_PAUSE_RESUME = {
    "HEALTHY": PauseResumeStatus.RUNNING,
    "WARNING": PauseResumeStatus.PAUSED,
    "COMPLETED": PauseResumeStatus.COMPLETED,
    "FAILED": PauseResumeStatus.FAILED,
}

# The statuses for which a human operator must intervene. CANCELLED is included
# for completeness even though no health status maps to it here.
_OPERATOR_ACTION_STATES = frozenset(
    {PauseResumeStatus.FAILED, PauseResumeStatus.CANCELLED}
)


class RuntimePauseResumeManager:
    """Stateless manager: :class:`RuntimeExecutionHealth` -> pause/resume state.

    Holds no state and owns no session, provider, cache, clock, or global. It maps
    the health status to a pause/resume status, allows pausing only while running
    and resuming only while paused, and flags operator action for a failed or
    cancelled runtime. It never executes, pauses/resumes anything, recovers, or
    changes the runtime health.
    """

    def create_pause_resume_state(
        self, health: RuntimeExecutionHealth
    ) -> RuntimePauseResumeState:
        """Return a deterministic :class:`RuntimePauseResumeState` (no execution).

        The status follows the fixed health→pause/resume mapping (an unmapped
        status falls back to ``RUNNING``); ``can_pause`` is true only while
        running, ``can_resume`` only while paused, and ``requires_operator_action``
        only for a failed or cancelled runtime. The health is only read — never
        changed — and nothing is executed, paused, or resumed.
        """
        status = _HEALTH_TO_PAUSE_RESUME.get(
            health.health_status, PauseResumeStatus.RUNNING
        )
        can_pause = status == PauseResumeStatus.RUNNING
        can_resume = status == PauseResumeStatus.PAUSED
        requires_operator_action = status in _OPERATOR_ACTION_STATES

        return RuntimePauseResumeState(
            runtime_id=health.runtime_id,
            execution_id=health.execution_id,
            pause_resume_status=status.value,
            can_pause=can_pause,
            can_resume=can_resume,
            requires_operator_action=requires_operator_action,
            pause_resume_metadata={
                "health_status": health.health_status,
                "pause_resume_status": status.value,
                "can_pause": can_pause,
                "can_resume": can_resume,
                "requires_operator_action": requires_operator_action,
                "health_score": health.health_score,
            },
        )
