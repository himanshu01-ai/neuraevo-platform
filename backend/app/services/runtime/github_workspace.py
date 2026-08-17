"""GitHub workspace abstraction (Sprint 15.14 — repository staging + cleanup).

Defines the workspace every GitHub operation uses for on-disk repository staging. A
:class:`GitHubWorkspace` owns a single staging root and is the *only* place
repository filesystem logic lives: it validates a repository name/path (rejecting
traversal and escapes), stages a repository directory under the staging root
(temporary repository storage), reports the resolved path, and cleans everything up
safely.

The :class:`GitHubWorkspaceManager` is the stateless factory that mints the current
(persistent) staging workspace and throwaway temporary workspaces. The workspace
performs *no Git logic* — no init, branches, commits, tags, or issues; those belong
to the execution layer. Deterministic and offline; stdlib only, and no ``Path`` ever
leaves in a DTO. Strictly additive to Sprints 15.1–15.13.
"""

import pathlib
import shutil
import tempfile
from typing import Optional


class GitHubWorkspaceError(ValueError):
    """Raised when a repository path/name is unsafe or the staging fails.

    The capability catches this at its boundary and reports a graceful ``FAILED``
    result; the exception object never crosses a capability boundary.
    """


class GitHubWorkspace:
    """One isolated staging workspace for repositories.

    Holds a resolved staging ``root``. Its responsibilities are repository-name
    validation, staging a repository directory under the root, reporting the resolved
    path, and cleanup — it performs no Git logic. Instances are effectively immutable
    (their root never changes) and expose paths only as plain strings.
    """

    def __init__(
        self,
        workspace_id: str,
        staging_path,
        is_temporary: bool = False,
    ) -> None:
        self.workspace_id = workspace_id
        self._staging = pathlib.Path(staging_path).resolve()
        self.is_temporary = is_temporary
        self._staging.mkdir(parents=True, exist_ok=True)

    # --- plain-string accessors (no Path leaks) -------------------------
    @property
    def staging_path(self) -> str:
        """The resolved staging directory, as a plain string."""
        return str(self._staging)

    def exists(self) -> bool:
        """Return whether the staging directory currently exists."""
        return self._staging.is_dir()

    # --- repository staging (validation + directory) --------------------
    def stage_repository(self, name: str) -> str:
        """Create and return the staging directory for repository ``name``.

        Validates that ``name`` is a single safe segment confined to the staging
        root (no separators/traversal), creates the directory, and returns its path
        as a plain string. Raises :class:`GitHubWorkspaceError` on an unsafe name.
        Performs no Git logic.
        """
        safe = self._safe_segment(name)
        target = (self._staging / safe).resolve()
        self._ensure_within(target)
        target.mkdir(parents=True, exist_ok=True)
        return str(target)

    def repository_path(self, name: str) -> str:
        """Return the resolved staging path for ``name`` without creating it."""
        safe = self._safe_segment(name)
        target = (self._staging / safe).resolve()
        self._ensure_within(target)
        return str(target)

    def validate_repository_path(self, path: str) -> str:
        """Return ``path`` if it is a directory inside the staging root, else raise.

        Used when opening a staged repository. Raises :class:`GitHubWorkspaceError`
        if the path escapes the root or is not an existing directory.
        """
        resolved = pathlib.Path(path).resolve()
        self._ensure_within(resolved)
        if not resolved.is_dir():
            raise GitHubWorkspaceError(f"repository path is not a directory: {path!r}")
        return str(resolved)

    # --- lifecycle ------------------------------------------------------
    def cleanup(self) -> None:
        """Clean the workspace's staging directory (temp removed, persistent emptied)."""
        if not self._staging.exists():
            return
        if self.is_temporary:
            shutil.rmtree(self._staging, ignore_errors=True)
            return
        for child in self._staging.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except OSError:
                    pass

    # --- helpers --------------------------------------------------------
    @staticmethod
    def _safe_segment(name: str) -> str:
        text = "" if name is None else str(name).strip()
        if not text or "/" in text or "\\" in text or text in (".", ".."):
            raise GitHubWorkspaceError(f"invalid repository name: {name!r}")
        return text

    def _ensure_within(self, resolved: pathlib.Path) -> None:
        try:
            resolved.relative_to(self._staging)
        except ValueError:
            raise GitHubWorkspaceError("repository path escapes the staging root")


class GitHubWorkspaceManager:
    """Stateless factory for :class:`GitHubWorkspace` instances.

    ``current_workspace`` returns the persistent staging workspace rooted at the
    configured staging root (or a deterministic default under the system temp dir);
    ``create_temporary_workspace`` mints a fresh throwaway workspace; ``cleanup``
    delegates to the workspace. It holds no state between calls and performs no Git
    logic.
    """

    DEFAULT_DIRNAME = "neuraevo_github"

    def current_workspace(
        self, staging_root: Optional[str] = None
    ) -> GitHubWorkspace:
        """Return the persistent repository-staging workspace (created)."""
        base = (
            pathlib.Path(staging_root)
            if staging_root
            else pathlib.Path(tempfile.gettempdir()) / self.DEFAULT_DIRNAME
        )
        base.mkdir(parents=True, exist_ok=True)
        return GitHubWorkspace("current", base)

    def create_temporary_workspace(self, prefix: str = "repo") -> GitHubWorkspace:
        """Return a fresh, isolated temporary repository-staging workspace."""
        temp_dir = tempfile.mkdtemp(prefix=f"neuraevo_github_{prefix}_")
        return GitHubWorkspace(
            f"temp-{pathlib.Path(temp_dir).name}", temp_dir, is_temporary=True
        )

    def cleanup(self, workspace: GitHubWorkspace) -> None:
        """Clean up ``workspace`` (delegates to :meth:`GitHubWorkspace.cleanup`)."""
        workspace.cleanup()
