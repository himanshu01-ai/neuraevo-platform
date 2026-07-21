"""Collaboration Platform tests — participants, permissions & access (Sprint 20A).

Two layers, both against a real in-memory database so the polymorphic resource
resolution, the check/unique constraints, and the reused ownership chains are
all exercised for real:

* ``CollaborationServiceTests`` drive :class:`CollaborationService` directly over
  a seeded owner, collaborator, outsider, employees, and one resource of every
  collaborated type (conversation, task, workflow, memory).
* ``CollaborationAPITests`` drive the endpoints through ``TestClient`` with the
  service bound to the same real session and ``get_current_user`` overridden,
  covering status codes, error mapping, DTO shapes, and permission enforcement.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_collaboration
"""

import unittest
import uuid

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.dependencies import get_collaboration_service, get_current_user
from app.main import app
from app.models.conversation import Conversation
from app.models.employee import Employee
from app.models.memory import Memory
from app.models.task import Task
from app.models.user import User
from app.models.workflow import Workflow
from app.schemas.collaboration import ParticipantCreate
from app.services.collaboration.service import (
    CollaborationAccessDeniedError,
    CollaborationService,
    CollaborationValidationError,
    DuplicateParticipantError,
    ParticipantNotFoundError,
    ResourceNotFoundError,
)
from app.utils.constants import (
    CollaborationResourceType,
    CollaborationRole,
    ParticipantType,
)


def make_engine():
    """A fresh in-memory database with every table these tests touch."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


class CollaborationFixture(unittest.TestCase):
    """An owner, a collaborator, an outsider, employees, and one of each resource."""

    def setUp(self):
        self.engine = make_engine()
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session: Session = self.Session()

        self.owner = self._user("owner@neuraevo.dev", "Olivia Owner")
        self.collaborator = self._user("collab@neuraevo.dev", "Cody Collaborator")
        self.outsider = self._user("outsider@neuraevo.dev", "Xavier Outsider")
        self.session.add_all([self.owner, self.collaborator, self.outsider])
        self.session.commit()

        # An employee the owner owns (a valid participant / conversation-memory
        # anchor) and one belonging to the outsider (an invalid participant).
        self.employee = self._employee(self.owner, "Research Assistant")
        self.foreign_employee = self._employee(self.outsider, "Rogue Assistant")
        self.session.add_all([self.employee, self.foreign_employee])
        self.session.commit()

        # One resource of every collaborated type, all owned by ``owner``.
        self.task = Task(
            id=uuid.uuid4(),
            user_id=self.owner.id,
            business_id="TSK-1001",
            name="Ship the collaboration core",
        )
        self.workflow = Workflow(
            id=uuid.uuid4(),
            user_id=self.owner.id,
            name="Onboarding",
            graph={"nodes": [], "edges": []},
        )
        self.conversation = Conversation(
            id=uuid.uuid4(),
            employee_id=self.employee.id,
            title="Kickoff",
        )
        self.memory = Memory(
            id=uuid.uuid4(),
            employee_id=self.employee.id,
            memory_type="fact",
            content="The launch date is set.",
        )
        self.session.add_all(
            [self.task, self.workflow, self.conversation, self.memory]
        )
        self.session.commit()

        self.service = CollaborationService(self.session)

        # (resource_type, resource_id) for every collaborated type.
        self.resources = {
            CollaborationResourceType.TASK: self.task.id,
            CollaborationResourceType.WORKFLOW: self.workflow.id,
            CollaborationResourceType.CONVERSATION: self.conversation.id,
            CollaborationResourceType.MEMORY: self.memory.id,
        }

    def tearDown(self):
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def _user(self, email: str, name: str) -> User:
        return User(
            id=uuid.uuid4(),
            email=email,
            hashed_password="x",
            full_name=name,
            is_active=True,
        )

    def _employee(self, owner: User, name: str) -> Employee:
        return Employee(
            id=uuid.uuid4(),
            user_id=owner.id,
            name=name,
            role="assistant",
        )


class CollaborationServiceTests(CollaborationFixture):
    """Role resolution, participant management, and ownership reuse."""

    # --- Owner resolution across every resource type --------------------

    def test_owner_resolves_to_owner_role_for_every_resource(self):
        for rtype, rid in self.resources.items():
            with self.subTest(resource=rtype.value):
                role, is_owner = self.service.get_access(self.owner, rtype, rid)
                self.assertEqual(role, CollaborationRole.OWNER)
                self.assertTrue(is_owner)

    def test_owner_is_synthesised_first_in_participant_list(self):
        for rtype, rid in self.resources.items():
            with self.subTest(resource=rtype.value):
                people = self.service.list_participants(self.owner, rtype, rid)
                self.assertTrue(people[0].is_owner)
                self.assertIsNone(people[0].id)  # no row — ownership is derived
                self.assertEqual(people[0].user_id, self.owner.id)
                self.assertEqual(people[0].name, "Olivia Owner")

    # --- Existence hiding ------------------------------------------------

    def test_outsider_sees_resource_as_not_found(self):
        for rtype, rid in self.resources.items():
            with self.subTest(resource=rtype.value):
                with self.assertRaises(ResourceNotFoundError):
                    self.service.list_participants(self.outsider, rtype, rid)
                with self.assertRaises(ResourceNotFoundError):
                    self.service.get_access(self.outsider, rtype, rid)

    def test_missing_resource_is_not_found(self):
        with self.assertRaises(ResourceNotFoundError):
            self.service.get_access(
                self.owner, CollaborationResourceType.TASK, uuid.uuid4()
            )

    # --- Adding a user participant --------------------------------------

    def test_add_user_participant_grants_that_role(self):
        for rtype, rid in self.resources.items():
            with self.subTest(resource=rtype.value):
                self.service.add_participant(
                    self.owner,
                    rtype,
                    rid,
                    ParticipantCreate(
                        participant_type=ParticipantType.USER,
                        user_id=self.collaborator.id,
                        role=CollaborationRole.VIEWER,
                    ),
                )
                role, is_owner = self.service.get_access(
                    self.collaborator, rtype, rid
                )
                self.assertEqual(role, CollaborationRole.VIEWER)
                self.assertFalse(is_owner)

    def test_viewer_can_list_but_cannot_manage(self):
        rtype, rid = CollaborationResourceType.TASK, self.task.id
        self.service.add_participant(
            self.owner,
            rtype,
            rid,
            ParticipantCreate(
                participant_type=ParticipantType.USER,
                user_id=self.collaborator.id,
                role=CollaborationRole.VIEWER,
            ),
        )
        # The viewer can see who is here...
        people = self.service.list_participants(self.collaborator, rtype, rid)
        self.assertEqual(len(people), 2)
        # ...but cannot invite anyone (owner-only in this slice).
        with self.assertRaises(CollaborationAccessDeniedError):
            self.service.add_participant(
                self.collaborator,
                rtype,
                rid,
                ParticipantCreate(
                    participant_type=ParticipantType.USER,
                    user_id=self.outsider.id,
                ),
            )

    def test_editor_still_cannot_manage_participants(self):
        rtype, rid = CollaborationResourceType.WORKFLOW, self.workflow.id
        self.service.add_participant(
            self.owner,
            rtype,
            rid,
            ParticipantCreate(
                participant_type=ParticipantType.USER,
                user_id=self.collaborator.id,
                role=CollaborationRole.EDITOR,
            ),
        )
        with self.assertRaises(CollaborationAccessDeniedError):
            self.service.add_participant(
                self.collaborator,
                rtype,
                rid,
                ParticipantCreate(
                    participant_type=ParticipantType.USER,
                    user_id=self.outsider.id,
                ),
            )

    def test_cannot_add_owner_as_participant(self):
        with self.assertRaises(CollaborationValidationError):
            self.service.add_participant(
                self.owner,
                CollaborationResourceType.TASK,
                self.task.id,
                ParticipantCreate(
                    participant_type=ParticipantType.USER,
                    user_id=self.owner.id,
                ),
            )

    def test_cannot_add_unknown_user(self):
        with self.assertRaises(CollaborationValidationError):
            self.service.add_participant(
                self.owner,
                CollaborationResourceType.TASK,
                self.task.id,
                ParticipantCreate(
                    participant_type=ParticipantType.USER,
                    user_id=uuid.uuid4(),
                ),
            )

    def test_duplicate_user_participant_is_rejected(self):
        rtype, rid = CollaborationResourceType.MEMORY, self.memory.id
        payload = ParticipantCreate(
            participant_type=ParticipantType.USER,
            user_id=self.collaborator.id,
        )
        self.service.add_participant(self.owner, rtype, rid, payload)
        with self.assertRaises(DuplicateParticipantError):
            self.service.add_participant(self.owner, rtype, rid, payload)

    # --- Adding an AI employee participant ------------------------------

    def test_add_employee_participant_reuses_ownership(self):
        for rtype, rid in self.resources.items():
            with self.subTest(resource=rtype.value):
                added = self.service.add_participant(
                    self.owner,
                    rtype,
                    rid,
                    ParticipantCreate(
                        participant_type=ParticipantType.EMPLOYEE,
                        employee_id=self.employee.id,
                        role=CollaborationRole.EDITOR,
                    ),
                )
                self.assertEqual(added.participant_type, ParticipantType.EMPLOYEE)
                self.assertEqual(added.employee_id, self.employee.id)
                self.assertEqual(added.name, "Research Assistant")
                self.assertFalse(added.is_owner)

    def test_cannot_add_employee_owned_by_someone_else(self):
        with self.assertRaises(CollaborationValidationError):
            self.service.add_participant(
                self.owner,
                CollaborationResourceType.TASK,
                self.task.id,
                ParticipantCreate(
                    participant_type=ParticipantType.EMPLOYEE,
                    employee_id=self.foreign_employee.id,
                ),
            )

    # --- Role updates & removal -----------------------------------------

    def test_update_role_changes_effective_access(self):
        rtype, rid = CollaborationResourceType.TASK, self.task.id
        added = self.service.add_participant(
            self.owner,
            rtype,
            rid,
            ParticipantCreate(
                participant_type=ParticipantType.USER,
                user_id=self.collaborator.id,
                role=CollaborationRole.VIEWER,
            ),
        )
        self.service.update_participant_role(
            self.owner, rtype, rid, added.id, CollaborationRole.EDITOR
        )
        role, _ = self.service.get_access(self.collaborator, rtype, rid)
        self.assertEqual(role, CollaborationRole.EDITOR)

    def test_remove_participant_revokes_access(self):
        rtype, rid = CollaborationResourceType.TASK, self.task.id
        added = self.service.add_participant(
            self.owner,
            rtype,
            rid,
            ParticipantCreate(
                participant_type=ParticipantType.USER,
                user_id=self.collaborator.id,
            ),
        )
        self.service.remove_participant(self.owner, rtype, rid, added.id)
        with self.assertRaises(ResourceNotFoundError):
            self.service.get_access(self.collaborator, rtype, rid)

    def test_participant_of_wrong_resource_is_not_found(self):
        added = self.service.add_participant(
            self.owner,
            CollaborationResourceType.TASK,
            self.task.id,
            ParticipantCreate(
                participant_type=ParticipantType.USER,
                user_id=self.collaborator.id,
            ),
        )
        # Same participant id, different resource → not found, never cross-wired.
        with self.assertRaises(ParticipantNotFoundError):
            self.service.remove_participant(
                self.owner,
                CollaborationResourceType.WORKFLOW,
                self.workflow.id,
                added.id,
            )

    def test_participants_are_isolated_per_resource(self):
        self.service.add_participant(
            self.owner,
            CollaborationResourceType.TASK,
            self.task.id,
            ParticipantCreate(
                participant_type=ParticipantType.USER,
                user_id=self.collaborator.id,
            ),
        )
        # The collaborator is on the task, not on the workflow.
        with self.assertRaises(ResourceNotFoundError):
            self.service.get_access(
                self.collaborator,
                CollaborationResourceType.WORKFLOW,
                self.workflow.id,
            )

    # --- Schema guard ----------------------------------------------------

    def test_schema_rejects_owner_role(self):
        with self.assertRaises(ValidationError):
            ParticipantCreate(
                participant_type=ParticipantType.USER,
                user_id=uuid.uuid4(),
                role=CollaborationRole.OWNER,
            )

    def test_schema_rejects_mismatched_identity(self):
        with self.assertRaises(ValidationError):
            ParticipantCreate(
                participant_type=ParticipantType.USER,
                employee_id=uuid.uuid4(),  # wrong identity for a user
            )


class CollaborationAPITests(CollaborationFixture):
    """The endpoints end-to-end, over the same real session."""

    def setUp(self):
        super().setUp()
        self._current_user = self.owner
        app.dependency_overrides[get_current_user] = lambda: self._current_user
        app.dependency_overrides[get_collaboration_service] = (
            lambda: CollaborationService(self.session)
        )
        self.client = TestClient(app)

    def _url(self, rtype: CollaborationResourceType, rid, suffix="participants"):
        return f"/api/v1/collaboration/{rtype.value}/{rid}/{suffix}"

    def test_owner_reads_access(self):
        resp = self.client.get(
            self._url(CollaborationResourceType.TASK, self.task.id, "access")
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["role"], "owner")
        self.assertTrue(body["is_owner"])

    def test_outsider_gets_404(self):
        self._current_user = self.outsider
        resp = self.client.get(
            self._url(CollaborationResourceType.TASK, self.task.id)
        )
        self.assertEqual(resp.status_code, 404)

    def test_add_employee_participant_returns_201(self):
        resp = self.client.post(
            self._url(CollaborationResourceType.CONVERSATION, self.conversation.id),
            json={
                "participant_type": "employee",
                "employee_id": str(self.employee.id),
                "role": "editor",
            },
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["participant_type"], "employee")
        self.assertEqual(body["role"], "editor")
        self.assertEqual(body["name"], "Research Assistant")
        self.assertFalse(body["is_owner"])

    def test_owner_appears_first_in_list(self):
        resp = self.client.get(
            self._url(CollaborationResourceType.TASK, self.task.id)
        )
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()
        self.assertTrue(rows[0]["is_owner"])
        self.assertIsNone(rows[0]["id"])

    def test_owner_role_in_payload_is_422(self):
        resp = self.client.post(
            self._url(CollaborationResourceType.TASK, self.task.id),
            json={
                "participant_type": "user",
                "user_id": str(self.collaborator.id),
                "role": "owner",
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_employee_not_owned_is_422(self):
        resp = self.client.post(
            self._url(CollaborationResourceType.TASK, self.task.id),
            json={
                "participant_type": "employee",
                "employee_id": str(self.foreign_employee.id),
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_duplicate_is_409(self):
        payload = {
            "participant_type": "user",
            "user_id": str(self.collaborator.id),
        }
        url = self._url(CollaborationResourceType.WORKFLOW, self.workflow.id)
        self.assertEqual(self.client.post(url, json=payload).status_code, 201)
        self.assertEqual(self.client.post(url, json=payload).status_code, 409)

    def test_invalid_resource_type_is_422(self):
        resp = self.client.get(
            f"/api/v1/collaboration/banana/{self.task.id}/participants"
        )
        self.assertEqual(resp.status_code, 422)

    def test_patch_then_delete_lifecycle(self):
        rtype, rid = CollaborationResourceType.MEMORY, self.memory.id
        created = self.client.post(
            self._url(rtype, rid),
            json={"participant_type": "user", "user_id": str(self.collaborator.id)},
        ).json()
        participant_id = created["id"]

        patched = self.client.patch(
            self._url(rtype, rid) + f"/{participant_id}",
            json={"role": "editor"},
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["role"], "editor")

        deleted = self.client.delete(self._url(rtype, rid) + f"/{participant_id}")
        self.assertEqual(deleted.status_code, 204)

        rows = self.client.get(self._url(rtype, rid)).json()
        self.assertEqual([r for r in rows if not r["is_owner"]], [])

    def test_viewer_cannot_add_but_can_list(self):
        rtype, rid = CollaborationResourceType.TASK, self.task.id
        # Owner adds the collaborator as a viewer.
        self.client.post(
            self._url(rtype, rid),
            json={"participant_type": "user", "user_id": str(self.collaborator.id)},
        )
        # Now act as the viewer.
        self._current_user = self.collaborator
        self.assertEqual(self.client.get(self._url(rtype, rid)).status_code, 200)
        forbidden = self.client.post(
            self._url(rtype, rid),
            json={"participant_type": "user", "user_id": str(self.outsider.id)},
        )
        self.assertEqual(forbidden.status_code, 403)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
