"""Employee domain tests (Sprint 18.2A).

Three layers, none of which touch a database or network:

* ``...ServiceTests`` run the real :class:`EmployeeService` against in-memory
  fake repositories, so lifecycle rules, configuration, capability/permission
  consistency and activity recording are exercised for real.
* ``EmployeeAPITests`` drive the endpoints through ``TestClient`` with the
  service mocked, covering HTTP concerns — status codes, error mapping, and
  ownership.
* ``LifecycleTests`` / ``HealthTests`` cover the pure policy modules directly.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_employees
"""

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_employee_service
from app.main import app
from app.models.employee import Employee
from app.models.employee_activity import EmployeeActivityEvent
from app.models.employee_assignment import EmployeeAssignment
from app.models.employee_capability import EmployeeCapabilityGrant
from app.models.employee_permission import EmployeePermissionGrant
from app.schemas.employee import (
    EmployeeAssignmentCreate,
    EmployeeCreate,
    EmployeePermissionInput,
    EmployeeUpdate,
)
from app.services.employee_health import derive_health
from app.services.employee_lifecycle import (
    RESTORABLE_STATUSES,
    allowed_transitions,
    can_transition,
)
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeNotFoundError,
    EmployeeService,
    EmployeeValidationError,
    InvalidStatusTransitionError,
)
from app.utils.constants import (
    AutonomyLevel,
    EmployeeAccent,
    EmployeeActivityKind,
    EmployeeCapability,
    EmployeeGlyph,
    EmployeeHealth,
    EmployeePermission,
    EmployeePriority,
    EmployeeStatus,
    EmployeeTone,
    ExecutionMode,
    PermissionLevel,
)


# --- Test doubles --------------------------------------------------------


class FakeSession:
    """Minimal unit-of-work stand-in that records commits."""

    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, instance) -> None:  # pragma: no cover - no-op
        return None


class FakeEmployeeRepository:
    """In-memory mirror of :class:`EmployeeRepository`'s public surface."""

    def __init__(self, session) -> None:
        self.session = session
        self.rows: dict[uuid.UUID, Employee] = {}

    # -- reads
    def get_by_id(self, employee_id, *, include_deleted=False):
        employee = self.rows.get(employee_id)
        if employee is None:
            return None
        if employee.deleted_at is not None and not include_deleted:
            return None
        return employee

    def list_by_user(self, user_id, *, skip=0, limit=100, include_deleted=False):
        return [
            e
            for e in self.rows.values()
            if e.user_id == user_id and (include_deleted or e.deleted_at is None)
        ]

    def count_by_name(self, user_id, name, *, exclude_id=None):
        return len(
            [
                e
                for e in self.rows.values()
                if e.user_id == user_id
                and e.name == name
                and e.deleted_at is None
                and e.id != exclude_id
            ]
        )

    # -- writes
    def create(self, user_id, data):
        employee = Employee(
            id=uuid.uuid4(),
            user_id=user_id,
            name=data.name,
            role=data.role,
            description=data.description,
            language=data.language,
            personality=data.personality,
            status=EmployeeStatus.DRAFT.value,
            autonomy=data.autonomy.value,
            tone=data.tone.value,
            execution_mode=data.execution_mode.value,
            priority=data.priority.value,
            require_approval=data.require_approval,
            accent=data.accent.value,
            glyph=data.glyph.value,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        employee.capabilities = []
        employee.permissions = []
        self.rows[employee.id] = employee
        return employee

    def update_fields(self, employee, **fields):
        for key, value in fields.items():
            setattr(employee, key, value)
        return employee

    def set_status(self, employee, status, *, archived_at=None):
        employee.status = status
        employee.archived_at = archived_at
        return employee

    def soft_delete(self, employee):
        employee.deleted_at = datetime.now(timezone.utc)
        return employee

    def delete(self, employee):
        self.rows.pop(employee.id, None)

    # -- capabilities
    def replace_capabilities(self, employee, capabilities):
        employee.capabilities = [
            EmployeeCapabilityGrant(employee_id=employee.id, capability=c)
            for c in sorted(set(capabilities))
        ]
        return employee

    def add_capability(self, employee, capability):
        if all(g.capability != capability for g in employee.capabilities):
            employee.capabilities.append(
                EmployeeCapabilityGrant(employee_id=employee.id, capability=capability)
            )
        return employee

    def remove_capability(self, employee, capability):
        employee.capabilities = [
            g for g in employee.capabilities if g.capability != capability
        ]
        return employee

    # -- permissions
    def replace_permissions(self, employee, permissions):
        employee.permissions = [
            EmployeePermissionGrant(
                employee_id=employee.id, permission=name, level=level
            )
            for name, level in sorted(permissions.items())
        ]
        return employee


class FakeActivityRepository:
    def __init__(self, session) -> None:
        self.session = session
        self.events: dict[uuid.UUID, list[EmployeeActivityEvent]] = {}

    def list_by_employee(self, employee_id, *, skip=0, limit=100):
        events = sorted(
            self.events.get(employee_id, []), key=lambda e: e.sequence, reverse=True
        )
        return events[skip : skip + limit]

    def next_sequence(self, employee_id):
        events = self.events.get(employee_id, [])
        return max((e.sequence for e in events), default=0) + 1

    def append(self, employee_id, *, kind, summary):
        event = EmployeeActivityEvent(
            id=uuid.uuid4(),
            employee_id=employee_id,
            kind=kind,
            summary=summary,
            sequence=self.next_sequence(employee_id),
            created_at=datetime.now(timezone.utc),
        )
        self.events.setdefault(employee_id, []).append(event)
        return event


class FakeAssignmentRepository:
    def __init__(self, session) -> None:
        self.session = session
        self.rows: dict[uuid.UUID, EmployeeAssignment] = {}

    def list_by_employee(self, employee_id):
        return [a for a in self.rows.values() if a.employee_id == employee_id]

    def count_by_employee(self, employee_id):
        return len(self.list_by_employee(employee_id))

    def get_by_id(self, assignment_id):
        return self.rows.get(assignment_id)

    def get_by_workflow(self, employee_id, workflow_id):
        return next(
            (
                a
                for a in self.rows.values()
                if a.employee_id == employee_id and a.workflow_id == workflow_id
            ),
            None,
        )

    def create(self, employee_id, data):
        assignment = EmployeeAssignment(
            id=uuid.uuid4(),
            employee_id=employee_id,
            workflow_id=data.workflow_id,
            workflow_name=data.workflow_name,
            priority=data.priority.value,
            execution_mode=data.execution_mode.value,
            dependency_summary=data.dependency_summary,
            created_at=datetime.now(timezone.utc),
        )
        self.rows[assignment.id] = assignment
        return assignment

    def delete(self, assignment):
        self.rows.pop(assignment.id, None)


class EmployeeServiceTestBase(unittest.TestCase):
    """Builds a real EmployeeService over in-memory repositories."""

    def setUp(self) -> None:
        self.session = FakeSession()
        for name, fake in (
            ("EmployeeRepository", FakeEmployeeRepository),
            ("EmployeeActivityRepository", FakeActivityRepository),
            ("EmployeeAssignmentRepository", FakeAssignmentRepository),
        ):
            patcher = patch(f"app.services.employee_service.{name}", fake)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.service = EmployeeService(self.session)
        self.owner = MagicMock(name="User")
        self.owner.id = uuid.uuid4()
        self.other = MagicMock(name="OtherUser")
        self.other.id = uuid.uuid4()

    def create(self, **overrides) -> Employee:
        payload = {"name": "Atlas", "role": "RESEARCH_ASSISTANT", **overrides}
        return self.service.create_employee(self.owner, EmployeeCreate(**payload))

    def kinds(self, employee) -> list[str]:
        return [e.kind for e in self.service.activity.events.get(employee.id, [])]


# --- Creation & configuration -------------------------------------------


class CreationTests(EmployeeServiceTestBase):
    def test_create_uses_conservative_defaults(self):
        employee = self.create()
        self.assertEqual(employee.status, EmployeeStatus.DRAFT.value)
        self.assertEqual(employee.autonomy, AutonomyLevel.BALANCED.value)
        self.assertEqual(employee.tone, EmployeeTone.PROFESSIONAL.value)
        self.assertEqual(employee.priority, EmployeePriority.MEDIUM.value)
        self.assertTrue(employee.require_approval)

    def test_create_persists_supplied_configuration(self):
        employee = self.create(
            autonomy=AutonomyLevel.AUTONOMOUS,
            tone=EmployeeTone.CONCISE,
            execution_mode=ExecutionMode.PARALLEL,
            priority=EmployeePriority.URGENT,
            require_approval=False,
            accent=EmployeeAccent.VIOLET,
            glyph=EmployeeGlyph.BRAIN,
        )
        self.assertEqual(employee.autonomy, "autonomous")
        self.assertEqual(employee.tone, "concise")
        self.assertEqual(employee.execution_mode, "parallel")
        self.assertEqual(employee.priority, "urgent")
        self.assertFalse(employee.require_approval)
        self.assertEqual(employee.accent, "violet")
        self.assertEqual(employee.glyph, "brain")

    def test_create_persists_capabilities(self):
        employee = self.create(
            capabilities=[EmployeeCapability.BROWSER, EmployeeCapability.MEMORY]
        )
        held = {g.capability for g in employee.capabilities}
        self.assertEqual(held, {"browser", "memory"})

    def test_create_persists_permissions(self):
        employee = self.create(
            capabilities=[EmployeeCapability.MEMORY],
            permissions=[
                EmployeePermissionInput(
                    permission=EmployeePermission.READ_MEMORY,
                    level=PermissionLevel.ALLOWED,
                )
            ],
        )
        self.assertEqual(len(employee.permissions), 1)
        self.assertEqual(employee.permissions[0].level, "allowed")

    def test_permission_without_its_capability_is_rejected(self):
        with self.assertRaises(EmployeeValidationError):
            self.create(
                capabilities=[],
                permissions=[
                    EmployeePermissionInput(
                        permission=EmployeePermission.SEND_EMAIL,
                        level=PermissionLevel.ALLOWED,
                    )
                ],
            )

    def test_blocked_permission_needs_no_capability(self):
        employee = self.create(
            capabilities=[],
            permissions=[
                EmployeePermissionInput(
                    permission=EmployeePermission.SEND_EMAIL,
                    level=PermissionLevel.BLOCKED,
                )
            ],
        )
        self.assertEqual(employee.permissions[0].level, "blocked")

    def test_create_records_one_event(self):
        employee = self.create()
        self.assertEqual(self.kinds(employee), [EmployeeActivityKind.CREATED.value])


# --- Update --------------------------------------------------------------


class UpdateTests(EmployeeServiceTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.employee = self.create()

    def test_update_changes_only_supplied_fields(self):
        original_role = self.employee.role
        updated = self.service.update_employee(
            self.owner, self.employee.id, EmployeeUpdate(name="Atlas II")
        )
        self.assertEqual(updated.name, "Atlas II")
        self.assertEqual(updated.role, original_role)

    def test_update_persists_configuration(self):
        updated = self.service.update_employee(
            self.owner,
            self.employee.id,
            EmployeeUpdate(
                autonomy=AutonomyLevel.ASK,
                tone=EmployeeTone.FRIENDLY,
                priority=EmployeePriority.HIGH,
                require_approval=False,
                accent=EmployeeAccent.ROSE,
                glyph=EmployeeGlyph.PEN,
            ),
        )
        self.assertEqual(updated.autonomy, "ask")
        self.assertEqual(updated.tone, "friendly")
        self.assertEqual(updated.priority, "high")
        self.assertFalse(updated.require_approval)
        self.assertEqual(updated.accent, "rose")
        self.assertEqual(updated.glyph, "pen")

    def test_update_replaces_capabilities(self):
        self.service.update_employee(
            self.owner,
            self.employee.id,
            EmployeeUpdate(capabilities=[EmployeeCapability.PYTHON]),
        )
        self.assertEqual(
            {g.capability for g in self.employee.capabilities}, {"python"}
        )

    def test_empty_capability_list_clears_grants(self):
        self.service.update_employee(
            self.owner,
            self.employee.id,
            EmployeeUpdate(capabilities=[EmployeeCapability.PYTHON]),
        )
        self.service.update_employee(
            self.owner, self.employee.id, EmployeeUpdate(capabilities=[])
        )
        self.assertEqual(self.employee.capabilities, [])

    def test_omitting_capabilities_leaves_them_alone(self):
        self.service.update_employee(
            self.owner,
            self.employee.id,
            EmployeeUpdate(capabilities=[EmployeeCapability.PYTHON]),
        )
        self.service.update_employee(
            self.owner, self.employee.id, EmployeeUpdate(name="Renamed")
        )
        self.assertEqual(
            {g.capability for g in self.employee.capabilities}, {"python"}
        )

    def test_permission_without_capability_rejected_on_update(self):
        with self.assertRaises(EmployeeValidationError):
            self.service.update_employee(
                self.owner,
                self.employee.id,
                EmployeeUpdate(
                    capabilities=[],
                    permissions=[
                        EmployeePermissionInput(
                            permission=EmployeePermission.RUN_CODE,
                            level=PermissionLevel.ALLOWED,
                        )
                    ],
                ),
            )

    def test_update_records_the_right_events(self):
        self.service.update_employee(
            self.owner, self.employee.id, EmployeeUpdate(name="Renamed")
        )
        self.assertIn(EmployeeActivityKind.UPDATED.value, self.kinds(self.employee))

        self.service.update_employee(
            self.owner, self.employee.id, EmployeeUpdate(tone=EmployeeTone.CONCISE)
        )
        self.assertIn(
            EmployeeActivityKind.CONFIGURATION_CHANGED.value, self.kinds(self.employee)
        )

    def test_no_op_update_records_nothing(self):
        before = len(self.kinds(self.employee))
        self.service.update_employee(self.owner, self.employee.id, EmployeeUpdate())
        self.assertEqual(len(self.kinds(self.employee)), before)

    def test_update_rejected_for_another_user(self):
        with self.assertRaises(EmployeeAccessDeniedError):
            self.service.update_employee(
                self.other, self.employee.id, EmployeeUpdate(name="Hijacked")
            )


# --- Lifecycle -----------------------------------------------------------


class LifecycleServiceTests(EmployeeServiceTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.employee = self.create()

    def test_status_transition_is_recorded(self):
        updated = self.service.update_employee(
            self.owner, self.employee.id, EmployeeUpdate(status=EmployeeStatus.READY)
        )
        self.assertEqual(updated.status, "ready")
        self.assertIn(
            EmployeeActivityKind.STATUS_CHANGED.value, self.kinds(self.employee)
        )

    def test_illegal_transition_is_rejected(self):
        # draft -> active is not permitted; an employee becomes ready first.
        with self.assertRaises(InvalidStatusTransitionError):
            self.service.update_employee(
                self.owner,
                self.employee.id,
                EmployeeUpdate(status=EmployeeStatus.ACTIVE),
            )
        self.assertEqual(self.employee.status, "draft")

    def test_setting_the_same_status_is_not_an_error(self):
        updated = self.service.update_employee(
            self.owner, self.employee.id, EmployeeUpdate(status=EmployeeStatus.DRAFT)
        )
        self.assertEqual(updated.status, "draft")

    def test_archive_sets_status_and_stamp(self):
        archived = self.service.archive_employee(self.owner, self.employee.id)
        self.assertEqual(archived.status, EmployeeStatus.ARCHIVED.value)
        self.assertIsNotNone(archived.archived_at)
        self.assertIn(EmployeeActivityKind.ARCHIVED.value, self.kinds(self.employee))

    def test_archiving_twice_is_idempotent(self):
        self.service.archive_employee(self.owner, self.employee.id)
        again = self.service.archive_employee(self.owner, self.employee.id)
        self.assertEqual(again.status, EmployeeStatus.ARCHIVED.value)

    def test_restore_returns_to_the_bench(self):
        self.service.archive_employee(self.owner, self.employee.id)
        restored = self.service.restore_employee(self.owner, self.employee.id)
        self.assertEqual(restored.status, EmployeeStatus.DRAFT.value)
        self.assertIsNone(restored.archived_at)
        self.assertIn(EmployeeActivityKind.RESTORED.value, self.kinds(self.employee))

    def test_restore_can_target_ready(self):
        self.service.archive_employee(self.owner, self.employee.id)
        restored = self.service.restore_employee(
            self.owner, self.employee.id, EmployeeStatus.READY
        )
        self.assertEqual(restored.status, "ready")

    def test_restore_cannot_go_straight_into_service(self):
        self.service.archive_employee(self.owner, self.employee.id)
        with self.assertRaises(InvalidStatusTransitionError):
            self.service.restore_employee(
                self.owner, self.employee.id, EmployeeStatus.ACTIVE
            )

    def test_restoring_a_live_employee_is_rejected(self):
        with self.assertRaises(InvalidStatusTransitionError):
            self.service.restore_employee(self.owner, self.employee.id)

    def test_full_path_to_active(self):
        self.service.update_employee(
            self.owner, self.employee.id, EmployeeUpdate(status=EmployeeStatus.READY)
        )
        updated = self.service.update_employee(
            self.owner, self.employee.id, EmployeeUpdate(status=EmployeeStatus.ACTIVE)
        )
        self.assertEqual(updated.status, "active")
        paused = self.service.update_employee(
            self.owner, self.employee.id, EmployeeUpdate(status=EmployeeStatus.PAUSED)
        )
        self.assertEqual(paused.status, "paused")


class SoftDeleteTests(EmployeeServiceTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.employee = self.create()

    def test_delete_hides_the_employee(self):
        self.service.delete_employee(self.owner, self.employee.id)
        with self.assertRaises(EmployeeNotFoundError):
            self.service.get_employee(self.owner, self.employee.id)

    def test_deleted_employee_leaves_the_list(self):
        self.service.delete_employee(self.owner, self.employee.id)
        self.assertEqual(self.service.list_employees(self.owner), [])

    def test_delete_preserves_the_row(self):
        """A soft delete must not destroy the employee or what it owns."""
        self.service.delete_employee(self.owner, self.employee.id)
        stored = self.service.employees.rows[self.employee.id]
        self.assertIsNotNone(stored)
        self.assertIsNotNone(stored.deleted_at)

    def test_delete_rejected_for_another_user(self):
        with self.assertRaises(EmployeeAccessDeniedError):
            self.service.delete_employee(self.other, self.employee.id)


# --- Capabilities & permissions -----------------------------------------


class CapabilityTests(EmployeeServiceTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.employee = self.create(capabilities=[EmployeeCapability.MEMORY])

    def test_list_capabilities(self):
        held = self.service.list_capabilities(self.owner, self.employee.id)
        self.assertEqual(held, [EmployeeCapability.MEMORY])

    def test_add_capability(self):
        self.service.add_capability(
            self.owner, self.employee.id, EmployeeCapability.BROWSER
        )
        held = {g.capability for g in self.employee.capabilities}
        self.assertEqual(held, {"memory", "browser"})

    def test_adding_twice_is_idempotent(self):
        self.service.add_capability(
            self.owner, self.employee.id, EmployeeCapability.MEMORY
        )
        self.assertEqual(len(self.employee.capabilities), 1)

    def test_remove_capability(self):
        self.service.remove_capability(
            self.owner, self.employee.id, EmployeeCapability.MEMORY
        )
        self.assertEqual(self.employee.capabilities, [])

    def test_revoking_a_capability_blocks_dependent_permissions(self):
        """An employee must never keep a permission it can no longer exercise."""
        self.service.update_employee(
            self.owner,
            self.employee.id,
            EmployeeUpdate(
                capabilities=[EmployeeCapability.MEMORY],
                permissions=[
                    EmployeePermissionInput(
                        permission=EmployeePermission.READ_MEMORY,
                        level=PermissionLevel.ALLOWED,
                    )
                ],
            ),
        )
        self.service.remove_capability(
            self.owner, self.employee.id, EmployeeCapability.MEMORY
        )
        self.assertEqual(self.employee.permissions[0].level, "blocked")

    def test_bulk_capability_replace_also_blocks_orphaned_permissions(self):
        """The PATCH path must leave the same consistent state as a revoke."""
        self.service.update_employee(
            self.owner,
            self.employee.id,
            EmployeeUpdate(
                capabilities=[EmployeeCapability.MEMORY],
                permissions=[
                    EmployeePermissionInput(
                        permission=EmployeePermission.READ_MEMORY,
                        level=PermissionLevel.ALLOWED,
                    )
                ],
            ),
        )
        # Replace capabilities without sending permissions.
        self.service.update_employee(
            self.owner,
            self.employee.id,
            EmployeeUpdate(capabilities=[EmployeeCapability.BROWSER]),
        )
        levels = {g.permission: g.level for g in self.employee.permissions}
        self.assertEqual(levels["read_memory"], "blocked")

    def test_bulk_replace_keeps_still_supported_permissions(self):
        self.service.update_employee(
            self.owner,
            self.employee.id,
            EmployeeUpdate(
                capabilities=[EmployeeCapability.MEMORY, EmployeeCapability.BROWSER],
                permissions=[
                    EmployeePermissionInput(
                        permission=EmployeePermission.BROWSE_WEB,
                        level=PermissionLevel.ALLOWED,
                    )
                ],
            ),
        )
        self.service.update_employee(
            self.owner,
            self.employee.id,
            EmployeeUpdate(capabilities=[EmployeeCapability.BROWSER]),
        )
        levels = {g.permission: g.level for g in self.employee.permissions}
        self.assertEqual(levels["browse_web"], "allowed")

    def test_capability_change_is_recorded(self):
        self.service.add_capability(
            self.owner, self.employee.id, EmployeeCapability.BROWSER
        )
        self.assertIn(
            EmployeeActivityKind.CONFIGURATION_CHANGED.value, self.kinds(self.employee)
        )

    def test_capabilities_rejected_for_another_user(self):
        with self.assertRaises(EmployeeAccessDeniedError):
            self.service.list_capabilities(self.other, self.employee.id)


# --- Assignments ---------------------------------------------------------


class AssignmentTests(EmployeeServiceTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.employee = self.create()

    def payload(self, workflow_id="wf_1", name="Weekly report"):
        return EmployeeAssignmentCreate(
            workflow_id=workflow_id,
            workflow_name=name,
            priority=EmployeePriority.HIGH,
            execution_mode=ExecutionMode.SEQUENTIAL,
            dependency_summary="Waits for the data export.",
        )

    def test_assign_and_list(self):
        self.service.assign_work(self.owner, self.employee.id, self.payload())
        assignments = self.service.list_assignments(self.owner, self.employee.id)
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].workflow_name, "Weekly report")
        self.assertEqual(assignments[0].priority, "high")

    def test_assignment_is_recorded(self):
        self.service.assign_work(self.owner, self.employee.id, self.payload())
        self.assertIn(EmployeeActivityKind.ASSIGNED.value, self.kinds(self.employee))

    def test_duplicate_assignment_rejected(self):
        self.service.assign_work(self.owner, self.employee.id, self.payload())
        with self.assertRaises(EmployeeValidationError):
            self.service.assign_work(self.owner, self.employee.id, self.payload())

    def test_unassign(self):
        assignment = self.service.assign_work(
            self.owner, self.employee.id, self.payload()
        )
        self.service.unassign_work(self.owner, self.employee.id, assignment.id)
        self.assertEqual(self.service.list_assignments(self.owner, self.employee.id), [])
        self.assertIn(EmployeeActivityKind.UNASSIGNED.value, self.kinds(self.employee))

    def test_unassigning_another_employees_work_is_rejected(self):
        other_employee = self.create(name="Nova")
        assignment = self.service.assign_work(
            self.owner, other_employee.id, self.payload()
        )
        with self.assertRaises(EmployeeNotFoundError):
            self.service.unassign_work(self.owner, self.employee.id, assignment.id)

    def test_assignment_count(self):
        self.service.assign_work(self.owner, self.employee.id, self.payload())
        self.service.assign_work(
            self.owner, self.employee.id, self.payload("wf_2", "Backlog triage")
        )
        self.assertEqual(self.service.assignment_count(self.employee), 2)

    def test_assignments_rejected_for_another_user(self):
        with self.assertRaises(EmployeeAccessDeniedError):
            self.service.list_assignments(self.other, self.employee.id)


# --- Activity ------------------------------------------------------------


class ActivityTests(EmployeeServiceTestBase):
    def test_history_is_newest_first(self):
        employee = self.create()
        self.service.update_employee(
            self.owner, employee.id, EmployeeUpdate(name="Renamed")
        )
        events = self.service.list_activity(self.owner, employee.id)
        self.assertEqual(events[0].kind, EmployeeActivityKind.UPDATED.value)
        self.assertEqual(events[-1].kind, EmployeeActivityKind.CREATED.value)

    def test_sequences_are_unique_and_increasing(self):
        employee = self.create()
        for name in ("A", "B", "C"):
            self.service.update_employee(
                self.owner, employee.id, EmployeeUpdate(name=name)
            )
        sequences = [e.sequence for e in self.service.list_activity(self.owner, employee.id)]
        self.assertEqual(sorted(sequences, reverse=True), sequences)
        self.assertEqual(len(set(sequences)), len(sequences))

    def test_activity_is_never_fabricated(self):
        """A read must not create history."""
        employee = self.create()
        self.service.list_activity(self.owner, employee.id)
        self.service.list_activity(self.owner, employee.id)
        self.assertEqual(len(self.kinds(employee)), 1)

    def test_activity_rejected_for_another_user(self):
        employee = self.create()
        with self.assertRaises(EmployeeAccessDeniedError):
            self.service.list_activity(self.other, employee.id)


# --- Lifecycle policy ----------------------------------------------------


class LifecycleTests(unittest.TestCase):
    def test_draft_cannot_jump_to_active(self):
        self.assertFalse(
            can_transition(EmployeeStatus.DRAFT, EmployeeStatus.ACTIVE)
        )

    def test_draft_can_become_ready(self):
        self.assertTrue(can_transition(EmployeeStatus.DRAFT, EmployeeStatus.READY))

    def test_ready_can_activate(self):
        self.assertTrue(can_transition(EmployeeStatus.READY, EmployeeStatus.ACTIVE))

    def test_active_can_pause_and_resume(self):
        self.assertTrue(can_transition(EmployeeStatus.ACTIVE, EmployeeStatus.PAUSED))
        self.assertTrue(can_transition(EmployeeStatus.PAUSED, EmployeeStatus.ACTIVE))

    def test_anything_live_can_archive(self):
        for status in (
            EmployeeStatus.DRAFT,
            EmployeeStatus.READY,
            EmployeeStatus.ACTIVE,
            EmployeeStatus.PAUSED,
            EmployeeStatus.ERROR,
        ):
            self.assertTrue(can_transition(status, EmployeeStatus.ARCHIVED), status)

    def test_archived_is_terminal_without_a_restore(self):
        self.assertEqual(allowed_transitions(EmployeeStatus.ARCHIVED), frozenset())

    def test_staying_put_is_allowed(self):
        for status in EmployeeStatus:
            self.assertTrue(can_transition(status, status), status)

    def test_nothing_transitions_into_error(self):
        for status in EmployeeStatus:
            if status is EmployeeStatus.ERROR:
                continue
            self.assertNotIn(EmployeeStatus.ERROR, allowed_transitions(status))

    def test_restore_targets_are_off_duty_states(self):
        self.assertEqual(
            RESTORABLE_STATUSES, frozenset({EmployeeStatus.DRAFT, EmployeeStatus.READY})
        )


# --- Health --------------------------------------------------------------


class HealthTests(unittest.TestCase):
    def build(self, *, status, capabilities=(), permissions=()):
        employee = Employee(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="Atlas",
            role="RESEARCH_ASSISTANT",
            language="en",
            status=status.value,
        )
        employee.capabilities = [
            EmployeeCapabilityGrant(employee_id=employee.id, capability=c)
            for c in capabilities
        ]
        employee.permissions = [
            EmployeePermissionGrant(
                employee_id=employee.id, permission=name, level=level
            )
            for name, level in permissions
        ]
        return employee

    def test_draft_is_unknown(self):
        report = derive_health(self.build(status=EmployeeStatus.DRAFT))
        self.assertEqual(report.state, EmployeeHealth.UNKNOWN)
        self.assertTrue(report.reasons)

    def test_archived_is_unknown(self):
        report = derive_health(self.build(status=EmployeeStatus.ARCHIVED))
        self.assertEqual(report.state, EmployeeHealth.UNKNOWN)

    def test_error_is_unhealthy(self):
        report = derive_health(self.build(status=EmployeeStatus.ERROR))
        self.assertEqual(report.state, EmployeeHealth.UNHEALTHY)

    def test_active_without_capabilities_is_degraded(self):
        report = derive_health(self.build(status=EmployeeStatus.ACTIVE))
        self.assertEqual(report.state, EmployeeHealth.DEGRADED)
        self.assertIn("No capabilities", report.reasons[0])

    def test_active_with_capabilities_is_healthy(self):
        report = derive_health(
            self.build(status=EmployeeStatus.ACTIVE, capabilities=["browser"])
        )
        self.assertEqual(report.state, EmployeeHealth.HEALTHY)

    def test_permission_without_capability_is_degraded(self):
        report = derive_health(
            self.build(
                status=EmployeeStatus.ACTIVE,
                capabilities=["browser"],
                permissions=[("send_email", "allowed")],
            )
        )
        self.assertEqual(report.state, EmployeeHealth.DEGRADED)
        self.assertTrue(any("send_email" in r for r in report.reasons))

    def test_blocked_permission_does_not_degrade(self):
        report = derive_health(
            self.build(
                status=EmployeeStatus.ACTIVE,
                capabilities=["browser"],
                permissions=[("send_email", "blocked")],
            )
        )
        self.assertEqual(report.state, EmployeeHealth.HEALTHY)

    def test_health_is_deterministic(self):
        employee = self.build(status=EmployeeStatus.ACTIVE, capabilities=["browser"])
        self.assertEqual(derive_health(employee).state, derive_health(employee).state)

    def test_unrecognised_status_does_not_crash(self):
        employee = self.build(status=EmployeeStatus.DRAFT)
        employee.status = "something_new"
        self.assertEqual(derive_health(employee).state, EmployeeHealth.UNKNOWN)


# --- Backward compatibility ---------------------------------------------


class LegacyEmployeeTests(EmployeeServiceTestBase):
    """A pre-Sprint-18.2A employee must keep working after the migration."""

    def legacy(self) -> Employee:
        employee = self.service.employees.create(
            self.owner.id, EmployeeCreate(name="Legacy", role="Assistant")
        )
        # What the migration leaves behind: draft status, default configuration,
        # no capabilities, no permissions, no history.
        employee.capabilities = []
        employee.permissions = []
        return employee

    def test_legacy_employee_is_readable(self):
        employee = self.legacy()
        self.assertEqual(
            self.service.get_employee(self.owner, employee.id).id, employee.id
        )

    def test_legacy_employee_is_updatable(self):
        employee = self.legacy()
        updated = self.service.update_employee(
            self.owner, employee.id, EmployeeUpdate(name="Modernised")
        )
        self.assertEqual(updated.name, "Modernised")

    def test_legacy_employee_can_be_archived(self):
        employee = self.legacy()
        archived = self.service.archive_employee(self.owner, employee.id)
        self.assertEqual(archived.status, EmployeeStatus.ARCHIVED.value)

    def test_legacy_employee_has_empty_history(self):
        employee = self.legacy()
        self.assertEqual(self.service.list_activity(self.owner, employee.id), [])

    def test_legacy_employee_health_is_unknown(self):
        employee = self.legacy()
        self.assertEqual(derive_health(employee).state, EmployeeHealth.UNKNOWN)


# --- API layer -----------------------------------------------------------


class EmployeeAPITests(unittest.TestCase):
    """HTTP concerns with the service mocked out."""

    def setUp(self) -> None:
        self.service = MagicMock(spec=EmployeeService)
        self.service.assignment_count.return_value = 0
        self.user = MagicMock(name="User")
        self.user.id = uuid.uuid4()

        self.employee = Employee(
            id=uuid.uuid4(),
            user_id=self.user.id,
            name="Atlas",
            role="RESEARCH_ASSISTANT",
            description="Reads things.",
            language="en",
            personality="Careful.",
            status=EmployeeStatus.DRAFT.value,
            autonomy=AutonomyLevel.BALANCED.value,
            tone=EmployeeTone.PROFESSIONAL.value,
            execution_mode=ExecutionMode.SEQUENTIAL.value,
            priority=EmployeePriority.MEDIUM.value,
            require_approval=True,
            accent=EmployeeAccent.SLATE.value,
            glyph=EmployeeGlyph.BOT.value,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.employee.capabilities = []
        self.employee.permissions = []

        app.dependency_overrides[get_employee_service] = lambda: self.service
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    @property
    def base(self) -> str:
        return f"/api/v1/employees/{self.employee.id}"

    # -- update
    def test_patch_returns_the_updated_employee(self):
        self.service.update_employee.return_value = self.employee
        response = self.client.patch(self.base, json={"name": "Atlas II"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Atlas")

    def test_patch_maps_not_found_to_404(self):
        self.service.update_employee.side_effect = EmployeeNotFoundError()
        response = self.client.patch(self.base, json={"name": "x"})
        self.assertEqual(response.status_code, 404)

    def test_patch_maps_access_denied_to_403(self):
        self.service.update_employee.side_effect = EmployeeAccessDeniedError()
        response = self.client.patch(self.base, json={"name": "x"})
        self.assertEqual(response.status_code, 403)

    def test_patch_maps_bad_transition_to_409(self):
        self.service.update_employee.side_effect = InvalidStatusTransitionError("no")
        response = self.client.patch(self.base, json={"status": "active"})
        self.assertEqual(response.status_code, 409)

    def test_patch_maps_validation_error_to_422(self):
        self.service.update_employee.side_effect = EmployeeValidationError("nope")
        response = self.client.patch(self.base, json={"capabilities": []})
        self.assertEqual(response.status_code, 422)

    def test_patch_rejects_an_unknown_status(self):
        response = self.client.patch(self.base, json={"status": "sleeping"})
        self.assertEqual(response.status_code, 422)

    def test_patch_rejects_an_unknown_capability(self):
        response = self.client.patch(self.base, json={"capabilities": ["telepathy"]})
        self.assertEqual(response.status_code, 422)

    # -- delete / archive / restore
    def test_delete_returns_204(self):
        response = self.client.delete(self.base)
        self.assertEqual(response.status_code, 204)
        self.service.delete_employee.assert_called_once()

    def test_archive_returns_the_employee(self):
        self.service.archive_employee.return_value = self.employee
        response = self.client.post(f"{self.base}/archive")
        self.assertEqual(response.status_code, 200)

    def test_restore_returns_the_employee(self):
        self.service.restore_employee.return_value = self.employee
        response = self.client.post(f"{self.base}/restore", json={"status": "ready"})
        self.assertEqual(response.status_code, 200)

    def test_restore_rejects_an_unknown_status(self):
        response = self.client.post(f"{self.base}/restore", json={"status": "flying"})
        self.assertEqual(response.status_code, 422)

    # -- response shape
    def test_response_flattens_grant_rows(self):
        """The ORM stores grants as rows; the wire contract exposes values.

        Validating the employee by attribute would hand pydantic the grant
        objects instead, which is exactly the shape mismatch this guards.
        """
        self.employee.capabilities = [
            EmployeeCapabilityGrant(
                employee_id=self.employee.id, capability="browser"
            ),
            EmployeeCapabilityGrant(
                employee_id=self.employee.id, capability="memory"
            ),
        ]
        self.employee.permissions = [
            EmployeePermissionGrant(
                employee_id=self.employee.id,
                permission="read_memory",
                level="allowed",
            )
        ]
        self.service.get_employee.return_value = self.employee

        response = self.client.get(self.base)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(sorted(body["capabilities"]), ["browser", "memory"])
        self.assertEqual(body["permissions"][0]["permission"], "read_memory")
        self.assertEqual(body["permissions"][0]["level"], "allowed")

    def test_list_flattens_grant_rows(self):
        self.employee.capabilities = [
            EmployeeCapabilityGrant(employee_id=self.employee.id, capability="python")
        ]
        self.service.list_employees.return_value = [self.employee]
        body = self.client.get("/api/v1/employees").json()
        self.assertEqual(body[0]["capabilities"], ["python"])

    def test_response_carries_the_configuration(self):
        self.service.get_employee.return_value = self.employee
        body = self.client.get(self.base).json()
        for key in (
            "autonomy",
            "tone",
            "execution_mode",
            "priority",
            "require_approval",
            "accent",
            "glyph",
            "health",
            "capabilities",
            "permissions",
            "assignment_count",
            "updated_at",
            "archived_at",
        ):
            self.assertIn(key, body)

    def test_response_keeps_the_original_fields(self):
        """Sprint 18.2 consumers must still find everything they read."""
        self.service.get_employee.return_value = self.employee
        body = self.client.get(self.base).json()
        for key in (
            "id",
            "user_id",
            "name",
            "role",
            "description",
            "language",
            "personality",
            "status",
            "created_at",
        ):
            self.assertIn(key, body)

    def test_health_is_derived_not_stored(self):
        self.service.get_employee.return_value = self.employee
        body = self.client.get(self.base).json()
        # A draft has never been in service, so nothing is known about it.
        self.assertEqual(body["health"], EmployeeHealth.UNKNOWN.value)

    # -- activity
    def test_activity_returns_events(self):
        event = EmployeeActivityEvent(
            id=uuid.uuid4(),
            employee_id=self.employee.id,
            kind=EmployeeActivityKind.CREATED.value,
            summary="Atlas was created",
            sequence=1,
            created_at=datetime.now(timezone.utc),
        )
        self.service.list_activity.return_value = [event]
        response = self.client.get(f"{self.base}/activity")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["kind"], "created")

    def test_activity_maps_not_found_to_404(self):
        self.service.list_activity.side_effect = EmployeeNotFoundError()
        self.assertEqual(self.client.get(f"{self.base}/activity").status_code, 404)

    # -- capabilities
    def test_capability_list(self):
        self.service.list_capabilities.return_value = [EmployeeCapability.BROWSER]
        response = self.client.get(f"{self.base}/capabilities")
        self.assertEqual(response.json(), ["browser"])

    def test_capability_grant(self):
        self.service.add_capability.return_value = self.employee
        response = self.client.post(
            f"{self.base}/capabilities", json={"capability": "python"}
        )
        self.assertEqual(response.status_code, 200)

    def test_capability_grant_rejects_unknown_value(self):
        response = self.client.post(
            f"{self.base}/capabilities", json={"capability": "telepathy"}
        )
        self.assertEqual(response.status_code, 422)

    def test_capability_revoke(self):
        self.service.remove_capability.return_value = self.employee
        response = self.client.delete(f"{self.base}/capabilities/python")
        self.assertEqual(response.status_code, 200)

    # -- assignments
    def test_assignment_list(self):
        assignment = EmployeeAssignment(
            id=uuid.uuid4(),
            employee_id=self.employee.id,
            workflow_id="wf_1",
            workflow_name="Weekly report",
            priority=EmployeePriority.HIGH.value,
            execution_mode=ExecutionMode.SEQUENTIAL.value,
            dependency_summary=None,
            created_at=datetime.now(timezone.utc),
        )
        self.service.list_assignments.return_value = [assignment]
        body = self.client.get(f"{self.base}/assignments").json()
        self.assertEqual(body[0]["workflow_name"], "Weekly report")

    def test_assignment_create(self):
        assignment = EmployeeAssignment(
            id=uuid.uuid4(),
            employee_id=self.employee.id,
            workflow_id="wf_1",
            workflow_name="Weekly report",
            priority=EmployeePriority.MEDIUM.value,
            execution_mode=ExecutionMode.SEQUENTIAL.value,
            dependency_summary=None,
            created_at=datetime.now(timezone.utc),
        )
        self.service.assign_work.return_value = assignment
        response = self.client.post(
            f"{self.base}/assignments",
            json={"workflow_id": "wf_1", "workflow_name": "Weekly report"},
        )
        self.assertEqual(response.status_code, 201)

    def test_duplicate_assignment_maps_to_422(self):
        self.service.assign_work.side_effect = EmployeeValidationError("already")
        response = self.client.post(
            f"{self.base}/assignments",
            json={"workflow_id": "wf_1", "workflow_name": "Weekly report"},
        )
        self.assertEqual(response.status_code, 422)

    def test_assignment_delete(self):
        response = self.client.delete(f"{self.base}/assignments/{uuid.uuid4()}")
        self.assertEqual(response.status_code, 204)

    # -- health
    def test_health_endpoint(self):
        self.service.get_employee.return_value = self.employee
        body = self.client.get(f"{self.base}/health").json()
        self.assertEqual(body["health"], EmployeeHealth.UNKNOWN.value)
        self.assertEqual(body["status"], "draft")
        self.assertTrue(body["reasons"])

    def test_health_maps_access_denied_to_403(self):
        self.service.get_employee.side_effect = EmployeeAccessDeniedError()
        self.assertEqual(self.client.get(f"{self.base}/health").status_code, 403)


class EmployeeAuthorizationTests(unittest.TestCase):
    """Every employee route requires a bearer token."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.employee_id = uuid.uuid4()
        self.addCleanup(app.dependency_overrides.clear)

    def test_all_routes_require_authentication(self):
        base = f"/api/v1/employees/{self.employee_id}"
        calls = [
            ("get", "/api/v1/employees"),
            ("post", "/api/v1/employees"),
            ("get", base),
            ("patch", base),
            ("delete", base),
            ("post", f"{base}/archive"),
            ("post", f"{base}/restore"),
            ("get", f"{base}/activity"),
            ("get", f"{base}/capabilities"),
            ("post", f"{base}/capabilities"),
            ("delete", f"{base}/capabilities/python"),
            ("get", f"{base}/assignments"),
            ("post", f"{base}/assignments"),
            ("get", f"{base}/health"),
        ]
        for method, url in calls:
            # GET/DELETE take no body on this client.
            kwargs = {"json": {}} if method in {"post", "patch"} else {}
            response = getattr(self.client, method)(url, **kwargs)
            self.assertEqual(response.status_code, 401, f"{method.upper()} {url}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

