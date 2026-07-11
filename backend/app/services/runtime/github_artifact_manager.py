"""GitHub artifact manager (Sprint 15.14 — deterministic change tracking).

Turns a completed repository change into an immutable :class:`GitHubArtifact`
descriptor. It is responsible *only* for artifacts: given a change kind, a name, an
optional path, and plain metadata, it mints a descriptor with a deterministic,
content-addressed id — it performs no Git logic, opens no file, and exposes no
provider object or credential.

Supports the artifact kinds the capability produces — commits, branches, tags,
issues, and repository reports — so it integrates with the existing artifact
architecture (mirroring the File System / Email / Calendar managers). Deterministic
and offline; stateless — it holds nothing between calls. Strictly additive to Sprints
15.1–15.13.
"""

import hashlib
from typing import Any, Dict, Optional

from app.services.runtime.github_capability_models import (
    GitHubArtifact,
    GitHubArtifactType,
)


class GitHubArtifactManager:
    """Stateless factory that turns a repository change into an artifact DTO.

    ``build`` mints a :class:`GitHubArtifact` with a deterministic id derived from
    the change kind, name, and path; ``commit``/``branch``/``tag``/``issue``/
    ``report`` are thin, named shortcuts over it. It performs no Git logic and reads
    no file contents.
    """

    def build(
        self,
        artifact_type: str,
        artifact_name: str,
        artifact_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GitHubArtifact:
        """Return an immutable artifact for ``artifact_type`` named ``artifact_name``.

        The id is a deterministic ``gh-<type>-<digest>`` where the digest is a stable
        hash of the type, name, and path, so the same change always yields the same
        id. Minting it runs nothing.
        """
        digest = hashlib.sha256(
            f"{artifact_type}:{artifact_name}:{artifact_path or ''}".encode("utf-8")
        ).hexdigest()[:16]
        return GitHubArtifact(
            artifact_id=f"gh-{artifact_type.lower()}-{digest}",
            artifact_type=artifact_type,
            artifact_name=artifact_name,
            artifact_path=artifact_path,
            artifact_metadata=dict(metadata or {}),
        )

    def commit(self, name, metadata=None) -> GitHubArtifact:
        """Return a ``COMMIT`` artifact for a created commit."""
        return self.build(GitHubArtifactType.COMMIT.value, name, None, metadata)

    def branch(self, name, metadata=None) -> GitHubArtifact:
        """Return a ``BRANCH`` artifact for a created branch."""
        return self.build(GitHubArtifactType.BRANCH.value, name, None, metadata)

    def tag(self, name, metadata=None) -> GitHubArtifact:
        """Return a ``TAG`` artifact for a created tag."""
        return self.build(GitHubArtifactType.TAG.value, name, None, metadata)

    def issue(self, name, metadata=None) -> GitHubArtifact:
        """Return an ``ISSUE`` artifact for a created/updated/closed issue."""
        return self.build(GitHubArtifactType.ISSUE.value, name, None, metadata)

    def report(self, name, metadata=None) -> GitHubArtifact:
        """Return a ``REPORT`` artifact for a repository or search report."""
        return self.build(GitHubArtifactType.REPORT.value, name, None, metadata)
