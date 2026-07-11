"""File system result models (Sprint 15.11 — immutable result DTOs).

The immutable, provider-independent results of the File System capability's
operations: a read, a write/append, a directory listing, a file search, and the
generic single-target operation (copy/move/rename/delete/exists/metadata/directory
create/delete). Kept in their own module (mirroring the browser/python model
split); each carries only plain data — no ``pathlib.Path``, file handle, or OS
object crosses this boundary, and every path is a workspace-relative POSIX string.
Strictly additive to Sprints 15.1–15.10, whose modules are left untouched.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.filesystem_capability_models import (
    DirectoryInfo,
    FileInfo,
    FileSystemArtifact,
)


class FileReadResult(BaseModel):
    """Immutable result of reading a file (no OS object exposed).

    ``frozen=True`` makes instances immutable. ``path`` is the workspace-relative
    path; ``content`` is the decoded text (``None`` in binary mode);
    ``binary_content`` is the raw bytes (``None`` in text mode); ``is_binary``
    records the mode; ``size_bytes`` is the number of bytes read; ``encoding`` is
    the text codec used (``None`` in binary mode); ``operation_status`` is a
    :class:`FileSystemOperationStatus` label; and ``operation_metadata`` carries
    plain descriptors (e.g. an error string). Producing this DTO reads nothing
    further.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    content: Optional[str] = None
    binary_content: Optional[bytes] = None
    is_binary: bool = False
    size_bytes: int = 0
    encoding: Optional[str] = None
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class FileWriteResult(BaseModel):
    """Immutable result of writing or appending a file (no OS object exposed).

    ``frozen=True`` makes instances immutable. ``path`` is the workspace-relative
    path; ``operation`` is ``WRITE`` or ``APPEND``; ``bytes_written`` is the byte
    count written; ``created`` marks whether the file was newly created;
    ``is_binary`` records the mode; ``operation_status`` is a
    :class:`FileSystemOperationStatus` label; ``artifact`` is the
    :class:`FileSystemArtifact` recorded for the change (``None`` on failure); and
    ``operation_metadata`` carries plain descriptors. Producing this DTO writes
    nothing further.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    operation: str
    bytes_written: int = 0
    created: bool = False
    is_binary: bool = False
    operation_status: str
    artifact: Optional[FileSystemArtifact] = None
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class DirectoryListingResult(BaseModel):
    """Immutable result of listing a directory (no OS object exposed).

    ``frozen=True`` makes instances immutable. ``path`` is the workspace-relative
    directory path; ``entries`` are the ordered :class:`FileInfo` records;
    ``entry_count`` is their number; ``recursive`` marks whether the listing walked
    subdirectories; ``operation_status`` is a :class:`FileSystemOperationStatus`
    label; and ``operation_metadata`` carries plain descriptors. Producing this DTO
    reads nothing further.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    entries: List[FileInfo] = Field(default_factory=list)
    entry_count: int = 0
    recursive: bool = False
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    """Immutable result of searching for files (no OS object exposed).

    ``frozen=True`` makes instances immutable. ``base_path`` is the workspace-
    relative directory searched; ``pattern`` is the glob used; ``matches`` are the
    ordered :class:`FileInfo` records; ``match_count`` is their number;
    ``recursive`` marks whether the search descended subdirectories;
    ``operation_status`` is a :class:`FileSystemOperationStatus` label; and
    ``operation_metadata`` carries plain descriptors. Producing this DTO reads
    nothing further.
    """

    model_config = ConfigDict(frozen=True)

    base_path: str
    pattern: str
    matches: List[FileInfo] = Field(default_factory=list)
    match_count: int = 0
    recursive: bool = False
    operation_status: str
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)


class OperationResult(BaseModel):
    """Immutable result of a single-target filesystem operation (no OS object).

    Covers copy, move, rename, delete, exists, metadata, and directory
    create/delete. ``frozen=True`` makes instances immutable. ``operation`` is a
    :class:`FileSystemOperation` label; ``source_path``/``destination_path`` are
    the workspace-relative operands (``destination_path`` is ``None`` for
    single-path operations); ``success`` marks a completed operation; ``exists`` is
    the boolean answer for an ``EXISTS`` check (``None`` otherwise);
    ``file_info``/``directory_info`` carry the descriptor for a ``METADATA`` check
    (``None`` otherwise); ``operation_status`` is a
    :class:`FileSystemOperationStatus` label; ``artifact`` is the
    :class:`FileSystemArtifact` recorded for a change (``None`` when none applies);
    and ``operation_metadata`` carries plain descriptors. Producing this DTO runs
    nothing further.
    """

    model_config = ConfigDict(frozen=True)

    operation: str
    source_path: Optional[str] = None
    destination_path: Optional[str] = None
    success: bool = False
    exists: Optional[bool] = None
    file_info: Optional[FileInfo] = None
    directory_info: Optional[DirectoryInfo] = None
    operation_status: str
    artifact: Optional[FileSystemArtifact] = None
    operation_metadata: Dict[str, Any] = Field(default_factory=dict)
