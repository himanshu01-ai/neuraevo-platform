"""Audit manager (Sprint 16.11 — produce immutable audit records).

Defines :class:`AuditManager`, which produces and holds an append-only trail of
immutable :class:`AuditRecord`\\ s for the operations the platform tracks — task and
workflow operations, approvals, recoveries, and administrative actions. It supports
``record`` (append a new record), ``history`` (the full trail), ``search`` (a
free-text scan), and ``filter`` (a structured :class:`AuditQuery`), plus per-category
convenience recorders.

It is a plain in-memory, append-only ledger: existing records are never mutated (each
is a frozen DTO), and it decides, delegates, and executes nothing. It never touches
the Workflow Coordinator, a capability, a repository, a database, an LLM provider, a
thread, or the network. Its only state is the ledger plus a deterministic sequence
counter. Strictly additive to Sprints 1.x–16.10, whose modules are left untouched.
"""

from typing import Any, Dict, List, Optional

from app.services.ai_employee.operations.models import (
    AuditCategory,
    AuditQuery,
    AuditRecord,
)


class AuditManager:
    """Append-only ledger of immutable audit records (ledger only, no execution).

    ``record`` appends a new immutable :class:`AuditRecord` and returns it; the
    ``record_task``/``record_workflow``/``record_approval``/``record_recovery``/
    ``record_administrative`` helpers record within a fixed :class:`AuditCategory`.
    ``history`` returns the full trail, ``search`` scans it for free text, and
    ``filter`` applies a structured :class:`AuditQuery`. It holds the ledger and a
    deterministic sequence counter — it runs nothing and never mutates a record.
    """

    def __init__(self) -> None:
        self._records: List[AuditRecord] = []
        self._sequence = 0

    # --- recording -------------------------------------------------------
    def record(
        self,
        category: AuditCategory,
        action: str,
        principal: str = "system",
        resource: str = "",
        outcome: str = "",
        detail: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditRecord:
        """Append and return a new immutable :class:`AuditRecord`."""
        sequence = self._next()
        record = AuditRecord(
            record_id=f"audit-{sequence}",
            category=category,
            action=action,
            principal=principal,
            resource=resource,
            outcome=outcome,
            sequence=sequence,
            detail=detail,
            record_metadata=dict(metadata or {}),
        )
        self._records.append(record)
        return record

    def record_task(self, action: str, **kwargs: Any) -> AuditRecord:
        """Record a ``TASK`` operation."""
        return self.record(AuditCategory.TASK, action, **kwargs)

    def record_workflow(self, action: str, **kwargs: Any) -> AuditRecord:
        """Record a ``WORKFLOW`` operation."""
        return self.record(AuditCategory.WORKFLOW, action, **kwargs)

    def record_approval(self, action: str, **kwargs: Any) -> AuditRecord:
        """Record an ``APPROVAL`` operation."""
        return self.record(AuditCategory.APPROVAL, action, **kwargs)

    def record_recovery(self, action: str, **kwargs: Any) -> AuditRecord:
        """Record a ``RECOVERY`` operation."""
        return self.record(AuditCategory.RECOVERY, action, **kwargs)

    def record_administrative(
        self, action: str, **kwargs: Any
    ) -> AuditRecord:
        """Record an ``ADMINISTRATIVE`` operation."""
        return self.record(AuditCategory.ADMINISTRATIVE, action, **kwargs)

    # --- reads -----------------------------------------------------------
    def history(self) -> List[AuditRecord]:
        """Return the full audit trail in deterministic recording order."""
        return list(self._records)

    def search(self, text: str) -> List[AuditRecord]:
        """Return records whose fields contain ``text`` (case-insensitive substring)."""
        needle = (text or "").lower()
        return [
            record
            for record in self._records
            if needle in self._haystack(record)
        ]

    def filter(self, query: AuditQuery) -> List[AuditRecord]:
        """Return the records matching ``query`` in order (capped by ``query.limit``).

        A ``None`` query field is not filtered on; ``category``/``principal``/
        ``action``/``resource`` are exact matches, ``text`` is a case-insensitive
        substring, and ``limit`` caps the count.
        """
        matches = [
            record
            for record in self._records
            if self._matches(record, query)
        ]
        if query.limit is not None:
            matches = matches[: query.limit]
        return matches

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _matches(record: AuditRecord, query: AuditQuery) -> bool:
        """Return whether ``record`` satisfies every set field of ``query``."""
        if query.category is not None and record.category != query.category:
            return False
        if (
            query.principal is not None
            and record.principal != query.principal
        ):
            return False
        if query.action is not None and record.action != query.action:
            return False
        if query.resource is not None and record.resource != query.resource:
            return False
        if (
            query.text is not None
            and query.text.lower() not in AuditManager._haystack(record)
        ):
            return False
        return True

    @staticmethod
    def _haystack(record: AuditRecord) -> str:
        """Return the lowercased searchable text of ``record``."""
        return " ".join(
            [
                record.category.value,
                record.action,
                record.principal,
                record.resource,
                record.outcome,
                record.detail,
            ]
        ).lower()

    def _next(self) -> int:
        """Return the next deterministic sequence ordinal."""
        self._sequence += 1
        return self._sequence
