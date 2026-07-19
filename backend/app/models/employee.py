"""SQLAlchemy ORM model for AI employees owned by users."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.constants import (
    AutonomyLevel,
    EmployeeAccent,
    EmployeeGlyph,
    EmployeePriority,
    EmployeeStatus,
    EmployeeTone,
    ExecutionMode,
)

if TYPE_CHECKING:
    from app.models.blueprint import Blueprint
    from app.models.conversation import Conversation
    from app.models.employee_activity import EmployeeActivityEvent
    from app.models.employee_assignment import EmployeeAssignment
    from app.models.employee_capability import EmployeeCapabilityGrant
    from app.models.employee_permission import EmployeePermissionGrant
    from app.models.interview_session import InterviewSession
    from app.models.memory import Memory
    from app.models.user import User


class Employee(Base):
    """An AI employee belonging to a single owning user."""

    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(
        String(50), default="en", nullable=False
    )
    personality: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Stored as a plain string; allowed values are defined by
    # ``app.utils.constants.EmployeeStatus`` and validated at the schema and
    # service layers, matching how ``Memory.memory_type`` is handled.
    status: Mapped[str] = mapped_column(
        String(50), default=EmployeeStatus.DRAFT.value, nullable=False
    )

    # --- Configuration (Sprint 18.2A) ------------------------------------
    # First-class columns rather than one opaque JSON blob, so each setting can
    # be queried, validated, and migrated on its own.
    autonomy: Mapped[str] = mapped_column(
        String(50), default=AutonomyLevel.BALANCED.value, nullable=False
    )
    tone: Mapped[str] = mapped_column(
        String(50), default=EmployeeTone.PROFESSIONAL.value, nullable=False
    )
    execution_mode: Mapped[str] = mapped_column(
        String(50), default=ExecutionMode.SEQUENTIAL.value, nullable=False
    )
    priority: Mapped[str] = mapped_column(
        String(50), default=EmployeePriority.MEDIUM.value, nullable=False
    )
    require_approval: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # --- Appearance (Sprint 18.2A) ---------------------------------------
    accent: Mapped[str] = mapped_column(
        String(50), default=EmployeeAccent.SLATE.value, nullable=False
    )
    glyph: Mapped[str] = mapped_column(
        String(50), default=EmployeeGlyph.BOT.value, nullable=False
    )

    # --- Lifecycle timestamps (Sprint 18.2A) -----------------------------
    # ``archived_at`` records a reversible retirement; ``deleted_at`` is the
    # soft delete, which hides the row from every read path while preserving
    # the memories, blueprint, sessions and conversations hanging off it.
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
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

    # Each employee belongs to exactly one owning user.
    owner: Mapped["User"] = relationship(back_populates="employees")

    # One employee accumulates many memories.
    memories: Mapped[List["Memory"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
    )

    # One employee has at most one blueprint.
    blueprint: Mapped[Optional["Blueprint"]] = relationship(
        back_populates="employee",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # One employee can have many interview sessions.
    interview_sessions: Mapped[List["InterviewSession"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="InterviewSession.started_at",
    )

    # One employee can have many conversations.
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="Conversation.created_at",
    )

    # --- Sprint 18.2A collections ----------------------------------------

    capabilities: Mapped[List["EmployeeCapabilityGrant"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeCapabilityGrant.capability",
    )

    permissions: Mapped[List["EmployeePermissionGrant"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeePermissionGrant.permission",
    )

    activity_events: Mapped[List["EmployeeActivityEvent"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeActivityEvent.sequence",
    )

    assignments: Mapped[List["EmployeeAssignment"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeAssignment.created_at",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Employee id={self.id} name={self.name!r} user_id={self.user_id}>"
