"""Interview session service: create, list, retrieve, update, and delete.

Enforces the ownership chain (User -> Employee -> Session) by reusing
:class:`EmployeeService`, and enforces interview-session state-transition
rules. No AI generation, scoring, evaluation, or report logic.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from app.models.interview_session import InterviewSession
from app.models.user import User
from app.repositories.interview_session_repository import (
    InterviewSessionRepository,
)
from app.schemas.interview_session import (
    InterviewSessionCreate,
    InterviewSessionUpdate,
)
from app.services.employee_service import EmployeeService
from app.utils.constants import SessionStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Permitted status transitions (including idempotent self-transitions).
_ALLOWED_TRANSITIONS: dict[SessionStatus, set[SessionStatus]] = {
    SessionStatus.CREATED: {SessionStatus.CREATED, SessionStatus.IN_PROGRESS},
    SessionStatus.IN_PROGRESS: {
        SessionStatus.IN_PROGRESS,
        SessionStatus.COMPLETED,
    },
    SessionStatus.COMPLETED: {SessionStatus.COMPLETED},
}


class InterviewSessionError(Exception):
    """Base class for interview-session domain errors."""


class InterviewSessionNotFoundError(InterviewSessionError):
    """Raised when no session exists for the employee."""


class InterviewSessionStateError(InterviewSessionError):
    """Raised when an invalid status transition is attempted."""


class InterviewSessionService:
    """Coordinates interview-session operations using the repository layer.

    The service owns the unit of work: the repository ``flush``es while the
    service commits the transaction.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.sessions = InterviewSessionRepository(session)
        # Reused for the User -> Employee ownership chain.
        self.employees = EmployeeService(session)

    def create_session(
        self,
        owner: User,
        employee_id: uuid.UUID,
        data: InterviewSessionCreate,
    ) -> InterviewSession:
        """Create a session for an employee the owner can access."""
        employee = self.employees.get_employee(owner, employee_id)
        interview_session = self.sessions.create_session(employee.id, data)
        self.session.commit()
        self.session.refresh(interview_session)
        logger.info(
            "User %s created interview session %s for employee %s",
            owner.id,
            interview_session.id,
            employee.id,
        )
        return interview_session

    def list_sessions(
        self, owner: User, employee_id: uuid.UUID
    ) -> Sequence[InterviewSession]:
        """List an employee's sessions, ordered by started_at."""
        employee = self.employees.get_employee(owner, employee_id)
        return self.sessions.list_sessions(employee.id)

    def get_session(
        self, owner: User, employee_id: uuid.UUID, session_id: uuid.UUID
    ) -> InterviewSession:
        """Return a single session scoped to an employee the owner can access.

        Raises :class:`InterviewSessionNotFoundError` if the session does not
        exist or belongs to a different employee.
        """
        employee = self.employees.get_employee(owner, employee_id)
        interview_session = self.sessions.get_session(session_id)
        if (
            interview_session is None
            or interview_session.employee_id != employee.id
        ):
            raise InterviewSessionNotFoundError(str(session_id))
        return interview_session

    def update_session(
        self,
        owner: User,
        employee_id: uuid.UUID,
        session_id: uuid.UUID,
        data: InterviewSessionUpdate,
    ) -> InterviewSession:
        """Apply a partial update to a session, enforcing valid transitions.

        Raises :class:`InterviewSessionStateError` for a disallowed status
        transition. When a session becomes ``completed`` and no
        ``completed_at`` is supplied, it is set to the current time.
        """
        interview_session = self.get_session(owner, employee_id, session_id)

        new_status: Optional[str] = None
        completed_at: Optional[datetime] = data.completed_at

        if data.status is not None:
            current = SessionStatus(interview_session.status)
            if data.status not in _ALLOWED_TRANSITIONS[current]:
                raise InterviewSessionStateError(
                    f"Cannot transition from {current.value} to {data.status.value}."
                )
            new_status = data.status.value
            # Auto-stamp completion time if moving to completed without one.
            if data.status is SessionStatus.COMPLETED and completed_at is None:
                completed_at = datetime.now(timezone.utc)

        self.sessions.update_session(
            interview_session,
            status=new_status,
            completed_at=completed_at,
        )
        self.session.commit()
        self.session.refresh(interview_session)
        logger.info(
            "User %s updated interview session %s (status=%s)",
            owner.id,
            session_id,
            interview_session.status,
        )
        return interview_session

    def delete_session(
        self, owner: User, employee_id: uuid.UUID, session_id: uuid.UUID
    ) -> None:
        """Delete a session scoped to an employee the owner can access."""
        interview_session = self.get_session(owner, employee_id, session_id)
        self.sessions.delete_session(interview_session)
        self.session.commit()
        logger.info(
            "User %s deleted interview session %s",
            owner.id,
            session_id,
        )
