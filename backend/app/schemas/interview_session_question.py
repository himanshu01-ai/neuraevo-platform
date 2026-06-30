"""Pydantic schemas for interview session-question (progress) data transfer."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.utils.constants import SessionQuestionStatus


class SessionQuestionCreate(BaseModel):
    """Input payload for linking a question to a session."""

    question_id: uuid.UUID


class SessionQuestionUpdate(BaseModel):
    """Partial-update payload for a session question."""

    status: Optional[SessionQuestionStatus] = None


class SessionQuestionResponse(BaseModel):
    """Public representation of a session question."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    question_id: uuid.UUID
    status: SessionQuestionStatus
    created_at: datetime
