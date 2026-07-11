"""File system artifact manager (Sprint 15.11 — deterministic change tracking).

Turns a completed filesystem change into an immutable :class:`FileSystemArtifact`
descriptor. It is responsible *only* for artifacts: given a change kind, a name, a
workspace-relative path, and plain metadata, it mints a descriptor with a
deterministic, content-addressed id — it never performs I/O, never opens a file,
and never exposes a ``Path`` or OS object.

Supports the four artifact kinds the capability produces — created, modified, and
deleted files, plus generated reports — so it integrates with the existing artifact
architecture (mirroring :class:`PythonArtifactManager`). Deterministic and offline;
stateless — it holds nothing between calls. Strictly additive to Sprints
15.1–15.10, whose modules are left untouched.
"""

import hashlib
from typing import Any, Dict, Optional

from app.services.runtime.filesystem_capability_models import (
    FileSystemArtifact,
    FileSystemArtifactType,
)


class FileSystemArtifactManager:
    """Stateless factory that turns a filesystem change into an artifact DTO.

    ``build`` mints a :class:`FileSystemArtifact` with a deterministic id derived
    from the change kind and path; ``created``/``modified``/``deleted``/``report``
    are thin, named shortcuts over it. It performs no I/O and reads no file
    contents.
    """

    def build(
        self,
        artifact_type: str,
        artifact_name: str,
        artifact_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileSystemArtifact:
        """Return an immutable artifact for ``artifact_type`` at ``artifact_path``.

        The id is a deterministic ``fs-<type>-<digest>`` where the digest is a
        stable hash of the type and path, so the same change always yields the same
        id. Minting it runs no filesystem logic.
        """
        digest = hashlib.sha256(
            f"{artifact_type}:{artifact_path}".encode("utf-8")
        ).hexdigest()[:16]
        return FileSystemArtifact(
            artifact_id=f"fs-{artifact_type.lower()}-{digest}",
            artifact_type=artifact_type,
            artifact_name=artifact_name,
            artifact_path=artifact_path,
            artifact_metadata=dict(metadata or {}),
        )

    def created(self, name, path, metadata=None) -> FileSystemArtifact:
        """Return a ``CREATED`` artifact for a newly created file/directory."""
        return self.build(FileSystemArtifactType.CREATED.value, name, path, metadata)

    def modified(self, name, path, metadata=None) -> FileSystemArtifact:
        """Return a ``MODIFIED`` artifact for an updated file."""
        return self.build(FileSystemArtifactType.MODIFIED.value, name, path, metadata)

    def deleted(self, name, path, metadata=None) -> FileSystemArtifact:
        """Return a ``DELETED`` artifact for a removed file/directory."""
        return self.build(FileSystemArtifactType.DELETED.value, name, path, metadata)

    def report(self, name, path, metadata=None) -> FileSystemArtifact:
        """Return a ``REPORT`` artifact for a generated report file."""
        return self.build(FileSystemArtifactType.REPORT.value, name, path, metadata)
