"""Email artifact manager (Sprint 15.12 — deterministic change tracking).

Turns a completed email change into an immutable :class:`EmailArtifact` descriptor.
It is responsible *only* for artifacts: given a change kind, a name, an optional
workspace-relative path, and plain metadata, it mints a descriptor with a
deterministic, content-addressed id — it never sends email, never opens a file, and
never exposes a provider object or credential.

Supports the artifact kinds the capability produces — sent and draft messages,
uploaded and downloaded attachments, and generated reports — so it integrates with
the existing artifact architecture (mirroring :class:`FileSystemArtifactManager` and
:class:`PythonArtifactManager`). Deterministic and offline; stateless — it holds
nothing between calls. Strictly additive to Sprints 15.1–15.11.
"""

import hashlib
from typing import Any, Dict, Optional

from app.services.runtime.email_capability_models import (
    EmailArtifact,
    EmailArtifactType,
)


class EmailArtifactManager:
    """Stateless factory that turns an email change into an artifact DTO.

    ``build`` mints an :class:`EmailArtifact` with a deterministic id derived from
    the change kind, name, and path; ``sent``/``draft``/``uploaded_attachment``/
    ``downloaded_attachment``/``report`` are thin, named shortcuts over it. It sends
    no email and reads no file contents.
    """

    def build(
        self,
        artifact_type: str,
        artifact_name: str,
        artifact_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EmailArtifact:
        """Return an immutable artifact for ``artifact_type`` named ``artifact_name``.

        The id is a deterministic ``em-<type>-<digest>`` where the digest is a stable
        hash of the type, name, and path, so the same change always yields the same
        id. Minting it sends no email.
        """
        digest = hashlib.sha256(
            f"{artifact_type}:{artifact_name}:{artifact_path or ''}".encode("utf-8")
        ).hexdigest()[:16]
        return EmailArtifact(
            artifact_id=f"em-{artifact_type.lower()}-{digest}",
            artifact_type=artifact_type,
            artifact_name=artifact_name,
            artifact_path=artifact_path,
            artifact_metadata=dict(metadata or {}),
        )

    def sent(self, name, metadata=None) -> EmailArtifact:
        """Return a ``SENT`` artifact for a sent message."""
        return self.build(EmailArtifactType.SENT.value, name, None, metadata)

    def draft(self, name, metadata=None) -> EmailArtifact:
        """Return a ``DRAFT`` artifact for a saved draft."""
        return self.build(EmailArtifactType.DRAFT.value, name, None, metadata)

    def uploaded_attachment(self, name, path, metadata=None) -> EmailArtifact:
        """Return an ``UPLOADED_ATTACHMENT`` artifact for a staged attachment."""
        return self.build(
            EmailArtifactType.UPLOADED_ATTACHMENT.value, name, path, metadata
        )

    def downloaded_attachment(self, name, path, metadata=None) -> EmailArtifact:
        """Return a ``DOWNLOADED_ATTACHMENT`` artifact for a downloaded attachment."""
        return self.build(
            EmailArtifactType.DOWNLOADED_ATTACHMENT.value, name, path, metadata
        )

    def report(self, name, metadata=None) -> EmailArtifact:
        """Return a ``REPORT`` artifact for a generated report (e.g. a search)."""
        return self.build(EmailArtifactType.REPORT.value, name, None, metadata)
