"""SQLAlchemy ORM model for blueprint version snapshots.

A blueprint version is an immutable snapshot of a blueprint's content fields,
captured before a generated update is applied (Sprint 4D). Storage only — no
generation or AI logic.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.blueprint import Blueprint


class BlueprintVersion(Base):
    """An immutable snapshot of a blueprint's content at a point in time."""

    __tablename__ = "blueprint_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("blueprints.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Sequential per blueprint, starting at 1.
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Snapshot of the blueprint's content fields at capture time.
    vision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    communication_style: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    personality_traits: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    goals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    constraints: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Each version belongs to exactly one blueprint.
    blueprint: Mapped["Blueprint"] = relationship(back_populates="versions")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<BlueprintVersion id={self.id} v{self.version_number} "
            f"blueprint_id={self.blueprint_id}>"
        )
