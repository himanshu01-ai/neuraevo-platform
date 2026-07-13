"""Notification engine (Sprint 16.4 — the production-grade NotificationManager).

Defines :class:`NotificationManager`, the coordinator of the Notification Engine.
It follows the locked flow ``NotificationManager -> NotificationPolicy ->
NotificationQueue -> NotificationDispatcher -> NotificationHistory`` and
coordinates the injected priority model, policy, queue, dispatcher, and history:

    notify          (assess priority, create + enqueue, record, dispatch if the
                     policy says so)
    flush           (release the policy's batch to the dispatcher)
    mark_delivered  (confirm delivery through the dispatcher)
    pending / queue_snapshot / history reads

It coordinates the notification *lifecycle* only: it never executes a workflow,
never executes a capability, and never delivers externally (the dispatcher is
in-memory). Constructor injection only; its only mutable state is a deterministic
sequence counter (the queue, dispatcher, and history hold their own records) — no
static, singleton, or service-locator state. Fully deterministic (no clock, UUID,
network, or SDK). Strictly additive to Sprints 1.x–16.3, whose modules are left
untouched.
"""

from typing import Any, Dict, List, Optional

from app.services.ai_employee.notification.dispatcher import (
    NotificationDispatcher,
)
from app.services.ai_employee.notification.history import NotificationHistory
from app.services.ai_employee.notification.models import (
    NotificationEvent,
    NotificationHistoryEntry,
    NotificationMessage,
    NotificationQueueItem,
    NotificationStatus,
)
from app.services.ai_employee.notification.policies import NotificationPolicy
from app.services.ai_employee.notification.priority import PriorityModel
from app.services.ai_employee.notification.queue import NotificationQueue


class NotificationManager:
    """Coordinates the notification lifecycle over policy, queue, dispatcher, history.

    Constructed with an injected :class:`NotificationPolicy`,
    :class:`NotificationQueue`, :class:`NotificationDispatcher`,
    :class:`NotificationHistory`, and :class:`PriorityModel` (constructor
    injection; it instantiates none of them). It assesses priority, creates and
    enqueues notification records, asks the policy when to dispatch, releases
    dispatchable batches to the dispatcher, confirms delivery, and records an audit
    history. It holds a deterministic sequence counter only; it executes no
    workflow, no capability, and delivers nothing externally.
    """

    def __init__(
        self,
        policy: NotificationPolicy,
        queue: NotificationQueue,
        dispatcher: NotificationDispatcher,
        history: NotificationHistory,
        priority_model: PriorityModel,
    ) -> None:
        self.policy = policy
        self.queue = queue
        self.dispatcher = dispatcher
        self.history = history
        self.priority_model = priority_model
        self._sequence = 0

    # --- creation & lifecycle -------------------------------------------
    def notify(
        self,
        event: NotificationEvent,
        workflow_id: str,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationMessage:
        """Create, enqueue, and (per policy) dispatch a notification.

        Assesses the event's priority via the priority model, builds a
        deterministic ``QUEUED`` :class:`NotificationMessage`, enqueues it, records
        it to history, and then asks the policy whether to dispatch now — flushing
        the released batch to the dispatcher when it says so. Returns the created
        (queued) message. Nothing is executed or delivered externally.
        """
        priority = self.priority_model.priority(event)
        created = NotificationMessage(
            message_id=f"notification-{workflow_id}-{self._next()}",
            workflow_id=workflow_id,
            event=event,
            priority=priority,
            status=NotificationStatus.QUEUED,
            message=message or f"{event.value} for {workflow_id}",
            created_at_sequence=self._sequence,
            message_metadata=dict(metadata or {}),
        )
        self.queue.enqueue(
            NotificationQueueItem(
                item_id=f"queue-{created.message_id}",
                message=created,
                priority=priority,
                sequence=self._next(),
                queued_at_sequence=self._sequence,
            )
        )
        self._record(created, NotificationStatus.QUEUED)

        result = self.policy.evaluate(self.queue.pending_count())
        if result.should_dispatch:
            self.flush(result.batch_size)
        return created

    def flush(self, count: Optional[int] = None) -> List[NotificationMessage]:
        """Release up to ``count`` queued notifications to the dispatcher.

        Dequeues the highest-priority items (all pending when ``count`` is
        ``None``), hands them to the dispatcher as one batch (marking them
        ``DISPATCHED``), records each to history, and returns the dispatched
        messages. It delivers nothing externally.
        """
        if count is None:
            count = self.queue.pending_count()
        items = self.queue.dequeue_batch(count)
        dispatched = self.dispatcher.dispatch_batch(
            [item.message for item in items]
        )
        for message in dispatched:
            self._record(message, NotificationStatus.DISPATCHED)
        return dispatched

    def mark_delivered(
        self, message: NotificationMessage
    ) -> NotificationMessage:
        """Confirm delivery of ``message`` through the dispatcher and record it."""
        delivered = self.dispatcher.mark_delivered(message)
        self._record(delivered, NotificationStatus.DELIVERED)
        return delivered

    # --- reads -----------------------------------------------------------
    def pending(self) -> List[NotificationQueueItem]:
        """Return the queued notifications awaiting dispatch (priority order)."""
        return self.queue.pending()

    def dispatched(self) -> List[NotificationMessage]:
        """Return the notifications currently recorded as dispatched."""
        return self.dispatcher.dispatched()

    def history_for_workflow(
        self, workflow_id: str
    ) -> List[NotificationHistoryEntry]:
        """Return the history entries for ``workflow_id``."""
        return self.history.find_by_workflow(workflow_id)

    # --- helpers ---------------------------------------------------------
    def _record(
        self, message: NotificationMessage, status: NotificationStatus
    ) -> None:
        """Append a deterministic history entry for ``message`` at ``status``."""
        self.history.record(
            NotificationHistoryEntry(
                entry_id=(
                    f"history-{message.message_id}-{status.value}-{self._next()}"
                ),
                message=message,
                status=status,
                recorded_at_sequence=self._sequence,
            )
        )

    def _next(self) -> int:
        """Return the next deterministic sequence ordinal."""
        self._sequence += 1
        return self._sequence
