"""Memory context service: assemble an employee's memories into context.

Read-only orchestration. Reuses :class:`EmployeeService` for the
User -> Employee ownership chain and the existing :class:`MemoryRepository` to
load memories, then assembles a reusable, newest-first context structure. No
AI generation, persistence, ranking, scoring, or search.
"""

import uuid

from app.models.user import User
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory_context import MemoryContextItem, MemoryContextResponse
from app.services.employee_service import EmployeeService
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Maximum characters for a derived title.
_TITLE_MAX_LENGTH = 80


class MemoryContextService:
    """Builds a structured, newest-first memory context for an employee."""

    def __init__(self, session) -> None:
        self.session = session
        # Reused for the User -> Employee ownership chain.
        self.employees = EmployeeService(session)
        # Reused Sprint 2 persistence (no new repository).
        self.memories = MemoryRepository(session)

    def build_memory_context(
        self, owner: User, employee_id: uuid.UUID
    ) -> MemoryContextResponse:
        """Assemble the employee's memories into context, newest first.

        Raises ``EmployeeNotFoundError`` / ``EmployeeAccessDeniedError`` via the
        reused ownership chain. An employee with no memories yields
        ``memory_count = 0`` and an empty list.
        """
        employee = self.employees.get_employee(owner, employee_id)

        # Load all of the employee's memories via the existing repository,
        # then order newest-first in the service (the repository returns
        # oldest-first and is left unchanged).
        total = self.memories.get_memory_stats(employee.id)["total_memories"]
        rows = (
            self.memories.list_memories(employee.id, limit=total)
            if total
            else []
        )
        ordered = sorted(rows, key=lambda m: m.created_at, reverse=True)

        items = [
            MemoryContextItem(
                id=memory.id,
                title=self._derive_title(memory.content),
                content=memory.content,
                memory_type=memory.memory_type,
                created_at=memory.created_at,
            )
            for memory in ordered
        ]

        logger.info(
            "User %s built memory context for employee %s (%d memories)",
            owner.id,
            employee.id,
            len(items),
        )
        return MemoryContextResponse(
            employee_id=employee.id,
            memory_count=len(items),
            memories=items,
        )

    @staticmethod
    def _derive_title(content: str) -> str:
        """Derive a short title from a memory's content (first line, trimmed)."""
        first_line = next(
            (line.strip() for line in content.splitlines() if line.strip()),
            "",
        )
        if len(first_line) > _TITLE_MAX_LENGTH:
            return first_line[: _TITLE_MAX_LENGTH - 3].rstrip() + "..."
        return first_line
