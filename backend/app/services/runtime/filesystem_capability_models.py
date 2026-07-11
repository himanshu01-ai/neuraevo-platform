"""File system capability models (Sprint 15.11 — immutable filesystem DTOs).

Provider-independent, immutable DTOs and enums for the File System execution
capability: the operation request, the file/directory descriptors, and the change
artifact. A :class:`FileSystemOperationRequest` carries one filesystem operation
(what to do, on which workspace-relative path, with what content); a
:class:`FileInfo` / :class:`DirectoryInfo` describes an entry the capability
observed (never a ``Path``, file handle, or OS object); a
:class:`FileSystemArtifact` records one change (created/modified/deleted file or a
generated report).

These carry only plain data across the boundary — no ``pathlib.Path``, file
handle, SDK, or OS object ever appears; paths are workspace-relative POSIX strings.
Strictly additive to Sprints 15.1–15.10, whose modules are left untouched. The
result DTOs live in :mod:`app.services.runtime.filesystem_results`.
"""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class FileSystemOperation(str, Enum):
    """The allowed, deterministic filesystem operation labels.

    Each maps one requested operation to a stable ``str`` label so requests
    serialise cleanly and the runtime bridge stays a pass-through. These are
    request labels only — naming one causes nothing to run until it is executed.
    """

    READ = "READ"
    WRITE = "WRITE"
    APPEND = "APPEND"
    COPY = "COPY"
    MOVE = "MOVE"
    RENAME = "RENAME"
    DELETE = "DELETE"
    EXISTS = "EXISTS"
    METADATA = "METADATA"
    CREATE_DIRECTORY = "CREATE_DIRECTORY"
    DELETE_DIRECTORY = "DELETE_DIRECTORY"
    LIST_DIRECTORY = "LIST_DIRECTORY"
    LIST_RECURSIVE = "LIST_RECURSIVE"
    SEARCH = "SEARCH"


class FileType(str, Enum):
    """The kind of a filesystem entry: a regular ``FILE`` or a ``DIRECTORY``."""

    FILE = "FILE"
    DIRECTORY = "DIRECTORY"


class FileSystemOperationStatus(str, Enum):
    """The allowed, deterministic filesystem operation outcomes.

    ``SUCCESS`` — the operation completed. ``NOT_FOUND`` — a required path did not
    exist. ``FAILED`` — the operation could not complete (invalid/unsafe path,
    conflict, or an OS error). Kept as a ``str`` enum so each serialises to its
    label; the bridge maps ``SUCCESS`` to ``COMPLETED`` and everything else to
    ``FAILED``.
    """

    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    FAILED = "FAILED"


class FileSystemArtifactType(str, Enum):
    """The kind of change an artifact records.

    ``CREATED`` / ``MODIFIED`` / ``DELETED`` describe a file (or directory) change;
    ``REPORT`` describes a generated report file. Plain labels only.
    """

    CREATED = "CREATED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    REPORT = "REPORT"


class FileInfo(BaseModel):
    """Immutable description of one file (no OS object exposed).

    ``frozen=True`` makes instances immutable. ``path`` is the workspace-relative
    POSIX path; ``name`` is the entry name; ``file_type`` is a :class:`FileType`
    label; ``size_bytes`` is the file size (``0`` for directories);
    ``modified_time`` is the POSIX mtime; and ``file_metadata`` carries plain
    descriptors (e.g. the suffix). Never a ``Path`` or file handle. Building this
    DTO touches no filesystem.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    name: str
    file_type: str
    size_bytes: int = 0
    modified_time: float = 0.0
    file_metadata: Dict[str, Any] = Field(default_factory=dict)


class DirectoryInfo(BaseModel):
    """Immutable description of one directory (no OS object exposed).

    ``frozen=True`` makes instances immutable. ``path`` is the workspace-relative
    POSIX path; ``name`` is the directory name; ``entry_count`` is the number of
    immediate entries; and ``directory_metadata`` carries plain descriptors.
    Building this DTO touches no filesystem.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    name: str
    entry_count: int = 0
    directory_metadata: Dict[str, Any] = Field(default_factory=dict)


class FileSystemArtifact(BaseModel):
    """Immutable description of one change an operation produced (no OS object).

    ``frozen=True`` makes instances immutable. ``artifact_id`` is a deterministic
    identifier; ``artifact_type`` is a :class:`FileSystemArtifactType` label
    (``CREATED``/``MODIFIED``/``DELETED``/``REPORT``); ``artifact_name`` is the
    entry name; ``artifact_path`` is its workspace-relative path; and
    ``artifact_metadata`` carries plain descriptors (never a file handle or OS
    object). Building this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    artifact_id: str
    artifact_type: str
    artifact_name: str
    artifact_path: str
    artifact_metadata: Dict[str, Any] = Field(default_factory=dict)


class FileSystemOperationRequest(BaseModel):
    """Immutable request to perform one filesystem operation (no execution).

    ``frozen=True`` makes instances immutable. ``operation`` is a
    :class:`FileSystemOperation` label; ``path`` is the workspace-relative target
    (empty means the workspace root, e.g. for a listing); ``destination`` is the
    second path for copy/move/rename; ``content``/``binary_content`` carry the
    text/bytes for write/append; ``binary`` selects binary mode for read/write;
    ``pattern`` is the glob for search; ``recursive`` toggles recursive listing/
    delete/search; ``overwrite`` controls safe-overwrite behaviour; ``encoding`` is
    the text codec; and ``request_metadata`` carries plain call-context descriptors.
    Building this DTO touches no filesystem.
    """

    model_config = ConfigDict(frozen=True)

    operation: str
    path: str = ""
    destination: Optional[str] = None
    content: Optional[str] = None
    binary_content: Optional[bytes] = None
    binary: bool = False
    pattern: Optional[str] = None
    recursive: bool = False
    overwrite: bool = True
    encoding: str = "utf-8"
    request_metadata: Dict[str, Any] = Field(default_factory=dict)
