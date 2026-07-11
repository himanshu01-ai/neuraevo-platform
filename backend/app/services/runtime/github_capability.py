"""GitHub capability (Sprint 15.14 — first-class GitHub ExecutionCapability).

Implements the Sprint 14.3 :class:`ExecutionCapability` contract by coordinating a
repository workspace, a repository execution seam, and an artifact manager into one
GitHub operation: validate (repository/branch/tag names, commit messages, issue ids)
→ stage the repository directory (init/clone) → delegate the operation to the
execution layer → record artifacts → return an immutable result DTO.

The actual Git logic runs behind the injectable :class:`GitHubExecutor` seam — the
analog of the Calendar layer's ``CalendarExecutor`` — so a future provider (GitHub
REST/GraphQL, Git CLI, GitLab, Bitbucket, Azure DevOps) drops in without touching the
Runtime or this capability. The default :class:`LocalGitExecutor` is a deterministic
in-memory Git simulation and never lets a git/SDK object, an API response, or a
credential escape into a DTO. The capability itself coordinates only: it owns no
provider logic and no planning. Stateless beyond its injected collaborators and
config. Strictly additive to Sprints 15.1–15.13 — it moves no Runtime, Planning,
Browser, Python, File System, Email, or Calendar code.
"""

import base64
from typing import Optional, Union

from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
    CapabilityExecutionStatus,
)
from app.services.runtime.github_artifact_manager import GitHubArtifactManager
from app.services.runtime.github_capability_models import (
    GitHubOperation,
    GitHubOperationRequest,
    GitHubOperationStatus,
    GitHubValidationError,
    deterministic_repository_id,
    validate_branch_name,
    validate_commit_message,
    validate_repository_name,
    validate_tag_name,
)
from app.services.runtime.github_execution import (
    GitHubExecutionContext,
    GitHubExecutor,
    LocalGitExecutor,
)
from app.services.runtime.github_results import (
    BranchResult,
    CreateCommitResult,
    IssueResult,
    OperationResult,
    RepositoryResult,
)
from app.services.runtime.github_workspace import (
    GitHubWorkspace,
    GitHubWorkspaceError,
    GitHubWorkspaceManager,
)

# Everything ``run`` may return; the runtime bridge serialises whichever it gets.
GitHubRunResult = Union[
    RepositoryResult,
    BranchResult,
    CreateCommitResult,
    IssueResult,
    OperationResult,
]

_SUCCESS = GitHubOperationStatus.SUCCESS.value
_FAILED = GitHubOperationStatus.FAILED.value

_OP = GitHubOperation


class GitHubCapability(ExecutionCapability):
    """GitHub execution capability implementing the Sprint 14.3 contract.

    Coordinates the validate → stage → execute → artifact pipeline. ``run`` validates
    names/messages, stages the repository directory for init/clone, delegates to the
    injected :class:`GitHubExecutor`, and records artifacts;
    ``current_workspace``/``create_temporary_workspace``/``cleanup_workspace`` expose
    repository-workspace lifecycle; ``execute`` bridges the runtime
    :class:`CapabilityExecutionRequest`/``Result``. Stateless beyond its injected
    collaborators and config — it owns no provider logic and never lets a git/SDK
    object, an API response, or a credential escape.
    """

    def __init__(
        self,
        executor: Optional[GitHubExecutor] = None,
        artifact_manager: Optional[GitHubArtifactManager] = None,
        workspace_manager: Optional[GitHubWorkspaceManager] = None,
        staging_root: Optional[str] = None,
    ) -> None:
        self.executor = executor or LocalGitExecutor()
        self.artifact_manager = artifact_manager or GitHubArtifactManager()
        self.workspace_manager = workspace_manager or GitHubWorkspaceManager()
        self.staging_root = staging_root

    # --- workspace lifecycle --------------------------------------------
    def current_workspace(self) -> GitHubWorkspace:
        """Return the persistent repository-staging workspace."""
        return self.workspace_manager.current_workspace(self.staging_root)

    def create_temporary_workspace(self, prefix: str = "repo") -> GitHubWorkspace:
        """Return a fresh, isolated temporary repository-staging workspace."""
        return self.workspace_manager.create_temporary_workspace(prefix)

    def cleanup_workspace(self, workspace: GitHubWorkspace) -> OperationResult:
        """Clean up ``workspace`` and report the outcome as an immutable result."""
        try:
            self.workspace_manager.cleanup(workspace)
        except OSError as exc:  # graceful — never leak the OS object
            return OperationResult(
                operation="CLEANUP",
                operation_status=_FAILED,
                operation_metadata={"error": type(exc).__name__},
            )
        return OperationResult(
            operation="CLEANUP",
            success=True,
            operation_status=_SUCCESS,
            operation_metadata={"workspace_id": workspace.workspace_id},
        )

    # --- native API ------------------------------------------------------
    def run(
        self,
        request: GitHubOperationRequest,
        workspace: Optional[GitHubWorkspace] = None,
    ) -> GitHubRunResult:
        """Run one operation, staging the repository directory for init/clone.

        Init/clone validate and stage a repository directory first (an unsafe name
        becomes a graceful ``FAILED``); branch/tag/commit operations validate their
        names/messages first; all delegate to the executor and record artifacts.
        Never raises for user errors.
        """
        operation = request.operation
        if operation in (_OP.INIT.value, _OP.CLONE.value):
            return self._run_repository_create(request, workspace)
        if operation == _OP.REPOSITORY_METADATA.value:
            return self._with_repo_report(
                self.executor.perform(request, self._empty_context())
            )
        if operation == _OP.CREATE_BRANCH.value:
            return self._run_create_branch(request)
        if operation == _OP.COMMIT.value:
            return self._run_commit(request)
        if operation == _OP.CREATE_TAG.value:
            return self._run_create_tag(request)
        if operation in (
            _OP.CREATE_ISSUE.value,
            _OP.UPDATE_ISSUE.value,
            _OP.CLOSE_ISSUE.value,
        ):
            return self._run_issue_change(request)
        if operation == _OP.SEARCH_ISSUES.value:
            return self._with_search_report(
                self.executor.perform(request, self._empty_context())
            )
        # OPEN, LIST_BRANCHES, CHECKOUT, DELETE_BRANCH, STATUS, STAGE, UNSTAGE,
        # HISTORY, LIST_TAGS, LIST_ISSUES, and any unsupported operation
        return self.executor.perform(request, self._empty_context())

    # --- ExecutionCapability contract (Sprint 14.3) ---------------------
    def execute(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        """Bridge the runtime contract to one GitHub operation.

        Reads the operation and its operands from ``capability_inputs``, runs it, and
        maps the result to a :class:`CapabilityExecutionResult` with plain,
        JSON-serialisable outputs — never a git/SDK object, an API response, or a
        credential.
        """
        inputs = request.capability_inputs
        github_request = GitHubOperationRequest(
            operation=inputs.get("operation", ""),
            repository_id=inputs.get("repository_id"),
            repository_name=inputs.get("repository_name"),
            repository_path=inputs.get("repository_path"),
            description=inputs.get("description"),
            source_url=inputs.get("source_url"),
            branch_name=inputs.get("branch_name"),
            files=dict(inputs.get("files", {}) or {}),
            paths=list(inputs.get("paths", []) or []),
            commit_message=inputs.get("commit_message"),
            author=inputs.get("author"),
            limit=inputs.get("limit"),
            tag_name=inputs.get("tag_name"),
            tag_message=inputs.get("tag_message"),
            commit_id=inputs.get("commit_id"),
            issue_number=inputs.get("issue_number"),
            issue_title=inputs.get("issue_title"),
            issue_body=inputs.get("issue_body"),
            labels=list(inputs.get("labels", []) or []),
            assignees=list(inputs.get("assignees", []) or []),
            issue_state=inputs.get("issue_state"),
            update_fields=dict(inputs.get("update_fields", {}) or {}),
            query=inputs.get("query"),
            state_filter=inputs.get("state_filter", "all"),
        )
        result = self.run(github_request)
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
                "operation": github_request.operation,
                "operation_status": result.operation_status,
            },
        )

    # --- repository create (init / clone) -------------------------------
    def _run_repository_create(self, request, workspace) -> RepositoryResult:
        active = workspace or self.current_workspace()
        try:
            name = validate_repository_name(request.repository_name or "repository")
            path = active.stage_repository(name)
        except (GitHubValidationError, GitHubWorkspaceError) as exc:
            return RepositoryResult(
                operation_status=_FAILED, operation_metadata={"error": str(exc)}
            )
        context = GitHubExecutionContext(
            repository_id=deterministic_repository_id(path),
            repository_path=path,
        )
        staged_request = request.model_copy(update={"repository_name": name})
        return self.executor.perform(staged_request, context)

    # --- validated changes ----------------------------------------------
    def _run_create_branch(self, request) -> BranchResult:
        try:
            name = validate_branch_name(request.branch_name)
        except GitHubValidationError as exc:
            return BranchResult(
                operation_status=_FAILED, operation_metadata={"error": str(exc)}
            )
        result = self.executor.perform(
            request.model_copy(update={"branch_name": name}), self._empty_context()
        )
        if result.operation_status != _SUCCESS:
            return result
        artifact = self.artifact_manager.branch(name, {"repository_id": request.repository_id})
        return result.model_copy(update={"artifact": artifact})

    def _run_commit(self, request) -> CreateCommitResult:
        try:
            message = validate_commit_message(request.commit_message)
        except GitHubValidationError as exc:
            return CreateCommitResult(
                operation_status=_FAILED, operation_metadata={"error": str(exc)}
            )
        result = self.executor.perform(
            request.model_copy(update={"commit_message": message}),
            self._empty_context(),
        )
        if result.operation_status != _SUCCESS or result.commit is None:
            return result
        artifact = self.artifact_manager.commit(
            result.commit.commit_id,
            {
                "message": message,
                "changed_files": len(result.commit.changed_files),
            },
        )
        return result.model_copy(update={"artifact": artifact})

    def _run_create_tag(self, request) -> OperationResult:
        try:
            name = validate_tag_name(request.tag_name)
        except GitHubValidationError as exc:
            return OperationResult(
                operation=_OP.CREATE_TAG.value,
                operation_status=_FAILED,
                operation_metadata={"error": str(exc)},
            )
        result = self.executor.perform(
            request.model_copy(update={"tag_name": name}), self._empty_context()
        )
        if result.operation_status != _SUCCESS or result.tag is None:
            return result
        artifact = self.artifact_manager.tag(name, {"commit_id": result.tag.commit_id})
        return result.model_copy(update={"artifact": artifact})

    def _run_issue_change(self, request) -> IssueResult:
        prepared = self._prepare_issue_request(request)
        result = self.executor.perform(prepared, self._empty_context())
        if result.operation_status != _SUCCESS or result.issue is None:
            return result
        artifact = self.artifact_manager.issue(
            f"#{result.issue.number} {result.issue.title}",
            {"issue_id": result.issue.issue_id, "state": result.issue.state},
        )
        return result.model_copy(update={"artifact": artifact})

    # --- reports --------------------------------------------------------
    def _with_repo_report(self, result: RepositoryResult) -> RepositoryResult:
        if result.operation_status != _SUCCESS or result.repository is None:
            return result
        artifact = self.artifact_manager.report(
            f"repository:{result.repository.name}",
            {
                "repository_id": result.repository.repository_id,
                "commit_count": result.repository.commit_count,
                "branch_count": result.repository.branch_count,
            },
        )
        return result.model_copy(update={"artifact": artifact})

    def _with_search_report(self, result: IssueResult) -> IssueResult:
        if result.operation_status != _SUCCESS:
            return result
        artifact = self.artifact_manager.report(
            "issue-search", {"match_count": result.match_count}
        )
        return result.model_copy(update={"artifact": artifact})

    # --- helpers --------------------------------------------------------
    def _prepare_issue_request(self, request) -> GitHubOperationRequest:
        """Fold the convenience issue fields into ``update_fields`` for an update."""
        if request.operation != _OP.UPDATE_ISSUE.value:
            return request
        updates = dict(request.update_fields)
        if request.issue_title is not None:
            updates.setdefault("title", request.issue_title)
        if request.issue_body is not None:
            updates.setdefault("body", request.issue_body)
        if request.issue_state is not None:
            updates.setdefault("state", request.issue_state)
        if request.labels:
            updates.setdefault("labels", list(request.labels))
        if request.assignees:
            updates.setdefault("assignees", list(request.assignees))
        return request.model_copy(update={"update_fields": updates})

    @staticmethod
    def _empty_context() -> GitHubExecutionContext:
        return GitHubExecutionContext()

    # --- runtime bridge helper ------------------------------------------
    @classmethod
    def _serialize(cls, result: GitHubRunResult) -> dict:
        """Return a plain, JSON-serialisable dict of ``result`` (no bytes/objects)."""
        return cls._sanitize(result.model_dump())

    @classmethod
    def _sanitize(cls, value):
        if isinstance(value, dict):
            return {key: cls._sanitize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._sanitize(item) for item in value]
        if isinstance(value, (bytes, bytearray)):
            return base64.b64encode(bytes(value)).decode("ascii")
        return value
