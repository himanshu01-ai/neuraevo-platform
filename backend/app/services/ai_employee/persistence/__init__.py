"""Persistence Layer package (Sprint 16.5 — production-grade persistence).

Upgrades the Sprint 16.2 PersistenceManager abstraction additively into a
production-grade Persistence Layer that stores *platform state* only — no database,
no AI memory, no embeddings, no vector store. It follows the flow
``WorkflowInstance -> PersistenceManager -> PersistenceRepository ->
PersistenceSnapshot``:

* the immutable DTOs :class:`PersistenceSnapshot`, :class:`PersistenceVersion`,
  :class:`PersistenceMetadata`, :class:`PersistenceHistory`, and
  :class:`PersistenceResult`, plus the :class:`SnapshotType` enum;
* the deterministic validation errors (:class:`PersistenceError` and its
  subclasses);
* the :class:`PersistenceRepository` abstraction with the in-memory
  :class:`InMemoryPersistenceRepository` (the repository owns storage); and
* the :class:`PersistenceManager` engine (the manager owns persistence decisions —
  versioning, snapshotting, validation).

This package is strictly additive to — and leaves untouched — every frozen sprint
through 16.4, and it imports no capability module.
"""

from app.services.ai_employee.persistence.manager import PersistenceManager
from app.services.ai_employee.persistence.models import (
    DuplicatePersistenceError,
    InvalidRestoreError,
    InvalidSnapshotError,
    MissingVersionError,
    MissingWorkflowError,
    PersistenceError,
    PersistenceHistory,
    PersistenceMetadata,
    PersistenceResult,
    PersistenceSnapshot,
    PersistenceVersion,
    SnapshotType,
)
from app.services.ai_employee.persistence.repository import (
    InMemoryPersistenceRepository,
    PersistenceRepository,
)

__all__ = [
    # DTOs & enum
    "PersistenceSnapshot",
    "PersistenceVersion",
    "PersistenceMetadata",
    "PersistenceHistory",
    "PersistenceResult",
    "SnapshotType",
    # validation errors
    "PersistenceError",
    "MissingWorkflowError",
    "MissingVersionError",
    "DuplicatePersistenceError",
    "InvalidRestoreError",
    "InvalidSnapshotError",
    # repository + engine
    "PersistenceRepository",
    "InMemoryPersistenceRepository",
    "PersistenceManager",
]
