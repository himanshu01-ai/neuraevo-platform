"""File system workspace abstraction (Sprint 15.11 — isolation + safe paths).

Defines the isolated workspace every File System operation runs inside. A
:class:`FileSystemWorkspace` owns a single root directory and enforces the
capability's core security guarantee: every requested path is normalised and
resolved *within* the root, so ``../`` traversal, absolute paths, and drive-letter
escapes are rejected before any I/O happens. It also owns the optional temporary
directory and workspace cleanup.

The :class:`FileSystemWorkspaceManager` is the stateless factory that mints the
current (persistent) workspace and throwaway temporary workspaces, and cleans them
up. Neither performs file read/write logic — that is the execution layer's job;
this module only does path math and directory lifecycle. Deterministic and offline;
no SDK, network, or OS object beyond ``pathlib``/``shutil``/``tempfile`` is used, and
no ``Path`` ever leaves in a DTO. Strictly additive to Sprints 15.1–15.10.
"""

import pathlib
import shutil
import tempfile
from typing import Any, Dict, Optional, Tuple


class WorkspacePathError(ValueError):
    """Raised when a requested path is unsafe — it would escape the workspace root.

    Covers ``../`` traversal, absolute paths, and drive-letter escapes. The
    execution layer catches this and reports a graceful ``FAILED`` result; the
    exception object never crosses a capability boundary.
    """


class FileSystemWorkspace:
    """One isolated, root-confined filesystem workspace.

    Holds a resolved ``root`` directory and an optional ``temp`` directory. Its
    responsibilities are path normalisation, *safe* path resolution (never escaping
    the root), and cleanup — it performs no file read/write logic itself. Instances
    are effectively immutable (their roots never change) and expose paths only as
    plain strings; the internal :class:`pathlib.Path` roots are used only by the
    in-process execution layer and never appear in a DTO.
    """

    def __init__(
        self,
        workspace_id: str,
        root_path,
        temp_path=None,
        is_temporary: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.workspace_id = workspace_id
        self._root = pathlib.Path(root_path).resolve()
        self._temp = pathlib.Path(temp_path).resolve() if temp_path else None
        self.is_temporary = is_temporary
        self.workspace_metadata: Dict[str, Any] = dict(metadata or {})

    # --- plain-string accessors (no Path leaks) -------------------------
    @property
    def root_path(self) -> str:
        """The resolved workspace root, as a plain string."""
        return str(self._root)

    @property
    def temp_path(self) -> Optional[str]:
        """The resolved temporary directory, as a plain string (or ``None``)."""
        return str(self._temp) if self._temp else None

    @property
    def root(self) -> pathlib.Path:
        """The resolved root as a :class:`Path` — for the in-process executor only."""
        return self._root

    def exists(self) -> bool:
        """Return whether the workspace root directory currently exists."""
        return self._root.is_dir()

    # --- safe path resolution (the security seam) -----------------------
    def resolve(self, path) -> Tuple[pathlib.Path, str]:
        """Resolve ``path`` inside the root, returning ``(absolute, relative_posix)``.

        The path is treated as workspace-relative: separators are normalised, and
        absolute paths and drive letters are rejected outright. The candidate is
        then resolved (collapsing ``.``/``..``) and confirmed to remain within the
        root; anything that would escape raises :class:`WorkspacePathError`. An
        empty path resolves to the root itself. No filesystem read/write happens
        here — only path math.
        """
        if path is None:
            raise WorkspacePathError("path must not be None")
        text = str(path).strip().replace("\\", "/")
        if self._is_absolute_like(text):
            raise WorkspacePathError(f"absolute paths are not permitted: {path!r}")
        parts = [
            part
            for part in pathlib.PurePosixPath(text).parts
            if part not in ("", "/", ".")
        ]
        resolved = self._root.joinpath(*parts).resolve()
        try:
            relative = resolved.relative_to(self._root)
        except ValueError:
            raise WorkspacePathError(
                f"path escapes the workspace root: {path!r}"
            )
        relative_posix = "" if str(relative) == "." else relative.as_posix()
        return resolved, relative_posix

    def normalize(self, path) -> str:
        """Return the safe workspace-relative POSIX form of ``path`` (may raise)."""
        return self.resolve(path)[1]

    def relative(self, absolute) -> str:
        """Return ``absolute`` as a workspace-relative POSIX string (best effort).

        Used to describe entries the executor already found inside the root; falls
        back to the bare name if the path is somehow outside (it never is for
        entries produced by walking the root).
        """
        candidate = pathlib.Path(absolute)
        try:
            return candidate.resolve().relative_to(self._root).as_posix()
        except ValueError:
            return candidate.name

    # --- lifecycle ------------------------------------------------------
    def ensure_root(self) -> None:
        """Create the workspace root directory if it does not exist."""
        self._root.mkdir(parents=True, exist_ok=True)

    def cleanup(self) -> None:
        """Clean the workspace.

        A temporary workspace is removed entirely; the persistent (current)
        workspace is emptied but its root directory is kept so it can be reused.
        Only paths inside the resolved root are touched. Errors are swallowed so
        cleanup never raises across a capability boundary.
        """
        if not self._root.exists():
            return
        if self.is_temporary:
            shutil.rmtree(self._root, ignore_errors=True)
            return
        for child in self._root.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except OSError:
                    pass

    # --- helpers --------------------------------------------------------
    @staticmethod
    def _is_absolute_like(text: str) -> bool:
        """Return whether ``text`` (with ``/`` separators) is an absolute path.

        Rejects POSIX roots (``/x``), UNC paths (``//host``), and Windows drive
        letters (``C:``) — the three ways an absolute path could escape the root.
        """
        if not text:
            return False
        if text.startswith("/"):
            return True
        return len(text) >= 2 and text[1] == ":"


class FileSystemWorkspaceManager:
    """Stateless factory for :class:`FileSystemWorkspace` instances.

    ``current_workspace`` returns the persistent workspace rooted at the configured
    root (or a deterministic default under the system temp dir);
    ``create_temporary_workspace`` mints a fresh throwaway workspace; ``cleanup``
    delegates to the workspace. It holds no state between calls and performs no file
    read/write logic.
    """

    DEFAULT_DIRNAME = "neuraevo_filesystem"

    def current_workspace(self, root_path: Optional[str] = None) -> FileSystemWorkspace:
        """Return the persistent workspace rooted at ``root_path`` (created).

        When ``root_path`` is ``None`` a deterministic directory under the system
        temp dir is used, so the capability always has an isolated root even when
        none is configured.
        """
        base = (
            pathlib.Path(root_path)
            if root_path
            else pathlib.Path(tempfile.gettempdir()) / self.DEFAULT_DIRNAME
        )
        base.mkdir(parents=True, exist_ok=True)
        return FileSystemWorkspace(
            "current", base, metadata={"kind": "current"}
        )

    def create_temporary_workspace(self, prefix: str = "fs") -> FileSystemWorkspace:
        """Return a fresh, isolated temporary workspace (its own new directory)."""
        temp_dir = tempfile.mkdtemp(prefix=f"neuraevo_fs_{prefix}_")
        return FileSystemWorkspace(
            f"temp-{pathlib.Path(temp_dir).name}",
            temp_dir,
            temp_path=temp_dir,
            is_temporary=True,
            metadata={"kind": "temporary"},
        )

    def cleanup(self, workspace: FileSystemWorkspace) -> None:
        """Clean up ``workspace`` (delegates to :meth:`FileSystemWorkspace.cleanup`)."""
        workspace.cleanup()
