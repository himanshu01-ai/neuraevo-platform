"""Pydantic schemas for the provider-agnostic AI response (Sprint 7.3).

The result of a single AI generation, decoupled from any vendor's response
format. Read-only DTOs: no provider types leak through — only the generated
text and provenance metadata. ``provider`` is the neutral provider name (e.g.
``"anthropic"``), never a vendor SDK object.
"""

import uuid

from pydantic import BaseModel


class AIResponseMetadata(BaseModel):
    """Provider-agnostic provenance metadata for a generated response."""

    provider: str
    language: str
    employee_id: uuid.UUID
    conversation_id: uuid.UUID
    prompt_message_count: int


class AIResponse(BaseModel):
    """Provider-agnostic result of one AI generation.

    ``content`` is the model's reply, returned verbatim (the orchestrator does
    no post-processing). ``metadata`` carries neutral provenance information.
    """

    content: str
    metadata: AIResponseMetadata
