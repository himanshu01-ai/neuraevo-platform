"""Multimodal AI framework models (Sprint 12.2 — provider-independent DTOs).

Strongly-typed, provider-independent request/response shapes for multimodal AI
generation. The request carries ONLY normalized data handed over from the
Sprint 12.1 Interaction layer (a modality tag, already-normalized text, the
conversation/employee identity, and a metadata dict) — never raw bytes, streams,
SDK objects, or provider objects. The response carries only plain text plus a
metadata dict. No concrete model call, SDK, HTTP, streaming, prompt building, or
provider logic lives here.

``InteractionType`` is reused from the Interaction layer rather than duplicated,
so the modality vocabulary has a single owner (no parallel enum).
"""

import uuid
from typing import Annotated, Any, Dict

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.interaction.models import InteractionType

# Trimmed, required, non-empty text (whitespace-only fails validation at 422).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class MultimodalAIRequest(BaseModel):
    """A provider-independent request for one multimodal AI generation.

    Carries only normalized data from the Interaction layer: ``interaction_type``
    tags the originating modality; ``normalized_content`` is the trimmed,
    non-empty plain-text normalization of the input; ``conversation_id`` and
    ``employee_id`` identify the owning conversation and AI employee; and
    ``metadata`` carries call-context (e.g. correlation ids) that is not content.
    ``metadata`` defaults to empty so callers may omit it. No raw bytes, streams,
    SDK objects, or provider objects ever appear here. Building this DTO performs
    no generation.
    """

    interaction_type: InteractionType
    normalized_content: _NonEmptyStr
    conversation_id: uuid.UUID
    employee_id: uuid.UUID
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MultimodalAIResponse(BaseModel):
    """A provider-independent result of a multimodal AI generation (immutable).

    ``frozen=True`` makes instances immutable, so a response cannot be mutated
    after a provider returns it. ``response_text`` is the provider's plain-text
    output (never a provider/SDK object or stream); ``metadata`` carries any
    extra plain context and defaults to empty. Provider-independent by
    construction.
    """

    model_config = ConfigDict(frozen=True)

    response_text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
