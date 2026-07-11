"""Email workspace abstraction (Sprint 15.12 — attachment staging + cleanup).

Defines the workspace every Email operation uses for attachment handling. A
:class:`EmailWorkspace` owns a single temporary staging directory and is the *only*
place attachment filesystem logic lives: it validates an attachment (existence,
size, and — when an attachment root is configured — that the source stays inside
it), stages its bytes into the staging directory, saves downloaded attachment bytes
back out, and cleans everything up safely.

The :class:`EmailWorkspaceManager` is the stateless factory that mints the current
(persistent) staging workspace and throwaway temporary workspaces, and cleans them
up. Neither sends or reads email — that is the execution layer's job. Attachments
can be sourced from a File System capability workspace by pointing ``attachment_root``
at that workspace's root. Deterministic and offline; stdlib only, and no ``Path``
ever leaves in a DTO. Strictly additive to Sprints 15.1–15.11.
"""

import mimetypes
import pathlib
import shutil
import tempfile
from typing import Optional

from app.services.runtime.email_capability_models import EmailAttachment

# Default maximum attachment size (25 MiB) — the common mailbox ceiling. The
# capability rejects anything larger with a clear error before "sending".
DEFAULT_MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024


class AttachmentError(ValueError):
    """Raised when an attachment is missing, too large, or escapes its root.

    The capability catches this at its boundary and reports a graceful ``FAILED``
    result; the exception object never crosses a capability boundary.
    """


class EmailWorkspace:
    """One isolated staging workspace for email attachments.

    Holds a resolved staging ``root`` and an optional ``attachment_root`` (e.g. a
    File System capability workspace root) that relative attachment paths are
    confined to. Its responsibilities are attachment validation, staging bytes into
    the staging directory, saving downloaded bytes, and cleanup — it sends and reads
    no email. Instances are effectively immutable (their roots never change) and
    expose paths only as plain strings.
    """

    def __init__(
        self,
        workspace_id: str,
        staging_path,
        attachment_root=None,
        max_attachment_bytes: int = DEFAULT_MAX_ATTACHMENT_BYTES,
        is_temporary: bool = False,
    ) -> None:
        self.workspace_id = workspace_id
        self._staging = pathlib.Path(staging_path).resolve()
        self._attachment_root = (
            pathlib.Path(attachment_root).resolve() if attachment_root else None
        )
        self.max_attachment_bytes = max_attachment_bytes
        self.is_temporary = is_temporary
        self._staging.mkdir(parents=True, exist_ok=True)

    # --- plain-string accessors (no Path leaks) -------------------------
    @property
    def staging_path(self) -> str:
        """The resolved staging directory, as a plain string."""
        return str(self._staging)

    @property
    def attachment_root(self) -> Optional[str]:
        """The configured attachment source root, as a plain string (or ``None``)."""
        return str(self._attachment_root) if self._attachment_root else None

    def exists(self) -> bool:
        """Return whether the staging directory currently exists."""
        return self._staging.is_dir()

    # --- attachment staging (validation + copy) -------------------------
    def stage_attachment(self, source) -> EmailAttachment:
        """Validate ``source`` and stage its bytes, returning an :class:`EmailAttachment`.

        Validates that the source exists, is a file, and is within the configured
        attachment root (for relative paths) and the size limit; raises
        :class:`AttachmentError` otherwise. The bytes are copied into the staging
        directory and read into the returned descriptor (content type guessed from
        the name). No email is sent here.
        """
        resolved, source_label = self._resolve_source(source)
        if not resolved.exists() or not resolved.is_file():
            raise AttachmentError(f"attachment not found: {source_label}")
        size = resolved.stat().st_size
        if size > self.max_attachment_bytes:
            raise AttachmentError(
                f"attachment exceeds the size limit "
                f"({size} > {self.max_attachment_bytes} bytes): {source_label}"
            )
        try:
            data = resolved.read_bytes()
        except OSError as exc:  # graceful — never leak the OS object
            raise AttachmentError(
                f"attachment could not be read ({type(exc).__name__}): {source_label}"
            )
        staged = self._staging / resolved.name
        try:
            staged.write_bytes(data)
        except OSError as exc:
            raise AttachmentError(
                f"attachment could not be staged ({type(exc).__name__}): {source_label}"
            )
        content_type = (
            mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        )
        return EmailAttachment(
            filename=resolved.name,
            content_type=content_type,
            size_bytes=size,
            source_path=source_label,
            staged_path=resolved.name,
            content=data,
            attachment_metadata={"staged": True},
        )

    def save_download(self, filename: str, content: bytes) -> str:
        """Write downloaded attachment ``content`` into staging; return its rel name.

        The filename is reduced to its bare name so a downloaded attachment can
        never write outside the staging directory. Returns the staging-relative
        name for the artifact to reference.
        """
        safe_name = pathlib.Path(filename or "attachment").name or "attachment"
        target = self._staging / safe_name
        target.write_bytes(content or b"")
        return safe_name

    # --- lifecycle ------------------------------------------------------
    def cleanup(self) -> None:
        """Clean the workspace's staging directory.

        A temporary workspace is removed entirely; a persistent one is emptied but
        its directory is kept for reuse. Only paths inside the staging root are
        touched. Errors are swallowed so cleanup never raises across a boundary.
        """
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
    def _resolve_source(self, source):
        """Resolve an attachment source to ``(absolute, label)``, guarding escapes.

        An absolute source must exist on disk as given. A relative source is joined
        to the configured attachment root (and confined to it); without a root, a
        relative source resolves against the current directory. Raises
        :class:`AttachmentError` if a relative source would escape the root.
        """
        text = str(source).strip().replace("\\", "/")
        candidate = pathlib.Path(text)
        if candidate.is_absolute() or (len(text) >= 2 and text[1] == ":"):
            return pathlib.Path(source).resolve(), text
        if self._attachment_root is not None:
            parts = [
                part
                for part in pathlib.PurePosixPath(text).parts
                if part not in ("", "/", ".")
            ]
            resolved = self._attachment_root.joinpath(*parts).resolve()
            try:
                resolved.relative_to(self._attachment_root)
            except ValueError:
                raise AttachmentError(
                    f"attachment path escapes the attachment root: {source!r}"
                )
            return resolved, text
        return candidate.resolve(), text


class EmailWorkspaceManager:
    """Stateless factory for :class:`EmailWorkspace` instances.

    ``current_workspace`` returns the persistent staging workspace rooted at the
    configured staging root (or a deterministic default under the system temp dir);
    ``create_temporary_workspace`` mints a fresh throwaway workspace; ``cleanup``
    delegates to the workspace. It holds no state between calls and sends no email.
    """

    DEFAULT_DIRNAME = "neuraevo_email"

    def current_workspace(
        self,
        staging_root: Optional[str] = None,
        attachment_root: Optional[str] = None,
        max_attachment_bytes: int = DEFAULT_MAX_ATTACHMENT_BYTES,
    ) -> EmailWorkspace:
        """Return the persistent staging workspace (created)."""
        base = (
            pathlib.Path(staging_root)
            if staging_root
            else pathlib.Path(tempfile.gettempdir()) / self.DEFAULT_DIRNAME
        )
        base.mkdir(parents=True, exist_ok=True)
        return EmailWorkspace(
            "current",
            base,
            attachment_root=attachment_root,
            max_attachment_bytes=max_attachment_bytes,
        )

    def create_temporary_workspace(
        self,
        prefix: str = "email",
        attachment_root: Optional[str] = None,
        max_attachment_bytes: int = DEFAULT_MAX_ATTACHMENT_BYTES,
    ) -> EmailWorkspace:
        """Return a fresh, isolated temporary staging workspace."""
        temp_dir = tempfile.mkdtemp(prefix=f"neuraevo_email_{prefix}_")
        return EmailWorkspace(
            f"temp-{pathlib.Path(temp_dir).name}",
            temp_dir,
            attachment_root=attachment_root,
            max_attachment_bytes=max_attachment_bytes,
            is_temporary=True,
        )

    def cleanup(self, workspace: EmailWorkspace) -> None:
        """Clean up ``workspace`` (delegates to :meth:`EmailWorkspace.cleanup`)."""
        workspace.cleanup()
