"""Pydantic schemas for interview question data transfer."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InterviewQuestionCreate(BaseModel):
    """Input payload for creating an interview question.

    ``blueprint_id`` is resolved from the employee's blueprint, not the body.
    """

    question_text: str = Field(min_length=1, max_length=10000)
    question_order: int


class InterviewQuestionResponse(BaseModel):
    """Public representation of an interview question."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    blueprint_id: uuid.UUID
    question_text: str
    question_order: int
    created_at: datetime
