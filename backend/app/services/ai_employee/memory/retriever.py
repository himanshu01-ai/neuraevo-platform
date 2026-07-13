"""Memory retriever (Sprint 16.6 — deterministic in-memory index + filters).

Defines :class:`MemoryRetriever`, the deterministic in-memory index of
:class:`MemoryRecord`s and the query engine over them. It holds the remembered
records (the memory index — not a persistence repository, database, or vector
store) and retrieves them with exact, deterministic filters: by workflow, by
category, by priority (importance), by tag, and newest-first (``latest``).

There is no semantic search and no embeddings — every filter is an exact match.
It holds instance-level state only (never a module-level global, so it is not a
singleton) and runs no background worker. Strictly additive to Sprints 1.x–16.5.
"""

from typing import Dict, List

from app.services.ai_employee.memory.models import MemoryQuery, MemoryRecord


class MemoryRetriever:
    """Deterministic in-memory index of memories with exact-match retrieval.

    Keeps records in an instance dictionary and preserves insertion order for the
    ``latest`` filter. ``add``/``update``/``remove``/``get``/``all`` manage the
    index; ``retrieve`` applies a :class:`MemoryQuery`'s exact filters (workflow,
    category, importance, tag), optionally orders newest-first, and caps the count.
    No semantic scoring, embeddings, or background processing — every result is
    deterministic. This is the memory index, not a persistence repository.
    """

    def __init__(self) -> None:
        self._records: Dict[str, MemoryRecord] = {}
        self._order: List[str] = []

    def add(self, record: MemoryRecord) -> None:
        """Insert ``record`` (or replace one with the same id), preserving order."""
        if record.memory_id not in self._records:
            self._order.append(record.memory_id)
        self._records[record.memory_id] = record

    def update(self, record: MemoryRecord) -> None:
        """Replace the stored record with the same id (in place, order preserved)."""
        if record.memory_id in self._records:
            self._records[record.memory_id] = record

    def remove(self, memory_id: str) -> bool:
        """Remove the record with ``memory_id``; return whether it existed."""
        existed = memory_id in self._records
        self._records.pop(memory_id, None)
        if memory_id in self._order:
            self._order.remove(memory_id)
        return existed

    def get(self, memory_id: str) -> MemoryRecord:
        """Return the record with ``memory_id`` (or ``None`` if absent)."""
        return self._records.get(memory_id)

    def all(self) -> List[MemoryRecord]:
        """Return every record in insertion order."""
        return [self._records[memory_id] for memory_id in self._order]

    def retrieve(self, query: MemoryQuery) -> List[MemoryRecord]:
        """Return the records matching ``query`` (exact filters, deterministic).

        Narrows by workflow, category, importance, and tag (each an exact match),
        orders newest-first when ``latest`` is set, and caps the count with
        ``limit``. There is no semantic search — the same index and query always
        yield the same list.
        """
        records = self.all()
        if query.workflow_id is not None:
            records = [
                r for r in records if r.workflow_id == query.workflow_id
            ]
        if query.category is not None:
            records = [r for r in records if r.category == query.category]
        if query.importance is not None:
            records = [r for r in records if r.importance == query.importance]
        if query.tag is not None:
            records = [r for r in records if query.tag in r.tags]
        if query.latest:
            records = sorted(
                records, key=lambda r: r.created_at_sequence, reverse=True
            )
        if query.limit is not None:
            records = records[: query.limit]
        return records
