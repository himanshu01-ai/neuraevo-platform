"""SQLAlchemy ORM model for permissions granted to an AI employee."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.constants import PermissionLevel

if TYPE_CHECKING:
    from app.models.employee import Employee


class EmployeePermissionGrant(Base):
    """One permission held by one employee, at a level.

    Unlike a capability, a permission is not simply held or not — it carries how
    freely it may be exercised, so the row stores a level. ``permission`` and
    ``level`` are plain strings whose allowed values are defined by
    :class:`app.utils.constants.EmployeePermission` and
    :class:`app.utils.constants.PermissionLevel`, validated at the schema and
    service layers.
    """

    __tablename__ = "employee_permissions"
    __table_args__ = (
        UniqueConstraint("employee_id", "permission", name="uq_employee_permission"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("employees.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    permission: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[str] = mapped_column(
        String(50), default=PermissionLevel.BLOCKED.value, nullable=False
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

    employee: Mapped["Employee"] = relationship(back_populates="permissions")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<EmployeePermissionGrant employee_id={self.employee_id} "
            f"permission={self.permission!r} level={self.level!r}>"
        )

