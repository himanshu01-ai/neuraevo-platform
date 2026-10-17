"""Project data-foundation tests over an isolated in-memory database."""

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import Conversation, Employee, Message, Project, ProjectCheckpoint, User
from app.schemas.project import (
    ProjectCheckpointCreate,
    ProjectContextReplacement,
    ProjectCreate,
    ProjectLifecycleChange,
    ProjectMetadataUpdate,
)
from app.services.project_service import (
    ProjectAccessDeniedError,
    ProjectArchivedError,
    ProjectCheckpointConflictError,
    ProjectCheckpointNotFoundError,
    ProjectCheckpointService,
    ProjectConflictError,
    ProjectService,
    ProjectValidationError,
    ProjectVersionConflictError,
)


def make_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


class ProjectDomainFixture(unittest.TestCase):
    def setUp(self):
        self.engine = make_engine()
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session: Session = self.Session()
        self.owner = self._user("project-owner@example.test")
        self.other = self._user("project-other@example.test")
        self.session.add_all([self.owner, self.other])
        self.session.commit()
        self.projects = ProjectService(self.session)
        self.checkpoints = ProjectCheckpointService(self.session)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    @staticmethod
    def _user(email: str) -> User:
        return User(
            id=uuid.uuid4(),
            email=email,
            hashed_password="not-a-password",
            is_active=True,
        )

    def _project(self, name: str = "NeuraEvo") -> Project:
        return self.projects.create_project(self.owner, ProjectCreate(name=name))

    def _approved_project(self, name: str = "NeuraEvo") -> Project:
        project = self._project(name)
        return self.projects.replace_approved_context(
            self.owner,
            project.id,
            ProjectContextReplacement(
                objective="Ship reliable project continuity.",
                technology_stack="FastAPI and Next.js",
                repository_reference="himanshu01-ai/neuraevo-platform",
                constraints="Only user-approved facts are durable.",
                current_state="Project foundation in progress.",
                expected_version=project.version,
                approved=True,
            ),
        )

    def _employee_conversation_message(
        self, project: Project, *, owner: User | None = None
    ) -> tuple[Employee, Conversation, Message]:
        actual_owner = owner or self.owner
        employee = Employee(
            id=uuid.uuid4(),
            user_id=actual_owner.id,
            name="Project Assistant",
            role="assistant",
        )
        self.session.add(employee)
        self.session.flush()
        conversation = Conversation(
            id=uuid.uuid4(),
            employee_id=employee.id,
            project_id=project.id,
            title="Project planning",
        )
        self.session.add(conversation)
        self.session.flush()
        message = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="assistant",
            content="The isolated test passed.",
        )
        self.session.add(message)
        self.session.commit()
        return employee, conversation, message


class ProjectServiceTests(ProjectDomainFixture):
    def test_create_is_unapproved_and_owned(self):
        project = self.projects.create_project(
            self.owner,
            ProjectCreate(name="  Builder workspace  ", objective=" draft "),
        )
        self.assertEqual(project.name, "Builder workspace")
        self.assertEqual(project.objective, "draft")
        self.assertEqual(project.context_revision, 0)
        self.assertIsNone(project.context_approved_at)
        self.assertEqual(project.version, 1)
        self.assertEqual(project.user_id, self.owner.id)

        with self.assertRaises(ProjectAccessDeniedError):
            self.projects.get_project(self.other, project.id)

    def test_lists_active_archived_and_all_with_pagination(self):
        active = self._project("Active")
        archived = self._project("Archived")
        self.projects.archive_project(
            self.owner,
            archived.id,
            ProjectLifecycleChange(expected_version=archived.version),
        )
        self.assertEqual(
            [row.id for row in self.projects.list_projects(self.owner)],
            [active.id],
        )
        self.assertEqual(
            [row.id for row in self.projects.list_projects(self.owner, archived=True)],
            [archived.id],
        )
        self.assertEqual(
            len(self.projects.list_projects(self.owner, archived=None)), 2
        )

    def test_approval_replaces_full_context_and_advances_revisions(self):
        project = self._approved_project()
        self.assertEqual(project.context_revision, 1)
        self.assertEqual(project.version, 2)
        self.assertIsNotNone(project.context_approved_at)
        self.assertEqual(project.objective, "Ship reliable project continuity.")

        replaced = self.projects.replace_approved_context(
            self.owner,
            project.id,
            ProjectContextReplacement(
                objective="Resume work safely.",
                expected_version=project.version,
                approved=True,
            ),
        )
        self.assertEqual(replaced.context_revision, 2)
        self.assertEqual(replaced.version, 3)
        self.assertIsNone(replaced.technology_stack)

    def test_approval_must_be_explicit_and_objective_nonblank(self):
        project = self._project()
        with self.assertRaises(ProjectValidationError):
            self.projects.replace_approved_context(
                self.owner,
                project.id,
                ProjectContextReplacement(
                    objective="Valid objective",
                    expected_version=project.version,
                ),
            )
        self.session.refresh(project)
        self.assertEqual(project.context_revision, 0)
        self.assertEqual(project.version, 1)

    def test_metadata_stale_version_has_no_partial_write(self):
        project = self._project("Original")
        changed = self.projects.update_metadata(
            self.owner,
            project.id,
            ProjectMetadataUpdate(name="Current", expected_version=1),
        )
        self.assertEqual(changed.version, 2)
        with self.assertRaises(ProjectVersionConflictError):
            self.projects.update_metadata(
                self.owner,
                project.id,
                ProjectMetadataUpdate(name="Stale", expected_version=1),
            )
        self.assertFalse(self.session.in_transaction())
        self.session.expire_all()
        persisted = self.session.get(Project, project.id)
        self.assertEqual(persisted.name, "Current")
        self.assertEqual(persisted.version, 2)

    def test_archive_restore_versioning_and_write_rejection(self):
        project = self._project()
        archived = self.projects.archive_project(
            self.owner,
            project.id,
            ProjectLifecycleChange(expected_version=1),
        )
        self.assertEqual(archived.version, 2)
        self.assertIsNotNone(archived.archived_at)
        with self.assertRaises(ProjectArchivedError):
            self.projects.update_metadata(
                self.owner,
                project.id,
                ProjectMetadataUpdate(name="No", expected_version=2),
            )
        self.assertFalse(self.session.in_transaction())
        with self.assertRaises(ProjectConflictError):
            self.projects.archive_project(
                self.owner,
                project.id,
                ProjectLifecycleChange(expected_version=2),
            )
        self.assertFalse(self.session.in_transaction())
        restored = self.projects.restore_project(
            self.owner,
            project.id,
            ProjectLifecycleChange(expected_version=2),
        )
        self.assertEqual(restored.version, 3)
        self.assertIsNone(restored.archived_at)


class ProjectCheckpointServiceTests(ProjectDomainFixture):
    def _save(
        self,
        project: Project,
        *,
        request_id: uuid.UUID | None = None,
        source_message_id: uuid.UUID | None = None,
        decisions: str | None = "Keep the canonical turn path.",
        next_steps: str | None = None,
    ) -> ProjectCheckpoint:
        return self.checkpoints.create_checkpoint(
            self.owner,
            project.id,
            ProjectCheckpointCreate(
                decisions=decisions,
                next_steps=next_steps,
                source_message_id=source_message_id,
                request_id=request_id or uuid.uuid4(),
                expected_version=project.version,
                confirmed=True,
            ),
        )

    def test_confirmation_content_and_verification_note_are_required(self):
        project = self._approved_project()
        with self.assertRaises(ProjectValidationError):
            self.checkpoints.create_checkpoint(
                self.owner,
                project.id,
                ProjectCheckpointCreate(
                    decisions="Decision", request_id=uuid.uuid4(), expected_version=2
                ),
            )
        with self.assertRaises(ProjectValidationError):
            self.checkpoints.create_checkpoint(
                self.owner,
                project.id,
                ProjectCheckpointCreate(
                    request_id=uuid.uuid4(), expected_version=2, confirmed=True
                ),
            )
        with self.assertRaises(ProjectValidationError):
            self.checkpoints.create_checkpoint(
                self.owner,
                project.id,
                ProjectCheckpointCreate(
                    verified_progress="Tests pass",
                    request_id=uuid.uuid4(),
                    expected_version=2,
                    confirmed=True,
                ),
            )

    def test_snapshot_sequence_history_and_latest(self):
        project = self._approved_project()
        first = self._save(project)
        self.session.refresh(project)
        second = self._save(
            project, decisions=None, next_steps="Implement the service tests."
        )
        self.assertEqual((first.sequence, second.sequence), (1, 2))
        self.assertEqual(first.context_revision, 1)
        self.assertEqual(
            first.context_snapshot,
            {
                "objective": "Ship reliable project continuity.",
                "technology_stack": "FastAPI and Next.js",
                "repository_reference": "himanshu01-ai/neuraevo-platform",
                "constraints": "Only user-approved facts are durable.",
                "current_state": "Project foundation in progress.",
            },
        )
        original_snapshot = dict(first.context_snapshot)
        self.session.refresh(project)
        self.projects.replace_approved_context(
            self.owner,
            project.id,
            ProjectContextReplacement(
                objective="A replacement objective.",
                technology_stack="PostgreSQL",
                repository_reference="example/replacement",
                constraints="A replacement constraint.",
                current_state="A replacement state.",
                expected_version=project.version,
                approved=True,
            ),
        )
        self.session.refresh(first)
        self.assertEqual(first.context_snapshot, original_snapshot)
        rows = self.checkpoints.list_checkpoints(self.owner, project.id)
        self.assertEqual([row.id for row in rows], [second.id, first.id])
        self.assertEqual(
            self.checkpoints.latest_checkpoint(self.owner, project.id).id,
            second.id,
        )
        self.assertEqual(first.decisions, "Keep the canonical turn path.")

    def test_identical_retry_is_idempotent_and_changed_content_conflicts(self):
        project = self._approved_project()
        request_id = uuid.uuid4()
        first = self._save(project, request_id=request_id)
        retry = self.checkpoints.create_checkpoint(
            self.owner,
            project.id,
            ProjectCheckpointCreate(
                decisions="Keep the canonical turn path.",
                request_id=request_id,
                expected_version=2,
                confirmed=True,
            ),
        )
        self.assertEqual(retry.id, first.id)
        self.assertEqual(self.session.get(Project, project.id).version, 3)
        with self.assertRaises(ProjectCheckpointConflictError):
            self.checkpoints.create_checkpoint(
                self.owner,
                project.id,
                ProjectCheckpointCreate(
                    decisions="Different decision",
                    request_id=request_id,
                    expected_version=3,
                    confirmed=True,
                ),
            )
        self.assertFalse(self.session.in_transaction())

    def test_identical_retry_survives_source_message_deletion(self):
        project = self._approved_project()
        _, conversation, message = self._employee_conversation_message(project)
        request_id = uuid.uuid4()
        checkpoint = self._save(
            project,
            request_id=request_id,
            source_message_id=message.id,
        )
        original_source_id = message.id
        original_fingerprint = checkpoint.request_fingerprint

        self.session.delete(conversation)
        self.session.commit()
        self.session.expire_all()
        retained = self.session.get(ProjectCheckpoint, checkpoint.id)
        self.assertIsNone(retained.source_message_id)

        retry = self.checkpoints.create_checkpoint(
            self.owner,
            project.id,
            ProjectCheckpointCreate(
                decisions="Keep the canonical turn path.",
                source_message_id=original_source_id,
                request_id=request_id,
                expected_version=2,
                confirmed=True,
            ),
        )
        self.assertEqual(retry.id, checkpoint.id)
        self.assertEqual(retry.request_fingerprint, original_fingerprint)

        with self.assertRaises(ProjectCheckpointConflictError):
            self.checkpoints.create_checkpoint(
                self.owner,
                project.id,
                ProjectCheckpointCreate(
                    decisions="Keep the canonical turn path.",
                    source_message_id=None,
                    request_id=request_id,
                    expected_version=3,
                    confirmed=True,
                ),
            )
        self.assertFalse(self.session.in_transaction())

    def test_stale_checkpoint_and_archived_project_do_not_write(self):
        project = self._approved_project()
        with self.assertRaises(ProjectVersionConflictError):
            self.checkpoints.create_checkpoint(
                self.owner,
                project.id,
                ProjectCheckpointCreate(
                    decisions="Stale",
                    request_id=uuid.uuid4(),
                    expected_version=1,
                    confirmed=True,
                ),
            )
        self.assertFalse(self.session.in_transaction())
        archived = self.projects.archive_project(
            self.owner,
            project.id,
            ProjectLifecycleChange(expected_version=2),
        )
        with self.assertRaises(ProjectArchivedError):
            self._save(archived)
        self.assertFalse(self.session.in_transaction())
        count = self.session.scalar(select(func.count()).select_from(ProjectCheckpoint))
        self.assertEqual(count, 0)

    def test_unapproved_and_invalid_source_rejections_end_transaction(self):
        unapproved = self._project("Draft")
        with self.assertRaises(ProjectValidationError):
            self._save(unapproved)
        self.assertFalse(self.session.in_transaction())

        approved = self._approved_project("Approved")
        with self.assertRaises(ProjectValidationError):
            self._save(approved, source_message_id=uuid.uuid4())
        self.assertFalse(self.session.in_transaction())

    def test_integrity_errors_are_narrowly_classified_and_rolled_back(self):
        project = self._approved_project()

        class ConstraintViolation(Exception):
            def __init__(self, name: str):
                super().__init__(name)
                self.diag = SimpleNamespace(constraint_name=name)

        sequence_failure = IntegrityError(
            "INSERT",
            {},
            ConstraintViolation("uq_checkpoint_sequence"),
        )
        with patch.object(
            self.checkpoints.checkpoints,
            "create",
            side_effect=sequence_failure,
        ):
            with self.assertRaises(ProjectCheckpointConflictError):
                self._save(project)
        self.assertFalse(self.session.in_transaction())

        unexpected = IntegrityError(
            "INSERT",
            {},
            ConstraintViolation("ck_unexpected_database_invariant"),
        )
        with patch.object(
            self.checkpoints.checkpoints,
            "create",
            side_effect=unexpected,
        ):
            with self.assertRaises(IntegrityError) as raised:
                self._save(project)
        self.assertIs(raised.exception, unexpected)
        self.assertFalse(self.session.in_transaction())

    def test_source_message_delete_race_is_reported_as_validation_failure(self):
        project = self._approved_project()
        _, _, message = self._employee_conversation_message(project)

        class ConstraintViolation(Exception):
            def __init__(self):
                super().__init__(
                    "fk_project_checkpoints_source_message_id_messages"
                )
                self.diag = SimpleNamespace(
                    constraint_name=(
                        "fk_project_checkpoints_source_message_id_messages"
                    )
                )

        failure = IntegrityError("INSERT", {}, ConstraintViolation())
        with patch.object(
            self.checkpoints.checkpoints,
            "source_belongs_to_owned_project",
            side_effect=[True, False],
        ), patch.object(
            self.checkpoints.checkpoints,
            "create",
            side_effect=failure,
        ):
            with self.assertRaises(ProjectValidationError):
                self._save(project, source_message_id=message.id)
        self.assertFalse(self.session.in_transaction())

    def test_checkpoint_reads_are_owner_and_project_scoped(self):
        project = self._approved_project()
        checkpoint = self._save(project)
        with self.assertRaises(ProjectAccessDeniedError):
            self.checkpoints.list_checkpoints(self.other, project.id)
        second_project = self._approved_project("Second")
        with self.assertRaises(ProjectCheckpointNotFoundError):
            self.checkpoints.get_checkpoint(
                self.owner, second_project.id, checkpoint.id
            )

    def test_source_message_must_follow_owned_project_chain(self):
        project = self._approved_project()
        _, _, message = self._employee_conversation_message(project)
        checkpoint = self._save(project, source_message_id=message.id)
        self.assertEqual(checkpoint.source_message_id, message.id)

        other_project = self._approved_project("Other")
        with self.assertRaises(ProjectValidationError):
            self._save(other_project, source_message_id=message.id)

        foreign_project = self.projects.create_project(
            self.other, ProjectCreate(name="Foreign")
        )
        _, _, foreign_message = self._employee_conversation_message(
            foreign_project, owner=self.other
        )
        self.session.refresh(other_project)
        with self.assertRaises(ProjectValidationError):
            self._save(other_project, source_message_id=foreign_message.id)

        # Even a corrupt/mis-associated conversation row cannot make a foreign
        # employee's message valid merely by carrying this project's id.
        foreign_employee = Employee(
            id=uuid.uuid4(),
            user_id=self.other.id,
            name="Foreign Assistant",
            role="assistant",
        )
        self.session.add(foreign_employee)
        self.session.flush()
        inconsistent = Conversation(
            id=uuid.uuid4(),
            employee_id=foreign_employee.id,
            project_id=other_project.id,
            title="Inconsistent ownership",
        )
        self.session.add(inconsistent)
        self.session.flush()
        inconsistent_message = Message(
            id=uuid.uuid4(),
            conversation_id=inconsistent.id,
            role="assistant",
            content="Must not be accepted.",
        )
        self.session.add(inconsistent_message)
        self.session.commit()
        self.session.refresh(other_project)
        with self.assertRaises(ProjectValidationError):
            self._save(other_project, source_message_id=inconsistent_message.id)

    def test_conversation_delete_nulls_source_and_retains_checkpoint(self):
        project = self._approved_project()
        _, conversation, message = self._employee_conversation_message(project)
        checkpoint = self._save(project, source_message_id=message.id)
        checkpoint_id = checkpoint.id
        self.session.delete(conversation)
        self.session.commit()
        self.session.expire_all()
        retained = self.session.get(ProjectCheckpoint, checkpoint_id)
        self.assertIsNotNone(retained)
        self.assertIsNone(retained.source_message_id)

    def test_database_project_delete_nulls_conversation_and_cascades_checkpoint(self):
        project = self._approved_project()
        _, conversation, _ = self._employee_conversation_message(project)
        checkpoint = self._save(project)
        conversation_id, checkpoint_id = conversation.id, checkpoint.id
        self.session.delete(project)
        self.session.commit()
        self.session.expire_all()
        retained_conversation = self.session.get(Conversation, conversation_id)
        self.assertIsNotNone(retained_conversation)
        self.assertIsNone(retained_conversation.project_id)
        self.assertIsNone(self.session.get(ProjectCheckpoint, checkpoint_id))

    def test_soft_deleted_employee_and_legacy_conversation_compatibility(self):
        project = self._approved_project()
        employee, conversation, _ = self._employee_conversation_message(project)
        employee.deleted_at = project.created_at
        legacy = Conversation(
            id=uuid.uuid4(), employee_id=employee.id, title="Legacy"
        )
        self.session.add(legacy)
        self.session.commit()
        self.assertIsNotNone(self.session.get(Project, project.id))
        self.assertIsNone(legacy.project_id)
        self.assertEqual(conversation.project_id, project.id)

    def test_user_delete_cascades_projects_and_checkpoints(self):
        project = self._approved_project()
        checkpoint = self._save(project)
        project_id, checkpoint_id = project.id, checkpoint.id
        self.session.delete(self.owner)
        self.session.commit()
        self.session.expire_all()
        self.assertIsNone(self.session.get(Project, project_id))
        self.assertIsNone(self.session.get(ProjectCheckpoint, checkpoint_id))


if __name__ == "__main__":
    unittest.main()

