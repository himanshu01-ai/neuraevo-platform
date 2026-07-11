"""Unit tests for the Sprint 15.14 GitHub Capability.

Covers the first-class GitHub :class:`ExecutionCapability` end to end without any
network, git binary, or SDK: operations run in-process through the deterministic
:class:`LocalGitExecutor` in-memory Git simulation, and each test uses a fresh
temporary staging directory that is cleaned up.

Covers:

* the immutable DTOs (:class:`RepositoryInfo`, :class:`BranchInfo`,
  :class:`CommitInfo`, :class:`TagInfo`, :class:`IssueInfo`, :class:`RepositoryStatus`,
  :class:`GitHubArtifact`, and the five result DTOs) and the enums;
* repository init/clone/open/metadata; list/create/checkout/delete branches;
  status; stage/unstage; commit and history; create/list tags; create/list/update/
  close/search issues;
* validation and clear errors (repository/branch/tag names, commit messages, issue
  ids, invalid operations);
* deterministic repository/commit/tag/issue ids;
* artifact generation (commit/branch/tag/issue/report);
* provider independence (an injected fake executor), ExecutionCapability compliance
  / runtime-bridge JSON safety, and workspace lifecycle;
* the composition-root wiring; and
* regression that prior seams are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_github_capability
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
from app.services.runtime.github_artifact_manager import GitHubArtifactManager
from app.services.runtime.github_capability import GitHubCapability
from app.services.runtime.github_capability_models import (
    BranchInfo,
    CommitInfo,
    GitHubArtifact,
    GitHubArtifactType,
    GitHubOperation,
    GitHubOperationRequest,
    GitHubOperationStatus,
    GitHubValidationError,
    IssueInfo,
    IssueState,
    RepositoryInfo,
    RepositoryStatus,
    TagInfo,
    deterministic_commit_id,
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

_OP = GitHubOperation
_STATUS = GitHubOperationStatus


class _GitHubTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.staging = tempfile.mkdtemp(prefix="neuraevo_gh_stage_")
        self.executor = LocalGitExecutor()
        self.capability = GitHubCapability(
            executor=self.executor, staging_root=self.staging
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.staging, ignore_errors=True)

    def _run(self, operation, **kwargs):
        return self.capability.run(GitHubOperationRequest(operation=operation, **kwargs))

    def _init(self, name="repo"):
        return self._run(_OP.INIT.value, repository_name=name)

    def _repo_with_commit(self, name="repo"):
        rid = self._init(name).repository.repository_id
        self._run(_OP.STAGE.value, repository_id=rid, files={"a.txt": "one"})
        self._run(_OP.COMMIT.value, repository_id=rid, commit_message="first")
        return rid


# =====================================================================
# DTOs and validation helpers
# =====================================================================
class GitHubDtoTests(unittest.TestCase):
    def test_operation_and_status_enums(self):
        self.assertEqual(len(list(GitHubOperation)), 20)
        self.assertEqual(
            [s.value for s in GitHubOperationStatus], ["SUCCESS", "NOT_FOUND", "FAILED"]
        )
        self.assertEqual(
            [a.value for a in GitHubArtifactType],
            ["COMMIT", "BRANCH", "TAG", "ISSUE", "REPORT"],
        )
        self.assertEqual([s.value for s in IssueState], ["OPEN", "CLOSED"])

    def test_dtos_are_immutable(self):
        repo = RepositoryInfo(repository_id="r", name="n", path="p")
        with self.assertRaises(ValidationError):
            repo.name = "x"
        with self.assertRaises(ValidationError):
            BranchInfo(name="main").is_current = True
        with self.assertRaises(ValidationError):
            CommitInfo(commit_id="c", message="m", author="a").message = "x"
        with self.assertRaises(ValidationError):
            TagInfo(name="v1", tag_id="t").name = "v2"
        with self.assertRaises(ValidationError):
            IssueInfo(issue_id="i", number=1, title="t").title = "x"
        with self.assertRaises(ValidationError):
            RepositoryStatus(repository_id="r").is_clean = False
        with self.assertRaises(ValidationError):
            GitHubArtifact(artifact_id="a", artifact_type="COMMIT", artifact_name="n").artifact_type = "TAG"

    def test_result_dtos_immutable(self):
        results = [
            RepositoryResult(operation_status="SUCCESS"),
            BranchResult(operation_status="SUCCESS"),
            CreateCommitResult(operation_status="SUCCESS"),
            IssueResult(operation_status="SUCCESS"),
            OperationResult(operation="STATUS", operation_status="SUCCESS"),
        ]
        for result in results:
            with self.assertRaises(ValidationError):
                result.operation_status = "FAILED"

    def test_validators(self):
        self.assertEqual(validate_repository_name("my-repo"), "my-repo")
        self.assertEqual(validate_branch_name("feature/x"), "feature/x")
        self.assertEqual(validate_tag_name("v1.2.3"), "v1.2.3")
        self.assertEqual(validate_commit_message("  hi  "), "hi")
        for bad in ("../evil", "a/b", "", "  "):
            with self.assertRaises(GitHubValidationError):
                validate_repository_name(bad)
        for bad in ("bad branch", "..", "/lead", "trail/", "a..b"):
            with self.assertRaises(GitHubValidationError):
                validate_branch_name(bad)
        with self.assertRaises(GitHubValidationError):
            validate_commit_message("   ")

    def test_deterministic_ids(self):
        self.assertEqual(
            deterministic_repository_id("/path/repo"),
            deterministic_repository_id("/path/repo"),
        )
        self.assertTrue(deterministic_repository_id("x").startswith("repo-"))
        self.assertTrue(
            deterministic_commit_id("r", None, "m", "d", "a").startswith("commit-")
        )


# =====================================================================
# Repository lifecycle
# =====================================================================
class GitHubRepositoryTests(_GitHubTestBase):
    def test_init_creates_repository(self):
        result = self._run(_OP.INIT.value, repository_name="my-repo", description="demo")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.repository.name, "my-repo")
        self.assertEqual(result.repository.default_branch, "main")
        self.assertTrue(result.repository.repository_id.startswith("repo-"))
        self.assertTrue(os.path.isdir(os.path.join(self.staging, "my-repo")))

    def test_init_rejects_unsafe_name(self):
        result = self._run(_OP.INIT.value, repository_name="../evil")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("invalid repository name", result.operation_metadata["error"])

    def test_open_repository(self):
        rid = self._init("openable").repository.repository_id
        result = self._run(_OP.OPEN.value, repository_id=rid)
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.repository.name, "openable")

    def test_open_missing_is_not_found(self):
        self.assertEqual(
            self._run(_OP.OPEN.value, repository_id="repo-missing").operation_status,
            _STATUS.NOT_FOUND.value,
        )

    def test_repository_metadata_has_report_artifact(self):
        rid = self._repo_with_commit()
        result = self._run(_OP.REPOSITORY_METADATA.value, repository_id=rid)
        self.assertEqual(result.repository.commit_count, 1)
        self.assertEqual(result.artifact.artifact_type, GitHubArtifactType.REPORT.value)

    def test_clone_from_local_repository(self):
        origin = self._repo_with_commit("origin")
        origin_path = self._run(_OP.OPEN.value, repository_id=origin).repository.path
        result = self._run(_OP.CLONE.value, repository_name="clone", source_url=origin_path)
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.repository.commit_count, 1)
        self.assertEqual(result.repository.repository_metadata["cloned_from"], origin_path)

    def test_clone_without_source_seeds_initial_commit(self):
        result = self._run(_OP.CLONE.value, repository_name="fresh", source_url="https://x/y.git")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.repository.commit_count, 1)

    def test_operation_on_missing_repository_is_not_found(self):
        self.assertEqual(
            self._run(_OP.STATUS.value, repository_id="repo-missing").operation_status,
            _STATUS.NOT_FOUND.value,
        )


# =====================================================================
# Branches / checkout
# =====================================================================
class GitHubBranchTests(_GitHubTestBase):
    def test_create_branch(self):
        rid = self._repo_with_commit()
        result = self._run(_OP.CREATE_BRANCH.value, repository_id=rid, branch_name="feature/x")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertIsNotNone(result.branch.head_commit_id)
        self.assertEqual(result.artifact.artifact_type, GitHubArtifactType.BRANCH.value)

    def test_create_duplicate_branch_fails(self):
        rid = self._repo_with_commit()
        self._run(_OP.CREATE_BRANCH.value, repository_id=rid, branch_name="dup")
        result = self._run(_OP.CREATE_BRANCH.value, repository_id=rid, branch_name="dup")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)

    def test_create_branch_invalid_name(self):
        rid = self._repo_with_commit()
        result = self._run(_OP.CREATE_BRANCH.value, repository_id=rid, branch_name="bad name")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("invalid branch name", result.operation_metadata["error"])

    def test_checkout_branch(self):
        rid = self._repo_with_commit()
        self._run(_OP.CREATE_BRANCH.value, repository_id=rid, branch_name="dev")
        result = self._run(_OP.CHECKOUT.value, repository_id=rid, branch_name="dev")
        self.assertTrue(result.branch.is_current)

    def test_checkout_missing_branch_is_not_found(self):
        rid = self._repo_with_commit()
        self.assertEqual(
            self._run(_OP.CHECKOUT.value, repository_id=rid, branch_name="ghost").operation_status,
            _STATUS.NOT_FOUND.value,
        )

    def test_list_branches(self):
        rid = self._repo_with_commit()
        self._run(_OP.CREATE_BRANCH.value, repository_id=rid, branch_name="dev")
        result = self._run(_OP.LIST_BRANCHES.value, repository_id=rid)
        names = sorted(b.name for b in result.branches)
        self.assertEqual(names, ["dev", "main"])
        self.assertTrue(any(b.is_default and b.name == "main" for b in result.branches))

    def test_delete_branch(self):
        rid = self._repo_with_commit()
        self._run(_OP.CREATE_BRANCH.value, repository_id=rid, branch_name="temp")
        result = self._run(_OP.DELETE_BRANCH.value, repository_id=rid, branch_name="temp")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        remaining = [b.name for b in self._run(_OP.LIST_BRANCHES.value, repository_id=rid).branches]
        self.assertNotIn("temp", remaining)

    def test_delete_current_and_default_blocked(self):
        rid = self._repo_with_commit()
        self._run(_OP.CREATE_BRANCH.value, repository_id=rid, branch_name="dev")
        self._run(_OP.CHECKOUT.value, repository_id=rid, branch_name="dev")
        current = self._run(_OP.DELETE_BRANCH.value, repository_id=rid, branch_name="dev")
        default = self._run(_OP.DELETE_BRANCH.value, repository_id=rid, branch_name="main")
        self.assertEqual(current.operation_status, _STATUS.FAILED.value)
        self.assertEqual(default.operation_status, _STATUS.FAILED.value)


# =====================================================================
# Status / stage / unstage / commit / history
# =====================================================================
class GitHubCommitTests(_GitHubTestBase):
    def test_stage_then_status_shows_staged(self):
        rid = self._init().repository.repository_id
        result = self._run(_OP.STAGE.value, repository_id=rid, files={"a.py": "x", "b.py": "y"})
        self.assertEqual(result.repository_status.staged_files, ["a.py", "b.py"])
        self.assertFalse(result.repository_status.is_clean)

    def test_commit_advances_branch(self):
        rid = self._init().repository.repository_id
        self._run(_OP.STAGE.value, repository_id=rid, files={"a.py": "x"})
        result = self._run(_OP.COMMIT.value, repository_id=rid, commit_message="init")
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.commit.changed_files, ["a.py"])
        self.assertEqual(result.artifact.artifact_type, GitHubArtifactType.COMMIT.value)
        status = self._run(_OP.STATUS.value, repository_id=rid).repository_status
        self.assertTrue(status.is_clean)

    def test_commit_empty_message_fails(self):
        rid = self._init().repository.repository_id
        self._run(_OP.STAGE.value, repository_id=rid, files={"a.py": "x"})
        result = self._run(_OP.COMMIT.value, repository_id=rid, commit_message="  ")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)

    def test_commit_nothing_staged_fails(self):
        rid = self._init().repository.repository_id
        result = self._run(_OP.COMMIT.value, repository_id=rid, commit_message="empty")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("nothing to commit", result.operation_metadata["error"])

    def test_unstage_moves_file_out_of_index(self):
        rid = self._init().repository.repository_id
        self._run(_OP.STAGE.value, repository_id=rid, files={"a.py": "x"})
        result = self._run(_OP.UNSTAGE.value, repository_id=rid, paths=["a.py"])
        self.assertEqual(result.repository_status.staged_files, [])
        self.assertEqual(result.repository_status.untracked_files, ["a.py"])

    def test_history_is_newest_first(self):
        rid = self._init().repository.repository_id
        self._run(_OP.STAGE.value, repository_id=rid, files={"a": "1"})
        self._run(_OP.COMMIT.value, repository_id=rid, commit_message="c1")
        self._run(_OP.STAGE.value, repository_id=rid, files={"a": "2"})
        self._run(_OP.COMMIT.value, repository_id=rid, commit_message="c2")
        result = self._run(_OP.HISTORY.value, repository_id=rid)
        self.assertEqual([c.message for c in result.commits], ["c2", "c1"])
        self.assertEqual(result.commits[0].parent_id, result.commits[1].commit_id)

    def test_history_respects_limit(self):
        rid = self._init().repository.repository_id
        for n in range(3):
            self._run(_OP.STAGE.value, repository_id=rid, files={"a": str(n)})
            self._run(_OP.COMMIT.value, repository_id=rid, commit_message=f"c{n}")
        self.assertEqual(len(self._run(_OP.HISTORY.value, repository_id=rid, limit=2).commits), 2)


# =====================================================================
# Tags
# =====================================================================
class GitHubTagTests(_GitHubTestBase):
    def test_create_and_list_tag(self):
        rid = self._repo_with_commit()
        created = self._run(_OP.CREATE_TAG.value, repository_id=rid, tag_name="v1.0.0", tag_message="release")
        self.assertEqual(created.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(created.artifact.artifact_type, GitHubArtifactType.TAG.value)
        listed = self._run(_OP.LIST_TAGS.value, repository_id=rid)
        self.assertEqual([t.name for t in listed.tags], ["v1.0.0"])

    def test_create_tag_invalid_name(self):
        rid = self._repo_with_commit()
        result = self._run(_OP.CREATE_TAG.value, repository_id=rid, tag_name="bad tag")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)

    def test_duplicate_tag_fails(self):
        rid = self._repo_with_commit()
        self._run(_OP.CREATE_TAG.value, repository_id=rid, tag_name="v1")
        result = self._run(_OP.CREATE_TAG.value, repository_id=rid, tag_name="v1")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)

    def test_tag_without_commit_fails(self):
        rid = self._init().repository.repository_id  # no commits yet
        result = self._run(_OP.CREATE_TAG.value, repository_id=rid, tag_name="v1")
        self.assertEqual(result.operation_status, _STATUS.FAILED.value)
        self.assertIn("no commit to tag", result.operation_metadata["error"])


# =====================================================================
# Issues
# =====================================================================
class GitHubIssueTests(_GitHubTestBase):
    def test_create_issue(self):
        rid = self._init().repository.repository_id
        result = self._run(
            _OP.CREATE_ISSUE.value, repository_id=rid, issue_title="Bug",
            issue_body="broken", labels=["bug"], assignees=["dev"],
        )
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertEqual(result.issue.number, 1)
        self.assertEqual(result.issue.state, IssueState.OPEN.value)
        self.assertEqual(result.issue.labels, ["bug"])
        self.assertTrue(result.issue.issue_id.startswith("issue-"))
        self.assertEqual(result.artifact.artifact_type, GitHubArtifactType.ISSUE.value)

    def test_issue_numbers_increment(self):
        rid = self._init().repository.repository_id
        first = self._run(_OP.CREATE_ISSUE.value, repository_id=rid, issue_title="A")
        second = self._run(_OP.CREATE_ISSUE.value, repository_id=rid, issue_title="B")
        self.assertEqual(first.issue.number, 1)
        self.assertEqual(second.issue.number, 2)

    def test_update_issue(self):
        rid = self._init().repository.repository_id
        created = self._run(_OP.CREATE_ISSUE.value, repository_id=rid, issue_title="Old")
        result = self._run(
            _OP.UPDATE_ISSUE.value, repository_id=rid, issue_number=created.issue.number,
            issue_title="New", labels=["urgent"],
        )
        self.assertEqual(result.issue.title, "New")
        self.assertEqual(result.issue.labels, ["urgent"])

    def test_close_issue(self):
        rid = self._init().repository.repository_id
        created = self._run(_OP.CREATE_ISSUE.value, repository_id=rid, issue_title="Bug")
        result = self._run(_OP.CLOSE_ISSUE.value, repository_id=rid, issue_number=created.issue.number)
        self.assertEqual(result.issue.state, IssueState.CLOSED.value)

    def test_update_missing_issue_is_not_found(self):
        rid = self._init().repository.repository_id
        self.assertEqual(
            self._run(_OP.UPDATE_ISSUE.value, repository_id=rid, issue_number=99, issue_title="x").operation_status,
            _STATUS.NOT_FOUND.value,
        )

    def test_list_issues_by_state(self):
        rid = self._init().repository.repository_id
        a = self._run(_OP.CREATE_ISSUE.value, repository_id=rid, issue_title="A")
        self._run(_OP.CREATE_ISSUE.value, repository_id=rid, issue_title="B")
        self._run(_OP.CLOSE_ISSUE.value, repository_id=rid, issue_number=a.issue.number)
        self.assertEqual(self._run(_OP.LIST_ISSUES.value, repository_id=rid, state_filter="all").match_count, 2)
        self.assertEqual(self._run(_OP.LIST_ISSUES.value, repository_id=rid, state_filter="open").match_count, 1)
        self.assertEqual(self._run(_OP.LIST_ISSUES.value, repository_id=rid, state_filter="closed").match_count, 1)

    def test_search_issues_with_report(self):
        rid = self._init().repository.repository_id
        self._run(_OP.CREATE_ISSUE.value, repository_id=rid, issue_title="Search feature", issue_body="add it")
        self._run(_OP.CREATE_ISSUE.value, repository_id=rid, issue_title="Other")
        result = self._run(_OP.SEARCH_ISSUES.value, repository_id=rid, query="search")
        self.assertEqual(result.match_count, 1)
        self.assertEqual(result.artifact.artifact_type, GitHubArtifactType.REPORT.value)


# =====================================================================
# Artifacts
# =====================================================================
class GitHubArtifactTests(_GitHubTestBase):
    def test_artifact_ids_are_deterministic(self):
        manager = GitHubArtifactManager()
        self.assertEqual(manager.commit("c1").artifact_id, manager.commit("c1").artifact_id)
        self.assertTrue(manager.commit("c1").artifact_id.startswith("gh-commit-"))

    def test_artifact_manager_supports_all_kinds_and_is_stateless(self):
        manager = GitHubArtifactManager()
        self.assertEqual(manager.commit("c").artifact_type, "COMMIT")
        self.assertEqual(manager.branch("b").artifact_type, "BRANCH")
        self.assertEqual(manager.tag("t").artifact_type, "TAG")
        self.assertEqual(manager.issue("i").artifact_type, "ISSUE")
        self.assertEqual(manager.report("r").artifact_type, "REPORT")
        self.assertEqual(vars(GitHubArtifactManager()), {})

    def test_failed_operation_has_no_artifact(self):
        result = self._run(_OP.INIT.value, repository_name="../bad")
        self.assertIsNone(result.artifact)


# =====================================================================
# Provider independence / ExecutionCapability compliance / bridge
# =====================================================================
class _FakeExecutor(GitHubExecutor):
    def __init__(self) -> None:
        self.calls = []

    def perform(self, request, context):
        self.calls.append((request, context))
        return OperationResult(
            operation=request.operation,
            repository_id="fake",
            success=True,
            operation_status=GitHubOperationStatus.SUCCESS.value,
            operation_metadata={"fake": True},
        )


class GitHubProviderTests(_GitHubTestBase):
    def test_provider_independence_with_injected_executor(self):
        fake = _FakeExecutor()
        capability = GitHubCapability(executor=fake, staging_root=self.staging)
        result = capability.run(GitHubOperationRequest(operation=_OP.STATUS.value, repository_id="r"))
        self.assertTrue(result.operation_metadata["fake"])
        self.assertEqual(len(fake.calls), 1)

    def test_capability_is_execution_capability(self):
        self.assertIsInstance(self.capability, ExecutionCapability)

    def test_local_executor_holds_only_instance_state(self):
        executor = LocalGitExecutor()
        result = executor.perform(
            GitHubOperationRequest(operation=_OP.OPEN.value, repository_id="none"),
            GitHubExecutionContext(),
        )
        self.assertEqual(result.operation_status, _STATUS.NOT_FOUND.value)

    def test_results_are_plain_dtos(self):
        result = self._init()
        self.assertIsInstance(result, RepositoryResult)
        self.assertIsInstance(result, BaseModel)

    def test_execute_bridges_init(self):
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="github",
            capability_inputs={"operation": "INIT", "repository_name": "bridge"},
        )
        result = self.capability.execute(request)
        self.assertEqual(result.execution_status, CapabilityExecutionStatus.COMPLETED.value)
        self.assertEqual(result.capability_name, "github")
        self.assertIsNotNone(result.capability_outputs["repository"]["repository_id"])
        self.assertEqual(result.execution_metadata["operation"], "INIT")

    def test_execute_maps_failure(self):
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="github",
            capability_inputs={"operation": "OPEN", "repository_id": "repo-missing"},
        )
        result = self.capability.execute(request)
        self.assertEqual(result.execution_status, CapabilityExecutionStatus.FAILED.value)

    def test_execute_outputs_are_json_safe(self):
        rid = self._repo_with_commit()
        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="github",
            capability_inputs={"operation": "HISTORY", "repository_id": rid},
        )
        result = self.capability.execute(request)
        self._assert_json_safe(result.capability_outputs)

    def _assert_json_safe(self, value):
        if isinstance(value, dict):
            for item in value.values():
                self._assert_json_safe(item)
        elif isinstance(value, list):
            for item in value:
                self._assert_json_safe(item)
        else:
            self.assertNotIsInstance(value, (bytes, bytearray, BaseModel))


# =====================================================================
# Workspace lifecycle
# =====================================================================
class GitHubWorkspaceTests(_GitHubTestBase):
    def test_current_workspace_staging(self):
        workspace = self.capability.current_workspace()
        self.assertTrue(workspace.exists())
        self.assertEqual(
            os.path.realpath(workspace.staging_path), os.path.realpath(self.staging)
        )

    def test_temporary_workspace_is_isolated(self):
        temp = self.capability.create_temporary_workspace()
        self.assertTrue(temp.is_temporary)
        self.assertTrue(temp.exists())
        self.assertNotEqual(
            os.path.realpath(temp.staging_path), os.path.realpath(self.staging)
        )

    def test_stage_repository_rejects_traversal(self):
        with self.assertRaises(GitHubWorkspaceError):
            self.capability.current_workspace().stage_repository("../escape")

    def test_cleanup_temporary_removes_it(self):
        temp = self.capability.create_temporary_workspace()
        path = temp.staging_path
        result = self.capability.cleanup_workspace(temp)
        self.assertEqual(result.operation_status, _STATUS.SUCCESS.value)
        self.assertFalse(os.path.exists(path))

    def test_cleanup_current_empties_but_keeps(self):
        self._init("keeper")
        workspace = self.capability.current_workspace()
        self.capability.cleanup_workspace(workspace)
        self.assertTrue(workspace.exists())
        self.assertEqual(list(os.scandir(self.staging)), [])

    def test_workspace_manager_is_stateless(self):
        self.assertEqual(vars(GitHubWorkspaceManager()), {})


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class GitHubDependencyInjectionTests(unittest.TestCase):
    def test_get_github_capability_returns_capability(self):
        from app.core.dependencies import get_github_capability

        capability = get_github_capability()
        self.assertIsInstance(capability, GitHubCapability)
        self.assertIsInstance(capability, ExecutionCapability)

    def test_github_capability_dep_is_wired(self):
        from app.core.dependencies import GitHubCapabilityDep

        self.assertIn(GitHubCapability, getattr(GitHubCapabilityDep, "__args__", ()))

    def test_wired_capability_executes(self):
        from app.core.dependencies import get_github_capability

        request = CapabilityExecutionRequest(
            runtime_id="rt", execution_id="ex", execution_unit_id="u",
            capability_name="github",
            capability_inputs={"operation": "INIT", "repository_name": "wired"},
        )
        result = get_github_capability().execute(request)
        self.assertEqual(result.execution_status, "COMPLETED")


# =====================================================================
# Regression — prior seams unchanged
# =====================================================================
class GitHubRegressionTests(unittest.TestCase):
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

    def test_sprint_15_11_filesystem_capability_unchanged(self):
        from app.core.dependencies import get_filesystem_capability

        self.assertIsInstance(get_filesystem_capability(), ExecutionCapability)

    def test_sprint_15_12_email_capability_unchanged(self):
        from app.core.dependencies import get_email_capability

        self.assertIsInstance(get_email_capability(), ExecutionCapability)

    def test_sprint_15_13_calendar_capability_unchanged(self):
        from app.core.dependencies import get_calendar_capability

        self.assertIsInstance(get_calendar_capability(), ExecutionCapability)


if __name__ == "__main__":
    unittest.main()
