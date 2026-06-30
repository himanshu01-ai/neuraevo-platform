"""AI Context Engine package (Sprint 7.1).

Runtime context assembly performed *before* any AI generation. Reuses existing
domain services for loading and ownership validation; introduces no parallel
ownership system and no persistence.
"""

from app.services.context.ai_context_engine_service import (
    AIContextEngineService,
)

__all__ = ["AIContextEngineService"]
