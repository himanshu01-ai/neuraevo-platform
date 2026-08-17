"""Notification queue (Sprint 16.4 — deterministic in-memory priority queue).

Defines :class:`NotificationQueue`, the deterministic in-memory priority queue of
:class:`NotificationQueueItem` records. It supports ``enqueue``, ``dequeue``
(highest priority first, FIFO within a priority), ``peek``, ``pending`` (in
priority order), ``pending_count``, and ``dequeue_batch`` (batch retrieval).

It holds instance-level state only (never a module-level global, so it is not a
singleton), runs no background worker, and is deterministic: a given sequence of
operations always yields the same ordering. Strictly additive to Sprints
1.x–16.3.
"""

from typing import List, Optional

from app.services.ai_employee.notification.models import (
    NotificationQueueItem,
    PRIORITY_ORDER,
)


class NotificationQueue:
    """Deterministic in-memory priority queue of notification items (no workers).

    Keeps items in an instance list and orders them by priority (``CRITICAL`` →
    ``LOW``), breaking ties by enqueue sequence (FIFO within a priority).
    ``enqueue`` appends; ``dequeue`` removes the highest-priority head; ``peek``
    inspects it without removing; ``dequeue_batch`` releases up to ``count`` items
    in that order; ``pending`` returns a priority-ordered copy. No background
    processing — every operation is synchronous and deterministic.
    """

    def __init__(self) -> None:
        self._items: List[NotificationQueueItem] = []

    def enqueue(self, item: NotificationQueueItem) -> None:
        """Append ``item`` to the queue (ordering is applied on read/removal)."""
        self._items.append(item)

    def _ordered(self) -> List[NotificationQueueItem]:
        """Return the items in dispatch order (priority desc, then FIFO)."""
        return sorted(
            self._items,
            key=lambda item: (-PRIORITY_ORDER[item.priority], item.sequence),
        )

    def peek(self) -> Optional[NotificationQueueItem]:
        """Return the highest-priority item without removing it (or ``None``)."""
        ordered = self._ordered()
        return ordered[0] if ordered else None

    def dequeue(self) -> Optional[NotificationQueueItem]:
        """Remove and return the highest-priority item (or ``None`` when empty)."""
        head = self.peek()
        if head is not None:
            self._items.remove(head)
        return head

    def dequeue_batch(self, count: int) -> List[NotificationQueueItem]:
        """Remove and return up to ``count`` items in dispatch order."""
        released: List[NotificationQueueItem] = []
        for _ in range(max(count, 0)):
            item = self.dequeue()
            if item is None:
                break
            released.append(item)
        return released

    def pending(self) -> List[NotificationQueueItem]:
        """Return a priority-ordered copy of all pending items."""
        return self._ordered()

    def pending_count(self) -> int:
        """Return the number of pending items."""
        return len(self._items)
