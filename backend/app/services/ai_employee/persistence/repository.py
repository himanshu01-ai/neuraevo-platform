"""Persistence repository (Sprint 16.5 — storage abstraction + in-memory store).

Defines the :class:`PersistenceRepository` abstraction and its basic implementation
:class:`InMemoryPersistenceRepository`. The abstraction is the seam a later Sprint
16.x storage provider plugs into; the Sprint 16.5 implementation keeps versioned
snapshots in a deterministic in-memory dictionary — no database, SQLite,
PostgreSQL, Redis, or cloud storage.

The repository *owns storage*: it stores and reads :class:`PersistenceVersion`
records and enforces version integrity (a duplicate version is rejected). It makes
no persistence *decisions* (which version is next, what to snapshot) — those belong
to the manager. Deterministic and instance-scoped (never a singleton or static
store). Strictly additive to Sprints 1.x–16.4.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from app.services.ai_employee.persistence.models import (
    DuplicatePersistenceError,
    PersistenceVersion,
)


class PersistenceRepository(ABC):
    """Abstraction that stores versioned snapshots (owns storage, not decisions).

    An implementation ``save`` a version (rejecting a duplicate version number),
    ``get`` a specific version, list all ``versions`` (ascending), read the
    ``latest``, ``delete`` a workflow's versions, and report ``exists``.
    Implementations must be deterministic; the Sprint 16.5 implementation is
    in-memory only — a durable store belongs to a later Sprint 16.x.
    """

    @abstractmethod
    def save(self, version: PersistenceVersion) -> None:
        """Store ``version``; raise :class:`DuplicatePersistenceError` if it exists."""

    @abstractmethod
    def get(
        self, workflow_id: str, version: int
    ) -> Optional[PersistenceVersion]:
        """Return the stored version for ``(workflow_id, version)`` or ``None``."""

    @abstractmethod
    def versions(self, workflow_id: str) -> List[PersistenceVersion]:
        """Return all stored versions for ``workflow_id`` in ascending order."""

    @abstractmethod
    def latest(self, workflow_id: str) -> Optional[PersistenceVersion]:
        """Return the highest-numbered stored version for ``workflow_id`` or ``None``."""

    @abstractmethod
    def delete(self, workflow_id: str) -> bool:
        """Delete all stored versions for ``workflow_id``; return whether any existed."""

    @abstractmethod
    def exists(self, workflow_id: str) -> bool:
        """Return whether any version is stored for ``workflow_id``."""


class InMemoryPersistenceRepository(PersistenceRepository):
    """Basic storage — keeps versioned snapshots in an in-memory dict, no database.

    Holds a per-workflow mapping of version number → :class:`PersistenceVersion`
    (instance state, never a module-level global, so it is not a singleton).
    ``save`` rejects a duplicate version number for integrity; the reads return
    deterministic, ascending results; ``delete`` drops a workflow's versions.
    Performs no database, file, or network I/O.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Dict[int, PersistenceVersion]] = {}

    def save(self, version: PersistenceVersion) -> None:
        """Store ``version`` (rejecting a duplicate version number)."""
        workflow = self._store.setdefault(version.workflow_id, {})
        if version.version in workflow:
            raise DuplicatePersistenceError(
                f"version {version.version} already exists for "
                f"{version.workflow_id}"
            )
        workflow[version.version] = version

    def get(
        self, workflow_id: str, version: int
    ) -> Optional[PersistenceVersion]:
        """Return the stored version for ``(workflow_id, version)`` or ``None``."""
        return self._store.get(workflow_id, {}).get(version)

    def versions(self, workflow_id: str) -> List[PersistenceVersion]:
        """Return all stored versions for ``workflow_id`` in ascending order."""
        workflow = self._store.get(workflow_id, {})
        return [workflow[number] for number in sorted(workflow)]

    def latest(self, workflow_id: str) -> Optional[PersistenceVersion]:
        """Return the highest-numbered stored version for ``workflow_id`` or ``None``."""
        workflow = self._store.get(workflow_id, {})
        if not workflow:
            return None
        return workflow[max(workflow)]

    def delete(self, workflow_id: str) -> bool:
        """Delete all stored versions for ``workflow_id``; return whether any existed."""
        existed = bool(self._store.get(workflow_id))
        self._store.pop(workflow_id, None)
        return existed

    def exists(self, workflow_id: str) -> bool:
        """Return whether any version is stored for ``workflow_id``."""
        return bool(self._store.get(workflow_id))
