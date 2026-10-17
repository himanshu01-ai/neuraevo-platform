"""Persistent project context and immutable resume checkpoints."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.models.user import User


class Project(Base):
    """A user's current, explicitly approved project context."""

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("context_revision >= 0", name="ck_projects_context_revision"),
        CheckConstraint("version >= 1", name="ck_projects_version"),
        CheckConstraint(
            "(context_revision = 0 AND context_approved_at IS NULL) OR "
            "(context_revision > 0 AND context_approved_at IS NOT NULL)",
            name="ck_projects_context_approval",
        ),
        Index(
            "ix_projects_user_archived_created",
            "user_id",
            "archived_at",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    technology_stack: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    repository_reference: Mapped[Optional[str]] = mapped_column(
        String(2048), nullable=True
    )
    constraints: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_revision: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    context_approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner: Mapped["User"] = relationship(back_populates="projects")
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="project", passive_deletes=True
    )
    checkpoints: Mapped[List["ProjectCheckpoint"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProjectCheckpoint.sequence",
    )


class ProjectCheckpoint(Base):
    """An immutable, explicitly confirmed project-resume snapshot."""

    __tablename__ = "project_checkpoints"
    __table_args__ = (
        UniqueConstraint("project_id", "sequence", name="uq_checkpoint_sequence"),
        UniqueConstraint("project_id", "request_id", name="uq_checkpoint_request"),
        CheckConstraint("sequence > 0", name="ck_checkpoints_sequence"),
        CheckConstraint("context_revision > 0", name="ck_checkpoints_context_revision"),
        CheckConstraint(
            "length(trim(coalesce(decisions, ''))) > 0 OR "
            "length(trim(coalesce(verified_progress, ''))) > 0 OR "
            "length(trim(coalesce(next_steps, ''))) > 0",
            name="ck_checkpoints_content",
        ),
        CheckConstraint(
            "length(trim(coalesce(verified_progress, ''))) = 0 OR "
            "length(trim(coalesce(verification_note, ''))) > 0",
            name="ck_checkpoints_verification_note",
        ),
        CheckConstraint(
            "length(request_fingerprint) = 64",
            name="ck_checkpoints_request_fingerprint",
        ),
        Index("ix_checkpoints_project_created", "project_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    decisions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verified_progress: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verification_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_steps: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    context_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey(
            "messages.id",
            name="fk_project_checkpoints_source_message_id_messages",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="checkpoints")
    source_message: Mapped[Optional["Message"]] = relationship(
        passive_deletes=True
    )

