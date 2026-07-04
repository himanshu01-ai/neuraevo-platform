"""Interaction framework models (Sprint 12.1 — provider-independent DTOs).

Strongly-typed, provider-independent shapes describing a single multimodal
interaction (text, voice, image, or document) inside one continuous
conversation. They carry only plain data (a modality tag, the raw content, and a
metadata dict) so no provider/SDK object is ever exposed across the interaction
boundary. No concrete modality handling, speech recognition/synthesis, OCR,
document parsing, AI inference, streaming, HTTP, SDK, or provider logic lives
here.
"""

from enum import Enum
from typing import Annotated, Any, Dict

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Trimmed, required, non-empty content (whitespace-only fails validation at 422).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class InteractionType(str, Enum):
    """The modality of a single interaction within one conversation.

    A conversation may mix these freely — the user never switches "modes". The
    interaction layer tags each request with one of them so a later provider can
    normalize it; this sprint only defines the vocabulary.

    - ``text``: a typed text message.
    - ``voice``: spoken audio input.
    - ``image``: a still image.
    - ``document``: a document (e.g. PDF, doc) supplied to the conversation.
    """

    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    DOCUMENT = "document"


class InteractionRequest(BaseModel):
    """A provider-independent request describing one incoming interaction.

    ``interaction_type`` tags the modality; ``content`` is the raw, trimmed,
    non-empty payload reference for that modality (validated so whitespace-only
    input is rejected); and ``metadata`` carries call-context (e.g. correlation
    ids, mime hints) that is not itself content. ``metadata`` defaults to empty
    so callers may omit it. Building this DTO performs no processing.
    """

    interaction_type: InteractionType
    content: _NonEmptyStr
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InteractionResult(BaseModel):
    """A provider-independent result of processing one interaction (immutable).

    ``frozen=True`` makes instances immutable, so a result cannot be mutated
    after a provider returns it. ``interaction_type`` echoes the handled
    modality; ``normalized_content`` is the provider's plain-text normalization
    of the input (never a provider/SDK object); ``metadata`` carries any extra
    plain context and defaults to empty. Provider-independent by construction.
    """

    model_config = ConfigDict(frozen=True)

    interaction_type: InteractionType
    normalized_content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
