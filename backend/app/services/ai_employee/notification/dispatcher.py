"""Notification dispatcher (Sprint 16.4 — abstraction + in-memory implementation).

Defines the :class:`NotificationDispatcher` abstraction and its basic
implementation :class:`InMemoryNotificationDispatcher`. The abstraction is the
seam a later Sprint 16.x delivery channel plugs into; the Sprint 16.4
implementation *records* dispatched and delivered notifications in memory and
**delivers nothing externally** — no Email, Slack, Teams, Discord, SMS, Push, or
WebSocket delivery is implemented here.

The dispatcher owns the ``DISPATCHED`` and ``DELIVERED`` status transitions
(returning new immutable :class:`NotificationMessage` copies); the engine hands it
queued messages and reads back what was dispatched/delivered. Deterministic and
instance-scoped (never a singleton or static store). Strictly additive to Sprints
1.x–16.3.
"""

from abc import ABC, abstractmethod
from typing import Dict, List

from app.services.ai_employee.notification.models import (
    NotificationMessage,
    NotificationStatus,
)


class NotificationDispatcher(ABC):
    """Abstraction that receives dispatchable notifications (no external delivery).

    An implementation ``dispatch`` one message (marking it ``DISPATCHED``),
    ``dispatch_batch`` several, and ``mark_delivered`` one (marking it
    ``DELIVERED``). Implementations must be deterministic and must not deliver
    externally — external channels belong to a later Sprint 16.x.
    """

    @abstractmethod
    def dispatch(self, message: NotificationMessage) -> NotificationMessage:
        """Receive one message and return it marked ``DISPATCHED``."""

    @abstractmethod
    def dispatch_batch(
        self, messages: List[NotificationMessage]
    ) -> List[NotificationMessage]:
        """Receive several messages and return them marked ``DISPATCHED``."""

    @abstractmethod
    def mark_delivered(
        self, message: NotificationMessage
    ) -> NotificationMessage:
        """Mark ``message`` ``DELIVERED`` and return the updated copy."""


class InMemoryNotificationDispatcher(NotificationDispatcher):
    """Basic dispatcher — records dispatched/delivered in memory, delivers none.

    Holds dispatched and delivered notifications in per-instance dictionaries
    keyed by ``message_id`` (never a module-level global, so it is not a
    singleton). ``dispatch`` records a ``DISPATCHED`` copy; ``dispatch_batch``
    dispatches each in order; ``mark_delivered`` moves a message to ``DELIVERED``.
    Nothing leaves the process — there is no Email/Slack/Teams/Discord/SMS/Push/
    WebSocket delivery. Deterministic given the order of calls.
    """

    def __init__(self) -> None:
        self._dispatched: Dict[str, NotificationMessage] = {}
        self._delivered: Dict[str, NotificationMessage] = {}

    def dispatch(self, message: NotificationMessage) -> NotificationMessage:
        """Record ``message`` as ``DISPATCHED`` and return the updated copy."""
        dispatched = message.model_copy(
            update={"status": NotificationStatus.DISPATCHED}
        )
        self._dispatched[dispatched.message_id] = dispatched
        return dispatched

    def dispatch_batch(
        self, messages: List[NotificationMessage]
    ) -> List[NotificationMessage]:
        """Dispatch each message in order and return the dispatched copies."""
        return [self.dispatch(message) for message in messages]

    def mark_delivered(
        self, message: NotificationMessage
    ) -> NotificationMessage:
        """Record ``message`` as ``DELIVERED`` (removing it from dispatched)."""
        delivered = message.model_copy(
            update={"status": NotificationStatus.DELIVERED}
        )
        self._delivered[delivered.message_id] = delivered
        self._dispatched.pop(delivered.message_id, None)
        return delivered

    # --- reads -----------------------------------------------------------
    def dispatched(self) -> List[NotificationMessage]:
        """Return the notifications currently recorded as dispatched."""
        return list(self._dispatched.values())

    def delivered(self) -> List[NotificationMessage]:
        """Return the notifications recorded as delivered."""
        return list(self._delivered.values())
