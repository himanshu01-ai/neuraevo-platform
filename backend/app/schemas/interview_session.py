"""Pydantic schemas for interview session data transfer."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.utils.constants import SessionStatus


class InterviewSessionCreate(BaseModel):
    """Input payload for creating a session. Status defaults to ``created``."""

    status: SessionStatus = SessionStatus.CREATED


class InterviewSessionUpdate(BaseModel):
    """Partial-update payload for a session. Unset fields are unchanged."""

    status: Optional[SessionStatus] = None
    completed_at: Optional[datetime] = None


class InterviewSessionResponse(BaseModel):
    """Public representation of an interview session."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    status: SessionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
