"""Request schema for the Conversation Runtime API (Sprint 7.5).

Input DTO for generating an AI response in an existing conversation. The
``conversation_id`` is a path parameter and the caller is taken from the auth
context; this body carries the employee to respond as and the current user
input. Read-only request DTO — no business logic.
"""

import uuid

from pydantic import BaseModel, Field


class GenerateConversationRequest(BaseModel):
    """Body for the runtime generation endpoint."""

    employee_id: uuid.UUID
    message: str = Field(min_length=1, max_length=10000)
