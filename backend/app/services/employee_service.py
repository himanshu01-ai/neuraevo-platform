"""Employee service: the AI employee domain's business logic.

Sits between the API layer and the repository layer and owns every decision:
ownership, lifecycle transitions, configuration consistency, and what gets
recorded in an employee's history. Repositories persist; this decides.

Sprint 18.2A completed the domain — update, archive/restore, soft delete,
configuration, capabilities, permissions, activity, assignments and health.
Nothing here executes an employee, invokes a capability, or runs a workflow;
this layer still only describes.
"""

import uuid
from typing import Optional, Sequence

from app.models.employee import Employee
from app.models.employee_assignment import EmployeeAssignment
from app.models.employee_activity import EmployeeActivityEvent
from app.models.user import User
from app.repositories.employee_activity_repository import (
    EmployeeActivityRepository,
)
from app.repositories.employee_assignment_repository import (
    EmployeeAssignmentRepository,
)
from app.repositories.employee_repository import EmployeeRepository
from app.schemas.employee import (
    EmployeeAssignmentCreate,
    EmployeeCreate,
    EmployeeUpdate,
)
from app.services.employee_health import EmployeeHealthReport, derive_health
from app.services.employee_lifecycle import RESTORABLE_STATUSES, can_transition
from app.utils.constants import (
    EmployeeActivityKind,
    EmployeeCapability,
    EmployeeStatus,
    PermissionLevel,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmployeeError(Exception):
    """Base class for employee-related domain errors."""


class EmployeeNotFoundError(EmployeeError):
    """Raised when no employee exists for the given identifier."""


class EmployeeAccessDeniedError(EmployeeError):
    """Raised when an employee exists but is owned by another user."""


class EmployeeValidationError(EmployeeError):
    """Raised when a request would leave the employee in an invalid state."""


class InvalidStatusTransitionError(EmployeeError):
    """Raised when a status change is not permitted from the current status."""


class EmployeeService:
    """Coordinates employee operations using the repository layer.

    The service owns the unit of work: repositories ``flush`` while the service
    is responsible for committing the transaction.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.employees = EmployeeRepository(session)
        self.activity = EmployeeActivityRepository(session)
        self.assignments = EmployeeAssignmentRepository(session)

    # --- Creation --------------------------------------------------------

    def create_employee(self, owner: User, data: EmployeeCreate) -> Employee:
        """Create a new employee owned by ``owner`` and persist it."""
        self._validate_permissions(data.capabilities, data.permissions)

        employee = self.employees.create(owner.id, data)

        if data.capabilities:
            self.employees.replace_capabilities(
                employee, [c.value for c in data.capabilities]
            )
        if data.permissions:
            self.employees.replace_permissions(
                employee, {p.permission.value: p.level.value for p in data.permissions}
            )

        self._record(
            employee, EmployeeActivityKind.CREATED, f"{employee.name} was created"
        )
        self.session.commit()
        self.session.refresh(employee)
        logger.info("User %s created employee %s", owner.id, employee.id)
        return employee

    # --- Reads -----------------------------------------------------------

    def list_employees(self, owner: User) -> Sequence[Employee]:
        """Return all of ``owner``'s employees, excluding soft-deleted ones."""
        return self.employees.list_by_user(owner.id)

    def get_employee(self, owner: User, employee_id: uuid.UUID) -> Employee:
        """Return a single employee the ``owner`` is allowed to access.

        Raises :class:`EmployeeNotFoundError` if it does not exist or has been
        deleted, or :class:`EmployeeAccessDeniedError` if it belongs to another
        user.
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

    # --- Update ----------------------------------------------------------

    def update_employee(
        self, owner: User, employee_id: uuid.UUID, data: EmployeeUpdate
    ) -> Employee:
        """Apply a partial update.

        Only fields that were actually supplied change — ``exclude_unset``
        distinguishes "set this to null" from "leave it alone". Identity,
        configuration and status changes are recorded as separate events so the
        history says which kind of change happened.
        """
        employee = self.get_employee(owner, employee_id)
        supplied = data.model_dump(exclude_unset=True)

        target_status = self._resolve_status_change(employee, data)
        self._apply_scalar_updates(employee, data, supplied)
        configuration_changed = self._apply_configuration(employee, data, supplied)

        if target_status is not None:
            previous = employee.status
            self.employees.set_status(
                employee,
                target_status.value,
                # Archiving through an update keeps the archive stamp honest.
                archived_at=(
                    self._now()
                    if target_status is EmployeeStatus.ARCHIVED
                    else None
                ),
            )
            self._record(
                employee,
                EmployeeActivityKind.STATUS_CHANGED,
                f"Status changed from {previous} to {target_status.value}",
            )

        if configuration_changed:
            self._record(
                employee,
                EmployeeActivityKind.CONFIGURATION_CHANGED,
                f"{employee.name}'s configuration was changed",
            )

        identity_fields = {"name", "role", "description", "language", "personality"}
        if identity_fields & supplied.keys():
            self._record(
                employee,
                EmployeeActivityKind.UPDATED,
                f"{employee.name} was updated",
            )

        self.session.commit()
        self.session.refresh(employee)
        logger.info("User %s updated employee %s", owner.id, employee.id)
        return employee

    # --- Lifecycle -------------------------------------------------------

    def archive_employee(self, owner: User, employee_id: uuid.UUID) -> Employee:
        """Retire an employee without destroying it."""
        employee = self.get_employee(owner, employee_id)
        current = self._status_of(employee)

        if current is EmployeeStatus.ARCHIVED:
            return employee

        if not can_transition(current, EmployeeStatus.ARCHIVED):
            raise InvalidStatusTransitionError(
                f"An employee cannot move from {current.value} to archived."
            )

        self.employees.set_status(
            employee, EmployeeStatus.ARCHIVED.value, archived_at=self._now()
        )
        self._record(
            employee,
            EmployeeActivityKind.ARCHIVED,
            f"{employee.name} was archived",
        )
        self.session.commit()
        self.session.refresh(employee)
        return employee

    def restore_employee(
        self,
        owner: User,
        employee_id: uuid.UUID,
        target: EmployeeStatus = EmployeeStatus.DRAFT,
    ) -> Employee:
        """Bring an archived employee back.

        A restore returns it to the bench (``draft`` or ``ready``), never
        straight into service — resuming work is a decision its owner makes
        afterwards.
        """
        employee = self.get_employee(owner, employee_id)

        if self._status_of(employee) is not EmployeeStatus.ARCHIVED:
            raise InvalidStatusTransitionError("Only an archived employee can be restored.")

        if target not in RESTORABLE_STATUSES:
            raise InvalidStatusTransitionError(
                f"An employee cannot be restored directly to {target.value}."
            )

        self.employees.set_status(employee, target.value, archived_at=None)
        self._record(
            employee,
            EmployeeActivityKind.RESTORED,
            f"{employee.name} was restored to {target.value}",
        )
        self.session.commit()
        self.session.refresh(employee)
        return employee

    def delete_employee(self, owner: User, employee_id: uuid.UUID) -> None:
        """Soft delete.

        A hard delete would cascade into this employee's memories, blueprint,
        interview sessions and conversations — years of accumulated context
        destroyed by one click, with no way back. The row is marked deleted
        instead: it disappears from every read path while everything it owns
        stays on disk and can be recovered by an operator.
        """
        employee = self.get_employee(owner, employee_id)
        self.employees.soft_delete(employee)
        self.session.commit()
        logger.info("User %s deleted employee %s (soft)", owner.id, employee_id)

    # --- Capabilities ----------------------------------------------------

    def list_capabilities(
        self, owner: User, employee_id: uuid.UUID
    ) -> list[EmployeeCapability]:
        employee = self.get_employee(owner, employee_id)
        return [EmployeeCapability(g.capability) for g in employee.capabilities]

    def add_capability(
        self, owner: User, employee_id: uuid.UUID, capability: EmployeeCapability
    ) -> Employee:
        employee = self.get_employee(owner, employee_id)
        held = {g.capability for g in employee.capabilities}
        if capability.value in held:
            return employee

        self.employees.add_capability(employee, capability.value)
        self._record(
            employee,
            EmployeeActivityKind.CONFIGURATION_CHANGED,
            f"Capability '{capability.value}' was granted",
        )
        self.session.commit()
        self.session.refresh(employee)
        return employee

    def remove_capability(
        self, owner: User, employee_id: uuid.UUID, capability: EmployeeCapability
    ) -> Employee:
        """Revoke a capability, and block anything that depended on it.

        Leaving a permission enabled for a capability the employee no longer
        holds would be a configuration the platform could not honour, so the
        dependent permissions drop to BLOCKED in the same transaction.
        """
        employee = self.get_employee(owner, employee_id)
        held = {g.capability for g in employee.capabilities}
        if capability.value not in held:
            return employee

        self.employees.remove_capability(employee, capability.value)

        remaining = {g.capability for g in employee.capabilities}
        levels = {
            g.permission: (
                g.level
                if self._permission_is_satisfied(g.permission, remaining)
                else PermissionLevel.BLOCKED.value
            )
            for g in employee.permissions
        }
        if levels:
            self.employees.replace_permissions(employee, levels)

        self._record(
            employee,
            EmployeeActivityKind.CONFIGURATION_CHANGED,
            f"Capability '{capability.value}' was revoked",
        )
        self.session.commit()
        self.session.refresh(employee)
        return employee

    # --- Assignments -----------------------------------------------------

    def list_assignments(
        self, owner: User, employee_id: uuid.UUID
    ) -> Sequence[EmployeeAssignment]:
        employee = self.get_employee(owner, employee_id)
        return self.assignments.list_by_employee(employee.id)

    def assign_work(
        self, owner: User, employee_id: uuid.UUID, data: EmployeeAssignmentCreate
    ) -> EmployeeAssignment:
        employee = self.get_employee(owner, employee_id)

        existing = self.assignments.get_by_workflow(employee.id, data.workflow_id)
        if existing is not None:
            raise EmployeeValidationError(
                "This employee is already assigned to that workflow."
            )

        assignment = self.assignments.create(employee.id, data)
        self._record(
            employee,
            EmployeeActivityKind.ASSIGNED,
            f"{employee.name} was assigned to {data.workflow_name}",
        )
        self.session.commit()
        self.session.refresh(assignment)
        return assignment

    def unassign_work(
        self, owner: User, employee_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> None:
        employee = self.get_employee(owner, employee_id)

        assignment = self.assignments.get_by_id(assignment_id)
        if assignment is None or assignment.employee_id != employee.id:
            raise EmployeeNotFoundError(str(assignment_id))

        name = assignment.workflow_name
        self.assignments.delete(assignment)
        self._record(
            employee,
            EmployeeActivityKind.UNASSIGNED,
            f"{employee.name} was unassigned from {name}",
        )
        self.session.commit()

    def assignment_count(self, employee: Employee) -> int:
        return self.assignments.count_by_employee(employee.id)

    # --- Activity --------------------------------------------------------

    def list_activity(
        self, owner: User, employee_id: uuid.UUID, *, skip: int = 0, limit: int = 100
    ) -> Sequence[EmployeeActivityEvent]:
        employee = self.get_employee(owner, employee_id)
        return self.activity.list_by_employee(employee.id, skip=skip, limit=limit)

    # --- Health ----------------------------------------------------------

    def health(self, owner: User, employee_id: uuid.UUID) -> EmployeeHealthReport:
        return derive_health(self.get_employee(owner, employee_id))

    # --- Internals -------------------------------------------------------

    @staticmethod
    def _now():
        from datetime import datetime, timezone

        return datetime.now(timezone.utc)

    @staticmethod
    def _status_of(employee: Employee) -> EmployeeStatus:
        try:
            return EmployeeStatus(employee.status)
        except ValueError:
            return EmployeeStatus.DRAFT

    @staticmethod
    def _permission_is_satisfied(permission: str, held: set[str]) -> bool:
        from app.services.employee_health import PERMISSION_REQUIRES

        required = PERMISSION_REQUIRES.get(permission)
        return required is None or required.value in held

    def _resolve_status_change(
        self, employee: Employee, data: EmployeeUpdate
    ) -> Optional[EmployeeStatus]:
        """Validate a requested status change, returning it if there is one."""
        if data.status is None:
            return None

        current = self._status_of(employee)
        if data.status == current:
            return None

        if not can_transition(current, data.status):
            raise InvalidStatusTransitionError(
                f"An employee cannot move from {current.value} to {data.status.value}."
            )
        return data.status

    def _apply_scalar_updates(
        self, employee: Employee, data: EmployeeUpdate, supplied: dict
    ) -> None:
        fields = {
            key: getattr(data, key)
            for key in ("name", "role", "description", "language", "personality")
            if key in supplied
        }
        if fields:
            self.employees.update_fields(employee, **fields)

    def _apply_configuration(
        self, employee: Employee, data: EmployeeUpdate, supplied: dict
    ) -> bool:
        """Apply configuration, capabilities and permissions. Reports whether
        anything actually changed, so the history isn't padded with no-ops."""
        changed = False

        settings = {
            key: getattr(data, key).value
            for key in ("autonomy", "tone", "execution_mode", "priority", "accent", "glyph")
            if key in supplied and getattr(data, key) is not None
        }
        if "require_approval" in supplied and data.require_approval is not None:
            settings["require_approval"] = data.require_approval

        if settings:
            self.employees.update_fields(employee, **settings)
            changed = True

        capabilities = (
            [c.value for c in data.capabilities]
            if data.capabilities is not None
            else None
        )
        if capabilities is not None:
            self.employees.replace_capabilities(employee, capabilities)
            changed = True

        if data.permissions is not None:
            held = {g.capability for g in employee.capabilities}
            self._validate_permission_levels(data.permissions, held)
            self.employees.replace_permissions(
                employee,
                {p.permission.value: p.level.value for p in data.permissions},
            )
            changed = True
        elif capabilities is not None:
            # Capabilities were replaced without new permissions. Anything that
            # depended on a capability just revoked has to drop to BLOCKED, or
            # the employee would be left holding a permission it cannot
            # exercise — the same rule ``remove_capability`` enforces, applied
            # to the bulk path so both routes leave a consistent state.
            self._block_unsupported_permissions(employee)

        return changed

    def _block_unsupported_permissions(self, employee: Employee) -> None:
        """Force every permission without its capability down to BLOCKED."""
        held = {g.capability for g in employee.capabilities}
        levels = {
            g.permission: (
                g.level
                if self._permission_is_satisfied(g.permission, held)
                else PermissionLevel.BLOCKED.value
            )
            for g in employee.permissions
        }
        if levels:
            self.employees.replace_permissions(employee, levels)

    def _validate_permissions(self, capabilities, permissions) -> None:
        """A permission may only be granted if its capability is held."""
        held = {c.value for c in capabilities}
        self._validate_permission_levels(permissions, held)

    def _validate_permission_levels(self, permissions, held: set[str]) -> None:
        for entry in permissions:
            if entry.level is PermissionLevel.BLOCKED:
                continue
            if not self._permission_is_satisfied(entry.permission.value, held):
                from app.services.employee_health import PERMISSION_REQUIRES

                required = PERMISSION_REQUIRES[entry.permission.value]
                raise EmployeeValidationError(
                    f"Permission '{entry.permission.value}' requires the "
                    f"'{required.value}' capability, which is not granted."
                )

    def _record(
        self, employee: Employee, kind: EmployeeActivityKind, summary: str
    ) -> None:
        """Write one history event. Called only where a change really happened."""
        self.activity.append(employee.id, kind=kind.value, summary=summary)

