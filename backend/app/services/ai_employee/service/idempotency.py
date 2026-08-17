"""Idempotency manager (Sprint 16.10 — prevent duplicate task execution).

Defines :class:`IdempotencyManager`, which deduplicates task submissions by their
idempotency key: the same request submitted again under the same key resolves to the
same task rather than running twice. It ``register``\\ s the first submission's
outcome, answers ``exists`` for a key, and ``resolve``\\ s a key back to its stored
:class:`IdempotencyRecord`. It also computes a deterministic ``fingerprint`` of a
request so the service can detect a key reused with a different request (a conflict).

It is a plain in-memory ledger: it stores records and computes digests only, and
decides, delegates, and executes nothing. It never touches the Workflow Coordinator,
a capability, a repository, a database, an LLM provider, a thread, or the network.
Its only state is the in-memory ledger plus a deterministic sequence counter.
Strictly additive to Sprints 1.x–16.9, whose modules are left untouched.
"""

from typing import Dict, Optional

from app.services.ai_employee.service.models import (
    IdempotencyRecord,
    TaskSubmissionRequest,
    TaskSubmissionResponse,
)


class IdempotencyManager:
    """In-memory ledger of idempotency records (ledger only, no execution).

    ``register`` stores the outcome of a first submission under its key; ``exists``
    reports whether a key is known; ``resolve`` returns the stored record (or
    ``None``); and ``fingerprint`` digests a request deterministically so a key reused
    with a different request can be told apart. It holds the ledger and a
    deterministic sequence counter — it runs nothing.
    """

    def __init__(self) -> None:
        self._records: Dict[str, IdempotencyRecord] = {}
        self._sequence = 0

    def register(
        self,
        key: str,
        request_id: str,
        task_id: str,
        fingerprint: str,
        response: TaskSubmissionResponse,
    ) -> IdempotencyRecord:
        """Store and return the :class:`IdempotencyRecord` for ``key``."""
        record = IdempotencyRecord(
            key=key,
            request_id=request_id,
            task_id=task_id,
            fingerprint=fingerprint,
            response=response,
            created_at_sequence=self._next(),
        )
        self._records[key] = record
        return record

    def exists(self, key: str) -> bool:
        """Return whether a record is registered for ``key``."""
        return key in self._records

    def resolve(self, key: str) -> Optional[IdempotencyRecord]:
        """Return the record registered for ``key``, or ``None`` when absent."""
        return self._records.get(key)

    def fingerprint(self, request: TaskSubmissionRequest) -> str:
        """Return a deterministic digest of ``request``'s task-defining fields.

        Two submissions with the same employee, task, priority, constraints, and
        workflow steps produce the same fingerprint, so the same key reused with a
        matching request replays and a mismatching request is a conflict. Pure and
        order-stable (input keys are sorted).
        """
        steps = ",".join(
            f"{step.step_id}:{step.capability_name}"
            for step in request.workflow_steps
        )
        inputs = ",".join(
            f"{name}={request.initial_inputs[name]!r}"
            for name in sorted(request.initial_inputs)
        )
        return "|".join(
            [
                request.employee.employee_id,
                request.task_id,
                request.task,
                request.priority.value,
                ",".join(request.constraints),
                steps,
                inputs,
            ]
        )

    def _next(self) -> int:
        """Return the next deterministic sequence ordinal."""
        self._sequence += 1
        return self._sequence
