"""Pydantic schema for conversation generation (preview).

Sprint 5D is generation-preview only: the reply is returned, never persisted.
"""

from pydantic import BaseModel


class ConversationGenerationResponse(BaseModel):
    """A generated (non-persisted) assistant reply."""

    reply: str
