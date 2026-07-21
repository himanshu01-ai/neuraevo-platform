"""Pydantic schemas for conversation message data transfer.

Messages are immutable after creation, so there is no update schema.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.utils.constants import MessageChannel, MessageRole

# Trimmed, required, non-empty (after trim) content. ``strip_whitespace`` runs
# before ``min_length``, so whitespace-only input fails validation (422).
MessageContent = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100000),
]


class MessageCreate(BaseModel):
    """Input payload for creating a message.

    ``conversation_id`` is taken from the path, and ``created_at`` is server
    generated — neither is accepted from the client. ``channel`` defaults to
    ``text`` so existing callers are unaffected; a spoken turn sends ``voice``.
    """

    role: MessageRole
    content: MessageContent
    channel: MessageChannel = MessageChannel.TEXT


class MessageResponse(BaseModel):
    """Public representation of a message."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    # Defaulted so a message-shaped object without the field reads as ``text``
    # (every real ``Message`` row carries a channel; only in-memory shapes that
    # predate voice omit it). Keeps the response backwards compatible for the
    # runtime-context normalisation that validates history into this schema.
    channel: MessageChannel = MessageChannel.TEXT
    created_at: datetime
