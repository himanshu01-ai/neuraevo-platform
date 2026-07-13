"""Notification history (Sprint 16.4 — deterministic in-memory audit history).

Defines :class:`NotificationHistory`, the deterministic in-memory store of
immutable :class:`NotificationHistoryEntry` records. It records an entry per
notification lifecycle point (queued, dispatched, delivered) and supports
``find_by_workflow``, ``find_by_type``, and ``find_by_status`` queries plus a full
``all`` listing.

It holds instance-level state only (never a module-level global, so it is not a
singleton), runs no background worker, and is deterministic: a given sequence of
records always yields the same history. Strictly additive to Sprints 1.x–16.3.
"""

from typing import List

from app.services.ai_employee.notification.models import (
    NotificationEvent,
    NotificationHistoryEntry,
    NotificationStatus,
)


class NotificationHistory:
    """Deterministic in-memory audit history of notifications (no workers).

    Appends :class:`NotificationHistoryEntry` records in order and answers
    ``find_by_workflow``/``find_by_type``/``find_by_status`` queries plus ``all``.
    Purely a store of immutable records — it decides, dispatches, and delivers
    nothing.
    """

    def __init__(self) -> None:
        self._entries: List[NotificationHistoryEntry] = []

    def record(self, entry: NotificationHistoryEntry) -> None:
        """Append ``entry`` to the history."""
        self._entries.append(entry)

    def all(self) -> List[NotificationHistoryEntry]:
        """Return a copy of every recorded entry in record order."""
        return list(self._entries)

    def find_by_workflow(
        self, workflow_id: str
    ) -> List[NotificationHistoryEntry]:
        """Return the entries whose notification belongs to ``workflow_id``."""
        return [
            entry
            for entry in self._entries
            if entry.message.workflow_id == workflow_id
        ]

    def find_by_type(
        self, event: NotificationEvent
    ) -> List[NotificationHistoryEntry]:
        """Return the entries whose notification event is ``event``."""
        return [
            entry for entry in self._entries if entry.message.event == event
        ]

    def find_by_status(
        self, status: NotificationStatus
    ) -> List[NotificationHistoryEntry]:
        """Return the entries recorded at lifecycle ``status``."""
        return [entry for entry in self._entries if entry.status == status]
