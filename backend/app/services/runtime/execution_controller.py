"""Execution controller (Sprint 14.7 — deterministic control-state derivation).

Reasoning-only component that consumes an :class:`ExecutionProgress` and produces
a single immutable, provider-independent :class:`ExecutionControlState`. It
represents runtime control only: it maps the progress status to a control status
and computes the available control actions (pause/resume/cancel/restart) — but it
never executes a capability, dispatches work, recovers, approves, or changes the
execution progress.

Fully deterministic and offline: no AI, network, clock, UUID, SDK, capability
knowledge, Runtime global, or persistence. Same progress in -> same control state
out.
"""

from typing import Tuple

from app.services.runtime.execution_controller_models import (
    ControlStatus,
    ExecutionControlState,
)
from app.services.runtime.execution_progress_models import (
    ExecutionProgress,
    ProgressStatus,
)

# Progress status -> control status (the mandated deterministic mapping). No
# progress status maps to PAUSED — pause is driven by a later runtime sprint, not
# derivable from progress alone.
_PROGRESS_TO_CONTROL = {
    ProgressStatus.NOT_STARTED.value: ControlStatus.IDLE,
    ProgressStatus.IN_PROGRESS.value: ControlStatus.RUNNING,
    ProgressStatus.COMPLETED.value: ControlStatus.COMPLETED,
    ProgressStatus.FAILED.value: ControlStatus.FAILED,
    ProgressStatus.CANCELLED.value: ControlStatus.CANCELLED,
    ProgressStatus.PARTIAL.value: ControlStatus.RUNNING,
}

# Control status -> (can_pause, can_resume, can_cancel, can_restart). The full
# table is defined for every status (PAUSED included) so the permissions stay
# correct even though this component never derives PAUSED from progress.
_CONTROL_PERMISSIONS = {
    ControlStatus.RUNNING: (True, False, True, False),
    ControlStatus.PAUSED: (False, True, True, False),
    ControlStatus.COMPLETED: (False, False, False, True),
    ControlStatus.FAILED: (False, False, False, True),
    ControlStatus.CANCELLED: (False, False, False, True),
    ControlStatus.IDLE: (False, False, False, False),
}

# Control statuses that represent terminal / active execution (state descriptors).
_TERMINAL_CONTROL = frozenset(
    {
        ControlStatus.COMPLETED,
        ControlStatus.FAILED,
        ControlStatus.CANCELLED,
    }
)
_ACTIVE_CONTROL = frozenset({ControlStatus.RUNNING, ControlStatus.PAUSED})


class ExecutionController:
    """Stateless controller: :class:`ExecutionProgress` -> control state.

    Holds no state and owns no session, provider, cache, clock, or global. It maps
    the progress status to a control status by a fixed table, looks up the
    available control actions for that status, and records deterministic state
    descriptors. It never executes, dispatches, recovers, or approves, and it
    never changes the execution progress.
    """

    def create_control_state(
        self, progress: ExecutionProgress
    ) -> ExecutionControlState:
        """Return a deterministic :class:`ExecutionControlState` (no execution).

        The control status follows the fixed progress→control mapping (an unknown
        progress status falls back to ``IDLE``); the control actions follow the
        fixed permissions table for that status; and the metadata records only
        deterministic state descriptors. The progress is only read — never
        changed — and nothing is executed.
        """
        control_status = _PROGRESS_TO_CONTROL.get(
            progress.progress_status, ControlStatus.IDLE
        )
        can_pause, can_resume, can_cancel, can_restart = self._permissions(
            control_status
        )

        return ExecutionControlState(
            runtime_id=progress.runtime_id,
            execution_id=progress.execution_id,
            control_status=control_status.value,
            can_pause=can_pause,
            can_resume=can_resume,
            can_cancel=can_cancel,
            can_restart=can_restart,
            control_metadata={
                "progress_status": progress.progress_status,
                "control_status": control_status.value,
                "is_terminal": control_status in _TERMINAL_CONTROL,
                "is_active": control_status in _ACTIVE_CONTROL,
                "completion_percentage": progress.completion_percentage,
            },
        )

    @staticmethod
    def _permissions(
        control_status: ControlStatus,
    ) -> Tuple[bool, bool, bool, bool]:
        """Return the (pause, resume, cancel, restart) actions for the status."""
        return _CONTROL_PERMISSIONS[control_status]
