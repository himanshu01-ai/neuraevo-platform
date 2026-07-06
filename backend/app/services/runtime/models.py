"""Conversation Runtime models (Sprint 12.14 — provider-independent DTOs).

Strongly-typed, provider-independent shapes describing one runtime turn: the
normalized user input (:class:`RuntimeRequest`), the deterministic request-type
vocabulary (:class:`RuntimeRequestType`), and the single aggregated result
(:class:`RuntimeResponse`). They carry only plain data — no SDK object, no
provider structure, and no live-session handle ever crosses the runtime
boundary.

The multimodal payload shapes (:class:`VisualInput`, :class:`DocumentInput`,
:class:`ActionRequest`, :class:`ActionResult`) are REUSED unchanged from where
Sprints 12.11–12.13 defined them. They are themselves provider-independent
(pydantic-only, frozen, no SDK types); importing them here is reuse, not
duplication — no parallel payload vocabulary is introduced.
"""

import uuid
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.session.providers.gemini_live_provider import (
    ActionRequest,
    ActionResult,
    DocumentInput,
    VisualInput,
)


class RuntimeRequestType(str, Enum):
    """The classified type of one normalized runtime request.

    Assigned by the runtime's rule-based ``_RequestClassifier`` — never by an
    AI/LLM — so runtime routing stays deterministic.

    - ``text``: a plain text turn.
    - ``audio``: a raw PCM audio chunk turn.
    - ``visual``: a visual input (image) turn.
    - ``document``: a document intelligence turn.
    - ``action``: an explicit tool/action execution request.
    - ``unknown``: the request carries no classifiable payload (not routable).
    """

    TEXT = "text"
    AUDIO = "audio"
    VISUAL = "visual"
    DOCUMENT = "document"
    ACTION = "action"
    UNKNOWN = "unknown"


class RuntimeRequest(BaseModel):
    """One normalized, provider-independent user request to the runtime.

    ``conversation_id`` / ``employee_id`` identify the owning conversation and
    AI employee (the runtime keys its single live session on them). Exactly ONE
    payload field is expected to be set — ``text``, ``audio``, ``visual``,
    ``document``, or ``action`` — and the rule-based classifier maps it to
    exactly one :class:`RuntimeRequestType` (anything else classifies as
    ``UNKNOWN``). ``metadata`` carries opaque call context (e.g. a ``model``
    hint forwarded verbatim to session creation) and is never interpreted by
    the runtime. Building this DTO performs no processing.
    """

    conversation_id: uuid.UUID
    employee_id: uuid.UUID
    text: Optional[str] = None
    audio: Optional[bytes] = None
    visual: Optional[VisualInput] = None
    document: Optional[DocumentInput] = None
    action: Optional[ActionRequest] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RuntimeResponse(BaseModel):
    """The single aggregated, provider-independent result of one runtime turn.

    Built ONLY by the runtime's ``_ResponseAssembler``: ``request_type`` echoes
    the classification; ``session_id`` / ``conversation_id`` / ``employee_id``
    tie the turn to its (reused) live session and owners; ``text`` carries a
    textual reply (text/visual/document turns); ``audio`` carries raw reply
    bytes (audio turns); ``action_result`` carries the Sprint 11 pipeline
    outcome (action turns); ``metadata`` carries plain orchestration context
    (e.g. ``session_reused``, ``memory_context_messages``). Never a provider
    DTO wrapper, never an SDK object. ``frozen=True`` makes instances
    immutable.
    """

    model_config = ConfigDict(frozen=True)

    request_type: RuntimeRequestType
    session_id: uuid.UUID
    conversation_id: uuid.UUID
    employee_id: uuid.UUID
    text: Optional[str] = None
    audio: Optional[bytes] = None
    action_result: Optional[ActionResult] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
