"""Persistence Layer models (Sprint 16.5 — immutable persistence DTOs + errors).

Provider-independent, immutable DTOs, the snapshot-type enum, and the deterministic
validation errors for the production-grade Persistence Layer: the snapshot of
platform state, its compact metadata, a stored version, the version history, and
the result of a persistence operation. This layer *upgrades* the Sprint 16.2
PersistenceManager abstraction additively — it introduces no change to any frozen
module.

It stores *platform state* only: it implements no database, no AI memory, no
embeddings, and no vector store. Snapshots carry plain data (the frozen Sprint 16.2
:class:`WorkflowInstance` / :class:`WorkflowProgress`, plus generic history and
metadata) — never a provider/SDK object, and never a live repository object crosses
the boundary. All timing is a deterministic integer sequence (never a clock).
Strictly additive to Sprints 1.x–16.4, whose modules are left untouched.
"""

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.ai_employee.platform_models import (
    WorkflowInstance,
    WorkflowProgress,
)

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


# =====================================================================
# Deterministic validation errors
# =====================================================================
class PersistenceError(Exception):
    """Base class for the Persistence Layer's deterministic validation errors."""


class MissingWorkflowError(PersistenceError):
    """Raised when an operation targets a workflow with no persisted versions."""


class MissingVersionError(PersistenceError):
    """Raised when a requested version does not exist for the workflow."""


class DuplicatePersistenceError(PersistenceError):
    """Raised when a version that already exists for the workflow is saved again."""


class InvalidRestoreError(PersistenceError):
    """Raised when a restore is structurally invalid (e.g. a non-positive version)."""


class InvalidSnapshotError(PersistenceError):
    """Raised when a snapshot cannot be built from the given (missing) instance."""


# =====================================================================
# Snapshot type
# =====================================================================
class SnapshotType(str, Enum):
    """The allowed, deterministic snapshot types.

    ``FULL`` — a complete capture of the workflow state. ``INCREMENTAL`` — a capture
    tagged as a delta over a prior version (the Sprint 16.5 in-memory store keeps a
    complete payload for each; delta computation belongs to a later Sprint 16.x).
    ``AUTO`` — a capture taken automatically rather than on explicit request. Kept as
    a ``str`` enum so each serialises to its label.
    """

    FULL = "FULL"
    INCREMENTAL = "INCREMENTAL"
    AUTO = "AUTO"


# =====================================================================
# DTOs
# =====================================================================
class PersistenceMetadata(BaseModel):
    """Immutable, compact descriptor of a persisted snapshot (no state payload).

    ``frozen=True`` makes instances immutable. ``workflow_id`` identifies the
    persisted workflow instance; ``version`` is its version ordinal (0 for an
    unsaved, standalone snapshot); ``snapshot_type`` is one of the
    :class:`SnapshotType` labels; ``created_at_sequence`` is the deterministic
    ordinal (never a clock); and ``metadata`` carries plain descriptors. Producing
    this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    workflow_id: _NonEmptyStr
    version: int = Field(default=0, ge=0)
    snapshot_type: SnapshotType = SnapshotType.FULL
    created_at_sequence: int = Field(default=0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PersistenceSnapshot(BaseModel):
    """Immutable capture of one workflow instance's platform state (no execution).

    ``frozen=True`` makes instances immutable. ``snapshot_id`` is the deterministic
    handle; ``workflow_id`` identifies the persisted workflow instance;
    ``snapshot_type`` is one of the :class:`SnapshotType` labels; ``instance`` is the
    captured Sprint 16.2 :class:`WorkflowInstance`; ``progress`` is its
    :class:`WorkflowProgress`; ``approval_history`` and ``notification_history`` are
    the captured approval/notification records (plain, provider-independent — any
    immutable history entries); ``workflow_metadata`` is the instance's metadata;
    ``metadata`` is the compact :class:`PersistenceMetadata`; and
    ``created_at_sequence`` is the deterministic ordinal. The snapshot captures
    state only — it executes nothing. (Because a :class:`WorkflowInstance` already
    carries its progress and metadata, this snapshot captures all five required
    content areas — instance, progress, metadata, approval history, notification
    history.)
    """

    model_config = ConfigDict(frozen=True)

    snapshot_id: _NonEmptyStr
    workflow_id: _NonEmptyStr
    snapshot_type: SnapshotType = SnapshotType.FULL
    instance: WorkflowInstance
    progress: WorkflowProgress
    approval_history: List[Any] = Field(default_factory=list)
    notification_history: List[Any] = Field(default_factory=list)
    workflow_metadata: Dict[str, Any] = Field(default_factory=dict)
    metadata: PersistenceMetadata
    created_at_sequence: int = Field(default=0, ge=0)


class PersistenceVersion(BaseModel):
    """Immutable versioned record wrapping one snapshot (a save produces one).

    ``frozen=True`` makes instances immutable. ``workflow_id`` identifies the
    persisted workflow instance; ``version`` is the sequential (1-based) version
    ordinal — each save creates the next one; ``snapshot`` is the captured
    :class:`PersistenceSnapshot`; ``created_at_sequence`` is the deterministic
    ordinal; and ``version_metadata`` carries plain descriptors. Producing this DTO
    runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    workflow_id: _NonEmptyStr
    version: int = Field(ge=1)
    snapshot: PersistenceSnapshot
    created_at_sequence: int = Field(default=0, ge=0)
    version_metadata: Dict[str, Any] = Field(default_factory=dict)


class PersistenceHistory(BaseModel):
    """Immutable version history for one workflow instance (deterministic order).

    ``frozen=True`` makes instances immutable. ``workflow_id`` identifies the
    workflow instance; ``versions`` are the :class:`PersistenceVersion` records in
    ascending version order; ``latest_version`` is the highest version; ``total`` is
    the count; and ``history_metadata`` carries plain descriptors. Producing this
    DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    workflow_id: _NonEmptyStr
    versions: List[PersistenceVersion] = Field(default_factory=list)
    latest_version: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)
    history_metadata: Dict[str, Any] = Field(default_factory=dict)


class PersistenceResult(BaseModel):
    """Immutable result of a persistence operation (no execution).

    ``frozen=True`` makes instances immutable. ``workflow_id`` identifies the
    workflow instance; ``operation`` names the operation (e.g. ``"save"``,
    ``"delete"``); ``success`` is the outcome; ``version`` is the version created or
    affected (``None`` when not applicable); ``snapshot`` is the captured snapshot
    for a save (``None`` otherwise); and ``result_metadata`` carries plain
    descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    workflow_id: _NonEmptyStr
    operation: _NonEmptyStr
    success: bool
    version: Optional[int] = None
    snapshot: Optional[PersistenceSnapshot] = None
    result_metadata: Dict[str, Any] = Field(default_factory=dict)
