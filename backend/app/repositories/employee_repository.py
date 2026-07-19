"""Data-access layer for :class:`~app.models.employee.Employee`.

Persistence only — no business logic. Transaction control is left to the
caller; methods ``flush`` so generated values like ``id`` are populated.

Sprint 18.2A added the employee's capability and permission collections here
rather than in their own repositories: they have no identity outside the
employee that owns them, so they are part of the same aggregate and are always
loaded, written, and discarded with it.

Soft delete: ``deleted_at`` marks a row as gone. Every read path below filters
it out by default, so a deleted employee is invisible to the application while
its memories, blueprint, sessions and conversations stay intact on disk.
"""

import uuid
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_capability import EmployeeCapabilityGrant
from app.models.employee_permission import EmployeePermissionGrant
from app.schemas.employee import EmployeeCreate


class EmployeeRepository:
    """CRUD-style accessors for :class:`Employee` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Reads -----------------------------------------------------------

    def get_by_id(
        self, employee_id: uuid.UUID, *, include_deleted: bool = False
    ) -> Optional[Employee]:
        employee = self.session.get(Employee, employee_id)
        if employee is None:
            return None
        if employee.deleted_at is not None and not include_deleted:
            return None
        return employee

    def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
    ) -> Sequence[Employee]:
        stmt = select(Employee).where(Employee.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(Employee.deleted_at.is_(None))
        stmt = stmt.offset(skip).limit(limit).order_by(Employee.created_at)
        return self.session.scalars(stmt).all()

    def count_by_name(
        self, user_id: uuid.UUID, name: str, *, exclude_id: Optional[uuid.UUID] = None
    ) -> int:
        """How many of this user's live employees already use ``name``."""
        stmt = select(Employee).where(
            Employee.user_id == user_id,
            Employee.name == name,
            Employee.deleted_at.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(Employee.id != exclude_id)
        return len(self.session.scalars(stmt).all())

    # --- Writes ----------------------------------------------------------

    def create(self, user_id: uuid.UUID, data: EmployeeCreate) -> Employee:
        """Persist a new employee owned by ``user_id``.

        Configuration fields carry schema defaults, so a caller that supplies
        only the Sprint 1D fields still produces a fully-formed row.
        """
        employee = Employee(
            user_id=user_id,
            name=data.name,
            role=data.role,
            description=data.description,
            language=data.language,
            personality=data.personality,
            autonomy=data.autonomy.value,
            tone=data.tone.value,
            execution_mode=data.execution_mode.value,
            priority=data.priority.value,
            require_approval=data.require_approval,
            accent=data.accent.value,
            glyph=data.glyph.value,
        )
        self.session.add(employee)
        self.session.flush()
        self.session.refresh(employee)
        return employee

    def update_fields(self, employee: Employee, **fields: object) -> Employee:
        """Assign the supplied attributes. The caller decides which to send."""
        for key, value in fields.items():
            setattr(employee, key, value)
        self.session.flush()
        return employee

    def set_status(
        self,
        employee: Employee,
        status: str,
        *,
        archived_at: Optional[datetime] = None,
    ) -> Employee:
        employee.status = status
        employee.archived_at = archived_at
        self.session.flush()
        return employee

    def soft_delete(self, employee: Employee) -> Employee:
        """Mark the row deleted without removing it or anything it owns."""
        employee.deleted_at = datetime.now(timezone.utc)
        self.session.flush()
        return employee

    def delete(self, employee: Employee) -> None:
        """Hard delete. Cascades to everything the employee owns."""
        self.session.delete(employee)
        self.session.flush()

    # --- Capabilities ----------------------------------------------------

    def replace_capabilities(
        self, employee: Employee, capabilities: Iterable[str]
    ) -> Employee:
        """Make the stored grants exactly ``capabilities``."""
        wanted = set(capabilities)
        existing = {grant.capability: grant for grant in employee.capabilities}

        for capability, grant in existing.items():
            if capability not in wanted:
                self.session.delete(grant)

        for capability in wanted - existing.keys():
            self.session.add(
                EmployeeCapabilityGrant(
                    employee_id=employee.id, capability=capability
                )
            )

        self.session.flush()
        self.session.refresh(employee)
        return employee

    def add_capability(self, employee: Employee, capability: str) -> Employee:
        if any(grant.capability == capability for grant in employee.capabilities):
            return employee
        self.session.add(
            EmployeeCapabilityGrant(employee_id=employee.id, capability=capability)
        )
        self.session.flush()
        self.session.refresh(employee)
        return employee

    def remove_capability(self, employee: Employee, capability: str) -> Employee:
        for grant in employee.capabilities:
            if grant.capability == capability:
                self.session.delete(grant)
                break
        self.session.flush()
        self.session.refresh(employee)
        return employee

    # --- Permissions -----------------------------------------------------

    def replace_permissions(
        self, employee: Employee, permissions: dict[str, str]
    ) -> Employee:
        """Make the stored permissions exactly ``permissions`` (name -> level)."""
        existing = {grant.permission: grant for grant in employee.permissions}

        for permission, grant in existing.items():
            if permission not in permissions:
                self.session.delete(grant)

        for permission, level in permissions.items():
            grant = existing.get(permission)
            if grant is None:
                self.session.add(
                    EmployeePermissionGrant(
                        employee_id=employee.id, permission=permission, level=level
                    )
                )
            elif grant.level != level:
                grant.level = level

        self.session.flush()
        self.session.refresh(employee)
        return employee

