"""Calendar artifact manager (Sprint 15.13 — deterministic change tracking).

Turns a completed calendar change into an immutable :class:`CalendarArtifact`
descriptor. It is responsible *only* for artifacts: given a change kind, a name, an
optional workspace-relative path, and plain metadata, it mints a descriptor with a
deterministic, content-addressed id — it performs no calendar logic, opens no file,
and exposes no provider object or credential.

Supports the artifact kinds the capability produces — created, updated, and deleted
events, imported and exported calendars, and generated reports — so it integrates
with the existing artifact architecture (mirroring the File System / Email managers).
Deterministic and offline; stateless — it holds nothing between calls. Strictly
additive to Sprints 15.1–15.12.
"""

import hashlib
from typing import Any, Dict, Optional

from app.services.runtime.calendar_capability_models import (
    CalendarArtifact,
    CalendarArtifactType,
)


class CalendarArtifactManager:
    """Stateless factory that turns a calendar change into an artifact DTO.

    ``build`` mints a :class:`CalendarArtifact` with a deterministic id derived from
    the change kind, name, and path; ``created``/``updated``/``deleted``/
    ``imported``/``exported``/``report`` are thin, named shortcuts over it. It
    performs no calendar logic and reads no file contents.
    """

    def build(
        self,
        artifact_type: str,
        artifact_name: str,
        artifact_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CalendarArtifact:
        """Return an immutable artifact for ``artifact_type`` named ``artifact_name``.

        The id is a deterministic ``cal-<type>-<digest>`` where the digest is a
        stable hash of the type, name, and path, so the same change always yields the
        same id. Minting it runs nothing.
        """
        digest = hashlib.sha256(
            f"{artifact_type}:{artifact_name}:{artifact_path or ''}".encode("utf-8")
        ).hexdigest()[:16]
        return CalendarArtifact(
            artifact_id=f"cal-{artifact_type.lower()}-{digest}",
            artifact_type=artifact_type,
            artifact_name=artifact_name,
            artifact_path=artifact_path,
            artifact_metadata=dict(metadata or {}),
        )

    def created(self, name, metadata=None) -> CalendarArtifact:
        """Return a ``CREATED`` artifact for a created event."""
        return self.build(CalendarArtifactType.CREATED.value, name, None, metadata)

    def updated(self, name, metadata=None) -> CalendarArtifact:
        """Return an ``UPDATED`` artifact for an updated event."""
        return self.build(CalendarArtifactType.UPDATED.value, name, None, metadata)

    def deleted(self, name, metadata=None) -> CalendarArtifact:
        """Return a ``DELETED`` artifact for a deleted event."""
        return self.build(CalendarArtifactType.DELETED.value, name, None, metadata)

    def imported(self, name, metadata=None) -> CalendarArtifact:
        """Return an ``IMPORTED`` artifact for an imported calendar."""
        return self.build(CalendarArtifactType.IMPORTED.value, name, None, metadata)

    def exported(self, name, path, metadata=None) -> CalendarArtifact:
        """Return an ``EXPORTED`` artifact for an exported .ics file."""
        return self.build(CalendarArtifactType.EXPORTED.value, name, path, metadata)

    def report(self, name, metadata=None) -> CalendarArtifact:
        """Return a ``REPORT`` artifact for a generated report (e.g. a search)."""
        return self.build(CalendarArtifactType.REPORT.value, name, None, metadata)
