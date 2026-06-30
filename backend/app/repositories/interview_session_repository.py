"""Data-access layer for :class:`~app.models.interview_session.InterviewSession`.

Persistence only — no business logic, authorization, or state-transition
rules. Transaction control is left to the caller; methods ``flush`` so
generated values like ``id`` are populated.
"""

import uuid
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interview_session import InterviewSession
from app.schemas.interview_session import InterviewSessionCreate


class InterviewSessionRepository:
    """CRUD-style accessors for :class:`InterviewSession` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_session(
        self, employee_id: uuid.UUID, data: InterviewSessionCreate
    ) -> InterviewSession:
        """Persist a new session for ``employee_id``.

        ``started_at`` is set by the database default; ``completed_at`` starts
        null.
        """
        interview_session = InterviewSession(
            employee_id=employee_id,
            status=data.status.value,
        )
        self.session.add(interview_session)
        self.session.flush()
        self.session.refresh(interview_session)
        return interview_session

    def get_session(
        self, session_id: uuid.UUID
    ) -> Optional[InterviewSession]:
        return self.session.get(InterviewSession, session_id)

    def list_sessions(
        self, employee_id: uuid.UUID
    ) -> Sequence[InterviewSession]:
        """Return an employee's sessions ordered by ``started_at``."""
        stmt = (
            select(InterviewSession)
            .where(InterviewSession.employee_id == employee_id)
            .order_by(InterviewSession.started_at)
        )
        return self.session.scalars(stmt).all()

    def update_session(
        self,
        interview_session: InterviewSession,
        *,
        status: Optional[str] = None,
        completed_at: Optional[datetime] = None,
    ) -> InterviewSession:
        """Apply a partial update to an existing session instance.

        Only arguments that are not ``None`` are written; unspecified fields
        are left untouched. The session is assumed to already be loaded and
        authorized by the caller, and any state-transition validation done.
        """
        if status is not None:
            interview_session.status = status
        if completed_at is not None:
            interview_session.completed_at = completed_at
        self.session.flush()
        self.session.refresh(interview_session)
        return interview_session

    def delete_session(self, interview_session: InterviewSession) -> None:
        self.session.delete(interview_session)
        self.session.flush()
