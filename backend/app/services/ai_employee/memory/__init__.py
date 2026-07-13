"""Memory Orchestrator package (Sprint 16.6 — decide what to remember/retrieve).

Adds the Memory Orchestrator: it decides what information should be remembered and
retrieved, while the Persistence Layer remains the only storage layer. It follows
the flow ``AIEmployee -> MemoryOrchestrator -> {MemoryPolicy, MemoryClassifier,
MemoryRetriever, PersistenceManager}``:

* the immutable DTOs :class:`MemoryRecord`, :class:`MemoryDecision`,
  :class:`MemoryQuery`, and :class:`MemorySummary`, plus the
  :class:`MemoryCategory` and :class:`MemoryImportance` enums and the
  :class:`MemoryNotFoundError`;
* the :class:`MemoryPolicy` abstraction with :class:`RuleBasedMemoryPolicy`
  (decide whether to remember);
* the :class:`MemoryClassifier` abstraction with :class:`RuleBasedMemoryClassifier`
  (determine importance);
* the deterministic in-memory :class:`MemoryRetriever` (exact-match retrieval — no
  embeddings, vectors, or semantic search); and
* the :class:`MemoryOrchestrator` engine, which always routes durable workflow-state
  storage through the Sprint 16.5 :class:`PersistenceManager`.

This package is strictly additive to — and leaves untouched — every frozen sprint
through 16.5, and it imports no capability module, no vector store, no embeddings,
and no LLM API.
"""

from app.services.ai_employee.memory.classifier import (
    MemoryClassifier,
    RuleBasedMemoryClassifier,
)
from app.services.ai_employee.memory.models import (
    IMPORTANCE_ORDER,
    MemoryCategory,
    MemoryDecision,
    MemoryImportance,
    MemoryLayerError,
    MemoryNotFoundError,
    MemoryQuery,
    MemoryRecord,
    MemorySummary,
)
from app.services.ai_employee.memory.orchestrator import MemoryOrchestrator
from app.services.ai_employee.memory.policy import (
    MemoryPolicy,
    RuleBasedMemoryPolicy,
)
from app.services.ai_employee.memory.retriever import MemoryRetriever

__all__ = [
    # DTOs & enums
    "MemoryRecord",
    "MemoryDecision",
    "MemoryQuery",
    "MemorySummary",
    "MemoryCategory",
    "MemoryImportance",
    "IMPORTANCE_ORDER",
    # errors
    "MemoryLayerError",
    "MemoryNotFoundError",
    # policy / classifier / retriever
    "MemoryPolicy",
    "RuleBasedMemoryPolicy",
    "MemoryClassifier",
    "RuleBasedMemoryClassifier",
    "MemoryRetriever",
    # orchestrator
    "MemoryOrchestrator",
]
