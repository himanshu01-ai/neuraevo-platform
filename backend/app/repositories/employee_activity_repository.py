"""Data-access layer for :class:`~app.models.employee_activity.EmployeeActivityEvent`.

Persistence only. The history is append-only, so this exposes an append and
reads — there is no update or delete: an event records that something happened,
and that does not stop being true.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.employee_activity import EmployeeActivityEvent


class EmployeeActivityRepository:
    """Append-and-read accessors for employee activity."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_employee(
        self, employee_id: uuid.UUID, *, skip: int = 0, limit: int = 100
    ) -> Sequence[EmployeeActivityEvent]:
        """Newest first — a history is read from the most recent event back."""
        stmt = (
            select(EmployeeActivityEvent)
            .where(EmployeeActivityEvent.employee_id == employee_id)
            .order_by(EmployeeActivityEvent.sequence.desc())
            .offset(skip)
            .limit(limit)
        )
        return self.session.scalars(stmt).all()

    def next_sequence(self, employee_id: uuid.UUID) -> int:
        """The next per-employee ordinal."""
        stmt = select(func.max(EmployeeActivityEvent.sequence)).where(
            EmployeeActivityEvent.employee_id == employee_id
        )
        current: Optional[int] = self.session.scalar(stmt)
        return (current or 0) + 1

    def append(
        self, employee_id: uuid.UUID, *, kind: str, summary: str
    ) -> EmployeeActivityEvent:
        event = EmployeeActivityEvent(
            employee_id=employee_id,
            kind=kind,
            summary=summary,
            sequence=self.next_sequence(employee_id),
        )
        self.session.add(event)
        self.session.flush()
        return event

