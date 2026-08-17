"""Approval queue (Sprint 16.3 — deterministic in-memory pending-request queue).

Defines :class:`ApprovalQueueManager`, the deterministic in-memory queue of
pending :class:`ApprovalRequest` records. It supports ``enqueue``, ``dequeue``
(FIFO head, or a specific request by id), ``find_by_workflow``, and ``pending``,
and can emit an immutable :class:`ApprovalQueue` snapshot.

It holds instance-level state only (never a module-level global, so it is not a
singleton), runs no background worker, and is deterministic: a given sequence of
operations always yields the same queue. Strictly additive to Sprints 1.x–16.2.
"""

from typing import List, Optional

from app.services.ai_employee.approval.models import (
    ApprovalQueue,
    ApprovalRequest,
)


class ApprovalQueueManager:
    """Deterministic in-memory queue of pending approval requests (no workers).

    Keeps requests in enqueue order in an instance list. ``enqueue`` appends;
    ``dequeue`` removes the FIFO head or, given a ``request_id``, that specific
    request; ``find_by_workflow`` filters by workflow; ``pending`` returns a copy;
    and ``snapshot`` captures an immutable :class:`ApprovalQueue`. No background
    processing — every operation is synchronous and deterministic.
    """

    def __init__(self) -> None:
        self._requests: List[ApprovalRequest] = []

    def enqueue(self, request: ApprovalRequest) -> None:
        """Append ``request`` to the tail of the pending queue."""
        self._requests.append(request)

    def dequeue(
        self, request_id: Optional[str] = None
    ) -> Optional[ApprovalRequest]:
        """Remove and return the FIFO head, or the request matching ``request_id``.

        With no ``request_id`` this pops the oldest pending request (FIFO), or
        ``None`` when the queue is empty. With a ``request_id`` it removes and
        returns that specific request (or ``None`` if it is not queued).
        """
        if request_id is None:
            return self._requests.pop(0) if self._requests else None
        for index, request in enumerate(self._requests):
            if request.request_id == request_id:
                return self._requests.pop(index)
        return None

    def find_by_workflow(self, workflow_id: str) -> List[ApprovalRequest]:
        """Return the pending requests for ``workflow_id`` in enqueue order."""
        return [
            request
            for request in self._requests
            if request.workflow_id == workflow_id
        ]

    def pending(self) -> List[ApprovalRequest]:
        """Return a copy of all pending requests in enqueue order."""
        return list(self._requests)

    def snapshot(self) -> ApprovalQueue:
        """Return an immutable :class:`ApprovalQueue` of the current pending set."""
        pending = list(self._requests)
        return ApprovalQueue(
            queue_id="approval-queue",
            pending_requests=pending,
            total=len(pending),
            pending_count=len(pending),
        )
