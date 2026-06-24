"""Data-access layer for :class:`~app.models.memory.Memory`.

Persistence only — no business logic or authorization. Transaction control is
left to the caller; methods ``flush`` so generated values like ``id`` are
populated.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.schemas.memory import MemoryCreate


class MemoryRepository:
    """CRUD-style accessors for :class:`Memory` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_memory(
        self, employee_id: uuid.UUID, data: MemoryCreate
    ) -> Memory:
        """Persist a new memory for ``employee_id``."""
        memory = Memory(
            employee_id=employee_id,
            memory_type=data.memory_type.value,
            content=data.content,
            importance_score=data.importance_score,
        )
        self.session.add(memory)
        self.session.flush()
        self.session.refresh(memory)
        return memory

    def get_memory(self, memory_id: uuid.UUID) -> Optional[Memory]:
        return self.session.get(Memory, memory_id)

    def list_memories(
        self,
        employee_id: uuid.UUID,
        *,
        memory_type: Optional[str] = None,
        min_importance: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Memory]:
        """Return an employee's memories, optionally filtered and paginated.

        Filters are applied only when provided. Results are ordered by
        ``created_at`` ascending (oldest first). This method performs no
        validation; callers are responsible for value/range checks.
        """
        stmt = select(Memory).where(Memory.employee_id == employee_id)
        if memory_type is not None:
            stmt = stmt.where(Memory.memory_type == memory_type)
        if min_importance is not None:
            stmt = stmt.where(Memory.importance_score >= min_importance)
        stmt = stmt.order_by(Memory.created_at).offset(offset).limit(limit)
        return self.session.scalars(stmt).all()

    def delete_memory(self, memory: Memory) -> None:
        self.session.delete(memory)
        self.session.flush()
