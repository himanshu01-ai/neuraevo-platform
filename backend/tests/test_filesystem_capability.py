"""Unit tests for the Sprint 15.11 File System Capability.

Covers the first-class filesystem :class:`ExecutionCapability` end to end without
any network, subprocess, or SDK: operations run in-process through the deterministic
:class:`LocalFileSystemExecutor`, and each test uses a fresh temporary workspace
root that is cleaned up.

Covers:

* the immutable DTOs (:class:`FileInfo`, :class:`DirectoryInfo`,
  :class:`FileReadResult`, :class:`FileWriteResult`, :class:`DirectoryListingResult`,
  :class:`SearchResult`, :class:`OperationResult`, :class:`FileSystemArtifact`) and
  the operation/status/type enums;
* workspace isolation, safe path resolution, temporary workspaces, and cleanup;
* read, write, append, copy, move, rename, delete, exists, and metadata;
* directory create/delete, listing, recursive listing, and search;
* text and binary files, and large files;
* the security controls (``../`` traversal, absolute-path escape, drive-letter
  escape, safe overwrite, validated existence);
* invalid paths, unsupported operations, and OS-error handling;
* artifact generation (created/modified/deleted/report), determinism, and integration;
* provider independence (an injected fake executor) and ExecutionCapability
  compliance / runtime bridge;
* the composition-root wiring; and
* regression that prior seams are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_filesystem_capability
"""

import os
import shutil
import tempfile
import unittest

from pydantic import BaseModel, ValidationError

from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionStatus,
)
from app.services.runtime.filesystem_artifact_manager import (
    FileSystemArtifactManager,
)
from app.services.runtime.filesystem_capability import FileSystemCapability
from app.services.runtime.filesystem_capability_models import (
    DirectoryInfo,
    FileInfo,
    FileSystemArtifact,
    FileSystemArtifactType,
    FileSystemOperation,
    FileSystemOperationRequest,
    FileSystemOperationStatus,
    FileType,
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
    WorkspacePathError,
)

_OP = FileSystemOperation
_STATUS = FileSystemOperationStatus


class _FsTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tempfile.mkdtemp(prefix="neuraevo_fs_test_")
        self.capability = FileSystemCapability(workspace_root=self.root)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _req(self, operation, **kwargs) -> FileSystemOperationRequest:
        return FileSystemOperationRequest(operation=operation, **kwargs)

    def _run(self, operation, **kwargs):
        return self.capability.run(self._req(operation, **kwargs))

    def _abs(self, *parts) -> str:
        return os.path.join(self.root, *parts)


# =====================================================================
# DTOs
# =====================================================================
class FsDtoTests(unittest.TestCase):
    def test_operation_enum_values(self):
        self.assertIn("READ", [o.value for o in FileSystemOperation])
        self.assertIn("LIST_RECURSIVE", [o.value for o in FileSystemOperation])
        self.assertEqual(len(list(FileSystemOperation)), 14)

    def test_status_and_type_values(self):
        self.assertEqual(
            [s.value for s in FileSystemOperationStatus],
            ["SUCCESS", "NOT_FOUND", "FAILED"],
        )
        self.assertEqual([t.value for t in FileType], ["FILE", "DIRECTORY"])
        self.assertEqual(
            [a.value for a in FileSystemArtifactType],
            ["CREATED", "MODIFIED", "DELETED", "REPORT"],
        )

    def test_request_defaults_and_immutable(self):
        req = FileSystemOperationRequest(operation="READ", path="a.txt")
        self.assertEqual(req.encoding, "utf-8")
        self.assertTrue(req.overwrite)
        self.assertFalse(req.recursive)
        with self.assertRaises(ValidationError):
            req.path = "b.txt"

    def test_result_dtos_immutable(self):
        read = FileReadResult(path="a", operation_status="SUCCESS")
        write = FileWriteResult(path="a", operation="WRITE", operation_status="SUCCESS")
        listing = DirectoryListingResult(path="d", operation_status="SUCCESS")
        search = SearchResult(base_path="d", pattern="*", operation_status="SUCCESS")
        op = OperationResult(operation="DELETE", operation_status="SUCCESS")
        for dto in (read, write, listing, search, op):
            with self.assertRaises(ValidationError):
                dto.operation_status = "FAILED"

    def test_info_and_artifact_immutable(self):
        info = FileInfo(path="a.txt", name="a.txt", file_type="FILE")
        directory = DirectoryInfo(path="d", name="d")
        artifact = FileSystemArtifact(
            artifact_id="x", artifact_type="CREATED", artifact_name="a.txt",
            artifact_path="a.txt",
        )
        with self.assertRaises(ValidationError):
            info.size_bytes = 5
        with self.assertRaises(ValidationError):
            directory.entry_count = 2
        with self.assertRaises(ValidationError):
            artifact.artifact_type = "DELETED"


# =====================================================================
# Workspace isolation, safe paths, lifecycle
# =====================================================================
class FsWorkspaceTests(_FsTestBase):
    def test_current_workspace_rooted_at_configured_root(self):
        workspace = self.capability.current_workspace()
        self.assertEqual(
            os.path.realpath(workspace.root_path), os.path.realpath(self.root)
        )
        self.assertTrue(workspace.exists())
        self.assertFalse(workspace.is_temporary)

    def test_temporary_workspace_is_isolated(self):
        temp = self.capability.create_temporary_workspace()
        self.assertTrue(temp.is_temporary)
        self.assertTrue(temp.exists())
        self.assertNotEqual(
            os.path.realpath(temp.root_path), os.path.realpath(self.root)
        )
        self.assertIsNotNone(temp.temp_path)

    def test_safe_resolution_stays_within_root(self):
        workspace = self.capability.current_workspace()
        resolved, rel = workspace.resolve("sub/dir/file.txt")
        self.assertEqual(rel, "sub/dir/file.txt")
        self.assertTrue(
            os.path.realpath(str(resolved)).startswith(os.path.realpath(self.root))
        )

    def test_resolution_normalizes_redundant_segments(self):
        workspace = self.capability.current_workspace()
        self.assertEqual(workspace.normalize("./a/./b//c"), "a/b/c")
        self.assertEqual(workspace.normalize(""), "")

    def test_traversal_raises_workspace_path_error(self):
        workspace = self.capability.current_workspace()
        for unsafe in ("../secret", "a/../../b", "../../../etc/passwd"):
            with self.assertRaises(WorkspacePathError):
                workspace.resolve(unsafe)

    def test_absolute_and_drive_paths_raise(self):
        workspace = self.capability.current_workspace()
        for unsafe in ("/etc/passwd", "C:/Windows/system32", "\\\\host\\share"):
            with self.assertRaises(WorkspacePathError):
                workspace.resolve(unsafe)

    def test_cleanup_empties_current_workspace_but_keeps_root(self):
        self._run(_OP.WRITE.value, path="keep/a.txt", content="x")
        workspace = self.capability.current_workspace()
        result = self.capability.cleanup_workspace(workspace)
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertTrue(workspace.exists())
        self.assertEqual(list(os.scandir(self.root)), [])

    def test_cleanup_removes_temporary_workspace(self):
        temp = self.capability.create_temporary_workspace()
        path = temp.root_path
        result = self.capability.cleanup_workspace(temp)
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertFalse(os.path.exists(path))

    def test_workspace_manager_is_stateless(self):
        self.assertEqual(vars(FileSystemWorkspaceManager()), {})


# =====================================================================
# Read / Write / Append
# =====================================================================
class FsReadWriteTests(_FsTestBase):
    def test_write_creates_file(self):
        result = self._run(_OP.WRITE.value, path="a.txt", content="hello")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertTrue(result.created)
        self.assertEqual(result.bytes_written, 5)
        self.assertTrue(os.path.exists(self._abs("a.txt")))

    def test_write_creates_parent_directories(self):
        result = self._run(_OP.WRITE.value, path="x/y/z.txt", content="deep")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertTrue(os.path.exists(self._abs("x", "y", "z.txt")))

    def test_read_returns_content(self):
        self._run(_OP.WRITE.value, path="a.txt", content="hello world")
        result = self._run(_OP.READ.value, path="a.txt")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.content, "hello world")
        self.assertEqual(result.encoding, "utf-8")
        self.assertFalse(result.is_binary)

    def test_read_missing_file_is_not_found(self):
        result = self._run(_OP.READ.value, path="missing.txt")
        self.assertEqual(result.operation_status, _STATUS.NOT_FOUND.value)

    def test_read_directory_fails(self):
        self._run(_OP.CREATE_DIRECTORY.value, path="d")
        result = self._run(_OP.READ.value, path="d")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)

    def test_overwrite_replaces_content(self):
        self._run(_OP.WRITE.value, path="a.txt", content="first")
        result = self._run(_OP.WRITE.value, path="a.txt", content="second")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertFalse(result.created)
        self.assertEqual(self._run(_OP.READ.value, path="a.txt").content, "second")

    def test_safe_overwrite_blocks_when_disabled(self):
        self._run(_OP.WRITE.value, path="a.txt", content="first")
        result = self._run(_OP.WRITE.value, path="a.txt", content="second", overwrite=False)
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("overwrite", result.operation_metadata["error"])
        self.assertEqual(self._run(_OP.READ.value, path="a.txt").content, "first")

    def test_append_extends_file(self):
        self._run(_OP.WRITE.value, path="a.txt", content="ab")
        result = self._run(_OP.APPEND.value, path="a.txt", content="cd")
        self.assertEqual(result.operation, _OP.APPEND.value)
        self.assertFalse(result.created)
        self.assertEqual(self._run(_OP.READ.value, path="a.txt").content, "abcd")

    def test_append_creates_when_missing(self):
        result = self._run(_OP.APPEND.value, path="new.txt", content="x")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertTrue(result.created)


# =====================================================================
# Binary and large files
# =====================================================================
class FsBinaryTests(_FsTestBase):
    def test_binary_round_trip(self):
        payload = bytes(range(256))
        self._run(_OP.WRITE.value, path="b.bin", binary=True, binary_content=payload)
        result = self._run(_OP.READ.value, path="b.bin", binary=True)
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertTrue(result.is_binary)
        self.assertEqual(result.binary_content, payload)
        self.assertIsNone(result.content)

    def test_binary_append(self):
        self._run(_OP.WRITE.value, path="b.bin", binary=True, binary_content=b"\x01\x02")
        self._run(_OP.APPEND.value, path="b.bin", binary=True, binary_content=b"\x03")
        result = self._run(_OP.READ.value, path="b.bin", binary=True)
        self.assertEqual(result.binary_content, b"\x01\x02\x03")

    def test_large_file_round_trip(self):
        big = "x" * (2 * 1024 * 1024)  # 2 MB of text
        write = self._run(_OP.WRITE.value, path="big.txt", content=big)
        self.assertEqual(write.bytes_written, len(big))
        result = self._run(_OP.READ.value, path="big.txt")
        self.assertEqual(result.size_bytes, len(big))
        self.assertEqual(len(result.content), len(big))


# =====================================================================
# Copy / Move / Rename / Delete / Exists / Metadata
# =====================================================================
class FsSingleTargetTests(_FsTestBase):
    def test_copy_duplicates_file(self):
        self._run(_OP.WRITE.value, path="a.txt", content="data")
        result = self._run(_OP.COPY.value, path="a.txt", destination="copy/a.txt")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertTrue(os.path.exists(self._abs("a.txt")))
        self.assertEqual(self._run(_OP.READ.value, path="copy/a.txt").content, "data")

    def test_copy_missing_source_is_not_found(self):
        result = self._run(_OP.COPY.value, path="missing.txt", destination="c.txt")
        self.assertEqual(result.operation_status, _STATUS.NOT_FOUND.value)

    def test_copy_requires_destination(self):
        self._run(_OP.WRITE.value, path="a.txt", content="x")
        result = self._run(_OP.COPY.value, path="a.txt")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("destination", result.operation_metadata["error"])

    def test_move_relocates_file(self):
        self._run(_OP.WRITE.value, path="a.txt", content="data")
        result = self._run(_OP.MOVE.value, path="a.txt", destination="moved/a.txt")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertFalse(os.path.exists(self._abs("a.txt")))
        self.assertEqual(self._run(_OP.READ.value, path="moved/a.txt").content, "data")

    def test_rename_changes_name(self):
        self._run(_OP.WRITE.value, path="old.txt", content="v")
        result = self._run(_OP.RENAME.value, path="old.txt", destination="new.txt")
        self.assertEqual(result.operation, _OP.RENAME.value)
        self.assertFalse(os.path.exists(self._abs("old.txt")))
        self.assertTrue(os.path.exists(self._abs("new.txt")))

    def test_delete_removes_file(self):
        self._run(_OP.WRITE.value, path="a.txt", content="x")
        result = self._run(_OP.DELETE.value, path="a.txt")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertFalse(os.path.exists(self._abs("a.txt")))

    def test_delete_missing_is_not_found(self):
        result = self._run(_OP.DELETE.value, path="missing.txt")
        self.assertEqual(result.operation_status, _STATUS.NOT_FOUND.value)

    def test_delete_directory_via_delete_file_fails(self):
        self._run(_OP.CREATE_DIRECTORY.value, path="d")
        result = self._run(_OP.DELETE.value, path="d")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)

    def test_exists_reports_presence_and_type(self):
        self._run(_OP.WRITE.value, path="a.txt", content="x")
        self._run(_OP.CREATE_DIRECTORY.value, path="d")
        file_result = self._run(_OP.EXISTS.value, path="a.txt")
        dir_result = self._run(_OP.EXISTS.value, path="d")
        missing = self._run(_OP.EXISTS.value, path="nope")
        self.assertTrue(file_result.exists)
        self.assertEqual(file_result.operation_metadata["file_type"], FileType.FILE.value)
        self.assertTrue(dir_result.exists)
        self.assertEqual(
            dir_result.operation_metadata["file_type"], FileType.DIRECTORY.value
        )
        self.assertFalse(missing.exists)

    def test_metadata_for_file_and_directory(self):
        self._run(_OP.WRITE.value, path="a.txt", content="hello")
        self._run(_OP.CREATE_DIRECTORY.value, path="d")
        self._run(_OP.WRITE.value, path="d/inner.txt", content="y")
        file_meta = self._run(_OP.METADATA.value, path="a.txt")
        dir_meta = self._run(_OP.METADATA.value, path="d")
        self.assertIsNotNone(file_meta.file_info)
        self.assertEqual(file_meta.file_info.size_bytes, 5)
        self.assertEqual(file_meta.file_info.file_metadata["suffix"], ".txt")
        self.assertIsNotNone(dir_meta.directory_info)
        self.assertEqual(dir_meta.directory_info.entry_count, 1)

    def test_metadata_missing_is_not_found(self):
        self.assertEqual(
            self._run(_OP.METADATA.value, path="nope").operation_status,
            _STATUS.NOT_FOUND.value,
        )


# =====================================================================
# Directory operations, recursive listing, search
# =====================================================================
class FsDirectoryTests(_FsTestBase):
    def test_create_directory(self):
        result = self._run(_OP.CREATE_DIRECTORY.value, path="a/b/c")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertTrue(os.path.isdir(self._abs("a", "b", "c")))

    def test_create_directory_idempotent_without_artifact(self):
        self._run(_OP.CREATE_DIRECTORY.value, path="d")
        result = self._run(_OP.CREATE_DIRECTORY.value, path="d")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertTrue(result.operation_metadata.get("already_existed"))
        self.assertIsNone(result.artifact)

    def test_list_directory_non_recursive(self):
        self._run(_OP.WRITE.value, path="a.txt", content="1")
        self._run(_OP.WRITE.value, path="b.txt", content="2")
        self._run(_OP.WRITE.value, path="sub/c.txt", content="3")
        result = self._run(_OP.LIST_DIRECTORY.value, path="")
        names = sorted(entry.name for entry in result.entries)
        self.assertEqual(names, ["a.txt", "b.txt", "sub"])
        self.assertFalse(result.recursive)

    def test_recursive_listing_includes_nested_entries(self):
        self._run(_OP.WRITE.value, path="a.txt", content="1")
        self._run(_OP.WRITE.value, path="sub/c.txt", content="3")
        result = self._run(_OP.LIST_RECURSIVE.value, path="")
        paths = sorted(entry.path for entry in result.entries)
        self.assertEqual(paths, ["a.txt", "sub", "sub/c.txt"])
        self.assertTrue(result.recursive)

    def test_delete_empty_directory(self):
        self._run(_OP.CREATE_DIRECTORY.value, path="empty")
        result = self._run(_OP.DELETE_DIRECTORY.value, path="empty")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertFalse(os.path.exists(self._abs("empty")))

    def test_delete_non_empty_directory_requires_recursive(self):
        self._run(_OP.WRITE.value, path="d/inner.txt", content="x")
        blocked = self._run(_OP.DELETE_DIRECTORY.value, path="d")
        self.assertEqual(blocked.operation_status, _STATUS.FAILED.value)
        self.assertIn("recursive", blocked.operation_metadata["error"])
        self.assertTrue(os.path.exists(self._abs("d")))
        allowed = self._run(_OP.DELETE_DIRECTORY.value, path="d", recursive=True)
        self.assertEqual(allowed.operation_status, _STATUS.SUCCESS.value)
        self.assertFalse(os.path.exists(self._abs("d")))

    def test_list_missing_directory_is_not_found(self):
        self.assertEqual(
            self._run(_OP.LIST_DIRECTORY.value, path="nope").operation_status,
            _STATUS.NOT_FOUND.value,
        )

    def test_search_non_recursive(self):
        self._run(_OP.WRITE.value, path="a.txt", content="1")
        self._run(_OP.WRITE.value, path="b.log", content="2")
        self._run(_OP.WRITE.value, path="sub/c.txt", content="3")
        result = self._run(_OP.SEARCH.value, path="", pattern="*.txt")
        self.assertEqual([m.path for m in result.matches], ["a.txt"])
        self.assertEqual(result.match_count, 1)

    def test_search_recursive(self):
        self._run(_OP.WRITE.value, path="a.txt", content="1")
        self._run(_OP.WRITE.value, path="sub/deep/c.txt", content="3")
        self._run(_OP.WRITE.value, path="sub/b.log", content="2")
        result = self._run(_OP.SEARCH.value, path="", pattern="*.txt", recursive=True)
        self.assertEqual(sorted(m.path for m in result.matches), ["a.txt", "sub/deep/c.txt"])
        self.assertTrue(result.recursive)


# =====================================================================
# Security: traversal, absolute escape, invalid paths, OS errors
# =====================================================================
class FsSecurityTests(_FsTestBase):
    def test_traversal_read_is_blocked(self):
        result = self._run(_OP.READ.value, path="../../../etc/passwd")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("escapes", result.operation_metadata["error"])

    def test_traversal_write_creates_nothing_outside_root(self):
        outside = os.path.join(os.path.dirname(self.root), "escaped.txt")
        self.assertFalse(os.path.exists(outside))
        result = self._run(_OP.WRITE.value, path="../escaped.txt", content="x")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertFalse(os.path.exists(outside))

    def test_absolute_path_write_is_blocked(self):
        result = self._run(_OP.WRITE.value, path="C:/Windows/hacked.txt", content="x")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("absolute", result.operation_metadata["error"])

    def test_traversal_copy_destination_is_blocked(self):
        self._run(_OP.WRITE.value, path="a.txt", content="x")
        result = self._run(_OP.COPY.value, path="a.txt", destination="../escaped.txt")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)

    def test_unsupported_operation_fails_gracefully(self):
        result = self.capability.run(self._req("FLY_TO_MOON"))
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("unsupported", result.operation_metadata["error"])

    def test_os_error_is_handled_gracefully(self):
        # A file exists at "a"; writing "a/b.txt" makes mkdir(parents) fail cleanly.
        self._run(_OP.WRITE.value, path="a", content="x")
        result = self._run(_OP.WRITE.value, path="a/b.txt", content="y")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIsInstance(result.operation_metadata["error"], str)


# =====================================================================
# Artifacts
# =====================================================================
class FsArtifactTests(_FsTestBase):
    def test_write_records_created_then_modified(self):
        created = self._run(_OP.WRITE.value, path="a.txt", content="1")
        modified = self._run(_OP.WRITE.value, path="a.txt", content="2")
        self.assertEqual(created.artifact.artifact_type, FileSystemArtifactType.CREATED.value)
        self.assertEqual(modified.artifact.artifact_type, FileSystemArtifactType.MODIFIED.value)
        self.assertEqual(created.artifact.artifact_name, "a.txt")
        self.assertEqual(created.artifact.artifact_path, "a.txt")

    def test_copy_records_created_at_destination(self):
        self._run(_OP.WRITE.value, path="a.txt", content="x")
        result = self._run(_OP.COPY.value, path="a.txt", destination="b.txt")
        self.assertEqual(result.artifact.artifact_type, FileSystemArtifactType.CREATED.value)
        self.assertEqual(result.artifact.artifact_path, "b.txt")

    def test_delete_records_deleted(self):
        self._run(_OP.WRITE.value, path="a.txt", content="x")
        result = self._run(_OP.DELETE.value, path="a.txt")
        self.assertEqual(result.artifact.artifact_type, FileSystemArtifactType.DELETED.value)

    def test_directory_create_and_delete_artifacts(self):
        created = self._run(_OP.CREATE_DIRECTORY.value, path="d")
        deleted = self._run(_OP.DELETE_DIRECTORY.value, path="d")
        self.assertEqual(created.artifact.artifact_type, FileSystemArtifactType.CREATED.value)
        self.assertTrue(created.artifact.artifact_metadata["is_directory"])
        self.assertEqual(deleted.artifact.artifact_type, FileSystemArtifactType.DELETED.value)

    def test_read_and_list_have_no_artifact(self):
        self._run(_OP.WRITE.value, path="a.txt", content="x")
        self.assertIsNone(
            getattr(self._run(_OP.READ.value, path="a.txt"), "artifact", None)
        )
        listing = self._run(_OP.LIST_DIRECTORY.value, path="")
        self.assertFalse(hasattr(listing, "artifact"))

    def test_failed_operation_has_no_artifact(self):
        result = self._run(_OP.WRITE.value, path="../x.txt", content="x")
        self.assertIsNone(result.artifact)

    def test_artifact_ids_are_deterministic(self):
        manager = FileSystemArtifactManager()
        first = manager.created("a.txt", "dir/a.txt")
        second = manager.created("a.txt", "dir/a.txt")
        self.assertEqual(first.artifact_id, second.artifact_id)
        self.assertTrue(first.artifact_id.startswith("fs-created-"))

    def test_artifact_manager_supports_report_and_is_stateless(self):
        manager = FileSystemArtifactManager()
        report = manager.report("summary.txt", "reports/summary.txt")
        self.assertEqual(report.artifact_type, FileSystemArtifactType.REPORT.value)
        self.assertEqual(vars(FileSystemArtifactManager()), {})


# =====================================================================
# Provider independence / ExecutionCapability compliance
# =====================================================================
class _FakeExecutor(FileSystemExecutor):
    def __init__(self) -> None:
        self.calls = []

    def perform(self, workspace, request):
        self.calls.append((workspace, request))
        return OperationResult(
            operation=request.operation,
            source_path=request.path,
            success=True,
            operation_status=FileSystemOperationStatus.SUCCESS.value,
            operation_metadata={"fake": True},
        )


class FsProviderTests(_FsTestBase):
    def test_provider_independence_with_injected_executor(self):
        fake = _FakeExecutor()
        capability = FileSystemCapability(executor=fake, workspace_root=self.root)
        result = capability.run(self._req(_OP.DELETE.value, path="a.txt"))
        self.assertTrue(result.operation_metadata["fake"])
        self.assertEqual(len(fake.calls), 1)

    def test_results_are_plain_dtos(self):
        self._run(_OP.WRITE.value, path="a.txt", content="x")
        result = self._run(_OP.READ.value, path="a.txt")
        self.assertIsInstance(result, FileReadResult)
        self.assertIsInstance(result, BaseModel)

    def test_capability_is_execution_capability(self):
        self.assertIsInstance(self.capability, ExecutionCapability)

    def test_local_executor_is_stateless(self):
        self.assertEqual(vars(LocalFileSystemExecutor()), {})

    def test_execute_bridges_runtime_contract_for_write(self):
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="filesystem",
            capability_inputs={"operation": "WRITE", "path": "a.txt", "content": "hi"},
        )
        result = self.capability.execute(request)
        self.assertEqual(result.execution_status, CapabilityExecutionStatus.COMPLETED.value)
        self.assertEqual(result.capability_name, "filesystem")
        self.assertTrue(result.capability_outputs["created"])
        self.assertEqual(result.execution_metadata["operation"], "WRITE")

    def test_execute_bridges_read_with_content(self):
        self._run(_OP.WRITE.value, path="a.txt", content="body")
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="filesystem",
            capability_inputs={"operation": "READ", "path": "a.txt"},
        )
        result = self.capability.execute(request)
        self.assertEqual(result.capability_outputs["content"], "body")

    def test_execute_maps_failure(self):
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="filesystem",
            capability_inputs={"operation": "READ", "path": "missing.txt"},
        )
        result = self.capability.execute(request)
        self.assertEqual(result.execution_status, CapabilityExecutionStatus.FAILED.value)

    def test_execute_outputs_are_json_serializable_plain_data(self):
        payload = b"\x00\x99\xff"
        self._run(_OP.WRITE.value, path="b.bin", binary=True, binary_content=payload)
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="filesystem",
            capability_inputs={"operation": "READ", "path": "b.bin", "binary": True},
        )
        result = self.capability.execute(request)
        # binary content is base64-encoded (a str), never raw bytes / objects
        self.assertIsInstance(result.capability_outputs["binary_content"], str)
        for value in result.capability_outputs.values():
            self.assertNotIsInstance(value, BaseModel)
            self.assertNotIsInstance(value, (bytes, bytearray))


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class FsDependencyInjectionTests(unittest.TestCase):
    def test_get_filesystem_capability_returns_capability(self):
        from app.core.dependencies import get_filesystem_capability

        capability = get_filesystem_capability()
        self.assertIsInstance(capability, FileSystemCapability)
        self.assertIsInstance(capability, ExecutionCapability)

    def test_filesystem_capability_dep_is_wired(self):
        from app.core.dependencies import FileSystemCapabilityDep

        self.assertIn(
            FileSystemCapability, getattr(FileSystemCapabilityDep, "__args__", ())
        )

    def test_wired_capability_executes(self):
        from app.core.dependencies import get_filesystem_capability

        temp_root = tempfile.mkdtemp(prefix="neuraevo_fs_di_")
        try:
            capability = FileSystemCapability(workspace_root=temp_root)
            request = CapabilityExecutionRequest(
                runtime_id="rt", execution_id="ex", execution_unit_id="u",
                capability_name="filesystem",
                capability_inputs={"operation": "WRITE", "path": "ok.txt", "content": "1"},
            )
            self.assertEqual(
                capability.execute(request).execution_status, "COMPLETED"
            )
            # the DI-provided default is also a valid capability
            self.assertIsInstance(get_filesystem_capability(), FileSystemCapability)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)


# =====================================================================
# Regression — prior seams unchanged
# =====================================================================
class FsRegressionTests(unittest.TestCase):
    def test_sprint_14_execution_capability_seam_unchanged(self):
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_sprint_15_1_registry_seam_unchanged(self):
        from app.core.dependencies import get_capability_registry

        self.assertEqual(get_capability_registry().snapshot().capability_count, 0)

    def test_sprint_15_6_browser_capability_unchanged(self):
        from app.core.dependencies import get_browser_capability

        self.assertIsInstance(get_browser_capability(), ExecutionCapability)

    def test_sprint_15_10_python_capability_unchanged(self):
        from app.core.dependencies import get_python_capability

        self.assertIsInstance(get_python_capability(), ExecutionCapability)


if __name__ == "__main__":
    unittest.main()
