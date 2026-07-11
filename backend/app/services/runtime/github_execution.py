"""GitHub execution layer (Sprint 15.14 — the replaceable provider seam).

Defines the :class:`GitHubExecutor` seam that performs the actual repository
operations and its default :class:`LocalGitExecutor` — a deterministic, offline
in-memory Git simulation (the analog of the Calendar layer's
``LocalCalendarExecutor``). The capability coordinates, validates, and builds DTOs;
this layer performs the repository/branch/commit/tag/issue logic. A single
``perform`` method keeps the seam tiny so a future provider (GitHub REST/GraphQL,
Git CLI, GitLab, Bitbucket, Azure DevOps) can implement it without any change to the
Runtime or the capability.

The default executor keeps an in-memory model of repositories (branches, commits,
tags, issues, index/working trees) in plain private structures and only ever emits
immutable DTOs; it builds no ``git``/``pygit2``/``GitPython``/SDK object into a
result and holds no credential. Instance state only (each capability gets its own
set of repositories); no static/singleton state, no network, thread, or subprocess.
Strictly additive to Sprints 15.1–15.13.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, NamedTuple, Optional, Union

from app.services.runtime.github_capability_models import (
    BranchInfo,
    CommitInfo,
    GitHubOperation,
    GitHubOperationRequest,
    GitHubOperationStatus,
    IssueInfo,
    IssueState,
    RepositoryInfo,
    RepositoryStatus,
    TagInfo,
    deterministic_commit_id,
    deterministic_issue_id,
    deterministic_tag_id,
    tree_digest,
)
from app.services.runtime.github_results import (
    BranchResult,
    CreateCommitResult,
    IssueResult,
    OperationResult,
    RepositoryResult,
)

_SUCCESS = GitHubOperationStatus.SUCCESS.value
_FAILED = GitHubOperationStatus.FAILED.value
_NOT_FOUND = GitHubOperationStatus.NOT_FOUND.value

_DEFAULT_AUTHOR = "NeuraEvo <bot@neuraevo.local>"
_DEFAULT_BRANCH = "main"

GitHubOperationOutcome = Union[
    RepositoryResult,
    BranchResult,
    CreateCommitResult,
    IssueResult,
    OperationResult,
]


class GitHubExecutionContext(NamedTuple):
    """Plain inputs the capability hands to the executor for repository creation.

    ``repository_id`` is the deterministic id (from the staged path) and
    ``repository_path`` is the staged directory, both set for init/clone. Carries
    only plain strings — never a git object or credential.
    """

    repository_id: Optional[str] = None
    repository_path: Optional[str] = None


class GitHubExecutor(ABC):
    """Replaceable seam that performs one repository operation and reports a DTO.

    Concrete executors own all Git/provider mechanics behind this single interface so
    the capability stays testable and provider-independent. An executor must never
    let a ``git``/``pygit2``/``GitPython``/SDK object, an API response, or a
    credential escape — it returns only a plain result DTO.
    """

    @abstractmethod
    def perform(
        self,
        request: GitHubOperationRequest,
        context: GitHubExecutionContext,
    ) -> GitHubOperationOutcome:
        """Perform ``request`` with the ``context`` and return its result."""


# =====================================================================
# Internal, mutable, never-exposed storage structures
# =====================================================================
class _Commit:
    __slots__ = (
        "commit_id", "message", "author", "parent_id", "branch",
        "changed_files", "tree", "sequence",
    )

    def __init__(self, commit_id, message, author, parent_id, branch, changed_files, tree, sequence):
        self.commit_id = commit_id
        self.message = message
        self.author = author
        self.parent_id = parent_id
        self.branch = branch
        self.changed_files = changed_files
        self.tree = tree
        self.sequence = sequence


class _Tag:
    __slots__ = ("name", "tag_id", "commit_id", "message")

    def __init__(self, name, tag_id, commit_id, message):
        self.name = name
        self.tag_id = tag_id
        self.commit_id = commit_id
        self.message = message


class _Issue:
    __slots__ = (
        "issue_id", "number", "title", "body", "state",
        "labels", "assignees", "created_at", "updated_at",
    )

    def __init__(self, issue_id, number, title, body, state, labels, assignees, created_at, updated_at):
        self.issue_id = issue_id
        self.number = number
        self.title = title
        self.body = body
        self.state = state
        self.labels = labels
        self.assignees = assignees
        self.created_at = created_at
        self.updated_at = updated_at


class _Repo:
    def __init__(self, repository_id, name, path, description, metadata):
        self.repository_id = repository_id
        self.name = name
        self.path = path
        self.description = description
        self.default_branch = _DEFAULT_BRANCH
        self.current_branch = _DEFAULT_BRANCH
        self.branches: Dict[str, Optional[str]] = {_DEFAULT_BRANCH: None}
        self.commits: Dict[str, _Commit] = {}
        self.tags: Dict[str, _Tag] = {}
        self.issues: Dict[int, _Issue] = {}
        self.index: Dict[str, str] = {}
        self.working: Dict[str, str] = {}
        self.metadata = dict(metadata or {})
        self._sequence = 0
        self._issue_counter = 0

    def next_sequence(self) -> float:
        value = float(self._sequence)
        self._sequence += 1
        return value

    def next_issue_number(self) -> int:
        self._issue_counter += 1
        return self._issue_counter

    def committed_tree(self) -> Dict[str, str]:
        head = self.branches.get(self.current_branch)
        return dict(self.commits[head].tree) if head else {}


class LocalGitExecutor(GitHubExecutor):
    """Default executor: a deterministic, offline in-memory Git simulation.

    Dispatches on the request's operation to a focused handler over an in-memory set
    of repositories keyed by id. It models init/clone/open, branches, staging,
    commits and history, tags, and issues — all deterministic and offline. A missing
    repository/branch/issue becomes ``NOT_FOUND`` — never a raised git object. Holds
    per-instance state only (no static/singleton state) and contacts no network.
    """

    def __init__(self) -> None:
        self._repos: Dict[str, _Repo] = {}

    # --- dispatch -------------------------------------------------------
    def perform(self, request, context) -> GitHubOperationOutcome:
        operation = request.operation
        if operation == GitHubOperation.INIT.value:
            return self._init(request, context)
        if operation == GitHubOperation.CLONE.value:
            return self._clone(request, context)
        if operation == GitHubOperation.OPEN.value:
            return self._open(request)
        if operation == GitHubOperation.REPOSITORY_METADATA.value:
            return self._metadata(request)
        repo = self._repos.get(request.repository_id)
        if repo is None:
            return self._repo_not_found(operation)
        if operation == GitHubOperation.LIST_BRANCHES.value:
            return self._list_branches(repo)
        if operation == GitHubOperation.CREATE_BRANCH.value:
            return self._create_branch(repo, request)
        if operation == GitHubOperation.CHECKOUT.value:
            return self._checkout(repo, request)
        if operation == GitHubOperation.DELETE_BRANCH.value:
            return self._delete_branch(repo, request)
        if operation == GitHubOperation.STATUS.value:
            return self._status_result(repo, GitHubOperation.STATUS.value)
        if operation == GitHubOperation.STAGE.value:
            return self._stage(repo, request)
        if operation == GitHubOperation.UNSTAGE.value:
            return self._unstage(repo, request)
        if operation == GitHubOperation.COMMIT.value:
            return self._commit(repo, request)
        if operation == GitHubOperation.HISTORY.value:
            return self._history(repo, request)
        if operation == GitHubOperation.CREATE_TAG.value:
            return self._create_tag(repo, request)
        if operation == GitHubOperation.LIST_TAGS.value:
            return self._list_tags(repo)
        if operation == GitHubOperation.CREATE_ISSUE.value:
            return self._create_issue(repo, request)
        if operation == GitHubOperation.LIST_ISSUES.value:
            return self._list_issues(repo, request)
        if operation == GitHubOperation.UPDATE_ISSUE.value:
            return self._update_issue(repo, request)
        if operation == GitHubOperation.CLOSE_ISSUE.value:
            return self._close_issue(repo, request)
        if operation == GitHubOperation.SEARCH_ISSUES.value:
            return self._search_issues(repo, request)
        return OperationResult(
            operation=operation or "UNKNOWN",
            operation_status=_FAILED,
            operation_metadata={"error": f"unsupported operation: {operation}"},
        )

    # --- repository lifecycle -------------------------------------------
    def _init(self, request, context) -> RepositoryResult:
        repo = _Repo(
            repository_id=context.repository_id,
            name=request.repository_name or "repository",
            path=context.repository_path or "",
            description=request.description,
            metadata={},
        )
        self._repos[repo.repository_id] = repo
        return RepositoryResult(
            repository=self._repo_info(repo), operation_status=_SUCCESS
        )

    def _clone(self, request, context) -> RepositoryResult:
        repo = _Repo(
            repository_id=context.repository_id,
            name=request.repository_name or "repository",
            path=context.repository_path or "",
            description=request.description,
            metadata={"cloned_from": request.source_url or ""},
        )
        source = self._find_source(request.source_url)
        if source is not None:
            self._copy_state(source, repo)
        else:
            self._seed_initial_commit(repo)
        self._repos[repo.repository_id] = repo
        return RepositoryResult(
            repository=self._repo_info(repo),
            operation_status=_SUCCESS,
            operation_metadata={"cloned_from": request.source_url or ""},
        )

    def _open(self, request) -> RepositoryResult:
        repo = self._repos.get(request.repository_id)
        if repo is None and request.repository_path:
            repo = next(
                (r for r in self._repos.values() if r.path == request.repository_path),
                None,
            )
        if repo is None:
            return RepositoryResult(
                operation_status=_NOT_FOUND,
                operation_metadata={"error": "repository not found"},
            )
        return RepositoryResult(
            repository=self._repo_info(repo), operation_status=_SUCCESS
        )

    def _metadata(self, request) -> RepositoryResult:
        repo = self._repos.get(request.repository_id)
        if repo is None:
            return RepositoryResult(
                operation_status=_NOT_FOUND,
                operation_metadata={"error": "repository not found"},
            )
        return RepositoryResult(
            repository=self._repo_info(repo), operation_status=_SUCCESS
        )

    # --- branches -------------------------------------------------------
    def _list_branches(self, repo) -> BranchResult:
        return BranchResult(
            branches=[self._branch_info(repo, name) for name in sorted(repo.branches)],
            operation_status=_SUCCESS,
        )

    def _create_branch(self, repo, request) -> BranchResult:
        name = request.branch_name
        if name in repo.branches:
            return BranchResult(
                operation_status=_FAILED,
                operation_metadata={"error": f"branch already exists: {name}"},
            )
        repo.branches[name] = repo.branches[repo.current_branch]
        return BranchResult(
            branch=self._branch_info(repo, name), operation_status=_SUCCESS
        )

    def _checkout(self, repo, request) -> BranchResult:
        name = request.branch_name
        if name not in repo.branches:
            return BranchResult(
                operation_status=_NOT_FOUND,
                operation_metadata={"error": f"branch not found: {name}"},
            )
        repo.current_branch = name
        repo.index = {}
        repo.working = dict(repo.committed_tree())
        return BranchResult(
            branch=self._branch_info(repo, name), operation_status=_SUCCESS
        )

    def _delete_branch(self, repo, request) -> BranchResult:
        name = request.branch_name
        if name not in repo.branches:
            return BranchResult(
                operation_status=_NOT_FOUND,
                operation_metadata={"error": f"branch not found: {name}"},
            )
        if name == repo.current_branch:
            return BranchResult(
                operation_status=_FAILED,
                operation_metadata={"error": "cannot delete the current branch"},
            )
        if name == repo.default_branch:
            return BranchResult(
                operation_status=_FAILED,
                operation_metadata={"error": "cannot delete the default branch"},
            )
        del repo.branches[name]
        return BranchResult(
            operation_status=_SUCCESS, operation_metadata={"deleted": name}
        )

    # --- staging / commit / history -------------------------------------
    def _stage(self, repo, request) -> OperationResult:
        if request.files:
            for name, content in request.files.items():
                repo.working[name] = content
                repo.index[name] = content
        elif request.paths:
            for path in request.paths:
                if path in repo.working:
                    repo.index[path] = repo.working[path]
        else:  # stage everything in the working tree
            repo.index.update(repo.working)
        return self._status_result(repo, GitHubOperation.STAGE.value)

    def _unstage(self, repo, request) -> OperationResult:
        if request.paths:
            for path in request.paths:
                repo.index.pop(path, None)
        else:
            repo.index = {}
        return self._status_result(repo, GitHubOperation.UNSTAGE.value)

    def _commit(self, repo, request) -> CreateCommitResult:
        message = request.commit_message or ""
        author = request.author or _DEFAULT_AUTHOR
        committed = repo.committed_tree()
        new_tree = dict(committed)
        changed: List[str] = []
        for name, content in repo.index.items():
            if committed.get(name) != content:
                changed.append(name)
            new_tree[name] = content
        if not changed:
            return CreateCommitResult(
                operation_status=_FAILED,
                operation_metadata={"error": "nothing to commit"},
            )
        parent = repo.branches[repo.current_branch]
        commit_id = deterministic_commit_id(
            repo.repository_id, parent, message, tree_digest(new_tree), author
        )
        commit = _Commit(
            commit_id, message, author, parent, repo.current_branch,
            sorted(changed), new_tree, repo.next_sequence(),
        )
        repo.commits[commit_id] = commit
        repo.branches[repo.current_branch] = commit_id
        repo.index = {}
        return CreateCommitResult(
            commit_id=commit_id,
            commit=self._commit_info(commit),
            operation_status=_SUCCESS,
        )

    def _history(self, repo, request) -> OperationResult:
        limit = request.limit
        commits: List[CommitInfo] = []
        cursor = repo.branches.get(repo.current_branch)
        while cursor is not None:
            commit = repo.commits[cursor]
            commits.append(self._commit_info(commit))
            if limit is not None and len(commits) >= limit:
                break
            cursor = commit.parent_id
        return OperationResult(
            operation=GitHubOperation.HISTORY.value,
            repository_id=repo.repository_id,
            success=True,
            commits=commits,
            operation_status=_SUCCESS,
        )

    # --- tags -----------------------------------------------------------
    def _create_tag(self, repo, request) -> OperationResult:
        name = request.tag_name
        if name in repo.tags:
            return OperationResult(
                operation=GitHubOperation.CREATE_TAG.value,
                repository_id=repo.repository_id,
                operation_status=_FAILED,
                operation_metadata={"error": f"tag already exists: {name}"},
            )
        target = request.commit_id or repo.branches.get(repo.current_branch)
        if target is None:
            return OperationResult(
                operation=GitHubOperation.CREATE_TAG.value,
                repository_id=repo.repository_id,
                operation_status=_FAILED,
                operation_metadata={"error": "no commit to tag"},
            )
        if target not in repo.commits:
            return OperationResult(
                operation=GitHubOperation.CREATE_TAG.value,
                repository_id=repo.repository_id,
                operation_status=_NOT_FOUND,
                operation_metadata={"error": f"commit not found: {target}"},
            )
        tag = _Tag(
            name, deterministic_tag_id(repo.repository_id, name, target),
            target, request.tag_message,
        )
        repo.tags[name] = tag
        return OperationResult(
            operation=GitHubOperation.CREATE_TAG.value,
            repository_id=repo.repository_id,
            success=True,
            tag=self._tag_info(tag),
            operation_status=_SUCCESS,
        )

    def _list_tags(self, repo) -> OperationResult:
        return OperationResult(
            operation=GitHubOperation.LIST_TAGS.value,
            repository_id=repo.repository_id,
            success=True,
            tags=[self._tag_info(repo.tags[name]) for name in sorted(repo.tags)],
            operation_status=_SUCCESS,
        )

    # --- issues ---------------------------------------------------------
    def _create_issue(self, repo, request) -> IssueResult:
        number = repo.next_issue_number()
        sequence = repo.next_sequence()
        issue = _Issue(
            deterministic_issue_id(repo.repository_id, number), number,
            request.issue_title or "", request.issue_body, IssueState.OPEN.value,
            list(request.labels), list(request.assignees), sequence, sequence,
        )
        repo.issues[number] = issue
        return IssueResult(issue=self._issue_info(issue), operation_status=_SUCCESS)

    def _list_issues(self, repo, request) -> IssueResult:
        state_filter = (request.state_filter or "all").lower()
        issues = [
            self._issue_info(repo.issues[number])
            for number in sorted(repo.issues)
            if state_filter == "all"
            or repo.issues[number].state.lower() == state_filter
        ]
        return IssueResult(
            issues=issues, match_count=len(issues), operation_status=_SUCCESS
        )

    def _update_issue(self, repo, request) -> IssueResult:
        issue = self._find_issue(repo, request.issue_number)
        if issue is None:
            return self._issue_not_found(request.issue_number)
        updates = request.update_fields
        if "title" in updates:
            issue.title = updates["title"]
        if "body" in updates:
            issue.body = updates["body"]
        if "state" in updates:
            issue.state = updates["state"]
        if "labels" in updates:
            issue.labels = list(updates["labels"])
        if "assignees" in updates:
            issue.assignees = list(updates["assignees"])
        issue.updated_at = repo.next_sequence()
        return IssueResult(issue=self._issue_info(issue), operation_status=_SUCCESS)

    def _close_issue(self, repo, request) -> IssueResult:
        issue = self._find_issue(repo, request.issue_number)
        if issue is None:
            return self._issue_not_found(request.issue_number)
        issue.state = IssueState.CLOSED.value
        issue.updated_at = repo.next_sequence()
        return IssueResult(issue=self._issue_info(issue), operation_status=_SUCCESS)

    def _search_issues(self, repo, request) -> IssueResult:
        query = (request.query or "").strip().lower()
        matches = [
            self._issue_info(repo.issues[number])
            for number in sorted(repo.issues)
            if not query or self._issue_matches(repo.issues[number], query)
        ]
        return IssueResult(
            issues=matches, match_count=len(matches), operation_status=_SUCCESS
        )

    # --- clone helpers --------------------------------------------------
    def _find_source(self, source_url) -> Optional[_Repo]:
        if not source_url:
            return None
        return next(
            (
                repo
                for repo in self._repos.values()
                if repo.path == source_url or repo.repository_id == source_url
            ),
            None,
        )

    @staticmethod
    def _copy_state(source: _Repo, target: _Repo) -> None:
        target.default_branch = source.default_branch
        target.current_branch = source.current_branch
        target.branches = dict(source.branches)
        target.commits = {
            cid: _Commit(
                c.commit_id, c.message, c.author, c.parent_id, c.branch,
                list(c.changed_files), dict(c.tree), c.sequence,
            )
            for cid, c in source.commits.items()
        }
        target.tags = {
            name: _Tag(t.name, t.tag_id, t.commit_id, t.message)
            for name, t in source.tags.items()
        }
        target.working = dict(source.committed_tree())
        target._sequence = source._sequence

    def _seed_initial_commit(self, repo: _Repo) -> None:
        tree = {"README.md": f"# {repo.name}\n"}
        commit_id = deterministic_commit_id(
            repo.repository_id, None, "Initial commit", tree_digest(tree), _DEFAULT_AUTHOR
        )
        repo.commits[commit_id] = _Commit(
            commit_id, "Initial commit", _DEFAULT_AUTHOR, None,
            repo.default_branch, ["README.md"], tree, repo.next_sequence(),
        )
        repo.branches[repo.default_branch] = commit_id
        repo.working = dict(tree)

    # --- status ---------------------------------------------------------
    def _status_result(self, repo, operation) -> OperationResult:
        return OperationResult(
            operation=operation,
            repository_id=repo.repository_id,
            success=True,
            repository_status=self._status(repo),
            operation_status=_SUCCESS,
        )

    def _status(self, repo) -> RepositoryStatus:
        committed = repo.committed_tree()
        staged = sorted(
            name for name, content in repo.index.items()
            if committed.get(name) != content
        )
        unstaged = sorted(
            name for name, content in repo.working.items()
            if content != repo.index.get(name, committed.get(name))
            and name in committed
        )
        untracked = sorted(
            name for name in repo.working
            if name not in committed and name not in repo.index
        )
        return RepositoryStatus(
            repository_id=repo.repository_id,
            current_branch=repo.current_branch,
            staged_files=staged,
            unstaged_files=unstaged,
            untracked_files=untracked,
            is_clean=not (staged or unstaged or untracked),
        )

    # --- DTO builders ---------------------------------------------------
    def _repo_info(self, repo) -> RepositoryInfo:
        return RepositoryInfo(
            repository_id=repo.repository_id,
            name=repo.name,
            path=repo.path,
            default_branch=repo.default_branch,
            current_branch=repo.current_branch,
            description=repo.description,
            branch_count=len(repo.branches),
            commit_count=len(repo.commits),
            tag_count=len(repo.tags),
            issue_count=len(repo.issues),
            repository_metadata=dict(repo.metadata),
        )

    def _branch_info(self, repo, name) -> BranchInfo:
        return BranchInfo(
            name=name,
            head_commit_id=repo.branches.get(name),
            is_current=(name == repo.current_branch),
            is_default=(name == repo.default_branch),
        )

    @staticmethod
    def _commit_info(commit) -> CommitInfo:
        return CommitInfo(
            commit_id=commit.commit_id,
            message=commit.message,
            author=commit.author,
            parent_id=commit.parent_id,
            branch=commit.branch,
            changed_files=list(commit.changed_files),
            timestamp=float(commit.sequence),
        )

    @staticmethod
    def _tag_info(tag) -> TagInfo:
        return TagInfo(
            name=tag.name, tag_id=tag.tag_id,
            commit_id=tag.commit_id, message=tag.message,
        )

    @staticmethod
    def _issue_info(issue) -> IssueInfo:
        return IssueInfo(
            issue_id=issue.issue_id,
            number=issue.number,
            title=issue.title,
            body=issue.body,
            state=issue.state,
            labels=list(issue.labels),
            assignees=list(issue.assignees),
            created_at=issue.created_at,
            updated_at=issue.updated_at,
        )

    # --- lookups / errors -----------------------------------------------
    @staticmethod
    def _find_issue(repo, number) -> Optional[_Issue]:
        if number is None:
            return None
        return repo.issues.get(number)

    @staticmethod
    def _issue_matches(issue, query) -> bool:
        haystacks = [issue.title, issue.body or "", *issue.labels]
        return any(query in text.lower() for text in haystacks)

    @staticmethod
    def _repo_not_found(operation) -> OperationResult:
        return OperationResult(
            operation=operation or "UNKNOWN",
            operation_status=_NOT_FOUND,
            operation_metadata={"error": "repository not found"},
        )

    @staticmethod
    def _issue_not_found(number) -> IssueResult:
        return IssueResult(
            operation_status=_NOT_FOUND,
            operation_metadata={"error": f"issue not found: {number}"},
        )
