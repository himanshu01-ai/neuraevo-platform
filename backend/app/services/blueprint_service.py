"""Blueprint service: create, retrieve, and update employee blueprints.

Sits between the API layer and the repository layer. Ownership is enforced by
delegating employee resolution to :class:`EmployeeService`. Enforces the
one-blueprint-per-employee rule. No AI, generation, or interview logic.
"""

import uuid

from app.models.blueprint import Blueprint
from app.models.user import User
from app.repositories.blueprint_repository import BlueprintRepository
from app.schemas.blueprint import BlueprintCreate, BlueprintUpdate
from app.services.employee_service import EmployeeService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BlueprintError(Exception):
    """Base class for blueprint-related domain errors."""


class BlueprintNotFoundError(BlueprintError):
    """Raised when an employee has no blueprint."""


class BlueprintAlreadyExistsError(BlueprintError):
    """Raised when creating a blueprint for an employee that already has one."""


class BlueprintAccessDeniedError(BlueprintError):
    """Raised when a blueprint does not belong to the specified employee."""


class BlueprintService:
    """Coordinates blueprint operations using the repository layer.

    The service owns the unit of work: the repository ``flush``es while the
    service commits the transaction.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.blueprints = BlueprintRepository(session)
        self.employees = EmployeeService(session)

    def create_blueprint(
        self, owner: User, employee_id: uuid.UUID, data: BlueprintCreate
    ) -> Blueprint:
        """Create the blueprint for an employee the owner can access.

        Raises ``EmployeeNotFoundError`` / ``EmployeeAccessDeniedError`` for
        the employee, and :class:`BlueprintAlreadyExistsError` if the employee
        already has a blueprint (one-per-employee rule).
        """
        employee = self.employees.get_employee(owner, employee_id)
        if self.blueprints.get_blueprint(employee.id) is not None:
            raise BlueprintAlreadyExistsError(str(employee_id))

        blueprint = self.blueprints.create_blueprint(employee.id, data)
        self.session.commit()
        self.session.refresh(blueprint)
        logger.info(
            "User %s created blueprint %s for employee %s",
            owner.id,
            blueprint.id,
            employee.id,
        )
        return blueprint

    def get_blueprint(self, owner: User, employee_id: uuid.UUID) -> Blueprint:
        """Return the blueprint for an employee the owner can access.

        Raises :class:`BlueprintNotFoundError` if the employee has none.
        """
        employee = self.employees.get_employee(owner, employee_id)
        blueprint = self.blueprints.get_blueprint(employee.id)
        if blueprint is None:
            raise BlueprintNotFoundError(str(employee_id))
        return blueprint

    def update_blueprint(
        self, owner: User, employee_id: uuid.UUID, data: BlueprintUpdate
    ) -> Blueprint:
        """Apply a partial update to an employee's blueprint.

        Resolves and authorizes via :meth:`get_blueprint` (raising the same
        domain exceptions). Only fields set on ``data`` are written.
        """
        blueprint = self.get_blueprint(owner, employee_id)
        self.blueprints.update_blueprint(
            blueprint,
            vision=data.vision,
            communication_style=data.communication_style,
            personality_traits=data.personality_traits,
            goals=data.goals,
            constraints=data.constraints,
            preferences=data.preferences,
        )
        self.session.commit()
        self.session.refresh(blueprint)
        logger.info(
            "User %s updated blueprint %s for employee %s",
            owner.id,
            blueprint.id,
            employee_id,
        )
        return blueprint
