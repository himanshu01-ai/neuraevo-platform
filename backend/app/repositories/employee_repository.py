"""Data-access layer for :class:`~app.models.employee.Employee`.

Persistence only — no business logic. Transaction control is left to the
caller; methods ``flush`` so generated values like ``id`` are populated.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate


class EmployeeRepository:
    """CRUD-style accessors for :class:`Employee` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, employee_id: uuid.UUID) -> Optional[Employee]:
        return self.session.get(Employee, employee_id)

    def list_by_user(
        self, user_id: uuid.UUID, *, skip: int = 0, limit: int = 100
    ) -> Sequence[Employee]:
        stmt = (
            select(Employee)
            .where(Employee.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(Employee.created_at)
        )
        return self.session.scalars(stmt).all()

    def create(self, user_id: uuid.UUID, data: EmployeeCreate) -> Employee:
        """Persist a new employee owned by ``user_id``."""
        employee = Employee(
            user_id=user_id,
            name=data.name,
            role=data.role,
            description=data.description,
            language=data.language,
            personality=data.personality,
        )
        self.session.add(employee)
        self.session.flush()
        self.session.refresh(employee)
        return employee

    def delete(self, employee: Employee) -> None:
        self.session.delete(employee)
        self.session.flush()
