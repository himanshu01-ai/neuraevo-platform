"""Pydantic schemas for conversation message data transfer.

Messages are immutable after creation, so there is no update schema.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.utils.constants import MessageRole

# Trimmed, required, non-empty (after trim) content. ``strip_whitespace`` runs
# before ``min_length``, so whitespace-only input fails validation (422).
MessageContent = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100000),
]


class MessageCreate(BaseModel):
    """Input payload for creating a message.

    ``conversation_id`` is taken from the path, and ``created_at`` is server
    generated — neither is accepted from the client.
    """

    role: MessageRole
    content: MessageContent


class MessageResponse(BaseModel):
    """Public representation of a message."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime
