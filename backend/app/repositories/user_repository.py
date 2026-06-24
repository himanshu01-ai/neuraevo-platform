"""Data-access layer for :class:`~app.models.user.User`.

Repositories encapsulate persistence only. They do not hash passwords,
authenticate, or enforce business rules; callers pass already-prepared values
(e.g. a pre-hashed password). Transaction control (commit/rollback) is left to
the caller; methods ``flush`` so generated values like ``id`` are populated.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """CRUD-style accessors for :class:`User` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
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
