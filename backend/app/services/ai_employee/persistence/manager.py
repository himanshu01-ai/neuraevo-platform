"""Persistence engine (Sprint 16.5 — the production-grade PersistenceManager).

Defines :class:`PersistenceManager`, the coordinator of the Persistence Layer. It
follows the locked flow ``WorkflowInstance -> PersistenceManager ->
PersistenceRepository -> PersistenceSnapshot`` and coordinates the injected
:class:`PersistenceRepository`:

    snapshot   (build an immutable capture of platform state)
    save       (assign the next version, store a new PersistenceVersion)
    load       (return the latest persisted instance)
    exists     (whether any version is persisted)
    delete     (drop all versions)
    version    (the latest version number)
    latest / history / restore   (deterministic version history)

It *owns persistence decisions* — which version is next, what to capture, and every
validation — but *never contains storage logic* (the repository stores) and never
executes a workflow or capability. Constructor injection only; its only mutable
state is a deterministic sequence counter (the repository holds the versions) — no
static, singleton, or service-locator state. Fully deterministic (no clock, UUID,
network, SDK, or database). Strictly additive to Sprints 1.x–16.4, whose modules
are left untouched.
"""

from typing import Any, List, Optional

from app.services.ai_employee.persistence.models import (
    InvalidRestoreError,
    InvalidSnapshotError,
    MissingVersionError,
    MissingWorkflowError,
    PersistenceHistory,
    PersistenceMetadata,
    PersistenceResult,
    PersistenceSnapshot,
    PersistenceVersion,
    SnapshotType,
)
from app.services.ai_employee.persistence.repository import (
    PersistenceRepository,
)
from app.services.ai_employee.platform_models import WorkflowInstance


class PersistenceManager:
    """Coordinates persistence over an injected repository (decisions, not storage).

    Constructed with an injected :class:`PersistenceRepository` (constructor
    injection; it instantiates none). It builds immutable snapshots, assigns the
    next version, validates every operation deterministically, and reads the version
    history — delegating all storage to the repository. It holds a deterministic
    sequence counter only; it executes no workflow, no capability, and contains no
    storage logic.
    """

    def __init__(self, repository: PersistenceRepository) -> None:
        self.repository = repository
        self._sequence = 0

    # --- snapshot construction ------------------------------------------
    def snapshot(
        self,
        instance: WorkflowInstance,
        snapshot_type: SnapshotType = SnapshotType.FULL,
        approval_history: Optional[List[Any]] = None,
        notification_history: Optional[List[Any]] = None,
        version: int = 0,
    ) -> PersistenceSnapshot:
        """Build an immutable :class:`PersistenceSnapshot` of ``instance`` (no save).

        Captures the workflow instance, its progress, its metadata, and the supplied
        approval/notification history into a deterministic snapshot tagged with
        ``snapshot_type`` and ``version`` (0 for a standalone, unsaved snapshot).
        Raises :class:`InvalidSnapshotError` when no instance is given. Nothing is
        stored or executed.
        """
        if instance is None:
            raise InvalidSnapshotError("cannot snapshot a missing instance")
        sequence = self._next()
        workflow_id = instance.instance_id
        metadata = PersistenceMetadata(
            workflow_id=workflow_id,
            version=version,
            snapshot_type=snapshot_type,
            created_at_sequence=sequence,
        )
        return PersistenceSnapshot(
            snapshot_id=f"snapshot-{workflow_id}-{version}-{sequence}",
            workflow_id=workflow_id,
            snapshot_type=snapshot_type,
            instance=instance,
            progress=instance.progress,
            approval_history=list(approval_history or []),
            notification_history=list(notification_history or []),
            workflow_metadata=dict(instance.instance_metadata),
            metadata=metadata,
            created_at_sequence=sequence,
        )

    # --- core operations -------------------------------------------------
    def save(
        self,
        instance: WorkflowInstance,
        snapshot_type: SnapshotType = SnapshotType.FULL,
        approval_history: Optional[List[Any]] = None,
        notification_history: Optional[List[Any]] = None,
    ) -> PersistenceResult:
        """Persist ``instance`` as the next version and return the result.

        The manager decides the next version (latest + 1, or 1 for a first save —
        so each save creates a new version), builds the snapshot, and hands a new
        :class:`PersistenceVersion` to the repository (which rejects a duplicate
        version). Raises :class:`InvalidSnapshotError` when no instance is given.
        Nothing is executed.
        """
        if instance is None:
            raise InvalidSnapshotError("cannot save a missing instance")
        workflow_id = instance.instance_id
        latest = self.repository.latest(workflow_id)
        next_version = latest.version + 1 if latest is not None else 1
        snapshot = self.snapshot(
            instance,
            snapshot_type,
            approval_history,
            notification_history,
            version=next_version,
        )
        record = PersistenceVersion(
            workflow_id=workflow_id,
            version=next_version,
            snapshot=snapshot,
            created_at_sequence=self._next(),
        )
        self.repository.save(record)
        return PersistenceResult(
            workflow_id=workflow_id,
            operation="save",
            success=True,
            version=next_version,
            snapshot=snapshot,
        )

    def load(self, workflow_id: str) -> WorkflowInstance:
        """Return the latest persisted :class:`WorkflowInstance` for ``workflow_id``.

        Raises :class:`MissingWorkflowError` when nothing is persisted for it.
        """
        latest = self.repository.latest(workflow_id)
        if latest is None:
            raise MissingWorkflowError(
                f"no persisted workflow: {workflow_id}"
            )
        return latest.snapshot.instance

    def exists(self, workflow_id: str) -> bool:
        """Return whether any version is persisted for ``workflow_id``."""
        return self.repository.exists(workflow_id)

    def delete(self, workflow_id: str) -> PersistenceResult:
        """Delete every persisted version for ``workflow_id`` and return the result.

        Raises :class:`MissingWorkflowError` when nothing is persisted for it.
        """
        if not self.repository.exists(workflow_id):
            raise MissingWorkflowError(
                f"no persisted workflow: {workflow_id}"
            )
        self.repository.delete(workflow_id)
        return PersistenceResult(
            workflow_id=workflow_id, operation="delete", success=True
        )

    # --- versioning ------------------------------------------------------
    def version(self, workflow_id: str) -> int:
        """Return the latest version number for ``workflow_id``.

        Raises :class:`MissingWorkflowError` when nothing is persisted for it.
        """
        return self.latest(workflow_id).version

    def latest(self, workflow_id: str) -> PersistenceVersion:
        """Return the latest :class:`PersistenceVersion` for ``workflow_id``.

        Raises :class:`MissingWorkflowError` when nothing is persisted for it.
        """
        latest = self.repository.latest(workflow_id)
        if latest is None:
            raise MissingWorkflowError(
                f"no persisted workflow: {workflow_id}"
            )
        return latest

    def history(self, workflow_id: str) -> PersistenceHistory:
        """Return the full :class:`PersistenceHistory` for ``workflow_id``.

        Raises :class:`MissingWorkflowError` when nothing is persisted for it.
        """
        versions = self.repository.versions(workflow_id)
        if not versions:
            raise MissingWorkflowError(
                f"no persisted workflow: {workflow_id}"
            )
        return PersistenceHistory(
            workflow_id=workflow_id,
            versions=versions,
            latest_version=versions[-1].version,
            total=len(versions),
        )

    def restore(self, workflow_id: str, version: int) -> PersistenceSnapshot:
        """Return the :class:`PersistenceSnapshot` persisted at ``version``.

        Raises :class:`InvalidRestoreError` for a structurally invalid version
        (``None`` or non-positive), :class:`MissingWorkflowError` when the workflow
        has no persisted versions, and :class:`MissingVersionError` when that
        specific version does not exist. Restores state only — nothing is executed.
        """
        if version is None or version < 1:
            raise InvalidRestoreError(
                f"invalid restore version: {version!r}"
            )
        if not self.repository.exists(workflow_id):
            raise MissingWorkflowError(
                f"no persisted workflow: {workflow_id}"
            )
        record = self.repository.get(workflow_id, version)
        if record is None:
            raise MissingVersionError(
                f"no version {version} for workflow: {workflow_id}"
            )
        return record.snapshot

    # --- helpers ---------------------------------------------------------
    def _next(self) -> int:
        """Return the next deterministic sequence ordinal."""
        self._sequence += 1
        return self._sequence
