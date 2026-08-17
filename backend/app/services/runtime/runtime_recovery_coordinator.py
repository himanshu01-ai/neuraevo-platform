"""Runtime recovery coordinator (Sprint 14.13 — deterministic recovery state).

Reasoning-only component that consumes a :class:`RuntimePauseResumeState` and
produces a single immutable, provider-independent :class:`RuntimeRecoveryState`.
It coordinates runtime recovery only: it maps the pause/resume status to a
recovery status and strategy and determines whether recovery is required — but it
never executes a capability, retries execution, resumes execution, performs
planning, or changes the pause/resume state.

Fully deterministic and offline: no AI, network, clock, UUID, SDK, capability
knowledge, Runtime global, or persistence. Same pause/resume state in -> same
recovery state out.
"""

from typing import Tuple

from app.services.runtime.runtime_pause_resume_models import (
    RuntimePauseResumeState,
)
from app.services.runtime.runtime_recovery_models import (
    RecoveryStatus,
    RecoveryStrategy,
    RuntimeRecoveryState,
)

# Pause/resume status -> (recovery status, recovery strategy). The mandated
# deterministic mapping; an unmapped status falls back to no recovery.
_PAUSE_RESUME_TO_RECOVERY = {
    "RUNNING": (RecoveryStatus.NOT_REQUIRED, RecoveryStrategy.NONE),
    "PAUSED": (RecoveryStatus.READY, RecoveryStrategy.RESUME),
    "COMPLETED": (RecoveryStatus.NOT_REQUIRED, RecoveryStrategy.NONE),
    "FAILED": (RecoveryStatus.FAILED, RecoveryStrategy.MANUAL),
    "CANCELLED": (RecoveryStatus.READY, RecoveryStrategy.RESTART),
}

# The recovery statuses for which recovery is required.
_RECOVERY_REQUIRED_STATES = frozenset(
    {RecoveryStatus.READY, RecoveryStatus.FAILED}
)


class RuntimeRecoveryCoordinator:
    """Stateless coordinator: :class:`RuntimePauseResumeState` -> recovery state.

    Holds no state and owns no session, provider, cache, clock, or global. It maps
    the pause/resume status to a recovery status and strategy and marks recovery
    required only for ready or failed recovery. It never executes, retries,
    resumes, plans, or changes the pause/resume state.
    """

    def create_recovery_state(
        self, pause_resume: RuntimePauseResumeState
    ) -> RuntimeRecoveryState:
        """Return a deterministic :class:`RuntimeRecoveryState` (no execution).

        The recovery status and strategy follow the fixed pause/resume→recovery
        mapping (an unmapped status falls back to ``NOT_REQUIRED``/``NONE``);
        recovery is required only for a ``READY`` or ``FAILED`` recovery status.
        The pause/resume state is only read — never changed — and nothing is
        executed, retried, or resumed.
        """
        recovery_status, recovery_strategy = self._resolve(
            pause_resume.pause_resume_status
        )
        recovery_required = recovery_status in _RECOVERY_REQUIRED_STATES

        return RuntimeRecoveryState(
            runtime_id=pause_resume.runtime_id,
            execution_id=pause_resume.execution_id,
            recovery_status=recovery_status.value,
            recovery_required=recovery_required,
            recovery_strategy=recovery_strategy.value,
            recovery_metadata={
                "pause_resume_status": pause_resume.pause_resume_status,
                "recovery_status": recovery_status.value,
                "recovery_strategy": recovery_strategy.value,
                "recovery_required": recovery_required,
                "requires_operator_action": (
                    pause_resume.requires_operator_action
                ),
            },
        )

    @staticmethod
    def _resolve(
        pause_resume_status: str,
    ) -> Tuple[RecoveryStatus, RecoveryStrategy]:
        """Return the (recovery status, strategy) for a pause/resume status."""
        return _PAUSE_RESUME_TO_RECOVERY.get(
            pause_resume_status,
            (RecoveryStatus.NOT_REQUIRED, RecoveryStrategy.NONE),
        )
