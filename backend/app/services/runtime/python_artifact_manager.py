"""Python artifact manager (Sprint 15.10 — deterministic artifact tracking).

Tracks the artifacts an execution produced by scanning the workspace directory and
classifying each file into an immutable :class:`PythonArtifact` DTO. It is
responsible *only* for artifacts: it scans files and builds descriptors — it never
executes Python, never opens a file's contents, and never exposes a file handle or
provider object.

Deterministic and offline: files are ordered by name and given position-based ids,
so the same directory always yields the same artifacts. Stateless — it holds
nothing between calls. Strictly additive to Sprints 15.1–15.9, whose modules are
left untouched.
"""

import pathlib
from typing import Dict, List, Optional

from app.services.runtime.python_capability_models import PythonArtifact

# File suffix -> plain artifact type label (deterministic; no content inspection).
_TYPE_BY_SUFFIX = {
    ".csv": "CSV",
    ".xlsx": "EXCEL",
    ".xls": "EXCEL",
    ".json": "JSON",
    ".png": "PNG",
    ".pdf": "PDF",
    ".txt": "TEXT",
}


class PythonArtifactManager:
    """Stateless tracker that turns workspace files into artifact descriptors.

    ``collect`` lists the files in a workspace directory (in name order) and builds
    one :class:`PythonArtifact` per file, with a deterministic id and a type label
    from the suffix. ``classify`` maps a name to its type label. It never executes
    Python or reads file contents.
    """

    def collect(
        self,
        workspace_dir,
        base_metadata: Optional[Dict[str, object]] = None,
    ) -> List[PythonArtifact]:
        """Return the workspace's files as ordered, immutable artifact DTOs.

        Files are ordered by name so ids are deterministic; each artifact records a
        type label, name, path, and plain metadata (suffix and size). A missing
        directory yields an empty list. Reads only directory entries — never file
        contents — and runs no Python.
        """
        directory = pathlib.Path(workspace_dir)
        if not directory.is_dir():
            return []
        files = sorted(
            (path for path in directory.iterdir() if path.is_file()),
            key=lambda path: path.name,
        )
        artifacts: List[PythonArtifact] = []
        for index, path in enumerate(files):
            metadata: Dict[str, object] = dict(base_metadata or {})
            metadata.update(
                {"suffix": path.suffix.lower(), "size_bytes": path.stat().st_size}
            )
            artifacts.append(
                PythonArtifact(
                    artifact_id=f"artifact-{index}",
                    artifact_type=self.classify(path.name),
                    artifact_name=path.name,
                    artifact_path=str(path),
                    artifact_metadata=metadata,
                )
            )
        return artifacts

    @staticmethod
    def classify(name: str) -> str:
        """Return the plain artifact type label for ``name`` (by suffix)."""
        return _TYPE_BY_SUFFIX.get(pathlib.Path(name).suffix.lower(), "FILE")
