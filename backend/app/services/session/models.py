"""Session framework models (Sprint 12.6 — provider-independent DTOs).

Provider-independent lifecycle DTOs for long-lived interaction sessions. They
describe only *lifecycle* — a session's identity, ownership, lifecycle state,
timestamps, and opaque metadata — and know nothing about Gemini, audio, video,
images, documents, streaming, transport, or any concrete session backend. Future
backends (Gemini Live, OpenAI Realtime, voice, screen sharing, collaborative,
MCP) reuse these shapes unchanged.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class SessionState(str, Enum):
    """Lifecycle state of a long-lived interaction session.

    - ``created``: session created but not yet active.
    - ``active``: session is live and usable.
    - ``paused``: session temporarily suspended, resumable.
    - ``closed``: session ended normally; terminal.
    - ``failed``: session ended due to an error; terminal.
    """

    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    FAILED = "failed"


class ConversationSession(BaseModel):
    """An immutable snapshot of one long-lived interaction session.

    ``session_id`` identifies the session; ``conversation_id`` and
    ``employee_id`` tie it to the owning conversation and AI employee; ``state``
    is its lifecycle state; ``created_at`` / ``updated_at`` are timestamps; and
    ``metadata`` carries opaque, provider-independent context (never transport or
    SDK objects). ``frozen=True`` makes instances immutable — a lifecycle
    transition produces a new snapshot rather than mutating one.
    """

    model_config = ConfigDict(frozen=True)

    session_id: uuid.UUID
    conversation_id: uuid.UUID
    employee_id: uuid.UUID
    state: SessionState
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Whether the session is currently ACTIVE (computed, never stored)."""
        return self.state == SessionState.ACTIVE


class SessionResult(BaseModel):
    """An immutable result of a session lifecycle operation.

    ``success`` is the outcome; ``session`` is the resulting session snapshot
    (``None`` when an operation fails or targets a missing session); ``metadata``
    carries any extra plain context and defaults to empty. ``frozen=True`` makes
    instances immutable. Provider-independent by construction.
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    session: Optional[ConversationSession] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
