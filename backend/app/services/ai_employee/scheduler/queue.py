"""Schedule queue (Sprint 16.7 — deterministic tick-ordered in-memory queue).

Defines :class:`ScheduleQueue`, the deterministic in-memory queue of
:class:`ScheduleEntry` records ordered by their next-execution tick. It supports
``enqueue``, ``dequeue_due`` (release the entries due at or before a tick),
``peek``, ``remove``, ``get``, ``update``, ``pending``, and ``ordered`` retrieval.

Ordering is by ``next_execution_tick`` ascending, with insertion order as a stable
tie-break — there is no wall-clock or background worker; a given sequence of
operations always yields the same order. It holds instance-level state only (never
a module-level global, so it is not a singleton). Strictly additive to Sprints
1.x–16.6.
"""

from typing import List, Optional

from app.services.ai_employee.scheduler.models import (
    ScheduleEntry,
    ScheduleStatus,
)


class ScheduleQueue:
    """Deterministic in-memory queue of schedule entries ordered by tick (no workers).

    Keeps entries in an instance list and orders them by ``next_execution_tick``
    (insertion order breaks ties). ``dequeue_due`` releases and removes the
    ``SCHEDULED`` entries due at or before a caller-supplied tick (``PAUSED`` entries
    are held); the other operations manage and read the queue. Every result is
    deterministic — no timers, sleeps, or background processing.
    """

    def __init__(self) -> None:
        self._entries: List[ScheduleEntry] = []

    def _ordered(self) -> List[ScheduleEntry]:
        """Return the entries ordered by tick (stable on insertion order)."""
        return sorted(self._entries, key=lambda entry: entry.next_execution_tick)

    def enqueue(self, entry: ScheduleEntry) -> None:
        """Append ``entry`` to the queue (ordering is applied on read/removal)."""
        self._entries.append(entry)

    def peek(self) -> Optional[ScheduleEntry]:
        """Return the earliest-tick entry without removing it (or ``None``)."""
        ordered = self._ordered()
        return ordered[0] if ordered else None

    def dequeue_due(self, now_tick: int) -> List[ScheduleEntry]:
        """Remove and return the ``SCHEDULED`` entries due at or before ``now_tick``.

        Entries are returned in tick order; ``PAUSED`` (and other non-``SCHEDULED``)
        entries are never released, so pausing a schedule holds it deterministically.
        """
        due = [
            entry
            for entry in self._ordered()
            if entry.status == ScheduleStatus.SCHEDULED
            and entry.next_execution_tick <= now_tick
        ]
        due_ids = {entry.entry_id for entry in due}
        self._entries = [
            entry for entry in self._entries if entry.entry_id not in due_ids
        ]
        return due

    def remove(self, entry_id: str) -> Optional[ScheduleEntry]:
        """Remove and return the entry with ``entry_id`` (or ``None``)."""
        for index, entry in enumerate(self._entries):
            if entry.entry_id == entry_id:
                return self._entries.pop(index)
        return None

    def get(self, entry_id: str) -> Optional[ScheduleEntry]:
        """Return the entry with ``entry_id`` without removing it (or ``None``)."""
        for entry in self._entries:
            if entry.entry_id == entry_id:
                return entry
        return None

    def update(self, entry: ScheduleEntry) -> bool:
        """Replace the queued entry with the same id; return whether it existed."""
        for index, existing in enumerate(self._entries):
            if existing.entry_id == entry.entry_id:
                self._entries[index] = entry
                return True
        return False

    def pending(self) -> List[ScheduleEntry]:
        """Return all queued entries in tick order."""
        return self._ordered()

    def ordered(self) -> List[ScheduleEntry]:
        """Return all queued entries in tick order (alias of :meth:`pending`)."""
        return self._ordered()
