"""Employee service: creation logic for AI employees.

Sits between the API layer and the repository layer. Sprint 1D scope is
limited to creating an employee and attaching it to its owning user. No voice
interview, memory, task execution, or AI reasoning is performed here.
"""

from app.models.employee import Employee
from app.models.user import User
from app.repositories.employee_repository import EmployeeRepository
from app.schemas.employee import EmployeeCreate
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmployeeError(Exception):
    """Base class for employee-related domain errors."""


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
