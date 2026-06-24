"""SQLAlchemy ORM model for employee memories."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class Memory(Base):
    """A single memory entry belonging to an employee.

    ``memory_type`` is stored as a plain string; allowed values are defined by
    :class:`app.utils.constants.MemoryType` and validated at the schema layer.
    """

    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("employees.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance_score: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Each memory belongs to exactly one employee.
    employee: Mapped["Employee"] = relationship(back_populates="memories")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<Memory id={self.id} type={self.memory_type!r} "
            f"employee_id={self.employee_id}>"
        )
