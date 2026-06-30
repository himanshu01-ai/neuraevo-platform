"""Pydantic schemas for the assembled prompt package (Sprint 7.2 Prompt Builder).

A provider-agnostic, structured representation of a ready-to-assemble prompt,
produced deterministically from a :class:`RuntimeAIContext`. These are read-only
DTOs: no provider/SDK-specific format, no AI, no execution — just data that a
later sprint can hand to a provider.
"""

import uuid
from typing import List

from pydantic import BaseModel


class PromptMessage(BaseModel):
    """A single provider-agnostic prompt message (role + content).

    ``role`` is one of the neutral values ``"user"`` / ``"assistant"`` /
    ``"system"`` — not tied to any vendor's message schema.
    """

    role: str
    content: str


class PromptMetadata(BaseModel):
    """Read-only transparency metadata describing the assembled package."""

    employee_id: uuid.UUID
    conversation_id: uuid.UUID
    memory_count: int
    message_count: int


class PromptPackage(BaseModel):
    """A deterministic, provider-agnostic prompt assembled from runtime context.

    ``system_prompt`` carries the assembled instruction block (identity,
    blueprint, personality, language, memories); ``messages`` carries the recent
    conversation followed by the current user input; ``language`` is surfaced for
    downstream use; ``metadata`` is read-only transparency information.
    """

    system_prompt: str
    messages: List[PromptMessage]
    language: str
    metadata: PromptMetadata
