"""Execution lifecycle manager (Sprint 14.9 — deterministic lifecycle aggregation).

Reasoning-only component that consumes an :class:`ExecutionEventLog` and produces
a single immutable, provider-independent :class:`RuntimeExecutionLifecycle`. It
represents the runtime lifecycle only: it maps the log's event status to a
lifecycle status, preserves the events in order, determines the current stage from
the latest event, and marks whether the lifecycle has terminated — but it never
executes a capability, dispatches work, recovers, approves, or changes the event
log.

Fully deterministic and offline: no AI, network, clock, UUID, SDK, capability
knowledge, Runtime global, or persistence. Same event log in -> same lifecycle
out.
"""

from app.services.runtime.execution_event_models import ExecutionEventLog
from app.services.runtime.execution_lifecycle_models import (
    LifecycleStatus,
    RuntimeExecutionLifecycle,
)

# Event status -> lifecycle status (the mandated deterministic mapping). Any
# unmapped status falls back to INITIALIZED.
_EVENT_TO_LIFECYCLE = {
    "INITIALIZED": LifecycleStatus.INITIALIZED,
    "ACTIVE": LifecycleStatus.RUNNING,
    "COMPLETED": LifecycleStatus.COMPLETED,
    "FAILED": LifecycleStatus.FAILED,
    "CANCELLED": LifecycleStatus.CANCELLED,
}

# The lifecycle statuses that represent a terminated runtime.
_TERMINAL_LIFECYCLE = frozenset(
    {
        LifecycleStatus.COMPLETED,
        LifecycleStatus.FAILED,
        LifecycleStatus.CANCELLED,
    }
)


class ExecutionLifecycleManager:
    """Stateless manager: :class:`ExecutionEventLog` -> lifecycle snapshot.

    Holds no state and owns no session, provider, cache, clock, or global. It maps
    the log's event status to a lifecycle status, preserves the events in their
    received order, reads the current stage from the latest event, and marks the
    terminal flag. It never executes, dispatches, recovers, or approves, and it
    never changes the event log.
    """

    def create_lifecycle(
        self, event_log: ExecutionEventLog
    ) -> RuntimeExecutionLifecycle:
        """Return a deterministic :class:`RuntimeExecutionLifecycle` (no execution).

        The lifecycle status follows the fixed event→lifecycle mapping (an
        unmapped status falls back to ``INITIALIZED``); the events are preserved
        exactly as received; the current stage is the latest event's type (or the
        log's event status when the history is empty); and the terminal flag is
        set only for completed/failed/cancelled. The event log is only read —
        never changed — and nothing is executed.
        """
        lifecycle_status = _EVENT_TO_LIFECYCLE.get(
            event_log.event_status, LifecycleStatus.INITIALIZED
        )
        events = list(event_log.events)
        current_stage = (
            events[-1].event_type if events else event_log.event_status
        )
        is_terminal = lifecycle_status in _TERMINAL_LIFECYCLE

        return RuntimeExecutionLifecycle(
            runtime_id=event_log.runtime_id,
            execution_id=event_log.execution_id,
            lifecycle_status=lifecycle_status.value,
            lifecycle_events=events,
            current_stage=current_stage,
            is_terminal=is_terminal,
            lifecycle_metadata={
                "event_status": event_log.event_status,
                "lifecycle_status": lifecycle_status.value,
                "event_count": len(events),
                "current_stage": current_stage,
                "is_terminal": is_terminal,
            },
        )
