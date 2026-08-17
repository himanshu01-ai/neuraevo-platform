"""File system execution layer (Sprint 15.11 — the replaceable I/O seam).

Defines the :class:`FileSystemExecutor` seam that performs the actual filesystem
logic and its default :class:`LocalFileSystemExecutor` — the analog of the Python
layer's ``PythonExecutor``/``SafePythonExecutor``. The capability coordinates; this
layer performs. Every operation resolves its path *through* the injected
:class:`FileSystemWorkspace` (so traversal and absolute-path escapes are rejected
before any I/O), reads/writes text or bytes with ``pathlib``/``shutil``, and turns
missing paths, conflicts, unsafe paths, and OS errors into graceful result DTOs
whose metadata carries only plain strings — never a ``Path``, file handle, or
exception object.

It contains no planning, no artifact bookkeeping, and no runtime coordination —
those belong to the capability. Deterministic and offline (stdlib only); no SDK,
network, thread, or subprocess is used. Strictly additive to Sprints 15.1–15.10.
"""

import pathlib
import shutil
from abc import ABC, abstractmethod
from typing import Union

from app.services.runtime.filesystem_capability_models import (
    DirectoryInfo,
    FileInfo,
    FileSystemOperation,
    FileSystemOperationRequest,
    FileSystemOperationStatus,
    FileType,
)
from app.services.runtime.filesystem_results import (
    DirectoryListingResult,
    FileReadResult,
    FileWriteResult,
    OperationResult,
    SearchResult,
)
from app.services.runtime.filesystem_workspace import (
    FileSystemWorkspace,
    WorkspacePathError,
)

_SUCCESS = FileSystemOperationStatus.SUCCESS.value
_FAILED = FileSystemOperationStatus.FAILED.value
_NOT_FOUND = FileSystemOperationStatus.NOT_FOUND.value

# The union every operation may return; the capability enriches these with
# artifacts but never constructs a different shape.
FileSystemOperationOutcome = Union[
    FileReadResult,
    FileWriteResult,
    DirectoryListingResult,
    SearchResult,
    OperationResult,
]


class FileSystemExecutor(ABC):
    """Replaceable seam that performs one filesystem operation and reports a DTO.

    Concrete executors own all filesystem mechanics behind this single interface so
    the capability stays testable and provider-independent. An executor must never
    let a ``Path``, file handle, or OS/exception object escape — it returns only a
    plain result DTO, always confining I/O to the given workspace's root.
    """

    @abstractmethod
    def perform(
        self,
        workspace: FileSystemWorkspace,
        request: FileSystemOperationRequest,
    ) -> FileSystemOperationOutcome:
        """Perform ``request`` inside ``workspace`` and return its result DTO."""


class LocalFileSystemExecutor(FileSystemExecutor):
    """Default executor: real filesystem I/O confined to the workspace root.

    Dispatches on the request's operation to a focused handler, each of which
    resolves its path through the workspace (rejecting escapes), performs the
    minimal ``pathlib``/``shutil`` I/O, and returns a graceful result DTO — a
    missing path becomes ``NOT_FOUND``, a conflict/unsafe path/OS error becomes
    ``FAILED`` with a plain error string. Stateless — it holds nothing between calls
    and creates no threads or processes.
    """

    def perform(
        self,
        workspace: FileSystemWorkspace,
        request: FileSystemOperationRequest,
    ) -> FileSystemOperationOutcome:
        operation = request.operation
        if operation == FileSystemOperation.READ.value:
            return self._read(workspace, request)
        if operation in (
            FileSystemOperation.WRITE.value,
            FileSystemOperation.APPEND.value,
        ):
            return self._write(workspace, request)
        if operation == FileSystemOperation.COPY.value:
            return self._copy(workspace, request)
        if operation in (
            FileSystemOperation.MOVE.value,
            FileSystemOperation.RENAME.value,
        ):
            return self._move(workspace, request)
        if operation == FileSystemOperation.DELETE.value:
            return self._delete(workspace, request)
        if operation == FileSystemOperation.EXISTS.value:
            return self._exists(workspace, request)
        if operation == FileSystemOperation.METADATA.value:
            return self._metadata(workspace, request)
        if operation == FileSystemOperation.CREATE_DIRECTORY.value:
            return self._create_directory(workspace, request)
        if operation == FileSystemOperation.DELETE_DIRECTORY.value:
            return self._delete_directory(workspace, request)
        if operation == FileSystemOperation.LIST_DIRECTORY.value:
            return self._list_directory(workspace, request, request.recursive)
        if operation == FileSystemOperation.LIST_RECURSIVE.value:
            return self._list_directory(workspace, request, True)
        if operation == FileSystemOperation.SEARCH.value:
            return self._search(workspace, request)
        return OperationResult(
            operation=operation or "UNKNOWN",
            operation_status=_FAILED,
            operation_metadata={"error": f"unsupported operation: {operation}"},
        )

    # --- file content ---------------------------------------------------
    def _read(self, workspace, request) -> FileReadResult:
        try:
            resolved, rel = workspace.resolve(request.path)
        except WorkspacePathError as exc:
            return FileReadResult(
                path=str(request.path),
                operation_status=_FAILED,
                operation_metadata={"error": str(exc)},
            )
        if not resolved.exists():
            return FileReadResult(
                path=rel,
                operation_status=_NOT_FOUND,
                operation_metadata={"error": "file not found"},
            )
        if resolved.is_dir():
            return FileReadResult(
                path=rel,
                operation_status=_FAILED,
                operation_metadata={"error": "path is a directory"},
            )
        try:
            raw = resolved.read_bytes()
        except OSError as exc:
            return FileReadResult(
                path=rel,
                operation_status=_FAILED,
                operation_metadata={"error": type(exc).__name__},
            )
        if request.binary:
            return FileReadResult(
                path=rel,
                binary_content=raw,
                is_binary=True,
                size_bytes=len(raw),
                operation_status=_SUCCESS,
            )
        try:
            text = raw.decode(request.encoding)
        except (UnicodeDecodeError, LookupError) as exc:
            return FileReadResult(
                path=rel,
                operation_status=_FAILED,
                operation_metadata={"error": f"decode error: {type(exc).__name__}"},
            )
        return FileReadResult(
            path=rel,
            content=text,
            is_binary=False,
            size_bytes=len(raw),
            encoding=request.encoding,
            operation_status=_SUCCESS,
        )

    def _write(self, workspace, request) -> FileWriteResult:
        is_append = request.operation == FileSystemOperation.APPEND.value
        operation = (
            FileSystemOperation.APPEND.value
            if is_append
            else FileSystemOperation.WRITE.value
        )
        try:
            resolved, rel = workspace.resolve(request.path)
        except WorkspacePathError as exc:
            return FileWriteResult(
                path=str(request.path),
                operation=operation,
                operation_status=_FAILED,
                operation_metadata={"error": str(exc)},
            )
        if resolved.is_dir():
            return FileWriteResult(
                path=rel,
                operation=operation,
                operation_status=_FAILED,
                operation_metadata={"error": "path is a directory"},
            )
        existed = resolved.exists()
        if not is_append and existed and not request.overwrite:
            return FileWriteResult(
                path=rel,
                operation=operation,
                created=False,
                operation_status=_FAILED,
                operation_metadata={"error": "file exists and overwrite is disabled"},
            )
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            if request.binary:
                data = request.binary_content or b""
                mode = "ab" if is_append else "wb"
                with open(resolved, mode) as handle:
                    handle.write(data)
                written = len(data)
            else:
                text = request.content or ""
                mode = "a" if is_append else "w"
                with open(resolved, mode, encoding=request.encoding) as handle:
                    handle.write(text)
                written = len(text.encode(request.encoding))
        except OSError as exc:
            return FileWriteResult(
                path=rel,
                operation=operation,
                operation_status=_FAILED,
                operation_metadata={"error": type(exc).__name__},
            )
        return FileWriteResult(
            path=rel,
            operation=operation,
            bytes_written=written,
            created=not existed,
            is_binary=request.binary,
            operation_status=_SUCCESS,
        )

    # --- single-target operations ---------------------------------------
    def _copy(self, workspace, request) -> OperationResult:
        resolved = self._resolve_pair(
            workspace, request, FileSystemOperation.COPY.value
        )
        if isinstance(resolved, OperationResult):
            return resolved
        src, src_rel, dst, dst_rel = resolved
        if not src.exists():
            return self._failed_pair(
                FileSystemOperation.COPY.value, src_rel, dst_rel, "source not found",
                status=_NOT_FOUND,
            )
        if src.is_dir():
            return self._failed_pair(
                FileSystemOperation.COPY.value, src_rel, dst_rel, "source is a directory"
            )
        if dst.exists() and not request.overwrite:
            return self._failed_pair(
                FileSystemOperation.COPY.value, src_rel, dst_rel,
                "destination exists and overwrite is disabled",
            )
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        except OSError as exc:
            return self._failed_pair(
                FileSystemOperation.COPY.value, src_rel, dst_rel, type(exc).__name__
            )
        return OperationResult(
            operation=FileSystemOperation.COPY.value,
            source_path=src_rel,
            destination_path=dst_rel,
            success=True,
            operation_status=_SUCCESS,
        )

    def _move(self, workspace, request) -> OperationResult:
        operation = (
            FileSystemOperation.RENAME.value
            if request.operation == FileSystemOperation.RENAME.value
            else FileSystemOperation.MOVE.value
        )
        resolved = self._resolve_pair(workspace, request, operation)
        if isinstance(resolved, OperationResult):
            return resolved
        src, src_rel, dst, dst_rel = resolved
        if not src.exists():
            return self._failed_pair(
                operation, src_rel, dst_rel, "source not found", status=_NOT_FOUND
            )
        if dst.exists() and not request.overwrite:
            return self._failed_pair(
                operation, src_rel, dst_rel,
                "destination exists and overwrite is disabled",
            )
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()
            shutil.move(str(src), str(dst))
        except OSError as exc:
            return self._failed_pair(operation, src_rel, dst_rel, type(exc).__name__)
        return OperationResult(
            operation=operation,
            source_path=src_rel,
            destination_path=dst_rel,
            success=True,
            operation_status=_SUCCESS,
        )

    def _delete(self, workspace, request) -> OperationResult:
        try:
            resolved, rel = workspace.resolve(request.path)
        except WorkspacePathError as exc:
            return self._failed_single(
                FileSystemOperation.DELETE.value, str(request.path), str(exc)
            )
        if not resolved.exists():
            return OperationResult(
                operation=FileSystemOperation.DELETE.value,
                source_path=rel,
                operation_status=_NOT_FOUND,
                operation_metadata={"error": "file not found"},
            )
        if resolved.is_dir():
            return self._failed_single(
                FileSystemOperation.DELETE.value, rel,
                "path is a directory; use delete_directory",
            )
        try:
            resolved.unlink()
        except OSError as exc:
            return self._failed_single(
                FileSystemOperation.DELETE.value, rel, type(exc).__name__
            )
        return OperationResult(
            operation=FileSystemOperation.DELETE.value,
            source_path=rel,
            success=True,
            operation_status=_SUCCESS,
        )

    def _exists(self, workspace, request) -> OperationResult:
        try:
            resolved, rel = workspace.resolve(request.path)
        except WorkspacePathError as exc:
            return self._failed_single(
                FileSystemOperation.EXISTS.value, str(request.path), str(exc)
            )
        present = resolved.exists()
        metadata = {}
        if present:
            metadata["file_type"] = (
                FileType.DIRECTORY.value if resolved.is_dir() else FileType.FILE.value
            )
        return OperationResult(
            operation=FileSystemOperation.EXISTS.value,
            source_path=rel,
            success=True,
            exists=present,
            operation_status=_SUCCESS,
            operation_metadata=metadata,
        )

    def _metadata(self, workspace, request) -> OperationResult:
        try:
            resolved, rel = workspace.resolve(request.path)
        except WorkspacePathError as exc:
            return self._failed_single(
                FileSystemOperation.METADATA.value, str(request.path), str(exc)
            )
        if not resolved.exists():
            return OperationResult(
                operation=FileSystemOperation.METADATA.value,
                source_path=rel,
                operation_status=_NOT_FOUND,
                operation_metadata={"error": "path not found"},
            )
        if resolved.is_dir():
            return OperationResult(
                operation=FileSystemOperation.METADATA.value,
                source_path=rel,
                success=True,
                directory_info=self._directory_info(resolved, rel),
                operation_status=_SUCCESS,
            )
        return OperationResult(
            operation=FileSystemOperation.METADATA.value,
            source_path=rel,
            success=True,
            file_info=self._file_info(resolved, rel),
            operation_status=_SUCCESS,
        )

    # --- directory operations -------------------------------------------
    def _create_directory(self, workspace, request) -> OperationResult:
        try:
            resolved, rel = workspace.resolve(request.path)
        except WorkspacePathError as exc:
            return self._failed_single(
                FileSystemOperation.CREATE_DIRECTORY.value, str(request.path), str(exc)
            )
        if resolved.exists():
            if resolved.is_dir():
                return OperationResult(
                    operation=FileSystemOperation.CREATE_DIRECTORY.value,
                    source_path=rel,
                    success=True,
                    operation_status=_SUCCESS,
                    operation_metadata={"already_existed": True},
                )
            return self._failed_single(
                FileSystemOperation.CREATE_DIRECTORY.value, rel,
                "a file already exists at this path",
            )
        try:
            resolved.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return self._failed_single(
                FileSystemOperation.CREATE_DIRECTORY.value, rel, type(exc).__name__
            )
        return OperationResult(
            operation=FileSystemOperation.CREATE_DIRECTORY.value,
            source_path=rel,
            success=True,
            operation_status=_SUCCESS,
        )

    def _delete_directory(self, workspace, request) -> OperationResult:
        try:
            resolved, rel = workspace.resolve(request.path)
        except WorkspacePathError as exc:
            return self._failed_single(
                FileSystemOperation.DELETE_DIRECTORY.value, str(request.path), str(exc)
            )
        if not resolved.exists():
            return OperationResult(
                operation=FileSystemOperation.DELETE_DIRECTORY.value,
                source_path=rel,
                operation_status=_NOT_FOUND,
                operation_metadata={"error": "directory not found"},
            )
        if not resolved.is_dir():
            return self._failed_single(
                FileSystemOperation.DELETE_DIRECTORY.value, rel,
                "path is not a directory",
            )
        try:
            if request.recursive:
                shutil.rmtree(resolved)
            else:
                resolved.rmdir()
        except OSError as exc:
            error = (
                "directory not empty; pass recursive=True"
                if not request.recursive
                else type(exc).__name__
            )
            return self._failed_single(
                FileSystemOperation.DELETE_DIRECTORY.value, rel, error
            )
        return OperationResult(
            operation=FileSystemOperation.DELETE_DIRECTORY.value,
            source_path=rel,
            success=True,
            operation_status=_SUCCESS,
        )

    def _list_directory(
        self, workspace, request, recursive
    ) -> DirectoryListingResult:
        try:
            resolved, rel = workspace.resolve(request.path or "")
        except WorkspacePathError as exc:
            return DirectoryListingResult(
                path=str(request.path),
                recursive=recursive,
                operation_status=_FAILED,
                operation_metadata={"error": str(exc)},
            )
        if not resolved.exists():
            return DirectoryListingResult(
                path=rel,
                recursive=recursive,
                operation_status=_NOT_FOUND,
                operation_metadata={"error": "directory not found"},
            )
        if not resolved.is_dir():
            return DirectoryListingResult(
                path=rel,
                recursive=recursive,
                operation_status=_FAILED,
                operation_metadata={"error": "path is not a directory"},
            )
        try:
            if recursive:
                paths = sorted(resolved.rglob("*"), key=lambda p: p.as_posix())
            else:
                paths = sorted(resolved.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            return DirectoryListingResult(
                path=rel,
                recursive=recursive,
                operation_status=_FAILED,
                operation_metadata={"error": type(exc).__name__},
            )
        entries = [self._entry_info(workspace, path) for path in paths]
        return DirectoryListingResult(
            path=rel,
            entries=entries,
            entry_count=len(entries),
            recursive=recursive,
            operation_status=_SUCCESS,
        )

    def _search(self, workspace, request) -> SearchResult:
        pattern = request.pattern or "*"
        try:
            resolved, rel = workspace.resolve(request.path or "")
        except WorkspacePathError as exc:
            return SearchResult(
                base_path=str(request.path),
                pattern=pattern,
                recursive=request.recursive,
                operation_status=_FAILED,
                operation_metadata={"error": str(exc)},
            )
        if not resolved.exists() or not resolved.is_dir():
            return SearchResult(
                base_path=rel,
                pattern=pattern,
                recursive=request.recursive,
                operation_status=_FAILED,
                operation_metadata={"error": "base path is not a directory"},
            )
        try:
            globber = resolved.rglob if request.recursive else resolved.glob
            matches = sorted(
                (p for p in globber(pattern) if p.is_file()),
                key=lambda p: p.as_posix(),
            )
        except OSError as exc:
            return SearchResult(
                base_path=rel,
                pattern=pattern,
                recursive=request.recursive,
                operation_status=_FAILED,
                operation_metadata={"error": type(exc).__name__},
            )
        infos = [self._entry_info(workspace, path) for path in matches]
        return SearchResult(
            base_path=rel,
            pattern=pattern,
            matches=infos,
            match_count=len(infos),
            recursive=request.recursive,
            operation_status=_SUCCESS,
        )

    # --- descriptor + failure helpers -----------------------------------
    def _resolve_pair(self, workspace, request, operation):
        """Resolve source + destination, or return a graceful ``FAILED`` result."""
        if not request.destination:
            try:
                _, src_rel = workspace.resolve(request.path)
            except WorkspacePathError:
                src_rel = str(request.path)
            return self._failed_pair(operation, src_rel, None, "destination is required")
        try:
            src, src_rel = workspace.resolve(request.path)
            dst, dst_rel = workspace.resolve(request.destination)
        except WorkspacePathError as exc:
            return self._failed_pair(
                operation, str(request.path), str(request.destination), str(exc)
            )
        return src, src_rel, dst, dst_rel

    def _entry_info(self, workspace, path) -> FileInfo:
        rel = workspace.relative(path)
        is_dir = path.is_dir()
        try:
            stat = path.stat()
            size = 0 if is_dir else stat.st_size
            mtime = stat.st_mtime
        except OSError:
            size, mtime = 0, 0.0
        return FileInfo(
            path=rel,
            name=path.name,
            file_type=FileType.DIRECTORY.value if is_dir else FileType.FILE.value,
            size_bytes=size,
            modified_time=mtime,
            file_metadata={} if is_dir else {"suffix": path.suffix.lower()},
        )

    def _file_info(self, resolved: pathlib.Path, rel: str) -> FileInfo:
        try:
            stat = resolved.stat()
            size, mtime = stat.st_size, stat.st_mtime
        except OSError:
            size, mtime = 0, 0.0
        return FileInfo(
            path=rel,
            name=resolved.name,
            file_type=FileType.FILE.value,
            size_bytes=size,
            modified_time=mtime,
            file_metadata={"suffix": resolved.suffix.lower()},
        )

    def _directory_info(self, resolved: pathlib.Path, rel: str) -> DirectoryInfo:
        try:
            entry_count = sum(1 for _ in resolved.iterdir())
        except OSError:
            entry_count = 0
        return DirectoryInfo(
            path=rel,
            name=resolved.name,
            entry_count=entry_count,
            directory_metadata={},
        )

    @staticmethod
    def _failed_single(operation, source, error, status=_FAILED) -> OperationResult:
        return OperationResult(
            operation=operation,
            source_path=source,
            success=False,
            operation_status=status,
            operation_metadata={"error": error},
        )

    @staticmethod
    def _failed_pair(
        operation, source, destination, error, status=_FAILED
    ) -> OperationResult:
        return OperationResult(
            operation=operation,
            source_path=source,
            destination_path=destination,
            success=False,
            operation_status=status,
            operation_metadata={"error": error},
        )
