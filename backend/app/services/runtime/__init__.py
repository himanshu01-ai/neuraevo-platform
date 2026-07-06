"""Conversation Runtime package (Sprint 7.4; Sprint 12.14 adds orchestration).

Two runtimes live here, each unchanged by the other:

* :class:`ConversationRuntimeService` (Sprint 7.4) — the single runtime entry
  point for request/response AI text generation. Coordinates the Sprint 7.1
  context engine, the Sprint 7.2 prompt builder, and the Sprint 7.3
  orchestrator into one ``execute`` call — and does nothing else (no
  generation, prompt building, context assembly, persistence, memory /
  permission / tool execution, streaming, or post-processing).

* :class:`ConversationRuntime` (Sprint 12.14) — the continuous multimodal
  Conversation Runtime. Orchestrates ONLY: it maintains conversation/session
  coordination over the frozen Session SPI, classifies each normalized request
  deterministically (rule-based), routes it to the reused Sprint 12
  communication stack (text/audio/visual/document/action over one live
  session), coordinates the reused Sprint 8/9 memory services, and aggregates
  one provider-independent :class:`RuntimeResponse`. It owns no business, AI,
  provider, tool, or memory logic.
"""

from app.services.runtime.conversation_runtime import (
    ConversationRuntime,
    LiveMessagingPort,
    RuntimeContext,
)
from app.services.runtime.conversation_runtime_service import (
    ConversationRuntimeService,
)
from app.services.runtime.models import (
    RuntimeRequest,
    RuntimeRequestType,
    RuntimeResponse,
)

__all__ = [
    "ConversationRuntime",
    "ConversationRuntimeService",
    "LiveMessagingPort",
    "RuntimeContext",
    "RuntimeRequest",
    "RuntimeRequestType",
    "RuntimeResponse",
]
