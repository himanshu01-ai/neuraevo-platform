"""Memory persistence package (Sprint 8.1).

Write-only persistence of a completed conversation turn (user + assistant
messages). No retrieval, semantic search, embeddings, importance scoring,
classification, AI/prompt/provider logic, or ownership validation — those belong
to other sprints/services.
"""

from app.services.memory.memory_persistence_service import (
    MemoryPersistenceService,
)

__all__ = ["MemoryPersistenceService"]
