"""Pydantic schemas for conversation data transfer."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.utils.constants import ConversationStatus


class ConversationCreate(BaseModel):
    """Input payload for creating a conversation. Status defaults to active."""

    title: str = Field(min_length=1, max_length=255)


class ConversationUpdate(BaseModel):
    """Partial-update payload for a conversation. Unset fields are unchanged."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    status: Optional[ConversationStatus] = None


class ConversationResponse(BaseModel):
    """Public representation of a conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    title: str
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
