"""SQLAlchemy ORM model for capabilities granted to an AI employee."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class EmployeeCapabilityGrant(Base):
    """One capability held by one employee.

    A row is the grant itself — its presence means the capability is held, so
    there is no "granted" flag to fall out of step with reality. ``capability``
    is stored as a plain string whose allowed values are defined by
    :class:`app.utils.constants.EmployeeCapability` and validated at the schema
    and service layers, matching ``Memory.memory_type``.
    """

    __tablename__ = "employee_capabilities"
    __table_args__ = (
        # A capability is held or it isn't; holding it twice is meaningless.
        UniqueConstraint("employee_id", "capability", name="uq_employee_capability"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("employees.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    capability: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    employee: Mapped["Employee"] = relationship(back_populates="capabilities")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<EmployeeCapabilityGrant employee_id={self.employee_id} "
            f"capability={self.capability!r}>"
        )

