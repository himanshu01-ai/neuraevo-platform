"""Pydantic schemas for interview answer data transfer."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class InterviewAnswerCreate(BaseModel):
    """Input payload for creating an answer.

    ``question_id`` is taken from the path, not the body.
    """

    answer_text: Optional[str] = Field(default=None, max_length=10000)


class InterviewAnswerUpdate(BaseModel):
    """Partial-update payload for an answer."""

    answer_text: Optional[str] = Field(default=None, max_length=10000)


class InterviewAnswerResponse(BaseModel):
    """Public representation of an answer."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_id: uuid.UUID
    answer_text: Optional[str] = None
    created_at: datetime
