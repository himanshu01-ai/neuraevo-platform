"""Persistence manager (Sprint 16.2 — persistence abstraction + in-memory store).

Defines the :class:`PersistenceManager` abstraction and its basic implementation
:class:`InMemoryPersistenceManager`. The abstraction lets later Sprint 16.x
implementations (PostgreSQL, Redis, file) plug in behind ``save_instance``/
``load_instance``/``delete_instance`` without any change to the lifecycle
manager. The basic implementation keeps instances in a deterministic in-memory
dictionary — no database, no I/O.

Each save produces an immutable :class:`WorkflowSnapshot` with a deterministic
sequence and id; a load returns the latest saved :class:`WorkflowInstance` (or
``None``); a delete reports whether the instance existed. Deterministic given the
order of calls. Strictly additive to Sprints 1.x–16.1.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from app.services.ai_employee.platform_models import (
    WorkflowInstance,
    WorkflowSnapshot,
)


class PersistenceManager(ABC):
    """Abstraction for persisting delegated jobs (no database, no external I/O).

    Implementations ``save_instance`` (returning a :class:`WorkflowSnapshot`),
    ``load_instance`` (returning the stored :class:`WorkflowInstance` or ``None``),
    and ``delete_instance`` (reporting whether it existed). Implementations must be
    deterministic; the Sprint 16.2 basic implementation is in-memory only — a
    durable store belongs to a later Sprint 16.x.
    """

    @abstractmethod
    def save_instance(self, instance: WorkflowInstance) -> WorkflowSnapshot:
        """Persist ``instance`` and return the :class:`WorkflowSnapshot` for it."""

    @abstractmethod
    def load_instance(
        self, instance_id: str
    ) -> Optional[WorkflowInstance]:
        """Return the persisted instance for ``instance_id`` (or ``None``)."""

    @abstractmethod
    def delete_instance(self, instance_id: str) -> bool:
        """Delete the persisted instance; return whether it existed."""


class InMemoryPersistenceManager(PersistenceManager):
    """Basic persistence store — keeps instances in an in-memory dict, no database.

    Holds instances keyed by ``instance_id`` and a monotonic save counter (instance
    state, never a module-level global, so it is not a singleton). Each
    ``save_instance`` overwrites the stored instance (latest wins) and returns a
    :class:`WorkflowSnapshot` carrying the deterministic next sequence and id.
    Deterministic given the order of calls; performs no database or file I/O.
    """

    def __init__(self) -> None:
        self._instances: Dict[str, WorkflowInstance] = {}
        self._sequence = 0

    def save_instance(self, instance: WorkflowInstance) -> WorkflowSnapshot:
        """Store ``instance`` (latest wins) and return its snapshot."""
        self._sequence += 1
        snapshot = WorkflowSnapshot(
            snapshot_id=f"snapshot-{instance.instance_id}-{self._sequence}",
            workflow_instance_id=instance.instance_id,
            instance=instance,
            sequence=self._sequence,
        )
        self._instances[instance.instance_id] = instance
        return snapshot

    def load_instance(
        self, instance_id: str
    ) -> Optional[WorkflowInstance]:
        """Return the stored instance for ``instance_id`` (or ``None``)."""
        return self._instances.get(instance_id)

    def delete_instance(self, instance_id: str) -> bool:
        """Delete the stored instance; return whether it was present."""
        existed = instance_id in self._instances
        self._instances.pop(instance_id, None)
        return existed
