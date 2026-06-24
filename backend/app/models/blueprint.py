"""SQLAlchemy ORM model for employee blueprints.

A blueprint is the structured identity/profile of an employee. Each employee
has at most one blueprint (enforced by a unique constraint on
``employee_id``). This model is storage only — no generation or AI logic.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class Blueprint(Base):
    """The structured profile belonging to a single employee."""

    __tablename__ = "blueprints"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("employees.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    vision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    communication_style: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    personality_traits: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    goals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    constraints: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # One-to-one: each blueprint belongs to exactly one employee.
    employee: Mapped["Employee"] = relationship(back_populates="blueprint")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Blueprint id={self.id} employee_id={self.employee_id}>"
