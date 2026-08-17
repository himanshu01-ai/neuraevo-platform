"""GitHub capability models (Sprint 15.14 — immutable Git/GitHub DTOs).

Provider-independent, immutable DTOs and enums for the GitHub execution capability:
repositories, branches, commits, tags, issues, status, the change artifact, and the
operation request. A :class:`RepositoryInfo`/:class:`CommitInfo`/:class:`IssueInfo`
is a plain snapshot of one entity (never a ``git``/``pygit2``/``GitPython``/GitHub
SDK object or an API response, and never an internal storage object).

Validation helpers live here because they produce/guard these DTOs:
:func:`validate_branch_name`, :func:`validate_tag_name`,
:func:`validate_commit_message`, :func:`validate_repository_name`, and the
``deterministic_*_id`` helpers (stable, content-addressed ids). They raise
:class:`GitHubValidationError`, which the capability catches at its boundary.
Strictly additive to Sprints 15.1–15.13. The result DTOs live in
:mod:`app.services.runtime.github_results`.
"""

import hashlib
import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# Branch/tag ref name shape: git-ref-ish, but deliberately strict.
_REF_RE = re.compile(r"^[A-Za-z0-9._\-/]+$")
# Repository name shape: a single safe path segment (no separators/traversal).
_REPO_NAME_RE = re.compile(r"^[A-Za-z0-9._\-]+$")


class GitHubValidationError(ValueError):
    """Raised when a repository/branch/tag/commit/issue input is invalid.

    The capability catches this at its boundary and reports a graceful ``FAILED``
    result; the exception object never crosses a capability boundary.
    """


class GitHubOperation(str, Enum):
    """The allowed, deterministic GitHub operation labels."""

    INIT = "INIT"
    CLONE = "CLONE"
    OPEN = "OPEN"
    REPOSITORY_METADATA = "REPOSITORY_METADATA"
    LIST_BRANCHES = "LIST_BRANCHES"
    CREATE_BRANCH = "CREATE_BRANCH"
    CHECKOUT = "CHECKOUT"
    DELETE_BRANCH = "DELETE_BRANCH"
    STATUS = "STATUS"
    STAGE = "STAGE"
    UNSTAGE = "UNSTAGE"
    COMMIT = "COMMIT"
    HISTORY = "HISTORY"
    CREATE_TAG = "CREATE_TAG"
    LIST_TAGS = "LIST_TAGS"
    CREATE_ISSUE = "CREATE_ISSUE"
    LIST_ISSUES = "LIST_ISSUES"
    UPDATE_ISSUE = "UPDATE_ISSUE"
    CLOSE_ISSUE = "CLOSE_ISSUE"
    SEARCH_ISSUES = "SEARCH_ISSUES"


class GitHubOperationStatus(str, Enum):
    """The allowed, deterministic GitHub operation outcomes.

    ``SUCCESS`` — completed. ``NOT_FOUND`` — a required repository/branch/issue did
    not exist. ``FAILED`` — an invalid name/message/path or an invalid operation. The
    bridge maps ``SUCCESS`` to ``COMPLETED`` and everything else to ``FAILED``.
    """

    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    FAILED = "FAILED"


class IssueState(str, Enum):
    """The state of an issue: ``OPEN`` or ``CLOSED``."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class GitHubArtifactType(str, Enum):
    """The kind of change an artifact records."""

    COMMIT = "COMMIT"
    BRANCH = "BRANCH"
    TAG = "TAG"
    ISSUE = "ISSUE"
    REPORT = "REPORT"


class RepositoryInfo(BaseModel):
    """Immutable snapshot of a repository (no git/SDK/storage object exposed).

    ``frozen=True`` makes instances immutable. ``repository_id`` is the deterministic
    id; ``name`` and ``path`` identify it; ``default_branch``/``current_branch`` are
    the refs; ``description`` is optional; ``branch_count``/``commit_count``/
    ``tag_count``/``issue_count`` are tallies; and ``repository_metadata`` carries
    plain descriptors (e.g. a clone source). Never a git object or API response.
    """

    model_config = ConfigDict(frozen=True)

    repository_id: str
    name: str
    path: str
    default_branch: str = "main"
    current_branch: str = "main"
    description: Optional[str] = None
    branch_count: int = 0
    commit_count: int = 0
    tag_count: int = 0
    issue_count: int = 0
    repository_metadata: Dict[str, Any] = Field(default_factory=dict)


class BranchInfo(BaseModel):
    """Immutable snapshot of a branch (no git object exposed).

    ``frozen=True`` makes instances immutable. ``name`` is the branch name;
    ``head_commit_id`` is the commit it points at (``None`` before any commit);
    ``is_current``/``is_default`` flag the checked-out/default branch; and
    ``branch_metadata`` carries plain descriptors.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    head_commit_id: Optional[str] = None
    is_current: bool = False
    is_default: bool = False
    branch_metadata: Dict[str, Any] = Field(default_factory=dict)


class CommitInfo(BaseModel):
    """Immutable snapshot of a commit (no git object exposed).

    ``frozen=True`` makes instances immutable. ``commit_id`` is the deterministic id;
    ``message`` is the commit message; ``author`` is the author string;
    ``parent_id`` is the parent commit (``None`` for the root); ``branch`` is the
    branch it was made on; ``changed_files`` are the paths it changed; ``timestamp``
    is a deterministic ordering value; and ``commit_metadata`` carries plain
    descriptors. Never a git object or SHA-bearing SDK object.
    """

    model_config = ConfigDict(frozen=True)

    commit_id: str
    message: str
    author: str
    parent_id: Optional[str] = None
    branch: str = "main"
    changed_files: List[str] = Field(default_factory=list)
    timestamp: float = 0.0
    commit_metadata: Dict[str, Any] = Field(default_factory=dict)


class TagInfo(BaseModel):
    """Immutable snapshot of a tag (no git object exposed).

    ``frozen=True`` makes instances immutable. ``name`` is the tag name; ``tag_id``
    is the deterministic id; ``commit_id`` is the tagged commit; ``message`` is the
    optional annotation; and ``tag_metadata`` carries plain descriptors.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    tag_id: str
    commit_id: Optional[str] = None
    message: Optional[str] = None
    tag_metadata: Dict[str, Any] = Field(default_factory=dict)


class IssueInfo(BaseModel):
    """Immutable snapshot of an issue (no SDK object / API response exposed).

    ``frozen=True`` makes instances immutable. ``issue_id`` is the deterministic id;
    ``number`` is the sequential issue number; ``title``/``body`` are the content;
    ``state`` is an :class:`IssueState` label; ``labels``/``assignees`` are plain
    string lists; ``created_at``/``updated_at`` are deterministic ordering values;
    and ``issue_metadata`` carries plain descriptors.
    """

    model_config = ConfigDict(frozen=True)

    issue_id: str
    number: int
    title: str
    body: Optional[str] = None
    state: str = IssueState.OPEN.value
    labels: List[str] = Field(default_factory=list)
    assignees: List[str] = Field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0
    issue_metadata: Dict[str, Any] = Field(default_factory=dict)


class RepositoryStatus(BaseModel):
    """Immutable working-tree status of a repository (no git object exposed).

    ``frozen=True`` makes instances immutable. ``repository_id`` and
    ``current_branch`` identify the context; ``staged_files`` are changes ready to
    commit; ``unstaged_files`` are modified-but-not-staged files; ``untracked_files``
    are new files not yet staged; ``is_clean`` is ``True`` when all three are empty;
    and ``status_metadata`` carries plain descriptors.
    """

    model_config = ConfigDict(frozen=True)

    repository_id: str
    current_branch: str = "main"
    staged_files: List[str] = Field(default_factory=list)
    unstaged_files: List[str] = Field(default_factory=list)
    untracked_files: List[str] = Field(default_factory=list)
    is_clean: bool = True
    status_metadata: Dict[str, Any] = Field(default_factory=dict)


class GitHubArtifact(BaseModel):
    """Immutable description of one change an operation produced (no SDK object).

    ``frozen=True`` makes instances immutable. ``artifact_id`` is a deterministic
    identifier; ``artifact_type`` is a :class:`GitHubArtifactType` label;
    ``artifact_name`` is a human name; ``artifact_path`` is a workspace-relative path
    where applicable (``None`` otherwise); and ``artifact_metadata`` carries plain
    descriptors. Building it runs nothing and carries no credential.
    """

    model_config = ConfigDict(frozen=True)

    artifact_id: str
    artifact_type: str
    artifact_name: str
    artifact_path: Optional[str] = None
    artifact_metadata: Dict[str, Any] = Field(default_factory=dict)


class GitHubOperationRequest(BaseModel):
    """Immutable request to perform one GitHub operation (no execution).

    ``frozen=True`` makes instances immutable. ``operation`` is a
    :class:`GitHubOperation` label. The remaining fields are the union the
    operations need: ``repository_id``/``repository_name``/``repository_path``/
    ``description``/``source_url`` (init/clone/open/metadata); ``branch_name``
    (branch ops); ``files``/``paths``/``commit_message``/``author`` (stage/unstage/
    commit); ``limit`` (history); ``tag_name``/``tag_message``/``commit_id`` (tags);
    ``issue_number``/``issue_title``/``issue_body``/``labels``/``assignees``/
    ``issue_state``/``update_fields`` (issues); ``query``/``state_filter`` (search/
    list issues); and ``request_metadata`` for plain descriptors. Building this DTO
    executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    operation: str
    repository_id: Optional[str] = None
    repository_name: Optional[str] = None
    repository_path: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    branch_name: Optional[str] = None
    files: Dict[str, str] = Field(default_factory=dict)
    paths: List[str] = Field(default_factory=list)
    commit_message: Optional[str] = None
    author: Optional[str] = None
    limit: Optional[int] = None
    tag_name: Optional[str] = None
    tag_message: Optional[str] = None
    commit_id: Optional[str] = None
    issue_number: Optional[int] = None
    issue_title: Optional[str] = None
    issue_body: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    assignees: List[str] = Field(default_factory=list)
    issue_state: Optional[str] = None
    update_fields: Dict[str, Any] = Field(default_factory=dict)
    query: Optional[str] = None
    state_filter: str = "all"
    request_metadata: Dict[str, Any] = Field(default_factory=dict)


# =====================================================================
# Validation helpers
# =====================================================================
def validate_repository_name(name: str) -> str:
    """Return ``name`` if it is a safe single-segment repository name, else raise.

    Rejects empty names, path separators, and traversal so a repository can never be
    staged outside its workspace. Raises :class:`GitHubValidationError` otherwise.
    """
    if not isinstance(name, str) or not name.strip():
        raise GitHubValidationError("repository name is required")
    candidate = name.strip()
    if not _REPO_NAME_RE.match(candidate) or candidate in (".", ".."):
        raise GitHubValidationError(f"invalid repository name: {name!r}")
    return candidate


def validate_branch_name(name: str) -> str:
    """Return ``name`` if it is a valid branch ref, else raise.

    Rejects empty names, whitespace, ``..``, leading/trailing ``/``, ``.lock``
    suffixes, and characters outside ``[A-Za-z0-9._/-]``. Raises
    :class:`GitHubValidationError` otherwise.
    """
    return _validate_ref(name, "branch")


def validate_tag_name(name: str) -> str:
    """Return ``name`` if it is a valid tag ref, else raise (see :func:`validate_branch_name`)."""
    return _validate_ref(name, "tag")


def _validate_ref(name: str, kind: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise GitHubValidationError(f"{kind} name is required")
    candidate = name.strip()
    if (
        " " in candidate
        or ".." in candidate
        or candidate.startswith("/")
        or candidate.endswith("/")
        or candidate.endswith(".lock")
        or not _REF_RE.match(candidate)
    ):
        raise GitHubValidationError(f"invalid {kind} name: {name!r}")
    return candidate


def validate_commit_message(message: Optional[str]) -> str:
    """Return the stripped ``message`` if non-empty, else raise."""
    if not isinstance(message, str) or not message.strip():
        raise GitHubValidationError("commit message must be a non-empty string")
    return message.strip()


def _short_hash(*parts: str) -> str:
    basis = "|".join(str(part) for part in parts)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]


def deterministic_repository_id(identifier: str) -> str:
    """Return a stable ``repo-<hex>`` id derived from a repository path/name."""
    return f"repo-{_short_hash(identifier)}"


def deterministic_commit_id(
    repository_id: str, parent_id: Optional[str], message: str, tree_digest: str, author: str
) -> str:
    """Return a stable ``commit-<hex>`` id derived from the commit's content."""
    return f"commit-{_short_hash(repository_id, parent_id or '', message, tree_digest, author)}"


def deterministic_tag_id(repository_id: str, name: str, commit_id: Optional[str]) -> str:
    """Return a stable ``tag-<hex>`` id derived from the tag's target."""
    return f"tag-{_short_hash(repository_id, name, commit_id or '')}"


def deterministic_issue_id(repository_id: str, number: int) -> str:
    """Return a stable ``issue-<hex>`` id derived from the repo and issue number."""
    return f"issue-{_short_hash(repository_id, str(number))}"


def tree_digest(tree: Dict[str, str]) -> str:
    """Return a deterministic digest of a file tree (``path->content``)."""
    joined = "\n".join(f"{path}={tree[path]}" for path in sorted(tree))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
