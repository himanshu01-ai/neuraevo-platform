"""Memory service: creation and listing of employee memories.

Sits between the API layer and the repository layer. Ownership is enforced by
delegating employee resolution to :class:`EmployeeService`, which raises
``EmployeeNotFoundError`` / ``EmployeeAccessDeniedError``. No AI logic, vector
search, embeddings, or retrieval ranking is performed here.
"""

import uuid
from typing import Sequence

from app.models.memory import Memory
from app.models.user import User
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory import MemoryCreate
from app.services.employee_service import EmployeeService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MemoryError(Exception):
    """Base class for memory-related domain errors."""


class MemoryNotFoundError(MemoryError):
    """Raised when no memory exists for the given identifier."""


class MemoryAccessDeniedError(MemoryError):
    """Raised when a memory exists but does not belong to the given employee."""


class MemoryService:
    """Coordinates memory operations using the repository layer.

    The service owns the unit of work: the repository ``flush``es while the
    service commits the transaction.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.memories = MemoryRepository(session)
        self.employees = EmployeeService(session)

    def create_memory(
        self, owner: User, employee_id: uuid.UUID, data: MemoryCreate
    ) -> Memory:
        """Create a memory for an employee the ``owner`` is allowed to access."""
        # Raises EmployeeNotFoundError (404) / EmployeeAccessDeniedError (403).
        employee = self.employees.get_employee(owner, employee_id)
        memory = self.memories.create_memory(employee.id, data)
        self.session.commit()
        self.session.refresh(memory)
        logger.info(
            "User %s added %s memory %s to employee %s",
            owner.id,
            memory.memory_type,
            memory.id,
            employee.id,
        )
        return memory

    def list_memories(
        self, owner: User, employee_id: uuid.UUID
    ) -> Sequence[Memory]:
        """List memories for an employee the ``owner`` is allowed to access."""
        employee = self.employees.get_employee(owner, employee_id)
        return self.memories.list_memories(employee.id)

    def get_memory(
        self, owner: User, employee_id: uuid.UUID, memory_id: uuid.UUID
    ) -> Memory:
        """Return a single memory scoped to an employee the owner can access.

        Raises :class:`EmployeeNotFoundError` / :class:`EmployeeAccessDeniedError`
        if the employee is missing or not owned by ``owner``;
        :class:`MemoryNotFoundError` if the memory does not exist; and
        :class:`MemoryAccessDeniedError` if it exists but belongs to a
        different employee.
        """
        employee = self.employees.get_employee(owner, employee_id)
        memory = self.memories.get_memory(memory_id)
        if memory is None:
            raise MemoryNotFoundError(str(memory_id))
        if memory.employee_id != employee.id:
            logger.warning(
                "User %s attempted to access memory %s via employee %s, "
                "but it belongs to employee %s",
                owner.id,
                memory_id,
                employee.id,
                memory.employee_id,
            )
            raise MemoryAccessDeniedError(str(memory_id))
        return memory

    def delete_memory(
        self, owner: User, employee_id: uuid.UUID, memory_id: uuid.UUID
    ) -> None:
        """Delete a memory the owner is allowed to access.

        Resolves and authorizes the memory via :meth:`get_memory` (raising the
        same domain exceptions) before deleting and committing.
        """
        memory = self.get_memory(owner, employee_id, memory_id)
        self.memories.delete_memory(memory)
        self.session.commit()
        logger.info(
            "User %s deleted memory %s from employee %s",
            owner.id,
            memory_id,
            employee_id,
        )
