"""Persistence-only repositories for projects and their checkpoints."""

import uuid
from datetime import datetime
from typing import Any, Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.employee import Employee
from app.models.message import Message
from app.models.project import Project, ProjectCheckpoint


class ProjectRepository:
    """Project reads and atomic versioned writes; never commits."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, user_id: uuid.UUID, **fields: object) -> Project:
        project = Project(user_id=user_id, **fields)
        self.session.add(project)
        self.session.flush()
        self.session.refresh(project)
        return project

    def get_by_id(self, project_id: uuid.UUID) -> Optional[Project]:
        return self.session.get(Project, project_id)

    def get_owned_for_update(
        self, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> Optional[Project]:
        stmt = (
            select(Project)
            .where(Project.id == project_id, Project.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self.session.scalar(stmt)

    def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        archived: Optional[bool] = False,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Project]:
        stmt = select(Project).where(Project.user_id == user_id)
        if archived is True:
            stmt = stmt.where(Project.archived_at.is_not(None))
        elif archived is False:
            stmt = stmt.where(Project.archived_at.is_(None))
        stmt = stmt.order_by(Project.created_at.desc()).offset(skip).limit(limit)
        return self.session.scalars(stmt).all()

    def update_if_version(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        expected_version: int,
        *,
        require_archived: Optional[bool],
        fields: dict[str, Any],
        increment_context_revision: bool = False,
    ) -> bool:
        conditions = [
            Project.id == project_id,
            Project.user_id == user_id,
            Project.version == expected_version,
        ]
        if require_archived is True:
            conditions.append(Project.archived_at.is_not(None))
        elif require_archived is False:
            conditions.append(Project.archived_at.is_(None))

        values = dict(fields)
        values["version"] = Project.version + 1
        values["updated_at"] = func.now()
        if increment_context_revision:
            values["context_revision"] = Project.context_revision + 1
        result = self.session.execute(
            update(Project)
            .where(*conditions)
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1


class ProjectCheckpointRepository:
    """Checkpoint persistence and source-chain verification; never commits."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        project_id: uuid.UUID,
        sequence: int,
        context_revision: int,
        context_snapshot: dict[str, Any],
        request_id: uuid.UUID,
        request_fingerprint: str,
        decisions: Optional[str],
        verified_progress: Optional[str],
        verification_note: Optional[str],
        next_steps: Optional[str],
        source_message_id: Optional[uuid.UUID],
    ) -> ProjectCheckpoint:
        checkpoint = ProjectCheckpoint(
            project_id=project_id,
            sequence=sequence,
            context_revision=context_revision,
            context_snapshot=context_snapshot,
            request_id=request_id,
            request_fingerprint=request_fingerprint,
            decisions=decisions,
            verified_progress=verified_progress,
            verification_note=verification_note,
            next_steps=next_steps,
            source_message_id=source_message_id,
        )
        self.session.add(checkpoint)
        self.session.flush()
        self.session.refresh(checkpoint)
        return checkpoint

    def get_for_project(
        self, project_id: uuid.UUID, checkpoint_id: uuid.UUID
    ) -> Optional[ProjectCheckpoint]:
        stmt = select(ProjectCheckpoint).where(
            ProjectCheckpoint.id == checkpoint_id,
            ProjectCheckpoint.project_id == project_id,
        )
        return self.session.scalar(stmt)

    def get_by_request(
        self, project_id: uuid.UUID, request_id: uuid.UUID
    ) -> Optional[ProjectCheckpoint]:
        stmt = select(ProjectCheckpoint).where(
            ProjectCheckpoint.project_id == project_id,
            ProjectCheckpoint.request_id == request_id,
        )
        return self.session.scalar(stmt)

    def list_for_project(
        self,
        project_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ProjectCheckpoint]:
        stmt = (
            select(ProjectCheckpoint)
            .where(ProjectCheckpoint.project_id == project_id)
            .order_by(ProjectCheckpoint.sequence.desc())
            .offset(skip)
            .limit(limit)
        )
        return self.session.scalars(stmt).all()

    def latest_for_project(
        self, project_id: uuid.UUID
    ) -> Optional[ProjectCheckpoint]:
        stmt = (
            select(ProjectCheckpoint)
            .where(ProjectCheckpoint.project_id == project_id)
            .order_by(ProjectCheckpoint.sequence.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def next_sequence(self, project_id: uuid.UUID) -> int:
        current = self.session.scalar(
            select(func.max(ProjectCheckpoint.sequence)).where(
                ProjectCheckpoint.project_id == project_id
            )
        )
        return int(current or 0) + 1

    def source_belongs_to_owned_project(
        self,
        source_message_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        stmt = (
            select(Message.id)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .join(Employee, Employee.id == Conversation.employee_id)
            .where(
                Message.id == source_message_id,
                Conversation.project_id == project_id,
                Employee.user_id == user_id,
            )
        )
        return self.session.scalar(stmt) is not None

