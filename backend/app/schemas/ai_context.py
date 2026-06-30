"""Pydantic schemas for the complete AI context (input builder).

Assembles the blueprint, memory context, and conversation context into one
structure that future AI generation will consume. The section types reuse the
existing DTOs (by subclassing) so no fields are duplicated. Read-only — no AI
generation here.
"""

import uuid

from pydantic import BaseModel

from app.schemas.blueprint import BlueprintResponse
from app.schemas.conversation_context import ConversationContextResponse
from app.schemas.memory_context import MemoryContextResponse


class BlueprintSection(BlueprintResponse):
    """Blueprint portion of the AI context (reuses ``BlueprintResponse``)."""


class MemorySection(MemoryContextResponse):
    """Memory portion of the AI context (reuses ``MemoryContextResponse``)."""


class ConversationSection(ConversationContextResponse):
    """Conversation portion (reuses ``ConversationContextResponse``)."""


class AIContextResponse(BaseModel):
    """The complete assembled AI context for an employee conversation."""

    employee_id: uuid.UUID
    conversation_id: uuid.UUID
    blueprint: BlueprintSection
    memory: MemorySection
    conversation: ConversationSection
