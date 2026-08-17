"""Data-access layer for :class:`~app.models.user.User`.

Repositories encapsulate persistence only. They do not hash passwords,
authenticate, or enforce business rules; callers pass already-prepared values
(e.g. a pre-hashed password). Transaction control (commit/rollback) is left to
the caller; methods ``flush`` so generated values like ``id`` are populated.
"""

import uuid
from datetime import datetime
from typing import Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """CRUD-style accessors for :class:`User` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return self.session.get(User, user_id)

    def get_by_ids(
        self, user_ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, User]:
        """Resolve many users in one round-trip, keyed by id.

        The batch counterpart to :meth:`get_by_id`, for read surfaces that would
        otherwise resolve a name per row (an N+1). ``None`` ids and duplicates are
        dropped; ids with no matching row are simply absent from the result, so a
        caller reads a miss the same way it would from :meth:`get_by_id`.
        """
        ids = [uid for uid in dict.fromkeys(user_ids) if uid is not None]
        if not ids:
            return {}
        stmt = select(User).where(User.id.in_(ids))
        return {user.id: user for user in self.session.scalars(stmt).all()}

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        return self.session.scalar(stmt)

    def get_by_password_reset_hash(self, token_hash: str) -> Optional[User]:
        """Look a user up by the digest of their outstanding reset token."""
        stmt = select(User).where(User.password_reset_hash == token_hash)
        return self.session.scalar(stmt)

    def list(self, *, skip: int = 0, limit: int = 100) -> Sequence[User]:
        stmt = select(User).offset(skip).limit(limit).order_by(User.created_at)
        return self.session.scalars(stmt).all()

    def create(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: Optional[str] = None,
    ) -> User:
        """Persist a new user and return it with generated fields populated."""
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
        )
        self.session.add(user)
        self.session.flush()
        self.session.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.session.delete(user)
        self.session.flush()

    # --- Credential / token field writers (Sprint 18.1A) -----------------
    #
    # Persistence only: callers pass already-generated hashes and already-
    # computed expiries. The repository decides nothing about validity,
    # expiry policy, or who is allowed to do this.

    def set_verification_token(
        self,
        user: User,
        *,
        token_hash: Optional[str],
        expires_at: Optional[datetime],
    ) -> User:
        """Store (or clear, with ``None``) the outstanding verification code."""
        user.verification_token_hash = token_hash
        user.verification_expires_at = expires_at
        self.session.flush()
        return user

    def mark_email_verified(self, user: User, *, verified_at: datetime) -> User:
        """Flag the address as verified and consume the verification code."""
        user.email_verified = True
        user.email_verified_at = verified_at
        user.verification_token_hash = None
        user.verification_expires_at = None
        self.session.flush()
        return user

    def set_password_reset_token(
        self,
        user: User,
        *,
        token_hash: Optional[str],
        expires_at: Optional[datetime],
    ) -> User:
        """Store (or clear, with ``None``) the outstanding reset token."""
        user.password_reset_hash = token_hash
        user.password_reset_expires_at = expires_at
        self.session.flush()
        return user

    def set_password(self, user: User, *, hashed_password: str) -> User:
        """Replace the stored password digest and consume the reset token."""
        user.hashed_password = hashed_password
        user.password_reset_hash = None
        user.password_reset_expires_at = None
        self.session.flush()
        return user

    def bump_token_epoch(self, user: User) -> User:
        """Advance the revocation marker, invalidating every issued token."""
        user.token_epoch = (user.token_epoch or 0) + 1
        self.session.flush()
        return user
