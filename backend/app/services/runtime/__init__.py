"""Conversation Runtime package (Sprint 7.4).

The single runtime entry point for AI execution. Coordinates the Sprint 7.1
context engine, the Sprint 7.2 prompt builder, and the Sprint 7.3 orchestrator
into one ``execute`` call — and does nothing else (no generation, prompt
building, context assembly, persistence, memory/permission/tool execution,
streaming, or post-processing).
"""

from app.services.runtime.conversation_runtime_service import (
    ConversationRuntimeService,
)

__all__ = ["ConversationRuntimeService"]
