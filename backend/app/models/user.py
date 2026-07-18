"""SQLAlchemy ORM model for application users."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class User(Base):
    """A registered platform user who can own AI employees."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Email verification (Sprint 18.1A) -------------------------------
    email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # SHA-256 digest of the outstanding verification code — never the code.
    verification_token_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    verification_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Password reset (Sprint 18.1A) -----------------------------------
    # SHA-256 digest of the outstanding reset token — never the token.
    password_reset_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    password_reset_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Token revocation (Sprint 18.1A) ---------------------------------
    # Incremented on logout and password reset. Issued JWTs embed the epoch
    # they were minted with; a mismatch means the token has been revoked.
    token_epoch: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
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

    # One user owns many employees.
    employees: Mapped[List["Employee"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<User id={self.id} email={self.email!r}>"
