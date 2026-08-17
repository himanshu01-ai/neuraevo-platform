"""File system capability (Sprint 15.11 — first-class filesystem ExecutionCapability).

Implements the Sprint 14.3 :class:`ExecutionCapability` contract by coordinating an
isolated workspace, a filesystem execution seam, and an artifact manager into one
filesystem operation: resolve the workspace → delegate the operation to the
execution layer (which confines all I/O to the workspace root) → record an artifact
for any change → return an immutable result DTO.

The actual filesystem logic runs behind the injectable :class:`FileSystemExecutor`
seam — the analog of the Python layer's ``PythonExecutor`` — so it stays replaceable
and testable; the default :class:`LocalFileSystemExecutor` performs stdlib
``pathlib``/``shutil`` I/O and never lets a ``Path``, file handle, or OS object
escape into a DTO. The capability itself coordinates only: it owns no filesystem
logic and no planning. Stateless beyond its injected collaborators and a workspace
root config; the workspace enforces isolation and rejects traversal/absolute-path
escapes. Strictly additive to Sprints 15.1–15.10 — it moves no Runtime, Planning,
Browser, or Python code.
"""

import base64
from typing import Optional, Union

from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
    CapabilityExecutionStatus,
)
from app.services.runtime.filesystem_artifact_manager import (
    FileSystemArtifactManager,
)
from app.services.runtime.filesystem_capability_models import (
    FileSystemArtifactType,
    FileSystemOperation,
    FileSystemOperationRequest,
    FileSystemOperationStatus,
)
from app.services.runtime.filesystem_execution import (
    FileSystemExecutor,
    LocalFileSystemExecutor,
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
    FileSystemWorkspaceManager,
)

# Everything ``run`` may return; the runtime bridge serialises whichever it gets.
FileSystemRunResult = Union[
    FileReadResult,
    FileWriteResult,
    DirectoryListingResult,
    SearchResult,
    OperationResult,
]

_SUCCESS = FileSystemOperationStatus.SUCCESS.value


class FileSystemCapability(ExecutionCapability):
    """File System execution capability implementing the Sprint 14.3 contract.

    Coordinates the workspace → execution → artifact pipeline. ``run`` resolves a
    workspace, delegates the operation to the injected
    :class:`FileSystemExecutor`, and records a :class:`FileSystemArtifact` for any
    change; ``current_workspace``/``create_temporary_workspace``/
    ``cleanup_workspace`` expose workspace lifecycle; ``execute`` bridges the
    runtime :class:`CapabilityExecutionRequest`/``Result``. Stateless beyond its
    injected collaborators and workspace-root config — it owns no filesystem logic
    and never lets a ``Path``, file handle, or OS object escape.
    """

    def __init__(
        self,
        executor: Optional[FileSystemExecutor] = None,
        artifact_manager: Optional[FileSystemArtifactManager] = None,
        workspace_manager: Optional[FileSystemWorkspaceManager] = None,
        workspace_root: Optional[str] = None,
    ) -> None:
        self.executor = executor or LocalFileSystemExecutor()
        self.artifact_manager = artifact_manager or FileSystemArtifactManager()
        self.workspace_manager = workspace_manager or FileSystemWorkspaceManager()
        self.workspace_root = workspace_root

    # --- workspace lifecycle --------------------------------------------
    def current_workspace(self) -> FileSystemWorkspace:
        """Return the persistent workspace rooted at the configured root."""
        return self.workspace_manager.current_workspace(self.workspace_root)

    def create_temporary_workspace(self, prefix: str = "fs") -> FileSystemWorkspace:
        """Return a fresh, isolated temporary workspace."""
        return self.workspace_manager.create_temporary_workspace(prefix)

    def cleanup_workspace(self, workspace: FileSystemWorkspace) -> OperationResult:
        """Clean up ``workspace`` and report the outcome as an immutable result."""
        try:
            self.workspace_manager.cleanup(workspace)
        except OSError as exc:  # graceful — never leak the OS object
            return OperationResult(
                operation="CLEANUP",
                source_path=workspace.root_path,
                success=False,
                operation_status=FileSystemOperationStatus.FAILED.value,
                operation_metadata={"error": type(exc).__name__},
            )
        return OperationResult(
            operation="CLEANUP",
            source_path=workspace.root_path,
            success=True,
            operation_status=_SUCCESS,
            operation_metadata={"workspace_id": workspace.workspace_id},
        )

    # --- native API ------------------------------------------------------
    def run(
        self,
        request: FileSystemOperationRequest,
        workspace: Optional[FileSystemWorkspace] = None,
    ) -> FileSystemRunResult:
        """Run one operation in ``workspace`` (default: the current workspace).

        Delegates the operation to the injected executor, then records an artifact
        for any change (created/modified/deleted). Never raises for user errors —
        a missing path, an unsafe path, or an OS error is reported as a graceful
        ``NOT_FOUND``/``FAILED`` result.
        """
        active = workspace or self.current_workspace()
        result = self.executor.perform(active, request)
        return self._with_artifact(request, result)

    # --- ExecutionCapability contract (Sprint 14.3) ---------------------
    def execute(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        """Bridge the runtime contract to one filesystem operation.

        Reads the operation and its operands from ``capability_inputs``, runs it in
        the current workspace, and maps the result to a
        :class:`CapabilityExecutionResult` with plain, JSON-serialisable outputs
        (binary content is base64-encoded) — never a ``Path`` or OS object.
        """
        inputs = request.capability_inputs
        fs_request = FileSystemOperationRequest(
            operation=inputs.get("operation", ""),
            path=inputs.get("path", "") or "",
            destination=inputs.get("destination"),
            content=inputs.get("content"),
            binary_content=inputs.get("binary_content"),
            binary=bool(inputs.get("binary", False)),
            pattern=inputs.get("pattern"),
            recursive=bool(inputs.get("recursive", False)),
            overwrite=bool(inputs.get("overwrite", True)),
            encoding=inputs.get("encoding", "utf-8"),
        )
        result = self.run(fs_request)
        status = (
            CapabilityExecutionStatus.COMPLETED.value
            if result.operation_status == _SUCCESS
            else CapabilityExecutionStatus.FAILED.value
        )
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=status,
            capability_outputs=self._serialize(result),
            execution_metadata={
                "operation": fs_request.operation,
                "operation_status": result.operation_status,
            },
        )

    # --- artifact coordination ------------------------------------------
    def _with_artifact(
        self, request: FileSystemOperationRequest, result: FileSystemRunResult
    ) -> FileSystemRunResult:
        """Record a change artifact on ``result`` when the operation mutated state."""
        if getattr(result, "operation_status", "") != _SUCCESS:
            return result
        operation = request.operation
        if operation in (
            FileSystemOperation.WRITE.value,
            FileSystemOperation.APPEND.value,
        ):
            artifact_type = (
                FileSystemArtifactType.CREATED.value
                if getattr(result, "created", False)
                else FileSystemArtifactType.MODIFIED.value
            )
            return self._attach(
                result,
                artifact_type,
                result.path,
                {"operation": operation, "bytes_written": result.bytes_written},
            )
        if operation == FileSystemOperation.COPY.value:
            return self._attach(
                result,
                FileSystemArtifactType.CREATED.value,
                result.destination_path,
                {"operation": operation},
            )
        if operation in (
            FileSystemOperation.MOVE.value,
            FileSystemOperation.RENAME.value,
        ):
            return self._attach(
                result,
                FileSystemArtifactType.MODIFIED.value,
                result.destination_path,
                {"operation": operation, "source": result.source_path},
            )
        if operation == FileSystemOperation.DELETE.value:
            return self._attach(
                result,
                FileSystemArtifactType.DELETED.value,
                result.source_path,
                {"operation": operation},
            )
        if operation == FileSystemOperation.CREATE_DIRECTORY.value:
            if result.operation_metadata.get("already_existed"):
                return result
            return self._attach(
                result,
                FileSystemArtifactType.CREATED.value,
                result.source_path,
                {"operation": operation, "is_directory": True},
            )
        if operation == FileSystemOperation.DELETE_DIRECTORY.value:
            return self._attach(
                result,
                FileSystemArtifactType.DELETED.value,
                result.source_path,
                {"operation": operation, "is_directory": True},
            )
        return result

    def _attach(self, result, artifact_type, path, metadata):
        """Return ``result`` with a freshly built artifact attached (immutable copy)."""
        if not path:
            return result
        name = path.rsplit("/", 1)[-1] or path
        artifact = self.artifact_manager.build(artifact_type, name, path, metadata)
        return result.model_copy(update={"artifact": artifact})

    # --- runtime bridge helper ------------------------------------------
    @staticmethod
    def _serialize(result: FileSystemRunResult) -> dict:
        """Return a plain, JSON-serialisable dict of ``result`` (no bytes/objects).

        Nested DTOs become plain dicts and any binary content is base64-encoded, so
        nothing but plain data crosses the runtime boundary.
        """
        data = result.model_dump()
        binary = data.get("binary_content")
        if isinstance(binary, (bytes, bytearray)):
            data["binary_content"] = base64.b64encode(bytes(binary)).decode("ascii")
        return data
