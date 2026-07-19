"""SQLAlchemy ORM model for an AI employee's activity history."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class EmployeeActivityEvent(Base):
    """One thing that happened to an employee.

    History is append-only: an event records that something occurred, so rows
    are never rewritten and never deleted except with the employee itself. Every
    row is written by the service at the moment of the change — nothing is
    reconstructed or inferred after the fact.

    ``sequence`` is a per-employee ordinal so the history has a stable order
    that does not depend on timestamp resolution.
    """

    __tablename__ = "employee_activity_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("employees.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Allowed values are defined by
    # ``app.utils.constants.EmployeeActivityKind``.
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    employee: Mapped["Employee"] = relationship(back_populates="activity_events")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<EmployeeActivityEvent employee_id={self.employee_id} "
            f"kind={self.kind!r} sequence={self.sequence}>"
        )

