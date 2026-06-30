"""Pydantic schemas for assembled conversation context.

A reusable, read-only structure that future AI generation sprints can consume.
This sprint performs no AI generation — it only shapes conversation history.
"""

import uuid
from typing import List

from pydantic import BaseModel

from app.utils.constants import MessageRole


class ConversationContextMessage(BaseModel):
    """A single message reduced to the fields needed for context."""

    role: MessageRole
    content: str


class ConversationContextResponse(BaseModel):
    """Assembled context: conversation history in chronological order."""

    employee_id: uuid.UUID
    conversation_id: uuid.UUID
    message_count: int
    messages: List[ConversationContextMessage]
