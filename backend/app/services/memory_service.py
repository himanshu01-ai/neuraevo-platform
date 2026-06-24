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
