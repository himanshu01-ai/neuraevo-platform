"""Employee service: creation and retrieval logic for AI employees.

Sits between the API layer and the repository layer. Scope is limited to
creating, listing, and fetching employees owned by a user. No voice interview,
memory, capability, task execution, or AI reasoning is performed here.
"""

import uuid
from typing import Sequence

from app.models.employee import Employee
from app.models.user import User
from app.repositories.employee_repository import EmployeeRepository
from app.schemas.employee import EmployeeCreate
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmployeeError(Exception):
    """Base class for employee-related domain errors."""


class EmployeeNotFoundError(EmployeeError):
    """Raised when no employee exists for the given identifier."""


class EmployeeAccessDeniedError(EmployeeError):
    """Raised when an employee exists but is owned by another user."""


class EmployeeService:
    """Coordinates employee operations using the repository layer.

    The service owns the unit of work: the repository ``flush``es while the
    service is responsible for committing the transaction.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.employees = EmployeeRepository(session)

    def create_employee(self, owner: User, data: EmployeeCreate) -> Employee:
        """Create a new employee owned by ``owner`` and persist it."""
        employee = self.employees.create(owner.id, data)
        self.session.commit()
        self.session.refresh(employee)
        logger.info("User %s created employee %s", owner.id, employee.id)
        return employee

    def list_employees(self, owner: User) -> Sequence[Employee]:
        """Return all employees belonging to ``owner``."""
        return self.employees.list_by_user(owner.id)

    def get_employee(self, owner: User, employee_id: uuid.UUID) -> Employee:
        """Return a single employee the ``owner`` is allowed to access.

        Raises :class:`EmployeeNotFoundError` if it does not exist, or
        :class:`EmployeeAccessDeniedError` if it belongs to another user.
        """
        employee = self.employees.get_by_id(employee_id)
        if employee is None:
            raise EmployeeNotFoundError(str(employee_id))
        if employee.user_id != owner.id:
            logger.warning(
                "User %s attempted to access employee %s owned by %s",
                owner.id,
                employee_id,
                employee.user_id,
            )
            raise EmployeeAccessDeniedError(str(employee_id))
        return employee
