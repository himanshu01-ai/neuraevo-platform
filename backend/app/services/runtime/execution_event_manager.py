"""Execution event manager (Sprint 14.8 — deterministic event generation).

Reasoning-only component that consumes an :class:`ExecutionControlState` and
produces a single immutable, provider-independent :class:`ExecutionEventLog`. It
records runtime execution events only: it maps the control status to an event
status, generates one deterministic event representing the current runtime state,
and assembles an immutable event history — but it never executes a capability,
dispatches work, recovers, approves, or changes the control state.

Fully deterministic and offline: no AI, network, clock, UUID, SDK, capability
knowledge, Runtime global, or persistence. Same control state in -> same event log
out. Event ids are derived by hashing (like the Sprint 13 id derivation), never
from a UUID or clock.
"""

import hashlib

from app.services.runtime.execution_controller_models import ExecutionControlState
from app.services.runtime.execution_event_models import (
    EventStatus,
    ExecutionEvent,
    ExecutionEventLog,
)

# Control status -> event status (the mandated deterministic mapping). PAUSED is
# not in the table (it is unreachable from the Sprint 14.7 controller); any
# unmapped status falls back to INITIALIZED.
_CONTROL_TO_EVENT = {
    "IDLE": EventStatus.INITIALIZED,
    "RUNNING": EventStatus.ACTIVE,
    "COMPLETED": EventStatus.COMPLETED,
    "FAILED": EventStatus.FAILED,
    "CANCELLED": EventStatus.CANCELLED,
}

# The single event's sequence always starts at 1.
_FIRST_SEQUENCE = 1


class ExecutionEventManager:
    """Stateless manager: :class:`ExecutionControlState` -> event log.

    Holds no state and owns no session, provider, cache, clock, or global. It maps
    the control status to an event status, generates exactly one deterministic
    event representing the current runtime state (sequence 1, id derived from the
    runtime id, execution id, and sequence), and returns an immutable log. It
    never executes, dispatches, recovers, or approves, and it never changes the
    control state.
    """

    def create_event_log(
        self, control_state: ExecutionControlState
    ) -> ExecutionEventLog:
        """Return a deterministic :class:`ExecutionEventLog` (no execution).

        The event status follows the fixed control→event mapping (an unmapped
        status falls back to ``INITIALIZED``); one event representing the current
        state is generated at sequence 1, with a deterministic id; and the count
        is ``len(events)``. The control state is only read — never changed — and
        nothing is executed.
        """
        event_status = _CONTROL_TO_EVENT.get(
            control_state.control_status, EventStatus.INITIALIZED
        )
        event = ExecutionEvent(
            event_id=self._event_id(
                control_state.runtime_id,
                control_state.execution_id,
                _FIRST_SEQUENCE,
            ),
            event_type=event_status.value,
            execution_id=control_state.execution_id,
            runtime_id=control_state.runtime_id,
            event_sequence=_FIRST_SEQUENCE,
        )
        events = [event]

        return ExecutionEventLog(
            runtime_id=control_state.runtime_id,
            execution_id=control_state.execution_id,
            event_status=event_status.value,
            events=events,
            event_count=len(events),
            event_metadata={
                "control_status": control_state.control_status,
                "event_status": event_status.value,
                "generated_events": len(events),
            },
        )

    @staticmethod
    def _event_id(runtime_id: str, execution_id: str, sequence: int) -> str:
        """Return a deterministic event id from runtime id, execution id, sequence."""
        raw = f"{runtime_id}|{execution_id}|{sequence}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"event-{digest}"
