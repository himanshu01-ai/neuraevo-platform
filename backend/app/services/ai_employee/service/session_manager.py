"""Session manager (Sprint 16.10 — manage AI Employee service sessions).

Defines :class:`SessionManager`, the component that manages the service's sessions:
it creates a session for each submitted task, loads and closes sessions, lists them,
and tracks which are active. A session is a lightweight, deterministic record of an
AI Employee engagement — it holds no execution state and runs nothing.

It is a plain in-memory ledger keyed by a deterministic session id: it decides
nothing about task assignment or execution (the service and the :class:`AIEmployee`
do). It never touches the Workflow Coordinator, a capability, a repository, a
database, an LLM provider, a thread, or the network. Its only state is the in-memory
ledger plus a deterministic sequence counter. Strictly additive to Sprints 1.x–16.9,
whose modules are left untouched.
"""

from typing import Dict, List

from app.services.ai_employee.service.models import (
    SessionInfo,
    SessionNotFoundException,
    SessionStatus,
)


class SessionManager:
    """In-memory ledger of service sessions (ledger only, no execution).

    ``create`` opens a new ``ACTIVE`` session with a deterministic id; ``load``
    returns a session (raising :class:`SessionNotFoundException` when absent);
    ``close`` transitions a session to ``CLOSED``; ``list`` returns every session in
    creation order; and ``active`` returns only the open ones. It holds the ledger
    and a deterministic sequence counter — it assigns, delegates, and executes
    nothing.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionInfo] = {}
        self._sequence = 0

    def create(self, employee_id: str, task_id: str) -> SessionInfo:
        """Open and return a new ``ACTIVE`` session for ``employee_id``/``task_id``.

        The session id is derived deterministically from the employee, task, and a
        sequence ordinal so repeated creates stay distinct and ordered. Nothing is
        executed.
        """
        sequence = self._next()
        session_id = f"session-{employee_id}-{task_id}-{sequence}"
        session = SessionInfo(
            session_id=session_id,
            employee_id=employee_id,
            task_id=task_id,
            status=SessionStatus.ACTIVE,
            active=True,
            created_at_sequence=sequence,
        )
        self._sessions[session_id] = session
        return session

    def load(self, session_id: str) -> SessionInfo:
        """Return the session with ``session_id``.

        Raises :class:`SessionNotFoundException` when no such session exists.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundException(f"no such session: {session_id}")
        return session

    def close(self, session_id: str) -> SessionInfo:
        """Close the session with ``session_id`` and return the ``CLOSED`` record.

        Raises :class:`SessionNotFoundException` when no such session exists.
        Closing an already-closed session is idempotent (it stays ``CLOSED``).
        """
        session = self.load(session_id)
        closed = session.model_copy(
            update={
                "status": SessionStatus.CLOSED,
                "active": False,
                "closed_at_sequence": self._next(),
            }
        )
        self._sessions[session_id] = closed
        return closed

    def list(self) -> List[SessionInfo]:
        """Return every session in deterministic creation order."""
        return list(self._sessions.values())

    def active(self) -> List[SessionInfo]:
        """Return only the sessions that are currently ``ACTIVE``."""
        return [s for s in self._sessions.values() if s.active]

    def _next(self) -> int:
        """Return the next deterministic sequence ordinal."""
        self._sequence += 1
        return self._sequence
